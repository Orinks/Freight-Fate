# Per-truck condition migration (wear, damage, fuel)

Execution handoff for an Opus session on `feat/career-1.9`. Design was
agreed with the owner on 2026-07-13; the judgment calls are already made
and recorded here. Work the plan top to bottom, run the focused tests as
you go, and pause when the checklist is done.

## Goal

Condition follows the truck, not the profile. Today
`models/profile.py` stores one flat set of condition fields --
`tire_wear_pct`, `brake_wear_pct`, `engine_wear_pct`,
`truck_damage_pct`, `truck_fuel_gal` (profile.py around lines 307-312)
-- so swapping tractors at the dealer teleports wear, damage, and fuel
onto the new truck. After this change each owned truck keeps its own
condition record, the garage fixes *that* truck, and the future rental
system can price a truck by its condition with zero further migration.

## Why now

The physics overhaul underway (jake staging, brake thermal mass,
hydroplaning on tread depth, chain damage) keeps adding wear-adjacent
state. Migrating storage first means every new physics feature is born
per-truck instead of joining a later, bigger migration.

## Target model

- New profile field: `truck_conditions: dict[str, dict]` keyed by truck
  key (the same keys as `owned_trucks` / `active_truck_key()`; company
  assignments key under their assignment key, `"rig"` included). Each
  record holds `tire_wear_pct`, `brake_wear_pct`, `engine_wear_pct`,
  `damage_pct`, `fuel_gal`.
- SCOPE LIMIT (deliberate): keyed by truck *model key*, matching the
  current `owned_trucks: list[str]` ownership model. True per-instance
  trucks (owning two identical tractors) are deferred to the rental
  feature; do not build instance ids in this slice.
- Keep the existing flat attribute names working as **properties** that
  proxy to the active truck's condition record. `city_garage.py`,
  `city.py`'s rig readout, and the save/snapshot layers all mutate
  `p.tire_wear_pct` etc. today -- with property getters/setters routed
  through `truck_conditions[self.active_truck_key()]`, most call sites
  need no edits at all. `load_truck_condition` / `store_truck_condition`
  (profile.py:420-438) stay the runtime funnel and become reads/writes
  of the active record.
- Upgrades (`upgrades` dict) stay profile-scoped in this slice --
  unchanged behavior, out of scope.
- Rig-care buffs are trip-snapshot-scoped and timed buffs are
  profile-scoped; both are untouched by this migration.

## Migration rule (owner-approved)

Loading a profile saved before this change: every truck in
`owned_trucks` (and the active/assigned key) inherits the profile's
current flat wear/damage values -- no free pristine spares. Fuel: the
ACTIVE truck inherits `truck_fuel_gal`; other owned trucks start with
full tanks (they were parked, and fuel windfalls are worth cents, not
an exploit). Trucks bought after the migration start fresh: zero wear,
zero damage, full tank (match whatever the dealer does today for fuel;
check `city_business.py`).

## Touch points to verify (not necessarily edit)

- `states/city_garage.py` (~lines 251-360): services read/write the
  flat attrs; with the property proxy they keep working -- verify each
  service touches the truck the player is actually driving.
- Truck dealer in `states/city_business.py`: buying must create the new
  truck's condition record; selling must drop it. Switching active
  truck must NOT copy condition anymore -- that is the whole point.
- `states/driving.py` (~43-45, ~345-347) start-of-trip wear baselines
  and the active-drive snapshot restore path: confirm they read through
  the runtime `TruckState` (they do today) and survive a save/load
  mid-trip on a non-default truck.
- `states/city.py` rig status readout (~446-448): should speak the
  active truck's numbers; with the proxy it does. Consider (optional,
  only if trivial) naming the truck in that readout, since "which truck
  am I checking" now matters.
- Company drivers: `owns_equipment()` False forces key `"rig"`; wear
  accrues under the assignment key and carrier-paid servicing keeps
  working (`test_settlement_accounting.py` has the precedent tests).

## Save compatibility

Follow the existing precedent in `tests/test_save_compat.py`. Old saves
must load with the inheritance rule above, silently. Decide with the
code whether to keep mirroring the flat fields on save for downgrade
tolerance (the air-brake snapshot's `schema` field pattern in
`sim/vehicle.py` is the house style for versioned blobs); if mirroring
is kept, the mirror is write-only from the active record.

## Tests

- New: per-truck accrual isolation (drive truck A, truck B unchanged),
  dealer swap no longer teleports condition, migration inheritance from
  a legacy profile dict, garage services hit only the active truck,
  company-driver assignment wear.
- Run focused first: `uv run pytest tests/test_save_compat.py
  tests/test_trucks.py tests/test_buffs.py tests/test_vehicle.py`
  plus the new file; then the full suite (expect ~1507, all green).
- `uv run ruff check src tests tools` before every commit.

## Changelog (required -- this is player-facing)

Add under `## Unreleased` / `Changed`, plain spoken language, e.g.:
"**Each truck now keeps its own condition.** Tire, brake, and engine
wear, damage, and fuel stay with the truck they happened to, so
swapping tractors no longer carries your wear along, and the garage
fixes the truck you drove in."

## Working agreement

- Branch: `feat/career-1.9` directly (this window works sequentially;
  no worktree needed). Push to remote `fork` (nromey/Freight-Fate)
  only -- `origin` (Orinks) is fetch-only, pushes to it 403.
- Narrate each step in chat as you go; the owner may be on a phone.
- Commit in tested units. When the checklist is done: update STATUS.md
  (newest-first entry), update the ROADMAP 1.9 section per the roadmap
  upkeep rule in AGENTS.md, then PAUSE for the owner to compact and
  switch models. Do not start unrelated tasks.
