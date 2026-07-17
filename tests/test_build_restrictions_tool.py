"""Development-time restriction builder tests (pure logic; no PBF or network)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_build_interchanges():
    """Import tools/build_interchanges.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "build_interchanges", ROOT / "tools" / "build_interchanges.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bx = _load_build_interchanges()


def _geom() -> list[tuple[float, float, float]]:
    # A 10-mile north-south leg, one vertex per mile.
    return [(40.0 + 0.0145 * i, -86.0, float(i)) for i in range(11)]


def _way_along(kind, value, ref="I-65", lo=4, hi=6):
    """A restriction way running along the leg between miles lo and hi."""
    coords = tuple((40.0 + 0.0145 * i, -86.0) for i in range(lo, hi + 1))
    return bx.LocalRestrictionWay(coords=coords, kind=kind, value=value, ref=ref)


def _way_across(kind, value, at=5, ref=""):
    """A restriction way crossing the leg east-west right at mile ``at``."""
    lat = 40.0 + 0.0145 * at
    coords = ((lat, -86.003), (lat, -86.0), (lat, -85.997))
    return bx.LocalRestrictionWay(coords=coords, kind=kind, value=value, ref=ref)


def _assemble(ways, highway="I-65", leg_miles=10.0):
    return bx.assemble_restrictions(ways, _geom(), leg_miles, highway)


# --- OSM value parsing ------------------------------------------------------


def test_parse_maxheight_meters_default_unit():
    assert abs(bx.parse_osm_maxheight_ft("4.1") - 13.45) < 0.01
    assert abs(bx.parse_osm_maxheight_ft("4.1 m") - 13.45) < 0.01


def test_parse_maxheight_feet_and_inches():
    assert bx.parse_osm_maxheight_ft("13'6\"") == 13.5
    assert bx.parse_osm_maxheight_ft("14'") == 14.0
    assert bx.parse_osm_maxheight_ft("13.5 ft") == 13.5


def test_parse_maxheight_untagged_values_rejected():
    for raw in ("", None, "default", "none", "unsigned", "below_default", "physical"):
        assert bx.parse_osm_maxheight_ft(raw) is None


def test_parse_maxweight_tonnes_default_unit():
    # 30 metric tonnes is about 33.1 short tons.
    assert abs(bx.parse_osm_maxweight_tons("30") - 33.07) < 0.01
    assert abs(bx.parse_osm_maxweight_tons("30 t") - 33.07) < 0.01


def test_parse_maxweight_explicit_units():
    assert bx.parse_osm_maxweight_tons("25 st") == 25.0
    assert bx.parse_osm_maxweight_tons("30000 lbs") == 15.0
    assert abs(bx.parse_osm_maxweight_tons("20000 kg") - 22.05) < 0.01


def test_parse_maxweight_untagged_values_rejected():
    for raw in ("", None, "none", "default", "unknown"):
        assert bx.parse_osm_maxweight_tons(raw) is None


def test_way_restrictions_apply_bake_thresholds():
    # 16ft+ clearances and 40+ short-ton limits are unposted noise.
    assert bx._way_restrictions({"maxheight": "16.5 ft"}) == []
    assert bx._way_restrictions({"maxweight": "40 st"}) == []
    assert bx._way_restrictions({"maxheight": "2 ft"}) == []  # data error, not a road
    both = bx._way_restrictions({"maxheight": "13'6\"", "maxweight": "30 st"})
    assert ("low_clearance", 13.5) in both
    assert ("weight_limit", 30.0) in both


# --- snapping and assembly --------------------------------------------------


def test_aligned_on_shield_way_bakes():
    profile = _assemble([_way_along("low_clearance", 13.5)])
    assert len(profile) == 1
    record = profile[0]
    assert record["kind"] == "low_clearance"
    assert record["feet"] == 13.5
    # Midpoint of the 4..6-mile way is the advisory point.
    assert 4.5 <= record["at_mi"] <= 5.5
    assert "OpenStreetMap" in record["source"]


def test_crossing_way_rejected_by_bearing_gate():
    # A restricted surface street crossing over the corridor must not bake,
    # even though its nodes sit right on the route line.
    assert _assemble([_way_across("low_clearance", 12.0)]) == []


def test_refless_way_needs_tight_snap():
    # Same alignment but no route ref: allowed only inside the tighter corridor.
    on_line = _way_along("weight_limit", 15.0, ref="")
    assert len(_assemble([on_line])) == 1
    offset = bx.LocalRestrictionWay(
        # About 90m west of the line: inside the on-shield corridor but outside
        # the refless one.
        coords=tuple((40.0 + 0.0145 * i, -86.0011) for i in range(4, 7)),
        kind="weight_limit",
        value=15.0,
        ref="",
    )
    assert _assemble([offset]) == []


def test_duplicate_carriageway_tags_collapse_to_most_restrictive():
    # Twin carriageways under the same bridge: two ways ~50m apart laterally,
    # tagged with slightly different clearances. One advisory, lowest value.
    eastbound = _way_along("low_clearance", 14.0, lo=4, hi=6)
    westbound = bx.LocalRestrictionWay(
        coords=tuple((40.0 + 0.0145 * i, -86.0005) for i in range(4, 7)),
        kind="low_clearance",
        value=13.5,
        ref="I-65",
    )
    profile = _assemble([eastbound, westbound])
    assert len(profile) == 1
    assert profile[0]["feet"] == 13.5


def test_distinct_restrictions_keep_separate_advisories():
    ways = [
        _way_along("low_clearance", 13.5, lo=1, hi=2),
        _way_along("weight_limit", 30.0, lo=8, hi=9),
    ]
    profile = _assemble(ways)
    assert [record["kind"] for record in profile] == ["low_clearance", "weight_limit"]


def test_axis_diff_ignores_travel_direction():
    assert bx._axis_diff_deg(10.0, 190.0) == 0.0
    assert bx._axis_diff_deg(0.0, 90.0) == 90.0
