"""Weather system and trip simulation tests."""

import itertools

from freight_fate.sim import Trip, TruckState, WeatherKind, WeatherSystem
from freight_fate.sim.trip import TripEventKind
from freight_fate.sim.weather import EFFECTS, REGION_WEIGHTS


def test_all_conditions_have_effects():
    for kind in WeatherKind:
        assert kind in EFFECTS


def test_all_regions_in_world_have_weights(world):
    regions = {c.region for c in world.cities.values()}
    for region in regions:
        assert region in REGION_WEIGHTS, f"no weather weights for {region}"


def test_weather_is_deterministic_with_seed():
    a = WeatherSystem("midwest", seed=7)
    b = WeatherSystem("midwest", seed=7)
    for _ in range(50):
        assert a.update(13.0) == b.update(13.0)
    assert a.current == b.current


def test_weather_eventually_changes():
    ws = WeatherSystem("northwest", seed=3)
    changes = [ws.update(15.0) for _ in range(200)]
    assert any(c is not None for c in changes)


def test_bad_weather_reduces_grip():
    assert EFFECTS[WeatherKind.SNOW].grip < EFFECTS[WeatherKind.CLEAR].grip
    assert EFFECTS[WeatherKind.HEAVY_RAIN].grip < EFFECTS[WeatherKind.RAIN].grip


def test_forecast_returns_requested_segments():
    ws = WeatherSystem("south", seed=1)
    assert len(ws.forecast(3)) == 3


def make_trip(world, start="Chicago", end="Indianapolis", **kwargs):
    route = world.route_options(start, end)[0]
    truck = TruckState()
    truck.transmission.automatic = True
    truck.start_engine()
    weather = WeatherSystem("midwest", seed=1)
    return Trip(route, truck, weather, seed=2, **kwargs), truck


def test_trip_completes_and_emits_arrival(world):
    trip, truck = make_trip(world)
    truck.throttle = 0.85
    events = []
    for i in itertools.count():
        truck.auto_shift()
        truck.update(1 / 60)
        events += trip.update(1 / 60)
        assert i < 60 * 60 * 30, "trip never finished"
        if trip.finished:
            break
    kinds = {e.kind for e in events}
    assert TripEventKind.ARRIVED in kinds
    assert trip.remaining_miles == 0.0


def test_trip_announces_stops_ahead(world):
    trip, truck = make_trip(world)
    truck.throttle = 0.85
    events = []
    for _ in range(60 * 60 * 10):
        truck.auto_shift()
        truck.update(1 / 60)
        events += trip.update(1 / 60)
        if trip.finished:
            break
    assert any(e.kind == TripEventKind.STOP_AHEAD for e in events)


def test_zone_speed_limits_apply(world):
    trip, _ = make_trip(world, "Atlanta", "Dallas")
    assert trip.zones, "long route should have at least one zone"
    zone = trip.zones[0]
    inside = (zone.start_mi + zone.end_mi) / 2
    limit, reason = trip.speed_limit_at(inside)
    assert limit == zone.limit_mph
    assert reason == zone.reason
    limit, reason = trip.speed_limit_at(zone.end_mi + 50)
    assert reason is None or limit != zone.limit_mph


def test_grades_are_bounded(world):
    trip, _ = make_trip(world, "Denver", "Salt Lake City")
    for mile in range(0, int(trip.total_miles), 3):
        assert abs(trip.grade_at(float(mile))) <= 0.08


def test_time_scale_compresses_fuel_burn(world):
    trip, truck = make_trip(world, time_scale=40.0)
    truck.throttle = 0.9
    for _ in range(60 * 30):
        truck.auto_shift()
        truck.update(1 / 60)
        trip.update(1 / 60)
    assert truck.fuel_burn_mult == 40.0
    assert truck.fuel_gal < truck.specs.fuel_tank_gal - 0.5


def test_every_weather_region_has_local_hazards():
    from freight_fate.sim.trip import GENERIC_HAZARDS, REGION_HAZARDS, hazard_choices

    for region in REGION_WEIGHTS:
        assert region in REGION_HAZARDS, f"no local hazards for {region}"
        pool = hazard_choices(region)
        assert set(GENERIC_HAZARDS) <= set(pool)
        assert set(REGION_HAZARDS[region]) <= set(pool)
    # unknown regions still get the nationwide staples
    assert hazard_choices("atlantis") == GENERIC_HAZARDS


def test_upcoming_stop_only_looks_ahead(world):
    trip, _ = make_trip(world)
    stop = trip.stops[0]
    trip.position_mi = stop.at_mi - 3.0
    assert trip.upcoming_stop(5.0) is stop
    trip.position_mi = stop.at_mi - 10.0
    assert trip.upcoming_stop(5.0) is None
    trip.position_mi = stop.at_mi + 0.1   # just past: the exit is gone
    next_stop = trip.upcoming_stop(5.0)
    assert next_stop is not stop


def test_eta_tracks_current_speed(world):
    """Regression: the C key's ETA was a constant 55 mph guess that never
    responded to how fast you were actually going."""
    trip, truck = make_trip(world)
    parked = trip.eta_game_hours()
    assert parked > 0
    truck.velocity_mps = 31.3   # ~70 mph
    fast = trip.eta_game_hours()
    truck.velocity_mps = 13.4   # ~30 mph
    slow = trip.eta_game_hours()
    assert fast < parked < slow  # parked assumes 55 mph, between the two
    # parked or crawling falls back to highway pace, never infinity
    truck.velocity_mps = 0.5
    assert trip.eta_game_hours() == parked


def test_progress_summary_mentions_highway(world):
    trip, _ = make_trip(world)
    text = trip.progress_summary()
    assert "I-65" in text
    assert "Indianapolis" in text
    metric = trip.progress_summary(imperial=False)
    assert "kilometers" in metric
