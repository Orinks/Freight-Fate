"""Sort the licensed brake material into the two round-robin banks + an e-brake.

Locked spec (Norm 2026-07-21):
  PRESS   -> clunk bank, shuffle RR, level by press force
  RELEASE -> hiss bank,  shuffle RR, length + level by how hard you braked
  E-BRAKE -> one big sustained air event (the full Bantam)
  All quiet under the engine; +-pitch/level jitter per trigger at play time.

The library is thin on real clunks: five of the six semi-truck brake samples
are AIR RELEASES (hiss), so the mechanical thunk of applying the brake mostly
has to come from the Bantam valve machine -- 61 s of a valve PRESSED and
released over and over, each press a thunk. So we extract a short PERCUSSIVE
ONSET (the thunk, before the air) from every source and every Bantam actuation,
then rank candidates by "bodyness" (low-mid thunk energy over airy high end).
The thunks float to the top of the clunk bank; the airy ones become hiss ticks.
Norm's ear culls the ranked banks -- these numbers only order the candidates.

Clunk hits keep body (high-pass at 110 Hz, not 200) so the thunk survives; the
low rumble/hum Norm flagged is still gone. Hiss releases stay high-passed at
200. Outputs to C:\\temp\\ffsound\\brakes as brake_clunk_NN / brake_hiss_NN /
ebrake_full, plus brake_clunk_demo / brake_hiss_demo to audition each bank.

Usage: uv run --with numpy --with soundfile --with scipy python sound-test/brake_banks.py
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

OUT = Path(r"C:\temp\ffsound\brakes")
LV = Path(r"C:\temp\ffsound\splice\Samples\packs\Large Vehicles")
IND = Path(r"C:\temp\ffsound\splice\Samples\packs\Industry Vol. 1")
BANTAM = IND / "BantamBrakeMach_S08IN.62.wav"
# Every truck/air brake one-shot in the library. Each gets tried BOTH ways:
# its onset for a clunk, its tail for a hiss -- bodyness decides which bank.
SOURCES = [
    LV / "SemiTruckBrake_S08IN.913.wav",
    LV / "SemiTruckBrake_S08IN.914.wav",
    LV / "SemiTruckBrake_S08IN.915.wav",
    LV / "SemiTruckBrake_S08IN.916.wav",
    LV / "SemiTruckBrake_S08IN.917.wav",
    LV / "SemiTruckAirBrake_BWU.95.wav",
    IND / "AirBrake_BW.20321.wav",
]
CLUNK_BODY_MIN = 1.5   # below this a "hit" is really an airy tick, not a thunk
CLUNK_KEEP = 14        # cap the clunk bank; Norm's ear culls the survivors
HISS_KEEP = 20         # cap the hiss bank the same way


def hp(x: np.ndarray, fc: float = 200.0) -> np.ndarray:
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


def band_energy(x: np.ndarray, lo: float, hi: float) -> float:
    S = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1.0 / C.SR)
    return float(S[(f >= lo) & (f < hi)].sum())


def bodyness(x: np.ndarray) -> float:
    """Thunk-vs-hiss: low-mid mechanical body over airy high end. High = clunk."""
    return band_energy(x, 90.0, 600.0) / (band_energy(x, 2500.0, 9000.0) + 1e-9)


def onset(x: np.ndarray, hpfc: float = 110.0) -> int:
    a = int(np.argmax(np.abs(hp(x, hpfc))))
    return max(0, a - int(0.006 * C.SR))


def clunk_hit(seg: np.ndarray, win_s: float = 0.09) -> np.ndarray:
    """Short percussive thunk: onset window, gentle HP to keep body, hit envelope."""
    seg = hp(seg[:int(win_s * C.SR)].copy(), 110.0)
    if len(seg) < 8:
        return seg
    atk = int(0.002 * C.SR)
    seg[:atk] *= np.linspace(0, 1, atk)
    seg *= np.linspace(1, 0, len(seg)) ** 1.8   # decays to a hit, not a tone
    return seg


def chuff(seg: np.ndarray, max_s: float = 0.55) -> np.ndarray:
    """Longer airy release: HP 200 to drop hum, eased tail so no endless sssh."""
    seg = hp(seg[:int(max_s * C.SR)].copy())
    if len(seg) < 8:
        return seg
    atk = int(0.008 * C.SR)
    seg[:atk] *= np.linspace(0, 1, atk)
    tail = int(len(seg) * 0.45)
    seg[-tail:] *= np.linspace(1, 0, tail) ** 1.5
    return seg


def bantam_events(x: np.ndarray, max_events: int = 24) -> list[int]:
    """Onset positions of each valve actuation in the Bantam machine loop."""
    xh = hp(x, 110.0)
    win = int(0.005 * C.SR)
    env = np.convolve(np.abs(xh), np.ones(win) / win, "same")
    thr = np.percentile(env, 88) * 0.6
    gap = int(0.30 * C.SR)
    out: list[int] = []
    i = 0
    while i < len(env) - int(0.55 * C.SR) and len(out) < max_events:
        if env[i] > thr and env[i] >= env[max(0, i - win):i + win].max() - 1e-9:
            out.append(max(0, i - int(0.006 * C.SR))); i += gap
        else:
            i += 1
    return out


def bantam_press_positions(x: np.ndarray, hop_s: float = 0.02, win_s: float = 0.09,
                           min_gap_s: float = 0.18) -> list[int]:
    """Find the PRESS moments: windows whose thunk is body-heavy, not the loud
    airy releases the amplitude detector catches. Greedy-pick the highest-body
    windows that are also audible, spaced so we don't re-cut one press twice."""
    win = int(win_s * C.SR); hop = int(hop_s * C.SR)
    pos = np.arange(0, max(1, len(x) - win), hop)
    bod = np.array([bodyness(clunk_hit(x[p:p + win])) for p in pos])
    amp = np.array([float(np.sqrt(np.mean(hp(x[p:p + win], 110.0) ** 2))) for p in pos])
    ok = (bod > CLUNK_BODY_MIN) & (amp > 2e-3)
    order = np.argsort(bod)[::-1]
    picked: list[int] = []
    for k in order:
        if not ok[k]:
            continue
        p = int(pos[k])
        if all(abs(p - q) > int(min_gap_s * C.SR) for q in picked):
            picked.append(p)
    return sorted(picked)


def loud_enough(x: np.ndarray) -> bool:
    return float(np.sqrt(np.mean(x ** 2))) > 1e-3


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in list(OUT.glob("brake_clunk_*.wav")) + list(OUT.glob("brake_hiss_*.wav")):
        stale.unlink()   # banks are rebuilt whole; drop old numbering first

    clunk_cands: list[tuple[float, np.ndarray]] = []
    hiss_cands: list[tuple[float, np.ndarray]] = []

    # Onset positions: one per truck one-shot, many across the Bantam.
    hits: list[tuple[np.ndarray, int]] = []
    for p in SOURCES:
        if p.exists():
            x = C.load_wav(p)
            hits.append((x, onset(x)))
    if BANTAM.exists():
        xb = C.load_wav(BANTAM)
        # Amplitude onsets feed the HISS bank (the loud releases); a separate
        # body-heavy scan feeds the CLUNK bank (the quieter presses).
        for a in bantam_events(xb):
            hits.append((xb, a))
        for a in bantam_press_positions(xb):
            hit = clunk_hit(xb[a:])
            if loud_enough(hit):
                clunk_cands.append((bodyness(hit), hit))

    # Each onset yields a thunk candidate (short hit) and a hiss candidate
    # (longer tail). bodyness ranks each into its bank; the same physical event
    # is only strong in one, so the ranking self-sorts press vs release.
    for x, a in hits:
        hit = clunk_hit(x[a:])
        if loud_enough(hit):
            clunk_cands.append((bodyness(hit), hit))
        tail = chuff(x[a:])
        if loud_enough(tail):
            hiss_cands.append((bodyness(tail), tail))

    clunk_cands.sort(key=lambda t: t[0], reverse=True)   # thunkiest first
    hiss_cands.sort(key=lambda t: t[0])                  # airiest first
    # Only keep genuine thunks -- an honest small bank beats one padded with
    # airy ticks. Norm's ear culls what survives the bodyness gate.
    clunks = [c for b, c in clunk_cands if b >= CLUNK_BODY_MIN][:CLUNK_KEEP]
    hisses = [h for _, h in hiss_cands[:HISS_KEEP]]

    for i, c in enumerate(clunks, 1):
        write(f"brake_clunk_{i:02d}.wav", c)
    for i, h in enumerate(hisses, 1):
        write(f"brake_hiss_{i:02d}.wav", h)

    # Demos: each bank laid out spaced, so the ear can cull in one listen.
    def demo(bank: list[np.ndarray], gap_s: float) -> np.ndarray:
        if not bank:
            return np.zeros(1)
        gap = np.zeros(int(gap_s * C.SR))
        return np.concatenate([np.concatenate([b / (np.abs(b).max() or 1) * 0.7, gap])
                               for b in bank])
    write("brake_clunk_demo.wav", demo(clunks, 0.35))
    write("brake_hiss_demo.wav", demo(hisses, 0.4))

    # e-brake: one big sustained air event -- 2.5 s of the Bantam machine running
    if BANTAM.exists():
        x = C.load_wav(BANTAM)
        mid = len(x) // 2
        eb = hp(x[mid:mid + int(2.5 * C.SR)]).copy()
        atk = int(0.02 * C.SR); eb[:atk] *= np.linspace(0, 1, atk)
        eb[-int(0.2 * C.SR):] *= np.linspace(1, 0, int(0.2 * C.SR))
        write("ebrake_full.wav", eb)

    survivors = [b for b, _ in clunk_cands if b >= CLUNK_BODY_MIN][:CLUNK_KEEP]
    print(f"  clunk bank: {len(clunks)} genuine thunks (bodyness >= {CLUNK_BODY_MIN})   "
          f"hiss bank: {len(hisses)}   + ebrake_full.wav")
    print("  clunk bodyness (thunkiest first): "
          + ", ".join(f"{b:.1f}" for b in survivors))
    print(f"  wrote banks + brake_clunk_demo / brake_hiss_demo to {OUT}")


if __name__ == "__main__":
    main()
