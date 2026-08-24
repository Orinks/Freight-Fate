//! Safe wrapper over the Prism speech library.
//!
//! Prism talks to whichever screen reader or TTS engine is present (NVDA,
//! JAWS, SAPI, VoiceOver, Speech Dispatcher, Orca...). The surface here is the
//! one prismatoid gives Python -- enumerate the registry with ids, names and
//! priorities, acquire a backend, ask it what it supports, speak through
//! `output` or `speak`, and adjust rate / pitch / volume / voice -- so a
//! speech layer written against prismatoid ports across line for line.
//!
//! Every operation degrades gracefully. If Prism is missing, no backend is
//! available, or a backend rejects a property, callers get `None`/`Err`
//! rather than a panic — announcements are an enhancement, never a hard
//! dependency.
//!
//! Nothing here clamps or rescales values. Rate, pitch and volume are floats
//! that Prism documents as `0.0..=1.0`; what a backend does with a value
//! outside that range is the backend's business, as it is from Python.

use std::ffi::{CStr, CString};
use std::fmt;
use std::ptr;
use std::sync::{Mutex, OnceLock};

use prism_sys::Api;

pub use prism_sys::{backend_id, PrismBackendId};

/// Errors surfaced by the safe wrapper.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    /// The Prism shared library could not be loaded or initialised.
    #[error("Prism is not available on this system")]
    Unavailable,
    /// No speech backend is usable right now (no screen reader, no TTS).
    #[error("no speech backend is available")]
    NoBackend,
    /// Text contained an interior NUL and cannot cross the C boundary.
    #[error("text contains an interior NUL byte")]
    InteriorNul,
    /// Text was empty. prismatoid refuses this before reaching the library
    /// (`Text MUST NOT be empty`), and so does this wrapper.
    #[error("text must not be empty")]
    EmptyText,
    /// The native call returned a non-zero `PrismError`.
    #[error("prism error {code}: {message}")]
    Native { code: i32, message: String },
}

impl Error {
    /// The native error code, when this error came from the library.
    pub fn code(&self) -> Option<i32> {
        match self {
            Error::Native { code, .. } => Some(*code),
            _ => None,
        }
    }
}

/// Whether the native Prism library was found and loaded.
pub fn native_available() -> bool {
    Api::get().is_some()
}

/// Turn a native return code into a `Result`, resolving its message text.
fn check(api: &Api, code: i32) -> Result<(), Error> {
    if code == prism_sys::PRISM_OK {
        return Ok(());
    }
    // SAFETY: `error_string` returns a static NUL-terminated string owned by
    // the library, valid for any code value.
    let message = unsafe {
        let text = (api.error_string)(code);
        if text.is_null() {
            String::from("unknown error")
        } else {
            CStr::from_ptr(text).to_string_lossy().into_owned()
        }
    };
    Err(Error::Native { code, message })
}

/// Read a `const char *` returned by Prism into an owned `String`.
///
/// # Safety
/// `text` must be NUL-terminated or null.
unsafe fn owned_string(text: *const std::os::raw::c_char, fallback: &str) -> String {
    if text.is_null() {
        fallback.to_string()
    } else {
        CStr::from_ptr(text).to_string_lossy().into_owned()
    }
}

/// Text for the C side: rejects empty strings (as prismatoid does) and
/// interior NULs (which C cannot carry).
fn c_text(text: &str) -> Result<CString, Error> {
    if text.is_empty() {
        return Err(Error::EmptyText);
    }
    CString::new(text).map_err(|_| Error::InteriorNul)
}

/// Serialises Prism's start-up and shutdown.
///
/// Not for the reason it was first written. The crashes that prompted it came
/// from a `PrismConfig` forty-seven bytes short of the real one, which
/// corrupted the stack on every call; glib noticing first made it look like a
/// type-registration conflict. With the struct right, start-up, shutdown, and
/// overlapping contexts all behave.
///
/// The lock stays because concurrent start-up is not something the library
/// documents, and it costs nothing in an app that starts speech once.
fn lifecycle_lock() -> &'static Mutex<()> {
    static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    LOCK.get_or_init(|| Mutex::new(()))
}

/// Take the lifecycle lock, ignoring poisoning.
///
/// It guards `()`; there is no state left inconsistent by a panic elsewhere,
/// and refusing all speech from then on would be the worse outcome.
fn lock_lifecycle() -> std::sync::MutexGuard<'static, ()> {
    lifecycle_lock()
        .lock()
        .unwrap_or_else(|err| err.into_inner())
}

/// Backend feature bits with a named predicate per bit.
///
/// Mirrors prismatoid's `BackendFeatures` dataclass: the same names, the same
/// bit positions (see [`prism_sys::features`]). `is_supported_at_runtime` is
/// the live check -- whether the screen reader or engine is reachable right
/// now -- while every `supports_*` says whether the backend implements that
/// entry point at all.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Default)]
pub struct Features(u64);

macro_rules! feature_predicates {
    ($($(#[$meta:meta])* $name:ident => $bit:ident),* $(,)?) => {
        $(
            $(#[$meta])*
            pub const fn $name(self) -> bool {
                self.0 & prism_sys::features::$bit != 0
            }
        )*

        /// Names of every set bit, for diagnostics.
        pub fn names(self) -> Vec<&'static str> {
            let mut names = Vec::new();
            $(
                if self.$name() {
                    names.push(stringify!($name));
                }
            )*
            names
        }
    };
}

impl Features {
    /// Wrap a raw bitmask as returned by `prism_backend_get_features`.
    pub const fn from_bits(bits: u64) -> Self {
        Self(bits)
    }

    /// The raw bitmask.
    pub const fn bits(self) -> u64 {
        self.0
    }

    /// Whether every bit in `mask` is set.
    pub const fn contains(self, mask: u64) -> bool {
        self.0 & mask == mask
    }

    feature_predicates! {
        /// The backend can reach its screen reader or engine right now.
        is_supported_at_runtime => IS_SUPPORTED_AT_RUNTIME,
        supports_speak => SUPPORTS_SPEAK,
        supports_speak_to_memory => SUPPORTS_SPEAK_TO_MEMORY,
        supports_braille => SUPPORTS_BRAILLE,
        /// `output` -- speech and braille in one call.
        supports_output => SUPPORTS_OUTPUT,
        supports_is_speaking => SUPPORTS_IS_SPEAKING,
        supports_stop => SUPPORTS_STOP,
        supports_pause => SUPPORTS_PAUSE,
        supports_resume => SUPPORTS_RESUME,
        supports_set_volume => SUPPORTS_SET_VOLUME,
        supports_get_volume => SUPPORTS_GET_VOLUME,
        supports_set_rate => SUPPORTS_SET_RATE,
        supports_get_rate => SUPPORTS_GET_RATE,
        supports_set_pitch => SUPPORTS_SET_PITCH,
        supports_get_pitch => SUPPORTS_GET_PITCH,
        supports_refresh_voices => SUPPORTS_REFRESH_VOICES,
        supports_count_voices => SUPPORTS_COUNT_VOICES,
        supports_get_voice_name => SUPPORTS_GET_VOICE_NAME,
        supports_get_voice_language => SUPPORTS_GET_VOICE_LANGUAGE,
        supports_get_voice => SUPPORTS_GET_VOICE,
        supports_set_voice => SUPPORTS_SET_VOICE,
        supports_get_channels => SUPPORTS_GET_CHANNELS,
        supports_get_sample_rate => SUPPORTS_GET_SAMPLE_RATE,
        supports_get_bit_depth => SUPPORTS_GET_BIT_DEPTH,
        performs_silence_trimming_on_speak => PERFORMS_SILENCE_TRIMMING_ON_SPEAK,
        performs_silence_trimming_on_speak_to_memory => PERFORMS_SILENCE_TRIMMING_ON_SPEAK_TO_MEMORY,
        supports_speak_ssml => SUPPORTS_SPEAK_SSML,
        supports_speak_to_memory_ssml => SUPPORTS_SPEAK_TO_MEMORY_SSML,
    }
}

impl fmt::Debug for Features {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_tuple("Features")
            .field(&format_args!("{:#x}", self.0))
            .field(&self.names())
            .finish()
    }
}

/// Prism's two ways of saying "no such backend": `INVALID` (0) from a name
/// lookup, and all-ones from `registry_id_at` past the end of the registry.
fn valid_id(id: PrismBackendId) -> Option<PrismBackendId> {
    (id != backend_id::INVALID && id != PrismBackendId::MAX).then_some(id)
}

/// A live Prism library context.
///
/// Dropping the context shuts Prism down, so it must outlive every [`Backend`]
/// taken from it. [`Announcer`] owns both together and drops them in order.
pub struct Context {
    api: &'static Api,
    raw: *mut prism_sys::PrismContext,
}

// The wrapper requires `&mut` for every mutating call, so a context may move
// between threads. Starting and stopping are serialised; see
// [`lifecycle_lock`].
unsafe impl Send for Context {}

impl Context {
    /// Initialise Prism.
    ///
    /// Returns [`Error::Unavailable`] when the native library is absent or
    /// refuses to start.
    pub fn new() -> Result<Self, Error> {
        let api = Api::get().ok_or(Error::Unavailable)?;
        let _guard = lock_lifecycle();
        // SAFETY: `config_init` fills the whole struct and `init` reads the
        // whole struct, so `PrismConfig` has to match the library's layout
        // exactly. It is pinned by a test in prism-sys.
        let raw = unsafe {
            let mut config = (api.config_init)();
            (api.init)(&mut config)
        };
        if raw.is_null() {
            return Err(Error::Unavailable);
        }
        Ok(Self { api, raw })
    }

    /// Number of backends registered in this build of Prism.
    pub fn backend_count(&self) -> usize {
        unsafe { (self.api.registry_count)(self.raw) }
    }

    /// The id of the backend at `index` in registry order, or `None` past the
    /// end.
    pub fn id_at(&self, index: usize) -> Option<PrismBackendId> {
        if index >= self.backend_count() {
            return None;
        }
        let id = unsafe { (self.api.registry_id_at)(self.raw, index) };
        valid_id(id)
    }

    /// Ids of every registered backend, in registry order.
    ///
    /// Registry order is not priority order; sort by [`Context::priority_of`]
    /// to rank them, as the game's backend picker does.
    pub fn backend_ids(&self) -> Vec<PrismBackendId> {
        (0..self.backend_count())
            .filter_map(|index| self.id_at(index))
            .collect()
    }

    /// Look a backend up by its registry name (`"SAPI"`, `"NVDA"`, `"UIA"`,
    /// ...). `None` when no backend has that name.
    pub fn id_by_name(&self, name: &str) -> Option<PrismBackendId> {
        let name = CString::new(name).ok()?;
        let id = unsafe { (self.api.registry_id)(self.raw, name.as_ptr()) };
        valid_id(id)
    }

    /// The registry name of a backend, or `None` for an unknown id.
    pub fn name_of(&self, id: PrismBackendId) -> Option<String> {
        let text = unsafe { (self.api.registry_name)(self.raw, id) };
        if text.is_null() {
            return None;
        }
        Some(unsafe { owned_string(text, "unknown") })
    }

    /// Prism's static priority for a backend: higher ranks first. This is
    /// what `acquire_best` ranks by, and it says nothing about whether the
    /// backend is usable right now -- check [`Features::is_supported_at_runtime`]
    /// on the acquired backend for that.
    pub fn priority_of(&self, id: PrismBackendId) -> i32 {
        unsafe { (self.api.registry_priority)(self.raw, id) }
    }

    /// Whether `id` names a registered backend.
    pub fn exists(&self, id: PrismBackendId) -> bool {
        unsafe { (self.api.registry_exists)(self.raw, id) }
    }

    /// Names of all registered backends, in registry order.
    pub fn backend_names(&self) -> Vec<String> {
        (0..self.backend_count())
            .map(|index| unsafe {
                let id = (self.api.registry_id_at)(self.raw, index);
                owned_string((self.api.registry_name)(self.raw, id), "unknown")
            })
            .collect()
    }

    /// Acquire the highest-priority backend usable right now.
    ///
    /// Prism ranks by static priority and prefers a backend that already has
    /// a live cached instance, so this does not notice a screen reader that
    /// started after the game did. A picker that needs that enumerates
    /// [`Context::backend_ids`] and checks each one's features instead.
    pub fn acquire_best(&self) -> Result<Backend, Error> {
        let raw = unsafe { (self.api.registry_acquire_best)(self.raw) };
        self.wrap_backend(raw)
    }

    /// Acquire a specific backend by id; see [`prism_sys::backend_id`].
    ///
    /// Prism caches the instance, so acquiring the same id twice hands back
    /// the same underlying backend.
    pub fn acquire(&self, id: PrismBackendId) -> Result<Backend, Error> {
        let raw = unsafe { (self.api.registry_acquire)(self.raw, id) };
        self.wrap_backend(raw)
    }

    fn wrap_backend(&self, raw: *mut prism_sys::PrismBackend) -> Result<Backend, Error> {
        if raw.is_null() {
            return Err(Error::NoBackend);
        }
        let backend = Backend { api: self.api, raw };
        // Some backends (SAPI) need an explicit initialise before the first
        // speak; those that do not report an "already initialised" error,
        // which is not fatal.
        if let Err(err) = check(self.api, unsafe { (self.api.backend_initialize)(raw) }) {
            log::debug!("prism backend initialize returned {err}");
        }
        Ok(backend)
    }
}

impl Drop for Context {
    fn drop(&mut self) {
        if !self.raw.is_null() {
            let _guard = lock_lifecycle();
            unsafe { (self.api.shutdown)(self.raw) };
            self.raw = ptr::null_mut();
        }
    }
}

/// A speech backend acquired from a [`Context`].
///
/// Rate, pitch and volume are `f32` fractions Prism documents as
/// `0.0..=1.0`; they are passed through untouched. Voices are addressed by
/// index in `0..voices_count()`.
pub struct Backend {
    api: &'static Api,
    raw: *mut prism_sys::PrismBackend,
}

unsafe impl Send for Backend {}

impl Backend {
    /// The backend's human-readable name (`"NVDA"`, `"SAPI"`, ...).
    pub fn name(&self) -> String {
        unsafe { owned_string((self.api.backend_name)(self.raw), "unknown") }
    }

    /// What this backend supports, as named predicates.
    pub fn features(&self) -> Features {
        Features::from_bits(unsafe { (self.api.backend_get_features)(self.raw) })
    }

    /// Whether this backend can speak at all.
    pub fn supports_speak(&self) -> bool {
        self.features().supports_speak()
    }

    /// Whether this backend can drive a braille display.
    pub fn supports_braille(&self) -> bool {
        self.features().supports_braille()
    }

    /// Speak (and braille, where supported) `text`, optionally interrupting
    /// the current utterance. Prism's `output` entry point; prefer it over
    /// [`Backend::speak`] whenever [`Features::supports_output`] is set.
    pub fn output(&mut self, text: &str, interrupt: bool) -> Result<(), Error> {
        let text = c_text(text)?;
        check(self.api, unsafe {
            (self.api.backend_output)(self.raw, text.as_ptr(), interrupt)
        })
    }

    /// Speak `text` only, optionally interrupting the current utterance.
    /// Prism's `speak` entry point.
    pub fn speak(&mut self, text: &str, interrupt: bool) -> Result<(), Error> {
        let text = c_text(text)?;
        check(self.api, unsafe {
            (self.api.backend_speak)(self.raw, text.as_ptr(), interrupt)
        })
    }

    /// Send `text` to a braille display only.
    pub fn braille(&mut self, text: &str) -> Result<(), Error> {
        let text = c_text(text)?;
        check(self.api, unsafe {
            (self.api.backend_braille)(self.raw, text.as_ptr())
        })
    }

    /// Stop any in-progress speech.
    pub fn stop(&mut self) -> Result<(), Error> {
        check(self.api, unsafe { (self.api.backend_stop)(self.raw) })
    }

    /// Pause in-progress speech.
    pub fn pause(&mut self) -> Result<(), Error> {
        check(self.api, unsafe { (self.api.backend_pause)(self.raw) })
    }

    /// Resume paused speech.
    pub fn resume(&mut self) -> Result<(), Error> {
        check(self.api, unsafe { (self.api.backend_resume)(self.raw) })
    }

    /// Whether the backend is currently speaking.
    pub fn is_speaking(&self) -> Result<bool, Error> {
        let mut speaking = false;
        check(self.api, unsafe {
            (self.api.backend_is_speaking)(self.raw, &mut speaking)
        })?;
        Ok(speaking)
    }

    /// Set speech rate; documented range `0.0..=1.0`, passed through as-is.
    pub fn set_rate(&mut self, rate: f32) -> Result<(), Error> {
        check(self.api, unsafe {
            (self.api.backend_set_rate)(self.raw, rate)
        })
    }

    /// Current speech rate.
    pub fn rate(&self) -> Result<f32, Error> {
        self.get_f32(self.api.backend_get_rate)
    }

    /// Set speech pitch; documented range `0.0..=1.0`, passed through as-is.
    /// Some backends (OneCore) report their native default as NaN.
    pub fn set_pitch(&mut self, pitch: f32) -> Result<(), Error> {
        check(self.api, unsafe {
            (self.api.backend_set_pitch)(self.raw, pitch)
        })
    }

    /// Current speech pitch.
    pub fn pitch(&self) -> Result<f32, Error> {
        self.get_f32(self.api.backend_get_pitch)
    }

    /// Set output volume; documented range `0.0..=1.0`, passed through as-is.
    pub fn set_volume(&mut self, volume: f32) -> Result<(), Error> {
        check(self.api, unsafe {
            (self.api.backend_set_volume)(self.raw, volume)
        })
    }

    /// Current output volume.
    pub fn volume(&self) -> Result<f32, Error> {
        self.get_f32(self.api.backend_get_volume)
    }

    /// Re-read the installed voices from the engine.
    pub fn refresh_voices(&mut self) -> Result<(), Error> {
        check(self.api, unsafe {
            (self.api.backend_refresh_voices)(self.raw)
        })
    }

    /// Number of voices this backend can switch between.
    pub fn voices_count(&self) -> Result<usize, Error> {
        self.get_usize(self.api.backend_count_voices)
    }

    /// Display name of the voice at `index` (`0..voices_count()`).
    pub fn voice_name(&self, index: usize) -> Result<String, Error> {
        self.get_indexed_str(self.api.backend_get_voice_name, index)
    }

    /// Language tag of the voice at `index`, as the engine reports it.
    pub fn voice_language(&self, index: usize) -> Result<String, Error> {
        self.get_indexed_str(self.api.backend_get_voice_language, index)
    }

    /// Switch to the voice at `index`.
    pub fn set_voice(&mut self, index: usize) -> Result<(), Error> {
        check(self.api, unsafe {
            (self.api.backend_set_voice)(self.raw, index)
        })
    }

    /// Index of the current voice.
    pub fn voice(&self) -> Result<usize, Error> {
        self.get_usize(self.api.backend_get_voice)
    }

    /// Channel count of the engine's audio output (speak-to-memory backends).
    pub fn channels(&self) -> Result<usize, Error> {
        self.get_usize(self.api.backend_get_channels)
    }

    /// Sample rate of the engine's audio output (speak-to-memory backends).
    pub fn sample_rate(&self) -> Result<usize, Error> {
        self.get_usize(self.api.backend_get_sample_rate)
    }

    /// Bit depth of the engine's audio output (speak-to-memory backends).
    pub fn bit_depth(&self) -> Result<usize, Error> {
        self.get_usize(self.api.backend_get_bit_depth)
    }

    fn get_f32(&self, getter: prism_sys::FnBackendGetF32) -> Result<f32, Error> {
        let mut value = 0.0;
        check(self.api, unsafe { getter(self.raw, &mut value) })?;
        Ok(value)
    }

    fn get_usize(&self, getter: prism_sys::FnBackendGetUsize) -> Result<usize, Error> {
        let mut value = 0;
        check(self.api, unsafe { getter(self.raw, &mut value) })?;
        Ok(value)
    }

    fn get_indexed_str(
        &self,
        getter: prism_sys::FnBackendGetIndexedStr,
        index: usize,
    ) -> Result<String, Error> {
        let mut text: *const std::os::raw::c_char = ptr::null();
        check(self.api, unsafe { getter(self.raw, index, &mut text) })?;
        // SAFETY: on success Prism points `text` at a NUL-terminated string it
        // owns; it is copied out before any further call on the backend.
        Ok(unsafe { owned_string(text, "") })
    }
}

impl fmt::Debug for Backend {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Backend")
            .field("name", &self.name())
            .finish()
    }
}

impl Drop for Backend {
    fn drop(&mut self) {
        if !self.raw.is_null() {
            unsafe { (self.api.backend_free)(self.raw) };
            self.raw = ptr::null_mut();
        }
    }
}

/// Screen-reader announcement helper with graceful fallback.
///
/// Construction never fails. When no backend is available every announcement
/// is a silent no-op, so callers can fall back to the status bar and activity
/// log without special-casing.
///
/// Portkey Drop's convenience; Freight Fate builds its own speech layer on
/// [`Context`] and [`Backend`] directly.
pub struct Announcer {
    // Declaration order is the drop order: the backend must be released
    // before the context that produced it.
    backend: Option<Backend>,
    context: Option<Context>,
}

impl Announcer {
    /// Build an announcer, acquiring the best backend if one exists.
    pub fn new() -> Self {
        match Context::new() {
            Ok(context) => match context.acquire_best() {
                Ok(backend) => {
                    log::info!("prism backend active: {}", backend.name());
                    Self {
                        backend: Some(backend),
                        context: Some(context),
                    }
                }
                Err(err) => {
                    log::debug!("no prism backend available: {err}");
                    Self {
                        backend: None,
                        context: Some(context),
                    }
                }
            },
            Err(err) => {
                log::debug!("prism unavailable: {err}");
                Self {
                    backend: None,
                    context: None,
                }
            }
        }
    }

    /// An announcer that never speaks. Used in tests and headless runs.
    pub fn disabled() -> Self {
        Self {
            backend: None,
            context: None,
        }
    }

    /// Whether speech output is actually wired up.
    pub fn is_available(&self) -> bool {
        self.backend.as_ref().is_some_and(Backend::supports_speak)
    }

    /// Name of the active backend, if any.
    pub fn backend_name(&self) -> Option<String> {
        self.backend.as_ref().map(Backend::name)
    }

    /// Names of every backend Prism knows about, for diagnostics.
    pub fn known_backends(&self) -> Vec<String> {
        self.context
            .as_ref()
            .map(Context::backend_names)
            .unwrap_or_default()
    }

    /// Speak `text`, interrupting the current utterance.
    ///
    /// Returns whether the text actually reached a backend.
    pub fn announce(&mut self, text: &str) -> bool {
        let Some(backend) = self.backend.as_mut() else {
            return false;
        };
        match backend.output(text, true) {
            Ok(()) => true,
            Err(err) => {
                log::warn!("failed to announce text via prism: {err}");
                false
            }
        }
    }

    /// Apply the app's 0–100 speech settings.
    ///
    /// Backends that follow the screen reader's own configuration (NVDA, JAWS)
    /// reject these; that is expected and left alone rather than reported.
    pub fn apply_settings(&mut self, rate: Option<i32>, volume: Option<i32>) {
        let Some(backend) = self.backend.as_mut() else {
            return;
        };
        if let Some(rate) = rate {
            if let Err(err) = backend.set_rate(percent_to_fraction(rate)) {
                log::debug!("backend does not accept a speech rate: {err}");
            }
        }
        if let Some(volume) = volume {
            if let Err(err) = backend.set_volume(percent_to_fraction(volume)) {
                log::debug!("backend does not accept a speech volume: {err}");
            }
        }
    }
}

impl Default for Announcer {
    fn default() -> Self {
        Self::new()
    }
}

impl fmt::Debug for Announcer {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Announcer")
            .field("available", &self.is_available())
            .field("backend", &self.backend_name())
            .finish()
    }
}

/// Convert a 0–100 setting into the 0.0–1.0 fraction Prism expects.
pub fn percent_to_fraction(percent: i32) -> f32 {
    percent.clamp(0, 100) as f32 / 100.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn percent_to_fraction_clamps_and_scales() {
        assert_eq!(percent_to_fraction(0), 0.0);
        assert_eq!(percent_to_fraction(50), 0.5);
        assert_eq!(percent_to_fraction(100), 1.0);
        assert_eq!(percent_to_fraction(-20), 0.0);
        assert_eq!(percent_to_fraction(250), 1.0);
    }

    #[test]
    fn disabled_announcer_is_silent_and_reports_unavailable() {
        let mut announcer = Announcer::disabled();
        assert!(!announcer.is_available());
        assert!(!announcer.announce("hello"));
        assert_eq!(announcer.backend_name(), None);
        assert!(announcer.known_backends().is_empty());
        // Applying settings without a backend must not panic.
        announcer.apply_settings(Some(70), Some(90));
    }

    #[test]
    fn announcer_construction_never_panics() {
        // CI has no screen reader; this must still yield a usable (silent)
        // announcer rather than failing.
        let announcer = Announcer::new();
        let _ = announcer.is_available();
        let _ = announcer.backend_name();
    }

    #[test]
    fn announcing_with_an_interior_nul_is_reported_not_panicked() {
        // Exercised through Backend when one exists; otherwise the announcer
        // short-circuits. Either way, no panic.
        let mut announcer = Announcer::new();
        let _ = announcer.announce("bad\0text");
    }

    #[test]
    fn c_text_rejects_what_prismatoid_rejects() {
        assert!(matches!(c_text(""), Err(Error::EmptyText)));
        assert!(matches!(c_text("a\0b"), Err(Error::InteriorNul)));
        assert_eq!(c_text("ok").unwrap().as_bytes(), b"ok");
    }

    #[test]
    fn error_code_is_only_reported_for_native_errors() {
        assert_eq!(
            Error::Native {
                code: 6,
                message: "x".into()
            }
            .code(),
            Some(6)
        );
        assert_eq!(Error::NoBackend.code(), None);
        assert_eq!(Error::EmptyText.code(), None);
    }
}

#[cfg(test)]
mod feature_tests {
    use super::*;
    use prism_sys::features as bits;

    type Predicate = fn(Features) -> bool;

    #[test]
    fn every_predicate_reads_its_own_bit_and_no_other() {
        let cases: &[(Predicate, u64)] = &[
            (
                Features::is_supported_at_runtime,
                bits::IS_SUPPORTED_AT_RUNTIME,
            ),
            (Features::supports_speak, bits::SUPPORTS_SPEAK),
            (
                Features::supports_speak_to_memory,
                bits::SUPPORTS_SPEAK_TO_MEMORY,
            ),
            (Features::supports_braille, bits::SUPPORTS_BRAILLE),
            (Features::supports_output, bits::SUPPORTS_OUTPUT),
            (Features::supports_is_speaking, bits::SUPPORTS_IS_SPEAKING),
            (Features::supports_stop, bits::SUPPORTS_STOP),
            (Features::supports_pause, bits::SUPPORTS_PAUSE),
            (Features::supports_resume, bits::SUPPORTS_RESUME),
            (Features::supports_set_volume, bits::SUPPORTS_SET_VOLUME),
            (Features::supports_get_volume, bits::SUPPORTS_GET_VOLUME),
            (Features::supports_set_rate, bits::SUPPORTS_SET_RATE),
            (Features::supports_get_rate, bits::SUPPORTS_GET_RATE),
            (Features::supports_set_pitch, bits::SUPPORTS_SET_PITCH),
            (Features::supports_get_pitch, bits::SUPPORTS_GET_PITCH),
            (
                Features::supports_refresh_voices,
                bits::SUPPORTS_REFRESH_VOICES,
            ),
            (Features::supports_count_voices, bits::SUPPORTS_COUNT_VOICES),
            (
                Features::supports_get_voice_name,
                bits::SUPPORTS_GET_VOICE_NAME,
            ),
            (
                Features::supports_get_voice_language,
                bits::SUPPORTS_GET_VOICE_LANGUAGE,
            ),
            (Features::supports_get_voice, bits::SUPPORTS_GET_VOICE),
            (Features::supports_set_voice, bits::SUPPORTS_SET_VOICE),
            (Features::supports_get_channels, bits::SUPPORTS_GET_CHANNELS),
            (
                Features::supports_get_sample_rate,
                bits::SUPPORTS_GET_SAMPLE_RATE,
            ),
            (
                Features::supports_get_bit_depth,
                bits::SUPPORTS_GET_BIT_DEPTH,
            ),
            (
                Features::performs_silence_trimming_on_speak,
                bits::PERFORMS_SILENCE_TRIMMING_ON_SPEAK,
            ),
            (
                Features::performs_silence_trimming_on_speak_to_memory,
                bits::PERFORMS_SILENCE_TRIMMING_ON_SPEAK_TO_MEMORY,
            ),
            (Features::supports_speak_ssml, bits::SUPPORTS_SPEAK_SSML),
            (
                Features::supports_speak_to_memory_ssml,
                bits::SUPPORTS_SPEAK_TO_MEMORY_SSML,
            ),
        ];
        assert_eq!(cases.len(), 28, "one case per prismatoid feature");
        for (index, (predicate, bit)) in cases.iter().enumerate() {
            assert!(predicate(Features::from_bits(*bit)), "case {index} own bit");
            assert!(
                !predicate(Features::from_bits(!bit)),
                "case {index} every other bit"
            );
            assert!(!predicate(Features::default()), "case {index} nothing set");
            assert!(
                predicate(Features::from_bits(u64::MAX)),
                "case {index} all set"
            );
        }
    }

    #[test]
    fn the_game_picker_bits_are_where_prismatoid_puts_them() {
        // The four bits the Python speech layer reads on every backend it
        // considers: runtime support, output, speak, stop. Literal positions
        // rather than the constants so a shifted constant fails here.
        let usable = Features::from_bits(1 | (1 << 2) | (1 << 5) | (1 << 7));
        assert!(usable.is_supported_at_runtime());
        assert!(usable.supports_speak());
        assert!(usable.supports_output());
        assert!(usable.supports_stop());
        assert!(!usable.supports_set_rate());
        assert!(!usable.supports_set_voice());

        let sapi_like = Features::from_bits((1 << 12) | (1 << 14) | (1 << 10) | (1 << 21));
        assert!(sapi_like.supports_set_rate());
        assert!(sapi_like.supports_set_pitch());
        assert!(sapi_like.supports_set_volume());
        assert!(sapi_like.supports_set_voice());
        assert!(!sapi_like.supports_count_voices());
    }

    #[test]
    fn names_and_debug_list_only_the_set_bits() {
        let features = Features::from_bits(bits::SUPPORTS_STOP | bits::SUPPORTS_SET_PITCH);
        assert_eq!(
            features.names(),
            vec!["supports_stop", "supports_set_pitch"]
        );
        assert!(Features::default().names().is_empty());
        let debug = format!("{features:?}");
        assert!(debug.contains("supports_stop"), "{debug}");
        assert!(!debug.contains("supports_speak"), "{debug}");
        assert!(features.contains(bits::SUPPORTS_STOP));
        assert!(!features.contains(bits::SUPPORTS_STOP | bits::SUPPORTS_SPEAK));
        assert_eq!(features.bits(), (1 << 7) | (1 << 14));
    }
}

#[cfg(test)]
mod concurrency_tests {
    use super::*;

    #[test]
    fn acquiring_backends_from_many_threads_is_safe() {
        // Not start-up: `lifecycle_lock` serialises `Context::new` and the
        // shutdown in `Context`'s drop, so those cannot overlap however many
        // threads run here. What does overlap is the middle -- acquiring a
        // backend, initialising it, and freeing it all run unlocked -- and
        // that is where a shared registry or a backend's own initialise
        // could race. Eight threads is arbitrary; two would prove the same.
        //
        // A regression here does not fail a case, it takes the test binary
        // down, which is how the short `PrismConfig` announced itself.
        //
        // Nothing is spoken: on a developer machine `Announcer::new` attaches
        // to whichever screen reader is running, and announcing here made the
        // suite talk over it eight times on every run.
        let threads: Vec<_> = (0..8)
            .map(|_| {
                std::thread::spawn(|| {
                    let announcer = Announcer::new();
                    // Reaches the backend's feature flags, so a backend
                    // acquired on this thread is also used on it.
                    let _ = announcer.is_available();
                })
            })
            .collect();
        for thread in threads {
            thread
                .join()
                .expect("acquiring a Prism backend should not panic");
        }
    }

    #[test]
    fn a_context_may_be_started_again_after_being_dropped() {
        // Settings that rebuild the announcer take this path, and it is the
        // pattern that failed hardest under the short struct.
        for _ in 0..3 {
            if let Ok(context) = Context::new() {
                drop(context);
            }
        }
    }
}
