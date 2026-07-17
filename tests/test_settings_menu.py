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
        assert app.ctx.settings.steering_assist == "off"
        cat = open_settings_category(app, "Gameplay")
        while not cat.items[cat.index].text.startswith("Lane drift"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.steering_assist == "light"
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.steering_assist == "realistic"
        cat.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.steering_assist == "light"
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_settings_menu_toggles_speed_keeper():
    from freight_fate.app import App

    app = App()
    try:
        assert app.ctx.settings.speed_keeper is True
        cat = open_settings_category(app, "Gameplay")
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


def test_live_weather_calendar_setting_defaults_on_and_persists():
    from freight_fate.app import App
    from freight_fate.settings import Settings

    app = App()
    try:
        assert app.ctx.settings.live_weather_controls_calendar is True
        cat = open_settings_category(app, "Speech and weather")
        while not cat.items[cat.index].text.startswith("Live weather controls calendar"):
            cat.handle_event(key_event(pygame.K_DOWN))
        assert "today's real date" in cat.current_help()
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.live_weather_controls_calendar is False
        assert Settings.load().live_weather_controls_calendar is False
        assert cat.items[cat.index].text == "Live weather controls calendar: off"
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
        assert labels == ["Gameplay", "Audio", "Speech and weather", "Online", "Updates", "Back"]

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
    app.ctx.say = lambda text, interrupt=True: spoken.append(text)
    try:
        menu = open_settings_category(app, "Online")
        labels = [item.text for item in menu.items]
        assert labels == [
            "Set up orinks.net account",
            "Profile sharing: not set up",
            "Back up saves to your orinks.net account: not set up",
            "Restore a cloud backup",
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
