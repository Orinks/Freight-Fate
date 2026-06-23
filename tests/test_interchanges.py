"""Interchange data model, spoken phrasing, and navigation-cue wiring."""

import dataclasses

import pytest

from freight_fate.data.world import (
    Interchange,
    _format_route_ref,
    _join_destinations,
    _parse_interchange,
)
from freight_fate.sim import Trip, TruckState, WeatherSystem

# --- phrasing ---------------------------------------------------------------

def test_full_phrase_reads_naturally():
    ix = Interchange(at_mi=72.7, exit_ref="7", destinations=("Trenton", "New York"),
                     via="US 1 North", highway="I-95", source="OSM")
    assert ix.spoken_phrase == "exit 7 for US-1 North toward Trenton and New York"
    assert ix.near_phrase == "Exit 7 for US-1 North toward Trenton and New York now."


def test_bare_exit_number_still_speaks():
    ix = Interchange(at_mi=5.0, exit_ref="42", source="OSM")
    assert ix.spoken_phrase == "exit 42"


def test_destinations_without_exit_number():
    ix = Interchange(at_mi=5.0, destinations=("Camden", "Shore Points"),
                     via="NJ 129 South", source="OSM")
    assert ix.spoken_phrase == "exit for NJ-129 South toward Camden and Shore Points"


def test_named_junction_without_ref_or_destinations():
    ix = Interchange(at_mi=5.0, name="Scranton Beltway", source="OSM")
    assert ix.spoken_phrase == "exit for Scranton Beltway"


def test_route_ref_formatting():
    assert _format_route_ref("US 1 North") == "US-1 North"
    assert _format_route_ref("I 95") == "I-95"
    assert _format_route_ref("NJ 29 South") == "NJ-29 South"
    assert _format_route_ref("I 95 North;NJTP North") == "I-95 North and NJTP North"
    assert _format_route_ref("") == ""


def test_join_destinations_oxford_comma():
    assert _join_destinations(("Trenton",)) == "Trenton"
    assert _join_destinations(("Trenton", "New York")) == "Trenton and New York"
    assert _join_destinations(("A", "B", "C")) == "A, B, and C"
    assert _join_destinations(()) == ""


# --- parsing / validation ---------------------------------------------------

def _raw(**over):
    base = {"at_mi": 10.0, "exit_ref": "7", "destinations": ["Trenton"],
            "via": "US 1 North", "source": "OSM"}
    base.update(over)
    return base


def test_parse_round_trips_fields():
    ix = _parse_interchange(_raw(), 50.0, "A", "B", "I-95")
    assert ix.at_mi == 10.0
    assert ix.exit_ref == "7"
    assert ix.destinations == ("Trenton",)
    assert ix.via == "US 1 North"
    assert ix.highway == "I-95"  # inherited from the leg default


def test_parse_accepts_string_destination():
    ix = _parse_interchange(_raw(destinations="Trenton"), 50.0, "A", "B", "I-95")
    assert ix.destinations == ("Trenton",)


def test_parse_requires_something_sayable():
    with pytest.raises(ValueError, match="no exit ref"):
        _parse_interchange(_raw(exit_ref="", destinations=[], name=""),
                           50.0, "A", "B", "I-95")


def test_parse_requires_source():
    with pytest.raises(ValueError, match="no source"):
        _parse_interchange(_raw(source=""), 50.0, "A", "B", "I-95")


def test_parse_rejects_at_mi_out_of_range():
    with pytest.raises(ValueError, match="outside leg mileage"):
        _parse_interchange(_raw(at_mi=99.0), 50.0, "A", "B", "I-95")


def test_parse_rejects_raw_osm_text():
    with pytest.raises(ValueError, match="raw OSM"):
        _parse_interchange(_raw(destinations=["node/12345"]), 50.0, "A", "B", "I-95")


# --- cue wiring -------------------------------------------------------------

def _route_with_interchange(world, start="Chicago", end="Indianapolis"):
    route = world.route_options(start, end)[0]
    leg = route.legs[0]
    at = leg.miles / 2.0
    ix = Interchange(at_mi=at, exit_ref="21", destinations=("Lafayette",),
                     via="US 52 West", highway=leg.highway, source="OSM")
    route.legs[0] = dataclasses.replace(leg, interchanges=(ix,))
    return route, at


def test_interchange_produces_navigation_cue(world):
    route, _ = _route_with_interchange(world)
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    cues = [c for c in trip.navigation_cues if c.kind == "interchange"]
    assert len(cues) == 1
    assert "exit 21" in cues[0].text
    assert "Lafayette" in cues[0].text


def test_interchange_cue_fires_during_drive(world):
    route, _ = _route_with_interchange(world)
    truck = TruckState()
    truck.transmission.automatic = True
    truck.start_engine()
    trip = Trip(route, truck, WeatherSystem("great_lakes", seed=1), seed=2)
    truck.throttle = 0.85
    seen = []
    for _ in range(60 * 60 * 10):
        truck.auto_shift()
        truck.update(1 / 60)
        for ev in trip.update(1 / 60):
            cue = ev.data.get("cue")
            if getattr(cue, "kind", "") == "interchange":
                seen.append(ev.message)
        if trip.finished:
            break
    assert any("exit 21" in m for m in seen), seen
    assert any("Lafayette" in m for m in seen), seen


def test_reverse_direction_mirrors_interchange_position(world):
    forward = world.route_options("Chicago", "Indianapolis")[0]
    leg = forward.legs[0]
    at = leg.miles / 2.0 - 10.0
    ix = Interchange(at_mi=at, exit_ref="21", destinations=("Lafayette",),
                     via="US 52 West", highway=leg.highway, source="OSM")

    forward.legs[0] = dataclasses.replace(leg, interchanges=(ix,))
    fwd_trip = Trip(forward, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    fwd_cue = next(c for c in fwd_trip.navigation_cues if c.kind == "interchange")

    reverse = world.route_options("Indianapolis", "Chicago")[0]
    rev_leg = reverse.legs[0]
    reverse.legs[0] = dataclasses.replace(
        rev_leg, interchanges=(dataclasses.replace(ix, highway=rev_leg.highway),))
    rev_trip = Trip(reverse, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    rev_cue = next(c for c in rev_trip.navigation_cues if c.kind == "interchange")

    # Same physical exit, mirrored mileage from the opposite travel direction.
    assert fwd_cue.at_mi == pytest.approx(rev_leg.miles - rev_cue.at_mi, abs=0.2)


def test_next_navigation_context_mentions_exit(world):
    from freight_fate.sim.trip import NavigationCue

    route, _ = _route_with_interchange(world)
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    trip.navigation_cues = [
        NavigationCue("interchange:0:50:21", "interchange", 50.0,
                      "exit 21 for US-52 West toward Lafayette", "")
    ]
    trip.position_mi = 40.0
    assert trip.next_navigation_context() == (
        "Next exit in 10 miles: exit 21 for US-52 West toward Lafayette."
    )
