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


def test_say_event_flushes_a_stale_route_backlog_end_to_end() -> None:
    """ctx.say_event: a burst of queued ROUTE events turns into an
    interrupting (channel-purging) delivery once the backlog goes stale --
    the drive is never dropped, staleness only changes its delivery."""
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
            app.ctx.say_event(line, interrupt=False, priority=EventPriority.ROUTE)

        assert all(not interrupt for _, interrupt in calls[:1])
        assert any(interrupt for _, interrupt in calls), (
            "a stale backlog was performed in full -- the pacer never flushed"
        )
        # Every line still reached the voice in order; for ROUTE, staleness
        # changes delivery, never drops the newest information.
        assert [text for text, _ in calls] == approach
    finally:
        app.shutdown()


def test_stale_ambient_chatter_is_dropped_not_promoted() -> None:
    """R1: chatter that would start speaking after the moment it described
    is discarded silently -- the old stale-flush promoted it to an
    interrupt, making the least important class the only one guaranteed to
    preempt. The review log still keeps the dropped line."""
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech.say_event = speech_stub(calls, with_interrupt=True)
        clock = FakeClock()
        app.ctx._event_pacer = EventSpeechPacer(clock=clock)

        app.ctx.say_event(LONG_LINE, interrupt=False)  # ~10s of speaking
        app.ctx.say_event(CHATTER, interrupt=False)  # would start far too late

        assert calls == [(LONG_LINE, False)], "stale chatter reached the voice"
        # Dropped from the air, kept in the log: recovery is what it is for.
        assert any(m.text == CHATTER for m in app.ctx.message_log.messages)
        # Never marked heard either: the player did not hear it, so the same
        # observation made fresh later speaks normally.
        clock.now += 30.0
        app.ctx.say_event(CHATTER, interrupt=False)
        assert calls[-1] == (CHATTER, False)
    finally:
        app.shutdown()


def test_would_start_stale_is_a_pure_reading() -> None:
    pacer, _ = make_pacer()
    pacer.should_flush(LONG_LINE)
    assert pacer.would_start_stale(CHATTER) is True
    # Pure: asking did not extend the projection or consume anything.
    assert pacer.would_start_stale(CHATTER) is True
    quiet, _ = make_pacer()
    assert quiet.would_start_stale(CHATTER) is False


def test_the_post_pause_purge_is_not_read_as_staleness() -> None:
    """The first line back from a pause must purge and speak, never drop."""
    pacer, clock = make_pacer()
    pacer.should_flush(LONG_LINE)
    pacer.pause()
    clock.now += 45.0
    assert pacer.would_start_stale(CHATTER) is False
    assert pacer.should_flush(CHATTER) is True


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


# -- the line the interrupt stepped on (tester report, 2026-08-12) --------------
#
# A hazard, a curve call, or an info key landing while the voice was mid-way
# through "Open weigh station ahead" destroyed the announcement outright: the
# purge that delivers an interrupting line took the queue with it, and nothing
# gave the cut line back. A tester blew a weigh station that way. The pacer
# now hands the cut ROUTE or CRITICAL line back so it queues right behind the
# line that cut it -- safety line first, then the line it stepped on.


STOP_LINE = "Planned stop, Iowa 80 Truckstop at Exit 284 in five miles."
HAZARD = "Hazard! Stopped traffic ahead."


def test_interrupt_hands_back_a_cut_route_line() -> None:
    pacer, _ = make_pacer()
    pacer.should_flush(STOP_LINE, EventPriority.ROUTE)
    assert pacer.note_interrupt(HAZARD) == (STOP_LINE, EventPriority.ROUTE)


def test_a_route_line_that_finished_is_not_handed_back() -> None:
    pacer, clock = make_pacer()
    pacer.should_flush(STOP_LINE, EventPriority.ROUTE)
    clock.now += 30.0  # the voice long since read it out in full
    assert pacer.note_interrupt(HAZARD) is None


def test_ambient_chatter_is_never_handed_back() -> None:
    pacer, _ = make_pacer()
    pacer.should_flush(CHATTER)  # AMBIENT: missing it costs the player nothing
    assert pacer.note_interrupt(HAZARD) is None


def test_a_critical_line_cut_by_another_critical_is_handed_back() -> None:
    pacer, _ = make_pacer()
    first = "Emergency vehicle approaching from behind. Move right."
    assert pacer.note_interrupt(first) is None  # quiet channel: nothing was cut
    assert pacer.note_interrupt(HAZARD) == (first, EventPriority.CRITICAL)


def test_a_line_interrupting_itself_is_not_handed_back() -> None:
    """The one-line ping-pong: A cutting A must not requeue A behind A."""
    pacer, _ = make_pacer()
    pacer.should_flush(STOP_LINE, EventPriority.ROUTE)
    assert pacer.note_interrupt(STOP_LINE) is None


def test_the_hand_back_happens_at_most_once_per_cut() -> None:
    pacer, _ = make_pacer()
    pacer.should_flush(STOP_LINE, EventPriority.ROUTE)
    assert pacer.note_interrupt(HAZARD) == (STOP_LINE, EventPriority.ROUTE)
    # The slot emptied with the hand-back and now holds the hazard: a further
    # interrupt rescues the line it lands on, never the stop line twice.
    assert pacer.note_interrupt("Sharp curve ahead.") == (HAZARD, EventPriority.CRITICAL)


def test_a_rescued_line_is_not_rescued_again_by_the_next_cut() -> None:
    """The trooper-escalation loop from the 21 August build note: a rescued
    line is requeued and re-protected, so a CHAIN of urgent lines used to
    replay it after every one -- "Signal for the scale exit" spoke five
    times. One rescue per line per window; the second cut drops it."""
    pacer, _ = make_pacer()
    escalations = [f"Failure to stop, warning {n}." for n in range(1, 6)]
    pacer.should_flush(STOP_LINE, EventPriority.ROUTE)
    rescues = 0
    for warning in escalations:
        cut = pacer.note_interrupt(warning)
        if cut is not None and cut[0] == STOP_LINE:
            rescues += 1
            # the app requeues the rescue behind the warning, re-protecting it
            pacer.note_queued(*cut)
    assert rescues == 1, f"the stop line was replayed {rescues} times"


def test_the_same_words_minutes_later_earn_a_fresh_rescue() -> None:
    """The cap is a window, not a life sentence: a genuinely new moment that
    happens to use the same words is cut and rescued like any other."""
    pacer, clock = make_pacer()
    pacer.should_flush(STOP_LINE, EventPriority.ROUTE)
    cut = pacer.note_interrupt(HAZARD)
    assert cut == (STOP_LINE, EventPriority.ROUTE)
    pacer.note_queued(*cut)
    clock.now += pacer.RESCUE_ONCE_WINDOW_S + 1.0
    pacer.should_flush(STOP_LINE, EventPriority.ROUTE)
    assert pacer.note_interrupt(HAZARD) == (STOP_LINE, EventPriority.ROUTE)


def test_say_event_requeues_the_route_line_a_hazard_cut() -> None:
    """ctx.say_event: safety line first, then the line it stepped on."""
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech.say_event = speech_stub(calls, with_interrupt=True)
        app.ctx._event_pacer = EventSpeechPacer(clock=FakeClock())

        app.ctx.say_event(STOP_LINE, interrupt=False, priority=EventPriority.ROUTE)
        app.ctx.say_event(HAZARD, interrupt=True)

        assert calls == [(STOP_LINE, False), (HAZARD, True), (STOP_LINE, False)]
        # Requeued, not re-reported: the review log still holds it once.
        assert [m.text for m in app.ctx.message_log.messages].count(STOP_LINE) == 1
    finally:
        app.shutdown()


def test_say_event_leaves_a_finished_route_line_alone() -> None:
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech.say_event = speech_stub(calls, with_interrupt=True)
        clock = FakeClock()
        app.ctx._event_pacer = EventSpeechPacer(clock=clock)

        app.ctx.say_event(STOP_LINE, interrupt=False, priority=EventPriority.ROUTE)
        clock.now += 30.0  # heard in full long before the hazard
        app.ctx.say_event(HAZARD, interrupt=True)

        assert calls == [(STOP_LINE, False), (HAZARD, True)]
    finally:
        app.shutdown()


def test_a_repeated_hazard_cannot_ping_pong_the_requeue() -> None:
    """The same hazard firing in a burst is one cut, one requeue -- the
    repeat suppression drops the copies before they reach the channel."""
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech.say_event = speech_stub(calls, with_interrupt=True)
        app.ctx._event_pacer = EventSpeechPacer(clock=FakeClock())

        app.ctx.say_event(STOP_LINE, interrupt=False, priority=EventPriority.ROUTE)
        for _ in range(3):
            app.ctx.say_event(HAZARD, interrupt=True)

        assert calls.count((HAZARD, True)) == 1
        assert calls.count((STOP_LINE, False)) == 2  # the original and one requeue
    finally:
        app.shutdown()


def test_a_requeued_line_cut_again_is_dropped_not_replayed() -> None:
    """Two genuine warnings in a row do not destroy the stop notice -- it is
    rescued once and finishes -- but they do not replay it either. This test
    used to pin the opposite (a rescue after EVERY cut); the 21 August build
    note ruled the repeat the bug: a chain of five trooper warnings spoke
    "Signal for the scale exit" five times. One rescue is the contract."""
    from freight_fate.app import App

    app = App()
    try:
        calls: list[tuple[str, bool]] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech.say_event = speech_stub(calls, with_interrupt=True)
        app.ctx._event_pacer = EventSpeechPacer(clock=FakeClock())

        app.ctx.say_event(STOP_LINE, interrupt=False, priority=EventPriority.ROUTE)
        app.ctx.say_event(HAZARD, interrupt=True)
        app.ctx.say_event("Emergency vehicle approaching from behind.", interrupt=True)

        assert calls.count((STOP_LINE, False)) == 2  # original, one rescue
    finally:
        app.shutdown()


# -- info keys on a shared voice (tester report, 2026-08-12) --------------------
#
# When events ride the main channel -- the player chose the main voice for
# them, or no separate voice could be bound -- an info key's reply interrupts
# whatever event line was mid-sentence there. The reply still answers first;
# the cut ROUTE or CRITICAL line queues right behind it.


SCALE_LINE = "Open weigh station ahead in two miles. All trucks must pull in."
INFO_REPLY = "Fifty five miles per hour."


def test_info_reply_on_the_main_voice_requeues_the_cut_event_line() -> None:
    from freight_fate.app import App

    app = App()
    try:
        main: list[tuple[str, bool]] = []
        app.ctx.settings.sapi_events = False  # events through the main voice
        app.ctx.speech.say = speech_stub(main, with_interrupt=True)
        app.ctx._event_pacer = EventSpeechPacer(clock=FakeClock())

        app.ctx.say_event(SCALE_LINE, interrupt=False, priority=EventPriority.ROUTE)
        app.ctx.say(INFO_REPLY)  # an info key answering, interrupt=True default

        assert main == [(SCALE_LINE, False), (INFO_REPLY, True), (SCALE_LINE, False)]
    finally:
        app.shutdown()


def test_info_reply_requeues_when_no_separate_event_voice_bound() -> None:
    """The player asked for a dedicated event voice but Prism bound none, so
    events fall back to the main channel and need the same protection."""
    from freight_fate.app import App

    app = App()
    try:
        main: list[tuple[str, bool]] = []
        events: list[tuple[str, bool]] = []
        app.ctx.settings.sapi_events = True  # asked for, but no backend bound
        app.ctx.speech.say = speech_stub(main, with_interrupt=True)
        app.ctx.speech.say_event = speech_stub(events, with_interrupt=True)
        app.ctx._event_pacer = EventSpeechPacer(clock=FakeClock())

        app.ctx.say_event(SCALE_LINE, interrupt=False, priority=EventPriority.ROUTE)
        app.ctx.say(INFO_REPLY)

        assert main == [(INFO_REPLY, True)]
        assert events == [(SCALE_LINE, False), (SCALE_LINE, False)]  # cut, requeued
    finally:
        app.shutdown()


def test_info_reply_with_a_dedicated_event_voice_leaves_the_road_alone() -> None:
    from freight_fate.app import App

    app = App()
    try:
        main: list[tuple[str, bool]] = []
        events: list[tuple[str, bool]] = []
        app.ctx.settings.sapi_events = True
        app.ctx.speech._event_backend = object()  # a separate voice is bound
        app.ctx.speech.say = speech_stub(main, with_interrupt=True)
        app.ctx.speech.say_event = speech_stub(events, with_interrupt=True)
        app.ctx._event_pacer = EventSpeechPacer(clock=FakeClock())

        app.ctx.say_event(SCALE_LINE, interrupt=False, priority=EventPriority.ROUTE)
        app.ctx.say(INFO_REPLY)

        # Two channels, two voices: the reply cannot cut the event line, so
        # nothing is requeued.
        assert main == [(INFO_REPLY, True)]
        assert events == [(SCALE_LINE, False)]
    finally:
        app.shutdown()


# -- instructions to act ride ROUTE, not chatter --------------------------------


def test_drowsy_warning_carries_route_priority(monkeypatch) -> None:
    """ "Take a break or sleep" is an instruction, not roadside colour: it
    must survive being talked over."""
    from freight_fate.app import App
    from freight_fate.sim import hos

    app = App()
    try:
        driving = _driving(app)
        events: list[tuple[str, dict]] = []
        monkeypatch.setattr(app.ctx, "say_event", lambda text, *a, **k: events.append((text, k)))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        monkeypatch.setattr(driving.hos, "check_warnings", lambda mode: [])
        app.ctx.profile.fatigue = hos.FATIGUE_DROWSY + 1.0

        driving._update_hours_and_fatigue(0.1)

        _, kwargs = next((t, k) for t, k in events if "drowsy" in t)
        assert kwargs.get("priority") is EventPriority.ROUTE
        assert kwargs.get("interrupt") is False
    finally:
        app.shutdown()


def test_non_urgent_hos_warning_carries_route_priority(monkeypatch) -> None:
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving(app)
        events: list[tuple[str, dict]] = []
        monkeypatch.setattr(app.ctx, "say_event", lambda text, *a, **k: events.append((text, k)))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx.controller.rumble, "alert", lambda: None)
        warning = "30 minutes of drive time left. Plan a break soon."
        monkeypatch.setattr(driving.hos, "check_warnings", lambda mode: [warning])

        driving._update_hours_and_fatigue(0.1)

        _, kwargs = next((t, k) for t, k in events if t == warning)
        assert kwargs.get("priority") is EventPriority.ROUTE
        assert kwargs.get("interrupt") is False
    finally:
        app.shutdown()


def test_urgent_hos_violation_still_interrupts(monkeypatch) -> None:
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving(app)
        events: list[tuple[str, dict]] = []
        monkeypatch.setattr(app.ctx, "say_event", lambda text, *a, **k: events.append((text, k)))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx.controller.rumble, "alert", lambda: None)
        warning = "Hours of service violation: 11 hours of driving used up."
        monkeypatch.setattr(driving.hos, "check_warnings", lambda mode: [warning])

        driving._update_hours_and_fatigue(0.1)

        _, kwargs = next((t, k) for t, k in events if t == warning)
        assert kwargs.get("interrupt") is True
        assert kwargs.get("priority") is EventPriority.CRITICAL
    finally:
        app.shutdown()


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
        driving._speak_ambient_event("Rain easing off, roads still wet.")

        pause = PauseMenuState(app.ctx, driving)
        app.push_state(pause)  # enter(): the player opened the pause menu
        assert stopped, "the event voice kept the road's backlog through the pause"
        assert not driving._pending_ambient_events

        # Nothing that arrived while the menu was up survives the way back.
        driving._speak_ambient_event("Passing the fuel island.")
        pause._resume()
        assert not driving._pending_ambient_events
    finally:
        app.shutdown()


# -- a chimed line is never silently lost (tester Sarah, US-12 East, 2026-08-14)


LANE_CLOSURE_LINE = (
    "Traffic squeezing at the construction taper in a quarter mile. "
    "Merge left early and leave a gap."
)


def test_a_hazard_no_longer_costs_the_driver_the_line_that_was_waiting() -> None:
    """Sarah, US-12 East, 2026-08-14: a lane closure dinged and vanished.

    The first fix kept the line in review, which stopped it being lost
    outright but still left her hearing a chime with no words. The hazard
    branch used to empty the one-deep ambient slot the moment it fired.

    It no longer does. The hazard holds the channel while it is live, the
    waiting line stays queued behind it, and when the road clears the
    driver hears what the ding was for. Review has it either way -- it is
    logged when it queues, not when it speaks.
    """
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        driving = _driving(app)
        played: list[tuple] = []
        events: list[tuple[str, bool]] = []
        driving.ctx.audio.play = lambda *a, **k: played.append(a)
        driving.ctx.say_event = speech_stub(events, with_interrupt=True)
        driving.ctx.controller.rumble.hazard = lambda: None

        # A lane-closure line already deferred into the ambient queue --
        # queued (and logged) behind chatter whose spacing had not cleared.
        driving._ambient_event_cooldown_s = 5.0
        driving._speak_ambient_event(LANE_CLOSURE_LINE, "events/traffic_slowing")
        assert [p.message for p in driving._pending_ambient_events] == [LANE_CLOSURE_LINE]
        played.clear()

        driving._handle_trip_event(
            TripEvent(
                TripEventKind.HAZARD,
                "Brake now! Stopped traffic ahead.",
                {"deadline_s": 4.0, "dodgeable": False, "name": "the stopped traffic"},
            )
        )

        # The hazard's own ding rang, and it still owns the channel:
        # nothing ambient speaks over a live hazard.
        assert any(call and call[0] == "events/hazard_warning" for call in played)
        assert all(text != LANE_CLOSURE_LINE for text, _ in events)
        # But the line is still there rather than discarded.
        assert [p.message for p in driving._pending_ambient_events] == [LANE_CLOSURE_LINE]

        # Hazard over, spacing clear: she hears what the ding was for.
        driving._hazard_deadline = None
        driving._ambient_event_cooldown_s = 0.0
        driving._update_ambient_events(0.1)
        assert any(text == LANE_CLOSURE_LINE for text, _ in events)
        # And review has it either way, logged when it queued.
        assert LANE_CLOSURE_LINE in [m.text for m in app.ctx.message_log.messages]
    finally:
        app.shutdown()


def test_a_second_ambient_line_no_longer_lands_on_top_of_the_first() -> None:
    """The other half of the single-slot bug: no hazard involved, just a
    second piece of ambient colour arriving before the cooldown holding
    both of them open clears.

    The first line used to be overwritten and never spoken. It keeps its
    place in the queue now and both are said, oldest first, which is what
    lets a mapped state line survive an interstate's chatter.
    """
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving(app)
        driving.ctx.audio.play = lambda *a, **k: None
        driving.ctx.say_event = lambda *a, **k: None
        driving._ambient_event_cooldown_s = 5.0  # still busy: both lines defer

        driving._speak_ambient_event("Rain easing off, roads still wet.", None)
        driving._speak_ambient_event("Passing the fuel island.", "ui/notify")

        # Both are waiting, in the order they happened.
        assert [p.message for p in driving._pending_ambient_events] == [
            "Rain easing off, roads still wet.",
            "Passing the fuel island.",
        ]
        # And both reached the review buffer when they queued.
        logged = [m.text for m in app.ctx.message_log.messages]
        assert "Rain easing off, roads still wet." in logged
        assert "Passing the fuel island." in logged
    finally:
        app.shutdown()


def test_speaking_a_drained_ambient_line_does_not_log_it_twice() -> None:
    """The line that does make it to speech was already logged when it
    queued; the drain call must not add it to review a second time."""
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving(app)
        driving.ctx.audio.play = lambda *a, **k: None
        driving.ctx.say_event = lambda *a, **k: None
        driving._ambient_event_cooldown_s = 5.0

        driving._speak_ambient_event("Rain easing off, roads still wet.", None)
        driving._ambient_event_cooldown_s = 0.0
        driving._hazard_deadline = None
        driving._update_ambient_events(0.0)

        logged = [m.text for m in app.ctx.message_log.messages]
        assert logged.count("Rain easing off, roads still wet.") == 1
    finally:
        app.shutdown()


def _lane_closure_event():
    from types import SimpleNamespace

    from freight_fate.sim.trip import TripEventKind

    pressure = SimpleNamespace(kind="construction_merge", direction="left")
    return SimpleNamespace(
        kind=TripEventKind.GPS_CUE,
        message=LANE_CLOSURE_LINE,
        data={"traffic_pressure": pressure},
    )


def test_a_lane_closure_merge_call_is_demoted_out_of_the_ambient_slot() -> None:
    """A construction-taper merge call is act-soon, same family as a zone
    entry or a checkpoint: it must never reach the one-deep ambient slot,
    where a hazard or the next piece of colour can erase it."""
    router = _router()
    event = _lane_closure_event()
    assert router._demoted_from_interrupt(event) is True
    assert router._event_priority(event) is EventPriority.ROUTE


def test_ordinary_traffic_pack_pressure_stays_ambient() -> None:
    """Only the construction-taper merge call is promoted; routine traffic
    colour (a pack, an exit building) still rides the ambient channel."""
    from types import SimpleNamespace

    from freight_fate.sim.trip import TripEventKind

    router = _router()
    pressure = SimpleNamespace(kind="route_merge", direction="right")
    event = SimpleNamespace(
        kind=TripEventKind.GPS_CUE,
        message="Merging traffic in a quarter mile. Keep right, leave a gap.",
        data={"traffic_pressure": pressure},
    )
    assert router._demoted_from_interrupt(event) is False
    assert router._event_priority(event) is EventPriority.AMBIENT


def test_a_lane_closure_merge_call_never_enters_the_ambient_queue() -> None:
    """End to end: even while a hazard has the ambient channel busy, the
    lane-closure merge call bypasses the ambient queue altogether
    and rides ROUTE's never-dropped queue instead."""
    from types import SimpleNamespace

    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        driving = _driving(app)
        events: list[tuple[str, dict]] = []
        driving.ctx.audio.play = lambda *a, **k: None
        driving.ctx.say_event = lambda text, *a, **k: events.append((text, k))
        driving._hazard_deadline = 2.0  # the channel is currently busy

        pressure = SimpleNamespace(kind="construction_merge", direction="left")
        driving._handle_trip_event(
            TripEvent(
                TripEventKind.GPS_CUE,
                LANE_CLOSURE_LINE,
                {"traffic_pressure": pressure},
            )
        )

        assert not driving._pending_ambient_events
        text, kwargs = events[0]
        assert text == LANE_CLOSURE_LINE
        assert kwargs.get("priority") is EventPriority.ROUTE
        assert kwargs.get("interrupt") is False
    finally:
        app.shutdown()


# -- terse speech: the same loss, and the review record it must not lose -------
#
# Sarah runs terse verbosity. Zone, warning, and closure lines are plain
# strings (never a SpokenMessage pair), so terse mode cannot shorten or
# silence them the way it can a hazard call or a stop callout -- there is no
# terse rendering for them to collapse into. That makes the following pin
# down two different things: the ambient-slot loss above reproduces
# identically under terse (it never depended on verbosity), and separately,
# ``_speak_ambient_event`` -- the mechanism the fix lives in -- still honors
# a genuinely terse-silenced line (an earcon-only preview, ``terse=""``)
# rather than starting to log lines the player's speech mode says were never
# said at all.


def test_hazard_survival_works_identically_under_terse_speech() -> None:
    """Same bug, same fix, independent of verbosity: the closure line was
    never a SpokenMessage, so terse never touched whether it spoke or
    logged -- confirming the loss (and the fix) is not verbosity-specific."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        driving = _driving(app)
        app.ctx.settings.driving_speech = "quiet"  # terse
        events: list[tuple[str, bool]] = []
        driving.ctx.audio.play = lambda *a, **k: None
        driving.ctx.say_event = speech_stub(events, with_interrupt=True)
        driving.ctx.controller.rumble.hazard = lambda: None
        driving._ambient_event_cooldown_s = 5.0
        driving._speak_ambient_event(LANE_CLOSURE_LINE, "events/traffic_slowing")
        assert [p.message for p in driving._pending_ambient_events] == [LANE_CLOSURE_LINE]

        driving._handle_trip_event(
            TripEvent(
                TripEventKind.HAZARD,
                "Brake now! Stopped traffic ahead.",
                {"deadline_s": 4.0, "dodgeable": False, "name": "the stopped traffic"},
            )
        )

        # Not spoken over the hazard, and not thrown away either.
        assert all(text != LANE_CLOSURE_LINE for text, _ in events)
        driving._hazard_deadline = None
        driving._ambient_event_cooldown_s = 0.0
        driving._update_ambient_events(0.1)
        assert any(text == LANE_CLOSURE_LINE for text, _ in events)
        # The full text -- there is only one rendering -- is in review.
        assert LANE_CLOSURE_LINE in [m.text for m in app.ctx.message_log.messages]
    finally:
        app.shutdown()


def test_a_lane_closure_merge_call_reaches_review_in_full_under_terse() -> None:
    """End to end under terse speech: the promoted ROUTE priority still
    delivers the closure call, in full, with nothing shortened away."""
    from types import SimpleNamespace

    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        driving = _driving(app)
        app.ctx.settings.driving_speech = "quiet"  # terse
        events: list[tuple[str, dict]] = []
        driving.ctx.audio.play = lambda *a, **k: None
        driving.ctx.say_event = lambda text, *a, **k: events.append((text, k))
        driving._hazard_deadline = 2.0  # the channel is currently busy

        pressure = SimpleNamespace(kind="construction_merge", direction="left")
        driving._handle_trip_event(
            TripEvent(
                TripEventKind.GPS_CUE,
                LANE_CLOSURE_LINE,
                {"traffic_pressure": pressure},
            )
        )

        assert not driving._pending_ambient_events
        text, kwargs = events[0]
        assert text == LANE_CLOSURE_LINE  # full text; nothing to shorten it into
        assert kwargs.get("priority") is EventPriority.ROUTE
    finally:
        app.shutdown()


def test_speak_ambient_event_still_honors_a_true_terse_mute_for_logging() -> None:
    """The fix logs at queue time, but it must not start logging lines the
    player's own speech mode says were never said at all -- an earcon-only
    preview (``terse=""``) stays out of review under terse, exactly as it
    already was before a hazard or overwrite ever entered the picture."""
    from freight_fate.app import App
    from freight_fate.speech_text import terse_silent

    app = App()
    try:
        driving = _driving(app)
        app.ctx.settings.driving_speech = "quiet"  # terse
        driving.ctx.audio.play = lambda *a, **k: None
        driving.ctx.say_event = lambda *a, **k: None
        before = len(app.ctx.message_log.messages)

        driving._speak_ambient_event(
            terse_silent("Toll ahead in two miles."), "events/toll_charged"
        )

        assert len(app.ctx.message_log.messages) == before
    finally:
        app.shutdown()


def test_speak_ambient_event_logs_the_full_text_not_the_terse_text() -> None:
    """A line terse only shortens (never silences) still reaches review in
    its full, normal wording -- review answers "what did I miss", not
    "what did terse mode just say"."""
    from freight_fate.app import App
    from freight_fate.speech_text import SpokenMessage

    app = App()
    try:
        driving = _driving(app)
        app.ctx.settings.driving_speech = "quiet"  # terse
        driving.ctx.audio.play = lambda *a, **k: None
        driving.ctx.say_event = lambda *a, **k: None
        pair = SpokenMessage(
            "Planned stop, Iowa 80 Truckstop at Exit 284 in five miles. "
            "Parking confirmed. Press X to signal for the exit.",
            "Iowa 80 Truckstop, Exit 284, five miles. Parking confirmed.",
        )

        driving._speak_ambient_event(pair, "ui/notify")

        logged = [m.text for m in app.ctx.message_log.messages]
        assert pair.normal in logged
        assert pair.terse not in logged
    finally:
        app.shutdown()


def test_a_confirmation_never_takes_the_hand_back_slot() -> None:
    """It answers something the player did; it is not a warning to rescue.

    Confirmations default to CRITICAL, so they used to qualify -- and then
    the next interrupting line on the main channel handed the FINISHED
    confirmation back to be requeued, where it resurfaced after, and could
    bury, the line the player had actually just asked for. The adversarial
    harness found it on settings_flips_mid_drive; pressed keys interrupting
    again (2026-08-16) turned it from rare into every info key.
    """
    from freight_fate.speech_pacing import SpeechCategory

    pacer, _ = make_pacer()
    confirmation = "Transmission changed to manual."
    assert (
        pacer.note_interrupt(confirmation, EventPriority.CRITICAL, SpeechCategory.CONFIRMATION)
        is None
    )
    # The S query that follows gets the channel to itself.
    assert pacer.note_interrupt(HAZARD) is None


def test_a_warning_is_still_handed_back_after_the_confirmation_rule() -> None:
    """The slot still does its job for the lines it was built for."""
    pacer, _ = make_pacer()
    pacer.should_flush(STOP_LINE, EventPriority.ROUTE)
    assert pacer.note_interrupt(HAZARD) == (STOP_LINE, EventPriority.ROUTE)


def test_a_line_that_waited_out_a_long_hazard_is_dropped_not_performed_late() -> None:
    """What keeps the queue from becoming a recital.

    The one-deep slot's crude virtue was that a long hazard could not bank
    anything: it threw the waiting line away. A queue that kept everything
    would answer a cleared hazard with a monologue about miles the truck has
    already left. Age is the replacement for that, and it is measured in
    real seconds because the wait happens in the player's ear.

    Dropped from the ear only: the line was logged when it queued, so review
    still answers for it. That is the guarantee Sarah's report bought and it
    survives here unchanged.
    """
    from freight_fate.app import App
    from freight_fate.states.driving_events import AMBIENT_QUEUE_MAX_AGE_S

    app = App()
    try:
        driving = _driving(app)
        events: list[tuple[str, bool]] = []
        driving.ctx.audio.play = lambda *a, **k: None
        driving.ctx.say_event = speech_stub(events, with_interrupt=True)

        driving._hazard_deadline = 30.0
        driving._speak_ambient_event("Passing the fuel island.", "ui/notify")
        assert driving._pending_ambient_events

        # A hazard that runs longer than the line stays true for.
        driving._update_ambient_events(AMBIENT_QUEUE_MAX_AGE_S + 0.1)
        assert not driving._pending_ambient_events

        driving._hazard_deadline = None
        driving._ambient_event_cooldown_s = 0.0
        driving._update_ambient_events(0.1)
        assert all(text != "Passing the fuel island." for text, _ in events)
        # Still reviewable, as it always was.
        assert "Passing the fuel island." in [m.text for m in app.ctx.message_log.messages]
    finally:
        app.shutdown()


def test_the_ambient_queue_is_bounded_and_drops_the_stalest_first() -> None:
    """A bound as well as an age, because a busy interstate can out-produce
    the drain even without a hazard. When it overflows the OLDEST goes: the
    same reasoning as the age cap, applied to depth instead of time."""
    from freight_fate.app import App
    from freight_fate.states.driving_events import AMBIENT_QUEUE_MAX

    app = App()
    try:
        driving = _driving(app)
        driving.ctx.audio.play = lambda *a, **k: None
        driving.ctx.say_event = lambda *a, **k: None
        driving._ambient_event_cooldown_s = 5.0

        for i in range(AMBIENT_QUEUE_MAX + 2):
            driving._speak_ambient_event(f"Ambient line {i}.")

        waiting = [p.message for p in driving._pending_ambient_events]
        assert len(waiting) == AMBIENT_QUEUE_MAX
        assert waiting[0] == "Ambient line 2."
        assert waiting[-1] == f"Ambient line {AMBIENT_QUEUE_MAX + 1}."
        # Everything queued reached review, including the two that fell off.
        logged = [m.text for m in app.ctx.message_log.messages]
        assert "Ambient line 0." in logged
        assert "Ambient line 1." in logged
    finally:
        app.shutdown()


def test_a_countdown_that_restates_itself_speaks_the_nearer_distance() -> None:
    """The FIFO must not make a waiting line WRONG.

    A CB call about a patrol post counts down as the truck closes: "in 5
    miles", then "in 4". Two moments would queue and both be said; this is
    one standing thing said again at a nearer distance, so the nearer
    wording replaces the further one where it already sits. Queueing both
    would say five when the driver is at four -- worse than the old
    single-slot overwrite, which got this case right by accident.
    """
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    sys_path_helper = __import__("enforcement_helpers")
    always_observing_post = sys_path_helper.always_observing_post

    app = App()
    try:
        driving = _driving(app)
        spoken: list[tuple[str, bool]] = []
        driving.ctx.audio.play = lambda *a, **k: None
        driving.ctx.say_event = speech_stub(spoken, with_interrupt=True)
        driving._ambient_event_cooldown_s = 5.0  # the channel is busy

        for miles, reach in ((5, 4.0), (4, 3.0)):
            driving._handle_trip_event(
                TripEvent(
                    TripEventKind.GPS_CUE,
                    f"CB chatter in {miles} miles: drivers report a bear ahead.",
                    {"cb_patrol": always_observing_post(at_mi=14.0, reach_mi=reach)},
                )
            )

        # One line waiting, carrying the nearer distance.
        waiting = [p.message for p in driving._pending_ambient_events]
        assert waiting == ["CB chatter in 4 miles: drivers report a bear ahead."]

        driving._ambient_event_cooldown_s = 0.0
        driving._update_ambient_events(0.1)
        assert spoken[-1][0] == "CB chatter in 4 miles: drivers report a bear ahead."
    finally:
        app.shutdown()


def test_two_different_moments_still_both_get_said() -> None:
    """The other side of the same rule, so supersession cannot creep.

    A billboard and a state line are two things that happened, not one
    thing restated, so neither replaces the other however close together
    they land. This is the case the single slot got wrong and the whole
    queue exists for.
    """
    from freight_fate.app import App

    app = App()
    try:
        driving = _driving(app)
        driving.ctx.audio.play = lambda *a, **k: None
        driving.ctx.say_event = lambda *a, **k: None
        driving._ambient_event_cooldown_s = 5.0

        driving._speak_ambient_event("Crossing into Ohio near the line on I-76.")
        driving._speak_ambient_event("Billboard: coffee at exit 4.")

        assert [p.message for p in driving._pending_ambient_events] == [
            "Crossing into Ohio near the line on I-76.",
            "Billboard: coffee at exit 4.",
        ]
    finally:
        app.shutdown()


def test_an_assist_changing_the_trucks_speed_is_never_dropped_as_chatter() -> None:
    """Tester Darren, I-75, 2026-08-18.

        [pacer] stale ambient dropped: Construction zone ahead;
                adaptive cruise easing to 45 miles per hour.

    Seventeen seconds later a trooper stopped him for the following gap that
    easing was closing. The truck slowed itself and never said why.

    An assist reporting that it is changing -- or handing back -- control of
    the truck is a consequence, not colour. It rides ROUTE's never-dropped
    contract, the same move the toll charge got for the same reason.
    """
    import inspect

    from freight_fate.speech_pacing import EventPriority
    from freight_fate.states import driving_events as de

    src = inspect.getsource(de.DrivingEventMixin)
    for line in (
        "adaptive cruise easing to",
        "Stopped traffic ahead; adaptive cruise canceled.",
        "Traffic ahead, adaptive cruise reducing speed.",
    ):
        assert line in src, line
        after = src.split(line, 1)[1][:400]
        assert "EventPriority.ROUTE" in after, f"{line!r} is not on the never-dropped channel"

    # And ROUTE really is the never-dropped channel: only AMBIENT is eligible
    # for the stale drop that binned Darren's line.
    assert EventPriority.ROUTE is not EventPriority.AMBIENT
    say_src = inspect.getsource(
        __import__("freight_fate.app", fromlist=["GameContext"]).GameContext.say_event
    )
    assert "priority == EventPriority.AMBIENT" in say_src


def test_no_never_dropped_line_rides_the_droppable_ambient_default() -> None:
    """R1's never-dropped contract, checked against the code rather than
    assumed from the table.

    The stale-ambient drop tests PRIORITY and never CATEGORY, so a SAFETY
    line that forgot to pass a priority defaulted to AMBIENT and became
    droppable -- in exactly the busy moment it matters most. Two were:
    the hazard follow-up "It is still in your lane. Nearly stop", and the
    reminder that you are still reversing down a live lane.

    Found in a pre-ship review, after the same bug class had already been
    caught twice in one day (an adaptive-cruise line, then the brake
    lockout the adversarial battery caught). Making the traffic channel
    busier is what turned a latent race into a real one.

    Widened to unrecoverable NAVIGATION when the same sweep found twelve
    more, among them "At <facility>. Stop to dock" and the gate warning that
    starts the miss clock -- the arrival half of the very bug that made a
    tester drive past a stop he had chosen on 2026-08-11. The approach notice
    was fixed then; the arrival call never was. NAVIGATION_ADVISORY stays out:
    the heads-up is droppable by design.
    """
    import pathlib
    import re

    offenders = []
    for path in sorted(pathlib.Path("src/freight_fate").rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        for match in re.finditer(r"say_event\(", src):
            seg = src[match.start() : match.start() + 800]
            depth = 0
            end = 0
            for i, ch in enumerate(seg):
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            call = seg[:end]
            # SAFETY and unrecoverable NAVIGATION both carry R1's
            # never-dropped contract. NAVIGATION_ADVISORY is the heads-up and
            # IS droppable by design, so it is excluded deliberately.
            unrecoverable = "SpeechCategory.SAFETY" in call or (
                "SpeechCategory.NAVIGATION" in call and "NAVIGATION_ADVISORY" not in call
            )
            if not unrecoverable:
                continue
            if "interrupt=False" in call and "priority=" not in call:
                # One deliberate exception: the turn APPROACH cue. It fires
                # while the corner is still ahead, so a warning that survives
                # to be spoken after the turn was missed is worse than one
                # that never arrives -- going stale is the right end for a
                # lead announcement. The act-now turn call is protected.
                if path.name == "driving_turns.py":
                    continue
                offenders.append(f"{path.name}:{src[: match.start()].count(chr(10)) + 1}")
    assert not offenders, "SAFETY lines riding the droppable ambient default: " + ", ".join(
        offenders
    )


def test_a_stale_flush_never_steps_on_a_safety_call() -> None:
    """The class promises a ROUTE or CRITICAL line still speaking is handed
    back, never dropped. ``note_interrupt`` honoured that; ``should_flush``
    did not -- its purge cleared the protected slot outright.

    An engine stall was stepped on exactly that way by the route-start merge
    cue on the owner's Denver playtest: the stall spoke CRITICAL, the merge
    cue flushed a moment later, and the stall was gone with no requeue. It
    was latent until that cue stopped being AMBIENT, because as chatter it
    had been dropped before ever reaching the flush.

    Narrowly CRITICAL: a backlog of stale ROUTE announcements really does
    describe road already driven, and rescuing those turned one flush into a
    recital of everything it had purged.
    """
    from freight_fate.speech_pacing import EventPriority, EventSpeechPacer

    now = [0.0]
    pacer = EventSpeechPacer(clock=lambda: now[0])

    # A safety call starts speaking.
    pacer.note_interrupt("Brake now! Stopped traffic ahead.", EventPriority.CRITICAL)
    # A route line arrives while it is still mid-sentence, far enough behind
    # the projection to flush.
    now[0] += 0.05
    assert pacer.should_flush("Merge onto US-40 west toward Salt Lake City.", EventPriority.ROUTE)
    cut = pacer.take_flush_cut()
    assert cut is not None, "the safety call was purged with no requeue"
    assert cut[0] == "Brake now! Stopped traffic ahead."
    # Collected once only.
    assert pacer.take_flush_cut() is None


def test_a_stale_flush_still_discards_a_stale_route_backlog() -> None:
    """The other half, and why the rescue is narrow. Route announcements go
    stale by their nature -- they describe road already driven -- so a flush
    that handed them all back would perform the very backlog it purged."""
    from freight_fate.speech_pacing import EventPriority, EventSpeechPacer

    now = [0.0]
    pacer = EventSpeechPacer(clock=lambda: now[0])

    pacer.note_queued("Next stop in 5 miles: service plaza.", EventPriority.ROUTE)
    now[0] += 0.05
    if pacer.should_flush("Zone ahead; speed limit 45.", EventPriority.ROUTE):
        assert pacer.take_flush_cut() is None, "a stale route backlog was resurrected"


def test_a_construction_zone_line_is_rescued_once_like_any_other() -> None:
    """Darren and Jerry, 2026-08-21: the repeat the build note describes at a
    scale happens in a work zone too.

    The cap is keyed on the line's own words, so it was always going to cover
    this -- but "was always going to" is not a test, and the report named a
    place the suite had never driven. These are the real work-zone lines,
    behind the run of urgent lines a busy taper produces.
    """
    work_zone = (
        "Work zone active. The right lane is closed; keep left and watch the barrels. "
        "Speed limit 45."
    )
    urgent = [
        "Brake lights ahead!",
        "Cones in your lane!",
        "Flagger stopping traffic!",
        "Truck merging left!",
        "Barrels in the shoulder!",
    ]
    pacer, _ = make_pacer()
    pacer.should_flush(work_zone, EventPriority.ROUTE)
    rescues = 0
    for warning in urgent:
        cut = pacer.note_interrupt(warning)
        if cut is not None and cut[0] == work_zone:
            rescues += 1
            pacer.note_queued(*cut)
    assert rescues == 1, f"the work zone line was replayed {rescues} times"


def test_the_merge_taper_line_is_rescued_once_too() -> None:
    """The other half of a work zone: the taper's own merge instruction, which
    is the line a driver can least afford to hear four times while deciding
    which way to go."""
    taper = "Construction merge taper. The right lane closes ahead; merge left now. Speed limit 55."
    pacer, _ = make_pacer()
    pacer.should_flush(taper, EventPriority.ROUTE)
    rescues = 0
    for n in range(1, 5):
        cut = pacer.note_interrupt(f"Hazard {n}!")
        if cut is not None and cut[0] == taper:
            rescues += 1
            pacer.note_queued(*cut)
    assert rescues == 1, f"the taper line was replayed {rescues} times"


def test_a_rescued_line_dies_when_its_moment_has_passed() -> None:
    """A cut line comes back so it can finish -- but only while it is still
    true. "Move right for the exit lane" handed back after the gore is behind
    the truck instructs a maneuver that no longer exists, which is the build
    note's own complaint about being told to signal for an exit when there is
    no exit left to take.
    """
    exit_line = "Exit 14A, half a mile ahead. Move right for the exit lane."
    passed = {"gone": False}
    pacer, _ = make_pacer()
    pacer.should_flush(exit_line, EventPriority.ROUTE)
    pacer._track(exit_line, EventPriority.ROUTE, None, lambda: not passed["gone"])
    # Cut while the exit is still ahead: handed back, as it should be.
    assert pacer.note_interrupt("Brake lights ahead!") == (exit_line, EventPriority.ROUTE)

    # Now the truck is past it. The same cut must NOT bring it back.
    passed["gone"] = True
    pacer2, _ = make_pacer()
    pacer2.should_flush(exit_line, EventPriority.ROUTE)
    pacer2._track(exit_line, EventPriority.ROUTE, None, lambda: not passed["gone"])
    assert pacer2.note_interrupt("Brake lights ahead!") is None


def test_a_hazard_call_does_not_come_back_once_the_hazard_is_clear() -> None:
    """Shane, 2026-08-21, on "Change lanes or brake! Retread debris from a
    blown tire.": the line repeated two or three times.

    A cut line is handed back so it finishes -- that is what rescued the
    missing "you swerve around the brake lights". But a dodge call handed back
    after the truck is clear tells the driver to swerve around something that
    is no longer there. Same rule the scale and the destination exit already
    carry: a rescued line has to still be true.
    """
    hazard_line = "Change lanes or brake! Retread debris from a blown tire."
    live = {"deadline": True}
    pacer, _ = make_pacer()
    pacer.should_flush(hazard_line, EventPriority.CRITICAL)
    pacer._track(hazard_line, EventPriority.CRITICAL, None, lambda: live["deadline"])
    # Still live: cut by something louder, handed back to finish.
    assert pacer.note_interrupt("Deer in the road!") == (hazard_line, EventPriority.CRITICAL)

    # Cleared: the same cut must not bring the dodge call back.
    live["deadline"] = False
    pacer2, _ = make_pacer()
    pacer2.should_flush(hazard_line, EventPriority.CRITICAL)
    pacer2._track(hazard_line, EventPriority.CRITICAL, None, lambda: live["deadline"])
    assert pacer2.note_interrupt("Deer in the road!") is None
