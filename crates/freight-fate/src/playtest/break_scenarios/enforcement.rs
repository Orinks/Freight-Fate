//! Enforcement guidance under deliberate mis-play (port of
//! `tools/playtest_break_scenarios/enforcement.py`).
//!
//! Tester Jerry's weigh-station report (2026-08-12): the open-scale
//! announcement said "press T", T at speed planned a sleep stop past the
//! scale, X then armed that truck stop's exit, and following both spoken
//! instructions crossed the scale unarmed at speed straight into a bypass
//! pull-over -- with the exit assist still steering for the truck-stop ramp
//! under the trooper's lights. This family drives the fixed contract end to
//! end with the real driving state.

use crate::playtest::breaker::{outcome, Outcome, Rig, RigOptions, DT};
use crate::states::base::Key;

use ff_core::sim::enforcement_posts::{EnforcementPost, KIND_FIXED_SCALE, METHOD_SCALE_SCREEN};
use ff_core::sim::trip::Trip;
use ff_core::sim::trip_models::RoadStop;

pub const SCALE_MI: f64 = 4.0;
pub const TRUCKSTOP_MI: f64 = 5.0;

/// One open scale with a sleep-capable travel center just past it.
pub fn inject_open_scale(trip: &mut Trip) -> (RoadStop, RoadStop) {
    let mut scale = RoadStop::new("Hamburg Scale", SCALE_MI, "weigh_station");
    scale.actions = vec!["inspect".to_string()];
    scale.parking = "none".to_string();
    let mut truckstop = RoadStop::new("Blue Beacon Travel Plaza", TRUCKSTOP_MI, "travel_center");
    truckstop.actions = ["park", "save", "fuel", "food", "break", "sleep"]
        .iter()
        .map(|action| action.to_string())
        .collect();
    truckstop.parking = "confirmed".to_string();
    truckstop.exit_label = "exit 55".to_string();
    trip.stops = vec![scale.clone(), truckstop.clone()];
    let mut post = EnforcementPost::new(SCALE_MI, KIND_FIXED_SCALE);
    post.method = METHOD_SCALE_SCREEN.to_string();
    post.reach_mi = 1.0;
    post.staffed = true;
    post.anchor = scale.key();
    trip.posts = vec![post];
    (scale, truckstop)
}

/// Follow the scale announcement literally -- T mid-warning, then X: both must
/// serve the scale.
pub fn scale_check_in_guidance() -> Outcome {
    let mut rig = Rig::new(RigOptions::default());
    let mut findings: Vec<String> = Vec::new();
    let (scale, _truckstop) = inject_open_scale(&mut rig.drive.trip);
    rig.prepare(54.0, None);
    rig.press(Key::K); // cruise at the limit: the scale is the only demand

    let ran = rig.step(
        20000,
        DT,
        Some(&|rig: &Rig| rig.said("Open weigh station") > 0),
    );
    if rig.said("Open weigh station") == 0 {
        findings.push(format!("no open-scale announcement in {ran} frames"));
        return outcome("scale_check_in_guidance", &rig, findings, "");
    }
    let notice = rig.lines_with("Open weigh station")[0].clone();
    if notice.contains("press T for inspection check-in") {
        findings.push("the announcement still teaches the rest key at speed".to_string());
    }
    // Capital-S since the mainline-crawl rewording.
    if !notice.contains("ignal for the scale exit") {
        findings.push("the announcement never teaches the exit key".to_string());
    }

    // Jerry's press: T immediately, mid-announcement in real audio.
    rig.press(Key::T);
    if rig.said("Planned sleep stop selected") > 0 {
        findings.push(
            "T mid scale warning planned a sleep stop past the scale instead of deferring"
                .to_string(),
        );
    }
    if rig.said("Weigh station first") == 0 {
        findings.push("T mid scale warning never said the scale comes first".to_string());
    }

    // Then X, following the announcement's exit instruction. Full lane keeping
    // pins the exit-lane mechanics out of the way: this scenario is about
    // WHICH exit the press serves, not lane work.
    rig.app.ctx.settings.lane_keeping = "full".to_string();
    rig.press(Key::X);
    match rig.drive.exit_stop.as_ref() {
        None => findings.push("X after the scale warning armed no exit at all".to_string()),
        Some(_) if !rig.drive.exit_signal_on => {
            findings.push("X after the scale warning armed no exit at all".to_string())
        }
        Some(stop) if stop.key() != scale.key() => findings.push(format!(
            "X armed the exit for {}, not the scale's inspection lane",
            stop.name
        )),
        Some(_) => {}
    }

    // Ride the capped cruise down to the gore. Compliance must end on the
    // scale's own ramp with no enforcement lights anywhere in the run.
    rig.step(
        20000,
        DT,
        Some(&|rig: &Rig| {
            rig.drive.ramp_mi.is_some()
                || rig.drive.pull_over.is_some()
                || rig.drive.trip.position_mi > SCALE_MI + 0.3
        }),
    );
    if rig.drive.pull_over.is_some() || rig.said("Scale bypass enforcement") > 0 {
        findings.push(
            "following both spoken instructions still ended in a bypass pull-over".to_string(),
        );
    }
    let on_scale_ramp = rig
        .drive
        .ramp_stop
        .as_ref()
        .is_some_and(|stop| stop.key() == scale.key());
    if !on_scale_ramp {
        findings.push(format!(
            "the truck never ended up on the scale's own ramp (position {:.2}, {:.0} mph)",
            rig.drive.trip.position_mi,
            rig.drive.truck().speed_mph()
        ));
    }
    outcome(
        "scale_check_in_guidance",
        &rig,
        findings,
        "T deferred to the scale, X armed the inspection lane, no bypass charge",
    )
}

/// Blow past the scale with a truck-stop exit armed: the pull-over must own
/// the road.
pub fn scale_pull_over_stands_down_exit() -> Outcome {
    let mut rig = Rig::new(RigOptions::default());
    let mut findings: Vec<String> = Vec::new();
    let (_scale, truckstop) = inject_open_scale(&mut rig.drive.trip);
    rig.prepare(54.0, None);
    // Recreate the pre-fix wreckage by force: exit armed for the truck stop
    // (not the scale), then blow the scale at speed.
    rig.drive.trip.position_mi = SCALE_MI - 0.1;
    rig.drive.enforcement_prev_mi = rig.drive.trip.position_mi;
    rig.drive.exit_stop = Some(truckstop);
    rig.drive.exit_signal_on = true;
    rig.drive.cruise_exit_mph = Some(40.0);
    rig.step(60, DT, Some(&|rig: &Rig| rig.drive.pull_over.is_some()));
    if rig.drive.pull_over.is_none() {
        findings.push("an unarmed 54 mph scale crossing was never charged".to_string());
    }
    if rig.drive.exit_signal_on || rig.drive.exit_stop.is_some() {
        findings.push(
            "the armed truck-stop exit kept announcing and steering during the pull-over"
                .to_string(),
        );
    }
    if rig.drive.cruise_exit_mph.is_some() {
        findings.push("the ramp cruise cap survived into the trooper stop".to_string());
    }
    outcome(
        "scale_pull_over_stands_down_exit",
        &rig,
        findings,
        "the pull-over stood the armed exit down; one demand on the driver",
    )
}
