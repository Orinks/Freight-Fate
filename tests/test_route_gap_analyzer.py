"""Unit tests for the route-gap analyzer's pure measurement helpers.

The tool itself is report-only and needs a local ORS, so these cover the parts
that decide what lands in the queue: how far an alternate has to stray before
it counts as a different road, which shield it is credited to, and how the
ranking treats a detour versus a real tradeoff.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import analyze_route_gaps as arg  # noqa: E402


def _line(lon_a, lat, lon_b, steps=200):
    """A straight east-west polyline as [[lon, lat], ...]."""
    return [[lon_a + (lon_b - lon_a) * i / steps, lat] for i in range(steps + 1)]


def test_haversine_matches_known_distance():
    # Nashville -> Memphis great circle is ~200 mi (the drive is longer).
    miles = arg.haversine_mi(36.1627, -86.7844, 35.1495, -90.0490)
    assert 190 < miles < 215


def test_densify_closes_long_gaps():
    coarse = [[-90.0, 35.0], [-86.0, 35.0]]
    dense = arg.densify(coarse, max_gap_mi=0.5)
    assert len(dense) > 300
    gaps = [
        arg.haversine_mi(a[1], a[0], b[1], b[0]) for a, b in zip(dense, dense[1:], strict=False)
    ]
    assert max(gaps) <= 0.75


def test_identical_route_does_not_diverge():
    base = arg.PolylineIndex(_line(-90.0, 35.0, -86.0))
    assert arg.divergence(_line(-90.0, 35.0, -86.0), base) == 0.0


def test_parallel_road_far_enough_away_fully_diverges():
    base = arg.PolylineIndex(_line(-90.0, 35.0, -86.0))
    # A degree of latitude is ~69 mi -- well past the 3 mi gate.
    assert arg.divergence(_line(-90.0, 36.0, -86.0), base) == 1.0


def test_ramp_level_wiggle_stays_below_the_gate():
    base = arg.PolylineIndex(_line(-90.0, 35.0, -86.0))
    # ~1.4 mi offset: a different ramp or frontage road, not a new corridor.
    assert arg.divergence(_line(-90.0, 35.02, -86.0), base) < arg.DIVERGENT_AT


def test_shield_miles_reads_names_and_concurrencies():
    steps = [
        {"name": "I 40", "distance": 1609.344 * 100},
        {"name": "Bear Creek Pike, US 412", "distance": 1609.344 * 10},
        {"name": "-", "distance": 1609.344 * 5},
    ]
    miles = arg.shield_miles(steps)
    assert miles["I-40"] == 100
    assert miles["US-412"] == 10
    assert miles["unnamed"] == 5


def test_road_class_follows_the_dominant_shield():
    assert arg.road_class({"I-40": 200.0, "US-70": 10.0}) == "interstate"
    assert arg.road_class({"US-412": 95.0, "I-65": 36.0}) == "us_highway"
    assert arg.road_class({"SR-152": 40.0}) == "state_highway"
    assert arg.road_class({"unnamed": 90.0}) == "unknown"


def test_score_penalizes_an_implausible_detour():
    tight = arg.candidate_score(0.9, "us_highway", 220.0, 200.0, 5.5, 5.0)
    sprawling = arg.candidate_score(0.9, "us_highway", 420.0, 200.0, 9.0, 5.0)
    assert tight > sprawling
    assert sprawling < 0.25


def test_score_rewards_the_shorter_but_slower_tradeoff():
    tradeoff = arg.candidate_score(0.8, "us_highway", 190.0, 200.0, 5.4, 5.0)
    plain = arg.candidate_score(0.8, "us_highway", 210.0, 200.0, 5.4, 5.0)
    assert tradeoff > plain
    assert arg.tradeoff_label(190.0, 200.0, 5.4, 5.0) == "shorter but slower"


def test_summary_line_reads_like_the_brief():
    pair = {
        "from": "nashville_tn_us",
        "to": "memphis_tn_us",
        "highway": "I-40",
        "leg_miles": 210.0,
        "alternates": [
            {
                "divergence": 0.78,
                "miles": 198.0,
                "road_class": "us_highway",
                "shields": [{"shield": "US-70", "miles": 150.0}],
                "tradeoff": "shorter but slower",
            }
        ],
    }
    line = arg.summary_line(pair)
    assert "nashville_tn_us->memphis_tn_us" in line
    assert "US-70 alternate diverges 78%" in line
    assert "us highway" in line
