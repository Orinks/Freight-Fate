"""Re-derive every baked curve's ``connector`` flag from OSM's own road classes.

WHAT WAS WRONG
--------------
The dense sweep decides ``connector`` by POSITION: a curve within
``CONNECTOR_WINDOW_MI`` (0.75 mi) of either end of a leg is a connector, and
everything else is mainline. That window is blind to the two places
interchange geometry actually lives:

  * the middle of a leg, where the route takes a ramp from one freeway to
    another, and
  * the miles of surface street and slip road a route rides before it ever
    reaches the interstate the leg is named for -- 0.75 mi does not get a
    truck out of Denver.

So ramp arcs and city-departure kinks were baked as INTERSTATE MAINLINE, and
every consumer that reads mainline curves -- the pacenote callout, the cruise
clause, cargo damage -- treated them as bends in the road. Measured: 1,954
interstate mainline curves demanding a drop below 65 mph, one every 44.2
miles, on a road system that asks for none.

THE DISCRIMINATOR IS READ, NOT DERIVED
--------------------------------------
``tools/curve_osm_facts.py`` reads what OSM way each curve's apex rides, and
what class of road the leg itself is made of, mile by mile. Two readings:

  ``osm:ramp``          the apex rides a ``highway=*_link`` way, which is the
                        tag OSM uses for a ramp, slip road or interchange
                        connector. True on every road class.
  ``osm:off-corridor``  the apex rides a road LESS IMPORTANT than the one its
                        leg is made of -- the town the route threads on its
                        way in or out, rather than the through road.

The comparison is what matters, and it is against the leg's own road rather
than a fixed class. An Interstate leg is made of ``motorway`` (every
Interstate mainline mile is a controlled-access freeway by statute, 23 CFR
625, and US mappers tag controlled access as ``motorway``), so only motorway
bends are its mainline. A curated I-65 leg whose route actually runs US-231
end to end is made of ``trunk``, and its trunk bends are that road's real
mainline.

WHY NOT JUST "IS IT MOTORWAY". Tried, and it fails in both directions. Gated
on the LABEL it silenced 2,677 real bends on 36 legs whose route never rides
the interstate they are named for. Turned off wholesale for those legs it
restored the real US-231 bends together with Brickell Avenue in downtown
Miami at a 38 ft radius. Comparing against the leg's own class does neither.

WHY NOT A COVERAGE PERCENTAGE. Also tried. The obvious gate is "apply the
rule only to legs that ride a freeway for more than half their miles", and
the histogram forbids it: the distribution is not bimodal, 52 interstate legs
sit between 40 and 60 percent, so any cut would sit in a crowd and would have
been chosen to look right. ``corridor_class`` is an argmax instead -- whichever
class the route spends most of its miles on -- so there is no number to tune.

Neither reading looks at radius, deflection, advisory or severity, so this
cannot tell a sharp curve from a gentle one and cannot delete a design
exception. I-70 through Glenwood Canyon is ``highway=motorway`` and reads
exactly like I-70 across Kansas.

MOUNTAIN GEOMETRY, CHECKED THE WAY THE ARTIFACT SCREEN CHECKS ITSELF. Of the
18,340 rows moved off-corridor, 1,183 are on HPMS mountainous legs, and 42 of
those turn like a switchback (135 degrees or more at an advisory of 30 or
less). Every one of the 42 is a named town street -- North Pack Square in
Asheville, Frederick Street in Cumberland, North Bartow Street, town squares
looping 260 to 368 degrees. Not one is a road switchback. Terrain alone
cannot separate a mountain town square from a mountain switchback; the road
under the bend can.

WHY NOT A RADIUS FLOOR
----------------------
Because that was tried and it deleted real road:
``INTERSTATE_MIN_RADIUS_FT`` raised to the 50 mph design minimum (758 ft)
reads correctly and takes I-70 out of Glenwood Canyon, which bends tighter
than standard under design exceptions. A screen sized to the design floor
cannot tell an exception from an artifact. This rule never sees the radius.

WHAT IT COSTS, SAID OUT LOUD
----------------------------
Some legs are labelled for a road their baked route does not ride: the
curated I-65 leg from Huntsville to Nashville runs US-231 end to end
(``bake_divided`` independently measures the same leg as undivided). Under
this rule every curve on such a leg reads off-freeway, which is TRUE -- they
are not on I-65 -- but it silences a genuinely curvy drive rather than fixing
the label. ``--report`` prints those legs, ranked, from the per-leg freeway
coverage in the facts file, so they can be given routing pins later.

THE RESIDUAL, MEASURED
----------------------
Of the 15,752 interstate mainline rows that survive, 11,986 ride a way with
the leg's own shield, 3,640 a way carrying another route number, and 126 a
``motorway`` way with no ``ref`` at all -- which is where this rule cannot
tell "a freeway" from "the Interstate". They are urban freeway spaghetti
(the Whitehurst Freeway, Denver's West 6th Avenue Freeway, Tampa's Crosstown
Connector, the I-95 Express Toll Lanes), 37 of them ask a truck to slow, and
the 300 ft interstate screen takes most of those at load. Left alone: they
are real bends on real controlled-access road, and a second rule to chase
twenty records would be fitting to the residual.

CONNECTORS ARE ONLY EVER ADDED
------------------------------
A row the sweep already flagged stays flagged: the positional window catches
city geometry the class reading can miss, so this is a union, never a
replacement.

Nothing is deleted. Every row keeps its radius, deflection and advisory; only
``connector`` moves, and ``connector_source`` records which reading moved it,
so the rule can be re-judged from the shipped data without re-baking.

The facts file itself is NOT committed -- 26 MB of derived cache, regenerated
by one offline pass over the local extracts. The decision it feeds is what
ships, row by row, in ``connector_source``.

Usage
-----
    uv run --group tooling python tools/curve_osm_facts.py --all   # slow, cached
    uv run python tools/bake_curve_connectors.py --report          # no write
    uv run python tools/bake_curve_connectors.py --write
    uv run python tools/bake_curve_connectors.py --check           # exit 1 if stale
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from world_source import load_world  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GAMEPLAY = ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "gameplay"
CURVES = GAMEPLAY / "curves.jsonl"
FACTS = GAMEPLAY / "curve_osm.jsonl"

# How near a way must be to count as the road under a curve apex.
#
# DERIVED, from the archive's own precision rather than from taste. The
# archival polyline is quantized at 1e-5 degrees (~1.1 m) and curve spans are
# kept at eps=0, so an apex sits essentially on the way ORS routed it along --
# MEASURED over Alabama and Colorado, the nearest road of any kind is within
# 0.6 m of the apex for 99 percent of curves, and beyond 25 m for 4 of 1,245.
# So this is a sanity bound on "was anything read at all", not a decision: the
# verdict comes from which way is nearest, and where a ramp and the mainline
# it leaves are both in range they are a median 11 m apart, twenty times the
# positioning error.
CORRIDOR_M = 25.0

# What OSM calls a controlled-access freeway. An Interstate mainline mile is
# one by statute, so this is the class an Interstate leg's mainline curves
# must ride -- not a threshold, a definition.
FREEWAY_CLASS = "motorway"

# OSM's own functional hierarchy, most important first. This is upstream's
# ordering, not a weighting anybody chose: the wiki defines the tags as a
# descending ladder of road importance, and every US mapper applies it that
# way.
#
# The rule compares a curve's road against the road ITS LEG IS MADE OF rather
# than against a fixed class, and it is the comparison that does the work. A
# leg made of motorway keeps only motorway bends, which is the Interstate
# case. A leg made of trunk -- a curated I-65 whose route actually runs
# US-231 end to end -- keeps its trunk bends, because those are that road's
# real mainline, while still dropping the primary and residential kinks where
# the route threads a town. Judging such a leg against `motorway` restored
# 2,677 rows including Brickell Avenue in downtown Miami at a 38 ft radius;
# judging it against its own class does not.
CLASS_RANK = {
    "motorway": 0,
    "trunk": 1,
    "primary": 2,
    "secondary": 3,
    "tertiary": 4,
    "unclassified": 5,
    "residential": 6,
}

SOURCE_NOTE = (
    "READ: OSM highway class of the nearest way to each curve apex "
    "(Geofabrik PBF, offline; ODbL, (c) OpenStreetMap contributors)"
)


def load_facts(path: Path) -> tuple[dict[str, dict], dict[tuple[str, int], dict]]:
    """``(per-leg coverage, per-curve readings)`` from the facts shard."""
    coverage: dict[str, dict] = {}
    facts: dict[tuple[str, int], dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "coverage_samples" in row:
            coverage[row["leg"]] = row
        else:
            facts[(row["leg"], row["seq"])] = row
    return coverage, facts


def freeway_coverage(coverage: dict[str, dict], leg: str) -> float | None:
    """Fraction of the leg's route miles riding a freeway-class way."""
    row = coverage.get(leg)
    if not row or not row["coverage_samples"]:
        return None
    return row.get("coverage_on_motorway", 0) / row["coverage_samples"]


def corridor_class(coverage: dict[str, dict], leg: str) -> str | None:
    """The class of road this leg is actually MADE of, mile by mile.

    Read, and an argmax rather than a cut: whichever class the route spends
    most of its miles on is what the leg is. No percentage is chosen, so
    there is no threshold to tune and no band for a leg to sit awkwardly
    inside -- which matters, because the coverage histogram turned out NOT to
    be bimodal (52 interstate legs sit between 40 and 60 percent freeway), so
    any percentage cut would have been picked to look right.

    ``None`` when nothing was read, and the caller falls back to the label.
    """
    row = coverage.get(leg)
    classes = (row or {}).get("ridden_classes") or {}
    if not classes:
        return None
    return max(classes.items(), key=lambda kv: (kv[1], kv[0]))[0]


def classify(fact: dict, made_of: str | None) -> tuple[bool, str]:
    """``(is connector, why)`` for one curve, from its OSM reading alone.

    ``made_of`` is the class of road the LEG is built from, read per mile
    from the route rather than taken from the leg's label (see
    ``corridor_class``). A bend on a road less important than that is not on
    the through route -- it is the town the route threads on its way in or
    out -- and a bend on the same class, or a better one, is mainline.

    An empty reason means nothing could be read: no road within the corridor,
    or no class recorded for the leg. Nothing may be concluded from that.
    """
    near_m = fact.get("near_m")
    near_hw = fact.get("near_hw")
    if near_m is None or near_hw is None or near_m > CORRIDOR_M:
        return False, ""
    if near_hw.endswith("_link"):
        return True, "osm:ramp"
    corridor_rank = CLASS_RANK.get(made_of or "")
    here = CLASS_RANK.get(near_hw)
    if corridor_rank is None or here is None:
        return False, "osm:mainline"
    if here > corridor_rank:
        return True, "osm:off-corridor"
    return False, "osm:mainline"


def reclassify(facts_path: Path) -> dict:
    """Rebuild every curve row's connector flag. Returns the run's report."""
    coverage, facts = load_facts(facts_path)
    world = load_world()
    highway = {f"{L['from']}:{L['to']}": str(L.get("highway", "")) for L in world["legs"]}

    lines = CURVES.read_text(encoding="utf-8").splitlines()
    meta_line = next((line for line in lines if line.startswith('{"meta"')), None)
    rows = [json.loads(line) for line in lines if line.strip() and not line.startswith('{"meta"')]

    counts = {"osm:ramp": 0, "osm:off-corridor": 0, "osm:mainline": 0, "sweep:window": 0}
    unread = unflagged = 0
    moved = {"osm:ramp": 0, "osm:off-corridor": 0}
    moved_by_leg: dict[str, int] = {}
    for row in rows:
        leg = row["leg"]
        # The verdict to preserve is the SWEEP's, not this tool's. A row this
        # tool flagged carries an ``osm:`` source and is re-decided freely, so
        # a second run on its own output lands in the same place as the first
        # -- otherwise every reading it ever made would be frozen in.
        prior = row.get("connector_source")
        was = bool(row.get("connector", False)) and prior in (None, "sweep:window")
        row.pop("connector", None)
        row.pop("connector_source", None)
        fact = facts.get((leg, row["seq"]))
        is_conn, why = (False, "")
        if fact is not None:
            made_of = corridor_class(coverage, leg)
            if made_of is None:
                # Nothing read about this leg's road: fall back to the label,
                # which is what the rule used before it could read the road.
                made_of = FREEWAY_CLASS if highway.get(leg, "").upper().startswith("I-") else None
            is_conn, why = classify(fact, made_of)
        if not why:
            # Nothing was read here -- no extract, or no road within the
            # corridor. Keep exactly what the sweep said; absence of a reading
            # must never be read as "mainline".
            unread += 1
        if was and not is_conn:
            # Only ever ADD. The positional window sees city geometry the
            # class reading can miss, so its verdict is never overturned.
            is_conn, why = True, "sweep:window"
        if is_conn:
            row["connector"] = True
            row["connector_source"] = why
            counts[why] += 1
            if not was and why in moved:
                moved[why] += 1
                moved_by_leg[leg] = moved_by_leg.get(leg, 0) + 1
        elif prior is not None and prior != "sweep:window":
            unflagged += 1
        else:
            counts["osm:mainline"] += 1

    payload = "\n".join(
        json.dumps(r, sort_keys=True) for r in sorted(rows, key=lambda r: (r["leg"], r["seq"]))
    )
    meta = json.loads(meta_line)["meta"] if meta_line else {"schema": 1}
    meta["data_version"] = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    params = meta.setdefault("params", {})
    params["connector_source"] = SOURCE_NOTE
    params["connector_corridor_m"] = CORRIDOR_M
    params["connector_freeway_class"] = FREEWAY_CLASS

    return {
        "text": json.dumps({"meta": meta}, sort_keys=True) + "\n" + payload + "\n",
        "counts": counts,
        "rows": len(rows),
        "unread": unread,
        "unflagged": unflagged,
        "moved": moved,
        "moved_by_leg": moved_by_leg,
        "coverage": coverage,
        "highway": highway,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--facts", help=f"facts shard to read (default {FACTS})")
    ap.add_argument("--write", action="store_true", help="rewrite curves.jsonl")
    ap.add_argument("--check", action="store_true", help="exit 1 if the shard is stale")
    ap.add_argument("--report", action="store_true", help="print the breakdown, no write")
    args = ap.parse_args()

    facts_path = Path(args.facts) if args.facts else FACTS
    if not facts_path.exists():
        print(f"no facts shard at {facts_path} -- run tools/curve_osm_facts.py --all first")
        return 1

    result = reclassify(facts_path)
    counts, total = result["counts"], result["rows"]
    conn = total - counts["osm:mainline"]
    print(f"{total} curve rows | {conn} connector, {counts['osm:mainline']} mainline")
    for why in ("osm:ramp", "osm:off-corridor", "sweep:window"):
        print(f"  {why:18s} {counts[why]:6d}")
    read = total - result["unread"]
    print(
        f"READ from OSM: {read}/{total} rows ({100 * read / total:.1f}%); "
        f"{result['unread']} left exactly as the sweep had them (nothing to read)"
    )
    print(
        f"connector by a reading rather than by the sweep's window: "
        f"{result['moved']['osm:ramp']} ramp, {result['moved']['osm:off-corridor']} off-corridor"
        + (f"; {result['unflagged']} re-read as mainline" if result["unflagged"] else "")
    )

    interstate = {
        lid for lid in result["coverage"] if result["highway"].get(lid, "").upper().startswith("I-")
    }
    ranked = sorted(
        ((freeway_coverage(result["coverage"], lid) or 0.0, lid) for lid in interstate),
        key=lambda p: p[0],
    )
    thin = [(cov, lid) for cov, lid in ranked if cov < 0.5]
    print(f"\n{len(thin)} of {len(interstate)} interstate legs ride a freeway for under half")
    print("their route -- these are LABEL defects, not connector-rich roads:")
    for cov, lid in thin[:25]:
        print(
            f"  {lid:52s} {result['highway'].get(lid, ''):8s} freeway {cov:4.0%} "
            f"| {result['moved_by_leg'].get(lid, 0)} curves moved"
        )
    if len(thin) > 25:
        print(f"  ... and {len(thin) - 25} more")

    if args.check:
        if CURVES.read_text(encoding="utf-8") != result["text"]:
            print("\nSTALE: curves.jsonl does not match the facts shard")
            return 1
        print("\nup to date")
        return 0
    if args.write:
        CURVES.write_text(result["text"], encoding="utf-8")
        print(f"\nwrote {CURVES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
