"""HYBRID candidate: real interior BODY bed + synth LOAD layer.

Layer 1 (fullness bed). Wherever a real interior recording already sits at the
target rpm, use it DIRECTLY -- a steady idle window (~647 rpm) for the idle and
a steady 1500 rpm window for cruise, each low-passed ~1.6 kHz so it carries the
body and bottom. The real signal's own firing-to-firing variation supplies the
fullness (~0.35) and the fixed ~800 Hz cab/block body resonance for free. For
the REV, where the rate must climb continuously from idle to 1800, no single
window fits, so the idle window is cut into firing-synchronous grains and
re-triggered by epoch-driven overlap-add: the firing RATE is set purely by how
far apart the grains are placed while each grain's CONTENT is left untouched --
a PSOLA-style retime that keeps the body formant fixed instead of pitch-shifting
a big diesel into a micro-engine.

Layer 2 (synth load, grows with rpm). Diesel KNOCK -- short broadband bursts at
the firing rate through FIXED resonances weighted low so the load's own spectral
centre sits near the body's, and it adds working grit without shifting the voice
up. A TURBO whine glides with boost, deliberately NOT locked to the firing
harmonics and pitched above 2.2 kHz so it colours the rev without falsifying the
body. A firing-edge tick sharpens each combustion. At idle the load is a whisper
under the real bed; on the rev and at cruise it grows into the working-engine
character the neutral recordings lack -- any thinness hides under real body.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import cand_common as C
from scipy.signal import butter, sosfilt, sosfiltfilt

KEY = "hybrid"
SR = C.SR
rng = np.random.default_rng(7)


# --- filters -----------------------------------------------------------------

def lp(x, fc, order=4):
    sos = butter(order, fc / (SR / 2), btype="low", output="sos")
    return sosfiltfilt(sos, x)


def hp(x, fc, order=2):
    sos = butter(order, fc / (SR / 2), btype="high", output="sos")
    return sosfiltfilt(sos, x)


def bp(x, lo, hi, order=2):
    sos = butter(order, [lo / (SR / 2), hi / (SR / 2)], btype="band", output="sos")
    return sosfilt(sos, x)


def norm(x):
    return x / (np.sqrt(np.mean(np.asarray(x, float) ** 2)) or 1.0)


BODY_FC = 1600.0   # bed low-pass: carries body + bottom, load fills above
BODY_HP = 50.0     # tame sub-rumble so low_db matches the real idle


def _body(x):
    return hp(lp(x, BODY_FC), BODY_HP)


# --- real steady windows (idle + cruise beds, native fullness) ---------------

def _real_window(source_key, rpm, dur_s=3.0):
    x = C.load_wav(C.LICENSED[source_key])
    w = C.find_steady_window(x, rpm, dur_s=dur_s)
    if w is None:
        w = x[: int(dur_s * SR)]
    return norm(w / (np.max(np.abs(w)) or 1.0))


# --- grain bed (rev retime, formant-fixed) -----------------------------------

def _idle_window():
    return _real_window("int_idle_low", 660, dur_s=3.0)


def _pitch_marks(w, rpm):
    P = SR * 20.0 / rpm
    sm = int(0.003 * SR)
    env = np.convolve(np.abs(w), np.ones(sm) / sm, mode="same")
    marks = [int(np.argmax(env[: int(1.5 * P)]))]
    while True:
        c = marks[-1] + P
        lo, hi = int(c - 0.30 * P), int(c + 0.30 * P)
        if hi >= len(w) - 1:
            break
        marks.append(lo + int(np.argmax(env[lo:hi])))
    return marks


def _grains(glen_s=0.07):
    w = _idle_window()
    _, r = C.rpm_track(w)
    rpm = float(np.median(r[r > 0])) or 660.0
    marks = _pitch_marks(w, rpm)
    glen = int(glen_s * SR)
    glen += glen % 2
    half = glen // 2
    win = np.hanning(glen)
    grains = [w[m - half:m - half + glen] * win
              for m in marks if m - half >= 0 and m - half + glen <= len(w)]
    return grains, glen


def _grain_bed(grains, glen, rpm_of_t, dur_s):
    n = int(dur_s * SR)
    out = np.zeros(n + glen)
    half = glen // 2
    pos, gi = 0.0, 0
    while pos < n:
        rpm = rpm_of_t(pos / SR)
        a = max(0, int(pos) - half)
        out[a:a + glen] += grains[gi % len(grains)][: len(out) - a]
        gi += 1
        pos += SR * 20.0 / rpm
    return _body(out[:n])


# --- Layer 2: synth load -----------------------------------------------------

LOAD_FLOOR = 0.22          # knock/tick presence even at idle (keeps rev honest)


def _load_of_rpm(rpm):
    return float(np.clip((rpm - 600.0) / 1200.0, 0.0, 1.0)) * (1.0 - LOAD_FLOOR) + LOAD_FLOOR


def _knock(rpm_of_t, dur_s):
    """Firing-rate broadband bursts through FIXED, low-weighted resonances."""
    n = int(dur_s * SR)
    raw = np.zeros(n + 512)
    blen = int(0.0045 * SR)
    bwin = np.hanning(blen)
    pos = 0.0
    while pos < n:
        rpm = rpm_of_t(pos / SR)
        a = int(pos)
        raw[a:a + blen] += rng.standard_normal(blen) * bwin * _load_of_rpm(rpm)
        pos += SR * 20.0 / rpm
    raw = raw[:n]
    # fixed resonances, weighted low so the knock centre sits near the body's
    return (0.80 * bp(raw, 300, 550)
            + 1.20 * bp(raw, 550, 900)
            + 0.50 * bp(raw, 1000, 1500)
            + 0.22 * bp(raw, 1700, 2100))


def _turbo(rpm_of_t, dur_s):
    """Boost-tracking whine above 2.2 kHz, not locked to the firing grid."""
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    grid = np.linspace(0, dur_s, 200)
    rpm_t = np.interp(t, grid, [rpm_of_t(g) for g in grid])
    boost = np.clip((rpm_t - 650.0) / 1150.0, 0.0, 1.0)
    fw = 3200.0 + boost * 3300.0          # 3.2 -> 6.5 kHz glide
    phase = 2 * np.pi * np.cumsum(fw) / SR
    tone = np.sin(phase) + 0.45 * np.sin(2.0 * phase)
    breath = bp(rng.standard_normal(n), 3200, 6800)
    return (0.62 * tone + 0.38 * norm(breath)) * boost ** 1.5


def _tick(rpm_of_t, dur_s):
    """Sharp firing-edge click, high-passed, grows with load."""
    n = int(dur_s * SR)
    raw = np.zeros(n + 64)
    tlen = int(0.0009 * SR)
    twin = np.hanning(tlen)
    pos = 0.0
    while pos < n:
        rpm = rpm_of_t(pos / SR)
        a = int(pos)
        raw[a:a + tlen] += rng.standard_normal(tlen) * twin * _load_of_rpm(rpm)
        pos += SR * 20.0 / rpm
    return hp(raw[:n], 3800)


def _load(rpm_of_t, dur_s, gain):
    # Turbo whine removed (Norm 2026-07-21: "jet engine whine" -- it read as an
    # aircraft, not a diesel). Knock and tick stay at their original weights, so
    # the load layer gets QUIETER (no turbo term) and the real recorded body
    # carries proportionally more of the working character -- which is the point.
    return gain * (0.60 * norm(_knock(rpm_of_t, dur_s))
                   + 0.12 * norm(_tick(rpm_of_t, dur_s)))


# --- deliverables ------------------------------------------------------------

def main():
    grains, glen = _grains()

    # IDLE -- real ~647 window as bed, whisper of load
    idle_bed = _body(_real_window("int_idle_low", 660, dur_s=3.0))
    idle_bed = norm(idle_bed)
    idle_raw = idle_bed + _load(lambda t: 647.0, len(idle_bed) / SR, gain=0.20)
    idle_loop = C.make_seamless_loop(idle_raw)
    idle_tiled = C.tile(idle_loop, 6.0)

    # REV -- continuous 650 -> 1800 grain-OLA bed, load grows with rpm
    rev_dur = 7.0

    def rev_rpm(t):
        f = np.clip(t / rev_dur, 0.0, 1.0) ** 0.85
        return 650.0 + f * (1800.0 - 650.0)

    rev_bed = norm(_grain_bed(grains, glen, rev_rpm, rev_dur))
    rev = rev_bed + _load(rev_rpm, rev_dur, gain=0.60)

    # CRUISE -- real 1500 window as bed, steady load
    cruise_bed = norm(_body(_real_window("int_mid", 1500, dur_s=3.0)))
    cruise_raw = cruise_bed + _load(lambda t: 1500.0, len(cruise_bed) / SR, gain=0.70)
    cruise_loop = C.make_seamless_loop(cruise_raw)
    cruise_tiled = C.tile(cruise_loop, 4.0)

    files = [
        C.write_wav(f"candidate_{KEY}_idle.wav", idle_tiled),
        C.write_wav(f"candidate_{KEY}_rev.wav", rev),
        C.write_wav(f"candidate_{KEY}_cruise1500.wav", cruise_tiled),
    ]

    def rms(x):
        return float(np.sqrt(np.mean(np.asarray(x, float) ** 2)))

    metrics = C.score(idle_loop, rev)
    print("KEY:", KEY)
    print("rms  idle:", round(rms(idle_tiled), 4),
          " rev:", round(rms(rev), 4), " cruise:", round(rms(cruise_tiled), 4))
    print("grains:", len(grains), " glen_ms:", round(glen / SR * 1000, 1))
    for f in files:
        print("  ", f)
    print("score:", metrics)
    return files, metrics


if __name__ == "__main__":
    main()
