//! Damage bands while driving: reduced power, limp mode, and out of service
//! (port of `freight_fate/states/driving_damage.py`, the `DamageBandMixin`).
//!
//! Damage used to be a number that cost money at the garage and shaved a
//! little power off a curve. A truck at 99 percent drove very nearly like a
//! healthy one, which is the wrong lesson twice over: an electronic engine
//! meets a serious fault with a staged inducement, and a truck past a certain
//! state of repair is not merely slow -- under the CVSA out-of-service
//! criteria it is an imminent hazard and is legally prohibited from operating
//! at all.
//!
//! So the ladder has four rungs, and the last one is a wall:
//!
//! * **reduced power** -- the engine holds back and burns more for the work.
//! * **limp mode** -- that, plus a road-speed cap the driver cannot drive out
//!   of.
//! * **the last call** -- an advisory that names the number which stops the
//!   truck.
//! * **out of service** -- the truck may not be driven. It may still crawl
//!   clear of a live lane, because leaving a stricken truck stopped in traffic
//!   is the more dangerous rule, but the run does not continue under its own
//!   power.
//!
//! The bands and every physical consequence live in `sim/vehicle`
//! (`damage_band`, `damage_derate_factor`, `speed_cap_mph`, `out_of_service`)
//! so the model layer stays the single source of truth and nothing here is
//! spoken flavour over unchanged physics. This module is the game layer around
//! them: what the driver hears at each edge, how the cap winds in, and what
//! recovery costs.
//!
//! Three rules shape the spoken side, all of them existing house rules:
//!
//! * **Speak first, then bite.** Crossing a band announces the cap and opens
//!   it at the speed the truck already has, then winds it down at about 2 mph
//!   per second -- the same comfortable-braking figure the dropped-speed-limit
//!   grace uses. A cap that snapped would take the road away mid-sentence.
//! * **Both edges, both verbosities.** Every band speaks once when it begins
//!   and again when a repair drops back out of it, terse included. Without the
//!   downward edge a player cannot tell whether a repair cleared limp mode.
//! * **Band before number.** A warning leads with the band; a status readout
//!   gives both, so the number and its meaning never travel separately.
//!
//! Recovery copies the out-of-fuel roadside rescue: not offered, not
//! refusable, real money and real game time. Who pays is where the two
//! business statuses part company, and they part sharply -- see
//! [`DrivingState::recover_out_of_service`].

use ff_core::achievements::increment_stat;
use ff_core::models::business::player_pays_operating_costs;
use ff_core::models::cargo_condition::{
    cargo_condition_text, cargo_outcome, CARGO_CLAIM_PCT, CARGO_EXCEPTION_PCT, CARGO_REJECT_PCT,
};
use ff_core::models::carrier_fleet::{slip_seat_pool, slip_seats};
use ff_core::models::trucks::truck_model;
use ff_core::pyfmt::fmt_grouped;
use ff_core::settings::Settings;
use ff_core::sim::trip_models::FACILITY_GATE_ZONE_MI;
use ff_core::sim::vehicle::TruckState;
use ff_core::speech_pacing::SpeechCategory;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

/// The condition rungs, in the order a load passes them, for the in-drive cue.
pub const CARGO_CUE_STEPS: [f64; 3] = [CARGO_EXCEPTION_PCT, CARGO_CLAIM_PCT, CARGO_REJECT_PCT];

/// The spoken band a damage number puts the truck in, or "" for none.
///
/// Used by every readout that shows a damage figure, so "78 percent" is never
/// heard without "limp mode" beside it.
pub fn damage_band_clause(settings: &Settings, truck: &TruckState) -> String {
    let band = truck.damage_band();
    if band == DAMAGE_BAND_OUT_OF_SERVICE {
        return "out of service".to_string();
    }
    if band == DAMAGE_BAND_LIMP || band == DAMAGE_BAND_LAST_CALL {
        return format!(
            "limp mode, capped at {}",
            settings.speed_text(DAMAGE_LIMP_CAP_MPH)
        );
    }
    if band == DAMAGE_BAND_REDUCED {
        return "reduced power".to_string();
    }
    String::new()
}

/// The delivery summary's damage sentence, or None when nothing to say.
pub fn damage_summary_line(
    settings: &Settings,
    truck: &TruckState,
    trip_damage: f64,
) -> Option<String> {
    if trip_damage <= 1.0 {
        return None;
    }
    let clause = damage_band_clause(settings, truck);
    if clause.is_empty() {
        return Some(format!(
            "The cargo run added {trip_damage:.0} percent truck damage. Visit the garage when you \
             can."
        ));
    }
    Some(format!(
        "The cargo run added {trip_damage:.0} percent truck damage. The truck is at {:.0} \
         percent, {clause}. Repair it before the next run.",
        truck.damage_pct
    ))
}

/// The carrier's bill for a run it will rule preventable.
///
/// Returns `(deductible, reputation_hit, spoken_reason)`. A real carrier files
/// an incident report and a safety committee rules the damage preventable or
/// not; the preventable ones run progressive discipline and very often a
/// deductible or a voided safety bonus. That is how a company driver feels
/// damage in the wallet without being handed a repair invoice that is not
/// theirs to pay -- the asymmetry the whole system rests on.
///
/// Both numbers scale with the deepest band the run reached rather than the
/// damage number at the gate, so patching the truck on the shoulder does not
/// launder the run.
pub fn preventable_damage_charge(driving: &DrivingState) -> (f64, f64, String) {
    let preventable = driving.trip.truck.preventable_damage_pct;
    let bands = driving.worst_damage_band;
    if bands <= DAMAGE_BAND_NONE || preventable < 1.0 {
        return (0.0, 0.0, String::new());
    }
    // The share of the run's damage the committee would call preventable,
    // against the depth it reached. Damage taken reacting correctly to a
    // modelled hazard is not counted in `preventable_damage_pct` at all.
    let share = 1.0f64.min(preventable / 1.0f64.max(DAMAGE_OUT_OF_SERVICE_PCT));
    let deductible = PREVENTABLE_DAMAGE_DEDUCTIBLE * bands as f64 * share;
    let reputation = PREVENTABLE_REPUTATION_PER_BAND * bands as f64;
    let reason = if bands == DAMAGE_BAND_REDUCED {
        "the truck came back in reduced power"
    } else if bands == DAMAGE_BAND_LIMP {
        "the run finished in limp mode"
    } else if bands == DAMAGE_BAND_LAST_CALL {
        "the truck was within a hair of out of service"
    } else {
        "the truck went out of service on the road"
    };
    (deductible, reputation, reason.to_string())
}

/// The load's condition for a status readout: the words and the number.
pub fn cargo_status_clause(truck: &TruckState) -> String {
    let condition = truck.cargo_damage_pct;
    // A tank load gets the tank vocabulary. Diesel does not "shift but sound".
    let liquid = truck.liquid.is_some();
    if condition < 1.0 {
        return if liquid { "settled" } else { "secure" }.to_string();
    }
    format!(
        "{}, {condition:.0} percent",
        cargo_condition_text(condition, liquid)
    )
}

impl DrivingState {
    // -- cargo condition -----------------------------------------------------

    /// Feed the bend to the freight, then say when it has cost something.
    ///
    /// The vehicle model has no map, so the road hands it the one thing it
    /// cannot know: how far past the posted advisory this bend is being taken.
    /// And a load that quietly degrades until the dock refuses it would be the
    /// worst kind of surprise for a player who cannot see the trailer -- so
    /// each rung speaks once, when it is crossed.
    pub fn update_cargo_condition(&mut self, ctx: &mut GameContext, _dt: f64) {
        let curve = self.trip.curve_at(self.trip.position_mi);
        let bend = curve.filter(|curve| !curve.connector);
        let speed_mph = self.trip.truck.speed_mph();
        let t = &mut self.trip.truck;
        t.corner_overspeed_mph = match &bend {
            Some(bend) => (speed_mph - bend.advisory_mph as f64).max(0.0),
            None => 0.0,
        };
        // The advisory itself as well as the excess: a liquid load needs the
        // ratio, because what a bend pulls sideways goes with the square of
        // how far over the posting it is being taken.
        t.corner_advisory_mph = bend.as_ref().map_or(0.0, |b| b.advisory_mph as f64);
        // And the geometry, for dry freight: a pallet is moved by the sideways
        // pull, which comes from the radius rather than from the sign.
        t.corner_radius_ft = bend.as_ref().map_or(0.0, |b| b.min_radius_ft as f64);
        let condition = t.cargo_damage_pct;
        // The HIGHEST rung crossed, not the next one up. A collision can put a
        // load through all three at once, and walking them a frame apart would
        // fire three interrupting warnings inside a tenth of a second; the
        // driver needs the state they are actually in, said once.
        let crossed: Vec<f64> = CARGO_CUE_STEPS
            .iter()
            .copied()
            .filter(|step| condition >= *step && *step > self.cargo_cue_at)
            .collect();
        if let Some(last) = crossed.last() {
            self.cargo_cue_at = *last;
            self.announce_cargo_condition(ctx);
        }
    }

    pub fn announce_cargo_condition(&mut self, ctx: &mut GameContext) {
        let cargo_damage_pct = self.trip.truck.cargo_damage_pct;
        let liquid = self.trip.truck.liquid.is_some();
        let outcome = cargo_outcome(cargo_damage_pct);
        let words = cargo_condition_text(cargo_damage_pct, liquid);
        ctx.audio.play("ui/warning");
        let message = if self.terse_speech(ctx) {
            let consequence = match outcome {
                "exception" => "Exception on the bill.",
                "claim" => "Claim likely.",
                _ => "The dock will refuse it.",
            };
            format!("Load {words}, {cargo_damage_pct:.0} percent. {consequence}")
        } else {
            let consequence = match outcome {
                "exception" => {
                    "The receiver will note an exception on the bill of lading and hold back part \
                     of the pay."
                }
                "claim" => {
                    "Claim territory now. The receiver will take it, and the carrier pays for \
                     what you broke."
                }
                _ => "The dock will refuse a load in this state.",
            };
            // The coaching tail teaches the driver how to save what is left;
            // once taught it is not news, so it rides the first report of the
            // episode and every escalation after speaks only the new number
            // and the consequence (research doc R11).
            let tail = if self.cargo_coaching_said {
                ""
            } else {
                " Brake and corner gently from here."
            };
            format!(
                "The load has shifted hard and is {words}, {cargo_damage_pct:.0} percent. \
                 {consequence}{tail}"
            )
        };
        self.cargo_coaching_said = true;
        // The load's condition is a state of the trailer, not a moment on the
        // road: it earns the voice when it starts and again when the number it
        // carries has moved. Otherwise the driver hears the same sentence for
        // the rest of the run and has to sit through it every time.
        //
        // The coaching tail only ever rides the first report -- every message
        // this sends, including that first one, carries the pay consequence
        // (an exception, a claim, a refused load), and the category governs
        // the whole line, not just the tail. MONEY, not COACHING.
        ctx.say_event_with(
            message,
            SayEvent::new()
                .key("cargo_condition")
                .category(SpeechCategory::Money),
        );
    }

    // -- the bands -----------------------------------------------------------

    pub fn damage_band_clause(&self, ctx: &GameContext) -> String {
        damage_band_clause(&ctx.settings, &self.trip.truck)
    }

    /// Announce band edges, hold the cap, and run recovery at the wall.
    pub fn update_damage_bands(&mut self, ctx: &mut GameContext, dt: f64) {
        let band = self.trip.truck.damage_band();
        // Settlement grades the run, not the moment it ended: a driver who
        // spent an hour in limp mode and then paid for a patch did something
        // to get there, and a clean arrival number would hide it.
        self.worst_damage_band = self.worst_damage_band.max(band);
        if band != self.damage_band {
            let previous = self.damage_band;
            self.damage_band = band;
            self.announce_damage_band(ctx, band, previous);
            if band == DAMAGE_BAND_OUT_OF_SERVICE {
                self.out_of_service_creep_s = 0.0;
            }
        }
        self.update_damage_cap(dt);
        if self.trip.truck.out_of_service() {
            // A window to get clear of a live lane, then road service arrives
            // whether or not the driver used it. Coming to a stop ends the
            // wait at once: a driver who has pulled over should not sit there
            // listening to nothing happen.
            self.out_of_service_creep_s += dt;
            if self.trip.truck.speed_mph() <= 1.0
                || self.out_of_service_creep_s >= OUT_OF_SERVICE_RECOVERY_GRACE_S
            {
                self.recover_out_of_service(ctx);
            }
        }
    }

    pub fn announce_damage_band(&mut self, ctx: &mut GameContext, band: i32, previous: i32) {
        let terse = self.terse_speech(ctx);
        let damage = self.trip.truck.damage_pct;
        let cap = ctx.settings.speed_text(DAMAGE_LIMP_CAP_MPH);
        // Every band here is a vehicle-condition readout (the redline/low-air
        // pattern) except the wall itself: out of service governs the truck
        // down to a creep and orders a stop right now, which is an act-now
        // cue, not a status readout. That one branch alone earns SAFETY.
        let mut category = SpeechCategory::Status;
        let message;
        if band > previous {
            if band == DAMAGE_BAND_REDUCED {
                message = if terse {
                    format!("Reduced power. Damage {damage:.0} percent.")
                } else {
                    format!(
                        "Reduced power. Damage is past {DAMAGE_DERATE_PCT:.0} percent; the engine \
                         is holding back and burning more fuel."
                    )
                };
            } else if band == DAMAGE_BAND_LIMP {
                message = if terse {
                    format!("Limp mode. Capped at {cap}.")
                } else {
                    format!(
                        "Limp mode. Damage is past {DAMAGE_LIMP_PCT:.0} percent; the engine is \
                         winding down to a {cap} cap."
                    )
                };
            } else if band == DAMAGE_BAND_LAST_CALL {
                // The advisory that must name the wall. A player who is
                // surprised by the truck stopping was not warned properly.
                message = if terse {
                    format!(
                        "Damage {damage:.0} percent. Out of service at \
                         {DAMAGE_OUT_OF_SERVICE_PCT:.0}."
                    )
                } else {
                    format!(
                        "Damage is past {DAMAGE_LAST_CALL_PCT:.0} percent. At \
                         {DAMAGE_OUT_OF_SERVICE_PCT:.0} percent the truck goes out of service and \
                         cannot be driven at all."
                    )
                };
            } else {
                message = self.out_of_service_message(ctx);
                category = SpeechCategory::Safety;
            }
            ctx.audio.play("ui/warning");
        } else {
            // Coming back down after a repair. Terse keeps the fact and drops
            // only the prose around it -- a driver who cannot hear that limp
            // mode cleared has no way to know the repair worked.
            if band == DAMAGE_BAND_NONE {
                message = if terse {
                    format!("Damage {damage:.0} percent. Full power.")
                } else {
                    format!("Repair complete. Damage {damage:.0} percent; full power restored.")
                };
            } else if band == DAMAGE_BAND_REDUCED {
                message = if terse {
                    format!("Reduced power. Damage {damage:.0} percent.")
                } else {
                    format!(
                        "Damage {damage:.0} percent. Limp mode is off; the truck is still in \
                         reduced power."
                    )
                };
            } else {
                message = if terse {
                    format!("Limp mode. Capped at {cap}.")
                } else {
                    format!("Damage {damage:.0} percent. Still in limp mode, capped at {cap}.")
                };
            }
            ctx.audio.play("ui/notify");
        }
        ctx.say_event_with(message, SayEvent::new().category(category));
    }

    /// The wall landing: the fact, the cost, and the path forward.
    ///
    /// Never an unexplained inability to move. The driver is told what has
    /// happened, what it will take, and what to do in the meantime, in that
    /// order, in both verbosities.
    pub fn out_of_service_message(&self, ctx: &GameContext) -> String {
        let creep = ctx.settings.speed_text(DAMAGE_CREEP_CAP_MPH);
        if self.terse_speech(ctx) {
            return format!(
                "Out of service. Damage {:.0} percent. {creep} to clear the lane, then brake to a \
                 stop. Road service is coming: {}.",
                self.trip.truck.damage_pct,
                self.recovery_cost_text(ctx)
            );
        }
        format!(
            "Out of service. Damage is past {DAMAGE_OUT_OF_SERVICE_PCT:.0} percent; the truck may \
             not be driven. {creep} to clear the lane, then stop on the shoulder for road \
             service. {}.",
            self.recovery_cost_text(ctx)
        )
    }

    /// What getting moving again will cost, said before it is charged.
    pub fn recovery_cost_text(&self, ctx: &GameContext) -> String {
        if player_pays_operating_costs(&profile_of(ctx).business_status) {
            let cost = self.roadside_repair_cost();
            return format!(
                "The repair will cost about {} dollars and most of {:.0} hours",
                fmt_grouped(cost, 0),
                BREAKDOWN_REPAIR_MIN / 60.0
            );
        }
        format!(
            "The carrier covers the bill, but dispatch grounds the tractor and the wait runs \
             about {:.0} hours",
            GROUNDED_SWAP_MIN / 60.0
        )
    }

    pub fn roadside_repair_cost(&self) -> f64 {
        road_repair_cost(
            self.trip.truck.damage_pct,
            BREAKDOWN_REPAIR_DAMAGE_PCT,
            BREAKDOWN_CALLOUT_FEE,
        )
    }

    // -- the speed cap -------------------------------------------------------

    /// What the road-speed governor is winding toward, or None for free.
    pub fn damage_cap_target(&self) -> Option<f64> {
        let t = &self.trip.truck;
        if t.out_of_service() {
            return Some(DAMAGE_CREEP_CAP_MPH);
        }
        if t.damage_pct >= DAMAGE_LIMP_PCT {
            return Some(DAMAGE_LIMP_CAP_MPH);
        }
        None
    }

    /// Flows that are already braking own the speed; the cap stays out.
    ///
    /// An enforcement pull-over and the facility gate zone both have their own
    /// braking curve and their own spoken contract. Laying a second, winding
    /// cap over either would fight a stop that is already happening.
    pub fn limp_cap_suspended(&self) -> bool {
        if self.pull_over.is_some() {
            return true;
        }
        if self.phase == DRIVE_PHASE_DELIVERY && self.destination_exit_taken {
            let remaining = self.trip.total_miles() - self.trip.position_mi;
            return remaining <= FACILITY_GATE_ZONE_MI;
        }
        false
    }

    pub fn update_damage_cap(&mut self, dt: f64) {
        let target = self.damage_cap_target();
        let Some(target) = target.filter(|_| !self.limp_cap_suspended()) else {
            self.limp_cap_mph = None;
            self.trip.truck.speed_cap_mph = None;
            return;
        };
        self.limp_cap_mph = Some(match self.limp_cap_mph {
            // Open at the speed the truck already has, never below the target
            // itself: the announcement has just been heard and the wind-down
            // starts from here.
            None => target.max(self.trip.truck.speed_mph()),
            Some(cap) => target.max(cap - LIMP_CAP_RAMP_MPH_PER_S * dt),
        });
        self.trip.truck.speed_cap_mph = self.limp_cap_mph;
    }

    /// Say once per engagement that limp mode, not the grade, owns the target.
    ///
    /// Mirrors the "cruise is flat out and still losing the grade" cue: the
    /// set speed is unreachable for a reason the driver cannot see, so name it
    /// and name what cruise is holding instead.
    pub fn announce_limp_cruise_cap(&mut self, ctx: &mut GameContext) {
        let (Some(cap), Some(target)) = (self.trip.truck.speed_cap_mph, self.cruise_mph) else {
            return;
        };
        if self.limp_cruise_said {
            return;
        }
        if target <= cap + 1.0 || self.trip.truck.speed_mph() < cap - 2.0 {
            return;
        }
        self.limp_cruise_said = true;
        let message = if self.terse_speech(ctx) {
            format!("Limp mode. Holding {}.", ctx.settings.speed_text(cap))
        } else {
            format!(
                "Cruise cannot hold {}; the truck is in limp mode. Holding {}.",
                ctx.settings.speed_text(target),
                ctx.settings.speed_text(cap)
            )
        };
        // ROUTE, not the ambient default: cruise is silently holding a lower
        // speed than the driver set, the same class as the adaptive-cruise
        // easing line -- an assist changing what the truck does is a
        // consequence, not colour (automation-handoff sweep, 2026-08-20, the
        // deferred 2026-08-15 audit).
        ctx.say_event_with(
            message,
            SayEvent::queued()
                .priority(EventPriority::Route)
                .category(SpeechCategory::Status),
        );
    }

    // -- recovery ------------------------------------------------------------

    /// Get an out-of-service truck legal again. Where the statuses part.
    ///
    /// An owner-operator's truck is their property and nobody grounds it for
    /// them -- but nobody pays for it either, and the bill lands whether the
    /// money is there or not. A company driver is the other way round: the
    /// tractor is not theirs to gamble with, so the carrier takes it out of
    /// service and covers the repair, and what the driver spends is the day
    /// and their standing with dispatch. Continuing to run wrecked company
    /// iron is a DOT out-of-service violation the carrier eats, which is
    /// exactly why real carriers do not leave it to the driver.
    pub fn recover_out_of_service(&mut self, ctx: &mut GameContext) {
        if self.recovering || !self.trip.truck.out_of_service() {
            return;
        }
        self.recovering = true;
        if player_pays_operating_costs(&profile_of(ctx).business_status) {
            self.roadside_repair_out_of_pocket(ctx);
        } else {
            self.carrier_grounds_the_tractor(ctx);
        }
        self.recovering = false;
        self.cancel_cruise(ctx, false);
        self.limp_cap_mph = None;
        self.out_of_service_creep_s = 0.0;
        // The recovery line IS the announcement for the band it lands in, so
        // the edge watcher must not speak it a second time.
        self.damage_band = self.trip.truck.damage_band();
    }

    /// Owner-operator: their truck, their bill, and it is not refusable.
    pub fn roadside_repair_out_of_pocket(&mut self, ctx: &mut GameContext) {
        let cost = self.roadside_repair_cost();
        let money = {
            let p = profile_mut_of(ctx);
            p.money -= cost; // can go negative: the truck cannot move otherwise
            p.money
        };
        self.trip
            .truck
            .recover_from_breakdown(BREAKDOWN_REPAIR_DAMAGE_PCT);
        self.trip.game_minutes += BREAKDOWN_REPAIR_MIN;
        hos_mut_of(ctx).on_duty(BREAKDOWN_REPAIR_MIN);
        ctx.audio.play("ui/error");
        let damage_pct = self.trip.truck.damage_pct;
        let message = if self.terse_speech(ctx) {
            format!(
                "Roadside repair, {} dollars. Damage {damage_pct:.0} percent, {}. You have {} \
                 dollars.",
                fmt_grouped(cost, 0),
                self.damage_band_clause(ctx),
                fmt_grouped(money, 0)
            )
        } else {
            format!(
                "Roadside repair got the truck moving for {} dollars; damage is down to \
                 {damage_pct:.0} percent, still in reduced power. It took {:.0} hours and it is \
                 now {}. You have {} dollars. Press {} to restart the engine.",
                fmt_grouped(cost, 0),
                BREAKDOWN_REPAIR_MIN / 60.0,
                clock_text(self.trip.local_hour()),
                fmt_grouped(money, 0),
                ctx.control_hint("engine")
            )
        };
        ctx.say_event_with(message, SayEvent::new().category(SpeechCategory::Money));
    }

    /// Company driver: the carrier takes the truck, and the driver waits.
    ///
    /// No money changes hands. What the driver loses is the hours, a chunk of
    /// standing, and a recorded preventable-equipment event on their record --
    /// the pattern that follows from repeating this belongs to the career and
    /// dispatch-trust layer, which reads the event; nothing here terminates
    /// anybody.
    pub fn carrier_grounds_the_tractor(&mut self, ctx: &mut GameContext) {
        {
            let p = profile_mut_of(ctx);
            p.career.reputation = 0.0f64.max(p.career.reputation - BREAKDOWN_REPUTATION_HIT);
        }
        self.record_equipment_event(ctx);
        let grounded = self.tractor_label(ctx);
        let spare = self.draw_yard_spare(ctx);
        self.trip.game_minutes += GROUNDED_SWAP_MIN;
        hos_mut_of(ctx).on_duty(GROUNDED_SWAP_MIN);
        ctx.audio.play("ui/error");
        let terse = self.terse_speech(ctx);
        let handover = match &spare {
            Some(spare) => {
                if terse {
                    format!("You are in the {spare}")
                } else {
                    format!("Dispatch put you in the {spare} for the rest of this run")
                }
            }
            None => {
                // No spare to draw: the yard sends a road crew instead, and
                // the tractor goes to the shop when the driver gets in.
                self.trip
                    .truck
                    .recover_from_breakdown(BREAKDOWN_REPAIR_DAMAGE_PCT);
                if terse {
                    "Patched to finish the run".to_string()
                } else {
                    "The road crew put it right enough to finish the run, and the shop takes it \
                     when you get in"
                        .to_string()
                }
            }
        };
        let damage_pct = self.trip.truck.damage_pct;
        let message = if terse {
            format!(
                "Grounded. The carrier pays. {handover}. Damage {damage_pct:.0} percent. Dispatch \
                 logged preventable equipment damage."
            )
        } else {
            format!(
                "Dispatch has taken the {grounded} out of service. The carrier covers the bill. \
                 {handover}. That cost {:.0} hours and it is now {}. Damage on the truck you are \
                 in is {damage_pct:.0} percent. Dispatch logged preventable equipment damage \
                 against your record; a pattern of it costs the seat. Press {} to restart the \
                 engine.",
                GROUNDED_SWAP_MIN / 60.0,
                clock_text(self.trip.local_hour()),
                ctx.control_hint("engine")
            )
        };
        ctx.say_event_with(message, SayEvent::new().category(SpeechCategory::Money));
    }

    /// Leave the event on the career for the trust and termination layer.
    ///
    /// Deliberately just a counter and a reputation hit: dispatch-trust
    /// regression and losing the seat are owned elsewhere, and there must not
    /// be two paths to either.
    pub fn record_equipment_event(&mut self, ctx: &mut GameContext) {
        increment_stat(profile_mut_of(ctx), "preventable_equipment_damage");
    }

    pub fn tractor_label(&self, ctx: &GameContext) -> String {
        let key = profile_of(ctx).active_truck_key();
        truck_model(&key)
            .map_or("tractor", |model| model.label)
            .to_string()
    }

    /// Swap a slip-seating driver into another of the yard's spares.
    ///
    /// Reuses the existing slip-seat pool rather than inventing a parallel
    /// one, and the spare is real used equipment carrying its own wear -- the
    /// point of the consequence is that it is plausibly a worse truck than the
    /// one just grounded. Returns the spoken label, or None when there is
    /// nothing to move into: a senior driver holds a dedicated seat that the
    /// assignment layer would hand straight back, and a yard whose every spare
    /// is also unfit has none to give.
    pub fn draw_yard_spare(&mut self, ctx: &mut GameContext) -> Option<String> {
        let p = profile_of(ctx);
        if !slip_seats(p) {
            return None;
        }
        let current = p.active_truck_key();
        let candidates: Vec<&'static str> = slip_seat_pool(p)
            .into_iter()
            .filter(|key| *key != current)
            .collect();
        if candidates.is_empty() {
            return None;
        }
        let damage_of = |ctx: &GameContext, key: &str| -> f64 {
            profile_of(ctx)
                .truck_conditions
                .get(key)
                .and_then(|record| record.get("damage_pct"))
                .and_then(|value| value.as_f64())
                .unwrap_or(0.0)
        };
        let pick = *candidates
            .iter()
            .min_by(|a, b| damage_of(ctx, a).total_cmp(&damage_of(ctx, b)))
            .expect("a non-empty candidate list");
        if damage_of(ctx, pick) >= DAMAGE_OUT_OF_SERVICE_PCT {
            return None; // the yard has nothing fit either
        }
        let cargo_kg = self.trip.truck.cargo_kg;
        let trailer_attached = self.trip.truck.trailer_attached;
        let automatic = self.trip.truck.transmission.automatic;
        let odometer_mi = self.trip.truck.odometer_mi;
        {
            // The grounded tractor keeps its damage.
            let old = self.trip.truck.clone();
            let p = profile_mut_of(ctx);
            p.store_truck_condition(&old);
            p.truck = pick.to_string();
            if p.truck_conditions.get(pick).is_none() {
                p.provision_truck_condition(pick, None);
                p.set_truck_damage_pct(GROUNDED_SPARE_DAMAGE_PCT);
            }
        }
        let specs = profile_of(ctx).truck_specs();
        self.trip.truck = TruckState::new(specs);
        self.trip.truck.cargo_kg = cargo_kg;
        self.trip.truck.trailer_attached = trailer_attached;
        self.trip.truck.transmission.automatic = automatic;
        self.trip.truck.odometer_mi = odometer_mi;
        profile_of(ctx).load_truck_condition(&mut self.trip.truck);
        let damage_pct = self.trip.truck.damage_pct;
        self.trip.truck.recover_from_breakdown(damage_pct);
        self.trip.truck.set_air_ready(true);
        Some(
            truck_model(pick)
                .map_or("yard spare", |model| model.label)
                .to_string(),
        )
    }
}
