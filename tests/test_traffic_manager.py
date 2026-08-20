"""Traffic bubble manager tests."""

from enforcement_helpers import always_observing_post

from freight_fate.data.world import get_world
from freight_fate.sim.traffic_manager import TrafficManager, TrafficVehicle
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherKind, WeatherSystem


def _ramp_miles(manager) -> list[float]:
    """Route miles just past each on-ramp -- where a merge can come from."""
    out: list[float] = []
    for start, leg in zip(manager.leg_starts, manager.route.legs, strict=False):
        for interchange in getattr(leg, "interchanges", ()) or ():
            at = getattr(interchange, "at_mi", None)
            if at is not None:
                out.append(start + at + 0.1)
    return sorted(out)


def _manager(seed: int = 1) -> TrafficManager:
    world = get_world()
    route = world.route_from_cities(["Chicago", "Indianapolis"])
    assert route is not None
    return _manager_for_route(route, seed=seed)


def _manager_for_route(route, seed: int = 1) -> TrafficManager:
    truck = TruckState()
    weather = WeatherSystem("great_lakes", seed=1)
    leg_starts = []
    at_mi = 0.0
    for leg in route.legs:
        leg_starts.append(at_mi)
        at_mi += leg.miles
    return TrafficManager(
        route=route,
        truck=truck,
        weather=weather,
        leg_starts=leg_starts,
        seed=seed,
        start_hour=8.0,
        hazard_scale=1.0,
        imperial=True,
    )


def test_traffic_vehicle_keeps_npc_compatibility_properties():
    vehicle = TrafficVehicle(
        key="traffic:test",
        position_mi=12.5,
        speed_mph=44.0,
        target_speed_mph=40.0,
        relative_lane=1,
        intent="merging",
        vehicle_class="car",
    )

    assert vehicle.at_mi == 12.5
    assert vehicle.end_mi > vehicle.at_mi
    assert vehicle.lane_text == "right lane"
    assert vehicle.behavior == "merging_vehicle"
    assert vehicle.reason == "merging traffic"


def test_state_trooper_vehicle_has_clear_status_reason():
    vehicle = TrafficVehicle(
        key="trooper:test",
        position_mi=12.5,
        speed_mph=62.0,
        target_speed_mph=62.0,
        relative_lane=0,
        intent="cruising",
        vehicle_class="state trooper",
    )

    assert vehicle.reason == "state trooper ahead"


def test_traffic_vehicle_maps_new_intents_to_legacy_behavior_and_reason():
    expected = {
        "cruising": ("steady_truck", "steady truck traffic"),
        "following": ("slow_car", "slow car ahead"),
        "merging": ("merging_vehicle", "merging traffic"),
        "braking": ("braking_traffic", "brake lights ahead"),
        "passing": ("passing_vehicle", "passing traffic"),
    }

    for intent, (behavior, reason) in expected.items():
        vehicle = TrafficVehicle(
            key=f"traffic:{intent}",
            position_mi=10.0,
            speed_mph=45.0,
            target_speed_mph=45.0,
            relative_lane=0,
            intent=intent,
            vehicle_class="car",
        )

        assert vehicle.behavior == behavior
        assert vehicle.reason == reason


def test_lead_vehicle_selects_nearest_vehicle_in_player_lane():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("left", 5.1, 55.0, 55.0, -1, "passing", "car", lane=1),
        TrafficVehicle("far", 6.0, 45.0, 45.0, 0, "following", "semi"),
        TrafficVehicle("near", 5.3, 42.0, 42.0, 0, "braking", "car"),
    ]

    context = manager.lead_vehicle(position_mi=5.0, truck_speed_mph=60.0)

    assert context is not None
    assert context.lead.key == "near"
    assert context.closing_mph == 18.0


def test_lead_vehicle_follows_the_player_into_the_left_lane():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("left", 5.1, 55.0, 55.0, -1, "passing", "car", lane=1),
        TrafficVehicle("right", 5.3, 42.0, 42.0, 0, "braking", "car"),
    ]

    manager.player_lane = 1
    context = manager.lead_vehicle(position_mi=5.0, truck_speed_mph=60.0)

    assert context is not None
    assert context.lead.key == "left"


def test_lead_vehicle_ignores_the_origin_lane_mid_change():
    """A lane change underway (``player_lane_target`` set) reasons about the
    lane being entered, not the one being left -- otherwise a lead in the
    origin lane keeps capping cruise for the whole maneuver."""
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("origin", 5.3, 42.0, 42.0, 0, "braking", "car"),
    ]

    manager.player_lane = 0
    manager.player_lane_target = 1  # changing into the left lane
    context = manager.lead_vehicle(position_mi=5.0, truck_speed_mph=60.0)

    assert context is None


def test_lead_vehicle_finds_a_lead_already_in_the_destination_lane():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("origin", 5.3, 42.0, 42.0, 0, "braking", "car"),
        TrafficVehicle("dest", 5.4, 40.0, 40.0, -1, "braking", "car", lane=1),
    ]

    manager.player_lane = 0
    manager.player_lane_target = 1
    context = manager.lead_vehicle(position_mi=5.0, truck_speed_mph=60.0)

    assert context is not None
    assert context.lead.key == "dest"


def test_lead_vehicle_reverts_to_origin_lane_once_the_change_target_clears():
    """No latching: once the lane layer stops reporting a change (an abort,
    or completion handled by ``player_lane`` itself), lead selection is back
    to the origin lane immediately."""
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("origin", 5.3, 42.0, 42.0, 0, "braking", "car"),
    ]

    manager.player_lane = 0
    manager.player_lane_target = 1
    assert manager.lead_vehicle(position_mi=5.0, truck_speed_mph=60.0) is None

    manager.player_lane_target = None  # aborted
    context = manager.lead_vehicle(position_mi=5.0, truck_speed_mph=60.0)

    assert context is not None
    assert context.lead.key == "origin"


def test_lead_vehicle_keeps_overlapping_vehicle_in_player_lane():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("overlap", 4.9, 20.0, 20.0, 0, "braking", "semi"),
    ]

    context = manager.lead_vehicle(position_mi=5.0, truck_speed_mph=10.0)

    assert context is not None
    assert context.lead.key == "overlap"
    assert context.gap_mi == 0.0


def test_update_moves_and_prunes_vehicles_outside_bubble():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("behind", -3.0, 55.0, 55.0, 0, "cruising", "semi"),
        TrafficVehicle("ahead", 2.0, 55.0, 55.0, 0, "cruising", "semi"),
    ]

    manager.update(dt=1.0, position_mi=0.0, time_scale=20.0)

    # Only the two seeded here are the subject; the rolling bubble also tops
    # the window up around the truck, and that is a different test's business.
    seeded = {v.key: v for v in manager.vehicles if v.key in ("behind", "ahead")}
    assert list(seeded) == ["ahead"]
    assert seeded["ahead"].position_mi > 2.2


def test_update_keeps_future_route_traffic_until_reached():
    world = get_world()
    route = world.supported_route("Seattle", "New York")
    assert route is not None
    manager = _manager_for_route(route, seed=7)
    manager.spawn_initial_traffic()
    initial_keys = {vehicle.key for vehicle in manager.vehicles}

    manager.update(dt=0.0, position_mi=0.0, time_scale=20.0)

    # Nothing seeded up the route may be dropped for being far away. The
    # bubble adds vehicles near the truck, so count the survivors by key
    # rather than the total, which now legitimately grows.
    survivors = {vehicle.key for vehicle in manager.vehicles}
    assert len(initial_keys) > 1
    assert initial_keys <= survivors
    assert any(vehicle.position_mi > 10.0 for vehicle in manager.vehicles)


def test_roving_posts_add_state_trooper_traffic():
    manager = _manager()
    manager.vehicles = [TrafficVehicle("traffic:existing", 2.0, 55.0, 55.0, 0, "cruising", "semi")]
    posts = [
        always_observing_post(at_mi=10.0, kind="roving_patrol"),
        always_observing_post(at_mi=22.0, kind="roving_patrol"),
        # Parked kinds belong to the enforcement cues, not the traffic bubble:
        # spawning a "cruising" vehicle for a median crossover is what used to
        # put phantom troopers into the lead-vehicle lookups.
        always_observing_post(at_mi=30.0, kind="median_post"),
    ]

    manager.add_enforcement_traffic(posts)
    manager.add_enforcement_traffic(posts)

    troopers = [vehicle for vehicle in manager.vehicles if vehicle.vehicle_class == "state trooper"]
    assert len(troopers) == 2
    assert [vehicle.position_mi for vehicle in manager.vehicles] == sorted(
        vehicle.position_mi for vehicle in manager.vehicles
    )
    assert all(vehicle.relative_lane == 0 for vehicle in troopers)


def test_merging_vehicle_moves_into_player_lane_and_creates_situation():
    manager = _manager()
    manager.vehicles = [TrafficVehicle("merge", 0.8, 42.0, 42.0, 1, "merging", "car")]

    manager.update(dt=0.0, position_mi=0.0, time_scale=20.0)
    situation = manager.next_situation(position_mi=0.0, truck_speed_mph=55.0)

    merging = next(v for v in manager.vehicles if v.key == "merge")
    assert merging.relative_lane == 0
    assert situation is not None
    assert situation.kind == "merging"
    assert "Merging" in situation.message


def test_braking_vehicle_slows_and_creates_lead_situation():
    manager = _manager()
    manager.vehicles = [TrafficVehicle("brake", 0.7, 45.0, 45.0, 0, "braking", "car")]

    manager.update(dt=1.0, position_mi=0.0, time_scale=20.0)
    situation = manager.next_situation(position_mi=0.0, truck_speed_mph=60.0)

    braking = next(v for v in manager.vehicles if v.key == "brake")
    assert braking.target_speed_mph < 45.0
    assert situation is not None
    assert situation.kind == "braking"
    assert "Brake lights" in situation.message


def test_braking_vehicle_in_a_zone_paces_the_zone_speed():
    """Inside a handed-over zone, braking traffic settles at the zone's own
    prevailing speed instead of ratcheting to the generic 45-percent-of-posted
    floor -- which sat at 25 on a 55 corridor whose heavy-traffic zone posted
    45, and parked the speed keeper there (Brandon, 2026-08-20)."""
    manager = _manager()
    manager.rolling_bubble = False
    manager._braking_zones = ((4.0, 8.0, "heavy traffic", 45.0),)
    manager.vehicles = [TrafficVehicle("brake", 5.5, 49.0, 49.0, 0, "braking", "car")]

    for _ in range(8):
        manager.update(dt=1.0, position_mi=5.0, time_scale=0.0)

    braking = manager.vehicles[0]
    assert braking.target_speed_mph == 45.0
    # Outside any zone the old floor still governs: the merge-window case.
    manager._braking_zones = ()
    for _ in range(8):
        manager.update(dt=1.0, position_mi=5.0, time_scale=0.0)
    floor = manager._floor_speed(manager._posted_limit_at(5.5))
    assert braking.target_speed_mph == floor


def test_next_situation_only_announces_vehicle_once():
    manager = _manager()
    manager.vehicles = [TrafficVehicle("lead", 0.7, 42.0, 42.0, 0, "following", "semi")]

    first = manager.next_situation(position_mi=0.0, truck_speed_mph=55.0)
    second = manager.next_situation(position_mi=0.0, truck_speed_mph=55.0)

    assert first is not None
    assert first.kind == "following"
    assert second is None


def test_next_situation_speaks_speed_units():
    manager = _manager()
    manager.vehicles = [TrafficVehicle("lead", 0.7, 42.0, 42.0, 0, "following", "semi")]

    situation = manager.next_situation(position_mi=0.0, truck_speed_mph=55.0)

    assert situation is not None
    assert "42 miles per hour" in situation.message


def test_manager_copies_leg_starts():
    world = get_world()
    route = world.route_from_cities(["Chicago", "Indianapolis"])
    leg_starts = [0.0]
    manager = TrafficManager(
        route=route,
        truck=TruckState(),
        weather=WeatherSystem("great_lakes", seed=1),
        leg_starts=leg_starts,
        seed=1,
        start_hour=8.0,
        hazard_scale=1.0,
        imperial=True,
    )

    leg_starts.append(12.0)

    assert manager.leg_starts == [0.0]


def _signature(manager: TrafficManager) -> list[tuple[float, float, int, str, str]]:
    return [
        (
            round(vehicle.position_mi, 2),
            round(vehicle.speed_mph, 1),
            vehicle.relative_lane,
            vehicle.intent,
            vehicle.vehicle_class,
        )
        for vehicle in manager.vehicles
    ]


def _placement_signature(manager: TrafficManager) -> list[tuple[float, int, str, str]]:
    return [
        (
            round(vehicle.position_mi, 2),
            vehicle.relative_lane,
            vehicle.intent,
            vehicle.vehicle_class,
        )
        for vehicle in manager.vehicles
    ]


def test_spawn_is_deterministic_for_same_route_and_seed():
    first = _manager(seed=1)
    second = _manager(seed=1)

    first.spawn_initial_traffic()
    second.spawn_initial_traffic()

    assert _signature(first)
    assert _signature(first) == _signature(second)


def test_bad_weather_slows_spawned_traffic_without_moving_it():
    clear = _manager(seed=1)
    rain = _manager(seed=1)
    rain.weather.current = WeatherKind.HEAVY_RAIN

    clear.spawn_initial_traffic()
    rain.spawn_initial_traffic()

    assert _signature(clear)
    assert [v.position_mi for v in rain.vehicles] == [v.position_mi for v in clear.vehicles]
    assert min(v.speed_mph for v in rain.vehicles) < min(v.speed_mph for v in clear.vehicles)


def test_long_route_bad_weather_preserves_spawned_traffic_positions():
    world = get_world()
    route = world.supported_route("Seattle", "New York")
    assert route is not None
    clear = _manager_for_route(route, seed=7)
    rain = _manager_for_route(route, seed=7)
    rain.weather.current = WeatherKind.HEAVY_RAIN

    clear.spawn_initial_traffic()
    rain.spawn_initial_traffic()

    assert clear.vehicles
    assert len(rain.vehicles) == len(clear.vehicles)
    assert _placement_signature(rain) == _placement_signature(clear)
    assert [v.speed_mph for v in rain.vehicles] != [v.speed_mph for v in clear.vehicles]


# -- the rolling bubble ------------------------------------------------------
# Traffic used to be seeded once for the whole route at one candidate per 85
# miles and never replaced, which left the bubble at 0-3 vehicles, draining as
# the trip went on, with nothing ever coming up from behind.


def test_the_bubble_fills_as_the_truck_drives():
    manager = _manager()
    manager.update(dt=0.0, position_mi=20.0, time_scale=1.0)

    assert len(manager.vehicles) >= 4


def test_the_bubble_does_not_drain_over_a_long_run():
    """Vehicles are retired behind the truck, so something must replace them.

    Advanced in driving-sized steps rather than jumps. A truck that teleports
    five miles at a time outruns its own window -- it culls a bubble's worth
    of traffic per step while only a few cells of new road come into range --
    which says nothing about a truck that drives there.
    """
    manager = _manager()
    manager.update(dt=0.0, position_mi=10.0, time_scale=1.0)
    early = len(manager.vehicles)

    position = 10.0
    while position < 70.0:
        position += 0.25
        manager.update(dt=1.0, position_mi=position, time_scale=1.0)

    assert early >= 1
    assert len(manager.vehicles) >= early


def test_traffic_appears_behind_the_truck_so_it_can_be_overtaken():
    """The old model placed everything ahead, so nobody could ever pass.

    Watched over a stretch of driving rather than at one mile: whether a
    given cell of road is carrying somebody is a coin the seed flips, and the
    claim here is about the road, not about mile 30.
    """
    manager = _manager()
    behind_seen: list[float] = []
    position = 30.0
    while position < 45.0:
        position += 0.25
        manager.update(dt=1.0, position_mi=position, time_scale=1.0)
        behind_seen.extend(v.speed_mph for v in manager.vehicles if v.position_mi < position)

    assert behind_seen, "nothing was ever spawned behind the truck"
    # Measured against the road, not against a fixed number. This stretch of
    # I-65 out of Chicago is posted at 55, and traffic speeds are drawn
    # relative to the posting -- a truck cannot legally outrun the limit, so
    # anything faster than it is something that can come by.
    limit = manager._posted_limit_at(40.0)
    assert any(mph > limit for mph in behind_seen), "nothing behind is fast enough to pass"


def test_nothing_is_created_alongside_the_truck():
    """A vehicle that materialises next to the cab appeared out of nowhere."""
    from freight_fate.sim.traffic_manager import NO_SPAWN_AHEAD_MI, NO_SPAWN_BEHIND_MI

    manager = _manager()
    manager.update(dt=0.0, position_mi=40.0, time_scale=1.0)

    for vehicle in manager.vehicles:
        gap = vehicle.position_mi - 40.0
        assert not (-NO_SPAWN_BEHIND_MI < gap < NO_SPAWN_AHEAD_MI), vehicle.key


def test_a_passed_cell_never_spawns_again():
    """Backing up or slowing must not repopulate road already driven."""
    manager = _manager()
    manager.update(dt=0.0, position_mi=50.0, time_scale=1.0)
    keys = {v.key for v in manager.vehicles}

    manager.vehicles = []
    manager.update(dt=0.0, position_mi=50.0, time_scale=1.0)

    assert not ({v.key for v in manager.vehicles} & keys)


def test_the_bubble_is_deterministic_for_the_same_seed_and_position():
    first, second = _manager(seed=4), _manager(seed=4)
    first.update(dt=0.0, position_mi=25.0, time_scale=1.0)
    second.update(dt=0.0, position_mi=25.0, time_scale=1.0)

    assert first.vehicles
    assert [(v.key, round(v.position_mi, 6), round(v.speed_mph, 6)) for v in first.vehicles] == [
        (v.key, round(v.position_mi, 6), round(v.speed_mph, 6)) for v in second.vehicles
    ]


def test_density_ignores_the_difficulty_and_compression_knobs():
    """Presence is not difficulty -- the same rule the police already follow.

    hazard_scale is the relaxed-mode hazard multiplier times the time-scale
    tuning's hazard frequency. Neither is a statement about how many vehicles
    exist, and together they were emptying the interstate.
    """
    busy = _manager(seed=3)
    quiet = _manager(seed=3)
    quiet.hazard_scale = 0.11

    busy.update(dt=0.0, position_mi=30.0, time_scale=1.0)
    quiet.update(dt=0.0, position_mi=30.0, time_scale=1.0)

    assert busy.vehicles
    assert len(busy.vehicles) == len(quiet.vehicles)


def test_density_follows_the_clock_not_the_departure_hour():
    """A run that leaves at 04:00 drives into the morning rush."""
    manager = _manager()
    leg = manager.route.legs[0]

    manager.hour = 3.0
    quiet = manager._leg_density(leg, night=True)
    manager.hour = 8.0
    rush = manager._leg_density(leg, night=False)

    assert rush > quiet


def test_traffic_runs_at_the_speed_of_the_road_it_is_on():
    """Highway traffic must not crawl because the map got faster.

    The intent bands were absolute mph, set before real posted limits were
    baked per leg. On a 75 mph corridor the whole population ran 20-40 mph
    slower than the road, so a lead-vehicle cue told the driver to leave room
    for 30 for a semi on an interstate (owner playtest, 2026-08-15).
    """
    world = get_world()
    route = world.route_from_cities(["Dallas", "Houston"])
    assert route is not None
    manager = _manager_for_route(route, seed=4)
    # A dry-road claim: bad weather slowing everyone down is the model
    # working, and would blur what this test is about.
    manager.weather.current = WeatherKind.CLEAR

    limit = manager._posted_limit_at(180.0)
    assert limit >= 70.0, f"the fixture stretch is meant to be a fast one, got {limit}"

    # Each vehicle once, at the speed it joined the road at, and paired with
    # where it joined: the claim is about the speed traffic is created with,
    # not about a braking vehicle's later deceleration, and a slow vehicle
    # lingers in the bubble long enough to dominate a per-frame sample.
    seen: list[tuple[float, float]] = []
    counted: set[str] = set()
    position = 175.0
    while position < 190.0:
        position += 0.25
        manager.update(dt=1.0, position_mi=position, time_scale=1.0)
        for v in manager.vehicles:
            if v.key not in counted:
                counted.add(v.key)
                seen.append((v.speed_mph, v.position_mi))

    assert seen, "nothing was ever spawned on the fixture stretch"
    for mph, at_mi in seen:
        floor = manager._floor_speed(manager._posted_limit_at(at_mi))
        assert mph >= floor - 0.01, f"{mph:.1f} mph at mile {at_mi:.1f}, floor {floor:.1f}"
    # And the fast road is carrying somebody at its own posted number, which
    # is what the old absolute bands could not do once the map got faster.
    fast = [mph for mph, at_mi in seen if manager._posted_limit_at(at_mi) >= 70.0]
    assert fast, "no vehicle was ever on the fast stretch"
    assert max(fast) >= limit, max(fast)
    # And nothing on a 75 mph corridor is doing town speeds. This is the
    # actual report: the old bands put merging traffic at 38-52 and braking
    # traffic at 35-48 whatever the road was posted at, so the truck told the
    # driver to leave room for 30 for a semi on an interstate.
    assert min(fast) >= limit - 25.0, min(fast)
    near_the_limit = [mph for mph in fast if mph >= limit - 8.0]
    assert len(near_the_limit) >= len(fast) // 4, f"{len(near_the_limit)} of {len(fast)}"


def test_traffic_scales_down_where_the_road_is_slow():
    """The same draw on a 45 mph posting must not put interstate speeds in a
    town: relative bands have to cut both ways."""
    world = get_world()
    route = world.route_from_cities(["Chicago", "Indianapolis"])
    assert route is not None
    manager = _manager_for_route(route, seed=4)

    slow = manager._posted_limit_at(5.0)
    assert slow <= 55.0, f"the fixture stretch is meant to be a slow one, got {slow}"

    seen: list[float] = []
    position = 3.0
    while position < 15.0:
        position += 0.25
        manager.update(dt=1.0, position_mi=position, time_scale=1.0)
        seen.extend(
            v.speed_mph for v in manager.vehicles if manager._posted_limit_at(v.position_mi) <= slow
        )

    assert seen, "nothing was ever spawned on the fixture stretch"
    assert max(seen) <= slow + 12.0, max(seen)


def test_the_opening_miles_of_a_run_spawn_nobody_merging():
    """Pulling out of a gate must not open with a merge warning.

    The bubble's nearest cell is barely a mile ahead, and a merging vehicle
    drawn there made "merging traffic ahead" the first thing a driver heard
    on a run they had not started moving on (owner report, 2026-08-16).
    Behaviour, not the constant: nothing merging is placed inside the
    window, and merging traffic still exists once the run is under way.
    """
    from freight_fate.sim.traffic_manager import MERGE_FREE_START_MI

    # Sweep seeds so this cannot pass by one lucky draw.
    opening: list[str] = []
    later: list[str] = []
    for seed in range(40):
        manager = _manager(seed=seed)
        manager._replenish(0.0)
        opening += [v.intent for v in manager.vehicles if v.position_mi < MERGE_FREE_START_MI]
        later += [v.intent for v in manager.vehicles if v.position_mi >= MERGE_FREE_START_MI]

    assert opening, "the sweep must actually place vehicles in the window"
    assert "merging" not in opening
    # The intent is withheld at the start, not removed from the game -- but a
    # merge now needs an on-ramp to come from, so this looks where one is
    # rather than anywhere past the window.
    for seed in range(40):
        manager = _manager(seed=seed)
        for ramp_mile in _ramp_miles(manager)[:6]:
            if ramp_mile < MERGE_FREE_START_MI:
                continue
            manager._spawned_cells.clear()
            manager.vehicles.clear()
            manager._replenish(ramp_mile)
            later += [v.intent for v in manager.vehicles if v.position_mi >= MERGE_FREE_START_MI]
    assert "merging" in later


def test_the_merge_free_window_only_covers_the_start_of_the_route():
    """Mid-route the start-of-run rule stops applying -- but a merge still
    needs a ramp to come from.

    This used to sample anywhere past MERGE_FREE_START_MI and expect a merge,
    which passed only because merging was drawn uniformly along the whole
    leg. It is positional now (see
    test_merging_only_happens_where_a_ramp_feeds_in), so the sample has to
    look where an on-ramp actually feeds in.
    """
    from freight_fate.sim.traffic_manager import MERGE_FREE_START_MI

    intents: list[str] = []
    for seed in range(40):
        manager = _manager(seed=seed)
        for ramp_mile in _ramp_miles(manager)[:6]:
            if ramp_mile < MERGE_FREE_START_MI:
                continue
            manager._spawned_cells.clear()
            manager.vehicles.clear()
            manager._replenish(ramp_mile)
            intents += [v.intent for v in manager.vehicles if v.position_mi >= MERGE_FREE_START_MI]
    assert "merging" in intents, "no merge anywhere near an on-ramp"


def test_traffic_density_reads_the_road_s_real_volume():
    """Owner, 2026-08-19: complete the traffic feature rather than leave the
    vehicle count on a guess.

    Density used to come from a class/metro heuristic -- "does this leg have
    checkpoints" standing in for how busy the road is. It now reads the baked
    HPMS volume under the truck, through the same chain congestion uses:
    AADT, this hour's share of the day, the peak direction's share, over the
    speed traffic is moving. Arrivals are Poisson, so the expected count in a
    cell becomes the chance it holds somebody.
    """
    import math

    from freight_fate.sim.traffic_manager import SPAWN_CELL_MI
    from freight_fate.sim.trip_models import DIRECTIONAL_SPLIT, hourly_volume_fraction

    def density(aadt, hour, mph=60.0):
        lam = aadt * hourly_volume_fraction(hour, False) * DIRECTIONAL_SPLIT / mph * SPAWN_CELL_MI
        return min(0.86, max(0.05, 1.0 - math.exp(-lam)))

    # A quiet rural highway empties out overnight and fills at rush.
    assert density(2500, 3.0) < 0.15
    assert density(2500, 17.0) > density(2500, 3.0) * 3

    # And a busy road is busier than a quiet one at the same hour.
    assert density(45000, 12.0) > density(2500, 12.0)


def test_a_leg_with_no_baked_volume_drives_exactly_as_before():
    """The fallback must be a true no-op. 6 of 1,290 legs have no HPMS
    coverage, and adding this must not quietly change how they feel."""
    import inspect

    from freight_fate.sim.traffic_manager import TrafficManager

    src = inspect.getsource(TrafficManager._leg_density)
    # The old shape is still there, reached only when the bake has nothing.
    assert "0.22 + leg.miles / 900.0" in src
    assert "if volume is None" in src


def test_merging_only_happens_where_a_ramp_feeds_in():
    """Owner, 2026-08-19: "why do we have to clear every single car? Have to
    swerve around every single one when most are just passing."

    Because merging was drawn UNIFORMLY along the leg at a weight of 1.2
    against 7.3 total -- one vehicle in six, anywhere, with no on-ramp in
    sight -- and braking was another one in seven, equally unconditioned. So
    roughly a third of everything ahead demanded action on a road where
    almost everything is really just travelling.

    Both are positional in life and both now have data: interchanges are
    baked (0.22 per mile on I-65) and congestion is placed from real HPMS
    volumes. On a 192-mile leg with 42 interchanges only about a tenth of the
    road can produce a merge, so the same share of vehicles now works out
    around ten times rarer overall.
    """
    from freight_fate.data.world import get_world
    from freight_fate.sim.traffic_manager import MERGE_WINDOW_MI, TrafficManager

    world = get_world()
    leg = next(
        leg
        for leg in world.legs
        if (leg.highway or "").startswith("I-")
        and leg.miles > 100
        and getattr(leg, "interchanges", ())
    )
    ramps = [i.at_mi for i in leg.interchanges if getattr(i, "at_mi", None) is not None]
    assert ramps

    manager = TrafficManager.__new__(TrafficManager)
    manager.route = type("R", (), {"legs": [leg], "cities": [leg.a, leg.b]})()
    manager.leg_starts = [0.0]

    # Right after a ramp: a merge is plausible.
    assert manager._merge_plausible_at(ramps[0] + 0.1)
    # Well clear of every ramp: it is not.
    far = max(
        (m for m in [r + MERGE_WINDOW_MI * 4 for r in ramps] if m < leg.miles),
        default=None,
    )
    clear = next(
        (
            m
            for m in [ramps[0] + MERGE_WINDOW_MI + 0.5]
            if all(not (0.0 <= m - r <= MERGE_WINDOW_MI) for r in ramps)
        ),
        None,
    )
    if clear is not None:
        assert not manager._merge_plausible_at(clear)
    assert far is None or isinstance(far, float)


def test_hard_braking_follows_the_congestion_not_the_dice():
    """The other half. "Somebody is on the brakes" used to be sprinkled evenly
    down an empty interstate; it now needs a jam or a ramp to explain it."""
    from freight_fate.sim.traffic_manager import TrafficManager

    manager = TrafficManager.__new__(TrafficManager)
    manager._braking_zones = ((10.0, 14.0),)
    manager.route = type("R", (), {"legs": [], "cities": []})()
    manager.leg_starts = []

    assert manager._braking_plausible_at(12.0)
    assert not manager._braking_plausible_at(40.0)
