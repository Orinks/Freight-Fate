//! The fuel island, for every state that can be standing on one
//! (Python's `_FuelPumpMixin`).
//!
//! A truck stop's pumps and its parking lot are separate facilities, and the
//! lot filling up does not lock the island: a driver turned away from an
//! overnight space can still pull to the pumps, fuel, and leave. Keeping the
//! purchase here rather than on `RestStopState` alone is what lets
//! `ParkingFullState` offer it -- before this, a full lot swallowed the whole
//! stop, and an overnight run could pass a row of open pumps and still go
//! dry.

use ff_core::models::loyalty::loyalty_earnings_text;
use ff_core::pyfmt::{fmt_f, fmt_grouped};
use ff_core::sim::trip_models::RoadStop;

use crate::app::GameContext;
use crate::states::base::Menu;
use crate::states::driving_core::{
    advance_rest_clock, hos_mut_of, player_pays_operating_costs, profile_mut_of, profile_of,
    FUEL_STOP_MIN,
};
use crate::states::driving_menu_states::DriveRef;

pub trait FuelPump: Menu {
    fn drive(&self) -> &DriveRef;
    fn stop(&self) -> &RoadStop;
    /// A fuel purchase this visit (free showers).
    fn fueled_here(&self) -> bool;
    fn set_fueled_here(&mut self, fueled: bool);

    fn fuel_label(&self, ctx: &mut GameContext) -> String {
        let Some((need, region)) = self.drive().with(ctx, |d, _| {
            (
                d.trip.truck.specs.fuel_tank_gal - d.trip.truck.fuel_gal,
                d.trip.current_region().to_string(),
            )
        }) else {
            return "Fuel: tank is full".to_string();
        };
        if need < 1.0 {
            return "Fuel: tank is full".to_string();
        }
        if !player_pays_operating_costs(&profile_of(ctx).business_status) {
            return format!("Refuel {} gallons on the carrier fuel card", fmt_f(need, 0));
        }
        let cost = ctx.economy.fuel_cost(&region, need) + 35.0;
        format!(
            "Refuel {} gallons for {} dollars",
            fmt_f(need, 0),
            fmt_grouped(cost, 0)
        )
    }

    fn refuel(&mut self, ctx: &mut GameContext) {
        let Some((mut need, region)) = self.drive().with(ctx, |d, _| {
            (
                d.trip.truck.specs.fuel_tank_gal - d.trip.truck.fuel_gal,
                d.trip.current_region().to_string(),
            )
        }) else {
            return;
        };
        if need < 1.0 {
            ctx.say("The tank is already full.");
            return;
        }
        let stop_name = self.stop().name.clone();
        let carrier_card = !player_pays_operating_costs(&profile_of(ctx).business_status);
        let mut cost = 0.0;
        if !carrier_card {
            cost = ctx.economy.fuel_cost(&region, need) + 35.0;
            if profile_of(ctx).money < cost {
                let partial_gal =
                    ((profile_of(ctx).money - 35.0) / ctx.economy.fuel_price(&region)).max(0.0);
                if partial_gal < 5.0 {
                    ctx.audio.play("ui/error");
                    ctx.say("You cannot afford fuel here.");
                    return;
                }
                need = partial_gal;
                cost = ctx.economy.fuel_cost(&region, need) + 35.0;
            }
            profile_mut_of(ctx).money -= cost;
        }
        self.drive().clone().with(ctx, |d, ctx| {
            d.trip.truck.refuel(Some(need));
            advance_rest_clock(d, ctx, FUEL_STOP_MIN, None, "");
            hos_mut_of(ctx).on_duty(FUEL_STOP_MIN);
        });
        self.set_fueled_here(true);
        self.save_here(ctx, true);
        ctx.audio.play("vehicle/fuel_pump");

        // Award loyalty points for fueling
        let loyalty_text = {
            let result = profile_mut_of(ctx)
                .loyalty
                .add_fueling(need, None, &stop_name, &region);
            loyalty_earnings_text(need, result.points_earned, &result.rewards)
        };

        if carrier_card {
            // the carrier fuel card covers road fuel for company drivers
            ctx.say(&format!(
                "Refueled {} gallons on the carrier fuel card. Fueling took {} minutes. \
                 {loyalty_text}",
                fmt_f(need, 0),
                fmt_f(FUEL_STOP_MIN, 0)
            ));
        } else {
            let money = profile_of(ctx).money;
            ctx.say(&format!(
                "Refueled {} gallons for {} dollars. You have {} dollars. Fueling took {} \
                 minutes. {loyalty_text}",
                fmt_f(need, 0),
                fmt_grouped(cost, 0),
                fmt_grouped(money, 0),
                fmt_f(FUEL_STOP_MIN, 0)
            ));
        }
        ctx.award_achievement("route_refuel");
        self.refresh(ctx, true);
    }

    fn save_here(&mut self, ctx: &mut GameContext, silent: bool) {
        self.drive().clone().with(ctx, |d, ctx| {
            let snapshot = d.snapshot(ctx);
            let p = profile_mut_of(ctx);
            p.store_truck_condition(&d.trip.truck);
            p.active_trip = Some(snapshot);
        });
        ctx.save_profile();
        if !silent {
            ctx.audio.play("ui/notify");
            let name = self.stop().spoken_name();
            ctx.say(&format!(
                "Saved at {name}. Your drive will resume from this rest stop."
            ));
        }
    }
}
