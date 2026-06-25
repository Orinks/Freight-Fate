"""Directional lane-drift rumble: panned to the side you drifted toward."""

import pytest


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Pan", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(CARGO_CATALOG["general"], 12.0, "Buffalo", "company yard",
              "Rochester", route.miles, 1000.0, 12.0,
              destination_location="Rochester freight market")
    return DrivingState(app.ctx, job, route, phase="delivery")


def test_lane_pan_follows_the_drift_side():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.lane.offset = -1.0   # drifted left
        assert d._lane_pan() == pytest.approx(-1.0)
        d.lane.offset = 0.9    # drifted right
        assert d._lane_pan() == pytest.approx(0.9)
        d.lane.offset = 2.0    # clamped to full right
        assert d._lane_pan() == pytest.approx(1.0)
        d.lane.offset = 0.0
        assert d._lane_pan() == 0.0
    finally:
        app.shutdown()


def test_rumble_is_panned_to_the_drift_side(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.ctx.settings.steering_assist = "realistic"
        d.lane.offset = 1.0     # at the right edge -> rumble fires
        d._lane_rumble_timer = 0.0
        calls = []
        monkeypatch.setattr(app.ctx.audio, "play",
                            lambda key, volume=1.0, pan=0.0: calls.append((key, pan)))
        d._update_audio(0.0)
        rumble = [pan for key, pan in calls if key == "vehicle/rumble_strip"]
        assert rumble, "the rumble strip should sound at the lane edge"
        assert rumble[0] == pytest.approx(1.0)   # hard right
    finally:
        app.shutdown()


def test_audio_play_accepts_pan_on_the_active_backend():
    from freight_fate.audio import AudioEngine

    audio = AudioEngine()
    try:
        # Whatever backend is active (BASS no-sound, pygame, or null), panning
        # a one-shot must not raise.
        audio.play("ui/menu_select", pan=0.8)
        audio.play("ui/menu_select", pan=-0.8)
        audio.play("ui/menu_select")
    finally:
        audio.shutdown()
