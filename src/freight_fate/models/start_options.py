"""Grounded career-start choices and starter carrier benefits."""

from __future__ import annotations

from dataclasses import dataclass, field

from .career_ladder import STARTER_CARRIER_NAME
from .trailers import DEFAULT_TRAILER_PROGRAMS

START_MODE_COMPANY = "company_driver"
START_MODE_OWNER_OPERATOR = "owner_operator"

DEFAULT_START_KEY = "northstar"
OWNER_OPERATOR_START_KEY = "roadstead_owner_operator"


@dataclass(frozen=True)
class CompanyPayPlan:
    """Carrier wage knobs for company-driver settlements."""

    pay_share: float
    min_per_mile: float
    stop_pay: float
    on_time_bonus_share: float

    def summary(self) -> str:
        return (
            f"{self.pay_share * 100:.0f} percent pay share, "
            f"{self.min_per_mile:.2f} dollars per mile floor, "
            f"{self.stop_pay:.0f} dollar stop pay, "
            f"{self.on_time_bonus_share * 100:.0f} percent on-time bonus"
        )


@dataclass(frozen=True)
class DispatchProfile:
    """Modest carrier dispatch tendencies for generated job boards."""

    short_haul_bias: float = 0.0
    regional_bias: float = 0.0
    long_haul_bias: float = 0.0
    deadline_slack: float = 1.0

    def summary(self) -> str:
        parts: list[str] = []
        if self.short_haul_bias:
            parts.append("more short training loads")
        if self.regional_bias:
            parts.append("more same-region lanes")
        if self.long_haul_bias:
            parts.append("more longer lanes")
        if self.deadline_slack > 1.0:
            parts.append("more appointment slack")
        return ", ".join(parts) if parts else "balanced dispatch"


@dataclass(frozen=True)
class CareerStartOption:
    key: str
    label: str
    carrier_name: str
    mode: str
    menu_summary: str
    help_text: str
    default_city: str = "Chicago"
    starting_money: float = 5_000.0
    starting_truck: str = "rig"
    owned_trucks: tuple[str, ...] = ()
    # ``None`` means a full tank for whatever truck this start hands over, read
    # from that model's own specs. A literal number here would drift the day a
    # tank capacity changes and quietly start the career short of fuel.
    truck_fuel_gal: float | None = None
    truck_damage_pct: float = 0.0
    starting_level_xp: float = 0.0
    starting_deliveries: int = 0
    starting_on_time_deliveries: int = 0
    starting_total_miles: float = 0.0
    starting_total_earnings: float = 0.0
    starting_reputation: float = 50.0
    company_pay: CompanyPayPlan | None = None
    cargo_weight_bonus: dict[str, float] = field(default_factory=dict)
    dispatch: DispatchProfile = field(default_factory=DispatchProfile)

    @property
    def is_owner_operator(self) -> bool:
        return self.mode == START_MODE_OWNER_OPERATOR

    @property
    def is_company_driver(self) -> bool:
        return self.mode == START_MODE_COMPANY


NORTHSTAR_PAY = CompanyPayPlan(
    pay_share=0.36,
    min_per_mile=0.82,
    stop_pay=175.0,
    on_time_bonus_share=0.04,
)


START_OPTIONS: dict[str, CareerStartOption] = {
    DEFAULT_START_KEY: CareerStartOption(
        key=DEFAULT_START_KEY,
        label=f"{STARTER_CARRIER_NAME}: balanced company driver",
        carrier_name=STARTER_CARRIER_NAME,
        mode=START_MODE_COMPANY,
        menu_summary=(
            "Balanced company-driver start with steady wages, normal training "
            "support, and assigned carrier equipment."
        ),
        help_text=(
            "A balanced company-driver path. The carrier assigns and maintains "
            "the tractor, pays fuel and routine repairs, and offers steady wage "
            "math without a sharp specialty."
        ),
        default_city="Chicago",
        company_pay=NORTHSTAR_PAY,
    ),
    "great_lakes_training": CareerStartOption(
        key="great_lakes_training",
        label="Great Lakes Training Transport: trainer-friendly company driver",
        carrier_name="Great Lakes Training Transport",
        mode=START_MODE_COMPANY,
        menu_summary=(
            "Trainer-friendly company start with stronger stop pay, more short "
            "rookie loads, and a little more appointment slack."
        ),
        help_text=(
            "A practical training-fleet start. Stop pay is better on short "
            "loads, and dispatch leans toward shorter training work with a "
            "little more deadline room. Equipment and routine costs stay "
            "carrier-paid."
        ),
        default_city="Milwaukee",
        company_pay=CompanyPayPlan(
            pay_share=0.33,
            min_per_mile=0.74,
            stop_pay=225.0,
            on_time_bonus_share=0.02,
        ),
        dispatch=DispatchProfile(short_haul_bias=0.8, deadline_slack=1.08),
    ),
    "prairie_link": CareerStartOption(
        key="prairie_link",
        label="Prairie Link Regional: mile-focused company driver",
        carrier_name="Prairie Link Regional",
        mode=START_MODE_COMPANY,
        menu_summary=(
            "Regional carrier with a better per-mile floor, lower stop pay, "
            "and more same-region grain and bulk lanes."
        ),
        help_text=(
            "A mile-focused company start. The per-mile wage floor is higher, "
            "but stop pay is lower, so it favors steady regional mileage over "
            "very short hops. Dispatch leans toward same-region grain and "
            "bulk work. The carrier still assigns and maintains the tractor."
        ),
        default_city="Kansas City",
        company_pay=CompanyPayPlan(
            pay_share=0.34,
            min_per_mile=0.95,
            stop_pay=130.0,
            on_time_bonus_share=0.03,
        ),
        cargo_weight_bonus={"grain": 0.25, "farm_inputs": 0.2, "bulk": 0.15},
        dispatch=DispatchProfile(regional_bias=0.7, long_haul_bias=0.1),
    ),
    "summit_value": CareerStartOption(
        key="summit_value",
        label="Summit Value Logistics: appointment-bonus company driver",
        carrier_name="Summit Value Logistics",
        mode=START_MODE_COMPANY,
        menu_summary=(
            "Higher percentage and on-time bonus for careful freight, with a "
            "smaller wage floor and more long-haul/high-value lanes."
        ),
        help_text=(
            "A performance-sensitive company start. Good on-time runs pay "
            "better, but the guaranteed floor is smaller. Dispatch leans "
            "toward longer and higher-value lanes. The carrier still supplies "
            "equipment, authority, insurance, fuel, and repairs."
        ),
        default_city="Denver",
        company_pay=CompanyPayPlan(
            pay_share=0.38,
            min_per_mile=0.78,
            stop_pay=150.0,
            on_time_bonus_share=0.06,
        ),
        cargo_weight_bonus={"electronics": 0.2, "automotive": 0.15, "parcel": 0.15},
        dispatch=DispatchProfile(long_haul_bias=0.35),
    ),
    OWNER_OPERATOR_START_KEY: CareerStartOption(
        key=OWNER_OPERATOR_START_KEY,
        label="Owner-operator start: higher risk, higher responsibility",
        carrier_name="Northstar Freight Lines",
        mode=START_MODE_OWNER_OPERATOR,
        menu_summary=(
            "Leased-on owner-operator from day one: a brand-new truck of your "
            "own, and every operating cost is yours."
        ),
        help_text=(
            "The hardest way to begin. You start leased on with a brand-new "
            "truck you have just bought -- full tank, no damage, nothing worn "
            "-- and limited working capital, and the operating costs -- fuel, "
            "repairs, reserves, and settlement fees -- come out of your own "
            "cash instead of the carrier's. You still start at level one and "
            "climb the same career as everyone else: this changes who pays, "
            "not how far along you are."
        ),
        default_city="Chicago",
        # The career itself starts at zero. This option is about ECONOMICS --
        # your truck, your costs -- and never about skipping the ladder. It
        # used to grant level 18 with 35 deliveries, 42,000 miles and 70,000
        # dollars of lifetime earnings, which handed the player most of a
        # thirty-level arc and published a career history that never happened
        # on their public profile.
        #
        # The truck itself is a design change of its own (owner, 2026-08-11):
        # it used to open with 110 gallons and 4 percent damage, which read as
        # a hand-me-down. Buying in means buying NEW, so the condition record
        # is left pristine and the tank is filled from the model's own specs.
        # The difficulty stays where it belongs -- in the costs and the thin
        # cushion -- rather than in a truck that starts already worn.
        starting_money=18_000.0,
        owned_trucks=("rig",),
        dispatch=DispatchProfile(long_haul_bias=0.25),
    ),
}


def start_option(key: str | None) -> CareerStartOption:
    return START_OPTIONS.get(key or DEFAULT_START_KEY, START_OPTIONS[DEFAULT_START_KEY])


def company_start_options() -> tuple[CareerStartOption, ...]:
    return tuple(option for option in START_OPTIONS.values() if option.is_company_driver)


def all_start_options() -> tuple[CareerStartOption, ...]:
    return tuple(START_OPTIONS.values())


def pay_plan_for_key(key: str | None) -> CompanyPayPlan:
    option = start_option(key)
    return option.company_pay or NORTHSTAR_PAY


def _provision_start_trucks(profile, option: CareerStartOption) -> None:
    """Give every truck this start hands over a brand-new condition record.

    A condition record carries nine dimensions -- fuel, damage, tire, brake and
    engine wear, grime, tire compound, whether chains are aboard, and chain
    wear -- and a start option only ever named two of them. Rebuilding the
    record instead of poking fields means a new dimension arrives pristine by
    default rather than silently starting a fresh career already worn. Any
    condition a start option deliberately wants worn is applied afterwards.
    """
    profile.truck_conditions = {}
    for key in {profile.active_truck_key(), *profile.owned_trucks}:
        profile.provision_truck_condition(key)
    if option.truck_fuel_gal is not None:
        # Never above the real tank: the option's number is a starting level,
        # not a license to overfill a truck whose capacity has since changed.
        profile.truck_fuel_gal = min(option.truck_fuel_gal, profile.truck_specs().fuel_tank_gal)
    if option.truck_damage_pct:
        profile.truck_damage_pct = option.truck_damage_pct


def apply_start_option(profile, option: CareerStartOption) -> None:
    """Apply a start option to a freshly created or reset profile."""

    profile.carrier_key = option.key
    profile.start_mode = option.mode
    profile.carrier_name = option.carrier_name
    profile.money = option.starting_money
    profile.business_status = (
        "leased_owner_operator" if option.is_owner_operator else "company_driver"
    )
    profile.truck = option.starting_truck
    profile.owned_trucks = list(option.owned_trucks)
    profile.owned_trailers = []
    profile.trailer_programs = list(DEFAULT_TRAILER_PROGRAMS) if option.is_owner_operator else []
    profile.upgrades = {}
    _provision_start_trucks(profile, option)
    profile.active_trip = None
    profile.dispatch_board_cache = None
    profile.pay_advance = 0.0
    profile.pay_advance_used_for_load = False
    profile.career.xp = option.starting_level_xp
    profile.career.deliveries = option.starting_deliveries
    profile.career.on_time_deliveries = option.starting_on_time_deliveries
    profile.career.total_miles = option.starting_total_miles
    profile.career.total_earnings = option.starting_total_earnings
    profile.career.reputation = option.starting_reputation


def option_for_profile(profile) -> CareerStartOption:
    key = getattr(profile, "carrier_key", DEFAULT_START_KEY)
    option = start_option(key)
    if option.key != DEFAULT_START_KEY or not getattr(profile, "carrier_name", ""):
        return option
    carrier = getattr(profile, "carrier_name", STARTER_CARRIER_NAME)
    for candidate in START_OPTIONS.values():
        if candidate.carrier_name == carrier:
            return candidate
    return option
