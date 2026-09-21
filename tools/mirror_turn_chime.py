"""Derive the rising right-turn chime from the falling left-turn chime.

The ElevenLabs sound model reliably produces a falling two-note doorbell
chime but resists prompts for a rising one (see ``events/turn_right`` in
``tools/generate_sounds.py`` for the attempts). So the shipped right cue is
built deterministically from the left cue: split at the quietest gap between
the two notes, swap the note order, and splice with short anti-click fades.
The result is a rising mirror of the left chime in the same voice.

Usage (after regenerating events/turn_left with generate_sounds.py):
    uv run python tools/mirror_turn_chime.py
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "src" / "freight_fate" / "assets" / "sounds" / "events"
SOURCE = EVENTS / "turn_left.ogg"
TARGET = EVENTS / "turn_right.ogg"


def mirror(source: Path, target: Path) -> None:
    x, sr = sf.read(str(source), always_2d=True)
    mono = x.mean(axis=1)
    hop = sr // 100
    count = len(mono) // hop
    env = np.array([np.sqrt(np.mean(mono[i * hop : (i + 1) * hop] ** 2)) for i in range(count)])
    active = np.nonzero(env > env.max() * 0.15)[0]
    if len(active) == 0:
        raise SystemExit(f"{source} appears silent; regenerate it first")
    start, end = int(active[0]), int(active[-1]) + 1
    span = end - start
    lo = start + span // 4
    hi = start + (3 * span) // 4
    mid = lo + int(np.argmin(env[lo:hi])) if hi > lo else (start + end) // 2
    cut = mid * hop

    note1, note2 = x[:cut].copy(), x[cut:].copy()
    fade = min(sr // 200, len(note1) // 4, len(note2) // 4)
    ramp = np.linspace(0.0, 1.0, fade)[:, None]
    for note in (note1, note2):
        note[:fade] *= ramp
        note[-fade:] *= ramp[::-1]

    out = np.concatenate([note2, note1])
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)
    try:
        sf.write(str(wav_path), out, sr)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(wav_path),
                "-c:a",
                "libvorbis",
                "-q:a",
                "5",
                str(target),
            ],
            check=True,
        )
    finally:
        wav_path.unlink()
    print(f"wrote {target}")


if __name__ == "__main__":
    mirror(SOURCE, TARGET)
