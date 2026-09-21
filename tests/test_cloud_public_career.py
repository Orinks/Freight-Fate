"""Choosing which career fronts the public profile, from the Cloud backup menu.

One career is the player's public face; the rest stay private cloud backups.
The list says which career is public, each backed-up career offers to become
it behind a spoken confirmation, and the choice goes to orinks.net.
"""

import time

import pygame
from speech_capture import speech_stub  # noqa: F401  (spoken-text capture fixture)

from freight_fate import cloud_saves
from freight_fate.online_presence import OnlineIdentity

IDENTITY = OnlineIdentity(driver_id="driver-testtest", driver_token="t" * 48)


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0)


def cloud_reply(public: str | None):
    return {
        "saves": [
            {"saveName": "Road Star", "revision": 2, "createdAt": time.time() * 1000},
            {"saveName": "Night Runs", "revision": 1, "createdAt": time.time() * 1000},
        ],
        "publicSaveName": public,
    }


def open_backup_menu(app, monkeypatch, public: str | None):
    from freight_fate.states.cloud_save_states import CloudBackupState

    monkeypatch.setattr(OnlineIdentity, "load", staticmethod(lambda: IDENTITY))
    monkeypatch.setattr(cloud_saves, "list_saves", lambda identity: cloud_reply(public))
    state = CloudBackupState(app.ctx)
    app.push_state(state)
    assert state._fetched.wait(5)
    state.update(0.0)
    return state


def settle(state, seconds=2.0):
    """Pump update until the slot's worker thread hands back its outcome."""
    deadline = time.time() + seconds
    while state._busy and time.time() < deadline:
        state.update(0.0)
        time.sleep(0.01)
    state.update(0.0)


def test_the_list_says_which_career_is_public(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        state = open_backup_menu(app, monkeypatch, public="Night Runs")
        texts = [item.text for item in state.items]
        assert any("Night Runs" in t and "your public career" in t for t in texts)
        assert not any("Road Star" in t and "your public career" in t for t in texts)
    finally:
        app.shutdown()


def test_a_backed_up_career_can_become_the_public_one(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.cloud_save_states import (
        CloudSlotState,
        ConfirmPublicCareerState,
    )

    chosen = []

    def fake_set_public_save(identity, *, save_name):
        chosen.append(save_name)
        return True

    app = App()
    try:
        state = open_backup_menu(app, monkeypatch, public=None)
        monkeypatch.setattr(cloud_saves, "set_public_save", fake_set_public_save)

        while "Night Runs" not in state.items[state.index].text:
            state.handle_event(key_event(pygame.K_DOWN))
        state.handle_event(key_event(pygame.K_RETURN))
        slot = app.state
        assert isinstance(slot, CloudSlotState)

        while "public career" not in slot.items[slot.index].text:
            slot.handle_event(key_event(pygame.K_DOWN))
        assert slot.items[slot.index].text == "Make this your public career"
        assert slot.items[slot.index].help
        slot.handle_event(key_event(pygame.K_RETURN))
        confirm = app.state
        assert isinstance(confirm, ConfirmPublicCareerState)

        while "Yes" not in confirm.items[confirm.index].text:
            confirm.handle_event(key_event(pygame.K_DOWN))
        confirm.handle_event(key_event(pygame.K_RETURN))
        settle(slot)

        assert chosen == ["Night Runs"]
        # The slot now says it is the public career instead of offering it.
        texts = [item.text for item in slot.items]
        assert "This is your public career" in texts
        assert "Make this your public career" not in texts
        # And the backup list behind it agrees without another fetch.
        assert state._public_save == "Night Runs"
    finally:
        app.shutdown()


def test_the_public_career_shows_status_not_an_action(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.cloud_save_states import CloudSlotState

    app = App()
    try:
        state = open_backup_menu(app, monkeypatch, public="Road Star")
        while "Road Star" not in state.items[state.index].text:
            state.handle_event(key_event(pygame.K_DOWN))
        state.handle_event(key_event(pygame.K_RETURN))
        slot = app.state
        assert isinstance(slot, CloudSlotState)
        texts = [item.text for item in slot.items]
        assert "This is your public career" in texts
        assert "Make this your public career" not in texts
    finally:
        app.shutdown()
