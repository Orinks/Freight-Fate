"""Granular gravel: unlimited, density-controllable shoulder and arrester-bed texture.

Reads licensed source from the local Splice folder; writes auditions to
C:\\temp\\fftest. Never commits audio -- the source stays untracked.

WHY GRANULAR AND NOT A LOOP. Gravel is a stochastic texture: no pitch, no
phrase, no periodicity. Loop five seconds of it and the ear learns the pattern
within about three passes, at which point it stops being gravel and becomes a
sample. Cut the same five seconds into short grains and re-scatter them with
randomised timing, level and playback position, and you get material that
never repeats while sounding identical to the source, because every grain IS
the source.

That also solves the problem a fixed recording cannot: DENSITY BECOMES A
PARAMETER. A car on gravel and a loaded tractor-trailer on gravel are the same
stones being struck at different rates -- eighteen contact patches instead of
four, more weight pressing them in. So one recording drives everything from a
light shoulder scuff to a truck plowing an arrester bed, just by changing
grains per second. No second recording needed, and no pitch-shifting, which
would drag the stone-impact spectrum and make the gravel sound like a
different size of rock.

Same split as the rest of this work: the grains are real recorded stone, the
scheduling is modelled.

Usage: uv run --with numpy --with soundfile python sound-test/gravel_granular.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pulse_synth
import soundfile as sf
from pulse_synth import SR, write_wav

pulse_synth.OUT = Path(r"C:\temp\fftest")
PACKS = Path(r"C:\Users\nrome\Documents\Splice\Samples\packs")
SOURCES = {
    "auto": PACKS / "Auto Vehicles Vol. 1" / "AutoDriveOffGravel_SFXB.422.wav",
    "suv": PACKS / "Auto Vehicles Vol. 2" / "SUVDirt_BW.60767.wav",
}

RNG = np.random.default_rng(11)  # fixed seed: reruns are byte-identical


def load(path: Path) -> np.ndarray:
    data, sr = sf.read(str(path), always_2d=True)
    mono = data.mean(axis=1)
    if sr != SR:
        mono = np.interp(np.linspace(0, len(mono) - 1, int(len(mono) * SR / sr)),
                         np.arange(len(mono)), mono)
    # Trim dead air at either end so grains never land on silence.
    e = np.abs(mono)
    e = np.convolve(e, np.ones(int(0.01 * SR)) / int(0.01 * SR), mode="same")
    live = np.where(e > e.max() * 0.06)[0]
    return mono[live[0]:live[-1]] if len(live) > 2 else mono


def granulate(
    src: np.ndarray,
    seconds: float,
    grains_per_s: float = 120.0,
    grain_ms: float = 55.0,
    jitter: float = 0.6,
    level_spread: float = 0.5,
) -> np.ndarray:
    """Scatter overlapping grains drawn from random points in the source.

    grain_ms is deliberately short. Long grains carry recognisable fragments of
    the original and the repeat becomes audible again; short ones carry only
    texture. Below about 25 ms you start hearing the grain envelope itself as a
    buzz at the grain rate, which is the classic granular artefact -- so 40-70
    ms is the usable window for stone.

    jitter randomises the spacing. Perfectly regular grain timing produces a
    tone at the grain rate for the same reason a rumble strip does; the whole
    point here is that the result must NOT be periodic.
    """
    n = int(seconds * SR)
    out = np.zeros(n + SR)
    g = max(8, int(grain_ms * 0.001 * SR))
    window = np.hanning(g)
    count = max(1, int(seconds * grains_per_s))
    # Nominal spacing, then jittered so no periodicity survives.
    step = n / count
    for i in range(count):
        pos = int(i * step + RNG.uniform(-jitter, jitter) * step)
        if pos < 0 or pos >= n:
            continue
        start = RNG.integers(0, max(1, len(src) - g))
        amp = 1.0 + level_spread * RNG.standard_normal()
        out[pos:pos + g] += src[start:start + g] * window * max(0.0, amp)
    out = out[:n]
    return out / (np.abs(out).max() or 1.0)


def deceleration_curve(seconds: float, v0_mph: float = 60.0, g_decel: float = 0.40) -> np.ndarray:
    """Speed over time for a truck entering an arrester bed.

    Arrester beds decelerate at roughly 0.3-0.5 g, so 60 mph is scrubbed in
    about five seconds and 300-400 feet. Density should follow SPEED, because
    the impact rate is stones-per-second and that falls with how fast the
    tyres are moving through them.
    """
    n = int(seconds * SR)
    t = np.arange(n) / SR
    v = np.maximum(v0_mph * 0.44704 - g_decel * 9.81 * t, 0.0)
    return v / (v[0] or 1.0)


def graded(src: np.ndarray, seconds: float, curve: np.ndarray, peak_density: float) -> np.ndarray:
    """Granulate with a time-varying density, following a normalised curve."""
    n = int(seconds * SR)
    out = np.zeros(n + SR)
    g = max(8, int(0.055 * SR))
    window = np.hanning(g)
    pos = 0.0
    while pos < n:
        frac = curve[min(int(pos), n - 1)]
        rate = max(4.0, peak_density * frac)
        start = RNG.integers(0, max(1, len(src) - g))
        amp = (0.35 + 0.65 * frac) * (1.0 + 0.5 * RNG.standard_normal())
        i = int(pos)
        out[i:i + g] += src[start:start + g] * window * max(0.0, amp)
        pos += SR / rate * RNG.uniform(0.4, 1.6)
    out = out[:n]
    return out / (np.abs(out).max() or 1.0)


def main() -> None:
    src = {k: load(p) for k, p in SOURCES.items() if p.exists()}
    for k, v in src.items():
        print(f"  source {k:5s} {len(v) / SR:5.2f}s usable")
    base = src.get("auto", next(iter(src.values())))

    print("\nDENSITY LADDER -- one source, from a scuff to a plough")
    for tag, dens in (("light", 45), ("car", 110), ("truck", 320), ("plough", 900)):
        y = granulate(base, 6.0, grains_per_s=dens)
        write_wav(f"gravel_{tag}.wav", y)
        e = np.abs(y)
        e = np.convolve(e, np.ones(480) / 480, mode="same")
        print(f"  {tag:7s} {dens:4d} grains/s   envelope variation {e.std() / (e.mean() or 1):.2f}")

    print("\nGRAIN LENGTH -- too long repeats, too short buzzes")
    for ms in (25, 55, 120):
        write_wav(f"gravel_grain{ms}ms.wav", granulate(base, 5.0, 320, grain_ms=ms))
        print(f"  {ms:3d} ms grains")

    print("\nRUNAWAY RAMP -- density follows the deceleration curve")
    secs = 7.0
    curve = deceleration_curve(secs)
    write_wav("gravel_runaway_ramp.wav", graded(base, secs, curve, peak_density=900))
    stop = np.argmax(curve <= 0.01) / SR if (curve <= 0.01).any() else secs
    print(f"  60 mph to rest in {stop:.1f}s at 0.40 g")

    print("\nSHOULDER DRIFT -- on, held, off")
    n = int(6.0 * SR)
    t = np.arange(n) / SR
    eng = np.clip(np.minimum((t - 0.5) / 0.4, (5.0 - t) / 0.5), 0.0, 1.0)
    write_wav("gravel_shoulder_drift.wav", graded(base, 6.0, eng, peak_density=320))

    if "suv" in src:
        print("\nBLEND -- auto grains over SUV grains, two stone sizes")
        a = granulate(base, 6.0, 320)
        b = granulate(src["suv"], 6.0, 220)
        write_wav("gravel_blend.wav", (a + 0.7 * b) / 1.7)

    print(f"\nwrote to {pulse_synth.OUT}")


if __name__ == "__main__":
    main()
