//! Which Prism call leaks Windows handles or USER objects when the game's
//! speech worker re-runs backend selection every 3 s?
//!
//! The game's health poll acquires each registry backend in priority order
//! and reads its features until one is usable. This loops the same calls
//! and prints the process's USER-object, GDI-object and kernel-handle
//! counts each round, so a leak shows as a count that climbs with the
//! iteration number.
//!
//! `cargo run -p prism --example handle_leak_probe` -- all backends, in
//! registry priority order, stopping at the first usable one (the game's
//! loop). Env: `PROBE_BACKEND=NAME` restricts to one backend,
//! `PROBE_MODE=acquire|features|create|acquire_forget|both` (default both),
//! `PROBE_ITERS`, and `FREIGHT_FATE_PRISM_PATH` points it at another Prism
//! build.
//!
//! Findings, 2026-09-12: `PROBE_BACKEND=OneCore PROBE_MODE=acquire` leaks
//! one USER object, two handles and about 30 KiB per iteration on
//! prismatoid 0.17.3 and 0.18.2; `acquire_forget` is flat, so the leak is
//! in freeing an acquired instance. prismatoid 0.16.7 (the Python 1.8
//! line) frees the same way and is clean. NVDA, SAPI and the rest are
//! clean after first use on every build.
use std::time::Duration;

#[cfg(windows)]
mod counts {
    #[link(name = "user32")]
    extern "system" {
        fn GetGuiResources(process: isize, flags: u32) -> u32;
    }
    #[link(name = "kernel32")]
    extern "system" {
        fn GetCurrentProcess() -> isize;
        fn GetProcessHandleCount(process: isize, count: *mut u32) -> i32;
        fn K32GetProcessMemoryInfo(process: isize, counters: *mut Counters, cb: u32) -> i32;
    }
    #[repr(C)]
    #[derive(Default)]
    pub struct Counters {
        cb: u32,
        page_faults: u32,
        peak_ws: usize,
        ws: usize,
        peak_paged: usize,
        paged: usize,
        peak_nonpaged: usize,
        nonpaged: usize,
        pagefile: usize,
        peak_pagefile: usize,
    }
    /// Private commit in KiB.
    pub fn private_kib() -> u64 {
        // SAFETY: zeroed counters with `cb` set, as the API requires.
        unsafe {
            let mut c = Counters {
                cb: std::mem::size_of::<Counters>() as u32,
                ..Default::default()
            };
            K32GetProcessMemoryInfo(GetCurrentProcess(), &mut c, c.cb);
            (c.pagefile / 1024) as u64
        }
    }
    pub fn read() -> (u32, u32, u32) {
        // SAFETY: pseudo-handle of the current process; plain counters.
        unsafe {
            let me = GetCurrentProcess();
            let mut handles = 0u32;
            GetProcessHandleCount(me, &mut handles);
            (GetGuiResources(me, 1), GetGuiResources(me, 0), handles)
        }
    }
}
#[cfg(not(windows))]
mod counts {
    pub fn read() -> (u32, u32, u32) {
        (0, 0, 0)
    }
    pub fn private_kib() -> u64 {
        0
    }
}

fn main() {
    let only = std::env::var("PROBE_BACKEND").ok();
    let mode = std::env::var("PROBE_MODE").unwrap_or_else(|_| "both".into());
    let iters: usize = std::env::var("PROBE_ITERS")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(120);
    let ctx = prism::Context::new().expect("prism context");
    let mut ids: Vec<(i32, prism::PrismBackendId, String)> = ctx
        .backend_ids()
        .into_iter()
        .map(|id| (ctx.priority_of(id), id, ctx.name_of(id).unwrap_or_default()))
        .collect();
    ids.sort_by_key(|(p, _, _)| std::cmp::Reverse(*p));
    for (p, id, name) in &ids {
        eprintln!("backend {name} id={id} priority={p}");
    }
    let (u0, g0, h0) = counts::read();
    let k0 = counts::private_kib();
    eprintln!("start: user={u0} gdi={g0} handles={h0} private={k0} KiB mode={mode} only={only:?}");
    for i in 0..iters {
        for (_, id, name) in &ids {
            if let Some(only) = &only {
                if only != name {
                    continue;
                }
            }
            let usable = match mode.as_str() {
                "acquire" => ctx.acquire(*id).is_ok(),
                "create" => ctx.create(*id).is_ok(),
                // Acquire and never free: tells whether the leak is in
                // the acquire or in the release half of the cycle.
                "acquire_forget" => match ctx.acquire(*id) {
                    Ok(b) => {
                        std::mem::forget(b);
                        true
                    }
                    Err(_) => false,
                },
                "features" => ctx
                    .acquire(*id)
                    .map(|b| b.features().is_supported_at_runtime())
                    .unwrap_or(false),
                _ => match ctx.acquire(*id) {
                    Ok(b) => {
                        let f = b.features();
                        f.is_supported_at_runtime() && (f.supports_output() || f.supports_speak())
                    }
                    Err(_) => false,
                },
            };
            if only.is_none() && usable && mode == "both" {
                break; // the game stops at the first usable backend
            }
        }
        if i % 10 == 9 {
            let (u, g, h) = counts::read();
            let k = counts::private_kib();
            eprintln!(
                "iter {:>4}: user={u} (+{}) gdi={g} (+{}) handles={h} (+{}) private={k} KiB (+{})",
                i + 1,
                u as i64 - u0 as i64,
                g as i64 - g0 as i64,
                h as i64 - h0 as i64,
                k as i64 - k0 as i64
            );
        }
        std::thread::sleep(Duration::from_millis(5));
    }
}
