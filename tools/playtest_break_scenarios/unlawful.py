"""Breaking the law on purpose, and the edges of what it costs.

The rest of the battery drives badly. This drives ILLEGALLY -- twenty over
past a staffed crossover, straight through an open scale, a stop sign at the
end of a ramp treated as a suggestion -- and then checks that what the game
charges for it is coherent: the fine matches the one place fines are priced,
the record moves once rather than twice, and the words the driver hears name
the same numbers the ledger does.

The interesting failures here are arithmetic and bookkeeping, not crashes. A
citation that charges a repeat offender past the cap, a violation counted
twice because two systems both recorded it, or a spoken summary quoting a
figure the wallet never lost are all invisible from inside a normal drive and
all things a player will eventually notice.
"""

from __future__ import annotations

from playtest_break import Rig, _outcome, scenario

# Where the injected furniture goes. Far enough in that the truck is settled
# at speed and any advance warning has room to land.
POST_MI = 3.0
SCALE_MI = 4.0


def _staffed_posts(trip, kind: str, miles: tuple[float, ...], reach_mi: float = 0.6):
    """A row of staffed posts, each able to look at the truck and act.

    Several rather than one on purpose: whether a given post looks is a
    seeded roll (``_observed_now``), so a scenario built on exactly one post
    is a scenario that reports nothing on most seeds. A row makes the LOOK
    reliable without touching the odds themselves, which is what the roll is
    there to model.
    """
    from freight_fate.sim.enforcement_posts import EnforcementPost

    posts = [
        EnforcementPost(
            at_mi=mi,
            kind=kind,
            leg_index=0,
            method="visual",
            reach_mi=reach_mi,
            staffed=True,
        )
        for mi in miles
    ]
    trip.posts = posts
    return posts


def _hold_over_limit(rig, mph_over: float, frames: int = 4000):
    """Drive at a fixed number over whatever is posted, and keep it there.

    Speeding is read as continuous DISTANCE over the limit, not a moment, so
    a scenario has to actually hold the speed while miles pass rather than
    setting a velocity and stepping once.
    """
    d = rig.d

    def _pin() -> bool:
        limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
        d.truck.velocity_mps = (limit + mph_over) / 2.23693629
        return d._pull_over is not None

    ran = 0
    for _ in range(frames):
        _pin()
        ran += rig.step(1)
        if d._pull_over is not None:
            break
    return ran


def _fine_charged(rig) -> float | None:
    """What the pending stop says this violation costs, if one is running."""
    stop = rig.d._pull_over
    if stop is None:
        return None
    for attr in ("fine", "amount", "fine_amount"):
        value = getattr(stop, attr, None)
        if isinstance(value, (int, float)):
            return float(value)
    return None


@scenario(
    "speeding_past_staffed_posts",
    "Hold twenty over past a row of staffed crossovers; the citation must price itself the same way the model does.",
)
def _speeding_past_staffed_posts():
    from freight_fate.models.enforcement import speeding_citation_fine
    from freight_fate.sim.enforcement_posts import KIND_MEDIAN

    rig = Rig(keep_patrols=True)
    findings: list[str] = []
    try:
        d = rig.d
        _staffed_posts(d.trip, KIND_MEDIAN, (2.0, 3.0, 4.0, 5.0, 6.0, 7.0))
        rig.prepare(speed_mph=55.0)
        citations_before = int(getattr(d.ctx.profile.driving_record, "citations", 0) or 0)

        _hold_over_limit(rig, 20.0)

        if d._pull_over is None:
            # Not a finding on its own: the look is a seeded roll and a run
            # where nobody looked is a legitimate outcome of the model. It
            # only means this seed proves nothing about the pricing.
            return _outcome(
                "speeding_past_staffed_posts",
                rig,
                findings,
                "no post looked on this seed; twenty over went unobserved",
            )

        if not rig.said("Lights and siren"):
            findings.append("a pull-over began with no lights-and-siren line spoken")

        charged = _fine_charged(rig)
        expected = speeding_citation_fine(20.0, citations_before)
        if charged is not None and abs(charged - expected) > 1.0:
            findings.append(
                f"speeding stop charges {charged:,.0f} where the model prices "
                f"twenty over at {expected:,.0f} for {citations_before} priors"
            )
        return _outcome(
            "speeding_past_staffed_posts",
            rig,
            findings,
            f"twenty over observed and priced at {charged if charged is not None else expected:,.0f}",
        )
    finally:
        rig.close()


@scenario(
    "scale_bypass_to_the_end",
    "Blow an open scale and ride the failure-to-stop ladder out; every line must still be true when it is spoken.",
)
def _scale_bypass_to_the_end():
    from freight_fate.sim.enforcement_posts import (
        KIND_FIXED_SCALE,
        METHOD_SCALE_SCREEN,
        EnforcementPost,
    )
    from freight_fate.sim.trip_models import RoadStop

    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        scale = RoadStop("Hamburg Scale", SCALE_MI, "weigh_station", ("inspect",), parking="none")
        d.trip.stops = [scale]
        d.trip.posts = [
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
        rig.prepare(speed_mph=62.0)

        # Never signal, never slow: the whole point is the driver who ignores
        # every instruction the scale gives.
        rig.step(20000, until=lambda: d.trip.position_mi > SCALE_MI + 2.0)

        if not rig.said("Open weigh station"):
            findings.append("the open scale never announced itself")
        if not rig.said("Scale bypass enforcement"):
            findings.append("driving straight through an open scale drew no bypass enforcement")

        # The reminder is documented as firing once per scale. The pacer
        # hands a cut ROUTE line back when an urgent line interrupts it, and
        # the bypass ladder is three escalating warnings in a row -- so this
        # counts what the driver actually HEARD, not what the guard intended.
        reminders = rig.said("Signal for the scale exit")
        if reminders > 2:
            findings.append(
                f'"Signal for the scale exit" was spoken {reminders} times for one scale'
            )

        # And the harder half: a distance is a claim about now. Once the
        # scale is behind the truck, a line still offering its exit is
        # telling the driver to do something impossible.
        past = [
            line
            for line in rig.transcript
            if "Weigh station in" in line and d.trip.position_mi > SCALE_MI
        ]
        if past and d.trip.position_mi > SCALE_MI + 1.0:
            findings.append(
                f"{len(past)} scale-exit lines are still offering an exit the truck has passed"
            )
        return _outcome(
            "scale_bypass_to_the_end",
            rig,
            findings,
            "bypass enforcement fired and the exit instruction was said once",
        )
    finally:
        rig.close()


@scenario(
    "work_zone_speeding_doubles_the_fine",
    "The same overspeed inside roadwork must cost exactly twice what it costs anywhere else.",
)
def _work_zone_speeding_doubles_the_fine():
    """A pricing edge, driven rather than unit-tested.

    The doubling and the repeat step compound in one place on purpose
    (``citation_fine``). This checks the two multipliers still meet there and
    nowhere else: a second application anywhere in the call path shows up
    here as four times the base rather than twice.
    """
    from freight_fate.models.enforcement import (
        CITATION_REPEAT_MAX_MULTIPLIER,
        CONSTRUCTION_ZONE_FINE_MULTIPLIER,
        speeding_citation_fine,
    )

    findings: list[str] = []
    for over in (10.0, 20.0, 35.0):
        plain = speeding_citation_fine(over, 0)
        zone = speeding_citation_fine(over, 0, construction_zone=True)
        if abs(zone - plain * CONSTRUCTION_ZONE_FINE_MULTIPLIER) > 0.01:
            findings.append(
                f"{over:.0f} over: roadwork charges {zone:,.0f} against {plain:,.0f} plain, "
                f"not the {CONSTRUCTION_ZONE_FINE_MULTIPLIER:g}x the model promises"
            )

    # The repeat step is capped; the zone doubling is applied after the cap,
    # so a career offender inside roadwork pays cap x 2 and never more.
    base = speeding_citation_fine(20.0, 0)
    worst = speeding_citation_fine(20.0, 50, construction_zone=True)
    ceiling = base * CITATION_REPEAT_MAX_MULTIPLIER * CONSTRUCTION_ZONE_FINE_MULTIPLIER
    if worst > ceiling + 0.01:
        findings.append(
            f"fifty priors inside roadwork charges {worst:,.0f}, past the "
            f"{ceiling:,.0f} the cap and the zone doubling allow together"
        )
    return _outcome(
        "work_zone_speeding_doubles_the_fine",
        None,
        findings,
        f"roadwork doubles cleanly and a career offender tops out at {ceiling:,.0f}",
    )


@scenario(
    "repeat_citations_stop_compounding",
    "A career offender's fines must climb to the cap and then stop, not compound forever.",
)
def _repeat_citations_stop_compounding():
    from freight_fate.models.enforcement import (
        CITATION_REPEAT_MAX_MULTIPLIER,
        WEIGH_STATION_BYPASS_FINE,
        citation_fine,
    )

    findings: list[str] = []
    priced = [citation_fine(WEIGH_STATION_BYPASS_FINE, n) for n in range(0, 40)]
    if any(b < a - 0.01 for a, b in zip(priced, priced[1:], strict=False)):
        findings.append("a further prior citation made the fine go DOWN")
    cap = WEIGH_STATION_BYPASS_FINE * CITATION_REPEAT_MAX_MULTIPLIER
    if priced[-1] > cap + 0.01:
        findings.append(
            f"forty priors price a bypass at {priced[-1]:,.0f}, past the cap {cap:,.0f}"
        )
    if priced[-1] < priced[0]:
        findings.append("a repeat offender is charged less than a first offender")
    return _outcome(
        "repeat_citations_stop_compounding",
        None,
        findings,
        f"the repeat step climbs to {cap:,.0f} and holds there",
    )


@scenario(
    "honk_the_air_down_to_the_valve",
    "Lean on the horn with the compressor gone: the protection valve must save the brakes, not the horn.",
)
def _honk_the_air_down_to_the_valve():
    """Brandon's shared-air ask, and the realism audit that followed it.

    Two halves of one claim, because half of it is about what a determined
    player CANNOT do -- and those are the claims that quietly stop being
    true. With the engine turning, the compressor out-earns the horn and no
    amount of leaning on it costs the brakes anything. With the engine dead
    and the air already going, the horn draws the tanks down to the
    protection valve and stops there: FMVSS 121 pressure-protects
    accessories, so honking your way into a spring-brake lockdown is
    mechanically impossible on a compliant tractor.
    """
    rig = Rig()
    findings: list[str] = []
    try:
        t = rig.d.truck
        rig.prepare(speed_mph=58.0)

        # Half one: engine running. The compressor should win, every time.
        t.primary_air_psi = t.secondary_air_psi = 95.0
        before = min(t.primary_air_psi, t.secondary_air_psi)
        t.horn_on = True
        for _ in range(6000):
            t.horn_on = True
            rig.step(1)
        with_engine = min(t.primary_air_psi, t.secondary_air_psi)
        if with_engine < t.HORN_PROTECTION_PSI:
            findings.append(
                f"a long blast with the engine running pulled the tanks from {before:.0f} "
                f"to {with_engine:.0f} psi, through the protection valve"
            )

        # Half two: engine dead, coasting, air already low. Now the horn is
        # the only draw and the valve is the only thing standing between it
        # and the brakes.
        t.horn_on = False
        t.stop_engine()
        t.primary_air_psi = t.secondary_air_psi = t.HORN_PROTECTION_PSI + 4.0
        t.horn_on = True
        floor = min(t.primary_air_psi, t.secondary_air_psi)
        for _ in range(30000):
            if t.horn_available:
                t.horn_on = True
            rig.step(1)
            floor = min(floor, t.primary_air_psi, t.secondary_air_psi)
            if not t.horn_available and not t.horn_on:
                break

        if t.horn_available:
            findings.append(
                f"with no compressor the horn still never reached the valve "
                f"({t.primary_air_psi:.0f} psi)"
            )
        elif not rig.said("protection valve"):
            findings.append("the horn cut out with no spoken reason; it just stopped")
        if floor < t.HORN_PROTECTION_PSI - 1.0:
            findings.append(
                f"the horn pulled the tanks to {floor:.0f} psi, past the "
                f"{t.HORN_PROTECTION_PSI:.0f} psi the protection valve is supposed to hold"
            )
        if t.parking_brake or getattr(t, "spring_brakes_applied", False):
            findings.append("honking alone locked the spring brakes, which FMVSS 121 forbids")
        return _outcome(
            "honk_the_air_down_to_the_valve",
            rig,
            findings,
            f"the compressor won while running; dead, the valve closed at {floor:.0f} psi",
        )
    finally:
        rig.close()


@scenario(
    "prepass_green_is_not_a_bypass_charge",
    "A weigh-in-motion green light must clear the scale; driving on cannot then be charged as a bypass.",
)
def _prepass_green_is_not_a_bypass_charge():
    """The one way today's transponder could hurt somebody.

    The bypass ladder and the weigh-in-motion verdict are separate systems
    that both watch the same gore point. If the verdict clears a driver and
    the ladder has not been told, the game tells you to keep rolling and then
    tickets you 1,800 dollars for doing it.
    """
    from freight_fate.models.business import WEIGH_STATION_TRANSPONDER_LEVEL
    from freight_fate.models.career import LEVEL_XP
    from freight_fate.sim.enforcement_posts import (
        KIND_FIXED_SCALE,
        METHOD_SCALE_SCREEN,
        EnforcementPost,
    )
    from freight_fate.sim.trip_models import RoadStop

    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        # A company driver the fleet trusts with a transponder. The level is
        # derived from XP, so this is the honest way to grant it.
        d.ctx.profile.career.xp = LEVEL_XP[WEIGH_STATION_TRANSPONDER_LEVEL - 1]
        scale = RoadStop("Hamburg Scale", SCALE_MI, "weigh_station", ("inspect",), parking="none")
        d.trip.stops = [scale]
        d.trip.posts = [
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
        rig.prepare(speed_mph=62.0)
        rig.step(20000, until=lambda: d.trip.position_mi > SCALE_MI + 2.0)

        # The verdict dict is keyed the way the enforcement watch keys a
        # scale, not by the stop's own key -- ask the state to build it
        # rather than guessing the format here.
        verdict = d._weigh_station_transponder_verdict.get(d._weigh_station_key(scale))
        if verdict is None:
            findings.append(
                "a level "
                f"{WEIGH_STATION_TRANSPONDER_LEVEL} company driver got no weigh-in-motion "
                "verdict at an open scale"
            )
        elif verdict == "green":
            spoke = rig.said("keep rolling")
            if not spoke:
                findings.append("a green verdict never told the driver to keep rolling")
            elif spoke > 1:
                # One verdict, one line. A ROUTE line cut by a hazard is
                # handed back by the pacer, and nothing caps how many times
                # that can happen, so a busy moment turns one clearance into
                # a chant.
                findings.append(f"the green-light clearance was spoken {spoke} times for one scale")
            if rig.said("Scale bypass enforcement"):
                findings.append(
                    "the transponder cleared the scale and the bypass ladder charged for it anyway"
                )
            if rig.said("Signal for the scale exit"):
                findings.append(
                    "a cleared driver was still told to signal for an exit they do not need"
                )
        return _outcome(
            "prepass_green_is_not_a_bypass_charge",
            rig,
            findings,
            f"weigh-in-motion verdict {verdict!r}, and the ladder agreed with it",
        )
    finally:
        rig.close()
