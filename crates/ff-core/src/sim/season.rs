//! Career calendar, seasons, and a regional temperature model.
//!
//! The career clock (`game_hours`, hours since career start) already encodes
//! both the date and the time of day: `game_hours // 24` is the day and
//! `game_hours % 24` is the clock hour. From it we derive a day of the year, a
//! season, and a grounded outdoor temperature per region -- a smooth seasonal
//! swing (coldest in mid-January, warmest in mid-July) plus a daily swing
//! (coldest before dawn, warmest mid-afternoon). Temperature in turn decides
//! whether precipitation falls as rain or snow and whether storms can brew, so
//! snow becomes a cold-season risk and thunderstorms a warm-season one.
//!
//! Everything here is pure and deterministic so the headless tests can exercise
//! it directly, and it is shared by the simulated weather and any display.
//!
//! Port of `freight_fate/sim/season.py`.

use std::f64::consts::PI;

use chrono::{Datelike, Local, NaiveDate, NaiveDateTime, Timelike, Weekday};

use super::weather::WeatherKind;
use crate::pyfmt::fmt_f;

pub const DAYS_PER_YEAR: f64 = 365.0;
/// New drivers start in early spring (~March 21) so a career eases in through
/// mild weather before the first winter arrives.
pub const CAREER_START_DAY_OF_YEAR: f64 = 80.0;

pub const SEASONS: [&str; 4] = ["winter", "spring", "summer", "autumn"];

// Temperatures at which precipitation type and ice risk flip, in Celsius.
/// At or below this, rain falls as snow and ice forms.
pub const FREEZING_C: f64 = 1.0;
/// Rain in the (floor, freezing] band glazes as ice.
pub const FREEZING_RAIN_FLOOR_C: f64 = -4.0;
/// Thunderstorms need convective warmth above this.
pub const WARM_STORM_C: f64 = 12.0;

/// Per region: (annual mean C, seasonal half-swing C, daily half-swing C).
/// Rough climatological values -- cold northern tier, hot desert and Gulf,
/// mild coasts -- tuned for plausible season/temperature feel, not forecasting.
pub const REGION_CLIMATE: [(&str, (f64, f64, f64)); 16] = [
    ("northeast", (9.0, 13.0, 6.0)),
    ("appalachia", (11.0, 11.0, 7.0)),
    ("great_lakes", (8.0, 14.0, 6.0)),
    // Coldest tier: the Iron Range and Upper Peninsula run Duluth-like
    // winters, well below the lower-lakes belt.
    ("upper_midwest", (4.5, 16.0, 7.0)),
    // Continental interior between the lakes and the plains.
    ("corn_belt", (11.0, 14.0, 8.0)),
    ("heartland", (11.0, 14.0, 7.0)),
    ("southern_plains", (17.0, 11.0, 8.0)),
    ("mid_south", (16.0, 11.0, 7.0)),
    ("atlantic_southeast", (17.0, 9.0, 7.0)),
    ("gulf_coast", (20.0, 8.0, 6.0)),
    ("florida", (23.0, 6.0, 6.0)),
    ("rockies", (5.0, 12.0, 9.0)),
    ("great_basin", (9.0, 13.0, 11.0)),
    ("desert_southwest", (21.0, 12.0, 12.0)),
    ("california", (16.0, 7.0, 8.0)),
    ("pacific_northwest", (11.0, 8.0, 6.0)),
];
/// `REGION_CLIMATE["heartland"]`.
pub const DEFAULT_CLIMATE: (f64, f64, f64) = (11.0, 14.0, 7.0);

/// `REGION_CLIMATE.get(region, DEFAULT_CLIMATE)`.
pub fn region_climate(region: &str) -> (f64, f64, f64) {
    REGION_CLIMATE
        .iter()
        .find(|(name, _)| *name == region)
        .map(|(_, climate)| *climate)
        .unwrap_or(DEFAULT_CLIMATE)
}

// Day of year (mid-January) when the seasonal cycle bottoms out, and clock
// hour when the daily cycle peaks.
const COLDEST_DAY: f64 = 15.0;
const WARMEST_HOUR: f64 = 15.0;

/// Day of the year (0..365) for a point on the career clock.
pub fn day_of_year(game_hours: f64) -> f64 {
    (CAREER_START_DAY_OF_YEAR + game_hours / 24.0).rem_euclid(DAYS_PER_YEAR)
}

/// A `game_hours` value equivalent to the real wall-clock date and time.
///
/// Lets the season and temperature helpers run off the real calendar -- used
/// when live weather is on, so the season the game reports matches the live
/// conditions -- without special-casing them: the returned value reproduces
/// the real day of the year and clock hour.
///
/// `now` defaults to the local wall clock (`datetime.datetime.now()`).
pub fn real_clock_game_hours(now: Option<NaiveDateTime>) -> f64 {
    let now = now.unwrap_or_else(|| Local::now().naive_local());
    let doy = f64::from(now.ordinal()); // 1..366
    let hour = f64::from(now.hour()) + f64::from(now.minute()) / 60.0;
    let days_offset = (doy - CAREER_START_DAY_OF_YEAR).rem_euclid(DAYS_PER_YEAR);
    days_offset * 24.0 + hour
}

/// The clock the player's own calendar runs on.
///
/// There are two clocks in a career and only one of them is ever spoken. The
/// raw `game_hours` is elapsed career time; what the player is TOLD the
/// date is comes from here -- the real wall-clock date when live weather is
/// driving the calendar, otherwise career time plus the profile's own
/// calendar offset. Every date the game reads back to a player, and every
/// badge that answers to a date, has to use this one.
///
/// `live_calendar` is the caller's answer to "is live weather driving the
/// calendar right now", which needs both a weather provider and the
/// `live_weather_controls_calendar` setting. The caller knows; this does
/// not, and guessing here is how the two clocks drifted apart in the first
/// place (the April 1 badge fired in August, 2026-08-11).
///
/// The Python original duck-typed a profile (`profile.game_hours` plus an
/// optional `calendar_game_hours`); here the caller passes the two numbers:
/// `calendar_game_hours` is the profile's offset calendar clock when it has
/// one, `game_hours` the raw career clock it falls back to.
pub fn player_calendar_hours(
    game_hours: f64,
    calendar_game_hours: Option<f64>,
    live_calendar: bool,
) -> f64 {
    if live_calendar {
        return real_clock_game_hours(None);
    }
    calendar_game_hours.unwrap_or(game_hours)
}

// Careers start on the calendar anchor March 21, 2001 -- a Wednesday -- so
// the day of the week falls out of the career clock directly.
const CAREER_START_WEEKDAY: i64 = 2;
pub const WEEKDAY_NAMES: [&str; 7] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
];

/// Day of the week (0=Monday .. 6=Sunday) for a point on the career clock.
pub fn day_of_week(game_hours: f64) -> usize {
    let days = (game_hours / 24.0).floor() as i64;
    (CAREER_START_WEEKDAY + days).rem_euclid(7) as usize
}

pub fn weekday_name(game_hours: f64) -> &'static str {
    WEEKDAY_NAMES[day_of_week(game_hours)]
}

/// Saturday or Sunday: commuter rush hours do not form.
pub fn is_weekend(game_hours: f64) -> bool {
    day_of_week(game_hours) >= 5
}

/// Northern-hemisphere season for the career clock.
pub fn season(game_hours: f64) -> &'static str {
    let doy = day_of_year(game_hours);
    if !(60.0..335.0).contains(&doy) {
        return "winter";
    }
    if doy < 152.0 {
        return "spring";
    }
    if doy < 244.0 {
        return "summer";
    }
    "autumn"
}

const MONTH_NAMES: [&str; 12] = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
];

/// The 2001 calendar date for a point on the clock: the career runs a fixed
/// 365-day (non-leap) year mapped onto 2001, where January 1 is day-of-year 1.
fn calendar_date(game_hours: f64) -> NaiveDate {
    let doy = day_of_year(game_hours).trunc() as i64;
    let jan_1 = NaiveDate::from_ymd_opt(2001, 1, 1).expect("2001-01-01 is a valid date");
    jan_1 + chrono::Duration::days((doy - 1).rem_euclid(365))
}

/// The career's calendar date for a point on the clock, e.g. 'March 21'.
///
/// The career runs a fixed 365-day (non-leap) year; day-of-year 80 -- the start
/// of a career -- is March 21.
pub fn date_text(game_hours: f64) -> String {
    let date = calendar_date(game_hours);
    format!("{} {}", MONTH_NAMES[date.month0() as usize], date.day())
}

/// Whether the career calendar has landed on a Friday the thirteenth.
///
/// The career runs the same fixed 365-day year every lap, mapped onto 2001,
/// so the unlucky dates are the ones 2001 had -- and they come round again
/// each career year, which is what a superstition wants anyway.
pub fn is_friday_the_thirteenth(game_hours: f64) -> bool {
    let date = calendar_date(game_hours);
    date.day() == 13 && date.weekday() == Weekday::Fri
}

/// Which year of the career this clock falls in (1 on the first lap of the
/// calendar, 2 after a full year, ...). Always 1 for the real-calendar clock.
pub fn career_year(game_hours: f64) -> i64 {
    (game_hours / (24.0 * DAYS_PER_YEAR)).floor() as i64 + 1
}

/// Outdoor temperature in Celsius: seasonal swing plus a daily swing.
pub fn temperature_c(region: &str, game_hours: f64) -> f64 {
    let (mean, seasonal_amp, daily_amp) = region_climate(region);
    let doy = day_of_year(game_hours);
    let hour = game_hours.rem_euclid(24.0);
    let seasonal = mean - seasonal_amp * (2.0 * PI * (doy - COLDEST_DAY) / DAYS_PER_YEAR).cos();
    let daily = daily_amp * (2.0 * PI * (hour - WARMEST_HOUR) / 24.0).cos();
    seasonal + daily
}

pub fn is_freezing(region: &str, game_hours: f64) -> bool {
    temperature_c(region, game_hours) <= FREEZING_C
}

/// Reconcile a sampled condition with the temperature.
///
/// Precipitation falls as snow when it is freezing and as rain when it is not;
/// thunderstorms need warmth to form. Dry conditions (clear, cloudy, fog,
/// wind) are temperature-agnostic and pass through unchanged. With no
/// temperature known (`None`), the condition is returned as sampled.
pub fn adjust_for_temperature(kind: WeatherKind, temp_c: Option<f64>) -> WeatherKind {
    let Some(temp_c) = temp_c else {
        return kind;
    };
    let wet = [
        WeatherKind::Rain,
        WeatherKind::HeavyRain,
        WeatherKind::Thunderstorm,
    ];
    if temp_c <= FREEZING_C {
        if kind == WeatherKind::Rain && temp_c > FREEZING_RAIN_FLOOR_C {
            // The freezing-rain band: rain that glazes on contact. Colder than
            // the band (or heavier precipitation) falls as plain snow.
            return WeatherKind::Ice;
        }
        if wet.contains(&kind) {
            return WeatherKind::Snow;
        }
        return kind;
    }
    if kind == WeatherKind::Snow || kind == WeatherKind::Ice {
        // Too warm to freeze: a cold rain, or just overcast when mild.
        return if temp_c < 6.0 {
            WeatherKind::Rain
        } else {
            WeatherKind::Cloudy
        };
    }
    if kind == WeatherKind::Thunderstorm && temp_c < WARM_STORM_C {
        return WeatherKind::HeavyRain;
    }
    kind
}

/// Reconcile weather with both temperature and the selected calendar.
///
/// Temperature handles the physical precipitation phase. The season check is
/// the final gameplay guard: snow is winter-only and thunderstorms are
/// summer-only, preventing a live observation from contradicting an
/// independently advancing career calendar.
pub fn adjust_for_calendar(
    kind: WeatherKind,
    temp_c: Option<f64>,
    game_hours: Option<f64>,
) -> WeatherKind {
    let adjusted = adjust_for_temperature(kind, temp_c);
    let Some(game_hours) = game_hours else {
        return adjusted;
    };
    let current_season = season(game_hours);
    if adjusted == WeatherKind::Snow && current_season != "winter" {
        return match temp_c {
            Some(t) if t < 6.0 => WeatherKind::Rain,
            _ => WeatherKind::Cloudy,
        };
    }
    if adjusted == WeatherKind::Thunderstorm && current_season != "summer" {
        return WeatherKind::HeavyRain;
    }
    adjusted
}

/// Spoken temperature in the player's units.
pub fn temperature_text(region: &str, game_hours: f64, imperial: bool) -> String {
    let temp_c = temperature_c(region, game_hours);
    if imperial {
        return format!("{} degrees Fahrenheit", fmt_f(temp_c * 9.0 / 5.0 + 32.0, 0));
    }
    format!("{} degrees Celsius", fmt_f(temp_c, 0))
}

#[cfg(test)]
mod tests {
    //! Ported from `tests/test_season.py` (career calendar, seasons, and the
    //! regional temperature model) plus `test_career_clock_weekdays` from
    //! `tests/test_congestion.py`, the one pure-season test living there.
    use super::*;
    use crate::sim::weather::test_support::new_system;
    use crate::sim::weather::WeatherProvider;
    use chrono::NaiveDate;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() <= 1e-6 * b.abs().max(1e-12)
    }

    /// Career hours that land on a given day of the year.
    fn hours_for_day(target_doy: f64) -> f64 {
        (target_doy - CAREER_START_DAY_OF_YEAR).rem_euclid(365.0) * 24.0
    }

    #[test]
    fn test_career_start_weekday_is_the_2001_anchor() {
        // `datetime.date(2001, 3, 21).weekday()` -- pinned so the hardcoded
        // constant can never drift from the calendar it stands for.
        let anchor = NaiveDate::from_ymd_opt(2001, 3, 21).unwrap();
        assert_eq!(
            i64::from(anchor.weekday().num_days_from_monday()),
            CAREER_START_WEEKDAY
        );
    }

    #[test]
    fn test_date_text_starts_at_march_21_and_advances() {
        assert_eq!(date_text(0.0), "March 21"); // day-of-year 80, career start
        assert_eq!(date_text(24.0 * 11.0), "April 1"); // eleven days on
        assert_eq!(date_text(24.0 * 100.0), "June 29"); // a hundred days on
                                                        // The fixed 365-day year wraps cleanly back to the start.
        assert_eq!(date_text(24.0 * DAYS_PER_YEAR), "March 21");
    }

    #[test]
    fn test_career_year_increments_after_a_full_year() {
        assert_eq!(career_year(0.0), 1);
        assert_eq!(career_year(24.0 * (DAYS_PER_YEAR - 1.0)), 1);
        assert_eq!(career_year(24.0 * DAYS_PER_YEAR), 2);
    }

    #[test]
    #[ignore = "needs models::profile (Profile.anchor_calendar_to)"]
    fn test_profile_calendar_offset_changes_date_without_changing_career_time() {
        // TODO(port): port with models::profile; the date_text side is covered above.
    }

    #[test]
    fn test_weather_system_exposes_date_text() {
        let sim = new_system("heartland", Some(1), None, Some(0.0), true);
        assert_eq!(sim.date_text().as_deref(), Some("March 21"));
        assert_eq!(sim.season(), Some("spring"));
        // No clock and no provider -> no calendar.
        assert_eq!(
            new_system("heartland", Some(1), None, None, true).date_text(),
            None
        );
    }

    #[test]
    fn test_career_starts_in_spring() {
        assert!(approx(day_of_year(0.0), CAREER_START_DAY_OF_YEAR));
        assert_eq!(season(0.0), "spring");
    }

    #[test]
    fn test_seasons_track_the_day_of_year() {
        assert_eq!(season(hours_for_day(15.0)), "winter"); // mid January
        assert_eq!(season(hours_for_day(100.0)), "spring"); // mid April
        assert_eq!(season(hours_for_day(200.0)), "summer"); // mid July
        assert_eq!(season(hours_for_day(280.0)), "autumn"); // early October
    }

    #[test]
    fn test_summer_is_warmer_than_winter() {
        let winter = temperature_c("great_lakes", hours_for_day(15.0) + 15.0); // mid-afternoon
        let summer = temperature_c("great_lakes", hours_for_day(200.0) + 15.0);
        assert!(summer > winter);
        assert!(winter < FREEZING_C); // a Great Lakes January is below freezing
    }

    #[test]
    fn test_nights_are_colder_than_afternoons() {
        let day = temperature_c("heartland", hours_for_day(200.0) + 15.0); // 3 PM
        let night = temperature_c("heartland", hours_for_day(200.0) + 4.0); // 4 AM
        assert!(night < day);
    }

    #[test]
    fn test_climate_differs_by_region() {
        let summer_afternoon = hours_for_day(200.0) + 15.0;
        assert!(
            temperature_c("desert_southwest", summer_afternoon)
                > temperature_c("great_lakes", summer_afternoon)
        );
        // The Gulf Coast does not freeze the way the northern tier does in winter.
        let winter_night = hours_for_day(15.0) + 4.0;
        assert!(!is_freezing("gulf_coast", winter_night));
        assert!(is_freezing("great_lakes", winter_night));
    }

    #[test]
    fn test_precipitation_falls_as_snow_when_freezing() {
        let cold = Some(FREEZING_C - 5.0);
        assert_eq!(
            adjust_for_temperature(WeatherKind::Rain, cold),
            WeatherKind::Snow
        );
        assert_eq!(
            adjust_for_temperature(WeatherKind::HeavyRain, cold),
            WeatherKind::Snow
        );
        assert_eq!(
            adjust_for_temperature(WeatherKind::Thunderstorm, cold),
            WeatherKind::Snow
        );
        assert_eq!(
            adjust_for_temperature(WeatherKind::Snow, cold),
            WeatherKind::Snow
        );
    }

    #[test]
    fn test_rain_in_the_freezing_band_glazes_as_ice() {
        // Rain just below freezing glazes on contact -- freezing rain. Colder than
        // the band it is plain snow, and only rain glazes: heavier precipitation
        // in the same band still falls as snow.
        let in_band = Some((FREEZING_C + FREEZING_RAIN_FLOOR_C) / 2.0);
        assert_eq!(
            adjust_for_temperature(WeatherKind::Rain, in_band),
            WeatherKind::Ice
        );
        assert_eq!(
            adjust_for_temperature(WeatherKind::HeavyRain, in_band),
            WeatherKind::Snow
        );
        assert_eq!(
            adjust_for_temperature(WeatherKind::Rain, Some(FREEZING_RAIN_FLOOR_C - 2.0)),
            WeatherKind::Snow
        );
        // Ice persists while it stays cold, and thaws the way snow does.
        assert_eq!(
            adjust_for_temperature(WeatherKind::Ice, in_band),
            WeatherKind::Ice
        );
        assert_eq!(
            adjust_for_temperature(WeatherKind::Ice, Some(4.0)),
            WeatherKind::Rain
        );
        assert_eq!(
            adjust_for_temperature(WeatherKind::Ice, Some(20.0)),
            WeatherKind::Cloudy
        );
    }

    #[test]
    fn test_snow_thaws_to_rain_or_cloud_when_warm() {
        assert_eq!(
            adjust_for_temperature(WeatherKind::Snow, Some(4.0)),
            WeatherKind::Rain
        );
        assert_eq!(
            adjust_for_temperature(WeatherKind::Snow, Some(20.0)),
            WeatherKind::Cloudy
        );
    }

    #[test]
    fn test_thunderstorms_need_warmth() {
        // A cold "storm" is really just heavy rain; a warm one stays a storm.
        assert_eq!(
            adjust_for_temperature(WeatherKind::Thunderstorm, Some(6.0)),
            WeatherKind::HeavyRain
        );
        assert_eq!(
            adjust_for_temperature(WeatherKind::Thunderstorm, Some(25.0)),
            WeatherKind::Thunderstorm
        );
    }

    #[test]
    fn test_calendar_guard_keeps_snow_in_winter_and_storms_in_summer() {
        let summer = Some(hours_for_day(200.0));
        let winter = Some(hours_for_day(15.0));
        assert_eq!(
            adjust_for_calendar(WeatherKind::Snow, Some(-10.0), summer),
            WeatherKind::Rain
        );
        assert_eq!(
            adjust_for_calendar(WeatherKind::Thunderstorm, Some(25.0), winter),
            WeatherKind::HeavyRain
        );
        assert_eq!(
            adjust_for_calendar(WeatherKind::Snow, Some(-10.0), winter),
            WeatherKind::Snow
        );
        assert_eq!(
            adjust_for_calendar(WeatherKind::Thunderstorm, Some(25.0), summer),
            WeatherKind::Thunderstorm
        );
    }

    #[test]
    fn test_dry_conditions_and_unknown_temperature_pass_through() {
        for kind in [
            WeatherKind::Clear,
            WeatherKind::Cloudy,
            WeatherKind::Fog,
            WeatherKind::Wind,
        ] {
            assert_eq!(adjust_for_temperature(kind, Some(-20.0)), kind);
            assert_eq!(adjust_for_temperature(kind, Some(35.0)), kind);
        }
        // No temperature known: leave the sampled condition alone.
        assert_eq!(
            adjust_for_temperature(WeatherKind::Snow, None),
            WeatherKind::Snow
        );
    }

    #[test]
    fn test_real_clock_game_hours_maps_to_the_real_date() {
        let jan = NaiveDate::from_ymd_opt(2026, 1, 15)
            .unwrap()
            .and_hms_opt(3, 0, 0)
            .unwrap(); // mid January, 3 AM
        let jul = NaiveDate::from_ymd_opt(2026, 7, 15)
            .unwrap()
            .and_hms_opt(15, 0, 0)
            .unwrap(); // mid July, 3 PM
        assert_eq!(season(real_clock_game_hours(Some(jan))), "winter");
        assert_eq!(season(real_clock_game_hours(Some(jul))), "summer");
        // The clock hour is preserved (pre-dawn vs mid-afternoon).
        assert!(approx(
            real_clock_game_hours(Some(jan)).rem_euclid(24.0),
            3.0
        ));
        assert!(approx(
            real_clock_game_hours(Some(jul)).rem_euclid(24.0),
            15.0
        ));
    }

    /// Minimal stand-in; no city set, so it stays offline.
    struct OfflineProvider;

    impl WeatherProvider for OfflineProvider {
        fn request(&mut self, _city: &str, _lat: f64, _lon: f64) {}

        fn get(&mut self, _city: &str) -> Option<WeatherKind> {
            None
        }
    }

    #[test]
    fn test_live_weather_makes_season_follow_the_real_clock() {
        // A career clock parked in summer...
        let summer_career = (200.0 - CAREER_START_DAY_OF_YEAR).rem_euclid(365.0) * 24.0;

        // ...with no live weather, the season is the career season.
        let offline = new_system("great_lakes", Some(1), None, Some(summer_career), true);
        assert_eq!(offline.season(), Some("summer"));

        // ...but with a provider (live weather on), the season tracks the real
        // calendar instead, regardless of the career clock.
        let mut live = new_system(
            "great_lakes",
            Some(1),
            Some(Box::new(OfflineProvider)),
            Some(summer_career),
            true,
        );
        assert_eq!(live.season(), Some(season(real_clock_game_hours(None))));
        let modeled = temperature_c("great_lakes", real_clock_game_hours(None));
        assert!((live.temperature_c().unwrap() - modeled).abs() <= 0.5);
    }

    struct ClearProvider;

    impl WeatherProvider for ClearProvider {
        fn request(&mut self, _city: &str, _lat: f64, _lon: f64) {}

        fn get(&mut self, _city: &str) -> Option<WeatherKind> {
            Some(WeatherKind::Clear)
        }
    }

    /// Live conditions do not freeze the career calendar when opted out.
    #[test]
    fn test_live_weather_can_leave_calendar_on_career_clock() {
        let start = hours_for_day(151.0) + 23.5;
        let mut live = new_system(
            "great_lakes",
            Some(1),
            Some(Box::new(ClearProvider)),
            Some(start),
            false,
        );
        let before = live.date_text();
        live.update(60.0);
        assert_ne!(live.date_text(), before);
        assert_eq!(live.date_text(), Some(date_text(start + 1.0)));
        assert_eq!(live.season(), Some(season(start + 1.0)));
    }

    struct ColdSnowProvider;

    impl WeatherProvider for ColdSnowProvider {
        fn request(&mut self, _city: &str, _lat: f64, _lon: f64) {}

        fn get(&mut self, _city: &str) -> Option<WeatherKind> {
            Some(WeatherKind::Snow)
        }

        fn get_temperature(&mut self, _city: &str) -> Option<f64> {
            Some(-10.0)
        }
    }

    #[test]
    fn test_live_snow_is_guarded_by_independent_career_season() {
        let summer = hours_for_day(200.0) + 15.0;
        let mut live = new_system(
            "great_lakes",
            Some(1),
            Some(Box::new(ColdSnowProvider)),
            Some(summer),
            false,
        );
        live.set_city("Chicago", 41.8, -87.6);
        live.update(0.0);
        assert!(live.live);
        assert_eq!(live.season(), Some("summer"));
        assert_ne!(live.current, WeatherKind::Snow);
    }

    #[test]
    fn test_temperature_text_uses_player_units() {
        let hours = hours_for_day(200.0) + 15.0;
        assert!(temperature_text("florida", hours, true).ends_with("Fahrenheit"));
        assert!(temperature_text("florida", hours, false).ends_with("Celsius"));
    }

    #[test]
    #[ignore = "needs App, models::profile and states::city"]
    fn test_terminal_sleep_uses_independent_calendar_with_live_weather() {
        // TODO(port): CityMenuState._time_weather / _sleep readout regression.
    }

    #[test]
    #[ignore = "needs App, models::profile and states::city"]
    fn test_terminal_does_not_present_modeled_temperature_while_live_weather_loads() {
        // TODO(port): CityMenuState "Time and weather" menu transcript.
    }

    #[test]
    #[ignore = "needs App, models::profile and states::city"]
    fn test_terminal_weather_source_ignores_the_online_services_master() {
        // TODO(port): CityMenuState._time_weather with online_services off.
    }

    #[test]
    #[ignore = "needs App, models::profile and states::city"]
    fn test_terminal_reports_old_fresh_observation_as_live_without_updating() {
        // TODO(port): CityMenuState "Time and weather" with a fresh-old provider.
    }

    /// A date badge must fire on the date the player was told it is.
    ///
    /// Reported 2026-08-11: the April 1 achievement fired with the real-time
    /// calendar on, months away from April. The seasonal achievements read the
    /// raw career clock, while every surface the player can hear -- the spoken
    /// date, the season, the weather -- runs on the calendar clock: the real
    /// wall-clock date when live weather drives it, otherwise the career clock
    /// plus the profile's own calendar offset. Two clocks, and the badges were
    /// reading the one nobody sees.
    ///
    /// The Python test carries the numbers in a `Profile`; here the profile's
    /// two clocks are passed directly (`calendar_game_hours` is
    /// `game_hours + calendar_offset_days * 24`, as `Profile` computes it).
    #[test]
    fn test_the_calendar_the_player_hears_is_the_one_achievements_read() {
        // A career sitting on its own day 11 -- April 1 by the raw career clock,
        // which starts on March 21.
        let game_hours = 11.0 * 24.0 + 9.0;
        assert_eq!(date_text(game_hours), "April 1");

        // With the real-time calendar driving things, the player is told the real
        // date, so that is the date the badge has to answer to.
        let real = player_calendar_hours(game_hours, None, true);
        assert_eq!(date_text(real), date_text(real_clock_game_hours(None)));

        // With the independent career calendar, the profile's own offset counts:
        // anchoring the calendar forward must move the badge with it.
        let calendar_game_hours = game_hours + 40.0 * 24.0;
        let career = player_calendar_hours(game_hours, Some(calendar_game_hours), false);
        assert_eq!(date_text(career), date_text(calendar_game_hours));
        assert_ne!(date_text(career), "April 1");
    }

    // -- from tests/test_congestion.py: the career calendar knows its weekdays --

    #[test]
    fn test_career_clock_weekdays() {
        // March 21, 2001 was a Wednesday.
        assert_eq!(day_of_week(0.0), 2);
        assert!(!is_weekend(0.0));
        assert_eq!(day_of_week(3.0 * 24.0), 5); // Saturday
        assert!(is_weekend(3.0 * 24.0));
        assert!(is_weekend(4.0 * 24.0)); // Sunday
        assert!(!is_weekend(5.0 * 24.0)); // Monday
    }

    #[test]
    fn test_weekday_name_and_friday_the_thirteenth_follow_the_2001_calendar() {
        assert_eq!(weekday_name(0.0), "Wednesday");
        assert_eq!(weekday_name(2.0 * 24.0), "Friday");
        // 2001-04-13 was a Friday: day-of-year 103, 23 career days in.
        assert!(is_friday_the_thirteenth(23.0 * 24.0 + 6.0));
        assert!(!is_friday_the_thirteenth(22.0 * 24.0));
        assert!(!is_friday_the_thirteenth(0.0));
    }
}
