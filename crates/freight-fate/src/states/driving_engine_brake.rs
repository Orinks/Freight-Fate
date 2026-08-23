//! No-engine-brake zones: town noise ordinances around route cities (port of
//! `freight_fate/states/driving_engine_brake.py`, the `EngineBrakeZoneMixin`).
//!
//! Engine brakes are legal under federal and state law; what exists in the
//! real world is hundreds of municipal noise ordinances, posted NO ENGINE
//! BRAKE at the city limits, with exemptions for emergencies -- and the
//! legitimate use of the retarder, holding a heavy truck back on a real
//! downgrade, stays legal everywhere. Fines run roughly 100 to 500 dollars and
//! escalate for repeat offenders (LegalClarity municipal-ordinance survey,
//! 2026; e.g. Snyder, Texas ordinance 1043). The game maps those ordinances
//! onto the same urban radius that already lowers the speed limit near a route
//! city.
//!
//! A blind player cannot see the sign, so the spoken cue is the sign: the zone
//! announces itself ahead when the retarder is on, a violation warns with a
//! grace window before any money moves, and the citation names the amount and
//! the reason.

use ff_core::pyfmt::fmt_grouped;
use ff_core::speech_pacing::SpeechCategory;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

/// How far out the spoken NO ENGINE BRAKE sign reads when the retarder is on.
pub const JAKE_ZONE_WARN_MI: f64 = 2.0;
/// Real seconds between the violation warning and the citation -- time to hear
/// the warning and reach the switch, mirroring the hazard reaction windows.
pub const JAKE_ZONE_GRACE_S: f64 = 10.0;
/// Municipal-ordinance range, escalating per citation and capped at the top.
pub const JAKE_ZONE_FINES: [f64; 3] = [150.0, 300.0, 500.0];
/// A descent a driver genuinely needs the retarder for is exempt everywhere.
/// Matches GRADE_WARN_CLEAR_PCT: under this, the G key calls the road level,
/// so the exemption and the spoken grade readout agree.
pub const JAKE_ZONE_EXEMPT_GRADE_PCT: f64 = 2.0;
/// Below this the retarder is not barking at road speed; a truck creeping a
/// gate queue or parked with the switch on is not what the ordinance is for.
pub const JAKE_ZONE_MIN_MPH: f64 = 10.0;

impl DrivingState {
    /// Warn, then fine, for engine braking inside a town's ban zone.
    pub fn update_engine_brake_zone(&mut self, ctx: &mut GameContext, dt: f64) {
        if self.ramp_mi.is_some() || self.trip.finished || self.pull_over.is_some() {
            return;
        }
        let city = self.trip.engine_brake_ban_at(self.trip.position_mi);
        match &city {
            Some(city) => {
                // A real driver flips engine-brake mode off at the town line;
                // the assists do the same before any driver-fault question is
                // asked.
                let city = city.clone();
                self.release_assist_jake_in_zone(ctx, &city);
            }
            None => self.assist_zone_cue_key = None,
        }
        // The switch alone is not the offense; the bark is. The vehicle already
        // knows whether the retarder is genuinely retarding (stage selected,
        // engine on, off the fuel, in gear), so ask it rather than re-deriving.
        let barking = self.trip.truck.jake_retard_torque_nm() > 0.0
            && self.trip.truck.speed_mph() >= JAKE_ZONE_MIN_MPH;
        // Cruise and the curve assist raise the retarder themselves and release
        // it themselves -- and inside a zone they have just released it above,
        // so an assist bark never reaches the fine path. Auto mode on an AMT is
        // different: the driver armed the stalk with J, so its bark is theirs.
        let driver_owns_jake = barking && self.cruise_jake_stage == 0 && !self.curve_assist_jake;
        let Some(city) = city else {
            self.jake_violation_deadline_s = None;
            self.jake_citation_latched = false;
            self.maybe_warn_jake_zone_ahead(ctx, driver_owns_jake);
            return;
        };
        if !driver_owns_jake || self.jake_zone_exempt() {
            self.jake_violation_deadline_s = None;
            if !self.trip.truck.engine_brake() {
                // The engagement is over; a fresh one can earn a fresh citation.
                self.jake_citation_latched = false;
            }
            return;
        }
        if self.jake_citation_latched {
            return; // one citation per continuous engagement
        }
        if self.jake_violation_deadline_s.is_none() {
            if self.jake_zone_grace_used.contains(&city) {
                // The grace window is one chance to comply, not a renewable
                // exemption. Flicking the switch off just before the timer
                // expires and straight back on used to draw warnings forever
                // and never a fine; coming back on the jake in the same town
                // is now an immediate citation.
                self.jake_citation_latched = true;
                self.fine_engine_braking(ctx, &city);
                return;
            }
            self.jake_zone_grace_used.insert(city.clone());
            self.jake_violation_deadline_s = Some(JAKE_ZONE_GRACE_S);
            self.speak_jake_zone_warning(ctx, &city);
            return;
        }
        let remaining = self.jake_violation_deadline_s.unwrap_or(0.0) - dt;
        self.jake_violation_deadline_s = Some(remaining);
        if remaining <= 0.0 {
            self.jake_violation_deadline_s = None;
            self.jake_citation_latched = true;
            self.fine_engine_braking(ctx, &city);
        }
    }

    /// May cruise or the curve assist raise the retarder here?
    ///
    /// Not inside a town's ban zone -- the assists respect the posted sign the
    /// way a driver flips engine-brake mode off in town -- except where the
    /// ordinance's own carve-outs apply: a real downgrade or an emergency,
    /// where the retarder is the safe tool everywhere.
    pub fn assist_jake_allowed(&mut self, _ctx: &mut GameContext) -> bool {
        if self
            .trip
            .engine_brake_ban_at(self.trip.position_mi)
            .is_none()
        {
            return true;
        }
        self.jake_zone_exempt()
    }

    /// Is the road under the truck a real downgrade?
    ///
    /// The one question that decides whether an assist may reach for the
    /// retarder at all. Holding a loaded truck back on a grade is sustained
    /// speed control, which is what the engine brake is built for and the one
    /// use every noise ordinance leaves legal. Slowing to a target speed --
    /// for a bend, a ramp, a lower posted limit, a lead vehicle -- is the
    /// service brakes' job, because only the drums give the precise control
    /// that needs, and a retarder drives the tractor's rear wheels alone.
    ///
    /// `JAKE_ZONE_EXEMPT_GRADE_PCT` is the same line the ordinance carve-out
    /// and the spoken G readout already draw between level road and a grade,
    /// so a driver hearing "level" never hears a retarder answering a grade.
    pub fn on_downgrade(&self) -> bool {
        self.trip.grade_at(self.trip.position_mi) * 100.0 <= -JAKE_ZONE_EXEMPT_GRADE_PCT
    }

    /// Drop an assist-raised retarder at the town line.
    ///
    /// Runs every frame inside a zone; releasing is idempotent and the raise
    /// gates keep the assists from reaching for it again. Spoken once per
    /// zone, only when a retarder audibly stops -- the note cutting out with
    /// no explanation is the confusing part -- and never in terse speech,
    /// which skips advisory-class cues (no money is at risk here).
    pub fn release_assist_jake_in_zone(&mut self, ctx: &mut GameContext, city: &str) {
        let cruise_owns = self.cruise_jake_stage > 0;
        if (!cruise_owns && !self.curve_assist_jake) || !self.trip.truck.engine_brake() {
            return;
        }
        if self.jake_zone_exempt() {
            return; // a real downgrade or emergency: safety wins in town too
        }
        self.trip.truck.engine_brake_stage = 0;
        if cruise_owns {
            self.cruise_jake_stage = 0;
        }
        self.curve_assist_jake = false;
        if self.assist_zone_cue_key.as_deref() == Some(city) || self.terse_speech(ctx) {
            return;
        }
        self.assist_zone_cue_key = Some(city.to_string());
        let spoken = ctx.world.spoken_city(city, Some(false));
        let message = if cruise_owns {
            format!(
                "No engine brake zone in {spoken}. Cruise is holding the engine brake off and \
                 using the brakes."
            )
        } else {
            format!(
                "No engine brake zone in {spoken}. The curve assist is using the brakes instead \
                 of the engine brake."
            )
        };
        ctx.audio.play_with("ui/notify", 0.6, 0.0);
        // ROUTE, not the ambient default: an assist silently switching how it
        // is braking is a consequence, not colour, same class as the
        // adaptive-cruise easing line (automation-handoff sweep, 2026-08-20,
        // the deferred 2026-08-15 audit).
        ctx.say_event_with(
            message,
            SayEvent::queued()
                .priority(EventPriority::Route)
                .category(SpeechCategory::Confirmation),
        );
    }

    /// The ordinance's own carve-outs: emergencies and real downgrades.
    pub fn jake_zone_exempt(&self) -> bool {
        // A live hazard warning or the emergency brake is the game's "avoiding
        // imminent danger" -- every well-drafted ordinance excuses that.
        if self.trip.truck.emergency_brake || self.hazard_deadline.is_some() {
            return true;
        }
        self.on_downgrade()
    }

    /// Read the NO ENGINE BRAKE sign out loud while it still helps.
    ///
    /// Only when the driver's own retarder is on: with it off there is nothing
    /// to do, and every route city would otherwise add a callout on top of the
    /// urban limit changes already announced there. Terse speech skips the
    /// advisory -- the in-zone warning still comes before any fine, so a terse
    /// driver risks nothing but a later cue.
    pub fn maybe_warn_jake_zone_ahead(&mut self, ctx: &mut GameContext, driver_owns_jake: bool) {
        if !driver_owns_jake || self.terse_speech(ctx) {
            return;
        }
        let Some((start_mi, city)) = self.trip.next_engine_brake_ban(JAKE_ZONE_WARN_MI) else {
            return;
        };
        let key = format!("{start_mi:.1}");
        if self.jake_zone_warned_key.as_deref() == Some(key.as_str()) {
            return;
        }
        self.jake_zone_warned_key = Some(key);
        let distance = ctx
            .settings
            .distance_text(start_mi - self.trip.position_mi, false);
        let spoken = ctx.world.spoken_city(&city, Some(false));
        ctx.audio.play_with("ui/notify", 0.6, 0.0);
        ctx.say_event_with(
            format!(
                "No engine brake zone in {distance}, coming into {spoken}. Switch the engine \
                 brake off before the zone."
            ),
            SayEvent::queued()
                .priority(EventPriority::Route)
                .category(SpeechCategory::Navigation),
        );
    }

    /// The warning that always precedes the first fine -- the audio sign.
    pub fn speak_jake_zone_warning(&mut self, ctx: &mut GameContext, city: &str) {
        ctx.audio.play("ui/warning");
        ctx.controller.rumble.alert();
        let message = if self.terse_speech(ctx) {
            "No engine brake zone. Switch it off.".to_string()
        } else {
            let spoken = ctx.world.spoken_city(city, Some(false));
            let hint = ctx.control_hint("engine_brake");
            format!(
                "No engine brakes in {spoken}; local noise rules. Switch the engine brake off \
                 with {hint} or you will be fined."
            )
        };
        ctx.say_event_with(
            message,
            SayEvent::new().category(SpeechCategory::Navigation),
        );
    }

    /// The citation: paid on the spot, escalating like repeat offenses do.
    pub fn fine_engine_braking(&mut self, ctx: &mut GameContext, city: &str) {
        let index = (self.jake_zone_fines.max(0) as usize).min(JAKE_ZONE_FINES.len() - 1);
        let fine = JAKE_ZONE_FINES[index];
        self.jake_zone_fines += 1;
        self.jake_fines_paid += fine;
        {
            let profile = profile_mut_of(ctx);
            profile.money -= fine; // can go negative; never a game over
                                   // A municipal noise ordinance is not an FMCSA serious violation,
                                   // so it never moves the suspension ladder -- but it is still a
                                   // citation on the record, and the next citation of any kind costs
                                   // more for it.
            profile.driving_record.record_citation(fine);
        }
        ctx.audio.play("ui/error");
        ctx.controller.rumble.alert();
        let message = if self.terse_speech(ctx) {
            format!("Engine brake citation: {} dollars.", fmt_grouped(fine, 0))
        } else {
            let spoken = ctx.world.spoken_city(city, Some(false));
            format!(
                "A local officer cites you for engine braking in {spoken}: a {} dollar fine under \
                 the town noise rules, paid on the spot.",
                fmt_grouped(fine, 0)
            )
        };
        ctx.say_event_with(message, SayEvent::new().category(SpeechCategory::Money));
    }
}
