"""Device-code activation: replaces the clipboard-paste credential setup.

The old flow made a player copy a Driver ID and a token from the Orinks
driver setup page and paste both into the game (see
:mod:`freight_fate.online_presence`'s :class:`OnlineIdentity`). That is
error-prone for a screen reader user working across two applications with no
shared clipboard review. This module instead drives the OAuth-device-code
style exchange already live on orinks.net: the game asks for a short code,
speaks it, the player types that code into any browser (any device) and
signs in there, and the game polls until the site says the code was claimed.

This is the *only* place that knows about the two activation endpoints. It
deliberately reuses :data:`freight_fate.online_presence.Transport`,
:func:`freight_fate.online_presence._http_json`, and
:func:`freight_fate.online_presence.base_url` rather than forking them, so
the game has exactly one HTTP client and exactly one
``FREIGHT_FATE_ONLINE_URL`` override for every Orinks endpoint.

Both request/response shapes below are an existing, already-deployed server
contract -- do not change field names or status-code meanings here without
updating the server first.
"""

from __future__ import annotations

import hashlib
import logging
import platform
import time
import urllib.error
import uuid
from dataclasses import dataclass, field

from .online_presence import Transport, _http_json, base_url

log = logging.getLogger(__name__)


def machine_key() -> str:
    """An opaque, stable name for this computer, for the computer list.

    orinks.net caps an account at ten computers and used to count
    ACTIVATIONS: every freshly unzipped build that connected took another
    slot, so a tester who takes a build a week filled the list with one PC
    and was locked out (armstrong445, 2026-08-15). Sending this lets the
    server replace that computer's entry instead of adding one.

    Hashed, and never the hostname itself: the server only ever compares it
    for equality, so there is no reason to hand over a name that might be a
    person's. Derived from the machine's network identity, which is stable
    across a reinstall and across unzipping the game somewhere else -- the
    two things that were minting duplicate rows.

    This is NOT identity and never authenticates anything: it is a hint the
    player triggers by deliberately connecting, and a wrong or missing one
    costs only a duplicate row.
    """
    seed = f"{uuid.getnode():x}:{platform.node()}"
    return hashlib.sha256(seed.encode("utf-8", "replace")).hexdigest()[:32]


__all__ = [
    "Activation",
    "machine_key",
    "PollResult",
    "spell_code",
    "start_activation",
    "poll_activation",
    "base_url",
]

# NATO phonetics for every letter the activation alphabet could ever contain.
# The alphabet itself (ABCDEFGHJKMNPQRTUVWXY346789, defined server-side)
# excludes O I L S Z 0 1 2 5 specifically so no two of these words are ever
# close enough to be confused for each other over a screen reader -- keeping
# the unused letters here too costs nothing and means this table never has
# to change if the server's alphabet ever does.
_PHONETIC = {
    "A": "Alpha",
    "B": "Bravo",
    "C": "Charlie",
    "D": "Delta",
    "E": "Echo",
    "F": "Foxtrot",
    "G": "Golf",
    "H": "Hotel",
    "I": "India",
    "J": "Juliett",
    "K": "Kilo",
    "L": "Lima",
    "M": "Mike",
    "N": "November",
    "O": "Oscar",
    "P": "Papa",
    "Q": "Quebec",
    "R": "Romeo",
    "S": "Sierra",
    "T": "Tango",
    "U": "Uniform",
    "V": "Victor",
    "W": "Whiskey",
    "X": "Xray",
    "Y": "Yankee",
    "Z": "Zulu",
}

_DIGITS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}


def spell_code(code: str) -> str:
    """Spell an activation code letter-by-letter for a screen reader.

    The game has no review cursor, so a player cannot step through a spoken
    string character by character the way they can in a browser -- speaking
    ``WKQR-3468`` once, as a word, gives them nothing to transcribe. This
    returns NATO phonetics for letters and plain words for digits,
    comma-separated (so a screen reader pauses between entries), with the
    dash spoken too so a player copying the code by ear knows it belongs in
    the string. Works on a code with or without the dash.
    """
    words = []
    for ch in code:
        if ch == "-":
            words.append("dash")
            continue
        upper = ch.upper()
        if upper in _PHONETIC:
            words.append(_PHONETIC[upper])
        elif ch in _DIGITS:
            words.append(_DIGITS[ch])
        else:
            # Defensive only: the server-issued alphabet never produces
            # anything else, but an unrecognised character still gets read
            # out verbatim instead of silently vanishing from the spelling.
            words.append(ch)
    return ", ".join(words)


@dataclass
class Activation:
    """An in-progress device-code activation.

    ``device_code`` is the polling secret -- it is bound to this device and
    never shown to the player, so it must never be logged or included in any
    spoken or transcript-bound string. It is ``repr=False`` so that invariant
    is structural rather than a rule every future caller has to remember: a
    stray ``log.warning("... %r", activation)`` would otherwise write the
    secret straight into the session log with nothing failing.
    ``user_code`` is the short code the
    player reads back and types into a browser. ``expires_at`` is a
    ``time.time()``-based deadline (the server gives a relative
    ``expires_in`` in seconds; this module resolves it to an absolute time
    once, at start, so a caller checking it later doesn't need to remember
    when the request was made).
    """

    device_code: str = field(repr=False)
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_at: float
    interval: float


@dataclass
class PollResult:
    """One poll's outcome.

    ``status`` is one of ``"pending"`` (keep waiting), ``"ready"`` (claimed
    -- ``driver_id``, ``token`` and ``display_name`` are all set),
    ``"expired"`` (the code timed out, or was over an account's device cap;
    either way the fix is the same: start over with a new code),
    ``"retry"`` (a transient failure -- network trouble, an HTTP status other
    than 400/410, a reply the caller could not parse, or a "ready" body with
    no ``driver_id``/``token`` in it -- that a caller
    should just poll again on the next tick, exactly like "pending"), or
    ``"error"`` (HTTP 400 specifically: the server rejected the stored
    device_code as malformed. Retrying the same code can never fix this, so
    it must not be presented to the player as "expired" or as something a
    moment's wait will resolve, the way "retry" is).
    """

    status: str
    driver_id: str | None = None
    token: str | None = None
    display_name: str | None = None


def start_activation(*, transport: Transport = _http_json) -> Activation | None:
    """Ask orinks.net to mint a new device code, or None if it could not.

    None covers every failure the player can't do anything about but wait
    and retry: rate limiting (429), the endpoint being down (503), a
    malformed reply, or a network error. The caller (the setup menu) is
    expected to show one generic "couldn't reach Orinks, try again" message
    for all of them -- there is nothing actionable to say differently.
    """
    try:
        # An older server ignores an unknown field, so this is safe to send
        # before the site half is everywhere.
        reply = transport(
            f"{base_url()}/api/freight-fate/activate/start", {"machine_key": machine_key()}, {}
        )
    except Exception as e:
        log.warning("Activation start failed: %s", e)
        return None
    try:
        return Activation(
            device_code=reply["device_code"],
            user_code=reply["user_code"],
            verification_uri=reply["verification_uri"],
            verification_uri_complete=reply["verification_uri_complete"],
            expires_at=time.time() + float(reply["expires_in"]),
            interval=float(reply["interval"]),
        )
    except (KeyError, TypeError, ValueError) as e:
        log.warning("Activation start returned a malformed reply: %s", e)
        return None


def poll_activation(activation: Activation, *, transport: Transport = _http_json) -> PollResult:
    """Check whether ``activation``'s code has been claimed yet.

    Runs on a timer while the player waits at the setup screen, so no
    exception may ever escape to the caller -- a transient network blip must
    not crash the menu. Never logs or otherwise surfaces
    ``activation.device_code``.

    "error" is reserved for HTTP 400 alone. Everything else this function
    cannot make sense of -- a dropped connection, a timeout, an SSL error, a
    5xx, an unexpected status code, a 200 body that is not even a mapping --
    comes back as "retry" instead, so a caller (``OnlineSetupState``) can
    just poll again on the next tick rather than forcing the player through
    a fresh activation code for what is very likely a momentary blip.
    """
    try:
        reply = transport(
            f"{base_url()}/api/freight-fate/activate/poll",
            {"device_code": activation.device_code},
            {},
        )
    except urllib.error.HTTPError as e:
        if e.code == 410:
            # Covers both a timed-out code and an over-cap redeem -- the
            # player learns the real reason (too many computers on the
            # account) in the browser at claim time, so the game just
            # treats both as "get a new code".
            return PollResult(status="expired")
        if e.code == 400:
            # Malformed device_code is not "expired": retrying the same code
            # can never fix it, so it must surface as a distinct status
            # rather than telling the player to just wait it out.
            log.warning("Activation poll rejected the stored device_code as malformed")
            return PollResult(status="error")
        # Any other HTTP status (429, 5xx, ...) is treated as transient: none
        # of them mean the code itself is bad, so the same code can just be
        # polled again.
        log.warning("Activation poll failed: HTTP %s", e.code)
        return PollResult(status="retry")
    except Exception as e:
        # URLError, socket timeouts, SSL errors, and anything else that is
        # not an HTTPError are all connectivity trouble, not a verdict on the
        # code -- transient, same as an HTTP 5xx above.
        log.warning("Activation poll failed: %s", e)
        return PollResult(status="retry")

    # A 200 body that isn't even a mapping (None, a list, a bare string --
    # anything a broken deploy or a middlebox could hand back) must land here
    # too, not raise: this whole block, not just the HTTPError branch above,
    # is the "never let an exception escape" guarantee the docstring makes.
    try:
        status = reply.get("status")
        if status == "ready":
            driver_id = reply.get("driver_id")
            token = reply.get("token")
            if not driver_id or not token:
                # A "ready" that carries no identity is not a claim the caller
                # can act on: saving it would write a null identity, tell the
                # player "Connected to orinks.net", and then quietly send
                # "Bearer None" on every heartbeat until the next launch drops
                # it. Treat it the same as any other body this module cannot
                # make sense of -- transient, keep polling -- so a broken
                # deploy or a body-rewriting middlebox resolves itself once
                # the real claim lands, and expiry (not a wrong success) is
                # the worst outcome.
                log.warning("Activation poll returned a ready reply with no identity")
                return PollResult(status="retry")
            return PollResult(
                status="ready",
                driver_id=driver_id,
                token=token,
                display_name=reply.get("display_name"),
            )
        if status == "pending":
            return PollResult(status="pending")
    except AttributeError:
        log.warning("Activation poll returned a non-object reply: %r", reply)
        return PollResult(status="retry")

    # An unrecognised 200 body (a mapping missing "status", or an unknown
    # value) is most plausibly a transient server or proxy hiccup rather than
    # evidence about the code itself, so it gets the same "poll again" status
    # as a network blip -- not the terminal "error" that only HTTP 400 gets.
    log.warning("Activation poll returned an unexpected status: %r", status)
    return PollResult(status="retry")
