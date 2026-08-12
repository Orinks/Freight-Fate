"""Liquid surge: the physics, the fairness, and the promise that nothing else changed.

The load-bearing test in this file is the first one. A tank load is a big
addition to the driving model, and the whole design rests on a driver hauling
anything else being unable to tell it exists.
"""

from __future__ import annotations

import math

import pytest

from freight_fate.audio import CH_SURGE
from freight_fate.models.career import ENDORSEMENT_LEVELS, Career
from freight_fate.models.cargo_condition import cargo_condition_text, cargo_fragility
from freight_fate.models.jobs import CARGO_CATALOG
from freight_fate.models.trailers import TANK_CAPACITY_TONS, trailer_keys_for_cargo
from freight_fate.sim.surge import (
    BAFFLED_MASS_MULT,
    MAX_FILL_FRACTION,
    LiquidLoad,
    fill_severity,
    lateral_accel_mps2,
    liquid_load_for,
)
from freight_fate.sim.vehicle import TruckState
from freight_fate.states.driving_core import (
    RAMP_ASSIST_FULL_DECEL_MPS2,
    RAMP_BAR_SOLID_MI,
    RAMP_BAR_TICK_RANGE_MI,
)
from freight_fate.states.driving_liquid import LiquidLoadMixin
from freight_fate.states.driving_stops import (
    assist_full_decel_mps2,
    bar_solid_zone_mi,
    bar_tick_range_mi,
)

CARGO_KG = 20_000.0


def _truck(liquid=None, speed_mps: float = 24.6) -> TruckState:
    t = TruckState()
    t.cargo_kg = CARGO_KG
    t.velocity_mps = speed_mps
    t.set_air_ready(parking_brake=False)
    t.liquid = liquid
    return t


def _roll_to_stop(truck: TruckState, brake: float = 1.0, dt: float = 0.02) -> float:
    """Brake to a standstill; returns metres travelled."""
    travelled = 0.0
    truck.throttle = 0.0
    truck.brake = brake
    for _ in range(int(120 / dt)):
        before = truck.velocity_mps
        truck.update(dt)
        travelled += max(0.0, (before + truck.velocity_mps) / 2.0) * dt
        if truck.velocity_mps <= 0.001:
            break
    return travelled


# -- the promise: other freight is untouched ---------------------------------------


def test_a_load_that_is_not_liquid_is_bit_for_bit_unchanged():
    """The whole design rests on this. No tank, no surge, no difference."""
    dry = _truck()
    assert dry.liquid is None
    assert dry.surge_force_n() == 0.0
    assert dry.surge_decel_penalty_mps2() == 0.0
    assert dry.pushed_through_by_surge() is False

    # And the trajectory itself, frame by frame, against a truck built before
    # any of this existed -- same speeds at every step.
    a, b = _truck(), _truck()
    a.brake = b.brake = 0.55
    for _ in range(400):
        a.update(0.02)
        b.update(0.02)
        assert a.velocity_mps == b.velocity_mps
    assert a.velocity_mps < 24.6


def test_only_tank_cargo_gets_a_liquid_load():
    for key in ("general", "electronics", "steel", "grain", "refrigerated"):
        assert liquid_load_for(CARGO_CATALOG[key], 20.0) is None
    assert liquid_load_for(None, 20.0) is None
    assert liquid_load_for(CARGO_CATALOG["fuel_bulk"], 13.0) is not None


def test_stopping_distance_is_unchanged_without_liquid():
    truck = _truck()
    # 24.6 m/s against the truck's own full-service figure, no surge term.
    expected = 24.6**2 / (2 * truck.full_service_decel_mps2())
    assert truck.stopping_distance_m() == pytest.approx(expected, rel=1e-9)


# -- the wave itself ---------------------------------------------------------------


def test_fill_severity_is_worst_at_half_and_vanishes_at_both_ends():
    assert fill_severity(0.5) == pytest.approx(1.0)
    assert fill_severity(0.0) == 0.0
    assert fill_severity(0.25) == pytest.approx(fill_severity(0.75))
    # A tank is never filled to the brim -- liquids expand in transit -- so
    # even a "full" load keeps a little free surface, and a little surge.
    assert 0.0 < fill_severity(1.0) < 0.2
    assert LiquidLoad(fill_fraction=1.0).fill_fraction == MAX_FILL_FRACTION


def test_baffles_shorten_the_period_and_smooth_bore_is_the_slow_heavy_one():
    smooth = LiquidLoad(fill_fraction=0.5, baffled=False)
    baffled = LiquidLoad(fill_fraction=0.5, baffled=True)
    # Rate carries the danger: the slow wave is the big one.
    assert smooth.period_s > baffled.period_s * 1.5
    assert 5.0 < smooth.period_s < 12.0
    assert baffled.period_s < 5.0
    assert baffled.slosh_mass_kg(CARGO_KG) == pytest.approx(
        smooth.slosh_mass_kg(CARGO_KG) * BAFFLED_MASS_MULT
    )


def test_baffles_do_nothing_at_all_for_lateral_surge():
    """The single most important asymmetry in the model, and the reason a
    baffled tanker still rolls over."""
    smooth = LiquidLoad(fill_fraction=0.5, baffled=False)
    baffled = LiquidLoad(fill_fraction=0.5, baffled=True)
    assert baffled.lateral.zeta == smooth.lateral.zeta
    assert baffled.lateral.omega == pytest.approx(smooth.lateral.omega)
    assert baffled.lateral.travel_m == pytest.approx(smooth.lateral.travel_m)
    assert baffled.slosh_mass_kg(CARGO_KG, lateral=True) == pytest.approx(
        smooth.slosh_mass_kg(CARGO_KG, lateral=True)
    )


def test_the_force_arrives_after_the_braking_not_with_it():
    """Surge is a lag, not a multiplier. If the shove were simultaneous it
    would just be a weaker brake; the delay is the whole hazard."""

    def trace(decel: float) -> list[float]:
        load = LiquidLoad(fill_fraction=0.5, baffled=False)
        out = []
        for step in range(400):  # 8 s; braking for the first two
            load.update(0.02, -decel if step < 100 else 0.0)
            out.append(load.force_n(CARGO_KG))
        return out

    forces = trace(4.0)
    peak = max(forces)
    peak_at = max(range(len(forces)), key=lambda i: forces[i]) * 0.02
    assert peak > 0.0
    # Essentially nothing at the moment the pedal goes down: the liquid has
    # not gone anywhere yet.
    assert forces[0] < 0.01 * peak
    assert peak_at > 0.5  # the shove is most of a second behind the pedal
    # And it keeps coming back after the driver has stopped braking.
    assert max(forces[150:]) > 0.0

    # Brake gently and the wave takes longer to arrive -- it has to travel the
    # tank either way, and a soft application does not throw it forward as
    # fast. Braking early and gently is the whole tanker technique.
    gentle = trace(1.2)
    gentle_at = max(range(len(gentle)), key=lambda i: gentle[i]) * 0.02
    assert gentle_at > peak_at
    assert max(gentle) < peak


def test_the_liquid_is_loudest_before_it_pushes_hardest():
    """The anticipation the audio layer is built on: the oscillator's velocity
    leads its displacement by a quarter period, so sonifying motion warns
    ahead of the force without predicting anything."""
    load = LiquidLoad(fill_fraction=0.5, baffled=False)
    motion, reach = [], []
    for step in range(500):
        load.update(0.02, -4.0 if step < 100 else 0.0)
        motion.append(load.longitudinal.motion)
        reach.append(load.longitudinal.reach)
    motion_peak = max(range(len(motion)), key=lambda i: motion[i])
    reach_peak = max(range(len(reach)), key=lambda i: reach[i])
    assert motion_peak < reach_peak
    lead_s = (reach_peak - motion_peak) * 0.02
    # A quarter of a seven-to-eight second period: over a second of warning.
    assert lead_s > 0.5


def test_the_wave_settles_and_says_so():
    baffled = LiquidLoad(fill_fraction=0.5, baffled=True)
    for step in range(2000):
        baffled.update(0.02, -4.0 if step < 100 else 0.0)
    assert baffled.settled


def test_a_smooth_bore_is_still_moving_long_after_a_baffled_one_has_settled():
    smooth = LiquidLoad(fill_fraction=0.5, baffled=False)
    baffled = LiquidLoad(fill_fraction=0.5, baffled=True)
    for step in range(600):  # 12 s
        drive = -4.0 if step < 100 else 0.0
        smooth.update(0.02, drive)
        baffled.update(0.02, drive)
    assert baffled.settled
    assert not smooth.settled


def test_the_wave_is_deterministic():
    """No RNG and no wall clock: an unlearnable penalty is not a skill test."""
    runs = []
    for _ in range(2):
        load = LiquidLoad(fill_fraction=0.42, baffled=False)
        trace = []
        for step in range(300):
            load.update(0.02, -3.5 if step < 90 else 0.4)
            trace.append((load.longitudinal.x, load.longitudinal.v))
        runs.append(trace)
    assert runs[0] == runs[1]


def test_a_coarse_frame_does_not_blow_up_the_oscillator():
    load = LiquidLoad(fill_fraction=0.5, baffled=False)
    for _ in range(50):
        load.update(0.5, -4.0)  # half-second frames: a stall or a resume
    assert math.isfinite(load.longitudinal.x)
    assert abs(load.longitudinal.x) <= load.longitudinal.travel_m + 1e-9


# -- what it does to the truck -----------------------------------------------------


def test_a_half_full_smooth_bore_needs_the_most_road():
    """Worst at half full, and worse than baffled at the same fill: the two
    facts every tanker manual leads with."""
    dry = _truck().stopping_distance_m()
    smooth = _truck(LiquidLoad(0.5, False)).stopping_distance_m()
    baffled = _truck(LiquidLoad(0.5, True)).stopping_distance_m()
    nearly_full = _truck(LiquidLoad(0.95, False)).stopping_distance_m()
    quarter = _truck(LiquidLoad(0.25, False)).stopping_distance_m()

    assert smooth > baffled > dry
    assert smooth > quarter > dry
    assert nearly_full < quarter
    assert 1.2 < smooth / dry < 1.6  # a third more road again, near enough


def test_braking_to_a_stop_actually_takes_longer_with_liquid_aboard():
    """Not just the estimate -- the simulated stop."""
    dry = _truck()
    wet = _truck(LiquidLoad(0.5, False))
    dry_m = _roll_to_stop(dry)
    wet_m = _roll_to_stop(wet)
    assert wet_m > dry_m


def test_the_load_pushes_a_stopped_truck_forward_when_the_brakes_come_off():
    """The lesson the CDL manuals put first: the wave can shove a stopped
    tractor out into the intersection."""
    truck = _truck(LiquidLoad(0.5, False), speed_mps=13.4)
    _roll_to_stop(truck)
    assert truck.velocity_mps == pytest.approx(0.0, abs=1e-3)
    # Off the brakes at the bar, the way a driver does when they think the
    # stop is made.
    truck.brake = 0.0
    truck.parking_brake = False
    crept = 0.0
    for _ in range(400):  # 8 s
        truck.update(0.02)
        crept += truck.velocity_mps * 0.02
    assert crept > 0.1, "the wave should still be shoving the truck along"


def test_surge_is_a_forward_push_never_a_brake():
    load = LiquidLoad(fill_fraction=0.5, baffled=False)
    truck = _truck(load)
    truck.brake = 1.0
    seen_forward = False
    for _ in range(500):
        truck.update(0.02)
        if truck.surge_force_n() > 0.0:
            seen_forward = True
    assert seen_forward


def test_a_bend_pulls_harder_the_further_over_the_advisory_you_take_it():
    at_advisory = lateral_accel_mps2(35.0, 35.0)
    over = lateral_accel_mps2(45.0, 35.0)
    assert over > at_advisory
    assert over / at_advisory == pytest.approx((45.0 / 35.0) ** 2)
    assert lateral_accel_mps2(45.0, 0.0) == 0.0  # a straight pulls nothing


def test_lateral_surge_builds_in_a_bend_taken_over_its_advisory():
    truck = _truck(LiquidLoad(0.5, False), speed_mps=20.0)
    truck.corner_advisory_mph = 30.0
    truck.throttle = 0.3
    for _ in range(200):
        truck.update(0.02)
    assert truck.liquid.lateral.reach > 0.0
    assert truck.liquid.lateral_load_factor() > 0.0


# -- fairness ----------------------------------------------------------------------


def test_being_carried_through_on_a_full_brake_application_is_not_preventable():
    truck = _truck(LiquidLoad(0.5, False), speed_mps=13.4)
    truck.brake = 1.0
    pushed = False
    for _ in range(600):
        truck.update(0.02)
        if truck.pushed_through_by_surge():
            pushed = True
            break
    assert pushed, "a hard-braking driver should be able to be pushed through"

    before = truck.preventable_damage_pct
    truck.apply_collision(0.2, preventable=not truck.pushed_through_by_surge())
    assert truck.damage_pct > 0.0
    assert truck.preventable_damage_pct == before


def test_coasting_into_a_bar_without_braking_is_still_the_drivers_fault():
    truck = _truck(LiquidLoad(0.5, False), speed_mps=13.4)
    truck.brake = 0.0
    for _ in range(200):
        truck.update(0.02)
    assert truck.pushed_through_by_surge() is False


def test_liquid_freight_is_hard_to_ruin_because_liquid_does_not_break():
    for key in ("fuel_bulk", "liquid_food"):
        assert cargo_fragility(CARGO_CATALOG[key]) < 0.5
    assert cargo_fragility(CARGO_CATALOG["electronics"]) > 2.0


def test_a_tank_load_is_described_in_words_that_fit_a_tank():
    """Diesel does not "shift but sound" and milk does not "break"."""
    assert cargo_condition_text(0.0, liquid=True) == "settled"
    assert cargo_condition_text(5.0, liquid=True) == "worked"
    assert cargo_condition_text(20.0, liquid=True) == "off spec"
    assert cargo_condition_text(40.0, liquid=True) == "contaminated"
    assert cargo_condition_text(80.0, liquid=True) == "lost"
    # And the dry-freight ladder is untouched.
    assert cargo_condition_text(0.0) == "secure"
    assert cargo_condition_text(5.0) == "shifted but sound"
    assert cargo_condition_text(80.0) == "ruined"


def test_outage_is_never_spoken():
    """Correct tanker jargon, but the game already uses the word for online
    services -- a driver hearing it mid-drive would think the site dropped."""
    for fill in (0.1, 0.3, 0.5, 0.8, 0.97):
        spoken = LiquidLoad(fill_fraction=fill).describe_fill()
        assert "outage" not in spoken.lower()
        assert "ullage" not in spoken.lower()
        assert "full" in spoken or "loaded" in spoken


# -- the freight and the licence ---------------------------------------------------


def test_tank_freight_is_gated_to_the_back_half_of_the_career():
    for key in ("fuel_bulk", "liquid_food"):
        cargo = CARGO_CATALOG[key]
        assert cargo.min_level >= 16, "tank work belongs to the back half of the arc"
        assert cargo.endorsement == "tank"
        assert cargo.tank is True
        assert trailer_keys_for_cargo(key) == ("tank",)


def test_liquid_food_is_the_harder_one_and_pays_for_it():
    """Sanitation forbids baffles in a food-grade tank, so the gentlest cargo
    in the game travels in the most vicious equipment."""
    fuel = CARGO_CATALOG["fuel_bulk"]
    milk = CARGO_CATALOG["liquid_food"]
    assert fuel.baffled is True
    assert milk.baffled is False
    assert milk.min_level > fuel.min_level
    assert milk.rate_per_mile > fuel.rate_per_mile
    # And both pay over the dry freight that shares their level band.
    assert fuel.rate_per_mile > CARGO_CATALOG["chemicals"].rate_per_mile


def test_the_tank_endorsement_unlocks_in_the_back_half():
    assert ENDORSEMENT_LEVELS["tank"] >= 16
    career = Career(xp=0.0)
    assert "tank" not in career.endorsements
    career.xp = 1_000_000.0
    assert "tank" in career.endorsements


# -- the cue layer -----------------------------------------------------------------


class _Audio:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def start_loop(self, channel, key, volume=1.0, fade_ms=0):
        self.calls.append(("loop", channel, key, volume))

    def set_loop_volume(self, channel, volume):
        self.calls.append(("vol", channel, volume))

    def stop_loop(self, channel, fade_ms=0):
        self.calls.append(("stop", channel))

    def play(self, key, volume=1.0, pan=0.0):
        self.calls.append(("play", key, volume))


class _Ctx:
    def __init__(self) -> None:
        self.audio = _Audio()
        self.said: list[str] = []

    def say_event(self, text, interrupt=True, review=True, **_pacing):
        self.said.append(text)


class _Driver(LiquidLoadMixin):
    def __init__(self, truck, terse: bool = False) -> None:
        self.truck = truck
        self.ctx = _Ctx()
        self._terse = terse

    def _terse_speech(self) -> bool:
        return self._terse


def _drive(driver, steps: int, decel: float, brake_steps: int) -> None:
    for step in range(steps):
        driver.truck.brake = 1.0 if step < brake_steps else 0.0
        driver.truck.liquid and driver.truck.liquid.update(
            0.02, -decel if step < brake_steps else 0.0
        )
        driver._update_liquid_cues(0.02)


def test_the_cue_layer_is_completely_silent_for_other_freight():
    driver = _Driver(_truck())
    _drive(driver, 400, 4.0, 100)
    assert driver.ctx.audio.calls == []
    assert driver.ctx.said == []


def test_the_wash_is_silent_on_steady_cruise_and_alive_once_the_load_runs():
    driver = _Driver(_truck(LiquidLoad(0.5, False)))
    # Steady: nothing moving, nothing sounding.
    _drive(driver, 50, 0.0, 0)
    assert driver.ctx.audio.calls == []
    # Braking: the bed comes up.
    _drive(driver, 200, 4.0, 100)
    loops = [c for c in driver.ctx.audio.calls if c[0] == "loop"]
    assert loops, "the wash should sound while the liquid is running"
    assert all(c[2] == "vehicle/liquid_wash" for c in loops)
    assert all(c[1] == CH_SURGE for c in loops)


def test_the_hit_fires_when_the_wave_arrives_and_is_the_loudest_thing_here():
    driver = _Driver(_truck(LiquidLoad(0.5, False)))
    _drive(driver, 400, 4.0, 100)
    hits = [c for c in driver.ctx.audio.calls if c[0] == "play"]
    assert hits, "the arriving wave should be a one-shot hit"
    assert any(c[1] == "vehicle/liquid_hit" for c in hits)
    loudest_hit = max(c[2] for c in hits)
    loudest_wash = max((c[3] for c in driver.ctx.audio.calls if c[0] == "loop"), default=0.0)
    assert loudest_hit > loudest_wash


def test_the_lateral_hit_has_its_own_voice():
    truck = _truck(LiquidLoad(0.5, False), speed_mps=20.0)
    truck.corner_advisory_mph = 25.0
    driver = _Driver(truck)
    for _ in range(500):
        truck.update(0.02)
        driver._update_liquid_cues(0.02)
    keys = {c[1] for c in driver.ctx.audio.calls if c[0] == "play"}
    assert "vehicle/liquid_hit_lateral" in keys


def test_the_load_running_and_the_load_settling_are_both_spoken():
    """A downward line is required: silence is otherwise ambiguous between
    "settled" and "the cue layer stopped working"."""
    for terse in (False, True):
        driver = _Driver(_truck(LiquidLoad(0.5, True)), terse=terse)
        _drive(driver, 3000, 4.0, 100)
        said = " ".join(driver.ctx.said).lower()
        assert "running forward" in said
        assert "settled" in said


def test_the_bed_is_dropped_on_the_way_out():
    driver = _Driver(_truck(LiquidLoad(0.5, False)))
    _drive(driver, 200, 4.0, 100)
    driver.ctx.audio.calls.clear()
    driver._stop_liquid_cues()
    assert ("stop", CH_SURGE) in driver.ctx.audio.calls


def test_the_status_screen_can_be_asked_what_the_tank_will_do():
    smooth = _Driver(_truck(LiquidLoad(0.5, False)))
    clause = smooth.liquid_status_clause()
    assert "smooth bore" in clause
    assert "half full" in clause
    assert "outage" not in clause.lower()
    baffled = _Driver(_truck(LiquidLoad(0.5, True)))
    assert "baffled" in baffled.liquid_status_clause()
    assert _Driver(_truck()).liquid_status_clause() == ""


# -- the stop cues now measure against what the truck can do ----------------------


def test_the_stop_bar_tick_range_is_unchanged_for_ordinary_freight():
    """The floor is the promise: a truck that stops inside the old three
    hundred feet hears the bar exactly where it always did."""
    truck = _truck(speed_mps=13.4)  # 30 mph, a normal bar approach
    assert bar_tick_range_mi(truck) == pytest.approx(RAMP_BAR_TICK_RANGE_MI)
    assert bar_solid_zone_mi(truck) == pytest.approx(RAMP_BAR_SOLID_MI)


def test_the_stop_bar_tick_starts_earlier_when_the_truck_needs_more_road():
    """A blind driver's whole model of where the bar is, is the tick's rate.
    It has to be measured against a range this truck can stop inside."""
    dry = _truck(speed_mps=24.6)
    wet = _truck(LiquidLoad(0.5, False), speed_mps=24.6)
    assert bar_tick_range_mi(wet) > bar_tick_range_mi(dry)

    # And the same is true of every other reason a truck stops long, which is
    # the point: this was owed work independent of any tank.
    icy = _truck(speed_mps=24.6)
    icy.grip = 0.3
    assert bar_tick_range_mi(icy) > bar_tick_range_mi(dry)

    downhill = _truck(speed_mps=24.6)
    downhill.grade = -0.06
    assert bar_tick_range_mi(downhill) > bar_tick_range_mi(dry)

    faded = _truck(speed_mps=24.6)
    faded.brake_temp_c = 600.0
    faded.brake_wear_pct = 90.0
    assert bar_tick_range_mi(faded) > bar_tick_range_mi(dry)


def test_the_held_tone_comes_in_early_when_sixty_feet_is_not_enough():
    close = _truck(LiquidLoad(0.5, False), speed_mps=13.4)
    assert bar_solid_zone_mi(close) > RAMP_BAR_SOLID_MI


def test_the_stopping_assist_can_only_ever_press_harder_than_it_used_to():
    for truck in (
        _truck(),
        _truck(LiquidLoad(0.5, False)),
        _truck(LiquidLoad(0.5, True)),
    ):
        assert assist_full_decel_mps2(truck) <= RAMP_ASSIST_FULL_DECEL_MPS2
        assert assist_full_decel_mps2(truck) > 0.0


def test_stopping_distance_answers_with_grade_grip_and_fade():
    level = _truck()
    base = level.stopping_distance_m()

    uphill = _truck()
    uphill.grade = 0.06
    assert uphill.stopping_distance_m() < base

    downhill = _truck()
    downhill.grade = -0.06
    assert downhill.stopping_distance_m() > base

    icy = _truck()
    icy.grip = 0.2
    assert icy.stopping_distance_m() > base

    assert _truck(speed_mps=0.0).stopping_distance_m() == 0.0
    # A reaction allowance is ground covered before the pedal moves.
    assert level.stopping_distance_m(reaction_s=1.5) == pytest.approx(base + 24.6 * 1.5)


def test_a_truck_that_cannot_out_brake_its_grade_still_returns_a_finite_number():
    runaway = _truck()
    runaway.grade = -0.5
    runaway.grip = 0.05
    runaway.brake_temp_c = 800.0
    assert math.isfinite(runaway.stopping_distance_m())
    assert runaway.stopping_distance_m() > 0.0


def test_how_full_the_tank_is_comes_from_the_load_weight():
    cargo = CARGO_CATALOG["fuel_bulk"]
    assert cargo.fill_fraction(TANK_CAPACITY_TONS / 2) == pytest.approx(0.5)
    assert cargo.fill_fraction(TANK_CAPACITY_TONS * 2) == 1.0
    assert CARGO_CATALOG["general"].fill_fraction(13.0) == 0.0
    # The same job therefore always drives the same way.
    a = liquid_load_for(cargo, 13.0)
    b = liquid_load_for(cargo, 13.0)
    assert a.fill_fraction == b.fill_fraction
    assert a.period_s == b.period_s
