//! Read-only browser for achievements earned across this installation.

use std::collections::HashSet;

use ff_core::achievements::{entry_text, ACHIEVEMENTS};

use crate::app::GameContext;
use crate::impl_state_for_menu;
use crate::states::base::{Menu, MenuCore, MenuItem};

pub struct AccountAchievementsState {
    menu: MenuCore<Self>,
}

impl AccountAchievementsState {
    pub fn new() -> Self {
        Self {
            menu: MenuCore::new("Account achievements").with_intro_help(
                "These achievements are earned across every career on this installation. \
                 Use up and down arrows to review earned and locked achievements in \
                 catalog order. Enter repeats an entry. Escape goes back to Online.",
            ),
        }
    }
}

impl Default for AccountAchievementsState {
    fn default() -> Self {
        Self::new()
    }
}

impl Menu for AccountAchievementsState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let earned = ctx.account_achievements.ids().len();
        ctx.say(&format!(
            "Account achievements. {earned} of {} earned across every career on this installation. {}",
            ACHIEVEMENTS.len(),
            self.current_text(ctx)
        ));
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let earned: HashSet<String> = ctx.account_achievements.ids().into_iter().collect();
        let mut items = Vec::with_capacity(ACHIEVEMENTS.len() + 1);
        for achievement in ACHIEVEMENTS.iter() {
            let unlocked = earned.contains(achievement.id);
            let (name, description) = entry_text(achievement, unlocked);
            let (label, help) = if unlocked {
                (format!("Earned: {name} - {description}"), description)
            } else if achievement.hidden {
                (format!("Locked: {name}"), description)
            } else {
                (format!("Locked: {name}"), "Keep playing to unlock it.")
            };
            let spoken = label.clone();
            items.push(MenuItem::new(label, move |_s: &mut Self, ctx| ctx.say(&spoken)).help(help));
        }
        items.push(MenuItem::new("Back to Online", |s: &mut Self, ctx| {
            s.go_back(ctx)
        }));
        items
    }
}

impl_state_for_menu!(AccountAchievementsState);
