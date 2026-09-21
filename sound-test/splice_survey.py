"""Survey the downloaded Splice truck recordings: what they are, where the usable bits are.

Read-only. Writes a report plus short excerpt WAVs to C:\\temp\\fftest.

Answers the questions that decide how each file gets used:

  1. INTERIOR OR EXTERIOR? Decided on spectral balance, not on the filename.
     An in-cab recording is low-dominated because the firewall and glass
     roll off the top; an exterior take keeps its high end. This matters
     more than anything else -- the game's whole POV is the driver's seat.
  2. REAL OR LOOPED? Cycle-to-cycle correlation, swept over f0. A real take
     sits near 0.67; a tiled loop approaches 1.0. This is the check that
     caught the Hollywood Edge donor, and it has to run on everything now.
  3. WHERE IS THE ENGINE, IN RPM, OVER TIME? A track of firing frequency
     across the file locates the startup ramp, the shifts, the cruise
     sections and the coast-downs without anyone scrubbing a timeline.
  4. WHERE ARE THE QUIET-ENGINE WINDOWS? Moments where road speed stays up
     while the engine unloads -- between shifts, or coasting. Those are the
     wind-and-tire bed, harvested from the right cab.

Usage: uv run --with numpy --with soundfile python sound-test/splice_survey.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pulse_synth
import soundfile as sf
from pulse_synth import SR, write_wav

pulse_synth.OUT = Path(r"C:\temp\fftest")
SRC = Path(r"C:\temp\fftest\splice")

WIN_S = 0.35
HOP_S = 0.10


def load(path: Path) -> np.ndarray:
    """Mono at SR. These are 96 kHz/24-bit, so decimate rather than interpolate."""
    data, sr = sf.read(str(path), always_2d=True)
    mono = data.mean(axis=1)
    if sr != SR:
        idx = np.linspace(0, len(mono) - 1, int(len(mono) * SR / sr))
        mono = np.interp(idx, np.arange(len(mono)), mono)
    return mono


def bands(x: np.ndarray) -> tuple[float, ...]:
    S = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    tot = S.sum() or 1.0
    return tuple(S[(f >= a) & (f < b)].sum() / tot
                 for a, b in ((0, 200), (200, 1000), (1000, 4000), (4000, SR / 2)))


# A Mack E7 idles near 600 and redlines around 2100. Constraining the
# search to a plausible band is half the fix for octave errors.
RPM_MIN, RPM_MAX = 500.0, 2200.0


def firing_track(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Firing frequency and its confidence, sampled across the file.

    HARMONIC SUM, not raw autocorrelation. Plain autocorrelation on an engine
    is badly octave-prone -- a strong second harmonic looks exactly like a
    fundamental an octave up, and the first version of this reported a diesel
    revving to 3400 rpm, which does not happen. Scoring each candidate f0 by
    the energy at f0, 2f0, 3f0 ... instead means a true fundamental beats its
    own harmonic, because only the true one lines every partial up.

    The search is also clamped to 500-2200 rpm. Anything outside that is not
    this engine, so allowing it only invites errors.

    Returns (times, hz, strength). Strength is the harmonic sum normalised by
    total band energy; below ~0.25 there is no clear engine -- silence, wind,
    or a non-engine event.
    """
    w, hop = int(WIN_S * SR), int(HOP_S * SR)
    times, hz, strength = [], [], []
    cand = np.arange(RPM_MIN, RPM_MAX, 5.0) / 20.0  # firing freq = rpm/20
    for i in range(0, len(x) - w, hop):
        seg = x[i:i + w] * np.hanning(w)
        if np.sqrt(np.mean(seg ** 2)) < 1e-4:
            times.append(i / SR); hz.append(0.0); strength.append(0.0)
            continue
        S = np.abs(np.fft.rfft(seg))
        f = np.fft.rfftfreq(w, 1.0 / SR)
        keep = f < 1200.0
        S, f = S[keep], f[keep]
        scores = np.zeros(len(cand))
        for ci, f0 in enumerate(cand):
            # Sum energy in a narrow bin around each of the first 8 partials.
            acc = 0.0
            for k in range(1, 9):
                fk = f0 * k
                if fk >= f[-1]:
                    break
                lo_i, hi_i = np.searchsorted(f, (fk * 0.97, fk * 1.03))
                if hi_i > lo_i:
                    acc += S[lo_i:hi_i].max()
            scores[ci] = acc
        # Normalise against the MEDIAN candidate, not against total band
        # energy. Dividing by the total compares 8 peak values to thousands of
        # bins, which collapses every score to ~0.05 and makes any absolute
        # threshold meaningless -- my second attempt did exactly that. What
        # actually matters is how far the best candidate stands out from a
        # typical one, which is scale-free and thresholds cleanly around 1.5.
        med = float(np.median(scores)) or 1.0
        bi = int(np.argmax(scores))
        times.append(i / SR); hz.append(float(cand[bi]))
        strength.append(float(scores[bi] / med))
    return np.array(times), np.array(hz), np.array(strength)


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


def describe(name: str, x: np.ndarray) -> None:
    b = bands(x)
    dur = len(x) / SR
    # Interior takes are low-dominated; exterior keeps its top end. Duff's
    # in-cab idle measures >4k = 0.07, the shipped synthetic loops 0.52-0.59.
    verdict = "INTERIOR (low-dominated)" if b[3] < 0.15 else \
              "exterior or bright" if b[3] > 0.25 else "borderline"
    print(f"\n=== {name} ===")
    print(f"  {dur:.1f}s   <200 {b[0]:.2f}  200-1k {b[1]:.2f}  "
          f"1k-4k {b[2]:.2f}  >4k {b[3]:.2f}   -> {verdict}")
    rep = cycle_repetition(x[int(len(x) * 0.4):int(len(x) * 0.4) + int(3 * SR)])
    print(f"  cycle repetition r={rep:+.3f}  "
          f"({'REAL take' if rep < 0.90 else 'LOOPED -- do not use as a donor'})")

    t, hz, s = firing_track(x)
    ok = s > 1.6
    if ok.any():
        rpm = hz[ok] * 20.0
        print(f"  engine present {100 * ok.mean():4.1f}% of the file   "
              f"rpm range {rpm.min():.0f}-{rpm.max():.0f}  (median {np.median(rpm):.0f})")

    # Coarse timeline: report where the engine speed changes materially.
    print("  timeline (firing freq -> rpm, 'quiet' = no clear engine):")
    step = max(1, len(t) // 22)
    for i in range(0, len(t), step):
        tag = f"{hz[i] * 20:6.0f} rpm" if s[i] > 1.6 else "     quiet"
        print(f"    {t[i]:6.1f}s  {tag}   conf {s[i]:.2f}")

    # Windows where the engine is weak but the file is not silent: candidate
    # wind-and-tire bed material.
    rms = np.array([np.sqrt(np.mean(x[int(a * SR):int(a * SR) + int(WIN_S * SR)] ** 2))
                    for a in t])
    loud = rms > np.median(rms) * 0.55
    quiet_engine = loud & (s < 1.35)
    if quiet_engine.any():
        runs, start = [], None
        for i, v in enumerate(quiet_engine):
            if v and start is None:
                start = i
            elif not v and start is not None:
                if t[i - 1] - t[start] >= 0.3:
                    runs.append((t[start], t[i - 1]))
                start = None
        if runs:
            print("  ROAD-BED CANDIDATES (loud, but no clear engine):")
            for a, b_ in runs[:8]:
                print(f"    {a:6.1f}s - {b_:6.1f}s   ({b_ - a:.2f}s)")


def main() -> None:
    files = sorted(SRC.glob("*.wav"))
    if not files:
        print(f"Nothing in {SRC}")
        return
    for path in files:
        x = load(path)
        describe(path.name, x)
    print(f"\n(excerpts can be cut once you say which windows you want)")


if __name__ == "__main__":
    main()
