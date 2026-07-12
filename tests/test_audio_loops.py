"""Unit-level checks for the reusable sustain-loop helper."""

import pytest

from freight_fate.audio import HORN_LOOP_END, HORN_LOOP_START, AudioEngine
from freight_fate.audio_loops import SustainLoop, to_seconds


@pytest.fixture(autouse=True)
def _free_leaked_bass():
    yield
    try:
        from sound_lib.external.pybass import BASS_Free, BASS_SetDevice

        BASS_SetDevice(0)
        BASS_Free()
    except Exception:
        pass


def test_to_seconds_samples_uses_frequency():
    assert to_seconds(44100, "samples", 44100) == 1.0
    assert to_seconds(11816, "samples", 44100) == pytest.approx(11816 / 44100)


def test_to_seconds_seconds_passthrough_ignores_frequency():
    assert to_seconds(0.5, "seconds") == 0.5
    assert to_seconds(0.5, "seconds", None) == 0.5


def test_to_seconds_rejects_samples_without_frequency():
    with pytest.raises(ValueError):
        to_seconds(11816, "samples")
    with pytest.raises(ValueError):
        to_seconds(11816, "samples", 0)


def test_to_seconds_rejects_unknown_units():
    with pytest.raises(ValueError):
        to_seconds(1, "frames", 44100)


def _bass_stream():
    """A real, non-looping BASS stream for the horn, or skip if BASS is absent."""
    a = AudioEngine()
    if a.backend_name != "bass":
        a.shutdown()
        pytest.skip("BASS backend unavailable")
    return a, a._impl._sfx_stream("vehicle/horn", looping=False)


def test_sustain_loop_computes_byte_positions_from_samples():
    a, stream = _bass_stream()
    try:
        loop = SustainLoop(stream, HORN_LOOP_START, HORN_LOOP_END, units="samples")
        # Verified against the shipped 44100 Hz horn asset.
        assert loop._start_byte == 47264
        assert not loop.released
        loop.stop()
    finally:
        a.shutdown()


def test_sustain_loop_release_is_idempotent():
    a, stream = _bass_stream()
    try:
        loop = SustainLoop(stream, HORN_LOOP_START, HORN_LOOP_END, units="samples")
        loop.release()
        assert loop.released
        loop.release()  # must not raise a second time
        loop.stop()  # nor when torn down after release
        assert loop.released
    finally:
        a.shutdown()


def test_sustain_loop_rejects_inverted_points():
    a, stream = _bass_stream()
    try:
        with pytest.raises(ValueError):
            SustainLoop(stream, HORN_LOOP_END, HORN_LOOP_START, units="samples")
    finally:
        a.shutdown()
