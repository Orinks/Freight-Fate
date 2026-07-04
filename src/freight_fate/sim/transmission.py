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
SHIFT_TIME = 1.0  # seconds of torque interruption


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
        self._shift_timer = SHIFT_TIME
        return ShiftResult(True, self._gear_name(target))

    def shift_up(self) -> ShiftResult:
        return self.request_gear(min(self.gear + 1, self.num_gears))

    def shift_down(self) -> ShiftResult:
        return self.request_gear(max(self.gear - 1, NEUTRAL))

    # -- automatic ---------------------------------------------------------------

    def auto_update(
        self, rpm: float, throttle: float, moving: bool, braking: bool = False
    ) -> int | None:
        """Pick a gear in automatic mode. Returns the new gear when it changes.

        While braking the box never upshifts -- a real automatic holds the gear
        for engine braking instead of grabbing a taller one as you slow, which
        otherwise read as "geared up while stopping"."""
        if not self.automatic or self.shifting:
            return None
        if self.in_reverse:
            return None
        if self.gear == NEUTRAL:
            if throttle > 0.05:
                self.gear = 1
                self._shift_timer = SHIFT_TIME
                return self.gear
            return None
        if not moving and self.gear > 1:
            # Stopped (or knocked to a crawl by a collision) in a high gear:
            # a real automatic returns to first instead of lugging until the
            # engine dies on every restart.
            self.gear = 1
            self._shift_timer = SHIFT_TIME
            return self.gear
        if rpm > AUTO_UPSHIFT_RPM and self.gear < self.num_gears and not braking:
            self.gear += 1
            self._shift_timer = SHIFT_TIME
            return self.gear
        if rpm < AUTO_DOWNSHIFT_RPM and self.gear > 1 and moving:
            self.gear -= 1
            self._shift_timer = SHIFT_TIME
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
        self._shift_timer = SHIFT_TIME
        return self.gear

    def update(self, dt: float) -> None:
        if self._shift_timer > 0.0:
            self._shift_timer = max(0.0, self._shift_timer - dt)

    @staticmethod
    def _gear_name(gear: int) -> str:
        if gear == REVERSE:
            return "reverse"
        return "neutral" if gear == NEUTRAL else f"gear {gear}"
