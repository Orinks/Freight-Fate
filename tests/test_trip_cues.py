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


def test_city_events_announce_a_state_line_the_map_does_not_carry(world):
    """The fallback that keeps a state line from passing in silence.

    Where the route has a surveyed boundary, the mapped crossing owns the
    announcement and this line does not repeat it -- that is
    test_city_events_do_not_repeat_mapped_state_crossings. Where it has
    none, this prefix is the only thing that says the state changed, so it
    has to still be here. This test used to assert the prefix on a leg that
    DOES carry a mapped crossing, from the years when the mapped one could
    never reach the driver and the duplicate was the lesser evil.
    """
    import dataclasses

    route = world.route_from_cities(["Chicago", "Cleveland", "Pittsburgh"])
    # The same leg with its surveyed boundary taken away: nothing else will
    # speak the state change, so the city line must carry it. A Leg is
    # frozen, so this is a replacement rather than an edit.
    assert route.legs[0].state_crossings
    route.legs[0] = dataclasses.replace(route.legs[0], state_crossings=())

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


def test_the_gate_zone_never_swallows_the_streets_before_it(world):
    """Owner report, 2026-08-17: "it says it's holding 25 when it's really
    doing more like 14." Root cause found 2026-08-18, and it is arithmetic.

    ``FACILITY_GATE_ZONE_MI`` is 0.5, but the median approach chain is 1.0
    mile and 234 of 1,415 facilities run 0.5 or shorter -- so "the last half
    mile" reached back over the whole approach. ``_active_zone_at`` takes the
    LOWEST limit among overlapping zones, so that blanket 15 overrode every
    25-mph street underneath it while the per-leg zones went on announcing
    25. The truck was pinned at 15 and told it was holding 25.
    """
    from freight_fate.sim.trip_models import FACILITY_GATE_LIMIT_MPH

    trip, _truck = make_trip(world)
    for total, leg_lengths in ((0.54, [0.05, 0.21, 0.05, 0.09, 0.14]), (0.4, [0.2, 0.2])):
        starts, acc = [], 0.0
        for length in leg_lengths:
            starts.append(acc)
            acc += length

        class _Leg:
            def __init__(self, miles):
                self.miles = miles
                self.local_speed_mph = 25.0

        class _Route:
            legs = [_Leg(m) for m in leg_lengths]
            miles = total

        trip.route = _Route()
        trip._leg_starts = starts
        trip._is_facility_approach_route = lambda: True
        zones = trip._facility_speed_zones()

        gate = [z for z in zones if z.limit_mph == FACILITY_GATE_LIMIT_MPH]
        assert gate, "the gate zone vanished"
        # It starts no earlier than the final leg, so it can never reach back
        # over a street the driver is still meant to be doing 25 on.
        assert gate[0].start_mi >= starts[-1] - 1e-9, (
            f"gate zone starts at {gate[0].start_mi} but the last leg starts at {starts[-1]}"
        )
        assert gate[0].start_mi > 0.0, "the gate zone covered the whole approach"

        # And nothing 25 is left fully shadowed by it.
        for zone in zones:
            if zone.limit_mph == 25.0:
                assert zone.start_mi < gate[0].start_mi, "a 25 street sits wholly inside the gate"


def test_debris_speaks_its_kind_and_the_split_keeps_the_old_rate(world):
    """ "Debris in the road" told a blind driver nothing about the dodge --
    a ladder and a mattress are different problems (Brandon, 2026-08-20).
    The named split must sum to the 1.2 weight the one generic entry
    carried, so debris stays exactly as common as it was."""
    from freight_fate.sim.trip_models import HAZARDS

    debris = {
        h.text: h
        for h in HAZARDS
        if h.name
        in ("the ladder", "the lumber", "the mattress", "the boxes", "the tarp", "the debris")
    }
    assert len(debris) == 6, sorted(debris)
    assert all(h.dodgeable for h in debris.values())
    assert abs(sum(h.weight for h in debris.values()) - 1.2) < 1e-9
    # Every named entry resolves to its own noun, so the cleared line says
    # what was cleared.
    names = {h.name for h in debris.values()}
    assert "the ladder" in names and "the mattress" in names


def test_the_animal_brake_call_names_the_animal(world):
    """Same rule as the debris split: 'an animal in the road' says nothing
    about what you are braking for (Brandon, 2026-08-20). The named split
    sums to the 0.7 the generic entry carried, so animals stay exactly as
    common, and every entry keeps animal=True so the dawn-dusk-night
    eligibility window still governs them all."""
    from freight_fate.sim.trip_models import HAZARDS

    animals = {
        h.text: h
        for h in HAZARDS
        if h.name in ("the dog", "the coyote", "the livestock", "the raccoon", "the animal")
    }
    assert len(animals) == 5, sorted(animals)
    assert all(h.animal for h in animals.values())
    assert abs(sum(h.weight for h in animals.values()) - 0.7) < 1e-9


def _horn_host(names, tried=False, seed=0, pos=100.0):

    cleared = []

    class _Trip:
        position_mi = pos

    class _Host:
        _hazard_deadline = 1.0
        _hazard_names = names
        _horn_scare_tried = tried
        trip_seed = seed
        trip = _Trip()

        def _hazard_names_text(self):
            return " and ".join(names)

        def _finish_hazard_clear(self, message):
            cleared.append(message)

    return _Host(), cleared


def test_the_horn_moves_a_movable_animal(world):
    """Shane's ask (2026-08-20): the air horn's one real power. Seeded on
    the hazard, so the same deer makes the same choice every retry; some
    seed in a short scan must clear a dog (70 percent) and the ladder must
    never care how loud you are."""
    from freight_fate.states.driving_updates import DrivingUpdateMixin as DrivingUpdatesMixin

    outcomes = []
    for seed in range(10):
        host, cleared = _horn_host(["the dog"], seed=seed)
        DrivingUpdatesMixin._horn_scare_animals(host)
        outcomes.append(bool(cleared))
        assert host._horn_scare_tried, "an attempt must always spend the one try"
    assert any(outcomes), "no dog moved across ten seeds at 70 percent"

    host, cleared = _horn_host(["the ladder"], seed=0)
    DrivingUpdatesMixin._horn_scare_animals(host)
    assert not cleared
    assert not host._horn_scare_tried, "a ladder must not spend the animal try"


def test_the_horn_gets_one_attempt_per_hazard(world):
    from freight_fate.states.driving_updates import DrivingUpdateMixin as DrivingUpdatesMixin

    host, cleared = _horn_host(["the dog"], tried=True, seed=3)
    DrivingUpdatesMixin._horn_scare_animals(host)
    assert not cleared, "a second blast must not re-roll the animal"


def test_the_welcome_sign_is_deterministic_and_authored(world):
    """The welcome-sign content shipped as data with its speaking left as
    'gameplay-layer follow-on' -- and sat silent until Brandon asked why
    state signs are not read (2026-08-20). Now appended to the crossing
    line (billboard chatter switch governs it); the pick is crc32-seeded
    so the same trip reads the same sign every run -- str hash() is
    process-randomized and must never seed it."""
    import random as _random
    import zlib

    from freight_fate.data.state_welcome import welcome_sign

    sign = welcome_sign("Texas", _random.Random(7 ^ zlib.crc32(b"Texas")))
    assert sign.startswith("Welcome to Texas"), sign
    assert sign == welcome_sign("Texas", _random.Random(7 ^ zlib.crc32(b"Texas")))
    assert welcome_sign("Atlantis", _random.Random(1)) == ""


def test_the_horn_drains_the_air_tanks_to_the_protection_valve(world):
    """Real trucks run the horn off the brake air (Brandon, 2026-08-20) --
    and FMVSS 121 pressure protection means the horn can never take the
    brakes down with it: below the valve's threshold the horn goes silent
    and the draw stops (realism audit, 2026-08-20; the first version let
    you honk to a spring-brake lockout, which a compliant tractor cannot
    do)."""
    from freight_fate.sim.vehicle import TruckState

    t = TruckState()
    before = t.primary_air_psi
    t.horn_on = True
    for _ in range(60 * 60):  # a full minute of leaning on it
        t._consume_brake_air(1 / 60)
    drained = before - t.primary_air_psi
    assert 5.0 <= drained <= 10.0, f"a minute of horn drained {drained:.2f} psi"
    t.horn_on = False
    mid = t.primary_air_psi
    for _ in range(60):
        t._consume_brake_air(1 / 60)
    assert t.primary_air_psi == mid, "released horn must not draw"
    # Honk forever: the valve floors the drain at its threshold.
    t.horn_on = True
    for _ in range(60 * 60 * 30):
        t._consume_brake_air(1 / 60)
    assert t.air_pressure_psi >= t.HORN_PROTECTION_PSI - 1.0, (
        f"the horn drained past the protection valve: {t.air_pressure_psi:.1f}"
    )
    assert not t.horn_available, "below threshold the horn must be dead"


def test_brake_lights_name_the_cause_when_the_road_knows_it(world):
    """Brandon asked WHY the brake lights (2026-08-20). A braking cue inside
    a construction or congestion zone names the cause; outside any
    mile-mapped zone it says nothing about cause -- phantom waves are real
    and inventing a reason would be worse than silence."""
    from freight_fate.sim.traffic_manager import TrafficManager
    from freight_fate.speech_text import brake_lights_cue

    caused = brake_lights_cue("half a mile", "30 miles per hour", "30", "Road work is the cause.")
    assert "Road work is the cause." in caused.normal
    assert "Road work" not in caused.terse, "the cause must not bloat terse mode"
    plain = brake_lights_cue("half a mile", "30 miles per hour", "30")
    assert "cause" not in plain.normal.lower()

    mgr = TrafficManager.__new__(TrafficManager)
    mgr._braking_zones = ((10.0, 14.0, "construction"), (20.0, 25.0, "heavy traffic"))
    assert mgr._braking_reason_at(12.0) == "construction"
    assert mgr._braking_reason_at(22.0) == "heavy traffic"
    assert mgr._braking_reason_at(50.0) == ""


def test_the_status_browse_says_how_much_to_the_next_level(world):
    """xp_to_next_level shipped 2026-08-17 from Brandon's report and ended
    up with zero callers -- the answer existed and nothing spoke it. He
    asked again 2026-08-20 and was exactly right. The driving status browse
    now carries it."""
    import os

    os.environ.setdefault("FREIGHT_FATE_NO_SPEECH", "1")
    from freight_fate.app import App

    app = App()
    try:
        from tests.driving_feature_helpers import start_drive  # type: ignore
    except Exception:
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from driving_feature_helpers import start_drive  # type: ignore
    try:
        driving = start_drive(app)
        lines = driving.status_lines()
        career_lines = [ln for ln in lines if ln.startswith("Career:")]
        assert len(career_lines) == 1, lines
        assert "to level" in career_lines[0] or "top career level" in career_lines[0]
    finally:
        app.shutdown()


def test_abandoning_a_bobtail_costs_nothing(world):
    """No load, no contract, nothing to breach, nothing to fine (Shane,
    2026-08-20). A loaded job still pays the five hundred and the
    reputation; an empty reposition just turns around."""
    from types import SimpleNamespace

    from freight_fate.states.driving_pause_states import AbandonJobConfirmationState

    host = AbandonJobConfirmationState.__new__(AbandonJobConfirmationState)
    host.driving = SimpleNamespace(job=SimpleNamespace(bobtail=True))
    assert host._is_bobtail()
    host.driving = SimpleNamespace(job=SimpleNamespace(bobtail=False))
    assert not host._is_bobtail()
    host.driving = SimpleNamespace(job=None)
    assert not host._is_bobtail()
