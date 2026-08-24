//! Port of the `GameContext` tests of `tests/test_speech_audio.py`: which
//! channel events go to, and that a state transition never flushes menu
//! speech before the new screen speaks.

use freight_fate::app::testing::TestApp;
use freight_fate::app::GameContext;
use freight_fate::speech::CaptureSpeech;
use freight_fate::states::base::State;

#[test]
fn test_events_via_screen_reader_never_interrupt_even_when_critical() {
    let mut app = TestApp::new();
    app.ctx.settings.sapi_events = false; // event voice = screen reader
    app.ctx.say_event("Brake now!"); // a critical event
                                     // Not on a separate voice, so the stale queue is flushed first and the
                                     // event is then spoken as a fresh screen-reader utterance.
    assert_eq!(app.speech().stop_main_calls(), 1);
    assert!(app.event_calls().is_empty());
    assert_eq!(app.main_calls(), vec![("Brake now!".to_string(), false)]);
    app.shutdown();
}

#[test]
fn test_events_on_separate_sapi_voice_keep_requested_interrupt() {
    let mut app = TestApp::with_speech(CaptureSpeech::full_voice());
    app.ctx.settings.sapi_events = true; // dedicated SAPI event voice
    app.ctx.say_event("Brake now!");
    app.ctx
        .say_event_with("Weather changing.", freight_fate::app::SayEvent::queued());
    assert!(app.main_calls().is_empty());
    assert_eq!(
        app.event_calls(),
        vec![
            ("Brake now!".to_string(), true),
            ("Weather changing.".to_string(), false)
        ]
    );
    app.shutdown();
}

#[test]
fn test_state_transitions_do_not_flush_menu_speech_before_enter() {
    struct SayingState;
    impl State for SayingState {
        fn enter(&mut self, ctx: &mut GameContext) {
            ctx.say("New screen.");
        }
    }
    let mut app = TestApp::new();
    app.push_state(SayingState);
    assert_eq!(app.speech().stop_calls(), 0);
    assert_eq!(app.speech().stop_main_calls(), 0);
    assert_eq!(app.main_calls(), vec![("New screen.".to_string(), true)]);
    app.shutdown();
}
