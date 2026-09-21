"""Production bake: the turn-signal indicator tone (`vehicle/signal_tone.wav`).

The owner's call (2026-07-27): the soft relay click that marks lane changes
and blinker cadence is hard to hear for some players; modern cabs play a
DESIGNED indicator tone through the speakers, so a clear tone is the
realistic sound of a current-year tractor -- the bare relay click is the
vintage sound (a future era-equipment option).

One neutral tick-tone, repeated by the game at the blinker cadence and
panned to the signaling side. Short and rounded: it has to read through
engine and road noise without ever being an alarm.

Usage: uv run python sound-test/signal_tone.py  (writes straight to assets)
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000
OUT = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "assets" / "sounds"


def build() -> np.ndarray:
    seconds = 0.09
    t = np.arange(int(SR * seconds)) / SR
    # Fundamental with one soft overtone: a designed "tock", not a beep.
    sig = np.sin(2.0 * np.pi * 950.0 * t) + 0.35 * np.sin(2.0 * np.pi * 1900.0 * t)
    # Fast attack, exponential release -- rounded enough to repeat forever.
    env = np.minimum(t / 0.004, 1.0) * np.exp(-t / 0.022)
    sig *= env
    top = float(np.max(np.abs(sig))) or 1.0
    return sig / top * 0.8


def main() -> None:
    path = OUT / "vehicle" / "signal_tone.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.clip(build(), -1.0, 1.0)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes((data * 32767.0).astype("<i2").tobytes())
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
