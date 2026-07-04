# ruff: noqa: F401,F403,F405,F821,I001
from __future__ import annotations

from enrich_routes_base import *


def coverage_report(data: dict[str, Any]) -> dict[str, Any]:
    cities = data["cities"]
    legs = data["legs"]
    totals = {
        "legs": len(legs),
        "route_points": 0,
        "state_crossings": 0,
        "state_crossings_expected": 0,
        "state_crossings_expected_present": 0,
        "checkpoints": 0,
        "state_miles": 0,
        "elevation_samples": 0,
        "grade_segments": 0,
        "pois": 0,
        "pois_with_actions": 0,
        "curated_pois": 0,
        "placeholder_pois": 0,
        "legs_with_curated_pois": 0,
        "legs_with_placeholder_only": 0,
        "legs_with_sufficient_poi_density": 0,
        "legs_with_fuel_support": 0,
        "poi_density": 0,
        "fuel_poi_support": 0,
        "toll_events": 0,
        "toll_legs": 0,
        "toll_review_pending": 0,
        "poi_review_pending": 0,
        "playable": 0,
    }
    leg_reports = []
    toll_review: list[dict[str, Any]] = []
    poi_review: list[dict[str, Any]] = []
    for leg in legs:
        corridor = leg.get("corridor", {})
        stops = leg.get("stops", [])
        from_state = cities[leg["from"]]["state"]
        to_state = cities[leg["to"]]["state"]
        expected_crossing = from_state != to_state
        curated_stops = [stop for stop in stops if not _stop_is_placeholder(stop)]
        placeholder_stops = [stop for stop in stops if _stop_is_placeholder(stop)]
        min_pois = _minimum_curated_pois(float(leg["miles"]))
        min_fuel_pois = _minimum_fuel_capable_pois(float(leg["miles"]))
        curated_pois_complete = bool(curated_stops) and all(
            stop.get("source")
            and _stop_actions(stop)
            and _stop_parking(stop) != "unknown"
            and _stop_directions(stop)
            for stop in curated_stops
        )
        sufficient_density = len(curated_stops) >= min_pois
        sufficient_fuel_support = (
            sum(1 for stop in curated_stops if "fuel" in _stop_actions(stop)) >= min_fuel_pois
        )
        present = {
            "route_points": len(corridor.get("route_points", [])) >= 2,
            "state_crossings": bool(corridor.get("state_crossings", [])),
            "checkpoints": bool(corridor.get("checkpoints", [])),
            "state_miles": bool(corridor.get("state_miles", [])),
            "elevation_samples": len(corridor.get("elevation_samples", [])) >= 2,
            "grade_segments": bool(corridor.get("grade_segments", [])),
            "pois": bool(stops),
            "pois_with_actions": curated_pois_complete,
            "curated_pois": curated_pois_complete,
            "poi_density": sufficient_density,
            "fuel_poi_support": sufficient_fuel_support,
        }
        missing = [field for field in REQUIRED_METADATA_FIELDS if not present[field]]
        if expected_crossing and not present["state_crossings"]:
            missing.append("state_crossings")
        playable = not missing
        for field, ok in present.items():
            if ok:
                totals[field] += 1
        toll_events = corridor.get("toll_events", [])
        totals["toll_events"] += len(toll_events)
        totals["toll_legs"] += int(bool(toll_events))
        if corridor.get("tollway_detected") and not toll_events:
            totals["toll_review_pending"] += 1
            toll_review.append(
                {
                    "from": leg["from"],
                    "to": leg["to"],
                    "highway": leg["highway"],
                    "note": "ORS flags a tollway but no toll_events are curated.",
                }
            )
        fuel_capable = sum(1 for stop in curated_stops if "fuel" in _stop_actions(stop))
        if float(leg["miles"]) >= LONG_LEG_POI_ADVISORY_MI and fuel_capable == 0:
            totals["poi_review_pending"] += 1
            poi_review.append(
                {
                    "from": leg["from"],
                    "to": leg["to"],
                    "highway": leg["highway"],
                    "miles": leg["miles"],
                    "note": (
                        "Long leg with no fuel-capable curated stop; leans on "
                        "the roadside-fuel fallback. Curation optional."
                    ),
                }
            )
        totals["curated_pois"] += len(curated_stops)
        totals["placeholder_pois"] += len(placeholder_stops)
        totals["legs_with_curated_pois"] += int(bool(curated_stops))
        totals["legs_with_placeholder_only"] += int(bool(placeholder_stops) and not curated_stops)
        totals["legs_with_sufficient_poi_density"] += int(sufficient_density)
        totals["legs_with_fuel_support"] += int(sufficient_fuel_support)
        totals["state_crossings_expected"] += int(expected_crossing)
        totals["state_crossings_expected_present"] += int(
            expected_crossing and present["state_crossings"]
        )
        totals["playable"] += int(playable)
        leg_reports.append(
            {
                "from": leg["from"],
                "to": leg["to"],
                "highway": leg["highway"],
                "miles": leg["miles"],
                "endpoint_state_change": expected_crossing,
                "playable": playable,
                "present": present,
                "missing": missing,
                "unsupported_reasons": _unsupported_reasons(
                    missing,
                    curated_count=len(curated_stops),
                    placeholder_count=len(placeholder_stops),
                    minimum_curated_pois=min_pois,
                    fuel_capable_count=sum(
                        1 for stop in curated_stops if "fuel" in _stop_actions(stop)
                    ),
                    minimum_fuel_capable_pois=min_fuel_pois,
                ),
                "poi_count": len(stops),
                "curated_poi_count": len(curated_stops),
                "placeholder_poi_count": len(placeholder_stops),
                "minimum_curated_pois": min_pois,
                "minimum_fuel_capable_pois": min_fuel_pois,
                "poi_actions": sorted(
                    {action for stop in curated_stops for action in _stop_actions(stop)}
                ),
                "toll_event_count": len(toll_events),
            }
        )
    percentages = {
        key: round(value / totals["legs"] * 100.0, 1)
        for key, value in totals.items()
        if key
        not in {
            "legs",
            "state_crossings_expected",
            "toll_events",
            "curated_pois",
            "placeholder_pois",
        }
    }
    if totals["state_crossings_expected"]:
        percentages["state_crossings_expected_present"] = round(
            totals["state_crossings_expected_present"] / totals["state_crossings_expected"] * 100.0,
            1,
        )
    return {
        "metadata_contract": {
            "playable_requires": list(REQUIRED_METADATA_FIELDS),
            "pois_are_advisory_not_required_for_dispatch": True,
            "placeholder_pois_do_not_count_for_dispatch": True,
            "advisory_minimum_curated_pois_by_length": {
                "under_160_mi": 1,
                "160_to_320_mi": 2,
                "over_320_mi": 3,
            },
            "advisory_minimum_fuel_capable_pois_by_length": {
                "under_160_mi": 0,
                "160_mi_and_over": 1,
            },
            "state_crossings_required_when_endpoint_states_differ": True,
            "runtime_network_calls": False,
            "legacy_full_graph_available_for_old_saves": True,
        },
        "current_batch_notes": [
            "Dispatch gates on routing metadata (geometry, elevation, grade, "
            f"state context) for the current {len(legs)}-leg network, from OSRM "
            "or the OpenRouteService driving-hgv route (elevation inline). "
            "Curated source-backed truck-stop coverage is now an additive "
            "quality layer, not a dispatch requirement; placeholder POIs stay "
            "quarantined and never count as curated. Long legs without a "
            "fuel/rest stop are flagged in poi_review, not blocked.",
        ],
        "toll_review": toll_review,
        "poi_review": poi_review,
        "high_priority_remaining_corridors": _priority_status(leg_reports),
        "totals": totals,
        "percentages": percentages,
        "legs": leg_reports,
        "missing_playable": [leg for leg in leg_reports if not leg["playable"]],
    }


def format_coverage_report(report: dict[str, Any]) -> str:
    totals = report["totals"]
    pct = report["percentages"]
    lines = [
        "Freight Fate route metadata coverage",
        f"Total legs: {totals['legs']}",
        f"Playable metadata-backed legs: {totals['playable']} ({pct.get('playable', 0.0):.1f}%)",
        f"Route geometry: {totals['route_points']} ({pct.get('route_points', 0.0):.1f}%)",
        f"Elevation/grade: {totals['grade_segments']} ({pct.get('grade_segments', 0.0):.1f}%)",
        f"POIs with actions: {totals['pois_with_actions']} "
        f"({pct.get('pois_with_actions', 0.0):.1f}%)",
        f"Curated POIs: {totals['curated_pois']} on "
        f"{totals['legs_with_curated_pois']} legs; placeholder POIs: "
        f"{totals['placeholder_pois']} on "
        f"{totals['legs_with_placeholder_only']} placeholder-only legs",
        f"Sufficient curated stop density: "
        f"{totals['legs_with_sufficient_poi_density']} "
        f"({pct.get('legs_with_sufficient_poi_density', 0.0):.1f}%)",
        f"Fuel-capable curated support: "
        f"{totals['legs_with_fuel_support']} "
        f"({pct.get('legs_with_fuel_support', 0.0):.1f}%)",
        f"Toll metadata: {totals['toll_events']} events on "
        f"{totals['toll_legs']} legs "
        f"({pct.get('toll_legs', 0.0):.1f}% of legs)",
        f"Expected state crossings represented: "
        f"{totals['state_crossings_expected_present']}/"
        f"{totals['state_crossings_expected']} "
        f"({pct.get('state_crossings_expected_present', 0.0):.1f}%)",
        "",
        "Current toll-corridor note:",
        "- NJ Turnpike, PA Turnpike, Ohio Turnpike, Indiana Toll Road, "
        "New England, Delaware, and Maryland I-95 toll events are modeled as "
        "settlement charges where source-backed estimates are checked in.",
        "- Toll plazas and gantries are payment events; toll-road service plazas "
        "remain separate actionable POIs.",
        "",
        "High-priority remaining corridors:",
    ]
    for item in report["high_priority_remaining_corridors"]:
        status = "playable" if item["playable"] else "missing " + ", ".join(item["missing"])
        lines.append(f"- {item['label']}: {status}")
    lines += [
        "",
        "Incomplete legs:",
    ]
    for leg in report["missing_playable"][:25]:
        lines.append(
            f"- {leg['from']} to {leg['to']} via {leg['highway']}: "
            f"missing {', '.join(leg['missing'])}"
        )
    omitted = len(report["missing_playable"]) - 25
    if omitted > 0:
        lines.append(f"- ... {omitted} more incomplete legs")
    return "\n".join(lines)


def _stop_actions(stop: dict[str, Any]) -> tuple[str, ...]:
    default_actions = {
        "truck_stop": ("park", "save", "fuel", "food", "break", "sleep"),
        "travel_center": ("park", "save", "fuel", "food", "break", "sleep"),
        "fuel_station": ("park", "save", "fuel", "break"),
        "service_plaza": ("park", "save", "fuel", "food", "break"),
        "public_rest_area": ("park", "save", "break", "sleep"),
        "truck_parking": ("park", "save", "break", "sleep"),
        "weigh_station": ("inspect",),
        "repair_shop": ("park", "save", "repair"),
    }
    return tuple(stop.get("actions") or default_actions.get(stop.get("type"), ()))


def _stop_parking(stop: dict[str, Any]) -> str:
    parking = str(stop.get("parking", "")).strip()
    if parking:
        return parking
    if "parking" not in stop.get("services", ()) and "park" not in _stop_actions(stop):
        return "none"
    if stop.get("type") in {"truck_stop", "travel_center", "service_plaza"}:
        return "likely"
    if stop.get("type") in {"public_rest_area", "truck_parking"}:
        return "limited"
    return "unknown"


def _stop_directions(stop: dict[str, Any]) -> tuple[str, ...]:
    return tuple(stop.get("directions") or ("both",))


def _stop_is_placeholder(stop: dict[str, Any]) -> bool:
    if stop.get("curation") == "placeholder":
        return True
    text = f"{stop.get('name', '')} {stop.get('source', '')}".lower()
    markers = (
        "corridor rest area",
        "corridor truck parking",
        "corridor fuel stop",
        "descriptive gameplay stop seeded",
        "seeded for offline route coverage",
    )
    return any(marker in text for marker in markers)


def _minimum_curated_pois(miles: float) -> int:
    if miles < 160.0:
        return 1
    if miles <= 320.0:
        return 2
    return 3


def _minimum_fuel_capable_pois(miles: float) -> int:
    if miles < 160.0:
        return 0
    return 1


def _unsupported_reasons(missing: list[str], **_poi_advisory: int) -> list[str]:
    """Blocking (routing) reasons a leg is not dispatchable.

    POIs are advisory and never appear in ``missing`` anymore, so they are not
    reported here; the extra keyword arguments are accepted for call-site
    compatibility and ignored.
    """
    return [f"missing {field}" for field in missing]


def _priority_status(leg_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for priority in HIGH_PRIORITY_REMAINING_CORRIDORS:
        leg = next(
            (
                item
                for item in leg_reports
                if item["from"] == priority["from"] and item["to"] == priority["to"]
            ),
            None,
        )
        out.append(
            {
                **priority,
                "playable": bool(leg and leg["playable"]),
                "missing": [] if leg is None else leg["missing"],
            }
        )
    return out


def _osrm_smoke(data: dict[str, Any], from_city: str, to_city: str) -> dict[str, Any]:
    cities = data["cities"]
    start = cities[from_city]
    end = cities[to_city]
    coords = f"{start['lon']},{start['lat']};{end['lon']},{end['lat']}"
    params = urllib.parse.urlencode(
        {
            "overview": "simplified",
            "geometries": "geojson",
            "alternatives": "false",
            "steps": "false",
        }
    )
    url = OSRM_ROUTE_URL.format(coords=coords) + "?" + params
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    route = payload["routes"][0]
    return {
        "code": payload.get("code", "unknown"),
        "miles": float(route["distance"]) / 1609.344,
        "points": len(route.get("geometry", {}).get("coordinates", [])),
    }


__all__ = [name for name in globals() if not name.startswith("__")]
