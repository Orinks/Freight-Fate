"""TD-PSOLA engine voice from ONE interior idle take (int_idle_low, 645-1275 rpm).

Method: find the firing rate with C.rpm_track, place pitch marks one firing
period apart (period = 20/rpm s ~ 31 ms at idle), cut 2-period Hann grains at
each mark, then OLA the grains at a NEW target firing period to move rpm while
each grain's internal spectrum -- the fixed cab/block formant -- is left alone.

  idle  -> re-space a steady idle window at the idle period, integer grain count,
           seamless loop.
  rev   -> ramp the target period from idle (~650) up to 1800 rpm over ~7 s.
  cruise-> re-space to 1500 rpm and seamless-loop.

Because every grain is a real idle firing, the ~800 Hz body resonance never
moves with rpm: only the spacing between firings changes. That is the whole
point -- it defeats the micro-engine bug by construction.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt

import cand_common as C

RNG = np.random.default_rng(7)
SR = C.SR
KEY = "psola"


def tame_clatter(x: np.ndarray, f_lo: float = 1600.0, f_hi: float = 3500.0,
                 g_hi: float = 0.45) -> np.ndarray:
    """One static high-shelf that eases this take's extra injector clatter.

    int_idle_low sits ~+10 dB above the reference cab in the 2.5-5 kHz clatter
    band -- a brighter, hissier recording. A single fixed shelf above the body
    band (>1600 Hz, so the 200-1500 Hz formant contour is untouched) brings the
    top end back toward the validated reference. Because the same filter is
    applied to every rpm before any grain is cut, the formant stays fixed -- it
    cannot cause the micro-engine drift the score guards against.
    """
    n = len(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    t = np.clip((np.log2(np.maximum(f, 1.0)) - np.log2(f_lo))
                / (np.log2(f_hi) - np.log2(f_lo)), 0.0, 1.0)
    return np.fft.irfft(np.fft.rfft(x) * (1.0 + (g_hi - 1.0) * t), n)


def firing_marks(x: np.ndarray, rpm_local: float) -> np.ndarray:
    """Pitch marks anchored to firing thumps, ~one firing period apart.

    We know the nominal firing period from rpm; we refine each mark to the
    local energy peak of the low-passed firing envelope so grains are phase
    coherent (each grain centred on a real combustion event).
    """
    p0 = SR * 20.0 / rpm_local                      # nominal firing period (samples)
    # firing thump envelope: rectify then smooth over ~half a firing period
    b, a = butter(2, 200.0 / (SR / 2), btype="low")
    env = filtfilt(b, a, np.abs(x))
    marks = []
    # first mark: strongest peak inside the opening period
    m = int(np.argmax(env[: int(p0)]))
    n = len(x)
    while m + p0 * 0.5 < n:
        marks.append(m)
        # search the next firing in a +-30% window around one period ahead
        lo = int(m + 0.7 * p0)
        hi = int(min(n, m + 1.3 * p0))
        if hi - lo < 4:
            break
        m = lo + int(np.argmax(env[lo:hi]))
    return np.array(marks, dtype=int)


def cut_grains(x: np.ndarray, marks: np.ndarray, half: int) -> list[np.ndarray]:
    """2*half-sample Hann grains centred on each usable mark."""
    win = np.hanning(2 * half)
    grains = []
    for m in marks:
        a, b = m - half, m + half
        if a < 0 or b > len(x):
            continue
        grains.append(x[a:b] * win)
    return grains


def ola(grains: list[np.ndarray], half: int, n_out: int,
        period_fn, gain_fn=None) -> np.ndarray:
    """Overlap-add grains at a target firing period, normalised by window sum.

    period_fn(sample_index) -> target firing period in samples (may vary for a
    rev). Grains are drawn cyclically from the idle bank so the formant is fixed.
    Dividing by the accumulated Hann window keeps amplitude constant no matter
    how much the grains overlap when the period shrinks.
    """
    out = np.zeros(n_out + 2 * half)
    wsum = np.zeros(n_out + 2 * half)
    win = np.hanning(2 * half)
    k = 0
    centre = float(half)
    ng = len(grains)
    while centre < n_out:
        c = int(centre)
        g = grains[k % ng]
        gain = 1.0 if gain_fn is None else gain_fn(centre)
        out[c - half:c - half + 2 * half] += g * gain
        wsum[c - half:c - half + 2 * half] += win
        centre += period_fn(centre)
        k += 1
    y = out[:n_out] / np.maximum(wsum[:n_out], 1e-4)
    return y


def main() -> None:
    src = C.load_wav(C.LICENSED["int_idle_low"])
    src = tame_clatter(src)             # ease the take's extra top-end clatter

    # --- steady idle window + its measured rpm --------------------------------
    win = C.find_steady_window(src, 660.0, dur_s=4.0, tol=90.0)
    if win is None:                     # fall back to the low-rpm head of the take
        win = src[: int(6.0 * SR)]
    t, r = C.rpm_track(win)
    good = r[r > 0]
    idle_rpm = float(np.median(good)) if len(good) else 660.0
    idle_rpm = float(np.clip(idle_rpm, 600.0, 720.0))

    half = int(round(SR * 20.0 / idle_rpm))          # one firing period (grain half)
    marks = firing_marks(win, idle_rpm)
    grains = cut_grains(win, marks, half)
    if len(grains) < 6:
        raise SystemExit("too few grains extracted -- check source window")

    # --- IDLE: re-space at the idle period, integer grain count, loop ---------
    period_idle = SR * 20.0 / idle_rpm
    n_grains_loop = len(grains)                       # use each real firing once
    loop_len = int(round(n_grains_loop * period_idle))
    idle_raw = ola(grains, half, loop_len,
                   period_fn=lambda c: period_idle)
    idle_loop = C.make_seamless_loop(idle_raw)
    idle_tiled = C.tile(idle_loop, 6.0)

    # --- REV: ramp the firing period from idle rpm up to 1800 over ~7 s -------
    rev_secs = 7.0
    n_rev = int(rev_secs * SR)
    rpm_lo, rpm_hi = idle_rpm, 1800.0

    def rev_rpm(sample_c: float) -> float:
        frac = np.clip(sample_c / n_rev, 0.0, 1.0)
        return rpm_lo + (rpm_hi - rpm_lo) * frac

    def rev_period(sample_c: float) -> float:
        return SR * 20.0 / rev_rpm(sample_c)

    def rev_gain(sample_c: float) -> float:
        # a diesel does get louder off idle; keep it gentle so RMS-match is fair
        return float((rev_rpm(sample_c) / idle_rpm) ** 0.2)

    rev = ola(grains, half, n_rev, period_fn=rev_period, gain_fn=rev_gain)

    # --- CRUISE 1500: constant firing period, seamless loop -------------------
    period_1500 = SR * 20.0 / 1500.0
    # integer firings so a natural loop point exists near ~1.5 s of content
    n_c = int(round(round(2.2 / (period_1500 / SR)) * period_1500))
    cruise_raw = ola(grains, half, n_c, period_fn=lambda c: period_1500)
    cruise_loop = C.make_seamless_loop(cruise_raw)
    cruise_tiled = C.tile(cruise_loop, 4.0)

    p_idle = C.write_wav(f"candidate_{KEY}_idle.wav", idle_tiled)
    p_rev = C.write_wav(f"candidate_{KEY}_rev.wav", rev)
    p_cru = C.write_wav(f"candidate_{KEY}_cruise1500.wav", cruise_tiled)

    metrics = C.score(idle_loop, rev)
    print("idle_rpm measured:", round(idle_rpm, 1),
          " grains:", len(grains), " half(samples):", half)
    print("files:")
    for p in (p_idle, p_rev, p_cru):
        print("  ", p)
    print("score:", metrics)
    for nm, arr in (("idle", idle_tiled), ("rev", rev), ("cruise", cruise_tiled)):
        print(f"  rms {nm}:", round(float(np.sqrt(np.mean(arr ** 2))), 4))


if __name__ == "__main__":
    main()
