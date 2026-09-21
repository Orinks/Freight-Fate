"""Clutch/shift clunk cues, cut from the INTERIOR cab takes (Norm 2026-07-21).

The Mac take (896) gave only weak shift transients (3-7x over the bed). The
in-cab S08IN takes are far cleaner -- 854 is a run of ~6 clutch clunks, 855 is
one big isolated clunk (523x), 859 is an interior idle->drive with real shifts.
A clunk recorded in the cab is exactly the right POV for the driver's-seat mix,
so the manual shift bank is rebuilt from these, with 896 kept only for A/B.

Per clunk, two cues (same split as before):
  MANUAL   -> wide window (clutch squeak + clunk + settle), the RR bank.
  AUTOMATIC-> tight window (disengage only, faster), the auto cue.

Every file is tagged with its source take so provenance is obvious in the mix
and Norm's ear can cull by cab, not just by count. Outputs to
C:\\temp\\ffsound\\shifts as shift_manual_<src>_NN / shift_auto_<src>_NN, plus
shift_manual_demo / shift_auto_demo across all of them.

Usage: uv run --with numpy --with soundfile --with scipy python sound-test/shift_clutch.py
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
LV = Path(r"C:\temp\ffsound\splice\Samples\packs\Large Vehicles")
# INTERIOR clutch clunks first; the Mac take is comparison only.
SOURCES = {
    "854": LV / "SemiTruck_S08IN.854.wav",       # ~6 clutch clunks in a row
    "855": LV / "SemiTruck_S08IN.855.wav",       # one big isolated clunk (523x)
    "859": LV / "SemiTruck_S08IN.859.wav",       # interior idle->drive, real shifts
    "896": LV / "SemiTruckMac_S08IN.896.wav",    # Mac take, A/B only
}
PER_SRC = 8                            # cap candidates per source
MANUAL_PRE, MANUAL_LEN = 0.15, 0.80    # clutch squeak + clunk + settle
AUTO_PRE, AUTO_LEN = 0.04, 0.22        # disengage only -- faster, for the auto


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
    w = int(0.005 * C.SR)
    return np.convolve(np.abs(hp(x, fc)), np.ones(w) / w, "same")


def floor_of(env: np.ndarray, dur_s: float) -> np.ndarray:
    """Global median for short clips (mostly clunk); running median for long."""
    if dur_s < 10.0:
        return np.full(len(env), max(float(np.median(env)), 1e-9))
    w = int(2.0 * C.SR); step = w // 4
    centres = np.arange(0, len(env), step)
    meds = np.array([np.median(env[max(0, c - w // 2):c + w // 2]) or 0.0 for c in centres])
    return np.maximum(np.interp(np.arange(len(env)), centres, meds), 1e-9)


def cut(x: np.ndarray, center: int, pre_s: float, len_s: float) -> np.ndarray:
    a = max(0, center - int(pre_s * C.SR))
    seg = x[a:a + int(len_s * C.SR)].copy()
    if len(seg) < 8:
        return seg
    atk = int(0.003 * C.SR)
    seg[:atk] *= np.linspace(0, 1, atk)
    tail = int(len(seg) * 0.30)
    seg[-tail:] *= np.linspace(1, 0, tail) ** 1.4
    return seg


def hf_share(seg: np.ndarray) -> float:
    S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    f = np.fft.rfftfreq(len(seg), 1.0 / C.SR)
    return float(S[f > 1200].sum() / (S.sum() or 1.0))


def decay_ms(seg: np.ndarray) -> float:
    e = np.convolve(np.abs(seg), np.ones(int(0.004 * C.SR)) / int(0.004 * C.SR), "same")
    pk = int(np.argmax(e)); after = e[pk:]
    below = after < e[pk] * 0.25
    return (int(np.argmax(below)) if below.any() else len(after)) / C.SR * 1000.0


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in list(OUT.glob("shift_manual_*.wav")) + list(OUT.glob("shift_auto_*.wav")):
        stale.unlink()

    all_manual: list[np.ndarray] = []
    all_auto: list[np.ndarray] = []
    print(f"  {'src':>4s} {'#':>2s} {'at':>7s} {'ratio':>6s} {'hf':>5s} {'decay':>6s}   guess")
    for src, path in SOURCES.items():
        if not path.exists():
            continue
        x = C.load_wav(path)
        env = transient_env(x)
        ratio = env / floor_of(env, len(x) / C.SR)
        gap = int(0.35 * C.SR)
        picked: list[int] = []
        for k in np.argsort(env)[::-1]:
            k = int(k)
            if ratio[k] < 4.0:
                break
            if all(abs(k - q) > gap for q in picked):
                picked.append(k)
            if len(picked) >= PER_SRC:
                break
        for n, e in enumerate(sorted(picked), 1):
            man = cut(x, e, MANUAL_PRE, MANUAL_LEN)
            aut = cut(x, e, AUTO_PRE, AUTO_LEN)
            hf, dec = hf_share(man), decay_ms(man)
            guess = ("squeak-rich" if hf > 0.35 and dec > 180
                     else "clunk / disengage" if dec < 140 else "shift (mixed)")
            print(f"  {src:>4s} {n:2d} {e / C.SR:6.2f}s {ratio[e]:6.0f} {hf:5.2f} {dec:5.0f}ms   {guess}")
            write(f"shift_manual_{src}_{n:02d}.wav", man)
            write(f"shift_auto_{src}_{n:02d}.wav", aut)
            all_manual.append(man); all_auto.append(aut)

    def demo(bank: list[np.ndarray], gap_s: float) -> np.ndarray:
        if not bank:
            return np.zeros(1)
        g = np.zeros(int(gap_s * C.SR))
        return np.concatenate([np.concatenate([b / (np.abs(b).max() or 1) * 0.7, g])
                               for b in bank])
    write("shift_manual_demo.wav", demo(all_manual, 0.4))
    write("shift_auto_demo.wav", demo(all_auto, 0.3))

    print(f"\n  clutch bank: {len(all_manual)} manual + {len(all_auto)} auto "
          f"(interior-first) + demos")
    print(f"  wrote to {OUT}")


if __name__ == "__main__":
    main()
