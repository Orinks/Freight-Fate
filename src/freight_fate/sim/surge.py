"""Liquid surge in a tank trailer: the load that keeps moving after you stop.

A tank is never filled to the brim -- liquids expand in transit, and a dense
product would blow the axle weights long before the shell was full -- so a
tanker is always hauling a free surface. That surface is the whole problem.
Brake, and the liquid keeps going at the speed the truck was doing until it
piles up against the front head; a while later it runs back. Real drivers are
taught the consequence directly: the wave can shove a stopped tractor out into
the intersection, and it is why you brake early, gently, and once.

The model here is the standard one: the free surface's first sloshing mode is
a damped oscillator riding in the tank, driven by the tank's own acceleration.

    x'' + 2*zeta*w*x' + w^2 * x = -a_truck

``x`` is how far the slug's centre of mass has moved from where it sits at
rest, positive forward. The liquid pushes back on the truck with

    F = m_slug * (w^2 * x + 2*zeta*w*x')

which is positive -- forward, against the brakes -- exactly when the slug is
piled up front. Nothing in that is a fudge factor: it is Newton's third law on
the sloshing mass, and every behaviour drivers are warned about falls out of
it without being written in.

Two properties of the solution do the design work:

* The force lags the braking. ``x`` needs a quarter period to build, so the
  shove arrives seconds after the pedal went down -- and keeps arriving, in
  alternating directions, after the truck has stopped.
* Velocity leads displacement by a quarter period. The liquid is loudest --
  it is *moving* fastest -- a quarter cycle before it pushes hardest. The
  audio layer sonifies ``x'`` and therefore warns ahead of the force it is
  about to deliver, without predicting anything.

Frequencies come from shallow-water theory for the first mode in a tank of
length ``L`` filled to depth ``h``:

    w = sqrt(g * k * tanh(k*h)),  k = pi / L

which for a 40-foot tank puts the fundamental between about 5.8 seconds (very
full) and 11 seconds (a quarter full) -- long, slow water, and a quarter of
that is one and a half to three seconds of honest warning.

Sources for the behaviour this reproduces: California DMV Commercial Driver
Handbook section 8 (tank vehicles: outage, baffled and smooth bore, surge and
rollover), and the FMCSA tank-vehicle endorsement material behind it.

Deterministic throughout: no RNG, no wall clock. Given a fill level, a tank
type and a history of accelerations, the wave is always the same wave.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

G = 9.81

# A road tanker is about forty feet of shell on a two-metre bore. Both feed
# the sloshing frequency, so they are named rather than buried in a constant.
TANK_LENGTH_M = 12.2
TANK_DEPTH_M = 2.0

# Baffles are transverse bulkheads with holes in them. The holes let the
# compartments talk, so the tank does not behave like four short tanks, but
# the wave has a much shorter run before it meets steel -- roughly half.
# Shorter run, higher frequency: a baffled load slaps quickly where a smooth
# bore rolls slowly, which is the difference a driver actually hears.
BAFFLED_LENGTH_MULT = 0.5

# How lightly the wave is damped, as a fraction of critical. A smooth bore is
# close to frictionless: the CDL manuals warn that once a smooth-bore load is
# swaying it will keep swaying, and 0.04 reproduces that -- perceptible for
# some ten cycles. Baffles are there precisely to spend that energy.
ZETA_SMOOTH = 0.04
ZETA_BAFFLED = 0.28

# Damping is only half of what baffles buy. The bulkheads also break the load
# into compartments that slosh largely independently and out of step with each
# other, so their reactions partly cancel and far less of the liquid arrives
# at the head as one slug. That reduction in participating mass -- not the
# damping -- is most of why a baffled tank is the forgiving one. Fore and aft
# only: side to side there is no bulkhead in the way and nothing is reduced.
BAFFLED_MASS_MULT = 0.45

# Baffles are transverse. They stand across the tank, so they are in the way
# of liquid running fore and aft and are not in the way of liquid running side
# to side. This single asymmetry is the reason a baffled tanker still rolls
# over, and it is the most important fact in the model.
ZETA_LATERAL = ZETA_SMOOTH

# The share of the liquid that actually participates in the first mode. A full
# tank has no free surface and an empty one has no liquid; the worst case is
# in the middle, which is why the manuals single out a half-full tank. The
# 4f(1-f) shape peaks at exactly half and vanishes at both ends.
SLOSH_MASS_PEAK = 0.55

# Liquids expand in transit, so room is always left above the load. Even a
# "full" tanker therefore carries a free surface and a little surge -- the
# reason a tanker never behaves quite like a solid load. (Kept internal: the
# trade calls this outage, but the game already uses that word for online
# services and a driver must not hear it mid-drive.)
MAX_FILL_FRACTION = 0.97

# How far the slug's centre of mass can travel before it is simply piled
# against the head and cannot go further, as a share of the run available.
# Beyond this the wave is breaking on steel, not translating.
TRAVEL_FRACTION = 0.14

# Curve advisories for trucks are posted around this lateral acceleration, so
# a bend taken at its advisory pulls about this much and one taken faster
# pulls with the square of the ratio.
CURVE_DESIGN_LAT_G = 0.12

# Below this the wave is no longer worth a driver's attention: the load has
# settled. Expressed as a share of the travel limit so it means the same thing
# on every tank.
SETTLED_TRAVEL_FRACTION = 0.06

# How long the slug spends piling against the head once it gets there. The
# linear spring alone badly understates a smooth bore, because a long tank's
# wave is slow -- small omega, and omega squared times a bounded displacement
# is a modest force. What actually shoves the truck is the *arrival*: the
# whole moving slug stopping against the head over a fraction of a second.
# That impulse is the shove the manuals describe, it is why smooth bore is
# feared and baffles help (a damped wave arrives slowly, or never reaches the
# head at all), and it is the same event the audio layer plays as the hit.
HEAD_IMPACT_S = 0.8

# The oscillator is integrated at no coarser than this. A frame is normally
# far shorter, but a paused-and-resumed frame or a slow machine must not be
# allowed to make a stiff spring explode.
MAX_SUBSTEP_S = 0.02


def fill_severity(fill_fraction: float) -> float:
    """How much of the liquid joins the first sloshing mode, 0 to 1.

    Peaks at half full, which is the case every tanker manual warns about,
    and falls to nothing at both ends.
    """
    f = min(MAX_FILL_FRACTION, max(0.0, float(fill_fraction)))
    return max(0.0, 4.0 * f * (1.0 - f))


@dataclass
class SloshAxis:
    """One damped sloshing mode: displacement and velocity, nothing else."""

    omega: float
    zeta: float
    travel_m: float
    x: float = 0.0
    v: float = 0.0
    # Set for exactly one frame when the slug reaches the end of its run and
    # turns around -- the wave arriving at the head. The audio layer consumes
    # it; nothing in the physics reads it.
    struck: bool = False
    strike_strength: float = 0.0
    # Speed the slug carried into the head, and how much of the impact window
    # is left to spend it over. This is where most of the shove lives.
    impact_v: float = 0.0
    impact_left_s: float = 0.0

    def step(self, dt: float, drive_accel: float) -> None:
        """Advance the mode under a tank acceleration of ``drive_accel``."""
        self.struck = False
        self.strike_strength = 0.0
        if self.impact_left_s > 0.0:
            self.impact_left_s = max(0.0, self.impact_left_s - dt)
            if self.impact_left_s <= 0.0:
                self.impact_v = 0.0
        if dt <= 0.0 or self.omega <= 0.0 or self.travel_m <= 0.0:
            return
        steps = max(1, int(math.ceil(dt / MAX_SUBSTEP_S)))
        h = dt / steps
        for _ in range(steps):
            was_moving = self.v
            # Semi-implicit Euler: stable for this spring at these steps, and
            # it conserves the phase relationship the audio layer depends on.
            accel = -drive_accel - 2.0 * self.zeta * self.omega * self.v - self.omega**2 * self.x
            self.v += accel * h
            self.x += self.v * h
            if self.x > self.travel_m:
                self.x = self.travel_m
                self._strike(was_moving, head_on=True)
            elif self.x < -self.travel_m:
                self.x = -self.travel_m
                self._strike(was_moving, head_on=True)
            elif was_moving != 0.0 and (was_moving > 0.0) != (self.v > 0.0):
                # Turned around short of the head: the wave ran out of energy
                # rather than out of tank. Still the moment the push peaks.
                self._strike(was_moving, ran_out=True)

    def _strike(self, incoming_v: float, ran_out: bool = False, head_on: bool = False) -> None:
        if self.struck:
            return
        reach = abs(self.x) / self.travel_m if self.travel_m > 0.0 else 0.0
        if ran_out and reach < SETTLED_TRAVEL_FRACTION:
            return
        if head_on:
            # The slug ran out of tank: it stops against the steel and spends
            # its momentum on the truck over the contact window.
            self.impact_v = incoming_v
            self.impact_left_s = HEAD_IMPACT_S
            self.v = -self.v * (1.0 - self.zeta)
        self.struck = True
        self.strike_strength = min(1.0, abs(incoming_v) / max(1e-6, self.peak_v))

    @property
    def impact_accel(self) -> float:
        """Acceleration per unit sloshing mass from the slug against the head,
        while the contact window lasts. Signed the way the slug was moving."""
        if self.impact_left_s <= 0.0:
            return 0.0
        return self.impact_v / HEAD_IMPACT_S

    @property
    def peak_v(self) -> float:
        """The velocity a slug swinging its full run would carry."""
        return self.omega * self.travel_m

    @property
    def reach(self) -> float:
        """How far out the slug is, 0 at rest, 1 against the head."""
        if self.travel_m <= 0.0:
            return 0.0
        return min(1.0, abs(self.x) / self.travel_m)

    @property
    def motion(self) -> float:
        """How fast the slug is running, 0 to 1. Leads :attr:`reach` by a
        quarter period -- this is the anticipation, and it is free."""
        peak = self.peak_v
        if peak <= 0.0:
            return 0.0
        return min(1.0, abs(self.v) / peak)

    @property
    def settled(self) -> bool:
        return self.reach < SETTLED_TRAVEL_FRACTION and self.motion < SETTLED_TRAVEL_FRACTION


@dataclass
class LiquidLoad:
    """A tank of liquid riding behind the driver, and how it behaves.

    ``fill_fraction`` and ``baffled`` are properties of the load: they are
    fixed when it is pumped on and they set the wave's size and its period.
    They are spoken at pickup. What changes moment to moment is the wave.
    """

    fill_fraction: float = 0.5
    baffled: bool = False
    tank_length_m: float = TANK_LENGTH_M
    longitudinal: SloshAxis = field(init=False)
    lateral: SloshAxis = field(init=False)

    def __post_init__(self) -> None:
        self.fill_fraction = min(MAX_FILL_FRACTION, max(0.0, float(self.fill_fraction)))
        run = self.tank_length_m * (BAFFLED_LENGTH_MULT if self.baffled else 1.0)
        travel = run * TRAVEL_FRACTION * self.severity
        self.longitudinal = SloshAxis(
            omega=self._omega(run),
            zeta=ZETA_BAFFLED if self.baffled else ZETA_SMOOTH,
            travel_m=travel,
        )
        # Side to side the tank is its bore, not its length, and no bulkhead
        # stands in the way. Short run, quick wave, undamped either way.
        self.lateral = SloshAxis(
            omega=self._omega(TANK_DEPTH_M),
            zeta=ZETA_LATERAL,
            travel_m=TANK_DEPTH_M * TRAVEL_FRACTION * self.severity,
        )

    def _omega(self, run_m: float) -> float:
        """First-mode sloshing frequency for a run of ``run_m`` at this fill."""
        if run_m <= 0.0 or self.severity <= 0.0:
            return 0.0
        k = math.pi / run_m
        depth = max(0.05, self.fill_fraction * TANK_DEPTH_M)
        return math.sqrt(G * k * math.tanh(k * depth))

    @property
    def severity(self) -> float:
        return fill_severity(self.fill_fraction)

    @property
    def period_s(self) -> float:
        """How long one full fore-and-aft cycle takes. Rate is the danger:
        a slow, long wave is a big one."""
        w = self.longitudinal.omega
        return (2.0 * math.pi / w) if w > 0.0 else 0.0

    def slosh_mass_kg(self, cargo_kg: float, *, lateral: bool = False) -> float:
        """How much of the liquid arrives as one slug on the given axis."""
        mass = max(0.0, float(cargo_kg)) * SLOSH_MASS_PEAK * self.severity
        if self.baffled and not lateral:
            mass *= BAFFLED_MASS_MULT
        return mass

    def update(self, dt: float, accel_mps2: float, lateral_accel_mps2: float = 0.0) -> None:
        """Advance both waves under the tank's own acceleration this frame."""
        self.longitudinal.step(dt, accel_mps2)
        self.lateral.step(dt, lateral_accel_mps2)

    def force_n(self, cargo_kg: float) -> float:
        """What the liquid is doing to the truck right now, newtons.

        Positive is forward: the slug piled against the front head pushing the
        truck on through the stop it was trying to make.
        """
        axis = self.longitudinal
        if axis.omega <= 0.0:
            return 0.0
        m = self.slosh_mass_kg(cargo_kg)
        spring = axis.omega**2 * axis.x + 2.0 * axis.zeta * axis.omega * axis.v
        return m * (spring + axis.impact_accel)

    def peak_force_n(self, cargo_kg: float) -> float:
        """The hardest forward shove this load can deliver, newtons.

        A property of the load rather than of the moment, so a stopping
        distance built on it is a stable number a driver can learn instead of
        one that breathes with the wave.

        Dominated by the head impact: a slug swinging its full run arrives at
        ``omega * travel`` and stops against the steel over the contact
        window. That is why a smooth bore is the frightening one -- barely
        damped, it arrives at nearly full speed every time -- and why baffles
        help, because a damped wave arrives slowly or not at all.
        """
        axis = self.longitudinal
        if axis.omega <= 0.0:
            return 0.0
        m = self.slosh_mass_kg(cargo_kg)
        # How much of a full swing survives one quarter cycle of damping.
        arrival = axis.peak_v * math.exp(-axis.zeta * math.pi / 2.0)
        impact = m * arrival / HEAD_IMPACT_S
        spring = m * axis.omega**2 * axis.travel_m
        return impact + spring

    def lateral_load_factor(self) -> float:
        """How much the side-to-side wave adds to what a bend is already
        asking of the tyres, as a share. Baffles do nothing here."""
        return self.lateral.reach * self.severity

    @property
    def settled(self) -> bool:
        return self.longitudinal.settled and self.lateral.settled

    def describe_tank(self) -> str:
        return "baffled" if self.baffled else "smooth bore"

    def describe_fill(self) -> str:
        """How full the tank is, in words. Never "outage" -- see the note on
        ``MAX_FILL_FRACTION``."""
        f = self.fill_fraction
        if f >= 0.9:
            return "nearly full"
        if f >= 0.7:
            return "three quarters full"
        if f >= 0.55:
            return "over half full"
        if f >= 0.45:
            return "half full"
        if f >= 0.3:
            return "a third full"
        return "lightly loaded"


def liquid_load_for(cargo, weight_tons: float) -> LiquidLoad | None:
    """The tank aboard for this load, or None if the freight is not liquid.

    Everything the wave does follows from the job: how full the shell is comes
    from the load's weight against the tank's capacity, and whether it is
    baffled is a property of the product. The same job therefore always drives
    the same way -- no randomness anywhere, because a penalty a driver cannot
    learn to avoid is not a skill test.
    """
    if cargo is None or not getattr(cargo, "tank", False):
        return None
    fill = float(cargo.fill_fraction(weight_tons))
    if fill <= 0.0:
        return None
    return LiquidLoad(fill_fraction=fill, baffled=bool(getattr(cargo, "baffled", False)))


def lateral_accel_mps2(speed_mph: float, advisory_mph: float) -> float:
    """What a bend posted at ``advisory_mph`` pulls when taken at ``speed_mph``.

    Advisories are set around a design lateral acceleration, so the pull goes
    with the square of how far over the posting the truck is.
    """
    if advisory_mph <= 0.0 or speed_mph <= 0.0:
        return 0.0
    ratio = speed_mph / advisory_mph
    return CURVE_DESIGN_LAT_G * G * ratio * ratio
