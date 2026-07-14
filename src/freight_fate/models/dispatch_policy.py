"""Dispatch autonomy policy: who picks the load and who picks the route.

Freedom to choose freight and routing is earned across the 30-level career
instead of being available from minute one:

- New company hires are *assigned* a load and a route by dispatch. Their real
  agency is accept or decline, and declines go on the service record.
- Senior company drivers pick their own loads from the board, but still run
  the lane dispatch gives them.
- Leased-on owner-operators and independent authority choose both -- that is
  the independence they bought into.

The policy is a pure function of business status and career level, mirroring
``career_level_guidance`` / ``career_objective``. State code consults it to
decide whether to present a menu or auto-assign; it never mutates saves.
"""

from __future__ import annotations

from dataclasses import dataclass

from .business import COMPANY_DRIVER, is_owner_operator

# Company level where dispatch starts letting the driver pick loads.
SENIOR_LOAD_CHOICE_LEVEL = 8
# Assigned-load refusals a company driver can spend before the next level-up.
NEW_HIRE_DECLINE_BUDGET = 3
# Regional Regulars (level 5+) have earned one more refusal per level band.
REGIONAL_REGULAR_LEVEL = 5
# Declining an assigned load is remembered: one on-time delivery wins it back.
DECLINE_REPUTATION_PENALTY = 2.0


@dataclass(frozen=True)
class DispatchPolicy:
    assigns_load: bool
    assigns_route: bool
    decline_budget: int


def dispatch_policy(profile) -> DispatchPolicy:
    """The dispatch autonomy band for this profile, derived from saves as-is."""
    status = getattr(profile, "business_status", COMPANY_DRIVER)
    if is_owner_operator(status):
        return DispatchPolicy(assigns_load=False, assigns_route=False, decline_budget=0)
    level = int(getattr(profile.career, "level", 1))
    budget = NEW_HIRE_DECLINE_BUDGET + (1 if level >= REGIONAL_REGULAR_LEVEL else 0)
    return DispatchPolicy(
        assigns_load=level < SENIOR_LOAD_CHOICE_LEVEL,
        assigns_route=True,
        decline_budget=budget,
    )


def declines_remaining(profile) -> int:
    """Assigned-load refusals left before dispatch stops offering alternatives."""
    budget = dispatch_policy(profile).decline_budget
    used = int(getattr(profile.career, "dispatch_declines_used", 0))
    return max(0, budget - used)
