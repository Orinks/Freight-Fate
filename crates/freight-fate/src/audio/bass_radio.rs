//! The BASS backend's music channel: shipped tracks, personal playlist
//! files, and live radio streams opened off the game thread.

use std::sync::{Arc, Mutex};

use bass_sys::safe::{self, Stream};
use bass_sys::{BASS_ATTRIB_VOL, BASS_STREAM_AUTOFREE};

use super::assets::{asset_bytes, MUSIC_EXTENSIONS};
use super::bass::{is_playing, set_volume, slide, BassBackend};
use super::{parse_icy_stream_title_text, AudioError};

/// The radio-connect state shared between the game thread and the connect
/// workers, every field guarded by the one mutex. The generation counter
/// tells a finished worker whether its request is still the current one;
/// the pending slot is how an opened stream crosses back to the game
/// thread, which alone touches `music_stream`.
#[derive(Default)]
pub(super) struct RadioShared {
    pub generation: u64,
    pub pending: Option<(String, u32, Stream)>, // (url, fade_ms, stream)
    pub connecting_url: Option<String>,
    pub failed_url: Option<String>,
}

/// Open a stream off-thread, unless the driver has moved on since.
fn radio_worker(shared: Arc<Mutex<RadioShared>>, url: String, generation: u64, fade_ms: u32) {
    match safe::stream_create_url(&url, BASS_STREAM_AUTOFREE) {
        Err(err) => {
            log::info!("Radio stream unavailable: {url} ({err})");
            let mut radio = shared.lock().unwrap_or_else(|e| e.into_inner());
            if generation == radio.generation {
                radio.failed_url = Some(url);
                radio.connecting_url = None;
            }
        }
        Ok(stream) => {
            let mut radio = shared.lock().unwrap_or_else(|e| e.into_inner());
            if generation == radio.generation {
                radio.pending = Some((url, fade_ms, stream)); // handed over to the game thread
                radio.connecting_url = None;
            }
            // Otherwise a newer request already won and the stream is dropped
            // (freed) here.
        }
    }
}

impl BassBackend {
    pub(super) fn play_music(&mut self, track: &str, fade_ms: u32) {
        if self.music_track.as_deref() == Some(track) {
            return;
        }
        self.play_music_at(track, fade_ms, 0.0);
    }

    /// Play a shipped track from `start_s` seconds in.
    ///
    /// The station rotation tunes in part way through whatever is on the air,
    /// so the stream is positioned before it is started -- decoded from
    /// memory, so the seek is exact. A seek that fails is only ever the
    /// difference between hearing the song from the middle and hearing it
    /// from the top, so it is logged and the track plays anyway.
    ///
    /// Unlike [`Self::play_music`] this does not short-circuit on the track
    /// already being the one loaded: the point of the call is the position.
    pub(super) fn play_music_at(&mut self, track: &str, fade_ms: u32, start_s: f64) {
        self.cancel_radio_connect();
        let Some((data, _ext)) = asset_bytes(&format!("music/{track}"), MUSIC_EXTENSIONS) else {
            log::warn!("Missing music track: {track}");
            return;
        };
        if let Some(stream) = self.music_stream.take() {
            self.fade_out(stream, 800);
            self.music_track = None;
        }
        let Some(stream) = self.make_stream(data, track, false) else {
            return;
        };
        let handle = stream.handle();
        let level = self.buses.music_level();
        if start_s > 0.0 {
            if let Err(err) = safe::seconds_to_bytes(handle, start_s)
                .and_then(|bytes| safe::channel_set_position_bytes(handle, bytes))
            {
                log::info!("Could not start {track} at {start_s:.1}s ({err})");
            }
        }
        if let Err(err) = set_volume(handle, 0.0)
            .and_then(|()| safe::channel_play(handle, false))
            .and_then(|()| slide(handle, BASS_ATTRIB_VOL, level, fade_ms))
        {
            log::warn!("Could not play music {track} ({err})");
            return;
        }
        self.music_stream = Some(stream);
        self.music_track = Some(track.to_string());
    }

    /// Tune a live internet stream, connecting off the game thread.
    ///
    /// Opening a URL blocks until the server answers, which on a dead or
    /// stalling station is seconds -- too long to spend inside a frame. The
    /// connect runs on a worker; `update` collects the opened stream back on
    /// the game thread. A failed connect fails on the NEXT call for the same
    /// URL, which is exactly when the driving state's reconnect loop retries
    /// a silent radio -- the fallback machinery still gets its error and
    /// speaks, just without the freeze.
    pub(super) fn play_radio_stream(&mut self, url: &str, fade_ms: u32) -> Result<(), AudioError> {
        // Same URL only dedupes while the stream is actually producing audio;
        // a stalled or dead connection must be torn down and recreated, or a
        // re-tune to the same station silently does nothing.
        if self.music_track.as_deref() == Some(url) && self.music_playing() {
            return Ok(());
        }
        let generation = {
            let mut radio = self.radio.lock().unwrap_or_else(|e| e.into_inner());
            if radio.connecting_url.as_deref() == Some(url) {
                return Ok(()); // already on its way; silence is the caller's retry cue
            }
            if radio.failed_url.as_deref() == Some(url) {
                // The last attempt never produced audio; say so now, and let
                // a later tune back to this station start a fresh attempt.
                radio.failed_url = None;
                return Err(AudioError::new("radio stream unavailable"));
            }
            radio.generation += 1;
            radio.pending = None;
            radio.connecting_url = Some(url.to_string());
            radio.generation
        };
        if let Some(stream) = self.music_stream.take() {
            self.fade_out(stream, 800);
            self.music_track = None;
        }
        let shared = Arc::clone(&self.radio);
        let worker_url = url.to_string();
        self.radio_threads.retain(|thread| !thread.is_finished());
        match std::thread::Builder::new()
            .name("radio-connect".to_string())
            .spawn(move || radio_worker(shared, worker_url, generation, fade_ms))
        {
            Ok(handle) => self.radio_threads.push(handle),
            Err(err) => {
                log::warn!("Could not start the radio connect worker: {err}");
                let mut radio = self.radio.lock().unwrap_or_else(|e| e.into_inner());
                if generation == radio.generation {
                    radio.failed_url = Some(url.to_string());
                    radio.connecting_url = None;
                }
            }
        }
        Ok(())
    }

    /// Wire up a stream a worker finished opening; game thread only.
    pub fn collect_radio_stream(&mut self) {
        let pending = {
            let mut radio = self.radio.lock().unwrap_or_else(|e| e.into_inner());
            radio.pending.take()
        };
        let Some((url, fade_ms, stream)) = pending else {
            return;
        };
        if self.music_track.is_some() {
            // Something else claimed the music channel while the station was
            // connecting (a menu bed, another tune); the late arrival loses.
            drop(stream);
            return;
        }
        let handle = stream.handle();
        let level = self.buses.music_level();
        if let Err(err) = set_volume(handle, 0.0)
            .and_then(|()| safe::channel_play(handle, false))
            .and_then(|()| slide(handle, BASS_ATTRIB_VOL, level, fade_ms))
        {
            log::warn!("Could not play radio stream: {url} ({err})");
            let mut radio = self.radio.lock().unwrap_or_else(|e| e.into_inner());
            radio.failed_url = Some(url);
            return;
        }
        self.music_stream = Some(stream);
        self.music_track = Some(url);
    }

    /// Orphan any connect in flight; its stream is freed, not wired up.
    fn cancel_radio_connect(&mut self) {
        let pending = {
            let mut radio = self.radio.lock().unwrap_or_else(|e| e.into_inner());
            radio.generation += 1;
            radio.connecting_url = None;
            radio.failed_url = None;
            radio.pending.take()
        };
        drop(pending); // the stream is freed with it
    }

    /// Play one media file from disk on the music channel.
    ///
    /// Reads the bytes and decodes from memory like the shipped music does,
    /// so a NAS path is read once per track rather than streamed over SMB.
    /// Fails when the file cannot be read or decoded, so the radio layer can
    /// skip to the next playlist entry.
    pub(super) fn play_music_file(&mut self, path: &str, fade_ms: u32) -> Result<(), AudioError> {
        let key = format!("file:{path}");
        self.cancel_radio_connect();
        let data: Arc<[u8]> = match std::fs::read(path) {
            Ok(data) => Arc::from(data),
            Err(_) => return Err(AudioError::new(format!("could not read {path}"))),
        };
        if let Some(stream) = self.music_stream.take() {
            self.fade_out(stream, 800);
            self.music_track = None;
        }
        let Some(stream) = self.make_stream(data, &key, false) else {
            return Err(AudioError::new(format!("could not decode {path}")));
        };
        let handle = stream.handle();
        let level = self.buses.music_level();
        if set_volume(handle, 0.0)
            .and_then(|()| safe::channel_play(handle, false))
            .and_then(|()| slide(handle, BASS_ATTRIB_VOL, level, fade_ms))
            .is_err()
        {
            return Err(AudioError::new(format!("could not play {path}")));
        }
        self.music_stream = Some(stream);
        self.music_track = Some(key);
        Ok(())
    }

    pub(super) fn music_playing(&self) -> bool {
        self.music_stream
            .as_ref()
            .map(|stream| is_playing(stream.handle()))
            .unwrap_or(false)
    }

    /// The song title the playing stream reports in its ICY metadata.
    ///
    /// Read straight off the BASS channel each call: the tag block is a
    /// pointer into BASS's own buffer, so this is a string copy, not a
    /// network round trip. None when nothing is streaming, when the stream
    /// carries no metadata, or when the last title block was empty.
    pub(super) fn radio_now_playing(&self) -> Option<String> {
        let stream = self.music_stream.as_ref()?;
        if !self.music_playing() {
            return None;
        }
        let raw = safe::tags_meta(stream.handle())?;
        parse_icy_stream_title_text(&raw)
    }

    pub(super) fn stop_music(&mut self, fade_ms: u32) {
        // Cancel before the early return: a radio still connecting has no
        // stream yet, and stopping the radio must orphan that connect too.
        self.cancel_radio_connect();
        let Some(stream) = self.music_stream.take() else {
            return;
        };
        self.fade_out(stream, fade_ms);
        self.music_track = None;
    }

    // -- inspection ------------------------------------------------------------

    /// The URL a connect worker is still opening, if any.
    pub fn radio_connecting_url(&self) -> Option<String> {
        self.radio
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .connecting_url
            .clone()
    }

    /// The URL whose last connect failed and has not been reported yet.
    pub fn radio_failed_url(&self) -> Option<String> {
        self.radio
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .failed_url
            .clone()
    }

    /// Whether an opened stream is waiting for the game thread to collect.
    pub fn radio_stream_pending(&self) -> bool {
        self.radio
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .pending
            .is_some()
    }
}
