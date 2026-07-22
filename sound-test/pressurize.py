"""Build the air-pressurization loop: the "building air" hiss under a cold start.

Spec (Norm 2026-07-21): a soft, seamless hiss that plays while the air system
is below 100 psi and stops when it is ready -- the blind player HEARS the air
build (faster when you rev, per the sim) and hears it stop. The game already
owns the cutout: `vehicle/air_dryer_purge.ogg` fires the "pshht" at ready, so
this loop only has to be the continuous fill that precedes it.

896's own build (0-14.5 s) is real but very faint (rms ~0.01, buried under
idle), so it can't carry the layer. Instead take a REAL air-brake release hiss,
flatten its decay into a steady level, and crossfade-loop it -- real pneumatic
timbre, constant level, seamless tiling for however long the sim takes to reach
100 psi (~11 s idle, ~6 s revving). A Bantam-pump variant is offered too, since
a compressor pumps rhythmically. Norm's ear picks the fill.

Outputs to C:\\temp\\ffsound\\air as pressurize_hiss / pressurize_pump, plus
pressurize_hiss_11s / pressurize_pump_11s demos (tiled to a full idle build,
ending where the game would fire the dryer purge).

Usage: uv run --with numpy --with soundfile --with scipy python sound-test/pressurize.py
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

OUT = Path(r"C:\temp\ffsound\air")
LV = Path(r"C:\temp\ffsound\splice\Samples\packs\Large Vehicles")
IND = Path(r"C:\temp\ffsound\splice\Samples\packs\Industry Vol. 1")
HISS_SRC = LV / "SemiTruckAirBrake_BWU.95.wav"     # long release hiss to flatten
PUMP_SRC = IND / "BantamBrakeMach_S08IN.62.wav"    # rhythmic pneumatic pump
LOOP_S = 2.5


def hp(x: np.ndarray, fc: float) -> np.ndarray:
    b, a = butter(2, fc / (C.SR / 2), "high")
    return filtfilt(b, a, x)


def write(name: str, x: np.ndarray, target_rms: float = 0.045) -> None:
    # Soft by default: this is a background layer under the idle, not a feature.
    x = np.nan_to_num(np.asarray(x, float))
    x = x * (target_rms / (float(np.sqrt(np.mean(x ** 2))) or 1.0))
    p = float(np.max(np.abs(x))) or 1.0
    if p > 0.97:
        x = x * (0.97 / p)
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as fh:
        fh.setnchannels(1); fh.setsampwidth(2); fh.setframerate(C.SR)
        fh.writeframes((x * 32767).astype("<i2").tobytes())


def smooth_env(x: np.ndarray, w_s: float = 0.02) -> np.ndarray:
    w = max(4, int(w_s * C.SR))
    return np.convolve(np.abs(x), np.ones(w) / w, "same")


def flatten(x: np.ndarray, floor_frac: float = 0.25) -> np.ndarray:
    """Divide out the decay so a real hiss becomes a steady, loopable fill."""
    env = smooth_env(x)
    env = np.maximum(env, floor_frac * (env.max() or 1.0))
    return x / env


def loop_hiss(x: np.ndarray, xfade_s: float = 0.2) -> np.ndarray:
    """Crossfade the tail into the head so the segment tiles seamlessly. Long
    equal-power crossfade is safe here -- hiss is stochastic, so no combing."""
    xf = int(xfade_s * C.SR)
    if len(x) < 2 * xf:
        return x
    body = x[:len(x) - xf].copy()
    w = np.linspace(0.0, 1.0, xf)
    body[:xf] = x[:xf] * np.sqrt(w) + x[len(x) - xf:] * np.sqrt(1.0 - w)
    return body


def steady_window(x: np.ndarray, len_s: float) -> np.ndarray:
    """The loudest sustained stretch -- where the hiss is fullest, past onset."""
    n = int(len_s * C.SR)
    if len(x) <= n:
        return x
    env = smooth_env(x, 0.05)
    csum = np.cumsum(env)
    best = int(np.argmax(csum[n:] - csum[:-n]))
    return x[best:best + n]


def tiled(loop: np.ndarray, secs: float) -> np.ndarray:
    reps = int(np.ceil(secs * C.SR / len(loop)))
    out = np.tile(loop, reps)[:int(secs * C.SR)]
    fade = int(0.15 * C.SR)                       # ease in/out for the demo
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) Continuous fill: flatten a real release hiss, high-pass the hum, loop.
    hiss = C.load_wav(HISS_SRC)
    hiss = hp(hiss, 220.0)
    hiss = flatten(steady_window(hiss, LOOP_S + 0.6))
    hiss_loop = loop_hiss(hiss[:int(LOOP_S * C.SR)])
    write("pressurize_hiss.wav", hiss_loop)
    write("pressurize_hiss_11s.wav", tiled(hiss_loop, 11.0))

    # 2) Pump variant: a steady stretch of the Bantam, softened and looped.
    pump = C.load_wav(PUMP_SRC)
    pump = hp(pump, 160.0)
    pump_loop = loop_hiss(steady_window(pump, LOOP_S), xfade_s=0.12)
    write("pressurize_pump.wav", pump_loop)
    write("pressurize_pump_11s.wav", tiled(pump_loop, 11.0))

    print(f"  pressurize_hiss.wav / pressurize_pump.wav  ({LOOP_S:.1f}s seamless loops)")
    print("  + _11s demos (full idle build; game fires air_dryer_purge at the end)")
    print(f"  wrote to {OUT}")


if __name__ == "__main__":
    main()
