"""Generate sound-effect assets via the ElevenLabs Sound Effects API.

Build-time only. Reads the ElevenLabs key from an out-of-repo file (or the
ELEVENLABS_API_KEY env var or local ignored .env), requests each effect, and
converts the returned MP3 to the project's Ogg Vorbis convention with ffmpeg.
Never run at runtime and the key is never bundled.

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
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "freight_fate" / "assets" / "sounds"
KEY_FILE = Path.home() / "AI API Keys.txt"
SOUND_API = "https://api.elevenlabs.io/v1/sound-generation"

# key -> (prompt, duration_seconds, prompt_influence)
SPECS: dict[str, tuple[str, float, float]] = {
    "events/hazard_warning": (
        "Short urgent brake warning sound for an audio driving game, loud clear "
        "double beep alert, sharp but not harsh, no speech, no music, no whoosh, "
        "clean, cuts through truck engine noise",
        0.8,
        0.75,
    ),
    "events/police_siren": (
        "A police car siren wailing close behind, urgent up-and-down electronic "
        "yelp and wail, heard from inside a truck cab, no music, clean",
        4.0,
        0.5,
    ),
    "events/cb_radio_chatter": (
        "CB radio squelch burst then a short muffled trucker voice transmission "
        "with static, click off, no music",
        3.0,
        0.4,
    ),
    "events/spike_strip": (
        "Heavy truck tires running over a police spike strip, sharp puncture then "
        "rushing air hiss of a deflating tire, no music",
        3.0,
        0.5,
    ),
    "events/turn_left": (
        "Short quiet non-verbal vehicle navigation earcon leaning left in stereo, "
        "soft two-note chime, under spoken GPS, no words, no voice, no melody",
        0.5,
        0.35,
    ),
    "events/turn_right": (
        "Short quiet non-verbal vehicle navigation earcon leaning right in stereo, "
        "soft two-note chime, under spoken GPS, no words, no voice, no melody",
        0.5,
        0.35,
    ),
    "events/turn_ahead": (
        "Short quiet centered non-verbal vehicle navigation earcon for straight "
        "ahead, soft chime, under spoken GPS, no words, no voice, no melody",
        0.5,
        0.35,
    ),
    "events/hazard_clear": (
        "Very short achievement-style success sound in C major, bright two-note "
        "confirmation ping using C then G, satisfying but subtle, heard in a truck "
        "cab, no whoosh, no melody, clean",
        1.0,
        0.65,
    ),
    "vehicle/air_dryer_purge": (
        "Truck air brake system air dryer purge, a single sharp pneumatic hiss "
        "and pop as the compressor cuts out, heard in the cab, no music",
        2.0,
        0.6,
    ),
    "vehicle/low_air_buzzer": (
        "Truck low air pressure warning buzzer, a steady harsh electronic alarm "
        "buzz on the dash, no music",
        2.5,
        0.6,
    ),
    "traffic/car_pass": (
        "A passenger car passing a truck cab on a highway, brief tire and wind "
        "whoosh from outside, no horn, no voice, no music",
        1.8,
        0.45,
    ),
    "traffic/box_truck_pass": (
        "A medium box truck passing a semi truck cab on a highway, deeper tire "
        "noise and short diesel whoosh, no horn, no voice, no music",
        2.2,
        0.45,
    ),
    "traffic/semi_pass": (
        "A large semi truck passing close by another truck cab on an interstate, "
        "heavy diesel rumble, tire roar, air wash, no horn, no voice, no music",
        2.8,
        0.5,
    ),
    "traffic/trooper_pass": (
        "A state trooper patrol car cruising past a truck cab on the highway, "
        "clean car tire whoosh with a subtle police radio chirp, no siren, no "
        "voice, no music",
        2.0,
        0.45,
    ),
    "vehicle/lane_centered": (
        "Very short calm centered-lane confirmation sound for an audio driving "
        "game, soft two-note dashboard chime, clear and positive but subtle, "
        "heard inside a truck cab, no speech, no music, no whoosh",
        0.9,
        0.75,
    ),
    "vehicle/lane_drift": (
        "Very short lane drift warning beep for an audio driving game, single "
        "clean dashboard beep, clear direction cue when panned left or right, "
        "subtle but easy to hear over truck engine noise, no speech, no music",
        0.5,
        0.75,
    ),
    "vehicle/turn_signal": (
        "Truck turn signal indicator clicking inside a cab, steady dry relay "
        "click-clack pattern, four clicks, close and mechanical, no music, "
        "no voice",
        1.6,
        0.7,
    ),
    "vehicle/tire_screech": (
        "Heavy truck tires screeching hard on asphalt during emergency "
        "braking, short aggressive skid, rubber on pavement, no crash impact, "
        "no music, no voice",
        1.6,
        0.6,
    ),
    "vehicle/brake_squeal": (
        "Overheated semi truck brakes squealing under heavy braking on a long "
        "downgrade, metallic high-pitched squeal with an air brake undertone, "
        "heard from the cab, no music, no voice",
        2.2,
        0.6,
    ),
    "ambient/truck_stop": (
        "Daytime truck stop parking lot ambience, several diesel engines "
        "idling at different distances, an occasional air brake hiss, one "
        "truck passing on the nearby interstate, light wind, a distant door "
        "slam, no voices, no music, steady bed suitable for seamless looping",
        12.0,
        0.4,
    ),
    "ambient/warehouse": (
        "Inside a large busy freight warehouse, big reverberant space, a "
        "forklift beeping and driving past, pallets set down, a distant dock "
        "door rattle, low ventilation hum, no voices, no music, steady bed "
        "suitable for seamless looping",
        12.0,
        0.4,
    ),
}

# Ambience beds loop at runtime; ask the API for a seamless loop when it can.
LOOP_KEYS = {"ambient/truck_stop", "ambient/warehouse"}


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def _api_key() -> str:
    _load_dotenv()
    env = os.environ.get("ELEVENLABS_API_KEY")
    if env:
        return env.strip()
    text = KEY_FILE.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"Eleven Labs:\s*\n\s*\n?\s*(sk_[A-Za-z0-9]+)", text)
    if not m:
        raise SystemExit(f"No ElevenLabs key found in {KEY_FILE}")
    return m.group(1)


def _request_mp3(key: str, payload: dict) -> bytes:
    req = urllib.request.Request(
        SOUND_API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _generate(key: str, spec_key: str, prompt: str, duration: float, influence: float) -> None:
    payload = {
        "text": prompt,
        "duration_seconds": duration,
        "prompt_influence": influence,
        "output_format": "mp3_44100_128",
    }
    if spec_key in LOOP_KEYS:
        payload["loop"] = True
    print(f"  requesting {spec_key} ({duration:.0f}s)...", flush=True)
    try:
        mp3 = _request_mp3(key, payload)
    except urllib.error.HTTPError:
        if "loop" not in payload:
            raise
        # Older API plans reject the loop flag; the prompt still asks for a
        # steady bed, so fall back to a plain generation.
        payload.pop("loop")
        print("    loop flag rejected; retrying without it...", flush=True)
        mp3 = _request_mp3(key, payload)
    out = ASSETS / f"{spec_key}.ogg"
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(mp3)
        tmp_path = tmp.name
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                tmp_path,
                "-c:a",
                "libvorbis",
                "-q:a",
                "5",
                str(out),
            ],
            check=True,
        )
    finally:
        os.unlink(tmp_path)
    print(f"    wrote {out} ({out.stat().st_size:,} bytes)", flush=True)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    wanted = argv or list(SPECS)
    key = _api_key()
    for spec_key in wanted:
        if spec_key not in SPECS:
            raise SystemExit(f"Unknown sound key {spec_key!r}; known: {', '.join(SPECS)}")
        prompt, duration, influence = SPECS[spec_key]
        _generate(key, spec_key, prompt, duration, influence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
