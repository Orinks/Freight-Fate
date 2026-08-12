"""Favorites: saved stations pull forward to their own early dial category."""

from freight_fate.models.profile import Profile
from freight_fate.radio import (
    DIAL_CATEGORY_NAMES,
    FAVORITES_GROUP,
    RadioState,
)

DALLAS = (32.7767, -96.797)


def _radio(**kwargs) -> RadioState:
    kwargs.setdefault("streamer_safe", False)
    kwargs.setdefault("position", DALLAS)
    return RadioState(**kwargs)


def test_toggle_saves_and_unsaves_with_spoken_confirmation():
    radio = _radio()
    station = next(s for s in radio.available_stations() if s.source_type == "imported")
    radio.station_id = station.id
    message = radio.toggle_favorite()
    assert message == f"Saved {station.display_name} to favorites."
    assert station.id in radio.favorite_ids
    message = radio.toggle_favorite()
    assert message == f"Removed {station.display_name} from favorites."
    assert station.id not in radio.favorite_ids


def test_favorite_pulls_a_web_station_ahead_of_terrestrial():
    radio = _radio()
    web = next(s for s in radio.available_stations() if s.source_type == "web")
    radio.favorite_ids.add(web.id)
    stations = radio.available_stations()
    favorite_index = stations.index(web)
    first_terrestrial = next(
        i
        for i, s in enumerate(stations)
        # Playlist-backed fictional stations are Freight Fate stations now,
        # sorted ahead of favorites by design; terrestrial means the real dial.
        if s.source_type in {"imported", "local", "regional"} and not s.playlist
    )
    assert favorite_index < first_terrestrial
    assert radio._group(web) == FAVORITES_GROUP
    assert DIAL_CATEGORY_NAMES[FAVORITES_GROUP] == "Favorites"


def test_category_jump_lands_on_favorites():
    radio = _radio()
    web = next(s for s in radio.available_stations() if s.source_type == "web")
    radio.favorite_ids.add(web.id)
    seen = set()
    for _ in range(len(DIAL_CATEGORY_NAMES)):
        action = radio.tune_category(1)
        seen.add(radio._group(radio.current_station()))
        if radio.current_station().id == web.id:
            break
    assert radio.current_station().id == web.id
    assert FAVORITES_GROUP in seen
    assert "Favorites" in action.message


def test_out_of_range_favorite_stays_off_the_dial():
    radio = _radio()
    dallas_local = next(s for s in radio.available_stations() if s.source_type == "imported")
    radio.favorite_ids.add(dallas_local.id)
    radio.update_position((47.6062, -122.3321))  # Seattle
    assert dallas_local.id not in {s.id for s in radio.available_stations()}


def test_streamer_safe_mode_still_hides_favorited_real_streams():
    radio = _radio()
    web = next(s for s in radio.available_stations() if s.source_type == "web")
    radio.favorite_ids.add(web.id)
    radio.streamer_safe = True
    assert web.id not in {s.id for s in radio.available_stations()}


def test_the_safety_fallback_cannot_be_favorited():
    radio = _radio()
    fallback = radio.fallback_station()
    radio.station_id = fallback.id
    radio.update_position(None)
    # Force current onto the fallback by making nothing else receivable.
    radio.catalog = (fallback,)
    assert radio.toggle_favorite() == "The safety fallback is always on the dial."
    assert not radio.favorite_ids


def test_favorites_ride_the_profile():
    profile = Profile()
    assert profile.radio_favorites == []
    profile.radio_favorites = ["rb-someid"]
    reloaded = Profile.from_dict(profile.to_dict())
    assert reloaded.radio_favorites == ["rb-someid"]

    class FakeSettings:
        radio_enabled = True
        radio_station_id = "route_playlist"
        radio_volume = 0.25
        radio_streamer_safe = False

    radio = RadioState.from_settings(FakeSettings(), reloaded)
    assert radio.favorite_ids == {"rb-someid"}
