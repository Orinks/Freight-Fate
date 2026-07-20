"""Terminal garage fuel and repair menu."""

from __future__ import annotations

from ..models.business import player_pays_operating_costs
from ..models.economy import REPAIR_COST_PER_PCT
from .base import MenuItem, MenuState

TERMINAL_FUEL_MIN = 20.0
TERMINAL_REPAIR_MIN = 60.0
TERMINAL_TIRE_MIN = 45.0
TERMINAL_BRAKE_MIN = 90.0
TERMINAL_ENGINE_MIN = 240.0
TERMINAL_WASH_MIN = 20.0
TIRE_SERVICE_COST_PER_PCT = 45.0
BRAKE_SERVICE_COST_PER_PCT = 40.0
ENGINE_OVERHAUL_COST_PER_PCT = 120.0
TRUCK_WASH_COST = 35.0
# Traction equipment. A tire-compound swap is a fresh set at that compound's
# price -- the tread you hand back is gone, like real life. Winter rubber
# carries a real premium; chains are a per-truck set that lives in the side
# box until a pass calls for them.
WINTER_TIRE_PREMIUM = 1.25
CHAIN_SET_COST = 750.0
TERMINAL_CHAINS_MIN = 10.0


def _record_terminal_duty(ctx, start_hour: float, end_hour: float, note: str) -> None:
    terminal = ctx.world.home_terminal(ctx.profile.current_city)
    ctx.profile.duty_log.record("on_duty_not_driving", start_hour, end_hour, terminal.name, note)


class GarageState(MenuState):
    title = "Garage"

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                self._fuel_label,
                self._refuel,
                help="Fill the tank. Company drivers use carrier-assigned tractors and bill the carrier. "
                "Owner-operators pay this region's diesel price.",
            ),
            MenuItem(
                self._repair_label,
                self._repair,
                help="Restore the tractor to full condition. Company drivers "
                "bill the carrier; owner-operators pay the shop.",
            ),
            MenuItem(
                self._tire_label,
                self._service_tires,
                help="Replace worn tires. Normal miles add slow tire wear, "
                "even when you drive cleanly; heavy loads and hard braking "
                "add more. Worn tires grip the road less. Company drivers "
                "bill the carrier; owner-operators pay the shop.",
            ),
            MenuItem(
                self._tire_swap_label,
                self._swap_tire_compound,
                help="Change tire compound with a fresh set. Winter rubber "
                "bites harder on snow and ice but wears faster and gives up "
                "a little grip on warm dry pavement. All-season is the "
                "cheaper everyday tire. Company tractors run whatever the "
                "carrier specs.",
            ),
            MenuItem(
                self._chains_label,
                self._buy_chains,
                help="Keep a set of snow chains in the side box. You chain "
                "up from the pause menu when stopped in snow or ice. Chains "
                "grip glare ice like nothing else, but keep it near chain "
                "speed and off bare pavement or they grind apart and snap. "
                "Company drivers bill the carrier.",
            ),
            MenuItem(
                self._brake_label,
                self._service_brakes,
                help="Reline worn brake shoes. Riding the service brakes "
                "wears them, hot brakes wear faster, and the engine brake "
                "costs them nothing. Worn shoes pull weaker and fade "
                "sooner. Company drivers bill the carrier; owner-operators "
                "pay the shop.",
            ),
            MenuItem(
                self._engine_label,
                self._service_engine,
                help="Overhaul a tired engine. Hours under load wear it "
                "slowly; over-revving and lugging wear it fast. A worn "
                "engine is down on power and burns more fuel. Company "
                "drivers bill the carrier; owner-operators pay the shop.",
            ),
            MenuItem(
                self._wash_label,
                self._wash_truck,
                help="Wash road grime off the truck after long or dirty "
                "runs. Company drivers bill the carrier; "
                "owner-operators pay.",
            ),
            MenuItem(
                "Upgrades",
                self._upgrades,
                help="Owner-operators can buy performance upgrades for "
                "owned tractors: more torque, less drag, a bigger tank, "
                "stronger brakes.",
            ),
            MenuItem(
                "Trucks",
                self._trucks,
                help="Owner-operators can buy a new truck, or switch between trucks they own.",
            ),
            MenuItem(
                "Trailer programs",
                self._trailers,
                help="Company drivers use carrier trailers. Owner-operators "
                "can add specialty trailer program slots. Own-authority "
                "drivers can also buy trailers.",
            ),
            MenuItem("Back", self.go_back, help="Return to the terminal menu."),
        ]

    def _region(self) -> str:
        return self.ctx.world.city(self.ctx.profile.current_city).region

    def _tank_gal(self) -> float:
        return self.ctx.profile.truck_specs().fuel_tank_gal

    def _fuel_label(self) -> str:
        p = self.ctx.profile
        need = self._tank_gal() - p.truck_fuel_gal
        if need < 1:
            return "Fuel: tank is full"
        if not player_pays_operating_costs(p.business_status):
            return f"Refuel assigned company tractor: {need:.0f} gallons, carrier billed"
        cost = self.ctx.economy.fuel_cost(self._region(), need)
        return f"Refuel {need:.0f} gallons for {cost:,.0f} dollars"

    def _repair_label(self) -> str:
        p = self.ctx.profile
        if p.truck_damage_pct < 1:
            return "Repairs: truck is in top shape"
        if not player_pays_operating_costs(p.business_status):
            return f"Repair assigned company tractor: {p.truck_damage_pct:.0f} percent damage, carrier billed"
        cost = self.ctx.economy.repair_cost(p.truck_damage_pct)
        return f"Repair {p.truck_damage_pct:.0f} percent damage for {cost:,.0f} dollars"

    def _refuel(self) -> None:
        p = self.ctx.profile
        tank = self._tank_gal()
        need = tank - p.truck_fuel_gal
        if need < 1:
            self.ctx.say("The tank is already full.")
            return
        if not player_pays_operating_costs(p.business_status):
            p.truck_fuel_gal = tank
            p.game_hours += TERMINAL_FUEL_MIN / 60.0
            p.hos.on_duty(TERMINAL_FUEL_MIN)
            self.ctx.save_profile()
            self.ctx.audio.play("vehicle/fuel_pump")
            self.ctx.say(
                f"Assigned company tractor tank filled on the carrier fuel account. Fueling took "
                f"{TERMINAL_FUEL_MIN:.0f} minutes. You still have "
                f"{p.money:,.0f} dollars."
            )
            self.ctx.award_achievement("route_refuel")
            self.refresh()
            return
        cost = self.ctx.economy.fuel_cost(self._region(), need)
        if p.money < cost:
            self._partial_refuel(tank)
            return
        p.money -= cost
        p.truck_fuel_gal = tank
        start = p.game_hours
        p.game_hours += TERMINAL_FUEL_MIN / 60.0
        _record_terminal_duty(self.ctx, start, p.game_hours, "terminal fuel")
        p.hos.on_duty(TERMINAL_FUEL_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("vehicle/fuel_pump")
        self.ctx.say(f"Tank filled. {cost:,.0f} dollars. You have {p.money:,.0f} dollars left.")
        self.ctx.award_achievement("route_refuel")
        self.refresh()

    def _partial_refuel(self, tank: float) -> None:
        p = self.ctx.profile
        price = self.ctx.economy.fuel_price(self._region())
        gallons = p.money / price if price > 0 else 0.0
        if gallons < 1:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Not enough money for even one gallon of fuel.")
            return
        cost = self.ctx.economy.fuel_cost(self._region(), gallons)
        p.money -= cost
        p.truck_fuel_gal = min(tank, p.truck_fuel_gal + gallons)
        start = p.game_hours
        p.game_hours += TERMINAL_FUEL_MIN / 60.0
        _record_terminal_duty(self.ctx, start, p.game_hours, "terminal fuel")
        p.hos.on_duty(TERMINAL_FUEL_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("vehicle/fuel_pump")
        self.ctx.say(
            f"Partial fuel: added {gallons:.0f} gallons for "
            f"{cost:,.0f} dollars. "
            f"You have {p.money:,.0f} dollars left."
        )
        self.ctx.award_achievement("route_refuel")
        self.refresh()

    def _repair(self) -> None:
        p = self.ctx.profile
        if p.truck_damage_pct < 1:
            self.ctx.say("Nothing to repair.")
            return
        deep_damage = p.truck_damage_pct >= 75.0
        if not player_pays_operating_costs(p.business_status):
            fixed = p.truck_damage_pct
            p.truck_damage_pct = 0.0
            p.game_hours += TERMINAL_REPAIR_MIN / 60.0
            p.hos.on_duty(TERMINAL_REPAIR_MIN)
            self.ctx.save_profile()
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"Carrier shop repaired {fixed:.0f} percent damage on the assigned tractor. "
                f"The repair took {TERMINAL_REPAIR_MIN:.0f} minutes and did "
                f"not reduce your cash balance."
            )
            self.ctx.award_achievement("garage_repair")
            if deep_damage:
                self.ctx.award_achievement("deep_repair")
            self.refresh()
            return
        cost = self.ctx.economy.repair_cost(p.truck_damage_pct)
        if p.money < cost:
            self._partial_repair()
            return
        p.money -= cost
        p.truck_damage_pct = 0.0
        start = p.game_hours
        p.game_hours += TERMINAL_REPAIR_MIN / 60.0
        _record_terminal_duty(self.ctx, start, p.game_hours, "terminal repair")
        p.hos.on_duty(TERMINAL_REPAIR_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"Truck repaired. {cost:,.0f} dollars. You have {p.money:,.0f} dollars left.")
        self.ctx.award_achievement("garage_repair")
        if deep_damage:
            self.ctx.award_achievement("deep_repair")
        self.refresh()

    def _partial_repair(self) -> None:
        p = self.ctx.profile
        repairable = p.money / REPAIR_COST_PER_PCT
        if repairable < 1:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Not enough money for one percent of repairs.")
            return
        cost = self.ctx.economy.repair_cost(repairable)
        p.money -= cost
        p.truck_damage_pct = max(0.0, p.truck_damage_pct - repairable)
        start = p.game_hours
        p.game_hours += TERMINAL_REPAIR_MIN / 60.0
        _record_terminal_duty(self.ctx, start, p.game_hours, "terminal repair")
        p.hos.on_duty(TERMINAL_REPAIR_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"Partial repairs fixed {repairable:.0f} percent damage "
            f"for {cost:,.0f} dollars. "
            f"You have {p.money:,.0f} dollars left."
        )
        self.ctx.award_achievement("garage_repair")
        self.refresh()

    def _tire_cost_per_pct(self) -> float:
        premium = WINTER_TIRE_PREMIUM if self.ctx.profile.tire_type == "winter" else 1.0
        return TIRE_SERVICE_COST_PER_PCT * premium

    def _compound_word(self) -> str:
        return "winter" if self.ctx.profile.tire_type == "winter" else "all-season"

    def _tire_label(self) -> str:
        p = self.ctx.profile
        wear = p.tire_wear_pct
        if wear < 1:
            return f"Tires: {self._compound_word()} tread is in top shape"
        if not player_pays_operating_costs(p.business_status):
            return f"Replace tires on assigned company tractor: {wear:.0f} percent wear, carrier billed"
        cost = round(wear * self._tire_cost_per_pct(), 2)
        return (
            f"Replace {self._compound_word()} tires: "
            f"{wear:.0f} percent wear for {cost:,.0f} dollars"
        )

    def _brake_label(self) -> str:
        p = self.ctx.profile
        wear = p.brake_wear_pct
        if wear < 1:
            return "Brakes: shoes are in top shape"
        if not player_pays_operating_costs(p.business_status):
            return f"Brake job on assigned company tractor: {wear:.0f} percent wear, carrier billed"
        cost = round(wear * BRAKE_SERVICE_COST_PER_PCT, 2)
        return f"Brake job: {wear:.0f} percent wear for {cost:,.0f} dollars"

    def _engine_label(self) -> str:
        p = self.ctx.profile
        wear = p.engine_wear_pct
        if wear < 1:
            return "Engine: running like new"
        if not player_pays_operating_costs(p.business_status):
            return (
                f"Engine overhaul on assigned company tractor: "
                f"{wear:.0f} percent wear, carrier billed"
            )
        cost = round(wear * ENGINE_OVERHAUL_COST_PER_PCT, 2)
        return f"Engine overhaul: {wear:.0f} percent wear for {cost:,.0f} dollars"

    def _wash_label(self) -> str:
        p = self.ctx.profile
        grime = p.road_grime_pct
        if grime < 1:
            return "Wash: truck is clean"
        if not player_pays_operating_costs(p.business_status):
            return f"Wash assigned company tractor: {grime:.0f} percent road grime, carrier billed"
        return f"Wash truck: {grime:.0f} percent road grime for {TRUCK_WASH_COST:,.0f} dollars"

    def _service_tires(self) -> None:
        p = self.ctx.profile
        wear = p.tire_wear_pct
        if wear < 1:
            self.ctx.say("The tires are already in top shape.")
            return
        start = p.game_hours
        if not player_pays_operating_costs(p.business_status):
            p.tire_wear_pct = 0.0
            p.game_hours += TERMINAL_TIRE_MIN / 60.0
            _record_terminal_duty(self.ctx, start, p.game_hours, "tire service")
            p.hos.on_duty(TERMINAL_TIRE_MIN)
            self.ctx.save_profile()
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"Carrier shop replaced tires with {wear:.0f} percent wear on "
                f"the assigned tractor. The service took "
                f"{TERMINAL_TIRE_MIN:.0f} minutes and did not reduce your "
                "cash balance."
            )
            self.refresh()
            return
        per_pct = self._tire_cost_per_pct()
        cost = round(wear * per_pct, 2)
        if p.money < cost:
            serviceable = p.money / per_pct
            if serviceable < 1:
                self.ctx.audio.play("ui/error")
                self.ctx.say("Not enough money for one percent of tire service.")
                return
            cost = round(serviceable * per_pct, 2)
            p.money -= cost
            p.tire_wear_pct = max(0.0, p.tire_wear_pct - serviceable)
            p.game_hours += TERMINAL_TIRE_MIN / 60.0
            _record_terminal_duty(self.ctx, start, p.game_hours, "tire service")
            p.hos.on_duty(TERMINAL_TIRE_MIN)
            self.ctx.save_profile()
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"Partial tire service fixed {serviceable:.0f} percent wear "
                f"for {cost:,.0f} dollars. "
                f"You have {p.money:,.0f} dollars left."
            )
            self.refresh()
            return
        p.money -= cost
        p.tire_wear_pct = 0.0
        p.game_hours += TERMINAL_TIRE_MIN / 60.0
        _record_terminal_duty(self.ctx, start, p.game_hours, "tire service")
        p.hos.on_duty(TERMINAL_TIRE_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"Tires replaced. {cost:,.0f} dollars. You have {p.money:,.0f} dollars left.")
        self.refresh()

    def _tire_swap_label(self) -> str:
        p = self.ctx.profile
        if not player_pays_operating_costs(p.business_status):
            return "Tire compound: the carrier specs its own rubber"
        if p.tire_type == "winter":
            cost = round(100 * TIRE_SERVICE_COST_PER_PCT, 2)
            return f"Switch to all-season tires: fresh set for {cost:,.0f} dollars"
        cost = round(100 * TIRE_SERVICE_COST_PER_PCT * WINTER_TIRE_PREMIUM, 2)
        return f"Switch to winter tires: fresh set for {cost:,.0f} dollars"

    def _swap_tire_compound(self) -> None:
        p = self.ctx.profile
        if not player_pays_operating_costs(p.business_status):
            self.ctx.say(
                "The carrier decides what rubber the assigned tractor runs. "
                "Company tractors stay on all-season tires."
            )
            return
        to_winter = p.tire_type != "winter"
        premium = WINTER_TIRE_PREMIUM if to_winter else 1.0
        cost = round(100 * TIRE_SERVICE_COST_PER_PCT * premium, 2)
        if p.money < cost:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                f"A fresh set of {'winter' if to_winter else 'all-season'} tires "
                f"costs {cost:,.0f} dollars."
            )
            return
        start = p.game_hours
        p.money -= cost
        p.tire_type = "winter" if to_winter else "all_season"
        p.tire_wear_pct = 0.0
        p.game_hours += TERMINAL_TIRE_MIN / 60.0
        _record_terminal_duty(self.ctx, start, p.game_hours, "tire swap")
        p.hos.on_duty(TERMINAL_TIRE_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        trade = (
            "Better bite on snow and ice; the soft compound wears faster and "
            "gives up a little on warm dry pavement."
            if to_winter
            else "Back to the everyday tire: longer tread life, standard grip."
        )
        self.ctx.say(
            f"Fresh {'winter' if to_winter else 'all-season'} set mounted for "
            f"{cost:,.0f} dollars. {trade} "
            f"You have {p.money:,.0f} dollars left."
        )
        self.refresh()

    def _chains_label(self) -> str:
        p = self.ctx.profile
        wear = p.chain_wear_pct
        carrier = not player_pays_operating_costs(p.business_status)
        if not p.chains_owned or wear >= 100:
            what = "Replace snapped snow chains" if p.chains_owned else "Buy snow chains"
            if carrier:
                return f"{what}: carrier billed"
            return f"{what}: {CHAIN_SET_COST:,.0f} dollars"
        if wear >= 1:
            if carrier:
                return f"Replace snow chains: {wear:.0f} percent worn, carrier billed"
            return f"Replace snow chains: {wear:.0f} percent worn, {CHAIN_SET_COST:,.0f} dollars"
        return "Snow chains: aboard and fresh"

    def _buy_chains(self) -> None:
        p = self.ctx.profile
        if p.chains_owned and p.chain_wear_pct < 1:
            self.ctx.say("A fresh set of chains is already in the side box.")
            return
        start = p.game_hours
        if not player_pays_operating_costs(p.business_status):
            p.chains_owned = True
            p.chain_wear_pct = 0.0
            p.game_hours += TERMINAL_CHAINS_MIN / 60.0
            _record_terminal_duty(self.ctx, start, p.game_hours, "chain set")
            p.hos.on_duty(TERMINAL_CHAINS_MIN)
            self.ctx.save_profile()
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                "A fresh chain set from the carrier shop is stowed in the "
                "side box, on the carrier account."
            )
            self.refresh()
            return
        if p.money < CHAIN_SET_COST:
            self.ctx.audio.play("ui/error")
            self.ctx.say(f"A set of snow chains costs {CHAIN_SET_COST:,.0f} dollars.")
            return
        p.money -= CHAIN_SET_COST
        p.chains_owned = True
        p.chain_wear_pct = 0.0
        p.game_hours += TERMINAL_CHAINS_MIN / 60.0
        _record_terminal_duty(self.ctx, start, p.game_hours, "chain set")
        p.hos.on_duty(TERMINAL_CHAINS_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"A fresh chain set is stowed in the side box for "
            f"{CHAIN_SET_COST:,.0f} dollars. "
            f"You have {p.money:,.0f} dollars left."
        )
        self.refresh()

    def _service_brakes(self) -> None:
        self._service_wear_meter(
            attr="brake_wear_pct",
            cost_per_pct=BRAKE_SERVICE_COST_PER_PCT,
            minutes=TERMINAL_BRAKE_MIN,
            duty_note="brake service",
            fresh_say="The brakes are already in top shape.",
            carrier_done="relined the brakes",
            partial_noun="brake service",
            done_say="Brakes relined.",
        )

    def _service_engine(self) -> None:
        self._service_wear_meter(
            attr="engine_wear_pct",
            cost_per_pct=ENGINE_OVERHAUL_COST_PER_PCT,
            minutes=TERMINAL_ENGINE_MIN,
            duty_note="engine overhaul",
            fresh_say="The engine is already running like new.",
            carrier_done="overhauled the engine",
            partial_noun="engine work",
            done_say="Engine overhauled.",
        )

    def _service_wear_meter(
        self,
        *,
        attr: str,
        cost_per_pct: float,
        minutes: float,
        duty_note: str,
        fresh_say: str,
        carrier_done: str,
        partial_noun: str,
        done_say: str,
    ) -> None:
        """Shared company/partial/full flow for a wear-meter service.

        Mirrors the tire service exactly; tires keep their own wording
        because players already know those phrases.
        """
        p = self.ctx.profile
        wear = getattr(p, attr)
        if wear < 1:
            self.ctx.say(fresh_say)
            return
        start = p.game_hours
        if not player_pays_operating_costs(p.business_status):
            setattr(p, attr, 0.0)
            p.game_hours += minutes / 60.0
            _record_terminal_duty(self.ctx, start, p.game_hours, duty_note)
            p.hos.on_duty(minutes)
            self.ctx.save_profile()
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"Carrier shop {carrier_done} at {wear:.0f} percent wear on "
                f"the assigned tractor. The service took {minutes:.0f} "
                "minutes and did not reduce your cash balance."
            )
            self.refresh()
            return
        cost = round(wear * cost_per_pct, 2)
        if p.money < cost:
            serviceable = p.money / cost_per_pct
            if serviceable < 1:
                self.ctx.audio.play("ui/error")
                self.ctx.say(f"Not enough money for one percent of {partial_noun}.")
                return
            cost = round(serviceable * cost_per_pct, 2)
            p.money -= cost
            setattr(p, attr, max(0.0, wear - serviceable))
            p.game_hours += minutes / 60.0
            _record_terminal_duty(self.ctx, start, p.game_hours, duty_note)
            p.hos.on_duty(minutes)
            self.ctx.save_profile()
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"Partial {partial_noun} fixed {serviceable:.0f} percent wear "
                f"for {cost:,.0f} dollars. "
                f"You have {p.money:,.0f} dollars left."
            )
            self.refresh()
            return
        p.money -= cost
        setattr(p, attr, 0.0)
        p.game_hours += minutes / 60.0
        _record_terminal_duty(self.ctx, start, p.game_hours, duty_note)
        p.hos.on_duty(minutes)
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"{done_say} {cost:,.0f} dollars. You have {p.money:,.0f} dollars left.")
        self.refresh()

    def _wash_truck(self) -> None:
        p = self.ctx.profile
        if p.road_grime_pct < 1:
            self.ctx.say("The truck is already clean.")
            return
        start = p.game_hours
        if not player_pays_operating_costs(p.business_status):
            grime = p.road_grime_pct
            p.road_grime_pct = 0.0
            p.game_hours += TERMINAL_WASH_MIN / 60.0
            _record_terminal_duty(self.ctx, start, p.game_hours, "truck wash")
            p.hos.on_duty(TERMINAL_WASH_MIN)
            self.ctx.save_profile()
            self.ctx.audio.play("ui/notify")
            self.ctx.say(
                f"Carrier account covered the truck wash: {grime:.0f} percent "
                "road grime cleaned off the assigned tractor."
            )
            self.refresh()
            return
        if p.money < TRUCK_WASH_COST:
            self.ctx.audio.play("ui/error")
            self.ctx.say(f"A truck wash costs {TRUCK_WASH_COST:,.0f} dollars.")
            return
        p.money -= TRUCK_WASH_COST
        p.road_grime_pct = 0.0
        p.game_hours += TERMINAL_WASH_MIN / 60.0
        _record_terminal_duty(self.ctx, start, p.game_hours, "truck wash")
        p.hos.on_duty(TERMINAL_WASH_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"Truck washed for {TRUCK_WASH_COST:,.0f} dollars. "
            f"You have {p.money:,.0f} dollars left."
        )
        self.refresh()

    def _upgrades(self) -> None:
        from .city_business import UpgradeShopState

        self.ctx.push_state(UpgradeShopState(self.ctx))

    def _trucks(self) -> None:
        from .city_business import TruckShopState

        self.ctx.push_state(TruckShopState(self.ctx))

    def _trailers(self) -> None:
        from .city_business import TrailerProgramState

        self.ctx.push_state(TrailerProgramState(self.ctx))
