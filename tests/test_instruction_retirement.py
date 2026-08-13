"""R7: instructions retire once the player has demonstrated them, and re-arm
when the control binding or the transmission changes."""

from freight_fate.models.profile import Profile
from freight_fate.speech_text import stop_callout
from freight_fate.spoken_advice import (
    RETIRE_AFTER,
    instruction_retired,
    note_demonstrated,
)


def test_an_instruction_retires_after_a_few_demonstrations():
    p = Profile(name="Retire")
    assert not instruction_retired(p, "engine", binding="E", automatic=True)
    for _ in range(RETIRE_AFTER):
        note_demonstrated(p, "engine", binding="E", automatic=True)
    assert instruction_retired(p, "engine", binding="E", automatic=True)


def test_a_remapped_binding_re_teaches():
    p = Profile(name="Rebind")
    for _ in range(RETIRE_AFTER):
        note_demonstrated(p, "engine", binding="E", automatic=True)
    assert instruction_retired(p, "engine", binding="E", automatic=True)
    # A different control (a controller, or a remap) is a different key: the
    # count starts over so the new control is taught.
    assert not instruction_retired(p, "engine", binding="right bumper plus A", automatic=True)


def test_a_transmission_switch_re_teaches():
    p = Profile(name="Shift")
    for _ in range(RETIRE_AFTER):
        note_demonstrated(p, "engine", binding="E", automatic=True)
    assert instruction_retired(p, "engine", binding="E", automatic=True)
    assert not instruction_retired(p, "engine", binding="E", automatic=False)


def test_the_count_does_not_run_away_past_the_threshold():
    p = Profile(name="Cap")
    for _ in range(RETIRE_AFTER + 10):
        count = note_demonstrated(p, "help", binding="F1", automatic=True)
    assert count == RETIRE_AFTER


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Wheel Entry", current_city="Denver")
    job = Job(
        CARGO_CATALOG["general"], 12.0, "Denver", "yard", "Salt Lake City", 200.0, 900.0, 12.0
    )
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    return DrivingState(app.ctx, job, route, trip_seed=1, start_hour=10.0)


def test_the_wheel_entry_line_retires_the_engine_and_help_hints():
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving(app)
        driving.truck.stop_engine()
        # Fresh: both instructions are taught.
        assert "start the engine" in driving._engine_entry_instruction()
        assert driving._help_hint_tail() != ""

        for _ in range(RETIRE_AFTER):
            driving._note_instruction_demonstrated("engine")
            driving._note_instruction_demonstrated("help")

        # Demonstrated: the key prompts fall away, the state note remains.
        assert driving._engine_entry_instruction() == "Engine off."
        assert driving._help_hint_tail() == ""
    finally:
        app.shutdown()


def test_arming_the_exit_signal_eventually_silences_the_callout_instruction():
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving(app)
        driving._refresh_exit_hint()
        assert driving.trip.exit_hint == "X"
        for _ in range(RETIRE_AFTER):
            driving._note_instruction_demonstrated("take_exit")
        driving._refresh_exit_hint()
        assert driving.trip.exit_hint == ""
    finally:
        app.shutdown()


def test_stop_callout_drops_the_exit_instruction_when_the_hint_is_empty():
    def _callout(exit_hint):
        return stop_callout(
            planned_prefix="",
            typed_name="travel center: Flying J",
            plain_name="Flying J",
            exit_label="exit 48A",
            distance="5 miles",
            parking_normal="confirmed truck parking",
            parking_certainty="confirmed",
            exit_hint=exit_hint,
        )

    taught = _callout("X")
    retired = _callout("")
    assert "Press X to signal for the exit." in taught.normal
    assert "signal for the exit" not in retired.normal
    # The route facts survive either way.
    assert "Flying J" in retired.normal
    assert "confirmed truck parking" in retired.normal
