//! Read-only category browser for achievements earned across this installation.

use std::collections::HashSet;

use ff_core::achievements::{
    achievements_in_category, categories, entry_text, Achievement, AchievementCategory,
    ACHIEVEMENTS,
};

use crate::app::GameContext;
use crate::impl_state_for_menu;
use crate::states::base::{Label, Menu, MenuCore, MenuItem};

const CONTROLS: &str = "Up and down choose a category. Enter opens it. In a category, \
Enter repeats the selected achievement. Inside a category, Escape or Back returns to account categories. \
From this category list, Escape or Back returns to Online. This \
read-only collection combines achievements earned across every career on this installation.";

pub struct AccountAchievementsState {
    menu: MenuCore<Self>,
}

impl AccountAchievementsState {
    pub fn new() -> Self {
        Self {
            menu: MenuCore::new("Account achievements").with_intro_help(CONTROLS),
        }
    }

    fn earned(ctx: &GameContext) -> HashSet<String> {
        ctx.account_achievements.ids().into_iter().collect()
    }

    fn summary_label(ctx: &GameContext) -> String {
        format!(
            "Summary: {} of {} earned across every career",
            ctx.account_achievements.ids().len(),
            ACHIEVEMENTS.len()
        )
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
        let earned = Self::earned(ctx);
        let mut items = vec![
            MenuItem::new("Controls and account scope", |_s: &mut Self, ctx| {
                ctx.say(CONTROLS)
            })
            .help(CONTROLS),
            MenuItem::new(
                Label::dynamic(|_s: &Self, ctx| Self::summary_label(ctx)),
                |_s: &mut Self, ctx| ctx.say(&Self::summary_label(ctx)),
            )
            .help("Hear the account-wide earned achievement count."),
        ];
        for category in categories() {
            let achievements = achievements_in_category(category.id);
            let done = achievements
                .iter()
                .filter(|achievement| earned.contains(achievement.id))
                .count();
            let category: &'static AchievementCategory = category;
            items.push(
                MenuItem::new(
                    format!("{}. {done} of {}", category.title, achievements.len()),
                    move |_s: &mut Self, ctx| {
                        ctx.push_state(AccountAchievementCategoryState::new(
                            category,
                            achievements.clone(),
                        ))
                    },
                )
                .help(category.description),
            );
        }
        items.push(MenuItem::new("Back to Online", |s: &mut Self, ctx| {
            s.go_back(ctx)
        }));
        items
    }
}

impl_state_for_menu!(AccountAchievementsState);

/// One category's account-wide achievements in canonical catalog order.
pub struct AccountAchievementCategoryState {
    menu: MenuCore<Self>,
    pub category: &'static AchievementCategory,
    pub achievements: Vec<&'static Achievement>,
}

impl AccountAchievementCategoryState {
    pub fn new(
        category: &'static AchievementCategory,
        achievements: Vec<&'static Achievement>,
    ) -> Self {
        Self {
            menu: MenuCore::new(category.title).with_intro_help(
                "Use up and down to review this category. Enter repeats the selected \
                 achievement. Escape or Back returns to the account categories.",
            ),
            category,
            achievements,
        }
    }

    fn earned(ctx: &GameContext) -> HashSet<String> {
        ctx.account_achievements.ids().into_iter().collect()
    }
}

impl Menu for AccountAchievementCategoryState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let earned = Self::earned(ctx);
        let done = self
            .achievements
            .iter()
            .filter(|achievement| earned.contains(achievement.id))
            .count();
        ctx.say(&format!(
            "Account achievements, {}. {done} of {} earned. {}",
            self.category.title,
            self.achievements.len(),
            self.current_text(ctx)
        ));
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let earned = Self::earned(ctx);
        let mut items = Vec::with_capacity(self.achievements.len() + 1);
        for achievement in &self.achievements {
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
        items.push(MenuItem::new(
            "Back to account categories",
            |s: &mut Self, ctx| s.go_back(ctx),
        ));
        items
    }
}

impl_state_for_menu!(AccountAchievementCategoryState);
