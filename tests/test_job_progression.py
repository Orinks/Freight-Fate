"""Career-arc job generation: regional starts, growing caps, freight lanes."""

import pytest

from freight_fate.models.jobs import (
    FACILITY_CARGO,
    LEVEL_DISTANCE_CAPS,
    LONG_HAUL_MILES,
    JobBoard,
    minimum_pay_for_level,
)


@pytest.mark.parametrize("city", ["Atlanta", "Philadelphia", "Chicago"])
def test_level_one_offers_are_short_regional_hops(world, city):
    single = total = 0
    for seed in range(20):
        jobs = JobBoard(world, seed=seed).offers(city, set(), level=1)
        assert jobs
        for job in jobs:
            total += 1
            assert job.distance_mi <= LEVEL_DISTANCE_CAPS[1]
            route = world.shortest_route(job.origin, job.destination)
            single += len(route.legs) == 1
    # mostly direct hops to neighboring cities, never more than two legs
    assert single / total >= 0.55


def test_level_one_and_two_never_exceed_two_legs(world):
    for seed in range(10):
        for level in (1, 2):
            for job in JobBoard(world, seed=seed).offers("Atlanta", set(), level=level):
                route = world.shortest_route(job.origin, job.destination)
                assert len(route.legs) <= 2


def test_level_two_adds_regional_two_leg_work(world):
    # Atlanta's real-world-style board mixes airport cargo, industrial
    # district loads, and cold-chain freight. Level 2 should visibly expand
    # from neighboring-city rookie hops into nearby regional work.
    level_one_two_leg = level_two_two_leg = 0
    for seed in range(40):
        for job in JobBoard(world, seed=seed).offers("Atlanta", set(), level=1):
            route = world.shortest_route(job.origin, job.destination)
            level_one_two_leg += len(route.legs) == 2
        for job in JobBoard(world, seed=seed).offers("Atlanta", set(), level=2):
            route = world.shortest_route(job.origin, job.destination)
            level_two_two_leg += len(route.legs) == 2

    assert level_two_two_leg > level_one_two_leg


def test_distance_cap_rises_with_level(world):
    caps = [JobBoard.distance_cap(level) for level in range(1, 9)]
    assert caps == sorted(caps)
    assert caps[0] <= 300
    assert JobBoard.distance_cap(5) >= 1000

    # the cap is honored by actual offers
    for seed in range(10):
        for job in JobBoard(world, seed=seed).offers("Chicago", set(), level=5):
            assert job.distance_mi <= JobBoard.distance_cap(5)


def test_long_hauls_unlock_around_level_five(world):
    def longest(level: int) -> float:
        return max(job.distance_mi
                   for seed in range(30)
                   for job in JobBoard(world, seed=seed).offers(
                       "Los Angeles", set(), level=level))

    assert longest(1) < LONG_HAUL_MILES
    assert longest(5) >= LONG_HAUL_MILES


def test_destination_weighting_prefers_near_cities(world):
    # Milwaukee is 92 miles from Chicago; New York is ~880. Even at a high
    # level with everything in range, near cities must come up far more often.
    near = far = 0
    for seed in range(60):
        for job in JobBoard(world, seed=seed).offers("Chicago", set(), level=6):
            near += job.destination == "Milwaukee"
            far += job.destination == "New York"
    assert near > far


def test_remote_terminal_still_gets_a_full_board(world):
    # Salt Lake City's nearest neighbor is beyond the level-1 cap; the board
    # must fall back to the nearest cities instead of coming up empty.
    jobs = JobBoard(world, seed=7).offers("Salt Lake City", set(), level=1)
    assert jobs
    assert all(job.distance_mi <= 600 for job in jobs)


def test_short_hauls_still_pay_for_fuel(world):
    # ~6 mpg at roughly $4/gallon is ~$0.67 per mile; rookie jobs must clear
    # that with room for repairs and profit.
    for seed in range(10):
        for job in JobBoard(world, seed=seed).offers("Atlanta", set(), level=1):
            assert job.pay >= job.distance_mi * 1.5


def test_rookie_boards_have_rewarding_minimum_pay(world):
    for city in ["Chicago", "Atlanta", "Memphis", "San Antonio", "Los Angeles"]:
        for seed in range(15):
            for job in JobBoard(world, seed=seed).offers(city, set(), level=1):
                assert job.pay >= minimum_pay_for_level(job.distance_mi, 1)


def test_representative_boards_use_truck_plausible_locations(world):
    plausible_types = {
        "air_cargo",
        "food_terminal",
        "industrial_park",
        "intermodal",
        "port",
        "retail_distribution",
    }
    for city in ["Chicago", "Atlanta", "Memphis", "San Antonio", "Los Angeles"]:
        assert {loc.type for loc in world.cities[city].locations} <= plausible_types
        jobs = JobBoard(world, seed=3).offers(city, set(), level=2)
        assert jobs
        assert all(any(job.origin_location == loc.name for loc in world.cities[city].locations)
                   for job in jobs)


def test_facility_type_filters_available_cargo(world):
    for seed in range(40):
        jobs = JobBoard(world, seed=seed).offers(
            "Chicago", {"refrigerated", "heavy_haul", "high_value"}, level=4)
        for job in jobs:
            allowed = FACILITY_CARGO[job.origin_type]
            assert job.cargo.key in allowed


def test_jobs_carry_destination_facility_metadata(world):
    jobs = JobBoard(world, seed=8).offers(
        "Los Angeles", {"refrigerated", "heavy_haul", "high_value"}, level=5)
    assert jobs
    for job in jobs:
        assert job.destination_location
        assert job.destination_type
        assert job.destination_location in {
            loc.name for loc in world.cities[job.destination].locations
        }
        text = job.describe()
        assert job.origin_location in text
        assert job.destination_location in text


def test_representative_stops_are_real_world_grounded(world):
    expected = {
        ("Atlanta", "Birmingham"): "Talladega I-20 Travel Center",
        ("Memphis", "Little Rock"): "Forrest City I-40 Truck Stop",
        ("San Antonio", "Dallas"): "Waco I-35 Travel Plaza",
        ("Los Angeles", "San Diego"): "San Onofre Truck Parking",
    }
    for (start, end), stop_name in expected.items():
        route = world.shortest_route(start, end)
        assert stop_name in route.stops
