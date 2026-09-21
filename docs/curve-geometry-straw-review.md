# Straw record review — Phil, 2026-07-15

Verdict: **architecture RATIFIED, fanout still GATED** on the required
changes below. I decoded both archival records and re-ran the curve
analysis from the decoded stream (scratchpad `verify_straw.py`, results
inline below), so every claim here is tested against the actual straw
bytes, not the write-up.

What's ratified as-is: the two-layer split, sharded NDJSON under
`world_data/us/geometry/`, delta+quantize at q=5 (~1.1 m), the
curvature-adaptive DP idea, the tier-0/tier-1 bundle-and-stream model
with version pinning, SQLite as a build-time runtime artifact, and
advisory = min(posted, sqrt(a_lat * R)) at 0.30 g dry-loaded (spot-checked:
872 ft -> 65, 110 ft -> 20, both correct). The compression thesis is real:
4.5x on the canyon, 8.2x on the straight, density following the road.

---

## Required changes (in priority order)

### 1. CRITICAL — the signed-sum rule erases half of every switchback
`analyse_curvature` sums *signed* turn over a curving run and drops runs
with |net| < 8 deg. A serpentine turns left-right-left inside one
continuous curving run, so the signs cancel. This is not hypothetical —
it is in the published straw table: canyon miles 37.9–39.0 carry ~560 deg
of gross turning (Salt River Canyon switchbacks, min radius 187 ft), but
`curves.jsonl` records only two LEFT curves totalling 86 deg. Every
right-hand half of that serpentine is missing. Same failure at miles
22.9–23.9 (216 deg gross, one 31-deg row survives) and 54.8–55.4.

Fix: split each curving run at every sign change of `turn_deg` (with a
small hysteresis so quantization wobble doesn't shred it), then apply the
8-deg deflection floor per single-direction segment. `direction` is only
meaningful after this split.

### 2. REQUIRED — radius from a sliding window, not 3-point circumradius
Circumradius through consecutive vertices is unstable under vertex
spacing and 1.1 m quantization (the sagitta of a 900-ft curve over a 40 m
chord is ~0.75 m — same order as the noise). Measured: re-deriving radii
from the decoded archive moved matched curves' min_radius by a median
36%, worst 236%, flipping the advisory on most. Production sampler:
fit the radius over a fixed-length sliding arc window (~60–100 m,
least-squares circle or arc-to-chord), which is stable under both
resampling and quantization. This also matches the original design memo
("heading change / turn radius over a sliding window").

### 3. REQUIRED — make the archive able to re-bake the gameplay tables
The strawman says gameplay tables are "baked from the archival layer";
the prototype bakes them from the raw ORS fetch, and today the archive
CANNOT reproduce them (my re-bake from the decoded stream: 91 curves vs
113 published, only 15 aligning). If the archive is the layer we keep,
it must be sufficient: keep ALL raw vertices inside detected curve spans
(eps = 0 there; tangents do all the compressing — the budget already only
squeezes tangents), and add an automated **round-trip acceptance check**
to the production tool: decode archive -> re-bake -> diff vs published
(curve count equal, radii within ~10%, advisories equal). Run it per leg
during the sweep; a miss is a bake bug, same policy as the linter-zero
rule. Baking gameplay tables in the same pass as the fetch stays fine —
the check just proves the archive carries the same truth.

### 4. REQUIRED — at_mi must use the leg-miles convention, like grades
Straw at_mi values are raw ORS mileage. The runtime positions the truck
in `leg.miles`; the grade bake already rescales
(`scale = leg_miles / total`, `enrich_routes_ors.py:266`). Curves and
speed_limits must apply the same scale, or every callout lands offset on
legs where ORS routing differs from the baked mileage. Related: the
decoded polyline is ~1% SHORT on twisty legs (86.68 mi decoded vs 87.52
raw — DP corner-cutting), so mileage must always ride the records; never
re-derive it from the decoded stream.

### 5. REQUIRED — a meta header line per shard
First line of every shard file: a meta record, e.g.
`{"meta":{"schema":1,"data_version":"<stamp>","source":"OpenRouteService
driving-hgv (self-hosted) + OSM via Overpass (ODbL attribution)","a_lat_g":0.30}}`.
One line solves three open holes at once: the missing `source` on
speed_limits/curves rows (non-negotiable), the version pinning §6 needs
for byte-identical streamed-vs-bundled packs, and recording the bake
parameters (a_lat, epsilons, window) so a re-bake is reproducible.

### 6. speed_limits hygiene
- Integer mph (`75`, not `75.0`).
- Define the semantics in the doc: a row governs `[at_mi, next_row)`;
  before the first row the existing terrain/city heuristic governs (the
  straight leg's first row at 4.1 mi made this ambiguous — that gap is
  the un-tagged in-town connector, which is fine, but it must be *stated*).
- Two transitions rounding to the same 0.1 at_mi: keep the later one.

### 7. Connector curves: TAG, don't drop
Add `"connector": true` to curves fully inside the first/last city
connector window (reuse Job 1's boundary semantics for what counts).
Runtime and speech filter on it; the data survives for anything that
later cares about yard approaches. Option (b) shield-gated detection is
REJECTED for now: your own §1 finding is that US-route ref matching is
porous, and a porous gate on curve *detection* deletes real canyon curves
— worse than four phantom ramps. Revisit (b) after #8 proves tight.

### 8. US-route shield matching (your flag — agreed, required for Job 2)
Accept concurrency refs (`US 60;SR 77`), widen the match corridor, and
re-check the canyon: the 45 -> 65 jump spanning miles 1.3–74 almost
certainly swallows a real mid-canyon 55 zone. Interstates are unaffected.

## Answers to §4 open questions

1. **curves fields**: current set + `apex_mi` (mileage of min radius —
   the tone-guidance anchor and the "late apex" speech hook) + the
   `connector` flag from #7. NO clothoid points, superelevation, or
   recommended line — OSM can't source banking, and the steering line
   comes from the archive polyline itself; add wheel-facing fields only
   when the steering prototype demands them.
2. **Budget**: (a) ratified — curves set the floor, the budget caps
   tangents only. Honest; sharding absorbs the size.
3. **Tuning numbers**: ratified as production starting values.
   CURVE_RADIUS_FT=3000 is generous but harmless (min(posted, advisory)
   mutes gentle sweeps). DP_EPS_CURVE_M=4 is superseded by #3 (eps 0 in
   curve spans). The radius *window* from #2 becomes the new number I own:
   start at 80 m.
4. **Elevation**: stays in the archival stream (`dele_m`); grade_segments
   bake from it so grades and curves share one geometry pass. Ratified.
5. **Shield matching**: yes — #8.

## Acceptance for the network fanout (supersets the existing HARD rules)

1. `repair_interstate_anchor_limits.py` reports ZERO (unchanged).
2. Determinism: run the sampler twice on a sample region -> byte-identical
   shards. Iterate legs in sorted order so shard content never depends on
   traversal order.
3. Round-trip check (#3) passes on every leg.
4. Re-run the two straw legs with #1+#2 fixed and eyeball the canyon
   table once more (expect MORE curves than 113, with R rows in the
   switchback windows) before fanning out.
5. world tests, `index_world.py --check`, full gates, changelog entry —
   unchanged.

Fix, regenerate the straw pair, and if the switchbacks read right the
fanout is unlocked — no second full review needed unless something in the
re-run surprises you.

## Addendum (owner-approved 2026-07-15): harvest runaway ramps in the same sweep

The production sampler's per-leg Overpass bbox query gains one tag family:
`way["highway"="escape"]` (emergency escape / runaway truck ramps). Emit a
small fourth table, `us/gameplay/ramps.jsonl`: `leg`, `at_mi` (leg-miles
convention, same rescale as everything else), `side` (L/R from geometry
offset vs the route line), `name` (if tagged), `source`. Real tagged ramps
only — no synthesis; curated DOT gap-fill happens later via the enrichment
recipe. Feeds the existing "runaway ramps as highway furniture" roadmap
feature (approach callouts + the escape move). Sanity anchor: I-70
Denver→Glenwood should surface several; Kansas should surface none.

## REV 2 VERDICT (Phil, 2026-07-15): FANOUT UNLOCKED

All eight required changes verified independently, not from the write-up:
- Switchbacks read RIGHT: canyon mi 37.5-39.5 = 15 alternating L/R curves
  including the two real horseshoe loops (171/174 ft radius, 202/229 deg).
- Fidelity: matching raw-detected vs archive-detected curves by geographic
  apex (drift-immune), canyon loses ZERO significant curves (10 unmatched,
  all >1000 ft radius gentle sweeps where posted governs). One moderate
  sweep (951 ft, adv 65) lost on the Colby in-town approach -- rider 1.
- Determinism EXECUTED: full re-run with live ORS+Overpass -> byte-identical
  artifacts (diff -r clean).
- Gap markers, meta headers, int mph, apex_mi, connector tags, leg-miles
  rescale: all present and correct in the artifacts.

Riders for the production sampler (fold in during the fanout build; none
require another straw review):
1. Widen the keep-verbatim margin so edge-of-span marginal curves survive
   the archive bake: CURVE_PAD_M 80 -> 150, or build the keep-mask at
   ~1.5x CURVE_RADIUS_FT while detection stays at 3000.
2. REQUIRED (owner-approved scope, arrived after rev 2 was cut): runaway
   ramp harvesting per the addendum above -- same bbox query, fourth table.
3. Trailing gap: a leg that ENDS in a >4 mi posting hole should close with
   a null row, same rule as mid-leg holes (canyon happens to end tagged).
4. data_version should hash PER SHARD in production (each file over its own
   records) -- a whole-network hash rewrites every shard header on any
   single-leg change, which is needless diff noise at 1287-leg scale.

Fan out. Prove the mountain chain first per the brief (I-70 Rockies,
AZ-77), linter ZERO, round-trip green on every leg, world tests, --check,
full gates, changelog. Compact between phases.
