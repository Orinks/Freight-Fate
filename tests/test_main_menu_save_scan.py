"""MainMenuState.enter() must scan the save directory once, not three times.

Profiling found _loadable_saves() -- a full re-read of every save on disk --
called three times in a row from a single MainMenuState.enter(): once from
build_items(), once from announce_entry()'s legacy-save check, and once from
enter()'s own profile lookup. See states/main_menu._reuse_loadable_saves_scan.
"""

from __future__ import annotations

from freight_fate.app import App
from freight_fate.models.profile import Profile
from freight_fate.states import main_menu
from freight_fate.states.main_menu import MainMenuState


def test_main_menu_enter_scans_saves_once(monkeypatch):
    profile = Profile(name="Road Star", current_city="Denver")
    profile.save()

    calls = []
    real_list_saves = Profile.list_saves

    def counting_list_saves():
        calls.append(1)
        return real_list_saves()

    monkeypatch.setattr(Profile, "list_saves", staticmethod(counting_list_saves))

    app = App()
    try:
        app.push_state(MainMenuState(app.ctx))
    finally:
        app.shutdown()

    assert len(calls) == 1


def test_main_menu_enter_scan_cache_does_not_leak_between_enters(monkeypatch):
    """Re-entering the menu after a save changed must still see it: the
    per-enter cache must not survive past its own enter() call."""
    profile = Profile(name="Road Star", current_city="Denver")
    profile.save()

    app = App()
    try:
        state = MainMenuState(app.ctx)
        app.push_state(state)
        first = main_menu._loadable_saves()
        assert len(first) == 1

        second_profile = Profile(name="Coast Runner", current_city="Chicago")
        second_profile.save()

        state.enter()  # re-enter, as returning from a submenu would
        assert len(main_menu._loadable_saves()) == 2
    finally:
        app.shutdown()


def test_reuse_loadable_saves_scan_is_reentrant(monkeypatch):
    """A nested scope must not drop the cache the outer scope still owns."""
    profile = Profile(name="Nested Driver", current_city="Denver")
    profile.save()

    calls = []
    real_list_saves = Profile.list_saves

    def counting_list_saves():
        calls.append(1)
        return real_list_saves()

    monkeypatch.setattr(Profile, "list_saves", staticmethod(counting_list_saves))

    with main_menu._reuse_loadable_saves_scan():
        main_menu._loadable_saves()
        with main_menu._reuse_loadable_saves_scan():
            main_menu._loadable_saves()
        main_menu._loadable_saves()

    assert len(calls) == 1
