//! Touch gestures: the iOS game's input surface.
//!
//! The iPhone and iPad game is the desktop game, spoken through Prism and
//! driven by the same states. `ios/ff_touch.m` recognizes the gestures (with
//! VoiceOver on, through a direct-interaction element) and queues a code for
//! each; [`TouchInput`] turns the codes into [`InputEvent`]s. A held finger
//! is a held pedal key. Every other gesture arrives as
//! [`InputEvent::Gesture`]: the driving state runs the command the player's
//! touch bindings give it, and every other screen, or a gesture with no
//! binding, gets the key a keyboard player would press ([`Gesture::key`]).
//! Nothing here touches UIKit, so the whole mapping is tested on every
//! platform.

use crate::states::base::{InputEvent, Key, Mods};

/// A gesture recognized by the native touch surface.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Gesture {
    Tap,
    DoubleTap,
    SwipeUp,
    SwipeDown,
    SwipeLeft,
    SwipeRight,
    TwoFingerTap,
    TwoFingerSwipeUp,
    TwoFingerSwipeDown,
    TwoFingerSwipeLeft,
    TwoFingerSwipeRight,
    ThreeFingerSwipeUp,
    ThreeFingerSwipeDown,
    ThreeFingerSwipeLeft,
    ThreeFingerSwipeRight,
    ThreeFingerDoubleTap,
    /// Opens the driving command list, and reads a name field back.
    ThreeFingerTap,
    /// One finger held still on the top half of the screen.
    HoldUpperBegan,
    /// One finger held still on the bottom half of the screen.
    HoldLowerBegan,
    HoldEnded,
    /// VoiceOver's two-finger scrub.
    Escape,
    /// VoiceOver's two-finger double tap.
    MagicTap,
    /// VoiceOver's double tap, when direct touch is not active.
    Activate,
    /// VoiceOver's swipe up on the adjustable element.
    Increment,
    /// VoiceOver's swipe down on the adjustable element.
    Decrement,
    /// A second finger's tap while the top-half hold is down.
    UpperHoldTap,
    UpperHoldDoubleTap,
    UpperHoldSwipeUp,
    UpperHoldSwipeDown,
    UpperHoldSwipeLeft,
    UpperHoldSwipeRight,
    /// A second finger's tap while the bottom-half hold is down.
    LowerHoldTap,
    LowerHoldDoubleTap,
    LowerHoldSwipeUp,
    LowerHoldSwipeDown,
    LowerHoldSwipeLeft,
    LowerHoldSwipeRight,
}

impl Gesture {
    /// The code `ios/ff_touch.m` queues for this gesture.
    pub fn from_code(code: i32) -> Option<Gesture> {
        Some(match code {
            0 => Gesture::Tap,
            1 => Gesture::DoubleTap,
            2 => Gesture::SwipeUp,
            3 => Gesture::SwipeDown,
            4 => Gesture::SwipeLeft,
            5 => Gesture::SwipeRight,
            6 => Gesture::TwoFingerTap,
            7 => Gesture::TwoFingerSwipeUp,
            8 => Gesture::TwoFingerSwipeDown,
            9 => Gesture::TwoFingerSwipeLeft,
            10 => Gesture::TwoFingerSwipeRight,
            11 => Gesture::ThreeFingerSwipeUp,
            12 => Gesture::ThreeFingerSwipeDown,
            13 => Gesture::ThreeFingerDoubleTap,
            14 => Gesture::HoldUpperBegan,
            15 => Gesture::HoldLowerBegan,
            16 => Gesture::HoldEnded,
            17 => Gesture::Escape,
            18 => Gesture::MagicTap,
            19 => Gesture::Activate,
            20 => Gesture::Increment,
            21 => Gesture::Decrement,
            22 => Gesture::ThreeFingerSwipeLeft,
            23 => Gesture::ThreeFingerSwipeRight,
            24 => Gesture::ThreeFingerTap,
            25 => Gesture::UpperHoldTap,
            26 => Gesture::UpperHoldDoubleTap,
            27 => Gesture::UpperHoldSwipeUp,
            28 => Gesture::UpperHoldSwipeDown,
            29 => Gesture::UpperHoldSwipeLeft,
            30 => Gesture::UpperHoldSwipeRight,
            31 => Gesture::LowerHoldTap,
            32 => Gesture::LowerHoldDoubleTap,
            33 => Gesture::LowerHoldSwipeUp,
            34 => Gesture::LowerHoldSwipeDown,
            35 => Gesture::LowerHoldSwipeLeft,
            36 => Gesture::LowerHoldSwipeRight,
            _ => return None,
        })
    }

    /// The key a single press of this gesture stands for, if it is a press.
    /// A second finger during a hold is a driving command and nothing else.
    pub fn key(self) -> Option<Key> {
        Some(match self {
            Gesture::Tap => Key::Comma,
            Gesture::DoubleTap | Gesture::Activate => Key::Return,
            Gesture::SwipeUp | Gesture::Increment => Key::Up,
            Gesture::SwipeDown | Gesture::Decrement => Key::Down,
            Gesture::SwipeLeft => Key::Left,
            Gesture::SwipeRight => Key::Right,
            Gesture::TwoFingerTap => Key::Tab,
            Gesture::MagicTap => Key::Space,
            Gesture::TwoFingerSwipeUp => Key::F1,
            Gesture::TwoFingerSwipeDown | Gesture::Escape => Key::Escape,
            Gesture::TwoFingerSwipeLeft => Key::Comma,
            Gesture::TwoFingerSwipeRight => Key::Period,
            Gesture::ThreeFingerSwipeUp => Key::Home,
            Gesture::ThreeFingerSwipeDown => Key::End,
            Gesture::ThreeFingerSwipeLeft => Key::PageUp,
            Gesture::ThreeFingerSwipeRight => Key::PageDown,
            Gesture::ThreeFingerTap => Key::F2,
            Gesture::ThreeFingerDoubleTap
            | Gesture::HoldUpperBegan
            | Gesture::HoldLowerBegan
            | Gesture::HoldEnded
            | Gesture::UpperHoldTap
            | Gesture::UpperHoldDoubleTap
            | Gesture::UpperHoldSwipeUp
            | Gesture::UpperHoldSwipeDown
            | Gesture::UpperHoldSwipeLeft
            | Gesture::UpperHoldSwipeRight
            | Gesture::LowerHoldTap
            | Gesture::LowerHoldDoubleTap
            | Gesture::LowerHoldSwipeUp
            | Gesture::LowerHoldSwipeDown
            | Gesture::LowerHoldSwipeLeft
            | Gesture::LowerHoldSwipeRight => return None,
        })
    }

    /// The pedal key a hold keeps down: Up for the top half, Down for the
    /// bottom.
    pub fn held_key(self) -> Option<Key> {
        match self {
            Gesture::HoldUpperBegan => Some(Key::Up),
            Gesture::HoldLowerBegan => Some(Key::Down),
            _ => None,
        }
    }

    /// The press that starts [`Self::held_key`].
    pub fn hold_events(self) -> Vec<InputEvent> {
        self.held_key().map(key_down).into_iter().collect()
    }

    /// The press and release of [`Self::key`], for a screen that did not
    /// take the gesture itself.
    pub fn key_events(self) -> Vec<InputEvent> {
        match self.key() {
            Some(key) => vec![
                key_down(key),
                InputEvent::KeyUp {
                    key,
                    mods: Mods::NONE,
                },
            ],
            None => Vec::new(),
        }
    }
}

/// What one gesture asks of the shell.
#[derive(Debug, Default, PartialEq)]
pub struct TouchOutput {
    pub events: Vec<InputEvent>,
    /// Show or hide the on-screen keyboard, for the letter commands.
    pub toggle_keyboard: bool,
}

/// The gesture translator, holding the one key a finger can hold.
#[derive(Debug, Default)]
pub struct TouchInput {
    held: Option<Key>,
}

impl TouchInput {
    pub fn new() -> Self {
        Self::default()
    }

    /// The key a held finger is keeping down, if any.
    pub fn held(&self) -> Option<Key> {
        self.held
    }

    pub fn handle(&mut self, gesture: Gesture) -> TouchOutput {
        let mut out = TouchOutput::default();
        match gesture {
            Gesture::ThreeFingerDoubleTap => out.toggle_keyboard = true,
            // Top half is the accelerator, bottom half the brake: the Up and
            // Down arrows held, so the latching brake and the reverse
            // press-and-hold work exactly as they do on a keyboard.
            // The hold goes out as its gesture, and the app presses the
            // key, so the press is known to be the screen's.
            Gesture::HoldUpperBegan | Gesture::HoldLowerBegan => {
                self.release_into(&mut out.events);
                out.events.push(InputEvent::Gesture(gesture));
                self.held = gesture.held_key();
            }
            Gesture::HoldEnded => self.release_into(&mut out.events),
            other => out.events.push(InputEvent::Gesture(other)),
        }
        out
    }

    /// Let go of a held key, as when the app leaves the foreground.
    pub fn release_into(&mut self, events: &mut Vec<InputEvent>) {
        if let Some(key) = self.held.take() {
            events.push(InputEvent::KeyUp {
                key,
                mods: Mods::NONE,
            });
        }
    }
}

fn key_down(key: Key) -> InputEvent {
    let text = match key {
        Key::Space => Some(' '),
        Key::Comma => Some(','),
        Key::Period => Some('.'),
        _ => None,
    };
    InputEvent::KeyDown {
        key,
        mods: Mods::NONE,
        text,
        repeat: false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    impl Gesture {
        fn hold_events_output(self) -> TouchOutput {
            TouchOutput {
                events: self.hold_events(),
                toggle_keyboard: false,
            }
        }
    }

    fn pressed(out: &TouchOutput) -> Vec<Key> {
        out.events
            .iter()
            .filter_map(|event| match event {
                InputEvent::KeyDown { key, .. } => Some(*key),
                _ => None,
            })
            .collect()
    }

    #[test]
    fn every_native_code_round_trips_and_unknown_codes_are_ignored() {
        for code in 0..37 {
            assert!(Gesture::from_code(code).is_some(), "code {code}");
        }
        assert_eq!(Gesture::from_code(37), None);
        assert_eq!(Gesture::from_code(-1), None);
    }

    #[test]
    fn discrete_gestures_reach_the_state_as_gestures() {
        let mut touch = TouchInput::new();
        for gesture in [
            Gesture::Tap,
            Gesture::MagicTap,
            Gesture::ThreeFingerTap,
            Gesture::UpperHoldTap,
        ] {
            assert_eq!(
                touch.handle(gesture).events,
                vec![InputEvent::Gesture(gesture)]
            );
        }
        assert_eq!(touch.held(), None);
    }

    #[test]
    fn menu_gestures_press_and_release_the_menu_keys() {
        for (gesture, key) in [
            (Gesture::SwipeUp, Key::Up),
            (Gesture::SwipeDown, Key::Down),
            (Gesture::DoubleTap, Key::Return),
            (Gesture::Activate, Key::Return),
            (Gesture::TwoFingerSwipeDown, Key::Escape),
            (Gesture::Escape, Key::Escape),
            (Gesture::Increment, Key::Up),
            (Gesture::Decrement, Key::Down),
            (Gesture::TwoFingerSwipeUp, Key::F1),
            (Gesture::ThreeFingerTap, Key::F2),
        ] {
            assert_eq!(
                gesture.key_events(),
                vec![
                    InputEvent::KeyDown {
                        key,
                        mods: Mods::NONE,
                        text: None,
                        repeat: false,
                    },
                    InputEvent::KeyUp {
                        key,
                        mods: Mods::NONE,
                    },
                ],
                "{gesture:?}"
            );
        }
    }

    #[test]
    fn a_second_finger_during_a_hold_presses_no_key() {
        assert!(Gesture::UpperHoldTap.key_events().is_empty());
        assert!(Gesture::LowerHoldSwipeRight.key_events().is_empty());
    }

    #[test]
    fn review_gestures_carry_the_typed_character() {
        assert!(matches!(
            Gesture::TwoFingerSwipeLeft.key_events().first(),
            Some(InputEvent::KeyDown {
                key: Key::Comma,
                text: Some(','),
                ..
            })
        ));
        assert!(matches!(
            Gesture::MagicTap.key_events().first(),
            Some(InputEvent::KeyDown {
                key: Key::Space,
                text: Some(' '),
                ..
            })
        ));
    }

    #[test]
    fn holds_keep_the_pedal_down_until_the_finger_lifts() {
        let mut touch = TouchInput::new();
        let out = touch.handle(Gesture::HoldUpperBegan);
        assert_eq!(
            out.events,
            vec![InputEvent::Gesture(Gesture::HoldUpperBegan)]
        );
        assert_eq!(
            pressed(&Gesture::HoldUpperBegan.hold_events_output()),
            vec![Key::Up]
        );
        assert_eq!(touch.held(), Some(Key::Up));

        let out = touch.handle(Gesture::HoldEnded);
        assert_eq!(
            out.events,
            vec![InputEvent::KeyUp {
                key: Key::Up,
                mods: Mods::NONE,
            }]
        );
        assert_eq!(touch.held(), None);
    }

    #[test]
    fn a_new_hold_releases_the_old_one_first() {
        let mut touch = TouchInput::new();
        touch.handle(Gesture::HoldUpperBegan);
        let out = touch.handle(Gesture::HoldLowerBegan);
        assert_eq!(
            out.events,
            vec![
                InputEvent::KeyUp {
                    key: Key::Up,
                    mods: Mods::NONE,
                },
                InputEvent::Gesture(Gesture::HoldLowerBegan),
            ]
        );
        assert_eq!(touch.held(), Some(Key::Down));
    }

    #[test]
    fn a_lift_with_nothing_held_says_nothing() {
        let mut touch = TouchInput::new();
        assert_eq!(touch.handle(Gesture::HoldEnded), TouchOutput::default());
    }

    #[test]
    fn three_finger_double_tap_asks_for_the_keyboard_and_presses_nothing() {
        let mut touch = TouchInput::new();
        let out = touch.handle(Gesture::ThreeFingerDoubleTap);
        assert!(out.toggle_keyboard);
        assert!(out.events.is_empty());
    }
}
