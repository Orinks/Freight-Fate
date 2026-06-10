"""Home terminal picker: default city, region labels, and the new-career flow."""

import pygame


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def open_picker(app, name=""):
    """Drive a new career up to the home terminal picker."""
    from freight_fate.states.main_menu import HomeTerminalState, MainMenuState

    app.push_state(MainMenuState(app.ctx))
    while app.state.items[app.state.index].text != "New career":
        app.state.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))
    for ch in name:
        app.state.handle_event(key_event(ord(ch.lower()), ch))
    app.state.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, HomeTerminalState)
    return app.state


def test_picker_lists_every_city_with_region_and_defaults_to_chicago(world):
    from freight_fate.app import App
    from freight_fate.states.main_menu import REGION_LABELS

    app = App()
    try:
        picker = open_picker(app)
        assert picker.items[picker.index].text.startswith("Chicago")
        assert len(picker.items) == len(world.cities)
        labels = {item.text for item in picker.items}
        for city in world.cities.values():
            assert f"{city.name}, {REGION_LABELS[city.region]}" in labels
    finally:
        app.shutdown()


def test_picking_a_city_sets_the_profile_start_city():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState

    app = App()
    try:
        picker = open_picker(app, name="Southerner")
        # first-letter navigation, like every other menu
        while not picker.items[picker.index].text.startswith("Atlanta"):
            picker.handle_event(key_event(ord("a"), "a"))
        picker.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityMenuState)
        p = app.ctx.profile
        assert p.name == "Southerner"
        assert p.current_city == "Atlanta"
        # the choice is already persisted to disk
        assert Profile.load(p.path).current_city == "Atlanta"
    finally:
        app.shutdown()


def test_escape_returns_to_name_entry_keeping_the_typed_name():
    from freight_fate.app import App
    from freight_fate.states.main_menu import NameEntryState

    app = App()
    try:
        open_picker(app, name="Bob")
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, NameEntryState)
        assert app.state.name == "Bob"
        assert app.ctx.profile is None  # nothing created until a city is picked
    finally:
        app.shutdown()


def test_existing_profiles_never_see_the_picker():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.main_menu import MainMenuState

    app = App()
    try:
        Profile(name="Veteran", current_city="Denver").save()
        app.push_state(MainMenuState(app.ctx))
        while app.state.items[app.state.index].text != "Continue":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.profile.current_city == "Denver"
    finally:
        app.shutdown()
