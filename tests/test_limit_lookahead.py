"""The co-driver warns before a posted-limit drop and sizes short zones.

Born from the NY-12 playtest (2026-07-19): real village 30s every few miles
are honest data, but hitting one blind at 55 in a Class-8 is not playable.
The warning reuses the curve-pacenote eligibility math (reaction plus
comfortable braking), and a short village zone has its length spoken on
entry so it reads as a passing event, not a new cruising speed.
"""

from __future__ import annotations

from freight_fate.data.world import Leg, SpeedLimitSample
from freight_fate.data.world_models import GradeSegment, Route, StateMileage
from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.trip import _spoken_short_miles
from freight_fate.sim.trip_models import RoadStop, TripEventKind


def _trip(world, speed_limits, *, imperial=True, grade_segments=()):
    """A quiet 100-mile US-highway trip between real cities (the heuristic
    branch needs real city regions), with a synthetic posted profile."""
    leg = Leg(
        "aberdeen_sd_us",
        "pierre_sd_us",
        100.0,
        "US-83",
        "flat",
        (),
        state_miles=(StateMileage("South Dakota", 100.0),),
        speed_limits=tuple(speed_limits),
        grade_segments=tuple(grade_segments),
    )
    route = Route(["aberdeen_sd_us", "pierre_sd_us"], [leg])
    trip = Trip(route, TruckState(), WeatherSystem("upper_midwest", seed=1), seed=2)
    trip.imperial = imperial
    trip.zones = []
    trip.curves = ()
    trip._hazard_check_mi = 1e9
    trip._inspection_check_mi = 1e9
    return trip


def _cues(trip, position_mi, speed_mph):
    trip.position_mi = position_mi
    trip.truck.velocity_mps = speed_mph * 0.44704
    return [e.message for e in trip.update(0) if e.kind == TripEventKind.GPS_CUE]


VILLAGE = (
    SpeedLimitSample(0.0, 65.0),
    SpeedLimitSample(50.0, 30.0),
    SpeedLimitSample(50.6, 65.0),
)


def test_warns_before_a_big_drop_at_speed(world):
    trip = _trip(world, VILLAGE)
    cues = _cues(trip, 49.8, 55.0)
    assert "Speed limit drops to 30 in a quarter mile." in cues


def test_warning_fires_once(world):
    trip = _trip(world, VILLAGE)
    _cues(trip, 49.8, 55.0)
    assert not [c for c in _cues(trip, 49.85, 55.0) if "drops to" in c]


def test_no_warning_when_already_slow(world):
    trip = _trip(world, VILLAGE)
    assert not [c for c in _cues(trip, 49.8, 30.0) if "drops to" in c]


def test_no_warning_beyond_the_scaled_lookahead_window(world):
    # Beyond LIMIT_WARNING_MAX_LEAD_MI the boundary isn't even scanned for
    # yet, whatever the current pace -- the cap that keeps a heavily
    # compressed drive from calling a drop absurdly far out.
    trip = _trip(world, VILLAGE)
    assert not [c for c in _cues(trip, 44.5, 55.0) if "drops to" in c]


def test_advance_warning_lead_scales_with_time_compression(world):
    """The lead is sized in ``LIMIT_WARNING_REAL_S`` real seconds of hearing-
    and-braking time at the current pace, not a fixed game-mile distance --
    the same law ``_zone_warning_lookahead_mi`` and ``EXIT_WARNING_REAL_S``
    apply elsewhere. Under heavy time compression the old curve-pacenote-
    derived lead (still used for curves) bought under a real second; a half
    mile passed in a few real seconds and the drop landed before the call
    finished speaking (owner's live playtest, 2026-08-12). The fix buys back
    several times that.
    """
    trip = _trip(world, VILLAGE)
    trip.time_scale = 40.0  # the game's top compression setting
    speed = 55.0
    # The compression ramp reads the truck's real speed; a parked trip idles
    # at the 4x floor, so put the truck at highway pace first.
    trip.truck.velocity_mps = speed * 0.44704
    scale = trip.effective_time_scale
    assert scale == 40.0  # full pacing already resumed at this speed

    old_lead_mi = trip._curve_pacenote_lead_mi(speed, 30.0)
    old_real_s = old_lead_mi * 3600.0 / (speed * scale)
    assert old_real_s < 1.0  # the bug: barely a real second to react

    new_lead_mi = trip._limit_drop_warning_lead_mi(speed)
    new_real_s = new_lead_mi * 3600.0 / (speed * scale)
    assert new_real_s > old_real_s * 5

    # And the cue actually fires that far out.
    position = 50.0 - new_lead_mi + 0.05
    cues = _cues(trip, position, speed)
    assert any(c.startswith("Speed limit drops to 30 in") for c in cues)


def test_no_warning_for_a_small_step(world):
    trip = _trip(
        world,
        (SpeedLimitSample(0.0, 65.0), SpeedLimitSample(50.0, 60.0)),
    )
    assert not [c for c in _cues(trip, 49.8, 65.0) if "drops to" in c]


def test_short_zone_length_spoken_on_entry(world):
    trip = _trip(world, VILLAGE)
    # Seeded well outside LIMIT_WARNING_MAX_LEAD_MI so this update only seeds
    # the announced limit at 65 and does not itself pre-announce the drop --
    # this test is about the arrival line's own span wording, covered
    # separately from the pre-announce suppression below.
    _cues(trip, 40.0, 55.0)
    cues = _cues(trip, 50.05, 30.0)
    assert "Speed limit reduced to 30 for half a mile." in cues


def test_long_zone_entry_stays_unsized(world):
    trip = _trip(
        world,
        (SpeedLimitSample(0.0, 65.0), SpeedLimitSample(50.0, 30.0)),
    )
    _cues(trip, 40.0, 55.0)  # seed the announced limit at 65, out of lookahead range
    cues = _cues(trip, 50.05, 30.0)
    reduced = [c for c in cues if c.startswith("Speed limit reduced")]
    assert reduced == ["Speed limit reduced to 30."]


def test_unannounced_drop_still_speaks_reduced_to(world):
    """A posting the advance pacenote never got a chance to warn about --
    too far out to be in the lookahead window when last checked -- still
    gets its plain arrival confirmation. Suppression only applies to a
    posting that was actually pre-announced."""
    trip = _trip(world, VILLAGE)
    seed_cues = _cues(trip, 40.0, 55.0)
    assert not [c for c in seed_cues if "drops to" in c]
    cues = _cues(trip, 50.05, 30.0)
    assert "Speed limit reduced to 30 for half a mile." in cues


def test_preannounced_drop_does_not_repeat_reduced_to(world):
    """The complaint (owner, live playtest, 2026-08-12): a posted drop spoke
    'Speed limit drops to 45 in half a mile.' and then, an instant later
    under time compression, 'Speed limit reduced to 45.' -- the same number
    twice. Once the advance pacenote has named a posting, the plain arrival
    line for that same number stays quiet."""
    trip = _trip(world, VILLAGE)
    warn_cues = _cues(trip, 49.8, 55.0)
    assert "Speed limit drops to 30 in a quarter mile." in warn_cues
    arrival_cues = _cues(trip, 50.05, 55.0)
    assert not [c for c in arrival_cues if c.startswith("Speed limit reduced")]


def test_raise_is_never_suppressed_by_a_preannounced_drop(world):
    """Only 'reduced to' is ever suppressed by a pre-announced drop -- a
    raise leaving the zone always speaks, carrying its own number."""
    trip = _trip(world, VILLAGE)
    _cues(trip, 49.8, 55.0)  # advance-warns and pre-announces the 30 drop
    _cues(trip, 50.05, 55.0)  # arrival, suppressed (see test above)
    cues = _cues(trip, 50.65, 55.0)
    assert "Speed limit raised to 65." in cues


def test_gap_marker_ends_a_village_zone(world):
    # The NY-12 shape: a village 30 whose OSM tagging ends 0.6 miles in.
    # Inside the gap the heuristic answers (US highway 65), not the stale 30.
    trip = _trip(
        world,
        (SpeedLimitSample(40.0, 30.0), SpeedLimitSample(40.6, None)),
    )
    assert trip._corridor_limit_at(40.3) == 30.0
    assert trip._corridor_limit_at(45.0) == 65.0


def test_lowered_limit_names_a_weigh_station_ahead(world):
    """No city nearby, but a weigh station sits just past the drop -- the
    scale is an honest reason the trip's own data can supply."""
    trip = _trip(
        world,
        (SpeedLimitSample(0.0, 65.0), SpeedLimitSample(50.0, 30.0)),
    )
    trip.stops = [RoadStop("SD Scale House", 50.5, "weigh_station")]
    _cues(trip, 40.0, 55.0)  # seed the announced limit at 65, out of lookahead range
    cues = _cues(trip, 50.05, 30.0)
    reduced = [c for c in cues if c.startswith("Speed limit reduced")]
    assert reduced == ["Speed limit reduced to 30 for the weigh station ahead."]


def test_lowered_limit_ignores_a_stop_already_passed(world):
    """A weigh station behind the truck does not explain a limit dropping
    now -- only a stop still ahead counts."""
    trip = _trip(
        world,
        (SpeedLimitSample(0.0, 65.0), SpeedLimitSample(50.0, 30.0)),
    )
    trip.stops = [RoadStop("SD Scale House", 49.0, "weigh_station")]
    _cues(trip, 40.0, 55.0)
    cues = _cues(trip, 50.05, 30.0)
    reduced = [c for c in cues if c.startswith("Speed limit reduced")]
    assert reduced == ["Speed limit reduced to 30."]


def test_lowered_limit_names_a_downgrade_ahead(world):
    """No city and no stop, but a sustained downgrade starts right where the
    lower posting begins -- the road's own profile explains the number."""
    trip = _trip(
        world,
        (SpeedLimitSample(0.0, 65.0), SpeedLimitSample(50.0, 30.0)),
        grade_segments=(GradeSegment(50.0, 55.0, -4.0, "hills"),),
    )
    _cues(trip, 40.0, 55.0)
    cues = _cues(trip, 50.05, 30.0)
    reduced = [c for c in cues if c.startswith("Speed limit reduced")]
    assert reduced == ["Speed limit reduced to 30 for the downgrade."]


def test_lowered_limit_city_reason_beats_a_stop_ahead(world, monkeypatch):
    """The named city stays the first and only reason when both a city and a
    road stop could explain the same drop -- the existing city clause is
    untouched and still wins."""
    trip = _trip(
        world,
        (SpeedLimitSample(0.0, 65.0), SpeedLimitSample(50.0, 30.0)),
    )
    trip.stops = [RoadStop("SD Scale House", 50.5, "weigh_station")]
    monkeypatch.setattr(trip, "_nearest_urban_city", lambda mile: ("pierre_sd_us", 60.0))
    _cues(trip, 40.0, 55.0)
    cues = _cues(trip, 50.05, 30.0)
    reduced = [c for c in cues if c.startswith("Speed limit reduced")]
    assert len(reduced) == 1
    assert "approaching" in reduced[0]
    assert "weigh station" not in reduced[0]


def test_raised_limit_never_gets_a_reason(world):
    """A raised limit stays bare even with a road stop sitting right at the
    boundary -- reasons only ever attach to a drop."""
    trip = _trip(world, VILLAGE)
    trip.stops = [RoadStop("SD Scale House", 50.7, "weigh_station")]
    _cues(trip, 49.8, 55.0)
    _cues(trip, 50.05, 55.0)
    cues = _cues(trip, 50.65, 55.0)
    assert "Speed limit raised to 65." in cues


def test_spoken_short_miles_units():
    assert _spoken_short_miles(0.2, True) == "a quarter mile"
    assert _spoken_short_miles(0.5, True) == "half a mile"
    assert _spoken_short_miles(0.5, False) == "800 meters"
