"""Generate in-cab radio music, host segments, and static via ElevenLabs.

Build-time only, like generate_sounds.py. Reads the ElevenLabs key from an
out-of-repo file (or ELEVENLABS_API_KEY / local ignored .env), composes
station music with the Eleven Music API, voices the Freight Fate Roadhouse
and Night Line hosts with the TTS API, and writes the project's Ogg Vorbis
convention with ffmpeg. The static burst is procedural (numpy) and costs no
credits. Never run at runtime; the key is never bundled.

Usage:
    uv run python tools/generate_radio.py                # everything
    uv run python tools/generate_radio.py --hosts        # host lines only
    uv run python tools/generate_radio.py --music        # music only
    uv run python tools/generate_radio.py --static       # static burst only
    uv run python tools/generate_radio.py radio_country_backroads
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_sounds import ASSETS, _api_key  # noqa: E402

MUSIC_API = "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128"
TTS_API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
VOICES_API = "https://api.elevenlabs.io/v1/voices"

# key -> (prompt, length_ms, force_instrumental)
MUSIC_SPECS: dict[str, tuple[str, int, bool]] = {
    # Country pool: fictional heartland stations
    "radio_country_backroads": (
        "Modern outlaw country song about driving a semi truck down two-lane "
        "backroads at sunrise, warm male vocals, telecaster twang, steady "
        "trucker shuffle beat, radio-friendly mix",
        150_000,
        False,
    ),
    "radio_country_two_lane": (
        "Easygoing classic country song about small towns rolling past a "
        "truck window, gentle male vocals, pedal steel guitar, brushed drums, "
        "warm nostalgic AM radio feel",
        150_000,
        False,
    ),
    "radio_country_diesel_heart": (
        "Upbeat country rock song about a diesel engine and the open "
        "interstate, confident female vocals, fiddle and electric guitar, "
        "driving rhythm, modern country radio sound",
        150_000,
        False,
    ),
    # Classic rock pool: city rock stations
    "radio_rock_open_throttle": (
        "Classic rock anthem about hauling freight through the night, "
        "gritty male vocals, crunchy electric guitars, driving drums, "
        "seventies highway rock energy, radio mix",
        150_000,
        False,
    ),
    "radio_rock_night_shift": (
        "Mid-tempo classic rock song about working the night shift on the "
        "road, soulful male vocals, hammond organ and electric guitar, "
        "steady groove, FM rock radio feel",
        150_000,
        False,
    ),
    "radio_rock_chrome_horizon": (
        "Melodic heartland rock song about chrome wheels and a wide open "
        "horizon, earnest male vocals, jangly guitars, big chorus, "
        "eighties arena rock radio sound",
        150_000,
        False,
    ),
    # Blues and soul pool: southern stations
    "radio_blues_delta_mile": (
        "Slow electric delta blues song about one more mile before home, "
        "weathered male vocals, slide guitar, sparse drums, late evening "
        "juke joint atmosphere",
        150_000,
        False,
    ),
    "radio_blues_crossroad_coffee": (
        "Warm soul blues song about coffee at a crossroads diner, smooth "
        "female vocals, horns and electric piano, laid back groove, "
        "southern soul radio feel",
        150_000,
        False,
    ),
    # Extra late-night bed for the Night Line rotation
    "radio_night_low_beams": (
        "Slow instrumental late night jazz for empty interstate driving, "
        "muted trumpet, soft brushed drums, upright bass, sparse electric "
        "piano, lonely and calm, no vocals",
        180_000,
        True,
    ),
}

# Roadhouse: warm gravelly daytime trucker DJ. Night Line: calm late-night voice.
HOST_VOICE_PREFERENCES = {
    "roadhouse": ("Brian", "Bill", "George", "Adam", "Daniel"),
    "nightline": ("Matilda", "Alice", "Sarah", "Rachel", "Charlotte"),
}

HOST_LINES: dict[str, tuple[str, ...]] = {
    "roadhouse": (
        "You're rolling with the Freight Fate Roadhouse, coast to coast, "
        "wherever the load takes you. Keep it between the lines, driver.",
        "That rig of yours sounds hungry for miles. More music coming right up on the Roadhouse.",
        "This one goes out to everybody staring down a long white line this "
        "morning. Hammer down, stay safe.",
        "Roadhouse radio, friend of the working driver. Check your mirrors, "
        "check your coffee, and roll on.",
        "If you're hauling through weather out there, take her slow. The "
        "Roadhouse will keep you company all the way.",
        "From the yard to the receiver and every mile between, this is the "
        "Freight Fate Roadhouse. Back to the music.",
    ),
    "nightline": (
        "This is the Night Line. Just you, me, and a few hundred miles of quiet highway.",
        "For every driver watching the small hours roll past the "
        "windshield, stay sharp out there. The Night Line's with you.",
        "You're on the Night Line, playing it slow and low until the sun finds you.",
        "If your eyes are getting heavy, find some parking and let the bunk "
        "win. The music will still be here.",
        "Somewhere out there a reefer hums in a dark lot and the coffee's "
        "gone cold. This one's for the long haul.",
        "Night Line time. Dim the dash lights, ease your shoulders, and let the miles pour.",
    ),
}


def _post_bytes(url: str, key: str, body: dict, timeout: int = 600) -> bytes:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "xi-api-key": key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _write_ogg(mp3: bytes, out: Path) -> None:
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


def _pick_voice(key: str, station: str) -> tuple[str, str]:
    req = urllib.request.Request(VOICES_API, headers={"xi-api-key": key})
    with urllib.request.urlopen(req, timeout=60) as resp:
        voices = json.load(resp).get("voices", [])
    by_name = {v.get("name", ""): v.get("voice_id", "") for v in voices}
    for name in HOST_VOICE_PREFERENCES[station]:
        if by_name.get(name):
            return name, by_name[name]
    if voices:
        v = voices[0]
        return v.get("name", "unknown"), v.get("voice_id", "")
    raise SystemExit("No ElevenLabs voices available on this account")


def generate_music(key: str, wanted: list[str]) -> None:
    for spec_key in wanted:
        prompt, length_ms, instrumental = MUSIC_SPECS[spec_key]
        print(f"  composing {spec_key} ({length_ms / 1000:.0f}s)...", flush=True)
        body = {
            "prompt": prompt,
            "music_length_ms": length_ms,
            "model_id": "music_v1",
            "force_instrumental": instrumental,
        }
        try:
            mp3 = _post_bytes(MUSIC_API, key, body)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:300]
            print(f"    FAILED {spec_key}: HTTP {exc.code} {detail}", flush=True)
            continue
        _write_ogg(mp3, ASSETS / "music" / f"{spec_key}.ogg")


def generate_hosts(key: str) -> None:
    for station, lines in HOST_LINES.items():
        name, voice_id = _pick_voice(key, station)
        print(f"  {station} host voice: {name}", flush=True)
        for i, line in enumerate(lines, start=1):
            out = ASSETS / "music" / f"host_{station}_{i:02d}.ogg"
            print(f"  speaking host_{station}_{i:02d}...", flush=True)
            body = {
                "text": line,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.45,
                    "similarity_boost": 0.75,
                    "style": 0.35,
                },
            }
            try:
                mp3 = _post_bytes(TTS_API.format(voice_id=voice_id), key, body, timeout=180)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:300]
                print(f"    FAILED host_{station}_{i:02d}: HTTP {exc.code} {detail}", flush=True)
                continue
            _write_ogg(mp3, out)


def generate_static() -> None:
    """Procedural AM-radio static burst; no API credits."""
    import numpy as np
    import soundfile as sf

    rng = np.random.default_rng(1290)
    rate = 44100
    seconds = 2.4
    noise = rng.normal(0.0, 1.0, int(rate * seconds))
    # crude band-limit: difference filter knocks out the deep rumble, a short
    # moving average softens the hiss into AM-radio crackle
    noise = np.diff(noise, prepend=0.0)
    kernel = np.ones(6) / 6.0
    noise = np.convolve(noise, kernel, mode="same")
    # crackle envelope: irregular bursts over a low bed
    t = np.linspace(0.0, seconds, noise.size)
    envelope = 0.35 + 0.65 * (rng.random(noise.size) ** 6)
    fade = np.minimum(1.0, np.minimum(t / 0.05, (seconds - t) / 0.4))
    sample = noise * envelope * fade
    sample = 0.8 * sample / np.max(np.abs(sample))
    out = ASSETS / "radio" / "static_burst.ogg"
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), sample.astype(np.float32), rate, format="OGG", subtype="VORBIS")
    print(f"    wrote {out} ({out.stat().st_size:,} bytes)", flush=True)


def report_durations() -> None:
    import soundfile as sf

    print("\nMeasured durations (paste into music.py):")
    for path in sorted((ASSETS / "music").glob("radio_*.ogg")) + sorted(
        (ASSETS / "music").glob("host_*.ogg")
    ):
        info = sf.info(str(path))
        print(f"  {path.stem}: {info.frames / info.samplerate:.1f}s")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    flags = {arg for arg in argv if arg.startswith("--")}
    keys = [arg for arg in argv if not arg.startswith("--")]
    do_all = not flags and not keys
    if keys:
        unknown = [k for k in keys if k not in MUSIC_SPECS]
        if unknown:
            raise SystemExit(f"Unknown music keys: {', '.join(unknown)}")
    if "--static" in flags or do_all:
        generate_static()
    needs_api = do_all or "--music" in flags or "--hosts" in flags or keys
    if needs_api:
        key = _api_key()
        if "--hosts" in flags or do_all:
            generate_hosts(key)
        if "--music" in flags or do_all or keys:
            generate_music(key, keys or list(MUSIC_SPECS))
    report_durations()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
