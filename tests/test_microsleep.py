"""Microsleep consequences at severe fatigue, through the driving state."""

import collections

import pygame
import pytest

from freight_fate.sim import hos
from freight_fate.states.driving import (
    MICROSLEEP_BASE_GM,
    MICROSLEEP_MIN_GM,
)


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Drowsy", current_city="Buffalo")
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
    return DrivingState(app.ctx, job, route, phase="delivery")


def _no_keys():
    return collections.defaultdict(bool)


def _keys(*pressed):
    keys = collections.defaultdict(bool)
    for key in pressed:
        keys[key] = True
    return keys


def test_microsleep_interval_shrinks_with_exhaustion():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        assert d._microsleep_interval_gm(hos.FATIGUE_SEVERE) == pytest.approx(MICROSLEEP_BASE_GM)
        assert d._microsleep_interval_gm(100.0) == pytest.approx(MICROSLEEP_MIN_GM)
        assert d._microsleep_interval_gm(95.0) < d._microsleep_interval_gm(82.0)
    finally:
        app.shutdown()


def test_microsleeps_only_strike_when_severely_fatigued_and_moving():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        # Fresh driver, or stopped: no nods however long you go.
        for _ in range(200):
            d._accrue_microsleep(1.0, moving=True, fatigue=30.0)
        assert d._microsleep_deadline is None
        for _ in range(200):
            d._accrue_microsleep(1.0, moving=False, fatigue=95.0)
        assert d._microsleep_deadline is None
        # Severely fatigued and rolling: a nod eventually comes.
        fired = False
        for _ in range(200):
            d._accrue_microsleep(1.0, moving=True, fatigue=90.0)
            if d._microsleep_deadline is not None:
                fired = True
                break
        assert fired
    finally:
        app.shutdown()


def test_reacting_to_a_microsleep_avoids_damage():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.truck.velocity_mps = 30.0
        before = d.truck.damage_pct
        d._begin_microsleep()
        assert d._microsleep_deadline is not None
        d._update_microsleep(_keys(pygame.K_DOWN), 0.1)  # brake = staying awake
        assert d._microsleep_deadline is None
        assert d.truck.damage_pct == pytest.approx(before)
        assert d._microsleep_cooldown_gm > 0.0
    finally:
        app.shutdown()


def test_ignoring_a_microsleep_drifts_off_the_road():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.truck.velocity_mps = 30.0
        before = d.truck.damage_pct
        speed_before = d.truck.speed_mph
        d._begin_microsleep()
        for _ in range(60):
            d._update_microsleep(_no_keys(), 0.1)
            if d._microsleep_deadline is None:
                break
        assert d.truck.damage_pct > before
        assert d.truck.speed_mph < speed_before  # scrubbed wandering onto the shoulder
        assert d._microsleep_misses == 1
    finally:
        app.shutdown()


def test_three_missed_microsleeps_force_a_stop():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        for _ in range(3):
            d.truck.velocity_mps = 30.0
            d._microsleep_cooldown_gm = 0.0
            d._begin_microsleep()
            for _ in range(60):
                d._update_microsleep(_no_keys(), 0.1)
                if d._microsleep_deadline is None:
                    break
        # The third drift slams the brakes and cuts throttle to force a stop.
        assert d.truck.brake == pytest.approx(1.0)
        assert d.truck.throttle == pytest.approx(0.0)
    finally:
        app.shutdown()
