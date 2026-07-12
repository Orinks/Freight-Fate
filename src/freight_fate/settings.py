"""Persistent game settings (units, volumes, transmission mode, pacing)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass

from .models.profile import data_dir

log = logging.getLogger(__name__)

TIME_SCALES = (10.0, 20.0, 40.0)

DRIVING_ASSIST_FIELDS = (
    "automatic_emergency_braking",
    "lane_departure_warning",
    "stop_and_go_assist",
    "lane_centering_assist",
    "descent_speed_control",
)

DRIVING_ASSIST_PRESETS = {
    "realistic": (True, True, True, False, "realistic"),
    "balanced": (True, True, True, True, "balanced"),
    "all": (True, True, True, True, "interactive"),
}


@dataclass
class Settings:
    imperial_units: bool = True
    automatic_transmission: bool = True  # friendlier default for new players
    # Simple keeps the familiar hold-through-stop behavior. Deliberate requires
    # a release and second press before an automatic changes direction.
    automatic_direction_changes: str = "simple"  # simple/deliberate
    # Distance compression while driving. Relaxed (10x) by default: new players
    # get the most real time to hear and react to spoken events; veterans can
    # step up to standard or fast in Settings, Gameplay.
    time_scale: float = 10.0
    real_weather: bool = False  # live conditions from the NWS API
    hos_mode: str = (
        "realistic"  # hours of service: realistic/relaxed (debug_off is an internal dev bypass)
    )
    steering_assist: str = "off"  # off/light/realistic lane drift
    driving_assistance_preset: str = "realistic"
    automatic_emergency_braking: bool = True
    lane_departure_warning: bool = True
    stop_and_go_assist: bool = True
    lane_centering_assist: bool = False
    descent_speed_control: str = "realistic"
    master_volume: float = 1.0
    sfx_volume: float = 0.8
    music_volume: float = 0.5
    weather_volume: float = 0.65
    engine_volume: float = 0.55
    ui_volume: float = 0.9
    speech_verbosity: int = 1  # 0 terse, 1 normal, 2 chatty
    announce_menu_position: bool = True  # speak "N of M" position in menus
    sapi_events: bool = True  # driving events on a separate voice
    event_backend: str = "SAPI"  # which voice that is (e.g. SAPI/OneCore)
    speech_rate: float = 0.5  # voice speed, 0..1 (backend default ~0.5)
    speech_pitch: float = 0.5  # voice pitch, 0..1 (backend default ~0.5)
    speech_volume: float = 1.0  # voice loudness, 0..1
    speech_voice: str = ""  # installed voice name; "" = backend default
    update_channel: str = ""  # "stable"/"dev"; "" follows this build's channel
    skipped_update: str = ""  # release tag the player chose to skip
    discord_presence: bool = True  # show broad activity in Discord (privacy-safe)
    # Share on-duty status on the public orinks.net drivers board. On by
    # default like Discord presence, but inert until the player completes the
    # browser setup: nothing is ever sent without a confirmed driver identity
    # (see online_presence.py), and board listing further requires choosing
    # the public visibility on the site.
    online_presence: bool = True
    # Back up saves to the player's own Orinks account after each local save.
    # Off by default and separate from drivers-board sharing: that feature's
    # spoken disclosure promises save files are never sent, so mirroring them
    # to the cloud needs its own explicit yes -- even though it reuses the
    # same account credentials and never shows saves to anyone else.
    cloud_saves: bool = False
    controller_enabled: bool = True  # accept game-controller input alongside the keyboard
    haptics_enabled: bool = True  # rumble/vibration feedback on the controller

    @property
    def path(self):
        return data_dir() / "settings.json"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
        tmp.replace(self.path)

    def apply_driving_assistance_preset(self, preset: str) -> None:
        values = DRIVING_ASSIST_PRESETS[preset]
        for field, value in zip(DRIVING_ASSIST_FIELDS, values, strict=True):
            setattr(self, field, value)
        self.driving_assistance_preset = preset
        self._sync_legacy_lane_setting()

    def refresh_driving_assistance_preset(self) -> str:
        values = tuple(getattr(self, field) for field in DRIVING_ASSIST_FIELDS)
        matches = [name for name, mapping in DRIVING_ASSIST_PRESETS.items() if mapping == values]
        self.driving_assistance_preset = matches[0] if len(matches) == 1 else "custom"
        self._sync_legacy_lane_setting()
        return self.driving_assistance_preset

    def _sync_legacy_lane_setting(self) -> None:
        if self.lane_centering_assist:
            self.steering_assist = "light"
        elif self.lane_departure_warning:
            self.steering_assist = "realistic"
        else:
            self.steering_assist = "off"

    @classmethod
    def load(cls) -> Settings:
        s = cls()
        data = None
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

        # Legacy 1.5.0 saves carried a player-selectable "off" mode. It is no
        # longer offered, so such saves fall through to the realistic default
        # below. debug_off stays valid as an internal dev/test bypass only.
        if s.hos_mode not in HOS_MODES:
            s.hos_mode = "realistic"
        if s.steering_assist not in ("off", "light", "realistic"):
            s.steering_assist = "off"
            s.lane_departure_warning = False
            s.lane_centering_assist = False
        if data is not None and "driving_assistance_preset" not in data:
            s.lane_departure_warning = s.steering_assist != "off"
            s.lane_centering_assist = s.steering_assist == "light"
            s.automatic_emergency_braking = False
            s.stop_and_go_assist = False
            s.descent_speed_control = "off"
            s.driving_assistance_preset = "custom"
        for field in DRIVING_ASSIST_FIELDS[:-1]:
            if not isinstance(getattr(s, field), bool):
                setattr(s, field, getattr(cls(), field))
        if s.descent_speed_control not in ("off", "realistic", "balanced", "interactive"):
            s.descent_speed_control = "realistic"
        if s.driving_assistance_preset not in (*DRIVING_ASSIST_PRESETS, "custom"):
            s.driving_assistance_preset = "custom"
        if data is None or "driving_assistance_preset" in data:
            s.refresh_driving_assistance_preset()
        if s.automatic_direction_changes not in ("simple", "deliberate"):
            s.automatic_direction_changes = "simple"
        if s.update_channel not in ("", "stable", "dev"):
            s.update_channel = ""
        if not isinstance(s.event_backend, str) or not s.event_backend:
            s.event_backend = "SAPI"
        if not isinstance(s.controller_enabled, bool):
            s.controller_enabled = True
        if not isinstance(s.haptics_enabled, bool):
            s.haptics_enabled = True
        if not isinstance(s.cloud_saves, bool):
            s.cloud_saves = False
        for attr in (
            "master_volume",
            "sfx_volume",
            "music_volume",
            "weather_volume",
            "engine_volume",
            "ui_volume",
            "speech_rate",
            "speech_pitch",
            "speech_volume",
        ):
            setattr(s, attr, max(0.0, min(1.0, float(getattr(s, attr)))))
        return s

    def speed_text(self, mph: float) -> str:
        if self.imperial_units:
            return f"{mph:.0f} miles per hour"
        return f"{mph * 1.609344:.0f} kilometers per hour"

    def distance_text(self, miles: float) -> str:
        if self.imperial_units:
            return f"{miles:.0f} miles"
        return f"{miles * 1.609344:.0f} kilometers"
