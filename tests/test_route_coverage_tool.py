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
    assert "source-backed truck-stop coverage" in report["current_batch_notes"][0]
    assert report["totals"]["legs"] == 660
    assert report["totals"]["playable"] == report["totals"]["legs"]
    assert report["missing_playable"] == []
    assert report["totals"]["route_points"] == report["totals"]["legs"]
    assert report["totals"]["grade_segments"] == report["totals"]["legs"]
    assert report["totals"]["placeholder_pois"] == 0
    assert report["totals"]["legs_with_placeholder_only"] == 0
    # POIs are an additive quality layer now, not a dispatch gate.
    assert report["metadata_contract"]["pois_are_advisory_not_required_for_dispatch"]
    assert "curated_pois" not in report["metadata_contract"]["playable_requires"]
    assert isinstance(report["poi_review"], list)
    assert isinstance(report["toll_review"], list)
    assert (
        report["totals"]["state_crossings_expected_present"]
        == (report["totals"]["state_crossings_expected"])
    )
    assert report["totals"]["toll_events"] >= 10
    assert report["totals"]["toll_legs"] >= 5

    chicago_indy = next(
        leg
        for leg in report["legs"]
        if leg["from"] == "chicago_il_us" and leg["to"] == "indianapolis_in_us"
    )
    assert chicago_indy["playable"]
    assert chicago_indy["missing"] == []

    chicago_st_louis = next(
        leg
        for leg in report["legs"]
        if leg["from"] == "chicago_il_us" and leg["to"] == "st_louis_mo_us"
    )
    assert chicago_st_louis["playable"]
    assert chicago_st_louis["missing"] == []
    assert chicago_st_louis["curated_poi_count"] >= (chicago_st_louis["minimum_curated_pois"])

    formerly_placeholder_only = next(
        leg
        for leg in report["legs"]
        if leg["from"] == "indianapolis_in_us" and leg["to"] == "st_louis_mo_us"
    )
    assert formerly_placeholder_only["playable"]
    assert formerly_placeholder_only["placeholder_poi_count"] == 0
    assert (
        formerly_placeholder_only["curated_poi_count"]
        >= (formerly_placeholder_only["minimum_curated_pois"])
    )
    assert formerly_placeholder_only["missing"] == []
    assert formerly_placeholder_only["unsupported_reasons"] == []

    newly_curated = {
        ("new_york_ny_us", "boston_ma_us"): 2,
        ("indianapolis_in_us", "nashville_tn_us"): 2,
        ("nashville_tn_us", "atlanta_ga_us"): 2,
        ("kansas_city_mo_us", "denver_co_us"): 3,
        ("dallas_tx_us", "albuquerque_nm_us"): 3,
    }
    for (start, end), expected_count in newly_curated.items():
        leg = next(item for item in report["legs"] if item["from"] == start and item["to"] == end)
        assert leg["playable"], f"{start} to {end}"
        assert leg["curated_poi_count"] >= expected_count
        assert leg["missing"] == []

    priorities = {item["label"]: item for item in report["high_priority_remaining_corridors"]}
    assert priorities["PA Turnpike / I-76 Allegheny corridor"]["playable"]
    assert priorities["Ohio/Indiana Turnpike and I-80/I-90 corridor"]["playable"]
    assert priorities["I-95 Northeast Corridor south of Philadelphia"]["playable"]


def test_route_coverage_report_enforces_routing_contract():
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

    for leg in report["legs"]:
        # Dispatch gates on routing metadata only; POIs are advisory.
        assert leg["playable"], f"{leg['from']} to {leg['to']}"
        assert leg["missing"] == []
        assert leg["unsupported_reasons"] == []
        assert leg["placeholder_poi_count"] == 0
        # Where a leg does have curated POIs, they must be valid (actioned).
        if leg["curated_poi_count"]:
            assert leg["present"]["pois_with_actions"], f"{leg['from']} to {leg['to']}"
