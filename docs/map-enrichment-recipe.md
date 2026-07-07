# Map Enrichment Recipe

The repeatable, per-leg process for bringing a leg up to full fidelity: real
named-place checkpoints, real truck-stop POIs, and fine-grained grade data.
It is written so any contributor or coding agent can execute it cold, batch
after batch, without re-deriving the judgment calls. It applies to three
jobs:

1. Enriching the existing sparse legacy legs (the backlog measured below).
2. Finishing new corridor legs right after they are built, so no new leg
   ships with placeholder-only content.
3. Periodic full-map review as the network grows toward national coverage.

It extends [`osm-routing-plan.md`](osm-routing-plan.md) (map architecture and
expansion plan) and [`route-stop-data.md`](route-stop-data.md) (leg schema and
determinism contract). Read those first if you have not.

## Invariants (non-negotiable, read before touching data)

- **Everything named is spoken.** Checkpoint `name` and `state` are narrated
  verbatim while driving ("Passing Seligman, Arizona on I-40"), and stop
  names are read in menus. No slug keys, no 2-letter state codes, no bare
  initialisms ("TA" must be "TA Travel Center"), no raw OSM tags.
- **Never invent a place.** Every checkpoint must be a real town or named
  locality you can attest is on that highway; every stop must be a real
  facility returned by a source query. A blind player hearing a fabricated
  town is worse than a sparse leg. "This leg genuinely has nothing" is an
  acceptable, honest result -- sparse rural legs are an intentional planning
  challenge.
- **Inspect leg content before changing it.** A leg that looks sparse by
  checkpoint count may carry rich hand-curated stops (this happened on I-10:
  "redundant" legs held real Van Horn / Fort Stockton / Sonora curation).
  Read the leg's current `stops` and `corridor` first; the job is to add,
  not to reset. Never delete a leg, stop, or checkpoint without reading it.
- **Curated mileage is pay.** `leg["miles"]` drives pay and deadlines. The
  enrichment steps below never change it (`--refresh-geometry` preserves it;
  `--adopt-ors-miles` is only for brand-new legs, always with `--only`).
- **Source notes on everything real.** Each checkpoint/stop records where it
  came from and how it was positioned. The placement tool writes these
  automatically; keep the convention if you edit by hand.
- **Data stays deterministic and offline.** All queries here are build-time.
  After any world.json edit: regenerate (`uv run python tools/index_world.py`),
  verify (`--check`), and run the world tests.

## Prerequisites

- `uv sync --group dev` (plus the `tooling` group for ORS: commands below use
  `uv run --group tooling` where needed).
- The self-hosted OpenRouteService server, for unlimited driving-hgv routing:
  `docker start ff-ors` if the container has exited (takes ~10-15 s to become
  healthy), then set `ORS_BASE_URL=http://localhost:8080/ors` and
  `ORS_API_KEY=selfhosted`.
- Overpass queries use the public endpoints (rate-limited, cached in
  `.route-cache/`; transient failures are skipped and retried on re-runs).

## Finding the backlog

Sparse legs are flagged by real-place checkpoint density:

```python
from freight_fate.data.world import World
w = World.load()
def density(leg):
    n = sum(1 for c in leg.checkpoints if c.type == "place"
            and "corridor between" not in c.name)
    return n / max(1.0, leg.miles) * 100.0, n
scored = sorted(((*density(leg), leg) for leg in w.legs), key=lambda t: t[0])
sparse = [t for t in scored if t[0] < 0.5]   # < 0.5 real places per 100 mi
```

Work the list biggest-mileage-first (single biggest wins), batched by
region or corridor so each batch reads as one reviewable content drop.

## The per-leg recipe

### 1. Snapshot the leg

Read the leg's current `stops`, `corridor.checkpoints`, `miles`, and
`highway` from `world.json`. Note what is already real (curated stops,
named checkpoints) -- that content is load-bearing and stays.

### 2. Identify candidate towns

List the real, well-known towns and named localities on that highway between
the endpoints, in driving order. Sources, in preference order:

- Public knowledge of the corridor (interstate exit towns are well
  documented; think "what would a trucker or road-tripper name on this
  stretch").
- GeoNames (`tools/pick_nodes.py` fetches `cities15000` for places over
  15k population; smaller waypoint towns -- most of them -- need hand-sourced
  coordinates from GeoNames/Census, recorded in the source note).

For each candidate, record: spoken name, latitude/longitude, and state.
When unsure whether a town is actually on the route, include it anyway --
the placement gate in step 4 rejects wrong towns mechanically.

### 3. Apply the node-vs-checkpoint rule

A candidate is a full CITY NODE (separate workflow: new city + legs) rather
than a checkpoint if it hits any of:

1. Junction with another BUILT interstate.
2. Freight generator: port, rail intermodal, real industry, energy or ag hub.
3. Spacing: the only stop breaking a gap longer than ~150 miles.
4. Real metro.

Otherwise it is a checkpoint. Tiebreaker: two candidates within ~30-40 miles
of each other -- the smaller one drops to checkpoint. Flag genuine coin-flips
for the map owner instead of deciding silently. A town can be BOTH a stop on
this leg today and a future node -- adding it as a checkpoint now does not
block promoting it later.

### 4. Position and write the checkpoints

```sh
uv run --group tooling python tools/place_checkpoints.py \
    --leg "from_slug:to_slug" \
    --candidate "Seligman|35.3258|-112.8747|AZ" \
    --candidate "Ash Fork|35.2247|-112.4841|AZ" \
    --write
```

The tool matches each candidate to the nearest point on the leg's real ORS
driving-hgv polyline, converts it to the leg's own mile scale, and REJECTS
anything more than 2 miles off-route -- the sanity gate that catches wrong
towns, coordinate typos, and places on a different road. It writes spoken
names and full spoken state names, merges with existing checkpoints (curated
positions win), and drops the synthetic "corridor between" placeholder once
at least one real place covers the leg. Investigate every rejection: it
usually means the coordinates or the town are wrong, not the gate.

### 5. Discover truck-stop POIs

```sh
uv run python tools/enrich_routes.py --add-overpass-pois \
    --only "from_slug:to_slug" --write
```

This queries mid-corridor sample points AND both endpoint cities (endpoint
clusters are where real truck stops live -- Tucumcari, Barstow, Kingman were
all missed before the endpoint fix). Additive only; existing curation is
deduped against, never replaced. Check every new name for initialisms and
non-spoken text before committing. An empty result at a rural leg or a metro
downtown is honest -- do not force a stop. Known gap: a metro's beltway truck
stops can sit outside the endpoint search box; add those by hand with source
notes if the leg needs fuel support.

### 6. Refresh geometry and grades

```sh
uv run --group tooling python tools/enrich_routes.py --refresh-geometry \
    --engine ors --only "from_slug:to_slug" --write
```

Re-derives `route_points`, `elevation_samples`, and `grade_segments` from
the real ORS polyline with fine 0.25-mile grade bins -- the fidelity that
feeds grade physics (and later fuel burn and maintenance). Curated miles,
stops, checkpoints, tolls, and crossings are preserved. Legs enriched before
the fine-grade fix (mid-2026) under-report real climbs (Kingman-Flagstaff
showed 1.37% max on a 4,000 ft climb), so run this for every touched leg.

### 7. Verify and commit

```sh
uv run python tools/index_world.py && uv run python tools/index_world.py --check
uv run pytest tests/test_world.py tests/test_world_overlay.py \
    tests/test_route_coverage_tool.py tests/test_place_checkpoints.py
uv run ruff check src tests tools
```

Then re-run the density snippet: the leg should now clear 0.5 real places
per 100 miles (most legs land well above). Spot-review the spoken strings of
everything added (read each new name and state aloud). Commit the batch with
real source notes in the message; data-only batches that change nothing
player-visible take `[skip changelog]`, but a batch that adds audible places
to legs players can drive deserves a changelog entry under `Added`.

## Batching guidance

- Batch by corridor or region (like the I-40 and I-40 desert-town passes),
  roughly 5-10 legs per commit, so review stays tractable.
- The full test suite runs once per batch; the focused tests above run per
  leg while iterating.
- ORS responses and Overpass responses are cached in `.route-cache/`;
  re-running a batch is cheap and safe (all steps are idempotent).
- The endpoint-city POI queries are cache-keyed per CITY, so working
  corridor-by-corridor gets cheaper as coverage grows.

## Building new corridors (composition)

The corridor-building pattern (pick nodes by the rule in step 3, add slug
cities with `spoken_city` + code state/country, add legs, `--enrich-all
--engine ors --no-overpass`, then `--adopt-ors-miles --only "<new legs>"
--write`) is documented in the map plan and proven on I-40/I-10. THIS recipe
is the finishing pass: run steps 1-7 for every new leg immediately after
building, so no corridor ships placeholder checkpoints or misses its
endpoint truck stops. One PR per corridor, each a player-facing content drop
with its own changelog line.
