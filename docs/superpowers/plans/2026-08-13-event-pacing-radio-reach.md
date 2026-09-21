# Event Pacing and Radio Reach Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Routine road announcements get real-seconds breathing gaps; radio stations stay clean through most of their contour and reach twice as far — per `docs/superpowers/specs/2026-08-13-event-pacing-radio-reach-design.md`.

**Architecture:** A small clock-injected `RoadEventBreather` (new module `sim/road_event_pacing.py`) gates the three routine talkers at their source — the gate is checked BEFORE state mutation, so when a window opens the next natural check announces the *current* state (supersede-for-free, no pending storage). Radio changes are constants plus one reach helper in `radio.py`.

**Tech Stack:** Python 3.12, pytest via `uv run`, `time.monotonic` behind an injected clock.

## Global Constraints

- All pytest invocations go through the **test-runner agent**; env `FREIGHT_FATE_NO_SPEECH=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`, serial `-n 0 -q -p no:cacheprovider` unless a step says otherwise. NEVER bare `uv run pytest` or `-n auto` from an implementer.
- Gaps are REAL seconds (wall clock), never game time: this is the whole point. Tests inject a fake clock; never `time.sleep`.
- Never gate: hazard/AEB lines, curve advisories/pacenotes, weigh-station and planned-stop calls, navigation maneuvers, enforcement lines, merge/closure warnings, or answers to player keys. The three gated categories are exactly: posted-limit arrival lines, NPC traffic situation calls, zone-entry colour lines.
- A NOT-preannounced limit DROP of more than 10 mph speaks immediately (ticket-relevant); everything else in its category waits.
- Radio: the smear-into-static owner ruling (2026-07-24) must survive — static rises TO program level at the edge, never on top of a loud one. Reception-physics tests use fixtures, NOT catalog stations.
- Intermediate commits touching `src/` carry `[skip changelog]`; the final task adds the CHANGELOG entry.
- `uv run ruff check src tests` before each commit; pre-commit may reformat — re-stage and commit again.
- Match surrounding idiom (prose why-comments; this codebase documents tester context at the definition).

## File Structure

- Create: `src/freight_fate/sim/road_event_pacing.py` — the breather (pure, clock-injected).
- Modify: `src/freight_fate/sim/trip.py` — `_check_speed_limit` (~2457) gains the gate; the `ZONE_ENTER` emit (~2416) gains the gate; Trip `__init__` constructs `self._event_breather`.
- Modify: `src/freight_fate/sim/trip_traffic.py` — `_check_npc_traffic_cues` (~69) gains the gate BEFORE `next_situation` is called (calling it marks vehicles announced, so a gated call must not happen at all).
- Modify: `src/freight_fate/radio.py` — thresholds (~476-479), reach helper feeding `effective_range_miles` (~441) and `estimate_signal` (~448).
- Create: `tests/test_road_event_pacing.py`. Modify: radio tests that pin the old thresholds (find them in Task 4; expect `tests/test_radio.py`, `tests/test_radio_multi_site.py`, `tests/test_radio_engine_power.py`).

---

### Task 1: The breather

**Files:**
- Create: `src/freight_fate/sim/road_event_pacing.py`
- Test: `tests/test_road_event_pacing.py` (create)

**Interfaces:**
- Produces (Tasks 2-3 consume):

```python
LIMIT_GAP_REAL_S = 12.0
TRAFFIC_GAP_REAL_S = 10.0
ZONE_GAP_REAL_S = 15.0

class RoadEventBreather:
    def __init__(self, clock=time.monotonic) -> None: ...
    def ready(self, category: str) -> bool:
        """Whether this category's window is open. Does NOT consume."""
    def spoke(self, category: str) -> None:
        """Record that the category just spoke; closes the window."""
```

Two methods, not one, because the callers decide to speak from their own state; `ready()` in the guard clause and `spoke()` beside the emit keeps the gate readable at the call site.

- [ ] **Step 1: Write the failing tests**

```python
"""Real-seconds breathing gaps for the routine road talkers.

Owner report 2026-08-13: in every driving mode the routine events -- limit
changes, traffic calls, zone chatter -- arrive back to back, because time
compression spends road 10-40x faster than a real cab and each system
announces on road distance. The owner kept the clock (career pacing is
balanced on it) and chose to space the ANNOUNCEMENTS in real seconds, the
same law the corner warnings already follow. Mechanics are untouched:
limits still bind, cruise still follows; only the narration breathes.
"""

import pytest

from freight_fate.sim.road_event_pacing import (
    LIMIT_GAP_REAL_S,
    TRAFFIC_GAP_REAL_S,
    ZONE_GAP_REAL_S,
    RoadEventBreather,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_first_line_of_a_category_is_always_ready():
    b = RoadEventBreather(clock=FakeClock())
    assert b.ready("limit")
    assert b.ready("traffic")
    assert b.ready("zone")


def test_speaking_closes_the_window_for_the_gap():
    clock = FakeClock()
    b = RoadEventBreather(clock=clock)
    b.spoke("limit")
    clock.now += LIMIT_GAP_REAL_S - 0.5
    assert not b.ready("limit")
    clock.now += 1.0
    assert b.ready("limit")


def test_categories_are_independent():
    clock = FakeClock()
    b = RoadEventBreather(clock=clock)
    b.spoke("limit")
    assert b.ready("traffic")
    assert b.ready("zone")


def test_ready_never_consumes():
    b = RoadEventBreather(clock=FakeClock())
    assert b.ready("limit")
    assert b.ready("limit")  # polling twice is not speaking twice


def test_gap_constants_are_real_seconds_apart():
    # The gaps are the design's numbers; a drive-by refactor that halves
    # them silently reintroduces the chatter this exists to kill.
    assert LIMIT_GAP_REAL_S == pytest.approx(12.0)
    assert TRAFFIC_GAP_REAL_S == pytest.approx(10.0)
    assert ZONE_GAP_REAL_S == pytest.approx(15.0)
```

- [ ] **Step 2: Run to verify failure** — test-runner: `uv run pytest tests/test_road_event_pacing.py -n 0 -q -p no:cacheprovider`. Expected: FAIL, module not found.

- [ ] **Step 3: Implement** `src/freight_fate/sim/road_event_pacing.py`:

```python
"""Real-seconds breathing gaps for the routine road talkers.

Time compression spends road 10-40x faster than a real cab, so systems
that announce on road distance -- posted-limit arrivals, traffic calls,
zone chatter -- pile their lines back to back in every driving mode
(owner report, 2026-08-13). The clock stays (career pacing is balanced
on it); the ANNOUNCEMENTS space out instead, in wall-clock seconds, the
same law the corner warnings and the keeper's ease already follow.

The gate lives at the SOURCE, before any state mutates: a caller that
finds its window shut simply does nothing, and the next natural check
after the window opens announces the CURRENT state. Superseding is free
-- nothing is held, so nothing goes stale.

Safety and action lines never come here: hazards, AEB, pacenotes, scale
and stop calls, maneuvers, enforcement, merge warnings, and every answer
to a player's key speak immediately, always.
"""

from __future__ import annotations

import time

LIMIT_GAP_REAL_S = 12.0  # posted-limit arrival lines
TRAFFIC_GAP_REAL_S = 10.0  # NPC traffic situation calls
ZONE_GAP_REAL_S = 15.0  # zone-entry colour

_GAPS = {
    "limit": LIMIT_GAP_REAL_S,
    "traffic": TRAFFIC_GAP_REAL_S,
    "zone": ZONE_GAP_REAL_S,
}


class RoadEventBreather:
    """One window per category, measured on the wall clock."""

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._last_spoke: dict[str, float] = {}

    def ready(self, category: str) -> bool:
        last = self._last_spoke.get(category)
        return last is None or self._clock() - last >= _GAPS[category]

    def spoke(self, category: str) -> None:
        self._last_spoke[category] = self._clock()
```

- [ ] **Step 4: Run to verify pass** (same command). Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/freight_fate/sim/road_event_pacing.py tests/test_road_event_pacing.py
git commit -m "feat(speech): real-seconds breather for the routine road talkers [skip changelog]"
```

---

### Task 2: Gate the posted-limit arrival line

**Files:**
- Modify: `src/freight_fate/sim/trip.py` — `__init__` (find where other `self._announced_*` state initializes) and `_check_speed_limit` (~2457)
- Test: `tests/test_road_event_pacing.py`

**Interfaces:**
- Consumes: `RoadEventBreather` from Task 1 — Trip gains `self._event_breather = RoadEventBreather()` in `__init__` (import at the top with the other sim imports).
- Produces: gating semantics Tasks 3 relies on matching.

- [ ] **Step 1: Read `_check_speed_limit` in full** (trip.py:2457-2502) including the preannounce-consumption branch — the gate must sit AFTER the `limit != announced` comparison and BEFORE any mutation, so a gated change leaves `_announced_speed_limit` and `_limit_drop_preannounced` untouched and the next check self-supersedes.

- [ ] **Step 2: Write the failing tests** (append; build a Trip the way existing trip tests do — find a lightweight Trip construction in `tests/test_weather_trip.py` or `tests/test_interchanges.py` and reuse its fixture pattern; monkeypatch `trip._event_breather._clock` with FakeClock):

```python
def test_two_limit_changes_inside_the_gap_speak_once_with_the_newest(...):
    # Drive the trip across a posting change; capture the emitted GPS_CUE.
    # Then, 3 fake-clock seconds later, cross a second change. Assert only
    # the FIRST spoke; advance the fake clock past LIMIT_GAP_REAL_S, run
    # _check_speed_limit again, and assert the line that now speaks names
    # the CURRENT posting (the second change), not the missed one.
    ...

def test_a_limit_bounce_inside_the_gap_never_speaks(...):
    # Change 55 -> 45 (spoken), then within the gap 45 -> 55 back. After
    # the window opens, _check_speed_limit finds current == last spoken
    # and says nothing. This is the owner's "dropping and coming straight
    # back" complaint staying dead under the gate.
    ...

def test_a_big_unannounced_drop_cuts_the_gap(...):
    # Speak a change; 2 fake seconds later drop 65 -> 45 (>10 mph, not
    # preannounced). It must speak IMMEDIATELY despite the closed window.
    ...
```

Write these as full tests against the real Trip fixture (the sketch above states the required behavior; the fixture mechanics come from the file you copied). Emitted lines are observed the way neighbouring trip tests observe `TripEventKind.GPS_CUE`.

- [ ] **Step 3: Run to verify the first two fail** (limit lines currently speak every change). The big-drop test may pass by accident (no gate exists yet) — that is expected; it pins the exemption so Task 2's gate cannot break it.

- [ ] **Step 4: Implement.** In `_check_speed_limit`, after computing `lowered` and before ANY mutation:

```python
        if limit != self._announced_speed_limit:
            lowered = limit < self._announced_speed_limit
            # Routine changes breathe (see road_event_pacing); a serious
            # unannounced drop does not wait -- it is ticket-relevant now.
            urgent = (
                lowered
                and self._announced_speed_limit - limit > 10.0
                and round(limit, 1) not in self._limit_drop_preannounced
            )
            if not urgent and not self._event_breather.ready("limit"):
                return  # untouched state; the next check self-supersedes
            self._announced_speed_limit = limit
            ...existing body unchanged...
            self._event_breather.spoke("limit")
            self._emit(
                TripEventKind.GPS_CUE,
                f"Speed limit {verb} {self._speed_value(limit)}{where}{span}.",
            )
```

(`spoke()` goes beside the `_emit`, after the preannounce-consumption `return` — a consumed preannounce spoke through the assist already and must ALSO close the window? No: the assist's line was the assist's; consuming it costs no new speech, so do NOT call `spoke()` on that path. Only a line this method actually emits closes the window.)

- [ ] **Step 5: Run the file plus the trip suites** — test-runner: `uv run pytest tests/test_road_event_pacing.py tests/test_weather_trip.py tests/test_interchanges.py -n 0 -q -p no:cacheprovider`. Existing tests that cross several postings quickly may now see fewer lines — read each failure: if it asserts per-change lines with no real-clock control, give that test a FakeClock advanced past the gap between changes (test adjustment, justified in the report), never weaken its assertions.

- [ ] **Step 6: Commit**

```bash
git add src/freight_fate/sim/trip.py tests/test_road_event_pacing.py
git commit -m "feat(speech): posted-limit arrivals breathe, serious drops cut in line [skip changelog]"
```

---

### Task 3: Gate traffic calls and zone-entry colour

**Files:**
- Modify: `src/freight_fate/sim/trip_traffic.py:69-80` (`_check_npc_traffic_cues`)
- Modify: `src/freight_fate/sim/trip.py` ~2416 (the `ZONE_ENTER` emit)
- Test: `tests/test_road_event_pacing.py`

**Interfaces:**
- Consumes: `self._event_breather` on Trip (Task 2), categories `"traffic"` and `"zone"`.

- [ ] **Step 1: Write the failing tests** (same fixture pattern as Task 2):

```python
def test_two_traffic_situations_inside_the_gap_speak_once(...):
    # Two announceable lead vehicles reach the 2.2-mile window 3 fake
    # seconds apart. One traffic line speaks. After TRAFFIC_GAP_REAL_S
    # the next check announces the CURRENT nearest situation. Crucially:
    # the gated vehicle is NOT in announced_vehicle_keys (the gate must
    # sit before next_situation, which marks keys as consumed).
    ...

def test_zone_entry_colour_breathes_but_merge_warnings_do_not(...):
    # Enter two zones 3 fake seconds apart: one colour line. Then assert
    # the construction merge warning path (the work-zone closure system)
    # is NOT routed through the breather -- fire it inside a closed
    # window and it still speaks.
    ...
```

- [ ] **Step 2: Run to verify both fail.**

- [ ] **Step 3: Implement.**

`trip_traffic.py` — gate before the manager call:

```python
    def _check_npc_traffic_cues(self) -> None:
        # Gate BEFORE next_situation: returning a situation marks its
        # vehicle announced, so a gated call would burn the announcement
        # without speaking it and the vehicle would stay silent forever.
        if not self._event_breather.ready("traffic"):
            return
        situation = self.traffic_manager.next_situation(
            position_mi=self.position_mi,
            truck_speed_mph=self.truck.speed_mph,
        )
        if situation is None:
            return
        self._event_breather.spoke("traffic")
        ...existing emit unchanged...
```

`trip.py` ZONE_ENTER — read the surrounding block first; wrap only the colour emit: `ready("zone")` in the guard, `spoke("zone")` beside the emit. The merge/closure warnings live in the driving state's work-zone system, not this emit — touch nothing there.

- [ ] **Step 4: Run** — test-runner: `uv run pytest tests/test_road_event_pacing.py tests/test_weather_trip.py tests/test_world_overlay.py -n 0 -q -p no:cacheprovider` plus whatever suite covers zone entries (grep tests for `ZONE_ENTER`). Same repair rule as Task 2 for quick-succession tests.

- [ ] **Step 5: Commit**

```bash
git add src/freight_fate/sim/trip_traffic.py src/freight_fate/sim/trip.py tests/test_road_event_pacing.py
git commit -m "feat(speech): traffic calls and zone colour breathe [skip changelog]"
```

---

### Task 4: Radio contours hold clean and reach farther

**Files:**
- Modify: `src/freight_fate/radio.py` (~441-479)
- Test: existing radio suites; add cases to whichever file already tests `signal_volume_factor` / `estimate_signal` (grep `tests/` for those names — expected `tests/test_radio.py` and `tests/test_radio_multi_site.py`)

**Interfaces:** none forward — constants and one helper, all inside radio.py.

- [ ] **Step 1: Write/adjust the failing tests.** Existing threshold tests encode the old requirement — update them BEFORE touching source (that is the RED), asserting:

- clean program (`signal_volume_factor == 1.0`) at 80% of contour distance;
- fading (factor < 1.0) past 85%;
- static engaged only in the outer edge (below the new `STATIC_SIGNAL_THRESHOLD` signal);
- `effective_range_miles` returns `range_miles * RADIO_REACH_MULT` (+ elevation lift when applicable);
- always-available and range-less stations byte-identically unchanged (factor 1.0, "built-in").

Use fixture stations per the radio test contract, e.g. `range_miles=40.0` → clean through 64 game-miles (80% of 80), fringing past ~68.

- [ ] **Step 2: Run to verify RED** — test-runner: `uv run pytest tests/test_radio.py tests/test_radio_multi_site.py tests/test_radio_engine_power.py -n 0 -q -p no:cacheprovider`.

- [ ] **Step 3: Implement** in `radio.py`:

```python
# Compression compensation for ranged stations (owner design 2026-08-13):
# the truck spends road miles 10-40x faster than a real cab, so a real
# 40-mile FM contour was two real minutes of program. Doubling the reach
# keeps radio regional (no station spans three states) while a median
# station now survives about seven real minutes at Relaxed. Applied in
# _reach_mi so every consumer -- range check, signal curve, elevation
# lift -- agrees on one number.
RADIO_REACH_MULT = 2.0


def _reach_mi(station: RadioStation) -> float:
    return station.range_miles * RADIO_REACH_MULT
```

Use `_reach_mi(station)` in BOTH branches of `effective_range_miles` (the no-elevation early return currently returns `station.range_miles` raw) and audit every other direct read of `station.range_miles` in radio.py and the states (grep) — the `<= 0` sentinel checks stay on the raw field; distance math moves to `_reach_mi`.

Rethreshold the curve (keep the comment block's ruling text, update the numbers and the rationale):

```python
SIGNAL_FULL_VOLUME = 0.20  # clean program through ~85% of the contour
SIGNAL_FRINGE_FLOOR = 0.3
SIGNAL_DEEP_FLOOR = 0.08
STATIC_SIGNAL_THRESHOLD = 0.12  # static smear lives in the outer edge only
```

Verify by hand in the report: `signal_volume_factor` stays continuous and monotonic at the new joins (signal 0.20 → factor 1.0; signal 0.12 → the fringe formula's value; below → sinking toward the deep floor), and the smear still goes TO program level.

- [ ] **Step 4: Run all radio suites** — test-runner: `uv run pytest tests/test_radio.py tests/test_radio_multi_site.py tests/test_radio_engine_power.py tests/test_radio_regional.py tests/test_radio_imported.py tests/test_radio_playlists.py tests/test_radio_favorites.py tests/test_radio_streaming.py -n 0 -q -p no:cacheprovider`. Expected: green after justified expectation updates only.

- [ ] **Step 5: Commit**

```bash
git add src/freight_fate/radio.py tests/
git commit -m "feat(radio): contours hold clean through 85 percent and reach twice as far [skip changelog]"
```

---

### Task 5: Changelog, roadmap, full verification

**Files:**
- Modify: `CHANGELOG.md` (`## Unreleased` → `### Changed`, first bullets)
- Modify: `ROADMAP.md` (beside the `landed 2026-08-13` entries)

- [ ] **Step 1: CHANGELOG bullets** (verbatim, screen-reader audience):

```markdown
- **The road talks at a human pace now.** Speed limit changes, traffic
  calls, and zone chatter used to arrive back to back, because the
  game's fast clock packs a lot of road into every real minute. Routine
  announcements now keep a few seconds of breathing room from each
  other, in every driving mode -- and when several things change close
  together, you hear the current state of the road, never a stale
  catch-up. Warnings that need your hands -- hazards, emergency braking,
  scales, your planned stops -- never wait, and a serious speed limit
  drop still speaks the moment it happens.

- **Radio stations hold their signal like real ones.** A station used to
  start crackling barely halfway through its coverage and spend most of
  its life in static. Stations now play clean through most of their
  range, reach about twice as far down the road, and only smear into
  static right at the edge -- so a good station lasts a good while
  before the dial asks for a retune.
```

- [ ] **Step 2: ROADMAP bullet**:

```markdown
- [x] **Road events breathe; radio contours last -- landed 2026-08-13**
      (owner: back-to-back events in every mode; most of the 5,700-station
      dial living in fringe). Kept the clock -- career pacing is balanced
      on it -- and spaced the three routine talkers (limit arrivals,
      traffic calls, zone colour) with real-seconds gaps at the source,
      self-superseding so only current state ever speaks; big unannounced
      limit drops cut in line. Radio: clean program through ~85% of the
      contour (was ~52%) and a 2x reach multiplier for compression, smear
      ruling intact at the true edge. Spec:
      `docs/superpowers/specs/2026-08-13-event-pacing-radio-reach-design.md`.
```

- [ ] **Step 3: Foreign-edit guard** — `git diff CHANGELOG.md ROADMAP.md` must show only your edits before staging; BLOCKED otherwise.

- [ ] **Step 4: Full verification** — test-runner: the focused files from Tasks 1-4 serially, then `uv run pytest -q` exactly once (default config), then `uv run ruff check src tests tools` and `uv run python -m compileall -q src tests tools`. Known pre-existing xdist flakes (`test_exit_window_scales_with_speed_and_pacing`, `test_a_hot_bend_actually_pushes_the_truck`) get reported, not chased.

- [ ] **Step 5: Commit** (carries the changelog — no `[skip changelog]`)

```bash
git add CHANGELOG.md ROADMAP.md
git commit -m "feat(speech,radio): road events breathe and radio contours last"
```

---

## Self-Review (done at authoring)

- Spec coverage: three categories with the spec's exact gaps → Tasks 1-3; supersede-never-catch-up → the gate-before-mutation design (Tasks 2-3); big-drop exemption → Task 2; exempt list → Global Constraints + Task 3's merge-warning test; real seconds → clock-injected breather; radio thresholds/multiplier/no-sweep → Task 4; out-of-scope compression untouched → no task touches time_scale.
- Placeholders: Tasks 2-3 test bodies are stated as behavioral sketches with the fixture source named (trip fixtures vary too much to transcribe blind); every assertion they must make is written out. All source code is complete.
- Type consistency: `RoadEventBreather(clock)` / `ready(category)` / `spoke(category)` and the three `*_GAP_REAL_S` names match across all tasks; `_reach_mi` used consistently in Task 4.
