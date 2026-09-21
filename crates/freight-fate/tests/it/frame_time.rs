//! How long a frame takes while the game is being DRIVEN, and a gate that
//! fails when that regresses.
//!
//! `bench_drive.rs` next door times `DrivingState::update` alone on a short
//! plains route. This file times the whole per-frame path the shipped loop
//! runs -- `App::tick` (controller repeats, the speech poll, cloud notices,
//! the audio fades, the speech duck, the state update, presence, the
//! achievement notice) plus `App::visible_lines`, which is everything
//! `App::frame` does once the SDL window is out of the picture -- and it
//! does it over a long, varied mountain route rather than empty interstate.
//!
//! # The route
//!
//! Denver -> Silverthorne -> Edwards -> Glenwood Springs -> Grand Junction:
//! 246 miles of I-70 in four legs. It was chosen because it is the least
//! uniform drive in the world data rather than the longest -- the Front
//! Range climb, the Eisenhower bore, Vail Pass, Glenwood Canyon and the
//! run down to the Grand Valley. All four legs carry full corridor detail
//! (grade segments, elevation samples, lane segments, interchanges,
//! checkpoints, restrictions, speed limits, AADT), so the frames being
//! timed are frames doing the game's real work: grade and curve lookups,
//! zone transitions, traffic in a rolling bubble, hazards, the speech
//! ladder and the event pacer.
//!
//! The route is longer than the run reaches. [`DriveRig::steer`] is a
//! throttle and a brake, not a player, and 63.5 miles in -- most of the way
//! to Silverthorne, over the Divide and down the far side -- it has run the
//! air tanks down and the spring brakes park the truck. That is about
//! 35 000 timed frames, ten minutes of real play, and the report names
//! where and why it ended rather than leaving a reader to assume the road
//! ran out. Anyone extending this should teach the driver the retarder
//! before reaching for a longer route.
//!
//! Traffic and hazards are LEFT ON. `PlaytestHarness` neutralises both
//! (`neutralize_random_trip_friction`) because it is measuring what the
//! game SAYS and traffic makes that non-repeatable; here they are the
//! workload, and the trip seed is what makes them repeatable instead.
//!
//! # Determinism
//!
//! The trip seed is pinned ([`TRIP_SEED`]) and the start hour with it. A
//! seeded trip seeds the weather system too (`WeatherSystem::new`), so the
//! run cannot draw an ice day one morning and a clear one the next -- an
//! unseeded drive picks fresh weather every time and ice changes the whole
//! drive. The event pacer runs on a [`FakeClock`] advanced one frame per
//! frame, for the reason written up on `PlaytestHarness::clock`: on the
//! wall clock a simulated drive outruns real time by two orders of
//! magnitude and the pacer correctly drops almost every ambient line, so
//! the speech half of the frame would go unmeasured.
//!
//! # Which build the numbers come from
//!
//! The report's numbers are from a RELEASE build, because a frame time out
//! of an unoptimised build is not the game's frame time. In this workspace
//! that is a smaller distinction than usual: `[profile.test]` compiles test
//! binaries at `opt-level = 2` even for a plain `cargo test`, and the same
//! drive measured 59.9 us there against 54.1 us under `--release`
//! (2026-08-24). Run it:
//!
//! ```text
//! CARGO_TARGET_DIR=target/frame cargo test --release -p freight-fate \
//!     --test it -- frame_time::bench --ignored --nocapture --test-threads 1
//! ```

use std::time::Instant;

use ff_core::models::jobs::{cargo_type, Job};
use ff_core::models::profile::Profile;

use freight_fate::app::testing::{FakeClock, TestApp};
use freight_fate::app::{SharedState, FPS};
use freight_fate::states::base::{Key, Mods};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::DRIVE_PHASE_DELIVERY;

/// One frame of the fixed step the loop runs at (`app::FPS` is 60).
const DT: f64 = 1.0 / FPS as f64;

/// What one frame is allowed to cost end to end if the loop is to hold the
/// rate it targets: `FrameClock::tick(FPS)` sleeps out the remainder of
/// this and no longer, so a frame that overruns it is a dropped frame.
const BUDGET_US: f64 = 1_000_000.0 / FPS as f64; // 16 666.7 us at 60 Hz

/// The drive, pinned. Any seed would do; this one is the transcript
/// suite's, so a spoken oddity seen here can be reproduced there.
const TRIP_SEED: i64 = 0;
/// Noon: full daylight, no dusk transition mid-run.
const START_HOUR: f64 = 12.0;
/// I-70 west out of Denver. Four legs, 246 miles, every one enriched.
const ROUTE: [&str; 5] = [
    "Denver",
    "Silverthorne",
    "Edwards",
    "Glenwood Springs",
    "Grand Junction",
];
/// A loaded van, not a bobtail: weight is what makes the grades work.
const CARGO: &str = "general";
const TONS: f64 = 18.0;

/// Frames thrown away before timing starts. The first ticks of a drive do
/// one-off work no later frame repeats -- the departure chain, the first
/// zone and corridor lookups, the first music selection.
const WARMUP: usize = 600;

fn env_usize(name: &str, fallback: usize) -> usize {
    std::env::var(name)
        .ok()
        .and_then(|v| v.trim().parse().ok())
        .unwrap_or(fallback)
}

// -- the rig ---------------------------------------------------------------------------

/// A drive on the app's own state stack, ready to be ticked frame by frame.
struct DriveRig {
    app: TestApp,
    clock: FakeClock,
    drive: SharedState,
}

impl DriveRig {
    fn mountain_run() -> DriveRig {
        let mut app = TestApp::new();
        // The pacer must see simulated time, not the wall clock this loop
        // outruns; see the module note.
        let clock = app.fake_pacer_clock();
        app.ctx.profile = Some(Profile::named_in("Frame Bench", ROUTE[0]));
        let route = app
            .ctx
            .world
            .route_from_cities(&ROUTE)
            .expect("Denver to Grand Junction over I-70 is a supported chain");
        let miles = route.miles().round();
        let cargo = cargo_type(CARGO).expect("general freight is in the cargo catalog");
        let destination = ROUTE[ROUTE.len() - 1];
        let mut job = Job::new(
            cargo,
            TONS,
            ROUTE[0],
            &format!("{} Terminal", ROUTE[0]),
            destination,
            miles,
            (miles * 10.0).max(500.0),
            (miles / 25.0).max(2.0),
        );
        job.destination_location = format!("{destination} Terminal");
        let mut drive = DrivingState::new(
            &mut app.ctx,
            job,
            route,
            Some(TRIP_SEED),
            DRIVE_PHASE_DELIVERY,
            Some(START_HOUR),
        );
        drive.trip.event_breather.set_clock(clock.boxed());
        // A truck that can move: engine running, tanks charged, parking
        // brake off, box on automatic. A parked truck exercises a fraction
        // of the frame and would flatter every number here.
        drive.trip.truck.set_air_ready(false);
        drive.trip.truck.start_engine();
        drive.trip.truck.transmission.automatic = true;
        drive.trip.truck.parking_brake = false;
        app.push_state(drive);
        let handle = app.state().expect("the drive is on the stack");
        DriveRig {
            app,
            clock,
            drive: handle,
        }
    }

    fn read<R>(&self, f: impl FnOnce(&DrivingState) -> R) -> R {
        let state = self.drive.borrow();
        let drive = state
            .as_any()
            .downcast_ref::<DrivingState>()
            .expect("the handle is the drive");
        f(drive)
    }

    /// The same, for the reads that memoise -- `Trip::speed_limit_at` caches
    /// the zone it landed in, so it takes `&mut self`.
    fn read_mut<R>(&self, f: impl FnOnce(&mut DrivingState) -> R) -> R {
        let mut state = self.drive.borrow_mut();
        let drive = state
            .as_any_mut()
            .downcast_mut::<DrivingState>()
            .expect("the handle is the drive");
        f(drive)
    }

    /// A driver who keeps the posted limit: throttle below it, brake above.
    ///
    /// Deliberately at the INPUT layer rather than by writing the truck's
    /// pedals, so the pedal ramp, the latch logic and the assists all run
    /// the way they do for a player. Holding the accelerator flat instead
    /// (what `bench_drive.rs` does) drives the whole route over the limit,
    /// which never leaves a zone in a state the zone code has to handle.
    /// The band around the limit is not decoration, and neither end of it
    /// is free. Braking the moment the truck is a hair over is riding the
    /// brakes: on the I-70 descents the compressor loses, the low-air
    /// warning comes at 60 psi and the spring brakes park the truck. Let
    /// it run further over instead and the troopers pull it over for
    /// speeding, which ends the drive just as dead. Four over and three
    /// under is the band that got furthest -- the run ends at mile 63.5 on
    /// low air either way, which is the air system working correctly on a
    /// driver that is a throttle and a brake and nothing else. A player
    /// would have used the retarder and gone on; the report says where and
    /// why the drive stopped so nobody mistakes it for the road running
    /// out.
    fn steer(&mut self) {
        let (limit_mph, speed_mph) = self.read_mut(|drive| {
            let mile = drive.trip.position_mi;
            let (limit, _reason) = drive.trip.speed_limit_at(mile);
            (limit, drive.trip.truck.speed_mph())
        });
        let target = limit_mph.max(25.0);
        let (throttle, brake) = if speed_mph > target + 4.0 {
            (false, true)
        } else if speed_mph < target - 3.0 {
            (true, false)
        } else {
            // In the band: hold whatever pedal is already down unless it is
            // the brake, which comes off so the tanks can recover.
            (self.app.ctx.input.is_pressed(Key::Up), false)
        };
        if throttle {
            self.app.ctx.input.press(Key::Up, Mods::NONE);
        } else {
            self.app.ctx.input.release(Key::Up, Mods::NONE);
        }
        if brake {
            self.app.ctx.input.press(Key::Down, Mods::NONE);
        } else {
            self.app.ctx.input.release(Key::Down, Mods::NONE);
        }
    }

    /// Whether the drive is still the screen being ticked. Once the truck
    /// reaches the gate the drive pops and the frames after it are a menu,
    /// not a drive.
    fn still_driving(&self) -> bool {
        self.app.drive_in_progress()
    }

    fn spoken_so_far(&self) -> usize {
        self.app.speech().entries().len()
    }

    fn speed_mph(&self) -> f64 {
        self.read(|drive| drive.trip.truck.speed_mph())
    }

    /// The tail of the transcript: what the drive was saying when it ended.
    fn last_lines(&self) -> Vec<String> {
        let lines = self.app.speech().transcript_lines();
        lines.iter().rev().take(5).rev().cloned().collect()
    }
}

/// How long the truck may sit still before a run gives up on it.
///
/// The synthetic driver in [`DriveRig::steer`] is a throttle and a brake,
/// not a player: it cannot answer a menu, take a turn off the highway or
/// check in anywhere, so somewhere on a long route it will eventually stop
/// at something a person would have handled. Every frame after that is a
/// PARKED truck, which is a fraction of the work of a driven one and would
/// quietly drag the whole distribution down. Ten seconds of frames is far
/// longer than any pause inside a normal drive (a hazard, a downshift, a
/// crawl through a zone) and short enough that the parked tail cannot move
/// the numbers.
const STALL_FRAMES: usize = 600;
/// Under this the truck is stopped, not merely slow.
const STOPPED_MPH: f64 = 0.5;

// -- statistics ------------------------------------------------------------------------

/// What one frame cost and what the drive was doing while it cost it.
#[derive(Clone, Copy)]
struct Frame {
    index: usize,
    total_us: f64,
    tick_us: f64,
    lines_us: f64,
    leg: usize,
    /// Lines the frame handed to speech. A frame that speaks does work no
    /// silent frame does: the ladder, the pacer, the duck.
    spoke: usize,
    /// How deep the state stack was. Anything above one means the drive
    /// pushed a screen (a stop, a check, an arrival) and the frame ticked
    /// that instead of the road.
    depth: usize,
}

struct Stats {
    n: usize,
    mean_us: f64,
    median_us: f64,
    p95_us: f64,
    p99_us: f64,
    max_us: f64,
    total_ms: f64,
}

fn stats(samples: &[f64]) -> Stats {
    assert!(!samples.is_empty(), "no frames were timed");
    let mut sorted = samples.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).expect("frame times are finite"));
    let n = sorted.len();
    let total: f64 = samples.iter().sum();
    // Nearest-rank percentile, the rule `tools/bench_drive.py` uses, so the
    // two sides' percentiles mean the same thing.
    let rank = |q: f64| {
        let idx = ((q * n as f64).ceil() as usize).saturating_sub(1);
        sorted[idx.min(n - 1)]
    };
    Stats {
        n,
        mean_us: total / n as f64,
        median_us: rank(0.5),
        p95_us: rank(0.95),
        p99_us: rank(0.99),
        max_us: sorted[n - 1],
        total_ms: total / 1000.0,
    }
}

fn mean_of(frames: &[Frame], keep: impl Fn(&Frame) -> bool) -> Option<(usize, f64)> {
    let picked: Vec<f64> = frames
        .iter()
        .filter(|f| keep(f))
        .map(|f| f.total_us)
        .collect();
    if picked.is_empty() {
        return None;
    }
    let n = picked.len();
    Some((n, picked.iter().sum::<f64>() / n as f64))
}

// -- the runs --------------------------------------------------------------------------

struct Run {
    frames: Vec<Frame>,
    end_mi: f64,
    total_mi: f64,
    end_speed_mph: f64,
    game_minutes: f64,
    legs_covered: usize,
    spoken: usize,
    /// The last few lines the drive spoke, so a run that ends early says
    /// what it ended on instead of leaving a reader to guess.
    last_lines: Vec<String>,
    pushes: usize,
    finished: bool,
}

/// Drive the route through the whole per-frame path (`App::tick` plus the
/// line build `App::render` would hand the window), timing each half.
fn drive_full_frames(warmup: usize, max_frames: usize) -> Run {
    let mut rig = DriveRig::mountain_run();
    for _ in 0..warmup {
        rig.steer();
        rig.clock.advance(DT);
        rig.app.tick(DT);
        std::hint::black_box(rig.app.visible_lines());
        if !rig.still_driving() {
            break;
        }
    }

    let mut frames = Vec::with_capacity(max_frames);
    let mut said = rig.spoken_so_far();
    let mut pushes = 0usize;
    let mut finished = false;
    let mut stopped_for = 0usize;
    for index in 0..max_frames {
        if !rig.still_driving() {
            finished = true;
            break;
        }
        if rig.speed_mph() < STOPPED_MPH {
            stopped_for += 1;
            if stopped_for > STALL_FRAMES {
                break;
            }
        } else {
            stopped_for = 0;
        }
        rig.steer();
        rig.clock.advance(DT);

        let t = Instant::now();
        rig.app.tick(DT);
        let tick_us = t.elapsed().as_secs_f64() * 1e6;

        let t = Instant::now();
        let lines = rig.app.visible_lines();
        let lines_us = t.elapsed().as_secs_f64() * 1e6;
        std::hint::black_box(lines);

        let now_said = rig.spoken_so_far();
        let depth = rig.app.ctx.stack_len();
        if depth > 1 {
            pushes += 1;
        }
        frames.push(Frame {
            index,
            total_us: tick_us + lines_us,
            tick_us,
            lines_us,
            leg: rig.read(|drive| drive.trip.current_leg_index()),
            spoke: now_said - said,
            depth,
        });
        said = now_said;
    }

    let (end_mi, total_mi, end_speed_mph, game_minutes, legs_covered) = rig.read(|drive| {
        (
            drive.trip.position_mi,
            drive.trip.total_miles(),
            drive.trip.truck.speed_mph(),
            drive.trip.game_minutes,
            drive.trip.current_leg_index() + 1,
        )
    });
    let spoken = rig.spoken_so_far();
    let last_lines = rig.last_lines();
    Run {
        frames,
        end_mi,
        total_mi,
        end_speed_mph,
        game_minutes,
        legs_covered,
        spoken,
        last_lines,
        pushes,
        finished,
    }
}

/// The same drive with only the sim stepped: `DrivingState::update_frame`
/// and nothing else in the frame.
///
/// Run separately rather than nested, because the sim runs INSIDE
/// `App::tick` and a timer cannot straddle it without instrumenting the
/// game. The two runs are the same seeded drive with the same steering, so
/// subtracting one mean from the other is a fair split as long as the two
/// end at the same mile -- which the report prints so a reader can check
/// rather than trust.
fn drive_sim_only(warmup: usize, max_frames: usize) -> Run {
    let mut rig = DriveRig::mountain_run();
    let step = |rig: &mut DriveRig| {
        rig.steer();
        rig.clock.advance(DT);
        let state = rig.drive.clone();
        let mut borrowed = state.borrow_mut();
        let drive = borrowed
            .as_any_mut()
            .downcast_mut::<DrivingState>()
            .expect("the handle is the drive");
        let t = Instant::now();
        drive.update_frame(&mut rig.app.ctx, DT);
        t.elapsed().as_secs_f64() * 1e6
    };
    for _ in 0..warmup {
        step(&mut rig);
    }
    let mut frames = Vec::with_capacity(max_frames);
    let mut said = rig.spoken_so_far();
    let mut finished = false;
    let mut stopped_for = 0usize;
    for index in 0..max_frames {
        if rig.read(|drive| drive.trip.finished) {
            finished = true;
            break;
        }
        if rig.speed_mph() < STOPPED_MPH {
            stopped_for += 1;
            if stopped_for > STALL_FRAMES {
                break;
            }
        } else {
            stopped_for = 0;
        }
        let us = step(&mut rig);
        let now_said = rig.spoken_so_far();
        frames.push(Frame {
            index,
            total_us: us,
            tick_us: us,
            lines_us: 0.0,
            leg: rig.read(|drive| drive.trip.current_leg_index()),
            spoke: now_said - said,
            depth: 1,
        });
        said = now_said;
    }
    let (end_mi, total_mi, end_speed_mph, game_minutes, legs_covered) = rig.read(|drive| {
        (
            drive.trip.position_mi,
            drive.trip.total_miles(),
            drive.trip.truck.speed_mph(),
            drive.trip.game_minutes,
            drive.trip.current_leg_index() + 1,
        )
    });
    let spoken = rig.spoken_so_far();
    let last_lines = rig.last_lines();
    Run {
        frames,
        end_mi,
        total_mi,
        end_speed_mph,
        game_minutes,
        legs_covered,
        spoken,
        last_lines,
        pushes: 0,
        finished,
    }
}

// -- inside App::tick ------------------------------------------------------------------

/// Every phase `App::tick` runs, timed one at a time.
#[derive(Default)]
struct Phases {
    controller: Vec<f64>,
    speech_poll: Vec<f64>,
    cloud: Vec<f64>,
    audio: Vec<f64>,
    duck: Vec<f64>,
    sim: Vec<f64>,
    presence_build: Vec<f64>,
    online_build: Vec<f64>,
    presence_push: Vec<f64>,
    online_push: Vec<f64>,
}

/// The same drive again, stepping `App::tick`'s phases by hand so each can
/// be timed on its own.
///
/// This MIRRORS `App::tick` and has to be kept in step with it: a phase
/// added there and not here is a phase this report silently omits. It is
/// the only way to get inside the tick without putting timers in the game,
/// which a bench must not do. What it leaves out is the controller-repeat
/// dispatch (a drive declines `wants_controller_repeat`) and the
/// disconnect branch, neither of which fires on a keyboard drive.
fn drive_tick_phases(warmup: usize, max_frames: usize) -> (Phases, f64) {
    let mut rig = DriveRig::mountain_run();
    let mut p = Phases::default();
    let step = |rig: &mut DriveRig, p: &mut Phases, record: bool| {
        rig.steer();
        rig.clock.advance(DT);
        let t = Instant::now();
        let repeats = rig.app.ctx.controller.tick(DT);
        std::hint::black_box(repeats);
        let controller = t.elapsed().as_secs_f64() * 1e6;

        let t = Instant::now();
        rig.app.ctx.speech.poll(DT);
        std::hint::black_box(rig.app.ctx.controller.take_disconnect());
        let speech_poll = t.elapsed().as_secs_f64() * 1e6;

        let t = Instant::now();
        let notices = rig.app.ctx.services.cloud.take_announcements();
        std::hint::black_box(notices);
        let cloud = t.elapsed().as_secs_f64() * 1e6;

        let t = Instant::now();
        rig.app.ctx.audio.update(DT);
        let audio = t.elapsed().as_secs_f64() * 1e6;

        let t = Instant::now();
        rig.app.ctx.update_speech_duck();
        let duck = t.elapsed().as_secs_f64() * 1e6;

        let state = rig.drive.clone();
        let t = Instant::now();
        {
            let mut borrowed = state.borrow_mut();
            let drive = borrowed
                .as_any_mut()
                .downcast_mut::<DrivingState>()
                .expect("the handle is the drive");
            drive.update_frame(&mut rig.app.ctx, DT);
        }
        rig.app.ctx.run_deferred();
        let sim = t.elapsed().as_secs_f64() * 1e6;

        let (presence, online, presence_build, online_build) = {
            let borrowed = state.borrow();
            let t = Instant::now();
            let presence = borrowed.presence(&rig.app.ctx);
            let presence_build = t.elapsed().as_secs_f64() * 1e6;
            let t = Instant::now();
            let online = borrowed.online_presence(&rig.app.ctx);
            let online_build = t.elapsed().as_secs_f64() * 1e6;
            (presence, online, presence_build, online_build)
        };
        let t = Instant::now();
        rig.app.ctx.services.presence.update(presence);
        let presence_push = t.elapsed().as_secs_f64() * 1e6;
        let t = Instant::now();
        rig.app.ctx.services.online.update(online);
        let online_push = t.elapsed().as_secs_f64() * 1e6;

        if record {
            p.controller.push(controller);
            p.speech_poll.push(speech_poll);
            p.cloud.push(cloud);
            p.audio.push(audio);
            p.duck.push(duck);
            p.sim.push(sim);
            p.presence_build.push(presence_build);
            p.online_build.push(online_build);
            p.presence_push.push(presence_push);
            p.online_push.push(online_push);
        }
    };
    for _ in 0..warmup {
        step(&mut rig, &mut p, false);
    }
    let mut stopped_for = 0usize;
    for _ in 0..max_frames {
        if rig.read(|drive| drive.trip.finished) {
            break;
        }
        if rig.speed_mph() < STOPPED_MPH {
            stopped_for += 1;
            if stopped_for > STALL_FRAMES {
                break;
            }
        } else {
            stopped_for = 0;
        }
        step(&mut rig, &mut p, true);
    }
    let end_mi = rig.read(|drive| drive.trip.position_mi);
    (p, end_mi)
}

fn phase_line(name: &str, samples: &[f64], frame_mean: f64) {
    if samples.is_empty() {
        return;
    }
    let s = stats(samples);
    println!(
        "  {name:<22} mean {:9.2}  median {:9.2}  p99 {:9.2}  {:5.1}%",
        s.mean_us,
        s.median_us,
        s.p99_us,
        100.0 * s.mean_us / frame_mean
    );
}

// -- the report ------------------------------------------------------------------------

fn report(title: &str, run: &Run) -> Stats {
    let totals: Vec<f64> = run.frames.iter().map(|f| f.total_us).collect();
    let s = stats(&totals);
    println!("\n{title}");
    println!("  frames timed       {}", s.n);
    println!(
        "  drove              {:.1} of {:.0} mi ({} legs), {:.0} game minutes{}",
        run.end_mi,
        run.total_mi,
        run.legs_covered,
        run.game_minutes,
        if run.finished {
            ", reached the gate"
        } else {
            ""
        }
    );
    println!("  end speed          {:.1} mph", run.end_speed_mph);
    println!("  lines spoken       {}", run.spoken);
    if !run.finished {
        println!("  ended on           {}", run.last_lines.join(" | "));
    }
    println!("  frames off-road    {} (a screen was pushed)", run.pushes);
    println!("  frame mean         {:.2} us", s.mean_us);
    println!("  frame median       {:.2} us", s.median_us);
    println!("  frame p95          {:.2} us", s.p95_us);
    println!("  frame p99          {:.2} us", s.p99_us);
    println!("  frame max          {:.2} us", s.max_us);
    println!("  timed total        {:.1} ms", s.total_ms);
    println!(
        "  sustainable rate   {:.0} fps if nothing else ran ({:.3}% of the \
         {:.0} us budget at the mean, {:.2}% at p99)",
        1e6 / s.mean_us,
        100.0 * s.mean_us / BUDGET_US,
        BUDGET_US,
        100.0 * s.p99_us / BUDGET_US,
    );
    let over = run.frames.iter().filter(|f| f.total_us > BUDGET_US).count();
    println!("  frames over budget {over} of {}", s.n);
    s
}

#[test]
#[ignore = "benchmark: run with --release --ignored --nocapture --test-threads 1"]
fn bench_frame_time_on_a_mountain_route() {
    let warmup = env_usize("FF_FRAME_WARMUP", WARMUP);
    // High enough to reach Grand Junction; the run stops itself at the gate.
    let max_frames = env_usize("FF_FRAME_FRAMES", 200_000);

    if cfg!(debug_assertions) {
        println!(
            "WARNING: this is a DEBUG build (opt-level 0). The numbers below \
             are not the game's frame time. Re-run with --release."
        );
    }

    let t0 = Instant::now();
    let full = drive_full_frames(warmup, max_frames);
    let full_wall = t0.elapsed().as_secs_f64();
    let full_stats = report("full frame (App::tick + the line build)", &full);
    println!("  wall clock         {full_wall:.1} s for the whole drive");

    // -- phase attribution -------------------------------------------------------------
    let tick: Vec<f64> = full.frames.iter().map(|f| f.tick_us).collect();
    let lines: Vec<f64> = full.frames.iter().map(|f| f.lines_us).collect();
    let tick_s = stats(&tick);
    let lines_s = stats(&lines);

    let sim = drive_sim_only(warmup, max_frames);
    let sim_stats = report("sim only (DrivingState::update_frame)", &sim);

    let overhead = (tick_s.mean_us - sim_stats.mean_us).max(0.0);
    println!("\nwhere the frame goes (means, us)");
    println!(
        "  sim step           {:8.2}  {:5.1}%",
        sim_stats.mean_us,
        100.0 * sim_stats.mean_us / full_stats.mean_us
    );
    println!(
        "  rest of App::tick  {overhead:8.2}  {:5.1}%  (speech poll, audio \
         fades, the duck, controller, presence, cloud notices)",
        100.0 * overhead / full_stats.mean_us
    );
    println!(
        "  line build         {:8.2}  {:5.1}%  (the 18 rows App::render \
         hands the window)",
        lines_s.mean_us,
        100.0 * lines_s.mean_us / full_stats.mean_us
    );
    println!("  line build p99     {:8.2}", lines_s.p99_us);
    println!(
        "  cross-check        the two runs ended at {:.1} mi and {:.1} mi; \
         the split is fair only where those agree",
        full.end_mi, sim.end_mi
    );

    // -- inside the tick ----------------------------------------------------------------
    let (phases, phase_end_mi) = drive_tick_phases(warmup, max_frames);
    println!("\ninside App::tick, phase by phase (us per frame)");
    phase_line("controller", &phases.controller, full_stats.mean_us);
    phase_line("speech poll", &phases.speech_poll, full_stats.mean_us);
    phase_line("cloud notices", &phases.cloud, full_stats.mean_us);
    phase_line("audio", &phases.audio, full_stats.mean_us);
    phase_line("speech duck", &phases.duck, full_stats.mean_us);
    phase_line("state update (sim)", &phases.sim, full_stats.mean_us);
    phase_line(
        "presence: build",
        &phases.presence_build,
        full_stats.mean_us,
    );
    phase_line(
        "presence: hand off",
        &phases.presence_push,
        full_stats.mean_us,
    );
    phase_line("online: build", &phases.online_build, full_stats.mean_us);
    phase_line("online: hand off", &phases.online_push, full_stats.mean_us);
    println!("  (this pass ended at {phase_end_mi:.1} mi)");

    // Does any phase get more expensive the longer the drive runs? A frame
    // cost that climbs with time driven is a different bug from a frame
    // cost that is merely high, and only one of them gets worse on a long
    // haul.
    let drift = |name: &str, samples: &[f64]| {
        if samples.len() < 200 {
            return;
        }
        let tenth = samples.len() / 10;
        let first: f64 = samples[..tenth].iter().sum::<f64>() / tenth as f64;
        let last: f64 = samples[samples.len() - tenth..].iter().sum::<f64>() / tenth as f64;
        println!(
            "  {name:<22} first tenth {first:9.2} us -> last tenth {last:9.2} us  \
             ({:.2}x)",
            if first > 0.0 { last / first } else { 0.0 }
        );
    };
    println!("\ndoes it get worse as the drive goes on?");
    drift("state update (sim)", &phases.sim);
    drift("presence: build", &phases.presence_build);
    drift("presence: hand off", &phases.presence_push);
    drift("online: build", &phases.online_build);
    drift("online: hand off", &phases.online_push);

    // -- what makes a frame expensive ---------------------------------------------------
    println!("\nwhat a slow frame was doing");
    if let Some((n, mean)) = mean_of(&full.frames, |f| f.spoke > 0) {
        println!("  frames that spoke      {n:6}  mean {mean:8.2} us");
    }
    if let Some((n, mean)) = mean_of(&full.frames, |f| f.spoke == 0) {
        println!("  frames that did not    {n:6}  mean {mean:8.2} us");
    }
    let mut leg_change = vec![false; full.frames.len()];
    for (flag, pair) in leg_change.iter_mut().skip(1).zip(full.frames.windows(2)) {
        *flag = pair[1].leg != pair[0].leg;
    }
    if let Some((n, mean)) = mean_of(&full.frames, |f| {
        leg_change[f.index.min(leg_change.len() - 1)]
    }) {
        println!("  frames changing leg    {n:6}  mean {mean:8.2} us");
    }
    if let Some((n, mean)) = mean_of(&full.frames, |f| f.depth > 1) {
        println!("  frames on a pushed screen {n:3}  mean {mean:8.2} us");
    }

    let mut worst = full.frames.clone();
    worst.sort_by(|a, b| b.total_us.partial_cmp(&a.total_us).expect("finite"));
    println!("\n  the twelve slowest frames");
    println!(
        "    {:>8}  {:>10}  {:>9}  {:>5}  {:>5}  {:>5}",
        "frame", "total us", "lines us", "leg", "said", "depth"
    );
    for f in worst.iter().take(12) {
        println!(
            "    {:>8}  {:>10.1}  {:>9.1}  {:>5}  {:>5}  {:>5}",
            f.index, f.total_us, f.lines_us, f.leg, f.spoke, f.depth
        );
    }
}

// -- the gate --------------------------------------------------------------------------

/// Frames each gate times. Enough that p99 has a real tail (its rank is the
/// 20th-slowest frame) and cheap enough to sit in the ordinary suite: about
/// a second per gate, release or debug.
const GATE_FRAMES: usize = 2_000;
const GATE_WARMUP: usize = 300;

/// Ground the gates must cover before their numbers mean anything.
///
/// Both would pass trivially on a parked truck: a frame that simulates
/// nothing is cheap, and its presence string cheaper still. So each checks
/// the drive went somewhere first. From a standing start, 2 300 frames of
/// this route put the truck about 2.7 miles along; a mile is comfortably
/// below that and far above anything a truck that never released its
/// brakes could reach.
const MOVED_MI: f64 = 1.0;

/// The share of one 60 Hz frame the driven frame is allowed at p99.
///
/// Derived, not fitted to this machine:
///
/// * The loop runs at `app::FPS` = 60, and `FrameClock::tick` sleeps out
///   only the remainder of `1/FPS`. So the whole frame budget is
///   [`BUDGET_US`] = 16 667 us, and anything over it is a dropped frame.
/// * This test measures the headless frame. A player's frame also carries
///   the SDL event pump and the window render, BASS mixing its channels,
///   and Prism handing text to a screen reader -- none of which exist here.
///   The measured part therefore cannot be allowed the whole budget.
/// * What it may have is set by the slowest hardware the game has to hold
///   60 fps on, not by what this desktop happens to do. Single-thread
///   throughput across the machines a Windows player plausibly runs spans
///   roughly four to one between a current desktop part and a low-end
///   mobile one (PassMark single-thread ratings, same generation). Giving
///   the measured frame a quarter of the budget here is giving it the whole
///   budget on a machine four times slower, which is the floor of support.
///
/// So: p99 <= 16 667 / 4 = 4 167 us, in release and in debug alike.
/// `[profile.test]` compiles test binaries at `opt-level = 2` even for a
/// plain `cargo test`, which is what CI runs, and the two measure the same
/// drive within a tenth (59.9 us against 54.1 us, 2026-08-24). There is no
/// second, looser number for an unoptimised run because there is no
/// meaningfully slower run to give one to; and if `[profile.test]` ever
/// went back to `opt-level = 0`, this ceiling still sits about seventy
/// times over what the frame costs.
///
/// This is a CATASTROPHE gate, not a drift gate, and the margin is large on
/// purpose: a tighter wall-clock number on a shared CI box fails when a
/// neighbouring job runs, and a perf test that fails for that reason is a
/// perf test somebody deletes.
/// [`a_frames_bookkeeping_never_out_costs_its_simulation`] is the tight
/// half of the pair, and the one that would have caught the bug this file
/// was written to find. Drift is for the report, not for the gate.
const BUDGET_SHARE: f64 = 0.25;

#[test]
fn a_driven_frame_stays_well_inside_the_sixty_hertz_budget() {
    let run = drive_full_frames(GATE_WARMUP, GATE_FRAMES);
    let totals: Vec<f64> = run.frames.iter().map(|f| f.total_us).collect();
    let s = stats(&totals);

    // The gate is only a gate if the frames it timed were a drive. A change
    // that parks the truck (or ends the leg early) would make every number
    // below meaninglessly small and the assertion would still pass.
    assert!(
        run.end_mi > MOVED_MI,
        "the bench drive covered only {:.2} mi in {} frames -- it was not \
         driving, so its frame times measure nothing",
        run.end_mi,
        s.n
    );
    assert!(
        run.spoken > 0,
        "the bench drive spoke nothing in {} frames; the speech half of the \
         frame went unmeasured",
        s.n
    );
    assert_eq!(s.n, GATE_FRAMES, "the drive ended before the gate's frames");

    let ceiling = BUDGET_US * BUDGET_SHARE;
    println!(
        "driven frame: mean {:.2} us, median {:.2} us, p95 {:.2} us, p99 \
         {:.2} us, max {:.2} us over {} frames ({:.1} mi); ceiling {:.0} us \
         ({:.0}% of the {:.0} us budget, {} build)",
        s.mean_us,
        s.median_us,
        s.p95_us,
        s.p99_us,
        s.max_us,
        s.n,
        run.end_mi,
        ceiling,
        BUDGET_SHARE * 100.0,
        BUDGET_US,
        if cfg!(debug_assertions) {
            "debug"
        } else {
            "release"
        },
    );
    assert!(
        s.p99_us < ceiling,
        "a driven frame's p99 is {:.1} us, past the {:.1} us this build is \
         allowed ({:.0}% of the {:.0} us frame at {FPS} fps). The frame got \
         an order of magnitude more expensive; see \
         frame_time::bench_frame_time_on_a_mountain_route for where it went.",
        s.p99_us,
        ceiling,
        BUDGET_SHARE * 100.0,
        BUDGET_US,
    );
}

/// The gate with real teeth, and the one that does not care how fast the
/// machine is.
///
/// Both sides of the comparison are measured in the same process, in the
/// same frames, so a loaded CI box slows them together and the RATIO holds.
/// That is what makes it safe to state tightly where a wall-clock number
/// cannot be.
///
/// The rule it enforces is a design one, not a measurement: **building the
/// status text for a presence panel must never cost more than simulating
/// the truck.** The sim is the frame's work -- physics, the corridor, the
/// traffic bubble, the hazards, the speech ladder. Presence is a short
/// string handed to Discord and to the drivers board, both of which
/// throttle to seconds. If the string costs more than the truck, something
/// in the builder is doing work it has no business doing per frame.
///
/// That is exactly the shape of the bug this file found: the online
/// presence builder was cloning the whole radio catalog (757 stations plus
/// the identity map) every frame to read one station name, at 2 395 us a
/// frame against the sim's 84 -- twenty-eight times over this line, and
/// ninety-seven per cent of the frame. The absolute gate above did not
/// notice, because 2.4 ms still fits in a 60 Hz frame. This one fails at
/// 1.0x, so it would have failed on the first frame.
#[test]
fn a_frames_bookkeeping_never_out_costs_its_simulation() {
    let (phases, end_mi) = drive_tick_phases(GATE_WARMUP, GATE_FRAMES);
    assert!(
        end_mi > MOVED_MI,
        "the bench drive covered only {end_mi:.2} mi -- it was not driving"
    );
    let sim = stats(&phases.sim);
    let presence = stats(&phases.presence_build);
    let online = stats(&phases.online_build);
    println!(
        "per frame: sim {:.2} us, Discord presence {:.2} us ({:.3}x the sim), \
         drivers board {:.2} us ({:.3}x the sim)",
        sim.mean_us,
        presence.mean_us,
        presence.mean_us / sim.mean_us,
        online.mean_us,
        online.mean_us / sim.mean_us,
    );
    for (what, built) in [
        ("Discord presence", &presence),
        ("the drivers board line", &online),
    ] {
        assert!(
            built.mean_us < sim.mean_us,
            "building {what} costs {:.2} us a frame against the simulation's \
             {:.2} us ({:.1}x). A presence string is throttled to seconds and \
             must not out-cost the truck; something in that builder is doing \
             per-frame work it does not need to. Run \
             frame_time::bench_frame_time_on_a_mountain_route for the \
             breakdown.",
            built.mean_us,
            sim.mean_us,
            built.mean_us / sim.mean_us,
        );
    }
}
