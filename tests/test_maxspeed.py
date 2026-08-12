"""Baked OSM maxspeed: normalization, the leg step-function, and the runtime
preference of a real posted limit over the highway/region heuristic."""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path

import pytest

from freight_fate.data.world import Leg, SpeedLimitSample
from freight_fate.data.world_models import Route, StateMileage
from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.trip import _leg_speed_limit_at, corridor_speed_limit

ROOT = Path(__file__).resolve().parents[1]


def _load_enrich_routes():
    """Import tools/enrich_routes.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "enrich_routes", ROOT / "tools" / "enrich_routes.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parse_osm_maxspeed = _load_enrich_routes().parse_osm_maxspeed


# --- maxspeed normalization -------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("55 mph", 55.0),
        ("65 mph", 65.0),
        ("55", 55.0),  # bare number assumed mph on the US map
        ("90 km/h", 55.0),  # 55.9 -> nearest 5
        ("100 kmh", 60.0),  # 62.1 -> nearest 5
        ("100 kph", 60.0),
        ("55 mph; 50 mph", 55.0),  # first (general) token wins
        ("60 mph;40 mph @ (wet)", 60.0),
        ("none", None),
        ("signals", None),
        ("variable", None),
        ("", None),
        ("RU:urban", None),  # no digits
        ("5 knots", None),  # nautical, ignored
        (None, None),
    ],
)
def test_parse_osm_maxspeed(raw, expected):
    assert parse_osm_maxspeed(raw) == expected


def test_parse_osm_maxspeed_default_kmh_for_non_us_data():
    # A bare number is km/h under OSM's default convention when asked.
    assert parse_osm_maxspeed("90", default_kmh=True) == 55.0


def test_parse_osm_maxspeed_clamps_to_truck_range():
    assert parse_osm_maxspeed("200 mph") == 85.0


# --- leg step function ------------------------------------------------------


def _leg(speed_limits=()):
    return Leg("A", "B", 100.0, "I-95", "flat", (), speed_limits=speed_limits)


def test_unbaked_leg_returns_none():
    assert _leg_speed_limit_at(_leg(), 50.0) is None


def test_single_sample_applies_everywhere():
    leg = _leg((SpeedLimitSample(0.0, 65.0),))
    assert _leg_speed_limit_at(leg, 0.0) == 65.0
    assert _leg_speed_limit_at(leg, 99.0) == 65.0


def test_step_function_picks_last_sample_at_or_before_offset():
    leg = _leg(
        (
            SpeedLimitSample(0.0, 65.0),
            SpeedLimitSample(40.0, 70.0),
            SpeedLimitSample(80.0, 55.0),
        )
    )
    assert _leg_speed_limit_at(leg, 10.0) == 65.0
    assert _leg_speed_limit_at(leg, 40.0) == 70.0
    assert _leg_speed_limit_at(leg, 79.9) == 70.0
    assert _leg_speed_limit_at(leg, 90.0) == 55.0


def test_offset_before_first_sample_uses_first():
    leg = _leg((SpeedLimitSample(10.0, 60.0), SpeedLimitSample(50.0, 70.0)))
    assert _leg_speed_limit_at(leg, 0.0) == 60.0


# --- coverage-gap markers ---------------------------------------------------


def test_gap_marker_answers_none_instead_of_holding_the_last_posting():
    # The NY-12 lesson: a village 30 whose tagging ends must not rule the
    # untagged miles that follow -- inside the gap the caller's heuristic
    # answers.
    leg = _leg(
        (
            SpeedLimitSample(0.0, 30.0),
            SpeedLimitSample(1.2, None),
            SpeedLimitSample(40.0, 55.0),
        )
    )
    assert _leg_speed_limit_at(leg, 0.5) == 30.0
    assert _leg_speed_limit_at(leg, 20.0) is None
    assert _leg_speed_limit_at(leg, 45.0) == 55.0


def test_parser_accepts_gap_markers_and_still_rejects_bad_numbers():
    from freight_fate.data.world_parsing import _parse_speed_limit

    sample = _parse_speed_limit({"at_mi": 5.0, "mph": None}, 100.0, "A", "B")
    assert sample.mph is None
    with pytest.raises(ValueError):
        _parse_speed_limit({"at_mi": 5.0, "mph": 150.0}, 100.0, "A", "B")


# --- the dwell filter -------------------------------------------------------


def _parsed(*pairs, places=()):
    from freight_fate.data.world_parsing import _parse_speed_limits

    raw = [{"at_mi": at, "mph": mph} for at, mph in pairs]
    return _parse_speed_limits(raw, 100.0, "A", "B", places=places)


def test_a_posting_too_short_to_be_a_sign_is_absorbed():
    """OSM segmentation, not signage.

    Reported 2026-08-11: "the speeds keep reducing and speeding up for random
    reasons that aren't apparent". A tenth of the baked profile is postings
    the truck is inside for a second or two -- an 80 that drops to 45 and back
    over four tenths of a mile is a way tag boundary, and no agency signs one.
    """
    kept = _parsed((0.0, 80.0), (20.0, 45.0), (20.4, 80.0), (60.0, 65.0))
    assert [(s.at_mi, s.mph) for s in kept] == [(0.0, 80.0), (60.0, 65.0)]


def test_a_long_zone_survives_the_dwell_filter():
    """Anything that holds for more than the dwell is a posting, full stop."""
    kept = _parsed((0.0, 55.0), (20.0, 30.0), (22.0, 55.0))
    assert [(s.at_mi, s.mph) for s in kept] == [(0.0, 55.0), (20.0, 30.0), (22.0, 55.0)]


def test_a_short_posting_a_village_explains_is_kept():
    """The rim-town case: Strawberry's 35 runs seven tenths of a mile, which
    is what a village main street really is. Length alone would delete the
    signs along with the noise, so a place on the road is what saves it."""
    noise = _parsed((0.0, 55.0), (20.0, 30.0), (20.6, 55.0))
    assert [(s.at_mi, s.mph) for s in noise] == [(0.0, 55.0)]
    signed = _parsed((0.0, 55.0), (20.0, 30.0), (20.6, 55.0), places=(20.1,))
    assert [(s.at_mi, s.mph) for s in signed] == [(0.0, 55.0), (20.0, 30.0), (20.6, 55.0)]


def test_the_dwell_is_real_seconds_and_not_a_distance():
    """The same six tenths of a mile is two different events.

    Reported again 2026-08-12, after the mile-based bar shipped: "the speeds
    just increase and decrease in seconds". A bar written in miles cannot
    answer that, because a mile at 70 goes by in under three real seconds and
    a mile at 30 takes over ten. Sized in seconds, the highway trim goes and
    the town street stays, with no exception needed for either.
    """
    highway = _parsed((0.0, 70.0), (20.0, 65.0), (21.2, 70.0))
    assert [(s.at_mi, s.mph) for s in highway] == [(0.0, 70.0)]
    town = _parsed((0.0, 45.0), (20.0, 30.0), (21.2, 45.0))
    assert [(s.at_mi, s.mph) for s in town] == [(0.0, 45.0), (20.0, 30.0), (21.2, 45.0)]


def test_a_village_does_not_excuse_a_highway_trim():
    """The pass a place buys is for a town speed, not for any drop at all.

    An 80 shaving to 75 for a quarter mile is a way boundary wherever it sits,
    and I-44 west of Oklahoma City had one beside a village: the old free pass
    kept it, and the player heard the limit drop and come back inside half a
    second. Nothing a village posts is 75.
    """
    trim = _parsed((0.0, 80.0), (20.0, 75.0), (20.25, 80.0), places=(20.1,))
    assert [(s.at_mi, s.mph) for s in trim] == [(0.0, 80.0)]


def test_even_a_town_zone_has_to_last_longer_than_a_blink():
    """A place lowers the bar; it does not remove it. A tenth of a mile of 25
    is still a tag boundary, village or no village."""
    blink = _parsed((0.0, 55.0), (20.0, 25.0), (20.1, 55.0), places=(20.05,))
    assert [(s.at_mi, s.mph) for s in blink] == [(0.0, 55.0)]


def test_the_first_posting_is_never_absorbed():
    """There is nothing behind it to inherit from."""
    kept = _parsed((0.0, 30.0), (0.2, 55.0), (80.0, 65.0))
    assert kept[0].at_mi == 0.0
    assert kept[0].mph == 30.0


def test_a_chain_of_short_postings_collapses_to_where_the_road_settles():
    """Stepping 70-65-60-55 over six tenths is one way boundary read four
    times. Only the value the road actually settles at survives, and it keeps
    its own start mile -- the 55 holds for the next twenty-nine miles, so it
    is a posting even though the steps that led to it were not."""
    kept = _parsed((0.0, 70.0), (10.0, 65.0), (10.3, 60.0), (10.6, 55.0), (40.0, 70.0))
    assert [(s.at_mi, s.mph) for s in kept] == [(0.0, 70.0), (10.6, 55.0), (40.0, 70.0)]


def test_a_short_coverage_gap_holds_the_posting_rather_than_flickering():
    """A gap marker exists to stop a stale town limit ruling untagged MILES.
    Half a mile of missing tagging is not that; flipping to the heuristic and
    back inside a second is the flicker itself."""
    kept = _parsed((0.0, 55.0), (30.0, None), (30.5, 55.0), (70.0, 65.0))
    assert [(s.at_mi, s.mph) for s in kept] == [(0.0, 55.0), (70.0, 65.0)]
    long_gap = _parsed((0.0, 55.0), (30.0, None), (60.0, 55.0))
    assert [(s.at_mi, s.mph) for s in long_gap] == [(0.0, 55.0), (30.0, None), (60.0, 55.0)]


def test_the_dwell_pacing_constants_match_the_sim():
    """The data layer never imports the sim, so it carries its own copy of the
    pacing it sizes the dwell against. Pin them, or a pacing change quietly
    stops meaning what the filter thinks it means."""
    from freight_fate.data.world_constants import (
        LIMIT_DWELL_FULL_COMPRESSION_MPH,
        LIMIT_DWELL_LOW_SPEED_SCALE,
        LIMIT_DWELL_REFERENCE_SCALE,
    )
    from freight_fate.settings import TIME_SCALES
    from freight_fate.sim.trip_models import FULL_COMPRESSION_MPH, LOW_SPEED_TIME_SCALE

    assert LIMIT_DWELL_LOW_SPEED_SCALE == LOW_SPEED_TIME_SCALE
    assert LIMIT_DWELL_FULL_COMPRESSION_MPH == FULL_COMPRESSION_MPH
    # Sized on the standard pace, the middle of the three the player can pick.
    assert sorted(TIME_SCALES)[1] == LIMIT_DWELL_REFERENCE_SCALE


def _posting_real_seconds(miles: float, mph: float | None) -> float:
    """How long the truck is inside a posting, in real seconds at standard pace."""
    from freight_fate.data.world_constants import (
        LIMIT_DWELL_FALLBACK_MPH,
        LIMIT_DWELL_FULL_COMPRESSION_MPH,
        LIMIT_DWELL_LOW_SPEED_SCALE,
        LIMIT_DWELL_REFERENCE_SCALE,
    )

    speed = max(mph or LIMIT_DWELL_FALLBACK_MPH, 5.0)
    ramp = min(1.0, speed / LIMIT_DWELL_FULL_COMPRESSION_MPH)
    scale = (
        LIMIT_DWELL_LOW_SPEED_SCALE
        + (LIMIT_DWELL_REFERENCE_SCALE - LIMIT_DWELL_LOW_SPEED_SCALE) * ramp
    )
    return (miles / speed * 3600.0) / scale


@pytest.mark.timeout(300)
def test_no_leg_in_the_world_flickers_its_posted_limit(world):
    """The whole point, checked on the shipped map rather than on fixtures.

    Every posting the player can meet lasts long enough to be a sign, and the
    only ones that last less than the full dwell are drops to a town speed
    beside a village the game names out loud -- so there is always something
    on the road to explain what they heard.
    """
    from freight_fate.data.world_constants import (
        LIMIT_DWELL_REAL_S,
        LIMIT_EXPLAINING_CATEGORIES,
        LIMIT_PLACE_DWELL_REAL_S,
        LIMIT_PLACE_NEAR_MI,
        LIMIT_PLACE_TOWN_MPH,
    )

    for leg in world.legs:
        places = tuple(
            lm.at_mi for lm in leg.landmarks if lm.category in LIMIT_EXPLAINING_CATEGORIES
        )
        samples = leg.speed_limits
        for i in range(1, len(samples)):
            sample = samples[i]
            end = samples[i + 1].at_mi if i + 1 < len(samples) else leg.miles
            seconds = _posting_real_seconds(end - sample.at_mi, sample.mph)
            if seconds >= LIMIT_DWELL_REAL_S:
                continue
            where = f"{leg.a} to {leg.b} at mile {sample.at_mi}"
            assert seconds >= LIMIT_PLACE_DWELL_REAL_S, f"{where} lasts {seconds:.2f}s"
            assert sample.mph is not None and sample.mph <= LIMIT_PLACE_TOWN_MPH, (
                f"{where} is a {sample.mph} posting held for only {seconds:.2f}s"
            )
            assert any(abs(sample.at_mi - at) <= LIMIT_PLACE_NEAR_MI for at in places), (
                f"{where} lasts {seconds:.2f}s with no place to explain it"
            )


def _load_repair():
    spec = importlib.util.spec_from_file_location(
        "repair_interstate_anchor_limits", ROOT / "tools" / "repair_interstate_anchor_limits.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.repair


def test_anchor_repair_keeps_gap_markers_and_drops_street_pollution():
    repair = _load_repair()
    data = {
        "legs": [
            {
                "from": "a",
                "to": "b",
                "highway": "I-40",
                "miles": 100.0,
                "corridor": {
                    "speed_limits": [
                        {"at_mi": 0.0, "mph": 40.0},  # city-street pollution
                        {"at_mi": 3.0, "mph": 70.0},
                        {"at_mi": 60.0, "mph": None},  # gap marker stays
                    ]
                },
            }
        ]
    }
    repaired = repair(data)
    assert len(repaired) == 1
    kept = data["legs"][0]["corridor"]["speed_limits"]
    assert kept == [{"at_mi": 3.0, "mph": 70.0}, {"at_mi": 60.0, "mph": None}]


def test_anchor_repair_trusts_a_surface_anchor_bounded_by_a_gap():
    # A town 35 at mile 0 that the sweep marked as ending 1 mile in never
    # owned the corridor -- the runtime already reverts inside the gap, so
    # the sample is honest and must survive the surface-anchor rule.
    repair = _load_repair()
    data = {
        "legs": [
            {
                "from": "a",
                "to": "b",
                "highway": "US-60",
                "miles": 80.0,
                "corridor": {
                    "speed_limits": [
                        {"at_mi": 0.0, "mph": 35.0},
                        {"at_mi": 1.0, "mph": None},
                        {"at_mi": 10.0, "mph": 65.0},
                    ]
                },
            }
        ]
    }
    assert repair(data) == []
    assert len(data["legs"][0]["corridor"]["speed_limits"]) == 3


# --- runtime preference and fallback ---------------------------------------


def _open_road_mile(trip):
    """A mile out on the open road, away from the urban-reduction radius."""
    return trip.total_miles / 2.0


def test_runtime_prefers_baked_maxspeed_over_heuristic(world):
    route = world.route_options("Chicago", "St. Louis")[0]
    heuristic = corridor_speed_limit(route.legs[0].highway, "heartland")
    baked = heuristic + 5.0  # a value the heuristic would never produce here
    # Chicago-St. Louis may route through intermediate cities, so bake the value
    # onto every leg -- the sampled open-road mile can land on any of them.
    route.legs[:] = [
        dataclasses.replace(leg, speed_limits=(SpeedLimitSample(0.0, baked),)) for leg in route.legs
    ]
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    assert trip._corridor_limit_at(_open_road_mile(trip)) == baked


def test_runtime_caps_general_baked_limit_to_state_truck_limit():
    leg = Leg(
        "A",
        "B",
        100.0,
        "I-5",
        "flat",
        (),
        state_miles=(StateMileage("California", 100.0),),
        speed_limits=(SpeedLimitSample(0.0, 65.0),),
    )
    trip = Trip(Route(["A", "B"], [leg]), TruckState(), WeatherSystem("california", seed=1), seed=2)
    assert trip._corridor_limit_at(50.0) == 55.0


def test_runtime_keeps_truck_specific_baked_limit():
    leg = Leg(
        "A",
        "B",
        100.0,
        "I-5",
        "flat",
        (),
        state_miles=(StateMileage("California", 100.0),),
        speed_limits=(SpeedLimitSample(0.0, 50.0, hgv=True),),
    )
    trip = Trip(Route(["A", "B"], [leg]), TruckState(), WeatherSystem("california", seed=1), seed=2)
    assert trip._corridor_limit_at(50.0) == 50.0


def test_runtime_caps_oregon_and_arizona_truck_limits():
    # Updated by the 2026-07-19 statute audit. Oregon's default is 55 (ORS
    # 811.111(1)(b)), not the 65 the old aggregator table carried, and Arizona
    # (A.R.S. 28-709, 65) was missing entirely while ADOT posts 75 -- the
    # worst failure mode, since the map served the car number.
    for state, highway, baked, expected in (
        ("Oregon", "I-5", 65.0, 55.0),
        ("Arizona", "I-40", 75.0, 65.0),
    ):
        leg = Leg(
            "A",
            "B",
            100.0,
            highway,
            "flat",
            (),
            state_miles=(StateMileage(state, 100.0),),
            speed_limits=(SpeedLimitSample(0.0, baked),),
        )
        trip = Trip(
            Route(["A", "B"], [leg]),
            TruckState(),
            WeatherSystem("pacific_northwest", seed=1),
            seed=2,
        )
        assert trip._corridor_limit_at(50.0) == expected


def test_idaho_nevada_north_dakota_no_longer_capped():
    """The audit removed three entries: Idaho repealed its split (49-654 as
    amended by H664, effective 2026-07-01) and Nevada and North Dakota never
    had one -- their numbers had been lifted from an aggregator's *general*
    limit column, inventing caps that bind nobody in law."""
    for state, baked in (("Idaho", 75.0), ("Nevada", 80.0), ("North Dakota", 80.0)):
        leg = Leg(
            "A",
            "B",
            100.0,
            "I-84",
            "flat",
            (),
            state_miles=(StateMileage(state, 100.0),),
            speed_limits=(SpeedLimitSample(0.0, baked),),
        )
        trip = Trip(
            Route(["A", "B"], [leg]),
            TruckState(),
            WeatherSystem("mountain_west", seed=1),
            seed=2,
        )
        assert trip._corridor_limit_at(50.0) == baked


def test_montana_split_is_scoped_to_road_class():
    """MCA 61-8-312 is 70 on interstates and 65 on all other public highways.
    A flat number cannot say that, which is why the table is keyed by class."""
    for highway, expected in (("I-90", 70.0), ("US-2", 65.0)):
        leg = Leg(
            "A",
            "B",
            100.0,
            highway,
            "flat",
            (),
            state_miles=(StateMileage("Montana", 100.0),),
            speed_limits=(SpeedLimitSample(0.0, 80.0),),
        )
        trip = Trip(
            Route(["A", "B"], [leg]),
            TruckState(),
            WeatherSystem("mountain_west", seed=1),
            seed=2,
        )
        assert trip._corridor_limit_at(50.0) == expected


def test_hgv_tag_is_trusted_only_as_far_as_the_statute_allows():
    """An explicit maxspeed:hgv outranks the statewide default -- that is how
    Oregon's eastern corridors keep their real 65 while I-5 stays 55 -- but it
    can never license a speed the statute forbids. Real case: I-5 carries a
    60 mph hgv tag eleven miles south of the Oregon line, inside California,
    where CVC 22406 says 55."""

    def _trip(state, highway, mph):
        leg = Leg(
            "A",
            "B",
            100.0,
            highway,
            "flat",
            (),
            state_miles=(StateMileage(state, 100.0),),
            speed_limits=(SpeedLimitSample(0.0, mph, hgv=True),),
        )
        return Trip(
            Route(["A", "B"], [leg]),
            TruckState(),
            WeatherSystem("pacific_northwest", seed=1),
            seed=2,
        )

    # Oregon declares a corridor maximum of 65, so a tagged 65 survives.
    assert _trip("Oregon", "I-84", 65.0)._corridor_limit_at(50.0) == 65.0
    # ...but not beyond it.
    assert _trip("Oregon", "I-84", 75.0)._corridor_limit_at(50.0) == 65.0
    # California permits no corridor exception: the stray tag is clamped.
    assert _trip("California", "I-5", 60.0)._corridor_limit_at(50.0) == 55.0
    # A class-scoped split must not let a tag borrow the interstate number
    # for a back highway (Montana: 70 interstate, 65 elsewhere).
    assert _trip("Montana", "US-2", 70.0)._corridor_limit_at(50.0) == 65.0


def test_runtime_reads_baked_profile_in_reverse_direction():
    leg = Leg(
        "A",
        "B",
        100.0,
        "I-65",
        "flat",
        (),
        state_miles=(StateMileage("Indiana", 100.0),),
        speed_limits=(
            SpeedLimitSample(0.0, 55.0),
            SpeedLimitSample(80.0, 70.0),
        ),
    )
    trip = Trip(
        Route(["B", "A"], [leg]), TruckState(), WeatherSystem("great_lakes", seed=1), seed=2
    )
    assert trip._corridor_limit_at(10.0) == 65.0
    assert trip._corridor_limit_at(90.0) == 55.0


def test_runtime_falls_back_to_heuristic_without_a_profile(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    route.legs[0] = dataclasses.replace(route.legs[0], speed_limits=())
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    mile = _open_road_mile(trip)
    leg_i, _ = trip._leg_at_mile(mile)
    expected = corridor_speed_limit(route.legs[leg_i].highway, trip._region_at(mile))
    assert trip._corridor_limit_at(mile) == expected


def test_baked_limit_wins_near_city(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    route.legs[0] = dataclasses.replace(route.legs[0], speed_limits=(SpeedLimitSample(0.0, 75.0),))
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    # Real posted data is authoritative; the city cap is only a fallback when
    # the route lacks baked speed samples.
    assert trip._corridor_limit_at(0.0) == 75.0


def _split_limit_trip(state: str, mph: float, hgv: bool, highway: str = "I-80") -> Trip:
    leg = Leg(
        "A",
        "B",
        100.0,
        highway,
        "flat",
        (),
        state_miles=(StateMileage(state, 100.0),),
        speed_limits=(SpeedLimitSample(0.0, mph, hgv=hgv),),
    )
    return Trip(Route(["A", "B"], [leg]), TruckState(), WeatherSystem("california", seed=1), seed=2)


def test_split_limit_reported_whether_the_cap_or_the_tag_produced_it():
    """A California 55 arrives two ways -- an explicit maxspeed:hgv (US-395)
    or the statutory cap pulling a 65 car posting down (I-80) -- and the
    driver must not be able to tell them apart. Keying off the cap alone
    stayed silent on the tagged roads, so the same 55 explained itself on one
    mile and not the next (player report, 2026-07-19)."""
    tagged = _split_limit_trip("California", 55.0, hgv=True, highway="US-395")
    capped = _split_limit_trip("California", 65.0, hgv=False)
    assert tagged.speed_limit_at(50.0)[0] == capped.speed_limit_at(50.0)[0] == 55.0
    assert tagged.truck_limit_at(50.0) == (True, "California")
    assert capped.truck_limit_at(50.0) == (True, "California")


def test_plain_posting_is_not_reported_as_a_truck_limit():
    # A state with no statutory split posts one number for everyone, so
    # nothing truck-specific should be claimed. Both examples were rechecked
    # by the 2026-07-19 audit: Nevada's old 75 entry was an invented cap, and
    # Arizona -- used here originally -- turned out to HAVE a split, so it is
    # no longer a valid example of one without.
    assert _split_limit_trip("Nevada", 80.0, hgv=False).truck_limit_at(50.0) == (False, None)
    assert _split_limit_trip("Texas", 75.0, hgv=False).truck_limit_at(50.0) == (False, None)


def test_zone_owns_the_reason_over_a_split_limit():
    """Inside construction the cone is why the number dropped, not the state
    line; crediting California there would explain the wrong thing."""
    trip = _split_limit_trip("California", 65.0, hgv=False)
    zone = trip.zones[0] if trip.zones else None
    if zone is None:
        pytest.skip("no zone generated for this seed")
    assert trip.truck_limit_at((zone.start_mi + zone.end_mi) / 2.0) == (False, None)


def test_local_truck_posting_is_a_truck_limit_without_crediting_the_state():
    # A truck-tagged posting in a state with no statutory split is still a
    # truck limit, but no state law explains it, so the callout must not
    # attribute one. (Was Arizona; the audit found Arizona does have a split.)
    assert _split_limit_trip("Texas", 45.0, hgv=True).truck_limit_at(50.0) == (True, None)
