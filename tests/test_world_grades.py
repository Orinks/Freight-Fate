"""The load-time screen that caps impossible slopes in the baked grade data.

Every grade segment in the world comes from one OpenRouteService elevation
profile over SRTM, and a few hundred of them describe a slope no road of their
class can hold -- elevation noise where the profile crossed a bridge. These
tests pin the ceilings and, more importantly, pin that a plausible steep grade
is left exactly as baked.
"""

from __future__ import annotations

import json

from freight_fate.data.data_resources import read_data_text
from freight_fate.data.grades import (
    CLASS_CEILING_PCT,
    TERRAIN_CEILING_PCT,
    grade_ceiling_pct,
    road_class,
    screen_grade_segments,
)
from freight_fate.data.world_corridor import build_leg_corridor
from freight_fate.data.world_models import GradeSegment


def _seg(pct: float, terrain: str = "mountain", start: float = 10.0, span: float = 0.3):
    return GradeSegment(start, start + span, pct, terrain, "OpenRouteService route elevation.")


def test_road_class_reads_the_highway_designation():
    assert road_class("I-5") == "interstate"
    assert road_class("I-70") == "interstate"
    assert road_class("US-550") == "us"
    assert road_class("CA-299") == "state"
    assert road_class("") == "state"


def test_ceiling_is_the_stricter_of_class_and_terrain():
    # An interstate in the mountains is governed by its class; the same
    # interstate labelled flat is governed by the terrain.
    assert grade_ceiling_pct("I-5", "mountain") == CLASS_CEILING_PCT["interstate"]
    assert grade_ceiling_pct("I-5", "flat") == TERRAIN_CEILING_PCT["flat"]
    assert grade_ceiling_pct("CA-299", "mountain") == CLASS_CEILING_PCT["state"]


def test_the_worst_baked_slope_is_clamped_to_the_interstate_ceiling():
    # +14.42 percent on I-5, the steepest record in the world data. No
    # interstate anywhere is built past 7.
    (screened,) = screen_grade_segments((_seg(14.42),), "I-5")
    assert screened.avg_grade_pct == CLASS_CEILING_PCT["interstate"]


def test_clamping_keeps_the_sign_so_a_descent_stays_a_descent():
    (screened,) = screen_grade_segments((_seg(-14.42),), "I-5")
    assert screened.avg_grade_pct == -CLASS_CEILING_PCT["interstate"]


def test_clamping_leaves_the_span_and_terrain_alone():
    (screened,) = screen_grade_segments((_seg(14.42, start=10.0, span=0.3),), "I-5")
    assert (screened.start_mi, screened.end_mi) == (10.0, 10.3)
    assert screened.terrain == "mountain"


def test_a_flat_labelled_segment_is_capped_below_its_class_ceiling():
    # 8.3 percent over a fifth of a mile on ground the bake itself called
    # flat -- the self-contradiction that proves it is a structure, not road.
    (screened,) = screen_grade_segments((_seg(8.3, terrain="flat", span=0.2),), "I-22")
    assert screened.avg_grade_pct == TERRAIN_CEILING_PCT["flat"]


def test_a_real_mountain_interstate_grade_is_left_exactly_as_baked():
    # The Eisenhower approach on I-70 is about 7 percent and genuinely is
    # that steep. The screen must not touch it.
    original = _seg(6.8)
    assert screen_grade_segments((original,), "I-70") == (original,)


def test_a_steep_us_route_pass_is_left_alone():
    # US-550 over Red Mountain Pass really does climb like this; only the
    # interstate class carries the tight ceiling.
    original = _seg(9.4)
    assert screen_grade_segments((original,), "US-550") == (original,)


def test_an_untouched_segment_keeps_its_original_source_string():
    original = _seg(3.0)
    (screened,) = screen_grade_segments((original,), "I-5")
    assert screened.source == original.source


def test_a_clamped_segment_says_in_its_source_that_the_value_was_derived():
    (screened,) = screen_grade_segments((_seg(14.42),), "I-5")
    assert "derived" in screened.source
    assert "14.42" in screened.source
    assert screened.source.startswith("OpenRouteService route elevation.")


def test_the_baked_i5_leg_loads_with_no_impossible_slope():
    legs = json.loads(read_data_text("world_data/us/legs/CA.json"))["legs"]
    leg = next(lg for lg in legs if lg["from"] == "chico_ca_us" and lg["to"] == "santa_rosa_ca_us")
    raw = leg["corridor"]["grade_segments"]
    assert max(abs(g["avg_grade_pct"]) for g in raw) > 14.0, "fixture no longer has the artifact"

    built = build_leg_corridor(
        leg["corridor"], float(leg["miles"]), leg["from"], leg["to"], "CA", leg["highway"]
    )
    worst = max(abs(s.avg_grade_pct) for s in built["grade_segments"])
    assert worst <= CLASS_CEILING_PCT["interstate"]
