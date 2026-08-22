//! Runtime loading of the Prism shared library.
//!
//! Speech is an enhancement, not a hard dependency: a missing library must not
//! stop the application from starting. So rather than linking against an import
//! library, the symbols are resolved once on first use and cached. If any part
//! of that fails, [`Api::get`] returns `None` and the caller falls back to
//! visual-only output.

use std::path::PathBuf;
use std::sync::OnceLock;

use libloading::{Library, Symbol};

use crate::*;

/// Shared-library file name for the current platform.
pub fn library_file_name() -> &'static str {
    if cfg!(windows) {
        "prism.dll"
    } else if cfg!(target_os = "macos") {
        "libprism.dylib"
    } else {
        "libprism.so"
    }
}

/// Candidate locations for the library, most specific first.
///
/// The bare file name is included last so the platform loader gets a chance to
/// find a system-wide install.
fn search_paths() -> Vec<PathBuf> {
    let file_name = library_file_name();
    let mut candidates = Vec::new();

    if let Ok(explicit) = std::env::var("PORTKEYDROP_PRISM_PATH") {
        if !explicit.is_empty() {
            candidates.push(PathBuf::from(explicit));
        }
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            candidates.push(dir.join(file_name));
            // Packaged macOS bundles keep native libraries beside the app
            // resources rather than next to the executable.
            candidates.push(dir.join("..").join("Frameworks").join(file_name));
            candidates.push(dir.join("lib").join(file_name));
        }
    }

    candidates.push(PathBuf::from(file_name));
    candidates
}

/// Resolved Prism entry points.
///
/// Only the symbols Portkey Drop actually calls are resolved. Adding a new call
/// site means adding a field here and a matching `load` line.
pub struct Api {
    _library: Library,

    pub config_init: FnConfigInit,
    pub init: FnInit,
    pub shutdown: FnShutdown,

    pub registry_count: FnRegistryCount,
    pub registry_id_at: FnRegistryIdAt,
    pub registry_id: FnRegistryId,
    pub registry_name: FnRegistryName,
    pub registry_exists: FnRegistryExists,
    pub registry_acquire: FnRegistryAcquire,
    pub registry_acquire_best: FnRegistryAcquireBest,

    pub backend_free: FnBackendFree,
    pub backend_get_features: FnBackendFeatures,
    pub backend_name: FnBackendName,
    pub backend_initialize: FnBackendInitialize,
    pub backend_speak: FnBackendSpeak,
    pub backend_output: FnBackendSpeak,
    pub backend_braille: FnBackendBraille,
    pub backend_stop: FnBackendVoid,
    pub backend_is_speaking: FnBackendGetBool,
    pub backend_set_volume: FnBackendSetF32,
    pub backend_get_volume: FnBackendGetF32,
    pub backend_set_rate: FnBackendSetF32,
    pub backend_get_rate: FnBackendGetF32,

    pub error_string: FnErrorString,
}

// The library and its function pointers stay alive for the process lifetime and
// Prism guards its own internal state, so the resolved table is shareable.
unsafe impl Send for Api {}
unsafe impl Sync for Api {}

/// Resolve one symbol, logging and bailing out if it is absent.
///
/// # Safety
/// The caller must give a `T` matching the symbol's real C signature.
unsafe fn symbol<T: Copy>(library: &Library, name: &[u8]) -> Option<T> {
    match library.get::<T>(name) {
        Ok(found) => Some(*Symbol::into_raw(found)),
        Err(err) => {
            log::warn!(
                "prism: missing symbol {}: {err}",
                String::from_utf8_lossy(&name[..name.len().saturating_sub(1)])
            );
            None
        }
    }
}

impl Api {
    /// Load and cache the Prism API, or `None` when it is unavailable.
    ///
    /// The first call does the work; later calls return the cached result,
    /// including a cached failure — a missing library is not retried.
    pub fn get() -> Option<&'static Api> {
        static API: OnceLock<Option<Api>> = OnceLock::new();
        API.get_or_init(Api::load).as_ref()
    }

    fn load() -> Option<Api> {
        for candidate in search_paths() {
            // SAFETY: loading a shared library runs its initialisers. Prism's
            // are benign, and the candidate paths are app-controlled.
            match unsafe { Library::new(&candidate) } {
                Ok(library) => match unsafe { Api::resolve(library) } {
                    Some(api) => {
                        log::info!("prism: loaded from {}", candidate.display());
                        return Some(api);
                    }
                    None => {
                        log::warn!(
                            "prism: {} loaded but is missing required symbols",
                            candidate.display()
                        );
                    }
                },
                Err(err) => {
                    log::debug!("prism: {} not loadable: {err}", candidate.display());
                }
            }
        }
        log::info!("prism: library not found; speech output is unavailable");
        None
    }

    /// # Safety
    /// Every signature below must match the C header exactly.
    unsafe fn resolve(library: Library) -> Option<Api> {
        Some(Api {
            config_init: symbol(&library, b"prism_config_init\0")?,
            init: symbol(&library, b"prism_init\0")?,
            shutdown: symbol(&library, b"prism_shutdown\0")?,

            registry_count: symbol(&library, b"prism_registry_count\0")?,
            registry_id_at: symbol(&library, b"prism_registry_id_at\0")?,
            registry_id: symbol(&library, b"prism_registry_id\0")?,
            registry_name: symbol(&library, b"prism_registry_name\0")?,
            registry_exists: symbol(&library, b"prism_registry_exists\0")?,
            registry_acquire: symbol(&library, b"prism_registry_acquire\0")?,
            registry_acquire_best: symbol(&library, b"prism_registry_acquire_best\0")?,

            backend_free: symbol(&library, b"prism_backend_free\0")?,
            backend_get_features: symbol(&library, b"prism_backend_get_features\0")?,
            backend_name: symbol(&library, b"prism_backend_name\0")?,
            backend_initialize: symbol(&library, b"prism_backend_initialize\0")?,
            backend_speak: symbol(&library, b"prism_backend_speak\0")?,
            backend_output: symbol(&library, b"prism_backend_output\0")?,
            backend_braille: symbol(&library, b"prism_backend_braille\0")?,
            backend_stop: symbol(&library, b"prism_backend_stop\0")?,
            backend_is_speaking: symbol(&library, b"prism_backend_is_speaking\0")?,
            backend_set_volume: symbol(&library, b"prism_backend_set_volume\0")?,
            backend_get_volume: symbol(&library, b"prism_backend_get_volume\0")?,
            backend_set_rate: symbol(&library, b"prism_backend_set_rate\0")?,
            backend_get_rate: symbol(&library, b"prism_backend_get_rate\0")?,

            error_string: symbol(&library, b"prism_error_string\0")?,

            _library: library,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn search_paths_end_with_bare_library_name() {
        let paths = search_paths();
        let last = paths.last().expect("at least one candidate");
        assert_eq!(last, &PathBuf::from(library_file_name()));
    }

    #[test]
    fn search_paths_honour_the_override_env_var() {
        // The override is read per call, so setting it here is enough.
        std::env::set_var("PORTKEYDROP_PRISM_PATH", "/tmp/custom-prism-lib");
        let paths = search_paths();
        std::env::remove_var("PORTKEYDROP_PRISM_PATH");
        assert_eq!(paths.first(), Some(&PathBuf::from("/tmp/custom-prism-lib")));
    }

    #[test]
    fn loading_is_cached_and_never_panics() {
        // Whether or not Prism is present, two calls must agree and neither
        // may panic.
        let first = Api::get().is_some();
        let second = Api::get().is_some();
        assert_eq!(first, second);
    }
}
