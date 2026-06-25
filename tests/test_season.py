"""Career calendar, seasons, and the regional temperature model."""

import pytest

from freight_fate.sim.season import (
    CAREER_START_DAY_OF_YEAR,
    FREEZING_C,
    adjust_for_temperature,
    day_of_year,
    is_freezing,
    season,
    temperature_c,
    temperature_text,
)
from freight_fate.sim.weather import WeatherKind


def _hours_for_day(target_doy: float) -> float:
    """Career hours that land on a given day of the year."""
    return ((target_doy - CAREER_START_DAY_OF_YEAR) % 365.0) * 24.0


def test_career_starts_in_spring():
    assert day_of_year(0.0) == pytest.approx(CAREER_START_DAY_OF_YEAR)
    assert season(0.0) == "spring"


def test_seasons_track_the_day_of_year():
    assert season(_hours_for_day(15)) == "winter"    # mid January
    assert season(_hours_for_day(100)) == "spring"   # mid April
    assert season(_hours_for_day(200)) == "summer"   # mid July
    assert season(_hours_for_day(280)) == "autumn"   # early October


def test_summer_is_warmer_than_winter():
    winter = temperature_c("great_lakes", _hours_for_day(15) + 15)  # mid-afternoon
    summer = temperature_c("great_lakes", _hours_for_day(200) + 15)
    assert summer > winter
    assert winter < FREEZING_C  # a Great Lakes January is below freezing


def test_nights_are_colder_than_afternoons():
    day = temperature_c("heartland", _hours_for_day(200) + 15)   # 3 PM
    night = temperature_c("heartland", _hours_for_day(200) + 4)  # 4 AM
    assert night < day


def test_climate_differs_by_region():
    summer_afternoon = _hours_for_day(200) + 15
    assert (temperature_c("desert_southwest", summer_afternoon)
            > temperature_c("great_lakes", summer_afternoon))
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


def test_temperature_text_uses_player_units():
    hours = _hours_for_day(200) + 15
    assert temperature_text("florida", hours, imperial=True).endswith("Fahrenheit")
    assert temperature_text("florida", hours, imperial=False).endswith("Celsius")
