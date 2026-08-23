//! Standing physical conditions: hot brakes, the destination approach
//! assist, the traction states, and the chain law.

use ff_core::models::enforcement::CHAIN_LAW_FINE;
use ff_core::pyfmt::fmt_grouped;
use ff_core::pyrandom::PyRandom;
use ff_core::speech_pacing::{EventPriority, SpeechCategory};

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;
use crate::states::driving_stops::arrival_servo_brake;

impl DrivingState {
    /// Squeal when hot brakes are worked past their fade temperature.
    pub fn update_brake_heat_cue(&mut self, ctx: &mut GameContext, dt: f64) {
        if self.brake_squeal_cooldown_s > 0.0 {
            self.brake_squeal_cooldown_s = (self.brake_squeal_cooldown_s - dt).max(0.0);
            return;
        }
        let t = &self.trip.truck;
        if t.brake >= 0.4 && t.speed_mph() > 10.0 && t.brake_temp_c >= t.specs.brake_fade_temp_c {
            ctx.audio.play_with("vehicle/brake_squeal", 0.8, 0.0);
            self.brake_squeal_cooldown_s = 4.0;
        }
    }

    /// Ease the truck down so it ARRIVES stopped, not so it stops on arrival.
    ///
    /// The setting promises "slows and stops at the selected facility
    /// arrival point". Only the stopping half existed: the arrival gate
    /// applies full brake, and it runs inside `if self.trip.finished` --
    /// true only once the truck is AT the point. So the assist could hold a
    /// truck that had already stopped, and nothing more. The owner drove a
    /// delivery to Odessa, braked himself, and the assist announced "stopped
    /// and holding" as though it had done it (2026-08-19: "it did not stop
    /// me. I stopped").
    ///
    /// Priced like the exit assist's ramp glide rather than as a fixed
    /// trigger distance: road speed stands until the truck is inside the
    /// distance it needs to shed, then the cap follows the deceleration
    /// down. A driver already slower than the cap is left alone; this never
    /// steers, and the only speed it ever adds is a walk over the last
    /// lengths to the point, because the dock opens at the point and not a
    /// truck-length short of it.
    pub fn update_destination_approach_assist(&mut self, ctx: &mut GameContext) {
        if !ctx.settings.destination_approach_assist {
            self.destination_arrival_active = false;
            self.destination_assist_brake = 0.0;
            return;
        }
        // HOW FAR TO THE GATE -- which is not the same as how far to the end
        // of the route. trip.remaining_miles measures the route, and it stays
        // parked while the truck is on the ramp: the harness showed it reading
        // 3.200 mi with the truck crawling yards from the market, so the cap
        // came out at 215 mph and the assist waved the truck through. The
        // arrival lives on the ramp instead -- ramp_mi counts down from
        // RAMP_LENGTH_MI to the stop, and the dock opens when it reaches zero
        // at docking speed; anything faster is a blown stop and the driver is
        // told they drove past (owner, three runs, 2026-08-19/20).
        //
        // A same-city street chain to a gate has no ramp, so that route shape
        // still measures off the route, which for it is the same thing.
        //
        // And a ramp that hands off to a street chain is NEITHER: its end is a
        // driving continuation, not the gate, and the chain's own trip carries
        // the arrival a mile further on. Treating it as the gate stopped the
        // truck dead at the bottom of the ramp with the city still to drive
        // (owner, Spokane, 2026-08-22).
        let ramp_is_destination = self
            .ramp_stop
            .as_ref()
            .is_some_and(|stop| stop.stop_type == "delivery_destination");
        let remaining_mi = if self.ramp_mi.is_some()
            && ramp_is_destination
            && !self.destination_street_chain_ahead(ctx)
        {
            self.ramp_mi
        } else if !self.trip.finished && self.trip.is_facility_approach_route() {
            Some(self.trip.remaining_miles())
        } else {
            None
        };
        let Some(remaining_mi) = remaining_mi else {
            self.destination_arrival_active = false;
            return;
        };
        // No margin held back, deliberately. Stopping short is not a safer
        // version of stopping: the dock opens at the END of the ramp, so a
        // truck halted two hundred feet shy of it with the brake held is a
        // truck that never arrives -- which is what a reserve of exactly that
        // size did on the first run after the clock fix. The gentle rate below
        // is the margin.
        let remaining_m = remaining_mi.max(0.0) * 1609.344;
        if remaining_m <= 0.0 {
            // At the point or past it: whatever is still on has to come off.
            if self.trip.truck.speed_mph() > DOCKING_MAX_MPH {
                self.trip.truck.throttle = 0.0;
                self.trip.truck.brake = 1.0;
                if self.cruise_mph.is_some() || self.keeper_mph.is_some() {
                    self.pause_speed_control(ctx, false);
                }
            }
            return;
        }
        // WHEN THE ARRIVAL TAKES THE PEDALS. The trigger is the game's ordinary
        // approach comfort curve with a pedal-build allowance in front of it --
        // the truck spends `lag` seconds at its current speed while the brake
        // comes up, THEN sheds at `a`:
        //
        //     v * lag  +  v^2 / (2a)  =  remaining
        //
        // whose positive root is the fastest it may still be doing and stop in
        // the road it has left. Solved, not approximated: taking the lag off
        // the distance first and then applying sqrt(2 a d) under-triggers,
        // because it prices the lag at the speed AFTER the shed. And priced at
        // the comfort rate, not the firmer rate the servo below will brake at:
        // triggering on the firm rate meant starting at the last metre that
        // could possibly work, and a throttle still decaying ate the margin.
        let a = APPROACH_DECEL_MPS2;
        let lag = APPROACH_ASSIST_REACTION_S;
        let cap_mps = -a * lag + ((a * lag).powi(2) + 2.0 * a * remaining_m).sqrt();
        if !self.destination_arrival_active {
            if self.trip.truck.velocity_mps <= cap_mps {
                return;
            }
            // LATCHED from here to the gate. This used to re-decide every
            // frame against the curve: over it, brake; under it, stand down
            // and hand the pedals back. Standing down is what zeroed the servo
            // and -- until the zone keeper learned to stay paused -- let the
            // keeper wind the truck back up toward the street limit, so the
            // assist chased a hair over the curve the whole way down and the
            // truck crossed the arrival point at 13.8 mph with the driver's
            // foot the only thing that stopped it (owner, Spokane,
            // 2026-08-21; Odessa, 2026-08-19, whose fix covered the ramp).
            // An arrival that has begun does not un-begin.
            self.destination_arrival_active = true;
            self.destination_assist_brake = 0.0;
            // ROUTE, not the ambient default: an automation naming that it
            // has the pedals, the same class as "Route-transition assistance
            // slowing". This assist used to take the brakes WITHOUT A WORD --
            // the only line it owned fired after the truck was already
            // stopped -- which for a blind driver is indistinguishable from
            // an assist that is not working, and is the likeliest reason it
            // was reported three times as "it did not stop me".
            ctx.say_event_with(
                "Destination approach assistance slowing.",
                SayEvent::queued()
                    .priority(EventPriority::Route)
                    .category(SpeechCategory::Confirmation),
            );
        }
        // The arrival owns the pedals: throttle off, and automatic speed
        // control paused the ARRIVAL way -- held until departure, never lifted
        // on its own -- so nothing holds a street limit against the shed.
        self.trip.truck.throttle = 0.0;
        if self.cruise_mph.is_some() || self.keeper_mph.is_some() {
            self.pause_speed_control(ctx, false);
        }
        // HOW HARD. The stop profile itself, from the moment the arrival
        // begins, recomputed each tick and mapped onto the pedal by
        // `arrival_servo_brake` -- which, unlike the ramp assist's servo,
        // has no floor, because a gate is not a bar. Floored at the ramp's
        // start rate the arrival waited until the road needed 0.6 m/s2, about
        // 35 metres out at street speed, then chased a demand that climbs
        // faster than the pedal follows and crossed the gate at 12 mph with
        // the brake at full.
        //
        // The profile aims at a WALK at the point, not at rest, and it asks
        // the brake only for the share of that the road is not already
        // taking. A profile to zero speed is exact for a truck whose only
        // retarder is the brake; the real one has rolling resistance, drag
        // and grade shedding speed underneath it, and the servo holds the
        // pedal a band above the demand, so the truck always came down
        // harder than the profile -- and an arrival that undershoots does
        // not self-correct: the demand falls as the square of the speed while
        // the road left falls linearly, so it converges on a stop SHORT of
        // the point, with the brake held and the throttle forced to zero.
        // Nine metres short at two hundredths of a mile an hour, the dock
        // never opening, is what Jerry's Hobbs arrival looked like
        // (2026-08-22); the bench found the street chain does the same thing
        // on an upgrade. The dock opens only AT the point, so the last
        // lengths are a creep the assist holds, throttle against the road if
        // it has to, until the point's own full-brake branch above stops it.
        let v = self.trip.truck.velocity_mps;
        let creep = ARRIVAL_CREEP_MPH / 2.23694;
        // What the road takes off on its own, m/s2: positive when it slows
        // the truck, negative when gravity is pushing it down to the gate.
        let road = self.trip.truck.resistance_force() / self.trip.truck.gross_mass_kg();
        let needed = 0.0f64.max(v * v - creep * creep) / (2.0 * remaining_m);
        if v > creep {
            self.destination_assist_brake = arrival_servo_brake(
                self.destination_assist_brake,
                needed - road,
                &self.trip.truck,
            );
            self.trip.truck.brake = self.trip.truck.brake.max(self.destination_assist_brake);
            return;
        }
        // At the walk, short of the point: the brake is off and the throttle
        // holds the pace -- the road's balancing pedal plus a nudge for the
        // shortfall, capped so it is a creep and never a launch. Nothing is
        // added while anyone else has a foot on the brake: a driver braking
        // at the gate, the hazard assist, a stop ahead all win.
        self.destination_assist_brake = 0.0;
        if self.trip.truck.brake > 0.0 || self.trip.truck.parking_brake {
            return;
        }
        let pedal = self.trip.truck.hold_throttle() + ARRIVAL_CREEP_THROTTLE_GAIN * (creep - v);
        self.trip.truck.throttle = self
            .trip
            .truck
            .throttle
            .max(ARRIVAL_CREEP_THROTTLE_MAX.min(pedal.max(0.0)));
    }

    /// Speak the physical traction states once, on the edge they begin.
    ///
    /// Each warning names the state and the action that clears it: ease off
    /// the speed when the tires float, ease off the jake when the drive
    /// wheels slide. The flag resets when the state clears, so a second
    /// excursion warns again.
    pub fn update_traction_cues(&mut self, ctx: &mut GameContext) {
        let planing = self.trip.truck.hydroplaning();
        if planing && !self.hydro_active {
            ctx.say_event_with(
                "Hydroplaning. The steering has gone light; ease off the speed.",
                SayEvent::new().category(SpeechCategory::Safety),
            );
        }
        self.hydro_active = planing;
        let slipping = self.trip.truck.jake_slipping() && self.trip.truck.speed_mph() > 5.0;
        if slipping && !self.jake_slip_active {
            ctx.say_event_with(
                "The drive wheels are sliding under the engine brake. Ease off the jake.",
                SayEvent::new().category(SpeechCategory::Safety),
            );
        }
        self.jake_slip_active = slipping;
        if self.trip.truck.chains_just_snapped {
            self.trip.truck.chains_just_snapped = false;
            ctx.say_event_with(
                "A tire chain let go and hammered the fender on its way off. The set is scrap; \
                 you are running on rubber again.",
                SayEvent::new().category(SpeechCategory::Money),
            );
        }
        let chains_fast =
            self.trip.truck.chains_on && self.trip.truck.speed_mph() > CHAIN_SAFE_MPH + 2.0;
        if chains_fast && !self.chains_fast_active {
            ctx.say_event_with(
                format!(
                    "The chains are hammering the pavement at this speed. Keep it under \
                     {CHAIN_SAFE_MPH:.0} or they will not last."
                ),
                SayEvent::new().category(SpeechCategory::Coaching),
            );
        }
        self.chains_fast_active = chains_fast;
    }

    /// Warn once per area, then run the deterministic checkpoint.
    ///
    /// The physics is the real enforcement -- glare ice at 0.15 grip does not
    /// negotiate -- but the law adds the honest paper consequence: roll past
    /// the midpoint of an active control out of compliance and the checkpoint
    /// at the bottom of the grade may have your number. One citation per area
    /// per level; the roll is seeded, so a reload does not re-roll the dice.
    pub fn update_chain_law(&mut self, ctx: &mut GameContext) {
        let level = self.trip.chain_law_level();
        if level == 0 || self.trip.truck.speed_mph() < 3.0 {
            return;
        }
        let Some(area) = self.trip.chain_law_area_at(self.trip.position_mi) else {
            return;
        };
        let compliant =
            self.trip.truck.chains_on || (level == 1 && self.trip.truck.tire_type == TIRE_WINTER);
        if compliant {
            return;
        }
        let key = (area as i64, level);
        if !self.chain_law_warned.contains(&key) {
            self.chain_law_warned.insert(key);
            let need = if level >= 2 {
                "chains"
            } else {
                "winter-rated tires or chains"
            };
            ctx.say_event_with(
                format!(
                    "You are rolling into an active chain law without {need}. Stop and chain up, \
                     or hope the checkpoint is unstaffed."
                ),
                SayEvent::new().category(SpeechCategory::Navigation),
            );
        }
        let (start, end) = self.trip.chain_law_areas[area];
        if self.trip.position_mi < (start + end) / 2.0 || self.chain_law_cited.contains(&key) {
            return;
        }
        self.chain_law_cited.insert(key);
        let mut rng =
            PyRandom::new_from_str(&format!("{}:chain-law:{area}:{level}", self.trip_seed));
        if rng.random() >= CHAIN_LAW_CHECKPOINT_CHANCE {
            return;
        }
        let zone = self.trip.in_construction_zone();
        let fine = citation_fine(
            CHAIN_LAW_FINE,
            career_citations(profile_of(ctx)),
            zone,
            None,
        );
        let money = {
            let p = profile_mut_of(ctx);
            p.money -= fine;
            p.money
        };
        self.ticket_fines_paid += fine;
        ctx.audio.play("ui/error");
        // A citation is money, not an act-now warning: ROUTE's never-dropped
        // queue instead of an interrupt that could erase one.
        ctx.say_event_with(
            format!(
                "Chain checkpoint. An officer waves you onto the scale apron and writes a \
                 chain-law citation: {} dollars.{} You have {} dollars.",
                fmt_grouped(fine, 0),
                construction_zone_fine_clause(zone),
                fmt_grouped(money, 0)
            ),
            SayEvent::queued()
                .priority(EventPriority::Route)
                .category(SpeechCategory::Money),
        );
    }
}
