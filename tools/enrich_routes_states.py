# ruff: noqa: F401,F403,F405,F821,I001
from __future__ import annotations

from enrich_routes_base import *


STATE_CONTEXT_SOURCE = (
    "Computed from OSRM route geometry and public U.S. state boundary GeoJSON."
)

# Highways that run alongside a river border -- I-84 hugging the Oregon bank of
# the Columbia is the worst offender -- make per-vertex point-in-polygon sampling
# flicker across the simplified boundary line, fabricating a string of crossings
# the driver never actually makes. Collapse any *round trip* (a dip into a
# neighbor state that returns to the state it came from) that is short in both
# absolute and relative terms back into the surrounding state. Genuine
# pass-throughs (state A -> B -> C) are never touched, and any excursion long
# enough to clear the fraction gate survives for human review.
STATE_CROSSING_MIN_DWELL_MI = 15.0
STATE_CROSSING_MIN_DWELL_FRACTION = 0.10


def coalesce_short_states(
    sequence: list[dict[str, Any]],
    leg_miles: float,
    min_dwell_mi: float = STATE_CROSSING_MIN_DWELL_MI,
    min_dwell_fraction: float = STATE_CROSSING_MIN_DWELL_FRACTION,
) -> list[dict[str, Any]]:
    """Drop short round-trip state excursions from a state sequence.

    ``sequence`` is the ordered list of ``{"state", "at_mi"}`` boundaries that
    begins at mile 0; the final segment runs to ``leg_miles``. A segment whose
    two neighbors are the *same* state and that is shorter than both
    ``min_dwell_mi`` miles and ``min_dwell_fraction`` of the leg is boundary
    noise and gets merged away. The first and last segments are always kept so a
    leg's endpoint states survive.
    """
    if len(sequence) <= 2:
        return sequence
    threshold = max(min_dwell_mi, leg_miles * min_dwell_fraction)
    segments: list[list[Any]] = []
    for i, item in enumerate(sequence):
        start = item["at_mi"]
        end = sequence[i + 1]["at_mi"] if i + 1 < len(sequence) else leg_miles
        segments.append([item["state"], start, end])
    while len(segments) > 2:
        excursions = [
            i
            for i in range(1, len(segments) - 1)
            if segments[i - 1][0] == segments[i + 1][0]
            and (segments[i][2] - segments[i][1]) < threshold
        ]
        if not excursions:
            break
        i = min(excursions, key=lambda k: segments[k][2] - segments[k][1])
        del segments[i]
        coalesced = [segments[0]]
        for seg in segments[1:]:
            if seg[0] == coalesced[-1][0]:
                coalesced[-1][2] = seg[2]
            else:
                coalesced.append(seg)
        segments = coalesced
    return [{"state": seg[0], "at_mi": seg[1]} for seg in segments]


def crossings_from_sequence(
    sequence: list[dict[str, Any]],
    leg_miles: float,
    highway: str,
) -> list[dict[str, Any]]:
    """Turn an ordered state sequence into state-crossing records."""
    crossings: list[dict[str, Any]] = []
    for prev, cur in zip(sequence, sequence[1:], strict=False):
        if prev["state"] == cur["state"]:
            continue
        crossings.append({
            "at_mi": round(max(0.1, min(leg_miles - 0.1, cur["at_mi"])), 1),
            "from_state": prev["state"],
            "state": cur["state"],
            "place": f"{prev['state']}-{cur['state']} line on {highway}",
            "source": STATE_CONTEXT_SOURCE,
        })
    return crossings


def state_miles_from_sequence(
    sequence: list[dict[str, Any]],
    leg_miles: float,
    endpoint_states: tuple[str, str],
) -> list[dict[str, Any]]:
    """Sum per-state mileage from an ordered state sequence."""
    mileage: dict[str, float] = {}
    bounds = sequence + [{"state": sequence[-1]["state"], "at_mi": leg_miles}]
    for prev, cur in zip(bounds, bounds[1:], strict=False):
        miles = max(0.0, cur["at_mi"] - prev["at_mi"])
        mileage[prev["state"]] = mileage.get(prev["state"], 0.0) + miles
    if not mileage:
        mileage[endpoint_states[0]] = leg_miles
    state_miles = [
        {"state": state, "miles": round(miles, 1)}
        for state, miles in mileage.items()
        if miles > 0
    ]
    total = sum(item["miles"] for item in state_miles)
    if state_miles and abs(total - leg_miles) >= 0.1:
        state_miles[-1]["miles"] = round(
            state_miles[-1]["miles"] + leg_miles - total, 1
        )
    return state_miles


def _state_context(
    data: dict[str, Any],
    leg: dict[str, Any],
    geometry: list[list[float]],
    state_shapes: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    leg_miles = float(leg["miles"])
    endpoint_states = (data["cities"][leg["from"]]["state"],
                       data["cities"][leg["to"]]["state"])
    points = _state_points(geometry, leg_miles, state_shapes)
    if not points:
        points = [
            {"at_mi": 0.0, "state": endpoint_states[0]},
            {"at_mi": leg_miles, "state": endpoint_states[1]},
        ]
    points[0]["state"] = points[0].get("state") or endpoint_states[0]
    points[-1]["state"] = points[-1].get("state") or endpoint_states[1]
    sequence: list[dict[str, Any]] = []
    for point in points:
        state = point.get("state")
        if not state:
            continue
        if not sequence or sequence[-1]["state"] != state:
            sequence.append({"state": state, "at_mi": point["at_mi"]})
    if not sequence:
        sequence = [{"state": endpoint_states[0], "at_mi": 0.0}]
    if sequence[0]["at_mi"] != 0.0:
        sequence.insert(0, {"state": sequence[0]["state"], "at_mi": 0.0})
    if sequence[-1]["state"] != endpoint_states[1]:
        sequence.append({"state": endpoint_states[1], "at_mi": leg_miles})
    sequence = coalesce_short_states(sequence, leg_miles)
    crossings = crossings_from_sequence(sequence, leg_miles, leg["highway"])
    state_miles = state_miles_from_sequence(sequence, leg_miles, endpoint_states)
    return {"state_miles": state_miles, "state_crossings": crossings}


def _state_points(
    geometry: list[list[float]],
    leg_miles: float,
    state_shapes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    distances = [0.0]
    for prev, cur in zip(geometry, geometry[1:], strict=False):
        distances.append(distances[-1] + _haversine_miles(prev[1], prev[0], cur[1], cur[0]))
    total = distances[-1] or 1.0
    out = []
    for coord, raw_miles in zip(geometry, distances, strict=True):
        lon, lat = coord
        state = _state_for_point(float(lat), float(lon), state_shapes)
        out.append({"at_mi": raw_miles / total * leg_miles, "state": state})
    return out


def _load_state_shapes(cache_dir: Path, rate_limit_s: float) -> list[dict[str, Any]]:
    payload = _cached_json(
        cache_dir,
        "boundaries",
        "us-states-publicamundi",
        SIMPLE_STATES_GEOJSON_URL,
        rate_limit_s=rate_limit_s,
    )
    return payload.get("features", [])


def _state_for_point(lat: float, lon: float, features: list[dict[str, Any]]) -> str:
    for feature in features:
        geometry = feature.get("geometry", {})
        if _point_in_geometry(lat, lon, geometry):
            return str(feature.get("properties", {}).get("name", ""))
    return ""


def _point_in_geometry(lat: float, lon: float, geometry: dict[str, Any]) -> bool:
    geom_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])
    if geom_type == "Polygon":
        return any(_point_in_ring(lat, lon, ring) for ring in coordinates[:1])
    if geom_type == "MultiPolygon":
        return any(
            any(_point_in_ring(lat, lon, ring) for ring in polygon[:1])
            for polygon in coordinates
        )
    return False


def _point_in_ring(lat: float, lon: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i, point in enumerate(ring):
        xi, yi = point[0], point[1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _cached_json(
    cache_dir: Path,
    namespace: str,
    key: str,
    url: str,
    *,
    rate_limit_s: float,
) -> dict[str, Any]:
    path = _cache_file(cache_dir, namespace, key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S + 20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if rate_limit_s > 0:
        time.sleep(rate_limit_s)
    return payload


def _cached_post_json(
    cache_dir: Path,
    namespace: str,
    key: str,
    url: str,
    body: bytes,
    *,
    rate_limit_s: float,
) -> dict[str, Any]:
    path = _cache_file(cache_dir, namespace, key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S + 25) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if rate_limit_s > 0:
        time.sleep(rate_limit_s)
    return payload


def _overpass_is_error(payload: dict[str, Any]) -> bool:
    """True if an Overpass HTTP-200 body is actually a server-side failure.

    Overpass reports query timeouts and rate limits as a 200 response carrying
    an empty ``elements`` list plus a ``remark`` -- so a naive cache treats the
    failure as a valid "nothing here" answer. A genuinely empty area returns no
    ``remark``, so only remark-bearing bodies are failures.
    """
    remark = str(payload.get("remark", "")).lower()
    return any(
        token in remark
        for token in ("runtime error", "timed out", "rate_limited", "too many")
    )


def _cached_overpass_json(
    cache_dir: Path,
    key: str,
    body: bytes,
    *,
    rate_limit_s: float,
) -> dict[str, Any]:
    path = _cache_file(cache_dir, "overpass", key)
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if not _overpass_is_error(cached):
            return cached
        path.unlink()  # drop a stale failure so this run can retry it
    last_error: Exception | None = None
    for url in OVERPASS_URLS:
        per_url = _cache_file(cache_dir, "overpass", f"{key}--{_hash_key(url)}")
        try:
            payload = _cached_post_json(
                cache_dir,
                "overpass",
                f"{key}--{_hash_key(url)}",
                url,
                body,
                rate_limit_s=rate_limit_s,
            )
        except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
            last_error = exc
            per_url.unlink(missing_ok=True)
            continue
        if _overpass_is_error(payload):
            # Server aborted (timeout / rate limit). Don't cache the failure;
            # try the next endpoint instead.
            last_error = RuntimeError(
                f"Overpass error from {url}: {payload.get('remark', '').strip()}")
            per_url.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True),
                        encoding="utf-8")
        return payload
    if last_error is not None:
        raise last_error
    raise RuntimeError("No Overpass endpoint configured")


def _cache_file(cache_dir: Path, namespace: str, key: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in key)
    return cache_dir / namespace / f"{safe[:120]}.json"


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_mi = 3958.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_mi * math.atan2(a ** 0.5, (1 - a) ** 0.5)


def _find_leg(data: dict[str, Any], from_city: str, to_city: str) -> dict[str, Any] | None:
    for leg in data["legs"]:
        if leg["from"] == from_city and leg["to"] == to_city:
            return leg
    return None


def _offline_summary(leg: dict[str, Any], corridor: dict[str, Any]) -> str:
    crossings = corridor.get("state_crossings", [])
    points = corridor.get("route_points", [])
    checkpoints = corridor.get("checkpoints", [])
    elevations = corridor.get("elevation_samples", [])
    grade_segments = corridor.get("grade_segments", [])
    state_text = ", ".join(
        f"{item['from_state']} to {item['state']} at {item['at_mi']} mi"
        for item in crossings
    ) or "no explicit state crossings"
    terrain_text = (
        f"{len(elevations)} elevation samples, {len(grade_segments)} grade segments"
        if elevations or grade_segments else "no route-derived terrain"
    )
    return (
        f"Offline corridor {leg['from']} to {leg['to']}: "
        f"{leg['miles']} miles via {leg['highway']}; "
        f"{len(points)} route points, {len(checkpoints)} checkpoints, "
        f"{terrain_text}, {state_text}."
    )


__all__ = [name for name in globals() if not name.startswith("__")]
