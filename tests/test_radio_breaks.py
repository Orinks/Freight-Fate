from freight_fate import radio_content
from freight_fate.music import MusicTrack


def test_content_duration_falls_back_to_music_catalog():
    # host_roadhouse_01 lives in music.py's host tables today
    assert radio_content.content_duration_s("host_roadhouse_01") > 0
    assert radio_content.content_duration_s("no_such_key") == 60.0


def test_station_ads_filters_by_format_tag(monkeypatch):
    spots = (
        MusicTrack("ad_test_tires", "Tire ad", "test", 22.0),
        MusicTrack("ad_test_diner", "Diner ad", "test", 25.0),
    )
    monkeypatch.setattr(radio_content, "AD_SPOTS", spots)
    monkeypatch.setattr(
        radio_content,
        "AD_FORMAT_TAGS",
        {"ad_test_tires": ("country",), "ad_test_diner": ("country", "blues")},
    )
    assert [t.key for t in radio_content.station_ads("blues")] == ["ad_test_diner"]
    assert len(radio_content.station_ads("country")) == 2
    assert radio_content.station_ads("jazz") == ()
