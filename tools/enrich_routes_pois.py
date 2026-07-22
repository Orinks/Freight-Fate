# ruff: noqa: F401,F403,F405,F821,I001
from __future__ import annotations

from enrich_routes_base import *


_TRUCK_POI_KEYWORDS = (
    "love's",
    "loves travel",
    "pilot",
    "flying j",
    "ta travel",
    "travelcenters",
    "petro stopping",
    "ta petro",
    "road ranger",
    "ambest",
    "sapp bros",
    "kwik trip",
    "kwik star",
    "one9",
    "roady",
    "mr. fuel",
    "busy bee",
    "travel center",
    "travel plaza",
    "travel stop",
    "truck stop",
    "truckstop",
    "service plaza",
    "truck plaza",
)
# Warehouse-club / grocery fuel: real OSM amenity=fuel points, but not truck
# stops (members-only pumps, no big-rig access -- Buc-ee's famously bans trucks).
_RETAIL_FUEL_KEYWORDS = (
    "sam's club",
    "sams club",
    "costco",
    "bj's",
    "walmart",
    "kroger",
    "meijer",
    "safeway",
    "albertsons",
    "h-e-b",
    "heb ",
    "buc-ee",
    "bucee",
    "wegmans",
    "publix",
    "giant eagle",
    "fred meyer",
    "king soopers",
    "stop & shop",
    "stop and shop",
    "woodman",
)
# Names that are not a place a driver stops for fuel/rest -- OSM mistags or
# mandatory-only facilities that shouldn't surface as a chooseable stop.
_NON_STOP_KEYWORDS = ("cleaning service", "weigh station", "inspection station")
_RETAIL_SHOP_TAGS = {"supermarket", "wholesale", "department_store", "convenience"}


def _truck_relevance(tags: dict[str, str], name: str, rural_fallback: bool = False) -> int | None:
    """Rank a candidate POI for a freight game; ``None`` means drop it.

    Truck-relevant only: service plazas, rest areas, HGV-tagged or HGV-diesel
    fuel, dedicated truck parking, and named truck-stop brands. A plain
    ``amenity=fuel`` car station with no truck signal is dropped -- a Class-8
    driver does not pull a 70-foot rig into a corner Shell. Warehouse/grocery
    retail and OSM mistags are rejected too.

    ``rural_fallback`` relaxes only the last rule: on a leg that would otherwise
    carry no stop at all, a named fuel station not explicitly diesel-free is
    accepted at the lowest score (1) as a splash-and-dash diesel point, so a real
    truck stop always outranks it and it types as a plain ``fuel_station``.
    """
    low = name.lower()
    if len(low.strip()) < 2:
        return None  # meaningless single-char names ("B")
    if any(word in low for word in _RETAIL_FUEL_KEYWORDS):
        return None
    if any(word in low for word in _NON_STOP_KEYWORDS):
        return None
    if tags.get("shop", "") in _RETAIL_SHOP_TAGS:
        return None
    amenity = tags.get("amenity", "")
    highway = tags.get("highway", "")
    hgv = tags.get("hgv", "") in {"yes", "designated"}
    hgv_diesel = tags.get("fuel:HGV_diesel", "") in {"yes", "designated"}
    is_brand = any(word in low for word in _TRUCK_POI_KEYWORDS)
    truck_signal = (
        highway in {"services", "rest_area"}
        or hgv
        or hgv_diesel
        or is_brand
        or amenity == "parking"
    )
    if not truck_signal:
        if rural_fallback and amenity == "fuel" and tags.get("fuel:diesel", "") != "no":
            return 1  # rural splash-and-dash diesel; any real truck stop outranks it
        return None  # generic car fuel -- not a truck stop
    score = 0
    if highway == "services":
        score += 10
    if highway == "rest_area":
        score += 8
    if hgv or hgv_diesel:
        score += 8
    if is_brand:
        score += 10
    if amenity == "fuel":
        score += 3
    if amenity == "parking":
        score += 1
    return score


def add_overpass_pois(
    data: dict[str, Any],
    *,
    cache_dir: Path,
    rate_limit_s: float,
    only: set[tuple[str, str]],
    per_leg: int = 2,
    rural_fallback: bool = False,
) -> dict[str, Any]:
    """Additively enrich legs with named OSM truck POIs of any brand.

    Purely additive (POIs do not gate dispatch): adds up to ``per_leg`` new
    named corridor stops per leg, deduped against existing Love's/Pilot
    curation. Robust to Overpass hiccups -- a leg that errors or finds nothing
    is simply skipped, and the cache makes re-runs resumable.

    Endpoint-city finds ride on top of the ``per_leg`` corridor budget: a
    physical truck stop at a city serves every leg touching that city (a
    driver on any of them really does pass it), so each such leg gets it at
    its own end -- and a long sparse leg still keeps its corridor slots for
    mid-route coverage. The minimum-spacing rule caps discovery at one stop
    per leg end per run.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    added = updated = 0
    still_empty: list[str] = []
    for leg in data["legs"]:
        key = (leg["from"], leg["to"])
        if only and key not in only and (leg["to"], leg["from"]) not in only:
            continue
        points = leg.get("corridor", {}).get("route_points", [])
        if len(points) < 2:
            continue
        stops = leg.setdefault("stops", [])
        existing = {str(s.get("name", "")).lower() for s in stops}
        taken_mi = [float(s["at_mi"]) for s in stops]
        cands = _overpass_named_candidates(
            leg,
            points,
            cache_dir,
            rate_limit_s,
            per_leg + len(existing) + 6,
            rural_fallback=rural_fallback,
        )
        fresh = []
        corridor_added = 0
        for cand in cands:
            if cand["name"].lower() in existing:
                continue
            at = float(cand["at_mi"])
            # Keep stops visibly apart on the corridor: a cluster of POIs found
            # near one sample point would otherwise land on nearly the same
            # mile. This also limits each endpoint city to one stop per run.
            if any(abs(at - t) < MIN_STOP_SPACING_MI for t in taken_mi):
                continue
            if cand["source"] == OVERPASS_POI_SOURCE:  # mid-corridor find
                if corridor_added >= per_leg:
                    continue
                corridor_added += 1
            fresh.append(cand)
            existing.add(cand["name"].lower())
            taken_mi.append(at)
        if fresh:
            leg["stops"] = sorted(stops + fresh, key=lambda s: float(s["at_mi"]))
            _spread_stop_positions(leg["stops"], leg["miles"])
            added += len(fresh)
            updated += 1
        elif not stops:
            still_empty.append(f"{leg['from']}-{leg['to']}")
    return {
        "added_pois": added,
        "updated_legs": updated,
        "legs_without_any_poi": still_empty,
        "coverage_totals": coverage_report(data)["totals"],
    }


MAXSPEED_SOURCE = (
    "OpenStreetMap maxspeed tags on the corridor highway ways (Overpass), "
    "development-time, normalized to mph; maxspeed:hgv preferred where tagged."
)
KMH_TO_MPH = 0.621371
# OSM `maxspeed` values that carry no numeric posted limit -- leave the leg to
# the runtime heuristic rather than inventing a number.
_MAXSPEED_NON_NUMERIC = {"none", "signals", "walk", "variable", "no", "unknown"}
_MAXSPEED_NUMBER = re.compile(r"(\d+(?:\.\d+)?)")
# Mainline corridor way classes worth a posted limit; service/link roads ignored.
_MAXSPEED_HIGHWAY_CLASSES = ("motorway", "trunk", "primary", "secondary")


def parse_osm_maxspeed(raw: Any, *, default_kmh: bool = False) -> float | None:
    """Normalize a raw OSM ``maxspeed`` value to mph, or ``None`` if unusable.

    Handles the common shapes: ``"55 mph"``, a bare ``"55"`` (assumed mph for the
    US map unless ``default_kmh``, matching OSM's km/h default for non-US data),
    metric ``"90 km/h"``/``"100 kmh"``, the ``"none"``/``"signals"`` non-values,
    and lists like ``"55 mph; 50 mph"`` (the first parseable token wins, i.e. the
    general limit before conditional ones). Results are rounded to the nearest
    5 mph and clamped to a sane truck range; anything unparseable returns
    ``None`` so the caller can fall back to the heuristic."""
    if raw is None:
        return None
    for token in re.split(r"[;,]", str(raw)):
        token = token.strip().lower()
        if not token or token in _MAXSPEED_NON_NUMERIC:
            continue
        if "knots" in token:
            continue
        match = _MAXSPEED_NUMBER.search(token)
        if not match:
            continue
        value = float(match.group(1))
        if "mph" in token:
            mph = value
        elif any(unit in token for unit in ("km/h", "kmh", "kph")):
            mph = value * KMH_TO_MPH
        else:
            mph = value * KMH_TO_MPH if default_kmh else value
        mph = round(mph / 5.0) * 5.0
        if mph < 5.0:
            continue
        return min(85.0, mph)
    return None


def _maxspeed_from_tags(tags: dict[str, str]) -> tuple[float, bool] | None:
    """Posted mph for a highway way, preferring the truck-specific tag.

    Returns ``(mph, is_hgv)`` or ``None`` when the way has no usable maxspeed."""
    hgv_mph = parse_osm_maxspeed(tags.get("maxspeed:hgv"))
    if hgv_mph is not None:
        return hgv_mph, True
    mph = parse_osm_maxspeed(tags.get("maxspeed"))
    if mph is not None:
        return mph, False
    return None


def _maxspeed_at_point(
    leg: dict[str, Any],
    point: dict[str, float],
    cache_dir: Path,
    rate_limit_s: float,
) -> tuple[float, bool] | None:
    """Best posted limit on the corridor's highway near one route point.

    Queries OSM ways carrying a ``maxspeed`` within a short radius and prefers
    the way whose ``ref`` matches the leg's highway shield (e.g. ``I 95``), so a
    parallel frontage road's 45 mph doesn't override the interstate."""
    box = _bbox(point["lat"], point["lon"], 400)
    classes = "|".join(_MAXSPEED_HIGHWAY_CLASSES)
    query = f"""
    [out:json][timeout:40];
    way["highway"~"{classes}"]["maxspeed"]({box});
    out tags 40;
    """
    try:
        payload = _cached_overpass_json(
            cache_dir,
            f"maxspeed--{leg['from']}--{leg['to']}--{point['at_mi']:.1f}",
            urllib.parse.urlencode({"data": query}).encode("utf-8"),
            rate_limit_s=rate_limit_s,
        )
    except (TimeoutError, OSError, urllib.error.URLError, urllib.error.HTTPError, RuntimeError):
        return None
    shield = _highway_digits(str(leg.get("highway", "")))
    best: tuple[float, bool] | None = None
    best_on_shield = False
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        parsed = _maxspeed_from_tags(tags)
        if parsed is None:
            continue
        mph, is_hgv = parsed
        on_shield = bool(shield) and _highway_digits(tags.get("ref", "")) == shield
        # A way matching the leg's shield always wins; otherwise keep the highest
        # posted limit found (the mainline, not a ramp or frontage road).
        if on_shield and not best_on_shield:
            best, best_on_shield = (mph, is_hgv), True
        elif on_shield == best_on_shield and (best is None or mph > best[0]):
            best = (mph, is_hgv)
    return best


def _highway_digits(highway: str) -> str:
    """The route number from a shield/ref, e.g. ``I-95`` or ``I 95`` -> ``95``."""
    digits = re.findall(r"\d+", str(highway))
    return digits[0] if digits else ""


def bake_maxspeed(
    data: dict[str, Any],
    *,
    cache_dir: Path,
    rate_limit_s: float,
    only: set[tuple[str, str]],
) -> dict[str, Any]:
    """Bake a real OSM ``maxspeed`` profile onto each leg from its route points.

    Additive and idempotent: samples the posted limit at each checked-in route
    point, collapses consecutive equal values into a step function, and stores it
    as ``corridor.speed_limits`` (mph, already normalized). Legs where OSM has no
    maxspeed on the corridor are left without a profile, so the runtime keeps
    using the highway/region heuristic for them."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    baked: list[dict[str, Any]] = []
    skipped: list[str] = []
    for leg in data["legs"]:
        key = (leg["from"], leg["to"])
        if only and key not in only and (leg["to"], leg["from"]) not in only:
            continue
        points = leg.get("corridor", {}).get("route_points", [])
        if len(points) < 2:
            skipped.append(f"{leg['from']}-{leg['to']}")
            continue
        samples: list[dict[str, Any]] = []
        for point in points:
            result = _maxspeed_at_point(leg, point, cache_dir, rate_limit_s)
            if result is None:
                continue
            mph, is_hgv = result
            at_mi = round(float(point["at_mi"]), 1)
            # Collapse a repeated limit into the step function it represents.
            if samples and samples[-1]["mph"] == mph and samples[-1]["hgv"] == is_hgv:
                continue
            samples.append({"at_mi": at_mi, "mph": mph, "source": MAXSPEED_SOURCE, "hgv": is_hgv})
        if samples:
            leg.setdefault("corridor", {})["speed_limits"] = samples
            baked.append({"from": leg["from"], "to": leg["to"], "samples": len(samples)})
        else:
            skipped.append(f"{leg['from']}-{leg['to']}")
    return {
        "baked_legs": baked,
        "legs_without_maxspeed": skipped,
        "coverage_totals": coverage_report(data)["totals"],
    }


_TRUCK_STOP_TYPES = {
    "travel_center",
    "truck_stop",
    "service_plaza",
    "public_rest_area",
    "truck_parking",
}


def _stop_is_truck_relevant(stop: dict[str, Any]) -> bool:
    """Whether a stored stop is somewhere a Class-8 driver actually stops.

    Raw OSM tags are not retained on the stored stop, so this judges by the
    stored type and name: keep service plazas, rest areas, truck parking,
    travel/truck centers, and named truck-stop brands; a plain ``fuel_station``
    (generic car gas) is not truck-relevant.
    """
    if str(stop.get("type", "")) in _TRUCK_STOP_TYPES:
        return True
    low = str(stop.get("name", "")).lower()
    return any(word in low for word in _TRUCK_POI_KEYWORDS)


def prune_non_truck_pois(data: dict[str, Any]) -> dict[str, Any]:
    """Strip auto-discovered non-truck POIs (generic car fuel) network-wide.

    Only Overpass-discovered stops are filtered; curated (hand-verified) stops
    are always kept. Purely subtractive -- POIs are advisory and dispatch gates
    on routing metadata, so a leg left stop-less stays playable.
    """
    removed = legs_emptied = 0
    for leg in data["legs"]:
        stops = leg.get("stops", [])
        if not stops:
            continue
        kept = []
        for stop in stops:
            src = str(stop.get("source", ""))
            is_overpass = "Overpass" in src and "amenity query" in src
            if is_overpass and not _stop_is_truck_relevant(stop):
                removed += 1
                continue
            kept.append(stop)
        if len(kept) != len(stops):
            leg["stops"] = kept
            if not kept:
                legs_emptied += 1
    return {
        "removed_pois": removed,
        "legs_emptied": legs_emptied,
        "coverage_totals": coverage_report(data)["totals"],
    }


def _stop_type_from_tags(tags: dict[str, str]) -> str:
    amenity = tags.get("amenity", "")
    highway = tags.get("highway", "")
    name = (tags.get("name") or tags.get("brand") or "").lower()
    if highway == "services":
        return "service_plaza"
    if highway == "rest_area":
        return "public_rest_area"
    if amenity == "parking":
        return "truck_parking"
    if "truck" in name or "travel" in name:
        return "travel_center"
    if amenity == "fuel" and (
        tags.get("hgv", "") in {"yes", "designated"}
        or tags.get("fuel:HGV_diesel", "") in {"yes", "designated"}
    ):
        return "travel_center"  # truck-capable fuel; keep it truck-typed
    if amenity == "fuel":
        return "fuel_station"
    return "travel_center"


def _services_for_stop_type(stop_type: str) -> list[str]:
    return {
        "truck_stop": ["diesel", "food", "parking"],
        "travel_center": ["diesel", "food", "parking"],
        "fuel_station": ["diesel", "parking"],
        "service_plaza": ["diesel", "food", "parking"],
        "public_rest_area": ["parking", "restrooms"],
        "truck_parking": ["parking"],
        "weigh_station": ["inspection"],
        "repair_shop": ["repair", "parking"],
    }[stop_type]


def _actions_for_stop_type(stop_type: str) -> list[str]:
    return {
        "truck_stop": ["park", "save", "fuel", "food", "break", "sleep"],
        "travel_center": ["park", "save", "fuel", "food", "break", "sleep"],
        "fuel_station": ["park", "save", "fuel", "break"],
        "service_plaza": ["park", "save", "fuel", "food", "break", "sleep"],
        "public_rest_area": ["park", "save", "break", "sleep"],
        "truck_parking": ["park", "save", "break", "sleep"],
        "weigh_station": ["inspect"],
        "repair_shop": ["park", "save", "repair"],
    }[stop_type]


# Minimum spacing between a newly-added POI and any existing stop. Several real
# truck stops often cluster at one interchange; surfacing them on near-identical
# miles reads as a "two stops on the same mile" bug while driving, so pick stops
# that are genuinely spread along the corridor instead.
MIN_STOP_SPACING_MI = 10.0


def _nearest_free_mile(
    target: float,
    taken: list[float],
    min_gap: float,
    lo: float,
    hi: float,
) -> float:
    """Closest mile to ``target`` that is >= ``min_gap`` from every taken mile."""

    def is_free(mile: float) -> bool:
        return all(abs(mile - t) >= min_gap - 1e-9 for t in taken)

    target = round(min(hi, max(lo, target)), 1)
    if is_free(target):
        return target
    step = 0.5
    for k in range(1, int((hi - lo) / step) + 2):
        for cand in (round(target + k * step, 1), round(target - k * step, 1)):
            if lo <= cand <= hi and is_free(cand):
                return cand
    return target


def _spread_stop_positions(
    stops: list[dict[str, Any]],
    leg_miles: float,
    *,
    min_gap: float = 1.0,
) -> list[dict[str, Any]]:
    """Give every stop its own truck-mile marker.

    Discovered POIs inherit their corridor sample point's mileage, so several
    can land on the same mile (and on top of a curated stop). Curated stops keep
    their authoritative positions; each discovered stop is nudged to the nearest
    free mile at least ``min_gap`` apart, staying within the leg."""
    lo, hi = 1.0, max(1.0, round(float(leg_miles) - 1.0, 1))
    taken = [round(float(s["at_mi"]), 1) for s in stops if s.get("source") != OVERPASS_POI_SOURCE]
    movable = sorted(
        (s for s in stops if s.get("source") == OVERPASS_POI_SOURCE),
        key=lambda s: float(s["at_mi"]),
    )
    for stop in movable:
        at = _nearest_free_mile(float(stop["at_mi"]), taken, min_gap, lo, hi)
        stop["at_mi"] = at
        taken.append(at)
    stops.sort(key=lambda s: float(s["at_mi"]))
    return stops


def _parking_for_stop_type(stop_type: str) -> str:
    """Explicit truck-parking availability for a discovered POI.

    The coverage contract treats ``parking == "unknown"`` as incomplete, so a
    discovered stop must declare a concrete value. Big travel centers and
    service plazas reliably have it; rest areas and dedicated truck lots have
    some; a generic fuel station offers a pull-in at best, not overnight."""
    if stop_type in {"truck_stop", "travel_center", "service_plaza"}:
        return "likely"
    return "limited"


def _clean_poi_name(value: str) -> str:
    name = " ".join(str(value).replace("\n", " ").split()).strip()
    lowered = name.lower()
    raw_markers = ("osm", "amenity=", "highway=", "node/", "way/", "relation/")
    if any(marker in lowered for marker in raw_markers):
        return ""
    return name[:80]


def _sample_geometry(
    geometry: list[list[float]],
    leg_miles: float,
    sample_count: int = 5,
) -> list[dict[str, float]]:
    if len(geometry) < 2:
        raise RuntimeError("OSRM route geometry has fewer than two points")
    distances = [0.0]
    for prev, cur in zip(geometry, geometry[1:], strict=False):
        distances.append(distances[-1] + _haversine_miles(prev[1], prev[0], cur[1], cur[0]))
    total = distances[-1] or 1.0
    desired = [leg_miles * i / (sample_count - 1) for i in range(sample_count)]
    samples = []
    for at_mi in desired:
        target = total * at_mi / leg_miles if leg_miles else 0.0
        index = next(
            (i for i, dist in enumerate(distances) if dist >= target),
            len(distances) - 1,
        )
        lon, lat = geometry[index]
        samples.append({"at_mi": at_mi, "lat": float(lat), "lon": float(lon)})
    samples[0]["at_mi"] = 0.0
    samples[-1]["at_mi"] = leg_miles
    return samples


def _grade_segments(
    samples: list[dict[str, float]],
    elevations_ft: list[float],
    leg: dict[str, Any],
) -> list[dict[str, Any]]:
    grades = []
    for start, end, elev_start, elev_end in zip(
        samples, samples[1:], elevations_ft, elevations_ft[1:], strict=False
    ):
        miles = max(0.1, end["at_mi"] - start["at_mi"])
        grade = (elev_end - elev_start) / (miles * 5280.0) * 100.0
        grades.append(grade)
    avg = sum(grades) / len(grades)
    max_abs = max(abs(grade) for grade in grades)
    terrain = str(leg.get("terrain", "flat"))
    if max_abs > 3.0:
        terrain = "mountain"
    elif max_abs > 0.8 and terrain == "flat":
        terrain = "hills"
    return [
        {
            "start_mi": 0.0,
            "end_mi": float(leg["miles"]),
            "avg_grade_pct": round(avg, 2),
            "terrain": terrain,
            "source": "Open-Meteo elevation samples summarized for corridor terrain.",
        }
    ]


def _checkpoints(
    data: dict[str, Any],
    leg: dict[str, Any],
    samples: list[dict[str, float]],
) -> list[dict[str, Any]]:
    """One fallback checkpoint at the leg midpoint, pending real curation.

    Checkpoint ``name`` and ``state`` are read aloud verbatim by the trip
    narrator ("Passing <name>, <state> on <highway>"), so both must be spoken
    text: composed spoken city names (never slug keys) and the full spoken
    state name (never a 2-letter code a screen reader would spell out).
    """
    cities = data["cities"]
    spoken_from = str(cities[leg["from"]].get("spoken_city") or leg["from"])
    spoken_to = str(cities[leg["to"]].get("spoken_city") or leg["to"])
    mid = samples[len(samples) // 2]
    return [
        {
            "name": f"{leg['highway']} corridor between {spoken_from} and {spoken_to}",
            "at_mi": round(max(1.0, min(float(leg["miles"]) - 1.0, mid["at_mi"])), 1),
            "type": "place",
            "state": spoken_state(data, cities[leg["to"]]["state"]),
            "highway": leg["highway"],
            "source": "Curated OSRM/OpenStreetMap corridor checkpoint.",
        }
    ]


__all__ = [name for name in globals() if not name.startswith("__")]
