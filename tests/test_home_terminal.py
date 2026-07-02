"""Home terminal picker: default city, region labels, and the new-career flow."""

import os

import pygame


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def open_picker(app, name=""):
    """Drive a new career up to the home terminal picker."""
    from freight_fate.states.main_menu import CareerStartState, HomeTerminalState, MainMenuState

    app.push_state(MainMenuState(app.ctx))
    while app.state.items[app.state.index].text != "New career":
        app.state.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))
    for ch in name:
        app.state.handle_event(key_event(ord(ch.lower()), ch))
    app.state.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, CareerStartState)
    app.state.handle_event(key_event(pygame.K_RETURN))  # default Northstar start
    assert isinstance(app.state, HomeTerminalState)
    return app.state


def test_region_picker_lists_regions_and_defaults_to_chicagos_region(world):
    from freight_fate.app import App
    from freight_fate.states.main_menu import _region_menu_name

    app = App()
    try:
        picker = open_picker(app)
        # defaults to the region that contains the default city (Chicago)
        default_region = world.cities["Chicago"].region
        assert picker.items[picker.index].text.startswith(_region_menu_name(default_region))
        # one item per region that actually has cities
        regions_with_cities = {c.region for c in world.cities.values()}
        assert len(picker.items) == len(regions_with_cities)
        # every region item names its city count
        for item in picker.items:
            assert "cit" in item.text  # "1 city" or "N cities"
    finally:
        app.shutdown()


def test_region_opens_a_city_submenu_listing_only_that_regions_cities(world):
    from freight_fate.app import App
    from freight_fate.states.main_menu import HomeCityState, _region_menu_name

    app = App()
    try:
        picker = open_picker(app)
        great_lakes = _region_menu_name("great_lakes")
        while not picker.items[picker.index].text.startswith(great_lakes):
            picker.handle_event(key_event(pygame.K_DOWN))
        picker.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, HomeCityState)
        listed = {item.text.split(",")[0] for item in app.state.items}
        expected = {c.name for c in world.cities.values() if c.region == "great_lakes"}
        assert listed == expected
        assert "Chicago" in listed
    finally:
        app.shutdown()


def test_picking_a_city_sets_the_profile_start_city():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.main_menu import HomeCityState, _region_menu_name

    app = App()
    ambient = []
    app.ctx.audio.set_ambient = lambda key, volume=1.0: ambient.append((key, volume))
    try:
        picker = open_picker(app, name="Southerner")
        # drill into Atlanta's region, then pick the city
        atlanta_region = app.ctx.world.cities["Atlanta"].region
        target = _region_menu_name(atlanta_region)
        while not picker.items[picker.index].text.startswith(target):
            picker.handle_event(key_event(pygame.K_DOWN))
        picker.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, HomeCityState)
        city_picker = app.state
        while not city_picker.items[city_picker.index].text.startswith("Atlanta"):
            city_picker.handle_event(key_event(pygame.K_DOWN))
        ambient.clear()
        city_picker.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityMenuState)
        p = app.ctx.profile
        assert p.name == "Southerner"
        assert p.current_city == "Atlanta"
        assert app.state.title == "Atlanta Company Yard"
        assert app.state.items[app.state.index].text == "Dispatch board"
        assert ("poi/facility_gate", 1.0) in ambient
        # the choice is already persisted to disk
        assert Profile.load(p.path).current_city == "Atlanta"
    finally:
        app.shutdown()


def test_escape_returns_to_name_entry_keeping_the_typed_name():
    from freight_fate.app import App
    from freight_fate.states.main_menu import CareerStartState, NameEntryState

    app = App()
    try:
        open_picker(app, name="Bob")
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, CareerStartState)
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, NameEntryState)
        assert app.state.name == "Bob"
        assert app.ctx.profile is None  # nothing created until a city is picked
    finally:
        app.shutdown()


def test_escape_from_city_list_returns_to_region_picker():
    from freight_fate.app import App
    from freight_fate.states.main_menu import HomeCityState, HomeTerminalState

    app = App()
    try:
        picker = open_picker(app, name="Bob")
        picker.handle_event(key_event(pygame.K_RETURN))  # open a region
        assert isinstance(app.state, HomeCityState)
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, HomeTerminalState)
        assert app.ctx.profile is None  # still nothing created
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


def test_manage_careers_deletes_selected_save_without_touching_others():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.music import music_track_duration_s
    from freight_fate.states.main_menu import (
        CareerActionsState,
        ConfirmCareerActionState,
        MainMenuState,
        ManageCareersState,
    )

    app = App()
    played = []
    app.ctx.audio.play_music = lambda track, fade_ms=1500: played.append(track)
    try:
        keep = Profile(name="Keep Me", current_city="Denver")
        keep_path = keep.save()
        delete = Profile(name="Delete Me", current_city="Atlanta")
        delete.career.total_miles = 10_000
        delete_path = delete.save()
        newer_time = keep_path.stat().st_mtime + 10.0
        os.utime(delete_path, (newer_time, newer_time))

        app.push_state(MainMenuState(app.ctx))
        assert played == ["menu_coast_to_coast"]
        while app.state.items[app.state.index].text != "Manage careers":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, ManageCareersState)

        while not app.state.items[app.state.index].text.startswith("Delete Me:"):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CareerActionsState)

        while app.state.items[app.state.index].text != "Delete this career":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, ConfirmCareerActionState)
        assert app.state.items[app.state.index].text == "Yes, delete Delete Me"
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, MainMenuState)
        assert played == ["menu_coast_to_coast"]
        app.state.update(music_track_duration_s("menu_coast_to_coast") + 0.1)
        assert played == ["menu_coast_to_coast", "menu_theme"]
        assert keep_path.exists()
        assert not delete_path.exists()
        labels = [item.text for item in app.state.items]
        assert any(label.startswith("Continue latest career: Keep Me") for label in labels)
    finally:
        app.shutdown()


def test_manage_careers_resets_selected_save_to_fresh_profile(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import STARTING_MONEY, Profile
    from freight_fate.states.main_menu import (
        ConfirmCareerActionState,
        MainMenuState,
        ManageCareersState,
    )

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        profile = Profile(name="Reset Me", current_city="Seattle", money=4321.0)
        profile.career.xp = 3200.0
        profile.career.deliveries = 11
        profile.truck_damage_pct = 48.0
        profile.active_trip = {"kind": "delivery", "job": {"destination": "Denver"}}
        path = profile.save()

        app.push_state(MainMenuState(app.ctx))
        while app.state.items[app.state.index].text != "Manage careers":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, ManageCareersState)

        app.state.handle_event(key_event(pygame.K_RETURN))
        assert app.state.items[app.state.index].text == "Reset this career"
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, ConfirmCareerActionState)
        assert "Resetting starts this driver over" in spoken[-1]
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, MainMenuState)
        fresh = Profile.load(path)
        assert fresh.name == "Reset Me"
        assert fresh.current_city == "Seattle"
        assert fresh.money == STARTING_MONEY
        assert fresh.career.deliveries == 0
        assert fresh.career.xp == 0
        assert fresh.truck_damage_pct == 0
        assert fresh.active_trip is None
        assert "Reset Me reset" in spoken[-1]
    finally:
        app.shutdown()
