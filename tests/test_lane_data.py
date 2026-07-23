"""Invariants for the baked lane-count data layer (corridor.lane_segments).

Nothing in the game reads lane_segments yet (it is baked ahead of a mechanic,
like grades and dense speed limits were), so these guard the raw data directly
rather than through the world model, which does not expose the key.
"""

import json
from pathlib import Path

import pytest

import freight_fate.data as ff_data

LEGS_DIR = Path(ff_data.__file__).parent / "world_data" / "us" / "legs"

LANES_MIN, LANES_MAX = 1, 10
ALLOWED_KEYS = {
    "start_mi",
    "end_mi",
    "lanes",
    "lanes_forward",
    "lanes_backward",
    "oneway",
    "source",
}


def _legs_with_lanes():
    """(leg_id, segments) for every leg that carries lane_segments."""
    out = []
    for shard in sorted(LEGS_DIR.glob("*.json")):
        data = json.loads(shard.read_text(encoding="utf-8"))
        for leg in data["legs"]:
            segs = leg.get("corridor", {}).get("lane_segments")
            if segs:
                out.append((f"{leg['from']}:{leg['to']}", segs))
    return out


LANE_LEGS = _legs_with_lanes()


def test_some_legs_have_lane_data():
    """The bake actually ran: a healthy fraction of legs carry lane data."""
    assert len(LANE_LEGS) >= 200, f"only {len(LANE_LEGS)} legs have lane_segments"


def test_lane_segments_are_well_formed():
    for leg_id, segs in LANE_LEGS:
        assert isinstance(segs, list) and segs, leg_id
        prev_end = -1.0
        for s in segs:
            assert set(s) <= ALLOWED_KEYS, f"{leg_id}: unexpected keys {set(s) - ALLOWED_KEYS}"
            start, end = s["start_mi"], s["end_mi"]
            assert 0.0 <= start < end, f"{leg_id}: bad span {start}->{end}"
            # sorted and non-overlapping along the leg
            assert start >= prev_end - 0.05, f"{leg_id}: segment overlap at {start} (prev end {prev_end})"
            prev_end = end
            lanes = s["lanes"]
            assert isinstance(lanes, int) and LANES_MIN <= lanes <= LANES_MAX, f"{leg_id}: lanes={lanes}"
            for k in ("lanes_forward", "lanes_backward"):
                if k in s:
                    v = s[k]
                    assert isinstance(v, int) and LANES_MIN <= v <= LANES_MAX, f"{leg_id}: {k}={v}"
            if "oneway" in s:
                assert s["oneway"] is True, f"{leg_id}: oneway={s['oneway']!r}"


def test_lane_sources_are_curated_not_raw_osm():
    """Source notes credit OSM but never leak a raw tag into stored text."""
    for leg_id, segs in LANE_LEGS:
        for s in segs:
            src = s.get("source", "")
            assert src and "OpenStreetMap" in src, f"{leg_id}: source missing/uncredited"
            # a raw tag dump (lanes=3, highway=motorway) must never be the source
            assert "lanes=" not in src and "highway=" not in src, f"{leg_id}: raw tag in source"


@pytest.mark.parametrize(
    "leg_id, predicate, why",
    [
        # Acceptance spot checks from the brief: metro widens, rural stays 2.
        ("albuquerque_nm_us:gallup_nm_us", lambda segs: any(s["lanes"] >= 3 for s in segs),
         "I-40 through Albuquerque should widen to 3+ lanes"),
        ("winslow_az_us:holbrook_az_us", lambda segs: any(s["lanes"] == 2 for s in segs),
         "rural I-40 Arizona should be 2 lanes"),
    ],
)
def test_acceptance_anchor_lane_counts(leg_id, predicate, why):
    by_id = dict(LANE_LEGS)
    assert leg_id in by_id, f"{leg_id} has no lane data"
    assert predicate(by_id[leg_id]), why
