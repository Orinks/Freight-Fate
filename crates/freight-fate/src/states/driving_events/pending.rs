//! TEMPORARY stubs for everything `driving_events.py` reached for on a mixin
//! that has not been ported yet (T4.4b landed first of the driving mixins).
//!
//! Each block below names the module that owns it. When that module lands its
//! real `impl DrivingState` (or its module-level functions), it DELETES its
//! block here -- a duplicate method is a compile error that points straight at
//! the pair, exactly as `states/driving.rs`'s own `pending` module works.
//!
//! Signatures are the contract: keep them when porting. Bodies do the least
//! that keeps a drive coherent (a neutral answer, a no-op) and log once per
//! process, except where the Python function is pure and short enough that the
//! faithful body IS the stub -- the four `driving_stops` helpers and the
//! `driving_speed_control` constants below are exact ports, kept here only so
//! this file's callers behave correctly before their owners land.

use std::sync::Once;

use ff_core::data::curves::RouteCurve;
use ff_core::sim::trip_models::{NavigationCue, RoadStop};
use ff_core::sim::vehicle::TruckState;
use ff_core::speech_text::SpokenMessage;

use crate::app::GameContext;
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

macro_rules! pending_once {
    ($name:literal) => {{
        static ONCE: Once = Once::new();
        ONCE.call_once(|| log::warn!("driving_events: {} is a pending stub", $name));
    }};
}

// -- provided by driving_stops.rs (module-level helpers) ---------------------------------
//
// Exact ports of the four pure functions `driving_events.py` imports from
// `driving_stops`. Faithful bodies, because the ramp bar and every stopping
// assist read them every frame and a neutral answer would be wrong.

/// `bar_tick_range_mi(truck)`: how far out the stop-bar tick starts, for this
/// truck as it is now.
///
/// Carries a reaction allowance as well as the stopping distance: the bar is
/// the one place where the cue *is* the instrument, so its range has to pay
/// for the listening too.
pub fn bar_tick_range_mi(truck: &TruckState) -> f64 {
    let needed = truck.stopping_distance_mi(None, RAMP_BAR_REACTION_S, true) + RAMP_BAR_SOLID_MI;
    RAMP_BAR_TICK_RANGE_MI.max(needed)
}

/// `bar_solid_zone_mi(truck)`: where the ticks fuse into the held tone.
///
/// Sixty feet is an owner spec written into the manual, so unlike the tick
/// range this does not simply become "whatever this truck needs". It extends
/// by one thing only: the extra road the *liquid* is asking for.
pub fn bar_solid_zone_mi(truck: &TruckState) -> f64 {
    RAMP_BAR_SOLID_MI + truck.surge_stopping_penalty_mi(None)
}

/// `assist_full_decel_mps2(truck)`: denominator for mapping needed
/// deceleration onto brake application. Taking the lower of nominal and
/// achievable means the assist can only ever press harder, never softer.
pub fn assist_full_decel_mps2(truck: &TruckState) -> f64 {
    0.5f64.max(RAMP_ASSIST_FULL_DECEL_MPS2.min(truck.full_service_decel_mps2()))
}

/// `assist_servo_brake(applied, needed_mps2, truck)`: the application a
/// stopping assist should be holding right now.
///
/// The floor is the assist's own trigger deceleration mapped through the same
/// denominator the demand is, so at the moment the assist first presses, floor
/// and demand agree. And the pedal follows a falling demand only once the fall
/// is worth a release: easing off is free; coming back on costs air.
pub fn assist_servo_brake(applied: f64, needed_mps2: f64, truck: &TruckState) -> f64 {
    let full = assist_full_decel_mps2(truck);
    let wanted = 1.0f64.min((RAMP_ASSIST_DECEL_START_MPS2 / full).max(needed_mps2 / full));
    if wanted > applied {
        return wanted;
    }
    if wanted < applied - RAMP_ASSIST_RELEASE_BAND {
        return wanted;
    }
    applied
}

// -- provided by driving_speed_control.rs (module constants) -----------------------------

pub const KEEPER_EASE_UNDERSHOOT_MPH: f64 = 1.0;
pub const KEEPER_SNUB_OVER_MPH: f64 = 1.5; // this far over the target starts a snub
pub const KEEPER_SNUB_UNDER_MPH: f64 = 1.0; // and it runs until this far back under it
pub const KEEPER_SNUB_DECEL_MPS2: f64 = 0.6;
pub const KEEPER_SNUB_MIN_BRAKE: f64 = 0.12; // a real application, not a drag
pub const KEEPER_SNUB_MAX_BRAKE: f64 = 0.6; // zone speeds never need more than this
pub const KEEPER_OVERRUN_MPH: f64 = 3.0;
pub const KEEPER_OVERRUN_S: f64 = 4.0;

// -- provided by driving_speed_control.rs (SpeedControlStateMixin) -----------------------
impl DrivingState {
    /// `_disarm_speed_control()`: the whole session off, both controllers.
    pub fn disarm_speed_control(&mut self, ctx: &mut GameContext) {
        pending_once!("disarm_speed_control");
        self.cancel_cruise(ctx, false);
        self.cancel_keeper(ctx, false);
        self.speed_control_armed = false;
        self.speed_control_target_mph = None;
        self.speed_control_paused_at_stop = false;
        self.speed_control_transit_pause = false;
        self.speed_control_stop_honored = false;
    }

    /// `_pause_speed_control(*, resume_when_rolling=False)`.
    pub fn pause_speed_control(
        &mut self,
        ctx: &mut GameContext,
        resume_when_rolling: bool,
    ) -> bool {
        pending_once!("pause_speed_control");
        if !self.speed_control_armed {
            return false;
        }
        self.cancel_cruise(ctx, true);
        self.cancel_keeper(ctx, true);
        self.speed_control_paused_at_stop = true;
        self.speed_control_transit_pause = resume_when_rolling;
        self.speed_control_stop_honored = false;
        true
    }

    /// `_clear_stop_pause()`: a departure releases an arrival's pause.
    pub fn clear_stop_pause(&mut self) {
        pending_once!("clear_stop_pause");
        self.speed_control_paused_at_stop = false;
        self.speed_control_transit_pause = false;
        self.speed_control_stop_honored = false;
    }

    /// `_cancel_keeper(*, preserve_session=False)`.
    pub fn cancel_keeper(&mut self, _ctx: &mut GameContext, preserve_session: bool) {
        pending_once!("cancel_keeper");
        self.keeper_mph = None;
        self.keeper_throttle = 0.0;
        self.keeper_zone = String::new();
        self.keeper_zone_limit = None;
        self.keeper_ease_said = None;
        self.keeper_ease_target = None;
        self.keeper_snub = 0.0;
        self.keeper_overrun_s = 0.0;
        self.keeper_overrun_said = false;
        if !preserve_session {
            self.speed_control_armed = false;
            self.speed_control_target_mph = None;
        }
    }

    /// `_restricted_zone_limit_ahead()`: the work zone or heavy traffic close
    /// enough that automatic control should already be shedding for it.
    pub fn restricted_zone_limit_ahead(&mut self, _ctx: &mut GameContext) -> Option<(f64, String)> {
        pending_once!("restricted_zone_limit_ahead");
        None
    }

    /// `_keeper_ease_mi(target_mph, scale)`: how much road the keeper needs to
    /// shed to `target_mph` from here.
    pub fn keeper_ease_mi(&self, _target_mph: f64, _scale: f64) -> f64 {
        pending_once!("keeper_ease_mi");
        0.0
    }

    /// `_keeper_speed_ahead()`: the lower number up the road the keeper is
    /// easing for, and why ("construction", "heavy traffic", "turn", ...).
    pub fn keeper_speed_ahead(&mut self, _ctx: &mut GameContext) -> Option<(f64, String)> {
        pending_once!("keeper_speed_ahead");
        None
    }
}

// -- provided by driving_updates.rs (DrivingUpdateMixin) ---------------------------------
impl DrivingState {
    /// `_hazard_deadline_for(window_s, dodgeable=None)`: real seconds left
    /// before the assist takes the truck, leaving the driver `window_s` of
    /// their own. Counted DOWN by `_update_hazard`, so it is a remainder and
    /// never an absolute clock reading.
    pub fn hazard_deadline_for(&self, window_s: f64, _dodgeable: Option<bool>) -> f64 {
        pending_once!("hazard_deadline_for");
        HAZARD_MIN_REACTION_S.max(window_s)
    }

    /// `_hazard_target_mph(dodgeable=None)`: the speed that resolves the
    /// active hazard by brake alone.
    pub fn hazard_target_mph(&self, dodgeable: Option<bool>) -> f64 {
        pending_once!("hazard_target_mph");
        if dodgeable.unwrap_or(self.hazard_dodgeable) {
            HAZARD_CREEP_MPH
        } else {
            HAZARD_SAFE_MPH
        }
    }

    /// `_clear_hazard()`: resolve the pending hazard and say so.
    pub fn clear_hazard(&mut self, _ctx: &mut GameContext) {
        pending_once!("clear_hazard");
        self.hazard_deadline = None;
        self.hazard_names.clear();
    }

    /// `_release_hazard_brake()`: drop whatever the assist was holding.
    pub fn release_hazard_brake(&mut self) {
        pending_once!("release_hazard_brake");
        self.aeb_brake = 0.0;
        self.aeb_emergency = false;
        self.aeb_hold_s = 0.0;
        self.aeb_losing_s = 0.0;
        self.aeb_decel_mps2 = 0.0;
        self.aeb_last_speed_mps = None;
        self.automatic_braking_announced = false;
        self.automatic_braking_escalated = false;
    }

    /// `_settle_engine_to_idle()`: hand the engine audio down before a menu
    /// takes the frame loop away.
    pub fn settle_engine_to_idle(&mut self, _ctx: &mut GameContext) {
        pending_once!("settle_engine_to_idle");
    }

    /// `_auto_jake_max_stage()`: the highest retarder stage automation may use.
    pub fn auto_jake_max_stage(&self) -> i32 {
        pending_once!("auto_jake_max_stage");
        JAKE_STAGES
    }

    /// `_begin_enforcement_pull_over(...)`: the lights come on.
    #[allow(clippy::too_many_arguments)]
    pub fn begin_enforcement_pull_over(
        &mut self,
        _ctx: &mut GameContext,
        kind: &str,
        title: &str,
        summary: &str,
        fine: f64,
        reputation_hit: f64,
        return_message: &str,
        _lights_message: &str,
    ) {
        pending_once!("begin_enforcement_pull_over");
        self.pull_over = Some(PULL_OVER_LIGHTS.to_string());
        self.pull_over_start_mi = self.trip.position_mi;
        self.pull_over_signaled = false;
        self.pull_over_limit = 0.0;
        self.pull_over_over = 0.0;
        self.pull_over_kind = kind.to_string();
        self.pull_over_title = title.to_string();
        self.pull_over_summary = summary.to_string();
        self.pull_over_fine = fine;
        self.pull_over_reputation_hit = reputation_hit;
        self.pull_over_return = return_message.to_string();
    }
}

// -- provided by driving_controls.rs (DrivingControlsMixin) ------------------------------
impl DrivingState {
    /// `_calendar_phrase()`: the spoken date, or "" when the trip has none.
    pub fn calendar_phrase(&self, _ctx: &GameContext) -> String {
        pending_once!("calendar_phrase");
        String::new()
    }

    /// `emergency_shoulder_sleep_reason()`: why a shoulder sleep is allowed
    /// here, or None when it is not.
    pub fn emergency_shoulder_sleep_reason(&self, _ctx: &GameContext) -> Option<String> {
        pending_once!("emergency_shoulder_sleep_reason");
        None
    }
}

// -- provided by driving_damage.rs (DamageMixin) -----------------------------------------
impl DrivingState {
    /// `_announce_limp_cruise_cap()`: name a limp-mode cap under the set speed.
    pub fn announce_limp_cruise_cap(&mut self, _ctx: &mut GameContext) {
        pending_once!("announce_limp_cruise_cap");
    }
}

// -- provided by driving_engine_brake.rs (EngineBrakeMixin) ------------------------------
impl DrivingState {
    /// `_assist_jake_allowed()`: whether the stalk lets automation retard.
    pub fn assist_jake_allowed(&mut self, _ctx: &mut GameContext) -> bool {
        pending_once!("assist_jake_allowed");
        true
    }

    /// `_on_downgrade()`: a real grade the retarder is built to hold, rather
    /// than a target speed the drums should be arriving at.
    pub fn on_downgrade(&self) -> bool {
        pending_once!("on_downgrade");
        self.trip.truck.grade <= -0.01
    }
}

// -- provided by driving_facility_gate.rs (FacilityGateMixin) ----------------------------
impl DrivingState {
    /// `_post_gate_zone()`: the gate's own 15 comes back once the destination
    /// exit is taken.
    pub fn post_gate_zone(&mut self) {
        pending_once!("post_gate_zone");
    }

    /// `_seed_gate_grace_at_gate(message)`: open the reaction window the gate
    /// warning's own words are owed.
    pub fn seed_gate_grace_at_gate(&mut self, _ctx: &GameContext, _message: &str) {
        pending_once!("seed_gate_grace_at_gate");
    }

    /// `_gate_miss_pending()`: warning heard, window spent, still rolling.
    pub fn gate_miss_pending(&self) -> bool {
        pending_once!("gate_miss_pending");
        false
    }

    /// `_charge_scripted_loop(minutes)`: hours, fatigue and idle fuel for a
    /// scripted loop-back.
    pub fn charge_scripted_loop(&mut self, _ctx: &mut GameContext, _minutes: f64) {
        pending_once!("charge_scripted_loop");
    }

    /// `_handle_missed_facility_gate()`: the gate's own loop-back.
    pub fn handle_missed_facility_gate(&mut self, _ctx: &mut GameContext) {
        pending_once!("handle_missed_facility_gate");
    }
}

// -- provided by driving_enforcement.rs (EnforcementWatchMixin) --------------------------
impl DrivingState {
    /// `_scale_outranks_rest_planning()`: an open scale ahead claims T, and
    /// says so. True when it spoke and the rest key must stop here.
    pub fn scale_outranks_rest_planning(&mut self, _ctx: &mut GameContext) -> bool {
        pending_once!("scale_outranks_rest_planning");
        false
    }

    /// `_scale_claiming_exit(stop)`: a nearer open scale that outranks the
    /// exit the driver was about to arm.
    pub fn scale_claiming_exit(
        &mut self,
        _ctx: &mut GameContext,
        _stop: Option<&RoadStop>,
    ) -> Option<RoadStop> {
        pending_once!("scale_claiming_exit");
        None
    }
}

// -- provided by driving_pacenotes.rs (PacenoteMixin) ------------------------------------
impl DrivingState {
    /// `_pacenote_text(curve, ahead_mi, speed_mph)`: the curve call.
    pub fn pacenote_text(
        &self,
        _ctx: &GameContext,
        _curve: &RouteCurve,
        _ahead_mi: f64,
        _speed_mph: f64,
    ) -> SpokenMessage {
        pending_once!("pacenote_text");
        SpokenMessage::new("")
    }

    /// `_curve_call_still_true(curve)`: whether a rescued curve call is still
    /// worth speaking. None leaves the rescue ungated, as in Python.
    pub fn curve_call_still_true(&self, _curve: Option<&RouteCurve>) -> Option<bool> {
        pending_once!("curve_call_still_true");
        None
    }
}

// -- provided by driving_turns.rs (StreetTurnMixin) --------------------------------------
impl DrivingState {
    /// `_turn_cue_in_play()`: the corner being approached or judged.
    pub fn turn_cue_in_play(&self) -> Option<NavigationCue> {
        pending_once!("turn_cue_in_play");
        None
    }

    /// `_turn_window_mi()`: how far out a corner is called.
    pub fn turn_window_mi(&self) -> f64 {
        pending_once!("turn_window_mi");
        0.0
    }

    /// `_turn_approach_text(cue, ahead_mi)`: the approach call.
    pub fn turn_approach_text(
        &self,
        _ctx: &GameContext,
        _cue: &NavigationCue,
        _ahead_mi: f64,
    ) -> String {
        pending_once!("turn_approach_text");
        String::new()
    }

    /// `_turn_grace_seconds(message)`: the reaction window the corner call's
    /// own words are owed.
    pub fn turn_grace_seconds(&self, _ctx: &GameContext, _message: &str) -> f64 {
        pending_once!("turn_grace_seconds");
        0.0
    }
}

// -- provided by driving_menu_states.rs / driving_rest_states.rs -------------------------
//
// The screens `driving_events.py` pushes. Each is `ctx.push_state(X::new(...))`
// (or `replace_state`) once its module lands; the stub does nothing so a drive
// keeps running headlessly.
impl DrivingState {
    /// `ctx.push_state(RestStopState(ctx, self, stop, prefer_sleep=...))`.
    pub fn push_rest_stop_state(
        &mut self,
        _ctx: &mut GameContext,
        _stop: &RoadStop,
        _prefer_sleep: bool,
    ) {
        pending_once!("push_rest_stop_state");
    }

    /// `ctx.push_state(ParkingFullState(ctx, self, stop))`.
    pub fn push_parking_full_state(&mut self, _ctx: &mut GameContext, _stop: &RoadStop) {
        pending_once!("push_parking_full_state");
    }

    /// `ctx.push_state(ShoulderSleepConfirmationState(ctx, self, reason, mi))`.
    pub fn push_shoulder_sleep_confirmation(
        &mut self,
        _ctx: &mut GameContext,
        _reason: &str,
        _anchor_mi: f64,
    ) {
        pending_once!("push_shoulder_sleep_confirmation");
    }

    /// `ctx.replace_state(ArrivalState(ctx, self))`.
    pub fn replace_with_arrival_state(&mut self, _ctx: &mut GameContext) {
        pending_once!("replace_with_arrival_state");
    }

    /// `ctx.replace_state(FacilityArrivalState(ctx, self))`.
    pub fn replace_with_facility_arrival_state(&mut self, _ctx: &mut GameContext) {
        pending_once!("replace_with_facility_arrival_state");
    }
}
