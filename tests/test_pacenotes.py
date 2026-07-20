"""The co-driver reads the road: spoken pacenotes from the baked curves.

First audible slice of the steering-by-ear design: curves that demand
slowing are called before they arrive, everything else stays silent, U
lists the next few bends, and D folds the bend into its one number.
"""

import pytest
from driving_feature_helpers import quiet_trip, start_drive

from freight_fate.data.curves import RouteCurve, leg_curves, route_curves
from freight_fate.settings import Settings
from freight_fate.sim.trip_models import TripEventKind


def _curve(start, direction="L", advisory=35, radius=307, deflection=60.0):
    return RouteCurve(
        start_mi=start,
        apex_mi=start + 0.05,
        end_mi=start + 0.1,
        direction=direction,
        advisory_mph=advisory,
        min_radius_ft=radius,
        deflection_deg=deflection,
    )


def test_shard_loads_mainline_curves_without_connectors():
    records = leg_curves("aberdeen_sd_us:pierre_sd_us")
    assert records, "the baked shard should cover this swept leg"
    assert all(r.direction in ("L", "R") for r in records)
    # Connector rows (interchange arcs) never reach the pacenote layer.
    assert all(r.advisory_mph > 0 for r in records)


def test_route_curves_mirror_reverse_legs(world):
    route = world.supported_route("aberdeen_sd_us", "pierre_sd_us")
    reverse = world.supported_route("pierre_sd_us", "aberdeen_sd_us")
    forward_curves = route_curves(route, route.cities)
    reverse_curves = route_curves(reverse, reverse.cities)
    assert forward_curves and reverse_curves
    assert len(forward_curves) == len(reverse_curves)
    # The same physical bend, met from the other end, turns the other way.
    first, mirrored = forward_curves[0], reverse_curves[-1]
    assert first.direction != mirrored.direction
    assert first.advisory_mph == mirrored.advisory_mph
    total = route.miles
    assert mirrored.start_mi == pytest.approx(total - first.end_mi, abs=0.01)


def test_severity_ladder():
    assert _curve(1.0, advisory=20).severity == "hairpin"
    assert _curve(1.0, advisory=45, deflection=170.0).severity == "hairpin"
    assert _curve(1.0, advisory=30).severity == "sharp"
    assert _curve(1.0, advisory=45).severity == "moderate"
    assert _curve(1.0, advisory=65).severity == "gentle"


def test_short_distance_text_units():
    s = Settings()
    assert s.short_distance_text(0.25) == "a quarter mile"
    assert s.short_distance_text(0.5) == "half a mile"
    assert s.short_distance_text(0.74) == "three quarters of a mile"
    assert s.short_distance_text(1.0) == "one mile"
    m = Settings()
    m.imperial_units = False
    assert m.short_distance_text(0.25) == "400 meters"
    assert m.short_distance_text(1.0) == "1.6 kilometers"


def _spoken_pacenotes(app, driving, monkeypatch, curves, speed_mph):
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
    driving.trip.curves = tuple(curves)
    driving.trip._announced_curves = set()
    driving.truck.velocity_mps = speed_mph * 0.44704
    for event in driving.trip.update(0):
        if event.kind == TripEventKind.CURVE:
            driving._handle_trip_event(event)
    return spoken


def test_pacenote_called_before_a_demanding_bend(monkeypatch):
    app_module = pytest.importorskip("freight_fate.app")
    app = app_module.App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        pos = driving.trip.position_mi
        spoken = _spoken_pacenotes(
            app, driving, monkeypatch, [_curve(pos + 0.3, "R", advisory=30)], 60.0
        )
        assert spoken, "a 30 mph bend at 60 mph demands a call"
        assert "Sharp right" in spoken[0]
        assert "Advise" in spoken[0]
        # The same frame never calls twice, and the next frame stays quiet.
        for event in driving.trip.update(0):
            if event.kind == TripEventKind.CURVE:
                driving._handle_trip_event(event)
        assert len(spoken) == 1
    finally:
        app.shutdown()


def test_pacenote_stays_silent_when_already_slow(monkeypatch):
    app_module = pytest.importorskip("freight_fate.app")
    app = app_module.App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        pos = driving.trip.position_mi
        spoken = _spoken_pacenotes(
            app, driving, monkeypatch, [_curve(pos + 0.3, advisory=55)], 50.0
        )
        assert spoken == [], "a bend you are already slow enough for stays silent"
    finally:
        app.shutdown()


def test_gentle_bends_only_call_when_truly_hot(monkeypatch):
    app_module = pytest.importorskip("freight_fate.app")
    app = app_module.App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        pos = driving.trip.position_mi
        # Five over a gentle 60 sweep is chatter, not help: silent.
        spoken = _spoken_pacenotes(
            app, driving, monkeypatch, [_curve(pos + 0.3, advisory=60, radius=2400)], 65.0
        )
        assert spoken == []
        # Twelve over the same sweep is genuinely hot: called.
        spoken = _spoken_pacenotes(
            app, driving, monkeypatch, [_curve(pos + 0.3, advisory=60, radius=2400)], 72.0
        )
        assert spoken and "Gentle bend" in spoken[0]
    finally:
        app.shutdown()


def test_pacenote_respects_the_setting(monkeypatch):
    app_module = pytest.importorskip("freight_fate.app")
    app = app_module.App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        app.ctx.settings.curve_callouts = False
        pos = driving.trip.position_mi
        spoken = _spoken_pacenotes(
            app, driving, monkeypatch, [_curve(pos + 0.3, advisory=25)], 60.0
        )
        assert spoken == []
    finally:
        app.shutdown()


def test_curve_event_uses_the_documented_short_pacenote_wording(monkeypatch):
    app_module = pytest.importorskip("freight_fate.app")
    app = app_module.App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        pos = driving.trip.position_mi
        spoken = _spoken_pacenotes(
            app, driving, monkeypatch, [_curve(pos + 0.3, "R", advisory=30)], 60.0
        )
        assert spoken == ["Sharp right, a quarter mile. Advise 30 miles per hour."]
    finally:
        app.shutdown()


def test_upcoming_curve_remains_eligible_after_resume(monkeypatch):
    app_module = pytest.importorskip("freight_fate.app")
    app = app_module.App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        spoken = []
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
        pos = driving.trip.position_mi
        curve = _curve(pos + 0.3, "L", advisory=30)
        driving.trip.curves = (curve,)
        driving.truck.velocity_mps = 60.0 * 0.44704

        driving.trip.restore(pos, driving.trip.game_minutes)
        key = f"curve:{curve.start_mi:.3f}:{curve.direction}"
        assert key not in driving.trip._announced_curves

        for event in driving.trip.update(0):
            if event.kind == TripEventKind.CURVE:
                driving._handle_trip_event(event)
        assert spoken == ["Sharp left, a quarter mile. Advise 30 miles per hour."]
    finally:
        app.shutdown()


def test_safe_speed_folds_in_the_bend(monkeypatch):
    app_module = pytest.importorskip("freight_fate.app")
    app = app_module.App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        pos = driving.trip.position_mi
        driving.trip.curves = (_curve(pos + 0.2, advisory=25),)
        driving._speak_safe_speed()
        assert "for the bend" in spoken[-1]
        assert "25" in spoken[-1]
    finally:
        app.shutdown()


def test_upcoming_lists_the_next_bends(monkeypatch):
    app_module = pytest.importorskip("freight_fate.app")
    app = app_module.App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        pos = driving.trip.position_mi
        driving.trip.curves = (
            _curve(pos + 2.0, "L", advisory=30),
            _curve(pos + 4.0, "R", advisory=65),  # gentle: stays out
        )
        driving._speak_upcoming()
        text = spoken[-1]
        assert "sharp left" in text.lower()
        assert "advise" in text.lower()
        assert "gentle" not in text.lower()
    finally:
        app.shutdown()


def test_lead_floor_scales_with_speed():
    # Owner's AZ-260 run (2026-07-19): at the posted 55 a fixed quarter-mile
    # floor is seconds, not a warning. The floor is now time-based.
    from freight_fate.sim.trip import PACENOTE_LEAD_FLOOR_S, Trip

    lead_55 = Trip._curve_pacenote_lead_mi(55.0, 25.0)
    assert lead_55 >= 55.0 * PACENOTE_LEAD_FLOOR_S / 3600.0
    # Slow approaches keep the old fixed minimum.
    assert Trip._curve_pacenote_lead_mi(20.0, 15.0) == pytest.approx(0.33)


def test_close_curve_says_just_ahead(monkeypatch):
    # Sub-quarter-mile distances must never round UP to "a quarter mile":
    # the words promised time the driver did not have (AZ-260, 2026-07-19).
    app_module = pytest.importorskip("freight_fate.app")
    app = app_module.App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        pos = driving.trip.position_mi
        spoken = _spoken_pacenotes(app, driving, monkeypatch, [_curve(pos + 0.05)], 50.0)
        assert spoken and "just ahead" in spoken[0]
        assert "quarter" not in spoken[0]
    finally:
        app.shutdown()


def test_silenced_curve_call_respeaks_once_refreshed(monkeypatch):
    # Ctrl must silence instantly (screen-reader reflex), but a safety call
    # cut mid-sentence re-speaks once with a fresh distance -- and only
    # while the bend is still ahead and the truck still hot.
    import pygame
    from driving_feature_helpers import key_event

    app_module = pytest.importorskip("freight_fate.app")
    app = app_module.App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        pos = driving.trip.position_mi
        spoken = _spoken_pacenotes(
            app, driving, monkeypatch, [_curve(pos + 0.3, "R", advisory=30)], 60.0
        )
        assert len(spoken) == 1

        driving.handle_event(key_event(pygame.K_LCTRL))  # the reflex
        driving._update_critical_respeak(2.5)  # past the re-speak delay
        assert len(spoken) == 2 and "Sharp right" in spoken[1]

        # One shot only: another Ctrl after the re-arm is spent stays quiet.
        driving.handle_event(key_event(pygame.K_LCTRL))
        driving._update_critical_respeak(2.5)
        assert len(spoken) == 2

        # And a call silenced AFTER braking below the advisory stays quiet.
        driving.trip._announced_curves = set()
        spoken2 = _spoken_pacenotes(
            app, driving, monkeypatch, [_curve(pos + 0.3, "R", advisory=30)], 60.0
        )
        assert len(spoken2) == 1
        driving.truck.velocity_mps = 25.0 * 0.44704
        driving.handle_event(key_event(pygame.K_LCTRL))
        driving._update_critical_respeak(2.5)
        assert len(spoken2) == 1
    finally:
        app.shutdown()


def test_linked_follower_rides_the_tail_not_its_own_call(monkeypatch):
    # Owner's Payson run (2026-07-19): "Then right" was a preview, not a
    # replacement -- every linked bend also fired its own full call and
    # chained S-bends flooded the driver. One chain, one call.
    app_module = pytest.importorskip("freight_fate.app")
    app = app_module.App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        pos = driving.trip.position_mi
        first = _curve(pos + 0.3, "L", advisory=35)
        follower = _curve(pos + 0.45, "R", advisory=25, deflection=170.0)
        spoken = _spoken_pacenotes(app, driving, monkeypatch, [first, follower], 60.0)
        assert len(spoken) == 1
        # The tail carries the follower's severity and tighter advisory.
        assert "Then hairpin right, advise 25 miles per hour." in spoken[0]

        # The follower stays suppressed on later frames too.
        for event in driving.trip.update(0):
            if event.kind == TripEventKind.CURVE:
                driving._handle_trip_event(event)
        assert len(spoken) == 1
    finally:
        app.shutdown()
