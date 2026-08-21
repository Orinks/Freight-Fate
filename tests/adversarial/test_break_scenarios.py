"""The adversarial battery, as tests.

``tools/playtest_break.py`` drives the real driving state and menu flow
through deliberately unreasonable play -- flooring it through town, coasting a
mountain in neutral, save-scumming a traffic stop -- and grades each scenario
CLEAN, ODD or ERROR. That is a discovery tool: it goes looking for things
nobody thought to assert, and its findings need a human to judge.

This file is the gate side of the same battery, and it exists because
"discovery tool" was doing too much work as an excuse. On 2026-08-10, four of
its nine findings turned out to be artifacts of the harness rather than bugs
in the game, and they had sat untriaged because ODD read as "someone should
look at this eventually" rather than as a failing test. Reporting through
pytest fixes the ambiguity:

* a **new** ODD finding fails, loudly, naming what it found
* a **known** ODD finding is a strict xfail carrying its explanation
* a known finding that gets **fixed** turns into XPASS, which fails and tells
  you to delete its entry from ``KNOWN_OPEN`` below

Deselected by default (``-m "not adversarial"`` lives in the pyproject
addopts) because the battery drives whole simulated deliveries. Run it with::

    uv run pytest tests/adversarial -m adversarial

Every entry in ``KNOWN_OPEN`` should also be a bullet on the roadmap. If you
fix one, delete the entry here in the same change -- that is what the strict
xfail is for.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_break_harness():
    """Import tools/playtest_break.py under its own name.

    ``tools/`` is not a package, so the battery is loaded by path -- the same
    trick tests/test_build_interchanges_tool.py uses. The module aliases
    itself into ``sys.modules["playtest_break"]`` before importing its
    scenario package, because the scenario modules register themselves with
    ``from playtest_break import ...`` and a second copy would collect every
    registration into a dict nobody reads. Loading it under that exact name
    keeps that arrangement intact.

    Deliberately NOT a conftest: a ``tests/adversarial/conftest.py`` claims
    the module name ``conftest``, and tests/test_online_presence.py imports
    ``FakeKeyring`` from the top-level one by that bare name. Whichever
    imported first won, which broke a module that has nothing to do with this
    battery.
    """
    if "playtest_break" in sys.modules:
        return sys.modules["playtest_break"]
    tools = ROOT / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    spec = importlib.util.spec_from_file_location("playtest_break", tools / "playtest_break.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["playtest_break"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def break_harness():
    return _load_break_harness()


# Findings that are real, verified, and not yet fixed. Keyed by scenario name;
# the value is why it is still open, spoken plainly enough to act on.
KNOWN_OPEN = {
    # The requeue-resurrection pair (scale_bypass_to_the_end and
    # prepass_green_is_not_a_bypass_charge) was fixed 2026-08-21 and their
    # entries deleted: the owner's build note ruled the repeat the bug, so
    # rescues are capped at one per line per window AND carry a validity
    # check -- the re-render/drop treatment this comment used to prescribe
    # (a line whose moment passed is dropped, not replayed frozen). The
    # test that pinned a rescue after every cut was revised to the new
    # contract in the same change.
    "short_hop_streak_xp_farming": (
        "25-mile hops earn 4.6x the XP efficiency of a 500-mile haul, and short "
        "hauls are the faster ones to drive; the streak bonus is now capped at "
        "the mileage XP, so what remains is the flat completion XP by design"
    ),
}


def _scenario_names():
    """Collected at import so each scenario is its own test node."""
    return sorted(_load_break_harness().SCENARIOS)


def _params():
    for name in _scenario_names():
        reason = KNOWN_OPEN.get(name)
        marks = [pytest.mark.xfail(reason=reason, strict=True)] if reason else []
        yield pytest.param(name, marks=marks, id=name)


@pytest.mark.adversarial
# A scenario can drive a full delivery; the default per-test timeout would kill
# the xdist worker rather than the test (see the CI xdist note in AGENTS.md).
@pytest.mark.timeout(600)
@pytest.mark.parametrize("name", list(_params()))
def test_scenario_finds_nothing_new(break_harness, name):
    outcome = break_harness.run_scenario(name)

    if outcome.verdict == "ERROR":
        pytest.fail(f"{name} crashed:\n" + "\n".join(outcome.findings))
    assert outcome.verdict == "CLEAN", f"{name} found:\n" + "\n".join(
        f"  - {finding}" for finding in outcome.findings
    )


@pytest.mark.adversarial
def test_every_known_open_finding_names_a_real_scenario(break_harness):
    """A renamed or deleted scenario must not silently retire its finding."""
    unknown = sorted(set(KNOWN_OPEN) - set(break_harness.SCENARIOS))
    assert not unknown, f"KNOWN_OPEN names scenarios that no longer exist: {unknown}"
