"""Test configuration: force headless drivers before anything imports pygame."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FREIGHT_FATE_NO_SPEECH", "1")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pytest
from hypothesis import HealthCheck, settings

settings.register_profile(
    "default",
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Keep saves and settings out of the real user data directory."""
    monkeypatch.setenv("FREIGHT_FATE_DATA_DIR", str(tmp_path / "data"))
    yield


@pytest.fixture(scope="session")
def world():
    from freight_fate.data import get_world

    return get_world()
