# ruff: noqa: F401,F403,F405,F821,I001
from __future__ import annotations

from enrich_routes_base import *


def ors_api_key() -> str | None:
    """The OpenRouteService key from the environment, or None when unset.

    Build-time only: the key is read here in the tooling and is never bundled
    with the game or read at runtime.
    """
    key = os.environ.get(ORS_API_KEY_ENV, "").strip()
    return key or None


def _ors_directions_kwargs(start: dict[str, Any], end: dict[str, Any]) -> dict[str, Any]:
    """The driving-hgv directions request as SDK keyword arguments.

    Pure, so it is unit-testable without the SDK installed.
    """
    return {
        "coordinates": [
            [float(start["lon"]), float(start["lat"])],
            [float(end["lon"]), float(end["lat"])],
        ],
        "profile": ORS_HGV_PROFILE,
        "format": "geojson",
        "elevation": True,
        "extra_info": list(ORS_EXTRA_INFO),
    }


def fetch_ors_hgv_route(
    start: dict[str, Any],
    end: dict[str, Any],
    api_key: str,
    *,
    timeout_s: float = OSRM_TIMEOUT_S + 15,
) -> dict[str, Any]:
    """Live OpenRouteService driving-hgv request returning the raw GeoJSON.

    Uses the official ``openrouteservice`` SDK (build-time ``tooling`` group),
    which handles auth and rate-limit retries. Kept separate from
    :func:`parse_ors_route` so the mapping can be unit-tested without network or
    the SDK installed. The SDK is imported lazily so the rest of this tool runs
    with the standard library alone.
    """
    try:
        import openrouteservice
    except ImportError as exc:
        raise SystemExit(
            "The OpenRouteService SDK is not installed. It is a build-time "
            "dependency: run with `uv run --group tooling ...`."
        ) from exc
    base_url = os.environ.get("ORS_BASE_URL", ORS_DEFAULT_BASE_URL)
    client = openrouteservice.Client(
        key=api_key, base_url=base_url, timeout=timeout_s, retry_over_query_limit=True
    )
    return client.directions(**_ors_directions_kwargs(start, end))


def parse_ors_route(payload: dict[str, Any]) -> dict[str, Any]:
    """Map an ORS driving-hgv GeoJSON response onto corridor-ready fields.

    Pure (no network) so it is unit-testable against a captured response.
    Returns the summary distance in miles, 2D ``[lon, lat]`` coordinates (the
    shape :func:`_sample_geometry` consumes), per-vertex elevation in feet
    (ORS returns 3D coordinates when ``elevation`` is requested, so no separate
    Open-Meteo elevation call is needed), the steepness extra-info segments, and
    whether the route touches any tollway.
    """
    features = payload.get("features") or []
    if not features:
        raise RuntimeError("ORS response has no route features")
    feature = features[0]
    coords3d = feature.get("geometry", {}).get("coordinates", [])
    if len(coords3d) < 2:
        raise RuntimeError("ORS route geometry has fewer than two points")
    coordinates = [[float(point[0]), float(point[1])] for point in coords3d]
    elevations_ft = [float(point[2]) * 3.28084 if len(point) > 2 else 0.0 for point in coords3d]
    props = feature.get("properties", {})
    distance_m = float(props.get("summary", {}).get("distance", 0.0))
    extras = props.get("extras", {})
    steepness = extras.get("steepness", {}).get("values", [])
    tollways = extras.get("tollways", {}).get("values", [])
    has_tollway = any(len(value) >= 3 and value[2] for value in tollways)
    return {
        "miles": distance_m / 1609.344,
        "coordinates": coordinates,
        "elevations_ft": elevations_ft,
        "steepness": steepness,
        "has_tollway": has_tollway,
    }


_OSRM_REF_RE = re.compile(r"([A-Za-z]{1,3})\s*-?\s*(\d+)")


def _osrm_primary_highway(
    data: dict[str, Any],
    leg: dict[str, Any],
    cache_dir: Path,
    rate_limit_s: float,
) -> str:
    """Dominant route shield for a leg, from OSRM's step ``ref`` field.

    OSRM separates the highway ref ("I 40") from the road name, so the
    longest-distance ref is reliably the through highway -- unlike ORS step
    names, which often carry only a concurrent US/state route. Interstates win
    when present, else the longest ref (so California's CA-99 legs label
    correctly too). Free and key-less; used only to *label* new legs -- the
    truck route itself still comes from ORS. Returns "" if OSRM is unavailable.
    """
    cities = data["cities"]
    start, end = cities[leg["from"]], cities[leg["to"]]
    coords = f"{start['lon']},{start['lat']};{end['lon']},{end['lat']}"
    params = {
        "overview": "false",
        "steps": "true",
        "alternatives": "false",
        "geometries": "geojson",
    }
    try:
        payload = _cached_json(
            cache_dir,
            "osrm-steps",
            f"{leg['from']}--{leg['to']}",
            OSRM_ROUTE_URL.format(coords=coords) + "?" + urllib.parse.urlencode(params),
            rate_limit_s=rate_limit_s,
        )
    except (TimeoutError, OSError, urllib.error.URLError, urllib.error.HTTPError):
        return ""
    if payload.get("code") != "Ok" or not payload.get("routes"):
        return ""
    by_ref: dict[str, float] = {}
    for route_leg in payload["routes"][0].get("legs", []):
        for step in route_leg.get("steps", []):
            dist = float(step.get("distance", 0.0))
            for part in str(step.get("ref", "") or "").split(";"):
                match = _OSRM_REF_RE.search(part)
                if match:
                    ref = f"{match.group(1).upper()}-{match.group(2)}"
                    by_ref[ref] = by_ref.get(ref, 0.0) + dist
    if not by_ref:
        return ""
    interstates = {r: d for r, d in by_ref.items() if r.startswith("I-")}
    pool = interstates or by_ref
    return max(pool, key=pool.__getitem__)


def _cached_ors_route(
    data: dict[str, Any],
    leg: dict[str, Any],
    cache_dir: Path,
    rate_limit_s: float,
    api_key: str,
) -> dict[str, Any]:
    """Parsed ORS driving-hgv route for a leg, caching the raw GeoJSON.

    Caching keeps re-runs off the rate-limited API; the committed artifact is
    still ``world.json``, and ``.route-cache/`` stays local (git-ignored).
    """
    cities = data["cities"]
    path = _cache_file(cache_dir, "ors", f"{leg['from']}--{leg['to']}--{leg['highway']}")
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = fetch_ors_hgv_route(cities[leg["from"]], cities[leg["to"]], api_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        if rate_limit_s > 0:
            time.sleep(rate_limit_s)
    return parse_ors_route(payload)


def ors_corridor_samples(
    parsed: dict[str, Any],
    leg_miles: float,
    sample_count: int = 5,
) -> tuple[list[dict[str, float]], list[float]]:
    """Evenly spaced corridor samples plus their elevation, from a parsed ORS
    route. Mirrors :func:`_sample_geometry` but carries the per-vertex elevation
    ORS returns inline, so no separate elevation request is needed.
    """
    coords = parsed["coordinates"]
    elevations = parsed["elevations_ft"]
    if len(coords) < 2:
        raise RuntimeError("ORS route geometry has fewer than two points")
    distances = [0.0]
    for prev, cur in zip(coords, coords[1:], strict=False):
        distances.append(distances[-1] + _haversine_miles(prev[1], prev[0], cur[1], cur[0]))
    total = distances[-1] or 1.0
    desired = [leg_miles * i / (sample_count - 1) for i in range(sample_count)]
    samples: list[dict[str, float]] = []
    sample_elevations: list[float] = []
    for at_mi in desired:
        target = total * at_mi / leg_miles if leg_miles else 0.0
        index = next(
            (i for i, dist in enumerate(distances) if dist >= target),
            len(distances) - 1,
        )
        lon, lat = coords[index]
        samples.append({"at_mi": at_mi, "lat": float(lat), "lon": float(lon)})
        sample_elevations.append(
            elevations[index]
            if index < len(elevations)
            else (elevations[-1] if elevations else 0.0)
        )
    samples[0]["at_mi"] = 0.0
    samples[-1]["at_mi"] = leg_miles
    return samples, sample_elevations


GRADE_BIN_MI = 0.25  # fixed real-distance width for grade-fidelity sampling


def fine_grade_samples(
    parsed: dict[str, Any],
    leg_miles: float,
    bin_width_mi: float = GRADE_BIN_MI,
) -> tuple[list[dict[str, float]], list[float]]:
    """Real elevation change over real distance traveled, in fixed-width bins.

    Feed the result to :func:`grade_segments_from_samples` for grade segments
    that actually reflect short, sharp pitches (a real mountain leg can carry
    a genuine 6-8% grade for under a mile) instead of the near-flat average
    :func:`ors_corridor_samples` gives at its default handful of samples.

    This is deliberately NOT ``ors_corridor_samples`` at a higher
    ``sample_count``: that function picks N evenly spaced *target* mileposts
    and snaps each to the nearest following vertex. Once N approaches real
    vertex density, a long straight stretch (sparser vertices) can collapse
    several targets onto the very same vertex -- a false flat run followed by
    a spurious jump once the scan reaches the next real vertex, producing
    wildly implausible grades (30%+ on real interstate terrain). Walking the
    polyline forward exactly once and closing a bin only on genuine
    accumulated distance avoids that artifact entirely. ORS already returns
    the full, undecimated elevation profile in the one directions() call, so
    this costs no extra requests.
    """
    coords = parsed["coordinates"]
    elevations = parsed["elevations_ft"]
    if len(coords) < 2:
        raise RuntimeError("ORS route geometry has fewer than two points")
    cumulative_mi = [0.0]
    for prev, cur in zip(coords, coords[1:], strict=False):
        cumulative_mi.append(cumulative_mi[-1] + _haversine_miles(prev[1], prev[0], cur[1], cur[0]))
    total = cumulative_mi[-1] or 1.0
    scale = leg_miles / total if leg_miles else 1.0

    lon0, lat0 = coords[0]
    samples: list[dict[str, float]] = [{"at_mi": 0.0, "lat": float(lat0), "lon": float(lon0)}]
    sample_elevations: list[float] = [elevations[0]]
    acc_mi = 0.0
    last = len(coords) - 1
    for i in range(1, len(coords)):
        acc_mi += cumulative_mi[i] - cumulative_mi[i - 1]
        if acc_mi >= bin_width_mi or i == last:
            lon, lat = coords[i]
            samples.append(
                {"at_mi": round(cumulative_mi[i] * scale, 3), "lat": float(lat), "lon": float(lon)}
            )
            sample_elevations.append(elevations[i])
            acc_mi = 0.0
    samples[-1]["at_mi"] = leg_miles
    return samples, sample_elevations


def _ors_sample_count(miles: float) -> int:
    """Corridor sample count for ORS legs.

    ORS returns elevation inline (no per-point Open-Meteo call), so denser
    sampling is cheap and gives real terrain. Roughly one sample per 30 miles,
    clamped so short legs still get a usable profile and long legs stay compact.
    """
    return max(5, min(25, int(miles // 30) + 2))


def _terrain_for_grade(abs_grade_pct: float) -> str:
    if abs_grade_pct > 3.0:
        return "mountain"
    if abs_grade_pct > 0.8:
        return "hills"
    return "flat"


def grade_segments_from_samples(
    samples: list[dict[str, float]],
    elevations_ft: list[float],
    leg: dict[str, Any],
) -> list[dict[str, Any]]:
    """Multiple grade segments grouping consecutive same-terrain intervals.

    Unlike the single averaged segment, this keeps real up/down structure (a
    mountain leg shows its climbs and descents instead of washing out to ~0%).
    Falls back to the single-segment builder when samples are too sparse.
    """
    if len(samples) < 3:
        return _grade_segments(samples, elevations_ft, leg)
    intervals: list[tuple[float, float, float, str]] = []
    for start, end, elev_a, elev_b in zip(
        samples, samples[1:], elevations_ft, elevations_ft[1:], strict=False
    ):
        run_mi = max(0.1, end["at_mi"] - start["at_mi"])
        grade = (elev_b - elev_a) / (run_mi * 5280.0) * 100.0
        intervals.append((start["at_mi"], end["at_mi"], grade, _terrain_for_grade(abs(grade))))
    segments: list[dict[str, Any]] = []
    seg_start, seg_end, grades, terrain = (
        intervals[0][0],
        intervals[0][1],
        [intervals[0][2]],
        intervals[0][3],
    )
    for start, end, grade, kind in intervals[1:]:
        if kind == terrain:
            seg_end = end
            grades.append(grade)
        else:
            segments.append(_grade_segment(seg_start, seg_end, grades, terrain))
            seg_start, seg_end, grades, terrain = start, end, [grade], kind
    segments.append(_grade_segment(seg_start, seg_end, grades, terrain))
    return segments


def _grade_segment(
    start_mi: float, end_mi: float, grades: list[float], terrain: str
) -> dict[str, Any]:
    return {
        "start_mi": round(start_mi, 1),
        "end_mi": round(end_mi, 1),
        "avg_grade_pct": round(sum(grades) / len(grades), 2),
        "terrain": terrain,
        "source": ORS_GRADE_SOURCE,
    }


def _ors_compare(
    data: dict[str, Any],
    from_city: str,
    to_city: str,
    api_key: str,
    cache_dir: Path,
    rate_limit_s: float,
) -> dict[str, Any]:
    """Read-only sanity check: ORS-derived corridor vs the checked-in one."""
    leg = _find_leg(data, from_city, to_city)
    if leg is None:
        raise SystemExit(f"No direct world leg {from_city} to {to_city}")
    parsed = _cached_ors_route(data, leg, cache_dir, rate_limit_s, api_key)
    miles = float(leg["miles"])
    samples, elevations = ors_corridor_samples(parsed, miles)
    ors_grade = _grade_segments(samples, elevations, leg)[0]
    corridor = leg.get("corridor", {})
    current_grades = corridor.get("grade_segments") or [{}]
    return {
        "leg_miles": miles,
        "ors_miles": parsed["miles"],
        "ors_points": len(parsed["coordinates"]),
        "ors_min_ft": min(elevations) if elevations else 0.0,
        "ors_max_ft": max(elevations) if elevations else 0.0,
        "ors_avg_grade_pct": ors_grade["avg_grade_pct"],
        "ors_terrain": ors_grade["terrain"],
        "current_terrain": current_grades[0].get("terrain", leg.get("terrain")),
        "current_avg_grade_pct": current_grades[0].get("avg_grade_pct"),
        "ors_has_tollway": parsed["has_tollway"],
        "current_toll_events": len(corridor.get("toll_events", ())),
    }


def _ors_smoke(
    data: dict[str, Any],
    from_city: str,
    to_city: str,
    api_key: str,
) -> dict[str, Any]:
    cities = data["cities"]
    payload = fetch_ors_hgv_route(cities[from_city], cities[to_city], api_key)
    parsed = parse_ors_route(payload)
    elevations = parsed["elevations_ft"]
    return {
        "miles": parsed["miles"],
        "points": len(parsed["coordinates"]),
        "min_ft": min(elevations) if elevations else 0.0,
        "max_ft": max(elevations) if elevations else 0.0,
        "steepness_segments": len(parsed["steepness"]),
        "has_tollway": parsed["has_tollway"],
    }


def _open_meteo_elevation_smoke(corridor: dict[str, Any]) -> dict[str, Any]:
    points = corridor.get("route_points", [])
    if not points:
        raise SystemExit("No route_points available for elevation smoke.")
    # Use a tiny subset: endpoints and one middle point if available.
    selected = [points[0]]
    if len(points) > 2:
        selected.append(points[len(points) // 2])
    if len(points) > 1:
        selected.append(points[-1])
    params = urllib.parse.urlencode(
        {
            "latitude": ",".join(str(point["lat"]) for point in selected),
            "longitude": ",".join(str(point["lon"]) for point in selected),
        }
    )
    req = urllib.request.Request(
        OPEN_METEO_ELEVATION_URL + "?" + params,
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    elevations_m = payload["elevation"]
    elevations_ft = [float(value) * 3.28084 for value in elevations_m]
    return {
        "samples": len(elevations_ft),
        "min_ft": min(elevations_ft),
        "max_ft": max(elevations_ft),
    }


def _overpass_poi_smoke(corridor: dict[str, Any]) -> dict[str, Any]:
    points = corridor.get("route_points", [])
    if not points:
        raise SystemExit("No route_points available for Overpass smoke.")
    lats = [float(point["lat"]) for point in points]
    lons = [float(point["lon"]) for point in points]
    south, north = min(lats) - 0.05, max(lats) + 0.05
    west, east = min(lons) - 0.05, max(lons) + 0.05
    query = f"""
    [out:json][timeout:12];
    (
      node["amenity"~"fuel|parking|restaurant"]({south},{west},{north},{east});
      node["highway"="rest_area"]({south},{west},{north},{east});
      node["highway"="services"]({south},{west},{north},{east});
    );
    out tags center 20;
    """
    payload = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_URL,
        data=payload,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S + 8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elements = data.get("elements", [])
    actionable = [
        element
        for element in elements
        if any(key in element.get("tags", {}) for key in ("amenity", "highway"))
    ]
    return {"elements": len(elements), "actionable_candidates": len(actionable)}


if __name__ == "__main__":
    sys.exit(main())

__all__ = [name for name in globals() if not name.startswith("__")]
