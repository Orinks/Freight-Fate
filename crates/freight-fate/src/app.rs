//! Application shell: the window, the state stack, and shared services
//! (port of `freight_fate/app.py`, with `__init__.py`'s version lookup and
//! `__main__.py`'s entry point).
//!
//! * [`GameContext`] (`app::context`) -- the services every state gets, and
//!   the state stack itself.
//! * `app::speech_delivery` -- `say` / `say_event`, the ladder, the pacer,
//!   the duck, the transcript.
//! * `app::sdl_shell` -- the SDL window, event translation, clipboard.
//! * `app::logging` -- session log configuration.
//! * `app::testing` -- the headless test rig later state ports reuse.

use std::sync::{Arc, OnceLock};
use std::time::{Duration, Instant};

use ff_core::assets_pack::prefetch_default as prefetch_sound_pack;
use ff_core::data::world::get_world;
use ff_core::message_log::MessageLog;
use ff_core::models::economy::Economy;
use ff_core::models::profile::{self as profile_module, data_dir};
use ff_core::settings::Settings;

use crate::audio::{Audio, AudioEngine, NullBackend};
use crate::cloud_saves::{CloudSaves, CloudSavesOptions};
use crate::controller::ControllerManager;
use crate::discord_presence::{DiscordPresence, DiscordPresenceOptions};
use crate::online_journal::JournalOutbox;
use crate::online_presence::{IdentityStore, OnlinePresence, OnlinePresenceOptions};
use crate::speech::{NullSpeech, Speech, SpeechSink};
use crate::states::base::{InputEvent, State};
use crate::states::driving::DrivingState;
use crate::states::main_menu::ConfirmQuitState;

pub mod boot_timing;
pub mod context;
pub mod logging;
pub mod sdl_shell;
pub mod speech_delivery;
pub mod testing;

pub use context::{
    share, Clipboard, ContextParts, GameContext, HeldKeys, MemoryClipboard, Services, SharedState,
};
pub use logging::{active_log_path, configure_logging};
pub use speech_delivery::{IntoSpoken, Say, SayEvent, Spoken, TRANSCRIPT_TARGET};

use sdl_shell::SdlShell;

pub const WINDOW_SIZE: (u32, u32) = (900, 640);
pub const FPS: u32 = 60;
pub const BG_COLOR: (u8, u8, u8) = (12, 12, 16);
pub const TEXT_COLOR: (u8, u8, u8) = (235, 235, 225);
pub const HILIGHT_COLOR: (u8, u8, u8) = (255, 210, 90);

/// The game's version (`freight_fate.__version__`): the version
/// `tools/build_release.py` stamped into `build_info.json` beside the
/// executable when there is one, else this crate's.
pub fn version() -> &'static str {
    static VERSION: OnceLock<String> = OnceLock::new();
    VERSION.get_or_init(|| baked_version().unwrap_or_else(|| env!("CARGO_PKG_VERSION").to_string()))
}

/// `package_version` from the `build_info.json` next to the executable.
fn baked_version() -> Option<String> {
    let exe = std::env::current_exe().ok()?;
    let info = std::fs::read_to_string(exe.parent()?.join("build_info.json")).ok()?;
    let data: serde_json::Value = serde_json::from_str(&info).ok()?;
    data.get("package_version")?
        .as_str()
        .filter(|v| !v.is_empty())
        .map(str::to_string)
}

/// `pygame.time.Clock`: `tick(fps)` blocks to cap the frame rate and
/// returns the seconds since the previous tick.
pub struct FrameClock {
    last: Instant,
    /// Whether `tick` sleeps to hold the frame rate (a harness driving
    /// `frame()` itself never calls `tick`).
    pub limit: bool,
}

impl FrameClock {
    pub fn new(limit: bool) -> Self {
        Self {
            last: Instant::now(),
            limit,
        }
    }

    pub fn tick(&mut self, fps: u32) -> f64 {
        if self.limit {
            let frame = Duration::from_secs_f64(1.0 / fps as f64);
            let elapsed = self.last.elapsed();
            if elapsed < frame {
                std::thread::sleep(frame - elapsed);
            }
        }
        let now = Instant::now();
        let dt = now.duration_since(self.last).as_secs_f64();
        self.last = now;
        dt
    }
}

/// What `App::run` pushes first: `MainMenuState` once `states::main_menu`
/// is ported; until then a one-row placeholder that quits, so `--smoke` and
/// the headless loop have a screen to stand on.
pub type InitialState = Box<dyn FnOnce(&mut GameContext) -> SharedState>;

fn placeholder_main_menu(_ctx: &mut GameContext) -> SharedState {
    share(crate::states::main_menu::MainMenuState::new())
}

pub struct App {
    pub ctx: GameContext,
    shell: Option<SdlShell>,
    clock: FrameClock,
    initial_state: Option<InitialState>,
}

impl App {
    /// The windowed game: SDL, the vendored sound pack prefetch, speech via
    /// Prism, BASS audio, every online service, the controller subsystem.
    pub fn new() -> Result<App, String> {
        // Opt PS4/PS5 pads into HIDAPI rumble so their motors work like Xbox
        // pads. Must be set before SDL init; Xbox/XInput needs no flag.
        for (name, value) in [
            ("SDL_JOYSTICK_HIDAPI_PS4_RUMBLE", "1"),
            ("SDL_JOYSTICK_HIDAPI_PS5_RUMBLE", "1"),
        ] {
            if std::env::var_os(name).is_none() {
                std::env::set_var(name, value);
            }
        }
        if std::env::var_os("FREIGHT_FATE_NO_SPEECH").is_some_and(|v| !v.is_empty()) {
            std::env::set_var("SDL_VIDEODRIVER", "dummy");
            std::env::set_var("SDL_AUDIODRIVER", "dummy");
        }
        // Kick the ~225MB sound pack's read-and-unmask onto a background
        // thread before anything else: it has no dependency on SDL or the
        // world data that follows, so it overlaps the rest of startup
        // instead of stalling the first sound played.
        prefetch_sound_pack();
        let shell = SdlShell::new(&format!("Freight Fate {}", version()))?;
        boot_timing::mark("window");
        let speech: Box<dyn SpeechSink> = Box::new(Speech::new());
        boot_timing::mark("speech");
        let audio: Box<dyn Audio> = Box::new(AudioEngine::new());
        boot_timing::mark("audio");
        Ok(Self::build(Some(shell), speech, audio))
    }

    /// The headless app: no window, no SDL, the null audio backend, the
    /// given speech sink (a `CaptureSpeech` in tests and the harness, a
    /// `NullSpeech` for `--headless`), the same `GameContext` otherwise.
    pub fn new_headless(speech: Box<dyn SpeechSink>) -> App {
        let audio: Box<dyn Audio> =
            Box::new(AudioEngine::with_backend(Box::new(NullBackend::new())));
        Self::new_headless_with(speech, audio)
    }

    /// A headless app on a caller-built audio engine (BASS on the no-sound
    /// device, a recorder, ...).
    pub fn new_headless_with(speech: Box<dyn SpeechSink>, audio: Box<dyn Audio>) -> App {
        Self::build(None, speech, audio)
    }

    fn build(shell: Option<SdlShell>, speech: Box<dyn SpeechSink>, audio: Box<dyn Audio>) -> App {
        let settings = Settings::load();
        boot_timing::mark("settings");
        let message_log = MessageLog::new();
        let world = get_world();
        boot_timing::mark("world");
        let economy = Economy::default();
        let presence = DiscordPresence::new(DiscordPresenceOptions {
            enabled: settings.discord_presence,
            ..Default::default()
        });
        // identity is loaded unconditionally, not gated on whether any
        // online setting is currently on: OnlinePresence/CloudSaves.
        // set_enabled() both refuse to turn on without an identity already
        // in hand, and nothing re-loads it when a player flips a setting on
        // mid-session -- only the account-link flow (adopt_online_identity)
        // does that. A player who linked an account and then turned every
        // online setting off must still be able to turn one back on later
        // without re-pasting credentials.
        let data_dir = data_dir();
        let store = IdentityStore::platform(&data_dir);
        let identity = store.load();
        boot_timing::mark("driver identity");
        let online = OnlinePresence::new(OnlinePresenceOptions {
            enabled: settings.online_presence,
            identity: identity.clone(),
            ..Default::default()
        });
        let cloud = CloudSaves::new(CloudSavesOptions {
            enabled: settings.cloud_saves,
            identity: identity.clone(),
            data_dir: data_dir.clone(),
            ..Default::default()
        });
        let journal = JournalOutbox::new(
            identity.clone(),
            settings.online_presence,
            &store.path().with_file_name("online-outbox.json"),
        );
        // Mastodon shares ride the same durable-outbox machinery but keep
        // their own file and enabled flag: posting to the player's own
        // Mastodon account is a separate consent from public Profile
        // sharing.
        let mastodon = JournalOutbox::new(
            identity,
            settings.mastodon_sharing,
            &store.path().with_file_name("online-mastodon-outbox.json"),
        );
        // Every profile save, wherever it happens, queues a cloud backup.
        let backup = cloud.clone();
        profile_module::set_save_listener(Some(Arc::new(
            move |profile: &profile_module::Profile| {
                backup.queue_backup(&profile.name, serde_json::Value::Object(profile.to_dict()));
            },
        )));
        boot_timing::mark("online services");
        let controller = match &shell {
            Some(shell) => ControllerManager::new(
                settings.controller_enabled,
                settings.haptics_enabled,
                Some(crate::controller::sdl::sdl_factory(shell.sdl.clone())),
            ),
            None => {
                ControllerManager::detached(settings.controller_enabled, settings.haptics_enabled)
            }
        };
        boot_timing::mark("controller");
        let clipboard: Box<dyn Clipboard> = match &shell {
            Some(shell) => Box::new(shell.clipboard()),
            None => Box::new(MemoryClipboard::default()),
        };
        let mut ctx = GameContext::new(ContextParts {
            speech,
            audio,
            controller,
            settings,
            world,
            economy,
            message_log,
            clipboard,
            services: Services {
                presence,
                online,
                cloud,
                journal,
                mastodon,
            },
        });
        ctx.apply_volumes();
        ctx.apply_speech();
        boot_timing::mark("volumes and voice");
        App {
            ctx,
            shell,
            clock: FrameClock::new(true),
            initial_state: None,
        }
    }

    /// Choose the screen `run` starts on (the main menu, once ported).
    pub fn set_initial_state(&mut self, factory: InitialState) {
        self.initial_state = Some(factory);
    }

    pub fn is_headless(&self) -> bool {
        self.shell.is_none()
    }

    // -- state stack (forwarders; the stack lives on the context) ----------------------

    pub fn state(&self) -> Option<SharedState> {
        self.ctx.state()
    }

    pub fn states(&self) -> Vec<SharedState> {
        self.ctx.states()
    }

    pub fn running(&self) -> bool {
        self.ctx.running
    }

    pub fn set_running(&mut self, running: bool) {
        self.ctx.running = running;
    }

    pub fn push_state<S: State + 'static>(&mut self, state: S) {
        self.ctx.push_state(state);
        self.ctx.run_deferred();
    }

    pub fn push_state_with<S: State + 'static>(&mut self, state: S, should_enter: bool) {
        self.ctx.push_state_with(state, should_enter);
        self.ctx.run_deferred();
    }

    pub fn push_shared(&mut self, state: SharedState) {
        self.ctx.push_shared(state);
        self.ctx.run_deferred();
    }

    pub fn pop_state(&mut self) {
        self.ctx.pop_state();
        self.ctx.run_deferred();
    }

    pub fn pop_state_with(&mut self, should_exit: bool, reentry: bool) {
        self.ctx.pop_state_with(should_exit, reentry);
        self.ctx.run_deferred();
    }

    pub fn replace_state<S: State + 'static>(&mut self, state: S) {
        self.ctx.replace_state(state);
        self.ctx.run_deferred();
    }

    pub fn replace_state_with<S: State + 'static>(
        &mut self,
        state: S,
        should_exit: bool,
        reentry: bool,
    ) {
        self.ctx.replace_state_with(state, should_exit, reentry);
        self.ctx.run_deferred();
    }

    pub fn reset_to<S: State + 'static>(&mut self, state: S) {
        self.ctx.reset_to(state);
        self.ctx.run_deferred();
    }

    pub fn reset_to_with<S: State + 'static>(
        &mut self,
        state: S,
        should_exit: bool,
        reentry: bool,
    ) {
        self.ctx.reset_to_with(state, should_exit, reentry);
        self.ctx.run_deferred();
    }

    // -- dispatch ---------------------------------------------------------------------------

    /// Feed a controller event to the manager, then to the active state.
    ///
    /// The manager updates its cached axis/modifier/hot-plug state first and
    /// reports whether the event is an accepted button press for the bound
    /// controller; only those reach the state, so a duplicate from a pad
    /// that enumerates twice can never fire an action a second time.
    pub fn dispatch_controller(&mut self, event: &InputEvent) {
        let forward = self.ctx.controller.process_event(event);
        if forward && self.ctx.controller.active() {
            if let Some(state) = self.ctx.state() {
                state.borrow_mut().handle_controller(&mut self.ctx, event);
                self.ctx.run_deferred();
            }
        }
    }

    /// Hand a keyboard/window event to the active state.
    ///
    /// Message review gets first refusal on every key press, which is what
    /// makes the review controls work on every screen instead of only the
    /// ones that remembered to call `handle_message_review`. A state that
    /// takes typed text declines them itself.
    pub fn dispatch_to_state(&mut self, event: &InputEvent) {
        let Some(state) = self.ctx.state() else {
            return;
        };
        if event.key_down().is_some() {
            self.ctx.controller.note_keyboard();
            let consumed = state
                .borrow_mut()
                .handle_message_review(&mut self.ctx, event);
            if consumed {
                self.ctx.run_deferred();
                return;
            }
        }
        state.borrow_mut().handle_event(&mut self.ctx, event);
        self.ctx.run_deferred();
    }

    /// Alt+F4 and the window's close button ask, they do not just go.
    ///
    /// Closing the window used to end the process on the spot. Mid-drive that
    /// is destructive and silent: saving happens only at stops, so the leg
    /// being driven is gone and the save still points at the last stop.
    /// Darren lost two routes to a mis-hit Alt+F4 and asked for the same gate
    /// Escape already puts in front of quitting (2026-08-22).
    ///
    /// The second close request is obeyed without further argument. A
    /// confirmation the player cannot get past would be a worse bug than the
    /// one it fixes -- if speech has dropped, or the dialog is somehow
    /// unreachable, Alt+F4 twice always closes the game.
    pub fn handle_close_request(&mut self) {
        let already_asking = self
            .ctx
            .state()
            .is_some_and(|state| state.borrow().as_any().is::<ConfirmQuitState>());
        if already_asking {
            self.ctx.running = false;
            return;
        }
        let unsaved = self.drive_in_progress();
        self.push_state(ConfirmQuitState::with_unsaved_drive(unsaved));
    }

    /// Whether a leg is being driven right now, saved nowhere.
    pub fn drive_in_progress(&self) -> bool {
        self.ctx
            .states()
            .iter()
            .any(|state| state.borrow().as_any().is::<DrivingState>())
    }

    /// One event through the loop's switch: focus, quit, controller, state.
    pub fn handle_event(&mut self, event: &InputEvent) {
        match event {
            InputEvent::WindowFocusGained => {
                // Switching screen readers happens outside the game;
                // re-check speech the moment the player comes back.
                self.ctx.speech.request_refresh();
            }
            InputEvent::Quit => self.handle_close_request(),
            InputEvent::KeyDown { key, mods, .. } => {
                self.ctx.input.press(*key, *mods);
                self.dispatch_to_state(event);
            }
            InputEvent::KeyUp { key, mods } => {
                self.ctx.input.release(*key, *mods);
                self.dispatch_to_state(event);
            }
            event if event.is_controller_event() => self.dispatch_controller(event),
            event => self.dispatch_to_state(event),
        }
    }

    /// The per-frame work after the events: controller repeats, the speech
    /// poll, disconnects, cloud notices, audio fades, the duck, the state
    /// update, presence, the achievement notice.
    pub fn tick(&mut self, dt: f64) {
        // Auto-repeat (held D-pad left/right) and analog smoothing.
        // Synthetic repeats go straight to the state (bypassing the manager,
        // whose press state must not be reset) and only where the menu
        // wants adjust-repeat -- driving keeps D-pad discrete.
        let repeats = self.ctx.controller.tick(dt);
        if let Some(state) = self.ctx.state() {
            if state.borrow().wants_controller_repeat() {
                for event in &repeats {
                    state.borrow_mut().handle_controller(&mut self.ctx, event);
                    self.ctx.run_deferred();
                }
            }
        }
        // Reconnect speech if the player's screen reader changed.
        self.ctx.speech.poll(dt);
        if self.ctx.controller.take_disconnect() {
            self.ctx.say(
                "Controller disconnected. You can keep playing with the \
                 keyboard, or reconnect your controller.",
            );
            if let Some(state) = self.ctx.state() {
                state.borrow_mut().on_controller_disconnect(&mut self.ctx);
                self.ctx.run_deferred();
            }
        }
        // Cloud backup refusals speak wherever the player is -- driving or
        // in menus -- not only on the terminal's Save game item: the worker
        // thread queues them and this loop delivers, queued on the normal
        // announcement channel so a backup notice never cuts off urgent
        // driving speech.
        for line in self.ctx.services.cloud.take_announcements() {
            self.ctx.say_with(line, Say::queued());
        }
        self.ctx.audio.update(dt); // advance time-based audio fades
        self.ctx.update_speech_duck(); // restore the mix after speech
        if let Some(state) = self.ctx.state() {
            state.borrow_mut().update(&mut self.ctx, dt);
            self.ctx.run_deferred();
            let (presence, online) = {
                let s = state.borrow();
                (s.presence(&self.ctx), s.online_presence(&self.ctx))
            };
            self.ctx.services.presence.update(presence);
            self.ctx.services.online.update(online);
        }
        if self.ctx.achievement_notice_timer > 0.0 {
            self.ctx.achievement_notice_timer = (self.ctx.achievement_notice_timer - dt).max(0.0);
            if self.ctx.achievement_notice_timer == 0.0 {
                self.ctx.achievement_notice.clear();
            }
        }
    }

    /// The lines the window would show this frame: the state's, capped at
    /// 18 (16 + a blank + the achievement notice while one shows).
    pub fn visible_lines(&self) -> Vec<String> {
        let Some(state) = self.ctx.state() else {
            return Vec::new();
        };
        let base = state.borrow().lines(&self.ctx);
        let mut lines: Vec<String> = if self.ctx.achievement_notice.is_empty() {
            base.into_iter().take(18).collect()
        } else {
            let mut lines: Vec<String> = base.into_iter().take(16).collect();
            lines.push(String::new());
            lines.push(self.ctx.achievement_notice.clone());
            lines
        };
        lines.truncate(18);
        lines
    }

    pub fn render(&mut self) {
        let lines = self.visible_lines();
        if let Some(shell) = self.shell.as_mut() {
            shell.render(&lines);
        }
    }

    /// One whole frame: pump events, tick, render. `dt` is the frame time.
    pub fn frame(&mut self, dt: f64) {
        let events = match self.shell.as_mut() {
            Some(shell) => match shell.poll() {
                Some(events) => events,
                None => {
                    log::error!(
                        "event pump failed (controller {}); skipping this batch",
                        if self.ctx.controller.connected() {
                            "connected"
                        } else {
                            "disconnected"
                        }
                    );
                    Vec::new()
                }
            },
            None => Vec::new(),
        };
        for event in &events {
            self.handle_event(event);
        }
        self.tick(dt);
        self.render();
    }

    /// Main loop. `max_frames` runs that many frames then exits cleanly;
    /// used by the `--smoke` build check.
    pub fn run(&mut self, max_frames: Option<u32>) {
        self.ctx.running = true;
        let factory = self
            .initial_state
            .take()
            .unwrap_or_else(|| Box::new(placeholder_main_menu));
        let first = factory(&mut self.ctx);
        self.push_shared(first);
        boot_timing::mark("first screen");
        self.ctx.services.presence.start(); // after init; never blocks if Discord is absent
        self.ctx.services.online.start(); // opt-in drivers board; dormant unless confirmed
        self.ctx.services.cloud.start(); // opt-in save backup; dormant unless confirmed
        boot_timing::mark("background services started");
        let mut frames = 0u32;
        while self.ctx.running {
            let dt = self.clock.tick(FPS);
            self.frame(dt);
            frames += 1;
            if frames == 1 {
                boot_timing::mark("first frame");
            }
            if max_frames.is_some_and(|max| frames >= max) {
                self.ctx.running = false;
            }
        }
        self.shutdown();
    }

    pub fn shutdown(&mut self) {
        // Through the guard, not straight to disk: the quit-time save is how
        // a sandboxed playtest session leaked its whole run onto the real
        // career (owner-found live: the Denver snow run persisted at quit
        // despite the sandbox holding for the entire drive).
        self.ctx.save_profile();
        if let Err(e) = self.ctx.settings.save() {
            log::warn!("Could not save settings: {e}");
        }
        boot_timing::mark("quit: saved");
        self.ctx.services.presence.shutdown();
        boot_timing::mark("quit: rich presence");
        self.ctx.services.online.shutdown();
        boot_timing::mark("quit: drivers board");
        self.ctx.services.cloud.shutdown(); // flushes the final save's backup, bounded
        boot_timing::mark("quit: cloud backup");
        profile_module::set_save_listener(None);
        self.ctx.controller.shutdown();
        boot_timing::mark("quit: controller");
        self.ctx.audio.shutdown();
        boot_timing::mark("quit: audio");
        self.ctx.speech.shutdown();
        boot_timing::mark("quit: speech");
        self.shell = None; // pygame.quit()
        boot_timing::mark("quit: window");
    }
}

/// The `--smoke` build check: prove world data loads, sound assets are
/// readable, and the deepest load path (continuing a career) finds every
/// baked runtime data file -- a missing file must fail the build here, not
/// a player's first Continue career.
pub fn smoke_checks() -> Result<(), String> {
    let _ = get_world();
    crate::audio::verify_sound_assets().map_err(|e| format!("smoke: {e}"))?;
    if ff_core::data::buffs::buff_catalog().is_empty() {
        return Err("smoke: buff catalog is empty".to_string());
    }
    if ff_core::data::curves::leg_curves("aberdeen_sd_us:pierre_sd_us", true).is_empty() {
        return Err("smoke: curve shard is empty".to_string());
    }
    let approaches = ff_core::data::world_local_data::load_facility_approaches(
        &ff_core::data::data_resources::data_path("facility_approaches.json"),
    )
    .map_err(|e| format!("smoke: {e}"))?;
    if approaches.is_empty() {
        return Err("smoke: facility approaches are empty".to_string());
    }
    ff_core::radio::load_radio_catalog(ff_core::data::data_resources::data_root())
        .map_err(|e| format!("smoke: {e}"))?;
    // And that the online driver token can still reach the platform secret
    // store, which a packaged build can lose silently.
    let (store_ok, store_detail) = crate::online_presence::secret_store_report();
    log::info!("Secret store: {store_detail}");
    if !store_ok {
        return Err(format!(
            "Secret store unreachable in this build: {store_detail}"
        ));
    }
    Ok(())
}

/// Command-line switches `main` understands.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct CliOptions {
    /// CI: boot, render a few frames, exit 0.
    pub smoke: bool,
    /// No window: the headless app with the null speech sink.
    pub headless: bool,
    /// The controller diagnostics tool instead of the game.
    pub controller_diagnostics: bool,
}

impl CliOptions {
    pub fn parse<I: IntoIterator<Item = String>>(args: I) -> Self {
        let mut options = Self::default();
        for arg in args {
            match arg.as_str() {
                "--smoke" => options.smoke = true,
                "--headless" => options.headless = true,
                "--controller-diagnostics" => options.controller_diagnostics = true,
                _ => {}
            }
        }
        options
    }
}

/// `freight_fate.app.main()`: the process entry, returning the exit code.
pub fn main_with(options: CliOptions) -> i32 {
    configure_logging();
    boot_timing::mark("start up");
    if options.controller_diagnostics {
        return crate::controller::diagnostics::run_controller_diagnostics();
    }
    let mut guard = crate::single_instance::SingleInstanceGuard::new();
    if !guard.acquire() {
        log::warn!("Freight Fate is already running.");
        return 0;
    }
    boot_timing::mark("single instance check");
    let code = run_game(&options);
    guard.release();
    boot_timing::mark("quit: done");
    code
}

fn run_game(options: &CliOptions) -> i32 {
    let max_frames = options.smoke.then_some(5);
    if options.smoke {
        if let Err(e) = smoke_checks() {
            log::error!("Fatal error: {e}");
            return 1;
        }
        boot_timing::mark("smoke checks");
    }
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let mut app = if options.headless {
            App::new_headless(Box::new(NullSpeech))
        } else {
            match App::new() {
                Ok(app) => app,
                Err(e) => {
                    log::error!("Fatal error: {e}");
                    return 1;
                }
            }
        };
        app.run(max_frames);
        0
    }));
    match result {
        Ok(code) => code,
        Err(_) => {
            log::error!("Fatal error");
            1
        }
    }
}
