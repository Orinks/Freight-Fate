//! Driving/physics abuse: floor it, reverse it, dynamite it (port of
//! `tools/playtest_break_scenarios/driving_physics.py`).
//!
//! Every scenario here puts the truck in a position no sane driver would
//! choose and checks whether the physics, the ledgers, and the spoken cues
//! stay honest about the consequences.

use crate::playtest::breaker::{fabricated_curve, outcome, Outcome, Rig, RigOptions, DT};
use crate::states::base::Key;
use crate::states::driving_core::{hos_of, FLAT_SPOT_WEAR_PCT_PER_MPH};

/// Flooring it must produce a real pull-over or nothing at all.
///
/// This scenario used to check a "speeding strike" ledger: hold nine over for
/// six seconds anywhere on the route and the drive banked a charge, billed at
/// the dock. That was a fine from an officer who was never there, and it is
/// gone. What replaces it is the harder question -- when the road DOES charge
/// you, was there a trooper, and did the player hear them?
pub fn floor_it_through_town() -> Outcome {
    let mut rig = Rig::new(RigOptions::default());
    let mut findings: Vec<String> = Vec::new();
    let money_before = rig.app.ctx.profile.as_ref().map(|p| p.money).unwrap_or(0.0);
    rig.prepare(30.0, None);
    rig.hold(Key::Up);
    let target = 25.0f64.min(rig.drive.trip.total_miles() - 8.0);
    rig.step(
        9000,
        DT,
        Some(&move |rig: &Rig| rig.drive.trip.position_mi >= target),
    );

    // Nothing may bank a charge behind the player's back any more.
    for ghost in ["Speeding strike", "due at delivery", "dollar maximum"] {
        if !rig.lines_with(ghost).is_empty() {
            findings.push(format!(
                "the removed silent speeding charge still speaks: {ghost:?}"
            ));
        }
    }
    let money_now = rig.app.ctx.profile.as_ref().map(|p| p.money).unwrap_or(0.0);
    let money_delta = money_now - money_before;
    let tickets = rig.drive.speeding_tickets;
    let fines = rig.drive.ticket_fines_paid;
    if money_delta < 0.0 && tickets == 0 {
        findings.push(format!(
            "money fell {:.0} with no traffic stop on the record: speeding nobody saw is \
             supposed to cost nothing",
            -money_delta
        ));
    }
    // A ticket is real money, so it has to have had a real officer behind it
    // -- and the player has to have heard them coming.
    if tickets != 0 {
        if rig.lines_with("Lights and siren behind you").is_empty() {
            findings.push(format!(
                "{tickets} ticket(s) written with no lights-and-siren call: the player was \
                 charged by an officer they never heard"
            ));
        }
        if (money_delta + fines).abs() > 0.01 {
            findings.push(format!(
                "ticket ledger mismatch: money moved {money_delta:+.0} but tickets total {fines:.0}"
            ));
        }
    }
    let every_post_heard = rig
        .drive
        .trip
        .posts
        .iter()
        .filter(|post| post.declined || !post.staffed)
        .all(|post| post.announced);
    if !every_post_heard {
        findings.push("a post acted on the driver before it had made a sound".to_string());
    }
    let note =
        format!("{tickets} traffic stop(s), {fines:.0} dollars, every one of them audible first");
    outcome("floor_it_through_town", &rig, findings, &note)
}

pub fn hairpin_at_70_no_assists() -> Outcome {
    let mut rig = Rig::new(RigOptions::default());
    let mut findings: Vec<String> = Vec::new();
    rig.app.ctx.settings.curve_speed_assist = false;
    rig.app.ctx.settings.route_transition_assist = false;
    let start = 12.0;
    rig.drive.trip.position_mi = start;
    rig.drive.trip.curves = vec![fabricated_curve(start + 1.0, 25, 'R')];
    rig.prepare(70.0, None);
    let damage_before = rig.drive.truck().damage_pct;
    rig.hold(Key::Up);
    rig.step(
        6000,
        DT,
        Some(&move |rig: &Rig| rig.drive.trip.position_mi >= start + 2.0),
    );
    if rig.said("too fast, drifting to the outside") == 0 {
        findings.push("no drifting-outside warning through a hairpin taken 45 over".to_string());
    }
    let min_speed = rig.drive.truck().speed_mph();
    let damage_delta = rig.drive.truck().damage_pct - damage_before;
    if damage_delta == 0.0 {
        findings.push(
            "blew a 25-advisory hairpin at 70 (assists and lane drift off): zero damage, no \
             crash, no spoken consequence beyond the warning -- the bend cannot hurt you"
                .to_string(),
        );
    }
    let note = format!(
        "hairpin punished the overspeed (damage +{damage_delta:.0}, min {min_speed:.0} mph)"
    );
    outcome("hairpin_at_70_no_assists", &rig, findings, &note)
}

pub fn reverse_down_the_route() -> Outcome {
    let mut rig = Rig::new(RigOptions::default());
    let mut findings: Vec<String> = Vec::new();
    rig.drive.trip.position_mi = 1.0;
    rig.prepare(0.0, None);
    // The deliberate direction gesture: a FRESH brake press at a standstill,
    // held through the confirmation beat.
    rig.run_frames(5); // settle with no keys so the press below is a rising edge
    rig.hold(Key::Down);
    rig.run_frames(60); // > DIRECTION_CHANGE_HOLD_S at DT
    if !rig.drive.truck().transmission.in_reverse() {
        findings.push("standstill reverse gesture never engaged reverse".to_string());
        return outcome("reverse_down_the_route", &rig, findings, "");
    }
    let mut max_reverse_mph = 0.0f64;
    let mut backed_mi = 0.0;
    for _ in 0..7200 {
        rig.drive.update_frame(&mut rig.app.ctx, DT);
        rig.app.ctx.run_deferred();
        max_reverse_mph = max_reverse_mph.max(rig.drive.truck().speed_mph());
        backed_mi = 1.0 - rig.drive.trip.position_mi;
        rig.check_invariants();
        if rig.drive.trip.position_mi <= 0.0 {
            break;
        }
    }
    rig.run_frames(300); // keep backing against the route origin
    if max_reverse_mph > 11.0 {
        findings.push(format!(
            "reverse reached {max_reverse_mph:.1} mph (cap should be ~10)"
        ));
    }
    if rig.drive.trip.position_mi < 0.0 {
        findings.push("backed to a negative route position".to_string());
    }
    let wrongway = rig.transcript().into_iter().any(|line| {
        let lower = line.to_lowercase();
        lower.contains("wrong") || lower.contains("backward") || lower.contains("back the way")
    });
    if backed_mi >= 0.5 && !wrongway {
        findings.push(format!(
            "backed {backed_mi:.1} miles down the interstate (to route mile {:.2}) with no \
             wrong-way or off-route feedback of any kind after the reverse beep started -- a \
             blind player has no way to know the trip is unwinding",
            rig.drive.trip.position_mi
        ));
    }
    if hos_of(&rig.app.ctx).driving_min <= 0.0 {
        findings.push("reversing at 9 mph never counted as HOS driving time".to_string());
    }
    let note = format!(
        "clamped at mile {:.2}, reverse capped {max_reverse_mph:.1} mph",
        rig.drive.trip.position_mi
    );
    outcome("reverse_down_the_route", &rig, findings, &note)
}

pub fn dynamite_parking_brake_at_60() -> Outcome {
    let mut rig = Rig::new(RigOptions::default());
    let mut findings: Vec<String> = Vec::new();
    rig.drive.trip.position_mi = 12.0;
    rig.prepare(60.0, None);
    rig.run_frames(30);
    let wear_before = rig.drive.truck().tire_wear_pct;
    let speed = rig.drive.truck().speed_mph();
    rig.drive.toggle_parking_brake(&mut rig.app.ctx);
    rig.app.ctx.run_deferred();
    if rig.said("dynamited") == 0 {
        findings
            .push("no spoken dynamiting consequence for a parking brake pull at 60".to_string());
    }
    let expected = speed * FLAT_SPOT_WEAR_PCT_PER_MPH;
    let delta = rig.drive.truck().tire_wear_pct - wear_before;
    if (delta - expected).abs() > 0.3 {
        findings.push(format!(
            "flat-spot wear {delta:.2}% does not match the model ({expected:.2}%)"
        ));
    }
    if rig.drive.trip.waiting {
        findings.push("waiting fast-forward armed by a parking brake pulled at speed".to_string());
    }
    rig.step(
        1200,
        DT,
        Some(&|rig: &Rig| rig.drive.truck().speed_mph() < 0.5),
    );
    if rig.drive.truck().speed_mph() >= 0.5 {
        findings.push("spring brakes never brought the truck to a stop".to_string());
    }
    if rig.drive.trip.waiting {
        findings.push("waiting fast-forward armed itself after the dynamited stop".to_string());
    }
    let scale = rig.drive.trip.effective_time_scale();
    if scale > rig.drive.trip.time_scale {
        findings.push(format!(
            "parked clock is running at {scale:.0}x without deliberate waiting"
        ));
    }
    rig.hold(Key::Up);
    rig.run_frames(90);
    rig.release(Key::Up);
    if rig.said("Parking brake set") == 0 {
        findings
            .push("throttle against the set parking brake drew no spoken lockout cue".to_string());
    }
    let note =
        format!("flat-spotted {delta:.1}% tread, stopped, no fast-forward, lockout cue spoken");
    outcome("dynamite_parking_brake_at_60", &rig, findings, &note)
}
