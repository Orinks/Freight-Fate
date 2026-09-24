//! The lights and signs on a facility's streets.
//!
//! The street bake reads the signals, stop signs, all-way stops and yields OSM
//! maps at each intersection a chain passes (`Trip::street_controls_between`).
//! Each is played through the ramp terminal's own machinery, not a copy of
//! it: the light's fixed-time cycle and its spoken phases, the cross-traffic
//! bubble, the stop bar's countdown and tick, the stop and yield rules,
//! route-transition assistance braking for a red or a sign and holding the
//! stop, and facility stopping assistance driving on from it with the speed
//! keeper. The two files that own all that (`ramp_terminal.rs`,
//! `ramp_crossing.rs`) read the live stop bar through `terminal_gap_mi`, and
//! this file puts a street's bar there.
//!
//! What differs on a street is only what a ramp terminal always is and a
//! street intersection is not: a turn. A green is driven at the street's own
//! speed, not rolled at the ramp's twenty, and crossing it says nothing; a
//! corner at a control keeps its own call and its own speed. An intersection
//! OSM holds no control for has none here -- unknown, never rolled for.

use ff_core::pyrandom::PyRandom;
use ff_core::sim::cross_traffic::{CROSSROAD_WIDTH_FT, YIELD_LINE_TO_CROSSROAD_FT};

use crate::app::GameContext;
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;
use crate::states::driving_speed_control::{KEEPER_EASE_REAL_S, KEEPER_SETTLE_REAL_S};

/// Where a street's stop bar stands short of the intersection node OSM maps
/// (the middle of the crossroad): the stop line's setback from the crossroad
/// edge plus half the crossroad, the two numbers the yield rule already uses
/// (MUTCD 11th ed. 3B.19's 4 to 30 ft, assumed at its middle; two 12 ft
/// lanes, assumed). DERIVED from those two.
pub const STREET_BAR_BEFORE_NODE_MI: f64 =
    (YIELD_LINE_TO_CROSSROAD_FT + CROSSROAD_WIDTH_FT / 2.0) / 5280.0;
/// A control this close to the start of a chain is the corner the ramp's own
/// terminal already played: the chain starts at that node.
pub const STREET_CONTROL_START_SKIP_MI: f64 = 0.02;

impl DrivingState {
    /// Whether a stop bar is live: a ramp terminal, or a street control.
    pub fn terminal_live(&self) -> bool {
        self.ramp_mi.is_some() || self.street_bar_mi.is_some()
    }

    /// How far the live stop bar is ahead, negative once past it.
    pub fn terminal_gap_mi(&self) -> Option<f64> {
        if let Some(ramp_mi) = self.ramp_mi {
            return Some(ramp_mi - RAMP_ACCESS_MI);
        }
        self.street_bar_mi.map(|bar| bar - self.trip.position_mi)
    }

    /// The live control is a street's, not a ramp's.
    pub fn on_street_control(&self) -> bool {
        self.ramp_mi.is_none() && self.street_bar_mi.is_some()
    }

    /// Where the live control is, in the collision and citation lines: " at
    /// the ramp end" for a ramp, nothing for a street, whose turn-by-turn
    /// already said where the truck is.
    pub fn terminal_where(&self) -> &'static str {
        if self.on_street_control() {
            ""
        } else {
            " at the ramp end"
        }
    }

    /// The mile a terminal's crossroad and its citation dice are seeded by.
    pub fn terminal_seed_mi(&self) -> f64 {
        if let Some(stop) = self.ramp_stop.as_ref() {
            return stop.at_mi;
        }
        self.street_bar_mi.unwrap_or(self.trip.position_mi)
    }

    /// Whether the live bar owes the truck a stop now: a red, a yellow short
    /// of the bar, a sign, or a yield with no gap. The bar's countdown and
    /// tick exist for that. A ramp always has one to make; a street's green,
    /// driven at the street's own speed, is not a stop and hears neither.
    pub fn bar_cues_owed(&self) -> bool {
        if !self.on_street_control() {
            return true;
        }
        match self.ramp_control.as_str() {
            "signal" => {
                let phase = self.ramp_light_phase();
                phase == "red"
                    || (phase == "yellow" && self.terminal_gap_mi().is_some_and(|gap| gap > 0.0))
            }
            "yield" => !self.yield_gap_clear(),
            _ => true,
        }
    }

    /// Road the truck needs to stop at a street's bar from where it is: the
    /// reaction seconds and the shed, on the real clock -- the gate's brake
    /// point, for a bar.
    fn street_bar_brake_point_mi(&self) -> f64 {
        let speed = self.trip.truck.speed_mph().max(1.0);
        let reaction_mi = (KEEPER_EASE_REAL_S + KEEPER_SETTLE_REAL_S) * speed / 3600.0;
        reaction_mi + self.keeper_shed_mi(0.0, 1.0)
    }

    /// How far out a street control is named: the ramp's own callout
    /// distance to its bar, or the brake point when that is further.
    fn street_control_call_mi(&self) -> f64 {
        (RAMP_CONTROL_ANNOUNCE_MI - RAMP_ACCESS_MI).max(self.street_bar_brake_point_mi())
    }

    /// Whether the clock runs real for a street control: from the call, only
    /// while it owes a stop. A green is driven on the trip's own pacing, and
    /// the light cycles in real seconds either way.
    pub fn street_control_on_real_time(&self) -> bool {
        let Some(gap) = self.terminal_gap_mi().filter(|_| self.on_street_control()) else {
            return false;
        };
        !self.ramp_terminal_done
            && (self.ramp_waiting_at_light
                || self.ramp_waiting_at_sign
                || (gap <= self.street_control_call_mi() && self.bar_cues_owed()))
    }

    fn street_controls_apply(&self) -> bool {
        self.ramp_mi.is_none()
            && !self.trip.outbound
            && !self.trip.finished
            && self.trip.has_street_detail()
    }

    /// Per frame, on a facility chain: name the next light or sign, work the
    /// pedals for it, judge the crossing, and hand the streets back.
    pub fn update_street_controls(&mut self, ctx: &mut GameContext, accelerating: bool) {
        if self.street_controls_trip != self.trip_generation {
            // A new trip is a new route: its bars are not this one's.
            self.street_controls_trip = self.trip_generation;
            self.street_controls_played.clear();
            if self.street_bar_mi.is_some() {
                self.end_street_control(ctx);
            }
        }
        if !self.street_controls_apply() {
            if self.street_bar_mi.is_some() {
                self.end_street_control(ctx);
            }
            return;
        }
        if self.street_bar_mi.is_none() && !self.arm_next_street_control() {
            return;
        }
        let Some(gap_mi) = self.terminal_gap_mi() else {
            return;
        };
        if !self.ramp_light_announced && gap_mi <= self.street_control_call_mi() {
            self.announce_street_control(ctx);
        }
        self.update_ramp_terminal_assist_with_input(ctx, accelerating);
        if !self.ramp_terminal_done && gap_mi <= 0.0 {
            self.update_ramp_terminal(ctx);
        }
        if self.ramp_terminal_done {
            self.finish_street_control(ctx);
        }
    }

    /// Put the next unplayed control within the call distance on the bar.
    fn arm_next_street_control(&mut self) -> bool {
        let position = self.trip.position_mi;
        let reach = position + self.street_control_call_mi() + STREET_BAR_BEFORE_NODE_MI;
        let next = self
            .trip
            .street_controls_between(STREET_CONTROL_START_SKIP_MI, reach)
            .into_iter()
            .map(|(node_mi, kind)| (node_mi, kind.to_string()))
            .find(|(node_mi, _)| {
                node_mi - STREET_BAR_BEFORE_NODE_MI > position
                    && !self
                        .street_controls_played
                        .contains(&street_control_key(*node_mi))
            });
        let Some((node_mi, kind)) = next else {
            return false;
        };
        let bar_mi = node_mi - STREET_BAR_BEFORE_NODE_MI;
        let control = match kind.as_str() {
            "signal" => "signal",
            "give_way" => "yield",
            _ => "stop", // "stop" facing the truck, and "all_way_stop"
        };
        // Seeded by the intersection, like a ramp's by its exit: the same
        // corner carries the same timing plan and the same traffic day.
        let key = street_control_key(node_mi);
        let mut rng = PyRandom::new_from_i64((self.trip_seed << 16) ^ key ^ 0x57EE7);
        let timing_key = format!(
            "street-light|{}|{}|{node_mi:.3}",
            self.trip.route.cities.first().map_or("", String::as_str),
            self.street_under_the_wheels(),
        );
        // At an all-way stop the cross street stops too: the truck's turn
        // comes after its own stop, with no gap to wait for.
        let cross_traffic = kind != "all_way_stop";
        self.begin_terminal_control(
            control.to_string(),
            &mut rng,
            &timing_key,
            node_mi,
            cross_traffic,
        );
        self.street_bar_mi = Some(bar_mi);
        self.street_control_kind = kind;
        true
    }

    /// The call for a street control, on the route channel like the ramp's.
    fn announce_street_control(&mut self, ctx: &mut GameContext) {
        self.ramp_light_announced = true;
        let message = match self.street_control_kind.as_str() {
            "signal" => {
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
                format!("Traffic light ahead. Light {phase}.")
            }
            kind => {
                ctx.audio.play_with("ui/notify", 0.7, 0.0);
                match kind {
                    "all_way_stop" => "All-way stop ahead.",
                    "give_way" => "Yield sign ahead.",
                    _ => "Stop sign ahead.",
                }
                .to_string()
            }
        };
        self.say_route_navigation(ctx, &message);
        // A countdown mark already behind the truck when the call lands is
        // not a distance that is true (the ramp's rule).
        if let Some(gap_mi) = self.terminal_gap_mi() {
            let unit_mi = if ctx.settings.imperial_units {
                1.0 / 5280.0
            } else {
                1.0 / 1609.344
            };
            for mark in self.ramp_bar_milestones(ctx) {
                if gap_mi < mark as f64 * unit_mi {
                    self.ramp_gap_milestones_said.insert(mark);
                }
            }
        }
    }

    /// The release line after a stop at a street's light or sign.
    ///
    /// With facility stopping assistance and the speed keeper on, the keeper
    /// drives on from the bar, hands off (owner ruling, 2026-09-01: signal to
    /// entrance); otherwise pulling away is the driver's.
    pub(crate) fn street_release_text(
        &mut self,
        ctx: &GameContext,
        lead: &str,
        clear: bool,
    ) -> String {
        if self.approach_pull_ahead_available(ctx) {
            self.approach_pull_ahead = true;
            let clear = if clear { " Clear." } else { "" };
            return format!("{lead}{clear} Speed keeper pulling ahead.");
        }
        if clear {
            format!("{lead} Clear; pull ahead.")
        } else {
            lead.to_string()
        }
    }

    /// The control is honored or run: mark it played, hand the streets back,
    /// and let the keeper drive on when the release promised it.
    fn finish_street_control(&mut self, ctx: &mut GameContext) {
        let pull_ahead = std::mem::take(&mut self.approach_pull_ahead);
        self.end_street_control(ctx);
        if !pull_ahead || !ctx.settings.speed_keeper || self.keeper_mph.is_some() {
            return;
        }
        let (limit, zone_reason) = self.trip.speed_limit_at(self.trip.position_mi);
        let Some(zone_reason) = zone_reason else {
            return;
        };
        // The stop the assist paused the session for is over; the keeper
        // takes the street from a standstill, the way it takes the first one
        // off the ramp (`begin_surface_chain`).
        self.clear_stop_pause();
        if self.cruise_mph.is_some() {
            self.cancel_cruise(ctx, true);
        }
        self.engage_keeper(ctx, limit, &zone_reason, Some(limit), false);
    }

    /// Take the street control off the bar, played.
    fn end_street_control(&mut self, ctx: &mut GameContext) {
        if let Some(bar_mi) = self.street_bar_mi.take() {
            self.street_controls_played
                .insert(street_control_key(bar_mi + STREET_BAR_BEFORE_NODE_MI));
        }
        self.street_control_kind.clear();
        self.ramp_control.clear();
        self.ramp_terminal_done = true;
        self.ramp_waiting_at_light = false;
        self.ramp_waiting_at_sign = false;
        self.ramp_assist_brake = 0.0;
        self.cross_bubble = None;
        self.set_bar_solid(ctx, false);
    }
}

/// A street control's identity on its route: the intersection's mile, to the
/// thousandth.
fn street_control_key(node_mi: f64) -> i64 {
    (node_mi * 1000.0).round() as i64
}
