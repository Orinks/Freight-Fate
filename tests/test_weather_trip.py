"""Weather system and trip simulation tests."""

import itertools
from dataclasses import replace

import pytest

from freight_fate.data.world_models import Stop
from freight_fate.sim import Trip, TruckState, WeatherKind, WeatherSystem
from freight_fate.sim.trip import NavigationCue, TrafficLead, TripEventKind
from freight_fate.sim.trip_models import RoadStop
from freight_fate.sim.weather import EFFECTS, REGION_WEIGHTS


def _gps_events(events):
    """GPS-cue events, excluding additive interchange/exit cues. Tests below
    target one specific cue (toll, state line, construction, traffic); curated
    interchanges share the GPS-cue stream, so filter them out to keep those
    assertions about the cue they mean."""
    return [
        e
        for e in events
        if e.kind == TripEventKind.GPS_CUE
        and getattr(e.data.get("cue"), "kind", "") != "interchange"
    ]


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


def test_offline_live_weather_change_is_identified_as_simulated_fallback(world):
    class OfflineProvider:
        def request(self, *args):
            pass

        def get(self, city):
            return None

        def unavailable(self, city):
            return True

    trip, _truck = make_trip(world)
    trip.weather.provider = OfflineProvider()
    trip.weather.minutes_until_change = 0.0
    trip.weather._sample = lambda *args, **kwargs: WeatherKind.RAIN

    events = trip.update(1.0)

    change = next(event for event in events if event.kind is TripEventKind.WEATHER_CHANGE)
    assert change.message.startswith("Simulated fallback weather changing: rain")


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


def test_relaxed_hazard_scale_lowers_hazard_risk(world):
    """Relaxed mode keeps random road hazards rare via the hazard scale."""
    from freight_fate.sim.hos import RELAXED_HAZARD_SCALE

    normal, _ = make_trip(world, seed=4)
    relaxed, _ = make_trip(world, seed=4, hazard_scale=RELAXED_HAZARD_SCALE)
    # Same route, weather, and clock: the only difference is the scale.
    assert relaxed._hazard_risk() == pytest.approx(normal._hazard_risk() * RELAXED_HAZARD_SCALE)
    assert relaxed._hazard_risk() < normal._hazard_risk()


def test_relaxed_mode_thins_traffic_density(world):
    """Relaxed mode also makes ambient traffic rarer, not just hazards."""
    from freight_fate.sim.hos import RELAXED_HAZARD_SCALE

    normal, _ = make_trip(world, seed=4)
    relaxed, _ = make_trip(world, seed=4, hazard_scale=RELAXED_HAZARD_SCALE)
    leg = normal.route.legs[0]
    assert relaxed._leg_traffic_density(leg, 0.0, False) == pytest.approx(
        normal._leg_traffic_density(leg, 0.0, False) * RELAXED_HAZARD_SCALE
    )
    assert relaxed._leg_traffic_density(leg, 0.0, False) < normal._leg_traffic_density(
        leg, 0.0, False
    )


def test_relaxed_mode_thins_random_inspection_odds(world):
    """Relaxed mode pulls a violating driver over less often; the random log
    check is thinned by the hazard scale (weigh stations are not)."""
    from freight_fate.sim.hos import RELAXED_HAZARD_SCALE

    normal, _ = make_trip(world, seed=4)
    relaxed, _ = make_trip(world, seed=4, hazard_scale=RELAXED_HAZARD_SCALE)
    leg = normal.route.legs[0]
    assert relaxed._random_inspection_odds(leg) == pytest.approx(
        normal._random_inspection_odds(leg) * RELAXED_HAZARD_SCALE
    )
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
    for _ in range(200):  # never drifts off the forced condition
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
    truck.drag_mult = 1.25  # a strong headwind / storm
    assert truck.resistance_force() > base


def test_visibility_shortens_hazard_reaction(world):
    trip, _ = make_trip(world)
    trip.weather.current = WeatherKind.CLEAR
    assert trip._visibility_reaction_factor() == 1.0
    trip.weather.current = WeatherKind.HEAVY_RAIN  # 1.5 mi visibility
    assert trip._visibility_reaction_factor() == pytest.approx(0.5)
    trip.weather.current = WeatherKind.FOG  # 0.3 mi -> floored
    assert trip._visibility_reaction_factor() == pytest.approx(0.4)


def test_too_fast_for_conditions_risks_traction_loss(world):
    trip, truck = make_trip(world)
    trip._hazard_check_mi = 1e9  # silence the random environmental hazards
    trip._inspection_check_mi = 1e9
    trip.traffic_leads = []

    def run_for_hazard(frames=12000):
        hits = []
        for _ in range(frames):
            trip.weather.current = WeatherKind.SNOW  # grip 0.45, safe speed 35
            truck.velocity_mps = 27.0  # ~60 mph, well over safe
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
    trip2.traffic_leads = []
    safe_hits = []
    for _ in range(6000):
        trip2.weather.current = WeatherKind.SNOW
        truck2.velocity_mps = 14.0  # ~31 mph, under safe 35
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
    route = world.facility_approach_route("Chicago", world.city("Chicago").locations[0].name)
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
    route = world.facility_approach_route("Chicago", world.city("Chicago").locations[0].name)
    truck = TruckState()
    weather = WeatherSystem("great_lakes", seed=1)
    trip = Trip(route, truck, weather, seed=2)

    trip.position_mi = trip.total_miles - 2.0
    events = trip.update(0.0)

    warnings = [event.message for event in events if event.kind == TripEventKind.GPS_CUE]
    assert "In 2 miles, facility gate ahead. Speed limit 15." in warnings


def test_construction_zone_warns_before_entry(world):
    trip, _ = make_trip(world, "Chicago", "Indianapolis", seed=12345)
    zone = next(z for z in trip.zones if z.reason == "construction")

    trip.position_mi = zone.start_mi - 2.0
    events = trip.update(0.0)

    warnings = _gps_messages(events)
    assert warnings == [f"In 2 miles, construction ahead. Speed limit {zone.limit_mph:.0f}."]


def test_construction_zone_does_not_fine_on_entry_tick(world):
    trip, truck = make_trip(world, "Chicago", "Indianapolis", seed=12345)
    zone = next(z for z in trip.zones if z.reason == "construction")
    truck.velocity_mps = 31.3  # about 70 mph

    trip.position_mi = zone.start_mi - 0.2
    moved_mi = 0.35
    trip.position_mi += moved_mi
    trip._check_zones()
    trip._check_inspections(moved_mi)

    kinds = [event.kind for event in trip._events]
    assert TripEventKind.ZONE_ENTER in kinds
    assert TripEventKind.INSPECTION not in kinds


def test_construction_zone_speeding_fine_waits_for_grace_distance(world):
    trip, truck = make_trip(world, "Chicago", "Indianapolis", seed=12345)
    zone = next(z for z in trip.zones if z.reason == "construction")
    truck.velocity_mps = 31.3  # about 70 mph

    trip.position_mi = zone.start_mi - 2.0
    advance = trip.update(0.0)
    assert _gps_messages(advance) == [
        f"In 2 miles, construction ahead. Speed limit {zone.limit_mph:.0f}."
    ]

    trip.position_mi = zone.start_mi + 0.3
    trip._events = []
    trip._check_zones()
    trip._check_inspections(0.4)
    assert not [event for event in trip._events if event.kind == TripEventKind.INSPECTION]

    trip.position_mi = zone.start_mi + 1.1
    trip._events = []
    trip._check_inspections(0.8)
    inspection = [event for event in trip._events if event.kind == TripEventKind.INSPECTION]
    assert [event.message for event in inspection] == [
        "Trooper in the construction zone clocks your speed."
    ]


def test_grades_are_bounded(world):
    trip, _ = make_trip(world, "Denver", "Salt Lake City")
    for mile in range(0, int(trip.total_miles), 3):
        assert abs(trip.grade_at(float(mile))) <= 0.08


def test_route_derived_flat_grade_is_stable_across_trip_seeds(world):
    trip_a, _ = make_trip(world, seed=1)
    trip_b, _ = make_trip(world, seed=99)
    miles = [0.0, 20.0, 33.0, 72.0, 122.0, 183.0]

    assert [trip_a.grade_at(mile) for mile in miles] == [trip_b.grade_at(mile) for mile in miles]
    assert max(abs(trip_a.grade_at(mile)) for mile in miles) < 0.002
    assert {trip_a.terrain_at(mile) for mile in miles} == {"flat"}


def test_traffic_varies_by_seed_but_route_grade_does_not(world):
    trip_a, _ = make_trip(world, seed=1)
    trip_b, _ = make_trip(world, seed=8)

    assert [trip_a.grade_at(mile) for mile in (10.0, 80.0, 150.0)] == [
        trip_b.grade_at(mile) for mile in (10.0, 80.0, 150.0)
    ]
    assert [(lead.at_mi, lead.speed_mph, lead.reason) for lead in trip_a.traffic_leads] != [
        (lead.at_mi, lead.speed_mph, lead.reason) for lead in trip_b.traffic_leads
    ]


def test_traffic_model_applies_to_enriched_and_legacy_routes(world):
    for cities in (["Chicago", "Indianapolis"], ["Chicago", "St. Louis"]):
        route = world.route_from_cities(cities)
        truck = TruckState()
        weather = WeatherSystem("great_lakes", seed=1)
        weather.current = WeatherKind.CLEAR
        trip = Trip(route, truck, weather, seed=1)
        assert trip.traffic_leads, cities


def test_bad_weather_slows_modeled_traffic(world):
    route = world.route_from_cities(["Chicago", "Indianapolis"])
    clear_weather = WeatherSystem("great_lakes", seed=1)
    clear_weather.current = WeatherKind.CLEAR
    rain_weather = WeatherSystem("great_lakes", seed=1)
    rain_weather.current = WeatherKind.HEAVY_RAIN

    clear = Trip(route, TruckState(), clear_weather, seed=1)
    rain = Trip(route, TruckState(), rain_weather, seed=1)

    assert clear.traffic_leads
    assert rain.traffic_leads
    assert rain.traffic_leads[0].at_mi == clear.traffic_leads[0].at_mi
    assert rain.traffic_leads[0].speed_mph < clear.traffic_leads[0].speed_mph
    assert "visibility" in rain.traffic_leads[0].reason


def test_time_scale_compresses_fuel_burn(world):
    trip, truck = make_trip(world, time_scale=40.0)
    truck.velocity_mps = 26.0  # already at cruise: full pacing applies
    truck.throttle = 0.9
    for _ in range(60 * 30):
        truck.auto_shift()
        truck.update(1 / 60)
        trip.update(1 / 60)
    assert truck.fuel_burn_mult == 40.0
    assert truck.fuel_gal < truck.specs.fuel_tank_gal - 0.5


def test_clock_compression_ramps_with_road_speed(world):
    """Physics runs in real time, so the clock eases off while maneuvering:
    working up through the gears must not bill an hour of game time. Full
    pacing only applies once the truck is at highway speed."""
    from freight_fate.sim.trip import FULL_COMPRESSION_MPH, LOW_SPEED_TIME_SCALE

    trip, truck = make_trip(world, time_scale=20.0)

    truck.velocity_mps = 0.0  # parked: near real-time pacing
    assert trip.effective_time_scale == pytest.approx(LOW_SPEED_TIME_SCALE)
    before = trip.game_minutes
    trip.update(1.0)
    assert trip.game_minutes - before == pytest.approx(LOW_SPEED_TIME_SCALE / 60.0)

    truck.velocity_mps = 25.0 / 2.23694  # 25 mph: mid-ramp
    mid = trip.effective_time_scale
    assert LOW_SPEED_TIME_SCALE < mid < 20.0

    truck.velocity_mps = (FULL_COMPRESSION_MPH + 10.0) / 2.23694  # cruise
    assert trip.effective_time_scale == pytest.approx(20.0)
    before = trip.game_minutes
    trip.update(1.0)
    assert trip.game_minutes - before == pytest.approx(20.0 / 60.0)


def test_parking_brake_waiting_runs_at_double_pacing(world):
    """Player-armed waiting (brake set by their own press) runs the clock at
    double the configured pacing; the auto-set brake at trip start does not,
    and rolling never fast-forwards even with waiting armed."""
    from freight_fate.sim.trip import LOW_SPEED_TIME_SCALE, PARKED_TIME_SCALE_MULT

    trip, truck = make_trip(world, time_scale=20.0)

    truck.velocity_mps = 0.0
    truck.parking_brake = True  # auto-set (trip start): not waiting
    assert trip.effective_time_scale == pytest.approx(LOW_SPEED_TIME_SCALE)

    trip.waiting = True  # the player's own brake press arms it
    assert trip.effective_time_scale == pytest.approx(20.0 * PARKED_TIME_SCALE_MULT)
    before = trip.game_minutes
    trip.update(1.0)
    assert trip.game_minutes - before == pytest.approx(20.0 * PARKED_TIME_SCALE_MULT / 60.0)
    assert trip.waiting  # still parked: stays armed

    truck.velocity_mps = 5.0 / 2.23694  # rolling with the brake dragging
    assert trip.effective_time_scale < 20.0 * PARKED_TIME_SCALE_MULT / 2.0

    truck.velocity_mps = 0.0
    truck.parking_brake = False  # any release path disarms on the next frame
    trip.update(1.0)
    assert not trip.waiting
    assert trip.effective_time_scale == pytest.approx(LOW_SPEED_TIME_SCALE)


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
        for word in (
            "snow",
            "ice",
            "fog",
            "crosswind",
            "dust",
            "water",
            "hail",
            "rockfall",
            "tumbleweed",
        ):
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
    trip.position_mi = stop.at_mi + 0.1  # just past: the exit is gone
    next_stop = trip.upcoming_stop(5.0)
    assert next_stop is not stop


def test_eta_tracks_current_speed(world):
    """Regression: the C key's ETA was a constant 55 mph guess that never
    responded to how fast you were actually going."""
    trip, truck = make_trip(world)
    parked = trip.eta_game_hours()
    assert parked > 0
    truck.velocity_mps = 31.3  # ~70 mph
    fast = trip.eta_game_hours()
    truck.velocity_mps = 13.4  # ~30 mph
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
    assert "Current grade 0.0 percent, level" in text
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

    trip.position_mi = 28.0
    advance = trip.update(0.0)
    repeat = trip.update(0.0)

    assert not _gps_events(advance)
    assert not [event for event in advance if event.kind == TripEventKind.STATE_CROSSING]
    assert not _gps_events(repeat)

    trip.position_mi = 31.5
    near = trip.update(0.0)
    assert not _gps_events(near)

    trip.position_mi = 32.8
    crossing = trip.update(0.0)
    assert [event.message for event in crossing if event.kind == TripEventKind.STATE_CROSSING] == [
        "Crossing into Indiana near the I-65 state line south of Hammond."
    ]

    trip.position_mi = 120.3
    rest = trip.update(0.0)
    assert not _gps_events(rest)


def test_likely_parking_is_not_announced_as_truck_parking():
    assert Stop("Fuel", 1.0, parking="likely").parking_label == ""
    assert RoadStop("Fuel", 1.0, parking="likely").parking_text == ""


def test_likely_parking_route_cue_just_announces_stop(world):
    trip, _truck = make_trip(world)
    leg = trip.route.legs[0]
    likely_stop = next(stop for stop in leg.stops if stop.parking == "likely")
    cue = next(cue for cue in trip.navigation_cues if cue.key.endswith(f":{likely_stop.name}"))

    assert cue.near_text == ""


def test_gps_traffic_cue_deduplicates(world):
    trip, _truck = make_trip(world)
    trip.navigation_cues.append(
        NavigationCue(
            "traffic:test",
            "traffic",
            10.0,
            "traffic queue ahead at 45 miles per hour",
            "Traffic slowing ahead; target speed 45.",
        )
    )

    trip.position_mi = 8.5
    first = trip.update(0.0)
    second = trip.update(0.0)

    assert _gps_messages(first) == [
        "Traffic slowing ahead in 2 miles; traffic queue ahead at 45 miles per hour."
    ]
    assert not _gps_events(second)


def test_route_context_describes_near_traffic_without_zero_distance(world):
    trip, _truck = make_trip(world)
    trip.navigation_cues = [
        NavigationCue(
            "traffic:test",
            "traffic",
            10.1,
            "traffic queue ahead",
            speed_mph=45.0,
        )
    ]
    trip.position_mi = 10.0

    context = trip.next_navigation_context()

    assert context == "Traffic just ahead: traffic queue ahead at 45 miles per hour."
    assert "0" not in context


def test_toll_cues_and_charges_deduplicate(world):
    trip, _truck = make_trip(world, "New York", "Philadelphia")

    # I-95 south from the Hunts Point node crosses to NJ at the GWB (mi 7.0);
    # the NJ Turnpike ticket toll follows at mi 8.9, so probe just past the
    # crossing to isolate the toll cue.
    trip.position_mi = 7.3
    advance = trip.update(0.0)
    repeat = trip.update(0.0)

    assert _gps_messages(advance) == [
        "ticket system toll point ahead: New Jersey Turnpike ticket entry. "
        "estimated toll 18 dollars will be billed to carrier settlement."
    ]
    assert not _gps_events(repeat)

    trip.position_mi = 9.5
    charged = trip.update(0.0)
    charged_again = trip.update(0.0)

    assert [event.message for event in charged if event.kind == TripEventKind.TOLL_CHARGED] == [
        "ticket system toll charged at New Jersey Turnpike ticket entry: "
        "Estimated 18 dollars, billed to carrier settlement."
    ]
    assert trip.toll_expense == 18.0
    assert not [event for event in charged_again if event.kind == TripEventKind.TOLL_CHARGED]


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
    trip.traffic_leads = [TrafficLead(10.0, 45.0, "traffic queue ahead", 4.0)]

    context = trip.traffic_context()
    assert context is not None
    assert context.lead.speed_mph == 45.0
    assert context.closing_mph > 15.0
    assert trip.traffic_target_speed() == 45.0

    events = trip.update(1.0)

    hazards = [event for event in events if event.kind == TripEventKind.HAZARD]
    assert hazards
    assert "Traffic queue ahead" in hazards[0].message
    assert "traffic" in hazards[0].data


def test_city_events_do_not_repeat_mapped_state_crossings(world):
    route = world.route_from_cities(["Chicago", "Cleveland", "Pittsburgh"])
    truck = TruckState()
    weather = WeatherSystem("great_lakes", seed=1)
    trip = Trip(route, truck, weather, seed=2)
    trip.position_mi = route.legs[0].miles

    events = trip.update(0.0)

    city_events = [e.message for e in events if e.kind == TripEventKind.CITY_REACHED]
    assert city_events == ["Passing Cleveland, Ohio. Continuing on I-76 toward Pittsburgh."]
    state_events = [e.message for e in events if e.kind == TripEventKind.STATE_CROSSING]
    assert any(message.startswith("Crossing into Ohio near ") for message in state_events)


def test_city_events_keep_crossing_fallback_without_mapped_state_line(world):
    route = world.route_from_cities(["Chicago", "Cleveland", "Pittsburgh"])
    route.legs[0] = replace(route.legs[0], state_crossings=())
    truck = TruckState()
    weather = WeatherSystem("great_lakes", seed=1)
    trip = Trip(route, truck, weather, seed=2)
    trip.position_mi = route.legs[0].miles

    events = trip.update(0.0)

    city_events = [e.message for e in events if e.kind == TripEventKind.CITY_REACHED]
    assert city_events == [
        "Crossing into Ohio. Passing Cleveland, Ohio. Continuing on I-76 toward Pittsburgh."
    ]


def test_city_events_include_state_without_repeating_crossing(world):
    route = world.route_from_cities(["New York", "Buffalo", "Cleveland"])
    truck = TruckState()
    weather = WeatherSystem("northeast", seed=1)
    trip = Trip(route, truck, weather, seed=2)
    trip.position_mi = route.legs[0].miles

    events = trip.update(0.0)

    city_events = [e.message for e in events if e.kind == TripEventKind.CITY_REACHED]
    assert city_events == ["Passing Buffalo, New York. Continuing on I-90 toward Cleveland."]
