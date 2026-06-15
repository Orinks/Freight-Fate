"""Truck physics: engine, forces, fuel, temperatures, and wear.

Forces are computed in SI units on a longitudinal (1-D) model:
engine drive force, aerodynamic drag, rolling resistance, grade force,
and braking. The numbers are tuned around a loaded Class 8 tractor-trailer:
~36 t gross, ~475 hp, 10-speed box with overdrive, ~70 mph governed top
speed, and ~6.5 mpg at cruise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .transmission import Transmission

G = 9.81
AIR_DENSITY = 1.225

# Full service application plus the spring brakes: the hardest stop the rig
# can make, still scaled by weather grip and brake fade.
EMERGENCY_BRAKE_MULT = 1.6


@dataclass(frozen=True)
class TruckSpecs:
    mass_kg: float = 36_000.0          # loaded gross weight
    drag_coefficient: float = 0.65
    frontal_area_m2: float = 10.0
    rolling_resistance: float = 0.0065
    wheel_radius_m: float = 0.5
    max_torque_nm: float = 2_400.0     # ~1770 lb-ft
    idle_rpm: float = 600.0
    max_rpm: float = 2_200.0
    peak_torque_rpm: float = 1_300.0
    driveline_efficiency: float = 0.85
    max_brake_decel_g: float = 0.35
    brake_fade_temp_c: float = 400.0   # brakes fade above this temperature
    fuel_tank_gal: float = 150.0
    fuel_burn_factor: float = 1.0      # model-specific thirst multiplier
    engine_brake_force_n: float = 25_000.0


@dataclass
class TruckState:
    specs: TruckSpecs = field(default_factory=TruckSpecs)
    transmission: Transmission = field(default_factory=Transmission)

    engine_on: bool = False
    velocity_mps: float = 0.0
    rpm: float = 600.0
    throttle: float = 0.0
    brake: float = 0.0
    engine_brake: bool = False
    emergency_brake: bool = False

    fuel_gal: float = 150.0
    engine_temp_c: float = 60.0
    brake_temp_c: float = 20.0
    damage_pct: float = 0.0      # 0 = pristine, 100 = wrecked
    odometer_mi: float = 0.0

    # environment, set each frame by the trip/weather layer
    grade: float = 0.0           # +uphill, e.g. 0.06 = 6%
    grip: float = 1.0            # weather traction multiplier
    fuel_burn_mult: float = 1.0  # trip time compression so mpg stays honest

    stalled: bool = False

    def __post_init__(self) -> None:
        self.rpm = self.specs.idle_rpm
        self.fuel_gal = self.specs.fuel_tank_gal

    # -- engine ----------------------------------------------------------------

    def start_engine(self) -> bool:
        if self.engine_on:
            return False
        if self.fuel_gal <= 0:
            return False
        self.engine_on = True
        self.stalled = False
        self.rpm = self.specs.idle_rpm
        return True

    def stop_engine(self) -> None:
        self.engine_on = False
        self.throttle = 0.0

    def torque_at(self, rpm: float) -> float:
        """Flat-topped torque curve typical of a big diesel."""
        s = self.specs
        if rpm < s.idle_rpm * 0.8 or rpm > s.max_rpm:
            return 0.0
        x = (rpm - s.peak_torque_rpm) / (s.max_rpm - s.idle_rpm)
        shape = max(0.0, 1.0 - 1.8 * x * x)
        return s.max_torque_nm * shape

    @property
    def health_factor(self) -> float:
        """Power multiplier from accumulated damage."""
        return max(0.3, 1.0 - self.damage_pct / 150.0)

    def coupled_rpm(self, gear: int | None = None) -> float:
        """Engine RPM implied by road speed in the given gear."""
        tr = self.transmission
        ratio = tr.ratio_for(self.transmission.gear if gear is None else gear)
        if ratio <= 0:
            return self.rpm
        wheel_rps = self.velocity_mps / (2 * math.pi * self.specs.wheel_radius_m)
        return wheel_rps * 60.0 * ratio

    def auto_shift(self) -> int | None:
        """Run automatic shifting from road-speed-coupled RPM (immune to the
        free-revving RPM spike during a shift's torque interruption)."""
        tr = self.transmission
        if not tr.automatic or not self.engine_on:
            return None
        rpm_est = self.coupled_rpm() if not tr.in_neutral else self.rpm
        rpm_est = max(rpm_est, self.specs.idle_rpm * (0.5 + 0.5 * self.throttle))
        return tr.auto_update(rpm_est, self.throttle, self.velocity_mps > 0.5)

    # -- forces -----------------------------------------------------------------

    def drive_force(self) -> float:
        if not self.engine_on or self.stalled:
            return 0.0
        ratio = self.transmission.drive_ratio
        if ratio == 0.0:
            return 0.0
        torque = self.torque_at(self.rpm) * self.throttle * self.health_factor
        force = torque * ratio * self.specs.driveline_efficiency / self.specs.wheel_radius_m
        # traction limit: drive wheels carry roughly a third of gross weight
        traction_limit = self.specs.mass_kg * G * 0.33 * self.grip
        return min(force, traction_limit)

    def resistance_force(self) -> float:
        s = self.specs
        v = self.velocity_mps
        drag = 0.5 * AIR_DENSITY * s.drag_coefficient * s.frontal_area_m2 * v * abs(v)
        rolling = s.mass_kg * G * s.rolling_resistance * (1.0 if v > 0.01 else 0.0)
        grade_f = s.mass_kg * G * math.sin(math.atan(self.grade))
        return drag + rolling + grade_f

    def brake_force(self) -> float:
        if self.velocity_mps <= 0.0:
            return 0.0
        s = self.specs
        fade_temp = s.brake_fade_temp_c
        fade = (1.0 if self.brake_temp_c < fade_temp
                else max(0.35, 1.0 - (self.brake_temp_c - fade_temp) / 400))
        application = 1.0 if self.emergency_brake else self.brake
        boost = EMERGENCY_BRAKE_MULT if self.emergency_brake else 1.0
        service = s.mass_kg * G * s.max_brake_decel_g * application * boost * fade * self.grip
        jake = s.engine_brake_force_n if (self.engine_brake and self.engine_on
                                          and not self.transmission.in_neutral) else 0.0
        return service + jake

    # -- per-frame update ---------------------------------------------------------

    def update(self, dt: float) -> None:
        s = self.specs
        tr = self.transmission
        tr.update(dt)

        net = self.drive_force() - self.resistance_force() - self.brake_force()
        accel = net / s.mass_kg
        self.velocity_mps = max(0.0, self.velocity_mps + accel * dt)
        self.odometer_mi += self.velocity_mps * dt / 1609.344

        self._update_rpm(dt)
        self._update_fuel(dt)
        self._update_temps(dt)

    def _update_rpm(self, dt: float) -> None:
        s = self.specs
        tr = self.transmission
        if not self.engine_on:
            self.rpm = max(0.0, self.rpm - 1500 * dt)
            return
        ratio = tr.ratio_for(tr.gear) if not tr.in_neutral else 0.0
        coupled = ratio > 0.0 and tr.clutch <= 0.5 and not tr.shifting
        if coupled:
            wheel_rps = self.velocity_mps / (2 * math.pi * s.wheel_radius_m)
            road_rpm = wheel_rps * 60.0 * ratio
            if road_rpm < s.idle_rpm:
                # Launch regime: in a low gear the clutch slips and the engine
                # holds idle-or-better. In a high gear the engine lugs and stalls.
                if tr.gear >= 4 and road_rpm < s.idle_rpm * 0.5:
                    self.stall()
                    return
                self.rpm = max(s.idle_rpm, s.idle_rpm + (s.max_rpm - s.idle_rpm)
                               * self.throttle * 0.3)
            else:
                self.rpm = min(s.max_rpm, road_rpm)
        else:
            target = s.idle_rpm + (s.max_rpm - s.idle_rpm) * self.throttle
            self.rpm += (target - self.rpm) * min(1.0, 4.0 * dt)

    def stall(self) -> None:
        self.engine_on = False
        self.stalled = True
        self.rpm = 0.0

    def _update_fuel(self, dt: float) -> None:
        if not self.engine_on:
            return
        # ~0.8 gal/h at idle; load burn calibrated for ~6.5-7 mpg at 60 mph cruise
        power_kw = abs(self.drive_force()) * self.velocity_mps / 1000.0
        burn = (0.00022 + power_kw * 1.5e-5) * self.specs.fuel_burn_factor
        self.fuel_gal = max(0.0, self.fuel_gal - burn * dt * self.fuel_burn_mult)
        if self.fuel_gal <= 0.0:
            self.stop_engine()

    def _update_temps(self, dt: float) -> None:
        s = self.specs
        load = self.throttle * (self.rpm / s.max_rpm) if self.engine_on else 0.0
        target = 60.0 + (28.0 + 45.0 * load if self.engine_on else 0.0)
        self.engine_temp_c += (target - self.engine_temp_c) * 0.03 * dt

        applied = 1.0 if self.emergency_brake else self.brake
        heating = applied * self.velocity_mps * 2.2
        cooling = (self.brake_temp_c - 20.0) * (0.02 + 0.004 * self.velocity_mps)
        self.brake_temp_c = max(20.0, self.brake_temp_c + (heating - cooling) * dt)

        if self.rpm > s.max_rpm * 0.98 and self.engine_on:
            self.damage_pct = min(100.0, self.damage_pct + 0.8 * dt)

    # -- convenience ---------------------------------------------------------------

    @property
    def speed_mph(self) -> float:
        return self.velocity_mps * 2.23694

    @property
    def speed_kmh(self) -> float:
        return self.velocity_mps * 3.6

    @property
    def fuel_fraction(self) -> float:
        return self.fuel_gal / self.specs.fuel_tank_gal

    def refuel(self, gallons: float | None = None) -> float:
        """Fill the tank (or add ``gallons``); returns gallons added."""
        space = self.specs.fuel_tank_gal - self.fuel_gal
        added = space if gallons is None else min(space, max(0.0, gallons))
        self.fuel_gal += added
        return added

    def apply_collision(self, severity: float) -> None:
        """severity 0..1; slows the truck and adds damage."""
        self.velocity_mps *= max(0.2, 1.0 - severity)
        self.damage_pct = min(100.0, self.damage_pct + severity * 18.0)
