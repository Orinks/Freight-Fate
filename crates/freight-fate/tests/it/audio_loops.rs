//! Port of the BASS-stream half of `tests/test_audio_loops.py`: the sustain
//! loop on a real, non-looping horn stream. (The `to_seconds` tests live
//! with the pure half in `ff_core::audio_loops`.)
//!
//! Wrapped in a module so `cargo test -p freight-fate audio` selects them.

mod audio_loops {
    use std::time::Duration;

    use bass_sys::safe;
    use freight_fate::audio::{
        asset_bytes, SustainLoop, SustainLoopError, SustainLoopSpec, HORN_LOOP, HORN_LOOP_END,
        HORN_LOOP_START, SFX_EXTENSIONS,
    };

    use crate::audio_support::{bass_rig, shipped_sounds, wait_for};

    /// A real, non-looping BASS stream for the horn (the engine keeps the
    /// device up), or None when BASS is absent -- or when the horn recording
    /// itself is not here to stream, which is a checkout without LFS.
    fn horn_stream() -> Option<(crate::audio_support::Rig, safe::Stream)> {
        if !shipped_sounds() {
            return None;
        }
        let rig = bass_rig()?;
        let (data, _ext) = asset_bytes("vehicle/horn", SFX_EXTENSIONS).expect("vehicle/horn");
        let stream = safe::stream_create_mem(&data, 0).expect("horn stream");
        Some((rig, stream))
    }

    #[test]
    fn test_sustain_loop_computes_byte_positions_from_samples() {
        let Some((_rig, stream)) = horn_stream() else {
            return;
        };
        let mut sustain = SustainLoop::new(stream.handle(), HORN_LOOP).unwrap();
        // Verified against the shipped 44100 Hz horn asset.
        assert_eq!(sustain.start_byte(), 47264);
        assert!(sustain.end_byte() > sustain.start_byte());
        assert!(!sustain.released());
        sustain.stop();
    }

    #[test]
    fn test_sustain_loop_release_is_idempotent() {
        let Some((_rig, stream)) = horn_stream() else {
            return;
        };
        let mut sustain = SustainLoop::new(stream.handle(), HORN_LOOP).unwrap();
        sustain.release();
        assert!(sustain.released());
        sustain.release(); // must not fail a second time
        sustain.stop(); // nor when torn down after release
        assert!(sustain.released());
    }

    #[test]
    fn test_sustain_loop_rejects_inverted_points() {
        let Some((_rig, stream)) = horn_stream() else {
            return;
        };
        let inverted = SustainLoopSpec::samples(HORN_LOOP_END as f64, HORN_LOOP_START as f64);
        match SustainLoop::new(stream.handle(), inverted) {
            Err(SustainLoopError::LoopPoints(_)) => {}
            other => panic!("expected a loop-point refusal, got {other:?}"),
        }
    }

    #[test]
    fn test_sustain_loop_seeks_back_at_the_loop_end_until_released() {
        // The mechanism itself, live on the no-sound device: held, the horn
        // outlives its own clip (the sync keeps seeking it back); released,
        // it runs on through the tail and ends.
        let Some((_rig, stream)) = horn_stream() else {
            return;
        };
        let handle = stream.handle();
        let clip_s = safe::channel_length_seconds(handle).unwrap();
        assert!(clip_s <= 1.0, "the horn clip grew: {clip_s} s");
        let mut sustain = SustainLoop::new(handle, HORN_LOOP).unwrap();
        safe::channel_play(handle, false).unwrap();
        std::thread::sleep(Duration::from_secs_f64(clip_s + 0.5));
        assert_eq!(
            safe::channel_is_active(handle),
            bass_sys::BASS_ACTIVE_PLAYING,
            "the held horn ended: the loop did not seek back"
        );
        sustain.release();
        assert!(
            wait_for(Duration::from_secs(3), || safe::channel_is_active(handle)
                == bass_sys::BASS_ACTIVE_STOPPED),
            "the released horn never rang out"
        );
    }
}
