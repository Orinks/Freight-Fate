//! Port of the audio half of `tests/test_speech_ducking.py`: the duck
//! reaches the channels the doc names -- engine, weather, and the music slot
//! the radio rides -- and leaves UI, siren, and gameplay cues at full volume.
//! The `App`/`GameContext` halves (when the duck engages, the earcon window,
//! the setting) belong to the app-shell port.
//!
//! Wrapped in a module so `cargo test -p freight-fate audio` selects them.


mod audio_speech_ducking {
    use freight_fate::audio::{Audio, Category, SPEECH_DUCK_LEVEL};

    use crate::audio_support::rig;

    #[test]
    fn test_the_backends_scale_engine_weather_and_music_only() {
        let mut r = rig();
        let buses = *r.engine.buses();
        let engine = buses.category_volume(Category::Engine);
        let weather = buses.category_volume(Category::Weather);
        let ui = buses.category_volume(Category::Ui);
        let siren = buses.category_volume(Category::Siren);
        let sfx = buses.category_volume(Category::Sfx);
        let music = buses.music_level();

        r.engine.set_speech_duck(SPEECH_DUCK_LEVEL);
        let ducked = *r.engine.buses();
        assert_eq!(ducked.speech_duck, SPEECH_DUCK_LEVEL);
        assert!(
            (ducked.category_volume(Category::Engine) - engine * SPEECH_DUCK_LEVEL).abs() < 1e-9
        );
        assert!(
            (ducked.category_volume(Category::Weather) - weather * SPEECH_DUCK_LEVEL).abs() < 1e-9
        );
        assert!((ducked.music_level() - music * SPEECH_DUCK_LEVEL).abs() < 1e-9);
        assert_eq!(ducked.category_volume(Category::Ui), ui);
        assert_eq!(ducked.category_volume(Category::Siren), siren);
        assert_eq!(ducked.category_volume(Category::Sfx), sfx);

        r.engine.set_speech_duck(1.0);
        assert!((r.engine.buses().category_volume(Category::Engine) - engine).abs() < 1e-9);
    }

    #[test]
    fn test_the_duck_rides_on_top_of_the_volume_settings() {
        // The player's volume settings are never touched: the factor
        // multiplies whatever they set, and a settings change while ducked
        // keeps honoring it.
        let mut r = rig();
        r.engine.set_speech_duck(SPEECH_DUCK_LEVEL);
        r.engine
            .set_volumes(&freight_fate::audio::VolumeUpdate::default().engine(0.8));
        let buses = *r.engine.buses();
        assert_eq!(buses.engine, 0.8);
        assert!((buses.category_volume(Category::Engine) - 0.8 * SPEECH_DUCK_LEVEL).abs() < 1e-9);
        assert_eq!(r.engine.engine_volume(), 0.8);
    }
}
