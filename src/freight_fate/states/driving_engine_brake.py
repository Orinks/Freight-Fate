# ruff: noqa: F403,F405
"""No-engine-brake zones: town noise ordinances around route cities.

Engine brakes are legal under federal and state law; what exists in the real
world is hundreds of municipal noise ordinances, posted NO ENGINE BRAKE at
the city limits, with exemptions for emergencies -- and the legitimate use of
the retarder, holding a heavy truck back on a real downgrade, stays legal
everywhere. Fines run roughly 100 to 500 dollars and escalate for repeat
offenders (LegalClarity municipal-ordinance survey, 2026; e.g. Snyder, Texas
ordinance 1043). The game maps those ordinances onto the same urban radius
that already lowers the speed limit near a route city.

A blind player cannot see the sign, so the spoken cue is the sign: the zone
announces itself ahead when the retarder is on, a violation warns with a
grace window before any money moves, and the citation names the amount and
the reason.
"""

from __future__ import annotations

from .driving_core import *

# How far out the spoken NO ENGINE BRAKE sign reads when the retarder is on.
JAKE_ZONE_WARN_MI = 2.0
# Real seconds between the violation warning and the citation -- time to hear
# the warning and reach the switch, mirroring the hazard reaction windows.
JAKE_ZONE_GRACE_S = 10.0
# Municipal-ordinance range, escalating per citation and capped at the top.
JAKE_ZONE_FINES = (150.0, 300.0, 500.0)
# A descent a driver genuinely needs the retarder for is exempt everywhere.
# Matches GRADE_WARN_CLEAR_PCT: under this, the G key calls the road level,
# so the exemption and the spoken grade readout agree.
JAKE_ZONE_EXEMPT_GRADE_PCT = 2.0
# Below this the retarder is not barking at road speed; a truck creeping a
# gate queue or parked with the switch on is not what the ordinance is for.
JAKE_ZONE_MIN_MPH = 10.0


class EngineBrakeZoneMixin:
    def _update_engine_brake_zone(self, dt: float) -> None:
        """Warn, then fine, for engine braking inside a town's ban zone."""
        t = self.truck
        if self._ramp_mi is not None or self.trip.finished or self._pull_over is not None:
            return
        city = self.trip.engine_brake_ban_at(self.trip.position_mi)
        if city is not None:
            # A real driver flips engine-brake mode off at the town line; the
            # assists do the same before any driver-fault question is asked.
            self._release_assist_jake_in_zone(city)
        else:
            self._assist_zone_cue_key = None
        # The switch alone is not the offense; the bark is. The vehicle already
        # knows whether the retarder is genuinely retarding (stage selected,
        # engine on, off the fuel, in gear), so ask it rather than re-deriving.
        barking = t.jake_retard_torque_nm() > 0.0 and t.speed_mph >= JAKE_ZONE_MIN_MPH
        # Cruise and the curve assist raise the retarder themselves and release
        # it themselves -- and inside a zone they have just released it above,
        # so an assist bark never reaches the fine path. Auto mode on an AMT is
        # different: the driver armed the stalk with J, so its bark is theirs.
        driver_owns_jake = barking and self._cruise_jake_stage == 0 and not self._curve_assist_jake
        if city is None:
            self._jake_violation_deadline_s = None
            self._jake_citation_latched = False
            self._maybe_warn_jake_zone_ahead(driver_owns_jake)
            return
        if not driver_owns_jake or self._jake_zone_exempt():
            self._jake_violation_deadline_s = None
            if not t.engine_brake:
                # The engagement is over; a fresh one can earn a fresh citation.
                self._jake_citation_latched = False
            return
        if self._jake_citation_latched:
            return  # one citation per continuous engagement
        if self._jake_violation_deadline_s is None:
            if city in self._jake_zone_grace_used:
                # The grace window is one chance to comply, not a renewable
                # exemption. Flicking the switch off just before the timer
                # expires and straight back on used to draw warnings forever
                # and never a fine; coming back on the jake in the same town
                # is now an immediate citation.
                self._jake_citation_latched = True
                self._fine_engine_braking(city)
                return
            self._jake_zone_grace_used.add(city)
            self._jake_violation_deadline_s = JAKE_ZONE_GRACE_S
            self._speak_jake_zone_warning(city)
            return
        self._jake_violation_deadline_s -= dt
        if self._jake_violation_deadline_s <= 0.0:
            self._jake_violation_deadline_s = None
            self._jake_citation_latched = True
            self._fine_engine_braking(city)

    def _assist_jake_allowed(self) -> bool:
        """May cruise or the curve assist raise the retarder here?

        Not inside a town's ban zone -- the assists respect the posted sign
        the way a driver flips engine-brake mode off in town -- except where
        the ordinance's own carve-outs apply: a real downgrade or an
        emergency, where the retarder is the safe tool everywhere.
        """
        if self.trip.engine_brake_ban_at(self.trip.position_mi) is None:
            return True
        return self._jake_zone_exempt()

    def _on_downgrade(self) -> bool:
        """Is the road under the truck a real downgrade?

        The one question that decides whether an assist may reach for the
        retarder at all. Holding a loaded truck back on a grade is sustained
        speed control, which is what the engine brake is built for and the one
        use every noise ordinance leaves legal. Slowing to a target speed --
        for a bend, a ramp, a lower posted limit, a lead vehicle -- is the
        service brakes' job, because only the drums give the precise control
        that needs, and a retarder drives the tractor's rear wheels alone.

        JAKE_ZONE_EXEMPT_GRADE_PCT is the same line the ordinance carve-out
        and the spoken G readout already draw between level road and a grade,
        so a driver hearing "level" never hears a retarder answering a grade.
        """
        return self.trip.grade_at(self.trip.position_mi) * 100.0 <= -JAKE_ZONE_EXEMPT_GRADE_PCT

    def _release_assist_jake_in_zone(self, city: str) -> None:
        """Drop an assist-raised retarder at the town line.

        Runs every frame inside a zone; releasing is idempotent and the
        raise gates keep the assists from reaching for it again. Spoken once
        per zone, only when a retarder audibly stops -- the note cutting out
        with no explanation is the confusing part -- and never in terse
        speech, which skips advisory-class cues (no money is at risk here).
        """
        cruise_owns = self._cruise_jake_stage > 0
        if not (cruise_owns or self._curve_assist_jake) or not self.truck.engine_brake:
            return
        if self._jake_zone_exempt():
            return  # a real downgrade or emergency: safety wins in town too
        self.truck.engine_brake_stage = 0
        if cruise_owns:
            self._cruise_jake_stage = 0
        self._curve_assist_jake = False
        if self._assist_zone_cue_key == city or self._terse_speech():
            return
        self._assist_zone_cue_key = city
        spoken = self.ctx.world.spoken_city(city, qualified=False)
        if cruise_owns:
            message = (
                f"No engine brake zone in {spoken}. Cruise is holding the "
                "engine brake off and using the brakes."
            )
        else:
            message = (
                f"No engine brake zone in {spoken}. The curve assist is "
                "using the brakes instead of the engine brake."
            )
        self.ctx.audio.play("ui/notify", volume=0.6)
        self.ctx.say_event(message, interrupt=False)

    def _jake_zone_exempt(self) -> bool:
        """The ordinance's own carve-outs: emergencies and real downgrades."""
        # A live hazard warning or the emergency brake is the game's "avoiding
        # imminent danger" -- every well-drafted ordinance excuses that.
        if self.truck.emergency_brake or self._hazard_deadline is not None:
            return True
        return self._on_downgrade()

    def _maybe_warn_jake_zone_ahead(self, driver_owns_jake: bool) -> None:
        """Read the NO ENGINE BRAKE sign out loud while it still helps.

        Only when the driver's own retarder is on: with it off there is
        nothing to do, and every route city would otherwise add a callout on
        top of the urban limit changes already announced there. Terse speech
        skips the advisory -- the in-zone warning still comes before any fine,
        so a terse driver risks nothing but a later cue.
        """
        if not driver_owns_jake or self._terse_speech():
            return
        ahead = self.trip.next_engine_brake_ban(JAKE_ZONE_WARN_MI)
        if ahead is None:
            return
        start_mi, city = ahead
        key = f"{start_mi:.1f}"
        if key == self._jake_zone_warned_key:
            return
        self._jake_zone_warned_key = key
        distance = self.ctx.settings.distance_text(start_mi - self.trip.position_mi)
        spoken = self.ctx.world.spoken_city(city, qualified=False)
        self.ctx.audio.play("ui/notify", volume=0.6)
        self.ctx.say_event(
            f"No engine brake zone in {distance}, coming into {spoken}. "
            "Switch the engine brake off before the zone.",
            interrupt=False,
        )

    def _speak_jake_zone_warning(self, city: str) -> None:
        """The warning that always precedes the first fine -- the audio sign."""
        self.ctx.audio.play("ui/warning")
        self.ctx.controller.rumble.alert()
        if self._terse_speech():
            message = "No engine brake zone. Switch it off."
        else:
            spoken = self.ctx.world.spoken_city(city, qualified=False)
            hint = self.ctx.control_hint("engine_brake")
            message = (
                f"No engine brakes in {spoken}; local noise rules. Switch the "
                f"engine brake off with {hint} or you will be fined."
            )
        self.ctx.say_event(message, interrupt=True)

    def _fine_engine_braking(self, city: str) -> None:
        """The citation: paid on the spot, escalating like repeat offenses do."""
        fine = JAKE_ZONE_FINES[min(self.jake_zone_fines, len(JAKE_ZONE_FINES) - 1)]
        self.jake_zone_fines += 1
        self.jake_fines_paid += fine
        self.ctx.profile.money -= fine  # can go negative; never a game over
        # A municipal noise ordinance is not an FMCSA serious violation, so it
        # never moves the suspension ladder -- but it is still a citation on
        # the record, and the next citation of any kind costs more for it.
        self.ctx.profile.driving_record.record_citation(fine)
        self.ctx.audio.play("ui/error")
        self.ctx.controller.rumble.alert()
        if self._terse_speech():
            message = f"Engine brake citation: {fine:,.0f} dollars."
        else:
            spoken = self.ctx.world.spoken_city(city, qualified=False)
            message = (
                f"A local officer cites you for engine braking in {spoken}: "
                f"a {fine:,.0f} dollar fine under the town noise rules, paid "
                "on the spot."
            )
        self.ctx.say_event(message, interrupt=True)
