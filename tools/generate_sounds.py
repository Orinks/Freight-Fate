"""Generate sound-effect assets via the ElevenLabs Sound Effects API.

Build-time only. Reads the ElevenLabs key from an out-of-repo file (or the
ELEVENLABS_API_KEY env var), requests each effect, and converts the returned
MP3 to the project's Ogg Vorbis convention with ffmpeg. Never run at runtime and
the key is never bundled.

Usage:
    uv run python tools/generate_sounds.py            # generate the default set
    uv run python tools/generate_sounds.py events/police_siren
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "freight_fate" / "assets" / "sounds"
KEY_FILE = Path.home() / "AI API Keys.txt"
SOUND_API = "https://api.elevenlabs.io/v1/sound-generation"

# key -> (prompt, duration_seconds, prompt_influence)
SPECS: dict[str, tuple[str, float, float]] = {
    "events/police_siren": (
        "A police car siren wailing close behind, urgent up-and-down electronic "
        "yelp and wail, heard from inside a truck cab, no music, clean",
        4.0, 0.5),
    "events/cb_radio_chatter": (
        "CB radio squelch burst then a short muffled trucker voice transmission "
        "with static, click off, no music",
        3.0, 0.4),
    "events/spike_strip": (
        "Heavy truck tires running over a police spike strip, sharp puncture then "
        "rushing air hiss of a deflating tire, no music",
        3.0, 0.5),
    "vehicle/air_dryer_purge": (
        "Truck air brake system air dryer purge, a single sharp pneumatic hiss "
        "and pop as the compressor cuts out, heard in the cab, no music",
        2.0, 0.6),
    "vehicle/low_air_buzzer": (
        "Truck low air pressure warning buzzer, a steady harsh electronic alarm "
        "buzz on the dash, no music",
        2.5, 0.6),
}


def _api_key() -> str:
    env = os.environ.get("ELEVENLABS_API_KEY")
    if env:
        return env.strip()
    text = KEY_FILE.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"Eleven Labs:\s*\n\s*\n?\s*(sk_[A-Za-z0-9]+)", text)
    if not m:
        raise SystemExit(f"No ElevenLabs key found in {KEY_FILE}")
    return m.group(1)


def _generate(key: str, spec_key: str, prompt: str, duration: float,
              influence: float) -> None:
    body = json.dumps({
        "text": prompt,
        "duration_seconds": duration,
        "prompt_influence": influence,
        "output_format": "mp3_44100_128",
    }).encode("utf-8")
    req = urllib.request.Request(
        SOUND_API, data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    print(f"  requesting {spec_key} ({duration:.0f}s)...", flush=True)
    with urllib.request.urlopen(req, timeout=120) as resp:
        mp3 = resp.read()
    out = ASSETS / f"{spec_key}.ogg"
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(mp3)
        tmp_path = tmp.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", tmp_path,
             "-c:a", "libvorbis", "-q:a", "5", str(out)],
            check=True)
    finally:
        os.unlink(tmp_path)
    print(f"    wrote {out} ({out.stat().st_size:,} bytes)", flush=True)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    wanted = argv or list(SPECS)
    key = _api_key()
    for spec_key in wanted:
        if spec_key not in SPECS:
            raise SystemExit(f"Unknown sound key {spec_key!r}; "
                             f"known: {', '.join(SPECS)}")
        prompt, duration, influence = SPECS[spec_key]
        _generate(key, spec_key, prompt, duration, influence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
