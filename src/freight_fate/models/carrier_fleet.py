"""Dispatch-assigned company tractors, banded by career level.

Real fleets do not let a new hire shop for a truck: dispatch hands out
whatever the yard has, and better equipment follows seniority. Company
drivers therefore run a carrier-assigned tractor chosen from a level-band
fleet pool. The pick is deterministic per driver and carrier, so the same
career always meets the same truck, but two drivers at the same level can
be handed different iron.

Owner-operators are outside this module: after the level-18 buy-in the
tractor on the profile is player property (see ``trucks.TRUCK_CATALOG``).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .trucks import TRUCK_CATALOG


@dataclass(frozen=True)
class FleetTier:
    key: str
    min_level: int
    label: str
    pool: tuple[str, ...]  # TRUCK_CATALOG keys dispatch draws from
    blurb: str  # spoken when dispatch hands the truck over


# Tank capacity never shrinks across tiers, so a promotion never strands a
# fuller tank than the new truck can hold.
FLEET_TIERS: tuple[FleetTier, ...] = (
    FleetTier(
        "yard_standard",
        1,
        "yard standard",
        ("rig",),
        "every new hire starts in the same trainer-spec tractor",
    ),
    FleetTier(
        "regional",
        4,
        "regional fleet",
        ("sunset_day_cab", "ridgeline_sleeper", "old_longnose"),
        "a newer regional tractor from the working fleet",
    ),
    FleetTier(
        "long_haul",
        9,
        "long-haul fleet",
        ("highline_sleeper", "big_bunk_conventional", "aero_cruiser"),
        "a long-haul sleeper with real interstate range",
    ),
    FleetTier(
        "premium",
        13,
        "premium fleet",
        ("summit_flagship", "silver_aero"),
        "a premium tractor reserved for senior drivers",
    ),
    FleetTier(
        "first_pick",
        17,
        "first pick of the yard",
        ("presidential_sleeper", "night_flag_aero"),
        "first pick of the yard, the carrier's best equipment",
    ),
)


def fleet_tier_for_level(level: int) -> FleetTier:
    tier = FLEET_TIERS[0]
    for candidate in FLEET_TIERS:
        if int(level) >= candidate.min_level:
            tier = candidate
    return tier


def _stable_index(profile, tier: FleetTier) -> int:
    name = str(getattr(profile, "name", "") or "Driver")
    carrier = str(getattr(profile, "carrier_key", "") or "")
    digest = hashlib.sha256(f"{name}|{carrier}|{tier.key}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % len(tier.pool)


def assigned_truck_key(profile) -> str:
    """The tractor dispatch has this company driver in right now."""
    level = int(getattr(getattr(profile, "career", None), "level", 1))
    tier = fleet_tier_for_level(level)
    return tier.pool[_stable_index(profile, tier)]


def fleet_assignment_text(profile) -> str:
    """Spoken description of the current carrier tractor assignment."""
    key = assigned_truck_key(profile)
    model = TRUCK_CATALOG[key]
    tier = fleet_tier_for_level(int(profile.career.level))
    return f"Dispatch has you in a {model.label} from the {tier.label}: {model.description}"


def fleet_upgrade_announcement(profile) -> str:
    """Spoken hand-over line when a promotion changes the assigned tractor."""
    key = assigned_truck_key(profile)
    model = TRUCK_CATALOG[key]
    return (
        f"Dispatch upgraded your assigned tractor. You are now running a "
        f"{model.label}: {model.description} The yard handed it over "
        "fueled, serviced, and washed."
    )
