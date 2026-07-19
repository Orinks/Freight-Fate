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
