//! `freightfate`: the game's entry point (`freight_fate/__main__.py`), plus
//! the drive tools that used to be separate Python scripts.
//!
//! Game switches: `--smoke` (boot, render five frames, exit 0 -- the CI build
//! check), `--headless` (no window, no speech), `--controller-diagnostics`
//! (the two-layer controller logger, see `controller::diagnostics`). Those
//! are parsed by `app::CliOptions` and handled by `app::main_with`.
//!
//! Tool switches, parsed here:
//!
//! * `--list-break-scenarios` -- name and one-line summary of every
//!   adversarial scenario (`tools/playtest_break.py --list`).
//! * `--break-scenario NAME` / `--break-battery` `[--transcript]` -- run one
//!   scenario, or all of them, and print the verdict table.
//! * `--playtest-sandbox` -- prepare (and with `--launch`, run the real game
//!   in) a data directory that cannot reach the owner's account
//!   (`tools/playtest_sandbox.py`).
//! * `--playtest-road --find FEATURE` -- start the real game already rolling
//!   at a named road feature (`tools/playtest_road.py`).
//!
//! # Why the tool parsing is here and not in `app::CliOptions`
//!
//! `CliOptions` lives in `app.rs`, which this task does not own. Rather than
//! reach into a file another port owns, the tool switches are recognised here
//! and everything unrecognised is handed on to `CliOptions::parse` exactly as
//! `tools/playtest_sandbox.py` handed its own leftovers to
//! `freight_fate.app.main`. A later change can fold these into `CliOptions`
//! without moving any behaviour.

use std::path::PathBuf;

use freight_fate::app::{self, App, CliOptions};
use freight_fate::playtest::{breaker, road, sandbox};
use freight_fate::speech::CaptureSpeech;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    std::process::exit(run(&args));
}

fn run(args: &[String]) -> i32 {
    if has(args, "--help") || has(args, "-h") || has(args, "/?") {
        print!("{USAGE}");
        return 0;
    }
    // An unrecognised switch used to fall through to `CliOptions::parse`, which
    // ignores what it does not know -- so `--help` LAUNCHED THE GAME. Someone
    // asking what the flags are gets a window and a main menu instead of an
    // answer, and on a machine already running a copy the single-instance
    // guard then refuses it for reasons that look unrelated. Say what is
    // wrong, print the usage, and exit non-zero.
    if let Some(unknown) = args.iter().find(|a| {
        a.starts_with('-')
            && !KNOWN_SWITCHES
                .iter()
                .any(|k| *k == a.as_str() || a.starts_with(&format!("{k}=")))
    }) {
        eprintln!("freightfate: unrecognised switch {unknown}\n");
        eprint!("{USAGE}");
        return 2;
    }
    if args.iter().any(|a| a == "--list-break-scenarios") {
        return list_break_scenarios();
    }
    if let Some(name) = flag_value(args, "--break-scenario") {
        return run_break(&[name], has(args, "--transcript"));
    }
    if has(args, "--break-battery") {
        let names: Vec<String> = breaker::scenario_names()
            .into_iter()
            .map(str::to_string)
            .collect();
        return run_break(&names, has(args, "--transcript"));
    }
    if has(args, "--playtest-sandbox") {
        return playtest_sandbox(args);
    }
    if has(args, "--playtest-road") {
        return playtest_road(args);
    }
    app::main_with(CliOptions::parse(args.iter().cloned()))
}

/// Every switch the binary answers to, for the unrecognised-switch check.
/// A new switch must be added here or it will be refused -- deliberately: a
/// silent fall-through is what made `--help` launch the game.
const KNOWN_SWITCHES: &[&str] = &[
    "--assists",
    "--at",
    "--break-battery",
    "--break-scenario",
    "--cargo",
    "--cargo-type",
    "--controller-diagnostics",
    "--cruise",
    "--curve-assist",
    "--descent",
    "--dir",
    "--find",
    "--from",
    "--headless",
    "--help",
    "--hour",
    "--lane-keeping",
    "--launch",
    "--lead",
    "--level",
    "--list-break-scenarios",
    "--log",
    "--max-advisory",
    "--max-miles",
    "--min-drop",
    "--min-pct",
    "--min-run",
    "--no-careers",
    "--no-cruise",
    "--no-sandbox",
    "--pick",
    "--planned-stop-assist",
    "--playtest-road",
    "--playtest-sandbox",
    "--predictive-cruise",
    "--print",
    "--reset",
    "--routes",
    "--sample",
    "--scan",
    "--seed",
    "--smoke",
    "--speed",
    "--to",
    "--transcript",
    "--transmission",
    "--trip-seed",
    "--verbosity",
    "--weather",
];

/// What `--help` prints. Kept in step with the module docs above.
const USAGE: &str = "freightfate -- Freight Fate

  freightfate                       play
  freightfate --smoke               boot, render five frames, exit (CI check)
  freightfate --headless            no window, no speech
  freightfate --controller-diagnostics
                                    log controller events, both layers

Drive tools:
  --playtest-road --find FEATURE    start already rolling at a road feature
                                    (downgrade, upgrade, zone, limit-drop,
                                    stop, scale, curve, interchange, toll,
                                    chain-law); --from/--to/--seed/--scan and
                                    the assist switches refine the search
  --playtest-sandbox [--launch]     a data directory that cannot reach the
                                    owner's account; --dir/--reset/--print
  --list-break-scenarios            name every adversarial scenario
  --break-scenario NAME             run one, --transcript to hear it
  --break-battery                   run them all and print the verdicts
  --log PATH                        session log for the watcher
";

// -- flag helpers ----------------------------------------------------------------------

fn has(args: &[String], name: &str) -> bool {
    args.iter().any(|a| a == name)
}

/// `--name value` or `--name=value`.
fn flag_value(args: &[String], name: &str) -> Option<String> {
    let prefix = format!("{name}=");
    for (i, arg) in args.iter().enumerate() {
        if let Some(value) = arg.strip_prefix(&prefix) {
            return Some(value.to_string());
        }
        if arg == name {
            return args.get(i + 1).cloned();
        }
    }
    None
}

fn flag_f64(args: &[String], name: &str) -> Option<f64> {
    flag_value(args, name).and_then(|v| v.parse().ok())
}

fn flag_i64(args: &[String], name: &str) -> Option<i64> {
    flag_value(args, name).and_then(|v| v.parse().ok())
}

fn flag_usize(args: &[String], name: &str) -> Option<usize> {
    flag_value(args, name).and_then(|v| v.parse().ok())
}

/// A `--name on|off` switch.
fn flag_on_off(args: &[String], name: &str) -> Option<bool> {
    flag_value(args, name).map(|v| v == "on")
}

// -- the adversarial battery -----------------------------------------------------------

fn list_break_scenarios() -> i32 {
    let scenarios = breaker::scenarios();
    let width = scenarios.iter().map(|s| s.name.len()).max().unwrap_or(0);
    for scenario in scenarios {
        println!("{:<width$}  {}", scenario.name, scenario.description);
    }
    0
}

fn run_break(names: &[String], transcript: bool) -> i32 {
    app::configure_logging();
    let known = breaker::scenario_names();
    let unknown: Vec<&str> = names
        .iter()
        .map(String::as_str)
        .filter(|name| !known.contains(name))
        .collect();
    if !unknown.is_empty() {
        eprintln!(
            "unknown scenario: {} (try --list-break-scenarios)",
            unknown.join(", ")
        );
        return 2;
    }
    let mut outcomes = Vec::new();
    for name in names {
        println!("running {name} ...");
        let Some(outcome) = breaker::run_scenario(name) else {
            continue;
        };
        for finding in &outcome.findings {
            let shown: String = finding.replace('\n', " ").chars().take(300).collect();
            println!("  [{}] {shown}", outcome.verdict.as_str());
        }
        if transcript {
            for line in &outcome.transcript {
                println!("    | {line}");
            }
        }
        outcomes.push(outcome);
    }
    breaker::print_summary(&outcomes);
    let errors = outcomes
        .iter()
        .filter(|o| o.verdict == breaker::Verdict::Error)
        .count();
    i32::from(errors > 0)
}

// -- the sandbox launcher ---------------------------------------------------------------

fn playtest_sandbox(args: &[String]) -> i32 {
    let dir = flag_value(args, "--dir")
        .map(PathBuf::from)
        .unwrap_or_else(sandbox::default_sandbox);
    let source = sandbox::real_saves();
    if let Err(e) = sandbox::prepare(
        &dir,
        has(args, "--reset"),
        !has(args, "--no-careers"),
        &source,
    ) {
        eprintln!("Could not prepare the sandbox: {e}");
        return 1;
    }
    println!("{}", sandbox::describe(&dir));
    if !sandbox::audit(&dir).is_empty() {
        // Refusing is the point. A sandbox that is only mostly isolated is
        // worse than no sandbox at all, because the operator stops watching.
        eprintln!("\nRefusing to launch: fix the above, or pass --reset.");
        return 1;
    }
    if has(args, "--print") {
        println!("\nFREIGHT_FATE_DATA_DIR={}", dir.display());
        return 0;
    }
    if !has(args, "--launch") {
        return 0;
    }
    let log_path = flag_value(args, "--log")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            ff_core::settings::game_root()
                .join("logs")
                .join("playtest-manual.log")
        });
    open_log(&log_path);
    println!("\nSession log: {}", log_path.display());
    let session = sandbox::open_session(&dir, &log_path);
    println!("Session file: {}", session.display());

    // Anything unrecognised is handed straight to the game -- `--smoke` above
    // all, which is how a sandbox launch gets tested without a person having
    // to sit through a window opening.
    let passthrough: Vec<String> = args
        .iter()
        .filter(|a| {
            !matches!(
                a.as_str(),
                "--playtest-sandbox" | "--reset" | "--no-careers" | "--launch" | "--print"
            ) && !a.starts_with("--dir")
                && !a.starts_with("--log")
        })
        .cloned()
        .collect();
    let code = app::main_with(CliOptions::parse(passthrough));
    sandbox::close_session();
    code
}

// -- the road launcher ------------------------------------------------------------------

fn playtest_road(args: &[String]) -> i32 {
    let headless = flag_f64(args, "--headless").unwrap_or(0.0);
    let opts = road_options(args);

    if headless == 0.0 {
        // `playtest_road` builds its own app and runs it, which means it never
        // passes through the guard `app::main_with` uses. Launching one while
        // a game was already open gave the owner two windows, the new drive
        // rolling unfocused behind the old one, and an open weigh station that
        // came and went unheard (2026-08-21). A bench is exempt: it opens no
        // window and several are fine at once.
        let mut guard = freight_fate::single_instance::SingleInstanceGuard::new();
        if !guard.acquire() {
            eprintln!(
                "Freight Fate is already running. Close it first -- a second window would \
                 start rolling behind the one you are looking at."
            );
            return 1;
        }
        let code = road_session(&opts, headless, args);
        guard.release();
        return code;
    }
    road_session(&opts, headless, args)
}

fn road_session(opts: &road::RoadOptions, headless: f64, args: &[String]) -> i32 {
    // ON BY DEFAULT since 2026-08-20, because the opt-in version was a trap.
    // A bench run started to answer one question about the engine brake, with
    // the flag simply not typed, created a "Playtest" career in the real save
    // directory and uploaded it to the owner's account minutes after that
    // account had been deliberately emptied. The tool cannot tell a throwaway
    // career from a real one; the only safe default is the one that cannot
    // reach the account at all.
    let sandbox_dir = if opts.sandbox {
        let dir = sandbox::default_sandbox();
        if let Err(e) = sandbox::prepare(&dir, false, true, &sandbox::real_saves()) {
            eprintln!("Could not prepare the sandbox: {e}");
            return 1;
        }
        println!("{}", sandbox::describe(&dir));
        if !sandbox::audit(&dir).is_empty() {
            eprintln!("Refusing to drive: the sandbox is not isolated.");
            return 1;
        }
        println!();
        Some(dir)
    } else {
        None
    };

    // A bench and a live drive both defaulting to playtest.log meant a bench
    // run mid-session rotated the transcript out from under the person
    // driving, and pointed the session watcher at the wrong road.
    let log_path = match &opts.log {
        Some(path) => PathBuf::from(path),
        None if headless > 0.0 => ff_core::settings::game_root()
            .join("logs")
            .join("playtest-bench.log"),
        None => ff_core::settings::game_root()
            .join("logs")
            .join("playtest.log"),
    };
    open_log(&log_path);
    if headless > 0.0 {
        for (name, value) in [
            ("FREIGHT_FATE_NO_SPEECH", "1"),
            ("SDL_VIDEODRIVER", "dummy"),
            ("SDL_AUDIODRIVER", "dummy"),
        ] {
            if std::env::var_os(name).is_none() {
                std::env::set_var(name, value);
            }
        }
    }

    // Pick the spot first, against the world data alone: nothing below needs
    // a window until we actually drive.
    let hit = match road::plan(opts) {
        road::RoadPlan::Done(code) => return code,
        road::RoadPlan::Drive(hit) => hit,
    };

    app::configure_logging();
    if headless > 0.0 {
        let mut app = App::new_headless(Box::new(CaptureSpeech::new()));
        let (driving, start_mi) = road::build_driving(&mut app.ctx, &hit, opts);
        road::print_setup(&mut app.ctx, &hit, start_mi, opts);
        app.push_state(driving);
        let frames = (60.0 * 60.0 * headless) as usize;
        for _ in 0..frames {
            app.tick(1.0 / 60.0);
        }
        app.shutdown();
        println!("\nBench done. Transcript written to {}", log_path.display());
        return 0;
    }

    let mut app = match App::new() {
        Ok(app) => app,
        Err(e) => {
            eprintln!("Fatal error: {e}");
            return 1;
        }
    };
    // The session must not leak its lane-keeping/assists overrides into the
    // player's real settings: shutdown saves settings on the way out, which
    // persisted a playtest's flags as the player's own choices (owner-hit
    // 2026-07-27: the steering override became the saved setting).
    let settings_path = ff_core::settings::data_dir().join("settings.json");
    let settings_before = std::fs::read(&settings_path).ok();

    // `App::run` takes its first screen from `set_initial_state`, so the
    // staged drive simply IS the screen the loop starts on -- and quitting to
    // the main menu reaches the REAL menu, with its working Exit.
    app.set_initial_state(road_builder(hit, args));
    if let Some(dir) = &sandbox_dir {
        // Announce the live session so tools/playtest_watch.py can follow this
        // drive the same way it follows a sandbox launch.
        sandbox::open_session(dir, &log_path);
    }
    println!("\n  G grade, J engine brake, K cruise, Down arrow brakes (hands cruise back).");
    println!("  To leave: Escape pauses; quit to the main menu, then Exit as usual.");
    println!("  Transcript: {}\n", log_path.display());
    app.run(None);
    app.shutdown();
    if sandbox_dir.is_some() {
        sandbox::close_session();
    }
    match settings_before {
        Some(bytes) => {
            let _ = std::fs::write(&settings_path, bytes);
        }
        None => {
            let _ = std::fs::remove_file(&settings_path);
        }
    }
    println!("\nDone. Transcript written to {}", log_path.display());
    0
}

/// The staged drive, as the app's initial-state factory.
fn road_builder(hit: road::Hit, args: &[String]) -> app::InitialState {
    let opts = road_options(args);
    Box::new(move |ctx| {
        let (driving, start_mi) = road::build_driving(ctx, &hit, &opts);
        road::print_setup(ctx, &hit, start_mi, &opts);
        freight_fate::app::share(driving)
    })
}

fn road_options(args: &[String]) -> road::RoadOptions {
    let mut opts = road::RoadOptions {
        origin: flag_value(args, "--from"),
        destination: flag_value(args, "--to"),
        routes: flag_value(args, "--routes").unwrap_or_else(|| "mountain".to_string()),
        seed: flag_i64(args, "--seed"),
        sample: flag_usize(args, "--sample").unwrap_or(road::RANDOM_SAMPLE),
        max_miles: flag_f64(args, "--max-miles").unwrap_or(road::RANDOM_MAX_MILES),
        feature: flag_value(args, "--find").unwrap_or_default(),
        at: flag_f64(args, "--at"),
        pick: flag_usize(args, "--pick").unwrap_or(0),
        trip_seed: flag_i64(args, "--trip-seed"),
        scan: has(args, "--scan"),
        min_pct: flag_f64(args, "--min-pct").unwrap_or(3.0),
        min_run: flag_f64(args, "--min-run").unwrap_or(1.0),
        min_drop: flag_f64(args, "--min-drop").unwrap_or(10.0),
        max_advisory: flag_f64(args, "--max-advisory").unwrap_or(45.0),
        lead: flag_f64(args, "--lead"),
        cruise: flag_f64(args, "--cruise").unwrap_or(0.0),
        speed: flag_f64(args, "--speed").unwrap_or(62.0),
        cargo: flag_f64(args, "--cargo").unwrap_or(20.0),
        cargo_type: flag_value(args, "--cargo-type").unwrap_or_else(|| "general".to_string()),
        level: flag_i64(args, "--level"),
        descent: flag_value(args, "--descent"),
        assists: flag_value(args, "--assists"),
        planned_stop_assist: flag_on_off(args, "--planned-stop-assist"),
        predictive_cruise: flag_on_off(args, "--predictive-cruise"),
        lane_keeping: flag_value(args, "--lane-keeping"),
        curve_assist: flag_on_off(args, "--curve-assist"),
        transmission: flag_value(args, "--transmission"),
        verbosity: flag_value(args, "--verbosity"),
        weather: flag_value(args, "--weather"),
        hour: flag_f64(args, "--hour"),
        log: flag_value(args, "--log"),
        sandbox: !has(args, "--no-sandbox"),
    };
    if has(args, "--no-cruise") {
        opts.cruise = 0.0;
    }
    if opts.feature.is_empty() && opts.at.is_none() {
        opts.feature = "downgrade".to_string();
    }
    opts
}

/// Point this session's log at `path` (`FREIGHT_FATE_LOG_FILE`), at INFO.
fn open_log(path: &std::path::Path) {
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    std::env::set_var("FREIGHT_FATE_LOG_FILE", path);
    if std::env::var_os("FREIGHT_FATE_LOG").is_none() {
        std::env::set_var("FREIGHT_FATE_LOG", "INFO");
    }
}
