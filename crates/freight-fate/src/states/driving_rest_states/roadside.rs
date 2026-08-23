//! The three roadside outcomes: a speeding stop, a non-speeding enforcement
//! stop, and the felony stop that ends a run.
//!
//! [`RoadsideExit`] is Python's `_RoadsideExitMixin`: a trait with provided
//! methods, no state of its own, shared by the first two screens.

use ff_core::models::enforcement;
use ff_core::pyfmt::{fmt_f, fmt_grouped};
use ff_core::pyrandom::PyRandom;
use ff_core::sim::hos;

use crate::app::{GameContext, Say};
use crate::discord_presence::PresenceState;
use crate::impl_state_for_menu;
use crate::states::base::{Menu, MenuCore, MenuItem};
use crate::states::city::CityMenuState;
use crate::states::driving::DrivingState;
use crate::states::driving_core::{
    advance_rest_clock, career_citations, citation_fine, clock_text, construction_zone_fine_clause,
    hos_mut_of, hos_of, profile_mut_of, profile_of, shut_down_engine, wake_air_instruction,
    DRIVE_PHASE_DELIVERY, FAILURE_TO_STOP_DAMAGE_PCT, FAILURE_TO_STOP_PROCESSING_MIN,
    INSPECTION_MIN, PULL_OVER_CLEAN_STOP_WARN_CHANCE,
};
use crate::states::driving_menu_states::DriveRef;
use crate::states::driving_updates::pending::EnforcementStopParams;

/// How a roadside stop lets the player go -- which depends on whether they
/// may still legally drive.
///
/// An ordinary ticket ends with merging back up to speed. A stop that just
/// pulled the licence cannot: the driver is not allowed to move the truck, so
/// offering the highway would be the game inviting them to break the rule it
/// just enforced, and there would be no way off the shoulder at all. In that
/// case the run ends here the way the felony stop already ends -- the load
/// goes back to dispatch and the driver is released to the terminal, where
/// "Wait out the CDL suspension" is waiting for them.
pub trait RoadsideExit: Menu {
    fn drive(&self) -> &DriveRef;

    fn licence_pulled(&self, ctx: &GameContext) -> bool {
        let Some(profile) = ctx.profile.as_ref() else {
            return false;
        };
        profile.driving_record.lifetime_disqualified
            || profile.driving_record.suspended(profile.game_hours)
    }

    fn roadside_exit_item(&self, ctx: &GameContext, highway_help: &str) -> MenuItem<Self> {
        if self.licence_pulled(ctx) {
            return MenuItem::new("Return to terminal", |s: &mut Self, ctx| {
                s.end_run_suspended(ctx)
            })
            .help(
                "Your licence is pulled, so the truck stays put. Dispatch takes the load back \
                 and you continue from the terminal.",
            );
        }
        MenuItem::new("Pull back onto the highway", |s: &mut Self, ctx| {
            s.go_back(ctx)
        })
        .help(highway_help)
    }

    /// Said as part of the outcome: why the run stops and what happens next.
    fn suspended_exit_text(&self, ctx: &GameContext) -> String {
        let profile = profile_of(ctx);
        let load = self
            .drive()
            .read(|d| {
                if d.phase == DRIVE_PHASE_DELIVERY && !d.job.bobtail {
                    format!(
                        "Dispatch takes the {} load back and reassigns it",
                        d.job.cargo.label
                    )
                } else {
                    "There is no loaded trailer to hand back, and the assignment is canceled"
                        .to_string()
                }
            })
            .unwrap_or_else(|| {
                "There is no loaded trailer to hand back, and the assignment is canceled"
                    .to_string()
            });
        let terminal = ctx
            .world
            .home_terminal(&profile.current_city)
            .map(|t| t.spoken_name())
            .unwrap_or_else(|_| "the terminal".to_string());
        if profile.driving_record.lifetime_disqualified {
            return format!(
                " You cannot drive this truck away: the licence is gone for good. {load}, and a \
                 relief driver takes the truck in. You are released to {terminal}."
            );
        }
        format!(
            " You cannot drive this truck away from here -- the licence is pulled as of now. \
             {load}, and a relief driver takes the truck in. You are released to {terminal}, \
             where you can wait the suspension out."
        )
    }

    /// Close out the run from the shoulder and release to the terminal.
    fn end_run_suspended(&mut self, ctx: &mut GameContext) {
        self.drive().clone().with(ctx, |d, ctx| {
            profile_mut_of(ctx).store_truck_condition(&d.trip.truck);
            let hours = d.trip.game_minutes / 60.0;
            let market_day = {
                let p = profile_mut_of(ctx);
                p.game_hours += hours;
                p.market_day()
            };
            let p = profile_mut_of(ctx);
            p.market.advance_to(market_day);
            p.active_trip = None;
            p.pay_advance_used_for_load = false;
        });
        ctx.save_profile();
        let city = CityMenuState::new(ctx, false);
        ctx.reset_to(city);
    }
}

// -- TrafficStopState ---------------------------------------------------------------------

const TRAFFIC_STOP_INTRO_HELP: &str =
    "The trooper has already decided. Press Enter or Escape to pull back onto the highway when \
     you are ready.";

/// A roadside traffic stop after a speeding pull-over: a spoken license and
/// logbook check, an on-the-spot ticket or a warning, then back to the road.
pub struct TrafficStopState {
    menu: MenuCore<Self>,
    driving: DriveRef,
    pub signaled: bool,
    pub over: f64,
    pub limit: f64,
    pub clean_stop: bool,
    /// The driver kept rolling through a failure-to-stop warning before
    /// finally pulling in: reckless-class behavior, not just speed.
    pub warned: bool,
    /// Whether the trooper clocked this speed inside roadwork, carried from
    /// where the violation happened rather than read at the shoulder.
    pub construction_zone: bool,
    outcome_text: String,
    presence_detail: String,
}

impl TrafficStopState {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        ctx: &mut GameContext,
        driving: &mut DrivingState,
        signaled: bool,
        over: f64,
        limit: f64,
        clean_stop: bool,
        warned: bool,
        construction_zone: bool,
    ) -> Self {
        let presence_detail = driving
            .presence_state(ctx)
            .map(|p| p.detail)
            .unwrap_or_default();
        let mut state = TrafficStopState {
            menu: MenuCore::new("Traffic stop").with_intro_help(TRAFFIC_STOP_INTRO_HELP),
            driving: DriveRef::active(ctx),
            signaled,
            over,
            limit,
            clean_stop,
            warned,
            construction_zone,
            outcome_text: String::new(),
            presence_detail,
        };
        state.resolve(ctx, driving);
        state
    }

    pub fn outcome_text(&self) -> &str {
        &self.outcome_text
    }

    /// Decide the outcome and apply any ticket immediately.
    fn resolve(&mut self, ctx: &mut GameContext, d: &mut DrivingState) {
        let rep = profile_of(ctx).career.reputation;
        let first = d.speeding_tickets == 0;
        // A warning for a first, marginal stop, or for a well-regarded driver
        // who pulled over promptly and wasn't egregiously over; otherwise a
        // ticket.
        let warning =
            (first && self.over < 15.0) || (rep >= 70.0 && self.signaled && self.over < 20.0);
        let over_text = ctx.settings.speed_text(self.over);
        let limit_text = ctx.settings.speed_text(self.limit);
        if warning {
            self.outcome_text = format!(
                "You were {over_text} over the {limit_text} limit. The trooper lets you off with \
                 a warning this time. Keep it down."
            );
            return;
        }
        // A prompt, fully-compliant stop earns a small chance the trooper lets
        // a ticket slide with a warning instead.
        // Named seed, quantised on where the stop happened: reloading the save
        // must not re-roll whether the trooper let it slide.
        let waiver_key = format!(
            "{}:police:waiver:{}",
            d.trip_seed,
            fmt_f(d.trip.position_mi, 1)
        );
        let waiver_roll = PyRandom::new_from_str(&waiver_key).random();
        if self.clean_stop && waiver_roll < PULL_OVER_CLEAN_STOP_WARN_CHANCE {
            self.outcome_text = format!(
                "You were {over_text} over the {limit_text} limit. I was gonna give you a \
                 ticket, but since you pulled over promptly, I'll let it go this time. Keep it \
                 down."
            );
            return;
        }
        // Priced by how far over the limit, how many citations the career
        // already carries, and whether it happened in a construction zone,
        // against the real state fine schedules.
        let fine = enforcement::speeding_citation_fine(
            self.over,
            career_citations(profile_of(ctx)),
            self.construction_zone,
        );
        d.speeding_tickets += 1;
        d.ticket_fines_paid += fine;
        let hit = hos::HOS_REPUTATION_HIT * if self.signaled { 0.7 } else { 1.0 };
        {
            let p = profile_mut_of(ctx);
            p.money -= fine;
            p.career.reputation = (rep - hit).max(0.0);
        }
        ctx.audio.play("ui/error");
        let serious = enforcement::is_serious_speed(self.over) || self.warned;
        let ladder = d.log_enforcement(ctx, fine, serious, false);
        self.outcome_text = format!(
            "You were {over_text} over the {limit_text} limit. Speeding ticket: {} dollars, paid \
             on the spot, and a reputation hit.{}",
            fmt_grouped(fine, 0),
            construction_zone_fine_clause(self.construction_zone)
        );
        if !ladder.is_empty() {
            self.outcome_text.push_str(&format!(" {ladder}"));
        }
        if self.licence_pulled(ctx) {
            let tail = self.suspended_exit_text(ctx);
            self.outcome_text.push_str(&tail);
        }
    }
}

impl RoadsideExit for TrafficStopState {
    fn drive(&self) -> &DriveRef {
        &self.driving
    }
}

impl Menu for TrafficStopState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        vec![self.roadside_exit_item(
            ctx,
            "Signal, check your mirror, and merge back up to speed.",
        )]
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let polite = if self.signaled {
            " You signaled and pulled over promptly."
        } else {
            ""
        };
        let outcome = self.outcome_text.clone();
        let current = self.current_text(ctx);
        ctx.say_with(
            format!(
                "You stop on the shoulder and the trooper walks up for a license and logbook \
                 check.{polite} {outcome} {current}"
            ),
            Say::new(),
        );
    }

    fn presence(&self, _ctx: &GameContext) -> Option<PresenceState> {
        Some(PresenceState::new("Pulled over", &self.presence_detail))
    }

    fn online_presence(&self, ctx: &GameContext) -> Option<PresenceState> {
        self.presence(ctx)
    }

    fn go_back(&mut self, ctx: &mut GameContext) {
        ctx.pop_state();
        ctx.say_with("Back on the highway. Watch your speed.", Say::new());
    }
}

impl_state_for_menu!(TrafficStopState);

// -- EnforcementStopState -----------------------------------------------------------------

const ENFORCEMENT_STOP_INTRO_HELP: &str =
    "Press Enter or Escape to pull back onto the highway when you are ready.";

/// Roadside enforcement stop for non-speeding violations.
pub struct EnforcementStopState {
    menu: MenuCore<Self>,
    driving: DriveRef,
    pub summary: String,
    pub construction_zone: bool,
    pub fine: f64,
    pub reputation_hit: f64,
    pub signaled: bool,
    pub return_message: String,
    pub out_of_service: bool,
    pub warned: bool,
    /// A scale bypass got caught precisely because the inspection was
    /// skipped. The trooper does not just write the ticket and wave you on --
    /// they do the inspection right there, on the shoulder, the same
    /// `INSPECTION_MIN` the check-in lane would have cost you.
    pub inspection_on_stop: bool,
    outcome_text: String,
    /// Whether the stop has been told once already. See `announce_entry`: the
    /// fine is charged here, in `resolve`, exactly once, and a later telling
    /// has to sound like history rather than a fresh charge.
    stop_announced: bool,
    presence_detail: String,
}

impl EnforcementStopState {
    pub fn new(
        ctx: &mut GameContext,
        driving: &mut DrivingState,
        params: EnforcementStopParams,
    ) -> Self {
        let presence_detail = driving
            .presence_state(ctx)
            .map(|p| p.detail)
            .unwrap_or_default();
        // Repeat offenders pay more for the same stop and nothing caps it, and
        // a construction zone doubles whatever that came to -- one schedule
        // for every citation in the game, priced in models/enforcement.
        let fine = citation_fine(
            params.fine,
            career_citations(profile_of(ctx)),
            params.construction_zone,
            None,
        );
        let mut state = EnforcementStopState {
            menu: MenuCore::new(&params.title).with_intro_help(ENFORCEMENT_STOP_INTRO_HELP),
            driving: DriveRef::active(ctx),
            summary: params.summary,
            construction_zone: params.construction_zone,
            fine,
            reputation_hit: params.reputation_hit,
            signaled: params.signaled,
            return_message: params.return_message,
            out_of_service: params.out_of_service,
            warned: params.warned,
            inspection_on_stop: params.inspection_on_stop,
            outcome_text: String::new(),
            stop_announced: false,
            presence_detail,
        };
        state.resolve(ctx, driving);
        state
    }

    pub fn outcome_text(&self) -> &str {
        &self.outcome_text
    }

    fn resolve(&mut self, ctx: &mut GameContext, d: &mut DrivingState) {
        d.ticket_fines_paid += self.fine;
        let hit = self.reputation_hit * if self.signaled { 0.8 } else { 1.0 };
        {
            let p = profile_mut_of(ctx);
            p.money -= self.fine;
            p.career.reputation = (p.career.reputation - hit).max(0.0);
        }
        ctx.audio.play("ui/error");
        let ladder = d.log_enforcement(ctx, self.fine, self.warned, false);
        self.outcome_text = format!(
            "Fine: {} dollars, paid on the spot, and a reputation hit.{}",
            fmt_grouped(self.fine, 0),
            construction_zone_fine_clause(self.construction_zone)
        );
        if !ladder.is_empty() {
            self.outcome_text.push_str(&format!(" {ladder}"));
        }
        if self.out_of_service {
            // The ten hours pass HERE, parked on the shoulder with the
            // officer's order in hand -- never as a silent mid-drive jump.
            // Capture the plain-language WHY before the reset wipes the
            // ledger: the stop must explain itself completely (owner ask,
            // 2026-07-24).
            let causes = hos_of(ctx).violation_causes(&ctx.settings.hos_mode);
            let why = if causes.is_empty() {
                String::new()
            } else {
                format!(" The order stands because {}.", causes.join(" and "))
            };
            // Ten hours parked is a real overnight fast-forward, the same as
            // every other sleep path -- the engine must not idle through the
            // whole order (log, 2026-08-12: it did, and the audio froze at
            // pre-stop revs for the entire ten hours).
            let engine_off = shut_down_engine(d, ctx);
            d.place_out_of_service(ctx);
            let lead = if engine_off.trim().is_empty() {
                String::new()
            } else {
                format!(" {}", engine_off.trim())
            };
            self.outcome_text.push_str(&format!(
                "{lead}{why} Out of service: ten hours pass parked on the shoulder before you \
                 may roll. It is now {}, your hours of service are reset, and you wake rested -- \
                 but the delivery deadline kept counting the whole time.{}",
                clock_text(d.trip.local_hour()),
                wake_air_instruction(d, ctx, false)
            ));
        }
        if self.inspection_on_stop {
            // Reuses the same check-in cost the scale itself would have
            // charged -- the driver dodged the lane, not the inspection.
            advance_rest_clock(
                d,
                ctx,
                INSPECTION_MIN,
                Some("on_duty_not_driving"),
                "weigh station bypass inspection",
            );
            hos_mut_of(ctx).on_duty(INSPECTION_MIN);
            self.outcome_text.push_str(&format!(
                " Since you didn't stop at the scale, they run the full inspection right here on \
                 the shoulder: {} minutes on the clock.",
                fmt_f(INSPECTION_MIN, 0)
            ));
        }
        if self.licence_pulled(ctx) {
            let tail = self.suspended_exit_text(ctx);
            self.outcome_text.push_str(&tail);
        }
    }
}

impl RoadsideExit for EnforcementStopState {
    fn drive(&self) -> &DriveRef {
        &self.driving
    }
}

impl Menu for EnforcementStopState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        vec![self.roadside_exit_item(
            ctx,
            "Signal, check your mirror, and merge back up to speed.",
        )]
    }

    /// The stop, said once as it happens and afterwards as history.
    ///
    /// `resolve` runs in the constructor and charges the fine exactly once,
    /// but this line was word-for-word identical every time it was spoken, so
    /// a second telling was indistinguishable from a second charge -- and a
    /// driver with no screen has no other way to tell them apart. Tester
    /// Darren's log has it twice, three seconds apart, on a 1,200 dollar
    /// work-zone citation (I-75, 2026-08-18).
    ///
    /// Not silenced, because re-reading the stop is the only route back to
    /// the detail. Led in the past tense instead, so the money is plainly
    /// already spent.
    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let polite = if self.signaled {
            " You signaled and pulled over promptly."
        } else {
            ""
        };
        let summary = self.summary.clone();
        let outcome = self.outcome_text.clone();
        let current = self.current_text(ctx);
        if self.stop_announced {
            ctx.say_with(
                format!(
                    "Reading back the stop you have already settled. {summary} {outcome} {current}"
                ),
                Say::new(),
            );
            return;
        }
        self.stop_announced = true;
        ctx.say_with(
            format!(
                "You stop on the shoulder for an enforcement inspection.{polite} {summary} \
                 {outcome} {current}"
            ),
            Say::new(),
        );
    }

    fn presence(&self, _ctx: &GameContext) -> Option<PresenceState> {
        Some(PresenceState::new("Pulled over", &self.presence_detail))
    }

    fn go_back(&mut self, ctx: &mut GameContext) {
        ctx.pop_state();
        let message = self.return_message.clone();
        ctx.say_with(message, Say::new());
    }
}

impl_state_for_menu!(EnforcementStopState);

// -- FelonyStopState ----------------------------------------------------------------------

const FELONY_INTRO_HELP: &str =
    "Press Enter or Escape to continue from the terminal after the enforcement stop.";

/// Failure-to-stop outcome after the player ignores an active siren.
pub struct FelonyStopState {
    menu: MenuCore<Self>,
    pub load_lost: bool,
    summary: String,
    standing_text: String,
}

impl FelonyStopState {
    pub fn new(ctx: &mut GameContext, driving: &mut DrivingState) -> Self {
        let load_lost = driving.phase == DRIVE_PHASE_DELIVERY && !driving.job.bobtail;
        let mut state = FelonyStopState {
            menu: MenuCore::new("Felony stop").with_intro_help(FELONY_INTRO_HELP),
            load_lost,
            summary: String::new(),
            standing_text: String::new(),
        };
        state.resolve(ctx, driving);
        state
    }

    pub fn summary(&self) -> &str {
        &self.summary
    }

    fn resolve(&mut self, ctx: &mut GameContext, d: &mut DrivingState) {
        d.failure_to_stop_count += 1;
        // The felony is priced like every other citation: the 5,000-dollar
        // statutory top of range, scaled by what this driver already has on
        // the record and by where the chase was.
        let zone = d.trip.in_construction_zone();
        let fine = citation_fine(
            enforcement::FAILURE_TO_STOP_FINE,
            career_citations(profile_of(ctx)),
            zone,
            None,
        );
        d.ticket_fines_paid += fine;
        {
            let p = profile_mut_of(ctx);
            p.money -= fine;
            p.career.reputation = (p.career.reputation - hos::HOS_REPUTATION_HIT * 3.0).max(0.0);
        }
        // The part that used to go nowhere: fleeing a stop in a commercial
        // vehicle is a major offense, and the licence answers for it.
        self.standing_text = d.log_enforcement(ctx, fine, false, true);
        // add_damage, not a raw assignment: spike damage has to cross the
        // bands so a spiked truck can go out of service like any other wreck.
        d.trip.truck.add_damage(FAILURE_TO_STOP_DAMAGE_PCT, true);
        d.trip.truck.velocity_mps = 0.0;
        d.trip.truck.throttle = 0.0;
        d.trip.truck.brake = 1.0;
        d.trip.truck.set_parking_brake();
        advance_rest_clock(
            d,
            ctx,
            FAILURE_TO_STOP_PROCESSING_MIN,
            Some("on_duty_not_driving"),
            "felony failure-to-stop enforcement",
        );
        hos_mut_of(ctx).on_duty(FAILURE_TO_STOP_PROCESSING_MIN);
        profile_mut_of(ctx).store_truck_condition(&d.trip.truck);
        let hours = d.trip.game_minutes / 60.0;
        let market_day = {
            let p = profile_mut_of(ctx);
            p.game_hours += hours;
            p.market_day()
        };
        {
            let p = profile_mut_of(ctx);
            p.market.advance_to(market_day);
            p.active_trip = None;
            p.pay_advance_used_for_load = false;
        }
        ctx.save_profile();

        let load_text = if self.load_lost {
            format!(
                "Dispatch cancels the {} load; there is no pay for this run.",
                d.job.cargo.label
            )
        } else {
            "There was no loaded trailer to lose, but the active assignment is canceled."
                .to_string()
        };
        let terminal = ctx
            .world
            .home_terminal(&profile_of(ctx).current_city)
            .map(|t| t.spoken_name())
            .unwrap_or_else(|_| "the terminal".to_string());
        self.summary = format!(
            "Troopers laid spike strips across the lane after you kept driving with lights and \
             siren behind you. Felony failure-to-stop fine: {} dollars, paid on the spot, with a \
             major reputation hit.{} Spike strips added {} percent truck damage, and processing \
             took {} hours. {load_text} You are released back to {terminal}.",
            fmt_grouped(fine, 0),
            construction_zone_fine_clause(zone),
            fmt_f(FAILURE_TO_STOP_DAMAGE_PCT, 0),
            fmt_f(FAILURE_TO_STOP_PROCESSING_MIN / 60.0, 0)
        );
        if !self.standing_text.is_empty() {
            self.summary.push_str(&format!(" {}", self.standing_text));
        }
    }
}

impl Menu for FelonyStopState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn build_items(&mut self, _ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        vec![
            MenuItem::new("Return to terminal", |s: &mut Self, ctx| s.go_back(ctx))
                .help("End the canceled run and continue from the city terminal."),
        ]
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let title = self.menu.title.clone();
        let summary = self.summary.clone();
        let current = self.current_text(ctx);
        ctx.say_with(format!("{title}. {summary} {current}"), Say::new());
    }

    fn go_back(&mut self, ctx: &mut GameContext) {
        let city = CityMenuState::new(ctx, false);
        ctx.reset_to(city);
    }
}

impl_state_for_menu!(FelonyStopState);
