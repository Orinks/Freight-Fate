"""Ramp-terminal controls: lights and stop signs where the ramp meets the
surface road, honored or run, baked from OSM or seeded by the heuristic."""

import pygame
import pytest
from speech_capture import speech_stub

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


def test_transition_assist_brakes_for_the_red():
    """With route-transition assistance on, a red ahead gets assist braking.

    Regression for the 2026-07-22 playtest: positioning a rig blind inside
    the bar's grace window was a damage-or-nothing task; the run ended with
    cross traffic in the trailer. The assist now works the pedals."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        app.ctx.settings.route_transition_assist = True
        _on_ramp(d, "signal", red=True, mph=35.0)
        d._ramp_mi = RAMP_ACCESS_MI + 0.08  # ~420 feet short of the bar
        d.truck.brake = 0.0
        d.truck.throttle = 0.5

        d._update_ramp_terminal_assist()

        assert d.truck.brake > 0.0
        assert d.truck.throttle == 0.0
    finally:
        app.shutdown()


def test_transition_assist_holds_the_stop_at_the_bar():
    from freight_fate.app import App
    from freight_fate.states.driving import RAMP_ASSIST_HOLD_MI

    app = App()
    try:
        d = _driving(app)
        app.ctx.settings.route_transition_assist = True
        _on_ramp(d, "signal", red=True, mph=1.0)
        d._ramp_mi = RAMP_ACCESS_MI + RAMP_ASSIST_HOLD_MI / 2.0

        d._update_ramp_terminal_assist()

        assert d._ramp_waiting_at_light
        assert d.truck.brake == 1.0
        assert not d._ramp_terminal_done
        assert d.truck.damage_pct == 0.0

        # The green flip releases the wait exactly like a manual hold.
        for _ in range(int(RAMP_LIGHT_RED_S * 10) + 5):
            d._update_ramp_light(0.1)
            if d._ramp_terminal_done:
                break
        assert d._ramp_terminal_done
        assert d.truck.damage_pct == 0.0
    finally:
        app.shutdown()


def test_transition_assist_completes_the_stop_sign():
    from freight_fate.app import App
    from freight_fate.states.driving import RAMP_ASSIST_HOLD_MI

    app = App()
    try:
        d = _driving(app)
        app.ctx.settings.route_transition_assist = True
        _on_ramp(d, "stop", red=False, mph=1.0)
        d._ramp_mi = RAMP_ACCESS_MI + RAMP_ASSIST_HOLD_MI / 2.0

        d._update_ramp_terminal_assist()

        assert d._ramp_terminal_done
        assert d.truck.damage_pct == 0.0
    finally:
        app.shutdown()


@pytest.mark.parametrize("control", ["stop", "signal"])
def test_transition_assist_releases_a_truck_stopped_short_of_the_hold(control):
    """Stopping short of the hold window must not pin the truck forever.

    Regression for the 2026-07-24 playtest softlock: braking manually on top
    of the assist parked the rig about 80 feet short of the bar -- past the
    hold window that ends the stop, inside the 30-metre band that keeps the
    assist working the pedals. With no speed left there was nothing to brake
    for, so the assist held throttle at zero and the brake at its floor every
    tick and the driver could never move again."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        app.ctx.settings.route_transition_assist = True
        _on_ramp(d, control, red=True, mph=0.0)
        d._ramp_mi = RAMP_ACCESS_MI + 80.0 / 5280.0  # inside the dead band
        d.truck.brake = 0.0
        d.truck.throttle = 0.5

        d._update_ramp_terminal_assist()

        # The pedals stay the driver's: they have to drive up to the bar.
        assert d.truck.throttle == 0.5
        assert d.truck.brake == 0.0
        # Short of the bar is not a completed stop, and not a light hold.
        assert not d._ramp_terminal_done
        assert not d._ramp_waiting_at_light
    finally:
        app.shutdown()


def test_transition_assist_caps_a_hot_green_crossing():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        app.ctx.settings.route_transition_assist = True
        _on_ramp(d, "signal", red=False, mph=40.0)
        d._ramp_mi = RAMP_ACCESS_MI + 0.03
        d.truck.brake = 0.0

        d._update_ramp_terminal_assist()

        assert d.truck.brake > 0.0
    finally:
        app.shutdown()


def test_transition_assist_off_leaves_the_pedals_alone():
    """Realistic drivers who turned the assist off keep the manual bar."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        app.ctx.settings.route_transition_assist = False
        _on_ramp(d, "signal", red=True, mph=35.0)
        d._ramp_mi = RAMP_ACCESS_MI + 0.08
        d.truck.brake = 0.0
        d.truck.throttle = 0.5

        d._update_ramp_terminal_assist()

        assert d.truck.brake == 0.0
        assert d.truck.throttle == 0.5
        assert not d._ramp_waiting_at_light
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
        monkeypatch.setattr(d.ctx, "say_event", speech_stub(spoken))
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
        monkeypatch.setattr(d.ctx, "say_event", speech_stub(spoken))
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
        monkeypatch.setattr(d.ctx, "say_event", speech_stub(spoken))
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
        monkeypatch.setattr(d.ctx, "say", speech_stub(spoken))
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
        monkeypatch.setattr(d.ctx, "say", speech_stub(spoken))
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
        app.ctx.say_event = lambda t, interrupt=True, **_: spoken.append(t)
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


def test_stop_sign_bar_has_position():
    """Countdown, ticks, S query, and stopped-short guidance all answer at
    a stop-sign terminal.

    Playtest 2026-07-22 (Milwaukee grain elevator): the sign announced
    once, then nothing until "blew the stop sign, 15 percent" -- every bar
    instrument was gated to signal terminals only."""
    from freight_fate.app import App
    from freight_fate.states.driving import RAMP_GAP_MILESTONES_FT

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, "stop", red=False, mph=15.0)
        spoken = []
        app.ctx.say_event = lambda t, interrupt=True, **_: spoken.append(t)

        # Rolling countdown through the terminal update, same as a light.
        for feet in (900, 450, 250, 100):
            d._ramp_mi = RAMP_ACCESS_MI + feet / 5280.0
            d._update_ramp_light(0.05)
        bar_calls = [t for t in spoken if "to the bar" in t]
        assert len(bar_calls) == len(RAMP_GAP_MILESTONES_FT)
        assert bar_calls[0] == "1000 feet to the bar."

        # Parking-sensor beeps run for the sign too (outside the solid zone).
        played = []
        d.ctx.audio.play = lambda *a, **k: played.append(a)
        d._ramp_mi = RAMP_ACCESS_MI + 100 / 5280.0
        d._ramp_bar_tick_timer = 0.0
        for _ in range(40):
            d._update_ramp_light(0.05)
        assert played

        # S answers with the sign and the gap.
        d._ramp_mi = RAMP_ACCESS_MI + 0.1
        text = d._ramp_light_query_text()
        assert text is not None
        assert "Stop sign" in text and "feet" in text and "stop bar" in text

        # Stopped short: guidance names the sign, not a light.
        spoken.clear()
        d.truck.velocity_mps = 0.0
        d._ramp_creep_prompt_said = False
        d._update_ramp_light(0.05)
        assert spoken and "stop sign" in spoken[0]
        assert "light" not in spoken[0]
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

        far, near = ticks_over(280), ticks_over(80)
        assert near > far > 0

        # Inside the final leeway the beeps fuse into the continuous tone
        # (owner spec 2026-07-27): no discrete beeps, the alert loop runs.
        loops = []
        d.ctx.audio.start_loop = lambda ch, key, volume=1.0, fade_ms=300: loops.append(key)
        d.ctx.audio.stop_loop = lambda ch, fade_ms=300: None
        assert ticks_over(30) == 0
        assert "vehicle/bar_solid" in loops

        # Beyond the range, and at a standstill, everything is silent.
        assert ticks_over(600) == 0
        d.truck.velocity_mps = 0.0
        d._bar_solid_on = False
        loops.clear()
        assert ticks_over(50) == 0
        assert not loops
    finally:
        app.shutdown()


@pytest.mark.parametrize("control", ["signal", "stop"])
def test_the_bar_tone_ends_when_the_bar_is_behind_the_truck(control):
    """Shane, 2026-08-03: creep up to the bar on a red, reach the solid tone,
    and it never stopped -- not when he got moving again, not in the menus,
    not until he killed the game. The tone's only off-switch sat behind the
    early return that fires the moment the terminal is done, so crossing the
    bar left it sounding with nothing on the road able to end it."""
    from freight_fate.app import App
    from freight_fate.states.driving import RAMP_BAR_SOLID_MI

    app = App()
    try:
        d = _driving(app)
        _on_ramp(d, control, red=True, mph=5.0)
        held: list[str] = []
        released: list[bool] = []
        d.ctx.audio.hold_alert = lambda key, volume=1.0, fade_ms=60: held.append(key)
        d.ctx.audio.release_alert = lambda fade_ms=120: released.append(True)
        d.ctx.audio.play = lambda *a, **k: None
        d.ctx.say_event = lambda *a, **k: None

        # Creeping inside the last leeway: the tone sounds, and keeps being
        # asserted for as long as it applies.
        d._ramp_mi = RAMP_ACCESS_MI + RAMP_BAR_SOLID_MI / 2.0
        for _ in range(10):
            d._update_ramp_light(0.05)
        assert held.count("vehicle/bar_solid") == 10
        assert d._bar_solid_on

        # The bar is crossed and the terminal is settled. From here the road
        # has nothing left to warn about: the tone stops, and stays stopped.
        d._ramp_terminal_done = True
        d._ramp_mi = RAMP_ACCESS_MI - 0.01
        held.clear()
        for _ in range(20):
            d._update_ramp_light(0.05)
        assert released, "the solid tone was left sounding past the stop bar"
        assert not held
        assert not d._bar_solid_on

        # And once the ramp itself is over, still silent.
        d._ramp_mi = None
        d._update_ramp_light(0.05)
        assert not held
    finally:
        app.shutdown()


def test_a_held_alert_tone_stops_when_nobody_is_holding_it():
    """The tone is a dead man's switch at the audio layer too: whatever else
    goes wrong -- a menu taking the frame, a state ending mid-alert -- a
    continuous tone in a player's headphones lapses on its own."""
    from freight_fate.audio import ALERT_HOLD_TIMEOUT_S, CH_ALERT, AudioEngine

    audio = AudioEngine()
    started: list[tuple[int, str]] = []
    stopped: list[int] = []
    audio.start_loop = lambda ch, key, volume=1.0, fade_ms=300: started.append((ch, key))
    audio.stop_loop = lambda ch, fade_ms=300: stopped.append(ch)

    audio.hold_alert("vehicle/bar_solid", volume=0.85)
    assert started == [(CH_ALERT, "vehicle/bar_solid")]

    # Re-asserted every frame, it holds.
    for _ in range(20):
        audio.hold_alert("vehicle/bar_solid", volume=0.85)
        audio.update(0.05)
    assert not stopped

    # The holder stops calling: the tone goes quiet on its own, promptly.
    elapsed = 0.0
    while not stopped and elapsed < 5.0:
        audio.update(0.05)
        elapsed += 0.05
    assert stopped == [CH_ALERT]
    assert elapsed <= ALERT_HOLD_TIMEOUT_S + 0.1

    # Silent stays silent: no repeat stops, and no tone the player never asked
    # for coming back.
    for _ in range(20):
        audio.update(0.05)
    assert stopped == [CH_ALERT]


def test_hairpin_approach_pins_the_clock_to_real_time():
    """The pacenote lead is sized in real reaction-plus-braking seconds, but
    compression spent them in a blink: "Hairpin right, a quarter mile" did
    not finish speaking before the braking point (owner, 2026-07-24). Inside
    a sharp bend's warning window the clock runs real, and it releases once
    the curve is behind the truck."""
    from types import SimpleNamespace

    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip.time_scale = 10.0
        d.truck.velocity_mps = 55.0 / 2.2369362920544
        assert d.trip.effective_time_scale > 8.0

        mile = d.trip.position_mi
        d.trip.curves = [
            SimpleNamespace(
                start_mi=mile + 0.3,
                apex_mi=mile + 0.35,
                end_mi=mile + 0.4,
                direction="R",
                advisory_mph=25,
                min_radius_ft=120,
                deflection_deg=150.0,
                severity="hairpin",
                connector=False,
            )
        ]
        assert d.trip.effective_time_scale == 1.0

        # Slow enough for the bend already: no pacenote, no decompression.
        d.truck.velocity_mps = 20.0 / 2.2369362920544
        assert d.trip.effective_time_scale > 1.0

        # Curve behind the truck: full compression returns.
        d.truck.velocity_mps = 55.0 / 2.2369362920544
        d.trip.position_mi = mile + 0.5
        assert d.trip.effective_time_scale > 8.0
    finally:
        app.shutdown()


def _approaching_a_terminal(app, monkeypatch, control: str, *, mph: float = 45.0):
    """A real drive rolling down a ramp toward a red terminal control."""
    from driving_feature_helpers import key_event, quiet_trip, start_drive

    class NoKeys:
        def __getitem__(self, _key):
            return False

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())
    driving = start_drive(app)
    quiet_trip(driving)
    driving.trip.traffic_context = lambda: None
    driving.trip.grade_at = lambda mile: 0.0
    driving.handle_event(key_event(pygame.K_e))
    t = driving.truck
    t.cargo_kg = 15000.0
    t.velocity_mps = mph / 2.2369362920544
    driving._ramp_stop = driving.trip.stops[0]
    driving._ramp_mi = 0.5
    driving._ramp_control = control
    driving._ramp_light_offset_s = 0.0  # red
    driving._ramp_light_timer = 0.0
    driving._ramp_light_announced = True
    driving._ramp_light_last_phase = "red"
    driving._ramp_terminal_done = False
    driving._ramp_waiting_at_light = False
    driving._ramp_assist_brake = 0.0
    return driving


def test_route_transition_assistance_stops_at_the_sign_on_the_air_it_has(monkeypatch):
    """The owner's report: the assist ran the tanks out stopping at a sign.

    Its floor of a third of the pedal took off far more than its own 0.6 m/s2
    trigger asked for, so the demand collapsed under the application, the
    assist let go, the demand climbed back, and round it went -- 276 brake
    applications on one flat approach, 125 psi down to 40, spring brakes on,
    and the truck stopped in the road short of the bar.
    """
    from freight_fate.app import App
    from freight_fate.sim.vehicle import TruckState

    app = App()
    said = []
    try:
        driving = _approaching_a_terminal(app, monkeypatch, "stop")
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(said))
        t = driving.truck
        # The air system charges for how far the pedal RISES, so that -- not
        # the number of frames it moved on -- is the cost of the approach.
        charged = {"rise": 0.0}
        original = TruckState._consume_brake_air

        def counting(self, dt):
            rising = min(1.0, self.brake) - self._last_service_air_application
            if rising > 1e-9:
                charged["rise"] += rising
            original(self, dt)

        monkeypatch.setattr(TruckState, "_consume_brake_air", counting)
        lowest_psi = t.air_pressure_psi
        for _ in range(60 * 120):
            driving.update(1 / 60)
            lowest_psi = min(lowest_psi, t.air_pressure_psi)
            if driving._ramp_terminal_done:
                break
        assert driving._ramp_terminal_done
        assert t.speed_mph <= RED_STOP_MPH, t.speed_mph
        assert "Stopped at the sign. Clear; pull ahead to the entrance." in said
        assert lowest_psi > 60.0, lowest_psi  # never even reached the low-air warning
        assert not t.spring_brakes_active
        # A pedal that only ever rises toward the bar can cost one full
        # application at most; the old release-and-remake cost thirty.
        assert charged["rise"] <= 4.0, charged
    finally:
        app.shutdown()


def test_route_transition_assistance_does_not_chatter_at_the_ramp_cap(monkeypatch):
    """One threshold decided both ways announced itself over and over."""
    from freight_fate.app import App

    app = App()
    said = []
    try:
        driving = _approaching_a_terminal(app, monkeypatch, "stop", mph=46.0)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(said))
        for _ in range(60 * 120):
            driving.update(1 / 60)
            if driving._ramp_terminal_done:
                break
        released = sum(e == "Route-transition assistance released." for e in said)
        assert released <= 1, said
    finally:
        app.shutdown()


def _ready_to_exit(app, monkeypatch, spoken, *, mph: float = 40.0):
    """A drive with an armed speed-control session, right at its exit."""
    d = _driving(app)
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    app.ctx.settings.route_transition_assist = True
    app.ctx.settings.speed_keeper = True
    d.truck.set_air_ready(parking_brake=False)
    d.truck.start_engine()
    d.truck.velocity_mps = mph / 2.2369362920544
    return d


def _take_the_exit(d, control: str = "stop", *, stop=None):
    """Drive the real exit-take path onto a ramp ending in ``control``."""
    from freight_fate.sim.trip_models import RoadStop

    d.trip.ramp_control_at = lambda mile: control
    if stop is None:
        stop = RoadStop("Test Plaza", d.trip.position_mi, "travel_center", ("rest",))
        stop.exit_label = ""
    d._exit_stop = stop
    d._exit_signal_on = True
    d._exit_signal_canceled = False
    d._exit_lane_alignment = 1.0
    d.lane.lane = 0
    d.trip.position_mi = stop.at_mi
    d._update_exit(0.0)
    return stop


def _honor_the_bar_and_drive_on(d):
    """Stop at the bar, pull away from it, and leave the ramp behind."""
    d.truck.velocity_mps = 0.0
    d._ramp_mi = RAMP_ACCESS_MI
    d._resume_speed_control_if_ready(braking=False)
    d.truck.brake = 0.0
    d.truck.velocity_mps = 3.0  # rolling to the entrance, still on the ramp
    d._resume_speed_control_if_ready(braking=False)
    d._ramp_mi = None  # the ramp is behind the truck


def test_ramp_terminal_hands_adaptive_cruise_back_after_the_stop_bar(monkeypatch):
    """Shane, 2026-08-15: taking an exit killed adaptive cruise and the speed
    keeper for the rest of the run, and only the resume key brought them back.

    The bar is a transit stop, not an arrival: honor it, drive on, and
    automatic speed control is simply there again."""
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _ready_to_exit(app, monkeypatch, spoken)
        d.trip.speed_limit_at = lambda mile: (65.0, None)
        d._engage_cruise(40.0)

        _take_the_exit(d)
        assert d._ramp_mi is not None  # the ramp really was taken
        # The ramp takes the pedals back, but not the session.
        assert d._cruise_mph is None
        assert d._speed_control_armed
        assert d._speed_control_paused_at_stop

        # Route-transition assistance brakes for the sign.
        d._ramp_light_announced = True
        d._ramp_mi = 0.22
        d._update_ramp_terminal_assist()
        assert d._ramp_assist_said
        assert d._speed_control_paused_at_stop

        _honor_the_bar_and_drive_on(d)
        d.truck.velocity_mps = 40.0 / 2.2369362920544
        d._resume_speed_control_if_ready(braking=False)

        # No key was pressed anywhere in that sequence.
        assert d._cruise_mph == pytest.approx(40.0)
        assert not d._speed_control_paused_at_stop
        # The existing resume line, once, and no new line about the pause.
        assert sum("Adaptive cruise resuming" in t for t in spoken) == 1
        assert not any("paus" in t.lower() for t in spoken), spoken
    finally:
        app.shutdown()


def test_ramp_terminal_hands_the_speed_keeper_back_after_the_stop_bar(monkeypatch):
    """The same for the keeper: it dies with cruise and must come back with it."""
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _ready_to_exit(app, monkeypatch, spoken, mph=25.0)
        d.trip.speed_limit_at = lambda mile: (25.0, "facility access road")
        d._engage_keeper(25.0, "facility access road")
        assert d._keeper_mph == pytest.approx(25.0)

        _take_the_exit(d)
        assert d._ramp_mi is not None
        assert d._keeper_mph is None
        assert d._speed_control_armed

        _honor_the_bar_and_drive_on(d)
        d.truck.velocity_mps = 15.0 / 2.2369362920544
        d._resume_speed_control_if_ready(braking=False)

        assert d._keeper_mph == pytest.approx(25.0)
        assert not d._speed_control_paused_at_stop
        assert sum("Automatic speed control resuming" in t for t in spoken) == 1
    finally:
        app.shutdown()


def test_speed_control_stays_off_on_the_creep_to_the_stop_bar(monkeypatch):
    """The trap the pause exists for: nothing re-engages while the truck is
    still slowing toward the bar, or rolling the last of the ramp to the
    entrance behind it."""
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _ready_to_exit(app, monkeypatch, spoken)
        d.trip.speed_limit_at = lambda mile: (65.0, None)
        d._engage_cruise(40.0)
        _take_the_exit(d)

        d._ramp_mi = 0.2
        for mph in (35.0, 20.0, 10.0, 2.0, 0.0):
            d.truck.velocity_mps = mph / 2.2369362920544
            d._resume_speed_control_if_ready(braking=False)
            assert d._cruise_mph is None, mph
            assert d._keeper_mph is None, mph

        # Stopped, then rolling again -- but the entrance is still ahead.
        d.truck.brake = 0.0
        d._ramp_mi = 0.08
        d.truck.velocity_mps = 20.0 / 2.2369362920544
        d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph is None
        assert d._keeper_mph is None
    finally:
        app.shutdown()


def test_an_arrival_pause_still_waits_for_departure(monkeypatch):
    """A pickup or delivery gate is an arrival, not a transit stop: it holds
    the session until the player departs, however long the truck rolls."""
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _ready_to_exit(app, monkeypatch, spoken)
        d.trip.speed_limit_at = lambda mile: (65.0, None)
        d._engage_cruise(40.0)

        assert d._pause_speed_control()  # the gate flavour: no resume_when_rolling
        d.truck.velocity_mps = 0.0
        d._resume_speed_control_if_ready(braking=False)
        d.truck.velocity_mps = 40.0 / 2.2369362920544
        for _ in range(5):
            d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph is None
        assert d._speed_control_paused_at_stop

        # Departing is what lets it back on.
        d._restore_speed_control_session(armed=True, target_mph=40.0)
        d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph == pytest.approx(40.0)
    finally:
        app.shutdown()


def test_the_destination_ramp_still_holds_speed_control_to_the_gate(monkeypatch):
    """The regression guard. A destination exit is an arrival: its ramp ends at
    the facility gate, and cruise winding back up on it is what drove an owner
    playtest past the terminal at 66 mph."""
    from freight_fate.app import App
    from freight_fate.sim.trip_models import RoadStop

    app = App()
    spoken = []
    try:
        d = _ready_to_exit(app, monkeypatch, spoken)
        d.trip.speed_limit_at = lambda mile: (65.0, None)
        d._engage_cruise(40.0)
        destination = RoadStop(
            "Rochester Freight Market",
            d.trip.position_mi,
            "delivery_destination",
            ("deliver",),
        )
        destination.exit_label = ""
        destination.exit_phrase = ""

        _take_the_exit(d, stop=destination)
        assert d._speed_control_paused_at_stop
        assert not d._speed_control_transit_pause

        _honor_the_bar_and_drive_on(d)
        d.truck.velocity_mps = 40.0 / 2.2369362920544
        for _ in range(5):
            d._resume_speed_control_if_ready(braking=False)

        assert d._cruise_mph is None
        assert d._keeper_mph is None
        assert d._speed_control_paused_at_stop
    finally:
        app.shutdown()


def test_a_green_ramp_light_rolled_through_still_hands_speed_control_back(monkeypatch):
    """No stop was ever required, so nothing can be waiting for one: the ramp
    falling behind the truck is how a green terminal is honored."""
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _ready_to_exit(app, monkeypatch, spoken)
        d.trip.speed_limit_at = lambda mile: (65.0, None)
        d._engage_cruise(40.0)
        _take_the_exit(d, "signal")
        assert d._speed_control_transit_pause

        # Rolled the whole ramp and through a green: never below a walk.
        d._ramp_mi = 0.2
        d.truck.velocity_mps = 20.0 / 2.2369362920544
        d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph is None  # still on the ramp
        assert not d._speed_control_stop_honored

        d._ramp_mi = None
        d.truck.velocity_mps = 40.0 / 2.2369362920544
        d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph == pytest.approx(40.0)
    finally:
        app.shutdown()


def test_a_weigh_station_ramp_hands_speed_control_back_after_check_in(monkeypatch):
    """A scale is a transit stop like any other: pull in, check in, drive on."""
    from freight_fate.app import App
    from freight_fate.sim.trip_models import RoadStop

    app = App()
    spoken = []
    try:
        d = _ready_to_exit(app, monkeypatch, spoken)
        d.trip.speed_limit_at = lambda mile: (65.0, None)
        d._engage_cruise(40.0)
        scale = RoadStop(
            "Ontario Scale", d.trip.position_mi, "weigh_station", ("inspect",), parking="none"
        )
        scale.exit_label = ""

        _take_the_exit(d, stop=scale)
        assert d._speed_control_transit_pause
        _honor_the_bar_and_drive_on(d)
        d.truck.velocity_mps = 40.0 / 2.2369362920544
        d._resume_speed_control_if_ready(braking=False)

        assert d._cruise_mph == pytest.approx(40.0)
    finally:
        app.shutdown()


def test_a_manual_takeover_on_the_ramp_is_never_undone(monkeypatch):
    """The player's own pedal keeps the resume waiting, and switching speed
    control off on the ramp keeps it off past the bar."""
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _ready_to_exit(app, monkeypatch, spoken)
        d.trip.speed_limit_at = lambda mile: (65.0, None)
        d._engage_cruise(40.0)
        _take_the_exit(d)

        # Braking down the ramp and away from the bar: never resumes under
        # the player's own foot.
        d._ramp_mi = None
        d.truck.velocity_mps = 40.0 / 2.2369362920544
        for _ in range(5):
            d._resume_speed_control_if_ready(braking=True)
        assert d._cruise_mph is None
        assert d._speed_control_paused_at_stop

        # Switching it off is final: the resume cannot bring back a session
        # the player ended.
        d._toggle_cruise()
        assert not d._speed_control_armed
        for _ in range(5):
            d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph is None
        assert d._keeper_mph is None
    finally:
        app.shutdown()


def test_a_stalled_or_backing_truck_at_the_bar_never_resumes(monkeypatch):
    """Speed control needs a running engine and forward motion. ``speed_mph``
    is unsigned, so a truck backing off the bar reads as rolling."""
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _ready_to_exit(app, monkeypatch, spoken)
        d.trip.speed_limit_at = lambda mile: (65.0, None)
        d._engage_cruise(40.0)
        _take_the_exit(d)
        d.truck.velocity_mps = 0.0
        d._resume_speed_control_if_ready(braking=False)
        d._ramp_mi = None

        d.truck.stalled = True
        d.truck.velocity_mps = 20.0 / 2.2369362920544
        d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph is None

        d.truck.stalled = False
        d.truck.engine_on = False
        d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph is None

        # Backing away from the bar is not driving on from it.
        d.truck.engine_on = True
        d.truck.velocity_mps = -3.0
        for _ in range(5):
            d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph is None
        assert d._keeper_mph is None

        # Rolling forward again is what finally hands it back.
        d.truck.velocity_mps = 20.0 / 2.2369362920544
        d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph == pytest.approx(40.0)
    finally:
        app.shutdown()


def test_reloading_mid_ramp_never_leaves_speed_control_stuck(monkeypatch):
    """A save carries the session, not the ramp, so a reload must not come
    back holding a pause for a ramp that is no longer there."""
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _ready_to_exit(app, monkeypatch, spoken)
        d.trip.speed_limit_at = lambda mile: (65.0, None)
        d._engage_cruise(40.0)
        _take_the_exit(d)
        assert d.snapshot()["speed_control_armed"]

        # What restoring that snapshot does to the session.
        d._ramp_mi = None
        d._restore_speed_control_session(armed=True, target_mph=40.0)
        assert not d._speed_control_paused_at_stop
        assert not d._speed_control_transit_pause

        d.truck.velocity_mps = 40.0 / 2.2369362920544
        d._resume_speed_control_if_ready(braking=False)
        assert d._cruise_mph == pytest.approx(40.0)
    finally:
        app.shutdown()


def _priority_recorder(calls):
    """Record (text, priority) for every event line the ramp speaks."""

    def _say(text, interrupt: bool = True, **kwargs):
        calls.append((str(text), kwargs.get("priority")))

    return _say


def test_the_ramp_coaching_outranks_chatter():
    """The lines that get you to the bar must not wait behind the road.

    Every one of them defaulted to AMBIENT, which waits the full stale budget
    behind whatever is speaking. On a real ramp the pacer dropped the assist's
    own "braking for the light" sixteen milliseconds after the yellow call,
    and "through on the yellow" behind that -- so the truck braked for the
    light and the driver was told none of it (owner playtest, 2026-08-15).
    """
    from freight_fate.app import App
    from freight_fate.speech_pacing import EventPriority

    app = App()
    calls: list[tuple[str, object]] = []
    try:
        d = _driving(app)
        app.ctx.say_event = _priority_recorder(calls)
        app.ctx.settings.route_transition_assist = True

        # The light changing under the driver, and the assist acting on it.
        _on_ramp(d, "signal", red=True, mph=35.0)
        d._ramp_light_last_phase = "green"
        d._update_ramp_light(0.1)
        d._ramp_mi = RAMP_ACCESS_MI + 0.08
        d.truck.brake = 0.0
        d.truck.throttle = 0.5
        d._update_ramp_terminal_assist()

        spoken = [text for text, _ in calls]
        assert any("turns red" in text for text in spoken), spoken
        assert any("assistance braking" in text for text in spoken), spoken
        for text, priority in calls:
            assert priority == EventPriority.ROUTE, (text, priority)
    finally:
        app.shutdown()


def test_being_stranded_short_of_the_bar_is_never_dropped_as_chatter():
    """Owner playtest, 2026-08-17: stopped 1,350 feet short through a whole
    green-yellow-red cycle with nothing said.

    The game produced exactly the right line -- "Drive up and stop at the
    bar; the red is the time to close the gap" -- and the pacer dropped it as
    stale ambient. It is not chatter: it is an instruction about a STANDING
    condition, and the truck stays stopped until the driver acts, so the
    staleness rule was reading a moment that had not passed. The same failure
    is recorded in the code from 2026-07-19, which is why this is pinned.
    """
    from freight_fate.app import App
    from freight_fate.speech_pacing import EventPriority

    line = (
        "You are stopped about 1,350 feet short of the light. Drive up and "
        "stop at the bar; the red is the time to close the gap."
    )
    app = App()
    try:
        app.ctx.settings.sapi_events = True
        said = []
        app.ctx.speech.say_event = lambda t, interrupt=True: said.append(t)
        # Back the channel up the way a busy ramp approach does.
        for _ in range(5):
            app.ctx._event_pacer.note_queued("Brake lights right ahead.", EventPriority.CRITICAL)
        app.ctx.say_event(line, interrupt=False, priority=EventPriority.ROUTE)
        assert said, "a standing instruction must survive a backed-up channel"
    finally:
        app.shutdown()


def test_the_stranded_prompts_ask_for_route_priority():
    """Pinned at the call site too: the default is AMBIENT, and AMBIENT is
    the one priority the stale-drop branch throws away."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src" / "freight_fate"
    text = (src / "states" / "driving_events.py").read_text(encoding="utf-8")
    for marker in ("short of the stop sign", "short of the light. Drive"):
        i = text.index(marker)
        window = text[i : i + 1400]
        assert "EventPriority.ROUTE" in window, marker
