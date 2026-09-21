"""Diesel startup and shutdown, from the same model as the cruise loops.

Audition only -- imports nothing from freight_fate. Touches no save data.
Writes to C:\\temp\\fftest.

No new synthesis machinery. Startup and shutdown are the cruise engine with a
time-varying RPM and time-varying per-layer gains, which `pulse_train()`
already supports (it takes a per-sample rate array). The interesting content
is entirely in the envelopes.

THE KEY INSIGHT: CRANKING IS THE ENGINE WITH COMBUSTION SWITCHED OFF. The
starter turns the engine over, cylinders compress and pass TDC, but nothing
burns -- so the torque and knock layers are muted and only the block RING
survives. That is the same excitation the jake uses, which makes sense: a
compression release is exactly this minus the release. Three sounds, one
model, distinguished only by which layers are alive.

Startup stages:

  1. Solenoid clack -- the pinion thrown into the flywheel ring gear.
  2. Cranking at 100-200 rpm. Firing rate is RPM/20, so 7.5 Hz at 150 rpm --
     slow enough that you hear individual chuffs rather than a pitch.
  3. UNEVEN cranking. This is what sells it. The starter loads up against
     each compression stroke, so cranking speed surges and drops at the
     compression rate. A steady 150 rpm sounds like a fan; a labouring one
     sounds like a diesel being turned over.
  4. Starter whine. Real numbers here: a truck flywheel ring gear runs
     ~138-150 teeth, so gear mesh sits at `crank_rpm/60 * teeth` -- about
     345 Hz at 150 rpm, climbing as it picks up. A pitched layer, not noise.
  5. Catch. Cylinders come in ONE AT A TIME over a few cycles, not together.
     That brief irregular moment is most of what makes a diesel start sound
     like a diesel start.
  6. Flare and settle. RPM shoots to ~1100, the starter drops out, then it
     drifts back to idle.

Shutdown is startup's mirror with one twist: fuel cuts instantly (torque and
knock to zero within a cycle) while compression continues all the way down,
and the engine stops against a compression stroke it cannot push over --
rocking back slightly. That final stumble is the bit generic shutdown samples
always miss.

Usage: uv run --with numpy --with soundfile python sound-test/engine_start.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pulse_synth
from engine_v1 import (
    BLOCK,
    CYLINDER_SKEW,
    CYLINDER_TRIM,
    FIRING_ORDER,
    KNOCK,
    cab_filter,
    combustion_envelope,
    turbo,
)
from pulse_synth import RNG, SR, bank_ir, grain, pulse_train, smoothstep, write_wav

pulse_synth.OUT = Path(r"C:\temp\fftest")

RING_GEAR_TEETH = 138  # Cummins/Mack-class flywheel; sets the starter whine


def _conv(sig: np.ndarray, ir: np.ndarray) -> np.ndarray:
    """Linear convolution truncated to length. These are one-shots, not loops,
    so the circular version the loop renderer needs would be wrong here."""
    n = 1 << int(np.ceil(np.log2(len(sig) + len(ir))))
    return np.fft.irfft(np.fft.rfft(sig, n) * np.fft.rfft(ir, n), n)[:len(sig)]


def engine_curve(
    rpm: np.ndarray,
    torque_gain: np.ndarray,
    knock_gain: np.ndarray,
    ring_gain: np.ndarray,
    cyl_onset: dict[int, float] | None = None,
    env_rpm: float = 700.0,
) -> np.ndarray:
    """The cruise model driven by curves instead of constants.

    `cyl_onset` maps a cylinder to the time (in seconds) it starts firing, so
    catch can be staggered per cylinder rather than switching the whole engine
    on at once.

    `env_rpm` fixes the combustion pressure envelope at one representative
    speed. Strictly the stroke duration should track instantaneous RPM, but
    re-deriving the envelope per event is expensive and the audible difference
    over a two-second start is small. Flagged rather than hidden.
    """
    n = len(rpm)
    cycle_rate = rpm / 120.0
    press = combustion_envelope(env_rpm)
    t = np.arange(n) / SR

    ring = np.zeros(n)
    torque = np.zeros(n)
    knock = np.zeros(n)
    for slot, cyl in enumerate(FIRING_ORDER):
        trim, skew = CYLINDER_TRIM[cyl], CYLINDER_SKEW[cyl]
        fire = pulse_train(cycle_rate, trim, phase0=slot / 6.0)
        ring += _conv(fire, bank_ir([(f * skew, d, g) for f, d, g in BLOCK]))
        # Per-cylinder catch: this cylinder contributes combustion only after
        # its own onset, ramped over ~1.5 cycles so it fades in rather than
        # appearing.
        gate = 1.0 if cyl_onset is None else smoothstep((t - cyl_onset.get(cyl, 0.0)) / 0.12)
        torque += _conv(fire * gate, press) * trim
        knock += _conv(_conv(fire * gate, grain(0.0035)),
                       bank_ir([(f * skew, d, g) for f, d, g in KNOCK]))

    air = RNG.standard_normal(n) * 0.10 * np.sqrt(np.maximum(rpm, 1.0) / 1500.0)
    body = ring * ring_gain + torque * torque_gain + knock * knock_gain
    return cab_filter(body + air * np.clip(rpm / 600.0, 0.0, 1.5))


def starter(rpm: np.ndarray, gain: np.ndarray) -> np.ndarray:
    """Ring-gear mesh whine, tracking cranking speed.

    Mesh frequency is crank speed times ring-gear teeth -- a real, derivable
    number rather than a tuned one. Harmonics because gear mesh is not a sine,
    plus a little brush/commutator hash on top.
    """
    n = len(rpm)
    mesh = rpm / 60.0 * RING_GEAR_TEETH
    phase = 2 * np.pi * np.cumsum(mesh) / SR
    sig = np.zeros(n)
    for mult, g in ((1.0, 1.0), (2.0, 0.45), (3.0, 0.18)):
        sig += g * np.sin(mult * phase)
    hash_ = RNG.standard_normal(n) * 0.25
    return (sig * 0.5 + hash_) * gain


def crank_rpm(t: np.ndarray, base: float = 150.0, ripple: float = 0.28) -> np.ndarray:
    """Cranking speed, surging against each compression stroke.

    The compression rate is itself RPM/20, so this is mildly self-referential;
    evaluating the ripple at the base speed is close enough and keeps it
    stable. Without this the start sounds like a fan spinning up.
    """
    comp_hz = base / 20.0
    return base * (1.0 - ripple * 0.5 * (1.0 - np.cos(2 * np.pi * comp_hz * t)))


def startup(seconds: float = 4.2, cold: bool = False) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n) / SR
    crank_end = 1.35 if not cold else 2.10
    catch_t = crank_end
    settle = 620.0
    flare = 1150.0 if not cold else 1350.0

    rpm = np.empty(n)
    cranking = t < crank_end
    rpm[cranking] = crank_rpm(t[cranking])
    # Catch: fast rise to the flare, then a slower drift down to idle.
    after = t[~cranking] - catch_t
    rise = smoothstep(after / 0.45)
    fall = smoothstep((after - 0.55) / (1.4 if not cold else 2.4))
    rpm[~cranking] = 150.0 + (flare - 150.0) * rise - (flare - settle) * fall

    # Layer gates.
    ring_gain = np.ones(n)
    combustion = smoothstep((t - catch_t) / 0.10)
    # Cylinders catch one at a time, in firing order, over ~1.5 cycles.
    step = 0.055 if not cold else 0.095
    onsets = {cyl: catch_t + i * step for i, cyl in enumerate(FIRING_ORDER)}

    sig = engine_curve(rpm, combustion, combustion * 1.1, ring_gain,
                       cyl_onset=onsets, env_rpm=settle)

    # Starter: on through cranking, drops out just after catch.
    st_gain = (1.0 - smoothstep((t - (catch_t + 0.18)) / 0.09)) * np.minimum(1.0, t / 0.04)
    sig += 0.30 * starter(rpm, st_gain)

    # Solenoid clack at t=0, and the Bendix kicking out after catch.
    for onset, gain, modes in (
        (0.0, 1.0, [(210.0, 0.020, 1.0), (860.0, 0.008, 0.7), (2400.0, 0.004, 0.4)]),
        (catch_t + 0.22, 0.55, [(180.0, 0.024, 1.0), (700.0, 0.009, 0.6)]),
    ):
        i = int(onset * SR)
        ir = bank_ir(modes)
        sig[i:i + len(ir)] += gain * ir[:max(0, n - i)]

    sig += turbo(n, 900.0, 0.3) * np.clip((rpm - 500.0) / 800.0, 0.0, 1.0)
    return sig


def shutdown(seconds: float = 2.6) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n) / SR
    idle, cut = 620.0, 0.35

    # Coast-down: friction plus pumping losses, dropping away faster at the
    # end as compression dominates. Not linear, and the difference is audible.
    decay = np.clip((t - cut) / 1.5, 0.0, 1.0)
    rpm = np.maximum(idle * (1.0 - decay ** 1.7), 8.0)
    rpm[t < cut] = idle

    # Fuel cut is abrupt -- combustion stops within a cycle. That suddenness
    # is the tell; ramping it sounds like coasting, not shutting off.
    combustion = 1.0 - smoothstep((t - cut) / 0.06)
    sig = engine_curve(rpm, combustion, combustion, np.ones(n), env_rpm=idle)

    # The stumble: the engine stops against a compression stroke it cannot
    # push over and rocks back. One last asymmetric lurch, late and low.
    stop_i = int(np.argmax(rpm <= 20.0)) if (rpm <= 20.0).any() else n - 1
    ir = bank_ir([(38.0, 0.070, 1.0), (96.0, 0.035, 0.55), (260.0, 0.012, 0.25)])
    for off, g in ((0.0, 1.0), (0.115, -0.45), (0.210, 0.16)):
        i = stop_i + int(off * SR)
        if i < n:
            sig[i:i + len(ir)] += g * 0.5 * ir[:max(0, n - i)]
    return sig


def main() -> None:
    print("STARTUP -- cranking is the engine with combustion switched off")
    for tag, cold in (("warm", False), ("cold", True)):
        sig = startup(cold=cold)
        write_wav(f"engine_startup_{tag}.wav", sig)
        print(f"  {tag:5s}  {len(sig) / SR:.2f}s")

    print("\nSTAGE ISOLATION -- to tune each piece by ear")
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    rpm = crank_rpm(t)
    write_wav("engine_start_cranking_only.wav",
              engine_curve(rpm, np.zeros(n), np.zeros(n), np.ones(n)))
    write_wav("engine_start_starter_only.wav",
              starter(rpm, np.minimum(1.0, t / 0.04)))
    print(f"  cranking (no combustion, no starter)   {n / SR:.2f}s")
    print(f"  starter whine alone, mesh {rpm.mean() / 60 * RING_GEAR_TEETH:.0f} Hz")

    print("\nSHUTDOWN -- fuel cuts instantly, compression carries it down")
    sig = shutdown()
    write_wav("engine_shutdown.wav", sig)
    print(f"  {len(sig) / SR:.2f}s")

    print("\nSHIPPED, for A/B:")
    assets = Path(__file__).resolve().parents[1] / "src/freight_fate/assets/sounds/engine"
    try:
        import soundfile as sf
        for name in ("start", "shutdown"):
            d, sr = sf.read(str(assets / f"{name}.ogg"), always_2d=True)
            print(f"  engine/{name}.ogg  {len(d) / sr:.2f}s")
    except Exception:
        pass

    print(f"\nwrote to {pulse_synth.OUT}")


if __name__ == "__main__":
    main()
