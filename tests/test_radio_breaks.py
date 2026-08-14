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


def _patched_pools(monkeypatch):
    hosts = tuple(MusicTrack(f"host_x_{i:02d}", f"h{i}", "", 5.0) for i in range(1, 9))
    ids = tuple(MusicTrack(f"id_x_{i:02d}", f"i{i}", "", 10.0) for i in range(1, 4))
    ads = tuple(MusicTrack(f"ad_y_{i:02d}", f"a{i}", "", 25.0) for i in range(1, 5))
    monkeypatch.setattr("freight_fate.music.STATION_HOST_SEGMENTS", {"x": hosts}, raising=False)
    monkeypatch.setattr(radio_content, "STATION_IDS", {"x": ids})
    monkeypatch.setattr(radio_content, "AD_SPOTS", ads)
    monkeypatch.setattr(radio_content, "AD_FORMAT_TAGS", {t.key: ("country",) for t in ads})


def test_break_pattern_cycles_and_is_deterministic(monkeypatch):
    _patched_pools(monkeypatch)
    kinds = []
    for i in range(8):
        first = radio_content.plan_break("x", "country", "seed", i)
        assert first == radio_content.plan_break("x", "country", "seed", i)
        kinds.append(first)
    # pattern: host, id, host, ad_id, repeated
    assert kinds[0][0].startswith("host_")
    assert kinds[1][0].startswith("id_")
    assert kinds[3][0].startswith("ad_") and kinds[3][1].startswith("id_")
    assert kinds[4] == kinds[0] or kinds[4][0].startswith("host_")


def test_break_slots_degrade_when_pools_missing(monkeypatch):
    _patched_pools(monkeypatch)
    monkeypatch.setattr(radio_content, "STATION_IDS", {})
    monkeypatch.setattr(radio_content, "AD_SPOTS", ())
    # id and ad slots fall back to a host break; still never empty for a
    # station that has a host
    for i in range(4):
        elems = radio_content.plan_break("x", "country", "seed", i)
        assert elems and elems[0].startswith("host_")
    # and a station with no host at all gets no break
    assert radio_content.plan_break("", "country", "seed", 0) == ()
