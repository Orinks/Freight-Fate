# 1.9 music intake, always-on FF stations, and instant live weather

Design for three 1.9-line changes (none port to dev): adding the
"country influenced originals" batch to the game's music, making the
fictional stations available to every player everywhere, and removing
the live-weather wait at drive start.

## 1. Music intake from the 2026-07 originals batch

Source: `~/Downloads/country influenced originals.zip` — 43 MP3s,
33 distinct titles (nine titles carry alternate takes). Intake rule
(owner, 2026-08-08): **one take per title**, chosen as the longest
duration, tie-broken by higher bitrate. All tracks are instrumentals.

Pipeline per track: extract chosen take → encode to Ogg Opus 80 kbps
stereo (PyAV, same settings as `tools/encode_music_opus.py`) →
`src/freight_fate/assets/sounds/music/<key>.opus` → catalog entry in
`music.py` with the real duration → credits row in
`assets/sounds/CREDITS.md` (Suno-composed originals batch, wording to
match the 2026-07 Zero batch rows) → regenerate `sounds.pak` where the
release packaging expects it. Audio keys are permanent once shipped.

### Placement (by title and intended mood; owner veto welcome)

**New station pool `jazz` — "Nashville After Hours" (new FF station):**
`more nashville jazzicals`, `when some nashville cats got jazzy`,
`that nashville sound in the 80's`, `that nashville sound in the 90's`,
`happens in nashville tonight`, `a caring touch`,
`penny for your thoughts`. Keys `radio_jazz_*`. Seven tracks — in range
of the existing pools (blues ships 12, night 14).

**Country station pool additions (`COUNTRY_TRACKS`):**
`texico station fill up`, `crutial load needed in arkansas`,
`kentucky rain called me home`, `texian style`,
`Texas country on a Tuesday evening`, `thursday night in fort worth`,
`texas wants you back, and so do I`, `alabama called`,
`carolina groovin`, `over yonder`. Keys `radio_country_*`.

**Day-drive beds (`DAY_DRIVE_TRACKS`):** `canoe trail`,
`on the gunflint`, `a little boat trip I took once`,
`dancing firelight`, `always around when you need me`. Keys `drive_*`.

**Night-drive beds (`NIGHT_DRIVE_TRACKS`):** `under the starlight`,
`gettin ever so slightly darker tonight`,
`why the stars said I love you that night`,
`her real words to me that night`, `when you were on my mind`,
`call me when you get this`, `maroon coloured scarf`,
`when we took that train I knew it was it`. Keys `night_*`.

**New menu milestone bed:** `progress for progress's sake` becomes a
seventh `MENU_TRACKS` bed for the career-arc band the 1.9 line added:
`_menu_milestone_index` gains a top tier at level >= 21 (or
75 deliveries / 40,000 miles, following the existing pattern of paired
thresholds). Existing profiles below the band hear no change.

**Left out (no clear home; can join later):** `country in the shower`,
`my heart wants you`, `when we took that train (alternate takes)` and
the other non-chosen takes.

Titles keep their file names as display titles, title-cased, with the
misspelling fixed ("Crucial Load Needed in Arkansas"). Descriptions
follow the existing catalog's style ("Easy pastoral fingerpicked bed").

### Testing

Existing music tests pin catalog/asset agreement; they extend to the new
keys automatically where they iterate `ALL_MUSIC_TRACKS`. New assertions:
the jazz pool is non-empty, the seventh milestone bed unlocks at the new
band, and every new catalog key has a shipped `.opus` asset.

## 2. Fictional stations: always available, for everyone

Today the 12 fictional `regional` stations (The Rawhide, Big Wheel
Country, Prairie Line, Big Sky Country, The Grind, Desert Rock, Chrome,
The Ridge, The Sound, The Delta, Bayou Soul, Southern Soul) are pinned
to transmitter coordinates with ~110-mile ranges: a player outside those
bubbles never hears the FF originals they carry. They already pass the
streamer-safe gate (they are not real streams), so geography is the only
gate being removed.

Changes:

- `radio_catalog.json`: the 12 stations (plus the new Nashville After
  Hours) set `always_available: true` and drop `lat`/`lon`/
  `range_miles`. Names, formats, and source notes stay; the city flavor
  lives on in the name and source text.
- `_dial_group()` in `radio.py`: any non-real-stream station backed by a
  `playlist` sorts into group 1, "Freight Fate stations", joining
  Roadhouse and Night Line — 15 FF stations, one category jump from
  anywhere, in every mode (streamer-safe on or off, real streams on or
  off, no truck position needed).
- The receivable list already honors `always_available`; reception reads
  "always available" instead of a distance, matching Roadhouse today.

Player-facing result: every player, in any state, in any mode, can tune
every FF-original station. Changelog bullet under Unreleased (the radio
rework is already a 1.9 headline; this folds into its story).

### Testing

New tests: with no position, streamer-safe on, and real streams off, all
playlist-backed stations appear in `receivable_stations()`; dial group 1
contains exactly the FF stations; a saved fictional-station favorite
stays receivable anywhere. Existing fictional-station reception tests
(in-range/out-of-range against transmitter coords) update to the new
always-on behavior.

## 3. Live weather: immediate at drive start, and never simulated
## while real weather is on

Harness evidence (probe drive, New York to Philadelphia, real NWS,
2026-08-08): the fetch pipeline is healthy — the first observation lands
about 1.5 seconds after the first driving tick and the next tick goes
live. The remaining causes of "waiting, then simulated" are structural:

1. **The drive-start gap.** The observation cache is keyed by an opaque
   route-cell string (`route:denver:cheyenne:0`) that exists only once
   the trip is built, so the first fetch — up to three sequential HTTP
   calls — cannot start until the first driving tick. Nothing earlier in
   the session can warm the cache: the city menu knows the city, and a
   previous trip may have ended at this exact city, but same-place
   requests under different keys always miss.
2. **Cell-boundary fallback.** Every 20 route miles the trip switches to
   a fresh cell key. One transient fetch failure on that fresh key flips
   `source_status` to "fallback" instantly: the last-known guard is
   bypassed because `unavailable()` consults only the new key, which has
   one recorded failure and no cache. A single dropped request at a cell
   boundary simulates weather while NWS is fine.

Owner ruling (2026-08-08): with real weather on, the game should never
fall back to simulated weather. Fixes, in order:

Root fix for the start gap: **observations belong to stations, not to
key strings.**

- `RealWeatherProvider` gains a coordinate-resolved layer: each request
  key maps (via the existing coordinate-keyed station cache) to the
  station's observation URL, and observations are cached **per station
  URL**, with request keys as aliases. Any request within the same
  station's coverage — city menu, previous trip, next trip's first
  cell — shares one fresh observation. `get(key)`/`unavailable(key)`
  semantics are unchanged for callers.
- **Warm at the terminal:** `CityMenuState.enter` requests weather for
  the parked city's coordinates through the shared provider. By the time
  a dispatch is accepted and the drive spins up, the origin station's
  observation is cached, and the trip's first route cell (which samples
  route mile zero, i.e. the same city) resolves to the same station —
  the drive starts already live.
- **Request at trip construction:** `Trip.__init__` (and snapshot
  restore) fires the first cell's request immediately instead of waiting
  for the first `update()` tick, so even cold starts (Continue straight
  into a mid-route resume) overlap the fetch with the drive-start
  speech instead of the drive itself.

And the fallback ruling: **failures hold last-known, they never
simulate.**

- While real weather is on and any live observation has been seen this
  session, a failed or pending fetch keeps the previous conditions and
  reports "last_known" (with its honest age), retrying on the existing
  60-second cadence. `WeatherSystem` already carries the last live kind;
  the change is that a fresh cell key's failure consults
  session-level history, not just its own key.
- "Fallback" (simulated) remains only for the genuinely cold case: real
  weather on, no observation ever seen this session, and the provider
  reporting failure — a fresh career start with no internet. That case
  keeps today's wording.

No new spoken text: "loading" and "last known" wording already exist;
they just become rare and honest respectively. 1.9-only by owner
decision; dev keeps the current behavior.

### Testing

Provider tests: two keys at the same coordinates share one observation
(one fetch); a fresh observation under one key serves another key
without a second fetch; per-key failure semantics survive the aliasing.
Weather tests: a new cell key whose fetch fails holds the previous live
kind and reports "last_known", not "fallback"; a session with no
observation ever still reaches "fallback" when the provider fails.
State tests: entering the city menu issues a provider request with the
city's coordinates; a trip constructed after a warmed menu reports
`source_status == "live"` on its first update tick.

## 4. Dead-stream manners (roadmap item, added by owner 2026-08-08)

Today a real stream that fails to play falls back to the silent
satellite station — the 2026-08-07 manual session's complaint. New
behavior when a stream refuses to play or dies:

- The failed station is remembered as unplayable for the rest of the
  session and leaves the dial (it returns next session; streams have
  bad days).
- The radio hands over to the next receivable station in the same dial
  category (same `_dial_group`), announcing the handover in one line:
  the dead station is named as off the air, then the replacement plays.
  Only when the whole category is exhausted does the old fallback
  station take over.

### Testing

A failing stream is excluded from `receivable_stations()` afterward; the
handover picks the next same-group receivable station; category
exhaustion still lands on the fallback; the spoken line names both
stations.

## Out of scope

- Porting any of this to dev (owner decision, 2026-08-08).
- Tejano/borderlands and western-swing batches (future palette work,
  noted so the idea is not lost).
- Facility/dock-work music beds for the timed-facility states.
- Retiring the unused alternate takes; they stay in the source zip only.
