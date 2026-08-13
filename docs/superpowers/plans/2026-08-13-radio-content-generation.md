# Radio Content Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Tasks 4-7 call the paid ElevenLabs API — they run inline with the owner's session key, never in parallel, and stop at every wave boundary to report spend.

**Goal:** Produce and wire the full station-identity content: per-station hosts, IDs/jingles with imaging effects, a shared ad pool, four new-genre stations, and a big song batch (~70 songs), all baked into the asset pack.

**Architecture:** A declarative plan module (`tools/radio_content_plan.py`) drives an extended `tools/generate_radio.py`: voice provisioning, TTS with an imaging post-production chain (ffmpeg/numpy compression + EQ + doubling + reverb, SFX mixed under IDs), Eleven Music songs, probe-first budget gating. Outputs land in `assets/music/` and `assets/radio/`, get measured, fill `music.py` / `radio_content.py` / `radio_catalog.json`, and repack into `sounds.pak`.

**Tech Stack:** ElevenLabs Music (`music_v1`), TTS (`eleven_multilingual_v2`), Sound Effects API, ffmpeg, numpy/soundfile, git-lfs.

Spec: `docs/superpowers/specs/2026-08-13-debt-dealer-radio-design.md` sections C-D.
Depends on: `2026-08-13-radio-break-slots.md` (merged first — tables must exist).

## Global Constraints

- Branch `feat/debt-dealer-radio`. Build-time generation only; the key comes from `generate_sounds._api_key()` (out-of-repo file / env), never bundled, never committed, never printed.
- Audio keys are an asset contract: `host_<station>_NN`, `id_<station>_NN`, `ad_<slug>`, `radio_<pool>_<slug>`. Existing keys never change.
- All spoken scripts are player-facing: plain road language, fictional business and station names only, no real brands, no jargon. CB radios appear only as one line inside the electronics-shop ad (owner ruling 2026-08-13).
- Deterministic post-processing: fixed numpy seeds per asset key.
- Durations in the catalogs must match measured file durations (`report_durations`).
- `git lfs push origin feat/debt-dealer-radio` manually before `git push` when `sounds.pak` changes; `git-lfs` lives at `C:\Program Files\Git LFS`, not on PATH. Never `git add -A`.
- Spend gates: report measured credit cost after the probe and after every wave; stop and ask the owner if a wave lands >25% over its estimate.

---

### Task 1: Content plan module — casting, scripts, prompts

**Files:**
- Create: `tools/radio_content_plan.py`
- Test: Create `tests/test_radio_content_plan.py`

**Interfaces:**
- Produces (all pure data, imported by `generate_radio.py` and the copy test):
  - `STATIONS: dict[str, StationPlan]` keyed by content key (= catalog `host` value), with `@dataclass StationPlan(station_id, name, voice, voice_fallbacks, persona, playlist, host_lines: tuple[str, ...], id_lines: tuple[str, ...], jingle_prompts: tuple[tuple[str, str], ...])` (jingle prompts: (asset_key, music prompt))
  - `AD_PLAN: tuple[AdPlan, ...]` with `@dataclass AdPlan(key, business, voice, script, formats: tuple[str, ...])`
  - `SONG_PLAN: dict[str, tuple[SongPlan, ...]]` per pool with `@dataclass SongPlan(key, title, description, prompt, length_ms, instrumental)`
  - `SFX_PROMPTS: dict[str, str]` (whoosh/impact/riser prompts for the imaging bed)

- [ ] **Step 1: Write the failing consistency test:**

```python
from tools.radio_content_plan import AD_PLAN, SONG_PLAN, STATIONS


def test_every_station_plan_is_complete():
    for key, plan in STATIONS.items():
        assert len(plan.host_lines) == 8, key
        assert len(plan.id_lines) >= 1, key
        assert len(plan.jingle_prompts) == 2, key  # 2 produced + 1 spoken = 3 IDs
        assert plan.voice, key
        assert plan.name in " ".join(plan.id_lines), key  # IDs name the station


def test_ad_pool_is_modern_and_tagged():
    assert len(AD_PLAN) >= 18
    keys = [a.key for a in AD_PLAN]
    assert len(keys) == len(set(keys))
    assert sum("CB" in a.script for a in AD_PLAN) == 1  # one line, one spot
    for ad in AD_PLAN:
        assert ad.formats, ad.key


def test_song_plan_matches_batch_size():
    for pool in ("oldies", "gospel", "tejano", "synthwave"):
        assert 8 <= len(SONG_PLAN[pool]) <= 10, pool
    for pool in ("country", "classic_rock", "blues", "jazz"):
        assert 8 <= len(SONG_PLAN[pool]) <= 10, pool
    night = SONG_PLAN.get("night_line", ())
    assert 2 <= len(night) <= 3
```

- [ ] **Step 2: Run `uv run pytest tests/test_radio_content_plan.py -p no:xdist -q`, verify ImportError.**
- [ ] **Step 3: Write the plan module.** This is the big authoring step. Content rules:
  - **Casting (voice names are ElevenLabs voice-library display names; fallbacks in preference order):** FFR Roadhouse → `Clyde` (owner pick). Night Line → a smoky, low, mature female late-night voice (search the shared library for e.g. `Serena` / `Charlotte`-adjacent "sultry, smoky" tags; scripts intimate and unhurried, adult in tone, always clean). Country stations (KRWZ, WHWX, KPNL, KBGK): four distinct warm/twangy voices, mix of genders. Classic rock (WGDX, KDRZ, KHRZ, KRIJ, KSDX): five weathered rock voices. Blues (WDTQ, WBYK, WSOZ): southern soul voices. WNAH jazz: cool and unhurried. KGOL oldies: bright AM-gold energy. WGLR gospel: warm preacher cadence. KTJO Tejano: bilingual host (Spanish colour, English enough to follow every sentence). KNDR synthwave: hushed, close-mic night voice.
  - **Host lines (8 per station):** in-register road talk mentioning the station name or frequency at least twice across the set; no dates, no real places' claims, no weather promises (the game speaks real weather elsewhere).
  - **ID lines (1 spoken legal-style per station):** "«call sign», «name», «city»" shaped, e.g. "K-N-D-R, Neon Drive 88 5, Las Vegas."
  - **Jingle prompts (2 per station):** Eleven Music prompts for 8-15 s sung/produced sweepers carrying the station name, genre-matched.
  - **Ads (18+):** fictional travel centers, diners, tire shops, diesel additive, carrier recruiting, motels, load-board app, coffee, owner-operator insurance, truck wash, chrome & electronics shop (the one CB mention), scales app, boots, satellite comms, rest-area chaplaincy, headset brand, GPS units, jerky. 20-30 s scripts, each tagged with the playlists it fits.
  - **Songs:** follow the `MUSIC_SPECS` prompt style already in `generate_radio.py` (concrete genre, mood, instrumentation, vocals or `instrumental`), lengths 150-260 s. New-station four pools get 8-10 each; country/classic_rock/blues/jazz top-ups 8-10 each; 2-3 Night Line vocal ballads.
- [ ] **Step 4: Run the test, verify passes. Also run `uv run ruff check tools`.**
- [ ] **Step 5: Commit** `feat(tools): radio content plan — casting, scripts, prompts [skip changelog]`

---

### Task 2: Voice provisioning (`--voices`)

**Files:**
- Modify: `tools/generate_radio.py`

**Interfaces:**
- Produces: `provision_voices(key) -> dict[str, str]` (voice name → voice_id) and CLI flag `--voices`; the map is cached to `tools/.radio_voices.json` (gitignored — add to `.gitignore`).

- [ ] **Step 1: Implement.** Extend the existing `_pick_voice` pattern:

```python
LIBRARY_SEARCH_API = "https://api.elevenlabs.io/v1/shared-voices?search={query}&page_size=5"
ADD_VOICE_API = "https://api.elevenlabs.io/v1/voices/add/{public_user_id}/{voice_id}"


def provision_voices(key: str) -> dict[str, str]:
    """Ensure every cast voice exists on the account; add from the shared
    library when missing. Returns name -> voice_id."""
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
        for candidate in (name, *fallbacks):
            if candidate in have:
                resolved[name] = have[candidate]
                break
        else:
            added = _add_from_library(key, name)
            if added:
                resolved[name] = added
            else:
                raise SystemExit(f"No voice found for cast '{name}' — adjust the plan")
    return resolved


def _add_from_library(key: str, name: str) -> str:
    req = urllib.request.Request(
        LIBRARY_SEARCH_API.format(query=urllib.parse.quote(name)),
        headers={"xi-api-key": key},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        hits = json.load(resp).get("voices", [])
    for hit in hits:
        if hit.get("name", "").lower() == name.lower() and hit.get("free_users_allowed", True):
            body = {"new_name": name}
            add = urllib.request.Request(
                ADD_VOICE_API.format(
                    public_user_id=hit["public_owner_id"], voice_id=hit["voice_id"]
                ),
                data=json.dumps(body).encode(),
                headers={"xi-api-key": key, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(add, timeout=60) as resp:
                return json.load(resp).get("voice_id", "")
    print(f"  library search found nothing usable for '{name}'", flush=True)
    return ""
```

Print each resolution ("cast Night Line -> Serena (added from library)") so the owner sees exactly what landed on the account. Adding voices touches the owner's ElevenLabs account: run `--voices` once, show the list of voices it WOULD add (dry-run print first when `--voices --dry-run`), and get the owner's go-ahead in-session before the adding call runs.
- [ ] **Step 2: Run `uv run python tools/generate_radio.py --voices --dry-run`, show the owner the cast list, then run `--voices` for real after their yes. Verify the printed map is complete.**
- [ ] **Step 3: Commit** `feat(tools): ElevenLabs voice provisioning [skip changelog]`

---

### Task 3: Imaging post-production chain

**Files:**
- Modify: `tools/generate_radio.py`
- Test: Create `tests/test_radio_imaging_chain.py` (pure-numpy unit test, no API)

**Interfaces:**
- Produces: `imaging_process(samples, rate, seed, *, doubled=True) -> np.ndarray` (compression + EQ + doubling + short bright reverb), `mix_id_bed(voice, sfx_layers, rate) -> np.ndarray`, `broadcast_compress(samples, rate) -> np.ndarray` (light chain for ads), `generate_sfx(key, prompts) -> None` (Sound Effects API → `assets/radio/imaging/<key>.ogg`).

- [ ] **Step 1: Failing unit test:** feed a 1 s 440 Hz sine through `imaging_process` with a fixed seed; assert output is same length ±ping-tail (allow up to +0.4 s), peak ≤ 1.0, RMS within 3 dB of a target loudness constant, and two runs with the same seed are byte-identical. Same-shape checks for `broadcast_compress`.
- [ ] **Step 2: Run, verify ImportError.**
- [ ] **Step 3: Implement with numpy** (soft-knee compressor via smoothed gain on the envelope; presence EQ as a biquad peak around 3 kHz + high-pass at 120 Hz; doubling as a 15 ms detuned copy at -6 dB; reverb as a short exponentially-decaying noise convolution, 0.25 s, seeded). SFX generation posts `{"text": prompt, "duration_seconds": ..}` to `https://api.elevenlabs.io/v1/sound-generation` and writes ogg via the existing `_write_ogg`. `mix_id_bed` lays a whoosh under the voice head and a riser into the tail, peak-normalized to 0.9.
- [ ] **Step 4: Run the unit test, verify passes.**
- [ ] **Step 5: Commit** `feat(tools): imaging post-production chain [skip changelog]`

---

### Task 4: Generation runners + probe-first budget gate

**Files:**
- Modify: `tools/generate_radio.py` (new flags: `--plan-hosts [STATION]`, `--plan-ids [STATION]`, `--plan-ads`, `--plan-songs POOL`, `--probe`, `--sfx`)

**Interfaces:**
- Consumes: Tasks 1-3. Produces asset files:
  - hosts → `assets/music/host_<station>_NN.ogg` (loudness-matched, natural voice)
  - spoken ID → `assets/music/id_<station>_01.ogg` (imaging chain + SFX bed)
  - jingles → `assets/music/id_<station>_02.ogg`, `_03.ogg` (Eleven Music, then loudness match)
  - ads → `assets/music/ad_<slug>.ogg` (broadcast compression)
  - songs → `assets/music/radio_<pool>_<slug>.ogg`
- Produces: `credit_usage(key) -> int` reading `GET /v1/user/subscription` `character_count`/`character_limit`, printed before/after every run.

- [ ] **Step 1: Implement the runners** by generalizing `generate_hosts`/`generate_music` to read the plan module; every runner prints per-asset progress and a spend delta from `credit_usage`. `--probe` generates exactly one song (first of `SONG_PLAN["oldies"]`), prints measured credits for it, and multiplies out the full song batch estimate.
- [ ] **Step 2: Run `--probe`. STOP. Report to the owner:** measured credits for one song, projected total for ~70 songs plus TTS/SFX, credits remaining on the account. Wait for the owner's go before Task 5.
- [ ] **Step 3: Commit** (code only, no assets yet) `feat(tools): plan-driven generation runners with spend gate [skip changelog]`

---

### Task 5: Spoken-content batch (cheap): hosts, IDs, ads, SFX

- [ ] **Step 1: Run in order, checking spend after each:** `--sfx`, then `--plan-ids` (all stations), then `--plan-hosts` (all stations — FFR re-voiced with Clyde and expanded to 8; keep the existing 6 scripts' spirit, `HOST_LINES` moves into the plan module), then `--plan-ads`.
- [ ] **Step 2: Listen-check at least one host break, one ID, and one ad per format** (play locally; the imaging chain should read as radio, not TTS-over-silence). Regenerate misfires individually.
- [ ] **Step 3: Report spend delta to the owner.**
- [ ] **Step 4: Commit assets** (`git add assets/music/host_* assets/music/id_* assets/music/ad_* assets/radio/imaging` — explicit paths, never `-A`) `feat(radio): station voices, IDs, and ad pool assets [skip changelog]`

---

### Task 6: Song batch in genre waves

- [ ] **Step 1: Wave order:** oldies → gospel → tejano → synthwave → country top-up → classic_rock top-up → blues top-up → jazz top-up → night_line ballads. After EACH wave: print spend delta + running total; STOP and report to the owner if >25% over the probe-based estimate, otherwise continue.
- [ ] **Step 2: Listen-check one song per wave; regenerate individual misfires by key.**
- [ ] **Step 3: Commit per 2-3 waves** with explicit paths: `feat(radio): <pools> song batch [skip changelog]`

---

### Task 7: Wire the data — catalogs, tables, new stations

**Files:**
- Modify: `src/freight_fate/music.py` (new pools `OLDIES_TRACKS`, `GOSPEL_TRACKS`, `TEJANO_TRACKS`, `SYNTHWAVE_TRACKS`; top-up entries appended to existing pools; new ballads appended to `NIGHT_LINE_VOCAL_TRACKS`; `STATION_PLAYLISTS` + `ALL_MUSIC_TRACKS` extended; `STATION_HOST_SEGMENTS` extended with all new host pools, keys `host_<station>_NN`)
- Modify: `src/freight_fate/radio_content.py` (fill `STATION_IDS`, `AD_SPOTS`, `AD_FORMAT_TAGS` from the plan's formats)
- Modify: `src/freight_fate/data/radio_catalog.json` (set `host` on the 13 regional rows; add 4 rows: KGOL Cruisin' Gold 105.9 Oklahoma City / WGLR Glory Road 91.5 Birmingham / KTJO Puro Tejano 107.1 San Antonio / KNDR Neon Drive 88.5 Las Vegas — `always_available`, dial group 1, `playlist` set, format text in the row's existing shape; verify call-sign/frequency uniqueness against curated + imported catalogs first: `python -c` sweep)
- Test: existing `tests/test_radio_breaks.py::test_station_content_tables_resolve` plus `tests/test_music_selection.py`, `tests/test_radio_regional.py`

- [ ] **Step 1: Run `report_durations`, paste measured durations into every new `MusicTrack`.**
- [ ] **Step 2: Fill the tables; run the consistency guard** — it now exercises the real data (every host/playlist resolves, keys unique, durations positive, ad tags valid).
- [ ] **Step 3: Run radio + music test files via the test-runner agent; fix pinned-count fallout** (e.g. tests asserting station counts or `ALL_MUSIC_TRACKS` size).
- [ ] **Step 4: Commit** `feat(radio): four new stations and full station identity wiring [skip changelog]`

---

### Task 8: Pack, changelog, roadmap, full suite

- [ ] **Step 1: Repack:** `uv run python tools/encode_music_opus.py` (if the music path uses it — follow the tool's own README/usage header) then `uv run python tools/pack_sounds.py`. Verify a clean-clone-style load: temporarily rename `assets/sounds`, run `uv run pytest tests/test_radio_breaks.py -p no:xdist -q` against the pack fallback, restore.
- [ ] **Step 2: Changelog** (`## Unreleased` → `Added`):

```markdown
- **Every Freight Fate station now sounds like a real station.** All the
  regional stations have their own host between songs, station jingles and
  IDs, and fictional commercials for the road: travel centers, diners,
  tire shops, and more. The Roadhouse has a new voice, and the Night Line
  host settles in even closer after dark.
- **Four new stations join the dial.** Cruisin' Gold plays oldies out of
  Oklahoma City, Glory Road brings southern gospel from Birmingham, Puro
  Tejano runs Tejano and regional Mexican from San Antonio, and Neon Drive
  hums synthwave out of Las Vegas -- with dozens of new songs across every
  station's playlist.
```

- [ ] **Step 3: ROADMAP** — 1.9 line: check off/describe the station-identity work; add an unchecked follow-up bullet for any pool that came in under target or any voice that needs recasting after tester feedback.
- [ ] **Step 4: Full suite + lint via the test-runner agent.**
- [ ] **Step 5: Commit** `feat(radio): station identity and soundtrack expansion` (changelog commit, no skip marker). Then `git lfs push origin feat/debt-dealer-radio` (full path to git-lfs) before any `git push`.
