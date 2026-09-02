//! Choosing, resetting and deleting saved careers (the `LoadDriverState`,
//! `ManageCareersState`, `CareerActionsState` and `ConfirmCareerActionState`
//! classes of `main_menu.py`).

use std::path::PathBuf;

use ff_core::models::profile::{LegacyCareerError, Profile};
use ff_core::models::start_options::{apply_start_option, option_for_profile};
use ff_core::playtest_levers::apply_continue_levers;
use ff_core::pyfmt::fmt_grouped;

use crate::app::{GameContext, Say};
use crate::impl_state_for_menu;
use crate::states::base::{Menu, MenuCore, MenuItem};
use crate::states::main_menu::{
    career_location, career_summary, legacy_saves, loadable_saves, pending_notice_state,
    world_entry_state, MainMenuState,
};
use crate::states::save_notice::LegacyCareerNoticeState;

pub struct LoadDriverState {
    menu: MenuCore<Self>,
}

impl LoadDriverState {
    pub fn new() -> Self {
        Self {
            menu: MenuCore::new("Choose career")
                .with_intro_help("Up and Down pick a career, Enter loads it, Escape goes back."),
        }
    }

    fn explain_legacy(&mut self, ctx: &mut GameContext, legacy: &LegacyCareerError) {
        ctx.push_state(LegacyCareerNoticeState::new(&legacy.name));
    }

    fn pick(&mut self, ctx: &mut GameContext, profile: &Profile) {
        ctx.profile = Some(profile.clone());
        let lever_notes = apply_continue_levers(ctx);
        ctx.say(&format!("Welcome back, {}.", profile.name));
        // The welcome above must be heard in full before the city menu's own
        // "Parked at..." announcement -- see world_entry_state.
        let next = pending_notice_state(ctx).unwrap_or_else(|| world_entry_state(ctx, true));
        ctx.replace_shared_with(next, true, true);
        for note in lever_notes {
            ctx.say_with(note, Say::queued());
        }
    }
}

impl Default for LoadDriverState {
    fn default() -> Self {
        Self::new()
    }
}

impl Menu for LoadDriverState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let mut items = Vec::new();
        for (path, profile) in loadable_saves() {
            let label = career_summary(ctx, &path, &profile, true);
            let help = format!("Load {}, {}.", profile.name, career_location(ctx, &profile));
            items.push(
                MenuItem::new(label, move |s: &mut Self, ctx| s.pick(ctx, &profile)).help(help),
            );
        }
        // Careers the 1.9 load gate refused stay on the list with a spoken
        // label -- silently dropping them reads as data loss. Picking one
        // opens the notice that explains and offers a fresh start.
        for legacy in legacy_saves() {
            items.push(
                MenuItem::new(
                    format!(
                        "{}: career from an earlier version of Freight Fate",
                        legacy.name
                    ),
                    move |s: &mut Self, ctx| s.explain_legacy(ctx, &legacy),
                )
                .help(
                    "This career cannot continue in version 1.9. Enter \
                     explains and offers a new career; the save is not touched.",
                ),
            );
        }
        items.push(MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)));
        items
    }
}

impl_state_for_menu!(LoadDriverState);

pub struct ManageCareersState {
    menu: MenuCore<Self>,
}

impl ManageCareersState {
    pub fn new() -> Self {
        Self {
            menu: MenuCore::new("Manage careers").with_intro_help(
                "Up and Down pick a career, Enter opens reset and delete, Escape goes back.",
            ),
        }
    }
}

impl Default for ManageCareersState {
    fn default() -> Self {
        Self::new()
    }
}

impl Menu for ManageCareersState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn build_items(&mut self, ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let mut items = Vec::new();
        for (path, profile) in loadable_saves() {
            let label = career_summary(ctx, &path, &profile, true);
            let help = format!(
                "Manage {}. Reset starts the career over; delete removes the save.",
                profile.name
            );
            items.push(
                MenuItem::new(label, move |_s: &mut Self, ctx| {
                    ctx.push_state(CareerActionsState::new(path.clone(), profile.clone()))
                })
                .help(help),
            );
        }
        items.push(MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)));
        items
    }
}

impl_state_for_menu!(ManageCareersState);

/// Which destructive action a confirmation screen is guarding.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CareerAction {
    Reset,
    Delete,
}

impl CareerAction {
    /// `_action_label`.
    pub fn label(self) -> &'static str {
        match self {
            CareerAction::Reset => "reset",
            CareerAction::Delete => "delete",
        }
    }
}

pub struct CareerActionsState {
    menu: MenuCore<Self>,
    pub path: PathBuf,
    pub profile: Profile,
}

impl CareerActionsState {
    pub fn new(path: PathBuf, profile: Profile) -> Self {
        Self {
            menu: MenuCore::new("Career actions")
                .with_intro_help("Reset and delete both ask for confirmation. Escape goes back."),
            path,
            profile,
        }
    }

    fn confirm(&mut self, ctx: &mut GameContext, action: CareerAction) {
        ctx.push_state(ConfirmCareerActionState::new(
            self.path.clone(),
            self.profile.clone(),
            action,
        ));
    }
}

impl Menu for CareerActionsState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let text = format!(
            "Actions for {}. {}",
            career_summary(ctx, &self.path, &self.profile, true),
            self.current_text(ctx)
        );
        ctx.say_with(text, Say::queued().review(false));
    }

    fn build_items(&mut self, _ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        vec![
            MenuItem::new("Reset this career", |s: &mut Self, ctx| {
                s.confirm(ctx, CareerAction::Reset)
            })
            .help(
                "Starts over with a fresh truck, money, career stats, market, \
                 and hours clock.",
            ),
            MenuItem::new("Delete this career", |s: &mut Self, ctx| {
                s.confirm(ctx, CareerAction::Delete)
            })
            .help("Removes this saved career for good."),
            MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)),
        ]
    }
}

impl_state_for_menu!(CareerActionsState);

pub struct ConfirmCareerActionState {
    menu: MenuCore<Self>,
    pub path: PathBuf,
    pub profile: Profile,
    pub action: CareerAction,
}

impl ConfirmCareerActionState {
    pub fn new(path: PathBuf, profile: Profile, action: CareerAction) -> Self {
        Self {
            menu: MenuCore::new("Confirm career action")
                .with_open_sound(Some("ui/error"))
                .with_intro_help("Enter confirms, Escape cancels."),
            path,
            profile,
            action,
        }
    }

    fn confirm(&mut self, ctx: &mut GameContext) {
        let name = self.profile.name.clone();
        let message = match self.action {
            CareerAction::Reset => {
                let mut fresh = Profile::named_in(&name, &self.profile.current_city);
                apply_start_option(&mut fresh, option_for_profile(&self.profile));
                if let Err(e) = fresh.save() {
                    log::error!("Could not save the profile: {e}");
                }
                format!(
                    "{name} reset. The career starts over at {} with {} and {} dollars.",
                    ctx.world.spoken_city(&fresh.current_city, None),
                    fresh.carrier_name,
                    fmt_grouped(fresh.money, 0)
                )
            }
            CareerAction::Delete => {
                let _ = std::fs::remove_file(&self.path);
                if ctx.profile.as_ref().is_some_and(|p| p.path() == self.path) {
                    ctx.profile = None;
                }
                format!("{name} deleted.")
            }
        };
        ctx.reset_to(MainMenuState::new());
        ctx.say(&message);
    }
}

impl Menu for ConfirmCareerActionState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let detail = match self.action {
            CareerAction::Reset => format!(
                "Reset starts over at {} with a fresh truck, starting money, \
                 no active trip, and no delivery history.",
                ctx.world.spoken_city(&self.profile.current_city, None)
            ),
            CareerAction::Delete => "Delete removes this saved career for good.".to_string(),
        };
        let text = format!(
            "Confirm {} for {}. {detail} {}",
            self.action.label(),
            self.profile.name,
            self.current_text(ctx)
        );
        ctx.say_with(text, Say::new().review(false));
    }

    fn build_items(&mut self, _ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        let label = self.action.label();
        vec![
            MenuItem::new(
                format!("Yes, {label} {}", self.profile.name),
                |s: &mut Self, ctx| s.confirm(ctx),
            )
            .help(format!("Confirm and {label} this saved career.")),
            MenuItem::new("No, keep this career", |s: &mut Self, ctx| s.go_back(ctx))
                .help("Back to career actions, nothing changed."),
        ]
    }
}

impl_state_for_menu!(ConfirmCareerActionState);
