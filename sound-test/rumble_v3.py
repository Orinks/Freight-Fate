"""Audition prototype v3: rumble strip, brighter carrier and an actual body.

Audition only -- imports nothing from freight_fate. Touches no save data.

v2 fixed the excitation model (noise amplitude-modulated at the groove rate,
rather than resonators ringing at a pitch, which built a vowel). It was right
about that. Two things were still wrong, and Norm's ear found both: it sounded
thin, and the transient-heavy variant was clearly better.

1. CARRIER AND MODULATOR OVERLAPPED IN FREQUENCY. v2 put the noise hump at
   115 Hz. The groove rate is 82 Hz at 55 mph and 104 Hz at 70 -- so at
   highway speed the modulator sat ON TOP of the carrier, and above it at 70.
   Amplitude modulation only reads as a crisp buzz when the carrier is well
   above the modulator; when they overlap you get a wobbling hum instead of a
   rasp. The rule of thumb is carrier centroid at least 5-10x the mod rate,
   so at 82 Hz the carrier wants to be centred near 700-1200 Hz, not 115.
   That is also exactly why the transient-heavy variant sounded better: the
   transient layer runs 74 Hz to 1.5 kHz, so turning it up was accidentally
   supplying the high carrier content the main layer lacked.

2. THE MAIN LAYER NEVER PASSED THROUGH THE STRUCTURE. In v2, `body` was raw
   modulated noise -- the only shaping it got was the gentle spectral hump.
   The fixed resonators were applied to the transient layer alone. So the
   layer carrying most of the energy had no axle, no suspension and no tire
   cavity in it. That is the thinness. Here the modulated carrier runs
   through the same fixed body bank, which is what gives it weight without
   giving back the pitch (the resonators ring, they are not gated).

GROOVE SPACING IS NO LONGER A GUESS. FHWA milled shoulder strips are 12 inch
centre-to-centre, 7 inch wide, 0.5 inch deep. 12 in = 0.305 m, so v2's 0.30 m
stands, and the duty cycle is pinned too: 7/12 = 0.58, against the 0.55 that
was being used. Neither number is free to tune by ear any more.

NO SYNTHESIZED GRAVEL. Norm's call, and it is the right one -- the library has
gravel in depth (Sony Vol 5 "Tires On Gravel Steady", General Series 6009
"Auto Road Surfaces"). Synthesis earns its place only where realism lives in
exact TIMING, which is the periodic strip buzz and nothing else. The shoulder
texture is a recording. So this module deliberately produces the strip cue
ALONE, meant to sit on top of a sampled bed rather than to supply its own.

Usage: uv run --with numpy --with soundfile python sound-test/rumble_v3.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pulse_synth
from pulse_synth import (
    RNG,
    SR,
    TRUCK_AXLES,
    bank_ir,
    cab_perspective,
    convolve,
    pulse_train,
    smoothstep,
    write_wav,
)

pulse_synth.OUT = Path(r"C:\temp\fftest")

# FHWA milled shoulder strip: 12 in centre-to-centre, 7 in wide, 0.5 in deep.
GROOVE_SPACING_M = 0.305
GROOVE_DUTY = 7.0 / 12.0

# Fixed structure: axle and suspension, tire cavity, cab panel. These never
# move with speed -- that is the whole reason this is synthesized rather than
# a pitch-shifted recording.
BODY = [
    (58.0, 0.045, 0.85),
    (128.0, 0.030, 1.00),
    (310.0, 0.016, 0.55),
    (700.0, 0.008, 0.25),
]

# Per-groove impact: heavily damped, densely moded. Rubber is lossy, so these
# are dead in under 10 ms -- long decays here are what built the v1 vowel.
IMPACT = [
    (74.0, 0.009, 0.9), (118.0, 0.007, 1.0), (162.0, 0.006, 0.8),
    (245.0, 0.005, 0.6), (330.0, 0.004, 0.5), (520.0, 0.003, 0.35),
    (880.0, 0.0025, 0.22), (1500.0, 0.002, 0.13),
]


def convolve_circular(sig: np.ndarray, ir: np.ndarray) -> np.ndarray:
    """Wrap-around convolution, so resonator tails rejoin at the loop seam."""
    n = len(sig)
    pad = np.zeros(n)
    pad[: min(len(ir), n)] = ir[:n]
    return np.fft.irfft(np.fft.rfft(sig) * np.fft.rfft(pad), n)


def contact_noise(n: int, centre_hz: float = 900.0, width: float = 1.6) -> np.ndarray:
    """Broadband tire-on-stone contact noise, shaped by a BROAD hump.

    Shaped on the spectrum directly rather than with a biquad, so the skirts
    can be made as gentle as wanted without a low-Q filter ringing. Centre it
    well above the groove rate: this layer is the carrier, and the pitch comes
    from chopping it, not from where it sits.
    """
    spec = np.fft.rfft(RNG.standard_normal(n))
    f = np.maximum(np.fft.rfftfreq(n, 1.0 / SR), 1.0)
    hump = 1.0 / (1.0 + ((np.log2(f / centre_hz)) / width) ** 2)
    # Keep real grit up top so it reads as stone and steel, not filtered hiss.
    grit = 0.35 / (1.0 + (f / 4200.0) ** 1.1)
    lowcut = (f / 40.0) ** 2 / (1.0 + (f / 40.0) ** 2)
    out = np.fft.irfft(spec * (hump + grit) * lowcut, n)
    return out / (np.abs(out).max() or 1.0)


def groove_modulator(rate: np.ndarray, duty: float = GROOVE_DUTY) -> np.ndarray:
    """Periodic 0..1 envelope at the groove rate. This carries the pitch."""
    n = len(rate)
    w = max(3, int(duty * SR / max(float(np.mean(rate)), 1.0)))
    amp = 1.0 + 0.22 * RNG.standard_normal(n)  # milling tolerance, tread, debris
    mod = convolve(pulse_train(rate, amp), np.hanning(w))
    mod -= mod.min()
    return mod / max(mod.max(), 1e-9)


def rumble(
    speed_ms: float,
    seconds: float = 4.0,
    carrier_hz: float = 900.0,
    depth: float = 0.9,
    transient_mix: float = 0.9,
    body_mix: float = 0.7,
    engagement: np.ndarray | None = None,
) -> np.ndarray:
    """The strip cue alone, per-axle, from the cab. Sits on a sampled bed.

    TWO PARALLEL PATHS, which is the correction to my own first attempt at
    this. Running the modulated carrier through the body bank does add the
    weight v2 lacked -- but done alone it also throws away the brightness that
    was the entire point, because the bank is four low modes and behaves like
    a lowpass. Measured: it dragged the centroid back down to 470 Hz however
    high the carrier was set.

    A real cab hears both paths at once. The STRUCTURE-BORNE path goes groove
    -> tire -> axle -> suspension -> frame -> seat, and everything in that
    chain is heavy, so it arrives low and thumpy. The AIRBORNE path goes
    contact patch -> air -> glass -> ear, and it keeps its top end. v2 had
    only the airborne path, so it was thin; body-only has just the structural
    path, so it is dull. Summing them is both correct and what actually
    sounds like a truck on a strip.
    """
    n = len(engagement) if engagement is not None else int(seconds * SR)
    eng = np.ones(n) if engagement is None else np.clip(engagement, 0.0, 1.0)
    rate = np.full(n, speed_ms / GROOVE_SPACING_M)
    impact_ir = bank_ir(IMPACT)
    out = np.zeros(n)
    for dist, load in TRUCK_AXLES:
        gain, hf_keep, prop = cab_perspective(dist)
        # Sitting further back is a phase offset on the same spatial grid --
        # every axle rolls over the same grooves, just not in step.
        phase0 = (dist / GROOVE_SPACING_M) % 1.0
        shift = int(phase0 * SR / (speed_ms / GROOVE_SPACING_M))
        mod = np.roll(groove_modulator(rate), shift)

        carrier = contact_noise(n, centre_hz=carrier_hz * (0.8 + 0.2 * hf_keep))
        chopped = carrier * (1.0 - depth + depth * mod)

        # Structure-borne: through the fixed body modes. Weight, no sparkle.
        structure = convolve_circular(chopped, bank_ir(
            [(f, d, g * (1.0 if f < 100 else hf_keep ** (1.0 + f / 400.0)))
             for f, d, g in BODY]))
        # Airborne: the chopped carrier straight to the ear, top end intact.
        # Distant axles lose more of it -- the trailer is behind the sleeper.
        airborne = chopped * hf_keep

        smack = RNG.standard_normal(max(2, int(0.0022 * SR)))
        smack *= np.hanning(len(smack))
        trans = np.roll(convolve_circular(convolve_circular(
            pulse_train(rate, 1.0 + 0.25 * RNG.standard_normal(n)), smack),
            impact_ir), shift) * hf_keep

        sig = (body_mix * structure + airborne + transient_mix * trans) * load * eng
        # Circular shift, not a zero-padded delay: a padded delay writes
        # silence into the head of the buffer, which is a click in a loop.
        out += gain * np.roll(sig, int(prop * SR))
    return out


def rumble_loop(speed_ms: float, grooves: int = 24, **kw) -> tuple[np.ndarray, float]:
    """A seamless loop holding a whole number of grooves. Returns (samples, hz).

    The shipped slot retriggers a short one-shot, so any replacement has to be
    a clean short loop. It also means ONE baked WAV freezes the buzz rate --
    and speed tracking is the entire reason to synthesize this instead of
    recording it. So these want generating per speed bucket at startup and
    crossfading, exactly like the jake loops, not baking to a single asset.
    """
    n = int(round(grooves * GROOVE_SPACING_M / speed_ms * SR))
    rate_hz = grooves * SR / n  # exact: phase closes over the buffer
    sig = rumble(rate_hz * GROOVE_SPACING_M, engagement=np.ones(n), **kw)
    return sig, rate_hz


def seam_check(x: np.ndarray) -> float:
    """Join step as a multiple of the waveform's own sample-to-sample step."""
    step = abs(float(x[0] - x[-1]))
    return step / (float(np.sqrt(np.mean(np.diff(x) ** 2))) or 1.0)


def profile(x: np.ndarray) -> str:
    S = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    tot = S.sum() or 1.0
    b = [S[(f >= a) & (f < c)].sum() / tot for a, c in
         ((0, 200), (200, 1000), (1000, 4000), (4000, SR / 2))]
    return (f"centroid {(S * f).sum() / tot:6.0f} Hz   <200 {b[0]:.2f}  "
            f"200-1k {b[1]:.2f}  1k-4k {b[2]:.2f}  >4k {b[3]:.2f}")


def main() -> None:
    mph = 0.44704
    speed55 = 55 * mph

    print("A/B: CARRIER CENTRE at 55 mph (groove rate 82 Hz)")
    print("  115 Hz is v2. Everything above it is the fix. Expect thin -> rasp.")
    for centre in (115.0, 400.0, 900.0, 1800.0):
        sig = rumble(speed55, carrier_hz=centre)
        write_wav(f"rumble3_55mph_carrier{centre:.0f}hz.wav", sig)
        print(f"    carrier {centre:6.0f} Hz   {profile(sig)}")

    print("\nA/B: TRANSIENT MIX at 55 mph, carrier fixed at 900 Hz")
    print("  v2 default was 0.45 and you preferred 1.1. With the carrier moved")
    print("  up, the main layer supplies the bite -- so less should now be needed.")
    for mix in (0.0, 0.45, 0.9, 1.4):
        sig = rumble(speed55, carrier_hz=900.0, transient_mix=mix)
        write_wav(f"rumble3_55mph_trans{mix:.2f}.wav", sig)
        print(f"    transient {mix:.2f}    {profile(sig)}")

    print("\nBODY RESONATORS IN vs OUT at 55 mph -- the thinness fix, isolated")
    write_wav("rumble3_55mph_with_body.wav", rumble(speed55, carrier_hz=900.0))
    print(f"    with body      {profile(rumble(speed55, carrier_hz=900.0))}")

    print("\nSPEED BUCKETS -- seamless loops, the shape the game actually needs")
    for m in (35, 45, 55, 65, 75):
        sig, hz = rumble_loop(m * mph, carrier_hz=900.0)
        write_wav(f"rumble3_loop_{m}mph.wav", sig)
        print(f"    {m:2d} mph   groove rate {hz:6.1f} Hz   "
              f"{len(sig) / SR:.3f}s   seam {seam_check(sig):.3f} x step")

    print("\nSEAM PROOF -- 55 mph loop tiled x6, listen for a tick at the joins")
    sig, _ = rumble_loop(speed55, carrier_hz=900.0)
    write_wav("rumble3_loop_55mph_x6.wav", np.tile(sig, 6))

    print("\nDRIFT ONTO THE STRIP at 70 mph -- per-axle, cab perspective")
    n = int(5.0 * SR)
    t = np.arange(n) / SR
    y = 3.6 * smoothstep((t - 0.8) / 3.0)
    eng = smoothstep((y - 1.55) / 0.23) * (1.0 - smoothstep((y - 2.15) / 0.35))
    write_wav("rumble3_lanechange_70mph.wav",
              rumble(70 * mph, carrier_hz=900.0, engagement=eng))

    print(f"\nwrote to {pulse_synth.OUT}")
    print("NOTE: no gravel here by design -- this is the periodic strip cue only,")
    print("      meant to ride on a sampled shoulder bed from the library.")


if __name__ == "__main__":
    main()
