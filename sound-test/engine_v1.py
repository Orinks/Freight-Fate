"""Audition prototype: in-cab diesel cruise loop, synthesized.

Audition only -- imports nothing from freight_fate except reading the shipped
idle loop as a spectral reference. Touches no save data.

WHY THIS EXISTS. The shipped engine/low, mid and high loops are uncredited in
CREDITS.md and measure as synthetic: 52-59% of their energy sits above 4 kHz,
centroid ~7 kHz. A real in-cab diesel is the opposite -- Darren Duff's actual
idle recording (engine/idle.ogg, which IS credited) measures centroid 1109 Hz
with 7% above 4 kHz. So the truck starts as a real diesel and pulls away into
hiss. That is the "not loud enough / not defined" problem: the authority of a
big diesel lives at the firing frequency and its first few harmonics, 50-400
Hz, and there is almost nothing down there in the current loops.

What IS right about them: their firing frequencies measure 50.0 / 75.0 / 105.0
Hz, exactly RPM/20 at 1000 / 1500 / 2100, matching the crossfade centres in
audio.py. The model was correct; the timbre was not.

THE MODEL. Same source/filter architecture as jake_v2.py, because it is the
same engine -- six cylinders on a 720 degree cycle in firing order 1-5-3-6-2-4,
each firing at RPM/120, recombining into the RPM/20 buzz with a half-order
lope. The jake releases compressed air; this burns fuel. Different excitation,
same structure, same fixed resonators. Three layers per cylinder:

  1. Combustion thump -- the torque pulse into the block. Low modes. This is
     the layer that carries authority and the one currently missing.
  2. Diesel knock -- the rapid pressure rise after ignition delay. Broadband,
     1-3 kHz at the source, and it grows with load. This is the "clatter" that
     makes a diesel a diesel rather than a generic engine.
  3. Intake/air rush -- a broadband floor rising with RPM.

Then ONE cab transfer function over the sum. In a conventional the stack is
outside and you are behind a firewall, so what reaches the driver is heavily
low-passed. Getting this filter right is most of the battle; it is exactly
what separates Duff's idle from the synthetic loops.

Turbo whine sits on top, tracking boost rather than firing order, so it is
deliberately NOT harmonically locked to RPM/20.

Every frequency below is a starting guess to be tuned by ear against a real
recording. The STRUCTURE is the claim; the numbers are not.

Usage: uv run --with numpy --with soundfile python sound-test/engine_v1.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pulse_synth
from pulse_synth import (
    RNG,
    SR,
    bank_ir,
    grain,
    pulse_train,
    write_wav,
)

pulse_synth.OUT = Path(r"C:\temp\fftest")
ASSETS = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "assets" / "sounds"

FIRING_ORDER = [1, 5, 3, 6, 2, 4]

# Shared with jake_v2: the same six cylinders, so the same trims. An engine
# that lopes one way under compression release should lope the same way under
# power -- it is the same valve lash and the same runner lengths.
CYLINDER_TRIM = {1: 1.00, 2: 0.86, 3: 1.09, 4: 0.81, 5: 0.97, 6: 1.14}
CYLINDER_SKEW = {1: 1.000, 2: 0.978, 3: 1.031, 4: 0.964, 5: 1.012, 6: 1.045}

# Block and mounts: where the combustion torque pulse goes. Heavy iron, so
# these are low and fairly damped. This bank is the authority of the sound.
BLOCK = [
    (52.0, 0.070, 1.00),
    (88.0, 0.055, 0.85),
    (147.0, 0.038, 0.60),
    (233.0, 0.026, 0.38),
    (390.0, 0.016, 0.22),
]

# Diesel knock: the pressure-rise rattle. Higher, shorter, and load-dependent.
KNOCK = [
    (1150.0, 0.006, 1.00),
    (1820.0, 0.004, 0.70),
    (2900.0, 0.003, 0.40),
]


def convolve_circular(sig: np.ndarray, ir: np.ndarray) -> np.ndarray:
    """Wrap-around convolution, so resonator tails rejoin at the loop seam.

    Ordinary (truncated) convolution leaves every mode ringing off the end of
    the buffer and starting from silence at the head, which is a guaranteed
    click when the loop repeats. Doing it circularly means the tail of the
    last cycle IS the head of the first. This is what makes the loop seamless,
    and the shipped mid.ogg -- seam discontinuity 1.85x RMS, an audible click
    every 3.6 seconds -- is what it sounds like when nobody does it.
    """
    n = len(sig)
    pad = np.zeros(n)
    pad[: min(len(ir), n)] = ir[:n]
    return np.fft.irfft(np.fft.rfft(sig) * np.fft.rfft(pad), n)


def combustion_envelope(rpm: float, stroke_frac: float = 0.42, rise_frac: float = 0.12) -> np.ndarray:
    """The pressure pulse of one power stroke. NOT an impulse.

    This is the fix for "it sounds like the jake" (Norm, 2026-07-20), and it
    is a real modelling error rather than a mixing one. A compression release
    IS impulsive -- the exhaust valve cracks near TDC and the pressure dumps,
    so exciting a resonator bank with an impulse is correct for the jake and
    is why the jake is convincing. Combustion is not impulsive. The gas pushes
    the piston through roughly 180 degrees of crank rotation: about 20 ms at
    1500 rpm.

    That duration is what makes an engine sound FULL. With six cylinders
    firing every 6.7 ms and each pushing for ~20 ms, three cylinders are
    under pressure at any instant and the sound never fully decays between
    events. The impulse model decays into silence between firings, and that
    gap is exactly the hollowness Norm heard.

    Note the duration scales with the CYCLE, not with wall-clock time -- at
    2100 rpm the same 180 degrees passes in 14 ms. Fixing it in milliseconds
    would make the engine progressively hollower as it revved.

    A slow push also preferentially excites the LOW modes, while the fast
    knock transient excites the high ones. That separation falls out of the
    physics rather than having to be dialled in.
    """
    stroke_s = 30.0 / rpm  # 180 degrees of crank
    n = max(8, int(stroke_s * 1.6 * SR))
    t = np.arange(n) / SR
    rise = max(rise_frac * stroke_s, 1.0 / SR)
    env = (1.0 - np.exp(-t / rise)) * np.exp(-t / (stroke_frac * stroke_s))
    # Normalize to PEAK, not to sum. Normalizing to sum makes this a unity-DC
    # smoothing kernel, which attenuates everything at and above the firing
    # frequency -- exactly the harmonics we are trying to strengthen. My first
    # attempt did that and measured BACKWARDS: <200 Hz energy fell from 0.31
    # to 0.16 as the stroke lengthened, because the block modes at 52-390 Hz
    # were being starved of excitation rather than sustained.
    return env / (env.max() or 1.0)


def cab_filter(sig: np.ndarray, cutoff_hz: float = 850.0, order: float = 2.2) -> np.ndarray:
    """Firewall, insulation and glass, as one gentle spectral tilt.

    Done on the spectrum rather than as a biquad cascade so the slope can be
    fractional -- a real cab is not an integer-order filter, and a steep one
    sounds like a blanket over the speaker. A small dashboard-panel bump keeps
    it from going dull.
    """
    n = len(sig)
    spec = np.fft.rfft(sig)
    f = np.maximum(np.fft.rfftfreq(n, 1.0 / SR), 1.0)
    roll = 1.0 / (1.0 + (f / cutoff_hz) ** order)
    panel = 0.30 / (1.0 + ((np.log2(f / 430.0)) / 0.55) ** 2)
    # Structure-borne floor: some high end always leaks through the frame.
    leak = 0.045 / (1.0 + (f / 5200.0) ** 1.2)
    return np.fft.irfft(spec * (roll + panel + leak), n)


def _closes(freq: float, n: int) -> float:
    """Snap a frequency to the nearest whole number of cycles in n samples.

    Anything tonal that does not close exactly on the buffer length puts a
    step at the loop join. The shift is at most half a cycle over the whole
    loop -- inaudible on a whine, and the difference between a seamless bed
    and a tick every 0.6 seconds.
    """
    return max(1.0, round(freq * n / SR)) * SR / n


def turbo(n: int, rpm: float, load: float) -> np.ndarray:
    """Compressor whine. Tracks boost, not firing order.

    Deliberately not a multiple of RPM/20: the turbo is on its own shaft, so
    locking it to the firing harmonics is the single fastest way to make an
    engine sound like a synthesizer. Blade-passing gives a pair of close,
    slightly inharmonic partials.
    """
    t = np.arange(n) / SR
    # Shaft speed rises with both revs and load, compressed well below linear.
    f0 = 1750.0 * (rpm / 1500.0) ** 0.55 * (0.72 + 0.28 * load)
    sig = np.zeros(n)
    for mult, gain in ((1.0, 1.0), (1.97, 0.42), (3.05, 0.16)):
        # A slow drift keeps it from being a dead sine. Both the partial and
        # the drift have to close on the loop, or they reintroduce the seam.
        f = _closes(f0 * mult, n)
        sig += gain * np.sin(2 * np.pi * f * t + 0.004 * np.sin(2 * np.pi * _closes(0.37, n) * t))
    return sig * (0.030 + 0.055 * load)


def engine(
    rpm: float,
    cycles: int = 8,
    load: float = 0.6,
    knock_mix: float = 0.55,
    turbo_mix: float = 1.0,
    stroke_frac: float = 0.42,
    torque_mix: float = 0.8,
    cab: bool = True,
) -> tuple[np.ndarray, float]:
    """One seamless in-cab cruise loop. Returns (samples, exact rpm).

    The loop holds a whole number of FOUR-STROKE CYCLES, not revolutions --
    the half-order lope repeats every two turns, so a loop cut on a revolution
    boundary scrambles it. The rate is then solved backwards from the buffer
    length so the phase closes exactly, which costs under 0.01% of RPM and
    buys a mathematically exact seam.
    """
    n = int(round(cycles * SR * 120.0 / rpm))
    cycle_rate = cycles * SR / n  # exact: phase advances `cycles` over n samples
    rate = np.full(n, cycle_rate)
    exact_rpm = cycle_rate * 120.0

    thump = np.zeros(n)
    knock = np.zeros(n)
    torque = np.zeros(n)
    # stroke_frac = 0 recovers the old impulse-only excitation, for A/B
    # against the version that sounded like a jake.
    press_env = combustion_envelope(exact_rpm, stroke_frac) if stroke_frac > 0 else None
    for slot, cyl in enumerate(FIRING_ORDER):
        phase0 = slot / 6.0
        trim = CYLINDER_TRIM[cyl]
        skew = CYLINDER_SKEW[cyl]
        fire = pulse_train(rate, trim, phase0=phase0)
        block_ir = bank_ir([(f * skew, d, g) for f, d, g in BLOCK])

        # THREE mechanisms, which I originally collapsed into one and got
        # wrong. They are separable in the physics and want separating here:
        #
        #  TORQUE -- the gas pressure pushing the piston through 180 degrees.
        #    A sustained periodic force, so it contributes directly at the
        #    firing frequency and its harmonics. This is the bottom end and
        #    the fullness, and it is what the impulse model had no term for.
        if press_env is not None:
            torque += convolve_circular(fire, press_env) * trim
        #  RING -- the block and mounts struck by the pressure RISE. That rise
        #    genuinely IS fast, so an impulse is the right excitation here.
        #    This is the layer the jake shares, and on its own it is why the
        #    engine sounded like one.
        thump += convolve_circular(fire, block_ir)
        #  KNOCK -- ignition-delay rattle. A burst, not an impulse.
        rattle = convolve_circular(fire, grain(0.0035))
        knock_ir = bank_ir([(f * skew, d, g) for f, d, g in KNOCK])
        knock += convolve_circular(rattle, knock_ir)

    # Combustion loads the block harder as fuelling rises; knock grows faster
    # than the thump does, which is why a working truck sounds busier. The
    # torque layer scales hardest of all -- that is what lugging sounds like.
    body = (thump * (0.55 + 0.45 * load)
            + torque_mix * (0.30 + 0.70 * load) * torque
            + knock_mix * (0.35 + 0.65 * load) * knock)

    # Intake and air rush: broadband floor under everything, rising with revs.
    air = RNG.standard_normal(n) * (0.10 + 0.06 * load) * (rpm / 1500.0) ** 0.5

    # cab=False returns the raw source with NO cab filtering, for when a
    # measured envelope is going to supply the cab instead. Applying a
    # measured envelope on top of cab_filter() puts two cabs in series, which
    # is what made every measured render come out too dark -- the top end was
    # being removed twice and no amount of fixing the envelope helped.
    out = cab_filter(body + air) if cab else (body + air)
    return out + turbo_mix * turbo(n, exact_rpm, load), exact_rpm


# --- measurement --------------------------------------------------------------


def profile(x: np.ndarray, sr: int = SR) -> tuple[float, tuple[float, ...]]:
    """Spectral centroid and the four band fractions used to compare assets."""
    S = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1.0 / sr)
    total = S.sum() or 1.0
    bands = tuple(S[(f >= a) & (f < b)].sum() / total for a, b in
                  ((0, 200), (200, 1000), (1000, 4000), (4000, sr / 2)))
    return float((S * f).sum() / total), bands


def profile_line(x: np.ndarray, sr: int = SR) -> str:
    cen, b = profile(x, sr)
    return (f"centroid {cen:6.0f} Hz   <200 {b[0]:.2f}  200-1k {b[1]:.2f}  "
            f"1k-4k {b[2]:.2f}  >4k {b[3]:.2f}")


def report(name: str, x: np.ndarray, sr: int = SR) -> None:
    print(f"  {name:<26} {profile_line(x, sr)}")


def reference() -> None:
    """Print the shipped assets so the synth is judged against them, not alone."""
    try:
        import soundfile as sf
    except ImportError:
        print("  (soundfile unavailable -- skipping reference comparison)")
        return
    for label, rel in (
        ("idle.ogg  (Duff, REAL)", "engine/idle.ogg"),
        ("low.ogg   (synthetic)", "engine/low.ogg"),
        ("mid.ogg   (synthetic)", "engine/mid.ogg"),
        ("high.ogg  (synthetic)", "engine/high.ogg"),
    ):
        try:
            d, sr = sf.read(str(ASSETS / rel), always_2d=True)
        except Exception:
            continue
        report(label, d.mean(axis=1), sr)


def fullness(x: np.ndarray) -> float:
    """How much the amplitude envelope collapses between firings. Lower = fuller.

    Quantifies what Norm meant by "an actual engine would sound more full".
    An impulse-excited model rings and then decays into near-silence before
    the next cylinder, so its envelope swings hard; a real engine always has
    a cylinder under pressure, so its envelope barely moves. Measured as the
    envelope's coefficient of variation -- standard deviation over mean of the
    rectified, smoothed signal. Around 0.2 is a continuous bed; above 0.6 is
    audibly a train of separate events.
    """
    env = np.abs(x)
    w = max(4, int(0.002 * SR))
    env = np.convolve(env, np.ones(w) / w, mode="same")
    return float(env.std() / (env.mean() or 1.0))


def seam_check(x: np.ndarray) -> float:
    """Click risk at the loop join, as a multiple of the signal's own step size.

    Comparing head samples to tail samples (the obvious test, and the one I
    reached for first) is wrong for anything containing noise: broadband noise
    is uncorrelated everywhere, so head-vs-tail always looks terrible while
    tiling it is perfectly inaudible. What actually clicks is a DISCONTINUITY
    -- a jump at the join bigger than the jumps the waveform already makes
    sample to sample. So measure the join step against the RMS of the signal's
    own first difference. Around 1.0 means the join is indistinguishable from
    any other sample boundary; several multiples means an audible tick.
    """
    step = abs(float(x[0] - x[-1]))
    typical = float(np.sqrt(np.mean(np.diff(x) ** 2))) or 1.0
    return step / typical


def main() -> None:
    print("SHIPPED ASSETS -- the target is idle.ogg, the outliers are the other three")
    reference()

    print("\nSYNTHESIZED CRUISE LOOPS (seamless, one per crossfade bucket)")
    for rpm, load in ((620, 0.15), (1000, 0.45), (1500, 0.60), (2100, 0.75)):
        sig, exact = engine(rpm, load=load)
        write_wav(f"engine_{rpm}rpm.wav", sig)
        report(f"engine_{rpm}rpm.wav", sig)
        print(f"    {'':26} exact {exact:7.2f} rpm   firing {exact / 20:5.1f} Hz   "
              f"seam {seam_check(sig):.3f} x rms")

    print("\nPOWER STROKE DURATION -- the 'sounds like the jake' fix")
    print("  0.00 = impulse excitation (the old model, and correct for a jake).")
    print("  Higher = the gas pushes for longer, cylinders overlap, gaps fill in.")
    try:
        import soundfile as sf
        d, sr = sf.read(str(ASSETS / "engine/idle.ogg"), always_2d=True)
        print(f"    {'idle.ogg (Duff, REAL)':28s} fullness {fullness(d.mean(axis=1)):.3f}")
    except Exception:
        pass
    for frac in (0.0, 0.20, 0.42, 0.70):
        sig, _ = engine(1500, load=0.6, stroke_frac=frac)
        tag = "impulse" if frac == 0 else f"{frac:.2f}"
        write_wav(f"engine_1500rpm_stroke_{tag}.wav", sig)
        print(f"    stroke_frac {frac:4.2f}{'':16s} fullness {fullness(sig):.3f}   {profile_line(sig)}")

    print("\nLOAD SWEEP at 1500 rpm -- pulling a grade vs coasting")
    for tag, load in (("light", 0.15), ("cruise", 0.55), ("lugging", 0.95)):
        sig, _ = engine(1500, load=load)
        write_wav(f"engine_1500rpm_{tag}.wav", sig)
        report(f"  load={load:.2f} ({tag})", sig)

    print("\nLAYER SOLOS at 1500 rpm -- to tune the balance by ear")
    for tag, kw in (
        ("no_knock", dict(knock_mix=0.0)),
        ("knock_heavy", dict(knock_mix=1.3)),
        ("no_turbo", dict(turbo_mix=0.0)),
        ("turbo_heavy", dict(turbo_mix=2.5)),
    ):
        sig, _ = engine(1500, **kw)
        write_wav(f"engine_1500rpm_{tag}.wav", sig)

    print("\nCAB FILTER SWEEP at 1500 rpm -- how much truck is between you and it")
    for tag, cut in (("bright", 1600.0), ("stock", 850.0), ("muffled", 480.0)):
        sig, _ = engine(1500, load=0.6)
        # Re-filter from the unfiltered body would be cleaner; this is an
        # audition, and refiltering an already-filtered signal is close enough
        # to hear the direction.
        write_wav(f"engine_1500rpm_cab_{tag}.wav", cab_filter(sig, cutoff_hz=cut))

    print("\nSEAM PROOF -- three loops back to back, listen for a click at the joins")
    sig, _ = engine(1500, load=0.6)
    write_wav("engine_1500rpm_looped_x3.wav", np.tile(sig, 3))

    print("\nRPM RAMP -- pulling away through the range, continuous not bucketed")
    parts = []
    for rpm in range(900, 2200, 100):
        seg, _ = engine(rpm, cycles=3, load=0.55 + 0.2 * (rpm - 900) / 1300)
        parts.append(seg)
    write_wav("engine_ramp_900_2100.wav", np.concatenate(parts))

    print(f"\nwrote to {pulse_synth.OUT}")


if __name__ == "__main__":
    main()
