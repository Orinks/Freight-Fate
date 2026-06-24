"""Game controller support: input translation, analog reads, devices, rumble."""

import pygame
import pytest

from freight_fate.controller import (
    AXIS_LEFT_TRIGGER,
    AXIS_LEFT_X,
    AXIS_LEFT_Y,
    AXIS_RIGHT_TRIGGER,
    BTN_A,
    BTN_B,
    BTN_BACK,
    BTN_LB,
    BTN_RB,
    BTN_START,
    BTN_X,
    BTN_Y,
    NEUTRAL_INPUT,
    ControllerManager,
    apply_deadzone,
    control_hint,
)


@pytest.fixture(scope="module", autouse=True)
def _pygame_ready():
    pygame.init()
    yield
    pygame.quit()


class FakeJoystick:
    """A scriptable stand-in for a pygame Joystick (no hardware needed)."""

    def __init__(self, *, name="Fake Pad", instance_id=7, axes=None, buttons=None):
        self._name = name
        self._instance_id = instance_id
        self._axes = dict(axes or {})
        self._buttons = dict(buttons or {})
        self.initialised = False
        self.rumbles = []
        self.rumble_return = True
        self.stopped = 0
        self.rumble_raises = False

    def init(self):
        self.initialised = True

    def quit(self):
        self.initialised = False

    def get_name(self):
        return self._name

    def get_instance_id(self):
        return self._instance_id

    def get_axis(self, axis):
        return self._axes.get(axis, 0.0)

    def get_button(self, button):
        return self._buttons.get(button, 0)

    def rumble(self, low, high, duration):
        if self.rumble_raises:
            raise RuntimeError("no rumble motors")
        self.rumbles.append((low, high, duration))
        return self.rumble_return

    def stop_rumble(self):
        self.stopped += 1


class FakeModule:
    """A stand-in for pygame.joystick."""

    def __init__(self, joysticks=None):
        self._joysticks = list(joysticks or [])
        self.inited = False

    def init(self):
        self.inited = True

    def get_init(self):
        return self.inited

    def get_count(self):
        return len(self._joysticks)

    def Joystick(self, index):  # noqa: N802 - mirrors pygame API
        return self._joysticks[index]


def button_event(button):
    return pygame.event.Event(pygame.JOYBUTTONDOWN, button=button)


def hat_event(value):
    return pygame.event.Event(pygame.JOYHATMOTION, value=value)


def axis_event(axis, value):
    return pygame.event.Event(pygame.JOYAXISMOTION, axis=axis, value=value)


# -- discrete translation ----------------------------------------------------------


def test_menu_buttons_map_to_navigation_keys():
    mgr = ControllerManager(joystick_module=FakeModule())
    assert [e.key for e in mgr.translate(button_event(BTN_A), "menu")] == [pygame.K_RETURN]
    assert [e.key for e in mgr.translate(button_event(BTN_B), "menu")] == [pygame.K_ESCAPE]
    assert [e.key for e in mgr.translate(button_event(BTN_START), "menu")] == [pygame.K_RETURN]
    assert [e.key for e in mgr.translate(button_event(BTN_BACK), "menu")] == [pygame.K_ESCAPE]
    assert [e.key for e in mgr.translate(button_event(BTN_LB), "menu")] == [pygame.K_HOME]
    assert [e.key for e in mgr.translate(button_event(BTN_RB), "menu")] == [pygame.K_END]
    assert [e.key for e in mgr.translate(button_event(BTN_X), "menu")] == [pygame.K_F1]


def test_driving_buttons_map_to_action_keys():
    mgr = ControllerManager(joystick_module=FakeModule())
    assert [e.key for e in mgr.translate(button_event(BTN_A), "driving")] == [pygame.K_e]
    assert [e.key for e in mgr.translate(button_event(BTN_X), "driving")] == [pygame.K_h]
    assert [e.key for e in mgr.translate(button_event(BTN_Y), "driving")] == [pygame.K_p]
    assert [e.key for e in mgr.translate(button_event(BTN_LB), "driving")] == [pygame.K_x]
    assert [e.key for e in mgr.translate(button_event(BTN_RB), "driving")] == [pygame.K_k]
    assert [e.key for e in mgr.translate(button_event(BTN_BACK), "driving")] == [pygame.K_TAB]
    assert [e.key for e in mgr.translate(button_event(BTN_START), "driving")] == [pygame.K_ESCAPE]


def test_b_button_has_no_discrete_driving_key():
    # B in driving is the held emergency brake, read by read(), not a press.
    mgr = ControllerManager(joystick_module=FakeModule())
    assert mgr.translate(button_event(BTN_B), "driving") == []


def test_synthetic_key_events_are_keydown_with_blank_unicode():
    mgr = ControllerManager(joystick_module=FakeModule())
    (event,) = mgr.translate(button_event(BTN_A), "menu")
    assert event.type == pygame.KEYDOWN
    assert event.unicode == ""


def test_hat_navigation_menu_and_driving():
    mgr = ControllerManager(joystick_module=FakeModule())
    assert [e.key for e in mgr.translate(hat_event((0, 1)), "menu")] == [pygame.K_UP]
    assert [e.key for e in mgr.translate(hat_event((0, -1)), "menu")] == [pygame.K_DOWN]
    assert [e.key for e in mgr.translate(hat_event((-1, 0)), "menu")] == [pygame.K_LEFT]
    assert [e.key for e in mgr.translate(hat_event((1, 0)), "menu")] == [pygame.K_RIGHT]
    assert mgr.translate(hat_event((0, 0)), "menu") == []
    assert [e.key for e in mgr.translate(hat_event((0, 1)), "driving")] == [pygame.K_r]
    assert [e.key for e in mgr.translate(hat_event((1, 0)), "driving")] == [pygame.K_c]


def test_non_joystick_event_returns_none():
    mgr = ControllerManager(joystick_module=FakeModule())
    keydown = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="a")
    assert mgr.translate(keydown, "menu") is None


def test_left_stick_navigates_menus_on_threshold_crossing():
    mgr = ControllerManager(joystick_module=FakeModule())
    # A push past the threshold emits one move...
    assert [e.key for e in mgr.translate(axis_event(AXIS_LEFT_Y, 0.9), "menu")] == [pygame.K_DOWN]
    # ...holding it does not repeat...
    assert mgr.translate(axis_event(AXIS_LEFT_Y, 0.95), "menu") == []
    # ...releasing to center arms it again...
    assert mgr.translate(axis_event(AXIS_LEFT_Y, 0.0), "menu") == []
    # ...and pushing the other way moves up.
    assert [e.key for e in mgr.translate(axis_event(AXIS_LEFT_Y, -0.9), "menu")] == [pygame.K_UP]
    # Horizontal stick maps to left/right for settings and help.
    assert [e.key for e in mgr.translate(axis_event(AXIS_LEFT_X, 0.9), "menu")] == [pygame.K_RIGHT]


def test_axis_motion_is_consumed_silently_while_driving():
    mgr = ControllerManager(joystick_module=FakeModule())
    assert mgr.translate(axis_event(AXIS_LEFT_X, 0.9), "driving") == []
    assert mgr.translate(axis_event(AXIS_RIGHT_TRIGGER, 0.5), "driving") == []


def test_translate_ignores_input_from_other_devices():
    # A flight stick or second pad on the bus must not drive the game; only the
    # active controller's events translate. (A HOTAS throttle resting off-center
    # streams axis motion that otherwise steals menu navigation.)
    js = FakeJoystick(instance_id=7)
    mgr = ControllerManager(joystick_module=FakeModule([js]))
    mgr.start()
    mine = pygame.event.Event(pygame.JOYHATMOTION, value=(0, -1), instance_id=7)
    other = pygame.event.Event(pygame.JOYHATMOTION, value=(0, -1), instance_id=99)
    noisy = pygame.event.Event(pygame.JOYAXISMOTION, axis=AXIS_LEFT_Y, value=0.9,
                               instance_id=99)
    assert [e.key for e in mgr.translate(mine, "menu")] == [pygame.K_DOWN]
    assert mgr.translate(other, "menu") == []
    assert mgr.translate(noisy, "menu") == []
    # The other device's noise must not have armed the shared nav state: the
    # active pad's first push still registers a move.
    active = pygame.event.Event(pygame.JOYAXISMOTION, axis=AXIS_LEFT_Y, value=0.9,
                                instance_id=7)
    assert [e.key for e in mgr.translate(active, "menu")] == [pygame.K_DOWN]


# -- control hints -----------------------------------------------------------------


def test_control_hint_switches_phrasing_by_scheme():
    # Keyboard prompts read naturally after "Press"/"Hold"; controller prompts
    # name the physical control descriptively.
    assert control_hint("engine", controller=False) == "E"
    assert control_hint("engine", controller=True) == "the A button"
    assert control_hint("accelerate", controller=False) == "the Up arrow"
    assert control_hint("accelerate", controller=True) == "the right trigger"
    assert control_hint("take_exit", controller=True) == "the left bumper"


# -- deadzone and analog reads -----------------------------------------------------


def test_apply_deadzone_ignores_slack_and_rescales():
    assert apply_deadzone(0.1, 0.15) == 0.0
    assert apply_deadzone(-0.1, 0.15) == 0.0
    assert apply_deadzone(0.15, 0.15) == 0.0
    # just past the edge starts near zero, full deflection reaches 1
    assert apply_deadzone(1.0, 0.15) == pytest.approx(1.0)
    assert apply_deadzone(-1.0, 0.15) == pytest.approx(-1.0)
    assert 0.0 < apply_deadzone(0.5, 0.15) < 0.5


def test_read_returns_neutral_without_a_joystick():
    mgr = ControllerManager(joystick_module=FakeModule())
    assert mgr.read() is NEUTRAL_INPUT


def test_trigger_normalisation_guards_against_phantom_half_pull():
    js = FakeJoystick(axes={AXIS_RIGHT_TRIGGER: 0.0})
    mgr = ControllerManager(joystick_module=FakeModule([js]))
    mgr.start()
    # Before the trigger is ever seen at rest, a 0.0 reading must not become 0.5.
    assert mgr.read().throttle == 0.0
    # Once it reports its true rest value, it is trusted thereafter.
    js._axes[AXIS_RIGHT_TRIGGER] = -1.0
    assert mgr.read().throttle == 0.0
    js._axes[AXIS_RIGHT_TRIGGER] = 1.0
    assert mgr.read().throttle == pytest.approx(1.0)
    js._axes[AXIS_RIGHT_TRIGGER] = 0.0  # half pressed
    assert mgr.read().throttle == pytest.approx(0.5)


def test_read_maps_axes_and_emergency_button():
    js = FakeJoystick(
        axes={
            AXIS_LEFT_X: -1.0,
            AXIS_LEFT_TRIGGER: -1.0,
            AXIS_RIGHT_TRIGGER: -1.0,
        },
        buttons={BTN_B: 1},
    )
    mgr = ControllerManager(joystick_module=FakeModule([js]))
    mgr.start()
    mgr.read()  # establish trigger rest
    js._axes[AXIS_LEFT_TRIGGER] = 1.0
    state = mgr.read()
    assert state.steer == pytest.approx(-1.0)
    assert state.brake == pytest.approx(1.0)
    assert state.throttle == 0.0
    assert state.emergency is True


def test_read_survives_a_misbehaving_driver():
    class Broken(FakeJoystick):
        def get_axis(self, axis):
            raise RuntimeError("device error")

    js = Broken()
    mgr = ControllerManager(joystick_module=FakeModule([js]))
    mgr.start()
    assert mgr.read() is NEUTRAL_INPUT


# -- device lifecycle --------------------------------------------------------------


def test_start_attaches_first_available_controller():
    js = FakeJoystick(name="Xbox Pad")
    mgr = ControllerManager(joystick_module=FakeModule([js]))
    mgr.start()
    assert mgr.connected
    assert mgr.name == "Xbox Pad"
    assert js.initialised


def test_start_without_devices_stays_disconnected():
    mgr = ControllerManager(joystick_module=FakeModule([]))
    mgr.start()
    assert not mgr.connected
    assert mgr.name == ""


def test_device_added_event_attaches_when_idle():
    module = FakeModule([])
    mgr = ControllerManager(joystick_module=module)
    mgr.start()
    assert not mgr.connected
    js = FakeJoystick()
    module._joysticks.append(js)
    consumed = mgr.handle_system_event(
        pygame.event.Event(pygame.JOYDEVICEADDED, device_index=0))
    assert consumed
    assert mgr.connected


def test_device_removed_event_detaches_and_repicks():
    first = FakeJoystick(instance_id=11)
    second = FakeJoystick(instance_id=22, name="Backup Pad")
    module = FakeModule([first, second])
    mgr = ControllerManager(joystick_module=module)
    mgr.start()
    assert mgr.name == first.get_name()
    # The active pad unplugs; the manager falls back to the remaining one.
    module._joysticks.remove(first)
    consumed = mgr.handle_system_event(
        pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=11))
    assert consumed
    assert mgr.connected
    assert mgr.name == "Backup Pad"


def test_device_removed_for_other_instance_is_ignored():
    js = FakeJoystick(instance_id=5)
    mgr = ControllerManager(joystick_module=FakeModule([js]))
    mgr.start()
    mgr.handle_system_event(
        pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=999))
    assert mgr.connected


# -- device selection --------------------------------------------------------------


def test_device_names_lists_every_connected_pad():
    a = FakeJoystick(name="Pad A", instance_id=1)
    b = FakeJoystick(name="Pad B", instance_id=2)
    mgr = ControllerManager(joystick_module=FakeModule([a, b]))
    assert mgr.device_names() == ["Pad A", "Pad B"]


def test_preferred_name_chosen_at_start_over_index_zero():
    a = FakeJoystick(name="Pad A", instance_id=1)
    b = FakeJoystick(name="Pad B", instance_id=2)
    mgr = ControllerManager(joystick_module=FakeModule([a, b]))
    mgr.preferred_name = "Pad B"
    mgr.start()
    assert mgr.name == "Pad B"


def test_select_switches_active_pad_and_records_preference():
    a = FakeJoystick(name="Pad A", instance_id=1)
    b = FakeJoystick(name="Pad B", instance_id=2)
    mgr = ControllerManager(joystick_module=FakeModule([a, b]))
    mgr.start()
    assert mgr.name == "Pad A"
    assert mgr.select(1) is True
    assert mgr.name == "Pad B"
    assert mgr.preferred_name == "Pad B"
    assert mgr.select(5) is False  # out of range, no change
    assert mgr.name == "Pad B"


def test_select_next_cycles_and_wraps():
    a = FakeJoystick(name="Pad A", instance_id=1)
    b = FakeJoystick(name="Pad B", instance_id=2)
    mgr = ControllerManager(joystick_module=FakeModule([a, b]))
    mgr.start()
    assert mgr.select_next(1) is True
    assert mgr.name == "Pad B"
    assert mgr.select_next(1) is True
    assert mgr.name == "Pad A"  # wrapped


def test_select_next_noop_with_a_single_pad():
    only = FakeJoystick(name="Solo")
    mgr = ControllerManager(joystick_module=FakeModule([only]))
    mgr.start()
    assert mgr.select_next(1) is False
    assert mgr.name == "Solo"


def test_removed_preferred_pad_repicks_preferred_when_back():
    a = FakeJoystick(name="Pad A", instance_id=1)
    b = FakeJoystick(name="Pad B", instance_id=2)
    module = FakeModule([a, b])
    mgr = ControllerManager(joystick_module=module)
    mgr.start()
    mgr.select(1)  # prefer Pad B
    # Pad B unplugs; the only one left is Pad A.
    module._joysticks.remove(b)
    mgr.handle_system_event(
        pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=2))
    assert mgr.name == "Pad A"
    # Pad B comes back; the manager returns to the preferred device.
    module._joysticks.append(b)
    mgr.handle_system_event(
        pygame.event.Event(pygame.JOYDEVICEADDED, device_index=1))
    assert mgr.name == "Pad B"


# -- rumble ------------------------------------------------------------------------


def test_rumble_forwards_to_joystick():
    js = FakeJoystick()
    mgr = ControllerManager(joystick_module=FakeModule([js]))
    mgr.start()
    assert mgr.rumble(0.5, 0.5, 1500) is True
    assert js.rumbles == [(0.5, 0.5, 1500)]
    mgr.stop_rumble()
    assert js.stopped == 1


def test_rumble_is_safe_without_a_joystick():
    mgr = ControllerManager(joystick_module=FakeModule([]))
    mgr.start()
    assert mgr.rumble(1.0, 1.0, 100) is False
    mgr.stop_rumble()  # no error


def test_rumble_swallows_unsupported_devices():
    js = FakeJoystick()
    js.rumble_raises = True
    mgr = ControllerManager(joystick_module=FakeModule([js]))
    mgr.start()
    assert mgr.rumble(1.0, 1.0, 100) is False
