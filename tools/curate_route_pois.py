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
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from freight_fate.data.world import WORLD_PATH, minimum_curated_pois

LOVES_ENDPOINT = "https://www.loves.com/api/fetch_stores"
PILOT_ENDPOINT = "https://locations.pilotflyingj.com/search"
# FHWA "Jason's Law" truck parking inventory (public rest areas / welcome centers
# with truck-parking spot counts), published as NTAD via the BTS ArcGIS hub.
# Fills corridors the major chains don't cover -- official government data.
JASONS_LAW_ENDPOINT = (
    "https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/"
    "NTAD_Truck_Stop_Parking/FeatureServer/0/query"
)
USER_AGENT = "FreightFateRouteCuration/1.0"
ACCESSED_DATE = "2026-06-17"
JASONS_LAW_ACCESSED_DATE = "2026-07-17"
JASONS_LAW_ABOUT_URL = "https://geodata.bts.gov/datasets/usdot::truck-stop-parking/about"
EARTH_RADIUS_MI = 3958.7613

# Existing stop types an official truck-parking survey record may annotate.
# Weigh stations and toll plazas are not parking; placeholders stay quarantined.
PARKING_ANNOTATABLE_TYPES = {
    "public_rest_area",
    "truck_parking",
    "travel_center",
    "truck_stop",
    "service_plaza",
    "fuel_station",
}


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
    # Surveyed truck-parking spot count (Jason's Law records carry one).
    parking_spaces: int = 0

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
            parking_spaces=self.parking_spaces,
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
        stop = {
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
        if self.parking_spaces > 0:
            stop["parking_spaces"] = self.parking_spaces
        return stop


MANUAL_CORRIDOR_POIS: dict[tuple[str, str], tuple[dict[str, Any], ...]] = {
    ("buffalo_ny_us", "new_york_ny_us"): (
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
            "actions": ["park", "save", "fuel", "food", "break", "sleep"],
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
            "actions": ["park", "save", "fuel", "food", "break", "sleep"],
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
            "actions": ["park", "save", "fuel", "food", "break", "sleep"],
            "services": ["diesel", "food", "parking", "restrooms"],
            "directions": ["both"],
            "parking": "likely",
            "curation": "curated",
        },
    ),
    ("tulsa_ok_us", "kansas_city_mo_us"): (
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
    ("sacramento_ca_us", "san_francisco_ca_us"): (
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
    ("sacramento_ca_us", "reno_nv_us"): (
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
    ("reno_nv_us", "las_vegas_nv_us"): (
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
    ("spokane_wa_us", "boise_id_us"): (
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
    parser.add_argument(
        "--include-jasons-law",
        action="store_true",
        help="Also pull the FHWA Jason's Law public truck-parking "
        "inventory to fill corridors the chains miss.",
    )
    parser.add_argument(
        "--annotate-parking",
        action="store_true",
        help="Annotate existing curated stops with official truck-parking "
        "capacity from the FHWA Jason's Law inventory instead of adding "
        "new stops (skips the operator chain feeds).",
    )
    parser.add_argument(
        "--jasons-law-file",
        type=Path,
        help="Read a locally downloaded GeoJSON snapshot of the Jason's Law "
        "layer instead of the live BTS endpoint.",
    )
    parser.add_argument(
        "--jasons-law-only",
        action="store_true",
        help="Fill under-density legs from the Jason's Law inventory alone "
        "(no operator chain feeds): annotate existing stops first, then "
        "offer only the records that matched no checked-in stop as new "
        "public rest-area POIs.",
    )
    args = parser.parse_args()

    data = json.loads(args.world.read_text(encoding="utf-8"))
    if args.jasons_law_only:
        candidates = fetch_jasons_law_candidates(args.jasons_law_file)
        # Records that describe an already checked-in stop must not come back
        # as lookalike new POIs under their survey names, so annotate first
        # (idempotent) and fill only from what remains.
        annotate_report = annotate_truck_parking(data, candidates)
        matched = set(annotate_report["matched_keys"])
        remaining = [c for c in candidates if c.key not in matched]
        report = curate_world(data, remaining, args.radius_miles)
        report["annotate"] = {
            k: v for k, v in annotate_report.items() if k not in {"annotations", "matched_keys"}
        }
        if args.write_world:
            args.world.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(
                f"Annotated {report['annotate']['annotated_stops']} stops, then "
                f"curated {report['added_pois']} survey POIs on "
                f"{report['updated_legs']} legs; "
                f"{len(report['remaining_gaps'])} legs still under threshold."
            )
        return
    if args.annotate_parking:
        candidates = fetch_jasons_law_candidates(args.jasons_law_file)
        report = annotate_truck_parking(data, candidates)
        if args.write_world:
            args.world.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(
                f"Annotated {report['annotated_stops']} stops on "
                f"{report['annotated_legs']} legs from "
                f"{report['matched_survey_records']} survey records."
            )
        return
    candidates = fetch_loves_candidates() + fetch_pilot_candidates()
    if args.include_jasons_law:
        candidates += fetch_jasons_law_candidates(args.jasons_law_file)
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


_DIRECTION_TOKENS = {"EB", "WB", "NB", "SB", "N", "S", "E", "W", "NORTH", "SOUTH", "EAST", "WEST"}


def _strip_direction(route: str) -> str:
    """'I-10 EB' -> 'I-10' so the FHWA route matches a leg's highway shield."""
    parts = route.replace("/", " ").split()
    while parts and parts[-1].upper().strip(".") in _DIRECTION_TOKENS:
        parts = parts[:-1]
    return " ".join(parts)


def fetch_jasons_law_candidates(source_file: Path | None = None) -> list[Candidate]:
    """Public truck-parking facilities from the FHWA Jason's Law inventory.

    Government source covering corridors the major chains miss -- rest areas and
    welcome centers with real truck-parking spot counts. Typed as public rest
    areas (legal overnight parking, no guaranteed fuel/food).

    ``source_file`` reads a locally downloaded GeoJSON snapshot of the same
    layer instead of the live endpoint, so re-runs are offline and reproducible.
    """
    if source_file is not None:
        payload = json.loads(source_file.read_text(encoding="utf-8"))
    else:
        params = urllib.parse.urlencode(
            {"where": "1=1", "outFields": "*", "outSR": "4326", "f": "geojson"}
        )
        payload = _read_json(f"{JASONS_LAW_ENDPOINT}?{params}", accept_json=True)
    out: list[Candidate] = []
    for feature in payload.get("features", []):
        props = feature.get("properties", {})
        coords = (feature.get("geometry") or {}).get("coordinates") or [None, None]
        lon, lat = coords[0], coords[1]
        if lat is None or lon is None:
            continue
        # Survey text arrives with stray newlines and doubled spaces; collapse
        # to single spaces so player-facing names and notes stay clean.
        raw_route = " ".join(str(props.get("highway_route", "") or "").split())
        highway = _strip_direction(raw_route)
        municipality = " ".join(str(props.get("municipality", "") or "").split())
        state = str(props.get("state", "") or "").strip()
        spots = props.get("number_of_spots")
        name = " ".join(str(props.get("nhs_rest_stop", "") or "").split())
        # Survey shorthand "MM 129" is mile-marker jargon; speak it as "Mile".
        name = re.sub(r"\bMM\b", "Mile", name)
        # Skip mandatory inspection/weigh facilities -- not a chooseable rest stop.
        if "weigh" in name.lower() or "inspection" in name.lower():
            continue
        # Dataset placeholders ("NA", "NHS Rest Stop or Truck Facility 19") ->
        # use a descriptive highway/municipality fallback instead.
        if name.upper() in {"NA", "N/A", "NONE"} or name.lower().startswith(
            "nhs rest stop or truck facility"
        ):
            name = ""
        if not name:
            near = f" near {municipality}" if municipality else ""
            name = f"{highway or 'Corridor'} truck parking{near}"
        spots_text = (
            f" with {int(spots)} truck parking spaces"
            if isinstance(spots, (int, float)) and spots
            else ""
        )
        out.append(
            Candidate(
                provider="jasons_law",
                key=str(props.get("OBJECTID")),
                name=name,
                poi_type="public_rest_area",
                lat=float(lat),
                lon=float(lon),
                highway=highway,
                exit_text=(f"mile post {props.get('mile_post')}" if props.get("mile_post") else ""),
                source_url=JASONS_LAW_ENDPOINT,
                source_note=(
                    f"FHWA Jason's Law truck parking inventory (NTAD via BTS) "
                    f"lists {name} on {raw_route or 'the corridor'} in "
                    f"{municipality}, {state}{spots_text}"
                ),
                parking="confirmed",
                services=("parking", "restrooms"),
                actions=("park", "save", "break", "sleep"),
                parking_spaces=(int(spots) if isinstance(spots, (int, float)) and spots > 0 else 0),
            )
        )
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
        curated_count = len(
            [stop for stop in leg.get("stops", []) if not _stop_is_placeholder(stop)]
        )
        if curated_count < minimum:
            remaining_gaps.append(
                {
                    "from": leg["from"],
                    "to": leg["to"],
                    "highway": leg["highway"],
                    "curated_pois": curated_count,
                    "minimum_curated_pois": minimum,
                }
            )
    return {
        "source_endpoints": [LOVES_ENDPOINT, f"{PILOT_ENDPOINT}?per=50&offset=N&locations=all"],
        "source_candidate_count": len(candidates),
        "added_pois": added_pois,
        "updated_legs": updated_legs,
        "remaining_gaps": remaining_gaps,
    }


def annotate_truck_parking(
    data: dict[str, Any],
    candidates: list[Candidate],
    *,
    max_at_mi_delta: float = 1.5,
    max_corridor_mi: float = 1.0,
) -> dict[str, Any]:
    """Annotate existing curated stops with official truck-parking capacity.

    Matches FHWA Jason's Law survey records to already checked-in stops (same
    corridor highway, snapped within ``max_corridor_mi`` of the route and
    ``max_at_mi_delta`` route miles of the stop) and writes ``parking_spaces``
    plus ``parking: confirmed`` with an appended source sentence. Paired
    directional records (EB/WB lots) collapse onto one stop keeping the larger
    lot's count. Never invents stops and never touches ``parking: none``.
    """
    annotated: list[dict[str, Any]] = []
    matched_keys: set[str] = set()
    near_route_candidates = 0
    for leg in data["legs"]:
        stops = [
            stop
            for stop in leg.get("stops", [])
            if not _stop_is_placeholder(stop)
            and str(stop.get("type", "")) in PARKING_ANNOTATABLE_TYPES
            and str(stop.get("parking", "")) != "none"
        ]
        if not stops:
            continue
        for candidate in candidates:
            projected = _project_candidate(leg, candidate)
            if (
                projected is None
                or projected.distance_mi is None
                or projected.distance_mi > max_corridor_mi
                or not _highway_matches(leg["highway"], projected.highway)
            ):
                continue
            near_route_candidates += 1
            best = _match_survey_record_to_stop(projected, stops, max_at_mi_delta)
            if best is None:
                continue
            spaces = max(int(best.get("parking_spaces", 0)), projected.parking_spaces)
            changed = False
            if spaces > 0 and spaces != int(best.get("parking_spaces", 0)):
                best["parking_spaces"] = spaces
                changed = True
            if str(best.get("parking", "")) != "confirmed":
                best["parking"] = "confirmed"
                changed = True
            if "Jason's Law" not in str(best.get("source", "")):
                spaces_part = f" with {spaces} truck parking spaces" if spaces else ""
                best["source"] = (
                    f"{str(best.get('source', '')).rstrip('. ')}. "
                    f"Truck parking confirmed by the FHWA Jason's Law inventory "
                    f"(USDOT BTS NTAD Truck Stop Parking, compiled 2019), which "
                    f"lists {projected.name}{spaces_part} on this corridor, "
                    f"accessed {JASONS_LAW_ACCESSED_DATE}: {JASONS_LAW_ABOUT_URL}"
                )
                changed = True
            matched_keys.add(candidate.key)
            if changed:
                annotated.append(
                    {
                        "from": leg["from"],
                        "to": leg["to"],
                        "stop": best["name"],
                        "parking_spaces": spaces,
                        "survey_record": projected.name,
                    }
                )
    annotated_legs = len({(item["from"], item["to"]) for item in annotated})
    return {
        "source_candidate_count": len(candidates),
        "candidates_near_routes": near_route_candidates,
        "matched_survey_records": len(matched_keys),
        "matched_keys": sorted(matched_keys),
        "annotated_stops": len(annotated),
        "annotated_legs": annotated_legs,
        "annotations": annotated,
    }


# Generic words that appear in almost every facility name; a name "match"
# needs at least one distinctive token in common beyond these.
_SURVEY_NAME_STOPWORDS = {
    "rest",
    "area",
    "welcome",
    "visitor",
    "visitors",
    "center",
    "travel",
    "stop",
    "stops",
    "truck",
    "parking",
    "plaza",
    "service",
    "county",
    "state",
    "road",
    "highway",
    "interstate",
    "nhs",
    "facility",
    "turnout",
    "north",
    "south",
    "east",
    "west",
    "northbound",
    "southbound",
    "eastbound",
    "westbound",
    "nb",
    "sb",
    "eb",
    "wb",
    "near",
    "the",
    "and",
}


def _survey_name_tokens(name: str) -> set[str]:
    tokens = {t for t in re.findall(r"[a-z]+", str(name).lower()) if len(t) >= 3}
    return tokens - _SURVEY_NAME_STOPWORDS


def _survey_names_match(stop_name: str, record_name: str) -> bool:
    return bool(_survey_name_tokens(stop_name) & _survey_name_tokens(record_name))


def _survey_names_conflict(stop_name: str, record_name: str) -> bool:
    """Both names carry distinctive place tokens and share none -- two
    different facilities that happen to project near each other."""
    stop_tokens = _survey_name_tokens(stop_name)
    record_tokens = _survey_name_tokens(record_name)
    return bool(stop_tokens) and bool(record_tokens) and not (stop_tokens & record_tokens)


# Public facility classes where a same-spot, same-class record is near-certain
# to be the same lot even when states name it by county rather than place.
_PUBLIC_PARKING_TYPES = {"public_rest_area", "truck_parking"}
_PUBLIC_MATCH_DELTA_MI = 0.7


def _match_survey_record_to_stop(
    projected: Candidate,
    stops: list[dict[str, Any]],
    max_at_mi_delta: float,
) -> dict[str, Any] | None:
    """The checked-in stop a survey record verifiably describes, or None.

    A distinctive name-token overlap matches any stop type; without one, only a
    public rest-area/truck-parking stop sitting nearly on top of the record
    matches -- a branded travel center never inherits a nearby public lot's
    count."""
    best: dict[str, Any] | None = None
    best_rank: tuple[int, float] | None = None
    record_tokens = _survey_name_tokens(projected.name)
    for stop in stops:
        delta = abs(float(stop["at_mi"]) - float(projected.at_mi or 0.0))
        if delta > max_at_mi_delta:
            continue
        overlap = len(_survey_name_tokens(str(stop.get("name", ""))) & record_tokens)
        public = (
            str(stop.get("type", "")) in _PUBLIC_PARKING_TYPES
            and delta <= _PUBLIC_MATCH_DELTA_MI
            and not _survey_names_conflict(str(stop.get("name", "")), projected.name)
        )
        if not overlap and not public:
            continue
        # More shared distinctive tokens beats closer distance: "Gee Creek"
        # must out-rank the adjacent "Scatter Creek" for record "Gee Creek NB".
        rank = (-overlap, delta)
        if best_rank is None or rank < best_rank:
            best, best_rank = stop, rank
    return best


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
    targets = [float(leg["miles"]) * (idx + 1) / (target_count + 1) for idx in range(target_count)]
    open_targets = sorted(
        targets,
        key=lambda target: min([abs(target - mile) for mile in existing_miles] or [float("inf")]),
        reverse=True,
    )[:need]
    for target in open_targets:
        available = [
            candidate
            for candidate in candidates
            if (candidate.provider, candidate.key) not in used
            and _far_enough(candidate, existing_miles, selected)
        ]
        if not available:
            available = [
                candidate
                for candidate in candidates
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
    return [
        candidate.to_stop() for candidate in sorted(selected, key=lambda item: item.at_mi or 0.0)
    ]


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
    return [dict(stop) for stop in manual if str(stop["name"]).casefold() not in existing_names]


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
