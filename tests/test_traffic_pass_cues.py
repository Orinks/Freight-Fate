"""The whoosh when somebody goes by.

Four pass-by cues shipped with the traffic bubble and only the trooper's
could ever play, because that one hangs off the enforcement layer's
crossing check. Civilian traffic going past the cab made no sound at all,
which on a road the player reads by ear is a hole in the only spatial
channel there is.
"""

import pytest
from speech_capture import speech_stub

from freight_fate.models.business import LEASED_OWNER_OPERATOR
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile
from freight_fate.sim.traffic_manager import TrafficVehicle
from freight_fate.states.driving_traffic_pass import TRAFFIC_PASS_MIN_GAP_S


@pytest.fixture
def app():
    from freight_fate.app import App

    made = App()
    try:
        yield made
    finally:
        made.shutdown()


def _driving(app, monkeypatch):
    from freight_fate.states.driving import DrivingState

    played: list[tuple[str, float]] = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    monkeypatch.setattr(app.ctx, "say", speech_stub())
    monkeypatch.setattr(
        app.ctx.audio,
        "play",
        lambda name, *a, **k: played.append((name, k.get("pan", 0.0))),
    )
    app.ctx.profile = Profile(name="Passer", current_city="Denver")
    app.ctx.profile.business_status = LEASED_OWNER_OPERATOR
    app.ctx.profile.owned_trucks = ["rig"]
    job = Job(
        CARGO_CATALOG["general"], 12.0, "Denver", "yard", "Salt Lake City", 200.0, 900.0, 12.0
    )
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, job, route, trip_seed=99, start_hour=10.0)
    app.push_state(driving)
    driving.truck.set_air_ready(parking_brake=False)
    driving.trip.position_mi = 20.0
    return driving, played


def _pass_once(driving, vehicle_class="car", *, lane=1, speed=75.0, ahead=0.2):
    """Walk one vehicle from ahead of the truck to behind it."""
    manager = driving.trip.traffic_manager
    manager.vehicles = [
        TrafficVehicle(
            key=f"probe:{vehicle_class}",
            position_mi=driving.trip.position_mi + ahead,
            speed_mph=speed,
            target_speed_mph=speed,
            relative_lane=-lane,
            intent="passing",
            vehicle_class=vehicle_class,
            lane=lane,
        )
    ]
    driving._update_traffic_passes(1 / 60)
    manager.vehicles[0].position_mi = driving.trip.position_mi - ahead
    driving._update_traffic_passes(1 / 60)


def test_a_semi_going_by_plays_the_semi_cue(app, monkeypatch):
    driving, played = _driving(app, monkeypatch)

    _pass_once(driving, "semi")

    assert any(name == "traffic/semi_pass" for name, _ in played)


def test_each_class_gets_its_own_whoosh(app, monkeypatch):
    for vehicle_class, expected in (
        ("car", "traffic/car_pass"),
        ("box truck", "traffic/box_truck_pass"),
        ("semi", "traffic/semi_pass"),
    ):
        driving, played = _driving(app, monkeypatch)
        _pass_once(driving, vehicle_class)
        assert any(name == expected for name, _ in played), vehicle_class


def test_the_cue_is_panned_to_the_side_it_passed_on(app, monkeypatch):
    driving, played = _driving(app, monkeypatch)

    _pass_once(driving, "car", lane=1)  # left of a truck in lane 0

    pans = [pan for name, pan in played if name.startswith("traffic/")]
    assert pans and pans[0] < 0.0


def test_a_vehicle_is_only_whooshed_once(app, monkeypatch):
    """A truck alongside in slow traffic can cross the bumper repeatedly."""
    driving, played = _driving(app, monkeypatch)
    manager = driving.trip.traffic_manager
    manager.vehicles = [TrafficVehicle("probe:car", 20.2, 75.0, 75.0, -1, "passing", "car", lane=1)]

    for offset in (0.2, -0.2, 0.2, -0.2):
        manager.vehicles[0].position_mi = 20.0 + offset
        driving._update_traffic_passes(1 / 60)

    assert len([n for n, _ in played if n.startswith("traffic/")]) == 1


def test_troopers_are_left_to_the_enforcement_layer(app, monkeypatch):
    """It already gives them a marker the civilian clips deliberately lack."""
    driving, played = _driving(app, monkeypatch)

    _pass_once(driving, "state trooper")

    assert not any(name == "traffic/trooper_pass" for name, _ in played)


def test_close_passes_do_not_machine_gun(app, monkeypatch):
    """Ten times pacing turns a populated road into a whoosh every 2 seconds."""
    driving, played = _driving(app, monkeypatch)
    manager = driving.trip.traffic_manager
    manager.vehicles = [
        TrafficVehicle(f"probe:{i}", 20.2, 75.0, 75.0, -1, "passing", "car", lane=1)
        for i in range(6)
    ]
    driving._update_traffic_passes(1 / 60)
    for vehicle in manager.vehicles:
        vehicle.position_mi = 19.8
    driving._update_traffic_passes(1 / 60)

    assert len([n for n, _ in played if n.startswith("traffic/")]) == 1


def test_the_cooldown_lets_the_next_one_through(app, monkeypatch):
    driving, played = _driving(app, monkeypatch)

    _pass_once(driving, "car")
    driving._update_traffic_passes(TRAFFIC_PASS_MIN_GAP_S)
    _pass_once(driving, "semi")

    names = [n for n, _ in played if n.startswith("traffic/")]
    assert "traffic/car_pass" in names
    assert "traffic/semi_pass" in names


def test_a_vehicle_holding_station_never_whooshes(app, monkeypatch):
    driving, played = _driving(app, monkeypatch)
    manager = driving.trip.traffic_manager
    manager.vehicles = [TrafficVehicle("probe:steady", 20.5, 60.0, 60.0, 0, "cruising", "semi")]

    for _ in range(20):
        driving._update_traffic_passes(1 / 60)

    assert not [n for n, _ in played if n.startswith("traffic/")]
