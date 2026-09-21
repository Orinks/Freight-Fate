//! Accepting a load dispatch relayed from a nearby city (`jobs::relay`,
//! `JobBoardState::accept_relay`): the deadhead corridor and the shipper's
//! approach are one pickup drive, the offer says the deadhead comes first,
//! and a save on the way rebuilds the same road.

use ff_core::models::jobs::Job;

use freight_fate::app::testing::TestApp;
use freight_fate::states::city::{
    describe_job, dispatch_cache_key, relay_load_for_board, JobBoardState, DRIVE_PHASE_PICKUP,
};
use freight_fate::states::driving::DrivingState;

use crate::states_city_support::*;

/// A company driver one delivery in, parked in `city`, and the load
/// dispatch relays onto an empty board there.
fn relayed_load(app: &mut TestApp, city: &str) -> Option<Job> {
    career(app, "Relay Driver", city);
    app.ctx
        .profile
        .as_mut()
        .expect("a career")
        .career
        .deliveries = 1;
    let key = dispatch_cache_key(profile(app));
    relay_load_for_board(&app.ctx, &key, &[])
}

#[test]
fn test_accepting_a_relayed_load_drives_the_deadhead_and_the_approach_as_one_pickup() {
    let mut app = TestApp::new();
    let mut job = None;
    for city in ["Sherman", "Topeka", "Cheyenne", "Amarillo", "Bismarck"] {
        job = relayed_load(&mut app, city);
        if job.is_some() {
            break;
        }
    }
    let job = job.expect("one of the small towns relays a load off an empty board");
    let world = app.ctx.world;
    let here = world.resolve_city_key(&profile(&app).current_city);
    let origin = world.resolve_city_key(&job.origin);
    assert_ne!(origin, here);

    // The offer says the deadhead comes first.
    let text = describe_job(&app.ctx, 1, &job, Some(1));
    assert!(
        text.contains(&format!("Load waiting in {}", job.spoken_origin())),
        "{text}"
    );
    assert!(
        text.contains("deadhead first, paid at the empty-mile rate"),
        "{text}"
    );

    let mut board = JobBoardState::new(&app.ctx, vec![job.clone()]);
    app.clear_speech();
    board.accept(&mut app.ctx, 0);
    app.ctx.run_deferred();
    assert!(is::<DrivingState>(&app), "the accept launched a drive");
    let announced = app.main_lines().join(" ");
    assert!(announced.contains("Load waiting at"), "{announced}");
    assert!(announced.contains("deadhead"), "{announced}");

    let (phase, cities) = with_state::<DrivingState, _>(&app, |d, _| {
        (d.phase.to_string(), d.trip.route.cities.clone())
    });
    assert_eq!(phase, DRIVE_PHASE_PICKUP);
    // Corridor from here to the shipper's city, then that city's approach:
    // the city appears at the join and again at the very end.
    assert_eq!(cities.first(), Some(&here), "{cities:?}");
    assert_eq!(cities.last(), Some(&origin), "{cities:?}");
    assert!(cities.len() > 2, "{cities:?}");
    if world
        .facility_approach_route(&origin, &job.origin_location)
        .is_ok()
    {
        assert_eq!(cities[cities.len() - 2], origin, "{cities:?}");
    }

    // A save mid-deadhead rebuilds the same road.
    let snapshot = with_state::<DrivingState, _>(&app, |d, ctx| d.snapshot(ctx));
    assert_eq!(snapshot["route_kind"], "deadhead_approach");
    let resumed = DrivingState::from_snapshot(&mut app.ctx, &snapshot).expect("resumes");
    assert_eq!(resumed.trip.route.cities, cities);
    assert_eq!(resumed.phase.to_string(), DRIVE_PHASE_PICKUP);
}
