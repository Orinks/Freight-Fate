"""Player profile with atomic packed-container save/load.

Saves are ``.ffsave`` files: a magic header plus zlib-compressed JSON, signed
inside with this install's HMAC key. The container keeps casual hand-editing
out of career state; the signature is the actual tamper check, and a failed
check marks the profile as modified rather than refusing to load it. Plain
``.json`` saves from older versions still load and are converted in place.

On Windows and Linux, Freight Fate is portable: profiles and settings live
in a ``saves`` directory inside the game's own main directory — next to the
executable in frozen builds, the project root when running from source.

macOS apps live in ``/Applications`` and must not write beside themselves
(that folder is admin-owned and often read-only), so on macOS saves go in the
standard per-user ``~/Library/Application Support/FreightFate`` folder.

The same reasoning covers Windows and Linux when the game itself sits in a
read-only location (for example Windows ``Program Files``): if the ``saves``
folder beside the game cannot be written, saves fall back to that per-user
data directory instead of failing on the first write and crashing mid-session.

Override the location with the ``FREIGHT_FATE_DATA_DIR`` environment variable
(which the tests use). Saves from older versions or misplaced layouts are
migrated into the active location automatically on first run.

When running from source, ``FREIGHT_FATE_SKIP_SAVE_SIGNING=1`` skips the
save-signature check (the file is re-signed locally on load) so arbitrary
save files can be loaded for testing. Frozen builds ignore the flag.

Saves are atomic: written to a temp file, then renamed over the old save,
so a crash mid-write can never corrupt an existing profile.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import logging
import os
import secrets
import shutil
import sys
import zlib
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..sim.hos import DutyLog, HosClock
from ..updater import is_frozen
from .business import COMPANY_DRIVER, INDEPENDENT_AUTHORITY, is_owner_operator
from .career import Career
from .career_ladder import STARTER_CARRIER_NAME
from .loyalty import LoyaltyAccount
from .market import Market
from .start_options import DEFAULT_START_KEY, START_MODE_COMPANY

log = logging.getLogger(__name__)

# The 1.9 line's per-truck condition records are plain dicts, so the
# TruckCondition dataclass the mainline introduced is not imported here.
SAVE_VERSION = 11
STARTING_MONEY = 5_000.0
DEFAULT_CITY = "chicago_il_us"
DEFAULT_FUEL_GAL = 150.0
SIGNATURE_FIELD = "_signature"
SIGNATURE_VERSION_FIELD = "_signature_version"
SIGNATURE_VERSION = 2
SECRET_FILE = "profile.key"

# Condition fields that were stored flat on the profile before per-truck
# conditions (SAVE_VERSION 11 / SIGNATURE_VERSION 2). Kept for two reasons:
# validating v1 signatures against the field set they were signed over, and
# migrating legacy saves into per-truck records.
_LEGACY_CONDITION_FIELDS = (
    "truck_damage_pct",
    "tire_wear_pct",
    "brake_wear_pct",
    "engine_wear_pct",
    "truck_fuel_gal",
)

# Packed save container: this magic header, then zlib-deflated profile JSON.
# The container stops accidental and casual hand-editing; the HMAC signature
# inside the JSON remains the actual tamper check. Legacy plain-JSON saves
# still load and are converted on their next save (the old file is kept as
# ``.json.bak`` so an older game version can still be rolled back to).
SAVE_MAGIC = b"FFSAVE1\x00"
SAVE_SUFFIX = ".ffsave"
LEGACY_SAVE_SUFFIX = ".json"

# Called with the profile after every successful save. The app points this at
# the cloud backup service so every save site -- deliveries, achievements,
# menu exits, shutdown -- queues a backup without knowing the service exists.
# Best-effort only: a listener failure must never break the local save.
save_listener: Callable[[Profile], None] | None = None

_legacy_checked = False
_unwritable_warned = False


def _macos_data_dir() -> Path:
    """The standard per-user save location on macOS."""
    return Path.home() / "Library" / "Application Support" / "FreightFate"


def _legacy_data_dir() -> Path:
    """Where saves lived before the portable layout (per-user folders).

    On macOS this is also the *current* save location, since app bundles
    cannot store saves beside themselves.
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        return _macos_data_dir()
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "FreightFate"


def _is_writable_dir(path: Path) -> bool:
    """Whether ``path`` exists (or can be created) and accepts a write.

    Detects installs in protected locations, such as Windows ``Program
    Files``, where the portable ``saves`` folder beside the game would raise
    on the first save and crash the game mid-session.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".freightfate-write-test"
        probe.write_text("", encoding="ascii")
        probe.unlink()
    except OSError:
        return False
    return True


def _save_root() -> Path:
    """The active save directory for this platform.

    Windows and Linux keep the portable ``saves`` folder next to the game.
    macOS uses the per-user Application Support folder so the app never has to
    write into ``/Applications``. When the game sits in a read-only location
    such as ``Program Files``, Windows and Linux fall back to that same
    per-user folder rather than crashing on the first save.
    """
    if sys.platform == "darwin":
        return _macos_data_dir()
    if _is_writable_dir(game_root()):
        return game_root() / "saves"
    fallback = _legacy_data_dir()
    global _unwritable_warned
    if not _unwritable_warned:
        _unwritable_warned = True
        log.warning(
            "Game directory %s is not writable; saving to the per-user folder "
            "%s instead. Move Freight Fate out of a protected location such as "
            "Program Files to keep saves beside the game.",
            game_root(),
            fallback,
        )
    return fallback


def game_root() -> Path:
    """The game's main directory: the executable's directory when frozen,
    the project root when running from source."""
    if is_frozen():
        exe_dir = _frozen_executable_dir()
        app_bundle = _macos_app_bundle(exe_dir)
        if app_bundle is not None:
            return app_bundle.parent
        return exe_dir
    return Path(__file__).resolve().parents[3]


def _frozen_executable_dir() -> Path:
    return Path(sys.executable).resolve().parent


def _macos_app_bundle(exe_dir: Path) -> Path | None:
    if sys.platform != "darwin":
        return None
    if exe_dir.name != "MacOS" or exe_dir.parent.name != "Contents":
        return None
    bundle = exe_dir.parent.parent
    return bundle if bundle.suffix == ".app" else None


def _migrate_legacy(target: Path) -> None:
    """One-time migration of old save folders into the portable one."""
    if _migrate_nearby_portable_saves(target):
        return
    if target.exists():
        return
    legacy = _legacy_data_dir()
    if legacy != target and legacy.is_dir():
        # A first run silently inheriting an old career looks like a haunted
        # save; the log line makes "where did this come from" answerable.
        log.info("Save migration: copying legacy saves from %s into %s", legacy, target)
        _copy_save_tree(legacy, target)


def _migrate_nearby_portable_saves(target: Path) -> bool:
    """Move earlier portable layouts into the current save root.

    These folders are already user-owned portable save folders near the game,
    so leaving them behind creates two plausible save locations. Per-user
    legacy folders are still copied, not moved.
    """
    for source in _portable_migration_candidates():
        if not source.is_dir():
            continue
        if not target.exists():
            log.info("Save migration: moving portable saves from %s to %s", source, target)
            _move_save_tree(source, target)
            return target.exists()
        log.info("Save migration: merging portable saves from %s into %s", source, target)
        _merge_save_tree(source, target)
        return True
    return False


def _leave_migration_marker(source: Path, target: Path) -> None:
    """A breadcrumb where a moved save tree used to be.

    A plain text file (never a directory, so it can't re-trigger candidate
    scans) telling a player -- or a debugging session -- where the saves went
    instead of leaving them to vanish without a trace.
    """
    marker = source.with_name(source.name + "-moved.txt")
    with contextlib.suppress(OSError):
        marker.write_text(
            "Freight Fate moved the saves that were in this folder to:\n"
            f"{target}\n"
            "This breadcrumb is safe to delete.\n",
            encoding="utf-8",
        )


def _copy_save_tree(source: Path, target: Path) -> None:
    """Copy a save tree without blocking startup if the filesystem objects."""
    # never block startup on a migration; old saves stay where they are
    with contextlib.suppress(OSError):
        shutil.copytree(source, target)


def _move_save_tree(source: Path, target: Path) -> None:
    """Move a nearby portable save folder into the active location."""
    with contextlib.suppress(OSError):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        _leave_migration_marker(source, target)


def _merge_save_tree(source: Path, target: Path) -> None:
    """Merge a duplicate nearby save folder without overwriting current saves."""
    with contextlib.suppress(OSError):
        for path in sorted(source.rglob("*")):
            dest = target / path.relative_to(source)
            if path.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            elif not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(dest))
        # Remove the duplicate tree only when every file was moved or already
        # existed in the active tree, and leave a breadcrumb in its place.
        if not any(path.is_file() for path in source.rglob("*")):
            shutil.rmtree(source, ignore_errors=True)
            _leave_migration_marker(source, target)


def _portable_migration_candidates() -> list[Path]:
    """Nearby save roots to fold into the active location.

    Covers previous archive nesting layouts and, on macOS, the misplaced
    ``saves`` folder beside the app bundle (or inside it) that earlier builds
    created in ``/Applications``.
    """
    root = game_root()
    parent = root.parent
    candidates = [
        root / "saves",
        root / "FreightFate" / "saves",
        parent / "saves",
        parent / "FreightFate" / "saves",
    ]
    if is_frozen():
        candidates.append(_frozen_executable_dir() / "saves")
    target = _save_root()
    seen: set[Path] = set()
    result: list[Path] = []
    for path in candidates:
        if path == target or path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


def data_dir() -> Path:
    override = os.environ.get("FREIGHT_FATE_DATA_DIR")
    if override:
        return Path(override)
    global _legacy_checked
    target = _save_root()
    if not _legacy_checked:
        _legacy_checked = True
        _migrate_legacy(target)
    return target


def profiles_dir() -> Path:
    d = data_dir() / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _known_fields(cls, payload) -> dict:
    """The subset of a nested save payload this build's dataclass accepts."""
    if not isinstance(payload, dict):
        return {}
    return {k: v for k, v in payload.items() if k in cls.__dataclass_fields__}


class ProfileIntegrityError(ValueError):
    """A save file failed its integrity signature check."""


def _secret_path() -> Path:
    return data_dir() / SECRET_FILE


def _profile_secret() -> bytes:
    """Per-install save signing key.

    This is not DRM: local users can ultimately control local files. It stops
    casual JSON edits from silently becoming trusted career state.
    """
    path = _secret_path()
    try:
        return bytes.fromhex(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        path.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_bytes(32)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(secret.hex(), encoding="ascii")
        os.replace(tmp, path)
        return secret


def _signed_payload(data: dict, signature_version: int) -> dict:
    # The mainline kept a flat _LEGACY_SIGNED_FIELDS allow-list for the same
    # job; this line versions the signature instead, so the older field set is
    # consulted only for the saves that were actually signed over it.
    allowed = set(Profile.__dataclass_fields__) | {"version"}
    if signature_version < 2:
        # v1 saves signed the flat condition fields, before per-truck
        # conditions replaced them. Validate against that older field set so a
        # legitimately signed v1 save is not quarantined on first load.
        allowed = (allowed - {"truck_conditions"}) | set(_LEGACY_CONDITION_FIELDS)
    return {key: data[key] for key in sorted(allowed) if key in data}


def _signature_for(data: dict, signature_version: int | None = None) -> str:
    if signature_version is None:
        signature_version = int(data.get(SIGNATURE_VERSION_FIELD, 1))
    payload = json.dumps(
        _signed_payload(data, signature_version),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hmac.new(_profile_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _is_signature_valid(data: dict) -> bool:
    signature = data.get(SIGNATURE_FIELD)
    if not isinstance(signature, str):
        return False
    return hmac.compare_digest(signature, _signature_for(data))


def encode_save_bytes(data: dict) -> bytes:
    """Pack an already-signed profile dict into the on-disk container form."""
    text = json.dumps(data, indent=2)
    return SAVE_MAGIC + zlib.compress(text.encode("utf-8"))


def _decode_save_bytes(raw: bytes) -> tuple[dict, bool]:
    """Parse container or legacy plain-JSON save bytes.

    Returns the profile dict and whether the bytes were a packed container.
    Raises ProfileIntegrityError for bytes that cannot be decoded at all.
    """
    packed = raw.startswith(SAVE_MAGIC)
    if packed:
        try:
            text = zlib.decompress(raw[len(SAVE_MAGIC) :]).decode("utf-8")
        except (zlib.error, UnicodeDecodeError) as e:
            raise ProfileIntegrityError("Save file is damaged and could not be read.") from e
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ProfileIntegrityError("Save file is damaged and could not be read.") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ProfileIntegrityError("Save file is damaged and could not be read.") from e
    if not isinstance(data, dict):
        raise ProfileIntegrityError("Save file is not a profile object.")
    return data, packed


def _sanitized_stem(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()
    return safe or "Driver"


def save_path_for(name: str) -> Path:
    """The canonical packed save path for a profile or cloud slot name."""
    return profiles_dir() / f"{_sanitized_stem(name)}{SAVE_SUFFIX}"


def find_save_path(name: str) -> Path | None:
    """The existing save file for a slot name: packed preferred, legacy accepted."""
    packed = save_path_for(name)
    if packed.exists():
        return packed
    legacy = packed.with_suffix(LEGACY_SAVE_SUFFIX)
    return legacy if legacy.exists() else None


def _signing_checks_disabled() -> bool:
    """Dev escape hatch: ``FREIGHT_FATE_SKIP_SAVE_SIGNING=1`` loads any save
    regardless of its signature, so arbitrary files can be tested. Honored
    only when running from source; frozen player builds always enforce
    signing so the flag can never become a tampering vector."""
    return not is_frozen() and os.environ.get("FREIGHT_FATE_SKIP_SAVE_SIGNING") == "1"


def _quarantine(path: Path) -> Path:
    target = path.with_suffix(path.suffix + ".invalid")
    n = 1
    while target.exists():
        target = path.with_suffix(path.suffix + f".invalid{n}")
        n += 1
    os.replace(path, target)
    return target


def _fresh_condition(fuel_gal: float = DEFAULT_FUEL_GAL) -> dict:
    """A brand-new truck's condition record: no wear, no damage, given fuel.

    Traction equipment rides in the same record -- tire compound, whether a
    chain set is aboard, and how worn that set is -- because it bolts to the
    truck, not the driver. Older records missing these keys read as the
    defaults through the property ``get`` calls below.
    """
    return {
        "tire_wear_pct": 0.0,
        "brake_wear_pct": 0.0,
        "engine_wear_pct": 0.0,
        "damage_pct": 0.0,
        "fuel_gal": fuel_gal,
        "tire_type": "all_season",
        "chains_owned": False,
        "chain_wear_pct": 0.0,
    }


def _truck_tank_gal(key: str, upgrades: dict | None = None) -> float:
    """A truck's full-tank capacity, or the default if its specs won't build.

    Upgrades matter here: a long-range tank is a truck's capacity, so a career
    that bought one must not be migrated back down to the base tank.
    """
    try:
        from .trucks import build_truck_specs

        return float(build_truck_specs(key, upgrades or {}).fuel_tank_gal)
    except Exception:
        return DEFAULT_FUEL_GAL


def _migrate_flat_conditions(data: dict) -> dict:
    """Build per-truck condition records from a pre-migration flat profile.

    Every owned truck (and the active/assigned key) inherits the profile's one
    saved wear and damage set -- no free pristine spares from a swap. The
    active truck also inherits the saved fuel; other parked trucks start with
    full tanks (they were sitting still, and a fuel windfall is worth cents,
    not an exploit).
    """

    def _pct(key: str) -> float:
        # Clamped, not trusted. A save carrying an impossible wear figure is
        # repaired on the way in; loading it verbatim would leave an old career
        # failing its own invariant check the moment it opened, which reads to
        # the player as a tampered save rather than an old one.
        return max(0.0, min(100.0, float(data.get(key, 0.0))))

    tire = _pct("tire_wear_pct")
    brake = _pct("brake_wear_pct")
    engine = _pct("engine_wear_pct")
    damage = _pct("truck_damage_pct")

    owns = is_owner_operator(data.get("business_status", COMPANY_DRIVER))
    active = str(data.get("truck", "rig")) if owns else "rig"
    keys = {str(k) for k in (data.get("owned_trucks") or [])}
    keys.add(active)

    # Tanks are sized with the career's upgrades applied, so a driver who paid
    # for a long-range tank keeps it through the migration on every truck.
    upgrades = data.get("upgrades")
    if not isinstance(upgrades, dict):
        upgrades = {}
    active_tank = _truck_tank_gal(active, upgrades)
    fuel = max(0.0, min(active_tank, float(data.get("truck_fuel_gal", DEFAULT_FUEL_GAL))))

    conditions: dict[str, dict] = {}
    for key in keys:
        conditions[key] = {
            "tire_wear_pct": tire,
            "brake_wear_pct": brake,
            "engine_wear_pct": engine,
            "damage_pct": damage,
            "fuel_gal": fuel if key == active else _truck_tank_gal(key, upgrades),
        }
    return conditions


@dataclass
class Profile:
    name: str = "Driver"
    money: float = STARTING_MONEY
    current_city: str = DEFAULT_CITY
    # Road grime stays profile-wide on this line; the per-truck record carries
    # tire, brake and engine wear, which the physics earns per tractor.
    road_grime_pct: float = 0.0
    # truck_conditions is declared above -- this line's records are plain dicts
    # holding traction gear as well as wear, so the mainline's typed record is
    # not repeated here.
    # An old save was converted to the per-truck format; the player has not yet
    # heard the one-time notice. Cleared when they dismiss it.
    migration_notice_pending: bool = False
    # The save failed its local signature check (edited outside the game, or
    # copied from another machine, whose signing key differs). Sticky: it is
    # signed into every later save, so clearing it by hand just trips the
    # signature again. Local play continues; shared features read this flag.
    integrity_modified: bool = False
    # The player has not yet heard the one-time spoken notice about the flag.
    integrity_notice_pending: bool = False
    game_hours: float = 6.0  # in-game clock, hours since career start
    # Whole-day offset used only by the spoken calendar and seasonal weather.
    # Existing careers can anchor their independent calendar to today's date
    # without changing deadlines, HOS, markets, or elapsed career time.
    calendar_offset_days: int = 0
    tutorial_done: bool = False
    truck: str = "rig"  # owner-operator active tractor, or assignment key
    owned_trucks: list[str] = field(default_factory=list)  # owned tractors after buy-in
    # Condition follows the truck, not the profile: wear, damage, and fuel per
    # owned truck key. The flat ``tire_wear_pct``/``truck_fuel_gal``/... names
    # remain as properties (below) proxying to the active truck's record.
    truck_conditions: dict[str, dict] = field(default_factory=dict)
    upgrades: dict[str, int] = field(default_factory=dict)  # owned-tractor upgrade key -> tier
    active_trip: dict | None = None  # mid-delivery snapshot, see DrivingState
    dispatch_board_cache: dict | None = None
    fatigue: float = 0.0  # 0 fresh .. 100 exhausted
    active_buffs: list = field(default_factory=list)  # timed consumables, see data/buffs.py
    pay_advance: float = 0.0  # outstanding dispatcher advance owed, repaid at delivery
    pay_advance_used_for_load: bool = False
    business_status: str = COMPANY_DRIVER  # company driver, then leased-on owner-operator
    carrier_name: str = STARTER_CARRIER_NAME
    carrier_key: str = DEFAULT_START_KEY
    start_mode: str = START_MODE_COMPANY
    authority_readiness: bool = False
    trailer_programs: list[str] = field(default_factory=list)
    owned_trailers: list[str] = field(default_factory=list)
    career: Career = field(default_factory=Career)
    market: Market = field(default_factory=Market)
    hos: HosClock = field(default_factory=HosClock)  # hours-of-service shift clock
    duty_log: DutyLog = field(default_factory=DutyLog)  # rolling Record of Duty Status
    loyalty: LoyaltyAccount = field(default_factory=LoyaltyAccount)  # truck stop loyalty program
    achievements: list[str] = field(default_factory=list)
    achievement_stats: dict = field(default_factory=dict)
    # Last few delivered from:to lanes, newest first -- assigned dispatch
    # prefers a lane not in this list so short-haul careers stop bouncing
    # between the same two cities forever.
    recent_lanes: list[str] = field(default_factory=list)

    # Set on the instance by from_dict when the raw dict needed a format
    # migration, so load() can rewrite the converted save to disk. Never
    # serialized (it is a class attribute, not a dataclass field).
    needs_migration_resave = False

    # -- serialization -------------------------------------------------------

    def to_dict(self) -> dict:
        d = asdict(self)
        d["version"] = SAVE_VERSION
        d[SIGNATURE_VERSION_FIELD] = SIGNATURE_VERSION
        d[SIGNATURE_FIELD] = _signature_for(d)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Profile:
        from .save_migration import migrate_save_data

        d, migrated = migrate_save_data(dict(d))
        d.pop("version", None)
        d.pop(SIGNATURE_FIELD, None)
        d.pop(SIGNATURE_VERSION_FIELD, None)
        # Nested payloads keep only the fields this build knows: saves written
        # by a newer snapshot (or an older one with since-removed fields) load
        # instead of crashing on an unexpected keyword.
        # Pre-11 saves stored one flat condition set; fan it out per truck so
        # each owned tractor keeps its own wear, damage, and fuel from here on.
        if not isinstance(d.get("truck_conditions"), dict):
            d["truck_conditions"] = _migrate_flat_conditions(d)
        career = Career(**_known_fields(Career, d.pop("career", {})))
        market = Market(**_known_fields(Market, d.pop("market", {})))
        hos = HosClock.from_dict(d.pop("hos", None))  # absent in v2 saves: fresh clock
        duty_log = DutyLog.from_dict(d.pop("duty_log", None))
        loyalty = LoyaltyAccount(**_known_fields(LoyaltyAccount, d.pop("loyalty", {})))
        known = {
            f
            for f in cls.__dataclass_fields__
            if f not in ("career", "market", "hos", "duty_log", "loyalty")
        }
        # truck_conditions rides through kwargs: on this line the records are
        # plain dicts, already fanned out per truck above, so they need no
        # per-record construction on the way in.
        kwargs = {k: v for k, v in d.items() if k in known}
        profile = cls(
            career=career, market=market, hos=hos, duty_log=duty_log, loyalty=loyalty, **kwargs
        )
        # A save that had to be migrated on load is rewritten on the next save,
        # so the conversion is not redone on every launch.
        profile.needs_migration_resave = migrated
        return profile

    # -- truck ------------------------------------------------------------------

    def owns_equipment(self) -> bool:
        """True when the profile is responsible for owned tractor equipment."""
        return is_owner_operator(self.business_status)

    def active_truck_key(self) -> str:
        """Truck model currently used for simulation.

        Company drivers operate whatever tractor the carrier fleet has
        assigned for their level band. The profile still carries ``truck``
        for save compatibility and for the owner-operator path, but
        company-driver play should not treat it as player-owned equipment.
        """
        if self.owns_equipment():
            return self.truck
        from .carrier_fleet import assigned_truck_key

        return assigned_truck_key(self)

    def visible_owned_trucks(self) -> tuple[str, ...]:
        """Player-owned tractors to show in menus."""
        return tuple(self.owned_trucks) if self.owns_equipment() else ()

    def active_trailer_programs(self) -> tuple[str, ...]:
        """Trailer programs the player controls for owner-operator dispatch."""
        if not self.owns_equipment():
            return ()
        from .trailers import DEFAULT_TRAILER_PROGRAMS, normalized_trailer_programs

        programs = normalized_trailer_programs(self.trailer_programs)
        if self.business_status == INDEPENDENT_AUTHORITY:
            owned = normalized_trailer_programs(self.owned_trailers)
            combined = list(programs)
            for key in owned:
                if key not in combined:
                    combined.append(key)
            if combined:
                return tuple(combined)
        if programs:
            return programs
        return DEFAULT_TRAILER_PROGRAMS

    def visible_owned_trailers(self) -> tuple[str, ...]:
        """Player-owned trailers to show in menus."""
        if self.business_status != INDEPENDENT_AUTHORITY:
            return ()
        from .trailers import normalized_trailer_programs

        return normalized_trailer_programs(self.owned_trailers)

    def truck_specs(self):
        """The active truck's specs with this profile's upgrades applied."""
        from .trucks import build_truck_specs

        upgrades = self.upgrades if self.owns_equipment() else {}
        return build_truck_specs(self.active_truck_key(), upgrades)

    # -- per-truck condition ---------------------------------------------------
    #
    # Condition lives in ``truck_conditions`` keyed by truck. The flat names
    # below stay as properties routed through the *active* truck's record, so
    # the garage, the rig readout, and the save layer keep using ``p.tire_wear_pct``
    # unchanged while each truck carries its own wear, damage, and fuel.

    def _condition(self) -> dict:
        """The active truck's condition record, created on first touch."""
        key = self.active_truck_key()
        rec = self.truck_conditions.get(key)
        if rec is None:
            rec = _fresh_condition()
            self.truck_conditions[key] = rec
        return rec

    def provision_truck_condition(self, key: str, fuel_gal: float | None = None) -> None:
        """Give a newly acquired truck its own fresh, full-tank record."""
        tank = _truck_tank_gal(key) if fuel_gal is None else float(fuel_gal)
        self.truck_conditions[key] = _fresh_condition(tank)

    @property
    def tire_wear_pct(self) -> float:
        return float(self._condition().get("tire_wear_pct", 0.0))

    @tire_wear_pct.setter
    def tire_wear_pct(self, value: float) -> None:
        self._condition()["tire_wear_pct"] = float(value)

    @property
    def brake_wear_pct(self) -> float:
        return float(self._condition().get("brake_wear_pct", 0.0))

    @brake_wear_pct.setter
    def brake_wear_pct(self, value: float) -> None:
        self._condition()["brake_wear_pct"] = float(value)

    @property
    def engine_wear_pct(self) -> float:
        return float(self._condition().get("engine_wear_pct", 0.0))

    @engine_wear_pct.setter
    def engine_wear_pct(self, value: float) -> None:
        self._condition()["engine_wear_pct"] = float(value)

    @property
    def truck_damage_pct(self) -> float:
        return float(self._condition().get("damage_pct", 0.0))

    @truck_damage_pct.setter
    def truck_damage_pct(self, value: float) -> None:
        self._condition()["damage_pct"] = float(value)

    @property
    def truck_fuel_gal(self) -> float:
        return float(self._condition().get("fuel_gal", DEFAULT_FUEL_GAL))

    @truck_fuel_gal.setter
    def truck_fuel_gal(self, value: float) -> None:
        self._condition()["fuel_gal"] = float(value)

    @property
    def tire_type(self) -> str:
        return str(self._condition().get("tire_type", "all_season"))

    @tire_type.setter
    def tire_type(self, value: str) -> None:
        self._condition()["tire_type"] = str(value)

    @property
    def chains_owned(self) -> bool:
        return bool(self._condition().get("chains_owned", False))

    @chains_owned.setter
    def chains_owned(self, value: bool) -> None:
        self._condition()["chains_owned"] = bool(value)

    @property
    def chain_wear_pct(self) -> float:
        return float(self._condition().get("chain_wear_pct", 0.0))

    @chain_wear_pct.setter
    def chain_wear_pct(self, value: float) -> None:
        self._condition()["chain_wear_pct"] = float(value)

    def load_truck_condition(self, truck) -> None:
        """Put the saved rig condition onto a fresh ``TruckState`` at trip start.

        Fuel, incident damage, and the wear meters travel together so no
        sync site can pick up one and drop another.
        """
        truck.fuel_gal = min(self.truck_fuel_gal, truck.specs.fuel_tank_gal)
        truck.damage_pct = self.truck_damage_pct
        truck.tire_wear_pct = self.tire_wear_pct
        truck.brake_wear_pct = self.brake_wear_pct
        truck.engine_wear_pct = self.engine_wear_pct
        truck.tire_type = self.tire_type
        truck.chain_wear_pct = self.chain_wear_pct

    RECENT_LANES_KEPT = 6

    def remember_lane(self, lane: str) -> None:
        """Record a delivered from:to lane for dispatch-variety preference."""
        if not lane:
            return
        lanes = [lane] + [entry for entry in self.recent_lanes if entry != lane]
        self.recent_lanes = lanes[: self.RECENT_LANES_KEPT]

    def store_truck_condition(self, truck) -> None:
        """Write the rig's current condition back to the profile for saving."""
        self.truck_fuel_gal = truck.fuel_gal
        self.truck_damage_pct = truck.damage_pct
        self.tire_wear_pct = truck.tire_wear_pct
        self.brake_wear_pct = truck.brake_wear_pct
        self.engine_wear_pct = truck.engine_wear_pct
        # Tire type is chosen at the garage, never behind the wheel, so it only
        # flows profile-to-truck. Chain wear accrues while driving chained.
        self.chain_wear_pct = truck.chain_wear_pct

    def fatigue_buff_rate(self, now_h: float) -> float:
        """Fatigue accrual multiplier from the active food or drink buff.

        1.0 when nothing is active. ``now_h`` is the absolute game hour
        (game_hours plus trip minutes), the same clock the entries store.
        """
        for entry in self.active_buffs:
            if entry.get("group") == "fatigue" and now_h < float(entry.get("expires_h", 0.0)):
                return float(entry.get("rate", 1.0))
        return 1.0

    def add_timed_buff(self, entry: dict) -> None:
        """One active buff per group: the newest replaces its predecessor."""
        group = entry.get("group")
        self.active_buffs = [b for b in self.active_buffs if b.get("group") != group]
        self.active_buffs.append(entry)

    def expire_buffs(self, now_h: float) -> list[dict]:
        """Drop timed buffs past their hour; returns them for announcing."""
        expired = [b for b in self.active_buffs if now_h >= float(b.get("expires_h", 0.0))]
        if expired:
            self.active_buffs = [b for b in self.active_buffs if b not in expired]
        return expired

    # The mainline's condition accessors lived here -- condition_for plus a
    # second set of flat-name properties over a typed TruckCondition record.
    # This line already has both, above, over its own dict-shaped records:
    # keeping the pair would silently shadow them, and road_grime_pct is a
    # plain field here rather than a per-truck value.

    def market_day(self) -> int:
        return int(self.game_hours // 24)

    @property
    def calendar_game_hours(self) -> float:
        return self.game_hours + self.calendar_offset_days * 24.0

    def has_started_career(self) -> bool:
        """Whether this profile has progressed beyond a just-created career."""
        return bool(
            self.game_hours > 6.0 + 1e-6
            or self.calendar_offset_days != 0
            or self.tutorial_done
            or self.active_trip is not None
            or self.dispatch_board_cache is not None
            or self.money != STARTING_MONEY
            or bool(self.upgrades)
            or self.pay_advance > 0
            or self.career.xp > 0
            or self.career.deliveries > 0
            or self.career.total_miles > 0
            or bool(self.achievements)
        )

    def anchor_calendar_to(self, target_game_hours: float) -> None:
        """Make the independent calendar show target's date without moving time."""
        target_day = int(target_game_hours // 24) % 365
        career_day = int(self.game_hours // 24) % 365
        self.calendar_offset_days = (target_day - career_day) % 365

    # -- persistence -----------------------------------------------------------

    @property
    def path(self) -> Path:
        return save_path_for(self.name)

    def save(self) -> Path:
        path = self.path
        tmp = path.with_suffix(SAVE_SUFFIX + ".tmp")
        with open(tmp, "wb") as f:
            f.write(encode_save_bytes(self.to_dict()))
        os.replace(tmp, path)
        # A converted legacy save keeps one plain-JSON copy as .json.bak so an
        # older game version can be rolled back to; the live file is packed.
        legacy = path.with_suffix(LEGACY_SAVE_SUFFIX)
        if legacy.exists():
            with contextlib.suppress(OSError):
                os.replace(legacy, legacy.with_suffix(".json.bak"))
        if save_listener is not None:
            try:
                save_listener(self)
            except Exception:
                log.debug("Profile save listener failed", exc_info=True)
        return path

    @classmethod
    def load(cls, path: Path) -> Profile:
        try:
            data, packed = _decode_save_bytes(path.read_bytes())
        except ProfileIntegrityError:
            # Unreadable beyond repair: move it aside so the picker's spoken
            # warning stays truthful and the file is not re-tried every visit.
            _quarantine(path)
            raise
        signed = SIGNATURE_FIELD in data
        resign = False
        tampered = False
        if signed and not _is_signature_valid(data):
            if _signing_checks_disabled():
                # Re-save below so the file gets a valid local signature and
                # keeps loading once the dev flag is off again.
                log.warning("Signature check skipped for %s (FREIGHT_FATE_SKIP_SAVE_SIGNING)", path)
                resign = True
            else:
                tampered = True
        elif not signed and packed and not _signing_checks_disabled():
            # The game only ever writes packed saves signed; a packed save
            # with no signature was unpacked, edited, and repacked. Plain
            # unsigned JSON, by contrast, is how every save from before
            # signing looks, so that legacy shape keeps its amnesty (it is
            # re-signed and packed by the resave below).
            tampered = True
        profile = cls.from_dict(data)
        if tampered and not profile.integrity_modified:
            profile.integrity_modified = True
            profile.integrity_notice_pending = True
        if profile.needs_migration_resave or resign or not signed or tampered or not packed:
            profile.save()
        return profile

    @staticmethod
    def list_saves() -> list[Path]:
        found = {p.stem: p for p in profiles_dir().glob(f"*{LEGACY_SAVE_SUFFIX}")}
        # A packed save shadows a leftover legacy twin of the same career.
        found.update({p.stem: p for p in profiles_dir().glob(f"*{SAVE_SUFFIX}")})
        return sorted(found.values(), key=lambda p: p.stat().st_mtime, reverse=True)

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)
        self.path.with_suffix(LEGACY_SAVE_SUFFIX).unlink(missing_ok=True)
