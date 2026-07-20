"""Truck catalog and owner-operator garage upgrades.

Owner-operator upgrades and chosen tractors live on the player profile. Company
drivers use carrier-assigned equipment and do not apply owned upgrades.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..sim.vehicle import TruckSpecs

# Upgrade effect constants.
ENGINE_TUNE_TORQUE_PER_TIER = 0.10  # +10% torque per tier
AERO_DRAG_MULT = 0.88  # -12% drag
TANK_EXTRA_GAL = 50.0
BRAKE_FADE_BONUS_C = 150.0  # fade onset pushed this much hotter


@dataclass(frozen=True)
class TruckModel:
    key: str
    label: str
    price: float
    description: str
    specs: TruckSpecs


@dataclass
class TruckCondition:
    """One owned truck's persistent condition, keyed by catalog key on the profile."""

    fuel_gal: float = 150.0
    damage_pct: float = 0.0
    tire_wear_pct: float = 0.0
    grime_pct: float = 0.0

    @classmethod
    def fresh(cls, truck_key: str, upgrades: dict[str, int] | None = None) -> TruckCondition:
        """A just-purchased truck: full tank for this model, everything else zero."""
        return cls(fuel_gal=build_truck_specs(truck_key, upgrades or {}).fuel_tank_gal)

    @classmethod
    def from_dict(cls, data: object) -> TruckCondition:
        if not isinstance(data, dict):
            return cls()
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})


TRUCK_CATALOG: dict[str, TruckModel] = {
    "rig": TruckModel(
        "rig",
        "standard rig",
        0.0,
        "The dependable tractor you started with: better fuel economy and "
        "a calmer highway feel than the heavy hauler.",
        TruckSpecs(),
    ),
    "heavy_hauler": TruckModel(
        "heavy_hauler",
        "heavy hauler",
        52_000.0,
        "A brute for heavy loads and long stretches: a quarter more torque "
        "and a two hundred gallon tank, but blunt aerodynamics and a "
        "thirstier engine.",
        TruckSpecs(
            max_torque_nm=3_000.0,
            fuel_tank_gal=200.0,
            drag_coefficient=0.75,
            fuel_burn_factor=1.2,
            mass_kg=37_500.0,
        ),
    ),
    # -- Carrier fleet and used-market tractors --------------------------------
    # Company drivers meet these as dispatch-assigned equipment (see
    # carrier_fleet); after the owner-operator buy-in the same models sell
    # here as used fleet units or retail trucks.
    "sunset_day_cab": TruckModel(
        "sunset_day_cab",
        "sunset day cab",
        38_000.0,
        "A tidy regional day cab: light, easy on diesel, and happy on "
        "short lanes. No bunk, no long-haul pretensions.",
        TruckSpecs(
            max_torque_nm=2_300.0,
            fuel_tank_gal=150.0,
            drag_coefficient=0.62,
            fuel_burn_factor=0.95,
            mass_kg=35_500.0,
        ),
    ),
    "ridgeline_sleeper": TruckModel(
        "ridgeline_sleeper",
        "ridgeline sleeper",
        58_000.0,
        "A mid-roof regional sleeper with a little more pull and a "
        "bigger tank: the workhorse most fleets hand a proven regional "
        "driver.",
        TruckSpecs(
            max_torque_nm=2_500.0,
            fuel_tank_gal=165.0,
            drag_coefficient=0.64,
            mass_kg=36_200.0,
        ),
    ),
    "old_longnose": TruckModel(
        "old_longnose",
        "old longnose",
        49_000.0,
        "A classic long-hood conventional: strong pull and a proud "
        "profile, but it fights the wind and drinks for the privilege.",
        TruckSpecs(
            max_torque_nm=2_700.0,
            fuel_tank_gal=165.0,
            drag_coefficient=0.72,
            fuel_burn_factor=1.12,
            mass_kg=36_800.0,
        ),
    ),
    "highline_sleeper": TruckModel(
        "highline_sleeper",
        "highline sleeper",
        82_000.0,
        "A raised-roof long-haul sleeper with a two hundred gallon tank "
        "and honest aerodynamics: built to live on the interstate for "
        "days at a time.",
        TruckSpecs(
            max_torque_nm=2_600.0,
            fuel_tank_gal=200.0,
            drag_coefficient=0.60,
            fuel_burn_factor=0.97,
            mass_kg=36_400.0,
        ),
    ),
    "big_bunk_conventional": TruckModel(
        "big_bunk_conventional",
        "big bunk conventional",
        89_000.0,
        "A big-bunk conventional with serious torque for mountain "
        "corridors and heavy long-haul freight. Comfortable, capable, "
        "and a little thirsty.",
        TruckSpecs(
            max_torque_nm=2_800.0,
            fuel_tank_gal=210.0,
            drag_coefficient=0.66,
            fuel_burn_factor=1.05,
            mass_kg=37_000.0,
        ),
    ),
    "aero_cruiser": TruckModel(
        "aero_cruiser",
        "aero cruiser",
        95_000.0,
        "A slippery fleet aero tractor tuned for fuel economy: modest "
        "torque, long legs, and the best mileage of the long-haul pool.",
        TruckSpecs(
            max_torque_nm=2_500.0,
            fuel_tank_gal=190.0,
            drag_coefficient=0.55,
            fuel_burn_factor=0.90,
            mass_kg=35_800.0,
        ),
    ),
    "summit_flagship": TruckModel(
        "summit_flagship",
        "summit flagship",
        128_000.0,
        "A premium flagship sleeper: big power, a two hundred twenty "
        "gallon tank, and clean aerodynamics. The truck senior drivers "
        "ask the shop about.",
        TruckSpecs(
            max_torque_nm=2_900.0,
            fuel_tank_gal=220.0,
            drag_coefficient=0.57,
            fuel_burn_factor=0.95,
            mass_kg=36_600.0,
        ),
    ),
    "silver_aero": TruckModel(
        "silver_aero",
        "silver aero",
        142_000.0,
        "A polished premium aero tractor: the slipperiest shape in the "
        "catalog with plenty of pull, sipping diesel at cruise like a "
        "truck half its size.",
        TruckSpecs(
            max_torque_nm=2_750.0,
            fuel_tank_gal=220.0,
            drag_coefficient=0.52,
            fuel_burn_factor=0.88,
            mass_kg=36_000.0,
        ),
    ),
    "presidential_sleeper": TruckModel(
        "presidential_sleeper",
        "presidential sleeper",
        185_000.0,
        "The top of the yard: huge torque, a two hundred forty gallon "
        "tank, and brakes that shrug off long mountain descents. First "
        "pick goes to the carrier's best.",
        TruckSpecs(
            max_torque_nm=3_100.0,
            fuel_tank_gal=240.0,
            drag_coefficient=0.58,
            fuel_burn_factor=0.98,
            mass_kg=37_200.0,
            brake_fade_temp_c=450.0,
        ),
    ),
    "night_flag_aero": TruckModel(
        "night_flag_aero",
        "night flag aero",
        198_000.0,
        "A flagship aero sleeper for drivers who live out west: enormous "
        "range, upgraded brakes, and the lowest drag on the road. It "
        "turns fuel islands into scenery.",
        TruckSpecs(
            max_torque_nm=2_950.0,
            fuel_tank_gal=240.0,
            drag_coefficient=0.50,
            fuel_burn_factor=0.85,
            mass_kg=36_200.0,
            brake_fade_temp_c=450.0,
        ),
    ),
}


@dataclass(frozen=True)
class Upgrade:
    key: str
    label: str
    description: str
    prices: tuple[float, ...]  # one entry per tier

    @property
    def max_tier(self) -> int:
        return len(self.prices)


UPGRADE_CATALOG: dict[str, Upgrade] = {
    "engine_tune": Upgrade(
        "engine_tune",
        "Engine tune",
        "Gives the truck more pulling power. It helps with heavy freight, "
        "hill climbs, mountain grades, and starting from a stop with a load. "
        "Buy it when heavy loads and steep routes feel sluggish.",
        (12_000.0, 26_000.0),
    ),
    "aero_kit": Upgrade(
        "aero_kit",
        "Aerodynamic kit",
        "Makes the truck burn less fuel at highway speed. It does not add "
        "more fuel capacity; it makes the same tank last longer. Buy it to "
        "save diesel money over long highway miles.",
        (9_000.0,),
    ),
    "long_range_tank": Upgrade(
        "long_range_tank",
        "Long-range tank",
        "Adds fifty gallons of fuel capacity. It does not make the truck more "
        "efficient; it lets you carry more fuel. Buy it for more distance "
        "between fuel stops and more route flexibility.",
        (7_500.0,),
    ),
    "reinforced_brakes": Upgrade(
        "reinforced_brakes",
        "Reinforced brakes",
        "Keeps braking power strong for longer when the brakes get hot. It "
        "helps on mountain descents, with heavy freight, and during emergency "
        "stops. Buy it when downhill control matters more than speed or range.",
        (6_500.0,),
    ),
}


def build_truck_specs(truck_key: str, upgrades: dict[str, int]) -> TruckSpecs:
    """Specs for the given truck model with the profile's upgrades applied."""
    model = TRUCK_CATALOG.get(truck_key, TRUCK_CATALOG["rig"])
    specs = model.specs
    changes: dict[str, float] = {}
    tier = upgrades.get("engine_tune", 0)
    if tier:
        changes["max_torque_nm"] = specs.max_torque_nm * (
            1.0 + ENGINE_TUNE_TORQUE_PER_TIER * min(tier, 2)
        )
    if upgrades.get("aero_kit"):
        changes["drag_coefficient"] = specs.drag_coefficient * AERO_DRAG_MULT
    if upgrades.get("long_range_tank"):
        changes["fuel_tank_gal"] = specs.fuel_tank_gal + TANK_EXTRA_GAL
    if upgrades.get("reinforced_brakes"):
        changes["brake_fade_temp_c"] = specs.brake_fade_temp_c + BRAKE_FADE_BONUS_C
    return replace(specs, **changes) if changes else specs
