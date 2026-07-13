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
)

NIGHT_DRIVE_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack("night_haul", "Night Haul", "Slow ambient pads for night driving", 204.76),
    MusicTrack("night_midnight_interstate", "Midnight Interstate", "Low night highway bed", 208.4),
    MusicTrack("night_neon_truck_stop", "Neon Truck Stop", "Soft truck-stop approach bed", 153.6),
    MusicTrack("night_rainy_miles", "Rainy Night Miles", "Sparse rainy night bed", 222.4),
    MusicTrack("night_lonely_plains", "Lonely Plains", "Open nighttime plains bed", 239.9),
    MusicTrack("night_mountain_pass", "Mountain Night Pass", "Quiet mountain night bed", 158.4),
    MusicTrack("night_small_hours", "Small Hours", "Slow piano ballad for late-night hauls", 159.6),
)

# Played at the menu (and the title screen of a loaded career) when the career
# clock reads night, in place of the daytime milestone bed.
MENU_NIGHT_TRACK = MusicTrack(
    "menu_theme_night", "Midnight Keys", "Quiet piano ballad for night menus", 169.9
)


ALL_MUSIC_TRACKS: tuple[MusicTrack, ...] = (
    MENU_TRACKS + MENU_ROTATION_TRACKS + (MENU_NIGHT_TRACK,) + DAY_DRIVE_TRACKS + NIGHT_DRIVE_TRACKS
)

_TRACKS_BY_KEY = {track.key: track for track in ALL_MUSIC_TRACKS}


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
