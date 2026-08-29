"""Test configuration: force headless drivers before anything imports pygame."""

import os

# Tests must never inherit a visible desktop/audio driver from the launching
# shell. Force the headless settings so running the suite cannot flash Freight
# Fate windows or speak over the user.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["FREIGHT_FATE_NO_SPEECH"] = "1"
# Builder machines carry the loose assets/sounds tree (it is not in the repo;
# the shipped audio is sounds.pak). Where the tree exists, tests exercise the
# loose-file path the sound authors rely on; a clean clone (CI) runs the same
# suite against the committed pack instead.
from pathlib import Path as _Path  # noqa: E402

if (_Path(__file__).parents[1] / "src" / "freight_fate" / "assets" / "sounds" / "ui").exists():
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

# Ceiling on what ``-n auto`` may spawn. A worker here is not cheap: it loads
# pygame and the audio stack, and most suites build whole App() instances, so
# the suite is bound by that setup rather than by how many cores are free.
# Measured on the 28-core developer machine, 140 driving tests:
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


@pytest.fixture(autouse=True)
def _online_offer_already_seen(isolated_data_dir):
    """Seed the one-time first-run orinks.net offer as already spent.

    The offer is on by default in real play: a fresh install has not seen it,
    so career creation shows it. A test that is not about that offer should
    not have to know it exists just to drive a career through App() -- so
    write settings.json with the gate already spent into this test's isolated
    data dir before any App() is constructed and reads it via
    Settings.load(). Depends on isolated_data_dir (not just autouse ordering)
    so FREIGHT_FATE_DATA_DIR is guaranteed set first, even if fixture order
    is ever reshuffled.

    A test that is about the offer opts back out: the state-level tests in
    tests/test_online_offer.py build their own in-memory Settings() through
    _make_ctx and never read this file, and its two spoken-order tests, which
    do construct an App(), clear online_offer_seen on ctx.settings afterwards
    so career creation offers exactly as it does on a fresh install.
    """
    from freight_fate.settings import Settings

    game_settings = Settings()
    game_settings.online_offer_seen = True
    game_settings.save()


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
