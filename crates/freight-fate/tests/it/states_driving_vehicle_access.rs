//! The job's rig reaches the trip (the app-shell case of
//! `tests/test_vehicle_access.py`; the model, the placement and the cues are
//! in `crates/ff-core/tests/sim_vehicle_access.rs`).

use ff_core::models::jobs::{JobBoard, OfferOptions};
use ff_core::models::profile::Profile;
use freight_fate::app::testing::TestApp;
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::DRIVE_PHASE_DELIVERY;

/// Everything in `sim_vehicle_access.rs` rests on the job's rig reaching the
/// trip. A real dispatch, not a hand-built `Trip`, so the wiring itself is
/// under test.
#[test]
fn test_the_job_decides_what_the_trip_can_reach() {
    for bobtail in [false, true] {
        let mut app = TestApp::new();
        app.ctx.profile = Some(Profile::named_in("Access Rails", "Chicago"));
        let (endorsements, level, market, city) = {
            let p = app.ctx.profile.as_ref().expect("a career");
            (
                p.career
                    .endorsements()
                    .iter()
                    .copied()
                    .collect::<Vec<&str>>(),
                p.career.level(),
                p.market.clone(),
                p.current_city.clone(),
            )
        };
        let mut board = JobBoard::new(app.ctx.world, None, None);
        let offers = board.offers(
            &city,
            &endorsements,
            OfferOptions {
                level,
                market: Some(&market),
                ..OfferOptions::default()
            },
        );
        let mut job = offers
            .into_iter()
            .find(|offer| {
                offer
                    .locked_reason(&endorsements, level, None, false)
                    .is_empty()
            })
            .expect("the board offered something this driver can take");
        job.bobtail = bobtail;
        let route = app
            .ctx
            .world
            .supported_route_options(&job.origin, &job.destination, 3)
            .expect("the world routes")
            .into_iter()
            .next()
            .expect("the dispatch lane is supported");

        let driving = DrivingState::new(&mut app.ctx, job, route, None, DRIVE_PHASE_DELIVERY, None);

        assert_eq!(driving.trip.bobtail, bobtail);
    }
}
