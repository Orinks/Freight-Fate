"""Freight market drift, determinism, and job pay integration."""

from freight_fate.models.jobs import JobBoard
from freight_fate.models.market import (
    MARKET_CARGO_KEYS,
    MARKET_MAX,
    MARKET_MIN,
    Market,
    market_condition,
)
from freight_fate.models.profile import Profile


def assert_in_bounds(market: Market) -> None:
    for key, mult in market.multipliers.items():
        assert MARKET_MIN <= mult <= MARKET_MAX, (key, mult)


def test_initial_multipliers_cover_all_cargo_classes():
    m = Market(seed=42)
    assert set(m.multipliers) == set(MARKET_CARGO_KEYS)
    assert_in_bounds(m)


def test_drift_stays_within_bounds_over_a_long_career():
    m = Market(seed=7)
    m.advance_to(400)
    assert m.day == 400
    assert_in_bounds(m)


def test_drift_is_deterministic_stepwise_vs_jump():
    a = Market(seed=99)
    b = Market(seed=99)
    for day in range(1, 31):
        a.advance_to(day)
    b.advance_to(30)
    assert a.multipliers == b.multipliers
    assert a.day == b.day == 30


def test_different_seeds_diverge():
    a = Market(seed=1)
    b = Market(seed=2)
    a.advance_to(10)
    b.advance_to(10)
    assert a.multipliers != b.multipliers


def test_advance_reports_whether_anything_changed():
    m = Market(seed=5)
    assert m.advance_to(0) is False
    assert m.advance_to(2) is True
    assert m.advance_to(2) is False


def test_market_condition_labels():
    assert market_condition(1.3) == "tight"
    assert market_condition(1.1) == "tight"
    assert market_condition(1.0) == "steady"
    assert market_condition(0.95) == "loose"
    assert market_condition(0.8) == "loose"


def test_summary_names_the_standouts():
    m = Market(seed=1)
    m.multipliers["electronics"] = 1.3
    m.multipliers["bulk"] = 0.8
    summary = m.summary()
    assert "electronics tight" in summary
    assert "bulk loose" in summary


def test_job_pay_scales_with_market(world):
    tight = Market(seed=0)
    tight.multipliers = {k: 1.3 for k in MARKET_CARGO_KEYS}
    loose = Market(seed=0)
    loose.multipliers = {k: 0.8 for k in MARKET_CARGO_KEYS}
    # identical board seeds generate the same jobs, so pay isolates the market
    jobs_tight = JobBoard(world, seed=11).offers("Chicago", set(), market=tight)
    jobs_loose = JobBoard(world, seed=11).offers("Chicago", set(), market=loose)
    assert jobs_tight and len(jobs_tight) == len(jobs_loose)
    for jh, jc in zip(jobs_tight, jobs_loose, strict=True):
        assert jh.cargo.key == jc.cargo.key
        assert abs(jh.pay / jc.pay - 1.3 / 0.8) < 0.01
        assert "Market is tight." in jh.describe()
        assert "Market is loose." in jc.describe()


def test_steady_market_is_not_called_out_per_job(world):
    steady = Market(seed=0)
    steady.multipliers = {k: 1.0 for k in MARKET_CARGO_KEYS}
    jobs = JobBoard(world, seed=11).offers("Chicago", set(), market=steady)
    assert jobs
    assert all("Market is" not in j.describe() for j in jobs)


def test_profile_persists_market_state():
    p = Profile(name="Market Test")
    p.market.advance_to(5)
    snapshot = dict(p.market.multipliers)
    path = p.save()
    loaded = Profile.load(path)
    assert loaded.market.seed == p.market.seed
    assert loaded.market.day == 5
    assert loaded.market.multipliers == snapshot
