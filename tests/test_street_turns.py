"""Surface-street turn-cue pacing and spoken road names."""

from freight_fate.data.world_models import Leg, Route
from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.trip import TripEventKind


def _street_route():
    """A synthetic three-block facility street chain (same-city route)."""
    city = "south_bend_in_us"
    legs = [
        Leg(
            city,
            city,
            0.15,
            "East Navarre Street",
            "flat",
            (),
            local_cue="Start on East Navarre Street.",
            local_speed_mph=25.0,
        ),
        Leg(
            city,
            city,
            0.2,
            "North Michigan Street",
            "flat",
            (),
            local_cue="Turn left onto North Michigan Street.",
            local_speed_mph=25.0,
        ),
        Leg(
            city,
            city,
            0.5,
            "South Michigan Street",
            "flat",
            (),
            local_cue="Continue onto South Michigan Street.",
            local_speed_mph=30.0,
        ),
    ]
    return Route([city] * (len(legs) + 1), legs)


def _street_trip():
    truck = TruckState()
    truck.transmission.automatic = True
    truck.start_engine()
    weather = WeatherSystem("great_lakes", seed=1)
    return Trip(_street_route(), truck, weather, seed=3), truck


def _local_turn_messages(events):
    return [
        e.message
        for e in events
        if e.kind == TripEventKind.GPS_CUE
        and getattr(e.data.get("cue"), "kind", "") == "local_turn"
    ]


# -- one maneuver at a time ------------------------------------------------


def test_departure_tick_speaks_only_the_first_street_maneuver():
    """Regression: a street chain used to read its whole itinerary on the
    first tick -- start, turn, and continue cues all inside the generic
    lookahead -- burying the maneuver that was actually next."""
    trip, _truck = _street_trip()
    spoken = _local_turn_messages(trip.update(1 / 60))
    assert len(spoken) == 1
    assert "East Navarre Street" in spoken[0]


def test_next_street_maneuver_waits_for_the_previous_junction():
    trip, _truck = _street_trip()
    trip.update(1 / 60)  # announces the start cue only
    # Still short of the first boundary: the turn stays quiet.
    trip.position_mi = 0.04
    assert _local_turn_messages(trip.update(1 / 60)) == []
    # Past it: the left turn becomes the nearest maneuver and speaks.
    trip.position_mi = 0.16
    spoken = _local_turn_messages(trip.update(1 / 60))
    assert len(spoken) == 1
    assert "Turn left onto North Michigan Street" in spoken[0]


# -- spoken road names -------------------------------------------------------


def test_spoken_road_text_trims_osm_ref_lists():
    from freight_fate.data.world_services import _spoken_road_text

    assert (
        _spoken_road_text("Turn left onto North Michigan Street (SR 933;BUS US 31).")
        == "Turn left onto North Michigan Street (SR 933)."
    )
    assert (
        _spoken_road_text("Slater Street SW (US 19; US 82; GA 3; GA 133; GA 520)")
        == "Slater Street SW (US 19)"
    )
    # Single refs and plain names pass through untouched.
    assert _spoken_road_text("Main Street (SR 26)") == "Main Street (SR 26)"
    assert _spoken_road_text("Richard G. Hatcher Boulevard") == "Richard G. Hatcher Boulevard"
    # Prose parentheticals with semicolons only lose text after the semicolon,
    # never the sentence around them.
    assert _spoken_road_text("no parens; still fine") == "no parens; still fine"


def test_facility_street_chains_speak_no_ref_lists(world):
    """Every turn-level facility approach in the shipped data reads clean:
    no semicolon ref lists survive into spoken cues or road names."""
    checked = 0
    for location_id, approach in world._facility_approaches.items():
        if not (approach.turn_level and approach.segments):
            continue
        if not any(";" in (s.cue or "") or ";" in (s.road or "") for s in approach.segments):
            continue
        city_key = location_id.split(":", 1)[0].replace("-", "_")
        if city_key not in world.cities:
            continue
        location = next(
            (
                loc
                for loc in world.cities[city_key].locations
                if getattr(loc, "id", None) == location_id
            ),
            None,
        )
        if location is None:
            continue
        route = world.facility_approach_route(city_key, location.name)
        for leg in route.legs:
            assert ";" not in leg.highway, (location_id, leg.highway)
            assert ";" not in (leg.local_cue or ""), (location_id, leg.local_cue)
        checked += 1
        if checked >= 5:
            break
    assert checked > 0, "expected at least one raw ref list in source data"
