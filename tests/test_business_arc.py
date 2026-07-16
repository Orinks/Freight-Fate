"""Company-driver to owner-operator business arc tests."""

import pygame
import pytest

from freight_fate.models.business import (
    AUTHORITY_ACTIVATION_COST,
    AUTHORITY_ACTIVATION_DELIVERIES,
    AUTHORITY_ACTIVATION_LEVEL,
    AUTHORITY_ACTIVATION_REPUTATION,
    AUTHORITY_ACTIVATION_WORKING_CAPITAL,
    AUTHORITY_READY_DELIVERIES,
    AUTHORITY_READY_LEVEL,
    AUTHORITY_READY_REPUTATION,
    AUTHORITY_READY_RESERVE,
    AUTHORITY_READY_WORKING_CAPITAL,
    COMPANY_DRIVER,
    INDEPENDENT_AUTHORITY,
    LEASED_OWNER_OPERATOR,
    OWNER_OPERATOR_BUY_IN,
    OWNER_OPERATOR_DELIVERIES,
    OWNER_OPERATOR_LEVEL,
    OWNER_OPERATOR_REPUTATION,
    OWNER_OPERATOR_WORKING_CAPITAL,
    authority_activation_eligibility,
    authority_readiness_eligibility,
    business_path_label,
    business_status_summary,
    has_authority_readiness,
    next_business_unlock,
    owner_operator_eligibility,
)
from freight_fate.models.career import LEVEL_XP
from freight_fate.models.career_ladder import CAREER_RANKS, STARTER_CARRIER_NAME
from freight_fate.models.trailers import (
    DEFAULT_TRAILER_PROGRAMS,
    TRAILER_CATALOG,
    compatible_with_programs,
    trailer_keys_for_cargo,
)


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def test_thirty_level_ladder_has_business_arc_titles():
    assert len(CAREER_RANKS) == 30
    assert [rank.level for rank in CAREER_RANKS] == list(range(1, 31))
    assert CAREER_RANKS[0].title == "Yard Trainee"
    assert CAREER_RANKS[4].title == "Regional Regular"
    assert CAREER_RANKS[14].title == "Owner-Operator Candidate"
    assert CAREER_RANKS[17].title == "Leased-On Owner-Operator"
    assert CAREER_RANKS[24].title == "Independent Authority Operator"
    assert CAREER_RANKS[-1].title == "Freight Fate Independent"


def test_owner_operator_unlock_requires_career_and_working_capital():
    from freight_fate.models.profile import Profile

    p = Profile(name="Business Gate")

    ok, reasons = owner_operator_eligibility(p)
    assert not ok
    assert any(f"Reach level {OWNER_OPERATOR_LEVEL}" in reason for reason in reasons)
    assert STARTER_CARRIER_NAME in business_status_summary(p)
    assert "company driver" in business_status_summary(p).lower()

    p.career.xp = LEVEL_XP[OWNER_OPERATOR_LEVEL - 1]
    p.career.deliveries = OWNER_OPERATOR_DELIVERIES
    p.career.reputation = OWNER_OPERATOR_REPUTATION
    p.money = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL

    ok, reasons = owner_operator_eligibility(p)
    assert ok
    assert reasons == ()

    p.pay_advance = 100.0
    ok, reasons = owner_operator_eligibility(p)
    assert not ok
    assert any("advance" in reason for reason in reasons)


def test_level_five_is_preparation_not_owner_operator_unlock():
    from freight_fate.models.profile import Profile

    p = Profile(name="Prep Gate")
    p.career.xp = LEVEL_XP[4]
    p.career.deliveries = 20
    p.career.reputation = 90
    p.money = 200_000.0

    ok, reasons = owner_operator_eligibility(p)

    assert not ok
    assert any(f"Reach level {OWNER_OPERATOR_LEVEL}" in reason for reason in reasons)
    assert "Regional Regular" in business_status_summary(p)
    assert "Experienced Company Driver" in next_business_unlock(p)


def test_business_path_reports_starter_company_rank_and_next_unlock():
    from freight_fate.models.profile import Profile

    p = Profile(name="Path Copy")
    p.career.xp = LEVEL_XP[14]

    assert STARTER_CARRIER_NAME in business_path_label(p)
    assert "Owner-Operator Candidate" in business_path_label(p)
    # From the level-14 prep rank onward, Business status reads the real
    # owner-operator checklist instead of pointing at the next rank title.
    unlock = next_business_unlock(p)
    assert "Owner-operator gate locked" in unlock
    assert "Reach level 18" in unlock


def test_business_status_menu_unlocks_owner_operator_when_qualified():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import BusinessStatusState

    app = App()
    try:
        app.ctx.profile = Profile(name="Owner Path", current_city="Chicago")
        p = app.ctx.profile
        p.career.xp = LEVEL_XP[OWNER_OPERATOR_LEVEL - 1]
        p.career.deliveries = OWNER_OPERATOR_DELIVERIES
        p.career.reputation = OWNER_OPERATOR_REPUTATION
        p.money = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL + 500

        app.push_state(BusinessStatusState(app.ctx))
        menu = app.state
        assert any("Buy into leased-on owner-operator" in item.text for item in menu.items)
        assert any("Carrier and rank" in item.text for item in menu.items)
        assert any("Next business unlock" in item.text for item in menu.items)
        while "Buy into leased-on owner-operator" not in menu.items[menu.index].text:
            menu.handle_event(key_event(pygame.K_DOWN))
        menu.handle_event(key_event(pygame.K_RETURN))

        assert p.business_status == LEASED_OWNER_OPERATOR
        assert p.money == pytest.approx(OWNER_OPERATOR_WORKING_CAPITAL + 500)
        assert p.dispatch_board_cache is None
    finally:
        app.shutdown()


def test_company_driver_garage_service_is_carrier_billed():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import GarageState

    app = App()
    try:
        app.ctx.profile = Profile(name="Company Service", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = COMPANY_DRIVER
        p.money = 25.0
        p.truck_fuel_gal = 0.0
        p.truck_damage_pct = 12.0
        app.push_state(GarageState(app.ctx))

        assert p.visible_owned_trucks() == ()
        assert "assigned company tractor" in app.state.items[0].text
        assert "carrier billed" in app.state.items[0].text
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.truck_fuel_gal == pytest.approx(p.truck_specs().fuel_tank_gal)
        assert p.money == pytest.approx(25.0)

        app.state.index = 1
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.truck_damage_pct == pytest.approx(0.0)
        assert p.money == pytest.approx(25.0)
    finally:
        app.shutdown()


def test_garage_sells_the_traction_equipment_ladder():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import GarageState
    from freight_fate.states.city_garage import (
        CHAIN_SET_COST,
        TIRE_SERVICE_COST_PER_PCT,
        WINTER_TIRE_PREMIUM,
    )

    app = App()
    try:
        app.ctx.profile = Profile(name="Equipment", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = LEASED_OWNER_OPERATOR
        p.owned_trucks = ["rig"]
        p.money = 20_000.0
        app.push_state(GarageState(app.ctx))
        state = app.state

        # Winter swap: a fresh set at the premium, compound on the record.
        p.tire_wear_pct = 30.0
        state._swap_tire_compound()
        winter_cost = round(100 * TIRE_SERVICE_COST_PER_PCT * WINTER_TIRE_PREMIUM, 2)
        assert p.tire_type == "winter"
        assert p.tire_wear_pct == 0.0
        assert p.money == pytest.approx(20_000.0 - winter_cost)

        # Chains go in the side box for a flat set price.
        money_before = p.money
        state._buy_chains()
        assert p.chains_owned
        assert p.chain_wear_pct == 0.0
        assert p.money == pytest.approx(money_before - CHAIN_SET_COST)

        # A fresh set aboard is not sold twice.
        money_before = p.money
        state._buy_chains()
        assert p.money == pytest.approx(money_before)
    finally:
        app.shutdown()


def test_company_driver_gets_carrier_chains_but_carrier_rubber():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import GarageState

    app = App()
    try:
        app.ctx.profile = Profile(name="Company Equip", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = COMPANY_DRIVER
        p.money = 50.0
        app.push_state(GarageState(app.ctx))
        state = app.state

        # The carrier specs the rubber: no compound swap on the assigned rig.
        state._swap_tire_compound()
        assert p.tire_type == "all_season"
        assert p.money == pytest.approx(50.0)

        # Chains are required equipment: carrier billed, never out of pocket.
        state._buy_chains()
        assert p.chains_owned
        assert p.money == pytest.approx(50.0)
    finally:
        app.shutdown()


def test_company_driver_truck_status_says_assigned_not_owned():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.models.trucks import TruckSpecs
    from freight_fate.states.city import CityMenuState

    app = App()
    spoken: list[str] = []
    try:
        app.ctx.profile = Profile(name="Assigned Tractor", current_city="Chicago")
        app.ctx.profile.owned_trucks = ["rig", "heavy_hauler"]  # legacy save data
        app.ctx.profile.truck = "heavy_hauler"
        app.ctx.profile.upgrades = {"engine_tune": 2}
        app.ctx.say = lambda text, interrupt=True: spoken.append(text)
        menu = CityMenuState(app.ctx)
        menu._truck_status()

        assert spoken
        assert "Assigned Northstar Freight Lines tractor" in spoken[-1]
        assert "Owned tractor" not in spoken[-1]
        assert "standard rig" in spoken[-1]
        assert app.ctx.profile.truck_specs().max_torque_nm == pytest.approx(
            TruckSpecs().max_torque_nm
        )
    finally:
        app.shutdown()


def test_company_driver_shops_hide_owned_truck_language():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import TruckShopState, UpgradeShopState

    app = App()
    spoken: list[str] = []
    try:
        app.ctx.profile = Profile(name="No Ownership", current_city="Chicago")
        p = app.ctx.profile
        p.owned_trucks = ["rig", "heavy_hauler"]  # old save values stay hidden
        p.money = 200_000.0
        app.ctx.say = lambda text, interrupt=True: spoken.append(text)

        app.push_state(TruckShopState(app.ctx))
        assert "carrier-assigned tractor" in app.state.items[0].text
        assert not any("owned" in item.text.lower() for item in app.state.items)
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.truck == "rig"
        assert p.money == pytest.approx(200_000.0)
        assert "carrier-assigned" in spoken[-1]

        app.pop_state()
        app.push_state(UpgradeShopState(app.ctx))
        assert "carrier-assigned tractor" in app.state.items[0].text
        assert not any("owned" in item.text.lower() for item in app.state.items)
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.upgrades == {}
        assert p.money == pytest.approx(200_000.0)
        assert "carrier-assigned" in spoken[-1]
    finally:
        app.shutdown()


def test_owner_operator_buy_in_records_first_owned_tractor():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import BusinessStatusState

    app = App()
    try:
        app.ctx.profile = Profile(name="Buy In Equipment", current_city="Chicago")
        p = app.ctx.profile
        p.career.xp = LEVEL_XP[OWNER_OPERATOR_LEVEL - 1]
        p.career.deliveries = OWNER_OPERATOR_DELIVERIES
        p.career.reputation = OWNER_OPERATOR_REPUTATION
        p.money = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL

        app.push_state(BusinessStatusState(app.ctx))
        while "Buy into leased-on owner-operator" not in app.state.items[app.state.index].text:
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert p.business_status == LEASED_OWNER_OPERATOR
        # The buy-in takes over the tractor dispatch had you in: at the
        # level-18 gate that is a first-pick fleet unit, not the starter rig.
        from freight_fate.models.carrier_fleet import assigned_truck_key

        assigned = assigned_truck_key(p)
        assert p.truck == assigned
        assert p.visible_owned_trucks() == (assigned,)
        assert p.active_trailer_programs() == DEFAULT_TRAILER_PROGRAMS
    finally:
        app.shutdown()


def test_owner_operator_can_buy_switch_and_upgrade_owned_equipment():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import TruckShopState, UpgradeShopState

    app = App()
    try:
        app.ctx.profile = Profile(name="Owned Equipment", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = LEASED_OWNER_OPERATOR
        p.owned_trucks = ["rig"]
        p.money = 200_000.0

        app.push_state(UpgradeShopState(app.ctx))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.upgrades
        assert p.money < 200_000.0

        app.pop_state()
        money_after_upgrade = p.money
        app.push_state(TruckShopState(app.ctx))
        while "Heavy hauler" not in app.state.items[app.state.index].text:
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.truck == "heavy_hauler"
        assert "heavy_hauler" in p.visible_owned_trucks()
        assert p.money == pytest.approx(money_after_upgrade - 52_000.0)

        while "Standard rig" not in app.state.items[app.state.index].text:
            app.state.handle_event(key_event(pygame.K_DOWN))
        money_before_switch = p.money
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.truck == "rig"
        assert p.money == pytest.approx(money_before_switch)
    finally:
        app.shutdown()


def test_trailer_catalog_matches_current_cargo_classes():
    assert {"dry_van", "reefer", "flatbed", "bulk"} <= set(TRAILER_CATALOG)
    assert trailer_keys_for_cargo("general") == ("dry_van",)
    assert trailer_keys_for_cargo("refrigerated") == ("reefer",)
    assert trailer_keys_for_cargo("steel") == ("flatbed",)
    assert trailer_keys_for_cargo("grain") == ("bulk",)
    assert compatible_with_programs("farm_inputs", ("dry_van",))
    assert compatible_with_programs("farm_inputs", ("bulk",))
    assert TRAILER_CATALOG["reefer"].purchase_price > TRAILER_CATALOG["reefer"].lease_deposit
    assert (
        TRAILER_CATALOG["reefer"].owned_per_mile_reserve
        < TRAILER_CATALOG["reefer"].per_mile_reserve
    )


def test_company_driver_dispatch_uses_carrier_trailer_support():
    from freight_fate.models.jobs import CARGO_CATALOG, Job

    job = Job(
        CARGO_CATALOG["refrigerated"],
        10.0,
        "Chicago",
        "cold storage",
        "Milwaukee",
        92.0,
        1200.0,
        5.0,
    )

    assert job.locked_reason({"refrigerated"}, 4) == ""
    assert "Requires Reefer trailer program" in job.locked_reason(
        {"refrigerated"},
        4,
        trailer_programs=DEFAULT_TRAILER_PROGRAMS,
        carrier_trailer_support=False,
    )


def test_owner_operator_can_add_specialty_trailer_program():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import TrailerProgramState

    app = App()
    try:
        app.ctx.profile = Profile(name="Trailer Lease", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = LEASED_OWNER_OPERATOR
        p.owned_trucks = ["rig"]
        p.money = 20_000.0

        app.push_state(TrailerProgramState(app.ctx))
        assert "Dry van: included carrier trailer program" in app.state.items[0].text
        while "Reefer" not in app.state.items[app.state.index].text:
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert "reefer" in p.active_trailer_programs()
        assert p.money == pytest.approx(12_000.0)
        assert p.dispatch_board_cache is None
    finally:
        app.shutdown()


def test_own_authority_can_buy_owned_trailer():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import TrailerProgramState

    app = App()
    try:
        app.ctx.profile = Profile(name="Trailer Owner", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = INDEPENDENT_AUTHORITY
        p.owned_trucks = ["rig"]
        p.trailer_programs = ["dry_van", "reefer"]
        p.money = TRAILER_CATALOG["reefer"].purchase_price + 2_000.0
        p.dispatch_board_cache = {"old": True}

        app.push_state(TrailerProgramState(app.ctx))
        while "Reefer" not in app.state.items[app.state.index].text:
            app.state.handle_event(key_event(pygame.K_DOWN))
        assert "buy trailer" in app.state.items[app.state.index].text
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert p.visible_owned_trailers() == ("reefer",)
        assert "reefer" in p.active_trailer_programs()
        assert p.money == pytest.approx(2_000.0)
        assert p.dispatch_board_cache is None
        assert "owned trailer" in app.state.items[app.state.index].text
    finally:
        app.shutdown()


def test_leased_on_owner_operator_does_not_see_trailer_purchase():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import TrailerProgramState

    app = App()
    try:
        app.ctx.profile = Profile(name="Leased Trailer", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = LEASED_OWNER_OPERATOR
        p.owned_trucks = ["rig"]
        p.money = 200_000.0

        app.push_state(TrailerProgramState(app.ctx))

        assert any("lease program" in item.text for item in app.state.items)
        assert not any("buy trailer" in item.text for item in app.state.items)
        assert p.visible_owned_trailers() == ()
    finally:
        app.shutdown()


def test_owner_operator_job_board_labels_missing_trailer_program():
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState

    app = App()
    try:
        app.ctx.profile = Profile(name="Trailer Board", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = LEASED_OWNER_OPERATOR
        p.owned_trucks = ["rig"]
        job = Job(
            CARGO_CATALOG["refrigerated"],
            12.0,
            "Chicago",
            "cold storage",
            "Milwaukee",
            92.0,
            1800.0,
            7.0,
        )

        app.push_state(JobBoardState(app.ctx, [job]))

        assert "Needs Reefer trailer program" in app.state.items[0].text
        assert "Gross revenue" in app.state.items[0].text
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.active_trip is None
    finally:
        app.shutdown()


def test_owner_operator_job_board_accepts_matching_trailer_program():
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState

    app = App()
    try:
        app.ctx.profile = Profile(name="Trailer Board Ready", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = LEASED_OWNER_OPERATOR
        p.owned_trucks = ["rig"]
        p.trailer_programs = ["dry_van", "reefer"]
        job = Job(
            CARGO_CATALOG["refrigerated"],
            12.0,
            "Chicago",
            "cold storage",
            "Milwaukee",
            92.0,
            1800.0,
            7.0,
        )

        app.push_state(JobBoardState(app.ctx, [job]))

        assert "Trailer program: Reefer" in app.state.items[0].text
    finally:
        app.shutdown()


def test_own_authority_job_board_labels_owned_trailer_and_program_charge():
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState

    job = Job(
        CARGO_CATALOG["refrigerated"],
        12.0,
        "Chicago",
        "cold storage",
        "Milwaukee",
        92.0,
        1800.0,
        7.0,
    )
    app = App()
    try:
        app.ctx.profile = Profile(name="Direct Owned Trailer", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = INDEPENDENT_AUTHORITY
        p.owned_trucks = ["rig"]
        p.trailer_programs = ["dry_van", "reefer"]
        p.owned_trailers = ["reefer"]

        app.push_state(JobBoardState(app.ctx, [job]))

        assert "Direct gross" in app.state.items[0].text
        assert "Owned trailer: Reefer" in app.state.items[0].text
        assert "owned-trailer reserve" in app.state.items[0].text
    finally:
        app.shutdown()

    app = App()
    try:
        app.ctx.profile = Profile(name="Direct Program Trailer", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = INDEPENDENT_AUTHORITY
        p.owned_trucks = ["rig"]
        p.trailer_programs = ["dry_van", "reefer"]

        app.push_state(JobBoardState(app.ctx, [job]))

        assert "Trailer program: Reefer" in app.state.items[0].text
        assert "program charge" in app.state.items[0].text
    finally:
        app.shutdown()


def test_company_driver_trailer_program_menu_stays_carrier_provided():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import TrailerProgramState

    app = App()
    try:
        app.ctx.profile = Profile(name="Company Trailers", current_city="Chicago")
        app.push_state(TrailerProgramState(app.ctx))

        assert "carrier-provided trailers" in app.state.items[0].text
        assert not any("lease program for" in item.text for item in app.state.items)
    finally:
        app.shutdown()


def test_owner_operator_settlement_uses_specialty_trailer_program_charge():
    from freight_fate.models.business import build_business_settlement
    from freight_fate.models.jobs import CARGO_CATALOG, Job

    dry_job = Job(
        CARGO_CATALOG["general"], 12.0, "Chicago", "yard", "Milwaukee", 100.0, 1000.0, 6.0
    )
    reefer_job = Job(
        CARGO_CATALOG["refrigerated"], 12.0, "Chicago", "cold", "Milwaukee", 100.0, 1000.0, 6.0
    )

    dry = build_business_settlement(
        LEASED_OWNER_OPERATOR, dry_job, dry_job.pay, on_time=True, driver_charges=0.0
    )
    reefer = build_business_settlement(
        LEASED_OWNER_OPERATOR, reefer_job, reefer_job.pay, on_time=True, driver_charges=0.0
    )

    dry_trailer = next(c.amount for c in dry.business_charges if c.label == "trailer program")
    reefer_trailer = next(c.amount for c in reefer.business_charges if c.label == "trailer program")
    assert reefer_trailer > dry_trailer


def test_own_authority_owned_trailer_reduces_trailer_charge():
    from freight_fate.models.business import build_business_settlement
    from freight_fate.models.jobs import CARGO_CATALOG, Job

    job = Job(
        CARGO_CATALOG["refrigerated"], 12.0, "Chicago", "cold", "Milwaukee", 100.0, 1000.0, 6.0
    )

    program = build_business_settlement(
        INDEPENDENT_AUTHORITY, job, job.pay, on_time=True, driver_charges=0.0
    )
    owned = build_business_settlement(
        INDEPENDENT_AUTHORITY,
        job,
        job.pay,
        on_time=True,
        driver_charges=0.0,
        owned_trailers=("reefer",),
    )

    program_trailer = next(
        c.amount for c in program.business_charges if c.label == "trailer program"
    )
    owned_trailer = next(
        c.amount for c in owned.business_charges if c.label == "owned trailer reserve"
    )
    assert owned_trailer < program_trailer
    assert owned.net_before_advance > program.net_before_advance


def test_authority_readiness_requires_endgame_owner_operator():
    from freight_fate.models.profile import Profile

    p = Profile(name="Authority Gate", current_city="Chicago")
    ok, reasons = authority_readiness_eligibility(p)

    assert not ok
    assert any("owner-operator" in reason for reason in reasons)

    p.business_status = LEASED_OWNER_OPERATOR
    p.owned_trucks = ["rig"]
    p.career.xp = LEVEL_XP[AUTHORITY_READY_LEVEL - 1]
    p.career.deliveries = AUTHORITY_READY_DELIVERIES
    p.career.reputation = AUTHORITY_READY_REPUTATION
    p.money = AUTHORITY_READY_RESERVE + AUTHORITY_READY_WORKING_CAPITAL

    ok, reasons = authority_readiness_eligibility(p)

    assert ok
    assert reasons == ()
    assert "authority prep reserve" in next_business_unlock(p)


def test_business_status_menu_sets_authority_readiness_reserve():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import BusinessStatusState

    app = App()
    try:
        app.ctx.profile = Profile(name="Authority Ready", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = LEASED_OWNER_OPERATOR
        p.owned_trucks = ["rig"]
        p.career.xp = LEVEL_XP[AUTHORITY_READY_LEVEL - 1]
        p.career.deliveries = AUTHORITY_READY_DELIVERIES
        p.career.reputation = AUTHORITY_READY_REPUTATION
        p.money = AUTHORITY_READY_RESERVE + AUTHORITY_READY_WORKING_CAPITAL + 500
        p.dispatch_board_cache = {"old": True}

        app.push_state(BusinessStatusState(app.ctx))
        while (
            "Commit 12,500 dollars to authority prep" not in app.state.items[app.state.index].text
        ):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert has_authority_readiness(p)
        assert p.money == pytest.approx(AUTHORITY_READY_WORKING_CAPITAL + 500)
        assert p.dispatch_board_cache is None
        assert "Authority prep reserve is set" in business_status_summary(p)
        assert any("Authority prep reserve: set" in item.text for item in app.state.items)
    finally:
        app.shutdown()


def test_authority_activation_requires_prep_and_specialty_program():
    from freight_fate.models.profile import Profile

    p = Profile(name="Authority Activate", current_city="Chicago")
    p.business_status = LEASED_OWNER_OPERATOR
    p.owned_trucks = ["rig"]
    p.career.xp = LEVEL_XP[AUTHORITY_READY_LEVEL - 1]
    p.career.deliveries = AUTHORITY_ACTIVATION_DELIVERIES
    p.career.reputation = AUTHORITY_ACTIVATION_REPUTATION
    p.money = AUTHORITY_ACTIVATION_COST + AUTHORITY_ACTIVATION_WORKING_CAPITAL

    ok, reasons = authority_activation_eligibility(p)
    assert not ok
    assert any("prep reserve" in reason for reason in reasons)

    p.authority_readiness = True
    ok, reasons = authority_activation_eligibility(p)
    assert not ok
    assert any(f"level {AUTHORITY_ACTIVATION_LEVEL}" in reason for reason in reasons)

    p.career.xp = LEVEL_XP[AUTHORITY_ACTIVATION_LEVEL - 1]
    ok, reasons = authority_activation_eligibility(p)
    assert not ok
    assert any("specialty trailer" in reason for reason in reasons)

    p.trailer_programs = ["dry_van", "reefer"]
    ok, reasons = authority_activation_eligibility(p)
    assert ok
    assert reasons == ()


def test_business_status_menu_activates_own_authority():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import BusinessStatusState

    app = App()
    try:
        app.ctx.profile = Profile(name="Own Authority", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = LEASED_OWNER_OPERATOR
        p.owned_trucks = ["rig"]
        p.trailer_programs = ["dry_van", "reefer"]
        p.authority_readiness = True
        p.career.xp = LEVEL_XP[AUTHORITY_ACTIVATION_LEVEL - 1]
        p.career.deliveries = AUTHORITY_ACTIVATION_DELIVERIES
        p.career.reputation = AUTHORITY_ACTIVATION_REPUTATION
        p.money = AUTHORITY_ACTIVATION_COST + AUTHORITY_ACTIVATION_WORKING_CAPITAL + 750
        p.dispatch_board_cache = {"old": True}

        app.push_state(BusinessStatusState(app.ctx))
        while "Activate own authority" not in app.state.items[app.state.index].text:
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert p.business_status == INDEPENDENT_AUTHORITY
        assert p.money == pytest.approx(AUTHORITY_ACTIVATION_WORKING_CAPITAL + 750)
        assert p.dispatch_board_cache is None
        assert "Direct freight" in business_status_summary(p)
        assert any("Own authority active" in item.text for item in app.state.items)
    finally:
        app.shutdown()


def test_direct_freight_board_pays_more_and_uses_direct_label(world):
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState

    base = JobBoard(world, seed=44).offers(
        "Chicago", {"refrigerated", "heavy_haul", "high_value"}, level=25
    )
    direct = JobBoard(world, seed=44).offers(
        "Chicago",
        {"refrigerated", "heavy_haul", "high_value"},
        level=25,
        direct_freight=True,
    )

    assert base
    assert direct
    assert direct[0].pay > base[0].pay

    app = App()
    try:
        app.ctx.profile = Profile(name="Direct Board", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = INDEPENDENT_AUTHORITY
        p.owned_trucks = ["rig"]
        p.trailer_programs = ["dry_van", "reefer", "flatbed", "bulk"]
        app.push_state(JobBoardState(app.ctx, [direct[0]]))

        assert "Direct gross" in app.state.items[0].text
        assert "Trailer program:" in app.state.items[0].text
    finally:
        app.shutdown()


def test_independent_authority_settlement_adds_business_overhead():
    from freight_fate.models.business import build_business_settlement
    from freight_fate.models.jobs import CARGO_CATALOG, Job

    job = Job(CARGO_CATALOG["general"], 12.0, "Chicago", "yard", "Milwaukee", 100.0, 1500.0, 6.0)

    leased = build_business_settlement(
        LEASED_OWNER_OPERATOR, job, job.pay, on_time=True, driver_charges=0.0
    )
    direct = build_business_settlement(
        INDEPENDENT_AUTHORITY, job, job.pay, on_time=True, driver_charges=0.0
    )

    labels = {charge.label for charge in direct.business_charges}
    assert "authority compliance reserve" in labels
    assert "factoring fee" in labels
    assert direct.status_label == "own authority"
    assert direct.business_charge_total > leased.business_charge_total


def test_company_driver_board_labels_carrier_gross(world):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState, JobBoardState

    app = App()
    try:
        app.ctx.profile = Profile(name="Board Labels", current_city="Chicago")
        app.push_state(CityMenuState(app.ctx))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, JobBoardState)
        assert app.state.jobs
        assert "Carrier gross" in app.state.items[0].text
    finally:
        app.shutdown()


def test_late_company_driver_still_uses_company_settlement_until_buy_in():
    from freight_fate.models.business import build_business_settlement
    from freight_fate.models.jobs import CARGO_CATALOG, Job

    job = Job(
        CARGO_CATALOG["general"],
        18.0,
        "Chicago",
        "Chicago yard",
        "Milwaukee",
        92.0,
        1800.0,
        6.0,
    )
    settlement = build_business_settlement(
        COMPANY_DRIVER, job, 1800.0, on_time=True, driver_charges=0.0
    )

    assert settlement.status == COMPANY_DRIVER
    assert settlement.business_charges == ()
