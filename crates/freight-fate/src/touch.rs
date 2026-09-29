//! Touch gestures as desktop key presses: the iOS game's input surface.
//!
//! The iPhone and iPad game is the desktop game, spoken through Prism and
//! driven by the same states, so a gesture does not get its own meaning: it
//! becomes the key a keyboard player would press. `ios/ff_touch.m` recognizes
//! the gestures (with VoiceOver on, through a direct-interaction element) and
//! queues a code for each; [`TouchInput`] turns the codes into
//! [`InputEvent`]s. Nothing here touches UIKit, so the whole mapping is tested
//! on every platform.

use crate::states::base::{InputEvent, Key, Mods};

/// A gesture recognized by the native touch surface.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
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
            _ => return None,
        })
    }

    /// The key a single press of this gesture stands for, if it is a press.
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
            | Gesture::HoldEnded => return None,
        })
    }
}

/// What one gesture asks of the shell.
#[derive(Debug, Default, PartialEq)]
pub struct TouchOutput {
    pub events: Vec<InputEvent>,
    /// Show or hide the on-screen keyboard, for the letter commands.
    pub toggle_keyboard: bool,
}

/// The gesture-to-key translator, holding the one key a finger can hold.
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
            Gesture::HoldUpperBegan | Gesture::HoldLowerBegan => {
                self.release_into(&mut out.events);
                let key = if gesture == Gesture::HoldUpperBegan {
                    Key::Up
                } else {
                    Key::Down
                };
                out.events.push(key_down(key));
                self.held = Some(key);
            }
            Gesture::HoldEnded => self.release_into(&mut out.events),
            other => {
                if let Some(key) = other.key() {
                    out.events.push(key_down(key));
                    out.events.push(InputEvent::KeyUp {
                        key,
                        mods: Mods::NONE,
                    });
                }
            }
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
        for code in 0..25 {
            assert!(Gesture::from_code(code).is_some(), "code {code}");
        }
        assert_eq!(Gesture::from_code(25), None);
        assert_eq!(Gesture::from_code(-1), None);
    }

    #[test]
    fn menu_gestures_press_and_release_the_menu_keys() {
        let mut touch = TouchInput::new();
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
            let out = touch.handle(gesture);
            assert_eq!(
                out.events,
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
        assert_eq!(touch.held(), None);
    }

    #[test]
    fn review_gestures_carry_the_typed_character() {
        let mut touch = TouchInput::new();
        let out = touch.handle(Gesture::TwoFingerSwipeLeft);
        assert!(matches!(
            out.events.first(),
            Some(InputEvent::KeyDown {
                key: Key::Comma,
                text: Some(','),
                ..
            })
        ));
        let out = touch.handle(Gesture::MagicTap);
        assert!(matches!(
            out.events.first(),
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
        assert_eq!(pressed(&out), vec![Key::Up]);
        assert_eq!(out.events.len(), 1);
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
                InputEvent::KeyDown {
                    key: Key::Down,
                    mods: Mods::NONE,
                    text: None,
                    repeat: false,
                },
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
