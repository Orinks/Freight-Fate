"""Tests for the device-code activation flow (replaces clipboard paste).

A fake transport keeps every test free of real sockets, matching the pattern
in ``test_online_presence.py``. The three contract points that matter most:
410 means "expired, get a new code" while 400 means "this device_code is
malformed and retrying it never helps" (they must not collapse to the same
status); an over-cap redeem also answers 410, because the real reason lives
on the website at claim time; and ``display_name`` must survive a ready poll
uncorrupted, because it is the player's only signal that the code was
claimed on the wrong account.
"""

from __future__ import annotations

import urllib.error

from freight_fate import online_activation
from freight_fate.online_activation import Activation, base_url


def _an_activation(**overrides) -> Activation:
    defaults = dict(
        device_code="a" * 64,
        user_code="WKQR-3468",
        verification_uri="https://orinks.net/activate",
        verification_uri_complete="https://orinks.net/activate?code=WKQR-3468",
        expires_at=0.0,
        interval=3.0,
    )
    defaults.update(overrides)
    return Activation(**defaults)


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://orinks.net", code, "err", None, None)


def _poll_raising(error: Exception):
    def transport(url, payload, headers, method=None):
        raise error

    return online_activation.poll_activation(_an_activation(), transport=transport)


# -- spell_code ----------------------------------------------------------------


def test_spell_code_uses_phonetics_and_speaks_the_dash():
    assert online_activation.spell_code("WKQR-3468") == (
        "Whiskey, Kilo, Quebec, Romeo, dash, three, four, six, eight"
    )


def test_spell_code_accepts_an_undashed_code():
    assert online_activation.spell_code("WKQR3468").startswith("Whiskey, Kilo")


def test_spell_code_covers_the_whole_activation_alphabet():
    # ABCDEFGHJKMNPQRTUVWXY346789 -- deliberately excludes O I L S Z 0 1 2 5,
    # chosen so no two phonetic words could ever be confused for each other.
    alphabet = "ABCDEFGHJKMNPQRTUVWXY346789"
    spelled = online_activation.spell_code(alphabet)
    words = spelled.split(", ")
    assert len(words) == len(alphabet)
    # No two entries collide, and every entry is non-empty.
    assert len(set(words)) == len(words)
    assert all(words)


# -- start_activation ------------------------------------------------------------


def test_start_returns_an_activation():
    def transport(url, payload, headers, method=None):
        assert url.endswith("/api/freight-fate/activate/start")
        return {
            "device_code": "a" * 64,
            "user_code": "WKQR-3468",
            "verification_uri": "https://orinks.net/activate",
            "verification_uri_complete": "https://orinks.net/activate?code=WKQR-3468",
            "expires_in": 600,
            "interval": 3,
        }

    activation = online_activation.start_activation(transport=transport)
    assert activation is not None
    assert activation.user_code == "WKQR-3468"
    assert activation.interval == 3


def test_start_returns_none_on_rate_limit_or_unavailable():
    for code in (429, 503):

        def transport(url, payload, headers, method=None, code=code):
            raise _http_error(code)

        assert online_activation.start_activation(transport=transport) is None


def test_start_returns_none_on_malformed_reply():
    """A 200 missing an expected field must not raise into the caller."""

    def transport(url, payload, headers, method=None):
        return {"device_code": "a" * 64}  # missing user_code and friends

    assert online_activation.start_activation(transport=transport) is None


def test_start_never_raises_on_network_trouble():
    def transport(url, payload, headers, method=None):
        raise OSError("no route to host")

    assert online_activation.start_activation(transport=transport) is None


# -- poll_activation ---------------------------------------------------------------


def test_poll_ready_carries_the_display_name():
    """The display name is the player's only signal that someone else claimed
    their code -- the game speaks it, so it must survive the poll."""

    def transport(url, payload, headers, method=None):
        assert url.endswith("/api/freight-fate/activate/poll")
        assert payload == {"device_code": _an_activation().device_code}
        return {
            "status": "ready",
            "driver_id": "rig-hauler",
            "token": "ffd_" + "b" * 64,
            "display_name": "Rig Hauler",
        }

    result = online_activation.poll_activation(_an_activation(), transport=transport)
    assert result.status == "ready"
    assert result.driver_id == "rig-hauler"
    assert result.token == "ffd_" + "b" * 64
    assert result.display_name == "Rig Hauler"


def test_poll_pending_carries_no_identity():
    def transport(url, payload, headers, method=None):
        return {"status": "pending"}

    result = online_activation.poll_activation(_an_activation(), transport=transport)
    assert result.status == "pending"
    assert result.driver_id is None
    assert result.token is None
    assert result.display_name is None


def test_poll_maps_410_to_expired_and_400_to_corrupt():
    """410 means the code timed out and a new one will fix it. 400 means the
    stored secret is malformed, which retrying the same code never fixes."""
    assert _poll_raising(_http_error(410)).status == "expired"
    assert _poll_raising(_http_error(400)).status == "error"


def test_poll_over_cap_redeem_reads_as_expired():
    """The server answers an over-cap redeem with 410 too -- the player learns
    the real reason (too many computers) on the website at claim time, so the
    game just treats it like any other timed-out code."""
    assert _poll_raising(_http_error(410)).status == "expired"


def test_poll_maps_503_to_error():
    assert _poll_raising(_http_error(503)).status == "error"


def test_poll_never_raises_on_network_trouble():
    """Polling runs on a timer while the player waits; a transient blip must
    not crash the menu."""
    result = _poll_raising(OSError("connection reset"))
    assert result.status == "error"


def test_poll_never_raises_on_malformed_200():
    def transport(url, payload, headers, method=None):
        return {"status": "some-unexpected-shape"}

    result = online_activation.poll_activation(_an_activation(), transport=transport)
    assert result.status == "error"


def test_base_url_reused_from_online_presence():
    # online_activation must not fork its own base_url -- one FREIGHT_FATE_ONLINE_URL
    # override has to redirect every Orinks endpoint the game talks to.
    assert base_url is online_activation.base_url
