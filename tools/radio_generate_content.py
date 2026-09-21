"""Plan-driven generation runners for the radio content plan.

Split out of ``generate_radio.py`` to stay under the repo's 1000-line file
cap: that module keeps the imaging/compression chain, the shared HTTP/ogg
helpers, and a thin CLI dispatch; this module reads
``tools/radio_content_plan.py`` (``STATIONS``, ``AD_PLAN``, ``SONG_PLAN``)
and turns it into ElevenLabs API calls plus finished ``assets/music/*.ogg``
files. Build-time only, never imported at runtime.

Every runner here is resume-friendly (skips an asset whose output file
already exists unless ``--force``), prints per-asset progress, and prints a
credit-usage delta (``GET /v1/user/subscription`` before/after) so a
partial or repeated run never spends silently. "Exists" means any of the
music extensions the game reads (``.opus``, ``.ogg``, ``.wav``): the shipped
tree was re-encoded to Opus after the first batch, and a runner that only
looked for ``.ogg`` would buy every song again. A scoped key without the
``user_read`` permission cannot read the meter; the delta then prints as
unreadable and each response's own ``character-cost`` header is printed
per asset instead.

Station-ID asset numbering follows ``radio_content_plan``'s own contract,
not a filename guess: each ``StationPlan.jingle_prompts`` entry already
carries its own output ``asset_key`` (``id_<station>_01`` / ``_02`` /
``_04``, per that module's docstring), so the produced jingles land exactly
there. The spoken IDs -- built from ``id_lines`` here, not from the plan --
take the keys the plan reserves for them: ``id_lines[0]`` is the legal ID
at ``id_<station>_03``, and every later line is a liner at
``id_<station>_05``, ``_06``, ... (``_04`` belongs to the third jingle).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_radio import (  # noqa: E402
    ASSETS,
    MUSIC_API,
    MUSIC_MODEL,
    TTS_API,
    TTS_MODEL,
    TTS_VOICE_SETTINGS,
    VOICE_CACHE,
    _normalize_to_target,
    _post_bytes,
    _rms_dbfs,
    _write_asset,
    _write_ogg,
    broadcast_compress,
    imaging_process,
    mix_id_bed,
)

SUBSCRIPTION_API = "https://api.elevenlabs.io/v1/user/subscription"
SFX_DIR = ASSETS / "radio" / "imaging"

# Same TTS delivery recipe generate_hosts already uses -- one voice
# character across hosts, station IDs, and ads keeps the cast consistent.
VOICE_SETTINGS = TTS_VOICE_SETTINGS

# Every container the game's music loader accepts, in its own preference
# order (audio/assets.rs MUSIC_EXTENSIONS). The resume check has to look for
# all of them: the shipped tree is Opus, the runners write Vorbis.
MUSIC_EXTENSIONS = ("opus", "ogg", "wav")

# mix_id_bed's two SFX layer names -> the SFX_PROMPTS key that fills each.
ID_SFX_LAYERS = {"whoosh": "radio_imaging_whoosh_short", "riser": "radio_imaging_riser"}


def _subscription(key: str) -> dict:
    req = urllib.request.Request(SUBSCRIPTION_API, headers={"xi-api-key": key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def credit_usage(key: str) -> int | None:
    """``character_count`` used against the account's ``character_limit``
    (``GET /v1/user/subscription``). TTS and Music generation both draw
    against this pool, so every runner reads it before and after its batch
    and prints the delta -- the only way to see a run's real cost without a
    dashboard trip.

    ``None`` when the key is scoped without ``user_read`` (the API answers
    401 with a missing-permissions status): a generation-only key is a
    reasonable thing to hand a build tool, and it must not stop the run.
    """
    try:
        return int(_subscription(key).get("character_count", 0))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return None
        raise


def _print_spend(before: int | None, after: int | None) -> None:
    if before is None or after is None:
        print(
            "  spend this run: not readable (the key lacks user_read; "
            "see the per-asset cost lines above)",
            flush=True,
        )
        return
    print(f"  spend this run: {after - before:,} characters ({before:,} -> {after:,})", flush=True)


def existing_output(stem: str) -> Path | None:
    """The music-tree file already standing in for ``stem``, if any.

    Checked in the loader's preference order, so the answer is the file
    the game would play; ``None`` means the asset still needs generating.
    """
    for ext in MUSIC_EXTENSIONS:
        candidate = ASSETS / "music" / f"{stem}.{ext}"
        if candidate.exists():
            return candidate
    return None


def _select_stations(content_key: str | None) -> dict:
    from radio_content_plan import STATIONS

    if content_key is None:
        return dict(STATIONS)
    if content_key not in STATIONS:
        raise SystemExit(f"Unknown station '{content_key}'; known: {', '.join(sorted(STATIONS))}")
    return {content_key: STATIONS[content_key]}


def _load_voice_map() -> dict[str, str]:
    if not VOICE_CACHE.exists():
        raise SystemExit(
            f"No cached voice map at {VOICE_CACHE} -- run "
            "`uv run python tools/generate_radio.py --voices` first."
        )
    return json.loads(VOICE_CACHE.read_text(encoding="utf-8"))


def _voice_id_for(voices: dict[str, str], name: str, context: str) -> str:
    voice_id = voices.get(name)
    if not voice_id:
        raise SystemExit(
            f"No cached voice for '{name}' ({context}) -- run "
            "`uv run python tools/generate_radio.py --voices` first."
        )
    return voice_id


def spoken_id_slot(line_index: int) -> int:
    """The ``id_<station>_NN`` number for ``id_lines[line_index]``.

    The legal ID keeps the ``_03`` the first batch shipped under; the
    liners after it start at ``_05`` because ``_04`` is the third sung
    jingle's key in the plan.
    """
    return 3 if line_index == 0 else 4 + line_index


def _station_seed(station_key: str) -> int:
    """Deterministic seed for imaging_process, stable across runs and
    machines (unlike Python's randomized ``hash()``)."""
    return zlib.crc32(station_key.encode("utf-8"))


def _mp3_bytes_to_samples(mp3_bytes: bytes):
    """Decode API-returned mp3 bytes to a float64 numpy array + sample
    rate, via ffmpeg, so the imaging chain can process TTS/Music output the
    same way it already processes procedurally generated audio."""
    import soundfile as sf

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(mp3_bytes)
        mp3_path = tmp.name
    wav_path = mp3_path[:-4] + ".wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", mp3_path, wav_path],
            check=True,
        )
        samples, rate = sf.read(wav_path, dtype="float64")
    finally:
        os.unlink(mp3_path)
        if os.path.exists(wav_path):
            os.unlink(wav_path)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    return samples, rate


def _loudness_match(samples, rate, *, label: str | None = None):
    """RMS-target normalize toward TARGET_RMS_DBFS with no EQ/compression/
    reverb -- for already-produced Music API output (jingles), which
    shouldn't get the voice-read imaging chain, just leveled to sit even
    with everything else on the dial."""
    out, peak_limited = _normalize_to_target(samples)
    if label is not None:
        note = " (peak-limited)" if peak_limited else ""
        print(f"    {label}: RMS {_rms_dbfs(out):.1f} dBFS{note}", flush=True)
    return out


def _jingle_length_ms(prompt: str) -> int:
    """Every jingle prompt states its own target length ("Ten second
    ..."/"Twelve second ..."); honor it instead of a single fixed
    duration. Falls back to 12s (mid-range of the API's accepted 10-15s
    window) for a prompt that doesn't lead with one of the two phrases.
    """
    text = prompt.strip().lower()
    if text.startswith("ten second"):
        return 10_000
    if text.startswith("twelve second"):
        return 12_000
    return 12_000


def _resample_linear(samples, src_rate: int, dst_rate: int):
    """Cheap linear-interpolation resample -- only exercised if a station's
    voice TTS and the imaging SFX beds ever come back at different sample
    rates (both ElevenLabs endpoints default to 44.1 kHz, so this is a
    safety net, not the common path)."""
    import numpy as np

    if src_rate == dst_rate or samples.size == 0:
        return samples
    dst_n = max(1, round(samples.size * dst_rate / src_rate))
    src_idx = np.linspace(0.0, samples.size - 1, dst_n)
    return np.interp(src_idx, np.arange(samples.size), samples)


def _load_id_sfx_layers():
    """Load the whoosh/riser beds mix_id_bed mixes under a station ID.

    Raises with a plain message naming ``--sfx`` if they haven't been
    generated yet -- imaging SFX is a separate, gated, credit-spending
    step (tools/generate_radio.py --sfx) and --plan-ids should never
    silently proceed without them.
    """
    import soundfile as sf

    missing = [name for name in ID_SFX_LAYERS.values() if not (SFX_DIR / f"{name}.ogg").exists()]
    if missing:
        names = ", ".join(f"{m}.ogg" for m in missing)
        raise SystemExit(
            f"Missing imaging SFX assets in {SFX_DIR}: {names} -- run "
            "`uv run python tools/generate_radio.py --sfx` first."
        )
    layers: dict = {}
    rate = 44100
    for layer_name, spec_key in ID_SFX_LAYERS.items():
        samples, rate = sf.read(str(SFX_DIR / f"{spec_key}.ogg"), dtype="float64")
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        layers[layer_name] = samples
    return layers, rate


def run_plan_hosts(key: str, content_key: str | None = None, *, force: bool = False) -> None:
    """--plan-hosts [STATION]: TTS every station's 8 host_lines in its cast
    voice, loudness-match with a light broadcast_compress pass, write
    assets/music/host_<station>_NN.ogg."""
    stations = _select_stations(content_key)
    voices = _load_voice_map()
    before = credit_usage(key)
    for station_key, plan in stations.items():
        voice_id = _voice_id_for(voices, plan.voice, f"station {station_key}")
        print(f"host lines for {station_key} ({plan.voice})...", flush=True)
        for i, line in enumerate(plan.host_lines, start=1):
            asset = f"host_{station_key}_{i:02d}"
            if existing_output(asset) and not force:
                print(f"  skip {asset} (exists)", flush=True)
                continue
            print(f"  speaking {asset}...", flush=True)
            body = {
                "text": line,
                "model_id": TTS_MODEL,
                "voice_settings": VOICE_SETTINGS,
            }
            try:
                mp3 = _post_bytes(TTS_API.format(voice_id=voice_id), key, body, timeout=180)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:300]
                print(f"    FAILED {asset}: HTTP {exc.code} {detail}", flush=True)
                continue
            samples, rate = _mp3_bytes_to_samples(mp3)
            processed = broadcast_compress(samples, rate, label=asset)
            _write_asset(processed, rate, f"music/{asset}.ogg")
    after = credit_usage(key)
    _print_spend(before, after)


def run_plan_ids(key: str, content_key: str | None = None, *, force: bool = False) -> None:
    """--plan-ids [STATION]: every id_lines entry TTS'd in the host voice ->
    imaging_process -> mix_id_bed with the SFX beds -> id_<station>_03.ogg
    for the legal ID (id_lines[0]) and id_<station>_05, _06, ... for the
    liners after it; each jingle_prompts entry -> Eleven Music -> loudness
    match -> the asset_key the plan already names for it
    (id_<station>_01/02/04)."""
    stations = _select_stations(content_key)
    voices = _load_voice_map()
    sfx_layers, sfx_rate = _load_id_sfx_layers()
    before = credit_usage(key)
    for station_key, plan in stations.items():
        voice_id = _voice_id_for(voices, plan.voice, f"station {station_key}")

        for line_index, line in enumerate(plan.id_lines):
            spoken_asset = f"id_{station_key}_{spoken_id_slot(line_index):02d}"
            if existing_output(spoken_asset) and not force:
                print(f"  skip {spoken_asset} (exists)", flush=True)
                continue
            print(f"spoken ID {spoken_asset} for {station_key} ({plan.voice})...", flush=True)
            body = {
                "text": line,
                "model_id": TTS_MODEL,
                "voice_settings": VOICE_SETTINGS,
            }
            try:
                mp3 = _post_bytes(TTS_API.format(voice_id=voice_id), key, body, timeout=180)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:300]
                print(f"    FAILED {spoken_asset}: HTTP {exc.code} {detail}", flush=True)
                continue
            samples, rate = _mp3_bytes_to_samples(mp3)
            voiced = imaging_process(samples, rate, _station_seed(station_key), label=spoken_asset)
            layers = {
                name: _resample_linear(layer, sfx_rate, rate) for name, layer in sfx_layers.items()
            }
            mixed = mix_id_bed(voiced, layers, rate)
            _write_asset(mixed, rate, f"music/{spoken_asset}.ogg")

        for asset_key, prompt in plan.jingle_prompts:
            if existing_output(asset_key) and not force:
                print(f"  skip {asset_key} (exists)", flush=True)
                continue
            length_ms = _jingle_length_ms(prompt)
            print(f"  composing jingle {asset_key} ({length_ms / 1000:.0f}s)...", flush=True)
            body = {
                "prompt": prompt,
                "music_length_ms": length_ms,
                "model_id": MUSIC_MODEL,
                "force_instrumental": False,
            }
            try:
                mp3 = _post_bytes(MUSIC_API, key, body)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:300]
                print(f"    FAILED {asset_key}: HTTP {exc.code} {detail}", flush=True)
                continue
            samples, rate = _mp3_bytes_to_samples(mp3)
            matched = _loudness_match(samples, rate, label=asset_key)
            _write_asset(matched, rate, f"music/{asset_key}.ogg")
    after = credit_usage(key)
    _print_spend(before, after)


def run_plan_ads(key: str, *, force: bool = False) -> None:
    """--plan-ads: TTS every AD_PLAN entry in its resolved voice ->
    broadcast_compress -> assets/music/<ad.key>.ogg."""
    from radio_content_plan import AD_PLAN

    voices = _load_voice_map()
    before = credit_usage(key)
    for ad in AD_PLAN:
        voice_id = _voice_id_for(voices, ad.voice, f"ad {ad.key}")
        if existing_output(ad.key) and not force:
            print(f"  skip {ad.key} (exists)", flush=True)
            continue
        print(f"  speaking {ad.key} ({ad.voice})...", flush=True)
        body = {
            "text": ad.script,
            "model_id": TTS_MODEL,
            "voice_settings": VOICE_SETTINGS,
        }
        try:
            mp3 = _post_bytes(TTS_API.format(voice_id=voice_id), key, body, timeout=180)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:300]
            print(f"    FAILED {ad.key}: HTTP {exc.code} {detail}", flush=True)
            continue
        samples, rate = _mp3_bytes_to_samples(mp3)
        processed = broadcast_compress(samples, rate, label=ad.key)
        _write_asset(processed, rate, f"music/{ad.key}.ogg")
    after = credit_usage(key)
    _print_spend(before, after)


def run_plan_songs(key: str, pool: str, *, force: bool = False, limit: int | None = None) -> None:
    """--plan-songs POOL: every SongPlan in the pool -> Eleven Music
    (music_length_ms=length_ms, force_instrumental per the plan) ->
    assets/music/<song.key>.ogg. No loudness pass, matching the existing
    generate_music songs -- station music has never been level-matched.

    ``limit``, when set, caps how many *fresh* generations this call makes
    (a budget-capped wave): songs already on disk still print their usual
    skip line and are resumed past for free -- they don't count against the
    cap. Once the cap is spent the loop stops; either way (cap hit or the
    pool finished under the cap) one line reports how many pool songs are
    still missing their output file -- counted across the *whole* pool, not
    just the songs after the stopping point, so an earlier song that failed
    its API call (HTTPError, logged and skipped without spending) still
    shows up as remaining instead of silently vanishing from the count.
    """
    from radio_content_plan import SONG_PLAN

    if pool not in SONG_PLAN:
        raise SystemExit(f"Unknown song pool '{pool}'; known: {', '.join(sorted(SONG_PLAN))}")
    before = credit_usage(key)
    songs = SONG_PLAN[pool]
    generated = 0
    for song in songs:
        if existing_output(song.key) and not force:
            print(f"  skip {song.key} (exists)", flush=True)
            continue
        if limit is not None and generated >= limit:
            break
        print(f"  composing {song.key} ({song.length_ms / 1000:.0f}s)...", flush=True)
        body = {
            "prompt": song.prompt,
            "music_length_ms": song.length_ms,
            "model_id": MUSIC_MODEL,
            "force_instrumental": song.instrumental,
        }
        try:
            mp3 = _post_bytes(MUSIC_API, key, body)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:300]
            print(f"    FAILED {song.key}: HTTP {exc.code} {detail}", flush=True)
            continue
        _write_ogg(mp3, ASSETS / "music" / f"{song.key}.ogg")
        generated += 1
    if limit is not None:
        remaining = sum(1 for s in songs if force or not existing_output(s.key))
        print(
            f"  limit {limit} reached, {remaining} of {len(songs)} pool songs remain ungenerated",
            flush=True,
        )
    after = credit_usage(key)
    _print_spend(before, after)


def run_probe(key: str, *, force: bool = False) -> None:
    """--probe: generate exactly one song (SONG_PLAN["oldies"][0]),
    measuring its real character cost against GET /v1/user/subscription
    before/after, then project the cost of the rest of the planned batch
    -- the remaining songs (extrapolated from the measured one) plus a
    character-count estimate for the TTS scripts (hosts + IDs + ads; TTS
    bills per character, unlike Music generation). Imaging SFX bills by
    duration_seconds, a different unit, so it's reported separately and
    left out of the character projection.

    Resume-friendly like the other runners: if the probe song's output file
    already exists, a re-run skips regenerating it (unless --force) so a
    repeated probe never silently re-spends Music credits. The
    before/after subscription read still runs either way, so a skipped
    probe reports 0 spend and the same account-remaining figure instead of
    just doing nothing.
    """
    from radio_content_plan import AD_PLAN, SFX_PROMPTS, SONG_PLAN, STATIONS

    song = SONG_PLAN["oldies"][0]
    out = ASSETS / "music" / f"{song.key}.ogg"

    try:
        before = _subscription(key)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise SystemExit(
                "--probe measures against GET /v1/user/subscription, which this key "
                "may not read (it lacks user_read). Grant the scope or use a full key."
            ) from exc
        raise
    before_count = int(before.get("character_count", 0))
    before_limit = int(before.get("character_limit", 0))
    print(f"  before: {before_count:,} / {before_limit:,} characters used", flush=True)

    if existing_output(song.key) and not force:
        print(
            f"  skip {song.key} (exists) -- pass --force to regenerate and re-measure", flush=True
        )
    else:
        print(f"  composing probe song {song.key} ({song.length_ms / 1000:.0f}s)...", flush=True)
        body = {
            "prompt": song.prompt,
            "music_length_ms": song.length_ms,
            "model_id": MUSIC_MODEL,
            "force_instrumental": song.instrumental,
        }
        mp3 = _post_bytes(MUSIC_API, key, body)
        _write_ogg(mp3, out)

    after = _subscription(key)
    after_count = int(after.get("character_count", 0))
    after_limit = int(after.get("character_limit", 0))
    delta = after_count - before_count
    remaining = after_limit - after_count
    print(f"  after:  {after_count:,} / {after_limit:,} characters used", flush=True)
    print(f"  probe song cost: {delta:,} characters", flush=True)

    total_songs = sum(len(batch) for batch in SONG_PLAN.values())
    remaining_songs = max(0, total_songs - 1)
    projected_song_cost = delta * remaining_songs

    tts_chars = 0
    for plan in STATIONS.values():
        tts_chars += sum(len(line) for line in plan.host_lines)
        tts_chars += sum(len(line) for line in plan.id_lines)
    for ad in AD_PLAN:
        tts_chars += len(ad.script)

    total_jingles = sum(len(plan.jingle_prompts) for plan in STATIONS.values())

    print(
        f"  {total_songs} songs planned total ({remaining_songs} remaining after this probe)",
        flush=True,
    )
    print(f"  projected remaining-song cost: ~{projected_song_cost:,} characters", flush=True)
    print(f"  TTS script characters (hosts + IDs + ads): {tts_chars:,}", flush=True)
    print(
        f"  projected grand total (remaining songs + TTS): "
        f"~{projected_song_cost + tts_chars:,} characters",
        flush=True,
    )
    print(
        f"  note: {total_jingles} station jingles and {len(SFX_PROMPTS)} imaging SFX beds "
        "still to generate, billed by generation/duration_seconds, not characters -- not "
        "included above",
        flush=True,
    )
    print(f"  credits remaining on account after probe: {remaining:,}", flush=True)
