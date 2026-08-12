"""Real-weather (NWS) provider tests. No network access: the fetch function
is injected everywhere."""

import logging
import threading

from freight_fate.sim.real_weather import (
    CACHE_TTL_S,
    OBSERVATION_MAX_AGE_S,
    RETRY_AFTER_S,
    STALE_AFTER_S,
    RealWeatherProvider,
    map_condition,
)
from freight_fate.sim.weather import WeatherKind, WeatherSystem

# -- NWS condition mapping -----------------------------------------------------


def test_condition_mapping_basics():
    assert map_condition("Clear") is WeatherKind.CLEAR
    assert map_condition("Sunny") is WeatherKind.CLEAR
    assert map_condition("Mostly Cloudy") is WeatherKind.CLOUDY
    assert map_condition("Overcast") is WeatherKind.CLOUDY
    assert map_condition("Patchy Fog") is WeatherKind.FOG
    assert map_condition("Light Rain") is WeatherKind.RAIN
    assert map_condition("Rain Showers") is WeatherKind.RAIN
    assert map_condition("Heavy Rain") is WeatherKind.HEAVY_RAIN
    assert map_condition("Snow") is WeatherKind.SNOW
    assert map_condition("Wintry Mix") is WeatherKind.SNOW
    assert map_condition("Thunderstorm") is WeatherKind.THUNDERSTORM


def test_glaze_conditions_map_to_freezing_rain():
    # Freezing rain, sleet, and ice used to be lumped into snow; they now map
    # to the glare-ice condition, and must win over the plain rain keyword.
    assert map_condition("Freezing Rain") is WeatherKind.ICE
    assert map_condition("Light Freezing Drizzle") is WeatherKind.ICE
    assert map_condition("Sleet") is WeatherKind.ICE
    assert map_condition("Ice Fog") is WeatherKind.ICE
    # Plain snow phrasing still lands on snow.
    assert map_condition("Light Snow") is WeatherKind.SNOW


def test_condition_unknown_or_empty_defaults_to_cloudy():
    assert map_condition("") is WeatherKind.CLOUDY
    assert map_condition("Volcanic Eruption") is WeatherKind.CLOUDY


def test_condition_precipitation_beats_clouds_and_storms_beat_rain():
    # cloud keyword present but rain wins
    assert map_condition("Cloudy with Rain") is WeatherKind.RAIN
    # thunder wins over rain
    assert map_condition("Thunderstorms and Rain") is WeatherKind.THUNDERSTORM
    # snow wins over rain (e.g. wintry mix described with rain)
    assert map_condition("Rain and Snow") is WeatherKind.SNOW


def test_strong_wind_promotes_clear_to_windy():
    assert map_condition("Clear", wind_kmh=45.0) is WeatherKind.WIND
    assert map_condition("Clear", wind_kmh=10.0) is WeatherKind.CLEAR
    # wind never overrides precipitation
    assert map_condition("Light Rain", wind_kmh=60.0) is WeatherKind.RAIN
    # an explicit windy phrase maps to wind on its own
    assert map_condition("Breezy") is WeatherKind.WIND


def test_fog_family_gated_on_measured_visibility():
    # NWS says "Fog/Mist" or "Haze" for anything under ~7 miles of visibility;
    # at 6 miles that's ordinary muggy air, not the game's quarter-mile fog.
    assert map_condition("Fog/Mist", visibility_mi=6.0) is WeatherKind.CLOUDY
    assert map_condition("Haze", visibility_mi=6.0) is WeatherKind.CLOUDY
    # Genuinely low visibility is still fog.
    assert map_condition("Fog", visibility_mi=0.25) is WeatherKind.FOG
    assert map_condition("Fog/Mist", visibility_mi=1.0) is WeatherKind.FOG
    # No measured visibility: trust the condition text.
    assert map_condition("Fog") is WeatherKind.FOG
    assert map_condition("Patchy Fog") is WeatherKind.FOG
    # The gate never touches non-fog conditions.
    assert map_condition("Light Rain", visibility_mi=6.0) is WeatherKind.RAIN
    # Hazy but windy air promotes to high winds like any cloudy sky.
    assert map_condition("Haze", wind_kmh=45.0, visibility_mi=6.0) is WeatherKind.WIND


# -- provider ----------------------------------------------------------------


class SyncProvider(RealWeatherProvider):
    """Run worker threads inline so tests are deterministic."""

    def request(self, city, lat, lon):
        before = threading.active_count()
        super().request(city, lat, lon)
        # join any thread we just spawned
        for t in threading.enumerate():
            if t.name == f"weather-{city}":
                t.join(timeout=5)
        assert threading.active_count() <= before + 1


def test_provider_fetches_and_caches():
    calls = []

    def fake_fetch(lat, lon):
        calls.append((lat, lon))
        return "Light Rain", 12.0, 8.0, 4.0

    p = SyncProvider(fetch=fake_fetch)
    assert p.get("Chicago") is None
    p.request("Chicago", 41.88, -87.63)
    assert p.get("Chicago") is WeatherKind.RAIN
    p.request("Chicago", 41.88, -87.63)  # cached: no second call
    assert len(calls) == 1


def test_provider_failure_is_silent_and_rate_limited():
    calls = []

    def broken_fetch(lat, lon):
        calls.append(1)
        raise OSError("no network")

    p = SyncProvider(fetch=broken_fetch)
    p.request("Denver", 39.7, -105.0)
    assert p.get("Denver") is None
    p.request("Denver", 39.7, -105.0)  # within retry window: no new attempt
    assert len(calls) == 1


def test_provider_refetches_after_ttl():
    now = [0.0]
    conditions = iter(["Clear", "Thunderstorm"])

    def fake_fetch(lat, lon):
        return next(conditions), 0.0, None, None

    p = SyncProvider(fetch=fake_fetch, clock=lambda: now[0])
    p.request("Dallas", 32.8, -96.8)
    assert p.get("Dallas") is WeatherKind.CLEAR
    now[0] = CACHE_TTL_S + 1
    p.request("Dallas", 32.8, -96.8)
    assert p.get("Dallas") is WeatherKind.THUNDERSTORM


def test_newly_fetched_old_observation_stays_live_without_claiming_update():
    """An old station reading can arrive in a fresh response. The five-minute
    fetch throttle means that response is not itself evidence of another active
    update, so speech must separate observation age from request activity."""
    wall = [2_000_000.0]
    observed_at = wall[0] - 12 * 60
    calls = []

    def fetch(lat, lon):
        calls.append((lat, lon))
        return "Light Rain", 5.0, 14.0, 6.0, observed_at

    provider = SyncProvider(
        fetch=fetch,
        clock=lambda: 0.0,
        wall_clock=lambda: wall[0],
    )
    weather = WeatherSystem("great_lakes", seed=1, provider=provider)
    weather.set_city("route-cell", 40.0, -80.0)

    weather.update(0.0)

    assert weather.source_status == "live"
    assert provider.observation_age_s("route-cell") == 12 * 60
    assert not provider.refreshing("route-cell")
    provider.request("route-cell", 40.0, -80.0)
    assert len(calls) == 1  # fresh fetch timestamp still enforces the throttle
    report = weather.report_lead()
    assert "The observation is 12 minutes old" in report
    assert report.startswith("Live weather:")
    assert "updating" not in report.lower()


def test_last_known_report_says_updating_only_during_true_inflight_refresh():
    monotonic = [0.0]
    wall = [2_000_000.0]
    refresh_started = threading.Event()
    release_refresh = threading.Event()
    calls = [0]

    def fetch(lat, lon):
        calls[0] += 1
        if calls[0] == 1:
            return "Light Rain", 5.0, 14.0, 6.0, wall[0] - 12 * 60
        refresh_started.set()
        assert release_refresh.wait(timeout=5)
        return "Clear", 0.0, 15.0, 10.0, wall[0]

    provider = RealWeatherProvider(
        fetch=fetch,
        clock=lambda: monotonic[0],
        wall_clock=lambda: wall[0],
    )
    weather = WeatherSystem("great_lakes", seed=1, provider=provider)
    weather.set_city("route-cell", 40.0, -80.0)
    provider.request("route-cell", 40.0, -80.0)
    for thread in threading.enumerate():
        if thread.name == "weather-route-cell":
            thread.join(timeout=5)
    weather.update(0.0)

    monotonic[0] = CACHE_TTL_S + 1
    wall[0] += CACHE_TTL_S + 1
    weather.update(0.0)
    assert refresh_started.wait(timeout=5)
    assert provider.refreshing("route-cell")
    assert "Live weather is updating for your current location" in weather.report_lead()

    release_refresh.set()
    for thread in threading.enumerate():
        if thread.name == "weather-route-cell":
            thread.join(timeout=5)
    assert not provider.refreshing("route-cell")


def test_failed_refresh_expires_last_known_observation_instead_of_loading_forever():
    monotonic = [0.0]
    wall = [1_000_000.0]
    calls = [0]

    def fetch(lat, lon):
        calls[0] += 1
        if calls[0] == 1:
            return "Heavy Rain", 5.0, 12.0, 1.0, wall[0]
        raise OSError("offline")

    p = SyncProvider(fetch=fetch, clock=lambda: monotonic[0], wall_clock=lambda: wall[0])
    p.request("route-cell", 40.0, -80.0)
    assert p.get("route-cell") is WeatherKind.HEAVY_RAIN

    monotonic[0] = wall[0] = CACHE_TTL_S + 1
    wall[0] += 1_000_000.0
    p.request("route-cell", 40.0, -80.0)
    assert p.stale("route-cell")
    assert not p.unavailable("route-cell")

    monotonic[0] = STALE_AFTER_S + 1
    wall[0] = 1_000_000.0 + STALE_AFTER_S + 1
    p.request("route-cell", 40.0, -80.0)
    assert p.get("route-cell") is None
    assert p.unavailable("route-cell")
    assert p.unavailable("route-cell")


def test_same_place_keys_share_one_observation():
    # Observations belong to stations, not to request-key strings: the city
    # menu's warm-up and the trip's first route cell are the same place, so
    # the second key must ride the first key's fetch instead of refetching.
    calls = []

    def fetch(lat, lon):
        calls.append((lat, lon))
        return "Light Rain", 5.0, 14.0, 6.0, 2_000_000.0

    p = SyncProvider(fetch=fetch, clock=lambda: 0.0, wall_clock=lambda: 2_000_000.0)
    p.request("city:newark", 40.7357, -74.1724)
    p.request("route:newark:philadelphia:0", 40.7357, -74.1724)
    assert p.get("route:newark:philadelphia:0") is WeatherKind.RAIN
    assert p.get_temperature("route:newark:philadelphia:0") == 14.0
    assert len(calls) == 1


def test_provider_reports_session_observation_history():
    p = SyncProvider(
        fetch=lambda lat, lon: ("Clear", 0.0, 20.0, 10.0, 2_000_000.0),
        clock=lambda: 0.0,
        wall_clock=lambda: 2_000_000.0,
    )
    assert not p.has_any_observation()
    p.request("route-cell", 40.0, -80.0)
    assert p.has_any_observation()


def test_hourly_metar_cadence_is_still_live():
    """NWS stations file routine observations once an hour, so the newest
    available observation is 30-60 minutes old for most of every hour. That is
    what "current conditions" means; it must never read as an NWS failure and
    push the player onto simulated fallback weather."""
    now = [2_000_000.0]
    p = SyncProvider(
        fetch=lambda lat, lon: ("Heavy Rain", 5.0, 12.0, 1.0, now[0] - 45 * 60.0),
        clock=lambda: 0.0,
        wall_clock=lambda: now[0],
    )
    p.request("route-cell", 40.0, -80.0)
    assert p.get("route-cell") is WeatherKind.HEAVY_RAIN
    assert not p.unavailable("route-cell")


def test_old_nws_observation_timestamp_is_never_treated_as_live():
    now = [2_000_000.0]
    old = now[0] - OBSERVATION_MAX_AGE_S - 1
    p = SyncProvider(
        fetch=lambda lat, lon: ("Heavy Rain", 5.0, 12.0, 1.0, old),
        clock=lambda: 0.0,
        wall_clock=lambda: now[0],
    )
    p.request("route-cell", 40.0, -80.0)
    assert p.get("route-cell") is None


def test_new_cell_fetch_failure_holds_last_known_not_fallback():
    """One dropped request at a route-cell boundary must never simulate.

    The truck crosses into a fresh 20-mile cell, that cell's first fetch
    fails, and the previous cell's live conditions are seconds old: the
    weather holds them as last-known and retries -- it does not flip to
    simulated fallback while NWS is fine (owner ruling, 2026-08-08)."""
    boom = [False]

    def fetch(lat, lon):
        if boom[0]:
            raise OSError("transient")
        return "Heavy Rain", 5.0, 12.0, 1.0, 2_000_000.0

    provider = SyncProvider(fetch=fetch, clock=lambda: 0.0, wall_clock=lambda: 2_000_000.0)
    weather = WeatherSystem("great_lakes", seed=1, provider=provider)
    weather.set_city("cell-0", 40.0, -80.0)
    weather.update(0.0)
    assert weather.source_status == "live"
    assert weather.current is WeatherKind.HEAVY_RAIN

    boom[0] = True
    weather.set_city("cell-1", 41.0, -81.0)
    weather.update(0.0)
    assert weather.source_status == "last_known"
    assert weather.current is WeatherKind.HEAVY_RAIN  # held, not resimulated
    # And it stays held on later ticks rather than drifting to fallback.
    weather.update(1.0)
    assert weather.source_status == "last_known"
    assert weather.current is WeatherKind.HEAVY_RAIN


def test_cold_session_with_failing_provider_still_reaches_fallback():
    def fetch(lat, lon):
        raise OSError("offline")

    provider = SyncProvider(fetch=fetch, clock=lambda: 0.0, wall_clock=lambda: 2_000_000.0)
    weather = WeatherSystem("great_lakes", seed=1, provider=provider)
    weather.set_city("cell-0", 40.0, -80.0)
    weather.update(0.0)
    assert weather.source_status == "fallback"


def test_expired_observation_retries_then_recovers_to_live_weather():
    monotonic = [0.0]
    wall = [2_000_000.0]
    calls = [0]

    def fetch(lat, lon):
        calls[0] += 1
        observed_at = wall[0]
        if calls[0] == 1:
            observed_at -= OBSERVATION_MAX_AGE_S + 1
        return "Clear", 0.0, 10.0, 10.0, observed_at

    provider = SyncProvider(
        fetch=fetch,
        clock=lambda: monotonic[0],
        wall_clock=lambda: wall[0],
    )
    weather = WeatherSystem("great_lakes", seed=1, provider=provider)
    weather.set_city("route-cell", 40.0, -80.0)

    weather.update(0.0)
    assert calls == [1]
    assert weather.source_status == "fallback"

    monotonic[0] = RETRY_AFTER_S - 0.1
    wall[0] += RETRY_AFTER_S - 0.1
    weather.update(0.0)
    assert calls == [1]
    assert weather.source_status == "fallback"

    monotonic[0] = RETRY_AFTER_S + 0.1
    wall[0] += 0.2
    weather.update(0.0)
    assert calls == [2]
    assert weather.source_status == "live"
    assert weather.current is WeatherKind.CLEAR


# -- stale-observation robustness ----------------------------------------------
#
# Regression coverage for a tester report (2026-08-11): a dead/parked station
# made every fetch for a route segment raise "NWS observation is too old to
# use", which escaped through the worker's generic failure handler as a
# WARNING-with-traceback every RETRY_AFTER_S (about once a minute) for
# stretches of a drive. The fix keeps the staleness gate well clear of a
# normal hourly METAR cadence, handles a too-old reading as a routine miss
# instead of an error, and logs it at most once per stretch.


def test_59_minute_old_observation_is_accepted():
    """A METAR up to just under an hour old is completely normal and must
    read as live, not trip the staleness gate."""
    now = [2_000_000.0]
    p = SyncProvider(
        fetch=lambda lat, lon: ("Clear", 0.0, 10.0, 10.0, now[0] - 59 * 60.0),
        clock=lambda: 0.0,
        wall_clock=lambda: now[0],
    )
    p.request("route-cell", 40.0, -80.0)
    assert p.get("route-cell") is WeatherKind.CLEAR
    assert not p.unavailable("route-cell")


def test_stale_observation_does_not_raise_out_of_worker():
    """A too-old observation used to raise a bare ValueError from inside the
    fetch path; the worker must absorb it internally instead."""
    now = [2_000_000.0]
    p = RealWeatherProvider(
        fetch=lambda lat, lon: (
            "Clear",
            0.0,
            10.0,
            10.0,
            now[0] - OBSERVATION_MAX_AGE_S - 1,
        ),
        clock=lambda: 0.0,
        wall_clock=lambda: now[0],
    )
    # Calling the worker body directly (synchronously, no thread boundary to
    # hide behind) must not raise.
    p._worker("route:charleston_wv_us:roanoke_va_us:6", 40.0, -80.0)
    assert p.get("route:charleston_wv_us:roanoke_va_us:6") is None
    assert p.unavailable("route:charleston_wv_us:roanoke_va_us:6")


def test_stale_observation_keeps_previous_conditions_smooth():
    """Once real conditions are known, one stale refresh must not yank the
    player back to simulated fallback weather -- the previous observation
    keeps serving (per ``_usable``/``STALE_AFTER_S``) until it genuinely
    expires or a fresh reading arrives."""
    monotonic = [0.0]
    wall = [2_000_000.0]
    calls = [0]

    def fetch(lat, lon):
        calls[0] += 1
        if calls[0] == 1:
            return "Heavy Rain", 5.0, 12.0, 1.0, wall[0]
        return "Clear", 0.0, 10.0, 10.0, wall[0] - OBSERVATION_MAX_AGE_S - 1

    p = SyncProvider(fetch=fetch, clock=lambda: monotonic[0], wall_clock=lambda: wall[0])
    p.request("route-cell", 40.0, -80.0)
    assert p.get("route-cell") is WeatherKind.HEAVY_RAIN

    monotonic[0] = CACHE_TTL_S + 1
    wall[0] += CACHE_TTL_S + 1
    p.request("route-cell", 40.0, -80.0)
    assert calls[0] == 2  # the stale refresh really was attempted
    assert p.get("route-cell") is WeatherKind.HEAVY_RAIN  # but did not overwrite the cache
    assert not p.unavailable("route-cell")


def test_repeated_stale_fetches_do_not_multiply_warnings(caplog):
    """A station stuck past the staleness cutoff keeps getting retried
    (RETRY_AFTER_S is under a minute), but the log must not repeat a full
    warning-with-traceback on every attempt -- at most one note per stretch,
    and never at WARNING/with a traceback."""
    now = [2_000_000.0]
    segment = "route:charleston_wv_us:roanoke_va_us:6"

    def stale_fetch(lat, lon):
        return "Clear", 0.0, 10.0, 10.0, now[0] - OBSERVATION_MAX_AGE_S - 1

    p = RealWeatherProvider(fetch=stale_fetch, clock=lambda: 0.0, wall_clock=lambda: now[0])
    with caplog.at_level(logging.DEBUG, logger="freight_fate.sim.real_weather"):
        for _ in range(5):
            p._worker(segment, 40.0, -80.0)

    assert p.unavailable(segment)
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == []
    notes = [r for r in caplog.records if segment in r.getMessage()]
    assert len(notes) == 1
    assert notes[0].exc_info is None


# -- temperature ---------------------------------------------------------------


def test_temp_to_c_handles_units_and_nulls():
    from freight_fate.sim.real_weather import _temp_to_c

    assert _temp_to_c({"value": 20.0, "unitCode": "wmoUnit:degC"}) == 20.0
    assert _temp_to_c({"value": 68.0, "unitCode": "wmoUnit:degF"}) == 20.0
    assert _temp_to_c({"value": None, "unitCode": "wmoUnit:degC"}) is None
    assert _temp_to_c(None) is None


def test_visibility_to_mi_handles_units_and_nulls():
    from freight_fate.sim.real_weather import _visibility_to_mi

    mi = _visibility_to_mi({"value": 16093.44, "unitCode": "wmoUnit:m"})
    assert mi is not None and abs(mi - 10.0) < 0.01
    km = _visibility_to_mi({"value": 1.609344, "unitCode": "wmoUnit:km"})
    assert km is not None and abs(km - 1.0) < 0.01
    assert _visibility_to_mi({"value": None, "unitCode": "wmoUnit:m"}) is None
    assert _visibility_to_mi(None) is None


def test_provider_reports_haze_with_good_visibility_as_cloudy():
    # The regression that shipped fog horns over a 6-mile-visibility summer
    # haze: the provider itself must apply the visibility gate.
    p = SyncProvider(fetch=lambda lat, lon: ("Haze", 9.0, 27.0, 6.0))
    p.request("Wilmington", 39.74, -75.54)
    assert p.get("Wilmington") is WeatherKind.CLOUDY


def test_provider_caches_observed_temperature():
    p = SyncProvider(fetch=lambda lat, lon: ("Clear", 0.0, -3.5, 10.0))
    assert p.get_temperature("Fargo") is None  # nothing fetched yet
    p.request("Fargo", 46.88, -96.79)
    assert p.get("Fargo") is WeatherKind.CLEAR
    assert p.get_temperature("Fargo") == -3.5


def test_provider_temperature_none_when_station_omits_it():
    p = SyncProvider(fetch=lambda lat, lon: ("Clear", 0.0, None, None))
    p.request("Reno", 39.5, -119.8)
    assert p.get("Reno") is WeatherKind.CLEAR
    assert p.get_temperature("Reno") is None


def test_weather_system_reports_real_observed_temperature():
    # A live provider with a real reading: the system reports the station's
    # temperature, not the seasonal climate model.
    p = SyncProvider(fetch=lambda lat, lon: ("Clear", 0.0, 2.0, 10.0))  # 2 C real
    ws = WeatherSystem("great_lakes", seed=1, provider=p)
    ws.set_city("Chicago", 41.88, -87.63)
    ws.update(1.0)
    assert ws.live
    assert ws.temperature_c == 2.0
    assert "36 degrees" in ws.describe(imperial=True)  # 2 C -> 35.6 F -> "36"


def test_live_report_omits_modeled_temperature_when_observation_has_none():
    class ConditionsOnlyProvider:
        def request(self, *args):
            pass

        def get(self, key):
            return WeatherKind.HEAVY_RAIN

        def stale(self, key):
            return False

        def unavailable(self, key):
            return False

    ws = WeatherSystem("desert_southwest", seed=1, provider=ConditionsOnlyProvider())
    ws.set_city("route-cell", 33.45, -112.07)
    ws.update(1.0)

    assert ws.source_status == "live"
    assert ws.temperature_c is not None  # The seasonal model remains available to mechanics.
    assert "degrees" not in ws.report_lead(imperial=True)
    assert "degrees" not in ws.source_conditions(imperial=True)
    assert "visibility" not in ws.source_conditions(imperial=True)
    assert "slick roads" not in ws.source_conditions(imperial=True)


# -- weather system integration ------------------------------------------------


def test_weather_system_applies_live_conditions():
    p = SyncProvider(fetch=lambda lat, lon: ("Heavy Rain", 5.0, 18.0, 1.5))
    ws = WeatherSystem("desert_southwest", seed=1, provider=p)
    ws.set_city("Phoenix", 33.45, -112.07)
    changed = ws.update(1.0)
    assert ws.live
    assert ws.current is WeatherKind.HEAVY_RAIN
    assert changed is WeatherKind.HEAVY_RAIN
    # Stable live data: no further changes, simulation stays paused.
    for _ in range(100):
        assert ws.update(30.0) is None
    assert ws.current is WeatherKind.HEAVY_RAIN


def test_late_observation_for_previous_route_cell_cannot_replace_current_cell():
    class LocationProvider:
        data = {"cell-a": None, "cell-b": WeatherKind.RAIN}

        def request(self, *args):
            pass

        def get(self, key):
            return self.data.get(key)

        def stale(self, key):
            return False

        def unavailable(self, key):
            return False

    provider = LocationProvider()
    ws = WeatherSystem("great_lakes", seed=1, provider=provider)
    ws.set_city("cell-a", 41.0, -87.0)
    ws.update(0.0)
    ws.set_city("cell-b", 40.0, -86.0)
    ws.update(0.0)
    assert ws.current is WeatherKind.RAIN

    provider.data["cell-a"] = WeatherKind.HEAVY_RAIN
    ws.update(0.0)
    assert ws.city == "cell-b"
    assert ws.current is WeatherKind.RAIN


def test_live_conditions_do_not_evolve_simulated_weather_with_independent_calendar():
    """The calendar toggle must not restart the simulated transition timer.

    Live weather may change when the provider's observation or target city
    changes, but it must not wander from rain to heavy rain or fog on its own.
    """
    p = SyncProvider(fetch=lambda lat, lon: ("Rain", 5.0, 18.0, 5.0))
    ws = WeatherSystem(
        "great_lakes",
        seed=2,
        provider=p,
        game_hours=100.0,
        live_weather_controls_calendar=False,
    )
    ws.set_city("Chicago", 41.88, -87.63)
    ws.update(1.0)
    assert ws.live
    # With the career calendar independent of the live feed, precipitation is
    # reconciled to the career season: live rain in a freezing Great Lakes
    # window lands as freezing rain. What matters here is that it settles once
    # and then holds -- it must not wander on its own.
    assert ws.current is WeatherKind.ICE
    assert ws.source_conditions(imperial=True) == (
        "observation rain, 64 degrees; treated as freezing rain for driving"
    )
    assert ws.report_lead(imperial=True).startswith(
        "Live weather: observation rain, 64 degrees; treated as freezing rain for driving"
    )

    for _ in range(200):
        assert ws.update(30.0) is None
    assert ws.current is WeatherKind.ICE


def test_weather_system_holds_clear_while_live_data_pending():
    """With a provider attached, weather starts clear and holds -- no simulated
    warm-up -- until live data (or a confirmed offline state) arrives."""

    class Pending:
        def request(self, city, lat, lon):
            pass

        def get(self, city):
            return None

        def unavailable(self, city):
            return False  # still fetching, not offline

    ws = WeatherSystem("pacific_northwest", seed=1, provider=Pending())
    ws.set_city("Seattle", 47.61, -122.33)
    assert ws.current is WeatherKind.CLEAR
    for _ in range(200):
        assert ws.update(30.0) is None  # no simulated transitions while pending
    assert ws.current is WeatherKind.CLEAR
    assert not ws.live


def test_weather_system_falls_back_when_offline():
    p = SyncProvider(fetch=lambda lat, lon: (_ for _ in ()).throw(OSError()))
    ws = WeatherSystem("great_lakes", seed=2, provider=p)
    ws.set_city("Chicago", 41.88, -87.63)
    changes = [ws.update(15.0) for _ in range(200)]
    assert not ws.live
    assert any(c is not None for c in changes)  # simulated weather still evolves


def test_weather_system_without_provider_unchanged():
    ws = WeatherSystem("great_lakes", seed=3)
    ws.update(1.0)
    assert not ws.live


def test_world_cities_have_coordinates(world):
    for city in world.cities.values():
        assert city.lat != 0.0, f"{city.name} missing latitude"
        assert city.lon != 0.0, f"{city.name} missing longitude"
        assert 24 < city.lat < 50
        assert -125 < city.lon < -66


def _nws_obs(text: str, age_s: float, now: float) -> dict:
    from datetime import datetime, timezone

    stamp = datetime.fromtimestamp(now - age_s, tz=timezone.utc).isoformat()
    return {
        "properties": {
            "textDescription": text,
            "windSpeed": {"value": 10.0, "unitCode": "wmoUnit:km_h-1"},
            "temperature": {"value": 20.0, "unitCode": "wmoUnit:degC"},
            "visibility": {"value": 16093.44, "unitCode": "wmoUnit:m"},
            "timestamp": stamp,
        }
    }


def test_station_walk_skips_a_dead_nearest_station(monkeypatch):
    """The nearest NWS station is not always a live one. A station sitting on
    a days-old observation pinned a route cell to simulated fallback for a
    whole session (2026-08-12 manual playtest): the resolver trusted index
    zero forever, and first contact had no previous conditions to hold. The
    fetch now walks to the next-nearest fresh station and remembers it."""
    import time as time_mod

    from freight_fate.sim import real_weather as rw

    monkeypatch.setattr(rw, "_station_cache", {})
    monkeypatch.setattr(rw, "_station_pick", {})
    urls = ["https://x/st0/observations/latest", "https://x/st1/observations/latest"]
    monkeypatch.setattr(rw, "_resolve_station_urls", lambda lat, lon: urls)
    now = time_mod.time()
    calls: list[str] = []

    def fake_get_json(url: str) -> dict:
        calls.append(url)
        if "st0" in url:
            return _nws_obs("Mostly Cloudy", 3 * 24 * 3600.0, now)  # parked station
        return _nws_obs("Rain", 20 * 60.0, now)  # fresh, 20 minutes old

    monkeypatch.setattr(rw, "_get_json", fake_get_json)

    text, _wind, _temp, _vis, observed_at = rw._default_fetch(41.88, -87.63)
    assert text == "Rain"
    assert observed_at is not None and time_mod.time() - observed_at < rw.OBSERVATION_MAX_AGE_S

    # The fresh station is remembered and asked first next time.
    calls.clear()
    rw._default_fetch(41.88, -87.63)
    assert "st1" in calls[0]


def test_station_walk_returns_freshest_when_all_are_stale(monkeypatch):
    import time as time_mod

    from freight_fate.sim import real_weather as rw

    monkeypatch.setattr(rw, "_station_cache", {})
    monkeypatch.setattr(rw, "_station_pick", {})
    urls = ["https://x/st0/observations/latest", "https://x/st1/observations/latest"]
    monkeypatch.setattr(rw, "_resolve_station_urls", lambda lat, lon: urls)
    now = time_mod.time()

    def fake_get_json(url: str) -> dict:
        if "st0" in url:
            return _nws_obs("Fog", 5 * 24 * 3600.0, now)
        return _nws_obs("Snow", 4 * 3600.0, now)  # stale too, but fresher

    monkeypatch.setattr(rw, "_get_json", fake_get_json)

    text, *_rest = rw._default_fetch(41.88, -87.63)
    assert text == "Snow"  # the freshest stale one, for the caller's hold logic
