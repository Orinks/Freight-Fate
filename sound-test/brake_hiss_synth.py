"""Synthesize the brake-RELEASE hiss from the bright truck-air spectrum.

Norm 2026-07-21: the Bantam-based hisses sound "too low" -- it is a small valve
machine, not a big rig's air brake. Same fix as the pressurization loop: pull
the SPECTRUM from a brighter, truck-right source, de-whistle it, and resynthesize.
That gives a brighter hiss, no tonal whine, and -- because it is synthesized --
ANY length we want, which is exactly what "a harder brake gives a longer hiss"
needs.

Source is the bright end of the library (measured centroids): SemiTruckBrake 917
(10.6 kHz, 9 s), SemiTruckAirBrake 95 (9.1 kHz), AirBrake 20321 (8.3 kHz). Their
de-whistled magnitude spectra are averaged into one truck-air-release shape.

Two products:
  brake_hiss_synth_<intensity> -- release one-shots (feather/light/firm/hard):
      fast onset, exponential air-bleed decay; harder = longer and a touch
      louder. Drop-in candidates against the real trimmed hisses.
  brake_hiss_bed -- a steady, seamless hiss loop (freq-domain, constant level,
      zero seam) the game can hold for ANY brake duration and release with its
      own envelope. This is the flexible primitive.

The PRESS clunk stays a real transient (brake_banks.py); only the release hiss
is synthesized here. Outputs to C:\\temp\\ffsound\\brakes.

Usage: uv run --with numpy --with soundfile --with scipy python sound-test/brake_hiss_synth.py
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt, medfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

OUT = Path(r"C:\temp\ffsound\brakes")
LV = Path(r"C:\temp\ffsound\splice\Samples\packs\Large Vehicles")
IND = Path(r"C:\temp\ffsound\splice\Samples\packs\Industry Vol. 1")
BRIGHT_SRCS = [
    LV / "SemiTruckBrake_S08IN.917.wav",       # 10.6 kHz centroid, brightest
    LV / "SemiTruckAirBrake_BWU.95.wav",       # 9.1 kHz
    IND / "AirBrake_BW.20321.wav",             # 8.3 kHz
]
# (tag, seconds, level) -- firmer press = longer bleed and a touch louder.
INTENSITIES = [("feather", 0.16, 0.07), ("light", 0.30, 0.09),
               ("firm", 0.55, 0.11), ("hard", 0.95, 0.12)]
BED_S = 2.0
SEED = 20260721


def hp(x: np.ndarray, fc: float) -> np.ndarray:
    b, a = butter(2, fc / (C.SR / 2), "high")
    return filtfilt(b, a, x)


def write(name: str, x: np.ndarray, target_rms: float) -> None:
    x = np.nan_to_num(np.asarray(x, float))
    x = x * (target_rms / (float(np.sqrt(np.mean(x ** 2))) or 1.0))
    p = float(np.max(np.abs(x))) or 1.0
    if p > 0.97:
        x = x * (0.97 / p)
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as fh:
        fh.setnchannels(1); fh.setsampwidth(2); fh.setframerate(C.SR)
        fh.writeframes((x * 32767).astype("<i2").tobytes())


def air_shape_blend(paths: list[Path], nfft: int = 8192) -> tuple[np.ndarray, np.ndarray]:
    """Average, de-whistled magnitude spectrum across the bright air sources."""
    f = np.fft.rfftfreq(nfft, 1.0 / C.SR)
    acc = np.zeros(len(f))
    used = 0
    for p in paths:
        if not p.exists():
            continue
        x = hp(C.load_wav(p), 220.0)
        frames = [np.abs(np.fft.rfft(x[i:i + nfft] * np.hanning(nfft)))
                  for i in range(0, len(x) - nfft, nfft // 2)]
        if not frames:
            continue
        mag = medfilt(np.mean(frames, axis=0), 41)     # de-whistle
        acc += mag / (mag.max() or 1.0)                # normalize so each counts equally
        used += 1
    return f, acc / max(1, used)


def synth_noise(f_src: np.ndarray, mag_src: np.ndarray, n: int, seed: int) -> np.ndarray:
    """Stationary noise with the target spectrum; periodic over n (seamless)."""
    f = np.fft.rfftfreq(n, 1.0 / C.SR)
    mag = np.interp(f, f_src, mag_src)
    rng = np.random.default_rng(seed)
    phase = rng.uniform(0.0, 2.0 * np.pi, len(mag))
    phase[0] = 0.0
    if n % 2 == 0:
        phase[-1] = 0.0
    return hp(np.fft.irfft(mag * np.exp(1j * phase), n), 300.0)


def release(f: np.ndarray, mag: np.ndarray, len_s: float, seed: int) -> np.ndarray:
    """A brake release: fast onset, exponential air-bleed decay over its length."""
    n = int(len_s * C.SR)
    y = synth_noise(f, mag, n, seed)
    t = np.linspace(0.0, 1.0, n)
    env = np.exp(-3.0 * t)                    # bleeds to ~5% by the end
    atk = int(0.005 * C.SR)
    env[:atk] *= np.linspace(0, 1, atk)
    return y * env


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("brake_hiss_synth_*.wav"):
        stale.unlink()

    f, mag = air_shape_blend(BRIGHT_SRCS)

    shots = []
    for i, (tag, dur, lvl) in enumerate(INTENSITIES):
        r = release(f, mag, dur, SEED + i)
        write(f"brake_hiss_synth_{tag}.wav", r, target_rms=lvl)
        shots.append((tag, r / (np.abs(r).max() or 1) * 0.8))

    # Steady bed the game can hold for any duration, then release itself.
    bed = synth_noise(f, mag, int(BED_S * C.SR), SEED)
    write("brake_hiss_bed.wav", bed, target_rms=0.08)

    # Demo: the four intensities in a row.
    gap = np.zeros(int(0.35 * C.SR))
    demo = np.concatenate([np.concatenate([s, gap]) for _, s in shots])
    write("brake_hiss_synth_demo.wav", demo, target_rms=0.09)

    print("  synthesized brake hisses: " + ", ".join(t for t, _ in shots)
          + "  + brake_hiss_bed (steady, any-length) + demo")
    print(f"  wrote to {OUT}")


if __name__ == "__main__":
    main()
