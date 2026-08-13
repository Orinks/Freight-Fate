"""A latched throttle yields to the speed authorities.

Owner design 2026-08-13 (spec: docs/superpowers/specs/
2026-08-13-pedal-latch-assists-design.md). Tester Brandon latched the
throttle for the whole trip and expected the assists to manage speed over
it; every assist read the latch as a manual override and stood down. The
latch is now the lowest-priority speed input: cruise, the speed keeper,
and curve assist outrank it while engaged, and it ramps back in when they
release. A hand-held key keeps its manual-override meaning everywhere.
"""

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
