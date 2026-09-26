use super::*;

#[test]
fn test_busy_follows_the_projection() {
    let (mut pacer, clock) = make_pacer();
    assert!(!pacer.busy());
    flush(&mut pacer, CHATTER);
    assert!(pacer.busy());
    clock.advance(10.0);
    assert!(!pacer.busy());
    flush(&mut pacer, CHATTER);
    pacer.reset();
    assert!(!pacer.busy());
}

// -- the S4 driving verbosity ladder (tests/test_driving_speech_ladder.py)

/// "coaching" was a fourth rung and is gone (2026-08-17).
///
/// It never differed from standard at the voice -- measured on two
/// scenarios, byte-identical transcripts -- because its two table cells
/// only bite where a coaching tip repeats and the game has exactly one
/// line in that category. A setting that offers a choice and changes
/// nothing audible is worse than one fewer choice in a game played by
/// ear. The CATEGORY survives; the rung does not.
#[test]
fn test_the_ladder_has_three_named_rungs() {
    assert_eq!(DRIVING_SPEECH_MODES, ["standard", "quiet", "urgent_only"]);
    assert!(disposition_row("coaching").is_none());
}

#[test]
fn test_every_rung_rules_on_every_category() {
    for mode in DRIVING_SPEECH_MODES {
        for category in SpeechCategory::ALL {
            assert!(Disposition::ALL.contains(&disposition_for(mode, Some(category))));
        }
    }
}

#[test]
fn test_safety_and_immediate_navigation_speak_at_every_rung() {
    // R1's never-dropped contract outranks the ladder. A rung may
    // shorten these; it may never silence them.
    for mode in DRIVING_SPEECH_MODES {
        for category in [SpeechCategory::Safety, SpeechCategory::Navigation] {
            assert!(matches!(
                disposition_for(mode, Some(category)),
                Disposition::Full | Disposition::Terse
            ));
        }
    }
}

#[test]
fn test_an_untagged_line_speaks_at_every_rung() {
    // A call site nobody has classified yet must be too loud, never silent.
    for mode in DRIVING_SPEECH_MODES {
        assert!(matches!(
            disposition_for(mode, None),
            Disposition::Full | Disposition::Terse
        ));
    }
}

#[test]
fn test_the_table_reads_exactly_as_the_spec_says() {
    assert_eq!(
        *disposition_row("standard").unwrap(),
        [
            (SpeechCategory::Safety, Disposition::Full),
            (SpeechCategory::Money, Disposition::Full),
            (SpeechCategory::Navigation, Disposition::Full),
            (SpeechCategory::NavigationAdvisory, Disposition::Full),
            (SpeechCategory::Coaching, Disposition::FirstOccurrence),
            (SpeechCategory::Confirmation, Disposition::Full),
            (SpeechCategory::Status, Disposition::Transitions),
        ]
    );
    assert_eq!(
        *disposition_row("quiet").unwrap(),
        [
            (SpeechCategory::Safety, Disposition::Terse),
            (SpeechCategory::Money, Disposition::Terse),
            (SpeechCategory::Navigation, Disposition::Terse),
            (SpeechCategory::NavigationAdvisory, Disposition::Terse),
            (SpeechCategory::Coaching, Disposition::Earcon),
            (SpeechCategory::Confirmation, Disposition::Terse),
            (SpeechCategory::Status, Disposition::Terse),
        ]
    );
    assert_eq!(
        *disposition_row("urgent_only").unwrap(),
        [
            (SpeechCategory::Safety, Disposition::Terse),
            (SpeechCategory::Money, Disposition::Silent),
            (SpeechCategory::Navigation, Disposition::Terse),
            (SpeechCategory::NavigationAdvisory, Disposition::Earcon),
            (SpeechCategory::Coaching, Disposition::Silent),
            (SpeechCategory::Confirmation, Disposition::Earcon),
            (SpeechCategory::Status, Disposition::Silent),
        ]
    );
}

#[test]
fn test_an_unknown_rung_falls_back_to_standard() {
    assert_eq!(
        disposition_for("nonsense", Some(SpeechCategory::Status)),
        Disposition::Transitions
    );
}

/// A guard against the shape of the bug, not just this instance of it.
///
/// If a later change makes every category quiet and urgent_only disagree
/// on inaudible at quiet, the two settings become indistinguishable again
/// however different the table looks.
#[test]
fn test_the_two_quietest_rungs_are_not_the_same_setting() {
    let quiet = disposition_row("quiet").unwrap();
    let urgent = disposition_row("urgent_only").unwrap();
    let audible = [
        Disposition::Full,
        Disposition::Terse,
        Disposition::FirstOccurrence,
        Disposition::Transitions,
    ];
    let differ: Vec<SpeechCategory> = quiet
        .iter()
        .filter(|(category, disposition)| row_disposition(urgent, *category) != Some(*disposition))
        .map(|(category, _)| *category)
        .collect();
    assert!(!differ.is_empty(), "the rungs are identical");
    assert!(
        differ
            .iter()
            .any(|c| audible.contains(&row_disposition(quiet, *c).unwrap())),
        "quiet and urgent_only differ only in categories quiet already \
             silences, so a player switching between them hears no change"
    );
}

/// Owner playtest, 2026-08-17: "the hazard earcon is being used double
/// in some places."
///
/// CONFIRMATION borrowed the shipped "Hazard clear" chime instead of
/// having a cue of its own, so at quiet every silenced confirmation
/// played "you got past the hazard" -- including "Automatic braking.",
/// which fires while the hazard is still there and the truck is braking
/// for it. That is the exact failure `ladder_earcons`' own docstring
/// forbids: one sound teaching a player two things.
///
/// Pinned as a rule rather than as one mapping, so the next category
/// added to the ladder cannot quietly borrow a different loaded sound.
#[test]
fn test_no_ladder_earcon_borrows_a_sound_that_already_means_something() {
    // Sounds that already carry a meaning of their own on the road.
    let spoken_for = [
        "Hazard clear",
        "Hazard warning",
        "Collision",
        "Overspeed",
        "Low air",
    ];
    let borrowed: Vec<_> = LADDER_EARCONS
        .iter()
        .filter(|(_, name)| spoken_for.contains(name))
        .collect();
    assert!(
        borrowed.is_empty(),
        "ladder earcon borrows a loaded sound: {borrowed:?}"
    );

    // And every ladder earcon is its own sound, not shared between two
    // categories -- which would be the same bug wearing a different hat.
    let mut names: Vec<&str> = LADDER_EARCONS.iter().map(|(_, name)| *name).collect();
    names.sort_unstable();
    names.dedup();
    assert_eq!(names.len(), LADDER_EARCONS.len());
    assert_eq!(ladder_earcon(SpeechCategory::Status), Some("Status note"));
    assert_eq!(ladder_earcon(SpeechCategory::Safety), None);
}

/// Quiet and urgent_only must not be able to drop a line as already-said.
///
/// Both quieter rungs deliver every category TERSE, EARCON, or SILENT --
/// the earcon/silent gate returns before `_ladder_repeats` is reached,
/// and a TERSE line is never dropped -- so the suppression that swallowed
/// 310 lines on standard could not touch them. That is a property of the
/// TABLE, not of the code, and it is exactly the kind of thing a later
/// table edit changes without anyone noticing: moving one quiet cell to
/// TRANSITIONS would silently hand quiet a leg-scoped memory it has never
/// had. Pinned so that edit has to be deliberate.
#[test]
fn test_only_standard_can_reach_the_already_said_gate() {
    let reaches_the_gate = [Disposition::FirstOccurrence, Disposition::Transitions];
    for rung in ["quiet", "urgent_only"] {
        let offenders: Vec<_> = disposition_row(rung)
            .unwrap()
            .iter()
            .filter(|(_, disposition)| reaches_the_gate.contains(disposition))
            .collect();
        assert!(
            offenders.is_empty(),
            "{rung} now reaches the already-said gate for {offenders:?}; \
                 that gate is standard's alone (Darren, 2026-08-19)"
        );
    }
}

#[test]
fn test_enum_values_round_trip() {
    for category in SpeechCategory::ALL {
        assert_eq!(SpeechCategory::from_value(category.value()), Some(category));
    }
    assert_eq!(SpeechCategory::from_value("flavor"), None);
    assert_eq!(Disposition::FirstOccurrence.value(), "first");
    assert!(EventPriority::Critical > EventPriority::Route);
    assert!(EventPriority::Route > EventPriority::Ambient);
}
