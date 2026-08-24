//! Port of the audio half of `tests/test_radio_now_playing.py`: what the
//! station says it is playing, read off the stream's ICY metadata. The
//! driving-state and status-screen tests of the Python file belong to the
//! states port.
//!
//! Wrapped in a module so `cargo test -p freight-fate audio` selects them.

mod audio_radio_now_playing {
    use std::time::Duration;

    use freight_fate::audio::{parse_icy_stream_title, Audio, AudioEngine, NullBackend};

    use crate::audio_support::{bass_rig, sine_wav, wait_for, IcyServer};

    #[test]
    fn test_icy_stream_title_parsing() {
        let cases: [(Option<&[u8]>, Option<&str>); 9] = [
            (
                Some(b"StreamTitle='Usher - U Remind Me';StreamUrl='';"),
                Some("Usher - U Remind Me"),
            ),
            (
                Some(b"StreamTitle='Darren Duff radio';"),
                Some("Darren Duff radio"),
            ),
            // UTF-8 from a modern Icecast mount.
            (
                Some("StreamTitle='Beyonc\u{e9} - Halo';".as_bytes()),
                Some("Beyonc\u{e9} - Halo"),
            ),
            // Latin-1 from an older Shoutcast one: not valid UTF-8, still a title.
            (
                Some(b"StreamTitle='Caf\xe9 del Mar';"),
                Some("Caf\u{e9} del Mar"),
            ),
            // Whitespace runs inside a title collapse; surrounding space goes.
            (
                Some(b"StreamTitle='  Artist   -   Title  ';"),
                Some("Artist - Title"),
            ),
            // An empty block between songs is "no information", not "".
            (Some(b"StreamTitle='';StreamUrl='';"), None),
            (Some(b"StreamUrl='http://x';"), None),
            (Some(b""), None),
            (None, None),
        ];
        for (raw, expected) in cases {
            assert_eq!(parse_icy_stream_title(raw).as_deref(), expected, "{raw:?}");
        }
    }

    #[test]
    fn test_the_audio_facade_answers_none_when_the_backend_cannot_know() {
        let engine = AudioEngine::with_backend(Box::new(NullBackend::new()));
        assert_eq!(engine.radio_now_playing(), None);
    }

    #[test]
    fn test_the_bass_backend_reads_the_title_off_the_stream() {
        // End to end against the real BASS ICY reader: a localhost station
        // interleaves `StreamTitle='...'` blocks, and the facade reports it.
        let Some(mut r) = bass_rig() else { return };
        let server = IcyServer::start(sine_wav(8.0, 1), Some("Usher - U Remind Me"));
        assert_eq!(r.engine.radio_now_playing(), None); // nothing streaming yet
        r.engine.play_radio_stream_with(&server.url, 100).unwrap();
        let bass = r.engine.bass_mut().unwrap();
        bass.join_radio_workers(Duration::from_secs(10));
        bass.collect_radio_stream();
        assert!(bass.music_track().is_some(), "the station did not open");
        let engine = &r.engine;
        assert!(
            wait_for(Duration::from_secs(5), || engine
                .radio_now_playing()
                .is_some()),
            "no title arrived"
        );
        assert_eq!(
            r.engine.radio_now_playing().as_deref(),
            Some("Usher - U Remind Me")
        );
        r.engine.stop_music_with(0);
        assert_eq!(r.engine.radio_now_playing(), None);
    }
}
