# ruff: noqa: F401,F403,F405,F821,I001
from __future__ import annotations

from enrich_routes_base import *


def enrich_all_routes(
    data: dict[str, Any],
    *,
    cache_dir: Path,
    limit: int | None,
    write: bool,
    rate_limit_s: float,
    use_overpass: bool,
    engine: str = "osrm",
    api_key: str | None = None,
) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    state_shapes = _load_state_shapes(cache_dir, rate_limit_s)
    processed = enriched = skipped = 0
    blockers: list[dict[str, Any]] = []
    for leg in data["legs"]:
        if limit is not None and processed >= limit:
            break
        corridor = leg.setdefault("corridor", {})
        needs = _leg_missing_fields(data, leg)
        if not needs:
            skipped += 1
            continue
        processed += 1
        try:
            # New legs are added with a "TBD" shield; label them from OSRM's ref
            # field so 100+ legs don't need hand-assigned highways. Done before
            # the ORS fetch so its cache key uses the final highway.
            if str(leg.get("highway", "")).upper() in ("", "TBD"):
                derived_hw = _osrm_primary_highway(data, leg, cache_dir, rate_limit_s)
                if derived_hw:
                    leg["highway"] = derived_hw
            if engine == "ors":
                parsed = _cached_ors_route(data, leg, cache_dir, rate_limit_s, api_key)
                geometry = parsed["coordinates"]
                samples, elevations = ors_corridor_samples(
                    parsed, float(leg["miles"]), sample_count=_ors_sample_count(float(leg["miles"]))
                )
                elevation_source = ORS_ELEVATION_SOURCE
                corridor_source = ORS_CORRIDOR_SOURCE
                corridor["tollway_detected"] = parsed["has_tollway"]
            else:
                route = _cached_osrm_route(data, leg, cache_dir, rate_limit_s)
                geometry = route["geometry"]["coordinates"]
                samples = _sample_geometry(geometry, float(leg["miles"]))
                elevations = _cached_elevations(samples, cache_dir, rate_limit_s)
                elevation_source = ELEVATION_SOURCE
                corridor_source = CORRIDOR_SOURCE
            if "route_points" in needs:
                corridor["route_points"] = [
                    {
                        "at_mi": round(point["at_mi"], 1),
                        "lat": round(point["lat"], 5),
                        "lon": round(point["lon"], 5),
                    }
                    for point in samples
                ]
            if "elevation_samples" in needs:
                corridor["elevation_samples"] = [
                    {
                        "at_mi": round(point["at_mi"], 1),
                        "elevation_ft": round(elevation, 1),
                        "source": elevation_source,
                    }
                    for point, elevation in zip(samples, elevations, strict=True)
                ]
            if "grade_segments" in needs:
                if engine == "ors":
                    fine_samples, fine_elevations = fine_grade_samples(parsed, float(leg["miles"]))
                    corridor["grade_segments"] = grade_segments_from_samples(
                        fine_samples, fine_elevations, leg
                    )
                else:
                    corridor["grade_segments"] = _grade_segments(samples, elevations, leg)
                # Label the leg's coarse terrain from the real grades. Only new
                # legs reach here (fully-enriched legs are skipped above), so a
                # placeholder "flat" on a freshly-added mountain leg is corrected
                # without rewriting existing curated terrain.
                rank = {"flat": 0, "hills": 1, "mountain": 2}
                terrains = [s.get("terrain", "flat") for s in corridor["grade_segments"]]
                if terrains:
                    leg["terrain"] = max(terrains, key=lambda t: rank.get(t, 0))
            if "checkpoints" in needs:
                corridor["checkpoints"] = _checkpoints(data, leg, samples)
            if "state_miles" in needs or "state_crossings" in needs:
                state_context = _state_context(data, leg, geometry, state_shapes)
                corridor["state_miles"] = state_context["state_miles"]
                if state_context["state_crossings"]:
                    corridor["state_crossings"] = state_context["state_crossings"]
                elif "state_crossings" in corridor:
                    corridor.pop("state_crossings")
            if not corridor.get("source"):
                corridor["source"] = corridor_source
            if "pois" in needs and use_overpass:
                stop = _discover_poi(data, leg, samples, cache_dir, rate_limit_s)
                if stop is not None:
                    leg["stops"] = [stop]
            if "pois" in _leg_missing_fields(data, leg):
                blockers.append(
                    {
                        "from": leg["from"],
                        "to": leg["to"],
                        "reason": "No actionable Overpass POI candidate found in sampled corridor searches.",
                        "next_action": (
                            "Run with --enrich-all --write after checking DOT/operator "
                            "sources or increasing Overpass search radius for this leg."
                        ),
                    }
                )
            else:
                enriched += 1
        except Exception as exc:  # noqa: BLE001 - batch report should keep moving.
            blockers.append(
                {
                    "from": leg["from"],
                    "to": leg["to"],
                    "reason": str(exc),
                    "next_action": "Retry this leg after checking cache/API availability.",
                }
            )
    report = coverage_report(data)
    return {
        "write": write,
        "processed": processed,
        "enriched_or_completed": enriched,
        "skipped_complete": skipped,
        "blockers": blockers,
        "coverage_totals": report["totals"],
    }


def _parse_only(value: str) -> set[tuple[str, str]]:
    # Legs are separated by ';' (not ',') so city names containing a comma
    # (e.g. "Charleston, West Virginia", disambiguated from Charleston, SC) parse
    # correctly. 'From:To' splits on the first ':'.
    pairs: set[tuple[str, str]] = set()
    for item in (value or "").split(";"):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise SystemExit(f"--only entries must be 'From:To', got {item!r}")
        a, b = item.split(":", 1)
        pairs.add((a.strip(), b.strip()))
    return pairs


def refresh_corridors(
    data: dict[str, Any],
    *,
    cache_dir: Path,
    rate_limit_s: float,
    engine: str,
    api_key: str | None,
    only: set[tuple[str, str]],
) -> dict[str, Any]:
    """Re-derive the geometry/terrain layer of selected legs from a routing
    engine, preserving every curated field.

    Only ``route_points``, ``elevation_samples``, ``grade_segments``, and the
    corridor source note are rewritten. Curated miles, POIs/stops, toll events,
    and the hand-named state crossings and checkpoints are left untouched, so a
    regeneration improves truck-legal geometry and real elevation without losing
    curation or changing pay/deadline-affecting mileage.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    refreshed: list[dict[str, Any]] = []
    for leg in data["legs"]:
        key = (leg["from"], leg["to"])
        if only and key not in only and (leg["to"], leg["from"]) not in only:
            continue
        corridor = leg.setdefault("corridor", {})
        miles = float(leg["miles"])
        if engine == "ors":
            parsed = _cached_ors_route(data, leg, cache_dir, rate_limit_s, api_key)
            samples, elevations = ors_corridor_samples(
                parsed, miles, sample_count=_ors_sample_count(miles)
            )
            elevation_source = ORS_ELEVATION_SOURCE
            corridor_source = ORS_CORRIDOR_SOURCE
            corridor["tollway_detected"] = parsed["has_tollway"]
            fine_samples, fine_elevations = fine_grade_samples(parsed, miles)
            grade_segments = grade_segments_from_samples(fine_samples, fine_elevations, leg)
        else:
            route = _cached_osrm_route(data, leg, cache_dir, rate_limit_s)
            samples = _sample_geometry(route["geometry"]["coordinates"], miles)
            elevations = _cached_elevations(samples, cache_dir, rate_limit_s)
            elevation_source = ELEVATION_SOURCE
            corridor_source = CORRIDOR_SOURCE
            grade_segments = _grade_segments(samples, elevations, leg)
        corridor["route_points"] = [
            {"at_mi": round(p["at_mi"], 1), "lat": round(p["lat"], 5), "lon": round(p["lon"], 5)}
            for p in samples
        ]
        corridor["elevation_samples"] = [
            {"at_mi": round(p["at_mi"], 1), "elevation_ft": round(e, 1), "source": elevation_source}
            for p, e in zip(samples, elevations, strict=True)
        ]
        corridor["grade_segments"] = grade_segments
        corridor["source"] = corridor_source
        refreshed.append(
            {"from": leg["from"], "to": leg["to"], "engine": engine, "points": len(samples)}
        )
    return {"refreshed": refreshed, "coverage_totals": coverage_report(data)["totals"]}


def _rescale_corridor_positions(leg: dict[str, Any], factor: float, new_miles: float) -> None:
    """Scale every at_mi position in a leg to a new total mileage.

    Keeps the corridor consistent (endpoints land exactly on 0 and new_miles)
    and clamps interior positions strictly inside the leg so the world loader's
    range validators still accept stops, crossings, checkpoints, and tolls.
    """
    corridor = leg.get("corridor", {})

    def interior(value: float) -> float:
        return max(0.1, min(round(new_miles - 0.1, 1), round(value * factor, 1)))

    for endpoint_field in ("route_points", "elevation_samples"):
        points = corridor.get(endpoint_field, [])
        for point in points:
            point["at_mi"] = round(min(new_miles, max(0.0, point["at_mi"] * factor)), 1)
        if points:
            points[0]["at_mi"] = 0.0
            points[-1]["at_mi"] = round(new_miles, 1)

    segments = corridor.get("grade_segments", [])
    for seg in segments:
        seg["start_mi"] = round(min(new_miles, max(0.0, seg["start_mi"] * factor)), 1)
        seg["end_mi"] = round(min(new_miles, max(0.0, seg["end_mi"] * factor)), 1)
        if seg["end_mi"] <= seg["start_mi"]:
            seg["end_mi"] = round(min(new_miles, seg["start_mi"] + 0.1), 1)
    if segments:
        segments[0]["start_mi"] = 0.0
        segments[-1]["end_mi"] = round(new_miles, 1)

    for field in ("state_crossings", "checkpoints", "toll_events"):
        for item in corridor.get(field, []):
            item["at_mi"] = interior(item["at_mi"])
    for stop in leg.get("stops", []):
        stop["at_mi"] = interior(stop["at_mi"])

    # state_miles is a per-state breakdown, not an at_mi; scale it so it still
    # sums to the leg total, fixing rounding drift on the last entry.
    state_miles = corridor.get("state_miles", [])
    for entry in state_miles:
        entry["miles"] = round(entry["miles"] * factor, 1)
    if state_miles:
        drift = round(new_miles - sum(e["miles"] for e in state_miles), 1)
        state_miles[-1]["miles"] = round(state_miles[-1]["miles"] + drift, 1)


def adopt_ors_miles(
    data: dict[str, Any],
    *,
    cache_dir: Path,
    rate_limit_s: float,
    api_key: str | None,
    only: set[tuple[str, str]],
) -> dict[str, Any]:
    """Rewrite leg mileage to the real ORS driving-hgv distance.

    Leg miles drive pay and deadlines, so accurate truck distances correct the
    economy. Every corridor at_mi position is rescaled to the new total so
    curated stops/crossings/tolls stay valid; their lat/lon and curation are
    otherwise preserved.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    changed: list[dict[str, Any]] = []
    for leg in data["legs"]:
        key = (leg["from"], leg["to"])
        if only and key not in only and (leg["to"], leg["from"]) not in only:
            continue
        old_miles = float(leg["miles"])
        parsed = _cached_ors_route(data, leg, cache_dir, rate_limit_s, api_key)
        new_miles = round(parsed["miles"])
        if new_miles <= 0 or new_miles == old_miles:
            continue
        leg["miles"] = new_miles
        _rescale_corridor_positions(leg, new_miles / old_miles, float(new_miles))
        changed.append(
            {"from": leg["from"], "to": leg["to"], "old_miles": old_miles, "new_miles": new_miles}
        )
    return {"changed": changed, "coverage_totals": coverage_report(data)["totals"]}


def format_enrichment_result(result: dict[str, Any]) -> str:
    totals = result["coverage_totals"]
    lines = [
        "Freight Fate route enrichment batch",
        f"Processed legs: {result['processed']}",
        f"Already complete: {result['skipped_complete']}",
        f"Completed in this view: {result['enriched_or_completed']}",
        f"Final playable metadata-backed legs: {totals['playable']}/{totals['legs']}",
        f"POIs with actions: {totals['pois_with_actions']}/{totals['legs']}",
        f"Expected crossings represented: "
        f"{totals['state_crossings_expected_present']}/"
        f"{totals['state_crossings_expected']}",
    ]
    if result["blockers"]:
        lines.append("Blockers:")
        for blocker in result["blockers"]:
            lines.append(
                f"- {blocker['from']} to {blocker['to']}: {blocker['reason']} "
                f"Next: {blocker['next_action']}"
            )
    return "\n".join(lines)


def _leg_missing_fields(data: dict[str, Any], leg: dict[str, Any]) -> list[str]:
    report = coverage_report({"cities": data["cities"], "legs": [leg]})
    return report["legs"][0]["missing"]


def _cached_osrm_route(
    data: dict[str, Any],
    leg: dict[str, Any],
    cache_dir: Path,
    rate_limit_s: float,
) -> dict[str, Any]:
    cities = data["cities"]
    start = cities[leg["from"]]
    end = cities[leg["to"]]
    coords = f"{start['lon']},{start['lat']};{end['lon']},{end['lat']}"
    params = {
        "overview": "simplified",
        "geometries": "geojson",
        "alternatives": "false",
        "steps": "false",
    }
    payload = _cached_json(
        cache_dir,
        "osrm",
        f"{leg['from']}--{leg['to']}--{leg['highway']}",
        OSRM_ROUTE_URL.format(coords=coords) + "?" + urllib.parse.urlencode(params),
        rate_limit_s=rate_limit_s,
    )
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RuntimeError(f"OSRM did not return a route: {payload.get('code')}")
    return payload["routes"][0]


def _cached_elevations(
    samples: list[dict[str, float]],
    cache_dir: Path,
    rate_limit_s: float,
) -> list[float]:
    params = urllib.parse.urlencode(
        {
            "latitude": ",".join(str(point["lat"]) for point in samples),
            "longitude": ",".join(str(point["lon"]) for point in samples),
        }
    )
    payload = _cached_json(
        cache_dir,
        "elevation",
        _hash_key(params),
        OPEN_METEO_ELEVATION_URL + "?" + params,
        rate_limit_s=rate_limit_s,
    )
    elevations_m = payload["elevation"]
    return [float(value) * 3.28084 for value in elevations_m]


def _discover_poi(
    data: dict[str, Any],
    leg: dict[str, Any],
    samples: list[dict[str, float]],
    cache_dir: Path,
    rate_limit_s: float,
) -> dict[str, Any] | None:
    candidate_points = [samples[len(samples) // 2]]
    if len(samples) >= 4:
        candidate_points.extend([samples[1], samples[-2]])
    for point in candidate_points:
        box = _bbox(point["lat"], point["lon"], 5000)
        query = f"""
        [out:json][timeout:40];
        (
          nwr["amenity"="fuel"]({box});
          nwr["highway"~"services|rest_area"]({box});
        );
        out tags center 12;
        """
        try:
            payload = _cached_overpass_json(
                cache_dir,
                f"{leg['from']}--{leg['to']}--{point['at_mi']:.1f}",
                urllib.parse.urlencode({"data": query}).encode("utf-8"),
                rate_limit_s=rate_limit_s,
            )
        except (TimeoutError, OSError, RuntimeError):
            continue
        stop = _poi_from_overpass(data, leg, point, payload.get("elements", []))
        if stop is not None:
            return stop
    return None


def _poi_from_overpass(
    data: dict[str, Any],
    leg: dict[str, Any],
    point: dict[str, float],
    elements: list[dict[str, Any]],
) -> dict[str, Any] | None:
    ranked: list[tuple[int, dict[str, Any]]] = []
    for element in elements:
        tags = element.get("tags", {})
        if not tags:
            continue
        name = _clean_poi_name(tags.get("name") or tags.get("brand") or "")
        amenity = tags.get("amenity", "")
        highway = tags.get("highway", "")
        score = 0
        if name:
            score += 8
        if amenity == "fuel":
            score += 6
        if highway in {"services", "rest_area"}:
            score += 5
        if tags.get("hgv") in {"yes", "designated"} or "truck" in name.lower():
            score += 4
        if amenity == "parking":
            score += 2
        ranked.append((score, element))
    if not ranked:
        return None
    _score, element = max(ranked, key=lambda item: item[0])
    tags = element.get("tags", {})
    name = _clean_poi_name(tags.get("name") or tags.get("brand") or "")
    stop_type = _stop_type_from_tags(tags)
    if not name:
        highway = tags.get("highway")
        if highway == "rest_area":
            name = f"{leg['highway']} corridor rest area"
        elif stop_type in {"truck_parking", "public_rest_area"}:
            name = f"{leg['highway']} corridor truck parking"
        else:
            name = f"{leg['highway']} corridor fuel stop"
    services = _services_for_stop_type(stop_type)
    actions = _actions_for_stop_type(stop_type)
    return {
        "name": name,
        "type": stop_type,
        "at_mi": round(max(1.0, min(float(leg["miles"]) - 1.0, point["at_mi"])), 1),
        "source": (
            "OpenStreetMap/Overpass development-time corridor amenity query, "
            f"accessed 2026-06-16 near {leg['from']} to {leg['to']} via "
            f"{leg['highway']}; curated into gameplay POI without raw OSM IDs."
        ),
        "parking": _parking_for_stop_type(stop_type),
        "actions": actions,
        "services": services,
    }


OVERPASS_POI_SOURCE = (
    "OpenStreetMap/Overpass development-time corridor amenity query, accessed "
    "2026-06-21; curated into a gameplay POI (clean name, normalized category) "
    "without raw OSM IDs."
)


def _bbox(lat: float, lon: float, radius_m: float) -> str:
    """A ``south,west,north,east`` box roughly ``radius_m`` around a point.

    Used as an Overpass bbox filter instead of ``around:``. On the public
    Overpass instances ``around:`` radius filters over broad amenity unions
    routinely time out (server aborts at 30-60s with an empty ``remark``
    payload); the equivalent bbox query returns the same POIs in a few seconds.
    """
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(0.1, math.cos(math.radians(lat))))
    return f"{lat - dlat},{lon - dlon},{lat + dlat},{lon + dlon}"


def _overpass_named_candidates(
    leg: dict[str, Any],
    samples: list[dict[str, float]],
    cache_dir: Path,
    rate_limit_s: float,
    want: int,
) -> list[dict[str, Any]]:
    """Named truck-relevant POIs of any brand near a leg, from OpenStreetMap.

    Brand-agnostic: returns Love's, Pilot, TA, Road Ranger, Kwik Trip,
    independents, rest areas, service plazas, and HGV truck parking alike --
    whatever OSM has a real name for. Unnamed amenities are skipped (no synthetic
    placeholders). Deduped by name, capped at ``want``.
    """
    candidate_points = [samples[len(samples) // 2]]
    if len(samples) >= 4:
        candidate_points += [samples[1], samples[-2]]
    if len(samples) >= 6:
        candidate_points += [samples[len(samples) // 4], samples[3 * len(samples) // 4]]
    # Gather across points, then rank: truck stops first, generic corridor fuel
    # as a fallback, warehouse/grocery retail fuel dropped entirely. Keeping the
    # best per name means one slow point doesn't starve the leg of good POIs.
    best: dict[str, tuple[int, dict[str, Any]]] = {}
    for point in candidate_points:
        box = _bbox(point["lat"], point["lon"], 6000)
        query = f"""
        [out:json][timeout:40];
        (
          nwr["amenity"="fuel"]["name"]({box});
          nwr["highway"~"services|rest_area"]["name"]({box});
          nwr["amenity"="parking"]["hgv"="yes"]["name"]({box});
        );
        out tags center 25;
        """
        try:
            payload = _cached_overpass_json(
                cache_dir,
                f"named--{leg['from']}--{leg['to']}--{point['at_mi']:.1f}",
                urllib.parse.urlencode({"data": query}).encode("utf-8"),
                rate_limit_s=rate_limit_s,
            )
        except (TimeoutError, OSError, urllib.error.URLError, urllib.error.HTTPError, RuntimeError):
            continue  # skip this point/leg; all endpoints failed or timed out
        at_mi = round(max(1.0, min(float(leg["miles"]) - 1.0, point["at_mi"])), 1)
        for element in payload.get("elements", []):
            tags = element.get("tags", {})
            raw = tags.get("name") or tags.get("brand") or ""
            try:
                name = _clean_poi_name(raw)
            except ValueError:
                continue
            if not name:
                continue
            score = _truck_relevance(tags, name)
            if score is None:
                continue  # retail/grocery fuel -- not a truck stop
            stop_type = _stop_type_from_tags(tags)
            cand = {
                "name": name,
                "type": stop_type,
                "at_mi": at_mi,
                "source": OVERPASS_POI_SOURCE,
                "parking": _parking_for_stop_type(stop_type),
                "actions": _actions_for_stop_type(stop_type),
                "services": _services_for_stop_type(stop_type),
            }
            existing = best.get(name.lower())
            if existing is None or score > existing[0]:
                best[name.lower()] = (score, cand)
    ranked = sorted(best.values(), key=lambda item: item[0], reverse=True)
    return [cand for _score, cand in ranked[:want]]


# Truck-stop brands / keywords (highest-value POIs for a freight game).

__all__ = [name for name in globals() if not name.startswith("__")]
