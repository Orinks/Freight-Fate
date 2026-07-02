"""Terminal garage fuel and repair menu."""

from __future__ import annotations

from ..models.business import player_pays_operating_costs
from ..models.economy import REPAIR_COST_PER_PCT
from .base import MenuItem, MenuState

TERMINAL_FUEL_MIN = 20.0
TERMINAL_REPAIR_MIN = 60.0
TERMINAL_TIRE_MIN = 45.0
TERMINAL_WASH_MIN = 20.0
TIRE_SERVICE_COST_PER_PCT = 45.0
TRUCK_WASH_COST = 35.0


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
                "even when you drive cleanly. Company drivers bill "
                "the carrier; owner-operators pay the shop.",
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
        return self.ctx.world.cities[self.ctx.profile.current_city].region

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

    def _tire_label(self) -> str:
        p = self.ctx.profile
        wear = p.tire_wear_pct
        if wear < 1:
            return "Tires: tread is in top shape"
        if not player_pays_operating_costs(p.business_status):
            return f"Replace tires on assigned company tractor: {wear:.0f} percent wear, carrier billed"
        cost = round(wear * TIRE_SERVICE_COST_PER_PCT, 2)
        return f"Replace tires: {wear:.0f} percent wear for {cost:,.0f} dollars"

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
        cost = round(wear * TIRE_SERVICE_COST_PER_PCT, 2)
        if p.money < cost:
            serviceable = p.money / TIRE_SERVICE_COST_PER_PCT
            if serviceable < 1:
                self.ctx.audio.play("ui/error")
                self.ctx.say("Not enough money for one percent of tire service.")
                return
            cost = round(serviceable * TIRE_SERVICE_COST_PER_PCT, 2)
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
