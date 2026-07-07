"""Menus for the orinks.net drivers board: setup flow and the live list.

The setup flow follows docs on the site: the game generates a random driver
identity, registers a short-lived setup session, opens the confirmation page
in the player's browser, and waits until they pick a driver name and
visibility there. Nothing is shared until that confirmation, and the spoken
disclosure below tells the player exactly what will be sent.

All network calls run on daemon threads; the menu states poll a small result
slot from ``update`` so the game loop and speech stay responsive throughout.
"""

from __future__ import annotations

import threading
import time
import webbrowser

from .. import online_presence
from ..online_presence import OnlineIdentity
from .base import MenuItem, MenuState

DISCLOSURE = (
    "Sharing on the drivers board sends your in-game activity to orinks.net "
    "while you are hauling: what you are doing, your route's cities, your "
    "cargo, and rough progress. It appears under a driver name you choose in "
    "your browser, next. Nothing about you or your computer is sent: no real "
    "name, no location, no save files. You can turn this off any time in "
    "Settings, Online, and you disappear from the board within minutes."
)


class OnlineSetupState(MenuState):
    """Spoken disclosure, then browser confirmation, then a confirmed identity.

    Pushed from the settings menu when the player turns sharing on for the
    first time. On success it saves the credentials, flips the setting, and
    tells the running presence service to adopt them.
    """

    title = "Drivers board setup"

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._phase = "idle"  # idle -> waiting -> done/failed
        self._outcome: str | None = None  # worker -> update() mailbox
        self._identity: OnlineIdentity | None = None
        self._cancel = threading.Event()

    def build_items(self) -> list[MenuItem]:
        if self._phase == "waiting":
            return [
                MenuItem(
                    "Waiting for you to confirm in the browser",
                    self.speak_current,
                    help="Finish choosing a driver name on the page that just "
                    "opened, then confirm sharing there. This menu continues "
                    "automatically.",
                ),
                MenuItem("Cancel setup", self._cancel_setup, help="Stop and share nothing."),
            ]
        return [
            MenuItem(
                "Open the setup page in my browser",
                self._begin,
                help="Creates a random driver identity and opens orinks.net "
                "to confirm it. Sharing starts only after you confirm there.",
            ),
            MenuItem("Hear what gets shared", self._speak_disclosure),
            MenuItem("Cancel", self.go_back, help="Leave without turning sharing on."),
        ]

    def announce_entry(self) -> None:
        self.ctx.say(f"{self.title}. {DISCLOSURE} {self.current_text()}")

    def _speak_disclosure(self) -> None:
        self.ctx.say(DISCLOSURE)

    def _begin(self) -> None:
        if self._phase == "waiting":
            return
        self._phase = "waiting"
        self._cancel.clear()
        self.refresh(keep_index=False)
        self.ctx.say(
            "Opening the setup page in your browser. Choose a driver name "
            "and a visibility there, then confirm. I will keep waiting here."
        )
        threading.Thread(target=self._worker, name="online-setup", daemon=True).start()

    def _worker(self) -> None:
        """Register the session, open the browser, and poll for confirmation."""
        identity = OnlineIdentity.generate()
        setup_token = online_presence.new_setup_token()
        url = online_presence.begin_setup(identity, setup_token)
        if url is None:
            self._outcome = "unreachable"
            return
        try:
            webbrowser.open(url)
        except Exception:
            self._outcome = "unreachable"
            return
        deadline = time.monotonic() + online_presence.SETUP_TIMEOUT_S
        while not self._cancel.is_set() and time.monotonic() < deadline:
            status = online_presence.check_setup(setup_token)
            if status == "confirmed":
                self._identity = identity
                self._outcome = "confirmed"
                return
            if status == "expired":
                self._outcome = "expired"
                return
            self._cancel.wait(online_presence.SETUP_POLL_INTERVAL_S)
        if not self._cancel.is_set():
            self._outcome = "expired"

    def update(self, dt: float) -> None:
        super().update(dt)
        outcome, self._outcome = self._outcome, None
        if outcome is None:
            return
        if outcome == "confirmed" and self._identity is not None:
            self._identity.save()
            self.ctx.settings.online_presence = True
            self.ctx.settings.save()
            self.ctx.adopt_online_identity(self._identity)
            self.ctx.apply_online_presence()
            self.ctx.audio.play("ui/menu_select")
            self.ctx.say(
                "Sharing is on. You will appear on the drivers board while you are hauling a load.",
                interrupt=True,
            )
            self.ctx.pop_state()
            return
        self._phase = "idle"
        self.refresh(keep_index=False)
        if outcome == "unreachable":
            self.ctx.say(
                "The orinks.net setup page could not be reached. Sharing "
                "stays off. You can try again later.",
                interrupt=True,
            )
        else:
            self.ctx.say(
                "The setup was not confirmed, so sharing stays off. "
                "You can start it again any time.",
                interrupt=True,
            )

    def _cancel_setup(self) -> None:
        self._cancel.set()
        self._phase = "idle"
        self.ctx.say("Setup cancelled. Nothing was shared.")
        self.ctx.pop_state()

    def go_back(self) -> None:
        self._cancel.set()
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
