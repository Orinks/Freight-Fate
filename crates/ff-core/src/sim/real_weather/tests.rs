use super::*;
use serde_json::json;
use std::sync::mpsc;
use std::sync::Mutex as StdMutex;

// -- NWS condition mapping -----------------------------------------------

#[test]
fn test_condition_mapping_basics() {
    assert_eq!(map_condition("Clear", 0.0, None), WeatherKind::Clear);
    assert_eq!(map_condition("Sunny", 0.0, None), WeatherKind::Clear);
    assert_eq!(
        map_condition("Mostly Cloudy", 0.0, None),
        WeatherKind::Cloudy
    );
    assert_eq!(map_condition("Overcast", 0.0, None), WeatherKind::Cloudy);
    assert_eq!(map_condition("Patchy Fog", 0.0, None), WeatherKind::Fog);
    assert_eq!(map_condition("Light Rain", 0.0, None), WeatherKind::Rain);
    assert_eq!(map_condition("Rain Showers", 0.0, None), WeatherKind::Rain);
    assert_eq!(
        map_condition("Heavy Rain", 0.0, None),
        WeatherKind::HeavyRain
    );
    assert_eq!(map_condition("Snow", 0.0, None), WeatherKind::Snow);
    assert_eq!(map_condition("Wintry Mix", 0.0, None), WeatherKind::Snow);
    assert_eq!(
        map_condition("Thunderstorm", 0.0, None),
        WeatherKind::Thunderstorm
    );
}

#[test]
fn test_glaze_conditions_map_to_freezing_rain() {
    // Freezing rain, sleet, and ice used to be lumped into snow; they now map
    // to the glare-ice condition, and must win over the plain rain keyword.
    assert_eq!(map_condition("Freezing Rain", 0.0, None), WeatherKind::Ice);
    assert_eq!(
        map_condition("Light Freezing Drizzle", 0.0, None),
        WeatherKind::Ice
    );
    assert_eq!(map_condition("Sleet", 0.0, None), WeatherKind::Ice);
    assert_eq!(map_condition("Ice Fog", 0.0, None), WeatherKind::Ice);
    // Plain snow phrasing still lands on snow.
    assert_eq!(map_condition("Light Snow", 0.0, None), WeatherKind::Snow);
}

#[test]
fn test_condition_unknown_or_empty_defaults_to_cloudy() {
    assert_eq!(map_condition("", 0.0, None), WeatherKind::Cloudy);
    assert_eq!(
        map_condition("Volcanic Eruption", 0.0, None),
        WeatherKind::Cloudy
    );
}

#[test]
fn test_condition_precipitation_beats_clouds_and_storms_beat_rain() {
    // cloud keyword present but rain wins
    assert_eq!(
        map_condition("Cloudy with Rain", 0.0, None),
        WeatherKind::Rain
    );
    // thunder wins over rain
    assert_eq!(
        map_condition("Thunderstorms and Rain", 0.0, None),
        WeatherKind::Thunderstorm
    );
    // snow wins over rain (e.g. wintry mix described with rain)
    assert_eq!(map_condition("Rain and Snow", 0.0, None), WeatherKind::Snow);
}

#[test]
fn test_strong_wind_promotes_clear_to_windy() {
    assert_eq!(map_condition("Clear", 45.0, None), WeatherKind::Wind);
    assert_eq!(map_condition("Clear", 10.0, None), WeatherKind::Clear);
    // wind never overrides precipitation
    assert_eq!(map_condition("Light Rain", 60.0, None), WeatherKind::Rain);
    // an explicit windy phrase maps to wind on its own
    assert_eq!(map_condition("Breezy", 0.0, None), WeatherKind::Wind);
}

#[test]
fn test_fog_family_gated_on_measured_visibility() {
    // NWS says "Fog/Mist" or "Haze" for anything under ~7 miles of visibility;
    // at 6 miles that's ordinary muggy air, not the game's quarter-mile fog.
    assert_eq!(
        map_condition("Fog/Mist", 0.0, Some(6.0)),
        WeatherKind::Cloudy
    );
    assert_eq!(map_condition("Haze", 0.0, Some(6.0)), WeatherKind::Cloudy);
    // Genuinely low visibility is still fog.
    assert_eq!(map_condition("Fog", 0.0, Some(0.25)), WeatherKind::Fog);
    assert_eq!(map_condition("Fog/Mist", 0.0, Some(1.0)), WeatherKind::Fog);
    // No measured visibility: trust the condition text.
    assert_eq!(map_condition("Fog", 0.0, None), WeatherKind::Fog);
    assert_eq!(map_condition("Patchy Fog", 0.0, None), WeatherKind::Fog);
    // The gate never touches non-fog conditions.
    assert_eq!(
        map_condition("Light Rain", 0.0, Some(6.0)),
        WeatherKind::Rain
    );
    // Hazy but windy air promotes to high winds like any cloudy sky.
    assert_eq!(map_condition("Haze", 45.0, Some(6.0)), WeatherKind::Wind);
}

// -- provider ----------------------------------------------------------------

/// The tests' `SyncProvider`: workers run inline so tests are deterministic.
fn sync_provider(fetch: FetchFn) -> RealWeatherProvider {
    RealWeatherProvider::new(fetch).with_threaded(false)
}

fn fixed(seconds: f64) -> Clock {
    Arc::new(move || seconds)
}

fn shared_clock(cell: &Arc<StdMutex<f64>>) -> Clock {
    let cell = Arc::clone(cell);
    Arc::new(move || *cell.lock().unwrap())
}

fn obs(text: &str, wind: f64, temp: Option<f64>, vis: Option<f64>) -> Observation {
    Observation::new(text, wind, temp, vis)
}

#[test]
fn test_provider_fetches_and_caches() {
    let calls = Arc::new(StdMutex::new(Vec::new()));
    let recorder = Arc::clone(&calls);
    let p = sync_provider(Arc::new(move |lat, lon| {
        recorder.lock().unwrap().push((lat, lon));
        Ok(obs("Light Rain", 12.0, Some(8.0), Some(4.0)))
    }));
    assert_eq!(p.get("Chicago"), None);
    p.request("Chicago", 41.88, -87.63);
    assert_eq!(p.get("Chicago"), Some(WeatherKind::Rain));
    p.request("Chicago", 41.88, -87.63); // cached: no second call
    assert_eq!(calls.lock().unwrap().len(), 1);
}

#[test]
fn test_provider_failure_is_silent_and_rate_limited() {
    let calls = Arc::new(StdMutex::new(0));
    let counter = Arc::clone(&calls);
    let p = sync_provider(Arc::new(move |_, _| {
        *counter.lock().unwrap() += 1;
        Err("no network".to_string())
    }));
    p.request("Denver", 39.7, -105.0);
    assert_eq!(p.get("Denver"), None);
    p.request("Denver", 39.7, -105.0); // within retry window: no new attempt
    assert_eq!(*calls.lock().unwrap(), 1);
}

#[test]
fn test_provider_refetches_after_ttl() {
    let now = Arc::new(StdMutex::new(0.0));
    let conditions = Arc::new(StdMutex::new(vec!["Thunderstorm", "Clear"]));
    let p = sync_provider(Arc::new(move |_, _| {
        let next = conditions.lock().unwrap().pop().unwrap();
        Ok(obs(next, 0.0, None, None))
    }))
    .with_clock(shared_clock(&now));
    p.request("Dallas", 32.8, -96.8);
    assert_eq!(p.get("Dallas"), Some(WeatherKind::Clear));
    *now.lock().unwrap() = CACHE_TTL_S + 1.0;
    p.request("Dallas", 32.8, -96.8);
    assert_eq!(p.get("Dallas"), Some(WeatherKind::Thunderstorm));
}

#[test]
fn test_newly_fetched_old_observation_stays_live_without_claiming_update() {
    // An old station reading can arrive in a fresh response. The five-minute
    // fetch throttle means that response is not itself evidence of another
    // active update, so speech must separate observation age from request
    // activity. (The spoken-report half of this test lives with
    // sim::weather's WeatherSystem; this is the provider half.)
    let wall = 2_000_000.0;
    let observed_at = wall - 12.0 * 60.0;
    let calls = Arc::new(StdMutex::new(0));
    let counter = Arc::clone(&calls);
    let provider = sync_provider(Arc::new(move |_, _| {
        *counter.lock().unwrap() += 1;
        Ok(obs("Light Rain", 5.0, Some(14.0), Some(6.0)).observed_at(observed_at))
    }))
    .with_clock(fixed(0.0))
    .with_wall_clock(fixed(wall));
    provider.request("route-cell", 40.0, -80.0);
    assert_eq!(provider.get("route-cell"), Some(WeatherKind::Rain));
    assert_eq!(provider.observation_age_s("route-cell"), Some(12.0 * 60.0));
    assert!(!provider.refreshing("route-cell"));
    provider.request("route-cell", 40.0, -80.0);
    assert_eq!(*calls.lock().unwrap(), 1); // fresh fetch timestamp still enforces the throttle
}

#[test]
fn test_last_known_report_says_updating_only_during_true_inflight_refresh() {
    // Provider half: `refreshing` is true only while a worker really is
    // in flight. The report wording lives with WeatherSystem.
    let monotonic = Arc::new(StdMutex::new(0.0));
    let wall = Arc::new(StdMutex::new(2_000_000.0));
    let (started_tx, started_rx) = mpsc::channel::<()>();
    let (release_tx, release_rx) = mpsc::channel::<()>();
    let release_rx = StdMutex::new(release_rx);
    let calls = Arc::new(StdMutex::new(0));
    let counter = Arc::clone(&calls);
    let wall_for_fetch = Arc::clone(&wall);
    let provider = RealWeatherProvider::new(Arc::new(move |_, _| {
        let n = {
            let mut c = counter.lock().unwrap();
            *c += 1;
            *c
        };
        let now = *wall_for_fetch.lock().unwrap();
        if n == 1 {
            return Ok(obs("Light Rain", 5.0, Some(14.0), Some(6.0)).observed_at(now - 12.0 * 60.0));
        }
        started_tx.send(()).unwrap();
        release_rx
            .lock()
            .unwrap()
            .recv_timeout(std::time::Duration::from_secs(5))
            .expect("released");
        Ok(obs("Clear", 0.0, Some(15.0), Some(10.0)).observed_at(now))
    }))
    .with_clock(shared_clock(&monotonic))
    .with_wall_clock(shared_clock(&wall));
    provider.request("route-cell", 40.0, -80.0);
    provider.join_background();
    assert_eq!(provider.get("route-cell"), Some(WeatherKind::Rain));

    *monotonic.lock().unwrap() = CACHE_TTL_S + 1.0;
    *wall.lock().unwrap() += CACHE_TTL_S + 1.0;
    provider.request("route-cell", 40.0, -80.0);
    started_rx
        .recv_timeout(std::time::Duration::from_secs(5))
        .expect("refresh started");
    assert!(provider.refreshing("route-cell"));
    assert!(provider.stale("route-cell"));

    release_tx.send(()).unwrap();
    provider.join_background();
    assert!(!provider.refreshing("route-cell"));
    assert_eq!(provider.get("route-cell"), Some(WeatherKind::Clear));
}

#[test]
fn test_failed_refresh_expires_last_known_observation_instead_of_loading_forever() {
    let monotonic = Arc::new(StdMutex::new(0.0));
    let wall = Arc::new(StdMutex::new(1_000_000.0));
    let calls = Arc::new(StdMutex::new(0));
    let counter = Arc::clone(&calls);
    let wall_for_fetch = Arc::clone(&wall);
    let p = sync_provider(Arc::new(move |_, _| {
        let mut c = counter.lock().unwrap();
        *c += 1;
        if *c == 1 {
            let now = *wall_for_fetch.lock().unwrap();
            return Ok(obs("Heavy Rain", 5.0, Some(12.0), Some(1.0)).observed_at(now));
        }
        Err("offline".to_string())
    }))
    .with_clock(shared_clock(&monotonic))
    .with_wall_clock(shared_clock(&wall));
    p.request("route-cell", 40.0, -80.0);
    assert_eq!(p.get("route-cell"), Some(WeatherKind::HeavyRain));

    *monotonic.lock().unwrap() = CACHE_TTL_S + 1.0;
    *wall.lock().unwrap() = CACHE_TTL_S + 1.0 + 1_000_000.0;
    p.request("route-cell", 40.0, -80.0);
    assert!(p.stale("route-cell"));
    assert!(!p.unavailable("route-cell"));

    *monotonic.lock().unwrap() = STALE_AFTER_S + 1.0;
    *wall.lock().unwrap() = 1_000_000.0 + STALE_AFTER_S + 1.0;
    p.request("route-cell", 40.0, -80.0);
    assert_eq!(p.get("route-cell"), None);
    assert!(p.unavailable("route-cell"));
    assert!(p.unavailable("route-cell"));
}

#[test]
fn test_same_place_keys_share_one_observation() {
    // Observations belong to stations, not to request-key strings: the city
    // menu's warm-up and the trip's first route cell are the same place, so
    // the second key must ride the first key's fetch instead of refetching.
    let calls = Arc::new(StdMutex::new(0));
    let counter = Arc::clone(&calls);
    let p = sync_provider(Arc::new(move |_, _| {
        *counter.lock().unwrap() += 1;
        Ok(obs("Light Rain", 5.0, Some(14.0), Some(6.0)).observed_at(2_000_000.0))
    }))
    .with_clock(fixed(0.0))
    .with_wall_clock(fixed(2_000_000.0));
    p.request("city:newark", 40.7357, -74.1724);
    p.request("route:newark:philadelphia:0", 40.7357, -74.1724);
    assert_eq!(
        p.get("route:newark:philadelphia:0"),
        Some(WeatherKind::Rain)
    );
    assert_eq!(p.get_temperature("route:newark:philadelphia:0"), Some(14.0));
    assert_eq!(*calls.lock().unwrap(), 1);
}

#[test]
fn test_provider_reports_session_observation_history() {
    let p = sync_provider(Arc::new(|_, _| {
        Ok(obs("Clear", 0.0, Some(20.0), Some(10.0)).observed_at(2_000_000.0))
    }))
    .with_clock(fixed(0.0))
    .with_wall_clock(fixed(2_000_000.0));
    assert!(!p.has_any_observation());
    p.request("route-cell", 40.0, -80.0);
    assert!(p.has_any_observation());
}

#[test]
fn test_hourly_metar_cadence_is_still_live() {
    // NWS stations file routine observations once an hour, so the newest
    // available observation is 30-60 minutes old for most of every hour. That
    // is what "current conditions" means; it must never read as an NWS failure
    // and push the player onto simulated fallback weather.
    let now = 2_000_000.0;
    let p = sync_provider(Arc::new(move |_, _| {
        Ok(obs("Heavy Rain", 5.0, Some(12.0), Some(1.0)).observed_at(now - 45.0 * 60.0))
    }))
    .with_clock(fixed(0.0))
    .with_wall_clock(fixed(now));
    p.request("route-cell", 40.0, -80.0);
    assert_eq!(p.get("route-cell"), Some(WeatherKind::HeavyRain));
    assert!(!p.unavailable("route-cell"));
}

#[test]
fn test_old_nws_observation_timestamp_is_never_treated_as_live() {
    let now = 2_000_000.0;
    let old = now - OBSERVATION_MAX_AGE_S - 1.0;
    let p = sync_provider(Arc::new(move |_, _| {
        Ok(obs("Heavy Rain", 5.0, Some(12.0), Some(1.0)).observed_at(old))
    }))
    .with_clock(fixed(0.0))
    .with_wall_clock(fixed(now));
    p.request("route-cell", 40.0, -80.0);
    assert_eq!(p.get("route-cell"), None);
}

#[test]
#[ignore = "needs sim::weather (WeatherSystem holds last-known conditions)"]
fn test_new_cell_fetch_failure_holds_last_known_not_fallback() {}

#[test]
#[ignore = "needs sim::weather (WeatherSystem fallback)"]
fn test_cold_session_with_failing_provider_still_reaches_fallback() {}

#[test]
fn test_expired_observation_retries_then_recovers_to_live_weather() {
    // Provider half: WeatherSystem.update drives request() every tick; here
    // the requests are issued directly at the same clock readings.
    let monotonic = Arc::new(StdMutex::new(0.0));
    let wall = Arc::new(StdMutex::new(2_000_000.0));
    let calls = Arc::new(StdMutex::new(0));
    let counter = Arc::clone(&calls);
    let wall_for_fetch = Arc::clone(&wall);
    let provider = sync_provider(Arc::new(move |_, _| {
        let mut c = counter.lock().unwrap();
        *c += 1;
        let mut observed_at = *wall_for_fetch.lock().unwrap();
        if *c == 1 {
            observed_at -= OBSERVATION_MAX_AGE_S + 1.0;
        }
        Ok(obs("Clear", 0.0, Some(10.0), Some(10.0)).observed_at(observed_at))
    }))
    .with_clock(shared_clock(&monotonic))
    .with_wall_clock(shared_clock(&wall));

    provider.request("route-cell", 40.0, -80.0);
    assert_eq!(*calls.lock().unwrap(), 1);
    assert_eq!(provider.get("route-cell"), None);
    assert!(provider.unavailable("route-cell"));

    *monotonic.lock().unwrap() = RETRY_AFTER_S - 0.1;
    *wall.lock().unwrap() += RETRY_AFTER_S - 0.1;
    provider.request("route-cell", 40.0, -80.0);
    assert_eq!(*calls.lock().unwrap(), 1);
    assert!(provider.unavailable("route-cell"));

    *monotonic.lock().unwrap() = RETRY_AFTER_S + 0.1;
    *wall.lock().unwrap() += 0.2;
    provider.request("route-cell", 40.0, -80.0);
    assert_eq!(*calls.lock().unwrap(), 2);
    assert_eq!(provider.get("route-cell"), Some(WeatherKind::Clear));
    assert!(!provider.unavailable("route-cell"));
}

// -- stale-observation robustness ----------------------------------------------
//
// Regression coverage for a tester report (2026-08-11): a dead/parked station
// made every fetch for a route segment raise "NWS observation is too old to
// use", which escaped through the worker's generic failure handler as a
// WARNING-with-traceback every RETRY_AFTER_S (about once a minute) for
// stretches of a drive. The fix keeps the staleness gate well clear of a
// normal hourly METAR cadence, handles a too-old reading as a routine miss
// instead of an error, and logs it at most once per stretch.

#[test]
fn test_59_minute_old_observation_is_accepted() {
    // A METAR up to just under an hour old is completely normal and must
    // read as live, not trip the staleness gate.
    let now = 2_000_000.0;
    let p = sync_provider(Arc::new(move |_, _| {
        Ok(obs("Clear", 0.0, Some(10.0), Some(10.0)).observed_at(now - 59.0 * 60.0))
    }))
    .with_clock(fixed(0.0))
    .with_wall_clock(fixed(now));
    p.request("route-cell", 40.0, -80.0);
    assert_eq!(p.get("route-cell"), Some(WeatherKind::Clear));
    assert!(!p.unavailable("route-cell"));
}

#[test]
fn test_stale_observation_does_not_raise_out_of_worker() {
    // A too-old observation used to raise a bare ValueError from inside the
    // fetch path; the worker must absorb it internally instead.
    let now = 2_000_000.0;
    let p =
        RealWeatherProvider::new(Arc::new(move |_, _| {
            Ok(obs("Clear", 0.0, Some(10.0), Some(10.0))
                .observed_at(now - OBSERVATION_MAX_AGE_S - 1.0))
        }))
        .with_clock(fixed(0.0))
        .with_wall_clock(fixed(now));
    // Calling the worker body directly (synchronously, no thread boundary to
    // hide behind) must not panic.
    p.worker("route:charleston_wv_us:roanoke_va_us:6", 40.0, -80.0);
    assert_eq!(p.get("route:charleston_wv_us:roanoke_va_us:6"), None);
    assert!(p.unavailable("route:charleston_wv_us:roanoke_va_us:6"));
}

#[test]
fn test_stale_observation_keeps_previous_conditions_smooth() {
    // Once real conditions are known, one stale refresh must not yank the
    // player back to simulated fallback weather -- the previous observation
    // keeps serving (per `usable`/`STALE_AFTER_S`) until it genuinely
    // expires or a fresh reading arrives.
    let monotonic = Arc::new(StdMutex::new(0.0));
    let wall = Arc::new(StdMutex::new(2_000_000.0));
    let calls = Arc::new(StdMutex::new(0));
    let counter = Arc::clone(&calls);
    let wall_for_fetch = Arc::clone(&wall);
    let p =
        sync_provider(Arc::new(move |_, _| {
            let mut c = counter.lock().unwrap();
            *c += 1;
            let now = *wall_for_fetch.lock().unwrap();
            if *c == 1 {
                return Ok(obs("Heavy Rain", 5.0, Some(12.0), Some(1.0)).observed_at(now));
            }
            Ok(obs("Clear", 0.0, Some(10.0), Some(10.0))
                .observed_at(now - OBSERVATION_MAX_AGE_S - 1.0))
        }))
        .with_clock(shared_clock(&monotonic))
        .with_wall_clock(shared_clock(&wall));
    p.request("route-cell", 40.0, -80.0);
    assert_eq!(p.get("route-cell"), Some(WeatherKind::HeavyRain));

    *monotonic.lock().unwrap() = CACHE_TTL_S + 1.0;
    *wall.lock().unwrap() += CACHE_TTL_S + 1.0;
    p.request("route-cell", 40.0, -80.0);
    assert_eq!(*calls.lock().unwrap(), 2); // the stale refresh really was attempted
    assert_eq!(p.get("route-cell"), Some(WeatherKind::HeavyRain)); // but did not overwrite the cache
    assert!(!p.unavailable("route-cell"));
}

#[test]
fn test_repeated_stale_fetches_do_not_multiply_warnings() {
    // A station stuck past the staleness cutoff keeps getting retried
    // (RETRY_AFTER_S is under a minute), but the log must not repeat a full
    // warning-with-traceback on every attempt -- at most one note per stretch,
    // and never at WARNING. The worker outcome stands in for the log capture.
    let now = 2_000_000.0;
    let segment = "route:charleston_wv_us:roanoke_va_us:6";
    let p =
        RealWeatherProvider::new(Arc::new(move |_, _| {
            Ok(obs("Clear", 0.0, Some(10.0), Some(10.0))
                .observed_at(now - OBSERVATION_MAX_AGE_S - 1.0))
        }))
        .with_clock(fixed(0.0))
        .with_wall_clock(fixed(now));
    let outcomes: Vec<WorkerOutcome> = (0..5).map(|_| p.worker(segment, 40.0, -80.0)).collect();
    assert!(p.unavailable(segment));
    assert!(!outcomes.contains(&WorkerOutcome::Failed));
    let notes = outcomes
        .iter()
        .filter(|o| **o == WorkerOutcome::StaleLogged)
        .count();
    assert_eq!(notes, 1);
    assert_eq!(outcomes[1..], [WorkerOutcome::StaleSilent; 4]);
}

// -- temperature ---------------------------------------------------------------

#[test]
fn test_temp_to_c_handles_units_and_nulls() {
    assert_eq!(
        temp_to_c(Some(&json!({"value": 20.0, "unitCode": "wmoUnit:degC"}))).unwrap(),
        Some(20.0)
    );
    assert_eq!(
        temp_to_c(Some(&json!({"value": 68.0, "unitCode": "wmoUnit:degF"}))).unwrap(),
        Some(20.0)
    );
    assert_eq!(
        temp_to_c(Some(&json!({"value": null, "unitCode": "wmoUnit:degC"}))).unwrap(),
        None
    );
    assert_eq!(temp_to_c(None).unwrap(), None);
}

#[test]
fn test_visibility_to_mi_handles_units_and_nulls() {
    let mi = visibility_to_mi(Some(&json!({"value": 16093.44, "unitCode": "wmoUnit:m"})))
        .unwrap()
        .unwrap();
    assert!((mi - 10.0).abs() < 0.01);
    let km = visibility_to_mi(Some(&json!({"value": 1.609344, "unitCode": "wmoUnit:km"})))
        .unwrap()
        .unwrap();
    assert!((km - 1.0).abs() < 0.01);
    assert_eq!(
        visibility_to_mi(Some(&json!({"value": null, "unitCode": "wmoUnit:m"}))).unwrap(),
        None
    );
    assert_eq!(visibility_to_mi(None).unwrap(), None);
}

#[test]
fn wind_to_kmh_converts_each_unit() {
    assert_eq!(
        wind_to_kmh(Some(&json!({"value": 10.0, "unitCode": "wmoUnit:km_h-1"}))).unwrap(),
        10.0
    );
    assert_eq!(
        wind_to_kmh(Some(&json!({"value": 10.0, "unitCode": "wmoUnit:m_s-1"}))).unwrap(),
        36.0
    );
    assert_eq!(
        wind_to_kmh(Some(&json!({"value": 10.0, "unitCode": "mph"}))).unwrap(),
        16.09344
    );
    assert_eq!(wind_to_kmh(Some(&json!({"value": null}))).unwrap(), 0.0);
    assert_eq!(wind_to_kmh(None).unwrap(), 0.0);
}

#[test]
fn test_provider_reports_haze_with_good_visibility_as_cloudy() {
    // The regression that shipped fog horns over a 6-mile-visibility summer
    // haze: the provider itself must apply the visibility gate.
    let p = sync_provider(Arc::new(|_, _| Ok(obs("Haze", 9.0, Some(27.0), Some(6.0)))));
    p.request("Wilmington", 39.74, -75.54);
    assert_eq!(p.get("Wilmington"), Some(WeatherKind::Cloudy));
}

#[test]
fn test_provider_caches_observed_temperature() {
    let p = sync_provider(Arc::new(|_, _| {
        Ok(obs("Clear", 0.0, Some(-3.5), Some(10.0)))
    }));
    assert_eq!(p.get_temperature("Fargo"), None); // nothing fetched yet
    p.request("Fargo", 46.88, -96.79);
    assert_eq!(p.get("Fargo"), Some(WeatherKind::Clear));
    assert_eq!(p.get_temperature("Fargo"), Some(-3.5));
}

#[test]
fn test_provider_temperature_none_when_station_omits_it() {
    let p = sync_provider(Arc::new(|_, _| Ok(obs("Clear", 0.0, None, None))));
    p.request("Reno", 39.5, -119.8);
    assert_eq!(p.get("Reno"), Some(WeatherKind::Clear));
    assert_eq!(p.get_temperature("Reno"), None);
}

#[test]
#[ignore = "needs sim::weather (WeatherSystem.describe)"]
fn test_weather_system_reports_real_observed_temperature() {}

#[test]
#[ignore = "needs sim::weather (WeatherSystem.report_lead / source_conditions)"]
fn test_live_report_omits_modeled_temperature_when_observation_has_none() {}

// -- weather system integration ------------------------------------------------

#[test]
#[ignore = "needs sim::weather (WeatherSystem)"]
fn test_weather_system_applies_live_conditions() {}

#[test]
#[ignore = "needs sim::weather (WeatherSystem)"]
fn test_late_observation_for_previous_route_cell_cannot_replace_current_cell() {}

#[test]
#[ignore = "needs sim::weather (WeatherSystem)"]
fn test_live_conditions_do_not_evolve_simulated_weather_with_independent_calendar() {}

#[test]
#[ignore = "needs sim::weather (WeatherSystem)"]
fn test_weather_system_holds_clear_while_live_data_pending() {}

#[test]
#[ignore = "needs sim::weather (WeatherSystem)"]
fn test_weather_system_falls_back_when_offline() {}

#[test]
#[ignore = "needs sim::weather (WeatherSystem)"]
fn test_weather_system_without_provider_unchanged() {}

#[test]
#[ignore = "needs data::world (the world fixture)"]
fn test_world_cities_have_coordinates() {}

// -- the station walk (monkeypatched _get_json in Python; a table transport here)

fn nws_obs(text: &str, age_s: f64, now: f64) -> Value {
    let stamp = chrono::DateTime::from_timestamp((now - age_s) as i64, 0)
        .unwrap()
        .to_rfc3339();
    json!({
        "properties": {
            "textDescription": text,
            "windSpeed": {"value": 10.0, "unitCode": "wmoUnit:km_h-1"},
            "temperature": {"value": 20.0, "unitCode": "wmoUnit:degC"},
            "visibility": {"value": 16093.44, "unitCode": "wmoUnit:m"},
            "timestamp": stamp,
        }
    })
}

/// Answers the discovery chain for any point with two stations, then
/// each station's latest observation from `answer`.
struct StationTransport {
    answer: Box<dyn Fn(&str) -> Value + Send + Sync>,
    calls: StdMutex<Vec<String>>,
}

impl HttpTransport for StationTransport {
    fn get(&self, url: &str, _: &[(&str, &str)], _: f64) -> Result<Vec<u8>, TransportError> {
        self.calls.lock().unwrap().push(url.to_string());
        let doc = if url.contains("/points/") {
            json!({"properties": {"observationStations": "https://x/stations"}})
        } else if url.ends_with("/stations") {
            json!({"observationStations": ["https://x/st0", "https://x/st1"]})
        } else {
            (self.answer)(url)
        };
        Ok(serde_json::to_vec(&doc).unwrap())
    }

    fn post(
        &self,
        _: &str,
        _: &[u8],
        _: &[(&str, &str)],
        _: f64,
    ) -> Result<Vec<u8>, TransportError> {
        Err(TransportError::new("no POST on the NWS API"))
    }
}

#[test]
fn test_station_walk_skips_a_dead_nearest_station() {
    // The nearest NWS station is not always a live one. A station sitting on
    // a days-old observation pinned a route cell to simulated fallback for a
    // whole session (2026-08-12 manual playtest): the resolver trusted index
    // zero forever, and first contact had no previous conditions to hold. The
    // fetch now walks to the next-nearest fresh station and remembers it.
    let now = 1_700_000_000.0;
    let transport = Arc::new(StationTransport {
        answer: Box::new(move |url| {
            if url.contains("st0") {
                nws_obs("Mostly Cloudy", 3.0 * 24.0 * 3600.0, now) // parked station
            } else {
                nws_obs("Rain", 20.0 * 60.0, now) // fresh, 20 minutes old
            }
        }),
        calls: StdMutex::new(Vec::new()),
    });
    let fetcher = NwsFetcher::new(transport.clone()).with_wall_clock(fixed(now));
    let observation = fetcher.default_fetch(41.88, -87.63).unwrap();
    assert_eq!(observation.text, "Rain");
    let observed_at = observation.observed_at.unwrap();
    assert!(now - observed_at < OBSERVATION_MAX_AGE_S);

    // The fresh station is remembered and asked first next time.
    transport.calls.lock().unwrap().clear();
    fetcher.default_fetch(41.88, -87.63).unwrap();
    assert!(transport.calls.lock().unwrap()[0].contains("st1"));
}

#[test]
fn test_station_walk_returns_freshest_when_all_are_stale() {
    let now = 1_700_000_000.0;
    let transport = Arc::new(StationTransport {
        answer: Box::new(move |url| {
            if url.contains("st0") {
                nws_obs("Fog", 5.0 * 24.0 * 3600.0, now)
            } else {
                nws_obs("Snow", 4.0 * 3600.0, now) // stale too, but fresher
            }
        }),
        calls: StdMutex::new(Vec::new()),
    });
    let fetcher = NwsFetcher::new(transport).with_wall_clock(fixed(now));
    let observation = fetcher.default_fetch(41.88, -87.63).unwrap();
    assert_eq!(observation.text, "Snow"); // the freshest stale one, for the caller's hold logic
}

#[test]
fn the_discovery_chain_is_cached_per_coarse_location() {
    let now = 1_700_000_000.0;
    let transport = Arc::new(StationTransport {
        answer: Box::new(move |_| nws_obs("Clear", 60.0, now)),
        calls: StdMutex::new(Vec::new()),
    });
    let fetcher = NwsFetcher::new(transport.clone()).with_wall_clock(fixed(now));
    fetcher.default_fetch(41.88, -87.63).unwrap();
    fetcher.default_fetch(41.881, -87.632).unwrap(); // rounds to the same key
    let calls = transport.calls.lock().unwrap();
    // points + stations once, then one observation per fetch.
    assert_eq!(calls.iter().filter(|u| u.contains("/points/")).count(), 1);
    assert_eq!(calls.len(), 4);
    assert!(calls[0].ends_with("/points/41.8800,-87.6300"));
}

#[test]
fn parse_observation_reads_an_nws_document() {
    let doc = nws_obs("Light Rain", 0.0, 1_700_000_000.0);
    let parsed = parse_observation(&doc).unwrap();
    assert_eq!(parsed.text, "Light Rain");
    assert_eq!(parsed.wind_kmh, 10.0);
    assert_eq!(parsed.temperature_c, Some(20.0));
    assert!((parsed.visibility_mi.unwrap() - 10.0).abs() < 0.01);
    assert_eq!(parsed.observed_at, Some(1_700_000_000.0));
    // A Z suffix parses like +00:00.
    assert_eq!(iso_timestamp("2023-11-14T22:13:20Z"), Some(1_700_000_000.0));
    assert!(parse_observation(&json!({})).is_err());
}
