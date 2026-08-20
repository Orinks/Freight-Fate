"""Enforcement guidance under deliberate mis-play.

Tester Jerry's weigh-station report (2026-08-12): the open-scale announcement
said "press T", T at speed planned a sleep stop past the scale, X then armed
that truck stop's exit, and following both spoken instructions crossed the
scale unarmed at speed straight into a bypass pull-over -- with the exit
assist still steering for the truck-stop ramp under the trooper's lights.
This family drives the fixed contract end to end with the real driving state.
"""

from __future__ import annotations

from playtest_break import Rig, _outcome, scenario

SCALE_MI = 4.0
TRUCKSTOP_MI = 5.0


def _inject_open_scale(trip):
    """One open scale with a sleep-capable travel center just past it."""
    from freight_fate.sim.enforcement_posts import (
        KIND_FIXED_SCALE,
        METHOD_SCALE_SCREEN,
        EnforcementPost,
    )
    from freight_fate.sim.trip_models import RoadStop

    scale = RoadStop(
        "Hamburg Scale",
        SCALE_MI,
        "weigh_station",
        ("inspect",),
        parking="none",
    )
    truckstop = RoadStop(
        "Blue Beacon Travel Plaza",
        TRUCKSTOP_MI,
        "travel_center",
        ("park", "save", "fuel", "food", "break", "sleep"),
        parking="confirmed",
        exit_label="exit 55",
    )
    trip.stops = [scale, truckstop]
    trip.posts = [
        EnforcementPost(
            at_mi=SCALE_MI,
            kind=KIND_FIXED_SCALE,
            leg_index=0,
            method=METHOD_SCALE_SCREEN,
            reach_mi=1.0,
            staffed=True,
            anchor=scale.key,
        )
    ]
    return scale, truckstop


@scenario(
    "scale_check_in_guidance",
    "Follow the scale announcement literally -- T mid-warning, then X: both must serve the scale.",
)
def _scale_check_in_guidance():
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        pygame = rig.pygame
        scale, truckstop = _inject_open_scale(d.trip)
        rig.prepare(speed_mph=54.0)
        rig.press(pygame.K_k)  # cruise at the limit: the scale is the only demand

        ran = rig.step(20000, until=lambda: rig.said("Open weigh station") > 0)
        if not rig.said("Open weigh station"):
            findings.append(f"no open-scale announcement in {ran} frames")
            return _outcome("scale_check_in_guidance", rig, findings, "")
        notice = rig.lines_with("Open weigh station")[0]
        if "press T for inspection check-in" in notice:
            findings.append("the announcement still teaches the rest key at speed")
        if "ignal for the scale exit" not in notice:  # capital-S since the mainline-crawl rewording
            findings.append("the announcement never teaches the exit key")

        # Jerry's press: T immediately, mid-announcement in real audio.
        rig.press(pygame.K_t)
        if rig.said("Planned sleep stop selected"):
            findings.append(
                "T mid scale warning planned a sleep stop past the scale instead of deferring"
            )
        if not rig.said("Weigh station first"):
            findings.append("T mid scale warning never said the scale comes first")

        # Then X, following the announcement's exit instruction. Full lane
        # keeping pins the exit-lane mechanics out of the way: this scenario
        # is about WHICH exit the press serves, not lane work.
        rig.ctx.settings.lane_keeping = "full"
        rig.press(pygame.K_x)
        if d._exit_stop is None or not d._exit_signal_on:
            findings.append("X after the scale warning armed no exit at all")
        elif d._exit_stop.key != scale.key:
            findings.append(
                f"X armed the exit for {d._exit_stop.name}, not the scale's inspection lane"
            )

        # Ride the capped cruise down to the gore. Compliance must end on the
        # scale's own ramp with no enforcement lights anywhere in the run.
        rig.step(
            20000,
            until=lambda: (
                d._ramp_mi is not None
                or d._pull_over is not None
                or d.trip.position_mi > SCALE_MI + 0.3
            ),
        )
        if d._pull_over is not None or rig.said("Scale bypass enforcement"):
            findings.append("following both spoken instructions still ended in a bypass pull-over")
        if d._ramp_stop is None or d._ramp_stop.key != scale.key:
            findings.append(
                "the truck never ended up on the scale's own ramp "
                f"(position {d.trip.position_mi:.2f}, {d.truck.speed_mph:.0f} mph)"
            )
        return _outcome(
            "scale_check_in_guidance",
            rig,
            findings,
            "T deferred to the scale, X armed the inspection lane, no bypass charge",
        )
    finally:
        rig.close()


@scenario(
    "scale_pull_over_stands_down_exit",
    "Blow past the scale with a truck-stop exit armed: the pull-over must own the road.",
)
def _scale_pull_over_stands_down_exit():
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        scale, truckstop = _inject_open_scale(d.trip)
        rig.prepare(speed_mph=54.0)
        # Recreate the pre-fix wreckage by force: exit armed for the truck
        # stop (not the scale), then blow the scale at speed.
        d.trip.position_mi = SCALE_MI - 0.1
        d._enforcement_prev_mi = d.trip.position_mi
        d._exit_stop = truckstop
        d._exit_signal_on = True
        d._cruise_exit_mph = 40.0
        rig.step(60, until=lambda: d._pull_over is not None)
        if d._pull_over is None:
            findings.append("an unarmed 54 mph scale crossing was never charged")
        if d._exit_signal_on or d._exit_stop is not None:
            findings.append(
                "the armed truck-stop exit kept announcing and steering during the pull-over"
            )
        if d._cruise_exit_mph is not None:
            findings.append("the ramp cruise cap survived into the trooper stop")
        return _outcome(
            "scale_pull_over_stands_down_exit",
            rig,
            findings,
            "the pull-over stood the armed exit down; one demand on the driver",
        )
    finally:
        rig.close()
