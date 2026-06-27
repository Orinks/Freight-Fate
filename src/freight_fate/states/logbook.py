"""Spoken in-cab Record of Duty Status screens."""

from __future__ import annotations

from ..sim.hos import clock_text, duration_text, duty_status_label
from .base import MenuItem, MenuState


def logbook_lines(ctx, driving=None) -> list[str]:
    p = ctx.profile
    now = _current_hour(p, driving)
    log = p.duty_log
    day_start = int(now // 24.0) * 24.0
    totals = log.totals_since(day_start, now)
    lines = [
        f"Current duty status: {duty_status_label(log.current_status())}",
        p.hos.summary(ctx.settings.hos_mode).rstrip("."),
        "Today's totals: "
        f"driving {duration_text(totals['driving'])}, "
        f"on duty not driving {duration_text(totals['on_duty_not_driving'])}, "
        f"off duty {duration_text(totals['off_duty'])}, "
        f"sleeper berth {duration_text(totals['sleeper_berth'])}.",
    ]
    recent = log.recent(8)
    if not recent:
        lines.append("No logbook entries yet.")
        return lines
    lines.append("Recent logbook entries:")
    for segment in recent:
        note = f", {segment.note}" if segment.note else ""
        lines.append(
            f"{clock_text(segment.start_hour)} to {clock_text(segment.end_hour)}, "
            f"{duty_status_label(segment.status)}, "
            f"{duration_text(segment.duration_hours)}, "
            f"{segment.location}{note}."
        )
    return lines


def traffic_stop_logbook_summary(ctx, driving) -> str:
    lines = logbook_lines(ctx, driving)
    if len(lines) <= 3:
        return "Logbook has no recent duty entries yet."
    latest = lines[-1]
    totals = lines[2]
    totals = totals.removeprefix("Today's totals: ")
    return f"Logbook shows {totals} Latest entry: {latest}"


class LogbookState(MenuState):
    """A reviewable spoken Record of Duty Status."""

    title = "Logbook"
    intro_help = (
        "Use up and down arrows to review logbook lines. Enter repeats the "
        "current line. Escape goes back."
    )

    def __init__(self, ctx, driving=None) -> None:
        super().__init__(ctx)
        self.driving = driving

    def announce_entry(self) -> None:
        self.ctx.say(f"{self.title}. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(line, lambda line=line: self.ctx.say(line),
                     help="Repeat this logbook line.")
            for line in logbook_lines(self.ctx, self.driving)
        ]
        items.append(MenuItem("Back", self.go_back, help="Return to the previous menu."))
        return items


def _current_hour(profile, driving=None) -> float:
    if driving is None:
        return profile.game_hours
    return profile.game_hours + driving.trip.game_minutes / 60.0
