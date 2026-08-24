//! The whoosh when somebody goes by (port of
//! `freight_fate/states/driving_traffic_pass.py`, the `TrafficPassMixin`).
//!
//! Four pass-by cues have been shipped and credited since the traffic bubble
//! landed -- car, box truck, semi, trooper -- and only the trooper's could ever
//! play. Its earcon hangs off the enforcement layer, which fires on crossing a
//! post's mile marker; civilian traffic had no equivalent, so the other three
//! were reachable only as decoration on a spoken hazard warning about a
//! vehicle *ahead*. Ordinary traffic going past the cab made no sound at all.
//!
//! That is a hole in the game's only spatial channel. A sighted player watches
//! a truck come up the left lane and go by; a blind player had silence, then a
//! sentence about something else entirely.
//!
//! Three rules, all borrowed from cues that already work here:
//!
//! * **Earcon, never a sentence.** Nothing follows from hearing a car pass,
//!   and the run's spoken budget belongs to things that cost money -- the same
//!   reasoning that keeps the marked-unit pass wordless in the enforcement
//!   layer.
//! * **Pan is confirmation, not meaning.** Both audio backends apply pan once
//!   at trigger, so the sweep has to be baked into the clip. The pan says
//!   which side; it is never the thing carrying the information.
//! * **Once per vehicle.** A truck alongside in stop-and-go traffic can cross
//!   the bumper repeatedly, and a cue that re-fired on each would sound
//!   broken.
//!
//! Troopers are skipped here on purpose: enforcement already gives them a
//! marker-plus-whoosh pass, and playing this one too would double them up.

use crate::app::GameContext;
use crate::states::driving::DrivingState;

/// Panned to the side the vehicle went by on. Matches the enforcement pass so
/// a civilian and a marked unit place the same way.
pub const TRAFFIC_PASS_PAN: f64 = 0.55;
pub const TRAFFIC_PASS_BASE_VOLUME: f64 = 0.55;
// A vehicle barely out-running the truck is a long, quiet event; one going by
// twenty over is a bang. Scaled on closing speed between these two, so the
// dial has somewhere to move without ever reaching the level of a cue the
// driver has to act on.
pub const TRAFFIC_PASS_MIN_CLOSING_MPH: f64 = 3.0;
pub const TRAFFIC_PASS_FULL_CLOSING_MPH: f64 = 22.0;
pub const TRAFFIC_PASS_QUIET_VOLUME: f64 = 0.34;
/// Real seconds between whooshes, and it has to be REAL seconds: the clock
/// runs at ten times pacing on a highway, so a populated road produces a
/// crossing every couple of seconds at the speaker even though the truck is
/// meeting traffic at an ordinary rate on the road. Measured before this
/// existed: 2.7 passes per mile is one every 2.2 seconds in the player's ear,
/// which is a machine gun, not a highway.
///
/// Dropping the extras rather than thinning the traffic is the honest way
/// round. The road should stay as busy as the road is -- the lead-vehicle and
/// hazard systems read that population -- and closely spaced vehicles do not
/// arrive as separate whooshes anyway; they blend into the road bed the cab
/// already carries.
pub const TRAFFIC_PASS_MIN_GAP_S: f64 = 6.0;

impl DrivingState {
    pub fn reset_traffic_passes(&mut self) {
        self.traffic_pass_side.clear();
        self.traffic_passed_keys.clear();
        self.traffic_pass_cooldown_s = 0.0;
    }

    pub fn traffic_pass_volume(&self, closing_mph: f64) -> f64 {
        let span = TRAFFIC_PASS_FULL_CLOSING_MPH - TRAFFIC_PASS_MIN_CLOSING_MPH;
        let share = (closing_mph.abs() - TRAFFIC_PASS_MIN_CLOSING_MPH) / span;
        let share = share.clamp(0.0, 1.0);
        TRAFFIC_PASS_QUIET_VOLUME + share * (TRAFFIC_PASS_BASE_VOLUME - TRAFFIC_PASS_QUIET_VOLUME)
    }

    /// Fire a whoosh for every bubble vehicle that just changed ends.
    pub fn update_traffic_passes(&mut self, ctx: &mut GameContext, dt: f64) {
        self.traffic_pass_cooldown_s = (self.traffic_pass_cooldown_s - dt).max(0.0);
        let position = self.trip.position_mi;
        let truck_mph = self.trip.truck.speed_mph();
        let player_lane = self.trip.traffic_manager.player_lane;
        // The bubble is read once so the cue bookkeeping below can borrow the
        // drive mutably; Python walked the manager's list in place.
        let bubble: Vec<(String, f64, f64, i64, String)> = self
            .trip
            .traffic_manager
            .vehicles
            .iter()
            .map(|v| {
                (
                    v.key.clone(),
                    v.position_mi,
                    v.speed_mph,
                    v.lane,
                    v.vehicle_class.clone(),
                )
            })
            .collect();
        let mut live_keys: std::collections::HashSet<String> = std::collections::HashSet::new();
        for (key, vehicle_mi, vehicle_mph, lane, vehicle_class) in bubble {
            live_keys.insert(key.clone());
            let relative = vehicle_mi - position;
            let was = self.traffic_pass_side.insert(key.clone(), relative);
            let Some(was) = was else {
                continue;
            };
            if self.traffic_passed_keys.contains(&key) {
                continue;
            }
            if (was > 0.0) == (relative > 0.0) {
                continue; // still on the same end of the truck
            }
            // A marked unit's pass belongs to the enforcement layer, which
            // gives it a marker the civilian clips deliberately lack.
            if vehicle_class.to_lowercase() == "state trooper" {
                continue;
            }
            // Marked passed either way: the vehicle really did go by, and
            // replaying it later when the cooldown lapses would put the
            // whoosh somewhere the vehicle no longer is.
            self.traffic_passed_keys.insert(key);
            if self.traffic_pass_cooldown_s > 0.0 {
                continue;
            }
            self.traffic_pass_cooldown_s = TRAFFIC_PASS_MIN_GAP_S;
            let closing = truck_mph - vehicle_mph;
            let volume = self.traffic_pass_volume(closing);
            let volume = 1.0f64.min(volume * 1.4f64.min(self.ambience_scale()));
            // Which side it went by on: anything not sharing the truck's lane
            // passed in another one, and lane indices count leftward.
            let mut side = if lane == player_lane {
                0.0
            } else {
                TRAFFIC_PASS_PAN
            };
            if lane > player_lane {
                side = -TRAFFIC_PASS_PAN;
            }
            ctx.audio
                .play_with(traffic_vehicle_pass_sound(&vehicle_class), volume, side);
        }
        // A vehicle that has left the bubble is gone for good (the manager
        // never re-spawns a retired cell), so its bookkeeping goes with it
        // rather than growing for the whole run.
        let gone: Vec<String> = self
            .traffic_pass_side
            .keys()
            .filter(|key| !live_keys.contains(*key))
            .cloned()
            .collect();
        for key in gone {
            self.traffic_pass_side.remove(&key);
            self.traffic_passed_keys.remove(&key);
        }
    }
}

/// The cue for this vehicle class, falling back to the car whoosh.
pub fn traffic_vehicle_pass_sound(vehicle_class: &str) -> &'static str {
    match vehicle_class.trim().to_lowercase().as_str() {
        "semi" => "traffic/semi_pass",
        "box truck" => "traffic/box_truck_pass",
        "service vehicle" => "traffic/box_truck_pass",
        "car" => "traffic/car_pass",
        // Classes added for the cross-bubble expansion (2026-08-20). They do
        // not spawn on the mainline yet; the keys exist so the day a spawner
        // deals one, it already has a voice.
        "pickup" => "traffic/pickup_pass",
        "motorcycle" => "traffic/motorcycle_pass",
        "bus" => "traffic/bus_pass",
        "tractor" => "traffic/tractor_pass",
        _ => "traffic/car_pass",
    }
}
