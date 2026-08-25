//! The facility street chains: the surface chain that carries a delivery from
//! the destination ramp to the gate, the departure chain that carries a loaded
//! run out of the origin's gate, and the acceleration lane that ends it.

use ff_core::data::world_models::Route;
use ff_core::sim::trip_models::acceleration_lane_mi;
use ff_core::sim::weather::WeatherSystem;
use ff_core::speech_pacing::{EventPriority, SpeechCategory};
use ff_core::units::spoken_feet_or_meters;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

impl DrivingState {
    /// The spoken state name for a city key, or "" when the world is silent.
    ///
    /// A street chain's legs carry no state segments -- they are built from
    /// local geometry, not from the corridor bake -- so the trip cannot work
    /// out for itself whose vehicle code governs its streets. The city can.
    pub fn city_state(&self, ctx: &GameContext, city: &str) -> String {
        ctx.world
            .city(city)
            .map(|city| city.state.clone())
            .unwrap_or_default()
    }

    /// The destination facility's tier-1 street chain, or None.
    ///
    /// Only a genuine multi-segment turn-level route makes a chain; a single
    /// synthetic leg would just be the old teleport with extra steps, so those
    /// facilities keep the scripted arrival.
    pub fn surface_chain_route(&self, ctx: &GameContext) -> Option<Route> {
        let route = ctx
            .world
            .facility_approach_route(&self.job.destination, &self.job.destination_location)
            .ok()?;
        if route.legs.len() < 2 {
            return None;
        }
        if !route.legs.iter().any(|leg| leg.local_speed_mph > 0.0) {
            return None;
        }
        Some(route)
    }

    /// Whether this delivery's ramp hands off to a street chain.
    ///
    /// Decides where the ARRIVAL is. With a chain, the ramp's end is a driving
    /// continuation (see `_update_ramp_terminal`'s handoff) and the gate is up
    /// to a mile of streets further on; without one, the ramp ends at the
    /// gate. The destination approach assist stopped the truck dead at the end
    /// of a ramp that had a mile of city still to drive, and left automatic
    /// speed control paused the arrival way for all of it (owner, Spokane,
    /// 2026-08-22: "it didn't stop where I can pull in"). Memoised: the answer
    /// is a property of the job, and the world lookup behind it is not free
    /// per frame.
    pub fn destination_street_chain_ahead(&mut self, ctx: &GameContext) -> bool {
        if self.destination_chain_ahead.is_none() {
            self.destination_chain_ahead = Some(self.surface_chain_route(ctx).is_some());
        }
        self.destination_chain_ahead.unwrap_or(false)
    }

    /// A throwaway weather system, so a new `Trip` can be built before the
    /// real one is moved across (Python aliased one object; `WeatherSystem`
    /// owns a live provider and cannot be cloned).
    fn placeholder_weather(&self) -> WeatherSystem {
        WeatherSystem::new("", Some(self.trip_seed), None, None, false)
    }

    /// Swap the finished highway trip for the facility's street chain.
    ///
    /// The clock, the day of the week, and the toll ledger carry over, so
    /// deadlines, rush hour, and settlement are unaffected: only the road
    /// under the wheels changes.
    pub fn begin_surface_chain(&mut self, ctx: &mut GameContext, announce: bool) -> bool {
        if self.surface_chain {
            return false; // already on the streets
        }
        let Some(route) = self.surface_chain_route(ctx) else {
            return false;
        };
        let local_state = self.city_state(ctx, &self.job.destination.clone());
        let options = TripOptions {
            time_scale: self.trip.time_scale,
            seed: Some(self.trip_seed ^ 0x5AFE),
            start_hour: self.trip.start_hour,
            imperial: self.trip.imperial(),
            hazard_scale: 0.0, // no random hazards on the last city miles
            career_hours: self.trip.career_hours,
            bobtail: self.trip.bobtail,
            destination_label: self.trip.destination_label.clone(),
            local_state,
            ..Default::default()
        };
        let mut surface = Trip::new(
            route.clone(),
            self.trip.truck.clone(),
            self.placeholder_weather(),
            options,
        );
        // These streets ARE the run-in to the dock, so they run on the real
        // clock from their first foot. The exit watch sets this every frame,
        // but it has already run for this one, and a compressed tick here
        // moves the truck seven times further than the brakes can answer for.
        surface.dock_run_in = true;
        surface.game_minutes = self.trip.game_minutes; // deadline and clock continuity
        surface.toll_charges = self.trip.toll_charges.clone(); // settlement reads the live trip
        surface.hos_violation = self.trip.hos_violation;
        let mut old = self.replace_trip(surface);
        let weather = std::mem::replace(&mut old.weather, self.placeholder_weather());
        self.trip.weather = weather;
        self.highway_trip = Some(old);
        self.surface_chain = true;
        // A latched destination arrival belongs to the trip it began on. The
        // ramp's arrival stopped the truck at the ramp's end; the street chain
        // is a fresh approach with its own point half a mile on, and carrying
        // the latch over would hold the pedals -- throttle off, speed control
        // paused -- for the whole chain and coast the truck to a halt in the
        // road.
        self.destination_arrival_active = false;
        self.destination_assist_brake = 0.0;
        self.reset_exit_lane_state();
        self.exit_signal_on = false;
        // The ramp's transit pause ends HERE, not a frame later on a
        // no-braking condition: the streets begin with the truck at whatever
        // speed the terminal let through and, on this chain, a corner 264 feet
        // on. Nothing held that speed down -- cruise was paused for the ramp,
        // the keeper had not come back, and the driver was on the brake
        // because of it, which is the one thing that keeps the keeper from
        // coming back (owner, Spokane, 2026-08-22: "I had to brake to start
        // the turn onto city streets"). The terminal is honoured by driving
        // through it; automatic speed control belongs to the street zones
        // from the first foot of them.
        self.clear_stop_pause();
        // The first corner, if the chain starts inside its own window: it is
        // spoken in THIS line, at this line's priority, or it is not heard at
        // all. Raised on its own a frame later it queued behind the
        // off-the-ramp announcement and the gate warning as a droppable lead,
        // went stale, and was dropped -- twice on one arrival, the second
        // time after the loop-back, so "Turn right onto West Main Avenue"
        // was never once spoken (owner, Spokane, 2026-08-22).
        let mut first_corner = String::new();
        if let Some(corner) = self.turn_cue_in_play() {
            let ahead = corner.at_mi - self.trip.position_mi;
            if ahead > 0.0 && ahead <= self.turn_window_mi() {
                let call = self.turn_approach_text(ctx, &corner, ahead);
                first_corner = format!(" Then {}", lower_first(&call));
                self.turn_advised.insert(corner.key.clone());
                self.trip.controlled_turn = true;
                if let Some(sound) = local_turn_sound(Some(&corner.direction)) {
                    let pan = if corner.direction == "left" {
                        -TURN_CUE_PAN
                    } else {
                        TURN_CUE_PAN
                    };
                    ctx.audio.play_with(sound, 1.0, pan);
                }
            }
        }
        if announce {
            let first = &route.legs[0];
            let street = if first.local_cue.is_empty() {
                format!("Start on {}", first.highway)
            } else {
                first.local_cue.trim_end_matches('.').to_string()
            };
            ctx.audio.play_with("ui/notify", 0.7, 0.0);
            let message = format!(
                "Off the ramp and onto city streets: {}.{first_corner} {} to the facility gate.",
                lower_first(&street),
                self.trip.distance_text(route.miles())
            );
            if !first_corner.is_empty() {
                self.turn_grace_s = self.turn_grace_seconds(ctx, &message);
            }
            let mut opts = SayEvent::queued().priority(EventPriority::Route);
            opts.category = Some(SpeechCategory::Navigation);
            ctx.say_event_with(message, opts);
        }
        true
    }

    /// The origin facility's street chain driven outbound, or None.
    ///
    /// Same bar as the arrival side: only a genuine multi-segment turn-level
    /// chain qualifies; other facilities keep the scripted departure straight
    /// onto the highway.
    pub fn departure_chain_route(&self, ctx: &GameContext) -> Option<Route> {
        if self.phase != DRIVE_PHASE_DELIVERY {
            return None;
        }
        ctx.world
            .facility_departure_route(&self.job.origin, &self.job.origin_location)
            .ok()
            .flatten()
    }

    /// Start the loaded run on the origin facility's street chain.
    ///
    /// The full highway trip built at dispatch is parked aside; the truck
    /// pulls out of the gate onto real streets and the on-ramp merge hands the
    /// highway trip back with the clock and toll ledger intact.
    pub fn begin_departure_chain(&mut self, ctx: &mut GameContext, announce: bool) -> bool {
        if self.departure_chain || self.surface_chain {
            return false;
        }
        let Some(route) = self.departure_chain_route(ctx) else {
            return false;
        };
        let local_state = self.city_state(ctx, &self.job.origin.clone());
        let options = TripOptions {
            time_scale: self.trip.time_scale,
            seed: Some(self.trip_seed ^ 0xD00D),
            start_hour: self.trip.start_hour,
            imperial: self.trip.imperial(),
            hazard_scale: 0.0, // no random hazards on the first city miles
            career_hours: self.trip.career_hours,
            bobtail: self.trip.bobtail,
            local_state,
            // Driven outbound: the gate is the first thing behind you,
            // and this chain ends at the on-ramp.
            outbound: true,
            ..Default::default()
        };
        let merge_highway = self
            .trip
            .route
            .legs
            .first()
            .map(|leg| leg.highway.clone())
            .unwrap_or_default();
        let surface = Trip::new(
            route.clone(),
            self.trip.truck.clone(),
            self.placeholder_weather(),
            options,
        );
        let mut highway = self.replace_trip(surface);
        let weather = std::mem::replace(&mut highway.weather, self.placeholder_weather());
        self.trip.weather = weather;
        self.highway_trip = Some(highway);
        self.departure_chain = true;
        // Pulling out of the gate ENDS the stop that paused automatic speed
        // control. An arrival pause is deliberately never lifted by the resume
        // path -- only a departure clears one -- and nothing was clearing this
        // one, so the pause a driver earned by arriving to load survived being
        // loaded and followed them onto the road: armed, paused, and refusing
        // to engage for the rest of the run (Brandon, 2026-08-21). This is the
        // departure that clears it.
        self.clear_stop_pause();
        if announce {
            let first = &route.legs[0];
            let street = if first.local_cue.is_empty() {
                format!("Start on {}", first.highway)
            } else {
                first.local_cue.trim_end_matches('.').to_string()
            };
            let distance = self.trip.distance_text(route.miles());
            let mut opts = SayEvent::queued().priority(EventPriority::Route);
            opts.category = Some(SpeechCategory::Navigation);
            ctx.say_event_with(
                format!(
                    "Out of the gate and onto city streets: {}. {distance} to the \
                     {merge_highway} on-ramp.",
                    lower_first(&street)
                ),
                opts,
            );
        }
        true
    }

    /// End of the streets: up the on-ramp and onto the highway trip.
    pub fn finish_departure_chain(&mut self, ctx: &mut GameContext) {
        let game_minutes = self.trip.game_minutes;
        let toll_charges = self.trip.toll_charges.clone();
        let hos_violation = self.trip.hos_violation;
        let Some(mut highway) = self.highway_trip.take() else {
            return;
        };
        highway.game_minutes = game_minutes; // clock continuity
        highway.toll_charges = toll_charges; // settlement reads the live trip
        highway.hos_violation = hos_violation;
        highway.truck = self.trip.truck.clone();
        let mut surface = self.replace_trip(highway);
        let weather = std::mem::replace(&mut surface.weather, self.placeholder_weather());
        self.trip.weather = weather;
        self.departure_chain = false;
        // Coming up the ramp you are in the right lane, merging left.
        self.lane.lane = 0;
        self.lane.offset = 0.0;
        let merge_highway = self
            .trip
            .route
            .legs
            .first()
            .map(|leg| leg.highway.clone())
            .unwrap_or_default();
        // The acceleration lane is a real stretch of road with a real length,
        // not a moment. Handing straight to the highway meant arriving at the
        // taper doing whatever the last corner left you at -- about 17 mph in
        // a measured run, which is the "came to a stop" a tester reported
        // (Brandon, 2026-08-21). Now the lane exists, sized from the highway
        // it feeds, and the truck has room to build speed on it.
        let (highway_mph, _) = self.trip.speed_limit_at(0.0);
        let grade = self.trip.grade_at(0.0);
        self.departure_ramp_mi = Some(acceleration_lane_mi(highway_mph, grade));
        // A real length of road is only room to build speed on if it is spent
        // at the rate a truck really covers it. The exit watch pins the lane
        // to the real clock every frame, but it has already run for this one,
        // and the shortest lane the table gives is 360 feet -- of which a
        // single compressed tick eats two dozen.
        self.trip.controlled_ramp = true;
        let lane_text = spoken_feet_or_meters(
            self.departure_ramp_mi.unwrap_or(0.0),
            ctx.settings.imperial_units,
        );
        // Hand the lane to the KEEPER explicitly, here, rather than leaving it
        // to the resume path to work out. The swap happens late in the frame,
        // so for one tick the new road looks like open highway with no zone on
        // it -- and the keeper duly handed off to cruise, which cannot hold
        // below its own minimum speed. The result was cruise nominally engaged
        // and nothing at all touching the throttle: the truck coasted the
        // entire acceleration lane at zero throttle (measured out of Aberdeen,
        // 2026-08-21). The keeper is the automation for this stretch and it
        // takes it directly.
        if ctx.settings.speed_keeper && self.speed_control_armed {
            if self.cruise_mph.is_some() {
                self.cancel_cruise(ctx, true);
            }
            self.engage_keeper(
                ctx,
                highway_mph,
                "acceleration lane",
                Some(highway_mph),
                false,
            );
        }
        ctx.audio.play_with("vehicle/signal_tone", 0.6, -0.6);
        let mut opts = SayEvent::queued().priority(EventPriority::Route);
        opts.category = Some(SpeechCategory::Navigation);
        ctx.say_event_with(
            format!(
                "Up the ramp onto {merge_highway}. {lane_text} of acceleration lane; build your \
                 speed and look for a gap."
            ),
            opts,
        );
    }

    /// Run down the acceleration lane after pulling out of a facility.
    ///
    /// The lane is the one place a loaded truck is SUPPOSED to be slower than
    /// the road it is joining. The Green Book sizes these lanes for a
    /// passenger car -- 75 percent of highway speed is its own design target
    /// -- so a rig that reaches the taper under the limit has not failed at
    /// anything, and the game must not pretend otherwise. What a real driver
    /// does about it is take a bigger gap, which is what the closing line
    /// says.
    pub fn update_departure_ramp(&mut self, ctx: &mut GameContext, moved_mi: f64) {
        let Some(left) = self.departure_ramp_mi else {
            return;
        };
        let left = left - 0.0f64.max(moved_mi);
        self.departure_ramp_mi = Some(left);
        if left > 0.0 {
            return;
        }
        self.departure_ramp_mi = None;
        let position = self.trip.position_mi;
        let (limit, _) = self.trip.speed_limit_at(position);
        let speed = self.trip.truck.speed_mph();
        let short_by = limit - speed;
        // Under the limit by enough to matter is the NORMAL outcome for a
        // loaded truck, so it is said as a fact about the gap you need, never
        // as a fault. Only a truck that is genuinely up to speed gets the
        // plain merge line.
        let message = if short_by >= MERGE_UNDER_SPEED_MPH {
            format!(
                "Lane ending at {}. You are under the {} traffic is running, so take a big gap \
                 and keep building speed once you are in.",
                ctx.settings.speed_text(speed),
                ctx.settings.speed_text(limit)
            )
        } else {
            "Lane ending. Merge left when clear.".to_string()
        };
        ctx.audio.play_with("vehicle/signal_tone", 0.6, -0.6);
        let mut opts = SayEvent::queued().priority(EventPriority::Route);
        opts.category = Some(SpeechCategory::Navigation);
        ctx.say_event_with(message, opts);
    }
}

/// Python's `text[:1].lower() + text[1:]`.
fn lower_first(text: &str) -> String {
    let mut chars = text.chars();
    match chars.next() {
        None => String::new(),
        Some(first) => first.to_lowercase().collect::<String>() + chars.as_str(),
    }
}
