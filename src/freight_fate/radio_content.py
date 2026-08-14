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

# Keyed by catalog station id.
STATION_IDS: dict[str, tuple[MusicTrack, ...]] = {}
AD_SPOTS: tuple[MusicTrack, ...] = ()
AD_FORMAT_TAGS: dict[str, tuple[str, ...]] = {}

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
