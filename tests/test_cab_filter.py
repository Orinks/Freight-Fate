"""Tests for the sealed-cab transfer on the engine voice."""

from __future__ import annotations

import io
import math
import wave

import numpy as np

from freight_fate import audio, cab_filter


def _sine_wav(freqs, sr=44100, seconds=0.5, channels=2, amp=0.25) -> bytes:
    t = np.arange(int(sr * seconds)) / sr
    x = sum(np.sin(2 * math.pi * f * t) for f in freqs) * amp / len(freqs)
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    frames = np.column_stack([pcm] * channels)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(frames.tobytes())
    return out.getvalue()


def _band_rms(data: bytes, lo: float, hi: float) -> float:
    with wave.open(io.BytesIO(data), "rb") as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        x = x.reshape(-1, w.getnchannels())[:, 0].astype(np.float64) / 32768.0
    spec = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    band = spec[(freqs >= lo) & (freqs < hi)]
    return float(np.sqrt(np.mean(band**2))) if len(band) else 0.0


def test_seal_darkens_highs_keeps_level_and_format():
    src = _sine_wav([80.0, 4000.0])
    sealed = cab_filter.seal_wav(src)
    # The cab: highs well down relative to lows, overall level held.
    high_drop = _band_rms(sealed, 3000, 5000) / _band_rms(src, 3000, 5000)
    low_hold = _band_rms(sealed, 40, 160) / _band_rms(src, 40, 160)
    assert high_drop < 0.2  # -16 dB shelf plus the 2.4 kHz lowpass
    assert low_hold > 0.8  # body low end survives the RMS re-match
    with wave.open(io.BytesIO(src), "rb") as a, wave.open(io.BytesIO(sealed), "rb") as b:
        assert (a.getframerate(), a.getnchannels(), a.getnframes(), a.getsampwidth()) == (
            b.getframerate(),
            b.getnchannels(),
            b.getnframes(),
            b.getsampwidth(),
        )


def test_seal_is_deterministic():
    src = _sine_wav([120.0, 1800.0], channels=1)
    assert cab_filter.seal_wav(src) == cab_filter.seal_wav(src)


def test_seal_passes_non_pcm_through():
    assert cab_filter.seal_wav(b"OggS not a wav at all") == b"OggS not a wav at all"


def test_playback_bytes_seals_engine_bands_only():
    # The band cuts come back transformed (and cached); any other key comes
    # back byte-identical to the raw asset.
    key = "engine/idle"
    raw = audio._asset_bytes(key, ("ogg", "wav"))
    assert raw is not None
    sealed = audio._playback_bytes(key, ("ogg", "wav"))
    assert sealed is not None
    if raw[1] == "wav":
        assert sealed[0] != raw[0]
        assert audio._playback_bytes(key, ("ogg", "wav"))[0] is sealed[0]  # cached
    other = "ui/menu_select"
    if audio._asset_bytes(other, ("ogg", "wav")) is not None:
        assert audio._playback_bytes(other, ("ogg", "wav")) == audio._asset_bytes(
            other, ("ogg", "wav")
        )
