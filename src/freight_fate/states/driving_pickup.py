# ruff: noqa: F403,F405
"""Pickup-arrival flow for the deadhead driving phase."""

from __future__ import annotations

from .driving_core import *


class DrivingPickupMixin:
    def _handle_pickup_gate(self) -> None:
        if self.truck.speed_mph <= DOCKING_MAX_MPH:
            self._open_pickup_arrival()
            return
        if self.truck.speed_mph <= DELIVERY_PARK_MPH:
            self._handle_pickup_creep()
            return
        if self._arrival_stop_said:
            return
        self._arrival_stop_said = True
        speed_control_paused = self._pause_speed_control()
        self.ctx.audio.play("ui/warning")
        self._set_status("Pickup ahead: slow down and come to a complete stop.")
        message = (
            f"Pickup ahead: {self._pickup_facility_text()}."
            if self._terse_speech()
            else (
                f"Pickup ahead: {self._pickup_facility_text()}. "
                "Slow down and come to a complete stop at the gate."
            )
        )
        self.ctx.say_event(message, interrupt=True)
        if speed_control_paused:
            self._announce_pickup_speed_control_pause()

    def _handle_pickup_creep(self) -> None:
        if self._arrival_full_stop_said:
            return
        self._arrival_full_stop_said = True
        speed_control_paused = self._pause_speed_control()
        self.ctx.audio.play("ui/notify", volume=0.7)
        self._set_status("Pickup gate: stop to check in.")
        self.ctx.say_event(f"At {self._pickup_facility_text()}. Stop to check in.", interrupt=False)
        if speed_control_paused:
            self._announce_pickup_speed_control_pause()

    def _announce_pickup_speed_control_pause(self) -> None:
        self.ctx.say_event(
            "Automatic speed control paused for pickup. It will resume after "
            "you depart with the load.",
            interrupt=False,
        )

    def _open_pickup_arrival(self) -> None:
        if self._arrival_menu_open:
            return
        from .city import PickupFacilityState, pickup_snapshot

        p = self.ctx.profile
        self._arrival_menu_open = True
        speed_control_paused = self._pause_speed_control()
        self.truck.throttle = 0.0
        self.truck.brake = 1.0
        self.truck.set_parking_brake()
        p.truck_fuel_gal = self.truck.fuel_gal
        p.truck_damage_pct = self.truck.damage_pct
        p.game_hours += self.trip.game_minutes / 60.0
        p.market.advance_to(p.market_day())
        p.active_trip = pickup_snapshot(
            self.job,
            air_brake=self.truck.air_brake_snapshot(),
            engine_on=self.truck.engine_on,
            speed_control_armed=self._speed_control_armed,
            speed_control_target_mph=self._speed_control_target_mph,
        )
        self.ctx.save_profile()
        if speed_control_paused:
            self._announce_pickup_speed_control_pause()
        self._set_status("Parked at pickup. Check in and load.")
        self.ctx.replace_state(PickupFacilityState(self.ctx, self.job, driving=self))

    def _pickup_facility_text(self) -> str:
        return self.job.origin_facility_text()

    def _pickup_progress_summary(self) -> str:
        return (
            f"{self.trip.remaining_miles:.1f} miles remaining of "
            f"{self.trip.total_miles:.1f} to pickup at "
            f"{self._pickup_facility_text()}."
        )
