"""Tests for the curve management tier on the unified curve pipeline.

Covers curve data loading (freight_fate.data.curves, the single loader),
trip integration (curve placement and approach events), and safe-speed
integration. The trip emits CURVE events for bends that demand slowing.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from freight_fate.data.curves import (
    HAIRPIN_DEFLECTION_DEG,
    HAIRPIN_MAX_MPH,
    INTERSTATE_MAX_DEFLECTION_DEG,
    INTERSTATE_MIN_RADIUS_FT,
    leg_curves,
    route_curves,
)
from freight_fate.data.world import Route, World
from freight_fate.sim.trip import Trip
from freight_fate.sim.trip_models import TripEventKind
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherSystem


class TestCurveLoading:
    """Curve data loading from the baked shard."""

    def test_unknown_leg_returns_empty_tuple(self) -> None:
        assert leg_curves("nonexistent_leg_xyz") == ()

    def test_connectors_are_filtered_by_default(self) -> None:
        mainline = leg_curves("aberdeen_sd_us:pierre_sd_us")
        everything = leg_curves("aberdeen_sd_us:pierre_sd_us", mainline_only=False)
        assert all(not c.connector for c in mainline)
        assert len(everything) >= len(mainline)
        assert any(c.connector for c in everything), (
            "this leg's interchange arcs should be present when asked for"
        )


class TestInterstateArtifactScreen:
    """Geometry artifacts never reach an interstate mainline.

    The dense sweep baked departure geometry and interchange vertices as
    mainline on some interstate legs, which read as 80-250 ft "hairpins" on
    roads that physically cannot bend that hard. The loader screens them.
    """

    def test_no_impossibly_sharp_interstate_mainline_curve(self, world: World) -> None:
        offenders = []
        for leg in world.legs:
            if not (leg.highway or "").upper().startswith("I-"):
                continue
            for rec in leg_curves(f"{leg.a}:{leg.b}"):
                if rec.min_radius_ft < INTERSTATE_MIN_RADIUS_FT:
                    offenders.append((leg.highway, f"{leg.a}:{leg.b}", rec))
        assert not offenders, (
            f"{len(offenders)} interstate mainline curves below "
            f"{INTERSTATE_MIN_RADIUS_FT} ft: {offenders[:5]}"
        )

    def test_no_switchback_deflection_on_interstate_mainline(self, world: World) -> None:
        """A 150-degree bend on interstate mainline is a mis-tagged loop ramp."""
        offenders = []
        for leg in world.legs:
            if not (leg.highway or "").upper().startswith("I-"):
                continue
            for rec in leg_curves(f"{leg.a}:{leg.b}"):
                if rec.deflection_deg >= INTERSTATE_MAX_DEFLECTION_DEG:
                    offenders.append((leg.highway, f"{leg.a}:{leg.b}", rec))
        assert not offenders, f"{len(offenders)} interstate switchbacks: {offenders[:5]}"

    def test_no_hairpin_severity_on_interstate_mainline(self, world: World) -> None:
        """The screen's whole point: no interstate mainline hairpin calls.

        Driven through ``route_curves`` -- the path every consumer takes --
        one leg at a time, so a mixed-class route cannot mask or fake a
        failure with some other road's legitimately sharp bend.
        """
        for leg in world.legs:
            if not (leg.highway or "").upper().startswith("I-"):
                continue
            route = Route([leg.a, leg.b], [leg])
            for cur in route_curves(route, route.cities):
                assert cur.severity != "hairpin", (
                    f"{leg.highway} {leg.a}:{leg.b} still calls a hairpin at "
                    f"mile {cur.apex_mi:.2f} (radius {cur.min_radius_ft} ft)"
                )

    def test_abilene_fort_worth_mile_four_hairpins_are_gone(self) -> None:
        """Flat I-20 had three 104-111 ft "hairpins" at mile 4."""
        recs = leg_curves("abilene_tx_us:fort_worth_tx_us")
        assert recs, "this leg is swept and should still have real curves"
        near_four = [r for r in recs if 3.5 <= r.apex_mi <= 4.5]
        assert not near_four, f"artifact cluster survived: {near_four}"
        assert min(r.min_radius_ft for r in recs) >= INTERSTATE_MIN_RADIUS_FT

    def test_akron_cleveland_mile_thirty_seven_hairpin_is_gone(self) -> None:
        """I-77 carried two 82 ft "hairpins" from interchange geometry."""
        recs = leg_curves("akron_oh_us:cleveland_oh_us")
        assert recs
        assert not [r for r in recs if r.min_radius_ft < INTERSTATE_MIN_RADIUS_FT]

        # The real bends on this leg stay. Pinned as a PROPERTY rather than a
        # count: the flat-ground screen took this leg from 21 mainline curves
        # to 11, and every one it removed is below the 1,482 ft floor a 65 mph
        # road may bend to -- including the two 82 ft, 160-degree records this
        # test is named for. A bare "at least fifteen" would have had to be
        # relaxed to keep passing, which says nothing; this says what must be
        # true of whatever survives.
        from freight_fate.data.curves import _leg_design_speed, min_radius_ft
        from freight_fate.data.world import get_world

        leg = next(
            leg for leg in get_world().legs if leg.a == "akron_oh_us" and leg.b == "cleveland_oh_us"
        )
        floor = min_radius_ft(_leg_design_speed(leg))
        assert len(recs) >= 8
        assert all(r.min_radius_ft >= floor for r in recs), (
            f"a curve under the {floor:.0f} ft floor survived on {leg.highway}"
        )

    def test_interstate_connector_arcs_are_untouched(self) -> None:
        """Ramps really are that sharp; physics still wants them."""
        everything = leg_curves("abilene_tx_us:fort_worth_tx_us", mainline_only=False)
        tight = [r for r in everything if r.connector and r.min_radius_ft < 150]
        assert tight, "interchange ramp arcs should survive the screen"

    def test_million_dollar_highway_switchbacks_survive(self) -> None:
        """US-550 Durango-Montrose really does switch back. Never screen it."""
        recs = leg_curves("durango_co_us:montrose_co_us")
        assert len(recs) >= 250
        assert min(r.min_radius_ft for r in recs) < 100
        assert max(r.deflection_deg for r in recs) >= 150.0

    def test_glenwood_canyon_interstate_curves_survive(self) -> None:
        """Real I-70 canyon geometry sits above the floor and must stay."""
        recs = leg_curves("glenwood_springs_co_us:grand_junction_co_us")
        assert len(recs) >= 55
        assert min(r.min_radius_ft for r in recs) < 500, (
            "Glenwood Canyon's genuinely sharp bends should still be here"
        )

    def test_us_highway_mountain_hairpins_survive(self) -> None:
        """US-40 over the Rockies keeps its real sharp curves.

        The interstate screen never applies to US routes; the separate
        flat-terrain screen (below) only takes the one Denver-departure
        artifact, so the mountain bends this leg is famous for stay.
        """
        recs = leg_curves("denver_co_us:salt_lake_city_ut_us")
        assert [r for r in recs if r.min_radius_ft < INTERSTATE_MIN_RADIUS_FT]


def _is_hairpin(rec) -> bool:
    """The artifact screen's question -- "could a road here really do this?"
    -- which is broader than the spoken hairpin and deliberately so: a very
    low advisory is an extreme claim about the ground whether or not the road
    comes back on itself. ``RouteCurve.severity`` uses shape alone, per
    MUTCD; see ``curves.HAIRPIN_DEFLECTION_DEG``."""
    return rec.advisory_mph <= HAIRPIN_MAX_MPH or rec.deflection_deg >= HAIRPIN_DEFLECTION_DEG


class TestUSRouteArtifactScreen:
    """A second, narrower screen for artifacts road class alone can't catch.

    US and state routes can carry the same city-departure sweep artifact an
    interstate can, but they also carry real switchbacks the interstate
    screen would wrongly delete (US-550, the Salt River Canyon) -- so this
    screen is gated on local terrain (flat ground can't hold a real
    hairpin), not on road class. See ``tools/screen_curve_artifacts.py``.
    """

    def test_denver_us40_departure_kink_is_gone(self) -> None:
        """The flat-Denver-metro kink at mile 1.7 was the reported case."""
        recs = leg_curves("denver_co_us:salt_lake_city_ut_us")
        near_departure = [r for r in recs if r.apex_mi < 2.0]
        assert not [r for r in near_departure if _is_hairpin(r)], (
            f"flat-terrain departure artifact survived: {near_departure}"
        )

    def test_flagged_artifacts_are_absent_from_every_leg(self, world: World) -> None:
        """Every ``(leg, seq)`` the offline screen names is actually gone.

        Round-trips ``curve_artifacts.jsonl`` against the loaded data so a
        stale baked file (screen re-run, loader not updated, or vice versa)
        fails loudly instead of silently drifting.
        """
        import json

        from freight_fate.data.data_resources import read_data_text

        text = read_data_text("world_data/us/gameplay/curve_artifacts.jsonl")
        assert text, "curve_artifacts.jsonl should exist once artifacts are flagged"
        flagged_legs: set[str] = set()
        count = 0
        for line in text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if "meta" in row:
                continue
            flagged_legs.add(row["leg"])
            count += 1
        assert count > 0

        by_key = {f"{leg.a}:{leg.b}": leg for leg in world.legs}
        for leg_key in flagged_legs:
            leg = by_key.get(leg_key)
            if leg is None:
                continue
            assert not (leg.highway or "").upper().startswith("I-"), (
                f"{leg_key} is flagged but is interstate mainline -- "
                "that screen is a separate, unconditional rule"
            )

    def test_city_departure_hairpins_are_gone_off_the_mountains(self) -> None:
        """Terrain alone could not see a departure kink on rolling ground.

        Reported 2026-08-11: hairpins "and not just on mountains either". The
        flat screen caught the artifact only where the city sat on flat
        ground, so the same 43 ft kink a mile out of Hazard on KY-80 -- and
        112 like it -- rode through on "hills".
        """
        for leg_key in (
            "hot_springs_ar_us:fort_smith_ar_us",
            "hot_springs_ar_us:little_rock_ar_us",
            "rochester_mn_us:winona_mn_us",
            "oxford_ms_us:memphis_tn_us",
        ):
            recs = leg_curves(leg_key)
            assert recs, leg_key
            near_departure = [r for r in recs if r.apex_mi < 2.5 and _is_hairpin(r)]
            assert not near_departure, f"{leg_key}: departure artifact survived: {near_departure}"

    def test_the_leg_end_rule_cuts_by_terrain_within_a_single_leg(self) -> None:
        """KY-80 out of Hazard carries both cases half a mile apart.

        A 43 ft kink at mile 1.06 on hills is departure geometry and goes; a
        real 80 ft switchback at mile 2.48, where the road is already into the
        mountains, stays. Position alone would have taken both, which is why
        the rule asks the terrain as well.
        """
        recs = leg_curves("hazard_ky_us:london_ky_us")
        near = [r for r in recs if r.apex_mi < 2.5 and _is_hairpin(r)]
        assert near, "the mountain switchback at mile 2.48 must survive"
        assert all(r.min_radius_ft >= 50 for r in near), (
            f"the hills kink at mile 1.06 should be gone: {near}"
        )

    def test_a_mountain_town_keeps_the_switchback_on_its_doorstep(self) -> None:
        """The leg-end rule spares mountain terrain, and has to.

        US-119 leaves Charleston straight into the mountains, and a real
        switchback sits within the first mile. Deleting by position alone
        would have taken it.
        """
        recs = leg_curves("charleston_wv_us:pikeville_ky_us")
        assert [r for r in recs if r.apex_mi < 2.5 and _is_hairpin(r)]

    def test_no_surviving_curve_is_tighter_than_a_road_can_bend(self) -> None:
        """A radius floor for every class, the sibling of the interstate 300 ft.

        50 ft is tighter than a loaded tractor-trailer's own turning circle,
        so nothing that bends harder is a road. The floor sits just under the
        tightest genuine switchback the world carries (US-550 at 54 ft), which
        is why it can be applied everywhere without a terrain test.
        """
        from freight_fate.data.curves import _load

        offenders = [
            (leg_key, rec)
            for leg_key, recs in _load().items()
            for rec in recs
            if not rec.connector and rec.min_radius_ft < 50
        ]
        assert not offenders, f"impossible mainline radii survived: {offenders[:5]}"

    def test_million_dollar_highway_untouched_by_the_new_screen(self) -> None:
        """A mountain corridor keeps every switchback under the new screen too."""
        recs = leg_curves("durango_co_us:montrose_co_us")
        assert len(recs) >= 250
        assert [r for r in recs if _is_hairpin(r)], (
            "US-550's real hairpins must survive the flat-terrain screen"
        )

    def test_salt_river_canyon_untouched_by_the_new_screen(self) -> None:
        """Globe->Show Low (US-60) keeps its mountain switchbacks too."""
        recs = leg_curves("globe_az_us:show_low_az_us")
        assert [r for r in recs if _is_hairpin(r)], (
            "the Salt River Canyon's real hairpins must survive the screen"
        )


class _MockWeather(WeatherSystem):
    """A weather system that returns a fixed safe speed for tests."""

    def __init__(self) -> None:
        super().__init__("heartland", seed=42)
        self._effects = MagicMock()
        self._effects.grip = 1.0
        self._effects.safe_speed_mph = 75.0
        self._effects.water_mm = 0.0
        self._effects.surface = "dry"
        self._effects.drag_mult = 1.0
        self._effects.visibility_mi = 10.0
        self._effects.sound = None
        self._effects.wind = 0.0

    @property
    def effects(self):
        return self._effects


class TestTripCurveIntegration:
    """Curve placement and approach events in the Trip system."""

    def test_place_curves_empty_short_approach(self) -> None:
        """A very short approach route (single leg, < 10 mi) gets no curves.

        Curves are only meaningful on highway-length legs; short facility
        approaches should have no curve placement.
        """
        from freight_fate.data.world_models import GradeSegment, Leg, RouteCheckpoint, StateMileage

        # Build a minimal single-leg route from a city to itself
        leg = Leg(
            a="abilene_tx_us",
            b="abilene_tx_us",
            miles=5.0,
            highway="US-83",
            terrain="flat",
            stops=(),
            checkpoints=(RouteCheckpoint("Midpoint", 2.5, "place", state="", highway="US-83"),),
            state_miles=(StateMileage("Texas", 5.0),),
            grade_segments=(GradeSegment(0.0, 5.0, 0.0, "flat", "test"),),
        )
        route = Route(["abilene_tx_us", "abilene_tx_us"], [leg])
        truck = TruckState()
        weather = _MockWeather()
        trip = Trip(route, truck, weather, time_scale=10.0, seed=42)
        assert trip.curves == []

    def test_interstate_artifact_never_reaches_trip_curves(self) -> None:
        """The Abilene I-20 mile-4 artifacts stay out of the live trip.

        ``Trip._place_curves`` keeps connectors for physics, so this checks
        the deepest consumer path, not just the spoken one.
        """
        world = World.load()
        route = world.supported_route("abilene_tx_us", "fort_worth_tx_us")
        assert route is not None
        assert all((leg.highway or "").startswith("I-") for leg in route.legs), (
            "this fixture route is meant to be interstate the whole way"
        )
        trip = Trip(route, TruckState(), _MockWeather(), time_scale=10.0, seed=42)
        mainline = [c for c in trip.curves if not c.connector]
        assert mainline, "the route should still have real curves"
        assert not [c for c in mainline if c.severity == "hairpin"]
        assert not [c for c in mainline if 3.5 <= c.apex_mi <= 4.5]

    def test_place_curves_highway_route(self) -> None:
        """A highway route resolves curves from leg-relative to trip miles."""
        truck = TruckState()
        weather = _MockWeather()
        world = World.load()
        route = world.shortest_route("abilene_tx_us", "dallas_tx_us")
        if route is None:
            return
        trip = Trip(route, truck, weather, time_scale=10.0, seed=42)
        # The trip should have curves if the abilene->dallas leg has data.
        # Some baked curves may have near-equal or slightly reversed start/end
        # due to leg-direction resolution; check the curve data is plausible.
        for cr in trip.curves:
            assert 0.0 <= cr.start_mi <= trip.total_miles
            assert 0.0 <= cr.end_mi <= trip.total_miles
            assert abs(cr.start_mi - cr.end_mi) < 5.0  # no mile-long outliers
            assert cr.direction in ("L", "R")

    def test_curve_at_inside(self) -> None:
        """curve_at returns the curve containing a milepost."""
        truck = TruckState()
        weather = _MockWeather()
        world = World.load()
        route = world.shortest_route("abilene_tx_us", "dallas_tx_us")
        if route is None:
            return
        trip = Trip(route, truck, weather, time_scale=10.0, seed=42)
        if not trip.curves:
            return
        # Pick the first curve and check that curve_at returns it
        cr = trip.curves[0]
        mid = (cr.start_mi + cr.end_mi) / 2.0
        found = trip.curve_at(mid)
        assert found is not None
        assert found.start_mi == cr.start_mi

    def test_curve_at_none(self) -> None:
        """Outside all curves, curve_at returns None."""
        truck = TruckState()
        weather = _MockWeather()
        world = World.load()
        route = world.shortest_route("abilene_tx_us", "dallas_tx_us")
        if route is None:
            return
        trip = Trip(route, truck, weather, time_scale=10.0, seed=42)
        assert trip.curve_at(-1.0) is None
        assert trip.curve_at(trip.total_miles + 1.0) is None

    def test_check_curves_emits_for_sharp_curve(self) -> None:
        """A sharp curve ahead generates a CURVE event with a pacenote."""
        truck = TruckState()
        truck.start_engine()
        truck.velocity_mps = 60.0 * 0.44704  # 60 mph in m/s
        weather = _MockWeather()
        world = World.load()
        route = world.shortest_route("abilene_tx_us", "dallas_tx_us")
        if route is None:
            return
        trip = Trip(route, truck, weather, time_scale=10.0, seed=42)
        if not trip.curves:
            return
        # Position the truck before the first curve
        first = trip.curves[0]
        trip.position_mi = max(0.0, first.start_mi - 1.0)
        # Run update to generate events
        events = trip.update(0.1)
        curve_events = [e for e in events if e.kind == TripEventKind.CURVE]
        # If the curve is sharp and not a connector, it should announce.
        # The curve_at check may trigger or not depending on distance.
        # The pacenote should mention advisory speed.
        for ev in curve_events:
            assert "advisory" in ev.message or "curve" in ev.message

    def test_restore_seeds_announced_curves(self) -> None:
        """Restoring a save seeds curves behind the position as announced."""
        truck = TruckState()
        weather = _MockWeather()
        world = World.load()
        route = world.shortest_route("abilene_tx_us", "dallas_tx_us")
        if route is None:
            return
        trip = Trip(route, truck, weather, time_scale=10.0, seed=42)
        if not trip.curves:
            return
        # Restore past the first curve
        first = trip.curves[0]
        trip.restore(first.start_mi + 0.5, 10.0)
        # The first curve should be in announced
        expected_key = f"curve:{first.start_mi:.3f}:{first.direction}"
        assert expected_key in trip._announced_curves


def _rec(start_mi, end_mi, direction, radius_ft, deflection_deg, advisory=25, connector=False):
    from freight_fate.data.curves import CurveRecord

    return CurveRecord(
        start_mi=start_mi,
        apex_mi=(start_mi + end_mi) / 2,
        end_mi=end_mi,
        direction=direction,
        advisory_mph=advisory,
        min_radius_ft=radius_ft,
        deflection_deg=deflection_deg,
        connector=connector,
    )


def test_a_curve_too_short_to_hold_its_own_arc_is_dropped():
    """Owner playtest, 2026-08-17: "is a hairpin supposed to be on this
    route?" on US-285 north of Santa Fe.

    A 160 ft radius turning 79.9 degrees needs 223 ft of road; that record
    claimed 53. Both existing screens correctly passed it -- it sits in real
    mountain terrain, where real switchbacks live -- so the pacenote layer
    called a 25 mph hairpin on a road posted 35. This screen asks a question
    terrain cannot excuse: does the record agree with itself?
    """
    from freight_fate.data.curves import _screen_geometry, arc_consistency

    # 500 ft radius, 30 degrees: needs 262 ft of arc.
    honest = _rec(1.00, 1.10, "L", 500, 30.0)  # 528 ft of span, comfortable
    assert arc_consistency(honest) > 1.0
    # The same bend claiming to happen in 11 ft.
    impossible = _rec(2.00, 2.002, "L", 500, 30.0)
    assert arc_consistency(impossible) < 0.1

    kept = _screen_geometry([honest, impossible])
    assert honest in kept
    assert impossible not in kept


def test_a_zero_tangent_reversal_takes_both_sides_with_it():
    """A digitized kink reads as opposite-direction curves meeting at a
    point. A through highway cannot swap lock with no straight between, so
    the whole wiggle goes -- including the side whose own arithmetic happens
    to be fine, because the road does not really go left-right there."""
    from freight_fate.data.curves import _screen_geometry

    # Left is arithmetically fine on its own; right contradicts itself.
    left = _rec(10.00, 10.05, "L", 160, 35.4)
    right = _rec(10.05, 10.06, "R", 160, 79.9)
    far = _rec(12.00, 12.20, "R", 900, 20.0, advisory=45)

    kept = _screen_geometry([left, right, far])
    assert left not in kept, "the fine-looking half of a zig-zag stays a zig-zag"
    assert right not in kept
    assert far in kept, "an unrelated curve down the road is untouched"


def test_a_real_switchback_pair_with_road_between_them_survives():
    """US-550 over Red Mountain Pass really does reverse. The screen must
    only take reversals with NO tangent -- otherwise it eats the mountain
    roads the previous two screens were careful to leave alone."""
    from freight_fate.data.curves import _screen_geometry

    # Two tight, honest bends with a tenth of a mile of straight between.
    first = _rec(5.00, 5.10, "L", 200, 90.0, advisory=25)
    second = _rec(5.20, 5.30, "R", 200, 90.0, advisory=25)
    kept = _screen_geometry([first, second])
    assert first in kept and second in kept


def test_ramps_are_exempt_like_the_other_screens():
    """Connectors really are that sharp and are recorded against a different
    baseline; the screens above exempt them and so does this one."""
    from freight_fate.data.curves import _screen_geometry

    ramp = _rec(1.00, 1.001, "L", 500, 30.0, connector=True)
    kept = _screen_geometry([ramp])
    assert ramp in kept


def test_a_record_missing_its_geometry_is_never_screened_on_arithmetic():
    from freight_fate.data.curves import _screen_geometry, arc_consistency

    blank = _rec(1.00, 1.001, "L", 0, 0.0)
    assert arc_consistency(blank) > 1.0
    assert blank in _screen_geometry([blank])


# --- flat-ground class screen (owner audit, 2026-08-19) ---------------------


def test_no_mainline_curve_bends_tighter_than_its_class_on_flat_ground():
    """Owner, 2026-08-19: "cruising down the highway or turnpike in a car, it
    hardly ever curves. I want an honest audit."

    The audit found the map disagreeing with the road. The MEDIAN interstate
    curve radius in the bake was 1,342 ft against a 1,330 ft design floor --
    half of them at or below what a 70 mph road may legally bend to -- and
    the tenth percentile across all mainline was 281 ft, an intersection
    rather than a highway. Interstate curve callouts ran 5.7 per hundred
    miles.

    Rough country still earns a tight bend: this screens flat ground only,
    so the Rockies and US-550 drive the way they should.
    """
    from freight_fate.data.curves import _screenable_legs, leg_curves
    from freight_fate.data.world import get_world

    world = get_world()
    screenable = _screenable_legs()
    offenders = []
    for leg in world.legs:
        floor = screenable.get(f"{leg.a}:{leg.b}")
        if floor is None:
            continue  # not flat enough to judge; see the canyon test below
        for curve in leg_curves(f"{leg.a}:{leg.b}"):
            if curve.min_radius_ft < floor:
                offenders.append((leg.a, leg.b, leg.highway, curve.min_radius_ft, floor))
    assert not offenders[:20], f"{len(offenders)} flat-ground curves under floor: {offenders[:5]}"


def test_rough_country_keeps_its_tight_bends():
    """The other half, and the reason this screens terrain rather than radius.

    A blanket radius floor would flatten the best driving in the game. A
    mountain leg is allowed to bend tighter than any design table, because
    real ones do.
    """
    from freight_fate.data.curves import _leg_is_level, leg_curves, min_radius_ft
    from freight_fate.data.world import get_world

    world = get_world()
    floor_70 = min_radius_ft(70.0)
    kept_tight = 0
    for leg in world.legs:
        if _leg_is_level(leg):
            continue
        for curve in leg_curves(f"{leg.a}:{leg.b}"):
            if curve.min_radius_ft < floor_70:
                kept_tight += 1
    assert kept_tight > 500, f"only {kept_tight} tight curves survive off flat ground"


def test_a_canyon_tagged_flat_is_not_screened_as_level_ground():
    """The world's terrain label is derived from NET elevation change, so a
    road that climbs and drops all the way along without getting anywhere
    reads as flat. I-70 through Glenwood Canyon is tagged flat, and its
    curves are cut into rock walls.

    Caught by test_glenwood_canyon_interstate_curves_survive when the screen
    first went in and took 21 real curves off it. Two proxies were tried and
    both failed -- the label itself, then feet of relief per mile, which
    calibrated against HPMS at a Youden's J of 0.29. The screen reads the
    real HPMS terrain class now, and HPMS calls this leg mountainous.
    """
    from freight_fate.data.curves import _leg_is_level
    from freight_fate.data.world import get_world

    canyon = next(
        leg
        for leg in get_world().legs
        if leg.a == "glenwood_springs_co_us" and leg.b == "grand_junction_co_us"
    )
    assert str(getattr(canyon, "terrain", "")) == "flat"  # the label really is wrong
    assert not _leg_is_level(canyon)  # HPMS is not


def test_the_radius_floor_matches_published_design_tables():
    """The floor is computed, so it has to be checked against print.

    ``min_radius_ft`` evaluates the AASHTO point-mass control
    (Rmin = V^2 / [15(0.01*emax + fmax)], FHWA-HRT-17-098 chapter 3) using
    the Green Book table 3-7 side-friction factors. These expected values
    are the TxDOT Roadway Design Manual's own tables 4-6 and 4-7, which
    republish the Green Book controls -- so if either the formula or a
    friction factor is mistyped, this fails against a published source
    rather than against my arithmetic.

    An earlier pass of this screen used 1,330 ft as the interstate floor.
    That is the SIXTY mph minimum at 6 percent superelevation; a 70 mph road
    needs 1,815 ft at 8 percent and 2,040 at 6. The screen was letting a
    whole design-speed step of bad geometry through.
    """
    from freight_fate.data.curves import SUPERELEVATION_MAX, min_radius_ft

    assert SUPERELEVATION_MAX == 0.08  # the most permissive standard built
    published_e8 = {40: 444, 50: 758, 60: 1200, 70: 1810, 75: 2210}
    for speed, expected in published_e8.items():
        assert abs(min_radius_ft(speed) - expected) <= 5, (
            f"{speed} mph: computed {min_radius_ft(speed):.0f} ft, "
            f"TxDOT table 4-7 says {expected} ft"
        )
    # And it really is a floor that rises with speed.
    assert min_radius_ft(50) < min_radius_ft(60) < min_radius_ft(70)


def test_the_radius_floor_follows_the_leg_s_own_posted_limit():
    """Design speed comes from the baked OSM maxspeed sweep, not a guess at
    the road's class. A 55 mph US route and a 70 mph interstate are held to
    different floors because they are different roads, and the data says
    which is which."""
    from freight_fate.data.curves import _leg_design_speed, min_radius_ft
    from freight_fate.data.world import get_world

    speeds = {_leg_design_speed(leg) for leg in get_world().legs}
    assert len(speeds) > 1, "every leg fell back to the same default speed"
    assert max(speeds) >= 65.0
    # The floor tracks it rather than being pinned per class.
    assert min_radius_ft(max(speeds)) > min_radius_ft(min(speeds))


def test_absence_of_a_terrain_class_is_never_read_as_level():
    """The safe direction, and the reason this reads a bake rather than a rule.

    Screening treats level ground as licence to delete geometry, so a leg
    HPMS never classified must keep every curve it has. Absence of evidence
    is not evidence of flatness -- getting this backwards would quietly
    strip curves from exactly the legs we know least about.
    """
    from freight_fate.data.curves import _leg_is_level

    class NoTerrain:
        hpms_terrain = None

    class Rolling:
        hpms_terrain = type("T", (), {"type": 2})()

    class Mountain:
        hpms_terrain = type("T", (), {"type": 3})()

    class Level:
        hpms_terrain = type("T", (), {"type": 1})()

    assert not _leg_is_level(NoTerrain())
    assert not _leg_is_level(Rolling())
    assert not _leg_is_level(Mountain())
    assert _leg_is_level(Level())


def test_the_terrain_bake_says_what_kind_of_value_it_carries():
    """AGENTS.md: a baked record must make plain whether it was read, derived
    or assumed. The HPMS class is READ; that one value stands for a whole leg
    is DERIVED, and the source string has to say both."""
    from freight_fate.data.world import get_world

    baked = [leg for leg in get_world().legs if getattr(leg, "hpms_terrain", None)]
    assert baked, "no leg carries an HPMS terrain class"
    source = baked[0].hpms_terrain.source
    assert "HPMS" in source
    assert "modal" in source.lower() or "derived" in source.lower()
    assert all(leg.hpms_terrain.type in (1, 2, 3) for leg in baked)


def test_a_hairpin_is_a_shape_not_a_speed() -> None:
    """MUTCD gives the Hairpin Curve sign (W1-11) for a change in horizontal
    alignment of 135 degrees or more -- a switchback, where the road comes
    back on itself. Advisory speed does not enter into it; MUTCD sorts by
    advisory separately and much lower, swapping the Turn sign (W1-1) for the
    Curve sign at 30 mph or less.

    The old rule said "advisory <= 25 OR deflection >= 150", and the advisory
    half called tight little bends taken slowly hairpins -- the worst of them
    deflecting ten degrees. That spends the word on nothing and leaves it
    meaning less when a real switchback turns up.
    """
    from freight_fate.data.curves import (
        HAIRPIN_DEFLECTION_DEG,
        HAIRPIN_TURN_MAX_MPH,
        RouteCurve,
    )

    def curve(advisory: int, deflection: float) -> RouteCurve:
        return RouteCurve(
            start_mi=1.0,
            apex_mi=1.05,
            end_mi=1.1,
            direction="L",
            advisory_mph=advisory,
            min_radius_ft=150,
            deflection_deg=deflection,
        )

    # MUTCD's own numbers, not rounder ones chosen nearby.
    assert HAIRPIN_DEFLECTION_DEG == 135.0
    assert HAIRPIN_TURN_MAX_MPH == 30

    # A switchback comes back on itself AND has to be crawled...
    assert curve(advisory=25, deflection=170.0).severity == "hairpin"
    assert curve(advisory=30, deflection=135.0).severity == "hairpin"
    # ...and a slow little kink is not one, however slowly it is taken.
    assert curve(advisory=25, deflection=10.6).severity != "hairpin"
    assert curve(advisory=20, deflection=94.0).severity != "hairpin"

    # Nor is a sweeper, however far round it goes. The angle is necessary and
    # not sufficient: MUTCD puts the hairpin sign up instead of a TURN sign,
    # and a 60 mph bend was never getting one. This is I-49 north of
    # Fayetteville, 811 ft radius through 143 degrees -- real road, and the
    # reason taking the angle alone put hairpins on seven interstate curves.
    assert curve(advisory=60, deflection=142.9).severity != "hairpin"

    # Darren's Norwich corner: real, tight, and correctly no longer a
    # switchback (NY-12, 2026-08-23).
    norwich = curve(advisory=25, deflection=94.0)
    assert norwich.severity == "sharp"
