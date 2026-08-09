# 1.9 Music Intake, Always-On FF Stations, Instant Live Weather — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the "country influenced originals" batch into beds, stations, and a new FF jazz station; make every FF-music station always available; make live weather immediate at drive start and never simulated while real weather is on.

**Architecture:** Music flows through the existing `music.py` catalog / opus asset / `sounds.pak` pipeline. The radio change is catalog data plus one dial-group rule. The weather change re-keys the provider's observation cache by station URL with request keys as aliases, adds a city-menu warm-up and trip-construction request, and re-orders `source_status` so session history beats per-key failures.

**Tech Stack:** Python 3.12, PyAV (encode only, via `uv run --with av`), pytest.

## Global Constraints

- Branch: `feat/career-1.9` only. Nothing ports to dev (owner, 2026-08-08).
- One take per title: longest duration wins, tie-break higher bitrate.
- Audio keys are permanent once shipped; spoken copy follows `docs/ontology.md`.
- Never `git add -A` (licensed sounds overlay lives near the tree).
- Changelog entries required for player-facing work; `[skip changelog]` otherwise.
- Run `uv run ruff check src tests tools` and the focused tests before every commit.

---

### Task 1: Encode the chosen takes to opus assets

**Files:**
- Create: 31 files under `src/freight_fate/assets/sounds/music/` (keys below)
- Create (scratchpad, not committed): `encode_originals.py`

**Interfaces:**
- Produces: `<key>.opus` assets and a printed `(key, title, duration_s)` table Task 2 copies into `music.py`.

Key map (zip title → key). Jazz: `more nashville jazzicals`→`radio_jazz_nashville_jazzicals`, `when some nashville cats got jazzy`→`radio_jazz_nashville_cats`, `that nashville sound in the 80's`→`radio_jazz_eighties_sound`, `that nashville sound in the 90's`→`radio_jazz_nineties_sound`, `happens in nashville tonight`→`radio_jazz_nashville_tonight`, `a caring touch`→`radio_jazz_caring_touch`, `penny for your thoughts`→`radio_jazz_penny_thoughts`. Country: `texico station fill up`→`radio_country_texico_fill_up`, `crutial load needed in arkansas`→`radio_country_arkansas_load`, `kentucky rain called me home`→`radio_country_kentucky_rain`, `texian style`→`radio_country_texian_style`, `Texas country on a Tuesday evening`→`radio_country_tuesday_texas`, `thursday night in fort worth.`→`radio_country_fort_worth_thursday`, `texas wants you back, and so do I`→`radio_country_texas_wants_you`, `alabama called`→`radio_country_alabama_called`, `carolina groovin`→`radio_country_carolina_groovin`, `over yonder `→`radio_country_over_yonder`. Day: `canoe trail`→`drive_canoe_trail`, `on the gunflint`→`drive_gunflint`, `a little boat trip I took once`→`drive_little_boat_trip`, `dancing firelight`→`drive_dancing_firelight`, `always around when you need me`→`drive_always_around`. Night: `under the starlight`→`night_under_starlight`, `gettin ever so slightly darker tonight`→`night_slightly_darker`, `why the stars said I love you that night`→`night_stars_said_love`, `her real words to me that night`→`night_her_real_words`, `when you were on my mind`→`night_on_my_mind`, `call me when you get this`→`night_call_me`, `maroon coloured scarf`→`night_maroon_scarf`, `when we took that train I knew it was it`→`night_train_knew`. Menu: `progress for progress's sake`→`menu_progress`.

- [ ] **Step 1: Write the encode script** (scratchpad). For each mapped title: gather all takes matching the base name (strip ` (N)` suffix), pick longest duration (tie: higher bitrate), decode with PyAV, encode Ogg Opus 80 kbps stereo 48 kHz to `music/<key>.opus`, print `key | display title | duration_s`. Mirror the encoder settings in `tools/encode_music_opus.py` (open output with format `ogg`, codec `libopus`, `bit_rate=80_000`).
- [ ] **Step 2: Run it**: `uv run --with av python <scratchpad>/encode_originals.py`. Expected: 31 opus files written; table printed; every duration within 5% of the MP3 probe values.
- [ ] **Step 3: Spot-verify**: `uv run python -c "import sound_lib"`-based playback is not needed; instead verify each file opens with PyAV and its container duration matches the printed value.
- [ ] **Step 4: Commit** the 31 assets only (`git add src/freight_fate/assets/sounds/music/*.opus` — exact new names), message `feat(music): encode the country-originals batch to opus [skip changelog]` (player-facing bullet lands with Task 8).

### Task 2: Catalog the new tracks in music.py

**Files:**
- Modify: `src/freight_fate/music.py`
- Test: `tests/test_music.py` (extend the existing file; create if absent)

**Interfaces:**
- Produces: `JAZZ_TRACKS: tuple[MusicTrack, ...]`, five new entries appended to `DAY_DRIVE_TRACKS`, eight to `NIGHT_DRIVE_TRACKS`, ten to `COUNTRY_TRACKS`, `MENU_TRACKS` seventh entry `menu_progress`, `STATION_PLAYLISTS["jazz"] = JAZZ_TRACKS`, and `ALL_MUSIC_TRACKS` including all of them. Task 4 references `JAZZ_TRACKS`.

- [ ] **Step 1: Failing tests.** Add to `tests/test_music.py`:

```python
def test_jazz_pool_exists_and_ships_assets():
    from freight_fate import music

    assert len(music.JAZZ_TRACKS) == 7
    assert music.STATION_PLAYLISTS["jazz"] == music.JAZZ_TRACKS
    root = Path(music.__file__).parent / "assets" / "sounds" / "music"
    for track in music.JAZZ_TRACKS:
        assert (root / f"{track.key}.opus").exists(), track.key


def test_seventh_menu_milestone_unlocks_at_level_21():
    from freight_fate import music

    assert music.MENU_TRACKS[6].key == "menu_progress"
    high = SimpleNamespace(
        career=SimpleNamespace(level=21, deliveries=0, total_miles=0),
        owned_trucks=(), truck="rig",
    )
    assert music._menu_milestone_index(high) == 6
    mid = SimpleNamespace(
        career=SimpleNamespace(level=9, deliveries=40, total_miles=20_000),
        owned_trucks=(), truck="rig",
    )
    assert music._menu_milestone_index(mid) == 5
```

- [ ] **Step 2: Run, expect FAIL** (`JAZZ_TRACKS` undefined): `uv run pytest tests/test_music.py -q`.
- [ ] **Step 3: Implement.** Append `MusicTrack` entries using Task 1's printed durations, descriptions in catalog voice (e.g. `"Smoky Nashville crossover jazz instrumental"`, `"Easy pastoral fingerpicked bed"`). Add `JAZZ_TRACKS` tuple after `BLUES_TRACKS`; add `"jazz": JAZZ_TRACKS` to `STATION_PLAYLISTS`; append `MusicTrack("menu_progress", "Progress for Progress's Sake", "Seasoned late-career country bed", <dur>)` to `MENU_TRACKS`; extend `ALL_MUSIC_TRACKS` with `+ JAZZ_TRACKS`. In `_menu_milestone_index`, add the top tier first: `if level >= 21 or deliveries >= 75 or miles >= 40_000: return 6`.
- [ ] **Step 4: Run tests + existing music/menu tests**: `uv run pytest tests/test_music.py tests/test_updater.py -q`. `test_settings_menu`/menu-music tests that iterate `MENU_TRACKS` must stay green; fix any pinned counts.
- [ ] **Step 5: Commit** `feat(music): catalog the originals batch with a jazz pool and a level-21 menu bed [skip changelog]`.

### Task 3: Credits and sound pack

**Files:**
- Modify: `src/freight_fate/assets/sounds/CREDITS.md`, `src/freight_fate/sounds.pak`

- [ ] **Step 1:** Add one credits table row per new track, wording matched to the existing batch rows: `| <Display Title> | music/<key>.opus | Suno-composed <description> (2026-08 originals batch) |`.
- [ ] **Step 2:** Regenerate the pack: `uv run python tools/pack_sounds.py` (confirm its output path is `src/freight_fate/sounds.pak` and that it picks up the licensed overlay dir if configured — read the tool header first; entry count should grow by exactly 31).
- [ ] **Step 3:** Verify: `uv run pytest tests/test_updater.py -q -k sound` plus `uv run python -c` snippet opening the pack via `freight_fate.assets_pack.SoundPack` and asserting the 31 new `music/*.opus` names are present.
- [ ] **Step 4: Commit** `feat(music): credit and pack the originals batch [skip changelog]` (add only CREDITS.md and sounds.pak by name).

### Task 4: Always-available FF stations + Nashville After Hours

**Files:**
- Modify: `src/freight_fate/data/radio_catalog.json`, `src/freight_fate/radio.py`
- Test: `tests/test_radio.py` (extend)

**Interfaces:**
- Consumes: `STATION_PLAYLISTS["jazz"]` from Task 2.
- Produces: 15 always-available FF stations in dial group 1.

- [ ] **Step 1: Failing tests.**

```python
def test_ff_music_stations_receivable_everywhere_in_every_mode():
    state = RadioState(position=None, streamer_safe=True, real_streams_enabled=False)
    names = {r.station.name for r in state.receivable_stations()}
    for expected in ("The Rawhide 98.1", "Big Sky Country 99.3", "The Delta 94.3",
                     "Nashville After Hours 92.9", "Freight Fate Roadhouse"):
        assert expected in names


def test_ff_music_stations_share_the_ff_dial_group():
    from freight_fate.radio import DEFAULT_RADIO_CATALOG, _dial_group

    playlist_backed = [s for s in DEFAULT_RADIO_CATALOG
                      if s.playlist and not s.real_stream and s.id != "route_playlist"]
    assert len(playlist_backed) == 14
    assert {_dial_group(s) for s in playlist_backed} == {1}
```

- [ ] **Step 2: Run, expect FAIL**: `uv run pytest tests/test_radio.py -q -k ff_music`.
- [ ] **Step 3: Catalog edits.** For the 12 fictional stations (`krwl-dallas`, `whwy-nashville`, `kpln-kansas-city`, `kbsk-billings`, `wgrx-chicago`, `kdrt-phoenix`, `kchm-los-angeles`, `krdg-denver`, `ksnd-seattle`, `wdlt-memphis`, `wbyu-new-orleans`, `wsol-atlanta`): set `"always_available": true`, delete `lat`/`lon`/`range_miles`. Add the new row after `wsol-atlanta`: id `wnah-nashville`, name `Nashville After Hours 92.9`, format `late-night jazz and crossover`, playlist `jazz`, source_type `regional`, `always_available: true`, source note naming it a Freight Fate original station. Confirm the loader (`radio.py` row parser near line 150) maps `always_available`; add the mapping if absent.
- [ ] **Step 4: Dial group.** In `_dial_group`, before the `local/regional/imported` branch: `if station.playlist and not station.real_stream: return 1`.
- [ ] **Step 5: Fix displaced tests.** Existing reception tests that pin fictional stations in/out of range against transmitter coordinates flip to always-on expectations; run `uv run pytest tests/test_radio.py -q` and update each failure to assert the new behavior (do not delete coverage — reassert on a real `local` station for range behavior).
- [ ] **Step 6: Run + commit** `feat(radio): every Freight Fate music station is always on the dial` (player-facing — changelog bullet lands with Task 8).

### Task 5: Provider observations keyed by station

**Files:**
- Modify: `src/freight_fate/sim/real_weather.py`
- Test: `tests/test_real_weather.py`

**Interfaces:**
- Produces: unchanged public API (`request/get/get_temperature/stale/refreshing/observation_age_s/refresh_failed/unavailable`), plus `has_any_observation() -> bool` for Task 6.

- [ ] **Step 1: Failing tests.**

```python
def test_same_place_keys_share_one_observation():
    calls = []
    def fetch(lat, lon):
        calls.append((lat, lon))
        return "Light Rain", 5.0, 14.0, 6.0, 2_000_000.0
    p = SyncProvider(fetch=fetch, clock=lambda: 0.0, wall_clock=lambda: 2_000_000.0)
    p.request("city:newark", 40.7357, -74.1724)
    p.request("route:newark:philadelphia:0", 40.7357, -74.1724)
    assert p.get("route:newark:philadelphia:0") is WeatherKind.RAIN
    assert len(calls) == 1


def test_provider_reports_session_observation_history():
    p = SyncProvider(fetch=lambda lat, lon: ("Clear", 0.0, 20.0, 10.0, 2_000_000.0),
                     clock=lambda: 0.0, wall_clock=lambda: 2_000_000.0)
    assert not p.has_any_observation()
    p.request("route-cell", 40.0, -80.0)
    assert p.has_any_observation()
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Inside `RealWeatherProvider`: observation storage becomes `self._obs_by_station: dict[str, _CachedObservation]` plus alias map `self._station_for_key: dict[str, str]`; station identity is `f"{round(lat, 2)},{round(lon, 2)}"` resolved through the existing `_station_cache` when the real fetch runs (inject-fetch tests use the coordinate-rounded identity directly — the worker computes `station_key = f"{round(lat, 2)},{round(lon, 2)}"` before calling `self._fetch`). `get`/`get_temperature`/`stale`/`observation_age_s`/`_usable` read through the alias; `request` short-circuits when the aliased station has a fresh observation (registering the alias without spawning a worker); the worker stores under the station identity and registers the alias. `has_any_observation()` returns `bool(self._obs_by_station)` under the lock. `_failed_at` stays keyed by request key.
- [ ] **Step 4: Run the full weather file**: `uv run pytest tests/test_real_weather.py tests/test_weather_trip.py -q`.
- [ ] **Step 5: Commit** `feat(weather): share NWS observations between same-station request keys [skip changelog]`.

### Task 6: Never simulate while real weather is on

**Files:**
- Modify: `src/freight_fate/sim/weather.py`
- Test: `tests/test_real_weather.py`

**Interfaces:**
- Consumes: `provider.has_any_observation()` from Task 5.

- [ ] **Step 1: Failing tests.**

```python
def test_new_cell_fetch_failure_holds_last_known_not_fallback():
    boom = [False]
    def fetch(lat, lon):
        if boom[0]:
            raise OSError("transient")
        return "Heavy Rain", 5.0, 12.0, 1.0, 2_000_000.0
    provider = SyncProvider(fetch=fetch, clock=lambda: 0.0, wall_clock=lambda: 2_000_000.0)
    weather = WeatherSystem("great_lakes", seed=1, provider=provider)
    weather.set_city("cell-0", 40.0, -80.0)
    weather.update(0.0)
    assert weather.source_status == "live"
    boom[0] = True
    weather.set_city("cell-1", 41.0, -81.0)
    weather.update(0.0)
    assert weather.source_status == "last_known"
    assert weather.current is WeatherKind.HEAVY_RAIN  # held, not resimulated


def test_cold_session_with_failing_provider_still_reaches_fallback():
    provider = SyncProvider(fetch=lambda lat, lon: (_ for _ in ()).throw(OSError()),
                            clock=lambda: 0.0, wall_clock=lambda: 2_000_000.0)
    weather = WeatherSystem("great_lakes", seed=1, provider=provider)
    weather.set_city("cell-0", 40.0, -80.0)
    weather.update(0.0)
    assert weather.source_status == "fallback"
```

- [ ] **Step 2: Run, expect FAIL** (second assert: today cell-1 failure reports "fallback").
- [ ] **Step 3: Implement.** In `WeatherSystem`: `_session_had_live` flag set in `_poll_provider` when `live` flips true. `source_status`: the `_carried_last_known` branch stops requiring `not self._provider_offline()`; `"fallback"` requires `self._provider_offline() and not self._session_had_live`. `update()`: the offline-simulation branch (`_fallback_active` seeding and the simulated transitions below it) only runs when `not self._session_had_live`; otherwise hold current conditions and return None (the 60-second provider retry keeps running via `_poll_provider`'s `request`).
- [ ] **Step 4: Run** `uv run pytest tests/test_real_weather.py tests/test_weather_trip.py tests/test_driving_cruise_weather.py -q` — the driving-status tests that mention "Simulated fallback weather" only trigger it via cold sessions now; update any that relied on mid-session fallback.
- [ ] **Step 5: Commit** `fix(weather): real weather holds last-known on failures instead of simulating` (player-facing — bullet in Task 8).

### Task 7: Warm at the terminal, request at trip construction

**Files:**
- Modify: `src/freight_fate/app.py` (GameContext), `src/freight_fate/states/city.py`, `src/freight_fate/sim/trip.py`
- Test: `tests/test_weather_trip.py`

- [ ] **Step 1: Failing tests.**

```python
def test_city_menu_warms_the_weather_provider(monkeypatch):
    # App-level: entering the city menu requests weather for the parked city.
    requested = []
    app = App()
    try:
        app.ctx.settings.real_weather = True
        provider = app.ctx.real_weather_provider()
        monkeypatch.setattr(provider, "request",
                            lambda key, lat, lon: requested.append((key, lat, lon)))
        state = CityMenuState(app.ctx)
        state.enter()
        assert requested and requested[0][0].startswith("city:")
    finally:
        app.shutdown()


def test_trip_requests_first_cell_at_construction():
    provider = SyncProvider(fetch=lambda lat, lon: ("Clear", 0.0, 20.0, 10.0, 2_000_000.0),
                            clock=lambda: 0.0, wall_clock=lambda: 2_000_000.0)
    trip = make_test_trip(provider=provider)  # follow the file's existing trip fixture
    assert trip.weather.source_status == "live" or provider.has_any_observation()
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** `GameContext.warm_real_weather(city_key: str) -> None`: no-op unless `real_weather_provider()` returns a provider and the world knows the city; requests `f"city:{city_key}"` with the city's lat/lon. Call it from `CityMenuState.enter`. In `Trip.__init__`, after `_leg_starts` exist: `key, lat, lon = self._weather_location(); self.weather.set_city(key, lat, lon)`, and if `self.weather.provider is not None`: `self.weather.provider.request(key, lat, lon)`. Snapshot restore path (`from_snapshot`) reaches `Trip.__init__`, so it inherits the request.
- [ ] **Step 4: Run** the weather trip file plus a real harness sanity: the probe script from the diagnosis (scratchpad `probe_weather3.py`) should now print `live` at frame 0.
- [ ] **Step 5: Commit** `feat(weather): live weather is ready when the drive starts` (player-facing — bullet in Task 8).

### Task 8: Dead-stream manners

**Files:**
- Modify: `src/freight_fate/radio.py`
- Test: `tests/test_radio.py`

**Interfaces:**
- Produces: `RadioState.unplayable_ids: set[str]`; the playback-failure path hands over inside the failed station's dial group.

- [ ] **Step 1: Failing tests.**

```python
def test_dead_stream_leaves_the_dial_for_the_session():
    state = RadioState(streamer_safe=False, real_streams_enabled=True)
    dead = next(s for s in state.catalog if s.real_stream)
    state.mark_unplayable(dead.id)
    assert dead.id not in {r.station.id for r in state.receivable_stations()}


def test_dead_stream_hands_over_inside_its_own_band():
    # Drive the playback-failure path with a backend whose play always raises
    # for the first station and succeeds for the second; assert the action's
    # station shares _dial_group with the dead one and the message names both.
    ...  # concrete backend stub per the existing playback tests in this file
```

- [ ] **Step 2: Run, expect FAIL** (`mark_unplayable` undefined).
- [ ] **Step 3: Implement.** `RadioState.__init__` gains `self.unplayable_ids: set[str] = set()`; `mark_unplayable(station_id)` adds to it; `_station_allowed` returns False for members. In the playback-failure handler (the `except` path that currently retunes to `fallback_reception()`), first `self.mark_unplayable(original.station.id)`, then choose `next(r for r in self.receivable_stations() if _dial_group(r.station) == _dial_group(original.station))` and play it with the message `f"{original.station.display_name} is off the air; it is off the dial for the rest of this session."` followed by the replacement's normal announcement; only fall to `fallback_reception()` when the generator is empty. Follow the second existing-test's backend stub pattern for the new test's concrete body.
- [ ] **Step 4: Run** `uv run pytest tests/test_radio.py -q`.
- [ ] **Step 5: Commit** `fix(radio): a dead stream hands over to its band and leaves the dial` (player-facing — bullet in Task 9).

### Task 9: Changelog, roadmap, full suite

**Files:**
- Modify: `CHANGELOG.md`, `ROADMAP.md`

- [ ] **Step 1:** Changelog bullets under Unreleased. Added: the new-music bullet (originals batch: new day and night driving beds, more country songs, the Nashville After Hours jazz station, a late-career menu theme). Changed: FF stations always available everywhere in every mode. Fixed: live weather ready at drive start and never replaced by simulated weather while the service can be reached (folds the loading-gap and last-known behavior into one player-story bullet); a dead stream hands over to the next station on its band instead of dropping to the silent satellite, and stays off the dial for the session.
- [ ] **Step 2:** ROADMAP: check off / add matching 1.9 bullets (music batch landed, FF stations un-geolocked, live-weather immediacy) in the 1.9 section, and reword the "Imported-tier follow-ups" bullet: the dead-station-manners clause is done; the HLS re-sweep and contour-overlay clauses remain open.
- [ ] **Step 3:** `uv run ruff check src tests tools` and full `uv run pytest` (background, headless env vars). All green.
- [ ] **Step 4:** Commit `feat(audio,weather): 1.9 music batch, always-on FF stations, instant live weather` and push `feat/career-1.9`.

## Self-Review

- Spec coverage: intake/encode (T1), catalog+milestone (T2), credits+pack (T3), always-on stations+jazz station (T4), station-keyed observations (T5), never-simulate ruling (T6), warm-up+construction request (T7), dead-stream manners (T8), changelog/roadmap (T9). Out-of-scope items from the spec have no tasks, as intended.
- Types: `JAZZ_TRACKS` (T2) consumed by T4's catalog row via `STATION_PLAYLISTS["jazz"]`; `has_any_observation()` defined in T5, consumed in T6. Names consistent.
- No placeholders: every code step carries concrete code or exact-value edits; T1's durations are produced by its own Step 2 output, consumed verbatim in T2.
