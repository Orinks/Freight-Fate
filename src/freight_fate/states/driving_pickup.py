# ruff: noqa: F403,F405
"""Pickup-arrival flow for the deadhead driving phase."""

from __future__ import annotations

from .base import TimedMessageState
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
        # Store the whole record, not just fuel and damage: this line also
        # accrues brake and engine wear, which the flat names do not carry.
        p.store_truck_condition(self.truck)
        # Rolling to the check-in lane takes time and is on-duty time.
        p.game_hours += (self.trip.game_minutes + STOP_PULL_IN_MIN) / 60.0
        p.hos.on_duty(STOP_PULL_IN_MIN)
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
        self._set_status("Pulling into pickup. Check-in menu opening.")

        def complete() -> None:
            self._set_status("Parked at pickup. Check in and load.")
            self.ctx.replace_state(PickupFacilityState(self.ctx, self.job, driving=self))

        # The pull-in is its own short spoken beat rather than a jump straight
        # to the check-in menu, so the arrival is something the driver hears
        # happen instead of a menu appearing under them.
        self.ctx.replace_state(
            TimedMessageState(
                self.ctx,
                title="Pulling into pickup",
                message=(
                    f"Pulling into {self._pickup_facility_text()}. "
                    "Setting the brakes and rolling to the check-in lane."
                ),
                status="Pulling into the pickup facility. Please wait.",
                seconds=STOP_PULL_IN_WAIT_S,
                on_complete=complete,
                sound_key="ui/notify",
            )
        )

    def _pickup_facility_text(self) -> str:
        return self.job.origin_facility_text()

    def _pickup_progress_summary(self) -> str:
        # Spoken distances go through the unit setting; a player on metric must
        # not hear miles here just because this handler moved modules.
        s = self.ctx.settings
        return (
            f"{s.distance_text(self.trip.remaining_miles, precise=True)} remaining of "
            f"{s.distance_text(self.trip.total_miles, precise=True)} to pickup at "
            f"{self._pickup_facility_text()}."
        )
