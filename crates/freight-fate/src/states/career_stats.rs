//! Career stats screen: the terminal's driver record as a reviewable menu
//! (port of `freight_fate/states/career_stats.py`).

use ff_core::models::career::xp_to_next_level;
use ff_core::models::enforcement;
use ff_core::models::jobs::endorsement_label;
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
                "Use up and down arrows to review each line. Enter repeats the current \
                 line. Escape returns to the terminal.",
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
        let mut held: Vec<String> = career
            .endorsements()
            .iter()
            .map(|e| endorsement_label(Some(e)).replace(" endorsement", ""))
            .collect();
        held.sort();
        // Earned endorsements were only ever spoken once, at the level-up
        // that granted them; this line is the reviewable record (owner got
        // stuck declining a reefer load he was already cleared to haul).
        let endorsements = if held.is_empty() {
            "Endorsements: none yet".to_string()
        } else {
            format!("Endorsements: {}", held.join(", "))
        };
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
            format!("Balance: {} dollars", fmt_grouped(p.money, 0)),
        ];
        if !owed.is_empty() {
            lines.push(owed);
        }
        lines.push(endorsements);
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
