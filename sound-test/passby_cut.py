"""Cut pass-by candidates out of the Splice roadside takes.

A pass-by is an envelope, not a pitch: the truck approaches, goes abeam, and
recedes, and the moment that matters is the level peak. The survey
(``splice_survey.py``) answers what a file IS -- real or looped, interior or
exterior, where the engine sits -- and this answers where to cut it.

Two versions come out of each candidate, because the survey settled the
question the game actually cares about: these takes carry 0.07-0.19 of their
energy below 200 Hz, which is a microphone at the roadside, not a driver
behind glass. Raw is right if the cue is ever heard with a window down; the
cab version rolls the top off the way a closed cab does.

Read-only on the sources. Writes to C:\\temp\\fftest\\passby.

Usage: uv run --with numpy --with soundfile python sound-test/passby_cut.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SRC = Path(r"C:\temp\fftest\splice")
OUT = Path(r"C:\temp\fftest\passby")
SR = 48000

# What the cue is worth in the game: long enough to hear the truck arrive and
# go, short enough that it never outlasts the vehicle it belongs to. The
# existing ElevenLabs cues sit in this range.
LEAD_S = 1.4
TAIL_S = 1.8
# The cab. A closed Class 8 cab is not a brick wall -- you hear plenty -- but
# the top end goes first, so a one-pole rolloff at a few kHz reads right
# without sounding like a blanket over the speaker.
CAB_CUTOFF_HZ = 2600.0


def load(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), always_2d=True)
    return data.mean(axis=1), sr


def resample(x: np.ndarray, sr: int) -> np.ndarray:
    if sr == SR:
        return x
    idx = np.linspace(0, len(x) - 1, int(len(x) * SR / sr))
    return np.interp(idx, np.arange(len(x)), x)


def envelope(x: np.ndarray, win_s: float = 0.05) -> np.ndarray:
    """Smoothed RMS. The peak of this is where the truck is abeam."""
    w = max(1, int(win_s * SR))
    power = np.convolve(x * x, np.ones(w) / w, mode="same")
    return np.sqrt(np.maximum(power, 0.0))


def one_pole_lowpass(x: np.ndarray, cutoff_hz: float) -> np.ndarray:
    a = np.exp(-2.0 * np.pi * cutoff_hz / SR)
    out = np.empty_like(x)
    prev = 0.0
    for i, sample in enumerate(x):
        prev = (1.0 - a) * sample + a * prev
        out[i] = prev
    return out


def normalise(x: np.ndarray, peak: float = 0.89) -> np.ndarray:
    high = float(np.max(np.abs(x))) or 1.0
    return x * (peak / high)


def fade(x: np.ndarray, ms: float = 60.0) -> np.ndarray:
    n = min(int(ms / 1000.0 * SR), len(x) // 2)
    if n <= 0:
        return x
    ramp = np.linspace(0.0, 1.0, n)
    out = x.copy()
    out[:n] *= ramp
    out[-n:] *= ramp[::-1]
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(SRC.glob("*PassBy*.wav")) + sorted(SRC.glob("*Away*.wav"))
    if not files:
        print(f"no source takes in {SRC}")
        return
    for path in files:
        mono, sr = load(path)
        x = resample(mono, sr)
        env = envelope(x)
        peak = int(np.argmax(env))
        start = max(0, peak - int(LEAD_S * SR))
        end = min(len(x), peak + int(TAIL_S * SR))
        cut = fade(normalise(x[start:end]))
        stem = path.stem
        sf.write(str(OUT / f"{stem}__raw.wav"), cut, SR)
        sf.write(str(OUT / f"{stem}__cab.wav"), normalise(one_pole_lowpass(cut, CAB_CUTOFF_HZ)), SR)
        # How sharp the pass is: a real abeam moment stands well above the
        # file's own median level. A flat ratio means there is no pass here,
        # just an engine running somewhere -- which is what separates a
        # highway take from a yard recording.
        ratio = float(env[peak] / (np.median(env) or 1e-9))
        print(
            f"{stem:32s} peak at {peak / SR:6.2f}s of {len(x) / SR:6.2f}s   "
            f"cut {start / SR:5.2f}-{end / SR:5.2f}s   peak/median {ratio:5.1f}x"
        )
    print(f"\nwrote {len(files) * 2} candidates to {OUT}")


if __name__ == "__main__":
    main()
