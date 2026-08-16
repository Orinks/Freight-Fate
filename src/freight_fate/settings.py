"""Persistent game settings (units, volumes, transmission mode, pacing)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import ClassVar

from .models.profile import data_dir
from .speech_pacing import (
    DEFAULT_DRIVING_SPEECH,
    DRIVING_SPEECH_MODES,
    Disposition,
    SpeechCategory,
    disposition_for,
)
from .units import (
    MILES_TO_KM,
    distance_unit,
    hud_speed,
    spoken_distance,
    spoken_gap,
    to_distance,
)

log = logging.getLogger(__name__)

TIME_SCALES = (10.0, 20.0, 40.0)
PROFILE_SHARING_CONSENT_VERSION = 3

# Bumped when the settings *menu* is reorganized enough that a returning
# player needs telling where things moved -- it tracks the shape of the menus,
# not any one field. A load that finds an older value on disk (or none)
# records which version it came from, and every notice newer than that is
# spoken once; a fresh install writes the current version and hears nothing.
#
# 1: the Gameplay category (Driving assistance, Difficulty and hours of
#    service, World and traffic, Controls), and the world-data rows leaving
#    Speech and weather.
# 2: the speed keeper moving to Driving assistance, and the lane and edge cue
#    volume moving to Audio.
# 3: speech_verbosity (0 terse / 1 normal) became the driving_speech ladder.
SETTINGS_VERSION = 3

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
    # "village" is deliberately absent: town and village names are not
    # chatter. They are governed by the place_callouts ladder instead,
    # because the name that explains a speed limit drop must survive a
    # player turning the ambient colour off.
}

# The player-facing chatter switches, in menu order.
CHATTER_FIELDS = (
    "chatter_parks",
    "chatter_rivers",
    "chatter_passes",
    "chatter_museums",
    "chatter_billboards",
)

# How much the ride-along says about the places along the road, whatever
# place data the world carries (curated route towns on one line, the baked
# village layer on another -- the player never needs to know which).
PLACE_CALLOUT_MODES = ("off", "sparse", "all")

# How much of the lane-holding work the truck does for the driver. The
# setting used to be called ``steering_assist`` and its values read exactly
# backwards: "off" meant the truck held the lane FOR you and took your exits,
# while "realistic" was the manual task -- and "off" was the default. A player
# who believed they had turned assistance off was in the most assisted mode
# there is, and their exits took themselves. The values now name what the
# truck does.
LANE_KEEPING_MODES = ("full", "partial", "off")

# The one value every fallback lands on: the loader's, the menu label's, and
# the spoken notice's. They agreed only by coincidence before, which is how a
# label and a behaviour can quietly come apart. "full" is right because
# landing on "off" instead would start drift, rumble strips, and off-road
# damage AND stop granting the destination exit -- a difficulty spike with no
# audible cause. It is safe as a default and unsafe as a *silent* one, so an
# unreadable value is spoken about once (see ``lane_keeping_unreadable``).
LANE_KEEPING_FALLBACK = "full"

# Spoken value labels. The bare value word must never appear alone: "off"
# here means the hardest mode, while "off" in overspeed warning, the speed
# keeper, and descent control all mean less help. The clause is what keeps a
# listener from carrying the wrong sense across rows, and "full" has to
# disambiguate itself from "full manual" in the same breath.
LANE_KEEPING_LABELS = {
    "full": "full, the truck holds the lane and takes your exits",
    "partial": "partial, gentle drift and you steer with help",
    "off": "off, you hold the lane and take your own exits",
}

# Every legacy value maps to the mode that behaves identically, so the rename
# moves nobody's difficulty. Anything else -- a corrupt file, a value from a
# build that is not this one -- lands on the fallback above: silently handing
# a blind player a manual steering task they never opted into is by far the
# worse failure.
LANE_KEEPING_FROM_LEGACY = {"off": "full", "light": "partial", "realistic": "off"}
LANE_KEEPING_TO_LEGACY = {"full": "off", "partial": "light", "off": "realistic"}

# How many times the row explains its own rename before it stops. A note
# queued behind a row announcement is cut off when the player keeps arrowing,
# so one shot is not enough for something this consequential; three makes a
# lost announcement self-correcting.
LANE_KEEPING_RENAME_NOTICES = 3

# How loud the policed country is. Presence is not difficulty: see the
# ``enforcement_presence`` field for why these two must never move together.
ENFORCEMENT_PRESENCE_LEVELS = ("full", "standard", "quiet")
# Multiplier on the ambient enforcement layer -- the marked-unit passes for
# posts nobody is sitting in, the scale approach beds, and the CB colour. It
# never reaches placement, staffing, observation or consequence.
ENFORCEMENT_AMBIENCE_SCALE = {"full": 1.35, "standard": 1.0, "quiet": 0.45}

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
    # Lane keeping is a preset field like the rest. It used to sit outside
    # them, which is how the preset row came to read "Realistic" over fully
    # automated lane keeping -- the one row a player checks to learn how much
    # the truck is doing could not see the biggest thing it was doing.
    "lane_keeping",
)

DRIVING_ASSIST_PRESETS = {
    "realistic": (True, True, True, False, "realistic", True, False, True, True, "off"),
    "balanced": (True, True, True, True, "balanced", True, True, True, True, "partial"),
    "all": (True, True, True, True, "interactive", True, True, True, True, "full"),
}


@dataclass
class Settings:
    # Master switch for the orinks.net and sharing services: the drivers
    # board, ``online_presence``, ``cloud_saves``, Mastodon sharing, and
    # Discord presence behave as disabled while it is off, without losing
    # their individual settings. Live-data simulation sources
    # (``real_weather``, ``real_traffic``, ``real_parking``) are
    # deliberately NOT gated here -- they follow their own Settings toggles
    # (owner ruling, 2026-08-08: two testers lost real weather to this
    # switch with no explanation at the weather toggle).
    online_services: bool = True
    imperial_units: bool = True
    # The engine voice: "real" plays the multisample recorded-cab ring
    # (release builds carry the licensed cuts); "classic" keeps the original
    # single pitched loop for players who prefer the familiar sound.
    engine_voice: str = "real"  # real / classic
    # The jake brake voice: "real" plays the recorded 1600 jake (the engine
    # brake growl players hear today); "classic" swaps in the synthesized
    # growl the game shipped before it, kept as the future jake A/B.
    jake_voice: str = "real"  # real / classic
    automatic_transmission: bool = True  # friendlier default for new players
    # Simple keeps the familiar hold-through-stop behavior. Deliberate requires
    # a release and second press before an automatic changes direction.
    automatic_direction_changes: str = "simple"  # simple/deliberate
    # Distance compression while driving. Relaxed (10x) by default: new players
    # get the most real time to hear and react to spoken events; veterans can
    # step up to standard or realistic in Settings, Gameplay.
    time_scale: float = 10.0
    real_weather: bool = False  # live conditions from the NWS API
    real_traffic: bool = False  # live traffic incidents from state 511 APIs
    real_parking: bool = False  # live truck parking availability from TPIMS APIs
    # Preserve the historical behavior by default: live weather also follows
    # the wall-clock date. Turn this off to let the career calendar advance
    # while live conditions continue to come from the NWS.
    live_weather_controls_calendar: bool = True
    hos_mode: str = (
        "realistic"  # hours of service: realistic/relaxed (debug_off is an internal dev bypass)
    )
    # How much of the lane-holding work the truck does. "full" keeps the
    # truck centred, takes your exits for you, and turns Left and Right into
    # tap lane changes. "partial" drifts gently and gives you generous
    # steering authority, but the lane work is yours. "off" is the whole
    # manual task: you hold the lane, and every exit needs its signal and
    # its exit lane. It is one of the preset fields, so the preset row can
    # never again read "Realistic" over fully automated lane keeping.
    #
    # The default is the realistic preset's value, so a fresh install really
    # is the ruleset the preset row has been claiming all along: for months
    # the row read "Realistic" while lane keeping was fully automated,
    # because the preset could not see this field. Owner ruling 2026-08-09 --
    # make the truck match the label players have been reading rather than
    # renaming the label to match a setting nobody chose. Existing players
    # are untouched: their saved value migrates to whatever they already had.
    lane_keeping: str = "off"
    # How many more times the Lane keeping row explains that it used to be
    # called Lane drift. Zero by default: a fresh install has nothing to
    # explain, and only a load that actually found the old key on disk raises
    # it. A setting rather than a profile field on purpose -- the rename is
    # global, so a per-career counter would re-fire on every career and fire
    # for careers created after the update, who never saw the old name.
    lane_keeping_rename_notice_left: int = 0
    # Set by ``load`` when the lane-keeping value on disk could not be read at
    # all and the fallback was taken blind. Deliberately not a saved field: it
    # describes one load, and the truck must say so once rather than leave a
    # player wondering why their exits are suddenly being taken.
    lane_keeping_unreadable: ClassVar[bool] = False
    # How much police activity the road makes audible. AMBIENCE ONLY. It never
    # changes where the enforcement posts are, whether one is staffed, or how
    # likely you are to be observed and pulled over -- if one slider moved
    # both, turning the noise down would quietly make the game easier while
    # the player believed they had only turned down noise. The on-demand
    # road-ahead readout reports enforcement at full detail at every level, so
    # what a quiet road costs you is atmosphere, never information you can ask
    # for. A quiet setting still hears every staffed post it passes: a post
    # the player was given no cue for is not allowed to cost them anything.
    enforcement_presence: str = "standard"  # full / standard / quiet
    # How loud the lane and edge cues speak: the edge-boundary textures,
    # the lane locator, and the dead-man's-curve strips all scale by it.
    lane_cue_loudness: str = "standard"  # subtle/standard/prominent
    # The shipped defaults now match the realistic preset field for field --
    # lane keeping was the only one that did not, and it is the default the
    # row has been claiming since before it could see that field.
    driving_assistance_preset: str = "realistic"
    automatic_emergency_braking: bool = True
    lane_departure_warning: bool = True
    stop_and_go_assist: bool = True
    lane_centering_assist: bool = False
    descent_speed_control: str = "realistic"
    exit_speed_assist: bool = True
    destination_approach_assist: bool = False
    # An explicit-plan accessibility aid, separate from the realism presets:
    # T plans a sleep stop, X signals for it, and only then may this bring the
    # truck to a complete stop at the entrance. Presets never turn it on.
    selected_stop_assist: bool = False
    curve_speed_assist: bool = True
    route_transition_assist: bool = True
    # Lets an armed speed-control session cover low-speed zones without a held
    # accelerator, then hand back to adaptive cruise on open roads. This input
    # accessibility aid stays independent of the assistance preset above:
    # presets never touch it.
    speed_keeper: bool = True
    # Cruise reads the baked grade profile a mile and a half ahead and plans
    # against it: banks a little momentum before a climb, gives up the last
    # few mph at a crest instead of fighting for them, and stops adding speed
    # it is about to brake away before a descent. Every modern truck ships
    # this as part of its cruise, not as a driver-assistance level, so it sits
    # outside the assistance presets the way the speed keeper does.
    predictive_cruise: bool = True
    # Double-tap-and-hold latches the accelerator or brake key so a long
    # pull or a steady snub needs no sustained hold; a fresh press of the
    # same key, the opposite pedal, or any safety override releases it.
    # The same input-accessibility layer as the keeper: presets never
    # touch it. Realism cover: the hand-throttle knob is a real cab control.
    # Modes (owner revision 2026-08-13): "assists first" lets cruise, the
    # speed keeper, and curve assist outrank a latched throttle; "latch
    # first" is the original meaning, the latch as a manual override the
    # assists stand down for; "off" is the plain pedals.
    pedal_latch: str = "assists first"  # assists first / latch first / off
    # The co-driver reads the road: spoken curve calls from the baked
    # geometry ("Sharp left, quarter mile, advise 35"), only for bends
    # that actually demand slowing at your current speed. The first
    # audible slice of the steering-by-ear work.
    curve_callouts: bool = True
    master_volume: float = 1.0
    sfx_volume: float = 0.8
    music_volume: float = 0.5
    radio_volume: float = 0.25
    radio_enabled: bool = True
    radio_station_id: str = "route_playlist"
    # The one radio licensing gate: on hides real public streams and
    # personal playlists so nothing licensed reaches a broadcast. Off by
    # default -- the full dial is the out-of-the-box experience, and safe
    # mode is the explicit choice a streamer makes. (The former separate
    # real-streams opt-in folded into this switch, 2026-08-12.)
    radio_streamer_safe: bool = False
    weather_volume: float = 0.65
    engine_volume: float = 0.55
    ui_volume: float = 0.9
    # Step the game sounds back while the road voice speaks: engine, weather,
    # and the radio drop to half volume for the length of the line, then come
    # back (XAG 105; speech priority research, R13). Off by default: in an
    # audio-first sim the engine is the instrument panel -- a blind driver
    # reads speed off it -- so ducking is opt-in for players who need it,
    # not a default that changes what everyone hears (owner, 2026-08-12).
    duck_audio_for_speech: bool = False
    # How much of the road's INFORMATION speaks: a ladder of named rungs
    # that cut whole categories, not one global compression. Flavor is not
    # governed here -- billboards, places and landmarks answer to the
    # chatter switches and the place-callouts ladder (owner, 2026-08-15).
    driving_speech: str = DEFAULT_DRIVING_SPEECH
    # Roadside chatter: the ambient color spoken between navigation cues.
    # Each category has its own switch so a player can keep the geography
    # (rivers, passes) while silencing the jokes (billboards), or vice versa.
    # Safety and navigation speech is never affected by these.
    chatter_parks: bool = True  # entering parks, forests, and wild lands
    chatter_rivers: bool = True  # named river crossings
    chatter_passes: bool = True  # mountain passes and scenic highway markers
    chatter_museums: bool = True  # museums and roadside attractions
    chatter_billboards: bool = True  # parody billboards
    # Place names along the road. "sparse" speaks only the names that explain
    # a speed limit change ("Entering Strawberry" right before the 35);
    # "all" adds the towns the route passes; "off" silences place names
    # entirely. The full baked place layer is never read aloud at any tier --
    # it exists to answer on-demand orientation questions.
    place_callouts: str = "sparse"
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
    # Share the public driver profile and on-duty board status on orinks.net.
    # Off here because a player with no account has nothing to share: without
    # a confirmed driver identity nothing is ever sent (see
    # online_presence.py). Connecting an account turns this on, since a
    # connected account that publishes nothing leaves a profile reading "no
    # career statistics yet". orinks.net stays the authority: this only flips
    # true once the server confirms, and board listing further requires
    # choosing the public visibility on the site.
    online_presence: bool = False
    profile_sharing_consent_version: int = 0
    # A failed server revocation keeps public state uncertain, but stops all
    # local publication immediately and retries when the player activates the
    # stable Profile sharing item again.
    profile_sharing_pending_off: bool = False
    # Back up saves to the player's own Orinks account after each local save.
    # Off here for the same reason as ``online_presence``: no account, nothing
    # to upload. Connecting an account turns this on -- the public career
    # statistics are derived from the latest accepted backup, so the two only
    # make sense together -- and the Online menu turns it off again on its own.
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
    # Whether the one-time first-run offer to connect this computer to
    # orinks.net has been made. Per install, not per career: the connection
    # belongs to the computer, so a second career must not ask again. Set on
    # either answer, so declining is respected and the prompt cannot reappear
    # after a mid-prompt quit.
    online_offer_seen: bool = False
    # The settings-menu layout version this file was last written by. See
    # SETTINGS_VERSION, which lists what each one changed: an older value on
    # load means every layout above it is new to this player, so the Gameplay
    # submenu explains once where their settings moved.
    settings_version: int = SETTINGS_VERSION
    # Which layout version this player was last told about. Set on load when an
    # older settings_version was found on disk, and cleared back to -1 (nothing
    # owed) the first time the Gameplay submenu speaks the "where things moved"
    # notices for every version above it. Persisted so a player who quits
    # before opening Gameplay still hears it next time; a fresh install never
    # sets it. An int rather than the single bool it replaced, so the next
    # reorganization does not need a field of its own -- and so a player two
    # layouts behind hears both moves instead of only the newest.
    settings_layout_notice_from: int = -1

    @property
    def path(self):
        return data_dir() / "settings.json"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        # Compatibility write, for one release only. A 1.8.x build installed
        # alongside this one shares the same settings.json and still reads
        # ``steering_assist``; if the key vanished it would fall back to its
        # own default and quietly change what the truck does over there. A
        # reader may tolerate keys it does not know, but a writer must not
        # drop a key another reader still needs. Remove this line once 1.9 is
        # the oldest build players run -- no earlier than the release after
        # 1.9.0.
        data["steering_assist"] = LANE_KEEPING_TO_LEGACY.get(self.lane_keeping, "off")
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(self.path)

    def lane_is_automated(self) -> bool:
        """Whether the truck holds the lane -- and takes the exits -- itself.

        Every spoken instruction about steering hangs off this one answer:
        automated means a tap changes lanes and the destination exit is
        granted, manual means holding a direction steers and every exit needs
        its signal and its lane. Nine call sites used to compare the raw
        string, which is exactly how spoken advice comes to name a key the
        driver's settings do not give them.
        """
        return self.lane_keeping == "full"

    def lane_is_manual(self) -> bool:
        """Whether the lane work -- and the exit -- belongs to the driver."""
        return not self.lane_is_automated()

    def lane_keeping_label(self) -> str:
        """The spoken value with the clause that says what it costs you."""
        return LANE_KEEPING_LABELS.get(
            self.lane_keeping, LANE_KEEPING_LABELS[LANE_KEEPING_FALLBACK]
        )

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
            if not isinstance(data, dict):
                log.warning("Settings file is not a settings object; using defaults")
                data = {}
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError):
            log.warning("Could not read settings; using defaults", exc_info=True)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict | None) -> Settings:
        """Build settings from a parsed settings file, running every migration.

        Split out of :meth:`load` so the migrations are testable without a
        filesystem. ``data`` is ``None`` when there was no readable file and
        every default stands -- several migrations below distinguish that
        from an empty dict (a file that exists but says nothing), and that
        distinction must survive the split.
        """
        s = cls()
        defaults = cls()
        if isinstance(data, dict):
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            # The former board-only opt-in covered less information. Never
            # silently expand it into public Profile sharing.
            if data.get("profile_sharing_consent_version") != PROFILE_SHARING_CONSENT_VERSION:
                s.online_presence = False
        # ``steering_assist`` became ``lane_keeping`` in 1.9. A save that
        # already carries the new key is read as-is; anything older has its
        # legacy value carried across to the mode that behaves identically,
        # so the truck does exactly what it did yesterday. A player who
        # cannot see the row change must never find the steering task in
        # their hands because a setting was renamed.
        if isinstance(data, dict) and "lane_keeping" not in data:
            legacy = data.get("steering_assist")
            if isinstance(legacy, str) and legacy in LANE_KEEPING_FROM_LEGACY:
                s.lane_keeping = LANE_KEEPING_FROM_LEGACY[legacy]
                # This player had the old row under the old name. The row
                # owes them an explanation, and only them.
                s.lane_keeping_rename_notice_left = LANE_KEEPING_RENAME_NOTICES
            elif "steering_assist" in data:
                # The old key is there but says nothing we recognise. Taking
                # the fallback silently would delete the destination-exit
                # decision without a sound.
                s.lane_keeping = LANE_KEEPING_FALLBACK
                s.lane_keeping_unreadable = True
            else:
                s.lane_keeping = LANE_KEEPING_FALLBACK
        from .sim.hos import HOS_MODES

        # Legacy 1.5.0 saves carried a player-selectable "off" mode. It is no
        # longer offered, so such saves fall through to the realistic default
        # below. debug_off stays valid as an internal dev/test bypass only.
        if s.hos_mode not in HOS_MODES:
            s.hos_mode = "realistic"
        if s.lane_cue_loudness not in ("subtle", "standard", "prominent"):
            s.lane_cue_loudness = "standard"
        if s.enforcement_presence not in ENFORCEMENT_PRESENCE_LEVELS:
            s.enforcement_presence = "standard"
        if s.lane_keeping not in LANE_KEEPING_MODES:
            s.lane_keeping = LANE_KEEPING_FALLBACK
            s.lane_keeping_unreadable = True
            s.lane_departure_warning = False
            s.lane_centering_assist = False
        if not isinstance(s.lane_keeping_rename_notice_left, int) or isinstance(
            s.lane_keeping_rename_notice_left, bool
        ):
            s.lane_keeping_rename_notice_left = 0
        s.lane_keeping_rename_notice_left = max(
            0, min(LANE_KEEPING_RENAME_NOTICES, s.lane_keeping_rename_notice_left)
        )
        if data is not None and "driving_assistance_preset" not in data:
            s.lane_departure_warning = s.lane_keeping != "full"
            s.lane_centering_assist = s.lane_keeping == "partial"
            for field in DRIVING_ASSIST_FIELDS:
                if field == "descent_speed_control":
                    setattr(s, field, "off")
                elif field not in (
                    "lane_departure_warning",
                    "lane_centering_assist",
                    # The migrated lane-keeping mode IS this save's current
                    # difficulty. The blanket "everything off" below must not
                    # reach it, or a pre-preset save would change what the
                    # truck does the moment it is opened.
                    "lane_keeping",
                ):
                    setattr(s, field, False)
            s.driving_assistance_preset = "custom"
        for field in DRIVING_ASSIST_FIELDS:
            if field in ("descent_speed_control", "lane_keeping"):
                continue
            if not isinstance(getattr(s, field), bool):
                setattr(s, field, getattr(cls(), field))
        if not isinstance(s.selected_stop_assist, bool):
            s.selected_stop_assist = False
        if s.descent_speed_control not in ("off", "realistic", "balanced", "interactive"):
            s.descent_speed_control = "realistic"
        if s.driving_assistance_preset not in (*DRIVING_ASSIST_PRESETS, "custom"):
            s.driving_assistance_preset = "custom"
        if data is None or "driving_assistance_preset" in data:
            s.refresh_driving_assistance_preset()
        if s.automatic_direction_changes not in ("simple", "deliberate"):
            s.automatic_direction_changes = "simple"
        if s.jake_voice not in ("real", "classic"):
            s.jake_voice = "real"
        # Latching pedals briefly shipped as a bool; map old saves over.
        if s.pedal_latch is True:
            s.pedal_latch = "assists first"
        elif s.pedal_latch is False:
            s.pedal_latch = "off"
        if s.pedal_latch not in ("assists first", "latch first", "off"):
            s.pedal_latch = "assists first"
        # The two-value verbosity became a four-rung ladder (S4). A terse
        # player asked for less and lands on quiet; everyone else on
        # standard, which is what normal already was. Keyed on the absence
        # of the new field, so a player who has since picked a rung is
        # never dragged back by a stale verbosity left in the file.
        if isinstance(data, dict) and "driving_speech" not in data:
            s.driving_speech = "quiet" if data.get("speech_verbosity") == 0 else "standard"
        if s.driving_speech not in DRIVING_SPEECH_MODES:
            s.driving_speech = DEFAULT_DRIVING_SPEECH
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
        # The village switch shipped for one alpha day as a chatter bool. An
        # explicit off carries over as silence; an untouched on takes the new
        # default ladder rather than pinning that player to the loudest tier.
        if (
            isinstance(data, dict)
            and "place_callouts" not in data
            and data.get("chatter_villages") is False
        ):
            s.place_callouts = "off"
        if s.place_callouts not in PLACE_CALLOUT_MODES:
            s.place_callouts = "sparse"
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
        if not isinstance(s.duck_audio_for_speech, bool):
            s.duck_audio_for_speech = False
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
            value = getattr(s, attr)
            # A level that is not a number -- null, true, a list, a word --
            # used to raise straight out of load() and take the game's whole
            # startup with it. It falls back to the default instead. A bool
            # counts as damage, not as a level: false would read as silence.
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                log.warning("Setting %s is not a level (%r); using the default", attr, value)
                value = getattr(defaults, attr)
            else:
                try:
                    value = float(value)
                except ValueError:
                    log.warning("Setting %s is not a level (%r); using the default", attr, value)
                    value = getattr(defaults, attr)
            setattr(s, attr, max(0.0, min(1.0, float(value))))
        if not isinstance(s.radio_station_id, str) or not s.radio_station_id:
            s.radio_station_id = "route_playlist"
        # Settings-menu layout migration. A file written under an older layout
        # (an older settings_version, or none at all) records the version it
        # came from, and the Gameplay submenu later speaks every notice above
        # it; a fresh install (no file to read) writes the current version and
        # stays silent. Not tied to any one field -- it tracks the menu shape.
        if not isinstance(s.settings_layout_notice_from, int) or isinstance(
            s.settings_layout_notice_from, bool
        ):
            s.settings_layout_notice_from = -1
        if isinstance(data, dict):
            saved_version = data.get("settings_version", 0)
            if not isinstance(saved_version, int) or isinstance(saved_version, bool):
                saved_version = 0
            if saved_version < SETTINGS_VERSION:
                # The oldest layout still owed wins: a player who is two
                # reorganizations behind hears both, in order.
                s.settings_layout_notice_from = (
                    saved_version
                    if s.settings_layout_notice_from < 0
                    else min(s.settings_layout_notice_from, saved_version)
                )
        s.settings_version = SETTINGS_VERSION
        return s

    def speech_disposition(self, category: SpeechCategory | None) -> Disposition:
        """How the player's rung delivers this category of information."""
        return disposition_for(self.driving_speech, category)

    def speaks(self, category: SpeechCategory | None) -> bool:
        """Whether this category reaches the voice at all on this rung."""
        return self.speech_disposition(category) not in (
            Disposition.EARCON,
            Disposition.SILENT,
        )

    def renders_terse(self) -> bool:
        """Whether spoken lines take their terse rendering on this rung.

        The rung picks the rendering, so ``SpokenMessage`` keeps the
        single-boolean ``render`` signature S2 gave it.
        """
        return self.driving_speech in ("quiet", "urgent_only")

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
            return f"{spoken_distance(mph, 'mile')} per hour"
        return f"{spoken_distance(mph * MILES_TO_KM, 'kilometer')} per hour"

    def speed_value(self, mph: float) -> str:
        """``speed_text``'s bare number, for the terse slot grammar where the
        frame carries the unit ("Limit 65.")."""
        value = mph if self.imperial_units else mph * MILES_TO_KM
        return f"{round(value):.0f}"

    def distance_text(self, miles: float, precise: bool = False) -> str:
        """Spoken distance in the player's unit. ``precise`` keeps one
        decimal for short spans ("1.2 miles ahead") where whole numbers
        would read as zero or lie by half a mile."""
        value = to_distance(miles, self.imperial_units)
        unit = "mile" if self.imperial_units else "kilometer"
        text = f"{value:.1f}" if precise else f"{value:.0f}"
        plural = "" if float(text) == 1.0 else "s"
        return f"{text} {unit}{plural}"

    def short_distance_text(self, miles: float) -> str:
        """Colloquial short range for pacenote-style calls: quarter-mile
        steps under a mile ("half a mile"), 100-meter steps under a
        kilometer ("400 meters"), the normal precise form beyond."""
        if self.imperial_units:
            if miles > 1.125:
                return self.distance_text(miles, precise=True)
            quarters = max(1, round(miles * 4))
            return {
                1: "a quarter mile",
                2: "half a mile",
                3: "three quarters of a mile",
                4: "one mile",
            }.get(quarters, self.distance_text(miles, precise=True))
        km = miles * MILES_TO_KM
        if km >= 0.95:
            return self.distance_text(miles, precise=True)
        meters = max(1, round(km * 10)) * 100
        return f"{meters} meters"

    def gap_text(self, miles: float) -> str:
        """A spoken distance kept to one decimal, for close-range cues."""
        return spoken_gap(miles, self.imperial_units)

    def hud_speed_text(self, mph: float) -> str:
        """Speed for the visual HUD, in the short written form."""
        return hud_speed(mph, self.imperial_units)

    def distance_value(self, miles: float, decimals: int = 0, *, grouped: bool = False) -> str:
        """A bare converted distance, for readouts that name the unit once
        after two numbers ("12 of 400 miles")."""
        group = "," if grouped else ""
        return f"{to_distance(miles, self.imperial_units):{group}.{decimals}f}"

    def distance_unit_text(self, *, plural: bool = True) -> str:
        """The player's distance unit, to pair with ``distance_value``."""
        return distance_unit(self.imperial_units, plural=plural)

    def per_distance(self, per_mile: float) -> float:
        """A per-mile rate as a rate in the player's own distance unit."""
        return per_mile if self.imperial_units else per_mile / MILES_TO_KM
