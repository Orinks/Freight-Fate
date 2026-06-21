"""Weather system and trip simulation tests."""

import itertools

from freight_fate.sim import Trip, TruckState, WeatherKind, WeatherSystem
from freight_fate.sim.trip import NavigationCue, TrafficLead, TripEventKind
from freight_fate.sim.weather import EFFECTS, REGION_WEIGHTS


def test_all_conditions_have_effects():
    for kind in WeatherKind:
        assert kind in EFFECTS


def test_all_regions_in_world_have_weights(world):
    regions = {c.region for c in world.cities.values()}
    for region in regions:
        assert region in REGION_WEIGHTS, f"no weather weights for {region}"


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

    assert [stop.name for stop in trip.stops] == [
        "Pilot Travel Center Remington",
        "Loves Travel Stop Lafayette",
    ]
    assert [stop.at_mi for stop in trip.stops] == [93.5, 121.3]
    assert all(stop.at_mi != trip.route.miles / 2 for stop in trip.stops)
    assert all(stop.parking == "confirmed" for stop in trip.stops)


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

    assert [stop.name for stop in trip.stops] == [
        "Hill County Safety Rest Area",
        "Road Ranger Waco",
        "Bell County Safety Rest Area",
    ]
    assert [round(stop.at_mi, 1) for stop in trip.stops] == [56.8, 89.7, 136.5]


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
    trip, _ = make_trip(world, "Chicago", "Indianapolis", seed=12345)
    zone = next(z for z in trip.zones if z.reason == "construction")

    trip.position_mi = zone.start_mi - 2.0
    events = trip.update(0.0)

    warnings = [event.message for event in events if event.kind == TripEventKind.GPS_CUE]
    assert warnings == [
        f"In 2 miles, construction ahead. Speed limit {zone.limit_mph:.0f}."
    ]


def test_construction_zone_does_not_fine_on_entry_tick(world):
    trip, truck = make_trip(world, "Chicago", "Indianapolis", seed=12345)
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
    trip, truck = make_trip(world, "Chicago", "Indianapolis", seed=12345)
    zone = next(z for z in trip.zones if z.reason == "construction")
    truck.velocity_mps = 31.3   # about 70 mph

    trip.position_mi = zone.start_mi - 2.0
    advance = trip.update(0.0)
    assert [event.message for event in advance if event.kind == TripEventKind.GPS_CUE] == [
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
    assert "Indianapolis, Indiana" in text
    assert "Grade level" in text
    assert "Next state line" in text
    assert "Illinois into Indiana" in text
    metric = trip.progress_summary(imperial=False)
    assert "kilometers" in metric


def test_gps_state_crossing_and_rest_stop_cues_deduplicate(world):
    trip, _truck = make_trip(world)

    trip.position_mi = 30.8
    advance = trip.update(0.0)
    repeat = trip.update(0.0)

    assert [event.message for event in advance if event.kind == TripEventKind.GPS_CUE] == [
        "In 2 miles, crossing from Illinois into Indiana near "
        "the I-65 state line south of Hammond."
    ]
    assert not [event for event in repeat if event.kind == TripEventKind.GPS_CUE]

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
            "Travel center ahead in 1 mile; confirmed truck parking; "
            "press X to take the exit."
        )
        for event in rest
    )


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

    assert [event.message for event in first if event.kind == TripEventKind.GPS_CUE] == [
        "Traffic slowing ahead in 2 miles; traffic queue ahead at 45 miles per hour."
    ]
    assert not [event for event in second if event.kind == TripEventKind.GPS_CUE]


def test_toll_cues_and_charges_deduplicate(world):
    trip, _truck = make_trip(world, "New York", "Philadelphia")

    trip.position_mi = 6.1
    advance = trip.update(0.0)
    repeat = trip.update(0.0)

    assert [event.message for event in advance if event.kind == TripEventKind.GPS_CUE] == [
        "ticket system toll point ahead: New Jersey Turnpike ticket entry. "
        "estimated toll 18 dollars will be billed to carrier settlement."
    ]
    assert not [event for event in repeat if event.kind == TripEventKind.GPS_CUE]

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
    assert [event.message for event in advance if event.kind == TripEventKind.GPS_CUE] == [
        "ticket system toll point ahead: Pennsylvania Turnpike eastern ticket entry. "
        "entry will be recorded for carrier settlement."
    ]

    trip.position_mi = 18.0
    entry = trip.update(0.0)
    assert [event.message for event in entry if event.kind == TripEventKind.GPS_CUE] == [
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
