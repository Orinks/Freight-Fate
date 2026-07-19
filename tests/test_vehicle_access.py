"""Stops a rig cannot physically enter stay out of the player's ears.

The map carries car-scale fuel stops a 70-foot combination vehicle has no
way into. Announcing one is a promise: "press X to take the exit" means the
stop is usable. A false stop burns driving hours and can strand a player
with no legal alternative, which is worse than no stop at all. So
``vehicle_access`` gates every surface that offers or counts a stop, and it
is a separate axis from parking certainty -- a lot can admit a rig for fuel
and still have nowhere to park it.
"""

from __future__ import annotations

import dataclasses

import pytest

from freight_fate.data.world_constants import (
    DEFAULT_VEHICLE_ACCESS,
    VEHICLE_ACCESS_LEVELS,
    vehicle_access_allows,
)
from freight_fate.data.world_models import Route, Stop
from freight_fate.data.world_parsing import _parse_stop
from freight_fate.sim.trip import Trip
from freight_fate.sim.trip_models import RoadStop
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherSystem


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


# --- parsing ----------------------------------------------------------------


def test_parse_stop_defaults_to_tractor_trailer():
    """Unclassified data keeps behaving exactly as it did before the sweep."""
    assert _parse_stop(_stop_raw(), 60.0, "a", "b").vehicle_access == "tractor_trailer"
    assert DEFAULT_VEHICLE_ACCESS == "tractor_trailer"


@pytest.mark.parametrize("level", sorted(VEHICLE_ACCESS_LEVELS))
def test_parse_stop_reads_every_access_level(level):
    stop = _parse_stop(_stop_raw(vehicle_access=level), 60.0, "a", "b")
    assert stop.vehicle_access == level


def test_parse_stop_rejects_unknown_access():
    with pytest.raises(ValueError, match="vehicle_access"):
        _parse_stop(_stop_raw(vehicle_access="rv_only"), 60.0, "a", "b")


def test_access_is_independent_of_parking():
    """A site may admit a rig for fuel and have nowhere to park it."""
    stop = _parse_stop(
        _stop_raw(parking="none", vehicle_access="tractor_trailer"), 60.0, "a", "b"
    )
    assert stop.parking == "none"
    assert stop.accessible_to(bobtail=False)


# --- the shared rule --------------------------------------------------------


def test_tractor_trailer_is_usable_by_everyone():
    assert vehicle_access_allows("tractor_trailer", bobtail=False)
    assert vehicle_access_allows("tractor_trailer", bobtail=True)


def test_bobtail_only_needs_a_bobtail():
    assert not vehicle_access_allows("bobtail_only", bobtail=False)
    assert vehicle_access_allows("bobtail_only", bobtail=True)


def test_none_is_never_usable():
    """Landmark only -- no rig configuration unlocks it."""
    assert not vehicle_access_allows("none", bobtail=False)
    assert not vehicle_access_allows("none", bobtail=True)


def test_stop_and_road_stop_agree():
    """The world model and the runtime stop must never disagree."""
    for level in sorted(VEHICLE_ACCESS_LEVELS):
        for bobtail in (False, True):
            world_stop = Stop("X", 10.0, vehicle_access=level)
            road_stop = RoadStop("X", 10.0, vehicle_access=level)
            assert world_stop.accessible_to(bobtail=bobtail) == road_stop.accessible_to(
                bobtail=bobtail
            )


# --- the driving surfaces ---------------------------------------------------


def _stops():
    return (
        Stop("Big Rig Plaza", 20.0, "travel_center", "note", ("fuel", "sleep"), ("diesel",)),
        Stop(
            "Corner Mart",
            40.0,
            "fuel_station",
            "note",
            ("fuel",),
            ("diesel",),
            vehicle_access="bobtail_only",
        ),
        Stop(
            "Scenic Overlook",
            60.0,
            "public_rest_area",
            "note",
            ("break",),
            (),
            vehicle_access="none",
        ),
    )


def _trip(world, *, bobtail: bool) -> Trip:
    cached = world.route_options("Chicago", "Indianapolis")[0]
    leg = dataclasses.replace(cached.legs[0], stops=_stops())
    route = Route(cities=list(cached.cities), legs=[leg] + list(cached.legs[1:]))
    truck = TruckState()
    truck.transmission.automatic = True
    return Trip(route, truck, WeatherSystem("great_lakes", seed=1), seed=2, bobtail=bobtail)


def _placed_names(trip: Trip) -> set[str]:
    return {stop.name for stop in trip.stops}


def test_pulling_a_trailer_hides_stops_a_rig_cannot_enter(world):
    names = _placed_names(_trip(world, bobtail=False))
    assert "Big Rig Plaza" in names
    assert "Corner Mart" not in names
    assert "Scenic Overlook" not in names


def test_bobtailing_unlocks_bobtail_only_stops(world):
    names = _placed_names(_trip(world, bobtail=True))
    assert "Big Rig Plaza" in names
    assert "Corner Mart" in names
    # Landmark-only stays landmark-only even tractor-first.
    assert "Scenic Overlook" not in names


def test_trip_defaults_to_the_cautious_read(world):
    """A caller that never says lands on the trailer case, not the open one."""
    cached = world.route_options("Chicago", "Indianapolis")[0]
    leg = dataclasses.replace(cached.legs[0], stops=_stops())
    route = Route(cities=list(cached.cities), legs=[leg] + list(cached.legs[1:]))
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    assert not trip.bobtail
    assert "Corner Mart" not in _placed_names(trip)


def test_navigation_cues_hide_the_same_stops(world):
    """The cue path reads legs directly -- it must not re-announce what the
    placed stops ruled out."""
    trip = _trip(world, bobtail=False)
    cue_texts = " ".join(cue.text for cue in trip.navigation_cues if cue.kind == "rest_stop")
    assert "Corner Mart" not in cue_texts
    assert "Scenic Overlook" not in cue_texts


def test_exit_arming_never_offers_an_unusable_stop(world):
    """upcoming_stop backs the X-arming path and the HOS next-legal-stop line."""
    trip = _trip(world, bobtail=False)
    trip.position_mi = 35.0
    stop = trip.upcoming_stop(20.0)
    assert stop is None or stop.name != "Corner Mart"


# --- pre-trip planning ------------------------------------------------------


def test_route_planning_counts_only_usable_stops(world):
    cached = world.route_options("Chicago", "Indianapolis")[0]
    leg = dataclasses.replace(cached.legs[0], stops=_stops())
    route = Route(cities=[cached.cities[0], cached.cities[1]], legs=[leg])

    usable = route.accessible_stop_details()
    assert [s.name for s in usable] == ["Big Rig Plaza"]
    # The unfiltered view still sees everything, for tooling and data review.
    assert len(route.stop_details) == 3

    bobtailing = route.accessible_stop_details(bobtail=True)
    assert [s.name for s in bobtailing] == ["Big Rig Plaza", "Corner Mart"]


# --- the wiring -------------------------------------------------------------


@pytest.mark.parametrize("bobtail", [False, True])
def test_the_job_decides_what_the_trip_can_reach(bobtail):
    """Everything above rests on the job's rig reaching the trip. A real
    dispatch, not a hand-built Trip, so the wiring itself is under test."""
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        app.ctx.profile = Profile(name="Access Rails")
        profile = app.ctx.profile
        profile.current_city = "Chicago"
        job = next(
            offer
            for offer in JobBoard(app.ctx.world).offers(
                profile.current_city,
                profile.career.endorsements,
                level=profile.career.level,
                market=profile.market,
            )
            if not offer.locked_reason(profile.career.endorsements, profile.career.level)
        )
        job = dataclasses.replace(job, bobtail=bobtail)
        route = app.ctx.world.supported_route_options(job.origin, job.destination)[0]

        driving = DrivingState(app.ctx, job, route)

        assert driving.trip.bobtail is bobtail
    finally:
        app.shutdown()
