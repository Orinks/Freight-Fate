import json

from freight_fate.settings import Settings
from freight_fate.states.online_states import DISCLOSURE, ProfileSharingSyncState


class ImmediateThread:
    def __init__(self, *, target, **_kwargs):
        self.target = target

    def start(self):
        self.target()


def test_disclosure_is_single_profile_sharing_consent():
    lowered = DISCLOSURE.lower()
    assert "profile sharing" in lowered
    assert "road-journal" in lowered
    assert "official achievements" in lowered
    assert "updates feed" in lowered
    assert "separately" not in lowered
    assert "unlisted" not in lowered
    assert "factual" not in lowered


def test_disable_success_confirms_off_and_clears_pending(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, **_kwargs: spoken.append(text))
    try:
        app.ctx.settings.online_presence = True
        app.ctx.settings.profile_sharing_pending_off = True
        state = ProfileSharingSyncState(app.ctx, False)
        app.push_state(state)
        state._outcome = "ok"
        state.update(0)
        assert app.ctx.settings.online_presence is False
        assert app.ctx.settings.profile_sharing_pending_off is False
        assert any("Profile sharing is off" in text for text in spoken)
        assert app.state is not state
    finally:
        app.shutdown()


def test_disable_failure_remains_pending_and_never_claims_off(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, **_kwargs: spoken.append(text))
    try:
        app.ctx.settings.online_presence = True
        app.ctx.settings.profile_sharing_pending_off = True
        state = ProfileSharingSyncState(app.ctx, False)
        app.push_state(state)
        state._outcome = "error"
        state.update(0)
        assert app.ctx.settings.online_presence is True
        assert app.ctx.settings.profile_sharing_pending_off is True
        assert any("may still be public" in text for text in spoken)
        assert not any("Profile sharing is off." in text for text in spoken)
        assert app.state is state
    finally:
        app.shutdown()


def test_disable_start_stops_local_services_before_server_confirmation(monkeypatch):
    import freight_fate.states.online_states as states
    from freight_fate.app import App
    from freight_fate.online_presence import OnlineIdentity

    app = App()
    identity = OnlineIdentity("driver-1234", "ffd_" + "a" * 64)
    monkeypatch.setattr(OnlineIdentity, "load", classmethod(lambda cls: identity))
    monkeypatch.setattr(states.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(states.online_presence, "set_profile_sharing", lambda *_args: "error")
    try:
        app.ctx.settings.online_presence = True
        app.ctx.apply_online_presence()
        state = ProfileSharingSyncState(app.ctx, False)
        app.push_state(state)
        state._start()
        assert app.ctx.settings.profile_sharing_pending_off is True
        assert app.online.enabled is False
        assert app.journal.enabled is False
        state.update(0)
        assert state.items[0].text == "Turn Profile sharing off"
    finally:
        app.shutdown()


def test_enable_success_and_failure_are_server_authoritative(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, **_kwargs: spoken.append(text))
    try:
        failed = ProfileSharingSyncState(app.ctx, True)
        app.push_state(failed)
        failed._outcome = "error"
        failed.update(0)
        assert app.ctx.settings.online_presence is False
        assert not any("Profile sharing is on." in text for text in spoken)

        app.pop_state()
        spoken.clear()
        succeeded = ProfileSharingSyncState(app.ctx, True)
        app.push_state(succeeded)
        succeeded._outcome = "ok"
        succeeded.update(0)
        assert app.ctx.settings.online_presence is True
        assert app.ctx.settings.profile_sharing_consent_version == 3
        assert any("Profile sharing is on." in text for text in spoken)
        assert app.state is not succeeded
    finally:
        app.shutdown()


def test_cancel_returns_without_changing_profile_sharing():
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.online_presence = False
        state = ProfileSharingSyncState(app.ctx, True)
        app.push_state(state)
        state.go_back()
        assert app.ctx.settings.online_presence is False
        assert app.state is not state
    finally:
        app.shutdown()


def test_only_current_profile_sharing_consent_can_remain_on(monkeypatch, tmp_path):
    import freight_fate.settings as settings_module

    monkeypatch.setattr(settings_module, "data_dir", lambda: tmp_path)
    for version, expected in [
        (None, False),
        (0, False),
        (1, False),
        (2, False),
        (3, True),
        (4, False),
    ]:
        data = {"online_presence": True}
        if version is not None:
            data["profile_sharing_consent_version"] = version
        (tmp_path / "settings.json").write_text(json.dumps(data), encoding="utf-8")
        assert Settings.load().online_presence is expected
