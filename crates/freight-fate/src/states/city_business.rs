//! Business-status, truck, upgrade, and trailer program menus (port of
//! `freight_fate/states/city_business.py`).

use ff_core::models::business::{
    authority_activation_eligibility, authority_readiness_eligibility, business_path_label,
    business_status_summary, has_authority_readiness, has_weigh_station_transponder,
    is_owner_operator, next_business_unlock, owner_operator_eligibility, status_label,
    weigh_station_transponder_eligibility, AUTHORITY_ACTIVATION_COST, AUTHORITY_READY_RESERVE,
    INDEPENDENT_AUTHORITY, LEASED_OWNER_OPERATOR, OWNER_OPERATOR_BUY_IN,
    WEIGH_STATION_TRANSPONDER_SIGNUP_FEE,
};
use ff_core::models::career::{
    endorsement_course_cost, endorsement_label_spoken, ENDORSEMENT_LEVELS,
};
use ff_core::models::trailers::{TrailerType, DEFAULT_TRAILER_PROGRAMS, TRAILER_CATALOG};
use ff_core::models::trucks::{TruckModel, Upgrade, TRUCK_CATALOG, UPGRADE_CATALOG};
use ff_core::pyfmt::{fmt_f, fmt_grouped};

use crate::app::GameContext;
use crate::impl_state_for_menu;
use crate::states::base::{Label, Menu, MenuCore, MenuItem};
use crate::states::city::{profile, profile_mut, py_capitalize};

// -- Business status -----------------------------------------------------------------------

pub struct BusinessStatusState {
    menu: MenuCore<Self>,
}

impl Default for BusinessStatusState {
    fn default() -> Self {
        Self::new()
    }
}

impl BusinessStatusState {
    pub fn new() -> Self {
        BusinessStatusState {
            menu: MenuCore::new("Business status").with_intro_help(
                "Use up and down arrows to review the business path. Enter repeats \
                 status, or buys into owner-operator status when qualified. Escape \
                 returns to the terminal.",
            ),
        }
    }

    fn summary_label(ctx: &GameContext) -> String {
        format!(
            "Current status: {}",
            status_label(&profile(ctx).business_status)
        )
    }

    fn summary(&mut self, ctx: &mut GameContext) {
        let text = business_status_summary(profile(ctx));
        ctx.say(&text);
    }

    fn rank_status(&mut self, ctx: &mut GameContext) {
        let text = business_path_label(profile(ctx));
        ctx.say(&text);
    }

    fn next_unlock(&mut self, ctx: &mut GameContext) {
        let text = next_business_unlock(profile(ctx));
        ctx.say(&text);
    }

    /// What the transponder subscription is still waiting on.
    ///
    /// Its own reader rather than `next_unlock`: that speaks the next
    /// BUSINESS unlock, which is a different question from why this one
    /// item is greyed, and answering the wrong question is how a locked
    /// row teaches a player nothing.
    fn locked_transponder(&mut self, ctx: &mut GameContext, reasons: &[String]) {
        let joined = reasons.join(" ");
        let body = if joined.is_empty() {
            "Not available yet.".to_string()
        } else {
            joined
        };
        ctx.say(&format!("Weigh station transponder. {body}"));
    }

    fn become_owner_operator(&mut self, ctx: &mut GameContext) {
        let (ok, reasons) = owner_operator_eligibility(profile(ctx));
        if !ok {
            ctx.audio.play("ui/error");
            ctx.say(&format!("Owner-operator path locked. {}", reasons.join(" ")));
            self.refresh(ctx, true);
            return;
        }
        let money = {
            let p = profile_mut(ctx);
            p.money -= OWNER_OPERATOR_BUY_IN;
            let assigned = p.active_truck_key();
            p.business_status = LEASED_OWNER_OPERATOR.to_string();
            if !p.owned_trucks.contains(&assigned) {
                p.owned_trucks.push(assigned.clone());
            }
            if p.trailer_programs.is_empty() {
                p.trailer_programs = DEFAULT_TRAILER_PROGRAMS
                    .iter()
                    .map(|s| s.to_string())
                    .collect();
            }
            p.truck = assigned;
            p.dispatch_board_cache = None;
            p.money
        };
        ctx.save_profile();
        ctx.audio.play("ui/cash");
        ctx.say(&format!(
            "Leased-on owner-operator status unlocked. You paid \
             {} dollars toward your first tractor \
             and kept {} dollars working capital. Future loads \
             pay higher gross revenue, and your business pays fuel, repairs, \
             maintenance reserve, insurance, trailer program, truck payment \
             reserve, and settlement fees.",
            fmt_grouped(OWNER_OPERATOR_BUY_IN, 0),
            fmt_grouped(money, 0)
        ));
        ctx.award_achievement("owner_operator_buyin");
        self.refresh(ctx, true);
    }

    fn set_authority_readiness(&mut self, ctx: &mut GameContext) {
        let (ok, reasons) = authority_readiness_eligibility(profile(ctx));
        if !ok {
            ctx.audio.play("ui/error");
            ctx.say(&format!("Authority prep locked. {}", reasons.join(" ")));
            self.refresh(ctx, true);
            return;
        }
        let money = {
            let p = profile_mut(ctx);
            p.money -= AUTHORITY_READY_RESERVE;
            p.authority_readiness = true;
            p.dispatch_board_cache = None;
            p.money
        };
        ctx.save_profile();
        ctx.audio.play("ui/cash");
        ctx.say(&format!(
            "Authority prep reserve set aside: \
             {} dollars. You have \
             {} dollars left. Own authority can unlock after \
             the final delivery, reputation, trailer program, and cash gates. \
             For now you remain leased on.",
            fmt_grouped(AUTHORITY_READY_RESERVE, 0),
            fmt_grouped(money, 0)
        ));
        self.refresh(ctx, true);
    }

    fn subscribe_transponder(&mut self, ctx: &mut GameContext) {
        let (ok, reasons) = weigh_station_transponder_eligibility(profile(ctx));
        if !ok {
            ctx.audio.play("ui/error");
            ctx.say(&format!(
                "Transponder subscription locked. {}",
                reasons.join(" ")
            ));
            self.refresh(ctx, true);
            return;
        }
        let money = {
            let p = profile_mut(ctx);
            p.money -= WEIGH_STATION_TRANSPONDER_SIGNUP_FEE;
            p.weigh_station_transponder = true;
            p.money
        };
        ctx.save_profile();
        ctx.audio.play("ui/cash");
        ctx.say(&format!(
            "Weigh station transponder subscription active. You paid \
             {} dollars. You have \
             {} dollars left. A clean truck now gets a \
             weigh-in-motion check at most open scales instead of a mandatory \
             pull-in, with a small per-mile settlement reserve while it is active.",
            fmt_grouped(WEIGH_STATION_TRANSPONDER_SIGNUP_FEE, 0),
            fmt_grouped(money, 0)
        ));
        self.refresh(ctx, true);
    }

    fn activate_authority(&mut self, ctx: &mut GameContext) {
        let (ok, reasons) = authority_activation_eligibility(profile(ctx));
        if !ok {
            ctx.audio.play("ui/error");
            ctx.say(&format!("Own authority locked. {}", reasons.join(" ")));
            self.refresh(ctx, true);
            return;
        }
        let money = {
            let p = profile_mut(ctx);
            p.money -= AUTHORITY_ACTIVATION_COST;
            p.business_status = INDEPENDENT_AUTHORITY.to_string();
            p.dispatch_board_cache = None;
            p.money
        };
        ctx.save_profile();
        ctx.audio.play("ui/cash");
        ctx.say(&format!(
            "Own authority active. Startup cost \
             {} dollars. You have \
             {} dollars left. Dispatch now lists direct freight. \
             Settlement includes insurance, compliance, trailer, truck, and \
             factoring costs.",
            fmt_grouped(AUTHORITY_ACTIVATION_COST, 0),
            fmt_grouped(money, 0)
        ));
        ctx.award_achievement("authority_active");
        self.refresh(ctx, true);
    }
}

impl Menu for BusinessStatusState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let summary = business_status_summary(profile(ctx));
        let current = self.current_text(ctx);
        ctx.say(&format!("Business status. {summary} {current}"));
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let p = profile(ctx);
        let mut items = vec![
            MenuItem::new(
                Label::dynamic(|_s: &Self, ctx| Self::summary_label(ctx)),
                |s: &mut Self, ctx| s.summary(ctx),
            )
            .help("Hear the current business status and tradeoffs."),
            MenuItem::new("Carrier and rank", |s: &mut Self, ctx| s.rank_status(ctx))
                .help("Hear your starter carrier, rank, and career stage."),
            MenuItem::new("Next business unlock", |s: &mut Self, ctx| {
                s.next_unlock(ctx)
            })
            .help("Hear the next career or business unlock."),
        ];
        if !is_owner_operator(&p.business_status) {
            let (ok, _reasons) = owner_operator_eligibility(p);
            if ok {
                items.push(
                    MenuItem::new(
                        format!(
                            "Buy into leased-on owner-operator: {} dollars",
                            fmt_grouped(OWNER_OPERATOR_BUY_IN, 0)
                        ),
                        |s: &mut Self, ctx| s.become_owner_operator(ctx),
                    )
                    .help(
                        "Buy your first tractor position and start running as \
                         a leased-on owner-operator. Higher revenue, but your \
                         business pays operating costs.",
                    ),
                );
            } else {
                items.push(
                    MenuItem::new("Owner-operator path locked", |s: &mut Self, ctx| {
                        s.summary(ctx)
                    })
                    .help("Hear the remaining requirements."),
                );
            }
        } else {
            if p.business_status == INDEPENDENT_AUTHORITY {
                items.push(
                    MenuItem::new("Own authority active", |s: &mut Self, ctx| s.summary(ctx))
                        .help(
                            "Direct freight is available. Settlement includes \
                             insurance, compliance, and factoring costs.",
                        ),
                );
            } else if has_authority_readiness(p) {
                items.push(
                    MenuItem::new("Authority prep reserve: set", |s: &mut Self, ctx| {
                        s.summary(ctx)
                    })
                    .help(
                        "This career has set aside the prep reserve for \
                         own-authority startup.",
                    ),
                );
                let (ok, _reasons) = authority_activation_eligibility(p);
                if ok {
                    items.push(
                        MenuItem::new(
                            format!(
                                "Activate own authority: {} dollars",
                                fmt_grouped(AUTHORITY_ACTIVATION_COST, 0)
                            ),
                            |s: &mut Self, ctx| s.activate_authority(ctx),
                        )
                        .help(
                            "Start direct freight with higher gross revenue \
                             and more business overhead.",
                        ),
                    );
                } else {
                    items.push(
                        MenuItem::new("Own authority locked", |s: &mut Self, ctx| {
                            s.next_unlock(ctx)
                        })
                        .help("Hear the remaining own-authority requirements."),
                    );
                }
            } else {
                let (ok, _reasons) = authority_readiness_eligibility(p);
                if ok {
                    items.push(
                        MenuItem::new(
                            format!(
                                "Commit {} dollars to authority prep",
                                fmt_grouped(AUTHORITY_READY_RESERVE, 0)
                            ),
                            |s: &mut Self, ctx| s.set_authority_readiness(ctx),
                        )
                        .help("Set aside money for the later own-authority activation gate."),
                    );
                } else {
                    items.push(
                        MenuItem::new("Authority prep locked", |s: &mut Self, ctx| {
                            s.next_unlock(ctx)
                        })
                        .help("Hear the remaining authority prep requirements."),
                    );
                }
            }
            if has_weigh_station_transponder(p) {
                items.push(
                    MenuItem::new(
                        "Weigh station transponder: subscribed",
                        |s: &mut Self, ctx| s.summary(ctx),
                    )
                    .help(
                        "Open scales run a weigh-in-motion check on this \
                         truck instead of demanding every truck pull in.",
                    ),
                );
            } else {
                let (ok, reasons) = weigh_station_transponder_eligibility(p);
                if ok {
                    items.push(
                        MenuItem::new(
                            format!(
                                "Subscribe to weigh station transponder: \
                                 {} dollars",
                                fmt_grouped(WEIGH_STATION_TRANSPONDER_SIGNUP_FEE, 0)
                            ),
                            |s: &mut Self, ctx| s.subscribe_transponder(ctx),
                        )
                        .help(
                            "A clean truck can be waved past most open scales \
                             instead of pulling in. Adds a small per-mile \
                             settlement reserve once active.",
                        ),
                    );
                } else {
                    // Locked, but SHOWN -- the same shape as the authority
                    // items above. Without this the subscription appeared
                    // only once the driver could already afford it, so the
                    // owner-operator with most to gain from knowing the
                    // transponder exists was the one told nothing about it,
                    // and the eligibility reasons were computed here and
                    // thrown away (owner, 2026-08-21).
                    let locked = reasons.clone();
                    items.push(
                        MenuItem::new(
                            "Weigh station transponder locked",
                            move |s: &mut Self, ctx: &mut GameContext| {
                                s.locked_transponder(ctx, &locked)
                            },
                        )
                        .help("Hear what the weigh station transponder still needs."),
                    );
                }
            }
        }
        items.push(MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)));
        items
    }
}

impl_state_for_menu!(BusinessStatusState);

// -- Upgrades ---------------------------------------------------------------------------------

pub struct UpgradeShopState {
    menu: MenuCore<Self>,
}

impl Default for UpgradeShopState {
    fn default() -> Self {
        Self::new()
    }
}

impl UpgradeShopState {
    pub fn new() -> Self {
        UpgradeShopState {
            menu: MenuCore::new("Upgrades").with_intro_help(
                "Each entry speaks the fleet upgrade, its price, and what you \
                 already own. Upgrades apply to every tractor in your fleet. \
                 Enter buys the next tier. Press F1 on an upgrade to hear \
                 what it does. Escape returns to the garage.",
            ),
        }
    }

    fn locked(&mut self, ctx: &mut GameContext) {
        ctx.audio.play("ui/error");
        ctx.say(
            "Upgrades are locked. Company drivers use carrier-assigned, \
             fleet-maintained tractors. Ownership upgrades unlock after the \
             leased-on owner-operator buy-in.",
        );
    }

    fn label(ctx: &GameContext, upgrade: &Upgrade) -> String {
        let owned = profile(ctx).upgrades.get(upgrade.key).copied().unwrap_or(0);
        let max_tier = upgrade.max_tier();
        if owned >= max_tier {
            let tiers = if max_tier > 1 {
                format!(", tier {owned} of {max_tier}")
            } else {
                String::new()
            };
            return format!("{}: owned{tiers}", upgrade.label);
        }
        let price = upgrade.prices[owned.max(0) as usize];
        if max_tier > 1 {
            let owned_part = if owned > 0 {
                format!(", tier {owned} owned")
            } else {
                String::new()
            };
            return format!(
                "{}, tier {} of {max_tier}: \
                 {} dollars{owned_part}",
                upgrade.label,
                owned + 1,
                fmt_grouped(price, 0)
            );
        }
        format!("{}: {} dollars", upgrade.label, fmt_grouped(price, 0))
    }

    fn buy(&mut self, ctx: &mut GameContext, upgrade: &'static Upgrade) {
        if !is_owner_operator(&profile(ctx).business_status) {
            ctx.audio.play("ui/error");
            ctx.say(
                "Upgrades unlock after the leased-on owner-operator buy-in. \
                 The company tractor stays carrier-maintained for now.",
            );
            return;
        }
        let owned = profile(ctx)
            .upgrades
            .get(upgrade.key)
            .copied()
            .unwrap_or(0);
        if owned >= upgrade.max_tier() {
            ctx.say(&format!("{} is already fully installed.", upgrade.label));
            return;
        }
        let price = upgrade.prices[owned.max(0) as usize];
        if profile(ctx).money < price {
            ctx.audio.play("ui/error");
            ctx.say(&format!(
                "Not enough money. {} costs {} dollars \
                 and you have {}.",
                upgrade.label,
                fmt_grouped(price, 0),
                fmt_grouped(profile(ctx).money, 0)
            ));
            return;
        }
        let (money, all_owned) = {
            let p = profile_mut(ctx);
            p.money -= price;
            p.upgrades.insert(upgrade.key.to_string(), owned + 1);
            let all_owned = UPGRADE_CATALOG
                .iter()
                .all(|item| p.upgrades.get(item.key).copied().unwrap_or(0) >= item.max_tier());
            (p.money, all_owned)
        };
        ctx.save_profile();
        ctx.audio.play("ui/cash");
        let tier_part = if upgrade.max_tier() > 1 {
            format!(" tier {}", owned + 1)
        } else {
            String::new()
        };
        ctx.say(&format!(
            "{}{tier_part} installed across your fleet for \
             {} dollars. \
             You have {} dollars left.",
            upgrade.label,
            fmt_grouped(price, 0),
            fmt_grouped(money, 0)
        ));
        ctx.award_achievement("first_upgrade");
        if all_owned {
            ctx.award_achievement("all_upgrades");
        }
        self.refresh(ctx, true);
    }
}

impl Menu for UpgradeShopState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let (money, owner) = {
            let p = profile(ctx);
            (p.money, is_owner_operator(&p.business_status))
        };
        let current = self.current_text(ctx);
        if owner {
            ctx.say(&format!(
                "Fleet upgrades. They apply to every tractor you own. \
                 You have {} dollars. {current}",
                fmt_grouped(money, 0)
            ));
        } else {
            ctx.say(&format!(
                "Upgrades. You have {} dollars. {current}",
                fmt_grouped(money, 0)
            ));
        }
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        if !is_owner_operator(&profile(ctx).business_status) {
            return vec![
                MenuItem::new(
                    "Upgrades locked: carrier-assigned tractor",
                    |s: &mut Self, ctx| s.locked(ctx),
                )
                .help(
                    "Company drivers use fleet-maintained equipment. \
                     Performance upgrades unlock after the leased-on \
                     owner-operator buy-in.",
                ),
                MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)),
            ];
        }
        let mut items: Vec<MenuItem<Self>> = UPGRADE_CATALOG
            .iter()
            .map(|u| {
                MenuItem::new(
                    Label::dynamic(move |_s: &Self, ctx| Self::label(ctx, u)),
                    move |s: &mut Self, ctx| s.buy(ctx, u),
                )
                .help(u.description)
            })
            .collect();
        items.push(MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)));
        items
    }
}

impl_state_for_menu!(UpgradeShopState);

// -- Trucks ----------------------------------------------------------------------------------

pub struct TruckShopState {
    menu: MenuCore<Self>,
    /// The dealer-name prefix is only true when the player actually
    /// opened this from the terminal's "Truck dealer" row -- reaching it
    /// from the garage's "Trucks" row would name a location the player
    /// never went to, which is a contradicted navigation cue for a blind
    /// or low-vision player.
    pub at_dealer: bool,
}

impl TruckShopState {
    pub fn new(at_dealer: bool) -> Self {
        TruckShopState {
            menu: MenuCore::new("Trucks").with_intro_help(
                "Owner-operators can buy tractors or switch among tractors \
                 they own. Your fleet upgrades apply to whichever tractor you \
                 drive. Company drivers use carrier-assigned equipment.",
            ),
            at_dealer,
        }
    }

    fn locked(&mut self, ctx: &mut GameContext) {
        ctx.audio.play("ui/error");
        ctx.say(
            "Truck ownership is locked. Company drivers run a carrier-assigned \
             tractor. Buying and switching owned tractors unlocks after the \
             leased-on owner-operator buy-in.",
        );
    }

    fn label(ctx: &GameContext, model: &TruckModel) -> String {
        let p = profile(ctx);
        let name = py_capitalize(model.label);
        let specs = &model.specs;
        let traits = format!(
            "{} thousand newton meters torque, \
             {} gallon tank",
            fmt_f(specs.max_torque_nm / 1000.0, 1),
            fmt_f(specs.fuel_tank_gal, 0)
        );
        if model.key == p.truck {
            return format!("{name}: currently driving, {traits}");
        }
        if p.visible_owned_trucks().iter().any(|k| k == model.key) {
            return format!("{name}: owned, {traits}, switch to it");
        }
        format!(
            "{name}: {traits}, buy for {} dollars",
            fmt_grouped(model.price, 0)
        )
    }

    fn pick(&mut self, ctx: &mut GameContext, model: &'static TruckModel) {
        if model.key == profile(ctx).truck {
            ctx.say(&format!("You are already driving the {}.", model.label));
            return;
        }
        if !is_owner_operator(&profile(ctx).business_status) {
            ctx.audio.play("ui/error");
            ctx.say(
                "Truck purchases unlock after the leased-on owner-operator buy-in. \
                 For now, the carrier assigns your company tractor.",
            );
            return;
        }
        if !profile(ctx).owned_trucks.iter().any(|k| k == model.key) {
            if profile(ctx).money < model.price {
                ctx.audio.play("ui/error");
                ctx.say(&format!(
                    "Not enough money. The {} costs \
                     {} dollars and you have {}.",
                    model.label,
                    fmt_grouped(model.price, 0),
                    fmt_grouped(profile(ctx).money, 0)
                ));
                return;
            }
            let owned_count = {
                let p = profile_mut(ctx);
                p.money -= model.price;
                p.owned_trucks.push(model.key.to_string());
                // A truck off the dealer lot is its own rig: fresh wear, full tank.
                p.provision_truck_condition(model.key, Some(model.specs.fuel_tank_gal));
                p.owned_trucks.len()
            };
            ctx.audio.play("ui/cash");
            self.switch_to(ctx, model);
            let money = profile(ctx).money;
            ctx.say(&format!(
                "You bought the {} for {} dollars \
                 and it is now your owned tractor. \
                 You have {} dollars left.",
                model.label,
                fmt_grouped(model.price, 0),
                fmt_grouped(money, 0)
            ));
            if model.key == "heavy_hauler" {
                ctx.award_achievement("heavy_hauler");
            }
            if owned_count >= 3 {
                ctx.award_achievement("three_trucks");
            }
            return;
        }
        ctx.audio.play("vehicle/truck_door");
        self.switch_to(ctx, model);
        ctx.say(&format!("You are now driving the {}.", model.label));
    }

    fn switch_to(&mut self, ctx: &mut GameContext, model: &TruckModel) {
        {
            let p = profile_mut(ctx);
            p.truck = model.key.to_string();
            let fuel = p.truck_fuel_gal().min(p.truck_specs().fuel_tank_gal);
            p.set_truck_fuel_gal(fuel);
        }
        ctx.save_profile();
        self.refresh(ctx, true);
    }
}

impl Menu for TruckShopState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let mut dealer = String::new();
        if self.at_dealer {
            if let Ok(service) = ctx
                .world
                .city_service(&profile(ctx).current_city, "truck_dealer")
            {
                if !service.fallback {
                    dealer = format!("Inside {}. ", service.name);
                }
            }
        }
        let money = profile(ctx).money;
        let current = self.current_text(ctx);
        ctx.say(&format!(
            "{dealer}Trucks. You have {} dollars. {current}",
            fmt_grouped(money, 0)
        ));
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        if !is_owner_operator(&profile(ctx).business_status) {
            return vec![
                MenuItem::new(
                    "Truck ownership locked: carrier-assigned tractor",
                    |s: &mut Self, ctx| s.locked(ctx),
                )
                .help(
                    "Company drivers do not buy tractors here. The carrier \
                     assigns and maintains the company tractor until the \
                     leased-on owner-operator buy-in.",
                ),
                MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)),
            ];
        }
        let mut items: Vec<MenuItem<Self>> = TRUCK_CATALOG
            .values()
            .map(|m| {
                MenuItem::new(
                    Label::dynamic(move |_s: &Self, ctx| Self::label(ctx, m)),
                    move |s: &mut Self, ctx| s.pick(ctx, m),
                )
                .help(m.description)
            })
            .collect();
        items.push(MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)));
        items
    }
}

impl_state_for_menu!(TruckShopState);

// -- Trailers --------------------------------------------------------------------------------

pub struct TrailerProgramState {
    menu: MenuCore<Self>,
}

impl Default for TrailerProgramState {
    fn default() -> Self {
        Self::new()
    }
}

impl TrailerProgramState {
    pub fn new() -> Self {
        TrailerProgramState {
            menu: MenuCore::new("Trailers").with_intro_help(
                "Company drivers use carrier-provided trailers. Owner-operators start \
                 with the dry van trailer program and can add specialty programs. \
                 Own-authority drivers can buy trailers outright. \
                 Escape returns to the garage.",
            ),
        }
    }

    fn locked(&mut self, ctx: &mut GameContext) {
        ctx.audio.play("ui/error");
        ctx.say(
            "Trailer programs are locked. Company drivers use carrier-provided \
             trailers, so no trailer lease is needed.",
        );
    }

    fn label(ctx: &GameContext, trailer: &TrailerType) -> String {
        let p = profile(ctx);
        let owned = p.visible_owned_trailers();
        if p.business_status == INDEPENDENT_AUTHORITY {
            if owned.iter().any(|k| k == trailer.key) {
                return format!("{}: owned trailer", trailer.label);
            }
            return format!(
                "{}: buy trailer for {} dollars",
                trailer.label,
                fmt_grouped(trailer.purchase_price, 0)
            );
        }
        let programs = p.active_trailer_programs();
        if programs.iter().any(|k| k == trailer.key) {
            if DEFAULT_TRAILER_PROGRAMS.contains(&trailer.key) {
                return format!("{}: included carrier trailer program", trailer.label);
            }
            return format!("{}: leased program active", trailer.label);
        }
        format!(
            "{}: lease program for {} dollars",
            trailer.label,
            fmt_grouped(trailer.lease_deposit, 0)
        )
    }

    fn select(&mut self, ctx: &mut GameContext, trailer: &'static TrailerType) {
        if profile(ctx).business_status == INDEPENDENT_AUTHORITY {
            self.buy_trailer(ctx, trailer);
            return;
        }
        self.lease(ctx, trailer);
    }

    fn lease(&mut self, ctx: &mut GameContext, trailer: &TrailerType) {
        if !is_owner_operator(&profile(ctx).business_status) {
            ctx.audio.play("ui/error");
            ctx.say(
                "Company drivers use carrier-provided trailers. Trailer \
                 programs unlock after the leased-on owner-operator buy-in.",
            );
            return;
        }
        if profile(ctx)
            .active_trailer_programs()
            .iter()
            .any(|k| k == trailer.key)
        {
            ctx.say(&format!(
                "{} trailer program is already active.",
                trailer.label
            ));
            return;
        }
        if profile(ctx).money < trailer.lease_deposit {
            ctx.audio.play("ui/error");
            ctx.say(&format!(
                "Not enough money. {} trailer program costs \
                 {} dollars and you have \
                 {}.",
                trailer.label,
                fmt_grouped(trailer.lease_deposit, 0),
                fmt_grouped(profile(ctx).money, 0)
            ));
            return;
        }
        let money = {
            let p = profile_mut(ctx);
            p.money -= trailer.lease_deposit;
            let mut programs = p.active_trailer_programs();
            programs.push(trailer.key.to_string());
            p.trailer_programs = programs;
            p.dispatch_board_cache = None;
            p.money
        };
        ctx.save_profile();
        ctx.audio.play("ui/cash");
        ctx.say(&format!(
            "{} trailer program active for \
             {} dollars. You have \
             {} dollars left. Matching cargo can now appear as \
             available on the dispatch board.",
            trailer.label,
            fmt_grouped(trailer.lease_deposit, 0),
            fmt_grouped(money, 0)
        ));
        self.refresh(ctx, true);
    }

    fn buy_trailer(&mut self, ctx: &mut GameContext, trailer: &TrailerType) {
        if profile(ctx).business_status != INDEPENDENT_AUTHORITY {
            ctx.audio.play("ui/error");
            ctx.say(
                "Trailer purchases unlock after own authority. Leased-on \
                 owner-operators can use trailer programs for now.",
            );
            return;
        }
        if profile(ctx)
            .visible_owned_trailers()
            .iter()
            .any(|k| k == trailer.key)
        {
            ctx.say(&format!("You already own a {} trailer.", trailer.label));
            return;
        }
        if profile(ctx).money < trailer.purchase_price {
            ctx.audio.play("ui/error");
            ctx.say(&format!(
                "Not enough money. The {} trailer costs \
                 {} dollars and you have \
                 {}.",
                trailer.label,
                fmt_grouped(trailer.purchase_price, 0),
                fmt_grouped(profile(ctx).money, 0)
            ));
            return;
        }
        let money = {
            let p = profile_mut(ctx);
            p.money -= trailer.purchase_price;
            let mut owned = p.visible_owned_trailers();
            owned.push(trailer.key.to_string());
            p.owned_trailers = owned;
            p.dispatch_board_cache = None;
            p.money
        };
        ctx.save_profile();
        ctx.audio.play("ui/cash");
        ctx.say(&format!(
            "{} trailer purchased for \
             {} dollars. You have \
             {} dollars left. Matching direct freight now uses \
             an owned-trailer reserve at settlement.",
            trailer.label,
            fmt_grouped(trailer.purchase_price, 0),
            fmt_grouped(money, 0)
        ));
        self.refresh(ctx, true);
    }
}

impl Menu for TrailerProgramState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let money = profile(ctx).money;
        let current = self.current_text(ctx);
        ctx.say(&format!(
            "Trailers. You have {} dollars. {current}",
            fmt_grouped(money, 0)
        ));
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        if !is_owner_operator(&profile(ctx).business_status) {
            return vec![
                MenuItem::new(
                    "Trailer programs locked: carrier-provided trailers",
                    |s: &mut Self, ctx| s.locked(ctx),
                )
                .help(
                    "Company drivers do not lease or buy trailers. The \
                     carrier supplies the right trailer for approved loads.",
                ),
                MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)),
            ];
        }
        let mut items: Vec<MenuItem<Self>> = TRAILER_CATALOG
            .iter()
            .map(|t| {
                MenuItem::new(
                    Label::dynamic(move |_s: &Self, ctx| Self::label(ctx, t)),
                    move |s: &mut Self, ctx| s.select(ctx, t),
                )
                .help(t.description)
            })
            .collect();
        items.push(MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)));
        items
    }
}

impl_state_for_menu!(TrailerProgramState);

// -- Endorsement courses -----------------------------------------------------------------------

pub struct EndorsementCourseState {
    menu: MenuCore<Self>,
}

impl Default for EndorsementCourseState {
    fn default() -> Self {
        Self::new()
    }
}

impl EndorsementCourseState {
    pub fn new() -> Self {
        EndorsementCourseState {
            menu: MenuCore::new("Endorsement courses").with_intro_help(
                "Each endorsement course unlocks its freight early, before the \
                 carrier would sponsor the training at the listed level. Enter books \
                 a course you can afford. Escape returns to the terminal.",
            ),
        }
    }

    fn buy(&mut self, ctx: &mut GameContext, key: &'static str) {
        let label = endorsement_label_spoken(key).unwrap_or(key);
        let cost = endorsement_course_cost(key).unwrap_or(0.0);
        if profile(ctx).career.endorsements().contains(key) {
            ctx.say(&format!("You already hold the {label} endorsement."));
            return;
        }
        if profile(ctx).money < cost {
            ctx.audio.play("ui/error");
            ctx.say(&format!(
                "The {label} course costs {} dollars and you have {}.",
                fmt_grouped(cost, 0),
                fmt_grouped(profile(ctx).money, 0)
            ));
            return;
        }
        let money = {
            let p = profile_mut(ctx);
            p.money -= cost;
            p.career.purchased_endorsements.push(key.to_string());
            p.dispatch_board_cache = None;
            p.money
        };
        ctx.save_profile();
        ctx.audio.play("ui/cash");
        ctx.say(&format!(
            "Course complete: you paid {} dollars and earned the \
             {label} endorsement. Matching freight is unlocked on the \
             dispatch board. You have {} dollars left.",
            fmt_grouped(cost, 0),
            fmt_grouped(money, 0)
        ));
        ctx.award_achievement("self_paid_course");
        self.refresh(ctx, true);
    }
}

impl Menu for EndorsementCourseState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let money = profile(ctx).money;
        let current = self.current_text(ctx);
        ctx.say(&format!(
            "Endorsement courses. Pay for training yourself to unlock \
             specialty freight early; the carrier sponsors each course for \
             free at its listed level. You have {} dollars. \
             {current}",
            fmt_grouped(money, 0)
        ));
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let career = &profile(ctx).career;
        let earned = career.endorsements();
        let mut items: Vec<MenuItem<Self>> = Vec::new();
        for (key, level) in ENDORSEMENT_LEVELS {
            let key: &'static str = key;
            let label = endorsement_label_spoken(key).unwrap_or(key);
            if earned.contains(key) {
                let how = if career.purchased_endorsements.iter().any(|k| k == key) {
                    "self-paid course"
                } else {
                    "carrier-sponsored"
                };
                items.push(
                    MenuItem::new(
                        format!("{} endorsement: earned, {how}", py_capitalize(label)),
                        move |_s: &mut Self, ctx| {
                            ctx.say(&format!("You already hold the {label} endorsement."))
                        },
                    )
                    .help("This endorsement is already on your license."),
                );
                continue;
            }
            let cost = endorsement_course_cost(key).unwrap_or(0.0);
            items.push(
                MenuItem::new(
                    format!(
                        "{} course: {} dollars \
                         (carrier-sponsored free at level {level})",
                        py_capitalize(label),
                        fmt_grouped(cost, 0)
                    ),
                    move |s: &mut Self, ctx| s.buy(ctx, key),
                )
                .help(format!(
                    "Pay for the {label} training and testing now to \
                     unlock that freight before level {level}."
                )),
            );
        }
        items.push(
            MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx))
                .help("Return to the terminal menu."),
        );
        items
    }
}

impl_state_for_menu!(EndorsementCourseState);
