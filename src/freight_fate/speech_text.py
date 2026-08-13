"""Spoken message pairs: one definition, both renderings side by side.

The terse contract (docs/speech-priority-research.md, R4) promises that
terse mode tells the player what to *do* and what it *cost*, and nothing
else -- in the shortest form the ontology allows. Making that real used to
depend on every call site remembering to hand-branch on the verbosity
setting, which is how 79 branches came to cover 711 speech call sites, and
how the terse hazard call drifted onto a synonym nobody diffed against the
help text.

So the pair lives in ONE definition: a builder in this module renders the
normal and terse forms of a message side by side, where a reviewer sees
both, and the delivery layer (``GameContext.say`` / ``say_event``) picks
the rendering the player's speech mode asks for. Drift between the two
forms is structurally impossible, and the safety-critical pairs are pinned
by copy tests on top of that.

Two rules bound every terse rendering (the research doc's R4):

- **Compress words, never certainty.** A qualifier that changes a decision
  survives terse; parking certainty keeps all five values distinguishable.
- **A fixed slot grammar, recorded in docs/ontology.md.** Hazards speak as
  [thing, distance, target speed]; stops as [name, exit, distance,
  qualifier]. A bare trailing number is only parseable because the frame
  never shuffles, so no terse line may reorder its slots.
"""

from __future__ import annotations


class SpokenMessage(str):
    """A spoken line carrying both of its renderings.

    The instance IS the normal rendering -- it subclasses ``str`` -- so
    everything that stores, compares, logs, or formats messages keeps
    working unchanged, while the delivery layer picks the rendering the
    player's speech mode asks for. ``terse=None`` means the line reads the
    same in both modes; ``terse=""`` means terse mode drops the line whole
    (an earcon or silence carries it instead, and it never reaches the
    review log -- as far as the drive is concerned it was not said).
    """

    __slots__ = ("terse",)

    terse: str | None

    def __new__(cls, normal: str, terse: str | None = None) -> SpokenMessage:
        self = super().__new__(cls, normal)
        self.terse = terse
        return self

    @property
    def normal(self) -> str:
        return str.__str__(self)

    def render(self, terse: bool) -> str:
        if terse and self.terse is not None:
            return self.terse
        return str.__str__(self)

    def plus(self, suffix: str) -> SpokenMessage:
        """Both renderings extended with one more sentence.

        Plain concatenation would flatten the pair back to a bare string
        and silently lose the terse form; this keeps the suffix on both.
        A dropped line (``terse=""``) keeps only the suffix in terse mode:
        the base line was color, but the suffix was appended because it
        reports something that happened.
        """
        if self.terse is None:
            terse = None
        elif self.terse:
            terse = f"{self.terse} {suffix}"
        else:
            terse = suffix
        return SpokenMessage(f"{self.normal} {suffix}", terse)


def terse_silent(normal: str) -> SpokenMessage:
    """Color, confirmation, or coaching: spoken in normal mode, carried by
    an earcon or by silence in terse mode."""
    return SpokenMessage(normal, "")
