"""Backing down a travelled lane: the ladder, and where it must stay quiet.

The adversarial harness backed a tractor-trailer a full mile down an
interstate and the game's only spoken line in all that time was a merge
instruction for the exit it was reversing away from. A sighted player would
see the world sliding the wrong way; a blind player had nothing, which makes
this an accessibility gap before it is a realism one.
"""

import pytest
from speech_capture import speech_stub

from freight_fate.models.business import LEASED_OWNER_OPERATOR
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile
from freight_fate.sim.transmission import REVERSE
from freight_fate.states.driving_wrong_way import (
    WRONG_WAY_REMIND_MI,
    WRONG_WAY_TRAFFIC_MI,
    WRONG_WAY_WARN_MI,
)

MPS_PER_MPH = 1 / 2.23694


@pytest.fixture
def app():
    from freight_fate.app import App

    made = App()
    try:
        yield made
    finally:
        made.shutdown()


def _driving(app):
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Backer", current_city="Denver")
    app.ctx.profile.business_status = LEASED_OWNER_OPERATOR
    app.ctx.profile.owned_trucks = ["rig"]
    job = Job(
        CARGO_CATALOG["general"], 12.0, "Denver", "yard", "Salt Lake City", 200.0, 900.0, 12.0
    )
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, job, route, trip_seed=99, start_hour=10.0)
    app.push_state(driving)
    driving.truck.set_air_ready(parking_brake=False)
    return driving


def _back_up(driving, miles, *, step_mi=0.005):
    """Roll the truck backwards along the route, a step at a time."""
    truck = driving.truck
    truck.transmission.gear = REVERSE
    truck.velocity_mps = 8.0 * MPS_PER_MPH
    travelled = 0.0
    while travelled < miles:
        driving.trip.last_moved_mi = -step_mi
        driving.trip.position_mi = max(0.0, driving.trip.position_mi - step_mi)
        driving._update_wrong_way(1 / 60)
        travelled += step_mi


def _open_road(driving):
    """Park the truck mid-route, clear of any stop, yard or receiver."""
    trip = driving.trip
    trip.position_mi = trip.total_miles / 2.0
    trip.stops = [s for s in (getattr(trip, "stops", None) or []) if False]
    return trip


# -- the ladder --------------------------------------------------------------


def test_backing_a_truck_length_says_so(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    driving = _driving(app)
    _open_road(driving)

    _back_up(driving, WRONG_WAY_REMIND_MI * 1.5)

    assert any("reverse" in line.lower() for line in spoken)


def test_the_warning_names_it_illegal_and_never_says_zero_miles(app, monkeypatch):
    """A driver told they are giving the route back needs a real number."""
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    driving = _driving(app)
    _open_road(driving)

    _back_up(driving, WRONG_WAY_WARN_MI * 1.2)

    warnings = [line for line in spoken if "wrong way" in line.lower()]
    assert warnings
    assert "illegal" in warnings[0]
    assert "0 miles" not in warnings[0]


def test_backing_far_enough_puts_you_into_traffic(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    driving = _driving(app)
    _open_road(driving)
    damage_before = driving.truck.damage_pct

    _back_up(driving, WRONG_WAY_TRAFFIC_MI * 1.2)

    assert any("traffic" in line.lower() for line in spoken)
    assert driving.truck.damage_pct > damage_before


# -- where it must stay quiet ------------------------------------------------


def test_backing_in_the_origin_yard_is_nobodys_business(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    driving = _driving(app)
    driving.trip.position_mi = 0.1

    _back_up(driving, WRONG_WAY_WARN_MI * 2)

    assert spoken == []


def test_backing_onto_the_receivers_dock_is_the_job(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    driving = _driving(app)
    driving.trip.position_mi = driving.trip.total_miles - 0.1

    _back_up(driving, WRONG_WAY_WARN_MI * 2)

    assert spoken == []


def test_rolling_forward_is_never_the_wrong_way(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    driving = _driving(app)
    trip = _open_road(driving)
    driving.truck.velocity_mps = 60.0 * MPS_PER_MPH

    for _ in range(400):
        trip.last_moved_mi = 0.005
        trip.position_mi += 0.005
        driving._update_wrong_way(1 / 60)

    assert spoken == []


def test_stopping_the_truck_forgets_the_stint(app, monkeypatch):
    """Coming to a stop resets the ladder; a later nudge starts over."""
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    driving = _driving(app)
    _open_road(driving)

    _back_up(driving, WRONG_WAY_REMIND_MI * 1.5)
    assert driving._wrong_way_mi > 0.0

    driving.truck.velocity_mps = 0.0
    driving._update_wrong_way(1 / 60)

    assert driving._wrong_way_mi == 0.0
