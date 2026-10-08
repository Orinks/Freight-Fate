"""EBU R128 / ITU-R BS.1770-4 loudness for the audio tools.

Integrated loudness, loudness range and true peak for a music track, plus the
two measures that still mean something on a 100 ms earcon: the loudest
momentary (400 ms) block and the true peak. numpy and scipy only, so the
tests can pin it without PyAV.

Every function takes float samples shaped ``(channels, n)`` at 48 kHz, the
rate the K-weighting coefficients below are published for. Callers resample
first; a mono file is measured as it plays in game, sent to both speakers,
so upmix it to two identical channels before measuring.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import lfilter, resample_poly

RATE = 48_000
_ABS_GATE = -70.0

# BS.1770-4 K-weighting at 48 kHz: a high shelf (the head) then a high pass.
_SHELF_B = [1.53512485958697, -2.69169618940638, 1.19839281085285]
_SHELF_A = [1.0, -1.69065929318241, 0.73248077421585]
_HIGHPASS_B = [1.0, -2.0, 1.0]
_HIGHPASS_A = [1.0, -1.99004745483398, 0.99007225036621]


def _k_weighted_power(samples: np.ndarray, window_s: float, hop_s: float) -> np.ndarray:
    """Mean-square power of each window, summed over channels (all weight 1)."""
    x = lfilter(_HIGHPASS_B, _HIGHPASS_A, lfilter(_SHELF_B, _SHELF_A, samples, axis=1), axis=1)
    window, hop = int(window_s * RATE), int(hop_s * RATE)
    if x.shape[1] < window:
        # A clip shorter than one window is measured as that window with
        # silence after it: a short click reads quieter than a long tone at
        # the same peak, which is what the ear hears too.
        x = np.pad(x, ((0, 0), (0, window - x.shape[1])))
    power = np.concatenate([np.zeros(1), np.cumsum((x.astype(np.float64) ** 2).sum(axis=0))])
    starts = np.arange(0, x.shape[1] - window + 1, hop)
    return (power[starts + window] - power[starts]) / window


def _lufs(power: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore"):
        return -0.691 + 10.0 * np.log10(power)


def integrated(samples: np.ndarray) -> float:
    """Gated integrated loudness in LUFS (-inf for silence)."""
    power = _k_weighted_power(samples, 0.4, 0.1)
    power = power[_lufs(power) > _ABS_GATE]
    if not power.size:
        return float("-inf")
    power = power[_lufs(power) > _lufs(power.mean()) - 10.0]
    return float(_lufs(power.mean()))


def loudness_range(samples: np.ndarray) -> float:
    """EBU Tech 3342 loudness range in LU: 10th to 95th percentile of the
    gated 3 s short-term loudness."""
    power = _k_weighted_power(samples, 3.0, 0.1)
    power = power[_lufs(power) > _ABS_GATE]
    if power.size < 2:
        return 0.0
    levels = _lufs(power[_lufs(power) > _lufs(power.mean()) - 20.0])
    low, high = np.percentile(levels, [10, 95])
    return float(high - low)


def max_momentary(samples: np.ndarray) -> float:
    """The loudest 400 ms block in LUFS: the level measure for short cues."""
    return float(_lufs(_k_weighted_power(samples, 0.4, 0.1)).max())


def true_peak(samples: np.ndarray) -> float:
    """Peak of the 4x oversampled signal in dBTP."""
    peak = float(np.abs(resample_poly(samples, 4, 1, axis=1)).max())
    return 20.0 * np.log10(peak) if peak > 0 else float("-inf")


def normalizing_gain(
    measured_lufs: float, measured_tp: float, target_lufs: float, max_tp: float
) -> tuple[float, bool]:
    """The static gain in dB that brings a track to ``target_lufs``, and
    whether the true-peak ceiling cut it short.

    Static gain only, never compression: a track whose peaks would cross
    ``max_tp`` stops at the ceiling and stays that much under the target.
    """
    gain = target_lufs - measured_lufs
    headroom = max_tp - measured_tp
    if gain > headroom:
        return headroom, True
    return gain, False
