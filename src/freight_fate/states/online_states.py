"""Menus for the orinks.net drivers board: setup flow and the live list.

Setup uses the device-code activation flow (see ``online_activation.py``):
the game asks orinks.net for a short activation code, speaks it, and the
player enters that code in any browser on any device -- no clipboard paste
between the two apps. The game polls in the background and adopts the
resulting driver identity once the code is claimed. Nothing is transmitted
until a code is claimed, and the spoken disclosure below tells the player
exactly what sharing will send.

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

from .. import online_activation, online_presence
from ..online_presence import OnlineIdentity
from ..settings import PROFILE_SHARING_CONSENT_VERSION
from .base import MenuItem, MenuState

# Polling schedule for OnlineSetupState (module-level so tests can shrink
# them to make a real background thread finish fast, instead of monkeypatching
# time.sleep globally and risking every other timed test in the same run).
_ACTIVATION_POLL_INTERVAL_FIRST = 3.0
_ACTIVATION_POLL_INTERVAL_LATER = 8.0
_ACTIVATION_POLL_FIRST_PHASE_SECONDS = 30.0
_ACTIVATION_STILL_WAITING_AFTER = 5.0

DISCLOSURE = (
    "Profile sharing is optional and off until you turn it on. When on, orinks.net can "
    "publicly show your driver name and broad on-duty board activity; eligible profile "
    "details; official achievements you earn; and automatic road-journal posts "
    "generated from gameplay. Public updates can also appear in the Freight Fate updates "
    "feed. Each post also tells orinks.net which game version you are running, used only "
    "for moderation and troubleshooting and never shown publicly. Freight Fate does not "
    "publish your real name, full save, coordinates, active cargo details, or precise "
    "real-world location. Detailed career statistics come only from your latest accepted "
    "private backup and include lifetime career earnings, the running total your career "
    "has ever earned; the money you currently have is never published. Turning Profile "
    "sharing off hides public details but does not turn Cloud backup off."
)

# pygame.SCRAP_TEXT is the plain string "text/plain". Windows resolves that to
# its own text format, so one type is all Windows ever needs -- but on X11 a
# scrap type names the selection target the clipboard owner advertises, and
# pygame maps "text/plain;charset=utf-8" onto UTF8_STRING, which is what every
# desktop app and browser offers. SCRAP_TEXT reaches none of them: it reads
# back nothing and is refused outright on write, which is why Linux copies and
# pastes used to fall through to a Tk fallback that a stock Linux desktop does
# not even have installed. Windows keeps its own type first, untouched.
#
# The two types are not always the same encoding, and which one
# "text/plain;charset=utf-8" is depends on the platform underneath pygame.
# On X11 it is genuinely UTF8_STRING, the name pygame gives it above. On
# Windows (native or under Wine) the identical scrap-type string is instead
# remapped to CF_UNICODETEXT, which answers in UTF-16LE regardless of the
# "utf-8" in its name -- pygame relabeled the type, it did not translate the
# bytes. Decoding both as UTF-8 happens to look right on native Windows only
# because CF_TEXT (SCRAP_TEXT) answers first and CF_UNICODETEXT is never
# reached; under Wine, an X11 owner that advertises only UTF8_STRING can
# leave CF_TEXT empty, so CF_UNICODETEXT's bytes reach the UTF-8 decoder and
# every non-ASCII character silently disappears. Each scrap type gets the
# encoding that platform actually answers in.
#
# SCRAP_TEXT is resolved once here, at import time, rather than read off
# pygame.SCRAP_TEXT inside the function below -- tests substitute the whole
# online_states.pygame name with a bare namespace that carries only .scrap,
# and this constant must survive that substitution unharmed.
_SCRAP_TEXT = pygame.SCRAP_TEXT


def _scrap_text_types() -> tuple[tuple[str, str], ...]:
    plain_encoding = "utf-16-le" if sys.platform == "win32" else "utf-8"
    return (
        (_SCRAP_TEXT, "utf-8"),
        ("text/plain;charset=utf-8", plain_encoding),
    )


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
            for scrap_type, encoding in _scrap_text_types():
                raw = scrap.get(scrap_type)
                if raw:
                    if encoding == "utf-16-le" and raw[-2:] == b"\x00\x00":
                        raw = raw[:-2]  # Windows NUL-terminates CF_UNICODETEXT
                    return _clean_clip(raw.decode(encoding, "ignore"))
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


def _clipboard_write_once(text: str) -> bool:
    """One clipboard write attempt. Same ladder as reading: scrap first,
    pbcopy on macOS (never Tk there -- see _clipboard_once), Tk elsewhere."""
    try:
        scrap = pygame.scrap
        if hasattr(scrap, "put_text"):  # pygame-ce >= 2.2
            scrap.put_text(text)
            return True
        if not scrap.get_init():
            scrap.init()  # needs the display up; raises when called early
        data = text.encode("utf-8")
        for scrap_type, _encoding in _scrap_text_types():
            try:
                scrap.put(scrap_type, data)
                return True
            except Exception:
                continue  # X11 refuses the types its clipboard does not carry
    except Exception:
        pass
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["pbcopy"], input=text.encode("utf-8"), timeout=2.0, check=False
            )
            return result.returncode == 0
        except Exception:
            return False
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        try:
            root.clipboard_clear()
            root.clipboard_append(text)
            # Flush ownership to the OS clipboard before the root dies, or
            # Windows hands out an empty clipboard to the next reader.
            root.update()
        finally:
            root.destroy()
        return True
    except Exception:
        return False


def _clipboard_holds(expected: str) -> bool:
    """Read back and compare, forgiving the CRLF conversion Windows applies."""
    read = _clipboard_once()
    if read is None:
        return False
    return read.replace("\r\n", "\n").strip() == expected.replace("\r\n", "\n").strip()


def write_clipboard_text(text: str) -> bool:
    """Clipboard write, verified by reading back before anyone says "copied".

    The verify pass is not paranoia: a Tk-set clipboard dies with its root on
    X11, and scrap.put can claim success on a clipboard another app holds
    open. Retries once, like reading, for that same contended-clipboard case.
    """
    if _clipboard_write_once(text) and _clipboard_holds(text):
        return True
    time.sleep(0.1)
    return _clipboard_write_once(text) and _clipboard_holds(text)


class OnlineSetupState(MenuState):
    """Request and track an orinks.net activation code for this computer.

    The menu is deliberately STATIC — the same five items for the
    whole flow, with labels that carry the captured state — because players
    build positional memory of spoken menus and refresh() preserves indices,
    not item identity. Only item 1's label carries progress; items 2-5 are
    fixed text.

    The game has no screen reader review cursor — a player cannot step
    through a spoken string character by character the way they can in a
    browser or an editor — so items 2 and 3 exist purely to let a player
    replay the activation code as many times as they need: item 2 spells it
    phonetically, item 3 puts it on the clipboard (a write, the direction
    that still works even when the game and the player's browser do not
    share a clipboard). Both stay available for as long as an activation is
    outstanding, and both double as the fallback path for when
    ``webbrowser.open`` does nothing. On success the identity is saved while
    Profile sharing and Cloud backup remain off.
    """

    title = "orinks.net account setup"

    def __init__(self, ctx, *, autostart: bool = False) -> None:
        super().__init__(ctx)
        self.activation: online_activation.Activation | None = None
        self._phase = "idle"  # idle | starting | waiting | expired | error
        self._poll_started = 0.0
        self._still_waiting_said = False
        self._outcome: tuple[str, object] | None = None  # worker -> update() mailbox
        # A fresh Event per run, replaced in _start_setup: exit() must always
        # have *something* to .set(), even if the player never starts setup.
        self._stop_event = threading.Event()
        # Set when this state is pushed straight from the offer's "Set up
        # now" answer: the player already said yes, so entry starts the
        # request itself instead of making them choose the first menu item
        # to confirm a decision they already made. Public so callers (and
        # tests) can see whether a given push will autostart.
        self.autostart = autostart

    # -- static menu ----------------------------------------------------------

    def enter(self) -> None:
        super().enter()
        if self.autostart:
            self._start_setup()

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                self._setup_label,
                self._start_setup,
                help="Asks orinks.net for an activation code, tries to open "
                "your browser with it filled in, and waits for you to sign "
                "in there.",
            ),
            MenuItem(
                "Say my activation code again",
                self._repeat_code,
                help="Spells out the activation code letter by letter, so "
                "you can copy it by ear as many times as you need.",
            ),
            MenuItem(
                "Copy my activation code",
                self._copy_code,
                help="Puts the activation code on the clipboard, for when "
                "the browser did not open on its own.",
            ),
            MenuItem("Hear what gets shared", self._speak_disclosure),
            MenuItem("Cancel", self.go_back, help="Leave without connecting this account."),
        ]

    def _setup_label(self) -> str:
        if self._phase == "starting":
            return "Starting setup with orinks.net"
        if self._phase == "waiting" and self.activation is not None:
            return f"Waiting for code {self.activation.user_code} to be entered"
        if self._phase == "expired":
            return "Activation code expired — choose to get a new one"
        if self._phase == "error":
            return "Setup could not continue — choose to start over"
        return "Set up this computer with orinks.net"

    def announce_entry(self) -> None:
        if self.autostart:
            # The player already said "Set up now" on the offer -- hearing
            # this five-item menu introduced, only to have _start_setup talk
            # over it a moment later with "Contacting orinks.net...", reads
            # as the game losing its place. Say nothing here; _start_setup
            # (called right after enter() finishes) speaks first instead.
            return
        self.ctx.say(
            f"{self.title}. This connects the game to your orinks.net account. "
            "Profile sharing and Cloud backup remain off until you turn each "
            "one on separately. The first item asks orinks.net for an "
            f"activation code. {self.current_text()}"
        )

    def _speak_disclosure(self) -> None:
        self.ctx.say(DISCLOSURE)

    def handle_event(self, event) -> None:
        # Re-orient after the browser round trip: this flow is a two-app
        # dance, and "where was I" is the first question on every return.
        if event.type == pygame.WINDOWFOCUSGAINED and self._phase == "waiting":
            self.ctx.say(f"Back in Freight Fate. {self.current_text()}")
            return
        super().handle_event(event)

    # -- starting -------------------------------------------------------------

    def _start_setup(self) -> None:
        if self._phase in ("starting", "waiting"):
            # Already under way -- repeat the code rather than burning a
            # second activation request the player did not ask for.
            if self.activation is not None:
                self.ctx.say(
                    "Still waiting for you to enter the code. Your "
                    f"activation code is {self.activation.user_code}.",
                    interrupt=True,
                )
            else:
                # Phase "starting": the request is in flight and there is no
                # code to repeat yet. Returning in silence here would read as
                # "did that keypress even register" -- this game has no visual
                # fallback to check against.
                self.ctx.say(
                    "Still contacting orinks.net for an activation code.",
                    interrupt=True,
                )
            return
        self._phase = "starting"
        self.activation = None
        self._still_waiting_said = False
        self.refresh()
        self.ctx.say("Contacting orinks.net for an activation code.", interrupt=True)
        self._stop_event = threading.Event()
        stop_event = self._stop_event

        def worker() -> None:
            activation = online_activation.start_activation()
            if stop_event.is_set():  # player already backed out
                return
            if activation is None:
                self._outcome = ("start_failed", None)
                return
            self._outcome = ("activation", activation)
            self._poll_loop(activation, stop_event)

        threading.Thread(target=worker, name="online-activation", daemon=True).start()

    def _poll_loop(
        self, activation: online_activation.Activation, stop_event: threading.Event
    ) -> None:
        """Poll until claimed, expired, told to stop, or terminally rejected.

        Runs entirely on the worker thread. Every reachable exit posts to
        ``self._outcome`` -- except "keep waiting", which posts nothing:
        update() times the "still waiting" line off ``self._poll_started``,
        not off a worker message, so a silent pending poll needs no mailbox
        entry at all. "retry" (a transient network blip or 5xx -- see
        ``online_activation.poll_activation``) is folded into "keep waiting"
        too: the whole point of splitting it from "error" is that a dropped
        connection three seconds from now should not force the player back
        through a fresh activation code.
        """
        first_phase_deadline = time.monotonic() + _ACTIVATION_POLL_FIRST_PHASE_SECONDS
        while not stop_event.is_set():
            if time.time() >= activation.expires_at:
                self._outcome = ("expired", None)
                return
            result = online_activation.poll_activation(activation)
            if stop_event.is_set():  # player backed out while the request was in flight
                return
            if result.status == "ready":
                self._outcome = ("ready", result)
                return
            if result.status == "expired":
                self._outcome = ("expired", None)
                return
            if result.status == "error":
                self._outcome = ("error", None)
                return
            # "pending" and "retry" both fall through here: nothing to post,
            # just wait out the interval and poll again.
            interval = (
                _ACTIVATION_POLL_INTERVAL_FIRST
                if time.monotonic() < first_phase_deadline
                else _ACTIVATION_POLL_INTERVAL_LATER
            )
            if stop_event.wait(interval):  # True means stop was requested during the wait
                return

    def _announce_activation(self, activation: online_activation.Activation) -> None:
        code = activation.user_code
        try:
            webbrowser.open(activation.verification_uri_complete)
            opened = True
        except Exception:
            opened = False
        if opened:
            self.ctx.say(
                f"Your activation code is {code}. I opened your browser to "
                f"{activation.verification_uri} with the code filled in. "
                "Sign in there to finish setup.",
                interrupt=True,
            )
        else:
            # webbrowser.open() can also silently do nothing without raising
            # (a remote/streamed session is the common case) -- items 2 and 3
            # are the fallback for that case too, not only this one, but this
            # is the one moment the game knows for certain that opening
            # failed, so it is worth naming them here.
            self.ctx.say(
                "The browser could not be opened. Your activation code is "
                f"{code}. In any browser, go to {activation.verification_uri} "
                "and enter it. Choose Say my activation code again to hear "
                "it spelled out, or Copy my activation code to put it on "
                "the clipboard.",
                interrupt=True,
            )

    # -- review affordances -----------------------------------------------------

    def _repeat_code(self) -> None:
        if self.activation is None:
            self.ctx.say(
                "There is no activation code right now. Choose Set up this "
                "computer with orinks.net first.",
                interrupt=True,
            )
            return
        self.ctx.say(
            "Your activation code, spelled out: "
            f"{online_activation.spell_code(self.activation.user_code)}.",
            interrupt=True,
        )

    def _copy_code(self) -> None:
        if self.activation is None:
            self.ctx.say(
                "There is no activation code right now. Choose Set up this "
                "computer with orinks.net first.",
                interrupt=True,
            )
            return
        # Never claim a copy that failed -- the write is verified (see
        # write_clipboard_text) before this ever says "copied".
        if write_clipboard_text(self.activation.user_code):
            self.ctx.say("Activation code copied to the clipboard.", interrupt=True)
        else:
            self.ctx.say(
                "I could not copy the activation code to the clipboard. "
                "Choose Say my activation code again to hear it spelled "
                "out instead.",
                interrupt=True,
            )

    # -- polling result -----------------------------------------------------------

    def update(self, dt: float) -> None:
        super().update(dt)
        if (
            self._phase == "waiting"
            and not self._still_waiting_said
            and time.monotonic() - self._poll_started > _ACTIVATION_STILL_WAITING_AFTER
        ):
            self._still_waiting_said = True
            # interrupt=False, deliberately: this fires five seconds after the
            # activation announcement *starts*, and the browser-failed variant
            # of that announcement (code, address, and both fallback menu
            # items) takes far longer than five seconds to speak. Interrupting
            # would cut a player off mid-address on exactly the path -- a
            # remote or streamed session where the browser never opens --
            # where the spoken address is the only way to finish setup.
            self.ctx.say("Still waiting.", interrupt=False)
        outcome, self._outcome = self._outcome, None
        if outcome is None:
            return
        kind, payload = outcome
        if kind == "start_failed":
            self._phase = "idle"
            self.refresh()
            self.ctx.say("Could not reach orinks.net. Try again.", interrupt=True)
            return
        if kind == "activation":
            self.activation = payload
            self._phase = "waiting"
            self._still_waiting_said = False
            self.refresh()
            self._announce_activation(payload)
            # Clock starts *after* the announcement is queued, not before, so
            # _ACTIVATION_STILL_WAITING_AFTER measures five seconds of actual
            # waiting rather than five seconds of the announcement still
            # being spoken.
            self._poll_started = time.monotonic()
            return
        if kind == "ready":
            self._finish_success(payload)
            return
        if kind == "expired":
            self.activation = None
            self._phase = "expired"
            self.refresh()
            self.ctx.say(
                "Your activation code expired. Choose Set up this computer "
                "with orinks.net again for a new code.",
                interrupt=True,
            )
            return
        if kind == "error":
            self.activation = None
            self._phase = "error"
            self.refresh()
            # A 400 here means the stored device_code is malformed, so the
            # only fix is a fresh code. Heard aloud, saying "trying again
            # will not fix it" and then naming a menu item to choose again
            # reads as a contradiction -- the two halves have to agree, so
            # this names the fresh code as the fix and leaves it there.
            self.ctx.say(
                "That activation code cannot be used. Choose Set up this "
                "computer with orinks.net for a fresh code.",
                interrupt=True,
            )
            return

    def _finish_success(self, result: online_activation.PollResult) -> None:
        self.activation = None
        self._phase = "idle"
        self.refresh()
        identity = OnlineIdentity(driver_id=result.driver_id, driver_token=result.token)
        try:
            identity.save()
        except OSError:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                "Your activation code was accepted, but this computer could "
                "not save the driver token securely. Nothing was changed. "
                "Check that your password store is available, then choose "
                "Set up this computer with orinks.net to try again.",
                interrupt=True,
            )
            return
        self.ctx.settings.online_presence = False
        self.ctx.settings.cloud_saves = False
        self.ctx.settings.profile_sharing_consent_version = 0
        self.ctx.settings.profile_sharing_pending_off = False
        self.ctx.settings.save()
        self.ctx.adopt_online_identity(identity)
        self.ctx.apply_online_presence()
        self.ctx.apply_cloud_saves()
        self.ctx.audio.play("ui/menu_select")
        # The display name is not decoration: it is the only way a player
        # finds out someone else claimed the code they spoke or copied, and
        # that the token just saved belongs to a stranger's driver, not theirs.
        display = result.display_name or "your driver"
        self.ctx.say(
            f"Connected to orinks.net as {display}. Profile sharing remains "
            "off. Cloud backup remains off until you turn it on.",
            interrupt=True,
        )
        self.ctx.pop_state()

    def go_back(self) -> None:
        # "starting" included, not just "waiting": a player who backs out
        # while the game is still contacting orinks.net for a code gets the
        # same confirmation as one who backs out mid-poll, rather than just
        # the generic menu-back sound and no word on what happened.
        if self._phase in ("starting", "waiting"):
            self.ctx.say("Setup canceled. Nothing was saved.")
        super().go_back()

    def exit(self) -> None:
        # Stops the poll worker no matter how this state is left (Cancel,
        # Escape, or a programmatic pop elsewhere) -- backing out must never
        # leave a thread polling into a dead state.
        self._stop_event.set()
        super().exit()


class ProfileSharingSyncState(MenuState):
    """Synchronize Profile sharing without blocking the game loop."""

    title = "Profile sharing"

    def __init__(self, ctx, enabled: bool) -> None:
        super().__init__(ctx)
        self.enabled = enabled
        self._pending = False
        self._outcome: str | None = None

    def build_items(self) -> list[MenuItem]:
        action = f"Turn Profile sharing {'on' if self.enabled else 'off'}"
        if self._pending:
            action = f"Turning Profile sharing {'on' if self.enabled else 'off'}"
        return [
            MenuItem(action, self._start),
            MenuItem("Hear what gets shared", lambda: self.ctx.say(DISCLOSURE, interrupt=True)),
            MenuItem("Cancel", self.go_back),
        ]

    def _start(self) -> None:
        if self._pending:
            return
        identity = OnlineIdentity.load()
        if identity is None:
            self.ctx.push_state(OnlineSetupState(self.ctx))
            return
        self._pending = True
        if not self.enabled:
            self.ctx.settings.profile_sharing_pending_off = True
            self.ctx.settings.save()
            self.ctx.apply_online_presence()
        self.refresh()
        self.ctx.say(
            "Turning Profile sharing on."
            if self.enabled
            else "Turning Profile sharing off. Local posting has stopped; public information may remain visible until orinks.net confirms the change.",
            interrupt=True,
        )

        def worker() -> None:
            self._outcome = online_presence.set_profile_sharing(identity, self.enabled)

        threading.Thread(target=worker, name="profile-sharing", daemon=True).start()

    def update(self, dt: float) -> None:
        super().update(dt)
        outcome, self._outcome = self._outcome, None
        if outcome is None:
            return
        self._pending = False
        if outcome == "ok":
            self.ctx.settings.online_presence = self.enabled
            if self.enabled:
                self.ctx.settings.profile_sharing_consent_version = PROFILE_SHARING_CONSENT_VERSION
            self.ctx.settings.profile_sharing_pending_off = False
            self.ctx.settings.save()
            self.ctx.apply_online_presence()
            self.ctx.say(
                "Profile sharing is on. Eligible driver information and gameplay updates can now appear publicly on orinks.net."
                if self.enabled
                else "Profile sharing is off. Posting has stopped and your Freight Fate profile and activity are no longer public.",
                interrupt=True,
            )
            self.ctx.pop_state()
            return
        self.refresh()
        self.ctx.say(
            "Profile sharing is still off. orinks.net could not confirm the change. Try again."
            if self.enabled
            else "Profile sharing may still be public. Local posting is stopped, but orinks.net could not confirm the request. Choose Turn Profile sharing off to retry.",
            interrupt=True,
        )

    def go_back(self) -> None:
        if self._pending:
            self.ctx.say(
                "Profile sharing is still updating. Stay here for the result.", interrupt=True
            )
            return
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


class MastodonLinkState(MenuState):
    """Link the player's own Mastodon account through orinks.net.

    The authorizing happens in the browser: the site is signed in with the
    same orinks.net account as driver setup, so this menu only opens the
    page and reports the server's word on the link. Unlinking lives on the
    same page. The menu is STATIC for the same positional-memory reason as
    OnlineSetupState; state rides in the labels.
    """

    title = "Mastodon account"

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._checking = False
        self._check_started = 0.0
        self._still_checking_said = False
        self._outcome: dict | str | None = None  # worker -> update() mailbox
        self._opened_browser = False

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "Open the Mastodon link page in my browser",
                self._open_page,
                help="Sign in on orinks.net if asked, enter your Mastodon "
                "server, and authorize Freight Fate there. Then come back "
                "here and check the link status.",
            ),
            MenuItem(
                self._status_label,
                self._check_status,
                help="Asks orinks.net whether a Mastodon account is linked to your driver.",
            ),
            MenuItem("Back", self.go_back),
        ]

    def _status_label(self) -> str:
        if self._checking:
            return "Checking the Mastodon link"
        s = self.ctx.settings
        if s.mastodon_linked:
            spoken = f" as {s.mastodon_linked_handle}" if s.mastodon_linked_handle else ""
            return f"Check link status. Last known: linked{spoken}"
        return "Check link status"

    def announce_entry(self) -> None:
        s = self.ctx.settings
        if s.mastodon_linked:
            spoken = s.mastodon_linked_handle or "a Mastodon account"
            known = f"Last I checked, {spoken} was linked."
        else:
            known = "No Mastodon account is linked yet, as far as this computer knows."
        self.ctx.say(
            f"{self.title}. Linking happens in your browser on orinks.net, "
            f"using the same sign-in as driver setup. {known} "
            f"{self.current_text()}"
        )

    def _open_page(self) -> None:
        url = f"{online_presence.base_url()}/freight-fate/online/mastodon"
        copied = write_clipboard_text(url)
        try:
            webbrowser.open(url)
        except Exception:
            if copied:
                self.ctx.say(
                    "The browser could not be opened. The link is on your "
                    "clipboard. Paste it into your browser's address bar.",
                    interrupt=True,
                )
            else:
                self.ctx.say(
                    "The browser could not be opened and the clipboard did "
                    "not take the link. In your browser, go to orinks.net, "
                    "then Freight Fate, then Online, then Mastodon.",
                    interrupt=True,
                )
            # The player may still get there by hand; keep the return
            # re-orientation armed either way.
            self._opened_browser = True
            return
        self._opened_browser = True
        clipboard_note = (
            " The link is also on your clipboard in case the browser did not open."
            if copied
            else ""
        )
        self.ctx.say(
            "Opening the Mastodon link page in your browser."
            + clipboard_note
            + " Authorize there, then come back here.",
            interrupt=True,
        )

    def handle_event(self, event) -> None:
        # Re-orient after the browser round trip, and answer "did it take"
        # without hunting: check the link the moment focus comes back.
        if event.type == pygame.WINDOWFOCUSGAINED and self._opened_browser and not self._checking:
            self.ctx.say("Back in Freight Fate. Checking your Mastodon link.")
            self._check_status(announce=False)
            return
        super().handle_event(event)

    def _check_status(self, announce: bool = True) -> None:
        if self._checking:
            return
        identity = OnlineIdentity.load()
        if identity is None:
            self.ctx.say(
                "This needs your orinks.net account first. Choose Set up "
                "orinks.net account on the Online menu.",
                interrupt=True,
            )
            return
        self._checking = True
        self._check_started = time.monotonic()
        self._still_checking_said = False
        self.refresh()
        if announce:
            self.ctx.say("Checking with orinks.net.", interrupt=True)

        def worker() -> None:
            self._outcome = online_presence.fetch_mastodon_status(identity) or "error"

        threading.Thread(target=worker, name="mastodon-status", daemon=True).start()

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
        if outcome == "error":
            self.refresh()
            self.ctx.say(
                "I could not reach orinks.net to check the Mastodon link. Try again in a moment.",
                interrupt=True,
            )
            return
        s = self.ctx.settings
        linked = bool(outcome.get("linked"))
        s.mastodon_linked = linked
        s.mastodon_linked_handle = str(outcome.get("handle") or "") if linked else ""
        s.save()
        self.refresh()
        if linked:
            spoken = s.mastodon_linked_handle or "your Mastodon account"
            self.ctx.say(
                f"Linked: {spoken}. You can now turn on Share notable "
                "deliveries to Mastodon on the Online menu.",
                interrupt=True,
            )
        else:
            self.ctx.say(
                "No Mastodon account is linked yet. Open the link page in "
                "your browser, authorize there, then check again.",
                interrupt=True,
            )
