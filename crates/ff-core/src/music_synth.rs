//! Synthesized music: pieces the game composes itself from a seed, for the
//! no-AI music source. Headless -- composing and rendering touch no device.

pub mod rng;
pub mod style;

pub use style::{menu_rung, menu_style, style, StyleId};
