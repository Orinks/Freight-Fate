"""Node-picker parsing and ranking (no network)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_pick_nodes():
    spec = importlib.util.spec_from_file_location(
        "pick_nodes", ROOT / "tools" / "pick_nodes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pick_nodes = _load_pick_nodes()


def test_parse_admin1_maps_us_states_only():
    text = "US.CA\tCalifornia\tCalifornia\t5332921\nCA.01\tAlberta\tAlberta\t1\nUS.NY\tNew York\tNew York\t5"
    mapping = pick_nodes.parse_admin1(text)
    assert mapping["CA"] == "California"
    assert mapping["NY"] == "New York"
    assert "01" not in mapping  # non-US rows are dropped


def test_parse_geonames_normalizes_us_cities_only():
    admin1 = {"TX": "Texas", "ON": "Ontario"}
    us = "1\tAustin\tAustin\t\t30.27\t-97.74\tP\tPPLA\tUS\t\tTX\t\t\t\t961855\t0\t149\tTZ\t2024"
    ca = "2\tToronto\tToronto\t\t43.7\t-79.4\tP\tPPL\tCA\t\tON\t\t\t\t2731571\t0\t76\tTZ\t2024"
    rows = pick_nodes.parse_geonames(us + "\n" + ca, admin1)
    assert len(rows) == 1
    assert rows[0]["name"] == "Austin"
    assert rows[0]["state"] == "Texas"
    assert rows[0]["population"] == 961855
    assert rows[0]["lat"] == 30.27


def test_parse_geonames_drops_non_contiguous_states():
    admin1 = {"TX": "Texas", "HI": "Hawaii", "PR": "Puerto Rico"}
    rows_txt = "\n".join([
        "1\tAustin\tAustin\t\t30.27\t-97.74\tP\tPPLA\tUS\t\tTX\t\t\t\t961855\t0\t1\tTZ\t2024",
        "2\tHonolulu\tHonolulu\t\t21.3\t-157.8\tP\tPPLA\tUS\t\tHI\t\t\t\t350000\t0\t1\tTZ\t2024",
        "3\tSan Juan\tSan Juan\t\t18.4\t-66.1\tP\tPPLA\tUS\t\tPR\t\t\t\t395000\t0\t1\tTZ\t2024",
    ])
    rows = pick_nodes.parse_geonames(rows_txt, admin1)
    assert [r["name"] for r in rows] == ["Austin"]


def test_rank_candidates_excludes_existing_and_nearby():
    rows = [
        {"name": "Austin", "state": "Texas", "lat": 30.27, "lon": -97.74, "population": 961855},
        {"name": "NearChi", "state": "Illinois", "lat": 41.95, "lon": -87.70, "population": 500000},
        {"name": "Tiny", "state": "Texas", "lat": 35.0, "lon": -101.0, "population": 50000},
    ]
    out = pick_nodes.rank_candidates(
        rows, {"Chicago"}, [(41.88, -87.63)],
        top_n=10, min_population=100_000, dedupe_mi=30.0)
    # NearChi is ~5 mi from existing Chicago; Tiny is below the pop floor
    assert [c["name"] for c in out] == ["Austin"]


def test_rank_candidates_dedupes_among_candidates_keeping_larger():
    rows = [
        {"name": "Big", "state": "Texas", "lat": 29.76, "lon": -95.37, "population": 900000},
        {"name": "BigSuburb", "state": "Texas", "lat": 29.80, "lon": -95.40, "population": 400000},
        {"name": "Far", "state": "Florida", "lat": 25.76, "lon": -80.19, "population": 300000},
    ]
    out = pick_nodes.rank_candidates(
        rows, set(), [], top_n=10, min_population=100_000, dedupe_mi=30.0)
    names = [c["name"] for c in out]
    assert "Big" in names and "Far" in names
    assert "BigSuburb" not in names  # within 30 mi of the larger Big


def test_rank_candidates_respects_top_n_by_population():
    rows = [
        {"name": "A", "state": "Texas", "lat": 31.0, "lon": -100.0, "population": 800000},
        {"name": "B", "state": "Florida", "lat": 27.0, "lon": -81.0, "population": 700000},
        {"name": "C", "state": "Ohio", "lat": 40.0, "lon": -83.0, "population": 600000},
    ]
    out = pick_nodes.rank_candidates(
        rows, set(), [], top_n=2, min_population=100_000, dedupe_mi=30.0)
    assert [c["name"] for c in out] == ["A", "B"]
