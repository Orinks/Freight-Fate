//! Player-chosen controls: which key, and which pad button, does what at the
//! wheel.
//!
//! Every discrete driving control is an [`Action`]. Each action has a
//! default keyboard chord (a key plus the modifiers held with it) and, for
//! the ones the pad reaches, a default button on the plain or the
//! right-bumper layer. A player can move any of them from Settings, Gameplay,
//! Controls; the choice is saved in `Settings` as text and rebuilt into a
//! [`KeyBindings`] table on the context, which is what the driving state and
//! the spoken hints read.
//!
//! What stays fixed, on purpose: Escape for the pause menu, Enter to confirm,
//! F1 for help, the Control keys that stop the event voice, the clutch on
//! Shift and the left bumper, plus and minus for the cruise target, the radio
//! dial keys, the message-review keys, and every menu key. Those are either
//! the screen reader's own vocabulary or a control with several physical
//! keys already, and moving them would cost more than it gives. On the pad,
//! Start (pause), Back (stop the voice, then help), the two bumpers and the
//! analog triggers and sticks stay where they are for the same reasons.
//!
//! A chord matches exactly: Shift K is its own binding, separate from K. A
//! key pressed with modifiers that no binding claims falls back to the bare
//! key's action, which is how the table always behaved (Shift held for the
//! clutch never stopped W from shifting up, and Alt E still starts the
//! engine).

use std::collections::HashMap;

use ff_core::settings::Settings;

use crate::app::held_keys::HeldKeys;
use crate::controller::ControllerButton;
use crate::states::base::{Key, Mods};

mod names;

pub use names::{key_saved_name, key_spoken_name, pad_button_short_name, parse_key_name};

/// One discrete driving control a player can move to another key or button.
///
/// The order here is the order of the rows on the shortcuts screens.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Action {
    Accelerate,
    Brake,
    EmergencyBrake,
    SteerLeft,
    SteerRight,
    Straighten,
    Engine,
    ParkingBrake,
    Horn,
    Cruise,
    CruiseResume,
    /// Pad only: the keyboard's plus and minus keys stay fixed.
    CruiseUp,
    CruiseDown,
    TakeExit,
    Rest,
    Status,
    Speed,
    SpeedLimit,
    SafeSpeed,
    Fuel,
    Clock,
    Route,
    Weather,
    Lane,
    LaneLocator,
    Grade,
    Upcoming,
    LastAnnouncement,
    Cb,
    HosWheel,
    HosBreak,
    HosDrive,
    PlaceState,
    PlaceRoad,
    PlaceTown,
    PlaceDirection,
    EngineBrake,
    AutoJake,
    JakeStage1,
    JakeStage2,
    JakeStage3,
    /// Pad only: one button walks the stages the keyboard has three keys for.
    CycleJake,
    ShiftUp,
    ShiftDown,
    Neutral,
    Reverse,
    TransmissionMode,
    Radio,
    RadioFavorite,
    RadioStatus,
    RadioNowPlaying,
}

/// A key with the modifiers held with it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Chord {
    pub key: Key,
    pub mods: Mods,
}

impl Chord {
    pub const fn plain(key: Key) -> Chord {
        Chord {
            key,
            mods: Mods::NONE,
        }
    }

    pub const fn shift(key: Key) -> Chord {
        Chord {
            key,
            mods: Mods::SHIFT,
        }
    }

    pub const fn alt(key: Key) -> Chord {
        Chord {
            key,
            mods: Mods::ALT,
        }
    }

    /// The chord as a player hears it: "Alt J", "the Up arrow", "T".
    pub fn spoken(&self) -> String {
        let mut out = String::new();
        if self.mods.ctrl {
            out.push_str("Control ");
        }
        if self.mods.alt {
            out.push_str("Alt ");
        }
        if self.mods.shift {
            out.push_str("Shift ");
        }
        out.push_str(&key_spoken_name(self.key));
        out
    }

    /// The chord as the settings file stores it: "alt+j", "up", "shift+k".
    pub fn saved(&self) -> Option<String> {
        let key = key_saved_name(self.key)?;
        let mut out = String::new();
        if self.mods.ctrl {
            out.push_str("ctrl+");
        }
        if self.mods.alt {
            out.push_str("alt+");
        }
        if self.mods.shift {
            out.push_str("shift+");
        }
        out.push_str(key);
        Some(out)
    }

    pub fn parse(text: &str) -> Option<Chord> {
        let mut mods = Mods::NONE;
        let mut key = None;
        for part in text.split('+') {
            match part {
                "ctrl" => mods.ctrl = true,
                "alt" => mods.alt = true,
                "shift" => mods.shift = true,
                name => key = Some(parse_key_name(name)?),
            }
        }
        key.map(|key| Chord { key, mods })
    }
}

/// A pad button, on the plain layer or with the right bumper held.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct PadChord {
    pub button: ControllerButton,
    pub modified: bool,
}

impl PadChord {
    pub const fn plain(button: ControllerButton) -> PadChord {
        PadChord {
            button,
            modified: false,
        }
    }

    pub const fn modified(button: ControllerButton) -> PadChord {
        PadChord {
            button,
            modified: true,
        }
    }

    /// As a hint names it: "the A button", "D-pad down", "right bumper plus
    /// Y".
    pub fn spoken(&self) -> String {
        let short = pad_button_short_name(self.button);
        if self.modified {
            format!("right bumper plus {short}")
        } else if matches!(
            self.button,
            ControllerButton::A | ControllerButton::B | ControllerButton::X | ControllerButton::Y
        ) {
            format!("the {short} button")
        } else {
            short.to_string()
        }
    }

    pub fn saved(&self) -> String {
        let name = names::pad_button_saved_name(self.button);
        if self.modified {
            format!("mod+{name}")
        } else {
            name.to_string()
        }
    }

    pub fn parse(text: &str) -> Option<PadChord> {
        let (modified, name) = match text.strip_prefix("mod+") {
            Some(rest) => (true, rest),
            None => (false, text),
        };
        names::parse_pad_button_name(name).map(|button| PadChord { button, modified })
    }
}

/// `(action, saved id, spoken label, default keyboard chords, default pad
/// chords)`. A control with more than one default chord keeps them all
/// until the player moves it, and then has only the chord they chose.
type Row = (
    Action,
    &'static str,
    &'static str,
    &'static [Chord],
    &'static [PadChord],
);

use ControllerButton as Pad;

const TABLE: &[Row] = &[
    (
        Action::Accelerate,
        "accelerate",
        "Accelerate",
        &[Chord::plain(Key::Up)],
        &[],
    ),
    (
        Action::Brake,
        "brake",
        "Brake",
        &[Chord::plain(Key::Down)],
        &[],
    ),
    (
        Action::EmergencyBrake,
        "emergency_brake",
        "Emergency brake",
        &[Chord::plain(Key::B)],
        &[],
    ),
    (
        Action::SteerLeft,
        "steer_left",
        "Steer left",
        &[Chord::plain(Key::Left)],
        &[],
    ),
    (
        Action::SteerRight,
        "steer_right",
        "Steer right",
        &[Chord::plain(Key::Right)],
        &[],
    ),
    (
        Action::Straighten,
        "straighten",
        "Straighten up",
        &[Chord::plain(Key::Slash)],
        &[],
    ),
    (
        Action::Engine,
        "engine",
        "Engine on or off",
        &[Chord::plain(Key::E)],
        &[PadChord::modified(Pad::A)],
    ),
    (
        Action::ParkingBrake,
        "parking_brake",
        "Parking brake",
        &[Chord::plain(Key::P)],
        &[PadChord::modified(Pad::Y)],
    ),
    (
        Action::Horn,
        "horn",
        "Horn",
        &[Chord::plain(Key::H)],
        &[PadChord::plain(Pad::LeftStick)],
    ),
    (
        Action::Cruise,
        "cruise",
        "Automatic speed control",
        &[Chord::plain(Key::K)],
        &[PadChord::plain(Pad::Y)],
    ),
    (
        Action::CruiseResume,
        "cruise_resume",
        "Resume the last cruise speed",
        &[Chord::shift(Key::K)],
        &[],
    ),
    (
        Action::CruiseUp,
        "cruise_up",
        "Cruise target up",
        &[],
        &[PadChord::modified(Pad::DPadRight)],
    ),
    (
        Action::CruiseDown,
        "cruise_down",
        "Cruise target down",
        &[],
        &[PadChord::modified(Pad::DPadLeft)],
    ),
    (
        Action::TakeExit,
        "take_exit",
        "Signal for the exit or a pull-over",
        &[Chord::plain(Key::X)],
        &[PadChord::plain(Pad::DPadDown)],
    ),
    (
        Action::Rest,
        "rest",
        "Rest stop",
        &[Chord::plain(Key::T)],
        &[PadChord::modified(Pad::DPadDown)],
    ),
    (
        Action::Status,
        "status",
        "Status menu",
        &[Chord::plain(Key::Tab)],
        &[PadChord::modified(Pad::Start)],
    ),
    (
        Action::Speed,
        "speed",
        "Speed",
        &[Chord::plain(Key::Space)],
        &[PadChord::plain(Pad::B)],
    ),
    (
        Action::SpeedLimit,
        "speed_limit",
        "Posted speed limit",
        &[Chord::plain(Key::S)],
        &[PadChord::modified(Pad::X)],
    ),
    (
        Action::SafeSpeed,
        "safe_speed",
        "Safe speed",
        &[Chord::plain(Key::D)],
        &[],
    ),
    (
        Action::Fuel,
        "fuel",
        "Fuel",
        &[Chord::plain(Key::F)],
        &[PadChord::modified(Pad::B)],
    ),
    (
        Action::Clock,
        "clock",
        "Clock",
        &[Chord::plain(Key::C)],
        &[PadChord::plain(Pad::DPadRight)],
    ),
    (
        Action::Route,
        "route",
        "Route and location",
        &[Chord::plain(Key::R)],
        &[
            PadChord::plain(Pad::DPadUp),
            PadChord::modified(Pad::DPadUp),
        ],
    ),
    (
        Action::Weather,
        "weather",
        "Weather",
        &[Chord::plain(Key::V)],
        &[PadChord::plain(Pad::DPadLeft)],
    ),
    (
        Action::Lane,
        "lane",
        "Lane position",
        &[Chord::plain(Key::L)],
        &[],
    ),
    (
        Action::LaneLocator,
        "lane_locator",
        "Lane locator",
        &[Chord::plain(Key::I)],
        &[],
    ),
    (
        Action::Grade,
        "grade",
        "Grade",
        &[Chord::plain(Key::G)],
        &[],
    ),
    (
        Action::Upcoming,
        "upcoming",
        "Road ahead",
        &[Chord::plain(Key::U)],
        &[],
    ),
    (
        Action::LastAnnouncement,
        "last_announcement",
        "Repeat the last announcement",
        &[Chord::plain(Key::A)],
        &[],
    ),
    (
        Action::Cb,
        "cb",
        "Repeat the last CB chatter",
        &[Chord::alt(Key::C)],
        &[],
    ),
    (
        Action::HosWheel,
        "hos_wheel",
        "Time at the wheel",
        &[Chord::alt(Key::A)],
        &[],
    ),
    (
        Action::HosBreak,
        "hos_break",
        "When the break is due",
        &[Chord::alt(Key::S)],
        &[],
    ),
    (
        Action::HosDrive,
        "hos_drive",
        "What ends this shift",
        &[Chord::alt(Key::D)],
        &[],
    ),
    (
        Action::PlaceState,
        "place_state",
        "The state",
        &[Chord::alt(Key::Num1), Chord::alt(Key::Kp1)],
        &[],
    ),
    (
        Action::PlaceRoad,
        "place_road",
        "The road",
        &[Chord::alt(Key::Num2), Chord::alt(Key::Kp2)],
        &[],
    ),
    (
        Action::PlaceTown,
        "place_town",
        "The town",
        &[Chord::alt(Key::Num3), Chord::alt(Key::Kp3)],
        &[],
    ),
    (
        Action::PlaceDirection,
        "place_direction",
        "The direction",
        &[Chord::alt(Key::Num4), Chord::alt(Key::Kp4)],
        &[],
    ),
    (
        Action::EngineBrake,
        "engine_brake",
        "Engine brake",
        &[Chord::plain(Key::J)],
        &[PadChord::plain(Pad::RightStick)],
    ),
    (
        Action::AutoJake,
        "auto_jake",
        "Automatic engine brake on or off",
        &[Chord::alt(Key::J)],
        &[],
    ),
    (
        Action::JakeStage1,
        "jake_stage_1",
        "Engine brake stage 1",
        &[Chord::plain(Key::Num1)],
        &[],
    ),
    (
        Action::JakeStage2,
        "jake_stage_2",
        "Engine brake stage 2",
        &[Chord::plain(Key::Num2)],
        &[],
    ),
    (
        Action::JakeStage3,
        "jake_stage_3",
        "Engine brake stage 3",
        &[Chord::plain(Key::Num3)],
        &[],
    ),
    (
        Action::CycleJake,
        "cycle_jake",
        "Next engine brake stage",
        &[],
        &[PadChord::modified(Pad::RightStick)],
    ),
    (
        Action::ShiftUp,
        "shift_up",
        "Shift up",
        &[Chord::plain(Key::W)],
        &[PadChord::plain(Pad::A)],
    ),
    (
        Action::ShiftDown,
        "shift_down",
        "Shift down",
        &[Chord::plain(Key::Q)],
        &[PadChord::plain(Pad::X)],
    ),
    (
        Action::Neutral,
        "neutral",
        "Neutral",
        &[Chord::plain(Key::N)],
        &[],
    ),
    (
        Action::Reverse,
        "reverse",
        "Reverse",
        &[Chord::plain(Key::Backspace)],
        &[],
    ),
    (
        Action::TransmissionMode,
        "transmission_mode",
        "Automatic or manual shifting",
        &[Chord::alt(Key::T)],
        &[],
    ),
    (
        Action::Radio,
        "radio",
        "Radio on or off",
        &[Chord::plain(Key::M)],
        &[],
    ),
    (
        Action::RadioFavorite,
        "radio_favorite",
        "Save the station as a favorite",
        &[Chord::plain(Key::O)],
        &[],
    ),
    (
        Action::RadioStatus,
        "radio_status",
        "Radio status",
        &[Chord::plain(Key::Y)],
        &[],
    ),
    (
        Action::RadioNowPlaying,
        "radio_now_playing",
        "What the radio is playing",
        &[Chord::shift(Key::Y)],
        &[],
    ),
];

fn row(action: Action) -> &'static Row {
    TABLE
        .iter()
        .find(|(a, ..)| *a == action)
        .expect("every Action has a row in TABLE")
}

impl Action {
    /// Every action, in screen order.
    pub fn all() -> impl Iterator<Item = Action> {
        TABLE.iter().map(|(a, ..)| *a)
    }

    /// The id the settings file stores.
    pub fn id(self) -> &'static str {
        row(self).1
    }

    pub fn from_id(id: &str) -> Option<Action> {
        TABLE.iter().find(|(_, i, ..)| *i == id).map(|(a, ..)| *a)
    }

    /// The row label: what the control does.
    pub fn label(self) -> &'static str {
        row(self).2
    }

    pub fn default_chords(self) -> &'static [Chord] {
        row(self).3
    }

    pub fn default_pad_chords(self) -> &'static [PadChord] {
        row(self).4
    }

    /// Whether the keyboard has this control at all.
    pub fn on_keyboard(self) -> bool {
        !self.default_chords().is_empty()
    }

    /// Whether the pad has this control at all.
    pub fn on_pad(self) -> bool {
        !self.default_pad_chords().is_empty()
    }
}

/// Why a key cannot be chosen, as the screen says it.
pub fn reserved_key_reason(chord: &Chord) -> Option<&'static str> {
    let bare = chord.mods == Mods::NONE;
    let fixed = match chord.key {
        Key::Escape => Some("Escape is the pause menu"),
        Key::Return | Key::KpEnter => Some("Enter confirms"),
        Key::F1 => Some("F1 is help"),
        Key::LCtrl | Key::RCtrl | Key::LShift | Key::RShift | Key::LAlt | Key::RAlt => {
            Some("a modifier key on its own cannot be a shortcut")
        }
        Key::Equals | Key::Plus | Key::KpPlus | Key::Minus | Key::KpMinus => {
            Some("plus and minus set the cruise target")
        }
        Key::PageUp | Key::PageDown | Key::Semicolon | Key::Quote => {
            Some("the radio dial keys are fixed")
        }
        Key::Comma | Key::Period | Key::LeftBracket | Key::RightBracket => {
            Some("the message review keys are fixed")
        }
        Key::Other(_) => Some("that key cannot be used"),
        _ => None,
    };
    if let Some(reason) = fixed {
        // Escape, F1 and the modifier keys are fixed however they are
        // pressed (the first two are answered before the table is asked);
        // the rest are only claimed bare, so Alt with a review key is free.
        let always = matches!(
            chord.key,
            Key::Escape
                | Key::F1
                | Key::LCtrl
                | Key::RCtrl
                | Key::LShift
                | Key::RShift
                | Key::LAlt
                | Key::RAlt
                | Key::Other(_)
        );
        if bare || always {
            return Some(reason);
        }
    }
    if chord.key == Key::C && chord.mods == Mods::CTRL {
        return Some("Control C copies the message in review");
    }
    None
}

/// Why a pad chord cannot be chosen, as the screen says it.
pub fn reserved_pad_reason(chord: &PadChord) -> Option<&'static str> {
    match chord.button {
        ControllerButton::LeftShoulder => Some("the left bumper is the clutch"),
        ControllerButton::RightShoulder => Some("the right bumper is the second layer"),
        ControllerButton::Guide => Some("the guide button belongs to the system"),
        ControllerButton::Start if !chord.modified => Some("Start is pause"),
        ControllerButton::Back if !chord.modified => {
            Some("Back stops the driving voice and reads help")
        }
        _ => None,
    }
}

/// The result of asking for a new binding.
#[derive(Debug, PartialEq, Eq)]
pub enum Rebind {
    Done,
    /// The chord already belongs to this action.
    Unchanged,
    Reserved(&'static str),
    /// Another action has the chord.
    Taken(Action),
}

/// The live table: defaults plus what the player moved.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct KeyBindings {
    keys: HashMap<Action, Chord>,
    pad: HashMap<Action, PadChord>,
}

impl KeyBindings {
    /// The table `settings` describes; unreadable entries are ignored, so
    /// one bad line never costs the rest.
    pub fn from_settings(settings: &Settings) -> KeyBindings {
        let mut out = KeyBindings::default();
        for (id, value) in entries(&settings.key_bindings) {
            if let (Some(action), Some(chord)) = (Action::from_id(id), Chord::parse(value)) {
                if action.on_keyboard() {
                    out.keys.insert(action, chord);
                }
            }
        }
        for (id, value) in entries(&settings.pad_bindings) {
            if let (Some(action), Some(chord)) = (Action::from_id(id), PadChord::parse(value)) {
                if action.on_pad() {
                    out.pad.insert(action, chord);
                }
            }
        }
        out
    }

    /// Write the moved controls back into `settings`.
    pub fn store(&self, settings: &mut Settings) {
        let mut keys: Vec<String> = Vec::new();
        let mut pad: Vec<String> = Vec::new();
        for action in Action::all() {
            if let Some(saved) = self.keys.get(&action).and_then(Chord::saved) {
                keys.push(format!("{}={saved}", action.id()));
            }
            if let Some(chord) = self.pad.get(&action) {
                pad.push(format!("{}={}", action.id(), chord.saved()));
            }
        }
        settings.key_bindings = keys.join(";");
        settings.pad_bindings = pad.join(";");
    }

    /// True when nothing has been moved from its default.
    pub fn is_default(&self) -> bool {
        self.keys.is_empty() && self.pad.is_empty()
    }

    pub fn reset(&mut self) {
        self.keys.clear();
        self.pad.clear();
    }

    pub fn reset_keys(&mut self) {
        self.keys.clear();
    }

    pub fn reset_pad(&mut self) {
        self.pad.clear();
    }

    // -- keyboard ----------------------------------------------------------------

    /// The chords that trigger `action` today.
    pub fn chords(&self, action: Action) -> Vec<Chord> {
        match self.keys.get(&action) {
            Some(chord) => vec![*chord],
            None => action.default_chords().to_vec(),
        }
    }

    /// The control's name for a spoken prompt, first chord only.
    pub fn spoken(&self, action: Action) -> String {
        self.chords(action)
            .first()
            .map(Chord::spoken)
            .unwrap_or_else(|| action.label().to_string())
    }

    /// The action a key press means: the exact chord if one is bound, else
    /// the bare key's action.
    pub fn action_for(&self, key: Key, mods: Mods) -> Option<Action> {
        self.exact_action(&Chord { key, mods }).or_else(|| {
            if mods == Mods::NONE {
                None
            } else {
                self.exact_action(&Chord::plain(key))
            }
        })
    }

    fn exact_action(&self, chord: &Chord) -> Option<Action> {
        Action::all().find(|action| self.chords(*action).contains(chord))
    }

    /// Whether `action`'s key is down right now, modifiers included.
    pub fn pressed(&self, input: &HeldKeys, action: Action) -> bool {
        let held = input.mods();
        self.chords(action).iter().any(|chord| {
            input.is_pressed(chord.key)
                && (!chord.mods.shift || held.shift)
                && (!chord.mods.ctrl || held.ctrl)
                && (!chord.mods.alt || held.alt)
        })
    }

    /// Move `action` to `chord`.
    pub fn set_chord(&mut self, action: Action, chord: Chord) -> Rebind {
        if let Some(reason) = reserved_key_reason(&chord) {
            return Rebind::Reserved(reason);
        }
        if self.chords(action).contains(&chord) {
            return Rebind::Unchanged;
        }
        if let Some(other) = self.exact_action(&chord) {
            return Rebind::Taken(other);
        }
        if action.default_chords() == [chord] {
            self.keys.remove(&action);
        } else {
            self.keys.insert(action, chord);
        }
        Rebind::Done
    }

    // -- pad ---------------------------------------------------------------------

    pub fn pad_chords(&self, action: Action) -> Vec<PadChord> {
        match self.pad.get(&action) {
            Some(chord) => vec![*chord],
            None => action.default_pad_chords().to_vec(),
        }
    }

    pub fn pad_spoken(&self, action: Action) -> String {
        self.pad_chords(action)
            .first()
            .map(PadChord::spoken)
            .unwrap_or_else(|| action.label().to_string())
    }

    pub fn pad_action_for(&self, button: ControllerButton, modified: bool) -> Option<Action> {
        let chord = PadChord { button, modified };
        Action::all().find(|action| self.pad_chords(*action).contains(&chord))
    }

    pub fn set_pad_chord(&mut self, action: Action, chord: PadChord) -> Rebind {
        if let Some(reason) = reserved_pad_reason(&chord) {
            return Rebind::Reserved(reason);
        }
        if self.pad_chords(action).contains(&chord) {
            return Rebind::Unchanged;
        }
        if let Some(other) = self.pad_action_for(chord.button, chord.modified) {
            return Rebind::Taken(other);
        }
        if action.default_pad_chords() == [chord] {
            self.pad.remove(&action);
        } else {
            self.pad.insert(action, chord);
        }
        Rebind::Done
    }

    // -- spoken hints -------------------------------------------------------------

    /// The keyboard phrase for a `control_hint` action id, when the hint
    /// names a control the player can move; `None` leaves the fixed table's
    /// wording alone.
    pub fn hint_key_phrase(&self, hint: &str) -> Option<String> {
        Some(match hint {
            "gears" => format!(
                "{} and {}",
                self.spoken(Action::ShiftUp),
                self.spoken(Action::ShiftDown)
            ),
            "gear_first" => self.spoken(Action::ShiftUp),
            other => self.spoken(hint_action(other)?),
        })
    }

    /// The pad phrase for a `control_hint` action id, same contract. The
    /// two-button phrases keep the table's tighter wording ("the A and X
    /// buttons") until one of the pair moves.
    pub fn hint_pad_phrase(&self, hint: &str) -> Option<String> {
        let pair = |a: Action, b: Action, joiner: &str| {
            if self.pad.contains_key(&a) || self.pad.contains_key(&b) {
                Some(format!(
                    "{} {joiner} {}",
                    self.pad_spoken(a),
                    self.pad_spoken(b)
                ))
            } else {
                None
            }
        };
        let action = match hint {
            "gear_first" => Action::ShiftUp,
            "cruise_adjust" => return pair(Action::CruiseDown, Action::CruiseUp, "or"),
            "gears" => return pair(Action::ShiftUp, Action::ShiftDown, "and"),
            other => hint_action(other)?,
        };
        if !action.on_pad() {
            return None;
        }
        Some(self.pad_spoken(action))
    }
}

/// The `input_hints` action ids that name a movable control.
fn hint_action(hint: &str) -> Option<Action> {
    Some(match hint {
        "accelerate" => Action::Accelerate,
        "brake" => Action::Brake,
        "emergency_brake" => Action::EmergencyBrake,
        "reverse" => Action::Reverse,
        "neutral" => Action::Neutral,
        "engine" => Action::Engine,
        "parking_brake" => Action::ParkingBrake,
        "take_exit" => Action::TakeExit,
        "rest" => Action::Rest,
        "cruise_set" => Action::Cruise,
        "speed" => Action::Speed,
        "status_menu" => Action::Status,
        "fuel" => Action::Fuel,
        "clock" => Action::Clock,
        "route" => Action::Route,
        "weather" => Action::Weather,
        "lane" => Action::Lane,
        "horn" => Action::Horn,
        "engine_brake" => Action::EngineBrake,
        _ => return None,
    })
}

/// `id=value` pairs from a saved bindings string.
fn entries(text: &str) -> impl Iterator<Item = (&str, &str)> {
    text.split(';')
        .filter(|part| !part.is_empty())
        .filter_map(|part| part.split_once('='))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_default_chord_is_saveable_and_unreserved() {
        for action in Action::all() {
            for chord in action.default_chords() {
                assert!(chord.saved().is_some(), "{action:?}");
                assert_eq!(reserved_key_reason(chord), None, "{action:?}");
                assert_eq!(Chord::parse(&chord.saved().unwrap()), Some(*chord));
            }
            for chord in action.default_pad_chords() {
                assert_eq!(reserved_pad_reason(chord), None, "{action:?}");
                assert_eq!(PadChord::parse(&chord.saved()), Some(*chord));
            }
            assert_eq!(Action::from_id(action.id()), Some(action));
        }
    }

    #[test]
    fn no_two_actions_share_a_default_chord() {
        let mut seen: HashMap<Chord, Action> = HashMap::new();
        for action in Action::all() {
            for chord in action.default_chords() {
                assert!(
                    seen.insert(*chord, action).is_none(),
                    "{chord:?} is both {action:?} and {:?}",
                    seen[chord]
                );
            }
        }
        let mut seen: HashMap<PadChord, Action> = HashMap::new();
        for action in Action::all() {
            for chord in action.default_pad_chords() {
                assert!(
                    seen.insert(*chord, action).is_none(),
                    "{chord:?} is both {action:?} and {:?}",
                    seen[chord]
                );
            }
        }
    }

    #[test]
    fn a_chord_with_unbound_modifiers_falls_back_to_the_bare_key() {
        let b = KeyBindings::default();
        assert_eq!(b.action_for(Key::E, Mods::ALT), Some(Action::Engine));
        assert_eq!(b.action_for(Key::W, Mods::SHIFT), Some(Action::ShiftUp));
        assert_eq!(
            b.action_for(Key::K, Mods::SHIFT),
            Some(Action::CruiseResume)
        );
        assert_eq!(b.action_for(Key::J, Mods::ALT), Some(Action::AutoJake));
        assert_eq!(b.action_for(Key::Num1, Mods::ALT), Some(Action::PlaceState));
        assert_eq!(
            b.action_for(Key::Num1, Mods::NONE),
            Some(Action::JakeStage1)
        );
        assert_eq!(b.action_for(Key::Escape, Mods::NONE), None);
    }

    #[test]
    fn moving_a_key_frees_the_old_one_and_refuses_a_taken_one() {
        let mut b = KeyBindings::default();
        assert_eq!(
            b.set_chord(Action::Engine, Chord::plain(Key::T)),
            Rebind::Taken(Action::Rest)
        );
        assert_eq!(
            b.set_chord(Action::Engine, Chord::plain(Key::Z)),
            Rebind::Done
        );
        assert_eq!(b.action_for(Key::Z, Mods::NONE), Some(Action::Engine));
        assert_eq!(b.action_for(Key::E, Mods::NONE), None);
        assert_eq!(
            b.set_chord(Action::Engine, Chord::plain(Key::Z)),
            Rebind::Unchanged
        );
        assert_eq!(
            b.set_chord(Action::Engine, Chord::plain(Key::Escape)),
            Rebind::Reserved("Escape is the pause menu")
        );
        // Back to the default clears the override rather than recording it.
        assert_eq!(
            b.set_chord(Action::Engine, Chord::plain(Key::E)),
            Rebind::Done
        );
        assert!(b.is_default());
    }

    #[test]
    fn bindings_round_trip_through_settings() {
        let mut b = KeyBindings::default();
        b.set_chord(Action::Engine, Chord::alt(Key::Z));
        b.set_chord(Action::Accelerate, Chord::plain(Key::F5));
        b.set_pad_chord(Action::Horn, PadChord::modified(ControllerButton::Paddle1));
        let mut settings = Settings::default();
        b.store(&mut settings);
        assert_eq!(settings.key_bindings, "accelerate=f5;engine=alt+z");
        assert_eq!(settings.pad_bindings, "horn=mod+paddle_1");
        assert_eq!(KeyBindings::from_settings(&settings), b);
        // A default table writes nothing.
        KeyBindings::default().store(&mut settings);
        assert_eq!(settings.key_bindings, "");
        assert_eq!(settings.pad_bindings, "");
    }

    #[test]
    fn garbage_in_the_settings_is_ignored() {
        let settings = Settings {
            key_bindings: "engine=nope;teleport=t;horn=alt+;=;;accelerate=w".to_string(),
            ..Settings::default()
        };
        let b = KeyBindings::from_settings(&settings);
        assert_eq!(b.chords(Action::Engine), vec![Chord::plain(Key::E)]);
        assert_eq!(b.chords(Action::Accelerate), vec![Chord::plain(Key::W)]);
    }

    #[test]
    fn default_hint_phrases_match_the_fixed_table() {
        let b = KeyBindings::default();
        for (hint, _) in ff_core::input_hints::HINTS {
            let expected_kb =
                ff_core::input_hints::control_hint(hint, ff_core::input_hints::KEYBOARD);
            if let Some(phrase) = b.hint_key_phrase(hint) {
                assert_eq!(phrase, expected_kb, "{hint}");
            }
            let expected_pad =
                ff_core::input_hints::control_hint(hint, ff_core::input_hints::CONTROLLER);
            if let Some(phrase) = b.hint_pad_phrase(hint) {
                assert_eq!(phrase, expected_pad, "{hint}");
            }
        }
    }

    #[test]
    fn a_moved_key_changes_the_hint() {
        let mut b = KeyBindings::default();
        b.set_chord(Action::Engine, Chord::plain(Key::Z));
        assert_eq!(b.hint_key_phrase("engine").as_deref(), Some("Z"));
        b.set_pad_chord(Action::Engine, PadChord::plain(ControllerButton::Paddle2));
        assert_eq!(b.hint_pad_phrase("engine").as_deref(), Some("paddle 2"));
    }
}
