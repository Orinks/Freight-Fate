"""Village and small-town callouts: the bake, the data, and the toggle.

The motivating case is Camp Verde to Payson, where the 35 mph zones on the
Mogollon Rim are Strawberry and Pine. Before this feature the limits dropped
with nothing naming the towns causing them, so the drop read as arbitrary.
"""

import sys
from pathlib import Path

import pytest

from freight_fate.data.world_parsing import _parse_landmark
from freight_fate.settings import CHATTER_CATEGORY_FIELDS, Settings
from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.trip_models import VILLAGE_ENTER_OFF_MI, VILLAGE_PASS_OFF_MI

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import bake_villages as bv  # noqa: E402

# Two-letter state codes and slug punctuation must never reach a spoken line.
UNSPOKEN_MARKERS = ("_", "osm", "place=", "node/", "way/")


def _trip(world, start, end, seed=5):
    route = world.supported_route(start, end)
    assert route is not None, f"no route {start} -> {end}"
    return Trip(route, TruckState(), WeatherSystem("desert_southwest", seed=seed), seed=seed)


# -- the bake's judgment rules ---------------------------------------------


def test_zone_starts_catches_a_step_down_inside_a_town_zone():
    """A 55->40->35 approach has two drops; the second is the village centre."""
    leg = {
        "corridor": {
            "speed_limits": [
                {"at_mi": 0.0, "mph": 55},
                {"at_mi": 37.1, "mph": 40},
                {"at_mi": 39.4, "mph": 35},
                {"at_mi": 43.0, "mph": 55},
            ]
        }
    }
    assert bv.zone_starts(leg) == [37.1, 39.4]


def test_zone_starts_ignores_highway_limits():
    leg = {"corridor": {"speed_limits": [{"at_mi": 0.0, "mph": 65}, {"at_mi": 10.0, "mph": 55}]}}
    assert bv.zone_starts(leg) == []


def test_paired_mile_puts_the_name_before_the_drop_it_explains():
    # The village point sits just past the drop; the callout still leads it.
    assert bv.paired_mile(39.5, [37.1, 39.4]) == 39.2
    # The nearest qualifying drop wins, not the first one in the list.
    assert bv.paired_mile(42.0, [37.1, 42.1]) == 41.9
    # Nothing nearby: the village keeps its own mile.
    assert bv.paired_mile(20.0, [37.1, 39.4]) is None


def test_unspeakable_multilingual_names_are_refused():
    """OSM joins alternative names into one string; none of it reads aloud."""
    assert not bv.speakable("Camp Verde / ʼMatthi:wa / Gambúdih")
    assert not bv.speakable("Kayenta (Todinesshzhee)")
    assert bv.speakable("Strawberry")
    assert bv.speakable("Truth or Consequences")


def test_spoken_line_enters_only_where_the_road_runs_through():
    assert bv.spoken_village("Strawberry", 0.12) == "Entering Strawberry"
    assert bv.spoken_village("Winslow", 2.4) == "Passing Winslow"
    assert bv.spoken_village("Winslow", bv.ENTER_OFF_MI) == "Entering Winslow"


# -- the baked data ---------------------------------------------------------


def test_baked_villages_are_real_named_places_spoken_cleanly(world):
    total = 0
    for leg in world.legs:
        for landmark in leg.landmarks:
            if landmark.category != "village":
                continue
            total += 1
            assert landmark.kind == "point"
            assert landmark.spoken.startswith(("Entering ", "Passing "))
            assert landmark.spoken.endswith(landmark.name)
            assert landmark.off_mi >= 0.0
            blob = f"{landmark.name} {landmark.spoken}".lower()
            assert not any(marker in blob for marker in UNSPOKEN_MARKERS)
            assert 0.0 <= landmark.at_mi <= leg.miles
    assert total > 500, "the village sweep is present, not a stub"


def test_entering_and_passing_match_the_baked_distance(world):
    for leg in world.legs:
        for landmark in leg.landmarks:
            if landmark.category != "village":
                continue
            entering = landmark.spoken.startswith("Entering ")
            assert entering == (landmark.off_mi <= VILLAGE_ENTER_OFF_MI)


def test_camp_verde_to_payson_names_strawberry_and_pine(world):
    """The motivating leg: the rim towns behind the 35 mph zones."""
    leg = next(
        leg
        for leg in world.legs
        if {leg.a, leg.b} == {"camp_verde_az_us", "payson_az_us"}
        or {leg.a, leg.b} == {"Camp Verde", "Payson"}
    )
    villages = {lm.name: lm for lm in leg.landmarks if lm.category == "village"}
    assert "Strawberry" in villages
    assert "Pine" in villages
    for name in ("Strawberry", "Pine"):
        assert villages[name].spoken == f"Entering {name}"
        assert villages[name].off_mi <= VILLAGE_ENTER_OFF_MI
    # Each is announced before the zone it explains, not after it.
    assert villages["Strawberry"].at_mi < villages["Pine"].at_mi


def test_parse_landmark_reads_and_guards_the_offset():
    good = {
        "name": "Strawberry",
        "category": "village",
        "kind": "point",
        "at_mi": 39.2,
        "off_mi": 0.12,
        "spoken": "Entering Strawberry",
    }
    parsed = _parse_landmark(good, 58.0, "a", "b")
    assert parsed.category == "village"
    assert parsed.off_mi == pytest.approx(0.12)
    # Landmarks baked before this feature carry no offset and sit on the route.
    bare = _parse_landmark({k: v for k, v in good.items() if k != "off_mi"}, 58.0, "a", "b")
    assert bare.off_mi == 0.0
    with pytest.raises(ValueError):
        _parse_landmark({**good, "off_mi": -1.0}, 58.0, "a", "b")
    with pytest.raises(ValueError):
        _parse_landmark({**good, "off_mi": "near"}, 58.0, "a", "b")


# -- in-engine: what the game actually serves -------------------------------


def test_trip_speaks_the_rim_towns_on_the_payson_run(world):
    trip = _trip(world, "Camp Verde", "Payson")
    spoken = [c.spoken for c in trip.landmarks if c.category == "village"]
    assert "Entering Strawberry." in spoken
    assert "Entering Pine." in spoken


def test_neighbouring_towns_both_speak(world):
    """Strawberry and Pine sit under three miles apart and both must land.

    A wider village spacing was tried and silently deleted Strawberry -- the
    exact case the feature exists for. Real towns are allowed to be close."""
    trip = _trip(world, "Camp Verde", "Payson")
    villages = [c for c in trip.landmarks if c.category == "village"]
    names = [c.spoken for c in villages]
    assert names == ["Entering Strawberry.", "Entering Pine."]
    gap = villages[1].at_mi - villages[0].at_mi
    assert gap < 3.0, "these two are genuinely close together"


def test_a_town_outranks_scenery_sharing_its_mile(world):
    """Pine and Tonto National Forest both sit at mile 41.9 on the rim.

    The town name orients the driver and explains the 35 about to arrive, so
    ambient scenery yields to it instead of winning by list order."""
    trip = _trip(world, "Camp Verde", "Payson")
    spoken = [c.spoken for c in trip.landmarks]
    assert "Entering Pine." in spoken
    assert "Entering Tonto National Forest." not in spoken
    # The scenery that does not collide with a town is untouched.
    assert "Entering Coconino National Forest." in spoken
    assert "Crossing the East Verde River." in spoken


def test_trip_withholds_villages_the_route_never_reaches(world):
    """Baked wide, displayed tight: a distant town is data, not a callout."""
    scheduled = 0
    for leg in world.legs:
        far = [
            lm
            for lm in leg.landmarks
            if lm.category == "village" and lm.off_mi > VILLAGE_PASS_OFF_MI
        ]
        scheduled += len(far)
    assert scheduled, "the wide catchment collected towns off the road"

    trip = _trip(world, "Camp Verde", "Payson")
    for callout in trip.landmarks:
        if callout.category != "village":
            continue
        name = callout.spoken.rstrip(".").split(" ", 1)[1]
        match = next(
            lm
            for leg in trip.route.legs
            for lm in leg.landmarks
            if lm.category == "village" and lm.name == name
        )
        assert match.off_mi <= VILLAGE_PASS_OFF_MI


# -- the toggle -------------------------------------------------------------


def test_village_callouts_are_on_by_default_and_switchable():
    settings = Settings()
    assert settings.chatter_villages is True
    assert CHATTER_CATEGORY_FIELDS["village"] == "chatter_villages"
    assert settings.chatter_enabled("village") is True
    settings.chatter_villages = False
    assert settings.chatter_enabled("village") is False
    # The village switch is its own: silencing towns leaves the scenery alone.
    assert settings.chatter_enabled("river") is True


def test_driving_speaks_and_silences_a_village_callout(monkeypatch):
    """In-engine: the switch decides whether the name reaches the player."""
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        from freight_fate.models.profile import Profile

        app.ctx.profile = Profile(name="Villages", current_city="Buffalo")
        route = app.ctx.world.supported_route("Buffalo", "Rochester")
        job = Job(
            CARGO_CATALOG["general"],
            12.0,
            "Buffalo",
            "company yard",
            "Rochester",
            route.miles,
            1000.0,
            12.0,
            destination_location="Rochester freight market",
        )
        driving = DrivingState(app.ctx, job, route, phase="delivery")
        calls = []
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: calls.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        village = TripEvent(
            TripEventKind.LANDMARK, "Entering Strawberry.", {"category": "village"}
        )

        driving._handle_trip_event(village)
        assert calls[-1] == "Entering Strawberry."

        app.ctx.settings.chatter_villages = False
        driving._ambient_event_cooldown_s = 0.0
        driving._pending_ambient_event = None
        driving._handle_trip_event(village)
        assert len(calls) == 1  # filtered, not repeated
    finally:
        app.shutdown()


def test_all_chatter_switch_covers_villages():
    settings = Settings()
    settings.set_all_chatter(False)
    assert settings.chatter_villages is False
    assert settings.chatter_enabled("village") is False
    settings.set_all_chatter(True)
    assert settings.chatter_villages is True
