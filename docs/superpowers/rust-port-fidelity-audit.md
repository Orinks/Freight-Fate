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

---

# Pass 2 — the money screens (2026-08-22)

Scope, exactly the gap §8.3 named: `states/city_business.py`,
`states/city_garage.py`, `states/driving_menu_states.py`, plus the four models
whose numbers those screens read out — `models/business.py`,
`models/settlement.py`, `models/jobs.py`, `models/trailer_yard.py`.

Same method and same classification as pass 1: mechanical sweeps to *find*
candidates, every candidate then read on both sides before it is called.

## 9. Spoken strings

The pass-1 extractor was rebuilt with two fixes it needed for these files:
f-string *fragments* are no longer emitted as separate candidates (they were
drowning the signal at 50% false-miss), and Python `+` chains of literals and
expressions are now folded into one normalised string, because
`city_business.py` and `models/business.py` assemble almost every long line
that way.

| Python file | candidate spoken strings | no verbatim Rust match |
|---|---|---|
| `states/city_business.py` | 119 | 5 |
| `states/city_garage.py` | 99 | 0 |
| `states/driving_menu_states.py` | 247 | 2 |
| `models/business.py` | 75 | 9 |
| `models/settlement.py` | 5 | 0 |
| `models/jobs.py` | 57 | 6 |
| `models/trailer_yard.py` | 18 | 0 |
| **total** | **620** | **22** |

All 22 read side by side. **All 22 are assembly differences, not text
differences** — the same bytes reached by a different concatenation, exactly the
pattern pass 1 found. Detail:

- `city_business.py:212,219,249,271,292` — five `"<prefix>. " + " ".join(reasons)`
  sites vs `city_business.rs:82,90,134,164,194` `format!("<prefix>. {}", reasons.join(" "))`.
  Identical, including the empty-reasons fallback: Python
  `(" ".join(reasons) or "Not available yet.")` vs `city_business.rs:75-81`
  `if joined.is_empty() { "Not available yet." } else { joined }`.
- `driving_menu_states.py:1300` `", and {}"` vs
  `driving_menu_states/arrival.rs:666-671` — same `", ".join(parts[:-1]) + ", and " + parts[-1]`
  shape, and the four wear meters are pushed in the same order (tire, brake,
  engine, road grime) with the same `>= 0.1` gate and `fmt_f(added, 1)`.
- `driving_menu_states.py:1913` `"Continue to " + self.terminal.name` vs
  `arrival.rs:1105` `format!("Continue to {}", self.terminal.name)`.
- `models/business.py:277,282,298` — three more `"<prefix>: " + " ".join(reasons)`
  sites vs `business.rs:394,401,428`.
- `models/business.py:319,337,360` — the three long business-status paragraphs,
  each unmatched only because Python appends the transponder / readiness /
  next-unlock clauses with `+` while `business.rs:455,472,491` interpolate them
  as `{transponder}`, `{readiness}`, `{lead}`. Read word for word against
  `_business_status_summary`; identical, including which clause is conditional
  and the trailing space before each.
- `models/jobs.py:286,287,292,301` — `"from " + ...`, `"to " + ...`, and the
  `describe()` line, vs `jobs.rs:248,249,272`. The one-line Rust `format!` at
  `jobs.rs:272` is byte-identical to Python's four-part f-string plus the
  `deadline_covers_rest` ternary plus the `Equipment:` tail.

**Findings in §9: none.**

## 10. Money and number rendering

Every `{...:spec}` slot in the seven Python files was extracted with its
expression, and every `fmt_grouped` / `fmt_f` / `round_py*` call site in the
Rust counterparts was listed with its argument. The two lists were then
reconciled per file, per expression.

| Python file | `,.0f` | `.0f` | `.1f` | `.2f` | Rust `fmt_grouped` | Rust `fmt_f` |
|---|---|---|---|---|---|---|
| `city_business.py` | 43 | 1 | 1 | 0 | 43 | 2 |
| `city_garage.py` | 36 | 26 | 0 | 0 | 36 | 26 |
| `driving_menu_states.py` | 51 | 23 | 8 | 2 | 51 | 33 |
| `models/business.py` | 13 | 3 | 0 | 0 | 13 | 3 |
| `models/settlement.py` | 1 | 0 | 0 | 0 | 1 | 0 |
| `models/jobs.py` | 1 | 3 | 1 | 0 | 1 | 4 |
| `models/trailer_yard.py` | 0 | 0 | 1 | 0 | 0 | 1 |
| **total** | **145** | **56** | **11** | **2** | **145** | **69** |

Not just the counts: the *expressions* reconcile one for one as well. In
`city_business.rs` for instance, `OWNER_OPERATOR_BUY_IN` twice,
`AUTHORITY_ACTIVATION_COST` twice, `AUTHORITY_READY_RESERVE` twice,
`WEIGH_STATION_TRANSPONDER_SIGNUP_FEE` twice, `price` four times,
`model.price` three, `trailer.purchase_price` three, `trailer.lease_deposit`
three, `cost` three and `money` nineteen — the same multiplicities as the
Python file.

**Raw-number scan.** A second sweep walked every `format!` / `write!` / `say`
site in the Rust counterpart files, split the arguments and the inline
captures, and flagged any that name something numeric without passing through
a `pyfmt` / `units` / `Settings::*_text` helper. Twenty-one hits, **all
integers or already-rendered strings**, none a finding: rank and career
`level` (`business.rs:196,239,288,338,370,405,422,454,471,481,490`,
`city_business.rs:1094,1102`, `jobs.rs:331`), the break/sleep stop counts and
their plural suffixes (`jobs/deadline.rs:85`), the `String`s `owed`
(`business.rs:440`), `pay_clause` (`arrival.rs:173`), `rate_clause`
(`arrival.rs:527,535`), `observation_age_value()` (`apps.rs:190`, a `String`
on both sides) and `cargo_status_clause` (`status.rs:173`).

**Verdict: no raw Rust `{}` or `{:.N}` on a player-facing number anywhere in
the seven surfaces.** Every one of the 214 specced slots routes through
`ff_core::pyfmt`. The blunt confirmation: a grep for `{:.` and `{:,` across
all eleven counterpart Rust files returns **nothing at all** — the port never
asks Rust to format a number, it always asks `pyfmt`.

**Findings in §10: none.**

## 11. Money arithmetic

Read expression by expression, with attention to where `round()` sits relative
to a multiply.

**`city_garage.py` — the shop.** `fuel_cost` = `round(fuel_price(region) * gallons, 2)`
and `fuel_price` = `round(base * market, 2)`; `repair_cost` =
`round(damage_pct * REPAIR_COST_PER_PCT * damage_severity_mult(damage_pct), 2)`.
`economy.rs:141-155` has the identical nesting with `round_py_n`, including the
inner round inside `fuel_cost`.

The three wear services and the tire service share one shape that is easy to
get wrong and is right on both sides:

```python
cost = round(wear * cost_per_pct, 2)
if p.money < cost:
    serviceable = p.money / cost_per_pct        # unrounded divisor
    if serviceable < 1: ...refuse...
    cost = round(serviceable * cost_per_pct, 2) # re-rounded AFTER the multiply
```

`city_garage.rs:744-755` (generic) and `:471-479` (tires) reproduce it exactly,
`round_py_n` in both places, the division by the *unrounded* `cost_per_pct`,
and the re-round after the multiply rather than before. The tire-compound swap
`round(100 * TIRE_SERVICE_COST_PER_PCT * premium, 2)` keeps the same operand
order at `city_garage.rs:550`, and the label variants at `:527,533` keep the
`WINTER_TIRE_PREMIUM` factor on the same side.

The one difference of shape is a Python `getattr`/`setattr` pair against a Rust
`WearMeter::read`/`write` enum; the meter written back is `max(0.0, wear - serviceable)`
on both sides, and the *tire* path (which reads the live field rather than the
captured `wear`) is likewise the live field on both.

**`city_business.py` — the shops.** No arithmetic beyond `p.money -= price`;
all prices are catalog constants. Order of operations checked anyway at every
buy: deduct, mutate, save, play sound, speak, award, refresh — the same
sequence, and the achievement predicates (`len(p.owned_trucks) >= 3`,
`all(...)` over `UPGRADE_CATALOG`) are evaluated at the same point relative to
the mutation. `specs.max_torque_nm / 1000` becomes `/ 1000.0` (Python's `/` is
already true division).

**Findings in §11 so far: none.**

### F2 — PLAYER-VISIBLE: the settlement line uses tank vocabulary where Python used dry-freight vocabulary

`cargo_condition_text(condition_pct, *, liquid: bool = False)`
(`src/freight_fate/models/cargo_condition.py:179`) swaps the whole vocabulary
for a tank: `secure / shifted but sound / damaged / badly damaged / ruined`
becomes `settled / worked / off spec / contaminated / lost`.

The four settlement-line calls in `driving_menu_states.py` **omit** the keyword,
so Python always speaks the dry-freight words, even for a tank load:

```python
# src/freight_fate/states/driving_menu_states.py:989,996,1006,1014
    f"{head} Load {cargo_condition_text(cargo.condition_pct)}, "
    f"{cargo_condition_text(cargo.condition_pct)} at "
    f"{cargo_condition_text(cargo.condition_pct)} at "
    f"arrived {cargo_condition_text(cargo.condition_pct)} at "
```

The Rust port passes the live flag:

```rust
// crates/freight-fate/src/states/driving_menu_states/arrival.rs:229,240,251,261
                cargo_condition_text(cargo.condition_pct, liquid),
```

with `let liquid = d.trip.truck.liquid.is_some();` (`arrival.rs:304`).

**What the player hears.** Deliver a damaged tank load. Python's settlement says
"the load arrived **damaged** at 24 percent"; the Rust port says "the load
arrived **off spec** at 24 percent". At a refused load it is "ruined" against
"lost", and in terse mode "Load damaged, 24 percent" against "Load off spec, 24
percent". Only liquid freight is affected, and only when the load took damage —
but the four other places these words are spoken (`driving_damage.py:137,176`,
`driving_liquid.py:225`) *do* pass `liquid`, so a tank driver hears the tank
words all run and then the dry words at the dock. Python is inconsistent; the
port quietly made it consistent.

**Not fixed here.** `driving_menu_states/` is owned by another agent right now
and the brief forbids editing it. It is also not unambiguous: the Rust reading
is arguably the intended text and the Python line arguably the bug, so which
way it goes is the lead's call. The one-line-per-site correction to match
Python is `cargo_condition_text(cargo.condition_pct, false)` at
`arrival.rs:229,240,251,261`.

### §11 continued — the models

**`models/business.py` — the settlement engine.** Read line by line against
`ff-core/src/models/business.rs:505-700`. Everything matches, including the
things a port usually gets wrong here:

- `company_driver_pay`: `round(max(wage_floor, wage_share) + bonus, 2)` — the
  round is outside the `max` and outside the `+ bonus` on both sides
  (`business.rs:530`), and `wage_floor = plan.stop_pay + job.distance_mi * plan.min_per_mile`
  keeps the multiply inside the add.
- `reputation_pay_bonus`: `max(0.0, min(1.0, (rep - 50.0) / 50.0))` ==
  `((rep - 50.0) / 50.0).clamp(0.0, 1.0)`, then one `round(_, 2)` after both
  multiplies.
- `owner_operator_charges` / `independent_authority_charges_for_trailers`:
  eleven per-mile charges, each `round(miles * RATE, 2)` — never
  `round(miles, 2) * RATE` — and the two share-of-gross charges
  (`OWNER_SETTLEMENT_FEE_SHARE`, `AUTHORITY_FACTORING_FEE_SHARE`) round after
  the multiply. Charge order in the vector is the same, which matters because
  `charge_summary` reads them out in order.
- `build_business_settlement`: `raw = gross - driver_charges - sum(charges)` is
  computed **before** the `max(0.0, ...)` and `_uncollected` is fed the
  *unfloored* `raw` on both sides — the one place where a misplaced floor
  would silently forgive a debt.
- The keyword defaults survive: Python's `deadline_business` call omits
  `reputation=`, and `arrival.rs:342-347` builds a separate
  `deadline_terms` with `reputation: None` rather than reusing `terms`.

**`models/jobs.py`.** `payout` applies the four multipliers in the same order
with `round` only at the end (`jobs.rs:362-376`); `_make_job` computes
`round(max(base_pay, minimum_pay_for_level(miles, level)) * mult * direct_mult, 2)`
with the round outside both multiplies (`jobs/board.rs:601-604`), and draws
`weight` before `rate` from the same RNG. `minimum_pay_for_level`
(`jobs/deadline.rs:369-394`) reproduces the taper, the flat floor and the
long-haul override in order. The whole 18-entry `CARGO_CATALOG` was compared
field by field — key, label, `rate_per_mile`, `weight_tons`, endorsement,
`fragile`, `min_level`, `tank`, `baffled` — and matches, in insertion order
(`IndexMap`).

**`models/trailer_yard.py`.** The seed function is
`int.from_bytes(sha256("|".join(str(p) for p in parts)).digest()[:6], "big")`
and `trailer_yard.rs:158-163` builds the same six bytes into a `u64`. The
`job.distance_mi` component of the `assigned` and `detention` seeds goes
through `py_str_float`, which is what makes `78.0` render as `"78.0"` and not
`"78"` — the exact trap §3 flagged, handled. `roll * roll / 100.0`,
`seed // 7`, `seed // 13`, `1000 + seed % 8999` and the `round(_, 0)` on the
slow-shipper extra all match, and `detention_pay` is
`round(minutes / 60.0 * DETENTION_PER_HOUR, 2)` on both sides.

**`models/settlement.py`.** Identical, including the fixed 185.0 / 45.0
amounts, the two membership sets, and detention entering the ledger as a
*negative* charge.

**`driving_menu_states.py` — the settlement screens.** The two long money
paragraphs were read slot by slot: the 18-slot delivery line
(`driving_menu_states.py:1261-1277` vs `arrival.rs:604-627`) and the 9-slot
paperwork preview (`:833-845` vs `facility_arrival.rs:293-309`). Both have
every argument in the same position. So do the four cargo-settlement branches
(`:987-1017` vs `arrival.rs:227-264`), where two branches say the claim value
before the pay loss and two say it after — and the port keeps each branch's
own order.

The mutation ordering around the money is the same as well: `p.money += net_pay`
happens before the paragraph reads `p.money`, `p.game_hours += hours` before
the paragraph reads the local clock, and `apply_hard_cap` before
`p.carrier_name` is spoken next to the written-off figure. `deductions_from_settlement`,
`settle_cargo`, `preventable_damage_charge` and `debt_line` live in
`models/solvency.py`, audited in pass 1.

**Findings in §11: none.** (F2, above, is a word choice, not arithmetic.)

## 12. Constants and thresholds

Every module-level `NAME = <literal>` in the seven Python files was extracted
and compared numerically against every `pub const NAME` in
`crates/ff-core/src` and `crates/freight-fate/src`, evaluating Rust constant
expressions where they are pure arithmetic.

**Zero numeric divergences.** Four Python names have no `const` of that name,
all of them tables rather than scalars, and each was checked in its Rust form
instead: `CARGO_CATALOG` (an `IndexMap` in `jobs/catalog.rs`, compared entry by
entry above), `ENDORSEMENT_LABELS` (the `endorsement_label` function),
`FACILITY_CARGO` (derived from `FACILITY_CARGO_ROLES` on both sides) and
`_CANDIDATES_CACHE` (a cache, not data).

Spot-read for the shop thresholds specifically, since they gate spoken text:
`TERMINAL_FUEL_MIN`, `TERMINAL_REPAIR_MIN`, `TERMINAL_TIRE_MIN`,
`TERMINAL_BRAKE_MIN`, `TERMINAL_WASH_MIN`, `TERMINAL_CHAINS_MIN`,
`TRUCK_WASH_COST`, `CHAIN_SET_COST`, `TIRE_SERVICE_COST_PER_PCT`,
`WINTER_TIRE_PREMIUM`, `BRAKE_SERVICE_COST_PER_PCT`,
`ENGINE_OVERHAUL_COST_PER_PCT`, `SETTLEMENT_LOW_FUEL_FRACTION`,
`ROAD_GRIME_PER_MILE`, the whole `OWNER_OPERATOR_*` / `AUTHORITY_*` /
`WEIGH_STATION_TRANSPONDER_*` family, `DETENTION_FREE_MIN`,
`DETENTION_PER_HOUR`, `LIVE_LOAD_SLOW_EXTRA_MIN`, `DROP_HOOK_MIN`,
`LIVE_LOAD_MIN`, `DROP_EMPTY_MIN`, `LIVE_UNLOAD_MIN`, `TRAILER_SWAP_MIN`,
`REPUTATION_BONUS_MAX_SHARE`, `HOOKUP_FEE`, `DIRECT_FREIGHT_PAY_MULT`,
`ASSIGNED_REPOSITION_PAY_FRACTION`, and the four by-level rate tables. All
equal, and the comparison operators around each (`< 1`, `>= 1.0`, `>= 0.1`,
`> 1`, `>= 100`, `>= 75.0`) match at every use site read in §10-11.

**Findings in §12: none.**

## 13. Findings of pass 2

**Totals: PLAYER-VISIBLE 1, LATENT 0, COSMETIC 0.**

- **F2** (above) — PLAYER-VISIBLE, **not fixed**: the settlement lines speak
  tank vocabulary where Python speaks dry-freight vocabulary, because the Rust
  port passes a `liquid` flag Python's four call sites leave at its `False`
  default. Written up for the lead rather than fixed: the file is owned by
  another agent this session, and which text is *right* is a design call.

- **F1** (pass 1, §6) — **FIXED**. The inspection dedupe key now renders its
  float the way Python's `str(round(x, 1))` does:

  ```diff
  --- a/crates/freight-fate/src/states/driving_events/trip_events.rs
  +++ b/crates/freight-fate/src/states/driving_events/trip_events.rs
  @@ -873,7 +873,7 @@ pub fn handle_inspection
               event.text(),
  -            ff_core::pyfmt::round_py_n(self.trip.position_mi, 1),
  +            ff_core::pyfmt::fmt_f(self.trip.position_mi, 1),
               self.hos_fine_count
  ```

  `fmt_f(x, 1)` rounds half-to-even at the format layer, which is exactly
  `str(round(x, 1))` for the whole range `position_mi` can take, so mile 10.0
  is now `"10.0"` and not `"10"`. **`cargo check -p freight-fate` could not
  confirm the build**: the crate is currently broken by another agent's
  in-flight edit (two `E0433` errors for missing `OnlineOfferState` and
  `CityMenuState` imports in `states/main_menu.rs`), and neither error touches
  this file. The change is a same-arity swap between two `Display` values.

### Notes for the lead (not defects)

1. **Defensive fallbacks with no Python counterpart.** Three places where the
   port returns a value where Python would raise: `minimum_pay_for_level`
   clamps `lvl` with `.max(1)` (`jobs/deadline.rs:370`) where Python would
   `KeyError` below level 1; `endorsement_course_cost(key).unwrap_or(0.0)`
   (`city_business.rs:1011,1091`) where Python indexes the dict; and
   `Job::describe` substitutes `"Pays"` for an empty `pay_label`
   (`jobs.rs:255-259`) where Python would speak the empty string. All three are
   unreachable today — level is always ≥ 1, the keys always exist, and the one
   `pay_label=` caller (`city.py:1573`) passes `pay_label()`, which never
   returns `""`.
2. **`f64::clamp` vs `max(0.0, min(1.0, x))` on NaN.** `reputation_pay_bonus`
   would give `1.0` in Python and `NaN` in Rust for a NaN reputation
   (`business.rs:510`). Reputation is never NaN; noted only because the same
   substitution appears elsewhere in the port.

## 14. Coverage, and where pass 2 stopped

**Covered.** All four requested checks over all seven files: 620 spoken-string
candidates swept and every one of the 22 non-verbatim matches read on both
sides; all 214 numeric format slots reconciled expression by expression against
the Rust `pyfmt` call sites, plus an independent raw-number scan over every
`format!`/`say` site in the counterpart files; every module constant compared
numerically; and every money expression in the seven files read with attention
to rounding position.

Full method bodies read side by side, Python then Rust: `_refuel` /
`_partial_refuel`, `_repair` / `_partial_repair`, `_service_wear_meter`,
`_service_tires`, `_swap_tire_compound`, `_buy_chains`, `_wash_truck`, all the
`_label` readers in both shop files, `_buy` (upgrades), `_pick` (trucks),
`_lease` / `_buy_trailer`, the endorsement course flow, `_business_status_summary`,
`next_business_unlock`, the three eligibility functions, `build_business_settlement`
and its three branches, `company_driver_pay`, `reputation_pay_bonus`, the two
charge builders, `Job.describe`, `Job.payout`, `_make_job`,
`minimum_pay_for_level`, the whole of `trailer_yard.py` and `settlement.py`,
`_driver_lines`, `_paperwork`, `_status`, `_cargo_settlement_line`, `_settle`
(all ~400 lines of it) and `_debt_settlement_lines`.

**Not covered.**

1. **`driving_menu_states/badges.rs`, `apps.rs`, `drive_ref.rs`** were covered
   by the string sweep and the format-slot reconciliation but not read as whole
   methods; they carry no money arithmetic.
2. **Argument slots behind inline captures** — same limitation as pass 1: a
   wrong but same-typed variable bound to the right name survives this audit.
   All *positional* slots in these files were traced, including the 18-slot
   delivery line.
3. **`models/economy.py`, `models/trailers.py`, `models/cargo_condition.py`,
   `models/career.py`** were read only where they fed a number or a word into
   the seven target files (`fuel_price` / `fuel_cost` / `repair_cost`,
   `trailer_program_charge_per_mile`, `cargo_condition_text`,
   `ENDORSEMENT_LEVELS` / `ENDORSEMENT_COURSE_COSTS`). They are the obvious
   next block.
4. **Nothing was run.** The one fix could not be compiled because the game
   crate is mid-edit by another agent; `ff-core` was not rebuilt because no
   `ff-core` file was touched.
