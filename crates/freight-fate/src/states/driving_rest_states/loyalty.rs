//! Loyalty program reward redemption menu (`LoyaltyRewardsState`).

use ff_core::models::loyalty::reward_cost_text;
use ff_core::sim::trip_models::RoadStop;

use crate::app::GameContext;
use crate::impl_state_for_menu;
use crate::states::base::{Menu, MenuCore, MenuItem};
use crate::states::driving_core::{profile_mut_of, profile_of};
use crate::states::driving_menu_states::DriveRef;

const LOYALTY_INTRO_HELP: &str = "Enter selects, Escape goes back.";

pub struct LoyaltyRewardsState {
    menu: MenuCore<Self>,
    #[allow(dead_code)]
    driving: DriveRef,
    pub stop: RoadStop,
}

impl LoyaltyRewardsState {
    pub fn new(driving: DriveRef, stop: RoadStop) -> Self {
        LoyaltyRewardsState {
            menu: MenuCore::new("Loyalty rewards").with_intro_help(LOYALTY_INTRO_HELP),
            driving,
            stop,
        }
    }

    fn use_shower_credit(&mut self, ctx: &mut GameContext) {
        if profile_mut_of(ctx).loyalty.use_shower_credit() {
            ctx.audio.play("ui/notify");
            ctx.say("Shower credit used. The shower is free.");
            self.refresh(ctx, true);
        } else {
            ctx.audio.play("ui/error");
            ctx.say("No shower credits available.");
        }
    }

    fn redeem(&mut self, ctx: &mut GameContext, reward: &str, label: &str, failure: &str) {
        let result = profile_mut_of(ctx).loyalty.redeem_reward(reward);
        if result.success {
            ctx.audio.play("ui/notify");
            ctx.say(&format!(
                "{label} redeemed. {} points spent, {} points remaining.",
                result.points_spent.unwrap_or(0),
                ff_core::pyfmt::fmt_f(result.points_remaining, 0)
            ));
            self.refresh(ctx, true);
        } else {
            ctx.audio.play("ui/error");
            ctx.say(failure);
        }
    }
}

impl Menu for LoyaltyRewardsState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let loyalty = &profile_of(ctx).loyalty;
        let shower_credits = loyalty.shower_credits;
        let can_shower = loyalty.can_redeem("shower");
        let can_parking = loyalty.can_redeem("parking");
        let can_food = loyalty.can_redeem("food");
        let can_laundry = loyalty.can_redeem("laundry");
        let mut items: Vec<MenuItem<Self>> = Vec::new();

        // Shower credits option
        if shower_credits > 0 {
            items.push(
                MenuItem::new(
                    format!("Use shower credit ({shower_credits} available)"),
                    |s: &mut Self, ctx| s.use_shower_credit(ctx),
                )
                .help("A shower credit from fueling 50 gallons or more."),
            );
        }

        // Point redemption options
        if can_shower {
            items.push(
                MenuItem::new(
                    format!("Redeem {}", reward_cost_text("shower")),
                    |s: &mut Self, ctx| {
                        s.redeem(ctx, "shower", "Shower", "Not enough points for a shower.")
                    },
                )
                .help("Loyalty points for a free shower."),
            );
        }
        if can_parking {
            items.push(
                MenuItem::new(
                    format!("Redeem {}", reward_cost_text("parking")),
                    |s: &mut Self, ctx| {
                        s.redeem(
                            ctx,
                            "parking",
                            "Parking discount",
                            "Not enough points for a parking discount.",
                        )
                    },
                )
                .help("Loyalty points for a parking discount."),
            );
        }
        if can_food {
            items.push(
                MenuItem::new(
                    format!("Redeem {}", reward_cost_text("food")),
                    |s: &mut Self, ctx| {
                        s.redeem(
                            ctx,
                            "food",
                            "Food discount",
                            "Not enough points for a food discount.",
                        )
                    },
                )
                .help("Loyalty points for a food discount."),
            );
        }
        if can_laundry {
            items.push(
                MenuItem::new(
                    format!("Redeem {}", reward_cost_text("laundry")),
                    |s: &mut Self, ctx| {
                        s.redeem(
                            ctx,
                            "laundry",
                            "Laundry discount",
                            "Not enough points for a laundry discount.",
                        )
                    },
                )
                .help("Loyalty points for a laundry discount."),
            );
        }

        if items.is_empty() {
            items.push(
                MenuItem::inert("No rewards available, more points needed")
                    .help("Fuel at truck stops to earn loyalty points."),
            );
        }

        items.push(
            MenuItem::new("Back to truck stop", |s: &mut Self, ctx| s.go_back(ctx))
                .help("Return to the truck stop menu."),
        );
        items
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let summary = profile_of(ctx).loyalty.summary();
        let title = self.menu.title.clone();
        let name = self.stop.spoken_name();
        ctx.say(&format!("{title}. {summary} At {name}."));
    }
}

impl_state_for_menu!(LoyaltyRewardsState);
