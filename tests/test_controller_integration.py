"""Controller wired end to end: context gating, driving analog, settings menu."""

import pygame
from test_controller import FakeJoystick, FakeModule
from test_driving_features import key_event, quiet_trip, start_drive

from freight_fate.controller import (
    AXIS_LEFT_TRIGGER,
    AXIS_LEFT_X,
    AXIS_RIGHT_TRIGGER,
)


def _attach(app, **kwargs):
    """Attach a fake controller to the running app's manager."""
    js = FakeJoystick(**kwargs)
    app.controller.joystick = js
    app.controller._instance_id = js.get_instance_id()
    # Trust the triggers immediately for tests (they rest at -1 on real pads).
    app.controller._trigger_seen.update({AXIS_LEFT_TRIGGER, AXIS_RIGHT_TRIGGER})
    return js


def test_context_input_neutral_when_controller_disabled():
    from freight_fate.app import App

    app = App()
    try:
        js = _attach(app, axes={AXIS_RIGHT_TRIGGER: 1.0})
        app.ctx.settings.controller_enabled = True
        assert app.ctx.controller_input().throttle > 0.9
        app.ctx.settings.controller_enabled = False
        assert app.ctx.controller_input().throttle == 0.0
        assert js is app.controller.joystick
    finally:
        app.shutdown()


def test_context_rumble_respects_settings():
    from freight_fate.app import App

    app = App()
    try:
        js = _attach(app)
        app.ctx.settings.controller_enabled = True
        app.ctx.settings.controller_rumble = True
        app.ctx.rumble(0.5, 0.5, 200)
        assert js.rumbles == [(0.5, 0.5, 200)]

        js.rumbles.clear()
        app.ctx.settings.controller_rumble = False
        app.ctx.rumble(0.5, 0.5, 200)
        assert js.rumbles == []

        app.ctx.settings.controller_rumble = True
        app.ctx.settings.controller_enabled = False
        app.ctx.rumble(0.5, 0.5, 200)
        assert js.rumbles == []
    finally:
        app.shutdown()


def test_driving_state_declares_driving_mode():
    from freight_fate.states.base import State
    from freight_fate.states.driving import DrivingState

    assert State.controller_mode == "menu"
    assert DrivingState.controller_mode == "driving"


def test_analog_trigger_drives_the_truck_forward():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.handle_event(key_event(pygame.K_e))  # start engine
        assert driving.truck.engine_on
        driving.truck.transmission.automatic = True
        driving.truck.set_air_ready(parking_brake=False)
        app.ctx.settings.controller_enabled = True
        _attach(app, axes={AXIS_RIGHT_TRIGGER: 1.0, AXIS_LEFT_TRIGGER: -1.0})

        for _ in range(40):
            driving.update(1 / 30)

        assert driving.truck.throttle > 0.5
        assert driving.truck.speed_mph > 1.0
    finally:
        app.shutdown()


def test_analog_left_stick_sets_lane_steering():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        app.ctx.settings.controller_enabled = True
        app.ctx.settings.steering_assist = "light"
        _attach(app, axes={AXIS_LEFT_X: -1.0,
                           AXIS_LEFT_TRIGGER: -1.0,
                           AXIS_RIGHT_TRIGGER: -1.0})

        driving.update(1 / 30)
        assert driving.lane.steering < -0.9
    finally:
        app.shutdown()


def test_controller_button_routes_through_app_loop_translation():
    """The app translates a joystick button into the key the state expects."""
    from freight_fate.app import App
    from freight_fate.states.main_menu import MainMenuState

    app = App()
    try:
        _attach(app)
        app.push_state(MainMenuState(app.ctx))
        menu = app.state
        start_index = menu.index
        mode = getattr(menu, "controller_mode", "menu")
        # Simulate the loop body: a down-hat becomes K_DOWN, A becomes Enter.
        for ev in app.controller.translate(
                pygame.event.Event(pygame.JOYHATMOTION, value=(0, -1)), mode):
            menu.handle_event(ev)
        assert menu.index == (start_index + 1) % len(menu.items)
    finally:
        app.shutdown()


def test_settings_menu_toggles_controller_options():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.main_menu import SettingsCategoryState

    app = App()
    try:
        app.ctx.profile = Profile(name="Pad")
        app.ctx.settings.controller_enabled = True
        app.ctx.settings.controller_rumble = True
        app.push_state(SettingsCategoryState(app.ctx, "gameplay"))
        menu = app.state

        labels = [item.text for item in menu.items]
        assert any(label.startswith("Controller:") for label in labels)
        assert any(label.startswith("Controller rumble:") for label in labels)

        while not menu.items[menu.index].text.startswith("Controller:"):
            menu.handle_event(key_event(pygame.K_DOWN))
        menu.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.controller_enabled is False

        while not menu.items[menu.index].text.startswith("Controller rumble:"):
            menu.handle_event(key_event(pygame.K_DOWN))
        menu.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.controller_rumble is False
    finally:
        app.shutdown()


def test_settings_menu_cycles_controller_device():
    from freight_fate.app import App
    from freight_fate.controller import ControllerManager
    from freight_fate.models.profile import Profile
    from freight_fate.states.main_menu import SettingsCategoryState

    app = App()
    try:
        a = FakeJoystick(name="Pad A", instance_id=1)
        b = FakeJoystick(name="Pad B", instance_id=2)
        mgr = ControllerManager(joystick_module=FakeModule([a, b]))
        mgr.start()
        app.controller = mgr
        app.ctx.controller = mgr
        app.ctx.profile = Profile(name="Pad")

        app.push_state(SettingsCategoryState(app.ctx, "gameplay"))
        menu = app.state
        while not menu.items[menu.index].text.startswith("Controller device:"):
            menu.handle_event(key_event(pygame.K_DOWN))
        assert "Pad A" in menu.items[menu.index].text

        menu.handle_event(key_event(pygame.K_RIGHT))  # adjust forward
        assert app.ctx.controller.name == "Pad B"
        assert app.ctx.settings.controller_device == "Pad B"
        assert "Pad B" in menu.items[menu.index].text
    finally:
        app.shutdown()
