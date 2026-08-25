//! The destination approach assist, driven to real facilities all over the map.
//!
//! Owner, 2026-08-24: "destination approach assistance works on some legs and
//! not others" -- on the legs where it fails the truck is never brought to a
//! stop ready to pull in.
//!
//! The four `states_driving_facility.rs` approach-assist cases were deferred
//! on "a hands-off end-to-end drive over baked chain data". This file is that
//! drive; those four now use its rigging for their own narrower bars, and it
//! runs the same drive as a SWEEP, because the defect is precisely that one
//! destination arrives and the next one does not. Every run here pins its
//! trip seed and its weather: an unseeded delivery draws its own road and its
//! own sky, and letting dispatch's random draw decide which shape got
//! measured is what hid this.
//!
//! The driver in these runs is a player, not a ghost. They roll the ramp and
//! the city streets at the posted number, and they lift the moment the assist
//! announces it has the pedals -- from there nothing but the game touches the
//! truck, which is what "it stops me at the destination" has to mean.

use ff_core::data::world::{get_world, World};
use ff_core::data::world_models::{CorridorDetail, GradeSegment, Leg, Route};
use ff_core::sim::trip_models::FACILITY_GATE_LIMIT_MPH;
use ff_core::sim::weather::WeatherKind;

use freight_fate::playtest::harness::{PlaytestHarness, RouteSetup};
use freight_fate::states::base::Key;
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::DOCKING_MAX_MPH;
use freight_fate::states::driving_menu_states::FacilityArrivalState;

use crate::transcript_cruise_support::{frame, hold, quiet, release_keys, DT, MPS_PER_MPH};

// -- picking the destinations ----------------------------------------------------------

/// A destination the sweep drives to: which city, which facility, and whether
/// the facility's approach is a real turn-level street chain.
#[derive(Debug, Clone)]
pub struct Destination {
    pub city: String,
    pub location: String,
    /// The state whose vehicle code governs its streets. One per state is how
    /// the sweep spreads itself; it also reads back in a failure.
    pub state: String,
    pub chain: bool,
}

impl Destination {
    pub fn kind(&self) -> &'static str {
        if self.chain {
            "street chain"
        } else {
            "plain"
        }
    }
}

/// One chain-capable facility and one plain one per state, walked in a fixed
/// order so the sweep drives the same places every run.
///
/// Both kinds have to be covered, and covered separately, because the two take
/// different roads to the same gate: a plain facility's ramp ends AT the gate,
/// while a chain facility's ramp hands off to up to a mile of city streets
/// that are a trip of their own.
pub fn destinations(world: &'static World, want: usize) -> (Vec<Destination>, Vec<Destination>) {
    let mut keys: Vec<&String> = world.cities.keys().collect();
    keys.sort();
    let mut chain: Vec<Destination> = Vec::new();
    let mut plain: Vec<Destination> = Vec::new();
    let mut chain_states: Vec<String> = Vec::new();
    let mut plain_states: Vec<String> = Vec::new();
    for city in keys {
        let Some(entry) = world.cities.get(city) else {
            continue;
        };
        // A destination is only drivable here if the world has somewhere to
        // start from that connects straight to it.
        if world.neighbors(city).is_empty() {
            continue;
        }
        let state = entry.state.clone();
        for location in &entry.locations {
            let Ok(route) = world.facility_approach_route(city, &location.name) else {
                continue;
            };
            // The same bar `surface_chain_route` applies: a genuine
            // multi-segment turn-level route, not a single synthetic leg.
            let is_chain =
                route.legs.len() >= 2 && route.legs.iter().any(|leg| leg.local_speed_mph > 0.0);
            let (bucket, seen) = if is_chain {
                (&mut chain, &mut chain_states)
            } else {
                (&mut plain, &mut plain_states)
            };
            if bucket.len() >= want || seen.contains(&state) {
                continue;
            }
            seen.push(state.clone());
            bucket.push(Destination {
                city: city.clone(),
                location: location.name.clone(),
                state: state.clone(),
                chain: is_chain,
            });
        }
        if chain.len() >= want && plain.len() >= want {
            break;
        }
    }
    (chain, plain)
}

// -- driving one of them ---------------------------------------------------------------

/// What one arrival did.
#[derive(Debug)]
pub struct Arrival {
    /// The dock menu opened, or the assist stopped and held at the gate with
    /// its prompt spoken. Either is "ready to pull in".
    pub ready: bool,
    /// The dock menu opened on its own.
    pub docked: bool,
    /// The assist announced that it had taken the pedals.
    pub assist_spoke: bool,
    /// Road speed when the run ended, mph.
    pub speed_mph: f64,
    /// Road still to the gate when the run ended, feet.
    pub short_by_ft: f64,
    /// The road grade under the gate, as a fraction: positive climbing to it.
    pub gate_grade_pct: f64,
    /// Whether the truck ever reached the facility's street chain.
    pub on_chain: bool,
    /// Road speed the moment the arrival point went under the wheels, mph.
    pub speed_at_point_mph: Option<f64>,
    /// How far the truck ran on past that point before it stopped, feet.
    pub past_the_point_ft: f64,
    /// Every line the driver heard.
    pub heard: Vec<String>,
}

impl Arrival {
    pub fn said(&self, needle: &str) -> bool {
        self.heard.iter().any(|line| line.contains(needle))
    }

    /// What went wrong, for a failure message that names the place and the
    /// numbers rather than just "assertion failed".
    pub fn report(&self, destination: &Destination) -> String {
        let tail: Vec<&String> = self.heard.iter().rev().take(6).rev().collect();
        format!(
            "{} ({}, {}, {}): ready={} assist_spoke={} on_chain={} speed={:.2} mph, {:.0} ft short of \
             the gate\nlast heard: {:#?}",
            destination.location,
            destination.city,
            destination.state,
            destination.kind(),
            self.ready,
            self.assist_spoke,
            self.on_chain,
            self.speed_mph,
            self.short_by_ft,
            tail,
        )
    }
}

/// What a competent player would be doing here, in mph.
///
/// The number the game itself holds a ramp at rather than the ramp ceiling: a
/// driver who pushes past the route-transition assist's cap spends the run
/// fighting its brake, and a truck that pumps its air down to the spring
/// brakes is a test of the air system, not of the arrival. On the streets it
/// is the posted number, eased to the advised speed for a corner in play --
/// a driver who hears "turn right, ten miles an hour" and holds twenty-nine
/// through it is testing the missed-turn loop-back, not the assist.
pub fn driver_target_mph(d: &mut DrivingState) -> f64 {
    if d.ramp_mi.is_some() {
        return d.armed_ramp_mph(None);
    }
    let posted = d.trip.speed_limit_at(d.trip.position_mi).0;
    match d.turn_cue_in_play() {
        Some(cue) if cue.at_mi >= d.trip.position_mi => posted.min(d.turn_speed_mph(&cue)),
        _ => posted,
    }
}

/// Drive the last mile to `destination`: down the destination ramp, through
/// any street chain, to the gate.
pub fn arrive(destination: &Destination) -> Arrival {
    arrive_over(destination, None)
}

/// Re-lay a facility's street chain on a constant grade.
///
/// The shipped chains are built from local street geometry, which carries no
/// grade segments at all, so the road under every one of them reads dead
/// level. A gate at the top of a climb is a real shape and the one a
/// brake-only stop profile gets wrong in the other direction, so the case
/// that wants one has to build it: the same streets, the same cues, the same
/// speeds, on a hill.
fn regrade_chain(d: &mut DrivingState, grade_pct: f64) {
    let city = d.trip.route.cities[0].clone();
    let legs: Vec<Leg> = d
        .trip
        .route
        .legs
        .iter()
        .map(|leg| {
            let detail = CorridorDetail {
                grade_segments: vec![GradeSegment::new(
                    0.0,
                    leg.miles,
                    grade_pct * 100.0,
                    "rolling",
                    "test bench",
                )],
                ..Default::default()
            };
            Leg::local(
                &city,
                leg.miles,
                &leg.highway,
                &leg.local_cue,
                leg.local_speed_mph,
            )
            .with_detail(detail)
        })
        .collect();
    let cities = vec![city; legs.len() + 1];
    d.trip.route = Route::from_legs(cities, legs);
}

/// [`arrive`], with the facility's street chain re-laid on a constant grade.
pub fn arrive_over(destination: &Destination, chain_grade_pct: Option<f64>) -> Arrival {
    let world = get_world();
    let origin = world.neighbors(&destination.city)[0]
        .other(&destination.city)
        .to_string();
    let mut harness = PlaytestHarness::new();
    harness.app.ctx.settings.destination_approach_assist = true;
    harness.app.ctx.settings.speed_keeper = true;
    harness.start_route(
        &origin,
        &destination.city,
        RouteSetup::seeded(4242)
            .named("Approach Sweep")
            .destination_location(&destination.location),
    );
    harness.with_drive(|d, ctx| {
        quiet(&mut d.trip);
        // Pinned, not drawn: rain changes what the road can shed, and a sweep
        // whose sky differs per destination is measuring the sky.
        d.weather_mut().current = WeatherKind::Clear;
        d.departure_checked = true;
        // A first-run career would talk over the arrival with lesson prompts.
        if let Some(profile) = ctx.profile.as_mut() {
            profile.tutorial_done = true;
        }
        d.tutorial = None;
        d.truck_mut().start_engine();
        d.truck_mut().transmission.automatic = true;
        d.truck_mut().set_air_ready(false);
        d.speed_control_armed = true;
    });
    let exit = harness.with_drive(|d, ctx| {
        d.destination_exit_stop(ctx)
            .expect("a delivery always has a destination exit")
    });
    let at = exit.at_mi;
    harness.with_drive(move |d, ctx| {
        d.exit_stop = Some(exit);
        d.exit_lane_alignment = 1.0;
        d.exit_signal_on = true; // signalled for it, like a driver
        d.trip.position_mi = at;
        d.truck_mut().velocity_mps = 40.0 * MPS_PER_MPH;
        d.update_exit(ctx, 0.0, 0.0);
    });
    assert!(
        harness.read_drive(|d| d.ramp_mi.is_some()),
        "{}: never got onto the destination ramp",
        destination.city
    );
    harness.with_drive(|d, _| {
        // The light or stop sign at the end of a ramp has an assist of its
        // own, and its own suite. Clear it, so the only automation that can
        // bring this truck up at the facility is the one under test.
        d.ramp_control = String::new();
        d.ramp_terminal_done = true;
    });
    harness.clear_speech();

    let mut ready = false;
    let mut docked = false;
    let mut on_chain = false;
    let mut gate_grade_pct = 0.0;
    let mut handed_off = false;
    let mut speed_at_point_mph: Option<f64> = None;
    let mut past_the_point_ft = 0.0;
    // Enough for a mile of city streets at a crawl, and no more: a truck that
    // has not arrived by then is not going to.
    for _ in 0..(60 * 600) {
        if !harness.has_drive() {
            // The automatic pull-in first replaces the drive with a timed
            // spoken transition. Finish it and require the real dock menu;
            // merely losing the drive is not proof that delivery can continue.
            harness.finish_timed_state();
            ready = harness.state_is::<FacilityArrivalState>();
            docked = ready;
            break;
        }
        if harness.read_drive(|d| d.arrival_menu_open) {
            harness.finish_timed_state();
            ready = harness.state_is::<FacilityArrivalState>();
            docked = ready;
            break;
        }
        let now_on_chain = harness.read_drive(|d| d.surface_chain);
        if now_on_chain && !on_chain {
            if let Some(grade_pct) = chain_grade_pct {
                harness.with_drive(move |d, _| regrade_chain(d, grade_pct));
            }
        }
        on_chain |= now_on_chain;
        // The arrival point, and everything after it. Integrated from the
        // truck's own speed rather than read off the trip: `position_mi`
        // jumps when the chain trip is swapped in, so it cannot measure how
        // far the truck ran past a gate it has already passed.
        if speed_at_point_mph.is_none() {
            let at_point = harness.read_drive(|d| {
                (d.trip.remaining_miles() <= 0.0 || d.trip.finished)
                    && d.ramp_mi.is_none()
                    && d.destination_exit_taken
            });
            if at_point {
                speed_at_point_mph = Some(harness.read_drive(|d| d.truck().speed_mph()));
            }
        } else {
            past_the_point_ft += harness.read_drive(|d| d.truck().velocity_mps) * DT * 3.28084;
        }
        // Stopped at the gate with the hold prompt spoken IS the arrival: the
        // assist holds there and waits for the driver to pull in.
        if harness
            .read_drive(|d| d.arrival_full_stop_said && d.truck().speed_mph() <= DOCKING_MAX_MPH)
        {
            ready = true;
            break;
        }
        if !handed_off {
            // The moment the assist claims the pedals the driver lifts, and
            // never touches anything again.
            handed_off = harness.read_drive(|d| d.destination_arrival_active);
            if handed_off {
                release_keys(&mut harness);
                // What the road under the gate is doing, read where the shed
                // begins: an upgrade sheds speed for free and is where a
                // brake-only profile stops SHORT of the gate.
                gate_grade_pct = harness.read_drive(|d| {
                    let end = d.trip.total_miles();
                    (d.trip.grade_at(end) + d.trip.grade_at((end - 0.1).max(0.0))) / 2.0
                });
            }
        }
        if !handed_off {
            let rolling =
                harness.with_drive(|d, _| driver_target_mph(d) > d.truck().speed_mph() + 2.0);
            if rolling {
                hold(&mut harness, &[Key::Up]);
            } else {
                release_keys(&mut harness);
            }
        }
        frame(&mut harness, DT);
    }
    release_keys(&mut harness);
    let (speed_mph, short_by_ft) = if harness.has_drive() {
        harness.read_drive(|d| {
            (
                d.truck().speed_mph(),
                d.ramp_mi.unwrap_or_else(|| d.trip.remaining_miles()) * 5280.0,
            )
        })
    } else {
        (0.0, 0.0)
    };
    let heard = harness.transcript();
    Arrival {
        ready,
        docked,
        gate_grade_pct,
        assist_spoke: heard
            .iter()
            .any(|line| line.contains("Destination approach assistance slowing")),
        speed_mph,
        short_by_ft,
        on_chain,
        speed_at_point_mph,
        past_the_point_ft,
        heard,
    }
}

// -- what every arrival owes the driver --------------------------------------------------

/// How many destinations of each kind the sweep drives.
pub const PER_KIND: usize = 25;

/// A tractor-trailer's own length. Stopping AT the gate means stopping within
/// it, not a city block later.
pub const TRUCK_LENGTH_FT: f64 = 70.0;

/// The whole promise, checked on one arrival: it stopped, it stopped at the
/// gate, and it said so. `None` when nothing is wrong.
pub fn what_went_wrong(destination: &Destination, arrival: &Arrival) -> Option<String> {
    let fault = |why: &str| Some(format!("{why}\n{}", arrival.report(destination)));
    // 1. It stopped, and the dock is reachable from where it stopped.
    if !arrival.ready {
        return fault("never reached a stop ready to pull in");
    }
    if arrival.speed_mph > DOCKING_MAX_MPH {
        return fault("still rolling at the end of the run");
    }
    // 2. It stopped AT the gate. Crossing the arrival point over the gate's
    //    own posted number is the Spokane report -- "it did not automatically
    //    stop at the destination; I had to stop" -- and running a city block
    //    past it is the same complaint from the other side.
    if let Some(speed) = arrival.speed_at_point_mph {
        if speed > FACILITY_GATE_LIMIT_MPH {
            return fault("crossed its own gate over the gate's posted number");
        }
    }
    if arrival.past_the_point_ft > TRUCK_LENGTH_FT {
        return fault("stopped more than its own length past the gate");
    }
    // 3. Nothing untrue was said about where the truck was.
    for lie in [
        "Drove past",
        "You never stopped",
        "missed the destination exit",
    ] {
        if arrival.said(lie) {
            return fault("was told it had blown the arrival it made");
        }
    }
    // 4. The assist named itself when it took the pedals. A truck that slows
    //    and halts in silence is, to a blind driver, indistinguishable from an
    //    assist that is not working -- which is how this was reported three
    //    times before anyone measured it.
    if !arrival.assist_spoke {
        return fault("took the pedals without saying so");
    }
    // 5. And it ended on an instruction the driver can act on: either the dock
    //    menu opened by itself, or the assist is holding and said which key
    //    opens it.
    if !arrival.docked
        && !arrival.said(
            "Destination approach stopped and holding. Press Enter, or controller A, to continue \
             into the facility.",
        )
    {
        return fault("stopped without telling the driver how to pull in");
    }
    if destination.chain {
        // A chain facility's streets are the way in. Stopping at the bottom of
        // the ramp is a stop up to a mile short of the gate, and being told
        // "you are at" the facility there is untrue by that same mile.
        if !arrival.on_chain {
            return fault("never drove the facility's own streets");
        }
        if !arrival.said("Off the ramp and onto city streets") {
            return fault("was handed city streets without being told");
        }
        if arrival.said("Come to a complete stop.") && !arrival.docked {
            return fault("was told it had arrived while the gate was still a mile of streets on");
        }
    }
    None
}

#[test]
fn test_the_approach_assist_stops_the_truck_at_every_kind_of_destination() {
    let world = get_world();
    let (chain, plain) = destinations(world, PER_KIND);
    assert_eq!(
        (chain.len(), plain.len()),
        (PER_KIND, PER_KIND),
        "the shipped world no longer offers {PER_KIND} of each kind of destination"
    );
    let mut failures: Vec<String> = Vec::new();
    let mut climbed = 0;
    for destination in chain.iter().chain(plain.iter()) {
        let arrival = arrive(destination);
        if arrival.gate_grade_pct > 0.01 {
            climbed += 1;
        }
        if let Some(fault) = what_went_wrong(destination, &arrival) {
            failures.push(fault);
        }
    }
    assert!(
        failures.is_empty(),
        "{} of {} destinations did not stop the truck ready to pull in:\n\n{}",
        failures.len(),
        chain.len() + plain.len(),
        failures.join("\n\n")
    );
    // The gate at the top of a climb is the case a brake-only stop profile
    // gets wrong in the other direction -- the road sheds the speed for free
    // and the truck halts short, with the dock never opening. The shipped
    // world supplies real ones; if it ever stops doing so this sweep has
    // quietly lost that half of the coverage.
    assert!(
        climbed > 0,
        "no destination in the sweep climbs to its gate any more"
    );
}

#[test]
fn test_shelby_cross_dock_approach_assist_reaches_the_arrival_gate() {
    // Darren, 2026-08-25: approaching Shelby Cross-Dock, the assist took the
    // truck from 30 to 14 to 5 to 2 mph while route status still said the
    // facility was a mile away, then never opened the dock. Switching the
    // assist off let the arrival fire eight seconds later. Drive the shipped
    // facility and require the player-visible outcome, not merely a slow
    // truck: hands off once the assist speaks, the dock opens at a crawl.
    let destination = Destination {
        city: "shelby_mt_us".to_string(),
        location: "Shelby Cross-Dock".to_string(),
        state: "MT".to_string(),
        chain: false,
    };
    let arrival = arrive(&destination);

    assert_eq!(
        what_went_wrong(&destination, &arrival),
        None,
        "{}",
        arrival.report(&destination)
    );
    assert!(arrival.docked, "{}", arrival.report(&destination));
    assert!(
        arrival.said("2 miles per hour"),
        "{}",
        arrival.report(&destination)
    );
    assert!(
        arrival.said("Destination approach assistance slowing."),
        "{}",
        arrival.report(&destination)
    );
    assert!(
        arrival.said("Pulling into freight terminal Shelby Cross-Dock")
            && arrival.said("dock menu opening in a moment."),
        "{}",
        arrival.report(&destination)
    );
    assert!(
        !arrival.said("Destination approach stopped and holding."),
        "{}",
        arrival.report(&destination)
    );
}

#[test]
#[ignore = "sweep probe: the same drives, printed rather than asserted"]
fn sweep_probe() {
    let world = get_world();
    let (chain, plain) = destinations(world, PER_KIND);
    let mut bad = 0;
    for d in chain.iter().chain(plain.iter()) {
        let arrival = arrive(d);
        let ok = arrival.ready && arrival.speed_mph <= DOCKING_MAX_MPH && arrival.assist_spoke;
        if !ok {
            bad += 1;
        }
        println!(
            "{:<6} {:<26} {:<44} chain={} onchain={} spoke={} v={:.2} short={:.0}ft              at_point={:?} past={:.0}ft",
            if ok { "ok" } else { "FAIL" },
            d.city,
            d.location,
            d.chain as u8,
            arrival.on_chain as u8,
            arrival.assist_spoke as u8,
            arrival.speed_mph,
            arrival.short_by_ft,
            arrival.speed_at_point_mph.map(|v| (v * 10.0).round() / 10.0),
            arrival.past_the_point_ft,
        );
        if !ok {
            for line in arrival.heard.iter().rev().take(10) {
                println!("      | {line}");
            }
        }
    }
    println!("failures: {bad}");
}
