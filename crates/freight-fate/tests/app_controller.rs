//! Port of `tests/test_controller.py`: hint routing, the manager, menus,
//! and driving. The manager tests run against the fake pad and subsystem
//! (`controller::fakes`), the Python `object()` controller and `FakeSDL`.

use std::cell::RefCell;
use std::rc::Rc;

use ff_core::input_hints::{control_hint, CONTROLLER, KEYBOARD};
use freight_fate::app::testing::TestApp;
use freight_fate::app::GameContext;
use freight_fate::controller::fakes::{fake_factory, FakePad, FakeSdlLog};
use freight_fate::controller::{
    ControllerAction, ControllerAxis, ControllerButton, ControllerManager,
};
use freight_fate::states::base::{InputEvent, Key, State};

fn button(button: ControllerButton, instance_id: u32) -> InputEvent {
    InputEvent::ControllerButtonDown {
        button,
        instance_id,
    }
}

fn button_up(button: ControllerButton, instance_id: u32) -> InputEvent {
    InputEvent::ControllerButtonUp {
        button,
        instance_id,
    }
}

fn axis(axis: ControllerAxis, value: i16, instance_id: u32) -> InputEvent {
    InputEvent::ControllerAxis {
        axis,
        value,
        instance_id,
    }
}

/// `m._controller = object(); m._instance_id = id`: a bound pad, id latched.
fn manager_with_pad(instance_id: u32) -> ControllerManager {
    let mut m = ControllerManager::detached(true, true);
    m.bind_device(Box::new(FakePad::new(instance_id)), "test pad");
    m.set_id_pending(false);
    m
}

/// Pretend a controller is connected so the app's manager reports active.
fn force_controller(app: &mut TestApp) {
    let c = &mut app.ctx.controller;
    c.set_enabled(true);
    c.bind_device(Box::new(FakePad::new(0)), "test pad");
    c.set_id_pending(false);
    c.active_device = CONTROLLER;
}

// -- pure hint table ---------------------------------------------------------

#[test]
fn test_control_hint_follows_device() {
    assert_eq!(control_hint("take_exit", KEYBOARD), "X");
    assert_eq!(control_hint("take_exit", CONTROLLER), "D-pad down");
    assert_eq!(control_hint("accelerate", KEYBOARD), "the Up arrow");
    assert_eq!(control_hint("accelerate", CONTROLLER), "the right trigger");
}

#[test]
fn test_control_hint_unknown_action_is_audible() {
    // An unknown action returns itself rather than crashing a live prompt.
    assert_eq!(
        control_hint("not_a_real_action", CONTROLLER),
        "not_a_real_action"
    );
}

// -- manager -----------------------------------------------------------------

#[test]
fn test_manager_without_device_is_inactive() {
    let mut m = ControllerManager::detached(true, true);
    assert!(!m.active());
    assert_eq!(m.device(), KEYBOARD);
    assert!(m.tick(0.016).is_empty());
    m.shutdown();
}

#[test]
fn test_menu_action_mapping() {
    let m = ControllerManager::detached(true, true);
    let force = |b| m.menu_action(&button(b, 0));
    assert_eq!(
        force(ControllerButton::DPadUp),
        Some(ControllerAction::MenuUp)
    );
    assert_eq!(
        force(ControllerButton::DPadDown),
        Some(ControllerAction::MenuDown)
    );
    assert_eq!(
        force(ControllerButton::DPadLeft),
        Some(ControllerAction::AdjustLeft)
    );
    assert_eq!(
        force(ControllerButton::DPadRight),
        Some(ControllerAction::AdjustRight)
    );
    assert_eq!(force(ControllerButton::A), Some(ControllerAction::Confirm));
    assert_eq!(force(ControllerButton::B), Some(ControllerAction::Back));
    assert_eq!(force(ControllerButton::Back), Some(ControllerAction::Help));
    // A button-up carries no menu action.
    assert_eq!(m.menu_action(&button_up(ControllerButton::A, 0)), None);
}

#[test]
fn test_trigger_deadzone_and_smoothing() {
    let mut m = manager_with_pad(0);
    // Below the 4% trigger deadzone -> still zero.
    m.process_event(&axis(
        ControllerAxis::TriggerRight,
        (32767.0 * 0.02) as i16,
        0,
    ));
    m.tick(0.016);
    assert_eq!(m.throttle(), 0.0);
    // Full press smooths up toward 1.0 over a few frames.
    m.process_event(&axis(ControllerAxis::TriggerRight, 32767, 0));
    for _ in 0..30 {
        m.tick(0.016);
    }
    assert!(m.throttle() > 0.95);
    m.shutdown();
}

#[test]
fn test_clutch_is_instant_like_shift() {
    // The left bumper is a digital button, so the clutch engages and
    // releases immediately -- matching the keyboard Shift -- with no
    // smoothing lag.
    let mut m = manager_with_pad(0);
    m.process_event(&button(ControllerButton::LeftShoulder, 0));
    assert_eq!(m.clutch(), 1.0); // no tick needed
    m.process_event(&button_up(ControllerButton::LeftShoulder, 0));
    assert_eq!(m.clutch(), 0.0);
    m.shutdown();
}

#[test]
fn test_modifier_tracks_right_bumper() {
    let mut m = manager_with_pad(0);
    assert!(!m.modifier);
    m.process_event(&button(ControllerButton::RightShoulder, 0));
    assert!(m.modifier);
    m.process_event(&button_up(ControllerButton::RightShoulder, 0));
    assert!(!m.modifier);
    m.shutdown();
}

#[test]
fn test_dpad_hold_auto_repeats() {
    let mut m = manager_with_pad(0);
    m.process_event(&button(ControllerButton::DPadLeft, 0));
    // Nothing before the initial delay, then repeats accumulate while held.
    assert!(m.tick(0.1).is_empty());
    let first = m.tick(0.25); // crosses the 0.3s initial delay
    assert_eq!(first.len(), 1);
    assert_eq!(first[0], button(ControllerButton::DPadLeft, 0));
    // Release stops further repeats.
    m.process_event(&button_up(ControllerButton::DPadLeft, 0));
    assert!(m.tick(1.0).is_empty());
    m.shutdown();
}

#[test]
fn test_disconnect_latches_once() {
    let mut m = manager_with_pad(7);
    m.process_event(&InputEvent::ControllerRemoved { instance_id: 7 });
    assert!(!m.connected());
    assert!(m.take_disconnect());
    assert!(!m.take_disconnect()); // consumed
    m.shutdown();
}

#[test]
fn test_reconnect_reopens_after_removed() {
    // A device-added after a device-removed must reopen the pad, so a
    // reconnect restores controller input rather than leaving it dead.
    let log = Rc::new(RefCell::new(FakeSdlLog::default()));
    let mut m = ControllerManager::new(
        true,
        true,
        Some(fake_factory(vec![("pad".to_string(), 7)], Rc::clone(&log))),
    );
    assert!(m.connected()); // bound at startup
    m.process_event(&InputEvent::ControllerRemoved { instance_id: 7 });
    assert!(!m.connected());

    let opens_before = log.borrow().opens.len();
    m.process_event(&InputEvent::ControllerAdded { device_index: 3 });
    assert_eq!(log.borrow().opens.len(), opens_before + 1); // bound the reconnected pad
    assert!(m.connected());
    m.shutdown();
}

#[test]
fn test_reopen_does_not_cycle_subsystem() {
    // reopen must drop the old pad and rebind WITHOUT quitting/re-initializing
    // the SDL subsystem -- cycling it re-registers the event watch and
    // doubles every controller event.
    let log = Rc::new(RefCell::new(FakeSdlLog::default()));
    let mut m = ControllerManager::new(
        true,
        true,
        Some(fake_factory(vec![("pad".to_string(), 7)], Rc::clone(&log))),
    );
    let (inits, quits, opens) = {
        let l = log.borrow();
        (l.inits, l.quits, l.opens.len())
    };
    m.reopen();
    let l = log.borrow();
    assert_eq!(l.inits, inits);
    assert_eq!(l.quits, quits);
    assert_eq!(l.opens.len(), opens + 1); // reopened, never cycled the subsystem
    drop(l);
    m.shutdown();
}

#[test]
fn test_add_ignored_while_pad_still_attached() {
    // A spurious device-added must not drop a working, still-attached
    // binding.
    let log = Rc::new(RefCell::new(FakeSdlLog::default()));
    let mut m = ControllerManager::new(
        true,
        true,
        Some(fake_factory(vec![("pad".to_string(), 7)], Rc::clone(&log))),
    );
    let opens = log.borrow().opens.len();
    m.process_event(&InputEvent::ControllerAdded { device_index: 3 });
    assert_eq!(log.borrow().opens.len(), opens); // left the existing pad bound
    assert_eq!(m.instance_id(), Some(7));
    m.shutdown();
}

#[test]
fn test_binding_latches_to_first_event_id() {
    // A hot-plug can leave the opened id stale, so the pad's real events
    // arrive under a different id. The first real event's id is
    // authoritative: the manager adopts it and applies the event (triggers
    // come back to life).
    let mut m = ControllerManager::detached(true, true);
    m.bind_device(Box::new(FakePad::new(0)), "pad"); // freshly (re)opened, id provisional
    assert!(m.id_pending());
    m.process_event(&axis(ControllerAxis::TriggerLeft, 32767, 2));
    assert_eq!(m.instance_id(), Some(2)); // adopted the id the events actually carry
    assert!(!m.id_pending()); // latched
    assert!(m.brake_target() > 0.0); // ...and the event was applied
    m.shutdown();
}

#[test]
fn test_foreign_duplicate_button_is_not_forwarded() {
    // Once the binding is latched, a button under a *different* id (a
    // duplicate from a pad that enumerates twice) must not be forwarded to
    // the state, or it would fire the action a second time.
    let mut m = manager_with_pad(0); // already latched to id 0
                                     // The genuine press is forwarded...
    assert!(m.process_event(&button(ControllerButton::A, 0)));
    // ...its duplicate under id 2 is dropped, not forwarded.
    assert!(!m.process_event(&button(ControllerButton::A, 2)));
    m.shutdown();
}

#[test]
fn test_duplicate_button_down_not_forwarded() {
    // A pad that delivers a button twice (same id, no intervening release)
    // must forward only the first press to the state.
    let mut m = manager_with_pad(0);
    assert!(m.process_event(&button(ControllerButton::A, 0)));
    assert!(!m.process_event(&button(ControllerButton::A, 0)));
    // After a genuine release, the next press is fresh again.
    assert!(m.process_event(&button_up(ControllerButton::A, 0)));
    assert!(m.process_event(&button(ControllerButton::A, 0)));
    m.shutdown();
}

#[test]
#[ignore = "needs states::driving"]
fn test_duplicate_button_down_does_not_double_toggle() {}

#[test]
fn test_disabled_manager_ignores_controller() {
    let mut m = manager_with_pad(0);
    m.set_enabled(false);
    assert!(!m.active());
    m.process_event(&axis(ControllerAxis::TriggerRight, 32767, 0));
    assert_eq!(m.throttle(), 0.0);
    m.shutdown();
}

#[test]
fn test_disabled_manager_never_inits_subsystem() {
    // With controller support off, the subsystem must not be touched: no
    // enumeration, no pad bound.
    let log = Rc::new(RefCell::new(FakeSdlLog::default()));
    let mut m = ControllerManager::new(
        false,
        true,
        Some(fake_factory(vec![("pad".to_string(), 7)], Rc::clone(&log))),
    );
    assert!(!m.subsystem_up()); // subsystem never initialized
    assert!(!m.connected());
    assert_eq!(log.borrow().inits, 0); // never went looking for a pad
    assert!(log.borrow().opens.is_empty());
    m.shutdown();
}

#[test]
fn test_enabling_inits_subsystem() {
    // Turning support on for the first time brings the subsystem up.
    let log = Rc::new(RefCell::new(FakeSdlLog::default()));
    let mut m = ControllerManager::new(false, true, Some(fake_factory(vec![], Rc::clone(&log))));
    m.set_enabled(true);
    assert!(m.enabled());
    assert_eq!(log.borrow().inits, 1);
    assert!(m.subsystem_up());
    m.shutdown();
}

#[test]
fn test_disabling_tears_down_subsystem() {
    // Disabling releases the open pad and uninitializes the subsystem so no
    // controller handles or SDL state linger while support is off.
    let log = Rc::new(RefCell::new(FakeSdlLog::default()));
    let mut m = ControllerManager::new(
        true,
        true,
        Some(fake_factory(vec![("pad".to_string(), 0)], Rc::clone(&log))),
    );
    assert!(m.connected());
    m.set_enabled(false);
    assert!(!m.connected()); // handle released
    assert!(!m.subsystem_up()); // subsystem uninitialized
    assert_eq!(log.borrow().quits, 1);
    m.shutdown();
}

// -- menus -------------------------------------------------------------------

#[test]
fn test_menu_dpad_moves_and_adjusts() {
    use freight_fate::states::base::Menu;
    use freight_fate::states::main_menu::SettingsCategoryState;

    let mut app = TestApp::new();
    force_controller(&mut app);
    app.push_state(SettingsCategoryState::new("controls"));
    let index = |app: &TestApp| -> usize {
        let state = app.state().unwrap();
        let state = state.borrow();
        state
            .as_any()
            .downcast_ref::<SettingsCategoryState>()
            .unwrap()
            .menu()
            .index
    };
    let start_index = index(&app);
    app.dispatch_controller(&button(ControllerButton::DPadDown, 0));
    assert_eq!(index(&app), start_index + 1);
    // Move to the Units item and adjust it with D-pad right.
    {
        let state = app.state().unwrap();
        let mut state = state.borrow_mut();
        state
            .as_any_mut()
            .downcast_mut::<SettingsCategoryState>()
            .unwrap()
            .menu_mut()
            .index = 0;
    }
    let before = app.ctx.settings.imperial_units;
    app.dispatch_controller(&button(ControllerButton::DPadRight, 0));
    assert_ne!(app.ctx.settings.imperial_units, before);
    app.shutdown();
}

#[test]
fn test_setting_toggle_gates_controller() {
    let mut app = TestApp::new();
    force_controller(&mut app);
    app.ctx.settings.controller_enabled = false;
    app.ctx.apply_controller();
    assert!(!app.ctx.controller.active());
    app.shutdown();
}

// -- driving -----------------------------------------------------------------

#[test]
#[ignore = "needs states::driving"]
fn test_analog_trigger_drives_throttle() {}

#[test]
#[ignore = "needs states::driving"]
fn test_held_partial_trigger_does_not_machinegun_brake_sound() {}

#[test]
#[ignore = "needs states::driving"]
fn test_controller_info_buttons_speak() {}

#[test]
#[ignore = "needs states::driving"]
fn test_controller_speed_control_handoff_status_adjustment_and_brake() {}

#[test]
#[ignore = "needs states::driving"]
fn test_paused_speed_control_can_be_canceled_by_keyboard_or_controller() {}

#[test]
#[ignore = "needs states::driving"]
fn test_controller_disconnect_pauses_driving() {}

#[test]
#[ignore = "needs an SDL event pump to fail; the headless app has none (the shell's poll guard is exercised by the windowed build)"]
fn test_event_pump_error_is_survived() {}

#[test]
fn test_plain_state_not_trapped_by_controller() {
    // A non-menu keyboard state (the update check screen in Python; a
    // plain Escape-to-dismiss screen here) must still be dismissable with
    // the controller via the base translation to key events.
    struct Dismissable;
    impl State for Dismissable {
        fn handle_event(&mut self, ctx: &mut GameContext, event: &InputEvent) {
            if let Some((Key::Escape, _, _)) = event.key_down() {
                ctx.pop_state();
            }
        }
    }
    let mut app = TestApp::new();
    force_controller(&mut app);
    app.push_state(Dismissable);
    app.push_state(Dismissable);
    let depth = app.states().len();
    app.dispatch_controller(&button(ControllerButton::B, 0)); // B -> Escape
    assert_eq!(app.states().len(), depth - 1);
    app.shutdown();
}

#[test]
fn test_hint_switches_with_active_device() {
    let mut app = TestApp::new();
    force_controller(&mut app);
    // A controller button marks the controller active.
    app.dispatch_controller(&button(ControllerButton::DPadDown, 0));
    assert_eq!(app.ctx.control_hint("take_exit"), "D-pad down");
    // A keyboard press flips hints back to key names.
    app.ctx.controller.note_keyboard();
    assert_eq!(app.ctx.control_hint("take_exit"), "X");
    app.shutdown();
}

/// The controller disconnect line reaches the player from the loop.
#[test]
fn disconnect_speaks_and_reaches_the_state() {
    struct Noticing(Rc<RefCell<u32>>);
    impl State for Noticing {
        fn on_controller_disconnect(&mut self, _ctx: &mut GameContext) {
            *self.0.borrow_mut() += 1;
        }
    }
    let mut app = TestApp::new();
    force_controller(&mut app);
    let count = Rc::new(RefCell::new(0));
    app.push_state(Noticing(Rc::clone(&count)));
    app.dispatch_controller(&InputEvent::ControllerRemoved { instance_id: 0 });
    app.tick(1.0 / 60.0);
    assert_eq!(*count.borrow(), 1);
    assert!(app
        .main_lines()
        .iter()
        .any(|line| line.starts_with("Controller disconnected.")));
    app.shutdown();
}

/// Rumble reaches the bound pad only while active and haptics are on.
#[test]
fn rumble_is_guarded_by_active_and_haptics() {
    let mut m = ControllerManager::detached(true, true);
    let pad = FakePad::new(0);
    let handle = pad.handle();
    m.bind_device(Box::new(pad), "pad");
    m.rumble.alert();
    m.tick(0.016);
    assert!(!handle.log.borrow().rumbles.is_empty());
    handle.log.borrow_mut().rumbles.clear();
    m.set_haptics_enabled(false);
    m.rumble.alert();
    m.tick(0.016);
    assert!(handle.log.borrow().rumbles.is_empty());
    m.shutdown();
}
