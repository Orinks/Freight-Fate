"""The steering lane cue: hearing your position in the lane while you steer.

The lane locator used to need the I key. Taking an exit with the lane work
yours means holding a position at the right of the lane, and that position
was the one thing on the road a blind driver could not hear (owner request,
2026-08-15). These tests pin what the move sounds like from the first held
arrow to the click that says the exit lane is set.
"""

import pytest
from speech_capture import speech_stub

from freight_fate.states.driving_core import (
    EXIT_LANE_READY,
    STEER_CUE_ARM_S,
    STEER_CUE_HOLD,
    STEER_CUE_TOCK_S,
)

LOCATOR = "vehicle/lane_locator"
SIGNAL = "vehicle/signal_tone"


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Steer", current_city="Buffalo")
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
    driving.ctx.settings.lane_keeping = "off"  # the lane work is the driver's
    driving.truck.velocity_mps = 25.0  # rolling, well over the cue's floor
    return driving


def _capture(monkeypatch, app):
    """Record every one-shot the cue plays: key, volume, pan."""
    calls: list[tuple[str, float, float]] = []
    monkeypatch.setattr(
        app.ctx.audio,
        "play",
        lambda key, volume=1.0, pan=0.0: calls.append((key, volume, pan)),
    )
    return calls


def _arm(driving, direction: float = 1.0) -> None:
    """Hold the wheel long enough that this is a move, not a correction."""
    driving.lane.steering = direction
    driving._update_steering_lane_cue(STEER_CUE_ARM_S)


def _signal_for_the_exit(driving) -> None:
    """An armed route exit, without needing a real stop on this leg."""
    driving._exit_stop = object()
    driving._exit_signal_on = True
    driving.lane.lane = 0  # ramps peel off the right lane


def test_holding_the_arrow_plays_the_position_tock_panned_to_the_lane(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = _capture(monkeypatch, app)
        d.lane.offset = 0.6  # already right of centre and still going right
        d.lane.steering = 1.0

        d._update_steering_lane_cue(STEER_CUE_ARM_S - 0.1)
        assert calls == []  # a nudge of the wheel is not a move

        d._update_steering_lane_cue(0.2)
        assert [(key, pan) for key, _vol, pan in calls] == [(LOCATOR, pytest.approx(0.6))]

        # It keeps time for as long as the wheel is held, and follows the truck.
        d.lane.offset = 0.95
        d._update_steering_lane_cue(STEER_CUE_TOCK_S)
        assert calls[-1][0] == LOCATOR
        assert calls[-1][2] == pytest.approx(0.95)
    finally:
        app.shutdown()


def test_the_tock_scales_with_the_lane_cue_loudness_setting(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = _capture(monkeypatch, app)
        d.ctx.settings.lane_cue_loudness = "subtle"
        _arm(d)
        assert calls[-1][0] == LOCATOR
        assert calls[-1][1] == pytest.approx(0.5 * 0.6)

        d.lane.steering = 0.0
        calls.clear()
        d._update_steering_lane_cue(1 / 60)
        assert calls[-1][0] == SIGNAL
        assert calls[-1][1] == pytest.approx(0.45 * 0.6)
    finally:
        app.shutdown()


def test_letting_go_of_the_wheel_cancels_the_signal(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = _capture(monkeypatch, app)
        _arm(d)
        assert calls and calls[0][0] == LOCATOR

        calls.clear()
        d.lane.steering = 0.0  # straightened out: the move is over
        d._update_steering_lane_cue(1 / 60)
        assert calls == [(SIGNAL, pytest.approx(0.45), 0.0)]  # centred, quieter
        assert not d._steer_cue_active

        # And it stays over: no second click, no stray tocks.
        calls.clear()
        for _ in range(120):
            d._update_steering_lane_cue(1 / 60)
        assert calls == []
    finally:
        app.shutdown()


def test_a_nudge_of_the_wheel_never_clicks(monkeypatch):
    """A drift correction is not a manoeuvre, so it gets no cue and no click."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = _capture(monkeypatch, app)
        d.lane.steering = -1.0
        d._update_steering_lane_cue(STEER_CUE_ARM_S - 0.2)
        d.lane.steering = 0.0
        d._update_steering_lane_cue(1 / 60)
        assert calls == []
    finally:
        app.shutdown()


def test_the_lane_change_ends_with_the_click_after_the_line_is_crossed(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.lane import LANE_WIDTH

    app = App()
    try:
        d = _driving(app)
        calls = _capture(monkeypatch, app)
        d.lane.lane = 0
        _arm(d, direction=-1.0)  # holding Left, moving toward the left lane
        d.lane.offset = -0.9
        d._update_steering_lane_cue(STEER_CUE_TOCK_S)
        assert calls[-1][2] == pytest.approx(-0.9)  # heard sliding left

        # The tires roll the line, the lane model re-centres in the new lane,
        # and the cue follows the truck through the settle.
        d.lane.lane = 1
        d.lane.offset = -0.9 + LANE_WIDTH
        d._update_steering_lane_cue(STEER_CUE_TOCK_S)
        assert calls[-1] == (LOCATOR, pytest.approx(0.5), pytest.approx(1.0))

        calls.clear()
        d.lane.steering = 0.0  # straightened up in the new lane
        d._update_steering_lane_cue(1 / 60)
        assert [key for key, _vol, _pan in calls] == [SIGNAL]
    finally:
        app.shutdown()


def test_the_beat_quickens_as_the_exit_lane_position_fills(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _capture(monkeypatch, app)
        _signal_for_the_exit(d)
        d._exit_lane_alignment = 0.0
        d.lane.offset = 0.0
        _arm(d)
        wide = d._steer_cue_timer
        assert wide == pytest.approx(STEER_CUE_TOCK_S)

        d._exit_lane_alignment = EXIT_LANE_READY - 0.05  # nearly there
        d._update_steering_lane_cue(wide)
        close = d._steer_cue_timer
        assert close < wide / 2
    finally:
        app.shutdown()


def test_reaching_the_exit_position_clicks_off_with_the_wheel_still_held(monkeypatch):
    """ "Far enough right now" arrives as the signal cancelling, not a sentence."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = _capture(monkeypatch, app)
        _signal_for_the_exit(d)
        d._exit_lane_alignment = 0.5
        _arm(d)
        assert calls[-1][0] == LOCATOR

        calls.clear()
        d._exit_lane_alignment = EXIT_LANE_READY  # the exit has the lane it needs
        d._update_steering_lane_cue(1 / 60)
        assert calls == [(SIGNAL, pytest.approx(0.45), 0.0)]
        assert d.lane.steering == 1.0  # the wheel is still over; the position is what ended it
        assert not d._steer_cue_active

        # Holding Right past the mark does not start it up again.
        calls.clear()
        for _ in range(120):
            d._update_steering_lane_cue(1 / 60)
        assert calls == []
    finally:
        app.shutdown()


def test_abandoning_the_exit_line_up_clicks_off_too(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = _capture(monkeypatch, app)
        _signal_for_the_exit(d)
        d._exit_lane_alignment = 0.4
        _arm(d)
        assert calls[-1][0] == LOCATOR

        calls.clear()
        d.lane.steering = 0.0
        d._exit_lane_alignment = 0.0  # steered back and let the commitment bleed away
        d._update_steering_lane_cue(1 / 60)
        assert [key for key, _vol, _pan in calls] == [SIGNAL]
    finally:
        app.shutdown()


def test_the_cue_stays_silent_under_lane_keeping_and_below_the_speed_floor(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = _capture(monkeypatch, app)
        d.ctx.settings.lane_keeping = "full"  # the truck holds the lane and takes the exit
        _signal_for_the_exit(d)
        d._exit_lane_alignment = 0.5
        for _ in range(120):
            d.lane.steering = 1.0
            d._update_steering_lane_cue(1 / 60)
        assert calls == []

        d.ctx.settings.lane_keeping = "off"
        d.truck.velocity_mps = 0.5  # about a walking pace: nothing to steer yet
        for _ in range(120):
            d.lane.steering = 1.0
            d._update_steering_lane_cue(1 / 60)
        assert calls == []
    finally:
        app.shutdown()


def test_it_does_not_double_the_locator_the_driver_already_turned_on(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = _capture(monkeypatch, app)
        d._lane_locator_on = True  # I is already ticking the same tock
        _signal_for_the_exit(d)
        d._exit_lane_alignment = 0.5
        for _ in range(120):
            d.lane.steering = 1.0
            d._update_steering_lane_cue(1 / 60)
        assert calls == []
    finally:
        app.shutdown()


def test_the_cue_cannot_survive_the_drive_losing_the_frame(monkeypatch):
    """A menu over the drive lets the latch lapse, and the move ends in
    silence -- never a signal cancelling over the pause screen."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = _capture(monkeypatch, app)
        _arm(d)
        assert app.ctx.audio.cue_held(STEER_CUE_HOLD)

        # A menu owns the frames now: the driving state stops updating while
        # the audio clock keeps running.
        app.ctx.audio.update(0.5)
        assert not app.ctx.audio.cue_held(STEER_CUE_HOLD)

        calls.clear()
        d.lane.steering = 0.0
        d._update_steering_lane_cue(1 / 60)
        assert calls == []
        assert not d._steer_cue_active
    finally:
        app.shutdown()


def test_the_whole_manoeuvre_adds_no_speech(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        _capture(monkeypatch, app)
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _signal_for_the_exit(d)
        d._exit_lane_alignment = 0.3
        for _ in range(240):
            d.lane.steering = 1.0
            d._exit_lane_alignment = min(1.0, d._exit_lane_alignment + 1 / 60)
            d._update_steering_lane_cue(1 / 60)
        d.lane.steering = 0.0
        d._update_steering_lane_cue(1 / 60)
        assert spoken == []
    finally:
        app.shutdown()
