"""Controller haptics: the pure RumbleEngine and the manager's device guard."""

from freight_fate.controller import ControllerManager
from freight_fate.rumble import RumbleEngine


class Recorder:
    """Stands in for the pad: records every send and stop the engine issues."""

    def __init__(self):
        self.calls = []  # (low, high, duration_ms)
        self.stops = 0

    def send(self, low, high, duration_ms):
        self.calls.append((low, high, duration_ms))

    def stop(self):
        self.stops += 1


def _engine():
    r = Recorder()
    return RumbleEngine(send=r.send, stop=r.stop), r


def _crossings(values):
    """How often a series crosses its own mean -- a proxy for its rate."""
    mean = sum(values) / len(values)
    return sum(1 for a, b in zip(values, values[1:], strict=False) if (a - mean) * (b - mean) < 0)


# -- one-shot effects --------------------------------------------------------


def test_alert_is_high_only_and_stops():
    e, r = _engine()
    e.alert()
    e.tick(0.05)  # still inside the 120 ms blip
    low, high, _ = r.calls[-1]
    assert low == 0.0
    assert high > 0.0
    e.tick(0.1)  # now past the blip: engine goes idle and stops once
    assert r.stops == 1


def test_hazard_sweep_leads_right_then_left_with_overlap():
    e, r = _engine()
    e.hazard()
    samples = []  # (t, low, high) whenever the engine actually drove the pad
    t = 0.0
    for _ in range(40):
        before = len(r.calls)
        e.tick(0.025)
        t += 0.025
        if len(r.calls) > before:
            low, high, _ = r.calls[-1]
            samples.append((t, low, high))
    peak_high_t = max(samples, key=lambda s: s[2])[0]
    peak_low_t = max(samples, key=lambda s: s[1])[0]
    # Right (high) grip leads, left (low) grip trails.
    assert peak_high_t < peak_low_t
    # They overlap: some moment has both motors clearly running.
    assert any(low > 0.1 and high > 0.1 for _, low, high in samples)
    # The whole thing is about 750 ms long.
    assert 0.7 <= samples[-1][0] <= 0.8


def test_impact_is_a_decaying_low_thump():
    e, r = _engine()
    e.impact(1.0)
    e.tick(0.02)
    early_low = r.calls[-1][0]
    for _ in range(20):  # past the 350 ms life
        e.tick(0.02)
    # It leads with the low motor and decays over its short life.
    assert early_low > 0.5
    assert r.stops == 1  # lapses on its own


# -- continuous effects ------------------------------------------------------


def test_rumble_strip_never_releases_a_motor_and_pulses_right_faster():
    e, r = _engine()
    lows, highs = [], []
    for _ in range(120):  # ~0.6 s of refreshed drift
        e.rumble_strip(1.0)
        e.tick(0.005)
        low, high, _ = r.calls[-1]
        lows.append(low)
        highs.append(high)
    # Harsh: both motors stay buzzing, never fully at zero.
    assert min(lows) > 0.0
    assert min(highs) > 0.0
    # The right (high) side pulses faster than the left (low) side.
    assert _crossings(highs) > _crossings(lows)


def test_rumble_strip_stops_after_refreshes_end():
    e, r = _engine()
    for _ in range(3):
        e.rumble_strip(1.0)
        e.tick(0.016)
    stops_before = r.stops
    for _ in range(5):  # stop refreshing; TTL lapses within a few frames
        e.tick(0.016)
    assert r.stops == stops_before + 1


def test_hard_brake_low_scales_with_level():
    (ea, ra), (eb, rb) = _engine(), _engine()
    ea.hard_brake(1.0)
    eb.hard_brake(0.5)
    ea.tick(0.016)
    eb.tick(0.016)  # identical phase, so only the level differs
    assert ra.calls[-1][0] > rb.calls[-1][0]


def test_combine_takes_the_per_motor_max():
    e, r = _engine()
    e.rumble_strip(0.2)  # gentle both-motor buzz
    e.hard_brake(1.0)  # strong low shudder
    e.tick(0.016)
    combined_low = r.calls[-1][0]

    e2, r2 = _engine()
    e2.rumble_strip(0.2)
    e2.tick(0.016)
    strip_only_low = r2.calls[-1][0]
    # The louder source wins each motor; low is at least the strip-only low.
    assert combined_low >= strip_only_low


def test_reset_clears_effects_and_stops():
    e, r = _engine()
    e.rumble_strip(1.0)
    e.tick(0.016)
    e.reset()
    assert r.stops >= 1
    r.calls.clear()
    e.tick(0.016)  # nothing left to drive
    assert r.calls == []


# -- manager device guard ----------------------------------------------------


class FakeDevice:
    def __init__(self):
        self.calls = []
        self.stops = 0

    def rumble(self, low, high, duration_ms):
        self.calls.append((low, high, duration_ms))
        return True

    def stop_rumble(self):
        self.stops += 1


def _manager(haptics):
    m = ControllerManager(enabled=True, haptics=haptics)
    m._controller = FakeDevice()
    m._instance_id = 0
    return m


def test_manager_drives_the_pad_when_haptics_enabled():
    m = _manager(haptics=True)
    m.rumble.alert()
    m.tick(0.05)
    assert m._controller.calls  # the blip reached the device


def test_manager_stays_silent_when_haptics_disabled():
    m = _manager(haptics=False)
    m.rumble.alert()
    m.tick(0.05)
    assert m._controller.calls == []  # guarded off, no device call


def test_set_haptics_enabled_toggles_and_stops():
    m = _manager(haptics=True)
    m.set_haptics_enabled(False)
    assert m._controller.stops >= 1  # reset silenced the pad
    m.rumble.alert()
    m.tick(0.05)
    assert m._controller.calls == []
