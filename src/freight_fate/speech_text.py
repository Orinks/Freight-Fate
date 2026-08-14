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

import re

_WORD_RE = re.compile(r"[a-z0-9]+")


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def type_prefix_is_redundant(label: str, name: str) -> bool:
    """Whether a facility's type prefix only repeats words already in its name.

    "cross-dock Chicago Cross-Dock" and "port Port of Indiana-Burns Harbor"
    say the type twice; dropping the prefix there removes repetition, not
    vocabulary (research doc R6). Match on whole words so a short label does
    not fire on a coincidental substring ("port" must not swallow "Newport").
    A "travel center: Love's" keeps its prefix, because the name does not
    carry the type.
    """
    label_words = _words(label)
    if not label_words:
        return False
    name_words = set(_words(name))
    return all(word in name_words for word in label_words)


def typed_name(label: str, name: str, *, sep: str = " ") -> str:
    """A facility's name with its type prefix, unless the prefix is redundant."""
    if type_prefix_is_redundant(label, name):
        return name
    return f"{label}{sep}{name}"


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


# -- hazard calls (R8) --------------------------------------------------------

# The dodgeable hazard's call to action, and the phrase the help teaches for
# it. One canonical phrase, never a synonym: a "swerve" rewording lived only
# in terse mode, delivered only to the players who turned explanations off --
# exactly the drift docs/ontology.md exists to prevent. A copy test scans
# src/ so the synonym cannot come back.
HAZARD_DODGE_CALL = "Brake or change lanes!"

# Calls the hazard warning tone already carries by itself. Terse drops them
# and keeps the body -- the thing and where it is.
_TONE_IMPLIED_CALLS = ("Brake now!", "Brake!")


def hazard_call(call: str, body: str) -> SpokenMessage:
    """The hazard warning: a call to action, then the thing and where.

    Terse keeps the call only when it carries information the hazard tone
    does not: ``HAZARD_DODGE_CALL`` means the hazard is dodgeable AND there
    is an open lane to send the dodge, so it survives in full. A bare
    "Brake!"/"Brake now!" is what the tone already said. Either way the
    terse call is the normal call or nothing -- never a rewording.
    """
    normal = f"{call} {body}"
    terse = body if call in _TONE_IMPLIED_CALLS else normal
    return SpokenMessage(normal, terse)


# -- traffic lead cues --------------------------------------------------------
# Terse slot grammar for hazard-family cues: [thing, distance, target speed].
# The trailing bare number is only parseable because the frame never
# shuffles; see the terse grammar table in docs/ontology.md.
#
# merging_traffic_cue is the one exception, at [thing, distance] -- a
# merging vehicle merges behind or passes on its own; the truck never has to
# change speed for it, so there is no target speed to append. Naming one in
# the old line ("be ready for 41 miles per hour") read as an instruction to
# slow down that nothing in the situation asked for.


def merging_traffic_cue(vehicle_class: str, gap: str) -> SpokenMessage:
    return SpokenMessage(
        f"Merging {vehicle_class} {gap} ahead. Hold your lane and leave a gap.",
        f"Merging {vehicle_class}, {gap}.",
    )


def brake_lights_cue(gap: str, speed_text: str, speed_value: str) -> SpokenMessage:
    return SpokenMessage(
        f"Brake lights {gap} ahead. Ease down and leave room for {speed_text}.",
        f"Brake lights, {gap}, {speed_value}.",
    )


def slow_lead_cue(vehicle_class: str, gap: str, speed_text: str, speed_value: str) -> SpokenMessage:
    return SpokenMessage(
        f"Slow {vehicle_class} {gap} ahead. Be ready near {speed_text}.",
        f"Slow {vehicle_class}, {gap}, {speed_value}.",
    )


# -- stops and parking certainty ----------------------------------------------

# The normal labels compressed, no new words, and every value still
# distinguishable: a qualifier a driver plans a ten-hour rest on is
# certainty, and terse compresses words, never certainty. "Likely" is
# spoken as silence in normal mode (a pre-existing design choice, noted for
# the owner in the research doc); terse mirrors normal exactly, so silence
# keeps meaning "likely" and nothing else.
TERSE_PARKING_LABELS = {
    "confirmed": "Parking confirmed.",
    "likely": "",
    "limited": "Parking limited.",
    "unknown": "Parking not verified.",
    "none": "No truck parking.",
}


def stop_callout(
    *,
    planned_prefix: str,
    typed_name: str,
    plain_name: str,
    exit_label: str,
    distance: str,
    parking_normal: str,
    parking_certainty: str,
    exit_hint: str = "X",
) -> SpokenMessage:
    """The stop-ahead callout. Terse slots: [name, exit, distance, qualifier].

    Terse drops the stop-type prefix (the proper name mostly repeats it),
    the "in"/"at" scaffolding, and the key instruction -- and keeps the
    parking qualifier, because that is the fact the plan turns on.

    ``exit_hint`` names the control that signals for the exit; the driving
    layer sets it to the device-correct hint, or to "" once the player has
    demonstrated the exit signal enough times for the instruction to retire
    (research doc R7). An empty hint drops the sentence entirely.
    """
    exit_part = f" at {exit_label}" if exit_label else ""
    normal_parts = [f"{planned_prefix}{typed_name}{exit_part} in {distance}."]
    if parking_normal:
        normal_parts.append(f"{parking_normal}.")
    if exit_hint:
        normal_parts.append(f"Press {exit_hint} to signal for the exit.")
    slots = [plain_name] + ([exit_label] if exit_label else []) + [distance]
    terse = f"{planned_prefix}{', '.join(slots)}."
    parking_terse = TERSE_PARKING_LABELS.get(parking_certainty, TERSE_PARKING_LABELS["unknown"])
    if parking_terse:
        terse = f"{terse} {parking_terse}"
    return SpokenMessage(" ".join(normal_parts), terse)


# -- money lines ---------------------------------------------------------------


def toll_charged(method_label: str, name: str, amount_text: str, estimated: bool) -> SpokenMessage:
    """The charged toll: what it cost always speaks (ROUTE, never dropped);
    terse keeps the cost and who pays, drops the bookkeeping prose."""
    estimate = "Estimated " if estimated else ""
    return SpokenMessage(
        f"{method_label} toll charged at {name}: "
        f"{estimate}{amount_text} dollars, billed to carrier settlement.",
        f"Toll, {amount_text} dollars, carrier.",
    )


# -- speed and cruise ----------------------------------------------------------


def overspeed_nag(limit_speed_text: str, limit_value: str) -> SpokenMessage:
    """The over-the-limit warning that rides the overspeed chime."""
    return SpokenMessage(
        f"Watch your speed. The limit is {limit_speed_text}.",
        f"Limit {limit_value}.",
    )


def cruise_curve_easing(pacenote: str, advisory_speed_text: str) -> SpokenMessage:
    """The curve call plus the assist's easing clause.

    Terse speaks the pacenote alone: its advisory number is the same number
    cruise is easing to, and the deceleration itself is audible. (A
    dedicated cruise earcon is on the roadmap; until it exists the curve
    chime plus the pacenote carry the moment.)
    """
    return SpokenMessage(
        f"{pacenote} Adaptive cruise easing to {advisory_speed_text} for the bend.",
        pacenote,
    )


# -- achievements --------------------------------------------------------------


def achievement_unlocked(name: str, description: str) -> SpokenMessage:
    """The full achievement record: name plus flavor, for the message log,
    the achievements menu, and a parked settlement readout. This is stored on
    the award, not spoken live -- the live announce is :func:`achievement_announced`."""
    return SpokenMessage(f"New achievement! {name}. {description}", f"{name}.")


def achievement_announced(name: str) -> SpokenMessage:
    """The live announce: earcon plus the name, in either speech mode.

    The flavor prose never speaks at speed (research doc R9); it waits in the
    message log and the achievements menu. Normal mode hears "New achievement!
    <name>."; terse hears the bare name, the sound having already said "new".
    """
    return SpokenMessage(f"New achievement! {name}.", f"{name}.")
