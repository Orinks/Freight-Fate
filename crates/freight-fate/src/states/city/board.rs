//! The dispatch board and its per-job detail reader (`JobBoardState`,
//! `JobDetailState`).

use std::collections::HashSet;

use serde_json::Value;

use ff_core::models::business::{
    build_business_settlement, has_weigh_station_transponder, is_owner_operator, pay_label,
    BusinessSettlement, SettlementTerms, INDEPENDENT_AUTHORITY,
};
use ff_core::models::career_objectives::career_objective;
use ff_core::models::career_training::{
    is_company_training_profile, training_guidance, training_recommendation_score, TrainingStage,
};
use ff_core::models::carrier_fleet::{
    assignment_reason_text, equipment_held_back, equipment_hold_text, slip_seats,
};
use ff_core::models::dispatch_policy::{
    declines_remaining, dispatch_policy, DECLINE_REPUTATION_PENALTY, SENIOR_LOAD_CHOICE_LEVEL,
};
use ff_core::models::enforcement;
use ff_core::models::jobs::{facility_text, lane_key, route_drive_hours, DescribeOptions, Job};
use ff_core::models::profile::Profile;
use ff_core::models::trailers::{
    compatible_with_programs, owned_trailer_for_cargo, required_program_text,
};
use ff_core::playtest_levers::forced_dispatch_destination;
use ff_core::pyfmt::{fmt_f, fmt_grouped};
use ff_core::sim::hos::limits;
use ff_core::sim::timezones::{appointment_text, city_zone};

use crate::app::{GameContext, Say, SharedState};
use crate::impl_state_for_menu;
use crate::states::base::{InputEvent, Key, Menu, MenuCore, MenuItem};
use crate::states::city::{
    base_menu_current_help, base_menu_handle_event, first_day_guidance_active, first_dispatch_done,
    home_terminal, launch_driving, profile, profile_mut, sleeps_needed, DrivingLaunch,
    LaunchAnnouncement, DRIVE_PHASE_DELIVERY, DRIVE_PHASE_PICKUP, PICKUP_CHECK_IN_MIN,
    PICKUP_LOADING_MIN,
};

/// The board's class-level `intro_help` (the browsable board; an assigned
/// board swaps in its own on construction).
pub const JOB_BOARD_INTRO_HELP: &str =
    "Each entry is one dispatch. Enter accepts the dispatch and \
     creates a local deadhead pickup drive from your terminal to \
     the named origin facility. Jobs name their origin and \
     destination facilities, and cargo depends on the facility \
     type. Tab repeats the freight market watch. Escape returns to \
     the terminal.";

const ASSIGNED_INTRO_HELP: &str = "Dispatch assigned this load. Enter on the assignment accepts \
     it and creates a local deadhead pickup drive from your \
     terminal to the named origin facility. Declining draws \
     another load, but refusals cost reputation from a small \
     budget that refills at your next promotion. Press F1 on the \
     assignment to review the job details line by line. Escape \
     returns to the terminal.";

// -- shared job wording ----------------------------------------------------------------

fn settlement_for(p: &Profile, job: &Job, with_reputation: bool) -> BusinessSettlement {
    let owned: Vec<String> = p.visible_owned_trailers();
    let owned_refs: Vec<&str> = owned.iter().map(String::as_str).collect();
    build_business_settlement(
        &p.business_status,
        job,
        job.pay,
        true,
        0.0,
        &SettlementTerms {
            carrier_key: Some(&p.carrier_key),
            owned_trailers: &owned_refs,
            reputation: if with_reputation {
                Some(p.career.reputation)
            } else {
                None
            },
            transponder: has_weigh_station_transponder(p),
        },
    )
}

/// `JobBoardState._locked_reason`: why this driver cannot take the job, or "".
pub fn locked_reason(p: &Profile, job: &Job) -> String {
    let endorsements: Vec<&str> = p.career.endorsements().into_iter().collect();
    let programs = p.active_trailer_programs();
    let program_refs: Vec<&str> = programs.iter().map(String::as_str).collect();
    job.locked_reason(
        &endorsements,
        p.career.level(),
        Some(&program_refs),
        !is_owner_operator(&p.business_status),
    )
}

/// `JobBoardState._trailer_note`.
pub fn trailer_note(p: &Profile, job: &Job) -> String {
    if !is_owner_operator(&p.business_status) {
        return "Carrier trailer provided.".to_string();
    }
    let cargo_key = job.cargo.key;
    if p.business_status == INDEPENDENT_AUTHORITY {
        if let Some(owned) = owned_trailer_for_cargo(cargo_key, p.visible_owned_trailers()) {
            return format!(
                "Owned trailer: {}. Direct freight gross; \
                 owned-trailer reserve at settlement.",
                owned.label
            );
        }
        if compatible_with_programs(cargo_key, p.active_trailer_programs()) {
            return format!(
                "Trailer program: {}. \
                 Direct freight gross; program charge at settlement.",
                required_program_text(cargo_key)
            );
        }
        return format!(
            "Needs {} trailer program or owned trailer.",
            required_program_text(cargo_key)
        );
    }
    if compatible_with_programs(cargo_key, p.active_trailer_programs()) {
        return format!("Trailer program: {}.", required_program_text(cargo_key));
    }
    format!(
        "Needs {} trailer program.",
        required_program_text(cargo_key)
    )
}

fn market_preview(business: &BusinessSettlement) -> String {
    let charges = business.business_charge_total();
    if charges > 0.0 {
        return format!(
            "Estimated take-home before advances: \
             {} dollars after \
             {} dollars business costs.",
            fmt_grouped(business.net_before_advance, 0),
            fmt_grouped(charges, 0)
        );
    }
    format!(
        "Estimated driver pay before advances: {} dollars.",
        fmt_grouped(business.net_before_advance, 0)
    )
}

/// Board line for a carrier-ASSIGNED reposition.
///
/// Skips Job.describe() and build_business_settlement() on purpose:
/// those price and phrase a real load's cargo, and running a
/// zero-weight reposition through the same math would show the
/// loaded per-mile wage floor instead of job.pay's already-reduced
/// empty-mile rate -- a preview the settlement then would not honor.
fn describe_reposition(ctx: &GameContext, total: usize, job: &Job, index: Option<usize>) -> String {
    let prefix = match index {
        Some(i) => format!("Job {i} of {total}: "),
        None => String::new(),
    };
    format!(
        "{prefix}Carrier-assigned reposition: drive empty to \
         {}, \
         {}. No cargo. \
         Pays {} dollars, the reduced empty-mile rate. \
         You will see the {} dispatch board on arrival.",
        job.spoken_destination(),
        ctx.settings.distance_text(job.distance_mi, false),
        fmt_grouped(job.pay, 0),
        job.spoken_destination()
    )
}

/// `JobBoardState._describe_job(job, index)`: `index` is the 1-based
/// board position, `total` the board size.
pub fn describe_job(ctx: &GameContext, total: usize, job: &Job, index: Option<usize>) -> String {
    if job.bobtail {
        return describe_reposition(ctx, total, job, index);
    }
    let p = profile(ctx);
    let business = settlement_for(p, job, true);
    let note = trailer_note(p, job);
    let preview = market_preview(&business);
    let distance = ctx.settings.distance_text(job.distance_mi, false);
    job.describe(&DescribeOptions {
        index,
        total: index.map(|_| total),
        pay_label: pay_label(&p.business_status),
        trailer_note: &note,
        display_pay: Some(business.gross_pay),
        market_preview: &preview,
        distance_text: &distance,
    })
}

// -- JobBoardState ------------------------------------------------------------------------

pub struct JobBoardState {
    menu: MenuCore<Self>,
    pub jobs: Vec<Job>,
    /// Index of the job whose hours warning was already heard once.
    confirm_risky_job: Option<usize>,
    session_declined: HashSet<usize>,
    assigned_queue: Vec<usize>,
}

impl JobBoardState {
    pub fn new(ctx: &GameContext, jobs: Vec<Job>) -> Self {
        let mut state = JobBoardState {
            menu: MenuCore::new("Dispatch board").with_intro_help(JOB_BOARD_INTRO_HELP),
            jobs,
            confirm_risky_job: None,
            session_declined: HashSet::new(),
            assigned_queue: Vec::new(),
        };
        if dispatch_policy(profile(ctx)).assigns_load {
            state.assigned_queue = state.assignment_queue(ctx);
        }
        if state.assigned_mode() {
            state.menu.intro_help = ASSIGNED_INTRO_HELP.to_string();
        } else if let Some(recommended) = state.recommended_job_index(ctx) {
            if state.recommendation_label(ctx).is_some() {
                state.menu.index = recommended;
            }
        }
        state
    }

    /// Dispatch picks the load: new company hires get an assignment,
    /// not a browsable board. Falls back to browsing when nothing on the
    /// board is unlocked, so the player can still hear what is there.
    pub fn assigned_mode(&self) -> bool {
        !self.assigned_queue.is_empty()
    }

    pub fn intro_help(&self) -> &str {
        &self.menu.intro_help
    }

    /// `_assigned_job`: the load dispatch is offering right now.
    pub fn assigned_job(&self) -> &Job {
        &self.jobs[self.assigned_queue[0]]
    }

    /// `_assigned_queue`: the order dispatch will offer the board in.
    pub fn assigned_queue(&self) -> &[usize] {
        &self.assigned_queue
    }

    fn describe(&self, ctx: &GameContext, job: &Job, index: Option<usize>) -> String {
        describe_job(ctx, self.jobs.len(), job, index)
    }

    fn announce_assignment(&mut self, ctx: &mut GameContext) {
        let p = profile(ctx);
        let remaining = declines_remaining(p);
        let decline_note = if self.assigned_queue.len() < 2 {
            "No alternative freight is available to request.".to_string()
        } else if remaining > 0 {
            format!(
                "You can decline {remaining} more assigned \
                 load{} before your next \
                 promotion, but refusals cost dispatch trust.",
                if remaining != 1 { "s" } else { "" }
            )
        } else {
            "You are out of declines until your next promotion, so \
             dispatch expects you to run this load."
                .to_string()
        };
        let objective_text = match self.training_recommendation_label(ctx) {
            Some(label) => format!(
                "First-day objective: run this {label} load \
                 cleanly to start building your record with dispatch. "
            ),
            None => format!("Career objective: {}. ", career_objective(p).title),
        };
        let hos_note = if self.job_exceeds_current_hos(ctx, self.assigned_job()) {
            "This assignment may need a legal rest before delivery; you will \
             get an hours warning at accept. "
        } else {
            ""
        };
        let market = p.market.summary();
        let current = self.current_text(ctx);
        ctx.say(&format!(
            "Dispatch board. Dispatch assigns your load and route while you \
             are a new company hire; load choice opens at level \
             {SENIOR_LOAD_CHOICE_LEVEL}. Listed amounts are carrier gross; \
             your settlement pays driver wages. {objective_text}\
             {decline_note} {hos_note}{market} {current}"
        ));
    }

    fn build_assignment_items(&mut self, ctx: &GameContext) -> Vec<MenuItem<Self>> {
        let index = self.assigned_queue[0];
        let job = &self.jobs[index];
        let assignment_help = if job.bobtail {
            "Dispatch assigned this reposition; it is an empty deadhead, \
             not a load. Accepting starts that drive directly -- no pickup \
             facility to stop at. Route inspection after accepting covers \
             rest, fuel, toll, weather, and restrictions."
        } else {
            "Dispatch assigned this load; new hires run the load and \
             lane dispatch picks. Accepting creates a local deadhead \
             pickup drive from your terminal to the named origin \
             facility. Route inspection after pickup covers rest, fuel, \
             toll, weather, and restrictions."
        };
        let mut items = vec![MenuItem::new(
            format!(
                "Accept assigned dispatch: {}",
                self.describe(ctx, job, None)
            ),
            move |s: &mut Self, ctx| s.accept(ctx, index),
        )
        .help(assignment_help)];
        let remaining = declines_remaining(profile(ctx));
        if self.assigned_queue.len() > 1 && remaining > 0 {
            items.push(
                MenuItem::new(
                    format!(
                        "Decline and request another load: \
                         {remaining} decline{} left",
                        if remaining != 1 { "s" } else { "" }
                    ),
                    |s: &mut Self, ctx| s.decline_assignment(ctx),
                )
                .help(
                    "Turn the assigned load down and let dispatch draw \
                     another. Refusals cost reputation, and the decline \
                     budget only refills when you reach the next level.",
                ),
            );
        }
        if self.assigned_queue.len() > 1 {
            items.push(
                MenuItem::new("Review the rest of today's board", |s: &mut Self, ctx| {
                    s.review_locked_board(ctx)
                })
                .help(format!(
                    "Hear the other loads dispatch posted today. They are \
                     flavor for now: assigned loads only until load choice \
                     unlocks at level {SENIOR_LOAD_CHOICE_LEVEL}."
                )),
            );
        }
        items.push(MenuItem::new("Back to terminal", |s: &mut Self, ctx| {
            s.go_back(ctx)
        }));
        items
    }

    /// Speak the pool behind the assignment, as flavor (owner design,
    /// 2026-07-24): the offer pool widens with every level, and growth the
    /// driver cannot hear is not a reward yet. On demand, never automatic.
    pub fn review_locked_board(&mut self, ctx: &mut GameContext) {
        let lines: Vec<String> = self.assigned_queue[1..]
            .iter()
            .map(|&i| &self.jobs[i])
            .map(|job| {
                if job.bobtail {
                    format!(
                        "a reposition to {}, \
                         {}, no cargo",
                        job.spoken_destination(),
                        ctx.settings.distance_text(job.distance_mi, false)
                    )
                } else {
                    format!(
                        "{} tons of {} to \
                         {}, {}",
                        fmt_f(job.weight_tons, 0),
                        job.cargo.label,
                        job.spoken_destination(),
                        ctx.settings.distance_text(job.distance_mi, false)
                    )
                }
            })
            .collect();
        ctx.say(&format!(
            "Dispatch also posted today: {}. \
             Declining your assignment draws the first of these next. \
             Postings change with each market day; load choice unlocks \
             at level {SENIOR_LOAD_CHOICE_LEVEL}.",
            lines.join("; ")
        ));
    }

    /// Board indices dispatch already re-drew past, remembered with the
    /// cached board so leaving and reopening does not re-offer them.
    fn declined_indices(&self, ctx: &GameContext) -> HashSet<usize> {
        let mut declined = self.session_declined.clone();
        if let Some(cache) = profile(ctx)
            .dispatch_board_cache
            .as_ref()
            .and_then(Value::as_object)
        {
            if let Some(list) = cache.get("declined").and_then(Value::as_array) {
                for index in list {
                    if let Some(n) = index.as_f64() {
                        declined.insert(n as usize);
                    }
                }
            }
        }
        declined
    }

    fn remember_decline(&mut self, ctx: &mut GameContext, index: usize) {
        self.session_declined.insert(index);
        if let Some(cache) = profile_mut(ctx)
            .dispatch_board_cache
            .as_mut()
            .and_then(Value::as_object_mut)
        {
            let mut declined: Vec<i64> = cache
                .get("declined")
                .and_then(Value::as_array)
                .map(|list| {
                    list.iter()
                        .filter_map(Value::as_f64)
                        .map(|n| n as i64)
                        .collect()
                })
                .unwrap_or_default();
            if !declined.contains(&(index as i64)) {
                declined.push(index as i64);
            }
            cache.insert("declined".into(), Value::from(declined));
        }
    }

    pub fn decline_assignment(&mut self, ctx: &mut GameContext) {
        if declines_remaining(profile(ctx)) <= 0 {
            ctx.audio.play("ui/error");
            ctx.say(
                "Dispatch has no patience left for refusals. Run this load; \
                 declines refill at your next promotion.",
            );
            return;
        }
        {
            let p = profile_mut(ctx);
            p.career.dispatch_declines_used += 1;
            p.career.reputation = (p.career.reputation - DECLINE_REPUTATION_PENALTY).max(0.0);
        }
        let declined = self.assigned_queue[0];
        self.remember_decline(ctx, declined);
        self.assigned_queue = self.assignment_queue(ctx);
        ctx.save_profile();
        ctx.audio.play("ui/notify");
        self.refresh(ctx, false);
        let remaining = declines_remaining(profile(ctx));
        let note = if remaining > 0 {
            format!(
                "You have {remaining} decline{} left.",
                if remaining != 1 { "s" } else { "" }
            )
        } else {
            "That was your last decline until your next promotion.".to_string()
        };
        let described = self.describe(ctx, self.assigned_job(), None);
        ctx.say(&format!(
            "Load declined. The refusal goes on your service record with \
             dispatch. {note} New assignment: \
             {described}"
        ));
    }

    fn job_label(&self, ctx: &GameContext, job: &Job, index: usize) -> String {
        let label = self.describe(ctx, job, Some(index));
        if self.recommended_job_index(ctx) == Some(index - 1) {
            let Some(recommendation) = self.recommendation_label(ctx) else {
                return label;
            };
            return format!("Recommended dispatch, {recommendation}: {label}");
        }
        label
    }

    fn recommendation_label(&self, ctx: &GameContext) -> Option<String> {
        if let Some(label) = self.training_recommendation_label(ctx) {
            return Some(label);
        }
        let p = profile(ctx);
        if first_dispatch_done(p) {
            return Some(career_objective(p).recommendation);
        }
        if is_company_training_profile(p) {
            return Some(career_objective(p).recommendation);
        }
        None
    }

    fn training_recommendation_label(&self, ctx: &GameContext) -> Option<String> {
        let p = profile(ctx);
        if !is_company_training_profile(p) {
            return None;
        }
        let guidance = training_guidance(p);
        if guidance.stage == TrainingStage::FirstDispatch && !first_dispatch_done(p) {
            return Some(guidance.recommendation_label);
        }
        None
    }

    fn focused_recommendation_is_spoken(&self, ctx: &GameContext) -> bool {
        self.recommendation_label(ctx).is_some()
            && self.recommended_job_index(ctx) == Some(self.menu.index)
    }

    /// (score, index) for each unlocked job; lower scores fit better.
    fn scored_candidates(&self, ctx: &GameContext) -> Vec<(f64, usize)> {
        let p = profile(ctx);
        let mut candidates: Vec<(f64, usize)> = Vec::new();
        for (index, job) in self.jobs.iter().enumerate() {
            if !locked_reason(p, job).is_empty() {
                continue;
            }
            if is_owner_operator(&p.business_status) {
                let business = settlement_for(p, job, false);
                candidates.push((-business.net_before_advance, index));
            } else if training_guidance(p).stage != TrainingStage::NormalGuidance {
                candidates.push((training_recommendation_score(p, job), index));
            } else {
                candidates.push((job.distance_mi, index));
            }
        }
        candidates
    }

    fn recommended_job_index(&self, ctx: &GameContext) -> Option<usize> {
        let mut candidates = self.scored_candidates(ctx);
        sort_scored(&mut candidates);
        candidates.first().map(|c| c.1)
    }

    /// Unlocked jobs in the order dispatch would assign them, best first.
    ///
    /// Declined loads move to the back: dispatch re-offers them only after
    /// the fresh candidates run out, and reopening the board does not put a
    /// refused load straight back on the driver.
    fn assignment_queue(&self, ctx: &GameContext) -> Vec<usize> {
        let mut candidates = self.scored_candidates(ctx);
        sort_scored(&mut candidates);
        let ordered: Vec<usize> = candidates.into_iter().map(|c| c.1).collect();
        let declined = self.declined_indices(ctx);
        let mut fresh: Vec<usize> = ordered
            .iter()
            .copied()
            .filter(|i| !declined.contains(i))
            .collect();
        let reoffered: Vec<usize> = ordered
            .iter()
            .copied()
            .filter(|i| declined.contains(i))
            .collect();
        // Lane variety: dispatch prefers a lane the driver has not just run.
        // A stable partition, so score order still rules inside each group,
        // and when every candidate is a recent lane nothing changes -- the
        // nudge can delay a repeat, never block dispatch.
        let recent: HashSet<&String> = profile(ctx).recent_lanes.iter().collect();
        if !recent.is_empty() {
            let world = ctx.world;
            let is_recent = |i: &usize| recent.contains(&lane_key(world, &self.jobs[*i]));
            let mut not_recent: Vec<usize> =
                fresh.iter().copied().filter(|i| !is_recent(i)).collect();
            let recent_ones: Vec<usize> = fresh.iter().copied().filter(is_recent).collect();
            not_recent.extend(recent_ones);
            fresh = not_recent;
        }
        let mut queue = fresh;
        queue.extend(reoffered);
        let forced = forced_dispatch_destination();
        if !forced.is_empty() && !queue.is_empty() {
            // Playtest lever: dispatch assigns the forced-destination load
            // first, so a tester is not stuck with pot luck.
            let key = ctx.world.resolve_city_key(&forced);
            if let Some(pos) = queue
                .iter()
                .position(|&index| ctx.world.resolve_city_key(&self.jobs[index].destination) == key)
            {
                let index = queue.remove(pos);
                queue.insert(0, index);
            }
        }
        queue
    }

    /// `_locked_reason(job)`.
    pub fn locked_reason(&self, ctx: &GameContext, job: &Job) -> String {
        locked_reason(profile(ctx), job)
    }

    /// The job the current menu row refers to, in either board mode.
    fn focused_job(&self) -> Option<usize> {
        if self.assigned_mode() {
            return if self.menu.index == 0 {
                Some(self.assigned_queue[0])
            } else {
                None
            };
        }
        if self.menu.index < self.jobs.len() {
            return Some(self.menu.index);
        }
        None
    }

    fn needs_hos_confirmation(&self, ctx: &GameContext, index: usize) -> bool {
        self.job_exceeds_current_hos(ctx, &self.jobs[index])
            && self.confirm_risky_job != Some(index)
    }

    /// True when hours already spent this shift force an extra 10-hour
    /// rest the job would not need on a fresh clock. Multi-shift routes
    /// budget their own sleeps into the deadline, so a rested driver is
    /// never warned just because the run is long.
    fn job_exceeds_current_hos(&self, ctx: &GameContext, job: &Job) -> bool {
        let p = profile(ctx);
        let Some((drive_limit, duty_limit, _break_after)) = limits(&ctx.settings.hos_mode) else {
            return false;
        };
        let Ok(Some(route)) = ctx
            .world
            .supported_route(&job.origin, &job.destination, None)
        else {
            return false;
        };
        // Pickup check-in and loading are on-duty work before the first route
        // mile; being over 30 non-driving minutes, they also reset the break
        // clock, so only the drive and duty limits matter here.
        let pickup_work_min = PICKUP_CHECK_IN_MIN + PICKUP_LOADING_MIN;
        let drive_h = route_drive_hours(Some(&route), 0.0, Some(ctx.world));
        let shift_h = drive_limit / 60.0;
        let fresh_first_h = drive_limit.min(duty_limit - pickup_work_min) / 60.0;
        let current_first_h = (drive_limit - p.hos.driving_min)
            .min(duty_limit - p.hos.duty_min - pickup_work_min)
            .max(0.0)
            / 60.0;
        sleeps_needed(drive_h, current_first_h, shift_h)
            > sleeps_needed(drive_h, fresh_first_h, shift_h)
    }

    fn hos_board_note(&self, ctx: &GameContext) -> String {
        if self.jobs.is_empty() {
            return String::new();
        }
        let risky = self
            .jobs
            .iter()
            .filter(|job| self.job_exceeds_current_hos(ctx, job))
            .count();
        if risky == self.jobs.len() {
            return "On your current hours, every listed dispatch would need an \
                    extra legal rest; sleeping first would clear that. "
                .to_string();
        }
        if risky > 0 {
            return format!(
                "On your current hours, {risky} dispatch{} \
                 would need an extra legal rest. ",
                if risky != 1 { "es" } else { "" }
            );
        }
        String::new()
    }

    /// Drop a dead offer and rebuild the rows: a cached board can outlive
    /// its facilities (a data update may retire one), and the next board
    /// visit rebuilds.
    fn drop_dead_offer(&mut self, ctx: &mut GameContext, index: usize) {
        profile_mut(ctx).dispatch_board_cache = None;
        self.jobs.remove(index);
        self.confirm_risky_job = None;
        self.assigned_queue = if dispatch_policy(profile(ctx)).assigns_load {
            self.assignment_queue(ctx)
        } else {
            Vec::new()
        };
        self.refresh(ctx, false);
        ctx.audio.play("ui/warning");
    }

    /// `_accept(job)`: take the job at `index` off the board.
    pub fn accept(&mut self, ctx: &mut GameContext, index: usize) {
        let Some(job) = self.jobs.get(index).cloned() else {
            return;
        };
        {
            let p = profile(ctx);
            if p.driving_record.suspended(p.game_hours) {
                let line = enforcement::suspension_refusal_line(p);
                ctx.audio.play("ui/error");
                ctx.say(&line);
                return;
            }
        }
        let locked = locked_reason(profile(ctx), &job);
        if !locked.is_empty() {
            ctx.audio.play("ui/error");
            if locked.contains("trailer program") {
                if profile(ctx).business_status == INDEPENDENT_AUTHORITY {
                    ctx.say(&format!(
                        "{locked} Open Garage, Trailers to lease support or \
                         buy a matching trailer."
                    ));
                } else {
                    ctx.say(&format!("{locked} Open Garage, Trailers to add it."));
                }
            } else {
                ctx.say(&format!(
                    "{locked} Keep delivering to level up, or book the \
                     endorsement course at the terminal."
                ));
            }
            return;
        }
        if self.needs_hos_confirmation(ctx, index) {
            self.confirm_risky_job = Some(index);
            ctx.audio.play("ui/warning");
            let summary = profile(ctx).hos.summary(&ctx.settings.hos_mode);
            ctx.say(&format!(
                "Hours warning. The hours you have already used this shift mean \
                 this dispatch needs an extra legal rest that fresh hours would \
                 avoid. {summary} \
                 Press Enter again to accept it anyway, or sleep first to clear \
                 the warning."
            ));
            return;
        }
        self.confirm_risky_job = None;
        if job.bobtail {
            self.accept_reposition(ctx, index);
            return;
        }
        let route = ctx
            .world
            .facility_approach_route(&job.origin, &job.origin_location);
        let Ok(route) = route else {
            // A cached board can outlive its facilities (a data update may
            // retire one, e.g. a template gated out by geography). Drop the
            // dead offer instead of crashing; the next board visit rebuilds.
            self.drop_dead_offer(ctx, index);
            ctx.say(
                "That load's facility is no longer on the network. Dispatch \
                 pulled the offer; the board will refresh with new loads.",
            );
            return;
        };
        let terminal = home_terminal(ctx);
        // Junior drivers slip-seat: the yard picks the tractor for the load
        // before the keys change hands, so the truck is decided before the
        // trip snapshot is taken.
        let equipment_note = slip_seat_note(ctx, &job);
        profile_mut(ctx).dispatch_board_cache = None;
        let line = format!(
            "Dispatch accepted from {}.{equipment_note} Deadhead \
             {} on \
             {} to pickup at \
             {}. \
             Check in with the shipper when you arrive.",
            terminal.name,
            ctx.settings.distance_text(route.miles(), true),
            route.highways().first().cloned().unwrap_or_default(),
            job.origin_facility_text()
        );
        launch_driving(
            ctx,
            DrivingLaunch::new(
                job,
                route,
                DRIVE_PHASE_PICKUP,
                LaunchAnnouncement::Line(line),
            ),
        );
        // first_dispatch is retired as an award (folded into "first_day" at
        // pickup completion, see city_pickup.py); the catalog entry and id
        // stay so the cloud validator's allow-list never sees a removed id.
    }

    /// Accept a carrier-ASSIGNED reposition straight off the board.
    ///
    /// There is no pickup facility to deadhead to -- the whole job IS the
    /// deadhead -- so this skips facility_approach_route and the pickup
    /// phase entirely, the same city-to-city drive BobtailDestState._start
    /// builds for a self-serve bobtail.
    fn accept_reposition(&mut self, ctx: &mut GameContext, index: usize) {
        let job = self.jobs[index].clone();
        let route = ctx
            .world
            .supported_route(&job.origin, &job.destination, None)
            .ok()
            .flatten();
        let Some(route) = route else {
            // A cached board can outlive the world it was built from, same
            // as the facility case above.
            self.drop_dead_offer(ctx, index);
            ctx.say(
                "That route is no longer on the network. Dispatch pulled the \
                 offer; the board will refresh with new loads.",
            );
            return;
        };
        profile_mut(ctx).dispatch_board_cache = None;
        let line = format!(
            "Dispatch assignment accepted: reposition to {}, \
             {} on \
             {}. No cargo, and pay is the reduced empty-mile \
             rate: {} dollars. You will see the \
             {} dispatch board on arrival.",
            job.spoken_destination(),
            ctx.settings.distance_text(route.miles(), true),
            route.highways().first().cloned().unwrap_or_default(),
            fmt_grouped(job.pay, 0),
            job.spoken_destination()
        );
        launch_driving(
            ctx,
            DrivingLaunch::new(
                job,
                route,
                DRIVE_PHASE_DELIVERY,
                LaunchAnnouncement::Line(line),
            ),
        );
    }
}

fn sort_scored(candidates: &mut [(f64, usize)]) {
    candidates.sort_by(|a, b| {
        a.0.partial_cmp(&b.0)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.1.cmp(&b.1))
    });
}

/// Draw the assigned tractor and say why, or nothing if it is not new.
///
/// Silent when the truck has not changed: a driver who drew the same
/// spare three loads running does not need telling three times.
///
/// A driver past slip-seating has ONE truck and draws nothing, so there
/// is normally nothing to say -- but if the yard is holding them below
/// the tractor their level earns, that is the one thing they will want
/// explained, and this used to be silent about it. A level 11 driver
/// capped to a regional truck by their standing got handed a yard mule
/// every run with no reason given anywhere near the moment it happened;
/// the explanation existed, but only on the standing screen, which you
/// have to already suspect the answer to go and read (Brandon,
/// 2026-08-21: "what gives?").
fn slip_seat_note(ctx: &mut GameContext, job: &Job) -> String {
    let terse = ctx.settings.renders_terse();
    let p = profile_mut(ctx);
    if p.owns_equipment() {
        return String::new();
    }
    if !slip_seats(p) {
        // No draw to announce, so say only the part that is news: why the
        // iron is short of the level, and what gives it back.
        return if equipment_held_back(p) {
            format!(" {}", equipment_hold_text(p, terse))
        } else {
            String::new()
        };
    }
    let before = p.active_truck_key();
    let key = p.take_slip_seat(job);
    if key == before {
        return String::new();
    }
    format!(
        " {}",
        assignment_reason_text::<Profile, Job>(&key, Some(job), Some(p), terse)
    )
}

impl Menu for JobBoardState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let n = self.jobs.len();
        let plural = if n != 1 { "es" } else { "" };
        // A board the player cannot take work from explains itself before it
        // lists anything. An unexplained empty or refusing board is exactly the
        // kind of silence this game does not do.
        {
            let p = profile(ctx);
            if p.driving_record.suspended(p.game_hours) {
                let line = enforcement::suspension_board_line(p);
                ctx.say(&format!(
                    "{line} You can still read the \
                     {n} listed dispatch{plural}. Escape returns to \
                     the terminal."
                ));
                return;
            }
        }
        if n == 0 {
            ctx.say("Dispatch board. No jobs available right now. Press Escape to go back.");
        } else if self.assigned_mode() {
            self.announce_assignment(ctx);
        } else {
            let p = profile(ctx);
            let status = p.business_status.as_str();
            let business_note = if status == INDEPENDENT_AUTHORITY {
                "Listed amounts are direct freight gross. Insurance, \
                 compliance, trailer, truck, and factoring costs come out \
                 at settlement. "
            } else if is_owner_operator(status) {
                "Listed amounts are owner-operator gross revenue. Trailer \
                 program needs are listed on each job. "
            } else {
                "Listed amounts are carrier gross; your settlement pays \
                 driver wages. Dispatch trusts you to pick your own \
                 loads now; routing is still assigned until you run \
                 your own truck. "
            };
            let objective_text =
                if let Some(training_label) = self.training_recommendation_label(ctx) {
                    let guidance = training_guidance(p);
                    format!(
                        "First-day objective: pick a {training_label} load. {} ",
                        guidance.dispatch_text
                    )
                } else if first_day_guidance_active(p) && !is_company_training_profile(p) {
                    "First-day objective: pick an unlocked load with a \
                 delivery deadline you can protect. Keep fuel, repairs, and \
                 your cash cushion in mind. "
                        .to_string()
                } else {
                    let objective = career_objective(p);
                    let recommendation = if self.focused_recommendation_is_spoken(ctx) {
                        String::new()
                    } else {
                        format!("Recommended dispatch: {}. ", objective.recommendation)
                    };
                    format!(
                        "Career objective: {}. \
                     {} \
                     {recommendation}",
                        objective.title, objective.dispatch_text
                    )
                };
            let hos_note = self.hos_board_note(ctx);
            let market = p.market.summary();
            ctx.say(&format!(
                "Dispatch board. {n} dispatch{plural} available. \
                 {business_note}{objective_text}\
                 {hos_note}\
                 {market}"
            ));
            let current = self.current_text(ctx);
            ctx.say_with(current, Say::queued().review(false));
        }
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        if self.assigned_mode() {
            return self.build_assignment_items(ctx);
        }
        let p = profile(ctx);
        let mut items: Vec<MenuItem<Self>> = Vec::new();
        for (i, job) in self.jobs.iter().enumerate() {
            let locked = locked_reason(p, job);
            let mut label = self.job_label(ctx, job, i + 1);
            if !locked.is_empty() {
                label = label.replacen("Job ", "Locked job ", 1);
            }
            let help_text = if job.bobtail {
                format!(
                    "Carrier-assigned reposition: an empty deadhead to \
                     {}. Route inspection after accepting \
                     covers rest, fuel, toll, weather, and restrictions.",
                    job.spoken_destination()
                )
            } else {
                format!(
                    "Load offer from {} to \
                     {}. Route inspection after \
                     pickup covers rest, fuel, toll, weather, and restrictions.",
                    job.origin_facility_text(),
                    job.destination_facility_text()
                )
            };
            items.push(
                MenuItem::new(label, move |s: &mut Self, ctx| s.accept(ctx, i)).help(help_text),
            );
        }
        items.push(MenuItem::new("Back to terminal", |s: &mut Self, ctx| {
            s.go_back(ctx)
        }));
        items
    }

    fn handle_event(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        if let Some((key, _, _)) = event.key_down() {
            if key == Key::F1 && !self.jobs.is_empty() {
                if let Some(index) = self.focused_job() {
                    let board: SharedState = ctx.state().expect("the board is the active state");
                    let job = self.jobs[index].clone();
                    ctx.push_state(JobDetailState::new(board, job, index));
                    return;
                }
            }
            if key == Key::Tab {
                let summary = profile(ctx).market.summary();
                ctx.say(&summary);
                return;
            }
        }
        base_menu_handle_event(self, ctx, event);
    }
}

impl_state_for_menu!(JobBoardState);

// -- JobDetailState -----------------------------------------------------------------------

const JOB_DETAIL_INTRO_HELP: &str =
    "Use up and down arrows to review each job detail line; Home and End \
     jump to the first and last row. Enter repeats detail lines, accepts \
     when Accept this dispatch is selected, or returns when Back to \
     dispatch board is selected. Escape also returns to the dispatch board.";

pub struct JobDetailState {
    menu: MenuCore<Self>,
    /// The board this job came from, for `Accept this dispatch`.
    board: SharedState,
    pub job: Job,
    job_index: usize,
}

impl JobDetailState {
    /// `JobDetailState(ctx, board, job)`; `job_index` is the job's position
    /// on that board.
    pub fn new(board: SharedState, job: Job, job_index: usize) -> Self {
        JobDetailState {
            menu: MenuCore::new("Job details").with_intro_help(JOB_DETAIL_INTRO_HELP),
            board,
            job,
            job_index,
        }
    }

    fn accept(&mut self, ctx: &mut GameContext) {
        ctx.pop_state();
        let board = self.board.clone();
        let index = self.job_index;
        // The semicolon matters: the RefMut is a temporary of this
        // statement, and without it the borrow outlives the handle above.
        if let Ok(mut state) = board.try_borrow_mut() {
            if let Some(board) = state.as_any_mut().downcast_mut::<JobBoardState>() {
                board.accept(ctx, index);
            }
        };
    }

    fn detail_lines(&self, ctx: &GameContext) -> Vec<String> {
        let job = &self.job;
        if job.bobtail {
            return self.reposition_detail_lines(ctx);
        }
        let p = profile(ctx);
        let business = settlement_for(p, job, true);
        let dollars_per_mile = business.gross_pay / job.distance_mi.max(1.0);
        let s = &ctx.settings;
        let world = ctx.world;
        // The detail view is the "tell me more" surface, so it always names the
        // state -- board offers stay short, but a player who does not know
        // where Baton Rouge is can open the job and hear "..., Louisiana".
        let destination_text = facility_text(
            &job.destination_type,
            &job.destination_location,
            &world.spoken_city(&job.destination, Some(true)),
            &job.destination_locality,
        );
        let zone = world
            .city(&job.destination)
            .map(|c| city_zone(c))
            .unwrap_or(ff_core::sim::timezones::EASTERN);
        let mut lines = vec![
            format!("Cargo: {}.", job.cargo.label),
            format!("Origin: {}.", job.origin_facility_text()),
            format!("Destination: {destination_text}."),
            format!("Distance: {}.", s.distance_text(job.distance_mi, false)),
            format!(
                "{}: {} dollars.",
                pay_label(&p.business_status),
                fmt_grouped(business.gross_pay, 0)
            ),
            format!(
                "Dollars per {}: \
                 {}.",
                s.distance_unit_text(false),
                fmt_f(s.per_distance(dollars_per_mile), 2)
            ),
            // The appointment reads in the receiver's local time, the way real
            // dispatch quotes it. "About" because the clock starts at pickup
            // departure, after check-in and loading.
            format!(
                "Deadline: {} hours; deliver by about \
                 {}.",
                fmt_f(job.deadline_game_h, 0),
                appointment_text(p.game_hours, job.deadline_game_h, zone)
            ),
            format!("Equipment: {}.", job.equipment_text()),
            format!("Trailer: {}", trailer_note(p, job)),
        ];
        let locked = locked_reason(p, job);
        if !locked.is_empty() {
            lines.push(format!("Locked: {locked}"));
        } else if let Some(endorsement) = job.cargo.endorsement {
            lines.push(format!("Endorsement: {}.", endorsement.replace('_', " ")));
        }
        lines.push(
            "Route details happen after pickup: rest, fuel, tolls, weather, and stops.".to_string(),
        );
        lines
    }

    fn reposition_detail_lines(&self, ctx: &GameContext) -> Vec<String> {
        let job = &self.job;
        vec![
            "This is a carrier-assigned reposition: dispatch is sending you \
             empty to a nearby city where freight is thicker, not a loaded haul."
                .to_string(),
            format!(
                "Destination: {}.",
                ctx.world.spoken_city(&job.destination, Some(true))
            ),
            format!(
                "Distance: {}.",
                ctx.settings.distance_text(job.distance_mi, false)
            ),
            format!(
                "Pay: {} dollars, the reduced empty-mile rate for deadhead miles.",
                fmt_grouped(job.pay, 0)
            ),
            "No cargo, no trailer program, no endorsement needed.".to_string(),
            "Route details happen after accepting: rest, fuel, tolls, weather, and stops."
                .to_string(),
        ]
    }
}

impl Menu for JobDetailState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let current = self.current_text(ctx);
        ctx.say(&format!("Job details. {JOB_DETAIL_INTRO_HELP} {current}"));
    }

    fn current_help(&self, ctx: &GameContext) -> String {
        format!(
            "{JOB_DETAIL_INTRO_HELP} {}",
            base_menu_current_help(self, ctx)
        )
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let mut items: Vec<MenuItem<Self>> = self
            .detail_lines(ctx)
            .into_iter()
            .map(|line| {
                let spoken = line.clone();
                MenuItem::new(line, move |_s: &mut Self, ctx| ctx.say(&spoken))
                    .help("This is a job detail line. Press Enter to repeat it.")
            })
            .collect();
        let locked = locked_reason(profile(ctx), &self.job);
        if !locked.is_empty() {
            let spoken = locked.clone();
            items.push(
                MenuItem::new(
                    format!("Cannot accept this dispatch: {locked}"),
                    move |_s: &mut Self, ctx| ctx.say(&spoken),
                )
                .help(format!("This dispatch is locked. {locked}")),
            );
        } else {
            items.push(
                MenuItem::new("Accept this dispatch", |s: &mut Self, ctx| s.accept(ctx))
                    .help("Accept this dispatch and begin the pickup drive."),
            );
        }
        items.push(
            MenuItem::new("Back to dispatch board", |s: &mut Self, ctx| s.go_back(ctx))
                .help("Return to the dispatch board without accepting this job."),
        );
        items
    }
}

impl_state_for_menu!(JobDetailState);
