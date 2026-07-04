"""Optional Discord Rich Presence: broad, privacy-safe "now playing" status.

This module is the *only* place that knows about Discord or the ``pypresence``
RPC library. Gameplay code reports a small :class:`PresenceState` (two short,
player-facing strings) and never touches the socket, the dependency, or the
throttle logic.

Everything here is best-effort and non-fatal by design. If Discord is closed,
unavailable, disconnected mid-session, or the optional ``pypresence`` package is
missing, the game must still start, play, and exit exactly as before -- so every
RPC interaction runs on a background thread and is wrapped so no error ever
propagates into the game loop.

Privacy: presence shows broad activity only (menu, terminal, driving, resting,
delivering) plus high-level route and cargo context. It never includes save
file paths, the driver's chosen name, internal debug data, or anything that is
not already visible game content.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)

# Discord application id for the "Freight Fate" rich-presence app. Register an
# application at https://discord.com/developers/applications and set its id here
# or via the FREIGHT_FATE_DISCORD_APP_ID environment variable. The placeholder
# below lets the integration run end to end; with an unregistered id Discord
# simply refuses the handshake and presence stays hidden (handled gracefully).
DEFAULT_CLIENT_ID = "1519334426453082162"

# Discord truncates the details/state lines at 128 characters.
MAX_FIELD_LEN = 128

# Discord rate-limits presence updates (~5 per 20s). Coalesce changes and never
# push more than one update per this many seconds; identical states are dropped.
MIN_UPDATE_INTERVAL_S = 15.0

# How often the worker re-evaluates while idle (also flushes a throttled change).
_WORKER_TICK_S = MIN_UPDATE_INTERVAL_S

# Backoff between connection attempts when Discord is not running.
_RECONNECT_INTERVAL_S = 30.0


@dataclass(frozen=True)
class PresenceState:
    """A broad, player-facing activity snapshot reported by gameplay code.

    ``activity`` is the headline line (e.g. "Driving a route"); ``detail`` is an
    optional secondary line (e.g. "Chicago to Dallas, steel coils"). Both are
    plain prose with no private data. Equality drives de-duplication, so two
    identical snapshots never trigger a redundant Discord update.
    """

    activity: str
    detail: str = ""


def _truncate(text: str, limit: int = MAX_FIELD_LEN) -> str:
    text = " ".join(text.split())  # collapse whitespace; keep it tidy
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"  # ellipsis


def format_activity(state: PresenceState, *, start: float | None = None) -> dict:
    """Translate a :class:`PresenceState` into pypresence ``update`` kwargs.

    Pure and side-effect free so it is trivially testable. Empty fields are
    omitted so Discord does not render blank lines, and both visible lines are
    clamped to Discord's 128-character limit. ``start`` (an epoch timestamp)
    shows an elapsed-time counter for the whole session when provided.
    """
    payload: dict = {"details": _truncate(state.activity)}
    detail = _truncate(state.detail)
    if detail:
        payload["state"] = detail
    if start is not None:
        payload["start"] = int(start)
    return payload


def driving_presence(
    *,
    phase: str,
    origin: str,
    destination: str,
    cargo: str,
    fraction: float,
    moving: bool,
    truck_label: str = "",
) -> PresenceState:
    """Build a privacy-safe driving snapshot from broad gameplay values.

    Pure, so the route/cargo/progress wording is unit-testable without a live
    game. ``fraction`` is route progress in 0..1; it is rounded to the nearest
    five percent so a steadily advancing trip does not churn Discord updates.
    Only public game content (city names, cargo label, truck model) is used --
    never the driver name, save path, or internal state.
    """
    pct = max(0, min(100, round(max(0.0, min(1.0, fraction)) * 20) * 5))
    if phase == "pickup":
        activity = f"Deadheading to a pickup in {origin}" if origin else "Deadheading to a pickup"
        detail = f"Picking up {cargo}" if cargo else ""
        return PresenceState(activity, detail)
    verb = "Driving" if moving else "Stopped"
    if origin and destination:
        activity = f"{verb}: {origin} to {destination}"
    elif destination:
        activity = f"{verb} to {destination}"
    else:
        activity = f"{verb} a route"
    bits = []
    if cargo:
        bits.append(cargo)
    bits.append(f"{pct}% there")
    if truck_label:
        bits.append(truck_label)
    return PresenceState(activity, ", ".join(bits))


class _RpcClient(Protocol):
    """The slice of ``pypresence.Presence`` this module relies on."""

    def connect(self) -> object: ...
    def update(self, **kwargs: object) -> object: ...
    def clear(self) -> object: ...
    def close(self) -> object: ...


def pypresence_available() -> bool:
    """Whether the optional ``pypresence`` dependency can be imported."""
    try:
        import pypresence  # noqa: F401
    except Exception:
        return False
    return True


def _default_rpc_factory(client_id: str) -> _RpcClient:
    """Build a real pypresence client. Raises if the dependency is missing."""
    from pypresence import Presence

    return Presence(client_id)


RpcFactory = Callable[[str], _RpcClient]


def _teardown_rpc(rpc: object, *, send_close: bool) -> None:
    """Fully release a pypresence client, including its loop and pipe transport.

    ``pypresence``'s synchronous client builds a private asyncio event loop and
    (on Windows) a proactor pipe transport during the handshake, and does not
    always release them cleanly -- whether a connection is closed normally or the
    handshake itself fails (e.g. an unregistered app id rejected with InvalidID).
    Left dangling, the transport's finaliser later raises inside ``__del__`` and
    the loop leaks. To avoid that noisy, half-closed teardown we close the
    transport and then *pump the loop* so the disconnect actually completes
    before the loop is closed. Every step is best-effort and never raises.
    """
    loop = getattr(rpc, "loop", None)
    transport = getattr(rpc, "sock_writer", None)  # a proactor pipe transport
    if loop is None or loop.is_closed():
        # No asyncio loop to drain (a test double, or a never-connected client).
        if send_close:
            with contextlib.suppress(Exception):
                rpc.clear()  # type: ignore[attr-defined]
            with contextlib.suppress(Exception):
                rpc.close()  # type: ignore[attr-defined]
        return
    asyncio.set_event_loop(loop)
    try:
        if send_close:
            with contextlib.suppress(Exception):
                rpc.clear()  # type: ignore[attr-defined]
        if transport is not None:
            with contextlib.suppress(Exception):
                transport.close()
        # Let the proactor finish closing the pipe instead of yanking the loop.
        for _ in range(20):
            with contextlib.suppress(Exception):
                loop.run_until_complete(asyncio.sleep(0.01))
            if getattr(transport, "_sock", None) is None:
                break
        with contextlib.suppress(Exception):
            loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        with contextlib.suppress(Exception):
            loop.close()
        asyncio.set_event_loop(None)


class DiscordPresence:
    """Best-effort Discord Rich Presence service.

    Gameplay calls :meth:`update` with a :class:`PresenceState`; it returns
    immediately, never blocking the game loop. A daemon worker thread owns all
    socket I/O: it connects (retrying when Discord is closed), pushes the latest
    state subject to de-duplication and throttling, and reconnects if Discord
    goes away. :meth:`shutdown` clears the presence and joins the worker.

    The worker is optional (``threaded=False``) so tests can drive the exact
    same connect/throttle/send logic synchronously with an injected clock and a
    fake RPC client.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        client_id: str | None = None,
        min_interval_s: float = MIN_UPDATE_INTERVAL_S,
        clock: Callable[[], float] = time.monotonic,
        rpc_factory: RpcFactory | None = _default_rpc_factory,
        session_start: float | None = None,
        threaded: bool = True,
    ) -> None:
        if client_id is None:
            client_id = os.environ.get("FREIGHT_FATE_DISCORD_APP_ID", DEFAULT_CLIENT_ID)
        # The feature is only live when it is enabled *and* there is a way to
        # talk to Discord. A missing dependency simply leaves it dormant.
        self._available = rpc_factory is not None
        self._enabled = bool(enabled) and self._available
        self._client_id = client_id
        self._min_interval = max(0.0, float(min_interval_s))
        self._clock = clock
        self._rpc_factory = rpc_factory
        self._session_start = session_start if session_start is not None else time.time()
        self._threaded = threaded

        self._lock = threading.Lock()
        self._desired: PresenceState | None = None
        self._last_sent: PresenceState | None = None
        self._last_send_t: float | None = None
        self._rpc: _RpcClient | None = None
        self._last_connect_attempt: float | None = None

        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False

    # -- public API -----------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def connected(self) -> bool:
        return self._rpc is not None

    def start(self) -> None:
        """Begin presence after app initialisation. Safe to call when disabled."""
        if not self._enabled or self._started:
            return
        self._started = True
        self._stop.clear()
        if self._threaded:
            self._thread = threading.Thread(target=self._run, name="discord-presence", daemon=True)
            self._thread.start()
        else:
            self._pump()

    def update(self, state: PresenceState | None) -> None:
        """Report the latest broad activity. Non-blocking and dedup-aware."""
        if not self._enabled or state is None:
            return
        with self._lock:
            if state == self._desired:
                return  # nothing changed; skip even the wakeup
            self._desired = state
        if self._threaded:
            self._wake.set()
        else:
            self._pump()

    def shutdown(self) -> None:
        """Clear the presence and stop the worker. Never raises."""
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None
        self._close()
        self._started = False

    def set_enabled(self, enabled: bool) -> None:
        """Toggle presence at runtime (e.g. from the settings menu)."""
        enabled = bool(enabled) and self._available
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if enabled:
            # Re-show whatever the game last reported, reconnecting at once
            # rather than waiting out the idle backoff (this is a user action).
            with self._lock:
                self._last_sent = None
            self._last_connect_attempt = None
            self.start()
        else:
            was_started = self._started
            self._stop.set()
            self._wake.set()
            thread = self._thread
            if was_started and thread is not None and thread.is_alive():
                thread.join(timeout=2.0)
            self._thread = None
            self._close()
            self._started = False
            self._stop.clear()

    # -- worker / single-step logic ------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._pump()
            except Exception:  # pragma: no cover - defensive belt-and-braces
                log.debug("Discord presence pump failed", exc_info=True)
            self._wake.wait(self._worker_wait())
            self._wake.clear()

    def _worker_wait(self) -> float:
        """Seconds to sleep before the next pump.

        Short when a reported change is still waiting out the throttle window,
        otherwise a lazy heartbeat. Capped so a throttled update always flushes.
        """
        with self._lock:
            pending = self._desired is not None and self._desired != self._last_sent
        if pending and self._last_send_t is not None:
            remaining = self._min_interval - (self._clock() - self._last_send_t)
            if remaining > 0:
                return min(remaining, _WORKER_TICK_S)
        return _WORKER_TICK_S

    def _pump(self) -> None:
        """One connect-then-maybe-send cycle. Swallows all RPC errors."""
        if self._stop.is_set():
            return
        if not self._ensure_connected():
            return
        with self._lock:
            desired = self._desired
            last_sent = self._last_sent
        if desired is None or desired == last_sent:
            return  # nothing new to show (de-dupe)
        now = self._clock()
        if self._last_send_t is not None and now - self._last_send_t < self._min_interval:
            return  # throttled; the worker re-checks after the window closes
        try:
            self._rpc.update(  # type: ignore[union-attr]
                **format_activity(desired, start=self._session_start)
            )
        except Exception:
            log.debug("Discord presence update failed; will reconnect", exc_info=True)
            self._close()
            return
        with self._lock:
            self._last_sent = desired
        self._last_send_t = now

    def _ensure_connected(self) -> bool:
        if self._rpc is not None:
            return True
        if self._rpc_factory is None:
            return False
        now = self._clock()
        if (
            self._last_connect_attempt is not None
            and now - self._last_connect_attempt < _RECONNECT_INTERVAL_S
        ):
            return False  # back off; Discord is probably not running
        self._last_connect_attempt = now
        rpc = None
        try:
            rpc = self._rpc_factory(self._client_id)
            rpc.connect()
        except Exception:
            log.debug("Discord not available; presence stays hidden", exc_info=True)
            # A failed handshake can still leave pypresence's event loop and
            # sockets open; tear them down so nothing leaks (e.g. a wrong app id
            # rejected with InvalidID).
            if rpc is not None:
                _teardown_rpc(rpc, send_close=False)
            return False
        self._rpc = rpc
        return True

    def _close(self) -> None:
        rpc = self._rpc
        self._rpc = None
        self._last_send_t = None
        with self._lock:
            self._last_sent = None
        if rpc is None:
            return
        _teardown_rpc(rpc, send_close=True)
