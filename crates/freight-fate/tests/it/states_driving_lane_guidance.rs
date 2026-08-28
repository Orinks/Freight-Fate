//! Player-proof lane-guidance audio regressions.

use ff_core::sim::lane::CENTERED_MAX;

use freight_fate::playtest::harness::{PlaytestHarness, StartDelivery};

const MPH_PER_MPS: f64 = 2.23694;

#[test]
fn test_lane_keeping_off_manual_correction_chimes_once_at_actual_center() {
    let mut harness = PlaytestHarness::new();
    harness.start_delivery(StartDelivery::named("Manual Lane Correction"));
    let audio = harness.app.record_audio();
    harness.app.ctx.settings.lane_keeping = "off".to_string();
    harness.app.ctx.settings.lane_departure_warning = true;
    harness.app.ctx.settings.lane_guide_tone = false;

    harness.with_drive(|drive, ctx| {
        drive.trip.curves.clear();
        drive.trip.truck.start_engine();
        drive.trip.truck.velocity_mps = 55.0 / MPH_PER_MPS;

        drive.lane.offset = 0.7;
        drive.update_lane_guidance_audio(ctx, 0.1);
        drive.lane.offset = CENTERED_MAX + 0.04;
        drive.update_lane_guidance_audio(ctx, 0.1);
    });
    assert!(audio
        .borrow()
        .played
        .iter()
        .all(|(key, _, _)| key != "vehicle/lane_centered"));

    harness.with_drive(|drive, ctx| {
        drive.lane.offset = CENTERED_MAX - 0.01;
        drive.update_lane_guidance_audio(ctx, 0.1);
        drive.lane.offset = 0.0;
        drive.update_lane_guidance_audio(ctx, 0.1);
    });
    let chimes = audio
        .borrow()
        .played
        .iter()
        .filter(|(key, _, _)| key == "vehicle/lane_centered")
        .count();
    assert_eq!(chimes, 1);
}
