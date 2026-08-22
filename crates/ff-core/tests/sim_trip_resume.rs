//! Mid-trip save and resume: snapshot, persistence, and the continue flow
//! (port of `tests/test_trip_resume.py`). Every case but the last drives
//! the App shell and waits for it.

mod sim_support;

use sim_support::*;

#[test]
#[ignore = "needs app shell (DrivingState.snapshot / from_snapshot)"]
fn test_active_drive_snapshot_restores_idling_engine() {}

#[test]
#[ignore = "needs app shell (DrivingState.snapshot / from_snapshot)"]
fn test_active_drive_snapshot_restores_paused_speed_control_session() {}

#[test]
#[ignore = "needs app shell (DrivingState.from_snapshot with a live weather provider)"]
fn test_resumed_drive_reports_old_fresh_observation_as_live() {}

#[test]
#[ignore = "needs app shell (quit to menu, HOS checkpoint)"]
fn test_quit_mid_drive_restores_checkpoint_hos_and_fatigue() {}

#[test]
#[ignore = "needs app shell (quit to menu, continue)"]
fn test_quit_mid_drive_resumes_from_the_last_stop() {}

#[test]
#[ignore = "needs app shell (resumed DrivingState first idle frame)"]
fn test_resumed_trip_does_not_replay_passed_announcements() {}

#[test]
#[ignore = "needs app shell (delivery clears the saved trip)"]
fn test_delivery_clears_the_saved_trip() {}

#[test]
#[ignore = "needs app shell (abandon job)"]
fn test_abandoning_clears_the_saved_trip() {}

#[test]
#[ignore = "needs app shell (abandon job keeps the hours)"]
fn test_abandoning_keeps_the_hours_spent_driving() {}

#[test]
#[ignore = "needs app shell (pause menu pacing change)"]
fn test_trip_pacing_change_applies_to_the_active_trip() {}

#[test]
#[ignore = "needs app shell (weather source change)"]
fn test_weather_source_change_applies_to_the_active_trip() {}

#[test]
#[ignore = "needs app shell (live weather calendar change)"]
fn test_live_weather_calendar_change_applies_to_active_trip() {}

#[test]
#[ignore = "needs app shell (arrival summary)"]
fn test_arrival_summary_calls_out_on_time_delivery_bonus() {}

#[test]
#[ignore = "needs app shell and models::profile (snapshot roundtrip)"]
fn test_snapshot_survives_profile_roundtrip() {}

#[test]
#[ignore = "needs app shell (snapshot air brake state)"]
fn test_snapshot_roundtrip_preserves_air_brake_state() {}

#[test]
#[ignore = "needs app shell (corrupt snapshot fallback)"]
fn test_corrupt_snapshot_falls_back_to_city() {}

#[test]
#[ignore = "needs app shell (old map snapshot)"]
fn test_old_map_snapshot_still_resumes() {}

#[test]
#[ignore = "needs app shell (old active trip deadline floor)"]
fn test_old_active_trip_gets_deadline_floor_and_model_marker() {}

#[test]
#[ignore = "needs app shell (active trip deadline across resumes)"]
fn test_current_active_trip_keeps_its_deadline_across_resumes() {}

#[test]
#[ignore = "needs app shell (resumed drive advances the calendar)"]
fn test_resumed_drive_advances_the_calendar_by_the_time_already_driven() {}

#[test]
#[ignore = "needs app shell (bare city job snapshot)"]
fn test_bare_city_job_snapshot_gets_facility_fallback() {}

#[test]
fn test_route_from_cities_roundtrip() {
    let w = world();
    let route = w
        .shortest_route("Chicago", "Denver", None, false)
        .unwrap()
        .expect("a route");
    let rebuilt = w
        .route_from_cities(&route.cities)
        .expect("the same cities rebuild the route");
    assert_eq!(rebuilt.cities, route.cities);
    let ids = |r: &ff_core::data::world_models::Route| {
        r.legs
            .iter()
            .map(|l| (l.a.clone(), l.b.clone(), l.miles))
            .collect::<Vec<_>>()
    };
    assert_eq!(ids(&rebuilt), ids(&route));
    assert!(w.route_from_cities(&["Chicago"]).is_none());
    assert!(w.route_from_cities(&["Chicago", "Not A City"]).is_none());
}
