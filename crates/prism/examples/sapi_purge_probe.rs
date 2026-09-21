//! Reproduction probe for the "both voices stop" wedge (Chris's log,
//! 2026-09-03): speak a long line through Prism's SAPI backend, stop it
//! mid-sentence the way the game's stop-speech key and interrupting road
//! lines do, and repeat. A watchdog on the main thread reports the phase
//! the worker never came back from.
//!
//! `cargo run -p prism --example sapi_purge_probe -- [iterations] [--nvda]`
//! It speaks out loud.
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let iterations: u64 = args.iter().find_map(|a| a.parse().ok()).unwrap_or(150);
    let with_nvda = args.iter().any(|a| a == "--nvda");
    let with_refresh = args.iter().any(|a| a == "--refresh");
    // phase: iteration * 10 + step; step 1 speak, 2 sleep, 3 stop-nvda,
    // 4 stop-sapi, 5 interrupt-speak, 6 refresh probe, 9 done
    let phase = Arc::new(AtomicU64::new(0));
    let worker_phase = Arc::clone(&phase);
    std::thread::spawn(move || {
        let ctx = prism::Context::new().expect("prism context");
        let sapi_id = ctx.id_by_name("SAPI").expect("SAPI registered");
        let mut sapi = ctx.acquire(sapi_id).expect("SAPI acquired");
        let mut nvda = if with_nvda {
            ctx.id_by_name("NVDA").and_then(|id| ctx.acquire(id).ok())
        } else {
            None
        };
        eprintln!(
            "SAPI usable={} nvda={}",
            sapi.features().is_supported_at_runtime(),
            nvda.as_ref()
                .map(|b| b.features().is_supported_at_runtime())
                .unwrap_or(false)
        );
        let line = "97 percent there, 8 miles left. On I-676 East in New Jersey, toward Atlantic City, New Jersey. Radio handover. ABC Classic is slow to answer. Trying again.";
        let mut seed: u64 = 0x9E3779B97F4A7C15;
        for i in 1..=iterations {
            let set = |step: u64| worker_phase.store(i * 10 + step, Ordering::SeqCst);
            set(1);
            let _ = sapi.speak(line, false);
            set(2);
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            let ms = 30 + (seed % 900);
            std::thread::sleep(Duration::from_millis(ms));
            if let Some(n) = nvda.as_mut() {
                set(3);
                let _ = n.speak("menu line", true);
                let _ = n.stop();
            }
            set(4);
            let _ = sapi.stop();
            set(5);
            let _ = sapi.speak("Traffic ahead.", true);
            if with_refresh {
                // The game's 3 s health poll: every registered backend is
                // acquired and asked for its runtime features.
                set(6);
                for id in ctx.backend_ids() {
                    if let Ok(b) = ctx.acquire(id) {
                        let _ = b.features().is_supported_at_runtime();
                    }
                }
            }
            set(9);
            if i % 10 == 0 {
                eprintln!("iteration {i} ok");
            }
        }
        worker_phase.store(u64::MAX, Ordering::SeqCst);
    });
    let mut last = 0;
    let mut since = Instant::now();
    loop {
        std::thread::sleep(Duration::from_millis(200));
        let p = phase.load(Ordering::SeqCst);
        if p == u64::MAX {
            eprintln!("CLEAN: {iterations} stop-while-speaking cycles, no wedge");
            std::process::exit(0);
        }
        if p != last {
            last = p;
            since = Instant::now();
        } else if since.elapsed() > Duration::from_secs(10) {
            eprintln!(
                "WEDGED: iteration {} step {} has not returned for 10 s",
                p / 10,
                p % 10
            );
            std::process::exit(2);
        }
    }
}
