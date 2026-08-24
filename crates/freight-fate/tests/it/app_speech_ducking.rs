//! Port of the `App`/`GameContext` half of `tests/test_speech_ducking.py`:
//! game audio steps back while the event voice speaks (R13, XAG 105).
//!
//! A warning must survive a loud cab -- engine, weather, and the radio --
//! without the voice itself getting louder. The duck engages the moment a
//! line reaches the event channel and restores on the pacer's own
//! projection of when the voice falls silent: no polling of the speech
//! backend, which cannot be asked. (The backend half -- which channels the
//! duck scales -- is `tests/audio_speech_ducking.rs`.)

use ff_core::settings::Settings;
use ff_core::speech_pacing::{monotonic_seconds, SpeechCategory};
use freight_fate::app::testing::{AudioLog, FakeClock, TestApp};
use freight_fate::app::SayEvent;
use freight_fate::audio::{EARCON_DUCK_S, SPEECH_DUCK_LEVEL};

fn rig(app: &mut TestApp) -> (AudioLog, FakeClock) {
    app.ctx.settings.sapi_events = true;
    // Opt in: the duck ships off by default (the engine is the instrument
    // panel), and these tests exercise what it does once a player enables
    // it.
    app.ctx.settings.duck_audio_for_speech = true;
    let audio = app.record_audio();
    let clock = app.fake_pacer_clock();
    (audio, clock)
}

#[test]
fn test_ducking_defaults_off() {
    // In an audio-first sim the engine is the instrument panel -- a blind
    // driver reads speed off it -- so ducking is opt-in for players who need
    // it, not a default that changes what everyone hears (owner, 2026-08-12).
    assert!(!Settings::default().duck_audio_for_speech);
}

#[test]
fn test_event_speech_ducks_the_mix_and_the_frame_after_silence_restores_it() {
    let mut app = TestApp::new();
    let (audio, clock) = rig(&mut app);

    app.ctx
        .say_event_with("Open weigh station ahead in two miles.", SayEvent::queued());
    assert_eq!(audio.borrow().ducks, vec![SPEECH_DUCK_LEVEL]);

    // Voice still speaking: the per-frame check leaves the duck alone.
    app.ctx.update_speech_duck();
    assert_eq!(audio.borrow().ducks, vec![SPEECH_DUCK_LEVEL]);

    // The projection says the line has finished: the mix comes back.
    clock.advance(30.0);
    app.ctx.update_speech_duck();
    assert_eq!(audio.borrow().ducks, vec![SPEECH_DUCK_LEVEL, 1.0]);

    // And it is restored exactly once, not every frame.
    app.ctx.update_speech_duck();
    assert_eq!(audio.borrow().ducks, vec![SPEECH_DUCK_LEVEL, 1.0]);
    app.shutdown();
}

#[test]
fn test_the_setting_turns_the_duck_off() {
    let mut app = TestApp::new();
    let (audio, _) = rig(&mut app);
    app.ctx.settings.duck_audio_for_speech = false;

    app.ctx
        .say_event_with("Open weigh station ahead in two miles.", SayEvent::queued());

    assert!(audio.borrow().ducks.is_empty());
    app.shutdown();
}

#[test]
fn test_a_suppressed_repeat_does_not_duck() {
    // A line the pacer never lets reach the voice must not touch the mix.
    let mut app = TestApp::new();
    let (audio, _) = rig(&mut app);
    let line = "You sideswiped a box truck in the right lane!";
    app.ctx.say_event(line);
    audio.borrow_mut().ducks.clear();

    app.ctx.say_event(line); // inside the repeat window

    assert!(audio.borrow().ducks.is_empty());
    app.shutdown();
}

#[test]
fn test_an_earcon_gets_the_room_the_words_it_replaces_would_have_had() {
    // Tester Shane, 2026-08-17: "some of the sounds when you put speech in
    // quiet mode have been significantly lowered." A spoken line ducks
    // engine, weather and radio while it talks; a silenced line returned
    // from say_event before reaching that duck, so its earcon played
    // against the full road bed.
    let mut app = TestApp::new();
    let audio = app.record_audio();
    app.ctx.settings.duck_audio_for_speech = true;
    app.ctx.settings.driving_speech = "quiet".to_string(); // confirmation -> earcon

    app.ctx.say_event_with(
        "Automatic braking.",
        SayEvent::queued().category(SpeechCategory::Confirmation),
    );

    let ducks = audio.borrow().ducks.clone();
    assert!(
        !ducks.is_empty(),
        "the earcon played against an unducked mix"
    );
    assert_eq!(*ducks.last().unwrap(), SPEECH_DUCK_LEVEL);
    assert!(app.ctx.speech_ducked());
    app.shutdown();
}

#[test]
fn test_the_earcon_duck_lets_go_on_its_own() {
    // It cannot lean on the pacer's projection, because a silenced line has
    // no voice to project -- so it holds for its own short window and
    // releases. A duck that never released would leave the road permanently
    // halved.
    let window = EARCON_DUCK_S;
    assert!(window <= 0.5, "longer than any ladder earcon needs");

    let mut app = TestApp::new();
    let audio = app.record_audio();
    app.ctx.settings.duck_audio_for_speech = true;
    app.ctx.settings.driving_speech = "quiet".to_string();

    app.ctx.say_event_with(
        "Automatic braking.",
        SayEvent::queued().category(SpeechCategory::Confirmation),
    );
    assert!(app.ctx.speech_ducked());

    // Still inside the window: the mix stays back.
    app.ctx.update_speech_duck();
    assert!(app.ctx.speech_ducked());

    app.ctx.set_earcon_duck_until(monotonic_seconds() - 0.01);
    app.ctx.update_speech_duck();
    assert!(!app.ctx.speech_ducked());
    assert_eq!(*audio.borrow().ducks.last().unwrap(), 1.0);
    app.shutdown();
}

#[test]
#[ignore = "Python swept its own source text for the setting check at every duck engage point; a source sweep has no Rust equivalent. The Rust engage points are engage_earcon_duck / engage_speech_duck, both gated, plus the driving-state ducks"]
fn test_nothing_anywhere_ducks_when_the_player_turned_ducking_off() {}

#[test]
fn test_with_ducking_off_an_earcon_leaves_the_mix_alone() {
    // The behavioral half of the rule, end to end.
    let mut app = TestApp::new();
    let audio = app.record_audio();
    app.ctx.settings.duck_audio_for_speech = false;
    app.ctx.settings.driving_speech = "quiet".to_string();

    app.ctx.say_event_with(
        "Automatic braking.",
        SayEvent::queued().category(SpeechCategory::Confirmation),
    );

    assert!(
        audio.borrow().ducks.is_empty(),
        "the mix was stepped back anyway: {:?}",
        audio.borrow().ducks
    );
    assert!(!app.ctx.speech_ducked());
    app.shutdown();
}
