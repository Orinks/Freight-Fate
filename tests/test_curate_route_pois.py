"""Tests for tools/curate_route_pois.py: the route-stop curation tool.

Only the sleep-gap rule is pinned here. The operator chain feeds and the
survey fetch are network calls; these tests hand the tool candidates directly.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_tool():
    """Import tools/curate_route_pois.py by path (tools is not a package)."""
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location(
        "curate_route_pois", ROOT / "tools" / "curate_route_pois.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


crp = _load_tool()

# A straight 65-mile northbound leg along one meridian: one degree of
# latitude is about 69 miles, so the corridor runs from 44.0 to 44.94.
LEG_MILES = 65.0
LEG_LON = -93.29


def _leg(stops: list[dict]) -> dict:
    return {
        "from": "owatonna_mn_us",
        "to": "minneapolis_mn_us",
        "highway": "I-35",
        "miles": LEG_MILES,
        "stops": stops,
        "corridor": {
            "route_points": [
                {"at_mi": 0.0, "lat": 44.0, "lon": LEG_LON},
                {"at_mi": LEG_MILES, "lat": 44.0 + LEG_MILES / 69.0, "lon": LEG_LON},
            ]
        },
    }


def _bobtail_fuel_station(name: str, at_mi: float) -> dict:
    return {
        "name": name,
        "type": "fuel_station",
        "at_mi": at_mi,
        "source": "OpenStreetMap corridor amenity query; generic fuel station",
        "parking": "limited",
        "actions": ["park", "save", "fuel", "break"],
        "services": ["diesel", "parking"],
        "vehicle_access": "bobtail_only",
    }


def _travel_center(name: str, at_mi: float) -> dict:
    return {
        "name": name,
        "type": "travel_center",
        "at_mi": at_mi,
        "source": "Chain locator",
        "parking": "confirmed",
        "actions": ["park", "save", "fuel", "food", "break", "sleep"],
        "services": ["diesel", "food", "parking", "restrooms"],
        "vehicle_access": "tractor_trailer",
    }


def _rest_area(key: str, name: str, miles_up: float, miles_off: float) -> crp.Candidate:
    """A survey rest area ``miles_up`` the leg and ``miles_off`` its line."""
    return crp.Candidate(
        provider="jasons_law",
        key=key,
        name=name,
        poi_type="public_rest_area",
        lat=44.0 + miles_up / 69.0,
        # One degree of longitude at 44 degrees north is about 49.6 miles.
        lon=LEG_LON + miles_off / 49.6,
        highway="I-35",
        exit_text="mile post 68",
        source_url=crp.JASONS_LAW_ENDPOINT,
        source_note=f"survey lists {name}",
        parking="confirmed",
        services=("parking", "restrooms"),
        actions=("park", "save", "break", "sleep"),
        parking_spaces=20,
    )


def _names(leg: dict) -> list[str]:
    return [stop["name"] for stop in leg["stops"]]


def test_a_leg_with_only_bobtail_stops_takes_the_rest_areas_on_its_road():
    # Two convenience stations meet the density minimum for 65 miles, and
    # neither is a place a loaded truck can spend the night.
    leg = _leg(
        [_bobtail_fuel_station("Kwik Trip", 16.2), _bobtail_fuel_station("Kwik Trip #1116", 32.5)]
    )
    data = {"legs": [leg]}
    candidates = [
        _rest_area("743", "Heath Creek", 27.0, 0.6),
        _rest_area("746", "New Market", 33.9, 0.1),
    ]

    report = crp.curate_world(data, candidates, radius_miles=20.0)

    assert _names(leg) == ["Kwik Trip", "Heath Creek", "Kwik Trip #1116", "New Market"]
    assert report["sleep_gap_fills"] == 2
    assert report["sleep_gaps_remaining"] == []
    heath = next(stop for stop in leg["stops"] if stop["name"] == "Heath Creek")
    assert "sleep" in heath["actions"]
    assert heath["parking_spaces"] == 20


def test_a_leg_with_a_real_travel_center_is_not_a_sleep_gap():
    leg = _leg([_travel_center("Love's Travel Stop Albert Lea", 20.0)])
    data = {"legs": [leg]}

    report = crp.curate_world(data, [_rest_area("743", "Heath Creek", 27.0, 0.6)], 20.0)

    assert _names(leg) == ["Love's Travel Stop Albert Lea"]
    assert report["sleep_gap_fills"] == 0


def test_a_rest_area_off_the_road_does_not_fill_a_sleep_gap():
    # Three miles off the line is another road: the density fill may offer
    # it from its 20-mile radius, the sleep-gap rule may not.
    leg = _leg(
        [_bobtail_fuel_station("Kwik Trip", 16.2), _bobtail_fuel_station("Kwik Trip #1116", 32.5)]
    )
    data = {"legs": [leg]}

    report = crp.curate_world(data, [_rest_area("743", "Heath Creek", 27.0, 3.0)], 20.0)

    assert _names(leg) == ["Kwik Trip", "Kwik Trip #1116"]
    assert report["sleep_gap_fills"] == 0
    assert report["sleep_gaps_remaining"] == [
        {"from": "owatonna_mn_us", "to": "minneapolis_mn_us", "highway": "I-35"}
    ]


def _surveyed_rest_area(name: str, at_mi: float, spaces: int) -> dict:
    return {
        "name": name,
        "type": "public_rest_area",
        "at_mi": at_mi,
        "source": (
            f"FHWA Jason's Law truck parking inventory (NTAD via BTS) lists {name} "
            f"on I-35 with {spaces} truck parking spaces, mile post 68."
        ),
        "parking": "confirmed",
        "actions": ["park", "save", "break", "sleep"],
        "services": ["parking", "restrooms"],
        "directions": ["both"],
        "parking_spaces": spaces,
    }


def test_a_paired_record_that_raises_a_surveyed_count_says_so_in_the_source():
    # The stop already carries the westbound lot's count from the survey. The
    # eastbound lot across the median is bigger; keeping the larger count is
    # the documented rule, but the record must not then contradict its own
    # source sentence.
    stop = _surveyed_rest_area("Turnout westbound", 25.0, 16)
    leg = _leg([stop])
    data = {"legs": [leg]}
    eastbound = crp.Candidate(
        provider="jasons_law",
        key="1795",
        name="Turnout eastbound",
        poi_type="public_rest_area",
        lat=44.0 + 25.3 / 69.0,
        lon=LEG_LON,
        highway="I-35",
        exit_text="mile post 188",
        source_url=crp.JASONS_LAW_ENDPOINT,
        source_note="survey lists Turnout eastbound",
        parking="confirmed",
        services=("parking", "restrooms"),
        actions=("park", "save", "break", "sleep"),
        parking_spaces=25,
    )

    report = crp.annotate_truck_parking(data, [eastbound])

    assert report["annotated_stops"] == 1
    assert stop["parking_spaces"] == 25
    assert "16 truck parking spaces" in stop["source"]
    assert "Turnout eastbound lists 25 truck parking spaces" in stop["source"]
    assert stop["source"].count("Jason's Law") == 1
