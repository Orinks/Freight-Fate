"""Career calendar, seasons, and a regional temperature model.

The career clock (``game_hours``, hours since career start) already encodes
both the date and the time of day: ``game_hours // 24`` is the day and
``game_hours % 24`` is the clock hour. From it we derive a day of the year, a
season, and a grounded outdoor temperature per region -- a smooth seasonal
swing (coldest in mid-January, warmest in mid-July) plus a daily swing
(coldest before dawn, warmest mid-afternoon). Temperature in turn decides
whether precipitation falls as rain or snow and whether storms can brew, so
snow becomes a cold-season risk and thunderstorms a warm-season one.

Everything here is pure and deterministic so the headless tests can exercise
it directly, and it is shared by the simulated weather and any display.
"""

from __future__ import annotations

import datetime
import math

from .weather import WeatherKind

DAYS_PER_YEAR = 365.0
# New drivers start in early spring (~March 21) so a career eases in through
# mild weather before the first winter arrives.
CAREER_START_DAY_OF_YEAR = 80.0

SEASONS = ("winter", "spring", "summer", "autumn")

# Temperatures at which precipitation type and ice risk flip, in Celsius.
FREEZING_C = 1.0  # at or below this, rain falls as snow and ice forms
WARM_STORM_C = 12.0  # thunderstorms need convective warmth above this

# Per region: (annual mean C, seasonal half-swing C, daily half-swing C).
# Rough climatological values -- cold northern tier, hot desert and Gulf,
# mild coasts -- tuned for plausible season/temperature feel, not forecasting.
REGION_CLIMATE: dict[str, tuple[float, float, float]] = {
    "northeast": (9.0, 13.0, 6.0),
    "appalachia": (11.0, 11.0, 7.0),
    "great_lakes": (8.0, 14.0, 6.0),
    "heartland": (11.0, 14.0, 7.0),
    "southern_plains": (17.0, 11.0, 8.0),
    "mid_south": (16.0, 11.0, 7.0),
    "atlantic_southeast": (17.0, 9.0, 7.0),
    "gulf_coast": (20.0, 8.0, 6.0),
    "florida": (23.0, 6.0, 6.0),
    "rockies": (5.0, 12.0, 9.0),
    "great_basin": (9.0, 13.0, 11.0),
    "desert_southwest": (21.0, 12.0, 12.0),
    "california": (16.0, 7.0, 8.0),
    "pacific_northwest": (11.0, 8.0, 6.0),
}
DEFAULT_CLIMATE = REGION_CLIMATE["heartland"]

# Day of year (mid-January) when the seasonal cycle bottoms out, and clock
# hour when the daily cycle peaks.
_COLDEST_DAY = 15.0
_WARMEST_HOUR = 15.0


def day_of_year(game_hours: float) -> float:
    """Day of the year (0..365) for a point on the career clock."""
    return (CAREER_START_DAY_OF_YEAR + game_hours / 24.0) % DAYS_PER_YEAR


def real_clock_game_hours(now: datetime.datetime | None = None) -> float:
    """A ``game_hours`` value equivalent to the real wall-clock date and time.

    Lets the season and temperature helpers run off the real calendar -- used
    when live weather is on, so the season the game reports matches the live
    conditions -- without special-casing them: the returned value reproduces
    the real day of the year and clock hour.
    """
    now = now or datetime.datetime.now()
    doy = now.timetuple().tm_yday  # 1..366
    hour = now.hour + now.minute / 60.0
    days_offset = (doy - CAREER_START_DAY_OF_YEAR) % DAYS_PER_YEAR
    return days_offset * 24.0 + hour


def season(game_hours: float) -> str:
    """Northern-hemisphere season for the career clock."""
    doy = day_of_year(game_hours)
    if doy < 60 or doy >= 335:
        return "winter"
    if doy < 152:
        return "spring"
    if doy < 244:
        return "summer"
    return "autumn"


def date_text(game_hours: float) -> str:
    """The career's calendar date for a point on the clock, e.g. 'March 21'.

    The career runs a fixed 365-day (non-leap) year; day-of-year 80 -- the start
    of a career -- is March 21."""
    doy = int(day_of_year(game_hours))
    # 2001 is a non-leap year; January 1 is day-of-year 1.
    date = datetime.date(2001, 1, 1) + datetime.timedelta(days=(doy - 1) % 365)
    return f"{date:%B} {date.day}"


def career_year(game_hours: float) -> int:
    """Which year of the career this clock falls in (1 on the first lap of the
    calendar, 2 after a full year, ...). Always 1 for the real-calendar clock."""
    return int(game_hours // (24.0 * DAYS_PER_YEAR)) + 1


def temperature_c(region: str, game_hours: float) -> float:
    """Outdoor temperature in Celsius: seasonal swing plus a daily swing."""
    mean, seasonal_amp, daily_amp = REGION_CLIMATE.get(region, DEFAULT_CLIMATE)
    doy = day_of_year(game_hours)
    hour = game_hours % 24.0
    seasonal = mean - seasonal_amp * math.cos(2 * math.pi * (doy - _COLDEST_DAY) / DAYS_PER_YEAR)
    daily = daily_amp * math.cos(2 * math.pi * (hour - _WARMEST_HOUR) / 24.0)
    return seasonal + daily


def is_freezing(region: str, game_hours: float) -> bool:
    return temperature_c(region, game_hours) <= FREEZING_C


def adjust_for_temperature(kind: WeatherKind, temp_c: float | None) -> WeatherKind:
    """Reconcile a sampled condition with the temperature.

    Precipitation falls as snow when it is freezing and as rain when it is not;
    thunderstorms need warmth to form. Dry conditions (clear, cloudy, fog,
    wind) are temperature-agnostic and pass through unchanged. With no
    temperature known (``None``), the condition is returned as sampled.
    """
    if temp_c is None:
        return kind
    wet = (WeatherKind.RAIN, WeatherKind.HEAVY_RAIN, WeatherKind.THUNDERSTORM)
    if temp_c <= FREEZING_C:
        if kind in wet:
            return WeatherKind.SNOW
        return kind
    if kind is WeatherKind.SNOW:
        # Too warm to snow: a cold rain, or just overcast when mild.
        return WeatherKind.RAIN if temp_c < 6.0 else WeatherKind.CLOUDY
    if kind is WeatherKind.THUNDERSTORM and temp_c < WARM_STORM_C:
        return WeatherKind.HEAVY_RAIN
    return kind


def temperature_text(region: str, game_hours: float, imperial: bool = True) -> str:
    """Spoken temperature in the player's units."""
    temp_c = temperature_c(region, game_hours)
    if imperial:
        return f"{temp_c * 9 / 5 + 32:.0f} degrees Fahrenheit"
    return f"{temp_c:.0f} degrees Celsius"
