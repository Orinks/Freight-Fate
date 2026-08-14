import pygame
import pytest
from speech_capture import speech_stub


def key_event(key, unicode="", mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode, mod=mod)


# Gameplay is now a category with its own submenu; these four screens live one
# level down from the Settings picker, under the "Gameplay" row.
GAMEPLAY_SUBCATEGORIES = {
    "Driving assistance",
    "Difficulty and hours of service",
    "World and traffic",
    "Controls",
}


def open_settings_category(app, label):
    """Open a settings screen by its spoken title.

    Handles both the top-level categories (Audio, Speech, ...) and the four
    Gameplay subcategories, routing through the Gameplay parent for the latter.
    """
    from freight_fate.states.main_menu import (
        GameplaySettingsState,
        SettingsCategoryState,
        SettingsState,
    )

    picker = SettingsState(app.ctx)
    app.push_state(picker)
    if label in GAMEPLAY_SUBCATEGORIES:
        while picker.items[picker.index].text != "Gameplay":
            picker.handle_event(key_event(pygame.K_DOWN))
        picker.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, GameplaySettingsState)
        parent = app.state
        while parent.items[parent.index].text != label:
            parent.handle_event(key_event(pygame.K_DOWN))
        parent.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, SettingsCategoryState)
        return app.state
    while picker.items[picker.index].text != label:
        picker.handle_event(key_event(pygame.K_DOWN))
    picker.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, SettingsCategoryState)
    return app.state


def open_online_hub_from_settings(app):
    """The Settings picker keeps an Online pointer that opens the hub."""
    from freight_fate.states.main_menu import SettingsState
    from freight_fate.states.online_hub import OnlineHubState

    picker = SettingsState(app.ctx)
    app.push_state(picker)
    while picker.items[picker.index].text != "Online":
        picker.handle_event(key_event(pygame.K_DOWN))
    picker.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, OnlineHubState)
    return app.state


@pytest.mark.smoke
def test_settings_menu_cycles_hours_of_service():
    from freight_fate.app import App

    app = App()
    try:
        assert app.ctx.settings.hos_mode == "realistic"
        cat = open_settings_category(app, "Difficulty and hours of service")
        while not cat.items[cat.index].text.startswith("Hours of service"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.hos_mode == "relaxed"
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.hos_mode == "realistic"
        cat.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.hos_mode == "relaxed"
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_settings_menu_cycles_lane_keeping():
    from freight_fate.app import App

    app = App()
    try:
        assert app.ctx.settings.lane_keeping == "off"  # the realistic default
        cat = open_settings_category(app, "Driving assistance")
        while not cat.items[cat.index].text.startswith("Lane keeping"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.lane_keeping == "full"
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.lane_keeping == "partial"
        cat.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.lane_keeping == "full"
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_lane_keeping_row_speaks_its_consequence_not_a_bare_value():
    """A bare "off" would be read across from the rows around it, where off
    means less help. Here it means the hardest mode."""
    from freight_fate.app import App

    app = App()
    try:
        cat = open_settings_category(app, "Driving assistance")
        while not cat.items[cat.index].text.startswith("Lane keeping"):
            cat.handle_event(key_event(pygame.K_DOWN))
        assert cat.items[cat.index].text == (
            "Lane keeping: off, you hold the lane and take your own exits"
        )
        cat.handle_event(key_event(pygame.K_RETURN))
        assert cat.items[cat.index].text == (
            "Lane keeping: full, the truck holds the lane and takes your exits"
        )
        cat.handle_event(key_event(pygame.K_RETURN))
        assert "you steer with help" in cat.items[cat.index].text
    finally:
        app.shutdown()


def test_lane_keeping_row_explains_its_rename_to_returning_players():
    """A blind player cannot see a row change name. The row says it, built
    from the value they actually ended up with, and only for a settings file
    that really carried the old key."""
    from freight_fate.app import App

    app = App()
    spoken = []
    app.ctx.say = lambda text, interrupt=True, review=True: spoken.append(text)
    try:
        app.ctx.settings.lane_keeping = "full"
        app.ctx.settings.lane_keeping_rename_notice_left = 3
        cat = open_settings_category(app, "Driving assistance")
        while not cat.items[cat.index].text.startswith("Lane keeping"):
            cat.handle_event(key_event(pygame.K_DOWN))
        notice = [line for line in spoken if "used to be Lane drift" in line]
        assert notice
        assert "yours read off" in notice[-1]
        assert "the truck still holds the lane and takes your exits" in notice[-1]
        assert app.ctx.settings.lane_keeping_rename_notice_left == 2
    finally:
        app.shutdown()


def test_an_unreadable_lane_value_is_announced_not_taken_in_silence():
    """Falling back to full is right; falling back silently is not. It
    deletes the destination-exit decision, and nothing later in the drive
    would tell the player why their exits are being taken."""
    from freight_fate.app import App
    from freight_fate.states.main_menu import MainMenuState

    app = App()
    spoken = []
    app.ctx.say = lambda text, interrupt=True, review=True: spoken.append(text)
    try:
        app.ctx.settings.lane_keeping_unreadable = True
        MainMenuState(app.ctx).announce_entry()
        assert any("lane keeping setting could not be read" in line for line in spoken)
        assert any("Settings, Gameplay, Driving assistance" in line for line in spoken)
        # Said once, not on every trip back to the main menu.
        spoken.clear()
        MainMenuState(app.ctx).announce_entry()
        assert not [line for line in spoken if "lane keeping setting could not be read" in line]
    finally:
        app.shutdown()


def test_the_rename_notice_stops_after_its_budget():
    from freight_fate.app import App

    app = App()
    spoken = []
    app.ctx.say = lambda text, interrupt=True, review=True: spoken.append(text)
    try:
        app.ctx.settings.lane_keeping_rename_notice_left = 0
        cat = open_settings_category(app, "Driving assistance")
        while not cat.items[cat.index].text.startswith("Lane keeping"):
            cat.handle_event(key_event(pygame.K_DOWN))
        assert not [line for line in spoken if "used to be Lane drift" in line]
    finally:
        app.shutdown()


# -- the Variant B reorganization: the Gameplay submenu tree --------------------

# The four Gameplay subcategories and the row each must own, by the leading
# words of the spoken label. This doubles as the membership spec: a setting in
# the wrong screen, or missing from every screen, fails here.
GAMEPLAY_SUBCATEGORY_ROWS = {
    "assistance": [
        "Driving assistance preset",
        "Automatic emergency braking",
        "Lane-departure warning",
        "Stop-and-go assistance",
        "Lane centering assistance",
        "Descent speed control",
        "Exit speed assistance",
        "Destination approach assistance",
        "Planned rest-stop stopping assistance",
        "Curve speed assistance",
        "Route-transition assistance",
        "Latching pedals",
        "Predictive cruise",
        "Curve callouts",
        "Lane keeping",
        "Lane and edge cue prominence",
        "Back",
    ],
    "difficulty": [
        "Driving mode",
        "Hours of service",
        "Overspeed warning",
        "Back",
    ],
    "world": [
        "Weather source",
        "Traffic source",
        "Parking source",
        "Live weather controls calendar",
        "Enforcement presence",
        "Back",
    ],
    "controls": [
        "Units",
        "Transmission",
        "Automatic direction changes",
        "Controller",
        "Haptics",
        "Speed keeper",
        "Back",
    ],
}


def _rows_startwith(items):
    return [item.text for item in items]


def test_gameplay_is_a_parent_of_four_subcategories():
    from freight_fate.app import App
    from freight_fate.states.main_menu import GameplaySettingsState, SettingsState

    app = App()
    try:
        picker = SettingsState(app.ctx)
        app.push_state(picker)
        while picker.items[picker.index].text != "Gameplay":
            picker.handle_event(key_event(pygame.K_DOWN))
        picker.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, GameplaySettingsState)
        assert _rows_startwith(app.state.items) == [
            "Driving assistance",
            "Difficulty and hours of service",
            "World and traffic",
            "Controls",
            "Back",
        ]
    finally:
        app.shutdown()


@pytest.mark.parametrize("category", sorted(GAMEPLAY_SUBCATEGORY_ROWS))
def test_each_gameplay_subcategory_has_exactly_its_rows(category):
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsCategoryState

    app = App()
    try:
        cat = SettingsCategoryState(app.ctx, category)
        labels = _rows_startwith(cat.build_items())
        expected = GAMEPLAY_SUBCATEGORY_ROWS[category]
        assert len(labels) == len(expected)
        for actual, prefix in zip(labels, expected, strict=True):
            assert actual.startswith(prefix), (category, actual, prefix)
        # Every non-Back screen stays short enough to hold in the ear.
        assert len(labels) <= 12 or category == "assistance"
    finally:
        app.shutdown()


def _all_settings_rows(app):
    """Every settings row reachable in the whole Settings tree, as
    (screen, label, help) triples: the picker, the Gameplay parent, and each
    category screen. The Online hub is its own menu and out of scope here."""
    from freight_fate.states.main_menu import (
        GameplaySettingsState,
        SettingsCategoryState,
        SettingsState,
    )

    rows = []
    for screen, menu in (
        ("picker", SettingsState(app.ctx)),
        ("gameplay", GameplaySettingsState(app.ctx)),
    ):
        for item in menu.build_items():
            rows.append((screen, item.text, item.help))
    for category in (
        "assistance",
        "difficulty",
        "world",
        "controls",
        "audio",
        "speech",
        "updates",
        "reports",
    ):
        cat = SettingsCategoryState(app.ctx, category)
        for item in cat.build_items():
            rows.append((category, item.text, item.help))
    return rows


def test_exactly_one_speed_keeper_row_in_the_whole_tree():
    """The speed keeper was a single bool with two live rows (old Gameplay and
    Driving assistance). Exactly one row may drive it now, and it is in
    Controls."""
    from freight_fate.app import App

    app = App()
    try:
        rows = _all_settings_rows(app)
        speed_keeper_rows = [
            (screen, label) for screen, label, _ in rows if label.startswith("Speed keeper")
        ]
        assert len(speed_keeper_rows) == 1, speed_keeper_rows
        assert speed_keeper_rows[0][0] == "controls"
    finally:
        app.shutdown()


def test_no_dead_pointer_stub_rows_remain():
    """The old Gameplay carried a Lane keeping row that changed nothing and
    only said the real control "has moved". No such stub survives the reorg."""
    from freight_fate.app import App

    app = App()
    try:
        rows = _all_settings_rows(app)
        # The picker/Gameplay Online pointer is a real navigation row and is
        # allowed; a "has moved to ... settings" stub standing in for a control
        # is not.
        stubs = [
            (screen, label)
            for screen, label, help_text in rows
            if "has moved to" in (help_text or "").lower()
        ]
        assert stubs == []
        # And the specific dead row is gone: no Lane keeping row outside the
        # Driving assistance screen.
        lane_rows = [
            (screen, label) for screen, label, _ in rows if label.startswith("Lane keeping")
        ]
        assert lane_rows == [("assistance", lane_rows[0][1])]
    finally:
        app.shutdown()


def test_every_gameplay_setting_stays_reachable_after_the_split():
    """The reorg's biggest risk is orphaning a field: a row that used to live
    in flat Gameplay or in Speech and weather but now belongs to no screen.
    Each moved setting must be reachable from exactly its new screen."""
    from freight_fate.app import App

    app = App()
    try:
        rows = _all_settings_rows(app)
        by_screen = {}
        for screen, label, _ in rows:
            by_screen.setdefault(screen, []).append(label)

        def reachable(screen, prefix):
            return any(label.startswith(prefix) for label in by_screen.get(screen, []))

        # Moved out of flat Gameplay.
        assert reachable("controls", "Units")
        assert reachable("controls", "Transmission")
        assert reachable("controls", "Automatic direction changes")
        assert reachable("controls", "Controller")
        assert reachable("controls", "Haptics")
        assert reachable("controls", "Speed keeper")
        assert reachable("difficulty", "Driving mode")
        assert reachable("difficulty", "Hours of service")
        assert reachable("difficulty", "Overspeed warning")
        assert reachable("world", "Enforcement presence")
        # Moved out of Speech and weather.
        assert reachable("world", "Weather source")
        assert reachable("world", "Traffic source")
        assert reachable("world", "Parking source")
        assert reachable("world", "Live weather controls calendar")
        # The world-data rows no longer appear in Speech.
        assert not reachable("speech", "Weather source")
        assert not reachable("speech", "Traffic source")
        assert not reachable("speech", "Parking source")
        assert not reachable("speech", "Live weather controls calendar")
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_settings_menu_toggles_speed_keeper():
    from freight_fate.app import App

    app = App()
    try:
        assert app.ctx.settings.speed_keeper is True
        cat = open_settings_category(app, "Controls")
        while not cat.items[cat.index].text.startswith("Speed keeper"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.speed_keeper is False
        cat.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.speed_keeper is True
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_settings_menu_cycles_automatic_direction_changes():
    from freight_fate.app import App
    from freight_fate.settings import Settings

    app = App()
    try:
        assert app.ctx.settings.automatic_direction_changes == "simple"
        cat = open_settings_category(app, "Controls")
        while not cat.items[cat.index].text.startswith("Automatic direction changes"):
            cat.handle_event(key_event(pygame.K_DOWN))

        assert cat.current_help().startswith("Both styles change direction with a fresh press")
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.automatic_direction_changes == "deliberate"
        assert Settings.load().automatic_direction_changes == "deliberate"
        assert cat.items[cat.index].text == "Automatic direction changes: deliberate"

        cat.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.automatic_direction_changes == "simple"
    finally:
        app.shutdown()


def test_invalid_automatic_direction_setting_falls_back_to_simple():
    import json

    from freight_fate.settings import Settings

    settings = Settings()
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    settings.path.write_text(
        json.dumps({"automatic_direction_changes": "mystery"}), encoding="utf-8"
    )

    assert Settings.load().automatic_direction_changes == "simple"


def test_settings_menu_toggles_jake_voice_and_persists():
    from freight_fate.app import App
    from freight_fate.settings import Settings

    app = App()
    try:
        assert app.ctx.settings.jake_voice == "real"
        cat = open_settings_category(app, "Audio")
        while not cat.items[cat.index].text.startswith("Engine brake voice"):
            cat.handle_event(key_event(pygame.K_DOWN))

        assert cat.items[cat.index].text == "Engine brake voice: recorded"
        assert cat.current_help().startswith("Recorded is the real engine brake growl")
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.jake_voice == "classic"
        assert Settings.load().jake_voice == "classic"
        assert cat.items[cat.index].text == "Engine brake voice: classic"

        cat.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.jake_voice == "real"
        assert cat.items[cat.index].text == "Engine brake voice: recorded"
    finally:
        app.shutdown()


def test_invalid_jake_voice_setting_falls_back_to_real():
    import json

    from freight_fate.settings import Settings

    settings = Settings()
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    settings.path.write_text(json.dumps({"jake_voice": "mystery"}), encoding="utf-8")

    assert Settings.load().jake_voice == "real"


def test_settings_menu_saves_each_change():
    from freight_fate.app import App
    from freight_fate.settings import Settings

    app = App()
    try:
        cat = open_settings_category(app, "Controls")
        assert app.ctx.settings.imperial_units is True
        while not cat.items[cat.index].text.startswith("Units"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.imperial_units is False
        assert Settings.load().imperial_units is False
    finally:
        app.shutdown()


def test_live_weather_calendar_setting_defaults_on_and_persists():
    from freight_fate.app import App
    from freight_fate.settings import Settings

    app = App()
    try:
        assert app.ctx.settings.live_weather_controls_calendar is True
        cat = open_settings_category(app, "World and traffic")
        while not cat.items[cat.index].text.startswith("Live weather controls calendar"):
            cat.handle_event(key_event(pygame.K_DOWN))
        assert "today's real date" in cat.current_help()
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.live_weather_controls_calendar is False
        assert Settings.load().live_weather_controls_calendar is False
        assert cat.items[cat.index].text == "Live weather controls calendar: off"
    finally:
        app.shutdown()


def test_disabling_live_calendar_anchors_established_career_to_today(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.sim.season import date_text

    app = App()
    app.ctx.profile = Profile(name="Established Driver", game_hours=54.0)
    target = 200.0 * 24.0 + 17.0
    monkeypatch.setattr("freight_fate.sim.season.real_clock_game_hours", lambda: target)
    try:
        original_game_hours = app.ctx.profile.game_hours
        cat = open_settings_category(app, "World and traffic")
        while not cat.items[cat.index].text.startswith("Live weather controls calendar"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))

        assert app.ctx.settings.live_weather_controls_calendar is False
        assert app.ctx.profile.game_hours == original_game_hours
        assert date_text(app.ctx.profile.calendar_game_hours) == date_text(target)
        assert app.ctx.profile.calendar_game_hours % 24 == original_game_hours % 24
    finally:
        app.shutdown()


def test_disabling_live_calendar_keeps_new_career_on_march_21(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile

    app = App()
    app.ctx.profile = Profile(name="Brand New Driver")
    monkeypatch.setattr("freight_fate.sim.season.real_clock_game_hours", lambda: 200.0 * 24.0)
    try:
        cat = open_settings_category(app, "World and traffic")
        while not cat.items[cat.index].text.startswith("Live weather controls calendar"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.profile.calendar_offset_days == 0
        assert app.ctx.profile.calendar_game_hours == 6.0
    finally:
        app.shutdown()


def test_settings_menu_volume_survives_new_app_session():
    from freight_fate.app import App
    from freight_fate.settings import Settings

    app = App()
    try:
        cat = open_settings_category(app, "Audio")
        assert cat.title == "Audio"
        while not cat.items[cat.index].text.startswith("Music volume"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RIGHT))
        assert app.ctx.settings.music_volume == 0.6
        assert Settings.load().music_volume == 0.6
        while not cat.items[cat.index].text.startswith("Weather sounds volume"):
            cat.handle_event(key_event(pygame.K_UP))
        cat.handle_event(key_event(pygame.K_RIGHT))
        assert app.ctx.settings.weather_volume == 0.75
        assert Settings.load().weather_volume == 0.75
        cat.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.weather_volume == 0.65
        assert Settings.load().weather_volume == 0.65
    finally:
        app.shutdown()

    next_app = App()
    try:
        assert next_app.ctx.settings.music_volume == 0.6
        assert next_app.ctx.audio.music_volume == 0.6
        assert next_app.ctx.settings.weather_volume == 0.65
        assert next_app.ctx.audio.weather_volume == 0.65
    finally:
        next_app.shutdown()


def test_settings_menu_f1_has_help_for_every_item():
    from freight_fate.app import App
    from freight_fate.states.main_menu import (
        GameplaySettingsState,
        SettingsCategoryState,
        SettingsState,
    )

    app = App()
    try:
        for menu in (SettingsState(app.ctx), GameplaySettingsState(app.ctx)):
            menu.items = menu.build_items()
            for i, item in enumerate(menu.items):
                menu.index = i
                text = menu.current_help()
                assert text == (item.help or f"{item.text}.")
                assert menu.intro_help not in text
        for category in (
            "assistance",
            "difficulty",
            "world",
            "controls",
            "audio",
            "speech",
            "updates",
            "reports",
        ):
            cat = SettingsCategoryState(app.ctx, category)
            cat.items = cat.build_items()
            for i, item in enumerate(cat.items):
                cat.index = i
                text = cat.current_help()
                assert text == (item.help or f"{item.text}.")
                assert cat.intro_help not in text
    finally:
        app.shutdown()


def test_haptics_help_explains_road_seam_feedback():
    from freight_fate.app import App

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        cat = open_settings_category(app, "Controls")
        while not cat.items[cat.index].text.startswith("Haptics"):
            cat.handle_event(key_event(pygame.K_DOWN))

        spoken.clear()
        cat.handle_event(key_event(pygame.K_F1))
        assert any("road seams" in text for text in spoken)
    finally:
        app.shutdown()


def test_settings_menu_uses_category_submenus():
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsCategoryState, SettingsState

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        picker = SettingsState(app.ctx)
        app.push_state(picker)
        labels = [item.text for item in picker.items]
        assert labels == [
            "Gameplay",
            "Audio",
            "Speech",
            "Online",
            "Updates",
            "Problem reports",
            "Back",
        ]

        while picker.items[picker.index].text != "Audio":
            picker.handle_event(key_event(pygame.K_DOWN))
        picker.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, SettingsCategoryState)
        assert app.state.title == "Audio"
        assert app.state.items[app.state.index].text.startswith("Master volume")

        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, SettingsState)

        spoken.clear()
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert "Settings saved." in spoken
    finally:
        app.shutdown()


def test_driving_assistance_preset_keyboard_path_and_custom_transition():
    from freight_fate.app import App
    from freight_fate.settings import Settings

    app = App()
    spoken = []
    utterances = []

    def fake_say(text, interrupt=True, review=True):
        spoken.append(text)
        utterances.append((text, interrupt))

    app.ctx.say = fake_say
    try:
        cat = open_settings_category(app, "Driving assistance")
        # The shipped defaults now ARE the realistic preset, field for field,
        # so the row can finally say so honestly rather than reading Custom
        # over a combination no preset described.
        assert cat.items[0].text == "Driving assistance preset: Realistic"
        assert app.ctx.settings.lane_keeping == "off"
        cat.handle_event(key_event(pygame.K_RIGHT))
        assert app.ctx.settings.driving_assistance_preset == "balanced"
        assert app.ctx.settings.lane_centering_assist is True
        assert app.ctx.settings.time_scale == 10.0
        assert app.ctx.settings.hos_mode == "realistic"
        cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.driving_assistance_preset == "custom"
        assert cat.items[0].text == "Driving assistance preset: Custom"
        loaded = Settings.load()
        assert loaded.driving_assistance_preset == "custom"
        assert any("Automatic emergency braking: off" in line for line in spoken)
        assert "Driving assistance preset: Custom." in spoken
        original_index = cat.index
        cat.handle_event(key_event(pygame.K_HOME))
        cat.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.driving_assistance_preset == "all"
        assert cat.items[cat.index].text == "Driving assistance preset: All assists"
        cat.handle_event(key_event(pygame.K_RIGHT))
        assert app.ctx.settings.driving_assistance_preset == "realistic"
        assert original_index == 1

        # A toggle that lands on Custom queues the preset note after the
        # spoken on/off state instead of interrupting it, and later toggles
        # while already Custom do not repeat the note.
        spoken.clear()
        utterances.clear()
        cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.driving_assistance_preset == "custom"
        state_line = next(
            i for i, line in enumerate(spoken) if "Automatic emergency braking: off" in line
        )
        assert state_line < spoken.index("Driving assistance preset: Custom.")
        assert ("Driving assistance preset: Custom.", False) in utterances
        spoken.clear()
        cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.driving_assistance_preset == "custom"
        assert any("Lane-departure warning: off" in line for line in spoken)
        assert "Driving assistance preset: Custom." not in spoken
    finally:
        app.shutdown()


def test_driving_assistance_presets_apply_complete_mappings():
    from freight_fate.settings import DRIVING_ASSIST_FIELDS, DRIVING_ASSIST_PRESETS, Settings

    settings = Settings()
    for preset, expected in DRIVING_ASSIST_PRESETS.items():
        settings.apply_driving_assistance_preset(preset)
        assert tuple(getattr(settings, field) for field in DRIVING_ASSIST_FIELDS) == expected
        assert settings.driving_assistance_preset == preset


def test_selected_stop_assist_keyboard_toggle_persists_outside_presets():
    from freight_fate.app import App
    from freight_fate.settings import Settings

    app = App()
    spoken = []
    app.ctx.say = lambda text, **_kwargs: spoken.append(text)
    try:
        assert app.ctx.settings.selected_stop_assist is False
        cat = open_settings_category(app, "Driving assistance")
        while not cat.items[cat.index].text.startswith("Planned rest-stop stopping assistance"):
            cat.handle_event(key_event(pygame.K_DOWN))
        assert cat.items[cat.index].text.endswith(": off")
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.selected_stop_assist is True
        assert cat.items[cat.index].text.endswith(": on")
        assert "Planned rest-stop stopping assistance: on." in spoken[-1]
        assert Settings.load().selected_stop_assist is True

        cat.handle_event(key_event(pygame.K_HOME))
        cat.handle_event(key_event(pygame.K_RIGHT))
        assert app.ctx.settings.selected_stop_assist is True
    finally:
        app.shutdown()


def test_a_fresh_install_is_the_realistic_preset():
    """The shipped defaults ARE the realistic preset, and the row says so.

    For months the row read "Realistic" while lane keeping was fully
    automated, because the preset could not see that field -- so a player
    reading the row believed they were driving the realistic ruleset. This
    makes the truck match the label those players have been reading, rather
    than renaming the label to match a setting nobody chose.
    """
    from freight_fate.settings import Settings

    settings = Settings()
    assert settings.lane_keeping == "off"
    assert settings.lane_is_manual()
    assert not settings.lane_is_automated()
    assert settings.driving_assistance_preset == "realistic"
    assert settings.refresh_driving_assistance_preset() == "realistic"


def test_an_unreadable_lane_value_still_falls_back_to_full_not_the_default():
    """A corrupt value is not a fresh install. We do not know what the player
    chose, so the fallback stays the most assisted mode and announces itself
    -- handing a blind player a manual steering task they never opted into is
    the worse failure. A new career, by contrast, gets the documented default.
    """
    from freight_fate.settings import LANE_KEEPING_FALLBACK

    assert LANE_KEEPING_FALLBACK == "full"


def test_every_preset_owns_lane_keeping():
    """Lane keeping used to sit outside the presets, so All assists forced it
    and no other preset could hand it back. Each preset now names a value."""
    from freight_fate.settings import Settings

    settings = Settings()
    for preset, expected in (("all", "full"), ("balanced", "partial"), ("realistic", "off")):
        settings.apply_driving_assistance_preset(preset)
        assert settings.lane_keeping == expected
        assert settings.driving_assistance_preset == preset


def test_the_preset_row_can_no_longer_lie_about_lane_keeping():
    """Regression: the row read "Realistic" over fully automated lane keeping
    -- the one row a player checks to learn how much the truck is doing could
    not see the biggest thing it was doing."""
    from freight_fate.settings import Settings

    settings = Settings()
    settings.apply_driving_assistance_preset("realistic")
    assert settings.refresh_driving_assistance_preset() == "realistic"
    settings.lane_keeping = "full"
    assert settings.refresh_driving_assistance_preset() == "custom"
    settings.apply_driving_assistance_preset("all")
    assert settings.refresh_driving_assistance_preset() == "all"
    settings.lane_keeping = "off"
    assert settings.refresh_driving_assistance_preset() == "custom"


def test_lane_keeping_row_updates_the_preset_row(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.apply_driving_assistance_preset("all")
        cat = open_settings_category(app, "Driving assistance")
        while not cat.items[cat.index].text.startswith("Lane keeping"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.lane_keeping != "full"
        assert app.ctx.settings.driving_assistance_preset == "custom"
    finally:
        app.shutdown()


def test_driving_assistance_presets_survive_reload():
    from freight_fate.settings import DRIVING_ASSIST_FIELDS, DRIVING_ASSIST_PRESETS, Settings

    for preset, expected in DRIVING_ASSIST_PRESETS.items():
        settings = Settings()
        settings.apply_driving_assistance_preset(preset)
        settings.save()
        loaded = Settings.load()
        assert loaded.driving_assistance_preset == preset
        assert tuple(getattr(loaded, field) for field in DRIVING_ASSIST_FIELDS) == expected


def test_legacy_settings_preserve_lane_keeping_choice():
    import json

    from freight_fate.settings import Settings

    settings = Settings()
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    settings.path.write_text(json.dumps({"steering_assist": "off"}), encoding="utf-8")
    loaded = Settings.load()
    # Legacy "off" was the truck holding the lane for you: "full" now.
    assert loaded.lane_keeping == "full"
    assert loaded.lane_departure_warning is False
    assert loaded.automatic_emergency_braking is False
    assert loaded.stop_and_go_assist is False
    assert loaded.descent_speed_control == "off"
    assert loaded.driving_assistance_preset == "custom"


@pytest.mark.parametrize(
    ("legacy", "expected"),
    (("off", "full"), ("light", "partial"), ("realistic", "off")),
)
def test_every_legacy_lane_value_migrates_without_changing_difficulty(legacy, expected):
    """The whole point of the rename: the words move, the truck does not."""
    import json

    from freight_fate.settings import Settings

    settings = Settings()
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    settings.path.write_text(
        json.dumps({"steering_assist": legacy, "driving_assistance_preset": "custom"}),
        encoding="utf-8",
    )
    loaded = Settings.load()
    assert loaded.lane_keeping == expected
    # A player who saw the old name is owed the explanation, and only them.
    assert loaded.lane_keeping_rename_notice_left == 3


def test_unknown_lane_value_falls_back_to_full_and_says_so():
    """Landing on "off" instead would start drift, rumble strips, off-road
    damage AND stop granting the destination exit -- with no audible cause."""
    import json

    from freight_fate.settings import Settings

    settings = Settings()
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    settings.path.write_text(
        json.dumps({"steering_assist": "sideways", "driving_assistance_preset": "custom"}),
        encoding="utf-8",
    )
    loaded = Settings.load()
    assert loaded.lane_keeping == "full"
    assert loaded.lane_keeping_unreadable is True
    # Nothing to explain about a rename that never applied to this value.
    assert loaded.lane_keeping_rename_notice_left == 0


def test_a_fresh_install_hears_no_rename_notice():
    from freight_fate.settings import Settings

    settings = Settings()
    if settings.path.exists():
        settings.path.unlink()
    loaded = Settings.load()
    assert loaded.lane_keeping == "off"  # the realistic default, not the fallback
    assert loaded.lane_keeping_rename_notice_left == 0
    assert loaded.lane_keeping_unreadable is False


def test_settings_still_write_the_legacy_lane_key_for_1_8_builds():
    """A 1.8.x build shares this settings.json and still reads
    ``steering_assist``; dropping the key would reset it to its own default
    and change what the truck does over there."""
    import json

    from freight_fate.settings import LANE_KEEPING_TO_LEGACY, Settings

    for mode, legacy in LANE_KEEPING_TO_LEGACY.items():
        settings = Settings()
        settings.lane_keeping = mode
        settings.save()
        written = json.loads(settings.path.read_text(encoding="utf-8"))
        assert written["lane_keeping"] == mode
        assert written["steering_assist"] == legacy


def test_exactly_one_driving_assistance_preset_selector():
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsCategoryState

    app = App()
    try:
        menu = SettingsCategoryState(app.ctx, "assistance")
        labels = [item.text for item in menu.build_items()]
        assert sum(label.startswith("Driving assistance preset:") for label in labels) == 1
        assert not any(
            "player style" in label.lower() or "descent preset" in label.lower() for label in labels
        )
    finally:
        app.shutdown()


def test_settings_saved_is_heard_and_not_cancelled_by_the_main_menu_welcome(monkeypatch):
    """Backing all the way out of Settings must not swallow "Settings saved.".

    SettingsState.go_back used to speak "Settings saved." and then pop back to
    the main menu, whose own entry announcement -- interrupt=True by default
    -- cancelled it before a screen reader finished the word "saved". A test
    that only checks the text is present in what was spoken (as the sibling
    test above does) cannot see that: the text was always in the list, it was
    just never actually heard. This asserts order and each line's interrupt
    flag, so "Settings saved." must be the last line spoken and the one that
    wins, not the one cut off.
    """
    from freight_fate.app import App
    from freight_fate.states.main_menu import MainMenuState, SettingsState

    spoken: list[tuple[str, bool]] = []
    app = App()
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken, with_interrupt=True))
    try:
        app.push_state(MainMenuState(app.ctx))
        while app.state.items[app.state.index].text != "Settings":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, SettingsState)

        spoken.clear()
        app.state.handle_event(key_event(pygame.K_ESCAPE))

        assert spoken, "nothing was spoken on the way out of Settings"
        text, interrupt = spoken[-1]
        assert text == "Settings saved."
        assert interrupt is True
    finally:
        app.shutdown()


def test_speech_setting_adjustment_previews_adjusted_voice(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsCategoryState

    class PreviewSpeech:
        supports_rate = True
        supports_pitch = False
        supports_volume = False
        event_backend_name = "none"

        def __init__(self):
            self.previews = []

        def event_backend_options(self):
            return []

        def select_event_backend(self, _name):
            return None

        def configure(self, **_kwargs):
            return None

        def voice_names(self):
            return []

        def say_adjustment_preview(self, setting, text, interrupt=True):
            self.previews.append((setting, text, interrupt))
            return True

        def shutdown(self):
            return None

    app = App()
    fallback_spoken = []
    preview = PreviewSpeech()
    monkeypatch.setattr(app.ctx, "speech", preview)
    monkeypatch.setattr(app, "speech", preview)
    monkeypatch.setattr(app.ctx, "say", speech_stub(fallback_spoken))
    try:
        menu = SettingsCategoryState(app.ctx, "speech")
        app.push_state(menu)
        while not app.state.items[app.state.index].text.startswith("Speech rate"):
            app.state.handle_event(key_event(pygame.K_DOWN))

        fallback_spoken.clear()
        app.state.handle_event(key_event(pygame.K_RIGHT))

        assert preview.previews
        setting, text, interrupt = preview.previews[-1]
        assert setting == "speech_rate"
        assert text.startswith("Speech rate:")
        assert interrupt is True
        assert fallback_spoken == []
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_online_sharing_label_tracks_identity_freshness():
    """The sharing label re-checks the identity file on every read.

    Regression: the configured check was captured once at menu build, so the
    label said "on" while sharing was actually dormant (no credentials), and
    stayed "not set up" after setup completed until the menu was rebuilt.
    """
    from freight_fate.app import App
    from freight_fate.online_presence import OnlineIdentity

    app = App()
    try:
        cat = open_online_hub_from_settings(app)
        while not cat.items[cat.index].text.startswith("Profile sharing"):
            cat.handle_event(key_event(pygame.K_DOWN))
        item = cat.items[cat.index]
        # Before setup the item is the driver-profile gateway; the sharing
        # wording only appears once credentials exist.
        assert item.text == "Profile sharing: not set up"

        # Credentials appear on disk (setup completing) with no menu rebuild:
        # the same MenuItem must immediately report the real on/off state.
        OnlineIdentity(driver_id="road-star-abcd1234", driver_token="t" * 68).save()
        assert item.text in (
            "Profile sharing: on",
            "Profile sharing: off",
        )
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_online_menu_keeps_profile_sharing_and_private_cloud_backup_separate():
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    app.ctx.say = speech_stub(spoken)
    try:
        menu = open_online_hub_from_settings(app)
        labels = [item.text for item in menu.items]
        assert labels == [
            "Drivers board",
            "Online services: on",
            "Set up orinks.net account",
            "Profile sharing: not set up",
            "Back up saves to your orinks.net account: not set up",
            "Restore a cloud backup",
            "Share notable deliveries to Mastodon: not set up",
            "Link a Mastodon account",
            "Discord presence: on",
            "Back",
        ]
        assert not any("shared career" in label.lower() for label in labels)

        for expected in labels[1:]:
            menu.handle_event(key_event(pygame.K_DOWN))
            assert menu.items[menu.index].text == expected
        assert any("Profile sharing: not set up" in text for text in spoken)
        assert any(
            "Back up saves to your orinks.net account: not set up" in text for text in spoken
        )
    finally:
        app.shutdown()


def test_problem_reports_reads_out_the_active_log_file(tmp_path, monkeypatch):
    """The log already records every spoken line; this screen is the only thing
    that tells a player it exists and where to find it."""
    from freight_fate import app as app_module
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsCategoryState

    log_path = tmp_path / "logs" / "game.log"
    log_path.parent.mkdir()
    log_path.write_text("session", encoding="utf-8")
    (tmp_path / "logs" / "game.prev.log").write_text("previous", encoding="utf-8")
    monkeypatch.setattr(app_module, "_log_file", log_path)

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        cat = SettingsCategoryState(app.ctx, "reports")
        app.push_state(cat)
        assert cat.title == "Problem reports"
        assert [item.text for item in cat.items] == ["Where the game log is saved", "Back"]

        spoken.clear()
        cat.handle_event(key_event(pygame.K_RETURN))
        said = " ".join(spoken)
        assert str(log_path) in said
        assert "game.prev.log" in said
        assert "never sends them anywhere" in said  # local-only is stated, not implied

        # A low-vision player reading the window sees the same path.
        assert any(str(log_path) in line for line in cat.lines())

        # Left and right are for stepping values; this row has none to step.
        cat.handle_event(key_event(pygame.K_RIGHT))
        cat.handle_event(key_event(pygame.K_LEFT))
        assert cat.items[cat.index].text == "Where the game log is saved"
    finally:
        app.shutdown()


def test_problem_reports_is_honest_when_no_log_is_being_written():
    """A source checkout writes no file; the screen must not name one anyway."""
    from freight_fate import app as app_module
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsCategoryState

    app = App()
    try:
        original = app_module._log_file
        app_module._log_file = None
        try:
            said = " ".join(SettingsCategoryState(app.ctx, "reports")._log_location_lines())
        finally:
            app_module._log_file = original
        assert "not writing a log file" in said
        assert "Packaged downloads always write one" in said
    finally:
        app.shutdown()


# -- the one-shot "where your settings moved" notice ---------------------------


def open_gameplay_parent(app):
    """Open Settings then the Gameplay parent, returning its state."""
    from freight_fate.states.main_menu import GameplaySettingsState, SettingsState

    picker = SettingsState(app.ctx)
    app.push_state(picker)
    while picker.items[picker.index].text != "Gameplay":
        picker.handle_event(key_event(pygame.K_DOWN))
    picker.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, GameplaySettingsState)
    return app.state


def test_gameplay_reorg_notice_fires_once_for_a_pre_reorg_settings_file():
    """A returning player cannot see the menu change shape, so the Gameplay
    submenu says once where their settings moved -- then never again."""
    import json

    from freight_fate.app import App
    from freight_fate.settings import Settings

    settings = Settings()
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    # A settings file from before the reorg carries no settings_version key.
    settings.path.write_text(json.dumps({"imperial_units": True}), encoding="utf-8")

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        assert app.ctx.settings.gameplay_reorg_notice_pending is True
        gameplay = open_gameplay_parent(app)
        assert any("Gameplay is now a category" in line for line in spoken)
        assert any("Weather, traffic, and parking sources moved" in line for line in spoken)
        assert any("Nothing about your settings changed" in line for line in spoken)
        # Cleared, and persisted so a restart does not replay it.
        assert app.ctx.settings.gameplay_reorg_notice_pending is False
        assert Settings.load().gameplay_reorg_notice_pending is False

        spoken.clear()
        gameplay.enter()  # re-reveal the same screen
        assert not [line for line in spoken if "Gameplay is now a category" in line]
    finally:
        app.shutdown()


def test_a_fresh_install_hears_no_gameplay_reorg_notice():
    """Nothing moved for a brand-new player, so the notice never fires."""
    from freight_fate.app import App
    from freight_fate.settings import Settings

    settings = Settings()
    if settings.path.exists():
        settings.path.unlink()

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        assert app.ctx.settings.gameplay_reorg_notice_pending is False
        open_gameplay_parent(app)
        assert not [line for line in spoken if "Gameplay is now a category" in line]
    finally:
        app.shutdown()


def test_a_current_version_settings_file_hears_no_notice():
    import json

    from freight_fate.settings import SETTINGS_VERSION, Settings

    settings = Settings()
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    settings.path.write_text(json.dumps({"settings_version": SETTINGS_VERSION}), encoding="utf-8")
    assert Settings.load().gameplay_reorg_notice_pending is False


def test_settings_version_is_written_to_disk():
    from freight_fate.settings import SETTINGS_VERSION, Settings

    settings = Settings()
    settings.save()
    import json

    written = json.loads(settings.path.read_text(encoding="utf-8"))
    assert written["settings_version"] == SETTINGS_VERSION
