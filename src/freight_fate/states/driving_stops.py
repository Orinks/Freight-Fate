"""Where the stop cues live, derived from what the truck can actually do.

Every stop cue in the game used to be a fixed distance: the stop-bar tick
started at three hundred feet, the held tone began at sixty, and the
route-transition assist mapped its pedal against a nominal three metres per
second squared. Those numbers were right for a dry van on level tarmac and
quietly wrong for everything else -- hot brakes, worn shoes, ice, a downgrade,
a partly filled tank running forward under braking.

That mattered more here than it would in a game you can look at. A blind
driver's entire model of *where do I stop* is the tick's rate accelerating
from one and a tenth seconds to a seventh of a second. Leave the range fixed
and the cue says exactly what it has always said while the truck needs half as
much road again -- so the driver does precisely what the instrument told them
and puts the tractor into the intersection. That is not difficulty. It is an
ambush built into the game's most trusted affordance.

So the geometry is computed from ``sim.vehicle``'s stopping distance instead,
which already knows about fade, wear, load, grip and grade, and now about
liquid surge as well. Every original constant survives as a floor: a truck
that can stop shorter than the old numbers hears the bar exactly where it
always did, and nothing changes for the freight that was already fine.
"""

from __future__ import annotations

from .driving_core import (
    RAMP_ASSIST_FULL_DECEL_MPS2,
    RAMP_BAR_REACTION_S,
    RAMP_BAR_SOLID_MI,
    RAMP_BAR_TICK_RANGE_MI,
)


def bar_tick_range_mi(truck) -> float:
    """How far out the stop-bar tick starts, for this truck as it is now.

    Carries a reaction allowance as well as the stopping distance: the bar is
    the one place where the cue *is* the instrument, so its range has to pay
    for the listening too.
    """
    needed = truck.stopping_distance_mi(reaction_s=RAMP_BAR_REACTION_S) + RAMP_BAR_SOLID_MI
    return max(RAMP_BAR_TICK_RANGE_MI, needed)


def bar_solid_zone_mi(truck) -> float:
    """Where the ticks fuse into the held tone: the last of the leeway.

    Sixty feet is an owner spec written into the manual, so unlike the tick
    range this does not simply become "whatever this truck needs" -- deriving
    it from speed would move the held tone for every dry van on a brisk
    approach, and a continuous tone arriving earlier for everybody is exactly
    the sensory load this game spends carefully.

    It extends by one thing only: the extra road the *liquid* is asking for.
    That is zero for every other load, so nothing else changes, and it is the
    one case where sixty feet is a promise the truck cannot keep -- the wave
    is still coming when the driver thinks the stop is made.
    """
    return RAMP_BAR_SOLID_MI + truck.surge_stopping_penalty_mi()


def assist_full_decel_mps2(truck) -> float:
    """Denominator for mapping needed deceleration onto brake application.

    Against a fixed nominal figure the assist under-brakes every truck that
    cannot make that figure -- which is exactly the set of trucks that need the
    pedal hardest. Taking the lower of nominal and achievable means the assist
    can only ever press harder than it used to, never softer, so no load that
    was already being handled correctly sees any change.
    """
    return max(0.5, min(RAMP_ASSIST_FULL_DECEL_MPS2, truck.full_service_decel_mps2()))
