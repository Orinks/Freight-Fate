//! The backend layer under [`super::Speech`]: what a voice and a registry of
//! voices look like, Prism's implementation of both, and the selection
//! policy (`pick_backend`, `pick_event_backend`) that the Python module
//! wrote straight against `prism.Context`.
//!
//! The traits exist so the policy can be exercised against fake registries
//! (`tests/test_speech_audio.py` does that with `FakeContext`); they are
//! not an abstraction anyone else implements for real.

use std::fmt;

/// A Prism backend id (a 64-bit hash of the registry name).
pub type BackendId = prism::PrismBackendId;

/// A backend's feature flags, as named booleans.
///
/// The mirror of prismatoid's `BackendFeatures` dataclass, narrowed to the
/// bits the game reads. `is_supported_at_runtime` is the live check --
/// whether the screen reader or engine is reachable right now -- while every
/// `supports_*` says whether the backend implements that entry point at all.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct VoiceFeatures {
    pub is_supported_at_runtime: bool,
    pub supports_output: bool,
    pub supports_speak: bool,
    /// Can put text on a braille display by itself (NVDA and JAWS; a
    /// software voice such as SAPI cannot).
    pub supports_braille: bool,
    pub supports_stop: bool,
    pub supports_set_rate: bool,
    pub supports_set_pitch: bool,
    pub supports_set_volume: bool,
    pub supports_set_voice: bool,
    pub supports_count_voices: bool,
    pub supports_get_voice_name: bool,
}

impl VoiceFeatures {
    /// A voice that can speak right now and nothing more: the default shape
    /// of the Python tests' `FakeFeatures`.
    pub const SPEAKING: VoiceFeatures = VoiceFeatures {
        is_supported_at_runtime: true,
        supports_output: true,
        supports_speak: true,
        supports_braille: false,
        supports_stop: false,
        supports_set_rate: false,
        supports_set_pitch: false,
        supports_set_volume: false,
        supports_set_voice: false,
        supports_count_voices: false,
        supports_get_voice_name: false,
    };

    /// A fully adjustable software voice (SAPI, OneCore): speaks, stops, and
    /// takes rate, pitch, volume and voice.
    pub const ADJUSTABLE: VoiceFeatures = VoiceFeatures {
        supports_stop: true,
        supports_set_rate: true,
        supports_set_pitch: true,
        supports_set_volume: true,
        supports_set_voice: true,
        supports_count_voices: true,
        supports_get_voice_name: true,
        ..VoiceFeatures::SPEAKING
    };

    /// A running screen reader with a braille display (NVDA, JAWS): speaks,
    /// brailles, owns its own rate and voice.
    pub const BRAILLING: VoiceFeatures = VoiceFeatures {
        supports_braille: true,
        ..VoiceFeatures::SPEAKING
    };

    /// Whether voice selection is fully supported: pick, count and name.
    pub const fn selects_voices(self) -> bool {
        self.supports_set_voice && self.supports_count_voices && self.supports_get_voice_name
    }
}

impl From<prism::Features> for VoiceFeatures {
    fn from(features: prism::Features) -> Self {
        VoiceFeatures {
            is_supported_at_runtime: features.is_supported_at_runtime(),
            supports_output: features.supports_output(),
            supports_speak: features.supports_speak(),
            supports_braille: features.supports_braille(),
            supports_stop: features.supports_stop(),
            supports_set_rate: features.supports_set_rate(),
            supports_set_pitch: features.supports_set_pitch(),
            supports_set_volume: features.supports_set_volume(),
            supports_set_voice: features.supports_set_voice(),
            supports_count_voices: features.supports_count_voices(),
            supports_get_voice_name: features.supports_get_voice_name(),
        }
    }
}

/// One acquired voice: the subset of `prism.Backend` the game calls.
///
/// Errors are [`prism::Error`] for the real thing and for the fakes alike;
/// the speech layer logs and carries on, it never propagates them.
pub trait VoiceBackend {
    /// Registry name (`"NVDA"`, `"SAPI"`, `"UIA"`, ...).
    fn name(&self) -> String;
    fn features(&self) -> VoiceFeatures;
    /// Speech plus braille in one call; preferred when supported.
    fn output(&mut self, text: &str, interrupt: bool) -> Result<(), prism::Error>;
    /// Speech only.
    fn speak(&mut self, text: &str, interrupt: bool) -> Result<(), prism::Error>;
    /// Braille display only, no speech. Only meaningful when
    /// `features().supports_braille`; a backend without it answers `Err`.
    fn braille(&mut self, text: &str) -> Result<(), prism::Error>;
    fn stop(&mut self) -> Result<(), prism::Error>;
    fn set_rate(&mut self, rate: f64) -> Result<(), prism::Error>;
    fn set_pitch(&mut self, pitch: f64) -> Result<(), prism::Error>;
    fn set_volume(&mut self, volume: f64) -> Result<(), prism::Error>;
    fn voices_count(&self) -> Result<usize, prism::Error>;
    fn voice_name(&self, index: usize) -> Result<String, prism::Error>;
    fn set_voice(&mut self, index: usize) -> Result<(), prism::Error>;
}

/// The registry of voices a context knows: the subset of `prism.Context`
/// the game calls.
pub trait VoiceRegistry {
    fn backend_count(&self) -> usize;
    /// Id of the backend at `index` in registry order.
    fn id_at(&self, index: usize) -> Option<BackendId>;
    /// Id of the backend registered under `name`.
    fn id_by_name(&self, name: &str) -> Option<BackendId>;
    fn name_of(&self, id: BackendId) -> Option<String>;
    /// Prism's static priority: higher ranks first.
    fn priority_of(&self, id: BackendId) -> i32;
    /// Acquire (or re-acquire: Prism caches instances) the backend.
    fn acquire(&self, id: BackendId) -> Result<Box<dyn VoiceBackend>, prism::Error>;
    /// End a fresh-instance start (see [`PrismRegistry::new_fresh`]): from
    /// here on `acquire` hands out Prism's cached instances again.
    fn settle(&self) {}
}

impl fmt::Debug for dyn VoiceBackend {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("VoiceBackend")
            .field("name", &self.name())
            .finish()
    }
}

// -- Prism -------------------------------------------------------------------

/// A live Prism context as a [`VoiceRegistry`]. Main thread only (see the
/// module docs of [`crate::speech`]).
pub struct PrismRegistry {
    ctx: prism::Context,
    /// While set, `acquire` builds a NEW backend instance instead of taking
    /// Prism's cached one. Cleared by [`VoiceRegistry::settle`].
    fresh: std::cell::Cell<bool>,
}

impl PrismRegistry {
    /// Initialise Prism. `Err` when the native library is missing or refuses
    /// to start; the game then runs mute, as it does today.
    pub fn new() -> Result<Self, prism::Error> {
        Ok(Self::from_context(prism::Context::new()?))
    }

    /// Initialise Prism for a replacement speech worker.
    ///
    /// Prism caches one instance per backend id across contexts, so after a
    /// worker wedges inside a native call (Chris, 2026-09-03: a SAPI purge
    /// that never returned took both voices for the rest of the session), a
    /// replacement that merely re-acquired SAPI would inherit the very
    /// instance still stuck in that call. Until `settle`, every `acquire`
    /// here creates a fresh instance -- for SAPI, its own apartment thread
    /// and voice -- and the start-up selection runs on those. Afterwards
    /// the three-second re-probe uses the cache again: creating and tearing
    /// down a SAPI voice per probe is not a cost to pay forever.
    pub fn new_fresh() -> Result<Self, prism::Error> {
        let registry = Self::from_context(prism::Context::new()?);
        registry.fresh.set(true);
        Ok(registry)
    }

    /// Wrap a context the caller already created.
    pub fn from_context(ctx: prism::Context) -> Self {
        Self {
            ctx,
            fresh: std::cell::Cell::new(false),
        }
    }
}

impl VoiceRegistry for PrismRegistry {
    fn backend_count(&self) -> usize {
        self.ctx.backend_count()
    }

    fn id_at(&self, index: usize) -> Option<BackendId> {
        self.ctx.id_at(index)
    }

    fn id_by_name(&self, name: &str) -> Option<BackendId> {
        self.ctx.id_by_name(name)
    }

    fn name_of(&self, id: BackendId) -> Option<String> {
        self.ctx.name_of(id)
    }

    fn priority_of(&self, id: BackendId) -> i32 {
        self.ctx.priority_of(id)
    }

    fn acquire(&self, id: BackendId) -> Result<Box<dyn VoiceBackend>, prism::Error> {
        let backend = if self.fresh.get() {
            self.ctx.create(id)?
        } else {
            self.ctx.acquire(id)?
        };
        Ok(Box::new(PrismVoice { backend }))
    }

    fn settle(&self) {
        self.fresh.set(false);
    }
}

/// A Prism backend as a [`VoiceBackend`].
pub struct PrismVoice {
    backend: prism::Backend,
}

impl VoiceBackend for PrismVoice {
    fn name(&self) -> String {
        self.backend.name()
    }

    fn features(&self) -> VoiceFeatures {
        self.backend.features().into()
    }

    fn output(&mut self, text: &str, interrupt: bool) -> Result<(), prism::Error> {
        self.backend.output(text, interrupt)
    }

    fn speak(&mut self, text: &str, interrupt: bool) -> Result<(), prism::Error> {
        self.backend.speak(text, interrupt)
    }

    fn braille(&mut self, text: &str) -> Result<(), prism::Error> {
        self.backend.braille(text)
    }

    fn stop(&mut self) -> Result<(), prism::Error> {
        self.backend.stop()
    }

    fn set_rate(&mut self, rate: f64) -> Result<(), prism::Error> {
        self.backend.set_rate(rate as f32)
    }

    fn set_pitch(&mut self, pitch: f64) -> Result<(), prism::Error> {
        self.backend.set_pitch(pitch as f32)
    }

    fn set_volume(&mut self, volume: f64) -> Result<(), prism::Error> {
        self.backend.set_volume(volume as f32)
    }

    fn voices_count(&self) -> Result<usize, prism::Error> {
        self.backend.voices_count()
    }

    fn voice_name(&self, index: usize) -> Result<String, prism::Error> {
        self.backend.voice_name(index)
    }

    fn set_voice(&mut self, index: usize) -> Result<(), prism::Error> {
        self.backend.set_voice(index)
    }
}

// -- selection policy -------------------------------------------------------

/// True when the backend can actually speak on this machine right now.
pub fn usable(backend: &dyn VoiceBackend) -> bool {
    let features = backend.features();
    features.is_supported_at_runtime && (features.supports_output || features.supports_speak)
}

/// True when Windows Narrator is up.
///
/// Narrator has no client API of its own: Prism reaches it through UI
/// Automation notifications (the `UIA` backend), and only a running
/// Narrator reads those aloud. The backend cannot tell the difference --
/// it reports runtime support whenever UIA itself exists, which is every
/// modern Windows -- so the process check lives here.
#[cfg(windows)]
pub fn narrator_running() -> bool {
    use windows_sys::Win32::Foundation::{CloseHandle, INVALID_HANDLE_VALUE};
    use windows_sys::Win32::System::Diagnostics::ToolHelp::{
        CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, PROCESSENTRY32W,
        TH32CS_SNAPPROCESS,
    };

    // SAFETY: plain Toolhelp32 walk. The snapshot handle is closed on every
    // path out, and `entry` is a zeroed PROCESSENTRY32W with `dwSize` set
    // before the first call, as the API requires.
    unsafe {
        let snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if snapshot.is_null() || snapshot == INVALID_HANDLE_VALUE {
            return false;
        }
        let mut entry: PROCESSENTRY32W = std::mem::zeroed();
        entry.dwSize = std::mem::size_of::<PROCESSENTRY32W>() as u32;
        let mut found = Process32FirstW(snapshot, &mut entry) != 0;
        let mut running = false;
        while found {
            let len = entry
                .szExeFile
                .iter()
                .position(|&c| c == 0)
                .unwrap_or(entry.szExeFile.len());
            let exe = String::from_utf16_lossy(&entry.szExeFile[..len]);
            if exe.to_lowercase() == "narrator.exe" {
                running = true;
                break;
            }
            found = Process32NextW(snapshot, &mut entry) != 0;
        }
        CloseHandle(snapshot);
        running
    }
}

/// Narrator is a Windows program; elsewhere it is never running.
#[cfg(not(windows))]
pub fn narrator_running() -> bool {
    false
}

fn name_of(ctx: &dyn VoiceRegistry, id: BackendId) -> String {
    ctx.name_of(id).unwrap_or_else(|| id.to_string())
}

/// Choose a speech backend from a registry.
///
/// Prism's `acquire_best` is unsuitable: it returns the highest-priority
/// backend that merely has a live cached instance -- which is whatever this
/// game already holds, so a screen reader started mid-session would never be
/// noticed -- and otherwise ranks by static registry priority whether or not
/// that screen reader is running. Instead, enumerate the registry in
/// priority order and validate every candidate against its live runtime
/// check. The `UIA` backend (Narrator's route) claims runtime support
/// unconditionally, so it is skipped unless Narrator is actually running,
/// and even then ranked last (see [`super::UIA_LAST_RESORT_PRIORITY`]).
/// Returns `None` when nothing on the machine can speak.
pub fn pick_backend(
    ctx: &dyn VoiceRegistry,
    override_name: Option<&str>,
) -> Option<Box<dyn VoiceBackend>> {
    pick_backend_gated(ctx, override_name, narrator_running)
}

/// [`pick_backend`] with the Narrator probe supplied, so the policy can be
/// tested against a fake registry with and without Narrator "running".
pub fn pick_backend_gated(
    ctx: &dyn VoiceRegistry,
    override_name: Option<&str>,
    narrator_probe: fn() -> bool,
) -> Option<Box<dyn VoiceBackend>> {
    if let Some(name) = override_name.filter(|name| !name.is_empty()) {
        match ctx.id_by_name(name).map(|id| ctx.acquire(id)) {
            Some(Ok(backend)) => {
                if usable(backend.as_ref()) {
                    return Some(backend);
                }
                log::warn!(
                    "Requested speech backend {name} is not usable; falling back to automatic choice"
                );
            }
            Some(Err(err)) => {
                log::warn!(
                    "Requested speech backend {name} not found; falling back to automatic choice: {err}"
                );
            }
            None => {
                log::warn!(
                    "Requested speech backend {name} not found; falling back to automatic choice"
                );
            }
        }
    }
    // The probe runs once per pick, not per candidate: one process scan per
    // 3 s health check is free, one per backend is not.
    let narrator = narrator_probe();
    let mut candidates: Vec<(i32, BackendId)> = Vec::new();
    for index in 0..ctx.backend_count() {
        let Some(backend_id) = ctx.id_at(index) else {
            continue;
        };
        let name = name_of(ctx, backend_id);
        let priority = if name == "UIA" {
            if !narrator {
                continue;
            }
            super::UIA_LAST_RESORT_PRIORITY
        } else {
            ctx.priority_of(backend_id)
        };
        candidates.push((priority, backend_id));
    }
    // Python's `list.sort(reverse=True)` is stable: equal priorities keep
    // registry order, so the first-registered of a tie still wins here.
    candidates.sort_by_key(|(priority, _)| std::cmp::Reverse(*priority));
    for (_, backend_id) in candidates {
        let Ok(backend) = ctx.acquire(backend_id) else {
            continue;
        };
        if usable(backend.as_ref()) {
            return Some(backend);
        }
    }
    None
}

/// A second, independent voice for driving events.
///
/// Screen readers interrupt the game's speech with their own chatter, so
/// critical announcements (hazards, warnings) can be cut off mid-sentence.
/// Routing events through a dedicated software voice (SAPI on Windows,
/// AVSpeech on macOS, Speech Dispatcher on Linux) keeps the two streams
/// from talking over each other. Returns `None` when the main channel
/// already is that backend (nothing to separate) or it is unusable, in
/// which case events fall back to the main channel.
pub fn pick_event_backend(
    ctx: &dyn VoiceRegistry,
    main_backend: Option<&dyn VoiceBackend>,
    name: &str,
) -> Option<Box<dyn VoiceBackend>> {
    let main_backend = main_backend?;
    if main_backend.name() == name {
        return None;
    }
    let backend = match ctx.id_by_name(name).map(|id| ctx.acquire(id)) {
        Some(Ok(backend)) => backend,
        Some(Err(err)) => {
            log::info!("Event speech backend {name} not available: {err}");
            return None;
        }
        None => {
            log::info!("Event speech backend {name} not available");
            return None;
        }
    };
    usable(backend.as_ref()).then_some(backend)
}

/// Some backends, notably OneCore, use their own native default pitch.
///
/// Prism reports that default as NaN on Windows. Forcing the neutral settings
/// value onto it changes the sound, so leave pitch untouched until the player
/// deliberately moves the setting away from the midpoint.
pub fn preserve_backend_default_pitch(backend: &dyn VoiceBackend, value: f64) -> bool {
    let name = backend.name().to_lowercase();
    (name == "onecore" || name == "one_core") && value == 0.5
}
