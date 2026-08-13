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
