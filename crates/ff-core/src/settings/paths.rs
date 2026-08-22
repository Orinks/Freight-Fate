//! Where the game keeps its saves and settings.
//!
//! Port of `data_dir`, `_save_root`, `game_root` and their helpers from
//! `freight_fate/models/profile.py`. Settings needs them before the profile
//! model lands, and the profile port is expected to build on these (adding
//! the one-time legacy-save migration `data_dir` ran there, which is not
//! reproduced here).
//!
//! On Windows and Linux, Freight Fate is portable: profiles and settings
//! live in a `saves` directory inside the game's own main directory -- next
//! to the executable in a packaged build, the project root when running from
//! source.
//!
//! macOS apps live in `/Applications` and must not write beside themselves
//! (that folder is admin-owned and often read-only), so on macOS saves go in
//! the standard per-user `~/Library/Application Support/FreightFate` folder.
//!
//! The same reasoning covers Windows and Linux when the game itself sits in
//! a read-only location (for example Windows `Program Files`): if the
//! `saves` folder beside the game cannot be written, saves fall back to that
//! per-user data directory instead of failing on the first write and
//! crashing mid-session.
//!
//! Override the location with the `FREIGHT_FATE_DATA_DIR` environment
//! variable (which the tests use).

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};

use once_cell::sync::Lazy;
use parking_lot::Mutex;

/// Environment variable that pins the save directory for a run.
pub const DATA_DIR_ENV: &str = "FREIGHT_FATE_DATA_DIR";

static UNWRITABLE_WARNED: AtomicBool = AtomicBool::new(false);
static WRITABLE_CACHE: Lazy<Mutex<HashMap<PathBuf, bool>>> =
    Lazy::new(|| Mutex::new(HashMap::new()));

/// Serialises tests that set process-global environment variables
/// (`FREIGHT_FATE_DATA_DIR`); every test that touches one holds this.
#[cfg(test)]
pub(crate) static ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

fn home_dir() -> PathBuf {
    #[allow(deprecated)]
    std::env::home_dir().unwrap_or_else(|| PathBuf::from("."))
}

/// The standard per-user save location on macOS.
fn macos_data_dir() -> PathBuf {
    home_dir()
        .join("Library")
        .join("Application Support")
        .join("FreightFate")
}

/// Where saves lived before the portable layout (per-user folders).
///
/// On macOS this is also the *current* save location, since app bundles
/// cannot store saves beside themselves.
pub fn legacy_data_dir() -> PathBuf {
    if cfg!(target_os = "macos") {
        return macos_data_dir();
    }
    let base = if cfg!(windows) {
        std::env::var_os("APPDATA")
            .map(PathBuf::from)
            .unwrap_or_else(home_dir)
    } else {
        std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home_dir().join(".local").join("share"))
    };
    base.join("FreightFate")
}

/// Whether `path` exists (or can be created) and accepts a write.
///
/// Detects installs in protected locations, such as Windows `Program
/// Files`, where the portable `saves` folder beside the game would raise on
/// the first save and crash the game mid-session.
///
/// Cached per path: `save_root()` re-derives this on every save-directory
/// lookup (several times per menu enter), and the answer cannot change
/// within one run -- `game_root()` is fixed once the process starts, and
/// nothing else in the portable-save code path relocates it mid-session.
/// Without the cache this was a real mkdir+write+unlink against disk every
/// single call.
fn is_writable_dir(path: &Path) -> bool {
    let mut cache = WRITABLE_CACHE.lock();
    if let Some(known) = cache.get(path) {
        return *known;
    }
    let writable = probe_writable(path);
    cache.insert(path.to_path_buf(), writable);
    writable
}

fn probe_writable(path: &Path) -> bool {
    if std::fs::create_dir_all(path).is_err() {
        return false;
    }
    let probe = path.join(".freightfate-write-test");
    if std::fs::write(&probe, b"").is_err() {
        return false;
    }
    std::fs::remove_file(&probe).is_ok()
}

/// The active save directory for this platform.
///
/// Windows and Linux keep the portable `saves` folder next to the game.
/// macOS uses the per-user Application Support folder so the app never has
/// to write into `/Applications`. When the game sits in a read-only location
/// such as `Program Files`, Windows and Linux fall back to that same
/// per-user folder rather than crashing on the first save.
pub fn save_root() -> PathBuf {
    if cfg!(target_os = "macos") {
        return macos_data_dir();
    }
    let root = game_root();
    if is_writable_dir(&root) {
        return root.join("saves");
    }
    let fallback = legacy_data_dir();
    if !UNWRITABLE_WARNED.swap(true, Ordering::SeqCst) {
        log::warn!(
            "Game directory {} is not writable; saving to the per-user folder {} instead. \
             Move Freight Fate out of a protected location such as Program Files to keep \
             saves beside the game.",
            root.display(),
            fallback.display()
        );
    }
    fallback
}

/// The directory of the running executable, resolved.
fn executable_dir() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    // Absolute, but not canonical: `canonicalize` on Windows yields a
    // verbatim `\?\` path, which then leaks into every save path and log
    // line built on it.
    let exe = std::path::absolute(&exe).unwrap_or(exe);
    exe.parent().map(Path::to_path_buf)
}

/// A packaged build ships `freight_fate/data` beside the executable (the
/// release layout); that is what "frozen" meant for the Python build.
fn packaged_exe_dir() -> Option<PathBuf> {
    let dir = executable_dir()?;
    if dir.join("freight_fate").join("data").is_dir() {
        Some(dir)
    } else {
        None
    }
}

fn macos_app_bundle(exe_dir: &Path) -> Option<PathBuf> {
    if !cfg!(target_os = "macos") {
        return None;
    }
    if exe_dir.file_name()? != "MacOS" || exe_dir.parent()?.file_name()? != "Contents" {
        return None;
    }
    let bundle = exe_dir.parent()?.parent()?;
    if bundle.extension()? == "app" {
        Some(bundle.to_path_buf())
    } else {
        None
    }
}

/// Walk up from `start` looking for the project root (`src/freight_fate`).
fn find_project_root(start: &Path) -> Option<PathBuf> {
    let mut cursor = Some(start);
    while let Some(dir) = cursor {
        if dir.join("src").join("freight_fate").is_dir() {
            return Some(dir.to_path_buf());
        }
        cursor = dir.parent();
    }
    None
}

/// The game's main directory: the executable's directory in a packaged
/// build (the enclosing folder of the app bundle on macOS), the project root
/// when running from source.
pub fn game_root() -> PathBuf {
    if let Some(exe_dir) = packaged_exe_dir() {
        if let Some(bundle) = macos_app_bundle(&exe_dir) {
            return bundle.parent().map(Path::to_path_buf).unwrap_or(exe_dir);
        }
        return exe_dir;
    }
    // Running from source: this crate sits at `crates/ff-core` in the repo,
    // as `settings.py` sat at `src/freight_fate/settings.py`.
    if let Some(root) = find_project_root(Path::new(env!("CARGO_MANIFEST_DIR"))) {
        return root;
    }
    if let Some(root) = executable_dir().and_then(|dir| find_project_root(&dir)) {
        return root;
    }
    executable_dir().unwrap_or_else(|| PathBuf::from("."))
}

/// Where settings and profiles live: `FREIGHT_FATE_DATA_DIR` when set (and
/// not empty), else [`save_root`].
pub fn data_dir() -> PathBuf {
    if let Some(override_dir) = std::env::var_os(DATA_DIR_ENV) {
        if !override_dir.is_empty() {
            return PathBuf::from(override_dir);
        }
    }
    save_root()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn with_env<T>(value: Option<&Path>, body: impl FnOnce() -> T) -> T {
        let _guard = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let previous = std::env::var_os(DATA_DIR_ENV);
        match value {
            Some(path) => std::env::set_var(DATA_DIR_ENV, path),
            None => std::env::remove_var(DATA_DIR_ENV),
        }
        let result = body();
        match previous {
            Some(old) => std::env::set_var(DATA_DIR_ENV, old),
            None => std::env::remove_var(DATA_DIR_ENV),
        }
        result
    }

    #[test]
    fn the_override_wins_and_an_empty_override_does_not() {
        let tmp = tempfile::tempdir().unwrap();
        with_env(Some(tmp.path()), || {
            assert_eq!(data_dir(), tmp.path());
        });
        with_env(Some(Path::new("")), || {
            assert_eq!(data_dir(), save_root());
        });
    }

    #[test]
    fn the_source_checkout_keeps_saves_beside_the_project() {
        let root = game_root();
        assert!(
            root.join("src").join("freight_fate").is_dir(),
            "{}",
            root.display()
        );
        if !cfg!(target_os = "macos") {
            assert_eq!(save_root(), root.join("saves"));
        }
    }

    #[test]
    fn the_writable_probe_is_cached_and_honest() {
        let tmp = tempfile::tempdir().unwrap();
        let dir = tmp.path().join("fresh");
        assert!(is_writable_dir(&dir));
        assert!(is_writable_dir(&dir));
        assert!(!dir.join(".freightfate-write-test").exists());
        // A file where a directory should be cannot be written into.
        let blocked = tmp.path().join("blocked");
        std::fs::write(&blocked, b"x").unwrap();
        assert!(!is_writable_dir(&blocked));
    }
}
