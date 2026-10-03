//! The rig, the runs and the statistics behind the gates and the bench in
//! `main.rs`; see that file for what is measured and why.

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
pub(super) struct Frame {
    pub(super) index: usize,
    pub(super) total_us: f64,
    pub(super) tick_us: f64,
    pub(super) lines_us: f64,
    pub(super) leg: usize,
    /// Lines the frame handed to speech. A frame that speaks does work no
    /// silent frame does: the ladder, the pacer, the duck.
    pub(super) spoke: usize,
    /// How deep the state stack was. Anything above one means the drive
    /// pushed a screen (a stop, a check, an arrival) and the frame ticked
    /// that instead of the road.
    pub(super) depth: usize,
}

pub(super) struct Stats {
    pub(super) n: usize,
    pub(super) mean_us: f64,
    pub(super) median_us: f64,
    pub(super) p95_us: f64,
    pub(super) p99_us: f64,
    pub(super) max_us: f64,
    pub(super) total_ms: f64,
}

pub(super) fn stats(samples: &[f64]) -> Stats {
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

pub(super) fn mean_of(frames: &[Frame], keep: impl Fn(&Frame) -> bool) -> Option<(usize, f64)> {
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

pub(super) struct Run {
    pub(super) frames: Vec<Frame>,
    pub(super) end_mi: f64,
    pub(super) total_mi: f64,
    pub(super) end_speed_mph: f64,
    pub(super) game_minutes: f64,
    pub(super) legs_covered: usize,
    pub(super) spoken: usize,
    /// The last few lines the drive spoke, so a run that ends early says
    /// what it ended on instead of leaving a reader to guess.
    pub(super) last_lines: Vec<String>,
    pub(super) pushes: usize,
    pub(super) finished: bool,
}

/// Drive the route through the whole per-frame path (`App::tick` plus the
/// line build `App::render` would hand the window), timing each half.
pub(super) fn drive_full_frames(warmup: usize, max_frames: usize) -> Run {
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
pub(super) fn drive_sim_only(warmup: usize, max_frames: usize) -> Run {
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
pub(super) struct Phases {
    pub(super) controller: Vec<f64>,
    pub(super) speech_poll: Vec<f64>,
    pub(super) cloud: Vec<f64>,
    pub(super) audio: Vec<f64>,
    pub(super) duck: Vec<f64>,
    pub(super) sim: Vec<f64>,
    pub(super) presence_build: Vec<f64>,
    pub(super) online_build: Vec<f64>,
    pub(super) presence_push: Vec<f64>,
    pub(super) online_push: Vec<f64>,
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
pub(super) fn drive_tick_phases(warmup: usize, max_frames: usize) -> (Phases, f64) {
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

pub(super) fn phase_line(name: &str, samples: &[f64], frame_mean: f64) {
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
