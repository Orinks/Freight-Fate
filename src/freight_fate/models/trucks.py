"""Truck catalog and garage upgrades.

Upgrades and the chosen truck live on the player profile; they come together
in :func:`build_truck_specs`, which produces the :class:`TruckSpecs` the
driving simulation runs on.
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
