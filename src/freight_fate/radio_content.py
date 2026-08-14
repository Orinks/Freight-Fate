"""Per-station radio identity content: IDs, ads, and break planning.

Tables are filled by the generation pass (tools/generate_radio.py); until
then they are empty and every consumer degrades to plain host breaks. Keys
follow the asset contract: host_<station>_NN, id_<station>_NN, ad_<slug>.

``STATION_IDS`` is keyed by catalog station id (the ``id`` field in
``data/radio_catalog.json``), not by host voice: an ID speaks a call sign,
and several stations can share one host.
"""

from __future__ import annotations

import zlib

from .music import MusicTrack, music_track_duration_s

# Keyed by catalog station id (not the host voice key -- an ID speaks a
# call sign, and several stations can share a host). Two produced jingles
# (_01/_02, sung) plus a spoken legal ID (_03) per station, matching
# tools/radio_content_plan.py STATIONS' jingle_prompts and id_lines.
STATION_IDS: dict[str, tuple[MusicTrack, ...]] = {
    "route_playlist": (
        MusicTrack(
            "id_roadhouse_01", "Freight Fate Roadhouse jingle 1", "Sung station jingle", 10.0
        ),
        MusicTrack(
            "id_roadhouse_02", "Freight Fate Roadhouse jingle 2", "Sung station jingle", 12.1
        ),
        MusicTrack(
            "id_roadhouse_03", "Freight Fate Roadhouse legal ID", "Spoken call-sign ID", 4.4
        ),
    ),
    "ff-night-line": (
        MusicTrack(
            "id_nightline_01", "Freight Fate Night Line jingle 1", "Sung station jingle", 10.0
        ),
        MusicTrack(
            "id_nightline_02", "Freight Fate Night Line jingle 2", "Sung station jingle", 12.0
        ),
        MusicTrack(
            "id_nightline_03", "Freight Fate Night Line legal ID", "Spoken call-sign ID", 5.2
        ),
    ),
    "krwl-dallas": (
        MusicTrack("id_rawhide_01", "The Rawhide 98.1 jingle 1", "Sung station jingle", 10.0),
        MusicTrack("id_rawhide_02", "The Rawhide 98.1 jingle 2", "Sung station jingle", 12.1),
        MusicTrack("id_rawhide_03", "The Rawhide 98.1 legal ID", "Spoken call-sign ID", 4.1),
    ),
    "whwy-nashville": (
        MusicTrack(
            "id_bigwheel_01", "Big Wheel Country 104.5 jingle 1", "Sung station jingle", 10.0
        ),
        MusicTrack(
            "id_bigwheel_02", "Big Wheel Country 104.5 jingle 2", "Sung station jingle", 12.0
        ),
        MusicTrack(
            "id_bigwheel_03", "Big Wheel Country 104.5 legal ID", "Spoken call-sign ID", 4.2
        ),
    ),
    "kpln-kansas-city": (
        MusicTrack("id_prairieline_01", "Prairie Line 95.7 jingle 1", "Sung station jingle", 10.0),
        MusicTrack("id_prairieline_02", "Prairie Line 95.7 jingle 2", "Sung station jingle", 12.0),
        MusicTrack("id_prairieline_03", "Prairie Line 95.7 legal ID", "Spoken call-sign ID", 3.6),
    ),
    "kbsk-billings": (
        MusicTrack("id_bigsky_01", "Big Sky Country 99.3 jingle 1", "Sung station jingle", 10.0),
        MusicTrack("id_bigsky_02", "Big Sky Country 99.3 jingle 2", "Sung station jingle", 12.0),
        MusicTrack("id_bigsky_03", "Big Sky Country 99.3 legal ID", "Spoken call-sign ID", 5.9),
    ),
    "wgrx-chicago": (
        MusicTrack("id_grind_01", "The Grind 97.9 jingle 1", "Sung station jingle", 10.1),
        MusicTrack("id_grind_02", "The Grind 97.9 jingle 2", "Sung station jingle", 12.0),
        MusicTrack("id_grind_03", "The Grind 97.9 legal ID", "Spoken call-sign ID", 3.4),
    ),
    "kdrt-phoenix": (
        MusicTrack("id_desertrock_01", "Desert Rock 101.5 jingle 1", "Sung station jingle", 10.0),
        MusicTrack("id_desertrock_02", "Desert Rock 101.5 jingle 2", "Sung station jingle", 12.0),
        MusicTrack("id_desertrock_03", "Desert Rock 101.5 legal ID", "Spoken call-sign ID", 4.2),
    ),
    "kchm-los-angeles": (
        MusicTrack("id_chrome_01", "Chrome 106.3 jingle 1", "Sung station jingle", 10.0),
        MusicTrack("id_chrome_02", "Chrome 106.3 jingle 2", "Sung station jingle", 12.0),
        MusicTrack("id_chrome_03", "Chrome 106.3 legal ID", "Spoken call-sign ID", 4.8),
    ),
    "krdg-denver": (
        MusicTrack("id_ridge_01", "The Ridge 103.7 jingle 1", "Sung station jingle", 10.0),
        MusicTrack("id_ridge_02", "The Ridge 103.7 jingle 2", "Sung station jingle", 13.0),
        MusicTrack("id_ridge_03", "The Ridge 103.7 legal ID", "Spoken call-sign ID", 3.8),
    ),
    "ksnd-seattle": (
        MusicTrack("id_sound_01", "The Sound 102.1 jingle 1", "Sung station jingle", 10.0),
        MusicTrack("id_sound_02", "The Sound 102.1 jingle 2", "Sung station jingle", 12.1),
        MusicTrack("id_sound_03", "The Sound 102.1 legal ID", "Spoken call-sign ID", 2.9),
    ),
    "wdlt-memphis": (
        MusicTrack("id_delta_01", "The Delta 94.3 jingle 1", "Sung station jingle", 10.0),
        MusicTrack("id_delta_02", "The Delta 94.3 jingle 2", "Sung station jingle", 12.0),
        MusicTrack("id_delta_03", "The Delta 94.3 legal ID", "Spoken call-sign ID", 5.7),
    ),
    "wbyu-new-orleans": (
        MusicTrack("id_bayou_01", "Bayou Soul 100.9 jingle 1", "Sung station jingle", 10.1),
        MusicTrack("id_bayou_02", "Bayou Soul 100.9 jingle 2", "Sung station jingle", 12.0),
        MusicTrack("id_bayou_03", "Bayou Soul 100.9 legal ID", "Spoken call-sign ID", 3.1),
    ),
    "wsol-atlanta": (
        MusicTrack(
            "id_southernsoul_01", "Southern Soul 96.5 jingle 1", "Sung station jingle", 10.0
        ),
        MusicTrack(
            "id_southernsoul_02", "Southern Soul 96.5 jingle 2", "Sung station jingle", 12.1
        ),
        MusicTrack("id_southernsoul_03", "Southern Soul 96.5 legal ID", "Spoken call-sign ID", 4.8),
    ),
    "wnah-nashville": (
        MusicTrack(
            "id_afterhours_01", "Nashville After Hours 92.9 jingle 1", "Sung station jingle", 10.0
        ),
        MusicTrack(
            "id_afterhours_02", "Nashville After Hours 92.9 jingle 2", "Sung station jingle", 12.1
        ),
        MusicTrack(
            "id_afterhours_03", "Nashville After Hours 92.9 legal ID", "Spoken call-sign ID", 5.2
        ),
    ),
    "kgol-oklahoma-city": (
        MusicTrack(
            "id_cruisingold_01", "Cruisin' Gold 105.9 jingle 1", "Sung station jingle", 10.0
        ),
        MusicTrack(
            "id_cruisingold_02", "Cruisin' Gold 105.9 jingle 2", "Sung station jingle", 12.1
        ),
        MusicTrack("id_cruisingold_03", "Cruisin' Gold 105.9 legal ID", "Spoken call-sign ID", 3.9),
    ),
    "wglr-birmingham": (
        MusicTrack("id_gloryroad_01", "Glory Road 91.5 jingle 1", "Sung station jingle", 10.1),
        MusicTrack("id_gloryroad_02", "Glory Road 91.5 jingle 2", "Sung station jingle", 12.0),
        MusicTrack("id_gloryroad_03", "Glory Road 91.5 legal ID", "Spoken call-sign ID", 5.7),
    ),
    "ktjo-san-antonio": (
        MusicTrack("id_purotejano_01", "Puro Tejano 107.1 jingle 1", "Sung station jingle", 10.1),
        MusicTrack("id_purotejano_02", "Puro Tejano 107.1 jingle 2", "Sung station jingle", 12.1),
        MusicTrack("id_purotejano_03", "Puro Tejano 107.1 legal ID", "Spoken call-sign ID", 3.8),
    ),
    "kndr-las-vegas": (
        MusicTrack("id_neondrive_01", "Neon Drive 88.5 jingle 1", "Sung station jingle", 10.0),
        MusicTrack("id_neondrive_02", "Neon Drive 88.5 jingle 2", "Sung station jingle", 12.0),
        MusicTrack("id_neondrive_03", "Neon Drive 88.5 legal ID", "Spoken call-sign ID", 3.4),
    ),
}

# The shared ad rotation, tools/radio_content_ads.py AD_PLAN. Ad voices are
# disjoint from every station's casting, so a break slot never puts a
# station host behind a commercial.
AD_SPOTS: tuple[MusicTrack, ...] = (
    MusicTrack("ad_red_hawk_travel_centers", "Red Hawk Travel Centers", "Radio ad spot", 25.6),
    MusicTrack("ad_dellas_blue_plate", "Della's Blue Plate Diner", "Radio ad spot", 24.2),
    MusicTrack("ad_ironline_tire", "Ironline Tire and Retread", "Radio ad spot", 23.3),
    MusicTrack("ad_bearclaw_diesel", "Bearclaw Diesel Treatment", "Radio ad spot", 27.4),
    MusicTrack("ad_meridian_freight_hiring", "Meridian Freight Lines", "Radio ad spot", 25.3),
    MusicTrack("ad_wagon_wheel_inn", "Wagon Wheel Motor Inn", "Radio ad spot", 24.0),
    MusicTrack("ad_loadlasso_app", "LoadLasso", "Radio ad spot", 21.2),
    MusicTrack("ad_black_kettle_coffee", "Black Kettle Coffee", "Radio ad spot", 18.9),
    MusicTrack("ad_granite_shield_insurance", "Granite Shield Insurance", "Radio ad spot", 22.2),
    MusicTrack("ad_silver_spray_wash", "Silver Spray Truck Wash", "Radio ad spot", 22.9),
    MusicTrack(
        "ad_silver_stack_electronics", "Silver Stack Chrome and Electronics", "Radio ad spot", 25.0
    ),
    MusicTrack("ad_weighahead_app", "WeighAhead", "Radio ad spot", 24.5),
    MusicTrack("ad_roadforge_boots", "Roadforge Boots", "Radio ad spot", 23.8),
    MusicTrack("ad_skyline_relay", "Skyline Relay", "Radio ad spot", 23.4),
    MusicTrack("ad_milepost_ministries", "Milepost Ministries", "Radio ad spot", 26.1),
    MusicTrack("ad_quietcab_headsets", "QuietCab Headsets", "Radio ad spot", 20.4),
    MusicTrack("ad_truelane_navigation", "TrueLane Navigation", "Radio ad spot", 21.5),
    MusicTrack("ad_smokestack_jerky", "Smokestack Jerky Company", "Radio ad spot", 24.4),
)

# Which STATION_PLAYLISTS pools each spot may air on, from
# tools/radio_content_ads.py AD_PLAN.formats ("route" never appears: the
# Roadhouse draws no ads).
AD_FORMAT_TAGS: dict[str, tuple[str, ...]] = {
    "ad_red_hawk_travel_centers": ("country", "classic_rock", "blues", "oldies", "tejano", "jazz"),
    "ad_dellas_blue_plate": ("country", "oldies", "gospel", "blues"),
    "ad_ironline_tire": ("country", "classic_rock", "blues", "tejano", "jazz"),
    "ad_bearclaw_diesel": ("country", "classic_rock", "blues"),
    "ad_meridian_freight_hiring": ("country", "classic_rock", "gospel", "tejano", "blues", "jazz"),
    "ad_wagon_wheel_inn": ("country", "blues", "oldies", "night"),
    "ad_loadlasso_app": ("country", "classic_rock", "tejano", "synthwave"),
    "ad_black_kettle_coffee": ("night", "jazz", "blues", "oldies", "country"),
    "ad_granite_shield_insurance": ("country", "classic_rock", "blues", "gospel", "jazz"),
    "ad_silver_spray_wash": ("country", "classic_rock", "tejano", "oldies"),
    "ad_silver_stack_electronics": ("country", "classic_rock", "blues", "oldies", "synthwave"),
    "ad_weighahead_app": ("classic_rock", "country", "synthwave"),
    "ad_roadforge_boots": ("country", "classic_rock", "blues", "gospel", "tejano"),
    "ad_skyline_relay": ("classic_rock", "synthwave", "night", "country", "jazz"),
    "ad_milepost_ministries": ("gospel", "country", "blues", "night"),
    "ad_quietcab_headsets": ("classic_rock", "synthwave", "country", "jazz", "night"),
    "ad_truelane_navigation": ("country", "classic_rock", "tejano", "oldies", "synthwave", "jazz"),
    "ad_smokestack_jerky": (
        "country",
        "classic_rock",
        "blues",
        "oldies",
        "tejano",
        "jazz",
        "night",
    ),
}

# One break after every 2 songs; break content cycles this pattern. An
# ad never runs without an ID chasing it back into music, so ads are
# never adjacent and an ID lands at least once per four breaks.
BREAK_PATTERN: tuple[str, ...] = ("host", "id", "host", "ad_id")


def content_duration_s(key: str) -> float:
    """Duration of an ID/ad key, falling back to the music catalog.

    The pools are small (under a hundred entries all told) and can be
    populated after import, so this scans them live rather than caching an
    index that would go stale and hand back the unknown-key fallback --
    which the playback loop would hear as real dead air.
    """
    for pool in STATION_IDS.values():
        for track in pool:
            if track.key == key:
                return track.duration_s
    for track in AD_SPOTS:
        if track.key == key:
            return track.duration_s
    return music_track_duration_s(key)


def station_ads(playlist: str) -> tuple[MusicTrack, ...]:
    return tuple(spot for spot in AD_SPOTS if playlist in AD_FORMAT_TAGS.get(spot.key, ()))


def _pick(pool: tuple[MusicTrack, ...], seed_key: str, index: int) -> str:
    ordered = sorted(pool, key=lambda t: zlib.crc32(f"{seed_key}|{t.key}".encode()))
    return ordered[index % len(ordered)].key


def plan_break(
    station_id: str, host: str, playlist: str, seed_key: str, break_index: int
) -> tuple[str, ...]:
    """Asset keys for one break slot. Empty when the station has no voice.

    Slot kinds cycle BREAK_PATTERN; a kind whose pool is empty falls back
    to a host break so the cadence the player learned never stutters.

    Each pool advances on its OWN count, not on the global break index: a
    host is heard twice per pattern cycle, an ID up to twice (its own slot
    plus the tag chasing an ad), an ad once. Indexing every pool by the
    global break number would sample them at stride 2 or 4 and leave most
    of a pool permanently unreachable.
    """
    from .music import STATION_HOST_SEGMENTS

    hosts = STATION_HOST_SEGMENTS.get(host, ())
    if not hosts:
        return ()
    cycle, pattern_pos = divmod(break_index, len(BREAK_PATTERN))
    kind = BREAK_PATTERN[pattern_pos]
    host_pos = 2 * cycle + (1 if pattern_pos == 2 else 0)
    id_pos = 2 * cycle + (1 if kind == "ad_id" else 0)
    ids = STATION_IDS.get(station_id, ())
    ads = station_ads(playlist)
    if kind == "id" and ids:
        return (_pick(ids, f"{seed_key}|id", id_pos),)
    if kind == "ad_id" and ads and ids:
        return (
            _pick(ads, f"{seed_key}|ad", cycle),
            _pick(ids, f"{seed_key}|tag", id_pos),
        )
    return (_pick(hosts, f"{seed_key}|host", host_pos),)
