"""Cut the gear-shift cues from 896 -- the SAME truck as the engine voice.

Norm 2026-07-21: the 896 take (the interior gem behind the whole engine
rebuild) is a truck driving around and working its gearbox, "complete with a
squeaky clutch". Cutting the shifts from 896 keeps the shift cue in the exact
same cab and engine as [[project-engine-voice-rebuild]] -- one coherent truck,
not a shift glued on from another recording.

Two cues come out of every shift event:
  MANUAL   -> the full character: clutch squeak + gear engagement + settle. A
              round-robin bank so repeated shifts vary (shuffle + jitter at
              play time). This is the squeaky clutch Norm wants for the manual.
  AUTOMATIC-> a TIGHT window on just the disengage transient, no squeak tail.
              "The auto probably shifts faster, so we just use the shorter
              engine-disengage sound." One quick cue.

Shift times are detected (high-pass away the engine bed, peak-pick the HF
transients over a local-median floor) and anchored to Norm's mapped shifts
(~32, 33.5, 37, 57.5 s), all of which sit on real transients. The final stop
(~108 s, a big clunk) is not a shift and is excluded by the region window.
Each candidate is labelled by HF content and decay so the ear can tell a
squeak-rich shift from a bare disengage. Outputs to C:\\temp\\ffsound\\shifts
as shift_manual_NN / shift_auto_NN, plus shift_manual_demo / shift_auto_demo.

Usage: uv run --with numpy --with soundfile --with scipy python sound-test/shift_896.py
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

OUT = Path(r"C:\temp\ffsound\shifts")
SRC = Path(r"C:\temp\ffsound\splice\Samples\packs\Large Vehicles\SemiTruckMac_S08IN.896.wav")
ANCHORS_S = [32.0, 33.5, 37.0, 57.5]   # Norm's mapped shifts (all land on transients)
REGION_S = (15.0, 65.0)                # the shifting stretch; excludes the ~108 s stop
MANUAL_PRE, MANUAL_LEN = 0.22, 1.00    # clutch squeak (before the clunk) + clunk + settle
AUTO_PRE, AUTO_LEN = 0.05, 0.26        # just the disengage -- faster, for the auto
KEEP = 12                              # cap each bank; Norm's ear culls


def hp(x: np.ndarray, fc: float) -> np.ndarray:
    b, a = butter(2, fc / (C.SR / 2), "high")
    return filtfilt(b, a, x)


def write(name: str, x: np.ndarray, target_rms: float = 0.10) -> None:
    x = np.nan_to_num(np.asarray(x, float))
    x = x * (target_rms / (float(np.sqrt(np.mean(x ** 2))) or 1.0))
    p = float(np.max(np.abs(x))) or 1.0
    if p > 0.97:
        x = x * (0.97 / p)
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as fh:
        fh.setnchannels(1); fh.setsampwidth(2); fh.setframerate(C.SR)
        fh.writeframes((x * 32767).astype("<i2").tobytes())


def transient_env(x: np.ndarray, fc: float = 800.0) -> np.ndarray:
    """HF energy over the engine bed: the shifter is metal/rubber above ~800 Hz."""
    env = np.abs(hp(x, fc))
    w = int(0.005 * C.SR)
    return np.convolve(env, np.ones(w) / w, "same")


def local_floor(env: np.ndarray, med_s: float = 2.0) -> np.ndarray:
    """Running median: the engine bed drifts, so a fixed threshold won't do."""
    w = int(med_s * C.SR); step = w // 4
    centres = np.arange(0, len(env), step)
    meds = np.array([np.median(env[max(0, c - w // 2):c + w // 2]) or 0.0 for c in centres])
    return np.maximum(np.interp(np.arange(len(env)), centres, meds), 1e-9)


def snap(env: np.ndarray, t_s: float, win_s: float = 0.6) -> int:
    """Snap an approximate anchor time to the nearest local energy peak."""
    c = int(t_s * C.SR); w = int(win_s * C.SR)
    lo, hi = max(0, c - w), min(len(env), c + w)
    return lo + int(np.argmax(env[lo:hi]))


def cut(x: np.ndarray, center: int, pre_s: float, len_s: float) -> np.ndarray:
    a = max(0, center - int(pre_s * C.SR))
    seg = x[a:a + int(len_s * C.SR)].copy()
    if len(seg) < 8:
        return seg
    atk = int(0.004 * C.SR)
    seg[:atk] *= np.linspace(0, 1, atk)
    tail = int(len(seg) * 0.30)
    seg[-tail:] *= np.linspace(1, 0, tail) ** 1.4
    return seg


def hf_share(seg: np.ndarray) -> float:
    S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    f = np.fft.rfftfreq(len(seg), 1.0 / C.SR)
    return float(S[f > 1200].sum() / (S.sum() or 1.0))


def decay_s(seg: np.ndarray) -> float:
    e = np.convolve(np.abs(seg), np.ones(int(0.004 * C.SR)) / int(0.004 * C.SR), "same")
    pk = int(np.argmax(e)); after = e[pk:]
    below = after < e[pk] * 0.25
    return (int(np.argmax(below)) if below.any() else len(after)) / C.SR


def main() -> None:
    if not SRC.exists():
        print(f"Source not found: {SRC}")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in list(OUT.glob("shift_manual_*.wav")) + list(OUT.glob("shift_auto_*.wav")):
        stale.unlink()

    x = C.load_wav(SRC)
    env = transient_env(x)
    ratio = env / local_floor(env)

    # Detected HF transients in the shifting region, min 0.4 s apart.
    lo, hi = int(REGION_S[0] * C.SR), int(REGION_S[1] * C.SR)
    gap = int(0.4 * C.SR)
    picked: list[int] = []
    for k in np.argsort(env)[::-1]:
        k = int(k)
        if not (lo <= k <= hi) or ratio[k] < 3.0:
            continue
        if all(abs(k - q) > gap for q in picked):
            picked.append(k)
    # Norm's mapped shifts are GUARANTEED in the bank; detected extras fill the
    # rest, strongest first. Extras landing on an anchor are dropped as dupes.
    anchors = sorted({snap(env, t) for t in ANCHORS_S})
    extras = [k for k in picked if all(abs(k - a) > int(0.3 * C.SR) for a in anchors)]
    extras.sort(key=lambda e: ratio[e], reverse=True)
    merged = sorted(anchors + extras[:max(0, KEEP - len(anchors))])

    print(f"  {'#':>2s} {'at':>7s} {'ratio':>6s} {'hf':>5s} {'decay':>6s}   guess")
    manuals: list[np.ndarray] = []
    autos: list[np.ndarray] = []
    for n, e in enumerate(merged, 1):
        man = cut(x, e, MANUAL_PRE, MANUAL_LEN)
        aut = cut(x, e, AUTO_PRE, AUTO_LEN)
        hf, dec = hf_share(man), decay_s(man)
        guess = ("squeak-rich (manual)" if hf > 0.35 and dec > 0.18
                 else "clunk / disengage" if dec < 0.14
                 else "shift (mixed)")
        print(f"  {n:2d} {e / C.SR:6.2f}s {ratio[e]:6.1f} {hf:5.2f} {dec * 1000:5.0f}ms   {guess}")
        manuals.append(man); autos.append(aut)

    for i, m in enumerate(manuals, 1):
        write(f"shift_manual_{i:02d}.wav", m)
    for i, a in enumerate(autos, 1):
        write(f"shift_auto_{i:02d}.wav", a)

    def demo(bank: list[np.ndarray], gap_s: float) -> np.ndarray:
        if not bank:
            return np.zeros(1)
        g = np.zeros(int(gap_s * C.SR))
        return np.concatenate([np.concatenate([b / (np.abs(b).max() or 1) * 0.7, g])
                               for b in bank])
    write("shift_manual_demo.wav", demo(manuals, 0.4))
    write("shift_auto_demo.wav", demo(autos, 0.3))

    print(f"\n  manual bank: {len(manuals)}   auto bank: {len(autos)}   "
          f"+ shift_manual_demo / shift_auto_demo")
    print(f"  wrote to {OUT}")


if __name__ == "__main__":
    main()
