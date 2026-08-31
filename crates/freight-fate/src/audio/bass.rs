//! The BASS implementation (`_BassBackend`): streams, slides, and a pitched
//! engine.
//!
//! Fails to construct if the BASS library cannot be loaded or initialised
//! at all; the facade then runs on the null backend. With the dummy SDL
//! audio driver (tests, CI) or when no device exists, BASS's "no sound"
//! device keeps the whole pipeline running silently.
//!
//! Split over three files, one `impl` block each: this one (construction,
//! assets, one-shots, loops, the sustain loop, volumes, shutdown),
//! `bass_engine` (the engine ring, the ignition crossfade, `update`) and
//! `bass_radio` (music, radio streams and the connect worker).

use std::any::Any;
use std::cell::Cell;
use std::collections::HashMap;
use std::path::Path;
use std::rc::Rc;
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use bass_sys::safe::{self, BassError, Stream};
use bass_sys::{
    BASS_ACTIVE_PLAYING, BASS_ATTRIB_FREQ, BASS_ATTRIB_PAN, BASS_ATTRIB_VOL,
    BASS_CONFIG_DEV_DEFAULT, BASS_CONFIG_NET_BUFFER, BASS_CONFIG_NET_PREBUF,
    BASS_CONFIG_NET_READTIMEOUT, BASS_CONFIG_NET_TIMEOUT, BASS_DEFAULT_DEVICE, BASS_ERROR_ALREADY,
    BASS_STREAM_AUTOFREE,
};
use ff_core::audio_fades::FadeScheduler;
use ff_core::audio_loops::SustainLoopSpec;
use ff_core::pyrandom::PyRandom;

use super::assets::{playback_bytes, plugin_lib_dir, SFX_EXTENSIONS};
use super::backend::{loop_category, one_shot_category, AudioBackend, Buses, VolumeUpdate};
use super::bass_radio::{PendingRadioStart, RadioShared};
use super::sustain::SustainLoop;
use super::{
    AudioError, KeyProbe, BASS_NO_SOUND_DEVICE, CH_REVERSE, CH_ROAD, ENGINE_RPM_IDLE,
    RADIO_CONNECT_TIMEOUT_MS, RADIO_NET_BUFFER_MS, RADIO_NET_PREBUF_PERCENT, RADIO_READ_TIMEOUT_MS,
    RADIO_SHUTDOWN_JOIN_S,
};

/// `sound_lib.Channel.is_playing`: active and not stalled or paused.
pub(super) fn is_playing(handle: u32) -> bool {
    safe::channel_is_active(handle) == BASS_ACTIVE_PLAYING
}

/// `sound_lib.Channel.set_volume`.
pub(super) fn set_volume(handle: u32, volume: f64) -> Result<(), BassError> {
    safe::channel_set_attribute(handle, BASS_ATTRIB_VOL, volume as f32)
}

/// `sound_lib.Channel.get_frequency`: the FREQ attribute, which starts at
/// the stream's own sample rate.
pub(super) fn get_frequency(handle: u32) -> Result<f64, BassError> {
    safe::channel_get_attribute(handle, BASS_ATTRIB_FREQ).map(f64::from)
}

/// `BASS_ChannelSlideAttribute` with the game's argument types.
pub(super) fn slide(handle: u32, attrib: u32, value: f64, ms: u32) -> Result<(), BassError> {
    safe::channel_slide_attribute(handle, attrib, value as f32, ms)
}

/// The BASSHLS plugin file name on this platform.
fn bass_hls_plugin_name() -> &'static str {
    if cfg!(windows) {
        "basshls.dll"
    } else if cfg!(target_os = "macos") {
        "libbasshls.dylib"
    } else {
        "libbasshls.so"
    }
}

/// A loop on a reserved slot: the Python `(key, gain, stream)` tuple, plus
/// the base frequency the road-noise slide caches on its stream.
pub(super) struct LoopEntry {
    pub key: String,
    pub gain: f64,
    pub stream: Stream,
    pub base_freq: Option<f64>,
}

/// One band of the multisample ring: `(native_rpm, stream, base_freq)` in
/// Python, plus the last rate target and volume applied, for inspection.
pub(super) struct EngineBand {
    pub native: f64,
    pub stream: Stream,
    pub base_freq: f64,
    pub last_rate_target: f64,
    pub last_volume: f64,
}

/// A read-only view of one engine band, for tests and diagnostics.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct EngineBandInfo {
    pub native: f64,
    pub handle: u32,
    pub base_freq: f64,
    /// The `BASS_ATTRIB_FREQ` target of the last slide (`base_freq * rate`).
    pub last_rate_target: f64,
    /// The last volume applied to the band.
    pub last_volume: f64,
}

pub struct BassBackend {
    pub(super) buses: Buses,
    pub(super) enabled: bool,
    pub(super) output_device: u32,
    pub(super) loops: HashMap<u32, LoopEntry>,
    pub(super) sustains: HashMap<u32, SustainLoop>,
    // slot -> (key, handle) still ringing out its release tail after a
    // release; the stream itself sits in `retained`. Tracked so a repeat
    // press cannot stack a second overlapping sound on top of the tail.
    pub(super) releasing: HashMap<u32, (String, u32)>,
    // Streams kept alive until BASS finishes them.
    pub(super) retained: Vec<Stream>,
    pub(super) music_track: Option<String>,
    pub(super) music_stream: Option<Stream>,
    pub(super) engine_running: bool,
    pub(super) engine_stream: Option<Stream>,
    pub(super) engine_base_freq: f64,
    // Multisample ring; empty when running on the legacy single pitched loop.
    pub(super) engine_bands: Vec<EngineBand>,
    // Player preference: true forces the legacy pitched loop even when the
    // multisample cuts are installed (Settings, "classic").
    pub(super) engine_voice_classic: bool,
    pub(super) engine_intro_stream: Option<u32>, // ignition one-shot, kept for the crossfade
    // The ignition fades write these; `update` re-applies the engine level
    // when they move (the Python fade callbacks called set_engine_rpm
    // directly; a Rust closure cannot borrow the backend it lives in).
    pub(super) engine_intro_gain: Rc<Cell<f64>>, // crossfade multiplier on the engine loop
    pub(super) engine_intro_load: Rc<Cell<f64>>, // ignition load boost: 1.0 forces full load
    pub(super) engine_starting: Rc<Cell<bool>>,  // true only during the ignition crossfade
    pub(super) intro_applied: (f64, f64),
    pub(super) engine_last_rpm: f64,
    pub(super) engine_last_throttle: f64,
    pub(super) engine_duck: f64, // shift-gap disengage: below the load floor
    pub(super) fades: FadeScheduler,
    pub(super) engine_wobble: Vec<[f64; 2]>,
    pub(super) wobble_rng: PyRandom,
    // Radio connects happen on worker threads (see play_radio_stream); the
    // shared state is guarded by its mutex. The generation counter tells a
    // finished worker whether its request is still the current one; the
    // pending slot is how an opened stream crosses back to the game thread,
    // which alone touches `music_stream`.
    pub(super) radio: Arc<Mutex<RadioShared>>,
    pub(super) radio_threads: Vec<JoinHandle<()>>,
    pub(super) radio_start: Option<PendingRadioStart>,
    pub(super) road_last_target: Option<f64>,
    // Test seams, mirroring what the Python tests monkeypatched onto
    // `_sfx_stream`: a key filter that makes a sound "absent", and a recorder
    // of every key asked for.
    pub(super) key_filter: Option<KeyProbe>,
    pub(super) requested_keys: Option<Vec<String>>,
}

impl BassBackend {
    /// Initialise BASS on the device the environment asks for: the no-sound
    /// device when `SDL_AUDIODRIVER=dummy`, else the system default with a
    /// no-sound fallback.
    pub fn new() -> Result<Self, BassError> {
        Self::new_with_device(Self::headless_requested())
    }

    /// Initialise BASS on the no-sound device regardless of the environment.
    pub fn new_headless() -> Result<Self, BassError> {
        Self::new_with_device(true)
    }

    /// The blocking half of coming up: load the natives and open the output
    /// device, without building a backend. BASS is process-global, so this
    /// can run on a worker thread while the boot keeps reading input; a
    /// later [`BassBackend::new`] / [`BassBackend::new_headless`] on the
    /// game thread then finds the device already open (`BASS_ERROR_ALREADY`
    /// is success in `init_device`) and returns immediately.
    ///
    /// `Ok(true)` means the default device refused and the no-sound device
    /// stood in -- the caller must finish with `new_headless`, or the game
    /// thread would probe the broken default device all over again.
    pub fn preopen_device() -> Result<bool, BassError> {
        if !bass_sys::native_available() {
            return Err(BassError::NOT_LOADED);
        }
        let _ = safe::set_config(BASS_CONFIG_NET_TIMEOUT, RADIO_CONNECT_TIMEOUT_MS);
        let _ = safe::set_config(BASS_CONFIG_NET_READTIMEOUT, RADIO_READ_TIMEOUT_MS);
        let _ = safe::set_config(BASS_CONFIG_NET_BUFFER, RADIO_NET_BUFFER_MS);
        let _ = safe::set_config(BASS_CONFIG_NET_PREBUF, RADIO_NET_PREBUF_PERCENT);
        if Self::headless_requested() {
            Self::init_device(BASS_NO_SOUND_DEVICE)?;
            return Ok(false); // asked-for silence is not a fallback
        }
        let _ = safe::set_config(BASS_CONFIG_DEV_DEFAULT, 1);
        if let Err(err) = Self::init_device(BASS_DEFAULT_DEVICE) {
            log::warn!("No audio device ({err}); using the BASS no-sound device");
            Self::init_device(BASS_NO_SOUND_DEVICE)?;
            return Ok(true);
        }
        Ok(false)
    }

    pub(super) fn headless_requested() -> bool {
        std::env::var("SDL_AUDIODRIVER")
            .map(|v| v.eq_ignore_ascii_case("dummy"))
            .unwrap_or(false)
    }

    fn init_device(device: i32) -> Result<(), BassError> {
        match safe::init(device, 44100, 0) {
            Ok(()) => Ok(()),
            // Already up (a previous engine in this process): that IS the
            // device we wanted.
            Err(err) if err.is(BASS_ERROR_ALREADY) => Ok(()),
            Err(err) => Err(err),
        }
    }

    fn new_with_device(no_sound: bool) -> Result<Self, BassError> {
        if !bass_sys::native_available() {
            return Err(BassError::NOT_LOADED);
        }
        let _ = safe::set_config(BASS_CONFIG_NET_TIMEOUT, RADIO_CONNECT_TIMEOUT_MS);
        let _ = safe::set_config(BASS_CONFIG_NET_READTIMEOUT, RADIO_READ_TIMEOUT_MS);
        let _ = safe::set_config(BASS_CONFIG_NET_BUFFER, RADIO_NET_BUFFER_MS);
        let _ = safe::set_config(BASS_CONFIG_NET_PREBUF, RADIO_NET_PREBUF_PERCENT);
        if no_sound {
            Self::init_device(BASS_NO_SOUND_DEVICE)?;
        } else {
            // sound_lib's Output() follows the system default device as the
            // player switches outputs; do the same.
            let _ = safe::set_config(BASS_CONFIG_DEV_DEFAULT, 1);
            if let Err(err) = Self::init_device(BASS_DEFAULT_DEVICE) {
                log::warn!("No audio device ({err}); using the BASS no-sound device");
                Self::init_device(BASS_NO_SOUND_DEVICE)?;
            }
        }
        let mut backend = Self {
            buses: Buses::new(),
            enabled: false,
            output_device: safe::current_device().unwrap_or(u32::MAX),
            loops: HashMap::new(),
            sustains: HashMap::new(),
            releasing: HashMap::new(),
            retained: Vec::new(),
            music_track: None,
            music_stream: None,
            engine_running: false,
            engine_stream: None,
            engine_base_freq: 0.0,
            engine_bands: Vec::new(),
            engine_voice_classic: false,
            engine_intro_stream: None,
            engine_intro_gain: Rc::new(Cell::new(1.0)),
            engine_intro_load: Rc::new(Cell::new(0.0)),
            engine_starting: Rc::new(Cell::new(false)),
            intro_applied: (1.0, 0.0),
            engine_last_rpm: ENGINE_RPM_IDLE,
            engine_last_throttle: 0.0,
            engine_duck: 1.0,
            fades: FadeScheduler::new(),
            engine_wobble: Vec::new(),
            wobble_rng: PyRandom::new_unseeded(),
            radio: Arc::new(Mutex::new(RadioShared::default())),
            radio_threads: Vec::new(),
            radio_start: None,
            road_last_target: None,
            key_filter: None,
            requested_keys: None,
        };
        backend.log_output_device();
        backend.load_plugins();
        backend.enabled = true;
        Ok(backend)
    }

    /// Name the output device the game is about to play through.
    ///
    /// A player reporting silence is far more often pointed at the wrong
    /// device -- speech on one output, the game on the system default -- or
    /// muted, than missing a sound file. The log could not tell those apart
    /// without naming the device, so it names it.
    fn log_output_device(&self) {
        let index = self.output_device;
        if index == u32::MAX {
            // Diagnostics must never be the thing that fails.
            log::info!("Audio output device: could not be identified");
            return;
        }
        if index != BASS_NO_SOUND_DEVICE as u32 {
            let name = safe::device_info(index)
                .map(|info| info.name)
                .unwrap_or_else(|_| "unknown".to_string());
            log::info!("Audio output device {index}: {name}");
        } else if Self::headless_requested() {
            // Asked for: headless runs, tests, and the release smoke check.
            log::info!("Audio output: no-sound device, as asked for by this run");
        } else {
            // Not asked for, and the reason a player hears nothing.
            log::warn!("Audio output is the BASS no-sound device; nothing will be audible");
        }
    }

    /// Load optional BASS addon plugins: everything beside the BASS library
    /// (the vendored `bassopus`, `bassflac`, `bass_aac`, `basshls`), then the
    /// game's own `lib/basshls` if the library directory did not carry it.
    ///
    /// A missing or refused plugin is not an error: stations that need it
    /// simply fail to open and the radio falls back with a spoken note.
    fn load_plugins(&self) {
        let mut loaded: Vec<String> = Vec::new();
        let library_dir = bass_sys::api()
            .ok()
            .and_then(|api| api.library_dir().map(Path::to_path_buf));
        if let Some(dir) = library_dir {
            for (name, result) in safe::load_plugins_from(&dir) {
                match result {
                    Ok(_) => loaded.push(name.to_ascii_lowercase()),
                    Err(err) if err.is(BASS_ERROR_ALREADY) => {
                        loaded.push(name.to_ascii_lowercase())
                    }
                    Err(_) => {}
                }
            }
        }
        let hls = bass_hls_plugin_name();
        if loaded.iter().any(|name| name == hls) {
            return;
        }
        let path = plugin_lib_dir().join(hls);
        if !path.is_file() {
            log::info!("BASS plugin not present: {hls}");
            return;
        }
        match safe::plugin_load(&path) {
            Ok(_) => log::info!("Loaded BASS plugin: {}", path.display()),
            Err(err) if err.is(BASS_ERROR_ALREADY) => {
                log::info!("BASS plugin already loaded: {}", path.display())
            }
            Err(err) => log::warn!("BASS could not load plugin: {} ({err})", path.display()),
        }
    }

    // -- assets -------------------------------------------------------------

    /// A fresh memory stream for one playback; autofreed once it stops.
    ///
    /// Memory streams sidestep BASS filename-encoding quirks entirely and
    /// work identically for packed and loose assets. BASS reads the buffer
    /// during playback; the `Stream` pins it for exactly as long as the
    /// stream lives.
    pub(super) fn make_stream(
        &self,
        data: Arc<[u8]>,
        label: &str,
        looping: bool,
    ) -> Option<Stream> {
        let stream = match safe::stream_create_mem_shared(data, BASS_STREAM_AUTOFREE) {
            Ok(stream) => stream,
            Err(err) => {
                log::warn!("Could not open stream: {label} ({err})");
                return None;
            }
        };
        if looping {
            let _ = safe::set_looping(stream.handle(), true);
        }
        Some(stream)
    }

    pub(super) fn sfx_stream(&mut self, key: &str, looping: bool) -> Option<Stream> {
        if let Some(recorder) = self.requested_keys.as_mut() {
            recorder.push(key.to_string());
        }
        if let Some(filter) = &self.key_filter {
            if !filter(key) {
                return None;
            }
        }
        let Some((data, _ext)) = playback_bytes(key, SFX_EXTENSIONS) else {
            log::warn!("Missing sound: {key}");
            return None;
        };
        self.make_stream(data, key, looping)
    }

    /// Keep a stream alive until BASS finishes with it.
    ///
    /// Dropping a `Stream` frees the BASS handle, which would cut one-shots
    /// and fade-outs short the moment the last reference is dropped.
    /// Finished streams (autofreed by BASS) are pruned on each call.
    pub(super) fn retain(&mut self, stream: Stream) {
        let mut alive: Vec<Stream> = Vec::with_capacity(self.retained.len() + 1);
        for retained in self.retained.drain(..) {
            if is_playing(retained.handle()) {
                alive.push(retained);
            }
            // Otherwise it is dropped here: already stopped and autofreed.
        }
        alive.push(stream);
        self.retained = alive;
    }

    /// Slide volume to -1: BASS stops (and autofrees) the channel at 0.
    pub(super) fn fade_out(&mut self, stream: Stream, fade_ms: u32) {
        if let Err(err) = slide(stream.handle(), BASS_ATTRIB_VOL, -1.0, fade_ms) {
            log::debug!("Fade-out failed; stream already gone ({err})");
            return; // dropped: the stream is gone either way
        }
        self.retain(stream); // keep it alive for the duration of the fade
    }

    // -- one-shots ----------------------------------------------------------

    pub(super) fn play(&mut self, key: &str, volume: f64, pan: f64) {
        let Some(stream) = self.sfx_stream(key, false) else {
            return;
        };
        let handle = stream.handle();
        let level =
            (volume * self.buses.category_volume(one_shot_category(key)) * self.buses.master)
                .clamp(0.0, 1.0);
        let started = set_volume(handle, level)
            .and_then(|()| {
                if pan != 0.0 {
                    safe::channel_set_attribute(
                        handle,
                        BASS_ATTRIB_PAN,
                        pan.clamp(-1.0, 1.0) as f32,
                    )
                } else {
                    Ok(())
                }
            })
            .and_then(|()| safe::channel_play(handle, false));
        if let Err(err) = started {
            log::warn!("Could not play {key} ({err})");
            return;
        }
        self.retain(stream);
    }

    // -- loops on reserved slots ------------------------------------------------

    pub(super) fn start_loop(&mut self, channel: u32, key: &str, volume: f64, fade_ms: u32) {
        if let Some(current) = self.loops.get(&channel) {
            if current.key == key {
                self.set_loop_volume(channel, volume);
                return;
            }
            self.stop_loop(channel, fade_ms.min(300));
        }
        let Some(stream) = self.sfx_stream(key, true) else {
            return;
        };
        let handle = stream.handle();
        self.loops.insert(
            channel,
            LoopEntry {
                key: key.to_string(),
                gain: volume,
                stream,
                base_freq: None,
            },
        );
        if set_volume(handle, 0.0)
            .and_then(|()| safe::channel_play(handle, false))
            .is_err()
        {
            self.loops.remove(&channel);
            return;
        }
        self.apply_loop_volume(channel, fade_ms);
    }

    pub(super) fn set_loop_volume(&mut self, channel: u32, volume: f64) {
        if let Some(entry) = self.loops.get_mut(&channel) {
            entry.gain = volume;
            self.apply_loop_volume(channel, 0);
        }
    }

    pub(super) fn set_loop_pan(&mut self, channel: u32, pan: f64) {
        let Some(entry) = self.loops.get(&channel) else {
            return;
        };
        // A dying stream drops its pan silently; the volume path logs.
        let _ = safe::channel_set_attribute(
            entry.stream.handle(),
            BASS_ATTRIB_PAN,
            pan.clamp(-1.0, 1.0) as f32,
        );
    }

    pub(super) fn stop_loop(&mut self, channel: u32, fade_ms: u32) {
        if let Some((_key, handle)) = self.releasing.remove(&channel) {
            // Cut the ringing-out tail too, if BASS has not finished it.
            if let Some(i) = self.retained.iter().position(|s| s.handle() == handle) {
                let tail = self.retained.remove(i);
                self.fade_out(tail, fade_ms);
            }
        }
        if let Some(mut sustain) = self.sustains.remove(&channel) {
            sustain.stop();
        }
        if let Some(entry) = self.loops.remove(&channel) {
            self.fade_out(entry.stream, fade_ms);
        }
    }

    /// True while `channel` is still ringing out a release tail of `key`.
    fn release_tail_playing(&mut self, channel: u32, key: &str) -> bool {
        let Some((tail_key, handle)) = self.releasing.get(&channel) else {
            return false;
        };
        if !is_playing(*handle) {
            self.releasing.remove(&channel);
            return false;
        }
        tail_key == key
    }

    /// Play `key` and loop only the interior region `spec` describes.
    ///
    /// The attack (before the loop start) plays once, then the region
    /// repeats seamlessly until [`Self::release_sustain_loop`]. A repeat call
    /// while the same key is already sounding on `channel` -- held or ringing
    /// out its release tail -- is ignored, so presses never stack.
    pub(super) fn start_sustain_loop(
        &mut self,
        channel: u32,
        key: &str,
        spec: SustainLoopSpec,
        volume: f64,
    ) {
        let current_key = self.loops.get(&channel).map(|entry| entry.key.clone());
        if current_key.as_deref() == Some(key) && self.sustains.contains_key(&channel) {
            self.set_loop_volume(channel, volume);
            return;
        }
        if self.release_tail_playing(channel, key) {
            return;
        }
        if current_key.is_some() {
            self.stop_loop(channel, 0);
        }
        let Some(stream) = self.sfx_stream(key, false) else {
            return;
        };
        let handle = stream.handle();
        let sustain = match SustainLoop::new(handle, spec) {
            Ok(sustain) => sustain,
            Err(err) => {
                log::warn!("Could not set loop points for {key} ({err})");
                return;
            }
        };
        self.releasing.remove(&channel);
        self.loops.insert(
            channel,
            LoopEntry {
                key: key.to_string(),
                gain: volume,
                stream,
                base_freq: None,
            },
        );
        self.sustains.insert(channel, sustain);
        if set_volume(handle, 0.0)
            .and_then(|()| safe::channel_play(handle, false))
            .is_err()
        {
            self.loops.remove(&channel);
            self.sustains.remove(&channel);
            return;
        }
        self.apply_loop_volume(channel, 0);
    }

    /// Stop looping `channel` and let its release tail play to the end.
    ///
    /// Playback continues from wherever it is, past the loop end, through the
    /// tail; BASS autofrees the stream at EOF. `fade_ms` optionally fades the
    /// tail out (0 keeps the natural release at full volume).
    pub(super) fn release_sustain_loop(&mut self, channel: u32, fade_ms: u32) {
        let Some(mut sustain) = self.sustains.remove(&channel) else {
            // No sustain loop here; fall back to a plain stop so callers can
            // use release/stop interchangeably on a channel.
            self.stop_loop(channel, fade_ms);
            return;
        };
        sustain.release();
        let Some(entry) = self.loops.remove(&channel) else {
            return;
        };
        let LoopEntry { key, stream, .. } = entry;
        let handle = stream.handle();
        if fade_ms > 0 {
            self.fade_out(stream, fade_ms);
        } else {
            // Hand the stream to the retain list so dropping the loop entry
            // does not free it mid-tail; BASS autofrees it at EOF.
            self.retain(stream);
        }
        // Remember the tail so a repeat press during it does not stack a
        // horn (the retain list owns the stream; this is the lookup).
        self.releasing.insert(channel, (key, handle));
    }

    pub(super) fn reverse_start(&mut self) {
        self.start_loop(CH_REVERSE, "vehicle/reverse", 0.4, 80);
    }

    pub(super) fn reverse_stop(&mut self) {
        self.stop_loop(CH_REVERSE, 80);
    }

    pub(super) fn apply_loop_volume(&mut self, channel: u32, fade_ms: u32) {
        let Some(entry) = self.loops.get(&channel) else {
            return;
        };
        let level =
            (entry.gain * self.buses.category_volume(loop_category(channel)) * self.buses.master)
                .clamp(0.0, 1.0);
        let handle = entry.stream.handle();
        let applied = if fade_ms > 0 {
            slide(handle, BASS_ATTRIB_VOL, level, fade_ms)
        } else {
            set_volume(handle, level)
        };
        if applied.is_err() {
            self.loops.remove(&channel);
        }
    }

    pub(super) fn set_road_noise(&mut self, speed_mps: f64) {
        let gain = (speed_mps / 30.0).min(1.0);
        if gain < 0.02 {
            self.stop_loop(CH_ROAD, 500);
            return;
        }
        self.start_loop(CH_ROAD, "vehicle/road", gain, 400);
        let Some(entry) = self.loops.get_mut(&CH_ROAD) else {
            return;
        };
        let mult = 0.4 + 0.9 * (speed_mps / 30.0).min(1.0);
        let handle = entry.stream.handle();
        let base_freq = match entry.base_freq {
            Some(base) => base,
            None => match get_frequency(handle) {
                Ok(base) => {
                    entry.base_freq = Some(base);
                    base
                }
                Err(_) => return,
            },
        };
        let target = base_freq * mult;
        if slide(handle, BASS_ATTRIB_FREQ, target, 120).is_ok() {
            self.road_last_target = Some(target);
        }
    }

    // -- volume control ---------------------------------------------------------

    pub(super) fn set_volumes(&mut self, volumes: &VolumeUpdate) {
        self.buses.apply(volumes);
        let channels: Vec<u32> = self.loops.keys().copied().collect();
        for channel in channels {
            self.apply_loop_volume(channel, 0);
        }
        // Reapply engine volume through the rpm path: it knows the current
        // model (multisample ring or legacy loop) and keeps the load contour.
        self.set_engine_rpm(self.engine_last_rpm, self.engine_last_throttle);
        if let Some(start) = self.radio_start.as_mut() {
            start.level = self.buses.music_level();
            if set_volume(start.handle, 0.0).is_err() {
                self.radio_start = None;
                self.music_stream = None;
            }
        } else if let Some(stream) = &self.music_stream {
            if set_volume(stream.handle(), self.buses.music_level()).is_err() {
                self.music_stream = None;
            }
        }
    }

    pub(super) fn shutdown(&mut self) {
        self.fades.clear();
        let channels: Vec<u32> = self.loops.keys().copied().collect();
        for channel in channels {
            self.stop_loop(channel, 0);
        }
        self.engine_stop(false);
        self.stop_music(0);
        self.retained.clear();
        self.releasing.clear();
        // A connect still in flight holds a worker inside BASS; freeing BASS
        // underneath it is a crash. Give it a bounded moment to come back.
        self.join_radio_workers(Duration::from_secs_f64(RADIO_SHUTDOWN_JOIN_S));
        if let Err(err) = safe::free() {
            log::debug!("BASS_Free: {err}");
        }
        self.enabled = false;
    }

    /// Wait up to `timeout` for the radio-connect workers to finish; a
    /// worker still inside its connect after that is left running (the
    /// Python `thread.join(timeout)` did the same).
    pub fn join_radio_workers(&mut self, timeout: Duration) {
        let deadline = Instant::now() + timeout;
        let threads = std::mem::take(&mut self.radio_threads);
        for thread in threads {
            while !thread.is_finished() && Instant::now() < deadline {
                std::thread::sleep(Duration::from_millis(5));
            }
            if thread.is_finished() {
                let _ = thread.join();
            } else {
                self.radio_threads.push(thread);
            }
        }
    }

    // -- inspection ------------------------------------------------------------
    // What the Python tests read off the backend's private fields.

    /// The BASS device index the backend initialised (0 is the no-sound
    /// device).
    pub fn output_device(&self) -> u32 {
        self.output_device
    }

    /// The reserved slots with a loop on them, sorted.
    pub fn loop_channels(&self) -> Vec<u32> {
        let mut channels: Vec<u32> = self.loops.keys().copied().collect();
        channels.sort_unstable();
        channels
    }

    /// The BASS handle of the loop on `channel`.
    pub fn loop_stream_handle(&self, channel: u32) -> Option<u32> {
        self.loops.get(&channel).map(|entry| entry.stream.handle())
    }

    /// The slots carrying a held sustain loop, sorted.
    pub fn sustain_channels(&self) -> Vec<u32> {
        let mut channels: Vec<u32> = self.sustains.keys().copied().collect();
        channels.sort_unstable();
        channels
    }

    /// The `(key, handle)` ringing out a release tail on `channel`.
    pub fn releasing_entry(&self, channel: u32) -> Option<(String, u32)> {
        self.releasing
            .get(&channel)
            .map(|(key, handle)| (key.clone(), *handle))
    }

    /// Handles of the streams retained until BASS finishes them, oldest first.
    pub fn retained_handles(&self) -> Vec<u32> {
        self.retained.iter().map(Stream::handle).collect()
    }

    pub fn is_retained(&self, handle: u32) -> bool {
        self.retained.iter().any(|s| s.handle() == handle)
    }

    /// Fades still running (the ignition crossfade schedules three).
    pub fn fade_count(&self) -> usize {
        self.fades.len()
    }

    pub fn engine_bands(&self) -> Vec<EngineBandInfo> {
        self.engine_bands
            .iter()
            .map(|band| EngineBandInfo {
                native: band.native,
                handle: band.stream.handle(),
                base_freq: band.base_freq,
                last_rate_target: band.last_rate_target,
                last_volume: band.last_volume,
            })
            .collect()
    }

    /// The legacy single pitched loop's handle, when that model is running.
    pub fn engine_stream_handle(&self) -> Option<u32> {
        self.engine_stream.as_ref().map(Stream::handle)
    }

    pub fn engine_base_freq(&self) -> f64 {
        self.engine_base_freq
    }

    pub fn engine_intro_gain(&self) -> f64 {
        self.engine_intro_gain.get()
    }

    pub fn engine_intro_load(&self) -> f64 {
        self.engine_intro_load.get()
    }

    /// The per-band `[rate walk, gain walk]` pairs.
    pub fn engine_wobble(&self) -> Vec<[f64; 2]> {
        self.engine_wobble.clone()
    }

    /// Seed the anti-repetition walk (it is unseeded, cosmetic randomness
    /// in the game).
    pub fn set_wobble_rng(&mut self, rng: PyRandom) {
        self.wobble_rng = rng;
    }

    /// The road loop's `(base frequency, last slide target)`.
    pub fn road_noise_frequency(&self) -> Option<(f64, f64)> {
        let base = self.loops.get(&CH_ROAD)?.base_freq?;
        Some((base, self.road_last_target?))
    }

    pub fn music_track(&self) -> Option<&str> {
        self.music_track.as_deref()
    }

    pub fn music_stream_handle(&self) -> Option<u32> {
        self.music_stream.as_ref().map(Stream::handle)
    }

    /// Make every key `keep` refuses resolve to nothing (test seam; `None`
    /// restores the real lookup).
    pub fn set_key_filter(&mut self, keep: Option<KeyProbe>) {
        self.key_filter = keep;
    }

    /// Start or stop recording every sound key the backend opens.
    pub fn record_requested_keys(&mut self, on: bool) {
        self.requested_keys = if on { Some(Vec::new()) } else { None };
    }

    /// The keys recorded so far (empty when not recording).
    pub fn requested_keys(&self) -> Vec<String> {
        self.requested_keys.clone().unwrap_or_default()
    }
}

impl AudioBackend for BassBackend {
    fn name(&self) -> &'static str {
        "bass"
    }

    fn enabled(&self) -> bool {
        self.enabled
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

    fn play(&mut self, key: &str, volume: f64, pan: f64) {
        BassBackend::play(self, key, volume, pan);
    }

    fn start_loop(&mut self, channel: u32, key: &str, volume: f64, fade_ms: u32) {
        BassBackend::start_loop(self, channel, key, volume, fade_ms);
    }

    fn set_loop_volume(&mut self, channel: u32, volume: f64) {
        BassBackend::set_loop_volume(self, channel, volume);
    }

    fn set_loop_pan(&mut self, channel: u32, pan: f64) {
        BassBackend::set_loop_pan(self, channel, pan);
    }

    fn stop_loop(&mut self, channel: u32, fade_ms: u32) {
        BassBackend::stop_loop(self, channel, fade_ms);
    }

    fn loop_entry(&self, channel: u32) -> Option<(String, f64)> {
        self.loops
            .get(&channel)
            .map(|entry| (entry.key.clone(), entry.gain))
    }

    fn start_sustain_loop(&mut self, channel: u32, key: &str, spec: SustainLoopSpec, volume: f64) {
        BassBackend::start_sustain_loop(self, channel, key, spec, volume);
    }

    fn release_sustain_loop(&mut self, channel: u32, fade_ms: u32) {
        BassBackend::release_sustain_loop(self, channel, fade_ms);
    }

    fn engine_start(&mut self, play_start_sound: bool) {
        BassBackend::engine_start(self, play_start_sound);
    }

    fn engine_stop(&mut self, shutdown_sound: bool) {
        BassBackend::engine_stop(self, shutdown_sound);
    }

    fn set_engine_rpm(&mut self, rpm: f64, throttle: f64) {
        BassBackend::set_engine_rpm(self, rpm, throttle);
    }

    fn set_engine_duck(&mut self, duck: f64) {
        BassBackend::set_engine_duck(self, duck);
    }

    fn set_road_noise(&mut self, speed_mps: f64) {
        BassBackend::set_road_noise(self, speed_mps);
    }

    fn update(&mut self, dt: f64) {
        BassBackend::update(self, dt);
    }

    fn reverse_start(&mut self) {
        BassBackend::reverse_start(self);
    }

    fn reverse_stop(&mut self) {
        BassBackend::reverse_stop(self);
    }

    fn engine_running(&self) -> bool {
        self.engine_running
    }

    fn engine_starting(&self) -> bool {
        self.engine_starting.get()
    }

    fn engine_voice_classic(&self) -> Option<bool> {
        Some(self.engine_voice_classic)
    }

    fn set_engine_voice_classic(&mut self, classic: bool) {
        self.engine_voice_classic = classic;
    }

    fn engine_last_rpm_throttle(&self) -> (f64, f64) {
        (self.engine_last_rpm, self.engine_last_throttle)
    }

    fn play_music(&mut self, track: &str, fade_ms: u32) {
        BassBackend::play_music(self, track, fade_ms);
    }

    fn play_music_at(&mut self, track: &str, fade_ms: u32, start_s: f64) {
        BassBackend::play_music_at(self, track, fade_ms, start_s);
    }

    fn play_radio_stream(&mut self, url: &str, fade_ms: u32) -> Result<(), AudioError> {
        BassBackend::play_radio_stream(self, url, fade_ms)
    }

    fn radio_now_playing(&self) -> Option<String> {
        BassBackend::radio_now_playing(self)
    }

    fn play_music_file(&mut self, path: &str, fade_ms: u32) -> Result<(), AudioError> {
        BassBackend::play_music_file(self, path, fade_ms)
    }

    fn music_playing(&self) -> bool {
        BassBackend::music_playing(self)
    }

    fn stop_music(&mut self, fade_ms: u32) {
        BassBackend::stop_music(self, fade_ms);
    }

    fn set_volumes(&mut self, volumes: &VolumeUpdate) {
        BassBackend::set_volumes(self, volumes);
    }

    fn shutdown(&mut self) {
        BassBackend::shutdown(self);
    }
}
