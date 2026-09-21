"""Engine-audio state: maps the truck's physical state to what the engine
should SOUND like, independent of any audio backend or sample set.

Today the engine is one idle loop pitch-slid by rpm (``audio.engine_freq_mult``),
so it cannot tell a truck parked and warming up from one pulling a grade. This
module is the small brain that names the situation instead:

  off         engine not running
  park_idle   parked, air still building -- the "neutral park" character
  ready_idle  parked, air up, drive-ready -- the FLIP target (Josh's cue)
  launch      pulling away from a stop
  cruise      rolling in gear
  reverse     backing up (the parking/backing mechanic keys off this)

The park_idle -> ready_idle FLIP fires exactly when the air system reaches the
governor release (``air_ready``): start cold, it fast-idles while it builds air,
then flips to the settled drive-ready idle -- the sound Josh liked in 896. A
separate ``pressurizing`` overlay flag (engine on, air not yet ready) drives the
air-fill loop regardless of which idle is playing.

Pure logic: ``classify`` takes primitives so it is trivially testable, and
``reading_from_truck`` adapts a live TruckState. The playback layer (multisample
selection, pitch tracking, crossfades) consumes the result; this module owns the
gameplay contract that the engine voice and the parking feature both read.
"""

from __future__ import annotations

from dataclasses import dataclass

# State names (also the contract the parking/backing feature reads).
OFF = "off"
PARK_IDLE = "park_idle"
READY_IDLE = "ready_idle"
LAUNCH = "launch"
CRUISE = "cruise"
REVERSE = "reverse"

# A truck slower than this is "stopped"; below LAUNCH_MPS but moving in gear it
# is still pulling away rather than cruising. LAUNCH_THROTTLE matches the
# throttle floor the vehicle uses to tell a real launch from a coasting creep.
STOP_MPS = 0.3
LAUNCH_MPS = 2.5
LAUNCH_THROTTLE = 0.15


@dataclass(frozen=True)
class EngineReading:
    """The physical signals the engine sound depends on, as plain values."""

    engine_on: bool
    stalled: bool
    rpm: float
    throttle: float
    speed_mps: float
    in_reverse: bool
    in_neutral: bool
    parked_brakes_holding: bool   # parking brake or spring brakes are set
    air_ready: bool               # air pressure at/above the governor release


@dataclass(frozen=True)
class EngineVoice:
    """What to play: the named state plus the air-fill overlay flag."""

    state: str
    pressurizing: bool


def classify(r: EngineReading) -> EngineVoice:
    """Name the engine situation. See module docstring for the states."""
    if not r.engine_on or r.stalled:
        return EngineVoice(OFF, pressurizing=False)

    # The air-fill loop plays whenever the engine is running below governor
    # release, regardless of which engine state is playing over it.
    building = not r.air_ready

    if r.in_reverse:
        return EngineVoice(REVERSE, pressurizing=building)

    stationary = r.speed_mps < STOP_MPS
    parked = r.in_neutral or r.parked_brakes_holding

    if stationary and parked:
        # The flip: fast park idle while air builds, drive-ready idle once up.
        return EngineVoice(PARK_IDLE if building else READY_IDLE, pressurizing=building)

    if stationary:
        # In gear, stopped, brakes off: on the throttle it is a launch; off it,
        # it is holding a ready idle (foot on the brake at a light).
        state = LAUNCH if r.throttle > LAUNCH_THROTTLE else READY_IDLE
        return EngineVoice(state, pressurizing=building)

    # Rolling: still launching until up to speed, then cruising.
    if r.speed_mps < LAUNCH_MPS and not r.in_neutral:
        return EngineVoice(LAUNCH, pressurizing=building)
    return EngineVoice(CRUISE, pressurizing=building)


def reading_from_truck(truck) -> EngineReading:
    """Adapt a live TruckState to an EngineReading (duck-typed, no imports)."""
    tr = truck.transmission
    return EngineReading(
        engine_on=truck.engine_on,
        stalled=truck.stalled,
        rpm=truck.rpm,
        throttle=truck.throttle,
        speed_mps=abs(truck.velocity_mps),
        in_reverse=tr.in_reverse,
        in_neutral=tr.in_neutral,
        parked_brakes_holding=truck.parking_brake or truck.spring_brakes_active,
        air_ready=truck.air_ready,
    )
