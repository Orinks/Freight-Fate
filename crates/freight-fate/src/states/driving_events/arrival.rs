//! Arriving: the facility gate, the missed destination exit, the dock menu,
//! and the state's own visible lines and presence.

use ff_core::models::business::player_pays_operating_costs;
use ff_core::models::trucks::TRUCK_CATALOG;
use ff_core::pyfmt::fmt_grouped;
use ff_core::sim::hos::{clock_text, time_of_day};
use ff_core::sim::trip_models::Zone;
use ff_core::speech_pacing::{EventPriority, SpeechCategory};

use crate::app::{GameContext, SayEvent};
use crate::discord_presence::{driving_presence, PresenceState};
use crate::states::base::TimedMessageState;
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;
use crate::states::driving_menu_states::{replace_drive_with, DriveRef, FacilityArrivalState};
use crate::states::driving_updates::live;

impl DrivingState {
    /// `_handle_out_of_fuel()`.
    pub fn handle_out_of_fuel(&mut self, ctx: &mut GameContext) {
        if self.rescue_offered {
            return;
        }
        self.rescue_offered = true;
        let fee = 750.0;
        let billing = {
            let profile = profile_mut_of(ctx);
            if player_pays_operating_costs(&profile.business_status) {
                profile.money -= fee; // can go negative: the rescue is not optional
                format!("for {} dollars", fmt_grouped(fee, 0))
            } else {
                // the carrier pays for company fuel, but a preventable service
                // call goes straight onto the driver's record
                profile.career.reputation = 0.0f64.max(profile.career.reputation - 2.0);
                "on the carrier account, and dispatch noted the service call".to_string()
            }
        };
        self.trip.truck.refuel(Some(30.0));
        self.trip.truck.recover_from_fuel_depletion();
        self.cancel_cruise(ctx, false);
        self.rescue_offered = false;
        ctx.audio.play("ui/error");
        // A repair bill and an instruction, spoken to a truck already coasted
        // to a stop: nothing act-now left, so it queues on ROUTE's
        // never-dropped contract instead of purging the channel.
        let engine = ctx.control_hint("engine");
        let mut opts = SayEvent::queued().priority(EventPriority::Route);
        opts.category = Some(SpeechCategory::Money);
        ctx.say_event_with(
            format!(
                "You ran out of fuel. Roadside rescue brought thirty gallons {billing}. Press \
                 {engine} to restart the engine, and plan your fuel stops."
            ),
            opts,
        );
    }

    /// `_arrive()`: the pickup or delivery arrival screen.
    pub fn arrive(&mut self, ctx: &mut GameContext) {
        self.replace_with_arrival_state(ctx);
    }

    /// `_handle_missed_destination_exit()`.
    pub fn handle_missed_destination_exit(&mut self, ctx: &mut GameContext) {
        let exit_details = self.destination_exit_details(ctx, true);
        self.trip.finished = false;
        self.exit_stop = None;
        self.exit_signal_on = false;
        self.exit_signal_canceled = false;
        self.cancel_cruise(ctx, false);
        let exit_at = match exit_details {
            Some(details) => details.0,
            // Rural approaches carry no baked interchange, so the details
            // scan finds nothing -- but the exit the player just missed was
            // the synthetic one _destination_exit_stop places a mile before
            // route end, and the loop-back must return to it. Without this
            // the second miss stranded the trip at 0 miles remaining with
            // no exit left to signal for (owner playtest, Sedona to Camp
            // Verde on AZ-260, 2026-07-18).
            None => 0.0f64.max(self.trip.total_miles() - DESTINATION_EXIT_BEFORE_END_MI),
        };
        // Every miss loops back. The say-once latch must never swallow
        // this reposition: when it did, the second miss stranded the trip
        // pinned at the end of the route with no exit left to signal for,
        // cruise dying every frame (playtest transcript, 2026-07-16).
        self.missed_destination_exit_said = true;
        self.trip.game_minutes += EXIT_MISS_LOOP_MIN;
        // The loop-back is a real drive: hours, fatigue, and idle fuel move
        // with the clock, exactly as the facility-gate miss charges them.
        self.charge_scripted_loop(ctx, EXIT_MISS_LOOP_MIN);
        // Drop back a full exit window, not a fixed mile: under time
        // compression one mile passes in a few real seconds, making the
        // re-approach unwinnable before it was heard.
        self.trip.position_mi = 0.0f64.max(exit_at - self.exit_window_mi());
        self.destination_exit_announced_key = String::new();
        self.destination_exit_response_s = 0.0;
        self.destination_exit_cache = None;
        let reroute_text = if self.terse_speech(ctx) {
            // The signal reset with the miss; when the lane work is theirs, terse
            // players still need to hear that arming it is on them again.
            if ctx.settings.lane_is_manual() {
                format!(
                    "Safe turnaround. Destination exit ahead again; press {} to signal.",
                    ctx.control_hint("take_exit")
                )
            } else {
                "Safe turnaround. Destination exit ahead again.".to_string()
            }
        } else {
            format!(
                "You continue to the next safe turnaround and loop back onto the approach. The \
                 destination exit is ahead again; press {} when you are close enough to take it.",
                ctx.control_hint("take_exit")
            )
        };
        ctx.audio.play("ui/warning");
        self.set_status("Destination exit missed. Use the next safe turnaround.");
        // A mandatory-stop miss, not an optional one: the route just changed
        // and this names the maneuver that still gets the load delivered, so
        // it must survive quiet/urgent_only as words.
        let facility = self.destination_facility_text(ctx);
        let mut opts = SayEvent::new();
        opts.category = Some(SpeechCategory::Navigation);
        ctx.say_event_with(
            format!("You missed the destination exit for {facility}. {reroute_text}"),
            opts,
        );
    }

    /// `_handle_arrival_gate()`.
    pub fn handle_arrival_gate(&mut self, ctx: &mut GameContext) {
        if ctx.settings.destination_approach_assist {
            self.cancel_cruise(ctx, false);
            self.trip.truck.throttle = 0.0;
            self.trip.truck.brake = 1.0;
            if self.trip.truck.speed_mph() <= 0.5 && !self.arrival_full_stop_said {
                self.arrival_full_stop_said = true;
                self.trip.truck.set_parking_brake();
                // Only while the key still does something. A cut line is
                // handed back so it finishes, and this one asks for a
                // keypress -- handed back after the driver has pressed it
                // and the dock menu is open, it asks for a press that has
                // already happened (Shane, 2026-08-21, three of these at
                // one dock). Third line in this family after the scale and
                // the destination exit; the rule is the same every time.
                //
                // Rust: the live `_arrival_menu_open` read cannot ride a
                // 'static closure, so it goes through `live` like the scale
                // reminder's mile does. The flag is stamped where it moves as
                // well as per frame, because the drive stops ticking the
                // moment the dock menu takes over -- which is exactly the
                // moment this gate has to notice.
                self.refresh_live_facts();
                let mut opts = SayEvent::new().valid(|| !live::arrival_menu_open());
                opts.category = Some(SpeechCategory::Navigation);
                ctx.say_event_with(
                    "Destination approach stopped and holding. Press Enter, or controller A, to \
                     continue into the facility.",
                    opts,
                );
            }
            return;
        }
        if self.trip.truck.speed_mph() <= DOCKING_MAX_MPH {
            self.open_facility_arrival(ctx);
            return;
        }
        if self.trip.truck.speed_mph() <= DELIVERY_PARK_MPH {
            self.handle_arrival_creep(ctx);
            return;
        }
        // Above the gate zone's posted limit with the warning heard and the
        // reaction window spent: the entrance is missed, not still ahead.
        // (See driving_facility_gate.py; the assist branch above brakes the
        // truck itself and must never reach this.)
        if self.gate_miss_pending() {
            self.handle_missed_facility_gate(ctx);
            return;
        }
        let facility = self.destination_facility_text(ctx);
        if self.arrival_stop_said {
            let message = if self.terse_speech(ctx) {
                format!("At {facility}. Stop to dock.")
            } else {
                format!(
                    "Still at {facility}. The delivery is here, not ahead: slow down and stop to \
                     dock."
                )
            };
            self.remind_arrival_gate(ctx, "Destination gate: stop to dock.", &message, false);
            return;
        }
        self.arrival_stop_said = true;
        self.gate_reminder_s = GATE_REMINDER_INTERVAL_S;
        self.cancel_cruise(ctx, false);
        ctx.audio.play("ui/warning");
        self.set_status("Destination ahead: slow down and come to a complete stop.");
        let message = if self.terse_speech(ctx) {
            format!("Destination ahead: {facility}.")
        } else {
            format!(
                "Destination ahead: {facility}. Slow down and come to a complete stop at the gate."
            )
        };
        self.seed_gate_grace_at_gate(ctx, &message);
        let mut opts = SayEvent::new();
        opts.category = Some(SpeechCategory::Navigation);
        ctx.say_event_with(message, opts);
    }

    /// Repeat a gate's stop instruction while the truck rolls past it.
    ///
    /// The gate warnings latch after speaking once, which is right for a
    /// driver who is slowing -- but a driver who rolls on hears nothing again
    /// for the rest of the drive, with any re-armed cruise happily holding
    /// highway speed at a dead-end. Re-speak on a calm cadence and drop the
    /// cruise each time; the reminder stops the moment the truck slows into
    /// the gate's own creep-and-dock flow.
    pub fn remind_arrival_gate(
        &mut self,
        ctx: &mut GameContext,
        status: &str,
        message: &str,
        pickup: bool,
    ) {
        if self.gate_reminder_s > 0.0 {
            return;
        }
        self.gate_reminder_s = GATE_REMINDER_INTERVAL_S;
        if pickup {
            self.pause_speed_control(ctx, false);
        } else {
            self.cancel_cruise(ctx, false);
        }
        ctx.audio.play("ui/warning");
        self.set_status(status);
        let mut opts = SayEvent::new();
        opts.category = Some(SpeechCategory::Navigation);
        ctx.say_event_with(message.to_string(), opts);
    }

    /// The gate's instruction when the trip has ended at one, else None.
    ///
    /// Mirrors the update loop's gate dispatch so the info keys agree with
    /// what the gate handlers are actually waiting for.
    pub fn arrival_gate_query_text(&self, ctx: &GameContext) -> Option<String> {
        if !self.trip.finished || self.arrival_menu_open || self.departure_chain {
            return None;
        }
        if self.phase == DRIVE_PHASE_PICKUP {
            return Some(format!(
                "At {}. Stop to check in.",
                self.pickup_facility_text(ctx)
            ));
        }
        if self.ramp_mi.is_some() || !self.destination_exit_taken {
            return None;
        }
        Some(format!(
            "At {}. Stop to dock.",
            self.destination_facility_text(ctx)
        ))
    }

    /// `_handle_arrival_creep()`.
    pub fn handle_arrival_creep(&mut self, ctx: &mut GameContext) {
        if self.arrival_full_stop_said {
            return;
        }
        self.arrival_full_stop_said = true;
        self.cancel_cruise(ctx, false);
        ctx.audio.play_with("ui/notify", 0.7, 0.0);
        self.set_status("Destination gate: stop to dock.");
        let facility = self.destination_facility_text(ctx);
        self.say_route_navigation(ctx, &format!("At {facility}. Stop to dock."));
    }

    /// `_open_facility_arrival()`.
    pub fn open_facility_arrival(&mut self, ctx: &mut GameContext) {
        if self.arrival_menu_open {
            return;
        }
        self.arrival_menu_open = true;
        // The frame loop stops here, so the gate on "press Enter to continue"
        // would keep reading the last tick's answer without this.
        live::set_arrival_menu_open(true);
        self.cancel_cruise(ctx, false);
        self.trip.truck.brake = 1.0;
        self.trip.truck.set_parking_brake();
        // A dock gate is a menu-driven stop like a roadside inspection: the
        // frame loop that eases revs down between frames stops the instant
        // the dock menu takes over, so without this the engine audio froze
        // at whatever rev the approach left it at, all the way through the
        // stop.
        self.settle_engine_to_idle(ctx);
        advance_rest_clock(self, ctx, STOP_PULL_IN_MIN, None, "");
        hos_mut_of(ctx).on_duty(STOP_PULL_IN_MIN);
        self.set_status("Pulling into destination. Dock menu opening.");

        let facility = self.destination_facility_text(ctx);
        // Python's `complete()` closed over `self`, so the drive stayed
        // reachable even though `replace_state` had just taken it off the
        // stack. A 'static callback cannot close over `&mut self`, so take
        // the drive's own handle NOW, while it is still the active state,
        // and carry that into the callback. Looking the drive up on the
        // stack from inside the callback cannot work: the replace below is
        // exactly what removed it, so the dock menu never opened and the
        // game sat on "Pulling into destination" forever.
        let drive = DriveRef::active(ctx);
        ctx.replace_state(
            TimedMessageState::new(
                "Pulling into destination",
                &format!("Pulling into {facility}. Brakes set; dock menu opening in a moment."),
                "Pulling into the destination facility. Please wait.",
                STOP_PULL_IN_WAIT_S,
                move |ctx: &mut GameContext| {
                    let handle = drive.clone();
                    drive.with(ctx, |drive, ctx| {
                        drive.set_status("Parked at destination. Dock and deliver.");
                        // `FacilityArrivalState(self.ctx, self)`: the drive
                        // it covers is the one that pulled in, not whatever
                        // the stack happens to be showing now.
                        let mut state = FacilityArrivalState::with_drive(handle);
                        state.enter_over_drive(ctx, drive);
                        replace_drive_with(ctx, state);
                    });
                },
            )
            .sound_key(Some("ui/notify")),
        );
    }

    /// `_destination_facility_text()`.
    pub fn destination_facility_text(&self, _ctx: &GameContext) -> String {
        self.job.destination_facility_text()
    }

    /// `_objective_text()`.
    pub fn objective_text(&self, ctx: &GameContext) -> String {
        if self.phase == DRIVE_PHASE_PICKUP {
            return format!("pickup at {}", self.pickup_facility_text(ctx));
        }
        format!("deliver to {}", self.destination_facility_text(ctx))
    }

    /// `presence()`: broad, privacy-safe activity for Discord Rich Presence.
    pub fn presence_state(&self, ctx: &GameContext) -> Option<PresenceState> {
        let total = if self.trip.total_miles() == 0.0 {
            1.0
        } else {
            self.trip.total_miles()
        };
        let fraction = self.trip.position_mi / total;
        let moving = self.trip.truck.speed_mph() >= 1.0;
        let truck = ctx
            .profile
            .as_ref()
            .and_then(|profile| TRUCK_CATALOG.get(profile.truck.as_str()));
        Some(driving_presence(
            self.phase,
            self.job.spoken_origin(),
            self.job.spoken_destination(),
            self.job.cargo.label,
            fraction,
            moving,
            truck.map(|truck| truck.label).unwrap_or(""),
        ))
    }

    /// `online_presence()`: the drivers-board snapshot.
    ///
    /// The drivers board line adds what the cab radio is playing; Discord
    /// presence (above) does not, so the clause rides only the board copy.
    /// Station display names are curated public catalog data (call sign and
    /// name), never a stream URL, and the clause disappears the moment the
    /// radio is switched off -- the board only ever hears what a passenger in
    /// the cab would.
    pub fn online_presence_state(&self, ctx: &GameContext) -> Option<PresenceState> {
        let base = self.presence_state(ctx)?;
        if !self.radio.enabled {
            return Some(base);
        }
        // `current_station` re-resolves the dial (and may take an identity
        // handover), which needs `&mut`; `lines()`/`presence()` are `&self`,
        // so the read runs on a copy and the handover is left to the tick.
        let station = self.radio.clone().current_station();
        let mut clause = format!("listening to {}", station.display_name());
        // And the song, when the stream says: broadcast metadata the station
        // itself publishes to every listener, so no more private than the
        // station name. The tick's copy, not a fresh read -- presence is
        // built often, and a title that changes mid-second can wait for the
        // next tick.
        if station.real_stream {
            if let Some(title) = self.radio_now_playing.as_ref() {
                if !title.is_empty() {
                    clause = format!("{clause}: {title}");
                }
            }
        }
        let detail = if base.detail.is_empty() {
            clause
        } else {
            format!("{}, {clause}", base.detail)
        };
        Some(PresenceState::new(&base.activity, &detail))
    }

    /// `lines()`: the visible mirror of the speech.
    pub fn visible_lines(&self, ctx: &GameContext) -> Vec<String> {
        let t = &self.trip.truck;
        let (limit, reason) = self.display_speed_limit();
        let gear = if t.transmission.in_neutral() {
            "N".to_string()
        } else {
            t.transmission.gear.to_string()
        };
        let title = if self.phase == DRIVE_PHASE_PICKUP {
            format!(
                "Deadheading to pickup at {}",
                self.pickup_facility_text(ctx)
            )
        } else {
            format!("Driving loaded to {}", self.job.spoken_destination())
        };
        let s = &ctx.settings;
        let decimals = if self.phase == DRIVE_PHASE_PICKUP {
            1
        } else {
            0
        };
        let remaining = format!(
            "{} of {} {}",
            s.distance_value(self.trip.remaining_miles(), decimals, false),
            s.distance_value(self.trip.total_miles(), decimals, false),
            s.distance_unit_text(true)
        );
        let reason_text = match reason {
            Some(reason) => format!(", {reason}"),
            None => String::new(),
        };
        let cruise = match self.cruise_mph {
            Some(mph) => format!("   CRUISE {mph:.0}"),
            None => String::new(),
        };
        let air_state = if t.air_low_warning() {
            "LOW AIR"
        } else if t.air_ready() {
            "air ready"
        } else {
            "building"
        };
        let brake_state = if t.spring_brakes_active() {
            "spring brakes"
        } else if t.parking_brake {
            "parking set"
        } else {
            "parking released"
        };
        let calendar = self.calendar_phrase(ctx);
        let calendar = if calendar.is_empty() {
            "unknown".to_string()
        } else {
            calendar
        };
        let fatigue = ctx
            .profile
            .as_ref()
            .map(|profile| profile.fatigue)
            .unwrap_or(0.0);
        vec![
            title,
            String::new(),
            format!(
                "Speed: {} (limit {}{reason_text})   Lane: {}",
                s.hud_speed_text(t.speed_mph()),
                s.distance_value(limit, 0, false),
                self.lane.lane_name()
            ),
            format!(
                "Gear: {gear}   RPM: {:.0}   {}{cruise}",
                t.rpm,
                if t.engine_on {
                    "ENGINE ON"
                } else {
                    "engine off"
                }
            ),
            format!(
                "Air: {:.0} psi   {air_state}   {brake_state}",
                t.air_pressure_psi()
            ),
            format!(
                "Fuel: {:.0}%   Damage: {:.0}%",
                t.fuel_fraction() * 100.0,
                t.damage_pct
            ),
            format!("Remaining: {remaining}"),
            format!("Weather: {}", self.trip.weather.current.value()),
            format!("Date: {calendar}"),
            format!(
                "Clock: {} {} ({})   Fatigue: {fatigue:.0}%",
                clock_text(self.trip.local_hour()),
                self.trip.current_timezone().name,
                time_of_day(self.trip.local_hour())
            ),
            String::new(),
            self.status_text.clone(),
        ]
    }

    /// `speed_limit_at(position)` for the window, without the congestion
    /// recompute `Trip::speed_limit_at` performs (`lines()` is `&self`).
    fn display_speed_limit(&self) -> (f64, Option<String>) {
        let mile = self.trip.position_mi;
        let mut best: Option<&Zone> = None;
        for zone in &self.trip.zones {
            if !(zone.start_mi <= mile && mile <= zone.end_mi) {
                continue;
            }
            if best.is_none_or(|found| zone.limit_mph < found.limit_mph) {
                best = Some(zone);
            }
        }
        match best {
            Some(zone) => (zone.limit_mph, Some(zone.reason.clone())),
            None => (self.trip.corridor_limit_at(mile), None),
        }
    }
}
