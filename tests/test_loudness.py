"""tools/loudness.py: the meter the music normalizer and sound audit trust."""

import loudness
import numpy as np
import pytest


def _sine(amplitude: float, seconds: float = 5.0, hz: float = 997.0) -> np.ndarray:
    t = np.arange(int(seconds * loudness.RATE)) / loudness.RATE
    tone = amplitude * np.sin(2 * np.pi * hz * t)
    return np.vstack([tone, tone])


def test_stereo_sine_reads_its_level_in_lufs():
    # BS.1770: a 997 Hz sine in both channels reads its dBFS level as LUFS.
    assert loudness.integrated(_sine(0.1)) == pytest.approx(-20.0, abs=0.1)
    assert loudness.true_peak(_sine(0.1)) == pytest.approx(-20.0, abs=0.1)
    assert loudness.loudness_range(_sine(0.1)) == pytest.approx(0.0, abs=0.1)


def test_silence_is_minus_infinity_not_a_crash():
    silent = np.zeros((2, loudness.RATE))
    assert loudness.integrated(silent) == float("-inf")


def test_a_click_shorter_than_one_block_is_still_measured():
    click = _sine(0.5, seconds=0.05)
    assert -40.0 < loudness.max_momentary(click) < loudness.max_momentary(_sine(0.5))


def test_gain_stops_at_the_peak_ceiling():
    assert loudness.normalizing_gain(-14.0, -3.0, -18.0, -1.0) == (-4.0, False)
    gain, limited = loudness.normalizing_gain(-26.0, -4.0, -18.0, -1.0)
    assert (gain, limited) == (3.0, True)
