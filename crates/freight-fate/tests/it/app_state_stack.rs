//! Port of `tests/test_state_stack.py`: what enters, what exits, and what
//! ends the game.
//!
//! Rebuilding the stack (quit to the title, arriving at a facility) empties
//! it on the way to a new screen. Only the player backing out of the last
//! state should end the run.

use std::cell::RefCell;
use std::rc::Rc;

use freight_fate::app::testing::TestApp;
use freight_fate::app::GameContext;
use freight_fate::states::base::State;

type Log = Rc<RefCell<Vec<(&'static str, &'static str)>>>;

/// A screen that notes when it is entered and left.
struct RecordingState {
    name: &'static str,
    log: Log,
}

impl State for RecordingState {
    fn enter(&mut self, _ctx: &mut GameContext) {
        self.log.borrow_mut().push(("enter", self.name));
    }

    fn exit(&mut self, _ctx: &mut GameContext) {
        self.log.borrow_mut().push(("exit", self.name));
    }
}

fn app_with_stack(names: &[&'static str]) -> (TestApp, Log) {
    let mut app = TestApp::new();
    app.set_running(true);
    let log: Log = Rc::new(RefCell::new(Vec::new()));
    for name in names {
        app.push_state(RecordingState {
            name,
            log: Rc::clone(&log),
        });
    }
    log.borrow_mut().clear();
    (app, log)
}

fn names(app: &TestApp) -> Vec<&'static str> {
    app.states()
        .iter()
        .map(|s| {
            s.borrow()
                .as_any()
                .downcast_ref::<RecordingState>()
                .unwrap()
                .name
        })
        .collect()
}

#[test]
fn test_reset_to_keeps_the_game_running() {
    // Quitting a drive to the main menu must not close the game.
    let (mut app, log) = app_with_stack(&["menu", "city", "driving", "pause"]);

    app.reset_to(RecordingState {
        name: "title",
        log: Rc::clone(&log),
    });

    assert!(app.running());
    assert_eq!(names(&app), vec!["title"]);
    assert_eq!(
        *log.borrow(),
        vec![
            ("exit", "pause"),
            ("exit", "driving"),
            ("exit", "city"),
            ("exit", "menu"),
            ("enter", "title"),
        ]
    );
    app.shutdown();
}

#[test]
fn test_replace_state_on_the_last_state_keeps_the_game_running() {
    let (mut app, log) = app_with_stack(&["menu"]);

    app.replace_state(RecordingState {
        name: "notice",
        log: Rc::clone(&log),
    });

    assert!(app.running());
    assert_eq!(names(&app), vec!["notice"]);
    assert_eq!(*log.borrow(), vec![("exit", "menu"), ("enter", "notice")]);
    app.shutdown();
}

#[test]
fn test_popping_the_last_state_ends_the_game() {
    // Backing out of the final screen is still how the player leaves.
    let (mut app, log) = app_with_stack(&["menu"]);

    app.pop_state();

    assert!(!app.running());
    assert!(app.states().is_empty());
    assert_eq!(*log.borrow(), vec![("exit", "menu")]);
    app.shutdown();
}

#[test]
fn test_pop_reveals_the_state_underneath() {
    let (mut app, log) = app_with_stack(&["menu", "settings"]);

    app.pop_state();

    assert!(app.running());
    assert_eq!(*log.borrow(), vec![("exit", "settings"), ("enter", "menu")]);
    app.shutdown();
}

#[test]
fn test_rebuilt_stack_can_skip_enter_and_exit() {
    // The new-career screens drop their pickers without re-speaking them.
    let (mut app, log) = app_with_stack(&["menu", "name", "region"]);

    app.pop_state_with(true, false);
    app.reset_to_with(
        RecordingState {
            name: "city",
            log: Rc::clone(&log),
        },
        false,
        false,
    );

    assert!(app.running());
    assert_eq!(names(&app), vec!["city"]);
    assert_eq!(*log.borrow(), vec![("exit", "region")]);
    app.shutdown();
}

/// The Rust stack's one deferral: a state that pops itself from inside its
/// own handler still exits (after the handler returns), and the revealed
/// state enters at once -- the Python order for everything but that exit.
#[test]
fn a_state_popping_itself_exits_after_its_handler_and_reveals_immediately() {
    struct Popper {
        log: Log,
    }
    impl State for Popper {
        fn handle_event(
            &mut self,
            ctx: &mut GameContext,
            _event: &freight_fate::states::base::InputEvent,
        ) {
            ctx.pop_state();
            self.log.borrow_mut().push(("after-pop", "popper"));
        }
        fn exit(&mut self, _ctx: &mut GameContext) {
            self.log.borrow_mut().push(("exit", "popper"));
        }
    }
    let (mut app, log) = app_with_stack(&["menu"]);
    app.push_state_with(
        Popper {
            log: Rc::clone(&log),
        },
        false,
    );
    app.dispatch_to_state(&freight_fate::states::base::InputEvent::key(
        freight_fate::states::base::Key::Escape,
    ));
    assert_eq!(
        *log.borrow(),
        vec![
            ("enter", "menu"),
            ("after-pop", "popper"),
            ("exit", "popper"),
        ]
    );
    assert_eq!(names(&app), vec!["menu"]);
    app.shutdown();
}
