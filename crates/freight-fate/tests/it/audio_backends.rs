//! Port of `tests/test_audio_backends.py`: audio backend selection, the BASS
//! engine model, and the facade's bank / jake-voice / asset logic.
//!
//! The pygame-only tests of the Python file (`test_env_var_forces_pygame_
//! backend` asserted "pygame or none", the pygame horn and music tests) have
//! no backend to run against here: the Rust build routes the pygame
//! preference to the null backend, which the first test pins. Tests that
//! faked `sound_lib` streams run against the real BASS no-sound device
//! instead, with a localhost station standing in for the faked URL stream.
//!
//! Wrapped in a module so `cargo test -p freight-fate audio` selects them.

mod audio_backends {
    use std::cell::RefCell;
    use std::rc::Rc;
    use std::time::Duration;

    use bass_sys::safe;
    use ff_core::ladder_earcons::{register_ladder_earcons, CONFIRMATION_NOTE_KEY};
    use ff_core::music::ALL_MUSIC_TRACKS;
    use ff_core::pyrandom::PyRandom;
    use freight_fate::audio::*;

    use crate::audio_support::{
        bass_rig, bass_rig_with_recordings, rig, shipped_music, shipped_sounds, sine_wav, wait_for,
        IcyServer,
    };

    /// Every facade call must be safe regardless of backend.
    fn exercise(a: &mut AudioEngine) {
        a.play("ui/menu_select");
        a.play("nonexistent/sound");
        a.engine_start();
        a.set_engine_rpm_with(1500.0, 0.5);
        a.set_engine_rpm_with(2200.0, 1.0);
        a.set_road_noise(20.0);
        a.set_road_noise(0.0);
        a.set_weather_with(Some("weather/rain_light"), 0.8);
        a.set_weather(None);
        a.set_wind(0.5);
        a.set_ambient_with(Some("ambient/truck_stop"), 0.4);
        a.play_music("menu_theme");
        a.play_music("open_road");
        a.play_music("not_a_track");
        a.set_volumes(&VolumeUpdate::default().master(0.5).sfx(0.5).music(0.5));
        a.stop_world();
        a.stop_music();
        a.shutdown();
    }

    #[test]
    fn test_bass_backend_selected_by_default() {
        let Some(mut r) = bass_rig() else { return };
        assert_eq!(r.engine.backend_name(), "bass");
        assert!(r.engine.enabled());
        exercise(&mut r.engine);
    }

    #[test]
    fn test_env_var_forces_pygame_backend() {
        // The Rust build has no pygame mixer: the preference lands on the
        // null backend, and every call stays safe.
        let _guard = crate::audio_support::audio_lock();
        let mut a = AudioEngine::from_preference("pygame");
        assert_eq!(a.backend_name(), "none");
        assert!(!a.enabled());
        exercise(&mut a);
    }

    #[test]
    fn test_fallback_to_pygame_when_bass_init_fails() {
        // What the facade builds when BASS refuses: the null backend, with
        // the whole surface still callable.
        let _guard = crate::audio_support::audio_lock();
        let mut a = AudioEngine::with_backend(Box::new(NullBackend::new()));
        assert_eq!(a.backend_name(), "none");
        exercise(&mut a);
    }

    #[test]
    fn test_engine_freq_mult_mapping() {
        assert_eq!(engine_freq_mult(ENGINE_RPM_IDLE), 1.0);
        assert!((engine_freq_mult(ENGINE_RPM_MAX) - ENGINE_FREQ_MAX_MULT).abs() < 1e-9);
        assert_eq!(engine_freq_mult(0.0), 1.0); // clamped below idle
        assert_eq!(engine_freq_mult(99_999.0), ENGINE_FREQ_MAX_MULT); // clamped above redline
        let mid = engine_freq_mult((ENGINE_RPM_IDLE + ENGINE_RPM_MAX) / 2.0);
        assert!((mid - (1.0 + ENGINE_FREQ_MAX_MULT) / 2.0).abs() < 1e-9);
    }

    #[test]
    fn test_engine_band_weights_edges_blend_and_pure_zones() {
        let natives: Vec<f64> = ENGINE_BANDS.iter().map(|(_k, rpm)| *rpm).collect();
        let n = natives.len();
        let solo = |index: usize| {
            let mut expected = vec![0.0; n];
            expected[index] = 1.0;
            expected
        };
        // Outside the ring the nearest band carries alone.
        assert_eq!(engine_band_weights(0.0, &natives), solo(0));
        assert_eq!(engine_band_weights(natives[0], &natives), solo(0));
        assert_eq!(engine_band_weights(natives[n - 1], &natives), solo(n - 1));
        assert_eq!(engine_band_weights(9999.0, &natives), solo(n - 1));
        // At the geometric midpoint of a gap exactly two bands blend equal-power.
        let mid = (natives[1] * natives[2]).sqrt();
        let w = engine_band_weights(mid, &natives);
        assert!(w[1] > 0.0 && w[2] > 0.0);
        assert_eq!(w.iter().filter(|x| **x > 0.0).count(), 2);
        assert!((w.iter().map(|x| x * x).sum::<f64>() - 1.0).abs() < 1e-6);
        // Just off a native rpm the band is PURE -- the crossfade windows are
        // narrow, so a cut near its recorded speed never shares the mix (this
        // is what kills both the formant smear and the two-pitch beat).
        for (i, native) in natives[..n - 1].iter().enumerate() {
            assert_eq!(engine_band_weights(native + 10.0, &natives), solo(i));
            if i > 0 {
                assert_eq!(engine_band_weights(native - 10.0, &natives), solo(i));
            }
        }
        // A sweep never needs more than a bounded stretch from any sounding
        // band: wherever a band has weight, rpm/native stays inside the
        // safety clamps.
        let mut rpm = 300.0;
        while rpm < 2400.0 {
            for (weight, native) in engine_band_weights(rpm, &natives).iter().zip(&natives) {
                if *weight > 1e-6 && natives[0] <= rpm && rpm <= natives[n - 1] {
                    let ratio = rpm / native;
                    assert!((ENGINE_BAND_RATE_MIN..=ENGINE_BAND_RATE_MAX).contains(&ratio));
                }
            }
            rpm += 7.0;
        }
    }

    #[test]
    fn test_engine_load_gain_keeps_audible_load_contour() {
        // Floor raised off the old 0.55 so coasting is not too quiet, but the
        // span stays wide enough to hear effort changes and the
        // automatic-shift unload.
        assert!((engine_load_gain(-1.0) - 0.68).abs() < 1e-9);
        assert!((engine_load_gain(0.0) - 0.68).abs() < 1e-9);
        assert!((engine_load_gain(0.45) - 0.824).abs() < 1e-9);
        assert!(engine_load_gain(0.08) < engine_load_gain(0.7));
        assert_eq!(engine_load_gain(1.0), 1.0);
        assert_eq!(engine_load_gain(2.0), 1.0);
    }

    #[test]
    fn test_split_volume_settings_apply_to_silent_backend() {
        let mut backend = NullBackend::new();
        backend.set_volumes(
            &VolumeUpdate::default()
                .master(0.8)
                .sfx(0.7)
                .music(0.6)
                .weather(0.5)
                .engine(0.4)
                .ui(0.9),
        );
        let buses = backend.buses();
        assert_eq!(buses.master, 0.8);
        assert_eq!(buses.sfx, 0.7);
        assert_eq!(buses.music, 0.6);
        assert_eq!(buses.weather, 0.5);
        assert_eq!(buses.engine, 0.4);
        assert_eq!(buses.ui, 0.9);
    }

    #[test]
    fn test_sound_lookup_prefers_ogg_when_available() {
        // asset_bytes answers from the pack on clean clones and from the
        // loose tree on builder machines; the extension preference holds
        // either way. Neither one here means there is nothing to prefer.
        if !shipped_sounds() {
            return;
        }
        for key in [
            "weather/rain_light",
            "weather/snow_wind",
            "vehicle/brake_air",
            "vehicle/brake_release",
            "vehicle/brake_set",
            "vehicle/horn",
            "vehicle/gear_shift",
            "vehicle/road",
        ] {
            let found = asset_bytes(key, SFX_EXTENSIONS);
            let (_data, ext) = found.unwrap_or_else(|| panic!("{key}"));
            assert_eq!(ext, "ogg", "{key}");
        }
    }

    #[test]
    fn test_engine_recordings_resolve_for_the_ring_and_one_shots() {
        // Looping beds may resolve to WAV (lossy edges break loop seams --
        // tools/fix_loop_seams.py); the licensed overlay's file wins where
        // present. One-shots stay ogg.
        if !shipped_sounds() {
            return;
        }
        let idle = asset_bytes("engine/idle", SFX_EXTENSIONS).unwrap().1;
        assert!(idle == "ogg" || idle == "wav");
        assert_eq!(
            asset_bytes("engine/start", SFX_EXTENSIONS).unwrap().1,
            "ogg"
        );
        assert_eq!(
            asset_bytes("engine/shutdown", SFX_EXTENSIONS).unwrap().1,
            "ogg"
        );
    }

    /// The clip's real length, decoded by BASS (the Python test used
    /// soundfile). `None` when BASS cannot load here.
    fn shipped_duration_s(key: &str) -> Option<f64> {
        let (data, _ext) = asset_bytes(key, SFX_EXTENSIONS).unwrap_or_else(|| panic!("{key}"));
        let stream = safe::stream_create_mem(&data, 0).ok()?;
        safe::channel_length_seconds(stream.handle()).ok()
    }

    #[test]
    fn test_engine_start_recording_is_short_one_shot() {
        let Some(_r) = bass_rig_with_recordings() else {
            return;
        };
        assert!(shipped_duration_s("engine/start").unwrap() <= 4.25);
    }

    #[test]
    fn test_vehicle_horn_and_shift_recordings_are_short_one_shots() {
        let Some(_r) = bass_rig_with_recordings() else {
            return;
        };
        assert!(shipped_duration_s("vehicle/horn").unwrap() <= 1.0);
        assert!(shipped_duration_s("vehicle/gear_shift").unwrap() <= 0.8);
    }

    #[test]
    fn test_asset_length_matches_a_real_decode_of_the_same_clip() {
        // A one-shot is handed to the mixer without a handle, so the only way
        // to know when it stops sounding is to measure the clip. Read from
        // the container's own headers -- no decoder, no audio device -- and
        // cross-checked here against an actual decode.
        let Some(_r) = bass_rig_with_recordings() else {
            return;
        };
        for key in [
            "driver/yawn",
            "events/spike_strip",
            "vehicle/signal_tone",
            "vehicle/bar_solid",
        ] {
            let decoded = shipped_duration_s(key).unwrap();
            assert!(
                (asset_length_s(key) - decoded).abs() <= 0.01,
                "{key}: header {} vs decode {decoded}",
                asset_length_s(key)
            );
        }
    }

    #[test]
    fn test_asset_length_covers_synthesized_cues_and_shrugs_at_unknown_keys() {
        // The Python test registered the enforcement signature; the ladder
        // earcons are the synthesized cues this build carries.
        register_ladder_earcons();
        assert!(
            asset_length_s(CONFIRMATION_NOTE_KEY) > 0.0,
            "a generated cue has a length too"
        );
        assert_eq!(asset_length_s("nothing/at_all"), 0.0);
    }

    #[test]
    fn test_bass_music_never_loops_catalog_tracks() {
        // Every catalog track has to open, which needs the music pack: with
        // only a pointer there is no track to open and no looping to check.
        if !shipped_music() {
            return;
        }
        let Some(mut r) = bass_rig() else { return };
        let bass = r.engine.bass().unwrap();
        assert!(bass.music_stream_handle().is_none());
        for track in ALL_MUSIC_TRACKS.iter() {
            r.engine.play_music_with(&track.key, 123);
            let bass = r.engine.bass().unwrap();
            let handle = bass
                .music_stream_handle()
                .unwrap_or_else(|| panic!("{} did not open", track.key));
            assert_eq!(safe::is_looping(handle), Ok(false), "{}", track.key);
            r.engine.stop_music_with(0);
        }
    }

    #[test]
    fn test_bass_radio_stream_uses_url_stream() {
        let Some(mut r) = bass_rig() else { return };
        let server = IcyServer::start(sine_wav(6.0, 1), None);
        r.engine.play_radio_stream_with(&server.url, 321).unwrap();
        let bass = r.engine.bass().unwrap();
        assert!(bass.music_track().is_none()); // the connect happens off-thread
        assert!(
            bass.radio_connecting_url().as_deref() == Some(server.url.as_str())
                || bass.radio_stream_pending()
        );
        let bass = r.engine.bass_mut().unwrap();
        bass.join_radio_workers(Duration::from_secs(10));
        assert!(
            bass.radio_stream_pending(),
            "the worker never opened the stream"
        );
        bass.collect_radio_stream();
        assert_eq!(server.connections(), 1);
        assert_eq!(bass.music_track(), Some(server.url.as_str()));
        let handle = bass.music_stream_handle().unwrap();
        // The fade-in was asked for: the stream is sliding up from zero.
        assert!(safe::channel_is_sliding(handle, bass_sys::BASS_ATTRIB_VOL));
        // A net stream may report "stalled" for a moment while its buffer
        // fills; it is producing audio shortly after.
        let bass = r.engine.bass().unwrap();
        assert!(
            wait_for(Duration::from_secs(5), || bass.music_playing()),
            "stream state {}",
            safe::channel_is_active(handle)
        );
    }

    #[test]
    fn test_bass_engine_wobble_meanders_and_shapes_the_ring() {
        // Anti-repetition: each band's rate and gain take a slow bounded
        // random walk so a seam-clean loop's period is never exactly fixed --
        // the ear cannot lock onto the recurrence. Rate stays within ~5 cents.
        let Some(mut r) = bass_rig() else { return };
        r.engine
            .set_volumes(&VolumeUpdate::default().master(1.0).engine(1.0));
        let bass = r.engine.bass_mut().unwrap();
        bass.set_wobble_rng(PyRandom::new_from_i64(7));
        r.engine.engine_start_with(false);
        let bass = r.engine.bass().unwrap();
        if bass.engine_bands().len() < 2 {
            eprintln!("the multisample ring is not installed; skipping");
            return;
        }
        for _ in 0..120 {
            // ~2 s of frames
            r.engine.update(1.0 / 60.0);
        }
        // Past the resume fade: intro gain is 1, so the level is the load alone.
        let bass = r.engine.bass().unwrap();
        assert_eq!(bass.engine_intro_gain(), 1.0);
        let [rate_walk, gain_walk] = bass.engine_wobble()[1]; // the 950 band's walks
        assert!(rate_walk != 0.0 && rate_walk.abs() <= ENGINE_WOBBLE_RATE_MAX);
        assert!(gain_walk != 0.0 && gain_walk.abs() <= ENGINE_WOBBLE_GAIN_MAX);

        r.engine.set_engine_rpm_with(950.0, 0.0);
        let bass = r.engine.bass().unwrap();
        let band = bass.engine_bands()[1]; // the 950 cut, pure at its native rpm
        assert_eq!(band.native, 950.0);
        let expected_rate = band.base_freq * (1.0 + rate_walk);
        assert!((band.last_rate_target - expected_rate).abs() < 1e-6);
        let base_level = engine_load_gain(0.0);
        assert!((band.last_volume - base_level * (1.0 + gain_walk)).abs() < 1e-9);
    }

    #[test]
    fn test_bass_radio_stream_recreates_a_stalled_stream() {
        // Re-tuning the SAME url must rebuild a dead connection (the dock bed
        // or a network stall killed it); only a live stream is allowed to
        // dedupe.
        let Some(mut r) = bass_rig() else { return };
        let server = IcyServer::start(sine_wav(0.3, 1), None);
        r.engine.play_radio_stream_with(&server.url, 100).unwrap();
        let bass = r.engine.bass_mut().unwrap();
        bass.join_radio_workers(Duration::from_secs(10));
        bass.collect_radio_stream();
        assert_eq!(server.connections(), 1);
        let bass = r.engine.bass().unwrap();
        assert!(wait_for(Duration::from_secs(5), || bass.music_playing()));
        // Live: the same url is a no-op.
        r.engine.play_radio_stream_with(&server.url, 100).unwrap();
        assert_eq!(server.connections(), 1);
        // The short clip ends -- a dead station -- and the retune reconnects.
        let handle = r.engine.bass().unwrap().music_stream_handle().unwrap();
        assert!(wait_for(Duration::from_secs(5), || {
            !super::audio_support_is_playing(handle)
        }));
        r.engine.play_radio_stream_with(&server.url, 100).unwrap();
        let bass = r.engine.bass_mut().unwrap();
        bass.join_radio_workers(Duration::from_secs(10));
        bass.collect_radio_stream();
        assert_eq!(server.connections(), 2);
        let bass = r.engine.bass().unwrap();
        assert!(wait_for(Duration::from_secs(5), || bass.music_playing()));
    }

    #[test]
    fn test_bass_engine_model_matches_available_cuts() {
        // With the multisample cuts installed the engine comes up as the
        // crossfade ring; a clean clone (synthesized engine/idle only) falls
        // back to the single pitched loop. Either way rpm tracking must be
        // safe.
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        let have_all_cuts = ENGINE_BANDS
            .iter()
            .all(|(key, _rpm)| asset_bytes(key, SFX_EXTENSIONS).is_some());
        r.engine.engine_start();
        assert!(r.engine.engine_running());
        let bass = r.engine.bass().unwrap();
        if have_all_cuts {
            assert_eq!(bass.engine_bands().len(), ENGINE_BANDS.len());
            assert!(bass.engine_stream_handle().is_none());
        } else {
            assert!(bass.engine_bands().is_empty());
            assert!(bass.engine_stream_handle().is_some());
            assert!(bass.engine_base_freq() > 0.0);
        }
        // frequency targets follow RPM; repeated slides must be safe
        for rpm in [600.0, 1100.0, 1800.0, 2200.0, 900.0] {
            r.engine.set_engine_rpm_with(rpm, 0.7);
        }
        r.engine.engine_stop();
        assert!(!r.engine.engine_running());
        let bass = r.engine.bass().unwrap();
        assert!(bass.engine_stream_handle().is_none());
        assert!(bass.engine_bands().is_empty());
    }

    #[test]
    fn test_engine_voice_setting_switches_models_live() {
        let Some(mut r) = bass_rig() else { return };
        let have_all_cuts = ENGINE_BANDS
            .iter()
            .all(|(key, _rpm)| asset_bytes(key, SFX_EXTENSIONS).is_some());
        r.engine.set_engine_voice(true); // classic
        r.engine.engine_start_with(false);
        let bass = r.engine.bass().unwrap();
        assert!(bass.engine_bands().is_empty());
        assert!(bass.engine_stream_handle().is_some()); // the classic pitched loop
        if have_all_cuts {
            r.engine.set_engine_voice(false); // back to real, live, mid-run
            assert!(r.engine.engine_running());
            let bass = r.engine.bass().unwrap();
            assert_eq!(bass.engine_bands().len(), ENGINE_BANDS.len());
            assert!(bass.engine_stream_handle().is_none());
        }
        r.engine.engine_stop();
    }

    #[test]
    fn test_both_1600_jake_cuts_ship() {
        // The jake A/B needs both cuts shipped -- the routing has nothing to
        // route to otherwise. (The Python test looked in the loose tree; the
        // Rust checkout carries them in the pack.)
        if !shipped_sounds() {
            return;
        }
        assert!(asset_bytes(JAKE_RECORDED_KEY, SFX_EXTENSIONS).is_some());
        assert!(asset_bytes(JAKE_CLASSIC_KEY, SFX_EXTENSIONS).is_some());
    }

    #[test]
    fn test_jake_voice_setting_routes_the_synth_key_and_applies_live() {
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        // has_asset resolves the key the player-facing catalog and the real
        // drive both use -- the routing must be invisible to callers.
        assert!(r.engine.has_asset(JAKE_RECORDED_KEY));
        r.engine.set_jake_voice(true); // classic, before anything is sounding
        assert!(r.engine.has_asset(JAKE_RECORDED_KEY));

        r.engine.set_jake_voice(false); // real again
        r.engine
            .start_loop_with(CH_JAKE, JAKE_RECORDED_KEY, 0.5, 300);
        let entry = r.engine.backend().loop_entry(CH_JAKE).unwrap();
        assert_eq!(entry.0, JAKE_RECORDED_KEY);

        r.engine.set_jake_voice(true); // classic, live, mid-growl
        let entry = r.engine.backend().loop_entry(CH_JAKE).unwrap();
        assert_eq!(entry.0, JAKE_CLASSIC_KEY);
        assert_eq!(entry.1, 0.5); // the level carries across the re-voice

        r.engine.set_jake_voice(false); // back to real, live
        let entry = r.engine.backend().loop_entry(CH_JAKE).unwrap();
        assert_eq!(entry.0, JAKE_RECORDED_KEY);

        r.engine.stop_loop(CH_JAKE);
    }

    #[test]
    fn test_the_jake_toggle_re_voices_whatever_band_is_sounding() {
        // A loop on a NON-jake channel is none of this toggle's business;
        // every jake band is (see the Python docstring's history).
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.set_jake_voice(false);
        // Asking for the 1800 band on "real" sounds the one recording -- that
        // is the routing. What this pins is that the toggle re-voices it.
        r.engine
            .start_loop_with(CH_JAKE, "engine/jake_1800", 0.4, 300);
        assert_eq!(
            r.engine.backend().loop_entry(CH_JAKE).unwrap().0,
            JAKE_RECORDED_KEY
        );
        r.engine.set_jake_voice(true);
        let entry = r.engine.backend().loop_entry(CH_JAKE).unwrap();
        assert_eq!(
            entry.0, JAKE_CLASSIC_KEY,
            "the 1800 band kept the old voice"
        );
        assert_eq!(entry.1, 0.4);
        r.engine.stop_loop(CH_JAKE);
    }

    #[test]
    fn test_classic_voice_prefers_the_original_recording() {
        // Settings "classic" promises the 1.8.x engine. Its cut ships under
        // its own key (engine_classic/idle) precisely because the licensed
        // overlay owns engine/idle -- with the rebuilt bank installed the
        // shared key is the rebuilt cut, and classic must not quietly follow
        // it.
        assert!(asset_bytes(ENGINE_CLASSIC_LOOP_KEY, SFX_EXTENSIONS).is_some());
        let Some(mut r) = bass_rig() else { return };
        r.engine.bass_mut().unwrap().record_requested_keys(true);
        r.engine.set_engine_voice(true); // classic
        r.engine.engine_start_with(false);
        let bass = r.engine.bass().unwrap();
        assert!(bass
            .requested_keys()
            .iter()
            .any(|k| k == ENGINE_CLASSIC_LOOP_KEY));
        assert!(bass.engine_bands().is_empty());
        assert!(bass.engine_stream_handle().is_some());
        r.engine.engine_stop();
    }

    #[test]
    fn test_bass_engine_falls_back_to_pitched_loop_without_cuts() {
        // A clean clone carries only the synthesized engine/idle: the ring
        // cannot form, and the legacy single pitched loop must come up
        // instead.
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine
            .bass_mut()
            .unwrap()
            .set_key_filter(Some(Box::new(|key: &str| {
                !(is_engine_band_key(key) && key != "engine/idle")
            })));
        r.engine.engine_start();
        assert!(r.engine.engine_running());
        let bass = r.engine.bass().unwrap();
        assert!(bass.engine_bands().is_empty());
        assert!(bass.engine_stream_handle().is_some());
        assert!(bass.engine_base_freq() > 0.0);
        for rpm in [600.0, 1500.0, 2200.0] {
            r.engine.set_engine_rpm_with(rpm, 0.5);
        }
        r.engine.engine_stop();
    }

    #[test]
    fn test_silent_engine_start_skips_the_ignition_crank() {
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.bass_mut().unwrap().record_requested_keys(true);
        r.engine.engine_start_with(false); // resume / menu-return path
        assert!(r.engine.engine_running());
        let bass = r.engine.bass().unwrap();
        assert!(!bass.requested_keys().iter().any(|k| k == "engine/start")); // the crank must not replay
                                                                             // The engine voice still comes up: the ring when the cuts are
                                                                             // installed, the legacy loop otherwise.
        assert!(!bass.engine_bands().is_empty() || bass.engine_stream_handle().is_some());
        r.engine.engine_stop();
    }

    #[test]
    fn test_deliberate_engine_start_plays_crank_and_arms_crossfade() {
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.bass_mut().unwrap().record_requested_keys(true);
        r.engine.engine_start(); // deliberate ignition
        let bass = r.engine.bass().unwrap();
        assert!(bass.requested_keys().iter().any(|k| k == "engine/start"));
        // A crank fade-out, the loop fade-in, and the post-handoff load
        // settle are scheduled; the loop starts silent so the ignition is not
        // drowned out, and its load is boosted to full so it meets the crank
        // tail without a dip.
        assert_eq!(bass.fade_count(), 3);
        assert_eq!(bass.engine_intro_gain(), 0.0);
        assert_eq!(bass.engine_intro_load(), 1.0);
        r.engine.engine_stop();
    }

    #[test]
    fn test_engine_start_crossfade_ramps_the_loop_up_over_time() {
        let Some(mut r) = bass_rig() else { return };
        r.engine.engine_start();
        assert_eq!(r.engine.bass().unwrap().engine_intro_gain(), 0.0);
        // Advance well past the clip length plus the crossfade window.
        for _ in 0..400 {
            r.engine.update(0.05);
        }
        let bass = r.engine.bass().unwrap();
        assert_eq!(bass.engine_intro_gain(), 1.0);
        assert_eq!(bass.fade_count(), 0); // finished fades are dropped
        r.engine.engine_stop();
    }

    #[test]
    fn test_engine_starting_true_during_crank_then_clears() {
        let Some(mut r) = bass_rig() else { return };
        r.engine.engine_start(); // deliberate ignition
        assert!(r.engine.engine_starting()); // loop has not taken over yet
                                             // Advance past the clip length plus the crossfade window.
        for _ in 0..400 {
            r.engine.update(0.05);
        }
        assert!(!r.engine.engine_starting()); // loop has taken over
        assert!(r.engine.engine_running());
        r.engine.engine_stop();
    }

    #[test]
    fn test_silent_engine_start_is_never_marked_starting() {
        let Some(mut r) = bass_rig() else { return };
        r.engine.engine_start_with(false); // resume / menu-return path
        assert!(!r.engine.engine_starting()); // no crank, nothing to gate on
        r.engine.engine_stop();
    }

    #[test]
    fn test_engine_stop_clears_engine_starting() {
        let Some(mut r) = bass_rig() else { return };
        r.engine.engine_start();
        assert!(r.engine.engine_starting());
        r.engine.engine_stop(); // stopping mid-crank must leave clean state
        assert!(!r.engine.engine_starting());
    }

    #[test]
    fn test_null_backend_is_never_engine_starting() {
        assert!(!NullBackend::new().engine_starting());
    }

    #[test]
    fn test_engine_stop_clears_pending_fades() {
        let Some(mut r) = bass_rig() else { return };
        r.engine.engine_start();
        assert!(r.engine.bass().unwrap().fade_count() > 0);
        r.engine.engine_stop();
        let bass = r.engine.bass().unwrap();
        assert_eq!(bass.fade_count(), 0);
        assert_eq!(bass.engine_intro_gain(), 1.0);
    }

    #[test]
    fn test_road_noise_loop_tracks_speed() {
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.set_road_noise(30.0);
        let entry = r.engine.backend().loop_entry(CH_ROAD).expect("road loop");
        assert_eq!(entry.0, "vehicle/road");
        assert_eq!(entry.1, 1.0);
        r.engine.set_road_noise(0.0);
        assert!(r.engine.backend().loop_entry(CH_ROAD).is_none());
    }

    #[test]
    fn test_new_context_loops_enter_mixer_at_full_gain() {
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.set_wind(2.0);
        let entry = r.engine.backend().loop_entry(CH_WEATHER_B).unwrap();
        assert_eq!(entry.0, "weather/wind");
        assert_eq!(entry.1, 1.0);
        r.engine.set_ambient(Some("poi/facility_gate"));
        let entry = r.engine.backend().loop_entry(CH_AMBIENT).unwrap();
        assert_eq!(entry.0, "poi/facility_gate");
        assert_eq!(entry.1, 1.0);
        assert_eq!(ENGINE_LOOP_GAIN, 1.0);
    }

    #[test]
    fn test_horn_uses_reserved_loop_slot() {
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.horn_start();
        assert_eq!(
            r.engine.backend().loop_entry(CH_HORN).unwrap().0,
            "vehicle/horn"
        );
        r.engine.horn_stop();
        assert!(r.engine.backend().loop_entry(CH_HORN).is_none());
    }

    #[test]
    fn test_bass_horn_sustains_then_rings_out_on_release() {
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.horn_start();
        r.engine.horn_start(); // key autorepeat must not stack a second horn
        let bass = r.engine.bass().unwrap();
        assert_eq!(bass.sustain_channels(), vec![CH_HORN]);
        let handle = bass.loop_stream_handle(CH_HORN).unwrap();
        r.engine.horn_stop();
        // The loop is released and the channel handed off, but the stream
        // keeps playing its release tail (retained so it is not freed
        // mid-tail).
        let bass = r.engine.bass().unwrap();
        assert!(bass.sustain_channels().is_empty());
        assert!(bass.loop_entry(CH_HORN).is_none());
        assert!(bass.is_retained(handle));
    }

    #[test]
    fn test_bass_horn_press_during_release_tail_does_not_stack() {
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.horn_start();
        r.engine.horn_stop(); // tail is now ringing out on the channel
        let bass = r.engine.bass().unwrap();
        let tail = bass.releasing_entry(CH_HORN).expect("a ringing tail");
        assert!(super::audio_support_is_playing(tail.1));
        let retained = bass.retained_handles().len();
        r.engine.horn_start(); // pressed again mid-tail: must be ignored, not stacked
        let bass = r.engine.bass().unwrap();
        assert!(bass.sustain_channels().is_empty()); // no new held loop
        assert!(bass.loop_entry(CH_HORN).is_none());
        assert_eq!(bass.releasing_entry(CH_HORN), Some(tail)); // same tail, no new stream
        assert_eq!(bass.retained_handles().len(), retained); // nothing new retained
    }

    #[test]
    fn test_bass_radio_failed_connect_reports_on_the_next_call() {
        // A connect that never produces audio fails on the NEXT call for the
        // same URL -- when the driving state's reconnect loop retries -- and
        // a later tune back starts a fresh attempt.
        let Some(mut r) = bass_rig() else { return };
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let url = format!(
            "http://127.0.0.1:{}/dead",
            listener.local_addr().unwrap().port()
        );
        drop(listener); // nothing answers on that port now
        r.engine.play_radio_stream_with(&url, 100).unwrap(); // silence: the caller's retry cue
        let bass = r.engine.bass_mut().unwrap();
        bass.join_radio_workers(Duration::from_secs(10));
        assert_eq!(bass.radio_failed_url().as_deref(), Some(url.as_str()));
        assert!(bass.radio_connecting_url().is_none());
        let err = r.engine.play_radio_stream_with(&url, 100).unwrap_err();
        assert_eq!(err.message, "radio stream unavailable");
        // The latch is spent: the third call is a fresh connect.
        r.engine.play_radio_stream_with(&url, 100).unwrap();
        let bass = r.engine.bass_mut().unwrap();
        bass.join_radio_workers(Duration::from_secs(10));
        assert_eq!(bass.radio_failed_url().as_deref(), Some(url.as_str()));
    }

    #[test]
    fn test_play_music_file_reads_the_file_and_refuses_what_it_cannot() {
        let Some(mut r) = bass_rig() else { return };
        let tmp = tempfile::tempdir().unwrap();
        let track = tmp.path().join("song.wav");
        std::fs::write(&track, sine_wav(1.0, 2)).unwrap();
        let path = track.to_str().unwrap().to_string();
        r.engine.play_music_file_with(&path, 50).unwrap();
        let bass = r.engine.bass().unwrap();
        assert_eq!(bass.music_track(), Some(format!("file:{path}").as_str()));
        assert!(wait_for(Duration::from_secs(3), || bass.music_playing()));
        let missing = tmp.path().join("missing.wav").to_str().unwrap().to_string();
        let err = r.engine.play_music_file(&missing).unwrap_err();
        assert_eq!(err.message, format!("could not read {missing}"));
        let garbage = tmp.path().join("garbage.wav");
        std::fs::write(&garbage, b"not audio at all").unwrap();
        let garbage = garbage.to_str().unwrap().to_string();
        let err = r.engine.play_music_file(&garbage).unwrap_err();
        assert_eq!(err.message, format!("could not decode {garbage}"));
        // A refused file left the channel empty (the previous track was
        // faded out before the attempt, as in the Python backend).
        assert!(r.engine.bass().unwrap().music_track().is_none());
    }

    /// The `(key, volume)` plays a recording backend saw.
    type Played = Rc<RefCell<Vec<(String, f64)>>>;

    /// A recording backend: the facade over it, its plays recorded, and a
    /// fake asset universe (the Python `_bank_facade`).
    struct RecordingBackend {
        buses: Buses,
        played: Played,
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
        fn as_any(&self) -> &dyn std::any::Any {
            self
        }
        fn as_any_mut(&mut self) -> &mut dyn std::any::Any {
            self
        }
        fn play(&mut self, key: &str, volume: f64, _pan: f64) {
            self.played.borrow_mut().push((key.to_string(), volume));
        }
    }

    fn bank_facade(present: &[&str]) -> (AudioEngine, Played) {
        let played = Rc::new(RefCell::new(Vec::new()));
        let mut a = AudioEngine::with_backend(Box::new(RecordingBackend {
            buses: Buses::new(),
            played: Rc::clone(&played),
        }));
        let present: Vec<String> = present.iter().map(|k| k.to_string()).collect();
        a.set_asset_probe(Some(Box::new(move |key: &str| {
            present.iter().any(|p| p == key)
        })));
        (a, played)
    }

    #[test]
    fn test_play_bank_cycles_every_cut_without_immediate_repeats() {
        let cuts = ["vehicle/hit_01", "vehicle/hit_02", "vehicle/hit_03"];
        let (mut a, played) = bank_facade(&cuts);
        for _ in 0..30 {
            a.play_bank("vehicle/hit", "vehicle/fallback");
        }
        let played = played.borrow();
        let keys: Vec<&str> = played.iter().map(|(k, _v)| k.as_str()).collect();
        let mut seen: Vec<&str> = keys.clone();
        seen.sort_unstable();
        seen.dedup();
        assert_eq!(seen, cuts);
        // Shuffled full cycles: every block of three is a permutation of the
        // bank, and no cut ever lands twice in a row across cycle seams.
        for block in keys.chunks(3) {
            let mut block: Vec<&str> = block.to_vec();
            block.sort_unstable();
            assert_eq!(block, cuts);
        }
        assert!(keys.windows(2).all(|w| w[0] != w[1]));
        // The per-trigger level jitter stays inside its band.
        assert!(played.iter().all(|(_k, vol)| (0.85..=1.17).contains(vol)));
    }

    #[test]
    fn test_play_bank_falls_back_to_the_classic_cue() {
        let (mut a, played) = bank_facade(&[]);
        a.play_bank_with("vehicle/hit", "vehicle/fallback", 0.6, 0.0);
        assert_eq!(
            *played.borrow(),
            vec![("vehicle/fallback".to_string(), 0.6)] // exact volume: no jitter on fallback
        );
    }

    #[test]
    fn test_has_asset_caches_the_lookup() {
        let (mut a, _played) = bank_facade(&["vehicle/ebrake"]);
        assert!(a.has_asset("vehicle/ebrake"));
        assert!(!a.has_asset("vehicle/not_there"));
        a.set_asset_probe(Some(Box::new(|_key: &str| false)));
        assert!(a.has_asset("vehicle/ebrake")); // cached, not re-probed
    }

    #[test]
    fn test_bass_one_shots_survive_garbage_collection() {
        // Dropping a `Stream` frees the BASS handle; the backend must hold it
        // until playback ends, or every one-shot (menu sounds, horn, warnings)
        // is cut off instantly.
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.play("ui/menu_move");
        let bass = r.engine.bass().unwrap();
        let retained = bass.retained_handles();
        assert!(!retained.is_empty());
        let handle = *retained.last().unwrap();
        assert!(super::audio_support_is_playing(handle)); // the one-shot really started on the device
    }

    #[test]
    fn test_bass_fading_loops_stay_alive_during_fade() {
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.set_weather_with(Some("weather/rain_light"), 0.8);
        assert!(!r.engine.bass().unwrap().loop_channels().is_empty());
        r.engine.set_weather(None); // 1200 ms fade-out
        let bass = r.engine.bass().unwrap();
        assert!(bass.loop_channels().is_empty());
        let retained = bass.retained_handles();
        assert!(!retained.is_empty());
        assert!(super::audio_support_is_playing(*retained.last().unwrap())); // still fading, not cut off
    }

    #[test]
    fn test_bass_headless_uses_no_sound_device() {
        // The rig sets SDL_AUDIODRIVER=dummy, which must route BASS to the
        // "no sound" device so CI runs the full pipeline without hardware.
        let Some(r) = bass_rig() else { return };
        assert!(r.engine.enabled());
        assert_eq!(
            r.engine.bass().unwrap().output_device(),
            BASS_NO_SOUND_DEVICE as u32
        );
    }

    #[test]
    fn test_bass_road_noise_frequency_changes_with_speed() {
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.set_road_noise(15.0);
        let (base, target) = r.engine.bass().unwrap().road_noise_frequency().unwrap();
        assert!((target - base * 0.85).abs() < 1e-6);
    }

    #[test]
    fn test_the_classic_jake_voice_covers_every_rpm_band() {
        // One voice per setting, whatever the rpm (owner, 2026-08-17: "it is
        // playing both").
        let mut r = rig();
        let bands: Vec<String> = [1200, 1400, 1600, 1800, 2000, 2200]
            .iter()
            .map(|b| format!("engine/jake_{b}"))
            .collect();
        r.engine.set_jake_voice(true);
        let classic: std::collections::BTreeSet<String> =
            bands.iter().map(|k| r.engine.voice_key(k)).collect();
        assert_eq!(
            classic,
            [JAKE_CLASSIC_KEY.to_string()].into_iter().collect()
        );

        r.engine.set_jake_voice(false);
        let recorded: std::collections::BTreeSet<String> =
            bands.iter().map(|k| r.engine.voice_key(k)).collect();
        // Real must collapse to the one recording too; the other bands are
        // synths.
        assert_eq!(
            recorded,
            [JAKE_RECORDED_KEY.to_string()].into_iter().collect()
        );
        assert!(!recorded.contains(JAKE_CLASSIC_KEY));
    }

    #[test]
    fn test_the_jake_voice_switch_applies_on_every_band_not_just_1600() {
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.set_jake_voice(false);
        // Growling on a band that is NOT 1600 -- the case the guard missed.
        r.engine
            .start_loop_with(CH_JAKE, "engine/jake_1400", 0.5, 300);
        assert_eq!(
            r.engine.backend().loop_entry(CH_JAKE).unwrap().0,
            JAKE_RECORDED_KEY
        );

        r.engine.set_jake_voice(true); // classic, live, mid-growl on 1400
        let entry = r.engine.backend().loop_entry(CH_JAKE).unwrap();
        assert_eq!(
            entry.0, JAKE_CLASSIC_KEY,
            "the switch did nothing off the 1600 band"
        );
        assert_eq!(entry.1, 0.5); // level carries across

        r.engine.set_jake_voice(false); // back to real, live
        assert!(r
            .engine
            .backend()
            .loop_entry(CH_JAKE)
            .unwrap()
            .0
            .starts_with(JAKE_BAND_PREFIX));
        r.engine.stop_loop(CH_JAKE);
    }

    #[test]
    fn test_the_classic_jake_is_not_restarted_by_every_rpm_band() {
        // On classic every band maps to one synth cut, so a caller caching
        // the BAND key saw each rpm crossing as a new sound and restarted the
        // same file over itself. `voice_key` exists so the drive can cache
        // what will actually sound.
        let mut r = rig();
        let bands: Vec<String> = [1200, 1400, 1600, 1800, 2000, 2200]
            .iter()
            .map(|b| format!("engine/jake_{b}"))
            .collect();
        r.engine.set_jake_voice(true);
        let distinct: std::collections::BTreeSet<String> =
            bands.iter().map(|b| r.engine.voice_key(b)).collect();
        assert_eq!(
            distinct.len(),
            1,
            "the classic voice should resolve every band to one cut"
        );
        r.engine.set_jake_voice(false);
        let distinct: std::collections::BTreeSet<String> =
            bands.iter().map(|b| r.engine.voice_key(b)).collect();
        assert_eq!(
            distinct.len(),
            1,
            "real must resolve to one voice too -- there is only one recording"
        );
    }

    #[test]
    fn test_one_jake_voice_sounds_whatever_the_rpm_in_both_directions() {
        let mut r = rig();
        let bands: Vec<String> = [1200, 1400, 1600, 1800, 2000, 2200]
            .iter()
            .map(|b| format!("engine/jake_{b}"))
            .collect();
        r.engine.set_jake_voice(false);
        let keys: std::collections::BTreeSet<String> =
            bands.iter().map(|b| r.engine.voice_key(b)).collect();
        assert_eq!(keys, [JAKE_RECORDED_KEY.to_string()].into_iter().collect());

        r.engine.set_jake_voice(true);
        let keys: std::collections::BTreeSet<String> =
            bands.iter().map(|b| r.engine.voice_key(b)).collect();
        assert_eq!(keys, [JAKE_CLASSIC_KEY.to_string()].into_iter().collect());

        // The Learn game sounds entry demos the classic cut by name, so asking
        // for it explicitly must never be re-voiced into the other one.
        for classic in [false, true] {
            r.engine.set_jake_voice(classic);
            assert_eq!(r.engine.voice_key(JAKE_CLASSIC_KEY), JAKE_CLASSIC_KEY);
        }
    }

    #[test]
    fn test_held_alert_lapses_on_its_own_and_cues_latch() {
        // The dead man's switches (ALERT_HOLD_TIMEOUT_S / CUE_HOLD_TIMEOUT_S):
        // a tone whose owner stops re-asserting it goes quiet on its own.
        let Some(mut r) = bass_rig_with_recordings() else {
            return;
        };
        r.engine.hold_alert("vehicle/bar_solid");
        assert_eq!(
            r.engine.backend().loop_entry(CH_ALERT).unwrap().0,
            "vehicle/bar_solid"
        );
        r.engine.update(ALERT_HOLD_TIMEOUT_S / 2.0);
        assert!(r.engine.backend().loop_entry(CH_ALERT).is_some());
        r.engine.update(ALERT_HOLD_TIMEOUT_S); // the owner went silent
        assert!(r.engine.backend().loop_entry(CH_ALERT).is_none());

        r.engine.hold_cue("tick");
        assert!(r.engine.cue_held("tick"));
        r.engine.update(CUE_HOLD_TIMEOUT_S + 0.01);
        assert!(!r.engine.cue_held("tick"));
        r.engine.hold_cue("tick");
        r.engine.release_cue("tick");
        assert!(!r.engine.cue_held("tick"));
    }
}

/// `sound_lib.Channel.is_playing` for a handle, for the tests above.
fn audio_support_is_playing(handle: u32) -> bool {
    bass_sys::safe::channel_is_active(handle) == bass_sys::BASS_ACTIVE_PLAYING
}
