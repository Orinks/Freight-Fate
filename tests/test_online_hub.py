"""The Online hub: one main-menu home for the board, account, and sharing."""

import pygame
import pytest
from speech_capture import speech_stub


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0)


@pytest.mark.smoke
def test_main_menu_online_item_opens_the_hub():
    from freight_fate.app import App
    from freight_fate.states.main_menu import MainMenuState
    from freight_fate.states.online_hub import OnlineHubState

    app = App()
    try:
        menu = MainMenuState(app.ctx)
        app.push_state(menu)
        while menu.items[menu.index].text != "Online":
            menu.handle_event(key_event(pygame.K_DOWN))
        assert menu.items[menu.index].help  # spoken help text exists for F1
        menu.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, OnlineHubState)
        hub = app.state
        # The board leads because viewing it shares nothing; the
        # online-enhancement master switch sits right under it.
        assert hub.items[0].text == "Drivers board"
        assert hub.items[1].text == "Online services: on"
        for item in hub.items[:-1]:  # every row but Back explains itself
            assert item.help
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_hub_drivers_board_item_opens_the_board(monkeypatch):
    from freight_fate import online_presence
    from freight_fate.app import App
    from freight_fate.states.online_hub import OnlineHubState
    from freight_fate.states.online_states import DriversOnlineState

    monkeypatch.setattr(online_presence, "fetch_board", lambda: [])
    app = App()
    try:
        hub = OnlineHubState(app.ctx)
        app.push_state(hub)
        assert hub.items[hub.index].text == "Drivers board"
        hub.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, DriversOnlineState)
    finally:
        app.shutdown()


def test_hub_left_right_adjust_rows_align_with_items():
    """Right arrow on an action row does nothing; on a toggle row it flips that
    row's own setting. Pins the adjust list against drifting out of step with
    build_items when rows are added or reordered."""
    from freight_fate.app import App
    from freight_fate.states.online_hub import OnlineHubState

    app = App()
    app.ctx.say = speech_stub()
    try:
        hub = OnlineHubState(app.ctx)
        app.push_state(hub)
        for label in (
            "Drivers board",
            "Open my driver setup page",
            "Restore a cloud backup",
            "Link a Mastodon account",
        ):
            while not hub.items[hub.index].text.startswith(label):
                hub.handle_event(key_event(pygame.K_DOWN))
            before = app.state
            hub.handle_event(key_event(pygame.K_RIGHT))
            assert app.state is before

        while not hub.items[hub.index].text.startswith("Discord presence"):
            hub.handle_event(key_event(pygame.K_DOWN))
        before = app.ctx.settings.discord_presence
        hub.handle_event(key_event(pygame.K_RIGHT))
        assert app.ctx.settings.discord_presence != before
        hub.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.discord_presence == before
    finally:
        app.shutdown()


def test_hub_opens_the_driver_setup_page_in_a_browser(monkeypatch):
    """The path is not something anyone should have to remember.

    Josh's ask, 2026-08-15: a player who needs to rename their driver or
    sign a computer out has to get to /freight-fate/online/setup, and until
    now the only way there was typing it. The row opens the address the
    build actually talks to, staged host included.
    """
    import webbrowser

    from freight_fate.app import App
    from freight_fate.states import online_hub, online_states

    opened: list[str] = []
    monkeypatch.setenv("FREIGHT_FATE_ONLINE_URL", "https://dev.orinks.net")
    monkeypatch.setattr(online_states, "write_clipboard_text", lambda _text: True)
    app = App()
    spoken: list[str] = []
    app.ctx.say = speech_stub(spoken)
    try:
        hub = online_hub.OnlineHubState(app.ctx)
        app.push_state(hub)
        while hub.items[hub.index].text != "Open my driver setup page":
            hub.handle_event(key_event(pygame.K_DOWN))
        monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)
        hub.handle_event(key_event(pygame.K_RETURN))

        assert opened == ["https://dev.orinks.net/freight-fate/online/setup"]
        # It stays on the hub: nothing to come back to in the game.
        assert app.state is hub
        said = " ".join(line for line in spoken if isinstance(line, str))
        assert "driver setup page" in said
        assert "computers signed in to your account" in said
    finally:
        app.shutdown()


def test_hub_setup_page_falls_back_to_the_clipboard(monkeypatch):
    """A remote or streamed session is the normal case where the browser
    never opens, and there is no review cursor to read an address out of."""
    import webbrowser

    from freight_fate.app import App
    from freight_fate.states import online_hub, online_states

    monkeypatch.setenv("FREIGHT_FATE_ONLINE_URL", "https://dev.orinks.net")
    monkeypatch.setattr(online_states, "write_clipboard_text", lambda _text: True)
    app = App()
    spoken: list[str] = []
    app.ctx.say = speech_stub(spoken)
    try:
        hub = online_hub.OnlineHubState(app.ctx)
        app.push_state(hub)
        while hub.items[hub.index].text != "Open my driver setup page":
            hub.handle_event(key_event(pygame.K_DOWN))

        def refuse(_url):
            raise RuntimeError("no browser here")

        monkeypatch.setattr(webbrowser, "open", refuse)
        hub.handle_event(key_event(pygame.K_RETURN))

        said = " ".join(line for line in spoken if isinstance(line, str))
        assert "clipboard" in said
    finally:
        app.shutdown()


def test_hub_setup_page_reads_the_address_out_when_nothing_else_works(monkeypatch):
    """Neither browser nor clipboard: the address itself has to be spoken,
    because it is the only way the player can reach the page at all."""
    import webbrowser

    from freight_fate.app import App
    from freight_fate.states import online_hub, online_states

    monkeypatch.setenv("FREIGHT_FATE_ONLINE_URL", "https://dev.orinks.net")
    monkeypatch.setattr(online_states, "write_clipboard_text", lambda _text: False)
    app = App()
    spoken: list[str] = []
    app.ctx.say = speech_stub(spoken)
    try:
        hub = online_hub.OnlineHubState(app.ctx)
        app.push_state(hub)
        while hub.items[hub.index].text != "Open my driver setup page":
            hub.handle_event(key_event(pygame.K_DOWN))

        def refuse(_url):
            raise RuntimeError("no browser here")

        monkeypatch.setattr(webbrowser, "open", refuse)
        hub.handle_event(key_event(pygame.K_RETURN))

        said = " ".join(line for line in spoken if isinstance(line, str))
        assert "https://dev.orinks.net/freight-fate/online/setup" in said
    finally:
        app.shutdown()
