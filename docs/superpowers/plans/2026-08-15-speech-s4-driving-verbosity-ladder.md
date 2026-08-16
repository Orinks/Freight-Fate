# Speech S4: Driving Verbosity Ladder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two-value `speech_verbosity` compression setting with a four-rung named ladder that cuts whole categories of informational driving speech, so a quiet drive is mostly engine, road, and radio.

**Architecture:** Informational speech already carries an *urgency* tag (`EventPriority`, from R1) that decides how long a line waits. This plan adds an orthogonal *category* tag (`SpeechCategory`) saying what a line is about, and a rung table mapping (rung, category) to one of six dispositions. The delivery layer (`GameContext.say` / `say_event`) consults the table before rendering, so a silenced category never reaches the voice. Flavor speech — billboards, places, landmarks, roadside chatter — is deliberately outside this system and keeps its existing switches.

**Tech Stack:** Python 3.12, `uv`, pytest (with `-q -n auto` and per-test timeouts preconfigured), pygame, Prism speech.

**Spec:** `docs/superpowers/specs/2026-08-15-speech-s4-driving-verbosity-ladder-design.md`

## Global Constraints

- Python 3.12. Run everything through `uv` (`uv run pytest`, `uv run ruff check src tests tools`).
- Headless runs need `FREIGHT_FATE_NO_SPEECH=1`; CI also sets `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy`.
- Keep practical code files at or below 1000 lines. `states/driving_updates.py` is already 3985 lines — do not grow it structurally; tagging call sites adds keywords to existing calls only.
- Spoken text is player-facing: no maintainer or CI jargon in anything a player hears.
- Use the canonical spoken noun from `docs/ontology.md`. A new concept means a new ontology row **in the same change**.
- `SAFETY` and `MONEY` never fall silent at any rung. A rung may pick the terse rendering; it may never pick silence.
- An untagged call site (`category=None`) speaks at every rung. The failure mode for an unclassified line is "too loud", never "silently dropped a warning".
- Never use Computer Use or desktop UI automation to validate the game. Use the headless transcript harness, tests, and owner manual validation.
- This branch takes **no pull requests** — commit directly (owner directive for `feat/career-1.9` work).
- Player-facing changes need a `CHANGELOG.md` entry under `## Unreleased`; anything else needs `[skip changelog]` in every commit message.

---

### Task 1: The category tag and the rung table

**Files:**
- Modify: `src/freight_fate/speech_pacing.py` (append after the `EventPriority` enum, around line 75)
- Test: `tests/test_driving_speech_ladder.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `SpeechCategory` (StrEnum: `SAFETY`, `NAVIGATION`, `MONEY`, `COACHING`, `CONFIRMATION`, `STATUS`), `Disposition` (StrEnum: `FULL`, `TERSE`, `FIRST_OCCURRENCE`, `TRANSITIONS`, `EARCON`, `SILENT`), `DRIVING_SPEECH_MODES: tuple[str, ...]`, `DRIVING_SPEECH_DISPOSITIONS: dict[str, dict[SpeechCategory, Disposition]]`, and `disposition_for(mode: str, category: SpeechCategory | None) -> Disposition`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_driving_speech_ladder.py`:

```python
"""The S4 driving verbosity ladder: rungs cut categories, not word counts.

The rung table is pinned as data so that changing what a rung silences is a
visible diff in this file rather than a behaviour surprise on the road.
"""

from __future__ import annotations

import pytest

from freight_fate.speech_pacing import (
    DRIVING_SPEECH_DISPOSITIONS,
    DRIVING_SPEECH_MODES,
    Disposition,
    SpeechCategory,
    disposition_for,
)


def test_the_ladder_has_four_named_rungs() -> None:
    assert DRIVING_SPEECH_MODES == ("coaching", "standard", "quiet", "urgent_only")


def test_every_rung_rules_on_every_category() -> None:
    for mode in DRIVING_SPEECH_MODES:
        for category in SpeechCategory:
            assert disposition_for(mode, category) in set(Disposition)


@pytest.mark.parametrize("mode", DRIVING_SPEECH_MODES)
@pytest.mark.parametrize("category", [SpeechCategory.SAFETY, SpeechCategory.MONEY])
def test_safety_and_money_speak_at_every_rung(mode: str, category: SpeechCategory) -> None:
    # R1's never-dropped contract outranks the ladder. A rung may shorten
    # these; it may never silence them.
    assert disposition_for(mode, category) in (Disposition.FULL, Disposition.TERSE)


@pytest.mark.parametrize("mode", DRIVING_SPEECH_MODES)
def test_an_untagged_line_speaks_at_every_rung(mode: str) -> None:
    # A call site nobody has classified yet must be too loud, never silent.
    assert disposition_for(mode, None) in (Disposition.FULL, Disposition.TERSE)


def test_the_table_reads_exactly_as_the_spec_says() -> None:
    assert DRIVING_SPEECH_DISPOSITIONS["coaching"] == {
        SpeechCategory.SAFETY: Disposition.FULL,
        SpeechCategory.MONEY: Disposition.FULL,
        SpeechCategory.NAVIGATION: Disposition.FULL,
        SpeechCategory.COACHING: Disposition.FULL,
        SpeechCategory.CONFIRMATION: Disposition.FULL,
        SpeechCategory.STATUS: Disposition.FULL,
    }
    assert DRIVING_SPEECH_DISPOSITIONS["standard"] == {
        SpeechCategory.SAFETY: Disposition.FULL,
        SpeechCategory.MONEY: Disposition.FULL,
        SpeechCategory.NAVIGATION: Disposition.FULL,
        SpeechCategory.COACHING: Disposition.FIRST_OCCURRENCE,
        SpeechCategory.CONFIRMATION: Disposition.FULL,
        SpeechCategory.STATUS: Disposition.TRANSITIONS,
    }
    assert DRIVING_SPEECH_DISPOSITIONS["quiet"] == {
        SpeechCategory.SAFETY: Disposition.TERSE,
        SpeechCategory.MONEY: Disposition.TERSE,
        SpeechCategory.NAVIGATION: Disposition.TERSE,
        SpeechCategory.COACHING: Disposition.EARCON,
        SpeechCategory.CONFIRMATION: Disposition.EARCON,
        SpeechCategory.STATUS: Disposition.EARCON,
    }
    assert DRIVING_SPEECH_DISPOSITIONS["urgent_only"] == {
        SpeechCategory.SAFETY: Disposition.TERSE,
        SpeechCategory.MONEY: Disposition.TERSE,
        SpeechCategory.NAVIGATION: Disposition.TERSE,
        SpeechCategory.COACHING: Disposition.SILENT,
        SpeechCategory.CONFIRMATION: Disposition.EARCON,
        SpeechCategory.STATUS: Disposition.SILENT,
    }


def test_an_unknown_rung_falls_back_to_standard() -> None:
    assert disposition_for("nonsense", SpeechCategory.STATUS) == Disposition.TRANSITIONS
```

Note on `urgent_only` + `NAVIGATION`: the table says `TERSE` rather than a
seventh disposition. "Act-now cues only" is enforced at the call sites in
Task 4, which tag non-actionable navigation lines (progress, distance-to-go,
upcoming-stop previews) as `STATUS` instead — that is what makes them fall
silent at this rung. Keeping the table's vocabulary at six dispositions is
deliberate; the alternative grows the enum for one cell.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_driving_speech_ladder.py -v`
Expected: FAIL — `ImportError: cannot import name 'SpeechCategory' from 'freight_fate.speech_pacing'`

- [ ] **Step 3: Write minimal implementation**

In `src/freight_fate/speech_pacing.py`, add `StrEnum` to the existing `from enum import IntEnum` import so it reads `from enum import IntEnum, StrEnum`, then append after the `EventPriority` class:

```python
class SpeechCategory(StrEnum):
    """What a line of informational speech is ABOUT.

    Orthogonal to :class:`EventPriority`, which says how long a line waits
    and whether staleness may drop it. Urgency alone gave the verbosity
    system only one lever -- length -- which is why compressing every
    message (stage S2) did not make the drive quieter: it never reduced how
    many things speak. The rung table below cuts by category instead.

    Flavor -- billboards, place names, landmarks, roadside colour -- is
    deliberately absent. It answers to the chatter switches and the
    place-callouts ladder, and the owner set those separately (2026-08-15).
    """

    SAFETY = "safety"
    NAVIGATION = "navigation"
    MONEY = "money"
    COACHING = "coaching"
    CONFIRMATION = "confirmation"
    STATUS = "status"


class Disposition(StrEnum):
    """What a rung does with a category.

    ``EARCON`` and ``SILENT`` both stop the words; they differ in whether
    the sound layer still marks the moment. Neither loses the line -- both
    still reach the message log, and the status-query keys still answer, so
    nothing the ladder cuts becomes unreachable.
    """

    FULL = "full"  # speaks, normal rendering
    TERSE = "terse"  # speaks, terse rendering -- never silence
    FIRST_OCCURRENCE = "first"  # speaks the first time per leg, then silent
    TRANSITIONS = "transitions"  # speaks on enter, worsen, and clear only
    EARCON = "earcon"  # the sound layer carries it; no words
    SILENT = "silent"  # no words, no sound; log and status keys only


DRIVING_SPEECH_MODES = ("coaching", "standard", "quiet", "urgent_only")

# The rung table. Read a row as "at this rung, a line of this category is
# delivered this way". Safety and money are FULL or TERSE in every row and a
# test pins that: R1's never-dropped contract outranks any rung.
DRIVING_SPEECH_DISPOSITIONS: dict[str, dict[SpeechCategory, Disposition]] = {
    "coaching": {
        SpeechCategory.SAFETY: Disposition.FULL,
        SpeechCategory.MONEY: Disposition.FULL,
        SpeechCategory.NAVIGATION: Disposition.FULL,
        SpeechCategory.COACHING: Disposition.FULL,
        SpeechCategory.CONFIRMATION: Disposition.FULL,
        SpeechCategory.STATUS: Disposition.FULL,
    },
    "standard": {
        SpeechCategory.SAFETY: Disposition.FULL,
        SpeechCategory.MONEY: Disposition.FULL,
        SpeechCategory.NAVIGATION: Disposition.FULL,
        SpeechCategory.COACHING: Disposition.FIRST_OCCURRENCE,
        SpeechCategory.CONFIRMATION: Disposition.FULL,
        SpeechCategory.STATUS: Disposition.TRANSITIONS,
    },
    "quiet": {
        SpeechCategory.SAFETY: Disposition.TERSE,
        SpeechCategory.MONEY: Disposition.TERSE,
        SpeechCategory.NAVIGATION: Disposition.TERSE,
        SpeechCategory.COACHING: Disposition.EARCON,
        SpeechCategory.CONFIRMATION: Disposition.EARCON,
        SpeechCategory.STATUS: Disposition.EARCON,
    },
    "urgent_only": {
        SpeechCategory.SAFETY: Disposition.TERSE,
        SpeechCategory.MONEY: Disposition.TERSE,
        SpeechCategory.NAVIGATION: Disposition.TERSE,
        SpeechCategory.COACHING: Disposition.SILENT,
        SpeechCategory.CONFIRMATION: Disposition.EARCON,
        SpeechCategory.STATUS: Disposition.SILENT,
    },
}

DEFAULT_DRIVING_SPEECH = "standard"


def disposition_for(mode: str, category: SpeechCategory | None) -> Disposition:
    """How this rung delivers this category.

    An unknown rung reads as the default rather than raising: a settings
    file edited by hand must not be able to crash the drive. A ``None``
    category is an unclassified call site and always speaks -- the rendering
    still follows the rung, so it gets shorter but never disappears.
    """
    row = DRIVING_SPEECH_DISPOSITIONS.get(mode) or DRIVING_SPEECH_DISPOSITIONS[
        DEFAULT_DRIVING_SPEECH
    ]
    if category is None:
        return row[SpeechCategory.SAFETY]
    return row.get(SpeechCategory(category), Disposition.FULL)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_driving_speech_ladder.py -v`
Expected: PASS, all cases.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src tests
git add src/freight_fate/speech_pacing.py tests/test_driving_speech_ladder.py
git commit -m "feat(speech): informational speech gets a category tag and a rung table [skip changelog]"
```

---

### Task 2: The setting, and the migration off `speech_verbosity`

**Files:**
- Modify: `src/freight_fate/settings.py` (`SETTINGS_VERSION` at line 36; the `speech_verbosity` field at line 294; the migration block at lines 537-540; new methods beside `chatter_enabled` at line 628)
- Test: `tests/test_driving_speech_ladder.py` (append)

**Interfaces:**
- Consumes: `SpeechCategory`, `Disposition`, `DRIVING_SPEECH_MODES`, `DEFAULT_DRIVING_SPEECH`, `disposition_for` from Task 1.
- Produces: `Settings.driving_speech: str`, `Settings.speech_disposition(category) -> Disposition`, `Settings.speaks(category) -> bool`, `Settings.renders_terse() -> bool`. `Settings.speech_verbosity` no longer exists.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_driving_speech_ladder.py`:

```python
from freight_fate.settings import Settings


def test_the_default_rung_is_standard() -> None:
    assert Settings().driving_speech == "standard"


def test_a_saved_terse_player_lands_on_quiet() -> None:
    s = Settings.from_dict({"speech_verbosity": 0})
    assert s.driving_speech == "quiet"


def test_a_saved_normal_player_lands_on_standard() -> None:
    s = Settings.from_dict({"speech_verbosity": 1})
    assert s.driving_speech == "standard"


def test_a_nonsense_saved_verbosity_lands_on_standard() -> None:
    s = Settings.from_dict({"speech_verbosity": 7})
    assert s.driving_speech == "standard"


def test_a_settings_file_that_already_has_a_rung_is_left_alone() -> None:
    # The migration must not re-run against a file that has moved on, or a
    # player who chose urgent_only would be dragged back to quiet on the
    # next launch of a build that still saw a stale speech_verbosity.
    s = Settings.from_dict({"speech_verbosity": 0, "driving_speech": "urgent_only"})
    assert s.driving_speech == "urgent_only"


def test_an_unreadable_rung_falls_back_to_standard() -> None:
    s = Settings.from_dict({"driving_speech": "loud please"})
    assert s.driving_speech == "standard"


def test_the_settings_object_answers_for_a_category() -> None:
    s = Settings()
    s.driving_speech = "urgent_only"
    assert s.speaks(SpeechCategory.SAFETY) is True
    assert s.speaks(SpeechCategory.STATUS) is False
    assert s.speaks(None) is True
    assert s.renders_terse() is True

    s.driving_speech = "coaching"
    assert s.speaks(SpeechCategory.STATUS) is True
    assert s.renders_terse() is False


def test_verbosity_is_gone() -> None:
    # 11 references across 7 src files, all replaced -- a leftover reader
    # would silently see normal for every player.
    assert not hasattr(Settings(), "speech_verbosity")
```

**`Settings.from_dict` does not exist yet — this task creates it.** Today
`settings.py:431` is `def load(cls) -> Settings`, which opens `s.path`, reads
JSON into a local `data`, and then runs some 190 lines of migration and
validation against it. The migration is not testable without touching the
filesystem, which is why this plan's first move in this task is a pure
extraction:

```python
    @classmethod
    def load(cls) -> Settings:
        s = cls()
        data = None
        try:
            with open(s.path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                log.warning("Settings file is not a settings object; using defaults")
                data = {}
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError):
            log.warning("Could not read settings; using defaults", exc_info=True)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict | None) -> Settings:
        """Build settings from a parsed file, running every migration.

        Split out of :meth:`load` so the migrations are testable without a
        filesystem. ``None`` means there was no readable file and every
        default stands -- several migrations below distinguish that from an
        empty dict, so the distinction must survive the split.
        """
        s = cls()
        defaults = cls()
        if isinstance(data, dict):
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            if data.get("profile_sharing_consent_version") != PROFILE_SHARING_CONSENT_VERSION:
                s.online_presence = False
        # ... every existing migration, unchanged, moves here ...
        return s
```

Move the migration body verbatim. Do not take the opportunity to tidy it:
several blocks branch on `data is None` versus `"key" not in data` to tell a
fresh install from an old file, and that logic is load-bearing. Run the full
suite after the extraction and before adding the ladder migration, so a
regression in the move is caught on its own rather than blamed on the ladder.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_driving_speech_ladder.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'driving_speech'`

- [ ] **Step 3: Write minimal implementation**

In `src/freight_fate/settings.py`:

1. Bump the version and note why:

```python
# 3: speech_verbosity (0 terse / 1 normal) became the driving_speech ladder.
SETTINGS_VERSION = 3
```

2. Replace the `speech_verbosity: int = 1` field (line 294) with:

```python
    # How much of the road's INFORMATION speaks: a ladder of named rungs
    # that cut whole categories, not one global compression. Flavor is not
    # governed here -- billboards, places and landmarks answer to the
    # chatter switches and the place-callouts ladder (owner, 2026-08-15).
    driving_speech: str = DEFAULT_DRIVING_SPEECH
```

3. Replace the retired-chatty migration block (lines 537-540) with:

```python
        # The two-value verbosity became a four-rung ladder (S4). A terse
        # player asked for less and lands on quiet; everyone else on
        # standard, which is what normal already was. Keyed on the absence
        # of the new field, so a player who has since picked a rung is
        # never dragged back by a stale verbosity left in the file.
        if isinstance(data, dict) and "driving_speech" not in data:
            s.driving_speech = "quiet" if data.get("speech_verbosity") == 0 else "standard"
        if s.driving_speech not in DRIVING_SPEECH_MODES:
            s.driving_speech = DEFAULT_DRIVING_SPEECH
```

4. Add the import at the top of the module:

```python
from .speech_pacing import (
    DEFAULT_DRIVING_SPEECH,
    DRIVING_SPEECH_MODES,
    Disposition,
    SpeechCategory,
    disposition_for,
)
```

5. Add the query methods beside `chatter_enabled` (around line 628):

```python
    def speech_disposition(self, category: SpeechCategory | None) -> Disposition:
        """How the player's rung delivers this category of information."""
        return disposition_for(self.driving_speech, category)

    def speaks(self, category: SpeechCategory | None) -> bool:
        """Whether this category reaches the voice at all on this rung."""
        return self.speech_disposition(category) not in (
            Disposition.EARCON,
            Disposition.SILENT,
        )

    def renders_terse(self) -> bool:
        """Whether spoken lines take their terse rendering on this rung.

        The rung picks the rendering, so ``SpokenMessage`` keeps the
        single-boolean ``render`` signature S2 gave it.
        """
        return self.driving_speech in ("quiet", "urgent_only")
```

6. Replace the remaining `speech_verbosity` readers. There are 11 across 7
files; `rg -n speech_verbosity src` lists them. Each is one of two shapes:

- `self.settings.speech_verbosity == 0` becomes `self.settings.renders_terse()`
- `['terse', 'normal'][s.speech_verbosity]` (the menu label) is handled in Task 6 — leave it for now and let the menu read `s.driving_speech` directly.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_driving_speech_ladder.py -v`
Expected: PASS.

Then confirm nothing else read the old field:

Run: `uv run pytest tests/test_speech_verbosity_pairs.py tests/test_terse_contract.py tests/test_tutorial_verbosity.py -v`
Expected: these will FAIL where they set `settings.speech_verbosity` directly. Update each to set `settings.driving_speech = "quiet"` / `"standard"` instead. That is the intended blast radius, and it is small because S2 centralized the reads.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src tests
git add src/freight_fate/settings.py tests/
git commit -m "feat(settings): the driving speech ladder replaces the verbosity pair [skip changelog]"
```

---

### Task 3: The delivery-layer gate

**Files:**
- Modify: `src/freight_fate/app.py` (`say` at line 190, `say_event` at line 252)
- Test: `tests/test_driving_speech_ladder.py` (append)

**Interfaces:**
- Consumes: `Settings.speaks`, `Settings.renders_terse`, `SpeechCategory` from Tasks 1-2.
- Produces: `GameContext.say(text, interrupt=True, review=True, *, category: SpeechCategory | None = None)` and `GameContext.say_event(text, interrupt=True, review=True, *, priority=None, key=None, force=False, category: SpeechCategory | None = None)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_driving_speech_ladder.py`:

```python
from speech_capture import speech_stub


def _app():
    from freight_fate.app import App

    app = App()
    app.ctx.settings.sapi_events = True
    return app


def test_a_silenced_category_never_reaches_the_voice() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say_event(
            "Load damage 43 percent.", interrupt=False, category=SpeechCategory.STATUS
        )

        assert spoken == []
    finally:
        app.shutdown()


def test_a_silenced_category_still_reaches_the_message_log() -> None:
    # Nothing the ladder cuts becomes unreachable -- the log and the
    # status-query keys still answer for it.
    app = _app()
    try:
        app.ctx.speech.say_event = speech_stub()
        app.ctx.settings.driving_speech = "urgent_only"
        before = len(app.ctx.message_log.messages)

        app.ctx.say_event(
            "Load damage 43 percent.", interrupt=False, category=SpeechCategory.STATUS
        )

        assert len(app.ctx.message_log.messages) == before + 1
    finally:
        app.shutdown()


def test_safety_speaks_at_the_quietest_rung() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say_event(
            "Brake or change lanes! Slow car ahead.",
            interrupt=True,
            category=SpeechCategory.SAFETY,
        )

        assert spoken == ["Brake or change lanes! Slow car ahead."]
    finally:
        app.shutdown()


def test_the_rung_picks_the_rendering() -> None:
    from freight_fate.speech_text import SpokenMessage

    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        pair = SpokenMessage("Watch your speed. The limit is 65 miles per hour.", "Limit 65.")

        app.ctx.settings.driving_speech = "quiet"
        app.ctx.say_event(pair, interrupt=True, category=SpeechCategory.NAVIGATION)

        assert spoken == ["Limit 65."]
    finally:
        app.shutdown()


def test_an_untagged_line_still_speaks_at_the_quietest_rung() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say_event("Something nobody classified.", interrupt=False)

        assert spoken == ["Something nobody classified."]
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_driving_speech_ladder.py -v`
Expected: FAIL — `TypeError: say_event() got an unexpected keyword argument 'category'`

- [ ] **Step 3: Write minimal implementation**

In `src/freight_fate/app.py`, `say_event` gains the keyword and the gate runs
**before** the `SpokenMessage` render, so a silenced category never renders,
never touches the pacer, and never engages the duck:

```python
    def say_event(
        self,
        text: str,
        interrupt: bool = True,
        review: bool = True,
        *,
        priority: EventPriority | None = None,
        key: str | None = None,
        force: bool = False,
        category: SpeechCategory | None = None,
    ) -> None:
```

Immediately after the docstring, before the `isinstance(text, SpokenMessage)`
block:

```python
        if not self.settings.speaks(category) and not force:
            # The player's rung silences this category. The line still
            # reaches the review log and the status keys, so the
            # information is cut from the drive, not from the game.
            # ``force`` is a line the player asked for and must hear.
            if isinstance(text, SpokenMessage):
                text = text.render(self.settings.renders_terse()) or text.normal
            transcript.info("[ladder] %s silenced: %s", self.settings.driving_speech, text)
            if review:
                self.message_log.add(text, MessageCategory.EVENT)
            return
```

Then change the existing render line from
`text = text.render(self.settings.speech_verbosity == 0)` to:

```python
            text = text.render(self.settings.renders_terse())
```

Apply the same two edits to `say` (line 190): add
`category: SpeechCategory | None = None` as a keyword-only parameter, gate on
`self.settings.speaks(category)` logging to `MessageCategory.GENERAL`, and
change its render call to `self.settings.renders_terse()`.

Add `SpeechCategory` to the existing `from .speech_pacing import EventPriority`
line.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_driving_speech_ladder.py -v`
Expected: PASS.

Run: `uv run pytest tests/test_event_speech_pacer.py tests/test_speech_verbosity_pairs.py -v`
Expected: PASS — `speech_capture.speech_stub` already swallows keyword-only
pacing arguments via `**_pacing`, so adding `category` breaks no existing stub.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src tests
git add src/freight_fate/app.py tests/test_driving_speech_ladder.py
git commit -m "feat(speech): the delivery layer gates on the player's rung [skip changelog]"
```

---

### Task 4: Tag the safety, navigation, and money call sites

**Files:**
- Modify: `src/freight_fate/states/driving_events.py` (31 `EventPriority` sites; `_event_priority` at line 486 is the hub)
- Modify: `src/freight_fate/sim/trip.py` (the toll-charged line, around line 2918)
- Test: `tests/test_driving_speech_ladder.py` (append)

**Interfaces:**
- Consumes: `SpeechCategory` and the gated `say_event` from Tasks 1-3.
- Produces: `_event_category(event) -> SpeechCategory`, mirroring the existing `_event_priority(event)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_driving_speech_ladder.py`:

```python
from freight_fate.sim.trip_models import TripEventKind
from freight_fate.states.driving_events import _EVENT_CATEGORIES, _FLAVOR_EVENT_KINDS


def _event(kind):
    return type("E", (), {"kind": kind, "data": {}})()


def test_the_hazard_call_is_safety() -> None:
    from freight_fate.states.driving_events import DrivingEventsMixin

    assert DrivingEventsMixin._event_category(_event(TripEventKind.HAZARD)) is (
        SpeechCategory.SAFETY
    )


def test_a_planned_stop_is_navigation() -> None:
    from freight_fate.states.driving_events import DrivingEventsMixin

    assert DrivingEventsMixin._event_category(_event(TripEventKind.STOP_AHEAD)) is (
        SpeechCategory.NAVIGATION
    )


def test_weather_colour_is_status_not_navigation() -> None:
    # This is what makes "act-now cues only" real at urgent_only: the stop
    # you must act on is NAVIGATION and speaks; the weather turning is
    # STATUS and does not.
    from freight_fate.states.driving_events import DrivingEventsMixin

    assert DrivingEventsMixin._event_category(_event(TripEventKind.WEATHER_CHANGE)) is (
        SpeechCategory.STATUS
    )


def test_billboards_and_landmarks_bypass_the_ladder_entirely() -> None:
    # The owner's directive, at the classification layer: flavor is not a
    # ladder category. Mapping BILLBOARD to STATUS would silence billboards
    # at urgent_only, which is precisely what must not happen. A flavor kind
    # classifies as None, so the gate passes it through and its own chatter
    # switch decides.
    from freight_fate.states.driving_events import DrivingEventsMixin

    for kind in (TripEventKind.BILLBOARD, TripEventKind.LANDMARK):
        assert DrivingEventsMixin._event_category(_event(kind)) is None
        assert kind in _FLAVOR_EVENT_KINDS
        assert kind not in _EVENT_CATEGORIES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_driving_speech_ladder.py -k category -v`
Expected: FAIL — `AttributeError: type object 'DrivingEventsMixin' has no attribute '_event_category'`

- [ ] **Step 3: Write minimal implementation**

In `driving_events.py`, add beside `_event_priority`:

```python
    @staticmethod
    def _event_category(event) -> SpeechCategory | None:
        """What this announcement is ABOUT, for the driving speech ladder.

        Deliberately separate from :meth:`_event_priority`: urgency decides
        how long a line waits, category decides whether the player's rung
        speaks it at all.

        ``None`` means "not the ladder's business" and the gate passes the
        line straight through. Two different things read as None and both
        are correct. Flavor -- billboards, landmarks, the place and border
        callouts -- answers to the chatter switches and the place-callouts
        ladder, and the owner set those separately (2026-08-15); a rung must
        never be able to silence them. And a kind nobody has classified yet
        also reads None, so the failure mode of a new event kind is a line
        too many rather than a warning the ladder ate.

        The navigation/status split is where "act-now cues only" lives: the
        stop, exit, or turn the player must act on is NAVIGATION; the
        weather turning and the road's general state are STATUS and fall
        silent at the quietest rung.
        """
        return _EVENT_CATEGORIES.get(event.kind)
```

and two module-level maps beside the other module constants:

```python
# Flavor kinds the driving speech ladder deliberately does not govern. They
# answer to the chatter switches and the place-callouts ladder instead. Kept
# as an explicit set rather than an absence, so the "is every kind
# classified" test can tell "decided to leave alone" from "forgot".
_FLAVOR_EVENT_KINDS = frozenset(
    {
        TripEventKind.LANDMARK,
        TripEventKind.BILLBOARD,
        TripEventKind.CITY_REACHED,
        TripEventKind.STATE_CROSSING,
        TripEventKind.TIMEZONE_CROSSING,
    }
)

_EVENT_CATEGORIES = {
    TripEventKind.HAZARD: SpeechCategory.SAFETY,
    TripEventKind.INSPECTION: SpeechCategory.SAFETY,
    TripEventKind.ZONE_ENTER: SpeechCategory.NAVIGATION,
    TripEventKind.ZONE_EXIT: SpeechCategory.NAVIGATION,
    TripEventKind.STOP_AHEAD: SpeechCategory.NAVIGATION,
    TripEventKind.STOP_REACHED: SpeechCategory.NAVIGATION,
    TripEventKind.CHECKPOINT: SpeechCategory.NAVIGATION,
    TripEventKind.GPS_CUE: SpeechCategory.NAVIGATION,
    TripEventKind.ARRIVED: SpeechCategory.NAVIGATION,
    TripEventKind.CURVE: SpeechCategory.NAVIGATION,
    TripEventKind.TOLL_CHARGED: SpeechCategory.MONEY,
    TripEventKind.WEATHER_CHANGE: SpeechCategory.STATUS,
    TripEventKind.LANE: SpeechCategory.STATUS,
}
```

`CURVE` is NAVIGATION rather than STATUS on purpose: a pacenote with an
advisory speed is a thing to act on, and R4's terse table already keeps the
curve composite as a spoken line ("Sharp left, half a mile, advise 35.").

Then thread `category=self._event_category(event)` into every `say_event`
call in the file that announces a trip event. The toll-charged line in
`trip.py` takes `category=SpeechCategory.MONEY` explicitly.

Every `TripEventKind` member must appear in exactly one of the two
collections. A test in Task 9 asserts that, so a future event kind cannot
join the enum without someone deciding whether the ladder governs it.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_driving_speech_ladder.py tests/test_driving_features.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src tests
git add src/freight_fate/states/driving_events.py src/freight_fate/sim/trip.py tests/
git commit -m "feat(speech): trip events carry what they are about [skip changelog]"
```

---

### Task 5: Tag the coaching, confirmation, and status call sites

**Files:**
- Modify: `src/freight_fate/states/driving_updates.py` (6 `EventPriority` sites; the standing-condition lines around 1010 and 1394)
- Modify: `src/freight_fate/states/driving_damage.py` (the load-damage coaching tail, around line 204)
- Modify: `src/freight_fate/states/driving.py` (the off-pavement standing condition, around line 607)
- Test: `tests/test_driving_speech_ladder.py` (append)

**Interfaces:**
- Consumes: `SpeechCategory` and the gated `say_event`.
- Produces: nothing new — these are call-site keywords only.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_driving_speech_ladder.py`:

```python
def test_the_load_damage_coaching_tail_is_silent_at_urgent_only(monkeypatch) -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"

        app.ctx.say_event(
            "Brake and corner gently from here.",
            interrupt=False,
            category=SpeechCategory.COACHING,
        )

        assert spoken == []
    finally:
        app.shutdown()


def test_the_same_tail_speaks_on_the_coaching_rung() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "coaching"

        app.ctx.say_event(
            "Brake and corner gently from here.",
            interrupt=False,
            category=SpeechCategory.COACHING,
        )

        assert spoken == ["Brake and corner gently from here."]
    finally:
        app.shutdown()


def test_no_driving_say_event_call_site_is_left_untagged() -> None:
    # The gate defaults untagged lines to speaking, which is the right
    # failure mode but the wrong finished state: an untagged line is one
    # the ladder cannot quiet. This pins the sweep as done.
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "states"
    untagged: list[str] = []
    for path in root.glob("driving*.py"):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"say_event\((.*?)\n\s*\)", source, re.S):
            if "category=" not in match.group(1) and "force=True" not in match.group(1):
                line = source[: match.start()].count("\n") + 1
                untagged.append(f"{path.name}:{line}")
    assert untagged == [], f"untagged say_event call sites: {untagged}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_driving_speech_ladder.py -k untagged -v`
Expected: FAIL, listing the call sites still missing a category.

- [ ] **Step 3: Write minimal implementation**

Work the failure list. Each site takes one keyword; use the taxonomy:

- `COACHING` — technique advice: "Brake and corner gently from here.", the ramp light-coaching line, load-damage tails.
- `CONFIRMATION` — outcome reports: cleared the hazard, held the line through the bend, backed up, latch caught.
- `STATUS` — speed drift, gaps, weather shifts, non-urgent HOS, redline and low-air bands, off-pavement position, leg progress.

Do not restructure these files. `driving_updates.py` is 3985 lines and this
task adds keywords to existing calls; splitting it is out of scope and would
bury the change.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_driving_speech_ladder.py -v`
Expected: PASS, including the untagged sweep.

Run: `uv run pytest tests/test_driving_features.py tests/test_driving_damage_bands.py tests/test_announcements.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src tests
git add src/freight_fate/states/ tests/
git commit -m "feat(speech): coaching, confirmations and status say what they are [skip changelog]"
```

---

### Task 6: The tutorial exemption, and learnable earcons

**Files:**
- Modify: `src/freight_fate/app.py` (the gate added in Task 3)
- Modify: `src/freight_fate/sound_catalog.py` (add entries for any earcon the ladder newly relies on)
- Test: `tests/test_driving_speech_ladder.py` (append)

**Interfaces:**
- Consumes: the gate from Task 3, `SpeechCategory`.
- Produces: nothing new — this closes two invariants the spec states and the gate would otherwise violate.

These are spec invariants 3 and 4. Without them the ladder ships two real
bugs: a brand-new player who picks `quiet` before their first drive loses the
teaching they have not had yet (R15's exact failure mode, reintroduced by a
different mechanism), and categories become sounds that nothing in the game
ever explains.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_driving_speech_ladder.py`:

```python
def test_the_ladder_does_not_apply_before_the_walkthrough_is_done() -> None:
    # R15, defended against a new mechanism. Terse used to silence the
    # tutorial outright, which orphaned exactly the new player most likely
    # to pick the quietest setting on day one. A rung must not do it either.
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"
        app.ctx.profile.tutorial_done = False

        app.ctx.say_event(
            "Press E to start the engine.",
            interrupt=False,
            category=SpeechCategory.COACHING,
        )

        assert spoken == ["Press E to start the engine."]
    finally:
        app.shutdown()


def test_the_ladder_applies_once_the_walkthrough_is_done() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "urgent_only"
        app.ctx.profile.tutorial_done = True

        app.ctx.say_event(
            "Press E to start the engine.",
            interrupt=False,
            category=SpeechCategory.COACHING,
        )

        assert spoken == []
    finally:
        app.shutdown()


def test_every_earcon_category_is_learnable() -> None:
    # R14's standing rule, binding S4's substitutions: no earcon may carry
    # meaning that the Learn game sounds screen cannot teach. This is what
    # makes "the rung replaces words with sounds" legitimate rather than
    # exclusionary.
    from freight_fate.sound_catalog import CATALOG

    learnable = {entry.key for category in CATALOG for entry in category.entries}
    for rung in DRIVING_SPEECH_MODES:
        for category in SpeechCategory:
            if disposition_for(rung, category) is Disposition.EARCON:
                assert LADDER_EARCONS[category] in learnable, (
                    f"{category} becomes an earcon at {rung} with nothing to learn it by"
                )
```

`LADDER_EARCONS` is a new mapping this task introduces, in
`speech_pacing.py` beside the rung table:

```python
# The sound that carries a category once a rung stops speaking it. Every
# value must exist in the Learn game sounds catalog -- pinned by test,
# because a sound the player cannot look up is information removed rather
# than information moved (R14).
LADDER_EARCONS = {
    SpeechCategory.COACHING: "coaching_note",
    SpeechCategory.CONFIRMATION: "hazard_clear",
    SpeechCategory.STATUS: "status_note",
}
```

Read `src/freight_fate/sound_catalog.py` first and use the real key
attribute name and the real key for the existing hazard-clear cue — the
dodge outcome pair already shipped in S3 (commit `c166a347`), so
`CONFIRMATION` should reuse it rather than inventing a second sound.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_driving_speech_ladder.py -k "walkthrough or learnable" -v`
Expected: FAIL — the tutorial test because the gate has no exemption, the
earcon test because `LADDER_EARCONS` does not exist.

- [ ] **Step 3: Write minimal implementation**

In `app.py`, the gate added in Task 3 grows one condition. Both in `say` and
`say_event`, change:

```python
        if not self.settings.speaks(category) and not force:
```

to:

```python
        if not self.settings.speaks(category) and not force and self._ladder_applies():
```

and add the helper beside them:

```python
    def _ladder_applies(self) -> bool:
        """Whether the driving speech rung may silence anything yet.

        First-run teaching outranks the rung, exactly as it outranks terse
        (research doc R15). A player who picks the quietest setting before
        their first drive is the one who most needs to be told the status,
        help, and hazard keys exist -- silence them and they can never pull
        information nobody told them about. The gate is ``tutorial_done``
        itself, so finishing the walkthrough and then choosing a quiet rung
        resurrects nothing.

        ``GameContext.profile`` is ``Profile | None`` (``app.py:98``), and
        the default here is deliberately ``True``: no profile means nobody
        is on a first drive, so the rung applies normally.
        """
        return bool(getattr(self.profile, "tutorial_done", True))
```

Then add `LADDER_EARCONS` to `speech_pacing.py` as above, and add any missing
entry to `sound_catalog.py` following the shape of the entries already there.
A new sound needs a name and a plain-language description of when the player
hears it — no maintainer jargon, since this text is read aloud.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_driving_speech_ladder.py tests/test_tutorial_verbosity.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src tests
git add src/freight_fate/app.py src/freight_fate/speech_pacing.py src/freight_fate/sound_catalog.py tests/test_driving_speech_ladder.py
git commit -m "feat(speech): teaching outranks the rung, and every substituted sound is learnable [skip changelog]"
```

---

### Task 7: The settings row, and the ontology

**Files:**
- Modify: `src/freight_fate/states/main_menu.py` (`_speech_control_specs` at line 1506; `_cycle_verbosity` at line 1995)
- Modify: `docs/ontology.md` (the "Terse speech grammar" section at line 453)
- Test: `tests/test_settings_menu.py` (append)

**Interfaces:**
- Consumes: `DRIVING_SPEECH_MODES`, `Settings.driving_speech`.
- Produces: `_cycle_driving_speech(self, d: int) -> None`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_settings_menu.py`, following the conventions already in
that file for building a menu state:

```python
def test_the_driving_speech_row_names_the_rung() -> None:
    from freight_fate.settings import Settings

    s = Settings()
    s.driving_speech = "quiet"
    assert _speech_row_label(s) == "Driving speech: quiet"


def test_the_row_cycles_all_four_rungs_and_wraps() -> None:
    from freight_fate.settings import Settings

    s = Settings()
    s.driving_speech = "coaching"
    seen = []
    for _ in range(5):
        seen.append(s.driving_speech)
        s.driving_speech = _next_rung(s.driving_speech, 1)
    assert seen == ["coaching", "standard", "quiet", "urgent_only", "coaching"]


def test_urgent_only_speaks_as_two_words() -> None:
    # The stored value is a key; the player hears English.
    assert _spoken_rung("urgent_only") == "urgent only"
```

Replace `_speech_row_label`, `_next_rung`, and `_spoken_rung` with the real
helpers once written — read `tests/test_settings_menu.py` first and match how
it already drives menu rows, rather than inventing a harness.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_settings_menu.py -k driving_speech -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Replace the verbosity spec in `_speech_control_specs` (line 1516):

```python
            (
                lambda: f"Driving speech: {s.driving_speech.replace('_', ' ')}",
                self._cycle_driving_speech,
                "How much the road tells you. Coaching explains technique, "
                "standard is the working default, quiet cuts confirmations "
                "and status to sounds, and urgent only leaves the safety "
                "calls, what things cost, and the turn you have to take. "
                "Billboards, place names and landmarks are not part of this "
                "-- they have their own switches below.",
            ),
```

Replace `_cycle_verbosity` (line 1995):

```python
    def _cycle_driving_speech(self, d: int) -> None:
        s = self.ctx.settings
        i = DRIVING_SPEECH_MODES.index(s.driving_speech)
        s.driving_speech = DRIVING_SPEECH_MODES[(i + d) % len(DRIVING_SPEECH_MODES)]
        self._announce()
```

Import `DRIVING_SPEECH_MODES` alongside the existing `PLACE_CALLOUT_MODES`
import in that module.

In `docs/ontology.md`, add to the "Terse speech grammar" section (which the
ladder now sits above) — the four rung names are the canonical spoken nouns:

```markdown
### Driving speech rungs

How much of the road's *information* speaks. Four rungs, cutting whole
categories rather than shortening sentences; the player picks one and the
delivery layer decides per category. "Terse" survives only as the internal
name of the shorter rendering and is no longer a thing the player selects.

| Concept | Canonical spoken noun | Never say | Where |
| --- | --- | --- | --- |
| The loudest rung, technique included | coaching | verbose, tutorial mode, chatty | `DRIVING_SPEECH_MODES` |
| The working default | standard | normal, default | `DRIVING_SPEECH_MODES` |
| Confirmations and status become sounds | quiet | terse (that is the rendering, not the rung), minimal | `DRIVING_SPEECH_MODES` |
| Safety, cost, and the turn you must take | urgent only | emergency mode, critical only | `DRIVING_SPEECH_MODES` |

Roadside colour -- billboards, place names, landmarks -- is **not** governed
by these rungs. It answers to the chatter switches and the place-callouts
ladder, and a player may run the loudest colour with the quietest rung.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_settings_menu.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src tests
git add src/freight_fate/states/main_menu.py docs/ontology.md tests/test_settings_menu.py
git commit -m "feat(settings): the driving speech row names its rung [skip changelog]"
```

---

### Task 8: Announce on change, not on state

**Files:**
- Modify: `src/freight_fate/states/driving_updates.py` (the `STATUS` sites tagged in Task 5)
- Test: `tests/test_driving_speech_ladder.py` (append)

**Interfaces:**
- Consumes: the `key=` parameter `say_event` already has.
- Produces: nothing new.

This is principle (4) of the owner's report. The mechanism is already built —
`say_event`'s `key=` marks a standing condition and "speaks when it starts and
again only when what it says has changed" (`app.py:276`). What is missing is
coverage: `STATUS` and `CONFIRMATION` lines that re-read a state the player
has not changed.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_driving_speech_ladder.py`:

```python
def test_an_unchanged_status_line_speaks_once() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "coaching"

        for _ in range(4):
            app.ctx.say_event(
                "Gap to the truck ahead: 3 seconds.",
                interrupt=False,
                key="lead_gap",
                category=SpeechCategory.STATUS,
            )

        assert spoken == ["Gap to the truck ahead: 3 seconds."]
    finally:
        app.shutdown()


def test_a_changed_status_line_speaks_again() -> None:
    app = _app()
    try:
        spoken: list[str] = []
        app.ctx.speech.say_event = speech_stub(spoken)
        app.ctx.settings.driving_speech = "coaching"

        app.ctx.say_event(
            "Gap to the truck ahead: 3 seconds.",
            interrupt=False,
            key="lead_gap",
            category=SpeechCategory.STATUS,
        )
        app.ctx.say_event(
            "Gap to the truck ahead: 1 second.",
            interrupt=False,
            key="lead_gap",
            category=SpeechCategory.STATUS,
        )

        assert spoken == [
            "Gap to the truck ahead: 3 seconds.",
            "Gap to the truck ahead: 1 second.",
        ]
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `uv run pytest tests/test_driving_speech_ladder.py -k status_line -v`
Expected: these two may already PASS — the pacer's `key=` handling is built.
If so, they are the regression pins for the audit that follows, and that is a
legitimate outcome for this step; do not weaken them to force a red.

- [ ] **Step 3: Do the audit**

Run the transcript harness and read for repeats:

```bash
FREIGHT_FATE_NO_SPEECH=1 uv run python tools/playtest_break.py --scenario career_economy --transcript
```

Every `STATUS` or `CONFIRMATION` line that appears more than once with
identical text and no intervening change of the condition it reports gets a
`key=`. Use a stable key naming the *condition*, not the message: `lead_gap`,
`redline`, `low_air`, `surface`, not `gap_3s`.

For each one fixed, add a test in the shape of the two above.

- [ ] **Step 4: Verify**

Run: `uv run pytest tests/test_driving_speech_ladder.py tests/test_event_speech_pacer.py -v`
Expected: PASS.

Re-run the transcript and confirm the repeats are gone.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src tests
git add src/freight_fate/states/ tests/test_driving_speech_ladder.py
git commit -m "feat(speech): standing conditions announce on change, not on state [skip changelog]"
```

---

### Task 9: The whole-drive proof, and the paperwork

**Files:**
- Test: `tests/test_driving_speech_ladder.py` (append)
- Modify: `CHANGELOG.md` (under `## Unreleased`)
- Modify: `ROADMAP.md` (the chattiness bullet at line 704)

**Interfaces:**
- Consumes: everything above.
- Produces: nothing.

- [ ] **Step 1: Write the failing test**

This is the closest a test can get to the owner's actual complaint: the same
drive, at each rung, saying strictly less.

```python
@pytest.mark.timeout(300)
def test_a_drive_gets_quieter_as_the_rung_tightens() -> None:
    # The owner's report is a COUNT complaint, not a length complaint, so
    # the pin is a count. Under xdist a sweep like this needs its own
    # timeout or the worker reads as "node down".
    counts = {}
    for rung in DRIVING_SPEECH_MODES:
        counts[rung] = _spoken_line_count_for_scenario("career_economy", rung)

    assert counts["coaching"] >= counts["standard"] > counts["quiet"] > counts["urgent_only"]


def test_every_trip_event_kind_is_classified() -> None:
    # Every kind is either governed by the ladder or explicitly left to the
    # flavor switches. Neither list may quietly gain a member by omission:
    # a new event kind must make someone decide which it is.
    from freight_fate.sim.trip_models import TripEventKind
    from freight_fate.states.driving_events import _EVENT_CATEGORIES, _FLAVOR_EVENT_KINDS

    undecided = [
        k.name
        for k in TripEventKind
        if k not in _EVENT_CATEGORIES and k not in _FLAVOR_EVENT_KINDS
    ]
    assert undecided == [], f"trip event kinds nobody classified: {undecided}"

    both = [k.name for k in TripEventKind if k in _EVENT_CATEGORIES and k in _FLAVOR_EVENT_KINDS]
    assert both == [], f"trip event kinds claimed by both lists: {both}"


def test_flavor_is_independent_of_the_rung() -> None:
    # The owner's directive of 2026-08-15, as an executable assertion: the
    # ladder governs information, the chatter switches govern colour, and
    # neither may grow a dependency on the other.
    from freight_fate.settings import Settings

    s = Settings()
    s.driving_speech = "urgent_only"
    s.set_all_chatter(True)
    assert s.chatter_enabled("billboard") is True

    s.driving_speech = "coaching"
    s.set_all_chatter(False)
    assert s.chatter_enabled("billboard") is False
```

Write `_spoken_line_count_for_scenario` as a helper in the test file, driving
`tools/playtest_break.py`'s scenario machinery in-process the way
`tests/test_playtest_harness.py` already does — read that file first and reuse
its seam rather than shelling out.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_driving_speech_ladder.py -k drive_gets_quieter -v`
Expected: FAIL until the helper exists; then it should PASS on the work from
Tasks 1-7. If it does **not** pass, the tagging sweep in Tasks 4-5 missed
categories — fix the tagging, not the assertion.

- [ ] **Step 3: Write the changelog entry**

In `CHANGELOG.md` under `## Unreleased`, in `### Changed`:

```markdown
- **Driving speech is now a ladder you pick, not a single terse switch.**
  The old setting only made each message shorter, which is why a quiet drive
  still talked constantly -- it never said fewer things. The new setting has
  four rungs. Coaching explains technique as you drive. Standard is the
  working default. Quiet turns confirmations and running status into sounds
  instead of sentences. Urgent only leaves the safety calls, what things
  cost, and the turn you actually have to take. Billboards, place names and
  landmarks are not part of this and keep their own switches, so you can
  drive a quiet cab through a talkative countryside. If you were on terse,
  you are now on quiet.
```

- [ ] **Step 4: Update the roadmap**

In `ROADMAP.md`, change the chattiness bullet at line 704 from `- [ ]` to
`- [x]`, retitle it "landed 2026-08-..", and reword its body to say what
shipped: principles (2) and (4) built as the ladder and announce-on-change;
principles (1) and (3) — the sonification pass and the per-minute cruise
speech budget — recorded as unchecked follow-up bullets, per the standing
rule that discovered follow-up work goes on the roadmap rather than staying
in commit messages.

- [ ] **Step 5: Full verification and commit**

```bash
uv run pytest
uv run ruff check src tests tools
uv run python -m compileall src tests tools
```

All three must pass before committing. Then:

```bash
git add tests/test_driving_speech_ladder.py CHANGELOG.md ROADMAP.md
git commit -m "feat(speech): the drive gets quieter by the rung, pinned end to end"
```

Note this commit has **no** `[skip changelog]`: it carries the changelog
entry, which is the point.

---

## After the plan

Hand the build to testers via the Dropbox share and the living document. Do
not present shipping the nightly as the next automatic step — the standing
gate is that the 1.9 nightly ships only after testers verify, and release
timing is the owner's call.
