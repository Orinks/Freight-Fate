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

## 1. Hard invariants (client-enforced, version-stable)

Ranges — all numeric fields must be finite (no NaN, no infinity):

- `money`: greater than -1,000,000 and below 1,000,000,000 (structural
  ceiling; the real judgment is rule 2.1).
- `fatigue`: 0 to 100.
- `calendar_offset_days`: integer from 0 through 364.
- Every `truck_conditions` record this line writes (save version 5, one
  record per owned truck; the flat `truck_damage_pct`, `tire_wear_pct`,
  `road_grime_pct`, `truck_fuel_gal` fields belong to version 4 and
  earlier and are migrated into the active truck's record on load):
  `damage_pct`, `tire_wear_pct`, `grime_pct` each 0 to 100; `fuel_gal`
  0 to the largest buildable tank (biggest catalog tank plus the
  long-range upgrade's 50 extra gallons — 250 today).
- `pay_advance`: 0 to 1,000,000.
- `career.xp`: 0 to 100,000,000 (structural; see 2.2).
- `career.reputation`: 0 to 100.
- `career.deliveries`, `on_time_deliveries`, `on_time_streak`,
  `dispatch_declines_used`: non-negative integers.
- `career.total_miles`, `career.total_earnings`: non-negative.
- Every `truck_conditions` record **(1.9 alpha)**: `tire_wear_pct`,
  `brake_wear_pct`, `engine_wear_pct`, `damage_pct`, `chain_wear_pct`
  each 0 to 100; `fuel_gal` 0 to the largest buildable tank (biggest
  catalog tank plus the long-range upgrade's 50 extra gallons — 250
  today).
- `integrity_modified`, `integrity_notice_pending`: real booleans. The
  first is the client's sticky local-tamper mark (set when a save fails
  its per-install signature; signed into every later save so it cannot be
  quietly cleared). The server treats a `true` here as advisory evidence,
  not proof — an honest cross-machine copy also trips it — and MAY clear
  it on a profile that passes full validation (absolution), so honest
  movers are not marked forever.

Relations:

- `on_time_deliveries` never exceeds `deliveries`.
- `on_time_streak` never exceeds `on_time_deliveries`.
- No achievement id appears twice.
- A known upgrade key's tier never exceeds that upgrade's top tier, and no
  tier is below 1.

Closed sets (stable enums — an unknown value is an edit):

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

2.1 **Money against career history.** Cash is bounded by
`startingMoney + career.total_earnings + pay_advance`. Every way the game
adds money also books lifetime earnings, and spending only ever lowers the
balance, so this holds for any honest career. A level-2 driver with nine
million dollars fails.

Do **not** add the price of owned trucks and upgrades to the left side. The
game grants equipment it never charged list price for — an owner-operator
buys out a carrier tractor worth far more than the buy-in — so pricing gear
as if it had been bought reads as roughly $150,000 of invented money and
rejects the backup of every driver who took that step. A career that
launders invented money through the garage is left to offline forensics.

2.2 **XP against the curve and the miles.** Level thresholds are the
`LEVEL_XP` table in `models/career.py`. The ceiling is
`deliveries * xpFlatPerDelivery + total_miles * xpPerMileMax`, both
exported in the invariants, plus a slack of a dollar or so for rounding.

Take those two figures from the export, never from a number copied into
the server. The rate they describe is what a spotless career actually
earns, so a career that delivers every mile on time sits exactly on the
ceiling rather than under it: a copied value that falls even slightly
behind a balance pass convicts the drivers who played best, which is what
happened when a hardcoded 1.2 per mile met the 1.9 arc's higher rates.

2.3 **Endorsements.** Earned endorsements come free at levels 2/3/4
(refrigerated/heavy_haul/high_value) — they are DERIVED from level, never
stored. Stored `purchased_endorsements` mean the player paid the course
(900 / 1,600 / 1,300 dollars); a purchased endorsement on a profile whose
earnings history could not have afforded it is suspicious, not fatal.

2.4 **Achievements against the stats that earn them.** Every id in
`achievements` (see `src/freight_fate/achievements.py` for the canonical
set) has a triggering condition; the gate spot-checks the cheap ones:
`five_deliveries`/`ten_deliveries` against `career.deliveries`,
`thousand_miles`/`long_haul` against `total_miles`, `level_three` against
XP, `twenty_five_grand` against `total_earnings`. An achievement without
its stats fails.

2.5 **Equipment against business status.** `owned_trucks`, `upgrades`,
and `owned_trailers` belong to owner-operators; a `company_driver` with a
garage full of owned equipment fails. `truck_conditions` keys should be a
subset of `owned_trucks` plus the carrier's standard tractor.

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
file is not restored. That path is for anything that crossed the network.

Local saves are packed `.ffsave` containers (magic header plus
zlib-deflated JSON) signed inside with the per-install HMAC key. A failed
local signature no longer quarantines: the save loads, the player hears a
one-time notice, and the profile carries the sticky `integrity_modified`
mark from then on (mark, don't block — local play is the player's own;
the mark is what shared features read). Quarantine (`.invalid` rename) is
reserved for files too damaged to decode at all. Plain unsigned `.json`
saves keep amnesty as the honest pre-signing legacy shape and convert to
signed containers on load; an unsigned *container* is always a tamper,
because the game never writes one.
