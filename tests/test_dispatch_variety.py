"""Assigned dispatch prefers a lane the driver has not just run.

Owner playtest 2026-07-15: level-1 assigned dispatch bounced the same two
cities forever (Winslow to Holbrook, again and again). The profile now
remembers the last few delivered from:to lanes and the assignment queue
stable-partitions fresh candidates so an unseen lane goes first -- score
order still rules inside each group, and an all-recent board changes
nothing, so the nudge can delay a repeat but never block dispatch.
"""

from freight_fate.models.jobs import JobBoard, lane_key
from freight_fate.models.profile import Profile


class _Ctx:
    def __init__(self, world, profile):
        self.world = world
        self.profile = profile

    def say(self, text: str, interrupt: bool = True) -> None:
        pass


def test_remember_lane_dedupes_and_caps():
    p = Profile(name="Variety")
    for i in range(10):
        p.remember_lane(f"a_{i}:b_{i}")
    assert len(p.recent_lanes) == Profile.RECENT_LANES_KEPT
    assert p.recent_lanes[0] == "a_9:b_9"

    p.remember_lane("a_9:b_9")  # re-running a lane moves it up, not in twice
    assert p.recent_lanes.count("a_9:b_9") == 1
    p.remember_lane("")  # never records an empty lane
    assert "" not in p.recent_lanes


def test_recent_lanes_survive_a_save_round_trip():
    p = Profile(name="Variety", current_city="denver_co_us")
    p.remember_lane("denver_co_us:silverthorne_co_us")
    restored = Profile.from_dict(p.to_dict())
    assert restored.recent_lanes == ["denver_co_us:silverthorne_co_us"]


def test_assignment_prefers_a_lane_not_recently_run(world):
    from freight_fate.states.city import JobBoardState

    profile = Profile(name="Variety", current_city="denver_co_us")
    ctx = _Ctx(world, profile)
    board = JobBoard(world, seed=11)
    jobs = board.offers("denver_co_us", set(), count=4, level=1)
    assert len({lane_key(world, job) for job in jobs}) >= 2, "need lane variety to test"

    baseline = JobBoardState(ctx, jobs)
    first = jobs[baseline._assigned_queue[0]]

    # The driver just ran the would-be assignment's lane: dispatch now leads
    # with a different one.
    profile.remember_lane(lane_key(world, first))
    varied = JobBoardState(ctx, jobs)
    assert lane_key(world, jobs[varied._assigned_queue[0]]) != lane_key(world, first)

    # Every candidate recently run: order falls back to plain score order.
    for job in jobs:
        profile.remember_lane(lane_key(world, job))
    saturated = JobBoardState(ctx, jobs)
    assert saturated._assigned_queue == baseline._assigned_queue
