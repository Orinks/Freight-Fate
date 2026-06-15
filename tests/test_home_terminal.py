"""Home terminal picker: default city, region labels, and the new-career flow."""

import os

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
        assert app.state.title == "Atlanta Company Yard"
        assert app.state.items[app.state.index].text == "Dispatch board"
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
        while not app.state.items[app.state.index].text.startswith("Continue latest career"):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.profile.current_city == "Denver"
    finally:
        app.shutdown()


def test_tampered_save_is_spoken_and_omitted_from_main_menu(monkeypatch):
    import json

    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.main_menu import MainMenuState

    good = Profile(name="Honest", current_city="Denver")
    good.save()
    bad = Profile(name="Edited", current_city="Chicago")
    bad_path = bad.save()
    data = json.loads(bad_path.read_text())
    data["money"] = 1_000_000.0
    bad_path.write_text(json.dumps(data))

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        app.push_state(MainMenuState(app.ctx))
        labels = [item.text for item in app.state.items]
        assert labels[0].startswith("Continue latest career: Honest")
        assert "failed its integrity check" in spoken[-1]
        assert not bad_path.exists()
        assert bad_path.with_suffix(".json.invalid").exists()
    finally:
        app.shutdown()


def test_how_to_play_mentions_corrupted_save_recovery_without_prominent_page():
    from freight_fate.states.main_menu import HELP_PAGES

    titles = [title for title, _lines in HELP_PAGES]
    help_text = " ".join(line for _title, lines in HELP_PAGES for line in lines).lower()

    assert "Saved careers" not in titles
    assert "edited or corrupted career saves may be moved aside" in help_text
    assert "checked for integrity" not in help_text
    assert "older unsigned saves" not in help_text


def test_choose_career_loads_an_older_save_without_deleting_the_newest():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.main_menu import LoadDriverState, MainMenuState

    app = App()
    try:
        older = Profile(name="Veteran", current_city="Denver", money=12345.0)
        older.career.xp = 1200.0
        older.career.deliveries = 7
        older_path = older.save()
        newer = Profile(name="Rookie", current_city="Atlanta", money=5000.0)
        newer_path = newer.save()
        os.utime(older_path, (1_700_000_000, 1_700_000_000))
        os.utime(newer_path, (1_800_000_000, 1_800_000_000))

        app.push_state(MainMenuState(app.ctx))
        labels = [item.text for item in app.state.items]
        assert labels[0].startswith("Continue latest career: Rookie")
        assert "Choose career" in labels

        while app.state.items[app.state.index].text != "Choose career":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, LoadDriverState)

        rows = [item.text for item in app.state.items]
        assert rows[0].startswith("Rookie: level 1")
        assert rows[1].startswith("Veteran: level 2")
        assert "12,345 dollars" in rows[1]
        assert "at Denver Company Yard in Denver" in rows[1]
        assert "7 deliveries" in rows[1]
        assert "last saved" in rows[1]

        while not app.state.items[app.state.index].text.startswith("Veteran:"):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityMenuState)
        assert app.ctx.profile.name == "Veteran"
        assert app.ctx.profile.current_city == "Denver"
        assert newer_path.exists()
    finally:
        app.shutdown()
