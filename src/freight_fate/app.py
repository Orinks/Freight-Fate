"""Application shell: pygame window, state stack, and shared services."""

from __future__ import annotations

import logging
import os
import sys

import pygame

from . import __version__
from .audio import AudioEngine
from .data.world import World, get_world
from .models.economy import Economy
from .models.profile import Profile
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
            for i, line in enumerate(state.lines()[:18]):
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
