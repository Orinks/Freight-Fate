//! The BASS backend's truck engine: the multisample ring with per-band rate
//! tracking, the legacy single pitched loop, the ignition crossfade, and
//! the per-frame `update`.

use std::rc::Rc;

use bass_sys::safe;
use bass_sys::BASS_ATTRIB_FREQ;
use ff_core::audio_fades::{curve, Fade};

use super::bass::{get_frequency, set_volume, slide, BassBackend, EngineBand};
use super::{
    advance_engine_wobble, engine_band_weights, engine_freq_mult, engine_load_gain, ENGINE_BANDS,
    ENGINE_BAND_RATE_MAX, ENGINE_BAND_RATE_MIN, ENGINE_CLASSIC_LOOP_KEY, ENGINE_LOOP_GAIN,
    ENGINE_LOOP_KEY, ENGINE_RESUME_FADE_S, ENGINE_RPM_IDLE, ENGINE_SLIDE_MS, ENGINE_SLIDE_SNAP_MS,
    ENGINE_SLIDE_SNAP_RPM, ENGINE_START_ASSUMED_LEN_S, ENGINE_START_CROSSFADE_S,
    ENGINE_START_FADE_IN_CURVE, ENGINE_START_FADE_OUT_CURVE, ENGINE_START_SETTLE_CURVE,
    ENGINE_START_SETTLE_S, ENGINE_START_TAIL_ANCHOR,
};

impl BassBackend {
    /// A fade that drives the engine loop's intro gain (0 = silent under the
    /// crank, 1 = full), presenting `start` at once as the Python `Fade` did.
    fn intro_gain_fade(
        &self,
        start: f64,
        end: f64,
        duration_s: f64,
        curve_name: &str,
        delay_s: f64,
        end_starting: bool,
    ) -> Fade {
        let gain = Rc::clone(&self.engine_intro_gain);
        let on_done: Option<Box<dyn FnMut()>> = if end_starting {
            let starting = Rc::clone(&self.engine_starting);
            Some(Box::new(move || starting.set(false)))
        } else {
            None
        };
        Fade::with_options(
            move |value| gain.set(value.clamp(0.0, 1.0)),
            start,
            end,
            duration_s,
            curve(curve_name),
            delay_s,
            on_done,
        )
    }

    pub(super) fn engine_start(&mut self, play_start_sound: bool) {
        if self.engine_running {
            return;
        }
        self.engine_running = true;
        self.fades.clear();
        // Hold the loop silent while the ignition one-shot plays; crossfade it
        // up at the tail. A silent (resume) start skips the crank.
        self.engine_intro_gain.set(0.0);
        self.engine_intro_load.set(0.0);
        if play_start_sound {
            self.begin_engine_start_crossfade();
        } else {
            let fade = self.intro_gain_fade(
                0.0,
                1.0,
                ENGINE_RESUME_FADE_S,
                ENGINE_START_FADE_IN_CURVE,
                0.0,
                false,
            );
            self.fades.add(fade);
        }
        self.engine_bands.clear();
        self.engine_wobble.clear();
        if !self.engine_voice_classic {
            for (key, native) in ENGINE_BANDS {
                let Some(stream) = self.sfx_stream(key, true) else {
                    continue;
                };
                let handle = stream.handle();
                let started = get_frequency(handle).and_then(|base_freq| {
                    set_volume(handle, 0.0)?;
                    safe::channel_play(handle, false)?;
                    Ok(base_freq)
                });
                let Ok(base_freq) = started else {
                    continue;
                };
                self.engine_bands.push(EngineBand {
                    native,
                    stream,
                    base_freq,
                    last_rate_target: base_freq,
                    last_volume: 0.0,
                });
                self.engine_wobble.push([0.0, 0.0]); // [rate walk, gain walk]
            }
        }
        if self.engine_bands.len() < 2 {
            // Not enough cuts for a crossfade ring (a clean clone carries only
            // the synthesized engine/idle): legacy single pitched loop.
            for band in self.engine_bands.drain(..) {
                let _ = safe::channel_stop(band.stream.handle());
                // Dropped here: the stream is freed.
            }
            let mut stream = None;
            if self.engine_voice_classic {
                stream = self.sfx_stream(ENGINE_CLASSIC_LOOP_KEY, true);
                if stream.is_none() {
                    log::warn!(
                        "Classic engine cut {ENGINE_CLASSIC_LOOP_KEY} is not in this build; using {ENGINE_LOOP_KEY} pitched instead"
                    );
                }
            }
            if stream.is_none() {
                stream = self.sfx_stream(ENGINE_LOOP_KEY, true);
            }
            if let Some(loop_stream) = &stream {
                let handle = loop_stream.handle();
                match get_frequency(handle).and_then(|base_freq| {
                    set_volume(handle, 0.0)?;
                    safe::channel_play(handle, false)?;
                    Ok(base_freq)
                }) {
                    Ok(base_freq) => self.engine_base_freq = base_freq,
                    Err(_) => stream = None,
                }
            }
            self.engine_stream = stream;
        }
        self.set_engine_rpm(ENGINE_RPM_IDLE, 0.0);
    }

    /// Play `engine/start` at full volume and blend into the loop at its tail.
    fn begin_engine_start_crossfade(&mut self) {
        self.engine_starting.set(true);
        let Some(stream) = self.sfx_stream("engine/start", false) else {
            // No crank available: bring the loop up promptly so the engine is
            // still audible.
            let fade = self.intro_gain_fade(0.0, 1.0, ENGINE_RESUME_FADE_S, "linear", 0.0, true);
            self.fades.add(fade);
            return;
        };
        let handle = stream.handle();
        let base = (self.buses.category_volume(super::backend::Category::Engine)
            * self.buses.master)
            .clamp(0.0, 1.0);
        if let Err(err) = set_volume(handle, base).and_then(|()| safe::channel_play(handle, false))
        {
            log::warn!("Could not play engine/start ({err})");
            let fade = self.intro_gain_fade(0.0, 1.0, ENGINE_RESUME_FADE_S, "linear", 0.0, true);
            self.fades.add(fade);
            return;
        }
        self.retain(stream);
        self.engine_intro_stream = Some(handle);
        let clip_len = Self::stream_length_s(handle);
        let delay = if ENGINE_START_TAIL_ANCHOR {
            (clip_len - ENGINE_START_CROSSFADE_S).max(0.0)
        } else {
            0.0
        };
        // Boost the loop to full (crank) load through the handoff so it meets
        // the crank tail at the same level instead of the quieter off-throttle
        // idle.
        self.engine_intro_load.set(1.0);

        // The crank itself: a dying stream ignores the slide, like the Python
        // `contextlib.suppress(BassError)`.
        let fade_crank = move |m: f64| {
            let _ = set_volume(handle, base * m);
        };
        self.fades.add(Fade::with_options(
            fade_crank,
            1.0,
            0.0,
            ENGINE_START_CROSSFADE_S,
            curve(ENGINE_START_FADE_OUT_CURVE),
            delay,
            None,
        ));
        let fade_in = self.intro_gain_fade(
            0.0,
            1.0,
            ENGINE_START_CROSSFADE_S,
            ENGINE_START_FADE_IN_CURVE,
            delay,
            true,
        );
        self.fades.add(fade_in);
        // Once the crossfade completes, ease the load boost back off so the
        // loop settles to its real off-throttle volume.
        let load = Rc::clone(&self.engine_intro_load);
        self.fades.add(Fade::with_options(
            move |value| load.set(value.clamp(0.0, 1.0)),
            1.0,
            0.0,
            ENGINE_START_SETTLE_S,
            curve(ENGINE_START_SETTLE_CURVE),
            delay + ENGINE_START_CROSSFADE_S,
            None,
        ));
    }

    /// Length of a stream in seconds, or a safe fallback.
    pub(super) fn stream_length_s(handle: u32) -> f64 {
        safe::channel_length_seconds(handle).unwrap_or(ENGINE_START_ASSUMED_LEN_S)
    }

    pub(super) fn update(&mut self, dt: f64) {
        self.collect_radio_stream();
        self.fades.update(dt);
        // The ignition fades moved the intro gain or load boost: re-apply the
        // engine level at the last known rpm, as the Python fade callbacks
        // did on every tick.
        let intro = (self.engine_intro_gain.get(), self.engine_intro_load.get());
        if self.engine_running && intro != self.intro_applied {
            self.set_engine_rpm(self.engine_last_rpm, self.engine_last_throttle);
        }
        // Advance the per-band anti-repetition walks; set_engine_rpm applies
        // them.
        advance_engine_wobble(&mut self.engine_wobble, dt, &mut self.wobble_rng);
    }

    pub(super) fn engine_stop(&mut self, shutdown_sound: bool) {
        self.reverse_stop();
        if !self.engine_running {
            return;
        }
        self.engine_running = false;
        self.fades.clear();
        self.engine_intro_gain.set(1.0);
        self.engine_intro_load.set(0.0);
        self.engine_starting.set(false);
        self.engine_intro_stream = None;
        let bands = std::mem::take(&mut self.engine_bands);
        for band in bands {
            self.fade_out(band.stream, 250);
        }
        self.engine_wobble.clear();
        if let Some(stream) = self.engine_stream.take() {
            self.fade_out(stream, 250);
        }
        if shutdown_sound {
            self.play("engine/shutdown", 1.0, 0.0);
        }
    }

    /// Track RPM: crossfade the multisample ring, or pitch the legacy loop.
    ///
    /// With the ring, each band's playback rate also slides toward
    /// `rpm / native_rpm` (clamped) so the pitch is continuous through a
    /// crossfade instead of stepping between the cuts' recorded speeds.
    pub(super) fn set_engine_rpm(&mut self, rpm: f64, throttle: f64) {
        if !(self.engine_running && (!self.engine_bands.is_empty() || self.engine_stream.is_some()))
        {
            return;
        }
        // A step-sized rpm change (shift re-entry) snaps; wander glides.
        let slide_ms = if (rpm - self.engine_last_rpm).abs() > ENGINE_SLIDE_SNAP_RPM {
            ENGINE_SLIDE_SNAP_MS
        } else {
            ENGINE_SLIDE_MS
        };
        self.engine_last_rpm = rpm;
        self.engine_last_throttle = throttle;
        let intro_gain = self.engine_intro_gain.get();
        let intro_load = self.engine_intro_load.get();
        self.intro_applied = (intro_gain, intro_load);
        let mut load_gain = engine_load_gain(throttle);
        // During the ignition handoff, boost load toward full so the loop
        // meets the crank tail; the boost eases back to 0 afterward.
        load_gain += intro_load * (1.0 - load_gain);
        let level = (ENGINE_LOOP_GAIN
            * load_gain
            * self.engine_duck
            * self.buses.engine
            * self.buses.speech_duck
            * self.buses.master
            * intro_gain)
            .clamp(0.0, 1.0);
        if !self.engine_bands.is_empty() {
            let natives: Vec<f64> = self.engine_bands.iter().map(|band| band.native).collect();
            let weights = engine_band_weights(rpm, &natives);
            let mut failed = false;
            for (i, band) in self.engine_bands.iter_mut().enumerate() {
                let w = weights[i];
                let wob = self.engine_wobble.get(i).copied().unwrap_or([0.0, 0.0]);
                let mut rate =
                    (rpm / band.native).clamp(ENGINE_BAND_RATE_MIN, ENGINE_BAND_RATE_MAX);
                rate *= 1.0 + wob[0];
                let handle = band.stream.handle();
                let target = band.base_freq * rate;
                let volume = level * w * (1.0 + wob[1]);
                if slide(handle, BASS_ATTRIB_FREQ, target, slide_ms)
                    .and_then(|()| set_volume(handle, volume))
                    .is_err()
                {
                    failed = true;
                    break;
                }
                band.last_rate_target = target;
                band.last_volume = volume;
            }
            if failed {
                self.engine_bands.clear();
            }
            return;
        }
        let Some(stream) = &self.engine_stream else {
            return;
        };
        let handle = stream.handle();
        let target = self.engine_base_freq * engine_freq_mult(rpm);
        if slide(handle, BASS_ATTRIB_FREQ, target, slide_ms)
            .and_then(|()| set_volume(handle, level))
            .is_err()
        {
            self.engine_stream = None;
        }
    }

    /// Shift-gap disengage: scale the engine bed below the load floor.
    pub(super) fn set_engine_duck(&mut self, duck: f64) {
        let duck = duck.clamp(0.0, 1.0);
        if duck == self.engine_duck {
            return;
        }
        self.engine_duck = duck;
        self.set_engine_rpm(self.engine_last_rpm, self.engine_last_throttle);
    }
}
