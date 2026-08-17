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


def test_a_conflict_names_both_copies_so_the_choice_can_be_answered(monkeypatch):
    """Brandon (armstrong445), 2026-08-15. The screen named the cloud copy's
    level and money and said nothing whatever about the save already on his
    machine, so he was asked to choose between something described and
    something anonymous. The safe-feeling answer to that question is to
    choose neither, and that is what he did for a day while his career sat
    unbacked. Both copies are now described the same way, from the same
    ``backup_summary`` the server line is built with, so they can be compared
    word for word."""
    from freight_fate.app import App
    from freight_fate.states import cloud_save_states

    app = App()
    try:
        monkeypatch.setattr(
            cloud_save_states,
            "_local_summary_for",
            lambda name: "armstrong45, level 4, 3,294 dollars",
        )
        state = cloud_save_states.CloudSlotState(
            app.ctx, "armstrong45", [{"revision": 4, "createdAt": time.time() * 1000}]
        )
        monkeypatch.setattr(
            state,
            "_conflict",
            lambda: {"latestSummary": "armstrong45, level 7, 9,100 dollars", "latestRevision": 4},
        )
        labels = [i.text for i in state.build_items()]
        headline = next(t for t in labels if "needs attention" in t)

        # What he keeps and what he moves to, both audible before either
        # choice is read out.
        assert "This computer's copy is armstrong45, level 4, 3,294 dollars" in headline
        assert "The cloud copy is armstrong45, level 7, 9,100 dollars" in headline

        keep_mine = next(t for t in labels if t.startswith("Keep this computer's save"))
        use_cloud = next(t for t in labels if t.startswith("Use the cloud copy"))
        # Each row names what it KEEPS: two rows differing only in "this
        # computer" and "the cloud" is not a choice a player can answer.
        assert "level 4, 3,294 dollars" in keep_mine
        assert "level 7, 9,100 dollars" in use_cloud
    finally:
        app.shutdown()


def test_an_unreadable_local_save_costs_a_sentence_not_the_resolution(monkeypatch):
    """The whole point of this screen is to unstick a career. A local save
    that will not load must not be the thing that stops it being unstuck."""
    from freight_fate.app import App
    from freight_fate.states import cloud_save_states

    app = App()
    try:
        state = cloud_save_states.CloudSlotState(
            app.ctx, "armstrong45", [{"revision": 4, "createdAt": time.time() * 1000}]
        )
        monkeypatch.setattr(
            state, "_conflict", lambda: {"latestSummary": "armstrong45, level 7, 9,100 dollars"}
        )
        monkeypatch.setattr(state, "_local_summary", lambda: "")

        labels = [i.text for i in state.build_items()]

        assert any(t.startswith("Keep this computer's save") for t in labels)
        assert any("The cloud copy is" in t for t in labels)
    finally:
        app.shutdown()


def test_no_cancel_row_is_named_after_a_real_action(monkeypatch):
    """The owner pressed "No, keep this computer's save" on his own career
    expecting it to upload, and it backed out doing nothing (2026-08-15) --
    because it was the restore confirmation's CANCEL, word for word the same
    promise as the conflict screen's real action, "Keep this computer's save
    and back it up". On the one screen where a career is already stuck, a
    retreat dressed as the remedy costs the player the fix. Cancels say they
    cancel."""
    from freight_fate.app import App
    from freight_fate.states import cloud_save_states as css

    app = App()
    try:
        slot = css.CloudSlotState(
            app.ctx, "armstrong45", [{"revision": 4, "createdAt": time.time() * 1000}]
        )
        confirms = [
            css.ConfirmRestoreState(app.ctx, slot, {"revision": 4}),
            css.ConfirmKeepMineState(app.ctx, slot),
            css.ConfirmDeleteCloudState(app.ctx, slot),
        ]
        for state in confirms:
            labels = [i.text for i in state.build_items()]
            no_row = next(t for t in labels if t.startswith("No"))
            assert no_row == "No, cancel and change nothing", (
                f"{type(state).__name__} offers {no_row!r}, which describes an "
                "outcome rather than a cancellation"
            )
            # And the yes still says what it does, so the pair is not two
            # indistinguishable rows.
            assert any(t.startswith("Yes,") for t in labels)
    finally:
        app.shutdown()


def test_the_restore_cancel_points_back_at_the_upload_choice(monkeypatch):
    """A player who lands on the restore confirmation while meaning to push
    their own save up needs the way out named, not just the retreat."""
    from freight_fate.app import App
    from freight_fate.states import cloud_save_states as css

    app = App()
    try:
        slot = css.CloudSlotState(
            app.ctx, "armstrong45", [{"revision": 4, "createdAt": time.time() * 1000}]
        )
        state = css.ConfirmRestoreState(app.ctx, slot, {"revision": 4})
        cancel = next(i for i in state.build_items() if i.text.startswith("No"))

        assert "Keep this computer's save and back it up" in cancel.help_text
    finally:
        app.shutdown()
