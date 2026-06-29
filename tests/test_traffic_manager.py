"""Traffic bubble manager tests."""

from freight_fate.data.world import get_world
from freight_fate.sim.traffic_manager import TrafficManager, TrafficVehicle
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherKind, WeatherSystem


def _manager(seed: int = 1) -> TrafficManager:
    world = get_world()
    route = world.route_from_cities(["Chicago", "Indianapolis"])
    truck = TruckState()
    weather = WeatherSystem("great_lakes", seed=1)
    return TrafficManager(
        route=route,
        truck=truck,
        weather=weather,
        leg_starts=[0.0],
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
    assert vehicle.reason == "merging traffic"


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
