"""Optional online presence: an opt-in "on duty" heartbeat to orinks.net.

This module is the *only* place that knows about the Orinks presence API.
Gameplay code reports the same broad :class:`PresenceState` snapshots it
already builds for Discord Rich Presence; this service posts the latest one
to the live drivers board while the player is hauling, and clears it when
they stop. The board then shows lines like "Road Star -- Driving: Chicago to
Dallas -- steel coils, 45% there".

Everything here is best-effort and non-fatal by design, mirroring
:mod:`freight_fate.discord_presence`: if the player is offline, the site is
down, or the feature is disabled, the game plays exactly as before. All
network I/O runs on a background thread and no error ever propagates into
the game loop.

Privacy: the feature is off by default and only ever sends the broad
activity strings above, authenticated by account-issued credentials the
player copies from the Orinks driver setup page and pastes into the game
once (see :func:`verify_identity`). The driver's display name lives on the
site, tied to their Orinks account; the game never transmits profile names,
save data, or anything about the real player. Every request's User-Agent
does carry the game's build identity (see :func:`client_version`) so the
site can tell which release a post came from -- moderation and bug triage
data, never shown publicly.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from .discord_presence import PresenceState
from .net import ssl_context

log = logging.getLogger(__name__)

# The www host, deliberately: the apex orinks.net answers API calls with a
# 307 redirect to www, and urllib will not re-send a POST body through a
# redirect -- so heartbeats against the apex fail with HTTPError 307.
DEFAULT_BASE_URL = "https://www.orinks.net"

# Presence is by far the biggest source of backend reads and writes -- a
# driver on a long haul beats for hours, and it is the single largest line in
# the site's database usage -- so beat every two and a half minutes. The board
# drops a driver six minutes after their last beat, which still absorbs one
# dropped request before anyone is called gone; keep this and PRESENCE_TTL_MS
# on the server in step, and widen the server's window first, or a single lost
# beat will blink a driver off the board.
#
# Only the keep-alive slows down. A change of activity still pushes within
# MIN_CHANGE_INTERVAL_S, so going on duty, pulling over, or starting a new leg
# still reaches the board in seconds.
HEARTBEAT_INTERVAL_S = 150.0

# When the activity changes (new leg, pulled over, back on the road), push
# the update sooner than the next heartbeat -- but never more often than this.
MIN_CHANGE_INTERVAL_S = 15.0

# A None snapshot must persist this long before the sign-off is sent. The
# hauling states report through brief sub-menus unevenly, and this grace
# stops a two-second detour (a status screen, a confirmation prompt) from
# bouncing the driver off and back onto the public board.
OFF_DUTY_GRACE_S = 20.0

_REQUEST_TIMEOUT_S = 10.0
_WORKER_TICK_S = HEARTBEAT_INTERVAL_S


def base_url() -> str:
    """The Orinks site root, overridable for development and tests."""
    return os.environ.get("FREIGHT_FATE_ONLINE_URL", DEFAULT_BASE_URL).rstrip("/")


def client_version() -> str:
    """The build identity this game reports with every Orinks request.

    Packaged builds report their release tag (``v1.8.0``, or
    ``nightly-20260711`` on the dev channel); a source checkout, which has no
    build stamp, reports ``source-<version>``. The site records the latest
    value per driver so moderation can tell which build a suspicious profile
    or save came from. It says nothing about the player or the machine.
    """
    from . import __version__, updater

    build = updater.load_build_info(__version__)
    tag = build.tag if build is not None else f"source-{__version__}"
    # User-Agent product tokens must stay printable and space-free; version
    # strings already are, but a malformed pyproject fallback must not be
    # able to break every request header.
    return "".join(c for c in tag if "!" <= c <= "~")[:64] or "unknown"


# A transport posts (or gets, when payload is None) JSON and returns the
# decoded JSON reply. Injected in tests; the default uses urllib with the
# shared verified TLS context.
Transport = Callable[[str, dict | None, dict[str, str]], dict]


def _http_json(url: str, payload: dict | None, headers: dict[str, str]) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    all_headers = {
        "User-Agent": f"FreightFate/{client_version()}",
        "Content-Type": "application/json",
        **headers,
    }
    req = urllib.request.Request(url, data=data, headers=all_headers)
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_S, context=ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


# -- driver identity ----------------------------------------------------------


@dataclass
class OnlineIdentity:
    """Account-issued credentials for posting presence.

    Both values come from the Orinks driver setup page after the player
    signs in there: ``driver_id`` is public (it names the profile page on
    Orinks); ``driver_token`` is the posting secret, shown once at issuance,
    and never leaves this machine except inside authenticated requests.
    """

    driver_id: str
    driver_token: str

    @staticmethod
    def path():
        from .models.profile import data_dir

        return data_dir() / "online.json"

    def save(self) -> None:
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"driver_id": self.driver_id, "driver_token": self.driver_token}, f, indent=2)
        tmp.replace(path)

    @classmethod
    def load(cls) -> OnlineIdentity | None:
        try:
            with open(cls.path(), encoding="utf-8") as f:
                data = json.load(f)
            driver_id = data["driver_id"]
            driver_token = data["driver_token"]
        except (FileNotFoundError, KeyError, json.JSONDecodeError, OSError, TypeError):
            return None
        if not isinstance(driver_id, str) or not isinstance(driver_token, str):
            return None
        if len(driver_id) < 8 or len(driver_token) < 24:
            return None
        return cls(driver_id=driver_id, driver_token=driver_token)


def verify_identity(identity: OnlineIdentity, *, transport: Transport = _http_json) -> str:
    """Check pasted credentials against Orinks without going on duty.

    Posts one empty-activity presence request -- the server treats that as an
    off-duty sign-off, so a valid pair changes nothing visible. Returns one
    of ``"ok"``, ``"driver_not_found"`` (the Driver ID is wrong),
    ``"unauthorized"`` (the token is wrong or was rotated), ``"rejected"``
    (the server answered but refused the credentials for another reason,
    e.g. a malformed paste), or ``"error"`` (network trouble; nothing
    learned).
    """
    try:
        reply = transport(
            f"{base_url()}/api/freight-fate/presence",
            {"driverId": identity.driver_id, "activity": "", "detail": ""},
            {"Authorization": f"Bearer {identity.driver_token}"},
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "driver_not_found"
        if e.code == 401:
            return "unauthorized"
        # Keep the server's own explanation (Convex sends a JSON error body)
        # so a player-attached log tells us *why* a paste was refused.
        try:
            body = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            body = ""
        log.warning("Online identity check failed: HTTP %s %s", e.code, body)
        if 400 <= e.code < 500:
            return "rejected"
        return "error"
    except Exception as e:
        log.warning("Online identity check failed: %s", e)
        return "error"
    return "ok" if reply.get("ok") else "error"


def set_profile_sharing(
    identity: OnlineIdentity, enabled: bool, *, transport: Transport = _http_json
) -> str:
    """Set the authoritative public Profile-sharing state on orinks.net."""
    try:
        reply = transport(
            f"{base_url()}/api/freight-fate/profile-sharing",
            {"driverId": identity.driver_id, "enabled": enabled},
            {"Authorization": f"Bearer {identity.driver_token}"},
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "driver_not_found"
        if e.code == 401:
            return "unauthorized"
        log.warning("Profile sharing update failed: HTTP %s", e.code)
        return "error"
    except Exception as e:
        log.warning("Profile sharing update failed: %s", e)
        return "error"
    return "ok" if reply.get("ok") and reply.get("enabled") is enabled else "error"


# -- presence service ---------------------------------------------------------


class OnlinePresence:
    """Best-effort heartbeat sender for the live drivers board.

    Gameplay calls :meth:`update` with the active state's on-duty
    :class:`PresenceState` (or None when the player is not hauling); it
    returns immediately. A daemon worker owns all HTTP: it posts a heartbeat
    every :data:`HEARTBEAT_INTERVAL_S`, pushes activity changes sooner
    (throttled), and posts one empty-activity request to leave the board when
    the player goes off duty. :meth:`shutdown` sends that sign-off too.

    The worker is optional (``threaded=False``) so tests can drive the exact
    same schedule/send logic synchronously with an injected clock and
    transport.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        identity: OnlineIdentity | None = None,
        heartbeat_s: float = HEARTBEAT_INTERVAL_S,
        min_change_s: float = MIN_CHANGE_INTERVAL_S,
        off_duty_grace_s: float = OFF_DUTY_GRACE_S,
        clock: Callable[[], float] = time.monotonic,
        transport: Transport = _http_json,
        threaded: bool = True,
    ) -> None:
        self._identity = identity
        self._enabled = bool(enabled) and identity is not None
        self._heartbeat = max(1.0, float(heartbeat_s))
        self._min_change = max(0.0, float(min_change_s))
        self._off_duty_grace = max(0.0, float(off_duty_grace_s))
        self._none_since: float | None = None
        self._clock = clock
        self._transport = transport
        self._threaded = threaded

        self._lock = threading.Lock()
        self._desired: PresenceState | None = None
        self._last_sent: PresenceState | None = None
        self._last_send_t: float | None = None
        self._on_board = False  # the server currently lists this driver

        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False

    # -- public API -----------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_identity(self, identity: OnlineIdentity | None) -> None:
        """Adopt freshly confirmed credentials (from the setup flow)."""
        self._identity = identity
        if identity is None:
            self.set_enabled(False)

    def start(self) -> None:
        """Begin the worker after app initialisation. Safe when disabled."""
        if not self._enabled or self._started:
            return
        self._started = True
        self._stop.clear()
        if self._threaded:
            self._thread = threading.Thread(target=self._run, name="online-presence", daemon=True)
            self._thread.start()
        else:
            self._pump()

    def update(self, state: PresenceState | None) -> None:
        """Report the latest on-duty snapshot; None means off duty."""
        if not self._enabled:
            return
        with self._lock:
            if state == self._desired:
                return
            self._desired = state
        if self._threaded:
            self._wake.set()
        else:
            self._pump()

    def set_enabled(self, enabled: bool) -> None:
        """Toggle at runtime (from the settings menu)."""
        enabled = bool(enabled) and self._identity is not None
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if enabled:
            with self._lock:
                self._last_sent = None
            self._last_send_t = None
            self.start()
        else:
            self._stop_worker()
            self._sign_off(wait_s=0.0)  # fire and forget; never stalls the menu

    def shutdown(self) -> None:
        """Leave the board and stop the worker. Never raises."""
        self._stop_worker()
        self._sign_off()

    # -- worker / single-step logic ------------------------------------------

    def _stop_worker(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None
        self._started = False
        self._stop.clear()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._pump()
            except Exception:  # pragma: no cover - defensive belt-and-braces
                log.debug("Online presence pump failed", exc_info=True)
            self._wake.wait(self._worker_wait())
            self._wake.clear()

    def _worker_wait(self) -> float:
        """Seconds until the next pump: the rest of the off-duty grace when a
        sign-off is brewing, soon for a pending change (once the change
        throttle allows it), otherwise the next scheduled heartbeat."""
        now = self._clock()
        with self._lock:
            desired = self._desired
            pending = desired != self._last_sent
        if desired is None:
            if not self._on_board or self._none_since is None:
                return _WORKER_TICK_S
            return max(0.05, self._off_duty_grace - (now - self._none_since))
        if self._last_send_t is None:
            return _WORKER_TICK_S
        until_heartbeat = self._heartbeat - (now - self._last_send_t)
        if pending:
            until_change = self._min_change - (now - self._last_send_t)
            return max(0.05, min(until_heartbeat, until_change))
        return max(0.05, until_heartbeat)

    def _pump(self) -> None:
        """Send at most one request: a change, a heartbeat, or a sign-off."""
        if self._stop.is_set() or not self._enabled or self._identity is None:
            return
        with self._lock:
            desired = self._desired
            last_sent = self._last_sent
        now = self._clock()
        since_send = None if self._last_send_t is None else now - self._last_send_t

        if desired is None:
            # Off duty: after a short grace (so a transient sub-menu does not
            # bounce the driver off the board), one sign-off request.
            if not self._on_board:
                return
            if self._none_since is None:
                self._none_since = now
            if now - self._none_since < self._off_duty_grace:
                return
            if self._post("", ""):
                self._on_board = False
                with self._lock:
                    self._last_sent = None
                self._last_send_t = now
            return

        self._none_since = None
        changed = desired != last_sent
        if changed and (since_send is None or since_send >= self._min_change):
            pass  # send the change now
        elif since_send is None or since_send >= self._heartbeat:
            pass  # steady-state heartbeat keeps the TTL alive
        else:
            return  # nothing due yet

        if self._post(desired.activity, desired.detail):
            self._on_board = True
            with self._lock:
                self._last_sent = desired
        # Count failures as attempts too, so an unreachable site is retried on
        # the heartbeat schedule instead of every worker wake-up.
        self._last_send_t = now

    def _post(self, activity: str, detail: str) -> bool:
        identity = self._identity
        if identity is None:
            return False
        try:
            reply = self._transport(
                f"{base_url()}/api/freight-fate/presence",
                {"driverId": identity.driver_id, "activity": activity, "detail": detail},
                {"Authorization": f"Bearer {identity.driver_token}"},
            )
        except Exception as e:
            log.debug("Online presence post failed: %s", e)
            return False
        return bool(reply.get("ok"))

    def _sign_off(self, wait_s: float = 2.0) -> None:
        """Best-effort empty-activity post so the board drops us promptly.

        Called from the game loop (settings toggle) and from shutdown, so the
        post runs on its own short-lived thread: a slow or unreachable site
        must never freeze the game. The board's TTL cleans up anyway if the
        post is lost. Synchronous mode keeps tests deterministic.
        """
        if not self._on_board:
            return
        self._on_board = False
        with self._lock:
            self._last_sent = None
        if not self._threaded:
            self._post("", "")
            return
        poster = threading.Thread(
            target=lambda: self._post("", ""), name="online-sign-off", daemon=True
        )
        poster.start()
        if wait_s > 0:
            poster.join(timeout=wait_s)


def fetch_board(*, transport: Transport = _http_json) -> list[dict] | None:
    """The current public drivers board, or None when unreachable.

    Each entry has ``displayName``, ``activity``, ``detail`` and
    ``updatedAt`` (epoch milliseconds). Called from a background thread by
    the in-game "Drivers online" view; never called on the game loop.
    """
    try:
        reply = transport(f"{base_url()}/api/freight-fate/presence", None, {})
    except Exception as e:
        log.debug("Online presence board fetch failed: %s", e)
        return None
    drivers = reply.get("drivers")
    return drivers if isinstance(drivers, list) else None
