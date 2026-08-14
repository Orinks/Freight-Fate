"""Per-station radio identity content: IDs, ads, and break planning.

Tables are filled by the generation pass (tools/generate_radio.py); until
then they are empty and every consumer degrades to plain host breaks. Keys
follow the asset contract: host_<station>_NN, id_<station>_NN, ad_<slug>.
"""

from __future__ import annotations

from .music import MusicTrack, music_track_duration_s

STATION_IDS: dict[str, tuple[MusicTrack, ...]] = {}
AD_SPOTS: tuple[MusicTrack, ...] = ()
AD_FORMAT_TAGS: dict[str, tuple[str, ...]] = {}

# One break after every 2 songs; break content cycles this pattern. An
# ad never runs without an ID chasing it back into music, so ads are
# never adjacent and an ID lands at least once per four breaks.
BREAK_PATTERN: tuple[str, ...] = ("host", "id", "host", "ad_id")

_LOCAL_BY_KEY: dict[str, MusicTrack] = {}


def _reindex() -> None:
    _LOCAL_BY_KEY.clear()
    for pool in STATION_IDS.values():
        _LOCAL_BY_KEY.update({t.key: t for t in pool})
    _LOCAL_BY_KEY.update({t.key: t for t in AD_SPOTS})


_reindex()


def content_duration_s(key: str) -> float:
    track = _LOCAL_BY_KEY.get(key)
    if track is not None:
        return track.duration_s
    return music_track_duration_s(key)


def station_ads(playlist: str) -> tuple[MusicTrack, ...]:
    return tuple(spot for spot in AD_SPOTS if playlist in AD_FORMAT_TAGS.get(spot.key, ()))
