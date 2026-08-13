"""The cab between the engine and the ear: the sealed-cab transfer function.

Testers heard the rebuilt engine voice as EXTERNAL -- a truck heard from
outside, not from the driver's seat (via Josh, 2026-08-13). The cuts were
recorded in a working cab but cleanly; a driver's ear gets the engine
through glass and firewall (strong high-frequency loss), through the body
structure (low end the panels carry and amplify), and inside a small hard
cavity (very short early reflections). This module applies that transfer
to the engine band cuts at load time, so the voice sits around the player
instead of in front of the windshield.

The parameters are the "sealed" (windows-up) variant the owner's ear
picked from the sound-test/cab_transfer.py auditions (2026-08-13): a
-16 dB shelf above 1 kHz, a 2.4 kHz lowpass, +5 dB of body low end, +4 dB
of panel boom at 63 Hz, and two early reflections at 1.7 and 3.3 ms. The
moderate variant from the same auditions is the natural "window cracked"
setting when the cabin-state work (doors/windows) picks intensities.

Implementation: the biquad chain's exact z-transform response and the
reflection comb are evaluated on the rfft bins of the whole loop and
multiplied into its spectrum -- circular convolution, so a seamless loop
stays seamless and the result equals the steady state a repeating loop
would reach through the real-time chain. Each render is RMS-matched to
its input (the transfer shapes timbre, the mixer owns level) with a peak
guard. Pure numpy, deterministic, one-time cost per cut (cached by the
audio engine).

Only 16-bit PCM WAV passes through the transfer; anything else returns
unchanged (the classic voice's ogg deliberately keeps its old sound).
"""

from __future__ import annotations

import io
import logging
import math
import wave

import numpy as np

log = logging.getLogger(__name__)

# Sealed-cab parameters (owner's ear, 2026-08-13; lab in sound-test/cab_transfer.py).
HIGH_SHELF_HZ = 1000.0  # glass/firewall attenuation corner
HIGH_SHELF_DB = -16.0
LOWPASS_HZ = 2400.0
BODY_SHELF_HZ = 100.0  # structure-borne low end
BODY_SHELF_DB = 5.0
BOOM_HZ = 63.0  # panel boom center
BOOM_DB = 4.0
BOOM_Q = 1.1
SHELF_SLOPE = 0.9
LOWPASS_Q = 0.7071
TAP_MS = (1.7, 3.3)  # first side-glass/firewall bounces of a cab-sized cavity
TAP_GAINS = (0.28, 0.20)


def _shelf_coeffs(sr: float, fc: float, gain_db: float, high: bool):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * fc / sr
    alpha = math.sin(w0) / 2.0 * math.sqrt((a + 1 / a) * (1 / SHELF_SLOPE - 1) + 2)
    cw = math.cos(w0)
    two_sqrt_a_alpha = 2.0 * math.sqrt(a) * alpha
    sign = 1.0 if high else -1.0
    b = (
        a * ((a + 1) + sign * (a - 1) * cw + two_sqrt_a_alpha),
        -2 * sign * a * ((a - 1) + sign * (a + 1) * cw),
        a * ((a + 1) + sign * (a - 1) * cw - two_sqrt_a_alpha),
    )
    a_ = (
        (a + 1) - sign * (a - 1) * cw + two_sqrt_a_alpha,
        2 * sign * ((a - 1) - sign * (a + 1) * cw),
        (a + 1) - sign * (a - 1) * cw - two_sqrt_a_alpha,
    )
    return b, a_


def _peaking_coeffs(sr: float, fc: float, gain_db: float, q: float):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * fc / sr
    alpha = math.sin(w0) / (2.0 * q)
    cw = math.cos(w0)
    return (1 + alpha * a, -2 * cw, 1 - alpha * a), (1 + alpha / a, -2 * cw, 1 - alpha / a)


def _lowpass_coeffs(sr: float, fc: float, q: float):
    w0 = 2.0 * math.pi * fc / sr
    alpha = math.sin(w0) / (2.0 * q)
    cw = math.cos(w0)
    return ((1 - cw) / 2, 1 - cw, (1 - cw) / 2), (1 + alpha, -2 * cw, 1 - alpha)


def _transfer(sr: float, n: int) -> np.ndarray:
    """The complex cab response on the rfft bins of an ``n``-sample loop."""
    z1 = np.exp(-2j * math.pi * np.arange(n // 2 + 1) / n)  # z^-1 per bin
    z2 = z1 * z1
    h = np.ones_like(z1)
    for b, a in (
        _peaking_coeffs(sr, BOOM_HZ, BOOM_DB, BOOM_Q),
        _shelf_coeffs(sr, BODY_SHELF_HZ, BODY_SHELF_DB, high=False),
        _shelf_coeffs(sr, HIGH_SHELF_HZ, HIGH_SHELF_DB, high=True),
        _lowpass_coeffs(sr, LOWPASS_HZ, LOWPASS_Q),
    ):
        h *= (b[0] + b[1] * z1 + b[2] * z2) / (a[0] + a[1] * z1 + a[2] * z2)
    taps = np.ones_like(z1)
    for ms, g in zip(TAP_MS, TAP_GAINS, strict=True):
        delay = int(sr * ms / 1000.0)
        taps += g * np.exp(-2j * math.pi * np.arange(n // 2 + 1) * delay / n)
    return h * taps / (1.0 + sum(TAP_GAINS))


def seal_wav(data: bytes) -> bytes:
    """Apply the sealed-cab transfer to a 16-bit PCM WAV, RMS-matched.

    Anything that is not 16-bit PCM comes back unchanged, logged once per
    process -- the transfer must never be the reason a sound goes missing.
    """
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            if w.getsampwidth() != 2 or w.getcomptype() != "NONE":
                log.warning("Cab transfer skipped: not 16-bit PCM")
                return data
            sr = w.getframerate()
            channels = w.getnchannels()
            frames = w.readframes(w.getnframes())
    except (wave.Error, EOFError):
        log.warning("Cab transfer skipped: unreadable WAV", exc_info=True)
        return data
    try:
        x = np.frombuffer(frames, dtype=np.int16).reshape(-1, channels)
        if not len(x):
            log.warning("Cab transfer skipped: empty WAV")
            return data
        x = x.astype(np.float64) / 32768.0
        h = _transfer(float(sr), x.shape[0])
        y = np.column_stack(
            [np.fft.irfft(np.fft.rfft(x[:, c]) * h, n=x.shape[0]) for c in range(channels)]
        )
    except ValueError:
        log.warning("Cab transfer skipped: malformed frame data", exc_info=True)
        return data
    rms_in = math.sqrt(float(np.mean(x**2)))
    rms_out = math.sqrt(float(np.mean(y**2)))
    if rms_out > 0:
        y *= rms_in / rms_out
    peak = float(np.max(np.abs(y)))
    if peak > 0.995:  # loudness match, but never clip
        y *= 0.995 / peak
    pcm = (np.clip(y, -1.0, 1.0) * 32767.0).round().astype(np.int16)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return out.getvalue()
