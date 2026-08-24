//! Smoke tests against the real vendored BASS library on the "no sound"
//! device. Every test skips (passes vacuously, with a note) when the library
//! is not loadable, so a Linux or macOS checkout without a vendored build
//! still runs the suite.
//!
//! BASS has one device per process and `cargo test` runs tests on parallel
//! threads, so every test takes `BASS_LOCK` and shares one `init`.

use std::sync::mpsc;
use std::sync::{Mutex, MutexGuard};
use std::time::{Duration, Instant};

use bass_sys::safe::*;
use bass_sys::*;

static BASS_LOCK: Mutex<()> = Mutex::new(());

/// Serialise the tests and make sure the no-sound device is up. `None` when
/// BASS is not loadable on this machine.
fn bass() -> Option<MutexGuard<'static, ()>> {
    if !native_available() {
        eprintln!("bass-sys: library not loadable here; skipping");
        return None;
    }
    let guard = BASS_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    match init(BASS_NO_SOUND_DEVICE, 44100, 0) {
        Ok(()) => {}
        Err(e) if e.is(BASS_ERROR_ALREADY) => {}
        Err(e) => panic!("BASS_Init(no sound) failed: {e}"),
    }
    Some(guard)
}

/// A 16-bit mono PCM WAV of `seconds` of a 440 Hz sine at 44.1 kHz.
fn sine_wav(seconds: f64) -> Vec<u8> {
    let rate: u32 = 44100;
    let frames = (seconds * rate as f64).round() as u32;
    let data_len = frames * 2;
    let mut out = Vec::with_capacity(44 + data_len as usize);
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_len).to_le_bytes());
    out.extend_from_slice(b"WAVE");
    out.extend_from_slice(b"fmt ");
    out.extend_from_slice(&16u32.to_le_bytes()); // PCM fmt chunk size
    out.extend_from_slice(&1u16.to_le_bytes()); // format = PCM
    out.extend_from_slice(&1u16.to_le_bytes()); // channels
    out.extend_from_slice(&rate.to_le_bytes());
    out.extend_from_slice(&(rate * 2).to_le_bytes()); // byte rate
    out.extend_from_slice(&2u16.to_le_bytes()); // block align
    out.extend_from_slice(&16u16.to_le_bytes()); // bits per sample
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_len.to_le_bytes());
    for i in 0..frames {
        let t = i as f64 / rate as f64;
        let s = (t * 440.0 * std::f64::consts::TAU).sin() * 0.5 * i16::MAX as f64;
        out.extend_from_slice(&(s as i16).to_le_bytes());
    }
    out
}

/// Poll `cond` every 10 ms for up to `timeout`.
fn wait_for(timeout: Duration, mut cond: impl FnMut() -> bool) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if cond() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    cond()
}

#[test]
fn init_no_sound_device_and_read_version() {
    let Some(_g) = bass() else { return };
    let v = version().expect("BASS_GetVersion");
    assert_eq!(v >> 16, BASSVERSION, "not a BASS 2.4 build: {v:#x}");
    let text = version_string().unwrap();
    assert!(text.starts_with("2.4."), "{text}");
    assert_eq!(current_device().unwrap(), 0, "the no-sound device is 0");
    let info = device_info(0).unwrap();
    assert!(info.initialised(), "{info:?}");
    // NET timeouts are what the game configures first thing.
    set_config(BASS_CONFIG_NET_TIMEOUT, 30000).unwrap();
    set_config(BASS_CONFIG_NET_READTIMEOUT, 30000).unwrap();
    assert_eq!(get_config(BASS_CONFIG_NET_TIMEOUT).unwrap(), 30000);
}

#[test]
fn memory_wav_stream_length_and_conversions() {
    let Some(_g) = bass() else { return };
    let wav = sine_wav(0.5);
    let stream = stream_create_mem(&wav, 0).expect("stream from memory WAV");
    let h = stream.handle();

    // 16-bit mono: two bytes per frame, and BASS decodes 16-bit WAV as-is.
    let frames = 22050u64;
    assert_eq!(channel_length_bytes(h).unwrap(), frames * 2);
    let secs = bytes_to_seconds(h, frames * 2).unwrap();
    assert!((secs - 0.5).abs() < 1e-6, "{secs}");
    assert_eq!(seconds_to_bytes(h, 0.25).unwrap(), frames);
    assert!((channel_length_seconds(h).unwrap() - 0.5).abs() < 1e-6);

    let info = channel_info(h).unwrap();
    assert_eq!(info.freq, 44100);
    assert_eq!(info.chans, 1);
    assert_eq!(info.ctype & BASS_CTYPE_STREAM_WAV, BASS_CTYPE_STREAM_WAV);
    assert_eq!(channel_frequency(h).unwrap(), 44100);
    assert_eq!(channel_device(h).unwrap(), 0);

    // Not playing yet.
    assert_eq!(channel_is_active(h), BASS_ACTIVE_STOPPED);
    assert_eq!(channel_position_bytes(h).unwrap(), 0);
    channel_set_position_bytes(h, frames).unwrap();
    assert_eq!(channel_position_bytes(h).unwrap(), frames);

    // Explicit free: the handle is gone afterwards.
    stream.free().unwrap();
    assert_eq!(
        channel_length_bytes(h).unwrap_err().code,
        BASS_ERROR_HANDLE,
        "freed handle must be rejected"
    );
}

#[test]
fn garbage_is_refused_with_a_named_error() {
    let Some(_g) = bass() else { return };
    let err = stream_create_mem(b"this is not audio", 0).unwrap_err();
    assert_eq!(err.code, BASS_ERROR_FILEFORM, "{err}");
    assert_eq!(err.name(), "BASS_ERROR_FILEFORM");
}

#[test]
fn loop_flag_round_trips_through_channel_flags() {
    let Some(_g) = bass() else { return };
    let wav = sine_wav(0.1);
    let stream = stream_create_mem(&wav, 0).unwrap();
    let h = stream.handle();
    assert!(!is_looping(h).unwrap());
    set_looping(h, true).unwrap();
    assert!(is_looping(h).unwrap());
    assert_eq!(
        channel_flags(h, 0, 0).unwrap() & BASS_SAMPLE_LOOP,
        BASS_SAMPLE_LOOP
    );
    set_looping(h, false).unwrap();
    assert!(!is_looping(h).unwrap());
    // The loop flag can also be given at creation.
    let looped = stream_create_mem(&wav, BASS_SAMPLE_LOOP).unwrap();
    assert!(is_looping(looped.handle()).unwrap());
}

#[test]
fn attributes_set_get_and_slide() {
    let Some(_g) = bass() else { return };
    let wav = sine_wav(2.0);
    let stream = stream_create_mem(&wav, 0).unwrap();
    let h = stream.handle();

    channel_set_attribute(h, BASS_ATTRIB_VOL, 0.5).unwrap();
    assert!((channel_get_attribute(h, BASS_ATTRIB_VOL).unwrap() - 0.5).abs() < 1e-6);
    channel_set_attribute(h, BASS_ATTRIB_PAN, -0.25).unwrap();
    assert!((channel_get_attribute(h, BASS_ATTRIB_PAN).unwrap() + 0.25).abs() < 1e-6);
    channel_set_attribute(h, BASS_ATTRIB_FREQ, 44100.0 * 1.5).unwrap();
    assert!((channel_get_attribute(h, BASS_ATTRIB_FREQ).unwrap() - 66150.0).abs() < 1.0);

    // Slides run on BASS's update thread even on the no-sound device.
    channel_play(h, false).unwrap();
    assert_eq!(channel_is_active(h), BASS_ACTIVE_PLAYING);
    channel_slide_attribute(h, BASS_ATTRIB_VOL, 0.1, 100).unwrap();
    assert!(channel_is_sliding(h, BASS_ATTRIB_VOL));
    assert!(
        wait_for(Duration::from_secs(3), || !channel_is_sliding(
            h,
            BASS_ATTRIB_VOL
        )),
        "slide never finished"
    );
    assert!((channel_get_attribute(h, BASS_ATTRIB_VOL).unwrap() - 0.1).abs() < 1e-3);

    channel_pause(h).unwrap();
    assert_eq!(channel_is_active(h), BASS_ACTIVE_PAUSED);
    channel_play(h, false).unwrap();
    channel_stop(h).unwrap();
    assert_eq!(channel_is_active(h), BASS_ACTIVE_STOPPED);
}

#[test]
fn mixtime_pos_sync_fires_and_can_seek_the_channel() {
    let Some(_g) = bass() else { return };
    let wav = sine_wav(1.0);
    let stream = stream_create_mem(&wav, 0).unwrap();
    let h = stream.handle();

    // The SustainLoop shape: a POS|MIXTIME sync at loop_end that seeks back
    // to loop_start, on the mixer thread. Report each firing to the test.
    let loop_start = seconds_to_bytes(h, 0.05).unwrap();
    let loop_end = seconds_to_bytes(h, 0.20).unwrap();
    let (tx, rx) = mpsc::channel::<(u32, u64)>();
    let sync = set_sync(
        h,
        BASS_SYNC_POS | BASS_SYNC_MIXTIME,
        loop_end,
        Box::new(move |_sync, channel, _data| {
            let _ = channel_set_position_bytes(channel, loop_start);
            let _ = tx.send((channel, channel_position_bytes(channel).unwrap_or(u64::MAX)));
        }),
    )
    .expect("BASS_ChannelSetSync");
    assert_ne!(sync.handle(), 0);
    assert_eq!(sync.channel(), h);

    channel_play(h, false).unwrap();
    // Force rendering on this thread so the first firing does not depend on
    // the update thread's timing; the callback then runs before this returns.
    channel_update(h, 500).unwrap();
    let first = rx
        .recv_timeout(Duration::from_secs(3))
        .expect("sync never fired");
    assert_eq!(first.0, h);
    assert!(
        first.1 <= loop_end,
        "seek inside the callback did not land: {first:?}"
    );

    // Left alone it keeps looping: a second firing arrives on the update
    // thread in real time.
    rx.recv_timeout(Duration::from_secs(3))
        .expect("loop did not repeat");

    // Remove the loop: playback runs past loop_end into the tail and no
    // further firings arrive. The channel is still playing.
    sync.remove().expect("BASS_ChannelRemoveSync");
    while rx.try_recv().is_ok() {}
    assert!(wait_for(Duration::from_secs(3), || {
        channel_position_bytes(h)
            .map(|p| p > loop_end)
            .unwrap_or(false)
            || channel_is_active(h) == BASS_ACTIVE_STOPPED
    }));
    assert!(rx.recv_timeout(Duration::from_millis(300)).is_err());
    channel_stop(h).unwrap();
}

#[test]
fn dropping_the_sync_guard_removes_it() {
    let Some(_g) = bass() else { return };
    let wav = sine_wav(0.5);
    let stream = stream_create_mem(&wav, 0).unwrap();
    let h = stream.handle();
    let (tx, rx) = mpsc::channel::<()>();
    {
        let _sync = set_sync(
            h,
            BASS_SYNC_POS | BASS_SYNC_MIXTIME,
            seconds_to_bytes(h, 0.05).unwrap(),
            Box::new(move |_, _, _| {
                let _ = tx.send(());
            }),
        )
        .unwrap();
        // Guard dropped here, before anything was rendered.
    }
    channel_play(h, false).unwrap();
    channel_update(h, 300).unwrap();
    assert!(
        rx.recv_timeout(Duration::from_millis(300)).is_err(),
        "a removed sync fired"
    );
    // A sync with a bad handle is refused and the closure is dropped cleanly.
    let err = set_sync(0xDEAD_BEEF, BASS_SYNC_END, 0, Box::new(|_, _, _| {})).unwrap_err();
    assert_eq!(err.code, BASS_ERROR_HANDLE);
}

#[test]
fn autofree_stream_goes_away_when_it_ends() {
    let Some(_g) = bass() else { return };
    let wav = sine_wav(0.1);
    let stream = stream_create_mem(&wav, BASS_STREAM_AUTOFREE).unwrap();
    let h = stream.handle();
    channel_play(h, false).unwrap();
    assert!(
        wait_for(Duration::from_secs(3), || channel_is_active(h)
            == BASS_ACTIVE_STOPPED),
        "a 0.1 s one-shot never ended on the no-sound device"
    );
    // BASS frees it on its update thread a moment after it stops; our Drop
    // then sees BASS_ERROR_HANDLE and shrugs.
    assert!(
        wait_for(Duration::from_secs(3), || {
            channel_length_bytes(h).err().map(|e| e.code) == Some(BASS_ERROR_HANDLE)
        }),
        "an ended autofree stream was not freed"
    );
    drop(stream);
}

#[test]
fn plugins_load_from_the_library_directory() {
    let Some(_g) = bass() else { return };
    let api = api().unwrap();
    let dir = api.library_dir().expect("library has a directory");
    let loaded = load_plugins_from(dir);
    let names: Vec<&str> = loaded.iter().map(|(n, _)| n.as_str()).collect();
    eprintln!("plugins in {}: {loaded:?}", dir.display());
    let opus = loaded.iter().find(|(n, _)| {
        n.eq_ignore_ascii_case("bassopus.dll")
            || n.eq_ignore_ascii_case("libbassopus.so")
            || n.eq_ignore_ascii_case("libbassopus.dylib")
    });
    match opus {
        Some((_, Ok(handle))) => {
            assert_ne!(*handle, 0);
            plugin_free(*handle).unwrap();
        }
        Some((name, Err(e))) => panic!("{name} refused: {e}"),
        None => eprintln!("bassopus not vendored for this platform ({names:?}); skipping"),
    }
    // Every other vendored add-on should have loaded too.
    for (name, result) in &loaded {
        assert!(result.is_ok(), "{name}: {result:?}");
    }
    plugin_free(0).unwrap();
    // A directory with nothing in it is an empty list, not an error.
    assert!(load_plugins_from(std::path::Path::new("does/not/exist")).is_empty());
}

#[test]
fn free_and_reinit_the_device() {
    let Some(_g) = bass() else { return };
    free().unwrap();
    // Nothing is initialised now, so a channel call fails with INIT.
    assert_eq!(
        stream_create_mem(&sine_wav(0.1), 0).unwrap_err().code,
        BASS_ERROR_INIT
    );
    init(BASS_NO_SOUND_DEVICE, 44100, 0).unwrap();
    assert_eq!(
        init(BASS_NO_SOUND_DEVICE, 44100, 0).unwrap_err().code,
        BASS_ERROR_ALREADY
    );
    assert_eq!(current_device().unwrap(), 0);
}

#[test]
fn url_stream_with_no_network_target_fails_softly() {
    let Some(_g) = bass() else { return };
    // An unroutable host: BASS must return an error, not hang or crash. Keep
    // the timeout short so the test does not.
    set_config(BASS_CONFIG_NET_TIMEOUT, 1500).unwrap();
    let err = stream_create_url("http://127.0.0.1:9/nothing", BASS_STREAM_AUTOFREE).unwrap_err();
    eprintln!("unreachable URL -> {err}");
    assert_ne!(err.code, BASS_OK);
    set_config(BASS_CONFIG_NET_TIMEOUT, 30000).unwrap();
    // And the tag readers answer None for a bad handle rather than exploding.
    assert_eq!(tags_meta(0xDEAD_BEEF), None);
    assert_eq!(tags_strings(0xDEAD_BEEF, BASS_TAG_ICY), None);
}
