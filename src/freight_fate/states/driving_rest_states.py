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


class EnforcementStopState(MenuState):
    """Roadside enforcement stop for non-speeding violations."""

    intro_help = "Press Enter or Escape to pull back onto the highway when you are ready."

    def __init__(
        self,
        ctx,
        driving: DrivingState,
        *,
        title: str,
        summary: str,
        fine: float,
        reputation_hit: float,
        signaled: bool,
        return_message: str,
    ) -> None:
        super().__init__(ctx)
        self.driving = driving
        self._title = title
        self.summary = summary
        self.fine = fine
        self.reputation_hit = reputation_hit
        self.signaled = signaled
        self.return_message = return_message
        self._outcome_text = ""
        self._resolve()

    @property
    def title(self) -> str:  # type: ignore[override]
        return self._title

    def presence(self):
        from ..discord_presence import PresenceState

        base = self.driving.presence()
        detail = base.detail if base is not None else ""
        return PresenceState("Pulled over", detail)

    def _resolve(self) -> None:
        p = self.ctx.profile
        d = self.driving
        d.ticket_fines_paid += self.fine
        p.money -= self.fine
        hit = self.reputation_hit * (0.8 if self.signaled else 1.0)
        p.career.reputation = max(0.0, p.career.reputation - hit)
        self.ctx.audio.play("ui/error")
        self._outcome_text = (
            f"Fine: {self.fine:,.0f} dollars, paid on the spot, and a reputation hit."
        )

    def announce_entry(self) -> None:
        polite = " You signaled and pulled over promptly." if self.signaled else ""
        self.ctx.say(
            f"You stop on the shoulder for an enforcement inspection.{polite} "
            f"{self.summary} {self._outcome_text} {self.current_text()}",
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
        self.ctx.say(self.return_message, interrupt=True)


class FelonyStopState(MenuState):
    """Failure-to-stop outcome after the player ignores an active siren."""

    title = "Felony stop"
    intro_help = "Press Enter or Escape to continue from the terminal after the enforcement stop."

    def __init__(self, ctx, driving: DrivingState) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.load_lost = driving.phase == DRIVE_PHASE_DELIVERY and not driving.job.bobtail
        self._summary = ""
        self._resolve()

    def _resolve(self) -> None:
        d = self.driving
        p = self.ctx.profile
        d.failure_to_stop_count += 1
        d.ticket_fines_paid += FAILURE_TO_STOP_FINE
        p.money -= FAILURE_TO_STOP_FINE
        p.career.reputation = max(0.0, p.career.reputation - hos.HOS_REPUTATION_HIT * 3.0)
        d.truck.damage_pct = min(100.0, d.truck.damage_pct + FAILURE_TO_STOP_DAMAGE_PCT)
        d.truck.velocity_mps = 0.0
        d.truck.throttle = 0.0
        d.truck.brake = 1.0
        d.truck.set_parking_brake()
        _advance_rest_clock(
            d,
            FAILURE_TO_STOP_PROCESSING_MIN,
            "on_duty_not_driving",
            "felony failure-to-stop enforcement",
        )
        d.hos.on_duty(FAILURE_TO_STOP_PROCESSING_MIN)
        p.store_truck_condition(d.truck)
        p.game_hours += d.trip.game_minutes / 60.0
        p.market.advance_to(p.market_day())
        p.active_trip = None
        p.pay_advance_used_for_load = False
        self.ctx.save_profile()

        load_text = (
            f"Dispatch cancels the {d.job.cargo.label} load; there is no pay for this run."
            if self.load_lost
            else "There was no loaded trailer to lose, but the active assignment is canceled."
        )
        self._summary = (
            "Troopers laid spike strips across the lane after you kept driving "
            "with lights and siren behind you. "
            f"Felony failure-to-stop fine: {FAILURE_TO_STOP_FINE:,.0f} dollars, "
            "paid on the spot, with a major reputation hit. "
            f"Spike strips added {FAILURE_TO_STOP_DAMAGE_PCT:.0f} percent truck "
            f"damage, and processing took {FAILURE_TO_STOP_PROCESSING_MIN / 60.0:.0f} "
            f"hours. {load_text} You are released back to "
            f"{self.ctx.world.home_terminal(p.current_city).spoken_name}."
        )

    def announce_entry(self) -> None:
        self.ctx.say(f"{self.title}. {self._summary} {self.current_text()}", interrupt=True)

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "Return to terminal",
                self.go_back,
                help="End the canceled run and continue from the city terminal.",
            )
        ]

    def go_back(self) -> None:
        from .city import CityMenuState

        self.ctx.reset_to(CityMenuState(self.ctx))


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
        self._fueled_here = False  # a fuel purchase this visit (free showers)

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
        self.ctx.audio.set_ambient(_poi_ambient_key(self.stop, self.driving.trip.local_hour))
        parts = [f"{self.stop.spoken_name}."]
        if self.stop.parking_text:
            parts.append(f"{self.stop.parking_text}.")
        brand_text = spoken_amenities(self.stop.name, getattr(self.stop, "type", ""))
        if brand_text:
            parts.append(f"{brand_text}.")
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

        # Loyalty program status
        p = self.ctx.profile
        loyalty_summary = p.loyalty.summary()
        items.append(
            MenuItem(
                f"Loyalty program: {loyalty_summary}",
                self._loyalty_menu,
                help="Check your loyalty points, shower credits, and redeem rewards "
                "at this truck stop.",
            )
        )

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
                    "your deadline advance fifteen minutes. Coffee eases fatigue "
                    "a little, but does not satisfy the 30-minute break rule.",
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
            items.append(
                MenuItem(
                    f"Motel room: sleep 10 hours for {MOTEL_COST:.0f} dollars",
                    self._motel_sleep,
                    help="A real bed near the lot. Costs money out of your own "
                    "pocket, but gives the same legal reset with full-quality "
                    "rest: you wake fresh. The clock advances 10 hours.",
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
        brand = classify_brand(self.stop.name)
        if brand is not None and brand.tier == "travel_center":
            if "tires" in brand.signature:
                tire_help = (
                    f"{brand.spoken} runs a dedicated tire bay: road tire "
                    "service close to the terminal garage price, done fast. "
                    "Company drivers bill the carrier; owner-operators pay."
                )
            else:
                tire_help = (
                    f"{brand.spoken} can mount tires on the road, at a "
                    "markup over the terminal garage. Tire specialists "
                    "like Love's and Speedco do the same work cheaper "
                    "and faster."
                )
            items.append(MenuItem(self._tire_label, self._service_tires, help=tire_help))
            if "repair" in brand.signature:
                items.append(
                    MenuItem(
                        self._brake_label,
                        self._service_brakes,
                        help=f"{brand.spoken} runs a full truck service "
                        "shop and can reline worn brake shoes on the "
                        "road, at a markup over the terminal garage. "
                        "Company drivers bill the carrier; "
                        "owner-operators pay.",
                    )
                )
        stop_buffs = buffs_for_stop(self.stop.name, tuple(self.stop.actions))
        if brand is not None and brand.bans_big_rigs and not self.driving.job.bobtail:
            # The famous ban: with a trailer on you never got past the lot.
            stop_buffs = ()
        for buff in stop_buffs:
            items.append(
                MenuItem(
                    (lambda b=buff: self._buff_label(b)),
                    (lambda b=buff: self._buy_buff(b)),
                    help=buff.help,
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
        if not player_pays_operating_costs(self.ctx.profile.business_status):
            return f"Refuel {need:.0f} gallons on the carrier fuel card"
        cost = self.ctx.economy.fuel_cost(d.trip.current_region, need) + 35.0
        return f"Refuel {need:.0f} gallons for {cost:,.0f} dollars"

    def _refuel(self) -> None:
        from ..models.loyalty import loyalty_earnings_text

        d = self.driving
        p = self.ctx.profile
        region = d.trip.current_region
        need = d.truck.specs.fuel_tank_gal - d.truck.fuel_gal
        if need < 1:
            self.ctx.say("The tank is already full.")
            return
        if not player_pays_operating_costs(p.business_status):
            # the carrier fuel card covers road fuel for company drivers
            d.truck.refuel(need)
            self._fueled_here = True
            _advance_rest_clock(d, FUEL_STOP_MIN)
            d.hos.on_duty(FUEL_STOP_MIN)
            self._save_here(silent=True)
            self.ctx.audio.play("vehicle/fuel_pump")

            # Award loyalty points for fueling
            loyalty_result = p.loyalty.add_fueling(
                need, stop_name=self.stop.name, location=self.stop.city
            )
            loyalty_text = loyalty_earnings_text(
                need, loyalty_result["points_earned"], loyalty_result["rewards"]
            )

            self.ctx.say(
                f"Refueled {need:.0f} gallons on the carrier fuel card. "
                f"Fueling took {FUEL_STOP_MIN:.0f} minutes. {loyalty_text}"
            )
            self.ctx.award_achievement("route_refuel")
            self.refresh()
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
        self._fueled_here = True
        _advance_rest_clock(d, FUEL_STOP_MIN)
        d.hos.on_duty(FUEL_STOP_MIN)
        self._save_here(silent=True)
        self.ctx.audio.play("vehicle/fuel_pump")

        # Award loyalty points for fueling
        loyalty_result = p.loyalty.add_fueling(
            need, stop_name=self.stop.name, location=self.stop.city
        )
        loyalty_text = loyalty_earnings_text(
            need, loyalty_result["points_earned"], loyalty_result["rewards"]
        )

        self.ctx.say(
            f"Refueled {need:.0f} gallons for {cost:,.0f} dollars. "
            f"You have {p.money:,.0f} dollars. Fueling took "
            f"{FUEL_STOP_MIN:.0f} minutes. {loyalty_text}"
        )
        self.ctx.award_achievement("route_refuel")
        self.refresh()

    def _loyalty_menu(self) -> None:
        """Show loyalty program details and redemption options."""
        self.ctx.push_state(LoyaltyRewardsState(self.ctx, self.driving, self.stop))


class LoyaltyRewardsState(MenuState):
    """Loyalty program reward redemption menu."""

    title = "Loyalty rewards"
    intro_help = (
        "Use up and down arrows to navigate, Enter to select. "
        "Escape cancels and returns to the previous menu."
    )

    def __init__(self, ctx, driving: DrivingState, stop) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.stop = stop

    def announce_entry(self) -> None:

        p = self.ctx.profile
        loyalty = p.loyalty

        self.ctx.say(
            f"{self.title}. {loyalty.summary()} "
            f"You are at {self.stop.spoken_name}. "
            f"Choose a reward to redeem or go back."
        )

    def build_items(self) -> list[MenuItem]:
        from ..models.loyalty import reward_cost_text

        p = self.ctx.profile
        loyalty = p.loyalty
        items: list[MenuItem] = []

        # Shower credits option
        if loyalty.shower_credits > 0:
            items.append(
                MenuItem(
                    f"Use shower credit ({loyalty.shower_credits} available)",
                    self._use_shower_credit,
                    help="Use a shower credit earned from fueling 50+ gallons.",
                )
            )

        # Point redemption options
        if loyalty.can_redeem("shower"):
            cost_text = reward_cost_text("shower")
            items.append(
                MenuItem(
                    f"Redeem {cost_text}",
                    self._redeem_shower,
                    help="Redeem loyalty points for a free shower.",
                )
            )

        if loyalty.can_redeem("parking"):
            cost_text = reward_cost_text("parking")
            items.append(
                MenuItem(
                    f"Redeem {cost_text}",
                    self._redeem_parking,
                    help="Redeem loyalty points for a parking discount.",
                )
            )

        if loyalty.can_redeem("food"):
            cost_text = reward_cost_text("food")
            items.append(
                MenuItem(
                    f"Redeem {cost_text}",
                    self._redeem_food,
                    help="Redeem loyalty points for a food discount.",
                )
            )

        if loyalty.can_redeem("laundry"):
            cost_text = reward_cost_text("laundry")
            items.append(
                MenuItem(
                    f"Redeem {cost_text}",
                    self._redeem_laundry,
                    help="Redeem loyalty points for a laundry discount.",
                )
            )

        if not items:
            items.append(
                MenuItem(
                    "No rewards available - need more points",
                    None,
                    help="Fuel at truck stops to earn loyalty points.",
                )
            )

        items.append(
            MenuItem(
                "Back to truck stop",
                self.go_back,
                help="Return to the truck stop menu.",
            )
        )

        return items

    def _use_shower_credit(self) -> None:
        p = self.ctx.profile
        if p.loyalty.use_shower_credit():
            self.ctx.audio.play("ui/notify")
            self.ctx.say("Shower credit used. You can now use the shower at no cost.")
            self.refresh()
        else:
            self.ctx.audio.play("ui/error")
            self.ctx.say("No shower credits available.")

    def _redeem_shower(self) -> None:
        p = self.ctx.profile
        result = p.loyalty.redeem_reward("shower")
        if result["success"]:
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"Shower redeemed! {result['points_spent']} points spent. "
                f"You have {result['points_remaining']} points remaining."
            )
            self.refresh()
        else:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Unable to redeem shower. Insufficient points.")

    def _redeem_parking(self) -> None:
        p = self.ctx.profile
        result = p.loyalty.redeem_reward("parking")
        if result["success"]:
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"Parking discount redeemed! {result['points_spent']} points spent. "
                f"You have {result['points_remaining']} points remaining."
            )
            self.refresh()
        else:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Unable to redeem parking discount. Insufficient points.")

    def _redeem_food(self) -> None:
        p = self.ctx.profile
        result = p.loyalty.redeem_reward("food")
        if result["success"]:
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"Food discount redeemed! {result['points_spent']} points spent. "
                f"You have {result['points_remaining']} points remaining."
            )
            self.refresh()
        else:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Unable to redeem food discount. Insufficient points.")

    def _redeem_laundry(self) -> None:
        p = self.ctx.profile
        result = p.loyalty.redeem_reward("laundry")
        if result["success"]:
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"Laundry discount redeemed! {result['points_spent']} points spent. "
                f"You have {result['points_remaining']} points remaining."
            )
            self.refresh()
        else:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Unable to redeem laundry discount. Insufficient points.")

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
        _advance_rest_clock(d, 15.0, "off_duty", "food and coffee")
        d.hos.take_break(15.0)
        p.fatigue = hos.rest_coffee_break(p.fatigue)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"You took a short food and coffee break. "
            f"It is {clock_text(d.trip.local_hour)}. "
            "The coffee helps you stay alert a little longer, but "
            "this short stop does not reset your 30-minute break "
            "requirement. "
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
        )
        self.ctx.award_achievement("slept_on_route")
        if before_fatigue < hos.FATIGUE_SEVERE:
            self.ctx.award_achievement("sleep_before_exhaustion")

    def _motel_sleep(self) -> None:
        """A paid bed where the parking is rough: a legal reset with real rest.

        Lodging is personal money even for company drivers -- the carrier
        pays for the truck, not the room."""
        d = self.driving
        p = self.ctx.profile
        if p.money < MOTEL_COST:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                f"A motel room costs {MOTEL_COST:,.0f} dollars and you have {p.money:,.0f}."
            )
            return
        p.money -= MOTEL_COST
        _advance_rest_clock(d, hos.SLEEP_MIN)
        d.hos.sleep()
        p.fatigue = 0.0
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"You took a motel room for {MOTEL_COST:,.0f} dollars and slept "
            f"a full ten hours. It is {clock_text(d.trip.current_hour)}. "
            f"Hours of service reset and you wake fresh. You have "
            f"{p.money:,.0f} dollars. {_deadline_text(d)}"
        )
        self.ctx.award_achievement("slept_on_route")

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
            f"{_deadline_text(d)}"
        )
        self.ctx.award_achievement("slept_on_route")

    def _repair(self) -> None:
        d = self.driving
        p = self.ctx.profile
        damage = d.truck.damage_pct
        if damage < 1.0:
            self.ctx.say("The truck does not need repair.")
            return
        if not player_pays_operating_costs(p.business_status):
            d.truck.damage_pct = 0.0
            _advance_rest_clock(d, 60.0)
            d.hos.on_duty(60.0)
            self._save_here(silent=True)
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"Shop repaired {damage:.0f} percent damage on the carrier "
                f"account. It is {clock_text(d.trip.current_hour)}. "
                f"{_deadline_text(d)}"
            )
            self.ctx.award_achievement("garage_repair")
            if damage >= 75.0:
                self.ctx.award_achievement("deep_repair")
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
        if damage >= 75.0:
            self.ctx.award_achievement("deep_repair")

    def _roadside_assistance(self) -> None:
        d = self.driving
        p = self.ctx.profile
        damage = d.truck.damage_pct
        if damage < 1.0:
            self.ctx.say("The truck does not need roadside assistance.")
            return
        repaired = max(0.0, damage - FIELD_REPAIR_DAMAGE_PCT)
        cost = MECHANIC_CALLOUT_FEE + repaired * MECHANIC_RATE_PER_PCT
        carrier_paid = not player_pays_operating_costs(p.business_status)
        if not carrier_paid:
            p.money -= cost
        d.truck.damage_pct = min(damage, FIELD_REPAIR_DAMAGE_PCT)
        _advance_rest_clock(d, MECHANIC_WAIT_MIN)
        d.hos.on_duty(MECHANIC_WAIT_MIN)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        billing = "on the carrier breakdown account" if carrier_paid else f"for {cost:,.0f} dollars"
        self.ctx.say(
            f"Roadside assistance patched the truck to "
            f"{d.truck.damage_pct:.0f} percent damage {billing}. It is "
            f"{clock_text(d.trip.local_hour)}. {_deadline_text(d)}"
        )
        self.ctx.award_achievement("roadside_fix")

    def _tire_bay(self) -> bool:
        brand = classify_brand(self.stop.name)
        return brand is not None and "tires" in brand.signature

    def _tire_rate(self) -> float:
        return ROAD_TIRE_SPECIALIST_COST_PER_PCT if self._tire_bay() else ROAD_TIRE_COST_PER_PCT

    def _tire_label(self) -> str:
        wear = self.driving.truck.tire_wear_pct
        if wear < 1:
            return "Tires: tread is in top shape"
        if not player_pays_operating_costs(self.ctx.profile.business_status):
            return f"Replace tires: {wear:.0f} percent wear, carrier billed"
        cost = round(wear * self._tire_rate(), 2)
        return f"Replace tires: {wear:.0f} percent wear for {cost:,.0f} dollars"

    def _brake_label(self) -> str:
        wear = self.driving.truck.brake_wear_pct
        if wear < 1:
            return "Brakes: shoes are in top shape"
        if not player_pays_operating_costs(self.ctx.profile.business_status):
            return f"Brake job: {wear:.0f} percent wear, carrier billed"
        cost = round(wear * ROAD_BRAKE_COST_PER_PCT, 2)
        return f"Brake job: {wear:.0f} percent wear for {cost:,.0f} dollars"

    def _service_tires(self) -> None:
        minutes = ROAD_TIRE_SPECIALIST_MIN if self._tire_bay() else ROAD_TIRE_MIN
        self._road_wear_service(
            attr="tire_wear_pct",
            cost_per_pct=self._tire_rate(),
            minutes=minutes,
            duty_note="road tire service",
            fresh_say="The tires are already in top shape.",
            service_noun="tire service",
            carrier_done="replaced the tires",
            done_say="Tires replaced.",
        )

    def _service_brakes(self) -> None:
        self._road_wear_service(
            attr="brake_wear_pct",
            cost_per_pct=ROAD_BRAKE_COST_PER_PCT,
            minutes=ROAD_BRAKE_MIN,
            duty_note="road brake service",
            fresh_say="The brakes are already in top shape.",
            service_noun="a brake job",
            carrier_done="relined the brakes",
            done_say="Brakes relined.",
        )

    def _road_wear_service(
        self,
        *,
        attr: str,
        cost_per_pct: float,
        minutes: float,
        duty_note: str,
        fresh_say: str,
        service_noun: str,
        carrier_done: str,
        done_say: str,
    ) -> None:
        """Brand-shop wear service on the road, all-or-nothing like road repair.

        Partial service stays a terminal-garage courtesy; a road shop sells
        the whole job or none of it."""
        d = self.driving
        p = self.ctx.profile
        wear = getattr(d.truck, attr)
        if wear < 1.0:
            self.ctx.say(fresh_say)
            return
        if not player_pays_operating_costs(p.business_status):
            setattr(d.truck, attr, 0.0)
            _advance_rest_clock(d, minutes, "on_duty_not_driving", duty_note)
            d.hos.on_duty(minutes)
            self._save_here(silent=True)
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"The shop {carrier_done} at {wear:.0f} percent wear on the "
                f"carrier account. It is {clock_text(d.trip.local_hour)}. "
                f"{_deadline_text(d)}"
            )
            self.refresh()
            return
        cost = round(wear * cost_per_pct, 2)
        if p.money < cost:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                f"{service_noun.capitalize()} costs {cost:,.0f} dollars here. You cannot afford it."
            )
            return
        p.money -= cost
        setattr(d.truck, attr, 0.0)
        _advance_rest_clock(d, minutes, "on_duty_not_driving", duty_note)
        d.hos.on_duty(minutes)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"{done_say} {cost:,.0f} dollars. It is "
            f"{clock_text(d.trip.local_hour)}. You have {p.money:,.0f} "
            f"dollars. {_deadline_text(d)}"
        )
        self.refresh()

    def _buff_price(self, buff) -> float:
        if buff.free_with_fuel and self._fueled_here:
            return 0.0
        return buff.price

    def _buff_label(self, buff) -> str:
        price = self._buff_price(buff)
        if price <= 0.0:
            return f"{buff.label}: free with your fuel purchase"
        return f"{buff.label}: {price:,.0f} dollars"

    def _buy_buff(self, buff) -> None:
        """Apply a consumable buff purchase (data/buffs.py).

        Food, drink, and showers are personal money even for company
        drivers -- the carrier pays for the truck, not your dinner. Rig
        care (lube, tires) is truck work, so the carrier covers it."""
        d = self.driving
        p = self.ctx.profile
        price = self._buff_price(buff)
        rig_buff = buff.group in ("engine", "tire")
        carrier_pays = rig_buff and not player_pays_operating_costs(p.business_status)
        if not carrier_pays and p.money < price:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                f"The {buff.label.lower()} costs {price:,.0f} dollars and you have {p.money:,.0f}."
            )
            return
        if not carrier_pays:
            p.money -= price
        if rig_buff:
            d.rig_buffs[buff.group] = {"id": buff.id, "label": buff.label, "rate": buff.rate}
            _advance_rest_clock(d, buff.stop_minutes, "on_duty_not_driving", buff.label.lower())
            d.hos.on_duty(buff.stop_minutes)
        else:
            if buff.fatigue_instant > 0.0:
                p.fatigue = max(0.0, p.fatigue - buff.fatigue_instant)
            p.add_timed_buff(
                {
                    "id": buff.id,
                    "label": buff.label,
                    "group": buff.group,
                    "rate": buff.rate,
                    "expires_h": d._absolute_game_hour() + buff.duration_game_h,
                    "worn_off": buff.worn_off,
                }
            )
            # Real off-duty time: a 30-minute meal also satisfies the
            # break rule, same as any other break. Never extra hours.
            _advance_rest_clock(d, buff.stop_minutes, "off_duty", buff.label.lower())
            d.hos.take_break(buff.stop_minutes)
        self._save_here(silent=True)
        self.ctx.audio.play("ui/notify")
        if carrier_pays:
            billing = "Billed to the carrier."
        elif price <= 0.0:
            billing = "Free with your fuel purchase."
        else:
            billing = f"{price:,.0f} dollars. You have {p.money:,.0f} dollars."
        self.ctx.say(
            f"{buff.purchased} {billing} It is {clock_text(d.trip.local_hour)}. {_deadline_text(d)}"
        )
        self.refresh()

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
        _record_inspection(self.ctx)

    def _save_here(self, *, silent: bool = False) -> None:
        d = self.driving
        p = self.ctx.profile
        p.store_truck_condition(d.truck)
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
        self.ctx.audio.set_ambient(_poi_ambient_key(self.stop, self.driving.trip.current_hour))
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
                f"Motel room: sleep 10 hours for {MOTEL_COST:.0f} dollars",
                self._motel,
                help="The lot is full, but a motel near the exit has a bed. "
                "Costs your own money; full-quality rest and a legal "
                "10-hour reset.",
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

    def _motel(self) -> None:
        d = self.driving
        p = self.ctx.profile
        if p.money < MOTEL_COST:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                f"A motel room costs {MOTEL_COST:,.0f} dollars and you have {p.money:,.0f}."
            )
            return
        p.money -= MOTEL_COST
        _advance_rest_clock(d, hos.SLEEP_MIN)
        d.hos.sleep()
        p.fatigue = 0.0
        p.store_truck_condition(d.truck)
        p.active_trip = d.snapshot()
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.pop_state()
        self.ctx.say(
            f"You took a motel room for {MOTEL_COST:,.0f} dollars and slept "
            f"a full ten hours. It is {clock_text(d.trip.current_hour)}. "
            f"Hours of service reset and you wake fresh. You have "
            f"{p.money:,.0f} dollars. Press E to start the engine.",
            interrupt=True,
        )
        self.ctx.award_achievement("slept_on_route")

    def _shoulder(self) -> None:
        self.ctx.push_state(
            ShoulderSleepConfirmationState(
                self.ctx,
                self.driving,
                f"The truck parking at {self.stop.spoken_name} is full tonight.",
                self.stop.at_mi,
            )
        )
