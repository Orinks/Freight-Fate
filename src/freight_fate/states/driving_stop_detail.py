from __future__ import annotations

from typing import TYPE_CHECKING

from ..sim.trip_models import RoadStop
from .base import MenuItem, MenuState
from .driving_core import POI_ACTION_LABELS, POI_SERVICE_LABELS, _join_phrase

if TYPE_CHECKING:
    from .driving import DrivingState

# Matches Trip.eta_game_hours: parked or crawling assumes a highway pace.
FALLBACK_MPH = 55.0


class StopDetailState(MenuState):
    """Full details for one upcoming route stop, opened from the Map screen.

    Mirrors the dispatch board's job details view: each fact is its own
    menu row, then the plan/cancel buttons, then Back.
    """

    title = "Stop details"
    intro_help = (
        "Use up and down arrows to review each detail line; Home and End "
        "jump to the first and last row. Enter repeats detail lines or "
        "activates the planning buttons. Escape returns to the map screen."
    )

    def __init__(self, ctx, driving: DrivingState, stop: RoadStop) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.stop = stop

    def enter(self) -> None:
        self.items = self.build_items()
        self.index = min(self.index, max(0, len(self.items) - 1))
        self.ctx.audio.play(self.open_sound_key)
        self.announce_entry()

    def announce_entry(self) -> None:
        self.ctx.say(f"Stop details. {self.intro_help} {self.current_text()}")

    def current_help(self) -> str:
        return f"{self.intro_help} {super().current_help()}"

    def build_items(self) -> list[MenuItem]:
        trip = self.driving.trip
        items = [
            MenuItem(
                line,
                lambda line=line: self.ctx.say(line),
                help="This is a stop detail line. Press Enter to repeat it.",
            )
            for line in self._detail_lines()
        ]
        planned = trip.planned_stop_key
        if trip.is_planned(self.stop):
            items.append(
                MenuItem(
                    f"Cancel planned stop at {self.stop.name}",
                    self._cancel,
                    help="Forget this planned stop. Announcements go back to normal.",
                )
            )
        else:
            move_note = (
                " You already have a planned stop; you'll be asked to confirm moving it here."
                if planned is not None
                else ""
            )
            items.append(
                MenuItem(
                    f"Plan to stop at {self.stop.name}",
                    self._plan,
                    help="Remember this stop. Announcements will call it your "
                    f"planned stop so you know when to take the exit.{move_note}",
                    # _plan (or the move confirmation) plays its own chime.
                    select_sound=None,
                )
            )
        items.append(MenuItem("Back", self.go_back, help="Return to the map screen."))
        return items

    def _detail_lines(self) -> list[str]:
        stop = self.stop
        trip = self.driving.trip
        settings = self.ctx.settings
        ahead = max(0.0, stop.at_mi - trip.position_mi)
        lines = [f"Stop: {trip.planned_prefix(stop)}{stop.spoken_name}."]
        if stop.exit_label:
            lines.append(f"Exit: {stop.exit_label}.")
        lines.append(f"Distance: {settings.distance_text(ahead)} ahead.")
        offers = [
            POI_ACTION_LABELS[action] for action in stop.actions if action in POI_ACTION_LABELS
        ]
        services = [
            POI_SERVICE_LABELS.get(service, service.replace("_", " ")) for service in stop.services
        ]
        if offers:
            lines.append(f"Offers: {_join_phrase(offers)}.")
        if services:
            lines.append(f"Listed services: {_join_phrase(services)}.")
        if not offers and not services:
            lines.append("Services not listed.")
        if stop.parking_text:
            lines.append(f"Parking: {stop.parking_text}.")
        lines.append(self._eta_line(ahead))
        return lines

    def _eta_line(self, ahead: float) -> str:
        # Same rule as Trip.eta_game_hours, over the distance to this stop.
        speed = self.driving.truck.speed_mph
        trip = self.driving.trip
        if speed >= trip.ETA_MIN_MPH:
            mph = speed
            basis = "at your current speed"
        else:
            mph = FALLBACK_MPH
            basis = "at a typical highway pace"
        eta_h = ahead / max(1.0, mph)
        hos_note = self.driving.hos.arrival_note(self.ctx.settings.hos_mode, eta_h * 60.0)
        return f"Estimated time to reach it: {eta_h:.1f} hours {basis}.{hos_note}"

    def _plan(self) -> None:
        trip = self.driving.trip
        if trip.planned_stop_key is not None and not trip.is_planned(self.stop):
            # A different stop is already planned: confirm before moving it.
            self.ctx.push_state(ConfirmMovePlanState(self.ctx, self.driving, self.stop))
            return
        self._set_planned_stop()

    def _set_planned_stop(self) -> None:
        self.driving.trip.planned_stop_key = self.stop.key
        self.ctx.audio.play("ui/notify")
        self.refresh()
        self.ctx.say(
            f"Planned stop set: {self.stop.spoken_name}. You will hear it "
            "called your planned stop as you approach."
        )

    def _cancel(self) -> None:
        self.driving.trip.planned_stop_key = None
        self.refresh()
        self.ctx.say("Planned stop canceled.")


class ConfirmMovePlanState(MenuState):
    """Yes/No guard shown when planning a stop while another stop is planned.

    Names the current planned stop and how far ahead it is, then asks whether
    to move the plan here. Lands on "Yes" so one Enter completes the move the
    player just asked for.
    """

    title = "Move planned stop?"
    intro_help = (
        "Use up and down arrows to navigate, Enter to select. "
        "Escape keeps your current planned stop."
    )

    def __init__(self, ctx, driving: DrivingState, stop: RoadStop) -> None:
        super().__init__(ctx)
        self.driving = driving
        self.stop = stop

    def _planned_stop(self) -> RoadStop | None:
        return self.driving.trip.planned_stop

    def _ahead_text(self, stop: RoadStop) -> str:
        ahead = max(0.0, stop.at_mi - self.driving.trip.position_mi)
        return self.ctx.settings.distance_text(ahead)

    def announce_entry(self) -> None:
        current = self._planned_stop()
        where = (
            f"{current.spoken_name}, {self._ahead_text(current)} ahead"
            if current is not None
            else self.driving.trip.planned_stop_label
        )
        self.ctx.say(
            f"{self.title} You already have a planned stop at {where}. "
            f"Move your plan to {self.stop.spoken_name}, "
            f"{self._ahead_text(self.stop)} ahead? {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        current = self._planned_stop()
        keep_name = (
            current.spoken_name if current is not None else self.driving.trip.planned_stop_label
        )
        return [
            MenuItem(
                f"Yes, move plan to {self.stop.spoken_name}",
                self._confirm,
                help="Move your planned stop to this one.",
            ),
            MenuItem(
                f"No, keep planned stop at {keep_name}",
                self.go_back,
                help="Return to the stop details without moving your plan.",
            ),
        ]

    def _confirm(self) -> None:
        self.driving.trip.planned_stop_key = self.stop.key
        # Popping re-enters the detail screen, which now shows the Cancel button.
        self.ctx.pop_state()
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"Planned stop moved to {self.stop.spoken_name}. You will hear it "
            "called your planned stop as you approach.",
            interrupt=True,  # cut the detail screen's re-entry announcement
        )
