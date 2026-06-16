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
    assert "NJ Turnpike-style service plaza POIs" in report["current_batch_notes"][0]
    assert report["totals"]["legs"] == 106
    assert report["totals"]["playable"] >= 9
    assert report["totals"]["playable"] < report["totals"]["legs"]
    assert report["totals"]["pois_with_actions"] >= report["totals"]["playable"]

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
    assert not chicago_st_louis["playable"]
    assert "route_points" in chicago_st_louis["missing"]

    priorities = {
        item["label"]: item
        for item in report["high_priority_remaining_corridors"]
    }
    assert not priorities["PA Turnpike / I-76 Allegheny corridor"]["playable"]
    assert "route_points" in priorities["PA Turnpike / I-76 Allegheny corridor"]["missing"]
    assert not priorities["Ohio/Indiana Turnpike and I-80/I-90 corridor"]["playable"]
