"""The radio as a driver uses it: keys, spoken readouts, and the menu.

No test here touches the network. The audio engine is stubbed so tuning a
station records the URL that would have been played instead of playing it.
"""

import pygame
import pytest
from driving_feature_helpers import key_event, start_drive
from speech_capture import speech_stub

from freight_fate.app import App
from freight_fate.data.radio_catalog import RadioCatalog, Station
from freight_fate.sim.radio import BAND_FM, BAND_SATELLITE, RadioTuner

NEAR = (41.8781, -87.6298)


class FakeRadioAudio:
    """Records what the radio asked the audio engine to do."""

    radio_supported = True

    def __init__(self) -> None:
        self.radio_state = "idle"
        self.played: list[str] = []
        self.gains: list[float] = []
        self.stops = 0
        self.music: list[str] = []  # tracks started
        self.music_stops = 0

    def play_radio(self, url, fade_ms=1200):
        self.played.append(url)
        self.radio_state = "playing"

    def stop_radio(self, fade_ms=600):
        self.stops += 1
        self.radio_state = "idle"

    def set_radio_gain(self, gain):
        self.gains.append(gain)

    def play_music(self, track, fade_ms=1500):
        self.music.append(track)

    def stop_music(self, fade_ms=1000):
        self.music_stops += 1

    def __getattr__(self, name):
        # Everything else the driving state asks of audio is a no-op here.
        return lambda *a, **k: None


def _catalog():
    def local(call_sign, frequency):
        return Station(
            id=f"id-{call_sign}",
            name=f"{call_sign} Radio",
            url=f"https://example.invalid/{call_sign}",
            band=BAND_FM,
            call_sign=call_sign,
            frequency=frequency,
            tags="country",
            lat=NEAR[0],
            lon=NEAR[1],
            radius_mi=40.0,
            radius_source="default",
        )

    return RadioCatalog(
        local=(local("WAAA", 90.1), local("WBBB", 95.5)),
        satellite=(
            Station(
                id="sat",
                name="Example Satellite",
                url="https://example.invalid/sat",
                band=BAND_SATELLITE,
            ),
        ),
    )


@pytest.fixture
def drive(monkeypatch):
    """A loaded delivery with the radio enabled and audio stubbed out."""
    app = App()
    try:
        driving = start_drive(app)
        app.ctx.settings.radio_enabled = True
        fake = FakeRadioAudio()
        monkeypatch.setattr(app.ctx, "audio", fake)
        # A tuner on a small known catalog, parked on top of the transmitters.
        driving._radio = RadioTuner(_catalog(), lat=NEAR[0], lon=NEAR[1])
        driving._radio_position_timer = 0.0
        yield app, driving, fake
    finally:
        app.shutdown()


def test_m_turns_the_radio_on_and_says_what_is_playing(drive, monkeypatch):
    app, driving, fake = drive
    spoken: list[str] = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

    driving.handle_event(key_event(pygame.K_m))

    assert driving.radio.on is True
    assert any("WAAA" in line for line in spoken)
    assert any("90.1 F M" in line for line in spoken)
    assert fake.played == ["https://example.invalid/WAAA"]


def test_m_again_is_an_instant_mute(drive, monkeypatch):
    app, driving, fake = drive
    monkeypatch.setattr(app.ctx, "say", speech_stub())
    driving.handle_event(key_event(pygame.K_m))
    spoken: list[str] = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

    driving.handle_event(key_event(pygame.K_m))

    assert driving.radio.on is False
    assert fake.stops >= 1
    assert "Radio off." in spoken


def test_o_and_i_step_up_and_down_the_dial(drive, monkeypatch):
    app, driving, fake = drive
    spoken: list[str] = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

    driving.handle_event(key_event(pygame.K_m))  # on, lands on WAAA
    driving.handle_event(key_event(pygame.K_o))  # up the dial
    assert driving.radio.station.call_sign == "WBBB"
    driving.handle_event(key_event(pygame.K_i))  # back down
    assert driving.radio.station.call_sign == "WAAA"
    assert fake.played[-1] == "https://example.invalid/WAAA"


def test_the_seek_keys_survive_message_review(drive, monkeypatch):
    """Review claims comma and period on every screen; the dial keys must not
    be keys review already owns, or they would never reach the driver."""
    app, driving, _ = drive
    monkeypatch.setattr(app.ctx, "say", speech_stub())
    for key in (pygame.K_m, pygame.K_i, pygame.K_o, pygame.K_y):
        assert driving.handle_message_review(key_event(key)) is False


def test_the_radio_is_off_unless_the_player_turned_it_on(monkeypatch):
    app = App()
    try:
        driving = start_drive(app)
        spoken: list[str] = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        assert app.ctx.settings.radio_enabled is False

        driving.handle_event(key_event(pygame.K_m))

        assert getattr(driving, "_radio", None) is None  # never even built
        assert any("Settings" in line for line in spoken)
    finally:
        app.shutdown()


def test_driving_out_of_range_hands_over_to_the_satellite(drive, monkeypatch):
    app, driving, fake = drive
    monkeypatch.setattr(app.ctx, "say", speech_stub())
    events: list[str] = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving.handle_event(key_event(pygame.K_m))

    # Teleport the truck a long way from the transmitters and let a second pass.
    monkeypatch.setattr(driving.trip, "position_latlon", lambda *a: (41.8781, -96.0))
    driving._update_radio(2.0)

    assert driving.radio.station.band == BAND_SATELLITE
    assert any("WAAA lost" in line for line in events)
    assert fake.played[-1] == "https://example.invalid/sat"


def test_a_dead_stream_hands_over_on_the_same_band(drive, monkeypatch):
    """A stream that will not play must not eject the driver from the band.

    Dropping straight to satellite strands them: that band holds one station,
    so the seek keys then do nothing and changing band lands back on the same
    dead station.
    """
    app, driving, fake = drive
    monkeypatch.setattr(app.ctx, "say", speech_stub())
    events: list[str] = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving.handle_event(key_event(pygame.K_m))
    assert driving.radio.station.call_sign == "WAAA"

    fake.radio_state = "failed"
    driving._update_radio(0.1)

    assert driving.radio.station.call_sign == "WBBB"  # the other FM station
    assert driving.radio.band == BAND_FM
    assert any("not answering" in line for line in events)
    assert fake.played[-1] == "https://example.invalid/WBBB"


def test_a_dead_station_leaves_the_dial_for_the_session(drive, monkeypatch):
    """Otherwise every band change walks straight back into the same failure."""
    app, driving, fake = drive
    monkeypatch.setattr(app.ctx, "say", speech_stub())
    monkeypatch.setattr(app.ctx, "say_event", speech_stub())
    driving.handle_event(key_event(pygame.K_m))
    fake.radio_state = "failed"
    driving._update_radio(0.1)

    remaining = [s.call_sign for s in driving.radio.stations_for(BAND_FM)]
    assert remaining == ["WBBB"], "the dead station is still on the dial"


def test_the_last_station_failing_falls_silent_and_says_so(drive, monkeypatch):
    app, driving, fake = drive
    monkeypatch.setattr(app.ctx, "say", speech_stub())
    events: list[str] = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    driving.handle_event(key_event(pygame.K_m))

    # Every station in turn refuses to play.
    for _ in range(6):
        fake.radio_state = "failed"
        driving._update_radio(0.1)

    assert driving.radio.on is False
    assert any("nothing else is in range" in line for line in events)


def test_seeking_a_band_with_one_station_says_so_instead_of_repeating(drive, monkeypatch):
    """Twelve presses must not read the same station out twelve times."""
    app, driving, fake = drive
    monkeypatch.setattr(app.ctx, "say", speech_stub())
    driving.handle_event(key_event(pygame.K_m))
    driving.radio.set_band(BAND_SATELLITE)

    spoken: list[str] = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    driving.handle_event(key_event(pygame.K_o))

    assert len(spoken) == 1
    assert "only station on satellite" in spoken[0]
    assert "Press Y" in spoken[0]


def test_reception_fades_with_signal_strength(drive, monkeypatch):
    app, driving, fake = drive
    monkeypatch.setattr(app.ctx, "say", speech_stub())
    driving.handle_event(key_event(pygame.K_m))

    # On top of the transmitter, then out near the edge of its circle.
    monkeypatch.setattr(driving.trip, "position_latlon", lambda *a: NEAR)
    driving._update_radio(2.0)
    strong = fake.gains[-1]
    monkeypatch.setattr(driving.trip, "position_latlon", lambda *a: (NEAR[0] + 0.5, NEAR[1]))
    driving._update_radio(2.0)
    assert fake.gains[-1] < strong


def test_switching_the_setting_off_mid_drive_stops_the_radio(drive, monkeypatch):
    app, driving, fake = drive
    monkeypatch.setattr(app.ctx, "say", speech_stub())
    driving.handle_event(key_event(pygame.K_m))
    assert driving.radio.on is True

    app.ctx.settings.radio_enabled = False
    driving._update_radio(0.1)

    assert driving.radio.on is False
    assert fake.stops >= 1


def test_the_radio_menu_lists_stations_and_keeps_favorites(drive, monkeypatch):
    app, driving, _ = drive
    from freight_fate.states.radio_states import RadioState

    monkeypatch.setattr(app.ctx, "say", speech_stub())
    driving.handle_event(key_event(pygame.K_m))
    state = RadioState(app.ctx, driving)
    state.enter()

    labels = [item.text for item in state.items]
    assert any(label.startswith("Radio: on") for label in labels)
    assert any("WAAA" in label for label in labels)
    assert "Back" in labels

    # Put the cursor on a station row and keep it.
    station_row = next(i for i, item in enumerate(state.items) if "WBBB" in item.text)
    state.index = station_row
    spoken: list[str] = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    state.handle_event(key_event(pygame.K_f))

    assert app.ctx.profile.radio_favorites == ["id-WBBB"]
    assert any("added to favorites" in line for line in spoken)

    # And the same key takes it back off.
    state.index = next(i for i, item in enumerate(state.items) if "WBBB" in item.text)
    state.handle_event(key_event(pygame.K_f))
    assert app.ctx.profile.radio_favorites == []


def test_favorites_survive_a_save_and_reload(drive):
    app, _driving, _ = drive
    profile = app.ctx.profile
    profile.radio_favorites = ["id-WAAA"]

    from freight_fate.models.profile import Profile

    restored = Profile.from_dict(profile.to_dict())
    assert restored.radio_favorites == ["id-WAAA"]


def test_an_older_save_without_favorites_still_loads():
    """The field is additive with a default, so no migration is involved."""
    from freight_fate.models.profile import Profile

    data = Profile(name="Old Hand").to_dict()
    data.pop("radio_favorites")
    assert Profile.from_dict(data).radio_favorites == []


def test_the_music_bed_stops_while_a_station_plays(drive, monkeypatch):
    """A station and a music bed together are a wall of sound."""
    app, driving, fake = drive
    monkeypatch.setattr(app.ctx, "say", speech_stub())

    driving.handle_event(key_event(pygame.K_m))
    assert fake.music_stops >= 1, "the drive bed kept playing under the station"

    # And the rotation cannot start it again behind the radio's back.
    fake.music.clear()
    driving._play_current_music()
    driving._update_music_rotation(driving._music_night, 9999.0)
    assert fake.music == []


def test_switching_the_radio_off_hands_the_cab_back_to_the_music(drive, monkeypatch):
    app, driving, fake = drive
    monkeypatch.setattr(app.ctx, "say", speech_stub())
    driving.handle_event(key_event(pygame.K_m))
    fake.music.clear()

    driving.handle_event(key_event(pygame.K_m))  # off again

    assert driving.radio.on is False
    assert fake.music, "the music bed did not come back"


def test_the_pause_menu_offers_the_radio(drive):
    app, driving, _ = drive
    from freight_fate.states.driving import PauseMenuState

    labels = [item.text for item in PauseMenuState(app.ctx, driving).build_items()]
    assert "Radio" in labels


def test_shift_m_opens_the_radio_screen(drive, monkeypatch):
    app, driving, _ = drive
    from freight_fate.states.radio_states import RadioState

    monkeypatch.setattr(app.ctx, "say", speech_stub())
    driving.handle_event(key_event(pygame.K_m, mod=pygame.KMOD_LSHIFT))

    assert isinstance(app.state, RadioState)
    # And plain M did not also fire, so the radio is still off.
    assert driving._radio.on is False


def test_the_settings_menu_exposes_the_radio_switch_and_volume():
    app = App()
    try:
        from freight_fate.states.main_menu import SettingsCategoryState

        state = SettingsCategoryState(app.ctx, "audio")
        labels = [item.text for item in state.build_items()]
        assert any(label.startswith("Radio stations:") for label in labels)
        assert any(label.startswith("Radio volume:") for label in labels)
        # Off by default, so a player recording their session is safe.
        assert "Radio stations: off" in labels
    finally:
        app.shutdown()
