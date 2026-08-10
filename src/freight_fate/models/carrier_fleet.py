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
    """The tier a career level makes a driver *eligible* for.

    Eligibility, not entitlement. What the yard actually hands over is
    ``assigned_fleet_tier``, which is this capped by where the driver stands
    with the carrier. Kept a pure function of level because the cloud-save
    validator's exported fleet-tier table is keyed on exactly that.
    """
    tier = FLEET_TIERS[0]
    for candidate in FLEET_TIERS:
        if int(level) >= candidate.min_level:
            tier = candidate
    return tier


# A carrier gives its best iron to the drivers it wants to keep, and a driver
# on a final warning does not get the new truck. So the level says what a
# driver has earned the right to and dispatch trust says what the yard is
# actually willing to put in their hands; the assignment is the lower of the
# two. A driver in full trust is capped by nothing and never touches any of
# this.
STANDING_TIER_CAP = {
    "full": len(FLEET_TIERS) - 1,
    "guarded": 2,  # long-haul fleet: still real equipment, not the flagships
    "poor": 1,  # regional fleet
    "last chance": 0,  # the yard's spares
}


def _career_level(profile) -> int:
    return int(getattr(getattr(profile, "career", None), "level", 1))


def eligible_fleet_tier(profile) -> FleetTier:
    """What this driver's level has earned the right to."""
    return fleet_tier_for_level(_career_level(profile))


def assigned_fleet_tier(profile) -> FleetTier:
    """What the yard will actually hand this driver: level capped by standing."""
    from .enforcement import standing_band

    earned = eligible_fleet_tier(profile)
    cap = STANDING_TIER_CAP.get(standing_band(profile), len(FLEET_TIERS) - 1)
    return FLEET_TIERS[min(FLEET_TIERS.index(earned), cap)]


def equipment_held_back(profile) -> bool:
    """Whether standing is holding this driver below the iron their level earns."""
    from .business import is_owner_operator

    if is_owner_operator(getattr(profile, "business_status", "")):
        return False  # their tractor is their own; no yard decides it
    return FLEET_TIERS.index(assigned_fleet_tier(profile)) < FLEET_TIERS.index(
        eligible_fleet_tier(profile)
    )


def _hold_cause_phrases(profile) -> tuple[str, str]:
    """(why the iron is held, what clears it), both in plain words."""
    from . import enforcement
    from .solvency import debt_owed, money_text

    cause = enforcement.standing_cause(profile)
    if cause == enforcement.CAUSE_DEBT:
        return f"you owe {money_text(debt_owed(profile))}", "Clear it"
    if cause == enforcement.CAUSE_LICENCE:
        clears = enforcement.clears_text(profile)
        when = f" until it clears {clears}" if clears else ""
        return f"your CDL is suspended{when}", "Get it back"
    return "your dispatch trust is down", "Bring it back up with clean on-time runs"


def equipment_hold_text(profile, terse: bool = False) -> str:
    """Why the yard handed over a lesser truck than the level earns.

    Names three things every time, because this is the most frequent moment in
    the whole change and the easiest to read as a bug: the tractor the level
    would have earned, the single reason in the driver's own numbers, and the
    exact thing that gives it back.
    """
    if not equipment_held_back(profile):
        return ""
    earned = eligible_fleet_tier(profile)
    reason, clears = _hold_cause_phrases(profile)
    if terse:
        return f"Held back from the {earned.label}: {reason}."
    return (
        f"Your level earns a tractor from the {earned.label}, but the yard "
        f"keeps its best iron for drivers in good standing, and {reason}. "
        f"{clears} and the {earned.label} comes back to you."
    )


def equipment_hold_clause(profile) -> str:
    """The one-sentence version, for a status line that already gave the cause."""
    if not equipment_held_back(profile):
        return ""
    return (
        f"The yard is also holding your equipment back: your tractor comes "
        f"from the {assigned_fleet_tier(profile).label}, not the "
        f"{eligible_fleet_tier(profile).label} your level earns."
    )


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
    tier = assigned_fleet_tier(profile)
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
    tier = assigned_fleet_tier(profile)
    if job is None or not slip_seats(profile):
        return tier.pool[_stable_index(profile, tier)]
    pool = slip_seat_pool(profile)
    needs = job_equipment_needs(job)
    # Ties break on pool order, which is stable per driver, so the same load
    # out of the same yard always comes with the same truck.
    return max(pool, key=lambda key: _fit_score(key, needs))


def assignment_reason_text(key: str, job, profile=None, terse: bool = False) -> str:
    """Why dispatch put the driver in this particular truck, in plain words.

    With a profile, a truck the yard is holding back says so here rather than
    leaving the driver to wonder why their level stopped buying them anything.
    """
    model = TRUCK_CATALOG[key]
    if profile is not None and equipment_held_back(profile):
        hold = equipment_hold_text(profile, terse=terse)
        if terse:
            return f"{model.label.capitalize()}. {hold}"
        return f"Dispatch has you in the {model.label} for this run. {hold}"
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
    tier = assigned_fleet_tier(profile)
    line = f"Dispatch has you in a {model.label} from the {tier.label}: {model.description}"
    hold = equipment_hold_text(profile)
    return f"{line} {hold}" if hold else line


def fleet_upgrade_announcement(profile) -> str:
    """Spoken hand-over line when a promotion changes the assigned tractor."""
    key = assigned_truck_key(profile)
    model = TRUCK_CATALOG[key]
    return (
        f"Dispatch upgraded your assigned tractor. You are now running a "
        f"{model.label}: {model.description} The yard handed it over "
        "fueled, serviced, and washed."
    )


def withheld_promotion_text(profile) -> str:
    """What a level-up says when standing keeps the better tractor in the yard.

    The tractor does not change hands, so nothing about the driver's current
    truck changes either -- no fresh fuel, no reset wear, no wash. Handing a
    lesser truck over spotless would tell the player something happened when
    nothing did.
    """
    if not equipment_held_back(profile):
        return ""
    model = TRUCK_CATALOG[profile.active_truck_key()]
    return (
        f"You keep the {model.label} you are in, exactly as it stands. "
        f"{equipment_hold_text(profile)}"
    )


# What a level-up says instead of promising a tractor the yard is not handing
# over. The rest of the rank's unlock still happens, so only the equipment
# half of the promise is corrected.
WITHHELD_UNLOCK_TAIL = "The tractor that comes with it is staying in the yard for now."
