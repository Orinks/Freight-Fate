"""Player profile with atomic JSON save/load.

Profiles live in the per-user data directory (override with the
``FREIGHT_FATE_DATA_DIR`` environment variable, which the tests use).
Saves are atomic: written to a temp file, then renamed over the old save,
so a crash mid-write can never corrupt an existing profile.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .career import Career

SAVE_VERSION = 1
STARTING_MONEY = 5_000.0
DEFAULT_CITY = "Chicago"


def data_dir() -> Path:
    override = os.environ.get("FREIGHT_FATE_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "FreightFate"


def profiles_dir() -> Path:
    d = data_dir() / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Profile:
    name: str = "Driver"
    money: float = STARTING_MONEY
    current_city: str = DEFAULT_CITY
    truck_damage_pct: float = 0.0
    truck_fuel_gal: float = 150.0
    game_hours: float = 6.0          # in-game clock, hours since career start
    tutorial_done: bool = False
    career: Career = field(default_factory=Career)

    # -- serialization -------------------------------------------------------

    def to_dict(self) -> dict:
        d = asdict(self)
        d["version"] = SAVE_VERSION
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Profile:
        d = dict(d)
        d.pop("version", None)
        career = Career(**d.pop("career", {}))
        known = {f for f in cls.__dataclass_fields__ if f != "career"}
        kwargs = {k: v for k, v in d.items() if k in known}
        return cls(career=career, **kwargs)

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
            return cls.from_dict(json.load(f))

    @staticmethod
    def list_saves() -> list[Path]:
        return sorted(profiles_dir().glob("*.json"),
                      key=lambda p: p.stat().st_mtime, reverse=True)

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)
