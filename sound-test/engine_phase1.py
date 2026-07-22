"""Phase 1 -- a fixed-formant engine VOICE and the in-game MIX around it.

Two things wrong with today's sound, and this addresses both:

  1. The BASS backend plays ONE idle recording and slides its playback
     frequency 1.0x -> 1.75x from 600 to 2200 rpm (audio.py engine_freq_mult).
     Stretching one clip 3x drags every formant up with the pitch, so a big
     diesel turns into a small one as it revs -- Norm's "full engine to micro
     engine". The pygame backend crossfades four loops instead, but three of
     them are thin synthetic loops that sound bad alone.

  2. Nothing is judged in the MIX. In game the engine plays UNDER a road bed
     (vehicle/road at speed/30) and wind, at the category levels engine 0.55,
     road 0.80 (sfx), wind 0.65 (weather). At cruise the road is LOUDER than
     the engine, which is exactly why "in the mix it gets better".

The model here: fixed formants, moving rate. A firing comb (source) is shaped
by the real idle's measured spectral envelope (filter). The rate rides rpm;
the formants never move, so it stays the same size of engine at any rpm. A few
anchor voices across 600-2000 rpm each carry their own timbre (darker at idle,
brighter up top), so the runtime slides each only a little -- "a few formants
to pitch shift", Norm 2026-07-20 -- and the road/wind bed hides the rest.

Reference: C:\\temp\\ffsound\\reference\\idle_647_REAL_interiorized.wav (real
Splice/Blastwave semi idle, transformed into the cab, 647 rpm). Renders go to
C:\\temp\\ffsound\\phase1 -- solos AND in-mix, so the ear judges what the game
actually plays.

Usage: uv run --with numpy --with soundfile python sound-test/engine_phase1.py
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import soundfile as sf

import engine_v1 as E
from pulse_synth import RNG, SR, bank_ir, convolve, grain, pulse_train

# --- paths -------------------------------------------------------------------

REF_DIR = Path(r"C:\temp\ffsound\reference")
OUT_DIR = Path(r"C:\temp\ffsound\phase1")
ASSETS = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "assets" / "sounds"
REF_IDLE = REF_DIR / "idle_647_REAL_interiorized.wav"
ROAD = ASSETS / "vehicle" / "road.ogg"
WIND = ASSETS / "weather" / "wind.ogg"

IDLE_RPM = 647.0

# --- the game's mix levels (audio.py) ----------------------------------------

ENGINE_VOL = 0.55   # _PygameBackend.engine_volume / BASS engine_volume
ROAD_VOL = 0.80     # road loop is CH_ROAD -> "sfx" -> sfx_volume
WIND_VOL = 0.65     # wind loop is CH_WEATHER_B -> "weather" -> weather_volume


def load_gain(throttle: float) -> float:
    """engine_load_gain: 0.68 off-throttle, 1.0 floored (audio.py)."""
    return 0.68 + 0.32 * max(0.0, min(1.0, throttle))


def road_gain(speed_mps: float) -> float:
    """set_road_noise: linear to full at 30 m/s."""
    return min(1.0, speed_mps / 30.0)


def wind_intensity(speed_mps: float) -> float:
    """Clear-day wind rising with speed. An audition knob, not from the sim."""
    return float(np.clip((speed_mps - 8.0) / 42.0, 0.0, 0.75))


# --- measurement (unchanged: confirm every tuning against ground truth) ------

THIRD_OCT = np.array([20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250,
                      315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500,
                      3150, 4000, 5000, 6300.0])
MATCH_LO, MATCH_HI = 200.0, 1000.0


def load_wav(path: Path) -> np.ndarray:
    data, sr = sf.read(str(path), always_2d=True)
    mono = data.mean(axis=1)
    if sr != SR:
        idx = np.linspace(0, len(mono) - 1, int(len(mono) * SR / sr))
        mono = np.interp(idx, np.arange(len(mono)), mono)
    return mono


def band_power(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    S = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    p = S ** 2
    out = np.array([p[(f >= fc / 2 ** (1 / 6)) & (f < fc * 2 ** (1 / 6))].sum()
                    for fc in THIRD_OCT])
    return THIRD_OCT, out, S


def diff_spectrum(synth: np.ndarray, real: np.ndarray) -> np.ndarray:
    fc, ps, _ = band_power(synth)
    _, pr, _ = band_power(real)
    m = (fc >= MATCH_LO) & (fc <= MATCH_HI)
    ps = ps * (pr[m].sum() / (ps[m].sum() or 1.0))
    return 10.0 * np.log10((ps + 1e-12) / (pr + 1e-12))


def show(name: str, synth: np.ndarray, real: np.ndarray) -> np.ndarray:
    d = diff_spectrum(synth, real)
    low = d[(THIRD_OCT >= 40) & (THIRD_OCT <= 160)].mean()
    mid = d[(THIRD_OCT >= 200) & (THIRD_OCT <= 1000)].mean()
    high = d[(THIRD_OCT >= 2500) & (THIRD_OCT <= 5000)].mean()
    boom = d[THIRD_OCT == 100][0]
    print(f"  {name:<24} low{low:+5.1f} mid{mid:+5.1f} 100Hz{boom:+5.1f} high{high:+5.1f}"
          f"   fullness {E.fullness(synth):.2f}")
    return d


def smooth_env(x: np.ndarray, frac_oct: float = 1 / 6) -> tuple[np.ndarray, np.ndarray]:
    """A recording's magnitude envelope, octave-smoothed, as a fixed filter.

    This is the 'record it, then twiddle numbers' step -- the cab colour is
    lifted straight off the real idle instead of guessed. Smoothing in
    fractional octaves keeps the formant shape (the 800 Hz body, the 100 Hz
    dip) while dropping the individual harmonic spikes, so it filters the
    synth's OWN harmonics rather than stamping the recording's pitch onto it.
    """
    S = np.abs(np.fft.rfft(x))
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    out = np.empty_like(S)
    logf = np.log2(np.maximum(f, 1.0))
    for i in range(len(S)):
        m = np.abs(logf - logf[i]) <= frac_oct
        out[i] = S[m].mean()
    return f, out


# --- the engine voice: source (firing comb) / filter (measured cab) ----------

# Diesel knock, gentler than engine_v1's -- the measured filter supplies most
# of the colour, so the source only needs the clatter, not a full resonance.
KNOCK = [(1150.0, 0.006, 1.00), (1820.0, 0.004, 0.55), (2900.0, 0.003, 0.30)]


def excite(rate: np.ndarray, load: np.ndarray, bright: np.ndarray,
           circular: bool, torque_mix: float = 0.8, stroke_frac: float = 0.5,
           air_mix: float = 1.0) -> np.ndarray:
    """Raw source: firing comb + sustained torque push + knock clatter + air.

    NO block resonators baked in -- that was the +18 dB boom at 100 Hz, an
    88 Hz mode piling onto the 97 Hz firing harmonic right where the real idle
    DIPS. Here the comb is close to flat and the measured filter does the
    shaping, so the 100 Hz dip in the real cab actually lands.

    THREE excitation terms, separable in the physics:
      COMB  -- a short 4 ms burst per firing. Broadband, gives harmonics and
               the attack edge. An impulse train alone buzzes ('sounds like
               the jake'); 4 ms gives body without a resonator.
      TORQUE-- the gas pushing the piston through ~180 deg, a slow sustained
               force. This is what fills the 31 ms gap between firings so the
               idle is a bed, not a putt-putt: it takes fullness from ~1.1
               (separate thumps) down toward the real idle's 0.35.
      KNOCK -- ignition-delay clatter, load- and rev-dependent.
    rate is per-sample (per-cylinder cycle rate rpm/120) so this serves both a
    steady loop and a swept pull.
    """
    conv = E.convolve_circular if circular else convolve
    n = len(rate)
    rpm_eq = float(np.median(rate)) * 120.0
    press = E.combustion_envelope(max(rpm_eq, 300.0), stroke_frac=stroke_frac)
    burst = grain(0.004)
    knock_ir = bank_ir(KNOCK)
    comb = np.zeros(n)
    torque = np.zeros(n)
    knock = np.zeros(n)
    for slot, cyl in enumerate(E.FIRING_ORDER):
        trim = E.CYLINDER_TRIM[cyl]
        fire = pulse_train(rate, trim, phase0=slot / 6.0)
        comb += conv(fire, burst) * trim
        torque += conv(fire, press) * trim
        rattle = conv(pulse_train(rate, 0.5, phase0=slot / 6.0), grain(0.003))
        knock += conv(rattle, knock_ir)
    # rate is the per-cylinder CYCLE rate (rpm/120); idle is ~5.4 Hz. Air rush
    # rises with revs, referenced so it sits near unity at idle.
    air = RNG.standard_normal(n) * (0.06 + 0.05 * load) * np.sqrt(np.maximum(rate, 0.1) / 5.39)
    return (torque_mix * torque + comb
            + (0.25 + 0.9 * load) * (0.4 + bright) * knock
            + air_mix * (0.5 + bright) * air)


def shape(raw: np.ndarray, env_f: np.ndarray, env_m: np.ndarray,
          bright: float) -> np.ndarray:
    """Apply the fixed measured filter, with a brightness tilt for high anchors.

    bright lifts the top and lightens the very bottom, standing in for the fact
    that a revving engine opens up -- more knock and turbo reach the ear -- yet
    the FORMANTS (the 800 Hz body) stay put. That is the whole point: pitch
    moves, formants do not.
    """
    n = len(raw)
    S = np.fft.rfft(raw)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    H = np.interp(f, env_f, env_m, left=env_m[0], right=env_m[-1])
    H = H / (H.max() or 1.0)
    if bright:
        tilt = 1.0 + bright * (np.clip((f - 900.0) / 4000.0, 0.0, 1.0)
                               - 0.4 * np.clip((160.0 - f) / 130.0, 0.0, 1.0))
        H = H * tilt
    return np.fft.irfft(S * H, n)


def voice_loop(rpm: float, load: float, env_f, env_m, bright: float = 0.0,
               cycles: int = 12, torque_mix: float = 0.4, stroke_frac: float = 0.5,
               air_mix: float = 2.5) -> np.ndarray:
    """One seamless fixed-formant loop at a steady rpm."""
    # Hold a whole number of four-stroke cycles and solve the rate back from the
    # buffer length, so the firing phase closes exactly and the loop is seamless.
    n = int(round(cycles * SR * 120.0 / rpm))
    # Per-cylinder CYCLE rate (rpm/120): each cylinder fires once per four-stroke
    # cycle, staggered slot/6, so six of them sum to the rpm/20 engine firing.
    rate = np.full(n, cycles * SR / n)
    raw = excite(rate, np.full(n, load), np.full(n, bright), circular=True,
                 torque_mix=torque_mix, stroke_frac=stroke_frac, air_mix=air_mix)
    return shape(raw, env_f, env_m, bright)


def voice_sweep(rpm_curve: np.ndarray, load_curve: np.ndarray,
                env_f, env_m, bright_curve: np.ndarray) -> np.ndarray:
    """A continuous pull: rate follows rpm, formants fixed. One-shot, not looped."""
    raw = excite(rpm_curve / 120.0, load_curve, bright_curve, circular=False)
    # Time-invariant filter = fixed formants. bright varies slowly, so applying
    # its mean tilt over the clip is close enough for an audition; the ear
    # tracks the rate sweep, not a few dB of top over ten seconds.
    return shape(raw, env_f, env_m, float(bright_curve.mean()))


# --- the mix -----------------------------------------------------------------


def bed(path: Path, n: int, seed: int) -> np.ndarray:
    """A looping bed cut to n samples from a real loop, level left intact."""
    src = load_wav(path)
    if len(src) < n:
        src = np.tile(src, int(np.ceil(n / len(src))))
    start = seed % max(1, len(src) - n)
    return src[start:start + n]


def mix(engine: np.ndarray, speed_mps: float, throttle: float) -> np.ndarray:
    """Engine under road + wind at the game's category levels."""
    n = len(engine)
    eng = engine / (np.abs(engine).max() or 1.0)
    e = eng * ENGINE_VOL * load_gain(throttle)
    r = bed(ROAD, n, 4000) * ROAD_VOL * road_gain(speed_mps)
    w = bed(WIND, n, 9000) * WIND_VOL * wind_intensity(speed_mps)
    return e + r + w


def write_raw(name: str, x: np.ndarray, peak: float = 0.9) -> None:
    x = np.nan_to_num(x)
    top = float(np.max(np.abs(x))) or 1.0
    x = x / top * peak
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT_DIR / name), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes((x * 32767).astype("<i2").tobytes())
    print(f"    wrote {name}")


# --- operating points and the audition ---------------------------------------

# rpm -> a plausible top-gear road speed, for the bed level at that point.
POINTS = [
    ("idle", 647, 0.10, 2.0),      # rpm, throttle, m/s
    ("low_1000", 1000, 0.45, 16.0),
    ("cruise_1500", 1500, 0.55, 27.0),
    ("high_1900", 1900, 0.70, 31.0),
]


def brightness_for(rpm: float) -> float:
    return float(np.clip((rpm - 647.0) / 1300.0, 0.0, 1.0)) * 0.7


def main() -> None:
    real = load_wav(REF_IDLE)
    env_f, env_m = smooth_env(real)
    print(f"reference idle {len(real)/SR:.2f}s  fullness {E.fullness(real):.2f}")
    print("filter = real idle's octave-smoothed envelope (fixed formants)\n")

    print("FILL sweep -- steady filtered air fills troughs without re-booming:")
    for tm, am in ((0.4, 1.0), (0.4, 2.5), (0.4, 4.0), (0.8, 2.5), (0.0, 3.5)):
        v = voice_loop(IDLE_RPM, 0.10, env_f, env_m, bright=0.0, torque_mix=tm, air_mix=am)
        show(f"torque {tm} air {am}", v, real)

    print("\nVOICE vs real idle @ 647 rpm (want low~0, 100Hz~0, mid~0, fullness~0.35):")
    idle_voice = voice_loop(IDLE_RPM, 0.10, env_f, env_m, bright=0.0)
    show("new voice (measured)", idle_voice, real)
    base, _ = E.engine(IDLE_RPM, load=0.10)
    show("engine_v1 baseline", base, real)

    def tile_to(x: np.ndarray, secs: float) -> np.ndarray:
        return np.tile(x, int(np.ceil(secs * SR / len(x))))[:int(secs * SR)]

    print("\nSTEADY POINTS -- new voice solo + in mix, and engine_v1 in the same bed:")
    for tag, rpm, thr, spd in POINTS:
        if tag == "idle":
            solo = tile_to(real, 4.0)          # idle ships the REAL sample
        else:
            solo = tile_to(voice_loop(rpm, thr, env_f, env_m, bright=brightness_for(rpm)), 4.0)
        write_raw(f"solo_{tag}.wav", solo)
        write_raw(f"mix_{tag}.wav", mix(solo, spd, thr))
        if tag != "idle":
            # Old voice (engine_v1) in the identical bed, for a clean A/B.
            old, _ = E.engine(rpm, load=thr)
            write_raw(f"mixOLD_{tag}.wav", mix(tile_to(old, 4.0), spd, thr))
        rg, wg = road_gain(spd) * ROAD_VOL, wind_intensity(spd) * WIND_VOL
        eg = ENGINE_VOL * load_gain(thr)
        print(f"    {tag:12} engine {eg:.2f}  road {rg:.2f}  wind {wg:.2f}  "
              f"({'road>engine' if rg > eg else 'engine>road'})")

    print("\nTRANSITION -- real idle, then pull to highway (no micro-engine):")
    fs = SR
    idle_hold = np.tile(real, int(np.ceil(2 * fs / len(real))))[:2 * fs]
    pull_s = 7.0
    n = int(pull_s * fs)
    t = np.arange(n) / fs
    ramp = t / pull_s
    rpm_curve = 647.0 + (1900.0 - 647.0) * ramp
    load_curve = 0.30 + 0.50 * ramp
    speed_curve = 2.0 + (31.0 - 2.0) * ramp
    bright_curve = np.clip((rpm_curve - 647.0) / 1300.0, 0.0, 1.0) * 0.7
    pull = voice_sweep(rpm_curve, load_curve, env_f, env_m, bright_curve)
    # Butt the real idle against the synth pull with a short equal-power dip so
    # the handoff has no click. They share the idle envelope as their filter,
    # so the timbre carries across; only the rate starts moving.
    xf = int(0.4 * fs)
    fade = np.linspace(0, 1, xf)
    engine_line = np.concatenate([idle_hold, pull])
    engine_line[2 * fs - xf:2 * fs] *= np.cos(fade * np.pi / 2)   # idle tail out
    engine_line[2 * fs:2 * fs + xf] *= np.sin(fade * np.pi / 2)   # pull head in
    # build the bed along the whole line
    full_n = len(engine_line)
    speed_full = np.concatenate([np.full(2 * fs, 2.0), speed_curve])
    thr_full = np.concatenate([np.full(2 * fs, 0.10), load_curve])
    e = engine_line / (np.abs(engine_line).max() or 1.0)
    eg = ENGINE_VOL * (0.68 + 0.32 * thr_full)
    rg = ROAD_VOL * np.clip(speed_full / 30.0, 0, 1)
    wg = WIND_VOL * np.clip((speed_full - 8) / 42.0, 0, 0.75)
    r = bed(ROAD, full_n, 4000)
    w = bed(WIND, full_n, 9000)
    transition = e * eg + r * rg + w * wg
    write_raw("transition_idle_to_highway_MIX.wav", transition)
    write_raw("transition_idle_to_highway_SOLO.wav", engine_line)

    print("\nANCHOR SLIDE distortion (how far each anchor pitch-shifts):")
    centers = [647, 1000, 1500, 1900]
    for i, c in enumerate(centers):
        lo = centers[i - 1] if i else c
        hi = centers[i + 1] if i + 1 < len(centers) else c
        span_lo = (lo + c) / 2 / c if i else 600 / c
        span_hi = (hi + c) / 2 / c if i + 1 < len(centers) else 2200 / c
        print(f"    anchor {c:5} rpm covers ~{span_lo:.2f}x..{span_hi:.2f}x "
              f"(max formant shift {max(abs(1-span_lo), abs(1-span_hi))*100:.0f}%)")

    print(f"\nwrote to {OUT_DIR}")


if __name__ == "__main__":
    main()
