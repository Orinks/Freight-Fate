"""Measure the missing parallel alternates: real ORS routes vs the legs we ship.

Report-only. Writes NOTHING to world data.

The 2026-07-30 completeness audit measured zero same-pair parallel alternate
legs in the whole network -- every "alternate" we model is a multi-hop path
through different cities. Route-selection-at-dispatch has no fuel until the
pairs we already serve have real alternatives. The local ORS holds the
complete US graph, so the real-world alternatives are sitting there unqueried.
This tool asks for them, measures how far each strays from the corridor we
actually ship, and emits the ranked queue of what is worth building.

Usage (local ORS only, never public)::

    ORS_BASE_URL=http://localhost:8080/ors ORS_API_KEY=selfhosted \
      uv run --group tooling python tools/analyze_route_gaps.py \
      --as-of 2026-07-30 --write

Determinism: same graph + same legs -> same report. Everything is sorted and
the report is stamped from ``--as-of``, never the wall clock. Raw ORS payloads
cache under ``.route-cache/gap-alts/`` so a re-run is free and an interrupted
run resumes where it stopped.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import straw_curve_sample as scs  # noqa: E402  (archive geometry decode)
import world_source  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GEOM_DIR = ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "geometry"
CACHE_DIR = ROOT / ".route-cache" / "gap-alts"
REPORT_PATH = ROOT / "logs" / "route-gaps.json"

ORS_PROFILE = "driving-hgv"
ORS_DEFAULT_BASE_URL = "http://localhost:8080/ors"
USER_AGENT = "Freight-Fate gap analyzer (local ORS)"

# Divergence: sample an alternate every SAMPLE_MI and count the fraction of
# samples farther than APART_MI from the corridor we ship. A ramp-level wiggle
# scores near zero; a genuinely different road scores high.
SAMPLE_MI = 2.0
APART_MI = 3.0
DIVERGENT_AT = 0.40
# Two alternates that barely differ from each other are the same road twice
# (ORS's share factor lets them overlap); collapse below this.
SAME_ROAD_UNDER = 0.25

EARTH_MI = 3958.7613


# --- geometry helpers -------------------------------------------------------
def haversine_mi(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Great-circle miles between two points."""
    phi_a, phi_b = math.radians(lat_a), math.radians(lat_b)
    d_phi = phi_b - phi_a
    d_lam = math.radians(lon_b - lon_a)
    hav = math.sin(d_phi / 2) ** 2 + math.cos(phi_a) * math.cos(phi_b) * math.sin(d_lam / 2) ** 2
    return 2 * EARTH_MI * math.asin(math.sqrt(hav))


def densify(coords: list[list[float]], max_gap_mi: float = 0.5) -> list[list[float]]:
    """Split any leg of a polyline longer than ``max_gap_mi`` into even pieces.

    The archived corridor geometry is already ~0.25 mi dense, but a leg that
    falls back to the coarse ``route_points`` can jump 30 mi between vertices.
    Densifying first means a plain nearest-vertex search measures distance to
    the *line*, not to whichever sample happens to be stored.
    """
    if len(coords) < 2:
        return list(coords)
    out: list[list[float]] = [list(coords[0])]
    for prev, cur in zip(coords, coords[1:], strict=False):
        gap = haversine_mi(prev[1], prev[0], cur[1], cur[0])
        steps = int(gap / max_gap_mi)
        for i in range(1, steps + 1):
            frac = i / (steps + 1)
            out.append([prev[0] + (cur[0] - prev[0]) * frac, prev[1] + (cur[1] - prev[1]) * frac])
        out.append(list(cur))
    return out


class PolylineIndex:
    """Grid-bucketed nearest-point lookup against a densified polyline."""

    CELL_DEG = 0.05  # ~3.5 mi of latitude; a cell ring covers the APART_MI gate

    def __init__(self, coords: list[list[float]]) -> None:
        self.points = densify(coords)
        self.cells: dict[tuple[int, int], list[int]] = {}
        for i, (lon, lat) in enumerate(self.points):
            self.cells.setdefault(self._cell(lat, lon), []).append(i)

    def _cell(self, lat: float, lon: float) -> tuple[int, int]:
        return (int(math.floor(lat / self.CELL_DEG)), int(math.floor(lon / self.CELL_DEG)))

    def distance_mi(self, lat: float, lon: float) -> float:
        """Miles from a point to the nearest vertex of the indexed polyline."""
        row, col = self._cell(lat, lon)
        # Two rings out covers APART_MI even where longitude cells run narrow.
        best = float("inf")
        for d_row in (-2, -1, 0, 1, 2):
            for d_col in (-2, -1, 0, 1, 2):
                for i in self.cells.get((row + d_row, col + d_col), ()):
                    p_lon, p_lat = self.points[i]
                    best = min(best, haversine_mi(lat, lon, p_lat, p_lon))
        if best == float("inf"):
            # Nothing nearby at all -- fall back to a full scan so the number
            # stays honest rather than reporting a fake infinity.
            for p_lon, p_lat in self.points:
                best = min(best, haversine_mi(lat, lon, p_lat, p_lon))
        return best


def sample_every(coords: list[list[float]], step_mi: float) -> list[tuple[float, float]]:
    """Walk a polyline and emit ``(lat, lon)`` roughly every ``step_mi``."""
    if len(coords) < 2:
        return [(c[1], c[0]) for c in coords]
    out: list[tuple[float, float]] = [(coords[0][1], coords[0][0])]
    acc = 0.0
    for prev, cur in zip(coords, coords[1:], strict=False):
        acc += haversine_mi(prev[1], prev[0], cur[1], cur[0])
        if acc >= step_mi:
            out.append((cur[1], cur[0]))
            acc = 0.0
    last = (coords[-1][1], coords[-1][0])
    if out[-1] != last:
        out.append(last)
    return out


def divergence(alt_coords: list[list[float]], base: PolylineIndex) -> float:
    """Fraction of an alternate's samples that ride a genuinely different road."""
    samples = sample_every(alt_coords, SAMPLE_MI)
    if not samples:
        return 0.0
    apart = sum(1 for lat, lon in samples if base.distance_mi(lat, lon) > APART_MI)
    return apart / len(samples)


# --- shields ----------------------------------------------------------------
_SHIELD_RE = re.compile(r"\b(I|US|SR|CR|Highway|Hwy)\s*-?\s*(\d+)\b", re.IGNORECASE)
_CLASS_ORDER = ("interstate", "us_highway", "state_highway", "unknown")


def shield_miles(steps: list[dict[str, Any]]) -> dict[str, float]:
    """Miles ridden per highway shield, from ORS step names.

    ORS names a step with whatever the way carries -- often "I 40", sometimes a
    street name plus concurrent refs ("Bear Creek Pike, US 412"), and sometimes
    nothing at all ("-"). Unnamed miles are reported separately rather than
    guessed at.
    """
    by_shield: dict[str, float] = {}
    for step in steps:
        miles = float(step.get("distance", 0.0)) / 1609.344
        name = str(step.get("name", "") or "")
        found = set()
        for prefix, number in _SHIELD_RE.findall(name):
            upper = prefix.upper()
            if upper in ("HIGHWAY", "HWY"):
                upper = "SR"
            found.add(f"{upper}-{number}")
        if not found:
            by_shield["unnamed"] = by_shield.get("unnamed", 0.0) + miles
            continue
        # A concurrency ("US 64, US 70") credits each shield the same miles;
        # the ranking only cares which roads carry the route, not a sum.
        for shield in found:
            by_shield[shield] = by_shield.get(shield, 0.0) + miles
    return by_shield


def road_class(by_shield: dict[str, float]) -> str:
    """Coarse class of the road an alternate mostly rides."""
    named = {k: v for k, v in by_shield.items() if k != "unnamed"}
    if not named:
        return "unknown"
    top = max(named, key=named.__getitem__)
    if top.startswith("I-"):
        return "interstate"
    if top.startswith("US-"):
        return "us_highway"
    return "state_highway"


def top_shields(by_shield: dict[str, float], limit: int = 4) -> list[dict[str, Any]]:
    named = [(k, v) for k, v in by_shield.items() if k != "unnamed"]
    named.sort(key=lambda kv: (-kv[1], kv[0]))
    return [{"shield": k, "miles": round(v, 1)} for k, v in named[:limit]]


# --- ranking ----------------------------------------------------------------
_CLASS_WEIGHT = {
    "interstate": 1.0,
    "us_highway": 0.95,
    "state_highway": 0.7,
    "unknown": 0.45,
}


def candidate_score(
    diverge: float,
    klass: str,
    alt_miles: float,
    base_miles: float,
    alt_hours: float,
    base_hours: float,
) -> float:
    """Rank a candidate: how different, how plausible, how real the tradeoff.

    A wildly longer path is not an alternative a driver would ever weigh, so
    detour ratio penalizes hard past a point. A *shorter* alternate that costs
    time is the most interesting case there is (the classic back-road
    tradeoff), so it earns a bonus.
    """
    if base_miles <= 0:
        return 0.0
    detour = alt_miles / base_miles
    score = diverge * _CLASS_WEIGHT.get(klass, 0.45)
    if detour > 1.75:
        score *= 0.2
    elif detour > 1.35:
        score *= 0.6
    elif detour > 1.15:
        score *= 0.85
    if alt_miles < base_miles and alt_hours > base_hours:
        score *= 1.25  # shorter but slower -- a genuine dispatch decision
    return round(min(score, 1.0), 4)


def tradeoff_label(alt_miles: float, base_miles: float, alt_hours: float, base_hours: float) -> str:
    shorter = alt_miles < base_miles - 1.0
    slower = alt_hours > base_hours + 0.05
    if shorter and slower:
        return "shorter but slower"
    if shorter and not slower:
        return "shorter and faster"
    if not shorter and slower:
        return "longer and slower"
    return "longer but faster"


# --- ORS --------------------------------------------------------------------
def ors_base_url() -> str:
    return os.environ.get("ORS_BASE_URL", ORS_DEFAULT_BASE_URL).rstrip("/")


def _cache_path(from_slug: str, to_slug: str, target_count: int) -> Path:
    return CACHE_DIR / f"{from_slug}--{to_slug}--tc{target_count}.json"


def fetch_alternatives(
    start: dict[str, Any],
    end: dict[str, Any],
    *,
    target_count: int,
    timeout_s: float,
) -> dict[str, Any]:
    """One local-ORS directions call asking for alternatives, raw GeoJSON back.

    Plain urllib rather than the SDK: the SDK has no alternative_routes
    passthrough on the geojson endpoint and we want the raw payload cached
    verbatim anyway.
    """
    body = {
        "coordinates": [
            [float(start["lon"]), float(start["lat"])],
            [float(end["lon"]), float(end["lat"])],
        ],
        "instructions": True,
        "extra_info": ["tollways", "waytype"],
        "alternative_routes": {
            "target_count": target_count,
            "weight_factor": 1.6,
            "share_factor": 0.6,
        },
    }
    request = urllib.request.Request(
        f"{ors_base_url()}/v2/directions/{ORS_PROFILE}/geojson",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": os.environ.get("ORS_API_KEY", "selfhosted"),
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return json.loads(response.read().decode("utf-8"))


def cached_alternatives(
    start: dict[str, Any],
    end: dict[str, Any],
    from_slug: str,
    to_slug: str,
    *,
    target_count: int,
    timeout_s: float,
    rate_limit_s: float,
) -> dict[str, Any]:
    path = _cache_path(from_slug, to_slug, target_count)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    payload = fetch_alternatives(start, end, target_count=target_count, timeout_s=timeout_s)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    if rate_limit_s > 0:
        time.sleep(rate_limit_s)
    return payload


# --- world data -------------------------------------------------------------
def load_geometry_archive() -> dict[str, list[list[float]]]:
    """Every leg's dense archived route, keyed ``from_slug:to_slug``."""
    archive: dict[str, list[list[float]]] = {}
    for shard in sorted(GEOM_DIR.glob("*.jsonl")):
        for line in shard.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith('{"meta"'):
                continue
            record = json.loads(line)
            archive[record["leg"]] = scs.decode_geometry(record["geom"])
    return archive


def baked_coords(
    leg: dict[str, Any], archive: dict[str, list[list[float]]]
) -> tuple[list[list[float]], str]:
    """The corridor we actually ship, densest source first."""
    key = f"{leg['from']}:{leg['to']}"
    coords = archive.get(key)
    if coords and len(coords) >= 2:
        return coords, "geometry_archive"
    points = leg.get("corridor", {}).get("route_points") or []
    return [[float(p["lon"]), float(p["lat"])] for p in points], "route_points"


def route_features(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return list(payload.get("features") or [])


def feature_summary(feature: dict[str, Any]) -> tuple[float, float]:
    summary = feature.get("properties", {}).get("summary", {})
    miles = float(summary.get("distance", 0.0)) / 1609.344
    hours = float(summary.get("duration", 0.0)) / 3600.0
    return miles, hours


def feature_steps(feature: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for segment in feature.get("properties", {}).get("segments", []) or []:
        steps.extend(segment.get("steps", []) or [])
    return steps


def feature_has_toll(feature: dict[str, Any]) -> bool:
    tollways = feature.get("properties", {}).get("extras", {}).get("tollways", {})
    return any(len(v) >= 3 and v[2] for v in tollways.get("values", []) or [])


def feature_coords(feature: dict[str, Any]) -> list[list[float]]:
    return [[float(p[0]), float(p[1])] for p in feature.get("geometry", {}).get("coordinates", [])]


# --- per-pair analysis ------------------------------------------------------
def analyze_pair(
    leg: dict[str, Any],
    cities: dict[str, Any],
    archive: dict[str, list[list[float]]],
    *,
    target_count: int,
    timeout_s: float,
    rate_limit_s: float,
) -> dict[str, Any]:
    from_slug, to_slug = leg["from"], leg["to"]
    result: dict[str, Any] = {
        "from": from_slug,
        "to": to_slug,
        "highway": leg.get("highway", ""),
        "leg_miles": round(float(leg.get("miles", 0.0)), 1),
        "geometry_source": "",
        "ors_routes": 0,
        "alternates": [],
        "best_score": 0.0,
        "error": "",
    }
    coords, source = baked_coords(leg, archive)
    result["geometry_source"] = source
    if len(coords) < 2:
        result["error"] = "no baked geometry"
        return result
    try:
        payload = cached_alternatives(
            cities[from_slug],
            cities[to_slug],
            from_slug,
            to_slug,
            target_count=target_count,
            timeout_s=timeout_s,
            rate_limit_s=rate_limit_s,
        )
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        detail = ""
        if isinstance(exc, urllib.error.HTTPError):
            try:
                detail = json.loads(exc.read().decode("utf-8"))["error"]["message"]
            except Exception:  # noqa: BLE001 -- error body shape is not contractual
                detail = str(exc)
        result["error"] = detail or str(exc)
        return result

    features = route_features(payload)
    result["ors_routes"] = len(features)
    if not features:
        result["error"] = "ORS returned no route"
        return result

    base_index = PolylineIndex(coords)
    primary_miles, primary_hours = feature_summary(features[0])
    result["ors_primary_miles"] = round(primary_miles, 1)
    result["ors_primary_hours"] = round(primary_hours, 2)
    # How far ORS's own best route sits from the corridor we ship. High here
    # means our leg is curated onto a road ORS would not pick -- context for
    # reading the alternates, not a defect.
    result["primary_divergence"] = round(divergence(feature_coords(features[0]), base_index), 3)

    kept: list[dict[str, Any]] = []
    for feature in features[1:]:
        alt_coords = feature_coords(feature)
        if len(alt_coords) < 2:
            continue
        diverge = divergence(alt_coords, base_index)
        alt_miles, alt_hours = feature_summary(feature)
        by_shield = shield_miles(feature_steps(feature))
        klass = road_class(by_shield)
        candidate = {
            "divergence": round(diverge, 3),
            "miles": round(alt_miles, 1),
            "hours": round(alt_hours, 2),
            "miles_delta": round(alt_miles - primary_miles, 1),
            "hours_delta": round(alt_hours - primary_hours, 2),
            "road_class": klass,
            "shields": top_shields(by_shield),
            "unnamed_miles": round(by_shield.get("unnamed", 0.0), 1),
            "tollway": feature_has_toll(feature),
            "tradeoff": tradeoff_label(alt_miles, primary_miles, alt_hours, primary_hours),
            "score": candidate_score(
                diverge, klass, alt_miles, primary_miles, alt_hours, primary_hours
            ),
            "_coords": alt_coords,
        }
        if diverge < DIVERGENT_AT:
            continue
        # Collapse near-duplicate alternates (ORS's share factor lets two
        # returned routes ride the same road with a different ramp).
        duplicate = False
        for existing in kept:
            if divergence(alt_coords, PolylineIndex(existing["_coords"])) < SAME_ROAD_UNDER:
                duplicate = True
                if candidate["score"] > existing["score"]:
                    existing.update(candidate)
                break
        if not duplicate:
            kept.append(candidate)

    for candidate in kept:
        candidate.pop("_coords", None)
    kept.sort(key=lambda c: (-c["score"], -c["divergence"], c["miles"]))
    result["alternates"] = kept
    result["best_score"] = kept[0]["score"] if kept else 0.0
    return result


def summary_line(pair: dict[str, Any]) -> str:
    """One spoken-style line for the top-N summary."""
    best = pair["alternates"][0]
    shields = ", ".join(s["shield"] for s in best["shields"]) or "unnamed roads"
    return (
        f"{pair['from']}->{pair['to']}: {pair['highway'] or 'existing leg'} exists "
        f"({pair['leg_miles']:.0f} mi); {shields} alternate diverges "
        f"{best['divergence'] * 100:.0f}%, {best['miles']:.0f} mi, "
        f"{best['road_class'].replace('_', ' ')}, {best['tradeoff']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True, help="Report date stamp (YYYY-MM-DD).")
    parser.add_argument("--write", action="store_true", help="Write logs/route-gaps.json.")
    parser.add_argument("--limit", type=int, default=0, help="Analyze only the first N legs.")
    parser.add_argument("--only", default="", help="Semicolon list of from:to pairs.")
    parser.add_argument("--workers", type=int, default=3, help="Concurrent ORS queries.")
    parser.add_argument("--target-count", type=int, default=3, help="Alternates to request.")
    parser.add_argument("--timeout", type=float, default=180.0, help="Per-request timeout.")
    parser.add_argument("--rate-limit", type=float, default=0.0, help="Sleep after each fetch.")
    parser.add_argument("--top", type=int, default=50, help="Summary lines to print.")
    args = parser.parse_args(argv)

    data = world_source.load_world()
    cities = data["cities"]
    legs = [leg for leg in data["legs"] if leg["from"] in cities and leg["to"] in cities]
    if args.only:
        wanted = {pair.strip() for pair in args.only.split(";") if pair.strip()}
        legs = [leg for leg in legs if f"{leg['from']}:{leg['to']}" in wanted]
    legs.sort(key=lambda leg: (leg["from"], leg["to"]))
    if args.limit:
        legs = legs[: args.limit]

    archive = load_geometry_archive()
    print(f"legs: {len(legs)}  geometry archive: {len(archive)}  ORS: {ors_base_url()}")

    def run(leg: dict[str, Any]) -> dict[str, Any]:
        return analyze_pair(
            leg,
            cities,
            archive,
            target_count=args.target_count,
            timeout_s=args.timeout,
            rate_limit_s=args.rate_limit,
        )

    pairs: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for done, pair in enumerate(pool.map(run, legs), start=1):
            pairs.append(pair)
            if done % 25 == 0 or done == len(legs):
                with_alt = sum(1 for p in pairs if p["alternates"])
                print(f"  {done}/{len(legs)} analyzed, {with_alt} with a real alternate")

    pairs.sort(key=lambda p: (p["from"], p["to"]))
    errors = [p for p in pairs if p["error"]]
    with_alt = [p for p in pairs if p["alternates"]]
    ranked = sorted(with_alt, key=lambda p: (-p["best_score"], p["from"], p["to"]))

    report = {
        "as_of": args.as_of,
        "profile": ORS_PROFILE,
        "ors_base_url": ors_base_url(),
        "params": {
            "sample_mi": SAMPLE_MI,
            "apart_mi": APART_MI,
            "divergent_at": DIVERGENT_AT,
            "same_road_under": SAME_ROAD_UNDER,
            "target_count": args.target_count,
        },
        "counts": {
            "pairs_analyzed": len(pairs),
            "pairs_with_alternate": len(with_alt),
            "pairs_without_alternate": len(pairs) - len(with_alt) - len(errors),
            "pairs_errored": len(errors),
            "alternates_total": sum(len(p["alternates"]) for p in with_alt),
            "by_class": {
                klass: sum(1 for p in with_alt if p["alternates"][0]["road_class"] == klass)
                for klass in _CLASS_ORDER
            },
        },
        "ranked": [
            {
                "from": p["from"],
                "to": p["to"],
                "score": p["best_score"],
                "summary": summary_line(p),
            }
            for p in ranked
        ],
        "pairs": pairs,
    }

    print()
    print(f"pairs analyzed:            {len(pairs)}")
    print(f"pairs with a real alternate {len(with_alt)}")
    print(f"pairs with none            {len(pairs) - len(with_alt) - len(errors)}")
    print(f"pairs errored              {len(errors)}")
    print()
    for line in report["ranked"][: args.top]:
        print("  " + line["summary"])

    if args.write:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\nwrote {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
