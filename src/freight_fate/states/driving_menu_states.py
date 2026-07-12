# ruff: noqa: F403,F405
from __future__ import annotations

import time

from ..sim.timezones import to_local
from .driving_core import *
from .driving_rest_states import ShoulderSleepConfirmationState

DELIVERY_SETTLEMENT_MAX_AVERAGE_MPH = 55.0
TIRE_WEAR_PER_MILE = 0.003
ROAD_GRIME_PER_MILE = 0.004


def _settlement_hours(driving: DrivingState) -> float:
    driven_hours = driving.trip.game_minutes / 60.0
    minimum_hours = driving.job.distance_mi / DELIVERY_SETTLEMENT_MAX_AVERAGE_MPH
    return max(driven_hours, minimum_hours)


class DrivingStatusState(MenuState):
    """Live driving status, grouped into screens you open one at a time.

    A tabbed layout (Right/Left to cycle Route, Driver, Map) needs visible tabs
    to make sense, so each screen is its own spoken submenu instead, matching
    the rest of the game's menus.
    """

    title = "Driving status"
    intro_help = (
        "Use up and down arrows to pick a status screen, Enter to open it, and "
        "Escape to return to driving. Each screen lists its status lines."
    )
    SCREENS = (("Route", "route"), ("Driver", "driver"), ("Map", "map"))

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                label,
                lambda key=key: self._open(key),
                help=f"Open the {label.lower()} status screen.",
            )
            for label, key in self.SCREENS
        ]
        items.append(
            MenuItem("Back to driving", self.go_back, help="Close status and resume driving.")
        )
        return items

    def _open(self, screen: str) -> None:
        self.ctx.push_state(DrivingStatusScreenState(self.ctx, self.driving, screen))

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()
        self.ctx.say("Back to driving.", interrupt=False)


class DrivingStatusScreenState(MenuState):
    """One screen of live driving status as a reviewable list of lines."""

    intro_help = (
        "Use up and down arrows to review each line. Enter repeats the current "
        "line. Escape goes back to the status screens."
    )
    TITLES = {"route": "Route", "driver": "Driver", "map": "Map"}

    def __init__(self, ctx, driving: DrivingState, screen: str) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.screen = screen

    @property
    def title(self) -> str:  # type: ignore[override]
        return self.TITLES.get(self.screen, "Status")

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                line,
                lambda line=line: self.ctx.say(line),
                help="Repeat this status line.",
            )
            for line in self._lines()
        ]
        items.append(MenuItem("Back", self.go_back, help="Back to the status screens."))
        return items

    def _lines(self) -> list[str]:
        if self.screen == "driver":
            return self._driver_lines()
        if self.screen == "map":
            return self._map_lines()
        return self.driving.status_lines()

    def _driver_lines(self) -> list[str]:
        d = self.driving
        t = d.truck
        profile = self.ctx.profile
        hours_used = d.trip.game_minutes / 60.0
        deadline = d.job.deadline_game_h - hours_used
        deadline_text = (
            f"{deadline:.1f} hours before the deadline, due {_deadline_appointment(d)}"
            if deadline >= 0
            else f"{-deadline:.1f} hours past the deadline"
        )
        return [
            f"Driver: {profile.name}",
            f"Money: {profile.money:,.0f} dollars",
            f"Load: {d.job.weight_tons:.0f} tons of {d.job.cargo.label}, "
            f"gross {d.truck.gross_mass_kg / KG_PER_TON:.0f} tons",
            f"Objective: {'pickup at ' + d._pickup_facility_text() if d.phase == DRIVE_PHASE_PICKUP else 'deliver to ' + d._destination_facility_text()}",
            f"Truck: fuel {t.fuel_fraction * 100:.0f} percent, damage {t.damage_pct:.0f} percent",
            f"Transmission: {'automatic' if t.transmission.automatic else 'manual'}, {d._gear_text()}",
            f"Fatigue: {profile.fatigue:.0f} percent",
            f"Hours: {d.hos.summary(self.ctx.settings.hos_mode).rstrip('.')}",
            f"Time: {clock_text(d.trip.local_hour)} {d.trip.current_timezone.name}, "
            f"{deadline_text}",
        ]

    def _map_lines(self) -> list[str]:
        d = self.driving
        route = d.route
        settings = self.ctx.settings
        lines = [
            f"Route: {' to '.join(route.cities)}",
            f"Highways: {_join_phrase(route.highways)}",
            f"Progress: {settings.distance_text(d.trip.position_mi)} driven, "
            f"{settings.distance_text(d.trip.remaining_miles)} remaining",
            f"Guidance: {d.trip.next_navigation_context(settings.imperial_units)}",
        ]
        upcoming = [stop for stop in d.trip.stops if stop.at_mi >= d.trip.position_mi - 0.05][:5]
        if upcoming:
            for stop in upcoming:
                ahead = max(0.0, stop.at_mi - d.trip.position_mi)
                lines.append(
                    f"Stop in {settings.distance_text(ahead)}: {stop.spoken_name}; "
                    f"{_poi_offers_text(stop)}."
                )
        else:
            lines.append("Stops: no more listed route stops before destination.")
        next_cues = [
            cue
            for cue in d.trip.navigation_cues
            if cue.at_mi > d.trip.position_mi + 0.05 and cue.kind != "rest_stop"
        ][:4]
        for cue in next_cues:
            ahead = max(0.0, cue.at_mi - d.trip.position_mi)
            speed = f" at {settings.speed_text(cue.speed_mph)}" if cue.speed_mph is not None else ""
            lines.append(f"Map point in {settings.distance_text(ahead)}: {cue.text}{speed}.")
        if route.estimated_tolls > 0:
            lines.append(
                f"Estimated carrier-paid toll exposure: {route.estimated_tolls:,.0f} dollars."
            )
        return lines


class PauseMenuState(MenuState):
    title = "Paused"

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def enter(self) -> None:
        self.ctx.audio.play("ui/pause")
        self.ctx.audio.stop_world()
        self.driving._reverse_cue_active = False
        super().enter()

    def presence(self):
        from ..discord_presence import PresenceState

        base = self.driving.presence()
        detail = base.detail if base is not None else ""
        return PresenceState("Paused", detail)

    def online_presence(self):
        # A paused player is not actively hauling, so they leave the public
        # drivers board as though they went off duty; the service's off-duty
        # grace absorbs a quick pause-and-resume without bouncing the row.
        # Discord presence (above) still shows "Paused" while the menu is up.
        return None

    def build_items(self) -> list[MenuItem]:
        drive_label = "pickup drive" if self.driving.phase == DRIVE_PHASE_PICKUP else "delivery"
        items = [
            MenuItem("Resume driving", self._resume, help=f"Return to the active {drive_label}."),
            MenuItem(
                "Trip status",
                self._status,
                help="Hear cargo, objective, route progress, and time used.",
            ),
            MenuItem(
                "Controls and help",
                self._controls,
                help="Open the how-to-play reference at the driving keys. "
                "Left and Right arrows change pages, Up and Down read "
                "line by line, Escape returns here.",
            ),
            MenuItem(
                self._mechanic_label,
                self._mechanic,
                help="A mobile mechanic patches the truck up enough to "
                "drive on. Costs much more than a garage repair, "
                "takes an hour and a half, and the bill is due even "
                "if it puts you in debt.",
            ),
            MenuItem(
                "Settings",
                self._settings,
                help="Change units, transmission, volumes, weather, "
                "voices, update channel, and trip pacing.",
            ),
            MenuItem(
                "Abandon job",
                self._abandon,
                help="Give up this job. Costs five hundred dollars and "
                "reputation, and returns you to the origin city.",
            ),
            MenuItem(
                "Quit to main menu",
                self._quit_to_menu,
                help="You can only save at a stop, so this drive is not "
                "saved in progress. It resumes from your last stop "
                "when you continue. Use Abandon job to drop the load.",
            ),
        ]
        if self.driving.emergency_shoulder_sleep_reason() is not None:
            items.insert(
                4,
                MenuItem(
                    "Emergency shoulder sleep",
                    self._emergency_shoulder_sleep,
                    help="Emergency-only poor sleep on the shoulder. Resets hours "
                    "of service, but fatigue remains, you may be ticketed, "
                    "minor truck damage can happen, and the deadline keeps "
                    "running.",
                ),
            )
        return items

    def go_back(self) -> None:
        self._resume()

    def _mechanic_label(self) -> str:
        damage = self.driving.truck.damage_pct
        if damage <= FIELD_REPAIR_DAMAGE_PCT:
            return "Call a roadside mechanic: not needed yet"
        repaired = damage - FIELD_REPAIR_DAMAGE_PCT
        cost = MECHANIC_CALLOUT_FEE + repaired * MECHANIC_RATE_PER_PCT
        return f"Call a roadside mechanic: {cost:,.0f} dollars"

    def _mechanic(self) -> None:
        d = self.driving
        damage = d.truck.damage_pct
        if damage <= FIELD_REPAIR_DAMAGE_PCT:
            self.ctx.say(
                "The truck is running well enough. A roadside mechanic "
                f"can help once damage is past "
                f"{FIELD_REPAIR_DAMAGE_PCT:.0f} percent."
            )
            return
        if d.truck.speed_mph > 3:
            self.ctx.say("Come to a complete stop first.")
            return
        p = self.ctx.profile
        repaired = damage - FIELD_REPAIR_DAMAGE_PCT
        cost = MECHANIC_CALLOUT_FEE + repaired * MECHANIC_RATE_PER_PCT
        p.money -= cost  # the rescue is never refused; money can go negative
        d.truck.damage_pct = FIELD_REPAIR_DAMAGE_PCT
        _advance_rest_clock(d, MECHANIC_WAIT_MIN)
        d.hos.on_duty(MECHANIC_WAIT_MIN)
        self.ctx.audio.play("ui/notify")
        self.refresh()
        self.ctx.say(
            f"A mobile mechanic patched the truck up to "
            f"{FIELD_REPAIR_DAMAGE_PCT:.0f} percent damage for "
            f"{cost:,.0f} dollars. You have {p.money:,.0f} dollars. "
            f"The repair took an hour and a half: it is "
            f"{clock_text(d.trip.local_hour)}. {_deadline_text(d)}"
        )

    def _emergency_shoulder_sleep(self) -> None:
        reason = self.driving.emergency_shoulder_sleep_reason()
        if reason is None:
            self.ctx.say(
                "Emergency shoulder sleep is not available right now. "
                "Use a route stop for normal breaks and sleep."
            )
            self.refresh()
            return
        self.ctx.push_state(
            ShoulderSleepConfirmationState(
                self.ctx, self.driving, reason, self.driving.trip.position_mi
            )
        )

    def handle_controller(self, event, manager) -> None:
        # Start pauses and unpauses, so it resumes from the pause menu too.
        if (
            event.type == pygame.CONTROLLERBUTTONDOWN
            and event.button == pygame.CONTROLLER_BUTTON_START
        ):
            self._resume()
            return
        super().handle_controller(event, manager)

    def _resume(self) -> None:
        self.ctx.audio.play("ui/unpause")
        self.ctx.pop_state()
        self.ctx.say("Resumed.", interrupt=False)

    def _status(self) -> None:
        d = self.driving
        hours_used = d.trip.game_minutes / 60.0
        if d.phase == DRIVE_PHASE_PICKUP:
            self.ctx.say(
                f"Driving to pickup at {d._pickup_facility_text()}. "
                f"{d.job.weight_tons:.0f} tons of {d.job.cargo.label} are "
                f"assigned for {d.job.spoken_destination}. "
                f"{d._pickup_progress_summary()} {hours_used:.1f} hours used. "
                f"{d._air_status_text()}."
            )
            return
        self.ctx.say(
            f"Hauling {d.job.weight_tons:.0f} tons of {d.job.cargo.label} "
            f"to {d.job.spoken_destination}. "
            f"{d.trip.progress_summary(self.ctx.settings.imperial_units)} "
            f"{hours_used:.1f} hours used of {d.job.deadline_game_h:.0f}. "
            f"{d._air_status_text()}."
        )

    def _controls(self) -> None:
        from .main_menu import HelpState, controls_help_page

        self.ctx.push_state(HelpState(self.ctx, start_page=controls_help_page()))

    def _settings(self) -> None:
        from .main_menu import SettingsState

        self.ctx.push_state(SettingsState(self.ctx))

    def _abandon(self) -> None:
        # Abandoning is destructive and one keystroke away, so confirm first.
        self.ctx.push_state(AbandonJobConfirmationState(self.ctx, self.driving))

    def _quit_to_menu(self) -> None:
        from .main_menu import MainMenuState

        # Saving happens only at stops, so a mid-drive quit writes nothing: the
        # on-disk save still points at your last stop, and Continue resumes the
        # leg from there. In-progress leg driving is intentionally not preserved.
        drive_label = "pickup drive" if self.driving.phase == DRIVE_PHASE_PICKUP else "delivery"
        self.ctx.say(
            f"Returning to the title. You can only save at a stop, so this "
            f"{drive_label} will resume from your last stop, not from here.",
            interrupt=True,
        )
        self.ctx.reset_to(MainMenuState(self.ctx))


class AbandonJobConfirmationState(MenuState):
    """Yes/No guard in front of abandoning a job. Lands on "No" so giving up
    the load takes a deliberate arrow to "Yes"."""

    title = "Abandon job?"
    intro_help = (
        "Use up and down arrows to navigate, Enter to select. "
        "Escape cancels and returns to the pause menu."
    )

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    def announce_entry(self) -> None:
        self.ctx.say(
            f"{self.title} Abandoning gives up this load. You will pay a five "
            "hundred dollar penalty, take a reputation hit, and return to "
            f"{self.ctx.world.spoken_city(self.ctx.profile.current_city)}. "
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "No, keep driving",
                self.go_back,
                help="Return to the pause menu and keep this job.",
            ),
            MenuItem(
                "Yes, abandon the job",
                self._confirm,
                help="Give up this job. Costs five hundred dollars and "
                "reputation, and returns you to the origin city.",
            ),
        ]

    def _confirm(self) -> None:
        from .city import CityMenuState

        p = self.ctx.profile
        p.money -= 500.0
        p.career.reputation = max(0.0, p.career.reputation - 5.0)
        p.truck_fuel_gal = self.driving.truck.fuel_gal
        p.truck_damage_pct = self.driving.truck.damage_pct
        # the hours spent on the failed run still happened: keep the world
        # clock consistent with the HOS and fatigue already accrued
        p.game_hours += self.driving.trip.game_minutes / 60.0
        p.market.advance_to(p.market_day())
        p.active_trip = None
        p.pay_advance_used_for_load = False
        self.ctx.save_profile()
        self.ctx.pop_state()  # close this confirmation
        self.ctx.pop_state()  # close the pause menu
        self.ctx.replace_state(CityMenuState(self.ctx))
        # interrupt=True so this overrides any menu re-announcement during unwind
        self.ctx.say(
            f"Job abandoned. You paid a five hundred dollar penalty and "
            f"returned to {self.ctx.world.spoken_city(p.current_city)}.",
            interrupt=True,
        )


class FacilityArrivalState(MenuState):
    title = "Destination facility"
    open_sound_key = "facility/dock_gate"
    intro_help = "Use arrows to navigate, Enter to select. Dock and deliver completes the job."

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving

    @property
    def facility(self) -> str:
        return self.driving._destination_facility_text()

    def presence(self):
        from ..discord_presence import PresenceState

        return PresenceState(
            "Delivering",
            f"{self.driving.job.cargo.label} to {self.driving.job.spoken_destination}",
        )

    def online_presence(self):
        return self.presence()

    def enter(self) -> None:
        sequence = select_menu_music_sequence(self.ctx.profile)
        self.ctx.play_music_sequence("menu", sequence)
        super().enter()

    def announce_entry(self) -> None:
        self.ctx.audio.set_ambient("poi/facility_gate")
        self.ctx.say(f"At {self.facility}. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "Dock and deliver",
                self._dock,
                help="Back into the dock and complete this delivery.",
            ),
            MenuItem(
                "Check paperwork",
                self._paperwork,
                help="Review pay, deadline, cargo condition, and charges.",
            ),
            MenuItem(
                "Check arrival status",
                self._status,
                help="Hear the facility, cargo, speed, and next step.",
            ),
        ]

    def _dock(self) -> None:
        d = self.driving
        if d.truck.speed_mph > DOCKING_MAX_MPH:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Stop before docking.")
            return
        d.truck.throttle = 0.0
        d.truck.brake = 1.0
        d.truck.set_parking_brake()
        d._set_status("Docked. Delivery paperwork signed.")
        self.ctx.audio.play("poi/dock_and_deliver")
        self.ctx.say(
            f"Docked at {self.facility}. Trailer secured and paperwork signed.", interrupt=True
        )
        d._arrive()

    def _paperwork(self) -> None:
        d = self.driving
        job = d.job
        hours = d.trip.game_minutes / 60.0
        remaining = job.deadline_game_h - hours
        trip_damage = max(0.0, d.truck.damage_pct - d.start_damage)
        estimated_pay = job.payout(hours, trip_damage)
        tolls = d.trip.toll_expense
        accessorials = carrier_accessorial_charges(job)
        carrier_charges = tolls + charge_total(accessorials)
        driver_charges = _speeding_settlement_fine(d.speeding_strikes)
        net_estimated_pay = max(0.0, estimated_pay - driver_charges)
        advance_due = round(min(self.ctx.profile.pay_advance, net_estimated_pay), 2)
        net_estimated_pay = round(net_estimated_pay - advance_due, 2)
        advance_note = (
            f" A pay advance of {advance_due:,.0f} dollars will be repaid from this settlement."
            if advance_due > 0
            else ""
        )
        timing = (
            f"{remaining:.1f} hours remain before the deadline"
            if remaining >= 0
            else f"{-remaining:.1f} hours past the deadline"
        )
        if trip_damage > 1:
            cargo_condition = (
                f"Damage consideration: this run added {trip_damage:.0f} "
                "percent truck damage, which may reduce final pay."
            )
        else:
            cargo_condition = "Cargo condition: no new damage recorded."
        self.ctx.say(
            f"Paperwork for {self.facility}: {job.weight_tons:.0f} tons of "
            f"{job.cargo.label}. Rate sheet lists {job.pay:,.0f} dollars; "
            f"current gross payout is {estimated_pay:,.0f} dollars. "
            f"Carrier-paid or reimbursed charges recorded so far are "
            f"{carrier_charges:,.0f} dollars, including tolls "
            f"{tolls:,.0f} and accessorials {charge_summary(accessorials)}. "
            "Those charges do not reduce driver pay. "
            f"Driver-responsibility charges are estimated at "
            f"{driver_charges:,.0f} dollars, for estimated net driver pay "
            f"{net_estimated_pay:,.0f}.{advance_note} "
            f"{timing}. {cargo_condition} Dock and deliver to settle."
        )

    def _status(self) -> None:
        d = self.driving
        self.ctx.say(
            f"At {self.facility}. Hauling {d.job.weight_tons:.0f} tons of "
            f"{d.job.cargo.label}. Current speed "
            f"{self.ctx.settings.speed_text(d.truck.speed_mph)}. "
            "Stop, then Dock and deliver."
        )

    def go_back(self) -> None:
        self.ctx.say("At destination. Dock and deliver to finish.")

    def lines(self) -> list[str]:
        return [
            self.title,
            "",
            f"Facility: {self.facility}",
            f"Speed: {self.driving.truck.speed_mph:.0f} mph",
            "Docking required before delivery settlement.",
            "",
        ] + [("> " if i == self.index else "  ") + item.text for i, item in enumerate(self.items)]


class ArrivalState(MenuState):
    title = "Delivery complete"
    intro_help = (
        "Use up and down arrows to review the delivery summary. Enter repeats "
        "the current line. Escape continues."
    )

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.summary_parts: list[str] = []
        self._achievement_messages: list[str] = []
        self._announcements: list[str] = []
        self.summary_lines: list[str] = []
        self.terminal = ctx.world.home_terminal(driving.job.destination)
        self._settle()

    def _settle_bobtail(self, hours: float, trip_damage: float) -> None:
        """Empty reposition run: relocate to the destination city, no pay."""
        d = self.driving
        p = self.ctx.profile
        job = d.job
        self.title = "Repositioned"
        p.current_city = job.destination
        driver_charges = _speeding_settlement_fine(d.speeding_strikes)
        if driver_charges:
            p.money -= driver_charges
            self.summary_parts.append(
                f"Driver-responsibility charges: speeding fines cost you "
                f"{driver_charges:,.0f} dollars."
            )
        p.truck_fuel_gal = d.truck.fuel_gal
        p.truck_damage_pct = d.truck.damage_pct
        p.game_hours += hours
        p.market.advance_to(p.market_day())
        p.active_trip = None
        p.pay_advance_used_for_load = False
        self.ctx.save_profile()
        self.summary_parts.insert(
            0,
            (
                f"Bobtailed empty to {job.spoken_destination} in {hours:.1f} hours. "
                f"It is {clock_text(to_local(p.game_hours, d.trip.destination_timezone))}. "
                f"No load and no pay, but you are "
                f"parked at {self.terminal.name} and can shop the {job.spoken_destination} "
                f"dispatch board. Fuel {d.truck.fuel_fraction * 100:.0f} percent."
            ),
        )
        if trip_damage > 1:
            self.summary_parts.append(
                f"The empty run added {trip_damage:.0f} percent truck damage. "
                "Visit the garage when you can."
            )
        # The arrival screen and announcement read summary_lines, not parts.
        self.summary_lines = list(self.summary_parts)

    def _settle(self) -> None:
        d = self.driving
        p = self.ctx.profile
        job = d.job
        hours = _settlement_hours(d)
        trip_damage = max(0.0, d.truck.damage_pct - d.start_damage)
        if job.bobtail:
            self._settle_bobtail(hours, trip_damage)
            return
        gross_pay = job.payout(hours, trip_damage)
        toll_expense = d.trip.toll_expense
        accessorials = carrier_accessorial_charges(job)
        carrier_charges = toll_expense + charge_total(accessorials)
        early_bonus = max(0.0, gross_pay - job.payout(job.deadline_game_h, trip_damage))
        driver_charges = _speeding_settlement_fine(d.speeding_strikes)
        if driver_charges:
            self.summary_parts.append(
                f"Driver-responsibility charges: speeding fines cost you "
                f"{driver_charges:,.0f} dollars."
            )
        # Tickets from being pulled over were already paid on the spot; report
        # them for transparency but don't deduct again at settlement.
        if d.speeding_tickets:
            self.summary_parts.append(
                f"On-the-spot speeding tickets this trip: {d.speeding_tickets}, "
                f"already paid, {d.ticket_fines_paid:,.0f} dollars."
            )
        net_pay = max(0.0, gross_pay - driver_charges)
        advance_repaid = round(min(p.pay_advance, net_pay), 2)
        if advance_repaid > 0:
            net_pay = round(net_pay - advance_repaid, 2)
            p.pay_advance = round(p.pay_advance - advance_repaid, 2)
            outstanding = (
                f" {p.pay_advance:,.0f} dollars of advance still outstanding."
                if p.pay_advance >= 1.0
                else ""
            )
            self.summary_parts.append(
                f"Pay advance repaid from this settlement: "
                f"{advance_repaid:,.0f} dollars.{outstanding}"
            )
        on_time = hours <= job.deadline_game_h
        p.money += net_pay
        p.current_city = job.destination
        p.truck_fuel_gal = d.truck.fuel_gal
        p.truck_damage_pct = d.truck.damage_pct
        tire_wear_added = min(100.0, job.distance_mi * TIRE_WEAR_PER_MILE)
        road_grime_added = min(100.0, job.distance_mi * ROAD_GRIME_PER_MILE)
        p.tire_wear_pct = min(100.0, p.tire_wear_pct + tire_wear_added)
        p.road_grime_pct = min(100.0, p.road_grime_pct + road_grime_added)
        previous_level = p.career.level
        announcements = p.career.record_delivery(job.distance_mi, net_pay, on_time, trip_damage)
        p.game_hours += hours
        p.market.advance_to(p.market_day())
        p.active_trip = None
        p.pay_advance_used_for_load = False
        self.ctx.save_profile()
        from ..online_journal import queue_career_milestones, queue_delivery

        occurred_at_ms = int(time.time() * 1000)
        if queue_delivery(
            self.ctx._app.journal,
            p,
            job,
            origin=self.ctx.world.spoken_city(job.origin),
            destination=self.ctx.world.spoken_city(job.destination),
            on_time=on_time,
            occurred_at_ms=occurred_at_ms,
            undamaged=trip_damage <= 1,
        ):
            self.ctx._app.journal.flush_async()
        if queue_career_milestones(
            self.ctx._app.journal,
            p,
            previous_level=previous_level,
            occurred_at_ms=occurred_at_ms,
        ):
            self.ctx._app.journal.flush_async()

        self.summary_parts.insert(
            0,
            (
                f"Delivered {job.weight_tons:.0f} tons of {job.cargo.label} to "
                f"{job.spoken_destination} in {hours:.1f} hours, "
                f"{'on time' if on_time else 'late'}. "
                f"It is {clock_text(to_local(p.game_hours, d.trip.destination_timezone))}. "
                f"Gross pay {gross_pay:,.0f} dollars. "
                f"Carrier-paid or reimbursed charges {carrier_charges:,.0f} dollars: "
                f"tolls {toll_expense:,.0f}, accessorials "
                f"{charge_summary(accessorials)}. "
                "These are billed to carrier settlement and not deducted from driver pay. "
                f"Driver-responsibility charges {driver_charges:,.0f} dollars. "
                f"Net driver pay {net_pay:,.0f} "
                f"dollars, and you now have {p.money:,.0f}. "
                f"After unloading, dispatch has you parked at "
                f"{self.terminal.name} for the {job.spoken_destination} service area."
            ),
        )
        if early_bonus >= 1.0:
            self.summary_parts.append(f"Early delivery bonus: {early_bonus:,.0f} dollars.")
        if trip_damage > 1:
            self.summary_parts.append(
                f"The cargo run added {trip_damage:.0f} percent truck damage. "
                "Visit the garage when you can."
            )
        if tire_wear_added > 0.0 or road_grime_added > 0.0:
            self.summary_parts.append(
                f"The run added {tire_wear_added:.1f} percent tire wear and "
                f"{road_grime_added:.1f} percent road grime."
            )
        self.summary_parts.extend(announcements)
        self._award_arrival_achievements(
            on_time=on_time,
            trip_damage=trip_damage,
            toll_expense=toll_expense,
            route_miles=d.route.miles,
            speeding_strikes=d.speeding_strikes,
            gross_pay=gross_pay,
        )
        self.summary_parts.extend(self._achievement_messages)
        timing = "On time" if on_time else "Late"
        bonus_text = (
            f"Early delivery bonus: {early_bonus:,.0f} dollars"
            if early_bonus >= 1.0
            else "No early delivery bonus on this run"
        )
        cargo_condition = (
            f"Truck damage added on this run: {trip_damage:.0f} percent"
            if trip_damage > 1
            else "No new damage recorded"
        )
        career_lines = announcements + self._achievement_messages
        if not career_lines:
            career_lines = ["No new career messages."]
        advance_lines = []
        if advance_repaid > 0:
            advance_lines.append(f"Pay advance repaid: {advance_repaid:,.0f} dollars.")
        if p.pay_advance >= 1.0:
            advance_lines.append(f"Pay advance still outstanding: {p.pay_advance:,.0f} dollars.")
        self.summary_lines = [
            f"Delivered {job.weight_tons:.0f} tons of {job.cargo.label} "
            f"to {job.spoken_destination}.",
            f"Trip time: {hours:.1f} hours, {timing.lower()}.",
            f"It is {clock_text(to_local(p.game_hours, d.trip.destination_timezone))}.",
            f"Parked at {self.terminal.name} for the {job.spoken_destination} service area.",
            f"Gross pay: {gross_pay:,.0f} dollars.",
            f"Carrier-paid or reimbursed charges: {carrier_charges:,.0f} "
            f"dollars, including tolls {toll_expense:,.0f} and "
            f"accessorials {charge_summary(accessorials)}.",
            "Carrier charges are not deducted from driver pay.",
            f"Driver-responsibility charges: {driver_charges:,.0f} dollars.",
            *advance_lines,
            f"Net driver pay: {net_pay:,.0f} dollars.",
            f"Money after settlement: {p.money:,.0f} dollars.",
            bonus_text + ".",
            f"Route: {' to '.join(self.ctx.world.spoken_city(c) for c in d.route.cities)}.",
            f"Distance credited: {job.distance_mi:.0f} miles.",
            cargo_condition + ".",
            f"Fuel remaining: {d.truck.fuel_fraction * 100:.0f} percent.",
            f"Truck damage now: {d.truck.damage_pct:.0f} percent.",
            *career_lines,
        ]
        self._announcements = announcements

    def _award_arrival_achievements(
        self,
        *,
        on_time: bool,
        trip_damage: float,
        toll_expense: float,
        route_miles: float,
        speeding_strikes: int,
        gross_pay: float = 0.0,
    ) -> None:
        p = self.ctx.profile
        route = self.driving.route
        world = self.ctx.world
        states = {world.cities[city].state for city in route.cities}
        regions = {world.cities[city].region for city in route.cities}
        region_count = 0
        for region in regions:
            region_count = add_unique_stat(p, "regions_visited", region)

        ids = ["first_delivery"]
        if on_time:
            ids.append("first_on_time")
        if trip_damage <= 1.0:
            ids.append("clean_delivery")
        if speeding_strikes == 0:
            ids.append("speed_limit_saint")
        if toll_expense > 0:
            ids.append("toll_paid")
        elif route_miles >= 300.0:
            ids.append("no_toll_long")
        if len(states) >= 2:
            ids.append("state_crossing")
        if len(states) >= 3:
            ids.append("multi_state")
        if len(regions) >= 3 or region_count >= 3:
            ids.append("three_regions")
        if route_miles >= 900.0:
            ids.append("long_haul")
        if p.career.deliveries >= 5:
            ids.append("five_deliveries")
        if p.career.deliveries >= 10:
            ids.append("ten_deliveries")
        if p.career.level >= 3:
            ids.append("level_three")
        if p.money >= 25_000.0:
            ids.append("twenty_five_grand")
        if p.career.total_miles >= 1_000.0:
            ids.append("thousand_miles")

        # -- Landmarks: direction, famous corridors, and city-arrival badges --
        origin, dest = route.cities[0], route.cities[-1]
        origin_lon = world.cities[origin].lon
        dest_lon = world.cities[dest].lon
        if dest_lon - origin_lon > 1.0:
            ids.append("eastbound_delivery")
        if origin_lon - dest_lon > 1.0:
            ids.append("westbound_delivery")
        if abs(dest_lon - origin_lon) >= 35.0:
            ids.append("coast_to_coast")
        route66 = {
            "chicago_il_us",
            "st_louis_mo_us",
            "tulsa_ok_us",
            "oklahoma_city_ok_us",
            "amarillo_tx_us",
            "albuquerque_nm_us",
            "flagstaff_az_us",
            "los_angeles_ca_us",
        }
        if origin in route66 and dest in route66:
            ids.append("route66_run")
        # Wall-clock badge conditions ("by Daybreak", "Midnight Freight") read
        # the destination's local clock, matching what the player just heard.
        arrival_hour = self.driving.trip.local_hour
        # Plain "deliver into this city" badges (titles claim nothing extra).
        simple_arrival = {
            "phoenix_az_us": "phoenix_arrival",
            "wichita_ks_us": "wichita_arrival",
            "bakersfield_ca_us": "bakersfield_arrival",
            "las_vegas_nv_us": "vegas_arrival",
        }
        if dest in simple_arrival:
            ids.append(simple_arrival[dest])
        # Badges whose title names a condition, so the condition is enforced:
        if dest == "amarillo_tx_us" and 5.0 <= arrival_hour < 12.0:  # "by Daybreak"
            ids.append("amarillo_arrival")
        if dest == "tulsa_ok_us" and on_time:  # "Right on Schedule"
            ids.append("tulsa_arrival")
        if world.cities[dest].state == "Georgia" and is_night(arrival_hour):
            ids.append("georgia_arrival")  # "Midnight Freight"
        # Departures: the title puts the city in the rearview / "out of" it.
        if origin == "lubbock_tx_us":  # "in the Rearview"
            ids.append("lubbock_arrival")
        if origin == "detroit_mi_us":  # "Last Load Out of"
            ids.append("detroit_run")

        # -- Challenges: grind milestones, long hauls, spotless runs ----------
        if region_count >= 14:
            ids.append("all_regions")
        if p.career.deliveries >= 50:
            ids.append("fifty_deliveries")
        if p.career.deliveries >= 100:
            ids.append("hundred_deliveries")
        if p.career.total_miles >= 10_000.0:
            ids.append("ten_thousand_miles")
        if p.career.total_miles >= 50_000.0:
            ids.append("fifty_thousand_miles")
        if p.money >= 100_000.0:
            ids.append("hundred_grand")
        if p.career.level >= 10:
            ids.append("max_level")
        if p.career.reputation >= 100.0:
            ids.append("top_reputation")
        if gross_pay >= 4_000.0:
            ids.append("big_payday")
        if route_miles >= 1_200.0 and on_time and trip_damage <= 1.0:
            ids.append("grueling_clean")
        if any(leg.terrain == "mountain" for leg in route.legs) and trip_damage <= 1.0:
            ids.append("mountain_clean")
        if len(route.legs) >= 4:
            ids.append("multi_leg_haul")
        # Five consecutive on-time, undamaged, ticket-free deliveries.
        stats = p.achievement_stats if isinstance(p.achievement_stats, dict) else {}
        p.achievement_stats = stats
        perfect = on_time and trip_damage <= 1.0 and speeding_strikes == 0
        streak = int(stats.get("perfect_streak", 0)) + 1 if perfect else 0
        stats["perfect_streak"] = streak
        if streak >= 5:
            ids.append("perfect_streak")

        for achievement_id in ids:
            result = self.ctx.award_achievement(achievement_id, announce=False)
            if result is not None:
                self._achievement_messages.append(result.message)
        self.ctx.save_profile()

    def enter(self) -> None:
        self.ctx.audio.stop_world()
        self.ctx.audio.play("ui/job_complete")
        if self._announcements or self._achievement_messages:
            self.ctx.audio.play("ui/level_up")
        self.ctx.audio.play("ui/cash")
        self.items = self.build_items()
        self.index = min(self.index, max(0, len(self.items) - 1))
        self.announce_entry()

    def announce_entry(self) -> None:
        self.ctx.say(
            f"{self.title}. {self.current_text()}",
            interrupt=False,
        )

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                line, lambda line=line: self.ctx.say(line), help="Repeat this settlement line."
            )
            for line in self.summary_lines
        ]
        items.append(MenuItem("Continue to " + self.terminal.name, self._continue))
        return items

    def go_back(self) -> None:
        self._continue()

    def _continue(self) -> None:
        from .city import CityMenuState

        self.ctx.replace_state(CityMenuState(self.ctx))

    def lines(self) -> list[str]:
        return (
            [self.title, ""]
            + self.summary_lines
            + [""]
            + [("> " if i == self.index else "  ") + item.text for i, item in enumerate(self.items)]
        )
