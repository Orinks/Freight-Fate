"""Audition prototype: pulse-train synthesis for jake brake, rumble strip, tone ladder.

Scratchpad only -- imports nothing from freight_fate, touches no save data,
writes WAVs to its own directory for auditioning in Reaper.

The shared model is source/filter. A phase accumulator walks a spatial or
crankshaft grid and emits one excitation per event; the excitation runs
through a bank of FIXED resonances. Rate moves with speed or RPM, formants
never move -- which is the whole reason this is synthesized rather than a
pitch-shifted sample.

Every frequency and decay below is a starting guess to be tuned by ear
against a real recording. The STRUCTURE is the claim; the numbers are not.

Usage: uv run python pulse_synth.py
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000
SPEED_OF_SOUND = 343.0
OUT = Path(__file__).resolve().parent / "audition"
RNG = np.random.default_rng(7)  # fixed seed: reruns are byte-identical


# --- plumbing ----------------------------------------------------------------


def write_wav(name: str, mono: np.ndarray, peak: float = 0.85) -> None:
    """Normalize to a target peak and write 16-bit mono."""
    x = np.nan_to_num(mono)
    top = float(np.max(np.abs(x))) or 1.0
    x = x / top * peak
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes((x * 32767).astype("<i2").tobytes())
    print(f"  {name:<40} {len(x) / SR:5.2f}s")


def resonator_ir(freq: float, decay_s: float, gain: float = 1.0) -> np.ndarray:
    """Impulse response of one mode: an exponentially decaying sinusoid."""
    n = int(decay_s * 5 * SR)
    t = np.arange(n) / SR
    return gain * np.exp(-t / decay_s) * np.sin(2 * np.pi * freq * t)


def bank_ir(modes: list[tuple[float, float, float]]) -> np.ndarray:
    """Sum several modes into one impulse response. modes = (freq, decay, gain)."""
    irs = [resonator_ir(f, d, g) for f, d, g in modes]
    n = max(len(ir) for ir in irs)
    out = np.zeros(n)
    for ir in irs:
        out[: len(ir)] += ir
    return out


def convolve(sig: np.ndarray, ir: np.ndarray) -> np.ndarray:
    """FFT convolution, truncated back to the signal length."""
    n = 1 << int(np.ceil(np.log2(len(sig) + len(ir))))
    y = np.fft.irfft(np.fft.rfft(sig, n) * np.fft.rfft(ir, n), n)
    return y[: len(sig)]


def grain(width_s: float = 0.0016) -> np.ndarray:
    """One groove smack: a short broadband burst, not a mathematical impulse."""
    w = max(2, int(width_s * SR))
    return RNG.standard_normal(w) * np.hanning(w)


def pulse_train(
    rate_hz: np.ndarray,
    amp: np.ndarray | float = 1.0,
    phase0: float = 0.0,
) -> np.ndarray:
    """Phase-accumulated impulses with sub-sample placement.

    rate_hz is per-sample, so speed and RPM can sweep. Sub-sample placement
    matters more than it looks: at 75 Hz an impulse quantized to the nearest
    sample carries up to 20 microseconds of jitter, audible as a rasp on top
    of the pitch. Interpolating across the two straddling samples removes it.
    """
    n = len(rate_hz)
    amps = np.full(n, amp, dtype=float) if np.isscalar(amp) else np.asarray(amp, float)
    phase = np.cumsum(rate_hz) / SR + phase0
    out = np.zeros(n + 2)
    hits = np.nonzero(np.floor(phase[1:]) > np.floor(phase[:-1]))[0] + 1
    for i in hits:
        span = phase[i] - phase[i - 1]
        frac = (phase[i] - np.floor(phase[i])) / span if span > 0 else 0.0
        pos = i - frac
        lo = int(np.floor(pos))
        w = pos - lo
        out[lo] += amps[i] * (1.0 - w)
        out[lo + 1] += amps[i] * w
    return out[:n]


def delay(sig: np.ndarray, seconds: float) -> np.ndarray:
    """Shift a signal later in time, keeping the length."""
    d = int(seconds * SR)
    if d <= 0:
        return sig
    return np.concatenate([np.zeros(d), sig[:-d]])


def smoothstep(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# --- 1. jake brake -----------------------------------------------------------

# Exhaust stack: a tonal, metallic filter.
STACK = [
    (95.0, 0.055, 1.00),
    (185.0, 0.040, 0.70),
    (430.0, 0.022, 0.45),
    (900.0, 0.014, 0.28),
    (1750.0, 0.008, 0.15),
]
AIR_RUSH = [(1200.0, 0.010, 1.0), (2600.0, 0.006, 0.6)]


def _jake_from_rate(rate: np.ndarray) -> np.ndarray:
    """Each compression release is a pressure pop plus escaping air."""
    pops = convolve(pulse_train(rate), bank_ir(STACK))
    air = convolve(pulse_train(rate, 0.55), grain(0.004))
    return pops + 0.35 * convolve(air, bank_ir(AIR_RUSH))


def jake(rpm: float, seconds: float = 3.0) -> np.ndarray:
    """Inline-six compression release: 3 events per revolution, f = RPM/20."""
    return _jake_from_rate(np.full(int(seconds * SR), rpm / 20.0))


def jake_engage(rpm: float = 1900.0, seconds: float = 4.0) -> np.ndarray:
    """Engagement clatter, then the buzz sliding down as the truck slows."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    rpm_curve = rpm - (rpm - 1150.0) * smoothstep(t / seconds)
    sig = _jake_from_rate(rpm_curve / 20.0) * np.minimum(1.0, t / 0.05)
    clatter = np.zeros(n)
    for onset, gain in ((0.0, 1.0), (0.018, 0.6), (0.041, 0.35)):
        i = int(onset * SR)
        ir = bank_ir([(320.0, 0.012, 1.0), (1400.0, 0.006, 0.7)])
        clatter[i : i + len(ir)] += gain * ir[: n - i]
    return sig + 0.8 * clatter


# --- 2. rumble strip ---------------------------------------------------------

GROOVE_SPACING_M = 0.30  # milled strip pitch; VERIFY against the real spec

# Fixed resonances: suspension/axle structure, tire cavity, cab panel. Truck
# tires are bigger than car tires so the cavity mode sits lower than the
# ~200 Hz usually quoted for passenger cars.
TRUCK_BODY = [
    (58.0, 0.045, 0.85),
    (128.0, 0.030, 1.00),
    (310.0, 0.016, 0.55),
    (700.0, 0.008, 0.25),
]

# Axles as (distance behind steer axle, tire load weight). The driver sits
# roughly a metre behind the steer axle in a conventional, about 1.5 m up.
DRIVER_BEHIND_STEER_M = 1.0
DRIVER_HEIGHT_M = 1.5

TRUCK_AXLES = [(0.0, 0.55), (6.10, 1.00), (7.35, 1.00), (12.9, 0.80), (14.15, 0.80)]
CAR_AXLES = [(0.0, 1.0), (2.70, 0.9)]


def cab_perspective(dist_behind_steer: float) -> tuple[float, float, float]:
    """What an axle sounds like from the driver's seat.

    Returns (gain, high-frequency keep, propagation delay). Three things
    change with distance back: it gets quieter, it gets duller (air
    absorption plus the trailer shadowing the direct path), and it arrives
    later. The trailer tandems are ~13 m back, so they land about 38 ms
    after the sound leaves them -- small next to the axle timing, but free.

    Gain is a softened inverse-distance law: pure 1/r puts the trailer 18 dB
    down, which is too dead, because a real cab also hears the axles through
    the frame. The 0.7 exponent stands in for that structure-borne path.
    """
    dx = dist_behind_steer - DRIVER_BEHIND_STEER_M
    r = float(np.hypot(dx, DRIVER_HEIGHT_M))
    r_ref = float(np.hypot(-DRIVER_BEHIND_STEER_M, DRIVER_HEIGHT_M))
    gain = (r_ref / r) ** 0.7
    hf_keep = (r_ref / r) ** 0.5
    return gain, hf_keep, r / SPEED_OF_SOUND


def body_ir(hf_keep: float) -> np.ndarray:
    """Resonator bank with the top end rolled off for distant axles."""
    modes = []
    for freq, dec, gain in TRUCK_BODY:
        # Progressively duller the further back the axle sits.
        tilt = 1.0 if freq < 100 else hf_keep ** (1.0 + freq / 400.0)
        modes.append((freq, dec, gain * tilt))
    return bank_ir(modes)


def rumble_steady(speed_ms: float, seconds: float = 6.0) -> np.ndarray:
    """Riding along the strip: every axle on it continuously."""
    n = int(seconds * SR)
    rate = np.full(n, speed_ms / GROOVE_SPACING_M)
    out = np.zeros(n)
    for dist, load in TRUCK_AXLES:
        gain, hf_keep, prop = cab_perspective(dist)
        # Same spatial grid for every axle -- sitting further back is a phase
        # offset in space, which decorrelates the axles the way reality does.
        phase0 = (dist / GROOVE_SPACING_M) % 1.0
        exc = convolve(pulse_train(rate, load, phase0=phase0), grain())
        out += gain * delay(convolve(exc, body_ir(hf_keep)), prop)
    return out


def rumble_lane_change(
    speed_ms: float,
    axles: list[tuple[float, float]],
    lane_change_s: float = 3.0,
    band_w: float = 0.40,
    seconds: float = 5.0,
    label: str = "",
) -> np.ndarray:
    """Crossing the strip: each axle traverses the band in its own time.

    The gap between axles is (distance behind steer) / speed -- that is the
    flurp-flurp. On a tractor-trailer it should spread into three audible
    events out to the trailer tandems, each quieter and duller than the last.
    """
    n = int(seconds * SR)
    t = np.arange(n) / SR
    rate = np.full(n, speed_ms / GROOVE_SPACING_M)
    start_t, band_y = 0.6, 1.70  # strip sits 1.7 m off lane centre
    y_steer = 3.6 * smoothstep((t - start_t) / lane_change_s)
    out = np.zeros(n)
    rows = []
    for dist, load in axles:
        lag = dist / speed_ms
        y = np.interp(t - lag, t, y_steer, left=0.0)
        inside = (y >= band_y) & (y <= band_y + band_w)
        gain, hf_keep, prop = cab_perspective(dist)
        if inside.any():
            rows.append((dist, t[inside][0] + prop, t[inside][-1] - t[inside][0], gain))
        # Soften the edges so a burst never switches on instantaneously.
        env = np.convolve(inside.astype(float), np.hanning(int(0.004 * SR)), "same")
        env /= max(env.max(), 1e-9)
        phase0 = (dist / GROOVE_SPACING_M) % 1.0
        exc = convolve(pulse_train(rate, load * env, phase0=phase0), grain())
        out += gain * delay(convolve(exc, body_ir(hf_keep)), prop)
    if label and rows:
        print(f"    {label}:")
        for dist, onset, dur, gain in rows:
            db = 20 * np.log10(max(gain, 1e-9))
            print(f"      axle {dist:5.2f}m back -> hits {onset:5.3f}s, "
                  f"{dur * 1000:4.0f}ms long, {db:+5.1f} dB at the ear")
    return out


# --- 3. curve tone ladder ----------------------------------------------------


def tone(freq: float, seconds: float = 0.26) -> np.ndarray:
    """One rung: flat pitch, no glide.

    Flat is deliberate. The shipped turn earcons already use pitch CONTOUR to
    mean direction (falling left, rising right), so the ladder has to speak in
    static levels or the two grammars collide.
    """
    n = int(seconds * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    # Two inharmonic partials give a struck-bar character rather than a bare
    # sine, without drifting into bell-like sustain.
    for mult, gain, decay in ((1.0, 1.0, 0.085), (2.76, 0.28, 0.045), (5.40, 0.10, 0.028)):
        sig += gain * np.exp(-t / decay) * np.sin(2 * np.pi * freq * mult * t)
    return sig * np.minimum(1.0, t / 0.002)  # 2 ms attack, no click


# --- render ------------------------------------------------------------------


def main() -> None:
    print("jake brake (f = RPM/20, inline six)")
    for rpm in (1200, 1500, 1800, 2100):
        write_wav(f"jake_{rpm}rpm_{rpm / 20:.0f}hz.wav", jake(rpm))
    write_wav("jake_engage_sweep.wav", jake_engage())

    print("\nrumble strip, steady (riding the edge)")
    for mph in (35, 55, 70):
        ms = mph * 0.44704
        write_wav(f"rumble_steady_{mph}mph_{ms / GROOVE_SPACING_M:.0f}hz.wav",
                  rumble_steady(ms))

    print("\nrumble strip, lane change (per-axle bursts, cab perspective)")
    for mph in (55, 70):
        ms = mph * 0.44704
        write_wav(f"rumble_lanechange_truck_{mph}mph.wav",
                  rumble_lane_change(ms, TRUCK_AXLES, label=f"truck {mph} mph"))
    write_wav("rumble_lanechange_car_65mph.wav",
              rumble_lane_change(65 * 0.44704, CAR_AXLES, label="car 65 mph"))
    write_wav("rumble_lanechange_truck_fast_swerve.wav",
              rumble_lane_change(70 * 0.44704, TRUCK_AXLES, lane_change_s=1.2,
                                 label="truck fast swerve"))

    print("\ncurve tone ladder (flat pitch, one timbre)")
    for name, freq in (("entry_low", 392.0), ("warning_mid", 523.25), ("center_high", 784.0)):
        write_wav(f"tone_{name}_{freq:.0f}hz.wav", tone(freq))
    gap = np.zeros(int(0.45 * SR))
    write_wav("tone_ladder_sequence.wav", np.concatenate([
        tone(523.25), gap, tone(392.0), gap, tone(784.0)]))

    print(f"\nwrote to {OUT}")


if __name__ == "__main__":
    main()
