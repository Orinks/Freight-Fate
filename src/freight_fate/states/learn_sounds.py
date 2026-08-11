"""Learn game sounds: hear a cue and what it means, before it matters.

Two screens. The first lists the catalog's categories; the second lists the
cues inside one and plays them on request.

Arrowing speaks the name and nothing else, the way every other menu in the
game behaves. Enter plays the cue, and Enter again replays it. A cue that
fired while its own name was being spoken would teach the player the
collision rather than the cue, and holding Down would machine-gun the audio,
so nothing here plays on movement.
"""

from __future__ import annotations

from ..sound_catalog import CATALOG, SoundCategory
from ..sound_demo import SoundDemo
from .base import MenuItem, MenuState


class LearnSoundsState(MenuState):
    """The category list."""

    title = "Learn game sounds"
    intro_help = (
        "Choose a group of sounds. Inside a group, Enter plays the sound and "
        "F1 says what it means. Up and down arrows move, Escape goes back."
    )

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                category.name,
                lambda c=category: self.ctx.push_state(LearnSoundCategoryState(self.ctx, c)),
                help=f"{len(category.entries)} sounds. {self._summary(category)}",
            )
            for category in CATALOG
        ]

    @staticmethod
    def _summary(category: SoundCategory) -> str:
        names = ", ".join(entry.name for entry in category.entries[:3])
        return f"Starting with {names}." if names else ""


class LearnSoundCategoryState(MenuState):
    """The cues inside one category, and the demo that plays them."""

    intro_help = (
        "Enter plays the sound, and Enter again plays it a second time. "
        "F1 says what it means and when you hear it. Up and down arrows "
        "move, Escape stops the sound and goes back."
    )

    def __init__(self, ctx, category: SoundCategory) -> None:
        super().__init__(ctx)
        self.category = category
        self.title = category.name
        self.demo = SoundDemo(ctx.audio)

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                entry.name,
                lambda e=entry: self.demo.start(e),
                help=f"{entry.meaning} {entry.when}".strip(),
                # The demo IS the confirmation; a menu click over the top of a
                # cue the player is trying to learn defeats the screen.
                select_sound=None,
            )
            for entry in self.category.entries
        ]

    def update(self, dt: float) -> None:
        super().update(dt)
        self.demo.update(dt)

    def move(self, delta: int) -> None:
        # Arrowing away from a running demo stops it: the next name should
        # arrive over silence, not over the last cue.
        self.demo.stop()
        super().move(delta)

    def go_back(self) -> None:
        self.demo.stop()
        super().go_back()

    def exit(self) -> None:
        self.demo.stop()
        super().exit()
