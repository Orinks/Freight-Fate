//! Highway exits: arming the signal, the exit lane, the countdown, the exit
//! speed assist, and the destination exit's own scan and announcement.

use ff_core::sim::trip_models::{
    RoadStop, TrafficPressure, APPROACH_DECEL_MPS2, APPROACH_REACTION_S,
};
use ff_core::speech_pacing::{EventPriority, SpeechCategory};

use crate::app::{GameContext, SayEvent};
use crate::states::base::Key;
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;
use crate::states::driving_updates::live;

impl DrivingState {
    /// `_take_exit()`: the take-exit control.
    pub fn take_exit(&mut self, ctx: &mut GameContext) {
        self.toggle_exit_signal(ctx);
    }

    /// `_toggle_exit_signal()`: arm, confirm, or cancel the exit signal.
    pub fn toggle_exit_signal(&mut self, ctx: &mut GameContext) {
        if self.ramp_mi.is_some() {
            self.say_plain(ctx, "You are already on the exit ramp. Brake to a stop.");
            return;
        }
        let selected = self.selected_sleep_stop();
        let window = self.exit_window_mi();
        let selected_ahead = selected.as_ref().is_some_and(|stop| {
            let ahead = stop.at_mi - self.trip.position_mi;
            ahead > 0.0 && ahead <= window
        });
        // Explicit T selection outranks inferred destination bookkeeping.
        let mut stop = if selected_ahead {
            selected
        } else {
            match self.exit_stop.clone() {
                Some(stop) => Some(stop),
                None => self.upcoming_exit_stop(ctx),
            }
        };
        // ...and a nearer open scale outranks both: the inspection lane is
        // not optional, and arming the farther ramp is exactly what carried
        // a tester past the scale unarmed. The plan itself survives.
        let scale_claimed = self.scale_claiming_exit(ctx, stop.as_ref());
        let outranked = if scale_claimed.is_some() {
            stop.clone()
        } else {
            None
        };
        if let Some(scale) = scale_claimed.clone() {
            stop = Some(scale);
        }
        let Some(stop) = stop else {
            self.say_plain(
                ctx,
                format!(
                    "No route exit to signal for yet. Press {} to plan an upcoming sleep-capable \
                     stop, or wait for an exit announcement.",
                    ctx.control_hint("rest")
                ),
            );
            return;
        };
        let responding_to_destination_callout = stop.stop_type == "delivery_destination"
            && self.destination_exit_response_s > 0.0
            && Self::destination_exit_key(&stop) == self.destination_exit_announced_key;
        if responding_to_destination_callout {
            // The shared event voice may now be reading a newer safety warning,
            // so do not stop it just to replace the earlier exit callout.
            self.destination_exit_response_s = 0.0;
        }
        self.exit_stop = Some(stop.clone());
        let ahead = stop.at_mi - self.trip.position_mi;
        if self.exit_signal_on {
            // This close to the gore, one stray press must not silently throw
            // the approach away (playtested: an X meant as "confirm" canceled
            // the signal and cost the exit). The first press keeps the signal
            // and says so; only a deliberate second press cancels.
            if ahead <= EXIT_CANCEL_GUARD_MI && !self.exit_cancel_armed {
                self.exit_cancel_armed = true;
                self.say_plain(
                    ctx,
                    format!(
                        "Signal stays on. Hold the exit lane and keep slowing. Press {} again to \
                         cancel the exit.",
                        ctx.control_hint("take_exit")
                    ),
                );
                return;
            }
            self.exit_signal_on = false;
            self.exit_cancel_armed = false;
            self.exit_signal_canceled = true;
            // Letting the cap linger would leave automatic control crawling
            // at ramp speed down the open highway after the driver begged off.
            self.cruise_exit_mph = None;
            self.destination_exit_response_s = 0.0;
            let canceled_selected = self.is_selected_stop(Some(&stop));
            if canceled_selected {
                self.clear_selected_stop_intent();
            }
            let planned = if canceled_selected {
                " Facility stopping assistance is still on, but disarmed for this exit. Your planned stop remains on \
                 the route map."
            } else {
                ""
            };
            let message = format!("Signal canceled. Keep following the highway.{planned}");
            self.set_status(message.clone());
            self.say_plain(ctx, message);
            return;
        }
        self.exit_signal_on = true;
        self.exit_cancel_armed = false;
        self.exit_signal_canceled = false;
        // The player just signalled for an exit; count it toward retiring the
        // "press X to signal" instruction, and update what the stop callout
        // will say from here (research doc R7).
        self.note_instruction_demonstrated(ctx, "take_exit");
        self.refresh_exit_hint(ctx);
        // Re-arming after a cancel starts the distance anchors over; without
        // this the milestones already spoken stay marked and the second
        // approach runs silent.
        self.exit_countdown_said.clear();
        ctx.audio.play_with("vehicle/signal_tone", 0.7, 0.6);
        let head = if scale_claimed.is_some() {
            format!("Signal on for the scale exit: {},", stop.name)
        } else if stop.stop_type == "delivery_destination" {
            let labeled = self.exit_phrase_of(ctx, &stop);
            let labeled = if labeled.is_empty() {
                stop.exit_label.clone()
            } else {
                labeled
            };
            // A labeled exit already names itself; don't repeat the
            // facility that the fallback phrase would have baked in.
            if labeled.is_empty() {
                format!("Signal on for the destination exit for {},", stop.name)
            } else {
                format!(
                    "Signal on for {labeled}, destination exit for {},",
                    stop.name
                )
            }
        } else {
            // Once the stop-ahead callout has named this facility in full this
            // leg, the exit signal speaks its proper name alone (research doc
            // R6).
            let facility = self.trip.name_facility(&stop.name, &stop.spoken_name());
            if stop.exit_label.is_empty() {
                format!("Signal on for the {facility} exit,")
            } else {
                format!("Signal on for {}, {facility},", stop.exit_label)
            }
        };
        let lane_hint = if self.lane.lane == 0 {
            ""
        } else {
            " Get into the right lane."
        };
        // Name the ramp's ending now, while there is still a mile of
        // mainline to plan the braking on: a stop sign heard only on the
        // ramp cost real playtesters real cross-traffic damage.
        let ending = match self.ramp_control_for(ctx, &stop, None).as_str() {
            "signal" => " The ramp ends at a traffic light.",
            "stop" => " The ramp ends at a stop sign.",
            _ => "",
        };
        let ahead_text = ctx.settings.distance_text(ahead, true);
        let ramp_text = ctx.settings.speed_text(self.armed_ramp_mph(Some(&stop)));
        let cap = self.cap_cruise_for_ramp(ctx, Some(&stop));
        let mut message = if ctx.settings.lane_is_automated() {
            self.exit_lane_alignment = EXIT_LANE_READY;
            self.exit_lane_ready_said = true;
            ctx.audio.play_with("ui/notify", 0.6, 0.0);
            // The first granted lane of the run says who granted it. A driver
            // who never asked for this needs one chance to notice the truck
            // is doing it, and where to change that.
            let granted = if self.lane_keeping_grant_said {
                "Exit lane set."
            } else {
                self.lane_keeping_grant_said = true;
                "Exit lane set for you by lane keeping."
            };
            format!(
                "{head} {ahead_text} ahead. {granted}{lane_hint} Slow to {ramp_text} or less for \
                 the ramp.{ending}{cap}"
            )
        } else {
            format!(
                "{head} {ahead_text} ahead.{lane_hint} Move right for the exit lane, then slow to \
                 {ramp_text} or less for the ramp.{ending}{cap}"
            )
        };
        if self.is_selected_stop(Some(&stop)) {
            self.selected_stop_assist_armed = ctx.settings.destination_approach_assist;
            if self.selected_stop_assist_armed {
                let lane_action = if ctx.settings.lane_is_manual() {
                    "Set the exit lane; "
                } else {
                    ""
                };
                message.push_str(&format!(
                    " Facility stopping assistance armed. {lane_action}After the ramp \
                     control is clear, it will stop at the entrance."
                ));
            } else {
                message.push_str(" Brake to a complete stop at the entrance.");
            }
        }
        if scale_claimed.is_some() {
            if let Some(outranked) = outranked.as_ref() {
                if self.is_selected_stop(Some(outranked)) || self.trip.is_planned(outranked) {
                    message
                        .push_str(" Your planned sleep stop waits until you are past the scale.");
                }
            }
        }
        self.set_status(message.clone());
        if responding_to_destination_callout {
            // Queue behind whichever event is currently speaking. Usually that
            // is the exit callout; if a critical warning preempted it, the
            // warning must finish before the confirmation.
            //
            // And it may only come back while the exit is still THERE. A line
            // cut by an urgent warning is handed back so it finishes rather
            // than vanishing, which is right -- but "move right for the exit
            // lane" handed back after the gore is behind the truck instructs a
            // maneuver that no longer exists. That is the same fault the scale
            // exit line was given a validity check for on 21 August; this one
            // was missed because the report only ever named the scale.
            //
            // Rust: the predicate reads the live trip, which a 'static closure
            // cannot borrow, so it goes through `live` exactly as the scale
            // reminder does. The port had written the deviation note and then
            // left the gate off entirely, so the confirmation could be handed
            // back after the gore with nothing to refuse it.
            let exit_mi = stop.at_mi;
            self.refresh_live_facts();
            let mut opts = SayEvent::queued()
                .priority(EventPriority::Route)
                .valid(move || live::position_mi() < exit_mi);
            opts.category = Some(SpeechCategory::Navigation);
            ctx.say_event_with(message, opts);
        } else {
            self.say_plain(ctx, message);
        }
    }

    /// Ramp speed for the exit this truck is actually taking.
    ///
    /// Every exit used to demand the same 45, and every cruise the same 40 --
    /// one number for a loop off a 55 and a directional connector off a 75
    /// alike. The owner drove it and said so (2026-08-21). This asks the road
    /// instead: `Trip.ramp_speed_at` reads the corridor limit and the baked
    /// `ramp_far_end`, and AASHTO's share does the rest.
    ///
    /// Falls back to the old constant when nothing is armed, so callers that
    /// ask out of context behave exactly as before.
    pub fn armed_ramp_mph(&self, stop: Option<&RoadStop>) -> f64 {
        // The caller may hand the stop in: the exit callout builds its
        // sentence BEFORE _exit_stop is assigned, and without it this fell
        // back to the old flat number and quietly undid the whole change.
        let at_mi = stop
            .or(self.ramp_stop.as_ref())
            .or(self.exit_stop.as_ref())
            .map(|stop| stop.at_mi);
        match at_mi {
            None => RAMP_MAX_MPH,
            Some(at_mi) => self.trip.ramp_speed_at(at_mi),
        }
    }

    /// How fast the truck may still be doing when it enters the exit.
    ///
    /// NOT the ramp's design speed, which is what you slow to ALONG it. A
    /// deceleration lane is a full lane beside the through lanes and exists
    /// so a driver leaves at road speed and sheds inside it -- demanding ramp
    /// speed at the gore makes the driver do the lane's job on the highway,
    /// which is the whole complaint (owner, 2026-08-21).
    ///
    /// So the gore accepts road speed, and the ramp's own number governs from
    /// there. Collapsing the two is what briefly made a ramp off a 55 stricter
    /// than the flat 45 it replaced -- tightening exactly where the change was
    /// supposed to loosen.
    pub fn gore_acceptance_mph(&mut self, stop: Option<&RoadStop>) -> f64 {
        let at_mi = stop
            .or(self.ramp_stop.as_ref())
            .or(self.exit_stop.as_ref())
            .map(|stop| stop.at_mi);
        let Some(at_mi) = at_mi else {
            return RAMP_MAX_MPH;
        };
        let (corridor, _) = self.trip.speed_limit_at(at_mi);
        // "Road speed" is what the posts let a truck do, not the number on the
        // sign to the decimal: the same leeway the enforcement layer gives
        // before a speed is a speed at all. Judged at the sign's exact number
        // the gate refused its own assist -- the exit speed assist stands down
        // once the truck is at or under acceptance, a downgrade then put it a
        // fraction over with cruise already paused, and the truck that did
        // everything right missed its exit. The old flat pair had this
        // headroom built in (45 accepted, 40 aimed for); this keeps it.
        //
        // Never below the old flat acceptance: a slow corridor must not make
        // taking an exit harder than it has ever been.
        RAMP_MAX_MPH.max(corridor + SPEEDING_LEEWAY_MPH)
    }

    /// What automatic control aims for on that ramp.
    ///
    /// A little under the ramp's own number, for the same reason the flat 40
    /// sat under the flat 45: the cruise loop has a two-mph brake deadband
    /// and downhill runs at it, and it must not leave the truck hovering
    /// just over the ramp's speed at the gore.
    pub fn armed_ramp_cruise_mph(&self, stop: Option<&RoadStop>) -> f64 {
        RAMP_MIN_DESIGN_MPH.max(self.armed_ramp_mph(stop) - RAMP_CRUISE_HEADROOM_MPH)
    }

    /// Bring automatic speed control down to ramp speed for an armed exit.
    ///
    /// Arming an exit commits the truck to leaving the highway, so the cruise
    /// target has to come down with it. Otherwise automatic control holds
    /// highway speed straight through the gore point and the driver loses the
    /// exit without ever touching a control. Returns the spoken addition, or
    /// an empty string when there is nothing to say.
    pub fn cap_cruise_for_ramp(&mut self, ctx: &GameContext, stop: Option<&RoadStop>) -> String {
        let Some(cruise_mph) = self.cruise_mph else {
            // Paused mid-session -- a zone keeper, or a planned-stop pause.
            // Remember the cap so cruise resumes at ramp speed, but say
            // nothing: the keeper is already holding a low zone speed.
            if self.speed_control_armed {
                if let Some(target) = self.speed_control_target_mph {
                    self.cruise_exit_mph = Some(target.min(self.armed_ramp_cruise_mph(stop)));
                }
            }
            return String::new();
        };
        // Cruise aims a little under the ramp's own number (the old 40 under
        // a flat 45). Its normal two-mph brake deadband, downhill acceleration,
        // and frame timing must not leave the truck hovering just above the
        // ramp's speed as it comes off.
        let capped = cruise_mph.min(self.armed_ramp_cruise_mph(stop));
        if self
            .cruise_exit_mph
            .is_some_and(|existing| existing <= capped)
        {
            // The destination-exit announcement already capped cruise and said
            // so; pressing X right after must not repeat the whole sentence.
            return String::new();
        }
        self.cruise_exit_mph = Some(capped);
        // The number is where the truck will BE at the gore, not where it goes
        // now: _ramp_approach_cap_mph holds road speed until the exit is close
        // enough to shed for. Arming five miles out and dropping straight to
        // ramp speed is the "keeper goes to 40 miles away from the exit"
        // report (Shane, 2026-08-15).
        let target = ctx.settings.speed_text(capped);
        if self.trip.truck.speed_mph() > capped + 1.0 {
            // Say WHEN, not just what. "Adaptive cruise will ease to 40 for
            // the ramp", heard five miles out, reads as "I am going to 40 now"
            // -- and the owner drove it and reported the truck slowing early
            // when it had done nothing of the kind: _ramp_approach_cap_mph
            // holds road speed until about half a mile out and only then
            // sheds. The behaviour was right and the sentence was wrong, which
            // is worse than the reverse, because nobody goes looking for a bug
            // in a truck that is behaving (owner playtest, 2026-08-21).
            return format!(
                " Adaptive cruise holds road speed, then eases to {target} at the ramp."
            );
        }
        format!(" Adaptive cruise holding {target} for the ramp.")
    }

    /// The armed exit's cap right now, measured off the road still left.
    ///
    /// The ramp target is where the truck has to BE at the gore. Applied the
    /// moment the exit is armed it is also where the truck goes immediately,
    /// and an exit arms as much as five miles out (further under time
    /// compression, which is what the arming window is sized in) -- so a
    /// driver heard the callout and then watched automatic control sit at 40
    /// for miles of open interstate with the exit nowhere near (tester
    /// report, Shane, 2026-08-15).
    ///
    /// Instead the cap glides: corridor speed stands until the exit is inside
    /// the road this truck needs to shed for it, then comes down along the
    /// deceleration itself, reaching the ramp number a little before the gore.
    /// The road is priced exactly as the keeper's ease prices it -- a reaction
    /// budget in real seconds at the speed the truck is doing, and a
    /// comfortable shed rate under that.
    ///
    /// In REAL miles, not compressed ones. Pricing the road through the
    /// effective time scale looked prudent and was the same report all over
    /// again: at high pacing the cap fell under a 65 mph cruise nine miles
    /// out, so signalling early was itself what slowed the truck (Shane,
    /// 2026-08-15, signalling nine miles before a truck stop). The clock is
    /// where that problem belongs and is now where it is solved --
    /// `Trip::armed_exit_decompression` puts the trip back on real time for
    /// the whole approach window, which is wider than this glide -- so by the
    /// time the cap has anything to say, the miles under it really are real
    /// ones.
    pub fn ramp_approach_cap_mph(&self) -> Option<f64> {
        let floor = self.cruise_exit_mph?;
        if self.ramp_mi.is_some() {
            return Some(floor); // already on the ramp: the number is the number
        }
        let stop = self.exit_stop.as_ref().or(self.ramp_stop.as_ref());
        let Some(stop) = stop else {
            return Some(floor);
        };
        let ahead = stop.at_mi - self.trip.position_mi;
        if ahead <= 0.0 {
            return Some(floor);
        }
        // Priced at the set speed, not the live one, so the cap cannot chase
        // its own slowing and hand the road back a mile an hour at a time.
        let speed = self
            .trip
            .truck
            .speed_mph()
            .max(self.cruise_mph.unwrap_or(0.0))
            .max(floor);
        let reaction_mi = APPROACH_REACTION_S * speed / 3600.0;
        let brake_m = 0.0f64.max(ahead - reaction_mi) * METERS_PER_MILE;
        let floor_mps = floor / MPH_PER_MPS;
        let allowed =
            (floor_mps * floor_mps + 2.0 * APPROACH_DECEL_MPS2 * brake_m).sqrt() * MPH_PER_MPS;
        Some(floor.max(allowed))
    }

    /// `_reset_exit_lane_state()`.
    pub fn reset_exit_lane_state(&mut self) {
        self.exit_lane_alignment = 0.0;
        self.exit_lane_prompt_said = false;
        self.exit_lane_ready_said = false;
        self.exit_commit_said = false;
        self.exit_cancel_armed = false;
        self.exit_right_hold_s = 0.0;
        self.exit_right_taps = 0;
        self.exit_tap_hint_said = false;
        self.exit_countdown_said.clear();
    }

    /// `_exit_lane_ready()`.
    pub fn exit_lane_ready(&self) -> bool {
        // Ramps peel off the right lane: no amount of in-lane alignment
        // helps from the left lane, and a change in progress toward the
        // right still counts as making the gore.
        if self.lane.lane != 0 && self.lane_change_target != Some(0) {
            return false;
        }
        self.exit_lane_alignment >= EXIT_LANE_READY || self.lane.offset >= EXIT_LANE_OFFSET_READY
    }

    /// Distance reminders for an armed exit, every steering mode.
    ///
    /// A canyon approach buries a single signal-on announcement under
    /// pacenotes and limit changes (owner playtest: signal at 4.7 miles,
    /// then silence until the miss). The countdown re-anchors the exit as
    /// it closes, and names the lane fix while there is road to make it.
    ///
    /// Terse speech opts out of the whole countdown: the player asked for
    /// the signal-on announcement to be the last word.
    pub fn update_exit_countdown(&mut self, ctx: &mut GameContext, stop: &RoadStop) {
        if self.terse_speech(ctx) {
            return;
        }
        let ahead = stop.at_mi - self.trip.position_mi;
        if ahead <= 0.0 {
            return;
        }
        let milestones: &[f64] = if ctx.settings.lane_is_manual() {
            // Players doing their own lane work get the two-mile exit-lane prep
            // prompt; the countdown adds only the closer anchors.
            &EXIT_COUNTDOWN_MILESTONES_MI[1..]
        } else {
            &EXIT_COUNTDOWN_MILESTONES_MI
        };
        let crossed: Vec<f64> = milestones
            .iter()
            .copied()
            .filter(|m| ahead <= *m && !self.exit_countdown_said.contains(m))
            .collect();
        if crossed.is_empty() {
            return;
        }
        // Time compression can cross several milestones in one frame:
        // mark them all, speak only the nearest.
        self.exit_countdown_said.extend(crossed.iter().copied());
        let nearest = crossed.iter().copied().fold(f64::INFINITY, f64::min);
        let distance = if nearest >= 1.0 {
            ctx.settings.distance_text(nearest, false)
        } else {
            ctx.settings.short_distance_text(nearest)
        };
        let name = if stop.stop_type == "delivery_destination" {
            "Destination exit".to_string()
        } else {
            format!("Exit for {}", stop.spoken_name())
        };
        let lane_text = if self.exit_lane_ready() {
            ""
        } else if ctx.settings.lane_is_automated() {
            " Tap Right to the right lane."
        } else {
            " Steer right for the exit lane."
        };
        ctx.audio.play_with("ui/notify", 0.6, 0.0);
        let mut opts = SayEvent::queued().priority(EventPriority::Route);
        opts.category = Some(SpeechCategory::Navigation);
        ctx.say_event_with(format!("{name} in {distance}.{lane_text}"), opts);
    }

    /// `_update_exit_preparation(keys, dt)`.
    pub fn update_exit_preparation(&mut self, ctx: &mut GameContext, dt: f64) {
        let Some(stop) = self.exit_stop.clone() else {
            self.reset_exit_lane_state();
            return;
        };
        if self.ramp_mi.is_some() {
            self.reset_exit_lane_state();
            return;
        }
        // The signal is how a driver COMMITS to an exit -- but with lane
        // keeping automated they never press it, because the game itself says
        // "lane keeping will take this exit". Gating the speed assist on the
        // signal therefore switched it off for exactly the preset that
        // promises the most help: the announcement said "adaptive cruise will
        // ease to 40 for the ramp", nothing eased, and the truck went through
        // the gore at 53 and missed the exit (owner playtest, Denver->
        // Silverthorne, 2026-08-19). Automated lane keeping IS the commitment.
        let automated = ctx.settings.lane_is_automated();
        let committed = self.exit_signal_on || automated;
        if committed {
            self.update_exit_countdown(ctx, &stop);
            self.update_exit_speed_assist(ctx, &stop);
        }
        if automated {
            return;
        }
        if !self.exit_signal_on {
            return;
        }
        let ahead = stop.at_mi - self.trip.position_mi;
        if ahead < -EXIT_COMMIT_WINDOW_MI {
            return;
        }

        let right = ctx.input.is_pressed(Key::Right);
        let left = ctx.input.is_pressed(Key::Left);
        // A quick tap is how full-lane-keeping players change lanes; when the
        // lane work is yours it only nudges the wheel and the exit lane never
        // builds. Two taps on one approach earn the how-to, once, so the
        // silence never reads as broken keys.
        if right {
            self.exit_right_hold_s += dt;
        } else {
            if self.exit_right_hold_s > 0.0 && self.exit_right_hold_s <= EXIT_TAP_HOLD_S {
                self.exit_right_taps += 1;
            }
            self.exit_right_hold_s = 0.0;
        }
        if self.exit_right_taps >= 2
            && self.exit_lane_alignment < EXIT_LANE_READY
            && !self.exit_tap_hint_said
        {
            self.exit_tap_hint_said = true;
            self.say_plain(
                ctx,
                "You are holding the lane yourself, so taps only nudge the wheel. Hold Right to \
                 steer into the exit lane.",
            );
        }
        if right {
            self.exit_lane_alignment += dt / 1.2;
        } else if left {
            self.exit_lane_alignment -= dt / 0.8;
        } else if self.exit_lane_ready_said
            && self.exit_lane_alignment >= EXIT_LANE_READY
            && self.lane.offset >= -0.25
        {
            self.exit_lane_alignment = self.exit_lane_alignment.max(EXIT_LANE_READY);
        } else if self.lane.offset >= EXIT_LANE_OFFSET_READY {
            self.exit_lane_alignment += dt / 2.0;
        } else if self.lane.offset < -0.25 {
            self.exit_lane_alignment -= dt / 0.8;
        } else {
            self.exit_lane_alignment -= dt / 4.0;
        }
        self.exit_lane_alignment = self.exit_lane_alignment.clamp(0.0, 1.0);

        if ahead > 0.0 && ahead <= EXIT_LANE_PREP_MI && !self.exit_lane_prompt_said {
            self.exit_lane_prompt_said = true;
            let pressure = self.active_exit_pressure(&stop);
            let pressure_text = if pressure.is_some_and(|p| p.intensity >= 0.35) {
                " Traffic is tight, so hold the lane and let the gap open."
            } else {
                ""
            };
            let ramp = self.armed_ramp_mph(None);
            let distance = ctx.settings.distance_text(ahead, true);
            let mut opts = SayEvent::queued().priority(EventPriority::Route);
            opts.category = Some(SpeechCategory::Navigation);
            ctx.say_event_with(
                format!(
                    "Exit lane in {distance}. Signal is on; steer right for the exit lane and \
                     slow to {ramp:.0}.{pressure_text}"
                ),
                opts,
            );
        }
        if ahead > 0.0
            && ahead <= EXIT_LANE_PREP_MI
            && self.exit_lane_ready()
            && !self.exit_lane_ready_said
        {
            self.exit_lane_ready_said = true;
            ctx.audio.play_with("ui/notify", 0.6, 0.0);
            self.say_plain(ctx, "Exit lane set. Hold this lane and keep slowing.");
        }
        if (0.0..=EXIT_COMMIT_WINDOW_MI).contains(&ahead) && !self.exit_commit_said {
            self.exit_commit_said = true;
            let ramp = self.armed_ramp_mph(None);
            let mut opts = SayEvent::queued().priority(EventPriority::Route);
            opts.category = Some(SpeechCategory::Navigation);
            ctx.say_event_with(
                format!("At the exit gore. Hold the exit lane and stay under {ramp:.0}."),
                opts,
            );
        }
    }

    /// Slow an armed exit toward ramp speed, in EVERY steering mode.
    ///
    /// This used to sit below the lane-work early return, so it never ran
    /// with `lane_keeping` on full -- and the All assists preset selects full
    /// lane keeping, which meant the easiest preset silently disabled one of
    /// the assists it had just turned on.
    pub fn update_exit_speed_assist(&mut self, ctx: &mut GameContext, stop: &RoadStop) {
        if !ctx.settings.exit_speed_assist {
            return;
        }
        let ahead = stop.at_mi - self.trip.position_mi;
        if !(ahead > 0.0 && ahead <= 1.5) {
            return;
        }
        if self.trip.truck.speed_mph() <= self.gore_acceptance_mph(Some(stop)) {
            if self.cruise_mph.is_some() || self.keeper_mph.is_some() {
                // Nothing to shed and a controller already holding the road:
                // leave it. This used to pause speed control the moment the
                // exit came inside its reach, whether or not it had anything
                // to brake for -- right for the old flat 45, where every
                // truck at road speed was over it, wrong now that the gore
                // accepts road speed. Paused with nothing to do, the assist
                // coasted; on a 3.7 percent downgrade the truck ran from 60 to
                // 69 with "automatic speed control paused" the only thing the
                // status said (owner, Spokane, twice, 2026-08-21/22). Cruise
                // holds the grade and its own ramp glide eases to the ramp's
                // number at the gore, which is what the callout promised.
                return;
            }
            // Down to ramp speed with nobody on the pedals. HOLD it to the
            // gore rather than handing back an empty one: left alone the
            // truck coasted the rest of the approach down to a dead stop in
            // the through lane, a quarter mile short of its own exit -- worst
            // at real-time pacing, where the coast has the most seconds to
            // finish.
            self.hold_exit_approach_speed();
            return;
        }
        if self.cruise_mph.is_some() || self.keeper_mph.is_some() {
            // Over what the gore accepts: the assist takes the pedals for the
            // ramp; the session is not its to end. Disarming here was the
            // first of the three places that left both controllers dead for
            // the rest of the run (Shane, 2026-08-15) -- and the keeper has to
            // come off too, or it fights the assist's own brake. A destination
            // exit still holds like any arrival; every other exit is a
            // transit stop.
            let transit = stop.stop_type != "delivery_destination";
            self.pause_speed_control(ctx, transit);
        }
        self.trip.truck.brake = self.trip.truck.brake.max(0.35);
        if self.assist_exit_slowing_said {
            return;
        }
        self.assist_exit_slowing_said = true;
        // Never name a key this driver's settings do not give them: with lane
        // drift off a tap changes lanes, and holding Right does nothing.
        let lane_text = if ctx.settings.lane_is_automated() {
            "Tap Right to the right lane and keep slowing."
        } else {
            "Hold Right for the exit lane and keep slowing."
        };
        // Never "confirm": there is no confirm action, and an X pressed to
        // obey it cancels the signal instead.
        let mut opts = SayEvent::queued().priority(EventPriority::Route);
        opts.category = Some(SpeechCategory::Confirmation);
        ctx.say_event_with(format!("Exit speed assistance slowing. {lane_text}"), opts);
    }

    /// Keep the truck at ramp speed on an approach the assist is running.
    ///
    /// A light, bounded throttle and never a brake. It stands down the moment
    /// the driver is on a pedal of their own, because slowing further for
    /// their own gore is their call; the driver can always ask for more than
    /// this, and the assist's own brake above ramp speed caps the other end.
    /// Says nothing: the slowing line already named who has the pedal, and
    /// holding the speed it announced is the same assist finishing its job.
    pub fn hold_exit_approach_speed(&mut self) {
        let target = self.armed_ramp_cruise_mph(None);
        let t = &mut self.trip.truck;
        if !t.engine_on || t.stalled || t.air_brakes_holding() {
            return;
        }
        if t.brake > 0.01 || t.emergency_brake || t.transmission.in_reverse() {
            return;
        }
        let short_by = target - t.speed_mph();
        if short_by <= 0.0 {
            return; // coasting between the target and the ramp limit is fine
        }
        t.throttle = t.throttle.max(EXIT_HOLD_MAX_THROTTLE.min(short_by / 10.0));
    }

    /// `_active_exit_pressure(stop)`.
    pub fn active_exit_pressure(&self, stop: &RoadStop) -> Option<TrafficPressure> {
        let sample_mi = self.trip.position_mi.min(stop.at_mi);
        let pressure = self.trip.traffic_pressure_at(Some(sample_mi))?;
        if pressure.kind != "exit" {
            return None;
        }
        if pressure.start_mi <= stop.at_mi && stop.at_mi <= pressure.end_mi + 0.2 {
            return Some(pressure);
        }
        None
    }

    /// Arming and announcement window for exits, scaled like zone warnings.
    ///
    /// At speed under time compression a fixed window shrinks to nothing in
    /// real terms -- at 74 mph on standard pacing, 5 miles is about 14 real
    /// seconds, and it was half that on the retired Realistic setting: not
    /// enough to hear the callout, arm the exit, and brake to ramp speed.
    /// Scale the window so it covers roughly `EXIT_WARNING_REAL_S` of real
    /// time at the current pace.
    pub fn exit_window_mi(&self) -> f64 {
        let speed = self.trip.truck.speed_mph().max(30.0);
        let miles = EXIT_WARNING_REAL_S * speed * self.trip.effective_time_scale() / 3600.0;
        EXIT_WINDOW_MI.max(miles.min(EXIT_WINDOW_MAX_MI))
    }

    /// `_upcoming_exit_stop()`.
    pub fn upcoming_exit_stop(&mut self, ctx: &mut GameContext) -> Option<RoadStop> {
        let window = self.exit_window_mi();
        let stop = self.trip.upcoming_stop(window).cloned();
        let Some(destination) = self.destination_exit_stop(ctx) else {
            return stop;
        };
        let ahead = destination.at_mi - self.trip.position_mi;
        let announced_destination_is_actionable = ahead > 0.0
            && self.destination_exit_response_s > 0.0
            && Self::destination_exit_key(&destination) == self.destination_exit_announced_key;
        if announced_destination_is_actionable {
            // X responds to the exit just named, even if an optional stop has
            // since entered the ordinary lookahead window.
            return Some(destination);
        }
        if !(ahead > 0.0 && ahead <= window) {
            return stop;
        }
        match stop {
            None => Some(destination),
            Some(stop) if destination.at_mi <= stop.at_mi => Some(destination),
            Some(stop) => Some(stop),
        }
    }

    /// `_exit_intent_ready(stop)`.
    pub fn exit_intent_ready(&self, ctx: &GameContext, stop: &RoadStop) -> bool {
        if self.exit_signal_canceled {
            return false;
        }
        if self.exit_signal_on {
            return true;
        }
        stop.stop_type == "delivery_destination" && ctx.settings.lane_is_automated()
    }
}
