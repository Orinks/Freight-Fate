"""One-time spoken notices about a save file: converted, or changed outside the game."""

from __future__ import annotations

from .base import MenuItem, MenuState


class SaveModifiedNoticeState(MenuState):
    title = "Save file changed outside the game"
    intro_help = "Press Enter on OK to continue to your career."

    def announce_entry(self) -> None:
        self.ctx.say(
            "Heads up. This save was changed outside the game, or copied from "
            "another computer, so it is now marked as modified. Your career "
            "still works normally on this computer, but shared features such "
            "as profile sharing may not accept a modified profile. "
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        return [MenuItem("OK", self._acknowledge, help="Continue to your career.")]

    def _acknowledge(self) -> None:
        from .main_menu import _world_entry_state, pending_notice_state

        p = self.ctx.profile
        p.integrity_notice_pending = False
        p.save()
        self.ctx.replace_state(pending_notice_state(self.ctx) or _world_entry_state(self.ctx))

    def go_back(self) -> None:
        # Escape acknowledges too; the player must never be stuck here.
        self._acknowledge()


class LegacyCareerNoticeState(MenuState):
    """A career from before 1.9 was picked from the list: explain, offer a
    fresh start, and leave the old save exactly as it is.

    Unlike the two notices above, no profile is loaded here -- the load gate
    refused the file without touching it, and this state only knows the
    driver name it carried.
    """

    title = "Career from an earlier version"
    intro_help = (
        "This career cannot continue in version 1.9. Enter on Start a new "
        "career begins a fresh one; Escape goes back to the career list."
    )

    def __init__(self, ctx, driver_name: str) -> None:
        super().__init__(ctx)
        self.driver_name = driver_name

    def announce_entry(self) -> None:
        self.ctx.say(
            f"{self.driver_name} was made in an earlier version of Freight "
            "Fate. Version 1.9 rebalances the whole career, from pay to "
            "trucks to levels, so every driver starts fresh, and careers "
            "from earlier versions stay where they are. Nothing was lost: "
            "the save is still on this computer, untouched, and it still "
            "works in Freight Fate 1.8. Whenever you are ready, start a new "
            f"career and try the new road. {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                "Start a new career",
                self._new_career,
                help="Begin a fresh 1.9 career with a new driver name.",
            ),
            MenuItem(
                "Back to the career list",
                self.go_back,
                help="Return to the saved careers without changing anything.",
            ),
        ]

    def _new_career(self) -> None:
        from .main_menu import NameEntryState

        self.ctx.replace_state(NameEntryState(self.ctx))


class SaveMigrationNoticeState(MenuState):
    title = "Save file updated"
    intro_help = "Press Enter on OK to continue to your career."

    def announce_entry(self) -> None:
        self.ctx.say(
            "Save file updated. This career was created by an older version of "
            "Freight Fate and has been converted, so every truck you own now "
            "keeps its own fuel, damage, tire wear, and road grime. The truck "
            "you were driving keeps its current condition; your other trucks "
            "start fueled up and fresh. The updated save can no longer be "
            f"opened by older versions of the game. {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        return [MenuItem("OK", self._acknowledge, help="Continue to your career.")]

    def _acknowledge(self) -> None:
        from .main_menu import _world_entry_state, pending_notice_state

        p = self.ctx.profile
        p.migration_notice_pending = False
        p.save()
        self.ctx.replace_state(pending_notice_state(self.ctx) or _world_entry_state(self.ctx))

    def go_back(self) -> None:
        # Escape acknowledges too; the player must never be stuck here.
        self._acknowledge()
