//! Freight Fate core: everything that needs no window, no audio device, no
//! screen reader and no network. World data, the simulation, the career
//! models, and the spoken-text rules the rest of the game renders.
//!
//! Ported module by module from `src/freight_fate/` (Python); each module
//! here keeps the name of the Python module it replaces.

pub mod pyfmt;
pub mod pyrandom;
pub mod units;

pub mod input_hints;
pub mod message_log;
pub mod speech_pacing;
pub mod speech_text;
