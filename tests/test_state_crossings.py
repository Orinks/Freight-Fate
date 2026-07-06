"""State-line crossing sanity: no phantom river-border zig-zags.

I-84 hugs the Oregon bank of the Columbia (the OR/WA line) for ~100 miles
without ever crossing it, but vertex-by-vertex point-in-polygon sampling against
a simplified boundary used to fabricate a flurry of OR<->WA crossings the driver
never makes. These tests pin the dwell filter that removes that noise and assert
the shipped world data stays clean.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from freight_fate.data import get_world

ROOT = Path(__file__).resolve().parents[1]


def _load_enrich_routes():
    """Import tools/enrich_routes.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "enrich_routes", ROOT / "tools" / "enrich_routes.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _seq(states_at):
    return [{"state": s, "at_mi": mi} for s, mi in states_at]


def test_short_round_trip_excursion_is_collapsed():
    coalesce = _load_enrich_routes().coalesce_short_states
    # OR -> WA(5mi) -> OR: a river-border flicker that should vanish.
    out = coalesce(_seq([("Oregon", 0.0), ("Washington", 70.0), ("Oregon", 75.0)]), leg_miles=400.0)
    assert [item["state"] for item in out] == ["Oregon"]


def test_genuine_pass_through_is_preserved():
    coalesce = _load_enrich_routes().coalesce_short_states
    # OH -> WV(short) -> PA is a real panhandle pass-through, not a round trip.
    out = coalesce(
        _seq([("Ohio", 0.0), ("West Virginia", 60.0), ("Pennsylvania", 64.0)]), leg_miles=120.0
    )
    assert [item["state"] for item in out] == ["Ohio", "West Virginia", "Pennsylvania"]


def test_long_round_trip_excursion_survives_for_review():
    coalesce = _load_enrich_routes().coalesce_short_states
    # A round trip larger than the fraction gate is left for a human to look at.
    out = coalesce(
        _seq([("Oregon", 0.0), ("Washington", 40.0), ("Oregon", 100.0)]), leg_miles=200.0
    )
    assert [item["state"] for item in out] == ["Oregon", "Washington", "Oregon"]


def test_endpoint_states_are_never_dropped():
    coalesce = _load_enrich_routes().coalesce_short_states
    # Even a tiny opening segment is an authoritative endpoint and must stay.
    out = coalesce(_seq([("Washington", 0.0), ("Oregon", 2.0)]), leg_miles=300.0)
    assert [item["state"] for item in out] == ["Washington", "Oregon"]


def test_world_has_no_phantom_state_round_trips():
    """No leg should enter a state and immediately return to where it came."""
    world = get_world()
    offenders = []
    for leg in world.legs:
        states = [world.cities[leg.a].state] + [c.state for c in leg.state_crossings]
        for first, _mid, third in zip(states, states[1:], states[2:], strict=False):
            if first == third:
                offenders.append((leg.a, leg.b, leg.highway, states))
    assert offenders == [], f"phantom round-trip crossings remain: {offenders}"


def test_i84_to_portland_never_enters_washington():
    """I-84 runs on the Oregon bank of the Columbia; it never crosses to WA."""
    world = get_world()
    checked = 0
    for leg in world.legs:
        if leg.highway != "I-84" or "portland_or_us" not in (leg.a, leg.b):
            continue
        checked += 1
        # ``c.state`` is the state you arrive in; on I-84 by Portland you never
        # end up in Washington (the from_state of a WA->OR leg is fine).
        arrived = {c.state for c in leg.state_crossings}
        assert "Washington" not in arrived, (
            f"{leg.a} -> {leg.b} on I-84 wrongly crosses into Washington: "
            f"{[c.place for c in leg.state_crossings]}"
        )
    assert checked, "expected at least one I-84 leg touching Portland"
