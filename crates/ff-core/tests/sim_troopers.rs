//! Trooper pull-overs: enforcement posts and the CB heads-up (the pure half
//! of `tests/test_troopers.py`; the interactive roadside stop, tickets,
//! warnings and evasion drive the app shell and are ignored until it lands).

mod sim_support;

use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::trip_models::TripEventKind;
use ff_core::sim::vehicle::TruckState;
use sim_support::*;

fn trip_with(seed: i64, hazard_scale: f64, start_hour: f64) -> Trip {
    let route = first_route_option(world(), "Salt Lake City", "Las Vegas");
    Trip::new(
        route,
        TruckState::default(),
        weather("great_basin", 1),
        TripOptions {
            seed: Some(seed),
            hazard_scale,
            start_hour,
            world: Some(world()),
            ..Default::default()
        },
    )
}

fn trip() -> Trip {
    trip_with(7, 1.0, 12.0)
}

// --- post model -------------------------------------------------------------

fn post_key(t: &Trip) -> Vec<(f64, String, bool)> {
    t.posts
        .iter()
        .map(|p| ((p.at_mi * 10.0).round() / 10.0, p.kind.clone(), p.staffed))
        .collect()
}

#[test]
fn test_post_seeding_is_deterministic() {
    assert_eq!(post_key(&trip()), post_key(&trip()));
}

#[test]
fn test_roving_posts_create_state_trooper_npcs() {
    let t = trip();
    let troopers: Vec<_> = t
        .traffic_manager
        .vehicles
        .iter()
        .filter(|v| v.vehicle_class == "state trooper")
        .collect();
    let roving = t
        .posts
        .iter()
        .filter(|p| p.kind == "roving_patrol" && p.staffed)
        .count();
    assert!(!t.posts.is_empty());
    assert_eq!(troopers.len(), roving);
    assert!(troopers.iter().all(|v| v.reason() == "state trooper ahead"));
}

#[test]
fn test_relaxed_hazards_do_not_thin_the_police() {
    // Presence is a fact about the country, not a difficulty knob.
    assert_eq!(trip_with(7, 0.3, 12.0).posts.len(), trip().posts.len());
}

#[test]
fn test_construction_zones_always_carry_a_work_zone_post() {
    let t = trip();
    if let Some(zone) = t.zones.iter().find(|z| z.reason == "construction") {
        let covering = t
            .posts
            .iter()
            .filter(|p| p.kind == "work_zone_post" && (p.at_mi - zone.start_mi).abs() < 1.0)
            .count();
        assert!(covering > 0);
    }
}

#[test]
fn test_active_post_returns_the_most_attentive_watcher() {
    let mut t = trip();
    let quiet = always_observing_post(50.0, "urban_unit", 1.0, 0.3, 0);
    let loud = always_observing_post(50.0, "work_zone_post", 1.0, 0.9, 0);
    t.posts = vec![quiet, loud.clone()];
    assert_eq!(t.active_post_at(50.0).map(|p| p.id()), Some(loud.id()));
    assert!(t.active_post_at(2000.0).is_none());
}

#[test]
fn test_cb_radio_warns_before_an_upcoming_post() {
    let mut t = trip();
    t.posts = vec![always_observing_post(14.0, "median_post", 4.0, 1.0, 0)];
    let post_id = t.posts[0].id();
    t.position_mi = 10.0 - 0.1;
    t.truck.velocity_mps = 1.0;

    let events = t.update(0.1);

    let cb_events: Vec<_> = events
        .iter()
        .filter(|e| e.data.cb_patrol.as_ref().is_some_and(|p| p.id() == post_id))
        .collect();
    assert!(!cb_events.is_empty());
    assert_eq!(cb_events[0].kind, TripEventKind::GpsCue);
    assert!(cb_events[0].text().contains("CB chatter"));
    assert!(cb_events[0].text().contains("bear"));
}

#[test]
fn test_cb_radio_post_warning_only_fires_once() {
    let mut t = trip();
    t.posts = vec![always_observing_post(14.0, "median_post", 4.0, 1.0, 0)];
    let post_id = t.posts[0].id();
    t.position_mi = 6.0;
    t.truck.velocity_mps = 1.0;

    let first = t.update(0.1);
    let second = t.update(0.1);

    let is_ours = |e: &ff_core::sim::trip_models::TripEvent| {
        e.data.cb_patrol.as_ref().is_some_and(|p| p.id() == post_id)
    };
    assert_eq!(first.iter().filter(|e| is_ours(e)).count(), 1);
    assert!(!second.iter().any(is_ours));
}

// --- driving-side: catching the speeder (app shell) -------------------------

// `test_speeding_past_a_staffed_post_starts_a_pull_over` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

#[test]
#[ignore = "needs app shell (DrivingState pull-over)"]
fn test_metric_pull_over_announcement_uses_metric_units() {}

// `test_speeding_with_no_post_watching_costs_nothing` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

// `test_debug_off_mode_never_pulls_you_over` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

#[test]
#[ignore = "needs app shell (DrivingState pull-over)"]
fn test_stopping_issues_an_immediate_ticket() {}

#[test]
#[ignore = "needs app shell (DrivingState pull-over)"]
fn test_stopping_drops_engine_audio_to_idle() {}

#[test]
#[ignore = "needs app shell (DrivingState pull-over)"]
fn test_metric_traffic_stop_outcome_uses_metric_units() {}

#[test]
#[ignore = "needs app shell (DrivingState pull-over)"]
fn test_first_marginal_stop_is_a_warning() {}

#[test]
#[ignore = "needs app shell (DrivingState pull-over)"]
fn test_accelerating_away_ends_in_a_forced_stop_not_a_felony() {}

#[test]
#[ignore = "needs app shell (DrivingState pull-over)"]
fn test_a_compliant_driver_is_never_charged_with_running() {}

#[test]
#[ignore = "needs app shell (DrivingState pull-over)"]
fn test_failure_to_stop_gives_staged_warnings() {}

#[test]
#[ignore = "needs app shell (DrivingState pull-over)"]
fn test_failure_to_stop_warning_acknowledges_signal() {}

#[test]
#[ignore = "needs app shell (DrivingState pull-over)"]
fn test_felony_stop_cancels_loaded_run_and_returns_to_terminal() {}

#[test]
#[ignore = "needs app shell (DrivingState pull-over)"]
fn test_felony_stop_does_not_claim_load_loss_for_empty_run() {}

#[test]
#[ignore = "needs app shell (DrivingState pull-over)"]
fn test_debug_off_mode_clears_active_pull_over_without_felony() {}

#[test]
#[ignore = "needs app shell (weigh station bypass; seed 1 lands under the 85 percent catch chance)"]
fn test_weigh_station_blow_past_starts_enforcement_stop() {}

#[test]
#[ignore = "needs app shell (weigh station bypass; seed 1 lands under the 85 percent catch chance)"]
fn test_weigh_station_bypass_is_not_certain_and_stays_silent_when_missed() {}

#[test]
#[ignore = "needs app shell (weigh station bypass)"]
fn test_closed_scale_never_charges_a_bypass() {}

#[test]
#[ignore = "needs app shell (weigh station bypass)"]
fn test_weigh_station_warning_is_spoken_before_bypass() {}

#[test]
#[ignore = "needs app shell (weigh station bypass)"]
fn test_debug_off_mode_bypasses_scale_blow_past() {}

#[test]
#[ignore = "needs app shell (weigh station bypass)"]
fn test_scale_bypass_does_not_overwrite_active_pull_over() {}

#[test]
#[ignore = "needs app shell (safety stop)"]
fn test_unsafe_damage_in_patrol_starts_safety_stop() {}

#[test]
#[ignore = "needs app shell (safety stop)"]
fn test_unsafe_damage_needs_active_enforcement() {}

#[test]
#[ignore = "needs app shell (construction zone fines)"]
fn test_the_merge_taper_counts_as_being_in_the_construction_zone() {}

#[test]
#[ignore = "needs app shell (construction zone fines)"]
fn test_roadwork_hides_behind_a_jam_and_still_doubles_the_fine() {}

#[test]
#[ignore = "needs app shell (construction zone fines)"]
fn test_a_scale_bypass_in_roadwork_costs_double_and_says_so() {}

#[test]
#[ignore = "needs app shell (construction zone fines)"]
fn test_a_repeat_scale_bypass_in_roadwork_compounds_rather_than_adds() {}

#[test]
#[ignore = "needs app shell (construction zone fines)"]
fn test_a_speeding_ticket_in_roadwork_doubles_and_the_line_says_the_charge() {}

#[test]
#[ignore = "needs app shell (construction zone fines)"]
fn test_leaving_the_zone_before_stopping_does_not_undo_the_doubling() {}

#[test]
#[ignore = "needs app shell (non-speeding stop escalation)"]
fn test_a_non_speeding_stop_escalates_with_priors() {}

#[test]
#[ignore = "needs app shell (F1 help)"]
fn test_f1_help_names_non_speed_enforcement_pullovers() {}

#[test]
#[ignore = "needs app shell (roadside stop)"]
fn test_braking_to_a_stop_reaches_the_roadside_stop() {}

#[test]
#[ignore = "needs app shell (clean-stop leniency: named, position-quantised seed)"]
fn test_clean_stop_can_waive_a_ticket_to_a_warning() {}

#[test]
#[ignore = "needs app shell (pull-over compliance)"]
fn test_failing_to_signal_takes_a_one_time_deduction() {}

#[test]
#[ignore = "needs app shell (pull-over compliance)"]
fn test_continuous_coasting_slowly_drains_compliance() {}

#[test]
#[ignore = "needs app shell (out-of-service stop)"]
fn test_out_of_service_stop_shuts_down_the_engine() {}

#[test]
#[ignore = "needs app shell (snapshot)"]
fn test_ticket_counters_survive_snapshot() {}
