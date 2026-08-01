"""Readouts that used to speak miles no matter what the units setting said.

The units setting always converted the driving cues, so a metric player heard
kilometers out on the road and then raw miles the moment they opened dispatch,
career stats, or the delivery summary. These lock each of those surfaces to the
player's own unit.
"""

from freight_fate.settings import Settings
from freight_fate.units import (
    MILES_TO_KM,
    distance_unit,
    hud_speed,
    spoken_gap,
    to_distance,
)


def _metric() -> Settings:
    s = Settings()
    s.imperial_units = False
    return s


def _imperial() -> Settings:
    s = Settings()
    s.imperial_units = True
    return s


def test_to_distance_leaves_imperial_alone_and_converts_metric():
    assert to_distance(100.0, True) == 100.0
    assert to_distance(100.0, False) == 100.0 * MILES_TO_KM


def test_distance_unit_names_both_settings_singular_and_plural():
    assert distance_unit(True) == "miles"
    assert distance_unit(True, plural=False) == "mile"
    assert distance_unit(False) == "kilometers"
    assert distance_unit(False, plural=False) == "kilometer"


def test_spoken_gap_keeps_one_decimal_in_both_units():
    assert spoken_gap(2.0, True) == "2.0 miles"
    assert spoken_gap(2.0, False) == "3.2 kilometers"


def test_hud_speed_uses_the_short_written_form():
    assert hud_speed(55.0, True) == "55 mph"
    assert hud_speed(55.0, False) == "89 km/h"


def test_distance_value_and_unit_pair_up_for_two_number_readouts():
    s = _metric()
    assert s.distance_value(100.0) == "161"
    assert s.distance_value(100.0, 1) == "160.9"
    assert s.distance_value(1000.0, grouped=True) == "1,609"
    assert s.distance_unit_text() == "kilometers"


def test_per_distance_rescales_a_per_mile_rate():
    # $3.22 a mile is $2.00 a kilometer -- the rate falls, it does not rise.
    assert _imperial().per_distance(3.218688) == 3.218688
    assert round(_metric().per_distance(3.218688), 2) == 2.0


def test_route_departure_summary_speaks_the_players_unit():
    from freight_fate.states.city_pickup import route_departure_summary

    class _Route:
        miles = 100.0
        highways = ["I-90"]
        estimated_tolls = 0.0

    assert "161 kilometers" in route_departure_summary(_Route(), _metric())
    assert "100 miles" in route_departure_summary(_Route(), _imperial())


def test_job_detail_reads_distance_and_rate_in_metric():
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState, JobDetailState

    app = App()
    try:
        app.ctx.settings.imperial_units = False
        app.ctx.profile = Profile(name="Metric", current_city="Buffalo")
        route = app.ctx.world.supported_route("Buffalo", "Rochester")
        job = Job(
            CARGO_CATALOG["general"],
            12.0,
            "Buffalo",
            "company yard",
            "Rochester",
            route.miles,
            1000.0,
            12.0,
            destination_location="Rochester freight market",
        )
        board = JobBoardState(app.ctx, [job])
        lines = JobDetailState(app.ctx, board, job)._detail_lines()
        joined = " ".join(lines)
        assert "kilometers" in joined
        assert "Dollars per kilometer" in joined
        assert "mile" not in joined
    finally:
        app.shutdown()


def test_career_stats_label_follows_the_units_setting():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.career_stats import CareerStatsState

    app = App()
    try:
        app.ctx.profile = Profile(name="Metric", current_city="Buffalo")
        app.ctx.profile.career.total_miles = 1000.0
        app.ctx.settings.imperial_units = False
        lines = CareerStatsState(app.ctx)._lines()
        assert "Lifetime kilometers: 1,609" in " ".join(lines)

        app.ctx.settings.imperial_units = True
        lines = CareerStatsState(app.ctx)._lines()
        assert "Lifetime miles: 1,000" in " ".join(lines)
    finally:
        app.shutdown()


def test_driving_hud_shows_metric_speed_and_remaining_distance():
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        app.ctx.settings.imperial_units = False
        app.ctx.profile = Profile(name="Metric", current_city="Buffalo")
        route = app.ctx.world.supported_route("Buffalo", "Rochester")
        job = Job(
            CARGO_CATALOG["general"],
            12.0,
            "Buffalo",
            "company yard",
            "Rochester",
            route.miles,
            1000.0,
            12.0,
            destination_location="Rochester freight market",
        )
        d = DrivingState(app.ctx, job, route, phase="delivery")
        d.truck.velocity_mps = 55.0 / 2.23694  # 55 mph
        joined = " ".join(d.lines())
        assert "Speed: 89 km/h" in joined
        assert "kilometers" in joined
        assert "mph" not in joined
    finally:
        app.shutdown()
