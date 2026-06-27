"""Grounded career-start choices and starter carrier benefits."""

from __future__ import annotations

from dataclasses import dataclass, field

from .career import LEVEL_XP
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
    truck_fuel_gal: float = 150.0
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
            "Experienced-driver start: leased-on owner-operator from day one "
            "with a starter tractor and real operating costs."
        ),
        help_text=(
            "Skip the company-driver ladder. You start leased on with an owned "
            "starter tractor, more gross revenue, limited working capital, and "
            "operating costs such as fuel, repairs, reserves, and settlement "
            "fees coming out of your cash."
        ),
        default_city="Chicago",
        starting_money=18_000.0,
        owned_trucks=("rig",),
        truck_fuel_gal=110.0,
        truck_damage_pct=4.0,
        starting_level_xp=LEVEL_XP[14],
        starting_deliveries=35,
        starting_on_time_deliveries=30,
        starting_total_miles=42_000.0,
        starting_total_earnings=70_000.0,
        starting_reputation=80.0,
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
    profile.trailer_programs = (
        list(DEFAULT_TRAILER_PROGRAMS) if option.is_owner_operator else []
    )
    profile.upgrades = {}
    profile.truck_fuel_gal = option.truck_fuel_gal
    profile.truck_damage_pct = option.truck_damage_pct
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
