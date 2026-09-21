"""Audition prototype v2: rumble strip without the formant-synth vowel.

Audition only -- imports nothing from freight_fate except reading two shipped
.ogg loops for the in-context mix. Touches no save data.

v1 was impulse-into-high-Q-resonators, which is literally how you build a
vowel: four isolated peaks ringing for 30-45 ms each. Norm heard it
immediately ("kind of sounds like a formant synth"). Three fixes:

1. WRONG EXCITATION MODEL. A tire on a strip is generating broadband noise
   continuously while in contact; the grooves amplitude-MODULATE it. So the
   pitch comes from the modulation rate, not from resonators ringing at a
   pitch. Same buzz frequency, no vowel.
2. DECAYS FAR TOO LONG. Rubber is lossy -- a groove impact should be dead
   in well under 10 ms, not 45. Short decay = low Q = broad, unpitched.
3. TOO FEW MODES. Isolated peaks read as a vowel; real structures have dense
   overlapping modes. The transient layer here uses many short ones.

Usage: uv run python rumble_v2.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pulse_synth
from pulse_synth import (
    GROOVE_SPACING_M,
    RNG,
    SR,
    TRUCK_AXLES,
    cab_perspective,
    convolve,
    delay,
    pulse_train,
    smoothstep,
    write_wav,
)

# Write beside this file rather than into an audition/ subdirectory.
pulse_synth.OUT = Path(__file__).resolve().parent
ASSETS = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "assets" / "sounds"


def tilt_noise(n: int, peak_hz: float = 115.0, width: float = 1.1) -> np.ndarray:
    """Broadband noise shaped by a BROAD response -- no resonant peaks.

    Shaping happens on the spectrum directly so the response can be made as
    gentle as wanted. A biquad at this centre frequency would need a very low
    Q to avoid ringing; doing it in the frequency domain sidesteps the
    question entirely.
    """
    spec = np.fft.rfft(RNG.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    f = np.maximum(f, 1.0)
    # A wide hump around the tire/suspension region, gentle skirts, grit kept
    # up top so it reads as stone and steel rather than a filtered hum.
    hump = 1.0 / (1.0 + ((np.log2(f / peak_hz)) / width) ** 2)
    highs = 0.16 / (1.0 + (f / 2600.0) ** 1.4)
    lowcut = (f / 32.0) ** 2 / (1.0 + (f / 32.0) ** 2)
    return np.fft.irfft(spec * (hump + highs) * lowcut, n)


def groove_modulator(rate: np.ndarray, duty: float = 0.55) -> np.ndarray:
    """Periodic 0..1 envelope at the groove rate.

    This is what carries the pitch. Widening the window softens the buzz
    toward a hiss; narrowing it sharpens toward a tone.
    """
    n = len(rate)
    mean_rate = float(np.mean(rate))
    w = max(3, int(duty * SR / max(mean_rate, 1.0)))
    # Per-hit amplitude jitter: milling tolerance, tread pattern, debris.
    amp = 1.0 + 0.22 * RNG.standard_normal(n)
    mod = convolve(pulse_train(rate, amp), np.hanning(w))
    mod -= mod.min()
    return mod / max(mod.max(), 1e-9)


def transient_layer(rate: np.ndarray) -> np.ndarray:
    """Per-groove impacts, deliberately heavily damped and densely moded."""
    n = len(rate)
    modes = [(f, d, g) for f, d, g in (
        (74.0, 0.009, 0.9), (118.0, 0.007, 1.0), (162.0, 0.006, 0.8),
        (245.0, 0.005, 0.6), (330.0, 0.004, 0.5), (520.0, 0.003, 0.35),
        (880.0, 0.0025, 0.22), (1500.0, 0.002, 0.13),
    )]
    ir = np.zeros(int(0.05 * SR))
    t = np.arange(len(ir)) / SR
    for freq, dec, gain in modes:
        ir += gain * np.exp(-t / dec) * np.sin(2 * np.pi * freq * t)
    amp = 1.0 + 0.25 * RNG.standard_normal(n)
    w = max(2, int(0.0022 * SR))
    smack = RNG.standard_normal(w) * np.hanning(w)
    return convolve(convolve(pulse_train(rate, amp), smack), ir)


def rumble(
    speed_ms: float,
    engagement: np.ndarray,
    depth: float = 0.88,
    transient_mix: float = 0.45,
    duty: float = 0.55,
) -> np.ndarray:
    """Per-axle, from the cab. Carrier noise modulated at the groove rate."""
    n = len(engagement)
    rate = np.full(n, speed_ms / GROOVE_SPACING_M)
    eng = np.clip(engagement, 0.0, 1.0)
    out = np.zeros(n)
    for dist, load in TRUCK_AXLES:
        gain, hf_keep, prop = cab_perspective(dist)
        # Being further back is a phase offset on the same spatial grid.
        shift = int((dist / GROOVE_SPACING_M % 1.0) * SR / (speed_ms / GROOVE_SPACING_M))
        mod = np.roll(groove_modulator(rate, duty), shift)
        carrier = tilt_noise(n, peak_hz=115.0 * (0.85 + 0.15 * hf_keep))
        body = carrier * (1.0 - depth + depth * mod)
        trans = np.roll(transient_layer(rate), shift) * hf_keep
        sig = (body + transient_mix * trans) * load * eng
        out += gain * delay(sig, prop)
    return out


def read_ogg(path: Path, seconds: float) -> np.ndarray:
    """Read a shipped loop as mono at SR, tiled to length. Empty on failure."""
    try:
        import soundfile as sf
    except ImportError:
        return np.zeros(int(seconds * SR))
    try:
        data, sr = sf.read(str(path), always_2d=True)
    except Exception:
        return np.zeros(int(seconds * SR))
    mono = data.mean(axis=1)
    if sr != SR:  # crude resample is fine for a background bed
        idx = np.linspace(0, len(mono) - 1, int(len(mono) * SR / sr))
        mono = np.interp(idx, np.arange(len(mono)), mono)
    n = int(seconds * SR)
    return np.tile(mono, int(n / len(mono)) + 1)[:n] if len(mono) else np.zeros(n)


def main() -> None:
    speed55, speed70 = 55 * 0.44704, 70 * 0.44704
    on = np.ones(int(4.0 * SR))

    print("rumble v2 -- the fix, held on the strip")
    write_wav("rumble2_55mph.wav", rumble(speed55, on))
    write_wav("rumble2_70mph.wav", rumble(speed70, on))
    write_wav("rumble2_35mph.wav", rumble(35 * 0.44704, on))

    print("\nrumble v2 -- how pitched should it be?")
    write_wav("rumble2_55mph_shallow_mod.wav", rumble(speed55, on, depth=0.55))
    write_wav("rumble2_55mph_deep_mod.wav", rumble(speed55, on, depth=0.99, duty=0.35))
    write_wav("rumble2_55mph_no_transients.wav", rumble(speed55, on, transient_mix=0.0))
    write_wav("rumble2_55mph_transient_heavy.wav", rumble(speed55, on, transient_mix=1.1))

    print("\nrumble v2 -- lane-change crossing (per-axle, cab perspective)")
    t = np.arange(int(5.0 * SR)) / SR
    y = 3.6 * smoothstep((t - 0.8) / 3.0)
    eng = smoothstep((y - 1.55) / 0.23) * (1.0 - smoothstep((y - 2.15) / 0.35))
    write_wav("rumble2_lanechange_70mph.wav", rumble(speed70, eng))

    print("\nin context: mixed under the game's road and engine loops")
    secs = 9.0
    n = int(secs * SR)
    road = read_ogg(ASSETS / "vehicle" / "road.ogg", secs)
    engine = read_ogg(ASSETS / "engine" / "mid.ogg", secs)
    if not road.any() and not engine.any():
        print("  (soundfile unavailable or oggs unreadable -- skipped)")
    else:
        tt = np.arange(n) / SR
        # Drift onto the strip at 3 s, sit on it, correct off at 6 s.
        eng_ctx = smoothstep((tt - 3.0) / 0.5) * (1.0 - smoothstep((tt - 6.0) / 0.5))
        strip = rumble(speed70, eng_ctx)
        bed = 0.30 * road / (np.abs(road).max() or 1) + 0.22 * engine / (np.abs(engine).max() or 1)
        strip = strip / (np.abs(strip).max() or 1)
        for name, level in (("quiet", 0.35), ("realistic", 0.75), ("loud", 1.15)):
            write_wav(f"rumble2_in_context_{name}.wav", bed + level * strip)

    print(f"\nwrote to {pulse_synth.OUT}")


if __name__ == "__main__":
    main()
