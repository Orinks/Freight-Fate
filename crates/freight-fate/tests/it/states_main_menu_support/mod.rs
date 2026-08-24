//! Shared rigging for the `states_main_menu*` / `states_*` integration
//! tests: drive a menu on the headless app the way the Python tests drove
//! `app.state.handle_event(key_event(...))`, read its rows, and write the
//! legacy save shapes the career-list tests need.
#![allow(dead_code)]

use std::path::{Path, PathBuf};

use ff_core::models::profile::{decode_save_bytes, encode_save_bytes, signature_for, Profile};
use freight_fate::app::testing::TestApp;
use freight_fate::app::GameContext;
use freight_fate::states::base::{InputEvent, Key, Menu, SimpleMenuState};
use serde_json::{json, Map, Value};

/// Run `f` with the active state downcast to `T`.
pub fn with_state<T: 'static, R>(app: &TestApp, f: impl FnOnce(&T, &GameContext) -> R) -> R {
    let state = app.state().expect("a state on the stack");
    let state = state.borrow();
    let t = state
        .as_any()
        .downcast_ref::<T>()
        .unwrap_or_else(|| panic!("active state is not a {}", std::any::type_name::<T>()));
    f(t, &app.ctx)
}

/// Run `f` with the active state downcast mutably to `T`.
pub fn with_state_mut<T: 'static, R>(
    app: &mut TestApp,
    f: impl FnOnce(&mut T, &mut GameContext) -> R,
) -> R {
    let state = app.state().expect("a state on the stack");
    let mut state = state.borrow_mut();
    let t = state
        .as_any_mut()
        .downcast_mut::<T>()
        .unwrap_or_else(|| panic!("active state is not a {}", std::any::type_name::<T>()));
    let result = f(t, &mut app.ctx);
    drop(state);
    app.ctx.run_deferred();
    result
}

/// Whether the active state is a `T`.
pub fn is<T: 'static>(app: &TestApp) -> bool {
    let state = app.state().expect("a state on the stack");
    let state = state.borrow();
    state.as_any().downcast_ref::<T>().is_some()
}

/// Whether the active state is the `todo_state` placeholder for `name`.
pub fn is_placeholder(app: &TestApp, name: &str) -> bool {
    if !is::<SimpleMenuState>(app) {
        return false;
    }
    with_state::<SimpleMenuState, _>(app, |s, _| {
        s.menu.title == format!("{name} (not ported yet)")
    })
}

/// The rows of the active `T` menu, as spoken.
pub fn labels<T: Menu + 'static>(app: &TestApp) -> Vec<String> {
    with_state::<T, _>(app, |t, ctx| {
        t.menu()
            .items
            .iter()
            .map(|item| item.text(t, ctx))
            .collect()
    })
}

/// The rows of the active `T` menu with their help.
pub fn labels_and_help<T: Menu + 'static>(app: &TestApp) -> Vec<(String, String)> {
    with_state::<T, _>(app, |t, ctx| {
        t.menu()
            .items
            .iter()
            .map(|item| (item.text(t, ctx), item.help_text(t, ctx)))
            .collect()
    })
}

pub fn current_label<T: Menu + 'static>(app: &TestApp) -> String {
    with_state::<T, _>(app, |t, ctx| {
        let core = t.menu();
        core.items[core.index].text(t, ctx)
    })
}

pub fn current_help<T: Menu + 'static>(app: &TestApp) -> String {
    with_state::<T, _>(app, |t, ctx| t.current_help(ctx))
}

pub fn index<T: Menu + 'static>(app: &TestApp) -> usize {
    with_state::<T, _>(app, |t, _| t.menu().index)
}

pub fn set_index<T: Menu + 'static>(app: &mut TestApp, index: usize) {
    with_state_mut::<T, _>(app, |t, _| t.menu_mut().index = index);
}

pub fn key(app: &mut TestApp, key: Key) {
    app.dispatch_to_state(&InputEvent::key(key));
}

pub fn typed(app: &mut TestApp, ch: char) {
    app.dispatch_to_state(&InputEvent::typed(ch));
}

/// Arrow down to the row starting with `prefix` and press Enter.
pub fn select<T: Menu + 'static>(app: &mut TestApp, prefix: &str) {
    move_to::<T>(app, prefix);
    key(app, Key::Return);
}

/// Arrow down to the row starting with `prefix`.
pub fn move_to<T: Menu + 'static>(app: &mut TestApp, prefix: &str) {
    let rows = labels::<T>(app).len();
    for _ in 0..=rows {
        if current_label::<T>(app).starts_with(prefix) {
            return;
        }
        key(app, Key::Down);
    }
    panic!(
        "no row starting with {prefix:?}; saw {:?}",
        labels::<T>(app)
    );
}

pub fn read_save(path: &Path) -> Map<String, Value> {
    decode_save_bytes(&std::fs::read(path).unwrap()).unwrap().0
}

pub fn write_packed(path: &Path, data: &Map<String, Value>) {
    std::fs::write(path, encode_save_bytes(data)).unwrap();
}

/// A save exactly as a current 1.8-line build leaves it.
pub fn write_1_8_save(name: &str) -> PathBuf {
    let p = Profile::named(name);
    let path = p.save().unwrap();
    let mut data = read_save(&path);
    data.remove("created_line");
    data.remove("_signature");
    data.remove("_signature_version");
    data.insert("version".into(), json!(5));
    data.insert("_signature_version".into(), json!(1));
    let signature = signature_for(&data, None);
    data.insert("_signature".into(), json!(signature));
    write_packed(&path, &data);
    path
}
