"""Time zones: coordinate-to-zone derivation, the local wall clock, trip
boundary crossings with their spoken clock change, and delivery appointments
quoted in the destination's local time."""

from __future__ import annotations

import pygame
import pytest

from freight_fate.data.world_models import Leg, Route, RoutePoint, StateMileage
from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.timezones import (
    CENTRAL,
    EASTERN,
    MOUNTAIN,
    PACIFIC,
    appointment_text,
    local_clock_text,
    to_local,
    zone_for,
)
from freight_fate.sim.trip_models import TripEventKind

# --- zone derivation ----------------------------------------------------------


def test_whole_states_resolve_from_the_table():
    assert zone_for(33.75, -84.39, "Georgia") is EASTERN  # Atlanta
    assert zone_for(41.88, -87.63, "Illinois") is CENTRAL  # Chicago
    assert zone_for(39.74, -104.99, "Colorado") is MOUNTAIN  # Denver
    assert zone_for(47.61, -122.33, "Washington") is PACIFIC  # Seattle


@pytest.mark.parametrize(
    "place, lat, lon, state, expected",
    [
        ("Knoxville", 35.96, -83.92, "Tennessee", EASTERN),
        ("Chattanooga", 35.05, -85.31, "Tennessee", EASTERN),
        ("Nashville", 36.16, -86.78, "Tennessee", CENTRAL),
        ("Memphis", 35.15, -90.05, "Tennessee", CENTRAL),
        ("Miami", 25.76, -80.19, "Florida", EASTERN),
        ("Pensacola", 30.42, -87.22, "Florida", CENTRAL),
        ("Louisville", 38.25, -85.76, "Kentucky", EASTERN),
        ("Bowling Green", 36.99, -86.44, "Kentucky", CENTRAL),
        ("Indianapolis", 39.77, -86.16, "Indiana", EASTERN),
        ("Evansville", 37.97, -87.57, "Indiana", CENTRAL),
        ("Dallas", 32.78, -96.80, "Texas", CENTRAL),
        ("El Paso", 31.76, -106.49, "Texas", MOUNTAIN),
        ("Sioux Falls", 43.55, -96.73, "South Dakota", CENTRAL),
        ("Rapid City", 44.08, -103.23, "South Dakota", MOUNTAIN),
        ("Boise", 43.62, -116.20, "Idaho", MOUNTAIN),
        ("Coeur d'Alene", 47.68, -116.78, "Idaho", PACIFIC),
        ("Portland", 45.52, -122.68, "Oregon", PACIFIC),
        ("Ontario", 44.03, -116.96, "Oregon", MOUNTAIN),
    ],
)
def test_split_states_follow_the_real_boundary(place, lat, lon, state, expected):
    assert zone_for(lat, lon, state) is expected, place


def test_unknown_state_falls_back_to_longitude():
    assert zone_for(40.0, -75.0) is EASTERN
    assert zone_for(40.0, -95.0) is CENTRAL
    assert zone_for(40.0, -108.0) is MOUNTAIN
    assert zone_for(40.0, -120.0) is PACIFIC


def test_missing_geometry_keeps_the_reference_clock():
    # Synthetic legs and incomplete data carry (0, 0); the clock must not move.
    assert zone_for(0.0, 0.0) is EASTERN
    assert zone_for(0.0, 0.0, "Atlantis") is EASTERN


def test_every_world_city_resolves_to_a_conus_zone(world):
    for key, city in world.cities.items():
        zone = zone_for(city.lat, city.lon, city.state)
        assert zone in (EASTERN, CENTRAL, MOUNTAIN, PACIFIC), (key, city.state)


# --- the local wall clock -------------------------------------------------------


def test_local_clock_wraps_backwards_across_midnight():
    # 1 AM on the Eastern reference clock is 10 PM Pacific the night before.
    assert to_local(1.0, PACIFIC) == -2.0
    assert local_clock_text(1.0, PACIFIC) == "10 PM"


def test_local_clock_can_name_its_zone():
    assert local_clock_text(12.0, CENTRAL, with_zone=True) == "11 AM Central Time"


# --- appointments ---------------------------------------------------------------


def test_appointment_same_local_day():
    assert appointment_text(6.0, 4.0, EASTERN) == "10 AM Eastern Time"


def test_appointment_tomorrow_counts_local_midnights():
    assert appointment_text(20.0, 10.0, EASTERN) == "6 AM Eastern Time tomorrow"


def test_appointment_days_ahead():
    assert appointment_text(6.0, 44.0, EASTERN) == "2 AM Eastern Time in 2 days"


def test_appointment_tomorrow_judged_in_the_destination_zone():
    # 10 PM on the reference clock is 9 PM Central; five hours later is past
    # the receiver's midnight even though it is not past Eastern's.
    assert appointment_text(22.0, 5.0, CENTRAL) == "2 AM Central Time tomorrow"


# --- trip crossings -------------------------------------------------------------


def _tennessee_leg() -> Leg:
    """A stylized east-to-middle Tennessee leg: Eastern until the boundary at
    the halfway point, Central beyond it. Kept under 70 miles so the trip
    places no traffic or patrols for the synthetic endpoint cities."""
    return Leg(
        "A",
        "B",
        60.0,
        "I-40",
        "hills",
        (),
        state_miles=(StateMileage("Tennessee", 60.0),),
        route_points=(
            RoutePoint(0.0, 35.96, -83.92),
            RoutePoint(20.0, 35.90, -85.00),
            RoutePoint(30.0, 36.00, -85.80),
            RoutePoint(40.0, 36.10, -86.30),
            RoutePoint(60.0, 36.16, -86.78),
        ),
    )


def _trip(route: Route, start_hour: float = 12.0) -> Trip:
    return Trip(
        route, TruckState(), WeatherSystem("mid_south", seed=1), seed=2, start_hour=start_hour
    )


def test_trip_finds_the_boundary_from_route_geometry():
    trip = _trip(Route(["A", "B"], [_tennessee_leg()]))
    assert trip.start_timezone is EASTERN
    assert trip.destination_timezone is CENTRAL
    assert [(c.at_mi, c.to_zone.key) for c in trip.timezone_crossings] == [(30.0, "central")]
    assert trip.timezone_at(20.0) is EASTERN
    assert trip.timezone_at(35.0) is CENTRAL


def test_trip_reversed_route_mirrors_the_boundary():
    trip = _trip(Route(["B", "A"], [_tennessee_leg()]))
    assert trip.start_timezone is CENTRAL
    assert trip.destination_timezone is EASTERN
    # The crossing lands on the first sampled point inside the new zone, so
    # driving the same leg the other way quantizes to the next sample over.
    assert [(c.at_mi, c.to_zone.key) for c in trip.timezone_crossings] == [(40.0, "eastern")]


def test_crossing_announces_the_new_local_clock_once():
    trip = _trip(Route(["A", "B"], [_tennessee_leg()]), start_hour=12.0)
    trip.position_mi = 35.0
    trip._check_timezone()
    events = [e for e in trip._events if e.kind == TripEventKind.TIMEZONE_CROSSING]
    assert len(events) == 1
    # Noon on the Eastern reference clock is 11 AM Central: the new local
    # time is the whole announcement, with no clock-setting instruction.
    assert events[0].message == "Crossing into Central Time. It is now 11 AM."
    trip._check_timezone()
    assert len([e for e in trip._events if e.kind == TripEventKind.TIMEZONE_CROSSING]) == 1


def test_crossing_east_announces_the_eastern_clock():
    trip = _trip(Route(["B", "A"], [_tennessee_leg()]), start_hour=12.0)
    trip.position_mi = 45.0
    trip._check_timezone()
    events = [e for e in trip._events if e.kind == TripEventKind.TIMEZONE_CROSSING]
    assert len(events) == 1
    assert events[0].message == "Crossing into Eastern Time. It is now 12 PM."


def test_terse_speech_says_only_the_zone():
    from freight_fate.states.driving_core import timezone_crossing_message

    trip = _trip(Route(["A", "B"], [_tennessee_leg()]), start_hour=12.0)
    trip.position_mi = 35.0
    trip._check_timezone()
    event = next(e for e in trip._events if e.kind == TripEventKind.TIMEZONE_CROSSING)
    assert timezone_crossing_message(event, terse=True) == "Central Time."
    assert timezone_crossing_message(event, terse=False) == event.message


def test_local_hour_follows_the_truck_across_the_boundary():
    trip = _trip(Route(["A", "B"], [_tennessee_leg()]), start_hour=12.0)
    assert trip.local_hour == 12.0
    trip.position_mi = 35.0
    assert trip.local_hour == 11.0


def test_restore_past_the_boundary_does_not_reannounce(world):
    # restore() walks real corridor data, so use a real route: resuming a
    # save from beyond the boundary must adopt the zone silently.
    route = world.route_options("Atlanta", "Dallas")[0]
    trip = Trip(route, TruckState(), WeatherSystem("atlantic_southeast", seed=1), seed=2)
    first = next(c for c in trip.timezone_crossings if c.to_zone is CENTRAL)
    trip.restore(position_mi=first.at_mi + 5.0, game_minutes=120.0)
    trip._check_timezone()
    assert [e for e in trip._events if e.kind == TripEventKind.TIMEZONE_CROSSING] == []
    assert trip.current_timezone is CENTRAL


def test_boundary_zigzag_is_not_a_crossing():
    # A road that pokes over the line and comes back within the dwell window
    # (the I-84-on-the-Columbia lesson) must not move the clock at all.
    leg = Leg(
        "A",
        "B",
        60.0,
        "I-40",
        "hills",
        (),
        state_miles=(StateMileage("Tennessee", 60.0),),
        route_points=(
            RoutePoint(0.0, 35.96, -83.92),
            RoutePoint(25.0, 35.90, -85.60),  # briefly over the line
            RoutePoint(30.0, 35.90, -85.20),  # and straight back
            RoutePoint(60.0, 35.96, -84.50),
        ),
    )
    trip = _trip(Route(["A", "B"], [leg]))
    assert trip.timezone_crossings == []
    assert trip.destination_timezone is EASTERN


# --- destination-local deadlines --------------------------------------------------


def test_deadline_reads_in_the_destination_zone():
    trip = _trip(Route(["A", "B"], [_tennessee_leg()]), start_hour=12.0)
    assert trip.deadline_clock_text(10.0) == "9 PM Central Time"
    assert trip.deadline_clock_text(20.0) == "7 AM Central Time tomorrow"


def test_deadline_clock_is_anchored_at_trip_start():
    trip = _trip(Route(["A", "B"], [_tennessee_leg()]), start_hour=12.0)
    before = trip.deadline_clock_text(10.0)
    trip.game_minutes = 180.0  # three hours of driving later...
    assert trip.deadline_clock_text(10.0) == before  # ...the appointment holds


# --- real world data ---------------------------------------------------------------


def test_atlanta_to_dallas_crosses_into_central(world):
    route = world.route_options("Atlanta", "Dallas")[0]
    trip = Trip(route, TruckState(), WeatherSystem("atlantic_southeast", seed=1), seed=2)
    assert trip.start_timezone is EASTERN
    assert trip.destination_timezone is CENTRAL
    keys = [(c.from_zone.key, c.to_zone.key) for c in trip.timezone_crossings]
    assert ("eastern", "central") in keys


def test_dispatch_detail_quotes_the_local_appointment():
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState

    app = App()
    try:
        app.ctx.profile = Profile(name="Zones", current_city="Buffalo")
        jobs = JobBoard(app.ctx.world, seed=7).offers(
            "Buffalo", {"refrigerated", "heavy_haul", "high_value"}, level=5
        )
        board = JobBoardState(app.ctx, jobs)
        app.push_state(board)
        board.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1, mod=0, unicode=""))
        joined = " ".join(app.state.lines())
        assert "deliver by about" in joined
        assert "Time" in joined  # the zone is always named on the appointment
    finally:
        app.shutdown()
