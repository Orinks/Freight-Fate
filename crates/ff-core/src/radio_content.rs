//! Per-station radio identity content: IDs, ads, and break planning.
//!
//! Tables are filled by the generation pass (tools/generate_radio.py); until
//! then they are empty and every consumer degrades to plain host breaks. Keys
//! follow the asset contract: host_<station>_NN, id_<station>_NN, ad_<slug>.
//!
//! `STATION_IDS` is keyed by catalog station id (the `id` field in
//! `data/radio_catalog.json`), not by host voice: an ID speaks a call sign,
//! and several stations can share one host.
//!
//! Port of `freight_fate/radio_content.py`. The Python tests swapped the
//! module tables out under `monkeypatch`; here the same planning runs over a
//! [`ContentTables`] value, and the module-level functions consult the
//! shipped [`ContentTables::shipped`] set.

use once_cell::sync::Lazy;

use crate::music::{self, crc32, MusicTrack};

/// `(station id, jingle 1 key/title/duration, jingle 2 ..., legal ID ...)`.
type IdRow = (
    &'static str,
    [(&'static str, &'static str, &'static str, f64); 3],
);

// Keyed by catalog station id (not the host voice key -- an ID speaks a
// call sign, and several stations can share a host). Two produced jingles
// (_01/_02, sung) plus a spoken legal ID (_03) per station, matching
// tools/radio_content_plan.py STATIONS' jingle_prompts and id_lines.
const STATION_ID_ROWS: &[IdRow] = &[
    (
        "route_playlist",
        [
            (
                "id_roadhouse_01",
                "Freight Fate Roadhouse jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_roadhouse_02",
                "Freight Fate Roadhouse jingle 2",
                "Sung station jingle",
                12.1,
            ),
            (
                "id_roadhouse_03",
                "Freight Fate Roadhouse legal ID",
                "Spoken call-sign ID",
                4.4,
            ),
        ],
    ),
    (
        "ff-night-line",
        [
            (
                "id_nightline_01",
                "Freight Fate Night Line jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_nightline_02",
                "Freight Fate Night Line jingle 2",
                "Sung station jingle",
                12.0,
            ),
            (
                "id_nightline_03",
                "Freight Fate Night Line legal ID",
                "Spoken call-sign ID",
                5.2,
            ),
        ],
    ),
    (
        "krwl-dallas",
        [
            (
                "id_rawhide_01",
                "The Rawhide 98.1 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_rawhide_02",
                "The Rawhide 98.1 jingle 2",
                "Sung station jingle",
                12.1,
            ),
            (
                "id_rawhide_03",
                "The Rawhide 98.1 legal ID",
                "Spoken call-sign ID",
                4.1,
            ),
        ],
    ),
    (
        "whwy-nashville",
        [
            (
                "id_bigwheel_01",
                "Big Wheel Country 104.5 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_bigwheel_02",
                "Big Wheel Country 104.5 jingle 2",
                "Sung station jingle",
                12.0,
            ),
            (
                "id_bigwheel_03",
                "Big Wheel Country 104.5 legal ID",
                "Spoken call-sign ID",
                4.2,
            ),
        ],
    ),
    (
        "kpln-kansas-city",
        [
            (
                "id_prairieline_01",
                "Prairie Line 95.7 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_prairieline_02",
                "Prairie Line 95.7 jingle 2",
                "Sung station jingle",
                12.0,
            ),
            (
                "id_prairieline_03",
                "Prairie Line 95.7 legal ID",
                "Spoken call-sign ID",
                3.6,
            ),
        ],
    ),
    (
        "kbsk-billings",
        [
            (
                "id_bigsky_01",
                "Big Sky Country 99.3 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_bigsky_02",
                "Big Sky Country 99.3 jingle 2",
                "Sung station jingle",
                12.0,
            ),
            (
                "id_bigsky_03",
                "Big Sky Country 99.3 legal ID",
                "Spoken call-sign ID",
                5.9,
            ),
        ],
    ),
    (
        "wgrx-chicago",
        [
            (
                "id_grind_01",
                "The Grind 97.9 jingle 1",
                "Sung station jingle",
                10.1,
            ),
            (
                "id_grind_02",
                "The Grind 97.9 jingle 2",
                "Sung station jingle",
                12.0,
            ),
            (
                "id_grind_03",
                "The Grind 97.9 legal ID",
                "Spoken call-sign ID",
                3.4,
            ),
        ],
    ),
    (
        "kdrt-phoenix",
        [
            (
                "id_desertrock_01",
                "Desert Rock 101.5 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_desertrock_02",
                "Desert Rock 101.5 jingle 2",
                "Sung station jingle",
                12.0,
            ),
            (
                "id_desertrock_03",
                "Desert Rock 101.5 legal ID",
                "Spoken call-sign ID",
                4.2,
            ),
        ],
    ),
    (
        "kchm-los-angeles",
        [
            (
                "id_chrome_01",
                "Chrome 106.3 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_chrome_02",
                "Chrome 106.3 jingle 2",
                "Sung station jingle",
                12.0,
            ),
            (
                "id_chrome_03",
                "Chrome 106.3 legal ID",
                "Spoken call-sign ID",
                4.8,
            ),
        ],
    ),
    (
        "krdg-denver",
        [
            (
                "id_ridge_01",
                "The Ridge 103.7 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_ridge_02",
                "The Ridge 103.7 jingle 2",
                "Sung station jingle",
                13.0,
            ),
            (
                "id_ridge_03",
                "The Ridge 103.7 legal ID",
                "Spoken call-sign ID",
                3.8,
            ),
        ],
    ),
    (
        "ksnd-seattle",
        [
            (
                "id_sound_01",
                "The Sound 102.1 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_sound_02",
                "The Sound 102.1 jingle 2",
                "Sung station jingle",
                12.1,
            ),
            (
                "id_sound_03",
                "The Sound 102.1 legal ID",
                "Spoken call-sign ID",
                2.9,
            ),
        ],
    ),
    (
        "wdlt-memphis",
        [
            (
                "id_delta_01",
                "The Delta 94.3 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_delta_02",
                "The Delta 94.3 jingle 2",
                "Sung station jingle",
                12.0,
            ),
            (
                "id_delta_03",
                "The Delta 94.3 legal ID",
                "Spoken call-sign ID",
                5.7,
            ),
        ],
    ),
    (
        "wbyu-new-orleans",
        [
            (
                "id_bayou_01",
                "Bayou Soul 100.9 jingle 1",
                "Sung station jingle",
                10.1,
            ),
            (
                "id_bayou_02",
                "Bayou Soul 100.9 jingle 2",
                "Sung station jingle",
                12.0,
            ),
            (
                "id_bayou_03",
                "Bayou Soul 100.9 legal ID",
                "Spoken call-sign ID",
                3.1,
            ),
        ],
    ),
    (
        "wsol-atlanta",
        [
            (
                "id_southernsoul_01",
                "Southern Soul 96.5 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_southernsoul_02",
                "Southern Soul 96.5 jingle 2",
                "Sung station jingle",
                12.1,
            ),
            (
                "id_southernsoul_03",
                "Southern Soul 96.5 legal ID",
                "Spoken call-sign ID",
                4.8,
            ),
        ],
    ),
    (
        "wnah-nashville",
        [
            (
                "id_afterhours_01",
                "Nashville After Hours 92.9 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_afterhours_02",
                "Nashville After Hours 92.9 jingle 2",
                "Sung station jingle",
                12.1,
            ),
            (
                "id_afterhours_03",
                "Nashville After Hours 92.9 legal ID",
                "Spoken call-sign ID",
                5.2,
            ),
        ],
    ),
    (
        "kgol-oklahoma-city",
        [
            (
                "id_cruisingold_01",
                "Cruisin' Gold 105.9 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_cruisingold_02",
                "Cruisin' Gold 105.9 jingle 2",
                "Sung station jingle",
                12.1,
            ),
            (
                "id_cruisingold_03",
                "Cruisin' Gold 105.9 legal ID",
                "Spoken call-sign ID",
                3.9,
            ),
        ],
    ),
    (
        "wglr-birmingham",
        [
            (
                "id_gloryroad_01",
                "Glory Road 91.5 jingle 1",
                "Sung station jingle",
                10.1,
            ),
            (
                "id_gloryroad_02",
                "Glory Road 91.5 jingle 2",
                "Sung station jingle",
                12.0,
            ),
            (
                "id_gloryroad_03",
                "Glory Road 91.5 legal ID",
                "Spoken call-sign ID",
                5.7,
            ),
        ],
    ),
    (
        "ktjo-san-antonio",
        [
            (
                "id_purotejano_01",
                "Puro Tejano 107.1 jingle 1",
                "Sung station jingle",
                10.1,
            ),
            (
                "id_purotejano_02",
                "Puro Tejano 107.1 jingle 2",
                "Sung station jingle",
                12.1,
            ),
            (
                "id_purotejano_03",
                "Puro Tejano 107.1 legal ID",
                "Spoken call-sign ID",
                3.8,
            ),
        ],
    ),
    (
        "kndr-las-vegas",
        [
            (
                "id_neondrive_01",
                "Neon Drive 88.5 jingle 1",
                "Sung station jingle",
                10.0,
            ),
            (
                "id_neondrive_02",
                "Neon Drive 88.5 jingle 2",
                "Sung station jingle",
                12.0,
            ),
            (
                "id_neondrive_03",
                "Neon Drive 88.5 legal ID",
                "Spoken call-sign ID",
                3.4,
            ),
        ],
    ),
];

// The shared ad rotation, tools/radio_content_ads.py AD_PLAN. Ad voices are
// disjoint from every station's casting, so a break slot never puts a
// station host behind a commercial.
const AD_ROWS: &[(&str, &str, f64)] = &[
    (
        "ad_red_hawk_travel_centers",
        "Red Hawk Travel Centers",
        25.6,
    ),
    ("ad_dellas_blue_plate", "Della's Blue Plate Diner", 24.2),
    ("ad_ironline_tire", "Ironline Tire and Retread", 23.3),
    ("ad_bearclaw_diesel", "Bearclaw Diesel Treatment", 27.4),
    ("ad_meridian_freight_hiring", "Meridian Freight Lines", 25.3),
    ("ad_wagon_wheel_inn", "Wagon Wheel Motor Inn", 24.0),
    ("ad_loadlasso_app", "LoadLasso", 21.2),
    ("ad_black_kettle_coffee", "Black Kettle Coffee", 18.9),
    (
        "ad_granite_shield_insurance",
        "Granite Shield Insurance",
        22.2,
    ),
    ("ad_silver_spray_wash", "Silver Spray Truck Wash", 22.9),
    (
        "ad_silver_stack_electronics",
        "Silver Stack Chrome and Electronics",
        25.0,
    ),
    ("ad_weighahead_app", "WeighAhead", 24.5),
    ("ad_roadforge_boots", "Roadforge Boots", 23.8),
    ("ad_skyline_relay", "Skyline Relay", 23.4),
    ("ad_milepost_ministries", "Milepost Ministries", 26.1),
    ("ad_quietcab_headsets", "QuietCab Headsets", 20.4),
    ("ad_truelane_navigation", "TrueLane Navigation", 21.5),
    ("ad_smokestack_jerky", "Smokestack Jerky Company", 24.4),
];

// Which STATION_PLAYLISTS pools each spot may air on, from
// tools/radio_content_ads.py AD_PLAN.formats ("route" never appears: the
// Roadhouse draws no ads).
const AD_FORMAT_ROWS: &[(&str, &[&str])] = &[
    (
        "ad_red_hawk_travel_centers",
        &[
            "country",
            "classic_rock",
            "blues",
            "oldies",
            "tejano",
            "jazz",
        ],
    ),
    (
        "ad_dellas_blue_plate",
        &["country", "oldies", "gospel", "blues"],
    ),
    (
        "ad_ironline_tire",
        &["country", "classic_rock", "blues", "tejano", "jazz"],
    ),
    ("ad_bearclaw_diesel", &["country", "classic_rock", "blues"]),
    (
        "ad_meridian_freight_hiring",
        &[
            "country",
            "classic_rock",
            "gospel",
            "tejano",
            "blues",
            "jazz",
        ],
    ),
    (
        "ad_wagon_wheel_inn",
        &["country", "blues", "oldies", "night"],
    ),
    (
        "ad_loadlasso_app",
        &["country", "classic_rock", "tejano", "synthwave"],
    ),
    (
        "ad_black_kettle_coffee",
        &["night", "jazz", "blues", "oldies", "country"],
    ),
    (
        "ad_granite_shield_insurance",
        &["country", "classic_rock", "blues", "gospel", "jazz"],
    ),
    (
        "ad_silver_spray_wash",
        &["country", "classic_rock", "tejano", "oldies"],
    ),
    (
        "ad_silver_stack_electronics",
        &["country", "classic_rock", "blues", "oldies", "synthwave"],
    ),
    (
        "ad_weighahead_app",
        &["classic_rock", "country", "synthwave"],
    ),
    (
        "ad_roadforge_boots",
        &["country", "classic_rock", "blues", "gospel", "tejano"],
    ),
    (
        "ad_skyline_relay",
        &["classic_rock", "synthwave", "night", "country", "jazz"],
    ),
    (
        "ad_milepost_ministries",
        &["gospel", "country", "blues", "night"],
    ),
    (
        "ad_quietcab_headsets",
        &["classic_rock", "synthwave", "country", "jazz", "night"],
    ),
    (
        "ad_truelane_navigation",
        &[
            "country",
            "classic_rock",
            "tejano",
            "oldies",
            "synthwave",
            "jazz",
        ],
    ),
    (
        "ad_smokestack_jerky",
        &[
            "country",
            "classic_rock",
            "blues",
            "oldies",
            "tejano",
            "jazz",
            "night",
        ],
    ),
];

/// One break after every 2 songs; break content cycles this pattern. An
/// ad never runs without an ID chasing it back into music, so ads are
/// never adjacent and an ID lands at least once per four breaks.
pub const BREAK_PATTERN: &[&str] = &["host", "id", "host", "ad_id"];

/// The identity-content tables the break planner reads. The shipped set is
/// [`ContentTables::shipped`]; tests build small ones.
#[derive(Debug, Clone, Default)]
pub struct ContentTables {
    /// Station IDs by catalog station id.
    pub station_ids: Vec<(String, Vec<MusicTrack>)>,
    /// The shared ad rotation.
    pub ad_spots: Vec<MusicTrack>,
    /// Which playlist pools each ad key may air on.
    pub ad_format_tags: Vec<(String, Vec<String>)>,
    /// Host pools by host voice key (`music.STATION_HOST_SEGMENTS`).
    pub host_segments: Vec<(String, Vec<MusicTrack>)>,
}

static SHIPPED: Lazy<ContentTables> = Lazy::new(|| ContentTables {
    station_ids: STATION_ID_ROWS
        .iter()
        .map(|(station, rows)| {
            let pool = rows
                .iter()
                .map(|(key, title, description, duration)| MusicTrack {
                    key: key.to_string(),
                    title: title.to_string(),
                    description: description.to_string(),
                    duration_s: *duration,
                })
                .collect();
            (station.to_string(), pool)
        })
        .collect(),
    ad_spots: AD_ROWS
        .iter()
        .map(|(key, title, duration)| MusicTrack {
            key: key.to_string(),
            title: title.to_string(),
            description: "Radio ad spot".to_string(),
            duration_s: *duration,
        })
        .collect(),
    ad_format_tags: AD_FORMAT_ROWS
        .iter()
        .map(|(key, tags)| {
            (
                key.to_string(),
                tags.iter().map(|t| t.to_string()).collect(),
            )
        })
        .collect(),
    host_segments: music::STATION_HOST_SEGMENTS.clone(),
});

impl ContentTables {
    /// The tables the game ships with.
    pub fn shipped() -> &'static ContentTables {
        &SHIPPED
    }

    fn lookup<'a>(table: &'a [(String, Vec<MusicTrack>)], key: &str) -> &'a [MusicTrack] {
        table
            .iter()
            .find(|(k, _)| k == key)
            .map(|(_, pool)| pool.as_slice())
            .unwrap_or(&[])
    }

    /// Duration of an ID/ad key, falling back to the music catalog.
    ///
    /// The pools are small (under a hundred entries all told) and can be
    /// populated after import, so this scans them live rather than caching an
    /// index that would go stale and hand back the unknown-key fallback --
    /// which the playback loop would hear as real dead air.
    pub fn content_duration_s(&self, key: &str) -> f64 {
        for (_, pool) in &self.station_ids {
            for track in pool {
                if track.key == key {
                    return track.duration_s;
                }
            }
        }
        for track in &self.ad_spots {
            if track.key == key {
                return track.duration_s;
            }
        }
        music::music_track_duration_s(key)
    }

    pub fn station_ads(&self, playlist: &str) -> Vec<MusicTrack> {
        self.ad_spots
            .iter()
            .filter(|spot| {
                self.ad_format_tags
                    .iter()
                    .find(|(key, _)| *key == spot.key)
                    .map(|(_, tags)| tags.iter().any(|t| t == playlist))
                    .unwrap_or(false)
            })
            .cloned()
            .collect()
    }

    /// Asset keys for one break slot. Empty when the station has no voice.
    ///
    /// Slot kinds cycle BREAK_PATTERN; a kind whose pool is empty falls back
    /// to a host break so the cadence the player learned never stutters.
    ///
    /// Each pool advances on its OWN count, not on the global break index: a
    /// host is heard twice per pattern cycle, an ID up to twice (its own slot
    /// plus the tag chasing an ad), an ad once. Indexing every pool by the
    /// global break number would sample them at stride 2 or 4 and leave most
    /// of a pool permanently unreachable.
    pub fn plan_break(
        &self,
        station_id: &str,
        host: &str,
        playlist: &str,
        seed_key: &str,
        break_index: usize,
    ) -> Vec<String> {
        let hosts = Self::lookup(&self.host_segments, host);
        if hosts.is_empty() {
            return Vec::new();
        }
        let cycle = break_index / BREAK_PATTERN.len();
        let pattern_pos = break_index % BREAK_PATTERN.len();
        let kind = BREAK_PATTERN[pattern_pos];
        let host_pos = 2 * cycle + usize::from(pattern_pos == 2);
        let id_pos = 2 * cycle + usize::from(kind == "ad_id");
        let ids = Self::lookup(&self.station_ids, station_id);
        let ads = self.station_ads(playlist);
        if kind == "id" && !ids.is_empty() {
            return vec![pick(ids, &format!("{seed_key}|id"), id_pos)];
        }
        if kind == "ad_id" && !ads.is_empty() && !ids.is_empty() {
            return vec![
                pick(&ads, &format!("{seed_key}|ad"), cycle),
                pick(ids, &format!("{seed_key}|tag"), id_pos),
            ];
        }
        vec![pick(hosts, &format!("{seed_key}|host"), host_pos)]
    }
}

fn pick(pool: &[MusicTrack], seed_key: &str, index: usize) -> String {
    let mut ordered: Vec<&MusicTrack> = pool.iter().collect();
    ordered.sort_by_key(|t| crc32(format!("{seed_key}|{}", t.key).as_bytes()));
    ordered[index % ordered.len()].key.clone()
}

/// The shipped `STATION_IDS` pool for a catalog station id.
pub fn station_ids(station_id: &str) -> &'static [MusicTrack] {
    ContentTables::lookup(&SHIPPED.station_ids, station_id)
}

/// The shipped `AD_SPOTS`.
pub fn ad_spots() -> &'static [MusicTrack] {
    &SHIPPED.ad_spots
}

/// The shipped `AD_FORMAT_TAGS` for an ad key.
pub fn ad_format_tags(ad_key: &str) -> &'static [String] {
    SHIPPED
        .ad_format_tags
        .iter()
        .find(|(key, _)| key == ad_key)
        .map(|(_, tags)| tags.as_slice())
        .unwrap_or(&[])
}

/// Duration of an ID/ad key, falling back to the music catalog (shipped tables).
pub fn content_duration_s(key: &str) -> f64 {
    SHIPPED.content_duration_s(key)
}

/// The shipped ads that may air on `playlist`.
pub fn station_ads(playlist: &str) -> Vec<MusicTrack> {
    SHIPPED.station_ads(playlist)
}

/// [`ContentTables::plan_break`] over the shipped tables.
pub fn plan_break(
    station_id: &str,
    host: &str,
    playlist: &str,
    seed_key: &str,
    break_index: usize,
) -> Vec<String> {
    SHIPPED.plan_break(station_id, host, playlist, seed_key, break_index)
}

#[cfg(test)]
mod tests {
    //! The pure half of `tests/test_radio_breaks.py`; the driving-state break
    //! queue tests (`break_driving`) belong to the game crate.
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn test_content_duration_falls_back_to_music_catalog() {
        // host_roadhouse_01 lives in music's host tables today
        assert!(content_duration_s("host_roadhouse_01") > 0.0);
        assert_eq!(content_duration_s("no_such_key"), 60.0);
    }

    fn track(key: &str, title: &str, duration: f64) -> MusicTrack {
        MusicTrack {
            key: key.into(),
            title: title.into(),
            description: "test".into(),
            duration_s: duration,
        }
    }

    #[test]
    fn test_station_ads_filters_by_format_tag() {
        let tables = ContentTables {
            ad_spots: vec![
                track("ad_test_tires", "Tire ad", 22.0),
                track("ad_test_diner", "Diner ad", 25.0),
            ],
            ad_format_tags: vec![
                ("ad_test_tires".into(), vec!["country".into()]),
                (
                    "ad_test_diner".into(),
                    vec!["country".into(), "blues".into()],
                ),
            ],
            ..Default::default()
        };
        let blues: Vec<String> = tables
            .station_ads("blues")
            .into_iter()
            .map(|t| t.key)
            .collect();
        assert_eq!(blues, vec!["ad_test_diner"]);
        assert_eq!(tables.station_ads("country").len(), 2);
        assert!(tables.station_ads("jazz").is_empty());
    }

    const STATION: &str = "brk-fixture";
    const HOST_COUNT: usize = 8;
    const ID_COUNT: usize = 3;
    const AD_COUNT: usize = 4;

    fn patched_pools() -> ContentTables {
        let hosts: Vec<MusicTrack> = (1..=HOST_COUNT)
            .map(|i| track(&format!("host_x_{i:02}"), &format!("h{i}"), 5.0))
            .collect();
        let ids: Vec<MusicTrack> = (1..=ID_COUNT)
            .map(|i| track(&format!("id_x_{i:02}"), &format!("i{i}"), 10.0))
            .collect();
        let ads: Vec<MusicTrack> = (1..=AD_COUNT)
            .map(|i| track(&format!("ad_y_{i:02}"), &format!("a{i}"), 25.0))
            .collect();
        ContentTables {
            host_segments: vec![("x".into(), hosts)],
            station_ids: vec![(STATION.into(), ids)],
            ad_format_tags: ads
                .iter()
                .map(|t| (t.key.clone(), vec!["country".to_string()]))
                .collect(),
            ad_spots: ads,
        }
    }

    fn breaks(tables: &ContentTables, count: usize) -> Vec<Vec<String>> {
        (0..count)
            .map(|i| tables.plan_break(STATION, "x", "country", "seed", i))
            .collect()
    }

    #[test]
    fn test_break_pattern_cycles_and_is_deterministic() {
        let tables = patched_pools();
        let kinds = breaks(&tables, 8);
        for (i, planned) in kinds.iter().enumerate() {
            assert_eq!(
                *planned,
                tables.plan_break(STATION, "x", "country", "seed", i)
            );
        }
        // pattern: host, id, host, ad_id, repeated
        for pos in [0, 2, 4, 6] {
            assert!(kinds[pos][0].starts_with("host_"), "{pos}");
        }
        for pos in [1, 5] {
            assert!(kinds[pos][0].starts_with("id_"), "{pos}");
        }
        for pos in [3, 7] {
            assert!(
                kinds[pos][0].starts_with("ad_") && kinds[pos][1].starts_with("id_"),
                "{pos}"
            );
        }
    }

    #[test]
    fn test_every_pool_entry_is_reachable_across_breaks() {
        // No segment is stranded: each pool advances on its own count.
        //
        // Host slots land twice per four-break cycle, ID slots up to twice (own
        // slot plus the tag chasing an ad), ads once -- so four cycles is enough
        // for the 8/3/4 fixture pools to be heard out in full.
        let tables = patched_pools();
        let planned = breaks(&tables, 4 * BREAK_PATTERN.len());
        let keys: Vec<&String> = planned.iter().flatten().collect();
        let count = |prefix: &str| {
            keys.iter()
                .filter(|k| k.starts_with(prefix))
                .collect::<HashSet<_>>()
                .len()
        };
        assert_eq!(count("host_"), HOST_COUNT);
        assert_eq!(count("id_"), ID_COUNT);
        assert_eq!(count("ad_"), AD_COUNT);
    }

    #[test]
    fn test_break_slots_degrade_when_pools_missing() {
        let mut tables = patched_pools();
        tables.station_ids.clear();
        tables.ad_spots.clear();
        // id and ad slots fall back to a host break; still never empty for a
        // station that has a host
        let planned = breaks(&tables, 4 * BREAK_PATTERN.len());
        assert!(planned
            .iter()
            .all(|elems| elems.len() == 1 && elems[0].starts_with("host_")));
        // a degraded station still cycles its whole host pool
        let distinct: HashSet<&String> = planned.iter().map(|e| &e[0]).collect();
        assert_eq!(distinct.len(), HOST_COUNT);
        // and a station with no host at all gets no break
        assert!(tables
            .plan_break(STATION, "", "country", "seed", 0)
            .is_empty());
    }

    #[test]
    fn test_ids_are_keyed_by_station_not_host() {
        // Two stations sharing a host still speak their own call signs.
        let mut tables = patched_pools();
        tables
            .station_ids
            .push(("brk-other".into(), vec![track("id_other_01", "o1", 10.0)]));
        assert_eq!(
            tables.plan_break("brk-other", "x", "country", "seed", 1),
            vec!["id_other_01".to_string()]
        );
        assert!(tables.plan_break("nope", "x", "country", "seed", 1)[0].starts_with("host_"));
    }

    #[test]
    fn test_station_content_tables_resolve() {
        // The on-disk half of the Python test (every clip in the pack) stays
        // with the asset sweep; the table invariants are pinned here.
        let shipped = ContentTables::shipped();
        let mut keys: Vec<&str> = shipped
            .station_ids
            .iter()
            .flat_map(|(_, pool)| pool.iter().map(|t| t.key.as_str()))
            .collect();
        keys.extend(shipped.ad_spots.iter().map(|t| t.key.as_str()));
        let unique: HashSet<&str> = keys.iter().cloned().collect();
        assert_eq!(keys.len(), unique.len());
        assert!(keys.iter().all(|k| content_duration_s(k) > 0.0));
        let spot_keys: HashSet<&str> = shipped.ad_spots.iter().map(|t| t.key.as_str()).collect();
        for (key, tags) in &shipped.ad_format_tags {
            assert!(spot_keys.contains(key.as_str()));
            assert!(
                tags.iter()
                    .all(|tag| !music::station_playlist(tag).is_empty()),
                "{key}"
            );
        }
        // Every registered host segment must resolve to its own duration; a pool
        // listed in STATION_HOST_SEGMENTS but missing from ALL_HOST_SEGMENTS
        // would fall through to the 60-second unknown-key guess, which the
        // playback loop hears as dead air.
        for (_, pool) in music::STATION_HOST_SEGMENTS.iter() {
            for segment in pool {
                assert_eq!(
                    content_duration_s(&segment.key),
                    segment.duration_s,
                    "{}",
                    segment.key
                );
            }
        }
        assert_eq!(station_ids("route_playlist").len(), 3);
        assert_eq!(ad_spots().len(), 18);
        assert!(ad_format_tags("ad_wagon_wheel_inn").contains(&"night".to_string()));
        assert!(
            station_ads("route").is_empty(),
            "the Roadhouse draws no ads"
        );
    }
}
