"""Career stats screen: the terminal's driver record as a reviewable menu."""

from __future__ import annotations

from .base import MenuItem, MenuState


def fully_rested(profile) -> bool:
    """Fresh hours of service and zero fatigue: sleeping gains nothing but time."""
    return profile.hos.driving_min <= 0.0 and profile.hos.duty_min <= 0.0 and profile.fatigue <= 0.0


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
        from ..models import enforcement
        from ..models.career import xp_to_next_level
        from ..models.jobs import ENDORSEMENT_LABELS
        from ..models.solvency import debt_line

        p = self.ctx.profile
        s = self.ctx.settings
        career = p.career
        pct = (100 * career.on_time_deliveries / career.deliveries) if career.deliveries else 100
        rest = "fully rested" if fully_rested(p) else f"fatigue {p.fatigue:.0f} percent"
        held = sorted(
            ENDORSEMENT_LABELS.get(e, e.replace("_", " ")).replace(" endorsement", "")
            for e in career.endorsements
        )
        # Earned endorsements were only ever spoken once, at the level-up
        # that granted them; this line is the reviewable record (owner got
        # stuck declining a reefer load he was already cleared to haul).
        endorsements = f"Endorsements: {', '.join(held)}" if held else "Endorsements: none yet"
        # Money was reviewable nowhere on this screen, which left a player
        # asking "how much do I owe" with no way to find out short of opening
        # a fuel menu. Balance is always here now; what is owed joins it only
        # when it is real. The slower career rate rides the trust line, which
        # is on this screen already.
        owed = debt_line(p)
        return [
            f"Level {career.level} driver, {career.xp:.0f} experience"
            + (
                f", {xp_owed:,.0f} to level {career.level + 1}"
                if (xp_owed := xp_to_next_level(career.xp)) is not None
                else ", top level"
            ),
            f"Reputation: {career.reputation:.0f} out of 100",
            enforcement.dispatch_trust_line(p),
            enforcement.career_menu_status(p),
            enforcement.standing_text(p),
            f"Balance: {p.money:,.0f} dollars",
            *([owed] if owed else []),
            endorsements,
            f"Deliveries: {career.deliveries}, {pct:.0f} percent on time",
            f"Lifetime {s.distance_unit_text()}: "
            f"{s.distance_value(career.total_miles, grouped=True)}",
            f"Lifetime earnings: {career.total_earnings:,.0f} dollars",
            f"Rest: {rest}",
            f"Hours: {p.hos.summary(self.ctx.settings.hos_mode).rstrip('.')}",
        ]
