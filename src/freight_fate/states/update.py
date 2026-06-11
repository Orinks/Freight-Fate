"""Update screens: check, prompt, what's-new reader, and download.

All fully spoken, matching the rest of the game's menus. The check and the
download run on background threads; the states poll them every frame and
speak progress, so the pygame loop (and the screen reader) never blocks on
the network.
"""

from __future__ import annotations

import logging
import threading

import pygame

from .. import __version__, updater
from .base import MenuItem, MenuState, State

log = logging.getLogger(__name__)


class UpdateChecker:
    """Background release check; poll ``result`` from the main loop."""

    def __init__(self, settings) -> None:
        self.done = threading.Event()
        self.result: updater.UpdateInfo | None = None
        self.error: str | None = None
        build = updater.load_build_info(__version__)
        channel = updater.resolve_channel(settings.update_channel, build)
        self._thread = threading.Thread(
            target=self._run, args=(channel, build), daemon=True)
        self._thread.start()

    def _run(self, channel: str, build) -> None:
        try:
            self.result = updater.check_for_update(channel, __version__, build)
        except Exception as e:  # offline, rate-limited, GitHub down...
            log.info("Update check failed: %s", e)
            self.error = "Could not reach the update server."
        finally:
            self.done.set()


class UpdateCheckState(State):
    """Manual 'Check for updates' from the Settings menu."""

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.checker: UpdateChecker | None = None
        self.message = ""

    def enter(self) -> None:
        if not updater.is_frozen():
            self.message = ("Updates are only available in the packaged game. "
                            "This copy runs from source; update it with git.")
            self.ctx.say(self.message + " Press Escape to go back.")
            return
        if self.checker is None:
            self.ctx.say("Checking for updates...")
            self.checker = UpdateChecker(self.ctx.settings)

    def update(self, dt: float) -> None:
        c = self.checker
        if c is None or not c.done.is_set() or self.message:
            return
        if c.error:
            self.message = c.error + " Check your internet connection and try again."
        elif c.result is None:
            self.message = f"You are up to date. Freight Fate version {__version__}."
        else:
            self.ctx.replace_state(UpdatePromptState(self.ctx, c.result))
            return
        self.ctx.say(self.message + " Press Escape to go back.")

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.ctx.audio.play("ui/menu_back")
            self.ctx.pop_state()

    def lines(self) -> list[str]:
        return ["Check for updates", "",
                self.message or "Checking for updates..."]


class UpdatePromptState(MenuState):
    """Asks whether to download a newly found update."""

    title = "Update available"
    intro_help = ("A new version of the game is available. Download and "
                  "restart installs it now. What's new reads the list of "
                  "changes. Skip this version stops asking about this "
                  "particular update.")

    def __init__(self, ctx, info: updater.UpdateInfo) -> None:
        super().__init__(ctx)
        self.info = info

    def announce_entry(self) -> None:
        mb = self.info.asset_size / 1e6
        size = f" The download is {mb:.0f} megabytes." if mb else ""
        self.ctx.say(f"Update available. {self.info.title} is ready to "
                     f"install. You are running version {__version__}.{size} "
                     f"{self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem("Download and restart", self._download,
                     help="Download the update, then restart the game with "
                          "the new version in place."),
            MenuItem("What's new", self._whats_new,
                     help="Read the changes in this update, line by line."),
            MenuItem("Remind me later", self.go_back,
                     help="Ask again the next time the game starts."),
            MenuItem("Skip this version", self._skip,
                     help="Do not ask about this update again. Later updates "
                          "will still be offered."),
        ]

    def _download(self) -> None:
        if not updater.is_frozen():
            self.ctx.say("Updates can only be installed in the packaged "
                         "game. This copy runs from source.")
            return
        self.ctx.replace_state(UpdateDownloadState(self.ctx, self.info))

    def _whats_new(self) -> None:
        self.ctx.push_state(WhatsNewState(self.ctx, self.info))

    def _skip(self) -> None:
        self.ctx.settings.skipped_update = self.info.tag
        self.ctx.settings.save()
        self.ctx.say(f"Skipping {self.info.title}. You will be asked again "
                     "when the next update comes out.")
        self.ctx.pop_state()


class WhatsNewState(State):
    """Line-by-line reader for the update's release notes."""

    def __init__(self, ctx, info: updater.UpdateInfo) -> None:
        super().__init__(ctx)
        self.info = info
        self.notes = info.notes or ["No change notes were provided."]
        self.line = -1

    def enter(self) -> None:
        self.ctx.say(f"What's new in {self.info.title}. "
                     f"{len(self.notes)} lines. Up and Down arrows read line "
                     "by line, Enter reads everything, Escape goes back.")

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.ctx.audio.play("ui/menu_back")
            self.ctx.pop_state()
        elif event.key == pygame.K_DOWN:
            self.line = min(self.line + 1, len(self.notes) - 1)
            self.ctx.say(self.notes[self.line])
        elif event.key == pygame.K_UP:
            self.line = max(self.line - 1, 0)
            self.ctx.say(self.notes[self.line])
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.ctx.say(" ".join(self.notes))

    def lines(self) -> list[str]:
        out = [f"What's new - {self.info.title}", ""]
        for i, text in enumerate(self.notes[:14]):
            out.append(("> " if i == self.line else "  ") + text)
        return out


class UpdateDownloadState(State):
    """Downloads and stages the update, then restarts the game."""

    def __init__(self, ctx, info: updater.UpdateInfo) -> None:
        super().__init__(ctx)
        self.info = info
        self.cancelled = threading.Event()
        self.done = threading.Event()
        self.new_root = None
        self.staging = None
        self.error: str | None = None
        self.progress = 0.0       # 0..1, written by the worker thread
        self._spoken_quarter = 0
        self._finished = False
        self._thread: threading.Thread | None = None

    def enter(self) -> None:
        if self._thread is not None:
            return
        mb = self.info.asset_size / 1e6
        size = f", {mb:.0f} megabytes" if mb else ""
        self.ctx.say(f"Downloading {self.info.title}{size}. The game will "
                     "restart when the download finishes. Press Escape to cancel.")
        self._thread = threading.Thread(target=self._work, daemon=True)
        self._thread.start()

    def _work(self) -> None:
        try:
            self.staging = updater.make_staging_dir()
            archive = updater.download(
                self.info, self.staging,
                progress=self._on_progress, cancelled=self.cancelled)
            self.new_root = updater.extract(archive, self.staging / "unpacked")
            archive.unlink(missing_ok=True)
        except updater.UpdateCancelled:
            pass
        except Exception as e:
            log.warning("Update download failed: %s", e)
            self.error = ("The download failed. Check your internet "
                          "connection and try again later.")
        finally:
            self.done.set()

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.progress = done / total

    def update(self, dt: float) -> None:
        if self._finished:
            return
        quarter = int(self.progress * 4)
        if quarter > self._spoken_quarter and quarter < 4:
            self._spoken_quarter = quarter
            self.ctx.say(f"{quarter * 25} percent.", interrupt=False)
        if not self.done.is_set():
            return
        self._finished = True
        if self.cancelled.is_set():
            self.ctx.pop_state()
        elif self.error or self.new_root is None:
            self.ctx.say(self.error or "The download failed.")
            self.ctx.audio.play("ui/error")
            self.ctx.pop_state()
        else:
            self.ctx.say("Download complete. Restarting the game to finish "
                         "the update. See you in a moment.", interrupt=True)
            updater.apply_and_restart(self.new_root, self.staging)
            self.ctx.quit()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN or self._finished:
            return
        if event.key == pygame.K_ESCAPE:
            self.cancelled.set()
            self.ctx.say("Update cancelled.")
            self.ctx.audio.play("ui/menu_back")
            if self.done.is_set():
                self._finished = True
                self.ctx.pop_state()
            # otherwise update() pops once the worker notices the flag
        elif event.key == pygame.K_TAB:
            self.ctx.say(f"{self.progress * 100:.0f} percent downloaded.")

    def lines(self) -> list[str]:
        return [f"Downloading {self.info.title}", "",
                f"{self.progress * 100:.0f} percent",
                "Press Escape to cancel, Tab for progress."]
