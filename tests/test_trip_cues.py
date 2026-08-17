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
    trip.traffic_manager.rolling_bubble = False
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
    # The dense maxspeed sweep gives this I-65 leg a real 65 mph zone at mile
    # 120; arriving from the 55 zone at the crossing announces that raise. The
    # rest-stop cue still does not re-fire -- that is what this asserts.
    assert _gps_messages(rest) == ["Speed limit raised to 65."]


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
    trip.traffic_manager.rolling_bubble = False
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


def test_zone_warnings_come_one_at_a_time_and_never_for_one_underfoot(world):
    """Owner playtest, 2026-08-17: five contradictory lines in sixty
    milliseconds on a facility approach.

    A tier-1 surface chain zones each street at its own baked speed, so a
    one-mile approach holds four or five zones. Warning every zone inside the
    lookahead fired them all at once -- "access road ahead, speed limit 15"
    hard against "access road ahead, speed limit 25", neither of them the
    number then in force, so the spoken limit contradicted what S answered.
    """
    from freight_fate.sim.trip import ZONE_WARNING_MIN_MI
    from freight_fate.sim.trip_models import Zone

    trip, _truck = make_trip(world)
    trip.zones = [
        Zone(0.05, 0.30, 15.0, "facility access road"),  # underfoot: no warning
        Zone(0.60, 1.00, 25.0, "facility access road"),
        Zone(1.00, 1.40, 15.0, "facility access road"),
        Zone(1.40, 1.60, 15.0, "facility gate"),
    ]
    trip._announced_zone_warnings.clear()
    trip._pending_zone_warning = None
    trip.position_mi = 0.0

    # Several ticks at a standstill: the loop runs every frame and must not
    # spend the whole approach's worth of warnings on the first one.
    for _ in range(5):
        trip._events.clear()
        trip._check_zones()
    warned = [e for e in trip._events if e.kind is TripEventKind.GPS_CUE]
    assert len(warned) <= 1, "one outstanding warning, not one per frame"

    # And nothing was said about the zone already under the wheels.
    said = " ".join(e.message for e in warned)
    assert "15" not in said or ZONE_WARNING_MIN_MI < 0.05


def test_distances_to_things_ahead_never_round_down_to_zero(world):
    """Owner playtest, 2026-08-17: "What is this in 0 miles BS?"

    ``_distance_text`` rounds to whole units, so every warning inside half a
    mile announced itself as "in 0 miles" -- which reads as "no distance at
    all" when the honest answer is "a quarter mile, get ready". Anything
    still in FRONT of the truck goes through ``_ahead_text`` instead, which
    steps in quarter miles down to "just ahead".

    Segment lengths are deliberately not covered: "continue for 60 miles"
    is a length, not a distance to something, and reads better whole.
    """
    trip, _truck = make_trip(world)

    for miles in (0.4, 0.3, 0.25, 0.1, 0.05, 0.0):
        spoken = trip._ahead_text(miles)
        assert "0 mile" not in spoken, f"{miles} mi spoke as {spoken!r}"

    assert trip._ahead_text(0.25) == "a quarter mile"
    assert trip._ahead_text(1.0) == "one mile"
    # Far enough out that whole miles are the natural wording again.
    assert trip._ahead_text(5.0) == "5 miles"

    # The lines the owner actually heard it in, end to end.
    from freight_fate.sim.trip_models import TrafficPressure, Zone

    trip.zones = [Zone(0.20, 0.60, 15.0, "facility access road")]
    trip._announced_zone_warnings.clear()
    trip._pending_zone_warning = None
    trip.position_mi = 0.0
    trip._events.clear()
    trip._check_zones()
    zone_said = " ".join(e.message for e in trip._events)
    assert "0 mile" not in zone_said, zone_said

    pressure = TrafficPressure(
        start_mi=0.2,
        end_mi=0.6,
        kind="route_merge",
        direction="right",
        intensity=0.5,
        target_speed_mph=45.0,
        reason="on-ramp",
    )
    assert "0 mile" not in trip._traffic_pressure_message(pressure, 0.2)
