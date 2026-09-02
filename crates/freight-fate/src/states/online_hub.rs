//! The Online menu: every online feature in one place on the main menu
//! (port of `freight_fate/states/online_hub.py`).
//!
//! These items used to live in Settings under an Online category, which buried
//! actions a player reaches for by name -- "restore my save on this new
//! computer", "who is hauling right now" -- behind a settings hunt. The hub
//! keeps each consent toggle next to the account item that gives it meaning,
//! and the drivers board sits first because viewing it shares nothing.
//!
//! Toggles keep the Settings adjust model (Enter or Right changes forward,
//! Left changes backward) so nothing moves under a player's fingers; action
//! rows ignore Left and Right the same way the old category did.

use crate::app::{GameContext, Say};
use crate::impl_state_for_menu;
use crate::online_presence::setup_page_url;
use crate::states::account_achievements::AccountAchievementsState;
use crate::states::base::{InputEvent, Key, Label, Menu, MenuCore, MenuItem};
use crate::states::cloud_save_states::{CloudBackupConsentState, CloudBackupState};
use crate::states::online_states::{
    load_identity, menu_default_handle_event, open_url, DriversOnlineState, MastodonLinkState,
    OnlineSetupState, ProfileSharingSyncState,
};

pub struct OnlineHubState {
    pub menu: MenuCore<Self>,
}

impl Default for OnlineHubState {
    fn default() -> Self {
        Self {
            menu: MenuCore::new(Self::TITLE).with_intro_help(Self::INTRO_HELP),
        }
    }
}

impl OnlineHubState {
    pub const TITLE: &'static str = "Online";
    pub const INTRO_HELP: &'static str =
        "Use up and down arrows to pick an item. Enter opens an item or \
         changes a setting forward, Right arrow also changes a setting \
         forward, and Left arrow changes it backward. Escape goes back. \
         Drivers on duty, the on and off duty notices, and Account          achievements work without connecting. \
         Account-backed services wait until you connect an orinks.net account, \
         and everything you share can be turned off again.";

    /// `OnlineHubState(ctx)`.
    pub fn new(_ctx: &mut GameContext) -> Self {
        Self::default()
    }

    fn on_off(value: bool) -> &'static str {
        if value {
            "on"
        } else {
            "off"
        }
    }

    fn adjust_row(&mut self, ctx: &mut GameContext, direction: i64) {
        // The board, achievements, account setup, setup page, restore, and Mastodon link
        // rows are actions, so left/right does nothing there instead of
        // changing a nearby toggle. This list is positional: a row added to
        // build_items has to be added here at the same index, or every toggle
        // below it starts answering for its neighbour.
        match self.menu.index {
            1 => self.toggle_duty_notifications(ctx, direction),
            3 => self.toggle_online_services(ctx, direction),
            6 => self.toggle_online_presence(ctx, direction),
            7 => self.toggle_cloud_saves(ctx, direction),
            9 => self.toggle_mastodon_sharing(ctx, direction),
            11 => self.toggle_discord_presence(ctx, direction),
            _ => {}
        }
    }

    fn announce(&mut self, ctx: &mut GameContext) {
        self.refresh(ctx, true);
        if let Err(e) = ctx.settings.save() {
            log::warn!("Could not save settings: {e}");
        }
        ctx.audio.play("ui/menu_select");
        self.speak_current(ctx);
    }

    fn drivers_board(&mut self, ctx: &mut GameContext) {
        let board = DriversOnlineState::new(ctx);
        ctx.push_state(board);
    }

    /// Toggle the spoken notice when another driver goes on or off duty.
    fn toggle_duty_notifications(&mut self, ctx: &mut GameContext, _direction: i64) {
        ctx.settings.duty_notifications = !ctx.settings.duty_notifications;
        ctx.apply_duty_notifications();
        self.announce(ctx);
    }

    fn account_achievements(&mut self, ctx: &mut GameContext) {
        ctx.push_state(AccountAchievementsState::new());
    }

    /// Toggle the master online services switch.
    ///
    /// When turned off all online features stop immediately. Individual
    /// toggle values are preserved so re-enabling restores the previous
    /// configuration without re-setting each service.
    fn toggle_online_services(&mut self, ctx: &mut GameContext, _direction: i64) {
        ctx.settings.online_services = !ctx.settings.online_services;
        if let Err(e) = ctx.settings.save() {
            log::warn!("Could not save settings: {e}");
        }
        // Both directions walk the same list: every live service re-reads the
        // master switch and stands down or reconnects to match.
        ctx.apply_presence();
        ctx.apply_online_presence();
        ctx.apply_duty_notifications();
        ctx.apply_cloud_saves();
        ctx.apply_mastodon_sharing();
        self.announce(ctx);
    }

    fn online_account_setup(&mut self, ctx: &mut GameContext) {
        let setup = OnlineSetupState::new(ctx);
        ctx.push_state(setup);
    }

    /// Open the driver setup page, or hand over the address if it cannot.
    ///
    /// Same shape as the Mastodon link page's opener: the clipboard write is
    /// attempted first so the fallback can promise something true, and the
    /// browser opener failing is never the end of the road -- a remote or
    /// streamed session is the normal case where it does nothing at all.
    fn open_setup_page(&mut self, ctx: &mut GameContext) {
        let url = setup_page_url();
        let copied = ctx.write_clipboard_text(&url);
        if !open_url(&url) {
            if copied {
                ctx.say(
                    "The browser could not be opened. The address is on your \
                     clipboard. Paste it into your browser's address bar.",
                );
            } else {
                // Spelled the way a player has to type it, since neither the
                // browser nor the clipboard is going to carry it for them.
                ctx.say(&format!(
                    "The browser could not be opened and the clipboard did \
                     not take the address. Go to {url} in any browser."
                ));
            }
            return;
        }
        let clipboard_note = if copied {
            " The address is also on your clipboard in case the browser did not open."
        } else {
            ""
        };
        ctx.say(&format!(
            "Opening your driver setup page in your browser. Sign in there \
             with your orinks.net account to change your driver name, your \
             profile sharing, or the computers signed in to your account.{clipboard_note}"
        ));
    }

    fn toggle_online_presence(&mut self, ctx: &mut GameContext, _direction: i64) {
        if load_identity().is_none() {
            // Not set up yet: the spoken disclosure and browser confirmation
            // happen in the setup state; it flips the setting on success.
            // The setting alone shares nothing without an identity.
            let setup = OnlineSetupState::new(ctx);
            ctx.push_state(setup);
            return;
        }
        let target = if ctx.settings.profile_sharing_pending_off {
            false
        } else {
            !ctx.settings.online_presence
        };
        let sync = ProfileSharingSyncState::new(ctx, target);
        ctx.push_state(sync);
    }

    fn toggle_cloud_saves(&mut self, ctx: &mut GameContext, _direction: i64) {
        if load_identity().is_none() {
            // Cloud backup rides the same account credentials as the board;
            // without them the setting would be inert, so point at the setup
            // item instead of flipping a switch that does nothing.
            ctx.say(
                "Cloud backup uses the same orinks.net sign-in as your driver \
                 profile. Choose Set up orinks.net account on this menu first, \
                 then turn cloud backup on.",
            );
            return;
        }
        if !ctx.settings.cloud_saves {
            let consent = CloudBackupConsentState::new(ctx);
            ctx.push_state(consent);
            return;
        }
        ctx.settings.cloud_saves = false;
        if let Err(e) = ctx.settings.save() {
            log::warn!("Could not save settings: {e}");
        }
        ctx.apply_cloud_saves();
        self.announce(ctx);
    }

    /// Careers whose backups are stopped until a copy is chosen.
    ///
    /// Never fails: this feeds a menu label that is spoken on every pass
    /// through the Online menu, and a cloud service that is off, missing or
    /// mid-start must cost the player a menu, not the menu itself.
    pub fn waiting_conflicts(ctx: &GameContext) -> Vec<String> {
        ctx.cloud_saves_service().conflicts().into_keys().collect()
    }

    fn cloud_backup_label(ctx: &GameContext) -> String {
        let waiting = Self::waiting_conflicts(ctx);
        if waiting.is_empty() {
            return "Restore a cloud backup".to_string();
        }
        if waiting.len() == 1 {
            // Name the career: with several backed up, "a career" sends the
            // player looking for which one.
            return format!(
                "Restore a cloud backup. {} is waiting for you to \
                 choose which copy to keep",
                waiting[0]
            );
        }
        format!(
            "Restore a cloud backup. {} careers are waiting for \
             you to choose which copy to keep",
            waiting.len()
        )
    }

    fn cloud_backup_help(ctx: &GameContext) -> String {
        let base = "List the careers backed up to your orinks.net account and bring \
             one onto this computer.";
        if Self::waiting_conflicts(ctx).is_empty() {
            return base.to_string();
        }
        // Say the consequence before the instruction: the reason to open a
        // row named "Restore" when you want to keep your own save is that
        // nothing backs up until you do, and that is what a player needs to
        // hear to override the name.
        format!(
            "Open this to choose which copy to keep. A career here changed on \
             another computer, and it is not backing up at all until you \
             pick. Choosing this computer's save keeps what you have played \
             and sends it up; nothing is overwritten until you choose. {base}"
        )
    }

    fn cloud_backup_menu(&mut self, ctx: &mut GameContext) {
        let backup = CloudBackupState::new(ctx);
        ctx.push_state(backup);
    }

    fn toggle_mastodon_sharing(&mut self, ctx: &mut GameContext, _direction: i64) {
        if load_identity().is_none() {
            ctx.say(
                "Sharing to Mastodon uses your orinks.net account. Choose \
                 Set up orinks.net account on this menu first, then link a \
                 Mastodon account.",
            );
            return;
        }
        if !ctx.settings.mastodon_linked && !ctx.settings.mastodon_sharing {
            // No known link: the switch would be inert, so point at the link
            // item instead of flipping it (same shape as cloud backup).
            ctx.say(
                "Sharing to Mastodon needs a linked Mastodon account. Choose \
                 Link a Mastodon account on this menu first, then turn \
                 sharing on.",
            );
            return;
        }
        ctx.settings.mastodon_sharing = !ctx.settings.mastodon_sharing;
        ctx.apply_mastodon_sharing();
        self.announce(ctx);
        if ctx.settings.mastodon_sharing {
            // The label said "on"; this says what "on" means, every time.
            ctx.say_with(
                "Only deliveries that earn an achievement, a level, or a perfect \
                 streak are posted. Posts are public on your own Mastodon \
                 account and carry the Freight Fate Runs hashtag, which is \
                 separate from the Freight Fate tag players use to talk about \
                 the game.",
                Say::queued(),
            );
        }
    }

    fn mastodon_account(&mut self, ctx: &mut GameContext) {
        if load_identity().is_none() {
            ctx.say(
                "Linking Mastodon uses your orinks.net sign-in. Choose Set \
                 up orinks.net account on this menu first.",
            );
            return;
        }
        let link = MastodonLinkState::new(ctx);
        ctx.push_state(link);
    }

    fn toggle_discord_presence(&mut self, ctx: &mut GameContext, _direction: i64) {
        ctx.settings.discord_presence = !ctx.settings.discord_presence;
        ctx.apply_presence();
        self.announce(ctx);
    }
}

impl Menu for OnlineHubState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn build_items(&mut self, _ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        vec![
            MenuItem::new("Drivers on duty", |s: &mut Self, ctx| s.drivers_board(ctx)).help(
                "Hear who is hauling right now on the public orinks.net \
                 drivers board. Viewing the board shares nothing about you.",
            ),
            // Right under the list it watches. Off by default: a line that
            // arrives unasked while the player is driving is theirs to turn
            // on, and each player who does costs the site one cached read of
            // the list a minute.
            MenuItem::new(
                Label::dynamic(|_: &Self, ctx| {
                    format!(
                        "Say when drivers go on or off duty: {}",
                        Self::on_off(ctx.settings.duty_notifications)
                    )
                }),
                |s: &mut Self, ctx| s.toggle_duty_notifications(ctx, 1),
            )
            .help(
                "When on, the game says when another driver sets off or signs                  off, like Road Star is on duty, wherever you are in the game.                  It checks the public drivers list about once a minute, the                  same way the Drivers on duty screen does, and never mentions                  you. Works without an orinks.net account and shares nothing                  about you. Off keeps it quiet; the Drivers on duty screen                  still shows who is out.",
            ),
            MenuItem::new("Account achievements", |s: &mut Self, ctx| {
                s.account_achievements(ctx)
            })
            .help(
                "Review achievements earned across every career on this installation. \
                 This account collection does not replace the career-specific \
                 Achievements menu on the main menu.",
            ),
            // This line's master switch survives the move into the hub: one
            // row that stands every orinks.net and sharing service down (or
            // back up) without losing the individual consents beneath it.
            MenuItem::new(
                Label::dynamic(|_: &Self, ctx| {
                    format!(
                        "Online services: {}",
                        Self::on_off(ctx.settings.online_services)
                    )
                }),
                |s: &mut Self, ctx| s.toggle_online_services(ctx, 1),
            )
            .help(
                "Master switch for the orinks.net and sharing services. \
                 When off, the drivers board, profile sharing, cloud backup, \
                 Mastodon sharing, and Discord presence all behave as \
                 disabled without losing their individual settings. Live \
                 weather, traffic, and parking are separate: they follow \
                 their own toggles under Settings.",
            ),
            MenuItem::new(
                Label::dynamic(|_: &Self, _| {
                    if load_identity().is_some() {
                        "orinks.net account: connected".to_string()
                    } else {
                        "Set up orinks.net account".to_string()
                    }
                }),
                |s: &mut Self, ctx| s.online_account_setup(ctx),
            )
            .help(
                "Connect the game to your orinks.net account. Connecting turns \
                 Profile sharing on and starts backing your careers up to that \
                 account; both are single items on this menu if you want either off. \
                 To change your driver name or sign a computer out afterwards, use \
                 Open my driver setup page below.",
            ),
            // Deliberately its own row rather than a job the account row does
            // once connected: that row is also the way back in when
            // orinks.net stops accepting this computer, which is exactly when
            // a player needs to re-activate rather than browse. Keeping both
            // available means the spoken recovery advice (cloud_saves
            // AUTH_HELP) still names something that works, and the row never
            // changes what it does under a player's fingers.
            MenuItem::new("Open my driver setup page", |s: &mut Self, ctx| {
                s.open_setup_page(ctx)
            })
            .help(
                "Opens your orinks.net driver setup page in a browser. \
                 That page is where you change your driver name, turn profile \
                 sharing on or off, see the computers signed in to your \
                 account, and sign any of them out. Nothing about it has to \
                 be typed or remembered: the game knows the address.",
            ),
            MenuItem::new(
                // The identity check lives INSIDE the label so it is
                // fresh on every read: a captured build-time value went
                // stale the moment setup completed (or the identity file
                // changed on disk) and misreported "on" while dormant.
                Label::dynamic(|_: &Self, ctx| {
                    if load_identity().is_none() {
                        return "Profile sharing: not set up".to_string();
                    }
                    if ctx.settings.profile_sharing_pending_off {
                        "Profile sharing: off requested".to_string()
                    } else {
                        format!(
                            "Profile sharing: {}",
                            Self::on_off(ctx.settings.online_presence)
                        )
                    }
                }),
                |s: &mut Self, ctx| s.toggle_online_presence(ctx, 1),
            )
            .help(
                "Profile sharing is one optional public setting for your driver profile, \
                 official achievements, automatic road-journal posts, updates feed, \
                 and on-duty board activity. Career statistics on the public profile \
                 include lifetime career earnings; the money you currently have is \
                 never published. Nothing is shared until you set it up: \
                 Set up the orinks.net account first, which turns this on. \
                 Cloud saves remain private and separate.",
            ),
            MenuItem::new(
                Label::dynamic(|_: &Self, ctx| {
                    if load_identity().is_some() {
                        format!(
                            "Back up saves to your orinks.net account: {}",
                            Self::on_off(ctx.settings.cloud_saves)
                        )
                    } else {
                        "Back up saves to your orinks.net account: not set up".to_string()
                    }
                }),
                |s: &mut Self, ctx| s.toggle_cloud_saves(ctx, 1),
            )
            .help(
                "After each game save, upload that career to your \
                 own orinks.net account so you can restore it on another \
                 computer. Backups are private to your account and never \
                 appear as public downloads. Uses the same orinks.net account \
                 sign-in, and comes on when you connect that account. The \
                 career statistics on your public profile are read from these \
                 backups, so turning this off empties them.",
            ),
            MenuItem::new(
                // Dynamic like the Mastodon row below, and for a sharper
                // reason: a career stops backing up entirely until someone
                // picks which copy wins, and this row is the only place that
                // choice can be made. Under the bare name a player who wants
                // to KEEP what he has just played reads "Restore" as "replace
                // my career with the cloud one" and arrows straight past the
                // thing that would unblock him -- Brandon (armstrong445) did
                // exactly that, landing on this row five times across twenty
                // minutes without opening it, and signed out and re-activated
                // instead, which cannot clear a conflict (2026-08-15). The
                // waiting decision now says itself, on the row.
                Label::dynamic(|_: &Self, ctx| Self::cloud_backup_label(ctx)),
                |s: &mut Self, ctx| s.cloud_backup_menu(ctx),
            )
            .help(Label::dynamic(|_: &Self, ctx| Self::cloud_backup_help(ctx))),
            MenuItem::new(
                // Same freshness rule as Profile sharing: the identity and
                // linked-handle checks live inside the label.
                Label::dynamic(|_: &Self, ctx| {
                    if load_identity().is_none() {
                        return "Share notable deliveries to Mastodon: not set up".to_string();
                    }
                    if ctx.settings.mastodon_linked {
                        format!(
                            "Share notable deliveries to Mastodon: {}",
                            Self::on_off(ctx.settings.mastodon_sharing)
                        )
                    } else {
                        "Share notable deliveries to Mastodon: not linked".to_string()
                    }
                }),
                |s: &mut Self, ctx| s.toggle_mastodon_sharing(ctx, 1),
            )
            .help(
                "When on, finishing a delivery that earns an achievement, a \
                 level, or a perfect streak posts a short public summary \
                 to your own Mastodon account with the Freight Fate Runs \
                 hashtag, which is separate from the Freight Fate tag \
                 players use to talk about the game. Routine deliveries \
                 are never posted. Link a \
                 Mastodon account first with the Mastodon account item.",
            ),
            MenuItem::new(
                Label::dynamic(|_: &Self, ctx| {
                    let s = &ctx.settings;
                    if s.mastodon_linked {
                        if s.mastodon_linked_handle.is_empty() {
                            "Mastodon account: linked".to_string()
                        } else {
                            format!("Mastodon account: linked as {}", s.mastodon_linked_handle)
                        }
                    } else {
                        "Link a Mastodon account".to_string()
                    }
                }),
                |s: &mut Self, ctx| s.mastodon_account(ctx),
            )
            .help(
                "Opens a page on orinks.net where you authorize your \
                 own Mastodon server, using the same orinks.net sign-in \
                 as driver setup. Unlinking also happens there.",
            ),
            MenuItem::new(
                Label::dynamic(|_: &Self, ctx| {
                    format!(
                        "Discord presence: {}",
                        Self::on_off(ctx.settings.discord_presence)
                    )
                }),
                |s: &mut Self, ctx| s.toggle_discord_presence(ctx, 1),
            )
            .help(
                "Show broad activity in Discord, like the main menu, \
                 driving a route, or resting. Only general game status \
                 is shared, never your save files or personal details. \
                 Has no effect if Discord is not running. Works without \
                 a driver profile.",
            ),
            MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)),
        ]
    }

    fn handle_event(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        match event.key_down() {
            Some((Key::Right, _, _)) => self.adjust_row(ctx, 1),
            Some((Key::Left, _, _)) => self.adjust_row(ctx, -1),
            _ => menu_default_handle_event(self, ctx, event),
        }
    }

    /// D-pad left/right on a controller maps to the same per-item adjust.
    fn adjust(&mut self, ctx: &mut GameContext, direction: i64) {
        self.adjust_row(ctx, direction);
    }
}

impl_state_for_menu!(OnlineHubState);
