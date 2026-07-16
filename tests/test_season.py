"""Career calendar, seasons, and the regional temperature model."""

import datetime

import pytest

from freight_fate.sim.season import (
    CAREER_START_DAY_OF_YEAR,
    DAYS_PER_YEAR,
    FREEZING_C,
    FREEZING_RAIN_FLOOR_C,
    adjust_for_temperature,
    career_year,
    date_text,
    day_of_year,
    is_freezing,
    real_clock_game_hours,
    season,
    temperature_c,
    temperature_text,
)
from freight_fate.sim.weather import WeatherKind, WeatherSystem


def _hours_for_day(target_doy: float) -> float:
    """Career hours that land on a given day of the year."""
    return ((target_doy - CAREER_START_DAY_OF_YEAR) % 365.0) * 24.0


def test_date_text_starts_at_march_21_and_advances():
    assert date_text(0.0) == "March 21"  # day-of-year 80, career start
    assert date_text(24.0 * 11) == "April 1"  # eleven days on
    assert date_text(24.0 * 100) == "June 29"  # a hundred days on
    # The fixed 365-day year wraps cleanly back to the start.
    assert date_text(24.0 * DAYS_PER_YEAR) == "March 21"


def test_career_year_increments_after_a_full_year():
    assert career_year(0.0) == 1
    assert career_year(24.0 * (DAYS_PER_YEAR - 1)) == 1
    assert career_year(24.0 * DAYS_PER_YEAR) == 2


def test_weather_system_exposes_date_text():
    sim = WeatherSystem("heartland", seed=1, game_hours=0.0)
    assert sim.date_text == "March 21"
    assert sim.season == "spring"
    # No clock and no provider -> no calendar.
    assert WeatherSystem("heartland", seed=1).date_text is None


def test_career_starts_in_spring():
    assert day_of_year(0.0) == pytest.approx(CAREER_START_DAY_OF_YEAR)
    assert season(0.0) == "spring"


def test_seasons_track_the_day_of_year():
    assert season(_hours_for_day(15)) == "winter"  # mid January
    assert season(_hours_for_day(100)) == "spring"  # mid April
    assert season(_hours_for_day(200)) == "summer"  # mid July
    assert season(_hours_for_day(280)) == "autumn"  # early October


def test_summer_is_warmer_than_winter():
    winter = temperature_c("great_lakes", _hours_for_day(15) + 15)  # mid-afternoon
    summer = temperature_c("great_lakes", _hours_for_day(200) + 15)
    assert summer > winter
    assert winter < FREEZING_C  # a Great Lakes January is below freezing


def test_nights_are_colder_than_afternoons():
    day = temperature_c("heartland", _hours_for_day(200) + 15)  # 3 PM
    night = temperature_c("heartland", _hours_for_day(200) + 4)  # 4 AM
    assert night < day


def test_climate_differs_by_region():
    summer_afternoon = _hours_for_day(200) + 15
    assert temperature_c("desert_southwest", summer_afternoon) > temperature_c(
        "great_lakes", summer_afternoon
    )
    # The Gulf Coast does not freeze the way the northern tier does in winter.
    winter_night = _hours_for_day(15) + 4
    assert not is_freezing("gulf_coast", winter_night)
    assert is_freezing("great_lakes", winter_night)


def test_precipitation_falls_as_snow_when_freezing():
    cold = FREEZING_C - 5.0
    assert adjust_for_temperature(WeatherKind.RAIN, cold) is WeatherKind.SNOW
    assert adjust_for_temperature(WeatherKind.HEAVY_RAIN, cold) is WeatherKind.SNOW
    assert adjust_for_temperature(WeatherKind.THUNDERSTORM, cold) is WeatherKind.SNOW
    assert adjust_for_temperature(WeatherKind.SNOW, cold) is WeatherKind.SNOW


def test_rain_in_the_freezing_band_glazes_as_ice():
    # Rain just below freezing glazes on contact -- freezing rain. Colder than
    # the band it is plain snow, and only rain glazes: heavier precipitation
    # in the same band still falls as snow.
    in_band = (FREEZING_C + FREEZING_RAIN_FLOOR_C) / 2.0
    assert adjust_for_temperature(WeatherKind.RAIN, in_band) is WeatherKind.ICE
    assert adjust_for_temperature(WeatherKind.HEAVY_RAIN, in_band) is WeatherKind.SNOW
    assert adjust_for_temperature(WeatherKind.RAIN, FREEZING_RAIN_FLOOR_C - 2.0) is (
        WeatherKind.SNOW
    )
    # Ice persists while it stays cold, and thaws the way snow does.
    assert adjust_for_temperature(WeatherKind.ICE, in_band) is WeatherKind.ICE
    assert adjust_for_temperature(WeatherKind.ICE, 4.0) is WeatherKind.RAIN
    assert adjust_for_temperature(WeatherKind.ICE, 20.0) is WeatherKind.CLOUDY


def test_snow_thaws_to_rain_or_cloud_when_warm():
    assert adjust_for_temperature(WeatherKind.SNOW, 4.0) is WeatherKind.RAIN
    assert adjust_for_temperature(WeatherKind.SNOW, 20.0) is WeatherKind.CLOUDY


def test_thunderstorms_need_warmth():
    # A cold "storm" is really just heavy rain; a warm one stays a storm.
    assert adjust_for_temperature(WeatherKind.THUNDERSTORM, 6.0) is WeatherKind.HEAVY_RAIN
    assert adjust_for_temperature(WeatherKind.THUNDERSTORM, 25.0) is WeatherKind.THUNDERSTORM


def test_dry_conditions_and_unknown_temperature_pass_through():
    for kind in (WeatherKind.CLEAR, WeatherKind.CLOUDY, WeatherKind.FOG, WeatherKind.WIND):
        assert adjust_for_temperature(kind, -20.0) is kind
        assert adjust_for_temperature(kind, 35.0) is kind
    # No temperature known: leave the sampled condition alone.
    assert adjust_for_temperature(WeatherKind.SNOW, None) is WeatherKind.SNOW


def test_real_clock_game_hours_maps_to_the_real_date():
    jan = datetime.datetime(2026, 1, 15, 3, 0)  # mid January, 3 AM
    jul = datetime.datetime(2026, 7, 15, 15, 0)  # mid July, 3 PM
    assert season(real_clock_game_hours(jan)) == "winter"
    assert season(real_clock_game_hours(jul)) == "summer"
    # The clock hour is preserved (pre-dawn vs mid-afternoon).
    assert real_clock_game_hours(jan) % 24 == pytest.approx(3.0)
    assert real_clock_game_hours(jul) % 24 == pytest.approx(15.0)


def test_live_weather_makes_season_follow_the_real_clock():
    # A career clock parked in summer...
    summer_career = ((200 - CAREER_START_DAY_OF_YEAR) % 365.0) * 24.0

    # ...with no live weather, the season is the career season.
    offline = WeatherSystem("great_lakes", seed=1, game_hours=summer_career)
    assert offline.season == "summer"

    # ...but with a provider (live weather on), the season tracks the real
    # calendar instead, regardless of the career clock.
    class _Provider:  # minimal stand-in; no city set, so it stays offline
        def request(self, *a):
            pass

        def get(self, *a):
            return None

    live = WeatherSystem("great_lakes", seed=1, game_hours=summer_career, provider=_Provider())
    assert live.season == season(real_clock_game_hours())
    assert live.temperature_c == pytest.approx(
        temperature_c("great_lakes", real_clock_game_hours()), abs=0.5
    )


def test_temperature_text_uses_player_units():
    hours = _hours_for_day(200) + 15
    assert temperature_text("florida", hours, imperial=True).endswith("Fahrenheit")
    assert temperature_text("florida", hours, imperial=False).endswith("Celsius")
