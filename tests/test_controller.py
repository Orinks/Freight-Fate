"""Controller support: hint routing, the manager, menus, and driving."""

import pygame
from driving_feature_helpers import quiet_trip, start_drive

from freight_fate.controller import ControllerAction, ControllerManager
from freight_fate.input_hints import CONTROLLER, KEYBOARD, control_hint


def _button(button, instance_id=0):
    return pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=button, instance_id=instance_id)


def _button_up(button, instance_id=0):
    return pygame.event.Event(pygame.CONTROLLERBUTTONUP, button=button, instance_id=instance_id)


def _axis(axis, value, instance_id=0):
    return pygame.event.Event(
        pygame.CONTROLLERAXISMOTION, axis=axis, value=value, instance_id=instance_id
    )


def force_controller(app):
    """Pretend a controller is connected so the manager reports active."""
    c = app.controller
    c.enabled = True
    c._controller = object()
    c._instance_id = 0
    c.active_device = CONTROLLER
    return c


# -- pure hint table ---------------------------------------------------------


def test_control_hint_follows_device():
    assert control_hint("take_exit", KEYBOARD) == "X"
    assert control_hint("take_exit", CONTROLLER) == "D-pad down"
    assert control_hint("accelerate", KEYBOARD) == "the Up arrow"
    assert control_hint("accelerate", CONTROLLER) == "the right trigger"


def test_control_hint_unknown_action_is_audible():
    # An unknown action returns itself rather than crashing a live prompt.
    assert control_hint("not_a_real_action", CONTROLLER) == "not_a_real_action"


# -- manager -----------------------------------------------------------------


def test_manager_without_device_is_inactive():
    # Force the no-controller branch so the test does not depend on whether a
    # physical pad happens to be plugged into the machine running the suite.
    m = ControllerManager(enabled=True)
    m._controller = None
    m._instance_id = None
    assert not m.active
    assert m.device == KEYBOARD
    assert m.tick(0.016) == []
    m.shutdown()


def test_menu_action_mapping():
    m = ControllerManager(enabled=True)
    force = lambda b: m.menu_action(_button(b))  # noqa: E731
    assert force(pygame.CONTROLLER_BUTTON_DPAD_UP) == ControllerAction.MENU_UP
    assert force(pygame.CONTROLLER_BUTTON_DPAD_DOWN) == ControllerAction.MENU_DOWN
    assert force(pygame.CONTROLLER_BUTTON_DPAD_LEFT) == ControllerAction.ADJUST_LEFT
    assert force(pygame.CONTROLLER_BUTTON_DPAD_RIGHT) == ControllerAction.ADJUST_RIGHT
    assert force(pygame.CONTROLLER_BUTTON_A) == ControllerAction.CONFIRM
    assert force(pygame.CONTROLLER_BUTTON_B) == ControllerAction.BACK
    assert force(pygame.CONTROLLER_BUTTON_BACK) == ControllerAction.HELP
    # A button-up carries no menu action.
    assert m.menu_action(_button_up(pygame.CONTROLLER_BUTTON_A)) is None


def test_trigger_deadzone_and_smoothing():
    m = ControllerManager(enabled=True)
    m._controller = object()
    m._instance_id = 0
    # Below the 4% trigger deadzone -> still zero.
    m.process_event(_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT, int(32767 * 0.02)))
    m.tick(0.016)
    assert m.throttle == 0.0
    # Full press smooths up toward 1.0 over a few frames.
    m.process_event(_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT, 32767))
    for _ in range(30):
        m.tick(0.016)
    assert m.throttle > 0.95
    m.shutdown()


def test_clutch_is_instant_like_shift():
    # The left bumper is a digital button, so the clutch engages and releases
    # immediately -- matching the keyboard Shift -- with no smoothing lag.
    m = ControllerManager(enabled=True)
    m._controller = object()
    m._instance_id = 0
    m.process_event(_button(pygame.CONTROLLER_BUTTON_LEFTSHOULDER))
    assert m.clutch == 1.0  # no tick needed
    m.process_event(_button_up(pygame.CONTROLLER_BUTTON_LEFTSHOULDER))
    assert m.clutch == 0.0
    m.shutdown()


def test_modifier_tracks_right_bumper():
    m = ControllerManager(enabled=True)
    m._controller = object()
    m._instance_id = 0
    assert not m.modifier
    m.process_event(_button(pygame.CONTROLLER_BUTTON_RIGHTSHOULDER))
    assert m.modifier
    m.process_event(_button_up(pygame.CONTROLLER_BUTTON_RIGHTSHOULDER))
    assert not m.modifier
    m.shutdown()


def test_dpad_hold_auto_repeats():
    m = ControllerManager(enabled=True)
    m._controller = object()
    m._instance_id = 0
    m.process_event(_button(pygame.CONTROLLER_BUTTON_DPAD_LEFT))
    # Nothing before the initial delay, then repeats accumulate while held.
    assert m.tick(0.1) == []
    first = m.tick(0.25)  # crosses the 0.3s initial delay
    assert len(first) == 1
    assert first[0].button == pygame.CONTROLLER_BUTTON_DPAD_LEFT
    # Release stops further repeats.
    m.process_event(_button_up(pygame.CONTROLLER_BUTTON_DPAD_LEFT))
    assert m.tick(1.0) == []
    m.shutdown()


def test_disconnect_latches_once():
    m = ControllerManager(enabled=True)
    m._controller = object()
    m._instance_id = 7
    m.process_event(pygame.event.Event(pygame.CONTROLLERDEVICEREMOVED, instance_id=7))
    assert not m.connected
    assert m.take_disconnect() is True
    assert m.take_disconnect() is False  # consumed
    m.shutdown()


def test_disabled_manager_ignores_controller():
    m = ControllerManager(enabled=True)
    m._controller = object()
    m._instance_id = 0
    m.set_enabled(False)
    assert not m.active
    m.process_event(_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT, 32767))
    assert m.throttle == 0.0
    m.shutdown()


# -- menus -------------------------------------------------------------------


def test_menu_dpad_moves_and_adjusts(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsCategoryState

    app = App()
    force_controller(app)
    app.push_state(SettingsCategoryState(app.ctx, "gameplay"))
    state = app.state
    start_index = state.index
    app._dispatch_controller(_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN))
    assert app.state.index == start_index + 1
    # Move to the Units item and adjust it with D-pad right.
    app.state.index = 0
    before = app.ctx.settings.imperial_units
    app._dispatch_controller(_button(pygame.CONTROLLER_BUTTON_DPAD_RIGHT))
    assert app.ctx.settings.imperial_units != before
    app.shutdown()


def test_setting_toggle_gates_controller():
    from freight_fate.app import App

    app = App()
    c = force_controller(app)
    app.ctx.settings.controller_enabled = False
    app.ctx.apply_controller()
    assert not c.active
    app.shutdown()


# -- driving -----------------------------------------------------------------


def test_analog_trigger_drives_throttle(monkeypatch):
    from freight_fate.app import App

    app = App()
    force_controller(app)
    driving = start_drive(app)
    quiet_trip(driving)
    app._dispatch_controller(_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT, 32767))
    for _ in range(20):
        app.controller.tick(0.016)
    driving.update(1 / 60)
    assert driving.truck.throttle > 0.5
    app.shutdown()


def test_held_partial_trigger_does_not_machinegun_brake_sound(monkeypatch):
    from freight_fate.app import App

    app = App()
    force_controller(app)
    driving = start_drive(app)
    quiet_trip(driving)
    driving.truck.velocity_mps = 15.0
    hisses = []
    real_play = app.ctx.audio.play
    monkeypatch.setattr(
        app.ctx.audio,
        "play",
        lambda key, volume=1.0: hisses.append(key) if key == "vehicle/brake_air" else real_play,
    )
    # A light, steady trigger position (~30%) held for many frames.
    app._dispatch_controller(_axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT, int(32767 * 0.30)))
    for _ in range(40):
        app.controller.tick(1 / 60)
        driving.update(1 / 60)
    assert driving.truck.brake > 0.2  # the brake is genuinely applied
    assert len(hisses) <= 1  # ...but the hiss fires once, not every frame
    app.shutdown()


def test_controller_info_buttons_speak(monkeypatch):
    from freight_fate.app import App

    app = App()
    force_controller(app)
    driving = start_drive(app)
    quiet_trip(driving)
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    # B button speaks speed; RB+B speaks fuel.
    app._dispatch_controller(_button(pygame.CONTROLLER_BUTTON_B))
    assert any("per hour" in t for t in spoken)
    spoken.clear()
    app._dispatch_controller(_button(pygame.CONTROLLER_BUTTON_RIGHTSHOULDER))
    app._dispatch_controller(_button(pygame.CONTROLLER_BUTTON_B))
    assert any("fuel" in t.lower() or "range" in t.lower() for t in spoken)
    app.shutdown()


def test_controller_disconnect_pauses_driving():
    from freight_fate.app import App
    from freight_fate.states.driving_menu_states import PauseMenuState

    app = App()
    force_controller(app)
    driving = start_drive(app)
    driving.on_controller_disconnect()
    assert isinstance(app.state, PauseMenuState)
    app.shutdown()


def test_plain_state_not_trapped_by_controller():
    # A non-menu keyboard state (the update check screen) must still be
    # dismissable with the controller via the base translation to key events.
    from freight_fate.app import App
    from freight_fate.states.main_menu import MainMenuState
    from freight_fate.states.update import UpdateCheckState

    app = App()
    force_controller(app)
    app.push_state(MainMenuState(app.ctx))
    app.push_state(UpdateCheckState(app.ctx))
    depth = len(app.states)
    app._dispatch_controller(_button(pygame.CONTROLLER_BUTTON_B))  # B -> Escape
    assert len(app.states) == depth - 1
    app.shutdown()


def test_hint_switches_with_active_device():
    from freight_fate.app import App

    app = App()
    force_controller(app)
    # A controller button marks the controller active.
    app._dispatch_controller(_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN))
    assert app.ctx.control_hint("take_exit") == "D-pad down"
    # A keyboard press flips hints back to key names.
    app.controller.note_keyboard()
    assert app.ctx.control_hint("take_exit") == "X"
    app.shutdown()
