"""Menus for the orinks.net drivers board: setup flow and the live list.

Setup follows the account model: the player signs in on orinks.net, the
site's driver setup page issues a public Driver ID and a one-time posting
token, and the player copies each into the clipboard and pastes it here.
Nothing is transmitted until the player activates "Connect and save", and
the spoken disclosure below tells them exactly what sharing will send.

All network calls run on daemon threads; the menu states poll a small result
slot from ``update`` so the game loop and speech stay responsive throughout.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
import webbrowser

import pygame

from .. import online_presence
from ..online_presence import OnlineIdentity
from .base import MenuItem, MenuState

DISCLOSURE = (
    "Sharing on the drivers board sends your in-game activity to orinks.net "
    "while you are hauling: what you are doing, your route's cities, your "
    "cargo, and rough progress. It appears under the driver name on your "
    "orinks.net account, chosen on the site's setup page. Nothing about you "
    "or your computer is sent: no real name, no location, no save files. You "
    "can turn this off any time in Settings, Online, and you disappear from "
    "the board within minutes."
)

_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-_")

# Tokens issued by the site are always "ffd_" plus 64 hex characters; the
# prefix is the reliable discriminator that lets the paste items forgive the
# most likely mistake, pasting one value onto the other item.
_TOKEN_PREFIX = "ffd_"


def _clean_clip(text: str) -> str:
    """Strip the junk Windows clipboards attach: NULs, CR/LF, whitespace."""
    return text.replace("\x00", "").strip()


def _clipboard_once() -> str | None:
    """One clipboard read attempt, or None when no text could be read."""
    try:
        scrap = pygame.scrap
        if hasattr(scrap, "get_text"):  # pygame-ce >= 2.2: returns clean str
            text = scrap.get_text()
            if text:
                return _clean_clip(text)
        else:  # legacy scrap: bytes with possible trailing NULs
            if not scrap.get_init():
                scrap.init()  # needs the display up; raises when called early
            raw = scrap.get(pygame.SCRAP_TEXT)
            if raw:
                return _clean_clip(raw.decode("utf-8", "ignore"))
    except Exception:
        pass
    # macOS fallback: pbpaste ships with the OS and needs no GUI toolkit.
    # A hidden Tk root must never be created here -- initializing Tk inside
    # a running SDL app aborts the whole process at the C level (Cocoa
    # tolerates one GUI toolkit per app), and try/except cannot catch it.
    if sys.platform == "darwin":
        try:
            result = subprocess.run(["pbpaste"], capture_output=True, timeout=2.0, check=False)
            if result.returncode == 0 and result.stdout:
                return _clean_clip(result.stdout.decode("utf-8", "ignore")) or None
        except Exception:
            pass
        return None
    # Fallback elsewhere: hidden Tk root, synchronously on the game loop (it
    # is fast; a worker-thread Tk on Windows is not reliable).
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        try:
            return _clean_clip(str(root.clipboard_get()))
        finally:
            root.destroy()
    except Exception:
        return None


def read_clipboard_text() -> str | None:
    """Best-effort clipboard text. Retries once: the Windows clipboard is a
    contended global that clipboard managers briefly hold open."""
    text = _clipboard_once()
    if text:
        return text
    time.sleep(0.1)
    return _clipboard_once()


def looks_like_driver_id(text: str) -> bool:
    t = text.strip().lower()
    return 8 <= len(t) <= 64 and all(c in _ID_CHARS for c in t)


def looks_like_token(text: str) -> bool:
    t = text.strip()
    return t.startswith(_TOKEN_PREFIX) and 24 <= len(t) <= 512 and not any(c.isspace() for c in t)


class OnlineSetupState(MenuState):
    """Paste account-issued credentials, verify them, and turn sharing on.

    Pushed from the settings menu when the player turns sharing on for the
    first time. The menu is deliberately STATIC — the same six items for the
    whole flow, with labels that carry the captured state — because players
    build positional memory of spoken menus and refresh() preserves indices,
    not item identity. On success it saves the credentials, flips the
    setting, and tells the running presence service to adopt them.
    """

    title = "Driver profile setup"

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._driver_id: str | None = None
        self._token: str | None = None
        self._checking = False
        self._check_started = 0.0
        self._still_checking_said = False
        self._outcome: str | None = None  # worker -> update() mailbox
        self._opened_browser = False

    # -- static menu ----------------------------------------------------------

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "Open the driver setup page in my browser",
                self._open_page,
                help="Sign in on orinks.net, set up your driver there, then "
                "copy your Driver ID first.",
            ),
            MenuItem(
                self._id_label,
                self._paste_id,
                help="Copies are taken from the clipboard. Use the Copy "
                "Driver ID button on the setup page, then choose this item.",
            ),
            MenuItem(
                self._token_label,
                self._paste_token,
                help="Use the Copy token button on the setup page, then "
                "choose this item. The token is never spoken aloud.",
            ),
            MenuItem(
                self._connect_label,
                self._connect,
                help="Checks your pasted credentials with orinks.net, saves "
                "them, and turns sharing on. Nothing is sent before this.",
            ),
            MenuItem("Hear what gets shared", self._speak_disclosure),
            MenuItem("Cancel", self.go_back, help="Leave without turning sharing on."),
        ]

    def _id_label(self) -> str:
        if self._driver_id:
            return f"Driver ID: {self._driver_id} — paste again to replace"
        return "Paste Driver ID from clipboard"

    def _token_label(self) -> str:
        if self._token:
            return "Driver token: captured — paste again to replace"
        return "Paste driver token from clipboard"

    def _connect_label(self) -> str:
        return "Checking your credentials" if self._checking else "Connect and save"

    def announce_entry(self) -> None:
        self.ctx.say(
            f"{self.title}. Sharing sends only your in-game hauling activity "
            "to orinks.net, under the driver name on your orinks.net account. "
            "Nothing personal is sent, and nothing is sent at all until you "
            "choose Connect and save at the end of this menu. The items below "
            f"walk you through it in order. {self.current_text()}"
        )

    def _speak_disclosure(self) -> None:
        self.ctx.say(DISCLOSURE)

    # -- the two-app dance ------------------------------------------------------

    def _open_page(self) -> None:
        url = f"{online_presence.base_url()}/freight-fate/online/setup"
        try:
            webbrowser.open(url)
        except Exception:
            self.ctx.say(
                "The browser could not be opened. In your browser, go to "
                "orinks.net, open Freight Fate, then Online setup.",
                interrupt=True,
            )
            return
        self._opened_browser = True
        self.ctx.say(
            "Opening the setup page in your browser. Sign in, set up your "
            "driver, and copy your Driver ID first. Then come back here.",
            interrupt=True,
        )

    def handle_event(self, event) -> None:
        # Re-orient after the browser round trip: this flow is a two-app
        # dance, and "where was I" is the first question on every return.
        if event.type == pygame.WINDOWFOCUSGAINED and self._opened_browser and not self._checking:
            self.ctx.say(f"Back in Freight Fate. {self.current_text()}")
            return
        super().handle_event(event)

    # -- pastes -----------------------------------------------------------------

    def _paste_id(self) -> None:
        text = read_clipboard_text()
        if not text:
            self.ctx.say(
                "I could not read text from the clipboard. Copy the Driver ID "
                "on the setup page, then choose this item again.",
                interrupt=True,
            )
            return
        if looks_like_token(text):
            self._token = text
            self.refresh()
            self.ctx.say(
                "That looks like your driver token, so I saved it as the "
                "token. Now copy your Driver ID and paste it on this item.",
                interrupt=True,
            )
            return
        candidate = text.lower()
        if not looks_like_driver_id(candidate):
            # Never speak the clipboard contents: it could hold anything.
            self.ctx.say(
                "The clipboard text does not look like a Driver ID. Use the "
                "Copy button next to it on the setup page, then choose this "
                "item again.",
                interrupt=True,
            )
            return
        self._driver_id = candidate
        self.refresh()
        self.ctx.say(f"Driver ID captured: {candidate}.", interrupt=True)

    def _paste_token(self) -> None:
        text = read_clipboard_text()
        if not text:
            self.ctx.say(
                "I could not read text from the clipboard. Copy the driver "
                "token on the setup page, then choose this item again.",
                interrupt=True,
            )
            return
        if not text.startswith(_TOKEN_PREFIX) and looks_like_driver_id(text.lower()):
            self._driver_id = text.lower()
            self.refresh()
            self.ctx.say(
                "That looks like your Driver ID, so I saved it as the Driver "
                "ID. Now copy your driver token and paste it on this item.",
                interrupt=True,
            )
            return
        if not looks_like_token(text):
            self.ctx.say(
                "The clipboard text does not look like a driver token. "
                "Tokens from the setup page start with the letters F F D "
                "and an underscore. Use the Copy token button on the setup "
                "page, then choose this item again.",
                interrupt=True,
            )
            return
        self._token = text
        self.refresh()
        # Spoken length must match what the site showed; text is already
        # trimmed. The token itself is never spoken.
        self.ctx.say(f"Token captured, {len(text)} characters.", interrupt=True)

    # -- connect ------------------------------------------------------------------

    def _connect(self) -> None:
        if self._checking:
            return
        if not self._driver_id or not self._token:
            have_id = "You have the Driver ID" if self._driver_id else "The Driver ID is missing"
            have_tok = (
                "the driver token is still missing" if not self._token else "you have the token"
            )
            if not self._driver_id and not self._token:
                message = (
                    "Not ready yet. Both values are missing. Choose Paste "
                    "Driver ID from clipboard first."
                )
            elif not self._token:
                message = f"Not ready yet. {have_id}; {have_tok}. Choose Paste driver token from clipboard first."
            else:
                message = f"Not ready yet. {have_id}; {have_tok}. Choose Paste Driver ID from clipboard first."
            self.ctx.say(message, interrupt=True)
            return
        self._checking = True
        self._check_started = time.monotonic()
        self._still_checking_said = False
        self.refresh()
        self.ctx.say("Checking your credentials with orinks.net.", interrupt=True)
        identity = OnlineIdentity(driver_id=self._driver_id, driver_token=self._token)

        def worker() -> None:
            self._outcome = online_presence.verify_identity(identity)

        threading.Thread(target=worker, name="online-verify", daemon=True).start()

    def update(self, dt: float) -> None:
        super().update(dt)
        if (
            self._checking
            and not self._still_checking_said
            and time.monotonic() - self._check_started > 5.0
        ):
            self._still_checking_said = True
            self.ctx.say("Still checking.")
        outcome, self._outcome = self._outcome, None
        if outcome is None:
            return
        self._checking = False
        self.refresh()
        if outcome == "ok" and self._driver_id and self._token:
            identity = OnlineIdentity(driver_id=self._driver_id, driver_token=self._token)
            identity.save()
            self.ctx.settings.online_presence = True
            self.ctx.settings.save()
            self.ctx.adopt_online_identity(identity)
            self.ctx.apply_online_presence()
            self.ctx.audio.play("ui/menu_select")
            self.ctx.say(
                f"Connected. You are set up as {self._driver_id}. Sharing is "
                "on; you appear on the board while hauling.",
                interrupt=True,
            )
            self.ctx.pop_state()
            return
        if outcome == "driver_not_found":
            self.ctx.say(
                "Orinks does not know that Driver ID. Re-copy the Driver ID "
                "from the setup page and paste it again.",
                interrupt=True,
            )
        elif outcome == "unauthorized":
            self.ctx.say(
                "The token does not match. If you rotated the token on the "
                "site, copy the new one and paste it again.",
                interrupt=True,
            )
        elif outcome == "rejected":
            self.ctx.say(
                "orinks.net answered, but did not accept the pasted Driver ID "
                "and token. Re-copy each one from the setup page with its "
                "Copy button, paste them again, and try Connect once more. "
                "Nothing was saved.",
                interrupt=True,
            )
        else:
            self.ctx.say(
                "Could not reach orinks.net. Check your connection and try "
                "Connect again. Nothing was saved.",
                interrupt=True,
            )

    def go_back(self) -> None:
        if self._driver_id or self._token:
            self.ctx.say("Setup closed. Nothing was saved.")
        super().go_back()


def _updated_text(updated_at_ms: float) -> str:
    """A speakable freshness phrase from a server epoch-milliseconds stamp."""
    age_s = max(0.0, time.time() - updated_at_ms / 1000.0)
    if age_s < 90:
        return "updated just now"
    minutes = round(age_s / 60)
    return f"updated {minutes} minutes ago"


class DriversOnlineState(MenuState):
    """The live drivers board as a spoken list.

    Public data, so it works with or without the player's own sharing set
    up. The fetch happens on a daemon thread; until it lands the menu holds a
    single "checking" line.
    """

    title = "Drivers online"

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._board: list[dict] | None = None
        self._fetched = threading.Event()
        self._announced = False

    def enter(self) -> None:
        self._start_fetch()
        super().enter()

    def _start_fetch(self) -> None:
        self._board = None
        self._fetched.clear()
        self._announced = False

        def worker() -> None:
            self._board = online_presence.fetch_board()
            self._fetched.set()

        threading.Thread(target=worker, name="online-board", daemon=True).start()

    def build_items(self) -> list[MenuItem]:
        if not self._fetched.is_set():
            return [
                MenuItem("Checking the drivers board", self.speak_current),
                MenuItem("Back", self.go_back),
            ]
        board = self._board
        items: list[MenuItem] = []
        if board is None:
            items.append(
                MenuItem(
                    "The drivers board could not be reached",
                    self.speak_current,
                    help="orinks.net did not answer. Refresh to try again.",
                )
            )
        elif not board:
            items.append(MenuItem("No drivers are on duty right now", self.speak_current))
        else:
            for entry in board:
                name = entry.get("displayName", "A driver")
                bits = [name, entry.get("activity", "")]
                if entry.get("detail"):
                    bits.append(entry["detail"])
                bits.append(_updated_text(float(entry.get("updatedAt", 0))))
                label = ". ".join(bit for bit in bits if bit)
                items.append(MenuItem(label, self.speak_current))
        items.append(MenuItem("Refresh", self._refresh_board, help="Check the board again."))
        items.append(MenuItem("Back", self.go_back))
        return items

    def _refresh_board(self) -> None:
        self._start_fetch()
        self.refresh(keep_index=False)
        self.ctx.say("Checking the drivers board.")

    def update(self, dt: float) -> None:
        super().update(dt)
        if self._announced or not self._fetched.is_set():
            return
        self._announced = True
        self.refresh(keep_index=False)
        board = self._board
        if board is None:
            self.ctx.say("The drivers board could not be reached.", interrupt=True)
        elif not board:
            self.ctx.say("No drivers are on duty right now.", interrupt=True)
        else:
            count = f"{len(board)} driver" + ("s are" if len(board) != 1 else " is")
            self.ctx.say(f"{count} on duty. {self.current_text()}", interrupt=True)
