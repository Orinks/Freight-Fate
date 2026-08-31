//! A data directory a manual playtest can be reckless in (port of
//! `tools/playtest_sandbox.py`).
//!
//! A playtest career is a throwaway: it exists to reach one weigh station or
//! one hairpin, it gets abandoned mid-load, and it is deleted the moment the
//! thing it was made for has been heard. None of that belongs on the owner's
//! account -- but a source checkout saves into `saves/` next to the game,
//! which IS the real account: the driver identity in `online.json`, the
//! cloud ledger in `cloud_saves.json`, and twenty-odd careers that have been
//! backing themselves up to the site all along.
//!
//! This puts a playtest somewhere else. It builds a sandbox data directory,
//! seeds it with the owner's real *settings* -- so the drive still
//! reproduces what a player would actually get -- and deliberately leaves
//! the identity behind. With no `online.json` the game has no driver:
//! the identity load returns nothing, and every cloud backup, presence
//! heartbeat and profile update is a branch that is never taken. The
//! publishing settings are turned off in the copy as well, so the sandbox
//! stays silent even if somebody later signs it in on purpose to test the
//! online screens.
//!
//! Careers are copied in by default, because most of what is worth
//! playtesting needs a driver who has already got somewhere: the
//! weigh-station transponder arrives at level four, the experience check
//! reads out a level. They are copies. Wreck them.

use std::path::{Path, PathBuf};

use serde_json::{Map, Value};

use ff_core::settings::{game_root, DATA_DIR_ENV};

/// `saves-playtest` beside the game.
pub fn default_sandbox() -> PathBuf {
    game_root().join("saves-playtest")
}

/// The real save directory a sandbox is seeded from.
pub fn real_saves() -> PathBuf {
    game_root().join("saves")
}

/// Where a live playtest announces itself for `tools/playtest_watch.py`.
pub fn session_file() -> PathBuf {
    game_root().join("logs").join("playtest-session.json")
}

/// Anything carrying the driver identity, or the cloud bookkeeping that
/// hangs off it. Copying one of these into a sandbox is exactly how a
/// throwaway career would reach the real account, so the seeding step names
/// them rather than hoping a glob never matches.
pub const IDENTITY_NAMES: [&str; 6] = [
    "online.json",
    "online.token",
    "cloud_saves.json",
    "meaningful_play.json",
    "online-outbox.json",
    "online-mastodon-outbox.json",
];

/// The settings that publish. A sandbox with no identity cannot reach the
/// site at all, so this is a second lock on the same door -- cheap, and it
/// is the one that still holds if a session deliberately signs the sandbox
/// in.
pub const OFFLINE_SETTINGS: [&str; 4] = [
    "cloud_saves",
    "online_presence",
    "online_services",
    "mastodon_sharing",
];

/// `.ffsave` is the signed current format. The `.json.bak` and
/// `.json.invalid` leftovers beside them are not careers the game will load,
/// so a sandbox does not want them cluttering its career list.
pub const CAREER_SUFFIX: &str = ".ffsave";

/// True for a file that would carry the real account into a sandbox.
///
/// Matches the backup spellings too (`online.json.pre-clerk.bak`): a stale
/// identity is still an identity, and the loader reads a driver id out of
/// whichever file it is pointed at.
pub fn is_identity(path: &Path) -> bool {
    let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
        return false;
    };
    IDENTITY_NAMES.contains(&name)
        || name.starts_with("online.json")
        || name.starts_with("online.token")
}

/// Copy the real settings in, with everything that publishes turned off.
///
/// False when there is no real settings file to copy, which is not an error:
/// a machine that has never run the game gets the game's own defaults, and
/// that is a legitimate thing to playtest.
pub fn seed_settings(sandbox: &Path, source: &Path) -> bool {
    let src = source.join("settings.json");
    let Ok(text) = std::fs::read_to_string(&src) else {
        return false;
    };
    let Ok(Value::Object(mut data)) = serde_json::from_str::<Value>(&text) else {
        return false;
    };
    for key in OFFLINE_SETTINGS {
        data.insert(key.to_string(), Value::Bool(false));
    }
    let sorted: Map<String, Value> = data.into_iter().collect();
    let Ok(rendered) = serde_json::to_string_pretty(&Value::Object(sorted)) else {
        return false;
    };
    std::fs::write(sandbox.join("settings.json"), rendered).is_ok()
}

/// Copy the real careers in as throwaways. Returns how many landed.
pub fn seed_careers(sandbox: &Path, source: &Path) -> usize {
    let src = source.join("profiles");
    let Ok(entries) = std::fs::read_dir(&src) else {
        return 0;
    };
    let dest = sandbox.join("profiles");
    if std::fs::create_dir_all(&dest).is_err() {
        return 0;
    }
    let mut paths: Vec<PathBuf> = entries
        .flatten()
        .map(|entry| entry.path())
        .filter(|path| {
            path.file_name()
                .and_then(|n| n.to_str())
                .is_some_and(|n| n.ends_with(CAREER_SUFFIX))
        })
        .collect();
    paths.sort();
    let mut copied = 0;
    for path in paths {
        let Some(name) = path.file_name() else {
            continue;
        };
        if std::fs::copy(&path, dest.join(name)).is_ok() {
            copied += 1;
        }
    }
    copied
}

/// Build the sandbox and point this process's game at it.
///
/// Sets `FREIGHT_FATE_DATA_DIR`, which has to happen before the game reads a
/// save path -- the override is consulted on every `data_dir()` call, but a
/// caller that has already resolved and cached a path keeps the old one.
pub fn prepare(sandbox: &Path, reset: bool, careers: bool, source: &Path) -> std::io::Result<()> {
    if reset && sandbox.exists() {
        std::fs::remove_dir_all(sandbox)?;
    }
    std::fs::create_dir_all(sandbox)?;
    if !sandbox.join("settings.json").exists() {
        seed_settings(sandbox, source);
    }
    if careers && !sandbox.join("profiles").exists() {
        seed_careers(sandbox, source);
    }
    std::env::set_var(DATA_DIR_ENV, sandbox);
    Ok(())
}

/// Every reason this sandbox could still reach the real account.
///
/// An empty list is the whole guarantee this tool offers, so it is computed
/// from what is on disk rather than from what the seeding step believes it
/// did.
pub fn audit(sandbox: &Path) -> Vec<String> {
    let mut problems = Vec::new();
    let mut found = Vec::new();
    walk(sandbox, &mut found);
    found.sort();
    for path in found {
        if is_identity(&path) {
            let shown = path.strip_prefix(sandbox).unwrap_or(&path).display();
            problems.push(format!("identity file in the sandbox: {shown}"));
        }
    }
    let settings = sandbox.join("settings.json");
    if settings.is_file() {
        match std::fs::read_to_string(&settings)
            .ok()
            .and_then(|text| serde_json::from_str::<Value>(&text).ok())
        {
            None => problems
                .push("settings.json is unreadable; cannot confirm publishing is off".to_string()),
            Some(value) => {
                let data = value.as_object().cloned().unwrap_or_default();
                for key in OFFLINE_SETTINGS {
                    if data.get(key).and_then(Value::as_bool).unwrap_or(false) {
                        problems.push(format!("settings.json still has {key} on"));
                    }
                }
            }
        }
    }
    problems
}

fn walk(dir: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            walk(&path, out);
        } else {
            out.push(path);
        }
    }
}

/// What a prepared sandbox holds, in one block, for the session log.
pub fn describe(sandbox: &Path) -> String {
    let profiles = sandbox.join("profiles");
    let mut careers: Vec<String> = std::fs::read_dir(&profiles)
        .into_iter()
        .flatten()
        .flatten()
        .filter_map(|entry| {
            let path = entry.path();
            let name = path.file_name()?.to_str()?;
            name.strip_suffix(CAREER_SUFFIX).map(str::to_string)
        })
        .collect();
    careers.sort();
    let shown = if careers.is_empty() {
        String::new()
    } else {
        let head = careers
            .iter()
            .take(6)
            .cloned()
            .collect::<Vec<_>>()
            .join(", ");
        let tail = if careers.len() > 6 { "..." } else { "" };
        format!(" ({head}{tail})")
    };
    let settings = if sandbox.join("settings.json").is_file() {
        "copied from saves/"
    } else {
        "game defaults"
    };
    let mut lines = vec![
        format!("Playtest sandbox: {}", sandbox.display()),
        format!("  careers: {}{shown}", careers.len()),
        format!("  settings: {settings}"),
    ];
    let problems = audit(sandbox);
    if problems.is_empty() {
        lines.push(
            "  no driver identity: cloud backup, presence and profile updates are off".to_string(),
        );
    } else {
        lines.push("  NOT ISOLATED:".to_string());
        lines.extend(problems.into_iter().map(|p| format!("    - {p}")));
    }
    lines.join("\n")
}

/// Announce a live playtest so `tools/playtest_watch.py` can follow it.
///
/// Both launchers write this -- the sandbox one and playtest_road's -- because
/// the watcher's job is the same either way, and the one thing it cannot work
/// out for itself is when the player has quit rather than simply parked the
/// truck and gone quiet.
pub fn open_session(sandbox: &Path, log_path: &Path) -> PathBuf {
    let file = session_file();
    if let Some(parent) = file.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let started = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0);
    let state = serde_json::json!({
        "pid": std::process::id(),
        "sandbox": sandbox.display().to_string(),
        "log": log_path.display().to_string(),
        "started": started,
        "running": true,
    });
    let _ = std::fs::write(
        &file,
        serde_json::to_string_pretty(&state).unwrap_or_default(),
    );
    file
}

/// Mark the session over. Best effort: a hard crash never reaches here,
/// which is why the watcher also checks whether the pid is still alive.
pub fn close_session() {
    let file = session_file();
    let Ok(text) = std::fs::read_to_string(&file) else {
        return;
    };
    let Ok(Value::Object(mut state)) = serde_json::from_str::<Value>(&text) else {
        return;
    };
    state.insert("running".to_string(), Value::Bool(false));
    let ended = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0);
    state.insert(
        "ended".to_string(),
        serde_json::Number::from_f64(ended)
            .map(Value::Number)
            .unwrap_or(Value::Null),
    );
    let _ = std::fs::write(
        &file,
        serde_json::to_string_pretty(&Value::Object(state)).unwrap_or_default(),
    );
}
