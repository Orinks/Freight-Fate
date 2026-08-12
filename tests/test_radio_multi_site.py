"""One dial slot per station identity: multi-site stations collapse.

Curated data legitimately carries the same live stream under several rows
on purpose -- one row per real transmitter/translator (KZYX Willits/Ukiah,
WNPN/ripr Newport/Providence, KENW's three New Mexico sites, SDPB's
statewide network). Each row still feeds its own reception physics, but a
screen reader user tuning past should hear it once, at whichever site is
loudest from the truck's current position -- not once per site. This file
pins that collapsing behavior on a small deterministic fixture rather than
the real catalog, so it stays stable as curated data changes.
"""

from dataclasses import replace

from freight_fate.radio import (
    DEFAULT_RADIO_CATALOG,
    SAFE_FALLBACK_STATION_ID,
    SAFE_ROUTE_PLAYLIST,
    RadioPlaybackError,
    RadioState,
    RadioStation,
    station_identity,
)

SITE_A_POS = (40.000, -75.000)
SITE_B_POS = (40.000, -74.850)  # ~7 miles east of Site A; ranges overlap both ways

FIXTURE_SITE_A = RadioStation(
    id="fixture-site-a",
    name="Fixture Public Radio",
    call_sign="KFIX",
    format="news",
    source="fixture network",
    source_type="local",
    stream_url="https://fixture.test/stream",
    stream_format="mp3",
    lat=SITE_A_POS[0],
    lon=SITE_A_POS[1],
    range_miles=25.0,
    real_stream=True,
    safe_for_streaming=False,
    supported=True,
)
# Same stream, a different real transmitter: same identity as Site A.
FIXTURE_SITE_B = replace(
    FIXTURE_SITE_A,
    id="fixture-site-b",
    lat=SITE_B_POS[0],
    lon=SITE_B_POS[1],
)
# A genuinely different station in the same dial category, for the dead-
# stream handover test: distinct stream_url, so never grouped with A/B.
FIXTURE_LONE = replace(
    FIXTURE_SITE_A,
    id="fixture-lone-station",
    name="Fixture Lone Station",
    call_sign="KLON",
    stream_url="https://fixture.test/lone-stream",
    range_miles=60.0,
)

# The safety sentinels only -- not the full real catalog. Pinning against
# DEFAULT_RADIO_CATALOG's real geography would make these tests fragile to
# future data edits (a curated station added near the fixture coordinates
# could out-rank the fixtures and break the dead-stream handover assertion).
_SENTINELS = tuple(
    s for s in DEFAULT_RADIO_CATALOG if s.id in {SAFE_ROUTE_PLAYLIST, SAFE_FALLBACK_STATION_ID}
)
FIXTURE_CATALOG = _SENTINELS + (FIXTURE_SITE_A, FIXTURE_SITE_B, FIXTURE_LONE)
IDENTITY = station_identity(FIXTURE_SITE_A)


class RecordingBackend:
    def __init__(self, *, fail_ids=()):
        self.fail_ids = set(fail_ids)
        self.played = []

    def play_station(self, station, volume):
        if station.id in self.fail_ids:
            raise RadioPlaybackError("station failed")
        self.played.append((station.id, volume))

    def stop_radio(self):
        pass


def _identity_receptions(radio):
    return [r for r in radio.receivable_stations() if station_identity(r.station) == IDENTITY]


def test_multi_site_station_lists_once_on_the_dial():
    radio = RadioState(catalog=FIXTURE_CATALOG, position=SITE_A_POS)
    assert len(_identity_receptions(radio)) == 1


def test_multi_site_station_lists_the_strongest_site():
    at_a = RadioState(catalog=FIXTURE_CATALOG, position=SITE_A_POS)
    winner_at_a = _identity_receptions(at_a)[0]
    assert winner_at_a.station.id == FIXTURE_SITE_A.id

    at_b = RadioState(catalog=FIXTURE_CATALOG, position=SITE_B_POS)
    winner_at_b = _identity_receptions(at_b)[0]
    assert winner_at_b.station.id == FIXTURE_SITE_B.id


def test_multi_site_station_hands_over_as_the_truck_moves():
    radio = RadioState(catalog=FIXTURE_CATALOG, station_id=FIXTURE_SITE_A.id, position=SITE_A_POS)
    assert radio.current_station().id == FIXTURE_SITE_A.id

    radio.update_position(SITE_B_POS)
    current = radio.current_station()

    # The handover is automatic -- no re-tune needed -- and it persists on
    # station_id so the next call (menu redraw, play(), status_text) agrees.
    assert current.id == FIXTURE_SITE_B.id
    assert radio.station_id == FIXTURE_SITE_B.id
    # Still exactly one dial entry at the new position, not two mid-transition.
    receptions = _identity_receptions(radio)
    assert len(receptions) == 1
    assert receptions[0].station.id == FIXTURE_SITE_B.id


def test_multi_site_dead_stream_still_hands_over_to_a_different_station():
    # Only Site A's id ever gets a play attempt (it's strongest at
    # SITE_A_POS); the assertion on the eventual station proves the failure
    # cascades to Site B too, rather than the radio quietly retrying the
    # same dead stream under B's id.
    radio = RadioState(
        catalog=FIXTURE_CATALOG,
        enabled=True,
        station_id=FIXTURE_SITE_A.id,
        position=SITE_A_POS,
    )
    backend = RecordingBackend(fail_ids={FIXTURE_SITE_A.id})

    action = radio.play(backend)

    assert action.fallback_used is True
    assert action.station.id == FIXTURE_LONE.id  # same band, not a sibling site
    assert radio.station_id == FIXTURE_LONE.id
    assert backend.played == [(FIXTURE_LONE.id, radio.volume)]
    # The whole identity is off the dial, not just the site that failed.
    assert {FIXTURE_SITE_A.id, FIXTURE_SITE_B.id} <= radio.unplayable_ids
    assert _identity_receptions(radio) == []


def test_multi_site_favorite_survives_a_handover():
    radio = RadioState(catalog=FIXTURE_CATALOG, station_id=FIXTURE_SITE_A.id, position=SITE_A_POS)
    radio.toggle_favorite()
    assert FIXTURE_SITE_A.id in radio.favorite_ids
    assert FIXTURE_SITE_B.id in radio.favorite_ids  # saved as one station, not one site

    radio.update_position(SITE_B_POS)
    current = radio.current_station()
    assert current.id == FIXTURE_SITE_B.id
    assert current.id in radio.favorite_ids
