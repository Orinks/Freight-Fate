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
    MusicTrack(
        "menu_progress",
        "Progress for Progress's Sake",
        "Seasoned late-career country bed",
        212.3,
    ),
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
    MusicTrack("drive_canoe_trail", "Canoe Trail", "Easy pastoral fingerpicked bed", 205.0),
    MusicTrack("drive_gunflint", "On the Gunflint", "Wide northwoods Americana bed", 240.0),
    MusicTrack(
        "drive_little_boat_trip",
        "A Little Boat Trip I Took Once",
        "Lazy riverside country bed",
        212.1,
    ),
    MusicTrack(
        "drive_dancing_firelight", "Dancing Firelight", "Warm campfire country-folk bed", 237.5
    ),
    MusicTrack(
        "drive_always_around",
        "Always Around When You Need Me",
        "Steady companionable country bed",
        201.9,
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
    MusicTrack(
        "night_under_starlight", "Under the Starlight", "Open-sky nighttime country bed", 165.7
    ),
    MusicTrack(
        "night_slightly_darker",
        "Gettin Ever So Slightly Darker Tonight",
        "Moody dusk-into-night country bed",
        174.9,
    ),
    MusicTrack(
        "night_stars_said_love",
        "Why the Stars Said I Love You That Night",
        "Tender starlit country waltz bed",
        163.8,
    ),
    MusicTrack(
        "night_her_real_words",
        "Her Real Words to Me That Night",
        "Slow confessional night ballad bed",
        242.5,
    ),
    MusicTrack(
        "night_on_my_mind",
        "When You Were on My Mind",
        "Wistful late-night country bed",
        211.9,
    ),
    MusicTrack(
        "night_call_me",
        "Call Me When You Get This",
        "Quiet waiting-by-the-phone night bed",
        187.0,
    ),
    MusicTrack(
        "night_maroon_scarf", "Maroon Coloured Scarf", "Soft keepsake night ballad bed", 222.3
    ),
    MusicTrack(
        "night_train_knew",
        "When We Took That Train I Knew It Was It",
        "Rolling nighttime train-memory bed",
        273.9,
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
    MusicTrack(
        "radio_country_dust_on_the_highway",
        "Dust on the Highway",
        "Driving outlaw country-rock instrumental",
        219.6,
    ),
    MusicTrack(
        "radio_country_texico_fill_up",
        "Texico Station Fill Up",
        "Bouncy truck-stop country instrumental",
        176.3,
    ),
    MusicTrack(
        "radio_country_arkansas_load",
        "Crucial Load Needed in Arkansas",
        "Urgent dispatch-run country instrumental",
        195.0,
    ),
    MusicTrack(
        "radio_country_kentucky_rain",
        "Kentucky Rain Called Me Home",
        "Rain-soaked homecoming country instrumental",
        181.0,
    ),
    MusicTrack(
        "radio_country_texian_style",
        "Texian Style",
        "Swaggering Texas country instrumental",
        184.4,
    ),
    MusicTrack(
        "radio_country_tuesday_texas",
        "Texas Country on a Tuesday Evening",
        "Easygoing weeknight Texas country instrumental",
        248.0,
    ),
    MusicTrack(
        "radio_country_fort_worth_thursday",
        "Thursday Night in Fort Worth",
        "Honky-tonk Thursday-night country instrumental",
        221.9,
    ),
    MusicTrack(
        "radio_country_texas_wants_you",
        "Texas Wants You Back, and So Do I",
        "Yearning Texas ballad instrumental",
        248.3,
    ),
    MusicTrack(
        "radio_country_alabama_called",
        "Alabama Called",
        "Southbound homesick country instrumental",
        270.9,
    ),
    MusicTrack(
        "radio_country_carolina_groovin",
        "Carolina Groovin",
        "Funky Carolina country-groove instrumental",
        288.3,
    ),
    MusicTrack(
        "radio_country_over_yonder",
        "Over Yonder",
        "Front-porch country stroll instrumental",
        165.8,
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
        "radio_rock_last_ferry_home", "Last Ferry Home", "Warm harbor-dusk rock song", 184.4
    ),
    MusicTrack(
        "radio_rock_static_and_stars",
        "Static and Stars",
        "Wide-open night-sky heartland rock",
        197.3,
    ),
    MusicTrack(
        "radio_rock_greywater_quay", "Greywater Quay", "Folk-rock tale of a salvaged sailor", 213.1
    ),
    MusicTrack(
        "radio_rock_inland_sea", "Inland Sea", "Heartland rock for the Great Salt Lake", 141.7
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

# Nashville jazz-crossover instrumentals: the Nashville After Hours station
# pool, the originals batch's second color after straight country.
JAZZ_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack(
        "radio_jazz_nashville_jazzicals",
        "More Nashville Jazzicals",
        "Smoky Nashville crossover jazz instrumental",
        280.0,
    ),
    MusicTrack(
        "radio_jazz_nashville_cats",
        "When Some Nashville Cats Got Jazzy",
        "Playful swing-country jazz instrumental",
        231.5,
    ),
    MusicTrack(
        "radio_jazz_eighties_sound",
        "That Nashville Sound in the 80's",
        "Smooth eighties countrypolitan instrumental",
        220.0,
    ),
    MusicTrack(
        "radio_jazz_nineties_sound",
        "That Nashville Sound in the 90's",
        "Polished nineties Nashville-pop instrumental",
        194.5,
    ),
    MusicTrack(
        "radio_jazz_nashville_tonight",
        "Happens in Nashville Tonight",
        "After-hours downtown jazz instrumental",
        195.8,
    ),
    MusicTrack(
        "radio_jazz_caring_touch",
        "A Caring Touch",
        "Gentle late-evening ballad instrumental",
        173.8,
    ),
    MusicTrack(
        "radio_jazz_penny_thoughts",
        "Penny for Your Thoughts",
        "Thoughtful brushed-drums jazz instrumental",
        195.0,
    ),
)

# Oldies, gospel, tejano, and synthwave station pools: the 2026-08 second
# originals batch. Titles/descriptions match tools/radio_content_pools.py
# SONG_PLAN exactly for the entries that made it to disk -- the ElevenLabs
# quota ran out mid-batch, so each pool only carries what actually generated
# (oldies finished in full; gospel, tejano, and synthwave are partial and
# resume from the plan's remaining entries in a later batch).
OLDIES_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack(
        "radio_oldies_jukebox_in_the_corner",
        "Jukebox in the Corner",
        "Bright doo-wop number about a truck-stop jukebox",
        168.0,
    ),
    MusicTrack(
        "radio_oldies_milkshake_moon",
        "Milkshake Moon",
        "Slow-dance doo-wop ballad in six-eight",
        186.0,
    ),
    MusicTrack(
        "radio_oldies_chrome_fins",
        "Chrome Fins",
        "Surf-rock instrumental for tailfin dreams",
        157.0,
    ),
    MusicTrack(
        "radio_oldies_hop_in_the_hardtop",
        "Hop in the Hardtop",
        "Jump-blues rock and roll dance number",
        160.0,
    ),
    MusicTrack(
        "radio_oldies_soda_shop_sweetheart",
        "Soda Shop Sweetheart",
        "Girl-group pop with wall-of-sound sparkle",
        172.1,
    ),
    MusicTrack(
        "radio_oldies_drive_in_picture_show",
        "Drive-In Picture Show",
        "Twist-beat rocker about drive-in movie nights",
        153.0,
    ),
    MusicTrack(
        "radio_oldies_transistor_summer",
        "Transistor Summer",
        "Sunny beach-pop tune about a pocket radio",
        170.0,
    ),
    MusicTrack(
        "radio_oldies_sock_hop_saturday",
        "Sock Hop Saturday",
        "Piano-pounding rock and roll dance-floor filler",
        155.1,
    ),
)

GOSPEL_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack(
        "radio_gospel_wide_is_the_river",
        "Wide Is the River",
        "Full-choir southern gospel about crossing over",
        214.0,
    ),
    MusicTrack(
        "radio_gospel_set_my_burden_down",
        "Set My Burden Down",
        "Slow-building spiritual of release and rest",
        226.1,
    ),
    MusicTrack(
        "radio_gospel_morning_will_come",
        "Morning Will Come",
        "Gentle piano ballad of hope before dawn",
        198.1,
    ),
)

TEJANO_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack(
        "radio_tejano_camino_de_flores",
        "Camino de Flores",
        "Flower-strewn cumbia for the road home",
        181.9,
    ),
    MusicTrack(
        "radio_tejano_mi_troquita",
        "Mi Troquita",
        "Affectionate conjunto polka about a beloved truck",
        165.0,
    ),
    MusicTrack(
        "radio_tejano_luna_de_laredo",
        "Luna de Laredo",
        "Romantic border-moon ranchera ballad",
        216.0,
    ),
)

SYNTHWAVE_TRACKS: tuple[MusicTrack, ...] = (
    MusicTrack(
        "radio_synthwave_afterglow_avenue",
        "Afterglow Avenue",
        "Dreamwave with soft vocals for the last mile",
        224.0,
    ),
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

# Radio instrumentals that double as menu beds. Curated, not the whole
# instrumental catalog: these sit well under menu speech (Glass Highway is the
# one rocker, by request), and the night picks stay behind the night theme so
# the day menu keeps its Americana feel. Vocal songs and host breaks stay on
# the radio -- menus already carry screen-reader speech.
_RADIO_TRACKS_BY_KEY = {
    track.key: track
    for track in COUNTRY_TRACKS + CLASSIC_ROCK_TRACKS + BLUES_TRACKS + (NIGHT_JAZZ_TRACK,)
}

MENU_DAY_ROTATION_TRACKS: tuple[MusicTrack, ...] = tuple(
    _RADIO_TRACKS_BY_KEY[key]
    for key in (
        "radio_country_steel_string_sunday",
        "radio_country_dobro_dusk",
        "radio_rock_glass_highway",
    )
)

MENU_NIGHT_ROTATION_TRACKS: tuple[MusicTrack, ...] = tuple(
    _RADIO_TRACKS_BY_KEY[key]
    for key in (
        "radio_blues_freight_yard_moon",
        "radio_blues_midnight_siding",
        "radio_night_low_beams",
    )
)

# Radio host segments, spoken between songs on the built-in and regional
# stations. ElevenLabs TTS clips, generated by tools/generate_radio.py; 8
# breaks per station (the asset contract in tools/radio_content_plan.py).
ROADHOUSE_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_roadhouse_{i:02d}", f"Freight Fate Roadhouse host break {i}", "FFR host segment", dur
    )
    for i, dur in enumerate((6.7, 4.9, 6.5, 6.4, 6.5, 6.6, 7.8, 7.0), start=1)
)

NIGHTLINE_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_nightline_{i:02d}",
        f"Freight Fate Night Line host break {i}",
        "FFN host segment",
        dur,
    )
    for i, dur in enumerate((6.2, 6.0, 5.4, 5.2, 6.1, 5.9, 4.6, 7.4), start=1)
)

RAWHIDE_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_rawhide_{i:02d}", f"The Rawhide 98.1 host break {i}", "KRWZ host segment", dur
    )
    for i, dur in enumerate((5.1, 4.4, 4.7, 5.2, 4.6, 5.2, 5.3, 4.2), start=1)
)

BIGWHEEL_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_bigwheel_{i:02d}",
        f"Big Wheel Country 104.5 host break {i}",
        "WHWX host segment",
        dur,
    )
    for i, dur in enumerate((5.2, 6.0, 4.6, 4.4, 5.0, 4.5, 2.6, 3.3), start=1)
)

PRAIRIELINE_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_prairieline_{i:02d}", f"Prairie Line 95.7 host break {i}", "KPNL host segment", dur
    )
    for i, dur in enumerate((6.6, 6.2, 5.3, 5.7, 3.6, 4.9, 5.2, 3.9), start=1)
)

BIGSKY_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_bigsky_{i:02d}", f"Big Sky Country 99.3 host break {i}", "KBGK host segment", dur
    )
    for i, dur in enumerate((7.7, 7.9, 6.2, 7.0, 6.3, 5.0, 5.6, 7.4), start=1)
)

GRIND_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(f"host_grind_{i:02d}", f"The Grind 97.9 host break {i}", "WGDX host segment", dur)
    for i, dur in enumerate((5.2, 3.6, 5.7, 5.6, 4.2, 2.6, 6.0, 3.5), start=1)
)

DESERTROCK_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_desertrock_{i:02d}", f"Desert Rock 101.5 host break {i}", "KDRZ host segment", dur
    )
    for i, dur in enumerate((5.9, 5.9, 6.5, 6.1, 5.4, 3.6, 7.0, 3.8), start=1)
)

CHROME_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(f"host_chrome_{i:02d}", f"Chrome 106.3 host break {i}", "KHRZ host segment", dur)
    for i, dur in enumerate((5.8, 4.5, 3.9, 5.1, 4.1, 3.8, 4.3, 3.7), start=1)
)

RIDGE_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(f"host_ridge_{i:02d}", f"The Ridge 103.7 host break {i}", "KRIJ host segment", dur)
    for i, dur in enumerate((5.5, 5.4, 4.4, 5.2, 4.1, 3.9, 3.9, 2.6), start=1)
)

SOUND_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(f"host_sound_{i:02d}", f"The Sound 102.1 host break {i}", "KSDX host segment", dur)
    for i, dur in enumerate((4.6, 4.6, 3.9, 5.7, 4.2, 4.4, 4.6, 3.1), start=1)
)

DELTA_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(f"host_delta_{i:02d}", f"The Delta 94.3 host break {i}", "WDTQ host segment", dur)
    for i, dur in enumerate((7.9, 5.0, 7.8, 6.3, 5.5, 8.1, 6.0, 5.3), start=1)
)

BAYOU_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(f"host_bayou_{i:02d}", f"Bayou Soul 100.9 host break {i}", "WBYK host segment", dur)
    for i, dur in enumerate((4.3, 3.6, 3.2, 4.5, 3.3, 2.6, 3.8, 2.9), start=1)
)

SOUTHERNSOUL_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_southernsoul_{i:02d}", f"Southern Soul 96.5 host break {i}", "WSOZ host segment", dur
    )
    for i, dur in enumerate((7.7, 4.5, 6.3, 9.1, 5.8, 7.9, 4.4, 4.8), start=1)
)

AFTERHOURS_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_afterhours_{i:02d}",
        f"Nashville After Hours 92.9 host break {i}",
        "WNAH host segment",
        dur,
    )
    for i, dur in enumerate((4.5, 5.6, 5.1, 4.1, 4.2, 4.3, 4.2, 3.2), start=1)
)

CRUISINGOLD_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_cruisingold_{i:02d}", f"Cruisin' Gold 105.9 host break {i}", "KGOL host segment", dur
    )
    for i, dur in enumerate((4.9, 5.9, 4.9, 5.3, 4.0, 5.5, 3.6, 2.9), start=1)
)

GLORYROAD_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_gloryroad_{i:02d}", f"Glory Road 91.5 host break {i}", "WGLR host segment", dur
    )
    for i, dur in enumerate((5.2, 4.6, 4.9, 7.3, 4.5, 4.7, 4.9, 3.8), start=1)
)

PUROTEJANO_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_purotejano_{i:02d}", f"Puro Tejano 107.1 host break {i}", "KTJO host segment", dur
    )
    for i, dur in enumerate((5.5, 4.7, 5.0, 7.6, 6.0, 4.8, 4.9, 5.3), start=1)
)

NEONDRIVE_HOST_SEGMENTS: tuple[MusicTrack, ...] = tuple(
    MusicTrack(
        f"host_neondrive_{i:02d}", f"Neon Drive 88.5 host break {i}", "KNDR host segment", dur
    )
    for i, dur in enumerate((4.7, 4.9, 5.2, 5.9, 3.8, 4.7, 4.5, 4.4), start=1)
)

STATION_PLAYLISTS: dict[str, tuple[MusicTrack, ...]] = {
    "country": COUNTRY_TRACKS,
    "classic_rock": CLASSIC_ROCK_TRACKS,
    "blues": BLUES_TRACKS,
    "jazz": JAZZ_TRACKS,
    "night": NIGHT_DRIVE_TRACKS + (NIGHT_JAZZ_TRACK,) + NIGHT_LINE_VOCAL_TRACKS,
    "oldies": OLDIES_TRACKS,
    "gospel": GOSPEL_TRACKS,
    "tejano": TEJANO_TRACKS,
    "synthwave": SYNTHWAVE_TRACKS,
}

STATION_HOST_SEGMENTS: dict[str, tuple[MusicTrack, ...]] = {
    "roadhouse": ROADHOUSE_HOST_SEGMENTS,
    "nightline": NIGHTLINE_HOST_SEGMENTS,
    "rawhide": RAWHIDE_HOST_SEGMENTS,
    "bigwheel": BIGWHEEL_HOST_SEGMENTS,
    "prairieline": PRAIRIELINE_HOST_SEGMENTS,
    "bigsky": BIGSKY_HOST_SEGMENTS,
    "grind": GRIND_HOST_SEGMENTS,
    "desertrock": DESERTROCK_HOST_SEGMENTS,
    "chrome": CHROME_HOST_SEGMENTS,
    "ridge": RIDGE_HOST_SEGMENTS,
    "sound": SOUND_HOST_SEGMENTS,
    "delta": DELTA_HOST_SEGMENTS,
    "bayou": BAYOU_HOST_SEGMENTS,
    "southernsoul": SOUTHERNSOUL_HOST_SEGMENTS,
    "afterhours": AFTERHOURS_HOST_SEGMENTS,
    "cruisingold": CRUISINGOLD_HOST_SEGMENTS,
    "gloryroad": GLORYROAD_HOST_SEGMENTS,
    "purotejano": PUROTEJANO_HOST_SEGMENTS,
    "neondrive": NEONDRIVE_HOST_SEGMENTS,
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
    + JAZZ_TRACKS
    + (NIGHT_JAZZ_TRACK,)
    + NIGHT_LINE_VOCAL_TRACKS
    + OLDIES_TRACKS
    + GOSPEL_TRACKS
    + TEJANO_TRACKS
    + SYNTHWAVE_TRACKS
)

# Spoken host breaks are deliberately short, so they live outside the music
# catalog but share the duration lookup for rotation timing.
ALL_HOST_SEGMENTS: tuple[MusicTrack, ...] = (
    ROADHOUSE_HOST_SEGMENTS
    + NIGHTLINE_HOST_SEGMENTS
    + RAWHIDE_HOST_SEGMENTS
    + BIGWHEEL_HOST_SEGMENTS
    + PRAIRIELINE_HOST_SEGMENTS
    + BIGSKY_HOST_SEGMENTS
    + GRIND_HOST_SEGMENTS
    + DESERTROCK_HOST_SEGMENTS
    + CHROME_HOST_SEGMENTS
    + RIDGE_HOST_SEGMENTS
    + SOUND_HOST_SEGMENTS
    + DELTA_HOST_SEGMENTS
    + BAYOU_HOST_SEGMENTS
    + SOUTHERNSOUL_HOST_SEGMENTS
    + AFTERHOURS_HOST_SEGMENTS
    + CRUISINGOLD_HOST_SEGMENTS
    + GLORYROAD_HOST_SEGMENTS
    + PUROTEJANO_HOST_SEGMENTS
    + NEONDRIVE_HOST_SEGMENTS
)

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
    if level >= 21 or deliveries >= 75 or miles >= 40_000:
        return 6
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
    at night opens on the quiet night bed and keeps its usual variety. A few
    radio instrumentals round out the rotation: mellow day picks behind the
    milestone bed, night blues and jazz behind the night theme.
    """
    primary_index = _menu_milestone_index(profile)
    unlocked_count = max(2, primary_index + 1)
    options = MENU_TRACKS[:unlocked_count] + MENU_ROTATION_TRACKS
    milestone_primary = MENU_TRACKS[primary_index].key
    if _profile_is_night(profile):
        primary = MENU_NIGHT_TRACK.key
        pool = options + MENU_NIGHT_ROTATION_TRACKS
    else:
        primary = milestone_primary
        pool = (
            tuple(track for track in options if track.key != milestone_primary)
            + MENU_DAY_ROTATION_TRACKS
        )
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
