"""Audition: does the synthesized engine want a real recorded bed under it?

Audition only -- reads shipped .ogg files, writes WAVs to C:\\temp\\fftest,
touches no save data.

NORM'S PROPOSAL (2026-07-20): mix the synthesized engine with a real in-cab
truck sound, maybe the idle. His characterization was that the synth sounded
electronic at first, but that the shipped low/mid/high sound MORE synthesized
on a back-to-back listen.

Measurement says he ranked them correctly. Cycle-to-cycle correlation -- how
much each firing cycle is a literal copy of the one before it, swept over f0
so a wrong period cannot fake a low score:

    idle.ogg   (Duff, real)   r = +0.67
    engine_v1  (synthesized)  r = +0.63
    mid.ogg    (shipped)      r = +0.996

So the synth already varies cycle to cycle about as much as a real recording
does, and the shipped loops are the outlier by a mile -- every cycle is a
near-exact copy, which is the textbook electronic tell. That is what he heard.

BUT IT ALSO MEANS THE SYNTH DOES NOT NEED MORE CYCLE VARIATION. It already
has it. So the "electronic at first" impression is coming from somewhere else,
and there are two candidates this file tests:

1. THE LOOP REPEATS. Cycle-to-cycle variation lives INSIDE the loop, but the
   loop itself is byte-identical every 0.64 s at 1500 rpm. The ear learns a
   0.64 s pattern very quickly, and once learned it stops sounding like an
   engine and starts sounding like a sample. Cycle variation cannot help with
   this -- only loop length or an asynchronous partner can.
2. THERE IS NO CAB AROUND IT. No wind, no HVAC, no chassis rattle, no tire
   roar. A bare engine with nothing else in the room reads as a synth patch
   however good the engine is.

WHY NOT idle.ogg AS THE BED -- the one place I think the proposal bites. The
idle is a RUNNING ENGINE with its own firing frequency. Mixed under a 1500 rpm
synth you get two engines in the cab at once, at unrelated rates, beating
against each other. Rendered below so it can be heard rather than argued.

The bed wants to be the NON-periodic part of the cab: wind, tire, structure.
That is exactly the split Norm already made for gravel vs rumble strip --
synthesize what is timing, sample what is texture -- applied one level up.
`vehicle/road.ogg` is already that slot, already 30 s, and already plays under
the engine, so the architecture exists. It is currently ElevenLabs-generated;
upgrading it to a real in-cab bed is the high-value move.

Usage: uv run --with numpy --with soundfile python sound-test/engine_mix.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pulse_synth
from engine_v1 import engine
from pulse_synth import SR, write_wav

pulse_synth.OUT = Path(r"C:\temp\fftest")
ASSETS = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "assets" / "sounds"


def read_mono(rel: str, seconds: float) -> np.ndarray:
    """Read a shipped asset as mono at SR, tiled/cropped to length."""
    import soundfile as sf

    data, sr = sf.read(str(ASSETS / rel), always_2d=True)
    mono = data.mean(axis=1)
    if sr != SR:
        idx = np.linspace(0, len(mono) - 1, int(len(mono) * SR / sr))
        mono = np.interp(idx, np.arange(len(mono)), mono)
    n = int(seconds * SR)
    if not len(mono):
        return np.zeros(n)
    return np.tile(mono, int(n / len(mono)) + 1)[:n]


def norm(x: np.ndarray) -> np.ndarray:
    return x / (np.abs(x).max() or 1.0)


def cycle_corr(x: np.ndarray, sr: int = SR, lo: float = 15.0, hi: float = 130.0) -> tuple[float, float]:
    """Best-case cycle-to-cycle correlation, sweeping f0.

    Sweeping matters: pick the wrong period and successive windows misalign,
    which reports a spuriously LOW correlation and flatters the signal. Taking
    the maximum over plausible f0 makes the number an upper bound on how
    repetitive the signal is, which is the honest direction to err.
    """
    best = (-9.0, 0.0)
    for p in range(int(sr / hi), int(sr / lo)):
        n = min((len(x) // p) - 1, 40)
        if n < 8:
            continue
        cs = [np.corrcoef(x[i * p:(i + 1) * p], x[(i + 1) * p:(i + 2) * p])[0, 1]
              for i in range(n)
              if x[i * p:(i + 1) * p].std() > 0 and x[(i + 1) * p:(i + 2) * p].std() > 0]
        if cs and np.mean(cs) > best[0]:
            best = (float(np.mean(cs)), sr / p)
    return best


def main() -> None:
    secs = 8.0

    print("CYCLE-TO-CYCLE REPETITION (best-case f0, so this is an upper bound)")
    print("  ~0.67 = a real recording. ~1.00 = every cycle is a copy: electronic.")
    for label, rel in (("idle.ogg (Duff, REAL)", "engine/idle.ogg"),
                       ("mid.ogg  (shipped)", "engine/mid.ogg")):
        r, f = cycle_corr(read_mono(rel, 3.0))
        print(f"    {label:24s} r={r:+.3f} at {f:5.1f} Hz")
    short, _ = engine(1500, cycles=8, load=0.6)
    r, f = cycle_corr(np.tile(short, int(secs * SR / len(short)) + 1)[:int(3 * SR)])
    print(f"    {'engine_v1 (synth)':24s} r={r:+.3f} at {f:5.1f} Hz")

    print("\n1. LOOP LENGTH -- same synth, different repeat period")
    print("   Listen for the point where you stop hearing a repeating sample.")
    for cycles, tag in ((8, "0.6s"), (32, "2.6s"), (128, "10s")):
        sig, _ = engine(1500, cycles=cycles, load=0.6)
        reps = max(1, int(secs * SR / len(sig)))
        write_wav(f"mix_looplen_{tag}.wav", np.tile(sig, reps))
        print(f"    {cycles:3d} cycles = {len(sig) / SR:5.2f}s loop, tiled x{reps}")

    print("\n2. NORM'S IDEA, LITERALLY: synth + idle.ogg underneath")
    print("   Two engines at once. Listen for the beating -- this is the failure.")
    body = np.tile(short, int(secs * SR / len(short)) + 1)[:int(secs * SR)]
    idle = read_mono("engine/idle.ogg", secs)
    for tag, level in (("quiet", 0.25), ("even", 0.6)):
        write_wav(f"mix_synth_plus_idle_{tag}.wav", norm(norm(body) + level * norm(idle)))

    print("\n3. THE VERSION I THINK IS RIGHT: synth + non-periodic cab bed")
    print("   road.ogg is 30s and asynchronous to the engine loop, so the")
    print("   composite never repeats at either period.")
    road = read_mono("vehicle/road.ogg", secs)
    for tag, level in (("subtle", 0.30), ("balanced", 0.55), ("bed_forward", 0.85)):
        write_wav(f"mix_synth_plus_road_{tag}.wav", norm(norm(body) + level * norm(road)))

    print("\n4. LONG LOOP + BED -- both fixes together, the actual proposal")
    long_sig, _ = engine(1500, cycles=128, load=0.6)
    long_body = np.tile(long_sig, int(secs * SR / len(long_sig)) + 1)[:int(secs * SR)]
    write_wav("mix_best_long_plus_road.wav", norm(norm(long_body) + 0.55 * norm(road)))

    print("\n5. CONTROL: the shipped mid.ogg mixed the same way, for reference")
    mid = read_mono("engine/mid.ogg", secs)
    write_wav("mix_control_shipped_plus_road.wav", norm(norm(mid) + 0.55 * norm(road)))

    print(f"\nwrote to {pulse_synth.OUT}")


if __name__ == "__main__":
    main()
