"""Traffic bubble manager tests."""

from freight_fate.data.world import get_world
from freight_fate.sim.traffic_manager import TrafficManager, TrafficVehicle
from freight_fate.sim.trip_models import PatrolWindow
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherKind, WeatherSystem


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
        TrafficVehicle("left", 5.1, 55.0, 55.0, -1, "passing", "car"),
        TrafficVehicle("far", 6.0, 45.0, 45.0, 0, "following", "semi"),
        TrafficVehicle("near", 5.3, 42.0, 42.0, 0, "braking", "car"),
    ]

    context = manager.lead_vehicle(position_mi=5.0, truck_speed_mph=60.0)

    assert context is not None
    assert context.lead.key == "near"
    assert context.closing_mph == 18.0


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

    assert [vehicle.key for vehicle in manager.vehicles] == ["ahead"]
    assert manager.vehicles[0].position_mi > 2.2


def test_update_keeps_future_route_traffic_until_reached():
    world = get_world()
    route = world.supported_route("Seattle", "New York")
    assert route is not None
    manager = _manager_for_route(route, seed=7)
    manager.spawn_initial_traffic()
    initial_count = len(manager.vehicles)

    manager.update(dt=0.0, position_mi=0.0, time_scale=20.0)

    assert initial_count > 1
    assert len(manager.vehicles) == initial_count
    assert any(vehicle.position_mi > 10.0 for vehicle in manager.vehicles)


def test_patrol_windows_add_state_trooper_traffic():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("traffic:existing", 2.0, 55.0, 55.0, 0, "cruising", "semi")
    ]
    patrols = [
        PatrolWindow(10.0, 14.0, 0.8, "highway enforcement"),
        PatrolWindow(22.0, 26.0, 0.9, "work zone enforcement"),
    ]

    manager.add_patrol_traffic(patrols)
    manager.add_patrol_traffic(patrols)

    troopers = [
        vehicle for vehicle in manager.vehicles
        if vehicle.vehicle_class == "state trooper"
    ]
    assert len(troopers) == 2
    assert [vehicle.position_mi for vehicle in manager.vehicles] == sorted(
        vehicle.position_mi for vehicle in manager.vehicles
    )
    assert all(vehicle.relative_lane == 0 for vehicle in troopers)


def test_merging_vehicle_moves_into_player_lane_and_creates_situation():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("merge", 0.8, 42.0, 42.0, 1, "merging", "car")
    ]

    manager.update(dt=0.0, position_mi=0.0, time_scale=20.0)
    situation = manager.next_situation(position_mi=0.0, truck_speed_mph=55.0)

    assert manager.vehicles[0].relative_lane == 0
    assert situation is not None
    assert situation.kind == "merging"
    assert "Merging" in situation.message


def test_braking_vehicle_slows_and_creates_lead_situation():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("brake", 0.7, 45.0, 45.0, 0, "braking", "car")
    ]

    manager.update(dt=1.0, position_mi=0.0, time_scale=20.0)
    situation = manager.next_situation(position_mi=0.0, truck_speed_mph=60.0)

    assert manager.vehicles[0].target_speed_mph < 45.0
    assert situation is not None
    assert situation.kind == "braking"
    assert "Brake lights" in situation.message


def test_next_situation_only_announces_vehicle_once():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("lead", 0.7, 42.0, 42.0, 0, "following", "semi")
    ]

    first = manager.next_situation(position_mi=0.0, truck_speed_mph=55.0)
    second = manager.next_situation(position_mi=0.0, truck_speed_mph=55.0)

    assert first is not None
    assert first.kind == "following"
    assert second is None


def test_next_situation_speaks_speed_units():
    manager = _manager()
    manager.vehicles = [
        TrafficVehicle("lead", 0.7, 42.0, 42.0, 0, "following", "semi")
    ]

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
    assert [v.position_mi for v in rain.vehicles] == [
        v.position_mi for v in clear.vehicles
    ]
    assert min(v.speed_mph for v in rain.vehicles) < min(
        v.speed_mph for v in clear.vehicles
    )


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
    assert [v.speed_mph for v in rain.vehicles] != [
        v.speed_mph for v in clear.vehicles
    ]
