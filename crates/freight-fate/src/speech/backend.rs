//! The backend layer under [`super::Speech`]: what a voice and a registry of
//! voices look like, Prism's implementation of both, and the selection
//! policy (`pick_backend`, `pick_event_backend`) that the Python module
//! wrote straight against `prism.Context`.
//!
//! The traits exist so the policy can be exercised against fake registries
//! (`tests/test_speech_audio.py` does that with `FakeContext`); they are
//! not an abstraction anyone else implements for real.

use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::fmt;
use std::rc::Rc;

#[cfg(test)]
#[path = "backend/recovery_tests.rs"]
mod recovery_tests;

/// A Prism backend id (a 64-bit hash of the registry name).
pub type BackendId = u64;

/// What a Prism call, or a fake standing in for one, can fail with.
pub type SpeechError = prismer::Error;

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

impl From<prismer::Features> for VoiceFeatures {
    fn from(features: prismer::Features) -> Self {
        use prismer::Features as F;
        let has = |flag: F| features.contains(flag);
        VoiceFeatures {
            is_supported_at_runtime: has(F::IS_SUPPORTED_AT_RUNTIME),
            supports_output: has(F::OUTPUT),
            supports_speak: has(F::SPEAK),
            supports_braille: has(F::BRAILLE),
            supports_stop: has(F::STOP),
            supports_set_rate: has(F::SET_RATE),
            supports_set_pitch: has(F::SET_PITCH),
            supports_set_volume: has(F::SET_VOLUME),
            supports_set_voice: has(F::SET_VOICE),
            supports_count_voices: has(F::COUNT_VOICES),
            supports_get_voice_name: has(F::GET_VOICE_NAME),
        }
    }
}

/// One acquired voice: the subset of `prism.Backend` the game calls.
///
/// Errors are [`SpeechError`] for the real thing and for the fakes alike;
/// the speech layer logs and carries on, it never propagates them.
pub trait VoiceBackend {
    /// Registry name (`"NVDA"`, `"SAPI"`, `"UIA"`, ...).
    fn name(&self) -> String;
    fn features(&self) -> VoiceFeatures;
    /// Speech plus braille in one call; preferred when supported.
    fn output(&mut self, text: &str, interrupt: bool) -> Result<(), SpeechError>;
    /// Speech only.
    fn speak(&mut self, text: &str, interrupt: bool) -> Result<(), SpeechError>;
    /// Braille display only, no speech. Only meaningful when
    /// `features().supports_braille`; a backend without it answers `Err`.
    fn braille(&mut self, text: &str) -> Result<(), SpeechError>;
    fn stop(&mut self) -> Result<(), SpeechError>;
    fn set_rate(&mut self, rate: f64) -> Result<(), SpeechError>;
    fn set_pitch(&mut self, pitch: f64) -> Result<(), SpeechError>;
    fn set_volume(&mut self, volume: f64) -> Result<(), SpeechError>;
    fn voices_count(&self) -> Result<usize, SpeechError>;
    fn voice_name(&self, index: usize) -> Result<String, SpeechError>;
    fn set_voice(&mut self, index: usize) -> Result<(), SpeechError>;
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
    fn acquire(&self, id: BackendId) -> Result<Box<dyn VoiceBackend>, SpeechError>;
    /// Finish startup. Recovery registries retain their private instances
    /// for settings replay and every later health check.
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

/// A live Prism context as a [`VoiceRegistry`]. Confined to the worker that
/// created it (see the module docs of [`crate::speech`]).
pub struct PrismRegistry {
    shared: Rc<PrismShared>,
}

/// The context and every instance taken from it, owned together.
///
/// prismer ties a backend's lifetime to the context it came from, while a
/// [`PrismVoice`] is handed out as a `'static` box. Each voice therefore holds
/// this whole owner by `Rc`, so the context outlives every backend by
/// construction rather than by drop order in the caller.
struct PrismShared {
    // Declared before `ctx`: fields drop in order, so every backend is freed
    // before the context that created it.
    instances: BackendInstances<prismer::Backend<'static>>,
    ctx: Box<prismer::Prism>,
}

/// Select native acquisition independently of the external native calls.
struct BackendInstances<T> {
    fresh: Cell<bool>,
    private: RefCell<HashMap<BackendId, Rc<RefCell<T>>>>,
}

impl<T> BackendInstances<T> {
    fn new(fresh: bool) -> Self {
        Self {
            fresh: Cell::new(fresh),
            private: RefCell::new(HashMap::new()),
        }
    }

    /// One native instance per backend id for this registry's lifetime: the
    /// first request goes to Prism (`acquire` for an ordinary worker, `create`
    /// for a replacement one) and every later request reuses it.
    ///
    /// Re-acquiring on every request is what leaked: Prism 0.18.2's OneCore
    /// backend loses a USER object, two handles and about 30 KiB on each
    /// acquire-and-free cycle, and the 3 s health probe re-acquires whatever
    /// it inspects -- the main voice itself when no screen reader is running
    /// and OneCore is the automatic choice, and every option when the event
    /// voices are enumerated. Prism hands out the same cached instance on each
    /// acquire anyway, so holding it changes nothing about what speaks. A
    /// failed acquire is not remembered: a screen reader that starts later is
    /// found on the next probe.
    fn acquire(
        &self,
        id: BackendId,
        create: impl FnOnce(BackendId) -> Result<T, SpeechError>,
        acquire: impl FnOnce(BackendId) -> Result<T, SpeechError>,
    ) -> Result<Rc<RefCell<T>>, SpeechError> {
        if let Some(backend) = self.private.borrow().get(&id) {
            return Ok(Rc::clone(backend));
        }
        let backend = if self.fresh.get() {
            create(id)?
        } else {
            acquire(id)?
        };
        let backend = Rc::new(RefCell::new(backend));
        self.private.borrow_mut().insert(id, Rc::clone(&backend));
        Ok(backend)
    }

    fn settle(&self) {}
}

impl PrismShared {
    /// Create or acquire the backend, then initialize it. prismer hands both
    /// back uninitialized (or, from the shared cache, possibly initialized
    /// already, which counts as success).
    fn open(&self, id: BackendId, fresh: bool) -> Result<prismer::Backend<'static>, SpeechError> {
        let id = prismer::BackendId(id);
        let backend = if fresh {
            self.ctx.create(id)?
        } else {
            self.ctx.acquire(id)?
        };
        match backend.initialize() {
            Ok(()) | Err(prismer::Error::AlreadyInitialized) => {}
            Err(err) => return Err(err),
        }
        // SAFETY: the borrow is of `*self.ctx`, a boxed context that never
        // moves and is dropped only with this `PrismShared`, after the
        // `instances` field that owns every backend (fields drop in
        // declaration order). Each `PrismVoice` holds this owner by `Rc`, so
        // no backend can be reached after its context is gone.
        Ok(unsafe {
            std::mem::transmute::<prismer::Backend<'_>, prismer::Backend<'static>>(backend)
        })
    }
}

impl PrismRegistry {
    /// Initialise Prism. `Err` when Prism refuses to start; the game then
    /// runs mute.
    pub fn new() -> Result<Self, SpeechError> {
        Self::with_fresh(false)
    }

    /// Initialise Prism for a replacement speech worker.
    ///
    /// Prism caches one instance per backend id across contexts, so after a
    /// worker wedges inside a native call (Chris, 2026-09-03: a SAPI purge
    /// that never returned took both voices for the rest of the session), a
    /// replacement that merely re-acquired SAPI would inherit the very
    /// instance still stuck in that call. Each backend id gets one private
    /// instance -- for SAPI, its own apartment thread and voice. Startup,
    /// settings replay and later probes reuse those private instances for
    /// this registry's entire lifetime, without returning to the shared cache.
    /// (An ordinary registry also holds each instance for its lifetime; the
    /// difference is only whether the first one comes from Prism's shared
    /// cache or is created privately.)
    pub fn new_fresh() -> Result<Self, SpeechError> {
        Self::with_fresh(true)
    }

    fn with_fresh(fresh: bool) -> Result<Self, SpeechError> {
        Ok(Self {
            shared: Rc::new(PrismShared {
                instances: BackendInstances::new(fresh),
                ctx: Box::new(prismer::Prism::new()?),
            }),
        })
    }
}

impl VoiceRegistry for PrismRegistry {
    fn backend_count(&self) -> usize {
        self.shared.ctx.backend_count()
    }

    fn id_at(&self, index: usize) -> Option<BackendId> {
        self.shared.ctx.backend_ids().get(index).map(|id| id.0)
    }

    fn id_by_name(&self, name: &str) -> Option<BackendId> {
        self.shared.ctx.backend_id_by_name(name).ok().map(|id| id.0)
    }

    fn name_of(&self, id: BackendId) -> Option<String> {
        self.shared.ctx.backend_name(prismer::BackendId(id))
    }

    fn priority_of(&self, id: BackendId) -> i32 {
        self.shared.ctx.backend_priority(prismer::BackendId(id))
    }

    fn acquire(&self, id: BackendId) -> Result<Box<dyn VoiceBackend>, SpeechError> {
        let shared = &self.shared;
        let backend = shared.instances.acquire(
            id,
            |id| shared.open(id, true),
            |id| shared.open(id, false),
        )?;
        Ok(Box::new(PrismVoice {
            backend,
            _owner: Rc::clone(shared),
        }))
    }

    fn settle(&self) {
        self.shared.instances.settle();
    }
}

/// A Prism backend as a [`VoiceBackend`].
pub struct PrismVoice {
    // Declared before `_owner`, so this handle is released before the last
    // reference to the context can go.
    backend: Rc<RefCell<prismer::Backend<'static>>>,
    _owner: Rc<PrismShared>,
}

impl VoiceBackend for PrismVoice {
    fn name(&self) -> String {
        self.backend.borrow().name()
    }

    fn features(&self) -> VoiceFeatures {
        self.backend.borrow().features().into()
    }

    fn output(&mut self, text: &str, interrupt: bool) -> Result<(), SpeechError> {
        non_empty(text)?;
        self.backend.borrow().output(text, interrupt)
    }

    fn speak(&mut self, text: &str, interrupt: bool) -> Result<(), SpeechError> {
        non_empty(text)?;
        self.backend.borrow().speak(text, interrupt)
    }

    fn braille(&mut self, text: &str) -> Result<(), SpeechError> {
        non_empty(text)?;
        self.backend.borrow().braille(text)
    }

    fn stop(&mut self) -> Result<(), SpeechError> {
        self.backend.borrow().stop()
    }

    fn set_rate(&mut self, rate: f64) -> Result<(), SpeechError> {
        self.backend.borrow().set_rate(rate as f32)
    }

    fn set_pitch(&mut self, pitch: f64) -> Result<(), SpeechError> {
        self.backend.borrow().set_pitch(pitch as f32)
    }

    fn set_volume(&mut self, volume: f64) -> Result<(), SpeechError> {
        self.backend.borrow().set_volume(volume as f32)
    }

    fn voices_count(&self) -> Result<usize, SpeechError> {
        self.backend.borrow().voice_count()
    }

    fn voice_name(&self, index: usize) -> Result<String, SpeechError> {
        self.backend.borrow().voice_name(index)
    }

    fn set_voice(&mut self, index: usize) -> Result<(), SpeechError> {
        self.backend.borrow().set_voice(index)
    }
}

/// Empty text never reaches Prism, as prismatoid refused it
/// (`Text MUST NOT be empty`).
fn non_empty(text: &str) -> Result<(), SpeechError> {
    if text.is_empty() {
        Err(prismer::Error::InvalidParam)
    } else {
        Ok(())
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
