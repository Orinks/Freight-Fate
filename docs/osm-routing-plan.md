# OSM Routing, Region, And Map-Expansion Plan

This is the design plan for redesigning Freight Fate's routing, trip, and
job-generation data around OpenStreetMap, fixing region classification errors
(for example, Reno was tagged as the Rockies), and growing the map toward
full-US coverage without breaking the offline-first, deterministic,
accessibility-first design.

It builds on the existing data contract in
[`docs/route-stop-data.md`](route-stop-data.md) and the freight model in
[`docs/freight-market-facilities.md`](freight-market-facilities.md). Read those
first; this plan extends them, it does not replace them.

## Decisions Driving This Plan

These were chosen deliberately and shape everything below:

1. **Runtime posture: offline-first plus an optional online tier.** The bundled
   static data remains the source of truth and the game stays fully playable
   with no network. When a connection is available, an optional background tier
   may refresh and extend data, modeled exactly on the existing Open-Meteo
   weather provider: cached, non-blocking, graceful `None` fallback, never on
   the hot game loop.
2. **Map scope: bundle a moderate curated network, stream finer detail.** Ship a
   substantially larger curated network as static data. When online, pull
   additional corridors and POIs for the player's area into a local overlay
   cache that persists for later offline play (progressive enrichment).
3. **Routing engine: OpenRouteService (HGV/heavy-goods profile).** Truck-aware
   routing (legal truck roads, grade/steepness, tollways, height/weight context)
   instead of the current car-only OSRM. Free hosted tier for development, with
   Docker self-hosting available for heavy batches.
4. **Regions: finer set, derived from coordinates.** Replace hand-typed region
   strings with a build-time classifier that assigns each city a region by
   point-in-polygon against authoritative boundaries, using an honest, finer
   taxonomy (for example Great Basin and Sierra rather than forcing Reno into
   the Rockies).

## Why This Fits The Existing Architecture

- Runtime driving already never calls OSM/OSRM/Overpass; those are build-time
  inputs. Open-Meteo is the only runtime network call and is the template for
  the optional online tier.
- The network is a curated intercity graph (currently 59 city nodes, 106 legs in
  [`world.json`](../src/freight_fate/data/world.json)), not "every US road."
  "Whole US" here means a much larger curated node/leg network plus harvested
  POIs, still baked to static data. Shipping a live routing engine is not
  realistic: the US OSM extract is about 11 GB and building a routing graph
  needs hundreds of GB of scratch space.
- New dispatchable freight is already gated behind a strict metadata-complete
  contract (`World.leg_metadata_complete`); the job board must not invent route
  conditions. Every expansion below must keep that gate green.

## Non-Goals

- No live routing engine shipped to end users.
- No per-frame or mid-trip network calls. Once a trip is dispatched, its route,
  grades, stops, tolls, state lines, and weigh stations are fixed (the
  determinism contract in `docs/route-stop-data.md`).
- No raw OSM IDs, tags, or source keys exposed in speech, menus, or help text.

---

## Workstream A: Region Taxonomy (Fixes Reno Now)

This is the smallest, highest-value change and is independent of the map
expansion. It can ship first.

### Current state

`region` is a hand-typed string per city in `world.json`. It drives weather
weighting, hazard flavor, fuel pricing, menu labels, and (indirectly) market
tags. Known errors: Reno is `rockies` (it is Great Basin / eastern Sierra,
western Nevada); Boise as `rockies` is also shaky (Snake River Plain /
intermountain).

Region is consumed in these places, so each new region value needs entries in
all of them:

- `REGION_WEIGHTS` / weather sampling — [`sim/weather.py`](../src/freight_fate/sim/weather.py)
- `REGION_HAZARDS` — [`sim/trip.py:39`](../src/freight_fate/sim/trip.py)
- `REGION_FUEL_PRICE` — [`models/economy.py`](../src/freight_fate/models/economy.py)
- `REGION_MARKET_TAGS` — [`data/world.py:447`](../src/freight_fate/data/world.py)
- `REGION_LABELS` (spoken/displayed names) — [`states/main_menu.py:485`](../src/freight_fate/states/main_menu.py)

### Locked region taxonomy (14)

Anchored on NOAA climate regions (for weather) crossed with USGS physiographic
provinces (for grades/hazards), then sanity-checked for freight character. Each
region below lists its identity and starting flavor-table values. Fuel prices
are starting points to balance, in dollars per gallon, replacing the current
eight-region `REGION_FUEL_PRICE`. Hazards are written in the style of the
existing `REGION_HAZARDS`. Boundary cases noted in the assignments are the only
judgment calls; everything else is unambiguous.

**Eastern / Appalachian**

- `northeast` — humid continental, nor'easters and snow, dense corridor
  traffic, coastal-plain-to-rolling terrain. Weather lean: snow, rain, cloud,
  fog up; thunderstorm low. Fuel ~4.15. Hazards: sudden lane closure; stopped
  traffic around a fender bender. Markets: port, intermodal, industrial, retail.
- `appalachia` — Appalachian/Allegheny mountains, sustained grades, valley fog,
  winter ice. Weather lean: fog and snow up, rain up. Fuel ~3.95. Terrain
  leans hills/mountain. Hazards: runaway-truck ramp warning on the steep grade;
  fog settling in the hollow ahead. Markets: industrial, mining, manufacturing.
- `great_lakes` — cold snowy winters, lake-effect snow, summer thunderstorms,
  flat industrial Midwest. Weather lean: snow (lake-effect) and thunderstorm
  and wind up. Fuel ~3.75. Hazards: lake-effect snow squall whiting out the
  lane; a deer crossing the road. Markets: intermodal, manufacturing,
  automotive, agriculture.

**Central**

- `heartland` — corn belt plus Missouri/Mississippi valley, thunderstorms,
  moderate snow. Weather lean: thunderstorm and wind up. Fuel ~3.60. Hazards:
  farm equipment pulling onto the highway; a sudden downpour flooding the right
  lane. Markets: agriculture, intermodal, food.
- `southern_plains` — Tornado Alley, high crosswinds, hail, hot, light snow.
  Weather lean: wind up strongly, thunderstorm up, clear up. Fuel ~3.45.
  Hazards: a crosswind gust shoving the trailer; hail hammering the windshield.
  Markets: energy, agriculture, intermodal, retail.
- `mid_south` — interior Dixie/Cumberland, humid subtropical, ice storms,
  rolling hills. Weather lean: thunderstorm and fog and rain up; snow low.
  Fuel ~3.45. Hazards: a sudden downpour flooding the right lane; retread
  debris from a blown tire. Markets: parcel, manufacturing, food.

**Southern / Coastal**

- `atlantic_southeast` — Piedmont plus Atlantic coastal plain, storms, coastal
  hurricanes. Weather lean: thunderstorm up, clear up, heavy rain moderate,
  snow near zero. Fuel ~3.65. Hazards: stopped traffic around a fender bender;
  a sudden thunderstorm downpour. Markets: port, manufacturing, retail, food.
- `gulf_coast` — Gulf humid subtropical, heavy rain, hurricanes, heat. Weather
  lean: thunderstorm and heavy rain up strongly, fog up, snow near zero. Fuel
  ~3.40 (refining belt, cheapest). Hazards: standing water flooding the lane; a
  fog bank rolling across the lanes. Markets: port, energy, chemical, food.
- `florida` — peninsular subtropical to tropical, daily storms, hurricanes,
  flat. Weather lean: thunderstorm up very strongly, heavy rain up, snow zero.
  Fuel ~3.85. Hazards: a sudden thunderstorm downpour; stopped traffic around a
  fender bender. Markets: port, food, retail, cold_chain.

**Western**

- `rockies` — Rocky Mountains plus Front Range, heavy snow, altitude grades,
  wind. Weather lean: snow up strongly, wind up, clear up. Fuel ~3.95. Terrain
  leans mountain. Hazards: rockfall debris on the road; a runaway truck on the
  grade ahead. Markets: mining, intermodal, construction.
- `great_basin` — Basin and Range plus Snake River Plain plus eastern Sierra,
  arid, big temperature swings, mountain passes. Weather lean: clear up
  strongly, wind up, snow up at passes, fog low. Fuel ~4.10 (remote). Hazards:
  a crosswind gust shoving the trailer; snow drifting across the mountain pass.
  Markets: intermodal, mining, retail. **This is the Reno fix.**
- `desert_southwest` — Sonoran/Mojave/Chihuahuan deserts plus Colorado Plateau,
  extreme heat, dust storms, monsoon, border freight. Weather lean: clear up
  very strongly, wind (dust) up, monsoon thunderstorm moderate, snow near zero.
  Fuel ~4.00. Hazards: a dust devil crossing the interstate; tumbleweeds piling
  in your lane. Markets: border, construction, food, mining.
- `california` — Mediterranean coast plus Central Valley, marine and tule fog,
  Sierra grades, highest fuel. Weather lean: clear up, fog up strongly
  (marine plus valley tule), cloud up, snow low. Fuel ~5.10 (CARB, highest).
  Hazards: a fog bank rolling across the lanes; a stalled car jutting off the
  shoulder. Markets: port, food, retail, intermodal.
- `pacific_northwest` — marine west coast, persistent rain, Cascade grades and
  snow. Weather lean: rain and cloud up very strongly, fog up, snow moderate
  inland/Cascade. Fuel ~4.45. Hazards: an elk crossing the road; standing water
  in your lane. Markets: port, lumber, agriculture, intermodal.

### City assignments (all 59)

- `northeast`: New York, Boston, Hartford, Philadelphia, Baltimore
- `appalachia`: Pittsburgh, Knoxville
- `great_lakes`: Chicago, Detroit, Cleveland, Columbus, Cincinnati,
  Indianapolis, Milwaukee, Minneapolis, Buffalo (Buffalo placed here for
  lake-effect, not `northeast`)
- `heartland`: St. Louis, Kansas City, Des Moines, Omaha (St. Louis borderline
  vs `great_lakes`)
- `southern_plains`: Dallas, Oklahoma City, Tulsa, Wichita, Amarillo
- `mid_south`: Nashville, Memphis, Louisville, Little Rock, Birmingham
  (Louisville borderline vs `great_lakes`)
- `atlantic_southeast`: Charlotte, Raleigh, Richmond, Atlanta, Savannah
- `gulf_coast`: Houston, New Orleans, San Antonio (San Antonio borderline vs
  `southern_plains`)
- `florida`: Jacksonville, Tampa, Miami (Jacksonville borderline vs
  `atlantic_southeast`)
- `rockies`: Denver, Cheyenne, Salt Lake City (SLC is the Wasatch Front, edge
  of `rockies`/`great_basin`)
- `great_basin`: Reno, Boise
- `desert_southwest`: Phoenix, Tucson, Las Vegas, Albuquerque, El Paso
- `california`: Los Angeles, San Diego, San Francisco, Sacramento, Fresno
- `pacific_northwest`: Seattle, Portland, Spokane (Spokane is inland semi-arid,
  drier and colder than the coast)

These assignments are the expected output of the build-time classifier; the
stored-equals-derived test enforces them. The classifier polygons must be drawn
so each city above falls in its listed region (in particular the Wasatch Front,
eastern Sierra, and Snake River Plain boundaries that separate `rockies`,
`great_basin`, `california`, and `pacific_northwest`).

### Implementation

1. Add region boundary polygons as a checked-in build asset (GeoJSON), sourced
   from authoritative public boundaries (Census regions/divisions as a base,
   refined with physiographic boundaries for Great Basin / Sierra). Attribution
   recorded in source notes.
2. Add a build-time classifier (new helper in `tools/`, or extend
   `enrich_routes.py`) that does point-in-polygon on each city's lat/lon and
   writes the resulting `region` into `world.json`. Region stays a checked-in
   string field, so runtime code is unchanged except for new region values.
3. Populate the five region tables above for every new region value.
4. Add a test asserting each city's stored `region` equals the classifier's
   output for its coordinates. This catches both bad coordinates and future
   drift as the map grows, so a Reno-style error cannot recur.

### Accessibility note

**Done.** The new-career picker is now two spoken levels: a region list
(`HomeTerminalState`) whose entries name each region and its city count, then a
per-region city list (`HomeCityState`). Both keep the standard menu model
(arrows, Home/End, Enter, Escape, F1, first-letter jump); region menu names drop
the leading "the" so type-ahead works. This keeps spoken navigation manageable
as the map grows toward national coverage instead of one long flat city list.
Escape steps back city list -> region list -> name entry. The default flow still
lands on the default city's region and then the default city.

---

## Workstream B: OpenRouteService HGV Build Pipeline

Replace/augment the car-only OSRM build step with truck-aware OpenRouteService.

### What ORS gives us that OSRM does not

- HGV (heavy-goods) profile: routes on legal truck roads.
- Elevation along the route (`elevation=true`), reducing or replacing the
  separate Open-Meteo elevation sampling step.
- `extras`: steepness (maps to our `grade_segments`/terrain), tollways (seeds
  `toll_events` candidates), waytype, surface.
- Optional vehicle parameters (height, weight, length, axle load, hazmat) for
  future cargo-aware routing.

### Implementation

1. Free HeiGIT/OpenRouteService account; API key read from an environment
   variable in build tooling only (never bundled, never used at runtime).
2. Add an ORS client to [`tools/enrich_routes.py`](../tools/enrich_routes.py)
   alongside the existing OSRM path. Map ORS responses into the existing
   corridor schema: `route_points`, `elevation_samples`, `grade_segments`
   (from steepness), `toll_events` candidates (from tollways), `state_crossings`
   and `state_miles` (still via the existing Census-boundary step).
3. Keep OSRM as a fallback so the pipeline degrades gracefully and existing
   cached corridors keep working. Use `.route-cache/` as today.
4. Respect rate limits (about 2,500 requests/day, 40/min on the free tier).
   The existing resumable batch + cache design already handles polite staging.
   For large batches, document Docker self-hosting (needs the regional/national
   OSM extract plus RAM) as the unlimited path.
5. Extend the build smoke check (the current `--live-smoke`) with an ORS HGV
   smoke that is credential-gated and skipped in CI when no key is present.

### Licensing / attribution

ORS and OSM-derived data carry ODbL/attribution obligations. The data contract
already requires this; keep OSM, ORS, and OpenStreetMap attribution visible in
release materials and per-record source notes.

---

## Workstream C: Tiered Map Expansion

Grow from 59 cities toward national coverage in staged, always-green batches.

### Bundled tier (static, deterministic)

1. Expand the node set in stages (for example 59 -> ~150 -> ~300 cities), adding
   key interchange nodes so truck routing follows realistic corridors rather
   than long city-to-city straight hops.
2. Generate legs between adjacent nodes via ORS HGV, then auto-enrich each leg
   to the metadata-complete contract (route points, elevation/grade, state
   context, source-backed POIs at the required density).
3. Keep `tools/enrich_routes.py --coverage-report --json` green after every
   batch. A leg only becomes a normal dispatch lane once it passes the gate; the
   legacy/full graph stays loadable for old saves.
4. Harvest POIs via the existing Overpass and operator-feed tooling
   (`discover_route_pois.py`, `curate_route_pois.py`), curated into clean
   player-facing names — no raw OSM text.

### Streamed tier (optional online overlay)

When online, the optional tier fetches additional secondary corridors and POIs
for the player's current area and writes them into a local overlay cache (in the
user data directory, like portable saves), so they are available for later
offline play. The bundled core never changes; the overlay is purely additive.

---

## Workstream D: Optional Online Runtime Tier

Mirror the Open-Meteo provider precisely. This is the only new runtime network
surface, and it is always optional.

### Design rules (determinism and accessibility safety)

- Background thread, cached, non-blocking; returns `None` when offline,
  unavailable, or rate-limited. The loop never waits on it.
- It only acts **between trips** (at the city hub and at job acceptance/
  dispatch). Once a `Trip` is constructed, its route and all route facts are
  fixed for the run. No mid-drive mutation.
- Output is written to a namespaced overlay file, never into the checked-in
  `world.json`. With the overlay absent, behavior is byte-for-byte identical to
  today.

### Components

1. **World overlay loader.** `World.load` merges the checked-in base with an
   optional overlay (extra cities, legs, POIs). Stable facility IDs and leg
   identity must be preserved so saves keep resolving; the loader keeps
   `_facilities_by_id` uniqueness and the `route_from_cities` legacy path
   working.
2. **`RealRouteProvider`** (new, sibling to `RealWeatherProvider`): given an
   origin/destination, fetch a fresh HGV route in the background and cache it.
   Used at job-accept/dispatch to optionally upgrade an accepted job's route
   fidelity, and to progressively pull nearby corridors/POIs for the current
   region into the overlay. Offline always falls back to bundled static data.
3. **Settings + accessibility.** A spoken setting to enable/disable online
   enrichment, defaulting to a privacy- and offline-friendly choice. Any new
   data surfaced to the player follows the existing spoken-label conventions.

---

## Risks And Open Questions

- **`world.json` size at scale.** It is ~580 KB for 59 cities; at ~300 cities it
  could reach several MB and is currently fully loaded into memory at startup.
  Plan: consider gzip-on-disk, sharding by region, or lazy loading before the
  node count gets large. Decide the threshold during Workstream C.
- **ORS rate limits vs. batch size.** Hundreds of cities means thousands of
  legs. The free tier needs multi-day polite batches; Docker self-hosting is the
  unlimited path but needs the OSM extract and RAM. Confirm which we use for the
  big batches.
- **Region boundaries need sign-off.** The taxonomy and polygon edges affect
  weather, hazards, fuel price, music, and labels. Lock the region list before
  populating the flavor tables.
- **Terminal-picker accessibility at scale.** Resolved for now: the picker is a
  two-level region -> city submenu (see Workstream A accessibility note). As the
  city count per region grows, revisit whether very large regions need a further
  split (for example by state) so no single city list becomes unwieldy.
- **Determinism guarantee.** The overlay and online tier must never make an
  in-progress trip non-reproducible. Tests should assert that, with no overlay
  and no network, the world and a given trip seed are identical to today.

## Suggested Sequencing

1. **Workstream A (regions).** Self-contained, fixes the visible Reno bug,
   ships first.
2. **Workstream B (ORS build pipeline).** Truck-aware data without changing
   runtime; validate against existing corridors before regenerating.
3. **Workstream D scaffolding (overlay loader + provider).** Additive, with the
   offline path provably unchanged.
4. **Workstream C (expansion).** Staged node growth and streamed overlay, kept
   green by the coverage report at each batch.

## Acceptance Artifacts

- `tools/enrich_routes.py --coverage-report --json` stays green at every batch.
- Region classifier test: stored region equals derived region for every city.
- Offline-determinism test: with no overlay/network, world and seeded trips are
  unchanged.
- Credential-gated ORS HGV build smoke, skipped in CI without a key.
- Attribution present in release materials and source notes (OSM/ODbL, ORS).
