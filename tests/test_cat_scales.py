"""Tests for tools/cat_scales.py: which truck stops have a CAT Scale."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
_spec = importlib.util.spec_from_file_location("cat_scales", ROOT / "tools" / "cat_scales.py")
cs = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = cs
_spec.loader.exec_module(cs)

SNAPSHOT = {"accessed": "2026-09-24", "points": [["n1", 40.0, -80.0]]}


def _stop(lat, services=("diesel",), source="Brand page.", kind="travel_center"):
    return {"type": kind, "lat": lat, "lon": -80.0, "services": list(services), "source": source}


def test_only_cat_branded_weighbridges_are_kept():
    overpass = {
        "elements": [
            {"type": "node", "id": 2, "lat": 1.0, "lon": 2.0, "tags": {"brand": "CAT Scale"}},
            {
                "type": "way",
                "id": 1,
                "center": {"lat": 3.0, "lon": 4.0},
                "tags": {"name": "CAT Scale"},
            },
            {"type": "node", "id": 3, "lat": 5.0, "lon": 6.0, "tags": {"operator": "Iowa DOT"}},
            {"type": "node", "id": 4, "lat": 7.0, "lon": 8.0, "tags": {}},
        ]
    }
    assert cs.cat_points(overpass) == [["n2", 1.0, 2.0], ["w1", 3.0, 4.0]]


def test_stop_on_the_lot_is_marked_once_and_a_neighbour_is_not():
    on_lot = _stop(40.001)  # about 0.07 mi
    across_town = _stop(40.01)  # about 0.7 mi
    pump = _stop(40.001, kind="fuel_station")
    data = {"legs": [{"stops": [on_lot, across_town, pump]}]}
    assert cs.apply(data, SNAPSHOT)["marked"] == 1
    assert on_lot["services"] == ["diesel", "scale"]
    assert cs.MARKER in on_lot["source"]
    assert "scale" not in across_town["services"] and "scale" not in pump["services"]
    # A second run changes nothing.
    assert cs.apply(data, SNAPSHOT) == {"marked": 0, "unmarked": 0, "already listed": 0}
    assert on_lot["services"] == ["diesel", "scale"]


def test_a_scale_that_leaves_the_map_is_unmarked_but_a_brand_read_one_stays():
    ours = _stop(40.001)
    brand_read = _stop(40.001, services=("diesel", "scale"))
    data = {"legs": [{"stops": [ours, brand_read]}]}
    cs.apply(data, SNAPSHOT)
    counts = cs.apply(data, {"accessed": "2026-10-01", "points": [["n9", 10.0, 10.0]]})
    assert counts["unmarked"] == 1
    assert ours["services"] == ["diesel"] and ours["source"] == "Brand page."
    assert brand_read["services"] == ["diesel", "scale"]
