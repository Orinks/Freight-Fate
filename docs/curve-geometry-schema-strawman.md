# Curve + speed geometry — design strawman (Oatis → Phil/Norm review)

Self-contained brief for the curvature-adaptive geometry pass (Job 2 maxspeed
+ the curve layer that feeds curve-nav/steering). **This is a strawman: the
massive network-wide run is GATED on Phil + Norm ratifying this schema.** No
mass generation on an unratified format — dense data is expensive to redo.

Extraction is Oatis'. The open decisions are the *fields/semantics* and the
*representation*, below.

---

## 1. Two layers (Phil's framing — keep them separate)

**Archival layer — the big dense geometry, source of truth, regenerable.**
The full curvature-adaptive polyline per leg. This is the bulk; it is encoded
for size (§3) and NEVER lives in `world.json`.

**Gameplay layer — small, plain, BAKED FROM the archival layer.** Per-curve
records, the maxspeed step function, grade segments. This is what the runtime
and the spoken layer read. It stays small plain JSON and **never depends on
the archival encoding** — decode happens at bake time, not at play time.

So: dense encoded archive → (bake) → small plain gameplay tables → (build) →
SQLite runtime artifact. Three stages, each regenerable from the one before.

---

## 2. Where it lives (NOT in world.json)

- Curated `world.json` stays lean (checkpoints, POIs, hand-named crossings —
  human decisions). Diffable, reviewable.
- Derived geometry goes in **separate sharded files**, e.g.
  `world_data/us/geometry/<state-or-corridor>.jsonl`. GitHub limits are
  per-file (≈50 MB warn / 100 MB block), so sharding by state/corridor keeps
  every file well under and makes each a packageable/streamable unit.
- Tabular, line-oriented (NDJSON/TSV): one record per line → record-granular
  diffs, greppable, streams into SQLite. Never a single gzipped blob (that
  kills diff + curation and reintroduces a "binary source").

---

## 3. Representation: compress from ENCODING, not just gzip (Phil)

The archival point stream is where size explodes, so compact it by *how it's
written*, staying text:
- **Quantize + delta-encode** the polyline (Google-polyline style): store
  successive lat/lon as integer deltas at ~1e-5 deg (~1.1 m) precision;
  elevation as delta-encoded integer meters. ~10x smaller than raw floats,
  still text, still record-granular.
- **Curvature-adaptive density with a hard per-leg point budget:**
  Douglas-Peucker simplification with a *tighter epsilon in bends* — arrow
  tangents collapse to a couple of points, curves keep the vertices that
  define their shape. A per-leg cap prevents any one leg blowing up.

---

## 4. Gameplay tables (baked from the archive)

### `speed_limits` (maxspeed step function — Job 2 core deliverable)
One row per posted-limit transition (collapsed; a 70-the-whole-way leg = 1 row).
`leg` (from:to), `at_mi`, `mph`, `hgv` (bool), `source`.

### `curves` (steering-facing — **Phil owns these fields**)
One row per detected curve; tangents produce none.
`leg`, `seq`, `start_mi`, `end_mi`, `direction` (L/R), `min_radius_ft`
(binding radius), `deflection_deg` (total heading change), `advisory_mph`
(physics-derived, §5).
**Open for Phil (what does the wheel read?):** entry/exit transition points
(clothoid feel), superelevation/banking, per-point radius vs one min, a
"recommended line." Add only what steering consumes.

### `grade_segments`
Already baked; regenerated from the same fine archive so grades and curves
share one geometry pass.

---

## 5. Physics-derived advisory speed

A curve of radius R has a lateral-accel-limited safe speed **v = √(a_lat·R)**.
Bake `advisory_mph` at a comfortable dry-loaded a_lat (~0.30 g); the runtime
scales a_lat down on ice/snow (a multiplier, not baked, so weather stays
dynamic). Effective target the game speaks/enforces = `min(posted, advisory)`.
This gives real "ease to 40 for this bend" from geometry even where OSM has no
advisory tag.

---

## 6. Distribution: bundle small, stream/download the dense layer

- **Tier 0 — always bundled, tiny:** coarse profiles + heuristics. Game is
  fully playable offline at base fidelity, small install. This is the
  accessibility floor; it never depends on a download.
- **Tier 1 — the dense derived layer (region shards):** offline players
  download region packs (or the whole set) into a folder and FF decompresses;
  online players stream per-route from a server (orinks.net), pulling only the
  legs the route needs → smaller install without losing offline play.
- **Version-pinned:** each region pack is stamped with the data version, so a
  streamed leg and a bundled leg are byte-identical — online and offline
  players drive the same road, determinism/reproducibility intact.
- **Graceful degrade (non-negotiable):** missing pack or failed stream → fall
  back to Tier 0. The game never breaks for lack of the dense layer.
- Streaming *baked* snapshots is NOT the live-API determinism problem — it's
  the same frozen versioned data, delivered on demand. Inside the boundary.
- A region **`.sqlite` file is the natural downloadable/streamable unit** — so
  the streaming model and the SQLite plan reinforce each other.

---

## 7. SQLite (runtime artifact, built from shards)

Baked from the sharded gameplay tables at build time, exactly like the
existing `_baked_world` step — a runtime artifact, never a source. Compact +
indexed → query one leg's curve/speed profile on demand as you approach it,
instead of parsing whole shards. Design the schema with **international** in
mind (units metric/imperial, a country/region column, a road-class taxonomy
that isn't US-only) so we cut the tables right once.

---

## 8. Non-negotiables (Phil)

Deterministic (same input → byte-identical output), loads fully offline,
source notes on everything, text-in-git for source + derived, SQLite is a
build-time runtime artifact only. The runtime and spoken layers read the small
gameplay tables, never the encoded archive.

---

## 9. Maintenance

Thorough **one-time** bake. Re-runs only when the MAP changes (new
legs/roads/interchanges). The sampler takes `--only` (per-leg / per-region) so
a map scan re-bakes just the affected legs — never the whole network again.

---

## 10. What's decided vs open

**Decided:** two-layer split; sharded derived files (not in world.json);
delta+quantize encoding; curvature-adaptive Douglas-Peucker with per-leg
budget; tiered bundle/stream distribution; SQLite as runtime artifact; physics
advisory speed = min(posted, √(a_lat·R)).
**Open for Phil:** exact `curves` fields steering needs; the point budget /
epsilon numbers; whether elevation rides the archival stream or stays in
grade_segments; international schema specifics (deferred to the SQLite phase).
