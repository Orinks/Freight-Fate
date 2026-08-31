//! The [`AudioEngine`] facade: backend selection, the jake voice routing,
//! round-robin banks, the asset-existence cache and the held-alert /
//! held-cue dead man's switches -- everything the Python `AudioEngine`
//! class did on top of its backend.

use std::collections::HashMap;

use ff_core::assets_pack::generated_sound;
use ff_core::pyrandom::PyRandom;

use super::{
    asset_bytes, Audio, AudioBackend, AudioError, BassBackend, Buses, KeyProbe, NullBackend,
    SustainLoopSpec, VolumeUpdate, ALERT_HOLD_TIMEOUT_S, BASS_NO_SOUND_DEVICE, CH_AIR, CH_ALERT,
    CH_AMBIENT, CH_EDGE, CH_HORN, CH_JAKE, CH_RADIO_FX, CH_ROAD, CH_WEATHER, CH_WEATHER_B,
    CUE_HOLD_TIMEOUT_S, HORN_LOOP, JAKE_BAND_PREFIX, JAKE_CLASSIC_KEY, JAKE_RECORDED_KEY,
    SFX_EXTENSIONS,
};

/// Facade over the active backend; the rest of the game talks only to this.
pub struct AudioEngine {
    backend: Box<dyn AudioBackend>,
    banks: HashMap<String, Vec<String>>, // base -> discovered numbered keys
    bank_order: HashMap<String, Vec<String>>, // base -> remaining shuffled cuts
    last_bank_key: HashMap<String, String>, // base -> cut played last
    asset_known: HashMap<String, bool>,  // key -> resolves anywhere
    logged_volumes: Option<VolumeUpdate>,
    alert_hold_key: String,          // continuous alert tone being re-asserted
    alert_hold_s: f64,               // time left before the hold lapses
    cue_holds: HashMap<String, f64>, // caller-owned held cues, name -> time left
    jake_voice_classic: bool,        // Settings: real (recorded) or classic (synth)
    rng: PyRandom,
    // Test seam: the asset universe `has_asset` and `play_bank` probe, in
    // place of the real pack-and-loose lookup (the Python tests monkeypatched
    // `_asset_bytes` for the same purpose).
    asset_probe: Option<KeyProbe>,
    // This run asked for sound and did not get it, and nobody has told the
    // player yet. Cleared by `take_silence_notice`.
    silence_notice: bool,
    // The deferred device probe (`new_deferred`): the worker thread opening
    // the output device reports here, and `update` finishes the swap on the
    // game thread. `None` once settled -- which is also the constructed
    // state of every other constructor.
    probe: Option<std::sync::mpsc::Receiver<Result<bool, bass_sys::safe::BassError>>>,
    // Environment read once at construction, so settling does not re-read
    // it on a different answer.
    probe_headless: bool,
    // While the probe is out, the null backend is a black hole: remember
    // the requests the real backend must honour the moment it arrives.
    replay_music: Option<MusicReplay>,
    replay_engine_voice: Option<bool>,
}

/// The music request to re-issue when the deferred backend arrives.
enum MusicReplay {
    Track { track: String, fade_ms: u32 },
    File { path: String, fade_ms: u32 },
    Radio { url: String, fade_ms: u32 },
}

impl Default for AudioEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioEngine {
    /// Pick the backend from `FREIGHT_FATE_AUDIO_BACKEND` and build the facade.
    pub fn new() -> Self {
        let pref = std::env::var("FREIGHT_FATE_AUDIO_BACKEND").unwrap_or_default();
        Self::from_preference(&pref)
    }

    /// Build the facade on an explicit backend preference (`""` or `"bass"`
    /// tries BASS first; anything else is the null backend).
    pub fn from_preference(pref: &str) -> Self {
        let (backend, silent) = pick_backend(pref);
        let mut engine = Self::with_backend(backend);
        engine.silence_notice = silent;
        log::info!("Audio backend: {}", engine.backend.name());
        engine
    }

    /// The facade over a backend the caller built -- a test double, or a
    /// backend constructed with options the environment does not express.
    pub fn with_backend(backend: Box<dyn AudioBackend>) -> Self {
        Self {
            backend,
            banks: HashMap::new(),
            bank_order: HashMap::new(),
            last_bank_key: HashMap::new(),
            asset_known: HashMap::new(),
            logged_volumes: None,
            alert_hold_key: String::new(),
            alert_hold_s: 0.0,
            cue_holds: HashMap::new(),
            jake_voice_classic: false,
            rng: PyRandom::new_unseeded(),
            asset_probe: None,
            silence_notice: false,
            probe: None,
            probe_headless: false,
            replay_music: None,
            replay_engine_voice: None,
        }
    }

    /// Like [`new`](Self::new), but the slow half -- loading the BASS
    /// natives and opening the output device -- runs on a worker thread
    /// while the game starts on the null backend. `update` swaps the real
    /// backend in when the probe lands, usually within the first second;
    /// on the machine where the device open hangs, the boot keeps reading
    /// input instead of sitting deaf (the reported 16-second stall).
    ///
    /// Costs during the window: transient one-shots are dropped (menu
    /// earcons, at worst), and the "no sound on this computer" notice
    /// arrives a beat after the menu instead of inside its greeting.
    /// Music, volumes and the engine-voice setting are remembered and
    /// re-issued on arrival.
    pub fn new_deferred() -> Self {
        let pref = std::env::var("FREIGHT_FATE_AUDIO_BACKEND").unwrap_or_default();
        let trimmed = pref.trim().to_ascii_lowercase();
        if !(trimmed.is_empty() || trimmed == "bass") {
            // Anything else resolves to the null backend without touching a
            // device; nothing to defer.
            return Self::from_preference(&pref);
        }
        let (tx, rx) = std::sync::mpsc::channel();
        std::thread::Builder::new()
            .name("audio-probe".into())
            .spawn(move || {
                let _ = tx.send(BassBackend::preopen_device());
            })
            .expect("spawn audio probe thread");
        let mut engine = Self::with_backend(Box::new(NullBackend::new()));
        engine.probe = Some(rx);
        engine.probe_headless = BassBackend::headless_requested();
        engine
    }

    /// Finish a deferred boot: the probe's verdict is in, so build the real
    /// backend on this thread (the device is already open, so this is
    /// instant) and swap it in.
    fn settle_probe(&mut self, outcome: Result<bool, bass_sys::safe::BassError>) {
        let no_sound_fallback = match outcome {
            Ok(fallback) => fallback,
            Err(err) => {
                log::warn!("BASS unavailable ({err}); running silent");
                self.silence_notice = !self.probe_headless;
                log::info!("Audio backend: {}", self.backend.name());
                return;
            }
        };
        // The worker may have landed on the no-sound device; finishing with
        // `new_headless` re-opens exactly that one instead of probing the
        // broken default device all over again on this thread.
        let built = if no_sound_fallback {
            BassBackend::new_headless()
        } else {
            BassBackend::new()
        };
        match built {
            Ok(backend) => {
                let deaf = !self.probe_headless
                    && (no_sound_fallback
                        || backend.output_device() == BASS_NO_SOUND_DEVICE as u32);
                self.adopt_backend(Box::new(backend), deaf);
            }
            Err(err) => {
                log::warn!("BASS unavailable ({err}); running silent");
                self.silence_notice = !self.probe_headless;
            }
        }
        log::info!("Audio backend: {}", self.backend.name());
    }

    /// Swap in a late-arriving backend and bring it up to date with what
    /// the game asked for while the null backend was standing in.
    fn adopt_backend(&mut self, backend: Box<dyn AudioBackend>, deaf: bool) {
        // Everything cached against the stand-in is a lie to the new
        // backend: `has_asset` answered from the null backend's universe,
        // and a menu cue cached as missing there would stay silent forever.
        self.asset_known.clear();
        self.banks.clear();
        self.bank_order.clear();
        self.last_bank_key.clear();
        self.backend = backend;
        self.silence_notice = deaf;
        if let Some(volumes) = self.logged_volumes {
            self.backend.set_volumes(&volumes);
        }
        if let Some(classic) = self.replay_engine_voice.take() {
            self.backend.set_engine_voice_classic(classic);
        }
        match self.replay_music.take() {
            Some(MusicReplay::Track { track, fade_ms }) => self.backend.play_music(&track, fade_ms),
            Some(MusicReplay::File { path, fade_ms }) => {
                let _ = self.backend.play_music_file(&path, fade_ms);
            }
            Some(MusicReplay::Radio { url, fade_ms }) => {
                let _ = self.backend.play_radio_stream(&url, fade_ms);
            }
            None => {}
        }
    }

    /// Arm (or disarm) the "this run has no sound" notice by hand.
    ///
    /// Only [`from_preference`](Self::from_preference) arms it for real, from
    /// what the environment actually gave the player. A caller-built engine --
    /// a test double, a headless run -- is silent on purpose and says nothing,
    /// so a test that wants the notice asks for it here.
    pub fn set_silence_notice(&mut self, pending: bool) {
        self.silence_notice = pending;
    }

    /// The active backend.
    pub fn backend(&self) -> &dyn AudioBackend {
        self.backend.as_ref()
    }

    pub fn backend_mut(&mut self) -> &mut dyn AudioBackend {
        self.backend.as_mut()
    }

    /// The BASS backend, when that is what is active.
    pub fn bass(&self) -> Option<&BassBackend> {
        self.backend.as_any().downcast_ref::<BassBackend>()
    }

    pub fn bass_mut(&mut self) -> Option<&mut BassBackend> {
        self.backend.as_any_mut().downcast_mut::<BassBackend>()
    }

    /// The volume buses of the active backend.
    pub fn buses(&self) -> &Buses {
        self.backend.buses()
    }

    /// Replace the asset-existence probe `has_asset` and `play_bank` use
    /// (`None` restores the real lookup). Test seam; answers already cached
    /// stand, as they did under the Python monkeypatch.
    pub fn set_asset_probe(&mut self, probe: Option<KeyProbe>) {
        self.asset_probe = probe;
    }

    pub fn jake_voice_classic(&self) -> bool {
        self.jake_voice_classic
    }

    fn asset_exists(&self, key: &str) -> bool {
        match &self.asset_probe {
            Some(probe) => probe(key),
            None => asset_bytes(key, SFX_EXTENSIONS).is_some(),
        }
    }

    /// Route a sound key through the player's chosen jake voice.
    ///
    /// Every caller -- the real drive and the Learn game sounds demo alike --
    /// asks for `engine/jake_1600` by name; this is the one place that swaps
    /// it for the classic synth cut when the setting calls for it, so
    /// neither call site needs to know the A/B exists.
    fn route_voice_key(&self, key: &str) -> String {
        if key == JAKE_CLASSIC_KEY {
            // Asked for the classic cut BY NAME -- the Learn game sounds entry
            // that exists to demo it. Never re-voiced, or the demo of one
            // voice would play the other.
            return key.to_string();
        }
        if !key.starts_with(JAKE_BAND_PREFIX) {
            return key.to_string();
        }
        // ONE voice per setting, whatever the rpm -- and that is true in BOTH
        // directions, which is what took three goes to get right.
        //
        // There is exactly one real jake recording (engine/jake_1600) and one
        // synth cut kept from before it (engine/jake_1600_synth). The other
        // five band files -- 1200, 1400, 1800, 2000, 2200 -- are all synths.
        //
        // 2026-08-17 fixed the classic direction: every band maps to the
        // synth, so "classic" stopped meaning "synth at 1600, Jerry's
        // recording everywhere else". The REAL direction was left alone, and
        // it had the same fault in mirror image -- band keys passed straight
        // through, so "real" meant the recording at 1600 and a synth at every
        // other band. Rpm moves constantly on a descent, so the two voices
        // alternated and the owner heard both, whichever setting he chose
        // (2026-08-19: "both the synth and the recording play when the jake is
        // used despite the setting").
        //
        // The single recording therefore stands for every band on "real", the
        // way the single synth already stood for every band on "classic".
        // Level still tracks rpm and retard stage (JAKE_STAGE_GAIN), so the
        // growl still answers the grade; what it no longer does is change
        // voice halfway down one.
        if self.jake_voice_classic {
            JAKE_CLASSIC_KEY.to_string()
        } else {
            JAKE_RECORDED_KEY.to_string()
        }
    }

    /// Discover a numbered round-robin bank (`base_01`..) once, cached.
    fn bank_keys(&mut self, base: &str) -> Vec<String> {
        if let Some(keys) = self.banks.get(base) {
            return keys.clone();
        }
        let mut keys = Vec::new();
        for i in 1..100 {
            let key = format!("{base}_{i:02}");
            if !self.asset_exists(&key) {
                break;
            }
            keys.push(key);
        }
        self.banks.insert(base.to_string(), keys.clone());
        keys
    }
}

/// The backend `FREIGHT_FATE_AUDIO_BACKEND` asks for: "" or "bass" tries BASS
/// and falls back to the null backend; anything else (the Python build's
/// "pygame") is the null backend outright.
/// The backend for a preference, and whether this run wanted sound and is
/// not going to get any.
///
/// Running on rather than failing to start is deliberate (README: "If BASS is
/// unavailable, the game continues with a silent audio backend rather than
/// failing to start"). Doing it without a word to the player is not: a driver
/// who cannot see a log has no way to tell a broken install from a broken
/// game. So the fallback still happens, and the second half of the pair is
/// what the main menu says out loud.
///
/// A run that ASKED to be silent -- `SDL_AUDIODRIVER=dummy`, headless CI,
/// the playtest harness -- got what it asked for and is told nothing.
fn pick_backend(pref: &str) -> (Box<dyn AudioBackend>, bool) {
    let pref = pref.trim().to_ascii_lowercase();
    let headless = BassBackend::headless_requested();
    if pref.is_empty() || pref == "bass" {
        match BassBackend::new() {
            Ok(backend) => {
                // BASS came up, but possibly on its no-sound device: the
                // device open failed and it fell back inside `new`. That is
                // audibly identical to no backend at all.
                let deaf = !headless && backend.output_device() == BASS_NO_SOUND_DEVICE as u32;
                return (Box::new(backend), deaf);
            }
            Err(err) => log::warn!("BASS unavailable ({err}); running silent"),
        }
        return (Box::new(NullBackend::new()), !headless);
    }
    if pref == "pygame" {
        log::warn!("FREIGHT_FATE_AUDIO_BACKEND=pygame: the pygame mixer is not part of this build; running silent");
    }
    (Box::new(NullBackend::new()), false)
}

impl Audio for AudioEngine {
    fn enabled(&self) -> bool {
        self.backend.enabled()
    }

    fn backend_name(&self) -> &str {
        self.backend.name()
    }

    fn take_silence_notice(&mut self) -> bool {
        std::mem::take(&mut self.silence_notice)
    }

    fn master_volume(&self) -> f64 {
        self.backend.buses().master
    }

    fn sfx_volume(&self) -> f64 {
        self.backend.buses().sfx
    }

    fn music_volume(&self) -> f64 {
        self.backend.buses().music
    }

    fn weather_volume(&self) -> f64 {
        self.backend.buses().weather
    }

    fn engine_volume(&self) -> f64 {
        self.backend.buses().engine
    }

    fn ui_volume(&self) -> f64 {
        self.backend.buses().ui
    }

    fn engine_running(&self) -> bool {
        self.backend.engine_running()
    }

    fn engine_starting(&self) -> bool {
        self.backend.engine_starting()
    }

    /// Public because a caller that caches "which cut is playing" has to
    /// cache the ROUTED key. Caching the band key instead meant that on the
    /// classic voice -- where every band maps to the one synth cut -- each
    /// rpm band change looked like a new sound and restarted the same file
    /// over itself, 120 ms of crossfade at a time, all the way down a grade.
    fn voice_key(&self, key: &str) -> String {
        self.route_voice_key(key)
    }

    fn play_with(&mut self, key: &str, volume: f64, pan: f64) {
        let key = self.route_voice_key(key);
        self.backend.play(&key, volume, pan);
    }

    /// Real mechanical events never sound twice the same, so banked cuts
    /// (`base_01`..`base_NN`, the licensed overlay) play in a shuffled cycle
    /// -- every cut once before any repeats, never the same cut twice in a
    /// row. A clean clone without the bank keeps the single classic cue.
    fn play_bank_with(&mut self, base: &str, fallback: &str, volume: f64, pan: f64) {
        let keys = self.bank_keys(base);
        if keys.is_empty() {
            self.play_with(fallback, volume, pan);
            return;
        }
        let mut order = self.bank_order.remove(base).unwrap_or_default();
        if order.is_empty() {
            order = self.rng.sample(&keys, keys.len());
            // A fresh shuffle may lead with the cut that just played; swap it
            // to the back so no cut ever sounds twice in a row.
            if order.len() > 1 && self.last_bank_key.get(base) == Some(&order[0]) {
                let last = order.len() - 1;
                order.swap(0, last);
            }
        }
        let key = order.remove(0);
        self.bank_order.insert(base.to_string(), order);
        self.last_bank_key.insert(base.to_string(), key.clone());
        // Per-trigger level jitter, ~±1.4 dB: no two clunks land identically.
        let jitter = self.rng.uniform(0.85, 1.17);
        self.play_with(&key, volume * jitter, pan);
    }

    /// Shift-gap disengage: scale the engine bed below the load floor.
    ///
    /// 1.0 is normal running; the drive loop drops it through a shift's
    /// torque interrupt so the engine genuinely falls away, then eases it
    /// back as the clutch hooks up.
    fn set_engine_duck(&mut self, duck: f64) {
        self.backend.set_engine_duck(duck);
    }

    /// Step engine, weather, and music (the radio's slot) down under the
    /// event voice and back: 1.0 is the normal mix, [`SPEECH_DUCK_LEVEL`]
    /// while the road is talking. The player's volume settings are never
    /// touched -- the factor rides on top of them and every reapplication
    /// (a settings change, a new loop) keeps honoring it until the caller
    /// restores 1.0.
    fn set_speech_duck(&mut self, duck: f64) {
        self.backend.set_speech_duck(duck);
    }

    /// Pick the engine voice: the recorded multisample ring or the classic
    /// single pitched loop (BASS backend; the null backend has no model).
    ///
    /// Applies live -- a running engine re-voices in place at its current
    /// rpm without replaying the ignition crank, so the Settings toggle is
    /// an instant A/B.
    fn set_engine_voice(&mut self, classic: bool) {
        if self.probe.is_some() {
            // The null stand-in has no voice model; keep the setting for the
            // backend on its way.
            self.replay_engine_voice = Some(classic);
        }
        match self.backend.engine_voice_classic() {
            None => return,
            Some(current) if current == classic => {
                self.backend.set_engine_voice_classic(classic);
                return;
            }
            Some(_) => {}
        }
        self.backend.set_engine_voice_classic(classic);
        if self.backend.engine_running() {
            let (rpm, throttle) = self.backend.engine_last_rpm_throttle();
            self.backend.engine_stop(false);
            self.backend.engine_start(false);
            self.backend.set_engine_rpm(rpm, throttle);
        }
    }

    /// Pick the jake voice: the recorded 1600 jake or the classic synth.
    ///
    /// Applies live -- a jake growl already sounding on the descent restarts
    /// on the new cut in place, the same instant A/B the engine voice
    /// setting gives.
    fn set_jake_voice(&mut self, classic: bool) {
        if self.jake_voice_classic == classic {
            return;
        }
        self.jake_voice_classic = classic;
        let Some((key, volume)) = self.backend.loop_entry(CH_JAKE) else {
            return;
        };
        if !key.starts_with(JAKE_BAND_PREFIX) {
            return; // not a jake loop at all; nothing to swap
        }
        // EVERY band, not just 1600. A descent runs through 1200 to 2200, so
        // guarding on the one band meant flipping the setting anywhere else
        // did nothing at all -- the old voice kept sounding until rpm next
        // crossed a boundary, and the driver heard the setting they had just
        // left (owner, 2026-08-19: "either the synthesized brake plays or the
        // recorded one, not both"). Restart on the band that is actually
        // sounding; the voice routing picks the voice.
        // Leaving classic, the synth stood in for every band, so 1600 -- the
        // cut it was made from -- is the honest band to come back on. Leaving
        // real, restart the band that is sounding and let the routing pick
        // the voice.
        let band = if key == JAKE_CLASSIC_KEY {
            JAKE_RECORDED_KEY.to_string()
        } else {
            key
        };
        self.start_loop_with(CH_JAKE, &band, volume, 120);
    }

    /// Cached; call sites use it to prefer a licensed cue and fall back to
    /// the committed one -- or to stay silent where silence was the old
    /// behavior -- on a clean clone.
    fn has_asset(&mut self, key: &str) -> bool {
        let key = self.route_voice_key(key);
        if generated_sound(&key).is_some() {
            // Synthesized cues are published after this engine was built, so a
            // miss cached before registration must never be the final answer.
            return true;
        }
        if let Some(known) = self.asset_known.get(&key) {
            return *known;
        }
        let known = self.asset_exists(&key);
        self.asset_known.insert(key, known);
        known
    }

    fn start_loop_with(&mut self, channel: u32, key: &str, volume: f64, fade_ms: u32) {
        let key = self.route_voice_key(key);
        self.backend.start_loop(channel, &key, volume, fade_ms);
    }

    fn set_loop_volume(&mut self, channel: u32, volume: f64) {
        self.backend.set_loop_volume(channel, volume);
    }

    fn set_loop_pan(&mut self, channel: u32, pan: f64) {
        self.backend.set_loop_pan(channel, pan);
    }

    fn stop_loop_with(&mut self, channel: u32, fade_ms: u32) {
        self.backend.stop_loop(channel, fade_ms);
    }

    /// The attack before the loop start plays once, then the region repeats
    /// until `release_sustain_loop`, which lets the release tail after the
    /// loop end play out. Ideal for held sounds (a horn, a siren) that should
    /// sustain naturally and ring out on release.
    fn start_sustain_loop_with(
        &mut self,
        channel: u32,
        key: &str,
        spec: SustainLoopSpec,
        volume: f64,
    ) {
        self.backend.start_sustain_loop(channel, key, spec, volume);
    }

    fn release_sustain_loop_with(&mut self, channel: u32, fade_ms: u32) {
        self.backend.release_sustain_loop(channel, fade_ms);
    }

    /// Call this every frame for as long as the alert applies. The tone
    /// starts on the first call and stops itself a fraction of a second
    /// after the calls stop, so it can never be left ringing by a caller
    /// that returned early, ended, or lost the frame to a menu. Calling it
    /// again after a silencing transition brings the same tone back.
    fn hold_alert_with(&mut self, key: &str, volume: f64, fade_ms: u32) {
        self.start_loop_with(CH_ALERT, key, volume, fade_ms);
        self.alert_hold_key = key.to_string();
        self.alert_hold_s = ALERT_HOLD_TIMEOUT_S;
    }

    fn release_alert_with(&mut self, fade_ms: u32) {
        if self.alert_hold_key.is_empty() {
            return;
        }
        self.alert_hold_key.clear();
        self.alert_hold_s = 0.0;
        self.stop_loop_with(CH_ALERT, fade_ms);
    }

    /// Mark the cue `name` as still going, for the next moment only.
    ///
    /// The caller plays the sound; this is only the latch that says the
    /// caller is still there. Call it every frame the cue applies. See
    /// [`CUE_HOLD_TIMEOUT_S`]: the countdown runs on the app's audio clock,
    /// which ticks on every screen, so an owner that stopped getting the
    /// frame lapses instead of picking up where it left off.
    fn hold_cue(&mut self, name: &str) {
        self.cue_holds.insert(name.to_string(), CUE_HOLD_TIMEOUT_S);
    }

    /// Whether `name` was re-asserted recently enough to still be live.
    fn cue_held(&self, name: &str) -> bool {
        self.cue_holds.get(name).copied().unwrap_or(0.0) > 0.0
    }

    /// Drop the latch on `name` now, having ended the cue deliberately.
    fn release_cue(&mut self, name: &str) {
        self.cue_holds.remove(name);
    }

    /// `play_start_sound` true (a deliberate ignition) plays the ignition
    /// one-shot and crossfades it into the idle loop at the clip's tail. Pass
    /// false to bring the running-engine loop up silently -- e.g. when
    /// resuming a saved trip whose engine was already on, or returning from
    /// an in-trip menu -- so the crank never replays.
    fn engine_start_with(&mut self, play_start_sound: bool) {
        self.backend.engine_start(play_start_sound);
    }

    fn engine_stop_with(&mut self, shutdown_sound: bool) {
        self.reverse_stop();
        self.backend.engine_stop(shutdown_sound);
    }

    fn update(&mut self, dt: f64) {
        if let Some(rx) = &self.probe {
            match rx.try_recv() {
                Ok(outcome) => {
                    self.probe = None;
                    self.settle_probe(outcome);
                }
                Err(std::sync::mpsc::TryRecvError::Empty) => {}
                Err(std::sync::mpsc::TryRecvError::Disconnected) => {
                    // The probe thread died without reporting. Run silent,
                    // and say so -- silence with no word is the one outcome
                    // that is never allowed.
                    self.probe = None;
                    self.silence_notice = !self.probe_headless;
                    log::warn!("Audio probe thread died; running silent");
                }
            }
        }
        self.backend.update(dt);
        // The held-alert watchdog. This runs from the app loop no matter which
        // screen is up, so a tone whose owner stopped updating goes quiet on
        // its own instead of running until the player quits the game.
        if self.alert_hold_s > 0.0 {
            self.alert_hold_s -= dt;
            if self.alert_hold_s <= 0.0 {
                self.release_alert();
            }
        }
        // Same watchdog for the latches whose sound the owner plays itself.
        if !self.cue_holds.is_empty() {
            for left in self.cue_holds.values_mut() {
                *left -= dt;
            }
            self.cue_holds.retain(|_name, left| *left > 0.0);
        }
    }

    fn set_engine_rpm_with(&mut self, rpm: f64, throttle: f64) {
        self.backend.set_engine_rpm(rpm, throttle);
    }

    /// Tire-on-asphalt loop whose volume (and pitch under BASS) tracks speed.
    fn set_road_noise(&mut self, speed_mps: f64) {
        self.backend.set_road_noise(speed_mps);
    }

    /// Play a weather ambience loop, e.g. `weather/rain_light`.
    fn set_weather_with(&mut self, key: Option<&str>, intensity: f64) {
        match key {
            None => self.stop_loop_with(CH_WEATHER, 1200),
            Some(key) => self.start_loop_with(CH_WEATHER, key, intensity.min(1.0), 1200),
        }
    }

    fn set_wind(&mut self, intensity: f64) {
        if intensity < 0.05 {
            self.stop_loop_with(CH_WEATHER_B, 1500);
        } else {
            self.start_loop_with(CH_WEATHER_B, "weather/wind", intensity.min(1.0), 1500);
        }
    }

    fn set_ambient_with(&mut self, key: Option<&str>, volume: f64) {
        match key {
            None => self.stop_loop_with(CH_AMBIENT, 800),
            Some(key) => self.start_loop_with(CH_AMBIENT, key, volume, 800),
        }
    }

    fn horn_start(&mut self) {
        self.start_sustain_loop_with(CH_HORN, "vehicle/horn", HORN_LOOP, 1.0);
    }

    fn horn_stop(&mut self) {
        // Let the horn's natural release ring out instead of cutting it short.
        self.release_sustain_loop_with(CH_HORN, 0);
    }

    fn reverse_start(&mut self) {
        self.backend.reverse_start();
    }

    fn reverse_stop(&mut self) {
        self.backend.reverse_stop();
    }

    fn stop_world(&mut self) {
        self.engine_stop_with(false);
        // A pause or an arrival cuts the alert now, without the watchdog's
        // fraction of a second of tone over the top of the menu.
        self.release_alert_with(200);
        for ch in [
            CH_ROAD,
            CH_WEATHER,
            CH_WEATHER_B,
            CH_AMBIENT,
            CH_HORN,
            CH_AIR,
            CH_JAKE,
            CH_RADIO_FX,
            // The edge texture is road noise like the rest: left out, a driver
            // who paused with a tire on the rumble strip took the strip into
            // the menu with them. It comes back on its own when the drive does.
            CH_EDGE,
        ] {
            self.stop_loop_with(ch, 400);
        }
    }

    /// Stream a music track, e.g. `play_music("menu_theme")`.
    fn play_music_with(&mut self, track: &str, fade_ms: u32) {
        if self.probe.is_some() {
            self.replay_music = Some(MusicReplay::Track {
                track: track.to_string(),
                fade_ms,
            });
        }
        self.backend.play_music(track, fade_ms);
    }

    /// Stream a music track from `start_s` seconds in, for tuning into a
    /// station that was already playing it.
    fn play_music_at(&mut self, track: &str, fade_ms: u32, start_s: f64) {
        if self.probe.is_some() {
            // The seek position would be stale by the time the backend
            // arrives; starting the track over is the honest replay.
            self.replay_music = Some(MusicReplay::Track {
                track: track.to_string(),
                fade_ms,
            });
        }
        self.backend.play_music_at(track, fade_ms, start_s);
    }

    /// Stream a live radio URL when the active backend supports it.
    fn play_radio_stream_with(&mut self, url: &str, fade_ms: u32) -> Result<(), AudioError> {
        if self.probe.is_some() {
            self.replay_music = Some(MusicReplay::Radio {
                url: url.to_string(),
                fade_ms,
            });
        }
        self.backend.play_radio_stream(url, fade_ms)
    }

    /// Play one local media file (a personal playlist entry) as music.
    fn play_music_file_with(&mut self, path: &str, fade_ms: u32) -> Result<(), AudioError> {
        if self.probe.is_some() {
            self.replay_music = Some(MusicReplay::File {
                path: path.to_string(),
                fade_ms,
            });
        }
        self.backend.play_music_file(path, fade_ms)
    }

    fn music_playing(&self) -> bool {
        self.backend.music_playing()
    }

    fn radio_now_playing(&self) -> Option<String> {
        self.backend.radio_now_playing()
    }

    fn stop_music_with(&mut self, fade_ms: u32) {
        self.replay_music = None;
        self.backend.stop_music(fade_ms);
    }

    fn set_volumes(&mut self, volumes: &VolumeUpdate) {
        self.backend.set_volumes(volumes);
        // The other half of a silence report: a healthy backend playing at
        // zero looks exactly like a broken one until the levels are written
        // down. Logged on change only, so it cannot flood the file.
        if self.logged_volumes.as_ref() != Some(volumes) {
            self.logged_volumes = Some(*volumes);
            log::info!("Volumes: {volumes}");
        }
    }

    fn shutdown(&mut self) {
        self.backend.shutdown();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::any::Any;
    use std::cell::RefCell;
    use std::rc::Rc;

    /// Records what the engine tells it, and nothing else.
    struct RecordingBackend {
        buses: Buses,
        log: Rc<RefCell<Vec<String>>>,
    }

    impl AudioBackend for RecordingBackend {
        fn name(&self) -> &'static str {
            "recording"
        }
        fn enabled(&self) -> bool {
            true
        }
        fn buses(&self) -> &Buses {
            &self.buses
        }
        fn buses_mut(&mut self) -> &mut Buses {
            &mut self.buses
        }
        fn as_any(&self) -> &dyn Any {
            self
        }
        fn as_any_mut(&mut self) -> &mut dyn Any {
            self
        }
        fn play_music(&mut self, track: &str, fade_ms: u32) {
            self.log
                .borrow_mut()
                .push(format!("music {track} {fade_ms}"));
        }
        fn set_engine_voice_classic(&mut self, classic: bool) {
            self.log
                .borrow_mut()
                .push(format!("voice classic={classic}"));
        }
        fn set_volumes(&mut self, volumes: &VolumeUpdate) {
            self.buses.apply(volumes);
            self.log.borrow_mut().push("volumes".to_string());
        }
    }

    fn engine_with_pending_probe() -> (
        AudioEngine,
        std::sync::mpsc::Sender<Result<bool, bass_sys::safe::BassError>>,
    ) {
        let (tx, rx) = std::sync::mpsc::channel();
        let mut engine = AudioEngine::with_backend(Box::new(NullBackend::new()));
        engine.probe = Some(rx);
        engine.probe_headless = false;
        (engine, tx)
    }

    /// The requests boot makes while the device is still opening -- the menu
    /// theme, the volume settings, the engine voice -- reach the real backend
    /// the moment it arrives, and the null stand-in's "that asset does not
    /// exist" answers do not outlive it.
    #[test]
    fn late_backend_hears_what_boot_asked_for() {
        let (mut engine, _tx) = engine_with_pending_probe();
        engine.play_music_with("menu_theme", 1500);
        engine.set_volumes(&VolumeUpdate::default().master(0.5));
        engine.set_engine_voice(true);
        // Cached against the null backend: false. Must not survive the swap.
        assert!(!engine.has_asset("ui/no_such_cue_for_this_test"));
        assert!(engine
            .asset_known
            .contains_key("ui/no_such_cue_for_this_test"));

        let log = Rc::new(RefCell::new(Vec::new()));
        engine.probe = None;
        engine.adopt_backend(
            Box::new(RecordingBackend {
                buses: Buses::new(),
                log: Rc::clone(&log),
            }),
            false,
        );

        let seen = log.borrow().join("; ");
        assert!(seen.contains("volumes"), "volumes not replayed: {seen}");
        assert!(
            seen.contains("voice classic=true"),
            "voice not replayed: {seen}"
        );
        assert!(
            seen.contains("music menu_theme 1500"),
            "music not replayed: {seen}"
        );
        assert!(
            engine.asset_known.is_empty(),
            "stand-in asset answers survived the swap"
        );
        assert!(!engine.take_silence_notice());
    }

    /// A probe that comes back empty-handed leaves the game on the null
    /// backend and arms the notice, so the main menu can say out loud that
    /// this run has no sound.
    #[test]
    fn failed_probe_runs_silent_and_says_so() {
        let (mut engine, tx) = engine_with_pending_probe();
        tx.send(Err(bass_sys::safe::BassError::NOT_LOADED)).unwrap();
        engine.update(0.0);
        assert!(engine.probe.is_none());
        assert_eq!(engine.backend_name(), "none");
        assert!(engine.take_silence_notice());
        assert!(!engine.take_silence_notice(), "the notice must speak once");
    }

    /// Music stopped before the backend arrives must not come back from the
    /// dead when it does.
    #[test]
    fn stopped_music_is_not_replayed() {
        let (mut engine, _tx) = engine_with_pending_probe();
        engine.play_music_with("menu_theme", 1500);
        engine.stop_music_with(400);
        let log = Rc::new(RefCell::new(Vec::new()));
        engine.probe = None;
        engine.adopt_backend(
            Box::new(RecordingBackend {
                buses: Buses::new(),
                log: Rc::clone(&log),
            }),
            false,
        );
        assert!(
            !log.borrow().join("; ").contains("music"),
            "stopped music was resurrected"
        );
    }
}
