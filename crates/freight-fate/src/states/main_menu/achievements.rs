//! The achievements browser: pick a career, then a category, then read its
//! badges (the `Achievement*State` classes of `main_menu.py`).

use ff_core::achievements::{
    achievements_in_category, categories, earned_ids, entry_text, Achievement, AchievementCategory,
    AchievementProfile, ACHIEVEMENTS,
};
use ff_core::models::profile::Profile;

use crate::app::GameContext;
use crate::impl_state_for_menu;
use crate::states::base::{Label, Menu, MenuCore, MenuItem};
use crate::states::main_menu::loadable_saves;

fn earned_count(profile: &Profile) -> usize {
    earned_ids(profile as &dyn AchievementProfile).len()
}

pub struct AchievementCareerState {
    menu: MenuCore<Self>,
}

impl AchievementCareerState {
    pub fn new() -> Self {
        Self {
            menu: MenuCore::new("Achievements").with_intro_help(
                "Pick a saved career. Enter opens its achievements, Escape goes back.",
            ),
        }
    }
}

impl Default for AchievementCareerState {
    fn default() -> Self {
        Self::new()
    }
}

impl Menu for AchievementCareerState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let first = self.menu.items.first().map(|item| item.text(self, ctx));
        if first.as_deref().is_none_or(|text| text == "Back") {
            ctx.say("Achievements. No saved careers yet.");
            return;
        }
        let text = format!("Achievements. {}", self.current_text(ctx));
        ctx.say(&text);
    }

    fn build_items(&mut self, _ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let mut items = Vec::new();
        for (_path, profile) in loadable_saves() {
            let earned = earned_count(&profile);
            let total = ACHIEVEMENTS.len();
            let name = profile.name.clone();
            items.push(
                MenuItem::new(
                    format!("{name}: {earned} of {total} earned"),
                    move |_s: &mut Self, ctx| {
                        ctx.push_state(AchievementsState::new(profile.clone()))
                    },
                )
                .help(format!("Achievements for {name}.")),
            );
        }
        items.push(MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)));
        items
    }
}

impl_state_for_menu!(AchievementCareerState);

/// The category menu: pick a category, then browse its achievements.
pub struct AchievementsState {
    menu: MenuCore<Self>,
    pub profile: Profile,
}

impl AchievementsState {
    pub fn new(profile: Profile) -> Self {
        Self {
            menu: MenuCore::new(&format!("Achievements for {}", profile.name))
                .with_intro_help("Up and Down pick a category, Enter opens it, Escape goes back."),
            profile,
        }
    }

    fn summary_label(&self) -> String {
        format!(
            "Summary: {} of {} earned",
            earned_count(&self.profile),
            ACHIEVEMENTS.len()
        )
    }

    fn summary(&mut self, ctx: &mut GameContext) {
        ctx.say(&format!(
            "{} has earned {} of {} achievements.",
            self.profile.name,
            earned_count(&self.profile),
            ACHIEVEMENTS.len()
        ));
    }
}

impl Menu for AchievementsState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let text = format!(
            "Achievements for {}. {} of {} earned. {}",
            self.profile.name,
            earned_count(&self.profile),
            ACHIEVEMENTS.len(),
            self.current_text(ctx)
        );
        ctx.say(&text);
    }

    fn build_items(&mut self, _ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let earned = earned_ids(&self.profile as &dyn AchievementProfile);
        let mut items = vec![MenuItem::new(
            Label::dynamic(|s: &Self, _ctx| s.summary_label()),
            |s: &mut Self, ctx| s.summary(ctx),
        )
        .help("The total earned.")];
        for category in categories() {
            let achs = achievements_in_category(category.id);
            let done = achs.iter().filter(|a| earned.contains(a.id)).count();
            let c: &'static AchievementCategory = category;
            let a = achs.clone();
            items.push(
                MenuItem::new(
                    format!("{}. {done} of {}", category.title, achs.len()),
                    move |s: &mut Self, ctx| {
                        ctx.push_state(AchievementCategoryState::new(
                            s.profile.clone(),
                            c,
                            a.clone(),
                        ))
                    },
                )
                .help(category.description),
            );
        }
        items.push(MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)));
        items
    }
}

impl_state_for_menu!(AchievementsState);

/// One category's achievements: earned ones tell their story, locked ones
/// show their goal, and hidden ones keep the secret until earned.
pub struct AchievementCategoryState {
    menu: MenuCore<Self>,
    pub profile: Profile,
    pub category: &'static AchievementCategory,
    pub achs: Vec<&'static Achievement>,
}

impl AchievementCategoryState {
    pub fn new(
        profile: Profile,
        category: &'static AchievementCategory,
        achs: Vec<&'static Achievement>,
    ) -> Self {
        Self {
            menu: MenuCore::new(category.title)
                .with_intro_help("Up and Down move, Enter repeats the entry, Escape goes back."),
            profile,
            category,
            achs,
        }
    }

    fn earned_count(&self) -> usize {
        let earned = earned_ids(&self.profile as &dyn AchievementProfile);
        self.achs.iter().filter(|a| earned.contains(a.id)).count()
    }
}

impl Menu for AchievementCategoryState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let text = format!(
            "{}. {} of {} earned. {}",
            self.category.title,
            self.earned_count(),
            self.achs.len(),
            self.current_text(ctx)
        );
        ctx.say(&text);
    }

    fn build_items(&mut self, _ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let earned = earned_ids(&self.profile as &dyn AchievementProfile);
        let mut items = Vec::new();
        for achievement in &self.achs {
            let unlocked = earned.contains(achievement.id);
            let (name, description) = entry_text(achievement, unlocked);
            let (label, help_text) = if unlocked {
                (format!("Earned: {name} - {description}"), description)
            } else if achievement.hidden {
                (format!("Locked: {name}"), description)
            } else {
                // Locked, non-hidden entries show only the title; the
                // description stays hidden until the achievement is earned.
                (format!("Locked: {name}"), "Keep playing to unlock it.")
            };
            let spoken = label.clone();
            items.push(
                MenuItem::new(label, move |_s: &mut Self, ctx| ctx.say(&spoken)).help(help_text),
            );
        }
        items.push(MenuItem::new(
            "Back to the categories",
            |s: &mut Self, ctx| s.go_back(ctx),
        ));
        items
    }
}

impl_state_for_menu!(AchievementCategoryState);
