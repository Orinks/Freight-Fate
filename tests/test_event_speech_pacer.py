"""The event-voice pacer drops stale backlogs instead of performing them.

Owner playtest 2026-07-15: arriving at the yard played the whole approach
script late -- "slow down to dock, at dock, delivering" heard after the
trailer was already empty -- because the event voice queues faster than it
speaks. The pacer projects when the channel falls silent; a queued line
that would start speaking more than STALE_WAIT_S after the moment it
described flushes the backlog and speaks fresh.

Tester transcript 2026-08-11 added three more failures the projection alone
could not answer, and the rest of this file covers them: one moment said
several times over, a standing condition read out unchanged for the rest of
the drive, and the stop the player planned lost behind roadside chatter.
"""

from __future__ import annotations

from speech_capture import speech_stub

from freight_fate.speech import EventPriority, EventSpeechPacer


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def make_pacer() -> tuple[EventSpeechPacer, FakeClock]:
    clock = FakeClock()
    return EventSpeechPacer(clock=clock), clock


LONG_LINE = "x" * 130  # ~10 seconds at the default 13 chars per second


def test_quiet_channel_queues_normally() -> None:
    pacer, _ = make_pacer()
    assert pacer.should_flush("Slow down for the dock.") is False


def test_backlog_past_the_threshold_flushes() -> None:
    pacer, _ = make_pacer()
    # First long line starts immediately; the second waits ~10s behind it --
    # far past the 3-second staleness budget.
    assert pacer.should_flush(LONG_LINE) is False
    assert pacer.should_flush("At the dock.") is True


def test_flush_restarts_the_projection() -> None:
    pacer, _ = make_pacer()
    pacer.should_flush(LONG_LINE)
    assert pacer.should_flush("At the dock.") is True
    # The flush purged the channel: the very next line queues normally.
    assert pacer.should_flush("Delivering.") is False


def test_interrupt_resets_to_truth() -> None:
    pacer, _ = make_pacer()
    pacer.should_flush(LONG_LINE)
    pacer.note_interrupt("Collision!")
    # The interrupting line purged the backlog; a short queued follow-up
    # starts right behind it, inside the staleness budget.
    assert pacer.should_flush("Total damage 12 percent.") is False


def test_projection_expires_with_real_time() -> None:
    pacer, clock = make_pacer()
    pacer.should_flush(LONG_LINE)
    clock.now += 30.0  # the voice long since finished speaking
    assert pacer.should_flush("Exit ahead.") is False


def test_reset_clears_the_projection() -> None:
    pacer, _ = make_pacer()
    pacer.should_flush(LONG_LINE)
    pacer.reset()
    assert pacer.should_flush("At the dock.") is False


def test_say_event_flushes_a_stale_backlog_end_to_end() -> None:
    """ctx.say_event: a burst of queued events turns into an interrupting
    (channel-purging) delivery once the backlog goes stale."""
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech.say_event = speech_stub(calls, with_interrupt=True)

        approach = [
            "Slow down for the dock, twenty five miles per hour through the yard.",
            "Passing the fuel island, dock doors ahead on the left.",
            "At the dock. Line up square and ease it back.",
            "Delivering. The forklift crew is unloading the trailer.",
        ]
        for line in approach:
            app.ctx.say_event(line, interrupt=False)

        assert all(not interrupt for _, interrupt in calls[:1])
        assert any(interrupt for _, interrupt in calls), (
            "a stale backlog was performed in full -- the pacer never flushed"
        )
        # Every line still reached the voice in order; staleness changes
        # delivery, never drops the newest information.
        assert [text for text, _ in calls] == approach
    finally:
        app.shutdown()


def test_many_short_lines_stay_within_budget_then_flush() -> None:
    pacer, _ = make_pacer()
    line = "Passing the fuel island."  # ~2.3s estimated
    verdicts = [pacer.should_flush(line) for _ in range(4)]
    # The first few fit inside the budget; the backlog eventually crosses it.
    assert verdicts[0] is False
    assert True in verdicts[1:]


# -- one moment, said once (tester transcript, 2026-08-11) ----------------------
#
# A sideswipe arrived as three identical lines inside six tenths of a second,
# and a load's condition was read out unchanged every few seconds for the rest
# of the drive. The pacer now knows what the player has already heard.


SIDESWIPE = (
    "You sideswiped a box truck in the right lane! The truck took damage, "
    "now 13 percent. Check your mirrors before moving over."
)


def test_identical_line_inside_the_window_is_a_repeat() -> None:
    pacer, clock = make_pacer()
    assert pacer.is_repeat(SIDESWIPE) is False
    pacer.note_spoken(SIDESWIPE)
    clock.now += 0.6  # the burst the tester heard
    assert pacer.is_repeat(SIDESWIPE) is True


def test_the_same_line_is_news_again_once_the_window_passes() -> None:
    pacer, clock = make_pacer()
    pacer.note_spoken(SIDESWIPE)
    clock.now += EventSpeechPacer.REPEAT_WINDOW_S + 0.1
    assert pacer.is_repeat(SIDESWIPE) is False


def test_a_line_the_player_asked_for_is_never_a_repeat() -> None:
    pacer, _ = make_pacer()
    pacer.note_spoken(SIDESWIPE)
    assert pacer.is_repeat(SIDESWIPE, force=True) is False


def test_standing_condition_repeats_only_when_it_changes() -> None:
    """A state of the world speaks when it starts and when it worsens."""
    pacer, clock = make_pacer()
    at_45 = "The load has shifted hard and is badly damaged, 45 percent."
    at_60 = "The load has shifted hard and is badly damaged, 60 percent."

    assert pacer.is_repeat(at_45, key="cargo_condition") is False
    pacer.note_spoken(at_45, key="cargo_condition")

    # Minutes later, still the same load in the same state: nothing new to say.
    clock.now += 300.0
    assert pacer.is_repeat(at_45, key="cargo_condition") is True

    # The damage has moved. That is news, and it speaks.
    assert pacer.is_repeat(at_60, key="cargo_condition") is False
    pacer.note_spoken(at_60, key="cargo_condition")
    clock.now += 300.0
    assert pacer.is_repeat(at_60, key="cargo_condition") is True


def test_a_cleared_condition_announces_itself_afresh() -> None:
    pacer, clock = make_pacer()
    redline = "Redline. Engine wear 4 percent."
    pacer.note_spoken(redline, key="engine_redline")
    clock.now += 300.0
    assert pacer.is_repeat(redline, key="engine_redline") is True
    # The engine came off the limiter and went back on: a fresh event.
    pacer.forget_condition("engine_redline")
    assert pacer.is_repeat(redline, key="engine_redline") is False


# -- stepping off the road ------------------------------------------------------


def test_pause_arms_a_purge_so_the_backlog_is_not_replayed() -> None:
    pacer, clock = make_pacer()
    pacer.should_flush(LONG_LINE)  # a line still speaking when the player pauses
    pacer.pause()
    clock.now += 45.0  # a while in the pause menu
    # Back on the road: the first line purges the channel rather than falling
    # in behind whatever the voice was still holding.
    assert pacer.should_flush("Speed limit reduced to 55 miles per hour.") is True


def test_resume_purges_once_then_paces_normally() -> None:
    pacer, _ = make_pacer()
    pacer.pause()
    pacer.resume()
    assert pacer.should_flush("Rest area in two miles.") is True
    # The purge is spent; the channel is trusted again from here.
    assert pacer.should_flush("Weigh station ahead.") is False


# -- the stop the player planned ------------------------------------------------


CHATTER = "Rain easing off, roads still wet."  # ~2.4s estimated


def test_route_priority_will_not_wait_out_a_backlog_of_chatter() -> None:
    """Tester Darren: planned stops get lost in the traffic chatter.

    Two pacers in identical states, so the only thing under test is the
    priority the line was submitted with.
    """
    stop_line = "Planned stop, Iowa 80 Truckstop at Exit 284 in five miles."

    ambient, _ = make_pacer()
    ambient.should_flush(CHATTER)
    # Behind one piece of chatter, another informational line is content to
    # wait its turn -- nothing is lost by hearing it a few seconds later.
    assert ambient.should_flush(stop_line, EventPriority.AMBIENT) is False

    route, _ = make_pacer()
    route.should_flush(CHATTER)
    # The same line as a planned stop has an exit to make, so it goes in
    # front of the chatter instead of behind it.
    assert route.should_flush(stop_line, EventPriority.ROUTE) is True


def test_route_priority_still_queues_behind_a_quiet_channel() -> None:
    pacer, _ = make_pacer()
    # Nothing is speaking: a route line has no reason to cut anything off.
    assert pacer.should_flush("Rest area in two miles.", EventPriority.ROUTE) is False


# -- through ctx.say_event, the way the road reaches the player -----------------


def test_say_event_speaks_a_repeated_event_once() -> None:
    from freight_fate.app import App

    app = App()
    try:
        calls: list[str] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech.say_event = speech_stub(calls)
        for _ in range(3):  # the burst the tester heard in six tenths of a second
            app.ctx.say_event(SIDESWIPE, interrupt=True)
        assert calls == [SIDESWIPE]
        # And a suppressed repeat is not left in the review history either.
        assert [m.text for m in app.ctx.message_log.messages].count(SIDESWIPE) == 1
    finally:
        app.shutdown()


def test_say_event_standing_condition_speaks_again_only_when_it_worsens() -> None:
    from freight_fate.app import App

    app = App()
    try:
        calls: list[str] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech.say_event = speech_stub(calls)
        clock = FakeClock()
        app.ctx._event_pacer = EventSpeechPacer(clock=clock)

        at_45 = "The load has shifted hard and is badly damaged, 45 percent."
        at_60 = "The load has shifted hard and is badly damaged, 60 percent."
        app.ctx.say_event(at_45, interrupt=True, key="cargo_condition")
        for _ in range(4):  # the rest of the drive, nothing about it changing
            clock.now += 10.0
            app.ctx.say_event(at_45, interrupt=True, key="cargo_condition")
        clock.now += 10.0
        app.ctx.say_event(at_60, interrupt=True, key="cargo_condition")

        assert calls == [at_45, at_60]
    finally:
        app.shutdown()


def test_say_event_forced_line_is_heard_even_when_it_repeats() -> None:
    """A status key answers every press, repeat or not."""
    from freight_fate.app import App

    app = App()
    try:
        calls: list[str] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech.say_event = speech_stub(calls)
        line = "Load secure."
        app.ctx.say_event(line, interrupt=True)
        app.ctx.say_event(line, interrupt=True, force=True)
        assert calls == [line, line]
    finally:
        app.shutdown()


def test_pausing_silences_the_road_and_resuming_does_not_replay_it() -> None:
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        stopped: list[str] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech.say_event = speech_stub(calls, with_interrupt=True)
        app.ctx.speech.stop_event = lambda: stopped.append("stopped")

        app.ctx.say_event("Travel plaza in five miles.", interrupt=False)
        app.ctx.say_event("Rain easing off, roads still wet.", interrupt=False)

        app.ctx.pause_event_speech()
        # Silencing the channel is what actually purges the voice's own queue;
        # without it the backlog is simply performed on the way back.
        assert stopped, "pausing left the event voice holding the road's backlog"

        app.ctx.resume_event_speech()
        app.ctx.say_event("Speed limit reduced to 55 miles per hour.", interrupt=False)
        # The first line back purges rather than queueing behind anything that
        # survived the pause.
        assert calls[-1] == ("Speed limit reduced to 55 miles per hour.", True)
    finally:
        app.shutdown()


# -- routing: which announcements are chatter and which are the drive ----------


def _stop_event(planned: bool):
    from types import SimpleNamespace

    from freight_fate.sim.trip import TripEventKind

    return SimpleNamespace(
        kind=TripEventKind.STOP_AHEAD,
        message="Planned stop, Iowa 80 Truckstop at Exit 284 in five miles.",
        data={"planned": planned},
    )


def _router():
    from freight_fate.states.driving_events import DrivingEventMixin

    class Router(DrivingEventMixin):
        pass

    return Router()


def test_a_planned_stop_never_goes_through_the_ambient_channel() -> None:
    """The one-deep ambient slot is where planned stops were being lost.

    A later piece of chatter overwrote the waiting notice, and a hazard threw
    it away outright, so the player drove past a stop they had chosen.
    """
    router = _router()
    assert router._should_space_ambient_event(_stop_event(planned=True)) is False
    # An ordinary travel-plaza notice is still informational and still spaced.
    assert router._should_space_ambient_event(_stop_event(planned=False)) is True


def test_stop_announcements_carry_route_priority() -> None:
    """Both kinds of stop notice are the drive, not colour.

    The planned one additionally skips the ambient spacing above; an ordinary
    travel-plaza notice still waits its turn, but when its turn comes it does
    not queue behind chatter either.
    """
    router = _router()
    assert router._event_priority(_stop_event(planned=True)) is EventPriority.ROUTE
    assert router._event_priority(_stop_event(planned=False)) is EventPriority.ROUTE


def test_driving_past_a_planned_stop_carries_route_priority() -> None:
    """The plan being cancelled is route news, not roadside colour."""
    from types import SimpleNamespace

    from freight_fate.sim.trip import TripEventKind

    event = SimpleNamespace(
        kind=TripEventKind.GPS_CUE,
        message="You drove past your planned stop, Iowa 80 Truckstop. Plan cancelled.",
        data={"planned": True},
    )
    assert _router()._event_priority(event) is EventPriority.ROUTE


def test_roadside_chatter_stays_ambient() -> None:
    from types import SimpleNamespace

    from freight_fate.sim.trip import TripEventKind

    event = SimpleNamespace(
        kind=TripEventKind.WEATHER_CHANGE,
        message="Rain easing off, roads still wet.",
        data={},
    )
    assert _router()._event_priority(event) is EventPriority.AMBIENT


# -- the player path: pause menu in, pause menu out ----------------------------


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Pacer", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(
        CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles,
        1000.0,
        12.0,
        destination_location="Rochester freight market",
    )
    return DrivingState(app.ctx, job, route, phase="delivery")


def test_the_pause_menu_drops_what_the_road_was_about_to_say() -> None:
    """Player paused mid-run and heard the last minute over again on resume."""
    from freight_fate.app import App
    from freight_fate.states.driving_pause_states import PauseMenuState

    app = App()
    try:
        driving = _driving(app)
        stopped: list[str] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech.say_event = speech_stub()
        app.ctx.speech.stop_event = lambda: stopped.append("stopped")
        driving._pending_ambient_event = ("Rain easing off, roads still wet.", None)

        pause = PauseMenuState(app.ctx, driving)
        app.push_state(pause)  # enter(): the player opened the pause menu
        assert stopped, "the event voice kept the road's backlog through the pause"
        assert driving._pending_ambient_event is None

        # Nothing that arrived while the menu was up survives the way back.
        driving._pending_ambient_event = ("Passing the fuel island.", None)
        pause._resume()
        assert driving._pending_ambient_event is None
    finally:
        app.shutdown()
