//! Can a second Prism context, on a second thread, speak while the first
//! context is alive and holding SAPI mid-utterance on its own thread?
//!
//! This is the precondition for respawning the game's speech worker after
//! a wedge (Chris's log, 2026-09-03: a SAPI purge that never returned took
//! both voices for the rest of the session). If Prism hands the second
//! context the SAME cached SAPI instance, the respawned worker would block
//! on the same lock and the answer is "no".
//!
//! `cargo run -p prism --example context_respawn_probe` -- speaks out loud.
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

fn main() {
    let phase = Arc::new(AtomicU64::new(0));
    let p1 = Arc::clone(&phase);
    // Thread 1: the "wedged" worker. Builds context A, starts a long SAPI
    // utterance, then parks holding everything.
    std::thread::spawn(move || {
        let ctx = prism::Context::new().expect("context A");
        let id = ctx.id_by_name("SAPI").expect("SAPI");
        let mut sapi = ctx.acquire(id).expect("SAPI A");
        let _ = sapi.speak(
            "Context A is speaking a long sentence that keeps going, and going, and going, so the second context can be tested while this one is busy, and still going.",
            true,
        );
        p1.store(1, Ordering::SeqCst);
        std::thread::sleep(Duration::from_secs(4));
        drop(sapi);
        drop(ctx);
        eprintln!("context A shut down");
    });
    while phase.load(Ordering::SeqCst) < 1 {
        std::thread::sleep(Duration::from_millis(20));
    }
    std::thread::sleep(Duration::from_millis(300));
    let p2 = Arc::clone(&phase);
    std::thread::spawn(move || {
        let started = Instant::now();
        let ctx = match prism::Context::new() {
            Ok(ctx) => ctx,
            Err(err) => {
                eprintln!("RESULT: second context refused: {err}");
                std::process::exit(3);
            }
        };
        eprintln!("context B created in {:?}", started.elapsed());
        let id = ctx.id_by_name("SAPI").expect("SAPI");
        let sapi = ctx.acquire(id).expect("SAPI B");
        // Shared instance test: A's utterance is still running; a distinct
        // SAPI voice in B is idle.
        let speaking = sapi.is_speaking();
        eprintln!("B sees SAPI speaking = {speaking:?} (true => same instance as A)");
        // And a created (uncached) instance, which must be idle either way.
        if let Ok(fresh) = ctx.create(id) {
            eprintln!(
                "B fresh SAPI instance: speaking = {:?}, usable = {}",
                fresh.is_speaking(),
                fresh.features().is_supported_at_runtime()
            );
        } else {
            eprintln!("B could not create a fresh SAPI instance");
        }
        let mut sapi = sapi;
        p2.store(2, Ordering::SeqCst);
        let _ = sapi.speak("Context B speaking.", false);
        p2.store(3, Ordering::SeqCst);
        std::thread::sleep(Duration::from_millis(600));
        let _ = sapi.stop();
        p2.store(4, Ordering::SeqCst);
        let _ = sapi.speak("Context B interrupting.", true);
        p2.store(5, Ordering::SeqCst);
        if let Some(nid) = ctx.id_by_name("NVDA") {
            if let Ok(mut nvda) = ctx.acquire(nid) {
                eprintln!(
                    "B NVDA usable = {}",
                    nvda.features().is_supported_at_runtime()
                );
                let _ = nvda.speak("Context B through NVDA.", true);
            }
        }
        p2.store(9, Ordering::SeqCst);
        // Outlive A's shutdown, then speak again through both a re-acquired
        // (cached) instance and the one B already holds.
        std::thread::sleep(Duration::from_millis(3500));
        let _ = sapi.speak("Context B after A shut down.", true);
        if let Ok(mut again) = ctx.acquire(id) {
            let _ = again.speak("Re-acquired after A shut down.", false);
            eprintln!(
                "B re-acquire after A shutdown: usable = {}",
                again.features().is_supported_at_runtime()
            );
        }
        std::thread::sleep(Duration::from_millis(1500));
        p2.store(10, Ordering::SeqCst);
    });
    let mut last = 0;
    let mut since = Instant::now();
    loop {
        std::thread::sleep(Duration::from_millis(100));
        let p = phase.load(Ordering::SeqCst);
        if p == 10 {
            eprintln!("RESULT: second context spoke, stopped and interrupted while A was alive");
            std::process::exit(0);
        }
        if p != last {
            last = p;
            since = Instant::now();
        } else if since.elapsed() > Duration::from_secs(10) {
            eprintln!("RESULT: WEDGED at phase {p} (2 speak, 3 stop, 4 interrupt-speak, 5 nvda)");
            std::process::exit(2);
        }
    }
}
