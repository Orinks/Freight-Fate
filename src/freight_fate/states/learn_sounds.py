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

from ..ladder_earcons import register_ladder_earcons
from ..lane_guide_tone import register_lane_guide_tone
from ..sound_catalog import CATALOG, SoundCategory, SoundEntry
from ..sound_demo import SoundDemo
from .base import MenuItem, MenuState
from .driving_siren import register_enforcement_sounds


class LearnSoundsState(MenuState):
    """The category list."""

    title = "Learn game sounds"
    intro_help = (
        "Choose a group of sounds. Inside a group, Enter plays the sound and "
        "F1 says what it means. Up and down arrows move, Escape goes back."
    )

    def build_items(self) -> list[MenuItem]:
        # Escape has always worked, but a row you can arrow onto is how every
        # other menu in the game offers the way out, and it is the only one a
        # player finds without having heard the intro (owner, 2026-08-16).
        items = [
            MenuItem(
                category.name,
                lambda c=category: self.ctx.push_state(LearnSoundCategoryState(self.ctx, c)),
                help=f"{len(category.entries)} sounds. {self._summary(category)}",
            )
            for category in CATALOG
        ]
        items.append(MenuItem("Back", self.go_back, help="Leave Learn game sounds."))
        return items

    @staticmethod
    def _summary(category: SoundCategory) -> str:
        names = ", ".join(entry.name for entry in category.entries[:3])
        return f"Starting with {names}." if names else ""


class LearnSoundCategoryState(MenuState):
    """The cues inside one category, and the demo that plays them."""

    intro_help = (
        "Enter plays the sound, and Enter again plays it once it has "
        "finished. F1 says what it means and when you hear it. Up and down "
        "arrows move. Escape goes back, and both moving away and going back "
        "stop a sound that would otherwise keep running; a short sound "
        "already playing finishes on its own."
    )

    def __init__(self, ctx, category: SoundCategory) -> None:
        super().__init__(ctx)
        self.category = category
        self.title = category.name
        self.demo = SoundDemo(ctx.audio)

    def enter(self) -> None:
        """Open the screen, ready to play everything the catalog names.

        The enforcement signature and the two ladder earcons are synthesized
        rather than shipped, and nothing else publishes the earcons at all --
        the ladder does not yet sound anything in gameplay, only this screen
        does. Opening this screen from the main menu would otherwise land on
        an entry that resolved to nothing -- a cue demonstrated as silence,
        which is the one thing this screen must never do. Registering is
        idempotent and cheap, so both entry points simply do it on the way in.

        Stopping the demo here covers re-entry: a screen pushed over this one
        freezes the demo's clock, and coming back re-announces the title while
        a held cue would otherwise pick its hold straight back up.
        """
        register_enforcement_sounds()
        register_ladder_earcons()
        register_lane_guide_tone()
        self.demo.stop()
        super().enter()

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(
                entry.name,
                lambda e=entry: self.play_entry(e),
                help=f"{entry.meaning} {entry.when}".strip(),
                # The demo IS the confirmation; a menu click over the top of a
                # cue the player is trying to learn defeats the screen.
                select_sound=None,
            )
            for entry in self.category.entries
        ]
        # Selecting this runs go_back, which stops a held demo on the way out,
        # so the row cannot leave a cue ringing behind it.
        items.append(MenuItem("Back", self.go_back, help="Back to the list of sound groups."))
        return items

    def play_entry(self, entry: SoundEntry) -> None:
        """Demo one entry, or say why it cannot be demonstrated.

        A cue that ships only in the licensed sound overlay resolves to
        nothing on a clean build. Playing nothing at all would teach the
        player that the real cue is silent, so the screen says so instead.
        """
        if not self.demo.can_play(entry):
            self.ctx.say(
                f"{entry.name} is not available in this copy of the game, "
                "so there is nothing to play. F1 still says what it means."
            )
            return
        self.demo.start(entry)

    def update(self, dt: float) -> None:
        super().update(dt)
        self.demo.update(dt)

    def speak_current(self) -> None:
        """Stop any running demo before speaking the newly selected entry.

        ``move`` (arrows), ``jump`` (Home/End) and ``_first_letter_jump``
        (typing a letter) are three separate routes into a changed
        selection, but ``MenuState`` funnels all three through this one
        hook before it speaks. Stopping the demo here, rather than in each
        route, means a held cue can never keep ringing under a name it
        does not belong to -- and a future navigation route inherits the
        rule for free instead of needing to remember it.
        """
        self.demo.stop()
        super().speak_current()

    def go_back(self) -> None:
        self.demo.stop()
        super().go_back()

    def exit(self) -> None:
        self.demo.stop()
        super().exit()
