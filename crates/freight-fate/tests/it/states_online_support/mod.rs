//! Shared rigging for the online/cloud state tests: the seams the Python
//! tests reached with `monkeypatch` (`OnlineIdentity.load`, `webbrowser.open`,
//! `online_presence.<call>`), as drop-guards that clear themselves, plus the
//! downcast helpers for reading a screen on the stack.
//!
//! Every override here is PER THREAD, and so is the save directory a
//! `TestApp` pins, which is what lets these tests run alongside each other
//! rather than queueing on one environment. Two things follow from that.
//! Install a guard on the same thread that will use it -- a worker the test
//! spawns sees none of them. And a guard is a convenience for asserting, not
//! a safety net: what stands between this suite and the live world is the set
//! of process-wide capabilities only the game's `main()` holds, so a
//! forgotten guard fails the test instead of reaching orinks.net (see
//! `browser_guard`, `network_guard`, `save_dir_guard` and
//! `secret_store_guard`).
//!
//! Declare the app first and the guards after, so Rust drops them in the
//! order that leaves nothing pointing at a dead app.

#![allow(dead_code)]

use std::sync::{Arc, Mutex};

use freight_fate::app::testing::TestApp;
use freight_fate::app::{share, GameContext, SharedState};
use freight_fate::cloud_saves::{CloudSaves, CloudSavesOptions};
use freight_fate::net::SharedTransport;
use freight_fate::online_presence::{IdentityStore, MemoryStore, OnlineIdentity};
use freight_fate::states::base::{InputEvent, Key, Menu, MenuItem, SimpleMenuState, State};
use freight_fate::states::online_states::{
    set_identity_store_override, set_online_transport_override, set_open_url_override,
};

/// `OnlineIdentity(driver_id="driver-testtest", driver_token="t" * 48)`.
pub fn identity() -> OnlineIdentity {
    OnlineIdentity::new("driver-testtest", &"t".repeat(48))
}

/// `monkeypatch.setattr(OnlineIdentity, "load", ...)`: an identity store over
/// a memory secret store in the app's data directory, holding `identity`
/// (or nothing). Cleared on drop.
pub struct IdentityGuard;

impl Drop for IdentityGuard {
    fn drop(&mut self) {
        set_identity_store_override(None);
    }
}

pub fn install_identity(app: &TestApp, identity: Option<&OnlineIdentity>) -> IdentityGuard {
    let store = IdentityStore::new(
        &app.data_dir.path().join("identity"),
        Some(MemoryStore::new()),
    );
    if let Some(identity) = identity {
        store
            .save(identity)
            .expect("the memory identity store saves");
    }
    set_identity_store_override(Some(Arc::new(store)));
    IdentityGuard
}

/// `monkeypatch.setattr(online_presence, "<call>", ...)`: route the menus'
/// one-shot orinks.net calls through `transport`. Cleared on drop.
pub struct TransportGuard;

impl Drop for TransportGuard {
    fn drop(&mut self) {
        set_online_transport_override(None);
    }
}

pub fn install_transport(transport: SharedTransport) -> TransportGuard {
    set_online_transport_override(Some(transport));
    TransportGuard
}

/// `monkeypatch.setattr(webbrowser, "open", ...)`: record every URL the game
/// asks a browser for and answer `opens`. Cleared on drop.
pub struct BrowserGuard {
    pub opened: Arc<Mutex<Vec<String>>>,
}

impl Drop for BrowserGuard {
    fn drop(&mut self) {
        set_open_url_override(None);
    }
}

pub fn install_browser(opens: bool) -> BrowserGuard {
    let opened = Arc::new(Mutex::new(Vec::new()));
    let log = Arc::clone(&opened);
    set_open_url_override(Some(Arc::new(move |url: &str| {
        log.lock().unwrap().push(url.to_string());
        opens
    })));
    BrowserGuard { opened }
}

impl BrowserGuard {
    pub fn opened(&self) -> Vec<String> {
        self.opened.lock().unwrap().clone()
    }
}

/// A clipboard that never takes the text (`write_clipboard_text` -> False).
pub struct RefusingClipboard;

impl freight_fate::app::Clipboard for RefusingClipboard {
    fn get_text(&self) -> Option<String> {
        None
    }
    fn set_text(&mut self, _text: &str) -> bool {
        false
    }
}

/// Replace the app's cloud service with one over `transport` (inline, so
/// its own worker never runs) carrying the test identity.
pub fn install_cloud(app: &mut TestApp, transport: SharedTransport, enabled: bool) -> CloudSaves {
    let service = CloudSaves::new(CloudSavesOptions {
        enabled,
        identity: Some(identity()),
        transport,
        threaded: false,
        data_dir: ff_core::models::profile::data_dir(),
        ..CloudSavesOptions::default()
    });
    app.ctx.services.cloud = service.clone();
    service
}

// -- reading a screen on the stack -----------------------------------------------------

/// Borrow the screen as its concrete type (`app.state` in Python).
pub fn with_state<T: State + 'static, R>(shared: &SharedState, f: impl FnOnce(&mut T) -> R) -> R {
    let mut state = shared.borrow_mut();
    let typed = state
        .as_any_mut()
        .downcast_mut::<T>()
        .unwrap_or_else(|| panic!("the state is not a {}", std::any::type_name::<T>()));
    f(typed)
}

/// Whether the shared state is a `T`.
pub fn is_state<T: State + 'static>(shared: &SharedState) -> bool {
    shared.borrow().as_any().is::<T>()
}

/// `[item.text for item in state.items]`.
pub fn labels<T: Menu + State>(shared: &SharedState, ctx: &GameContext) -> Vec<String> {
    let state = shared.borrow();
    let typed = state.as_any().downcast_ref::<T>().expect("state type");
    typed
        .menu()
        .items
        .iter()
        .map(|item| item.text(typed, ctx))
        .collect()
}

/// `[item.help_text for item in state.items]`.
pub fn helps<T: Menu + State>(shared: &SharedState, ctx: &GameContext) -> Vec<String> {
    let state = shared.borrow();
    let typed = state.as_any().downcast_ref::<T>().expect("state type");
    typed
        .menu()
        .items
        .iter()
        .map(|item| item.help_text(typed, ctx))
        .collect()
}

/// `state.items[state.index].text`.
pub fn current_label<T: Menu + State>(shared: &SharedState, ctx: &GameContext) -> String {
    let state = shared.borrow();
    let typed = state.as_any().downcast_ref::<T>().expect("state type");
    let core = typed.menu();
    core.items[core.index].text(typed, ctx)
}

/// `[(i.text, i.help_text) for i in state.build_items()]` on a screen that is
/// not on the stack.
pub fn built_rows<T: Menu + State>(state: &mut T, ctx: &mut GameContext) -> Vec<(String, String)> {
    let items = state.build_items(ctx);
    items
        .iter()
        .map(|item| (item.text(state, ctx), item.help_text(state, ctx)))
        .collect()
}

/// `app.state.handle_event(key_event(key))` through the app's dispatch.
pub fn press(app: &mut TestApp, key: Key) {
    app.dispatch_to_state(&InputEvent::key(key));
}

/// Arrow down until the current row starts with `prefix`.
pub fn move_to<T: Menu + State>(app: &mut TestApp, shared: &SharedState, prefix: &str) {
    for _ in 0..32 {
        if current_label::<T>(shared, &app.ctx).starts_with(prefix) {
            return;
        }
        press(app, Key::Down);
    }
    panic!("no row starting with {prefix:?}");
}

/// Push a state and hand back its shared handle.
pub fn push<S: State + 'static>(app: &mut TestApp, state: S) -> SharedState {
    let shared = share(state);
    app.push_shared(shared.clone());
    shared
}

/// Everything said on the main channel, space-joined.
pub fn said(app: &TestApp) -> String {
    app.main_lines().join(" ")
}

/// A plain screen to sit under the one being tested, so a pop or a replace
/// has somewhere to land and never empties the stack.
pub fn base_state() -> SimpleMenuState {
    SimpleMenuState::new(
        "Base",
        vec![MenuItem::new(
            "Back",
            |_: &mut SimpleMenuState, ctx: &mut GameContext| ctx.pop_state(),
        )],
    )
}
