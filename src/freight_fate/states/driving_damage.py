# ruff: noqa: F403,F405
"""Damage bands while driving: reduced power, limp mode, and out of service.

Damage used to be a number that cost money at the garage and shaved a little
power off a curve. A truck at 99 percent drove very nearly like a healthy
one, which is the wrong lesson twice over: an electronic engine meets a
serious fault with a staged inducement, and a truck past a certain state of
repair is not merely slow -- under the CVSA out-of-service criteria it is an
imminent hazard and is legally prohibited from operating at all.

So the ladder has four rungs, and the last one is a wall:

* **reduced power** -- the engine holds back and burns more for the work.
* **limp mode** -- that, plus a road-speed cap the driver cannot drive out of.
* **the last call** -- an advisory that names the number which stops the truck.
* **out of service** -- the truck may not be driven. It may still crawl clear
  of a live lane, because leaving a stricken truck stopped in traffic is the
  more dangerous rule, but the run does not continue under its own power.

The bands and every physical consequence live in ``sim/vehicle``
(``damage_band``, ``damage_derate_factor``, ``speed_cap_mph``,
``out_of_service``) so the model layer stays the single source of truth and
nothing here is spoken flavour over unchanged physics. This module is the
game layer around them: what the driver hears at each edge, how the cap winds
in, and what recovery costs.

Three rules shape the spoken side, all of them existing house rules:

* **Speak first, then bite.** Crossing a band announces the cap and opens it
  at the speed the truck already has, then winds it down at about 2 mph per
  second -- the same comfortable-braking figure the dropped-speed-limit grace
  uses. A cap that snapped would take the road away mid-sentence.
* **Both edges, both verbosities.** Every band speaks once when it begins and
  again when a repair drops back out of it, terse included. Without the
  downward edge a player cannot tell whether a repair cleared limp mode.
* **Band before number.** A warning leads with the band; a status readout
  gives both, so the number and its meaning never travel separately.

Recovery copies the out-of-fuel roadside rescue: not offered, not refusable,
real money and real game time. Who pays is where the two business statuses
part company, and they part sharply -- see ``_recover_out_of_service``.
"""

from __future__ import annotations

from ..models.business import player_pays_operating_costs
from ..models.cargo_condition import (
    CARGO_CLAIM_PCT,
    CARGO_EXCEPTION_PCT,
    CARGO_REJECT_PCT,
    cargo_condition_text,
    cargo_outcome,
)
from ..models.carrier_fleet import slip_seat_pool, slip_seats
from ..models.trucks import TRUCK_CATALOG
from ..sim.trip_models import FACILITY_GATE_ZONE_MI
from .driving_core import *

# The condition rungs, in the order a load passes them, for the in-drive cue.
CARGO_CUE_STEPS = (CARGO_EXCEPTION_PCT, CARGO_CLAIM_PCT, CARGO_REJECT_PCT)


def damage_band_clause(settings, truck) -> str:
    """The spoken band a damage number puts the truck in, or "" for none.

    Used by every readout that shows a damage figure, so "78 percent" is
    never heard without "limp mode" beside it.
    """
    band = truck.damage_band
    if band == DAMAGE_BAND_OUT_OF_SERVICE:
        return "out of service"
    if band in (DAMAGE_BAND_LIMP, DAMAGE_BAND_LAST_CALL):
        return f"limp mode, capped at {settings.speed_text(DAMAGE_LIMP_CAP_MPH)}"
    if band == DAMAGE_BAND_REDUCED:
        return "reduced power"
    return ""


def damage_summary_line(settings, truck, trip_damage: float) -> str | None:
    """The delivery summary's damage sentence, or None when nothing to say."""
    if trip_damage <= 1.0:
        return None
    clause = damage_band_clause(settings, truck)
    if not clause:
        return (
            f"The cargo run added {trip_damage:.0f} percent truck damage. "
            "Visit the garage when you can."
        )
    return (
        f"The cargo run added {trip_damage:.0f} percent truck damage. "
        f"The truck is at {truck.damage_pct:.0f} percent, {clause}. "
        "Repair it before the next run."
    )


def preventable_damage_charge(driving) -> tuple[float, float, str]:
    """The carrier's bill for a run it will rule preventable.

    Returns ``(deductible, reputation_hit, spoken_reason)``. A real carrier
    files an incident report and a safety committee rules the damage
    preventable or not; the preventable ones run progressive discipline and
    very often a deductible or a voided safety bonus. That is how a company
    driver feels damage in the wallet without being handed a repair invoice
    that is not theirs to pay -- the asymmetry the whole system rests on.

    Both numbers scale with the deepest band the run reached rather than the
    damage number at the gate, so patching the truck on the shoulder does not
    launder the run.
    """
    preventable = float(getattr(driving.truck, "preventable_damage_pct", 0.0))
    bands = int(getattr(driving, "_worst_damage_band", DAMAGE_BAND_NONE))
    if bands <= DAMAGE_BAND_NONE or preventable < 1.0:
        return 0.0, 0.0, ""
    # The share of the run's damage the committee would call preventable,
    # against the depth it reached. Damage taken reacting correctly to a
    # modelled hazard is not counted in ``preventable_damage_pct`` at all.
    share = min(1.0, preventable / max(1.0, DAMAGE_OUT_OF_SERVICE_PCT))
    deductible = PREVENTABLE_DAMAGE_DEDUCTIBLE * bands * share
    reputation = PREVENTABLE_REPUTATION_PER_BAND * bands
    reason = {
        DAMAGE_BAND_REDUCED: "the truck came back in reduced power",
        DAMAGE_BAND_LIMP: "the run finished in limp mode",
        DAMAGE_BAND_LAST_CALL: "the truck was within a hair of out of service",
        DAMAGE_BAND_OUT_OF_SERVICE: "the truck went out of service on the road",
    }[bands]
    return deductible, reputation, reason


def cargo_status_clause(truck) -> str:
    """The load's condition for a status readout: the words and the number."""
    condition = float(getattr(truck, "cargo_damage_pct", 0.0))
    if condition < 1.0:
        return "secure"
    return f"{cargo_condition_text(condition)}, {condition:.0f} percent"


class DamageBandMixin:
    # -- cargo condition ---------------------------------------------------------

    def _update_cargo_condition(self, dt: float) -> None:
        """Feed the bend to the freight, then say when it has cost something.

        The vehicle model has no map, so the road hands it the one thing it
        cannot know: how far past the posted advisory this bend is being
        taken. And a load that quietly degrades until the dock refuses it
        would be the worst kind of surprise for a player who cannot see the
        trailer -- so each rung speaks once, when it is crossed.
        """
        t = self.truck
        curve = self.trip.curve_at(self.trip.position_mi)
        t.corner_overspeed_mph = (
            max(0.0, t.speed_mph - curve.advisory_mph)
            if curve is not None and not curve.connector
            else 0.0
        )
        condition = t.cargo_damage_pct
        # The HIGHEST rung crossed, not the next one up. A collision can put a
        # load through all three at once, and walking them a frame apart would
        # fire three interrupting warnings inside a tenth of a second; the
        # driver needs the state they are actually in, said once.
        crossed = [step for step in CARGO_CUE_STEPS if condition >= step > self._cargo_cue_at]
        if crossed:
            self._cargo_cue_at = crossed[-1]
            self._announce_cargo_condition()

    def _announce_cargo_condition(self) -> None:
        t = self.truck
        outcome = cargo_outcome(t.cargo_damage_pct)
        words = cargo_condition_text(t.cargo_damage_pct)
        self.ctx.audio.play("ui/warning")
        if self._terse_speech():
            consequence = {
                "exception": "Exception on the bill.",
                "claim": "Claim likely.",
                "rejected": "The dock will refuse it.",
            }[outcome]
            message = f"Load {words}, {t.cargo_damage_pct:.0f} percent. {consequence}"
        else:
            consequence = {
                "exception": (
                    "The receiver will note an exception on the bill of lading and "
                    "hold back part of the pay."
                ),
                "claim": (
                    "This is claim territory now: the receiver will take it, and the "
                    "carrier will pay for what you broke."
                ),
                "rejected": (
                    "The dock will refuse a load in this state. You would arrive with "
                    "nothing to deliver and a claim for the whole of it."
                ),
            }[outcome]
            message = (
                f"The load has shifted hard and is {words}, {t.cargo_damage_pct:.0f} "
                f"percent. {consequence} Brake and corner gently from here."
            )
        self.ctx.say_event(message, interrupt=True)

    # -- the bands ---------------------------------------------------------------

    def _damage_band_clause(self) -> str:
        return damage_band_clause(self.ctx.settings, self.truck)

    def _update_damage_bands(self, dt: float) -> None:
        """Announce band edges, hold the cap, and run recovery at the wall."""
        t = self.truck
        band = t.damage_band
        # Settlement grades the run, not the moment it ended: a driver who
        # spent an hour in limp mode and then paid for a patch did something
        # to get there, and a clean arrival number would hide it.
        self._worst_damage_band = max(self._worst_damage_band, band)
        if band != self._damage_band:
            previous = self._damage_band
            self._damage_band = band
            self._announce_damage_band(band, previous)
            if band == DAMAGE_BAND_OUT_OF_SERVICE:
                self._out_of_service_creep_s = 0.0
        self._update_damage_cap(dt)
        if t.out_of_service:
            # A window to get clear of a live lane, then road service arrives
            # whether or not the driver used it. Coming to a stop ends the
            # wait at once: a driver who has pulled over should not sit there
            # listening to nothing happen.
            self._out_of_service_creep_s += dt
            if (
                t.speed_mph <= 1.0
                or self._out_of_service_creep_s >= OUT_OF_SERVICE_RECOVERY_GRACE_S
            ):
                self._recover_out_of_service()

    def _announce_damage_band(self, band: int, previous: int) -> None:
        terse = self._terse_speech()
        damage = self.truck.damage_pct
        cap = self.ctx.settings.speed_text(DAMAGE_LIMP_CAP_MPH)
        if band > previous:
            if band == DAMAGE_BAND_REDUCED:
                message = (
                    f"Reduced power. Damage {damage:.0f} percent."
                    if terse
                    else (
                        f"Reduced power. Damage is past {DAMAGE_DERATE_PCT:.0f} percent; "
                        "the engine is holding back and burning more fuel. Get it repaired."
                    )
                )
            elif band == DAMAGE_BAND_LIMP:
                message = (
                    f"Limp mode. Capped at {cap}."
                    if terse
                    else (
                        f"Limp mode. Damage is past {DAMAGE_LIMP_PCT:.0f} percent; the "
                        f"engine is winding down to a {cap} cap. Find a stop and repair."
                    )
                )
            elif band == DAMAGE_BAND_LAST_CALL:
                # The advisory that must name the wall. A player who is
                # surprised by the truck stopping was not warned properly.
                message = (
                    f"Damage {damage:.0f} percent. Out of service at "
                    f"{DAMAGE_OUT_OF_SERVICE_PCT:.0f}."
                    if terse
                    else (
                        f"Damage is past {DAMAGE_LAST_CALL_PCT:.0f} percent. At "
                        f"{DAMAGE_OUT_OF_SERVICE_PCT:.0f} percent the truck goes out of "
                        "service and cannot be driven at all. Stop and repair now."
                    )
                )
            else:
                message = self._out_of_service_message()
            self.ctx.audio.play("ui/warning")
        else:
            # Coming back down after a repair. Terse keeps the fact and drops
            # only the prose around it -- a driver who cannot hear that limp
            # mode cleared has no way to know the repair worked.
            if band == DAMAGE_BAND_NONE:
                message = (
                    f"Damage {damage:.0f} percent. Full power."
                    if terse
                    else f"Repair complete. Damage {damage:.0f} percent; full power restored."
                )
            elif band == DAMAGE_BAND_REDUCED:
                message = (
                    f"Reduced power. Damage {damage:.0f} percent."
                    if terse
                    else (
                        f"Damage {damage:.0f} percent. Limp mode is off; the truck is "
                        "still in reduced power."
                    )
                )
            else:
                message = (
                    f"Limp mode. Capped at {cap}."
                    if terse
                    else f"Damage {damage:.0f} percent. Still in limp mode, capped at {cap}."
                )
            self.ctx.audio.play("ui/notify")
        self.ctx.say_event(message, interrupt=True)

    def _out_of_service_message(self) -> str:
        """The wall landing: the fact, the cost, and the path forward.

        Never an unexplained inability to move. The driver is told what has
        happened, what it will take, and what to do in the meantime, in that
        order, in both verbosities.
        """
        creep = self.ctx.settings.speed_text(DAMAGE_CREEP_CAP_MPH)
        if self._terse_speech():
            return (
                f"Out of service. Damage {self.truck.damage_pct:.0f} percent. "
                f"{creep} to clear the lane, then brake to a stop. "
                f"Road service is coming: {self._recovery_cost_text()}."
            )
        return (
            f"Out of service. Damage is past {DAMAGE_OUT_OF_SERVICE_PCT:.0f} percent, "
            "and a truck in this state may not be driven. You have "
            f"{creep} left to get clear of the lane; brake to a stop on the "
            f"shoulder and road service will come to you. {self._recovery_cost_text()}."
        )

    def _recovery_cost_text(self) -> str:
        """What getting moving again will cost, said before it is charged."""
        if player_pays_operating_costs(self.ctx.profile.business_status):
            cost = self._roadside_repair_cost()
            return (
                f"The repair will cost about {cost:,.0f} dollars and most of "
                f"{BREAKDOWN_REPAIR_MIN / 60.0:.0f} hours"
            )
        return (
            "The carrier covers the bill, but dispatch grounds the tractor and "
            f"the wait runs about {GROUNDED_SWAP_MIN / 60.0:.0f} hours"
        )

    def _roadside_repair_cost(self) -> float:
        return road_repair_cost(
            self.truck.damage_pct, BREAKDOWN_REPAIR_DAMAGE_PCT, BREAKDOWN_CALLOUT_FEE
        )

    # -- the speed cap -----------------------------------------------------------

    def _damage_cap_target(self) -> float | None:
        """What the road-speed governor is winding toward, or None for free."""
        t = self.truck
        if t.out_of_service:
            return DAMAGE_CREEP_CAP_MPH
        if t.damage_pct >= DAMAGE_LIMP_PCT:
            return DAMAGE_LIMP_CAP_MPH
        return None

    def _limp_cap_suspended(self) -> bool:
        """Flows that are already braking own the speed; the cap stays out.

        An enforcement pull-over and the facility gate zone both have their
        own braking curve and their own spoken contract. Laying a second,
        winding cap over either would fight a stop that is already happening.
        """
        if self._pull_over is not None:
            return True
        if self.phase == DRIVE_PHASE_DELIVERY and self._destination_exit_taken:
            remaining = self.trip.total_miles - self.trip.position_mi
            return remaining <= FACILITY_GATE_ZONE_MI
        return False

    def _update_damage_cap(self, dt: float) -> None:
        t = self.truck
        target = self._damage_cap_target()
        if target is None or self._limp_cap_suspended():
            self._limp_cap_mph = None
            t.speed_cap_mph = None
            return
        if self._limp_cap_mph is None:
            # Open at the speed the truck already has, never below the target
            # itself: the announcement has just been heard and the wind-down
            # starts from here.
            self._limp_cap_mph = max(target, t.speed_mph)
        else:
            self._limp_cap_mph = max(target, self._limp_cap_mph - LIMP_CAP_RAMP_MPH_PER_S * dt)
        t.speed_cap_mph = self._limp_cap_mph

    def _announce_limp_cruise_cap(self) -> None:
        """Say once per engagement that limp mode, not the grade, owns the target.

        Mirrors the "cruise is flat out and still losing the grade" cue: the
        set speed is unreachable for a reason the driver cannot see, so name
        it and name what cruise is holding instead.
        """
        cap = self.truck.speed_cap_mph
        target = self._cruise_mph
        if cap is None or target is None or self._limp_cruise_said:
            return
        if target <= cap + 1.0 or self.truck.speed_mph < cap - 2.0:
            return
        self._limp_cruise_said = True
        speed_text = self.ctx.settings.speed_text
        message = (
            f"Limp mode. Holding {speed_text(cap)}."
            if self._terse_speech()
            else (
                f"Cruise cannot hold {speed_text(target)}; the truck is in limp mode. "
                f"Holding {speed_text(cap)}."
            )
        )
        self.ctx.say_event(message, interrupt=False)

    # -- recovery ---------------------------------------------------------------

    def _recover_out_of_service(self) -> None:
        """Get an out-of-service truck legal again. Where the statuses part.

        An owner-operator's truck is their property and nobody grounds it for
        them -- but nobody pays for it either, and the bill lands whether the
        money is there or not. A company driver is the other way round: the
        tractor is not theirs to gamble with, so the carrier takes it out of
        service and covers the repair, and what the driver spends is the day
        and their standing with dispatch. Continuing to run wrecked company
        iron is a DOT out-of-service violation the carrier eats, which is
        exactly why real carriers do not leave it to the driver.
        """
        if self._recovering or not self.truck.out_of_service:
            return
        self._recovering = True
        try:
            if player_pays_operating_costs(self.ctx.profile.business_status):
                self._roadside_repair_out_of_pocket()
            else:
                self._carrier_grounds_the_tractor()
        finally:
            self._recovering = False
        self._cancel_cruise()
        self._limp_cap_mph = None
        self._out_of_service_creep_s = 0.0
        # The recovery line IS the announcement for the band it lands in, so
        # the edge watcher must not speak it a second time.
        self._damage_band = self.truck.damage_band

    def _roadside_repair_out_of_pocket(self) -> None:
        """Owner-operator: their truck, their bill, and it is not refusable."""
        p = self.ctx.profile
        t = self.truck
        cost = self._roadside_repair_cost()
        p.money -= cost  # can go negative: the truck cannot move otherwise
        t.recover_from_breakdown(BREAKDOWN_REPAIR_DAMAGE_PCT)
        self.trip.game_minutes += BREAKDOWN_REPAIR_MIN
        self.hos.on_duty(BREAKDOWN_REPAIR_MIN)
        self.ctx.audio.play("ui/error")
        if self._terse_speech():
            message = (
                f"Roadside repair, {cost:,.0f} dollars. Damage {t.damage_pct:.0f} percent, "
                f"{self._damage_band_clause()}. You have {p.money:,.0f} dollars."
            )
        else:
            message = (
                f"Roadside repair got the truck moving for {cost:,.0f} dollars; damage "
                f"is down to {t.damage_pct:.0f} percent, still in reduced power. It took "
                f"{BREAKDOWN_REPAIR_MIN / 60.0:.0f} hours and it is now "
                f"{clock_text(self.trip.local_hour)}. You have {p.money:,.0f} dollars. "
                f"Press {self.ctx.control_hint('engine')} to restart the engine, and "
                "repair it properly at the next stop."
            )
        self.ctx.say_event(message, interrupt=True)

    def _carrier_grounds_the_tractor(self) -> None:
        """Company driver: the carrier takes the truck, and the driver waits.

        No money changes hands. What the driver loses is the hours, a chunk of
        standing, and a recorded preventable-equipment event on their record --
        the pattern that follows from repeating this belongs to the career and
        dispatch-trust layer, which reads the event; nothing here terminates
        anybody.
        """
        p = self.ctx.profile
        p.career.reputation = max(0.0, p.career.reputation - BREAKDOWN_REPUTATION_HIT)
        self._record_equipment_event()
        grounded = self._tractor_label()
        spare = self._draw_yard_spare()
        self.trip.game_minutes += GROUNDED_SWAP_MIN
        self.hos.on_duty(GROUNDED_SWAP_MIN)
        self.ctx.audio.play("ui/error")
        if spare is not None:
            handover = (
                f"Dispatch put you in the {spare} for the rest of this run"
                if not self._terse_speech()
                else f"You are in the {spare}"
            )
        else:
            # No spare to draw: the yard sends a road crew instead, and the
            # tractor goes to the shop when the driver gets in.
            self.truck.recover_from_breakdown(BREAKDOWN_REPAIR_DAMAGE_PCT)
            handover = (
                "The road crew put it right enough to finish the run, and the "
                "shop takes it when you get in"
                if not self._terse_speech()
                else "Patched to finish the run"
            )
        if self._terse_speech():
            message = (
                f"Grounded. The carrier pays. {handover}. Damage "
                f"{self.truck.damage_pct:.0f} percent. "
                f"Dispatch logged preventable equipment damage."
            )
        else:
            message = (
                f"Dispatch has taken the {grounded} out of service; a truck in this "
                "state is not yours to keep driving and the carrier will not have it "
                f"on the road. The carrier covers the bill. {handover}. That cost "
                f"{GROUNDED_SWAP_MIN / 60.0:.0f} hours and it is now "
                f"{clock_text(self.trip.local_hour)}. Damage on the truck you are in "
                f"is {self.truck.damage_pct:.0f} percent. Dispatch logged preventable "
                "equipment damage against your record; a pattern of it costs the seat. "
                f"Press {self.ctx.control_hint('engine')} to restart the engine."
            )
        self.ctx.say_event(message, interrupt=True)

    def _record_equipment_event(self) -> None:
        """Leave the event on the career for the trust and termination layer.

        Deliberately just a counter and a reputation hit: dispatch-trust
        regression and losing the seat are owned elsewhere, and there must
        not be two paths to either.
        """
        increment_stat(self.ctx.profile, "preventable_equipment_damage")

    def _tractor_label(self) -> str:
        model = TRUCK_CATALOG.get(self.ctx.profile.active_truck_key())
        return model.label if model is not None else "tractor"

    def _draw_yard_spare(self) -> str | None:
        """Swap a slip-seating driver into another of the yard's spares.

        Reuses the existing slip-seat pool rather than inventing a parallel
        one, and the spare is real used equipment carrying its own wear -- the
        point of the consequence is that it is plausibly a worse truck than
        the one just grounded. Returns the spoken label, or None when there is
        nothing to move into: a senior driver holds a dedicated seat that the
        assignment layer would hand straight back, and a yard whose every
        spare is also unfit has none to give.
        """
        p = self.ctx.profile
        if not slip_seats(p):
            return None
        current = p.active_truck_key()
        candidates = [key for key in slip_seat_pool(p) if key != current]
        if not candidates:
            return None

        def damage_of(key: str) -> float:
            record = p.truck_conditions.get(key)
            return float(record.get("damage_pct", 0.0)) if record else 0.0

        pick = min(candidates, key=damage_of)
        if damage_of(pick) >= DAMAGE_OUT_OF_SERVICE_PCT:
            return None  # the yard has nothing fit either
        old = self.truck
        p.store_truck_condition(old)  # the grounded tractor keeps its damage
        p.truck = pick
        if p.truck_conditions.get(pick) is None:
            p.provision_truck_condition(pick)
            p.truck_damage_pct = GROUNDED_SPARE_DAMAGE_PCT
        self.truck = TruckState(specs=p.truck_specs())
        self.truck.cargo_kg = old.cargo_kg
        self.truck.trailer_attached = old.trailer_attached
        self.truck.transmission.automatic = old.transmission.automatic
        self.truck.odometer_mi = old.odometer_mi
        p.load_truck_condition(self.truck)
        self.truck.recover_from_breakdown(self.truck.damage_pct)
        self.truck.set_air_ready(parking_brake=True)
        model = TRUCK_CATALOG.get(pick)
        return model.label if model is not None else "yard spare"
