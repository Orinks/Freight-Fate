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
    """Connecting does not switch either feature on -- it only lets the
    player turn each on separately later.

    A substring check can never close this gap, in either direction: a
    rewrite that keeps "lets you turn on cloud backup" and "appear on the
    drivers board" verbatim, then adds a clause -- "...so your career is
    already protected" -- still passes both a word-ban and a positive
    substring check while reintroducing exactly the false promise a player
    could act on. So this pins the entire spoken line, word for word. Any
    future edit to this copy -- even one that keeps the two required
    phrases -- has to update this literal string, which forces the person
    making the edit to read what the offer now claims before it can ship.
    """
    spoken: list = []
    ctx = _make_ctx(spoken)
    online_offer.OnlineOfferState(ctx).enter()
    said = [line for line in spoken if isinstance(line, str)]

    assert said == [
        "Before you set off. You can connect this computer to an "
        "orinks.net account. That is what lets you turn on cloud backup "
        "for your career and appear on the drivers board later, from "
        "Online on the main menu. It takes a code and your browser, and "
        "you can do it any time instead. Not now. 1 of 2."
    ]


def test_not_now_is_the_starting_item():
    """The low-effort answer on a one-shot consent prompt should be the one
    that changes nothing."""
    spoken: list = []
    state = online_offer.OnlineOfferState(_make_ctx(spoken))
    state.enter()
    assert "Not now" in state.current_text()


def test_accepting_pushes_setup_with_activation_already_started():
    # OnlineSetupState must go on top via push_state (not replace_state),
    # so the CityMenuState underneath survives -- that is what makes
    # backing out of setup land in the world instead of back on this offer.
    spoken: list = []
    ctx = _make_ctx(spoken)
    pushed: list = []
    ctx.push_state = lambda state: pushed.append(state)

    state = online_offer.OnlineOfferState(ctx)
    state.enter()
    state._accept()

    assert ctx.settings.online_offer_seen is True
    names = [type(s).__name__ for s in pushed]
    assert "OnlineSetupState" in names
    setup = next(s for s in pushed if type(s).__name__ == "OnlineSetupState")
    # The flag, not just the state: pushing setup without autostart would
    # leave the player confirming a decision they already made.
    assert setup.autostart is True
    # And the city menu is still reachable underneath, via replace_state on
    # the original offer state.
    assert ("replace", "CityMenuState") in spoken


def test_creating_a_first_career_reaches_the_offer(monkeypatch):
    """The offer replaces the city menu at career creation; its own exits put
    the city menu back, so a player lands in the same place either way."""
    from freight_fate.states import main_menu

    monkeypatch.setattr(online_offer, "_stored_identity", lambda: None)
    ctx = _make_ctx([])
    assert (
        main_menu._first_state_after_career_creation(ctx).__class__.__name__ == "OnlineOfferState"
    )


def test_creating_a_later_career_goes_straight_to_the_city_menu(monkeypatch):
    from freight_fate.states import main_menu

    monkeypatch.setattr(online_offer, "_stored_identity", lambda: None)
    ctx = _make_ctx([])
    ctx.settings.online_offer_seen = True
    assert main_menu._first_state_after_career_creation(ctx).__class__.__name__ == "CityMenuState"
