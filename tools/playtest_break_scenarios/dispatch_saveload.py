"""Dispatch board and save/load abuse.

Declining loads until the budget runs dry (and checking the board doesn't
reroll on re-entry), and saving/reloading mid-hazard or mid-traffic-stop to
see whether the consequences survive the round trip.
"""

from __future__ import annotations

from playtest_break import Outcome, Rig, _fresh_data_dir, _outcome, _Shim, scenario


@scenario(
    "dispatch_decline_budget",
    "Decline assigned loads until dispatch runs dry; re-enter the board hunting a reroll.",
)
def _decline_budget():
    _fresh_data_dir()
    import pygame
    from playtest_harness import PlaytestHarness, key_event

    findings: list[str] = []
    with PlaytestHarness(_Shim()) as h:
        from freight_fate.models.dispatch_policy import declines_remaining
        from freight_fate.states.city import CityMenuState, JobBoardState
        from freight_fate.states.main_menu import (
            CareerStartState,
            HomeCityState,
            HomeTerminalState,
            MainMenuState,
            NameEntryState,
        )

        app = h.app
        app.push_state(MainMenuState(app.ctx))
        h._select_current_menu_text("New career")
        assert isinstance(app.state, NameEntryState)
        for ch in "Breaker":
            app.state.handle_event(key_event(ord(ch.lower()), ch))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CareerStartState)
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, HomeTerminalState)
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, HomeCityState)
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityMenuState)
        p = app.ctx.profile
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, JobBoardState)
        if not app.state.assigned_mode:
            findings.append("a brand-new hire was not in assigned-load mode")
        budget = declines_remaining(p)
        declined = 0
        while declined <= budget + 5:
            label = next((item for item in h.menu_labels() if item.startswith("Decline")), None)
            if label is None:
                break
            h.select_menu_item(label)
            declined += 1
        if declined > budget:
            findings.append(
                f"decline budget said {budget} but the board accepted {declined} declines"
            )
        if declines_remaining(p) != max(0, budget - declined):
            findings.append("declines_remaining does not match the declines actually spent")
        jobs_before = [(j.origin, j.destination, round(j.pay)) for j in app.state.jobs]
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, CityMenuState)
        h._select_current_menu_text("Dispatch board")
        assert isinstance(app.state, JobBoardState)
        jobs_after = [(j.origin, j.destination, round(j.pay)) for j in app.state.jobs]
        if jobs_before != jobs_after:
            findings.append(
                "leaving and re-entering the dispatch board rerolled the offers -- "
                "board-reroll farming is open (dispatch_board_cache failed)"
            )
        if any(item.startswith("Decline") for item in h.menu_labels()) and budget > 0:
            findings.append("spent declines came back after re-entering the board")
        verdict = "ODD" if findings else "CLEAN"
        note = (
            findings[0]
            if findings
            else (f"budget of {budget} enforced; board and spent declines survive re-entry")
        )
        return Outcome("dispatch_decline_budget", verdict, note, findings, h.result.transcript)


@scenario(
    "save_scum_enforcement",
    "Save and reload during a traffic stop and a live hazard; do the consequences survive?",
)
def _save_scum():
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        from freight_fate.states.driving import DrivingState

        d.trip.position_mi = 12.0
        rig.prepare(speed_mph=70.0)
        d.speeding_strikes = 3
        d.jake_zone_fines = 2
        d.jake_fines_paid = 450.0
        d.ticket_fines_paid = 150.0
        d.hos.drive(200.0)
        d._begin_pull_over(55.0)
        d._hazard_deadline = 6.0
        deadline_before = d.job.deadline_game_h
        snap = d.snapshot()
        resumed = DrivingState.from_snapshot(rig.ctx, snap)
        if resumed is None:
            findings.append("snapshot failed to round-trip at all")
            return _outcome("save_scum_enforcement", rig, findings, "")
        if d._pull_over is not None and resumed._pull_over is None:
            findings.append(
                "save-and-reload during a traffic stop erases the stop: the trooper, the "
                "ticket, and the felony ladder all vanish -- quit-to-menu is a get-out-of-"
                "jail-free card (pull-over state is not in the snapshot)"
            )
        if resumed._hazard_deadline is None and d._hazard_deadline is not None:
            findings.append(
                "a live hazard warning does not survive save/reload: reload mid-hazard and "
                "the debris is gone without braking"
            )
        if resumed.speeding_strikes != 3:
            findings.append("speeding strikes lost in the snapshot round-trip")
        if resumed.jake_zone_fines != 2 or resumed.jake_fines_paid != 450.0:
            findings.append("jake citations lost in the snapshot round-trip")
        if resumed.ticket_fines_paid != 150.0:
            findings.append("ticket ledger lost in the snapshot round-trip")
        if abs(resumed.job.deadline_game_h - deadline_before) > 1e-6:
            findings.append(
                f"deadline drifted across save/reload: {deadline_before} -> "
                f"{resumed.job.deadline_game_h} (free hours)"
            )
        if abs(resumed.trip.position_mi - d.trip.position_mi) > 1e-6:
            findings.append("position drifted across save/reload")
        if abs(resumed.hos.driving_min - d.hos.driving_min) > 1e-6:
            findings.append("HOS driving clock drifted across save/reload")
        return _outcome(
            "save_scum_enforcement",
            rig,
            findings,
            "snapshot preserved every ledger and live consequence",
        )
    finally:
        rig.close()
