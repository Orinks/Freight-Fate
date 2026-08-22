//! PrePass-style weigh-in-motion bypass: the transponder gate and verdicts
//! (port of `tests/test_weigh_station_transponder.py`). The gate lives in
//! `models::business` / `models::profile` (wave 2) and the verdict mechanic
//! in the app shell; every case waits for those.

#[test]
#[ignore = "needs models::business and models::profile (has_weigh_station_transponder)"]
fn test_company_driver_below_level_four_has_no_transponder() {}

#[test]
#[ignore = "needs models::business and models::profile (has_weigh_station_transponder)"]
fn test_company_driver_at_level_four_gets_a_free_transponder() {}

#[test]
#[ignore = "needs models::business and models::profile (weigh_station_transponder_eligibility)"]
fn test_owner_operator_needs_the_purchased_subscription_not_just_level() {}

#[test]
#[ignore = "needs models::business and models::jobs (owner_operator_charges)"]
fn test_transponder_settlement_charge_only_when_subscribed() {}

#[test]
#[ignore = "needs app shell (transponder verdict in DrivingState)"]
fn test_below_the_gate_the_scale_still_demands_every_truck() {}

#[test]
#[ignore = "needs app shell (transponder verdict in DrivingState)"]
fn test_transponder_green_bypasses_without_a_charge() {}

#[test]
#[ignore = "needs app shell (transponder verdict in DrivingState)"]
fn test_transponder_red_pulls_in_like_the_old_flow() {}

#[test]
#[ignore = "needs app shell (transponder verdict in DrivingState)"]
fn test_overweight_load_is_always_red_lighted() {}

#[test]
#[ignore = "needs app shell (transponder verdict seeded off trip seed and stop)"]
fn test_transponder_verdict_is_seeded_off_trip_seed_and_stop() {}
