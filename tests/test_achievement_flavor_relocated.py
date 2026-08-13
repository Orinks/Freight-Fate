"""R9: achievement flavor leaves the drive.

Mid-drive an achievement is its earcon and its name; the flavor prose waits
in the message log, the achievements menu, and a parked settlement -- and the
settlement collapses a run's badges into one row that names them rather than
reading a comedy paragraph for each.
"""

from freight_fate.speech_text import achievement_announced, achievement_unlocked


def test_live_announce_is_name_only_in_both_modes():
    pair = achievement_unlocked("Night Owl", "You ran the small hours and kept it clean.")
    live = achievement_announced("Night Owl")
    # The stored record keeps the flavor for the log and the menu...
    assert "kept it clean" in pair.normal
    # ...but the live announce never speaks it, in either speech mode.
    assert live.normal == "New achievement! Night Owl."
    assert live.render(terse=True) == "Night Owl."
    assert "kept it clean" not in live.normal


def test_award_speaks_the_short_line_and_logs_the_flavor(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile

    app = App()
    try:
        app.ctx.profile = Profile(name="Flavor Relocation")
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, **_k: spoken.append(text))

        result = app.ctx.award_achievement("first_delivery")

        assert result is not None
        assert spoken == [achievement_announced(result.achievement.name)]
        assert "New achievement!" in str(result.message)  # full record still built
        # The flavor is reachable: it landed in the review log.
        assert str(app.ctx.message_log.messages[-1].text) == str(result.message)
    finally:
        app.shutdown()
