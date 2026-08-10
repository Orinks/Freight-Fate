"""Shared fixtures for the enforcement layer.

A post is a place with a body and a graded look, so a test that wants to ask
"what happens when an officer sees this" has to build one that is staffed,
already announced, and pointed at the piece of road the test cares about.
Doing that by hand in every test invites the quiet failure where a post is
present but declines to look and the assertion passes for the wrong reason.
"""

from __future__ import annotations

from freight_fate.sim.enforcement_observe import OBSERVE_HOLD_MI
from freight_fate.sim.enforcement_posts import METHOD_BY_KIND, EnforcementPost


def always_observing_post(
    *,
    at_mi: float,
    kind: str = "median_post",
    reach_mi: float = 1.0,
    notice: float = 1.0,
    leg_index: int = 0,
) -> EnforcementPost:
    """A staffed, already-heard post watching ``reach_mi`` up to ``at_mi``."""
    return EnforcementPost(
        at_mi=at_mi,
        kind=kind,
        leg_index=leg_index,
        method=METHOD_BY_KIND[kind],
        reach_mi=reach_mi,
        facing="both",
        staffed=True,
        notice=notice,
        announced=True,
    )


def watch_speed(driving, *, over: float = 20.0, dt: float = 0.1) -> float:
    """Put the truck ``over`` the limit under a watching post, and let it look.

    Runs the two halves in the same order the drive loop does: the watch
    first, so an officer who acts suppresses the silent at-delivery strike,
    then the strike bookkeeping for the speeding nobody saw.

    Returns the posted limit. Seeds the over-limit distance past the
    observation hold directly: the hold is a stretch of road, and driving that
    stretch out frame by frame is not what any of these tests is about.
    """
    from freight_fate.states.driving import SPEEDING_HOLD_S

    driving.trip.position_mi = driving.trip.total_miles / 2.0
    driving._enforcement_prev_mi = driving.trip.position_mi
    limit, _ = driving.trip.speed_limit_at(driving.trip.position_mi)
    driving.truck.velocity_mps = (limit + over) / 2.23694
    driving._over_limit_mi = OBSERVE_HOLD_MI * 2.0
    driving._update_enforcement_watch(dt)
    driving._update_speeding(SPEEDING_HOLD_S + 1.0)
    return limit


def open_scale_post(stop, *, leg_index: int = 0) -> EnforcementPost:
    """An open weigh station standing behind ``stop``.

    Whether a scale is open is settled at trip build from a seeded draw, so a
    test that invents a RoadStop has to say which side of that draw it wants.
    """
    return EnforcementPost(
        at_mi=stop.at_mi,
        kind="fixed_scale",
        leg_index=leg_index,
        method=METHOD_BY_KIND["fixed_scale"],
        reach_mi=0.5,
        facing="with_traffic",
        staffed=True,
        anchor=stop.key,
        announced=True,
    )
