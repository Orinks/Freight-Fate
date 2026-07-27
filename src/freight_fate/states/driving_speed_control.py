# ruff: noqa: F403,F405
"""Shared lifecycle helpers for the driving state's speed controllers."""

from __future__ import annotations

from .driving_core import KEEPER_MIN_MPH


class SpeedControlStateMixin:
    def _clear_cruise(self, *, preserve_exit_cap: bool = False) -> None:
        self._cruise_mph = None
        self._cruise_throttle = 0.0
        self._cruise_applied = 0.0
        self._cruise_trim = 0.0
        if self._cruise_jake_on:
            # Hand the retarder back with the cruise session, but only when
            # cruise raised it -- the driver's own jake switch stays put.
            self._cruise_jake_on = False
            self.truck.engine_brake = False
        self._cruise_snubbing = False
        self._cruise_grade_said = 0
        self._cruise_beaten_s = 0.0
        if not preserve_exit_cap:
            self._cruise_exit_mph = None
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._acc_limit_capped = False

    def _clear_keeper(self) -> None:
        self._keeper_mph = None
        self._keeper_throttle = 0.0
        self._keeper_zone = ""

    def _disarm_speed_control(self) -> None:
        self._clear_cruise()
        self._clear_keeper()
        self._speed_control_armed = False
        self._speed_control_target_mph = None

    def _pause_speed_control(self) -> bool:
        """Pause an armed session at a planned stop without forgetting it."""
        if not self._speed_control_armed:
            return False
        was_active = self._cruise_mph is not None or self._keeper_mph is not None
        self._clear_cruise()
        self._clear_keeper()
        return was_active

    def _restore_speed_control_session(self, *, armed: bool, target_mph: float | None) -> None:
        self._clear_cruise()
        self._clear_keeper()
        self._speed_control_armed = armed
        self._speed_control_target_mph = target_mph if armed else None

    def _resume_speed_control_if_ready(self, *, braking: bool) -> None:
        """Resume a paused job-scoped session once the player is rolling again."""
        if (
            not self._speed_control_armed
            or self._cruise_mph is not None
            or self._keeper_mph is not None
        ):
            return
        t = self.truck
        if t.emergency_brake:
            self._disarm_speed_control()
            self.ctx.say_event("Automatic speed control canceled.", interrupt=False)
            return
        if (
            braking
            or t.air_brakes_holding
            or not t.engine_on
            or t.stalled
            or t.speed_mph < KEEPER_MIN_MPH
        ):
            return
        limit, zone_reason = self.trip.speed_limit_at(self.trip.position_mi)
        if zone_reason is not None:
            if not self.ctx.settings.speed_keeper:
                return
            self._engage_keeper(limit, zone_reason, target_mph=limit, announce=False)
            self.ctx.say_event(
                "Automatic speed control resuming. Speed keeper holding "
                f"{self.ctx.settings.speed_text(self._keeper_mph)} through the "
                f"{zone_reason} zone.",
                interrupt=False,
            )
            return
        self._engage_cruise(self._speed_control_target_mph or limit, transition=True)

    def _cancel_cruise(self, *, preserve_session: bool = False) -> None:
        if preserve_session:
            self._clear_cruise(preserve_exit_cap=True)
        else:
            self._disarm_speed_control()

    def _cancel_keeper(self, *, preserve_session: bool = False) -> None:
        if preserve_session:
            self._clear_keeper()
        else:
            self._disarm_speed_control()

    def _construction_limit_ahead(self) -> float | None:
        """A lower work-zone limit inside the player's advance-warning window."""
        if not self._speed_control_armed or not self.ctx.settings.speed_keeper:
            return None
        lookahead_mi = self.trip._zone_warning_lookahead_mi()
        zone = self.trip.next_zone_within(lookahead_mi)
        if zone is None or zone.reason != "construction":
            return None
        current_limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
        return zone.limit_mph if zone.limit_mph < current_limit else None
