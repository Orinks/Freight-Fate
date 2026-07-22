"""Lift the cab/block formants off a real recording and give back the numbers.

Read-only over the library. Writes WAVs and a resonance table to C:\\temp\\fftest.

THE PIANOTEQ MOVE (Norm, 2026-07-20). Modartt measured real instruments to get
a basis, then exposed the parameters so you can twiddle them -- which is why
you can build instruments that never existed. Same shape here: measure a real
in-cab diesel to get the resonance basis, then hand back a table of
frequencies, bandwidths and gains that can be tuned by ear like a piano.

The recording supplies the FILTER. The synth supplies the SOURCE. That split
is the entire point, because it is what a recording cannot give you: a real
loop is welded to one RPM, and pitch-shifting it drags the formants with it,
which is the toy sound. Lift the formants off once and they stop moving, which
is physically correct -- a cab does not resonate differently because the
engine is revving.

METHOD. Linear prediction. LPC fits an all-pole filter to the spectrum, which
is exactly a resonator bank: each conjugate pole pair IS one resonance, with a
centre frequency and a bandwidth. That makes this literally a source/filter
separation rather than an analogy -- the LPC residual is the excitation and
the poles are the structure. Analysis runs at a reduced rate so the available
poles get spent on the region that matters (block, cab, panels, all under a
few kHz) rather than on hiss.

CAVEAT WORTH KNOWING. LPC cannot tell a cab resonance from a strong engine
harmonic. On a very steady recording the firing harmonics are narrow and
loud, and some poles will lock onto them -- which would bake one RPM back
into the "fixed" filter, the exact thing we are trying to avoid. Mitigations
here: pick windows with cycle-to-cycle variation, and report each pole's
bandwidth so narrow ones can be spotted and widened or dropped. A structural
resonance is broad; a captured harmonic is needle-thin.

Usage: uv run --with numpy --with soundfile python sound-test/engine_formants.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pulse_synth
import soundfile as sf
from engine_v1 import engine, profile_line
from pulse_synth import SR, write_wav

pulse_synth.OUT = Path(r"C:\temp\fftest")
OUT = pulse_synth.OUT

ANALYSIS_SR = 12000  # poles spent below 6 kHz, where the cab actually lives
LPC_ORDER = 34


def resample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    if src == dst:
        return x
    idx = np.linspace(0, len(x) - 1, int(len(x) * dst / src))
    return np.interp(idx, np.arange(len(x)), x)


def levinson(r: np.ndarray, order: int) -> np.ndarray:
    """Levinson-Durbin: autocorrelation sequence -> all-pole coefficients."""
    a = np.zeros(order + 1)
    a[0] = 1.0
    err = r[0]
    if err <= 0:
        return a
    for i in range(1, order + 1):
        acc = r[i] + np.dot(a[1:i], r[i - 1:0:-1]) if i > 1 else r[i]
        k = -acc / err
        a[1:i + 1] = a[1:i + 1] + k * a[i - 1::-1][:i]
        err *= 1.0 - k * k
        if err <= 0:
            break
    return a


def lpc(x: np.ndarray, order: int = LPC_ORDER) -> np.ndarray:
    """All-pole fit to a windowed frame, via the autocorrelation method."""
    w = x * np.hanning(len(x))
    # Slight pre-emphasis: without it the fit spends most of its poles on the
    # steep low-frequency tilt and resolves the upper resonances poorly.
    w = np.append(w[0], w[1:] - 0.97 * w[:-1])
    full = np.correlate(w, w, "full")[len(w) - 1:]
    if full[0] <= 0:
        return np.zeros(order + 1)
    return levinson(full[:order + 1] / full[0], order)


def poles_to_resonances(a: np.ndarray, sr: int = ANALYSIS_SR) -> list[tuple[float, float, float]]:
    """Turn the all-pole coefficients into (frequency, bandwidth, gain) rows.

    One conjugate pole pair per resonance. Bandwidth comes from how close the
    pole sits to the unit circle -- near the edge means lightly damped and
    narrow, deeper in means broad and heavily damped. Narrow ones are the
    suspicious ones (see the caveat in the module docstring).
    """
    roots = [r for r in np.roots(a) if r.imag > 0 and abs(r) < 1.0]
    out = []
    for r in roots:
        freq = float(np.angle(r) * sr / (2 * np.pi))
        bw = float(-np.log(abs(r)) * sr / np.pi)
        if 25.0 < freq < sr / 2 * 0.95 and bw > 0:
            out.append((freq, bw, float(1.0 / max(bw, 1.0))))
    out.sort(key=lambda t: t[0])
    if out:
        top = max(g for _, _, g in out)
        out = [(f, b, g / top) for f, b, g in out]
    return out


def envelope_from_lpc(a: np.ndarray, n_fft: int, sr_a: int, sr_out: int) -> np.ndarray:
    """Magnitude response of the all-pole filter, mapped onto the output rate."""
    w = np.linspace(0, np.pi, n_fft // 2 + 1)
    z = np.exp(-1j * np.outer(w, np.arange(len(a))))
    mag = 1.0 / np.maximum(np.abs(z @ a), 1e-6)
    f_a = np.linspace(0, sr_a / 2, len(mag))
    f_o = np.linspace(0, sr_out / 2, n_fft // 2 + 1)
    env = np.interp(f_o, f_a, mag, right=mag[-1] * 0.02)
    return env / (env.max() or 1.0)


def apply_envelope(x: np.ndarray, env: np.ndarray) -> np.ndarray:
    """Impose a magnitude envelope on a signal, phase untouched."""
    n = len(x)
    spec = np.fft.rfft(x)
    e = np.interp(np.linspace(0, 1, len(spec)), np.linspace(0, 1, len(env)), env)
    return np.fft.irfft(spec * e, n)


def donor_frames(x: np.ndarray, sr: int, n_frames: int = 24) -> np.ndarray:
    """Average LPC over several frames, so one odd moment cannot define the cab."""
    xa = resample(x, sr, ANALYSIS_SR)
    flen = int(0.064 * ANALYSIS_SR)
    step = max(flen // 2, (len(xa) - flen) // max(n_frames, 1))
    fits = []
    for i in range(0, len(xa) - flen, step):
        a = lpc(xa[i:i + flen])
        if np.isfinite(a).all() and abs(a[0] - 1.0) < 1e-9:
            fits.append(a)
    if not fits:
        return np.zeros(LPC_ORDER + 1)
    # Average the SPECTRA, not the coefficients -- averaging LPC coefficients
    # directly is not meaningful and can land you outside the stable region.
    return np.array(fits)


def main() -> None:
    donors = sorted(OUT.glob("donor_*.wav"))
    if len(sys.argv) > 1:
        donors = [Path(sys.argv[1])]
    if not donors:
        print("No donor_*.wav found. Run engine_donor_scan.py first.")
        return

    n_fft = 8192
    for path in donors:
        d, sr = sf.read(str(path), always_2d=True)
        x = d.mean(axis=1)
        fits = donor_frames(x, sr)
        if not len(fits):
            print(f"{path.name}: no usable frames")
            continue
        envs = np.array([envelope_from_lpc(a, n_fft, ANALYSIS_SR, SR) for a in fits])
        env = np.median(envs, axis=0)
        env = env / (env.max() or 1.0)

        print(f"\n=== {path.stem} ===")
        print(f"  frames fitted: {len(fits)}")
        res = poles_to_resonances(fits[len(fits) // 2])
        print("  resonance basis (median frame) -- the numbers to twiddle:")
        print(f"    {'freq Hz':>9s} {'bw Hz':>8s} {'gain':>6s}   note")
        for f, b, g in res[:14]:
            note = ""
            if b < 40:
                # Threshold raised from 25 Hz after the HE/PTA donor slipped
                # through at 26.5 Hz: a single narrow pole at 100.9 Hz with
                # gain 1.00 swamped the whole filter and pushed the shaped
                # synth to <200 Hz = 0.76. Structural resonances in a cab run
                # 70-500 Hz wide; anything under ~40 Hz is a captured harmonic.
                note = "NARROW -- captured engine harmonic, widen or drop"
            elif b > 900:
                note = "very broad -- general tilt rather than a resonance"
            print(f"    {f:9.1f} {b:8.1f} {g:6.2f}   {note}")

        # Drive the synth through the measured envelope.
        for rpm in (1000, 1500, 2100):
            raw, _ = engine(rpm, cycles=32, load=0.6)
            shaped = apply_envelope(raw, env)
            tag = f"{path.stem.replace('donor_', '')}_{rpm}"
            write_wav(f"formant_{tag}.wav", shaped)
            if rpm == 1500:
                print(f"  synth through this cab:  {profile_line(shaped)}")
                print(f"  synth with stock filter: {profile_line(raw)}")

    print(f"\nwrote to {OUT}")


if __name__ == "__main__":
    main()
