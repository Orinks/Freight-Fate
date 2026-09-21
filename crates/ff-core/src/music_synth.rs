//! Synthesized music: pieces the game composes itself from a seed, for the
//! no-AI music source. Headless -- composing and rendering touch no device.

pub mod compose;
pub mod render;
pub mod rng;
pub mod style;

pub use compose::{compose, Note, Score, Voice};
pub use render::{render, SAMPLE_RATE};
pub use style::{menu_rung, menu_style, style, StyleId};
