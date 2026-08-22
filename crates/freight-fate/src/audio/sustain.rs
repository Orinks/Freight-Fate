//! The BASS half of sustain-loop-with-release playback (the Python
//! `audio_loops.SustainLoop`).
//!
//! A real "attack -> sustain -> release" sound -- a horn held down, a siren,
//! an engine that idles then spins down -- should loop only a short interior
//! region while it is held, then play its natural release tail once let go.
//! Plain whole-file looping instead replays the attack every cycle and never
//! lets the release ring out.
//!
//! [`SustainLoop`] drives a raw `BASS_ChannelSetSync` position sync that
//! seeks the stream back to the loop start each time playback reaches the
//! loop end; [`SustainLoop::release`] removes the sync so playback flows
//! past the loop end through to the end of the file. Because the sync is a
//! *mixtime* sync, the seek happens during mixing and the loop is seamless.
//! The closure behind the sync is the only game code that runs on the BASS
//! mixer thread; the [`SyncGuard`] keeps it alive for exactly as long as
//! BASS holds a pointer to it (the Python class pinned its `SYNCPROC` on the
//! instance for the same reason).
//!
//! The unit conversion and loop-point validation live in
//! `ff_core::audio_loops` ([`SustainLoopSpec::resolve`]); this file is the
//! part that needs a live stream.

use std::fmt;

use bass_sys::safe::{self, BassError, SyncGuard};
use bass_sys::{BASS_ATTRIB_FREQ, BASS_SYNC_MIXTIME, BASS_SYNC_POS};
use ff_core::audio_loops::{LoopPointError, SustainLoopSpec};

/// Why a sustain loop could not be installed: the Python constructor's
/// `ValueError` (bad loop points) or a BASS refusal.
#[derive(Debug, Clone, PartialEq)]
pub enum SustainLoopError {
    LoopPoints(LoopPointError),
    Bass(BassError),
}

impl fmt::Display for SustainLoopError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::LoopPoints(err) => write!(f, "{err}"),
            Self::Bass(err) => write!(f, "BASS refused the loop sync: {err}"),
        }
    }
}

impl std::error::Error for SustainLoopError {}

impl From<LoopPointError> for SustainLoopError {
    fn from(err: LoopPointError) -> Self {
        Self::LoopPoints(err)
    }
}

impl From<BassError> for SustainLoopError {
    fn from(err: BassError) -> Self {
        Self::Bass(err)
    }
}

/// A live sustain loop on one BASS stream, seeking start<-end each cycle.
///
/// Construct it on a stream that is created **non-looping** and already
/// playing (or about to play): it installs a mixtime position sync at
/// `loop_end` that seeks back to `loop_start`. Call [`release`] to let the
/// release tail play out, or [`stop`] when tearing the loop down.
///
/// [`release`]: SustainLoop::release
/// [`stop`]: SustainLoop::stop
#[derive(Debug)]
pub struct SustainLoop {
    channel: u32,
    sync: Option<SyncGuard>,
    start_byte: u64,
    end_byte: u64,
    released: bool,
}

impl SustainLoop {
    /// Install the loop on `channel` (a BASS stream handle).
    pub fn new(channel: u32, spec: SustainLoopSpec) -> Result<Self, SustainLoopError> {
        // The stream's playback rate, for sample-unit loop points; an
        // unreadable one only matters for sample units, where `resolve`
        // refuses it.
        let freq = safe::channel_get_attribute(channel, BASS_ATTRIB_FREQ)
            .ok()
            .map(f64::from);
        let resolved = spec.resolve(freq)?;
        let start_byte = safe::seconds_to_bytes(channel, resolved.start_s)?;
        let end_byte = safe::seconds_to_bytes(channel, resolved.end_s)?;
        // The seek is done at mixtime so it lands exactly on the loop
        // boundary with no audible gap. Runs on the mixer thread.
        let sync = safe::set_sync(
            channel,
            BASS_SYNC_POS | BASS_SYNC_MIXTIME,
            end_byte,
            Box::new(move |_sync, playing_channel, _data| {
                let _ = safe::channel_set_position_bytes(playing_channel, start_byte);
            }),
        )?;
        Ok(Self {
            channel,
            sync: Some(sync),
            start_byte,
            end_byte,
            released: false,
        })
    }

    /// The stream the loop is installed on.
    pub fn channel(&self) -> u32 {
        self.channel
    }

    /// The loop start, in bytes of the stream.
    pub fn start_byte(&self) -> u64 {
        self.start_byte
    }

    /// The loop end, in bytes of the stream.
    pub fn end_byte(&self) -> u64 {
        self.end_byte
    }

    pub fn released(&self) -> bool {
        self.released
    }

    /// Remove the loop sync so playback continues into the release tail.
    ///
    /// Idempotent: safe to call more than once (e.g. a defensive stop after
    /// a key release).
    pub fn release(&mut self) {
        if self.released {
            return;
        }
        self.released = true;
        if let Some(sync) = self.sync.take() {
            if let Err(err) = sync.remove() {
                // The stream may already be gone; BASS took the sync with it.
                log::debug!("SustainLoop.release: sync already removed ({err})");
            }
        }
    }

    /// Tear the loop down. The caller is responsible for stopping the stream.
    pub fn stop(&mut self) {
        self.release();
    }
}
