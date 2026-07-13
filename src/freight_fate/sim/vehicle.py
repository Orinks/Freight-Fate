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
MAX_REVERSE_MPS = 4.5  # about 10 mph: backing speed, not road speed

KG_PER_TON = 1000.0  # game cargo "tons" are treated as metric tonnes
# Reference loaded Class 8: ~36 t gross at a full ~21.5 t payload, leaving a
# ~14.5 t tractor-and-empty-trailer tare. A TruckState's default cargo equals
# this reference payload, so an unconfigured truck keeps the original loaded
# behavior; lighter loads (and empty deadheads) weigh proportionally less.
REFERENCE_CARGO_KG = 21_500.0
LAUNCH_TRACTION_LOW_SPEED_MPH = 25.0
LAUNCH_TRACTION_START_G = 0.12
LAUNCH_TRACTION_ROLLING_G = 0.33

# -- rig wear -------------------------------------------------------------------
# Tires, brakes, and the engine wear from how the truck is driven, not just
# from miles. Distance- and energy-coupled terms scale with the trip's time
# compression (carried in ``fuel_burn_mult``) so wear per game mile stays
# honest at any time scale; the abuse terms (over-rev, lugging) charge per
# real second of the behavior, like the damage accrual they replace.
# Absolute rates are compressed for playability; the ratios are the point:
# jake-braked descents spare the service brakes, heavy loads chew tires,
# and redline abuse eats the engine.
TIRE_WEAR_PCT_PER_MILE = 0.003  # tread loss per mile at the rated gross
TIRE_WEAR_BRAKING_PCT = 2.0e-4  # extra per (application x m/s x s): stops scrub tread
BRAKE_WEAR_PCT_PER_MJ = 4.0e-3  # per megajoule actually dissipated in the shoes
BRAKE_WEAR_HOT_MULT = 2.0  # glazing: wear doubles once the shoes are past fade
ENGINE_WEAR_PCT_PER_H_IDLE = 0.03
ENGINE_WEAR_PCT_PER_H_FULL_LOAD = 0.15
ENGINE_WEAR_OVER_REV_PCT_PER_S = 0.8  # was the damage_pct redline penalty
ENGINE_WEAR_LUG_PCT_PER_S = 0.05  # heavy throttle far below the torque band
LUG_THROTTLE = 0.7
LUG_RPM_FRACTION = 0.7  # of peak-torque RPM

# -- jake brake -----------------------------------------------------------------
# The engine brake is retarding TORQUE at the crank, not a flat force at the
# wheels: wheel force = torque x gear ratio / wheel radius, so the jake bites
# hard in a low gear at high RPM and does almost nothing in overdrive at low
# RPM. Three stages (two, four, six cylinders) scale the torque, and retard
# grows with RPM -- which is the whole grade discipline: pick the gear and
# the speed BEFORE the hill, because the jake rewards being set up early.
JAKE_STAGES = 3
JAKE_RPM_FLOOR = 0.3  # fraction of full retard left near idle speed

# A hill can drive the engine past the governor through the wheels; power
# alone cannot. Sitting AT governed speed is safe -- overspeed wear starts
# just beyond it, which is what actually hurts a diesel.
ROAD_OVERSPEED_RPM_MULT = 1.15  # how far the road can spin the engine past governed
OVER_REV_RPM_MULT = 1.02  # abuse wear begins past this multiple of governed speed

# -- brake heat -------------------------------------------------------------------
# Heating is the real dissipated power (service brake force times speed)
# soaked into the drums' thermal mass, so faded shoes that grip less also
# heat less and the model finds its own equilibrium. Cooling is convective
# and grows with the square root of speed: outrunning your brakes does not
# also air-condition them.
AMBIENT_C = 20.0
BRAKE_COOL_BASE_PER_S = 0.0006  # fraction of excess heat shed per second, parked
BRAKE_COOL_SPEED_PER_S = 0.0006  # extra fraction per sqrt(m/s) of airflow

# -- traction -----------------------------------------------------------------
# Hydroplaning follows the Horne relation: onset speed goes with the square
# root of tire pressure, about 106 mph for a fresh ribbed truck tire at
# highway pressure -- which is why a properly shod truck essentially never
# planes. Worn tread and deeper standing water pull the onset down into the
# speeds the game actually drives; past onset the tires ride the water film
# and grip collapses toward its floor over a short speed band.
HYDRO_ONSET_BASE_MPH = 106.0  # ~10.35 x sqrt(105 psi), fresh tread in a thin film
HYDRO_TREAD_LOSS = 0.45  # bald tires plane at 55 percent of the fresh onset speed
HYDRO_MIN_WATER_MM = 0.8  # a thinner film cannot float a loaded truck tire
HYDRO_WATER_LOSS_PER_MM = 0.06  # onset drop per millimeter past the minimum film
HYDRO_FULL_BAND_MPH = 12.0  # mph past onset where the collapse bottoms out
HYDRO_GRIP_FLOOR = 0.30  # fraction of wet grip left when fully planing

# The jake retards through the drive axle alone, so its force is capped by
# that axle's share of the grip -- not the whole rig's. Half the axle's
# static grip is the usable margin before compression braking breaks the
# drive wheels loose (the start of a trolley jackknife). Dry pavement never
# reaches the cap; glare ice puts full stage 3 in a low gear well past it.
DRIVE_AXLE_LOAD_FRACTION = 0.425  # tandem drives carry 34k of an 80k gross
JAKE_LOCK_MARGIN = 0.5  # usable fraction of drive-axle grip before the wheels slide

# Traction equipment. Tire compound and chains multiply the weather's grip on
# the surfaces they were made for, and both trades are honest: winter rubber
# is a softer compound that bites cold snow but wears faster and gives up a
# little on warm dry pavement; chains are the only thing that truly holds
# glare ice, and they are consumable -- sized for packed snow at chain speed,
# they grind themselves apart on bare pavement or past CHAIN_SAFE_MPH until a
# cross chain lets go into the fender. Wear rates are compressed for
# playability like every other wear constant; the trade-offs are not.
TIRE_ALL_SEASON = "all_season"
TIRE_WINTER = "winter"
WINTER_SNOW_GRIP_MULT = 1.30
WINTER_ICE_GRIP_MULT = 1.50  # 0.15 becomes 0.22: better, still frightening
WINTER_DRY_GRIP_LOSS = 0.03  # the soft compound squirms a little on warm dry roads
WINTER_TREAD_WEAR_MULT = 1.5  # and it wears half again as fast
CHAIN_SNOW_GRIP_MULT = 1.50  # chained packed snow drives about like rain
CHAIN_ICE_GRIP_MULT = 2.50  # 0.15 becomes 0.38: crossable, carefully
CHAIN_BARE_GRIP_LOSS = 0.15  # steel between the tread and dry pavement
CHAIN_SAFE_MPH = 30.0  # chain speed; faster hammers the links apart
CHAIN_WEAR_PCT_PER_MILE = 0.2  # about 500 miles of life used right
CHAIN_WEAR_OVERSPEED_MULT = 6.0
CHAIN_WEAR_BARE_MULT = 40.0  # bare pavement eats a set in a couple of miles
CHAIN_SNAP_DAMAGE_PCT = 4.0  # the freed cross chains flail the fender and lines

# What wear does to the physics.
TIRE_WEAR_GRIP_LOSS = 0.25  # bald tires lose a quarter of their grip
BRAKE_WEAR_FORCE_LOSS = 0.30  # worn shoes lose up to 30% braking force
BRAKE_WEAR_FADE_LOSS_C = 150.0  # and start fading this much sooner
ENGINE_WEAR_POWER_LOSS = 0.25  # a tired engine is down up to a quarter
ENGINE_WEAR_FUEL_PENALTY = 0.15  # and burns up to 15% more fuel for its power


@dataclass(frozen=True)
class TruckSpecs:
    mass_kg: float = 36_000.0  # gross weight at the reference payload
    drag_coefficient: float = 0.65
    frontal_area_m2: float = 10.0
    rolling_resistance: float = 0.0065
    wheel_radius_m: float = 0.5
    max_torque_nm: float = 2_400.0  # ~1770 lb-ft
    idle_rpm: float = 600.0
    max_rpm: float = 2_200.0
    peak_torque_rpm: float = 1_300.0
    driveline_efficiency: float = 0.85
    max_brake_decel_g: float = 0.35
    brake_fade_temp_c: float = 400.0  # brakes fade above this temperature
    brake_thermal_mass_j_per_c: float = 180_000.0  # drums and shoes, all ten positions
    fuel_tank_gal: float = 150.0
    fuel_burn_factor: float = 1.0  # model-specific thirst multiplier
    engine_brake_torque_nm: float = 1_800.0  # stage-3 retarding torque near rated RPM
    # Air-brake thresholds follow official CDL references: FMCSA gives
    # typical compressor cut-out/cut-in ranges, California places low-air
    # warnings at 55-75 psi, and Georgia describes spring brakes applying
    # around 20-45 psi. Runtime build rates are intentionally compressed for
    # playability; see README.md for source URLs and simplification notes.
    air_governor_cut_out_psi: float = 125.0
    air_governor_cut_in_psi: float = 100.0
    air_low_warning_psi: float = 60.0
    air_spring_brake_psi: float = 40.0
    air_parking_release_psi: float = 100.0
    air_cold_start_psi: float = 55.0
    air_build_idle_psi_per_s: float = 4.0
    air_build_fast_psi_per_s: float = 7.0
    air_loss_primary_per_application_psi: float = 4.5
    air_loss_secondary_per_application_psi: float = 3.5
    air_loss_trailer_per_application_psi: float = 2.0
    air_loss_per_application_psi: float = 4.0  # legacy tuning reference
    air_loss_hold_psi_per_s: float = 0.25


@dataclass
class TruckState:
    specs: TruckSpecs = field(default_factory=TruckSpecs)
    transmission: Transmission = field(default_factory=Transmission)

    engine_on: bool = False
    velocity_mps: float = 0.0
    rpm: float = 600.0
    throttle: float = 0.0
    brake: float = 0.0
    engine_brake_stage: int = 0  # 0 = off, 1..JAKE_STAGES = cylinders engaged
    emergency_brake: bool = False
    parking_brake: bool = False
    primary_air_psi: float = 125.0
    secondary_air_psi: float = 125.0
    trailer_air_psi: float = 125.0
    air_compressor_active: bool = False

    fuel_gal: float = 150.0
    engine_temp_c: float = 60.0
    brake_temp_c: float = 20.0
    damage_pct: float = 0.0  # incident damage: collisions, leaving the road
    tire_wear_pct: float = 0.0  # 0 = fresh tread, 100 = bald
    brake_wear_pct: float = 0.0  # 0 = new shoes, 100 = metal on metal
    engine_wear_pct: float = 0.0  # 0 = fresh overhaul, 100 = worn out
    tire_type: str = TIRE_ALL_SEASON  # all_season or winter, follows the truck
    chains_on: bool = False  # steel on the drives; installed and pulled at a stop
    chain_wear_pct: float = 0.0  # 0 = fresh set, 100 = snapped or scrap
    chains_just_snapped: bool = False  # one-shot event flag, consumed by the cue layer
    odometer_mi: float = 0.0
    cargo_kg: float = REFERENCE_CARGO_KG  # payload aboard; default = full reference load

    # environment, set each frame by the trip/weather layer
    grade: float = 0.0  # +uphill, e.g. 0.06 = 6%
    grip: float = 1.0  # weather traction multiplier
    water_mm: float = 0.0  # standing water on the road; drives hydroplaning
    surface: str = "dry"  # dry, wet, snow, or ice; keys the traction equipment
    drag_mult: float = 1.0  # weather aero drag multiplier (headwinds/storms)
    fuel_burn_mult: float = 1.0  # trip time compression so mpg stays honest
    tire_wear_buff_mult: float = 1.0  # driver-care buff on tread wear (data/buffs.py)
    engine_wear_buff_mult: float = 1.0  # driver-care buff on duty-cycle engine wear

    stalled: bool = False
    _last_service_air_application: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        self.rpm = self.specs.idle_rpm
        self.fuel_gal = self.specs.fuel_tank_gal

    # Not a dataclass field: the bool view proxies the staged jake so every
    # existing on/off call site keeps working. Switching on selects full
    # retard; the stage keys pick lighter settings.
    @property
    def engine_brake(self) -> bool:
        return self.engine_brake_stage > 0

    @engine_brake.setter
    def engine_brake(self, value: bool) -> None:
        self.engine_brake_stage = JAKE_STAGES if value else 0

    # -- engine ----------------------------------------------------------------

    def start_engine(self) -> bool:
        if self.engine_on:
            return False
        if self.fuel_gal <= 0:
            return False
        self.engine_on = True
        self.stalled = False
        self.rpm = self.specs.idle_rpm
        self._sync_air_compressor()
        return True

    def stop_engine(self) -> None:
        self.engine_on = False
        self.throttle = 0.0
        self.air_compressor_active = False

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
        """Power multiplier from accumulated incident damage."""
        return max(0.3, 1.0 - self.damage_pct / 150.0)

    # -- wear effects ------------------------------------------------------------

    @property
    def hydro_onset_mph(self) -> float | None:
        """The speed where the tires start riding the water film, or None when
        the road holds too little water to float a loaded truck tire. Chains
        bite through the film, so a chained truck cannot plane."""
        if self.chains_on or self.water_mm < HYDRO_MIN_WATER_MM:
            return None
        tread = 1.0 - HYDRO_TREAD_LOSS * self.tire_wear_pct / 100.0
        water = max(0.5, 1.0 - HYDRO_WATER_LOSS_PER_MM * (self.water_mm - HYDRO_MIN_WATER_MM))
        return HYDRO_ONSET_BASE_MPH * tread * water

    @property
    def hydroplaning(self) -> bool:
        onset = self.hydro_onset_mph
        return onset is not None and self.speed_mph > onset

    def _hydro_grip_mult(self) -> float:
        """1.0 below onset, collapsing toward the floor as speed leaves the
        onset behind. Slowing down restores contact -- and grip -- smoothly."""
        onset = self.hydro_onset_mph
        if onset is None or self.speed_mph <= onset:
            return 1.0
        frac = min(1.0, (self.speed_mph - onset) / HYDRO_FULL_BAND_MPH)
        return 1.0 - (1.0 - HYDRO_GRIP_FLOOR) * frac

    @property
    def traction_equipment_mult(self) -> float:
        """Grip multiplier from chains or the tire compound on this surface.

        Chains put steel between the tread and the road, so they speak for
        the contact patch alone -- the tire type under them stops mattering.
        """
        if self.chains_on:
            if self.surface == "ice":
                return CHAIN_ICE_GRIP_MULT
            if self.surface == "snow":
                return CHAIN_SNOW_GRIP_MULT
            return 1.0 - CHAIN_BARE_GRIP_LOSS
        if self.tire_type == TIRE_WINTER:
            if self.surface == "ice":
                return WINTER_ICE_GRIP_MULT
            if self.surface == "snow":
                return WINTER_SNOW_GRIP_MULT
            if self.surface == "dry":
                return 1.0 - WINTER_DRY_GRIP_LOSS
        return 1.0

    @property
    def effective_grip(self) -> float:
        """Weather grip degraded by tread wear and hydroplaning, helped or
        hurt by traction equipment; bald tires make every surface worse and
        float sooner in standing water. With chains on, steel is the contact
        patch: tread wear and the water film stop mattering."""
        equip = self.traction_equipment_mult
        if self.chains_on:
            return self.grip * equip
        tread = 1.0 - TIRE_WEAR_GRIP_LOSS * self.tire_wear_pct / 100.0
        return self.grip * tread * equip * self._hydro_grip_mult()

    @property
    def brake_wear_factor(self) -> float:
        return 1.0 - BRAKE_WEAR_FORCE_LOSS * self.brake_wear_pct / 100.0

    @property
    def brake_fade_onset_c(self) -> float:
        """Worn shoes start fading cooler than the spec sheet says."""
        return self.specs.brake_fade_temp_c - BRAKE_WEAR_FADE_LOSS_C * self.brake_wear_pct / 100.0

    @property
    def engine_wear_factor(self) -> float:
        return 1.0 - ENGINE_WEAR_POWER_LOSS * self.engine_wear_pct / 100.0

    @property
    def tare_kg(self) -> float:
        """Tractor plus empty trailer: gross weight carrying no payload."""
        return max(0.0, self.specs.mass_kg - REFERENCE_CARGO_KG)

    @property
    def gross_mass_kg(self) -> float:
        """Current gross weight: tare plus the payload aboard.

        Drives acceleration, grade and rolling resistance, braking, and (via
        the forces) fuel burn, so a heavy load pulls away gently, lugs on
        grades, and stops longer, while an empty deadhead is light and brisk.
        """
        return self.tare_kg + max(0.0, self.cargo_kg)

    def coupled_rpm(self, gear: int | None = None) -> float:
        """Engine RPM implied by road speed in the given gear."""
        tr = self.transmission
        ratio = tr.ratio_for(self.transmission.gear if gear is None else gear)
        if ratio == 0:
            return self.rpm
        wheel_rps = abs(self.velocity_mps) / (2 * math.pi * self.specs.wheel_radius_m)
        return wheel_rps * 60.0 * abs(ratio)

    def auto_shift(self) -> int | None:
        """Run automatic shifting from road-speed-coupled RPM (immune to the
        free-revving RPM spike during a shift's torque interruption)."""
        tr = self.transmission
        if not tr.automatic or not self.engine_on:
            return None
        rpm_est = self.coupled_rpm() if not tr.in_neutral else self.rpm
        rpm_est = max(rpm_est, self.specs.idle_rpm * (0.5 + 0.5 * self.throttle))
        braking = self.brake > 0.01 or self.emergency_brake or self.air_brakes_holding
        jaking = self.engine_brake_stage > 0 and self.engine_on and self.throttle <= 0.05
        return tr.auto_update(
            rpm_est, self.throttle, self.velocity_mps > 0.5, braking, engine_braking=jaking
        )

    # -- forces -----------------------------------------------------------------

    def drive_force(self) -> float:
        if not self.engine_on or self.stalled or self.air_brakes_holding:
            return 0.0
        ratio = self.transmission.drive_ratio
        if ratio == 0.0:
            return 0.0
        torque = self.torque_at(self.rpm) * self.throttle * self.health_factor
        torque *= self.engine_wear_factor
        direction = -1.0 if ratio < 0 else 1.0
        force = torque * abs(ratio) * self.specs.driveline_efficiency / self.specs.wheel_radius_m
        # Drive wheels can use roughly a third of gross weight once rolling,
        # but a loaded tractor-trailer eases into that force instead of
        # launching at the full traction cap from a dead stop.
        launch = min(1.0, self.speed_mph / LAUNCH_TRACTION_LOW_SPEED_MPH)
        traction_g = (
            LAUNCH_TRACTION_START_G + (LAUNCH_TRACTION_ROLLING_G - LAUNCH_TRACTION_START_G) * launch
        )
        traction_limit = self.gross_mass_kg * G * traction_g * self.effective_grip
        return direction * min(force, traction_limit)

    def resistance_force(self) -> float:
        s = self.specs
        v = self.velocity_mps
        direction = 1.0 if v > 0.01 else -1.0 if v < -0.01 else 0.0
        drag = (
            0.5 * AIR_DENSITY * s.drag_coefficient * s.frontal_area_m2 * self.drag_mult * v * abs(v)
        )
        rolling = self.gross_mass_kg * G * s.rolling_resistance * direction
        grade_f = self.gross_mass_kg * G * math.sin(math.atan(self.grade))
        return drag + rolling + grade_f

    def service_brake_force(self) -> float:
        """Magnitude of the foundation-brake force biting the drums right now.

        This is the force that heats and wears the shoes; the jake is kept
        separate because its energy goes out the exhaust, not into the drums.
        """
        if abs(self.velocity_mps) <= 0.01:
            return 0.0
        s = self.specs
        fade_temp = self.brake_fade_onset_c
        fade = (
            1.0
            if self.brake_temp_c < fade_temp
            else max(0.20, 1.0 - (self.brake_temp_c - fade_temp) / 300)
        )
        holding = self.air_brakes_holding
        application = 1.0 if self.emergency_brake or holding else self.brake
        boost = EMERGENCY_BRAKE_MULT if self.emergency_brake or holding else 1.0
        effort = G * s.max_brake_decel_g * application * boost * fade * self.brake_wear_factor
        # Tire friction scales with the weight on the tires (and weather grip);
        # the foundation brakes have a fixed force ceiling sized for the rated
        # gross (``specs.mass_kg``). A load at or below the rated weight reaches
        # the friction-limited deceleration (unchanged behavior), but a heavier
        # load is brake-capacity limited -- the brakes cannot generate enough
        # force for its mass, so it decelerates more gently and stops longer.
        friction = self.gross_mass_kg * effort * self.effective_grip
        capacity = s.mass_kg * effort
        return min(friction, capacity)

    def jake_retard_torque_nm(self) -> float:
        """Compression-brake torque at the crank for the current stage and RPM."""
        if (
            self.engine_brake_stage <= 0
            or not self.engine_on
            or self.throttle > 0.05
            or self.transmission.in_neutral
        ):
            return 0.0
        s = self.specs
        rpm_frac = max(0.0, min(1.0, self.rpm / s.max_rpm))
        stage = min(JAKE_STAGES, self.engine_brake_stage) / JAKE_STAGES
        return s.engine_brake_torque_nm * stage * (
            JAKE_RPM_FLOOR + (1.0 - JAKE_RPM_FLOOR) * rpm_frac
        )

    def _jake_force_demand(self) -> float:
        """Wheel force the jake asks for: crank torque through the gearing.

        The gear ratio is the multiplier, so the same stage that pins the
        speed in 7th barely leans on the truck in overdrive -- and it drops
        out entirely mid-shift, exactly like the drive torque does.
        """
        ratio = abs(self.transmission.drive_ratio)
        if ratio == 0.0 or abs(self.velocity_mps) <= 0.01:
            return 0.0
        s = self.specs
        return self.jake_retard_torque_nm() * ratio * s.driveline_efficiency / s.wheel_radius_m

    def _jake_traction_cap(self) -> float:
        """The most retard the drive axle can transmit before its wheels slide."""
        return (
            self.gross_mass_kg * G * DRIVE_AXLE_LOAD_FRACTION * JAKE_LOCK_MARGIN
            * self.effective_grip
        )

    def jake_brake_force(self) -> float:
        """Retarding force actually delivered: demand, capped by drive-axle grip.

        On dry pavement the cap sits far above anything the jake can ask for;
        on ice a hard stage in a low gear runs into it, which is the physics
        behind the CDL rule about compression brakes on slick roads.
        """
        demand = self._jake_force_demand()
        if demand <= 0.0:
            return 0.0
        return min(demand, self._jake_traction_cap())

    @property
    def jake_slipping(self) -> bool:
        """Whether the jake is asking for more than the drive axle can hold --
        the drive wheels breaking loose, the start of a trolley jackknife."""
        demand = self._jake_force_demand()
        return demand > 0.0 and demand > self._jake_traction_cap()

    def brake_force(self) -> float:
        if abs(self.velocity_mps) <= 0.01:
            return 0.0
        direction = 1.0 if self.velocity_mps > 0 else -1.0
        return direction * (self.service_brake_force() + self.jake_brake_force())

    # -- per-frame update ---------------------------------------------------------

    def update(self, dt: float) -> None:
        tr = self.transmission
        tr.update(dt)
        self._update_air_system(dt)

        net = self.drive_force() - self.resistance_force() - self.brake_force()
        accel = net / self.gross_mass_kg
        old_v = self.velocity_mps
        new_v = self.velocity_mps + accel * dt
        drive_force = self.drive_force()
        if self.air_brakes_holding and abs(old_v) < 0.05 and abs(new_v) < 0.05:
            new_v = 0.0
        if (old_v > 0.0 > new_v and drive_force <= 0.0) or (
            old_v < 0.0 < new_v and drive_force >= 0.0
        ):
            new_v = 0.0
        if self.transmission.in_reverse:
            new_v = max(-MAX_REVERSE_MPS, new_v)
        elif new_v < 0.0:
            new_v = 0.0
        self.velocity_mps = new_v
        self.odometer_mi += abs(self.velocity_mps) * dt / 1609.344

        self._update_rpm(dt)
        self._update_fuel(dt)
        self._update_temps(dt)
        self._update_wear(dt)

    # -- air brakes ---------------------------------------------------------------

    @property
    def air_pressure_psi(self) -> float:
        """Compatibility view: the lowest available service/supply reservoir."""
        return min(self.primary_air_psi, self.secondary_air_psi, self.trailer_air_psi)

    @air_pressure_psi.setter
    def air_pressure_psi(self, value: float) -> None:
        self._set_all_air_reservoirs(value)

    @property
    def air_low_warning(self) -> bool:
        return self.air_pressure_psi <= self.specs.air_low_warning_psi

    @property
    def spring_brakes_active(self) -> bool:
        return self.air_pressure_psi <= self.specs.air_spring_brake_psi

    @property
    def air_ready(self) -> bool:
        return self.air_pressure_psi >= self.specs.air_parking_release_psi

    @property
    def air_brakes_holding(self) -> bool:
        return self.parking_brake or self.spring_brakes_active

    def set_cold_air_start(self) -> None:
        """Parked trip start: low air, spring/parking brakes set."""
        self._set_all_air_reservoirs(self.specs.air_cold_start_psi)
        self.parking_brake = True
        self.air_compressor_active = False
        self._last_service_air_application = 0.0

    def set_air_ready(self, *, parking_brake: bool = True) -> None:
        """Compatibility/default state: charged tanks, parked safely."""
        self._set_all_air_reservoirs(self.specs.air_governor_cut_out_psi)
        self.parking_brake = parking_brake
        self.air_compressor_active = False
        self._last_service_air_application = 0.0

    def set_parking_brake(self) -> None:
        self.parking_brake = True

    def release_parking_brake(self) -> bool:
        if not self.air_ready:
            return False
        self.parking_brake = False
        self.primary_air_psi = self._clamp_air_psi(self.primary_air_psi - 1.0)
        self.secondary_air_psi = self._clamp_air_psi(self.secondary_air_psi - 1.0)
        self.trailer_air_psi = self._clamp_air_psi(self.trailer_air_psi - 1.5)
        self._sync_air_compressor()
        return True

    def air_brake_snapshot(self) -> dict:
        return {
            "schema": 2,
            "pressure_psi": round(self.air_pressure_psi, 1),
            "primary_psi": round(self.primary_air_psi, 1),
            "secondary_psi": round(self.secondary_air_psi, 1),
            "trailer_psi": round(self.trailer_air_psi, 1),
            "parking_brake": self.parking_brake,
            "compressor_active": self.air_compressor_active,
        }

    def restore_air_brake_snapshot(self, data: object, *, default_ready: bool) -> None:
        if not isinstance(data, dict):
            if default_ready:
                self.set_air_ready(parking_brake=True)
            else:
                self.set_cold_air_start()
            return
        fallback = data.get("pressure_psi", self.specs.air_governor_cut_out_psi)
        self.primary_air_psi = self._snapshot_air_value(data.get("primary_psi", fallback))
        self.secondary_air_psi = self._snapshot_air_value(data.get("secondary_psi", fallback))
        self.trailer_air_psi = self._snapshot_air_value(data.get("trailer_psi", fallback))
        self.parking_brake = bool(data.get("parking_brake", True))
        self.air_compressor_active = bool(data.get("compressor_active", False))
        self._last_service_air_application = 0.0
        if self.spring_brakes_active:
            self.parking_brake = True
        self._sync_air_compressor()

    def _clamp_air_psi(self, value: float) -> float:
        return max(0.0, min(self.specs.air_governor_cut_out_psi, value))

    def _snapshot_air_value(self, value: object) -> float:
        try:
            return self._clamp_air_psi(float(value))
        except (TypeError, ValueError):
            return self.specs.air_governor_cut_out_psi

    def _set_all_air_reservoirs(self, value: float) -> None:
        pressure = self._clamp_air_psi(value)
        self.primary_air_psi = pressure
        self.secondary_air_psi = pressure
        self.trailer_air_psi = pressure

    def _sync_air_compressor(self) -> None:
        if not self.engine_on:
            self.air_compressor_active = False
            return
        reservoirs = (self.primary_air_psi, self.secondary_air_psi, self.trailer_air_psi)
        if min(reservoirs) <= self.specs.air_governor_cut_in_psi:
            self.air_compressor_active = True
        elif min(reservoirs) >= self.specs.air_governor_cut_out_psi:
            self.air_compressor_active = False

    def _update_air_system(self, dt: float) -> None:
        self._consume_brake_air(dt)
        if self.spring_brakes_active:
            self.parking_brake = True
        self._sync_air_compressor()
        if self.air_compressor_active and self.engine_on:
            rpm_span = max(1.0, self.specs.max_rpm - self.specs.idle_rpm)
            rpm_factor = max(0.0, min(1.0, (self.rpm - self.specs.idle_rpm) / rpm_span))
            rate = (
                self.specs.air_build_idle_psi_per_s
                + (self.specs.air_build_fast_psi_per_s - self.specs.air_build_idle_psi_per_s)
                * rpm_factor
            )
            self.primary_air_psi = self._clamp_air_psi(self.primary_air_psi + rate * dt)
            self.secondary_air_psi = self._clamp_air_psi(self.secondary_air_psi + rate * 0.96 * dt)
            self.trailer_air_psi = self._clamp_air_psi(self.trailer_air_psi + rate * 0.85 * dt)
        self._sync_air_compressor()

    def _consume_brake_air(self, dt: float) -> None:
        application = max(0.0, min(1.0, self.brake))
        if self.emergency_brake:
            application = 1.0
        rising = max(0.0, application - self._last_service_air_application)
        hold = application * self.specs.air_loss_hold_psi_per_s * dt
        if rising > 0.0:
            self.primary_air_psi -= rising * self.specs.air_loss_primary_per_application_psi
            self.secondary_air_psi -= rising * self.specs.air_loss_secondary_per_application_psi
            self.trailer_air_psi -= rising * self.specs.air_loss_trailer_per_application_psi
        if application > 0.0 and not self.parking_brake:
            self.primary_air_psi -= hold * 1.15
            self.secondary_air_psi -= hold * 0.95
            self.trailer_air_psi -= hold * 0.55
        if self.emergency_brake:
            self.trailer_air_psi -= hold * 1.5
        self.primary_air_psi = self._clamp_air_psi(self.primary_air_psi)
        self.secondary_air_psi = self._clamp_air_psi(self.secondary_air_psi)
        self.trailer_air_psi = self._clamp_air_psi(self.trailer_air_psi)
        self._last_service_air_application = application

    def _update_rpm(self, dt: float) -> None:
        s = self.specs
        tr = self.transmission
        if not self.engine_on:
            self.rpm = max(0.0, self.rpm - 1500 * dt)
            return
        ratio = tr.ratio_for(tr.gear) if not tr.in_neutral else 0.0
        coupled = ratio != 0.0 and tr.clutch <= 0.5 and not tr.shifting
        if tr.automatic and tr.shifting and ratio != 0.0:
            wheel_rps = abs(self.velocity_mps) / (2 * math.pi * s.wheel_radius_m)
            road_rpm = wheel_rps * 60.0 * abs(ratio)
            target = max(s.idle_rpm, min(self.rpm, road_rpm))
            self.rpm += (target - self.rpm) * min(1.0, 5.0 * dt)
            return
        if coupled:
            wheel_rps = abs(self.velocity_mps) / (2 * math.pi * s.wheel_radius_m)
            road_rpm = wheel_rps * 60.0 * abs(ratio)
            if road_rpm < s.idle_rpm:
                # Launch regime: in a low gear the clutch slips and the engine
                # holds idle-or-better. In a high gear the engine lugs.
                if tr.gear >= 4 and road_rpm < s.idle_rpm * 0.5:
                    if not tr.automatic:
                        self.stall()
                        return
                    # A real automatic kicks down rather than lugging to a
                    # stall while still rolling. The RPM-threshold downshift
                    # can be outrun by a hard deceleration during the shift
                    # delay, so force the drop here.
                    tr.kickdown()
                self.rpm = max(
                    s.idle_rpm, s.idle_rpm + (s.max_rpm - s.idle_rpm) * self.throttle * 0.3
                )
            else:
                # Road-driven: a downgrade can push past the governor, and
                # that overspeed (not governed running) is what wears the
                # engine. An automatic upshifts to protect itself first.
                self.rpm = min(s.max_rpm * ROAD_OVERSPEED_RPM_MULT, road_rpm)
        else:
            target = s.idle_rpm + (s.max_rpm - s.idle_rpm) * self.throttle
            self.rpm += (target - self.rpm) * min(1.0, 4.0 * dt)

    def stall(self) -> None:
        self.engine_on = False
        self.stalled = True
        self.rpm = 0.0
        self.air_compressor_active = False

    def _update_fuel(self, dt: float) -> None:
        if not self.engine_on:
            return
        # ~0.8 gal/h at idle; load burn calibrated for ~6.5-7 mpg at 60 mph cruise
        power_kw = abs(self.drive_force()) * abs(self.velocity_mps) / 1000.0
        burn = (0.00022 + power_kw * 1.5e-5) * self.specs.fuel_burn_factor
        # A tired engine burns more fuel for the power it still makes.
        burn *= 1.0 + ENGINE_WEAR_FUEL_PENALTY * self.engine_wear_pct / 100.0
        self.fuel_gal = max(0.0, self.fuel_gal - burn * dt * self.fuel_burn_mult)
        if self.fuel_gal <= 0.0:
            self.stop_engine()

    def _update_temps(self, dt: float) -> None:
        s = self.specs
        load = self.throttle * (self.rpm / s.max_rpm) if self.engine_on else 0.0
        target = 60.0 + (28.0 + 45.0 * load if self.engine_on else 0.0)
        self.engine_temp_c += (target - self.engine_temp_c) * 0.03 * dt

        speed = abs(self.velocity_mps)
        # Real energy accounting: the power the shoes actually dissipate
        # (force times speed) soaks into the drums' thermal mass. Heavier
        # loads brake with more force and so heat faster; faded shoes grip
        # less and heat less, which is what keeps the model stable.
        heating = self.service_brake_force() * speed / s.brake_thermal_mass_j_per_c
        cool_frac = BRAKE_COOL_BASE_PER_S + BRAKE_COOL_SPEED_PER_S * math.sqrt(speed)
        cooling = (self.brake_temp_c - AMBIENT_C) * cool_frac
        self.brake_temp_c = max(AMBIENT_C, self.brake_temp_c + (heating - cooling) * dt)

    def _update_wear(self, dt: float) -> None:
        s = self.specs
        # Distance- and energy-coupled wear scales with the trip's time
        # compression (fuel_burn_mult, same trick fuel uses) so a game mile
        # costs the same tread at any time scale.
        sim_dt = dt * self.fuel_burn_mult
        speed = abs(self.velocity_mps)
        load = self.gross_mass_kg / s.mass_kg
        application = 1.0 if self.emergency_brake or self.air_brakes_holding else self.brake

        tire = speed * sim_dt / 1609.344 * TIRE_WEAR_PCT_PER_MILE * load
        if speed > 0.01:
            tire += application * speed * sim_dt * TIRE_WEAR_BRAKING_PCT
        if self.tire_type == TIRE_WINTER:
            tire *= WINTER_TREAD_WEAR_MULT
        self.tire_wear_pct = min(100.0, self.tire_wear_pct + tire * self.tire_wear_buff_mult)

        # Chains wear by the mile, brutally faster on bare pavement or past
        # chain speed. A set ground to nothing lets a cross chain go: the
        # links flail into the fender and the whole set is scrap.
        if self.chains_on and speed > 0.01:
            rate = CHAIN_WEAR_PCT_PER_MILE
            if self.surface not in ("snow", "ice"):
                rate *= CHAIN_WEAR_BARE_MULT
            if self.speed_mph > CHAIN_SAFE_MPH:
                rate *= CHAIN_WEAR_OVERSPEED_MULT
            self.chain_wear_pct = min(
                100.0, self.chain_wear_pct + rate * speed * sim_dt / 1609.344
            )
            if self.chain_wear_pct >= 100.0:
                self.chains_on = False
                self.chains_just_snapped = True
                self.damage_pct = min(100.0, self.damage_pct + CHAIN_SNAP_DAMAGE_PCT)

        # The service brakes wear with the energy they actually dissipate;
        # the jake dumps its share out the exhaust and costs the shoes nothing.
        service_force = self.service_brake_force()
        if service_force > 0.0 and speed > 0.01:
            brake = service_force * speed * sim_dt / 1.0e6 * BRAKE_WEAR_PCT_PER_MJ
            if self.brake_temp_c >= self.brake_fade_onset_c:
                brake *= BRAKE_WEAR_HOT_MULT
            self.brake_wear_pct = min(100.0, self.brake_wear_pct + brake)

        if self.engine_on:
            duty = self.throttle * (self.rpm / s.max_rpm)
            rate = ENGINE_WEAR_PCT_PER_H_IDLE + (
                ENGINE_WEAR_PCT_PER_H_FULL_LOAD - ENGINE_WEAR_PCT_PER_H_IDLE
            ) * min(1.0, duty)
            # Care buffs slow honest duty-cycle wear only; the abuse terms
            # below stay full price -- fresh oil does not excuse over-revving.
            engine = rate / 3600.0 * sim_dt * self.engine_wear_buff_mult
            # Abuse penalties charge per real second of the behavior, like
            # the damage accrual the over-rev term replaces.
            if self.rpm > s.max_rpm * OVER_REV_RPM_MULT:
                engine += ENGINE_WEAR_OVER_REV_PCT_PER_S * dt
            lugging = (
                not self.transmission.in_neutral
                and self.throttle > LUG_THROTTLE
                and speed > 0.5
                and self.rpm < s.peak_torque_rpm * LUG_RPM_FRACTION
            )
            if lugging:
                engine += ENGINE_WEAR_LUG_PCT_PER_S * dt
            self.engine_wear_pct = min(100.0, self.engine_wear_pct + engine)

    # -- convenience ---------------------------------------------------------------

    @property
    def speed_mph(self) -> float:
        return abs(self.velocity_mps) * 2.23694

    @property
    def speed_kmh(self) -> float:
        return abs(self.velocity_mps) * 3.6

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
