"""Hard integrity invariants a loadable profile must satisfy.

This is the client half of the shared-profile integrity design
(docs/profile-invariants.md is the maintained list; this module is its
executable mirror). The server's validation gate owns the *plausibility*
heuristics -- money against career history, XP against miles -- because
those rules tighten over time and always know the current content set.
The client enforces only the invariants that are true in every version of
the game: ranges, counts, and relations that no honest save can break.

Version tolerance is deliberate: a save written by a newer build may own
a truck, trailer, or buff this build has never heard of, and that is the
validator-version gate's problem, not grounds for rejection here. Unknown
catalog KEYS pass; impossible VALUES do not.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models.profile import Profile
from .models.trucks import TANK_EXTRA_GAL, TRUCK_CATALOG, UPGRADE_CATALOG

# Structural ceilings, far above anything an honest career reaches; these
# exist to reject NaN/absurd numbers, not to judge progress (the server's
# plausibility rules do that with real curves).
MONEY_FLOOR = -1_000_000.0
MONEY_CEILING = 1_000_000_000.0
XP_CEILING = 100_000_000.0
ADVANCE_CEILING = 1_000_000.0

# The roomiest tank the game can build: biggest catalog tank plus the
# long-range upgrade. A record claiming more diesel than that is edited.
_MAX_FUEL_GAL = max(m.specs.fuel_tank_gal for m in TRUCK_CATALOG.values()) + TANK_EXTRA_GAL


@dataclass(frozen=True)
class Violation:
    code: str  # stable machine label, for tests and server logs
    detail: str  # plain language, safe to speak

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"{self.code}: {self.detail}"


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _check_range(
    out: list[Violation], code: str, label: str, value: object, low: float, high: float
) -> None:
    if not _finite(value) or not (low <= float(value) <= high):
        out.append(Violation(code, f"{label} is outside the possible range."))


def check_profile_invariants(profile: Profile) -> list[Violation]:
    """Every hard invariant the profile breaks, empty when it is sound."""
    out: list[Violation] = []
    _check_range(out, "money", "The bank balance", profile.money, MONEY_FLOOR, MONEY_CEILING)
    _check_range(out, "fatigue", "Fatigue", profile.fatigue, 0.0, 100.0)
    _check_range(out, "road_grime", "Road grime", profile.road_grime_pct, 0.0, 100.0)
    _check_range(out, "pay_advance", "The pay advance", profile.pay_advance, 0.0, ADVANCE_CEILING)
    _check_range(out, "damage", "Truck damage", profile.truck_damage_pct, 0.0, 100.0)
    _check_range(out, "tire_wear", "Tire wear", profile.tire_wear_pct, 0.0, 100.0)
    if not _finite(profile.truck_fuel_gal) or not (0.0 <= profile.truck_fuel_gal <= _MAX_FUEL_GAL):
        out.append(Violation("fuel_range", "The truck carries an impossible amount of fuel."))

    career = profile.career
    _check_range(out, "xp", "Career experience", career.xp, 0.0, XP_CEILING)
    _check_range(out, "reputation", "Reputation", career.reputation, 0.0, 100.0)
    for code, label, value in (
        ("deliveries", "The delivery count", career.deliveries),
        ("on_time_deliveries", "The on-time delivery count", career.on_time_deliveries),
    ):
        if not isinstance(value, int) or value < 0:
            out.append(Violation(code, f"{label} is not a possible count."))
    if not _finite(career.total_miles) or career.total_miles < 0:
        out.append(Violation("total_miles", "The career mileage is not possible."))
    if not _finite(career.total_earnings) or career.total_earnings < 0:
        out.append(Violation("total_earnings", "The career earnings are not possible."))
    if (
        isinstance(career.deliveries, int)
        and isinstance(career.on_time_deliveries, int)
        and career.on_time_deliveries > career.deliveries >= 0
    ):
        out.append(
            Violation("on_time_exceeds", "More on-time deliveries than deliveries driven.")
        )

    if len(profile.achievements) != len(set(profile.achievements)):
        out.append(Violation("achievement_dupes", "The same achievement recorded twice."))

    for key, tier in profile.upgrades.items():
        if not isinstance(tier, int) or tier < 1:
            out.append(Violation("upgrade_tier", "An upgrade tier that is not possible."))
            continue
        upgrade = UPGRADE_CATALOG.get(key)
        # Unknown upgrade keys pass (a newer build may have added one); a
        # KNOWN upgrade past its top tier can only be an edit.
        if upgrade is not None and tier > upgrade.max_tier:
            out.append(Violation("upgrade_tier", "An upgrade pushed past its top tier."))

    return out


def spoken_rejection(violations: list[Violation]) -> str:
    """One plain sentence for the speech layer when an import is refused."""
    if not violations:
        return ""
    return (
        "This profile fails the game's integrity checks and was not "
        f"loaded. First problem: {violations[0].detail}"
    )
