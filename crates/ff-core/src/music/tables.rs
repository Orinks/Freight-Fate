//! The music catalog tables: every track, host break and pool the
//! selectors in `music` draw from. Split from `music.rs` so the logic
//! file stays readable; the names are re-exported from `music`.

use once_cell::sync::Lazy;

use super::MusicTrack;

/// `(key, title, description, duration_s)` -- the literal tables below.
type Row = (&'static str, &'static str, &'static str, f64);

fn tracks(rows: &[Row]) -> Vec<MusicTrack> {
    rows.iter()
        .map(|(key, title, description, duration_s)| {
            MusicTrack::new(key, title, description, *duration_s)
        })
        .collect()
}

pub static MENU_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[
        (
            "menu_theme",
            "Headlights West",
            "Warm Americana for new careers",
            128.4,
        ),
        (
            "menu_first_rig",
            "Keys To The Rig",
            "Easy country-rock milestone bed",
            143.2,
        ),
        (
            "menu_regional_carrier",
            "Regional Lines",
            "Confident heartland rock bed",
            133.7,
        ),
        (
            "menu_fleet_owner",
            "Yard Lights",
            "Steady fleet-owner menu bed",
            94.6,
        ),
        (
            "menu_coast_to_coast",
            "Coast To Coast Ledger",
            "Broad road-trip menu bed",
            104.7,
        ),
        (
            "menu_legendary_haul",
            "Million Mile Morning",
            "Late-career Americana bed",
            117.5,
        ),
        (
            "menu_progress",
            "Progress for Progress's Sake",
            "Seasoned late-career country bed",
            212.3,
        ),
    ])
});

pub static MENU_ROTATION_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[(
        "menu_urban_roll",
        "Urban Roll",
        "Easy city-groove menu bed",
        114.5,
    )])
});

pub static DAY_DRIVE_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[
        (
            "open_road",
            "Open Road",
            "Easy mid-tempo groove for long hauls",
            131.6,
        ),
        (
            "drive_desert_two_lane",
            "Desert Two-Lane",
            "Dry, spacious daytime road bed",
            234.7,
        ),
        (
            "drive_mountain_grade",
            "Mountain Grade",
            "Measured climb-focused road bed",
            154.8,
        ),
        (
            "drive_rain_day_cruise",
            "Rain-Day Cruise",
            "Gentle rainy daytime drive bed",
            173.0,
        ),
        (
            "drive_urban_roll",
            "Urban Roll",
            "Light city traffic drive bed",
            144.8,
        ),
        (
            "drive_dawn_push",
            "Dawn Push",
            "Soft early-morning drive bed",
            114.0,
        ),
        (
            "drive_high_plains_wind",
            "High Plains Wind",
            "Warm high-plains Americana bed",
            183.2,
        ),
        (
            "drive_open_sky_run",
            "Open Sky Run",
            "Breezy open-sky Americana bed",
            176.0,
        ),
        (
            "drive_golden_hour_freeway",
            "Golden Hour Freeway",
            "Golden-hour heartland drive bed",
            184.8,
        ),
        (
            "drive_amber_lanes",
            "Amber Lanes",
            "Warm sunset freeway drive bed",
            129.3,
        ),
        (
            "drive_river_valley_roll",
            "River Valley Roll",
            "Rolling folk-rock valley bed",
            164.1,
        ),
        (
            "drive_green_mile_bend",
            "Green Mile Bend",
            "Easy fingerpicked river-road bed",
            140.9,
        ),
        (
            "drive_county_line_cruise",
            "County Line Cruise",
            "Laid-back twangy cruising bed",
            158.6,
        ),
        (
            "drive_two_lane_daydream",
            "Two-Lane Daydream",
            "Relaxed two-lane country-rock bed",
            127.1,
        ),
        (
            "drive_chrome_creek",
            "Chrome Creek",
            "Breezy slide-guitar roots bed",
            122.6,
        ),
        (
            "drive_silver_current",
            "Silver Current",
            "Sparkling slide-guitar morning bed",
            149.0,
        ),
        (
            "drive_canoe_trail",
            "Canoe Trail",
            "Easy pastoral fingerpicked bed",
            205.0,
        ),
        (
            "drive_gunflint",
            "On the Gunflint",
            "Wide northwoods Americana bed",
            240.0,
        ),
        (
            "drive_little_boat_trip",
            "A Little Boat Trip I Took Once",
            "Lazy riverside country bed",
            212.1,
        ),
        (
            "drive_dancing_firelight",
            "Dancing Firelight",
            "Warm campfire country-folk bed",
            237.5,
        ),
        (
            "drive_always_around",
            "Always Around When You Need Me",
            "Steady companionable country bed",
            201.9,
        ),
    ])
});

pub static NIGHT_DRIVE_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[
        (
            "night_haul",
            "Night Haul",
            "Slow ambient pads for night driving",
            204.76,
        ),
        (
            "night_midnight_interstate",
            "Midnight Interstate",
            "Low night highway bed",
            208.4,
        ),
        (
            "night_neon_truck_stop",
            "Neon Truck Stop",
            "Soft truck-stop approach bed",
            153.6,
        ),
        (
            "night_rainy_miles",
            "Rainy Night Miles",
            "Sparse rainy night bed",
            222.4,
        ),
        (
            "night_lonely_plains",
            "Lonely Plains",
            "Open nighttime plains bed",
            239.9,
        ),
        (
            "night_mountain_pass",
            "Mountain Night Pass",
            "Quiet mountain night bed",
            158.4,
        ),
        (
            "night_small_hours",
            "Small Hours",
            "Slow piano ballad for late-night hauls",
            159.6,
        ),
        (
            "night_quiet_mile",
            "Quiet Mile",
            "Calm electric-piano night bed",
            194.6,
        ),
        (
            "night_soft_shoulder",
            "Soft Shoulder",
            "Soft ambient night-highway bed",
            188.0,
        ),
        (
            "night_starlight_grade",
            "Starlight Grade",
            "Gentle piano mountain-night bed",
            227.4,
        ),
        (
            "night_high_beam_hush",
            "High Beam Hush",
            "Hushed strings-and-piano night bed",
            172.3,
        ),
        (
            "night_under_starlight",
            "Under the Starlight",
            "Open-sky nighttime country bed",
            165.7,
        ),
        (
            "night_slightly_darker",
            "Gettin Ever So Slightly Darker Tonight",
            "Moody dusk-into-night country bed",
            174.9,
        ),
        (
            "night_stars_said_love",
            "Why the Stars Said I Love You That Night",
            "Tender starlit country waltz bed",
            163.8,
        ),
        (
            "night_her_real_words",
            "Her Real Words to Me That Night",
            "Slow confessional night ballad bed",
            242.5,
        ),
        (
            "night_on_my_mind",
            "When You Were on My Mind",
            "Wistful late-night country bed",
            211.9,
        ),
        (
            "night_call_me",
            "Call Me When You Get This",
            "Quiet waiting-by-the-phone night bed",
            187.0,
        ),
        (
            "night_maroon_scarf",
            "Maroon Coloured Scarf",
            "Soft keepsake night ballad bed",
            222.3,
        ),
        (
            "night_train_knew",
            "When We Took That Train I Knew It Was It",
            "Rolling nighttime train-memory bed",
            273.9,
        ),
    ])
});

/// Played at the menu (and the title screen of a loaded career) when the career
/// clock reads night, in place of the daytime milestone bed.
pub static MENU_NIGHT_TRACK: Lazy<MusicTrack> = Lazy::new(|| {
    MusicTrack::new(
        "menu_theme_night",
        "Midnight Keys",
        "Quiet piano ballad for night menus",
        169.9,
    )
});

// Format pools for the fictional regional radio stations. The first three per
// pool are ElevenLabs-composed (tools/generate_radio.py); the 2026-07 batch is
// Suno-composed via the Zero CLI.
pub static COUNTRY_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[
        (
            "radio_country_backroads",
            "Backroads Sunrise",
            "Outlaw country trucking song",
            150.0,
        ),
        (
            "radio_country_two_lane",
            "Two-Lane Towns",
            "Easy classic country song",
            150.0,
        ),
        (
            "radio_country_diesel_heart",
            "Diesel Heart",
            "Upbeat country rock song",
            150.0,
        ),
        (
            "radio_country_county_fair",
            "County Fair",
            "Upbeat county-fair country song",
            164.3,
        ),
        (
            "radio_country_porch_light",
            "Porch Light",
            "Warm homecoming country song",
            171.9,
        ),
        (
            "radio_country_wildflower_mile",
            "Wildflower Mile",
            "Hopeful springtime country song",
            138.7,
        ),
        (
            "radio_country_dust_and_daylight",
            "Dust and Daylight",
            "Gritty outlaw country song",
            142.4,
        ),
        (
            "radio_country_blue_ridge_morning",
            "Blue Ridge Morning",
            "Upbeat bluegrass instrumental",
            144.0,
        ),
        (
            "radio_country_appalachian_sunrise",
            "Appalachian Sunrise",
            "Bright mountain bluegrass instrumental",
            100.0,
        ),
        (
            "radio_country_steel_string_sunday",
            "Steel String Sunday",
            "Lazy pedal-steel instrumental",
            131.8,
        ),
        (
            "radio_country_dobro_dusk",
            "Dobro Dusk",
            "Mellow dobro country instrumental",
            217.2,
        ),
        (
            "radio_country_mile_marker_moon",
            "Mile Marker Moon",
            "Moonlit homesick country waltz",
            188.0,
        ),
        (
            "radio_country_paper_town",
            "Paper Town",
            "Wistful small-town country song",
            149.4,
        ),
        (
            "radio_country_tailgate_summer",
            "Tailgate Summer",
            "Rowdy lakeside party country song",
            119.4,
        ),
        (
            "radio_country_grandpas_radio",
            "Grandpa's Radio",
            "Tender heirloom-radio country ballad",
            163.0,
        ),
        (
            "radio_country_dust_on_the_highway",
            "Dust on the Highway",
            "Driving outlaw country-rock instrumental",
            219.6,
        ),
        (
            "radio_country_texico_fill_up",
            "Texico Station Fill Up",
            "Bouncy truck-stop country instrumental",
            176.3,
        ),
        (
            "radio_country_arkansas_load",
            "Crucial Load Needed in Arkansas",
            "Urgent dispatch-run country instrumental",
            195.0,
        ),
        (
            "radio_country_kentucky_rain",
            "Kentucky Rain Called Me Home",
            "Rain-soaked homecoming country instrumental",
            181.0,
        ),
        (
            "radio_country_texian_style",
            "Texian Style",
            "Swaggering Texas country instrumental",
            184.4,
        ),
        (
            "radio_country_tuesday_texas",
            "Texas Country on a Tuesday Evening",
            "Easygoing weeknight Texas country instrumental",
            248.0,
        ),
        (
            "radio_country_fort_worth_thursday",
            "Thursday Night in Fort Worth",
            "Honky-tonk Thursday-night country instrumental",
            221.9,
        ),
        (
            "radio_country_texas_wants_you",
            "Texas Wants You Back, and So Do I",
            "Yearning Texas ballad instrumental",
            248.3,
        ),
        (
            "radio_country_alabama_called",
            "Alabama Called",
            "Southbound homesick country instrumental",
            270.9,
        ),
        (
            "radio_country_carolina_groovin",
            "Carolina Groovin",
            "Funky Carolina country-groove instrumental",
            288.3,
        ),
        (
            "radio_country_over_yonder",
            "Over Yonder",
            "Front-porch country stroll instrumental",
            165.8,
        ),
    ])
});

pub static CLASSIC_ROCK_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[
        (
            "radio_rock_open_throttle",
            "Open Throttle",
            "Seventies highway rock anthem",
            150.0,
        ),
        (
            "radio_rock_night_shift",
            "Night Shift",
            "Mid-tempo organ-driven rock",
            150.0,
        ),
        (
            "radio_rock_chrome_horizon",
            "Chrome Horizon",
            "Heartland arena rock song",
            150.0,
        ),
        (
            "radio_rock_thunder_county",
            "Thunder County",
            "Storm-charged seventies rock anthem",
            174.9,
        ),
        (
            "radio_rock_midnight_arcade",
            "Midnight Arcade",
            "Neon eighties arena rock song",
            168.0,
        ),
        (
            "radio_rock_neon_avenue",
            "Neon Avenue",
            "Late-night organ-driven rock groove",
            157.2,
        ),
        (
            "radio_rock_ember_sky",
            "Ember Sky",
            "Hopeful heartland rock song",
            138.0,
        ),
        (
            "radio_rock_glass_highway",
            "Glass Highway",
            "Melodic highway rock instrumental",
            178.1,
        ),
        (
            "radio_rock_mercury_miles",
            "Mercury Miles",
            "Soaring lead-guitar rock instrumental",
            142.4,
        ),
        (
            "radio_rock_switchback",
            "Switchback",
            "Funky seventies rock instrumental",
            124.7,
        ),
        (
            "radio_rock_hairpin",
            "Hairpin",
            "Wah-driven mountain rock instrumental",
            69.0,
        ),
        (
            "radio_rock_wildfire_line",
            "Wildfire Line",
            "Driving fire-crew hard rock anthem",
            224.4,
        ),
        (
            "radio_rock_silver_falcon",
            "Silver Falcon",
            "Female-fronted muscle-car rocker",
            134.9,
        ),
        (
            "radio_rock_last_ferry_home",
            "Last Ferry Home",
            "Warm harbor-dusk rock song",
            184.4,
        ),
        (
            "radio_rock_static_and_stars",
            "Static and Stars",
            "Wide-open night-sky heartland rock",
            197.3,
        ),
        (
            "radio_rock_greywater_quay",
            "Greywater Quay",
            "Folk-rock tale of a salvaged sailor",
            213.1,
        ),
        (
            "radio_rock_inland_sea",
            "Inland Sea",
            "Heartland rock for the Great Salt Lake",
            141.7,
        ),
    ])
});

pub static BLUES_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[
        (
            "radio_blues_delta_mile",
            "Delta Mile",
            "Slow electric delta blues",
            150.0,
        ),
        (
            "radio_blues_crossroad_coffee",
            "Crossroad Coffee",
            "Warm southern soul blues",
            150.0,
        ),
        (
            "radio_blues_raincheck",
            "Raincheck",
            "Slow rained-out electric blues",
            222.4,
        ),
        (
            "radio_blues_magnolia_porch",
            "Magnolia Porch",
            "Warm porch-evening southern soul",
            165.8,
        ),
        (
            "radio_blues_neon_bourbon",
            "Neon and Bourbon",
            "Smoky Chicago bar-band blues",
            197.1,
        ),
        (
            "radio_blues_freight_yard_moon",
            "Freight Yard Moon",
            "Midnight rail-yard blues instrumental",
            229.9,
        ),
        (
            "radio_blues_midnight_siding",
            "Midnight Siding",
            "Slow-burning night blues instrumental",
            213.8,
        ),
        (
            "radio_blues_slow_train_shuffle",
            "Slow Train Shuffle",
            "Rolling harmonica blues instrumental",
            216.2,
        ),
        (
            "radio_blues_boxcar_stroll",
            "Boxcar Stroll",
            "Easy boxcar harmonica instrumental",
            183.1,
        ),
        (
            "radio_blues_grits_and_gasoline",
            "Grits and Gasoline",
            "Greasy roadside blues rocker",
            115.0,
        ),
        (
            "radio_blues_paycheck_friday",
            "Paycheck Friday",
            "Swinging horn-section jump blues",
            136.6,
        ),
        (
            "radio_blues_levee_moon",
            "Levee Moon",
            "Smoky riverside delta soul",
            166.6,
        ),
    ])
});

// Nashville jazz-crossover instrumentals: the Nashville After Hours station
// pool, the originals batch's second color after straight country.
pub static JAZZ_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[
        (
            "radio_jazz_nashville_jazzicals",
            "More Nashville Jazzicals",
            "Smoky Nashville crossover jazz instrumental",
            280.0,
        ),
        (
            "radio_jazz_nashville_cats",
            "When Some Nashville Cats Got Jazzy",
            "Playful swing-country jazz instrumental",
            231.5,
        ),
        (
            "radio_jazz_eighties_sound",
            "That Nashville Sound in the 80's",
            "Smooth eighties countrypolitan instrumental",
            220.0,
        ),
        (
            "radio_jazz_nineties_sound",
            "That Nashville Sound in the 90's",
            "Polished nineties Nashville-pop instrumental",
            194.5,
        ),
        (
            "radio_jazz_nashville_tonight",
            "Happens in Nashville Tonight",
            "After-hours downtown jazz instrumental",
            195.8,
        ),
        (
            "radio_jazz_caring_touch",
            "A Caring Touch",
            "Gentle late-evening ballad instrumental",
            173.8,
        ),
        (
            "radio_jazz_penny_thoughts",
            "Penny for Your Thoughts",
            "Thoughtful brushed-drums jazz instrumental",
            195.0,
        ),
    ])
});

// Oldies, gospel, tejano, and synthwave station pools: the 2026-08 second
// originals batch. Titles/descriptions match tools/radio_content_pools.py
// SONG_PLAN exactly for the entries that made it to disk -- the ElevenLabs
// quota ran out mid-batch, so each pool only carries what actually generated
// (oldies finished in full; gospel, tejano, and synthwave are partial and
// resume from the plan's remaining entries in a later batch).
pub static OLDIES_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[
        (
            "radio_oldies_jukebox_in_the_corner",
            "Jukebox in the Corner",
            "Bright doo-wop number about a truck-stop jukebox",
            168.0,
        ),
        (
            "radio_oldies_milkshake_moon",
            "Milkshake Moon",
            "Slow-dance doo-wop ballad in six-eight",
            186.0,
        ),
        (
            "radio_oldies_chrome_fins",
            "Chrome Fins",
            "Surf-rock instrumental for tailfin dreams",
            157.0,
        ),
        (
            "radio_oldies_hop_in_the_hardtop",
            "Hop in the Hardtop",
            "Jump-blues rock and roll dance number",
            160.0,
        ),
        (
            "radio_oldies_soda_shop_sweetheart",
            "Soda Shop Sweetheart",
            "Girl-group pop with wall-of-sound sparkle",
            172.1,
        ),
        (
            "radio_oldies_drive_in_picture_show",
            "Drive-In Picture Show",
            "Twist-beat rocker about drive-in movie nights",
            153.0,
        ),
        (
            "radio_oldies_transistor_summer",
            "Transistor Summer",
            "Sunny beach-pop tune about a pocket radio",
            170.0,
        ),
        (
            "radio_oldies_sock_hop_saturday",
            "Sock Hop Saturday",
            "Piano-pounding rock and roll dance-floor filler",
            155.1,
        ),
    ])
});

pub static GOSPEL_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[
        (
            "radio_gospel_wide_is_the_river",
            "Wide Is the River",
            "Full-choir southern gospel about crossing over",
            214.0,
        ),
        (
            "radio_gospel_set_my_burden_down",
            "Set My Burden Down",
            "Slow-building spiritual of release and rest",
            226.1,
        ),
        (
            "radio_gospel_morning_will_come",
            "Morning Will Come",
            "Gentle piano ballad of hope before dawn",
            198.1,
        ),
    ])
});

pub static TEJANO_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[
        (
            "radio_tejano_camino_de_flores",
            "Camino de Flores",
            "Flower-strewn cumbia for the road home",
            181.9,
        ),
        (
            "radio_tejano_mi_troquita",
            "Mi Troquita",
            "Affectionate conjunto polka about a beloved truck",
            165.0,
        ),
        (
            "radio_tejano_luna_de_laredo",
            "Luna de Laredo",
            "Romantic border-moon ranchera ballad",
            216.0,
        ),
    ])
});

pub static SYNTHWAVE_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[(
        "radio_synthwave_afterglow_avenue",
        "Afterglow Avenue",
        "Dreamwave with soft vocals for the last mile",
        224.0,
    )])
});

pub static NIGHT_JAZZ_TRACK: Lazy<MusicTrack> = Lazy::new(|| {
    MusicTrack::new(
        "radio_night_low_beams",
        "Low Beams",
        "Late-night instrumental jazz",
        180.0,
    )
});

// Vocal ballads exclusive to the Night Line station playlist. They stay out of
// NIGHT_DRIVE_TRACKS so the Roadhouse night rotation remains instrumental.
pub static NIGHT_LINE_VOCAL_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    tracks(&[
        (
            "radio_night_last_diner",
            "Last Diner Open",
            "Quiet late-night diner ballad",
            158.7,
        ),
        (
            "radio_night_third_shift_waltz",
            "Third Shift Waltz",
            "Gentle waltz for night workers",
            109.2,
        ),
    ])
});
