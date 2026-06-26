"""Real-weather (NWS) provider tests. No network access: the fetch function
is injected everywhere."""

import threading

from freight_fate.sim.real_weather import CACHE_TTL_S, RealWeatherProvider, map_condition
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
        return "Light Rain", 12.0

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
        return next(conditions), 0.0

    p = SyncProvider(fetch=fake_fetch, clock=lambda: now[0])
    p.request("Dallas", 32.8, -96.8)
    assert p.get("Dallas") is WeatherKind.CLEAR
    now[0] = CACHE_TTL_S + 1
    p.request("Dallas", 32.8, -96.8)
    assert p.get("Dallas") is WeatherKind.THUNDERSTORM


# -- weather system integration ------------------------------------------------

def test_weather_system_applies_live_conditions():
    p = SyncProvider(fetch=lambda lat, lon: ("Heavy Rain", 5.0))
    ws = WeatherSystem("desert_southwest", seed=1, provider=p)
    ws.set_city("Phoenix", 33.45, -112.07)
    changed = ws.update(1.0)
    assert ws.live
    assert ws.current is WeatherKind.HEAVY_RAIN
    assert changed is WeatherKind.HEAVY_RAIN
    # stable live data: no further changes, simulation stays paused
    for _ in range(100):
        assert ws.update(30.0) is None
    assert ws.current is WeatherKind.HEAVY_RAIN


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
