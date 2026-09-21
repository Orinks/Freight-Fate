"""Scan the sound library for a real in-cab diesel to lift FORMANTS from.

Read-only over the NAS library. Writes nothing but a report and short excerpt
WAVs to C:\\temp\\fftest for auditioning.

WHAT THIS IS FOR. Not to find a bed to play back -- to find a recording whose
BLOCK, CAB AND PANEL RESONANCES can become the filter that the synthesized
pulse train runs through. Norm's Pianoteq framing, which is exactly right:
Modartt measured real instruments to get a basis, then exposed the numbers so
you can twiddle them. Same here. The recording supplies the formants; the
synth supplies the timing; the numbers stay tunable.

That makes the selection criteria DIFFERENT from picking a playable loop:

  - Engine-forward, not road-forward. Wind and tire roar are broadband and
    would smear the formant estimate toward noise.
  - Steady. A window with an RPM ramp in it has moving harmonics, and the
    envelope estimator would average them into mush.
  - Low, not hissy. In-cab diesel character lives under ~1 kHz; a hissy take
    means the mic was outside or the transfer path is wrong.
  - A CLEAR firing frequency. If we cannot find the fundamental we cannot
    tell the source from the filter, which is the whole exercise.

Usage: uv run --with numpy --with soundfile python sound-test/engine_donor_scan.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pulse_synth
import soundfile as sf
from pulse_synth import SR, write_wav

pulse_synth.OUT = Path(r"C:\temp\fftest")
NAS = Path("//romeyserv/share/sounds/high quality")

# Candidates from the manifest sweep. Trains and farm tractors are included
# deliberately as controls -- a locomotive is the wrong object but a very
# strong diesel formant set, so if one of those wins on the numbers it tells
# us the metric is measuring "diesel" rather than "truck".
CANDIDATES = [
    ("BBC lorry 10-ton",
     "BBC Sound Effects Library/05 - Transport/01-Diesel Lorry - 10 Ton Interior Startup, Constant Run, Stop.flac"),
    ("SI2000 T27 driving",
     "sound_ideas/2000 Series/Sound Ideas 2000 Series - 2021 - Track27 - Diesel Truck, Driving Along, Interior.mp3"),
    ("SI2000 T26 start/drive",
     "sound_ideas/2000 Series/Sound Ideas 2000 Series - 2021 - Track26 - Diesel Truck, Start, Drive, Stop, Interior.mp3"),
    ("6025 mil fast smooth",
     "sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6025 Military/74 Truck,Military Weapons Carrier_Int_Drive Fast On Smooth Terrain.flac"),
    ("6025 mil slow smooth",
     "sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6025 Military/73 Truck,Military Weapons Carrier_Int_Drive Slow On Smooth Terrain.flac"),
    ("6025 mil onboard fast",
     "sound_ideas/The_General_Series_6000_-_Sound_Effects_Library/6025 Military/81 Truck,Military Weapons Carrier_Onboard_Drive Fast,Smooth Terrain.flac"),
    ("HE interior driving",
     "hollywood edge/ambience crowds and battle sounds/21_-_Interior_Of_Truck_While_Driving.mp3"),
    ("PTA interior driving",
     "planes, trains, and automobiles/Interior of truck while driving.mp3"),
    ("Digiffects lorry idle",
     "sound_ideas/Digiffects/D15 Transport/57 - Bus - transport lorry - big - on - idle - interior - off  - car.flac"),
    ("Sony 18wheeler idle",
     "Sony/Volume 5/Vehicles/Cars & Trucks/18 Wheeler In Idle Stop.flac"),
    ("KMP truck cabin",
     "KMP Film Video Sound Effects/06/32 - Inside hefftruck cabine.flac"),
    ("20thFox army int drive",
     "sound_ideas/Twentieth Century Fox Sound Effects Library/10/41 - TRUCK, MILITARY          ARMY TRUCK INTERIOR_  START,  DRIVE,  STOP,  SHUT OFF.flac"),
    ("BBC railcar cab (ctrl)",
     "BBC Sound Effects Library/041 - Trains/33-Diesel Trains-railcar drivers cab start into constant run.flac"),
]

WIN_S = 2.0  # analysis window
HOP_S = 1.0


def load(path: Path, limit_s: float = 120.0) -> np.ndarray | None:
    try:
        data, sr = sf.read(str(path), always_2d=True, frames=int(limit_s * 48000))
    except Exception:
        return None
    mono = data.mean(axis=1)
    if sr != SR:
        idx = np.linspace(0, len(mono) - 1, int(len(mono) * SR / sr))
        mono = np.interp(idx, np.arange(len(mono)), mono)
    return mono if len(mono) > int(4 * SR) else None


def firing_freq(x: np.ndarray, lo: float = 18.0, hi: float = 160.0) -> tuple[float, float]:
    """Autocorrelation fundamental of the low band, with its peak strength.

    Restricted to the low band because the firing frequency is the thing we
    need to separate source from filter; harmonics above 400 Hz only confuse
    the search.
    """
    F = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    F[f > 400] = 0
    lp = np.fft.irfft(F)
    if lp.std() == 0:
        return 0.0, 0.0
    # FFT autocorrelation, not np.correlate. np.correlate('full') is O(n^2),
    # which on a 96k-sample window is ~9 billion operations PER WINDOW -- it
    # ran for minutes per file before I caught it. Wiener-Khinchin does the
    # same job in O(n log n).
    m = 1 << int(np.ceil(np.log2(len(lp) * 2)))
    spec = np.fft.rfft(lp, m)
    ac = np.fft.irfft(spec * np.conj(spec), m)[:len(lp)]
    ac = ac / (ac[0] or 1.0)
    a, b = int(SR / hi), min(int(SR / lo), len(ac) - 1)
    if b <= a:
        return 0.0, 0.0
    k = a + int(np.argmax(ac[a:b]))
    return SR / k, float(ac[k])


def bands(x: np.ndarray) -> tuple[float, ...]:
    S = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    tot = S.sum() or 1.0
    return tuple(S[(f >= a) & (f < b)].sum() / tot
                 for a, b in ((0, 200), (200, 1000), (1000, 4000), (4000, SR / 2)))


def flux(x: np.ndarray, n: int = 8) -> float:
    """Mean spectral change between consecutive sub-blocks. Lower = steadier."""
    w = len(x) // n
    mags = [np.abs(np.fft.rfft(x[i * w:(i + 1) * w] * np.hanning(w))) for i in range(n)]
    mags = [m / (m.sum() or 1.0) for m in mags]
    return float(np.mean([np.abs(mags[i + 1] - mags[i]).sum() for i in range(n - 1)]))


def score_window(x: np.ndarray) -> tuple[float, dict]:
    """Rank a window as a FORMANT DONOR, not as a playable bed."""
    f0, strength = firing_freq(x)
    b = bands(x)
    fl = flux(x)
    m = {"f0": f0, "periodicity": strength, "bands": b, "flux": fl,
         "rms": float(np.sqrt(np.mean(x ** 2)))}
    if f0 <= 0 or strength < 0.15:
        return -1.0, m
    # Engine present and clearly pitched; steady; low-dominated; not hissy.
    s = (2.2 * strength
         + 1.4 * (b[0] + b[1])
         - 1.6 * b[3]
         - 2.0 * min(fl, 1.0))
    # LOOP PENALTY, added after this scorer ranked a looped asset first.
    # "Very periodic and very steady" describes an ideal formant donor AND a
    # tiled loop equally well, so the original score walked straight into the
    # artifact it was supposed to avoid: the top two candidates measured
    # r = 0.981 cycle-to-cycle (a loop; a real recording sits near 0.67), and
    # LPC on them locked a needle-thin pole onto an engine harmonic. Penalise
    # anything that repeats itself too perfectly to be a real take.
    rep = cycle_repetition(x)
    if rep > 0.90:
        s -= 4.0 * (rep - 0.90) / 0.10
    m["repetition"] = rep
    return float(s), m


def cycle_repetition(x: np.ndarray, lo: float = 15.0, hi: float = 140.0) -> float:
    """Best-case correlation between successive periods. ~0.67 real, ~0.99 loop."""
    best = -1.0
    for p in range(int(SR / hi), int(SR / lo), 12):
        n = min((len(x) // p) - 1, 24)
        if n < 6:
            continue
        cs = [np.corrcoef(x[i * p:(i + 1) * p], x[(i + 1) * p:(i + 2) * p])[0, 1]
              for i in range(n)
              if x[i * p:(i + 1) * p].std() > 0 and x[(i + 1) * p:(i + 2) * p].std() > 0]
        if cs:
            best = max(best, float(np.mean(cs)))
    return best


def main() -> None:
    print(f"{'candidate':24s} {'best':>6s} {'f0':>7s} {'per':>5s} "
          f"{'<200':>5s} {'2-1k':>5s} {'1-4k':>5s} {'>4k':>5s} {'flux':>5s}  at")
    print("-" * 92)
    results = []
    for label, rel in CANDIDATES:
        x = load(NAS / rel)
        if x is None:
            print(f"{label:24s}  unreadable / too short")
            continue
        best = (-9.0, None, 0.0)
        for start in range(0, int(len(x) - WIN_S * SR), int(HOP_S * SR)):
            w = x[start:start + int(WIN_S * SR)]
            if np.sqrt(np.mean(w ** 2)) < 0.005:
                continue
            s, m = score_window(w)
            if s > best[0]:
                best = (s, m, start / SR)
        s, m, at = best
        if m is None:
            print(f"{label:24s}  no usable window")
            continue
        b = m["bands"]
        print(f"{label:24s} {s:6.2f} {m['f0']:7.1f} {m['periodicity']:5.2f} "
              f"{b[0]:5.2f} {b[1]:5.2f} {b[2]:5.2f} {b[3]:5.2f} {m['flux']:5.2f}  {at:6.1f}s")
        results.append((s, label, rel, at, m))

    results.sort(reverse=True, key=lambda r: r[0])
    print("\nTop donors -- excerpts written for audition:")
    for s, label, rel, at, m in results[:5]:
        x = load(NAS / rel)
        if x is None:
            continue
        seg = x[int(at * SR):int((at + 4.0) * SR)]
        safe = label.lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
        write_wav(f"donor_{safe}.wav", seg)
        print(f"  {label:24s} score {s:5.2f}  f0 {m['f0']:6.1f} Hz "
              f"-> implied {m['f0'] * 20:5.0f} rpm if inline-six")

    print(f"\nwrote to {pulse_synth.OUT}")


if __name__ == "__main__":
    main()
