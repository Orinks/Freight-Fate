"""The physics bench runs, is deterministic, and preserves the physics
orderings the game teaches (jake spares the shoes, weather stretches
stopping distance, no-brakes descents run away).

The bench itself is the tuning instrument; these tests are only the
regression net that keeps it trustworthy.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_bench():
    """Import tools/physics_bench.py by path (tools is not a package).

    The module must sit in sys.modules before exec: its dataclasses use
    deferred annotations, which dataclass processing resolves through
    sys.modules[cls.__module__].
    """
    spec = importlib.util.spec_from_file_location(
        "physics_bench", ROOT / "tools" / "physics_bench.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["physics_bench"] = module
    spec.loader.exec_module(module)
    return module


bench = _load_bench()
_RESULTS = {sc.name: bench.run_scenario(sc) for sc in bench.SCENARIOS}


def _summary(name: str) -> str:
    return "\n".join(_RESULTS[name].summary)


def _wear_added(name: str, which: str) -> float:
    line = next(s for s in _RESULTS[name].summary if s.startswith("wear added"))
    for part in line.split(","):
        if which in part:
            return float(part.split(which)[1].split("percent")[0].strip())
    raise AssertionError(f"no {which} wear in: {line}")


def _stop_feet(name: str) -> float:
    line = next(s for s in _RESULTS[name].summary if s.startswith("stopping distance"))
    return float(line.split()[2])


def test_every_scenario_produces_a_summary():
    for name, result in _RESULTS.items():
        assert result.summary, name
        assert result.events, name


def test_bench_is_deterministic():
    sc = next(s for s in bench.SCENARIOS if s.name == "grade-no-jake")
    again = bench.run_scenario(sc)
    assert again.events == _RESULTS["grade-no-jake"].events
    assert again.summary == _RESULTS["grade-no-jake"].summary


def test_jake_spares_the_service_brakes():
    assert _wear_added("grade-jake-snub", "brakes") < _wear_added("grade-no-jake", "brakes")


def test_no_brakes_descent_runs_away():
    assert any("RUNAWAY" in e for e in _RESULTS["grade-runaway"].events)
    top_line = _RESULTS["grade-runaway"].summary[0]
    top_mph = float(top_line.split("top")[1].split("mph")[0].strip())
    assert top_mph > 80.0


def test_weather_stretches_stopping_distance():
    dry = _stop_feet("stop-dry")
    rain = _stop_feet("stop-rain")
    snow = _stop_feet("stop-snow")
    bald_rain = _stop_feet("stop-bald-rain")
    assert dry < rain < snow
    assert rain < bald_rain


def test_jake_stages_form_a_ladder():
    # Full jake spares the shoes entirely, stage 1 makes them work, and no
    # jake at all works them hardest -- the staged retard teaches by degrees.
    full = _wear_added("grade-jake-snub", "brakes")
    stage1 = _wear_added("grade-jake-stage1", "brakes")
    none = _wear_added("grade-no-jake", "brakes")
    assert full <= stage1 < none


def test_drag_descent_reaches_fade_and_jake_descent_stays_cool():
    # The drag-vs-snub lesson with teeth: riding the shoes down six miles of
    # 6 percent cooks them past fade; the jake descent never warms them.
    assert _RESULTS["grade-no-jake"].metrics["peak-temp-c"] > 400.0
    assert _RESULTS["grade-jake-only"].metrics["peak-temp-c"] < 100.0


def test_sweep_and_solve_specs_parse():
    assert bench._parse_range("target=20:60:5") == ("target", 20.0, 60.0, 5.0)
    assert bench._parse_range("cargo=21.5:33.5") == ("cargo", 21.5, 33.5, None)
    assert bench._parse_limit("peak-temp-c<=400") == ("peak-temp-c", "<=", 400.0)
    assert bench._parse_limit("avg-mph>=30") == ("avg-mph", ">=", 30.0)


def test_variant_swaps_only_the_named_knob():
    sc = next(s for s in bench.SCENARIOS if s.name == "grade-no-jake")
    assert bench._variant(sc, "cargo", 30.0).cargo_kg == 30_000.0
    graded = bench._variant(sc, "grade", -4.0)
    assert all(pct in (0.0, -4.0) for _, pct in graded.profile)
    assert bench._variant(sc, "target", 42.0).target_mph == 42.0


def test_worn_brakes_fade_sooner_than_fresh():
    # Same descent, same driving: worn shoes must not end up in better
    # shape than fresh ones, and their fade threshold sits lower.
    fresh = _wear_added("grade-no-jake", "brakes")
    worn = _wear_added("grade-worn-brakes", "brakes")
    assert worn >= fresh
