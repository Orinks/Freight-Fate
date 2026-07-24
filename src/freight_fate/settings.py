"""Persistent game settings (units, volumes, transmission mode, pacing)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass

from .models.profile import data_dir
from .units import spoken_distance

log = logging.getLogger(__name__)

TIME_SCALES = (10.0, 20.0, 40.0)
PROFILE_SHARING_CONSENT_VERSION = 3


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
    # Preserve the historical behavior by default: live weather also follows
    # the wall-clock date. Turn this off to let the career calendar advance
    # while live conditions continue to come from the NWS.
    live_weather_controls_calendar: bool = True
    hos_mode: str = (
        "realistic"  # hours of service: realistic/relaxed (debug_off is an internal dev bypass)
    )
    steering_assist: str = "off"  # off/light/realistic lane drift
    # Lets an armed speed-control session cover low-speed zones without a held
    # accelerator, then hand back to adaptive cruise on open roads. This input
    # accessibility aid remains independent of the wider 1.9 assist framework.
    speed_keeper: bool = True
    master_volume: float = 1.0
    sfx_volume: float = 0.8
    music_volume: float = 0.5
    weather_volume: float = 0.65
    engine_volume: float = 0.55
    ui_volume: float = 0.9
    speech_verbosity: int = 1  # 0 terse, 1 normal
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
    # Post short public summaries of notable deliveries (new badges, level
    # ups, perfect streaks) to the player's own Mastodon account through
    # orinks.net. Off by default, separate from Profile sharing, and inert
    # until a Mastodon account is linked on the site.
    mastodon_sharing: bool = False
    # Last-known link state and handle, refreshed on every status check. Two
    # fields because a link can exist without a handle (the server could not
    # read the account name): linked gates the toggle, the handle is only
    # spoken. The server stays the authority; this cache only keeps the
    # settings menu from needing the network to read a label.
    mastodon_linked: bool = False
    mastodon_linked_handle: str = ""
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

    @classmethod
    def load(cls) -> Settings:
        s = cls()
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
        if s.automatic_direction_changes not in ("simple", "deliberate"):
            s.automatic_direction_changes = "simple"
        # The chatty level (2) was retired; it never diverged from normal
        # beyond a quicker speed-callout timer. Saved chatty falls to normal.
        if s.speech_verbosity not in (0, 1):
            s.speech_verbosity = 1
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
        if not isinstance(s.mastodon_sharing, bool):
            s.mastodon_sharing = False
        if not isinstance(s.mastodon_linked, bool):
            s.mastodon_linked = False
        if not isinstance(s.mastodon_linked_handle, str):
            s.mastodon_linked_handle = ""
        if not isinstance(s.live_weather_controls_calendar, bool):
            s.live_weather_controls_calendar = True
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
            return f"{spoken_distance(mph, 'mile')} per hour"
        return f"{spoken_distance(mph * 1.609344, 'kilometer')} per hour"

    def distance_text(self, miles: float) -> str:
        if self.imperial_units:
            return spoken_distance(miles, "mile")
        return spoken_distance(miles * 1.609344, "kilometer")
