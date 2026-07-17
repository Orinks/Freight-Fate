"""Official truck-parking capacity and posted-restriction data behavior."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from freight_fate.data.world_models import RouteRestriction, Stop
from freight_fate.data.world_parsing import _parse_restrictions, _parse_stop
from freight_fate.sim import hos
from freight_fate.sim.trip_models import RoadStop

ROOT = Path(__file__).resolve().parents[1]


# --- parking_spaces on stops ------------------------------------------------


def _stop_raw(**overrides):
    raw = {
        "name": "Kenosha Safety Rest Area",
        "type": "public_rest_area",
        "at_mi": 30.0,
        "parking": "confirmed",
        "source": "WisDOT rest-area page",
    }
    raw.update(overrides)
    return raw


def test_parse_stop_reads_parking_spaces():
    stop = _parse_stop(_stop_raw(parking_spaces=45), 60.0, "a", "b")
    assert stop.parking_spaces == 45


def test_parse_stop_defaults_parking_spaces_to_zero():
    stop = _parse_stop(_stop_raw(), 60.0, "a", "b")
    assert stop.parking_spaces == 0


def test_parse_stop_rejects_implausible_parking_spaces():
    with pytest.raises(ValueError, match="implausible"):
        _parse_stop(_stop_raw(parking_spaces=5000), 60.0, "a", "b")
    with pytest.raises(ValueError, match="implausible"):
        _parse_stop(_stop_raw(parking_spaces=-3), 60.0, "a", "b")


def test_stop_parking_label_speaks_capacity_when_surveyed():
    stop = Stop("Rest Area", 10.0, "public_rest_area", parking="confirmed", parking_spaces=45)
    assert stop.parking_label == "confirmed truck parking, 45 spaces"
    unsurveyed = Stop("Rest Area", 10.0, "public_rest_area", parking="confirmed")
    assert unsurveyed.parking_label == "confirmed truck parking"


def test_road_stop_parking_text_speaks_capacity_when_surveyed():
    stop = RoadStop("Rest Area", 10.0, "public_rest_area", parking="confirmed", parking_spaces=22)
    assert stop.parking_text == "confirmed truck parking, 22 spaces"
    silent = RoadStop("Rest Area", 10.0, "public_rest_area", parking="likely", parking_spaces=22)
    assert silent.parking_text == ""


# --- capacity-aware overnight crunch ----------------------------------------


def test_parking_crunch_unchanged_when_capacity_unknown():
    assert hos.parking_full_probability(23.0) == hos.parking_full_probability(23.0, 0)


def test_small_lots_fill_earlier_and_big_lots_later():
    base = hos.parking_full_probability(23.0)
    assert base > 0.0
    assert hos.parking_full_probability(23.0, 8) > base
    assert hos.parking_full_probability(23.0, 150) < base
    assert hos.parking_full_probability(23.0, 60) < base


def test_capacity_never_creates_daytime_crunch():
    assert hos.parking_full_probability(12.0, 5) == 0.0


# --- posted restriction advisories ------------------------------------------


def test_parse_restrictions_orders_and_validates():
    raw = [
        {"at_mi": 40.0, "kind": "weight_limit", "tons": 30.0},
        {"at_mi": 12.0, "kind": "low_clearance", "feet": 13.5},
    ]
    parsed = _parse_restrictions(raw, 60.0, "a", "b")
    assert [r.kind for r in parsed] == ["low_clearance", "weight_limit"]


def test_parse_restriction_rejects_unknown_kind_and_bad_values():
    with pytest.raises(ValueError, match="unknown kind"):
        _parse_restrictions([{"at_mi": 5.0, "kind": "toll"}], 60.0, "a", "b")
    with pytest.raises(ValueError, match="implausible clearance"):
        _parse_restrictions([{"at_mi": 5.0, "kind": "low_clearance", "feet": 3.0}], 60.0, "a", "b")
    with pytest.raises(ValueError, match="implausible weight"):
        _parse_restrictions([{"at_mi": 5.0, "kind": "weight_limit", "tons": 90.0}], 60.0, "a", "b")


def test_restriction_spoken_text_is_player_language():
    clearance = RouteRestriction(12.0, "low_clearance", feet=13.5)
    assert clearance.spoken_ahead == "low clearance ahead: posted 13 feet 6 inches"
    assert clearance.spoken_near == "Low clearance: posted 13 feet 6 inches."
    whole = RouteRestriction(12.0, "low_clearance", feet=14.0)
    assert whole.value_text == "14 feet"
    weight = RouteRestriction(40.0, "weight_limit", tons=30.0)
    assert weight.spoken_ahead == "weight limit ahead: posted 30 tons"
    fractional = RouteRestriction(40.0, "weight_limit", tons=27.5)
    assert fractional.value_text == "27.5 tons"


def test_restriction_rounding_never_speaks_twelve_inches():
    # 13.999 ft rounds to inches == 12 and must carry into the next foot.
    assert RouteRestriction(1.0, "low_clearance", feet=13.999).value_text == "14 feet"


# --- Jason's Law survey matching (curation tool) ----------------------------


def _load_curate_tool():
    spec = importlib.util.spec_from_file_location(
        "curate_route_pois", ROOT / "tools" / "curate_route_pois.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


curate = _load_curate_tool()


def _candidate(name, at_mi, spaces=20, highway="I-65"):
    return curate.Candidate(
        provider="jasons_law",
        key=f"key:{name}",
        name=name,
        poi_type="public_rest_area",
        lat=0.0,
        lon=0.0,
        highway=highway,
        exit_text="",
        source_url="https://example.test",
        source_note="test",
        parking="confirmed",
        services=("parking",),
        actions=("park", "save", "break", "sleep"),
        at_mi=at_mi,
        distance_mi=0.1,
        parking_spaces=spaces,
    )


def test_survey_match_prefers_distinctive_name_overlap():
    stops = [
        {"name": "Gee Creek Northbound Rest Area", "type": "public_rest_area", "at_mi": 30.0},
        {"name": "Scatter Creek Rest Area", "type": "public_rest_area", "at_mi": 30.4},
    ]
    match = curate._match_survey_record_to_stop(_candidate("Gee Creek NB", 30.5), stops, 1.5)
    assert match is stops[0]


def test_survey_match_rejects_conflicting_place_names():
    # Two different public facilities that happen to project near each other.
    stops = [{"name": "Sumter Welcome Center", "type": "public_rest_area", "at_mi": 30.0}]
    match = curate._match_survey_record_to_stop(
        _candidate("Greene County Rest Area (SB)", 30.2), stops, 1.5
    )
    assert match is None


def test_survey_match_never_gives_branded_stop_a_public_lot_count():
    stops = [{"name": "Pilot Travel Center Franklin", "type": "travel_center", "at_mi": 30.0}]
    match = curate._match_survey_record_to_stop(
        _candidate("Simpson County Welcome Center", 30.1), stops, 1.5
    )
    assert match is None


def test_survey_match_allows_generic_stop_name_by_proximity():
    stops = [{"name": "Truck Parking", "type": "truck_parking", "at_mi": 30.0}]
    match = curate._match_survey_record_to_stop(
        _candidate("Blytheville (WC) (10-12-A)", 30.2), stops, 1.5
    )
    assert match is stops[0]
