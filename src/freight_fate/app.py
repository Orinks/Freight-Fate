"""Application shell: pygame window, state stack, and shared services."""

from __future__ import annotations

import contextlib
import faulthandler
import logging
import os
import sys
import time
from pathlib import Path

import pygame

from . import __version__
from .achievements import AchievementAward, award
from .audio import AudioEngine
from .cloud_saves import CloudSaves
from .controller import ControllerManager
from .data.world import World, get_world
from .discord_presence import DiscordPresence
from .models.economy import Economy
from .models.profile import Profile
from .music import music_track_duration_s
from .online_journal import JournalOutbox, queue_achievement, queue_profile_snapshot
from .online_presence import OnlineIdentity, OnlinePresence
from .settings import Settings
from .speech import Speech
from .states.base import State

log = logging.getLogger(__name__)
# Every spoken line lands here too, so a logged playtest reads as a transcript of
# what the player heard -- the most faithful record for an audio-first game.
transcript = logging.getLogger("freight_fate.transcript")

WINDOW_SIZE = (900, 640)
FPS = 60

_CONTROLLER_EVENTS = frozenset(
    {
        pygame.CONTROLLERBUTTONDOWN,
        pygame.CONTROLLERBUTTONUP,
        pygame.CONTROLLERAXISMOTION,
        pygame.CONTROLLERDEVICEADDED,
        pygame.CONTROLLERDEVICEREMOVED,
    }
)
BG_COLOR = (12, 12, 16)
TEXT_COLOR = (235, 235, 225)
HILIGHT_COLOR = (255, 210, 90)


def _stop_main_speech(speech) -> None:
    stop = getattr(speech, "stop_main", None) or getattr(speech, "stop", None)
    if stop is not None:
        stop()


def _stop_event_speech(speech) -> None:
    stop = getattr(speech, "stop_event", None)
    if stop is not None:
        stop()


class GameContext:
    """Shared services handed to every state."""

    def __init__(self, app: App) -> None:
        self._app = app
        self.speech: Speech = app.speech
        self.audio: AudioEngine = app.audio
        self.controller: ControllerManager = app.controller
        self.settings: Settings = app.settings
        self.world: World = app.world
        self.economy: Economy = app.economy
        self.profile: Profile | None = None
        self._real_weather = None
        self._music_pool_positions: dict[tuple[str, tuple[str, ...]], int] = {}
        self._music_pool_last: dict[str, str] = {}
        self._music_rotation_pool: tuple[str, tuple[str, ...]] | None = None
        self._music_rotation_track: str | None = None
        self._music_rotation_elapsed_s = 0.0
        self.achievement_notice = ""
        self.achievement_notice_timer = 0.0

    def real_weather_provider(self):
        """Shared NWS provider when real weather is enabled, else None.

        Created lazily and kept for the whole session so its cache spans trips.
        """
        if not self.settings.real_weather:
            return None
        if self._real_weather is None:
            from .sim.real_weather import RealWeatherProvider

            self._real_weather = RealWeatherProvider()
        return self._real_weather

    def say(self, text: str, interrupt: bool = True) -> None:
        transcript.info("%s", text)
        self.speech.say(text, interrupt)

    def say_event(self, text: str, interrupt: bool = True) -> None:
        """Driving event announcements (hazards, warnings, weather, ...).

        With the dedicated SAPI event voice enabled, events speak on their own
        channel, where ``interrupt`` only cuts off a previous event -- so an
        urgent cue can still jump ahead of a stale one without touching the
        screen reader.

        With it disabled the player has chosen to hear events through their
        screen reader. Urgent events first flush stale game speech, then speak
        as a fresh queued utterance so old messages do not bury the warning.
        """
        transcript.info("[event] %s", text)
        if self.settings.sapi_events:
            self.speech.say_event(text, interrupt)
        else:
            if interrupt:
                _stop_main_speech(self.speech)
            self.speech.say(text, interrupt=False)

    def stop_event_speech(self) -> None:
        _stop_event_speech(self.speech)

    def stop_speech(self) -> None:
        """Silence all in-progress speech on both channels (main and event).

        Menus and readers speak through the main channel, so the driving-only
        ``stop_event_speech`` does not quiet them. This silences everything so a
        single key works as a "stop talking" everywhere in the game.
        """
        _stop_main_speech(self.speech)
        _stop_event_speech(self.speech)

    # -- state stack ------------------------------------------------------------

    def push_state(self, state: State) -> None:
        self._app.push_state(state)

    def pop_state(self) -> None:
        self._app.pop_state()

    def replace_state(self, state: State) -> None:
        self._app.replace_state(state)

    def reset_to(self, state: State) -> None:
        self._app.reset_to(state)

    def quit(self) -> None:
        self._app.running = False

    def save_profile(self) -> None:
        if self.profile is not None:
            self.profile.save()

    def apply_volumes(self) -> None:
        self.audio.set_volumes(
            master=self.settings.master_volume,
            sfx=self.settings.sfx_volume,
            music=self.settings.music_volume,
            weather=self.settings.weather_volume,
            engine=self.settings.engine_volume,
            ui=self.settings.ui_volume,
        )

    def apply_presence(self) -> None:
        """Reflect the Discord presence setting (e.g. after a settings change)."""
        self._app.presence.set_enabled(self.settings.discord_presence)

    def apply_online_presence(self) -> None:
        """Reflect the drivers-board setting (e.g. after a settings change)."""
        self._app.online.set_enabled(self.settings.online_presence)

    def apply_cloud_saves(self) -> None:
        """Reflect the cloud backup setting (e.g. after a settings change)."""
        self._app.cloud.set_enabled(self.settings.cloud_saves)

    def cloud_saves_service(self) -> CloudSaves:
        """The backup service, for the Cloud backup menu."""
        return self._app.cloud

    def adopt_online_identity(self, identity) -> None:
        """Adopt freshly confirmed account credentials (setup flow). The
        drivers board and cloud backup share them."""
        self._app.online.set_identity(identity)
        self._app.cloud.set_identity(identity)

    def apply_controller(self) -> None:
        """Reflect the controller setting (e.g. after a settings change)."""
        self.controller.set_enabled(self.settings.controller_enabled)

    def apply_haptics(self) -> None:
        """Reflect the haptics setting (e.g. after a settings change)."""
        self.controller.set_haptics_enabled(self.settings.haptics_enabled)

    def control_hint(self, action: str) -> str:
        """Name a control for a spoken prompt, following the active device."""
        return self.controller.hint(action)

    def apply_speech(self) -> None:
        self.speech.select_event_backend(
            self.settings.event_backend if self.settings.sapi_events else None
        )
        # If the saved voice was not on this machine (e.g. a Windows save's
        # SAPI opened on macOS), record the one actually used so the menu and
        # later sessions reflect reality.
        if self.settings.sapi_events:
            actual = self.speech.event_backend_name
            if actual not in ("none", "unknown") and actual != self.settings.event_backend:
                self.settings.event_backend = actual
        self.speech.configure(
            rate=self.settings.speech_rate,
            pitch=self.settings.speech_pitch,
            volume=self.settings.speech_volume,
            voice=self.settings.speech_voice or None,
        )

    def next_music_track(self, pool_name: str, sequence: tuple[str, ...]) -> str:
        """Advance a session-local music pool without immediate repeats."""
        if not sequence:
            return ""
        if len(sequence) == 1:
            track = sequence[0]
            self._music_pool_last[pool_name] = track
            return track
        key = (pool_name, sequence)
        index = (self._music_pool_positions.get(key, -1) + 1) % len(sequence)
        if sequence[index] == self._music_pool_last.get(pool_name):
            index = (index + 1) % len(sequence)
        self._music_pool_positions[key] = index
        track = sequence[index]
        self._music_pool_last[pool_name] = track
        return track

    def play_music_sequence(
        self,
        pool_name: str,
        sequence: tuple[str, ...],
        *,
        fade_ms: int = 1500,
        advance: bool = False,
    ) -> str:
        """Play or refresh a pool without jarring compatible menu restarts."""
        if (
            not advance
            and self._music_rotation_pool is not None
            and self._music_rotation_track is not None
            and self._music_rotation_pool[0] == pool_name
        ):
            self._music_rotation_pool = (pool_name, sequence)
            return self._music_rotation_track
        track = self.next_music_track(pool_name, sequence)
        if not track:
            self.clear_music_rotation()
            return track
        self._music_rotation_pool = (pool_name, sequence)
        self._music_rotation_track = track
        self._music_rotation_elapsed_s = 0.0
        self.audio.play_music(track, fade_ms=fade_ms)
        return track

    def update_music_rotation(self, dt: float) -> None:
        """Advance music beds when their one-shot playback ends."""
        if self._music_rotation_pool is None or self._music_rotation_track is None:
            # No menu bed is rotating. A drive sitting under this menu (pause,
            # settings, a traffic stop...) keeps its own playlist turning over,
            # so the music does not fall silent when the current track ends.
            for state in reversed(self._app.states[:-1]):
                tick = getattr(state, "tick_covered_music", None)
                if tick is not None:
                    tick(dt)
                    break
            return
        self._music_rotation_elapsed_s += max(0.0, dt)
        if self._music_rotation_elapsed_s < music_track_duration_s(self._music_rotation_track):
            return
        pool_name, sequence = self._music_rotation_pool
        self.play_music_sequence(pool_name, sequence, advance=True)

    def clear_music_rotation(self) -> None:
        self._music_rotation_pool = None
        self._music_rotation_track = None
        self._music_rotation_elapsed_s = 0.0

    def award_achievement(
        self,
        achievement_id: str,
        *,
        event: bool = False,
        interrupt: bool = False,
        announce: bool = True,
    ) -> AchievementAward | None:
        if self.profile is None:
            return None
        result = award(self.profile, achievement_id)
        if result is None:
            return None
        self.profile.save()
        if queue_achievement(
            self._app.journal, result.achievement, earned_at_ms=int(time.time() * 1000)
        ):
            self._app.journal.flush_async()
        self.achievement_notice = result.message
        self.achievement_notice_timer = 12.0
        if not announce:
            return result
        self.audio.play("ui/level_up", volume=0.8)
        self.say(result.message, interrupt=interrupt)
        return result


class App:
    def __init__(self) -> None:
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        # Opt PS4/PS5 pads into HIDAPI rumble so their motors work like Xbox
        # pads. Must be set before pygame.init(); Xbox/XInput needs no flag.
        os.environ.setdefault("SDL_JOYSTICK_HIDAPI_PS4_RUMBLE", "1")
        os.environ.setdefault("SDL_JOYSTICK_HIDAPI_PS5_RUMBLE", "1")
        if os.environ.get("FREIGHT_FATE_NO_SPEECH"):
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            os.environ["SDL_AUDIODRIVER"] = "dummy"
        pygame.init()
        pygame.display.set_caption(f"Freight Fate {__version__}")
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Segoe UI, DejaVu Sans, Arial", 26)
        self.font_big = pygame.font.SysFont("Segoe UI, DejaVu Sans, Arial", 34, bold=True)

        self.settings = Settings.load()
        self.speech = Speech()
        self.audio = AudioEngine()
        self.world = get_world()
        self.economy = Economy()
        self.presence = DiscordPresence(enabled=self.settings.discord_presence)
        identity = OnlineIdentity.load()
        self.online = OnlinePresence(
            enabled=self.settings.online_presence,
            identity=identity,
        )
        self.cloud = CloudSaves(
            enabled=self.settings.cloud_saves,
            identity=identity,
        )
        self.journal = JournalOutbox(
            identity=identity,
            enabled=self.settings.online_presence,
            path=OnlineIdentity.path().with_name("online-outbox.json"),
        )
        # Every profile save, wherever it happens, queues a cloud backup.
        from .models import profile as profile_module

        def saved_profile(profile) -> None:
            self.cloud.queue_backup(profile)
            try:
                from .models.trucks import TRUCK_CATALOG

                city_name = self.world.city(profile.current_city).spoken_qualified
                truck_name = TRUCK_CATALOG[profile.truck].label
                queued = queue_profile_snapshot(
                    self.journal,
                    profile,
                    city_name=city_name,
                    truck_name=truck_name,
                    captured_at_ms=int(time.time() * 1000),
                )
                if queued:
                    self.journal.flush_async()
            except (KeyError, AttributeError):
                log.debug("Profile snapshot was not queueable", exc_info=True)

        self._profile_save_listener = saved_profile
        profile_module.save_listener = saved_profile
        self.controller = ControllerManager(
            enabled=self.settings.controller_enabled,
            haptics=self.settings.haptics_enabled,
        )
        self.ctx = GameContext(self)
        self.ctx.apply_volumes()
        self.ctx.apply_speech()

        self.states: list[State] = []
        self.running = False

    # -- state stack ------------------------------------------------------------

    @property
    def state(self) -> State | None:
        return self.states[-1] if self.states else None

    def push_state(self, state: State) -> None:
        self.states.append(state)
        state.enter()

    def pop_state(self) -> None:
        if self.states:
            self.states.pop().exit()
        if self.state is not None:
            self.state.enter()
        else:
            self.running = False

    def replace_state(self, state: State) -> None:
        if self.states:
            self.states.pop().exit()
        self.push_state(state)

    def reset_to(self, state: State) -> None:
        while self.states:
            self.states.pop().exit()
        self.push_state(state)

    def _dispatch_controller(self, event: pygame.event.Event) -> None:
        """Feed a controller event to the manager, then to the active state.

        The manager updates its cached axis/modifier/hot-plug state first and
        reports whether the event is an accepted button press for the bound
        controller; only those reach the state, so a duplicate from a pad that
        enumerates twice can never fire an action a second time.
        """
        forward = self.controller.process_event(event)
        if forward and self.controller.active and self.state is not None:
            self.state.handle_controller(event, self.controller)

    # -- main loop ------------------------------------------------------------

    def run(self, max_frames: int | None = None) -> None:
        """Main loop. ``max_frames`` runs that many frames then exits
        cleanly; used by the --smoke build check."""
        from .states.main_menu import MainMenuState

        self.running = True
        self.push_state(MainMenuState(self.ctx))
        self.presence.start()  # after init; never blocks if Discord is absent
        self.online.start()  # opt-in drivers board; dormant unless confirmed
        self.cloud.start()  # opt-in save backup; dormant unless confirmed
        frames = 0
        try:
            while self.running:
                dt = self.clock.tick(FPS) / 1000.0
                try:
                    events = pygame.event.get()
                except Exception:
                    # A controller hot-plug (notably a Bluetooth resume) can make
                    # SDL's internal instance-id map inconsistent, and pygame's
                    # controller layer then raises out of the C event pump
                    # (KeyError surfacing as SystemError). Losing this batch of
                    # events is survivable; crashing the game is not.
                    log.exception(
                        "pygame.event.get() failed (frame %d; controller %s); skipping this batch",
                        frames,
                        "connected" if self.controller.connected else "disconnected",
                    )
                    with contextlib.suppress(Exception):
                        pygame.event.pump()
                    continue
                for event in events:
                    if event.type == pygame.WINDOWFOCUSGAINED:
                        # Switching screen readers happens outside the game;
                        # re-check speech the moment the player comes back.
                        self.speech.request_refresh()
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type in _CONTROLLER_EVENTS:
                        self._dispatch_controller(event)
                    elif self.state is not None:
                        if event.type == pygame.KEYDOWN:
                            self.controller.note_keyboard()
                        self.state.handle_event(event)
                # Auto-repeat (held D-pad left/right) and analog smoothing.
                # Synthetic repeats go straight to the state (bypassing the
                # manager, whose press state must not be reset) and only where
                # the menu wants adjust-repeat -- driving keeps D-pad discrete.
                repeats = self.controller.tick(dt)
                state = self.state
                if state is not None and getattr(state, "wants_controller_repeat", False):
                    for event in repeats:
                        state.handle_controller(event, self.controller)
                # Reconnect speech if the player's screen reader changed.
                self.speech.poll(dt)
                if self.controller.take_disconnect():
                    self.ctx.say(
                        "Controller disconnected. You can keep playing with the "
                        "keyboard, or reconnect your controller.",
                    )
                    if self.state is not None:
                        self.state.on_controller_disconnect()
                self.ctx.audio.update(dt)  # advance time-based audio fades
                if self.state is not None:
                    self.state.update(dt)
                    self.presence.update(self.state.presence())
                    self.online.update(self.state.online_presence())
                if self.ctx.achievement_notice_timer > 0:
                    self.ctx.achievement_notice_timer = max(
                        0.0,
                        self.ctx.achievement_notice_timer - dt,
                    )
                    if self.ctx.achievement_notice_timer == 0:
                        self.ctx.achievement_notice = ""
                self.render()
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    self.running = False
        finally:
            self.shutdown()

    def render(self) -> None:
        self.screen.fill(BG_COLOR)
        state = self.state
        if state is not None:
            y = 30
            base_lines = state.lines()
            if self.ctx.achievement_notice:
                lines = base_lines[:16] + ["", self.ctx.achievement_notice]
            else:
                lines = base_lines[:18]
            for i, line in enumerate(lines[:18]):
                font = self.font_big if i == 0 else self.font
                color = HILIGHT_COLOR if line.startswith("> ") else TEXT_COLOR
                surf = font.render(line, True, color)
                self.screen.blit(surf, (40, y))
                y += font.get_height() + 6
        pygame.display.flip()

    def shutdown(self) -> None:
        if self.ctx.profile is not None:
            self.ctx.profile.save()
        self.settings.save()
        self.presence.shutdown()
        self.online.shutdown()
        self.cloud.shutdown()  # flushes the final save's backup, bounded
        from .models import profile as profile_module

        if profile_module.save_listener == self._profile_save_listener:
            profile_module.save_listener = None
        self.controller.shutdown()
        self.audio.shutdown()
        self.speech.shutdown()
        pygame.quit()


def _configure_logging() -> None:
    """Console logging from source; a fresh log file in the packaged game.

    The windowed build has no console, so without a file every warning --
    update failures especially -- vanishes. The log lives in the game folder
    (logs/game.log) where a player can find and share it without mixing it
    with durable saves.
    """
    from . import updater

    packaged = updater.is_frozen()
    # An explicit log file (set for playtests/observation) forces file output and
    # an INFO default even from a source checkout, so a session can be reviewed
    # after the fact without streaming to a console.
    explicit_log_file = os.environ.get("FREIGHT_FATE_LOG_FILE")
    default_level = "INFO" if (packaged or explicit_log_file) else "WARNING"
    level = os.environ.get("FREIGHT_FATE_LOG", default_level)
    handlers = None

    log_path = None
    if explicit_log_file:
        log_path = Path(explicit_log_file)
    elif packaged:
        from .models.profile import game_root

        log_path = game_root() / "logs" / "game.log"
    if log_path is not None:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            # Keep the previous run's log as game.prev.log: after a crash the
            # player relaunches the game to report it, and that relaunch must
            # not wipe the evidence.
            if log_path.exists():
                # Rotation is best-effort; a locked file still gets a fresh log.
                prev = log_path.with_name(f"{log_path.stem}.prev{log_path.suffix}")
                with contextlib.suppress(OSError):
                    log_path.replace(prev)
            handlers = [logging.FileHandler(log_path, mode="w", encoding="utf-8")]
            # Crashes inside native libraries (audio, video) kill the process
            # without ever reaching Python logging; faulthandler writes the
            # tracebacks straight to the log file as the process dies.
            faulthandler.enable(file=handlers[0].stream)
        except OSError:
            pass  # unwritable disk: console-only is the best we can do
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    _configure_logging()
    smoke = "--smoke" in sys.argv[1:]  # CI: boot, render a few frames, exit 0
    from .single_instance import SingleInstanceGuard

    guard = SingleInstanceGuard()
    if not guard.acquire():
        log.warning("Freight Fate is already running.")
        return 0
    try:
        if smoke:
            # The build check must prove world data loads (frozen builds
            # carry it baked into the executable, not as files) and that
            # sound assets are readable (frozen builds ship a pack file).
            from .audio import verify_sound_assets
            from .data.world import get_world

            get_world()
            verify_sound_assets()
        App().run(max_frames=5 if smoke else None)
    except Exception:
        log.exception("Fatal error")
        return 1
    finally:
        guard.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
