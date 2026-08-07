"""Test configuration: force headless drivers before anything imports pygame."""

import os

# Tests must never inherit a visible desktop/audio driver from the launching
# shell. Force the headless settings so running the suite cannot flash Freight
# Fate windows or speak over the user.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["FREIGHT_FATE_NO_SPEECH"] = "1"
os.environ["FREIGHT_FATE_IGNORE_SOUND_PACK"] = "1"
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


class FakeKeyring:
    """An in-memory stand-in for the platform secret store."""

    def __init__(self) -> None:
        self.passwords: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self.passwords[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self.passwords.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        del self.passwords[(service, username)]


@pytest.fixture(autouse=True)
def isolated_keyring(monkeypatch):
    """Keep the online driver token out of the real secret store.

    Unlike the data directory there is no per-test Credential Manager or
    Keychain to point at, so a test that reached the real one would leave
    credentials behind on the machine that ran it -- and a leftover from an
    earlier run could bleed a token into a later test's fresh data directory.
    Tests that need the no-store path patch this to ``None`` themselves.
    """
    from freight_fate import online_presence

    monkeypatch.setattr(online_presence, "keyring", FakeKeyring())
    # Resolved tokens are cached for the life of the process, which outlives
    # any one test's data directory.
    monkeypatch.setattr(online_presence.OnlineIdentity, "_token_cache", {})
    yield


@pytest.fixture(scope="session")
def world():
    from freight_fate.data import get_world

    return get_world()
