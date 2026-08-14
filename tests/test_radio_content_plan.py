"""Consistency checks for the declarative radio content plan.

The plan (tools/radio_content_plan.py) is pure data consumed by the
generation pass; these tests pin the counts, the casting invariants, and
the spoken-text rules so a content edit cannot silently break the asset
contract or the player-facing register.
"""

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.radio_content_plan import (  # noqa: E402
    AD_PLAN,
    SFX_PROMPTS,
    SONG_PLAN,
    STATIONS,
)

# Playlists that draw ads are real STATION_PLAYLISTS pools (present or
# arriving with the new stations). Never "route": FFR draws no ads.
AD_POOLS = {
    "country",
    "classic_rock",
    "blues",
    "jazz",
    "night",
    "oldies",
    "gospel",
    "tejano",
    "synthwave",
}

# Asset keys follow the shipped catalog's prefixes; classic rock and the
# Night Line pools predate this plan and keep their short stems.
POOL_KEY_PREFIXES = {"classic_rock": "radio_rock_", "night_line": "radio_night_"}

# Spoken content is player-facing for blind players: never name keys,
# menus, or maintainer machinery, and never promise weather.
BANNED_SPOKEN = ("press ", "menu", "setting", "keyboard", "screen reader", "forecast")


def _name_hook(name: str) -> str:
    """The distinctive spoken core of a station name.

    Strips the leading article, the Freight Fate brand prefix, and a
    trailing frequency token so "The Rawhide 98.1" hooks on "Rawhide".
    """
    hook = name.removeprefix("The ").removeprefix("Freight Fate ")
    head, _, tail = hook.rpartition(" ")
    if head and any(ch.isdigit() for ch in tail):
        hook = head
    return hook


def test_every_station_plan_is_complete():
    for key, plan in STATIONS.items():
        assert len(plan.host_lines) == 8, key
        assert len(plan.id_lines) >= 1, key
        assert len(plan.jingle_prompts) == 2, key  # 2 produced + 1 spoken = 3 IDs
        assert plan.voice, key
        assert plan.name in " ".join(plan.id_lines), key  # IDs name the station


def test_station_casting_is_one_to_one():
    voices = [plan.voice for plan in STATIONS.values()]
    assert len(voices) == len(set(voices))
    for key, plan in STATIONS.items():
        assert len(plan.voice_fallbacks) == 2, key
        assert plan.voice not in plan.voice_fallbacks, key
        # A fallback firing must not collapse two stations onto one voice.
        assert not set(plan.voice_fallbacks) & set(voices), key
    # The plan is cast against the owner's real ElevenLabs roster, which
    # is finite: 19 primaries and 6 ad voices leave 13 names for 38
    # fallback slots, so fallbacks may be shared across stations. They
    # still never shadow a primary or ad voice, and no single name backs
    # more than three stations (a cap of two tops out at 26 slots).
    from tools.radio_content_plan import AD_PLAN as _ads

    ad_voices = {ad.voice for ad in _ads}
    fallbacks = [name for plan in STATIONS.values() for name in plan.voice_fallbacks]
    assert not set(fallbacks) & (set(voices) | ad_voices)
    stations_per_name = Counter(fallbacks)
    assert max(stations_per_name.values()) <= 3, stations_per_name


# The owner's real ElevenLabs account roster (dry-run 2026-08-13; match by
# the name before " - ") plus the five proven library-addable names. Every
# cast name must come from this set -- inventing a name means the
# generation pass silently falls back to an arbitrary voice.
ACCOUNT_VOICES = {
    "Adam", "Alexandra", "Alice", "Archer", "Bella", "Bill", "Brian",
    "Callum", "Charlie", "Chris", "Claudia", "Clyde", "Daniel", "Eric",
    "Ethan", "George", "Grandpa Spuds Oxley", "Harry", "Jade", "Jamie",
    "Janet", "Jessica", "Josha", "Laura", "Liam", "Lily", "Mark",
    "Matilda", "River", "Roger", "Sarah", "Wade", "Will",
}  # fmt: skip
LIBRARY_ADDS = {"Thomas", "Patrick", "Rachel", "Michael", "Amelia"}


def test_every_cast_name_is_on_the_real_roster():
    roster = ACCOUNT_VOICES | LIBRARY_ADDS
    for key, plan in STATIONS.items():
        assert plan.voice in roster, (key, plan.voice)
        for name in plan.voice_fallbacks:
            assert name in roster, (key, name)
    for ad in AD_PLAN:
        assert ad.voice in roster, (ad.key, ad.voice)


def test_ad_voices_never_collide_with_station_casting():
    # A station host must never be heard reading a commercial, even
    # after a casting fallback fires.
    primaries = {plan.voice for plan in STATIONS.values()}
    fallbacks = {name for plan in STATIONS.values() for name in plan.voice_fallbacks}
    for ad in AD_PLAN:
        assert ad.voice not in primaries, (ad.key, ad.voice)
        assert ad.voice not in fallbacks, (ad.key, ad.voice)


def test_host_sets_name_the_station_and_stay_in_register():
    for key, plan in STATIONS.items():
        hook = _name_hook(plan.name)
        named = sum(hook in line for line in plan.host_lines)
        assert named >= 2, (key, hook)
        for line in plan.host_lines + plan.id_lines:
            lowered = line.lower()
            for banned in BANNED_SPOKEN:
                assert banned not in lowered, (key, banned, line)


def test_jingle_prompts_carry_the_station_name():
    seen_keys = set()
    for key, plan in STATIONS.items():
        hook = _name_hook(plan.name)
        for asset_key, prompt in plan.jingle_prompts:
            assert asset_key.startswith(f"id_{key}_"), (key, asset_key)
            assert asset_key not in seen_keys, asset_key
            seen_keys.add(asset_key)
            assert hook in prompt, (key, asset_key)


def test_ad_pool_is_modern_and_tagged():
    assert len(AD_PLAN) >= 18
    keys = [a.key for a in AD_PLAN]
    assert len(keys) == len(set(keys))
    assert sum("CB" in a.script for a in AD_PLAN) == 1  # one line, one spot
    for ad in AD_PLAN:
        assert ad.formats, ad.key
        assert set(ad.formats) <= AD_POOLS, ad.key
        assert ad.key.startswith("ad_"), ad.key
        assert ad.voice, ad.key
        assert ad.business, ad.key
        # 20-30 second reads: enough words for a real spot, not a promo tag.
        assert 55 <= len(ad.script.split()) <= 80, (ad.key, len(ad.script.split()))
        lowered = ad.script.lower()
        for banned in BANNED_SPOKEN:
            assert banned not in lowered, (ad.key, banned)
    # Every ad-drawing pool needs enough spots that its stations don't
    # alternate the same two reads forever.
    for pool in AD_POOLS:
        tagged = sum(pool in ad.formats for ad in AD_PLAN)
        assert tagged >= 5, (pool, tagged)


def test_song_plan_matches_batch_size():
    for pool in ("oldies", "gospel", "tejano", "synthwave"):
        assert 8 <= len(SONG_PLAN[pool]) <= 10, pool
    for pool in ("country", "classic_rock", "blues", "jazz"):
        assert 8 <= len(SONG_PLAN[pool]) <= 10, pool
    night = SONG_PLAN.get("night_line", ())
    assert 2 <= len(night) <= 3


def test_song_plan_keys_lengths_and_prompts_are_sound():
    seen = set()
    for pool, songs in SONG_PLAN.items():
        prefix = POOL_KEY_PREFIXES.get(pool, f"radio_{pool}_")
        for song in songs:
            assert song.key.startswith(prefix), (pool, song.key)
            assert song.key not in seen, song.key
            seen.add(song.key)
            assert song.title, song.key
            assert song.description, song.key
            assert song.prompt, song.key
            assert 150_000 <= song.length_ms <= 260_000, song.key
            assert isinstance(song.instrumental, bool), song.key


def test_song_plan_never_collides_with_the_shipped_catalog():
    from freight_fate.music import ALL_MUSIC_TRACKS

    shipped_keys = {track.key for track in ALL_MUSIC_TRACKS}
    shipped_titles = {track.title for track in ALL_MUSIC_TRACKS}
    for songs in SONG_PLAN.values():
        for song in songs:
            assert song.key not in shipped_keys, song.key
            assert song.title not in shipped_titles, song.title


def test_sfx_prompts_cover_the_imaging_bed():
    assert len(SFX_PROMPTS) >= 6
    for key, prompt in SFX_PROMPTS.items():
        assert key, key
        assert prompt, key
