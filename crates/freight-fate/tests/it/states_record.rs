//! The reasons behind the record: every citation and violation booked at
//! the wheel keeps why, what it cost, when, and where, and Career stats
//! opens the list newest first.

use crate::states_city_support::*;
use crate::states_driving_menus_support::{a_drive, with_drive};
use ff_core::models::enforcement::{self, RECORD_ENTRIES_KEPT};
use ff_core::models::profile::Profile;
use freight_fate::app::testing::TestApp;
use freight_fate::states::base::SimpleMenuState;
use freight_fate::states::career_stats::{record_lines, CareerStatsState};

#[test]
fn test_a_citation_at_the_wheel_keeps_its_reason_fine_and_place() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    with_drive(&drive, |d| {
        d.log_enforcement(
            &mut app.ctx,
            340.0,
            false,
            false,
            "Speeding, 12 miles per hour over the 65 limit",
        );
    });
    let record = &app.ctx.profile.as_ref().unwrap().driving_record;
    assert_eq!(record.citations, 1);
    assert_eq!(record.entries.len(), 1);
    let entry = &record.entries[0];
    assert_eq!(entry.kind, enforcement::RECORD_CITATION);
    assert_eq!(
        entry.reason,
        "Speeding, 12 miles per hour over the 65 limit"
    );
    assert_eq!(entry.fine, 340.0);
    assert!(entry.place.contains("I-90"), "{}", entry.place);
    assert!(entry.place.contains("New York"), "{}", entry.place);
    assert_eq!(record.unexplained_citations(), 0);
}

#[test]
fn test_serious_and_major_bookings_keep_their_kind() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    with_drive(&drive, |d| {
        d.log_enforcement(
            &mut app.ctx,
            1_000.0,
            true,
            false,
            "Drove through the barrels in a work zone",
        );
        d.log_enforcement(
            &mut app.ctx,
            2_500.0,
            false,
            true,
            "Ran from a traffic stop",
        );
    });
    let record = &app.ctx.profile.as_ref().unwrap().driving_record;
    assert_eq!(record.entries[0].kind, enforcement::RECORD_SERIOUS);
    assert_eq!(record.entries[1].kind, enforcement::RECORD_MAJOR);
    assert_eq!(record.serious_violations.len(), 1);
    assert_eq!(record.major_offenses.len(), 1);
}

#[test]
fn test_career_stats_opens_the_list_newest_first() {
    let mut app = TestApp::new();
    career(&mut app, "Record List", "Chicago");
    {
        let record = &mut app.ctx.profile.as_mut().unwrap().driving_record;
        record.record_citation_at(200.0, 30.0);
        record.note(
            enforcement::RECORD_CITATION,
            "Ran the red light",
            200.0,
            30.0,
            "I-90 East near Gary, Indiana",
        );
        record.record_citation_at(340.0, 50.0);
        record.note(
            enforcement::RECORD_CITATION,
            "Speeding, 12 miles per hour over the 65 limit",
            340.0,
            50.0,
            "I-65 South, Indiana",
        );
    }
    let lines = record_lines(&app.ctx);
    assert_eq!(
        lines[0],
        "Citation, day 3, 2 AM: Speeding, 12 miles per hour over the 65 limit. 340 dollars. \
         On I-65 South, Indiana."
    );
    assert_eq!(
        lines[1],
        "Citation, day 2, 6 AM: Ran the red light. 200 dollars. On I-90 East near Gary, Indiana."
    );
    assert_eq!(lines.len(), 2);

    app.push_state(CareerStatsState::new());
    select::<CareerStatsState>(&mut app, "Citations and violations");
    assert!(is::<SimpleMenuState>(&app));
    let rows = labels::<SimpleMenuState>(&app);
    assert_eq!(rows[0], lines[0]);
    assert_eq!(rows.last().map(String::as_str), Some("Back"));
}

#[test]
fn test_counts_from_before_reasons_were_kept_are_said_once() {
    let mut app = TestApp::new();
    career(&mut app, "Old Record", "Chicago");
    {
        let record = &mut app.ctx.profile.as_mut().unwrap().driving_record;
        record.record_citation_at(200.0, 30.0);
        record.record_citation_at(200.0, 40.0);
        record.record_citation_at(150.0, 60.0);
        record.note(
            enforcement::RECORD_CITATION,
            "Ran the stop sign",
            150.0,
            60.0,
            "US-30, Indiana",
        );
    }
    let lines = record_lines(&app.ctx);
    assert_eq!(lines.len(), 2, "{lines:?}");
    assert_eq!(
        lines[1],
        "2 earlier citations recorded before reasons were kept."
    );

    let clean = Profile::named_in("Clean", "Chicago");
    app.ctx.profile = Some(clean);
    assert_eq!(
        record_lines(&app.ctx),
        vec!["No citations or violations on your record.".to_string()]
    );
}

#[test]
fn test_the_list_keeps_the_newest_entries_when_it_fills() {
    let mut record = enforcement::DrivingRecord::new();
    for i in 0..(RECORD_ENTRIES_KEPT + 5) {
        record.record_citation_at(100.0, i as f64);
        record.note(
            enforcement::RECORD_CITATION,
            "Speeding",
            100.0,
            i as f64,
            "",
        );
    }
    assert_eq!(record.entries.len(), RECORD_ENTRIES_KEPT);
    assert_eq!(record.entries[0].game_hours, 5.0);
    assert_eq!(record.unexplained_citations(), 5);
}
