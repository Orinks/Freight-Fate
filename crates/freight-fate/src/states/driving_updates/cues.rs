//! What the lane sounds like: the pan, the off-pavement transitions, the
//! edge-boundary ladder, the curve run's verdict, the dead-man's-curve
//! strips, the locator and steering tocks, and the guidance director.

use ff_core::data::curves::RouteCurve;
use ff_core::lane_guide_tone::LANE_GUIDE_TONE_KEY;
use ff_core::sim::lane::OFF_ROAD;
use ff_core::sim::lane_guidance::{
    classify_boundaries, cue_loudness, edge_rung, GuidanceFrame, CURVE_LEAD_MI, TRANSVERSE_KEY,
};
use ff_core::sim::trip_models::highway_class;
use ff_core::speech_pacing::SpeechCategory;

use crate::app::{GameContext, SayEvent};
use crate::audio::{CH_EDGE, CH_LANE_GUIDE, CH_ROAD};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;
use crate::states::driving_updates::LANE_GUIDE_TONE_VOLUME;

impl DrivingState {
    /// Stereo pan for the rumble strip: it comes from the side you have
    /// drifted toward (negative left, positive right), so the side you hear it
    /// on is the side to steer away from.
    pub fn lane_pan(&self) -> f64 {
        self.lane.offset.clamp(-1.0, 1.0)
    }

    pub fn off_pavement(&self) -> bool {
        self.lane.edge_excursion() >= OFF_ROAD
    }

    /// A severity band that rises as the truck goes deeper off and faster,
    /// so the transition speech fires again when the condition worsens
    /// (research doc R12). Zero to two.
    pub fn off_pavement_band(&self) -> i32 {
        let depth = if self.lane.edge_excursion() < 1.4 {
            0
        } else {
            1
        };
        let fast = if self.trip.truck.speed_mph() >= 45.0 {
            1
        } else {
            0
        };
        depth + fast
    }

    /// Speak the off-pavement condition at its transitions only: on entry,
    /// and again when it worsens. A steady or easing band stays silent -- the
    /// panned edge-rumble loop carries where the truck is (research doc R12).
    pub fn announce_off_pavement(&mut self, ctx: &mut GameContext) {
        let band = self.off_pavement_band();
        if let Some(previous) = self.road_position_band {
            if band <= previous {
                // Still off, no worse: track the band so a later worsening speaks,
                // but say nothing now.
                self.road_position_band = Some(band);
                return;
            }
        }
        self.road_position_band = Some(band);
        let boundary = self.edge_boundary();
        let mut message = if boundary == "oncoming" {
            // Past an undivided centerline is not a shoulder: say the
            // real danger, on the side it lives.
            "Across the centerline, in the oncoming lane!".to_string()
        } else if boundary == "median" {
            "Off the pavement, into the median on the left!".to_string()
        } else {
            self.lane.describe()
        };
        if !self.terse_speech(ctx) {
            message += " Steer back toward the lane center.";
        }
        // Position (the standing off-pavement condition) is STATUS; this
        // function only ever speaks on entry or worsening -- the transition
        // itself is the warning, so every line it emits is SAFETY.
        ctx.say_event_with(message, SayEvent::new().category(SpeechCategory::Safety));
    }

    /// What lies past the road edge the truck is drifting toward.
    ///
    /// The divided flag prefers the baked lane segment at the current mile,
    /// then the leg's carriageway-geometry flag (Track D2), then the
    /// classifier's honest inference (interstates are divided by
    /// definition; one lane per side means a centerline).
    pub fn edge_boundary(&self) -> &'static str {
        let baked = self.trip.lanes_at(None);
        let leg = &self.trip.route.legs[self.trip.current_leg_index()];
        let divided = match baked {
            Some((_, divided)) => Some(divided),
            None => leg.divided,
        };
        let (left, right) = classify_boundaries(
            self.lane.lane,
            self.lane.lane_count,
            divided,
            highway_class(&leg.highway) == "interstate",
        );
        if self.lane.offset < 0.0 {
            left
        } else {
            right
        }
    }

    /// Close the loop the pacenote opens: a soft tick on the bend's side
    /// as the curve begins, and a spoken verdict once you are through --
    /// held your line, caught the edge, or through it hot. The windshield
    /// gives a sighted driver this for free; the co-driver owes it to ours
    /// (owner ask 2026-07-27: "nothing tells you that you made it through
    /// well"). Chained bends hold their verdict for the last link.
    pub fn update_curve_run(&mut self, ctx: &mut GameContext, active: Option<&RouteCurve>) {
        let active = active.filter(|curve| !curve.connector);
        if let Some(curve) = active {
            let fresh = self
                .curve_run
                .as_ref()
                .map(|run| run.curve != *curve)
                .unwrap_or(true);
            if fresh {
                let (limit, _) = self.trip.speed_limit_at(self.trip.position_mi);
                let mut demanding =
                    (curve.advisory_mph as f64) < limit && curve.severity() != "gentle";
                let mut touched = false;
                let mut hot = false;
                if let Some(run) = self.curve_run.as_ref() {
                    // A chained link: carry what the earlier bends earned.
                    demanding = demanding || run.demanding;
                    touched = run.touched;
                    hot = run.hot;
                }
                self.curve_run = Some(CurveRun {
                    curve: *curve,
                    demanding,
                    touched,
                    hot,
                });
                if demanding && ctx.settings.curve_callouts {
                    let pan = if curve.direction == 'L' {
                        -PACENOTE_CUE_PAN
                    } else {
                        PACENOTE_CUE_PAN
                    };
                    let volume = 1.0f64.min(0.65 * self.cue_loudness(ctx));
                    ctx.audio.play_with("vehicle/curve_bink", volume, pan);
                }
            }
            let rumbling = self.lane.rumble_level() > 0.0;
            let speed = self.trip.truck.speed_mph();
            if let Some(run) = self.curve_run.as_mut() {
                if rumbling {
                    run.touched = true;
                }
                if speed > run.curve.advisory_mph as f64 + 15.0 {
                    run.hot = true;
                }
            }
            return;
        }
        if self.curve_run.is_none() {
            return;
        }
        if self.trip.curve_ahead_mi(0.2).is_some() {
            return; // linked "then right": the verdict waits for the last bend
        }
        let run = self.curve_run.take().expect("checked above");
        if !run.demanding || !ctx.settings.curve_callouts {
            return;
        }
        if self.terse_speech(ctx) {
            ctx.audio.play_with("vehicle/lane_centered", 0.5, 0.0);
            return;
        }
        let text = if run.touched {
            "Through the bend. You caught the edge."
        } else if run.hot {
            "Through the bend, hot."
        } else if ctx.settings.lane_is_manual() {
            "Through the bend, held your line."
        } else {
            "Through the bend."
        };
        ctx.say_event_with(
            text,
            SayEvent::queued().category(SpeechCategory::Confirmation),
        );
    }

    /// Lanes on our side at this mile.
    ///
    /// One answer, kept on the trip, so the lane the truck steers in and the
    /// lane a work zone may cone off can never disagree -- two readings of
    /// the road is how a closure landed on a one-lane stretch.
    pub fn lane_count_here(&self) -> i64 {
        self.trip.lane_count_at(None)
    }

    pub fn cue_loudness(&self, ctx: &GameContext) -> f64 {
        cue_loudness(&ctx.settings.lane_cue_loudness).unwrap_or(1.0)
    }

    /// Fixed dead-man's-curve bars ahead of hairpins: cross them, hear
    /// them -- at any speed, in any assist mode, because they are cut into
    /// the road. Louder when faster, like the real hits.
    pub fn update_transverse_strips(&mut self, ctx: &mut GameContext) {
        if self.trip.truck.speed_mph() < 2.0 {
            return;
        }
        let position = self.trip.position_mi;
        let strips = self.transverse_strip_miles.clone();
        for strip_mi in strips {
            if self.transverse_fired.contains(&strip_mi) || position < strip_mi {
                continue;
            }
            if position - strip_mi > 0.5 {
                self.transverse_fired.push(strip_mi); // resumed past it; stay quiet
                continue;
            }
            self.transverse_fired.push(strip_mi);
            let volume =
                1.0f64.min((0.65 + self.trip.truck.speed_mph() / 150.0) * self.cue_loudness(ctx));
            ctx.audio.play_with(TRANSVERSE_KEY, volume, 0.0);
            ctx.controller.rumble.impact(0.5);
        }
    }

    /// The I-key locator: a soft tock every beat, panned to where the
    /// truck sits in its lane. Player-summoned, so it keeps ticking until
    /// they shut it off or lane keeping takes the lane over.
    pub fn update_lane_locator_audio(&mut self, ctx: &mut GameContext, dt: f64) {
        if !self.lane_locator_on {
            return;
        }
        if ctx.settings.lane_is_automated() || self.trip.truck.speed_mph() < 2.0 {
            return;
        }
        self.lane_locator_timer -= dt;
        if self.lane_locator_timer > 0.0 {
            return;
        }
        self.lane_locator_timer = 0.9;
        let pan = self.lane.offset.clamp(-1.0, 1.0);
        let volume = 1.0f64.min(0.5 * self.cue_loudness(ctx));
        ctx.audio.play_with("vehicle/lane_locator", volume, pan);
    }

    /// How far along the exit-lane position is, 0 to 1.
    ///
    /// Either route to ready counts, the same two the exit itself accepts:
    /// the commitment built by holding Right, and simply sitting far enough
    /// over. Whichever is further along is what the driver is hearing.
    pub fn exit_alignment_progress(&self) -> f64 {
        if self.exit_stop.is_none() || !self.exit_signal_on {
            return 0.0;
        }
        if self.lane.lane != 0 && self.lane_change_target != Some(0) {
            return 0.0; // ramps peel off the right lane; in-lane position cannot help
        }
        (self.exit_lane_alignment / EXIT_LANE_READY)
            .max(self.lane.offset / EXIT_LANE_OFFSET_READY)
            .clamp(0.0, 1.0)
    }

    /// Is a lane move underway that the driver should hear their position for?
    ///
    /// Two ways in. Holding a steering direction for `STEER_CUE_ARM_S` is a
    /// move rather than a drift correction, and lasts as long as the wheel is
    /// held. An armed exit takes the cue over for the whole line-up: it runs
    /// from the moment the driver starts moving over until the exit lane is
    /// set, so the wheel coming back afterwards cannot re-arm it.
    pub fn steering_lane_cue_armed(&mut self, ctx: &GameContext, dt: f64) -> bool {
        if self.lane.steering != 0.0 {
            self.steer_cue_hold_s += dt;
        } else {
            self.steer_cue_hold_s = 0.0;
        }
        if self.lane_locator_on {
            return false; // the driver already has this tock running; one is enough
        }
        if ctx.settings.lane_is_automated() {
            return false; // the truck holds the lane and takes the exit itself
        }
        if self.trip.truck.speed_mph() < STEER_CUE_MIN_MPH {
            return false;
        }
        let steered = self.steer_cue_hold_s >= STEER_CUE_ARM_S;
        if self.exit_stop.is_some() && self.exit_signal_on && self.ramp_mi.is_none() {
            if self.exit_lane_ready() {
                return false;
            }
            return steered || self.exit_lane_alignment > 0.0;
        }
        steered
    }

    /// Hear where you are in the lane while you steer across it.
    ///
    /// The lane locator answers "where am I" on demand. This answers it for
    /// the length of a move being made right now, with no key to remember:
    /// the same panned tock, keeping time from the moment the wheel goes
    /// over until the move is done. Taking an exit with the lane work yours
    /// means holding a position at the right of the lane, and that position
    /// was the one thing on the road a blind driver could not hear (owner,
    /// 2026-08-15).
    ///
    /// The beat closes up as the exit-lane position fills, then stops dead
    /// and the signal cancels the instant the position is good -- a turn
    /// signal clicking off as the wheel comes back. The quickening says
    /// "nearly", the click says "set", and neither is a sentence.
    pub fn update_steering_lane_cue(&mut self, ctx: &mut GameContext, dt: f64) {
        if !self.steering_lane_cue_armed(ctx, dt) {
            if !self.steer_cue_active {
                return;
            }
            self.steer_cue_active = false;
            self.steer_cue_timer = 0.0;
            // Click off only if we still held the frame a moment ago. A menu
            // over the drive lets the latch lapse on the audio clock, and the
            // move ends in silence rather than a signal cancelling at the
            // pause screen -- the dead man's switch, same as a held alert.
            if ctx.audio.cue_held(STEER_CUE_HOLD) {
                ctx.audio.release_cue(STEER_CUE_HOLD);
                let volume = 1.0f64.min(STEER_CUE_CANCEL_VOL * self.cue_loudness(ctx));
                // centred and quieter: the signal off, not the signal on
                ctx.audio.play_with("vehicle/signal_tone", volume, 0.0);
            }
            return;
        }
        ctx.audio.hold_cue(STEER_CUE_HOLD);
        if !self.steer_cue_active {
            self.steer_cue_active = true;
            self.steer_cue_timer = 0.0; // first tock lands on the frame the move starts
        }
        self.steer_cue_timer -= dt;
        if self.steer_cue_timer > 0.0 {
            return;
        }
        let span = STEER_CUE_TOCK_S - STEER_CUE_TOCK_FAST_S;
        self.steer_cue_timer = STEER_CUE_TOCK_S - span * self.exit_alignment_progress();
        let volume = 1.0f64.min(0.5 * self.cue_loudness(ctx));
        let pan = self.lane.offset.clamp(-1.0, 1.0);
        ctx.audio.play_with("vehicle/lane_locator", volume, pan);
    }

    /// Run the edge-boundary ladder: structural loops, not louder beeps.
    ///
    /// Clipping the strip is intermittent, fully on it is periodic, off the
    /// pavement is aperiodic gravel -- states a driver can tell apart under
    /// engine noise. Panned to the drift side. Past an undivided centerline
    /// the strip stays the outermost texture (there is no gravel out there;
    /// the spoken warning carries the oncoming danger).
    pub fn update_edge_ladder_audio(&mut self, ctx: &mut GameContext) {
        let rung = if ctx.settings.lane_is_automated() || self.trip.truck.speed_mph() < 2.0 {
            None // tires that are not rolling make no groove noise
        } else {
            edge_rung(
                self.lane.edge_excursion(),
                self.edge_boundary(),
                self.cue_loudness(ctx),
            )
        };
        let Some((key, volume)) = rung else {
            if self.edge_loop_key.is_some() {
                ctx.audio.stop_loop_with(CH_EDGE, 150);
                self.edge_loop_key = None;
            }
            return;
        };
        ctx.audio.start_loop_with(CH_EDGE, key, volume, 120);
        ctx.audio.set_loop_volume(CH_EDGE, volume);
        let pan = self.lane_pan();
        ctx.audio.set_loop_pan(CH_EDGE, pan);
        self.edge_loop_key = Some(key.to_string());
    }

    /// Signed steer the active bend asks for, -1 full left .. 1 full right.
    ///
    /// Direction leads into the curve (a left bend wants left); magnitude
    /// follows the same tightness/overspeed shape the curve push uses, so
    /// the guide leans harder exactly when the bend pulls harder.
    pub fn curve_steer_demand(&self) -> f64 {
        let active = self.trip.curve_at(self.trip.position_mi);
        let Some(bend) = active.as_ref().filter(|curve| !curve.connector) else {
            // Ramp connectors and street maneuvers carry no mainline curve
            // record, and returning 0.0 here left the panned road bed dead
            // centre through every exit and every turn. The maneuver demand
            // keeps the guide leaning (see driving_turns.py).
            return self.maneuver_steer_demand(active.as_ref());
        };
        let tightness = 0.2f64.max(1.0 - bend.min_radius_ft as f64 / 5000.0);
        let excess = 0.0f64.max(self.trip.truck.speed_mph() - bend.advisory_mph as f64);
        let magnitude = 1.0f64.min(tightness * (1.0 + excess * 0.04));
        if bend.direction == 'L' {
            -magnitude
        } else {
            magnitude
        }
    }

    /// Run the guidance director: the road bed leans toward where the
    /// wheel should go (pursuit guide -- follow the sound), wakes for drift
    /// or a bend, and slews home on the centered straight. Never a new
    /// tone: the community ruling keeps the guide on the existing bed.
    pub fn update_lane_guidance_audio(&mut self, ctx: &mut GameContext, dt: f64) {
        let frame = if !ctx.settings.lane_departure_warning {
            self.lane_guidance.update(&self.lane, dt, false, 0.0, None)
        } else {
            let assist_on =
                ctx.settings.lane_is_manual() && self.trip.truck.speed_mph() >= LANE_MIN_MPH;
            let curve_steer = self.curve_steer_demand();
            let curve_ahead_mi = self.trip.curve_ahead_mi(CURVE_LEAD_MI);
            self.lane_guidance
                .update(&self.lane, dt, assist_on, curve_steer, curve_ahead_mi)
        };
        if ctx.settings.lane_guide_tone {
            self.lean_the_tone(ctx, frame);
        } else if frame.pan != self.road_pan_applied {
            ctx.audio.set_loop_pan(CH_ROAD, frame.pan);
            self.road_pan_applied = frame.pan;
        }
        if frame.centered {
            // The drift settled: the old centered earcon still says so.
            ctx.audio.play_with("vehicle/lane_centered", 0.45, 0.0);
        }
    }

    /// The opt-in alternative: lean a tone of the guide's own.
    ///
    /// Same frame, same pan, same wake and sleep -- only the thing being
    /// panned differs. The bed is left flat while the tone is in use, or a
    /// driver who switched would get both leaning at once and the bed would
    /// stay wherever the last drift left it.
    ///
    /// Silence is still centered: the loop starts on the wake and stops on
    /// the settle, so a straight road is as quiet as it has always been.
    /// That is what keeps this inside the community ruling rather than
    /// merely beside it -- the objection was to a CONTINUOUS tone, and this
    /// one only exists while the truck is actually off center.
    pub fn lean_the_tone(&mut self, ctx: &mut GameContext, frame: GuidanceFrame) {
        if self.road_pan_applied != 0.0 {
            ctx.audio.set_loop_pan(CH_ROAD, 0.0);
            self.road_pan_applied = 0.0;
        }
        if frame.awake {
            if !self.lane_guide_tone_on {
                let volume = LANE_GUIDE_TONE_VOLUME * self.cue_loudness(ctx);
                ctx.audio
                    .start_loop_with(CH_LANE_GUIDE, LANE_GUIDE_TONE_KEY, volume, 120);
                self.lane_guide_tone_on = true;
            }
            if frame.pan != self.lane_guide_pan_applied {
                ctx.audio.set_loop_pan(CH_LANE_GUIDE, frame.pan);
                self.lane_guide_pan_applied = frame.pan;
            }
        } else if self.lane_guide_tone_on {
            ctx.audio.stop_loop_with(CH_LANE_GUIDE, 180);
            self.lane_guide_tone_on = false;
            self.lane_guide_pan_applied = 0.0;
        }
    }
}
