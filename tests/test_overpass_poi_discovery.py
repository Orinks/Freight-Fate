"""Endpoint-city Overpass POI discovery (no network).

The per-leg POI search historically queried only mid-corridor route_points
samples, so real truck-stop clusters at a leg's endpoint cities were never
found (Tucumcari, Barstow, Kingman, Indio, and Van Horn were all hand-added
after the fact). These pin the fix: the endpoint cities are queried too,
cache-keyed per city so legs sharing an endpoint reuse one response; a stop
at a shared city serves every leg touching that city (each gets it at its
own end); and endpoint finds ride on top of the ``per_leg`` corridor budget,
with the minimum-spacing rule capping discovery at one stop per leg end.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_enrich_routes():
    """Import tools/enrich_routes.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "enrich_routes", ROOT / "tools" / "enrich_routes.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


enrich_routes = _load_enrich_routes()


def _route_points(miles: float, count: int = 7) -> list[dict[str, float]]:
    return [
        {"at_mi": round(miles * i / (count - 1), 1), "lat": 35.0 + i * 0.1, "lon": -110.0 - i * 0.1}
        for i in range(count)
    ]


def _leg(from_city: str, to_city: str, miles: float, stops=None) -> dict:
    leg = {
        "from": from_city,
        "to": to_city,
        "miles": miles,
        "highway": "I-40",
        "corridor": {"route_points": _route_points(miles)},
    }
    if stops is not None:
        leg["stops"] = stops
    return leg


def _world(legs: list[dict]) -> dict:
    cities: dict[str, dict] = {}
    for leg in legs:
        for key in (leg["from"], leg["to"]):
            cities.setdefault(key, {"state": "AZ"})
    return {"cities": cities, "legs": legs}


def _stop_element(name: str) -> dict:
    return {"tags": {"name": name, "amenity": "fuel", "hgv": "yes"}}


def _patch_overpass(monkeypatch, responses: dict[str, dict]) -> list[str]:
    """Serve canned per-cache-key Overpass responses; record the keys queried."""
    pipeline = sys.modules["enrich_routes_pipeline"]
    calls: list[str] = []

    def fake(cache_dir, key, body, *, rate_limit_s):
        calls.append(key)
        return responses.get(key, {"elements": []})

    monkeypatch.setattr(pipeline, "_cached_overpass_json", fake)
    return calls


def test_endpoint_cities_are_queried_and_city_cluster_found(monkeypatch, tmp_path):
    leg = _leg("flagstaff_az_us", "kingman_az_us", 151.0)
    data = _world([leg])
    calls = _patch_overpass(
        monkeypatch,
        {"named-city--kingman_az_us": {"elements": [_stop_element("Flying J Travel Center")]}},
    )

    result = enrich_routes.add_overpass_pois(data, cache_dir=tmp_path, rate_limit_s=0.0, only=set())

    # Both endpoint cities are queried, cache-keyed by city (shared across legs),
    # alongside the leg-keyed mid-corridor samples.
    assert "named-city--flagstaff_az_us" in calls
    assert "named-city--kingman_az_us" in calls
    assert any(key.startswith("named--flagstaff_az_us--kingman_az_us--") for key in calls)
    assert result["added_pois"] == 1
    (stop,) = leg["stops"]
    assert stop["name"] == "Flying J Travel Center"
    assert stop["at_mi"] == 150.0  # pinned to the Kingman end, not nudged mid-leg
    assert "kingman_az_us endpoint city" in stop["source"]


def test_shared_endpoint_stop_serves_every_touching_leg(monkeypatch, tmp_path):
    west = _leg("flagstaff_az_us", "kingman_az_us", 151.0)
    south = _leg("kingman_az_us", "las_vegas_nv_us", 103.0)
    data = _world([west, south])
    _patch_overpass(
        monkeypatch,
        {"named-city--kingman_az_us": {"elements": [_stop_element("Flying J Travel Center")]}},
    )

    result = enrich_routes.add_overpass_pois(data, cache_dir=tmp_path, rate_limit_s=0.0, only=set())

    # A driver on either leg really does pass the Kingman cluster, so each leg
    # gets the stop at its own end.
    assert result["added_pois"] == 2
    (west_stop,) = west["stops"]
    (south_stop,) = south["stops"]
    assert west_stop["name"] == south_stop["name"] == "Flying J Travel Center"
    assert west_stop["at_mi"] == 150.0  # Kingman end of Flagstaff->Kingman
    assert south_stop["at_mi"] == 1.0  # Kingman end of Kingman->Las Vegas


def test_existing_curated_endpoint_stop_is_not_duplicated_or_crowded(monkeypatch, tmp_path):
    curated = {"name": "TA Travel Center", "at_mi": 147.0, "source": "hand curated"}
    leg = _leg("flagstaff_az_us", "kingman_az_us", 151.0, stops=[curated])
    data = _world([leg])
    _patch_overpass(
        monkeypatch,
        {
            "named-city--kingman_az_us": {
                "elements": [_stop_element("TA Travel Center"), _stop_element("Flying J Travel Center")]
            }
        },
    )

    result = enrich_routes.add_overpass_pois(data, cache_dir=tmp_path, rate_limit_s=0.0, only=set())

    # The rediscovered TA dedupes by name; Flying J is blocked by the 10-mile
    # spacing rule (one stop cluster per leg end), so hand curation stands.
    assert result["added_pois"] == 0
    assert leg["stops"] == [curated]


def test_endpoint_finds_ride_on_top_of_corridor_budget(monkeypatch, tmp_path):
    leg = _leg("flagstaff_az_us", "kingman_az_us", 151.0)
    data = _world([leg])
    prefix = "named--flagstaff_az_us--kingman_az_us--"
    _patch_overpass(
        monkeypatch,
        {
            f"{prefix}75.5": {"elements": [_stop_element("Roadside Truck Stop A")]},
            f"{prefix}25.2": {"elements": [_stop_element("Roadside Truck Stop B")]},
            f"{prefix}125.8": {"elements": [_stop_element("Roadside Truck Stop C")]},
            "named-city--flagstaff_az_us": {"elements": [_stop_element("Love's Travel Stop")]},
        },
    )

    result = enrich_routes.add_overpass_pois(
        data, cache_dir=tmp_path, rate_limit_s=0.0, only=set(), per_leg=2
    )

    # per_leg caps the mid-corridor finds at 2; the endpoint-city find still
    # lands, so a long sparse leg keeps both its corridor slots.
    assert result["added_pois"] == 3
    names = {s["name"] for s in leg["stops"]}
    assert "Love's Travel Stop" in names
    assert sum(1 for n in names if n.startswith("Roadside Truck Stop")) == 2
    (endpoint_stop,) = [s for s in leg["stops"] if s["name"] == "Love's Travel Stop"]
    assert endpoint_stop["at_mi"] == 1.0  # the Flagstaff end
