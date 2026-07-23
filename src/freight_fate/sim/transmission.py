"""Ten-speed truck transmission with manual and automatic modes.

Manual shifting follows the real sequence: press the clutch, pick the target
gear, release the clutch. Shifting without the clutch grinds and is refused.
Automatic mode shifts on RPM thresholds with a truck-like torque-interrupt delay.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Eaton-style overdrive 10-speed spread. The top range uses direct 9th and
# overdrive 10th so the automatic does not reach top gear at city speeds.
GEAR_RATIOS = (12.69, 9.29, 6.75, 4.90, 3.62, 2.59, 1.90, 1.38, 1.00, 0.74)
REVERSE_RATIO = 13.9
FINAL_DRIVE = 3.55
REVERSE = -1
NEUTRAL = 0

AUTO_UPSHIFT_RPM = 1750
AUTO_DOWNSHIFT_RPM = 1050
# Torque-interrupt length. Real AMTs are quickest in the low box -- small
# inertia steps and launch urgency -- and take the longest up top, so the
# time scales with the gear being ENGAGED (owner's ear after the Camp
# Verde-Kingman run: a one-second gap on a two-second low-gear pull reads
# as a long, "shifty" hole). SHIFT_TIME stays as the top-gear ceiling and
# the conservative figure the grade-loss estimate uses.
SHIFT_TIME = 1.0  # seconds of torque interruption, 10th-gear ceiling
SHIFT_TIME_LOW = 0.45  # through gear 4


def shift_time_for(gear: int) -> float:
    """Seconds of torque interruption for a shift engaging ``gear``."""
    g = max(1, min(10, gear))
    if g <= 4:
        return SHIFT_TIME_LOW
    return SHIFT_TIME_LOW + (SHIFT_TIME - SHIFT_TIME_LOW) * (g - 4) / 6.0
# With the engine brake working, a real automatic pre-selects a lower range
# to put the engine where the retarder bites (high RPM) instead of upshifting
# away from it. Downshift while below the target band, but never into a gear
# that would spin the engine past the ceiling.
JAKE_PRESELECT_RPM = 1700
JAKE_MAX_RPM = 2150
PROGRESSIVE_UPSHIFT_RPM = (1000, 1300, 1400, 1500, 1600, 1700, 1700, 1700, 1700, 1800)


@dataclass
class ShiftResult:
    ok: bool
    message: str
    grind: bool = False


@dataclass
class Transmission:
    automatic: bool = False
    gear: int = NEUTRAL  # -1 = reverse, 0 = neutral, 1..10
    clutch: float = 0.0  # 0 engaged .. 1 fully pressed
    _shift_timer: float = field(default=0.0, repr=False)
    _gear_hold_timer: float = field(default=999.0, repr=False)

    @property
    def num_gears(self) -> int:
        return len(GEAR_RATIOS)

    @property
    def in_neutral(self) -> bool:
        return self.gear == NEUTRAL

    @property
    def in_reverse(self) -> bool:
        return self.gear == REVERSE

    @property
    def shifting(self) -> bool:
        return self._shift_timer > 0.0

    @property
    def drive_ratio(self) -> float:
        """Overall ratio engine->wheels; zero when no torque path exists."""
        if self.in_neutral or self.shifting or self.clutch > 0.5:
            return 0.0
        if self.in_reverse:
            return -REVERSE_RATIO * FINAL_DRIVE
        return GEAR_RATIOS[self.gear - 1] * FINAL_DRIVE

    def ratio_for(self, gear: int) -> float:
        if gear == REVERSE:
            return -REVERSE_RATIO * FINAL_DRIVE
        return GEAR_RATIOS[gear - 1] * FINAL_DRIVE if gear else 0.0

    # -- manual ----------------------------------------------------------------

    def request_gear(self, target: int) -> ShiftResult:
        """Manual gear selection. Requires the clutch to be pressed."""
        if self.automatic:
            return ShiftResult(False, "Transmission is in automatic mode")
        if not REVERSE <= target <= self.num_gears:
            return ShiftResult(False, f"No gear {target}")
        if target == self.gear:
            return ShiftResult(False, f"Already in {self._gear_name(target)}")
        if self.clutch < 0.8 and target != NEUTRAL:
            return ShiftResult(False, "Clutch not pressed", grind=True)
        self.gear = target
        self._shift_timer = shift_time_for(self.gear)
        return ShiftResult(True, self._gear_name(target))

    def shift_up(self) -> ShiftResult:
        return self.request_gear(min(self.gear + 1, self.num_gears))

    def shift_down(self) -> ShiftResult:
        return self.request_gear(max(self.gear - 1, NEUTRAL))

    # -- automatic ---------------------------------------------------------------

    def auto_update(
        self,
        rpm: float,
        throttle: float,
        moving: bool,
        braking: bool = False,
        can_upshift: bool = True,
        minimum_shift_interval_s: float = 0.0,
        upshift_rpm: float = AUTO_UPSHIFT_RPM,
        start_gear: int = 1,
        upshift_steps: int = 1,
        downshift_target: int | None = None,
        engine_braking: bool = False,
        downshift_rpm: float = AUTO_DOWNSHIFT_RPM,
    ) -> int | None:
        """Pick a gear in automatic mode. Returns the new gear when it changes.

        While braking the box never upshifts -- a real automatic holds the gear
        for engine braking instead of grabbing a taller one as you slow, which
        otherwise read as "geared up while stopping". With the engine brake
        active it goes further and pre-selects DOWN toward the retard band,
        because a jake in overdrive at low RPM is barely a brake at all."""
        if not self.automatic or self.shifting:
            return None
        if self.in_reverse:
            return None
        if self.gear == NEUTRAL:
            if throttle > 0.05:
                self.gear = max(1, min(self.num_gears, start_gear))
                self._shift_timer = shift_time_for(self.gear)
                self._gear_hold_timer = 0.0
                return self.gear
            return None
        restart_gear = max(1, min(self.num_gears, start_gear))
        if not moving and self.gear > restart_gear:
            # Stopped (or knocked to a crawl by a collision) in a high gear:
            # a real automatic returns to its starting gear -- first when
            # grossed out, third when light -- instead of lugging until the
            # engine dies on every restart. Snapping all the way to first
            # regardless used to throw away the light rig's start gear
            # before the truck had rolled a foot.
            self.gear = restart_gear
            self._shift_timer = shift_time_for(self.gear)
            self._gear_hold_timer = 0.0
            return self.gear
        # The comfort hold between shifts never delays engine protection:
        # with the road driving the engine past the jake ceiling, the box
        # upshifts NOW, timer or no timer. Under power the governor caps RPM,
        # so the hold stays in charge and anti-hunting keeps its teeth.
        if self._gear_hold_timer < minimum_shift_interval_s and not (
            engine_braking and rpm > JAKE_MAX_RPM
        ):
            return None
        # Braking or engine-braking holds the gear -- except that a real
        # automatic protects its engine: once the road spins it past the
        # ceiling, the box upshifts anyway. On a downgrade that trades
        # engine safety for a taller gear and a weaker jake, which is
        # exactly the runaway spiral a mismanaged descent earns.
        hold_gear = (braking or engine_braking) and rpm < JAKE_MAX_RPM
        if rpm > upshift_rpm and self.gear < self.num_gears and not hold_gear and can_upshift:
            self.gear = min(self.num_gears, self.gear + max(1, upshift_steps))
            self._shift_timer = shift_time_for(self.gear)
            self._gear_hold_timer = 0.0
            return self.gear
        if engine_braking and moving and self.gear > 1 and rpm < JAKE_PRESELECT_RPM:
            lower = GEAR_RATIOS[self.gear - 2]
            current = GEAR_RATIOS[self.gear - 1]
            if rpm * lower / current <= JAKE_MAX_RPM:
                self.gear -= 1
                self._shift_timer = shift_time_for(self.gear)
                self._gear_hold_timer = 0.0
                return self.gear
        if rpm < downshift_rpm and self.gear > 1 and moving:
            target = self.gear - 1 if downshift_target is None else downshift_target
            self.gear = max(1, min(self.gear - 1, target))
            self._shift_timer = shift_time_for(self.gear)
            self._gear_hold_timer = 0.0
            return self.gear
        return None

    def kickdown(self) -> int | None:
        """Emergency single downshift to keep an automatic out of a lugging
        gear while still rolling. The normal RPM-threshold downshift can be
        outrun by a hard deceleration during the shift delay; this forces the
        drop so the engine kicks down instead of stalling. No-op in manual."""
        if not self.automatic or self.gear <= 1:
            return None
        self.gear -= 1
        self._shift_timer = shift_time_for(self.gear)
        self._gear_hold_timer = 0.0
        return self.gear

    def update(self, dt: float) -> None:
        self._gear_hold_timer += max(0.0, dt)
        if self._shift_timer > 0.0:
            self._shift_timer = max(0.0, self._shift_timer - dt)

    @staticmethod
    def _gear_name(gear: int) -> str:
        if gear == REVERSE:
            return "reverse"
        return "neutral" if gear == NEUTRAL else f"gear {gear}"
