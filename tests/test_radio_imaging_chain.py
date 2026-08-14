"""Pure-numpy unit tests for the imaging post-production chain.

No network calls, no ffmpeg, no on-disk assets: feeds a synthetic sine
through imaging_process/broadcast_compress/mix_id_bed and checks the
numeric contract -- length within the documented ping-tail allowance,
peak headroom, RMS close to the loudness-match target, and determinism
per seed. tools/generate_radio.py's generate_sfx (the actual credit-
spending Sound Effects API call) is intentionally not exercised here.
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.generate_radio import (  # noqa: E402
    TARGET_RMS_DBFS,
    broadcast_compress,
    imaging_process,
    mix_id_bed,
)

RATE = 44100
MAX_TAIL_SAMPLES = int(0.4 * RATE)


def _sine(seconds: float, freq: float = 440.0, rate: int = RATE) -> np.ndarray:
    t = np.linspace(0.0, seconds, int(rate * seconds), endpoint=False)
    return (0.5 * np.sin(2.0 * np.pi * freq * t)).astype(np.float64)


def _rms_dbfs(samples: np.ndarray) -> float:
    if samples.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(samples))))
    return 20.0 * np.log10(rms) if rms > 0.0 else -120.0


def test_imaging_process_length_within_ping_tail_allowance():
    sine = _sine(1.0)
    out = imaging_process(sine, RATE, seed=7)
    assert sine.size <= out.size <= sine.size + MAX_TAIL_SAMPLES


def test_imaging_process_peak_at_most_one():
    sine = _sine(1.0)
    out = imaging_process(sine, RATE, seed=7)
    assert np.max(np.abs(out)) <= 1.0 + 1e-6


def test_imaging_process_rms_within_3db_of_target():
    sine = _sine(1.0)
    out = imaging_process(sine, RATE, seed=7)
    assert abs(_rms_dbfs(out) - TARGET_RMS_DBFS) <= 3.0


def test_imaging_process_same_seed_is_byte_identical():
    sine = _sine(1.0)
    out_a = imaging_process(sine, RATE, seed=42)
    out_b = imaging_process(sine, RATE, seed=42)
    assert out_a.shape == out_b.shape
    assert np.array_equal(out_a, out_b)


def test_imaging_process_different_seed_changes_output():
    sine = _sine(1.0)
    out_a = imaging_process(sine, RATE, seed=1)
    out_b = imaging_process(sine, RATE, seed=2)
    # Different seeds pick a different detune direction/amount and a
    # different reverb impulse response, so the two outputs must differ
    # even though they share length bounds and loudness target.
    assert out_a.shape != out_b.shape or not np.array_equal(out_a, out_b)


def test_imaging_process_without_doubling_still_valid():
    sine = _sine(1.0)
    out = imaging_process(sine, RATE, seed=7, doubled=False)
    assert sine.size <= out.size <= sine.size + MAX_TAIL_SAMPLES
    assert np.max(np.abs(out)) <= 1.0 + 1e-6
    assert abs(_rms_dbfs(out) - TARGET_RMS_DBFS) <= 3.0


def test_imaging_process_returns_float32():
    sine = _sine(1.0)
    out = imaging_process(sine, RATE, seed=7)
    assert out.dtype == np.float32


def test_broadcast_compress_shape_matches_input():
    sine = _sine(1.0)
    out = broadcast_compress(sine, RATE)
    assert out.shape == sine.shape
    assert out.dtype == np.float32


def test_broadcast_compress_peak_at_most_one():
    sine = _sine(1.0)
    out = broadcast_compress(sine, RATE)
    assert np.max(np.abs(out)) <= 1.0 + 1e-6


def test_broadcast_compress_rms_within_3db_of_target():
    sine = _sine(1.0)
    out = broadcast_compress(sine, RATE)
    assert abs(_rms_dbfs(out) - TARGET_RMS_DBFS) <= 3.0


def test_broadcast_compress_deterministic():
    sine = _sine(1.0)
    out_a = broadcast_compress(sine, RATE)
    out_b = broadcast_compress(sine, RATE)
    assert np.array_equal(out_a, out_b)


def test_broadcast_compress_handles_silence():
    silence = np.zeros(RATE, dtype=np.float64)
    out = broadcast_compress(silence, RATE)
    assert out.shape == silence.shape
    assert np.max(np.abs(out)) <= 1.0 + 1e-6
    assert np.all(np.isfinite(out))


def test_mix_id_bed_peak_normalized_to_point_nine():
    voice = _sine(1.0)
    whoosh = _sine(0.4, freq=880.0)
    riser = _sine(0.6, freq=220.0)
    mixed = mix_id_bed(voice, {"whoosh": whoosh, "riser": riser}, RATE)
    assert np.isclose(np.max(np.abs(mixed)), 0.9, atol=1e-6)


def test_mix_id_bed_riser_lands_in_the_tail():
    voice = _sine(1.0)
    riser = np.ones(int(0.3 * RATE), dtype=np.float64)
    mixed = mix_id_bed(voice, {"riser": riser}, RATE)
    # The riser should contribute to the last part of the mix, not the head.
    head_energy = float(np.sum(np.square(mixed[: int(0.1 * RATE)])))
    tail_energy = float(np.sum(np.square(mixed[-int(0.1 * RATE) :])))
    assert tail_energy > head_energy


def test_mix_id_bed_missing_layers_ok():
    voice = _sine(1.0)
    mixed = mix_id_bed(voice, {}, RATE)
    assert mixed.size == voice.size
    assert np.max(np.abs(mixed)) <= 1.0 + 1e-6
