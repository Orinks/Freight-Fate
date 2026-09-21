"""Test configuration: headless, isolated, and capped in parallelism."""

import os

# Tests must never inherit a visible desktop/audio driver from the launching
# shell. Force the headless settings so running the suite cannot flash Freight
# Fate windows or speak over the user.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["FREIGHT_FATE_NO_SPEECH"] = "1"

import pytest
from hypothesis import HealthCheck, settings

settings.register_profile(
    "default",
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

# Ceiling on what ``-n auto`` may spawn. Measured when the suite still built
# whole game instances, on the 28-core developer machine, 140 driving tests:
#
#     n=4  48s    n=8  31s    n=12  33s    n=16  31s    n=auto(28)  crashed
#
# Past eight there is nothing left to win, and at twenty-eight the run dies
# with an INTERNALERROR in the reporter rather than merely running slowly --
# so the uncapped default was costing correctness, not just a usable desktop.
# CI runners have far fewer cores than this ceiling, so they are unaffected;
# PYTEST_XDIST_AUTO_NUM_WORKERS still overrides it either way.
MAX_XDIST_AUTO_WORKERS = 8


@pytest.hookimpl(tryfirst=True)
def pytest_xdist_auto_num_workers(config):
    """Resolve ``-n auto`` to something that leaves the machine usable."""
    override = os.environ.get("PYTEST_XDIST_AUTO_NUM_WORKERS")
    if override:
        try:
            return int(override)
        except ValueError:
            pass  # xdist warns about this itself; fall through to the cap
    return max(1, min(MAX_XDIST_AUTO_WORKERS, os.cpu_count() or 1))


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Keep saves and settings out of the real user data directory."""
    monkeypatch.setenv("FREIGHT_FATE_DATA_DIR", str(tmp_path / "data"))
    yield


@pytest.fixture(scope="session")
def world():
    from ffworld import get_world

    return get_world()
