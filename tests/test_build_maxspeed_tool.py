"""Development-time maxspeed builder tests (pure logic; no PBF or network)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_build_interchanges():
    """Import tools/build_interchanges.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "build_interchanges", ROOT / "tools" / "build_interchanges.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bx = _load_build_interchanges()


def _geom() -> list[tuple[float, float, float]]:
    # A 10-mile north-south leg, one vertex per mile.
    return [(40.0 + 0.0145 * i, -86.0, float(i)) for i in range(11)]


def _way_along(mph, ref="I-65", hgv=False, lo=0, hi=10):
    coords = tuple((40.0 + 0.0145 * i, -86.0) for i in range(lo, hi + 1))
    return bx.LocalMaxspeedWay(coords=coords, mph=mph, hgv=hgv, ref=ref)


def _profile(ways, highway="I-65", leg_miles=10.0):
    """Assemble a profile through the grid the runner uses."""
    return bx.assemble_maxspeed(
        bx.build_maxspeed_grid(ways), _geom(), leg_miles, highway)


# --- small helpers ----------------------------------------------------------

def test_state_slug():
    assert bx._state_slug("Indiana") == "indiana"
    assert bx._state_slug("District of Columbia") == "district-of-columbia"
    assert bx._state_slug("  West Virginia ") == "west-virginia"


def test_route_digits():
    assert bx._route_digits("I-65") == "65"
    assert bx._route_digits("I 95") == "95"
    assert bx._route_digits("US 30") == "30"
    assert bx._route_digits("") == ""


def test_leg_states_unions_mileage_and_endpoints():
    data = {"cities": {"A": {"state": "Illinois"}, "B": {"state": "Indiana"}}}
    leg = {"from": "A", "to": "B",
           "corridor": {"state_miles": [{"state": "Illinois", "miles": 5},
                                        {"state": "Indiana", "miles": 5}]}}
    assert bx._leg_states(data, leg) == {"Illinois", "Indiana"}


def test_pbf_for_states_picks_existing_only(tmp_path: Path):
    (tmp_path / "indiana-latest.osm.pbf").write_bytes(b"")
    found = bx._pbf_for_states({"Indiana", "Ohio"}, tmp_path)
    assert [p.name for p in found] == ["indiana-latest.osm.pbf"]


# --- profile assembly -------------------------------------------------------

def test_no_on_corridor_ways_yields_empty_profile():
    far = bx.LocalMaxspeedWay(coords=((10.0, 10.0),), mph=65.0, hgv=False, ref="")
    assert _profile([far]) == []


def test_uniform_limit_collapses_to_one_sample():
    profile = _profile([_way_along(65.0)])
    assert [s["mph"] for s in profile] == [65.0]
    assert profile[0]["at_mi"] == 0.0
    assert profile[0]["source"].startswith("OpenStreetMap maxspeed")


def test_changing_limit_produces_a_step():
    profile = _profile([_way_along(70.0, lo=0, hi=4), _way_along(55.0, lo=6, hi=10)])
    mphs = [s["mph"] for s in profile]
    assert mphs[0] == 70.0 and mphs[-1] == 55.0
    assert any(a["mph"] != b["mph"]
               for a, b in zip(profile, profile[1:], strict=False))


def test_shield_match_beats_a_parallel_frontage_road():
    mainline = _way_along(70.0, ref="I-65")
    frontage = _way_along(45.0, ref="")        # no shield -> not on-shield
    profile = _profile([frontage, mainline])
    assert all(s["mph"] == 70.0 for s in profile)


def test_truck_specific_limit_is_preferred_and_flagged():
    car = _way_along(65.0, ref="I-5", hgv=False)
    truck = _way_along(55.0, ref="I-5", hgv=True)
    profile = _profile([car, truck], highway="I-5")
    assert all(s["mph"] == 55.0 and s["hgv"] for s in profile)
