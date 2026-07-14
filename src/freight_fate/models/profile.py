"""Player profile with atomic JSON save/load.

On Windows and Linux, Freight Fate is portable: profiles and settings live
in a ``saves`` directory inside the game's own main directory — next to the
executable in frozen builds, the project root when running from source.

macOS apps live in ``/Applications`` and must not write beside themselves
(that folder is admin-owned and often read-only), so on macOS saves go in the
standard per-user ``~/Library/Application Support/FreightFate`` folder.

Override the location with the ``FREIGHT_FATE_DATA_DIR`` environment variable
(which the tests use). Saves from older versions or misplaced layouts are
migrated into the active location automatically on first run.

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
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..sim.hos import DutyLog, HosClock
from ..updater import is_frozen
from .business import COMPANY_DRIVER, INDEPENDENT_AUTHORITY, is_owner_operator
from .career import Career
from .career_ladder import STARTER_CARRIER_NAME
from .market import Market
from .start_options import DEFAULT_START_KEY, START_MODE_COMPANY

log = logging.getLogger(__name__)

SAVE_VERSION = 10
STARTING_MONEY = 5_000.0
DEFAULT_CITY = "chicago_il_us"
SIGNATURE_FIELD = "_signature"
SIGNATURE_VERSION_FIELD = "_signature_version"
SIGNATURE_VERSION = 1
SECRET_FILE = "profile.key"

# Called with the profile after every successful save. The app points this at
# the cloud backup service so every save site -- deliveries, achievements,
# menu exits, shutdown -- queues a backup without knowing the service exists.
# Best-effort only: a listener failure must never break the local save.
save_listener: Callable[[Profile], None] | None = None

_legacy_checked = False


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


def _save_root() -> Path:
    """The active save directory for this platform.

    Windows and Linux keep the portable ``saves`` folder next to the game.
    macOS uses the per-user Application Support folder so the app never has to
    write into ``/Applications``.
    """
    if sys.platform == "darwin":
        return _macos_data_dir()
    return game_root() / "saves"


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


def _signed_payload(data: dict) -> dict:
    allowed = set(Profile.__dataclass_fields__) | {"version"}
    return {key: data[key] for key in sorted(allowed) if key in data}


def _signature_for(data: dict) -> str:
    payload = json.dumps(
        _signed_payload(data), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hmac.new(_profile_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _is_signature_valid(data: dict) -> bool:
    signature = data.get(SIGNATURE_FIELD)
    if not isinstance(signature, str):
        return False
    return hmac.compare_digest(signature, _signature_for(data))


def _quarantine(path: Path) -> Path:
    target = path.with_suffix(path.suffix + ".invalid")
    n = 1
    while target.exists():
        target = path.with_suffix(path.suffix + f".invalid{n}")
        n += 1
    os.replace(path, target)
    return target


@dataclass
class Profile:
    name: str = "Driver"
    money: float = STARTING_MONEY
    current_city: str = DEFAULT_CITY
    truck_damage_pct: float = 0.0
    tire_wear_pct: float = 0.0
    road_grime_pct: float = 0.0
    truck_fuel_gal: float = 150.0
    game_hours: float = 6.0  # in-game clock, hours since career start
    tutorial_done: bool = False
    truck: str = "rig"  # owner-operator active tractor, or assignment key
    owned_trucks: list[str] = field(default_factory=list)  # owned tractors after buy-in
    upgrades: dict[str, int] = field(default_factory=dict)  # owned-tractor upgrade key -> tier
    active_trip: dict | None = None  # mid-delivery snapshot, see DrivingState
    dispatch_board_cache: dict | None = None
    fatigue: float = 0.0  # 0 fresh .. 100 exhausted
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
    achievements: list[str] = field(default_factory=list)
    achievement_stats: dict = field(default_factory=dict)

    # -- serialization -------------------------------------------------------

    def to_dict(self) -> dict:
        d = asdict(self)
        d["version"] = SAVE_VERSION
        d[SIGNATURE_VERSION_FIELD] = SIGNATURE_VERSION
        d[SIGNATURE_FIELD] = _signature_for(d)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Profile:
        d = dict(d)
        d.pop("version", None)
        d.pop(SIGNATURE_FIELD, None)
        d.pop(SIGNATURE_VERSION_FIELD, None)
        # Nested payloads keep only the fields this build knows: saves written
        # by a newer snapshot (or an older one with since-removed fields) load
        # instead of crashing on an unexpected keyword.
        career = Career(**_known_fields(Career, d.pop("career", {})))
        market = Market(**_known_fields(Market, d.pop("market", {})))
        hos = HosClock.from_dict(d.pop("hos", None))  # absent in v2 saves: fresh clock
        duty_log = DutyLog.from_dict(d.pop("duty_log", None))
        known = {
            f for f in cls.__dataclass_fields__ if f not in ("career", "market", "hos", "duty_log")
        }
        kwargs = {k: v for k, v in d.items() if k in known}
        return cls(career=career, market=market, hos=hos, duty_log=duty_log, **kwargs)

    # -- truck ------------------------------------------------------------------

    def owns_equipment(self) -> bool:
        """True when the profile is responsible for owned tractor equipment."""
        return is_owner_operator(self.business_status)

    def active_truck_key(self) -> str:
        """Truck model currently used for simulation.

        Company drivers operate the carrier-assigned standard tractor. The
        profile still carries ``truck`` for save compatibility and for the
        owner-operator path, but company-driver play should not treat it as
        player-owned equipment.
        """
        return self.truck if self.owns_equipment() else "rig"

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

    def market_day(self) -> int:
        return int(self.game_hours // 24)

    # -- persistence -----------------------------------------------------------

    @property
    def path(self) -> Path:
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in self.name).strip()
        return profiles_dir() / f"{safe or 'Driver'}.json"

    def save(self) -> Path:
        path = self.path
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        os.replace(tmp, path)
        if save_listener is not None:
            try:
                save_listener(self)
            except Exception:
                log.debug("Profile save listener failed", exc_info=True)
        return path

    @classmethod
    def load(cls, path: Path) -> Profile:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ProfileIntegrityError("Save file is not a profile object.")
        signed = SIGNATURE_FIELD in data
        if signed and not _is_signature_valid(data):
            _quarantine(path)
            raise ProfileIntegrityError("Save file failed its integrity check and was quarantined.")
        profile = cls.from_dict(data)
        if not signed:
            profile.save()
        return profile

    @staticmethod
    def list_saves() -> list[Path]:
        return sorted(profiles_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)
