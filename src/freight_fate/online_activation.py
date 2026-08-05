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

import logging
import time
import urllib.error
from dataclasses import dataclass

from .online_presence import Transport, _http_json, base_url

log = logging.getLogger(__name__)

__all__ = [
    "Activation",
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
    spoken or transcript-bound string. ``user_code`` is the short code the
    player reads back and types into a browser. ``expires_at`` is a
    ``time.time()``-based deadline (the server gives a relative
    ``expires_in`` in seconds; this module resolves it to an absolute time
    once, at start, so a caller checking it later doesn't need to remember
    when the request was made).
    """

    device_code: str
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
    either way the fix is the same: start over with a new code), or
    ``"error"`` (network trouble, or a device_code the server rejected as
    malformed -- retrying the same code can never fix the latter, so it must
    not be presented to the player as "expired").
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
        reply = transport(f"{base_url()}/api/freight-fate/activate/start", {}, {})
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
            log.warning("Activation poll rejected the stored device_code as malformed")
        else:
            log.warning("Activation poll failed: HTTP %s", e.code)
        # 400 (malformed device_code) is not "expired": retrying the same
        # code can never fix it, so it must surface as a distinct status
        # rather than telling the player to just wait it out.
        return PollResult(status="error")
    except Exception as e:
        log.warning("Activation poll failed: %s", e)
        return PollResult(status="error")

    status = reply.get("status")
    if status == "ready":
        return PollResult(
            status="ready",
            driver_id=reply.get("driver_id"),
            token=reply.get("token"),
            display_name=reply.get("display_name"),
        )
    if status == "pending":
        return PollResult(status="pending")
    # An unrecognised 200 body is not something a retry can fix either, but
    # it is also not evidence the code expired -- treat it like any other
    # answer the game can't make sense of.
    log.warning("Activation poll returned an unexpected status: %r", status)
    return PollResult(status="error")
