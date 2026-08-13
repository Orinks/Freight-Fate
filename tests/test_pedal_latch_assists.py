"""A latched throttle yields to the speed authorities.

Owner design 2026-08-13 (spec: docs/superpowers/specs/
2026-08-13-pedal-latch-assists-design.md). Tester Brandon latched the
throttle for the whole trip and expected the assists to manage speed over
it; every assist read the latch as a manual override and stood down. The
latch is now the lowest-priority speed input: cruise, the speed keeper,
and curve assist outrank it while engaged, and it ramps back in when they
release. A hand-held key keeps its manual-override meaning everywhere.
"""

import pygame
from speech_capture import speech_stub

DT = 1 / 60


class FakeKeys:
    def __init__(self, held):
        self.held = held

    def __getitem__(self, key):
        return key in self.held


def _drive_frames(driving, seconds):
    t = 0.0
    while t < seconds:
        driving.update(DT)
        t += DT


def _latch_throttle(driving):
    """Catch the latch directly; the gesture itself is test_pedal_latch.py's job."""
    driving._throttle_latch.latched = True
    driving._throttle_latch._state = "resting"


def _fake_curve(monkeypatch, driving, advisory=35.0):
    """Match the real ``RouteCurve`` constructor -- see ``_AssistRig`` in
    test_driving_features.py, the source of truth for its fields."""
    from freight_fate.data.curves import RouteCurve

    start_mi = driving.trip.position_mi - 0.05
    curve = RouteCurve(
        start_mi=start_mi,
        apex_mi=start_mi + 1.0,
        end_mi=start_mi + 2.05,
        direction="R",
        advisory_mph=advisory,
        min_radius_ft=1500,
        deflection_deg=60.0,
        connector=False,
    )
    monkeypatch.setattr(driving.trip, "curve_at", lambda _mile: curve)
    return curve


def test_speed_authority_predicate_reads_all_three():
    from driving_feature_helpers import start_drive

    from freight_fate.app import App

    app = App()
    try:
        d = start_drive(app)
        assert not d._speed_authority_engaged()
        d._cruise_mph = 55.0
        assert d._speed_authority_engaged()
        d._cruise_mph = None
        d._keeper_mph = 25.0
        assert d._speed_authority_engaged()
        d._keeper_mph = None
        d._curve_assist_active = True
        assert d._speed_authority_engaged()
    finally:
        app.shutdown()


def test_cruise_holds_its_speed_under_a_latched_throttle(monkeypatch):
    """The Brandon case: latch caught, cruise engaged -- cruise must drive
    the pedal, not fight a throttle ramping to full."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.engine_on = True  # _update_cruise cancels the session without it
        # The corridor's posted limit here is well under 60: the overspeed
        # alarm is its own pre-existing hard release (out of scope for this
        # fix), so it is switched off to isolate the latch/cruise handoff.
        app.ctx.settings.overspeed_warning = "off"
        d.truck.velocity_mps = 60 / 2.2369362920544
        _latch_throttle(d)
        d._engage_cruise(55.0)

        _drive_frames(d, 3.0)

        assert d._cruise_mph is not None  # cruise never stood down
        assert d._throttle_latch.latched  # and the latch never dropped
        # Cruise is trimming DOWN toward 55: a yielded latch cannot be
        # holding the pedal at full power.
        assert d.truck.throttle < 0.5
    finally:
        app.shutdown()


def test_a_hand_held_key_still_stands_the_assists_down(monkeypatch):
    """Physical hold keeps today's manual-override meaning."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    held = {pygame.K_UP}
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.engine_on = True  # _update_cruise cancels the session without it
        d.truck.velocity_mps = 60 / 2.2369362920544
        d._engage_cruise(55.0)

        _drive_frames(d, 2.0)

        assert d._cruise_mph is not None  # engaged, waiting for the key to lift
        assert d.truck.throttle > 0.9  # but the hand owns the pedal
    finally:
        app.shutdown()


def test_the_latch_ramps_back_in_when_the_authority_releases(monkeypatch):
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.engine_on = True  # _update_cruise cancels the session without it
        # See the sibling cruise test: the corridor limit here is under 60,
        # and the overspeed hard release is a separate, pre-existing system
        # this task does not touch.
        app.ctx.settings.overspeed_warning = "off"
        d.truck.velocity_mps = 60 / 2.2369362920544
        _latch_throttle(d)
        d._engage_cruise(55.0)
        _drive_frames(d, 2.0)
        assert d.truck.throttle < 0.5

        d._cancel_cruise()
        _drive_frames(d, 1.0)

        assert d._throttle_latch.latched
        assert d.truck.throttle > 0.9  # the latch has the pedal again
    finally:
        app.shutdown()


def test_keeper_holds_a_zone_speed_under_a_latched_throttle(monkeypatch):
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App
    from freight_fate.sim.trip_models import Zone

    app = App()
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.engine_on = True  # _update_keeper cancels the session without it
        # The zone limit doubles as the overspeed alarm's reference speed, so
        # being this far over it would trip that separate, pre-existing hard
        # release before the keeper gets a chance to work; not what this
        # test is about.
        app.ctx.settings.overspeed_warning = "off"
        # A school zone under the wheels, truck well over its number.
        start = d.trip.position_mi
        d.trip.zones.append(Zone(start - 0.1, start + 3.0, 25.0, "school"))
        d.truck.velocity_mps = 40 / 2.2369362920544
        _latch_throttle(d)
        d._engage_keeper(25.0, "school", target_mph=25.0, announce=False)

        _drive_frames(d, 8.0)

        assert d._keeper_mph is not None  # keeper never stood down
        assert d._throttle_latch.latched
        assert d.truck.speed_mph < 33.0  # shedding toward the zone number
    finally:
        app.shutdown()


def test_releasing_the_latch_leaves_cruise_holding(monkeypatch):
    """Owner rule 2026-08-13: unlatching hands the pedal back to the hand;
    it is not a cruise cancel. The brake stays the cancel, unchanged."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    spoken = []
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.engine_on = True  # _update_cruise cancels the session without it
        app.ctx.settings.overspeed_warning = "off"
        d.truck.velocity_mps = 60 / 2.2369362920544
        _latch_throttle(d)
        d._engage_cruise(55.0)
        _drive_frames(d, 1.0)

        # A fresh press of the throttle key returns the pedal to the hand...
        held.add(pygame.K_UP)
        _drive_frames(d, 0.3)
        held.discard(pygame.K_UP)
        _drive_frames(d, 1.0)

        assert not d._throttle_latch.latched
        assert "Throttle released." in spoken
        assert d._cruise_mph is not None  # ...and cruise never blinked
        assert not any("cruise canceled" in s.lower() for s in spoken)
    finally:
        app.shutdown()


def test_curve_assist_drains_a_latched_throttle(monkeypatch):
    """The 0.35 service trim must not fight a pedal ramping to full."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.engine_on = True
        app.ctx.settings.overspeed_warning = "off"
        d.ctx.settings.curve_speed_assist = True
        monkeypatch.setattr(d.trip, "engine_brake_ban_at", lambda _mile: None)
        _fake_curve(monkeypatch, d, advisory=35.0)
        d.truck.velocity_mps = 50 / 2.2369362920544
        _latch_throttle(d)

        _drive_frames(d, 3.0)

        assert d._curve_assist_active
        assert d._throttle_latch.latched
        assert d.truck.throttle < 0.05  # yielded and drained
        assert d.truck.speed_mph < 48.0  # the trim is actually winning now
    finally:
        app.shutdown()


def test_latch_first_mode_keeps_the_old_override_meaning(monkeypatch):
    """Owner revision: "latch first" is the pre-change behavior -- a latched
    throttle is a manual override and cruise stands down (stays engaged,
    waiting, while the latch drives the pedal)."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        app.ctx.settings.pedal_latch = "latch first"
        app.ctx.settings.overspeed_warning = "off"
        d.truck.engine_on = True
        d.truck.velocity_mps = 60 / 2.2369362920544
        _latch_throttle(d)
        d._engage_cruise(55.0)

        _drive_frames(d, 2.0)

        assert d._cruise_mph is not None  # engaged, standing down
        assert d._throttle_latch.latched
        assert d.truck.throttle > 0.9  # the latch owns the pedal, old style
        assert not d._latch_yielding
    finally:
        app.shutdown()


def test_the_catch_line_names_the_authority_holding_the_speed(monkeypatch):
    """Latching while cruise or the keeper drives must not sound dead."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    spoken = []
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.engine_on = True
        app.ctx.settings.overspeed_warning = "off"
        d.truck.velocity_mps = 60 / 2.2369362920544
        d._engage_cruise(55.0)

        # The real gesture, so the spoken confirmation path is the one
        # players hear: tap, release, press and hold through the catch.
        held.add(pygame.K_UP)
        _drive_frames(d, 0.2)
        held.discard(pygame.K_UP)
        _drive_frames(d, 0.2)
        held.add(pygame.K_UP)
        _drive_frames(d, 0.8)
        held.discard(pygame.K_UP)

        assert "Throttle latched. Adaptive cruise holds the speed." in spoken
        assert "Throttle latched." not in spoken  # replaced, not doubled
    finally:
        app.shutdown()


def test_a_plain_catch_keeps_its_plain_line(monkeypatch):
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    spoken = []
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        held.add(pygame.K_UP)
        _drive_frames(d, 0.2)
        held.discard(pygame.K_UP)
        _drive_frames(d, 0.2)
        held.add(pygame.K_UP)
        _drive_frames(d, 0.8)
        held.discard(pygame.K_UP)

        assert "Throttle latched." in spoken
    finally:
        app.shutdown()


def test_latch_first_catch_keeps_the_plain_line(monkeypatch):
    """Owner revision: "latch first" is the pre-change behavior -- the plain
    line is the truth, since nothing outranks the latch in this mode, so
    the authority line must not appear even with cruise engaged."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    spoken = []
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        app.ctx.settings.pedal_latch = "latch first"
        app.ctx.settings.overspeed_warning = "off"
        d.truck.engine_on = True
        d.truck.velocity_mps = 60 / 2.2369362920544
        d._engage_cruise(55.0)

        held.add(pygame.K_UP)
        _drive_frames(d, 0.2)
        held.discard(pygame.K_UP)
        _drive_frames(d, 0.2)
        held.add(pygame.K_UP)
        _drive_frames(d, 0.8)
        held.discard(pygame.K_UP)

        assert "Throttle latched." in spoken
        assert "Throttle latched. Adaptive cruise holds the speed." not in spoken
    finally:
        app.shutdown()


def test_curve_assist_jake_arrives_once_the_latched_throttle_drains(monkeypatch):
    """On a real downgrade the assist raises the retarder -- but on the
    engage frame a yielded latch is still draining, so the capability
    check must retry while the latch is yielding."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    app = App()
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        d.truck.engine_on = True
        app.ctx.settings.overspeed_warning = "off"
        d.ctx.settings.curve_speed_assist = True
        monkeypatch.setattr(d.trip, "engine_brake_ban_at", lambda _mile: None)
        # A real downgrade under the bend, faked the same way the existing
        # downgrade jake coverage does it (_AssistRig, test_driving_features.py):
        # trip.grade_at, not a monkeypatched _on_downgrade.
        monkeypatch.setattr(d.trip, "grade_at", lambda _mile: -0.06)
        d.truck.grade = -0.06
        d.truck.velocity_mps = 50 / 2.2369362920544
        # jake_capable needs a truck actually in gear -- a freshly departed
        # drive with velocity set directly (skipping a real launch) is still
        # in neutral, same reason _AssistRig sets this by hand.
        d.truck.transmission.automatic = True
        d.truck.transmission.gear = 9
        d.truck.rpm = 1500.0
        d.truck.grip = 1.0
        _latch_throttle(d)

        # No curve yet: let the latch ramp the pedal all the way up first, so
        # the corner arrives on a throttle that is genuinely still high --
        # not one that just happens to read low because it never got the
        # chance to ramp. That is the whole scenario the retry exists for.
        _drive_frames(d, 1.5)
        assert d.truck.throttle > 0.9

        _fake_curve(monkeypatch, d, advisory=30.0)
        _drive_frames(d, 3.0)

        assert d._curve_assist_active
        assert d._curve_assist_jake  # engaged after the drain, not never
    finally:
        app.shutdown()
