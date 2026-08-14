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
    uv run python tools/generate_radio.py --voices --dry-run  # show what would be added
    uv run python tools/generate_radio.py --voices             # add missing cast voices
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_sounds import ASSETS, _api_key  # noqa: E402

MUSIC_API = "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128"
TTS_API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
VOICES_API = "https://api.elevenlabs.io/v1/voices"
LIBRARY_SEARCH_API = "https://api.elevenlabs.io/v1/shared-voices?search={query}&page_size=5"
ADD_VOICE_API = "https://api.elevenlabs.io/v1/voices/add/{public_user_id}/{voice_id}"
VOICE_CACHE = Path(__file__).resolve().parent / ".radio_voices.json"

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


def _search_library(key: str, name: str) -> list[dict]:
    req = urllib.request.Request(
        LIBRARY_SEARCH_API.format(query=urllib.parse.quote(name)),
        headers={"xi-api-key": key},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp).get("voices", [])


def _find_in_library(key: str, name: str) -> dict | None:
    for hit in _search_library(key, name):
        if hit.get("name", "").lower() == name.lower():
            return hit
    return None


def _add_from_library(key: str, name: str) -> str:
    hit = _find_in_library(key, name)
    if not hit:
        print(f"  library search found nothing usable for '{name}'", flush=True)
        return ""
    owner_id = hit.get("public_owner_id", "")
    body = {"new_name": name}
    add = urllib.request.Request(
        ADD_VOICE_API.format(public_user_id=owner_id, voice_id=hit["voice_id"]),
        data=json.dumps(body).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(add, timeout=60) as resp:
        return json.load(resp).get("voice_id", "")


def provision_voices(key: str, *, dry_run: bool = False) -> dict[str, str]:
    """Ensure every cast voice exists on the account; add from the shared
    library when missing. Returns name -> voice_id.

    In dry-run mode, the account voice list and the library search are both
    read-only GETs; the add-voice endpoint is never called and nothing is
    cached, so it is safe to run against the owner's real ElevenLabs account
    at any time.
    """
    from radio_content_plan import AD_PLAN, STATIONS

    wanted: dict[str, tuple[str, ...]] = {}
    for plan in STATIONS.values():
        wanted[plan.voice] = plan.voice_fallbacks
    for ad in AD_PLAN:
        wanted.setdefault(ad.voice, ())

    req = urllib.request.Request(VOICES_API, headers={"xi-api-key": key})
    with urllib.request.urlopen(req, timeout=60) as resp:
        have = {v["name"]: v["voice_id"] for v in json.load(resp).get("voices", [])}

    resolved: dict[str, str] = {}
    for name, fallbacks in wanted.items():
        match = next(((c, have[c]) for c in (name, *fallbacks) if c in have), None)
        if match:
            candidate, voice_id = match
            resolved[name] = voice_id
            tag = "" if candidate == name else f" (resolved via fallback {candidate})"
            print(f"  {name} -> {voice_id}{tag}", flush=True)
            continue
        if dry_run:
            hit = _find_in_library(key, name)
            if hit:
                print(
                    f"  {name} -> WOULD ADD from library "
                    f"(match: {hit.get('name')}, category: {hit.get('category', 'unknown')})",
                    flush=True,
                )
            else:
                print(f"  {name} -> NOT FOUND anywhere", flush=True)
            continue
        added = _add_from_library(key, name)
        if added:
            resolved[name] = added
            print(f"  {name} -> {added} (added from library)", flush=True)
        else:
            raise SystemExit(f"No voice found for cast '{name}' -- adjust the plan")

    if not dry_run:
        VOICE_CACHE.write_text(
            json.dumps(resolved, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"  cached voice map to {VOICE_CACHE}", flush=True)
    return resolved


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


def _fm_hiss(rng, rate: int, seconds: float):
    """Shaped FM interstation noise; the shared recipe for all fringe assets.

    FM fringe noise is not AM crackle -- the limiter rejects impulse
    noise (owner's ham-ear ruling 2026-07-23). What a real receiver
    plays between stations is the demodulator's triangular noise
    spectrum (+6 dB/octave) rolled off by the 75 microsecond
    de-emphasis network: a full, smooth frying hiss with body around
    1-2 kHz, no pops. A second gentle pole (~5 kHz) stands in for the
    receiver's audio stage: pure post-de-emphasis noise is rise-then-
    flat and reads thin and digital on full-range playback.
    """
    import numpy as np

    noise = rng.normal(0.0, 1.0, int(rate * seconds))
    # FM demod noise rises 6 dB/octave: a differentiator is exactly that.
    shaped = np.diff(noise, prepend=0.0)
    for rc in (75e-6, 1.0 / (2.0 * np.pi * 5000.0)):
        alpha = (1.0 / rate) / (rc + 1.0 / rate)
        acc = 0.0
        out_buf = np.empty_like(shaped)
        for i, x in enumerate(shaped):
            acc += alpha * (x - acc)
            out_buf[i] = acc
        shaped = out_buf
    return shaped


def _write_asset(sample, rate: int, relpath: str) -> None:
    import soundfile as sf

    out = ASSETS / relpath
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), sample.astype("float32"), rate, format="OGG", subtype="VORBIS")
    print(f"    wrote {out} ({out.stat().st_size:,} bytes)", flush=True)


def generate_static() -> None:
    """Procedural FM interstation hiss burst; no API credits."""
    import numpy as np

    rng = np.random.default_rng(1290)
    rate = 44100
    seconds = 2.4
    shaped = _fm_hiss(rng, rate, seconds)
    t = np.linspace(0.0, seconds, shaped.size)
    # slow AGC-like wander, subtle: +/-20 percent over ~1 Hz, never impulsive
    wander = 1.0 + 0.2 * np.sin(2.0 * np.pi * (0.7 * t + 0.3 * np.sin(2.0 * np.pi * 0.23 * t)))
    fade = np.minimum(1.0, np.minimum(t / 0.05, (seconds - t) / 0.4))
    sample = shaped * wander * fade
    sample = 0.8 * sample / np.max(np.abs(sample))
    _write_asset(sample, rate, "radio/static_burst.ogg")


def generate_fringe() -> None:
    """FM fringe runtime kit: a seamless hiss-bed loop and the picket bank.

    The bed loops on its own channel with distance-scaled gain; pickets are
    short sharp-edged splashes (FM capture is a threshold -- the gating is
    abrupt, owner ruling 2026-07-23) fired at the Rayleigh-flutter rate by
    the driving state. Edges: ~3 ms attack, ~12 ms release; anything softer
    smears the picket, anything shorter clicks.
    """
    import numpy as np

    rate = 44100
    rng = np.random.default_rng(4471)
    # Bed: generate long, then splice the tail over the head (equal-power,
    # 50 ms) so the loop point is seamless in a noise signal.
    seconds = 4.0
    xfade = int(0.05 * rate)
    raw = _fm_hiss(rng, rate, seconds + 0.05)
    head = raw[:xfade].copy()
    body = raw[xfade : xfade + int(seconds * rate)].copy()
    ramp = np.linspace(0.0, 1.0, xfade)
    body[-xfade:] = body[-xfade:] * np.sqrt(1.0 - ramp) + head * np.sqrt(ramp)
    body = 0.7 * body / np.max(np.abs(body))
    _write_asset(body, rate, "radio/fm_hiss_loop.ogg")

    durations = (0.05, 0.07, 0.09, 0.11, 0.13, 0.16)
    for i, dur in enumerate(durations, start=1):
        splash = _fm_hiss(rng, rate, dur)
        n = splash.size
        attack = int(0.003 * rate)
        release = int(0.012 * rate)
        env = np.ones(n)
        env[:attack] = np.linspace(0.0, 1.0, attack)
        env[-release:] = np.linspace(1.0, 0.0, release)
        splash = splash * env
        splash = 0.85 * splash / np.max(np.abs(splash))
        _write_asset(splash, rate, f"radio/picket_{i:02d}.ogg")


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
    if "--voices" in flags:
        dry_run = "--dry-run" in flags
        key = _api_key()
        if dry_run:
            print("Dry run: read-only account + library lookups, nothing added.", flush=True)
        resolved = provision_voices(key, dry_run=dry_run)
        if not dry_run:
            print(f"\n{len(resolved)} voice(s) resolved and cached.", flush=True)
        return 0
    do_all = not flags and not keys
    if keys:
        unknown = [k for k in keys if k not in MUSIC_SPECS]
        if unknown:
            raise SystemExit(f"Unknown music keys: {', '.join(unknown)}")
    if "--static" in flags or do_all:
        generate_static()
    if "--fringe" in flags or do_all:
        generate_fringe()
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
