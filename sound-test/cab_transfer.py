"""Cab transfer function audition: does a cabin filter "internalize" the engine?

Tester complaint (via Josh, 2026-08-13): the rebuilt engine voice reads as
EXTERNAL -- a truck heard from outside, not from the driver's seat. That is
literally a description of a missing cabin transfer function. The 896 cuts
were recorded in a working cab, but cleanly; a driver's ear gets the engine
through the firewall and glass (strong high-frequency loss), through the
body structure (low-end boom the panels pass and amplify), and inside a
small hard cavity (very short early reflections). None of that is in the
shipped cuts, so the voice sits "in front of" the listener instead of
around them.

This script applies a candidate cab transfer to each licensed engine band
cut and writes loudness-matched A/B/C renders for the owner's ear:

  <band>_1_original.wav       the shipped cut, untouched
  <band>_2_cab.wav            moderate cab: shelf -10 dB above 1 kHz,
                              lowpass at 3.5 kHz, +3 dB body low end,
                              a whisper of 2-4 ms early reflections
  <band>_3_cab_sealed.wav     windows-up cab: -16 dB shelf, 2.4 kHz
                              lowpass, +5 dB body, fuller reflections

Every render is RMS-matched to its original so the A/B judges timbre, not
level (a quieter copy always reads duller). Filters run circularly -- the
IIR warms up over one full loop pass and the reflections wrap -- so each
render still loops seamlessly and can be auditioned on repeat.

If an intensity between _2 and _3 wins, the keeper becomes a real-time
biquad chain on the engine bus (cheap: four biquads + two taps per band),
sitting BETWEEN the engine voice and the ear -- it wraps rebuilt and
classic alike, and the door/window states of the queued cabin-audio work
modulate it later.

Deterministic: pure arithmetic, no randomness. Reads the licensed cuts
(sounds-licensed/engine), writes sound-test/render-cab/*.wav (gitignored).

Usage: uv run python sound-test/cab_transfer.py
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT / "src" / "freight_fate" / "assets" / "sounds-licensed" / "engine"
OUT_DIR = Path(__file__).resolve().parent / "render-cab"

BANDS = ("idle", "low", "mid", "midhigh", "high")

# (name, shelf_db, lowpass_hz, body_shelf_db, boom_db, tap_gains)
VARIANTS = (
    ("2_cab", -10.0, 3500.0, 3.0, 2.5, (0.20, 0.14)),
    ("3_cab_sealed", -16.0, 2400.0, 5.0, 4.0, (0.28, 0.20)),
)

# Early-reflection delays: first side-glass/firewall bounces of a cab-sized
# cavity (roughly 0.6 m and 1.1 m extra path).
TAP_MS = (1.7, 3.3)

HIGH_SHELF_HZ = 1000.0  # glass/firewall attenuation corner
BODY_SHELF_HZ = 100.0  # structure-borne low end
BOOM_HZ = 63.0  # panel boom center
BOOM_Q = 1.1


def _biquad(b0, b1, b2, a0, a1, a2):
    return np.array([b0 / a0, b1 / a0, b2 / a0]), np.array([1.0, a1 / a0, a2 / a0])


def high_shelf(sr: float, fc: float, gain_db: float, slope: float = 0.9):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * fc / sr
    alpha = math.sin(w0) / 2.0 * math.sqrt((a + 1 / a) * (1 / slope - 1) + 2)
    cw = math.cos(w0)
    two_sqrt_a_alpha = 2.0 * math.sqrt(a) * alpha
    return _biquad(
        a * ((a + 1) + (a - 1) * cw + two_sqrt_a_alpha),
        -2 * a * ((a - 1) + (a + 1) * cw),
        a * ((a + 1) + (a - 1) * cw - two_sqrt_a_alpha),
        (a + 1) - (a - 1) * cw + two_sqrt_a_alpha,
        2 * ((a - 1) - (a + 1) * cw),
        (a + 1) - (a - 1) * cw - two_sqrt_a_alpha,
    )


def low_shelf(sr: float, fc: float, gain_db: float, slope: float = 0.9):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * fc / sr
    alpha = math.sin(w0) / 2.0 * math.sqrt((a + 1 / a) * (1 / slope - 1) + 2)
    cw = math.cos(w0)
    two_sqrt_a_alpha = 2.0 * math.sqrt(a) * alpha
    return _biquad(
        a * ((a + 1) - (a - 1) * cw + two_sqrt_a_alpha),
        2 * a * ((a - 1) - (a + 1) * cw),
        a * ((a + 1) - (a - 1) * cw - two_sqrt_a_alpha),
        (a + 1) + (a - 1) * cw + two_sqrt_a_alpha,
        -2 * ((a - 1) + (a + 1) * cw),
        (a + 1) + (a - 1) * cw - two_sqrt_a_alpha,
    )


def peaking(sr: float, fc: float, gain_db: float, q: float):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * fc / sr
    alpha = math.sin(w0) / (2.0 * q)
    cw = math.cos(w0)
    return _biquad(
        1 + alpha * a, -2 * cw, 1 - alpha * a, 1 + alpha / a, -2 * cw, 1 - alpha / a
    )


def lowpass(sr: float, fc: float, q: float = 0.7071):
    w0 = 2.0 * math.pi * fc / sr
    alpha = math.sin(w0) / (2.0 * q)
    cw = math.cos(w0)
    return _biquad((1 - cw) / 2, 1 - cw, (1 - cw) / 2, 1 + alpha, -2 * cw, 1 - alpha)


def filt_circular(x: np.ndarray, sections) -> np.ndarray:
    """Run a biquad chain over a loop as if it were periodic.

    Two passes over the concatenated loop, keep the second: the filter state
    entering the kept pass is the state a steady repeating loop would carry,
    so the render's seam matches the original's.
    """
    y = np.concatenate([x, x])
    for b, a in sections:
        out = np.zeros_like(y)
        x1 = x2 = y1 = y2 = 0.0
        for i in range(len(y)):
            xi = y[i]
            yi = b[0] * xi + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2
            out[i] = yi
            x2, x1 = x1, xi
            y2, y1 = y1, yi
        y = out
    return y[len(x) :]


def early_reflections(x: np.ndarray, sr: float, gains) -> np.ndarray:
    y = x.copy()
    for ms, g in zip(TAP_MS, gains, strict=True):
        y += g * np.roll(x, int(sr * ms / 1000.0))
    return y / (1.0 + sum(gains))


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        assert w.getsampwidth() == 2, f"{path.name}: expected 16-bit PCM"
        data = np.frombuffer(w.readframes(n), dtype=np.int16)
    return data.reshape(-1, ch).astype(np.float64) / 32768.0, sr


def write_wav(path: Path, data: np.ndarray, sr: int) -> None:
    clipped = np.clip(data, -1.0, 1.0)
    pcm = (clipped * 32767.0).round().astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(data.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    for band in BANDS:
        src = ENGINE_DIR / f"{band}.wav"
        if not src.exists():
            print(f"skip {band}: {src} not present (licensed tree required)")
            continue
        x, sr = read_wav(src)
        write_wav(OUT_DIR / f"{band}_1_original.wav", x, sr)
        rms_in = math.sqrt(float(np.mean(x**2)))
        for name, shelf_db, lp_hz, body_db, boom_db, taps in VARIANTS:
            chain = [
                peaking(sr, BOOM_HZ, boom_db, BOOM_Q),
                low_shelf(sr, BODY_SHELF_HZ, body_db),
                high_shelf(sr, HIGH_SHELF_HZ, shelf_db),
                lowpass(sr, lp_hz),
            ]
            y = np.column_stack(
                [filt_circular(x[:, c], chain) for c in range(x.shape[1])]
            )
            y = early_reflections(y, sr, taps)
            rms_out = math.sqrt(float(np.mean(y**2)))
            if rms_out > 0:
                y *= rms_in / rms_out
            peak = float(np.max(np.abs(y)))
            if peak > 0.995:  # loudness match, but never clip the render
                y *= 0.995 / peak
            write_wav(OUT_DIR / f"{band}_{name}.wav", y, sr)
            print(f"{band}: {name} rendered")
    print(f"renders in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
