"""Procedural audio asset generator for Freight Fate.

Every sound and music track shipped with the game is synthesized from scratch
by this script, so the entire asset library is original work released under
CC0 (see assets/sounds/CREDITS.md). Run it from the repo root:

    uv run python tools/generate_audio.py [--only PATTERN]

Sound effects are written as 16-bit 44.1 kHz WAV. Music is written as OGG
Vorbis when the ``soundfile`` package is available (it is in the dev group),
otherwise as WAV.

All randomness is seeded, so the output is reproducible.
"""

from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

import numpy as np

SR = 44100
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "freight_fate" / "assets" / "sounds"

rng = np.random.default_rng(0x7261C)


# ---------------------------------------------------------------------------
# Core DSP helpers
# ---------------------------------------------------------------------------

def time_axis(dur: float) -> np.ndarray:
    return np.arange(int(round(dur * SR))) / SR


def sine(freq: float, dur: float, phase: float = 0.0) -> np.ndarray:
    return np.sin(2 * np.pi * freq * time_axis(dur) + phase)


def sine_sweep(f0: float, f1: float, dur: float) -> np.ndarray:
    t = time_axis(dur)
    freqs = np.linspace(f0, f1, t.size)
    phase = 2 * np.pi * np.cumsum(freqs) / SR
    return np.sin(phase)


def saw(freq: float, dur: float, harmonics: int = 24) -> np.ndarray:
    """Band-limited sawtooth via additive synthesis."""
    t = time_axis(dur)
    out = np.zeros_like(t)
    k = 1
    while k <= harmonics and freq * k < SR / 2.2:
        out += np.sin(2 * np.pi * freq * k * t) / k
        k += 1
    return out * (2 / np.pi)


def white(dur: float) -> np.ndarray:
    return rng.standard_normal(int(round(dur * SR)))


def brown(dur: float) -> np.ndarray:
    x = np.cumsum(white(dur))
    x -= np.linspace(x[0], x[-1], x.size)  # remove drift so loops behave
    return x / (np.abs(x).max() + 1e-9)


def fft_gain(x: np.ndarray, gain_fn) -> np.ndarray:
    """Apply a frequency-domain gain curve. gain_fn(freqs_hz) -> gains."""
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(x.size, 1 / SR)
    return np.fft.irfft(spec * gain_fn(freqs), n=x.size)


def lowpass(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    return fft_gain(x, lambda f: 1 / np.sqrt(1 + (f / max(cutoff, 1.0)) ** (2 * order)))


def highpass(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    return fft_gain(x, lambda f: 1 / np.sqrt(1 + (max(cutoff, 1.0) / np.maximum(f, 1e-6)) ** (2 * order)))


def bandpass(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    return lowpass(highpass(x, lo, order), hi, order)


def resonant(x: np.ndarray, center: float, q: float = 8.0) -> np.ndarray:
    """Narrow resonant peak, useful for squeals and whines."""
    def gain(f):
        bw = center / q
        return 1 / (1 + ((f - center) / bw) ** 2)
    return fft_gain(x, gain)


def env_adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    """ADSR envelope over n samples. a/d/r in seconds, s = sustain level."""
    a_n, d_n, r_n = (max(1, int(round(x * SR))) for x in (a, d, r))
    s_n = max(0, n - a_n - d_n - r_n)
    env = np.concatenate([
        np.linspace(0, 1, a_n, endpoint=False),
        np.linspace(1, s, d_n, endpoint=False),
        np.full(s_n, s),
        np.linspace(s, 0, r_n),
    ])
    return env[:n] if env.size >= n else np.pad(env, (0, n - env.size))


def fade(x: np.ndarray, fin: float = 0.005, fout: float = 0.01) -> np.ndarray:
    x = x.copy()
    n_in = min(x.shape[0], max(1, int(round(fin * SR))))
    n_out = min(x.shape[0], max(1, int(round(fout * SR))))
    ramp_in = np.linspace(0, 1, n_in)
    ramp_out = np.linspace(1, 0, n_out)
    if x.ndim == 1:
        x[:n_in] *= ramp_in
        x[-n_out:] *= ramp_out
    else:
        x[:n_in] *= ramp_in[:, None]
        x[-n_out:] *= ramp_out[:, None]
    return x


def normalize(x: np.ndarray, peak: float = 0.89) -> np.ndarray:
    m = np.abs(x).max()
    return x * (peak / m) if m > 0 else x


def soft_clip(x: np.ndarray, drive: float = 1.5) -> np.ndarray:
    return np.tanh(x * drive) / np.tanh(drive)


def seamless(x: np.ndarray, xfade: float = 0.25) -> np.ndarray:
    """Make a loop click-free by crossfading the tail into the head."""
    n = int(round(xfade * SR))
    if n <= 0 or n * 2 >= x.shape[0]:
        return x
    ramp = np.linspace(0, 1, n)
    if x.ndim == 1:
        head = x[:n] * ramp + x[-n:] * (1 - ramp)
        return np.concatenate([head, x[n:-n]])
    head = x[:n] * ramp[:, None] + x[-n:] * (1 - ramp)[:, None]
    return np.concatenate([head, x[n:-n]])


def fft_convolve(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    n = x.size + ir.size - 1
    nfft = 1 << (n - 1).bit_length()
    out = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)
    return out[:n]


def reverb(x: np.ndarray, decay: float = 1.4, mix: float = 0.22, tone: float = 4500.0) -> np.ndarray:
    """Convolution reverb with a synthetic exponentially-decaying noise IR."""
    ir = rng.standard_normal(int(round(decay * SR))) * np.exp(-np.linspace(0, 7, int(round(decay * SR))))
    ir = lowpass(ir, tone)
    ir /= np.abs(ir).sum() ** 0.5
    wet = fft_convolve(x, ir)[: x.size]
    wet = normalize(wet, np.abs(x).max() + 1e-9)
    return x * (1 - mix) + wet * mix


def stereoize(x: np.ndarray, width: float = 0.35, delay_ms: float = 12.0) -> np.ndarray:
    """Mono -> stereo with a short decorrelating delay (Haas effect)."""
    if x.ndim == 2:
        return x
    d = int(round(delay_ms / 1000 * SR))
    left = x
    right = np.concatenate([x[d:], x[:d]])
    mid, side = (left + right) / 2, (left - right) / 2
    return np.stack([mid + side * width, mid - side * width], axis=1)


def pan(x: np.ndarray, pos: float) -> np.ndarray:
    """Constant-power pan. pos in [-1, 1]."""
    theta = (pos + 1) / 2 * np.pi / 2
    return np.stack([x * np.cos(theta), x * np.sin(theta)], axis=1)


def mix_at(canvas: np.ndarray, clip: np.ndarray, start_s: float) -> None:
    i = int(round(start_s * SR))
    j = min(canvas.shape[0], i + clip.shape[0])
    if i >= canvas.shape[0]:
        return
    canvas[i:j] += clip[: j - i]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

written: list[Path] = []


def save_wav(rel: str, x: np.ndarray, peak: float = 0.89) -> None:
    x = normalize(np.asarray(x, dtype=np.float64), peak)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    written.append(path)
    print(f"  {rel}  ({x.shape[0] / SR:.2f}s)")


def save_music(rel_no_ext: str, x: np.ndarray, peak: float = 0.85) -> None:
    x = normalize(np.asarray(x, dtype=np.float64), peak)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    try:
        import soundfile as sf

        path = OUT / (rel_no_ext + ".ogg")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write in chunks: libsndfile's vorbis encoder can overflow the stack
        # when handed multi-minute buffers in a single call on Windows.
        with sf.SoundFile(str(path), "w", SR, 2, format="OGG", subtype="VORBIS") as f:
            step = 65536
            for i in range(0, x.shape[0], step):
                f.write(x[i : i + step])
        written.append(path)
        print(f"  {rel_no_ext}.ogg  ({x.shape[0] / SR:.2f}s)")
    except Exception as e:  # pragma: no cover - fallback path
        print(f"  (soundfile unavailable: {e}; writing WAV)")
        save_wav(rel_no_ext + ".wav", x, peak)


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------

def ks_pluck(freq: float, dur: float, brightness: float = 0.55, seed: int = 0) -> np.ndarray:
    """Karplus-Strong plucked string — warm acoustic-guitar-like tone."""
    n = int(round(dur * SR))
    period = max(2, int(round(SR / freq)))
    local = np.random.default_rng(seed)
    buf = local.uniform(-1, 1, period)
    buf = lowpass(buf, 1200 + 6000 * brightness, order=1)
    out = np.empty(n)
    idx = 0
    blend = 0.5
    for i in range(n):
        out[i] = buf[idx]
        nxt = (idx + 1) % period
        buf[idx] = (buf[idx] * (1 - blend) + buf[nxt] * blend) * 0.996
        idx = nxt
    out *= np.exp(-np.linspace(0, 2.2, n))
    return out


def pad_tone(freq: float, dur: float, detune: float = 0.4) -> np.ndarray:
    """Warm slow-attack pad: three detuned saws through a lowpass."""
    voices = [saw(freq * (1 + c * detune / 100), dur, harmonics=16)
              for c in (-1, 0, 1)]
    x = sum(voices) / 3
    x = lowpass(x, freq * 6 + 400, order=2)
    n = x.size
    env = env_adsr(n, a=min(0.8, dur / 3), d=0.4, s=0.8, r=min(1.2, dur / 3))
    return x * env


def bass_tone(freq: float, dur: float) -> np.ndarray:
    x = sine(freq, dur) + 0.35 * sine(freq * 2, dur) + 0.1 * sine(freq * 3, dur)
    env = env_adsr(x.size, a=0.01, d=0.15, s=0.7, r=min(0.3, dur / 3))
    return soft_clip(x * env, 1.2)


def chime(freq: float, dur: float = 0.6) -> np.ndarray:
    """Bell-like FM chime for UI sounds."""
    t = time_axis(dur)
    mod = np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-t * 8) * 2.0
    x = np.sin(2 * np.pi * freq * t + mod)
    return x * np.exp(-t * 6)


NOTE = {n: 440.0 * 2 ** ((i - 9) / 12) for i, n in enumerate(
    ["C", "Cs", "D", "Ds", "E", "F", "Fs", "G", "Gs", "A", "As", "B"])}


def note(name: str, octave: int) -> float:
    return NOTE[name] * 2 ** (octave - 4)


# ---------------------------------------------------------------------------
# UI sounds
# ---------------------------------------------------------------------------

def gen_ui() -> None:
    print("UI sounds:")
    # menu_move: short soft blip
    x = sine(660, 0.07) * env_adsr(int(round(0.07 * SR)), 0.004, 0.03, 0.4, 0.03)
    save_wav("ui/menu_move.wav", fade(lowpass(x, 4000)), peak=0.5)

    # menu_select: two quick ascending notes
    x = np.zeros(int(round(0.28 * SR)))
    mix_at(x, chime(note("E", 5), 0.18) * 0.8, 0.0)
    mix_at(x, chime(note("A", 5), 0.2) * 0.9, 0.08)
    save_wav("ui/menu_select.wav", fade(x), peak=0.55)

    # menu_back: descending pair
    x = np.zeros(int(round(0.26 * SR)))
    mix_at(x, chime(note("A", 4), 0.16) * 0.8, 0.0)
    mix_at(x, chime(note("E", 4), 0.2) * 0.8, 0.07)
    save_wav("ui/menu_back.wav", fade(x), peak=0.5)

    # menu_open: soft rising swell
    x = sine_sweep(330, 660, 0.25) * env_adsr(int(round(0.25 * SR)), 0.08, 0.05, 0.7, 0.1)
    save_wav("ui/menu_open.wav", fade(lowpass(x, 3000)), peak=0.45)

    # error: low double-buzz
    seg = soft_clip(saw(110, 0.1, harmonics=10), 2.5) * env_adsr(int(round(0.1 * SR)), 0.005, 0.02, 0.8, 0.04)
    x = np.zeros(int(round(0.3 * SR)))
    mix_at(x, seg, 0.0)
    mix_at(x, seg, 0.14)
    save_wav("ui/error.wav", fade(x), peak=0.5)

    # notify: gentle two-tone chime
    x = np.zeros(int(round(0.7 * SR)))
    mix_at(x, chime(note("G", 5), 0.5), 0.0)
    mix_at(x, chime(note("B", 5), 0.55) * 0.7, 0.12)
    save_wav("ui/notify.wav", fade(reverb(x, 0.8, 0.18)), peak=0.5)

    # warning: urgent triple beep
    beep = sine(880, 0.09) * env_adsr(int(round(0.09 * SR)), 0.005, 0.02, 0.9, 0.02)
    x = np.zeros(int(round(0.55 * SR)))
    for k in range(3):
        mix_at(x, beep, k * 0.16)
    save_wav("ui/warning.wav", fade(x), peak=0.6)

    # cash: bright coin ding with sparkle
    x = np.zeros(int(round(0.8 * SR)))
    mix_at(x, chime(note("D", 6), 0.6), 0.0)
    mix_at(x, chime(note("A", 6), 0.5) * 0.5, 0.05)
    sparkle = highpass(white(0.15), 6000) * np.exp(-np.linspace(0, 10, int(round(0.15 * SR)))) * 0.2
    mix_at(x, sparkle, 0.0)
    save_wav("ui/cash.wav", fade(reverb(x, 0.7, 0.15)), peak=0.55)

    # job_complete: short rising arpeggio
    x = np.zeros(int(round(1.4 * SR)))
    for k, (nm, octv) in enumerate([("G", 4), ("B", 4), ("D", 5), ("G", 5)]):
        mix_at(x, chime(note(nm, octv), 0.7) * (0.7 + 0.1 * k), k * 0.11)
    save_wav("ui/job_complete.wav", fade(reverb(x, 1.2, 0.22)), peak=0.6)

    # level_up: bigger fanfare with pad swell
    x = np.zeros(int(round(2.2 * SR)))
    for k, (nm, octv) in enumerate([("C", 4), ("E", 4), ("G", 4), ("C", 5), ("E", 5)]):
        mix_at(x, chime(note(nm, octv), 0.9) * (0.6 + 0.1 * k), k * 0.1)
    mix_at(x, pad_tone(note("C", 3), 1.8) * 0.5, 0.0)
    save_wav("ui/level_up.wav", fade(reverb(x, 1.5, 0.25)), peak=0.62)

    # pause / unpause
    x = sine_sweep(520, 360, 0.16) * env_adsr(int(round(0.16 * SR)), 0.01, 0.04, 0.6, 0.06)
    save_wav("ui/pause.wav", fade(lowpass(x, 3500)), peak=0.45)
    x = sine_sweep(360, 520, 0.16) * env_adsr(int(round(0.16 * SR)), 0.01, 0.04, 0.6, 0.06)
    save_wav("ui/unpause.wav", fade(lowpass(x, 3500)), peak=0.45)

    # typing tick for text feedback
    x = highpass(white(0.03), 2500) * np.exp(-np.linspace(0, 14, int(round(0.03 * SR))))
    save_wav("ui/tick.wav", fade(x, 0.001, 0.01), peak=0.35)


# ---------------------------------------------------------------------------
# Engine sounds
# ---------------------------------------------------------------------------

def engine_cycle_noise(n_samples: int, firing_hz: float, jitter_seed: int) -> np.ndarray:
    """Combustion pulse train with per-cycle amplitude jitter that wraps
    cleanly when the buffer holds an integer number of cycles."""
    t = np.arange(n_samples) / SR
    cycles = int(round(firing_hz * n_samples / SR))
    local = np.random.default_rng(jitter_seed)
    amps = 0.8 + 0.4 * local.random(max(cycles, 1))
    cycle_idx = np.minimum((t * firing_hz).astype(int) % max(cycles, 1), amps.size - 1)
    phase = (t * firing_hz) % 1.0
    pulse = np.exp(-phase * 9.0)  # sharp attack, exponential tail per cycle
    return pulse * amps[cycle_idx]


def engine_loop(rpm: float, dur: float = 4.0, cylinders: int = 6) -> np.ndarray:
    """Diesel truck engine loop at a fixed RPM, seamless."""
    firing = rpm / 60 * cylinders / 2  # four-stroke firing frequency
    # integer cycles per loop for seamlessness
    firing = round(firing * dur) / dur
    n = int(round(dur * SR))
    t = np.arange(n) / SR

    pulses = engine_cycle_noise(n, firing, jitter_seed=int(rpm))

    # Low rumble: harmonics of the firing frequency, decaying spectrum
    rumble = np.zeros(n)
    for k in range(1, 9):
        f = firing * k
        if f > 400:
            break
        rumble += np.sin(2 * np.pi * f * t + k) / (k ** 1.3)
    rumble *= 0.9

    # Combustion roar: brown noise amplitude-modulated by the pulse train
    roar = brown(dur) * (0.25 + pulses * 0.9)
    roar = bandpass(roar, 40, 900 + rpm * 0.4)

    # Mechanical clatter: filtered noise ticks at twice the firing rate
    tick_phase = (t * firing * 2) % 1.0
    clatter = highpass(white(dur), 1500) * np.exp(-tick_phase * 18) * 0.12
    clatter *= min(1.0, rpm / 1500)

    # Turbo whine grows with RPM
    whine = sine(rpm / 60 * 21, dur) * 0.05 * max(0.0, (rpm - 1000) / 1500)

    x = rumble * 0.55 + roar * 0.85 + clatter + whine
    x = soft_clip(x, 1.3)
    x = seamless(x, 0.4)
    return stereoize(x, width=0.25, delay_ms=9)


def gen_engine() -> None:
    print("Engine sounds:")
    for name, rpm in [("idle", 620), ("low", 1000), ("mid", 1500), ("high", 2100)]:
        save_wav(f"engine/{name}.wav", engine_loop(rpm), peak=0.8)

    # start: starter crank into ignition catch and settle
    crank_dur, catch_dur = 1.3, 1.7
    t = time_axis(crank_dur)
    crank_rate = 4.5 + 1.5 * t / crank_dur  # starter motor speeding up
    crank_phase = np.cumsum(crank_rate) / SR
    crank = lowpass(white(crank_dur), 700) * (0.4 + 0.6 * np.exp(-(crank_phase % 1.0) * 6))
    crank += sine(38, crank_dur) * 0.25
    catch = engine_loop(620, catch_dur)[:, 0]
    catch_env = np.linspace(0, 1, catch.size) ** 0.5
    rev_burst = engine_loop(1100, 0.8)[:, 0] * env_adsr(int(round(0.8 * SR)), 0.05, 0.3, 0.4, 0.4)
    x = np.zeros(int((crank_dur + catch_dur) * SR))
    mix_at(x, crank * np.linspace(1, 0.4, crank.size), 0.0)
    mix_at(x, catch * catch_env, crank_dur * 0.85)
    mix_at(x, rev_burst * 0.7, crank_dur * 0.95)
    save_wav("engine/start.wav", fade(stereoize(soft_clip(x, 1.2)), 0.01, 0.3), peak=0.8)

    # rev: quick RPM sweep up and back down
    up = sine_sweep(52, 130, 0.45)
    down = sine_sweep(130, 60, 0.75)
    sweep = np.concatenate([up, down])
    roarn = bandpass(brown(1.2), 50, 1400) * (0.4 + 0.6 * np.abs(sweep))
    x = soft_clip(sweep * 0.6 + roarn, 1.4) * env_adsr(int(round(1.2 * SR)), 0.03, 0.2, 0.8, 0.35)
    save_wav("engine/rev.wav", fade(stereoize(x)), peak=0.8)

    # shutdown: idle dying away with a last shudder
    base = engine_loop(620, 1.8)[:, 0]
    slow = np.interp(np.linspace(0, base.size - 1, int(round(2.4 * SR))) ** 1.04 % base.size,
                     np.arange(base.size), base)
    x = slow * np.linspace(1, 0, slow.size) ** 1.5
    save_wav("engine/shutdown.wav", fade(stereoize(x), 0.01, 0.4), peak=0.7)


# ---------------------------------------------------------------------------
# Vehicle sounds
# ---------------------------------------------------------------------------

def gen_vehicle() -> None:
    print("Vehicle sounds:")
    # gear_shift: mechanical clunk
    thunk = lowpass(white(0.12), 300) * np.exp(-np.linspace(0, 12, int(round(0.12 * SR))))
    click = highpass(white(0.04), 2000) * np.exp(-np.linspace(0, 18, int(round(0.04 * SR)))) * 0.5
    x = np.zeros(int(round(0.25 * SR)))
    mix_at(x, click, 0.0)
    mix_at(x, thunk, 0.02)
    mix_at(x, click * 0.6, 0.09)
    save_wav("vehicle/gear_shift.wav", fade(x), peak=0.6)

    # gear_grind: failed shift
    grind = resonant(white(0.5), 1700, q=4) * env_adsr(int(round(0.5 * SR)), 0.01, 0.1, 0.8, 0.15)
    grind += resonant(white(0.5), 900, q=5) * 0.6
    rattle = (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 31 * time_axis(0.5))))
    save_wav("vehicle/gear_grind.wav", fade(soft_clip(grind * rattle, 2.0)), peak=0.6)

    # air brake: psshhh
    hiss = highpass(white(0.9), 1200) * np.exp(-np.linspace(0, 5, int(round(0.9 * SR))))
    pop = lowpass(white(0.05), 500) * np.exp(-np.linspace(0, 16, int(round(0.05 * SR))))
    x = np.zeros(int(round(0.95 * SR)))
    mix_at(x, pop, 0.0)
    mix_at(x, hiss, 0.03)
    save_wav("vehicle/brake_air.wav", fade(x), peak=0.6)

    # brake_squeal
    sq = resonant(white(1.1), 2900, q=24) * env_adsr(int(round(1.1 * SR)), 0.08, 0.2, 0.75, 0.35)
    sq += resonant(white(1.1), 4400, q=30) * 0.4
    save_wav("vehicle/brake_squeal.wav", fade(sq), peak=0.5)

    # horn: classic two-tone air horn
    dur = 1.3
    a = saw(311, dur, harmonics=18) + saw(311 * 1.002, dur, harmonics=18)
    b = saw(370, dur, harmonics=18) + saw(370 * 0.998, dur, harmonics=18)
    x = bandpass(a + b, 180, 2600)
    x = soft_clip(x, 2.2) * env_adsr(int(round(dur * SR)), 0.03, 0.1, 0.95, 0.18)
    save_wav("vehicle/horn.wav", fade(reverb(x, 1.0, 0.15)), peak=0.8)

    # collision: heavy impact
    boom = lowpass(white(0.8), 150) * np.exp(-np.linspace(0, 9, int(round(0.8 * SR))))
    crash = bandpass(white(0.6), 800, 6000) * np.exp(-np.linspace(0, 11, int(round(0.6 * SR)))) * 0.7
    debris = highpass(white(1.2), 1500) * np.exp(-np.linspace(0, 6, int(round(1.2 * SR)))) * 0.25
    x = np.zeros(int(round(1.4 * SR)))
    mix_at(x, crash, 0.0)
    mix_at(x, boom * 1.2, 0.005)
    mix_at(x, debris, 0.12)
    save_wav("vehicle/collision.wav", fade(soft_clip(x, 1.5), 0.002, 0.3), peak=0.85)

    # tire screech
    sc = resonant(white(1.0), 1300, q=7) + resonant(white(1.0), 2100, q=9) * 0.7
    wob = 1 + 0.25 * np.sin(2 * np.pi * 13 * time_axis(1.0))
    x = sc * wob * env_adsr(int(round(1.0 * SR)), 0.04, 0.15, 0.85, 0.3)
    save_wav("vehicle/tire_screech.wav", fade(x), peak=0.6)

    # fuel pump loop
    glug_rate = 3.2
    t = time_axis(2.0)
    glug = lowpass(white(2.0), 400) * (0.4 + 0.6 * np.exp(-((t * glug_rate) % 1.0) * 7))
    hum = sine(96, 2.0) * 0.18
    x = seamless(glug + hum, 0.3)
    save_wav("vehicle/fuel_pump.wav", x, peak=0.5)

    # truck door
    latch = highpass(white(0.05), 1800) * np.exp(-np.linspace(0, 15, int(round(0.05 * SR))))
    slam = lowpass(white(0.25), 280) * np.exp(-np.linspace(0, 10, int(round(0.25 * SR))))
    x = np.zeros(int(round(0.4 * SR)))
    mix_at(x, latch, 0.0)
    mix_at(x, slam, 0.03)
    save_wav("vehicle/truck_door.wav", fade(x), peak=0.65)

    # turn signal: single relay click (game repeats it)
    click = highpass(white(0.025), 2800) * np.exp(-np.linspace(0, 20, int(round(0.025 * SR))))
    body = lowpass(white(0.03), 900) * np.exp(-np.linspace(0, 16, int(round(0.03 * SR)))) * 0.5
    x = np.zeros(int(round(0.06 * SR)))
    mix_at(x, click, 0.0)
    mix_at(x, body, 0.004)
    save_wav("vehicle/turn_signal.wav", fade(x, 0.001, 0.01), peak=0.4)

    # rumble strip: edge-of-lane warning loop
    t = time_axis(1.0)
    buzz = lowpass(white(1.0), 220) * (0.3 + 0.7 * np.exp(-((t * 18) % 1.0) * 5))
    buzz += sine(55, 1.0) * 0.3
    save_wav("vehicle/rumble_strip.wav", seamless(soft_clip(buzz, 1.6), 0.15), peak=0.6)

    # road noise loop (tires on asphalt)
    base = bandpass(white(4.0), 90, 1100)
    swirl = 0.75 + 0.25 * np.sin(2 * np.pi * 0.6 * time_axis(4.0))
    save_wav("vehicle/road.wav", seamless(stereoize(base * swirl, 0.4), 0.5), peak=0.45)


# ---------------------------------------------------------------------------
# Weather sounds
# ---------------------------------------------------------------------------

def gen_weather() -> None:
    print("Weather sounds:")
    # rain_light: soft patter
    dur = 6.0
    bed = bandpass(white(dur), 1500, 9000) * 0.35
    drops = np.zeros(int(round(dur * SR)))
    local = np.random.default_rng(11)
    for _ in range(140):
        at = local.random() * (dur - 0.05)
        d = highpass(white(0.02), 3000) * np.exp(-np.linspace(0, 22, int(round(0.02 * SR))))
        mix_at(drops, d * (0.2 + 0.5 * local.random()), at)
    x = seamless(stereoize(bed + drops, 0.5), 0.7)
    save_wav("weather/rain_light.wav", x, peak=0.45)

    # rain_heavy: dense downpour with low rumble
    bed = bandpass(white(dur), 700, 11000) * 0.8 + lowpass(brown(dur), 250) * 0.4
    surge = 0.8 + 0.2 * np.sin(2 * np.pi * 0.23 * time_axis(dur))
    x = seamless(stereoize(bed * surge, 0.55), 0.7)
    save_wav("weather/rain_heavy.wav", x, peak=0.6)

    # thunder: deep rolling boom
    n = int(round(4.5 * SR))
    crack = bandpass(white(0.35), 900, 7000) * np.exp(-np.linspace(0, 9, int(round(0.35 * SR))))
    roll = lowpass(brown(4.5), 110) * np.exp(-np.linspace(0, 3.2, n))
    roll *= 1 + 0.5 * np.sin(2 * np.pi * 0.9 * time_axis(4.5) + 1)
    x = np.zeros(n)
    mix_at(x, crack, 0.0)
    x += roll * 1.3
    save_wav("weather/thunder.wav", fade(stereoize(soft_clip(x, 1.3), 0.45), 0.005, 0.8), peak=0.85)

    # wind: broadband whoosh with slow gusts
    dur = 8.0
    t = time_axis(dur)
    gust = 0.45 + 0.3 * np.sin(2 * np.pi * 0.11 * t) + 0.25 * np.sin(2 * np.pi * 0.043 * t + 2)
    body = bandpass(white(dur), 150, 1200) * gust
    whistle = resonant(white(dur), 950, q=11) * (gust ** 2) * 0.4
    x = seamless(stereoize(body + whistle, 0.6), 1.0)
    save_wav("weather/wind.wav", x, peak=0.5)

    # snow_wind: softer, higher, colder
    body = bandpass(white(dur), 400, 2600) * gust * 0.7
    whistle = resonant(white(dur), 1800, q=16) * (gust ** 2) * 0.5
    x = seamless(stereoize(body + whistle, 0.6), 1.0)
    save_wav("weather/snow_wind.wav", x, peak=0.42)

    # fog horn ambience (distant)
    horn = saw(98, 2.2, harmonics=8)
    horn = lowpass(horn, 500) * env_adsr(int(round(2.2 * SR)), 0.3, 0.3, 0.8, 0.8)
    save_wav("weather/fog_horn.wav", fade(reverb(horn, 2.5, 0.5), 0.05, 1.0), peak=0.4)


def gen_ambient() -> None:
    print("Ambient sounds:")
    # truck stop: low hum, distant idles, occasional pass-by whoosh
    dur = 10.0
    hum = lowpass(brown(dur), 130) * 0.5
    distant = lowpass(engine_loop(620, dur)[:, 0], 300) * 0.25
    n = min(hum.size, distant.size)  # engine_loop is shortened by its seamless crossfade
    x = hum[:n] + distant[:n]
    local = np.random.default_rng(23)
    for _ in range(3):
        at = local.random() * (dur - 2.5)
        wlen = 2.2
        envp = np.sin(np.linspace(0, np.pi, int(round(wlen * SR)))) ** 2
        whoosh = bandpass(white(wlen), 200, 1500) * envp * 0.3
        mix_at(x, whoosh, at)
    save_wav("ambient/truck_stop.wav", seamless(stereoize(x, 0.5), 1.0), peak=0.45)

    # warehouse interior: hum + reverberant clanks
    hum = sine(60, dur) * 0.12 + sine(120, dur) * 0.05 + lowpass(white(dur), 400) * 0.1
    x = np.array(hum)
    for _ in range(5):
        at = local.random() * (dur - 1)
        clank = resonant(white(0.3), 1100 + local.random() * 1500, q=14)
        clank *= np.exp(-np.linspace(0, 8, int(round(0.3 * SR))))
        mix_at(x, reverb(clank, 1.8, 0.6) * 0.25, at)
    save_wav("ambient/warehouse.wav", seamless(stereoize(x, 0.5), 1.0), peak=0.4)


# ---------------------------------------------------------------------------
# Music
# ---------------------------------------------------------------------------

def render_track(events: list[tuple[float, np.ndarray, float]], dur: float) -> np.ndarray:
    """events: (start_s, stereo_or_mono_clip, gain)."""
    canvas = np.zeros((int(round(dur * SR)), 2))
    for start, clip, gain in events:
        if clip.ndim == 1:
            clip = np.stack([clip, clip], axis=1)
        mix_at(canvas, clip * gain, start)
    return canvas


def chord_notes(root: str, octave: int, quality: str) -> list[float]:
    semis = {"maj": [0, 4, 7], "min": [0, 3, 7], "sus2": [0, 2, 7], "7": [0, 4, 7, 10]}[quality]
    base = note(root, octave)
    return [base * 2 ** (s / 12) for s in semis]


def gen_menu_theme() -> None:
    """'Headlights West' — warm, unhurried Americana for the main menu."""
    print("Music: menu theme")
    bpm = 72
    beat = 60 / bpm
    bar = beat * 4
    # G - Em - C - D, four times through = 16 bars
    prog = [("G", "maj"), ("E", "min"), ("C", "maj"), ("D", "maj")] * 4
    dur = bar * len(prog)
    events: list[tuple[float, np.ndarray, float]] = []

    # Pads: one chord per bar
    for i, (root, qual) in enumerate(prog):
        at = i * bar
        for j, f in enumerate(chord_notes(root, 3, qual)):
            events.append((at, pad_tone(f, bar * 1.05), 0.16 - 0.02 * j))

    # Bass: root on 1 and 3, fifth on 3 every other bar
    for i, (root, _qual) in enumerate(prog):
        at = i * bar
        rootf = note(root, 2)
        fifth = rootf * 2 ** (7 / 12)
        events.append((at, bass_tone(rootf, beat * 1.8), 0.30))
        events.append((at + beat * 2, bass_tone(fifth if i % 2 else rootf, beat * 1.8), 0.24))

    # Melody: plucked guitar over G major pentatonic, seeded walk
    penta = [note("G", 4), note("A", 4), note("B", 4), note("D", 5), note("E", 5),
             note("G", 5), note("A", 5)]
    local = np.random.default_rng(42)
    idx = 2
    tme = bar * 2  # let the pads breathe first
    while tme < dur - bar:
        step = local.choice([-2, -1, -1, 0, 1, 1, 2])
        idx = int(np.clip(idx + step, 0, len(penta) - 1))
        length = float(local.choice([beat, beat, beat * 2, beat / 2]))
        if local.random() < 0.8:  # rests keep it sparse
            p = ks_pluck(penta[idx], min(2.2, length * 2), brightness=0.6,
                         seed=int(tme * 1000) & 0xFFFF)
            events.append((tme, pan(p, float(local.uniform(-0.3, 0.3))), 0.34))
        tme += length

    x = render_track(events, dur)
    x[:, 0] = reverb(x[:, 0], 1.8, 0.24)
    x[:, 1] = reverb(x[:, 1], 1.8, 0.24)
    x = seamless(x, 1.5)
    save_music("music/menu_theme", x)


def gen_open_road() -> None:
    """'Open Road' — easy mid-tempo groove for long hauls."""
    print("Music: open road")
    bpm = 92
    beat = 60 / bpm
    bar = beat * 4
    # A mixolydian feel: A - G - D - A
    prog = [("A", "maj"), ("G", "maj"), ("D", "maj"), ("A", "maj")] * 6
    dur = bar * len(prog)
    events: list[tuple[float, np.ndarray, float]] = []

    # Bass groove: root - root - fifth - octave pattern per bar
    for i, (root, _qual) in enumerate(prog):
        at = i * bar
        r = note(root, 2)
        pattern = [(0.0, r), (1.0, r), (1.75, r), (2.0, r * 2 ** (7 / 12)), (3.0, r * 2)]
        for off, f in pattern:
            events.append((at + off * beat, bass_tone(f, beat * 0.85), 0.30))

    # Brushed hat: soft noise ticks on eighth notes
    tick = highpass(white(0.04), 5500) * np.exp(-np.linspace(0, 16, int(round(0.04 * SR))))
    n_eighths = int(dur / (beat / 2))
    for k in range(n_eighths):
        g = 0.10 if k % 2 == 0 else 0.05
        events.append((k * beat / 2, tick, g))

    # Pads: sparser, every two bars
    for i in range(0, len(prog), 2):
        root, qual = prog[i]
        at = i * bar
        for j, f in enumerate(chord_notes(root, 3, qual)):
            events.append((at, pad_tone(f, bar * 2.1), 0.10 - 0.015 * j))

    # Lead plucks: call-and-answer phrases on A major pentatonic
    penta = [note("A", 3), note("B", 3), note("Cs", 4), note("E", 4), note("Fs", 4),
             note("A", 4), note("B", 4), note("Cs", 5), note("E", 5)]
    local = np.random.default_rng(7)
    idx = 4
    tme = bar * 4
    while tme < dur - bar * 2:
        # short phrase
        for _ in range(int(local.integers(3, 6))):
            step = local.choice([-2, -1, 0, 1, 2])
            idx = int(np.clip(idx + step, 0, len(penta) - 1))
            length = float(local.choice([beat / 2, beat / 2, beat]))
            p = ks_pluck(penta[idx], min(1.8, length * 2.5), brightness=0.7,
                         seed=int(tme * 1000) & 0xFFFF)
            events.append((tme, pan(p, float(local.uniform(-0.4, 0.4))), 0.30))
            tme += length
        tme += float(local.choice([bar / 2, bar, bar]))  # breathe between phrases

    x = render_track(events, dur)
    x[:, 0] = reverb(x[:, 0], 1.3, 0.18)
    x[:, 1] = reverb(x[:, 1], 1.3, 0.18)
    x = seamless(x, 1.2)
    save_music("music/open_road", x)


def gen_night_haul() -> None:
    """'Night Haul' — slow ambient pads for rainy night driving."""
    print("Music: night haul")
    bar = 4.0
    prog = [("A", "min"), ("F", "maj"), ("C", "maj"), ("G", "maj")] * 4
    dur = bar * len(prog)
    events: list[tuple[float, np.ndarray, float]] = []
    for i, (root, qual) in enumerate(prog):
        at = i * bar
        for j, f in enumerate(chord_notes(root, 3, qual)):
            events.append((at, pad_tone(f, bar * 1.15, detune=0.6), 0.15 - 0.02 * j))
        events.append((at, bass_tone(note(root, 2), bar * 0.9), 0.20))
    # sparse high plucks like distant lights
    local = np.random.default_rng(99)
    penta = [note("A", 5), note("C", 6), note("D", 6), note("E", 6), note("G", 6)]
    tme = bar * 2
    while tme < dur - bar:
        f = float(local.choice(penta))
        p = ks_pluck(f, 2.5, brightness=0.4, seed=int(tme * 977) & 0xFFFF)
        events.append((tme, pan(p, float(local.uniform(-0.6, 0.6))), 0.16))
        tme += float(local.uniform(2.0, 6.0))
    x = render_track(events, dur)
    x[:, 0] = reverb(x[:, 0], 2.6, 0.35, tone=3000)
    x[:, 1] = reverb(x[:, 1], 2.6, 0.35, tone=3000)
    x = seamless(x, 2.0)
    save_music("music/night_haul", x)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

GENERATORS = {
    "ui": gen_ui,
    "engine": gen_engine,
    "vehicle": gen_vehicle,
    "weather": gen_weather,
    "ambient": gen_ambient,
    "menu_theme": gen_menu_theme,
    "open_road": gen_open_road,
    "night_haul": gen_night_haul,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="generate only groups containing this substring")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in GENERATORS.items():
        if args.only and args.only not in name:
            continue
        fn()
    total = sum(p.stat().st_size for p in written)
    print(f"\n{len(written)} files, {total / 1e6:.1f} MB total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
