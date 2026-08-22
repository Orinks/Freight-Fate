//! Weather system tests.
//!
//! Ported from `tests/test_weather_trip.py` (every test; the ones that need
//! the trip simulation, the world data, the truck or the app shell are
//! `#[ignore]`d with the dependency named), the pure `WeatherSystem` + fake
//! provider tests of `tests/test_real_weather.py` (the rest need the NWS
//! provider in `sim::real_weather`), and a pin on `fmt_g`, the private
//! Python `%g` formatter `describe` uses for visibility.

use super::test_support::{env_write, new_system};
use super::*;
use crate::sim::season::CAREER_START_DAY_OF_YEAR;
use std::collections::HashSet;

fn system(region: &str, seed: i64) -> WeatherSystem {
    new_system(region, Some(seed), None, None, true)
}

fn system_at(region: &str, seed: i64, game_hours: f64) -> WeatherSystem {
    new_system(region, Some(seed), None, Some(game_hours), true)
}

fn with_provider(region: &str, seed: i64, provider: Box<dyn WeatherProvider>) -> WeatherSystem {
    new_system(region, Some(seed), Some(provider), None, true)
}

// -- tests/test_weather_trip.py ---------------------------------------------

#[test]
fn test_all_conditions_have_effects() {
    for kind in WeatherKind::ALL {
        assert!(EFFECTS.iter().any(|(k, _)| *k == kind));
        let _ = effects(kind);
    }
}

/// The surface field keys the traction-equipment ladder, so every row must
/// use one of the four words the physics understands.
#[test]
fn test_every_condition_names_a_real_surface() {
    for (kind, eff) in EFFECTS {
        assert!(
            ["dry", "wet", "snow", "ice"].contains(&eff.surface),
            "{kind:?}"
        );
    }
    assert_eq!(effects(WeatherKind::Snow).surface, "snow");
    assert_eq!(effects(WeatherKind::Ice).surface, "ice");
    assert_eq!(effects(WeatherKind::Rain).surface, "wet");
    assert_eq!(effects(WeatherKind::Clear).surface, "dry");
}

/// Conditions seen across a run with the career clock set to a season.
fn season_conditions(region: &str, game_hours: f64) -> HashSet<WeatherKind> {
    let mut ws = system_at(region, 5, game_hours);
    let mut seen = HashSet::from([ws.current]);
    for _ in 0..400 {
        ws.update(60.0); // advance about an hour per step
        seen.insert(ws.current);
    }
    seen
}

#[test]
fn test_summer_runs_have_no_snow() {
    let summer_hours = (200.0 - CAREER_START_DAY_OF_YEAR) * 24.0; // mid July
    let seen = season_conditions("great_lakes", summer_hours);
    assert!(!seen.contains(&WeatherKind::Snow));
}

#[test]
fn test_winter_runs_have_snow_but_no_thunderstorms() {
    let winter_hours = (15.0 - CAREER_START_DAY_OF_YEAR).rem_euclid(365.0) * 24.0; // mid January
    let seen = season_conditions("great_lakes", winter_hours);
    assert!(seen.contains(&WeatherKind::Snow));
    assert!(!seen.contains(&WeatherKind::Thunderstorm));
}

#[test]
fn test_seasonal_weather_is_deterministic_with_seed() {
    let winter_hours = (15.0_f64 - 80.0).rem_euclid(365.0) * 24.0;
    let mut a = system_at("rockies", 11, winter_hours);
    let mut b = system_at("rockies", 11, winter_hours);
    for _ in 0..80 {
        assert_eq!(a.update(45.0), b.update(45.0));
    }
    assert_eq!(a.current, b.current);
    assert_eq!(a.season(), b.season());
    assert_eq!(a.season(), Some("winter"));
}

#[test]
fn test_seasons_off_by_default_leaves_temperature_unknown() {
    let mut ws = system("heartland", 1);
    assert_eq!(ws.game_hours, None);
    assert_eq!(ws.temperature_c(), None);
    assert_eq!(ws.season(), None);
}

#[test]
fn test_weather_is_deterministic_with_seed() {
    let mut a = system("great_lakes", 7);
    let mut b = system("great_lakes", 7);
    for _ in 0..50 {
        assert_eq!(a.update(13.0), b.update(13.0));
    }
    assert_eq!(a.current, b.current);
}

#[test]
fn test_weather_eventually_changes() {
    let mut ws = system("pacific_northwest", 3);
    let changes: Vec<Option<WeatherKind>> = (0..200).map(|_| ws.update(15.0)).collect();
    assert!(changes.iter().any(|c| c.is_some()));
}

#[test]
fn test_bad_weather_reduces_grip() {
    assert!(effects(WeatherKind::Snow).grip < effects(WeatherKind::Clear).grip);
    assert!(effects(WeatherKind::HeavyRain).grip < effects(WeatherKind::Rain).grip);
}

#[test]
fn test_forecast_returns_requested_segments() {
    let mut ws = system("atlantic_southeast", 1);
    assert_eq!(ws.forecast(3).len(), 3);
}

/// Pressing V speaks a forecast; it must not change future weather.
#[test]
fn test_forecast_does_not_regenerate_weather_timeline() {
    let mut with_forecast = system("great_lakes", 9);
    let mut untouched = system("great_lakes", 9);
    for _ in 0..5 {
        assert_eq!(with_forecast.forecast(2).len(), 2);
    }
    for _ in 0..80 {
        assert_eq!(with_forecast.update(10.0), untouched.update(10.0));
    }
    assert_eq!(with_forecast.current, untouched.current);
}

#[test]
fn test_force_weather_override_locks_condition() {
    const VAR: &str = "FREIGHT_FATE_FORCE_WEATHER";
    let _guard = env_write();
    std::env::set_var(VAR, "snow");
    let mut ws = WeatherSystem::new("heartland", Some(1), None, None, true);
    assert_eq!(ws.current, WeatherKind::Snow);
    for _ in 0..200 {
        // never drifts off the forced condition
        ws.update(30.0);
        assert_eq!(ws.current, WeatherKind::Snow);
    }

    std::env::set_var(VAR, "heavy_rain");
    assert_eq!(
        WeatherSystem::new("heartland", Some(1), None, None, true).current,
        WeatherKind::HeavyRain
    );
    std::env::remove_var(VAR);
    std::env::set_var(VAR, "bogus");
    assert_eq!(
        WeatherSystem::new("heartland", Some(1), None, None, true).forced,
        None
    );
    std::env::remove_var(VAR);
}

#[test]
fn test_force_weather_accepts_every_python_spelling() {
    const VAR: &str = "FREIGHT_FATE_FORCE_WEATHER";
    let _guard = env_write();
    for (spelling, kind) in [
        ("ICE", WeatherKind::Ice),
        ("freezing rain", WeatherKind::Ice),
        ("freezing_rain", WeatherKind::Ice),
        (" Heavy Rain ", WeatherKind::HeavyRain),
        ("high_winds", WeatherKind::Wind),
        ("wind", WeatherKind::Wind),
    ] {
        std::env::set_var(VAR, spelling);
        assert_eq!(forced_weather(), Some(kind), "{spelling:?}");
    }
    std::env::set_var(VAR, "   ");
    assert_eq!(forced_weather(), None);
    std::env::remove_var(VAR);
    assert_eq!(forced_weather(), None);
}

// -- tests/test_real_weather.py: the pure WeatherSystem + fake-provider tests --

struct ConditionsOnlyProvider;

impl WeatherProvider for ConditionsOnlyProvider {
    fn request(&mut self, _city: &str, _lat: f64, _lon: f64) {}

    fn get(&mut self, _city: &str) -> Option<WeatherKind> {
        Some(WeatherKind::HeavyRain)
    }

    fn stale(&mut self, _city: &str) -> bool {
        false
    }

    fn unavailable(&mut self, _city: &str) -> bool {
        false
    }
}

#[test]
fn test_live_report_omits_modeled_temperature_when_observation_has_none() {
    let mut ws = with_provider("desert_southwest", 1, Box::new(ConditionsOnlyProvider));
    ws.set_city("route-cell", 33.45, -112.07);
    ws.update(1.0);

    assert_eq!(ws.source_status(), "live");
    assert!(ws.temperature_c().is_some()); // The seasonal model remains available to mechanics.
    assert!(!ws.report_lead(true).contains("degrees"));
    assert!(!ws.source_conditions(true).contains("degrees"));
    assert!(!ws.source_conditions(true).contains("visibility"));
    assert!(!ws.source_conditions(true).contains("slick roads"));
}

/// Per-cell readings the test rewrites between ticks; the `Rc<RefCell>` is
/// the Python test reaching into the provider object it still holds.
type SharedReadings =
    std::rc::Rc<std::cell::RefCell<std::collections::HashMap<String, Option<WeatherKind>>>>;

struct LocationProvider {
    data: SharedReadings,
}

impl WeatherProvider for LocationProvider {
    fn request(&mut self, _city: &str, _lat: f64, _lon: f64) {}

    fn get(&mut self, city: &str) -> Option<WeatherKind> {
        self.data.borrow().get(city).copied().flatten()
    }

    fn stale(&mut self, _city: &str) -> bool {
        false
    }

    fn unavailable(&mut self, _city: &str) -> bool {
        false
    }
}

#[test]
fn test_late_observation_for_previous_route_cell_cannot_replace_current_cell() {
    let data: SharedReadings = Default::default();
    data.borrow_mut().insert("cell-a".to_string(), None);
    data.borrow_mut()
        .insert("cell-b".to_string(), Some(WeatherKind::Rain));
    let provider = LocationProvider { data: data.clone() };
    let mut ws = with_provider("great_lakes", 1, Box::new(provider));
    ws.set_city("cell-a", 41.0, -87.0);
    ws.update(0.0);
    ws.set_city("cell-b", 40.0, -86.0);
    ws.update(0.0);
    assert_eq!(ws.current, WeatherKind::Rain);

    data.borrow_mut()
        .insert("cell-a".to_string(), Some(WeatherKind::HeavyRain));
    ws.update(0.0);
    assert_eq!(ws.city.as_deref(), Some("cell-b"));
    assert_eq!(ws.current, WeatherKind::Rain);
}

struct Pending;

impl WeatherProvider for Pending {
    fn request(&mut self, _city: &str, _lat: f64, _lon: f64) {}

    fn get(&mut self, _city: &str) -> Option<WeatherKind> {
        None
    }

    fn unavailable(&mut self, _city: &str) -> bool {
        false // still fetching, not offline
    }
}

/// With a provider attached, weather starts clear and holds -- no simulated
/// warm-up -- until live data (or a confirmed offline state) arrives.
#[test]
fn test_weather_system_holds_clear_while_live_data_pending() {
    let mut ws = with_provider("pacific_northwest", 1, Box::new(Pending));
    ws.set_city("Seattle", 47.61, -122.33);
    assert_eq!(ws.current, WeatherKind::Clear);
    for _ in 0..200 {
        assert_eq!(ws.update(30.0), None); // no simulated transitions while pending
    }
    assert_eq!(ws.current, WeatherKind::Clear);
    assert!(!ws.live);
}

#[test]
fn test_weather_system_without_provider_unchanged() {
    let mut ws = system("great_lakes", 3);
    ws.update(1.0);
    assert!(!ws.live);
}

/// A provider that is offline from the first tick (the shape of
/// `SyncProvider(fetch=raise OSError)` in the Python tests, minus the NWS
/// machinery): the system must fall back to simulated weather and say so.
struct Offline;

impl WeatherProvider for Offline {
    fn request(&mut self, _city: &str, _lat: f64, _lon: f64) {}

    fn get(&mut self, _city: &str) -> Option<WeatherKind> {
        None
    }

    fn unavailable(&mut self, _city: &str) -> bool {
        true
    }
}

#[test]
fn test_weather_system_falls_back_when_offline() {
    let mut ws = with_provider("great_lakes", 2, Box::new(Offline));
    ws.set_city("Chicago", 41.88, -87.63);
    let changes: Vec<Option<WeatherKind>> = (0..200).map(|_| ws.update(15.0)).collect();
    assert!(!ws.live);
    assert!(changes.iter().any(|c| c.is_some())); // simulated weather still evolves
    assert_eq!(ws.source_status(), "fallback");
    assert!(ws
        .report_lead(true)
        .starts_with("Simulated fallback weather: "));
    assert_eq!(ws.observation_age_value(), "not applicable");
}

/// A stable live feed with a temperature and an observation age: the spoken
/// report lines, end to end, without the NWS provider.
struct SteadyRain {
    age_s: f64,
    refreshing: bool,
}

impl WeatherProvider for SteadyRain {
    fn request(&mut self, _city: &str, _lat: f64, _lon: f64) {}

    fn get(&mut self, _city: &str) -> Option<WeatherKind> {
        Some(WeatherKind::Rain)
    }

    fn get_temperature(&mut self, _city: &str) -> Option<f64> {
        Some(18.0)
    }

    fn observation_age_s(&mut self, _city: &str) -> Option<f64> {
        Some(self.age_s)
    }

    fn refreshing(&mut self, _city: &str) -> bool {
        self.refreshing
    }
}

#[test]
fn test_live_report_lines_read_the_station_back() {
    let provider = SteadyRain {
        age_s: 12.0 * 60.0,
        refreshing: false,
    };
    let mut ws = with_provider("great_lakes", 1, Box::new(provider));
    ws.set_city("Chicago", 41.88, -87.63);
    assert_eq!(ws.update(1.0), Some(WeatherKind::Rain));
    assert!(ws.live);
    assert_eq!(ws.source_status(), "live");
    assert_eq!(ws.temperature_c(), Some(18.0));
    // 18 C -> 64.4 F -> "64".
    assert_eq!(ws.source_conditions(true), "rain, 64 degrees");
    assert_eq!(ws.source_conditions(false), "rain, 18 degrees Celsius");
    assert_eq!(
        ws.report_lead(true),
        "Live weather: rain, 64 degrees, near your current route position. \
         The observation is 12 minutes old"
    );
    assert_eq!(ws.observation_age_value(), "12 minutes old");
    assert_eq!(ws.event_source_label(), "Live weather");
    assert_eq!(ws.conditions_label(), "Live conditions");
    assert!(!ws.has_simulated_forecast());
    assert_eq!(ws.describe(true, false), "rain, 64 degrees");
    // Stable live data: no further changes, simulation stays paused.
    for _ in 0..100 {
        assert_eq!(ws.update(30.0), None);
    }
}

#[test]
fn test_observation_age_text_rounds_down_to_whole_minutes() {
    let mut ws = with_provider(
        "great_lakes",
        1,
        Box::new(SteadyRain {
            age_s: 59.0,
            refreshing: false,
        }),
    );
    ws.set_city("Chicago", 41.88, -87.63);
    assert_eq!(
        ws.observation_age_text().as_deref(),
        Some("The observation is less than a minute old")
    );
    assert_eq!(ws.observation_age_value(), "less than a minute old");

    let mut ws = with_provider(
        "great_lakes",
        1,
        Box::new(SteadyRain {
            age_s: 119.0,
            refreshing: true,
        }),
    );
    ws.set_city("Chicago", 41.88, -87.63);
    assert_eq!(
        ws.observation_age_text().as_deref(),
        Some("The observation is 1 minute old")
    );
    assert_eq!(
        ws.last_known_notice(),
        "The observation is 1 minute old. Live weather is updating for your current location"
    );
    // No city tracked: nothing to age.
    let mut ws = with_provider(
        "great_lakes",
        1,
        Box::new(SteadyRain {
            age_s: 0.0,
            refreshing: false,
        }),
    );
    assert_eq!(ws.observation_age_text(), None);
    assert_eq!(ws.last_known_notice(), "Observation age is unavailable");
    assert_eq!(
        ws.live_observation_notice(),
        "Observation age is unavailable"
    );
    assert_eq!(ws.observation_age_value(), "unavailable");
    assert!(ws.live_weather_loading());
    assert_eq!(ws.source_status(), "loading");
    assert_eq!(ws.source_conditions(true), "neutral conditions");
    assert_eq!(
        ws.report_lead(true),
        "Live weather is loading for your current route position. \
         Temporary neutral driving conditions are in use"
    );
}

// -- describe(): the spoken condition line ----------------------------------

#[test]
fn test_describe_reads_visibility_with_python_g_formatting() {
    let _guard = env_write();
    std::env::set_var("FREIGHT_FATE_FORCE_WEATHER", "fog");
    let mut fog = WeatherSystem::new("heartland", Some(1), None, None, true);
    std::env::set_var("FREIGHT_FATE_FORCE_WEATHER", "thunderstorm");
    let mut storm = WeatherSystem::new("heartland", Some(1), None, None, true);
    std::env::set_var("FREIGHT_FATE_FORCE_WEATHER", "heavy rain");
    let mut heavy = WeatherSystem::new("heartland", Some(1), None, None, true);
    std::env::set_var("FREIGHT_FATE_FORCE_WEATHER", "ice");
    let mut ice = WeatherSystem::new("heartland", Some(1), None, None, true);
    std::env::remove_var("FREIGHT_FATE_FORCE_WEATHER");
    drop(_guard);

    assert_eq!(fog.describe(true, false), "fog, visibility 0.3 miles");
    assert_eq!(
        fog.describe(false, false),
        "fog, visibility 0.482803 kilometers"
    );
    assert_eq!(
        storm.describe(true, false),
        "thunderstorm, visibility 1 miles, slick roads"
    );
    assert_eq!(
        storm.describe(false, false),
        "thunderstorm, visibility 1.60934 kilometers, slick roads"
    );
    assert_eq!(
        heavy.describe(true, false),
        "heavy rain, visibility 1.5 miles, slick roads"
    );
    assert_eq!(
        heavy.describe(false, false),
        "heavy rain, visibility 2.41402 kilometers, slick roads"
    );
    assert_eq!(ice.describe(true, false), "freezing rain, ice on the road");
}

#[test]
fn test_fmt_g_matches_python_format_g() {
    assert_eq!(fmt_g(0.3), "0.3");
    assert_eq!(fmt_g(1.0), "1");
    assert_eq!(fmt_g(1.5), "1.5");
    assert_eq!(fmt_g(0.3 * 1.609344), "0.482803");
    assert_eq!(fmt_g(1.5 * 1.609344), "2.41402");
    assert_eq!(fmt_g(1.0 * 1.609344), "1.60934");
    assert_eq!(fmt_g(0.0), "0");
    assert_eq!(fmt_g(100000.0), "100000");
    assert_eq!(fmt_g(1000000.0), "1e+06");
    assert_eq!(fmt_g(0.0001), "0.0001");
    assert_eq!(fmt_g(0.00001), "1e-05");
    assert_eq!(fmt_g(123456789.0), "1.23457e+08");
    assert_eq!(fmt_g(-2.5), "-2.5");
}

#[test]
fn test_weather_kind_round_trips_its_spoken_value() {
    for kind in WeatherKind::ALL {
        assert_eq!(WeatherKind::from_value(kind.value()), Some(kind));
    }
    assert_eq!(WeatherKind::from_value("drizzle"), None);
    assert_eq!(WeatherKind::Ice.value(), "freezing rain");
    assert_eq!(WeatherKind::HeavyRain.name(), "HEAVY_RAIN");
    assert_eq!(region_weights("atlantis"), &DEFAULT_WEIGHTS[..]);
    assert_eq!(region_weights("heartland"), &DEFAULT_WEIGHTS[..]);
    assert_eq!(REGION_WEIGHTS.len(), 16);
}

#[test]
fn test_forecast_weights_append_an_unlisted_current_kind_last() {
    // Freezing rain is not in any region table; `weights[cur] = ... * 2.5`
    // appends it at the end of the dict, which is where random.choices saw
    // it. The draw order is what makes a seeded forecast reproducible.
    let mut weights: Vec<(WeatherKind, f64)> = region_weights("heartland").to_vec();
    set_weight(&mut weights, WeatherKind::Ice, |w| w.unwrap_or(1.0) * 2.5);
    assert_eq!(weights.len(), 9);
    assert_eq!(weights[8], (WeatherKind::Ice, 2.5));
    set_weight(&mut weights, WeatherKind::Clear, |w| w.unwrap_or(1.0) * 2.5);
    assert_eq!(weights[0], (WeatherKind::Clear, 10.0));
    assert_eq!(weights.len(), 9);
}

// -- the rest of tests/test_weather_trip.py, waiting on their dependencies --

#[test]
#[ignore = "needs data::world"]
fn test_all_regions_in_world_have_weights() {
    // TODO(port): port once the Rust data::world is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_route_weather_coordinates_follow_multiple_points_on_long_leg() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_route_weather_coordinates_reverse_with_travel_direction() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_route_weather_location_switches_at_multi_leg_boundary() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_normal_route_cell_refresh_is_silent_and_failures_hold_last_known() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_live_change_omits_modeled_temperature_and_does_not_hide_later_stale_status() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_freshly_fetched_old_observation_change_stays_live_and_announces_age() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_offline_live_weather_change_is_identified_as_simulated_fallback() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_relaxed_hazard_scale_lowers_hazard_risk() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_corridor_busyness_scales_hazard_check_frequency() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_hazard_check_interval_shortens_on_busy_corridors() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_relaxed_mode_thins_traffic_density() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_relaxed_mode_reduces_merge_exit_pressure() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_relaxed_mode_thins_random_inspection_odds() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs sim::trip (corridor_speed_limit)"]
fn test_corridor_speed_limit_by_highway_and_region() {
    // TODO(port): port once the Rust sim::trip (corridor_speed_limit) is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_speed_limit_varies_by_corridor_and_drops_in_cities() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_speed_limit_change_is_announced_crossing_out_of_a_city() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_speed_limit_cue_names_direction_and_city() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_speed_limit_drop_behind_a_city_says_leaving() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs sim::vehicle (TruckState)"]
fn test_weather_drag_multiplier_increases_resistance() {
    // TODO(port): port once the Rust sim::vehicle (TruckState) is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_visibility_shortens_hazard_reaction() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_too_fast_for_conditions_risks_traction_loss() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_trip_completes_and_emits_arrival() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_trip_announces_stops_ahead() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_trip_uses_explicit_stop_positions() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_trip_uses_only_curated_pois_at_runtime() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_trip_places_reverse_route_stops_from_travel_direction() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_zone_speed_limits_apply() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_delivery_final_miles_use_facility_approach_limits() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_the_last_three_miles_are_not_a_thirty_five_wall() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_the_destination_approach_starts_where_the_shed_needs_it() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_a_facility_with_a_longer_approach_road_gets_a_longer_zone() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_the_facility_gate_zone_is_unchanged() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_the_approach_speaks_no_more_often_than_it_used_to() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_pickup_deadhead_route_uses_local_facility_limits() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_driving_through_a_city_lists_its_stops_once() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_a_merged_city_stop_keeps_an_exit_label() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_signaling_for_a_namesake_does_not_pass_as_taking_the_planned_exit() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_a_plan_survives_passing_a_stop_that_shares_its_name() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_every_stop_announces_even_when_names_repeat() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_facility_gate_warns_before_final_low_speed_zone() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_zone_entry_is_worded_apart_from_its_advance_warning() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_construction_zone_warns_before_entry() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_construction_zone_has_staged_merge_taper() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_construction_warning_lead_allows_normal_braking() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_construction_zone_does_not_fine_on_entry_tick() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_construction_zone_speeding_fine_waits_for_grace_distance() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_late_emergency_brake_can_save_construction_speeding() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_grades_are_bounded() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_route_derived_flat_grade_is_stable_across_trip_seeds() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_traffic_varies_by_seed_but_route_grade_does_not() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_npc_traffic_model_applies_to_enriched_and_legacy_routes() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_npc_traffic_seeding_is_deterministic() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_npc_traffic_moves_each_trip_tick() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_npc_vehicles_property_tracks_traffic_manager() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_bad_weather_slows_modeled_traffic() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_rush_hour_can_slow_modeled_traffic() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_traffic_pressure_marks_exit_and_construction_context() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_merge_traffic_pressures_drop_the_speed_advisory() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_traffic_pressure_gps_cue_deduplicates() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_npc_traffic_cue_and_status_are_reviewable() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_metric_toggle_updates_npc_traffic_cue_units() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_metric_toggle_updates_npc_traffic_cue_speed_units() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_npc_traffic_status_includes_speed_units() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_time_scale_compresses_fuel_burn() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_clock_compression_ramps_with_road_speed() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_parking_brake_waiting_runs_at_double_pacing() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs sim::trip (eligible_hazards)"]
fn test_every_region_has_clear_day_hazards() {
    // TODO(port): port once the Rust sim::trip (eligible_hazards) is available.
}

#[test]
#[ignore = "needs sim::trip (eligible_hazards)"]
fn test_weather_and_terrain_gate_hazards() {
    // TODO(port): port once the Rust sim::trip (eligible_hazards) is available.
}

#[test]
#[ignore = "needs sim::trip (eligible_hazards)"]
fn test_wildlife_is_biased_to_dawn_dusk_and_night() {
    // TODO(port): port once the Rust sim::trip (eligible_hazards) is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_upcoming_stop_only_looks_ahead() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_eta_tracks_current_speed() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_progress_summary_mentions_highway() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_gps_state_crossing_and_rest_stop_cues_deduplicate() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world_models (Stop) and sim::trip_models (RoadStop)"]
fn test_likely_parking_is_not_announced_as_truck_parking() {
    // TODO(port): port once the Rust data::world_models (Stop) and sim::trip_models (RoadStop) is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_likely_parking_route_cue_just_announces_stop() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_gps_traffic_cue_deduplicates() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_route_context_describes_near_traffic_without_zero_distance() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_toll_cues_and_charges_deduplicate() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_non_toll_route_does_not_charge_tolls() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_zero_amount_toll_entry_marker_does_not_record_expense() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_traffic_context_and_warning_are_grounded_in_lead_vehicle() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_city_events_do_not_repeat_mapped_state_crossings() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_city_events_keep_crossing_fallback_without_mapped_state_line() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_city_events_include_state_without_repeating_crossing() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_same_city_highway_dispatch_is_not_a_facility_approach() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_trip_requests_first_cell_weather_at_construction() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}

#[test]
#[ignore = "needs App and states::city"]
fn test_city_menu_warms_the_weather_provider() {
    // TODO(port): port once the Rust App and states::city is available.
}

#[test]
#[ignore = "needs App"]
fn test_live_data_providers_ignore_the_online_services_master_switch() {
    // TODO(port): port once the Rust App is available.
}

#[test]
#[ignore = "needs data::world and sim::trip"]
fn test_weather_is_asked_again_at_a_state_line() {
    // TODO(port): port once the Rust data::world and sim::trip is available.
}
