"""The Online hub: one main-menu home for the board, account, and sharing."""

import pygame
import pytest


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
        # This line keeps the online-enhancement master switch at the top of
        # the hub; the board sits right under it.
        assert hub.items[0].text == "Online services: on"
        assert hub.items[1].text == "Drivers board"
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
        hub.handle_event(key_event(pygame.K_DOWN))  # past the master switch
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
    app.ctx.say = lambda text, interrupt=True: None
    try:
        hub = OnlineHubState(app.ctx)
        app.push_state(hub)
        for label in ("Drivers board", "Restore a cloud backup", "Link a Mastodon account"):
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
