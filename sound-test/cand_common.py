"""Shared harness for the phase-2 engine-voice candidates (ultracode menu).

Every candidate method imports this so scoring, I/O and the source material are
identical across the fan-out -- only the SYNTHESIS METHOD differs. The ear picks
the winner; these numbers only prove a candidate isn't obviously broken (thin,
boxy, seamed, or micro-engine) before it reaches the ear.

The target the whole menu is chasing: a diesel idle as FULL as the real
recording that also tiles SEAMLESSLY, plus a rev up through ~1800 rpm that stays
the SAME SIZE of engine (formants fixed -- pitch moves, the 800 Hz body does
not). "Boxy" and "does not represent the full idle" are the two failures to beat.

Reference / source material (real, interiorized Splice/Blastwave semi):
  REF_IDLE       647 rpm, the spectral TARGET (but itself a bad loop -- 17x seam)
  SRC_IDLE_LONG  ~12 s continuous real idle, the raw stock to cut/stretch/analyse
Outputs go to C:\\temp\\ffsound\\candidates.

Usage from a candidate script (run from repo root):
  uv run --with numpy --with soundfile --with scipy python sound-test/cand_<name>.py
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48000

REF_DIR = Path(r"C:\temp\ffsound\reference")
CAND_DIR = Path(r"C:\temp\ffsound\candidates")
REF_IDLE = REF_DIR / "idle_647_REAL_interiorized.wav"
SRC_IDLE_LONG = Path(r"C:\temp\fftest\IDLE904") / "48 cycles 11.93s.wav"

# LICENSED real source (Splice / Blastwave etc.) -- the stock candidates may USE.
# Three long INTERIOR takes cover idle->redline from the driver's seat; two long
# steady EXTERIOR takes give clean high-rpm loops via interiorize(). rpm ranges
# are measured, not from filenames.
_LV = Path(r"C:\temp\ffsound\splice\Samples\packs\Large Vehicles")
LICENSED = {
    # INTERIOR cab -- the driver's seat POV, the primary stock. Together these
    # cover idle -> redline from inside the cab.
    "int_idle_low": _LV / "SemiTruck_S08IN.859.wav",       # 104s INT, 645-1275 rpm
    "int_mid":      _LV / "SemiTruckMac_S08IN.909.wav",    # 70s  INT, 630-1470 rpm
    "int_high":     _LV / "SemiTruckEngine_BW.60624.wav",  # 176s INT, 1440-2175 rpm
    # EXTERIOR Mac takes -- richer rev/range material; interiorize() to bring
    # them into the cab. Long steady ones make the cleanest high-rpm loops.
    "ext_hi_a":     _LV / "SemiTruckMac_S08IN.904.wav",    # 76s  EXT, ~1900 steady
    "ext_hi_b":     _LV / "SemiTruckMac_S08IN.905.wav",    # 80s  EXT, ~1900 steady
    "ext_range_a":  _LV / "SemiTruckMac_S08IN.896.wav",    # 124s EXT, 525-1350 wide
    "ext_range_b":  _LV / "SemiTruckMac_S08IN.907.wav",    # 84s  EXT, 715-2105 wide
    "ext_range_c":  _LV / "SemiTruckMac_S08IN.908.wav",    # 49s  EXT, 505-1895 wide
    "ext_rev_a":    _LV / "SemiTruckMac_S08IN.886.wav",    # 7s   EXT, hard rev to 2195
    "ext_rev_b":    _LV / "SemiTruckMac_S08IN.889.wav",    # 6s   EXT, rev 1565-2175
    "ext_idle":     _LV / "SemiTruckStartIdle_SFXB.264.wav",  # 91s EXT idle ~500-670
}
# UNLICENSED shipped idle -- Duff's real in-cab idle (~800 rpm). For COMPARISON
# of character only; it is being removed and must never be a source or shipped.
COMPARE_IDLE = (Path(__file__).resolve().parents[1] / "src" / "freight_fate"
                / "assets" / "sounds" / "engine" / "idle.ogg")

IDLE_RPM = 647.0
FIRING_HZ = IDLE_RPM / 20.0          # 32.35 Hz -- the engine firing rate at idle
FIRING_PERIOD_S = 20.0 / IDLE_RPM     # 30.9 ms between firings
CYCLE_PERIOD_S = 120.0 / IDLE_RPM     # 185.5 ms per four-stroke cycle

# 1/3-octave centres for all spectral scoring.
THIRD_OCT = np.array([25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315,
                      400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150,
                      4000, 5000, 6300.0])
MATCH_LO, MATCH_HI = 200.0, 1000.0    # energy-match band (the part that agrees)


# --- I/O ---------------------------------------------------------------------


def load_wav(path: Path | str) -> np.ndarray:
    """Mono at SR. Sources are 96 kHz/24-bit, so resample to the engine rate."""
    data, sr = sf.read(str(path), always_2d=True)
    mono = data.mean(axis=1)
    if sr != SR:
        idx = np.linspace(0, len(mono) - 1, int(len(mono) * SR / sr))
        mono = np.interp(idx, np.arange(len(mono)), mono)
    return mono


def write_wav(name: str, x: np.ndarray, target_rms: float = 0.12,
              peak_ceiling: float = 0.97) -> str:
    """Loudness-match to a common RMS and write 16-bit mono to CAND_DIR.

    Matching RMS (not peak) is what makes the menu a fair A/B: a candidate does
    not get to sound better by simply being louder. A peak guard prevents the
    odd transient from clipping. Returns the full path written.
    """
    x = np.nan_to_num(np.asarray(x, dtype=float))
    r = float(np.sqrt(np.mean(x ** 2))) or 1.0
    x = x * (target_rms / r)
    p = float(np.max(np.abs(x))) or 1.0
    if p > peak_ceiling:
        x = x * (peak_ceiling / p)
    CAND_DIR.mkdir(parents=True, exist_ok=True)
    out = CAND_DIR / name
    with wave.open(str(out), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes((x * 32767).astype("<i2").tobytes())
    return str(out)


def tile(x: np.ndarray, seconds: float) -> np.ndarray:
    """Repeat a loop to a duration -- so the seam is AUDIBLE if it exists."""
    n = int(seconds * SR)
    if len(x) == 0:
        return np.zeros(n)
    return np.tile(x, int(np.ceil(n / len(x))))[:n]


# --- spectral measurement ----------------------------------------------------


def band_power(x: np.ndarray) -> np.ndarray:
    S = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    return np.array([S[(f >= fc / 2 ** (1 / 6)) & (f < fc * 2 ** (1 / 6))].sum()
                     for fc in THIRD_OCT])


def diff_curve(cand: np.ndarray, real: np.ndarray) -> np.ndarray:
    """dB(cand/real) per 1/3-oct, energy-matched over 200-1000 Hz."""
    pc, pr = band_power(cand), band_power(real)
    m = (THIRD_OCT >= MATCH_LO) & (THIRD_OCT <= MATCH_HI)
    pc = pc * (pr[m].sum() / (pc[m].sum() or 1.0))
    return 10.0 * np.log10((pc + 1e-12) / (pr + 1e-12))


def diff_summary(cand: np.ndarray, real: np.ndarray) -> dict:
    d = diff_curve(cand, real)
    return {
        "low_db": float(d[(THIRD_OCT >= 40) & (THIRD_OCT <= 160)].mean()),
        "mid_db": float(d[(THIRD_OCT >= 200) & (THIRD_OCT <= 1000)].mean()),
        "high_db": float(d[(THIRD_OCT >= 2500) & (THIRD_OCT <= 5000)].mean()),
        # "Boxy" = a mid hump the real cab does not have. Measure how far the
        # candidate's 200-1500 Hz CONTOUR departs from the real one (RMS dB,
        # after the energy match). Near 0 = same broad shape as the real idle;
        # large = a resonant box. This is the number that tracks Norm's "boxy".
        "mid_shape_dev": float(np.sqrt(np.mean(
            d[(THIRD_OCT >= 200) & (THIRD_OCT <= 1500)] ** 2))),
    }


def fullness(x: np.ndarray) -> float:
    """Envelope collapse between firings (CV of the 2 ms-smoothed envelope).

    The real idle sits at 0.35: individual firings audible but a continuous bed
    underneath. Above ~0.7 is a train of separate thumps (putt-putt); near 0.2
    is a smooth drone with no life. Match the real, do not minimise it.
    """
    env = np.abs(x)
    w = max(4, int(0.002 * SR))
    env = np.convolve(env, np.ones(w) / w, mode="same")
    return float(env.std() / (env.mean() or 1.0))


def seam_check(x: np.ndarray) -> float:
    """Loop-join discontinuity as a multiple of the signal's own step size.

    ~1.0 means the join is indistinguishable from any other sample boundary;
    the reference idle scores 17x, which is the pause Norm hears every loop. A
    shippable loop must sit near 1 -- this is a hard gate, not a preference.
    """
    step = abs(float(x[0] - x[-1]))
    typical = float(np.sqrt(np.mean(np.diff(x) ** 2))) or 1.0
    return step / typical


def formant_centroid(x: np.ndarray, lo: float = 150.0, hi: float = 2200.0) -> float:
    """Centroid of the octave-smoothed spectral ENVELOPE over the body band.

    The micro-engine test. Formants are fixed cab/block resonances, so this
    should barely move between idle and a rev. If it rises with rpm, the method
    is pitch-shifting the whole spectrum -- the big-engine-to-small-engine bug.
    """
    S = np.abs(np.fft.rfft(x))
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    logf = np.log2(np.maximum(f, 1.0))
    env = np.empty_like(S)
    for i in range(len(S)):
        env[i] = S[np.abs(logf - logf[i]) <= 1 / 6].mean()
    band = (f >= lo) & (f <= hi)
    return float((f[band] * env[band]).sum() / (env[band].sum() or 1.0))


def score(idle_loop: np.ndarray, rev: np.ndarray | None = None) -> dict:
    """The guardrail metrics for one candidate. Ear still judges; this gates."""
    real = load_wav(REF_IDLE)
    out = {"fullness": round(fullness(idle_loop), 3),
           "real_fullness": round(fullness(real), 3),
           "seam": round(seam_check(idle_loop), 2)}
    out.update({k: round(v, 2) for k, v in diff_summary(idle_loop, real).items()})
    if rev is not None and len(rev) > SR:
        # formant drift from the first second (near idle) to the last (revved)
        c0 = formant_centroid(rev[:SR])
        c1 = formant_centroid(rev[-SR:])
        out["rev_formant_ratio"] = round(c1 / (c0 or 1.0), 3)
    return out


def load_real_idle_target() -> np.ndarray:
    return load_wav(REF_IDLE)


def load_real_idle_source() -> np.ndarray:
    """The long continuous real idle to cut/stretch/analyse (not the bad loop)."""
    return load_wav(SRC_IDLE_LONG)


# --- real-material helpers (shared so the fan-out is consistent) --------------


def rpm_track(x: np.ndarray, hop_s: float = 0.25, win_s: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """Firing frequency -> rpm across a file, by harmonic sum (octave-robust).

    Plain autocorrelation octave-errors on engines; scoring each candidate f0 by
    the energy stacked at f0..8f0 lets the true fundamental win. Clamped to a
    real diesel's 500-2200 rpm.
    """
    w, hop = int(win_s * SR), int(hop_s * SR)
    cand = np.arange(500.0, 2200.0, 5.0) / 20.0
    times, rpm = [], []
    for i in range(0, max(1, len(x) - w), hop):
        seg = x[i:i + w] * np.hanning(w)
        if np.sqrt(np.mean(seg ** 2)) < 1e-4:
            times.append(i / SR); rpm.append(0.0); continue
        S = np.abs(np.fft.rfft(seg)); f = np.fft.rfftfreq(w, 1.0 / SR)
        scores = np.zeros(len(cand))
        for ci, f0 in enumerate(cand):
            acc = 0.0
            for k in range(1, 9):
                fk = f0 * k
                if fk >= f[-1]:
                    break
                lo, hi = np.searchsorted(f, (fk * 0.97, fk * 1.03))
                if hi > lo:
                    acc += S[lo:hi].max()
            scores[ci] = acc
        times.append(i / SR); rpm.append(cand[int(np.argmax(scores))] * 20.0)
    return np.array(times), np.array(rpm)


def find_steady_window(x: np.ndarray, target_rpm: float, dur_s: float = 2.5,
                       tol: float = 70.0) -> np.ndarray | None:
    """The steadiest dur_s slice whose rpm sits within tol of target_rpm.

    Returns None if the take never dwells near that rpm -- the caller then falls
    back to stretching the nearest content instead of cutting.
    """
    t, r = rpm_track(x)
    if len(t) < 3:
        return None
    hop = t[1] - t[0]
    need = int(dur_s / hop)
    best, best_dev = None, 1e9
    for i in range(0, len(r) - need):
        seg = r[i:i + need]
        if np.any(seg <= 0) or abs(seg.mean() - target_rpm) > tol:
            continue
        dev = float(seg.std())
        if dev < best_dev:
            best_dev, best = dev, i
    if best is None:
        return None
    a = int(t[best] * SR)
    return x[a:a + int(dur_s * SR)]


def make_seamless_loop(x: np.ndarray, xfade_s: float = 0.012,
                       max_trim_s: float = 0.16) -> np.ndarray:
    """Loop with no click AND no phasing, by landing the join on a real period.

    The old version overlapped ~120 ms of the wrapped tail onto the head. The
    amplitude matched (seam_check ~1) but the two overlapped stretches of engine
    are DECORRELATED, so the overlap combs -- the "tape changing phase for a
    quarter second every loop" Norm hears. Fix: find the loop end near the
    intended length where the real continuation x[e:e+C] most resembles the head
    x[:C] -- i.e. a natural firing-cycle boundary -- then crossfade only a SHORT
    window (~12 ms) of two segments that already match, so there is nothing to
    comb. Trims at most one cycle, so the loop stays the length it was meant to.
    """
    n = len(x)
    xf = min(int(xfade_s * SR), int(0.015 * SR))   # cap: long fades are the bug
    C = int(0.006 * SR)                             # 6 ms match context
    if n <= 2 * (C + xf):
        return x
    head = x[:C]
    seg2 = np.convolve(x ** 2, np.ones(C), "valid")          # sum x[j:j+C]^2
    cc = np.correlate(x, head, "valid")                      # sum x[j:j+C]*head
    ssd = seg2[:len(cc)] - 2.0 * cc + float(np.dot(head, head))
    e_hi = n - C
    e_lo = max(C + xf + 1, n - int(max_trim_s * SR))
    idx = np.arange(len(ssd))
    m = (idx >= e_lo) & (idx <= e_hi)
    e = int(idx[m][np.argmin(ssd[m])])
    y = x[:e].copy()
    w = np.linspace(0.0, 1.0, xf)
    y[:xf] = x[:xf] * w + x[e:e + xf] * (1.0 - w)   # blends two matched segments
    return y


def _envelope(npy_name: str) -> tuple[np.ndarray, np.ndarray]:
    a = np.load(REF_DIR / npy_name)
    return a[0], a[1]


def interiorize(x: np.ndarray) -> np.ndarray:
    """Turn an EXTERIOR take into the cab: multiply by interior/exterior ratio.

    H = envelope(859 interior) / envelope(904 exterior), normalised over the
    match band, applied as a zero-phase filter. This is the transform validated
    in section 7 (+~20 dB at 60-100 Hz, ~flat above 2 kHz) that unlocks every
    exterior sweep as in-cab source.
    """
    if_f, if_m = _envelope("formant859.npy")
    ef_f, ef_m = _envelope("formant904_sweep.npy")
    n = len(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    Hi = np.interp(f, if_f, if_m, left=if_m[0], right=if_m[-1])
    He = np.interp(f, ef_f, ef_m, left=ef_m[0], right=ef_m[-1])
    H = Hi / np.maximum(He, He.max() * 1e-3)
    band = (f >= MATCH_LO) & (f <= MATCH_HI)
    Hn = H / (H[band].mean() or 1.0)
    return np.fft.irfft(np.fft.rfft(x) * Hn, n)


if __name__ == "__main__":  # smoke test: print the target's own scores
    real = load_wav(REF_IDLE)
    print("reference idle self-scores:")
    print("  fullness", round(fullness(real), 3), " seam", round(seam_check(real), 2))
    print("  source long-idle:", round(len(load_real_idle_source()) / SR, 2), "s")
    print("  formant centroid:", round(formant_centroid(real), 1), "Hz")
