"""Copy honest truck stops onto opposite-direction overlapping legs.

Directed legs are not exact A↔B reverses. Opposite traffic is a different row.
This finds same-highway partners with opposite travel vectors and geographic
overlap, then copies tractor-trailer truck facilities that sit on the partner's
geometry but are missing there.

Does not invent city pairs. Does not promote convenience plazas. Idempotent.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from fill_truck_access_gaps import _gap_fill_access
from leg_geometry import corridor_geometry
from world_source import load_world, save_world

ROOT = Path(__file__).resolve().parents[1]
EARTH_RADIUS_MI = 3958.7613
MAX_OFF_MI = 2.0
NEAR_MI = 5.0
NEAR_LATLON_MI = 0.5
HONEST_TYPES = {
    "truck_stop",
    "travel_center",
    "truck_parking",
    "service_plaza",
    "public_rest_area",
}
TRUCK_NAME_WORDS = (
    "travel center",
    "travel stop",
    "travel plaza",
    "truck stop",
    "truckstop",
    "flying j",
    "love's",
    "loves ",
    "pilot",
    "petro",
    "little america",
    "iowa 80",
    "sapp bros",
    "road ranger",
    "ambest",
    "ta travel",
    "one9",
)


def _city_ll(cities: dict[str, Any], slug: str) -> tuple[float, float] | None:
    city = cities.get(slug) or {}
    lat, lon = city.get("lat"), city.get("lon")
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def _highway_key(leg: dict[str, Any]) -> str:
    highway = str(leg.get("highway") or "").strip()
    if not highway:
        return ""
    return highway.split()[0]


def _direction(cities: dict[str, Any], leg: dict[str, Any]) -> tuple[float, float] | None:
    start = _city_ll(cities, leg["from"])
    end = _city_ll(cities, leg["to"])
    if start is None or end is None:
        return None
    return (end[0] - start[0], end[1] - start[1])


def _dot(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


def _polyline(leg: dict[str, Any]) -> list[tuple[float, float, float]]:
    line = corridor_geometry(leg)
    if line and len(line) >= 2:
        return line
    points = (leg.get("corridor") or {}).get("route_points") or []
    out = [
        (float(p["lat"]), float(p["lon"]), float(p["at_mi"]))
        for p in points
        if "lat" in p and "lon" in p and "at_mi" in p
    ]
    return sorted(out, key=lambda row: row[2])


def _project(line: list[tuple[float, float, float]], lat: float, lon: float) -> tuple[float, float]:
    best_mi, best_d = line[0][2], float("inf")
    for plat, plon, mi in line:
        d = _haversine_mi(lat, lon, plat, plon)
        if d < best_d:
            best_d, best_mi = d, mi
    # refine around the nearest vertex
    miles = line[-1][2]
    lo = max(0.0, best_mi - 15.0)
    hi = min(miles, best_mi + 15.0)
    step = 0.25
    mi = lo
    while mi <= hi:
        # interpolate
        if mi <= line[0][2]:
            plat, plon = line[0][0], line[0][1]
        elif mi >= line[-1][2]:
            plat, plon = line[-1][0], line[-1][1]
        else:
            plat = plon = 0.0
            for (a_lat, a_lon, a_mi), (b_lat, b_lon, b_mi) in zip(line, line[1:], strict=False):
                if a_mi <= mi <= b_mi:
                    span = b_mi - a_mi
                    t = 0.0 if span <= 0 else (mi - a_mi) / span
                    plat = a_lat + (b_lat - a_lat) * t
                    plon = a_lon + (b_lon - a_lon) * t
                    break
        d = _haversine_mi(lat, lon, plat, plon)
        if d < best_d:
            best_d, best_mi = d, mi
        mi += step
    return best_mi, best_d


def _point_at(line: list[tuple[float, float, float]], at_mi: float) -> tuple[float, float] | None:
    if not line:
        return None
    if at_mi <= line[0][2]:
        return line[0][0], line[0][1]
    for (a_lat, a_lon, a_mi), (b_lat, b_lon, b_mi) in zip(line, line[1:], strict=False):
        if a_mi <= at_mi <= b_mi:
            span = b_mi - a_mi
            t = 0.0 if span <= 0 else (at_mi - a_mi) / span
            return a_lat + (b_lat - a_lat) * t, a_lon + (b_lon - a_lon) * t
    return line[-1][0], line[-1][1]


def _bbox(line: list[tuple[float, float, float]], cities: dict[str, Any], leg: dict[str, Any]):
    pts = list(line)
    for slug in (leg["from"], leg["to"]):
        ll = _city_ll(cities, slug)
        if ll is not None:
            pts.append((ll[0], ll[1], 0.0))
    if not pts:
        return None
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    return min(lats), max(lats), min(lons), max(lons)


def _overlap(a, b, pad: float = 0.2) -> bool:
    if a is None or b is None:
        return False
    a0, a1, o0, o1 = a
    c0, c1, p0, p1 = b
    return not (a1 + pad < c0 or c1 + pad < a0 or o1 + pad < p0 or p1 + pad < o0)


def _norm_name(name: str) -> str:
    return " ".join(str(name).lower().replace("’", "'").split())


# Mirrors ff-core `data::world_constants::screened_vehicle_access`; change them
# together. A fuel-type stop is truck-serving on evidence, not on its type:
# `service_plaza` was the import's word for any OpenStreetMap highway=services
# feature, and that tag sits on bus bays and industrial suppliers too. Until
# 2026-09-17 the type alone made a record honest, which copied "Horner
# Industrial Group" and "Trailers Plus Salt Lake City" onto partner legs.
_SCREENED_TYPES = {"travel_center", "service_plaza", "fuel_station"}
_ACCESS_NAME_WORDS = (
    "truck",
    "travel",
    "plaza",
    "rest area",
    "service area",
    "traffic center",
    "fuel center",
    "welcome center",
)


def _access_screen_allows(stop: dict[str, Any]) -> bool:
    """Whether the game's load-time access screen reads this stop as open to a
    tractor-trailer."""
    if str(stop.get("type") or "") not in _SCREENED_TYPES:
        return True
    if stop.get("parking") == "confirmed" or int(stop.get("parking_spaces") or 0) > 0:
        return True
    if any(service in ("scale", "showers") for service in stop.get("services") or []):
        return True
    lowered = _norm_name(stop.get("name") or "")
    return _chain(lowered) is not None or any(word in lowered for word in _ACCESS_NAME_WORDS)


def _is_honest(stop: dict[str, Any]) -> bool:
    if str(stop.get("vehicle_access", "tractor_trailer")) != "tractor_trailer":
        return False
    name = str(stop.get("name") or "")
    # never promote convenience plazas
    if _gap_fill_access(name) == "bobtail_only":
        return False
    if not _access_screen_allows(stop):
        return False
    stop_type = str(stop.get("type") or "")
    lowered = _norm_name(name)
    if stop_type in HONEST_TYPES:
        return True
    return any(word in lowered for word in TRUCK_NAME_WORDS)


def _one_way_only(stop: dict[str, Any]) -> bool:
    directions = stop.get("directions")
    if not directions:
        return False
    dirs = {str(d).lower() for d in directions}
    return dirs in ({"forward"}, {"reverse"})


# Mirrors ff-core `data::stop_twins`; change them together.
TWIN_STOP_MILES = 4.0
_CHAINS = (
    "love's", "pilot", "flying j", "ta ", "travelcenters", "petro", "road ranger",
    "one9", "sapp bros", "sapp brothers", "bosselman", "iowa 80", "little america", "ambest",
    "roady's", "stamart", "onvo", "kwik trip", "kwik star",
)  # fmt: skip
_GENERIC_NAME_WORDS = frozenset(
    [
        "travel",
        "center",
        "centre",
        "centers",
        "travelcenter",
        "travelcenters",
        "stop",
        "stopping",
        "plaza",
        "truck",
        "the",
        "service",
        "area",
        "station",
        "store",
        "country",
        "dealer",
        "of",
        "america",
        "and",
        "express",
        "fuel",
        "shopping",
    ]
)


def _chain(name: str) -> str | None:
    lowered = _norm_name(name)
    for chain in _CHAINS:
        if lowered.startswith(chain) or lowered == chain.strip():
            return chain
    return None


def _place_words(name: str, chain: str) -> frozenset[str]:
    rest = _norm_name(name).removeprefix(chain.strip())
    words = "".join(ch if ch.isalnum() else " " for ch in rest).split()
    return frozenset(
        w for w in words if len(w) > 1 and not w.isdigit() and w not in _GENERIC_NAME_WORDS
    )


def _same_chain_store(a: str, b: str) -> bool:
    chain = _chain(a)
    if chain is None or chain != _chain(b):
        return False
    place_a, place_b = _place_words(a, chain), _place_words(b, chain)
    return not place_a or not place_b or place_a == place_b


def _already_on_leg(
    dest: dict[str, Any],
    name: str,
    lat: float | None,
    lon: float | None,
    at_mi: float,
) -> bool:
    target = _norm_name(name)
    for stop in dest.get("stops") or []:
        if (
            _norm_name(stop.get("name")) == target
            and abs(float(stop.get("at_mi", 0.0)) - at_mi) <= NEAR_MI
        ):
            return True
        if _same_chain_store(name, str(stop.get("name") or "")) and (
            abs(float(stop.get("at_mi", 0.0)) - at_mi) <= TWIN_STOP_MILES
        ):
            # The partner already lists this store under another name: the
            # map import's bare "Flying J Travel Center" and the locator's
            # "Flying J Travel Center Corfu" are one Flying J. Copying it
            # would hand the leg a twin (ff-core `data::stop_twins` screens
            # the ones already in the data, and owns the four-mile figure).
            return True
        if lat is None or lon is None:
            continue
        slat, slon = stop.get("lat"), stop.get("lon")
        if slat is None or slon is None:
            continue
        if _haversine_mi(float(lat), float(lon), float(slat), float(slon)) <= NEAR_LATLON_MI:
            return True
    return False


def find_partnerships(data: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    cities = data["cities"]
    by_hwy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    lines: dict[tuple[str, str], list[tuple[float, float, float]]] = {}
    for leg in data["legs"]:
        key = _highway_key(leg)
        if key:
            by_hwy[key].append(leg)
        lines[(leg["from"], leg["to"])] = _polyline(leg)

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[tuple[tuple[str, str], tuple[str, str]]] = set()
    for legs in by_hwy.values():
        for i, a in enumerate(legs):
            da = _direction(cities, a)
            if da is None or da == (0.0, 0.0):
                continue
            la = lines[(a["from"], a["to"])]
            ba = _bbox(la, cities, a)
            for b in legs[i + 1 :]:
                db = _direction(cities, b)
                if db is None or db == (0.0, 0.0):
                    continue
                if _dot(da, db) >= 0:
                    continue
                lb = lines[(b["from"], b["to"])]
                if not _overlap(ba, _bbox(lb, cities, b)):
                    continue
                # require at least one shared geometry hit within ~15 mi
                shared = False
                sample = la[:: max(1, len(la) // 12)] or la
                for plat, plon, _ in sample:
                    for qlat, qlon, _ in lb[:: max(1, len(lb) // 12)] or lb:
                        if _haversine_mi(plat, plon, qlat, qlon) <= 15.0:
                            shared = True
                            break
                    if shared:
                        break
                if not shared:
                    continue
                key = tuple(sorted(((a["from"], a["to"]), (b["from"], b["to"]))))
                if key in seen:
                    continue
                seen.add(key)
                pairs.append((a, b))
    return pairs


def missing_copies(
    src: dict[str, Any],
    dst: dict[str, Any],
    src_line: list[tuple[float, float, float]],
    dst_line: list[tuple[float, float, float]],
) -> list[tuple[dict[str, Any], float, float, float]]:
    """Return (stop, at_mi_on_dst, lat, lon) candidates to copy."""
    if len(dst_line) < 2:
        return []
    miles = float(dst.get("miles") or 0.0)
    out: list[tuple[dict[str, Any], float, float, float]] = []
    for stop in src.get("stops") or []:
        if not _is_honest(stop) or _one_way_only(stop):
            continue
        lat, lon = stop.get("lat"), stop.get("lon")
        if lat is None or lon is None:
            point = _point_at(src_line, float(stop.get("at_mi") or 0.0))
            if point is None:
                continue
            lat, lon = point
        lat_f, lon_f = float(lat), float(lon)
        at_mi, off = _project(dst_line, lat_f, lon_f)
        if off > MAX_OFF_MI:
            continue
        at_mi = round(min(max(at_mi, 0.1), max(0.1, round(miles - 0.1, 1))), 1)
        if _already_on_leg(dst, str(stop.get("name") or ""), lat_f, lon_f, at_mi):
            continue
        out.append((stop, at_mi, lat_f, lon_f))
    return out


def copy_stop(stop: dict[str, Any], at_mi: float, lat: float, lon: float) -> dict[str, Any]:
    copied = dict(stop)
    copied["at_mi"] = at_mi
    copied["lat"] = lat
    copied["lon"] = lon
    copied["vehicle_access"] = "tractor_trailer"
    note = str(copied.get("source") or "").strip()
    suffix = "Opposite-direction copy onto overlapping same-highway partner; curated 2026-09-16."
    # A copy of a copy (A to B, then B to its other partner C) is still one
    # copy of the original; the note used to stack once per hop.
    if suffix not in note:
        copied["source"] = f"{note} {suffix}".strip() if note else suffix
    # default both unless the original was already both
    if not copied.get("directions"):
        copied["directions"] = ["both"]
    return copied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    data = load_world()
    pairs = find_partnerships(data)
    print(f"{len(pairs)} opposite-direction overlapping same-highway partnership(s).")

    lines = {(leg["from"], leg["to"]): _polyline(leg) for leg in data["legs"]}
    missing_partner_dirs = 0
    missing_copy_count = 0
    added = 0
    top: list[tuple[int, str]] = []

    for a, b in pairs:
        for src, dst in ((a, b), (b, a)):
            src_line = lines[(src["from"], src["to"])]
            dst_line = lines[(dst["from"], dst["to"])]
            cands = missing_copies(src, dst, src_line, dst_line)
            if not cands:
                continue
            missing_partner_dirs += 1
            missing_copy_count += len(cands)
            label = (
                f"{src['from']}->{src['to']} => {dst['from']}->{dst['to']} "
                f"({len(cands)}): "
                + ", ".join(f"{s.get('name')}@{mi}" for s, mi, _, _ in cands[:4])
            )
            top.append((len(cands), label))
            if args.write:
                for stop, at_mi, lat, lon in cands:
                    if args.limit and added >= args.limit:
                        break
                    # re-check after earlier inserts
                    if _already_on_leg(dst, str(stop.get("name") or ""), lat, lon, at_mi):
                        continue
                    dst.setdefault("stops", []).append(copy_stop(stop, at_mi, lat, lon))
                    added += 1
                dst.get("stops", []).sort(key=lambda s: float(s.get("at_mi", 0.0)))

    top.sort(reverse=True)
    print(
        f"{missing_partner_dirs} partnership-direction(s) missing ≥1 honest truck stop "
        f"({(100.0 * missing_partner_dirs / max(1, 2 * len(pairs))):.0f}% of directed partners)."
    )
    print(f"{missing_copy_count} missing copy candidate(s).")
    if args.report:
        print("\nTop diffs:")
        for count, label in top[:25]:
            print(f"  {count:3}  {label}")

    if args.write:
        print(f"\nCopied {added} stop(s). Wrote {save_world(data)} shard(s).")
    else:
        print("\nDry run. Re-run with --write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
