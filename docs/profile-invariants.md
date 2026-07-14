# Profile invariants — the maintained list for the validation gate

Companion to `docs/profile-sharing-integrity-design.md` (on the
`docs/profile-integrity` branch): the server signs only what it has
validated, and validation is only as good as this list. This file is the
single source of truth for what an honest profile must satisfy.

Two tiers, and the split matters:

- **Hard invariants** are true in every version of the game. The client
  enforces them too (`src/freight_fate/profile_invariants.py` is the
  executable mirror of section 1, run on every server-verified restore as
  defense in depth). No honest save ever breaks one.
- **Plausibility rules** compare fields against each other and against the
  game's real curves. They live on the server only, because they tighten
  over time and the server always knows the current content set. Bump
  `validator_version` when they change.

Maintenance rule: when a feature adds or changes a field, this doc and the
client module change **in the same PR** as the feature. A field with no
entry here is a field the gate silently trusts.

Which fields exist depends on the client line: entries marked **(1.9
alpha)** below belong to fields the 1.9 alpha line writes; this line's
saves do not carry them, and this line's client module mirrors only the
fields it knows. The server enforces the full list — a rule over a field
a given save does not carry simply does not fire for that save.

## 1. Hard invariants (client-enforced, version-stable)

Ranges — all numeric fields must be finite (no NaN, no infinity):

- `money`: greater than -1,000,000 and below 1,000,000,000 (structural
  ceiling; the real judgment is rule 2.1).
- `fatigue`, `road_grime_pct`: 0 to 100.
- `truck_damage_pct`, `tire_wear_pct`: 0 to 100.
- `truck_fuel_gal`: 0 to the largest buildable tank (biggest catalog tank
  plus the long-range upgrade's 50 extra gallons — 250 today).
- `pay_advance`: 0 to 1,000,000.
- `career.xp`: 0 to 100,000,000 (structural; see 2.2).
- `career.reputation`: 0 to 100.
- `career.deliveries`, `on_time_deliveries`: non-negative integers.
- `career.on_time_streak`, `career.dispatch_declines_used`: non-negative
  integers **(1.9 alpha)**.
- `career.total_miles`, `career.total_earnings`: non-negative.
- Every `truck_conditions` record **(1.9 alpha)**: `tire_wear_pct`,
  `brake_wear_pct`, `engine_wear_pct`, `damage_pct`, `chain_wear_pct`
  each 0 to 100; `fuel_gal` 0 to the largest buildable tank.

Relations:

- `on_time_deliveries` never exceeds `deliveries`.
- `on_time_streak` never exceeds `on_time_deliveries` **(1.9 alpha)**.
- No achievement id appears twice.
- A known upgrade key's tier never exceeds that upgrade's top tier, and no
  tier is below 1.

Closed sets (stable enums — an unknown value is an edit; all **1.9
alpha** fields today):

- `business_status`: `company_driver`, `leased_owner_operator`,
  `independent_authority`.
- `truck_conditions[*].tire_type`: `all_season`, `winter`.
- `career.purchased_endorsements` entries: `refrigerated`, `heavy_haul`,
  `high_value`.

Version tolerance (deliberate): unknown truck, trailer, buff, upgrade, or
achievement KEYS pass the client check — a save written by a newer build
may own content this build has never heard of, and the validator-version
gate owns that problem. Impossible VALUES never pass. The server, which
always knows the current content set, SHOULD reject unknown keys.

## 2. Plausibility rules (server-side; tighten freely, bump the version)

2.1 **Money against career history.** Gross lifetime pay is bounded by
`career.total_earnings`; a balance far above
`starting money (5,000) + total_earnings` cannot be honest. Flag anything
above that sum plus a modest allowance for bonuses; hard-reject multiples
of it. A level-2 driver with nine million dollars fails.

2.2 **XP against the curve and the miles.** Level thresholds are the
`LEVEL_XP` table in `models/career.py` (0, 1,000, 2,500, 4,500, 7,000,
10,000 ... 572,000 at the top). XP accrues from deliveries; profiles with
huge XP over tiny `deliveries`/`total_miles` fail. Rough honest shape:
XP on the order of miles driven times single-digit multipliers.

2.3 **Endorsements.** Earned endorsements come free at levels 2/3/4
(refrigerated/heavy_haul/high_value) — they are DERIVED from level, never
stored. Stored `purchased_endorsements` **(1.9 alpha)** mean the player
paid the course (900 / 1,600 / 1,300 dollars); a purchased endorsement on
a profile whose earnings history could not have afforded it is
suspicious, not fatal.

2.4 **Achievements against the stats that earn them.** Every id in
`achievements` (see `src/freight_fate/achievements.py` for the canonical
set) has a triggering condition; the gate spot-checks the cheap ones:
`five_deliveries`/`ten_deliveries` against `career.deliveries`,
`thousand_miles`/`long_haul` against `total_miles`, `level_three` against
XP, `twenty_five_grand` against `total_earnings`. An achievement without
its stats fails.

2.5 **Equipment against business status (1.9 alpha).** `owned_trucks`,
`upgrades`, and `owned_trailers` belong to owner-operators; a
`company_driver` with a garage full of owned equipment fails.
`truck_conditions` keys should be a subset of `owned_trucks` plus the
carrier's standard tractor.

2.6 **Market sanity.** `market.multipliers` values are drawn from
0.9 to 1.15; anything outside a small tolerance of that band is edited.

2.7 **Possession implies acquisition — the Golden Antler rule.** Any
gated item must arrive with the counter/event trail that grants it. The
planned first instances, so the rule ships with teeth:

- **Big Buck's punch card**: 10 punches, purchasable — must be paired
  with the purchase transaction trail (money history that could afford
  it) and punches-remaining in 0..10.
- **The GOLDEN ANTLER**: lifetime Big Buck's access, deliberately very
  hard to get. It must NEVER appear in a profile without the granting
  event trail — this is the item the whole rule exists for. Until the
  acquisition path ships, ANY profile claiming one fails, full stop.
- Same shape later: the Golden Flare (lifetime roadside), the golden EZ
  pass, souvenirs and welcome-center collectibles.

The long-term strengthener stays the design doc's event ledger: an
append-only trail the server REPLAYS instead of trusting claimed totals.
Every new collectible should land ledger-ready.

## 3. What the client does with a failure

`verify_cloud_revision` (signature) runs first; then
`check_profile_invariants`; any violation raises with a spoken,
jargon-free line built by `spoken_rejection` — "This profile fails the
game's integrity checks and was not loaded. First problem: ..." — and the
file is not restored. Local saves keep the existing per-install HMAC
quarantine (`.invalid` rename); this layer is for anything that crossed
the network.
