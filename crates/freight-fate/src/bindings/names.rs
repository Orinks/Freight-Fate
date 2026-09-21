//! Key and pad button names: the id the settings file stores and the words
//! the screen reader says.

use crate::controller::ControllerButton;
use crate::states::base::Key;

/// `(key, saved id, spoken name)` for every key a shortcut can land on.
const KEYS: &[(Key, &str, &str)] = &[
    (Key::A, "a", "A"),
    (Key::B, "b", "B"),
    (Key::C, "c", "C"),
    (Key::D, "d", "D"),
    (Key::E, "e", "E"),
    (Key::F, "f", "F"),
    (Key::G, "g", "G"),
    (Key::H, "h", "H"),
    (Key::I, "i", "I"),
    (Key::J, "j", "J"),
    (Key::K, "k", "K"),
    (Key::L, "l", "L"),
    (Key::M, "m", "M"),
    (Key::N, "n", "N"),
    (Key::O, "o", "O"),
    (Key::P, "p", "P"),
    (Key::Q, "q", "Q"),
    (Key::R, "r", "R"),
    (Key::S, "s", "S"),
    (Key::T, "t", "T"),
    (Key::U, "u", "U"),
    (Key::V, "v", "V"),
    (Key::W, "w", "W"),
    (Key::X, "x", "X"),
    (Key::Y, "y", "Y"),
    (Key::Z, "z", "Z"),
    (Key::Num0, "0", "0"),
    (Key::Num1, "1", "1"),
    (Key::Num2, "2", "2"),
    (Key::Num3, "3", "3"),
    (Key::Num4, "4", "4"),
    (Key::Num5, "5", "5"),
    (Key::Num6, "6", "6"),
    (Key::Num7, "7", "7"),
    (Key::Num8, "8", "8"),
    (Key::Num9, "9", "9"),
    (Key::Kp0, "kp_0", "keypad 0"),
    (Key::Kp1, "kp_1", "keypad 1"),
    (Key::Kp2, "kp_2", "keypad 2"),
    (Key::Kp3, "kp_3", "keypad 3"),
    (Key::Kp4, "kp_4", "keypad 4"),
    (Key::Kp5, "kp_5", "keypad 5"),
    (Key::Kp6, "kp_6", "keypad 6"),
    (Key::Kp7, "kp_7", "keypad 7"),
    (Key::Kp8, "kp_8", "keypad 8"),
    (Key::Kp9, "kp_9", "keypad 9"),
    (Key::KpEnter, "kp_enter", "keypad Enter"),
    (Key::KpPlus, "kp_plus", "keypad plus"),
    (Key::KpMinus, "kp_minus", "keypad minus"),
    (Key::F1, "f1", "F1"),
    (Key::F2, "f2", "F2"),
    (Key::F3, "f3", "F3"),
    (Key::F4, "f4", "F4"),
    (Key::F5, "f5", "F5"),
    (Key::F6, "f6", "F6"),
    (Key::F7, "f7", "F7"),
    (Key::F8, "f8", "F8"),
    (Key::F9, "f9", "F9"),
    (Key::F10, "f10", "F10"),
    (Key::F11, "f11", "F11"),
    (Key::F12, "f12", "F12"),
    (Key::Return, "enter", "Enter"),
    (Key::Escape, "escape", "Escape"),
    (Key::Space, "space", "Space"),
    (Key::Tab, "tab", "Tab"),
    (Key::Backspace, "backspace", "Backspace"),
    (Key::Up, "up", "the Up arrow"),
    (Key::Down, "down", "the Down arrow"),
    (Key::Left, "left", "the Left arrow"),
    (Key::Right, "right", "the Right arrow"),
    (Key::Home, "home", "Home"),
    (Key::End, "end", "End"),
    (Key::PageUp, "page_up", "Page Up"),
    (Key::PageDown, "page_down", "Page Down"),
    (Key::Insert, "insert", "Insert"),
    (Key::Delete, "delete", "Delete"),
    (Key::Comma, "comma", "comma"),
    (Key::Period, "period", "period"),
    (Key::Slash, "slash", "slash"),
    (Key::Backslash, "backslash", "backslash"),
    (Key::Backquote, "grave", "grave accent"),
    (Key::Equals, "equals", "equals"),
    (Key::Plus, "plus", "plus"),
    (Key::Minus, "minus", "minus"),
    (Key::Semicolon, "semicolon", "semicolon"),
    (Key::Quote, "apostrophe", "apostrophe"),
    (Key::LeftBracket, "left_bracket", "left bracket"),
    (Key::RightBracket, "right_bracket", "right bracket"),
    (Key::LCtrl, "left_ctrl", "Left Control"),
    (Key::RCtrl, "right_ctrl", "Right Control"),
    (Key::LShift, "left_shift", "Left Shift"),
    (Key::RShift, "right_shift", "Right Shift"),
    (Key::LAlt, "left_alt", "Left Alt"),
    (Key::RAlt, "right_alt", "Right Alt"),
];

/// The id the settings file stores for `key`; `None` for a key the game
/// has no name for.
pub fn key_saved_name(key: Key) -> Option<&'static str> {
    KEYS.iter().find(|(k, ..)| *k == key).map(|(_, id, _)| *id)
}

/// The key as the screen reader says it.
pub fn key_spoken_name(key: Key) -> String {
    match KEYS.iter().find(|(k, ..)| *k == key) {
        Some((_, _, spoken)) => (*spoken).to_string(),
        None => "an unnamed key".to_string(),
    }
}

pub fn parse_key_name(id: &str) -> Option<Key> {
    KEYS.iter().find(|(_, i, _)| *i == id).map(|(k, ..)| *k)
}

/// `(button, saved id, short spoken name)`.
const PAD: &[(ControllerButton, &str, &str)] = &[
    (ControllerButton::A, "a", "A"),
    (ControllerButton::B, "b", "B"),
    (ControllerButton::X, "x", "X"),
    (ControllerButton::Y, "y", "Y"),
    (ControllerButton::Back, "back", "Back"),
    (ControllerButton::Guide, "guide", "the guide button"),
    (ControllerButton::Start, "start", "Start"),
    (
        ControllerButton::LeftStick,
        "left_stick",
        "the left stick click",
    ),
    (
        ControllerButton::RightStick,
        "right_stick",
        "the right stick click",
    ),
    (
        ControllerButton::LeftShoulder,
        "left_bumper",
        "the left bumper",
    ),
    (
        ControllerButton::RightShoulder,
        "right_bumper",
        "the right bumper",
    ),
    (ControllerButton::DPadUp, "dpad_up", "D-pad up"),
    (ControllerButton::DPadDown, "dpad_down", "D-pad down"),
    (ControllerButton::DPadLeft, "dpad_left", "D-pad left"),
    (ControllerButton::DPadRight, "dpad_right", "D-pad right"),
    (ControllerButton::Misc1, "misc", "the extra button"),
    (ControllerButton::Paddle1, "paddle_1", "paddle 1"),
    (ControllerButton::Paddle2, "paddle_2", "paddle 2"),
    (ControllerButton::Paddle3, "paddle_3", "paddle 3"),
    (ControllerButton::Paddle4, "paddle_4", "paddle 4"),
    (ControllerButton::Touchpad, "touchpad", "the touchpad"),
];

pub(super) fn pad_button_saved_name(button: ControllerButton) -> &'static str {
    PAD.iter()
        .find(|(b, ..)| *b == button)
        .map(|(_, id, _)| *id)
        .unwrap_or("unknown")
}

/// The button as a hint names it after "right bumper plus".
pub fn pad_button_short_name(button: ControllerButton) -> &'static str {
    PAD.iter()
        .find(|(b, ..)| *b == button)
        .map(|(_, _, spoken)| *spoken)
        .unwrap_or("an unnamed button")
}

pub(super) fn parse_pad_button_name(id: &str) -> Option<ControllerButton> {
    PAD.iter().find(|(_, i, _)| *i == id).map(|(b, ..)| *b)
}
