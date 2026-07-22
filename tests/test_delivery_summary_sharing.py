"""The delivery-complete clipboard copy and Mastodon notable-delivery shares."""

from __future__ import annotations

import pygame

from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile
from freight_fate.online_journal import JournalOutbox, queue_mastodon_share
from freight_fate.online_presence import OnlineIdentity
from freight_fate.states import online_states


def _identity() -> OnlineIdentity:
    return OnlineIdentity("driver-1234", "ffd_" + "a" * 64)


def _job() -> Job:
    return Job(
        CARGO_CATALOG["general"], 20, "chicago_il_us", "terminal", "denver_co_us", 1000, 2000, 20
    )


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0)


# -- queueing rules -------------------------------------------------------------


def test_routine_deliveries_are_never_queued_for_mastodon(tmp_path):
    box = JournalOutbox(_identity(), True, tmp_path / "outbox.json")
    profile = Profile(name="Road Star")
    profile.career.deliveries = 7
    assert not queue_mastodon_share(
        box,
        profile,
        _job(),
        origin="Chicago, Illinois",
        destination="Denver, Colorado",
        on_time=True,
        occurred_at_ms=123,
        reasons=[],
    )
    assert box.items == []


def test_notable_share_carries_allowlisted_facts_and_posts_once(tmp_path):
    box = JournalOutbox(_identity(), True, tmp_path / "outbox.json")
    profile = Profile(name="Road Star")
    profile.career.deliveries = 1
    reasons = [
        {"type": "level", "level": 2},
        {"type": "achievements", "names": ["Signed On"]},
    ]
    assert queue_mastodon_share(
        box,
        profile,
        _job(),
        origin="Chicago, Illinois",
        destination="Denver, Colorado",
        on_time=True,
        occurred_at_ms=123,
        reasons=reasons,
    )
    item = box.items[0]
    assert item.endpoint == "/api/freight-fate/mastodon/share"
    inner = item.payload["payload"]
    assert inner["reasons"] == reasons
    assert inner["cargo"] == CARGO_CATALOG["general"].label
    assert inner["origin"] == "Chicago, Illinois"
    assert inner["onTime"] is True
    # The same completed delivery never posts twice, even if re-queued.
    assert not queue_mastodon_share(
        box,
        profile,
        _job(),
        origin="Chicago, Illinois",
        destination="Denver, Colorado",
        on_time=True,
        occurred_at_ms=456,
        reasons=reasons,
    )


# -- arrival screen ---------------------------------------------------------------


def _complete_first_delivery(app):
    from freight_fate.models.jobs import JobBoard
    from freight_fate.states.driving import ArrivalState, DrivingState

    app.ctx.profile = Profile(name="Notable Run")
    p = app.ctx.profile
    p.current_city = "Chicago"
    job = next(
        job
        for job in JobBoard(app.ctx.world).offers(
            p.current_city,
            p.career.endorsements,
            level=p.career.level,
            market=p.market,
        )
        if not job.locked_reason(p.career.endorsements, p.career.level)
    )
    route = app.ctx.world.supported_route_options(job.origin, job.destination)[0]
    driving = DrivingState(app.ctx, job, route)
    driving.trip.game_minutes = job.deadline_game_h * 30.0
    driving.speeding_strikes = 0
    return ArrivalState(app.ctx, driving)


def test_arrival_menu_offers_copy_before_continue(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        spoken: list[str] = []
        monkeypatch.setattr(app.ctx, "say", lambda text, **_kw: spoken.append(text))
        arrival = _complete_first_delivery(app)
        arrival.enter()
        labels = [item.text for item in arrival.items]
        assert labels[-1].startswith("Continue to ")
        assert labels[-2] == "Copy delivery summary to clipboard"

        copied: list[str] = []
        monkeypatch.setattr(
            online_states, "write_clipboard_text", lambda text: bool(copied.append(text)) or True
        )
        arrival._copy_summary()
        assert copied[0].splitlines()[0] == "Freight Fate: Delivery complete."
        for line in arrival.summary_lines:
            assert line in copied[0]
        assert spoken[-1] == "Delivery summary copied to clipboard."

        monkeypatch.setattr(online_states, "write_clipboard_text", lambda text: False)
        arrival._copy_summary()
        assert spoken[-1].startswith("I could not copy to the clipboard")
    finally:
        app.shutdown()


def test_first_delivery_queues_a_mastodon_share_when_enabled(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.mastodon.set_identity(_identity())
        app.settings.mastodon_sharing = True
        app.ctx.apply_mastodon_sharing()
        flushed: list[int] = []
        monkeypatch.setattr(app.mastodon, "flush_async", lambda: flushed.append(1))
        monkeypatch.setattr(app.ctx, "say", lambda *_a, **_kw: None)

        _complete_first_delivery(app)

        assert app.mastodon.items, "the first delivery earns achievements, so it is notable"
        inner = app.mastodon.items[0].payload["payload"]
        achievement_reason = next(r for r in inner["reasons"] if r["type"] == "achievements")
        assert achievement_reason["names"]
        assert flushed
    finally:
        app.shutdown()


def test_sharing_off_queues_nothing(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.mastodon.set_identity(_identity())
        assert app.settings.mastodon_sharing is False
        app.ctx.apply_mastodon_sharing()
        monkeypatch.setattr(app.ctx, "say", lambda *_a, **_kw: None)

        _complete_first_delivery(app)

        assert app.mastodon.items == []
    finally:
        app.shutdown()


# -- settings menu ------------------------------------------------------------


def _open_online_settings(app):
    """Walk Settings to the Online pointer, which opens the Online hub."""
    from freight_fate.states.main_menu import SettingsState
    from freight_fate.states.online_hub import OnlineHubState

    picker = SettingsState(app.ctx)
    app.push_state(picker)
    while picker.items[picker.index].text != "Online":
        picker.handle_event(key_event(pygame.K_DOWN))
    picker.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, OnlineHubState)
    return app.state


def test_mastodon_toggle_needs_a_linked_account_first(monkeypatch):
    from freight_fate.app import App

    _identity().save()  # account is set up, but no Mastodon link is known
    app = App()
    try:
        spoken: list[str] = []
        monkeypatch.setattr(app.ctx, "say", lambda text, **_kw: spoken.append(text))
        cat = _open_online_settings(app)
        while not cat.items[cat.index].text.startswith("Share notable deliveries"):
            cat.handle_event(key_event(pygame.K_DOWN))
        assert cat.items[cat.index].text.endswith("not linked")
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.mastodon_sharing is False
        assert "Link a Mastodon account" in spoken[-1]
    finally:
        app.shutdown()


def test_mastodon_toggle_flips_and_discloses_when_linked(monkeypatch):
    from freight_fate.app import App

    _identity().save()
    app = App()
    try:
        app.ctx.settings.mastodon_linked = True
        app.ctx.settings.mastodon_linked_handle = "@roadstar@mastodon.example"
        spoken: list[str] = []
        monkeypatch.setattr(app.ctx, "say", lambda text, **_kw: spoken.append(text))
        cat = _open_online_settings(app)
        while not cat.items[cat.index].text.startswith("Share notable deliveries"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.mastodon_sharing is True
        assert app.mastodon.enabled is True
        assert any("FreightFate hashtag" in text for text in spoken)
        cat.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.mastodon_sharing is False
        assert app.mastodon.enabled is False
    finally:
        app.shutdown()


def test_mastodon_toggle_works_when_linked_without_a_handle(monkeypatch):
    # Regression: a link can exist with no readable handle (the server could
    # not fetch the account name). The toggle must gate on the linked flag,
    # not the display handle, or the player hears "linked" from the status
    # check while the switch keeps refusing.
    from freight_fate.app import App

    _identity().save()
    app = App()
    try:
        app.ctx.settings.mastodon_linked = True
        app.ctx.settings.mastodon_linked_handle = ""
        monkeypatch.setattr(app.ctx, "say", lambda *_a, **_kw: None)
        cat = _open_online_settings(app)
        while not cat.items[cat.index].text.startswith("Share notable deliveries"):
            cat.handle_event(key_event(pygame.K_DOWN))
        assert cat.items[cat.index].text.endswith("off")
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.mastodon_sharing is True
    finally:
        app.shutdown()


def test_status_check_records_linked_flag_even_without_handle():
    from types import SimpleNamespace

    from freight_fate.settings import Settings
    from freight_fate.states.online_states import MastodonLinkState

    settings = Settings()
    said: list[str] = []
    ctx = SimpleNamespace(
        settings=settings,
        say=lambda text, interrupt=True: said.append(text),
        audio=SimpleNamespace(play=lambda *_a, **_kw: None),
    )
    state = MastodonLinkState(ctx)
    state.items = state.build_items()
    state._checking = True
    state._outcome = {"linked": True, "handle": ""}
    state.update(0)
    assert settings.mastodon_linked is True
    assert settings.mastodon_linked_handle == ""
    assert any(text.startswith("Linked: your Mastodon account") for text in said)


def test_online_adjust_rows_still_line_up(monkeypatch):
    # The online category wires labels and left/right handlers as two
    # parallel lists; a new row must land in both at the same index or
    # left/right silently retargets a neighboring setting.
    from freight_fate.app import App

    _identity().save()
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda *_a, **_kw: None)
        cat = _open_online_settings(app)
        before = app.ctx.settings.discord_presence
        while not cat.items[cat.index].text.startswith("Discord presence"):
            cat.handle_event(key_event(pygame.K_DOWN))
        cat.handle_event(key_event(pygame.K_RIGHT))
        assert app.ctx.settings.discord_presence is (not before)
    finally:
        app.shutdown()
