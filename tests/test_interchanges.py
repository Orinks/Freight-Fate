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
from freight_fate.sim.trip import _leg_heading, _nearest_exit_label

# --- phrasing ---------------------------------------------------------------


def test_full_phrase_reads_naturally():
    ix = Interchange(
        at_mi=72.7,
        exit_ref="7",
        destinations=("Trenton", "New York"),
        via="US 1 North",
        highway="I-95",
        source="OSM",
    )
    assert ix.spoken_phrase == "exit 7 for US-1 North toward Trenton and New York"
    assert ix.near_phrase == "Exit 7 for US-1 North toward Trenton and New York now."


def test_bare_exit_number_still_speaks():
    ix = Interchange(at_mi=5.0, exit_ref="42", source="OSM")
    assert ix.spoken_phrase == "exit 42"


def test_destinations_without_exit_number():
    ix = Interchange(
        at_mi=5.0, destinations=("Camden", "Shore Points"), via="NJ 129 South", source="OSM"
    )
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
    base = {
        "at_mi": 10.0,
        "exit_ref": "7",
        "destinations": ["Trenton"],
        "via": "US 1 North",
        "source": "OSM",
    }
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
        _parse_interchange(_raw(exit_ref="", destinations=[], name=""), 50.0, "A", "B", "I-95")


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
    ix = Interchange(
        at_mi=at,
        exit_ref="21",
        destinations=("Lafayette",),
        via="US 52 West",
        highway=leg.highway,
        source="OSM",
    )
    route.legs[0] = dataclasses.replace(leg, interchanges=(ix,))
    return route, at


def test_interchange_produces_navigation_cue(world):
    route, _ = _route_with_interchange(world)
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    cues = [c for c in trip.navigation_cues if c.kind == "interchange"]
    assert len(cues) == 1
    assert "exit 21" in cues[0].text
    assert "Lafayette" in cues[0].text


def test_interchange_cue_stays_silent_during_drive(world):
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
    assert seen == []


def test_reverse_direction_mirrors_interchange_position(world):
    forward = world.route_options("Chicago", "Indianapolis")[0]
    leg = forward.legs[0]
    at = leg.miles / 2.0 - 10.0
    ix = Interchange(
        at_mi=at,
        exit_ref="21",
        destinations=("Lafayette",),
        via="US 52 West",
        highway=leg.highway,
        source="OSM",
    )

    forward.legs[0] = dataclasses.replace(leg, interchanges=(ix,))
    fwd_trip = Trip(forward, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    fwd_cue = next(c for c in fwd_trip.navigation_cues if c.kind == "interchange")

    reverse = world.route_options("Indianapolis", "Chicago")[0]
    rev_leg = reverse.legs[0]
    reverse.legs[0] = dataclasses.replace(
        rev_leg, interchanges=(dataclasses.replace(ix, highway=rev_leg.highway),)
    )
    rev_trip = Trip(reverse, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    rev_cue = next(c for c in rev_trip.navigation_cues if c.kind == "interchange")

    # Same physical exit, mirrored mileage from the opposite travel direction.
    assert fwd_cue.at_mi == pytest.approx(rev_leg.miles - rev_cue.at_mi, abs=0.2)


def test_next_exit_context_mentions_flavor_exit(world):
    from freight_fate.sim.trip import NavigationCue

    route, _ = _route_with_interchange(world)
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    trip.navigation_cues = [
        NavigationCue(
            "interchange:0:50:21",
            "interchange",
            50.0,
            "exit 21 for US-52 West toward Lafayette",
            "",
        )
    ]
    trip.position_mi = 40.0
    assert trip.next_navigation_context() == "Destination Indianapolis ahead."
    assert trip.next_exit_context() == (
        "Next listed exit in 10 miles: exit 21 for US-52 West toward Lafayette."
    )


def test_next_navigation_context_prioritizes_actionable_stop_over_exit(world):
    from freight_fate.sim.trip import NavigationCue

    route, _ = _route_with_interchange(world)
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    trip.navigation_cues = [
        NavigationCue(
            "interchange:0:40:21",
            "interchange",
            40.0,
            "exit 21 for US-52 West toward Lafayette",
            "",
        ),
        NavigationCue(
            "rest_stop:0:50:pilot", "rest_stop", 50.0, "travel center ahead at exit 26", ""
        ),
    ]
    trip.position_mi = 30.0
    assert trip.next_navigation_context() == (
        "Next stop in 20 miles: travel center ahead at exit 26."
    )
    assert trip.next_exit_context() == (
        "Next listed exit in 10 miles: exit 21 for US-52 West toward Lafayette."
    )


# --- Scope A: grounded exits, ramps, onramps --------------------------------


def test_interchange_exit_label_property():
    assert Interchange(at_mi=5.0, exit_ref="7", source="x").exit_label == "exit 7"
    assert Interchange(at_mi=5.0, destinations=("Camden",), source="x").exit_label == ""


def test_leg_heading_follows_route_numbering(world):
    # Odd routes are signed N/S even where the geometry runs diagonally
    # (I-95 NY->Philadelphia trends southwest but is signed South).
    assert _leg_heading("I-95", "new_york_ny_us", "philadelphia_pa_us") == "South"
    assert _leg_heading("I-95", "philadelphia_pa_us", "new_york_ny_us") == "North"
    # Even routes are signed E/W.
    assert _leg_heading("I-80", "chicago_il_us", "cleveland_oh_us") == "East"
    assert _leg_heading("I-80", "cleveland_oh_us", "chicago_il_us") == "West"
    # No route number -> no heading.
    assert _leg_heading("Local Road", "chicago_il_us", "cleveland_oh_us") == ""


def _leg0_curated_stop(route):
    leg = route.legs[0]
    forward = route.cities[0] == leg.a
    stop = next(s for s in leg.stops if s.curated and s.applies_to_direction(forward))
    return leg, stop


def test_nearest_exit_label_respects_tolerance(world):
    base = world.route_options("Chicago", "Indianapolis")[0].legs[0]
    leg = dataclasses.replace(
        base,
        interchanges=(
            Interchange(at_mi=50.0, exit_ref="7", source="x"),
            Interchange(at_mi=80.0, exit_ref="", destinations=("Town",), source="x"),
        ),
    )
    assert _nearest_exit_label(leg, 51.0) == "exit 7"  # within 2.0 mi
    assert _nearest_exit_label(leg, 55.0) == ""  # too far
    assert _nearest_exit_label(leg, 80.0) == ""  # nearest has no ref


def test_place_stops_attaches_exit_label(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    leg, target = _leg0_curated_stop(route)
    ix = Interchange(
        at_mi=target.at_mi,
        exit_ref="21",
        destinations=("Lafayette",),
        via="US 52 West",
        highway=leg.highway,
        source="OSM",
    )
    route.legs[0] = dataclasses.replace(leg, interchanges=(ix,))
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    placed = next(s for s in trip.stops if s.name == target.name)
    assert placed.exit_label == "exit 21"


def test_rest_stop_cue_names_exit_when_linked(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    leg, target = _leg0_curated_stop(route)
    ix = Interchange(
        at_mi=target.at_mi,
        exit_ref="21",
        destinations=("Lafayette",),
        via="US 52 West",
        highway=leg.highway,
        source="OSM",
    )
    route.legs[0] = dataclasses.replace(leg, interchanges=(ix,))
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    cue = next(c for c in trip.navigation_cues if c.kind == "rest_stop" and target.name in c.key)
    assert "at exit 21" in cue.near_text


def test_rest_stop_cue_generic_without_linked_exit(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    leg, target = _leg0_curated_stop(route)
    route.legs[0] = dataclasses.replace(leg, interchanges=())
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    cue = next(c for c in trip.navigation_cues if c.kind == "rest_stop" and target.name in c.key)
    assert "exit" in cue.near_text  # "press X to take the exit"
    assert "at exit" not in cue.near_text  # no fabricated exit number


def test_first_leg_has_onramp_cue(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    onramps = [c for c in trip.navigation_cues if c.kind == "onramp"]
    assert len(onramps) == 1
    text = onramps[0].near_text
    assert text.startswith(f"Merge onto {route.legs[0].highway} South toward ")
    assert "Indianapolis" in text and "miles." in text


def test_onramp_cue_fires_at_drive_start(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    truck = TruckState()
    truck.transmission.automatic = True
    truck.start_engine()
    trip = Trip(route, truck, WeatherSystem("great_lakes", seed=1), seed=2)
    truck.throttle = 0.85
    seen = []
    for _ in range(60 * 120):
        truck.auto_shift()
        truck.update(1 / 60)
        for ev in trip.update(1 / 60):
            if "Merge onto" in ev.message:
                seen.append(ev.message)
        if seen:
            break
    assert seen and seen[0].startswith("Merge onto")


# --- text cleanup: exit-ref whitespace + via-redundant destinations ---------


def test_parse_normalizes_exit_ref_whitespace():
    ix = _parse_interchange(_raw(exit_ref="103 B"), 50.0, "A", "B", "I-70")
    assert ix.exit_ref == "103B"
    assert ix.exit_label == "exit 103B"


def test_spoken_phrase_drops_via_redundant_destination():
    ix = Interchange(
        at_mi=5.0,
        exit_ref="101A",
        via="I 70",
        destinations=("I 70 East", "Parsons Avenue"),
        source="x",
    )
    assert ix.spoken_phrase == "exit 101A for I-70 toward Parsons Avenue"


def test_spoken_phrase_via_only_when_all_destinations_redundant():
    ix = Interchange(
        at_mi=5.0, exit_ref="101A", via="I 70", destinations=("I 70 East",), source="x"
    )
    assert ix.spoken_phrase == "exit 101A for I-70"


def test_spoken_phrase_keeps_unrelated_destinations():
    ix = Interchange(
        at_mi=5.0, exit_ref="7", via="US 1 North", destinations=("Trenton", "New York"), source="x"
    )
    assert ix.spoken_phrase == "exit 7 for US-1 North toward Trenton and New York"


# --- metric navigation distances --------------------------------------------


def test_metric_navigation_cues_use_kilometers(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    metric = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2, imperial=False)
    blob = " ".join(f"{c.text} {c.near_text}" for c in metric.navigation_cues)
    assert "kilometers" in blob
    assert "mile" not in blob

    # The default (imperial) trip keeps miles, so existing drives are unchanged.
    imperial = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    blob_i = " ".join(f"{c.text} {c.near_text}" for c in imperial.navigation_cues)
    assert "miles" in blob_i


def test_metric_drive_speaks_distances_in_kilometers(world):
    from freight_fate.sim.trip import TripEventKind

    route = world.route_options("Chicago", "Indianapolis")[0]
    truck = TruckState()
    truck.transmission.automatic = True
    truck.start_engine()
    trip = Trip(route, truck, WeatherSystem("great_lakes", seed=1), seed=2, imperial=False)
    truck.throttle = 0.85
    nav: list[str] = []
    for _ in range(60 * 60 * 12):
        truck.auto_shift()
        truck.update(1 / 60)
        for ev in trip.update(1 / 60):
            if ev.kind in (TripEventKind.GPS_CUE, TripEventKind.STOP_AHEAD):
                nav.append(ev.message)
        if trip.finished:
            break
    assert nav, "expected navigation announcements on a long metric drive"
    blob = " ".join(nav)
    assert "kilometers" in blob
    assert "mile" not in blob


def test_unit_toggle_rerenders_baked_navigation_cues(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)

    def cue_blob() -> str:
        return " ".join(f"{c.text} {c.near_text}" for c in trip.navigation_cues)

    assert "miles" in cue_blob() and "kilometers" not in cue_blob()
    # Switching units mid-trip re-renders the distances already on the route.
    trip.imperial = False
    assert "kilometers" in cue_blob() and "mile" not in cue_blob()
    trip.imperial = True
    assert "miles" in cue_blob() and "kilometers" not in cue_blob()


def test_metric_zone_warning_uses_metric_speed_limit(world):
    from freight_fate.sim.trip import TripEventKind, Zone

    route = world.route_options("Chicago", "Indianapolis")[0]
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2, imperial=False)
    trip.zones = [Zone(5.0, 10.0, 45.0, "construction")]
    trip._announced_zone_warnings.clear()
    trip.position_mi = 4.0  # within the 2-mile warning lookahead of the zone

    msgs = [ev.message for ev in trip.update(0.0) if ev.kind == TripEventKind.GPS_CUE]
    blob = " ".join(msgs)
    assert "Speed limit 72" in blob  # 45 mph rendered as 72 km/h
    assert "Speed limit 45" not in blob
