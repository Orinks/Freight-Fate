//! Career stats screen: the terminal's driver record as a reviewable menu
//! (port of `freight_fate/states/career_stats.py`).

use ff_core::models::career::xp_to_next_level;
use ff_core::models::carrier_fleet::equipment_status_lines;
use ff_core::models::credentials::{credential, CredentialTier, CREDENTIALS};
use ff_core::models::enforcement;
use ff_core::models::profile::Profile;
use ff_core::models::solvency::debt_line;
use ff_core::pyfmt::{fmt_f, fmt_grouped};

use crate::app::GameContext;
use crate::impl_state_for_menu;
use crate::states::base::{Menu, MenuCore, MenuItem};

/// Fresh hours of service and zero fatigue: sleeping gains nothing but time.
pub fn fully_rested(profile: &Profile) -> bool {
    profile.hos.driving_min <= 0.0 && profile.hos.duty_min <= 0.0 && profile.fatigue <= 0.0
}

/// Career stats as a list of lines, matching the driving status screens.
pub struct CareerStatsState {
    menu: MenuCore<Self>,
}

impl CareerStatsState {
    pub fn new() -> Self {
        Self {
            menu: MenuCore::new("Career stats").with_intro_help(
                "Up and down review the lines. Enter repeats a line. Escape returns to the \
                 terminal.",
            ),
        }
    }

    /// The spoken lines, in order (`_lines`).
    pub fn stat_lines(ctx: &GameContext) -> Vec<String> {
        let Some(p) = ctx.profile.as_ref() else {
            return Vec::new();
        };
        let s = &ctx.settings;
        let career = &p.career;
        let pct = if career.deliveries != 0 {
            100.0 * career.on_time_deliveries as f64 / career.deliveries as f64
        } else {
            100.0
        };
        let rest = if fully_rested(p) {
            "fully rested".to_string()
        } else {
            format!("fatigue {} percent", fmt_f(p.fatigue, 0))
        };
        let hours_now = p.game_hours;
        // Earned credentials were only ever spoken once, at the level-up
        // that granted them; these lines are the reviewable record (owner
        // got stuck declining a reefer load he was already cleared to
        // haul). One line per ladder tier, in tier order, plus what is
        // still waiting on a background check.
        let held = career.endorsements();
        let tier_line = |tier: CredentialTier, noun: &str, empty: &str| {
            let mut labels: Vec<&str> = CREDENTIALS
                .iter()
                .filter(|c| c.tier == tier && held.contains(c.key))
                .map(|c| c.label)
                .collect();
            labels.sort_unstable();
            if labels.is_empty() {
                format!("{noun}: {empty}")
            } else {
                format!("{noun}: {}", labels.join(", "))
            }
        };
        let certificates = tier_line(CredentialTier::Certificate, "Certificates", "none yet");
        let endorsements = if held.contains("tank") && held.contains("hazmat") {
            let line = tier_line(CredentialTier::Endorsement, "Endorsements", "none yet");
            format!("{line}, the X combination")
        } else {
            tier_line(CredentialTier::Endorsement, "Endorsements", "none yet")
        };
        let mut specialist: Vec<&str> = CREDENTIALS
            .iter()
            .filter(|c| {
                held.contains(c.key)
                    && matches!(
                        c.tier,
                        CredentialTier::Specialist | CredentialTier::Training
                    )
            })
            .map(|c| c.label)
            .collect();
        specialist.sort_unstable();
        let mut pending: Vec<String> = career
            .pending_credentials
            .iter()
            .filter_map(|p| {
                let cred = credential(&p.key)?;
                let days = ((p.ready_at_h - hours_now) / 24.0).ceil().max(0.0);
                Some(format!(
                    "{} background check in progress, about {} days left",
                    cred.gate_label,
                    fmt_f(days, 0)
                ))
            })
            .collect();
        pending.sort();
        // Money was reviewable nowhere on this screen, which left a player
        // asking "how much do I owe" with no way to find out short of opening
        // a fuel menu. Balance is always here now; what is owed joins it only
        // when it is real. The slower career rate rides the trust line, which
        // is on this screen already.
        let owed = debt_line(p);
        let level = career.level();
        let next = match xp_to_next_level(career.xp) {
            Some(xp_owed) => format!(", {} to level {}", fmt_grouped(xp_owed, 0), level + 1),
            None => ", top level".to_string(),
        };
        let mut lines = vec![
            format!(
                "Level {level} driver, {} experience{next}",
                fmt_f(career.xp, 0)
            ),
            format!("Reputation: {} out of 100", fmt_f(career.reputation, 0)),
            enforcement::dispatch_trust_line(p),
            enforcement::career_menu_status(p),
            enforcement::standing_text(p),
        ];
        // What the driver is actually in, and what stands between them and
        // the next tier. The hold was spoken at the dispatch hand-over and at
        // the level-up that brought no truck, and nowhere a player could go
        // and ASK -- which is what this screen is for (Brandon, 2026-08-22).
        lines.extend(equipment_status_lines(p));
        lines.push(format!("Balance: {} dollars", fmt_grouped(p.money, 0)));
        if !owed.is_empty() {
            lines.push(owed);
        }
        lines.push(certificates);
        lines.push(endorsements);
        if !specialist.is_empty() {
            lines.push(format!("Training and cards: {}", specialist.join(", ")));
        }
        lines.extend(pending);
        lines.push(format!(
            "Deliveries: {}, {} percent on time",
            career.deliveries,
            fmt_f(pct, 0)
        ));
        lines.push(format!(
            "Lifetime {}: {}",
            s.distance_unit_text(true),
            s.distance_value(career.total_miles, 0, true)
        ));
        lines.push(format!(
            "Lifetime earnings: {} dollars",
            fmt_grouped(career.total_earnings, 0)
        ));
        lines.push(format!("Rest: {rest}"));
        lines.push(format!(
            "Hours: {}",
            p.hos.summary(&ctx.settings.hos_mode).trim_end_matches('.')
        ));
        lines
    }
}

impl Default for CareerStatsState {
    fn default() -> Self {
        Self::new()
    }
}

impl Menu for CareerStatsState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let mut items: Vec<MenuItem<Self>> = Self::stat_lines(ctx)
            .into_iter()
            .map(|line| {
                let spoken = line.clone();
                MenuItem::new(line, move |_s: &mut Self, ctx| ctx.say(&spoken))
                    .help("Repeat this status line.")
            })
            .collect();
        items.push(
            MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx))
                .help("Back to the terminal menu."),
        );
        items
    }
}

impl_state_for_menu!(CareerStatsState);
