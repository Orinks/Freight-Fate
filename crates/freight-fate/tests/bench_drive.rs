//! Frame-time benchmark for the per-frame drive loop (`DrivingState::update`
//! -> `states/driving_updates`).
//!
//! Deliberately `#[ignore]`d: it is a measurement, not an assertion, and a
//! benchmark run in a normal `cargo test` would only add seconds to the
//! suite. The Python counterpart is `tools/bench_drive.py`; the two build the
//! same drive (Denver -> Cheyenne, `trip_seed = 0`, start hour 12, engine
//! running, parking brake off, accelerator held) and tick the same number of
//! frames at the same fixed dt, so the two numbers are comparable. The method
//! and every asymmetry that could not be removed are written up in
//! `docs/superpowers/rust-port-benchmarks.md`.
//!
//! Run it in RELEASE -- a debug build of the sim is several times slower and
//! says nothing about what a player would get:
//!
//! ```text
//! CARGO_TARGET_DIR=target/bench cargo test --release -p freight-fate \
//!     --test bench_drive -- --ignored --nocapture
//! ```
//!
//! `FF_BENCH_FRAMES` and `FF_BENCH_WARMUP` override the frame counts (the
//! Python side reads the same two variables).

use std::time::Instant;

use ff_core::data::world::get_world;
use ff_core::models::jobs::make_reposition_job;
use ff_core::models::profile::Profile;

use freight_fate::app::testing::TestApp;
use freight_fate::states::base::{Key, Mods, State};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::DRIVE_PHASE_DELIVERY;

/// One frame of the game's fixed step (`app::FPS` is 60).
const DT: f64 = 1.0 / 60.0;
/// Frames thrown away before timing starts: the first ticks of a drive do
/// one-off work (the departure chain, the first zone lookups, the first
/// corridor decode) that no later frame repeats.
const DEFAULT_WARMUP: usize = 600;
/// 12 000 frames is 200 seconds of play at 60 Hz. The ceiling is the route:
/// with the accelerator pinned the truck reaches Cheyenne at about 15 400
/// frames, and every frame after that is a parked truck rather than a drive.
/// 12 000 leaves the run entirely on the road (about 78 of the 100.4 miles).
const DEFAULT_FRAMES: usize = 12_000;

fn env_usize(name: &str, fallback: usize) -> usize {
    std::env::var(name)
        .ok()
        .and_then(|v| v.trim().parse().ok())
        .unwrap_or(fallback)
}

/// Mean, median, p99, max -- all in microseconds -- over an already-sorted
/// copy of the samples.
struct Stats {
    mean_us: f64,
    median_us: f64,
    p99_us: f64,
    max_us: f64,
    total_ms: f64,
}

fn stats(samples: &[f64]) -> Stats {
    let mut sorted = samples.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).expect("frame times are finite"));
    let n = sorted.len();
    let total: f64 = samples.iter().sum();
    // Nearest-rank percentile, the same rule `tools/bench_drive.py` uses.
    let rank = |q: f64| {
        let idx = ((q * n as f64).ceil() as usize).saturating_sub(1);
        sorted[idx.min(n - 1)]
    };
    Stats {
        mean_us: total / n as f64,
        median_us: rank(0.5),
        p99_us: rank(0.99),
        max_us: sorted[n - 1],
        total_ms: total / 1000.0,
    }
}

/// The transcript suite's drive, exactly as `states_driving_core.rs` builds
/// it: Denver -> Cheyenne at `trip_seed = 0`, start hour 12.
fn a_real_drive(app: &mut TestApp) -> DrivingState {
    let world = get_world();
    let mut profile = Profile::named_in("Prelude", "Denver");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let job = make_reposition_job(world, "Denver", "Cheyenne", false, None)
        .expect("Denver to Cheyenne is a supported reposition");
    let route = world
        .shortest_route("Denver", "Cheyenne", None, false)
        .expect("the world routes")
        .expect("Denver to Cheyenne has a route");
    DrivingState::new(
        &mut app.ctx,
        job,
        route,
        Some(0),
        DRIVE_PHASE_DELIVERY,
        Some(12.0),
    )
}

#[test]
#[ignore = "benchmark: run with --release --ignored --nocapture"]
fn bench_drive_frame_time() {
    let warmup = env_usize("FF_BENCH_WARMUP", DEFAULT_WARMUP);
    let frames = env_usize("FF_BENCH_FRAMES", DEFAULT_FRAMES);

    // The world is a process-global `OnceCell`, so this call is the load and
    // every later `get_world()` is a pointer. Timed here for the record; the
    // startup numbers in the report come from `--smoke`, not from this.
    let t0 = Instant::now();
    let _ = get_world();
    let world_load_ms = t0.elapsed().as_secs_f64() * 1000.0;

    let t0 = Instant::now();
    let mut app = TestApp::new();
    let app_ms = t0.elapsed().as_secs_f64() * 1000.0;

    let t0 = Instant::now();
    let mut drive = a_real_drive(&mut app);
    let build_ms = t0.elapsed().as_secs_f64() * 1000.0;

    drive.enter(&mut app.ctx);
    // A truck that can actually move: engine running, tanks charged, parking
    // brake off. A parked drive would exercise a fraction of the frame.
    drive.trip.truck.set_air_ready(false);
    drive.trip.truck.start_engine();
    // Accelerator held for the whole run (`pygame.key.get_pressed()[K_UP]`
    // on the Python side).
    app.ctx.input.press(Key::Up, Mods::NONE);

    for _ in 0..warmup {
        drive.update(&mut app.ctx, DT);
    }

    let mut samples = Vec::with_capacity(frames);
    for _ in 0..frames {
        let t = Instant::now();
        drive.update(&mut app.ctx, DT);
        samples.push(t.elapsed().as_secs_f64() * 1_000_000.0);
    }

    let s = stats(&samples);
    // What the truck actually did, so the Python run can be checked against
    // this one rather than assumed equivalent.
    let position_mi = drive.trip.position_mi;
    let speed_mph = drive.trip.truck.speed_mph();
    let game_minutes = drive.trip.game_minutes;
    // Anything the drive pushed on top of itself (a traffic stop, a rest
    // screen): the Python side reports the same number, and a mismatch means
    // the two runs did not do the same work.
    let pushed_states = app.ctx.stack_len();

    println!("bench_drive (rust, release)");
    println!("  warmup frames      {warmup}");
    println!("  timed frames       {frames}");
    println!("  dt                 {DT:.6} s (60 Hz)");
    println!("  world load         {world_load_ms:.1} ms");
    println!("  TestApp::new       {app_ms:.1} ms");
    println!("  DrivingState::new  {build_ms:.1} ms");
    println!("  frame mean         {:.2} us", s.mean_us);
    println!("  frame median       {:.2} us", s.median_us);
    println!("  frame p99          {:.2} us", s.p99_us);
    println!("  frame max          {:.2} us", s.max_us);
    println!("  timed total        {:.1} ms", s.total_ms);
    println!("  end position       {position_mi:.3} mi");
    println!("  end speed          {speed_mph:.2} mph");
    println!("  end game minutes   {game_minutes:.3}");
    println!("  states pushed      {pushed_states}");

    // The only assertion: a frame that took longer than a whole second means
    // the run measured something other than the drive.
    assert!(s.max_us < 1_000_000.0, "a frame took over a second");
}
