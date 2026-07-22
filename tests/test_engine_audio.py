"""Engine-audio state classifier: the contract the engine voice and the
parking/backing feature both read."""

from freight_fate.engine_audio import (
    CRUISE,
    LAUNCH,
    OFF,
    PARK_IDLE,
    READY_IDLE,
    REVERSE,
    EngineReading,
    classify,
    reading_from_truck,
)
from freight_fate.sim import TruckState


def reading(**over) -> EngineReading:
    base = dict(
        engine_on=True,
        stalled=False,
        rpm=600.0,
        throttle=0.0,
        speed_mps=0.0,
        in_reverse=False,
        in_neutral=True,
        parked_brakes_holding=True,
        air_ready=True,
    )
    base.update(over)
    return EngineReading(**base)


def test_engine_off_is_off():
    assert classify(reading(engine_on=False)).state == OFF


def test_stalled_is_off():
    assert classify(reading(stalled=True)).state == OFF


def test_parked_while_air_builds_is_park_idle_with_pressurizing():
    v = classify(reading(air_ready=False))
    assert v.state == PARK_IDLE
    assert v.pressurizing is True


def test_park_idle_flips_to_ready_idle_when_air_is_up():
    # The Josh flip: same parked truck, air now at governor release.
    v = classify(reading(air_ready=True))
    assert v.state == READY_IDLE
    assert v.pressurizing is False


def test_reverse_wins_over_idle_and_still_shows_air_fill():
    v = classify(reading(in_reverse=True, air_ready=False))
    assert v.state == REVERSE
    assert v.pressurizing is True


def test_in_gear_stopped_on_throttle_is_launch():
    v = classify(
        reading(in_neutral=False, parked_brakes_holding=False, throttle=0.5)
    )
    assert v.state == LAUNCH


def test_in_gear_stopped_off_throttle_holds_ready_idle():
    v = classify(
        reading(in_neutral=False, parked_brakes_holding=False, throttle=0.0)
    )
    assert v.state == READY_IDLE


def test_rolling_slow_in_gear_is_launch():
    v = classify(reading(in_neutral=False, parked_brakes_holding=False, speed_mps=1.5))
    assert v.state == LAUNCH


def test_rolling_up_to_speed_is_cruise():
    v = classify(reading(in_neutral=False, parked_brakes_holding=False, speed_mps=15.0))
    assert v.state == CRUISE


def test_reading_from_a_parked_truck_classifies_and_flips():
    # A freshly parked truck starts below governor release, then reaches it.
    truck = TruckState()
    truck.start_engine()
    truck.set_air_ready(parking_brake=True)  # air up, parking brake set
    v = classify(reading_from_truck(truck))
    assert v.state == READY_IDLE
    assert v.pressurizing is False
