//! Spoken message pairs: one definition, both renderings side by side.
//!
//! The terse contract (docs/speech-priority-research.md, R4) promises that
//! terse mode tells the player what to *do* and what it *cost*, and nothing
//! else -- in the shortest form the ontology allows. Making that real used
//! to depend on every call site remembering to hand-branch on the verbosity
//! setting, which is how 79 branches came to cover 711 speech call sites,
//! and how the terse hazard call drifted onto a synonym nobody diffed
//! against the help text.
//!
//! So the pair lives in ONE definition: a builder in this module renders the
//! normal and terse forms of a message side by side, where a reviewer sees
//! both, and the delivery layer (`GameContext::say` / `say_event`) picks the
//! rendering the player's speech mode asks for. Drift between the two forms
//! is structurally impossible, and the safety-critical pairs are pinned by
//! copy tests on top of that.
//!
//! Two rules bound every terse rendering (the research doc's R4):
//!
//! - **Compress words, never certainty.** A qualifier that changes a
//!   decision survives terse; parking certainty keeps all five values
//!   distinguishable.
//! - **A fixed slot grammar, recorded in docs/ontology.md.** Hazards speak
//!   as [thing, distance, target speed]; stops as [name, exit, distance,
//!   qualifier]. A bare trailing number is only parseable because the frame
//!   never shuffles, so no terse line may reorder its slots.
//!
//! Port of `freight_fate/speech_text.py`.

use std::fmt;

/// The Python `_WORD_RE = [a-z0-9]+` over the lowercased text.
fn words(text: &str) -> Vec<String> {
    text.to_lowercase()
        .split(|c: char| !c.is_ascii_lowercase() && !c.is_ascii_digit())
        .filter(|word| !word.is_empty())
        .map(str::to_string)
        .collect()
}

/// Whether a facility's type prefix only repeats words already in its name.
///
/// "cross-dock Chicago Cross-Dock" and "port Port of Indiana-Burns Harbor"
/// say the type twice; dropping the prefix there removes repetition, not
/// vocabulary (research doc R6). Match on whole words so a short label does
/// not fire on a coincidental substring ("port" must not swallow "Newport").
/// A "travel center: Love's" keeps its prefix, because the name does not
/// carry the type.
pub fn type_prefix_is_redundant(label: &str, name: &str) -> bool {
    let label_words = words(label);
    if label_words.is_empty() {
        return false;
    }
    let name_words = words(name);
    label_words.iter().all(|word| name_words.contains(word))
}

/// A facility's name with its type prefix, unless the prefix is redundant.
pub fn typed_name(label: &str, name: &str, sep: &str) -> String {
    if type_prefix_is_redundant(label, name) {
        return name.to_string();
    }
    format!("{label}{sep}{name}")
}

/// A spoken line carrying both of its renderings.
///
/// In Python the instance WAS the normal rendering -- a `str` subclass -- so
/// everything that stores, compares, logs, or formats messages kept working
/// unchanged. Here `Display` is the normal rendering and plain text converts
/// into one via `From`, so a call site can pass a `&str` where a message is
/// accepted. The delivery layer picks the rendering the player's speech mode
//! asks for. `terse == None` means the line reads the same in both modes;
/// `terse == Some("")` means terse mode drops the line whole (an earcon or
/// silence carries it instead, and it never reaches the review log -- as far
/// as the drive is concerned it was not said).
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct SpokenMessage {
    pub normal: String,
    pub terse: Option<String>,
}
