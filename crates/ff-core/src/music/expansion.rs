//! Owner-selected September 2026 radio additions, timed from the encoded masters.
use super::MusicTrack;
use once_cell::sync::Lazy;

pub(super) fn tracks(pool: &str) -> Vec<MusicTrack> {
    let rows: &[(&str, &str, &str, f64)] = match pool {
        "country" => &[
            (
                "radio_country_split_rail",
                "Split Rail",
                "Fence-line country tune about staying the course",
                183.526,
            ),
            (
                "radio_country_county_fair_lights",
                "County Fair Lights",
                "Up-tempo song of a first kiss at the county fair",
                175.726,
            ),
            (
                "radio_country_porch_swing_promise",
                "Porch Swing Promise",
                "Front-porch love duet in three-four time",
                271.207,
            ),
            (
                "radio_country_harvest_moon_over_the_barn",
                "Harvest Moon Over the Barn",
                "Wistful waltz about the farm passing to the next generation",
                206.367,
            ),
            (
                "radio_country_cold_coffee_courage",
                "Cold Coffee Courage",
                "Wry country anthem for the last hundred miles",
                169.966,
            ),
            (
                "radio_country_last_bale_of_summer",
                "Last Bale of Summer",
                "Harvest-end ballad of fields going quiet",
                212.047,
            ),
            (
                "radio_country_red_dirt_ring",
                "Red Dirt Ring",
                "Stomping red-dirt band instrumental",
                165.887,
            ),
            (
                "radio_country_high_line_home",
                "High Line Home",
                "Northern-plains song of the long way back",
                194.406,
            ),
        ],
        "classic_rock" => &[
            (
                "radio_rock_paper_crown",
                "Paper Crown",
                "Anthem for the small-town king who never left",
                202.367,
            ),
            (
                "radio_rock_bar_band_saturday",
                "Bar Band Saturday",
                "Grinning blues-rocker about the cover band that never quit",
                177.566,
            ),
            (
                "radio_rock_lights_over_superior",
                "Lights Over Superior",
                "Instrumental for northern lights over the big lake",
                225.806,
            ),
            (
                "radio_rock_last_payphone_in_town",
                "Last Payphone in Town",
                "Horn-stabbed funk-rock about a call that never came",
                173.607,
            ),
            (
                "radio_rock_vulture_pass",
                "Vulture Pass",
                "Menacing desert hard-rock instrumental",
                209.526,
            ),
            (
                "radio_rock_magnetic_west",
                "Magnetic West",
                "Wanderlust rocker pulled toward the sunset",
                190.767,
            ),
            (
                "radio_rock_river_rising",
                "River Rising",
                "Boogie about a town sandbagging through a spring flood",
                292.366,
            ),
            (
                "radio_rock_furnace_wind",
                "Furnace Wind",
                "Heat-wave rocker about a love that will not cool",
                213.167,
            ),
        ],
        "blues" => &[
            (
                "radio_blues_eleven_bridges",
                "Eleven Bridges",
                "Counting crossings on a heavy-hearted run",
                218.126,
            ),
            (
                "radio_blues_fish_fry_friday",
                "Fish Fry Friday",
                "Greasy jump-blues floor shaker for the church fish fry",
                161.566,
            ),
            (
                "radio_blues_back_porch_darling",
                "Back Porch Darling",
                "Soul-blues serenade on a summer back porch",
                203.607,
            ),
            (
                "radio_blues_leaky_roof",
                "Leaky Roof Blues",
                "Rain-streaked slow blues about a landlord who never shows",
                223.607,
            ),
            (
                "radio_blues_catfish_county",
                "Catfish County",
                "Swamp-groove instrumental with harmonica lead",
                185.607,
            ),
            (
                "radio_blues_low_water_crossing",
                "Low Water Crossing",
                "Texas blues shuffle about risky crossings",
                177.526,
            ),
            (
                "radio_blues_night_shift_queen",
                "Night Shift Queen",
                "Horn-driven soul tribute to a night-shift hero",
                191.927,
            ),
            (
                "radio_blues_red_lights_and_regrets",
                "Red Lights and Regrets",
                "Minor-key blues of long stops and old choices",
                229.526,
            ),
        ],
        "night_line" => &[(
            "radio_night_dashboard_glow",
            "Dashboard Glow",
            "Hushed confession lit by instrument lights",
            203.966,
        )],
        _ => &[],
    };
    rows.iter()
        .map(|(key, title, description, duration)| {
            MusicTrack::new(key, title, description, *duration)
        })
        .collect()
}

// Vocal ballads exclusive to the Night Line station playlist. They stay out of
// NIGHT_DRIVE_TRACKS so the Roadhouse night rotation remains instrumental.
pub static NIGHT_LINE_VOCAL_TRACKS: Lazy<Vec<MusicTrack>> = Lazy::new(|| {
    super::tables::tracks(&[
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
        (
            "radio_night_paper_cup_moon",
            "Paper Cup Moon",
            "Quiet ballad of vending-machine coffee at midnight",
            196.1,
        ),
        (
            "radio_night_idle_hearts",
            "Idle Hearts",
            "Slow duet for two trucks idling side by side",
            218.1,
        ),
    ])
    .into_iter()
    .chain(tracks("night_line"))
    .collect()
});

#[cfg(test)]
mod tests {
    use crate::music::{
        music_track_duration_s, station_playlist, ALL_MUSIC_TRACKS, DAY_DRIVE_TRACKS,
        MENU_DAY_ROTATION_TRACKS, MENU_NIGHT_ROTATION_TRACKS, NIGHT_DRIVE_TRACKS,
    };

    #[test]
    fn selected_september_songs_reach_their_station_pools_only() {
        let manifest: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../docs/radio-september-2026.json"
        )))
        .unwrap();
        let songs = manifest["tracks"].as_array().unwrap();
        assert_eq!(songs.len(), 25);
        for song in songs {
            let key = song["key"].as_str().unwrap();
            let pool = match song["pool"].as_str().unwrap() {
                "night_line" => "night",
                other => other,
            };
            for station in ["country", "classic_rock", "blues", "jazz", "night"] {
                assert_eq!(
                    station_playlist(station).iter().any(|t| t.key == key),
                    station == pool,
                    "{key} routed incorrectly to {station}"
                );
            }
            assert_eq!(ALL_MUSIC_TRACKS.iter().filter(|t| t.key == key).count(), 1);
            assert_eq!(
                music_track_duration_s(key),
                song["duration_s"].as_f64().unwrap()
            );
            // The September batch was generated for the radio, so none of it
            // should have leaked into the drive or menu beds -- except the one
            // track the owner asked for in the menus, which keeps its station
            // slot as well and is named here so the promotion is deliberate.
            let borrowed_by_the_menu = key == "radio_rock_lights_over_superior";
            assert_eq!(
                DAY_DRIVE_TRACKS
                    .iter()
                    .chain(NIGHT_DRIVE_TRACKS.iter())
                    .chain(MENU_DAY_ROTATION_TRACKS.iter())
                    .chain(MENU_NIGHT_ROTATION_TRACKS.iter())
                    .any(|t| t.key == key),
                borrowed_by_the_menu,
                "{key} is in a drive or menu pool it was not meant for"
            );
        }
    }
}
