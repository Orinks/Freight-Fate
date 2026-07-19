"""Kilometer mode stays kilometers everywhere it speaks a distance.

Forum report (Cosgrach, 2026-07-17): with units set to kilometers, the
dispatch board, route selection, and the exit-signal announcement still
said miles while R spoke kilometers -- "38 miles" on the board, then
"60 kilometers remaining" at the wheel. Every spoken distance now routes
through Settings.distance_text.
"""

from freight_fate.settings import Settings


def _metric() -> Settings:
    s = Settings()
    s.imperial_units = False
    return s


def test_distance_text_units_and_precision():
    s = Settings()
    assert s.distance_text(38.0) == "38 miles"
    assert s.distance_text(1.0) == "1 mile"
    assert s.distance_text(1.0, precise=True) == "1.0 mile"
    assert s.distance_text(1.2, precise=True) == "1.2 miles"

    m = _metric()
    assert m.distance_text(38.0) == "61 kilometers"
    assert m.distance_text(1.2, precise=True) == "1.9 kilometers"
    assert m.distance_text(1 / 1.609344, precise=True) == "1.0 kilometer"
    assert m.distance_text(0.62) == "1 kilometer"


def test_job_description_speaks_the_players_unit(world):
    from freight_fate.models.jobs import JobBoard

    board = JobBoard(world, seed=7)
    job = board.offers("denver_co_us", set(), count=1, level=1)[0]
    m = _metric()
    text = job.describe(distance_text=m.distance_text(job.distance_mi))
    assert "kilometers" in text
    assert "miles" not in text


def test_route_description_speaks_the_players_unit(world):
    route = world.supported_route("denver_co_us", "silverthorne_co_us")
    m = _metric()
    text = route.describe(m.distance_text(route.miles))
    assert "kilometers" in text
    assert "miles" not in text


def test_exit_signal_announcement_speaks_kilometers(monkeypatch):
    """The exact leak from the report: signaling for an exit said
    '1.2 miles ahead' regardless of the units setting."""
    from driving_feature_helpers import quiet_trip, start_drive

    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        app.ctx.settings.imperial_units = False
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))

        class _Stop:
            at_mi = driving.trip.position_mi + 1.2
            type = "travel_center"
            spoken_name = "Test Plaza"
            exit_label = ""

        driving._exit_stop = _Stop()
        driving._exit_signal_on = False
        driving._toggle_exit_signal()

        assert driving._exit_signal_on
        message = spoken[-1]
        assert "kilometers ahead" in message
        assert "miles ahead" not in message
    finally:
        app.shutdown()


def test_no_hardcoded_miles_in_spoken_driving_paths():
    """Source-level tripwire: spoken f-strings in the states package must
    not embed a literal miles figure; Settings.distance_text owns units.
    Allows unit-aware helpers (which branch on the setting) and comments."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "states"
    pattern = re.compile(r"\{[^{}]*:\.\df\}\s*miles")
    offenders = []
    for path in root.glob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and "per hour" not in line and "distance_text or" not in line:
                offenders.append(f"{path.name}:{i}: {line.strip()}")
    assert offenders == [], "hardcoded spoken miles: " + "; ".join(offenders[:5])
