"""Tests for the one-time first-run orinks.net offer.

Nothing here touches the network: the offer itself makes no calls, and the
accept path is asserted by the state it pushes, not by running setup.

Most tests here drive the state directly, which says nothing about how the
offer composes with the lines spoken around it. The two spoken-order tests at
the bottom drive a real career creation through ``App`` instead, because that
composition is where the offer was once spoken and then cancelled before a
player heard a word of it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pygame
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


# -- what a first-run player actually hears ------------------------------------
#
# Everything above tests one state in isolation. These drive the real career
# creation, because the defect these exist to catch is not in either line: it
# is one line interrupting the other, which only exists when the two are
# composed. They assert on what reaches the speech layer, in order, including
# whether each line cancelled the one before it.


def _key(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def _open_city_picker(app, name):
    """Drive New career as far as the home city picker, ready to confirm."""
    from freight_fate.states.main_menu import HomeCityState, HomeTerminalState, MainMenuState

    app.push_state(MainMenuState(app.ctx))
    while app.state.items[app.state.index].text != "New career":
        app.state.handle_event(_key(pygame.K_DOWN))
    app.state.handle_event(_key(pygame.K_RETURN))
    for ch in name:
        app.state.handle_event(_key(ord(ch.lower()), ch))
    app.state.handle_event(_key(pygame.K_RETURN))
    assert isinstance(app.state, HomeTerminalState)
    app.state.handle_event(_key(pygame.K_RETURN))  # default region
    assert isinstance(app.state, HomeCityState)


def _first_run_app(monkeypatch, spoken):
    """An App whose next career creation is a genuine first run.

    tests/conftest.py seeds the one-time gate as already spent for every test,
    so a test about the offer has to open it back up -- otherwise this file
    would pin copy the player never reaches.
    """
    from freight_fate.app import App

    monkeypatch.setattr(online_offer, "_stored_identity", lambda: None)
    app = App()
    app.ctx.settings.online_offer_seen = False
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken, with_interrupt=True))
    return app


def test_the_welcome_is_heard_in_full_and_then_the_offer(monkeypatch):
    """The welcome comes first and nothing cuts it off, then the offer.

    Speaking the welcome after pushing the offer state cancelled the offer
    mid-sentence: the player heard "Welcome aboard", then silence, sitting on
    an unexplained two-item consent menu whose disclosure -- that connecting
    only lets cloud backup and the drivers board be turned on later -- had been
    cut away.
    """
    spoken: list[tuple[str, bool]] = []
    app = _first_run_app(monkeypatch, spoken)
    try:
        _open_city_picker(app, name="Rookie")
        spoken.clear()
        app.state.handle_event(_key(pygame.K_RETURN))  # confirm the home city
        assert isinstance(app.state, online_offer.OnlineOfferState)

        lines = [text for text, _interrupt in spoken]
        assert lines[0].startswith("Welcome aboard, Rookie.")
        assert lines[0].endswith("Your first stop is the dispatch board.")
        assert lines[1].startswith("Before you set off.")
        assert lines[1].endswith("Not now. 1 of 2.")
        # The welcome opens the sequence, and every line after it queues, so
        # both are heard end to end rather than the last one winning.
        assert [interrupt for _text, interrupt in spoken] == [True] + [False] * (len(spoken) - 1)
        assert len(spoken) == 2
    finally:
        app.shutdown()


def test_saying_no_is_heard_before_the_city_menu_announcement(monkeypatch):
    """The one line naming where to find Online later must survive the move
    into the world -- it is the whole of saying no."""
    spoken: list[tuple[str, bool]] = []
    app = _first_run_app(monkeypatch, spoken)
    try:
        _open_city_picker(app, name="Rookie")
        app.state.handle_event(_key(pygame.K_RETURN))  # confirm the home city
        offer = app.state
        assert isinstance(offer, online_offer.OnlineOfferState)
        assert "Not now" in offer.current_text()  # the cursor starts here
        spoken.clear()
        offer.handle_event(_key(pygame.K_RETURN))

        from freight_fate.states.city import CityMenuState

        assert isinstance(app.state, CityMenuState)
        lines = [text for text, _interrupt in spoken]
        assert lines[0] == "No problem. You can connect any time from Online on the main menu."
        assert lines[1].startswith("Parked at")
        assert lines[2].startswith("Dispatch board.")
        assert [interrupt for _text, interrupt in spoken] == [True] + [False] * (len(spoken) - 1)
        assert len(spoken) == 3
    finally:
        app.shutdown()
