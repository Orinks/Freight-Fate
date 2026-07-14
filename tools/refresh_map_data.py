"""Owner-run map refresh: report what the world has drifted from reality.

Report-only by design. The world's baked data is deterministic and curated;
this tool never edits it. It re-checks the live sources the bakes came from
and prints what needs a human (or a recipe run) to act on:

- ``--radio``: play every supported real radio stream through the game's own
  BASS stack and report the dead ones. Stream URLs rot fast -- seven died
  within a day of the 2026-07-14 sweep -- so this is the cheapest, highest
  value check.
- ``--limits-lint``: run the speed-limit anchor repair rules as a linter.
  Zero findings means the baked profiles still satisfy every judgment rule
  in tools/repair_interstate_anchor_limits.py; any finding means either new
  pollution (bake bug) or hand-edited drift.
- ``--stops``: for chosen legs, re-query OSM (Overpass; honors the
  OVERPASS_URL env for the self-hosted instance) for named truck POIs and
  diff against the baked stops: fresh names worth curating in, and baked
  OSM-sourced stops that no longer appear (a weak closure signal -- verify
  before removing; the search is sampled, not exhaustive).

Usage:
    uv run python tools/refresh_map_data.py --radio --limits-lint
    uv run python tools/refresh_map_data.py --stops --only phoenix_az_us,globe_az_us
    uv run python tools/refresh_map_data.py --stops --max-legs 25
    uv run python tools/refresh_map_data.py --all --max-legs 25

Exit code is 1 when anything needs attention, so a scheduled run can alert.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = ROOT / "src" / "freight_fate" / "data" / "world.json"
RADIO_PATH = ROOT / "src" / "freight_fate" / "data" / "radio_catalog.json"
CACHE_DIR = ROOT / ".cache" / "map-refresh"

sys.path.insert(0, str(Path(__file__).resolve().parent))


def check_radio() -> list[str]:
    """Play every supported real stream; return the dead ones."""
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("FREIGHT_FATE_NO_SPEECH", "1")
    sys.path.insert(0, str(ROOT / "src"))
    from freight_fate.audio import _BassBackend

    catalog = json.loads(RADIO_PATH.read_text(encoding="utf-8"))
    targets = [
        s for s in catalog["stations"] if s.get("real_stream") and s.get("supported")
    ]
    backend = _BassBackend()
    dead: list[str] = []
    for station in targets:
        stream = backend._url_stream(station["stream_url"])
        verdict = "dead"
        if stream is not None:
            stream.play()
            time.sleep(2.0)
            if stream.position:
                verdict = "alive"
            stream.stop()
        if verdict == "dead":
            # One retry with a pause: stream hosts throttle rapid connects.
            time.sleep(3.0)
            stream = backend._url_stream(station["stream_url"])
            if stream is not None:
                stream.play()
                time.sleep(2.0)
                if stream.position:
                    verdict = "alive"
                stream.stop()
        if verdict == "dead":
            dead.append(f"{station['id']} | {station['stream_url']}")
        print(f"  {verdict:5} | {station['id']}")
    return dead


def check_limits() -> list[dict]:
    """Run the anchor-repair judgment rules as a linter (no writes)."""
    from repair_interstate_anchor_limits import repair

    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    return repair(data)  # mutates only the in-memory copy


def check_stops(only: set[tuple[str, str]], max_legs: int) -> dict[str, list[str]]:
    """Diff live OSM truck POIs against baked stops for the chosen legs."""
    # enrich_routes stitches the helper modules into one namespace at import
    # time (pipeline functions resolve names defined in sibling modules), so
    # the candidate finder must be reached through it.
    import enrich_routes

    _overpass_named_candidates = enrich_routes._overpass_named_candidates

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    fresh: list[str] = []
    recheck: list[str] = []
    checked = 0
    for leg in data["legs"]:
        key = (leg["from"], leg["to"])
        if only and key not in only and (leg["to"], leg["from"]) not in only:
            continue
        points = leg.get("corridor", {}).get("route_points", [])
        if len(points) < 2:
            continue
        if max_legs and checked >= max_legs:
            break
        checked += 1
        stops = leg.get("stops", [])
        baked_names = {str(s.get("name", "")).lower() for s in stops}
        candidates = _overpass_named_candidates(leg, points, CACHE_DIR, 1.0, 12)
        candidate_names = {str(c.get("name", "")).lower() for c in candidates}
        for cand in candidates:
            if cand["name"].lower() not in baked_names:
                fresh.append(f"{leg['from']}-{leg['to']}: {cand['name']} at mile {cand['at_mi']}")
        for stop in stops:
            source = str(stop.get("source", ""))
            if "OpenStreetMap" not in source:
                continue  # curated stops are not expected in the OSM query
            if str(stop.get("name", "")).lower() in candidate_names:
                continue
            # The sampled search not passing near a stop proves nothing;
            # ask OSM directly around the stop's own corridor point.
            if _stop_still_in_osm(enrich_routes, leg, points, stop):
                continue
            recheck.append(
                f"{leg['from']}-{leg['to']}: {stop.get('name')} at mile "
                f"{stop.get('at_mi')} (absent around its own point -- "
                "verify before touching)"
            )
        print(f"  checked {leg['from']}-{leg['to']}: {len(candidates)} live candidates")
    return {"fresh": fresh, "recheck": recheck}


def _stop_still_in_osm(enrich_routes, leg: dict, points: list[dict], stop: dict) -> bool:
    """Whether the baked stop's name still appears near its corridor point."""
    at_mi = float(stop.get("at_mi", 0.0))
    point = min(points, key=lambda p: abs(float(p["at_mi"]) - at_mi))
    box = enrich_routes._bbox(point["lat"], point["lon"], 8000)
    name = str(stop.get("name", "")).replace('"', "")
    query = f"""
    [out:json][timeout:40];
    nwr["name"~"{name}", i]({box});
    out tags 5;
    """
    import urllib.parse

    try:
        payload = enrich_routes._cached_overpass_json(
            CACHE_DIR,
            f"exists--{leg['from']}--{leg['to']}--{at_mi:.1f}--{name[:24]}",
            urllib.parse.urlencode({"data": query}).encode("utf-8"),
            rate_limit_s=1.0,
        )
    except Exception:  # noqa: BLE001 -- Overpass hiccups are not closures
        return True
    return bool(payload.get("elements"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--radio", action="store_true", help="check real radio streams")
    parser.add_argument("--limits-lint", action="store_true", help="lint baked speed limits")
    parser.add_argument("--stops", action="store_true", help="diff live OSM POIs vs baked stops")
    parser.add_argument("--all", action="store_true", help="run every check")
    parser.add_argument(
        "--only",
        nargs="*",
        default=[],
        metavar="FROM,TO",
        help="limit --stops to these legs (repeatable, comma-separated city keys)",
    )
    parser.add_argument("--max-legs", type=int, default=0, help="cap --stops leg count")
    args = parser.parse_args()
    if args.all:
        args.radio = args.limits_lint = args.stops = True
    if not (args.radio or args.limits_lint or args.stops):
        parser.error("pick at least one check (--radio, --limits-lint, --stops, or --all)")

    attention = 0
    if args.radio:
        print("== Radio dial health ==")
        dead = check_radio()
        for line in dead:
            print(f"  DEAD: {line}")
        print(f"  {len(dead)} dead stream(s)\n")
        attention += len(dead)
    if args.limits_lint:
        print("== Speed-limit lint ==")
        findings = check_limits()
        for entry in findings:
            print(f"  DRIFT: {entry['leg']} ({entry['highway']}): {entry['dropped']}")
        print(f"  {len(findings)} finding(s) -- fresh bakes must report zero\n")
        attention += len(findings)
    if args.stops:
        if not args.only and not args.max_legs:
            parser.error("--stops needs --only legs or --max-legs (a full sweep is a long run)")
        print("== Truck-stop drift ==")
        only = {tuple(pair.split(",", 1)) for pair in args.only}
        report = check_stops(only, args.max_legs)
        for line in report["fresh"]:
            print(f"  NEW: {line}")
        for line in report["recheck"]:
            print(f"  RECHECK: {line}")
        print(
            f"  {len(report['fresh'])} uncurated candidate(s), "
            f"{len(report['recheck'])} baked stop(s) to re-verify\n"
        )
        attention += len(report["fresh"]) + len(report["recheck"])

    if attention:
        print(f"{attention} item(s) need attention. Nothing was changed; curate via the recipes.")
        return 1
    print("Everything checked is still true. Nothing was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
