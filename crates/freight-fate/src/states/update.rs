//! Update screens: check, prompt, what's-new reader, and download (port of
//! `freight_fate/states/update.py`).
//!
//! All fully spoken, matching the rest of the game's menus. The check and
//! the download run on background threads; the states poll them every frame
//! and speak progress, so the game loop (and the screen reader) never blocks
//! on the network.

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use ff_core::pyfmt::fmt_f;
use ff_core::settings::Settings;

use crate::app::{version, GameContext, Say};
use crate::impl_state_for_menu;
use crate::net;
use crate::states::base::{InputEvent, Key, Menu, MenuCore, MenuItem, State};
use crate::updater::{self, DownloadError, UpdateInfo, UpdaterEnv};

/// Background release check; poll [`UpdateChecker::is_done`] from the main
/// loop.
#[derive(Clone)]
pub struct UpdateChecker {
    done: Arc<AtomicBool>,
    result: Arc<Mutex<Option<UpdateInfo>>>,
    error: Arc<Mutex<Option<String>>>,
}

impl UpdateChecker {
    /// Start the check on a daemon thread.
    pub fn new(settings: &Settings) -> Self {
        let checker = Self::idle();
        let build = updater::load_build_info(version());
        let channel = updater::resolve_channel(&settings.update_channel, build.as_ref());
        let worker = checker.clone();
        let current = version().to_string();
        std::thread::Builder::new()
            .name("update-check".into())
            .spawn(move || worker.run(&channel, &current, build.as_ref()))
            .ok();
        checker
    }

    /// A checker that has already finished with the given answer (the test
    /// seam the Python suite reached with a `SimpleNamespace(done, result)`).
    pub fn finished(result: Option<UpdateInfo>, error: Option<String>) -> Self {
        let checker = Self::idle();
        *checker.result.lock().unwrap_or_else(|e| e.into_inner()) = result;
        *checker.error.lock().unwrap_or_else(|e| e.into_inner()) = error;
        checker.done.store(true, Ordering::SeqCst);
        checker
    }

    /// A checker nothing has started: never done (`threading.Event()` unset).
    pub fn idle() -> Self {
        Self {
            done: Arc::new(AtomicBool::new(false)),
            result: Arc::new(Mutex::new(None)),
            error: Arc::new(Mutex::new(None)),
        }
    }

    fn run(&self, channel: &str, current: &str, build: Option<&updater::BuildInfo>) {
        match updater::check_for_update(channel, current, build) {
            Ok(result) => {
                *self.result.lock().unwrap_or_else(|e| e.into_inner()) = result;
            }
            Err(e) => {
                // offline, rate-limited, GitHub down...
                log::warn!("Update check failed: {e:?}");
                *self.error.lock().unwrap_or_else(|e| e.into_inner()) = Some(format!(
                    "Could not reach the update server. {}",
                    net::describe_error(&e)
                ));
            }
        }
        self.done.store(true, Ordering::SeqCst);
    }

    /// `checker.done.is_set()`.
    pub fn is_done(&self) -> bool {
        self.done.load(Ordering::SeqCst)
    }

    /// `checker.result`.
    pub fn result(&self) -> Option<UpdateInfo> {
        self.result
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .clone()
    }

    /// `checker.error`.
    pub fn error(&self) -> Option<String> {
        self.error.lock().unwrap_or_else(|e| e.into_inner()).clone()
    }
}

/// Manual 'Check for updates' from the Settings menu.
pub struct UpdateCheckState {
    pub checker: Option<UpdateChecker>,
    pub message: String,
}

impl UpdateCheckState {
    pub fn new() -> Self {
        Self {
            checker: None,
            message: String::new(),
        }
    }
}

impl Default for UpdateCheckState {
    fn default() -> Self {
        Self::new()
    }
}

impl State for UpdateCheckState {
    fn enter(&mut self, ctx: &mut GameContext) {
        if !updater::is_frozen() {
            self.message = "Updates are only available in the packaged game. \
                            This copy runs from source; update it with git."
                .to_string();
            ctx.say(&format!("{} Press Escape to go back.", self.message));
            return;
        }
        if self.checker.is_none() {
            ctx.say("Checking for updates...");
            self.checker = Some(UpdateChecker::new(&ctx.settings));
        }
    }

    fn update(&mut self, ctx: &mut GameContext, dt: f64) {
        ctx.update_music_rotation(dt);
        let Some(c) = &self.checker else {
            return;
        };
        if !c.is_done() || !self.message.is_empty() {
            return;
        }
        if let Some(error) = c.error() {
            self.message = format!("{error} Try again in a little while.");
        } else if let Some(info) = c.result() {
            ctx.replace_state(UpdatePromptState::new(info));
            return;
        } else {
            self.message = format!(
                "You are up to date. Freight Fate version {}.",
                updater::spoken_version(version())
            );
        }
        ctx.say(&format!("{} Press Escape to go back.", self.message));
    }

    fn handle_event(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        let Some((key, _, _)) = event.key_down() else {
            return;
        };
        if matches!(key, Key::Escape | Key::Return | Key::KpEnter) {
            ctx.audio.play("ui/menu_back");
            ctx.pop_state();
        }
    }

    fn lines(&self, _ctx: &GameContext) -> Vec<String> {
        let status = if self.message.is_empty() {
            "Checking for updates...".to_string()
        } else {
            self.message.clone()
        };
        vec!["Check for updates".to_string(), String::new(), status]
    }
}

/// Asks whether to download a newly found update.
pub struct UpdatePromptState {
    menu: MenuCore<Self>,
    pub info: UpdateInfo,
}

impl UpdatePromptState {
    pub fn new(info: UpdateInfo) -> Self {
        Self {
            menu: MenuCore::new("Update available").with_intro_help(
                "A new version of the game is available. Download and \
                 restart installs it now. What's new reads the list of \
                 changes. Skip this version stops asking about this \
                 particular update.",
            ),
            info,
        }
    }

    fn download(&mut self, ctx: &mut GameContext) {
        if !updater::is_frozen() {
            ctx.say(
                "Updates can only be installed in the packaged game. This copy runs from source.",
            );
            return;
        }
        ctx.replace_state(UpdateDownloadState::new(self.info.clone()));
    }

    fn whats_new(&mut self, ctx: &mut GameContext) {
        ctx.push_state(WhatsNewState::new(self.info.clone()));
    }

    fn skip(&mut self, ctx: &mut GameContext) {
        ctx.settings.skipped_update = self.info.tag.clone();
        if let Err(e) = ctx.settings.save() {
            log::warn!("Could not save settings: {e}");
        }
        ctx.say(&format!(
            "Skipping {}. You will be asked again when the next update comes out.",
            self.info.title
        ));
        ctx.pop_state();
    }
}

/// `asset_size / 1e6` spoken as whole megabytes, or `None` when unknown.
fn megabytes(info: &UpdateInfo) -> Option<String> {
    let mb = info.asset_size as f64 / 1e6;
    (mb != 0.0).then(|| fmt_f(mb, 0))
}

impl Menu for UpdatePromptState {
    fn menu(&self) -> &MenuCore<Self> {
        &self.menu
    }

    fn menu_mut(&mut self) -> &mut MenuCore<Self> {
        &mut self.menu
    }

    fn announce_entry(&mut self, ctx: &mut GameContext) {
        let size = megabytes(&self.info)
            .map(|mb| format!(" The download is {mb} megabytes."))
            .unwrap_or_default();
        let text = format!(
            "Update available. {} is ready to install. You are running version {}.{size} {}",
            self.info.title,
            updater::spoken_version(version()),
            self.current_text(ctx)
        );
        ctx.say(&text);
    }

    fn build_items(&mut self, _ctx: &mut GameContext) -> Vec<MenuItem<Self>> {
        vec![
            MenuItem::new("Download and restart", |s: &mut Self, ctx| s.download(ctx)).help(
                "Download the update, then restart the game with the new version in place.",
            ),
            MenuItem::new("What's new", |s: &mut Self, ctx| s.whats_new(ctx))
                .help("Read the changes in this update, line by line."),
            MenuItem::new("Remind me later", |s: &mut Self, ctx| s.go_back(ctx)).help(
                "Dismiss this prompt. Ask again after returning to the main menu from a terminal or pickup facility, or the next time the game starts.",
            ),
            MenuItem::new("Skip this version", |s: &mut Self, ctx| s.skip(ctx)).help(
                "Do not ask about this update again. Later updates will still be offered.",
            ),
        ]
    }
}

impl_state_for_menu!(UpdatePromptState);

/// Line-by-line reader for the update's release notes.
pub struct WhatsNewState {
    pub info: UpdateInfo,
    pub notes: Vec<String>,
    pub line: i64,
}

impl WhatsNewState {
    pub fn new(info: UpdateInfo) -> Self {
        let notes = if info.notes.is_empty() {
            vec!["No change notes were provided.".to_string()]
        } else {
            info.notes.clone()
        };
        Self {
            info,
            notes,
            line: -1,
        }
    }
}

impl State for WhatsNewState {
    fn enter(&mut self, ctx: &mut GameContext) {
        ctx.say(&format!(
            "What's new in {}. {} lines. Up and Down arrows read line \
             by line, Enter reads everything, Escape goes back.",
            self.info.title,
            self.notes.len()
        ));
    }

    fn handle_event(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        let Some((key, _, _)) = event.key_down() else {
            return;
        };
        match key {
            Key::Escape => {
                ctx.audio.play("ui/menu_back");
                ctx.pop_state();
            }
            Key::Down => {
                self.line = (self.line + 1).min(self.notes.len() as i64 - 1);
                ctx.say(&self.notes[self.line as usize]);
            }
            Key::Up => {
                self.line = (self.line - 1).max(0);
                ctx.say(&self.notes[self.line as usize]);
            }
            Key::Return | Key::KpEnter | Key::Space => {
                ctx.say(&self.notes.join(" "));
            }
            _ => {}
        }
    }

    fn lines(&self, _ctx: &GameContext) -> Vec<String> {
        let mut out = vec![format!("What's new - {}", self.info.title), String::new()];
        for (i, text) in self.notes.iter().take(14).enumerate() {
            let marker = if i as i64 == self.line { "> " } else { "  " };
            out.push(format!("{marker}{text}"));
        }
        out
    }
}

/// The worker's shared outcome: written by the download thread, read by
/// `update` on the main thread.
#[derive(Default)]
struct DownloadOutcome {
    new_root: Option<PathBuf>,
    staging: Option<PathBuf>,
    error: Option<String>,
}

/// `updater.can_auto_apply` / `stash_for_manual_install`, injectable so a
/// test can stage an update that needs a manual install without a real
/// AppImage (the Python tests monkeypatched the module functions).
pub type AutoApplyProbe = Box<dyn Fn(&Path) -> bool>;
pub type StashHook = Box<dyn Fn(&Path) -> PathBuf>;

/// Downloads and stages the update, then restarts the game.
pub struct UpdateDownloadState {
    pub info: UpdateInfo,
    cancelled: Arc<AtomicBool>,
    done: Arc<AtomicBool>,
    outcome: Arc<Mutex<DownloadOutcome>>,
    /// 0..1, written by the worker thread (as f64 bits).
    progress: Arc<AtomicU64>,
    spoken_quarter: i64,
    finished: bool,
    started: bool,
    can_auto_apply: AutoApplyProbe,
    stash_for_manual_install: StashHook,
}

impl UpdateDownloadState {
    pub fn new(info: UpdateInfo) -> Self {
        Self {
            info,
            cancelled: Arc::new(AtomicBool::new(false)),
            done: Arc::new(AtomicBool::new(false)),
            outcome: Arc::new(Mutex::new(DownloadOutcome::default())),
            progress: Arc::new(AtomicU64::new(0f64.to_bits())),
            spoken_quarter: 0,
            finished: false,
            started: false,
            can_auto_apply: Box::new(|root| updater::can_auto_apply(root, &UpdaterEnv::current())),
            stash_for_manual_install: Box::new(|root| {
                updater::stash_for_manual_install(root, None)
            }),
        }
    }

    /// Test seam: a download that has already finished with `new_root`
    /// staged under `staging` (`state.staging = ...; state.new_root = ...;
    /// state.done.set()` in the Python tests), with the apply probes
    /// injected.
    pub fn finished_with(
        info: UpdateInfo,
        staging: PathBuf,
        new_root: PathBuf,
        can_auto_apply: AutoApplyProbe,
        stash_for_manual_install: StashHook,
    ) -> Self {
        let mut state = Self::new(info);
        {
            let mut outcome = state.outcome.lock().unwrap_or_else(|e| e.into_inner());
            outcome.staging = Some(staging);
            outcome.new_root = Some(new_root);
        }
        state.done.store(true, Ordering::SeqCst);
        state.started = true;
        state.can_auto_apply = can_auto_apply;
        state.stash_for_manual_install = stash_for_manual_install;
        state
    }

    pub fn progress(&self) -> f64 {
        f64::from_bits(self.progress.load(Ordering::Relaxed))
    }

    pub fn is_cancelled(&self) -> bool {
        self.cancelled.load(Ordering::SeqCst)
    }

    pub fn is_done(&self) -> bool {
        self.done.load(Ordering::SeqCst)
    }

    pub fn is_finished(&self) -> bool {
        self.finished
    }

    pub fn error(&self) -> Option<String> {
        self.outcome
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .error
            .clone()
    }

    pub fn new_root(&self) -> Option<PathBuf> {
        self.outcome
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .new_root
            .clone()
    }

    fn work(
        info: UpdateInfo,
        outcome: Arc<Mutex<DownloadOutcome>>,
        progress: Arc<AtomicU64>,
        cancelled: Arc<AtomicBool>,
        done: Arc<AtomicBool>,
    ) {
        let result = (|| -> Result<(), DownloadError> {
            let staging = updater::make_staging_dir()?;
            outcome.lock().unwrap_or_else(|e| e.into_inner()).staging = Some(staging.clone());
            let mut on_progress = |done: u64, total: u64| {
                if total > 0 {
                    progress.store((done as f64 / total as f64).to_bits(), Ordering::Relaxed);
                }
            };
            let archive =
                updater::download(&info, &staging, Some(&mut on_progress), Some(&cancelled))?;
            let new_root = updater::stage_update(&archive, &staging, &UpdaterEnv::current())?;
            outcome.lock().unwrap_or_else(|e| e.into_inner()).new_root = Some(new_root);
            Ok(())
        })();
        match result {
            Ok(()) | Err(DownloadError::Cancelled) => {}
            Err(DownloadError::Net(e)) => {
                log::warn!("Update download failed: {e:?}");
                outcome.lock().unwrap_or_else(|e| e.into_inner()).error = Some(format!(
                    "The download failed. {} Try again later.",
                    net::describe_error(&e)
                ));
            }
            Err(DownloadError::Io(e)) => {
                log::warn!("Update download failed: {e:?}");
                outcome.lock().unwrap_or_else(|e| e.into_inner()).error =
                    Some(format!("The download failed. {e} Try again later."));
            }
        }
        done.store(true, Ordering::SeqCst);
    }
}

impl State for UpdateDownloadState {
    fn enter(&mut self, ctx: &mut GameContext) {
        if self.started {
            return;
        }
        let size = megabytes(&self.info)
            .map(|mb| format!(", {mb} megabytes"))
            .unwrap_or_default();
        ctx.say(&format!(
            "Downloading {}{size}. The game will \
             restart when the download finishes. Press Escape to cancel.",
            self.info.title
        ));
        self.started = true;
        let info = self.info.clone();
        let outcome = Arc::clone(&self.outcome);
        let progress = Arc::clone(&self.progress);
        let cancelled = Arc::clone(&self.cancelled);
        let done = Arc::clone(&self.done);
        std::thread::Builder::new()
            .name("update-download".into())
            .spawn(move || Self::work(info, outcome, progress, cancelled, done))
            .ok();
    }

    fn update(&mut self, ctx: &mut GameContext, dt: f64) {
        ctx.update_music_rotation(dt);
        if self.finished {
            return;
        }
        let quarter = (self.progress() * 4.0) as i64;
        if quarter > self.spoken_quarter && quarter < 4 {
            self.spoken_quarter = quarter;
            ctx.say_with(format!("{} percent.", quarter * 25), Say::queued());
        }
        if !self.is_done() {
            return;
        }
        self.finished = true;
        let (new_root, staging, error) = {
            let outcome = self.outcome.lock().unwrap_or_else(|e| e.into_inner());
            (
                outcome.new_root.clone(),
                outcome.staging.clone(),
                outcome.error.clone(),
            )
        };
        if self.is_cancelled() {
            ctx.pop_state();
            return;
        }
        let Some(new_root) = new_root.filter(|_| error.is_none()) else {
            ctx.say(&error.unwrap_or_else(|| "The download failed.".to_string()));
            ctx.audio.play("ui/error");
            ctx.pop_state();
            return;
        };
        if !(self.can_auto_apply)(&new_root) {
            // e.g. an AppImage sitting in a folder this user cannot write
            // to: the swap would fail, so park the download somewhere
            // findable and say where instead of dead-ending on restart.
            let dest = (self.stash_for_manual_install)(&new_root);
            ctx.say(&format!(
                "Download complete, but this install cannot update itself \
                 automatically. The new version was saved to {}. \
                 Install it yourself, then restart the game.",
                dest.display()
            ));
            ctx.pop_state();
            return;
        }
        ctx.say(
            "Download complete. Restarting the game to finish the update. See you in a moment.",
        );
        let staging = staging.unwrap_or_else(|| new_root.clone());
        if let Err(e) = updater::apply_and_restart(&new_root, &staging) {
            log::warn!("Could not spawn the update apply script: {e}");
        }
        ctx.quit();
    }

    fn handle_event(&mut self, ctx: &mut GameContext, event: &InputEvent) {
        let Some((key, _, _)) = event.key_down() else {
            return;
        };
        if self.finished {
            return;
        }
        match key {
            Key::Escape => {
                self.cancelled.store(true, Ordering::SeqCst);
                ctx.say("Update cancelled.");
                ctx.audio.play("ui/menu_back");
                if self.is_done() {
                    self.finished = true;
                    ctx.pop_state();
                }
                // otherwise update() pops once the worker notices the flag
            }
            Key::Tab => {
                ctx.say(&format!(
                    "{} percent downloaded.",
                    fmt_f(self.progress() * 100.0, 0)
                ));
            }
            _ => {}
        }
    }

    fn lines(&self, _ctx: &GameContext) -> Vec<String> {
        vec![
            format!("Downloading {}", self.info.title),
            String::new(),
            format!("{} percent", fmt_f(self.progress() * 100.0, 0)),
            "Press Escape to cancel, Tab for progress.".to_string(),
        ]
    }
}
