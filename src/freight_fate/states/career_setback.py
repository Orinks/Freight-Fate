"""The two moments a career changes shape: losing the seat, losing the truck.

Both are the longest and most consequential things the game ever says, and
both remove the tractor the driver was in. A single spoken line would be gone
to the first keypress, so each one lands as a screen the player can arrow
through, re-read line by line, and leave when they are ready -- the same
cadence as the save notices.

Neither is an ending. The save is intact, the career is intact, and there is
freight on the board in the morning; the last line of every notice says where
to go next, and the screen refuses to close without the player acknowledging
it.
"""

from __future__ import annotations

from ..models import solvency
from .base import MenuItem, MenuState

_TITLES = {
    "termination": "Your carrier has ended your employment",
    "repossession": "The lender has taken the truck back",
}


class CareerSetbackNoticeState(MenuState):
    """A termination or a repossession, told once and re-readable."""

    intro_help = (
        "Use up and down arrows to read each line again. Enter repeats the "
        "current line. Enter on Continue, or Escape, returns to the terminal."
    )

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        record = ctx.profile.driving_record
        self.kind = str(record.setback_notice_kind or "")
        self.lines = list(record.setback_notice_lines or ())
        self.title = _TITLES.get(self.kind, "A change to your career")

    def announce_entry(self) -> None:
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"{self.title}. {' '.join(self.lines)}", interrupt=True)
        self.ctx.say(self.current_text(), interrupt=False, review=False)

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(line, lambda line=line: self.ctx.say(line), help="Repeat this line.")
            for line in self.lines
        ]
        items.append(MenuItem("Continue", self._acknowledge, help="Back to the terminal menu."))
        return items

    def _acknowledge(self) -> None:
        solvency.clear_setback_notice(self.ctx.profile)
        self.ctx.save_profile()
        self.ctx.pop_state()

    def go_back(self) -> None:
        # Escape acknowledges too; the player is never stuck on this screen.
        self._acknowledge()
