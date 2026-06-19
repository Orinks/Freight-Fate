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


MENU_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack("menu_theme", "Headlights West", "Warm Americana for new careers"),
    MusicTrack("menu_first_rig", "Keys To The Rig", "Easy country-rock milestone bed"),
    MusicTrack("menu_regional_carrier", "Regional Lines", "Confident heartland rock bed"),
    MusicTrack("menu_fleet_owner", "Yard Lights", "Steady fleet-owner menu bed"),
    MusicTrack("menu_coast_to_coast", "Coast To Coast Ledger", "Broad road-trip menu bed"),
    MusicTrack("menu_legendary_haul", "Million Mile Morning", "Late-career Americana bed"),
)

DAY_DRIVE_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack("open_road", "Open Road", "Easy mid-tempo groove for long hauls"),
    MusicTrack("drive_desert_two_lane", "Desert Two-Lane", "Dry, spacious daytime road bed"),
    MusicTrack("drive_mountain_grade", "Mountain Grade", "Measured climb-focused road bed"),
    MusicTrack("drive_rain_day_cruise", "Rain-Day Cruise", "Gentle rainy daytime drive bed"),
    MusicTrack("drive_urban_roll", "Urban Roll", "Light city traffic drive bed"),
    MusicTrack("drive_dawn_push", "Dawn Push", "Soft early-morning drive bed"),
)

NIGHT_DRIVE_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack("night_haul", "Night Haul", "Slow ambient pads for night driving"),
    MusicTrack("night_midnight_interstate", "Midnight Interstate", "Low night highway bed"),
    MusicTrack("night_neon_truck_stop", "Neon Truck Stop", "Soft truck-stop approach bed"),
    MusicTrack("night_rainy_miles", "Rainy Night Miles", "Sparse rainy night bed"),
    MusicTrack("night_lonely_plains", "Lonely Plains", "Open nighttime plains bed"),
    MusicTrack("night_mountain_pass", "Mountain Night Pass", "Quiet mountain night bed"),
)


ALL_MUSIC_TRACKS: tuple[MusicTrack, ...] = (
    MENU_TRACKS + DAY_DRIVE_TRACKS + NIGHT_DRIVE_TRACKS
)


def select_menu_music(profile) -> str:
    """Choose a menu bed from the player's broad career milestone."""
    if profile is None:
        return "menu_theme"
    career = profile.career
    level = career.level
    deliveries = career.deliveries
    miles = career.total_miles
    owned = set(getattr(profile, "owned_trucks", ()))
    truck = getattr(profile, "truck", "rig")
    if level >= 9 or deliveries >= 40 or miles >= 20_000:
        return "menu_legendary_haul"
    if level >= 7 or miles >= 10_000:
        return "menu_coast_to_coast"
    if level >= 5 or len(owned) >= 2:
        return "menu_fleet_owner"
    if level >= 3 or miles >= 2_500:
        return "menu_regional_carrier"
    if level >= 2 or deliveries >= 3 or truck != "rig":
        return "menu_first_rig"
    return "menu_theme"


def _route_key(route) -> str:
    pieces = [
        ",".join(getattr(route, "cities", ()) or ()),
        ",".join(getattr(route, "highways", ()) or ()),
        str(getattr(route, "terrain_summary", "")),
    ]
    return "|".join(pieces)


def _pick(options: tuple[MusicTrack, ...], seed_key: str) -> str:
    index = zlib.crc32(seed_key.encode("utf-8")) % len(options)
    return options[index].key


def select_drive_music(route, trip_seed: int, hour: float, weather_kind=None) -> str:
    """Choose a stable day/night music bed for a trip context."""
    options = NIGHT_DRIVE_TRACKS if is_night(hour) else DAY_DRIVE_TRACKS
    weather = getattr(weather_kind, "name", str(weather_kind or ""))
    seed_key = f"{trip_seed}|{int(hour) // 3}|{weather}|{_route_key(route)}"
    return _pick(options, seed_key)
