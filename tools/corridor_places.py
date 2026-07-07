"""List real named places along a leg's route -- the candidate engine.

The scale tool behind docs/map-enrichment-recipe.md and the interstate
spider. Given a leg (or any two coordinates), it fetches the real ORS
driving-hgv route, then reports every real US populated place within a
buffer of that route, ordered along the drive, with population and
off-route distance. Two uses:

- **Enrich an existing leg**: `--leg from_slug:to_slug` prints ready-to-use
  ``--candidate`` strings for tools/place_checkpoints.py. Places that are
  already city nodes are dropped (they are not checkpoints).
- **Spider a corridor**: `--from-coord/--to-coord` (or a long leg) with
  `--min-pop` raised prints the real towns/cities along a highway between
  two anchors -- the raw material for deciding new nodes and legs in a
  sparse region.

Data: GeoNames US populated places (CC BY), cached under .route-cache/.
Read-only -- never writes world.json. Review the list, then feed the ones
you want to place_checkpoints (checkpoints) or add as nodes (spider).
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import enrich_routes as er  # noqa: E402
import pick_nodes as pn  # noqa: E402

GEONAMES_US_URL = "https://download.geonames.org/export/dump/US.zip"
# Feature codes under class P we do NOT want as checkpoints/nodes: neighborhoods
# (sections of a larger place), and destroyed/abandoned/historical/religious
# populated places -- none are a place a driver passes and orients by today.
_DROP_FEATURE_CODES = frozenset({"PPLX", "PPLW", "PPLQ", "PPLH", "PPLR"})
_FILTERED_CACHE = "us_populated_places.json"


def load_us_places(cache_dir: Path) -> list[dict[str, Any]]:
    """All contiguous-US populated places from the GeoNames US dump.

    Parses the full country file once (feature class P, minus neighborhoods
    and defunct places) and caches the compact result, so later runs skip the
    ~2M-row parse. Each place: name, state (full spoken), lat, lon, population.
    """
    filtered = cache_dir / "geonames" / _FILTERED_CACHE
    if filtered.exists():
        return json.loads(filtered.read_text(encoding="utf-8"))
    admin1 = pn.parse_admin1(
        pn._cached_bytes(cache_dir, "admin1CodesASCII.txt", pn.GEONAMES_ADMIN1_URL).decode("utf-8")
    )
    zip_bytes = pn._cached_bytes(cache_dir, "US.zip", GEONAMES_US_URL)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        text = zf.read("US.txt").decode("utf-8")
    places: list[dict[str, Any]] = []
    for line in text.splitlines():
        cols = line.split("\t")
        if len(cols) < 15 or cols[6] != "P" or cols[7] in _DROP_FEATURE_CODES:
            continue
        state = admin1.get(cols[10])
        if state is None or state in pn.NON_CONTIGUOUS_STATES:
            continue
        try:
            places.append(
                {
                    "name": cols[1],
                    "state": state,
                    "lat": float(cols[4]),
                    "lon": float(cols[5]),
                    "population": int(cols[14] or 0),
                }
            )
        except ValueError:
            continue
    filtered.parent.mkdir(parents=True, exist_ok=True)
    filtered.write_text(json.dumps(places), encoding="utf-8")
    return places


def _cumulative_miles(coords: list[list[float]]) -> list[float]:
    cumulative = [0.0]
    for i in range(1, len(coords)):
        lon1, lat1 = coords[i - 1][0], coords[i - 1][1]
        lon2, lat2 = coords[i][0], coords[i][1]
        cumulative.append(cumulative[-1] + pn._haversine_miles(lat1, lon1, lat2, lon2))
    return cumulative


def corridor_candidates(
    coords: list[list[float]],
    route_miles: float,
    leg_miles: float,
    places: list[dict[str, Any]],
    node_coords: list[tuple[float, float]],
    *,
    buffer_mi: float,
    dedupe_mi: float,
    min_pop: int,
    min_spacing_mi: float,
) -> list[dict[str, Any]]:
    """Places within ``buffer_mi`` of the route, ordered along the drive.

    Bounding-box prunes first (so we scan the whole US place list cheaply),
    then nearest-vertex matches survivors. Drops places near an existing node
    (``dedupe_mi``) and thins clusters so a run of adjacent hamlets collapses
    to the largest within ``min_spacing_mi`` -- keeping the candidate list to
    real orientation points, not every crossroads.
    """
    if len(coords) < 2:
        raise ValueError("route needs at least 2 vertices")
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    margin = buffer_mi / 60.0 + 0.05  # deg; generous, bbox is just a coarse prune
    lo_lon, hi_lon = min(lons) - margin, max(lons) + margin
    lo_lat, hi_lat = min(lats) - margin, max(lats) + margin
    cumulative = _cumulative_miles(coords)
    total = cumulative[-1] or route_miles or 1.0

    near: list[dict[str, Any]] = []
    for place in places:
        if place["population"] < min_pop:
            continue
        lat, lon = place["lat"], place["lon"]
        if not (lo_lat <= lat <= hi_lat and lo_lon <= lon <= hi_lon):
            continue
        best_off = float("inf")
        best_i = 0
        for i, coord in enumerate(coords):
            off = pn._haversine_miles(lat, lon, coord[1], coord[0])
            if off < best_off:
                best_off, best_i = off, i
        if best_off > buffer_mi:
            continue
        at_mi = round(max(0.0, min(leg_miles, cumulative[best_i] / total * leg_miles)), 1)
        if any(pn._haversine_miles(lat, lon, nlat, nlon) <= dedupe_mi for nlat, nlon in node_coords):
            continue  # already a city node -- not a checkpoint candidate
        near.append({**place, "at_mi": at_mi, "off_mi": round(best_off, 2)})

    near.sort(key=lambda p: p["at_mi"])
    # Thin clusters: within a spacing window, keep the largest place only.
    kept: list[dict[str, Any]] = []
    for cand in near:
        clash = next((k for k in kept if abs(k["at_mi"] - cand["at_mi"]) < min_spacing_mi), None)
        if clash is None:
            kept.append(cand)
        elif cand["population"] > clash["population"]:
            kept[kept.index(clash)] = cand
    kept.sort(key=lambda p: p["at_mi"])
    return kept


def _state_code(data: dict[str, Any], full_name: str) -> str:
    """The 2-letter code place_checkpoints accepts, from a full state name."""
    for country in data.get("geo", {}).get("countries", {}).values():
        for code, name in country.get("states", {}).items():
            if name == full_name:
                return code
    return full_name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leg", help="Existing leg as 'from_slug:to_slug'.")
    parser.add_argument("--from-coord", help="Spider mode: 'lat,lon' start.")
    parser.add_argument("--to-coord", help="Spider mode: 'lat,lon' end.")
    parser.add_argument("--highway", default="corridor", help="Highway label for spider mode.")
    parser.add_argument("--buffer-mi", type=float, default=2.0, help="Max off-route distance.")
    parser.add_argument("--min-pop", type=int, default=0, help="Drop places below this population.")
    parser.add_argument(
        "--dedupe-mi", type=float, default=6.0, help="Drop places this close to an existing node."
    )
    parser.add_argument(
        "--min-spacing-mi",
        type=float,
        default=8.0,
        help="Collapse clusters within this window to the largest place.",
    )
    parser.add_argument("--cache-dir", default=str(er.CACHE_PATH))
    parser.add_argument("--rate-limit", type=float, default=0.5)
    args = parser.parse_args(argv)

    api_key = er.ors_api_key()
    if api_key is None:
        raise SystemExit(
            f"Needs {er.ORS_API_KEY_ENV} and the tooling group (uv run --group tooling ...)."
        )
    data = json.loads(er.WORLD_PATH.read_text(encoding="utf-8"))
    cache_dir = Path(args.cache_dir)
    places = load_us_places(cache_dir)
    node_coords = [(float(c["lat"]), float(c["lon"])) for c in data["cities"].values()]

    if args.leg:
        from_city, _, to_city = args.leg.partition(":")
        leg = next(
            (
                candidate
                for candidate in data["legs"]
                if candidate["from"] == from_city.strip() and candidate["to"] == to_city.strip()
            ),
            None,
        )
        if leg is None:
            raise SystemExit(f"No leg {args.leg!r} in world.json")
        parsed = er._cached_ors_route(data, leg, cache_dir, args.rate_limit, api_key)
        leg_miles = float(leg["miles"])
        highway = leg["highway"]
        label = f"{leg['from']} -> {leg['to']}"
    elif args.from_coord and args.to_coord:
        fa, fo = (float(x) for x in args.from_coord.split(","))
        ta, to = (float(x) for x in args.to_coord.split(","))
        payload = er.fetch_ors_hgv_route({"lat": fa, "lon": fo}, {"lat": ta, "lon": to}, api_key)
        parsed = er.parse_ors_route(payload)
        leg_miles = float(parsed["miles"])
        highway = args.highway
        label = f"{args.from_coord} -> {args.to_coord} ({leg_miles:.0f} mi)"
    else:
        raise SystemExit("Pass --leg, or both --from-coord and --to-coord.")

    cands = corridor_candidates(
        parsed["coordinates"],
        float(parsed["miles"]),
        leg_miles,
        places,
        node_coords,
        buffer_mi=args.buffer_mi,
        dedupe_mi=args.dedupe_mi,
        min_pop=args.min_pop,
        min_spacing_mi=args.min_spacing_mi,
    )

    print(f"# {label} | {highway} | {len(cands)} candidate place(s) within {args.buffer_mi}mi")
    print(f"# (min_pop={args.min_pop}, dedupe={args.dedupe_mi}mi, spacing={args.min_spacing_mi}mi)")
    for c in cands:
        code = _state_code(data, c["state"])
        pop = f"pop {c['population']:,}" if c["population"] else "pop n/a"
        print(
            f'  --candidate "{c["name"]}|{c["lat"]:.4f}|{c["lon"]:.4f}|{code}"'
            f'   # mi {c["at_mi"]}, {c["off_mi"]}mi off, {pop}'
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
