"""Tests for tools/nonchain_plazas.py: what an unbranded service plaza really is."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_tool():
    """Import tools/nonchain_plazas.py by path (tools is not a package)."""
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location(
        "nonchain_plazas", ROOT / "tools" / "nonchain_plazas.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ncp = _load_tool()


def _place(name, tags=None, within=(), identified="at the coordinate", dist=0.0002, element="way"):
    osm = None
    if tags is not None:
        osm = {"element": element, "dist_mi": dist, "identified": identified, "tags": tags}
    return {"name": name, "osm": osm, "within": list(within)}


def _verdict(entry, tolled=False, curated=False):
    return ncp.decide_place(entry, tolled, curated)["verdict"]


def test_a_candidate_is_an_unbranded_service_plaza_that_does_not_name_itself():
    plaza = {"name": "Castaic Truck Stop", "type": "service_plaza"}
    assert ncp.is_candidate(plaza)
    assert not ncp.is_candidate({**plaza, "type": "travel_center"})
    assert not ncp.is_candidate({**plaza, "name": "Love's Travel Stop"})
    assert not ncp.is_candidate({**plaza, "name": "Sideling Hill Service Plaza"})
    # Once confirmed it is settled, which is what makes a second run a no-op.
    assert not ncp.is_candidate({**plaza, "source": f"x {ncp.CONFIRMED_NOTE} (read): y."})


def test_a_toll_authority_as_operator_keeps_the_plaza():
    entry = _place(
        "Clifton Springs Travel Plaza",
        {"highway": "services", "operator": "New York State Thruway Authority"},
        within=[{"amenity": "parking", "hgv": "designated"}],
    )
    verdict = ncp.decide_place(entry, True, False)
    assert verdict["verdict"] == "service_plaza"
    assert verdict["kind"] == "read"


def test_hgv_tags_make_a_travel_center_and_say_what_was_read():
    entry = _place(
        "Eagles",
        {"highway": "services"},
        within=[{"amenity": "fuel", "hgv": "yes"}, {"amenity": "weighbridge"}],
    )
    verdict = ncp.decide_place(entry, False, False)
    assert verdict["verdict"] == "travel_center"
    assert verdict["kind"] == "read"
    assert "truck scale" in verdict["why"]


def test_a_truck_stop_name_with_nothing_read_is_left_to_the_load_time_screen():
    entry = _place("Flags West Truck Stop", {"highway": "services"}, within=[{"amenity": "fuel"}])
    assert _verdict(entry) == "screen"
    assert _verdict(_place("Truck Stop 44")) == "screen"


def test_a_bare_services_feature_named_for_another_business_is_removed():
    bare = {"highway": "services", "operator": "WeGo Transit"}
    assert _verdict(_place("Bay 2", bare, element="node")) == "remove"
    assert _verdict(_place("Horner Industrial Group", {"highway": "services"})) == "remove"
    # Not when the name says stop, and not when nothing identified the place.
    assert _verdict(_place("Longhorn Travel Plaza", {"highway": "services"})) == "travel_center"
    assert _verdict(_place("Horner Industrial Group")) == "unverified"


def test_a_customer_lot_is_removed_even_with_a_pump_inside_its_bounds():
    entry = _place(
        "Auto Repair",
        {"highway": "services", "access": "customers", "operator": "Business Parking"},
        within=[{"amenity": "fuel"}],
    )
    assert _verdict(entry) == "remove"


def test_fuel_and_nothing_for_trucks_is_a_fuel_station():
    entry = _place("Mile Marker 27", {"highway": "services"}, within=[{"amenity": "fuel"}])
    verdict = ncp.decide_place(entry, False, False)
    assert (verdict["verdict"], verdict["kind"]) == ("fuel_station", "read")


def test_another_store_of_a_brand_does_not_identify_this_one():
    far = _place(
        "QuikTrip",
        {"amenity": "fuel", "brand": "QuikTrip", "hgv": "yes"},
        identified="by name",
        dist=2.4,
    )
    verdict = ncp.decide_place(far, False, False)
    # Its HGV tag is about that store. The brand sells fuel: derived, and said so.
    assert (verdict["verdict"], verdict["kind"]) == ("fuel_station", "derived")


def test_curated_parking_and_a_concession_name_keep_the_type():
    assert (
        _verdict(_place("Madison, CT - North", {"highway": "services", "hgv": "yes"}), curated=True)
        == "service_plaza"
    )
    assert (
        _verdict(_place("Lone Chimney Concessions Plaza", {"highway": "services"}))
        == "service_plaza"
    )


def test_the_committed_evidence_supports_the_match_distance_cut():
    evidence = json.loads(ncp.EVIDENCE_PATH.read_text(encoding="utf-8"))
    assert evidence["meta"]["kind"] == "read"
    distances = sorted(
        place["osm"]["dist_mi"] for place in evidence["places"].values() if place["osm"]
    )
    at_coordinate = [d for d in distances if d <= ncp.AT_COORDINATE_MI]
    beyond = [d for d in distances if d > ncp.AT_COORDINATE_MI]
    # The cut sits in a gap: nothing within a factor of twenty of it on either side.
    assert len(at_coordinate) >= 100
    assert max(at_coordinate) <= ncp.AT_COORDINATE_MI / 2
    assert min(beyond) >= ncp.AT_COORDINATE_MI * 20
    for place in evidence["places"].values():
        if place["osm"]:
            expected = (
                "at the coordinate"
                if place["osm"]["dist_mi"] <= ncp.AT_COORDINATE_MI
                else "by name"
            )
            assert place["osm"]["identified"] == expected


def test_the_retype_appends_what_was_read_and_resets_assumed_fields():
    stop = {
        "name": "Mile Marker 27",
        "type": "service_plaza",
        "source": "OpenStreetMap/Overpass query.",
        "parking": "likely",
        "services": ["diesel", "food", "parking"],
        "actions": ["park", "save", "fuel", "food", "break", "sleep"],
    }
    verdict = {"verdict": "fuel_station", "kind": "read", "why": "it maps fuel"}
    out = ncp._retyped(stop, verdict)
    assert out["type"] == "fuel_station"
    assert out["source"].startswith("OpenStreetMap/Overpass query. Type corrected from")
    assert "(read)" in out["source"] and ncp.ACCESSED in out["source"]
    assert out["services"] == ["diesel", "parking"]
    assert "sleep" not in out["actions"]
    assert out["parking"] == "limited"
    # A travel center keeps the fields: the import assumed the same for both.
    kept = ncp._retyped(stop, {**verdict, "verdict": "travel_center"})
    assert kept["services"] == stop["services"] and kept["actions"] == stop["actions"]
    assert stop["type"] == "service_plaza"
