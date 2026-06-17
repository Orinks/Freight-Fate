"""Curate source-backed route POIs into the offline world data.

This is a development-time helper. It fetches public, no-key operator locator
feeds, projects candidate truck-relevant stops onto checked-in route geometry,
and can write explicit curated POIs into ``world.json``. Runtime gameplay stays
offline and reads only the checked-in result.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from freight_fate.data.world import WORLD_PATH, minimum_curated_pois

LOVES_ENDPOINT = "https://www.loves.com/api/fetch_stores"
PILOT_ENDPOINT = "https://locations.pilotflyingj.com/search"
USER_AGENT = "FreightFateRouteCuration/1.0"
ACCESSED_DATE = "2026-06-17"
EARTH_RADIUS_MI = 3958.7613


@dataclass(frozen=True)
class Candidate:
    provider: str
    key: str
    name: str
    poi_type: str
    lat: float
    lon: float
    highway: str
    exit_text: str
    source_url: str
    source_note: str
    parking: str
    services: tuple[str, ...]
    actions: tuple[str, ...]
    at_mi: float | None = None
    distance_mi: float | None = None

    def with_projection(self, at_mi: float, distance_mi: float) -> Candidate:
        return Candidate(
            self.provider,
            self.key,
            self.name,
            self.poi_type,
            self.lat,
            self.lon,
            self.highway,
            self.exit_text,
            self.source_url,
            self.source_note,
            self.parking,
            self.services,
            self.actions,
            at_mi,
            distance_mi,
        )

    def to_stop(self) -> dict[str, Any]:
        if self.at_mi is None or self.distance_mi is None:
            raise ValueError(f"{self.name} has not been projected onto a route")
        exit_part = f", {self.exit_text}" if self.exit_text else ""
        source = (
            f"{self.source_note}{exit_part}; at_mi estimated by projecting "
            f"source coordinates onto checked-in route geometry "
            f"({self.distance_mi:.1f} mi from simplified corridor line), "
            f"accessed {ACCESSED_DATE}: {self.source_url}"
        )
        return {
            "name": self.name,
            "type": self.poi_type,
            "at_mi": round(self.at_mi, 1),
            "source": source,
            "actions": list(self.actions),
            "services": list(self.services),
            "directions": ["both"],
            "parking": self.parking,
            "curation": "curated",
        }


MANUAL_CORRIDOR_POIS: dict[tuple[str, str], tuple[dict[str, Any], ...]] = {
    ("Buffalo", "New York"): (
        {
            "name": "Pembroke Service Area",
            "type": "service_plaza",
            "at_mi": 34.0,
            "source": (
                "New York State Thruway Authority official service-area listing "
                "identifies Pembroke Service Area on I-90/NYS Thruway near "
                "milepost 397; at_mi estimated from Buffalo-to-New York checked "
                f"route geometry, accessed {ACCESSED_DATE}: "
                "https://www.thruway.ny.gov/travelers/service-areas"
            ),
            "actions": ["park", "save", "fuel", "food", "break"],
            "services": ["diesel", "food", "parking", "restrooms"],
            "directions": ["both"],
            "parking": "likely",
            "curation": "curated",
        },
        {
            "name": "Junius Ponds Service Area",
            "type": "service_plaza",
            "at_mi": 108.0,
            "source": (
                "New York State Thruway Authority official service-area listing "
                "identifies Junius Ponds Service Area on I-90/NYS Thruway at "
                "milepost 324 between exits 41 and 42; at_mi estimated from "
                f"checked route geometry, accessed {ACCESSED_DATE}: "
                "https://www.thruway.ny.gov/travelers/service-areas"
            ),
            "actions": ["park", "save", "fuel", "food", "break"],
            "services": ["diesel", "food", "parking", "restrooms"],
            "directions": ["both"],
            "parking": "likely",
            "curation": "curated",
        },
        {
            "name": "Pattersonville Service Area",
            "type": "service_plaza",
            "at_mi": 252.0,
            "source": (
                "Applegreen and New York State Thruway service-area listings "
                "identify Pattersonville Service Area on the New York State "
                "Thruway; at_mi estimated from checked route geometry, accessed "
                f"{ACCESSED_DATE}: https://www.applegreen.com/"
            ),
            "actions": ["park", "save", "fuel", "food", "break"],
            "services": ["diesel", "food", "parking", "restrooms"],
            "directions": ["both"],
            "parking": "likely",
            "curation": "curated",
        },
    ),
    ("Tulsa", "Kansas City"): (
        {
            "name": "Pete's 66 Fort Scott",
            "type": "truck_stop",
            "at_mi": 142.0,
            "source": (
                "Truck Stops and Services directory lists Pete's 66 in Fort "
                "Scott on the US-54/US-69 corridor with 10 parking spots; "
                "at_mi estimated from checked route geometry, accessed "
                f"{ACCESSED_DATE}: "
                "https://www.truckstopsandservices.com/location_details.php?id=10851"
            ),
            "actions": ["park", "save", "fuel", "food", "break"],
            "services": ["diesel", "food", "parking", "restrooms"],
            "directions": ["both"],
            "parking": "limited",
            "curation": "curated",
        },
        {
            "name": "Trading Post Rest Area",
            "type": "public_rest_area",
            "at_mi": 178.0,
            "source": (
                "Kansas US-69 Trading Post Rest Area public listing identifies "
                "separate truck and vehicle parking, restrooms, picnic area, "
                "vending, and RV dump station; at_mi estimated from checked "
                f"route geometry, accessed {ACCESSED_DATE}: "
                "https://www.kansasrestareas.com/ks-us-route-69-kansas-us69-trading-post-rest-area-bidirectional/"
            ),
            "actions": ["park", "save", "break", "sleep"],
            "services": ["parking", "restrooms", "vending"],
            "directions": ["both"],
            "parking": "confirmed",
            "curation": "curated",
        },
    ),
    ("Sacramento", "San Francisco"): (
        {
            "name": "Sacramento 49er Travel Plaza",
            "type": "travel_center",
            "at_mi": 8.0,
            "source": (
                "Sacramento 49er Travel Plaza official parking page states "
                "that the facility dedicates a large area to controlled big "
                "rig parking; at_mi estimated from the Sacramento I-80 approach, "
                f"accessed {ACCESSED_DATE}: https://sacramento49er.com/parking/"
            ),
            "actions": ["park", "save", "fuel", "food", "break", "sleep"],
            "services": ["diesel", "food", "parking", "restrooms"],
            "directions": ["both"],
            "parking": "confirmed",
            "curation": "curated",
        },
    ),
    ("Sacramento", "Reno"): (
        {
            "name": "Sacramento 49er Travel Plaza",
            "type": "travel_center",
            "at_mi": 8.0,
            "source": (
                "Sacramento 49er Travel Plaza official parking page states "
                "that the facility dedicates a large area to controlled big "
                "rig parking; at_mi estimated from the Sacramento I-80 approach, "
                f"accessed {ACCESSED_DATE}: https://sacramento49er.com/parking/"
            ),
            "actions": ["park", "save", "fuel", "food", "break", "sleep"],
            "services": ["diesel", "food", "parking", "restrooms"],
            "directions": ["both"],
            "parking": "confirmed",
            "curation": "curated",
        },
    ),
    ("Reno", "Las Vegas"): (
        {
            "name": "Hawthorne Shell",
            "type": "truck_stop",
            "at_mi": 125.0,
            "source": (
                "Truck Stops and Services directory lists Hawthorne Shell on "
                "US-95 in Hawthorne, Nevada; parking certainty limited because "
                "the public listing confirms corridor truck-stop status but not "
                f"a current stall count, accessed {ACCESSED_DATE}: "
                "https://www.truckstopsandservices.com/location_details.php?id=11838"
            ),
            "actions": ["park", "save", "fuel", "break"],
            "services": ["diesel", "parking", "restrooms"],
            "directions": ["both"],
            "parking": "limited",
            "curation": "curated",
        },
        {
            "name": "Rebel Oil Truck Stop Beatty",
            "type": "truck_stop",
            "at_mi": 365.0,
            "source": (
                "Truck Stops and Services directory lists Rebel Oil Truck Stop "
                "on US-95 in Beatty with 5 parking spots; at_mi estimated from "
                f"checked route geometry, accessed {ACCESSED_DATE}: "
                "https://www.truckstopsandservices.com/location_details.php?id=11844"
            ),
            "actions": ["park", "save", "fuel", "food", "break"],
            "services": ["diesel", "food", "parking", "restrooms"],
            "directions": ["both"],
            "parking": "limited",
            "curation": "curated",
        },
    ),
    ("Spokane", "Boise"): (
        {
            "name": "Love's Travel Stop Post Falls",
            "type": "travel_center",
            "at_mi": 35.0,
            "source": (
                "Love's official store feed lists store 301 in Post Falls, "
                "Idaho on the I-90 approach used before the US-95 southbound "
                "corridor; at_mi estimated from checked route geometry, accessed "
                f"{ACCESSED_DATE}: https://www.loves.com/api/fetch_stores"
            ),
            "actions": ["park", "save", "fuel", "food", "break", "sleep"],
            "services": ["diesel", "food", "parking", "restrooms"],
            "directions": ["both"],
            "parking": "likely",
            "curation": "curated",
        },
        {
            "name": "Winchester Rest Area",
            "type": "public_rest_area",
            "at_mi": 185.0,
            "source": (
                "Idaho rest-area listing identifies Winchester Rest Area on "
                "US-95 near mile marker 278; at_mi estimated from checked route "
                f"geometry, accessed {ACCESSED_DATE}: https://www.idahorestareas.com/"
            ),
            "actions": ["park", "save", "break", "sleep"],
            "services": ["parking", "restrooms"],
            "directions": ["both"],
            "parking": "limited",
            "curation": "curated",
        },
        {
            "name": "Midvale Hill Rest Area",
            "type": "public_rest_area",
            "at_mi": 360.0,
            "source": (
                "Idaho rest-area listing identifies Midvale Hill Rest Area on "
                "US-95 near mile marker 101; at_mi estimated from checked route "
                f"geometry, accessed {ACCESSED_DATE}: https://www.idahorestareas.com/"
            ),
            "actions": ["park", "save", "break", "sleep"],
            "services": ["parking", "restrooms"],
            "directions": ["both"],
            "parking": "limited",
            "curation": "curated",
        },
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path, default=WORLD_PATH)
    parser.add_argument("--radius-miles", type=float, default=20.0)
    parser.add_argument("--write-world", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.world.read_text(encoding="utf-8"))
    candidates = fetch_loves_candidates() + fetch_pilot_candidates()
    report = curate_world(data, candidates, args.radius_miles)
    if args.write_world:
        args.world.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"Curated {report['added_pois']} POIs on {report['updated_legs']} legs; "
            f"{len(report['remaining_gaps'])} legs still under threshold."
        )


def fetch_loves_candidates() -> list[Candidate]:
    payload = _read_json(LOVES_ENDPOINT)
    out: list[Candidate] = []
    for store in payload["stores"]:
        lat = store.get("latitude")
        lon = store.get("longitude")
        if lat is None or lon is None:
            continue
        number = str(store["number"])
        city = str(store.get("city", "")).strip()
        state = str(store.get("state", "")).strip()
        out.append(
            Candidate(
                provider="loves",
                key=number,
                name=f"Love's Travel Stop {city}".strip(),
                poi_type="travel_center",
                lat=float(lat),
                lon=float(lon),
                highway=str(store.get("highway", "")).strip(),
                exit_text=_format_exit(store.get("exitNumber")),
                source_url=LOVES_ENDPOINT,
                source_note=(
                    f"Love's official store feed lists store {number} in "
                    f"{city}, {state} on {store.get('highway', 'the corridor')}"
                ),
                parking="likely",
                services=("diesel", "food", "parking", "restrooms"),
                actions=("park", "save", "fuel", "food", "break", "sleep"),
            )
        )
    return out


def fetch_pilot_candidates() -> list[Candidate]:
    out: list[Candidate] = []
    offset = 0
    while True:
        url = f"{PILOT_ENDPOINT}?per=50&offset={offset}&locations=all"
        payload = _read_json(url, accept_json=True)
        response = payload["response"]
        entities = response["entities"]
        for entity in entities:
            profile = entity.get("profile", {})
            coord = profile.get("yextDisplayCoordinate") or {}
            address = profile.get("address") or {}
            if not coord:
                continue
            store_id = str(entity.get("id") or profile.get("meta", {}).get("id"))
            name = str(profile.get("name") or "Pilot Travel Center")
            parking_count = _int_text(profile.get("c_pagesPublicParkingCount"))
            services = ["diesel", "food", "restrooms"]
            if parking_count > 0:
                services.append("parking")
            amenities = tuple(str(item) for item in profile.get("c_pagesAmenities", ()))
            if any("cat scale" in item.lower() for item in amenities):
                services.append("scale")
            out.append(
                Candidate(
                    provider="pilot",
                    key=store_id,
                    name=_pilot_name(name, address, store_id),
                    poi_type="travel_center",
                    lat=float(coord["lat"]),
                    lon=float(coord["long"]),
                    highway=str(profile.get("c_interstate", "")).strip(),
                    exit_text=_format_exit(profile.get("c_exitNumber")),
                    source_url=str(
                        profile.get("c_pagesURL")
                        or profile.get("websiteUrl")
                        or f"{PILOT_ENDPOINT}?per=50&locations=all"
                    ),
                    source_note=(
                        f"Pilot Flying J official locator lists {name} "
                        f"store {store_id} in {address.get('city', '')}, "
                        f"{address.get('region', '')}"
                        + (
                            f" with {parking_count} public truck parking spaces"
                            if parking_count > 0
                            else ""
                        )
                    ),
                    parking="confirmed" if parking_count > 0 else "limited",
                    services=tuple(dict.fromkeys(services)),
                    actions=("park", "save", "fuel", "food", "break", "sleep"),
                )
            )
        offset += len(entities)
        if offset >= int(response["count"]) or not entities:
            break
        time.sleep(0.1)
    return out


def curate_world(
    data: dict[str, Any],
    candidates: list[Candidate],
    radius_miles: float,
) -> dict[str, Any]:
    added_pois = 0
    updated_legs = 0
    remaining_gaps = []
    for leg in data["legs"]:
        original_stops = leg.get("stops", [])
        curated_stops = [stop for stop in original_stops if not _stop_is_placeholder(stop)]
        minimum = minimum_curated_pois(float(leg["miles"]))
        selected: list[dict[str, Any]] = []
        manual = MANUAL_CORRIDOR_POIS.get((leg["from"], leg["to"]), ())
        if len(curated_stops) < minimum and manual:
            selected.extend(_dedupe_manual(manual, curated_stops))
        if len(curated_stops) + len(selected) < minimum:
            projected = [
                item
                for item in (_project_candidate(leg, candidate) for candidate in candidates)
                if item is not None
                and item.distance_mi is not None
                and item.distance_mi <= radius_miles
                and _highway_matches(leg["highway"], item.highway)
                and _not_duplicate(item, curated_stops, selected)
            ]
            need = minimum - len(curated_stops) - len(selected)
            selected.extend(_select_spread(projected, leg, curated_stops + selected, need))
        if selected or len(curated_stops) != len(original_stops):
            leg["stops"] = sorted(
                curated_stops + selected,
                key=lambda stop: float(stop["at_mi"]),
            )
            added_pois += len(selected)
            updated_legs += 1
        curated_count = len([stop for stop in leg.get("stops", []) if not _stop_is_placeholder(stop)])
        if curated_count < minimum:
            remaining_gaps.append({
                "from": leg["from"],
                "to": leg["to"],
                "highway": leg["highway"],
                "curated_pois": curated_count,
                "minimum_curated_pois": minimum,
            })
    return {
        "source_endpoints": [LOVES_ENDPOINT, f"{PILOT_ENDPOINT}?per=50&offset=N&locations=all"],
        "source_candidate_count": len(candidates),
        "added_pois": added_pois,
        "updated_legs": updated_legs,
        "remaining_gaps": remaining_gaps,
    }


def _read_json(url: str, *, accept_json: bool = False) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT}
    if accept_json:
        headers["Accept"] = "application/json"
    request = urllib.request.Request(url, headers=headers)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Unable to fetch route POI source {url}") from last_error


def _project_candidate(leg: dict[str, Any], candidate: Candidate) -> Candidate | None:
    points = leg.get("corridor", {}).get("route_points", [])
    if len(points) < 2:
        return None
    best_distance = float("inf")
    best_at_mi = 0.0
    for start, end in zip(points, points[1:], strict=False):
        distance, at_mi = _project_to_segment(candidate, start, end)
        if distance < best_distance:
            best_distance = distance
            best_at_mi = at_mi
    if not 3.0 < best_at_mi < float(leg["miles"]) - 3.0:
        return None
    return candidate.with_projection(best_at_mi, best_distance)


def _project_to_segment(
    candidate: Candidate,
    start: dict[str, Any],
    end: dict[str, Any],
) -> tuple[float, float]:
    lat0 = (float(start["lat"]) + float(end["lat"]) + candidate.lat) / 3.0
    px, py = _xy(candidate.lat, candidate.lon, lat0)
    ax, ay = _xy(float(start["lat"]), float(start["lon"]), lat0)
    bx, by = _xy(float(end["lat"]), float(end["lon"]), lat0)
    vx = bx - ax
    vy = by - ay
    wx = px - ax
    wy = py - ay
    segment_len_sq = vx * vx + vy * vy
    t = 0.0 if segment_len_sq == 0.0 else (wx * vx + wy * vy) / segment_len_sq
    t = max(0.0, min(1.0, t))
    qx = ax + t * vx
    qy = ay + t * vy
    at_mi = float(start["at_mi"]) + t * (float(end["at_mi"]) - float(start["at_mi"]))
    return math.hypot(px - qx, py - qy), at_mi


def _xy(lat: float, lon: float, lat0: float) -> tuple[float, float]:
    return (
        math.radians(lon) * math.cos(math.radians(lat0)) * EARTH_RADIUS_MI,
        math.radians(lat) * EARTH_RADIUS_MI,
    )


def _select_spread(
    candidates: list[Candidate],
    leg: dict[str, Any],
    existing: list[dict[str, Any]],
    need: int,
) -> list[dict[str, Any]]:
    if need <= 0:
        return []
    selected: list[Candidate] = []
    used: set[tuple[str, str]] = set()
    existing_miles = [float(stop["at_mi"]) for stop in existing]
    target_count = len(existing_miles) + need
    targets = [
        float(leg["miles"]) * (idx + 1) / (target_count + 1)
        for idx in range(target_count)
    ]
    open_targets = sorted(targets, key=lambda target: min(
        [abs(target - mile) for mile in existing_miles] or [float("inf")]
    ), reverse=True)[:need]
    for target in open_targets:
        available = [
            candidate for candidate in candidates
            if (candidate.provider, candidate.key) not in used
            and _far_enough(candidate, existing_miles, selected)
        ]
        if not available:
            available = [
                candidate for candidate in candidates
                if (candidate.provider, candidate.key) not in used
            ]
        if not available:
            break
        chosen = min(
            available,
            key=lambda candidate: (
                abs(float(candidate.at_mi or 0.0) - target),
                float(candidate.distance_mi or 0.0),
            ),
        )
        selected.append(chosen)
        used.add((chosen.provider, chosen.key))
    return [candidate.to_stop() for candidate in sorted(selected, key=lambda item: item.at_mi or 0.0)]


def _far_enough(
    candidate: Candidate,
    existing_miles: list[float],
    selected: list[Candidate],
) -> bool:
    at_mi = float(candidate.at_mi or 0.0)
    other_miles = existing_miles + [float(item.at_mi or 0.0) for item in selected]
    return all(abs(at_mi - other) >= 12.0 for other in other_miles)


def _dedupe_manual(
    manual: tuple[dict[str, Any], ...],
    existing: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing_names = {str(stop["name"]).casefold() for stop in existing}
    return [
        dict(stop)
        for stop in manual
        if str(stop["name"]).casefold() not in existing_names
    ]


def _not_duplicate(
    candidate: Candidate,
    existing: list[dict[str, Any]],
    selected: list[dict[str, Any]],
) -> bool:
    name = candidate.name.casefold()
    source_key = f" {candidate.key} "
    for stop in existing + selected:
        if str(stop.get("name", "")).casefold() == name:
            return False
        if source_key.strip() and source_key in f" {stop.get('source', '')} ":
            return False
    return True


def _highway_matches(leg_highway: str, candidate_highway: str) -> bool:
    leg = _normalize_highway(leg_highway)
    candidate = _normalize_highway(candidate_highway)
    return bool(candidate) and (leg in candidate or candidate in leg)


def _normalize_highway(value: str) -> str:
    text = str(value).upper()
    replacements = {
        "INTERSTATE": "I",
        "US HWY": "US",
        "HIGHWAY": "",
        "HWY": "",
        ",": " ",
        "/": " ",
        "-": " ",
        "_": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def _stop_is_placeholder(stop: dict[str, Any]) -> bool:
    text = f"{stop.get('name', '')} {stop.get('source', '')}".lower()
    return stop.get("curation") == "placeholder" or "seeded for offline route coverage" in text


def _format_exit(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.lower().startswith("exit") else f"exit {text}"


def _int_text(value: Any) -> int:
    try:
        return int(str(value or "0").strip())
    except ValueError:
        return 0


def _pilot_name(name: str, address: dict[str, Any], store_id: str) -> str:
    city = str(address.get("city") or "").strip()
    if city:
        return f"{name} {city}"
    return f"{name} {store_id}"


if __name__ == "__main__":
    main()
