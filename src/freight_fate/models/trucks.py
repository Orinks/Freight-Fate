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


# Equipment traits dispatch matches a load against. A real yard does not hand
# out tractors at random: a run that cannot be finished inside one driving
# shift needs a bunk, a heavy load needs a tractor spec'd to pull it, and a
# day's worth of city stops is day-cab work. These are the axes that decision
# turns on (see ``dispatch_policy.assignment_for_job``).
CAB_DAY = "day"  # no bunk: local and regional turns only
CAB_SLEEPER = "sleeper"  # a bed, so the driver can rest on the road
SPEC_LIGHT = "light"  # tare-light, leaves payload headroom, modest pull
SPEC_STANDARD = "standard"  # the everyday fleet tractor
SPEC_HEAVY = "heavy"  # heavy-spec driveline for weight and mountain work


@dataclass(frozen=True)
class TruckModel:
    key: str
    label: str
    price: float
    description: str
    specs: TruckSpecs
    cab: str = CAB_SLEEPER
    spec: str = SPEC_STANDARD


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
        spec=SPEC_HEAVY,
    ),
    # -- Carrier fleet and used-market tractors --------------------------------
    # Company drivers meet these as dispatch-assigned equipment (see
    # carrier_fleet); after the owner-operator buy-in the same models sell
    # here as used fleet units or retail trucks.
    #
    # Every tier carries day cabs and sleepers, and light, standard, and heavy
    # driveline specs, so dispatch has something real to choose between when it
    # matches a tractor to a load. Tanks never shrink from one tier to the next
    # (test_carrier_fleet pins it), which is why the day cabs live in the two
    # lower tiers -- the only place a small tank is honest.
    #
    # -- Yard standard: the trainer-spec iron a new hire meets ------------------
    "trainer_day_cab": TruckModel(
        "trainer_day_cab",
        "trainer day cab",
        26_000.0,
        "The tractor every new hire learns on: a plain day cab with soft "
        "power, light steering, and nowhere to sleep. Forgiving, slow, and "
        "impossible to be precious about.",
        TruckSpecs(
            max_torque_nm=2_050.0,
            fuel_tank_gal=150.0,
            drag_coefficient=0.70,
            fuel_burn_factor=0.94,
            mass_kg=34_800.0,
        ),
        cab=CAB_DAY,
        spec=SPEC_LIGHT,
    ),
    "yard_mule": TruckModel(
        "yard_mule",
        "yard mule",
        24_000.0,
        "A stubby day cab that spends most of its life shoving trailers "
        "around the lot. Grunt down low, no manners above fifty, and it "
        "drinks like it is being punished.",
        TruckSpecs(
            max_torque_nm=2_450.0,
            fuel_tank_gal=150.0,
            drag_coefficient=0.78,
            fuel_burn_factor=1.18,
            mass_kg=35_900.0,
        ),
        cab=CAB_DAY,
        spec=SPEC_HEAVY,
    ),
    "hand_me_down_sleeper": TruckModel(
        "hand_me_down_sleeper",
        "hand-me-down sleeper",
        31_000.0,
        "A tired flat-roof sleeper handed down the seniority list until it "
        "reached you. The bunk is thin and the paint is faded, but it will "
        "get you there and back.",
        TruckSpecs(
            max_torque_nm=2_250.0,
            fuel_tank_gal=150.0,
            drag_coefficient=0.69,
            fuel_burn_factor=1.06,
            mass_kg=35_600.0,
        ),
    ),
    "plain_jane_conventional": TruckModel(
        "plain_jane_conventional",
        "plain jane conventional",
        34_000.0,
        "No chrome, no fairings, no nonsense: a base-spec conventional "
        "sleeper bought by the dozen. Nothing about it is special and "
        "nothing about it breaks.",
        TruckSpecs(
            max_torque_nm=2_350.0,
            fuel_tank_gal=155.0,
            drag_coefficient=0.67,
            mass_kg=35_900.0,
        ),
    ),
    # -- Regional fleet: proven drivers, day work and overnight turns ----------
    "city_shuttle": TruckModel(
        "city_shuttle",
        "city shuttle",
        36_000.0,
        "A short, light day cab built for stop-and-go: it turns inside its "
        "own trailer, sips diesel in traffic, and leaves every pound it "
        "saves for the freight.",
        TruckSpecs(
            max_torque_nm=2_200.0,
            fuel_tank_gal=150.0,
            drag_coefficient=0.68,
            fuel_burn_factor=0.90,
            mass_kg=34_600.0,
        ),
        cab=CAB_DAY,
        spec=SPEC_LIGHT,
    ),
    "dock_hopper": TruckModel(
        "dock_hopper",
        "dock hopper",
        39_000.0,
        "The everyday city day cab: enough pull for a full trailer, tight "
        "mirrors, and air seats that have seen a thousand docks. Home "
        "every night by design.",
        TruckSpecs(
            max_torque_nm=2_400.0,
            fuel_tank_gal=155.0,
            drag_coefficient=0.66,
            mass_kg=35_600.0,
        ),
        cab=CAB_DAY,
    ),
    "short_haul_stubnose": TruckModel(
        "short_haul_stubnose",
        "short-haul stubnose",
        44_000.0,
        "A heavy-spec day cab for the loads nobody wants on a light "
        "tractor: gravel, steel, and drum mixers. All driveline, no "
        "comfort, and it will pull a building off its footings.",
        TruckSpecs(
            max_torque_nm=2_850.0,
            fuel_tank_gal=155.0,
            drag_coefficient=0.74,
            fuel_burn_factor=1.14,
            mass_kg=37_400.0,
            brake_fade_temp_c=430.0,
        ),
        cab=CAB_DAY,
        spec=SPEC_HEAVY,
    ),
    "midroof_runner": TruckModel(
        "midroof_runner",
        "mid-roof runner",
        54_000.0,
        "A light mid-roof sleeper for drivers who live on two-day lanes: "
        "quick, economical, and just tall enough to stand up and change a "
        "shirt.",
        TruckSpecs(
            max_torque_nm=2_400.0,
            fuel_tank_gal=160.0,
            drag_coefficient=0.61,
            fuel_burn_factor=0.92,
            mass_kg=35_200.0,
        ),
        spec=SPEC_LIGHT,
    ),
    "farm_road_workhorse": TruckModel(
        "farm_road_workhorse",
        "farm road workhorse",
        57_000.0,
        "Built for grain country: heavy driveline, tall gearing, and a "
        "chassis that shrugs off washboard county roads. It hauls hoppers "
        "in spring and complains about it all summer.",
        TruckSpecs(
            max_torque_nm=2_800.0,
            fuel_tank_gal=170.0,
            drag_coefficient=0.71,
            fuel_burn_factor=1.10,
            mass_kg=37_200.0,
        ),
        spec=SPEC_HEAVY,
    ),
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
        cab=CAB_DAY,
        spec=SPEC_LIGHT,
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
        spec=SPEC_HEAVY,
    ),
    # -- Long-haul fleet: sleepers with real interstate range ------------------
    "long_run_midroof": TruckModel(
        "long_run_midroof",
        "long run mid-roof",
        74_000.0,
        "A no-drama mid-roof built for the middle of the country: honest "
        "range, honest power, and a bunk you can actually sleep a full ten "
        "hours in.",
        TruckSpecs(
            max_torque_nm=2_550.0,
            fuel_tank_gal=185.0,
            drag_coefficient=0.62,
            fuel_burn_factor=0.96,
            mass_kg=36_100.0,
        ),
    ),
    "dry_lightning": TruckModel(
        "dry_lightning",
        "dry lightning",
        86_000.0,
        "A light-spec aero sleeper that runs the desert lanes: it gives up "
        "torque for tare weight and mileage, and it will out-run anything "
        "in the yard on flat ground.",
        TruckSpecs(
            max_torque_nm=2_450.0,
            fuel_tank_gal=180.0,
            drag_coefficient=0.56,
            fuel_burn_factor=0.87,
            mass_kg=34_900.0,
        ),
        spec=SPEC_LIGHT,
    ),
    "interstate_condo": TruckModel(
        "interstate_condo",
        "interstate condo",
        99_000.0,
        "A raised-roof sleeper with room to stand, cook, and live: the "
        "truck drivers move into rather than drive. Heavy on comfort, "
        "steady everywhere else.",
        TruckSpecs(
            max_torque_nm=2_650.0,
            fuel_tank_gal=205.0,
            drag_coefficient=0.63,
            fuel_burn_factor=1.02,
            mass_kg=36_700.0,
        ),
    ),
    "steel_hauler": TruckModel(
        "steel_hauler",
        "steel hauler",
        97_000.0,
        "A heavy-spec flatbed tractor with a headache rack and a driveline "
        "sized for coil and plate. Rides like a brick empty and like it "
        "was born to it loaded.",
        TruckSpecs(
            max_torque_nm=2_900.0,
            fuel_tank_gal=195.0,
            drag_coefficient=0.70,
            fuel_burn_factor=1.09,
            mass_kg=37_600.0,
            brake_fade_temp_c=430.0,
        ),
        spec=SPEC_HEAVY,
    ),
    "mountain_spec_hauler": TruckModel(
        "mountain_spec_hauler",
        "mountain spec hauler",
        104_000.0,
        "Spec'd for the western grades: deep gearing, a big retarder, and "
        "brakes that stay cool where other trucks start smelling hot. "
        "Slow up, unbothered down.",
        TruckSpecs(
            max_torque_nm=2_950.0,
            fuel_tank_gal=200.0,
            drag_coefficient=0.67,
            fuel_burn_factor=1.07,
            mass_kg=37_400.0,
            brake_fade_temp_c=470.0,
            engine_brake_torque_nm=2_050.0,
        ),
        spec=SPEC_HEAVY,
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
        spec=SPEC_HEAVY,
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
        spec=SPEC_LIGHT,
    ),
    # -- Premium fleet: what seniority gets you -------------------------------
    "cabover_revival": TruckModel(
        "cabover_revival",
        "cabover revival",
        118_000.0,
        "A modern cabover: short, light, and startlingly quick, with the "
        "whole road laid out under the windscreen. Every pound it saves "
        "goes to the load, and it turns where nothing else will.",
        TruckSpecs(
            max_torque_nm=2_600.0,
            fuel_tank_gal=200.0,
            drag_coefficient=0.59,
            fuel_burn_factor=0.91,
            mass_kg=34_700.0,
        ),
        spec=SPEC_LIGHT,
    ),
    "chrome_shop_special": TruckModel(
        "chrome_shop_special",
        "chrome shop special",
        124_000.0,
        "Every light the catalog sells and a stack of polished pipe: a "
        "senior driver's reward truck. It is genuinely good, and it knows "
        "exactly how good it looks.",
        TruckSpecs(
            max_torque_nm=2_800.0,
            fuel_tank_gal=210.0,
            drag_coefficient=0.68,
            fuel_burn_factor=1.06,
            mass_kg=36_900.0,
        ),
    ),
    "deep_sleeper_custom": TruckModel(
        "deep_sleeper_custom",
        "deep sleeper custom",
        132_000.0,
        "A stretched custom sleeper with a proper bed and a wardrobe: for "
        "drivers who are out for a month at a time and have stopped "
        "pretending otherwise.",
        TruckSpecs(
            max_torque_nm=2_850.0,
            fuel_tank_gal=215.0,
            drag_coefficient=0.64,
            fuel_burn_factor=1.00,
            mass_kg=37_100.0,
        ),
    ),
    "wide_glide_tourer": TruckModel(
        "wide_glide_tourer",
        "wide glide tourer",
        136_000.0,
        "A wide-cab highway tourer built around the seat and the sound "
        "system: quiet at speed, easy over a long day, and no trouble at "
        "all in a crosswind.",
        TruckSpecs(
            max_torque_nm=2_800.0,
            fuel_tank_gal=220.0,
            drag_coefficient=0.58,
            fuel_burn_factor=0.94,
            mass_kg=36_500.0,
        ),
    ),
    "granite_grade_king": TruckModel(
        "granite_grade_king",
        "granite grade king",
        146_000.0,
        "A heavy-spec premium tractor for the worst grades on the map: "
        "enormous torque, oversized brakes, and a retarder that holds a "
        "loaded trailer down a six percent without a word.",
        TruckSpecs(
            max_torque_nm=3_050.0,
            fuel_tank_gal=225.0,
            drag_coefficient=0.65,
            fuel_burn_factor=1.08,
            mass_kg=37_700.0,
            brake_fade_temp_c=480.0,
            engine_brake_torque_nm=2_150.0,
        ),
        spec=SPEC_HEAVY,
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
        spec=SPEC_HEAVY,
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
        spec=SPEC_LIGHT,
    ),
    # -- First pick of the yard: the carrier's best iron -----------------------
    "midnight_flyer": TruckModel(
        "midnight_flyer",
        "midnight flyer",
        176_000.0,
        "A light-spec flagship for drivers who run nights: the quietest "
        "cab on the property, a huge tank, and mileage that makes a "
        "dispatcher smile.",
        TruckSpecs(
            max_torque_nm=2_800.0,
            fuel_tank_gal=230.0,
            drag_coefficient=0.53,
            fuel_burn_factor=0.86,
            mass_kg=35_400.0,
            brake_fade_temp_c=450.0,
        ),
        spec=SPEC_LIGHT,
    ),
    "owner_spec_showpiece": TruckModel(
        "owner_spec_showpiece",
        "owner spec showpiece",
        188_000.0,
        "Ordered the way an owner would order it, then handed to the "
        "driver the carrier least wants to lose. Everything on it is the "
        "good version.",
        TruckSpecs(
            max_torque_nm=2_900.0,
            fuel_tank_gal=235.0,
            drag_coefficient=0.56,
            fuel_burn_factor=0.92,
            mass_kg=36_500.0,
            brake_fade_temp_c=455.0,
        ),
    ),
    "centurion_longhood": TruckModel(
        "centurion_longhood",
        "centurion longhood",
        204_000.0,
        "A flagship long-hood with a hood you could land a plane on: "
        "monstrous torque, brakes to match, and an unapologetic thirst. "
        "The truck people photograph at the fuel island.",
        TruckSpecs(
            max_torque_nm=3_150.0,
            fuel_tank_gal=245.0,
            drag_coefficient=0.71,
            fuel_burn_factor=1.10,
            mass_kg=37_800.0,
            brake_fade_temp_c=470.0,
            engine_brake_torque_nm=2_100.0,
        ),
        spec=SPEC_HEAVY,
    ),
    "continental_expedition": TruckModel(
        "continental_expedition",
        "continental expedition",
        216_000.0,
        "Built to cross the continent without a scheduled stop: two "
        "hundred fifty gallons, mountain-grade brakes, and enough torque "
        "to make a loaded pull feel like an errand.",
        TruckSpecs(
            max_torque_nm=3_100.0,
            fuel_tank_gal=250.0,
            drag_coefficient=0.60,
            fuel_burn_factor=1.00,
            mass_kg=37_500.0,
            brake_fade_temp_c=480.0,
            engine_brake_torque_nm=2_200.0,
        ),
        spec=SPEC_HEAVY,
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
        spec=SPEC_HEAVY,
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
        spec=SPEC_LIGHT,
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
