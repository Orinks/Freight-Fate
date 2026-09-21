use super::*;

#[test]
fn test_blinker_updates_pan_and_volume_between_repeats_without_restarting() {
    let Some(mut r) = bass_rig_with_recordings() else {
        return;
    };
    let key = "vehicle/turn_signal";
    r.engine.play_if_idle(key, 0.8, -0.6);
    let handle = r.engine.bass().unwrap().exclusive_cue_handle(key).unwrap();
    let before = safe::channel_get_attribute(handle, bass_sys::BASS_ATTRIB_VOL).unwrap();
    r.engine.update_cue(key, 0.4, 0.7);
    assert_eq!(
        r.engine.bass().unwrap().exclusive_cue_handle(key),
        Some(handle)
    );
    assert!(
        (safe::channel_get_attribute(handle, bass_sys::BASS_ATTRIB_PAN).unwrap() - 0.7).abs()
            < 1e-6
    );
    assert!(
        (safe::channel_get_attribute(handle, bass_sys::BASS_ATTRIB_VOL).unwrap() - before / 2.0)
            .abs()
            < 1e-6
    );
}

#[test]
fn test_blinker_stops_on_release_menu_and_owner_timeout() {
    let Some(mut r) = bass_rig_with_recordings() else {
        return;
    };
    let key = "vehicle/turn_signal";
    for stop in 0..3 {
        r.engine.play_if_idle(key, 0.8, -0.6);
        let handle = r.engine.bass().unwrap().exclusive_cue_handle(key).unwrap();
        assert_eq!(
            safe::channel_is_active(handle),
            bass_sys::BASS_ACTIVE_PLAYING
        );
        match stop {
            0 => r.engine.release_cue(key),
            1 => r.engine.stop_world(),
            _ => r.engine.update(CUE_HOLD_TIMEOUT_S + 0.01),
        }
        assert_eq!(r.engine.bass().unwrap().exclusive_cue_handle(key), None);
        assert_ne!(
            safe::channel_is_active(handle),
            bass_sys::BASS_ACTIVE_PLAYING
        );
        assert!(!r.engine.cue_held(key));
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

#[test]
fn test_engine_pan_bands_and_legacy_inherit_and_preserve_engine_state() {
    let Some(mut r) = bass_rig_with_recordings() else {
        return;
    };
    for classic in [false, true] {
        r.engine.engine_stop_with(false);
        r.engine.set_engine_voice(classic);
        r.engine.set_engine_pan(-0.6);
        r.engine.engine_start_with(false);
        r.engine.update(1.0);
        r.engine.set_engine_rpm_with(1150.0, 0.7);
        let handles = |engine: &AudioEngine| {
            let bass = engine.bass().unwrap();
            if classic {
                assert!(bass.engine_bands().is_empty());
                vec![bass.engine_stream_handle().expect("legacy engine stream")]
            } else {
                let bands = bass.engine_bands();
                assert_eq!(bands.len(), ENGINE_BANDS.len());
                bands.iter().map(|band| band.handle).collect::<Vec<_>>()
            }
        };
        let original = handles(&r.engine);
        let volumes: Vec<_> = original
            .iter()
            .map(|h| safe::channel_get_attribute(*h, bass_sys::BASS_ATTRIB_VOL).unwrap())
            .collect();
        let bands = r.engine.bass().unwrap().engine_bands();
        let wobble = r.engine.bass().unwrap().engine_wobble();
        for (pan, expected) in [
            (-0.6, -0.6),
            (0.0, 0.0),
            (0.7, 0.7),
            (-2.0, -1.0),
            (2.0, 1.0),
        ] {
            // The first assertion also checks pan inherited at stream creation.
            if pan != -0.6 {
                r.engine.set_engine_pan(pan);
            }
            assert_eq!(handles(&r.engine), original, "pan must not restart streams");
            for (i, handle) in original.iter().enumerate() {
                assert!(
                    (safe::channel_get_attribute(*handle, bass_sys::BASS_ATTRIB_PAN).unwrap()
                        as f64
                        - expected)
                        .abs()
                        < 1e-6
                );
                assert_eq!(
                    safe::channel_get_attribute(*handle, bass_sys::BASS_ATTRIB_VOL).unwrap(),
                    volumes[i]
                );
            }
            let bass = r.engine.bass().unwrap();
            assert_eq!(bass.engine_wobble(), wobble);
            for (before, after) in bands.iter().zip(bass.engine_bands()) {
                assert_eq!(before.last_rate_target, after.last_rate_target);
                assert_eq!(before.last_volume, after.last_volume);
            }
        }
        r.engine.engine_stop_with(false);
        r.engine.engine_start_with(false);
        for handle in handles(&r.engine) {
            assert_eq!(
                safe::channel_get_attribute(handle, bass_sys::BASS_ATTRIB_PAN).unwrap(),
                1.0
            );
        }
    }
}

#[test]
fn test_blinker_repeat_waits_for_actual_playback_completion() {
    let Some(mut r) = bass_rig_with_recordings() else {
        return;
    };
    let key = "vehicle/turn_signal";
    r.engine.play_if_idle(key, 0.5, -0.6);
    let handle = r.engine.bass().unwrap().exclusive_cue_handle(key).unwrap();
    for _ in 0..20 {
        r.engine.play_if_idle(key, 0.5, 0.6);
        assert_eq!(
            r.engine.bass().unwrap().exclusive_cue_handle(key),
            Some(handle)
        );
        assert!(
            (safe::channel_get_attribute(handle, bass_sys::BASS_ATTRIB_PAN).unwrap() - 0.6).abs()
                < 1e-6
        );
    }
    // Real completion on BASS's silent device, not a guessed clip duration.
    assert!(wait_for(
        Duration::from_secs(5),
        || safe::channel_is_active(handle) == bass_sys::BASS_ACTIVE_STOPPED
    ));
    r.engine.play_if_idle(key, 0.5, 0.6);
    let next = r.engine.bass().unwrap().exclusive_cue_handle(key).unwrap();
    assert_eq!(safe::channel_is_active(next), bass_sys::BASS_ACTIVE_PLAYING);
    assert!(
        (safe::channel_get_attribute(next, bass_sys::BASS_ATTRIB_PAN).unwrap() - 0.6).abs() < 1e-6
    );
    r.engine.shutdown();
    assert_eq!(r.engine.bass().unwrap().exclusive_cue_handle(key), None);
}
