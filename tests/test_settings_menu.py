import pygame
import pytest


def key_event(key, unicode="", mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode, mod=mod)


def open_settings_category(app, label):
    from freight_fate.states.main_menu import SettingsCategoryState, SettingsState

    picker = SettingsState(app.ctx)
    app.push_state(picker)
    while picker.items[picker.index].text != label:
        picker.handle_event(key_event(pygame.K_DOWN))
    picker.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, SettingsCategoryState)
    return app.state


@pytest.mark.smoke
def test_settings_menu_cycles_hours_of_service():
    from freight_fate.app import App

    app = App()
    try:
        assert app.ctx.settings.hos_mode == "realistic"
        cat = open_settings_category(app, "Gameplay")
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
def test_settings_menu_cycles_lane_drift():
    from freight_fate.app import App

    app = App()
    try:
        assert app.ctx.settings.steering_assist == "realistic"
        cat = open_settings_category(app, "Gameplay")
        while not cat.items[cat.index].text.startswith("Lane drift"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.steering_assist == "off"
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.steering_assist == "light"
        cat.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.steering_assist == "off"
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_settings_menu_cycles_automatic_direction_changes():
    from freight_fate.app import App
    from freight_fate.settings import Settings

    app = App()
    try:
        assert app.ctx.settings.automatic_direction_changes == "simple"
        cat = open_settings_category(app, "Gameplay")
        while not cat.items[cat.index].text.startswith("Automatic direction changes"):
            cat.handle_event(key_event(pygame.K_DOWN))

        assert cat.current_help().startswith("Simple changes between forward and reverse")
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


def test_settings_menu_saves_each_change():
    from freight_fate.app import App
    from freight_fate.settings import Settings

    app = App()
    try:
        cat = open_settings_category(app, "Gameplay")
        assert app.ctx.settings.imperial_units is True
        while not cat.items[cat.index].text.startswith("Units"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.imperial_units is False
        assert Settings.load().imperial_units is False
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
    from freight_fate.states.main_menu import SettingsCategoryState, SettingsState

    app = App()
    try:
        picker = SettingsState(app.ctx)
        picker.items = picker.build_items()
        for i, item in enumerate(picker.items):
            picker.index = i
            text = picker.current_help()
            assert text == (item.help or f"{item.text}.")
            assert picker.intro_help not in text
        for category in ("gameplay", "audio", "speech", "updates"):
            cat = SettingsCategoryState(app.ctx, category)
            cat.items = cat.build_items()
            for i, item in enumerate(cat.items):
                cat.index = i
                text = cat.current_help()
                assert text == (item.help or f"{item.text}.")
                assert cat.intro_help not in text
    finally:
        app.shutdown()


def test_settings_menu_uses_category_submenus():
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsCategoryState, SettingsState

    app = App()
    spoken = []
    app.ctx.say = lambda text, interrupt=True: spoken.append(text)
    try:
        picker = SettingsState(app.ctx)
        app.push_state(picker)
        labels = [item.text for item in picker.items]
        assert labels == [
            "Gameplay",
            "Driving assistance",
            "Audio",
            "Speech and weather",
            "Online",
            "Updates",
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
    app.ctx.say = lambda text, interrupt=True: spoken.append(text)
    try:
        cat = open_settings_category(app, "Driving assistance")
        assert cat.items[0].text == "Driving assistance preset: Realistic"
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
    finally:
        app.shutdown()


def test_driving_assistance_presets_apply_complete_mappings():
    from freight_fate.settings import DRIVING_ASSIST_FIELDS, DRIVING_ASSIST_PRESETS, Settings

    settings = Settings()
    for preset, expected in DRIVING_ASSIST_PRESETS.items():
        settings.apply_driving_assistance_preset(preset)
        assert tuple(getattr(settings, field) for field in DRIVING_ASSIST_FIELDS) == expected
        assert settings.driving_assistance_preset == preset


def test_driving_assistance_presets_survive_reload():
    from freight_fate.settings import DRIVING_ASSIST_FIELDS, DRIVING_ASSIST_PRESETS, Settings

    for preset, expected in DRIVING_ASSIST_PRESETS.items():
        settings = Settings()
        settings.apply_driving_assistance_preset(preset)
        settings.save()
        loaded = Settings.load()
        assert loaded.driving_assistance_preset == preset
        assert tuple(getattr(loaded, field) for field in DRIVING_ASSIST_FIELDS) == expected


def test_legacy_settings_preserve_lane_drift_choice():
    import json

    from freight_fate.settings import Settings

    settings = Settings()
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    settings.path.write_text(json.dumps({"steering_assist": "off"}), encoding="utf-8")
    loaded = Settings.load()
    assert loaded.steering_assist == "off"
    assert loaded.lane_departure_warning is False
    assert loaded.automatic_emergency_braking is False
    assert loaded.stop_and_go_assist is False
    assert loaded.descent_speed_control == "off"
    assert loaded.driving_assistance_preset == "custom"


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
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: fallback_spoken.append(text))
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
        cat = open_settings_category(app, "Online")
        while not cat.items[cat.index].text.startswith("Driver profile"):
            cat.handle_event(key_event(pygame.K_DOWN))
        item = cat.items[cat.index]
        # Before setup the item is the driver-profile gateway; the sharing
        # wording only appears once credentials exist.
        assert item.text == "Driver profile: not set up"

        # Credentials appear on disk (setup completing) with no menu rebuild:
        # the same MenuItem must immediately report the real on/off state.
        OnlineIdentity(driver_id="road-star-abcd1234", driver_token="t" * 68).save()
        assert item.text in (
            "Share on the drivers board: on",
            "Share on the drivers board: off",
        )
    finally:
        app.shutdown()
