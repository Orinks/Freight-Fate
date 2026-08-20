"""Grounded congestion: HPMS volume against capacity on a commuter clock."""

import dataclasses

import pytest

from freight_fate.data.world_models import Leg, TrafficVolumeSample
from freight_fate.sim.season import day_of_week, is_weekend
from freight_fate.sim.trip import Trip
from freight_fate.sim.trip_models import (
    HOURLY_SHARE_WEEKDAY,
    HOURLY_SHARE_WEEKEND,
    URBAN_RADIUS_MI,
    congestion_limit_mph,
    congestion_ratio,
    heuristic_aadt,
    leg_aadt_at,
)
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherSystem


def _trip(world, start="Chicago", end="Indianapolis", **kwargs) -> Trip:
    route = world.route_options(start, end)[0]
    truck = TruckState()
    truck.transmission.automatic = True
    return Trip(route, truck, WeatherSystem("great_lakes", seed=1), seed=2, **kwargs)


def _synthetic_trip(world, **kwargs) -> Trip:
    """A trip whose first leg carries a known HPMS profile: a genuinely
    overloaded metro stretch for the first dozen miles, light rural volume
    beyond. Independent of whatever the checked-in bake contains."""
    from freight_fate.data.world_models import Route

    cached = world.route_options("Chicago", "Indianapolis")[0]
    samples = (
        TrafficVolumeSample(at_mi=0.0, aadt=150000.0, lanes=3),
        TrafficVolumeSample(at_mi=12.0, aadt=22000.0, lanes=2),
    )
    leg = dataclasses.replace(cached.legs[0], traffic_volumes=samples)
    route = Route(cities=list(cached.cities), legs=[leg] + list(cached.legs[1:]))
    truck = TruckState()
    truck.transmission.automatic = True
    return Trip(route, truck, WeatherSystem("great_lakes", seed=1), seed=2, **kwargs)


# -- The commuter curve and capacity math -------------------------------------------


def test_hourly_shares_cover_a_full_day():
    assert len(HOURLY_SHARE_WEEKDAY) == 24
    assert len(HOURLY_SHARE_WEEKEND) == 24
    assert sum(HOURLY_SHARE_WEEKDAY) == pytest.approx(1.0, abs=0.02)
    assert sum(HOURLY_SHARE_WEEKEND) == pytest.approx(1.0, abs=0.02)
    # Weekday twin peaks; weekend has no AM commute spike.
    assert HOURLY_SHARE_WEEKDAY[7] > HOURLY_SHARE_WEEKDAY[11]
    assert HOURLY_SHARE_WEEKDAY[17] == max(HOURLY_SHARE_WEEKDAY)
    assert HOURLY_SHARE_WEEKEND[7] < HOURLY_SHARE_WEEKDAY[7] / 2.0


def test_urban_volumes_jam_at_rush_hour_and_rural_ones_do_not():
    urban = heuristic_aadt("I-90", near_city=True)
    rural = heuristic_aadt("I-90", near_city=False)
    assert congestion_ratio(urban, 17.0, 2, weekend=False) > 0.9
    assert congestion_ratio(urban, 3.0, 2, weekend=False) < 0.2
    assert congestion_ratio(rural, 17.0, 2, weekend=False) < 0.5
    # The same demand over more lanes flows better.
    assert congestion_ratio(urban, 17.0, 4, weekend=False) < congestion_ratio(
        urban, 17.0, 2, weekend=False
    )


def test_congestion_limit_buckets():
    assert congestion_limit_mph(0.5, 70.0) is None
    assert congestion_limit_mph(0.8, 70.0) == pytest.approx(58.0)
    assert congestion_limit_mph(0.95, 70.0) == pytest.approx(38.0)
    assert congestion_limit_mph(1.2, 70.0) == pytest.approx(26.0)


# -- The career calendar knows its weekdays ------------------------------------------


def test_career_clock_weekdays():
    # Careers start Wednesday, March 21, 2001.
    assert day_of_week(0.0) == 2
    assert not is_weekend(0.0)
    assert day_of_week(3 * 24.0) == 5  # Saturday
    assert is_weekend(3 * 24.0)
    assert is_weekend(4 * 24.0)  # Sunday
    assert not is_weekend(5 * 24.0)  # Monday


# -- Placement: prone stretches sit at the metros ------------------------------------


def test_congestion_zones_sit_on_the_overloaded_stretch(world):
    trip = _synthetic_trip(world)
    jams = [z for z in trip.zones if z.reason == "heavy traffic"]
    assert jams, "an overloaded metro stretch should be congestion-prone"
    zone = jams[0]
    assert zone.aadt is not None and zone.aadt >= 100000.0
    assert zone.start_mi <= 1.0  # covers the loaded miles...
    assert zone.end_mi <= 12.0 + URBAN_RADIUS_MI  # ...not the rural ones
    # The light rural remainder of the leg spawns no jam.
    assert all(z.end_mi <= 20.0 for z in jams)


def test_weekend_mornings_do_not_jam(world):
    # Saturday (career day 3) at the 7 AM weekday peak hour.
    weekday = _synthetic_trip(world, start_hour=7.0, career_hours=0.0)
    weekend = _synthetic_trip(world, start_hour=7.0, career_hours=3 * 24.0)
    weekday_jam = [z for z in weekday.zones if z.reason == "heavy traffic"][0]
    weekend_jam = [z for z in weekend.zones if z.reason == "heavy traffic"][0]
    assert weekday._zone_is_active(weekday_jam)
    assert not weekend._zone_is_active(weekend_jam)


def test_active_jam_sets_the_prevailing_speed(world):
    trip = _synthetic_trip(world, start_hour=17.0)
    jam = [z for z in trip.zones if z.reason == "heavy traffic"][0]
    assert trip._zone_is_active(jam)
    limit, reason = trip.speed_limit_at((jam.start_mi + jam.end_mi) / 2.0)
    assert reason == "heavy traffic"
    assert limit < 55.0
    # The same spot at 3 AM is open road at the corridor limit.
    night = _synthetic_trip(world, start_hour=3.0)
    night_limit, night_reason = night.speed_limit_at((jam.start_mi + jam.end_mi) / 2.0)
    assert night_reason != "heavy traffic"
    assert night_limit > limit


def test_jam_traffic_settles_at_the_zone_speed_not_the_generic_floor(world):
    """Brandon, 2026-08-20: a heavy-traffic zone posting 45 dropped the truck
    to 25 and held it there. The injected braking lead -- which never takes
    an exit -- ratcheted down to the manager's generic 45-percent-of-posted
    floor (25 on that 55 corridor), well under the zone's own prevailing
    speed, and the speed keeper followed it for the rest of the zone with
    no visible lead to blame. Braking traffic in a zone settles at the
    zone's number, so the keeper's target does too."""
    # 1 PM puts the synthetic jam in the light band: prevailing exactly 45.
    trip = _synthetic_trip(world, start_hour=13.0)
    jam = [z for z in trip.zones if z.reason == "heavy traffic"][0]
    assert trip._zone_is_active(jam)
    assert jam.limit_mph == pytest.approx(45.0)
    manager = trip.traffic_manager
    manager.vehicles = []
    manager.rolling_bubble = False
    trip.position_mi = jam.start_mi + 0.1
    trip._check_zones()  # entering the live jam injects the queue
    lead = next(
        v for v in manager.vehicles if v.key.startswith("congestion:") and v.intent == "braking"
    )
    # The trap this pins: the generic floor sits under the zone's number.
    floor = manager._floor_speed(manager._posted_limit_at(lead.position_mi))
    assert floor < jam.limit_mph
    trip.update(0.01)  # publishes the braking zones, pace included
    # Ride just behind the lead long enough for the old ratchet to have
    # reached its floor; time_scale zero freezes positions so the gap holds.
    for _ in range(8):
        manager.update(dt=1.0, position_mi=lead.position_mi - 0.5, time_scale=0.0)
    assert lead.target_speed_mph == pytest.approx(jam.limit_mph)


def test_entering_a_live_jam_fills_it_with_slow_traffic(world):
    trip = _synthetic_trip(world, start_hour=17.0)
    jam = [z for z in trip.zones if z.reason == "heavy traffic"][0]
    trip.traffic_manager.vehicles = []
    trip.position_mi = jam.start_mi + 0.1
    trip._check_zones()
    injected = [v for v in trip.traffic_manager.vehicles if v.key.startswith("congestion:")]
    assert len(injected) >= 3
    assert {v.lane for v in injected} == {0, 1}  # both lanes are full of metal
    assert all(v.speed_mph <= jam.limit_mph + 5.0 for v in injected)
    # Re-entering does not stack duplicates.
    trip._active_zone = None
    trip._check_zones()
    again = [v for v in trip.traffic_manager.vehicles if v.key.startswith("congestion:")]
    assert len(again) == len(injected)


# -- Baked HPMS profiles override the heuristic ---------------------------------------


def test_baked_leg_profile_wins_over_the_heuristic(world):
    from freight_fate.data.world_models import Route

    cached = world.route_options("Chicago", "Indianapolis")[0]
    samples = (
        TrafficVolumeSample(at_mi=0.0, aadt=150000.0, lanes=4),
        TrafficVolumeSample(at_mi=60.0, aadt=18000.0, lanes=2),
    )
    leg = dataclasses.replace(cached.legs[0], traffic_volumes=samples)
    assert leg_aadt_at(leg, 10.0) == (150000.0, 4)
    assert leg_aadt_at(leg, 90.0) == (18000.0, 2)

    route = Route(cities=list(cached.cities), legs=[leg] + list(cached.legs[1:]))
    truck = TruckState()
    truck.transmission.automatic = True
    trip = Trip(route, truck, WeatherSystem("great_lakes", seed=1), seed=2)
    aadt, lanes = trip._route_aadt_at(10.0)
    assert (aadt, lanes) == (150000.0, 4)


def test_unbaked_leg_reads_none():
    leg = Leg("A", "B", 100.0, "I-99", "flat", ())
    assert leg_aadt_at(leg, 10.0) is None


def test_traffic_volume_parser_orders_and_validates():
    from freight_fate.data.world_parsing import _parse_traffic_volumes

    parsed = _parse_traffic_volumes(
        [
            {"at_mi": 50.0, "aadt": 20000, "lanes": 2},
            {"at_mi": 0.0, "aadt": 90000, "lanes": 3},
        ],
        100.0,
        "A",
        "B",
    )
    assert [s.at_mi for s in parsed] == [0.0, 50.0]
    assert parsed[1].aadt == 20000
    with pytest.raises(ValueError):
        _parse_traffic_volumes([{"at_mi": 1.0}], 100.0, "A", "B")


def test_baked_lanes_feed_the_lane_count():
    from freight_fate.sim.trip_models import leg_lane_count

    unbaked = Leg("A", "B", 100.0, "I-99", "flat", ())
    assert leg_lane_count(unbaked) == 2
    baked = dataclasses.replace(unbaked, lanes=3)
    assert leg_lane_count(baked) == 3
