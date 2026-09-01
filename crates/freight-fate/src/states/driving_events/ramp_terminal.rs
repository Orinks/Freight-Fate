//! What meets you where a ramp joins the surface road: the light or the sign,
//! the cross-traffic bubble, the stop bar's countdown and its held tone, the
//! route-transition assist, and the crossing itself.

use ff_core::pyrandom::PyRandom;
use ff_core::sim::cross_traffic::{cross_sound_lead_s, CrossTraffic, CrossVehicle};
use ff_core::sim::trip_models::RoadStop;
use ff_core::speech_pacing::{EventPriority, SpeechCategory};
use ff_core::units::spoken_feet_or_meters;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

use crate::states::driving_stops::{bar_solid_zone_mi, bar_tick_range_mi};

/// What a terminal violation met: a vehicle in the conflict window, one
/// arriving within a horn's length, or an empty crossroad.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum CrossMeeting {
    Hit,
    Near,
    Empty,
}

impl DrivingState {
    /// The control at this stop's ramp end, decidable any time.
    ///
    /// Baked OSM data (a traffic_signals or stop node on the exit's ramp
    /// links) wins; otherwise a seeded urban/rural heuristic stands in --
    /// most urban diamond terminals are signalized, rural ones lean to stop
    /// signs, and a share flow free like a cloverleaf loop. Pure function of
    /// the trip seed, the stop, and baked data, so the signal-on announcement
    /// a mile out and the ramp itself always agree.
    pub fn ramp_control_for(
        &self,
        _ctx: &GameContext,
        stop: &RoadStop,
        rng: Option<&mut PyRandom>,
    ) -> String {
        if stop.stop_type == "weigh_station" {
            // A scale has its own deceleration ramp flowing straight into
            // the inspection lane -- no public crossroad, no light, no stop
            // sign. The scale bar itself is the terminal, and the arrival
            // stop machinery already owns it ("At the scale. Stop now").
            // The dice used to put a stop sign here, spoken with the
            // MAINLINE's limit on its far side (owner playtest, 2026-08-20,
            // "Stop sign at ramp end. Limit 70").
            return "none".to_string();
        }
        let mut control = self.trip.ramp_control_at(stop.at_mi, 0.15);
        if control.is_empty() && self.ramp_meets_a_freeway(stop) {
            // A system interchange: this ramp ends in a merge onto another
            // freeway, and nothing stops traffic there. Decided before the
            // dice rather than by them -- see FREEWAY_VIA_RE.
            control = "none".to_string();
        }
        if control.is_empty() {
            let mut owned;
            let rng = match rng {
                Some(rng) => rng,
                None => {
                    owned = PyRandom::new_from_i64(
                        (self.trip_seed << 16) ^ (stop.at_mi * 100.0) as i64,
                    );
                    &mut owned
                }
            };
            let (signal_w, stop_w) = if self.trip.near_city(stop.at_mi) {
                RAMP_CONTROL_URBAN_WEIGHTS
            } else {
                RAMP_CONTROL_RURAL_WEIGHTS
            };
            let roll = rng.random();
            control = if roll < signal_w {
                "signal".to_string()
            } else if roll < stop_w {
                "stop".to_string()
            } else {
                "none".to_string()
            };
        }
        control
    }

    /// Whether this exit's ramp lands on another freeway.
    ///
    /// The baked `ramp_far_end` answers first: it is walked link topology, a
    /// fact about the road the ramp reaches. `surface` in particular
    /// SUPPRESSES the `via` guess below -- via is signage (where the exit
    /// points), not the road the ramp lands on, and measured against walked
    /// topology the signage guess called a controlled surface terminal "free
    /// flow" on about a third of the exits it fired on.
    ///
    /// The via fallback survives for exits the walk could not judge: 4,999 of
    /// the world's 18,011 exits lead to an interstate and every one of them
    /// used to take its chances with the urban/rural weights below, which
    /// handed stop signs to roughly half the rural ones -- a stop sign where
    /// an interstate meets an interstate does not exist (owner, 2026-08-17).
    pub fn ramp_meets_a_freeway(&self, stop: &RoadStop) -> bool {
        let Some(interchange) = self.trip.interchange_at(stop.at_mi, 0.15) else {
            return false;
        };
        if interchange.ramp_far_end == "motorway" {
            return true;
        }
        if interchange.ramp_far_end == "surface" {
            return false;
        }
        freeway_via_matches(&interchange.via.to_uppercase())
    }

    /// Set up the terminal control state for the ramp just taken.
    pub fn begin_ramp_terminal(&mut self, ctx: &GameContext, stop: &RoadStop) {
        let mut rng = PyRandom::new_from_i64((self.trip_seed << 16) ^ (stop.at_mi * 100.0) as i64);
        self.ramp_control = self.ramp_control_for(ctx, stop, Some(&mut rng));
        self.ramp_light_timer = 0.0;
        self.ramp_light_offset_s =
            rng.random() * (RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S + RAMP_LIGHT_YELLOW_S);
        self.ramp_light_announced = false;
        self.ramp_light_last_phase = String::new();
        self.ramp_terminal_done = self.ramp_control == "none";
        self.ramp_waiting_at_light = false;
        self.ramp_creep_prompt_said = false;
        self.ramp_gap_milestones_said.clear();
        self.ramp_bar_tick_timer = 0.0;
        self.ramp_assist_said = false;
        self.ramp_assist_brake = 0.0;
        self.ramp_waiting_at_sign = false;
        self.approach_pull_ahead = false;
        self.approach_pull_ahead_canceled = false;
        // The cross bubble: a controlled terminal means a real crossroad, so
        // simulate it. Seeded like the control itself so the same terminal
        // always carries the same traffic day; the near-city split reuses the
        // same urban/rural judgment the control dice already trust.
        self.cross_bubble = if matches!(
            self.ramp_control.as_str(),
            "signal" | "stop" | "yield" | "roundabout"
        ) {
            // A roundabout entry is gap acceptance against circulating
            // traffic: yield rates, spoken as a roundabout.
            let control = if self.ramp_control == "roundabout" {
                "yield"
            } else {
                self.ramp_control.as_str()
            };
            Some(CrossTraffic::new(
                (self.trip_seed << 16) ^ (stop.at_mi * 100.0) as i64 ^ 0x5AFE,
                control,
                self.trip.near_city(stop.at_mi),
            ))
        } else {
            None
        };
    }

    /// `_ramp_light_phase()`.
    pub fn ramp_light_phase(&self) -> &'static str {
        let cycle = RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S + RAMP_LIGHT_YELLOW_S;
        let into = (self.ramp_light_offset_s + self.ramp_light_timer).rem_euclid(cycle);
        if into < RAMP_LIGHT_RED_S {
            return "red";
        }
        if into < RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S {
            return "green";
        }
        "yellow"
    }

    /// Only true red punishes a crossing: entering on yellow is legal,
    /// exactly like the real law.
    pub fn ramp_light_is_red(&self) -> bool {
        self.ramp_light_phase() == "red"
    }

    /// Advance the terminal light in real time and speak state changes.
    pub fn update_ramp_light(&mut self, ctx: &mut GameContext, dt: f64) {
        // The bar's cues run first and unconditionally. They are the only code
        // that stops the solid tone, and every early return below used to skip
        // them: a driver who reached the tone and then crossed the bar --
        // green, red, or stop sign -- carried it through the rest of the run
        // and out into the menus (Shane, 2026-08-03).
        self.update_ramp_bar_ticks(ctx, dt);
        self.update_cross_bubble(ctx, dt);
        if self.ramp_mi.is_none() || self.ramp_terminal_done {
            return;
        }
        if matches!(self.ramp_control.as_str(), "stop" | "yield" | "roundabout") {
            // A sign has no phases, but its bar needs a position just
            // as much as a light's: without the countdown, the ticks, and
            // the stopped-short guidance, the sign was one announce line
            // and then silence until the damage message (playtest
            // 2026-07-22, Milwaukee grain elevator, 15 percent).
            self.update_ramp_queue_guidance(ctx);
            self.update_ramp_gap_countdown(ctx);
            return;
        }
        if self.ramp_control != "signal" {
            return;
        }
        self.ramp_light_timer += dt;
        self.update_ramp_queue_guidance(ctx);
        self.update_ramp_gap_countdown(ctx);
        let phase = self.ramp_light_phase();
        if !self.ramp_light_announced || phase == self.ramp_light_last_phase {
            return;
        }
        self.ramp_light_last_phase = phase.to_string();
        if self.ramp_waiting_at_light && phase == "green" {
            // The wait at the stop bar ends; the driveway is just ahead.
            self.ramp_waiting_at_light = false;
            self.ramp_terminal_done = true;
            ctx.audio.play_with("events/ramp_light_green", 0.8, 0.0);
            let message = self.terminal_release_text(ctx, "Green light.", false);
            self.say_route_navigation(ctx, &message);
            return;
        }
        // Every phase change speaks. The light is an instruction, not
        // ambiance: a silent flip back to red between the spoken green and
        // the stop bar cost real playtesters real trailer damage. The wording
        // is distance-aware: a screen shows where the stop bar is, so speech
        // has to say whether the driver has reached it.
        //
        // ROUTE, for the same reason the comment above gives. Left at the
        // AMBIENT default, this whole family waited the full stale budget
        // behind whatever was speaking, and on a real ramp the pacer dropped
        // the assist's own "braking for the light" sixteen milliseconds after
        // the yellow call, then "through on the yellow" behind it -- so the
        // truck braked for the light and the driver was told none of it
        // (owner playtest, 2026-08-15).
        let short = self.ramp_mi.unwrap_or(0.0) > RAMP_ACCESS_MI;
        if phase == "red" {
            ctx.audio.play_with("events/ramp_light_red", 0.7, 0.0);
            self.say_route_navigation(ctx, "The light ahead turns red. Be ready to stop.");
        } else if phase == "yellow" {
            ctx.audio.play_with("ui/notify", 0.7, 0.0);
            let message = if short {
                "The light ahead turns yellow. You are short of it: stop, then creep up to the \
                 bar on the red."
            } else {
                "The light turns yellow at the bar. Continuing through is legal."
            };
            self.say_route_navigation(ctx, message);
        } else {
            ctx.audio.play_with("events/ramp_light_green", 0.7, 0.0);
            let message = if short {
                "The light ahead turns green. Roll toward it; if it changes before you are \
                 there, stop and creep up on the red."
            } else {
                "The light ahead turns green."
            };
            self.say_route_navigation(ctx, message);
        }
    }

    /// Which distances to the stop bar are worth SAYING on this rung.
    ///
    /// The bar already has a non-spoken instrument: inside
    /// `RAMP_BAR_TICK_RANGE_MI` a centre tick speeds up as the bar closes,
    /// and fuses to a solid tone at the end. Rate carries distance, silence
    /// means stopped. So a spoken milestone inside that range is speech
    /// restating what the driver is already listening to -- four calls on
    /// every ramp terminal, of which the last two were audible twice.
    ///
    /// Standard keeps the calls the tick cannot make, the ones out beyond its
    /// range. Quiet keeps one: the rung means less automatic speech, the
    /// terminal callout has already named the light or the sign, and the tick
    /// does the rest of the work (owner, 2026-08-21).
    pub fn ramp_bar_milestones(&self, ctx: &GameContext) -> Vec<i64> {
        let imperial = ctx.settings.imperial_units;
        let thresholds: &[i64] = if imperial {
            &RAMP_GAP_MILESTONES_FT
        } else {
            &RAMP_GAP_MILESTONES_M
        };
        let unit_mi = if imperial {
            1.0 / 5280.0
        } else {
            1.0 / 1609.344
        };
        let mut outside_tick: Vec<i64> = thresholds
            .iter()
            .copied()
            .filter(|threshold| *threshold as f64 * unit_mi > RAMP_BAR_TICK_RANGE_MI)
            .collect();
        // Never silent: a unit system whose milestones all sit inside the tick
        // range still gets its farthest call, so the bar is never announced by
        // sound alone to a driver who has the tick turned down.
        if outside_tick.is_empty() {
            outside_tick = thresholds[..1].to_vec();
        }
        if self.terse_speech(ctx) {
            // Quiet gets the far call and the HANDOFF call -- the one at the
            // distance where the tick starts, so the words hand the driver to
            // the sound rather than simply stopping (owner, after driving it,
            // 2026-08-21: "leave 300 in because that's when the stop bar beeps
            // come in, so the sound will do the guiding at that point"). In
            // feet that is 300 exactly; in metres the nearest milestone to the
            // same physical distance.
            let handoff = thresholds
                .iter()
                .copied()
                .min_by(|a, b| {
                    ((*a as f64 * unit_mi) - RAMP_BAR_TICK_RANGE_MI)
                        .abs()
                        .total_cmp(&(((*b as f64 * unit_mi) - RAMP_BAR_TICK_RANGE_MI).abs()))
                })
                .expect("the milestone table is never empty");
            let far = outside_tick[0];
            return if handoff == far {
                vec![far]
            } else {
                vec![far, handoff]
            };
        }
        // Two is the owner's number (2026-08-21), and it makes both unit
        // systems behave alike: the tick rule alone left metric with a third
        // call at 100 metres that imperial had no equivalent for.
        outside_tick.into_iter().take(2).collect()
    }

    /// Run the crossroad's own traffic while the terminal is live.
    ///
    /// Real seconds, like the light: the terminal already stops the clock
    /// compressing, and a gap that shrank at 4x would be unreadable. Each
    /// vehicle fires its crossing cue half a cue-length before it reaches the
    /// conflict point, panned to the ear it comes from, so the peak of the
    /// doppler lands on the actual crossing -- the gap IS the audio.
    pub fn update_cross_bubble(&mut self, ctx: &mut GameContext, dt: f64) {
        if self.cross_bubble.is_none() {
            return;
        }
        if self.ramp_mi.is_none() || self.ramp_terminal_done {
            // The terminal released the driver; the crossroad is behind them.
            self.cross_bubble = None;
            return;
        }
        if self.ramp_control == "signal" {
            // The cross street runs the orthogonal phase. Yellow counts as
            // ours: real cross traffic is already stopped by then.
            let green = self.ramp_light_phase() != "red";
            if let Some(bubble) = self.cross_bubble.as_mut() {
                bubble.player_has_green = green;
            }
        }
        let ramp_mi = self.ramp_mi.unwrap_or(0.0);
        // The crossroad fades in down the ramp: nothing until the terminal
        // callout distance, full presence at the bar.
        let closeness = 1.0 - 1.0f64.min(0.0f64.max(ramp_mi) / RAMP_CONTROL_ANNOUNCE_MI);
        let mut cues: Vec<(&'static str, f64, f64)> = Vec::new();
        if let Some(bubble) = self.cross_bubble.as_mut() {
            bubble.update(dt);
            if closeness <= 0.05 {
                return;
            }
            for vehicle in bubble.vehicles.iter_mut() {
                if vehicle.sound_started || vehicle.position_mi >= 0.0 || vehicle.speed_mph <= 1.0 {
                    continue;
                }
                let eta = -vehicle.position_mi * 3600.0 / vehicle.speed_mph;
                if eta > cross_sound_lead_s(vehicle.vehicle_class).unwrap_or(1.2) {
                    continue;
                }
                vehicle.sound_started = true;
                cues.push((
                    vehicle.vehicle_class,
                    0.25 + 0.6 * closeness,
                    if vehicle.from_side == "left" {
                        -0.7
                    } else {
                        0.7
                    },
                ));
            }
        }
        for (vehicle_class, volume, pan) in cues {
            let key = format!("traffic/{}_cross", vehicle_class.replace(' ', "_"));
            ctx.audio.play_with(&key, volume, pan);
        }
    }

    /// What a terminal violation met, and the vehicle it met.
    ///
    /// With no bubble to consult (older saves mid-ramp), the old certainty
    /// stands: the violation hits.
    pub fn cross_violation_meets(&self) -> (CrossMeeting, Option<CrossVehicle>) {
        let Some(bubble) = self.cross_bubble.as_ref() else {
            return (CrossMeeting::Hit, None);
        };
        if let Some(vehicle) = bubble.occupant() {
            return (CrossMeeting::Hit, Some(vehicle.clone()));
        }
        if let Some(vehicle) = bubble.approaching(2.0) {
            return (CrossMeeting::Near, Some(vehicle.clone()));
        }
        (CrossMeeting::Empty, None)
    }

    /// The crossing cue for the vehicle a violation met.
    pub fn cross_vehicle_sound(vehicle: Option<&CrossVehicle>) -> String {
        match vehicle {
            None => "traffic/car_cross".to_string(),
            Some(vehicle) => format!("traffic/{}_cross", vehicle.vehicle_class.replace(' ', "_")),
        }
    }

    /// Tell a driver stopped short of the stop bar to close the gap.
    ///
    /// A cautious stop on the first "brake to a stop" callout can land a
    /// quarter mile short of the bar, where one green is never enough road
    /// from a standstill. Without this prompt that plays as a light stuck in
    /// an endless loop (playtest transcript, 2026-07-16).
    pub fn update_ramp_queue_guidance(&mut self, ctx: &mut GameContext) {
        if !self.ramp_light_announced || self.ramp_waiting_at_light {
            return;
        }
        let Some(ramp_mi) = self.ramp_mi else {
            return;
        };
        if ramp_mi <= RAMP_ACCESS_MI {
            return;
        }
        if self.trip.truck.speed_mph() > RED_STOP_MPH {
            self.ramp_creep_prompt_said = false;
            return;
        }
        if self.ramp_creep_prompt_said {
            return;
        }
        self.ramp_creep_prompt_said = true;
        // Name the gap: "creep" for a real 600-foot gap takes minutes and
        // reads as a light stuck in a loop. Far back is a drive, and the red
        // phase is exactly the time to make it.
        let gap_mi = ramp_mi - RAMP_ACCESS_MI;
        if matches!(self.ramp_control.as_str(), "stop" | "yield" | "roundabout") {
            let noun = match self.ramp_control.as_str() {
                "stop" => "the stop sign",
                "yield" => "the yield line",
                _ => "the roundabout entry",
            };
            // A stop sign demands the stop at the bar; a yield only asks for
            // the gap there.
            let tail = if self.ramp_control == "stop" {
                "stop again at the bar"
            } else {
                "take your gap at the bar"
            };
            let message = if gap_mi > RAMP_CREEP_MI {
                let gap = self.short_distance_text(ctx, gap_mi);
                format!("You are stopped about {gap} short of {noun}. Drive up and {tail}.")
            } else {
                format!("You are stopped short of {noun}. Creep ahead and {tail}.")
            };
            // ROUTE, not the ambient default. This is an instruction about a
            // STANDING condition -- the truck is stopped short of the bar and
            // stays stopped until the driver acts -- so the staleness rule that
            // drops a line "starting after the moment it described" is reading
            // a moment that has not passed. It dropped exactly this line in the
            // owner playtest of 2026-08-17, leaving the truck 1,350 feet short
            // through a whole green-yellow-red cycle with nothing said; the same
            // failure the comment below already records from 2026-07-19. ROUTE
            // waits its turn behind anything urgent, and is never dropped.
            self.say_route_navigation(ctx, &message);
            return;
        }
        let on_green = self.ramp_light_phase() == "green";
        let message = if gap_mi > RAMP_CREEP_MI {
            let gap = self.short_distance_text(ctx, gap_mi);
            if on_green {
                format!(
                    "You are stopped about {gap} short of the light, and it is green. Drive up \
                     now; stop at the bar if it changes."
                )
            } else {
                format!(
                    "You are stopped about {gap} short of the light. Drive up and stop at the \
                     bar; the red is the time to close the gap."
                )
            }
        } else if on_green {
            "You are stopped short of the light and it is green. Roll ahead now.".to_string()
        } else {
            "You are stopped short of the light. Creep ahead and hold at the stop bar for green."
                .to_string()
        };
        // ROUTE, not the ambient default. This is an instruction about a
        // STANDING condition -- the truck is stopped short of the bar and
        // stays stopped until the driver acts -- so the staleness rule that
        // drops a line "starting after the moment it described" is reading
        // a moment that has not passed. It dropped exactly this line in the
        // owner playtest of 2026-08-17, leaving the truck 1,350 feet short
        // through a whole green-yellow-red cycle with nothing said; the same
        // failure the comment below already records from 2026-07-19. ROUTE
        // waits its turn behind anything urgent, and is never dropped.
        self.say_route_navigation(ctx, &message);
    }

    /// Count the stop bar down while the truck is rolling toward it.
    ///
    /// The stopped-driver prompt above names the gap only at a standstill, so
    /// a rolling driver had no idea where the bar was: the owner crept 1300
    /// feet in stop-and-listen hops across three light cycles (playtest log,
    /// 2026-07-19). Rolling milestone calls give the bar a position the same
    /// way the exit countdown gives the exit one.
    pub fn update_ramp_gap_countdown(&mut self, ctx: &mut GameContext) {
        if !self.ramp_light_announced || self.ramp_waiting_at_light {
            return;
        }
        let Some(ramp_mi) = self.ramp_mi else {
            return;
        };
        if ramp_mi <= RAMP_ACCESS_MI {
            return;
        }
        if self.trip.truck.speed_mph() <= RED_STOP_MPH {
            return;
        }
        let gap_mi = ramp_mi - RAMP_ACCESS_MI;
        let thresholds = self.ramp_bar_milestones(ctx);
        let imperial = ctx.settings.imperial_units;
        let unit_mi = if imperial {
            1.0 / 5280.0
        } else {
            1.0 / 1609.344
        };
        let unit_word = if imperial { "feet" } else { "meters" };
        for threshold in thresholds {
            if gap_mi <= threshold as f64 * unit_mi
                && !self.ramp_gap_milestones_said.contains(&threshold)
            {
                self.ramp_gap_milestones_said.insert(threshold);
                if self.terse_speech(ctx) {
                    // The distance, and nothing else. Quiet gets ONE call for
                    // the whole approach, and by the time it lands the driver
                    // has already been told this is a bar and what the limit
                    // is -- so repeating either of those is the wordiness the
                    // rung exists to remove (owner, 2026-08-21, replacing the
                    // compact-line spec of 2026-07-23 for this line only).
                    self.say_route_navigation(ctx, &format!("{threshold} {unit_word}."));
                    return;
                }
                self.say_route_navigation(ctx, &format!("{threshold} {unit_word} to the bar."));
                return;
            }
        }
    }

    /// The continuous tone of the bar's final zone.
    ///
    /// Held, not started: the tone is re-asserted on every tick it applies to
    /// and lapses on its own as soon as it is not, so it cannot survive this
    /// state losing the frame to a menu or an arrival screen. Turning it back
    /// off here is still instant.
    pub fn set_bar_solid(&mut self, ctx: &mut GameContext, on: bool) {
        if on {
            // 0.85 read as jarring against everything else on the road
            // (Darren, 2026-08-15): a continuous tone at nearly full scale
            // sits far louder than the intermittent cues around it, and this
            // one plays while the driver is concentrating on stopping. The
            // tone still has to be unmistakable, so it stays the loudest
            // continuous cue -- just no longer the loudest thing in the cab.
            ctx.audio
                .hold_alert_with("vehicle/bar_solid", BAR_SOLID_VOLUME, 60);
        } else if self.bar_solid_on {
            ctx.audio.release_alert();
        }
        self.bar_solid_on = on;
    }

    /// Parking-sensor tick for the stop bar's last few hundred feet.
    ///
    /// Rate carries the distance -- faster is closer -- and silence means
    /// stopped, so the cue never nags a driver holding at the bar. Center pan,
    /// unlike the side-panned curve cues, so the two never read as the same
    /// instrument (owner ask, 2026-07-19). Inside the last stretch of leeway,
    /// still moving, the ticks fuse into a continuous tone (owner spec,
    /// written into the manual 2026-07-27): at the solid tone you had better
    /// be close to stopped.
    pub fn update_ramp_bar_ticks(&mut self, ctx: &mut GameContext, dt: f64) {
        if !self.ramp_light_announced || self.ramp_waiting_at_light {
            self.set_bar_solid(ctx, false);
            return;
        }
        let Some(ramp_mi) = self.ramp_mi else {
            self.set_bar_solid(ctx, false);
            return;
        };
        if self.ramp_terminal_done {
            self.set_bar_solid(ctx, false);
            return;
        }
        if self.trip.truck.speed_mph() <= RED_STOP_MPH {
            self.set_bar_solid(ctx, false);
            return;
        }
        let gap_mi = ramp_mi - RAMP_ACCESS_MI;
        // Both distances come from what this truck can actually stop in, with
        // the old constants as their floors: a load that stops longer -- hot
        // brakes, ice, a downgrade, liquid running forward in a tank -- hears
        // the bar earlier, because it needs the road earlier.
        let tick_range_mi = bar_tick_range_mi(&self.trip.truck);
        let solid_mi = bar_solid_zone_mi(&self.trip.truck);
        if gap_mi > tick_range_mi || gap_mi < 0.0 {
            self.set_bar_solid(ctx, false);
            return;
        }
        if gap_mi <= solid_mi {
            self.set_bar_solid(ctx, true);
            return;
        }
        self.set_bar_solid(ctx, false);
        let closeness = 1.0 - gap_mi / tick_range_mi;
        let period =
            RAMP_BAR_TICK_SLOW_S - closeness * (RAMP_BAR_TICK_SLOW_S - RAMP_BAR_TICK_FAST_S);
        self.ramp_bar_tick_timer += dt;
        if self.ramp_bar_tick_timer >= period {
            self.ramp_bar_tick_timer = 0.0;
            // Full volume: at 0.5 the owner judged it missable by someone
            // not listening for it (2026-07-19). The dedicated beep the old
            // note asked for arrived with the curve bink (2026-07-27).
            ctx.audio.play_with("vehicle/curve_bink", 0.9, 0.0);
        }
    }

    /// Light phase and bar distance on demand, for the info keys.
    ///
    /// "Stop at the bar" is only an instruction if the bar has a position; a
    /// sighted driver reads it off the windshield, so speech must answer the
    /// same question whenever the driver asks (owner ask, 2026-07-19).
    pub fn ramp_light_query_text(&mut self, ctx: &GameContext) -> Option<String> {
        let ramp_mi = self.ramp_mi?;
        if !matches!(self.ramp_control.as_str(), "signal" | "stop") || self.ramp_terminal_done {
            return None;
        }
        let gap_mi = ramp_mi - RAMP_ACCESS_MI;
        if self.ramp_control == "stop" {
            if gap_mi <= 0.0 {
                return Some("At the stop bar. Stop sign; brake to a full stop.".to_string());
            }
            let limit_text = self.approach_limit_text(ctx);
            let limit_clause = if limit_text.is_empty() {
                String::new()
            } else {
                format!(", speed limit {limit_text}")
            };
            return Some(format!(
                "Stop sign, about {} to the stop bar{limit_clause}.",
                self.short_distance_text(ctx, gap_mi)
            ));
        }
        let phase = self.ramp_light_phase();
        if gap_mi <= 0.0 {
            return Some(format!("At the stop bar. The light is {phase}."));
        }
        let limit_text = self.approach_limit_text(ctx);
        let limit_clause = if limit_text.is_empty() {
            String::new()
        } else {
            format!(", speed limit {limit_text}")
        };
        Some(format!(
            "Light {phase}, about {} to the stop bar{limit_clause}.",
            self.short_distance_text(ctx, gap_mi)
        ))
    }

    /// A short gap in round spoken units: feet or meters, never decimals.
    pub fn short_distance_text(&self, ctx: &GameContext, miles: f64) -> String {
        spoken_feet_or_meters(miles, ctx.settings.imperial_units)
    }

    /// The enforced limit AT THE STOP BAR, spoken.
    ///
    /// The terminal callouts named the control but never the limit the
    /// approach is driven at (owner report 2026-07-23). First cut read the
    /// limit at the truck's position -- which mid-ramp still said 55, the
    /// highway's number, useless for a light a quarter mile ahead (owner's
    /// log, same night). The honest number is the zone at the bar itself: the
    /// street being entered.
    pub fn approach_limit_text(&mut self, ctx: &GameContext) -> String {
        let mut bar_mi = self.trip.position_mi;
        if let Some(ramp_mi) = self.ramp_mi {
            bar_mi += 0.0f64.max(ramp_mi - RAMP_ACCESS_MI);
        }
        // Probe just PAST the bar, not at it: the entered road's zone (the
        // facility access 25, the street's 35) begins on the far side, so a
        // probe at the bar itself still read the corridor's 55 -- the owner
        // was told "speed limit 55 on the approach" at a stop sign whose far
        // side was a 25 access road (log, 2026-07-23, Merced).
        bar_mi += 0.05;
        bar_mi = bar_mi.min(0.0f64.max(self.trip.total_miles() - 0.01));
        let (limit, _) = self.trip.speed_limit_at(bar_mi);
        // Screened for self-contradiction, not extremity: a street behind a
        // ramp terminal is never posted at the corridor's own highway number,
        // so a probe that comes back with one found no street zone at all --
        // it read the mainline through the gap and told the owner "Stop sign
        // at ramp end. Limit 70" at two exits running (playtest, 2026-08-20).
        // Better no limit clause than a wrong one.
        let position = self.trip.position_mi;
        let (corridor_limit, _) = self.trip.speed_limit_at(position);
        if limit >= corridor_limit && corridor_limit > RAMP_MAX_MPH {
            return String::new();
        }
        ctx.settings.speed_text(limit)
    }

    /// Mid-ramp callout naming the control at the terminal.
    pub fn announce_ramp_terminal(&mut self, ctx: &mut GameContext) {
        self.ramp_light_announced = true;
        let limit_text = self.approach_limit_text(ctx);
        let terse = self.terse_speech(ctx);
        if self.ramp_control == "signal" {
            let phase = self.ramp_light_phase();
            self.ramp_light_last_phase = phase.to_string();
            ctx.audio.play_with(
                if phase == "red" {
                    "events/ramp_light_red"
                } else {
                    "events/ramp_light_green"
                },
                0.8,
                0.0,
            );
            if terse {
                // The limit clause is CONDITIONAL, like every other one built
                // from this text. `approach_limit_text` deliberately returns
                // nothing when it cannot trust the number -- better no clause
                // than a wrong one -- and interpolating that gave quiet
                // drivers a sentence with a hole in it: "Light at ramp end,
                // green. Limit ." (Shane P, 2026-08-23). The stop, yield and
                // roundabout branches below always guarded it; this one did
                // not.
                let limit_clause = if limit_text.is_empty() {
                    String::new()
                } else {
                    format!(" Limit {limit_text}.")
                };
                self.say_route_navigation(
                    ctx,
                    &format!("Light at ramp end, {phase}.{limit_clause}"),
                );
                return;
            }
            // "Brake to a stop" alone invites stopping right here, a quarter
            // mile short of the bar; the stop belongs at the light.
            let message = if phase == "red" {
                "Traffic light at the end of the ramp, currently red. Roll down and stop at the \
                 light."
            } else if phase == "yellow" {
                "Traffic light at the end of the ramp, currently yellow -- it will be red when \
                 you reach it. Roll down and stop at the light."
            } else {
                "Traffic light at the end of the ramp, currently green."
            };
            let approach_clause = if limit_text.is_empty() {
                String::new()
            } else {
                format!(" Speed limit {limit_text} on the approach.")
            };
            self.say_route_navigation(ctx, &format!("{message}{approach_clause}"));
        } else if self.ramp_control == "stop" {
            ctx.audio.play_with("ui/notify", 0.7, 0.0);
            if terse {
                let limit_clause = if limit_text.is_empty() {
                    String::new()
                } else {
                    format!(" Limit {limit_text}.")
                };
                self.say_route_navigation(ctx, &format!("Stop sign at ramp end.{limit_clause}"));
                return;
            }
            let approach_clause = if limit_text.is_empty() {
                String::new()
            } else {
                format!(" Speed limit {limit_text} on the approach.")
            };
            self.say_route_navigation(
                ctx,
                &format!(
                    "Stop sign at the end of the ramp. Brake to a full stop there.{approach_clause}"
                ),
            );
        } else if matches!(self.ramp_control.as_str(), "yield" | "roundabout") {
            ctx.audio.play_with("ui/notify", 0.7, 0.0);
            let terse_noun = if self.ramp_control == "roundabout" {
                "Roundabout"
            } else {
                "Yield"
            };
            if terse {
                let limit_clause = if limit_text.is_empty() {
                    String::new()
                } else {
                    format!(" Limit {limit_text}.")
                };
                self.say_route_navigation(ctx, &format!("{terse_noun} at ramp end.{limit_clause}"));
                return;
            }
            // The instruction is the sign's real rule: slow for the gap, and
            // the stop is only owed when the road is not clear. "Brake to a
            // stop" here would teach the stop-sign habit at a sign whose
            // whole point is that a clear road never demands it.
            let message = if self.ramp_control == "roundabout" {
                "Roundabout at the end of the ramp. Yield to traffic in the circle: slow, listen \
                 for your gap, and stop only if it is not clear."
            } else {
                "Yield sign at the end of the ramp. Slow, listen for your gap, and stop only if \
                 the road is not clear."
            };
            let approach_clause = if limit_text.is_empty() {
                String::new()
            } else {
                format!(" Speed limit {limit_text} on the approach.")
            };
            self.say_route_navigation(ctx, &format!("{message}{approach_clause}"));
        }
    }

    /// One ROUTE-priority navigation line, the shape this whole section uses.
    pub(crate) fn say_route_navigation(&self, ctx: &mut GameContext, message: &str) {
        let mut opts = SayEvent::queued().priority(EventPriority::Route);
        opts.category = Some(SpeechCategory::Navigation);
        ctx.say_event_with(message.to_string(), opts);
    }

    /// One ROUTE-priority confirmation line.
    pub(crate) fn say_route_confirmation(&self, ctx: &mut GameContext, message: &str) {
        let mut opts = SayEvent::queued().priority(EventPriority::Route);
        opts.category = Some(SpeechCategory::Confirmation);
        ctx.say_event_with(message.to_string(), opts);
    }
}
