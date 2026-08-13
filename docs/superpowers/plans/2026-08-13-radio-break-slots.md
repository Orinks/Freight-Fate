# Radio Break-Slot Machinery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize the playlist stations' every-2-songs host break into break slots that cycle host / station ID / commercial-then-ID, ready for the per-station content the generation plan will bake.

**Architecture:** A new `radio_content.py` module owns per-station host, ID, and ad tables plus deterministic break planning; `driving_updates.py` swaps its single-host rotation for a small break queue. Ships working against today's assets (FFR/FFN hosts only) — empty pools degrade to exactly today's behavior.

**Tech Stack:** Python 3.12, pytest, `zlib.crc32` deterministic shuffles (house pattern).

Spec: `docs/superpowers/specs/2026-08-13-debt-dealer-radio-design.md` section C (scheduler + code layout).

## Global Constraints

- Branch `feat/debt-dealer-radio`; commits `[skip changelog]` except the final one (the changelog entry for the whole radio feature lands in the generation plan; THIS plan is all `[skip changelog]` — machinery with no player-visible change until content exists... except FFR/FFN hosts keep playing, which is behavior-preserving).
- Reception-physics and radio tests use fixtures, never catalog stations.
- Audio keys are an asset contract (Freight Fate Rail consumes them): existing `host_roadhouse_NN` / `host_nightline_NN` keys must not change.
- `music.py` stays under 1000 lines; new tables go in `radio_content.py`.
- Determinism: no `random`, no time-of-day seeds — `zlib.crc32(f"{seed_key}|{key}")` ordering only.

---

### Task 1: `radio_content.py` — tables and duration lookup

**Files:**
- Create: `src/freight_fate/radio_content.py`
- Test: Create `tests/test_radio_breaks.py`

**Interfaces:**
- Consumes: `MusicTrack`, `STATION_HOST_SEGMENTS`, `music_track_duration_s` from `freight_fate.music`.
- Produces:
  - `STATION_IDS: dict[str, tuple[MusicTrack, ...]]` (keyed by the catalog `host` field value; empty for now)
  - `AD_SPOTS: tuple[MusicTrack, ...]` (empty for now)
  - `AD_FORMAT_TAGS: dict[str, tuple[str, ...]]` (ad key -> playlist keys it fits; empty)
  - `BREAK_PATTERN: tuple[str, ...] = ("host", "id", "host", "ad_id")`
  - `content_duration_s(key: str) -> float`
  - `station_ads(playlist: str) -> tuple[MusicTrack, ...]`

- [ ] **Step 1: Failing tests:**

```python
from freight_fate import radio_content
from freight_fate.music import MusicTrack


def test_content_duration_falls_back_to_music_catalog():
    # host_roadhouse_01 lives in music.py's host tables today
    assert radio_content.content_duration_s("host_roadhouse_01") > 0
    assert radio_content.content_duration_s("no_such_key") == 60.0


def test_station_ads_filters_by_format_tag(monkeypatch):
    spots = (
        MusicTrack("ad_test_tires", "Tire ad", "test", 22.0),
        MusicTrack("ad_test_diner", "Diner ad", "test", 25.0),
    )
    monkeypatch.setattr(radio_content, "AD_SPOTS", spots)
    monkeypatch.setattr(
        radio_content, "AD_FORMAT_TAGS",
        {"ad_test_tires": ("country",), "ad_test_diner": ("country", "blues")},
    )
    assert [t.key for t in radio_content.station_ads("blues")] == ["ad_test_diner"]
    assert len(radio_content.station_ads("country")) == 2
    assert radio_content.station_ads("jazz") == ()
```

- [ ] **Step 2: Run `uv run pytest tests/test_radio_breaks.py -p no:xdist -q`, verify ImportError.**
- [ ] **Step 3: Implement:**

```python
"""Per-station radio identity content: IDs, ads, and break planning.

Tables are filled by the generation pass (tools/generate_radio.py); until
then they are empty and every consumer degrades to plain host breaks. Keys
follow the asset contract: host_<station>_NN, id_<station>_NN, ad_<slug>.
"""

from __future__ import annotations

import zlib

from .music import MusicTrack, music_track_duration_s

STATION_IDS: dict[str, tuple[MusicTrack, ...]] = {}
AD_SPOTS: tuple[MusicTrack, ...] = ()
AD_FORMAT_TAGS: dict[str, tuple[str, ...]] = {}

# One break after every 2 songs; break content cycles this pattern. An
# ad never runs without an ID chasing it back into music, so ads are
# never adjacent and an ID lands at least once per four breaks.
BREAK_PATTERN: tuple[str, ...] = ("host", "id", "host", "ad_id")

_LOCAL_BY_KEY: dict[str, MusicTrack] = {}


def _reindex() -> None:
    _LOCAL_BY_KEY.clear()
    for pool in STATION_IDS.values():
        _LOCAL_BY_KEY.update({t.key: t for t in pool})
    _LOCAL_BY_KEY.update({t.key: t for t in AD_SPOTS})


_reindex()


def content_duration_s(key: str) -> float:
    track = _LOCAL_BY_KEY.get(key)
    if track is not None:
        return track.duration_s
    return music_track_duration_s(key)


def station_ads(playlist: str) -> tuple[MusicTrack, ...]:
    return tuple(
        spot for spot in AD_SPOTS if playlist in AD_FORMAT_TAGS.get(spot.key, ())
    )
```

(Module-level `monkeypatch.setattr` in the tests bypasses `_reindex`; that is fine — `content_duration_s` is exercised against the real tables, `station_ads` against patched ones.)

- [ ] **Step 4: Run, verify passes.**
- [ ] **Step 5: Commit** `feat(radio): radio_content module for station identity [skip changelog]`

---

### Task 2: Deterministic break planning

**Files:**
- Modify: `src/freight_fate/radio_content.py`
- Test: `tests/test_radio_breaks.py`

**Interfaces:**
- Produces: `plan_break(host: str, playlist: str, seed_key: str, break_index: int) -> tuple[str, ...]` — asset keys for one break slot, possibly empty.

- [ ] **Step 1: Failing tests:**

```python
def _patched_pools(monkeypatch):
    hosts = tuple(MusicTrack(f"host_x_{i:02d}", f"h{i}", "", 5.0) for i in range(1, 9))
    ids = tuple(MusicTrack(f"id_x_{i:02d}", f"i{i}", "", 10.0) for i in range(1, 4))
    ads = tuple(MusicTrack(f"ad_y_{i:02d}", f"a{i}", "", 25.0) for i in range(1, 5))
    monkeypatch.setattr(
        "freight_fate.music.STATION_HOST_SEGMENTS", {"x": hosts}, raising=False
    )
    monkeypatch.setattr(radio_content, "STATION_IDS", {"x": ids})
    monkeypatch.setattr(radio_content, "AD_SPOTS", ads)
    monkeypatch.setattr(
        radio_content, "AD_FORMAT_TAGS", {t.key: ("country",) for t in ads}
    )


def test_break_pattern_cycles_and_is_deterministic(monkeypatch):
    _patched_pools(monkeypatch)
    kinds = []
    for i in range(8):
        first = radio_content.plan_break("x", "country", "seed", i)
        assert first == radio_content.plan_break("x", "country", "seed", i)
        kinds.append(first)
    # pattern: host, id, host, ad_id, repeated
    assert kinds[0][0].startswith("host_")
    assert kinds[1][0].startswith("id_")
    assert kinds[3][0].startswith("ad_") and kinds[3][1].startswith("id_")
    assert kinds[4] == kinds[0] or kinds[4][0].startswith("host_")


def test_break_slots_degrade_when_pools_missing(monkeypatch):
    _patched_pools(monkeypatch)
    monkeypatch.setattr(radio_content, "STATION_IDS", {})
    monkeypatch.setattr(radio_content, "AD_SPOTS", ())
    # id and ad slots fall back to a host break; still never empty for a
    # station that has a host
    for i in range(4):
        elems = radio_content.plan_break("x", "country", "seed", i)
        assert elems and elems[0].startswith("host_")
    # and a station with no host at all gets no break
    assert radio_content.plan_break("", "country", "seed", 0) == ()
```

- [ ] **Step 2: Run, verify fails.**
- [ ] **Step 3: Implement:**

```python
def _pick(pool: tuple[MusicTrack, ...], seed_key: str, index: int) -> str:
    ordered = sorted(
        pool, key=lambda t: zlib.crc32(f"{seed_key}|{t.key}".encode())
    )
    return ordered[index % len(ordered)].key


def plan_break(host: str, playlist: str, seed_key: str, break_index: int) -> tuple[str, ...]:
    """Asset keys for one break slot. Empty when the station has no voice.

    Slot kinds cycle BREAK_PATTERN; a kind whose pool is empty falls back
    to a host break so the cadence the player learned never stutters.
    """
    from .music import STATION_HOST_SEGMENTS

    hosts = STATION_HOST_SEGMENTS.get(host, ())
    if not hosts:
        return ()
    kind = BREAK_PATTERN[break_index % len(BREAK_PATTERN)]
    ids = STATION_IDS.get(host, ())
    ads = station_ads(playlist)
    if kind == "id" and ids:
        return (_pick(ids, f"{seed_key}|id", break_index),)
    if kind == "ad_id" and ads and ids:
        return (
            _pick(ads, f"{seed_key}|ad", break_index),
            _pick(ids, f"{seed_key}|tag", break_index),
        )
    return (_pick(hosts, f"{seed_key}|host", break_index),)
```

- [ ] **Step 4: Run, verify passes.**
- [ ] **Step 5: Commit** `feat(radio): deterministic break planning [skip changelog]`

---

### Task 3: Scheduler swap in `driving_updates.py`

**Files:**
- Modify: `src/freight_fate/states/driving_updates.py` (`_start_station_rotation` ~line 1948, `_update_radio_playback` ~line 1962)
- Modify: `src/freight_fate/states/driving_core.py` (imports)
- Test: `tests/test_radio_breaks.py` (and keep `tests/test_music_selection.py`, `tests/test_radio_regional.py` green)

**Interfaces:**
- Consumes: `radio_content.plan_break`, `radio_content.content_duration_s`.
- Produces: instance fields `_radio_break_queue: tuple[str, ...]`, `_radio_break_pos: int`, `_radio_break_count: int` replacing `_radio_playing_host` / `_radio_hosts` / `_radio_host_index`.

- [ ] **Step 1: Failing test** — drive the rotation logic the way existing radio tests do (find the harness in `tests/test_radio_regional.py` that steps `_update_radio_playback` with a fixture station; reuse it). Assert: with a fixture station whose host has pools patched in (Task 2's `_patched_pools`), after 2 songs the next played key is a host, after 4 songs an ID appears, after 8 an ad plays followed by an ID, then music resumes. With all pools empty and no host, songs chain without any break (today's no-host behavior).
- [ ] **Step 2: Run, verify fails.**
- [ ] **Step 3: Implement.** In `_start_station_rotation`, replace the host lines with:

```python
self._radio_break_queue: tuple[str, ...] = ()
self._radio_break_pos = 0
self._radio_break_count = 0
self._radio_tracks_since_break = 0
```

In `_update_radio_playback`, replace the host-branch block (the `_radio_playing_host` reads, the `>= RADIO_TRACKS_PER_HOST_BREAK` dispatch) with:

```python
if self._radio_break_queue:
    current = self._radio_break_queue[self._radio_break_pos]
else:
    current = self._radio_playlist[self._radio_track_index % len(self._radio_playlist)]
if self._radio_elapsed_s < content_duration_s(current):
    return
self._radio_elapsed_s = 0.0
if self._radio_break_queue:
    self._radio_break_pos += 1
    if self._radio_break_pos < len(self._radio_break_queue):
        self.ctx.audio.play_music(
            self._radio_break_queue[self._radio_break_pos], fade_ms=300
        )
        return
    self._radio_break_queue = ()
    self._play_station_track(fade_ms=1200)
    return
self._radio_track_index += 1
self._radio_tracks_since_break += 1
if self._radio_tracks_since_break >= RADIO_TRACKS_PER_HOST_BREAK:
    queue = plan_break(
        station.host,
        station.playlist,
        f"{self.trip_seed}|{station.id}",
        self._radio_break_count,
    )
    self._radio_tracks_since_break = 0
    if queue:
        self._radio_break_queue = queue
        self._radio_break_pos = 0
        self._radio_break_count += 1
        self.ctx.audio.play_music(queue[0], fade_ms=600)
        return
self._play_station_track(fade_ms=2500)
```

Imports move through `driving_core.py` the way `select_host_segments` does today (add `plan_break`/`content_duration_s`, delete `select_host_segments` import if now unused there). Sweep for other readers of the deleted fields (`grep -rn "_radio_playing_host\|_radio_hosts\|_radio_host_index" src/`) — the drivers-board presence or pause states may read them; update those readers to `bool(self._radio_break_queue)`.

- [ ] **Step 4: Run the radio-adjacent files via the test-runner agent:** `uv run pytest tests/test_radio_breaks.py tests/test_radio_regional.py tests/test_music_selection.py tests/test_radio.py -p no:xdist -q`.
- [ ] **Step 5: Commit** `feat(radio): break slots replace the single host rotation [skip changelog]`

---

### Task 4: Catalog consistency test + full suite

**Files:**
- Modify: `tests/test_radio_breaks.py`

- [ ] **Step 1: Add the standing consistency test** (it guards the generation plan's data fills):

```python
def test_station_content_tables_resolve():
    import json
    from pathlib import Path

    from freight_fate import radio_content
    from freight_fate.music import STATION_HOST_SEGMENTS, STATION_PLAYLISTS

    catalog = json.loads(
        Path("src/freight_fate/data/radio_catalog.json").read_text(encoding="utf-8")
    )
    for row in catalog["stations"]:
        if row.get("playlist"):
            assert row["playlist"] in ("route",) or row["playlist"] in STATION_PLAYLISTS
        if row.get("host"):
            assert row["host"] in STATION_HOST_SEGMENTS, row["id"]
    keys = [t.key for pool in radio_content.STATION_IDS.values() for t in pool]
    keys += [t.key for t in radio_content.AD_SPOTS]
    assert len(keys) == len(set(keys))
    assert all(radio_content.content_duration_s(k) > 0 for k in keys)
    assert set(radio_content.AD_FORMAT_TAGS) <= {t.key for t in radio_content.AD_SPOTS} | set(radio_content.AD_FORMAT_TAGS)
    for tags in radio_content.AD_FORMAT_TAGS.values():
        assert all(tag in STATION_PLAYLISTS for tag in tags)
```

- [ ] **Step 2: Run it, verify passes now (tables empty).**
- [ ] **Step 3: Full suite via the test-runner agent** (`uv run pytest`, `uv run ruff check src tests tools`).
- [ ] **Step 4: Commit** `test(radio): station content consistency guard [skip changelog]`
