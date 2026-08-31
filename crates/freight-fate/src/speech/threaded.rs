//! The speech worker: Prism on its own thread, so a wedged screen-reader
//! call can never freeze the game.
//!
//! # Why
//!
//! Every spoken line used to be a synchronous Prism/SAPI call on the main
//! game loop. The one time that call did not return -- tester Shane,
//! 2026-08-30, an event-voice interrupt at an I-77 on-ramp -- the whole
//! game froze with it, silently and permanently: the log's last line is
//! the transcript entry written immediately before `say_event`, and the
//! only thing left to do was kill the process. A screen reader or SAPI
//! wedging is outside this game's control; the game staying drivable
//! through it is not.
//!
//! # The threading invariant, kept
//!
//! The rule in [`crate::speech`] is real: exactly one Prism context per
//! process, and every call on it from one thread (its registry probes are
//! not re-entrant across threads). That invariant never said the thread
//! has to be the game loop's. Here the one context is built INSIDE the
//! worker thread and never leaves it; [`super::live::Speech`] stays
//! `!Send`, and the main thread holds only channels.
//!
//! # Semantics preserved
//!
//! Commands are processed strictly in send order by one worker, so the
//! relative order of says, interrupts, and stops is exactly what it was.
//! What changes is who waits: nobody. If the backend wedges, the queue
//! bounds itself (a full queue drops new SAY lines -- the transcript and
//! review log already have them from the main side -- and never grows),
//! the watchdog in [`ThreadedSpeech::poll`] says so once in the log, and
//! the game keeps driving on earcons until the backend comes back.
//!
//! The two calls that genuinely need an answer (`refresh`,
//! `say_adjustment_preview`) wait a BOUNDED couple of seconds and answer
//! pessimistically on timeout -- a settings-menu hiccup, never a freeze.

use std::sync::mpsc::{self, RecvTimeoutError, TrySendError};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use super::SpeechSink;

/// How long a silent worker is allowed before the watchdog calls it wedged.
const WEDGE_AFTER_S: f64 = 8.0;
/// Command queue depth; beyond it, new say lines are dropped, not queued.
const QUEUE_DEPTH: usize = 256;
/// The worker's own poll cadence when idle.
const IDLE_POLL: Duration = Duration::from_millis(200);
/// Bounded wait for the two calls that need an answer.
const REPLY_WAIT: Duration = Duration::from_secs(2);

enum Command {
    Say {
        text: String,
        interrupt: bool,
    },
    SayEvent {
        text: String,
        interrupt: bool,
    },
    StopMain,
    StopEvent,
    Stop,
    RequestRefresh,
    Refresh {
        announce: bool,
        reply: mpsc::Sender<bool>,
    },
    Configure {
        rate: Option<f64>,
        pitch: Option<f64>,
        volume: Option<f64>,
        voice: Option<String>,
    },
    SelectEventBackend(Option<String>),
    Preview {
        setting: String,
        text: String,
        interrupt: bool,
        reply: mpsc::Sender<bool>,
    },
    Shutdown {
        done: mpsc::Sender<()>,
    },
}

/// The query answers, published by the worker after every state change so
/// the main thread can answer without asking Prism anything.
#[derive(Clone, Default)]
struct Snapshot {
    available: bool,
    backend_name: String,
    event_backend_name: String,
    has_separate_event_voice: bool,
    supports_rate: bool,
    supports_pitch: bool,
    supports_volume: bool,
    event_supports_rate: bool,
    event_backend_options: Vec<String>,
    voice_names: Vec<String>,
}

fn publish(snapshot: &Arc<Mutex<Snapshot>>, inner: &dyn SpeechSink) {
    let fresh = Snapshot {
        available: inner.available(),
        backend_name: inner.backend_name(),
        event_backend_name: inner.event_backend_name(),
        has_separate_event_voice: inner.has_separate_event_voice(),
        supports_rate: inner.supports_rate(),
        supports_pitch: inner.supports_pitch(),
        supports_volume: inner.supports_volume(),
        event_supports_rate: inner.event_supports_rate(),
        event_backend_options: inner.event_backend_options(),
        voice_names: inner.voice_names(),
    };
    *snapshot.lock().expect("speech snapshot lock") = fresh;
}

/// A [`SpeechSink`] whose Prism lives on a worker thread.
pub struct ThreadedSpeech {
    commands: mpsc::SyncSender<Command>,
    snapshot: Arc<Mutex<Snapshot>>,
    heartbeat: Arc<Mutex<Instant>>,
    /// Set by [`shutdown`](SpeechSink::shutdown) BEFORE the shutdown
    /// command is queued: the worker checks it per command and drops
    /// queued sentences instead of speaking them. Without it, quitting
    /// waited through every queued synchronous say before the release --
    /// which read as the game "taking longer to hand the screen reader
    /// back" than before the worker existed (Brandon, 2026-08-31).
    shutting_down: Arc<std::sync::atomic::AtomicBool>,
    /// Watchdog latch: the wedge is reported once, and once more only if
    /// the worker recovers and wedges again.
    wedged: bool,
    dropped_lines: u64,
}

impl ThreadedSpeech {
    /// The production sink: Prism built inside the worker.
    pub fn spawn() -> Self {
        Self::spawn_with(|| Box::new(super::live::Speech::new()))
    }

    /// A worker around any sink factory -- the tests hand in fakes that
    /// block or record. The factory runs ON the worker thread, which is
    /// what lets the `!Send` production sink live there.
    pub fn spawn_with<F>(factory: F) -> Self
    where
        F: FnOnce() -> Box<dyn SpeechSink> + Send + 'static,
    {
        let (commands, rx) = mpsc::sync_channel::<Command>(QUEUE_DEPTH);
        let snapshot: Arc<Mutex<Snapshot>> = Arc::default();
        let heartbeat = Arc::new(Mutex::new(Instant::now()));
        let shutting_down = Arc::new(std::sync::atomic::AtomicBool::new(false));
        let worker_snapshot = Arc::clone(&snapshot);
        let worker_heartbeat = Arc::clone(&heartbeat);
        let worker_shutting_down = Arc::clone(&shutting_down);
        std::thread::Builder::new()
            .name("speech".to_string())
            .spawn(move || {
                let mut inner = factory();
                publish(&worker_snapshot, inner.as_ref());
                let beat = || {
                    *worker_heartbeat.lock().expect("speech heartbeat lock") = Instant::now();
                };
                loop {
                    beat();
                    // Quitting: everything still queued is a sentence the
                    // player chose not to wait for. Skip the says, keep
                    // answering everything that carries a reply, and let
                    // the Shutdown command through to the release.
                    let draining = worker_shutting_down.load(std::sync::atomic::Ordering::Relaxed);
                    match rx.recv_timeout(IDLE_POLL) {
                        Ok(Command::Say { text, interrupt }) => {
                            if !draining {
                                inner.say(&text, interrupt)
                            }
                        }
                        Ok(Command::SayEvent { text, interrupt }) => {
                            if !draining {
                                inner.say_event(&text, interrupt)
                            }
                        }
                        Ok(Command::StopMain) => inner.stop_main(),
                        Ok(Command::StopEvent) => inner.stop_event(),
                        Ok(Command::Stop) => inner.stop(),
                        Ok(Command::RequestRefresh) => inner.request_refresh(),
                        Ok(Command::Refresh { announce, reply }) => {
                            let changed = inner.refresh(announce);
                            publish(&worker_snapshot, inner.as_ref());
                            let _ = reply.send(changed);
                        }
                        Ok(Command::Configure {
                            rate,
                            pitch,
                            volume,
                            voice,
                        }) => {
                            inner.configure(rate, pitch, volume, voice.as_deref());
                            publish(&worker_snapshot, inner.as_ref());
                        }
                        Ok(Command::SelectEventBackend(name)) => {
                            inner.select_event_backend(name.as_deref());
                            publish(&worker_snapshot, inner.as_ref());
                        }
                        Ok(Command::Preview {
                            setting,
                            text,
                            interrupt,
                            reply,
                        }) => {
                            let spoke = inner.say_adjustment_preview(&setting, &text, interrupt);
                            let _ = reply.send(spoke);
                        }
                        Ok(Command::Shutdown { done }) => {
                            inner.shutdown();
                            let _ = done.send(());
                            return;
                        }
                        Err(RecvTimeoutError::Timeout) => {
                            // The 3-second voice health poll, on the worker's
                            // own cadence; a backend swap it performs changes
                            // the answers the main thread hands out.
                            inner.poll(IDLE_POLL.as_secs_f64());
                            publish(&worker_snapshot, inner.as_ref());
                        }
                        Err(RecvTimeoutError::Disconnected) => {
                            inner.shutdown();
                            return;
                        }
                    }
                }
            })
            .expect("the speech worker spawns");
        ThreadedSpeech {
            commands,
            snapshot,
            heartbeat,
            shutting_down,
            wedged: false,
            dropped_lines: 0,
        }
    }

    fn snapshot(&self) -> Snapshot {
        self.snapshot.lock().expect("speech snapshot lock").clone()
    }

    /// Queue a command without ever waiting. A full queue means the worker
    /// is wedged inside the backend; a say line is then dropped (the
    /// transcript and review log keep it), anything else is tried anyway.
    fn send_lossy(&mut self, command: Command) {
        if let Err(TrySendError::Full(command)) = self.commands.try_send(command) {
            if matches!(command, Command::Say { .. } | Command::SayEvent { .. }) {
                self.dropped_lines += 1;
                if self.dropped_lines.is_power_of_two() {
                    log::warn!(
                        "speech queue full: {} line(s) dropped while the backend is stalled",
                        self.dropped_lines
                    );
                }
            }
            // Non-say commands on a full queue are lost too, but the queue
            // only fills when the backend has been gone for hundreds of
            // lines; the periodic snapshot republish squares state back up
            // when it returns.
        }
    }

    fn bounded_reply(&mut self, build: impl FnOnce(mpsc::Sender<bool>) -> Command) -> bool {
        let (reply_tx, reply_rx) = mpsc::channel();
        self.send_lossy(build(reply_tx));
        reply_rx.recv_timeout(REPLY_WAIT).unwrap_or(false)
    }
}

impl SpeechSink for ThreadedSpeech {
    fn say(&mut self, text: &str, interrupt: bool) {
        self.send_lossy(Command::Say {
            text: text.to_string(),
            interrupt,
        });
    }

    fn say_event(&mut self, text: &str, interrupt: bool) {
        self.send_lossy(Command::SayEvent {
            text: text.to_string(),
            interrupt,
        });
    }

    fn stop_main(&mut self) {
        self.send_lossy(Command::StopMain);
    }

    fn stop_event(&mut self) {
        self.send_lossy(Command::StopEvent);
    }

    fn stop(&mut self) {
        self.send_lossy(Command::Stop);
    }

    /// The main thread's poll is now a WATCHDOG, not a backend call: it
    /// judges the worker by its heartbeat and says so, once, when the
    /// backend has stopped answering. The game keeps running either way --
    /// that sentence is this module's whole reason to exist.
    fn poll(&mut self, _dt: f64) {
        let stale = self
            .heartbeat
            .lock()
            .expect("speech heartbeat lock")
            .elapsed()
            .as_secs_f64();
        if stale > WEDGE_AFTER_S && !self.wedged {
            self.wedged = true;
            log::error!(
                "speech backend stopped responding {stale:.0}s ago (a wedged screen reader \
                 or SAPI call); the game continues without speech until it returns"
            );
        } else if stale <= WEDGE_AFTER_S && self.wedged {
            self.wedged = false;
            log::warn!("speech backend recovered");
        }
    }

    fn request_refresh(&mut self) {
        self.send_lossy(Command::RequestRefresh);
    }

    fn available(&self) -> bool {
        // A wedged worker cannot speak, whatever the backend last claimed.
        let stale = self
            .heartbeat
            .lock()
            .expect("speech heartbeat lock")
            .elapsed()
            .as_secs_f64();
        self.snapshot().available && stale <= WEDGE_AFTER_S
    }

    fn backend_name(&self) -> String {
        self.snapshot().backend_name
    }

    fn has_separate_event_voice(&self) -> bool {
        self.snapshot().has_separate_event_voice
    }

    fn event_backend_name(&self) -> String {
        self.snapshot().event_backend_name
    }

    fn supports_rate(&self) -> bool {
        self.snapshot().supports_rate
    }

    fn supports_pitch(&self) -> bool {
        self.snapshot().supports_pitch
    }

    fn supports_volume(&self) -> bool {
        self.snapshot().supports_volume
    }

    fn event_supports_rate(&self) -> bool {
        self.snapshot().event_supports_rate
    }

    fn event_backend_options(&self) -> Vec<String> {
        self.snapshot().event_backend_options
    }

    fn select_event_backend(&mut self, name: Option<&str>) {
        self.send_lossy(Command::SelectEventBackend(name.map(str::to_string)));
    }

    fn voice_names(&self) -> Vec<String> {
        self.snapshot().voice_names
    }

    fn configure(
        &mut self,
        rate: Option<f64>,
        pitch: Option<f64>,
        volume: Option<f64>,
        voice: Option<&str>,
    ) {
        self.send_lossy(Command::Configure {
            rate,
            pitch,
            volume,
            voice: voice.map(str::to_string),
        });
    }

    fn say_adjustment_preview(&mut self, setting: &str, text: &str, interrupt: bool) -> bool {
        let setting = setting.to_string();
        let text = text.to_string();
        self.bounded_reply(|reply| Command::Preview {
            setting,
            text,
            interrupt,
            reply,
        })
    }

    fn refresh(&mut self, announce: bool) -> bool {
        let (reply_tx, reply_rx) = mpsc::channel();
        self.send_lossy(Command::Refresh {
            announce,
            reply: reply_tx,
        });
        // Re-detection really can take a beat; give it longer than the
        // preview, still bounded.
        reply_rx
            .recv_timeout(Duration::from_secs(4))
            .unwrap_or(false)
    }

    fn shutdown(&mut self) {
        // The flag first, then the command: the worker skips every say
        // still queued ahead of it, so the wait below covers one in-flight
        // utterance at most, not the whole backlog.
        self.shutting_down
            .store(true, std::sync::atomic::Ordering::Relaxed);
        let (done_tx, done_rx) = mpsc::channel();
        if self
            .commands
            .try_send(Command::Shutdown { done: done_tx })
            .is_ok()
        {
            // Give the backend a bounded chance to release cleanly; a
            // wedged one is abandoned, which is exactly what quitting a
            // frozen game by hand used to do -- minus freezing the game.
            let _ = done_rx.recv_timeout(Duration::from_secs(3));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

    /// A sink that records calls and can be told to wedge forever.
    struct StubSink {
        calls: Arc<Mutex<Vec<String>>>,
        wedge: Arc<AtomicBool>,
        polls: Arc<AtomicUsize>,
    }

    impl SpeechSink for StubSink {
        fn say(&mut self, text: &str, _interrupt: bool) {
            if self.wedge.load(Ordering::SeqCst) {
                // A wedged SAPI call: never returns (bounded here so the
                // test process itself can exit).
                std::thread::sleep(Duration::from_secs(600));
            }
            self.calls.lock().unwrap().push(format!("say {text}"));
        }
        fn say_event(&mut self, text: &str, _interrupt: bool) {
            self.calls.lock().unwrap().push(format!("event {text}"));
        }
        fn stop_main(&mut self) {
            self.calls.lock().unwrap().push("stop_main".into());
        }
        fn stop_event(&mut self) {}
        fn stop(&mut self) {}
        fn poll(&mut self, _dt: f64) {
            self.polls.fetch_add(1, Ordering::SeqCst);
        }
        fn request_refresh(&mut self) {}
        fn available(&self) -> bool {
            true
        }
        fn backend_name(&self) -> String {
            "stub".to_string()
        }
        fn has_separate_event_voice(&self) -> bool {
            true
        }
        fn event_backend_name(&self) -> String {
            "stub-event".to_string()
        }
        fn supports_rate(&self) -> bool {
            true
        }
        fn supports_pitch(&self) -> bool {
            false
        }
        fn supports_volume(&self) -> bool {
            true
        }
        fn event_supports_rate(&self) -> bool {
            false
        }
        fn event_backend_options(&self) -> Vec<String> {
            vec!["stub-event".to_string()]
        }
        fn select_event_backend(&mut self, _name: Option<&str>) {}
        fn voice_names(&self) -> Vec<String> {
            vec!["Stub Voice".to_string()]
        }
        fn configure(
            &mut self,
            _rate: Option<f64>,
            _pitch: Option<f64>,
            _volume: Option<f64>,
            _voice: Option<&str>,
        ) {
        }
        fn say_adjustment_preview(&mut self, setting: &str, _t: &str, _i: bool) -> bool {
            self.calls
                .lock()
                .unwrap()
                .push(format!("preview {setting}"));
            true
        }
        fn refresh(&mut self, _announce: bool) -> bool {
            true
        }
        fn shutdown(&mut self) {
            self.calls.lock().unwrap().push("shutdown".into());
        }
    }

    type CallLog = Arc<Mutex<Vec<String>>>;

    /// The worker under test plus the stub's shared handles.
    struct Rig {
        sink: ThreadedSpeech,
        calls: CallLog,
        wedge: Arc<AtomicBool>,
        polls: Arc<AtomicUsize>,
    }

    fn rig() -> Rig {
        let calls: Arc<Mutex<Vec<String>>> = Arc::default();
        let wedge = Arc::new(AtomicBool::new(false));
        let polls = Arc::new(AtomicUsize::new(0));
        let (calls2, wedge2, polls2) = (calls.clone(), wedge.clone(), polls.clone());
        let sink = ThreadedSpeech::spawn_with(move || {
            Box::new(StubSink {
                calls: calls2,
                wedge: wedge2,
                polls: polls2,
            })
        });
        Rig {
            sink,
            calls,
            wedge,
            polls,
        }
    }

    fn wait_for(calls: &Arc<Mutex<Vec<String>>>, count: usize) {
        for _ in 0..200 {
            if calls.lock().unwrap().len() >= count {
                return;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        panic!(
            "worker never processed {count} call(s): {:?}",
            calls.lock().unwrap()
        );
    }

    /// Quit must not wait through the say backlog: the shutdown flag makes
    /// the worker DROP every sentence still queued, so the screen reader
    /// gets the desk back after at most the in-flight utterance (Brandon,
    /// 2026-08-31: closing the game took visibly longer than before the
    /// speech worker existed).
    #[test]
    fn shutdown_skips_the_queued_backlog_instead_of_speaking_it() {
        let Rig {
            mut sink, calls, ..
        } = rig();
        // A backlog a player would otherwise sit through.
        for i in 0..50 {
            sink.say(&format!("queued {i}"), false);
        }
        let started = Instant::now();
        sink.shutdown();
        assert!(
            started.elapsed() < Duration::from_secs(2),
            "shutdown waited through the backlog: {:?}",
            started.elapsed()
        );
        let spoken = calls.lock().unwrap();
        let says = spoken.iter().filter(|c| c.starts_with("say ")).count();
        assert!(
            says < 50,
            "every queued sentence was spoken before release ({says})"
        );
        assert!(
            spoken.iter().any(|c| c == "shutdown"),
            "the backend was never released: {spoken:?}"
        );
    }

    #[test]
    fn says_arrive_on_the_worker_in_send_order() {
        let Rig {
            mut sink, calls, ..
        } = rig();
        sink.say("one", false);
        sink.say_event("two", true);
        sink.stop_main();
        wait_for(&calls, 3);
        assert_eq!(
            calls.lock().unwrap().as_slice(),
            ["say one", "event two", "stop_main"]
        );
        sink.shutdown();
        assert!(calls.lock().unwrap().iter().any(|c| c == "shutdown"));
    }

    #[test]
    fn queries_answer_from_the_snapshot_without_touching_the_backend() {
        let Rig { sink, .. } = rig();
        // Give the worker a beat to publish its first snapshot.
        for _ in 0..100 {
            if sink.available() {
                break;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        assert!(sink.available());
        assert_eq!(sink.backend_name(), "stub");
        assert_eq!(sink.event_backend_name(), "stub-event");
        assert!(sink.supports_rate());
        assert!(!sink.supports_pitch());
        assert_eq!(sink.voice_names(), ["Stub Voice"]);
    }

    #[test]
    fn a_wedged_backend_never_blocks_a_say_and_the_watchdog_notices() {
        let Rig {
            mut sink, wedge, ..
        } = rig();
        wedge.store(true, Ordering::SeqCst);
        sink.say("this one wedges the backend", false);
        // The whole point: further speech returns instantly while the
        // backend sits inside its stuck call.
        let started = Instant::now();
        for i in 0..300 {
            sink.say(&format!("line {i}"), false);
        }
        sink.stop();
        assert!(
            started.elapsed() < Duration::from_secs(1),
            "queueing speech must never wait on the backend"
        );
        // The watchdog reads the stale heartbeat as unavailable well before
        // it logs the wedge.
        std::thread::sleep(Duration::from_secs_f64(WEDGE_AFTER_S + 1.0));
        sink.poll(0.016);
        assert!(!sink.available());
        // Bounded replies answer pessimistically instead of hanging.
        let answered = Instant::now();
        assert!(!sink.say_adjustment_preview("speech_rate", "preview", false));
        assert!(answered.elapsed() < Duration::from_secs(4));
        // Shutdown of a wedged worker is bounded too: abandoned, not joined.
        let quitting = Instant::now();
        sink.shutdown();
        assert!(quitting.elapsed() < Duration::from_secs(5));
    }

    #[test]
    fn the_worker_polls_the_backend_on_its_own_cadence() {
        let Rig { sink, polls, .. } = rig();
        std::thread::sleep(Duration::from_millis(900));
        assert!(
            polls.load(Ordering::SeqCst) >= 2,
            "the idle worker drives the 3-second voice health poll"
        );
        drop(sink);
    }

    #[test]
    fn bounded_replies_reach_the_backend_when_it_is_healthy() {
        let Rig {
            mut sink, calls, ..
        } = rig();
        assert!(sink.say_adjustment_preview("speech_rate", "faster", false));
        assert!(sink.refresh(false));
        wait_for(&calls, 1);
        assert!(calls.lock().unwrap()[0].starts_with("preview"));
        sink.shutdown();
    }
}
