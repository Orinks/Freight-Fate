//! The real streets from I-20 exit 292B to the Abilene Company Yard, driven
//! the way the live agent drive of 2026-09-24 drove them: every assist on,
//! nobody on the pedals, the game's own time compression. That drive met a
//! red at about seven of its fourteen lights where the synthetic arterial
//! (at real time) promised one or two.

use ff_core::data::world::get_world;
use ff_core::sim::weather::WeatherKind;
use freight_fate::playtest::harness::{PlaytestHarness, RouteSetup};
use freight_fate::states::base::Key;
use freight_fate::states::driving_menu_states::FacilityArrivalState;
use freight_fate::states::driving_rest_states::RestStopState;

use crate::transcript_cruise_support::{frame, quiet, DT, MPS_PER_MPH};

/// What one drive down the Abilene streets met.
#[derive(Debug, Default)]
pub struct StreetLights {
    /// Signals the truck reached the call distance of.
    pub signals: usize,
    /// Signals that owed a stop at some moment of the approach, by the
    /// game's own judgement (`bar_cues_owed`): the ones it names, counts the
    /// bar down for and slows the clock for.
    pub reds_met: usize,
    /// Signals the truck came to a stop and held at.
    pub stops: usize,
    pub arrived: bool,
    pub transcript: String,
    /// What the grade key says at the gate.
    pub grade_at_gate: String,
    /// Lines said twice in a row that no flush handed back.
    pub said_twice: Vec<String>,
    /// Lines the pacer handed back after a cut.
    pub hand_backs: usize,
}

/// Drive exit 292B's ramp and streets to the Abilene Company Yard gate from
/// trip seed `seed`, every assist on, at the settings' own time scale.
pub fn abilene_street_lights(seed: i64) -> StreetLights {
    let world = get_world();
    let mut harness = PlaytestHarness::new();
    {
        let s = &mut harness.app.ctx.settings;
        s.apply_driving_assistance_preset("all");
        s.speed_keeper = true;
        s.automatic_transmission = true;
        s.lane_keeping = "full".to_string();
        s.time_scale = 10.0;
    }
    let cities = world
        .shortest_route("dallas_tx_us", "abilene_tx_us", None, false)
        .expect("the world routes")
        .expect("Dallas has a route to Abilene")
        .cities;
    let mut setup = RouteSetup::seeded(seed)
        .named("Abilene Lights")
        .destination_location("Abilene Company Yard");
    setup.route_cities = Some(cities);
    harness.start_route("dallas_tx_us", "abilene_tx_us", setup);
    harness.with_drive(|d, ctx| {
        quiet(&mut d.trip);
        d.weather_mut().current = WeatherKind::Clear;
        d.departure_checked = true;
        if let Some(profile) = ctx.profile.as_mut() {
            profile.tutorial_done = true;
        }
        d.tutorial = None;
        d.truck_mut().start_engine();
        d.truck_mut().transmission.automatic = true;
        d.truck_mut().transmission.gear = 9;
        d.truck_mut().rpm = 1500.0;
        d.truck_mut().set_air_ready(false);
        d.speed_control_armed = true;
    });
    let exit = harness.with_drive(|d, ctx| {
        d.destination_exit_stop(ctx)
            .expect("a delivery always has a destination exit")
    });
    assert_eq!(exit.exit_label, "exit 292B", "the live drive's exit");
    let at = exit.at_mi;
    harness.with_drive(move |d, ctx| {
        d.exit_stop = Some(exit);
        d.exit_lane_alignment = 1.0;
        d.exit_signal_on = true;
        d.trip.position_mi = at;
        d.truck_mut().velocity_mps = 40.0 * MPS_PER_MPH;
        d.update_exit(ctx, 0.0, 0.0);
    });
    harness.clear_speech();
    let mut out = StreetLights::default();
    let mut live_bar: Option<f64> = None;
    let mut owed = false;
    let mut was_waiting = false;
    // Half an hour of road: the live drive took nine minutes.
    for _ in 0..(30.0 * 60.0 / DT) as usize {
        if !harness.has_drive() {
            harness.finish_timed_state();
            out.arrived = harness.state_is::<FacilityArrivalState>();
            break;
        }
        if harness.read_drive(|d| d.arrival_menu_open) {
            harness.finish_timed_state();
            out.arrived = harness.state_is::<FacilityArrivalState>();
            break;
        }
        // Facility stopping assistance holds at the entrance for Enter.
        if harness.read_drive(|d| {
            d.surface_chain && d.trip.remaining_miles() < 0.1 && d.truck().speed_mph() < 1.0
        }) {
            out.arrived = true;
            out.grade_at_gate = harness.with_drive(|d, ctx| d.next_grade_text(ctx));
            break;
        }
        let (bar, signal, owes, waiting) = harness.read_drive(|d| {
            let signal = d.on_street_control() && d.ramp_control == "signal";
            let live = signal && !d.ramp_terminal_done;
            let gap = d.terminal_gap_mi().unwrap_or(0.0);
            (
                d.street_bar_mi.filter(|_| signal),
                signal,
                live && d.ramp_light_announced && gap > 0.0 && d.bar_cues_owed(),
                signal && d.ramp_waiting_at_light,
            )
        });
        if signal && bar != live_bar && bar.is_some() {
            out.signals += 1;
            owed = false;
        }
        if signal {
            live_bar = bar;
        }
        if owes && !owed {
            owed = true;
            out.reds_met += 1;
        }
        if waiting && !was_waiting {
            out.stops += 1;
        }
        was_waiting = waiting;
        harness.with_drive(|d, _| {
            let cut_out = d.truck().specs.air_governor_cut_out_psi;
            d.truck_mut().set_air_pressure_psi(cut_out);
        });
        frame(&mut harness, DT);
    }
    out.transcript = harness.transcript_text();
    // A line said twice in a row is a repeat unless it is the pacer
    // finishing a line a flush cut before its first word (heard once).
    let lines: Vec<&str> = out
        .transcript
        .lines()
        .filter(|l| !l.trim().is_empty())
        .collect();
    for pair in lines.windows(2) {
        let text = pair[1].trim_start_matches("[event] ");
        if pair[0] == pair[1] && harness.app.ctx.handed_back_count(text) == 0 {
            out.said_twice.push(text.to_string());
        }
    }
    out.hand_backs = harness.app.ctx.handed_back_count("");
    out
}

#[test]
#[cfg_attr(
    ci_quick,
    ignore = "sweep: twenty drives of the Abilene streets from exit 292B"
)]
fn test_the_abilene_streets_meet_few_reds_with_every_assist_on() {
    let seeds: i64 = std::env::var("SIGNAL_SEEDS")
        .ok()
        .and_then(|n| n.parse().ok())
        .unwrap_or(20);
    let runs: Vec<StreetLights> = (1..=seeds).map(abilene_street_lights).collect();
    for (seed, run) in runs.iter().enumerate() {
        eprintln!(
            "seed {}: {} signals, {} reds met, {} stops, arrived {}",
            seed + 1,
            run.signals,
            run.reds_met,
            run.stops,
            run.arrived
        );
    }
    let reds: usize = runs.iter().map(|r| r.reds_met).sum();
    let stops: usize = runs.iter().map(|r| r.stops).sum();
    eprintln!(
        "average {:.2} reds met, {:.2} stops",
        reds as f64 / runs.len() as f64,
        stops as f64 / runs.len() as f64
    );
    for (seed, run) in runs.iter().enumerate() {
        assert!(
            run.arrived,
            "seed {} never arrived\n{}",
            seed + 1,
            run.transcript
        );
    }
    // Measured before the lights ran on real seconds and were judged at the
    // truck's arrival: 8.35 of the 12 owed a stop on average, 3.6 stops.
    // After: 2.9 and 0.9. A random arrival at each street's first light and
    // at the turn's light alone is about 2.
    let n = runs.len() as f64;
    assert!(
        reds as f64 / n <= 4.0,
        "{:.2} reds a drive",
        reds as f64 / n
    );
    assert!(
        stops as f64 / n <= 1.5,
        "{:.2} stops a drive",
        stops as f64 / n
    );
}

// -- the Love's at Baird, taken with X ------------------------------------------------

/// Drive I-20 from `origin` to the Love's Travel Stop at Baird (exit 307)
/// the way the live drive took it: X at the stop's call, every assist on.
/// Returns whether its streets were driven, and what was said.
fn baird_by_x(origin: &str, destination: &str) -> (bool, String) {
    let mut harness = PlaytestHarness::new();
    {
        let s = &mut harness.app.ctx.settings;
        s.apply_driving_assistance_preset("all");
        s.speed_keeper = true;
        s.automatic_transmission = true;
        s.lane_keeping = "full".to_string();
        s.time_scale = 10.0;
    }
    harness.start_route(origin, destination, RouteSetup::seeded(7).named("Baird"));
    let stop = harness.with_drive(|d, ctx| {
        quiet(&mut d.trip);
        d.weather_mut().current = WeatherKind::Clear;
        d.departure_checked = true;
        if let Some(profile) = ctx.profile.as_mut() {
            profile.tutorial_done = true;
        }
        d.tutorial = None;
        d.truck_mut().start_engine();
        d.truck_mut().transmission.automatic = true;
        d.truck_mut().transmission.gear = 10;
        d.truck_mut().set_air_ready(false);
        let stop = d
            .trip
            .stops
            .iter()
            .find(|s| s.name == "Love's Travel Stop Baird")
            .cloned()
            .expect("the Baird Love's is on I-20");
        d.trip.position_mi = stop.at_mi - 2.5;
        d.truck_mut().velocity_mps = 65.0 * MPS_PER_MPH;
        stop
    });
    frame(&mut harness, DT);
    harness.press_key(Key::X, None);
    assert_eq!(
        harness.read_drive(|d| d.exit_stop.as_ref().map(|s| s.key())),
        Some(stop.key()),
        "X signals the Love's\n{}",
        harness.transcript_text()
    );
    let mut streets = false;
    for _ in 0..(10.0 * 60.0 / DT) as usize {
        if !harness.has_drive() || harness.state_is::<RestStopState>() {
            break;
        }
        streets |= harness.read_drive(|d| d.stop_chain.is_some());
        if harness.read_drive(|d| d.arrival_menu_open) {
            break;
        }
        harness.with_drive(|d, _| {
            let cut_out = d.truck().specs.air_governor_cut_out_psi;
            d.truck_mut().set_air_pressure_psi(cut_out);
        });
        frame(&mut harness, DT);
    }
    (streets, harness.transcript_text())
}

#[test]
fn test_the_bairds_streets_are_driven_eastbound_when_signalled_with_x() {
    let (streets, heard) = baird_by_x("abilene_tx_us", "fort_worth_tx_us");
    assert!(streets, "{heard}");
    assert!(heard.contains("Off the ramp."), "{heard}");
    assert!(heard.contains("Into the lot."), "{heard}");
}

/// The live drive's direction. Exit 307's westbound ramp was never measured
/// (it leaves at its own junction node, 1.07 km from the eastbound one the
/// bake searched around), so it has no terminal and no streets until the
/// ramp bake runs with `RAMP_SIBLING_JUNCTION_M`.
#[test]
#[ignore = "needs the ramp terminals re-baked with the sibling-junction search (OSM refresh)"]
fn test_the_bairds_streets_are_driven_westbound_when_signalled_with_x() {
    let (streets, heard) = baird_by_x("fort_worth_tx_us", "abilene_tx_us");
    assert!(streets, "{heard}");
    assert!(heard.contains("Into the lot."), "{heard}");
}

/// What the same drives said: a light is named only when it owes a stop, a
/// street is not a zone, no line is heard twice in a row, and the grade key
/// never counts "0 miles" of road.
#[test]
#[cfg_attr(
    ci_quick,
    ignore = "sweep: drives of the Abilene streets from exit 292B"
)]
fn test_the_abilene_streets_say_each_thing_once() {
    for seed in [1, 3, 6] {
        let run = abilene_street_lights(seed);
        let heard = &run.transcript;
        if std::env::var("SIGNAL_DUMP").is_ok() {
            eprintln!("seed {seed}:\n{heard}\n{}", run.grade_at_gate);
        }
        assert!(run.arrived, "seed {seed} never arrived\n{heard}");
        let named = heard.matches("Traffic light ahead.").count();
        assert!(
            named <= run.reds_met,
            "seed {seed}: {named} lights named, {} owed a stop\n{heard}",
            run.reds_met
        );
        assert!(
            named < run.signals,
            "seed {seed}: every light named\n{heard}"
        );
        for zone in ["access road zone", "facility access road"] {
            assert!(!heard.contains(zone), "seed {seed}: {zone:?}\n{heard}");
        }
        assert!(
            run.said_twice.is_empty(),
            "seed {seed}: said twice {:?}\n{heard}",
            run.said_twice
        );
        // The live drive handed back a line at almost every light, each a
        // burst of route lines landing in one frame.
        assert!(
            run.hand_backs <= 3,
            "seed {seed}: {} lines handed back\n{heard}",
            run.hand_backs
        );
        assert!(
            !run.grade_at_gate.contains(" 0 miles"),
            "seed {seed}: {}",
            run.grade_at_gate
        );
    }
}
