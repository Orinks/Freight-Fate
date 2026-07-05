"""Ramp-terminal controls: lights and stop signs where the ramp meets the
surface road, honored or run, baked from OSM or seeded by the heuristic."""

import pytest

from freight_fate.states.driving import (
    GREEN_ROLL_MPH,
    RAMP_ACCESS_MI,
    RAMP_LIGHT_GREEN_S,
    RAMP_LIGHT_RED_S,
    RED_STOP_MPH,
)


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Ramps", current_city="Buffalo")
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


class _FakeStop:
    def __init__(self, at_mi: float = 30.0):
        self.at_mi = at_mi
        self.name = "Test Plaza"
        self.type = "travel_center"


def _on_ramp(d, control: str, *, red: bool, mph: float) -> None:
    """Put the truck mid-ramp approaching the terminal with a known light."""
    d.truck.start_engine()
    d.truck.velocity_mps = mph / 2.2369362920544
    d._ramp_mi = RAMP_ACCESS_MI  # right at the terminal bar
    d._ramp_control = control
    d._ramp_light_offset_s = 0.0 if red else RAMP_LIGHT_RED_S  # phase start
    d._ramp_light_timer = 0.0
    d._ramp_light_announced = True
    d._ramp_light_was_red = red
    d._ramp_terminal_done = False
    d._ramp_waiting_at_light = False


def test_heuristic_control_is_deterministic_and_valid():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        stop = _FakeStop()
        d._begin_ramp_terminal(stop)
        first = d._ramp_control
        d._begin_ramp_terminal(stop)
        assert d._ramp_control == first
        assert first in ("signal", "stop", "none")
        # A different exit may differ, but stays valid.
        d._begin_ramp_terminal(_FakeStop(at_mi=55.0))
        assert d._ramp_control in ("signal", "stop", "none")
    finally:
        app.shutdown()


def test_baked_interchange_control_beats_the_heuristic():
    import dataclasses

    from freight_fate.app import App
    from freight_fate.data.world_models import Interchange, Route
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        app.ctx.profile = Profile(name="Ramps", current_city="Buffalo")
        cached = app.ctx.world.supported_route("Buffalo", "Rochester")
        pinned = Interchange(
            at_mi=30.0,
            exit_ref="7",
            highway=cached.legs[0].highway,
            source="test",
            ramp_control="stop",
        )
        # supported_route returns a cached Route from the world singleton;
        # build a private copy carrying the pinned interchange.
        route = Route(
            cities=list(cached.cities),
            legs=[dataclasses.replace(cached.legs[0], interchanges=(pinned,))]
            + list(cached.legs[1:]),
        )
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
        d = DrivingState(app.ctx, job, route, phase="delivery")
        assert d.trip.ramp_control_at(30.0) == "stop"
        d._begin_ramp_terminal(_FakeStop(at_mi=30.0))
        assert d._ramp_control == "stop"
    finally:
        app.shutdown()


def test_red_light_holds_then_green_releases():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, "signal", red=True, mph=0.0)
        d._update_ramp_terminal()
        assert d._ramp_waiting_at_light
        assert not d._ramp_terminal_done
        # Sit through the rest of the red; the flip releases the wait.
        for _ in range(int(RAMP_LIGHT_RED_S * 10) + 5):
            d._update_ramp_light(0.1)
            if d._ramp_terminal_done:
                break
        assert d._ramp_terminal_done
        assert not d._ramp_waiting_at_light
        assert d.truck.damage_pct == 0.0
    finally:
        app.shutdown()


def test_running_the_red_costs_damage():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, "signal", red=True, mph=30.0)
        d._ramp_mi = 0.05  # well past the bar, still moving
        before = d.truck.damage_pct
        d._update_ramp_terminal()
        assert d._ramp_terminal_done
        assert d.truck.damage_pct > before
    finally:
        app.shutdown()


def test_creeping_the_red_draws_horns_not_damage():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, "signal", red=True, mph=8.0)
        d._ramp_mi = 0.05  # past the bar at a creep
        d._update_ramp_terminal()
        assert d._ramp_terminal_done
        assert d.truck.damage_pct == 0.0
    finally:
        app.shutdown()


def test_green_light_rolls_through_clean():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, "signal", red=False, mph=GREEN_ROLL_MPH - 5.0)
        d._update_ramp_terminal()
        assert d._ramp_terminal_done
        assert d.truck.damage_pct == 0.0
    finally:
        app.shutdown()


def test_still_braking_toward_the_bar_is_not_a_violation():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        # At the check line but before the grace distance, still slowing.
        _on_ramp(d, "signal", red=True, mph=20.0)
        d._update_ramp_terminal()
        assert not d._ramp_terminal_done
        assert d.truck.damage_pct == 0.0
        _on_ramp(d, "stop", red=False, mph=20.0)
        d._update_ramp_terminal()
        assert not d._ramp_terminal_done
    finally:
        app.shutdown()


def test_stop_sign_full_stop_clears():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, "stop", red=False, mph=RED_STOP_MPH - 1.0)
        d._update_ramp_terminal()
        assert d._ramp_terminal_done
        assert d.truck.damage_pct == 0.0
    finally:
        app.shutdown()


def test_blowing_the_stop_sign_clips_cross_traffic():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, "stop", red=False, mph=30.0)
        d._ramp_mi = 0.05  # past the bar at speed
        before = d.truck.damage_pct
        d._update_ramp_terminal()
        assert d._ramp_terminal_done
        assert d.truck.damage_pct > before
    finally:
        app.shutdown()


def test_light_cycle_alternates():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d._ramp_light_offset_s = 0.0
        d._ramp_light_timer = 0.0
        assert d._ramp_light_is_red()
        d._ramp_light_timer = RAMP_LIGHT_RED_S + 0.1
        assert not d._ramp_light_is_red()
        d._ramp_light_timer = RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S + 0.1
        assert d._ramp_light_is_red()
    finally:
        app.shutdown()


def test_interchange_parser_accepts_and_validates_ramp_control():
    from freight_fate.data.world_parsing import _parse_interchange

    raw = {
        "at_mi": 10.0,
        "exit_ref": "12",
        "source": "test source",
        "ramp_control": "signal",
    }
    ix = _parse_interchange(raw, 50.0, "A", "B", "I-99")
    assert ix.ramp_control == "signal"
    raw["ramp_control"] = "roundabout"
    with pytest.raises(ValueError):
        _parse_interchange(raw, 50.0, "A", "B", "I-99")
