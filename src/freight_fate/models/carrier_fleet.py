"""Dispatch-assigned company tractors, banded by career level.

Real fleets do not let a new hire shop for a truck: dispatch hands out
whatever the yard has, and better equipment follows seniority. Company
drivers therefore run a carrier-assigned tractor chosen from a level-band
fleet pool. The pick is deterministic per driver and carrier, so the same
career always meets the same truck, but two drivers at the same level can
be handed different iron.

Junior drivers slip-seat, which is what actually happens to a new hire at a
big carrier: no truck is *yours*, and the yard hands you whatever is free and
suited to the run. So below ``DEDICATED_TRUCK_LEVEL`` the tractor is chosen
per load out of a small pool of spares, matched to the work -- a bunk for a
run that cannot be finished inside one driving shift, a heavy-spec driveline
for a heavy load, a day cab for a day's worth of city stops. Seniority ends
that: from ``DEDICATED_TRUCK_LEVEL`` the driver has one assigned tractor and
keeps it, which is the whole point of seniority.

The pool is small and stable on purpose. Each tractor keeps its own wear,
damage, and fuel (``Profile.truck_conditions``), so a driver cycling through
three spares watches three trucks age rather than climbing into a factory
fresh one every load.

Owner-operators are outside this module: after the level-18 buy-in the
tractor on the profile is player property (see ``trucks.TRUCK_CATALOG``).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .trucks import CAB_DAY, CAB_SLEEPER, SPEC_HEAVY, SPEC_LIGHT, TRUCK_CATALOG

# Seniority earns a truck of your own. Below this the driver slip-seats.
DEDICATED_TRUCK_LEVEL = 9
# Spare tractors the yard keeps free for a junior driver to draw from.
SLIP_SEAT_POOL_SIZE = 3
# Hours of service allow eleven hours of driving between rests, which at
# real average lane speed is a bit over six hundred miles. Past this a run
# cannot be finished inside one shift, so the truck needs a bunk in it.
SLEEPER_RUN_MI = 500.0
# Payload past this is heavy-spec work: a light tractor can legally carry it
# but will spend the whole trip wishing it were not.
HEAVY_LOAD_TONS = 20.0
# Inside this, the run is a turn: back the same day, so a day cab is the
# honest piece of equipment and the yard keeps its sleepers for the long lanes.
DAY_CAB_RUN_MI = 250.0


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
        (
            "sunset_day_cab",
            "ridgeline_sleeper",
            "old_longnose",
            "city_shuttle",
            "dock_hopper",
            "short_haul_stubnose",
            "midroof_runner",
            "farm_road_workhorse",
            "trainer_day_cab",
            "hand_me_down_sleeper",
            "plain_jane_conventional",
            "yard_mule",
        ),
        "a newer regional tractor from the working fleet",
    ),
    FleetTier(
        "long_haul",
        9,
        "long-haul fleet",
        (
            "highline_sleeper",
            "big_bunk_conventional",
            "aero_cruiser",
            "long_run_midroof",
            "dry_lightning",
            "interstate_condo",
            "steel_hauler",
            "mountain_spec_hauler",
        ),
        "a long-haul sleeper with real interstate range",
    ),
    FleetTier(
        "premium",
        13,
        "premium fleet",
        (
            "summit_flagship",
            "silver_aero",
            "cabover_revival",
            "chrome_shop_special",
            "deep_sleeper_custom",
            "wide_glide_tourer",
            "granite_grade_king",
        ),
        "a premium tractor reserved for senior drivers",
    ),
    FleetTier(
        "first_pick",
        17,
        "first pick of the yard",
        (
            "presidential_sleeper",
            "night_flag_aero",
            "midnight_flyer",
            "owner_spec_showpiece",
            "centurion_longhood",
            "continental_expedition",
        ),
        "first pick of the yard, the carrier's best equipment",
    ),
)


def fleet_tier_for_level(level: int) -> FleetTier:
    tier = FLEET_TIERS[0]
    for candidate in FLEET_TIERS:
        if int(level) >= candidate.min_level:
            tier = candidate
    return tier


def _driver_seed(profile, tier: FleetTier) -> int:
    name = str(getattr(profile, "name", "") or "Driver")
    carrier = str(getattr(profile, "carrier_key", "") or "")
    digest = hashlib.sha256(f"{name}|{carrier}|{tier.key}".encode()).digest()
    return int.from_bytes(digest[:4], "big")


def _stable_index(profile, tier: FleetTier) -> int:
    return _driver_seed(profile, tier) % len(tier.pool)


def slip_seat_pool(profile) -> tuple[str, ...]:
    """The spare tractors this yard leaves free for this junior driver.

    A rotated slice of the tier pool rather than a random sample, so the same
    driver always draws the same few trucks and their wear is something the
    player can actually get to know.

    The slice is then made to cover the work. A yard that dispatches long
    freight does not leave a driver holding nothing but day cabs -- the rotation
    alone did exactly that, and the driver went out on a nine hundred mile run
    with nowhere legal to sleep -- and a yard that dispatches heavy freight
    keeps something spec'd to pull it.
    """
    tier = fleet_tier_for_level(int(getattr(getattr(profile, "career", None), "level", 1)))
    pool = tier.pool
    size = min(SLIP_SEAT_POOL_SIZE, len(pool))
    start = _driver_seed(profile, tier) % len(pool)
    rotated = [pool[(start + offset) % len(pool)] for offset in range(len(pool))]
    picked = rotated[:size]
    # Sleeper first: it is the one a load can legally require. Each rule gets
    # its own slot, working back from the end -- sharing one slot let the heavy
    # rule overwrite the sleeper the previous rule had just put there, and the
    # driver went back to holding nothing but day cabs.
    reserved: set[int] = set()
    for trait in (
        lambda key: TRUCK_CATALOG[key].cab == CAB_SLEEPER,
        lambda key: TRUCK_CATALOG[key].spec == SPEC_HEAVY,
    ):
        if any(trait(key) for key in picked):
            continue
        replacement = next((key for key in rotated if trait(key) and key not in picked), None)
        slot = next((i for i in reversed(range(len(picked))) if i not in reserved), None)
        if replacement is None or slot is None:
            continue  # this tier has none to cover with, or no slot left
        picked[slot] = replacement
        reserved.add(slot)
    return tuple(picked)


def slip_seats(profile) -> bool:
    """Whether this driver takes a truck per load instead of owning a seat."""
    level = int(getattr(getattr(profile, "career", None), "level", 1))
    return level < DEDICATED_TRUCK_LEVEL


def job_equipment_needs(job) -> tuple[bool, bool, bool]:
    """What the load asks of a tractor: (sleeper, heavy spec, day-cab work)."""
    if job is None:
        return False, False, False
    distance = float(getattr(job, "distance_mi", 0.0) or 0.0)
    weight = float(getattr(job, "weight_tons", 0.0) or 0.0)
    return (
        distance > SLEEPER_RUN_MI,
        weight >= HEAVY_LOAD_TONS,
        distance <= DAY_CAB_RUN_MI,
    )


def _fit_score(key: str, needs: tuple[bool, bool, bool]) -> tuple[int, int]:
    """How well a tractor suits the load; higher is better.

    The first number is the hard one -- a run that needs a bunk simply cannot
    go out on a day cab -- and the second is preference, so the yard still
    hands out something sensible when the perfect truck is already gone.
    """
    needs_sleeper, needs_heavy, is_turn = needs
    model = TRUCK_CATALOG[key]
    hard = 0 if (needs_sleeper and model.cab == CAB_DAY) else 1
    score = 0
    if needs_heavy:
        score += {SPEC_HEAVY: 3, SPEC_LIGHT: -1}.get(model.spec, 1)
    else:
        # Nothing heavy about the load: a light tractor leaves the payload
        # headroom and burns less doing it.
        score += {SPEC_LIGHT: 2, SPEC_HEAVY: -1}.get(model.spec, 1)
    if is_turn and model.cab == CAB_DAY:
        score += 2  # a day's work is day-cab work; keep the sleepers for lanes
    if needs_sleeper and model.cab == CAB_SLEEPER:
        score += 2
    return hard, score


def assigned_truck_key(profile, job=None) -> str:
    """The tractor dispatch has this company driver in for this run.

    Without a job -- a menu readout, a save load, anything outside a dispatch
    -- this is the driver's standing assignment. With one, and while the
    driver is still slip-seating, it is the best fit the yard has free.
    """
    level = int(getattr(getattr(profile, "career", None), "level", 1))
    tier = fleet_tier_for_level(level)
    if job is None or not slip_seats(profile):
        return tier.pool[_stable_index(profile, tier)]
    pool = slip_seat_pool(profile)
    needs = job_equipment_needs(job)
    # Ties break on pool order, which is stable per driver, so the same load
    # out of the same yard always comes with the same truck.
    return max(pool, key=lambda key: _fit_score(key, needs))


def assignment_reason_text(key: str, job) -> str:
    """Why dispatch put the driver in this particular truck, in plain words."""
    model = TRUCK_CATALOG[key]
    needs_sleeper, needs_heavy, is_turn = job_equipment_needs(job)
    if needs_sleeper and model.cab == CAB_SLEEPER:
        reason = "this one is too far to finish in a shift, so you need the bunk"
    elif needs_heavy and model.spec == SPEC_HEAVY:
        reason = "it is a heavy load and this one has the driveline for it"
    elif is_turn and model.cab == CAB_DAY:
        reason = "it is a turn, so you are in a day cab and back tonight"
    elif model.spec == SPEC_LIGHT:
        reason = "the load is light, so you may as well have the economical one"
    else:
        reason = "it is what the yard has free"
    return f"Dispatch put you in the {model.label} for this run: {reason}."


def fleet_assignment_text(profile) -> str:
    """Spoken description of the current carrier tractor assignment."""
    # The active key, not a fresh assignment draw: a slip-seating driver may
    # still be holding the tractor dispatch matched to their last load, and
    # the readout has to name the truck whose condition it describes.
    key = profile.active_truck_key()
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
