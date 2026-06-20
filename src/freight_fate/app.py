"""Application shell: pygame window, state stack, and shared services."""

from __future__ import annotations

import logging
import os
import sys

import pygame

from . import __version__
from .achievements import AchievementAward, award
from .audio import AudioEngine
from .data.world import World, get_world
from .models.economy import Economy
from .models.profile import Profile
from .music import music_track_duration_s
from .settings import Settings
from .speech import Speech
from .states.base import State

log = logging.getLogger(__name__)

WINDOW_SIZE = (900, 640)
FPS = 60
BG_COLOR = (12, 12, 16)
TEXT_COLOR = (235, 235, 225)
HILIGHT_COLOR = (255, 210, 90)


class GameContext:
    """Shared services handed to every state."""

    def __init__(self, app: App) -> None:
        self._app = app
        self.speech: Speech = app.speech
        self.audio: AudioEngine = app.audio
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
        """Shared Open-Meteo provider when real weather is enabled, else None.

        Created lazily and kept for the whole session so its cache spans trips.
        """
        if not self.settings.real_weather:
            return None
        if self._real_weather is None:
            from .sim.real_weather import RealWeatherProvider

            self._real_weather = RealWeatherProvider()
        return self._real_weather

    def say(self, text: str, interrupt: bool = True) -> None:
        self.speech.say(text, interrupt)

    def say_event(self, text: str, interrupt: bool = True) -> None:
        """Driving event announcements (hazards, warnings, weather, ...).

        Spoken on a separate SAPI voice when the player has that enabled, so
        a screen reader reading menus or keystrokes cannot cut them off.
        """
        if self.settings.sapi_events:
            self.speech.say_event(text, interrupt)
        else:
            self.speech.say(text, interrupt)

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
        self.audio.set_volumes(master=self.settings.master_volume,
                               sfx=self.settings.sfx_volume,
                               music=self.settings.music_volume)

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
            advance: bool = False) -> str:
        """Play or refresh a pool without jarring compatible menu restarts."""
        if (not advance
                and self._music_rotation_pool is not None
                and self._music_rotation_track is not None
                and self._music_rotation_pool[0] == pool_name):
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
            return
        self._music_rotation_elapsed_s += max(0.0, dt)
        if self._music_rotation_elapsed_s < music_track_duration_s(
                self._music_rotation_track):
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
            announce: bool = True) -> AchievementAward | None:
        if self.profile is None:
            return None
        result = award(self.profile, achievement_id)
        if result is None:
            return None
        self.profile.save()
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
        self.ctx = GameContext(self)
        self.ctx.apply_volumes()

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

    # -- main loop ------------------------------------------------------------

    def run(self, max_frames: int | None = None) -> None:
        """Main loop. ``max_frames`` runs that many frames then exits
        cleanly; used by the --smoke build check."""
        from .states.main_menu import MainMenuState

        self.running = True
        self.push_state(MainMenuState(self.ctx))
        frames = 0
        try:
            while self.running:
                dt = self.clock.tick(FPS) / 1000.0
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif self.state is not None:
                        self.state.handle_event(event)
                if self.state is not None:
                    self.state.update(dt)
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
        self.audio.shutdown()
        self.speech.shutdown()
        pygame.quit()


def _configure_logging() -> None:
    """Console logging from source; a fresh log file in the packaged game.

    The windowed build has no console, so without a file every warning --
    update failures especially -- vanishes. The log lives next to the saves
    (game folder, saves/game.log) where a player can find and share it.
    """
    level = os.environ.get("FREIGHT_FATE_LOG", "WARNING")
    handlers = None
    from . import updater

    if updater.is_frozen():
        from .models.profile import data_dir

        try:
            log_path = data_dir() / "game.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handlers = [logging.FileHandler(log_path, mode="w", encoding="utf-8")]
        except OSError:
            pass  # unwritable disk: console-only is the best we can do
    logging.basicConfig(
        level=level, handlers=handlers,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> int:
    _configure_logging()
    smoke = "--smoke" in sys.argv[1:]   # CI: boot, render a few frames, exit 0
    try:
        App().run(max_frames=5 if smoke else None)
    except Exception:
        log.exception("Fatal error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
