"""Career-arc job generation: regional starts, growing caps, freight lanes."""

import pytest

from freight_fate.models.jobs import (
    FACILITY_CARGO,
    LEVEL_DISTANCE_CAPS,
    LONG_HAUL_MILES,
    MIN_JOB_DISTANCE_MI,
    JobBoard,
    minimum_pay_for_level,
)


@pytest.mark.parametrize("city", ["Atlanta", "Philadelphia", "Chicago"])
def test_level_one_offers_are_short_regional_hops(world, city):
    # Rookie reach is gated by the distance cap and proximity weighting, not by
    # leg count: jobs stay regional and lean short, but the board offers variety
    # (it is no longer locked to one back-and-forth destination).
    cap = LEVEL_DISTANCE_CAPS[1]
    near = total = 0
    destinations: set[str] = set()
    for seed in range(20):
        jobs = JobBoard(world, seed=seed).offers(city, set(), level=1)
        assert jobs
        for job in jobs:
            total += 1
            assert job.distance_mi <= cap  # within the regional cap
            near += job.distance_mi <= cap * 0.6  # proximity favors near cities
            destinations.add(job.destination)
    assert near / total >= 0.5  # predominantly short hauls
    assert len(destinations) >= 3  # variety, not one repeated route


def test_level_one_and_two_stay_within_the_regional_cap(world):
    # The distance cap keeps rookie work regional; leg count no longer gates it.
    for seed in range(10):
        for level in (1, 2):
            cap = LEVEL_DISTANCE_CAPS[level]
            for job in JobBoard(world, seed=seed).offers("Atlanta", set(), level=level):
                route = world.supported_route(job.origin, job.destination)
                assert route is not None
                assert job.distance_mi <= cap


def test_higher_level_reaches_farther_destinations(world):
    # Level 2's larger cap lets it take jobs to cities level 1 cannot reach.
    def max_distance(level: int) -> float:
        return max(
            job.distance_mi
            for seed in range(40)
            for job in JobBoard(world, seed=seed).offers("Milwaukee", set(), level=level)
        )

    assert max_distance(2) > max_distance(1)


def test_bobtail_relocates_to_a_nearby_city_without_pay():
    from freight_fate.app import App
    from freight_fate.models.jobs import make_reposition_job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import ArrivalState, DrivingState

    app = App()
    try:
        app.ctx.profile = Profile(name="Bobtail")
        p = app.ctx.profile
        p.current_city = "Denver"
        money_before = p.money
        job = make_reposition_job(app.ctx.world, "Denver", "Cheyenne")
        assert job is not None and job.bobtail and job.pay == 0.0
        route = app.ctx.world.supported_route("Denver", "Cheyenne")
        driving = DrivingState(app.ctx, job, route)
        driving.trip.game_minutes = 120.0
        # a bobtail run survives save/resume as a bobtail run
        assert DrivingState.from_snapshot(app.ctx, driving.snapshot()).job.bobtail

        # Push the state so enter() runs -- this is the path that crashed when
        # the bobtail settle left _announcements unset and summary_lines empty.
        app.ctx.push_state(ArrivalState(app.ctx, driving))
        arrival = app.state

        assert p.current_city == "cheyenne_wy_us"  # relocated to the new hub
        assert p.money == money_before  # no pay for an empty run
        assert p.career.deliveries == 0  # not counted as a delivery
        # The repositioned arrival screen carries its summary.
        assert arrival.summary_lines
        assert any("Cheyenne" in line for line in arrival.summary_lines)
    finally:
        app.shutdown()


def test_bobtail_personal_conveyance_records_off_duty_hos_time():
    from freight_fate.app import App
    from freight_fate.models.jobs import make_reposition_job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        app.ctx.profile = Profile(name="Bobtail HOS", current_city="Denver")
        job = make_reposition_job(app.ctx.world, "Denver", "Cheyenne")
        assert job is not None and job.bobtail
        route = app.ctx.world.supported_route("Denver", "Cheyenne")
        driving = DrivingState(app.ctx, job, route)
        driving.truck.velocity_mps = 20.0

        driving._update_hours_and_fatigue(60.0)

        assert driving.hos.status == "off_duty"
        assert driving.hos.driving_min == 0.0
        assert driving.hos.off_duty_min > 0.0
    finally:
        app.shutdown()


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
        return max(
            job.distance_mi
            for seed in range(30)
            for job in JobBoard(world, seed=seed).offers("Phoenix", set(), level=level)
        )

    assert longest(1) < LONG_HAUL_MILES
    assert longest(5) >= LONG_HAUL_MILES


def test_destination_weighting_prefers_near_cities(world):
    # Milwaukee is 92 miles from Chicago; New York is ~880. Even at a high
    # level with everything in range, near cities must come up far more often.
    near = far = 0
    for seed in range(60):
        for job in JobBoard(world, seed=seed).offers("Chicago", set(), level=6):
            near += job.destination == "milwaukee_wi_us"
            far += job.destination == "new_york_ny_us"
    assert near > far


def test_board_never_offers_a_haul_below_the_minimum(world):
    # Cities stand for whole freight areas, so trivial across-town hops are not
    # offered as dispatches, no matter how close two cities sit on the map.
    for city in ["New York", "Philadelphia", "Los Angeles", "Dallas", "Norfolk"]:
        for seed in range(20):
            for level in (1, 6):
                for job in JobBoard(world, seed=seed).offers(city, set(), level=level):
                    assert job.distance_mi >= MIN_JOB_DISTANCE_MI, (
                        f"{job.origin} -> {job.destination} is only {job.distance_mi:.0f} mi"
                    )


@pytest.mark.parametrize(
    ("city", "too_close"),
    [
        ("Norfolk", "Virginia Beach"),  # 18 mi
        ("Bridgeport", "New Haven"),  # 21 mi
    ],
)
def test_close_neighbors_are_not_dispatched(world, city, too_close):
    # The nearest neighbor sits under the minimum, so it must never be offered,
    # yet the board still fills from farther destinations.
    for seed in range(30):
        jobs = JobBoard(world, seed=seed).offers(city, set(), level=1)
        assert jobs
        assert all(job.destination != too_close for job in jobs)


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
    for city in ["Chicago", "Atlanta", "Philadelphia", "San Antonio", "Los Angeles"]:
        for seed in range(15):
            for job in JobBoard(world, seed=seed).offers(city, set(), level=1):
                # pay is rounded to cents, so compare against the floor to cents
                assert job.pay >= round(minimum_pay_for_level(job.distance_mi, 1), 2)


def test_long_haul_boards_have_rewarding_minimum_pay(world):
    endorsements = {"refrigerated", "heavy_haul", "high_value"}
    long_jobs = [
        job
        for city in ["Chicago", "Atlanta", "Dallas", "Los Angeles"]
        for seed in range(30)
        for job in JobBoard(world, seed=seed).offers(city, endorsements, level=5)
        if job.distance_mi >= 600
    ]

    assert long_jobs
    for job in long_jobs:
        assert job.pay / job.distance_mi >= 5.25


def test_representative_boards_use_truck_plausible_locations(world):
    for city in ["Chicago", "Atlanta", "Philadelphia", "San Antonio", "Los Angeles"]:
        jobs = JobBoard(world, seed=3).offers(city, set(), level=2)
        assert jobs
        assert all(
            any(job.origin_location == loc.name for loc in world.city(city).locations)
            for job in jobs
        )
        assert all(job.origin_facility_id for job in jobs)


def test_facility_type_filters_available_cargo(world):
    for seed in range(40):
        jobs = JobBoard(world, seed=seed).offers(
            "Chicago", {"refrigerated", "heavy_haul", "high_value"}, level=4
        )
        for job in jobs:
            allowed = FACILITY_CARGO[job.origin_type]
            assert job.cargo.key in allowed


def test_jobs_match_shipper_and_receiver_roles(world):
    for city in ["Chicago", "Fresno", "Houston", "Memphis", "Detroit"]:
        for seed in range(12):
            jobs = JobBoard(world, seed=seed).offers(
                city, {"refrigerated", "heavy_haul", "high_value"}, level=5
            )
            assert jobs
            for job in jobs:
                origin = world.facility_location(job.origin, job.origin_facility_id)
                destination = world.facility_location(job.destination, job.destination_facility_id)
                assert job.cargo.key in origin.ships
                assert job.cargo.key in destination.receives
                assert origin.name in job.describe()
                assert destination.name in job.describe()


def test_regional_specialization_shapes_generated_freight(world):
    chicago_cargo = {
        job.cargo.key
        for seed in range(25)
        for job in JobBoard(world, seed=seed).offers(
            "Chicago", {"refrigerated", "heavy_haul", "high_value"}, level=5
        )
    }
    fresno_cargo = {
        job.cargo.key
        for seed in range(25)
        for job in JobBoard(world, seed=seed).offers(
            "Fresno", {"refrigerated", "heavy_haul", "high_value"}, level=5
        )
    }
    houston_types = {
        job.origin_type
        for seed in range(25)
        for job in JobBoard(world, seed=seed).offers(
            "Houston", {"refrigerated", "heavy_haul", "high_value"}, level=5
        )
    }

    assert {"container", "parcel"} & chicago_cargo
    assert {"grain", "food", "refrigerated"} & fresno_cargo
    assert "chemical_petroleum_terminal" in houston_types


def test_higher_levels_unlock_more_facility_and_cargo_variety(world):
    low_jobs = [
        job
        for seed in range(20)
        for job in JobBoard(world, seed=seed).offers("Chicago", set(), level=1)
    ]
    high_jobs = [
        job
        for seed in range(20)
        for job in JobBoard(world, seed=seed).offers(
            "Chicago", {"refrigerated", "heavy_haul", "high_value"}, level=5
        )
    ]

    assert low_jobs and high_jobs
    assert len({job.cargo.key for job in high_jobs}) > len({job.cargo.key for job in low_jobs})
    assert len({job.origin_type for job in high_jobs}) > len({job.origin_type for job in low_jobs})
    assert any(job.cargo.min_level > 1 or job.cargo.endorsement for job in high_jobs)


def test_jobs_carry_destination_facility_metadata(world):
    jobs = JobBoard(world, seed=8).offers(
        "Los Angeles", {"refrigerated", "heavy_haul", "high_value"}, level=5
    )
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


def test_job_offer_avoids_repeating_facility_type_in_generated_names():
    from freight_fate.models.jobs import CARGO_CATALOG, Job

    job = Job(
        CARGO_CATALOG["general"],
        12.0,
        "South Bend",
        "South Bend Grocery Distribution Center",
        "Fort Wayne",
        85.0,
        833.0,
        4.0,
        origin_type="grocery_retail_dc",
        destination_location="Fort Wayne Dry Warehouse",
        destination_type="dry_warehouse",
    )

    text = job.describe(1, 5)

    assert "from South Bend Grocery Distribution Center in South Bend" in text
    assert "to Fort Wayne Dry Warehouse in Fort Wayne" in text
    assert "grocery and retail distribution center South Bend" not in text
    assert "dry warehouse Fort Wayne Dry Warehouse" not in text


def test_representative_stops_are_real_world_grounded(world):
    expected = {
        ("Atlanta", "Birmingham"): "Pilot Travel Center Lincoln",
        ("Memphis", "Little Rock"): "Forrest City I-40 Rest Area",
        ("San Antonio", "Dallas"): "Road Ranger Waco",
        ("Los Angeles", "San Diego"): "San Onofre Safety Roadside Rest Area",
        ("Des Moines", "Chicago"): "Iowa 80 Truckstop",
        ("Houston", "Dallas"): "Pilot Travel Center Huntsville",
        ("Los Angeles", "Fresno"): "Pilot Travel Center Bakersfield",
        ("Fresno", "Sacramento"): "Flying J Travel Center Ripon",
    }
    for (start, end), stop_name in expected.items():
        route = world.shortest_route(start, end)
        assert stop_name in route.stops


def test_new_dispatches_only_use_metadata_supported_routes(world):
    for city in ["Chicago", "Atlanta", "Philadelphia", "San Antonio", "Los Angeles"]:
        for seed in range(12):
            for job in JobBoard(world, seed=seed).offers(city, set(), level=6):
                route = world.supported_route(job.origin, job.destination)
                assert route is not None
                assert route.metadata_complete(world)


# Sweeping every city's board grows with the map and, under coverage tracing
# on the slower Windows CI runner, straddles the default 120-second hang
# timeout. It is long, not hung, so give it real headroom.
@pytest.mark.timeout(300)
# Scans every city x 4 seeds, so its runtime scales with the (now much larger)
# map -- ~50s locally, which tips past the default 120s cap on slower CI runners.
# The work is legitimate coverage, not a hang, so give it generous headroom.
@pytest.mark.timeout(300)
def test_whole_board_never_offers_unsupported_route_legs(world):
    endorsements = {"refrigerated", "heavy_haul", "high_value"}
    routes = {}
    for city in world.city_names():
        for seed in range(4):
            jobs = JobBoard(world, seed=seed).offers(city, endorsements, level=6)
            for job in jobs:
                key = (job.origin, job.destination)
                route = routes.get(key)
                if route is None:
                    route = world.supported_route(job.origin, job.destination)
                    routes[key] = route
                assert route is not None, f"{job.origin} to {job.destination}"
                assert route.metadata_complete(world), f"{job.origin} to {job.destination}"
                assert all(world.leg_metadata_complete(leg) for leg in route.legs)
                assert all(stop.curated for stop in route.stop_details)


def test_former_legacy_routes_are_now_metadata_supported_for_dispatch(world):
    route = world.supported_route("Chicago", "St. Louis")
    assert route is not None
    assert route.metadata_complete(world)
    jobs = JobBoard(world, seed=9).offers("Chicago", set(), level=6)
    assert jobs
    assert all(world.supported_route(job.origin, job.destination) is not None for job in jobs)


def test_former_placeholder_only_routes_are_metadata_supported(world):
    route = world.supported_route("Memphis", "Nashville")
    assert route is not None
    assert route.metadata_complete(world)
    assert all(stop.curated for stop in route.stop_details)

    supported = world.supported_route("Memphis", "Little Rock")
    assert supported is not None
    assert supported.metadata_complete(world)

    jobs = JobBoard(world, seed=4).offers("Memphis", set(), level=1)
    assert jobs
    assert all(world.supported_route(job.origin, job.destination) is not None for job in jobs)
