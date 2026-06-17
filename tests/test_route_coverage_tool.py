"""Route metadata coverage report tests."""

from __future__ import annotations

import json
import subprocess
import sys


def test_route_coverage_report_is_machine_readable():
    result = subprocess.run(
        [
            sys.executable,
            "tools/enrich_routes.py",
            "--coverage-report",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)

    assert report["metadata_contract"]["runtime_network_calls"] is False
    assert report["metadata_contract"]["legacy_full_graph_available_for_old_saves"] is True
    assert report["metadata_contract"]["placeholder_pois_do_not_count_for_dispatch"]
    assert "Curated truck-stop coverage" in report["current_batch_notes"][0]
    assert report["totals"]["legs"] == 106
    assert report["totals"]["playable"] < report["totals"]["legs"]
    assert report["totals"]["route_points"] == report["totals"]["legs"]
    assert report["totals"]["grade_segments"] == report["totals"]["legs"]
    assert report["totals"]["placeholder_pois"] > 0
    assert report["totals"]["legs_with_placeholder_only"] > 0
    assert report["totals"]["legs_with_curated_pois"] < report["totals"]["legs"]
    assert report["totals"]["legs_with_sufficient_poi_density"] < report["totals"]["legs"]
    assert report["totals"]["state_crossings_expected_present"] == (
        report["totals"]["state_crossings_expected"]
    )
    assert report["totals"]["toll_events"] >= 10
    assert report["totals"]["toll_legs"] >= 5

    chicago_indy = next(
        leg for leg in report["legs"]
        if leg["from"] == "Chicago" and leg["to"] == "Indianapolis"
    )
    assert chicago_indy["playable"]
    assert chicago_indy["missing"] == []

    chicago_st_louis = next(
        leg for leg in report["legs"]
        if leg["from"] == "Chicago" and leg["to"] == "St. Louis"
    )
    assert chicago_st_louis["playable"]
    assert chicago_st_louis["missing"] == []
    assert chicago_st_louis["curated_poi_count"] >= (
        chicago_st_louis["minimum_curated_pois"]
    )

    placeholder_only = next(
        leg for leg in report["legs"]
        if leg["from"] == "Indianapolis" and leg["to"] == "St. Louis"
    )
    assert not placeholder_only["playable"]
    assert placeholder_only["placeholder_poi_count"] == 1
    assert "curated_pois" in placeholder_only["missing"]
    assert placeholder_only["unsupported_reasons"]

    newly_curated = {
        ("New York", "Boston"): 2,
        ("Indianapolis", "Nashville"): 2,
        ("Nashville", "Atlanta"): 2,
        ("Kansas City", "Denver"): 3,
        ("Dallas", "Albuquerque"): 3,
    }
    for (start, end), expected_count in newly_curated.items():
        leg = next(
            item for item in report["legs"]
            if item["from"] == start and item["to"] == end
        )
        assert leg["playable"], f"{start} to {end}"
        assert leg["curated_poi_count"] >= expected_count
        assert leg["missing"] == []

    priorities = {
        item["label"]: item
        for item in report["high_priority_remaining_corridors"]
    }
    assert priorities["PA Turnpike / I-76 Allegheny corridor"]["playable"]
    assert priorities["Ohio/Indiana Turnpike and I-80/I-90 corridor"]["playable"]
    assert priorities["I-95 Northeast Corridor south of Philadelphia"]["playable"]
