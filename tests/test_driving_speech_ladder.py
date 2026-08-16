"""The S4 driving verbosity ladder: rungs cut categories, not word counts.

The rung table is pinned as data so that changing what a rung silences is a
visible diff in this file rather than a behaviour surprise on the road.
"""

from __future__ import annotations

import pytest

from freight_fate.settings import Settings
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
