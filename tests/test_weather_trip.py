"""Weather system and trip simulation tests."""

import itertools

import pytest

from freight_fate.data.world_models import Stop
from freight_fate.sim import Trip, TruckState, WeatherKind, WeatherSystem
from freight_fate.sim.trip import (
    CONSTRUCTION_ENFORCEMENT_GRACE_MI,
    CONSTRUCTION_TAPER_LIMIT_MPH,
    CONSTRUCTION_TAPER_MI,
    NavigationCue,
    NPCVehicle,
    TripEventKind,
)
from freight_fate.sim.trip_models import RoadStop
from freight_fate.sim.weather import EFFECTS, REGION_WEIGHTS


def _gps_events(events):
    """GPS-cue events, excluding additive interchange/exit cues. Tests below
    target one specific cue (toll, state line, construction, traffic); curated
    interchanges share the GPS-cue stream, so filter them out to keep those
    assertions about the cue they mean."""
    return [e for e in events
            if e.kind == TripEventKind.GPS_CUE
            and getattr(e.data.get("cue"), "kind", "") != "interchange"]


def _gps_messages(events):
    return [e.message for e in _gps_events(events)]


def test_all_conditions_have_effects():
    for kind in WeatherKind:
        assert kind in EFFECTS


def test_all_regions_in_world_have_weights(world):
    regions = {c.region for c in world.cities.values()}
    for region in regions:
        assert region in REGION_WEIGHTS, f"no weather weights for {region}"


def _season_conditions(region, game_hours, steps=400, seed=5):
    """Conditions seen across a run with the career clock set to a season."""
    ws = WeatherSystem(region, seed=seed, game_hours=game_hours)
    seen = {ws.current}
    for _ in range(steps):
        ws.update(60.0)  # advance about an hour per step
        seen.add(ws.current)
    return seen


def test_summer_runs_have_no_snow():
    from freight_fate.sim.season import CAREER_START_DAY_OF_YEAR

    summer_hours = (200 - CAREER_START_DAY_OF_YEAR) * 24.0  # mid July
    seen = _season_conditions("great_lakes", summer_hours)
    assert WeatherKind.SNOW not in seen


def test_winter_runs_have_snow_but_no_thunderstorms():
    from freight_fate.sim.season import CAREER_START_DAY_OF_YEAR

    winter_hours = ((15 - CAREER_START_DAY_OF_YEAR) % 365.0) * 24.0  # mid January
    seen = _season_conditions("great_lakes", winter_hours)
    assert WeatherKind.SNOW in seen
    assert WeatherKind.THUNDERSTORM not in seen


def test_seasonal_weather_is_deterministic_with_seed():
    winter_hours = ((15 - 80.0) % 365.0) * 24.0
    a = WeatherSystem("rockies", seed=11, game_hours=winter_hours)
    b = WeatherSystem("rockies", seed=11, game_hours=winter_hours)
    for _ in range(80):
        assert a.update(45.0) == b.update(45.0)
    assert a.current == b.current
    assert a.season == b.season == "winter"


def test_seasons_off_by_default_leaves_temperature_unknown():
    ws = WeatherSystem("heartland", seed=1)
    assert ws.game_hours is None
    assert ws.temperature_c is None
    assert ws.season is None


def test_weather_is_deterministic_with_seed():
    a = WeatherSystem("great_lakes", seed=7)
    b = WeatherSystem("great_lakes", seed=7)
    for _ in range(50):
        assert a.update(13.0) == b.update(13.0)
    assert a.current == b.current


def test_weather_eventually_changes():
    ws = WeatherSystem("pacific_northwest", seed=3)
    changes = [ws.update(15.0) for _ in range(200)]
    assert any(c is not None for c in changes)


def test_bad_weather_reduces_grip():
    assert EFFECTS[WeatherKind.SNOW].grip < EFFECTS[WeatherKind.CLEAR].grip
    assert EFFECTS[WeatherKind.HEAVY_RAIN].grip < EFFECTS[WeatherKind.RAIN].grip


def test_forecast_returns_requested_segments():
    ws = WeatherSystem("atlantic_southeast", seed=1)
    assert len(ws.forecast(3)) == 3


def test_forecast_does_not_regenerate_weather_timeline():
    """Pressing V speaks a forecast; it must not change future weather."""
    with_forecast = WeatherSystem("great_lakes", seed=9)
    untouched = WeatherSystem("great_lakes", seed=9)
    for _ in range(5):
        assert len(with_forecast.forecast(2)) == 2
    for _ in range(80):
        assert with_forecast.update(10.0) == untouched.update(10.0)
    assert with_forecast.current is untouched.current


def make_trip(world, start="Chicago", end="Indianapolis", seed=2, **kwargs):
    route = world.route_options(start, end)[0]
    truck = TruckState()
    truck.transmission.automatic = True
    truck.start_engine()
    weather = WeatherSystem("great_lakes", seed=1)
    return Trip(route, truck, weather, seed=seed, **kwargs), truck


def _brake_until_speed(
    trip: Trip,
    truck: TruckState,
    target_mph: float,
    *,
    emergency: bool = False,
    limit_s: float = 20.0,
    dt: float = 1 / 60,
) -> list:
    truck.throttle = 0.0
    truck.brake = 1.0
    truck.emergency_brake = emergency
    inspections = []
    for _ in range(int(limit_s / dt)):
        truck.auto_shift()
        truck.update(dt)
        events = trip.update(dt)
        inspections.extend(
            event for event in events if event.kind == TripEventKind.INSPECTION
        )
        if truck.speed_mph <= target_mph:
            return inspections
    raise AssertionError(f"truck did not slow to {target_mph} mph")


def test_relaxed_hazard_scale_lowers_hazard_risk(world):
    """Relaxed mode keeps random road hazards rare via the hazard scale."""
    from freight_fate.sim.hos import RELAXED_HAZARD_SCALE

    normal, _ = make_trip(world, seed=4)
    relaxed, _ = make_trip(world, seed=4, hazard_scale=RELAXED_HAZARD_SCALE)
    # Same route, weather, and clock: the only difference is the scale.
    assert relaxed._hazard_risk() == pytest.approx(
        normal._hazard_risk() * RELAXED_HAZARD_SCALE)
    assert relaxed._hazard_risk() < normal._hazard_risk()


def test_corridor_busyness_scales_hazard_check_frequency(world):
    dense_route = world.route_from_cities(["New York", "Boston"])
    sparse_route = world.route_from_cities(["Las Vegas", "Reno"])
    weather = WeatherSystem("northeast", seed=1)
    dense = Trip(dense_route, TruckState(), weather, seed=1)
    sparse = Trip(sparse_route, TruckState(), WeatherSystem("great_basin", seed=1),
                  seed=1)
    dense.position_mi = 25.0
    sparse.position_mi = sparse.total_miles / 2

    assert dense._corridor_hazard_factor_at(dense.position_mi) > (
        sparse._corridor_hazard_factor_at(sparse.position_mi)
    )


def test_hazard_check_interval_shortens_on_busy_corridors(world):
    class FixedRng:
        def uniform(self, low, high):
            assert (low, high) == (20, 60)
            return 40.0

    dense_route = world.route_from_cities(["New York", "Boston"])
    sparse_route = world.route_from_cities(["Las Vegas", "Reno"])
    dense = Trip(dense_route, TruckState(), WeatherSystem("northeast", seed=1),
                 seed=1)
    sparse = Trip(sparse_route, TruckState(), WeatherSystem("great_basin", seed=1),
                  seed=1)
    dense.position_mi = 25.0
    sparse.position_mi = sparse.total_miles / 2
    dense._rng = FixedRng()
    sparse._rng = FixedRng()

    assert dense._next_hazard_check_interval_mi() < (
        sparse._next_hazard_check_interval_mi()
    )


def test_relaxed_mode_thins_traffic_density(world):
    """Relaxed mode also makes ambient traffic rarer, not just hazards."""
    from freight_fate.sim.hos import RELAXED_HAZARD_SCALE

    normal, _ = make_trip(world, seed=4)
    relaxed, _ = make_trip(world, seed=4, hazard_scale=RELAXED_HAZARD_SCALE)
    leg = normal.route.legs[0]
    assert relaxed._leg_traffic_density(leg, 0.0, False) == pytest.approx(
        normal._leg_traffic_density(leg, 0.0, False) * RELAXED_HAZARD_SCALE)
    assert (relaxed._leg_traffic_density(leg, 0.0, False)
            < normal._leg_traffic_density(leg, 0.0, False))


def test_relaxed_mode_reduces_merge_exit_pressure(world):
    from freight_fate.sim.hos import RELAXED_HAZARD_SCALE

    normal, _ = make_trip(world, seed=4)
    relaxed, _ = make_trip(world, seed=4, hazard_scale=RELAXED_HAZARD_SCALE)

    normal_exit = next(p for p in normal.traffic_pressures if p.kind == "exit")
    stop_mile = normal.stops[0].at_mi - 2.0

    assert relaxed._traffic_pressure_intensity(stop_mile, "exit") == pytest.approx(
        normal._traffic_pressure_intensity(stop_mile, "exit") * RELAXED_HAZARD_SCALE)
    relaxed_exit = next(
        (p for p in relaxed.traffic_pressures if p.kind == "exit"),
        None,
    )
    if relaxed_exit is not None:
        assert relaxed_exit.intensity < normal_exit.intensity
        assert relaxed_exit.target_speed_mph > normal_exit.target_speed_mph


def test_relaxed_mode_thins_random_inspection_odds(world):
    """Relaxed mode pulls a violating driver over less often; the random log
    check is thinned by the hazard scale (weigh stations are not)."""
    from freight_fate.sim.hos import RELAXED_HAZARD_SCALE

    normal, _ = make_trip(world, seed=4)
    relaxed, _ = make_trip(world, seed=4, hazard_scale=RELAXED_HAZARD_SCALE)
    leg = normal.route.legs[0]
    assert relaxed._random_inspection_odds(leg) == pytest.approx(
        normal._random_inspection_odds(leg) * RELAXED_HAZARD_SCALE)
    assert relaxed._random_inspection_odds(leg) < normal._random_inspection_odds(leg)


def test_corridor_speed_limit_by_highway_and_region():
    from freight_fate.sim.trip import BASE_SPEED_LIMIT_MPH, corridor_speed_limit

    # Rural Interstates run faster out West, slower in the Northeast.
    assert corridor_speed_limit("I-80", "great_basin") == 80
    assert corridor_speed_limit("I-90", "northeast") == 65
    assert corridor_speed_limit("I-70", "heartland") == 70
    # US highways and state routes are slower than Interstates.
    assert corridor_speed_limit("US-30", "heartland") == 65
    assert corridor_speed_limit("SR-99", "california") == 60
    # An unknown region on an Interstate falls back to the base limit.
    assert corridor_speed_limit("I-5", "atlantis") == BASE_SPEED_LIMIT_MPH


def test_speed_limit_varies_by_corridor_and_drops_in_cities(world):
    from freight_fate.sim.trip import URBAN_LIMIT_MPH

    trip, _ = make_trip(world)  # Chicago -> Indianapolis, an Interstate corridor
    # Near the origin city the limit drops to the urban value.
    near_city, reason = trip.speed_limit_at(1.0)
    assert reason is None
    assert near_city == URBAN_LIMIT_MPH
    # Out on the open road it is the faster corridor limit.
    open_road, reason = trip.speed_limit_at(trip.total_miles / 2)
    assert reason is None
    assert open_road >= 65
    assert open_road > near_city


def test_speed_limit_change_is_announced_crossing_out_of_a_city(world):
    from freight_fate.sim.trip import URBAN_RADIUS_MI, TripEventKind

    trip, truck = make_trip(world)
    truck.throttle = 0.95
    messages = []
    for _ in range(8000):
        truck.auto_shift()
        truck.update(1 / 60)
        for event in trip.update(1 / 60):
            if event.kind == TripEventKind.GPS_CUE:
                messages.append(event.message)
        if trip.position_mi > URBAN_RADIUS_MI + 4:
            break
    # Leaving the urban stretch raises the posted limit, and that is spoken.
    assert any("Speed limit" in m for m in messages)


def test_speed_limit_cue_names_direction_and_city(world, monkeypatch):
    trip, _ = make_trip(world)  # Chicago -> Indianapolis
    trip._active_zone = None

    # A drop near the origin city names the direction and the city.
    trip.position_mi = 0.0
    trip._announced_speed_limit = 65.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 45.0)
    trip._events.clear()
    trip._check_speed_limit()
    lowered = [e.message for e in trip._events]
    assert any("reduced to" in m and "approaching" in m for m in lowered), lowered

    # A rise just states the higher value -- no "approaching" on the way up.
    trip._announced_speed_limit = 45.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 65.0)
    trip._events.clear()
    trip._check_speed_limit()
    raised = [e.message for e in trip._events]
    assert any("raised to" in m for m in raised), raised
    assert all("approaching" not in m for m in raised)


def test_force_weather_override_locks_condition(monkeypatch):
    monkeypatch.setenv("FREIGHT_FATE_FORCE_WEATHER", "snow")
    ws = WeatherSystem("heartland", seed=1)
    assert ws.current is WeatherKind.SNOW
    for _ in range(200):              # never drifts off the forced condition
        ws.update(30.0)
        assert ws.current is WeatherKind.SNOW

    monkeypatch.setenv("FREIGHT_FATE_FORCE_WEATHER", "heavy_rain")
    assert WeatherSystem("heartland", seed=1).current is WeatherKind.HEAVY_RAIN
    monkeypatch.delenv("FREIGHT_FATE_FORCE_WEATHER")
    monkeypatch.setenv("FREIGHT_FATE_FORCE_WEATHER", "bogus")
    assert WeatherSystem("heartland", seed=1)._forced is None


def test_weather_drag_multiplier_increases_resistance():
    truck = TruckState()
    truck.velocity_mps = 25.0
    base = truck.resistance_force()
    truck.drag_mult = 1.25          # a strong headwind / storm
    assert truck.resistance_force() > base


def test_visibility_shortens_hazard_reaction(world):
    trip, _ = make_trip(world)
    trip.weather.current = WeatherKind.CLEAR
    assert trip._visibility_reaction_factor() == 1.0
    trip.weather.current = WeatherKind.HEAVY_RAIN   # 1.5 mi visibility
    assert trip._visibility_reaction_factor() == pytest.approx(0.5)
    trip.weather.current = WeatherKind.FOG          # 0.3 mi -> floored
    assert trip._visibility_reaction_factor() == pytest.approx(0.4)


def test_too_fast_for_conditions_risks_traction_loss(world):
    trip, truck = make_trip(world)
    trip._hazard_check_mi = 1e9          # silence the random environmental hazards
    trip._inspection_check_mi = 1e9
    trip.npc_vehicles = []

    def run_for_hazard(frames=12000):
        hits = []
        for _ in range(frames):
            trip.weather.current = WeatherKind.SNOW   # grip 0.45, safe speed 35
            truck.velocity_mps = 27.0                 # ~60 mph, well over safe
            for e in trip.update(1 / 60):
                if e.kind == TripEventKind.HAZARD:
                    hits.append(e.message)
            if hits:
                break
        return hits

    hits = run_for_hazard()
    assert any("too fast for the conditions" in m for m in hits)

    # At a safe speed for the snow, no traction-loss incident fires.
    trip2, truck2 = make_trip(world, seed=7)
    trip2._hazard_check_mi = 1e9
    trip2._inspection_check_mi = 1e9
    trip2.npc_vehicles = []
    safe_hits = []
    for _ in range(6000):
        trip2.weather.current = WeatherKind.SNOW
        truck2.velocity_mps = 14.0                    # ~31 mph, under safe 35
        for e in trip2.update(1 / 60):
            if e.kind == TripEventKind.HAZARD:
                safe_hits.append(e.message)
    assert not any("too fast for the conditions" in m for m in safe_hits)


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


def test_trip_uses_explicit_stop_positions(world):
    trip, _ = make_trip(world)

    by_name = {stop.name: stop for stop in trip.stops}
    # Hand-curated stops keep their explicit checked-in positions and parking,
    # even with additive OpenStreetMap stops now interleaved on the leg.
    assert by_name["Pilot Travel Center Remington"].at_mi == 93.5
    assert by_name["Loves Travel Stop Lafayette"].at_mi == 121.3
    assert by_name["Pilot Travel Center Remington"].parking == "confirmed"
    assert by_name["Loves Travel Stop Lafayette"].parking == "confirmed"
    # No stop sits at the naive route midpoint, and every stop (curated or
    # discovered) declares a concrete, non-unknown parking value.
    assert all(stop.at_mi != trip.route.miles / 2 for stop in trip.stops)
    assert all(stop.parking != "unknown" for stop in trip.stops)


def test_trip_uses_only_curated_pois_at_runtime(world):
    route = world.route_from_cities(["Memphis", "Nashville"])
    truck = TruckState()
    weather = WeatherSystem("great_lakes", seed=1)
    trip = Trip(route, truck, weather, seed=2)

    assert route.raw_stop_details
    assert all(stop.curated for stop in route.raw_stop_details)
    assert route.stop_details
    assert trip.stops
    assert {stop.name for stop in trip.stops} <= {stop.name for stop in route.stop_details}


def test_trip_places_reverse_route_stops_from_travel_direction(world):
    route = world.route_from_cities(["Dallas", "San Antonio"])
    truck = TruckState()
    weather = WeatherSystem("southern_plains", seed=1)
    trip = Trip(route, truck, weather, seed=2)

    positions = {stop.name: round(stop.at_mi, 1) for stop in trip.stops}
    # Curated stops are positioned from the direction of travel (not the raw
    # stored order); additive OSM stops do not displace them.
    assert positions["Hill County Safety Rest Area"] == 56.8
    assert positions["Road Ranger Waco"] == 89.7
    assert positions["Bell County Safety Rest Area"] == 136.5
    # Every stop stays ordered along the direction of travel.
    ats = [stop.at_mi for stop in trip.stops]
    assert ats == sorted(ats)


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


def test_delivery_final_miles_use_facility_approach_limits(world):
    trip, _ = make_trip(world, "Chicago", "Indianapolis")

    limit, reason = trip.speed_limit_at(trip.total_miles - 2.0)
    assert limit == 35.0
    assert reason == "destination approach"

    limit, reason = trip.speed_limit_at(trip.total_miles - 0.2)
    assert limit == 15.0
    assert reason == "facility gate"


def test_pickup_deadhead_route_uses_local_facility_limits(world):
    route = world.facility_approach_route(
        "Chicago", world.cities["Chicago"].locations[0].name)
    truck = TruckState()
    weather = WeatherSystem("great_lakes", seed=1)
    trip = Trip(route, truck, weather, seed=2)

    limit, reason = trip.speed_limit_at(0.1)
    assert limit == 25.0
    assert reason == "facility access road"

    limit, reason = trip.speed_limit_at(trip.total_miles - 0.2)
    assert limit == 15.0
    assert reason == "facility gate"


def test_facility_gate_warns_before_final_low_speed_zone(world):
    route = world.facility_approach_route(
        "Chicago", world.cities["Chicago"].locations[0].name)
    truck = TruckState()
    weather = WeatherSystem("great_lakes", seed=1)
    trip = Trip(route, truck, weather, seed=2)

    trip.position_mi = trip.total_miles - 2.0
    events = trip.update(0.0)

    warnings = [event.message for event in events if event.kind == TripEventKind.GPS_CUE]
    assert "In 2 miles, facility gate ahead. Speed limit 15." in warnings


def test_construction_zone_warns_before_entry(world):
    trip, truck = make_trip(world, "Chicago", "Indianapolis", seed=2)
    zone = next(z for z in trip.zones if z.reason == "construction")
    truck.velocity_mps = 70 / 2.23694
    trip.time_scale = 20.0

    lookahead = trip._zone_warning_lookahead_mi()
    assert lookahead >= 6.0

    trip.position_mi = zone.start_mi - lookahead
    events = trip.update(0.0)

    warnings = _gps_messages(events)
    assert warnings == [
        f"Brake now! In {trip._distance_text(lookahead)}, construction ahead. "
        f"Merge left for the flagger taper; speed limit "
        f"{CONSTRUCTION_TAPER_LIMIT_MPH:.0f}, then {zone.limit_mph:.0f} "
        "through the work zone."
    ]


def test_construction_zone_has_staged_merge_taper(world):
    trip, _ = make_trip(world, "Chicago", "Indianapolis", seed=2)
    zone = next(z for z in trip.zones if z.reason == "construction")
    taper = next(
        z for z in trip.zones
        if z.reason == "construction merge" and z.end_mi == zone.start_mi
    )

    assert taper.start_mi == pytest.approx(zone.start_mi - CONSTRUCTION_TAPER_MI)
    assert taper.limit_mph == CONSTRUCTION_TAPER_LIMIT_MPH
    limit, reason = trip.speed_limit_at((taper.start_mi + taper.end_mi) / 2)
    assert (limit, reason) == (CONSTRUCTION_TAPER_LIMIT_MPH, "construction merge")
    limit, reason = trip.speed_limit_at((zone.start_mi + zone.end_mi) / 2)
    assert (limit, reason) == (zone.limit_mph, "construction")


def test_construction_warning_lead_allows_normal_braking(world):
    trip, truck = make_trip(world, "Chicago", "Indianapolis", seed=2)
    zone = next(z for z in trip.zones if z.reason == "construction")
    truck.velocity_mps = 70 / 2.23694
    trip.time_scale = 20.0
    trip.position_mi = zone.start_mi - trip._zone_warning_lookahead_mi()

    events = trip.update(0.0)
    assert _gps_messages(events)[0].startswith("Brake now!")

    inspections = _brake_until_speed(trip, truck, zone.limit_mph)

    assert trip.position_mi < zone.start_mi
    assert inspections == []


def test_construction_zone_does_not_fine_on_entry_tick(world):
    trip, truck = make_trip(world, "Chicago", "Indianapolis", seed=2)
    zone = next(z for z in trip.zones if z.reason == "construction")
    truck.velocity_mps = 31.3   # about 70 mph

    trip.position_mi = zone.start_mi - 0.2
    moved_mi = 0.35
    trip.position_mi += moved_mi
    trip._check_zones()
    trip._check_inspections(moved_mi)

    kinds = [event.kind for event in trip._events]
    assert TripEventKind.ZONE_ENTER in kinds
    assert TripEventKind.INSPECTION not in kinds


def test_construction_zone_speeding_fine_waits_for_grace_distance(world):
    trip, truck = make_trip(world, "Chicago", "Indianapolis", seed=2)
    zone = next(z for z in trip.zones if z.reason == "construction")
    truck.velocity_mps = 31.3   # about 70 mph

    trip.position_mi = zone.start_mi - 2.0
    advance = trip.update(0.0)
    assert _gps_messages(advance) == [
        "Brake now! In 2 miles, construction ahead. "
        f"Merge left for the flagger taper; speed limit "
        f"{CONSTRUCTION_TAPER_LIMIT_MPH:.0f}, then {zone.limit_mph:.0f} "
        "through the work zone."
    ]

    trip.position_mi = zone.start_mi + CONSTRUCTION_ENFORCEMENT_GRACE_MI - 0.1
    trip._events = []
    trip._check_zones()
    trip._check_inspections(0.4)
    assert not [event for event in trip._events if event.kind == TripEventKind.INSPECTION]

    trip.position_mi = zone.start_mi + CONSTRUCTION_ENFORCEMENT_GRACE_MI + 0.1
    trip._events = []
    trip._check_inspections(0.8)
    inspection = [event for event in trip._events if event.kind == TripEventKind.INSPECTION]
    assert [event.message for event in inspection] == [
        "Trooper in the construction zone clocks your speed."
    ]


def test_late_emergency_brake_can_save_construction_speeding(world):
    trip, truck = make_trip(world, "Chicago", "Indianapolis", seed=2)
    zone = next(z for z in trip.zones if z.reason == "construction")
    truck.velocity_mps = 70 / 2.23694
    trip.time_scale = 20.0
    trip.position_mi = zone.start_mi + CONSTRUCTION_ENFORCEMENT_GRACE_MI - 0.7
    trip._check_zones()
    trip._events = []

    inspections = _brake_until_speed(
        trip,
        truck,
        zone.limit_mph + 9.0,
        emergency=True,
        limit_s=5.0,
    )

    assert trip.position_mi < zone.start_mi + CONSTRUCTION_ENFORCEMENT_GRACE_MI
    assert inspections == []


def test_grades_are_bounded(world):
    trip, _ = make_trip(world, "Denver", "Salt Lake City")
    for mile in range(0, int(trip.total_miles), 3):
        assert abs(trip.grade_at(float(mile))) <= 0.08


def test_route_derived_flat_grade_is_stable_across_trip_seeds(world):
    trip_a, _ = make_trip(world, seed=1)
    trip_b, _ = make_trip(world, seed=99)
    miles = [0.0, 20.0, 33.0, 72.0, 122.0, 183.0]

    assert [trip_a.grade_at(mile) for mile in miles] == [
        trip_b.grade_at(mile) for mile in miles
    ]
    assert max(abs(trip_a.grade_at(mile)) for mile in miles) < 0.002
    assert {trip_a.terrain_at(mile) for mile in miles} == {"flat"}


def test_traffic_varies_by_seed_but_route_grade_does_not(world):
    trip_a, _ = make_trip(world, seed=1)
    trip_b, _ = make_trip(world, seed=8)

    assert [trip_a.grade_at(mile) for mile in (10.0, 80.0, 150.0)] == [
        trip_b.grade_at(mile) for mile in (10.0, 80.0, 150.0)
    ]
    assert [
        (vehicle.at_mi, vehicle.speed_mph, vehicle.reason)
        for vehicle in trip_a.npc_vehicles
    ] != [
        (vehicle.at_mi, vehicle.speed_mph, vehicle.reason)
        for vehicle in trip_b.npc_vehicles
    ]


def test_npc_traffic_model_applies_to_enriched_and_legacy_routes(world):
    for cities in (["Chicago", "Indianapolis"], ["Chicago", "St. Louis"]):
        route = world.route_from_cities(cities)
        truck = TruckState()
        weather = WeatherSystem("great_lakes", seed=1)
        weather.current = WeatherKind.CLEAR
        trip = Trip(route, truck, weather, seed=1)
        assert trip.npc_vehicles, cities


def test_npc_traffic_seeding_is_deterministic(world):
    route = world.route_from_cities(["Chicago", "Indianapolis"])
    weather = WeatherSystem("great_lakes", seed=1)
    weather.current = WeatherKind.CLEAR

    trip_a = Trip(route, TruckState(), weather, seed=1, start_hour=8.0)
    trip_b = Trip(route, TruckState(), weather, seed=1, start_hour=8.0)

    assert hasattr(trip_a, "traffic_manager")
    assert trip_a.npc_vehicles is trip_a.traffic_manager.vehicles

    def signature(trip):
        return [
            (
                round(vehicle.position_mi, 2),
                round(vehicle.speed_mph, 1),
                vehicle.relative_lane,
                vehicle.behavior,
            )
            for vehicle in trip.npc_vehicles
        ]

    assert signature(trip_a)
    assert signature(trip_a) == signature(trip_b)


def test_npc_traffic_moves_each_trip_tick(world):
    trip, _truck = make_trip(world)
    trip.npc_vehicles = [
        NPCVehicle("npc:test", 5.0, 60.0, 60.0, 0, "steady_truck")
    ]
    trip._hazard_check_mi = 1e9
    trip._inspection_check_mi = 1e9

    trip.update(1.0)

    assert trip.npc_vehicles[0].position_mi > 5.2


def test_bad_weather_slows_modeled_traffic(world):
    route = world.route_from_cities(["Chicago", "Indianapolis"])
    clear_weather = WeatherSystem("great_lakes", seed=1)
    clear_weather.current = WeatherKind.CLEAR
    rain_weather = WeatherSystem("great_lakes", seed=1)
    rain_weather.current = WeatherKind.HEAVY_RAIN

    clear = Trip(route, TruckState(), clear_weather, seed=1)
    rain = Trip(route, TruckState(), rain_weather, seed=1)

    assert clear.npc_vehicles
    assert rain.npc_vehicles
    assert rain.npc_vehicles[0].at_mi == clear.npc_vehicles[0].at_mi
    assert rain.npc_vehicles[0].speed_mph < clear.npc_vehicles[0].speed_mph


def test_rush_hour_can_slow_modeled_traffic(world):
    route = world.route_from_cities(["Chicago", "Indianapolis"])
    midday = Trip(
        route, TruckState(), WeatherSystem("great_lakes", seed=1),
        seed=1, start_hour=12.0)
    rush = Trip(
        route, TruckState(), WeatherSystem("great_lakes", seed=1),
        seed=1, start_hour=8.0)

    assert rush._rush_hour_traffic_bias(route.legs[0]) > 0.0
    if rush.npc_vehicles and midday.npc_vehicles:
        assert min(vehicle.speed_mph for vehicle in rush.npc_vehicles) <= (
            min(vehicle.speed_mph for vehicle in midday.npc_vehicles)
        )


def test_traffic_pressure_marks_exit_and_construction_context(world):
    trip, _ = make_trip(world)

    assert any(p.kind == "exit" and p.direction == "right"
               for p in trip.traffic_pressures)
    if any(zone.reason == "construction merge" for zone in trip.zones):
        assert any(p.kind == "construction_merge" and p.direction == "left"
                   for p in trip.traffic_pressures)


def test_traffic_pressure_gps_cue_deduplicates(world):
    trip, _truck = make_trip(world)
    pressure = next(p for p in trip.traffic_pressures if p.kind == "exit")
    trip.position_mi = pressure.start_mi - 1.0

    first = trip.update(0.0)
    second = trip.update(0.0)

    cues = [
        event for event in first
        if event.kind == TripEventKind.GPS_CUE
        and event.data.get("traffic_pressure") is pressure
    ]
    assert len(cues) == 1
    assert "Exit traffic building" in cues[0].message
    assert "Signal early" in cues[0].message
    assert not [
        event for event in second
        if event.kind == TripEventKind.GPS_CUE
        and event.data.get("traffic_pressure") is pressure
    ]


def test_npc_traffic_cue_and_status_are_reviewable(world):
    trip, truck = make_trip(world)
    truck.velocity_mps = 29.0
    trip.position_mi = 10.0
    trip.npc_vehicles = [
        NPCVehicle("npc:merge", 10.8, 42.0, 42.0, 0, "merging_vehicle")
    ]

    events = trip.update(0.0)

    npc_cues = [
        event for event in events
        if event.kind == TripEventKind.GPS_CUE
        and event.data.get("npc_vehicle") is trip.npc_vehicles[0]
    ]
    assert len(npc_cues) == 1
    assert "Merging vehicle" in npc_cues[0].message
    assert "leave a gap" in npc_cues[0].message
    status = trip.npc_traffic_status()
    assert "Traffic: merging traffic" in status
    assert "moving 42 miles per hour" in status


def test_metric_toggle_updates_npc_traffic_cue_units(world):
    trip, truck = make_trip(world)
    truck.velocity_mps = 29.0
    trip.position_mi = 10.0
    trip.imperial = False
    trip.npc_vehicles = [
        NPCVehicle("npc:metric-merge", 10.8, 42.0, 42.0, 0, "merging_vehicle")
    ]

    events = trip.update(0.0)

    npc_cue = next(
        event for event in events
        if event.kind == TripEventKind.GPS_CUE
        and event.data.get("npc_vehicle") is trip.npc_vehicles[0]
    )
    assert "1.3 kilometers ahead" in npc_cue.message
    assert "68 kilometers per hour" in npc_cue.message
    assert "miles" not in npc_cue.message


def test_npc_traffic_status_includes_speed_units(world):
    trip, _truck = make_trip(world)
    trip.position_mi = 10.0
    trip.npc_vehicles = [
        NPCVehicle("npc:status", 10.8, 68.0, 68.0, 0, "steady_truck")
    ]

    assert "moving 68 miles per hour" in trip.npc_traffic_status()


def test_time_scale_compresses_fuel_burn(world):
    trip, truck = make_trip(world, time_scale=40.0)
    truck.throttle = 0.9
    for _ in range(60 * 30):
        truck.auto_shift()
        truck.update(1 / 60)
        trip.update(1 / 60)
    assert truck.fuel_burn_mult == 40.0
    assert truck.fuel_gal < truck.specs.fuel_tank_gal - 0.5


def test_every_region_has_clear_day_hazards():
    """Every region always has plausible clear, calm, daytime hazards: the
    nationwide staples are never filtered out."""
    from freight_fate.sim.trip import WeatherKind, eligible_hazards

    noon = 12.0
    for region in list(REGION_WEIGHTS) + ["atlantis"]:
        pool = dict(eligible_hazards(region, WeatherKind.CLEAR, "flat", noon))
        assert "debris on the road" in pool
        # No weather- or terrain-specific hazard leaks into a clear flat day:
        # nothing about snow, fog, wind, water, or mountain rockfall. (Wildlife
        # is not weather-gated -- it stays eligible but heavily down-weighted
        # by day -- so animal hazards are deliberately not excluded here.)
        text = " ".join(pool)
        for word in ("snow", "ice", "fog", "crosswind", "dust", "water",
                     "hail", "rockfall", "tumbleweed"):
            assert word not in text, f"{word!r} should not occur on a clear day"


def test_weather_and_terrain_gate_hazards():
    from freight_fate.sim.trip import WeatherKind, eligible_hazards

    # Snow hazards only appear when it is snowing.
    clear = dict(eligible_hazards("great_lakes", WeatherKind.CLEAR, "flat", 12.0))
    snowy = dict(eligible_hazards("great_lakes", WeatherKind.SNOW, "flat", 12.0))
    assert not any("snow" in t or "ice" in t for t in clear)
    assert any("snow" in t for t in snowy)

    # Rockfall is a mountain-terrain hazard, not a flatland one.
    flat = dict(eligible_hazards("rockies", WeatherKind.CLEAR, "flat", 12.0))
    mountain = dict(eligible_hazards("rockies", WeatherKind.CLEAR, "mountain", 12.0))
    assert "rockfall debris on the road" not in flat
    assert "rockfall debris on the road" in mountain

    # The dropped, implausible hazards are gone for good.
    everything = {
        t
        for region in REGION_WEIGHTS
        for weather in WeatherKind
        for terrain in ("flat", "hills", "mountain")
        for t, _ in eligible_hazards(region, weather, terrain, 3.0)
    }
    assert not any("farm equipment" in t for t in everything)
    assert not any("dust devil" in t for t in everything)


def test_wildlife_is_biased_to_dawn_dusk_and_night():
    """Deer and elk are far likelier at night than at midday, and the same
    catalog drives both -- only the time of day changes the weight."""
    from freight_fate.sim.trip import WeatherKind, eligible_hazards

    day = dict(eligible_hazards("great_lakes", WeatherKind.CLEAR, "flat", 12.0))
    night = dict(eligible_hazards("great_lakes", WeatherKind.CLEAR, "flat", 23.0))
    deer = "a deer crossing the road"
    assert night[deer] > day[deer]
    # Non-animal staples keep the same weight regardless of the hour.
    assert night["debris on the road"] == day["debris on the road"]


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
    assert "Indianapolis, Indiana" in text
    assert "Grade level" in text
    # The summary reports the nearest upcoming cue; an early stop leads here.
    assert "Next stop" in text
    metric = trip.progress_summary(imperial=False)
    assert "kilometers" in metric

    # Once past that stop, the summary surfaces the upcoming state-line crossing.
    trip.position_mi = 25.0
    state_text = trip.progress_summary()
    assert "Next state line" in state_text
    assert "Illinois into Indiana" in state_text


def test_gps_state_crossing_and_rest_stop_cues_deduplicate(world):
    trip, _truck = make_trip(world)

    trip.position_mi = 23.0
    advance = trip.update(0.0)
    repeat = trip.update(0.0)

    assert _gps_messages(advance) == [
        "In 10 miles, crossing from Illinois into Indiana near "
        "the I-65 state line south of Hammond."
    ]
    assert not _gps_events(repeat)

    trip.position_mi = 31.5
    near = trip.update(0.0)
    assert not _gps_events(near)

    trip.position_mi = 32.8
    crossing = trip.update(0.0)
    assert [event.message for event in crossing
            if event.kind == TripEventKind.STATE_CROSSING] == [
        "Crossing into Indiana near the I-65 state line south of Hammond."
    ]

    trip.position_mi = 120.3
    rest = trip.update(0.0)
    assert any(
        event.kind == TripEventKind.GPS_CUE
        and event.message == (
            "Travel center at exit 175 ahead in 1 mile; confirmed truck parking; "
            "press X to signal for the exit."
        )
        for event in rest
    )


def test_likely_parking_is_not_announced_as_truck_parking():
    assert Stop("Fuel", 1.0, parking="likely").parking_label == ""
    assert RoadStop("Fuel", 1.0, parking="likely").parking_text == ""


def test_likely_parking_route_cue_just_announces_stop(world):
    trip, _truck = make_trip(world)
    leg = trip.route.legs[0]
    likely_stop = next(stop for stop in leg.stops if stop.parking == "likely")
    cue = next(cue for cue in trip.navigation_cues
               if cue.key.endswith(f":{likely_stop.name}"))

    assert "likely truck parking" not in cue.near_text
    assert cue.near_text.startswith(likely_stop.label.capitalize())
    assert cue.near_text.endswith("ahead in 1 mile; press X to signal for the exit.")
    assert ";;" not in cue.near_text


def test_gps_traffic_cue_deduplicates(world):
    trip, _truck = make_trip(world)
    trip.navigation_cues.append(NavigationCue(
        "traffic:test",
        "traffic",
        10.0,
        "traffic queue ahead at 45 miles per hour",
        "Traffic slowing ahead; target speed 45.",
    ))

    trip.position_mi = 8.5
    first = trip.update(0.0)
    second = trip.update(0.0)

    assert _gps_messages(first) == [
        "Traffic slowing ahead in 2 miles; traffic queue ahead at 45 miles per hour."
    ]
    assert not _gps_events(second)


def test_route_context_describes_near_traffic_without_zero_distance(world):
    trip, _truck = make_trip(world)
    trip.navigation_cues = [NavigationCue(
        "traffic:test",
        "traffic",
        10.1,
        "traffic queue ahead",
        speed_mph=45.0,
    )]
    trip.position_mi = 10.0

    context = trip.next_navigation_context()

    assert context == "Traffic just ahead: traffic queue ahead at 45 miles per hour."
    assert "0" not in context


def test_toll_cues_and_charges_deduplicate(world):
    trip, _truck = make_trip(world, "New York", "Philadelphia")

    trip.position_mi = 6.1
    advance = trip.update(0.0)
    repeat = trip.update(0.0)

    assert _gps_messages(advance) == [
        "ticket system toll point ahead: New Jersey Turnpike ticket entry. "
        "estimated toll 18 dollars will be billed to carrier settlement."
    ]
    assert not _gps_events(repeat)

    trip.position_mi = 8.0
    charged = trip.update(0.0)
    charged_again = trip.update(0.0)

    assert [event.message for event in charged
            if event.kind == TripEventKind.TOLL_CHARGED] == [
        "ticket system toll charged at New Jersey Turnpike ticket entry: "
        "Estimated 18 dollars, billed to carrier settlement."
    ]
    assert trip.toll_expense == 18.0
    assert not [event for event in charged_again
                if event.kind == TripEventKind.TOLL_CHARGED]


def test_non_toll_route_does_not_charge_tolls(world):
    trip, _truck = make_trip(world, "Chicago", "Indianapolis")

    trip.position_mi = trip.total_miles
    events = trip.update(0.0)

    assert trip.toll_expense == 0.0
    assert not [event for event in events if event.kind == TripEventKind.TOLL_CHARGED]


def test_zero_amount_toll_entry_marker_does_not_record_expense(world):
    trip, _truck = make_trip(world, "Philadelphia", "Pittsburgh")

    trip.position_mi = 16.1
    advance = trip.update(0.0)
    assert _gps_messages(advance) == [
        "ticket system toll point ahead: Pennsylvania Turnpike eastern ticket entry. "
        "entry will be recorded for carrier settlement."
    ]

    trip.position_mi = 18.0
    entry = trip.update(0.0)
    assert _gps_messages(entry) == [
        "ticket system entry recorded at Pennsylvania Turnpike eastern ticket entry; "
        "toll will be billed at carrier settlement."
    ]
    assert trip.toll_expense == 0.0
    assert not [event for event in entry if event.kind == TripEventKind.TOLL_CHARGED]


def test_traffic_context_and_warning_are_grounded_in_lead_vehicle(world):
    trip, truck = make_trip(world)
    truck.velocity_mps = 29.0
    trip.position_mi = 9.98
    trip.npc_vehicles = [
        NPCVehicle("npc:queue", 10.0, 45.0, 45.0, 0, "braking_traffic")
    ]

    context = trip.traffic_context()
    assert context is not None
    assert context.lead.speed_mph == 45.0
    assert context.closing_mph > 15.0
    assert trip.traffic_target_speed() == 45.0

    events = trip.update(1.0)

    hazards = [event for event in events if event.kind == TripEventKind.HAZARD]
    assert hazards
    assert "Brake lights" in hazards[0].message
    assert "traffic" in hazards[0].data


def test_city_events_announce_state_crossings(world):
    route = world.route_from_cities(["Chicago", "Cleveland", "Pittsburgh"])
    truck = TruckState()
    weather = WeatherSystem("great_lakes", seed=1)
    trip = Trip(route, truck, weather, seed=2)
    trip.position_mi = route.legs[0].miles

    events = trip.update(0.0)

    city_events = [e.message for e in events if e.kind == TripEventKind.CITY_REACHED]
    assert city_events == [
        "Crossing into Ohio. Passing Cleveland, Ohio. "
        "Continuing on I-76 toward Pittsburgh."
    ]


def test_city_events_include_state_without_repeating_crossing(world):
    route = world.route_from_cities(["New York", "Buffalo", "Cleveland"])
    truck = TruckState()
    weather = WeatherSystem("northeast", seed=1)
    trip = Trip(route, truck, weather, seed=2)
    trip.position_mi = route.legs[0].miles

    events = trip.update(0.0)

    city_events = [e.message for e in events if e.kind == TripEventKind.CITY_REACHED]
    assert city_events == [
        "Passing Buffalo, New York. Continuing on I-90 toward Cleveland."
    ]
