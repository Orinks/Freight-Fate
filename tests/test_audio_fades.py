"""The reusable, backend-agnostic fade utility (curves, Fade, FadeScheduler)."""

import math

from freight_fate.audio_fades import CURVES, Fade, FadeScheduler, curve


def test_every_curve_pins_its_endpoints():
    for name, fn in CURVES.items():
        assert abs(fn(0.0)) < 1e-9, name
        assert abs(fn(1.0) - 1.0) < 1e-9, name


def test_curve_lookup_defaults_to_linear_for_unknown_names():
    assert curve("nope")(0.4) == 0.4


def test_equal_power_pair_keeps_constant_energy():
    # out^2 + in^2 == 1 at every point is the defining property of an
    # equal-power crossfade.
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        out = 1.0 - CURVES["equal_power_out"](t)  # remaining level of the fade-out
        gain_in = CURVES["equal_power_in"](t)
        assert abs(out * out + gain_in * gain_in - 1.0) < 1e-9


def test_fade_reaches_end_after_duration():
    seen = []
    fade = Fade(seen.append, 1.0, 0.0, 1.0, curve="linear")
    assert seen[-1] == 1.0  # starting value applied immediately
    assert not fade.advance(0.5)
    assert abs(seen[-1] - 0.5) < 1e-9
    assert fade.advance(0.6)  # crosses the end
    assert seen[-1] == 0.0
    assert fade.done


def test_fade_honors_delay():
    seen = []
    fade = Fade(seen.append, 0.0, 1.0, 1.0, delay_s=0.5)
    fade.advance(0.4)  # still inside the delay
    assert seen[-1] == 0.0
    fade.advance(0.6)  # elapsed 1.0s total => 0.5s into the 1.0s ramp
    assert abs(seen[-1] - 0.5) < 1e-9


def test_zero_duration_fade_snaps_to_end():
    seen = []
    fade = Fade(seen.append, 0.0, 1.0, 0.0)
    assert fade.advance(0.0)
    assert seen[-1] == 1.0


def test_on_done_fires_exactly_once():
    calls = []
    fade = Fade(lambda _v: None, 0.0, 1.0, 0.5, on_done=lambda: calls.append(1))
    fade.advance(0.6)
    fade.advance(0.6)
    assert calls == [1]


def test_scheduler_advances_and_drops_finished_fades():
    a, b = [], []
    sched = FadeScheduler()
    sched.add(Fade(a.append, 0.0, 1.0, 0.5))
    sched.add(Fade(b.append, 0.0, 1.0, 2.0))
    assert len(sched) == 2
    sched.update(1.0)  # first fade finishes, second still running
    assert len(sched) == 1
    assert a[-1] == 1.0
    assert 0.0 < b[-1] < 1.0
    sched.clear()
    assert len(sched) == 0


def test_curve_shapes_are_distinct_at_the_midpoint():
    # A crude guard that the library actually offers different shapes to tune.
    mids = {name: fn(0.5) for name, fn in CURVES.items()}
    assert mids["linear"] == 0.5
    assert mids["ease_in"] < 0.5 < mids["ease_out"]
    assert math.isclose(mids["ease_in_out"], 0.5)
