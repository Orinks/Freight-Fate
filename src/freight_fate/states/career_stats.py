"""Career stats screen: the terminal's driver record as a reviewable menu."""

from __future__ import annotations

from .base import MenuItem, MenuState


def fully_rested(profile) -> bool:
    """Fresh hours of service and zero fatigue: sleeping gains nothing but time."""
    return (
        profile.hos.driving_min <= 0.0
        and profile.hos.duty_min <= 0.0
        and profile.fatigue <= 0.0
    )


class CareerStatsState(MenuState):
    """Career stats as a list of lines, matching the driving status screens."""

    title = "Career stats"
    intro_help = (
        "Use up and down arrows to review each line. Enter repeats the current "
        "line. Escape returns to the terminal."
    )

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                line,
                lambda line=line: self.ctx.say(line),
                help="Repeat this status line.",
            )
            for line in self._lines()
        ]
        items.append(MenuItem("Back", self.go_back, help="Back to the terminal menu."))
        return items

    def _lines(self) -> list[str]:
        p = self.ctx.profile
        career = p.career
        pct = (100 * career.on_time_deliveries / career.deliveries) if career.deliveries else 100
        rest = "fully rested" if fully_rested(p) else f"fatigue {p.fatigue:.0f} percent"
        return [
            f"Level {career.level} driver, {career.xp:.0f} experience",
            f"Reputation: {career.reputation:.0f} out of 100",
            f"Deliveries: {career.deliveries}, {pct:.0f} percent on time",
            f"Lifetime miles: {career.total_miles:,.0f}",
            f"Lifetime earnings: {career.total_earnings:,.0f} dollars",
            f"Rest: {rest}",
            f"Hours: {p.hos.summary(self.ctx.settings.hos_mode).rstrip('.')}",
        ]
