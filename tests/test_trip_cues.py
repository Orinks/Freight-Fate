"""Trip hazard, GPS cue, toll, and city-event tests."""

from test_weather_trip import _gps_events, _gps_messages, make_trip

from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.trip import NavigationCue, NPCVehicle, TripEventKind
from freight_fate.sim.weather import REGION_WEIGHTS


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
    trip.traffic_manager.vehicles = []

    # State crossings speak once, at the line -- the old 10-mile advance
    # warning was cut in the reduce-repeated-alerts player-feedback round.
    trip.position_mi = 23.0
    advance = trip.update(0.0)
    repeat = trip.update(0.0)
    assert not _gps_events(advance)
    assert not _gps_events(repeat)

    trip.position_mi = 31.5
    near = trip.update(0.0)
    assert not _gps_events(near)

    trip.position_mi = 32.8
    crossing = trip.update(0.0)
    assert [event.message for event in crossing if event.kind == TripEventKind.STATE_CROSSING] == [
        "Crossing into Indiana near the I-65 state line south of Hammond."
    ]
    again = trip.update(0.0)
    assert not [e for e in again if e.kind == TripEventKind.STATE_CROSSING]

    # Road stops keep their single actionable announcement from _check_stops
    # at five miles; the extra one-mile reminder is gone for the same reason.
    trip.position_mi = 120.3
    rest = trip.update(0.0)
    assert not _gps_events(rest)


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


def test_toll_cues_and_charges_deduplicate(world):
    trip, _truck = make_trip(world, "New York", "Philadelphia")

    # No advance state-crossing chatter -- the line itself will speak when
    # the truck reaches it.
    trip.position_mi = 6.1
    crossing = trip.update(0.0)
    assert not _gps_events(crossing)

    trip.position_mi = 7.2
    advance = trip.update(0.0)
    repeat = trip.update(0.0)

    assert _gps_messages(advance) == [
        "ticket system toll point ahead: New Jersey Turnpike ticket entry. "
        "estimated toll 18 dollars will be billed to carrier settlement."
    ]
    assert not _gps_events(repeat)

    trip.position_mi = 9.0
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
    trip.traffic_manager.vehicles = [
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
