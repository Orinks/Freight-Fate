"""Ramp-terminal controls: lights and stop signs where the ramp meets the
surface road, honored or run, baked from OSM or seeded by the heuristic."""

import pytest

from freight_fate.states.driving import (
    GREEN_ROLL_MPH,
    RAMP_ACCESS_MI,
    RAMP_LIGHT_GREEN_S,
    RAMP_LIGHT_RED_S,
    RAMP_LIGHT_YELLOW_S,
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
    d._ramp_light_last_phase = "red" if red else "green"
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
        assert d._ramp_light_phase() == "red"
        d._ramp_light_timer = RAMP_LIGHT_RED_S + 0.1
        assert not d._ramp_light_is_red()
        assert d._ramp_light_phase() == "green"
        # Green ends in yellow, not a hard cut to red -- and yellow is legal.
        d._ramp_light_timer = RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S + 0.1
        assert d._ramp_light_phase() == "yellow"
        assert not d._ramp_light_is_red()
        d._ramp_light_timer = RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S + RAMP_LIGHT_YELLOW_S + 0.1
        assert d._ramp_light_is_red()
    finally:
        app.shutdown()


def test_crossing_on_yellow_is_legal():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, "signal", red=False, mph=GREEN_ROLL_MPH - 5.0)
        # Put the cycle just into the yellow phase at the stop bar.
        d._ramp_light_offset_s = RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S + 0.5
        assert d._ramp_light_phase() == "yellow"
        d._update_ramp_terminal()
        assert d._ramp_terminal_done
        assert d.truck.damage_pct == 0.0
    finally:
        app.shutdown()


def test_stopped_short_of_the_light_gets_creep_guidance(monkeypatch):
    """A cautious stop far short of the bar must not read as a stuck light:
    the game says the driver is short and to creep up (playtest 2026-07-16)."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = []
        monkeypatch.setattr(d.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
        _on_ramp(d, "signal", red=True, mph=0.0)
        d._ramp_mi = RAMP_ACCESS_MI + 0.15  # stopped well short of the bar

        d._update_ramp_light(0.1)
        # A real gap is named in feet and driven, not crept: 0.15 mi of
        # "creep" spans several light cycles and reads as a stuck light.
        assert any("800 feet short of the light" in text for text in spoken)
        assert any("Drive up" in text for text in spoken)

        # Once per stop, not every frame.
        d._update_ramp_light(0.1)
        assert len([t for t in spoken if "short of the light" in t]) == 1

        # Rolling re-arms the prompt; the next stop short prompts again --
        # and within a couple hundred feet the wording drops to a creep.
        d.truck.velocity_mps = 10.0 / 2.2369362920544
        d._update_ramp_light(0.1)
        d.truck.velocity_mps = 0.0
        d._ramp_mi = RAMP_ACCESS_MI + 0.02
        d._update_ramp_light(0.1)
        assert len([t for t in spoken if "short of the light" in t]) == 2
        assert any("Creep ahead" in text for text in spoken)

        # At the bar the prompt stays quiet: the waiting handshake owns it.
        spoken.clear()
        d._ramp_creep_prompt_said = False
        d._ramp_mi = RAMP_ACCESS_MI
        d._update_ramp_light(0.1)
        assert not any("stopped short" in text for text in spoken)
    finally:
        app.shutdown()


def test_yellow_and_green_wording_track_distance_to_the_bar(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = []
        monkeypatch.setattr(d.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
        # Short of the bar, moving: yellow says stop then creep up on the red.
        _on_ramp(d, "signal", red=False, mph=20.0)
        d._ramp_mi = RAMP_ACCESS_MI + 0.15
        d._update_ramp_light(RAMP_LIGHT_GREEN_S + 0.5)  # into yellow
        assert any("creep up to the bar" in text for text in spoken)

        # At the bar: yellow says continuing through is legal.
        spoken.clear()
        _on_ramp(d, "signal", red=False, mph=20.0)
        d._update_ramp_light(RAMP_LIGHT_GREEN_S + 0.5)
        assert any("Continuing through is legal" in text for text in spoken)
    finally:
        app.shutdown()


def test_every_light_change_is_spoken_on_the_approach(monkeypatch):
    """The silent flip back to red between a spoken green and the stop bar
    cost a real playtester trailer damage; every phase change must speak."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = []
        monkeypatch.setattr(d.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
        _on_ramp(d, "signal", red=True, mph=10.0)
        d._ramp_mi = RAMP_ACCESS_MI + 0.3  # still descending the ramp
        cycle = RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S + RAMP_LIGHT_YELLOW_S
        for _ in range(int(cycle * 10) + 5):  # one full cycle at 0.1 s steps
            d._update_ramp_light(0.1)
        assert any("turns green" in text for text in spoken)
        assert any("turns yellow" in text for text in spoken)
        assert any("turns red" in text for text in spoken)
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


def test_ramp_control_is_knowable_before_the_ramp():
    """The signal-on announcement a mile out and the ramp itself must
    always agree: _ramp_control_for is a pure preview of the decision
    _begin_ramp_terminal commits to."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        for at_mi in (10.0, 22.5, 30.0, 41.0, 55.0):
            stop = _FakeStop(at_mi=at_mi)
            early = d._ramp_control_for(stop)
            d._begin_ramp_terminal(stop)
            assert d._ramp_control == early, at_mi
    finally:
        app.shutdown()


def test_signal_on_names_the_ramp_ending(monkeypatch):
    """Owner playtest 2026-07-16: the stop sign was announced only on the
    ramp, far too late to brake for. The signal-on announcement names the
    ending while there is still a mile of mainline to plan on."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = []
        monkeypatch.setattr(d.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        d.trip.ramp_control_at = lambda mi: "stop"
        stop = _FakeStop(at_mi=d.trip.position_mi + 1.2)
        stop.spoken_name = "Test Plaza"
        stop.exit_label = ""
        d._exit_stop = stop
        d._exit_signal_on = False

        d._toggle_exit_signal()

        assert d._exit_signal_on
        assert "The ramp ends at a stop sign." in spoken[-1]
    finally:
        app.shutdown()


def test_upcoming_readout_names_the_ramp_ending(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = []
        monkeypatch.setattr(d.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        d.trip.ramp_control_at = lambda mi: "signal"
        stop = _FakeStop(at_mi=d.trip.position_mi + 5.0)
        stop.spoken_name = "Test Plaza"
        d.trip.upcoming_stop = lambda within_mi: stop

        d._speak_upcoming()

        assert any(
            "Test Plaza" in text and "ramp ends at a traffic light" in text for text in spoken
        )
    finally:
        app.shutdown()


def test_controlled_ramp_pins_the_clock_to_real_time():
    """Under speed-based compression a hot ramp entry burned the whole
    half mile in a few real seconds (log receipt: exit 17:00:13, sign
    blown 17:00:18). From the gore of a controlled ramp the clock runs
    real, so the warning buys human reaction seconds."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip.time_scale = 10.0
        d.truck.velocity_mps = 45.0 / 2.2369362920544  # hot entry
        assert d.trip.effective_time_scale > 8.0

        d.trip.controlled_ramp = True
        assert d.trip.effective_time_scale == 1.0

        d.trip.controlled_ramp = False
        assert d.trip.effective_time_scale > 8.0
    finally:
        app.shutdown()


def test_update_exit_maintains_the_controlled_ramp_flag():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, "stop", red=False, mph=40.0)
        d._ramp_mi = RAMP_ACCESS_MI + 0.3
        d._ramp_stop = _FakeStop()
        d._update_exit(0.0)
        assert d.trip.controlled_ramp

        # Past the terminal the clock may compress again.
        d._ramp_terminal_done = True
        d._update_exit(0.0)
        assert not d.trip.controlled_ramp

        # A free-flow ramp never pins the clock.
        d._ramp_terminal_done = False
        d._ramp_control = "none"
        d._update_exit(0.0)
        assert not d.trip.controlled_ramp
    finally:
        app.shutdown()


def test_stop_bar_query_names_light_and_distance():
    # Owner playtest 2026-07-19: "where's the bar, you never know." S must
    # answer with the light phase and the gap, any time the driver asks.
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, "signal", red=True, mph=20.0)
        d._ramp_mi = RAMP_ACCESS_MI + 0.1  # ~530 feet short of the bar
        text = d._ramp_light_query_text()
        assert text is not None
        assert "red" in text and "feet" in text and "stop bar" in text

        spoken = []
        app.ctx.say = lambda t, interrupt=True: spoken.append(t)
        d._speak_speed_limit()
        assert spoken and "stop bar" in spoken[0]

        # Off the ramp, S goes back to the posted limit.
        d._ramp_mi = None
        assert d._ramp_light_query_text() is None
    finally:
        app.shutdown()


def test_rolling_countdown_speaks_each_milestone_once():
    from freight_fate.app import App
    from freight_fate.states.driving import RAMP_GAP_MILESTONES_FT

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, "signal", red=True, mph=15.0)
        spoken = []
        app.ctx.say_event = lambda t, interrupt=True: spoken.append(t)
        for feet in (900, 450, 250, 100):
            d._ramp_mi = RAMP_ACCESS_MI + feet / 5280.0
            d._update_ramp_gap_countdown()
            d._update_ramp_gap_countdown()  # same gap again: no repeat
        bar_calls = [t for t in spoken if "to the bar" in t]
        assert len(bar_calls) == len(RAMP_GAP_MILESTONES_FT)
        assert bar_calls[0] == "1000 feet to the bar."
        assert bar_calls[-1] == "150 feet to the bar."

        # Stopped: the countdown yields to the stopped-driver guidance.
        spoken.clear()
        d.truck.velocity_mps = 0.0
        d._ramp_gap_milestones_said.clear()
        d._update_ramp_gap_countdown()
        assert not spoken
    finally:
        app.shutdown()


def test_bar_ticks_speed_up_as_the_bar_closes():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, "signal", red=True, mph=10.0)
        played = []
        d.ctx.audio.play = lambda *a, **k: played.append(a)

        def ticks_over(feet, seconds=3.0, dt=0.05):
            played.clear()
            d._ramp_mi = RAMP_ACCESS_MI + feet / 5280.0
            d._ramp_bar_tick_timer = 0.0
            for _ in range(int(seconds / dt)):
                d._update_ramp_bar_ticks(dt)
            return len(played)

        far, near = ticks_over(280), ticks_over(30)
        assert near > far > 0

        # Beyond the range, and at a standstill, the tick is silent.
        assert ticks_over(600) == 0
        d.truck.velocity_mps = 0.0
        assert ticks_over(50) == 0
    finally:
        app.shutdown()
