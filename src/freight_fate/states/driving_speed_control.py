# ruff: noqa: F403,F405
"""Shared lifecycle helpers for the driving state's speed controllers."""

from __future__ import annotations


class SpeedControlStateMixin:
    def _clear_cruise(self) -> None:
        self._cruise_mph = None
        self._cruise_throttle = 0.0
        self._cruise_applied = 0.0
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

    def _cancel_cruise(self, *, preserve_session: bool = False) -> None:
        if preserve_session:
            self._clear_cruise()
        else:
            self._disarm_speed_control()

    def _cancel_keeper(self, *, preserve_session: bool = False) -> None:
        if preserve_session:
            self._clear_keeper()
        else:
            self._disarm_speed_control()
