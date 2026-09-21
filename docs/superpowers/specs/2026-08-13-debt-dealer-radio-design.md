# Debt payoff, direct truck dealer, and station identity — design

Owner approvals: 2026-08-13 (all four sections). Sources: tester feedback via
Telegram (Shane and Darren's out-of-pocket debt fix, seconded by Josh), Josh's
direction on city services, and Josh's ElevenLabs direction for the radio.

## A. Pay debt out of pocket

Today the carried balance (`Profile.fines_owed`) only comes down through the
25-percent settlement collection in `models/solvency.py`. A driver holding
cash has no way to just pay it, which testers correctly read as a hole.

### Behavior

- A menu item **"Pay down what you owe: X dollars owed"** appears on the
  terminal menu (`CityMenuState`) and the truck-stop rest menu whenever
  `fines_owed >= 1` and the driver has at least 10 dollars of cash.
- It opens a small `PayDebtState` menu built from the driver's real numbers:
  - **"Pay it all: X dollars"** — only when cash covers the full balance.
  - **"Pay half: Y dollars"** — half the balance, capped at available cash.
  - **"Pay what you can, keeping a 200 dollar cushion: Z dollars"** — only
    when cash minus 200 is positive and less than the balance.
  - **Back.**
  Options that would compute to under 1 dollar are not offered. Every option
  leaves cash at or above zero.
- The spoken result states what was paid, the cash remaining, and either the
  new balance or that the account is clear. Clearing the balance ends
  settlement collection immediately (collection already keys off
  `fines_owed`, so no extra state is needed).
- The overdraft half of `debt_owed` (cash below zero) is untouched: there is
  no cash to pay with in that state, so the menu item simply never shows.

### Spoken pointers

- `debt_warning_line` rungs 1 and 2 (full form only, not terse) and
  `debt_line` gain one sentence: "You can also pay it down from cash at any
  terminal or truck stop."
- `advance_refused_reason` keeps its wording; it already points at running a
  load.

### Implementation shape

- `models/solvency.py`: pure helpers `out_of_pocket_options(profile) ->
  list[tuple[label, amount]]` and `pay_out_of_pocket(profile, amount) ->
  float` (clamps to balance and cash, returns what was actually paid).
  Constants `PAYOFF_CASH_CUSHION = 200.0`, `PAYOFF_MIN_CASH = 10.0`.
- `states/city.py`: menu item + `PayDebtState` (a `MenuState`).
- `states/driving_rest_states.py`: same item on the truck-stop menu, reusing
  `PayDebtState`.
- Tests: unit tests for option computation and clamping edge cases (cash
  exactly at cushion, balance under 1 dollar, cash under 10); a menu-flow
  test that pays in full and confirms collection stops; spoken-copy check
  that amounts read as "1,234 dollars".

## B. Remove the drive to city services

The local drive uniquely gates only the truck dealer — the garage and the
dispatch board are already direct terminal items. Owner ruling: remove it;
services belong at the terminal and at rest stops.

### Behavior

- Terminal menu: **"Drive to city services" is removed**, replaced by
  **"Truck dealer"**, which opens `TruckShopState` directly (Garage stays as
  is; the dispatch board already opens the freight market).
- The shop intro uses the source-backed dealer name from
  `city_services.json` when one exists: "Inside Rush Truck Center of
  Dallas." Fallback stays "{City} Truck Dealer". The data file and
  `world_services.city_services()` accessors stay; only the routing is
  removed.
- `CityServiceSelectState`, `DRIVE_PHASE_CITY_SERVICE`, and every branch
  keyed on it in `states/driving*.py` are deleted, along with
  `city_service_route` / `city_service_approach` / `city_service_geometry`
  plumbing that nothing else reads.
- **Save compatibility:** a save whose `active_trip` snapshot carries the
  `city_service` phase loads parked at the terminal with the trip dropped
  and one spoken line: "Local service drives were retired in this update;
  you are parked at the terminal." No money or time changes.
- Spoken texts promising "city services" during suspensions and lifetime
  disqualification (`driving_rest_states.py`) reword to name what is really
  there: "rest, repairs, the garage, and the truck dealer." Help text and
  `docs/ontology.md` follow (add a "truck dealer" row if the concept is not
  there; remove/replace "city services").
- Data note: `city_services.json` garage and freight-market entries become
  dormant but stay checked in — they are source-backed POI data and the
  dealer entry is still read. No world regen needed.

### Tests

- Terminal menu test: dealer item present, opens the shop, spoken intro uses
  the source-backed name.
- Save-load test: fixture snapshot with `phase == "city_service"` loads to
  the terminal with the notice, profile intact.
- Sweep: no remaining references to the removed phase or state.

## C. Station identity packages

All fictional stations get a produced identity: hosts, station IDs/jingles,
and commercials. Baked assets only — build-time generation, never runtime
API calls, key never bundled (same contract as today's
`tools/generate_radio.py`).

### Per-station package

- **Host:** one distinct ElevenLabs voice per station, 8 personality-matched
  breaks (~5-8 s each), written in the station's own register. No maintainer
  jargon; plain road talk.
  - **FFR Roadhouse: Clyde** (owner pick). Existing 6 breaks re-voiced with
    Clyde and expanded to 8.
  - **Night Line:** its own identity, a bit more adult — smoky, low,
    intimate late-night voice; scripts lean confessional and unhurried, still
    clean.
  - Remaining stations cast by format: warm twang for country, weathered
    rock voices, southern soul for the blues dial, cool and unhurried for
    Nashville After Hours, bright AM-gold energy for oldies, warm preacher
    cadence for gospel, bilingual host for Tejano (Spanish colour, English
    enough to follow), hushed synth-era voice for the synthwave station.
- **Station IDs/jingles:** 3 per station. Mix of short produced sweepers
  (Eleven Music, ~8-15 s, sung or produced with the station name and
  frequency) and one dry spoken legal-style ID (TTS in the host voice).
- **Imaging post-production (owner question, 2026-08-13):** ID and sweeper
  voices are processed, not dry TTS — broadcast-style compression and EQ,
  slight doubling and a short bright reverb on the imaging voice, so a
  station ID sounds like imaging, not a screen reader over a song. IDs and
  stingers get the sound-effects layer real imaging carries: whooshes,
  impacts, and risers generated with the ElevenLabs sound-effects API
  (cheap), mixed under and around the voice. Host breaks stay natural-voiced
  but are loudness-matched to the music; ads get light broadcast compression
  per spot. The mixing/processing step is ffmpeg + numpy in the generation
  tool, deterministic per asset.
- **Commercials:** a shared pool of ~18 fictional modern spots (~20-30 s,
  TTS, varied voices): travel centers, diners, tire shops, diesel additive,
  carrier recruiting, motels, a load-board app, coffee, owner-operator
  insurance, and a truck-electronics/chrome shop where CB radios sit
  alongside dash cams, ELDs, and GPS units (owner note: modern setting — CBs
  appear as one line in that spot, no dedicated CB-shop ad). Every business
  name is fictional; no real brands. Spots are tagged by format fit and
  rotated across stations.

### New stations (always_available, dial group 1)

| Station | Format | Playlist pool |
| --- | --- | --- |
| KGOL Cruisin' Gold 105.9 (Oklahoma City) | oldies / classic hits | `oldies` |
| WGLR Glory Road 91.5 (Birmingham) | southern gospel | `gospel` |
| KTJO Puro Tejano 107.1 (San Antonio) | Tejano / regional Mexican | `tejano` |
| KNDR Neon Drive 88.5 (Las Vegas) | synthwave / night electronic | `synthwave` |

Call signs and frequencies checked for uniqueness against the full catalog
(curated + imported) at implementation time; adjust if a collision shows.
Reception-physics tests keep using fixtures, never catalog stations.

### Break scheduler

Generalize the current every-2-songs host break (`driving_updates.py` around
`_radio_hosts` / `RADIO_TRACKS_PER_HOST_BREAK`) into **break slots**:

- After every 2 songs, one break plays. Break content cycles a per-station
  pattern, deterministic from the trip seed:
  `HOST, ID, HOST, AD_THEN_ID` (repeat).
- An `AD_THEN_ID` break plays one commercial then a short ID back into
  music, the way a real spot break ends. Ads therefore never run
  back-to-back and an ID lands at least once per four breaks.
- Stations with no ads or no IDs (personal playlists, streams, route
  playlist) skip those slot types gracefully; streams are untouched — this
  is playlist-station machinery only.
- Element selection within a type is the existing deterministic shuffle
  (`zlib.crc32` over trip seed + station id), no repeats until a pool
  exhausts.

### Code layout

- New module `src/freight_fate/radio_content.py`: per-station host/ID tables,
  the ad pool, break patterns, and the selection helpers — keeps `music.py`
  (652 lines) under the 1000-line rule.
- `music.py`: four new song pools (`OLDIES_TRACKS`, `GOSPEL_TRACKS`,
  `TEJANO_TRACKS`, `SYNTHWAVE_TRACKS`), pool top-ups, and
  `STATION_PLAYLISTS` entries.
- `data/radio_catalog.json`: 4 new station rows; `host` field values for all
  playlist stations.
- Tests: catalog consistency (every playlist/host/ID/ad key resolves, keys
  unique, durations positive), break-pattern unit tests (ad spacing, ID
  cadence, determinism), plus the existing radio fixtures untouched.

## D. Generation pipeline and budget

- `tools/generate_radio.py` grows a data-driven plan (module
  `tools/radio_content_plan.py`): per-station voice map, break scripts, ID
  and ad scripts, jingle prompts, song prompts.
- **Voice provisioning:** a `--voices` step lists the account's voices,
  verifies the plan's casts, and adds missing ones from the shared voice
  library via the API (`/v1/voices/add/...`). Premades (Clyde et al.) are
  already on every account. This is the owner-requested "add voices to my
  account" step.
- **Probe-first budget gate:** generate one song, read the real credit cost
  from the subscription endpoint before/after, report it, then scale the
  estimate for the batch and confirm before the waves run.
- **Big batch (owner pick):** ~8-10 songs per new genre and ~8-10 top-ups
  per existing pool (country, classic rock, blues, jazz; a couple of Night
  Line vocal ballads) — roughly 70 songs. Generated in genre waves with a
  running spend report between waves; stop-on-hot at any wave boundary.
- All audio lands through the existing ffmpeg → Ogg Vorbis convention;
  `report_durations` output pastes into the catalogs; durations must match
  the shipped files.
- **Packing:** repack `sounds.pak` (`tools/pack_sounds.py`, opus encode step
  where the pipeline calls for it). LFS gotchas apply: `git lfs push origin
  feat/career-1.9` manually before `git push`; never `git add -A`.
- Changelog: player-language entries for the debt payoff, the truck dealer
  move, and the radio/station update. ROADMAP: same change — check off /
  add bullets under the 1.9 line.

## Out of scope

- Runtime TTS or any network audio generation in the game.
- Real-station (streamed) behavior, reception physics, streamer-safe logic.
- The overdraft side of debt, advance rules, and the ceiling/consequence
  ladder — all unchanged.
- Leaderboards, cloud, or online surfaces.
