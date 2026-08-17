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
        d.ctx.settings.lane_keeping = "off"
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


def test_road_bed_leans_toward_the_correction_on_a_drift(monkeypatch):
    from freight_fate.app import App
    from freight_fate.audio import CH_ROAD

    app = App()
    try:
        d = _driving(app)
        d.ctx.settings.lane_keeping = "off"
        d.truck.velocity_mps = 25.0  # guidance only listens at speed
        pans = []
        monkeypatch.setattr(
            app.ctx.audio,
            "set_loop_pan",
            lambda ch, pan: pans.append(pan) if ch == CH_ROAD else None,
        )

        d.lane.offset = -0.6  # drifting left: the wheel should go right
        d._update_audio(0.5)

        assert pans and pans[-1] > 0.0  # the road bed leans right -- follow it
    finally:
        app.shutdown()


def test_road_bed_slews_home_and_centered_cue_ends_a_drift(monkeypatch):
    from freight_fate.app import App
    from freight_fate.audio import CH_ROAD

    app = App()
    try:
        d = _driving(app)
        d.ctx.settings.lane_keeping = "off"
        d.truck.velocity_mps = 25.0  # guidance only listens at speed
        calls = []
        pans = []
        monkeypatch.setattr(
            app.ctx.audio,
            "play",
            lambda key, volume=1.0, pan=0.0: calls.append((key, volume, pan)),
        )
        monkeypatch.setattr(
            app.ctx.audio,
            "set_loop_pan",
            lambda ch, pan: pans.append(pan) if ch == CH_ROAD else None,
        )

        d.lane.offset = 0.6  # drift right wakes the guide
        d._update_audio(0.5)
        d.lane.offset = 0.05  # settled back to center
        for _ in range(4):
            d._update_audio(0.5)

        assert pans and pans[-1] == pytest.approx(0.0)  # bed back home
        assert ("vehicle/lane_centered", pytest.approx(0.45), pytest.approx(0.0)) in calls
    finally:
        app.shutdown()


def test_guidance_stays_asleep_inside_normal_wander(monkeypatch):
    from freight_fate.app import App
    from freight_fate.audio import CH_ROAD

    app = App()
    try:
        d = _driving(app)
        d.ctx.settings.lane_keeping = "off"
        d.truck.velocity_mps = 25.0  # guidance only listens at speed
        pans = []
        monkeypatch.setattr(
            app.ctx.audio,
            "set_loop_pan",
            lambda ch, pan: pans.append(pan) if ch == CH_ROAD else None,
        )

        d.lane.offset = 0.35  # ordinary wander, inside the wake line
        d._update_audio(0.5)

        assert not [pan for pan in pans if pan != 0.0], (
            "centered-and-stable must leave the road bed home"
        )
    finally:
        app.shutdown()


def test_transverse_strips_fire_once_at_the_marked_mile(monkeypatch):
    """The dead-man's-curve bars are road furniture: cross them, hear them --
    any speed, any assist mode, exactly once."""
    from freight_fate.app import App
    from freight_fate.sim.lane_guidance import TRANSVERSE_KEY

    app = App()
    try:
        d = _driving(app)
        d.ctx.settings.lane_keeping = "full"  # even with drift off
        d.truck.velocity_mps = 25.0
        d._transverse_strip_miles = (5.0,)
        d._transverse_fired = set()
        calls = []
        monkeypatch.setattr(
            app.ctx.audio, "play", lambda key, volume=1.0, pan=0.0: calls.append(key)
        )
        d.trip.position_mi = 4.9
        d._update_transverse_strips()
        assert TRANSVERSE_KEY not in calls  # not there yet
        d.trip.position_mi = 5.1
        d._update_transverse_strips()
        d._update_transverse_strips()
        assert calls.count(TRANSVERSE_KEY) == 1  # once, not per frame
    finally:
        app.shutdown()


def test_lane_locator_toggle_and_panned_tick(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _driving(app)
        d.ctx.say = lambda text, **kw: spoken.append(text)
        d.truck.velocity_mps = 25.0

        d.ctx.settings.lane_keeping = "full"
        d._toggle_lane_locator()
        assert not d._lane_locator_on  # refused: nothing to locate
        assert "holds the lane" in spoken[-1]

        d.ctx.settings.lane_keeping = "off"
        d._toggle_lane_locator()
        assert d._lane_locator_on
        calls = []
        monkeypatch.setattr(
            app.ctx.audio, "play", lambda key, volume=1.0, pan=0.0: calls.append((key, pan))
        )
        d.lane.offset = 0.8  # sitting right of center
        d._update_lane_locator_audio(1.0)
        ticks = [pan for key, pan in calls if key == "vehicle/lane_locator"]
        assert ticks and ticks[-1] == pytest.approx(0.8)
        d._toggle_lane_locator()
        assert not d._lane_locator_on
    finally:
        app.shutdown()


def test_cue_loudness_scales_the_edge_rung():
    from freight_fate.sim.lane_guidance import edge_rung

    _, standard = edge_rung(1.05, boundary="shoulder", loudness=1.0)
    _, subtle = edge_rung(1.05, boundary="shoulder", loudness=0.6)
    _, prominent = edge_rung(1.05, boundary="shoulder", loudness=1.35)
    assert subtle < standard < prominent <= 1.0


def test_a_hot_bend_actually_pushes_the_truck(monkeypatch):
    """A 30-advisory bend taken 15 over must demand real counter-steering:
    unopposed, the truck reaches the lane line in a handful of seconds.
    Pins the curve-push scaling against the double-CURVE_RATE bug that let
    every bend be driven no-hands (owner-caught on Camp Verde-Payson)."""
    from types import SimpleNamespace

    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.ctx.settings.lane_keeping = "off"
        d.ctx.settings.curve_speed_assist = False
        d.truck.velocity_mps = 45.0 / 2.23694
        bend = SimpleNamespace(
            start_mi=0.0,
            end_mi=1.0,
            advisory_mph=30.0,
            min_radius_ft=235.0,
            direction="L",
            connector=False,
            severity="curve",
        )
        monkeypatch.setattr(d.trip, "curve_at", lambda mile: bend)
        from collections import defaultdict

        no_keys = defaultdict(bool)  # hands off the wheel
        for _ in range(8 * 60):  # eight seconds through the bend
            d._update_lane(no_keys, 1 / 60)
        # A left bend pushes the truck right, toward the outside.
        assert d.lane.offset > 0.45, d.lane.offset
    finally:
        app.shutdown()


def test_pinballing_across_a_line_keeps_only_the_thump(monkeypatch):
    """The first crossing gets the marker roll, the signal tone, and the
    spoken lane. Re-crossing inside the repeat window is fighting the bend,
    not changing lanes: quieter thump only, no ding, no announcement."""
    from freight_fate.app import App

    app = App()
    events = []
    try:
        d = _driving(app)
        d.ctx.settings.lane_keeping = "off"
        d.ctx.say_event = lambda text, interrupt=False, **_: events.append(text)
        d.truck.velocity_mps = 25.0
        played = []
        monkeypatch.setattr(
            app.ctx.audio, "play", lambda key, volume=1.0, pan=0.0: played.append((key, volume))
        )

        d.lane.lane = 0
        d.lane.crossed = 1
        d._on_lane_crossed()
        assert any(k == "vehicle/signal_tone" for k, _ in played)
        assert any("lane" in e for e in events)

        played.clear()
        events.clear()
        d.lane.crossed = -1  # right back across, mid-fight
        d._on_lane_crossed()
        rolls = [(k, v) for k, v in played if k == "vehicle/lane_line_cross"]
        assert rolls and rolls[0][1] < 0.7  # quieter thump
        assert not any(k == "vehicle/signal_tone" for k, _ in played)
        assert not any("In the" in e for e in events)
    finally:
        app.shutdown()


def test_curve_run_speaks_a_verdict_on_exit(monkeypatch):
    """The co-driver closes the loop: entering a demanding bend ticks on its
    side, and leaving it earns a spoken verdict -- clean, edge, or hot."""
    from types import SimpleNamespace

    from freight_fate.app import App

    app = App()
    events = []
    try:
        d = _driving(app)
        d.ctx.settings.lane_keeping = "off"
        d.ctx.settings.curve_callouts = True
        d.ctx.settings.speech_verbosity = 1
        d.ctx.say_event = lambda text, interrupt=False, **_: events.append(text)
        d.truck.velocity_mps = 30.0 / 2.23694
        ticks = []
        monkeypatch.setattr(
            app.ctx.audio, "play", lambda key, volume=1.0, pan=0.0: ticks.append((key, pan))
        )
        monkeypatch.setattr(d.trip, "curve_ahead_mi", lambda lead: None)
        bend = SimpleNamespace(
            start_mi=1.0,
            end_mi=1.3,
            advisory_mph=30.0,
            min_radius_ft=235.0,
            direction="L",
            connector=False,
            severity="curve",
        )

        d._update_curve_run(bend)  # entering
        assert ("vehicle/curve_bink", pytest.approx(-0.85)) in ticks  # left bend, left ear
        d._update_curve_run(bend)  # riding it, clean and at advisory
        d._update_curve_run(None)  # out the far side
        assert events and "held your line" in events[-1]

        # A hot run says so instead.
        d.truck.velocity_mps = 50.0 / 2.23694
        d._update_curve_run(bend)
        d._update_curve_run(None)
        assert "hot" in events[-1]
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


def test_the_engine_steps_back_while_the_road_is_leaning():
    """The lean carries its meaning in the pan of the road bed, and that bed
    is recorded about 15 dB under the engine with the road channel already at
    full gain by highway speed -- there is no headroom to raise it. So the
    engine ducks instead, the way it does for speech, and only while the guide
    is actually leaning (owner and Darren, 2026-08-17)."""
    from freight_fate.app import App
    from freight_fate.audio import GUIDE_DUCK_LEVEL

    assert 0.0 < GUIDE_DUCK_LEVEL < 1.0
    app = App()
    try:
        audio = app.ctx.audio
        impl = audio._impl
        if not hasattr(impl, "_guide_duck"):
            pytest.skip("headless null backend carries no mix state")
        assert impl._guide_duck == 1.0  # straight road: nothing to say

        audio.set_guidance_duck(True)
        assert impl._guide_duck == GUIDE_DUCK_LEVEL

        audio.set_guidance_duck(False)
        assert impl._guide_duck == 1.0
    finally:
        app.shutdown()


def test_the_guide_duck_and_the_shift_gap_duck_are_independent():
    """A gear change mid-bend must not cancel the room the lean was given."""
    from freight_fate.app import App
    from freight_fate.audio import GUIDE_DUCK_LEVEL

    app = App()
    try:
        audio = app.ctx.audio
        impl = audio._impl
        if not hasattr(impl, "_guide_duck"):
            pytest.skip("headless null backend carries no mix state")
        audio.set_guidance_duck(True)
        audio.set_engine_duck(0.6)  # a shift gap lands during the lean
        assert impl._guide_duck == GUIDE_DUCK_LEVEL
        assert impl._engine_duck == 0.6
        audio.set_engine_duck(1.0)  # the shift finishes
        assert impl._guide_duck == GUIDE_DUCK_LEVEL, "the lean keeps its room"
    finally:
        app.shutdown()
