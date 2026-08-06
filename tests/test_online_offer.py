"""Tests for the one-time first-run orinks.net offer.

Nothing here touches the network: the offer itself makes no calls, and the
accept path is asserted by the state it pushes, not by running setup.
"""

from __future__ import annotations

from types import SimpleNamespace

from speech_capture import speech_stub

from freight_fate.settings import Settings
from freight_fate.states import online_offer


def _make_ctx(spoken: list) -> SimpleNamespace:
    return SimpleNamespace(
        settings=Settings(),
        say=speech_stub(spoken),
        audio=SimpleNamespace(play=lambda *a, **k: None),
        push_state=lambda state: spoken.append(("push", type(state).__name__)),
        replace_state=lambda state: spoken.append(("replace", type(state).__name__)),
        pop_state=lambda *a, **k: spoken.append(("pop",)),
        # CityMenuState.__init__ stores ctx.world on its JobBoard; the decline
        # and go_back paths construct it for real (not a mock), so the fixture
        # needs a placeholder even though these tests never read from it.
        world=None,
    )


def test_offered_when_the_gate_is_open_and_nothing_is_connected(monkeypatch):
    monkeypatch.setattr(online_offer, "_stored_identity", lambda: None)
    ctx = _make_ctx([])
    assert online_offer.should_offer_online(ctx) is True


def test_not_offered_once_seen(monkeypatch):
    monkeypatch.setattr(online_offer, "_stored_identity", lambda: None)
    ctx = _make_ctx([])
    ctx.settings.online_offer_seen = True
    assert online_offer.should_offer_online(ctx) is False


def test_not_offered_when_already_connected(monkeypatch):
    """A second career on a connected computer must not ask again -- the
    connection is per computer, not per career."""
    monkeypatch.setattr(online_offer, "_stored_identity", lambda: object())
    ctx = _make_ctx([])
    assert ctx.settings.online_offer_seen is False
    assert online_offer.should_offer_online(ctx) is False


def test_declining_sets_the_gate_and_enters_the_world():
    spoken: list = []
    ctx = _make_ctx(spoken)
    state = online_offer.OnlineOfferState(ctx)
    state.enter()
    state._decline()

    assert ctx.settings.online_offer_seen is True
    assert ("replace", "CityMenuState") in spoken


def test_escape_behaves_exactly_like_not_now():
    """The player must never be stuck here, and backing out must still spend
    the one offer -- otherwise it reappears on the next career."""
    spoken: list = []
    ctx = _make_ctx(spoken)
    state = online_offer.OnlineOfferState(ctx)
    state.enter()
    state.go_back()

    assert ctx.settings.online_offer_seen is True
    assert ("replace", "CityMenuState") in spoken


def test_the_offer_names_where_to_find_it_later():
    spoken: list = []
    ctx = _make_ctx(spoken)
    online_offer.OnlineOfferState(ctx).enter()
    said = " ".join(line for line in spoken if isinstance(line, str))
    assert "Online" in said


def test_the_offer_does_not_promise_backup_or_the_board():
    """Connecting does not switch either on. Promising them would leave a
    player believing their career is backed up when nothing is."""
    spoken: list = []
    ctx = _make_ctx(spoken)
    online_offer.OnlineOfferState(ctx).enter()
    said = " ".join(line for line in spoken if isinstance(line, str)).lower()
    assert "backed up" not in said
    assert "backing up" not in said


def test_not_now_is_the_starting_item():
    """The low-effort answer on a one-shot consent prompt should be the one
    that changes nothing."""
    spoken: list = []
    state = online_offer.OnlineOfferState(_make_ctx(spoken))
    state.enter()
    assert "Not now" in state.current_text()
