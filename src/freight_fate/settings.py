"""Persistent game settings (units, volumes, transmission mode, pacing)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass

from .models.profile import data_dir

log = logging.getLogger(__name__)

TIME_SCALES = (10.0, 20.0, 40.0)


@dataclass
class Settings:
    imperial_units: bool = True
    automatic_transmission: bool = True   # friendlier default for new players
    time_scale: float = 20.0              # distance compression while driving
    real_weather: bool = False            # live conditions from Open-Meteo
    hos_mode: str = "realistic"           # hours of service: realistic/relaxed/off
    master_volume: float = 1.0
    sfx_volume: float = 0.8
    music_volume: float = 0.55
    speech_verbosity: int = 1             # 0 terse, 1 normal, 2 chatty

    @property
    def path(self):
        return data_dir() / "settings.json"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
        tmp.replace(self.path)

    @classmethod
    def load(cls) -> Settings:
        s = cls()
        try:
            with open(s.path, encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError):
            log.warning("Could not read settings; using defaults", exc_info=True)
        from .sim.hos import HOS_MODES

        if s.hos_mode not in HOS_MODES:
            s.hos_mode = "realistic"
        return s

    def speed_text(self, mph: float) -> str:
        if self.imperial_units:
            return f"{mph:.0f} miles per hour"
        return f"{mph * 1.609344:.0f} kilometers per hour"

    def distance_text(self, miles: float) -> str:
        if self.imperial_units:
            return f"{miles:.0f} miles"
        return f"{miles * 1.609344:.0f} kilometers"
