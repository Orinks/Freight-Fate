def test_a_semi_out_there_is_governed_like_a_real_one():
    """NPC heavy trucks are not cars with a different pass-by clip.

    Speeds are drawn from the POSTED limit, which is right for cars -- in a
    split-limit state the cars going by a rig held to 55 really are doing the
    legal 65, and that difference is the traffic the player hears. Applied to
    a semi it put one at 75 on a 70 road, and 65 to 75 alongside a player rig
    capped at 55: a truck the player could never pass, because there was
    nothing to pass. ATRI's Operational Costs survey finds ~85 percent of
    fleets running limiters, most commonly at 65 (Brandon, 2026-08-21).
    """
    import random

    from freight_fate.sim.traffic_manager import (
        GOVERNED_CLASSES,
        GOVERNED_TRUCK_BAND_MPH,
        TrafficManager,
    )

    manager = TrafficManager.__new__(TrafficManager)
    rng = random.Random(11)
    top = GOVERNED_TRUCK_BAND_MPH[1]

    for limit in (65.0, 70.0, 75.0, 80.0):
        for intent in ("cruising", "passing", "following"):
            for vehicle_class in GOVERNED_CLASSES:
                for _ in range(60):
                    speed = manager._intent_speed(intent, limit, rng, vehicle_class)
                    assert speed <= top, (vehicle_class, intent, limit, speed)

    # A car is untouched: it still runs the posted number and then some, which
    # is what a rig held below the car limit is supposed to hear going by.
    fast = [manager._intent_speed("passing", 75.0, rng, "car") for _ in range(60)]
    assert max(fast) > top

    # And the governor is a BAND, not one number -- a road full of semis all
    # doing exactly 65 never has one slowly overtaking another.
    governed = [manager._intent_speed("cruising", 80.0, rng, "semi") for _ in range(200)]
    assert min(governed) >= GOVERNED_TRUCK_BAND_MPH[0]
    assert max(governed) - min(governed) > 2.0
