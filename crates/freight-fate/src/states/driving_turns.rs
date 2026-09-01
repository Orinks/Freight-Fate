//! Street corners cost speed, not reflex: be under the turn speed or loop back
//! (port of `freight_fate/states/driving_turns.py`, the `TurnCommitmentMixin`).
//!
//! The sim carries no heading or yaw -- `LaneKeeping` has a lateral offset and
//! a discrete lane index and nothing else -- so a "manual turn" could only ever
//! have been a reaction-window quick-time event. That version was built and
//! withdrawn (2026-07-15) because a timed snap excludes players with slow
//! reaction or motor impairments. The owner's replacement is commitment, not
//! reflex: a corner is a speed you have to be under by the time you reach it,
//! announced far enough out to brake by ear, exactly the way the exit ramp
//! already demands `RAMP_MAX_MPH` and the facility gate demands
//! `FACILITY_GATE_LIMIT_MPH`. Braking to a spoken number is plannable; snapping
//! an arrow inside a second and a half is not.
//!
//! The turn speed is anchored to the road, never invented: the street the truck
//! is turning ONTO carries a baked `local_speed_mph` (25 named, 15 unnamed
//! service ways), and the corner itself is capped at `TURN_CORNER_MAX_MPH`. A
//! 53-foot trailer off-tracks through a signalised city corner; CDL training
//! teaches completing one at 10 to 15, entering at no more than 20. Twenty also
//! sits honestly between the two speeds the game already posts -- a sweeping
//! ramp at 45 and the gate crawl at 15 -- so the ladder a player learns by ear
//! stays ordered.
//!
//! The miss is the fourth instance of the shipped loop-back pattern (blown ramp
//! stop, missed destination exit, missed facility gate) and inherits the two
//! lessons that cost the most to learn:
//!
//! - Drop back a FULL SPOKEN WINDOW, never a fixed distance. Under time
//!   compression a fixed stretch passes before it can be heard, so the retry is
//!   unwinnable.
//! - RESET EVERY say-once latch on the reposition, including the trip's own
//!   navigation announcements. When the missed-exit loop did not, the second
//!   miss stranded the trip.
//!
//! Escalation ships on day one, because a loop with no escalation is a route
//! that can stop being finishable: the core sentence is identical every time so
//! the flow stays predictable by ear, help is appended from the second miss, and
//! the corner is completed for the player -- with the time still charged --
//! either on a repeat miss of the SAME corner or on the third miss anywhere.
//!
//! Highway junctions are deliberately not judged here. Their cues carry no
//! direction, radius, or lane ordinal, and `docs/nav-phrasing-brief.md` forbids
//! speaking a lane ordinal that was never harvested.

use ff_core::data::curves::RouteCurve;
use ff_core::sim::trip_models::{
    NavigationCue, FACILITY_ACCESS_LIMIT_MPH, FACILITY_GATE_LIMIT_MPH,
};
use ff_core::speech_pacing::{EventPriority, SpeechCategory};

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

/// The approach call is sized in REAL seconds of hearing-and-braking time, the
/// same budget the exit callout gets, then converted to game miles at the
/// current pace. `LOCAL_TURN_LOOKAHEAD_MI` alone is about 1.4 real seconds at
/// street speed -- a reflex window, which is the thing this design refuses.
pub const TURN_WARNING_REAL_S: f64 = 25.0;
/// Bounded by the road it lives on: a city block is short, and no corner call
/// should arrive two miles of arterial before the corner exists.
pub const TURN_WINDOW_MIN_MI: f64 = 0.25;
pub const TURN_WINDOW_MAX_MI: f64 = 2.0;
/// The corner ceiling for a tractor-trailer, whatever the street is posted at.
pub const TURN_CORNER_MAX_MPH: f64 = 20.0;
/// Brake deadband: the truck may be a few mph over without failing, the same
/// forgiveness the curve assist's hysteresis grants.
pub const TURN_SPEED_MARGIN_MPH: f64 = 3.0;
/// Game minutes one loop through the safe turnaround costs. The gate and the
/// destination exit charge 20 for a highway-scale turnaround -- miles of
/// frontage road at 45 and back. A city corner is four right turns around one
/// block at 20 with signals on two of them, so it costs a fraction of that.
pub const TURN_MISS_LOOP_MIN: f64 = 8.0;
/// How far past the corner it stays the corner in play, and where a completed
/// turn puts the truck back on the road.
pub const TURN_COMMIT_TAIL_MI: f64 = 0.15;
/// Inside this the approach call drops the distance and says "now" -- and is
/// an act-now instruction rather than a lead, which changes how it is paced.
pub const TURN_NOW_MI: f64 = 0.05;
/// The pursuit guide starts leaning into the corner this far out, reaching its
/// full lean at the corner itself.
pub const TURN_GUIDE_LEAD_MI: f64 = 0.2;
pub const TURN_GUIDE_DEMAND: f64 = 0.9;
/// An exit ramp peels right; the lane model already pushes the truck that way,
/// so the road bed leans with it instead of sitting dead centre.
pub const RAMP_GUIDE_DEMAND: f64 = 0.45;

/// `_is_judged_turn(cue)`: a baked street maneuver with a real side to it.
///
/// `local:start` is where the chain begins, not a corner, and an "ahead"
/// or "straight" maneuver has nothing to steer through.
pub fn is_judged_turn(cue: &NavigationCue) -> bool {
    cue.kind == "local_turn"
        && cue.key.starts_with("local:turn:")
        && matches!(
            cue.direction.trim().to_lowercase().as_str(),
            "left" | "right"
        )
}

impl DrivingState {
    // -- the corner in play ---------------------------------------------------

    /// `_reset_turn_state_for_trip()`: cue keys belong to one trip's route; a
    /// surface-chain swap builds a new one, so the latches start clean with it.
    pub fn reset_turn_state_for_trip(&mut self) {
        self.turn_trip_id = self.trip_generation;
        self.turn_advised.clear();
        self.turn_missed.clear();
        self.turn_resolved.clear();
        self.turn_grace_s = 0.0;
        self.trip.controlled_turn = false;
    }

    /// `_turn_cues_in_play()`: every unsettled corner from here on, nearest
    /// first.
    ///
    /// The commitment loop only ever judges one corner at a time, so it asks
    /// for the first of these. A planner that has to BRAKE for corners needs
    /// the whole run: city blocks are shorter than one corner's own tail, so
    /// the next corner is regularly already in front of the truck while this
    /// one is still being taken.
    pub fn turn_cues_in_play(&mut self) -> Vec<NavigationCue> {
        if self.turn_trip_id != self.trip_generation {
            self.reset_turn_state_for_trip();
        }
        let position = self.trip.position_mi;
        let mut cues: Vec<NavigationCue> = self
            .trip
            .navigation_cues
            .iter()
            .filter(|cue| {
                is_judged_turn(cue)
                    && !self.turn_resolved.contains(&cue.key)
                    && cue.at_mi - position >= -TURN_COMMIT_TAIL_MI
            })
            .cloned()
            .collect();
        cues.sort_by(|a, b| a.at_mi.total_cmp(&b.at_mi));
        cues
    }

    /// `_turn_cue_in_play()`: the corner currently being approached or judged,
    /// or None.
    pub fn turn_cue_in_play(&mut self) -> Option<NavigationCue> {
        self.turn_cues_in_play().into_iter().next()
    }

    /// The same read without the lazy latch reset, for the one caller that
    /// only has `&self`.
    ///
    /// Python's `_turn_cues_in_play` re-seeds the per-corner latches when the
    /// trip has been swapped; the pursuit guide below reads the corner from
    /// the audio pass, which `_update_turn_commitment` has already run ahead
    /// of in the same frame (`driving_updates.py`: 577 before 595), so the
    /// re-seed has always happened by then.
    fn turn_cue_in_play_read(&self) -> Option<NavigationCue> {
        let position = self.trip.position_mi;
        self.trip
            .navigation_cues
            .iter()
            .filter(|cue| {
                is_judged_turn(cue)
                    && !self.turn_resolved.contains(&cue.key)
                    && cue.at_mi - position >= -TURN_COMMIT_TAIL_MI
            })
            .min_by(|a, b| a.at_mi.total_cmp(&b.at_mi))
            .cloned()
    }

    /// `_turn_leg_index(cue)`.
    pub fn turn_leg_index(&self, cue: &NavigationCue) -> usize {
        cue.key
            .rsplit_once(':')
            .and_then(|(_, tail)| tail.parse::<usize>().ok())
            .unwrap_or(0)
    }

    /// `_turn_street_text(cue)`: the street being turned onto, in the world's
    /// own spoken name.
    pub fn turn_street_text(&self, cue: &NavigationCue) -> String {
        let index = self.turn_leg_index(cue);
        let legs = &self.trip.route.legs;
        if let Some(leg) = legs.get(index) {
            if !leg.highway.is_empty() {
                return leg.highway.clone();
            }
        }
        "the next street".to_string()
    }

    /// `_turn_speed_mph(cue)`: the speed the corner has to be taken under --
    /// the street's own posted limit, capped at what a trailer can turn,
    /// floored at the gate crawl so the gate stays the slowest thing on the
    /// route.
    pub fn turn_speed_mph(&self, cue: &NavigationCue) -> f64 {
        let index = self.turn_leg_index(cue);
        let posted = self
            .trip
            .route
            .legs
            .get(index)
            .map(|leg| leg.local_speed_mph)
            .unwrap_or(0.0);
        let street = if posted != 0.0 {
            posted
        } else {
            FACILITY_ACCESS_LIMIT_MPH
        };
        FACILITY_GATE_LIMIT_MPH.max(street.min(TURN_CORNER_MAX_MPH))
    }

    /// `_turn_window_mi()`: how far out the corner is called, and how far back
    /// a miss drops -- a full spoken window, so the retry is winnable.
    pub fn turn_window_mi(&self) -> f64 {
        let speed = self.trip.truck.speed_mph().max(TURN_CORNER_MAX_MPH);
        let miles = TURN_WARNING_REAL_S * speed * self.trip.effective_time_scale() / 3600.0;
        TURN_WINDOW_MIN_MI.max(miles.min(TURN_WINDOW_MAX_MI))
    }

    /// `_turn_grace_seconds(message)`: real reaction seconds after `message`,
    /// the ramp-arrival rule -- a corner is never failed while its own cue is
    /// still being spoken.
    pub fn turn_grace_seconds(&self, ctx: &GameContext, message: &str) -> f64 {
        let speech_rate = if ctx.settings.sapi_events && ctx.speech.event_supports_rate() {
            ctx.settings.speech_rate
        } else {
            0.0
        };
        ramp_arrival_grace_seconds(message, speech_rate)
    }

    /// `_turn_miss_suspended()`: something else owns the wheel -- a hazard
    /// swerve, a microsleep, a traffic stop, or an open arrival menu must
    /// never read as a miss.
    pub fn turn_miss_suspended(&self) -> bool {
        self.hazard_deadline.is_some()
            || self.microsleep_deadline.is_some()
            || self.pull_over.is_some()
            || self.arrival_menu_open
    }

    // -- spoken text ----------------------------------------------------------

    /// `_turn_approach_text(cue, ahead_mi)`: the approach call, in the pacenote
    /// grammar -- side, street, distance, advisory.
    ///
    /// Terse drops the advisory tail but keeps everything a driver needs to
    /// place the corner -- and always says the verb, because a bare "Right now"
    /// reads as a direction or as timing, never reliably one.
    pub fn turn_approach_text(
        &self,
        ctx: &GameContext,
        cue: &NavigationCue,
        ahead_mi: f64,
    ) -> String {
        let settings = &ctx.settings;
        let direction = cue.direction.trim().to_lowercase();
        let street = self.turn_street_text(cue);
        let target = settings.speed_text(self.turn_speed_mph(cue));
        let mut call = if ahead_mi <= TURN_NOW_MI {
            format!("Turn {direction} now onto {street}.")
        } else {
            let distance = settings.short_distance_text(ahead_mi);
            format!("{} turn onto {street}, {distance}.", capitalize(&direction))
        };
        if self.terse_speech(ctx) {
            return call;
        }
        call = format!("{call} Advise {target}.");
        if self.keeper_mph.is_some() && self.trip.truck.speed_mph() > self.turn_speed_mph(cue) {
            // The keeper sheds this corner's speed itself, so say so here
            // rather than as a second utterance on top of the corner call --
            // and so nobody reaches for the brake, which cancels the session.
            call = format!("{call} Speed keeper easing.");
        }
        call
    }

    // -- the frame ------------------------------------------------------------

    /// `_update_turn_commitment(dt)`: call the corner, hold the clock through
    /// it, judge it once.
    pub fn update_turn_commitment(&mut self, ctx: &mut GameContext, dt: f64) {
        let cue = self.turn_cue_in_play();
        if self.turn_grace_s > 0.0 {
            self.turn_grace_s = 0.0f64.max(self.turn_grace_s - dt);
        }
        let Some(cue) = cue else {
            self.trip.controlled_turn = false;
            return;
        };
        let ahead = cue.at_mi - self.trip.position_mi;
        if !self.turn_advised.contains(&cue.key) {
            if self.trip.truck.speed_mph() <= self.turn_speed_mph(&cue) {
                // Already slow enough to make it: the route's own maneuver cue
                // is the whole story, and an advisory a crawling truck cannot
                // fail is noise. The gate's speed warning works the same way.
                //
                // The CLOCK is a separate question, and conflating the two is
                // what made a downtown arrival unfollowable: this return used
                // to leave `controlled_turn` alone, so a truck held under
                // every corner's speed by the keeper took the whole chain at
                // full compression and heard four corners in fifteen real
                // seconds (owner, Spokane, 2026-08-21: "I missed the turn").
                // Being slow enough to MAKE a corner is not being given time
                // to HEAR about it, and the route's own maneuver cue -- the
                // whole story here, by the comment above -- still has to
                // arrive far enough ahead to be acted on.
                if ahead <= 0.0 {
                    self.resolve_turn(&cue);
                } else if ahead <= self.turn_window_mi() {
                    self.trip.controlled_turn = true;
                }
                return;
            }
            if ahead > self.turn_window_mi() {
                return;
            }
            // Either the window opened, or a resumed save arrived at the
            // corner cold. Both start the clock with the corner's own advice;
            // neither may latch a miss on first contact.
            self.turn_advised.insert(cue.key.clone());
            self.trip.controlled_turn = true;
            let message = self.turn_approach_text(ctx, &cue, 0.0f64.max(ahead));
            self.turn_grace_s = self.turn_grace_seconds(ctx, &message);
            if let Some(sound) = local_turn_sound(Some(&cue.direction)) {
                let pan = if cue.direction == "left" {
                    -TURN_CUE_PAN
                } else {
                    TURN_CUE_PAN
                };
                ctx.audio.play_with(sound, 1.0, pan);
            }
            // A LEAD is deliberately left on the droppable ambient default,
            // unlike the act-now navigation calls raised to ROUTE alongside
            // it: a quarter-mile warning that survives to be spoken AFTER the
            // turn has been missed is worse than one that never arrives
            // (test_missed_turn_speaks_at_urgent_only caught exactly that, the
            // stale cue landing on top of the miss announcement). Going stale
            // is the correct end for a lead.
            //
            // A call that already says "now" is not a lead. It is the only
            // instruction the driver gets for a corner they are already at --
            // a cold arrival, or a loop-back onto a corner closer to the start
            // of the street chain than one spoken window -- and dropped as
            // stale it leaves the driver with nothing: "Turn right now onto
            // West Main Avenue" was dropped twice on one arrival and never
            // once heard (owner, Spokane, 2026-08-22). ROUTE, like the
            // trip's own near call.
            if 0.0f64.max(ahead) <= TURN_NOW_MI {
                ctx.say_event_with(
                    message,
                    SayEvent::queued()
                        .priority(EventPriority::Route)
                        .category(SpeechCategory::Navigation),
                );
            } else {
                ctx.say_event_with(
                    message,
                    SayEvent::queued().category(SpeechCategory::Navigation),
                );
            }
            return;
        }
        if ahead > 0.0 {
            return;
        }
        if self.turn_grace_s > 0.0 {
            return; // the corner's own cue is still speaking
        }
        if self.turn_miss_suspended() {
            self.resolve_turn(&cue);
            return;
        }
        if self.trip.truck.speed_mph() > self.turn_speed_mph(&cue) + TURN_SPEED_MARGIN_MPH {
            self.handle_missed_turn(ctx, &cue);
        } else {
            self.resolve_turn(&cue);
        }
    }

    /// `_resolve_turn(cue)`: this corner is settled; the clock goes back to
    /// trip pacing.
    pub fn resolve_turn(&mut self, cue: &NavigationCue) {
        self.turn_resolved.insert(cue.key.clone());
        self.turn_grace_s = 0.0;
        self.trip.controlled_turn = false;
    }

    /// `_reposition_for_turn(cue)`: drop back a full spoken window onto the
    /// approach, and clear every say-once latch the re-approach has to speak
    /// through again.
    pub fn reposition_for_turn(&mut self, cue: &NavigationCue) {
        let mut floor: f64 = 0.0;
        for other in &self.trip.navigation_cues {
            if is_judged_turn(other) && other.at_mi < cue.at_mi {
                floor = floor.max(other.at_mi + TURN_COMMIT_TAIL_MI);
            }
        }
        self.trip.position_mi = floor.max(cue.at_mi - self.turn_window_mi());
        self.turn_advised.remove(&cue.key);
        self.turn_grace_s = 0.0;
        self.trip.controlled_turn = false;
        // The trip's own GPS maneuver announcements latch per cue key; without
        // this the loop-back would run in silence (the missed-exit lesson).
        self.trip
            .announced_navigation
            .remove(&format!("{}:advance", cue.key));
        self.trip
            .announced_navigation
            .remove(&format!("{}:near", cue.key));
    }

    /// `_handle_missed_turn(cue)`: the scripted loop-back, or the corner
    /// completed for the player.
    pub fn handle_missed_turn(&mut self, ctx: &mut GameContext, cue: &NavigationCue) {
        self.turn_miss_count += 1;
        self.trip.game_minutes += TURN_MISS_LOOP_MIN;
        // The loop-back drops the controllers but keeps the session armed:
        // on a facility approach the keeper manages the corners, and after
        // the turnaround or the auto-turn it resumes on its own instead of
        // leaving the truck idling off the corner (owner ruling, 2026-09-01;
        // disarming here is what did that on the first agent drives).
        self.cancel_cruise(ctx, true);
        self.cancel_keeper(ctx, true);
        let terse = self.terse_speech(ctx);
        let street = self.turn_street_text(cue);
        let target = ctx.settings.speed_text(self.turn_speed_mph(cue));
        // One loop-back per corner, and never a fourth miss on one run: a
        // route must never become unfinishable. The time is still charged.
        let completed = self.turn_missed.contains(&cue.key) || self.turn_miss_count >= 3;
        let core = if terse {
            "Missed the turn.".to_string()
        } else {
            format!("You missed the turn onto {street}.")
        };
        let (tail, status): (String, &str) = if completed {
            self.resolve_turn(cue);
            self.trip.position_mi = self.trip.position_mi.max(cue.at_mi + TURN_COMMIT_TAIL_MI);
            let tail = if terse {
                "Turn made for you.".to_string()
            } else {
                format!(
                    "The turn is made for you and you are on {street}. The clock is still running."
                )
            };
            (tail, "Turn missed again. The turn was made for you.")
        } else {
            self.turn_missed.insert(cue.key.clone());
            self.reposition_for_turn(cue);
            let tail = if terse {
                "Safe turnaround. Turn ahead again.".to_string()
            } else {
                "You continue to the next safe turnaround and loop back onto the approach. The \
                 turn is ahead again."
                    .to_string()
            };
            (tail, "Missed the turn. Use the next safe turnaround.")
        };
        let mut message = format!("{core} {tail}");
        if self.turn_miss_count >= 2 {
            // The identical core line keeps the flow predictable by ear; a
            // repeat miss earns help, not scolding.
            message += &format!(
                " Brake to {target} with {} on the approach.",
                ctx.control_hint("brake")
            );
        }
        ctx.audio.play("ui/warning");
        self.set_status(status);
        // A mandatory turn on the route, not an optional stop: names the
        // loop-back (or the auto-turn) that still delivers the load, so it
        // must survive quiet/urgent_only as words, not an earcon blip.
        ctx.say_event_with(
            message,
            SayEvent::new().category(SpeechCategory::Navigation),
        );
    }

    // -- the pursuit guide ----------------------------------------------------

    /// `_maneuver_steer_demand(connector=None)`: signed steer for the maneuvers
    /// that carry no mainline curve record.
    ///
    /// Connector arcs are excluded from the curve PUSH and from the pacenotes
    /// on purpose (ramps carry their own speech), and street legs carry baked
    /// maneuvers instead of curve geometry. Excluding them from the GUIDE as
    /// well silenced the panned road bed -- the only continuous directional
    /// audio the game has -- through every exit ramp and every turn, which is
    /// exactly where a blind driver needs it. This feeds the existing bed a
    /// synthetic demand; it never adds a tone (`sim::lane_guidance`).
    pub fn maneuver_steer_demand(&self, connector: Option<&RouteCurve>) -> f64 {
        if let Some(connector) = connector {
            let tightness = 0.2f64.max(1.0 - connector.min_radius_ft as f64 / 5000.0);
            let excess = 0.0f64.max(self.trip.truck.speed_mph() - connector.advisory_mph as f64);
            let magnitude = 1.0f64.min(tightness * (1.0 + excess * 0.04));
            return if connector.direction == 'L' {
                -magnitude
            } else {
                magnitude
            };
        }
        if self.ramp_mi.is_some() {
            return RAMP_GUIDE_DEMAND;
        }
        let Some(cue) = self.turn_cue_in_play_read() else {
            return 0.0;
        };
        let ahead = cue.at_mi - self.trip.position_mi;
        if ahead > TURN_GUIDE_LEAD_MI {
            return 0.0;
        }
        let magnitude = if ahead <= 0.0 {
            TURN_GUIDE_DEMAND
        } else {
            TURN_GUIDE_DEMAND * (1.0 - ahead / TURN_GUIDE_LEAD_MI)
        };
        if cue.direction.to_lowercase() == "left" {
            -magnitude
        } else {
            magnitude
        }
    }
}

/// Python's `str.capitalize()`: first character upper, the rest lower.
fn capitalize(text: &str) -> String {
    let mut chars = text.chars();
    match chars.next() {
        None => String::new(),
        Some(first) => first.to_uppercase().collect::<String>() + &chars.as_str().to_lowercase(),
    }
}
