# Refreshing city-service data (the periodic re-bake)

City services -- the freight market, garage, and truck dealer you drive to in
each city -- are source-backed from OpenStreetMap at build time and baked into
three checked-in files the game reads offline:

- `src/freight_fate/data/city_services.json` -- the chosen POI per service.
- `src/freight_fate/data/local_approaches.json` -- nearest-road approach per
  target (the distance the runtime drives when there is no turn-level route).
- `src/freight_fate/data/local_geometry.json` -- turn-by-turn local streets
  where a route could be built.

OSM changes over time (new depots, renamed roads, corrected tags), so this
data goes stale. This is the mechanism to refresh it. It is offline at
runtime; the refresh itself pulls fresh extracts at build time only.

## When to run it

Occasionally -- a few times a year, or when a city's services feel wrong. It
is deterministic and idempotent: re-running without fresh OSM yields the same
files.

## Step 1 -- fetch fresh per-state extracts

The bakes read one Geofabrik `<state>-latest.osm.pbf` per state, from
`~/.cache/freight-fate-osm/regions/`. Pull current copies for every state that
has a city:

```
uv run --group tooling python tools/fetch_state_extracts.py
```

- Idempotent: an up-to-date file is skipped (size-checked against the server);
  a changed one is re-downloaded. Writes to a `.part` sidecar and renames on
  success, so an interrupted run resumes cleanly.
- `--states Texas "West Virginia"` limits the pull; `--force` re-downloads
  everything; `--jobs N` sets parallelism (default 3, be polite to Geofabrik).
- A provenance manifest is written to `extract-sources.json` in the cache dir.

The full set is ~11 GB across 49 states.

## Step 2 -- re-bake the three files, in order

Each stage reads the previous stage's output, so run them in sequence:

```
uv run --group tooling python tools/build_city_services.py --all-supported --write
uv run --group tooling python tools/build_local_approaches.py --write
uv run --group tooling python tools/build_local_geometry.py --write
```

Each stage makes a full pass over the ~11 GB of extracts, so the chain takes
on the order of an hour. The default `--cache-dir` matches step 1.

## Step 3 -- verify and gate

```
uv run pytest tests/test_city_services.py tests/test_local_approaches.py \
  tests/test_local_geometry.py tests/test_build_city_services_tool.py
uv run ruff check tools src tests
```

The coverage-count assertions in `test_local_*` pin the sweep's own inventory;
when the map has grown since the last sweep, update them to the fresh numbers
(this is expected -- the tests document the sweep, they do not constrain it).

## The rules the bake enforces (do not regress)

- **A city service is an errand, not a haul.** `build_city_services` only
  matches a POI within ~10 estimated road-miles of the city anchor
  (`MAX_CITY_SERVICE_MATCH_MI`). A logistics site in the next town over is not
  this city's freight market; it falls back to a short synthesized approach.
- **State field is the full name.** world.json keys cities by 2-letter code,
  but the per-state extract filenames and the sibling bakes use the full state
  name; the tools resolve it through the loaded world. (A stale 2-letter field
  here is what silently broke a full re-bake before.)
- **Slugs key the file; display names are spoken.** Output is keyed by the
  canonical world key (`tyler_tx_us`) so shared names (Jackson MS / Jackson MI)
  do not collide, but every player-facing service name uses the display name.
- **No turn-level route means a short fallback**, never the raw geodesic
  distance baked as one long 25 mph segment (that was the 30-mile-errand bug).
