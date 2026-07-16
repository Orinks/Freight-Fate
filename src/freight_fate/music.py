"""Music catalog and deterministic track selection."""

from __future__ import annotations

import zlib
from dataclasses import dataclass

from .sim.hos import is_night


@dataclass(frozen=True)
class MusicTrack:
    key: str
    title: str
    description: str
    duration_s: float


MENU_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack("menu_theme", "Headlights West", "Warm Americana for new careers", 128.4),
    MusicTrack("menu_first_rig", "Keys To The Rig", "Easy country-rock milestone bed", 143.2),
    MusicTrack("menu_regional_carrier", "Regional Lines", "Confident heartland rock bed", 133.7),
    MusicTrack("menu_fleet_owner", "Yard Lights", "Steady fleet-owner menu bed", 94.6),
    MusicTrack("menu_coast_to_coast", "Coast To Coast Ledger", "Broad road-trip menu bed", 104.7),
    MusicTrack("menu_legendary_haul", "Million Mile Morning", "Late-career Americana bed", 117.5),
)

MENU_ROTATION_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack("menu_urban_roll", "Urban Roll", "Easy city-groove menu bed", 114.5),
)

DAY_DRIVE_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack("open_road", "Open Road", "Easy mid-tempo groove for long hauls", 131.6),
    MusicTrack("drive_desert_two_lane", "Desert Two-Lane", "Dry, spacious daytime road bed", 234.7),
    MusicTrack("drive_mountain_grade", "Mountain Grade", "Measured climb-focused road bed", 154.8),
    MusicTrack("drive_rain_day_cruise", "Rain-Day Cruise", "Gentle rainy daytime drive bed", 173.0),
    MusicTrack("drive_urban_roll", "Urban Roll", "Light city traffic drive bed", 144.8),
    MusicTrack("drive_dawn_push", "Dawn Push", "Soft early-morning drive bed", 114.0),
    MusicTrack(
        "drive_high_plains_wind", "High Plains Wind", "Warm high-plains Americana bed", 183.2
    ),
    MusicTrack("drive_open_sky_run", "Open Sky Run", "Breezy open-sky Americana bed", 176.0),
    MusicTrack(
        "drive_golden_hour_freeway", "Golden Hour Freeway", "Golden-hour heartland drive bed", 184.8
    ),
    MusicTrack("drive_amber_lanes", "Amber Lanes", "Warm sunset freeway drive bed", 129.3),
    MusicTrack(
        "drive_river_valley_roll", "River Valley Roll", "Rolling folk-rock valley bed", 164.1
    ),
    MusicTrack(
        "drive_green_mile_bend", "Green Mile Bend", "Easy fingerpicked river-road bed", 140.9
    ),
    MusicTrack(
        "drive_county_line_cruise", "County Line Cruise", "Laid-back twangy cruising bed", 158.6
    ),
    MusicTrack(
        "drive_two_lane_daydream", "Two-Lane Daydream", "Relaxed two-lane country-rock bed", 127.1
    ),
    MusicTrack("drive_chrome_creek", "Chrome Creek", "Breezy slide-guitar roots bed", 122.6),
    MusicTrack(
        "drive_silver_current", "Silver Current", "Sparkling slide-guitar morning bed", 149.0
    ),
)

NIGHT_DRIVE_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack("night_haul", "Night Haul", "Slow ambient pads for night driving", 204.76),
    MusicTrack("night_midnight_interstate", "Midnight Interstate", "Low night highway bed", 208.4),
    MusicTrack("night_neon_truck_stop", "Neon Truck Stop", "Soft truck-stop approach bed", 153.6),
    MusicTrack("night_rainy_miles", "Rainy Night Miles", "Sparse rainy night bed", 222.4),
    MusicTrack("night_lonely_plains", "Lonely Plains", "Open nighttime plains bed", 239.9),
    MusicTrack("night_mountain_pass", "Mountain Night Pass", "Quiet mountain night bed", 158.4),
    MusicTrack("night_small_hours", "Small Hours", "Slow piano ballad for late-night hauls", 159.6),
    MusicTrack("night_quiet_mile", "Quiet Mile", "Calm electric-piano night bed", 194.6),
    MusicTrack("night_soft_shoulder", "Soft Shoulder", "Soft ambient night-highway bed", 188.0),
    MusicTrack(
        "night_starlight_grade", "Starlight Grade", "Gentle piano mountain-night bed", 227.4
    ),
    MusicTrack(
        "night_high_beam_hush", "High Beam Hush", "Hushed strings-and-piano night bed", 172.3
    ),
)

# Played at the menu (and the title screen of a loaded career) when the career
# clock reads night, in place of the daytime milestone bed.
MENU_NIGHT_TRACK = MusicTrack(
    "menu_theme_night", "Midnight Keys", "Quiet piano ballad for night menus", 169.9
)

# Format pools for the fictional regional radio stations. The first three per
# pool are ElevenLabs-composed (tools/generate_radio.py); the 2026-07 batch is
# Suno-composed via the Zero CLI.
COUNTRY_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack(
        "radio_country_backroads", "Backroads Sunrise", "Outlaw country trucking song", 150.0
    ),
    MusicTrack("radio_country_two_lane", "Two-Lane Towns", "Easy classic country song", 150.0),
    MusicTrack("radio_country_diesel_heart", "Diesel Heart", "Upbeat country rock song", 150.0),
    MusicTrack(
        "radio_country_county_fair", "County Fair", "Upbeat county-fair country song", 164.3
    ),
    MusicTrack("radio_country_porch_light", "Porch Light", "Warm homecoming country song", 171.9),
    MusicTrack(
        "radio_country_wildflower_mile", "Wildflower Mile", "Hopeful springtime country song", 138.7
    ),
    MusicTrack(
        "radio_country_dust_and_daylight", "Dust and Daylight", "Gritty outlaw country song", 142.4
    ),
    MusicTrack(
        "radio_country_blue_ridge_morning",
        "Blue Ridge Morning",
        "Upbeat bluegrass instrumental",
        144.0,
    ),
    MusicTrack(
        "radio_country_appalachian_sunrise",
        "Appalachian Sunrise",
        "Bright mountain bluegrass instrumental",
        100.0,
    ),
    MusicTrack(
        "radio_country_steel_string_sunday",
        "Steel String Sunday",
        "Lazy pedal-steel instrumental",
        131.8,
    ),
    MusicTrack(
        "radio_country_dobro_dusk", "Dobro Dusk", "Mellow dobro country instrumental", 217.2
    ),
    MusicTrack(
        "radio_country_mile_marker_moon",
        "Mile Marker Moon",
        "Moonlit homesick country waltz",
        188.0,
    ),
    MusicTrack("radio_country_paper_town", "Paper Town", "Wistful small-town country song", 149.4),
    MusicTrack(
        "radio_country_tailgate_summer",
        "Tailgate Summer",
        "Rowdy lakeside party country song",
        119.4,
    ),
    MusicTrack(
        "radio_country_grandpas_radio",
        "Grandpa's Radio",
        "Tender heirloom-radio country ballad",
        163.0,
    ),
)

CLASSIC_ROCK_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack("radio_rock_open_throttle", "Open Throttle", "Seventies highway rock anthem", 150.0),
    MusicTrack("radio_rock_night_shift", "Night Shift", "Mid-tempo organ-driven rock", 150.0),
    MusicTrack("radio_rock_chrome_horizon", "Chrome Horizon", "Heartland arena rock song", 150.0),
    MusicTrack(
        "radio_rock_thunder_county", "Thunder County", "Storm-charged seventies rock anthem", 174.9
    ),
    MusicTrack(
        "radio_rock_midnight_arcade", "Midnight Arcade", "Neon eighties arena rock song", 168.0
    ),
    MusicTrack(
        "radio_rock_neon_avenue", "Neon Avenue", "Late-night organ-driven rock groove", 157.2
    ),
    MusicTrack("radio_rock_ember_sky", "Ember Sky", "Hopeful heartland rock song", 138.0),
    MusicTrack(
        "radio_rock_glass_highway", "Glass Highway", "Melodic highway rock instrumental", 178.1
    ),
    MusicTrack(
        "radio_rock_mercury_miles", "Mercury Miles", "Soaring lead-guitar rock instrumental", 142.4
    ),
    MusicTrack("radio_rock_switchback", "Switchback", "Funky seventies rock instrumental", 124.7),
    MusicTrack("radio_rock_hairpin", "Hairpin", "Wah-driven mountain rock instrumental", 69.0),
    MusicTrack(
        "radio_rock_wildfire_line", "Wildfire Line", "Driving fire-crew hard rock anthem", 224.4
    ),
    MusicTrack(
        "radio_rock_silver_falcon", "Silver Falcon", "Female-fronted muscle-car rocker", 134.9
    ),
    MusicTrack(
        "radio_rock_last_ferry_home", "Last Ferry Home", "Warm harbor-dusk rock song", 142.3
    ),
    MusicTrack(
        "radio_rock_static_and_stars",
        "Static and Stars",
        "Wide-open night-sky heartland rock",
        197.3,
    ),
)

BLUES_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack("radio_blues_delta_mile", "Delta Mile", "Slow electric delta blues", 150.0),
    MusicTrack(
        "radio_blues_crossroad_coffee", "Crossroad Coffee", "Warm southern soul blues", 150.0
    ),
    MusicTrack("radio_blues_raincheck", "Raincheck", "Slow rained-out electric blues", 222.4),
    MusicTrack(
        "radio_blues_magnolia_porch", "Magnolia Porch", "Warm porch-evening southern soul", 165.8
    ),
    MusicTrack(
        "radio_blues_neon_bourbon", "Neon and Bourbon", "Smoky Chicago bar-band blues", 197.1
    ),
    MusicTrack(
        "radio_blues_freight_yard_moon",
        "Freight Yard Moon",
        "Midnight rail-yard blues instrumental",
        229.9,
    ),
    MusicTrack(
        "radio_blues_midnight_siding",
        "Midnight Siding",
        "Slow-burning night blues instrumental",
        213.8,
    ),
    MusicTrack(
        "radio_blues_slow_train_shuffle",
        "Slow Train Shuffle",
        "Rolling harmonica blues instrumental",
        216.2,
    ),
    MusicTrack(
        "radio_blues_boxcar_stroll", "Boxcar Stroll", "Easy boxcar harmonica instrumental", 183.1
    ),
    MusicTrack(
        "radio_blues_grits_and_gasoline",
        "Grits and Gasoline",
        "Greasy roadside blues rocker",
        115.0,
    ),
    MusicTrack(
        "radio_blues_paycheck_friday", "Paycheck Friday", "Swinging horn-section jump blues", 136.6
    ),
    MusicTrack("radio_blues_levee_moon", "Levee Moon", "Smoky riverside delta soul", 166.6),
)

NIGHT_JAZZ_TRACK = MusicTrack(
    "radio_night_low_beams", "Low Beams", "Late-night instrumental jazz", 180.0
)

# Vocal ballads exclusive to the Night Line station playlist. They stay out of
# NIGHT_DRIVE_TRACKS so the Roadhouse night rotation remains instrumental.
NIGHT_LINE_VOCAL_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack("radio_night_last_diner", "Last Diner Open", "Quiet late-night diner ballad", 158.7),
    MusicTrack(
        "radio_night_third_shift_waltz",
        "Third Shift Waltz",
        "Gentle waltz for night workers",
        109.2,
    ),
)

# Radio host segments, spoken between songs on the built-in stations.
# ElevenLabs TTS clips, generated by tools/generate_radio.py.
ROADHOUSE_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(f"host_roadhouse_{i:02d}", f"Roadhouse host break {i}", "FFR host segment", dur)
    for i, dur in enumerate((6.5, 5.0, 5.8, 5.6, 5.8, 6.1), start=1)
)

NIGHTLINE_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(f"host_nightline_{i:02d}", f"Night Line host break {i}", "FFN host segment", dur)
    for i, dur in enumerate((4.5, 6.2, 4.1, 5.5, 5.9, 5.1), start=1)
)

STATION_PLAYLISTS: dict[str, tuple[MusicTrack, ...]] = {
    "country": COUNTRY_TRACKS,
    "classic_rock": CLASSIC_ROCK_TRACKS,
    "blues": BLUES_TRACKS,
    "night": NIGHT_DRIVE_TRACKS + (NIGHT_JAZZ_TRACK,) + NIGHT_LINE_VOCAL_TRACKS,
}

STATION_HOST_SEGMENTS: dict[str, tuple[MusicTrack, ...]] = {
    "roadhouse": ROADHOUSE_HOST_SEGMENTS,
    "nightline": NIGHTLINE_HOST_SEGMENTS,
}

# Songs played between host breaks on stations that have a host.
RADIO_TRACKS_PER_HOST_BREAK = 2


ALL_MUSIC_TRACKS: tuple[MusicTrack, ...] = (
    MENU_TRACKS
    + MENU_ROTATION_TRACKS
    + (MENU_NIGHT_TRACK,)
    + DAY_DRIVE_TRACKS
    + NIGHT_DRIVE_TRACKS
    + COUNTRY_TRACKS
    + CLASSIC_ROCK_TRACKS
    + BLUES_TRACKS
    + (NIGHT_JAZZ_TRACK,)
    + NIGHT_LINE_VOCAL_TRACKS
)

# Spoken host breaks are deliberately short, so they live outside the music
# catalog but share the duration lookup for rotation timing.
ALL_HOST_SEGMENTS: tuple[MusicTrack, ...] = ROADHOUSE_HOST_SEGMENTS + NIGHTLINE_HOST_SEGMENTS

_TRACKS_BY_KEY = {track.key: track for track in ALL_MUSIC_TRACKS + ALL_HOST_SEGMENTS}


def _profile_is_night(profile) -> bool:
    """True when the loaded career's clock currently reads night.

    Reads the absolute career clock, not the current city's local time: menu
    music is chosen before the world data (and with it the city's time zone)
    is loaded, and a bed picked up to three hours off local dusk is cosmetic.
    """
    if profile is None:
        return False
    hour = (getattr(profile, "game_hours", 0.0) or 0.0) % 24.0
    return is_night(hour)


def select_menu_music(profile) -> str:
    """Choose a menu bed: the night theme after dark, else the milestone bed."""
    if _profile_is_night(profile):
        return MENU_NIGHT_TRACK.key
    return MENU_TRACKS[_menu_milestone_index(profile)].key


def _menu_milestone_index(profile) -> int:
    if profile is None:
        return 0
    career = profile.career
    level = career.level
    deliveries = career.deliveries
    miles = career.total_miles
    if hasattr(profile, "visible_owned_trucks"):
        owned = set(profile.visible_owned_trucks())
        truck = profile.active_truck_key()
    else:
        owned = set(getattr(profile, "owned_trucks", ()))
        truck = getattr(profile, "truck", "rig")
    if level >= 9 or deliveries >= 40 or miles >= 20_000:
        return 5
    if level >= 7 or miles >= 10_000:
        return 4
    if level >= 5 or len(owned) >= 2:
        return 3
    if level >= 3 or miles >= 2_500:
        return 2
    if level >= 2 or deliveries >= 3 or truck != "rig":
        return 1
    return 0


def select_menu_music_sequence(profile) -> tuple[str, ...]:
    """Menu playlist: the night theme leads after dark, else the milestone bed.

    The milestone beds still rotate in after the night theme, so a career loaded
    at night opens on the quiet night bed and keeps its usual variety.
    """
    primary_index = _menu_milestone_index(profile)
    unlocked_count = max(2, primary_index + 1)
    options = MENU_TRACKS[:unlocked_count] + MENU_ROTATION_TRACKS
    milestone_primary = MENU_TRACKS[primary_index].key
    if _profile_is_night(profile):
        primary = MENU_NIGHT_TRACK.key
        pool = options
    else:
        primary = milestone_primary
        pool = tuple(track for track in options if track.key != milestone_primary)
    career = getattr(profile, "career", None)
    seed_key = "|".join(
        (
            str(getattr(profile, "name", "")),
            str(getattr(profile, "current_city", "")),
            str(getattr(career, "deliveries", 0)),
            str(int(getattr(career, "total_miles", 0))),
            primary,
        )
    )
    rest = sorted(
        pool,
        key=lambda track: zlib.crc32(f"{seed_key}|{track.key}".encode()),
    )
    return (primary, *(track.key for track in rest))


def _route_key(route) -> str:
    pieces = [
        ",".join(getattr(route, "cities", ()) or ()),
        ",".join(getattr(route, "highways", ()) or ()),
        str(getattr(route, "terrain_summary", "")),
    ]
    return "|".join(pieces)


def select_drive_music_sequence(
    route,
    trip_seed: int,
    hour: float,
    weather_kind=None,
) -> tuple[str, ...]:
    """Return a stable, deterministic day or night driving playlist."""
    options = NIGHT_DRIVE_TRACKS if is_night(hour) else DAY_DRIVE_TRACKS
    weather = getattr(weather_kind, "name", str(weather_kind or ""))
    seed_key = f"{trip_seed}|{weather}|{_route_key(route)}"
    ordered = sorted(
        options,
        key=lambda track: zlib.crc32(f"{seed_key}|{track.key}".encode()),
    )
    return tuple(track.key for track in ordered)


def select_drive_music(route, trip_seed: int, hour: float, weather_kind=None) -> str:
    """Choose a stable day/night music bed for a trip context."""
    return select_drive_music_sequence(route, trip_seed, hour, weather_kind)[0]


def music_track_duration_s(track: str) -> float:
    """Best-known duration for slow playlist rotation."""
    info = _TRACKS_BY_KEY.get(track)
    return info.duration_s if info is not None else 60.0


def select_station_playlist(playlist: str, seed_key: str) -> tuple[str, ...]:
    """A stable shuffled track order for one station on one trip."""
    pool = STATION_PLAYLISTS.get(playlist, ())
    ordered = sorted(
        pool,
        key=lambda track: zlib.crc32(f"{seed_key}|{track.key}".encode()),
    )
    return tuple(track.key for track in ordered)


def select_host_segments(host: str, seed_key: str) -> tuple[str, ...]:
    """A stable shuffled host-break order for one station on one trip."""
    pool = STATION_HOST_SEGMENTS.get(host, ())
    ordered = sorted(
        pool,
        key=lambda track: zlib.crc32(f"{seed_key}|{track.key}".encode()),
    )
    return tuple(track.key for track in ordered)
