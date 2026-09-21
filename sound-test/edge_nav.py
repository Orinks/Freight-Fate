"""Audition prototype: the graded edge boundary for curve navigation.

Scratchpad only -- imports nothing from freight_fate, touches no save data.
Builds on pulse_synth.py (same directory) for the source/filter machinery.

Three boundary states, distinguished by STRUCTURE rather than volume, so
they stay separable under engine and road noise:

    clipping the strip   intermittent -- only some grooves catch
    fully on the strip   periodic     -- a pitched buzz
    out on the shoulder  aperiodic    -- crunch, no pitch at all

One mechanism the whole way: the same tire hitting things at a rising rate
with rising randomness. Everything is stereo, because which SIDE the sound
comes from is the instruction -- hear it right, steer left.

Usage: uv run python edge_nav.py
"""

from __future__ import annotations

import wave

import numpy as np
from pulse_synth import (
    GROOVE_SPACING_M,
    OUT,
    RNG,
    SR,
    TRUCK_AXLES,
    body_ir,
    cab_perspective,
    convolve,
    delay,
    grain,
    pulse_train,
    smoothstep,
)

# Lateral geometry, metres from lane centre. The strip sits just inside the
# fog line; past it the pavement ends.
CLIP_Y = 1.55  # tire's outer edge starts catching grooves
FULL_Y = 1.78  # whole tire on the strip
SHOULDER_Y = 2.15  # off the pavement, into gravel


def write_stereo(name: str, left: np.ndarray, right: np.ndarray, peak: float = 0.85) -> None:
    n = min(len(left), len(right))
    stereo = np.stack([np.nan_to_num(left[:n]), np.nan_to_num(right[:n])], axis=1)
    top = float(np.max(np.abs(stereo))) or 1.0
    stereo = stereo / top * peak
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes((stereo * 32767).astype("<i2").tobytes())
    print(f"  {name:<42} {n / SR:5.2f}s")


def strip_texture(speed_ms: float, engagement: np.ndarray) -> np.ndarray:
    """Tire on the milled strip, summed over axles from the cab's seat.

    `engagement` runs 0..1: below 1 the tire is only clipping the grooves, so
    individual hits drop out at random rather than merely getting quieter.
    That intermittency is what makes 'clipping' audibly a different STATE
    instead of a softer version of the same one.
    """
    n = len(engagement)
    rate = np.full(n, speed_ms / GROOVE_SPACING_M)
    out = np.zeros(n)
    for dist, load in TRUCK_AXLES:
        gain, hf_keep, prop = cab_perspective(dist)
        phase0 = (dist / GROOVE_SPACING_M) % 1.0
        # Each groove either catches or it does not; probability rises with
        # engagement, so partial contact reads as a ragged, stuttering rumble.
        catch = (RNG.random(n) < np.clip(engagement, 0.0, 1.0) ** 0.6).astype(float)
        amp = load * catch * (0.35 + 0.65 * np.clip(engagement, 0.0, 1.0))
        exc = convolve(pulse_train(rate, amp, phase0=phase0), grain())
        out += gain * delay(convolve(exc, body_ir(hf_keep)), prop)
    return out


def gravel_texture(speed_ms: float, amount: np.ndarray) -> np.ndarray:
    """Loose shoulder: dense random impacts, deliberately with no periodicity.

    Aperiodic is the whole point -- it is the one boundary state that carries
    no pitch, so it can never be mistaken for the strip.
    """
    n = len(amount)
    # Impact density scales with speed; the result is noise, not a pulse train.
    noise = RNG.standard_normal(n) * np.clip(amount, 0.0, 1.0)
    noise *= 0.6 + 0.4 * (speed_ms / 30.0)
    body = convolve(noise, body_ir(0.85))
    # A little grit on top so it reads as stones, not just filtered rumble.
    grit = convolve(noise * RNG.standard_normal(n), grain(0.0009))
    return body + 0.30 * grit


def edge_state(y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Split lateral offset into strip engagement and gravel amount."""
    engagement = smoothstep((y - CLIP_Y) / (FULL_Y - CLIP_Y))
    gravel = smoothstep((y - SHOULDER_Y) / 0.35)
    # Once you are properly off the pavement the strip is behind you.
    return engagement * (1.0 - 0.85 * gravel), gravel


def pan(sig: np.ndarray, side: float) -> tuple[np.ndarray, np.ndarray]:
    """Constant-power pan. side = -1 hard left, +1 hard right."""
    theta = (np.clip(side, -1.0, 1.0) + 1.0) * 0.25 * np.pi
    return sig * np.cos(theta), sig * np.sin(theta)


def render(y: np.ndarray, speed_ms: float, side: float) -> tuple[np.ndarray, np.ndarray]:
    engagement, gravel = edge_state(y)
    sig = strip_texture(speed_ms, engagement) + 1.15 * gravel_texture(speed_ms, gravel)
    return pan(sig, side)


def ramp(seconds: float, y_from: float, y_to: float) -> np.ndarray:
    t = np.linspace(0.0, 1.0, int(seconds * SR))
    return y_from + (y_to - y_from) * t


def hold(seconds: float, y: float) -> np.ndarray:
    return np.full(int(seconds * SR), y)


def main() -> None:
    speed = 62 * 0.44704

    print("boundary states, held (right side)")
    for name, y in (("clipping", 1.62), ("full_strip", 1.85), ("shoulder_gravel", 2.40)):
        left, right = render(hold(3.0, y), speed, side=+1.0)
        write_stereo(f"edge_{name}_right.wav", left, right)

    print("\nboundary states, held (left side -- for the pan check)")
    left, right = render(hold(3.0, 1.85), speed, side=-1.0)
    write_stereo("edge_full_strip_left.wav", left, right)

    print("\nrunning wide then recovering")
    # The gesture that matters: drift out, hear it escalate on the side you
    # are drifting toward, correct, and return to silence. Silence is centred.
    y = np.concatenate([
        hold(1.2, 1.20),              # tracking the arc, nothing to hear
        ramp(1.8, 1.20, 1.92),        # running wide, onto the strip
        hold(0.8, 1.92),              # sitting on it
        ramp(1.6, 1.92, 1.10),        # correcting back in
        hold(1.4, 1.10),              # centred again, silent
    ])
    left, right = render(y, speed, side=+1.0)
    write_stereo("edge_drift_and_recover_right.wav", left, right)

    print("\nover-correcting across to the other edge")
    y_r = np.concatenate([hold(0.8, 1.20), ramp(1.4, 1.20, 1.88), hold(0.6, 1.88),
                          ramp(1.2, 1.88, 1.20), hold(1.0, 1.20)])
    y_l = np.concatenate([hold(0.8, 1.20), hold(1.4, 1.20), hold(0.6, 1.20),
                          ramp(1.2, 1.20, 1.20), ramp(1.0, 1.20, 1.90)])
    lr, rr = render(y_r, speed, side=+1.0)
    ll, rl = render(y_l, speed, side=-1.0)
    n = min(len(lr), len(ll))
    write_stereo("edge_overcorrect_right_then_left.wav", lr[:n] + ll[:n], rr[:n] + rl[:n])

    print("\nall the way off the pavement")
    y = np.concatenate([hold(0.8, 1.20), ramp(2.2, 1.20, 2.55), hold(1.6, 2.55),
                        ramp(1.8, 2.55, 1.15), hold(0.8, 1.15)])
    left, right = render(y, speed, side=+1.0)
    write_stereo("edge_off_onto_shoulder_right.wav", left, right)

    print(f"\nwrote to {OUT}")


if __name__ == "__main__":
    main()
