//! Terminal garage fuel and repair menu (port of
//! `freight_fate/states/city_garage.py`).

use ff_core::models::business::player_pays_operating_costs;
use ff_core::models::economy::{damage_severity_mult, Economy, REPAIR_COST_PER_PCT};
use ff_core::models::profile::Profile;
use ff_core::pyfmt::{fmt_f, fmt_grouped, round_py_n};

use crate::app::GameContext;
use crate::impl_state_for_menu;
use crate::meaningful_play::MeaningfulPlayReason;
use crate::states::base::{Label, Menu, MenuCore, MenuItem};
use crate::states::city::{profile, profile_mut};
use crate::states::city_business::{TrailerProgramState, TruckShopState, UpgradeShopState};

pub const TERMINAL_FUEL_MIN: f64 = 20.0;
pub const TERMINAL_REPAIR_MIN: f64 = 60.0;
pub const TERMINAL_TIRE_MIN: f64 = 45.0;
pub const TERMINAL_BRAKE_MIN: f64 = 90.0;
pub const TERMINAL_ENGINE_MIN: f64 = 240.0;
pub const TERMINAL_WASH_MIN: f64 = 20.0;
pub const TIRE_SERVICE_COST_PER_PCT: f64 = 45.0;
pub const BRAKE_SERVICE_COST_PER_PCT: f64 = 40.0;
pub const ENGINE_OVERHAUL_COST_PER_PCT: f64 = 120.0;
pub const TRUCK_WASH_COST: f64 = 35.0;
// Traction equipment. A tire-compound swap is a fresh set at that compound's
// price -- the tread you hand back is gone, like real life. Winter rubber
// carries a real premium; chains are a per-truck set that lives in the side
// box until a pass calls for them.
pub const WINTER_TIRE_PREMIUM: f64 = 1.25;
pub const CHAIN_SET_COST: f64 = 750.0;
pub const TERMINAL_CHAINS_MIN: f64 = 10.0;

fn record_terminal_duty(ctx: &mut GameContext, start_hour: f64, end_hour: f64, note: &str) {
    let terminal = crate::states::city::home_terminal(ctx);
    profile_mut(ctx).duty_log.record(
        "on_duty_not_driving",
        start_hour,
        end_hour,
        &terminal.name,
        note,
    );
}

fn save_equipment_change(ctx: &mut GameContext) {
    ctx.mark_meaningful_play(MeaningfulPlayReason::EquipmentChanged);
    ctx.save_profile();
}

/// The two wear meters that share one service flow (`_service_wear_meter`).
#[derive(Clone, Copy)]
enum WearMeter {
    Brakes,
    Engine,
}

impl WearMeter {
    fn read(self, p: &Profile) -> f64 {
        match self {
            WearMeter::Brakes => p.brake_wear_pct(),
            WearMeter::Engine => p.engine_wear_pct(),
        }
    }

    fn write(self, p: &mut Profile, value: f64) {
        match self {
            WearMeter::Brakes => p.set_brake_wear_pct(value),
            WearMeter::Engine => p.set_engine_wear_pct(value),
        }
    }
}

/// The wording of one wear-meter service.
struct WearService {
    meter: WearMeter,
    cost_per_pct: f64,
    minutes: f64,
    duty_note: &'static str,
    fresh_say: &'static str,
    carrier_done: &'static str,
    partial_noun: &'static str,
    done_say: &'static str,
}

pub struct GarageState {
    menu: MenuCore<Self>,
}

impl Default for GarageState {
    fn default() -> Self {
        Self::new()
    }
}

impl GarageState {
    pub fn new() -> Self {
        GarageState {
            menu: MenuCore::new("Garage"),
        }
    }

    fn region(ctx: &GameContext) -> String {
        ctx.world
            .city(&profile(ctx).current_city)
            .map(|c| c.region.clone())
            .unwrap_or_default()
    }

    fn tank_gal(ctx: &GameContext) -> f64 {
        profile(ctx).truck_specs().fuel_tank_gal
    }

    fn fuel_label(ctx: &GameContext) -> String {
        let p = profile(ctx);
        let need = Self::tank_gal(ctx) - p.truck_fuel_gal();
        if need < 1.0 {
            return "Fuel: tank is full".to_string();
        }
        if !player_pays_operating_costs(&p.business_status) {
            return format!(
                "Refuel assigned company tractor: {} gallons, carrier billed",
                fmt_f(need, 0)
            );
        }
        let cost = ctx.economy.fuel_cost(&Self::region(ctx), need);
        format!(
            "Refuel {} gallons for {} dollars",
            fmt_f(need, 0),
            fmt_grouped(cost, 0)
        )
    }

    fn repair_label(ctx: &GameContext) -> String {
        let p = profile(ctx);
        if p.truck_damage_pct() < 1.0 {
            return "Repairs: truck is in top shape".to_string();
        }
        if !player_pays_operating_costs(&p.business_status) {
            return format!(
                "Repair assigned company tractor: {} percent damage, carrier billed",
                fmt_f(p.truck_damage_pct(), 0)
            );
        }
        let cost = Economy::repair_cost(p.truck_damage_pct());
        format!(
            "Repair {} percent damage for {} dollars",
            fmt_f(p.truck_damage_pct(), 0),
            fmt_grouped(cost, 0)
        )
    }

    pub fn refuel(&mut self, ctx: &mut GameContext) {
        let tank = Self::tank_gal(ctx);
        let need = tank - profile(ctx).truck_fuel_gal();
        if need < 1.0 {
            ctx.say("The tank is already full.");
            return;
        }
        if !player_pays_operating_costs(&profile(ctx).business_status) {
            let money = {
                let p = profile_mut(ctx);
                p.set_truck_fuel_gal(tank);
                p.game_hours += TERMINAL_FUEL_MIN / 60.0;
                p.hos.on_duty(TERMINAL_FUEL_MIN);
                p.money
            };
            ctx.save_profile();
            ctx.audio.play("vehicle/fuel_pump");
            ctx.say(&format!(
                "Assigned company tractor tank filled on the carrier fuel account. Fueling took \
                 {} minutes. You still have \
                 {} dollars.",
                fmt_f(TERMINAL_FUEL_MIN, 0),
                fmt_grouped(money, 0)
            ));
            ctx.award_achievement("route_refuel");
            self.refresh(ctx, true);
            return;
        }
        let cost = ctx.economy.fuel_cost(&Self::region(ctx), need);
        if profile(ctx).money < cost {
            self.partial_refuel(ctx, tank);
            return;
        }
        let (start, end, money) = {
            let p = profile_mut(ctx);
            p.money -= cost;
            p.set_truck_fuel_gal(tank);
            let start = p.game_hours;
            p.game_hours += TERMINAL_FUEL_MIN / 60.0;
            (start, p.game_hours, p.money)
        };
        record_terminal_duty(ctx, start, end, "terminal fuel");
        profile_mut(ctx).hos.on_duty(TERMINAL_FUEL_MIN);
        ctx.save_profile();
        ctx.audio.play("vehicle/fuel_pump");
        ctx.say(&format!(
            "Tank filled. {} dollars. You have {} dollars left.",
            fmt_grouped(cost, 0),
            fmt_grouped(money, 0)
        ));
        ctx.award_achievement("route_refuel");
        self.refresh(ctx, true);
    }

    fn partial_refuel(&mut self, ctx: &mut GameContext, tank: f64) {
        let region = Self::region(ctx);
        let price = ctx.economy.fuel_price(&region);
        let gallons = if price > 0.0 {
            profile(ctx).money / price
        } else {
            0.0
        };
        if gallons < 1.0 {
            ctx.audio.play("ui/error");
            ctx.say("Not enough money for even one gallon of fuel.");
            return;
        }
        let cost = ctx.economy.fuel_cost(&region, gallons);
        let (start, end, money) = {
            let p = profile_mut(ctx);
            p.money -= cost;
            let fuel = tank.min(p.truck_fuel_gal() + gallons);
            p.set_truck_fuel_gal(fuel);
            let start = p.game_hours;
            p.game_hours += TERMINAL_FUEL_MIN / 60.0;
            (start, p.game_hours, p.money)
        };
        record_terminal_duty(ctx, start, end, "terminal fuel");
        profile_mut(ctx).hos.on_duty(TERMINAL_FUEL_MIN);
        ctx.save_profile();
        ctx.audio.play("vehicle/fuel_pump");
        ctx.say(&format!(
            "Partial fuel: added {} gallons for \
             {} dollars. \
             You have {} dollars left.",
            fmt_f(gallons, 0),
            fmt_grouped(cost, 0),
            fmt_grouped(money, 0)
        ));
        ctx.award_achievement("route_refuel");
        self.refresh(ctx, true);
    }

    pub fn repair(&mut self, ctx: &mut GameContext) {
        let damage = profile(ctx).truck_damage_pct();
        if damage < 1.0 {
            ctx.say("Nothing to repair.");
            return;
        }
        let deep_damage = damage >= 75.0;
        if !player_pays_operating_costs(&profile(ctx).business_status) {
            let fixed = damage;
            {
                let p = profile_mut(ctx);
                p.set_truck_damage_pct(0.0);
                p.game_hours += TERMINAL_REPAIR_MIN / 60.0;
                p.hos.on_duty(TERMINAL_REPAIR_MIN);
            }
            save_equipment_change(ctx);
            ctx.audio.play("ui/notify");
            ctx.say(&format!(
                "Carrier shop repaired {} percent damage on the assigned tractor. \
                 The repair took {} minutes and did \
                 not reduce your cash balance.",
                fmt_f(fixed, 0),
                fmt_f(TERMINAL_REPAIR_MIN, 0)
            ));
            ctx.award_achievement("garage_repair");
            if deep_damage {
                ctx.award_achievement("deep_repair");
            }
            self.refresh(ctx, true);
            return;
        }
        let cost = Economy::repair_cost(damage);
        if profile(ctx).money < cost {
            self.partial_repair(ctx);
            return;
        }
        let (start, end, money) = {
            let p = profile_mut(ctx);
            p.money -= cost;
            p.set_truck_damage_pct(0.0);
            let start = p.game_hours;
            p.game_hours += TERMINAL_REPAIR_MIN / 60.0;
            (start, p.game_hours, p.money)
        };
        record_terminal_duty(ctx, start, end, "terminal repair");
        profile_mut(ctx).hos.on_duty(TERMINAL_REPAIR_MIN);
        save_equipment_change(ctx);
        ctx.audio.play("ui/notify");
        ctx.say(&format!(
            "Truck repaired. {} dollars. You have {} dollars left.",
            fmt_grouped(cost, 0),
            fmt_grouped(money, 0)
        ));
        ctx.award_achievement("garage_repair");
        if deep_damage {
            ctx.award_achievement("deep_repair");
        }
        self.refresh(ctx, true);
    }

    fn partial_repair(&mut self, ctx: &mut GameContext) {
        // The shop works down from the worst of it, so what a short wallet
        // buys is priced at the depth it starts from, not at the flat rate.
        // Dividing the money by the flat rate quoted more percent than the
        // curve actually sells and overdrew the account by pennies.
        let (money, damage) = {
            let p = profile(ctx);
            (p.money, p.truck_damage_pct())
        };
        let mut repairable = money / (REPAIR_COST_PER_PCT * damage_severity_mult(damage));
        repairable = repairable.min(damage);
        if repairable < 1.0 {
            ctx.audio.play("ui/error");
            ctx.say("Not enough money for one percent of repairs.");
            return;
        }
        let cost = money.min(round_py_n(
            repairable * REPAIR_COST_PER_PCT * damage_severity_mult(damage),
            2,
        ));
        let (start, end, money) = {
            let p = profile_mut(ctx);
            p.money -= cost;
            p.set_truck_damage_pct((damage - repairable).max(0.0));
            let start = p.game_hours;
            p.game_hours += TERMINAL_REPAIR_MIN / 60.0;
            (start, p.game_hours, p.money)
        };
        record_terminal_duty(ctx, start, end, "terminal repair");
        profile_mut(ctx).hos.on_duty(TERMINAL_REPAIR_MIN);
        save_equipment_change(ctx);
        ctx.audio.play("ui/notify");
        ctx.say(&format!(
            "Partial repairs fixed {} percent damage \
             for {} dollars. \
             You have {} dollars left.",
            fmt_f(repairable, 0),
            fmt_grouped(cost, 0),
            fmt_grouped(money, 0)
        ));
        ctx.award_achievement("garage_repair");
        self.refresh(ctx, true);
    }

    fn tire_cost_per_pct(ctx: &GameContext) -> f64 {
        let premium = if profile(ctx).tire_type() == "winter" {
            WINTER_TIRE_PREMIUM
        } else {
            1.0
        };
        TIRE_SERVICE_COST_PER_PCT * premium
    }

    fn compound_word(ctx: &GameContext) -> &'static str {
        if profile(ctx).tire_type() == "winter" {
            "winter"
        } else {
            "all-season"
        }
    }

    fn tire_label(ctx: &GameContext) -> String {
        let p = profile(ctx);
        let wear = p.tire_wear_pct();
        if wear < 1.0 {
            return format!("Tires: {} tread is in top shape", Self::compound_word(ctx));
        }
        if !player_pays_operating_costs(&p.business_status) {
            return format!(
                "Replace tires on assigned company tractor: {} percent wear, carrier billed",
                fmt_f(wear, 0)
            );
        }
        let cost = round_py_n(wear * Self::tire_cost_per_pct(ctx), 2);
        format!(
            "Replace {} tires: {} percent wear for {} dollars",
            Self::compound_word(ctx),
            fmt_f(wear, 0),
            fmt_grouped(cost, 0)
        )
    }

    fn brake_label(ctx: &GameContext) -> String {
        let p = profile(ctx);
        let wear = p.brake_wear_pct();
        if wear < 1.0 {
            return "Brakes: shoes are in top shape".to_string();
        }
        if !player_pays_operating_costs(&p.business_status) {
            return format!(
                "Brake job on assigned company tractor: {} percent wear, carrier billed",
                fmt_f(wear, 0)
            );
        }
        let cost = round_py_n(wear * BRAKE_SERVICE_COST_PER_PCT, 2);
        format!(
            "Brake job: {} percent wear for {} dollars",
            fmt_f(wear, 0),
            fmt_grouped(cost, 0)
        )
    }

    fn engine_label(ctx: &GameContext) -> String {
        let p = profile(ctx);
        let wear = p.engine_wear_pct();
        if wear < 1.0 {
            return "Engine: running like new".to_string();
        }
        if !player_pays_operating_costs(&p.business_status) {
            return format!(
                "Engine overhaul on assigned company tractor: \
                 {} percent wear, carrier billed",
                fmt_f(wear, 0)
            );
        }
        let cost = round_py_n(wear * ENGINE_OVERHAUL_COST_PER_PCT, 2);
        format!(
            "Engine overhaul: {} percent wear for {} dollars",
            fmt_f(wear, 0),
            fmt_grouped(cost, 0)
        )
    }

    fn wash_label(ctx: &GameContext) -> String {
        let p = profile(ctx);
        let grime = p.road_grime_pct();
        if grime < 1.0 {
            return "Wash: truck is clean".to_string();
        }
        if !player_pays_operating_costs(&p.business_status) {
            return format!(
                "Wash assigned company tractor: {} percent road grime, carrier billed",
                fmt_f(grime, 0)
            );
        }
        format!(
            "Wash truck: {} percent road grime for {} dollars",
            fmt_f(grime, 0),
            fmt_grouped(TRUCK_WASH_COST, 0)
        )
    }

    pub fn service_tires(&mut self, ctx: &mut GameContext) {
        let wear = profile(ctx).tire_wear_pct();
        if wear < 1.0 {
            ctx.say("The tires are already in top shape.");
            return;
        }
        let start = profile(ctx).game_hours;
        if !player_pays_operating_costs(&profile(ctx).business_status) {
            let end = {
                let p = profile_mut(ctx);
                p.set_tire_wear_pct(0.0);
                p.game_hours += TERMINAL_TIRE_MIN / 60.0;
                p.game_hours
            };
            record_terminal_duty(ctx, start, end, "tire service");
            profile_mut(ctx).hos.on_duty(TERMINAL_TIRE_MIN);
            save_equipment_change(ctx);
            ctx.audio.play("ui/notify");
            ctx.say(&format!(
                "Carrier shop replaced tires with {} percent wear on \
                 the assigned tractor. The service took \
                 {} minutes and did not reduce your \
                 cash balance.",
                fmt_f(wear, 0),
                fmt_f(TERMINAL_TIRE_MIN, 0)
            ));
            self.refresh(ctx, true);
            return;
        }
        let per_pct = Self::tire_cost_per_pct(ctx);
        let mut cost = round_py_n(wear * per_pct, 2);
        if profile(ctx).money < cost {
            let serviceable = profile(ctx).money / per_pct;
            if serviceable < 1.0 {
                ctx.audio.play("ui/error");
                ctx.say("Not enough money for one percent of tire service.");
                return;
            }
            cost = round_py_n(serviceable * per_pct, 2);
            let (end, money) = {
                let p = profile_mut(ctx);
                p.money -= cost;
                p.set_tire_wear_pct((p.tire_wear_pct() - serviceable).max(0.0));
                p.game_hours += TERMINAL_TIRE_MIN / 60.0;
                (p.game_hours, p.money)
            };
            record_terminal_duty(ctx, start, end, "tire service");
            profile_mut(ctx).hos.on_duty(TERMINAL_TIRE_MIN);
            save_equipment_change(ctx);
            ctx.audio.play("ui/notify");
            ctx.say(&format!(
                "Partial tire service fixed {} percent wear \
                 for {} dollars. \
                 You have {} dollars left.",
                fmt_f(serviceable, 0),
                fmt_grouped(cost, 0),
                fmt_grouped(money, 0)
            ));
            self.refresh(ctx, true);
            return;
        }
        let (end, money) = {
            let p = profile_mut(ctx);
            p.money -= cost;
            p.set_tire_wear_pct(0.0);
            p.game_hours += TERMINAL_TIRE_MIN / 60.0;
            (p.game_hours, p.money)
        };
        record_terminal_duty(ctx, start, end, "tire service");
        profile_mut(ctx).hos.on_duty(TERMINAL_TIRE_MIN);
        save_equipment_change(ctx);
        ctx.audio.play("ui/notify");
        ctx.say(&format!(
            "Tires replaced. {} dollars. You have {} dollars left.",
            fmt_grouped(cost, 0),
            fmt_grouped(money, 0)
        ));
        self.refresh(ctx, true);
    }

    fn tire_swap_label(ctx: &GameContext) -> String {
        let p = profile(ctx);
        if !player_pays_operating_costs(&p.business_status) {
            return "Tire compound: the carrier specs its own rubber".to_string();
        }
        if p.tire_type() == "winter" {
            let cost = round_py_n(100.0 * TIRE_SERVICE_COST_PER_PCT, 2);
            return format!(
                "Switch to all-season tires: fresh set for {} dollars",
                fmt_grouped(cost, 0)
            );
        }
        let cost = round_py_n(100.0 * TIRE_SERVICE_COST_PER_PCT * WINTER_TIRE_PREMIUM, 2);
        format!(
            "Switch to winter tires: fresh set for {} dollars",
            fmt_grouped(cost, 0)
        )
    }

    pub fn swap_tire_compound(&mut self, ctx: &mut GameContext) {
        if !player_pays_operating_costs(&profile(ctx).business_status) {
            ctx.say(
                "The carrier decides what rubber the assigned tractor runs. \
                 Company tractors stay on all-season tires.",
            );
            return;
        }
        let to_winter = profile(ctx).tire_type() != "winter";
        let premium = if to_winter { WINTER_TIRE_PREMIUM } else { 1.0 };
        let cost = round_py_n(100.0 * TIRE_SERVICE_COST_PER_PCT * premium, 2);
        let compound = if to_winter { "winter" } else { "all-season" };
        if profile(ctx).money < cost {
            ctx.audio.play("ui/error");
            ctx.say(&format!(
                "A fresh set of {compound} tires \
                 costs {} dollars.",
                fmt_grouped(cost, 0)
            ));
            return;
        }
        let (start, end, money) = {
            let p = profile_mut(ctx);
            let start = p.game_hours;
            p.money -= cost;
            p.set_tire_type(if to_winter { "winter" } else { "all_season" });
            p.set_tire_wear_pct(0.0);
            p.game_hours += TERMINAL_TIRE_MIN / 60.0;
            (start, p.game_hours, p.money)
        };
        record_terminal_duty(ctx, start, end, "tire swap");
        profile_mut(ctx).hos.on_duty(TERMINAL_TIRE_MIN);
        save_equipment_change(ctx);
        ctx.audio.play("ui/notify");
        let trade = if to_winter {
            "Better bite on snow and ice; the soft compound wears faster and \
             gives up a little on warm dry pavement."
        } else {
            "Back to the everyday tire: longer tread life, standard grip."
        };
        ctx.say(&format!(
            "Fresh {compound} set mounted for \
             {} dollars. {trade} \
             You have {} dollars left.",
            fmt_grouped(cost, 0),
            fmt_grouped(money, 0)
        ));
        self.refresh(ctx, true);
    }

    fn chains_label(ctx: &GameContext) -> String {
        let p = profile(ctx);
        let wear = p.chain_wear_pct();
        let carrier = !player_pays_operating_costs(&p.business_status);
        if !p.chains_owned() || wear >= 100.0 {
            let what = if p.chains_owned() {
                "Replace snapped snow chains"
            } else {
                "Buy snow chains"
            };
            if carrier {
                return format!("{what}: carrier billed");
            }
            return format!("{what}: {} dollars", fmt_grouped(CHAIN_SET_COST, 0));
        }
        if wear >= 1.0 {
            if carrier {
                return format!(
                    "Replace snow chains: {} percent worn, carrier billed",
                    fmt_f(wear, 0)
                );
            }
            return format!(
                "Replace snow chains: {} percent worn, {} dollars",
                fmt_f(wear, 0),
                fmt_grouped(CHAIN_SET_COST, 0)
            );
        }
        "Snow chains: aboard and fresh".to_string()
    }

    pub fn buy_chains(&mut self, ctx: &mut GameContext) {
        {
            let p = profile(ctx);
            if p.chains_owned() && p.chain_wear_pct() < 1.0 {
                ctx.say("A fresh set of chains is already in the side box.");
                return;
            }
        }
        let start = profile(ctx).game_hours;
        if !player_pays_operating_costs(&profile(ctx).business_status) {
            let end = {
                let p = profile_mut(ctx);
                p.set_chains_owned(true);
                p.set_chain_wear_pct(0.0);
                p.game_hours += TERMINAL_CHAINS_MIN / 60.0;
                p.game_hours
            };
            record_terminal_duty(ctx, start, end, "chain set");
            profile_mut(ctx).hos.on_duty(TERMINAL_CHAINS_MIN);
            save_equipment_change(ctx);
            ctx.audio.play("ui/notify");
            ctx.say(
                "A fresh chain set from the carrier shop is stowed in the \
                 side box, on the carrier account.",
            );
            self.refresh(ctx, true);
            return;
        }
        if profile(ctx).money < CHAIN_SET_COST {
            ctx.audio.play("ui/error");
            ctx.say(&format!(
                "A set of snow chains costs {} dollars.",
                fmt_grouped(CHAIN_SET_COST, 0)
            ));
            return;
        }
        let (end, money) = {
            let p = profile_mut(ctx);
            p.money -= CHAIN_SET_COST;
            p.set_chains_owned(true);
            p.set_chain_wear_pct(0.0);
            p.game_hours += TERMINAL_CHAINS_MIN / 60.0;
            (p.game_hours, p.money)
        };
        record_terminal_duty(ctx, start, end, "chain set");
        profile_mut(ctx).hos.on_duty(TERMINAL_CHAINS_MIN);
        save_equipment_change(ctx);
        ctx.audio.play("ui/notify");
        ctx.say(&format!(
            "A fresh chain set is stowed in the side box for \
             {} dollars. \
             You have {} dollars left.",
            fmt_grouped(CHAIN_SET_COST, 0),
            fmt_grouped(money, 0)
        ));
        self.refresh(ctx, true);
    }

    pub fn service_brakes(&mut self, ctx: &mut GameContext) {
        self.service_wear_meter(
            ctx,
            &WearService {
                meter: WearMeter::Brakes,
                cost_per_pct: BRAKE_SERVICE_COST_PER_PCT,
                minutes: TERMINAL_BRAKE_MIN,
                duty_note: "brake service",
                fresh_say: "The brakes are already in top shape.",
                carrier_done: "relined the brakes",
                partial_noun: "brake service",
                done_say: "Brakes relined.",
            },
        );
    }

    pub fn service_engine(&mut self, ctx: &mut GameContext) {
        self.service_wear_meter(
            ctx,
            &WearService {
                meter: WearMeter::Engine,
                cost_per_pct: ENGINE_OVERHAUL_COST_PER_PCT,
                minutes: TERMINAL_ENGINE_MIN,
                duty_note: "engine overhaul",
                fresh_say: "The engine is already running like new.",
                carrier_done: "overhauled the engine",
                partial_noun: "engine work",
                done_say: "Engine overhauled.",
            },
        );
    }

    /// Shared company/partial/full flow for a wear-meter service.
    ///
    /// Mirrors the tire service exactly; tires keep their own wording
    /// because players already know those phrases.
    fn service_wear_meter(&mut self, ctx: &mut GameContext, service: &WearService) {
        let wear = service.meter.read(profile(ctx));
        if wear < 1.0 {
            ctx.say(service.fresh_say);
            return;
        }
        let start = profile(ctx).game_hours;
        if !player_pays_operating_costs(&profile(ctx).business_status) {
            let end = {
                let p = profile_mut(ctx);
                service.meter.write(p, 0.0);
                p.game_hours += service.minutes / 60.0;
                p.game_hours
            };
            record_terminal_duty(ctx, start, end, service.duty_note);
            profile_mut(ctx).hos.on_duty(service.minutes);
            save_equipment_change(ctx);
            ctx.audio.play("ui/notify");
            ctx.say(&format!(
                "Carrier shop {} at {} percent wear on \
                 the assigned tractor. The service took {} \
                 minutes and did not reduce your cash balance.",
                service.carrier_done,
                fmt_f(wear, 0),
                fmt_f(service.minutes, 0)
            ));
            self.refresh(ctx, true);
            return;
        }
        let mut cost = round_py_n(wear * service.cost_per_pct, 2);
        if profile(ctx).money < cost {
            let serviceable = profile(ctx).money / service.cost_per_pct;
            if serviceable < 1.0 {
                ctx.audio.play("ui/error");
                ctx.say(&format!(
                    "Not enough money for one percent of {}.",
                    service.partial_noun
                ));
                return;
            }
            cost = round_py_n(serviceable * service.cost_per_pct, 2);
            let (end, money) = {
                let p = profile_mut(ctx);
                p.money -= cost;
                service.meter.write(p, (wear - serviceable).max(0.0));
                p.game_hours += service.minutes / 60.0;
                (p.game_hours, p.money)
            };
            record_terminal_duty(ctx, start, end, service.duty_note);
            profile_mut(ctx).hos.on_duty(service.minutes);
            save_equipment_change(ctx);
            ctx.audio.play("ui/notify");
            ctx.say(&format!(
                "Partial {} fixed {} percent wear \
                 for {} dollars. \
                 You have {} dollars left.",
                service.partial_noun,
                fmt_f(serviceable, 0),
                fmt_grouped(cost, 0),
                fmt_grouped(money, 0)
            ));
            self.refresh(ctx, true);
            return;
        }
        let (end, money) = {
            let p = profile_mut(ctx);
            p.money -= cost;
            service.meter.write(p, 0.0);
            p.game_hours += service.minutes / 60.0;
            (p.game_hours, p.money)
        };
        record_terminal_duty(ctx, start, end, service.duty_note);
        profile_mut(ctx).hos.on_duty(service.minutes);
        save_equipment_change(ctx);
        ctx.audio.play("ui/notify");
        ctx.say(&format!(
            "{} {} dollars. You have {} dollars left.",
            service.done_say,
            fmt_grouped(cost, 0),
            fmt_grouped(money, 0)
        ));
        self.refresh(ctx, true);
    }

    pub fn wash_truck(&mut self, ctx: &mut GameContext) {
        if profile(ctx).road_grime_pct() < 1.0 {
            ctx.say("The truck is already clean.");
            return;
        }
        let start = profile(ctx).game_hours;
        if !player_pays_operating_costs(&profile(ctx).business_status) {
            let (grime, end) = {
                let p = profile_mut(ctx);
                let grime = p.road_grime_pct();
                p.set_road_grime_pct(0.0);
                p.game_hours += TERMINAL_WASH_MIN / 60.0;
                (grime, p.game_hours)
            };
            record_terminal_duty(ctx, start, end, "truck wash");
            profile_mut(ctx).hos.on_duty(TERMINAL_WASH_MIN);
            ctx.save_profile();
            ctx.audio.play("ui/notify");
            ctx.say(&format!(
                "Carrier account covered the truck wash: {} percent \
                 road grime cleaned off the assigned tractor.",
                fmt_f(grime, 0)
            ));
            self.refresh(ctx, true);
            return;
        }
        if profile(ctx).money < TRUCK_WASH_COST {
            ctx.audio.play("ui/error");
            ctx.say(&format!(
                "A truck wash costs {} dollars.",
                fmt_grouped(TRUCK_WASH_COST, 0)
            ));
            return;
        }
        let (end, money) = {
            let p = profile_mut(ctx);
            p.money -= TRUCK_WASH_COST;
            p.set_road_grime_pct(0.0);
            p.game_hours += TERMINAL_WASH_MIN / 60.0;
            (p.game_hours, p.money)
        };
        record_terminal_duty(ctx, start, end, "truck wash");
        profile_mut(ctx).hos.on_duty(TERMINAL_WASH_MIN);
        ctx.save_profile();
        ctx.audio.play("ui/notify");
        ctx.say(&format!(
            "Truck washed for {} dollars. \
             You have {} dollars left.",
            fmt_grouped(TRUCK_WASH_COST, 0),
            fmt_grouped(money, 0)
        ));
        self.refresh(ctx, true);
    }

    fn upgrades(&mut self, ctx: &mut GameContext) {
        ctx.push_state(UpgradeShopState::new());
    }

    fn trucks(&mut self, ctx: &mut GameContext) {
        ctx.push_state(TruckShopState::new(false));
    }

    fn trailers(&mut self, ctx: &mut GameContext) {
        ctx.push_state(TrailerProgramState::new());
    }
}

impl Menu for GarageState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn build_items(&mut self, _ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        vec![
            MenuItem::new(
                Label::dynamic(|_s: &Self, ctx| Self::fuel_label(ctx)),
                |s: &mut Self, ctx| s.refuel(ctx),
            )
            .help(
                "Fill the tank. Company drivers use carrier-assigned tractors and bill the carrier. \
                 Owner-operators pay this region's diesel price.",
            ),
            MenuItem::new(
                Label::dynamic(|_s: &Self, ctx| Self::repair_label(ctx)),
                |s: &mut Self, ctx| s.repair(ctx),
            )
            .help(
                "Restore the tractor to full condition. Company drivers \
                 bill the carrier; owner-operators pay the shop.",
            ),
            MenuItem::new(
                Label::dynamic(|_s: &Self, ctx| Self::tire_label(ctx)),
                |s: &mut Self, ctx| s.service_tires(ctx),
            )
            .help(
                "Replace worn tires. Normal miles add slow tire wear, \
                 even when you drive cleanly; heavy loads and hard braking \
                 add more. Worn tires grip the road less. Company drivers \
                 bill the carrier; owner-operators pay the shop.",
            ),
            MenuItem::new(
                Label::dynamic(|_s: &Self, ctx| Self::tire_swap_label(ctx)),
                |s: &mut Self, ctx| s.swap_tire_compound(ctx),
            )
            .help(
                "Change tire compound with a fresh set. Winter rubber \
                 bites harder on snow and ice but wears faster and gives up \
                 a little grip on warm dry pavement. All-season is the \
                 cheaper everyday tire. Company tractors run whatever the \
                 carrier specs.",
            ),
            MenuItem::new(
                Label::dynamic(|_s: &Self, ctx| Self::chains_label(ctx)),
                |s: &mut Self, ctx| s.buy_chains(ctx),
            )
            .help(
                "Keep a set of snow chains in the side box. You chain \
                 up from the pause menu when stopped in snow or ice. Chains \
                 grip glare ice like nothing else, but keep it near chain \
                 speed and off bare pavement or they grind apart and snap. \
                 Company drivers bill the carrier.",
            ),
            MenuItem::new(
                Label::dynamic(|_s: &Self, ctx| Self::brake_label(ctx)),
                |s: &mut Self, ctx| s.service_brakes(ctx),
            )
            .help(
                "Reline worn brake shoes. Riding the service brakes \
                 wears them, hot brakes wear faster, and the engine brake \
                 costs them nothing. Worn shoes pull weaker and fade \
                 sooner. Company drivers bill the carrier; owner-operators \
                 pay the shop.",
            ),
            MenuItem::new(
                Label::dynamic(|_s: &Self, ctx| Self::engine_label(ctx)),
                |s: &mut Self, ctx| s.service_engine(ctx),
            )
            .help(
                "Overhaul a tired engine. Hours under load wear it \
                 slowly; over-revving and lugging wear it fast. A worn \
                 engine is down on power and burns more fuel. Company \
                 drivers bill the carrier; owner-operators pay the shop.",
            ),
            MenuItem::new(
                Label::dynamic(|_s: &Self, ctx| Self::wash_label(ctx)),
                |s: &mut Self, ctx| s.wash_truck(ctx),
            )
            .help(
                "Wash road grime off the truck after long or dirty \
                 runs. Company drivers bill the carrier; \
                 owner-operators pay.",
            ),
            MenuItem::new("Upgrades", |s: &mut Self, ctx| s.upgrades(ctx)).help(
                "Owner-operators can buy performance upgrades for \
                 owned tractors: more torque, less drag, a bigger tank, \
                 stronger brakes.",
            ),
            MenuItem::new("Trucks", |s: &mut Self, ctx| s.trucks(ctx)).help(
                "Owner-operators can buy a new truck, or switch between trucks they own.",
            ),
            MenuItem::new("Trailer programs", |s: &mut Self, ctx| s.trailers(ctx)).help(
                "Company drivers use carrier trailers. Owner-operators \
                 can add specialty trailer program slots. Own-authority \
                 drivers can also buy trailers.",
            ),
            MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx))
                .help("Return to the terminal menu."),
        ]
    }
}

impl_state_for_menu!(GarageState);
