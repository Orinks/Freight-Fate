"""Blowing the stop at the end of the destination ramp loops back.

A destination terminal with no street chain used to simply wait when the truck
rolled past it at speed: the arrival line was spoken once, the ramp counted
down past it forever, and nothing else was ever said. A player circled the ramp
for minutes with the route status frozen and quit to the menu (owner playtest,
Buffalo to Albany, 2026-08-12). It now loops back through the next safe
turnaround like every other missed stop on the route.
"""

import pytest
from driving_feature_helpers import release_air_brakes
from speech_capture import speech_stub

from freight_fate.sim.trip_models import RoadStop
from freight_fate.states.driving_core import (
    RAMP_OVERSHOOT_MI,
    RAMP_TERMINAL_MISS_LOOP_MIN,
)


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Terminal", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(
        CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles,
        1000.0,
        12.0,
        destination_location="Rochester freight market",
    )
    driving = DrivingState(app.ctx, job, route, phase="delivery")
    driving.trip.traffic_manager.vehicles = []
    return driving


def _at_the_terminal(driving, *, mph: float = 36.0):
    """End of a no-chain destination ramp, terminal cleared, still rolling."""
    driving._surface_chain_route = lambda: None  # a facility with no street chain
    stop = RoadStop("the Rochester freight market", 10.0, "delivery_destination", ("deliver",))
    driving._destination_exit_taken = True
    driving._ramp_stop = stop
    driving._ramp_mi = 0.0
    driving._ramp_control = "none"
    driving._ramp_terminal_done = True
    driving._ramp_light_announced = True
    release_air_brakes(driving)
    driving.truck.start_engine()
    driving.truck.velocity_mps = mph / 2.23694
    return stop


def _arrival_line(stop):
    return (f"You are at {stop.name}. Come to a complete stop.", True)


def test_blown_destination_terminal_loops_back(monkeypatch):
    from freight_fate.app import App

    app = App()
    said = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(said, with_interrupt=True))
    try:
        d = _driving(app)
        stop = _at_the_terminal(d)
        minutes = d.trip.game_minutes

        d._update_exit(0.0)
        assert said[-1] == _arrival_line(stop)
        spoken = len(said)
        grace = d._ramp_arrival_grace_s
        assert grace > 0.0, "the destination arrival must open a reaction window"

        # Distance alone cannot consume the spoken reaction window.
        d._update_exit(RAMP_OVERSHOOT_MI, grace - 0.1)
        assert d._ramp_mi <= -RAMP_OVERSHOOT_MI
        assert len(said) == spoken
        assert d.trip.game_minutes == pytest.approx(minutes)

        d._update_exit(0.0, 0.2)
        assert len(said) == spoken + 1, "the loop-back speaks once, not every frame"
        line, interrupt = said[-1]
        assert interrupt
        assert "safe turnaround" in line
        assert stop.name in line
        assert d.trip.game_minutes == pytest.approx(minutes + RAMP_TERMINAL_MISS_LOOP_MIN)

        # The entrance is ahead again, and it announces fresh on the re-approach.
        assert d._ramp_stop is stop
        assert d._ramp_mi > 0.0
        assert not d._ramp_end_said
        assert not d._speed_control_armed
        d._update_exit(d._ramp_mi)
        assert said[-1] == _arrival_line(stop)
    finally:
        app.shutdown()


def test_second_blown_terminal_loops_again_and_names_the_brake(monkeypatch):
    from freight_fate.app import App

    app = App()
    said = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(said, with_interrupt=True))
    try:
        d = _driving(app)
        stop = _at_the_terminal(d)
        minutes = d.trip.game_minutes

        d._update_exit(0.0)  # the arrival line
        d._update_exit(RAMP_OVERSHOOT_MI, d._ramp_arrival_grace_s + 1.0)
        first = said[-1][0]
        assert "safe turnaround" in first
        assert "Brake with" not in first

        d._update_exit(d._ramp_mi)  # fresh arrival on the re-approach
        assert said[-1] == _arrival_line(stop)
        d._update_exit(RAMP_OVERSHOOT_MI, d._ramp_arrival_grace_s + 1.0)

        second = said[-1][0]
        assert "safe turnaround" in second
        assert "Brake with" in second, "a repeat miss earns help, not silence"
        assert d._ramp_terminal_miss_count == 2
        assert d._ramp_mi > 0.0
        assert d.trip.game_minutes == pytest.approx(minutes + 2 * RAMP_TERMINAL_MISS_LOOP_MIN)
    finally:
        app.shutdown()


def test_stopping_before_the_overshoot_still_opens_the_arrival(monkeypatch):
    from freight_fate.app import App

    app = App()
    said = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(said, with_interrupt=True))
    try:
        d = _driving(app)
        stop = _at_the_terminal(d)
        opened = []
        monkeypatch.setattr(d, "_open_facility_arrival", lambda: opened.append(True))
        minutes = d.trip.game_minutes

        d._update_exit(0.0)
        assert said[-1] == _arrival_line(stop)

        # Rolled a little past the end of the ramp, but stopped inside the
        # overshoot distance: that is an arrival, not a miss.
        d.truck.velocity_mps = 0.0
        d._update_exit(0.2, 1.0)

        assert opened == [True]
        assert d._ramp_mi is None
        assert d._ramp_stop is None
        assert d.trip.finished
        assert d.trip.game_minutes == pytest.approx(minutes)
        assert d._ramp_terminal_miss_count == 0
    finally:
        app.shutdown()


def test_speed_control_waits_out_a_pending_ramp_stop(monkeypatch):
    """Automatic speed control must not resume onto a ramp with a stop on it.

    Taking the exit cancels cruise outright; the resume helper re-engaged it a
    frame later and drove the playtest straight past the entrance.
    """
    from freight_fate.app import App

    app = App()
    monkeypatch.setattr(app.ctx, "say", speech_stub())
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = _driving(app)
        d.trip.speed_limit_at = lambda mile: (65.0, None)
        release_air_brakes(d)
        d.truck.start_engine()
        d.truck.velocity_mps = 25.0
        d._restore_speed_control_session(armed=True, target_mph=55.0)

        d._ramp_mi = 0.3  # rolling down the ramp toward the stop
        d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph is None
        assert d._keeper_mph is None
        assert d._speed_control_armed  # still armed, just not engaging here

        d._ramp_mi = None  # the arrival settled and the ramp is behind the truck
        d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph == pytest.approx(55.0)
    finally:
        app.shutdown()
