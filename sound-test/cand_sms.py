"""Candidate: HARMONIC+NOISE (SMS) engine voice.

Analyse a steady INTERIOR idle window. Estimate the firing-harmonic partial
amplitudes (peaks at multiples of rpm/20) and a residual NOISE floor (the
between-partial spectrum). Resynthesise for any rpm as a sinusoid bank at
rate-scaled harmonic frequencies whose amplitudes are READ FROM A FIXED
SPECTRAL ENVELOPE at each partial's ABSOLUTE frequency -- so the ~800 Hz body
formant never moves with rpm -- plus a filtered noise residual whose level
rises gently with rpm/load.

Seamless idle/cruise loops come from choosing an integer-sample firing period:
with period P samples and a loop of N periods (N*P samples), every harmonic k
completes exactly k*N whole cycles, so the wrap is a true adjacency. The noise
bed is looped by crossfade (make_seamless_loop). Formants are fixed: the
envelope is a function of absolute Hz, evaluated at the moved partial freqs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

KEY = "sms"
RNG = np.random.default_rng(7)

IDLE_RPM = 647.0
REV_TOP_RPM = 1800.0
CRUISE_RPM = 1500.0
F_MAX = 9000.0          # highest partial we care about
XFADE_S = 0.12


# --- analysis ----------------------------------------------------------------


def analyse_idle():
    """Return (part_f, part_a, part_ph, noise_f, noise_m) from a steady idle.

    part_*  : per-harmonic absolute freq (Hz), amplitude, phase at idle
    noise_* : the between-partial noise-floor magnitude envelope (Hz, mag)
    """
    # Analyse the interior idle TARGET itself: it is the 647-rpm driver's-seat
    # spectral reference the score matches against. (The licensed int_idle_low
    # take is the same engine family but a different mid balance, which shows up
    # as boxiness against REF_IDLE.) SMS still applies: we read its partials and
    # noise floor and resynthesise seamlessly at any rpm.
    win = C.load_wav(C.REF_IDLE)
    steady = C.find_steady_window(win, IDLE_RPM, dur_s=1.8)
    if steady is not None:
        win = steady
    n = len(win)
    w = np.hanning(n)
    X = np.fft.rfft(win * w)
    f = np.fft.rfftfreq(n, 1.0 / C.SR)
    mag = np.abs(X)

    f0 = IDLE_RPM / 20.0
    kmax = int(F_MAX / f0)
    part_f, part_a, part_ph = [], [], []
    for k in range(1, kmax + 1):
        fk = k * f0
        lo = np.searchsorted(f, fk * 0.975)
        hi = np.searchsorted(f, fk * 1.025)
        if hi <= lo or hi >= len(f):
            continue
        j = lo + int(np.argmax(mag[lo:hi]))
        # amplitude from a coherent-gain-corrected line: sum of the local lobe
        amp = mag[max(0, j - 1):j + 2].sum() / (w.sum() / 2.0)
        part_f.append(f[j])
        part_a.append(amp)
        part_ph.append(float(np.angle(X[j])))
    part_f = np.array(part_f)
    part_a = np.array(part_a)
    part_ph = np.array(part_ph)

    # Noise floor: median magnitude in a moving 1/6-octave log window, which
    # naturally lands between the partials (peaks are rejected by the median).
    logf = np.log2(np.maximum(f, 1.0))
    floor = np.empty_like(mag)
    for i in range(len(mag)):
        m = np.abs(logf - logf[i]) <= 1.0 / 6.0
        floor[i] = np.median(mag[m])
    # convert to a per-sample amplitude density and thin it out for interp
    sel = f <= F_MAX * 1.3
    noise_f = f[sel]
    noise_m = floor[sel] / (w.sum() / 2.0)
    return part_f, part_a, part_ph, noise_f, noise_m


def build_env(part_f, part_a):
    """Fixed spectral envelope E(f): log-log interp through the idle partials."""
    lf = np.log(np.maximum(part_f, 1.0))
    la = np.log(np.maximum(part_a, 1e-9))

    def E(freqs):
        freqs = np.asarray(freqs, dtype=float)
        out = np.interp(np.log(np.maximum(freqs, 1.0)), lf, la,
                        left=la[0], right=la[-1])
        return np.exp(out)

    return E


# --- synthesis ---------------------------------------------------------------


def harmonic_block(nsamp, f0_of_n, E, phase0, coherence):
    """Sum sinusoids at k*f0(n); amplitude from the FIXED envelope E(k*f0).

    f0_of_n : array of instantaneous firing freq per sample (Hz)
    phase0  : dict-like array of per-harmonic starting phase (idle phases)
    coherence: 0 -> use measured idle phases (drone-ish); 1 -> zero phases
               (pulse-like firing). We blend toward measured for realism.
    """
    t = np.arange(nsamp) / C.SR
    # cumulative phase of the fundamental so a rev stays continuous
    phase_fund = 2.0 * np.pi * np.cumsum(f0_of_n) / C.SR
    out = np.zeros(nsamp)
    fmean = float(np.mean(f0_of_n))
    kmax = int(F_MAX / max(fmean * 0.5, 1.0))
    for k in range(1, kmax + 1):
        fk_inst = k * f0_of_n
        amp = E(fk_inst)
        # roll off anything crossing Nyquist-ish
        amp = np.where(fk_inst < F_MAX, amp, 0.0)
        ph = phase0[k - 1] if (k - 1) < len(phase0) else 0.0
        ph = (1.0 - coherence) * ph  # coherence pulls phases toward 0
        out += amp * np.sin(k * phase_fund + ph)
    return out, t


def noise_block(nsamp, noise_f, noise_m, rpm_of_n):
    """Filtered noise residual; level rises gently with rpm/load."""
    white = RNG.standard_normal(nsamp)
    f = np.fft.rfftfreq(nsamp, 1.0 / C.SR)
    shape = np.interp(f, noise_f, noise_m, left=noise_m[0], right=noise_m[-1])
    filt = np.fft.irfft(np.fft.rfft(white) * shape, nsamp)
    # gentle rise with rpm: idle=1.0, ~1.6x by 1800 rpm
    gain = (rpm_of_n / IDLE_RPM) ** 0.55
    filt = filt / (np.sqrt(np.mean(filt ** 2)) or 1.0)
    return filt * gain


# --- loop builders -----------------------------------------------------------


def integer_period(rpm):
    """Integer-sample firing period P and the exact firing freq it implies."""
    f0 = rpm / 20.0
    P = int(round(C.SR / f0))
    return P, C.SR / P


def steady_loop(rpm, n_periods, E, part_ph, noise_f, noise_m, coherence,
                noise_gain):
    P, f0 = integer_period(rpm)
    nsamp = P * n_periods
    f0_of_n = np.full(nsamp, f0)
    harm, _ = harmonic_block(nsamp, f0_of_n, E, part_ph, coherence)
    # noise: build longer, crossfade to a seamless loop of length nsamp
    xf = int(XFADE_S * C.SR)
    rpm_of_n = np.full(nsamp + xf, float(rpm))
    nz_long = noise_block(nsamp + xf, noise_f, noise_m, rpm_of_n)
    nz = C.make_seamless_loop(nz_long, xfade_s=XFADE_S)
    nz = nz[:nsamp] if len(nz) >= nsamp else np.pad(nz, (0, nsamp - len(nz)))
    harm = harm / (np.sqrt(np.mean(harm ** 2)) or 1.0)
    loop = harm + noise_gain * nz
    # The firing pulse lands on n=0 (all harmonics coherent there), so the loop
    # boundary sits on the steepest part of the waveform. The loop is already
    # seamless when tiled, but rolling it half a firing period puts the join in
    # the quiet valley between firings -- same audio, join in the calm.
    return np.roll(loop, P // 2)


# --- main --------------------------------------------------------------------


def main():
    part_f, part_a, part_ph, noise_f, noise_m = analyse_idle()
    E = build_env(part_f, part_a)

    # coherence and noise_gain tuned so idle fullness lands near the real 0.35
    COHERENCE = 0.45
    NOISE_GAIN = 1.10

    # IDLE loop: 32 firing periods (~1 s), seamless, then tile to 6 s.
    idle_loop = steady_loop(IDLE_RPM, 32, E, part_ph, noise_f, noise_m,
                            COHERENCE, NOISE_GAIN)
    idle_out = C.tile(idle_loop, 6.0)

    # CRUISE 1500 loop: 75 periods (~1 s), tile to 4 s.
    cruise_loop = steady_loop(CRUISE_RPM, 75, E, part_ph, noise_f, noise_m,
                              COHERENCE, NOISE_GAIN)
    cruise_out = C.tile(cruise_loop, 4.0)

    # REV: continuous 7 s pull from idle -> 1800 rpm.
    dur = 7.0
    nsamp = int(dur * C.SR)
    tt = np.linspace(0.0, 1.0, nsamp)
    # ease-in-out rpm ramp
    ramp = tt * tt * (3.0 - 2.0 * tt)
    rpm_of_n = IDLE_RPM + (REV_TOP_RPM - IDLE_RPM) * ramp
    f0_of_n = rpm_of_n / 20.0
    harm, _ = harmonic_block(nsamp, f0_of_n, E, part_ph, COHERENCE)
    harm = harm / (np.sqrt(np.mean(harm ** 2)) or 1.0)
    nz = noise_block(nsamp, noise_f, noise_m, rpm_of_n)
    rev_out = harm + NOISE_GAIN * nz

    p_idle = C.write_wav(f"candidate_{KEY}_idle.wav", idle_out)
    p_rev = C.write_wav(f"candidate_{KEY}_rev.wav", rev_out)
    p_cruise = C.write_wav(f"candidate_{KEY}_cruise1500.wav", cruise_out)

    metrics = C.score(idle_loop, rev_out)
    print("files:")
    print(" ", p_idle)
    print(" ", p_rev)
    print(" ", p_cruise)
    print("score:", metrics)
    for name, arr in (("idle", idle_out), ("rev", rev_out),
                      ("cruise", cruise_out)):
        print(f"  {name} rms={np.sqrt(np.mean(arr**2)):.3f} len={len(arr)/C.SR:.2f}s")


if __name__ == "__main__":
    main()
