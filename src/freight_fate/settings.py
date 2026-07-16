"""Persistent game settings (units, volumes, transmission mode, pacing)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass

from .models.profile import data_dir

log = logging.getLogger(__name__)

TIME_SCALES = (10.0, 20.0, 40.0)
PROFILE_SHARING_CONSENT_VERSION = 3

# Which chatter switch governs each roadside-callout category. Zone entries
# (parks, forests, wilderness) share one switch; the lone highway heritage
# marker rides with the scenic passes.
CHATTER_CATEGORY_FIELDS = {
    "national_park": "chatter_parks",
    "national_forest": "chatter_parks",
    "wilderness": "chatter_parks",
    "protected_area": "chatter_parks",
    "river": "chatter_rivers",
    "mountain_pass": "chatter_passes",
    "highway_marker": "chatter_passes",
    "museum": "chatter_museums",
    "billboard": "chatter_billboards",
    # Placed roadside billboards baked as leg landmarks (billboard spider); ride
    # the same switch as the random-pool billboards so one toggle governs both.
    "billboard_sign": "chatter_billboards",
}

# The player-facing chatter switches, in menu order.
CHATTER_FIELDS = (
    "chatter_parks",
    "chatter_rivers",
    "chatter_passes",
    "chatter_museums",
    "chatter_billboards",
)

DRIVING_ASSIST_FIELDS = (
    "automatic_emergency_braking",
    "lane_departure_warning",
    "stop_and_go_assist",
    "lane_centering_assist",
    "descent_speed_control",
    "exit_speed_assist",
    "destination_approach_assist",
    "curve_speed_assist",
    "route_transition_assist",
)

DRIVING_ASSIST_PRESETS = {
    "realistic": (True, True, True, False, "realistic", True, False, True, True),
    "balanced": (True, True, True, True, "balanced", True, True, True, True),
    "all": (True, True, True, True, "interactive", True, True, True, True),
}


@dataclass
class Settings:
    imperial_units: bool = True
    automatic_transmission: bool = True  # friendlier default for new players
    # Simple keeps the familiar hold-through-stop behavior. Deliberate requires
    # a release and second press before an automatic changes direction.
    automatic_direction_changes: str = "simple"  # simple/deliberate
    # Dash chime plus a spoken heads-up while over the posted limit, like a
    # carrier-set overspeed alert; on by default, a company truck would have
    # it. "urgent only" keeps just the runaway alarm for deliberate speeders.
    overspeed_warning: str = "on"  # on / urgent only / off
    # Distance compression while driving. Relaxed (10x) by default: new players
    # get the most real time to hear and react to spoken events; veterans can
    # step up to standard or realistic in Settings, Gameplay.
    time_scale: float = 10.0
    real_weather: bool = False  # live conditions from the NWS API
    hos_mode: str = (
        "realistic"  # hours of service: realistic/relaxed (debug_off is an internal dev bypass)
    )
    # Whether the lane-position task runs at all. A simulation choice like
    # the speed keeper, not a safety assist: presets never change it, and the
    # 1.9 exit mechanics only demand signals and lane discipline when it is on.
    steering_assist: str = "off"  # off/light/realistic lane drift
    driving_assistance_preset: str = "realistic"
    automatic_emergency_braking: bool = True
    lane_departure_warning: bool = True
    stop_and_go_assist: bool = True
    lane_centering_assist: bool = False
    descent_speed_control: str = "realistic"
    exit_speed_assist: bool = True
    destination_approach_assist: bool = False
    curve_speed_assist: bool = True
    route_transition_assist: bool = True
    # Holds a gentle speed through low-speed zones where adaptive cruise is
    # unavailable, so nobody has to keep the accelerator key held down. An
    # input-accessibility aid, not a realism choice: presets never touch it.
    speed_keeper: bool = True
    # Double-tap-and-hold latches the accelerator or brake key so a long
    # pull or a steady snub needs no sustained hold; a fresh press of the
    # same key, the opposite pedal, or any safety override releases it.
    # The same input-accessibility layer as the keeper: presets never
    # touch it. Realism cover: the hand-throttle knob is a real cab control.
    pedal_latch: bool = True
    master_volume: float = 1.0
    sfx_volume: float = 0.8
    music_volume: float = 0.5
    radio_volume: float = 0.25
    radio_enabled: bool = True
    radio_station_id: str = "route_playlist"
    radio_streamer_safe: bool = True
    radio_real_streams: bool = False
    weather_volume: float = 0.65
    engine_volume: float = 0.55
    ui_volume: float = 0.9
    speech_verbosity: int = 1  # 0 terse, 1 normal, 2 chatty
    # Roadside chatter: the ambient color spoken between navigation cues.
    # Each category has its own switch so a player can keep the geography
    # (rivers, passes) while silencing the jokes (billboards), or vice versa.
    # Safety and navigation speech is never affected by these.
    chatter_parks: bool = True  # entering parks, forests, and wild lands
    chatter_rivers: bool = True  # named river crossings
    chatter_passes: bool = True  # mountain passes and scenic highway markers
    chatter_museums: bool = True  # museums and roadside attractions
    chatter_billboards: bool = True  # parody billboards
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
    online_presence: bool = False
    profile_sharing_consent_version: int = 0
    # A failed server revocation keeps public state uncertain, but stops all
    # local publication immediately and retries when the player activates the
    # stable Profile sharing item again.
    profile_sharing_pending_off: bool = False
    # Back up saves to the player's own Orinks account after each local save.
    # Off by default and separate from public Profile sharing. It needs its
    # own explicit yes even though it reuses the same account credentials.
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

    def refresh_driving_assistance_preset(self) -> str:
        values = tuple(getattr(self, field) for field in DRIVING_ASSIST_FIELDS)
        matches = [name for name, mapping in DRIVING_ASSIST_PRESETS.items() if mapping == values]
        self.driving_assistance_preset = matches[0] if len(matches) == 1 else "custom"
        return self.driving_assistance_preset

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
            # The former board-only opt-in covered less information. Never
            # silently expand it into public Profile sharing.
            if data.get("profile_sharing_consent_version") != PROFILE_SHARING_CONSENT_VERSION:
                s.online_presence = False
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
            for field in DRIVING_ASSIST_FIELDS:
                if field == "descent_speed_control":
                    setattr(s, field, "off")
                elif field not in ("lane_departure_warning", "lane_centering_assist"):
                    setattr(s, field, False)
            s.driving_assistance_preset = "custom"
        for field in DRIVING_ASSIST_FIELDS:
            if field == "descent_speed_control":
                continue
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
        # The overspeed alert briefly shipped as a bool; map old saves over.
        if s.overspeed_warning is True:
            s.overspeed_warning = "on"
        elif s.overspeed_warning is False:
            s.overspeed_warning = "off"
        if s.overspeed_warning not in ("on", "urgent only", "off"):
            s.overspeed_warning = "on"
        if s.update_channel not in ("", "stable", "dev"):
            s.update_channel = ""
        if not isinstance(s.event_backend, str) or not s.event_backend:
            s.event_backend = "SAPI"
        if not isinstance(s.controller_enabled, bool):
            s.controller_enabled = True
        if not isinstance(s.haptics_enabled, bool):
            s.haptics_enabled = True
        for attr in CHATTER_FIELDS:
            if not isinstance(getattr(s, attr), bool):
                setattr(s, attr, True)
        if not isinstance(s.cloud_saves, bool):
            s.cloud_saves = False
        for attr in (
            "master_volume",
            "sfx_volume",
            "music_volume",
            "radio_volume",
            "weather_volume",
            "engine_volume",
            "ui_volume",
            "speech_rate",
            "speech_pitch",
            "speech_volume",
        ):
            setattr(s, attr, max(0.0, min(1.0, float(getattr(s, attr)))))
        if not isinstance(s.radio_station_id, str) or not s.radio_station_id:
            s.radio_station_id = "route_playlist"
        return s

    def chatter_enabled(self, category: str) -> bool:
        """Whether a roadside-callout category is currently spoken.

        Unknown categories default to on so a future bake category speaks
        rather than silently vanishing."""
        field = CHATTER_CATEGORY_FIELDS.get(category)
        return True if field is None else bool(getattr(self, field))

    def chatter_summary(self) -> str:
        """The master menu label state: everything, off, or custom."""
        states = [bool(getattr(self, field)) for field in CHATTER_FIELDS]
        if all(states):
            return "everything"
        if not any(states):
            return "off"
        return "custom"

    def set_all_chatter(self, enabled: bool) -> None:
        for field in CHATTER_FIELDS:
            setattr(self, field, enabled)

    def speed_text(self, mph: float) -> str:
        if self.imperial_units:
            return f"{mph:.0f} miles per hour"
        return f"{mph * 1.609344:.0f} kilometers per hour"

    def distance_text(self, miles: float) -> str:
        if self.imperial_units:
            return f"{miles:.0f} miles"
        return f"{miles * 1.609344:.0f} kilometers"
