# Re-bake briefs — 2026-07-14 (for the execution pass)

Two data-quality jobs, root-caused and specced by the analysis pass on
2026-07-14. Each is deterministic and verifiable; follow the rules exactly
and record what shipped in ROADMAP.md per AGENTS.md.

## Job 1: city-service approaches — kill the 35-mile errand

**Symptom (proven in-engine):** driving to a city service (garage, freight
market, truck dealer) in 91 cities builds a 10-to-35-mile route at a
blanket 25 mph — e.g. `tyler_tx_us:freight_market` is 35.0 miles, about 80
game-minutes to run an errand. 166 chains exceed 5 miles.

**Root cause (two radii that were never reconciled):**

1. `tools/build_city_services.py` matches service POIs within
   `DEFAULT_RADIUS_MI = 28.0` crow-flies miles of the city anchor.
2. `tools/build_local_geometry.py` only attempts turn-level routing within
   `MAX_CITY_SERVICE_ROUTE_MI = 18.0` miles.
3. Its fallback (`geometry_record`, no-geometry branch) then bakes the
   target's FULL `approach_miles` as one single "local approach road"
   segment at 25 mph, `turn_level=false`.

Any service matched between 18 and 28 miles is therefore guaranteed to
become a monster. The fallback's own reason string says it plainly:
"Target is beyond the bounded local route graph distance for this pass."

**The rule:** a city service is an errand, not a haul. A sourced POI more
than **10 road-miles** (use crow-flies x 1.3 as the road estimate at match
time) from the city anchor is a wrong match for the city-service mechanic:
prefer the nearest in-cap candidate, and if none exists, the city simply
has no sourced POI for that service — fall back to the synthesized default
approach (about 3 miles, `CITY_SERVICE_APPROACH_MILES`), flagged
`estimated`/`fallback` exactly like other unsourced services.

**Execution:**

1. In `build_city_services.py`: add a match cap (10 road-mi estimated) as
   above; keep `DEFAULT_RADIUS_MI` as the SEARCH radius if convenient, but
   selection must respect the cap.
2. In `build_local_geometry.py` `geometry_record`: guard the fallback --
   never bake `approach_miles` greater than `MAX_CITY_SERVICE_ROUTE_MI`
   into a segment; clamp to the synthesized default and set a
   fallback_reason that names the discarded distance.
3. Re-run both bakes offline against the local PBF extracts
   (`D:\ors\files\`), regenerate downstream artifacts, and verify:
   - no chain in `local_geometry.json` exceeds 5.0 total miles for
     `city_service:*` keys (facility chains are already healthy, max 4.0);
   - `tyler_tx_us:freight_market`, `beckley_wv_us:freight_market`, and
     `mankato_mn_us:garage` all build in-engine routes under 5 miles
     (see the proof harness pattern in the 2026-07-14 session STATUS).
4. Gates: `uv run pytest tests/test_world.py tests/test_world_overlay.py`
   plus the full suite before push. Changelog entry required
   (player-facing: errands stop being 80-minute drives).

## Job 2: dense maxspeed re-sweep (needs Overpass — check health first)

**Context:** the 2026-07-14 anchor repairs (three classes: interstate
anchors, surface anchors, lone samples — see
`tools/repair_interstate_anchor_limits.py`, which encodes all the judgment
rules) fixed 680 legs offline. What remains is *coverage*: legs whose
profile was dropped now ride the heuristic (55 urban / 65 rural), which is
honest but smooth — the real Salt River Canyon has 25-mph hairpins the data
should carry.

**The rule set (already encoded in the repair tool — the sweep must not
reintroduce what it removes):**

- Interstate legs: no sample below 45 survives at any position.
- Surface legs: no sub-45 mile-0/end anchor sample when the corridor is
  fast; no lone anchor sample owning a leg over 15 miles.
- The bake already prefers `maxspeed:hgv` and shield-matched ways
  (`enrich_routes_pois.py`, including the 2026-07-14 shield-less sub-45
  guard). Keep both guards.

**Execution:**

1. Health-check self-hosted Overpass first (`ff-overpass`, port 12347;
   recovery runbook in project memory. ORS-only work does not need it).
2. Sample DENSER on legs currently without a profile: every checked-in
   route point, not just anchors — mountain and canyon corridors first
   (US-60 Globe–Show Low, AZ-77 Show Low–Holbrook, the I-70 Rockies legs).
3. After the sweep, run `tools/repair_interstate_anchor_limits.py` as a
   post-bake linter — it must report ZERO repairs on freshly baked data;
   any hit is a bake bug, not a data fix.
4. Regenerate `world_data`, verify `--check`, world tests, full gates,
   changelog entry.

## Sequencing note

Job 1 first: it is fully offline and unblocks the worst player-facing pain.
Job 2 whenever Overpass is confirmed healthy. Both in a worktree; never in
parallel with each other (both write world-adjacent data).

## RESUME INSTRUCTIONS — Job 1, after the 2026-07-14 evening pause

You were paused mid-Job-1 because a national surface resweep landed on the
main branch underneath you (tier-1 chains 821 -> 1,541; 5,784 chains total
in local_geometry.json). Your bake OUTPUTS are stale; your TOOL changes are
exactly what we want and carry over. Verified from the main window: the
match cap, the fallback guard, the canonical-key fix (Jackson MS vs Jackson
MI -- good catch, keep it), fetch_state_extracts.py, and the runbook doc.

Resume like this, in the ff-city-services worktree:

1. Stash or commit ONLY the tool + test + doc changes
   (tools/build_city_services.py, tools/build_local_approaches.py,
   tools/build_local_geometry.py, tests/test_build_city_services_tool.py,
   tools/fetch_state_extracts.py, docs/refresh-city-service-data.md).
   Discard your modified data files -- they were baked against the old base
   and are superseded.
2. Rebase the branch onto the updated feat/career-1.9 (commit d6af862 or
   later): it now contains the resweep your re-bake must run on top of.
3. Re-run the bakes offline against the local PBF extracts with your fixed
   tools. The canonical-key change may relocate entries keyed by display
   name -- make sure legacy keys still resolve (the runtime has
   resolve_city_key; verify a Jackson and a Portland by hand).
4. Verify before committing:
   - chain tally: no city_service chain over 5.0 total miles, and total
     chain count STAYS at or above 5,784 (the resweep's coverage must
     survive your re-bake);
   - the display-name collision regression is CONFIRMED and map-wide, not
     just Jackson: 31 display names are shared by 2+ cities and 23 of the
     old city_services entries sit on colliding bare names (Albany, Austin,
     Buffalo, Charleston, Columbus, Las Vegas NM, ...). Acceptance: every
     city_services key after your re-bake is a canonical slug, each twin
     city gets its own entry, and spot-check both Jacksons plus Las Vegas
     NM resolve to their own services in-engine;
   - in-engine: tyler_tx_us:freight_market, beckley_wv_us:freight_market,
     mankato_mn_us:garage all under 5 miles;
   - tools/refresh_map_data.py --limits-lint still reports zero;
   - full gates (pytest, ruff, compileall).
5. Changelog entry (player-facing: errands stop being 80-minute drives) and
   a ROADMAP check-off on the overlong-city-service bullet.
