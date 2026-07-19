#!/usr/bin/env python3
"""Map which US states the game's routes pass through.

Loads the world data and reports which states are covered by the game's
corridors, based on state_miles and state_crossings baked into each leg's
corridor data.

Usage: uv run python tools/map_route_states.py
"""

from __future__ import annotations

import json
from pathlib import Path

WORLD_DATA_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "freight_fate" / "data" / "world_data"
)
LEGS_PATH = WORLD_DATA_PATH / "us" / "legs.json"
CITIES_PATH = WORLD_DATA_PATH / "us" / "cities.json"


def main():
    with open(LEGS_PATH, encoding="utf-8") as f:
        legs_data = json.load(f)

    with open(CITIES_PATH, encoding="utf-8") as f:
        cities_data = json.load(f)

    legs = legs_data["legs"]
    cities = cities_data.get("cities", {})

    # Build city -> state lookup (from cities metadata)
    city_state: dict[str, str] = {}
    for key, raw in cities.items():
        state_code = str(raw.get("state", "")).strip()
        city_state[key] = state_code

    # Track states found via each method
    states_from_crossings: set[str] = set()
    states_from_mileages: set[str] = set()
    states_from_city_endpoints: set[str] = set()
    highway_state_map: dict[str, set[str]] = {}
    legs_with_data = 0
    legs_without = 0

    for leg in legs:
        corridor = leg.get("corridor", {})
        has_state_data = False

        # 1. State crossings (state lines)
        sc = corridor.get("state_crossings", [])
        for crossing in sc:
            s = str(crossing.get("state", "")).strip()
            fs = str(crossing.get("from_state", "")).strip()
            if s:
                states_from_crossings.add(s.lower())
                has_state_data = True
            if fs:
                states_from_crossings.add(fs.lower())
                has_state_data = True

        # 2. State mileages
        sm = corridor.get("state_miles", [])
        for m in sm:
            s = str(m.get("state", "")).strip()
            if s:
                states_from_mileages.add(s.lower())
                has_state_data = True

        # 3. City endpoints (from/from_state in city lookup)
        leg_from = str(leg.get("from", "")).strip()
        leg_to = str(leg.get("to", "")).strip()
        if leg_from in city_state and city_state[leg_from]:
            states_from_city_endpoints.add(city_state[leg_from].lower())
            has_state_data = True
        if leg_to in city_state and city_state[leg_to]:
            states_from_city_endpoints.add(city_state[leg_to].lower())
            has_state_data = True

        # Track which highways go through which states
        highway = leg.get("highway", "")
        if highway and has_state_data:
            leg_states: set[str] = set()
            for crossing in sc:
                s = str(crossing.get("state", "")).strip()
                if s:
                    leg_states.add(s)
            for m in sm:
                s = str(m.get("state", "")).strip()
                if s:
                    leg_states.add(s)
            if leg_from in city_state and city_state[leg_from]:
                leg_states.add(city_state[leg_from])
            if leg_to in city_state and city_state[leg_to]:
                leg_states.add(city_state[leg_to])
            if leg_states:
                highway_state_map.setdefault(highway, set()).update(leg_states)

        if has_state_data:
            legs_with_data += 1
        else:
            legs_without += 1

    # Combine all state sources
    all_states = states_from_crossings | states_from_mileages | states_from_city_endpoints
    # Also check state_miles at leg level (non-corridor)
    for leg in legs:
        sm = leg.get("state_miles", [])
        for m in sm:
            s = str(m.get("state", "")).strip()
            if s:
                all_states.add(s.lower())

    print("=" * 60)
    print("FREIGHT FATE — Route State Coverage Report")
    print("=" * 60)
    print()
    print(f"Total legs: {len(legs)}")
    print(f"  With state data:  {legs_with_data}")
    print(f"  Without any:      {legs_without}")
    print()

    if all_states:
        print(f"States covered by routes ({len(all_states)}):")
        print("-" * 40)
        for s in sorted(all_states):
            count_legs = sum(1 for leg in legs if _leg_touches_state(leg, s, city_state))
            print(f"  {s:<20} ~{count_legs} legs")
    else:
        print("No state data found in legs.")

    print()
    print("States by detection method:")
    print(f"  State crossings:    {len(states_from_crossings):>3}  {sorted(states_from_crossings)}")
    print(f"  State mileages:     {len(states_from_mileages):>3}  {sorted(states_from_mileages)}")
    print(
        f"  City endpoints:     {len(states_from_city_endpoints):>3}  {sorted(states_from_city_endpoints)}"
    )
    print()

    print("State → Highways map:")
    print("-" * 40)
    for state in sorted(all_states):
        highways = sorted(
            hw
            for hw, states in highway_state_map.items()
            if any(s.lower() == state for s in states)
        )
        print(f"  {state}: {', '.join(highways) if highways else '(no highway data)'}")

    print()
    print("Highway → States map:")
    print("-" * 40)
    for highway in sorted(highway_state_map):
        states = sorted(highway_state_map[highway])
        print(f"  {highway}: {', '.join(states)}")

    print()
    print("=" * 60)
    print("Recommendation: Which 511 API states support the routes")
    print("=" * 60)
    supported_511_states = {
        "ohio": "OHGO (already implemented)",
        "wisconsin": "Iteris platform",
        "new york": "Iteris platform",
        "georgia": "Iteris platform",
        "arizona": "Iteris platform",
        "alaska": "Iteris platform",
        "connecticut": "Iteris platform",
        "texas": "DriveTexas API",
        "oregon": "TripCheck API",
        "nevada": "nvroads API",
        "washington": "WSDOT API",
    }

    for state in sorted(all_states):
        state_lower = state.lower()
        api_info = supported_511_states.get(state_lower, "No known public 511 API")
        print(f"  {state:<15} → {api_info}")


def _leg_touches_state(leg: dict, state: str, city_state: dict) -> bool:
    """Check if a leg touches the given state (case-insensitive)."""
    state_lower = state.lower()

    # Check city endpoints
    leg_from = str(leg.get("from", "")).strip()
    leg_to = str(leg.get("to", "")).strip()
    if leg_from in city_state and city_state[leg_from].lower() == state_lower:
        return True
    if leg_to in city_state and city_state[leg_to].lower() == state_lower:
        return True

    # Check corridor state data
    corridor = leg.get("corridor", {})
    for crossing in corridor.get("state_crossings", []):
        s = str(crossing.get("state", "")).strip()
        fs = str(crossing.get("from_state", "")).strip()
        if s.lower() == state_lower or fs.lower() == state_lower:
            return True
    for m in corridor.get("state_miles", []):
        s = str(m.get("state", "")).strip()
        if s.lower() == state_lower:
            return True

    return False


if __name__ == "__main__":
    main()
