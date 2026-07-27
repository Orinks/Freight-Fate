"""Directional lane-drift rumble: panned to the side you drifted toward."""

import pytest


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Pan", current_city="Buffalo")
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
    return DrivingState(app.ctx, job, route, phase="delivery")


def test_lane_pan_follows_the_drift_side():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.lane.offset = -1.0  # drifted left
        assert d._lane_pan() == pytest.approx(-1.0)
        d.lane.offset = 0.9  # drifted right
        assert d._lane_pan() == pytest.approx(0.9)
        d.lane.offset = 2.0  # clamped to full right
        assert d._lane_pan() == pytest.approx(1.0)
        d.lane.offset = 0.0
        assert d._lane_pan() == 0.0
    finally:
        app.shutdown()


def test_edge_ladder_loop_is_panned_to_the_drift_side(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.lane_guidance import EDGE_STRIP_KEY

    app = App()
    try:
        d = _driving(app)
        d.ctx.settings.steering_assist = "realistic"
        d.truck.velocity_mps = 25.0  # rolling: grooves make noise
        d.lane.offset = 1.0  # whole tire on the right-edge strip
        loops = []
        pans = []
        monkeypatch.setattr(
            app.ctx.audio,
            "start_loop",
            lambda ch, key, volume=1.0, fade_ms=300: loops.append(key),
        )
        monkeypatch.setattr(app.ctx.audio, "set_loop_volume", lambda ch, volume: None)
        monkeypatch.setattr(app.ctx.audio, "set_loop_pan", lambda ch, pan: pans.append(pan))
        d._update_audio(0.0)
        assert EDGE_STRIP_KEY in loops, "the strip loop should run at the lane edge"
        assert pans and pans[-1] == pytest.approx(1.0)  # hard right
    finally:
        app.shutdown()


def test_guidance_bed_wakes_panned_to_the_drift_side(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.lane_guidance import BED_KEY

    app = App()
    try:
        d = _driving(app)
        d.ctx.settings.steering_assist = "realistic"
        d.truck.velocity_mps = 25.0  # guidance only listens at speed
        loops = []
        pans = []
        monkeypatch.setattr(
            app.ctx.audio,
            "start_loop",
            lambda ch, key, volume=1.0, fade_ms=300: loops.append((ch, key, volume)),
        )
        monkeypatch.setattr(app.ctx.audio, "set_loop_volume", lambda ch, volume: None)
        monkeypatch.setattr(app.ctx.audio, "set_loop_pan", lambda ch, pan: pans.append(pan))

        d.lane.offset = -0.6  # drifting left, past the wake line
        d._update_audio(0.0)

        assert [entry for entry in loops if entry[1] == BED_KEY]
        assert pans and pans[-1] < 0.0  # the bed sits on the drift side
    finally:
        app.shutdown()


def test_guidance_bed_sleeps_and_centered_cue_ends_a_drift(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.ctx.settings.steering_assist = "realistic"
        d.truck.velocity_mps = 25.0  # guidance only listens at speed
        calls = []
        stops = []
        monkeypatch.setattr(
            app.ctx.audio,
            "play",
            lambda key, volume=1.0, pan=0.0: calls.append((key, volume, pan)),
        )
        monkeypatch.setattr(
            app.ctx.audio, "stop_loop", lambda ch, fade_ms=300: stops.append(ch)
        )

        d.lane.offset = 0.6  # drift right wakes the bed
        d._update_audio(0.0)
        d.lane.offset = 0.05  # settled back to center
        d._update_audio(0.0)

        from freight_fate.audio import CH_LANE

        assert CH_LANE in stops, "the guidance bed should stop once centered"
        assert ("vehicle/lane_centered", pytest.approx(0.45), pytest.approx(0.0)) in calls
    finally:
        app.shutdown()


def test_guidance_stays_asleep_inside_normal_wander(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.ctx.settings.steering_assist = "realistic"
        d.truck.velocity_mps = 25.0  # guidance only listens at speed
        loops = []
        monkeypatch.setattr(
            app.ctx.audio,
            "start_loop",
            lambda ch, key, volume=1.0, fade_ms=300: loops.append(key),
        )

        d.lane.offset = 0.35  # ordinary wander, inside the wake line
        d._update_audio(0.0)

        from freight_fate.sim.lane_guidance import BED_KEY

        assert BED_KEY not in loops, "centered-and-stable must stay silent"
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
