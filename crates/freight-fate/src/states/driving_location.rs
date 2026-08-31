//! Current-location details for the on-demand route report (port of
//! `freight_fate/states/driving_location.py`, the `DrivingLocationMixin`).

use std::sync::Arc;

use ff_core::data::world_models::{Landmark, Leg};
use ff_core::sim::trip::spoken_short_miles;
use ff_core::sim::trip_models::leg_state_at;
use ff_core::sim::trip_route_helpers::leg_heading;
use ff_core::units::{spoken_feet_or_meters, MILES_TO_KM};

use crate::app::GameContext;
use crate::states::driving::DrivingState;
use crate::states::driving_core::DRIVE_PHASE_PICKUP;

/// Where the quarter-mile ladder runs out of anything honest to say: its own
/// floor is "a quarter mile", which at 200 feet from the gate overstates the
/// gap six times over. Below these the answer is feet, or metres where the
/// 100-metre ladder bottoms out.
pub const CLOSING_FEET_MI: f64 = 0.125;
pub const CLOSING_METERS_KM: f64 = 0.15;

/// A town this close to the road, and this close along it, is the town the
/// truck is in rather than one it can see: the baked villages sit within a
/// few hundred feet of the corridor when the highway runs straight through.
pub const IN_TOWN_OFF_MI: f64 = 1.0;
pub const IN_TOWN_ALONG_MI: f64 = 1.5;
/// Past this there is no town worth naming. The bake keeps places out to
/// eleven miles off an empty interstate on purpose, so the window is wide;
/// beyond it "no town near here" is the more useful answer than a name the
/// driver could not reach.
pub const NEAREST_TOWN_MI: f64 = 30.0;

/// `spoken_closing_distance(miles, imperial)`: how far to something still
/// ahead, worded so it is never zero.
///
/// `Trip::distance_text` rounds to whole units, so anything under half a
/// mile spoke as "0 miles" -- and on surface streets at 25 mph the last half
/// mile takes over a minute, all of it spent hearing that the gate is zero
/// miles away (owner report, 2026-08-15). Quarter-mile steps take over under
/// a mile and a bit, feet or metres under a quarter mile: the same ladder
/// the pacenotes and the stop-bar countdown already speak.
pub fn spoken_closing_distance(miles: f64, imperial: bool) -> String {
    let miles = 0.0f64.max(miles);
    let short = if imperial {
        miles < CLOSING_FEET_MI
    } else {
        miles * MILES_TO_KM < CLOSING_METERS_KM
    };
    if short {
        return spoken_feet_or_meters(miles, imperial);
    }
    spoken_short_miles(miles, imperial)
}

/// `_highway_frame()`'s answer: the leg under the wheels, the city it is
/// driven from, the city it runs toward, and the truck's offset in the leg's
/// own native frame.
pub struct HighwayFrame {
    pub leg: Arc<Leg>,
    pub from_city: String,
    pub toward_city: String,
    pub native_offset: f64,
}

impl DrivingState {
    /// `_speak_route_status()`.
    pub fn speak_route_status(&mut self, ctx: &mut GameContext) {
        // Deliberately short: how far along you are, how far to the thing you
        // are actually driving at, and where you are. Grade, zones, and the
        // next maneuver each have their own key, so repeating them here just
        // made drivers wait through a paragraph to hear where they were.
        //
        // Once the trip has ended at a facility gate, the leg readout below
        // would recite the abandoned route with a frozen countdown -- "3
        // miles remaining" that never move (playtest 2026-07-22). The only
        // honest route status left is the gate.
        if let Some(gate) = self.arrival_gate_query_text(ctx) {
            ctx.say(&format!("Route status: you have arrived. {gate}"));
            return;
        }
        // On the facility approach, the highway framing is a lie: the driver
        // heard "on I-90 West, 3 miles remaining" with a frozen countdown
        // while rolling city streets toward the gate (playtest 2026-07-22).
        // Both approach shapes answer with the gate distance instead.
        if self.surface_chain {
            let target = format!("the gate at {}", self.approach_facility_text(ctx));
            self.say_local_status(ctx, &target, None, None);
            return;
        }
        if self.destination_exit_taken {
            let target = self.approach_facility_text(ctx);
            // The ramp's own countdown, never the frozen mainline remainder.
            let ramp_left = self.ramp_mi;
            self.say_local_status(
                ctx,
                &target,
                Some("off the highway, on the facility approach"),
                ramp_left,
            );
            return;
        }
        // Pulling out of the origin gate is city streets too, and the highway
        // readout below was just as wrong there: it read the two-mile street
        // chain's percent as the run's progress and pointed the driver
        // "toward" the city they were standing in (owner report, 2026-08-15).
        // What is actually ahead on that chain is the on-ramp.
        if self.departure_chain {
            let target = self.departure_ramp_text();
            self.say_local_status(ctx, &target, None, None);
            return;
        }
        // The pickup drive is a local approach from end to end -- there is no
        // highway leg under it to frame, and its route starts and ends in the
        // one city, so "toward" it says nothing.
        if self.trip.is_facility_approach_route() {
            let target = format!("the gate at {}", self.approach_facility_text(ctx));
            self.say_local_status(ctx, &target, None, None);
            return;
        }
        let (leg_index, leg_start) = self.trip.leg_at_mile(self.trip.position_mi);
        let leg = self.trip.route.legs[leg_index].clone();
        let from_city = self.trip.route.cities[leg_index].clone();
        let toward_city = self.trip.route.cities[leg_index + 1].clone();
        let forward = from_city == leg.a;
        let leg_offset = 0.0f64.max(leg.miles.min(self.trip.position_mi - leg_start));
        let native_offset = if forward {
            leg_offset
        } else {
            leg.miles - leg_offset
        };

        let heading = leg_heading(ctx.world, &leg.highway, &from_city, &toward_city);
        let road = format!("{} {heading}", leg.highway).trim().to_string();
        let state = {
            let read = leg_state_at(&leg, native_offset);
            if read.is_empty() {
                city_state(ctx, &toward_city)
            } else {
                read
            }
        };
        let toward = ctx.world.spoken_city(&toward_city, Some(true));

        // Progress leads so a one-line braille display gets it without panning,
        // and the percent is the same figure the online drivers board shows.
        // A planned stop is the next place you actually mean to be, so it takes
        // the distance slot from the destination until you have passed it.
        let planned = self
            .trip
            .planned_stop()
            .filter(|stop| stop.at_mi > self.trip.position_mi)
            .map(|stop| (stop.at_mi, stop.spoken_name()));
        let lead = match planned {
            Some((at_mi, spoken_name)) => {
                let ahead = self.closing_text(at_mi - self.trip.position_mi);
                format!(
                    "{} percent there, {ahead} to {spoken_name}.",
                    self.trip.progress_percent()
                )
            }
            None => format!(
                "{} percent there, {} left.",
                self.trip.progress_percent(),
                self.closing_text(self.trip.remaining_miles())
            ),
        };
        ctx.say(&format!("{lead} On {road} in {state}, toward {toward}."));
    }

    // --- One fact per key (Tim K., 2026-08-16) -------------------------
    //
    // R answers all of this in one sentence, which is the right shape when
    // you are orienting yourself and the wrong one when you want a single
    // fact at 65 miles an hour: you sit through the progress, the road and
    // the destination to hear the state. These four keys each speak one
    // thing and stop, so they are cheap to press twice and cheap to press
    // by mistake. They read the same data R does -- there is no second
    // source of truth for where the truck is.

    /// `_local_route_city()`: the city a street route runs inside, or the
    /// run's destination.
    pub fn local_route_city(&self) -> String {
        self.trip.route.cities.first().cloned().unwrap_or_default()
    }

    /// `_on_local_streets()`: whether the truck is on a street chain rather
    /// than a highway leg.
    pub fn on_local_streets(&self) -> bool {
        self.surface_chain
            || self.departure_chain
            || self.destination_exit_taken
            || self.trip.is_facility_approach_route()
    }

    /// `_highway_frame()`: the leg under the wheels and where the truck sits
    /// in its native frame.
    ///
    /// None on a street chain or a route with no legs -- the callers each have
    /// their own honest answer for that case rather than a shared fallback
    /// sentence.
    pub fn highway_frame(&self) -> Option<HighwayFrame> {
        if self.on_local_streets() || self.trip.route.legs.is_empty() {
            return None;
        }
        let (leg_index, leg_start) = self.trip.leg_at_mile(self.trip.position_mi);
        let leg = self.trip.route.legs[leg_index].clone();
        let from_city = self.trip.route.cities[leg_index].clone();
        let toward_city = self.trip.route.cities[leg_index + 1].clone();
        let forward = from_city == leg.a;
        let leg_offset = 0.0f64.max(leg.miles.min(self.trip.position_mi - leg_start));
        let native_offset = if forward {
            leg_offset
        } else {
            leg.miles - leg_offset
        };
        Some(HighwayFrame {
            leg,
            from_city,
            toward_city,
            native_offset,
        })
    }

    /// `_speak_current_state()`: Alt+1, the state the truck is in, and nothing
    /// else.
    pub fn speak_current_state(&mut self, ctx: &mut GameContext) {
        let state = match self.highway_frame() {
            None => {
                let city = self.local_route_city();
                city_state(ctx, &city)
            }
            Some(frame) => {
                let read = leg_state_at(&frame.leg, frame.native_offset);
                if read.is_empty() {
                    city_state(ctx, &frame.toward_city)
                } else {
                    read
                }
            }
        };
        if state.is_empty() {
            ctx.say("No state known here.");
        } else {
            ctx.say(&format!("In {state}."));
        }
    }

    /// `_speak_current_road()`: Alt+2, the road under the wheels, signed the
    /// way you would read it.
    ///
    /// On a street chain this is the street name, which is what "the road you
    /// are on" means there; where the approach has only generic access-road
    /// geometry there is no name to speak and saying so beats inventing one.
    pub fn speak_current_road(&mut self, ctx: &mut GameContext) {
        let Some(frame) = self.highway_frame() else {
            let street = self.street_under_the_wheels();
            if street.is_empty() {
                ctx.say("On the facility approach. No road name.");
            } else {
                ctx.say(&format!("On {street}."));
            }
            return;
        };
        let heading = leg_heading(
            ctx.world,
            &frame.leg.highway,
            &frame.from_city,
            &frame.toward_city,
        );
        let road = format!("{} {heading}", frame.leg.highway)
            .trim()
            .to_string();
        if road.is_empty() {
            ctx.say("No road name here.");
        } else {
            ctx.say(&format!("On {road}."));
        }
    }

    /// `_speak_current_town()`: Alt+3, the town the truck is in, or the
    /// nearest one worth naming.
    ///
    /// The villages baked along each leg carry how far off the corridor they
    /// sit, which is what separates "you are in Pine" from "Fairfield is six
    /// miles off to your right" -- and the honest answer on an empty stretch
    /// is that there is no town, said out loud rather than left as silence.
    pub fn speak_current_town(&mut self, ctx: &mut GameContext) {
        let Some(frame) = self.highway_frame() else {
            let city = self.local_route_city();
            let spoken = if city.is_empty() {
                String::new()
            } else {
                ctx.world.spoken_city(&city, Some(true))
            };
            if spoken.is_empty() {
                ctx.say("No town known here.");
            } else {
                ctx.say(&format!("In {spoken}."));
            }
            return;
        };
        let forward = frame.from_city == frame.leg.a;
        // Ranked by how far the town actually is, not by how far along the
        // road it sits: a place 200 feet ahead and five miles off is further
        // away than one two miles up the road and right on it, and "nearest"
        // has to mean nearest.
        let mut nearest: Option<(f64, f64, Landmark)> = None;
        for landmark in frame.leg.landmarks() {
            if landmark.category != "village" {
                continue;
            }
            let along = landmark.at_mi - frame.native_offset;
            let away = (along.powi(2) + landmark.off_mi.powi(2)).sqrt();
            if nearest.as_ref().is_none_or(|found| away < found.0) {
                nearest = Some((away, along, landmark.clone()));
            }
        }
        let Some((away, along, landmark)) = nearest else {
            ctx.say("No town near here.");
            return;
        };
        if away > NEAREST_TOWN_MI {
            ctx.say("No town near here.");
            return;
        }
        let off_road = landmark.off_mi;
        if along.abs() <= IN_TOWN_ALONG_MI && off_road <= IN_TOWN_OFF_MI {
            ctx.say(&format!("In {}.", landmark.name));
            return;
        }
        let off = if off_road >= 0.1 {
            format!("{} off the road", self.closing_text(off_road))
        } else {
            String::new()
        };
        let where_text = if along.abs() <= IN_TOWN_ALONG_MI {
            // Level with it: "two miles ahead" would be a distance the driver
            // covers in seconds and then still not be there.
            if off.is_empty() {
                "right beside the road".to_string()
            } else {
                off
            }
        } else {
            // Ahead or behind is read in the direction of travel, not the
            // leg's native frame: on a leg driven b-to-a those are opposites,
            // and the word has to match the mirror.
            let past = if forward { along < 0.0 } else { along > 0.0 };
            let mut where_text = format!(
                "{} {}",
                self.closing_text(along.abs()),
                if past { "back" } else { "ahead" }
            );
            if !off.is_empty() {
                where_text = format!("{where_text}, {off}");
            }
            where_text
        };
        ctx.say(&format!("Nearest town, {}: {where_text}.", landmark.name));
    }

    /// `_speak_current_direction()`: Alt+4, the direction of travel, worded the
    /// way the shields are.
    ///
    /// The signed direction, not a compass bearing: I-95 out of New York is
    /// signed South while the geometry trends southwest, and the driver is
    /// placing themselves against the signs. A street chain has no signed
    /// direction at all, and saying so is better than rounding one up.
    pub fn speak_current_direction(&mut self, ctx: &mut GameContext) {
        let Some(frame) = self.highway_frame() else {
            ctx.say("On city streets. No signed direction here.");
            return;
        };
        let heading = leg_heading(
            ctx.world,
            &frame.leg.highway,
            &frame.from_city,
            &frame.toward_city,
        );
        if heading.is_empty() {
            ctx.say("No signed direction here.");
        } else {
            ctx.say(&format!("{heading}bound."));
        }
    }

    /// `_say_local_status(target, where=None)`: one route report for a local
    /// street route -- where the truck is, what it is actually driving at, and
    /// the next maneuver if one is left. Sentences that come up empty are
    /// dropped rather than spoken as a gap.
    ///
    /// `distance_mi` overrides the spoken closing distance; `None` reads the
    /// trip's remaining miles. The override exists because the mainline
    /// odometer FREEZES once the destination exit is taken (the ramp
    /// consumes the movement instead), so that branch must speak the ramp's
    /// own countdown -- Tim heard "4 miles to go" four times over a minute,
    /// the last one three seconds after he was already at the gate, and
    /// braked hard for it (tester report, 2026-08-30).
    pub fn say_local_status(
        &mut self,
        ctx: &mut GameContext,
        target: &str,
        where_: Option<&str>,
        distance_mi: Option<f64>,
    ) {
        // No next-maneuver clause. On streets the event voice announces every
        // turn as it arrives, so including it here meant R re-read, on the
        // screen reader, the line the event voice had just delivered (owner,
        // 2026-08-17). The highway readout above dropped the maneuver for
        // exactly this reason and said so in its own comment; the street
        // readout kept it, and that inconsistency is the bug.
        let where_text = match where_ {
            Some(where_) => where_.to_string(),
            None => self.local_where_text(ctx),
        };
        let distance = distance_mi.unwrap_or_else(|| self.trip.remaining_miles());
        let parts = [
            format!("Route status: {where_text}."),
            format!("{} to {target}.", self.closing_text(distance.max(0.0))),
        ];
        let line = parts
            .iter()
            .filter(|part| !part.is_empty())
            .cloned()
            .collect::<Vec<_>>()
            .join(" ");
        ctx.say(&line);
    }

    /// `_closing_text(miles)`: a distance to something the truck has not
    /// reached yet.
    pub fn closing_text(&self, miles: f64) -> String {
        spoken_closing_distance(miles, self.trip.imperial())
    }

    /// `_street_under_the_wheels()`: the road the truck is on right now, when
    /// that road is a street.
    ///
    /// Read at the truck's own position rather than off the chain's first
    /// leg, so a report taken three turns in names the street being driven
    /// and not the one the chain started on. Empty on a route with no baked
    /// street geometry -- a synthetic one-leg approach has only the generic
    /// "facility access road", which is not a street name and must not be
    /// spoken as one.
    pub fn street_under_the_wheels(&self) -> String {
        if self.trip.route.legs.is_empty() {
            return String::new();
        }
        let (leg_index, _) = self.trip.leg_at_mile(self.trip.position_mi);
        let leg = &self.trip.route.legs[leg_index];
        if leg.local_speed_mph <= 0.0 && leg.local_cue.is_empty() {
            return String::new();
        }
        leg.highway.clone()
    }

    /// `_local_where_text()`: where the truck is on a local street route,
    /// spoken.
    pub fn local_where_text(&self, ctx: &GameContext) -> String {
        let city = ctx
            .world
            .spoken_city(&self.trip.route.cities[0], Some(true));
        let street = self.street_under_the_wheels();
        if !street.is_empty() {
            return format!("on city streets, {street}, in {city}");
        }
        format!("on the facility approach in {city}")
    }

    /// `_departure_ramp_text()`: what the departure chain is actually driving
    /// at -- its on-ramp.
    ///
    /// Named the same way the chain's own opening line names it, so the two
    /// do not read as two different places.
    pub fn departure_ramp_text(&self) -> String {
        let first = self
            .highway_trip
            .as_ref()
            .and_then(|trip| trip.route.legs.first());
        match first {
            Some(leg) => format!("the {} on-ramp", leg.highway),
            None => "the highway on-ramp".to_string(),
        }
    }

    /// `_approach_facility_text()`.
    pub fn approach_facility_text(&self, ctx: &GameContext) -> String {
        if self.phase == DRIVE_PHASE_PICKUP {
            return self.pickup_facility_text(ctx);
        }
        self.destination_facility_text(ctx)
    }
}

/// `world.cities[key].state`, empty where the key is not a world city.
fn city_state(ctx: &GameContext, city: &str) -> String {
    let key = ctx.world.resolve_city_key(city);
    ctx.world
        .cities
        .get(&key)
        .map(|city| city.state.clone())
        .unwrap_or_default()
}
