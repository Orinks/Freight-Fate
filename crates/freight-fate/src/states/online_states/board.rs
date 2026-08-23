//! The live drivers board and the Mastodon link screen (the second half of
//! `freight_fate/states/online_states.py`, split out for length).

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Instant;

use ff_core::pyfmt::round_py_int;
use serde_json::Value;

use crate::app::GameContext;
use crate::impl_state_for_menu;
use crate::online_presence::{self, MastodonStatus};
use crate::states::base::{InputEvent, Label, Menu, MenuCore, MenuItem};

use super::support::{
    load_identity, menu_default_enter, menu_default_handle_event, online_transport, open_url,
    run_worker, wall_time, Mailbox,
};

/// A speakable freshness phrase from a server epoch-milliseconds stamp.
pub fn updated_text(updated_at_ms: f64) -> String {
    let age_s = (wall_time() - updated_at_ms / 1000.0).max(0.0);
    if age_s < 90.0 {
        return "updated just now".to_string();
    }
    let minutes = round_py_int(age_s / 60.0);
    format!("updated {minutes} minutes ago")
}

/// `str(value)` for the board's string fields, `""` for a missing one.
fn field_text(entry: &Value, key: &str) -> String {
    match entry.get(key) {
        None | Some(Value::Null) => String::new(),
        Some(Value::String(s)) => s.clone(),
        Some(other) => online_presence::py_str(other),
    }
}

/// `float(entry.get("updatedAt", 0))`.
fn updated_at_ms(entry: &Value) -> f64 {
    match entry.get("updatedAt") {
        Some(Value::Number(n)) => n.as_f64().unwrap_or(0.0),
        Some(Value::String(s)) => s.trim().parse().unwrap_or(0.0),
        _ => 0.0,
    }
}

// -- DriversOnlineState ----------------------------------------------------------------------

/// The live drivers board as a spoken list.
///
/// Public data, so it works with or without the player's own sharing set
/// up. The fetch happens on a daemon thread; until it lands the menu holds a
/// single "checking" line.
pub struct DriversOnlineState {
    pub menu: MenuCore<Self>,
    /// The board once fetched: `Some(None)` when orinks.net could not be
    /// reached, `Some(Some(rows))` otherwise; `None` until the fetch lands.
    pub board: Option<Option<Vec<Value>>>,
    result: Mailbox<Option<Vec<Value>>>,
    fetched: Arc<AtomicBool>,
    announced: bool,
    pub threaded: bool,
}

impl DriversOnlineState {
    pub const TITLE: &'static str = "Drivers online";

    /// `DriversOnlineState(ctx)`.
    pub fn new(_ctx: &mut GameContext) -> Self {
        Self {
            menu: MenuCore::new(Self::TITLE),
            board: None,
            result: Mailbox::new(),
            fetched: Arc::new(AtomicBool::new(false)),
            announced: false,
            threaded: true,
        }
    }

    /// Whether the fetch has answered (`self._fetched.is_set()`).
    pub fn fetched(&self) -> bool {
        self.fetched.load(Ordering::SeqCst)
    }

    fn start_fetch(&mut self) {
        self.board = None;
        self.result = Mailbox::new();
        self.fetched = Arc::new(AtomicBool::new(false));
        self.announced = false;
        let result = self.result.clone();
        let fetched = Arc::clone(&self.fetched);
        let transport = online_transport();
        run_worker(self.threaded, "online-board", move || {
            result.post(online_presence::fetch_board(transport.as_ref()));
            fetched.store(true, Ordering::SeqCst);
        });
    }

    /// Move a landed fetch out of the mailbox (the worker sets `_board`
    /// before `_fetched`; here the board travels in the mailbox).
    fn absorb(&mut self) {
        if self.fetched() {
            if let Some(board) = self.result.take() {
                self.board = Some(board);
            }
        }
    }

    fn refresh_board(&mut self, ctx: &mut GameContext) {
        self.start_fetch();
        self.refresh(ctx, false);
        ctx.say("Checking the drivers board.");
    }
}

impl Menu for DriversOnlineState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn enter(&mut self, ctx: &mut GameContext) {
        self.start_fetch();
        menu_default_enter(self, ctx);
    }

    fn build_items(&mut self, _ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        self.absorb();
        if !self.fetched() {
            return vec![
                MenuItem::new("Checking the drivers board", |s: &mut Self, ctx| {
                    s.speak_current(ctx)
                }),
                MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)),
            ];
        }
        let mut items: Vec<MenuItem<Self>> = Vec::new();
        match self.board.as_ref().and_then(|b| b.as_ref()) {
            None => items.push(
                MenuItem::new(
                    "The drivers board could not be reached",
                    |s: &mut Self, ctx| s.speak_current(ctx),
                )
                .help("orinks.net did not answer. Refresh to try again."),
            ),
            Some(board) if board.is_empty() => items.push(MenuItem::new(
                "No drivers are on duty right now",
                |s: &mut Self, ctx| s.speak_current(ctx),
            )),
            Some(board) => {
                for entry in board {
                    let name = match entry.get("displayName") {
                        None => "A driver".to_string(),
                        Some(_) => field_text(entry, "displayName"),
                    };
                    let mut bits = vec![name, field_text(entry, "activity")];
                    let detail = field_text(entry, "detail");
                    if !detail.is_empty() {
                        bits.push(detail);
                    }
                    bits.push(updated_text(updated_at_ms(entry)));
                    let label = bits
                        .into_iter()
                        .filter(|bit| !bit.is_empty())
                        .collect::<Vec<_>>()
                        .join(". ");
                    items.push(MenuItem::new(label, |s: &mut Self, ctx| {
                        s.speak_current(ctx)
                    }));
                }
            }
        }
        items.push(
            MenuItem::new("Refresh", |s: &mut Self, ctx| s.refresh_board(ctx))
                .help("Check the board again."),
        );
        items.push(MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)));
        items
    }

    fn update(&mut self, ctx: &mut GameContext, dt: f64) {
        ctx.update_music_rotation(dt);
        if self.announced || !self.fetched() {
            return;
        }
        self.announced = true;
        self.refresh(ctx, false);
        match self.board.as_ref().and_then(|b| b.as_ref()) {
            None => ctx.say("The drivers board could not be reached."),
            Some(board) if board.is_empty() => ctx.say("No drivers are on duty right now."),
            Some(board) => {
                let count = format!(
                    "{} driver{}",
                    board.len(),
                    if board.len() != 1 { "s are" } else { " is" }
                );
                let current = self.current_text(ctx);
                ctx.say(&format!("{count} on duty. {current}"));
            }
        }
    }
}

impl_state_for_menu!(DriversOnlineState);

// -- MastodonLinkState -------------------------------------------------------------------------

/// The status worker's answer: the server's word, or `"error"`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MastodonOutcome {
    Status(MastodonStatus),
    Error,
}

/// Link the player's own Mastodon account through orinks.net.
///
/// The authorizing happens in the browser: the site is signed in with the
/// same orinks.net account as driver setup, so this menu only opens the
/// page and reports the server's word on the link. Unlinking lives on the
/// same page. The menu is STATIC for the same positional-memory reason as
/// OnlineSetupState; state rides in the labels.
pub struct MastodonLinkState {
    pub menu: MenuCore<Self>,
    pub checking: bool,
    check_started: Option<Instant>,
    still_checking_said: bool,
    /// worker -> update() mailbox
    pub outcome: Mailbox<MastodonOutcome>,
    opened_browser: bool,
    pub threaded: bool,
}

impl MastodonLinkState {
    pub const TITLE: &'static str = "Mastodon account";

    /// `MastodonLinkState(ctx)`.
    pub fn new(_ctx: &mut GameContext) -> Self {
        Self {
            menu: MenuCore::new(Self::TITLE),
            checking: false,
            check_started: None,
            still_checking_said: false,
            outcome: Mailbox::new(),
            opened_browser: false,
            threaded: true,
        }
    }

    fn status_label(&self, ctx: &GameContext) -> String {
        if self.checking {
            return "Checking the Mastodon link".to_string();
        }
        let s = &ctx.settings;
        if s.mastodon_linked {
            let spoken = if s.mastodon_linked_handle.is_empty() {
                String::new()
            } else {
                format!(" as {}", s.mastodon_linked_handle)
            };
            return format!("Check link status. Last known: linked{spoken}");
        }
        "Check link status".to_string()
    }

    fn open_page(&mut self, ctx: &mut GameContext) {
        let url = format!(
            "{}/freight-fate/online/mastodon",
            online_presence::base_url()
        );
        let copied = ctx.write_clipboard_text(&url);
        if !open_url(&url) {
            if copied {
                ctx.say(
                    "The browser could not be opened. The link is on your \
                     clipboard. Paste it into your browser's address bar.",
                );
            } else {
                ctx.say(
                    "The browser could not be opened and the clipboard did \
                     not take the link. In your browser, go to orinks.net, \
                     then Freight Fate, then Online, then Mastodon.",
                );
            }
            // The player may still get there by hand; keep the return
            // re-orientation armed either way.
            self.opened_browser = true;
            return;
        }
        self.opened_browser = true;
        let clipboard_note = if copied {
            " The link is also on your clipboard in case the browser did not open."
        } else {
            ""
        };
        ctx.say(&format!(
            "Opening the Mastodon link page in your browser.{clipboard_note} Authorize there, then come back here."
        ));
    }

    /// `_check_status(announce=True)`.
    pub fn check_status(&mut self, ctx: &mut GameContext, announce: bool) {
        if self.checking {
            return;
        }
        let Some(identity) = load_identity() else {
            ctx.say(
                "This needs your orinks.net account first. Choose Set up \
                 orinks.net account on the Online menu.",
            );
            return;
        };
        self.checking = true;
        self.check_started = Some(Instant::now());
        self.still_checking_said = false;
        self.refresh(ctx, true);
        if announce {
            ctx.say("Checking with orinks.net.");
        }
        let outcome = self.outcome.clone();
        let transport = online_transport();
        run_worker(self.threaded, "mastodon-status", move || {
            outcome.post(
                match online_presence::fetch_mastodon_status(&identity, transport.as_ref()) {
                    Some(status) => MastodonOutcome::Status(status),
                    None => MastodonOutcome::Error,
                },
            );
        });
    }
}

impl Menu for MastodonLinkState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn build_items(&mut self, _ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        vec![
            MenuItem::new(
                "Open the Mastodon link page in my browser",
                |s: &mut Self, ctx| s.open_page(ctx),
            )
            .help(
                "Sign in on orinks.net if asked, enter your Mastodon \
                 server, and authorize Freight Fate there. Then come back \
                 here and check the link status.",
            ),
            MenuItem::new(
                Label::dynamic(|s: &Self, ctx| s.status_label(ctx)),
                |s: &mut Self, ctx| s.check_status(ctx, true),
            )
            .help("Asks orinks.net whether a Mastodon account is linked to your driver."),
            MenuItem::new("Back", |s: &mut Self, ctx| s.go_back(ctx)),
        ]
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let s = &ctx.settings;
        let known = if s.mastodon_linked {
            let spoken = if s.mastodon_linked_handle.is_empty() {
                "a Mastodon account".to_string()
            } else {
                s.mastodon_linked_handle.clone()
            };
            format!("Last I checked, {spoken} was linked.")
        } else {
            "No Mastodon account is linked yet, as far as this computer knows.".to_string()
        };
        let current = self.current_text(ctx);
        ctx.say(&format!(
            "{}. Linking happens in your browser on orinks.net, \
             using the same sign-in as driver setup. {known} \
             {current}",
            Self::TITLE
        ));
    }

    fn handle_event(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        // Re-orient after the browser round trip, and answer "did it take"
        // without hunting: check the link the moment focus comes back.
        if matches!(event, InputEvent::WindowFocusGained) && self.opened_browser && !self.checking {
            ctx.say("Back in Freight Fate. Checking your Mastodon link.");
            self.check_status(ctx, false);
            return;
        }
        menu_default_handle_event(self, ctx, event);
    }

    fn update(&mut self, ctx: &mut GameContext, dt: f64) {
        ctx.update_music_rotation(dt);
        if self.checking
            && !self.still_checking_said
            && self
                .check_started
                .is_some_and(|started| started.elapsed().as_secs_f64() > 5.0)
        {
            self.still_checking_said = true;
            ctx.say("Still checking.");
        }
        let Some(outcome) = self.outcome.take() else {
            return;
        };
        self.checking = false;
        let status = match outcome {
            MastodonOutcome::Error => {
                self.refresh(ctx, true);
                ctx.say(
                    "I could not reach orinks.net to check the Mastodon link. Try again in a moment.",
                );
                return;
            }
            MastodonOutcome::Status(status) => status,
        };
        let linked = status.linked;
        ctx.settings.mastodon_linked = linked;
        ctx.settings.mastodon_linked_handle = if linked {
            status.handle.clone()
        } else {
            String::new()
        };
        if let Err(e) = ctx.settings.save() {
            log::warn!("Could not save settings: {e}");
        }
        self.refresh(ctx, true);
        if linked {
            let spoken = if ctx.settings.mastodon_linked_handle.is_empty() {
                "your Mastodon account".to_string()
            } else {
                ctx.settings.mastodon_linked_handle.clone()
            };
            ctx.say(&format!(
                "Linked: {spoken}. You can now turn on Share notable \
                 deliveries to Mastodon on the Online menu."
            ));
        } else {
            ctx.say(
                "No Mastodon account is linked yet. Open the link page in \
                 your browser, authorize there, then check again.",
            );
        }
    }
}

impl_state_for_menu!(MastodonLinkState);
