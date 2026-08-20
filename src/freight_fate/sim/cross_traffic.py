"""The cross bubble: real NPC traffic on the road a ramp terminal meets.

The mainline traffic bubble rotated ninety degrees (owner design,
2026-08-20 -- "make passing traffic actually pass; this is why they're
NPCs"). When a terminal announces, a short simulated stretch of crossroad
comes to life around the conflict point: vehicles spawn at the edges with
seeded Poisson arrivals, drive through, and despawn on the far side. They
are entities, not audio sweeps -- they platoon behind slow leaders (the
real burst-then-gap rhythm no random stream produces), they queue for the
cross street's own signal phase, and their pan and loudness fall out of
simulated position, so finding a gap is a listening skill: exactly how a
sighted driver reads an intersection by looking left.

Axis convention: position is MILES along the crossroad, negative on the
side the vehicle entered from, zero at the conflict point in front of the
player's stop bar. Vehicles all drive toward positive (each carries its
``from_side`` so audio knows which ear it started in); left-entering and
right-entering streams are two independent lanes that do not interact,
which matches a two-way crossroad seen from the stop bar.

Arrival rates are DESIGN CONSTANTS keyed to what the terminal already
knows -- its control kind and whether it is near a route city -- declared
as such below. The honest number would be the crossroad's own AADT, which
the bake does not carry yet; when it does (ROADMAP), the rates read from
it and these constants become the fallback.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

# The simulated stretch: a third of a mile each side of the conflict point.
CROSS_EXTENT_MI = 0.35
# The conflict window: a vehicle inside this many feet of the crossing line
# is a collision if the truck noses through. Sized as a generous lane-and-a
# -half so the window opens only when the crossing is genuinely clear.
CONFLICT_WINDOW_FT = 55.0
_CONFLICT_WINDOW_MI = CONFLICT_WINDOW_FT / 5280.0

# Mean seconds between arrivals PER SIDE, by (near_city, control kind).
# Design constants, stated as such (see module docstring): a signalized
# urban crossroad is a busy arterial, a rural stop-sign road is nearly
# empty, and free-flow terminals have no cross street at all (the caller
# never builds a bubble for them). Poisson arrivals; platooning below is
# what turns these into the bursts and long gaps real junctions have.
ARRIVAL_MEAN_S = {
    (True, "signal"): 7.0,
    (True, "stop"): 11.0,
    (True, "yield"): 9.0,
    (False, "signal"): 14.0,
    (False, "stop"): 30.0,
    (False, "yield"): 22.0,
}
DEFAULT_ARRIVAL_MEAN_S = 18.0

# Crossroad speed by context: urban arterial pace vs a rural two-lane.
CROSS_SPEED_MPH = {True: 32.0, False: 48.0}
CROSS_SPEED_JITTER_MPH = 6.0

# Following model on the cross axis: the speed allowed into a gap is what a
# comfortable brake can shed inside it, v = SAFE_SPEED_K * sqrt(gap_mi).
# K = sqrt(2 * a * 3600) with a as mph per second: 200 is a ~5.6 mph/s
# brake, inside the 8 mph/s the chase below can actually deliver, so the
# envelope is followable with margin instead of a promise the dynamics miss.
SAFE_SPEED_K = 200.0
# The minimum standing gap is a car length and a half of daylight.
MIN_GAP_MI = 30.0 / 5280.0

# Where cross traffic stops for ITS red: just short of the conflict point,
# the crossroad's own stop bar.
CROSS_BAR_MI = -45.0 / 5280.0

# Vehicle classes on a crossroad are not an interstate's mix: cars and
# pickups dominate, semis are rare visitors. Weights are design constants;
# every class named here has both a pass and a crossing sound shipped
# (traffic/<class>_cross), so the ear can tell a semi-sized gap problem
# from a motorcycle-sized one.
CROSS_CLASSES: tuple[tuple[str, float, float], ...] = (
    # (class, weight, length_ft)
    ("car", 5.0, 15.0),
    ("pickup", 2.5, 20.0),
    ("box truck", 0.8, 26.0),
    ("semi", 0.5, 70.0),
    ("motorcycle", 0.5, 8.0),
    ("bus", 0.3, 40.0),
    ("tractor", 0.15, 18.0),
)
_RURAL_ONLY_BONUS = {"tractor": 5.0}  # tractors belong to farm country

# Seconds before a vehicle reaches the conflict point to start its crossing
# cue, per class: half the cue's duration, so the sound's closest-approach
# peak lands on the actual crossing. Derived from the durations in
# tools/generate_sounds.py `_TRAFFIC_SYNTH_SPECS` (peak at 0.5 * duration).
CROSS_SOUND_LEAD_S = {
    "car": 1.1,
    "pickup": 1.1,
    "box truck": 1.25,
    "semi": 1.6,
    "motorcycle": 0.8,
    "bus": 1.5,
    "tractor": 1.75,
}


@dataclass
class CrossVehicle:
    """One NPC on the crossroad, driving toward positive positions."""

    position_mi: float
    speed_mph: float
    target_mph: float
    vehicle_class: str
    length_mi: float
    from_side: str  # "left" | "right" -- the ear it entered in
    crossed: bool = False  # has passed the conflict point (for the sweep cue)
    sound_started: bool = False  # its crossing cue has been triggered

    @property
    def front_mi(self) -> float:
        return self.position_mi + self.length_mi


@dataclass
class CrossTraffic:
    """The living crossroad at one terminal.

    ``player_has_green`` mirrors the PLAYER's signal phase when the
    terminal is a light: the cross street runs the orthogonal phase, so
    cross traffic flows on the player's red and queues at its own bar on
    the player's green -- which is why a red light is audibly BUSY and a
    green is audible as the cross stream dying. Stop and yield terminals
    leave it False-flowing (cross traffic has the right of way and never
    stops).
    """

    seed: int
    control: str  # "signal" | "stop" | "yield"
    near_city: bool
    vehicles: list[CrossVehicle] = field(default_factory=list)
    player_has_green: bool = False
    _rng: random.Random = field(init=False)
    _next_spawn_s: dict[str, float] = field(init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self._next_spawn_s = {"left": 0.0, "right": 0.0}
        # Pre-roll the road so the bubble is mid-life when the player first
        # hears it: an intersection does not begin existing when you arrive.
        for _ in range(120):
            self.update(0.5)

    # -- spawning ---------------------------------------------------------

    def _arrival_mean_s(self) -> float:
        return ARRIVAL_MEAN_S.get((self.near_city, self.control), DEFAULT_ARRIVAL_MEAN_S)

    def _draw_class(self) -> tuple[str, float]:
        classes = list(CROSS_CLASSES)
        if not self.near_city:
            classes = [
                (name, weight * _RURAL_ONLY_BONUS.get(name, 1.0), length)
                for name, weight, length in classes
            ]
        total = sum(w for _, w, _ in classes)
        roll = self._rng.random() * total
        for name, weight, length in classes:
            roll -= weight
            if roll <= 0.0:
                return name, length / 5280.0
        return classes[0][0], classes[0][2] / 5280.0

    def _entry_blocked(self, side: str) -> bool:
        """No room at the edge: the last arrival is still on top of it.

        Poisson interarrivals can be near zero; without this gate two
        vehicles spawn overlapped and the following model can never
        separate them. The waiting arrival is simply held outside the
        bubble -- which is where a real platoon forms anyway."""
        edge = -CROSS_EXTENT_MI
        room = MIN_GAP_MI + max(length for _, _, length in CROSS_CLASSES) / 5280.0
        return any(v.from_side == side and v.position_mi < edge + room for v in self.vehicles)

    def _spawn(self, side: str) -> None:
        name, length_mi = self._draw_class()
        base = CROSS_SPEED_MPH[self.near_city]
        speed = base + self._rng.uniform(-CROSS_SPEED_JITTER_MPH, CROSS_SPEED_JITTER_MPH)
        if name == "tractor":
            speed = min(speed, 20.0)  # a tractor is the platoon-maker
        # Never enter faster than the gap ahead allows: a fast car arriving
        # on a slow tractor's tail joins the platoon, it does not ram it.
        rear = min(
            (v for v in self.vehicles if v.from_side == side),
            key=lambda v: v.position_mi,
            default=None,
        )
        if rear is not None:
            gap = rear.position_mi - (-CROSS_EXTENT_MI + length_mi)
            surplus = max(0.0, gap - MIN_GAP_MI)
            speed = min(speed, math.sqrt(rear.speed_mph**2 + SAFE_SPEED_K**2 * surplus))
        self.vehicles.append(
            CrossVehicle(
                position_mi=-CROSS_EXTENT_MI,
                speed_mph=speed,
                target_mph=speed,
                vehicle_class=name,
                length_mi=length_mi,
                from_side=side,
            )
        )

    # -- the frame --------------------------------------------------------

    def update(self, dt: float) -> list[CrossVehicle]:
        """Advance the crossroad by ``dt`` REAL seconds (terminals run on
        the real clock). Returns vehicles that crossed the conflict point
        this frame, for the crossing-sweep cue."""
        for side in ("left", "right"):
            self._next_spawn_s[side] -= dt
            if self._next_spawn_s[side] <= 0.0:
                if self._entry_blocked(side):
                    self._next_spawn_s[side] = 0.5  # hold at the edge for room
                else:
                    self._spawn(side)
                    self._next_spawn_s[side] = self._rng.expovariate(1.0 / self._arrival_mean_s())
        crossed_now: list[CrossVehicle] = []
        for side in ("left", "right"):
            lane = [v for v in self.vehicles if v.from_side == side]
            lane.sort(key=lambda v: -v.position_mi)  # leader first
            leader: CrossVehicle | None = None
            for v in lane:
                target = v.target_mph
                # The cross street's own red: queue at its bar while the
                # player holds green. Vehicles already past the bar clear
                # the intersection rather than trapping themselves in it.
                if self.player_has_green and v.position_mi < CROSS_BAR_MI:
                    bar_gap = CROSS_BAR_MI - v.front_mi
                    if bar_gap <= 0.0:
                        target = 0.0
                    else:
                        target = min(target, SAFE_SPEED_K * math.sqrt(bar_gap))
                if leader is not None:
                    gap = leader.position_mi - v.front_mi
                    if gap <= MIN_GAP_MI:
                        # Inside the standing gap: fall behind the leader
                        # until daylight reopens.
                        target = min(target, max(0.0, leader.speed_mph - 5.0))
                    else:
                        # The braking invariant: with both able to brake at
                        # the envelope rate, the gap never closes below the
                        # minimum while v^2 <= leader^2 + K^2 * surplus. The
                        # additive form (leader + K*sqrt(surplus)) permits
                        # more than that and overlapped when a leader was
                        # itself braking for ITS leader.
                        target = min(
                            target,
                            math.sqrt(leader.speed_mph**2 + SAFE_SPEED_K**2 * (gap - MIN_GAP_MI)),
                        )
                # Constant-rate brake and throttle. Not a proportional chase:
                # error-proportional decay never quite reaches the target, and
                # a follower riding just above its allowed speed compounds the
                # shortfall into the gap until it overlaps its leader. The 8
                # here is the brake the SAFE_SPEED_K envelope assumes margin
                # against.
                if v.speed_mph > target:
                    v.speed_mph = max(target, v.speed_mph - 8.0 * dt)
                else:
                    v.speed_mph = min(target, v.speed_mph + 5.0 * dt)
                v.speed_mph = max(0.0, v.speed_mph)
                before = v.position_mi
                v.position_mi += v.speed_mph * dt / 3600.0
                if not v.crossed and before < 0.0 <= v.position_mi:
                    v.crossed = True
                    crossed_now.append(v)
                leader = v
        self.vehicles = [v for v in self.vehicles if v.position_mi <= CROSS_EXTENT_MI]
        return crossed_now

    # -- questions the terminal asks --------------------------------------

    def occupant(self) -> CrossVehicle | None:
        """The vehicle inside the conflict window right now, if any."""
        for v in self.vehicles:
            if (
                v.position_mi + v.length_mi > -_CONFLICT_WINDOW_MI
                and v.position_mi < _CONFLICT_WINDOW_MI
            ):
                return v
        return None

    def occupied(self) -> bool:
        """A vehicle is inside the conflict window right now."""
        return self.occupant() is not None

    def approaching(self, within_s: float = 4.0) -> CrossVehicle | None:
        """The nearest vehicle that would reach the conflict point within
        ``within_s`` seconds at its current speed -- the one a driver about
        to pull out actually has to answer for."""
        best: CrossVehicle | None = None
        best_eta = within_s
        for v in self.vehicles:
            if v.position_mi >= 0.0 or v.speed_mph <= 1.0:
                continue
            eta = -v.position_mi * 3600.0 / v.speed_mph
            if eta <= best_eta:
                best_eta = eta
                best = v
        return best

    def clear_to_cross(self) -> bool:
        """The gap-acceptance answer: nothing in the window, nothing about
        to arrive in it."""
        return not self.occupied() and self.approaching() is None

    def audible(self) -> list[tuple[str, str, float, float]]:
        """(vehicle_class, side_now, pan, closeness 0..1) per vehicle worth
        hearing. Pan is where the vehicle IS (negative = left of the
        conflict point from the stop bar), closeness drives loudness."""
        out: list[tuple[str, str, float, float]] = []
        for v in self.vehicles:
            closeness = max(0.0, 1.0 - abs(v.position_mi) / CROSS_EXTENT_MI)
            if closeness <= 0.05:
                continue
            side = "left" if v.position_mi < 0.0 else "right"
            if v.from_side == "right":
                side = "right" if v.position_mi < 0.0 else "left"
            pan = -0.8 if side == "left" else 0.8
            out.append((v.vehicle_class, side, pan, closeness))
        return out
