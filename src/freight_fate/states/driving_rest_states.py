# ruff: noqa: F403,F405
from __future__ import annotations

from .driving_core import *


class ShoulderSleepConfirmationState(MenuState):
    """Emergency shoulder sleep warning, shared by full lots and no-stop cases."""

    title = "Emergency shoulder sleep"
    intro_help = (
        "Use up and down arrows to navigate, Enter to select. "
        "Escape cancels and returns to the previous menu."
    )

    def __init__(
        self, ctx, driving: DrivingState, reason: str, anchor_mi: float | None = None
    ) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.reason = reason
        self.anchor_mi = anchor_mi

    def announce_entry(self) -> None:
        self.ctx.say(
            f"{self.title}. {self.reason} Shoulder sleep is emergency-only. "
            "It advances ten hours and gives you poor rest: you will not wake "
            "fully rested. If hours of service are enforced, your ELD clock "
            "will reset. You may be ticketed for illegal parking, minor truck "
            "damage can happen, and the delivery deadline keeps counting. "
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "Cancel and keep looking for a safe stop",
                self.go_back,
                help="Return to the previous menu without resting here.",
            ),
            MenuItem(
                "Sleep on the shoulder anyway",
                self._sleep,
                help="Accept poor emergency rest, possible ticket, "
                "possible minor truck damage, and deadline time loss.",
            ),
        ]

    def _sleep(self) -> None:
        anchor = self.anchor_mi
        if anchor is None:
            anchor = self.driving.trip.position_mi
        text = _perform_shoulder_sleep(self.driving, anchor)
        self.ctx.pop_state()
        if self.ctx._app.state is not self.driving:
            self.ctx.pop_state()
        self.ctx.say(text, interrupt=False)


class TrafficStopState(MenuState):
    """A roadside traffic stop after a speeding pull-over: a spoken license and
    logbook check, an on-the-spot ticket or a warning, then back to the road."""

    intro_help = (
        "The trooper has already decided. Press Enter or Escape to "
        "pull back onto the highway when you are ready."
    )

    def __init__(
        self, ctx, driving: DrivingState, *, signaled: bool, over: float, limit: float
    ) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.signaled = signaled
        self.over = over
        self.limit = limit
        self._outcome_text = ""
        self._resolve()

    @property
    def title(self) -> str:  # type: ignore[override]
        return "Traffic stop"

    def presence(self):
        from ..discord_presence import PresenceState

        base = self.driving.presence()
        detail = base.detail if base is not None else ""
        return PresenceState("Pulled over", detail)

    def online_presence(self):
        return self.presence()

    def _resolve(self) -> None:
        """Decide the outcome and apply any ticket immediately."""
        p = self.ctx.profile
        d = self.driving
        rep = p.career.reputation
        first = d.speeding_tickets == 0
        # A warning for a first, marginal stop, or for a well-regarded driver who
        # pulled over promptly and wasn't egregiously over; otherwise a ticket.
        warning = (first and self.over < 15.0) or (
            rep >= 70.0 and self.signaled and self.over < 20.0
        )
        over_text = self.ctx.settings.speed_text(self.over)
        limit_text = self.ctx.settings.speed_text(self.limit)
        if warning:
            self._outcome_text = (
                f"You were {over_text} over the {limit_text} limit. The "
                "trooper lets you off with a warning this time. Keep it down."
            )
            return
        fine = SPEEDING_TICKET_FINES[min(d.speeding_tickets, len(SPEEDING_TICKET_FINES) - 1)]
        d.speeding_tickets += 1
        d.ticket_fines_paid += fine
        p.money -= fine
        hit = hos.HOS_REPUTATION_HIT * (0.7 if self.signaled else 1.0)
        p.career.reputation = max(0.0, rep - hit)
        self.ctx.audio.play("ui/error")
        self._outcome_text = (
            f"You were {over_text} over the {limit_text} limit. Speeding "
            f"ticket: {fine:,.0f} dollars, paid on the spot, and a reputation "
            "hit."
        )

    def announce_entry(self) -> None:
        polite = " You signaled and pulled over promptly." if self.signaled else ""
        self.ctx.say(
            f"You stop on the shoulder and the trooper walks up for a license "
            f"and logbook check.{polite} {self._outcome_text} {self.current_text()}",
            interrupt=True,
        )

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "Pull back onto the highway",
                self.go_back,
                help="Signal, check your mirror, and merge back up to speed.",
            )
        ]

    def go_back(self) -> None:
        self.ctx.pop_state()
        self.ctx.say("Back on the highway. Watch your speed.", interrupt=True)


class RestStopState(MenuState):
    """Spoken route POI menu: actions come from the corridor metadata."""

    intro_help = (
        "Use up and down arrows to navigate, Enter to select. "
        "Escape returns to the road. Breaks and sleep advance the "
        "clock, and your delivery deadline keeps counting."
    )

    def __init__(self, ctx, driving: DrivingState, stop) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.stop = stop

    @property
    def title(self) -> str:  # type: ignore[override]
        return self.stop.spoken_name

    def presence(self):
        from ..discord_presence import PresenceState

        base = self.driving.presence()
        detail = base.detail if base is not None else ""
        return PresenceState("Resting at a stop", detail)

    def online_presence(self):
        return self.presence()

    def announce_entry(self) -> None:
        self.ctx.audio.set_ambient(_poi_ambient_key(self.stop))
        parts = [f"{self.stop.spoken_name}."]
        if self.stop.parking_text:
            parts.append(f"{self.stop.parking_text}.")
        parts.extend(
            [
                f"It is {clock_text(self.driving.trip.local_hour)}.",
                self.current_text(),
            ]
        )
        self.ctx.say(" ".join(parts))

    def build_items(self) -> list[MenuItem]:
        actions = set(self.stop.actions)
        items: list[MenuItem] = []
        if "fuel" in actions:
            items.append(
                MenuItem(
                    self._fuel_label,
                    self._refuel,
                    help="Fill the tank at this region's diesel price, plus a "
                    "35 dollar service fee. If cash is short, buy as many "
                    "gallons as you can afford.",
                )
            )
        if "food" in actions:
            items.append(
                MenuItem(
                    "Food and coffee break",
                    self._food_break,
                    help="A short off-duty break for food or coffee. The clock and "
                    "your deadline advance fifteen minutes.",
                )
            )
        if "break" in actions:
            items.append(
                MenuItem(
                    "Take a 30-minute break",
                    self._take_break,
                    help="Satisfies the 30-minute break rule and eases fatigue. "
                    "The clock and your deadline advance half an hour.",
                )
            )
        if "sleep" in actions:
            for hours in (2, 3, 7, 8):
                items.append(
                    MenuItem(
                        f"Sleep {hours} hours in sleeper berth",
                        lambda h=hours: self._sleeper_split_rest(h),
                        help=self._sleeper_split_help(hours),
                    )
                )
            items.append(
                MenuItem(
                    "Sleep 10 hours",
                    self._sleep,
                    help="A full reset: fresh hours of service and zero fatigue. "
                    "The clock and your deadline advance 10 hours.",
                )
            )
        else:
            # No proper sleeper facility here, but you can always bed down in the
            # lot -- a legal reset, just cramped and poor rest.
            items.append(
                MenuItem(
                    "Sleep 10 hours in the lot",
                    self._emergency_lot_sleep,
                    help="No sleeper facility here, but you can sleep in the lot for "
                    "a legal 10-hour reset. The rest is poor, so you wake still "
                    "tired, and the clock advances 10 hours.",
                )
            )
        if "repair" in actions:
            items.append(
                MenuItem(
                    "Use repair service",
                    self._repair,
                    help="Pay the shop to repair truck damage before returning to the road.",
                )
            )
        if "roadside_assistance" in actions:
            items.append(
                MenuItem(
                    "Call roadside assistance",
                    self._roadside_assistance,
                    help="Use the listed roadside assistance service for a field "
                    "repair before returning to the road.",
                )
            )
        if "towing" in actions:
            items.append(
                MenuItem(
                    "Request towing service",
                    self._roadside_assistance,
                    help="Use the listed towing service for roadside help before "
                    "returning to the road.",
                )
            )
        if "inspect" in actions:
            items.append(
                MenuItem(
                    "Check in at inspection station",
                    self._inspect,
                    help="Stop and record the inspection check-in before continuing.",
                )
            )
        if "save" in actions:
            items.append(
                MenuItem(
                    "Save at this stop",
                    self._save_here,
                    help="Save the active drive at this route POI without leaving the road.",
                )
            )
        if self._pay_advance_available():
            items.append(
                MenuItem(
                    self._pay_advance_label,
                    self._request_pay_advance,
                    help="Draw cash against this load when you are broke and cannot "
                    "afford fuel. Repaid automatically out of your delivery "
                    "settlement.",
                )
            )
        items.append(
            MenuItem(
                "Back to the road", self.go_back, help="Leave this stop and return to driving."
            )
        )
        return items

    def _pay_advance_label(self) -> str:
        p = self.ctx.profile
        grant = pay_advance_grant(p.money, p.pay_advance, p.pay_advance_used_for_load)
        if grant > 0:
            return f"Request pay advance: {grant:,.0f} dollars"
        return "Request pay advance"

    def _pay_advance_available(self) -> bool:
        p = self.ctx.profile
        return pay_advance_grant(p.money, p.pay_advance, p.pay_advance_used_for_load) > 0

    def _request_pay_advance(self) -> None:
        p = self.ctx.profile
        grant = pay_advance_grant(p.money, p.pay_advance, p.pay_advance_used_for_load)
        if grant <= 0:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                pay_advance_unavailable_reason(p.money, p.pay_advance, p.pay_advance_used_for_load)
            )
            return
        p.money += grant
        p.pay_advance = round(p.pay_advance + grant, 2)
        p.pay_advance_used_for_load = True
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"Pay advance approved: {grant:,.0f} dollars against your "
            f"{self.driving.job.destination} load. It will be deducted at "
            f"delivery. You have {p.money:,.0f} dollars, with "
            f"{p.pay_advance:,.0f} dollars of advance still to repay."
        )
        self.refresh()

    def _fuel_label(self) -> str:
        d = self.driving
        need = d.truck.specs.fuel_tank_gal - d.truck.fuel_gal
        if need < 1:
            return "Fuel: tank is full"
        cost = self.ctx.economy.fuel_cost(d.trip.current_region, need) + 35.0
        return f"Refuel {need:.0f} gallons for {cost:,.0f} dollars"

    def _refuel(self) -> None:
        d = self.driving
        p = self.ctx.profile
        region = d.trip.current_region
        need = d.truck.specs.fuel_tank_gal - d.truck.fuel_gal
        if need < 1:
            self.ctx.say("The tank is already full.")
            return
        cost = self.ctx.economy.fuel_cost(region, need) + 35.0
        if p.money < cost:
            partial_gal = max(0.0, (p.money - 35.0) / self.ctx.economy.fuel_price(region))
            if partial_gal < 5:
                self.ctx.audio.play("ui/error")
                self.ctx.say("You cannot afford fuel here.")
                return
            need = partial_gal
            cost = self.ctx.economy.fuel_cost(region, need) + 35.0
        p.money -= cost
        d.truck.refuel(need)
        _advance_rest_clock(d, FUEL_STOP_MIN)
        d.hos.on_duty(FUEL_STOP_MIN)
        self._save_here(silent=True)
        self.ctx.audio.play("vehicle/fuel_pump")
        self.ctx.say(
            f"Refueled {need:.0f} gallons for {cost:,.0f} dollars. "
            f"You have {p.money:,.0f} dollars. Fueling took "
            f"{FUEL_STOP_MIN:.0f} minutes."
        )
        self.ctx.award_achievement("route_refuel")
        self.refresh()

    def _take_break(self) -> None:
        d = self.driving
        p = self.ctx.profile
        _advance_rest_clock(d, 30.0)
        d.hos.take_break(30.0)
        p.fatigue = hos.rest_break(p.fatigue)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"You took a 30-minute break. "
            f"It is {clock_text(d.trip.local_hour)}. "
            f"Your break requirement is reset and you feel a little "
            f"fresher. {_deadline_text(d)}"
        )
        self.ctx.award_achievement("break_taken")

    def _food_break(self) -> None:
        d = self.driving
        p = self.ctx.profile
        _advance_rest_clock(d, 15.0)
        d.hos.take_break(15.0)
        p.fatigue = max(0.0, p.fatigue - 3.0)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"You took a short food and coffee break. "
            f"It is {clock_text(d.trip.local_hour)}. "
            f"{_deadline_text(d)}"
        )

    def _sleeper_split_help(self, hours: int) -> str:
        if hours == 2:
            pair = "Can pair with 8 hours in the sleeper berth."
        elif hours == 3:
            pair = "Can pair with 7 hours in the sleeper berth."
        elif hours == 7:
            pair = "Can pair with 3 more hours at sleep-capable parking."
        else:
            pair = "Can pair with 2 more hours at sleep-capable parking."
        return f"{pair} The clock and your deadline advance {hours} hours."

    def _sleeper_split_rest(self, hours: int) -> None:
        d = self.driving
        p = self.ctx.profile
        minutes = float(hours * 60)
        engine_off = _shut_down_engine(d)
        _advance_rest_clock(d, minutes)
        completed = d.hos.sleeper_split_rest(minutes)
        p.fatigue = hos.rest_sleeper_split(p.fatigue, minutes, completed=completed)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        status = (
            f"Sleeper split credited. {d.hos.summary(self.ctx.settings.hos_mode)} "
            if completed
            else (d.hos.split_pending_summary() or "Sleeper berth rest recorded.")
        )
        self.ctx.say(
            f"{engine_off}You slept {hours} hours in the sleeper berth. "
            f"It is {clock_text(d.trip.local_hour)}. {status} {_deadline_text(d)}"
            f"{_wake_air_instruction(d)}"
        )
        self.ctx.award_achievement("slept_on_route")
        self.refresh()

    def _sleep(self) -> None:
        d = self.driving
        p = self.ctx.profile
        before_fatigue = p.fatigue
        engine_off = _shut_down_engine(d)
        _advance_rest_clock(d, hos.SLEEP_MIN)
        d.hos.sleep()
        p.fatigue = hos.rest_sleep(p.fatigue)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"{engine_off}You slept 10 hours and woke rested. "
            f"It is {clock_text(d.trip.local_hour)}. "
            f"Hours of service reset. {_deadline_text(d)}"
            f"{_wake_air_instruction(d)}"
        )
        self.ctx.award_achievement("slept_on_route")
        if before_fatigue < hos.FATIGUE_SEVERE:
            self.ctx.award_achievement("sleep_before_exhaustion")

    def _emergency_lot_sleep(self) -> None:
        """Bed down in a break/fuel stop's lot when out of hours: a legal HOS
        reset, but cramped poor rest (no proper sleeper), so you wake still
        tired. No shoulder fine -- a lot is more legitimate than the freeway."""
        d = self.driving
        p = self.ctx.profile
        engine_off = _shut_down_engine(d)
        _advance_rest_clock(d, hos.SLEEP_MIN)
        d.hos.sleep()
        p.fatigue = hos.rest_shoulder(p.fatigue)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"{engine_off}You bed down in the cramped lot, off to the side. "
            f"It is {clock_text(d.trip.local_hour)}. Hours of service "
            f"reset, but the rest was poor and you wake still tired. "
            f"{_deadline_text(d)}{_wake_air_instruction(d)}"
        )
        self.ctx.award_achievement("slept_on_route")

    def _repair(self) -> None:
        d = self.driving
        p = self.ctx.profile
        damage = d.truck.damage_pct
        if damage < 1.0:
            self.ctx.say("The truck does not need repair.")
            return
        cost = self.ctx.economy.repair_cost(damage)
        if p.money < cost:
            self.ctx.audio.play("ui/error")
            self.ctx.say(f"Repair costs {cost:,.0f} dollars. You cannot afford it.")
            return
        p.money -= cost
        d.truck.damage_pct = 0.0
        _advance_rest_clock(d, 60.0)
        d.hos.on_duty(60.0)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"Truck repaired for {cost:,.0f} dollars. "
            f"It is {clock_text(d.trip.local_hour)}. "
            f"You have {p.money:,.0f} dollars. {_deadline_text(d)}"
        )
        self.ctx.award_achievement("garage_repair")

    def _roadside_assistance(self) -> None:
        d = self.driving
        p = self.ctx.profile
        damage = d.truck.damage_pct
        if damage < 1.0:
            self.ctx.say("The truck does not need roadside assistance.")
            return
        repaired = max(0.0, damage - FIELD_REPAIR_DAMAGE_PCT)
        cost = MECHANIC_CALLOUT_FEE + repaired * MECHANIC_RATE_PER_PCT
        p.money -= cost
        d.truck.damage_pct = min(damage, FIELD_REPAIR_DAMAGE_PCT)
        _advance_rest_clock(d, MECHANIC_WAIT_MIN)
        d.hos.on_duty(MECHANIC_WAIT_MIN)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"Roadside assistance patched the truck to "
            f"{d.truck.damage_pct:.0f} percent damage for "
            f"{cost:,.0f} dollars. It is "
            f"{clock_text(d.trip.local_hour)}. {_deadline_text(d)}"
        )

    def _inspect(self) -> None:
        d = self.driving
        _advance_rest_clock(d, INSPECTION_MIN)
        d.hos.on_duty(INSPECTION_MIN)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"Inspection check-in complete at {self.stop.spoken_name}. "
            f"It is {clock_text(d.trip.local_hour)}. "
            f"{_deadline_text(d)}"
        )
        self.ctx.award_achievement("inspection")

    def _save_here(self, *, silent: bool = False) -> None:
        d = self.driving
        p = self.ctx.profile
        p.truck_fuel_gal = d.truck.fuel_gal
        p.truck_damage_pct = d.truck.damage_pct
        p.active_trip = d.snapshot()
        self.ctx.save_profile()
        if not silent:
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"Saved at {self.stop.spoken_name}. Your drive will resume from this rest stop."
            )

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()
        self.ctx.say(
            "Back on the road. The parking brake is set. Press "
            f"{self.ctx.control_hint('engine')} to start the engine if needed, then "
            f"{self.ctx.control_hint('parking_brake')} to release the brake "
            "and drive on.",
            interrupt=True,
        )


class ParkingFullState(MenuState):
    """The overnight lot is full: push on, or risk the shoulder."""

    title = "Parking full"
    intro_help = (
        "The truck parking here is full. Use up and down arrows and "
        "Enter to choose. Escape returns to the road to find "
        "another stop."
    )

    def __init__(self, ctx, driving: DrivingState, stop) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.stop = stop

    def announce_entry(self) -> None:
        self.ctx.audio.set_ambient("poi/rest_stop_night")
        self.ctx.say(
            f"The truck parking at {self.stop.spoken_name} is full tonight. "
            f"It is {clock_text(self.driving.trip.local_hour)}. "
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "Drive on to the next stop",
                self._drive_on,
                help="Return to the road and try the next rest stop.",
            ),
            MenuItem(
                "Park on the shoulder and sleep",
                self._shoulder,
                help="Ten hours of poor sleep. Resets your hours of "
                "service, but you will not wake fresh, and you risk "
                "a fine for illegal parking or minor truck damage.",
            ),
        ]

    def go_back(self) -> None:
        self._drive_on()

    def _drive_on(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()
        self.ctx.say(
            "Back on the road. The next stop is announced as you "
            f"approach it. Press {self.ctx.control_hint('engine')} to start the engine.",
            interrupt=True,
        )

    def _shoulder(self) -> None:
        self.ctx.push_state(
            ShoulderSleepConfirmationState(
                self.ctx,
                self.driving,
                f"The truck parking at {self.stop.spoken_name} is full tonight.",
                self.stop.at_mi,
            )
        )
