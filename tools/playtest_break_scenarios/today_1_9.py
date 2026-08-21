"""The 1.9 tester-reported fixes, driven the way the reports were written.

Each of these exists because a tester found something by playing badly or
oddly, and the fix that followed made a promise. A promise in a changelog is
worth what the next change leaves of it, so these drive the promise rather
than the code path: what does the driver end up with, and does the game's own
speech agree with the ledger.
"""

from __future__ import annotations

from playtest_break import Rig, _outcome, scenario


def _abandon(rig):
    """Walk the real confirmation state, exactly as the pause menu does."""
    from freight_fate.states.driving_pause_states import (
        AbandonJobConfirmationState,
        PauseMenuState,
    )

    ctx = rig.ctx
    ctx.push_state(rig.d)
    ctx.push_state(PauseMenuState(ctx, rig.d))
    confirm = AbandonJobConfirmationState(ctx, rig.d)
    ctx.push_state(confirm)
    confirm.announce_entry()
    confirm._confirm()


@scenario(
    "abandon_an_empty_run_costs_nothing",
    "Shane's bobtail turnaround: no load means no contract, so calling it off can cost no money.",
)
def _abandon_an_empty_run_costs_nothing():
    """Shane P., 2026-08-20: turning back from an empty reposition was fined.

    Three shapes of the same menu item, and the whole fix is that they are
    priced differently: a loaded job breaches a paying contract (500 dollars
    and 5 reputation), a self-serve bobtail breaches nothing at all, and a
    dispatch-assigned reposition costs standing but not money. The failure
    worth catching is the wrong branch being taken -- which reads to a
    player as being fined for giving back an empty trailer.
    """
    findings: list[str] = []

    for label, bobtail, assigned, want_money, want_rep in (
        ("self-serve bobtail", True, False, 0.0, 0.0),
        ("assigned reposition", True, True, 0.0, 3.0),
        ("loaded job", False, False, 500.0, 5.0),
    ):
        rig = Rig()
        try:
            p = rig.ctx.profile
            rig.d.job.bobtail = bobtail
            rig.d.job.assigned = assigned
            rig.d.trip.position_mi = rig.d.trip.total_miles * 0.5
            money_before, rep_before = p.money, p.career.reputation
            hours_before = p.game_hours

            _abandon(rig)

            lost = money_before - p.money
            rep_lost = rep_before - p.career.reputation
            if abs(lost - want_money) > 0.01:
                findings.append(
                    f"{label}: abandoning cost {lost:,.2f} dollars, expected {want_money:,.2f}"
                )
            if abs(rep_lost - want_rep) > 0.01:
                findings.append(
                    f"{label}: abandoning cost {rep_lost:.1f} reputation, expected {want_rep:.1f}"
                )
            # The hours already driven happened whatever the freight was.
            if p.game_hours < hours_before:
                findings.append(f"{label}: abandoning wound the career clock BACKWARDS")

            # And the confirmation has to describe the branch it will take.
            said = " ".join(rig.transcript)
            if want_money > 0.0 and "five hundred" not in said:
                findings.append(f"{label}: charges 500 without warning the driver first")
            if want_money == 0.0 and "five hundred" in said:
                findings.append(f"{label}: promised a 500 dollar penalty it does not charge")
        finally:
            rig.close()

    return _outcome(
        "abandon_an_empty_run_costs_nothing",
        None,
        findings,
        "empty runs cost nothing, an assignment costs standing, a load costs 500 and 5",
    )


@scenario(
    "jake_stays_off_where_it_does_not_belong",
    "Brandon's climb report: the retarder holds a load back downhill and does nothing else.",
)
def _jake_stays_off_where_it_does_not_belong():
    """Two places the engine brake must never raise itself.

    Brandon, 2026-08-20: cruise reached for the jake on a CLIMB, where the
    hill was about to take that speed for free. The same week's fix stopped
    it on soaked level pavement, where no real driver would allow it. Both
    are the same rule -- the retarder exists to hold a load back on a
    downgrade, and slowing anywhere else is the service brakes' job -- so
    both are checked here against the real cruise controller.
    """
    rig = Rig()
    findings: list[str] = []
    try:
        d, t = rig.d, rig.d.truck
        pygame = rig.pygame
        rig.prepare(speed_mph=62.0)
        rig.press(pygame.K_k)  # cruise on, holding this speed

        # A sustained climb, with the truck over its set speed: the shape
        # that used to reach for the retarder.
        d.trip.grade_at = lambda mi: 0.05
        t.grade = 0.05
        for climbed in range(1, 1801):
            t.grade = 0.05
            rig.step(1)
            if t.engine_brake_stage > 0:
                findings.append(
                    f"the jake came up on a 5 percent CLIMB after {climbed} frames "
                    f"at {t.speed_mph:.0f} mph"
                )
                break

        # Slick, level pavement. Same demand to lose speed, and the drums
        # are the only right answer.
        d.trip.grade_at = lambda mi: 0.0
        t.grade = 0.0
        t.engine_brake_stage = 0
        d.weather.current = rig.WeatherKind.RAIN
        for _ in range(1800):
            t.grade = 0.0
            rig.step(1)
            if t.engine_brake_stage > 0:
                findings.append(f"the jake came up on wet LEVEL road at {t.speed_mph:.0f} mph")
                break
        return _outcome(
            "jake_stays_off_where_it_does_not_belong",
            rig,
            findings,
            "the retarder stayed down on a climb and on wet level road",
        )
    finally:
        rig.close()


@scenario(
    "named_hazards_keep_their_frequency",
    "Brandon's naming asks: debris and animals say what they are, and are no more common than before.",
)
def _named_hazards_keep_their_frequency():
    """Splitting one hazard into six is a frequency change unless it is not.

    Brandon asked what kind of debris and what kind of animal, 2026-08-20,
    and the answer was to replace one generic entry with a family of named
    ones. That is arithmetic: the family's weights have to sum to what the
    single entry carried, or the split quietly makes debris commoner and the
    road busier than it was. The comments in trip_models state the totals
    the split was built to preserve -- 1.2 for debris, 0.7 for the
    nationwide animals -- so this checks the code against its own promise.

    Nothing here drives; it is a table with an invariant, and the invariant
    is the sort that survives review and dies to the next edit.
    """
    from freight_fate.sim.trip_models import HAZARDS

    findings: list[str] = []

    debris_family = {
        "a ladder fallen from a truck in the lane",
        "loose lumber dropped across the lane",
        "a mattress lying in the lane",
        "spilled cargo boxes across the lane",
        "a shredded truck tarp in the lane",
        "debris on the road",
    }
    animal_family = {
        "a dog loose on the road",
        "a coyote crossing the road",
        "loose livestock on the road",
        "a raccoon in the lane",
        "an animal on the road",
    }
    by_text = {h.text: h for h in HAZARDS}

    for label, family, expected, generic in (
        ("debris", debris_family, 1.2, "debris on the road"),
        ("nationwide animals", animal_family, 0.7, "an animal on the road"),
    ):
        missing = sorted(family - by_text.keys())
        if missing:
            findings.append(f"{label}: these entries are gone from the table: {missing}")
            continue
        total = sum(by_text[text].weight for text in family)
        if abs(total - expected) > 0.001:
            findings.append(
                f"{label} now weigh {total:.3f} against the {expected} the split promised "
                "to preserve; the road got busier without anyone deciding to"
            )
        # The anonymous fallback is meant to be the rare unidentifiable one,
        # not the common case wearing a family as cover.
        share = by_text[generic].weight / total if total else 1.0
        if share > 0.2:
            findings.append(
                f"{label}: the unnamed fallback is {share:.0%} of the family, "
                "so 'what is it?' still usually has no answer"
            )

    # And the contract the naming exists for: a hazard the driver has to
    # clear must be nameable when they clear it.
    for hazard in HAZARDS:
        if (hazard.dodgeable or hazard.animal) and not hazard.name:
            findings.append(f"hazard {hazard.text!r} has no name to clear it by")

    return _outcome(
        "named_hazards_keep_their_frequency",
        None,
        findings,
        "debris and animals are named, and exactly as common as they were",
    )


@scenario(
    "weather_cap_releases_when_the_sky_does",
    "Fight the storm cap with the cruise key, then clear the sky: the cap must hold, then let go.",
)
def _weather_cap_releases_when_the_sky_does():
    """Brandon's weather-cruise ask, driven by somebody arguing with it.

    Two failures a clean unit test does not reach. First, a driver who
    simply refuses the cap -- holding the cruise-up key through a
    thunderstorm -- must not be able to ratchet past the safe speed; if
    they could, the cap is advice with extra steps. Second, and worse, a
    cap that fails to RELEASE leaves the truck governed on a dry road with
    nothing to explain it, which is indistinguishable from a broken speed
    keeper. The promise is explicit: clear-day driving is untouched.
    """
    rig = Rig()
    findings: list[str] = []
    try:
        d, t = rig.d, rig.d.truck
        pygame = rig.pygame
        rig.prepare(speed_mph=68.0)
        rig.press(pygame.K_k)  # cruise on around 68

        d.weather.current = rig.WeatherKind.THUNDERSTORM
        rig.step(600)
        safe = d.weather.effects.safe_speed_mph
        if safe >= 68.0:
            return _outcome(
                "weather_cap_releases_when_the_sky_does",
                rig,
                findings,
                f"this storm's safe speed is {safe:.0f}, no cap to test below 68",
            )

        # Argue with it: twenty presses of cruise-up in the storm, on an
        # empty road so the only thing holding the truck down is the cap.
        top = 0.0
        for _ in range(20):
            d.trip.traffic_manager.vehicles = []
            d.trip.traffic_pressures = []
            rig.press(pygame.K_EQUALS)
            rig.step(30)
            top = max(top, t.speed_mph)
        if top > safe + 4.0:
            findings.append(
                f"holding the cruise-up key through the storm reached {top:.0f} mph "
                f"against a safe speed of {safe:.0f}"
            )
        if not rig.said("easing to"):
            findings.append("the storm cap was applied with nothing said about it")

        # Now the sky clears. The cap has to let go on its own.
        #
        # Judged on a road with nothing else on it: the first version of this
        # ran into a hazard, read the resulting near-stop as a cap that never
        # released, and reported a bug that was a braking event. A stopped
        # truck and a governed truck look identical from the speedometer, so
        # the traffic has to be gone before the question means anything.
        d.weather.current = rig.WeatherKind.CLEAR
        recovered = 0.0
        for _ in range(240):
            d.trip.traffic_manager.vehicles = []
            d.trip.traffic_pressures = []
            rig.step(25)
            recovered = max(recovered, t.speed_mph)
            if recovered > safe + 5.0:
                break

        clear_safe = d.weather.effects.safe_speed_mph
        if clear_safe < 68.0:
            findings.append(f"clear weather still reports a safe speed of {clear_safe:.0f}")
        elif recovered < safe + 5.0:
            findings.append(
                f"the sky cleared and the truck never got above {recovered:.0f} mph, "
                f"about the storm's {safe:.0f}; the cap looks stuck"
            )
        return _outcome(
            "weather_cap_releases_when_the_sky_does",
            rig,
            findings,
            f"the cap held at {safe:.0f} against twenty presses, then let go when it cleared",
        )
    finally:
        rig.close()
