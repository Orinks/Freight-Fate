//! The spoken route POI menu: actions come from the corridor metadata
//! (`RestStopState`).

use ff_core::data::amenities::{classify_brand, spoken_amenities};
use ff_core::data::buffs::{buffs_for_stop, Buff};
use ff_core::models::solvency;
use ff_core::pyfmt::{fmt_f, fmt_grouped, round_py_n};
use ff_core::sim::hos;
use ff_core::sim::trip_models::RoadStop;
use serde_json::json;

use crate::app::{GameContext, Say};
use crate::discord_presence::PresenceState;
use crate::impl_state_for_menu;
use crate::states::base::{Menu, MenuCore, MenuItem};
use crate::states::city::PayDebtState;
use crate::states::driving::DrivingState;
use crate::states::driving_core::{
    advance_rest_clock, clock_text, deadline_text, hos_mut_of, hos_of, pay_advance_grant,
    pay_advance_unavailable_reason, player_pays_operating_costs, poi_ambient_key, profile_mut_of,
    profile_of, record_inspection, road_repair_cost, shut_down_engine, wake_air_instruction,
    RigBuff, FIELD_REPAIR_DAMAGE_PCT, INSPECTION_MIN, MECHANIC_CALLOUT_FEE, MECHANIC_WAIT_MIN,
    MOTEL_COST, ROAD_BRAKE_COST_PER_PCT, ROAD_BRAKE_MIN, ROAD_TIRE_COST_PER_PCT, ROAD_TIRE_MIN,
    ROAD_TIRE_SPECIALIST_COST_PER_PCT, ROAD_TIRE_SPECIALIST_MIN,
};
use crate::states::driving_menu_states::{keep_rows, DriveRef};
use crate::states::driving_rest_states::fuel_pump::FuelPump;
use crate::states::driving_rest_states::loyalty::LoyaltyRewardsState;

const REST_STOP_INTRO_HELP: &str =
    "Use up and down arrows to navigate, Enter to select. Escape returns to the road. Breaks and \
     sleep advance the clock, and your delivery deadline keeps counting.";

/// Which wear meter a road shop is selling a job on.
#[derive(Clone, Copy, PartialEq, Eq)]
enum WearMeter {
    Tire,
    Brake,
}

pub struct RestStopState {
    menu: MenuCore<Self>,
    driving: DriveRef,
    pub stop: RoadStop,
    prefer_sleep: bool,
    fueled_here: bool,
    confirm_sleep_rested: bool,
}

impl RestStopState {
    pub fn new(ctx: &GameContext, stop: RoadStop, prefer_sleep: bool) -> Self {
        RestStopState {
            menu: MenuCore::new(&stop.spoken_name()).with_intro_help(REST_STOP_INTRO_HELP),
            driving: DriveRef::active(ctx),
            stop,
            prefer_sleep,
            fueled_here: false,
            confirm_sleep_rested: false,
        }
    }

    /// The same screen over a drive the caller already shares (tests).
    pub fn with_drive(driving: DriveRef, stop: RoadStop, prefer_sleep: bool) -> Self {
        RestStopState {
            menu: MenuCore::new(&stop.spoken_name()).with_intro_help(REST_STOP_INTRO_HELP),
            driving,
            stop,
            prefer_sleep,
            fueled_here: false,
            confirm_sleep_rested: false,
        }
    }

    /// `enter()` run while the drive is still in hand -- see `drive_ref`.
    pub fn enter_over_drive(&mut self, ctx: &mut GameContext, driving: &mut DrivingState) {
        self.confirm_sleep_rested = false;
        let items = self.rows(ctx, driving);
        self.menu.items = items;
        self.place_cursor(ctx);
        if let Some(key) = self.menu.open_sound_key.clone() {
            ctx.audio.play(&key);
        }
        self.announce_over_drive(ctx, driving);
    }

    fn place_cursor(&mut self, ctx: &GameContext) {
        if self.prefer_sleep {
            let index = self
                .menu
                .items
                .iter()
                .position(|item| item.text(self, ctx).starts_with("Sleep "))
                .unwrap_or(0);
            self.menu.index = index;
            // This is an arrival hint, not a permanent focus policy.
            // Returning from a submenu must preserve the row the player
            // invoked.
            self.prefer_sleep = false;
        } else {
            self.menu.index = self.menu.index.min(self.menu.items.len().saturating_sub(1));
        }
    }

    /// Warn once before a redundant sleep, matching the terminal. A sleep
    /// gains nothing when hours of service are already fresh and this rest
    /// cannot lower fatigue any further -- for a proper berth that means zero
    /// fatigue, for a lot's poor rest it bottoms out at the shoulder floor.
    /// Returns true if this press should be blocked.
    fn guard_double_sleep(&mut self, ctx: &mut GameContext, fatigue_floor: f64) -> bool {
        let gains_nothing = {
            let p = profile_of(ctx);
            p.hos.driving_min <= 0.0 && p.hos.duty_min <= 0.0 && p.fatigue <= fatigue_floor
        };
        if gains_nothing && !self.confirm_sleep_rested {
            self.confirm_sleep_rested = true;
            ctx.audio.play("ui/warning");
            ctx.say(
                "You are already rested: fresh hours of service and no more rest to gain here. \
                 Sleeping now would only move the clock and your deadline forward. Press Enter \
                 again to sleep anyway.",
            );
            return true;
        }
        self.confirm_sleep_rested = false;
        false
    }

    fn announce_over_drive(&mut self, ctx: &mut GameContext, d: &mut DrivingState) {
        ctx.audio
            .set_ambient(Some(poi_ambient_key(&self.stop, d.trip.local_hour())));
        let mut parts = vec![format!("{}.", self.stop.spoken_name())];
        if self.stop.stop_type == "weigh_station" {
            // An inspection, not hospitality: no parking chatter, no live lot
            // lookup, no brand amenities. The one-template announce read a
            // scale its truck-stop script -- "no truck parking... Loyalty
            // program: Loyalty points: 0" -- at an open scale (owner
            // playtest, 2026-08-20).
            parts.push("Inspection station.".to_string());
            parts.push(format!("It is {}.", clock_text(d.trip.local_hour())));
            parts.push(self.current_text(ctx));
            ctx.say(&parts.join(" "));
            return;
        }
        let parking_text = self.stop.parking_text();
        if !parking_text.is_empty() {
            parts.push(format!("{parking_text}."));
        }
        // Check real-time parking availability if enabled
        if ctx.settings.real_parking && d.trip.parking_provider.is_some() {
            if let Some(availability) = check_parking_availability(d) {
                parts.push(availability);
            }
        }
        let brand_text = spoken_amenities(&self.stop.name, &self.stop.stop_type);
        if !brand_text.is_empty() {
            parts.push(format!("{brand_text}."));
        }
        parts.push(format!("It is {}.", clock_text(d.trip.local_hour())));
        parts.push(self.current_text(ctx));
        ctx.say(&parts.join(" "));
    }

    fn rows(&mut self, ctx: &mut GameContext, d: &mut DrivingState) -> Vec<MenuItem<Self>> {
        let actions: Vec<String> = self.stop.actions.clone();
        let has = |name: &str| actions.iter().any(|a| a == name);
        let mut items: Vec<MenuItem<Self>> = Vec::new();
        let is_scale = self.stop.stop_type == "weigh_station";

        // Loyalty program status -- at hospitality stops. A scale hands out
        // citations, not points.
        if !is_scale {
            let summary = profile_of(ctx).loyalty.summary();
            items.push(
                MenuItem::new(
                    format!("Loyalty program: {summary}"),
                    |s: &mut Self, ctx| s.loyalty_menu(ctx),
                )
                .help(
                    "Check your loyalty points, shower credits, and redeem rewards at this truck \
                     stop.",
                ),
            );
        }

        if has("fuel") {
            let label = self.fuel_label(ctx, d);
            items.push(
                MenuItem::new(label, |s: &mut Self, ctx| s.refuel(ctx)).help(
                    "Fill the tank at this region's diesel price, plus a 35 dollar service fee. \
                     If cash is short, buy as many gallons as you can afford.",
                ),
            );
        }
        if has("food") {
            items.push(
                MenuItem::new("Food and coffee break", |s: &mut Self, ctx| {
                    s.food_break(ctx)
                })
                .help(
                    "A short off-duty break for food or coffee. The clock and your deadline \
                     advance fifteen minutes. Coffee eases fatigue a little, but does not \
                     satisfy the 30-minute break rule.",
                ),
            );
        }
        if has("break") {
            items.push(
                MenuItem::new("Take a 30-minute break", |s: &mut Self, ctx| {
                    s.take_break(ctx)
                })
                .help(
                    "Satisfies the 30-minute break rule and eases fatigue. The clock and your \
                     deadline advance half an hour.",
                ),
            );
        }
        if has("sleep") {
            for hours in [2, 3, 7, 8] {
                items.push(
                    MenuItem::new(
                        format!("Sleep {hours} hours in sleeper berth"),
                        move |s: &mut Self, ctx: &mut GameContext| s.sleeper_split_rest(ctx, hours),
                    )
                    .help(sleeper_split_help(hours)),
                );
            }
            items.push(
                MenuItem::new("Sleep 10 hours", |s: &mut Self, ctx| s.sleep(ctx)).help(
                    "A full reset: fresh hours of service and zero fatigue. The clock and your \
                     deadline advance 10 hours.",
                ),
            );
        } else if !is_scale {
            // No proper sleeper facility here, but you can always bed down in
            // the lot -- a legal reset, just cramped and poor rest. Except at
            // a scale: nobody sleeps in an active inspection facility, and
            // there is no motel on the far side of the platform (the scale
            // was offering both, plus a loyalty program -- owner playtest,
            // 2026-08-20).
            items.push(
                MenuItem::new("Sleep 10 hours in the lot", |s: &mut Self, ctx| {
                    s.emergency_lot_sleep(ctx)
                })
                .help(
                    "No sleeper facility here, but you can sleep in the lot for a legal 10-hour \
                     reset. The rest is poor, so you wake still tired, and the clock advances 10 \
                     hours.",
                ),
            );
            items.push(
                MenuItem::new(
                    format!(
                        "Motel room: sleep 10 hours for {} dollars",
                        fmt_f(MOTEL_COST, 0)
                    ),
                    |s: &mut Self, ctx| s.motel_sleep(ctx),
                )
                .help(
                    "A real bed near the lot. Costs money out of your own pocket, but gives the \
                     same legal reset with full-quality rest: you wake fresh. The clock advances \
                     10 hours.",
                ),
            );
        }
        if has("repair") {
            items.push(
                MenuItem::new("Use repair service", |s: &mut Self, ctx| s.repair(ctx))
                    .help("Pay the shop to repair truck damage before returning to the road."),
            );
        }
        if !solvency::out_of_pocket_options(profile_of(ctx)).is_empty() {
            let owed = solvency::money_text(solvency::debt_owed(profile_of(ctx)));
            items.push(
                MenuItem::new(
                    format!("Pay down what you owe: {owed} owed"),
                    |_s: &mut Self, ctx: &mut GameContext| {
                        let state = PayDebtState::new();
                        ctx.push_state(state);
                    },
                )
                .help("Put your own cash toward the balance you owe, right from this stop."),
            );
        }
        let brand = classify_brand(&self.stop.name);
        if let Some(brand) = brand {
            if brand.tier == "travel_center" {
                let tire_help = if brand.signature.contains(&"tires") {
                    format!(
                        "{} runs a dedicated tire bay: road tire service close to the terminal \
                         garage price, done fast. Company drivers bill the carrier; \
                         owner-operators pay.",
                        brand.spoken
                    )
                } else {
                    format!(
                        "{} can mount tires on the road, at a markup over the terminal garage. \
                         Tire specialists like Love's and Speedco do the same work cheaper and \
                         faster.",
                        brand.spoken
                    )
                };
                items.push(
                    MenuItem::new(self.tire_label(ctx, d), |s: &mut Self, ctx| {
                        s.service_wear(ctx, WearMeter::Tire)
                    })
                    .help(tire_help),
                );
                if brand.signature.contains(&"repair") {
                    items.push(
                        MenuItem::new(brake_label(ctx, d), |s: &mut Self, ctx| {
                            s.service_wear(ctx, WearMeter::Brake)
                        })
                        .help(format!(
                            "{} runs a full truck service shop and can reline worn brake shoes \
                             on the road, at a markup over the terminal garage. Company drivers \
                             bill the carrier; owner-operators pay.",
                            brand.spoken
                        )),
                    );
                }
            }
        }
        let action_refs: Vec<&str> = actions.iter().map(String::as_str).collect();
        let mut stop_buffs = buffs_for_stop(&self.stop.name, &action_refs);
        if brand.is_some_and(|b| b.bans_big_rigs) && !d.job.bobtail {
            // The famous ban: with a trailer on you never got past the lot.
            stop_buffs = Vec::new();
        }
        for buff in stop_buffs {
            let label = self.buff_label(buff);
            let id = buff.id.clone();
            items.push(
                MenuItem::new(label, move |s: &mut Self, ctx: &mut GameContext| {
                    s.buy_buff(ctx, &id)
                })
                .help(buff.help.clone()),
            );
        }
        if has("roadside_assistance") {
            items.push(
                MenuItem::new("Call roadside assistance", |s: &mut Self, ctx| {
                    s.roadside_assistance(ctx)
                })
                .help(
                    "Use the listed roadside assistance service for a field repair before \
                     returning to the road.",
                ),
            );
        }
        if has("towing") {
            items.push(
                MenuItem::new("Request towing service", |s: &mut Self, ctx| {
                    s.roadside_assistance(ctx)
                })
                .help(
                    "Use the listed towing service for roadside help before returning to the \
                     road.",
                ),
            );
        }
        if has("inspect") {
            items.push(
                MenuItem::new("Check in at inspection station", |s: &mut Self, ctx| {
                    s.inspect(ctx)
                })
                .help("Stop and record the inspection check-in before continuing."),
            );
        }
        if has("save") {
            items.push(
                MenuItem::new("Save at this stop", |s: &mut Self, ctx| {
                    s.save_here(ctx, false)
                })
                .help("Save the active drive at this route POI without leaving the road."),
            );
        }
        if self.pay_advance_available(ctx) {
            items.push(
                MenuItem::new(self.pay_advance_label(ctx), |s: &mut Self, ctx| {
                    s.request_pay_advance(ctx)
                })
                .help(
                    "Draw cash against this load when you are broke and cannot afford fuel. \
                     Repaid automatically out of your delivery settlement.",
                ),
            );
        }
        items.push(
            MenuItem::new("Back to the road", |s: &mut Self, ctx| s.go_back(ctx))
                .help("Leave this stop and return to driving."),
        );
        items
    }

    fn pay_advance_label(&self, ctx: &GameContext) -> String {
        let p = profile_of(ctx);
        let grant = pay_advance_grant(p.money, p.pay_advance, p.pay_advance_used_for_load);
        if grant > 0.0 {
            return format!("Request pay advance: {} dollars", fmt_grouped(grant, 0));
        }
        "Request pay advance".to_string()
    }

    fn pay_advance_available(&self, ctx: &GameContext) -> bool {
        let p = profile_of(ctx);
        pay_advance_grant(p.money, p.pay_advance, p.pay_advance_used_for_load) > 0.0
    }

    fn request_pay_advance(&mut self, ctx: &mut GameContext) {
        let (grant, reason) = {
            let p = profile_of(ctx);
            (
                pay_advance_grant(p.money, p.pay_advance, p.pay_advance_used_for_load),
                pay_advance_unavailable_reason(p.money, p.pay_advance, p.pay_advance_used_for_load),
            )
        };
        if grant <= 0.0 {
            ctx.audio.play("ui/error");
            ctx.say(&reason);
            return;
        }
        let (money, advance) = {
            let p = profile_mut_of(ctx);
            p.money += grant;
            p.pay_advance = round_py_n(p.pay_advance + grant, 2);
            p.pay_advance_used_for_load = true;
            (p.money, p.pay_advance)
        };
        self.save_here(ctx, true);
        ctx.audio.play("ui/notify");
        let destination = self
            .driving
            .read(|d| d.job.destination.clone())
            .unwrap_or_default();
        ctx.say(&format!(
            "Pay advance approved: {} dollars against your {destination} load. It will be \
             deducted at delivery. You have {} dollars, with {} dollars of advance still to \
             repay.",
            fmt_grouped(grant, 0),
            fmt_grouped(money, 0),
            fmt_grouped(advance, 0)
        ));
        self.refresh(ctx, true);
    }

    /// Show loyalty program details and redemption options.
    fn loyalty_menu(&mut self, ctx: &mut GameContext) {
        let state = LoyaltyRewardsState::new(self.driving.clone(), self.stop.clone());
        ctx.push_state(state);
    }

    fn take_break(&mut self, ctx: &mut GameContext) {
        let Some(text) = self.driving.clone().with(ctx, |d, ctx| {
            advance_rest_clock(d, ctx, 30.0, None, "");
            hos_mut_of(ctx).take_break(30.0);
            {
                let p = profile_mut_of(ctx);
                p.fatigue = hos::rest_break(p.fatigue);
            }
            format!(
                "You took a 30-minute break. It is {}. Your break requirement is reset and you \
                 feel a little fresher. {}",
                clock_text(d.trip.local_hour()),
                deadline_text(d, ctx)
            )
        }) else {
            return;
        };
        self.save_here(ctx, true);
        ctx.audio.play("ui/notify");
        ctx.say(&text);
        ctx.award_achievement("break_taken");
    }

    fn food_break(&mut self, ctx: &mut GameContext) {
        let Some(text) = self.driving.clone().with(ctx, |d, ctx| {
            advance_rest_clock(d, ctx, 15.0, Some("off_duty"), "food and coffee");
            hos_mut_of(ctx).take_break(15.0);
            {
                let p = profile_mut_of(ctx);
                p.fatigue = hos::rest_coffee_break(p.fatigue);
            }
            format!(
                "You took a short food and coffee break. It is {}. The coffee helps you stay \
                 alert a little longer, but this short stop does not reset your 30-minute break \
                 requirement. {}",
                clock_text(d.trip.local_hour()),
                deadline_text(d, ctx)
            )
        }) else {
            return;
        };
        self.save_here(ctx, true);
        ctx.audio.play("ui/notify");
        ctx.say(&text);
    }

    fn sleeper_split_rest(&mut self, ctx: &mut GameContext, hours: i64) {
        if self.guard_double_sleep(ctx, 0.0) {
            return;
        }
        let Some(text) = self.driving.clone().with(ctx, |d, ctx| {
            let minutes = (hours * 60) as f64;
            let engine_off = shut_down_engine(d, ctx);
            advance_rest_clock(d, ctx, minutes, None, "");
            let completed = hos_mut_of(ctx).sleeper_split_rest(minutes);
            {
                let p = profile_mut_of(ctx);
                p.fatigue = hos::rest_sleeper_split(p.fatigue, minutes, completed);
            }
            let mode = ctx.settings.hos_mode.clone();
            let status = if completed {
                format!("Sleeper split credited. {} ", hos_of(ctx).summary(&mode))
            } else {
                // A rest that did NOT reset the shift leads with that
                // consequence: the old wording buried "split pending" in one
                // clause and the owner drove into a window violation
                // believing he had hours left (2026-07-24). The countdown
                // warnings re-arm too, so the 60- and 30-minute window calls
                // speak again after waking.
                hos_mut_of(ctx).re_arm_warnings();
                let pending = hos_of(ctx)
                    .split_pending_summary()
                    .unwrap_or("Sleeper berth rest recorded.")
                    .to_string();
                if hos::HOS_NON_ENFORCED_MODES.contains(&mode.as_str()) {
                    format!("{pending} ")
                } else {
                    let duty_limit = hos::limits(&mode).map(|(_, duty, _)| duty).unwrap_or(0.0);
                    let duty_left_h = (duty_limit - hos_of(ctx).duty_min).max(0.0) / 60.0;
                    let window = if duty_left_h <= 0.0 {
                        "Warning: this sleep did NOT reset your hours, and your duty window has \
                         already closed. Do not drive: finish the split or take a full 10-hour \
                         reset first. "
                            .to_string()
                    } else {
                        let closes = clock_text((d.trip.local_hour() + duty_left_h) % 24.0);
                        format!(
                            "This sleep did NOT reset your hours. Your duty window closes in {} \
                             hours, at {closes}. ",
                            fmt_f(duty_left_h, 1)
                        )
                    };
                    format!("{window}{pending} ")
                }
            };
            format!(
                "{engine_off}You slept {hours} hours in the sleeper berth. It is {}. {status}{}{}",
                clock_text(d.trip.local_hour()),
                deadline_text(d, ctx),
                wake_air_instruction(d, ctx, true)
            )
        }) else {
            return;
        };
        self.save_here(ctx, true);
        ctx.audio.play("ui/notify");
        ctx.say(&text);
        ctx.award_achievement("slept_on_route");
        self.refresh(ctx, true);
    }

    fn sleep(&mut self, ctx: &mut GameContext) {
        if self.guard_double_sleep(ctx, 0.0) {
            return;
        }
        let before_fatigue = profile_of(ctx).fatigue;
        let Some(text) = self.driving.clone().with(ctx, |d, ctx| {
            let engine_off = shut_down_engine(d, ctx);
            advance_rest_clock(d, ctx, hos::SLEEP_MIN, None, "");
            hos_mut_of(ctx).sleep();
            {
                let p = profile_mut_of(ctx);
                p.fatigue = hos::rest_sleep(p.fatigue);
            }
            format!(
                "{engine_off}You slept 10 hours and woke rested. It is {}. Hours of service \
                 reset. {}{}",
                clock_text(d.trip.local_hour()),
                deadline_text(d, ctx),
                wake_air_instruction(d, ctx, true)
            )
        }) else {
            return;
        };
        self.save_here(ctx, true);
        ctx.audio.play("ui/notify");
        ctx.say(&text);
        ctx.award_achievement("slept_on_route");
        if before_fatigue < hos::FATIGUE_SEVERE {
            ctx.award_achievement("sleep_before_exhaustion");
        }
    }

    /// A paid bed where the parking is rough: a legal reset with real rest.
    ///
    /// Lodging is personal money even for company drivers -- the carrier pays
    /// for the truck, not the room.
    fn motel_sleep(&mut self, ctx: &mut GameContext) {
        let money = profile_of(ctx).money;
        if money < MOTEL_COST {
            ctx.audio.play("ui/error");
            ctx.say(&format!(
                "A motel room costs {} dollars and you have {}.",
                fmt_grouped(MOTEL_COST, 0),
                fmt_grouped(money, 0)
            ));
            return;
        }
        profile_mut_of(ctx).money -= MOTEL_COST;
        let Some(text) = self.driving.clone().with(ctx, |d, ctx| {
            // A motel bed is still a real sleep: no truck idles all night
            // just because the driver is not in it. Every other sleep option
            // shuts the engine down first; the motel room was the one path
            // that skipped it while still sending the driver off to bed.
            let engine_off = shut_down_engine(d, ctx);
            advance_rest_clock(d, ctx, hos::SLEEP_MIN, None, "");
            hos_mut_of(ctx).sleep();
            profile_mut_of(ctx).fatigue = 0.0;
            let money = profile_of(ctx).money;
            format!(
                "{engine_off}You took a motel room for {} dollars and slept a full ten hours. It \
                 is {}. Hours of service reset and you wake fresh. You have {} dollars. {}{}",
                fmt_grouped(MOTEL_COST, 0),
                clock_text(d.trip.current_hour()),
                fmt_grouped(money, 0),
                deadline_text(d, ctx),
                wake_air_instruction(d, ctx, true)
            )
        }) else {
            return;
        };
        self.save_here(ctx, true);
        ctx.audio.play("ui/notify");
        ctx.say(&text);
        // No Five-by-Two here: the badge is ten hours IN THE BUNK, and a
        // motel bed is the night you specifically did not spend in it (owner
        // report, 2026-08-20). The cramped-lot sleep keeps the award -- the
        // stop has no beds, so the lot night IS a bunk night.
    }

    /// Bed down in a break/fuel stop's lot when out of hours: a legal HOS
    /// reset, but cramped poor rest (no proper sleeper), so you wake still
    /// tired. No shoulder fine -- a lot is more legitimate than the freeway.
    fn emergency_lot_sleep(&mut self, ctx: &mut GameContext) {
        if self.guard_double_sleep(ctx, hos::FATIGUE_SHOULDER_FLOOR) {
            return;
        }
        let Some(text) = self.driving.clone().with(ctx, |d, ctx| {
            let engine_off = shut_down_engine(d, ctx);
            advance_rest_clock(d, ctx, hos::SLEEP_MIN, None, "");
            hos_mut_of(ctx).sleep();
            {
                let p = profile_mut_of(ctx);
                p.fatigue = hos::rest_shoulder(p.fatigue);
            }
            format!(
                "{engine_off}You bed down in the cramped lot, off to the side. It is {}. Hours \
                 of service reset, but the rest was poor and you wake still tired. {}{}",
                clock_text(d.trip.local_hour()),
                deadline_text(d, ctx),
                wake_air_instruction(d, ctx, true)
            )
        }) else {
            return;
        };
        self.save_here(ctx, true);
        ctx.audio.play("ui/notify");
        ctx.say(&text);
        ctx.award_achievement("slept_on_route");
    }

    fn repair(&mut self, ctx: &mut GameContext) {
        let damage = self
            .driving
            .read(|d| d.trip.truck.damage_pct)
            .unwrap_or(0.0);
        if damage < 1.0 {
            ctx.say("The truck does not need repair.");
            return;
        }
        let carrier = !player_pays_operating_costs(&profile_of(ctx).business_status);
        if !carrier {
            let cost = ff_core::models::economy::Economy::repair_cost(damage);
            if profile_of(ctx).money < cost {
                ctx.audio.play("ui/error");
                ctx.say(&format!(
                    "Repair costs {} dollars. You cannot afford it.",
                    fmt_grouped(cost, 0)
                ));
                return;
            }
            profile_mut_of(ctx).money -= cost;
            let Some(text) = self.driving.clone().with(ctx, |d, ctx| {
                d.trip.truck.damage_pct = 0.0;
                advance_rest_clock(d, ctx, 60.0, None, "");
                hos_mut_of(ctx).on_duty(60.0);
                let money = profile_of(ctx).money;
                format!(
                    "Truck repaired for {} dollars. It is {}. You have {} dollars. {}",
                    fmt_grouped(cost, 0),
                    clock_text(d.trip.local_hour()),
                    fmt_grouped(money, 0),
                    deadline_text(d, ctx)
                )
            }) else {
                return;
            };
            self.save_here(ctx, true);
            ctx.audio.play("ui/notify");
            ctx.say(&text);
        } else {
            let Some(text) = self.driving.clone().with(ctx, |d, ctx| {
                d.trip.truck.damage_pct = 0.0;
                advance_rest_clock(d, ctx, 60.0, None, "");
                hos_mut_of(ctx).on_duty(60.0);
                format!(
                    "Shop repaired {} percent damage on the carrier account. It is {}. {}",
                    fmt_f(damage, 0),
                    clock_text(d.trip.current_hour()),
                    deadline_text(d, ctx)
                )
            }) else {
                return;
            };
            self.save_here(ctx, true);
            ctx.audio.play("ui/notify");
            ctx.say(&text);
        }
        ctx.award_achievement("garage_repair");
        if damage >= 75.0 {
            ctx.award_achievement("deep_repair");
        }
    }

    fn roadside_assistance(&mut self, ctx: &mut GameContext) {
        let damage = self
            .driving
            .read(|d| d.trip.truck.damage_pct)
            .unwrap_or(0.0);
        if damage < 1.0 {
            ctx.say("The truck does not need roadside assistance.");
            return;
        }
        let cost = road_repair_cost(damage, FIELD_REPAIR_DAMAGE_PCT, MECHANIC_CALLOUT_FEE);
        let carrier_paid = !player_pays_operating_costs(&profile_of(ctx).business_status);
        if !carrier_paid {
            profile_mut_of(ctx).money -= cost;
        }
        let Some(text) = self.driving.clone().with(ctx, |d, ctx| {
            d.trip.truck.damage_pct = damage.min(FIELD_REPAIR_DAMAGE_PCT);
            advance_rest_clock(d, ctx, MECHANIC_WAIT_MIN, None, "");
            hos_mut_of(ctx).on_duty(MECHANIC_WAIT_MIN);
            let billing = if carrier_paid {
                "on the carrier breakdown account".to_string()
            } else {
                format!("for {} dollars", fmt_grouped(cost, 0))
            };
            format!(
                "Roadside assistance patched the truck to {} percent damage {billing}. It is {}. \
                 {}",
                fmt_f(d.trip.truck.damage_pct, 0),
                clock_text(d.trip.local_hour()),
                deadline_text(d, ctx)
            )
        }) else {
            return;
        };
        self.save_here(ctx, true);
        ctx.audio.play("ui/notify");
        ctx.say(&text);
        ctx.award_achievement("roadside_fix");
    }

    fn tire_bay(&self) -> bool {
        classify_brand(&self.stop.name).is_some_and(|b| b.signature.contains(&"tires"))
    }

    fn tire_rate(&self) -> f64 {
        if self.tire_bay() {
            ROAD_TIRE_SPECIALIST_COST_PER_PCT
        } else {
            ROAD_TIRE_COST_PER_PCT
        }
    }

    fn tire_label(&self, ctx: &GameContext, d: &DrivingState) -> String {
        let wear = d.trip.truck.tire_wear_pct;
        if wear < 1.0 {
            return "Tires: tread is in top shape".to_string();
        }
        if !player_pays_operating_costs(&profile_of(ctx).business_status) {
            return format!(
                "Replace tires: {} percent wear, carrier billed",
                fmt_f(wear, 0)
            );
        }
        let cost = round_py_n(wear * self.tire_rate(), 2);
        format!(
            "Replace tires: {} percent wear for {} dollars",
            fmt_f(wear, 0),
            fmt_grouped(cost, 0)
        )
    }

    fn service_wear(&mut self, ctx: &mut GameContext, meter: WearMeter) {
        let (cost_per_pct, minutes, duty_note, fresh_say, service_noun, carrier_done, done_say) =
            match meter {
                WearMeter::Tire => (
                    self.tire_rate(),
                    if self.tire_bay() {
                        ROAD_TIRE_SPECIALIST_MIN
                    } else {
                        ROAD_TIRE_MIN
                    },
                    "road tire service",
                    "The tires are already in top shape.",
                    "tire service",
                    "replaced the tires",
                    "Tires replaced.",
                ),
                WearMeter::Brake => (
                    ROAD_BRAKE_COST_PER_PCT,
                    ROAD_BRAKE_MIN,
                    "road brake service",
                    "The brakes are already in top shape.",
                    "a brake job",
                    "relined the brakes",
                    "Brakes relined.",
                ),
            };
        self.road_wear_service(
            ctx,
            meter,
            cost_per_pct,
            minutes,
            duty_note,
            fresh_say,
            service_noun,
            carrier_done,
            done_say,
        );
    }

    /// Brand-shop wear service on the road, all-or-nothing like road repair.
    ///
    /// Partial service stays a terminal-garage courtesy; a road shop sells
    /// the whole job or none of it.
    #[allow(clippy::too_many_arguments)]
    fn road_wear_service(
        &mut self,
        ctx: &mut GameContext,
        meter: WearMeter,
        cost_per_pct: f64,
        minutes: f64,
        duty_note: &str,
        fresh_say: &str,
        service_noun: &str,
        carrier_done: &str,
        done_say: &str,
    ) {
        let wear = self
            .driving
            .read(|d| match meter {
                WearMeter::Tire => d.trip.truck.tire_wear_pct,
                WearMeter::Brake => d.trip.truck.brake_wear_pct,
            })
            .unwrap_or(0.0);
        if wear < 1.0 {
            ctx.say(fresh_say);
            return;
        }
        let carrier = !player_pays_operating_costs(&profile_of(ctx).business_status);
        let cost = round_py_n(wear * cost_per_pct, 2);
        if !carrier && profile_of(ctx).money < cost {
            ctx.audio.play("ui/error");
            ctx.say(&format!(
                "{} costs {} dollars here. You cannot afford it.",
                py_capitalize(service_noun),
                fmt_grouped(cost, 0)
            ));
            return;
        }
        if !carrier {
            profile_mut_of(ctx).money -= cost;
        }
        let duty_note = duty_note.to_string();
        let Some(text) = self.driving.clone().with(ctx, |d, ctx| {
            match meter {
                WearMeter::Tire => d.trip.truck.tire_wear_pct = 0.0,
                WearMeter::Brake => d.trip.truck.brake_wear_pct = 0.0,
            }
            advance_rest_clock(d, ctx, minutes, Some("on_duty_not_driving"), &duty_note);
            hos_mut_of(ctx).on_duty(minutes);
            if carrier {
                format!(
                    "The shop {carrier_done} at {} percent wear on the carrier account. It is \
                     {}. {}",
                    fmt_f(wear, 0),
                    clock_text(d.trip.local_hour()),
                    deadline_text(d, ctx)
                )
            } else {
                let money = profile_of(ctx).money;
                format!(
                    "{done_say} {} dollars. It is {}. You have {} dollars. {}",
                    fmt_grouped(cost, 0),
                    clock_text(d.trip.local_hour()),
                    fmt_grouped(money, 0),
                    deadline_text(d, ctx)
                )
            }
        }) else {
            return;
        };
        self.save_here(ctx, true);
        ctx.audio.play("ui/notify");
        ctx.say(&text);
        self.refresh(ctx, true);
    }

    fn buff_price(&self, buff: &Buff) -> f64 {
        if buff.free_with_fuel && self.fueled_here {
            return 0.0;
        }
        buff.price
    }

    fn buff_label(&self, buff: &Buff) -> String {
        let price = self.buff_price(buff);
        if price <= 0.0 {
            return format!("{}: free with your fuel purchase", buff.label);
        }
        format!("{}: {} dollars", buff.label, fmt_grouped(price, 0))
    }

    /// Apply a consumable buff purchase (`data/buffs.rs`).
    ///
    /// Food, drink, and showers are personal money even for company drivers
    /// -- the carrier pays for the truck, not your dinner. Rig care (lube,
    /// tires) is truck work, so the carrier covers it.
    fn buy_buff(&mut self, ctx: &mut GameContext, buff_id: &str) {
        let action_refs: Vec<&str> = self.stop.actions.iter().map(String::as_str).collect();
        let Some(buff) = buffs_for_stop(&self.stop.name, &action_refs)
            .into_iter()
            .find(|b| b.id == buff_id)
        else {
            return;
        };
        let price = self.buff_price(buff);
        let rig_buff = buff.group == "engine" || buff.group == "tire";
        let carrier_pays =
            rig_buff && !player_pays_operating_costs(&profile_of(ctx).business_status);
        if !carrier_pays && profile_of(ctx).money < price {
            ctx.audio.play("ui/error");
            ctx.say(&format!(
                "The {} costs {} dollars and you have {}.",
                buff.label.to_lowercase(),
                fmt_grouped(price, 0),
                fmt_grouped(profile_of(ctx).money, 0)
            ));
            return;
        }
        if !carrier_pays {
            profile_mut_of(ctx).money -= price;
        }
        let Some(text) = self.driving.clone().with(ctx, |d, ctx| {
            if rig_buff {
                d.rig_buffs.insert(
                    buff.group.clone(),
                    RigBuff {
                        id: buff.id.clone(),
                        label: buff.label.clone(),
                        rate: buff.rate,
                    },
                );
                advance_rest_clock(
                    d,
                    ctx,
                    buff.stop_minutes,
                    Some("on_duty_not_driving"),
                    &buff.label.to_lowercase(),
                );
                hos_mut_of(ctx).on_duty(buff.stop_minutes);
            } else {
                if buff.fatigue_instant > 0.0 {
                    let p = profile_mut_of(ctx);
                    p.fatigue = (p.fatigue - buff.fatigue_instant).max(0.0);
                }
                let expires_h = d.absolute_game_hour(ctx, None) + buff.duration_game_h;
                profile_mut_of(ctx).add_timed_buff(json!({
                    "id": buff.id,
                    "label": buff.label,
                    "group": buff.group,
                    "rate": buff.rate,
                    "expires_h": expires_h,
                    "worn_off": buff.worn_off,
                }));
                // Real off-duty time: a 30-minute meal also satisfies the
                // break rule, same as any other break. Never extra hours.
                advance_rest_clock(
                    d,
                    ctx,
                    buff.stop_minutes,
                    Some("off_duty"),
                    &buff.label.to_lowercase(),
                );
                hos_mut_of(ctx).take_break(buff.stop_minutes);
            }
            let billing = if carrier_pays {
                "Billed to the carrier.".to_string()
            } else if price <= 0.0 {
                "Free with your fuel purchase.".to_string()
            } else {
                format!(
                    "{} dollars. You have {} dollars.",
                    fmt_grouped(price, 0),
                    fmt_grouped(profile_of(ctx).money, 0)
                )
            };
            format!(
                "{} {billing} It is {}. {}",
                buff.purchased,
                clock_text(d.trip.local_hour()),
                deadline_text(d, ctx)
            )
        }) else {
            return;
        };
        self.save_here(ctx, true);
        ctx.audio.play("ui/notify");
        ctx.say(&text);
        self.refresh(ctx, true);
    }

    fn inspect(&mut self, ctx: &mut GameContext) {
        let stop = self.stop.clone();
        let Some(text) = self.driving.clone().with(ctx, |d, ctx| {
            advance_rest_clock(d, ctx, INSPECTION_MIN, None, "");
            hos_mut_of(ctx).on_duty(INSPECTION_MIN);
            ctx.audio.play("ui/notify");
            // Whether the screening lane waves you through or pulls you in is
            // the safety record's job. A clean career is waved through nearly
            // every time; a career carrying citations, out-of-service history
            // and a beaten-up truck is pulled in at every open scale.
            let selected = d.scale_selects_driver(ctx, &stop);
            let outcome = if selected {
                "Officers pull you into the inspection lane."
            } else {
                "Officers wave you straight back onto the highway."
            };
            format!(
                "Inspection check-in complete at {}. {outcome} {} It is {}. {}",
                stop.spoken_name(),
                d.safety_record_line(ctx),
                clock_text(d.trip.local_hour()),
                deadline_text(d, ctx)
            )
        }) else {
            return;
        };
        ctx.say(&text);
        record_inspection(ctx);
    }
}

/// Check real-time parking availability for this stop.
fn check_parking_availability(d: &mut DrivingState) -> Option<String> {
    let provider = d.trip.parking_provider.clone()?;
    // Ask about the state and position the truck is actually at; the provider
    // answers empty for states without a live TPIMS feed.
    let state = d.trip.state_at(None);
    if state.is_empty() {
        return None;
    }
    let (latitude, longitude) = d.trip.latlon_at(None);
    let locations = provider.get_available_locations_near(&state, latitude, longitude, 25.0);
    if locations.is_empty() {
        return Some("No real-time parking data available nearby.".to_string());
    }
    // Find the closest location with available spaces
    let total_available: i64 = locations.iter().map(|loc| loc.available.unwrap_or(0)).sum();
    if total_available > 0 {
        Some(format!(
            "Real-time parking: {total_available} spaces available nearby."
        ))
    } else {
        Some("Real-time parking: nearby lots are full.".to_string())
    }
}

fn sleeper_split_help(hours: i64) -> String {
    let pair = match hours {
        2 => "Can pair with 8 hours in the sleeper berth.",
        3 => "Can pair with 7 hours in the sleeper berth.",
        7 => "Can pair with 3 more hours at sleep-capable parking.",
        _ => "Can pair with 2 more hours at sleep-capable parking.",
    };
    format!("{pair} The clock and your deadline advance {hours} hours.")
}

fn brake_label(ctx: &GameContext, d: &DrivingState) -> String {
    let wear = d.trip.truck.brake_wear_pct;
    if wear < 1.0 {
        return "Brakes: shoes are in top shape".to_string();
    }
    if !player_pays_operating_costs(&profile_of(ctx).business_status) {
        return format!("Brake job: {} percent wear, carrier billed", fmt_f(wear, 0));
    }
    let cost = round_py_n(wear * ROAD_BRAKE_COST_PER_PCT, 2);
    format!(
        "Brake job: {} percent wear for {} dollars",
        fmt_f(wear, 0),
        fmt_grouped(cost, 0)
    )
}

/// Python `str.capitalize()`.
fn py_capitalize(text: &str) -> String {
    ff_core::data::world_models::py_capitalize(text)
}

impl FuelPump for RestStopState {
    fn drive(&self) -> &DriveRef {
        &self.driving
    }

    fn stop(&self) -> &RoadStop {
        &self.stop
    }

    fn fueled_here(&self) -> bool {
        self.fueled_here
    }

    fn set_fueled_here(&mut self, fueled: bool) {
        self.fueled_here = fueled;
    }
}

impl Menu for RestStopState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let built = self
            .driving
            .clone()
            .call(self, ctx, |s, ctx, d| s.rows(ctx, d));
        keep_rows(built, &self.driving, &self.menu.items)
    }

    fn enter(&mut self, ctx: &mut GameContext) {
        self.confirm_sleep_rested = false;
        let items = self.build_items(ctx);
        self.menu.items = items;
        self.place_cursor(ctx);
        if let Some(key) = self.menu.open_sound_key.clone() {
            ctx.audio.play(&key);
        }
        self.announce_entry(ctx);
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        self.driving
            .clone()
            .call(self, ctx, |s, ctx, d| s.announce_over_drive(ctx, d));
    }

    // Moving off a sleep item withdraws its pending double-press
    // confirmation, so a stale "press Enter again" can never sleep you
    // silently later.
    fn move_by(&mut self, ctx: &mut GameContext, delta: i64) {
        self.confirm_sleep_rested = false;
        let core = self.menu_mut();
        if core.items.is_empty() {
            return;
        }
        let n = core.items.len() as i64;
        core.index = ((core.index as i64 + delta).rem_euclid(n)) as usize;
        ctx.audio.play("ui/menu_move");
        self.speak_current(ctx);
    }

    fn jump(&mut self, ctx: &mut GameContext, index: usize) {
        self.confirm_sleep_rested = false;
        let core = self.menu_mut();
        if core.items.is_empty() {
            return;
        }
        core.index = index.min(core.items.len() - 1);
        ctx.audio.play("ui/menu_move");
        self.speak_current(ctx);
    }

    fn presence(&self, ctx: &GameContext) -> Option<PresenceState> {
        let detail = self
            .driving
            .read(|d| d.presence_state(ctx).map(|p| p.detail).unwrap_or_default())
            .unwrap_or_default();
        Some(PresenceState::new("Resting at a stop", &detail))
    }

    fn online_presence(&self, ctx: &GameContext) -> Option<PresenceState> {
        self.presence(ctx)
    }

    fn go_back(&mut self, ctx: &mut GameContext) {
        ctx.audio.play("ui/menu_back");
        ctx.pop_state();
        let engine = ctx.control_hint("engine");
        let brake = ctx.control_hint("parking_brake");
        ctx.say_with(
            format!(
                "Back on the road. The parking brake is set. Press {engine} to start the engine \
                 if needed, then {brake} to release the brake and drive on."
            ),
            Say::new(),
        );
    }
}

impl_state_for_menu!(RestStopState);
