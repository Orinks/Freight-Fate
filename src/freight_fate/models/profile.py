"""Player profile with atomic JSON save/load.

Freight Fate is portable: profiles and settings live in a ``saves``
directory inside the game's own main directory — next to the executable
in frozen builds, the project root when running from source. Nothing is
written to per-user system folders. Override the location with the
``FREIGHT_FATE_DATA_DIR`` environment variable (which the tests use).
Saves from older versions, which lived in the per-user data directory,
are migrated over automatically on first run.

Saves are atomic: written to a temp file, then renamed over the old save,
so a crash mid-write can never corrupt an existing profile.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import secrets
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..sim.hos import HosClock
from .career import Career
from .market import Market

SAVE_VERSION = 4
STARTING_MONEY = 5_000.0
DEFAULT_CITY = "Chicago"
SIGNATURE_FIELD = "_signature"
SIGNATURE_VERSION_FIELD = "_signature_version"
SIGNATURE_VERSION = 1
SECRET_FILE = "profile.key"

_legacy_checked = False


def _legacy_data_dir() -> Path:
    """Where saves lived before the portable layout (per-user folders)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "FreightFate"


def game_root() -> Path:
    """The game's main directory: the executable's directory when frozen,
    the project root when running from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def _migrate_legacy(target: Path) -> None:
    """One-time copy of an old per-user save folder into the portable one."""
    if target.exists():
        return
    for source in _portable_migration_candidates():
        if source.is_dir():
            _copy_save_tree(source, target)
            return
    legacy = _legacy_data_dir()
    if legacy.is_dir():
        _copy_save_tree(legacy, target)


def _copy_save_tree(source: Path, target: Path) -> None:
    """Copy a save tree without blocking startup if the filesystem objects."""
    # never block startup on a migration; old saves stay where they are
    with contextlib.suppress(OSError):
        shutil.copytree(source, target)


def _portable_migration_candidates() -> list[Path]:
    """Nearby portable save roots from previous archive nesting layouts."""
    root = game_root()
    parent = root.parent
    candidates = [
        root / "FreightFate" / "saves",
        parent / "saves",
        parent / "FreightFate" / "saves",
    ]
    return [path for path in candidates if path != root / "saves"]


def data_dir() -> Path:
    override = os.environ.get("FREIGHT_FATE_DATA_DIR")
    if override:
        return Path(override)
    global _legacy_checked
    portable = game_root() / "saves"
    if not _legacy_checked:
        _legacy_checked = True
        _migrate_legacy(portable)
    return portable


def profiles_dir() -> Path:
    d = data_dir() / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


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
    payload = json.dumps(_signed_payload(data), sort_keys=True,
                         separators=(",", ":"), ensure_ascii=True)
    return hmac.new(_profile_secret(), payload.encode("utf-8"),
                    hashlib.sha256).hexdigest()


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
    truck_fuel_gal: float = 150.0
    game_hours: float = 6.0          # in-game clock, hours since career start
    tutorial_done: bool = False
    truck: str = "rig"               # key into trucks.TRUCK_CATALOG
    owned_trucks: list[str] = field(default_factory=lambda: ["rig"])
    upgrades: dict[str, int] = field(default_factory=dict)  # upgrade key -> tier
    active_trip: dict | None = None  # mid-delivery snapshot, see DrivingState
    dispatch_board_cache: dict | None = None
    fatigue: float = 0.0             # 0 fresh .. 100 exhausted
    career: Career = field(default_factory=Career)
    market: Market = field(default_factory=Market)
    hos: HosClock = field(default_factory=HosClock)  # hours-of-service shift clock
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
        career = Career(**d.pop("career", {}))
        market = Market(**d.pop("market", {}))
        hos = HosClock.from_dict(d.pop("hos", None))  # absent in v2 saves: fresh clock
        known = {f for f in cls.__dataclass_fields__ if f not in ("career", "market", "hos")}
        kwargs = {k: v for k, v in d.items() if k in known}
        return cls(career=career, market=market, hos=hos, **kwargs)

    # -- truck ------------------------------------------------------------------

    def truck_specs(self):
        """The active truck's specs with this profile's upgrades applied."""
        from .trucks import build_truck_specs

        return build_truck_specs(self.truck, self.upgrades)

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
            raise ProfileIntegrityError(
                "Save file failed its integrity check and was quarantined.")
        profile = cls.from_dict(data)
        if not signed:
            profile.save()
        return profile

    @staticmethod
    def list_saves() -> list[Path]:
        return sorted(profiles_dir().glob("*.json"),
                      key=lambda p: p.stat().st_mtime, reverse=True)

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)
