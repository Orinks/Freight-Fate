"""What a tank load sounds like from the driver's seat.

The physics live in ``sim/surge.py``. This is the part the player actually
meets: a gated cue layer that is completely silent on steady cruise and on
every other kind of freight, and that comes alive from the moment the liquid
starts running until it has settled again.

Three decisions shape all of it.

**The wave is sonified by its speed, not its force.** The oscillator's
velocity leads its displacement by a quarter period, and the force the truck
feels goes with displacement. So playing the liquid's *motion* means the sound
peaks a quarter cycle -- one and a half to three seconds, on these tanks --
before the shove arrives. That warning is not predicted, estimated or faked;
it is the same relationship that makes a swing loudest at the bottom and
highest at the ends. Nothing is being modelled twice, and there is nothing for
a driver to learn to distrust.

**Rate carries the danger.** A half-full smooth bore rolls slowly: a long,
late, heavy wave. A baffled tank slaps quickly and dies. The player hears
which one they are hauling in the tempo of wash and hit rather than in a
level, because tempo survives a mono speaker, a low effects volume, and the
jake brake running at full gain on top of it -- and level does not.

**Nothing is panned.** Left and right are already fully spoken for: the road
bed's pan is the lane-guidance instrument and the edge ladder's is the drift
side. A tanker drifting in a bend would otherwise put three separate things on
one axis. Fore and aft is not a decision the driver makes anyway -- only the
timing and the size of the wave are -- so those are what get encoded.

The sound sits high on purpose. The engine and the road own everything below
a kilohertz, and the jake is loudest at exactly the moment surge matters, so
this layer plays the *surface* of the liquid -- the wash and the slap against
the head, up where nothing else lives.
"""

from __future__ import annotations

from ..audio import CH_SURGE
from ..models.cargo_condition import cargo_condition_text
from ..speech_pacing import SpeechCategory

# The wash is the liquid on the move. Below this it is not doing anything a
# driver needs to hear, and holding a bed under that floor would just be one
# more thing making noise in a cab that already has plenty.
SURGE_WASH_FLOOR = 0.10
SURGE_WASH_GAIN = 0.55

# The hit is the wave arriving. It is the load-bearing event -- it has to
# survive a mono speaker at a low effects volume -- so it is the loudest thing
# this layer does, and it is a one-shot rather than part of any bed.
SURGE_HIT_GAIN = 0.85
SURGE_HIT_FLOOR = 0.18  # weaker arrivals than this are not worth a sound

# The first real wave of a run gets spoken; after that the audio carries it.
# A driver does not need to be told about the liquid every time they brake.
SURGE_SPEAK_REACH = 0.55
# And the load settling gets spoken too. Without a downward line there is no
# way to know the wave has damped -- silence is ambiguous between "settled"
# and "the cue layer stopped working", and for a blind driver that is not a
# distinction to leave hanging.
SURGE_SETTLE_SPEAK_DELAY_S = 1.5

# A bend with liquid running sideways in it is the tanker rollover case, and
# it gets its own voice: baffles do nothing about lateral surge, so this can
# happen on the load that has been forgiving all day.
SURGE_LATERAL_WARN = 0.45
SURGE_LATERAL_COOLDOWN_S = 20.0


class LiquidLoadMixin:
    """Speech and audio for a sloshing tank load. Inert without one."""

    def _liquid(self):
        """The tank aboard, or None for every other kind of freight."""
        return getattr(self.truck, "liquid", None)

    def _liquid_audio_ready(self) -> bool:
        """Whether the surge assets are in this build, checked once.

        They are baked by ``sound-test/liquid_surge.py`` into the sound pack.
        A build made before that bake should fall back to the spoken layer in
        silence rather than log a missing asset on every frame.
        """
        ready = getattr(self, "_liquid_audio_ok", None)
        if ready is None:
            has = getattr(self.ctx.audio, "has_asset", None)
            ready = True if has is None else bool(has("vehicle/liquid_wash"))
            self._liquid_audio_ok = ready
        return ready

    # -- per-frame cue layer ------------------------------------------------------

    def _update_liquid_cues(self, dt: float) -> None:
        liquid = self._liquid()
        if liquid is None:
            return
        axis = liquid.longitudinal
        audio = self.ctx.audio
        if not self._liquid_audio_ready():
            self._update_liquid_speech(dt, liquid)
            return

        # The wash: how fast the liquid is running, which is what leads.
        motion = axis.motion
        if motion >= SURGE_WASH_FLOOR:
            audio.start_loop(
                CH_SURGE, "vehicle/liquid_wash", volume=SURGE_WASH_GAIN * motion, fade_ms=90
            )
            audio.set_loop_volume(CH_SURGE, SURGE_WASH_GAIN * motion)
            self._liquid_wash_on = True
        elif getattr(self, "_liquid_wash_on", False):
            audio.stop_loop(CH_SURGE, fade_ms=260)
            self._liquid_wash_on = False

        # The hit: the wave reaching the end of its run and turning over.
        if axis.struck and axis.strike_strength >= SURGE_HIT_FLOOR:
            audio.play("vehicle/liquid_hit", volume=SURGE_HIT_GAIN * axis.strike_strength)
        if liquid.lateral.struck and liquid.lateral.strike_strength >= SURGE_HIT_FLOOR:
            # Side to side gets a different voice, because it means something
            # different: this is the one that rolls trucks over.
            audio.play(
                "vehicle/liquid_hit_lateral",
                volume=SURGE_HIT_GAIN * liquid.lateral.strike_strength,
            )

        self._update_liquid_speech(dt, liquid)

    def _update_liquid_speech(self, dt: float, liquid) -> None:
        terse = self._terse_speech()
        reach = liquid.longitudinal.reach

        if liquid.lateral.reach >= SURGE_LATERAL_WARN:
            self._liquid_lateral_cooldown_s = getattr(self, "_liquid_lateral_cooldown_s", 0.0)
            if self._liquid_lateral_cooldown_s <= 0.0:
                self._liquid_lateral_cooldown_s = SURGE_LATERAL_COOLDOWN_S
                self.ctx.say_event(
                    "Load running sideways. Ease off."
                    if terse
                    else (
                        "The load is running to the outside of the bend. "
                        "Ease off now -- baffles do nothing about this one."
                    ),
                    interrupt=True,
                    category=SpeechCategory.SAFETY,
                )
        else:
            self._liquid_lateral_cooldown_s = max(
                0.0, getattr(self, "_liquid_lateral_cooldown_s", 0.0) - dt
            )

        if reach >= SURGE_SPEAK_REACH and not getattr(self, "_liquid_surge_said", False):
            self._liquid_surge_said = True
            self._liquid_settled_said = False
            self.ctx.say_event(
                "Load running forward."
                if terse
                else (
                    "The load is running forward in the tank. "
                    "It will push you on when it gets there."
                ),
                interrupt=False,
                category=SpeechCategory.STATUS,
            )
            return

        # Settled: said once, after the wave has actually stayed down, so a
        # single quiet frame between cycles cannot claim it.
        if not getattr(self, "_liquid_surge_said", False):
            return
        if liquid.settled:
            self._liquid_settle_timer_s = getattr(self, "_liquid_settle_timer_s", 0.0) + dt
            if self._liquid_settle_timer_s >= SURGE_SETTLE_SPEAK_DELAY_S:
                self._liquid_surge_said = False
                self._liquid_settle_timer_s = 0.0
                if not getattr(self, "_liquid_settled_said", False):
                    self._liquid_settled_said = True
                    self.ctx.say_event(
                        "Load settled." if terse else "The load has settled.",
                        interrupt=False,
                        category=SpeechCategory.CONFIRMATION,
                    )
        else:
            self._liquid_settle_timer_s = 0.0

    def _stop_liquid_cues(self) -> None:
        """Drop the bed on any transition out of driving. A continuous sound
        must never outlive the thing it belongs to."""
        if getattr(self, "_liquid_wash_on", False):
            self.ctx.audio.stop_loop(CH_SURGE, fade_ms=120)
            self._liquid_wash_on = False

    # -- spoken on demand ---------------------------------------------------------

    def liquid_status_clause(self) -> str:
        """What is in the tank and how it will behave, for the status screens.

        A driver who cannot see the trailer has to be able to ask what they
        are hauling and get the answer that matters -- not the product name,
        which they already know, but whether this one will come back at them.
        """
        liquid = self._liquid()
        if liquid is None:
            return ""
        tank = liquid.describe_tank()
        fill = liquid.describe_fill()
        behaviour = (
            "Baffles will damp the wave in a couple of cycles."
            if liquid.baffled
            else "Smooth bore: nothing inside to slow the wave down."
        )
        return (
            f"Tank trailer, {fill}, {tank}. {behaviour} "
            f"One surge cycle takes about {liquid.period_s:.0f} seconds."
        )

    def liquid_condition_clause(self) -> str:
        """The load's condition in the words that fit a tank."""
        liquid = self._liquid()
        if liquid is None:
            return ""
        condition = float(getattr(self.truck, "cargo_damage_pct", 0.0))
        if condition < 1.0:
            return "settled"
        return f"{cargo_condition_text(condition, liquid=True)}, {condition:.0f} percent"

    # The pickup walk-around says what is in the tank and how it will behave;
    # that lives in states/city_pickup.py, where the driver is standing next to
    # the trailer and the truck does not exist yet.
