//! A safe place to learn the iPhone and iPad gesture surface.

use std::time::{Duration, Instant};

use crate::app::{GameContext, Say};
use crate::bindings::{touch_gesture_name, Action};
use crate::impl_state_for_menu;
use crate::states::base::{InputEvent, Menu, MenuCore, MenuItem, State};
use crate::touch::Gesture;

pub struct TouchPracticeState {
    last_escape: Option<Instant>,
}

impl TouchPracticeState {
    pub fn new() -> Self {
        Self { last_escape: None }
    }

    fn say_gesture(&self, ctx: &mut GameContext, gesture: Gesture) {
        let text = match gesture {
            Gesture::HoldUpperBegan => "Gas.".to_string(),
            Gesture::HoldLowerBegan => "Brake.".to_string(),
            Gesture::EmergencyBrakeHoldBegan => "Emergency brake.".to_string(),
            Gesture::HornHoldBegan => "Horn.".to_string(),
            Gesture::HoldEnded => return,
            other => match ctx.bindings.touch_command(other) {
                Some(command) => format!(
                    "{}: {}.",
                    touch_gesture_name(other).unwrap_or("Gesture"),
                    command.label()
                ),
                None => format!("{}: {}.", fixed_name(other), fixed_binding(ctx, other)),
            },
        };
        ctx.say(&text);
    }
}

pub struct TouchPracticeOfferState {
    menu: MenuCore<Self>,
}

impl TouchPracticeOfferState {
    pub fn new() -> Self {
        Self {
            menu: MenuCore::new("Practice touch gestures?"),
        }
    }
}

impl Default for TouchPracticeOfferState {
    fn default() -> Self {
        Self::new()
    }
}

impl Menu for TouchPracticeOfferState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        // Queued, so the departure line spoken just before is not cut off.
        let text = format!(
            "Before your first drive, practice the touch gestures? Practice names each \
             gesture without moving the truck. {}",
            self.current_text(ctx)
        );
        ctx.say_with(text, Say::queued());
    }

    fn build_items(&mut self, _ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        vec![
            MenuItem::new("Practice gestures", |_s: &mut Self, ctx| {
                ctx.pop_state();
                ctx.push_state(TouchPracticeState::new());
            }),
            MenuItem::new("Skip and start driving", |s: &mut Self, ctx| s.go_back(ctx)),
        ]
    }
}

impl_state_for_menu!(TouchPracticeOfferState);

impl Default for TouchPracticeState {
    fn default() -> Self {
        Self::new()
    }
}

impl State for TouchPracticeState {
    fn enter(&mut self, ctx: &mut GameContext) {
        ctx.say("Practice gestures. Gestures are named but do not control the truck. Escape twice within two seconds to leave.");
    }

    fn handle_event(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        if matches!(
            event,
            InputEvent::KeyDown {
                key: crate::states::base::Key::Escape,
                ..
            }
        ) {
            ctx.pop_state();
        }
    }

    fn handle_gesture(&mut self, ctx: &mut GameContext, gesture: Gesture) -> bool {
        if matches!(gesture, Gesture::Escape | Gesture::TwoFingerSwipeDown) {
            let now = Instant::now();
            if self
                .last_escape
                .is_some_and(|then| now.duration_since(then) <= Duration::from_secs(2))
            {
                ctx.say("Leaving gesture practice.");
                ctx.pop_state();
            } else {
                self.last_escape = Some(now);
                ctx.say("Escape again to leave practice.");
            }
        } else {
            self.last_escape = None;
            self.say_gesture(ctx, gesture);
        }
        true
    }
}

fn fixed_name(gesture: Gesture) -> &'static str {
    match gesture {
        Gesture::Tap => "Tap",
        Gesture::DoubleTap | Gesture::Activate => "Double tap",
        Gesture::SwipeUp | Gesture::Increment => "Swipe up",
        Gesture::SwipeDown | Gesture::Decrement => "Swipe down",
        Gesture::SwipeLeft => "Swipe left",
        Gesture::SwipeRight => "Swipe right",
        Gesture::TwoFingerTap => "Two-finger tap",
        Gesture::MagicTap => "Magic tap",
        Gesture::TwoFingerSwipeUp => "Two-finger swipe up",
        Gesture::TwoFingerSwipeLeft => "Two-finger swipe left",
        Gesture::TwoFingerSwipeRight => "Two-finger swipe right",
        Gesture::ThreeFingerTap => "Three-finger tap",
        Gesture::ThreeFingerSwipeUp => "Three-finger swipe up",
        Gesture::ThreeFingerSwipeDown => "Three-finger swipe down",
        Gesture::ThreeFingerSwipeLeft => "Three-finger swipe left",
        Gesture::ThreeFingerSwipeRight => "Three-finger swipe right",
        Gesture::ThreeFingerDoubleTap => "Three-finger double tap",
        _ => "Gesture",
    }
}

fn fixed_binding(ctx: &GameContext, gesture: Gesture) -> String {
    match gesture {
        Gesture::HoldUpperBegan => ctx.control_name(Action::Accelerate),
        Gesture::HoldLowerBegan => ctx.control_name(Action::Brake),
        Gesture::EmergencyBrakeHoldBegan => ctx.control_name(Action::EmergencyBrake),
        Gesture::HornHoldBegan => ctx.control_name(Action::Horn),
        Gesture::MagicTap => "pause".to_string(),
        _ => "fixed command".to_string(),
    }
}
