"""Build the air-pressurization loop: the "building air" hiss under a cold start.

Spec (Norm 2026-07-21): a soft, seamless hiss that plays while the air system
is below 100 psi and stops when it is ready -- the blind player HEARS the air
build (faster when you rev, per the sim) and hears it stop. The game already
owns the cutout: `vehicle/air_dryer_purge.ogg` fires the "pshht" at ready, so
this loop only has to be the continuous fill that precedes it.

First attempt looped a real air-brake release directly. Two artifacts (Norm's
ear): a ~half-second WHINE (a real air whistle at ~2.7 kHz in the sample) and a
glaring SEAM (the release decays, so the level dropped at the loop point). Both
come from looping a real, decaying, whistling recording.

Fix: resynthesize instead of loop. Take the real air-brake spectrum, median-
smooth it across frequency to remove the tonal whistle (no whine), then build a
loop directly in the frequency domain -- target magnitude, random phase over
exactly the loop length. An inverse FFT of that is one period of a periodic
signal: constant level, ZERO seam, no crossfade, and the same real air timbre.
Deterministic (seeded), so it regenerates. A rhythmic Bantam-pump variant is
offered too (a compressor pumps); its macro level is flattened so it does not
seam either.

Outputs to C:\\temp\\ffsound\\air as pressurize_hiss / pressurize_pump, plus
pressurize_hiss_11s / pressurize_pump_11s demos.

Usage: uv run --with numpy --with soundfile --with scipy python sound-test/pressurize.py
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt, medfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

OUT = Path(r"C:\temp\ffsound\air")
LV = Path(r"C:\temp\ffsound\splice\Samples\packs\Large Vehicles")
IND = Path(r"C:\temp\ffsound\splice\Samples\packs\Industry Vol. 1")
HISS_SRC = LV / "SemiTruckAirBrake_BWU.95.wav"     # real air spectrum to resynthesize
PUMP_SRC = IND / "BantamBrakeMach_S08IN.62.wav"    # rhythmic pneumatic pump
LOOP_S = 2.5
SEED = 20260721   # deterministic phase, so the render reproduces


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


def smooth_env(x: np.ndarray, w_s: float) -> np.ndarray:
    w = max(4, int(w_s * C.SR))
    return np.convolve(np.abs(x), np.ones(w) / w, "same")


def air_shape(x: np.ndarray, nfft: int = 8192) -> tuple[np.ndarray, np.ndarray]:
    """Average magnitude spectrum of the real air, de-whistled by a frequency
    median filter (narrow tonal peaks removed, broadband air shape kept)."""
    x = hp(x, 220.0)
    frames = [np.abs(np.fft.rfft(x[i:i + nfft] * np.hanning(nfft)))
              for i in range(0, len(x) - nfft, nfft // 2)]
    mag = np.mean(frames, axis=0)
    mag = medfilt(mag, 41)                     # kill narrow whistles (~2.7 kHz)
    f = np.fft.rfftfreq(nfft, 1.0 / C.SR)
    return f, mag


def synth_loop(f_src: np.ndarray, mag_src: np.ndarray, len_s: float) -> np.ndarray:
    """One period of periodic noise with the target spectrum: constant level,
    seamless by construction (random phase over exactly the loop length)."""
    n = int(len_s * C.SR)
    f = np.fft.rfftfreq(n, 1.0 / C.SR)
    mag = np.interp(f, f_src, mag_src)
    rng = np.random.default_rng(SEED)
    phase = rng.uniform(0.0, 2.0 * np.pi, len(mag))
    phase[0] = 0.0                              # DC real
    if n % 2 == 0:
        phase[-1] = 0.0                         # Nyquist real
    y = np.fft.irfft(mag * np.exp(1j * phase), n)
    return hp(y, 200.0)                         # drop any sub-bass rumble


def flatten(x: np.ndarray, w_s: float, floor_frac: float = 0.3) -> np.ndarray:
    """Even out the macro level so a decaying source does not seam; a wide
    window keeps pump pulses faster than w_s intact."""
    env = smooth_env(x, w_s)
    env = np.maximum(env, floor_frac * (env.max() or 1.0))
    return x / env


def loop_xfade(x: np.ndarray, xfade_s: float = 0.2) -> np.ndarray:
    xf = int(xfade_s * C.SR)
    if len(x) < 2 * xf:
        return x
    body = x[:len(x) - xf].copy()
    w = np.linspace(0.0, 1.0, xf)
    body[:xf] = x[:xf] * np.sqrt(w) + x[len(x) - xf:] * np.sqrt(1.0 - w)
    return body


def steady_window(x: np.ndarray, len_s: float) -> np.ndarray:
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
    fade = int(0.15 * C.SR)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) Continuous fill: resynthesize the de-whistled air spectrum as a
    #    perfectly periodic loop -- no whine, no seam, constant level.
    f, mag = air_shape(C.load_wav(HISS_SRC))
    hiss_loop = synth_loop(f, mag, LOOP_S)
    write("pressurize_hiss.wav", hiss_loop)
    write("pressurize_hiss_11s.wav", tiled(hiss_loop, 11.0))

    # 2) Pump variant: a steady Bantam stretch, macro-level flattened (so it
    #    does not seam) then crossfade-looped; the pulse rhythm survives.
    pump = hp(C.load_wav(PUMP_SRC), 160.0)
    pump = flatten(steady_window(pump, LOOP_S + 0.4), w_s=0.35)
    pump_loop = loop_xfade(pump[:int(LOOP_S * C.SR)], xfade_s=0.12)
    write("pressurize_pump.wav", pump_loop)
    write("pressurize_pump_11s.wav", tiled(pump_loop, 11.0))

    print(f"  pressurize_hiss.wav (resynth, whine-free, seamless) / "
          f"pressurize_pump.wav  ({LOOP_S:.1f}s loops)")
    print("  + _11s demos (game fires air_dryer_purge at the end)")
    print(f"  wrote to {OUT}")


if __name__ == "__main__":
    main()
