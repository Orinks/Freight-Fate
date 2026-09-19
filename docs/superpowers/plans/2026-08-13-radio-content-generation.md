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

---

## Suno candidates and listening links - September 19, 2026

Created September 19, 2026. Based on the content plan at Career 1.9 commit 72f85e86 and the inventory in C:/ff-tester/FreightFate/freight_fate/music.pak.

### Status and listening notes

All 33 missing song prompts and 19 additional station-jingle slots now have Suno candidates, counting the Roadhouse trial the owner liked. Each generation has two takes in the Suno workspace; the links below open one candidate per planned slot, not an endorsed selection. Generation entries were verified, but not every take's final completion or audio quality. Nothing was downloaded, published, or integrated into the game by this session. Playback was left paused.

The eight country candidates and two rock candidates were generated in Simple mode before the owner requested manually written lyrics. Later vocal songs use original lyrics entered in Advanced mode. Instrumentals use arrangement instructions only. Vocal genders follow the narrator; River Rising is a male-female duet. Suno's actual performance still needs listening verification.

Some short jingles display Credits Refunded. This is a UI status, not a listening verdict. Check clear station-name pronunciation, clean beginnings and endings, musical character, and sensible duration. Later, audition chosen assets with game speech and engine audio before integration.

Final duration check: Neon Drive returned 0:27 and 0:08 despite the 0:12 target. The linked first take is the longer one; the [eight-second Neon Drive alternate](https://suno.com/song/443802c3-c5a2-45e3-a882-7805e83772d1) is also available. Custom duration is therefore a target, not a verified exact-length guarantee; selected jingles may need trimming.

The first pair titled Vulture Pass accidentally retained Paper Crown lyrics because clearing the editor failed. Do not use those: 97d078f4-3d2c-4465-ac1e-9711c8f8f142 and d7f2a6ba-d6e5-45df-bea1-0907ca546cfc. The corrected Vulture Pass — Instrumental pair is linked below. All subsequent editor text was verified before submission.

### Country: earlier automatic-lyric candidates

- [Split Rail](https://suno.com/song/cd8835a5-4433-42bc-9d7e-e044aa730874).
- [County Fair Lights, generated as At the Top of the Ferris](https://suno.com/song/028d9086-5c7a-46ac-9e5b-99fe8f8fbfbe).
- [Porch Swing Promise — selected duet retake A](https://suno.com/song/81aa9882-1473-41d4-8a66-0d3242b7dfdc).
- [Harvest Moon Over the Barn](https://suno.com/song/10e263c2-b485-4413-8681-787c6edc95f4).
- [Cold Coffee Courage](https://suno.com/song/f01396d2-f089-4eaf-b054-79f20ad7d0ba).
- [Last Bale of Summer](https://suno.com/song/ad45e351-273a-46ad-aaf6-23d7b8099a5e).
- [Red Dirt Ring, generated as Barn Dance Duel](https://suno.com/song/a6471d5c-107e-4c0f-8cbf-8aa12d6e4ae7): instrumental.
- [High Line Home, generated as The Northern High Line](https://suno.com/song/abf8f56c-0e6f-4cd8-9782-14042519024b).

### Classic rock

- [Paper Crown](https://suno.com/song/db920dc3-6454-4861-af0a-c71cc3c01b8f): original lyrics, female narrator addressing her former high-school boyfriend.
- [Bar Band Saturday, generated as Loudest Little Band](https://suno.com/song/3c06d3f2-cbf9-4e32-8c35-eedbf31f438d): earlier automatic lyrics.
- [Lights Over Superior, generated as Expressive Guitar Arc](https://suno.com/song/0f4f5e35-fc47-426b-8880-acf4f6a7cd82): earlier Simple-mode instrumental.
- [Last Payphone in Town](https://suno.com/song/9dfb8f32-71b3-4191-970e-e5e1c7cdc5a8): original lyrics, male narrator.
- [Vulture Pass — Instrumental, corrected version](https://suno.com/song/c1cec1aa-ff79-456f-a46b-f51b0565dbe6): instrumental arrangement instructions.
- [Magnetic West](https://suno.com/song/26bc7622-1fdb-4a5b-838d-2278ddee5ba0): original lyrics, female narrator starting a new life.
- [River Rising — selected duet retake B](https://suno.com/song/57c036ee-fd3c-407a-943d-ddba882e3809): original lyrics, male-female community duet.
- [Furnace Wind](https://suno.com/song/904d2498-cb4f-4b01-b57d-ecf5042f7cf3): original lyrics, smoky female lead.

### Blues

- [Eleven Bridges](https://suno.com/song/dbd2a741-c418-4a35-8b3c-273bb5995e87): original lyrics, reflective male narrator.
- [Fish Fry Friday](https://suno.com/song/bfe4c0a9-5e04-4620-a05e-9e53c9135eb7): original lyrics, exuberant female storyteller.
- [Back Porch Darling](https://suno.com/song/5e3088f1-5839-4d12-95a8-287173a1eca3): original lyrics, female serenade to a longtime partner.
- [Leaky Roof Blues](https://suno.com/song/76edbaf4-0163-4957-9d35-c0890d313adb): original lyrics, weathered male narrator.
- [Catfish County](https://suno.com/song/7ee496ed-d232-484d-99ef-06c6f979a92c): harmonica-led instrumental.
- [Low Water Crossing](https://suno.com/song/bd6abc07-276a-46ac-9dcf-b2079590141e): original lyrics, male narrator choosing the higher road after a previous mistake.
- [Night Shift Queen](https://suno.com/song/335d42ef-1f29-4d19-a8af-6c8af3048b43): original lyrics, female supervisor narrating her shift.
- [Red Lights and Regrets](https://suno.com/song/7932cd44-3c07-46b9-81ed-f8fa28fe252c): original lyrics, reflective male narrator.

### Jazz

- [Lower Broad Lullaby](https://suno.com/song/b924a7bd-3fee-4248-b6c0-2c59c284d2e8): muted-trumpet instrumental.
- [Velvet Downbeat](https://suno.com/song/760d1b78-9277-40a8-ab00-0fc384cdf8f0): tenor-sax swing instrumental.
- [Neon and Nylon](https://suno.com/song/0cca0565-be3d-4354-b733-e1e1d140b646): nylon guitar and electric piano instrumental.
- [Printer's Alley Last Call](https://suno.com/song/74d8cb9b-9583-4662-aade-8c802a71b08d): plunger-mute trombone instrumental.
- [Brushed Steel](https://suno.com/song/d781eb13-4cfb-4135-881e-1a4d4ce182e9): pedal-steel jazz instrumental.
- [Midnight Mezzanine](https://suno.com/song/9940202b-aac1-42d8-a9da-cfe2b051e5f8): piano nocturne.
- [Blue Neon Glow](https://suno.com/song/67a91cb3-31ae-4154-9822-d222505040ba): original lyrics, female torch-song narrator remembering a former male partner.
- [Cumberland Moonrise](https://suno.com/song/dd2657ae-8fc4-47dc-8d4e-6bdbb21a2f8c): flugelhorn instrumental.

### Night Line

- [Dashboard Glow](https://suno.com/song/bafd04a3-3c9a-47df-b1dc-4651061209ec): original lyrics, intimate male narrator learning to speak honestly to his partner.

### Additional station jingles

The station ID 04 titles refer to the missing additional jingle slot in the plan. No existing IDs were replaced. The Roadhouse trial is an owner-liked alternative to the exact planned solo-voice/whistle arrangement; the remaining station jingles follow their planned identity. Twelve-second targets allow room for the ending; actual durations vary.

- [Freight Fate Roadhouse — Coast to Coast ID](https://suno.com/song/9e6007bf-7d50-431e-ad9d-eeb1f301520c): owner liked this trial; warm male harmonies.
- [Night Line — Station ID 04](https://suno.com/song/d773df22-d9b3-477e-9b8a-a5a46f293c46): hushed female lead.
- [The Rawhide — Station ID 04](https://suno.com/song/ddf13ac6-b109-41bd-9218-62b9ad1afa82): cowboy baritone.
- [Big Wheel Country — Station ID 04](https://suno.com/song/0c9e048b-0b6d-464e-95b6-7cefeb8fc42b): female duet.
- [Prairie Line — Station ID 04](https://suno.com/song/356ef85e-8d45-4c2c-9351-0f1be2013723): warm male lead.
- [Big Sky Country — Station ID 04](https://suno.com/song/b56bcab1-058c-4a2c-aeac-6f5ca6496a80): high male tenor.
- [The Grind — Station ID 04](https://suno.com/song/da3f4704-b42f-4402-8783-a176e4782737): gravelly male lead.
- [Desert Rock — Station ID 04](https://suno.com/song/590f71dd-3573-4689-a471-a5f473553e88): low raspy male lead.
- [Chrome — Station ID 04](https://suno.com/song/4aeafb12-8db3-4c8e-99ae-84f6de25223a): powerhouse female lead with group response.
- [The Ridge — Station ID 04](https://suno.com/song/ab402f95-1430-4677-8179-0bf90b0f0488): soaring male lead.
- [The Sound — Station ID 04](https://suno.com/song/4da332c6-440f-4690-ab3f-f5b618f7cdf2): relaxed male lead.
- [The Delta — Station ID 04](https://suno.com/song/7bb87f34-c8d3-47c6-981f-5078f149ba29): weathered male lead.
- [Bayou Soul — Station ID 04](https://suno.com/song/307f8afb-5efa-41d4-a003-d32c8e4d9ab4): playful raspy male lead.
- [Southern Soul — Station ID 04](https://suno.com/song/442dcb8c-087f-4088-98c2-1d5471111669): rich female lead with choir response.
- [Nashville After Hours — Station ID 04](https://suno.com/song/82e808dc-1769-4940-b5d4-49bbcae08f94): hushed male crooner.
- [Cruisin' Gold — Station ID 04](https://suno.com/song/446195a5-7652-4f57-8d5c-8244e6d41c5e): mixed harmony singers.
- [Glory Road — Station ID 04](https://suno.com/song/69e200e8-bdd3-4f38-8636-8d24f28a7a5d): female lead and mixed choir.
- [Puro Tejano — Station ID 04](https://suno.com/song/4653a11b-1ea4-417d-af6f-22304040628c): bright male lead with Spanish pronunciation.
- [Neon Drive — Station ID 04](https://suno.com/song/44b20cea-05d9-4eea-880b-b975121e30d2): breathy female voice with vocoder.

### Next production step

Audition both versions in Suno and choose takes. Confirm lyrics, pronunciation, absence of unwanted vocals in instrumentals, clean endings, and level consistency. Then download selected originals, measure durations, preserve the established asset keys, and test the game mix before updating music.pak. The existing pack remains untouched.

## Duet retakes using Fade Out at the Bar

The owner approved the other linked song takes and requested duet retakes using the metatag structure from [the published Fade Out at the Bar reference](https://suno.com/song/663d250f-1995-480f-9f24-a4a99c5fbbc3). The existing duet versions remain alternates; none were deleted or overwritten.

These new generations preserve every lyric word from the linked original versions. Section tags now explicitly identify Male, Female, and Male & Female, with instrumental intro/outro tags. Style prompts reinforce solo alternating verses and joined harmony choruses while retaining each song's genre. New entries were verified; consistent vocal-role performance still requires listening. Playback remains paused.

- Porch Swing Promise: [duet retake A](https://suno.com/song/81aa9882-1473-41d4-8a66-0d3242b7dfdc), [duet retake B](https://suno.com/song/f505f7c8-20d0-4424-b547-e52352d8ab9f). [Existing alternate](https://suno.com/song/503e7a2f-5050-433e-ab8d-3c9668010d61).
- River Rising: [duet retake A](https://suno.com/song/5afdfaf0-c4bf-4d13-90ab-fca5badc935a), [duet retake B](https://suno.com/song/57c036ee-fd3c-407a-943d-ddba882e3809). [Existing alternate](https://suno.com/song/71fd5c68-4a69-405f-af89-712d16628c37).

### Owner-selected duet takes

- **Porch Swing Promise: take A selected.** [Open selected Porch Swing Promise](https://suno.com/song/81aa9882-1473-41d4-8a66-0d3242b7dfdc).
- **River Rising: take B selected.** [Open selected River Rising](https://suno.com/song/57c036ee-fd3c-407a-943d-ddba882e3809).

The owner listened and selected these versions. Earlier versions and the other retakes remain alternates. Both selections were downloaded and integrated in the September 19 batch described below.

## September 19 snapshot integration

The owner approved the linked full-song takes, selecting Porch Swing Promise duet retake A and River Rising duet retake B. The available 25 downloads covered eight country, eight classic-rock, eight blues, and Dashboard Glow. These are encoded as stereo 48 kHz Opus at 80 kbps, with gain toward the existing -16 dBFS RMS target and a 0.95 sample-peak cap. Last Bale of Summer and Fish Fry Friday received an additional 2 dB of headroom after checking codec overshoot; their decoded true peaks are -1.6 and -1.9 dBTP respectively. Masters and alternate takes remain preserved.

The Rust station playlists include the matching genre additions. Dashboard Glow joins only the Night Line vocal pool. The rebuilt music pack retains all 380 previous entries byte-for-byte and adds 25 entries, for 405 total. Catalog durations come from the encoded files. [Source links, master hashes, encoding gains, and durations](../../radio-september-2026.json) identify every selected asset.

Eight jazz songs remain to download first, followed by 19 jingles, after the September 21 allowance refresh.
