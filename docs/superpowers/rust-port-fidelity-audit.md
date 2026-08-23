# Rust port fidelity audit

Status: COMPLETE for the four requested areas (2026-08-22).

**Totals: PLAYER-VISIBLE 0, LATENT 1, COSMETIC 0. Nothing fixed, because the one
finding is not player-visible and the brief reserves fixes for those.**

Method: read the Python original, then the Rust port, then compare. Mechanical
sweeps are used to *find* candidates; every candidate below was then confirmed by
reading both sides. Nothing here is inferred from the Rust alone.

Classification: **PLAYER-VISIBLE** (a player would hear or feel it), **LATENT**
(wrong but currently unreachable), **COSMETIC**.

---

## 1. Spoken strings

An AST-level extractor pulled every string literal and f-string from the seven
target Python files (interpolations normalised to `{}`), and a Rust lexer pulled
every string literal from `crates/freight-fate/src` and `crates/ff-core/src`,
including every contiguous run of literals joined (so `concat!(...)`,
line-continuation literals and multi-part `format!` strings all match).

| Python file | candidate spoken strings | no verbatim Rust match |
|---|---|---|
| `states/driving_events.py` | 297 | 9 |
| `states/driving_updates.py` | 153 | 4 |
| `states/driving_controls.py` | 189 | 5 |
| `states/driving_enforcement.py` | 21 | 1 |
| `states/city.py` | 196 | 1 |
| `states/main_menu.py` | 254 | 0 |
| `models/solvency.py` | 23 | 0 |
| **total** | **1133** | **20** |

All 20 were read side by side. **All 20 are assembly differences (the same bytes
reached by a different concatenation), not text differences.** Detail:

- `driving_events.py:898,913` vs `states/driving_events/trip_events.rs:837,851`:
  Python `f"{message} Speed keeper holding {...}."`, Rust
  `message.plus("Speed keeper holding {keeper}.")`. Same normal rendering; see §5.
- `driving_events.py:1384,1390` vs `states/driving_events/exits.rs:186,191`:
  identical; Python appends `_cap_cruise_for_ramp(stop)` with `+`, Rust
  interpolates `{cap}`.
- `driving_events.py:2212,2285` vs `states/driving_events/chains.rs:166,260`:
  identical, including `lower_first()` == `street[:1].lower() + street[1:]` and
  `trim_end_matches('.')` == `.rstrip(".")`.
- `driving_events.py:5436,5437` vs `states/driving_events/arrival.rs:320,322`.
- `driving_events.py:5505` — HUD/presence text, matches.
- `driving_updates.py:253,3846` — `logging` format strings, not spoken;
  `frame.rs:96` carries the same fields.
- `driving_updates.py:1611` vs `states/driving_updates/lanes.rs:686`: identical,
  both money numbers through `fmt_grouped(_, 0)`.
- `driving_updates.py:3339` (`, and {}`) — join fragment, present.
- `driving_controls.py:307,443` — the two long help texts, both verbatim in
  `states/driving_controls/help.rs`.
- `driving_controls.py:691,1209,1250` vs `driving_controls/vehicle.rs:154`,
  `info.rs:518`, `status.rs:70`: identical, including
  `parts.truncate(UPCOMING_MAX_CLAUSES)` == `parts[:UPCOMING_MAX_CLAUSES]`.
- `driving_enforcement.py:156` `SCALE_NOTICE_SAMPLE` vs
  `states/driving_enforcement.rs:116` `concat!(...)`: identical.
- `city.py:1387` vs `states/city/board.rs:283`: identical.

### Numeric interpolation routing

- `speed_text` / `distance_text` call-site counts match closely (`driving_events`
  26 py / 25 rs, `driving_updates` 4/4, `driving_controls` 24/23,
  `driving_enforcement` 0/0, `city` 10/10 distance); no site interpolates a
  speed or distance raw.
- Every `{:,.0f}` site in the seven files has an `fmt_grouped(_, 0)` counterpart
  (`trip_events.rs:943`, `status.rs:39`, `conditions.rs:327`, `lanes.rs:686`,
  `city/terminal.rs:176,224`, `city/board.rs:145,166,1140`,
  `ff-core/src/models/solvency.rs`).
- Remaining raw `{:.N}` in the ported state files are key strings
  (`weigh:{}:{:.1}`, `barrels:{:.1}`, `stop:{:.1}`, `{:.3}:{}:{}`) or
  percent/grade values Python also formats with `:.Nf`.

**Findings in §1: none.**

---

## 2. Numeric thresholds and module constants

Every module-level `NAME = <literal>` in **all** of `src/freight_fate/` was
extracted and compared numerically against every `const NAME: T = ...;` in
`crates/ff-core/src` and `crates/freight-fate/src`, evaluating Rust constant
expressions where they are pure arithmetic.

**Zero numeric divergences.** Every apparent difference is the same value written
as an expression, verified individually: `hos.RODS_WINDOW_HOURS` 192 = `8.0*24.0`;
`cloud_saves.MAX_UPLOAD_BYTES` 921600 = `900*1024`;
`models/enforcement.SERIOUS_WINDOW_DAYS` 1095 = `3*365`;
`online_presence.IDLE_SIGNOFF_S` = `30.0*60.0`; `cross_traffic.CROSS_BAR_MI` =
`-45.0/5280.0`, `MIN_GAP_MI` = `30.0/5280.0`; the `CACHE_TTL_S` /
`STALE_AFTER_S` / `OBSERVATION_MAX_AGE_S` family;
`city.ASSIGNED_REPOSITION_BOARD_CHANCE` = `1.0/9.0`;
`driving_core.RAMP_ASSIST_HOLD_MI` = `60.0/5280.0`, `RAMP_BAR_TICK_RANGE_MI` =
`300.0/5280.0`, `RAMP_CONTROL_URBAN_WEIGHTS` = `(0.843, 1.0-0.05)`,
`RAMP_CONTROL_RURAL_WEIGHTS` = `(0.514, 1.0-0.20)`.

Private Python scalars with no named Rust constant are inlined at their Rust use
sites; each was spot-checked and carries the same value.

**Findings in §2: none.**

---

## 3. RNG seeding and draw order

All 36 `random.Random(...)` construction sites in `states/driving*.py`,
`sim/*.py` and `models/*.py` were matched to their Rust counterparts.

Verified identical, including seed-string rendering:

- `sim/hos.py:987,993,999` vs `ff-core/src/sim/hos.rs:299,308,317` —
  `PyRandom::new_from_str`, `round(stop_mi*10)` via `round_py_int`.
- `sim/enforcement_posts.py:299 post_seed` vs `enforcement_posts.rs:264`, with
  `seed_text(None) == "None"` reproducing `f"{None}"`.
- `driving_enforcement.py:937` vs `driving_enforcement/watch.rs:343` — the seed
  interpolates a float and Rust uses `py_str_float(round_py_n(position, 1))`, so
  an integral mile renders `"10.0"`. The exact trap named in the brief; correct.
- `driving_enforcement.py:1028` vs `driving_enforcement/scales.rs:238`.
- `driving_enforcement.py:400` vs `driving_enforcement/cues.rs:125` — same seed,
  same two draws in order (`random()`, then `choice(TABLEAU_INTRO_REASONS)`),
  same `SpokenMessage(normal, TABLEAU_INTRO_LINE)` terse pair.
- `driving_events.py:492` vs `trip_events.rs:340` (`trip_seed ^ crc32(bytes)`).
- `driving_events.py:2413,2451` vs `ramp_terminal.rs:63,115` — **draw order
  checked line by line**: control draw first (only when the baked control is
  absent), light-offset draw second; `CrossTraffic` seeded with the same
  `(trip_seed<<16) ^ int(at_mi*100) ^ 0x5AFE`, same gate set, same
  `roundabout -> "yield"`.
- `driving_updates.py:3312,4104,4181,4536` vs `hazards.rs:380`,
  `enforcement.rs:461,560`, `conditions.rs:304`.
- `driving.py:232,373`, `sim/trip.py:258-260,1085`, `sim/lane.py:74`,
  `sim/cross_traffic.py:147`, `models/economy.py:95`, `models/jobs.py:916`,
  `models/market.py:68,89`, `sim/traffic_manager.py:283,731` — matched,
  including the `None -> new_unseeded()` branch and sha256-prefix-16 seeding.

`int(x)` -> `x as i64` truncates toward zero on both sides; `trip_seed <
2^31`, so `<< 16` cannot overflow `i64`.

**Findings in §3: none.**

---

## 4. Conditional inversions and off-by-ones

A sweep compared, for every named constant, the *set* of comparison operators
applied to it on each side (normalising `CONST < x` to `x > CONST`), across all
of `src/freight_fate/` vs all of `crates/*/src`. A `>=` that became `>` anywhere
shows up as an operator present on one side only. After filtering test-only
files, **three** names differed, all three benign on inspection:

- `FIRST_1_9_SAVE_VERSION` — Python
  `not (isinstance(version, int) and version >= X)` (`models/profile.py:390`),
  Rust `n.as_i64() < X` with a non-integer `version` falling to `_ => true`
  (`ff-core/src/models/profile.rs:274-284`). Logically identical, including the
  JSON-float case (`6.0` is legacy on both sides).
- `METHOD_SCALE_SCREEN` — Python
  `post.method not in (METHOD_VISUAL, METHOD_SCALE_SCREEN)`
  (`sim/enforcement_observe.py:182`), Rust
  `post.method != METHOD_VISUAL && post.method != METHOD_SCALE_SCREEN`
  (`ff-core/src/sim/enforcement_observe.rs:171`). Same set.
- `PERSONAL_PLAYLIST_SOURCE_TYPE` — the `!=` at
  `states/driving_updates/radio.rs:649` is the port of `radio.py:1285`, whose
  private `_station_allowed` `ff_core` does not expose; the operator matches its
  real original, not the `driving_updates.py` site the name-based sweep paired
  it with.

Structural spot reads (full method bodies, Python then Rust): `_update_chain_law`,
`_begin_ramp_terminal` / `_ramp_light_phase`, `status_lines`, `_ramp_control_for`
/ `_ramp_meets_a_freeway`, `_candidates` (observation model). All match on guard
order, boundary operators and early-return placement.

**Findings in §4: none.**

---

## 5. Additional sweeps (beyond the brief)

Four more mechanical passes, each chosen because it catches a class the first
four cannot:

**Clamp inversions.** For every named constant, the set of `max`/`min` wrappers
around it on each side. Seven candidates, all false positives from the nested
shape `x.max(CONST.min(y))` == `max(x, min(CONST, y))`
(`ARRIVAL_CREEP_THROTTLE_MAX`, `EXIT_HOLD_MAX_THROTTLE`, `GRADE_WARN_SCAN_MI`,
`KEEPER_EASE_MAX_MI`, `MAX_DRIVABLE_LANES`, `RAMP_ASSIST_FULL_DECEL_MPS2`,
`FACILITY_GATE_ZONE_MI`, the last as
`local_mi.clamp(FACILITY_GATE_ZONE_MI, DESTINATION_APPROACH_TRUSTED_MAX_MI)` ==
`min(max(local_mi, FACILITY_GATE_ZONE_MI), DESTINATION_APPROACH_TRUSTED_MAX_MI)`).

**Rounding mode.** Python `round()` is banker's; Rust `f64::round()` is
half-away-from-zero. Only 7 bare `.round()` calls exist in the whole workspace,
none in a spoken number: two are test-only, one is
`(PCC_GRADE_WINDOW_MI / PCC_PREVIEW_STEP_MI).round()` (2.9999999999999996 — no
tie possible), one is the SDL rumble 16-bit conversion, one is in
`playtest/harness.rs` (another agent's file). Everywhere a number reaches the
player, the port uses `pyfmt::round_py` / `round_py_n` / `round_py_int` —
`models/solvency.rs` alone has 21 of them, matching Python's 21 `round(_, 2)`.

**Delivery options.** Python's `say_event(text, interrupt=True, review=True,
priority=None, key=None, force=False, category=None)` maps to `SayEvent::new()`
(`interrupt=true, review=true`) and `SayEvent::queued()` (`interrupt=false`);
the Rust defaults match. Every `priority=EventPriority.ROUTE` site in
`driving_events.py` also carries `interrupt=False`, which is what the Rust
`say_route_navigation` / `say_route_confirmation` helpers hardcode, so the
helpers cannot be wrong for their call sites. Per-module `EventPriority` counts
reconcile exactly once those helpers (39 call sites) are accounted for.

**Terse gates and speech categories.** `_terse_speech()` gate counts reconcile
per module once Rust's hoisted `let terse = self.terse_speech(ctx)` is counted
by uses rather than calls (`driving_updates` py 10 vs rs 6 calls / 10 uses;
`driving_controls` 6/6; `driving_enforcement` 0/0). `SpeechCategory` counts
likewise reconcile once the shared `opts()` closure in
`driving_updates/air.rs:35` (one definition, three call sites) and the two
route helpers are accounted for. `terse_silent()` and the `SpokenMessage`
normal/terse pairs match one for one, including
`driving_enforcement/cues.rs:135`.

---

## 6. Findings

### F1 — LATENT: inspection dedupe key renders its float the Rust way, not the Python way

`src/freight_fate/states/driving_events.py:935`:

```python
    f"{event.message}:{round(self.trip.position_mi, 1)}:{self.hos_fine_count}",
```

`crates/freight-fate/src/states/driving_events/trip_events.rs:874-878`:

```rust
            "{}:{}:{}",
            event.text(),
            ff_core::pyfmt::round_py_n(self.trip.position_mi, 1),
            self.hos_fine_count
```

Python renders a float through `str()`, so mile 10.0 becomes `"10.0"`; Rust's
`Display` for `f64` prints `10`. The key therefore differs from Python's for
every whole-tenth mile.

**Why LATENT, not player-visible.** This string is only ever a member of the
`enforcement_events` set — never spoken, never an RNG seed, never compared
against a key produced anywhere else (the `event.data.key` branch short-circuits
before the fallback is built). Both sides are internally consistent, the mapping
stays injective, and the saved/restored set in `driving/snapshot.rs` uses the
same rendering it wrote.

**Why it is worth fixing anyway.** Every sibling of this line gets it right and
gets it right *deliberately*: `driving_updates/enforcement.rs:220,282,600` and
`lanes.rs:571,643` use `{:.1}` / `{:.2}`, `enforcement_posts.rs:335` and
`trip_models.rs:714` use `fmt_f`, and `driving_enforcement/watch.rs:343` goes to
the trouble of `py_str_float(round_py_n(position, 1))` *because that one is an
RNG seed*. This is the single site in the four audited surfaces that renders a
Python float with Rust's `Display`, and the same slip one file over — in a seed
string — would move every downstream draw. One-line fix: `fmt_f(self.trip.position_mi, 1)`.

Left unfixed per the brief (fixes reserved for PLAYER-VISIBLE findings); it is
the lead's to schedule.

---

## 7. Notes for the lead (not defects)

1. **`SpokenMessage` flattening.** Python's `SpokenMessage` subclasses `str`, so
   `f"{message} extra"` silently discards the terse rendering, while Rust's
   `message.plus("extra")` preserves it. They agree today only because the
   messages reaching `driving_events.py:898,913` are plain `str`
   (`sim/trip.py:2706,2737` build them). If a zone message ever gains a terse
   form, terse mode will diverge at `trip_events.rs:837,851`.
2. **`exit_phrase` is re-derived rather than carried.** Python attaches
   `stop.exit_phrase` at build time (`driving_events.py:1915`); Rust's
   `exit_phrase_of` (`driving_events/destination_exit.rs:61`) re-runs
   `destination_exit_details()` and matches on `at_mi` within `0.001`.
   Equivalent while that stays stable between build and use, which it is today.

---

## 8. Coverage, and where this stopped

**Covered.** All four requested areas, plus the four extra sweeps in §5. The
spoken-string sweep ran over the seven named files (1133 candidate strings, well
past the 120 asked for). The constant sweep, the operator sweep and the
clamp sweep ran over the **whole** package rather than only the driving modules,
because they were cheap once written. Every one of the ~60 spoken lines whose
Rust rendering uses two or more *positional* format slots — the only slots whose
arguments can be silently transposed — was read argument by argument, including
the eight-slot truck-condition line (`city.py:598` vs `city/terminal.rs:290`),
the five-slot time-and-weather line (`city.py:707` vs `city/weather.rs:180`),
the three-psi air line (`driving_controls.py:1348` vs
`driving_controls/status.rs:222`) and the save-slot timestamp
(`main_menu.py:238` vs `main_menu.rs:401`).

Full method bodies read side by side: `_update_hazard` (the safety-critical
one, `driving_updates.py:3389-3527` vs `driving_updates/hazards.rs:478-622`,
including the AEB engage ladder, the emergency escalation and the collision
branch), `_update_chain_law`, `_begin_ramp_terminal` / `_ramp_control_for` /
`_ramp_meets_a_freeway` / `_ramp_light_phase`, `status_lines` /
`_air_status_text`, `_hos_route_context`, `_brake_budget_s` / `_aeb_engage_s` /
`_hazard_deadline_for` / `_hazard_target_mph` / `_dodge_still_beats_the_hazard`,
`lane_count_at`, `_candidates` (observation model), `_tableau_intro_message`,
`_adjust_radio_volume`, and the weather/source/freshness assembly in `city.py`.

**Not covered.**

1. **Argument slots behind inline captures.** Where the Rust uses named inline
   captures (`{facility}`, `{limit_text}`, ...) the argument cannot be
   transposed, so those were not individually traced back to their Python
   expression. A *wrong but same-typed* variable bound to the right name would
   survive this audit.
2. **Other agents' files.** `driving_menu_states`, `driving_rest_states`,
   `driving_pause_states`, `driving_stop_detail`, `driving_school`,
   `driving_radio_app`, `playtest.rs`, `main.rs` were read where they informed a
   comparison but never edited, and their spoken strings were not swept.
3. **`city_business.py`, `city_garage.py`, `driving_menu_states.py`.** Between
   them these hold 123 of the codebase's 224 grouped-number (`{:,.0f}`) format
   sites — over half the money the game speaks. They were covered by the
   constant, operator and clamp sweeps but **not** by the string sweep or the
   positional-slot read. **This is the largest remaining gap and the obvious
   next block of work.**
4. **Data-layer text.** `ff-core/src/data/*` (billboards, state welcomes,
   street limits) was only reached incidentally.
5. **Nothing was built or run.** No fix was made, so no `cargo check` was
   needed; per the brief the game crate may be mid-edit by other agents.
