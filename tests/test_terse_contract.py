"""The terse contract: what to do and what it cost, nothing else (R4, R8).

These are copy tests in the repo's usual sense: they pin the safety-critical
normal/terse pairs so one side cannot change without the other being looked
at, and they pin the two rules that bound every terse rendering -- compress
words, never certainty; and a fixed slot order, recorded in
docs/ontology.md.
"""

from __future__ import annotations

from pathlib import Path

from freight_fate.data.world_constants import PARKING_CERTAINTY_LABELS
from freight_fate.speech_text import (
    HAZARD_DODGE_CALL,
    TERSE_PARKING_LABELS,
    achievement_unlocked,
    brake_lights_cue,
    cruise_curve_easing,
    hazard_call,
    merging_traffic_cue,
    overspeed_nag,
    slow_lead_cue,
    stop_callout,
    toll_charged,
)

SRC = Path(__file__).resolve().parents[1] / "src"


# -- the hazard call (R8) ------------------------------------------------------


def test_the_dodge_call_survives_terse_in_full_and_is_never_a_synonym() -> None:
    pair = hazard_call(HAZARD_DODGE_CALL, "Slow car right ahead.")
    assert pair.normal == "Brake or change lanes! Slow car right ahead."
    assert pair.terse == pair.normal


def test_the_dodge_call_is_the_phrase_the_help_teaches() -> None:
    help_text = (SRC / "freight_fate" / "states" / "main_menu_help.py").read_text(encoding="utf-8")
    assert "Brake or change lanes" in help_text
    assert HAZARD_DODGE_CALL.rstrip("!") == "Brake or change lanes"


def test_the_swerve_synonym_is_gone_from_every_spoken_string() -> None:
    """Terse mode said "Brake or swerve!" where every other surface taught
    "Brake or change lanes" -- a synonym for the game's most safety-critical
    cue, delivered only to the players who turned explanations off. Pin its
    absence the way the ontology pins "bear"."""
    offenders = [
        path for path in SRC.rglob("*.py") if "Brake or swerve" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_tone_implied_calls_drop_to_the_body_in_terse() -> None:
    assert hazard_call("Brake now!", "Deer in the road.").terse == "Deer in the road."
    assert hazard_call("Brake!", "Mattress in your lane.").terse == "Mattress in your lane."
    assert hazard_call("Brake now!", "Deer in the road.").normal == "Brake now! Deer in the road."


# -- certainty survives compression --------------------------------------------


def test_parking_certainty_keeps_all_five_values_distinguishable() -> None:
    assert set(TERSE_PARKING_LABELS) == set(PARKING_CERTAINTY_LABELS)
    spoken = {key: label for key, label in TERSE_PARKING_LABELS.items() if key != "likely"}
    assert all(spoken.values()), "a certainty value lost its words"
    assert len(set(spoken.values())) == len(spoken), "two certainty values collapsed"


def test_likely_is_silence_in_terse_exactly_as_in_normal() -> None:
    assert PARKING_CERTAINTY_LABELS["likely"] == ""
    assert TERSE_PARKING_LABELS["likely"] == ""


def test_unknown_is_spoken_not_verified_never_unverified() -> None:
    assert TERSE_PARKING_LABELS["unknown"] == "Parking not verified."


# -- slot grammar (docs/ontology.md) -------------------------------------------


def test_hazard_family_cues_speak_thing_distance_target_speed() -> None:
    assert (
        brake_lights_cue("2.1 miles", "38 miles per hour", "38").terse
        == "Brake lights, 2.1 miles, 38."
    )
    assert (
        merging_traffic_cue("box truck", "0.4 miles", "45 miles per hour", "45").terse
        == "Merging box truck, 0.4 miles, 45."
    )
    assert (
        slow_lead_cue("car", "1.2 miles", "40 miles per hour", "40").terse
        == "Slow car, 1.2 miles, 40."
    )


def test_hazard_family_cues_keep_their_normal_coaching() -> None:
    assert (
        brake_lights_cue("2.1 miles", "38 miles per hour", "38").normal
        == "Brake lights 2.1 miles ahead. Ease down and leave room for 38 miles per hour."
    )
    assert (
        merging_traffic_cue("box truck", "0.4 miles", "45 miles per hour", "45").normal
        == "Merging box truck 0.4 miles ahead. Hold your lane, leave a gap, "
        "and be ready for 45 miles per hour."
    )
    assert (
        slow_lead_cue("car", "1.2 miles", "40 miles per hour", "40").normal
        == "Slow car 1.2 miles ahead. Be ready near 40 miles per hour."
    )


def test_stop_callout_speaks_name_exit_distance_qualifier() -> None:
    pair = stop_callout(
        planned_prefix="",
        typed_name="travel center: Flying J Travel Center Corfu",
        plain_name="Flying J Travel Center Corfu",
        exit_label="exit 48A",
        distance="5 miles",
        parking_normal="confirmed truck parking",
        parking_certainty="confirmed",
    )
    assert pair.normal == (
        "travel center: Flying J Travel Center Corfu at exit 48A in 5 miles. "
        "confirmed truck parking. Press X to signal for the exit."
    )
    assert pair.terse == "Flying J Travel Center Corfu, exit 48A, 5 miles. Parking confirmed."


def test_stop_callout_without_exit_or_parking_keeps_the_frame() -> None:
    pair = stop_callout(
        planned_prefix="Planned stop, ",
        typed_name="public rest area: Sweetwater Rest Area",
        plain_name="Sweetwater Rest Area",
        exit_label="",
        distance="3 miles",
        parking_normal="",
        parking_certainty="likely",
    )
    assert pair.terse == "Planned stop, Sweetwater Rest Area, 3 miles."
    assert "Press X" in pair.normal


def test_the_terse_stop_callout_never_drops_a_bad_parking_verdict() -> None:
    pair = stop_callout(
        planned_prefix="",
        typed_name="truck fuel station: Corner Pump",
        plain_name="Corner Pump",
        exit_label="",
        distance="2 miles",
        parking_normal="no truck parking",
        parking_certainty="none",
    )
    assert pair.terse == "Corner Pump, 2 miles. No truck parking."


def test_the_charged_toll_speaks_what_amount_who_pays() -> None:
    pair = toll_charged("E-ZPass", "New York State Thruway settlement", "15", True)
    assert pair.normal == (
        "E-ZPass toll charged at New York State Thruway settlement: "
        "Estimated 15 dollars, billed to carrier settlement."
    )
    assert pair.terse == "Toll, 15 dollars, carrier."


def test_the_speed_nag_compresses_to_the_limit() -> None:
    pair = overspeed_nag("65 miles per hour", "65")
    assert pair.normal == "Watch your speed. The limit is 65 miles per hour."
    assert pair.terse == "Limit 65."


def test_the_cruise_easing_clause_folds_into_the_pacenote_in_terse() -> None:
    pair = cruise_curve_easing(
        "Sharp left, half a mile. Advise 35 miles per hour.", "35 miles per hour"
    )
    assert pair.normal == (
        "Sharp left, half a mile. Advise 35 miles per hour. "
        "Adaptive cruise easing to 35 miles per hour for the bend."
    )
    assert pair.terse == "Sharp left, half a mile. Advise 35 miles per hour."


def test_an_achievement_is_its_name_alone_in_terse() -> None:
    pair = achievement_unlocked("Bumper-to-Bumper Blues", "Heavy traffic, and you kept it sane.")
    assert pair.normal == (
        "New achievement! Bumper-to-Bumper Blues. Heavy traffic, and you kept it sane."
    )
    assert pair.terse == "Bumper-to-Bumper Blues."


# -- the pairs actually ride the events ----------------------------------------


def test_settings_speed_value_is_the_bare_number_in_the_player_unit() -> None:
    from freight_fate.settings import Settings

    s = Settings()
    s.imperial_units = True
    assert s.speed_value(65) == "65"
    s.imperial_units = False
    assert s.speed_value(65) == "105"
