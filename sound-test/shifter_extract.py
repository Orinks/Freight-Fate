"""Find and cut the gear-shift transients out of the Sony 18-wheeler interior.

Read-only over the library. Writes candidate one-shots to C:\\temp\\fftest.

WHY. `docs/sound-shortlist.md` need 4 (driveline clunk) was the one the sweep
called thin: "expect to build the shift layer by combining the GMC 6000 clunk,
a pitched-down BustedFX transmission clunk, and a Platinum Sounds air
release." Norm heard an actual shifter being worked in
`Sony/Volume 5/.../18 Wheeler In Idle Stop.flac` -- which is a real
tractor's real shifter, in the cab, against that tractor's own idle. One
genuine event beats three unrelated recordings glued together, and it comes
with the correct room and the correct engine already behind it.

DETECTION. A shift clunk is a short broadband mechanical transient sitting on
a steady idle bed. So: high-pass away the idle fundamental and its low
harmonics, take an energy envelope, and look for sharp rises against the local
median. Using the local median rather than a global threshold matters because
the idle level drifts through the take, and a fixed threshold either misses
quiet shifts or fires constantly on the loud stretch.

Each hit is exported with pre-roll and a tail, so the natural decay is intact
and the cut can be tightened by ear afterwards. Nothing here is a final asset
-- these are candidates to audition against the shipped `vehicle/gear_shift.ogg`.

Usage: uv run --with numpy --with soundfile python sound-test/shifter_extract.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pulse_synth
import soundfile as sf
from pulse_synth import SR, write_wav

pulse_synth.OUT = Path(r"C:\temp\fftest")
SRC = Path("//romeyserv/share/sounds/high quality/Sony/Volume 5/Vehicles/Cars & Trucks/18 Wheeler In Idle Stop.flac")

PRE_ROLL_S = 0.06   # a little air before the strike
TAIL_S = 0.55       # enough for the clunk to ring out
MIN_GAP_S = 0.25    # two hits closer than this are one event


def load(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Return (mono at SR, stereo at SR). Stereo is kept for the actual cut."""
    data, sr = sf.read(str(path), always_2d=True)
    if sr != SR:
        idx = np.linspace(0, len(data) - 1, int(len(data) * SR / sr))
        data = np.stack([np.interp(idx, np.arange(len(data)), data[:, c])
                         for c in range(data.shape[1])], axis=1)
    return data.mean(axis=1), data


def transient_envelope(x: np.ndarray, hp_hz: float = 700.0) -> np.ndarray:
    """Energy of the high band only, smoothed.

    High-passing is what separates a mechanical strike from the engine. The
    idle fundamental and its first harmonics live below ~400 Hz and are LOUD;
    leaving them in means the envelope tracks the engine and every detection
    is just a combustion pulse.
    """
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    spec[f < hp_hz] = 0
    hp = np.fft.irfft(spec, len(x))
    env = np.abs(hp)
    w = max(4, int(0.005 * SR))
    return np.convolve(env, np.ones(w) / w, mode="same")


def find_hits(env: np.ndarray, thresh: float = 3.2, med_s: float = 1.5) -> list[int]:
    """Peaks that rise well above the LOCAL median level.

    Local, not global: the idle level drifts across the take, so a single
    threshold either misses the quiet shifts or fires nonstop on the loud
    stretch.
    """
    w = int(med_s * SR)
    # Coarse running median -- exact is needlessly slow over a few million
    # samples and this only sets a floor.
    step = w // 4
    centres = np.arange(0, len(env), step)
    def med_at(c: int) -> float:
        seg = env[max(0, c - w // 2):c + w // 2]
        return float(np.median(seg)) if seg.size else 0.0

    meds = np.array([med_at(c) for c in centres])
    floor = np.interp(np.arange(len(env)), centres, meds)
    floor = np.maximum(floor, 1e-9)
    ratio = env / floor

    hits = []
    gap = int(MIN_GAP_S * SR)
    i = 0
    while i < len(ratio):
        if ratio[i] > thresh:
            j = min(len(ratio), i + gap)
            peak = i + int(np.argmax(env[i:j]))
            hits.append(peak)
            i = peak + gap
        else:
            i += 1
    return hits


def main() -> None:
    if not SRC.exists():
        print(f"Source not reachable: {SRC}")
        return
    mono, stereo = load(SRC)
    dur = len(mono) / SR
    print(f"source: {SRC.name}")
    print(f"  {dur:.1f}s, {stereo.shape[1]}ch\n")

    env = transient_envelope(mono)
    hits = find_hits(env)
    print(f"found {len(hits)} transient candidates\n")
    print(f"  {'#':>3s} {'at':>8s} {'peak/floor':>11s} {'HF ratio':>9s}   guess")

    kept = []
    for n, h in enumerate(hits, 1):
        a = max(0, h - int(PRE_ROLL_S * SR))
        b = min(len(mono), h + int(TAIL_S * SR))
        seg = mono[a:b]
        if not len(seg):
            continue
        # How much of the event is high band. A shifter is metal on metal and
        # sits high; an air release is high but sustained; a door or a body
        # thump is low. Combined with duration this separates them.
        S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        f = np.fft.rfftfreq(len(seg), 1.0 / SR)
        hf = float(S[f > 1200].sum() / (S.sum() or 1.0))
        # Decay time: mechanical clunks die fast, air hisses do not.
        e = np.abs(seg)
        e = np.convolve(e, np.ones(int(0.004 * SR)) / int(0.004 * SR), mode="same")
        pk = int(np.argmax(e))
        after = e[pk:]
        decay_i = np.argmax(after < e[pk] * 0.25) if (after < e[pk] * 0.25).any() else len(after)
        decay_s = decay_i / SR

        if hf > 0.45 and decay_s < 0.18:
            guess = "CLUNK -- mechanical, fast decay"
        elif hf > 0.45:
            guess = "air / hiss -- sustained"
        elif decay_s < 0.12:
            guess = "low thump -- body or door"
        else:
            guess = "engine or ambience"

        ratio = env[h] / max(np.median(env), 1e-9)
        print(f"  {n:3d} {h / SR:7.2f}s {ratio:11.1f} {hf:9.2f}   {guess}")
        kept.append((n, h, a, b, guess))

    print("\nwriting candidates (stereo, natural decay intact):")
    for n, h, a, b, guess in kept:
        tag = "clunk" if guess.startswith("CLUNK") else "other"
        write_wav(f"shift_{tag}_{n:02d}_{h / SR:06.2f}s.wav", stereo[a:b].mean(axis=1))

    print("\nreference: the shipped cue, for A/B")
    ship = Path(__file__).resolve().parents[1] / "src/freight_fate/assets/sounds/vehicle/gear_shift.ogg"
    try:
        d, sr = sf.read(str(ship), always_2d=True)
        m = d.mean(axis=1)
        print(f"  vehicle/gear_shift.ogg  {len(m) / sr:.2f}s (Darren Duff)")
    except Exception:
        pass

    print(f"\nwrote to {pulse_synth.OUT}")


if __name__ == "__main__":
    main()
