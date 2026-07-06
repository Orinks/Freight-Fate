"""Terminal garage: fuel, repairs, tires, wash, fleet upgrades, and the truck shop."""

from __future__ import annotations

from ..models.economy import REPAIR_COST_PER_PCT
from ..models.trucks import TRUCK_CATALOG, UPGRADE_CATALOG, TruckModel, Upgrade
from .base import MenuItem, MenuState

TERMINAL_FUEL_MIN = 20.0
TERMINAL_REPAIR_MIN = 60.0
TERMINAL_TIRE_MIN = 45.0
TERMINAL_WASH_MIN = 20.0
TIRE_SERVICE_COST_PER_PCT = 45.0
TRUCK_WASH_COST = 35.0


class GarageState(MenuState):
    title = "Garage"

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                self._fuel_label,
                self._refuel,
                help="Fill the tank at this region's diesel price. If cash "
                "is short, buy as many gallons as you can afford.",
            ),
            MenuItem(
                self._repair_label,
                self._repair,
                help="Restore the truck to full condition. If cash is short, "
                "repair as much damage as you can afford.",
            ),
            MenuItem(
                self._tire_label,
                self._service_tires,
                help="Replace worn tires. Normal miles add slow tire wear, "
                "even when you drive cleanly.",
            ),
            MenuItem(
                self._wash_label,
                self._wash_truck,
                help="Wash road grime off the truck after long or dirty runs.",
            ),
            MenuItem(
                "Upgrades",
                self._upgrades,
                help="Buy performance upgrades for your truck: more torque, "
                "less drag, a bigger tank, stronger brakes.",
            ),
            MenuItem(
                "Trucks", self._trucks, help="Buy a new truck, or switch between trucks you own."
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
        cost = self.ctx.economy.fuel_cost(self._region(), need)
        return f"Refuel {need:.0f} gallons for {cost:,.0f} dollars"

    def _repair_label(self) -> str:
        p = self.ctx.profile
        if p.truck_damage_pct < 1:
            return "Repairs: truck is in top shape"
        cost = self.ctx.economy.repair_cost(p.truck_damage_pct)
        return f"Repair {p.truck_damage_pct:.0f} percent damage for {cost:,.0f} dollars"

    def _tire_label(self) -> str:
        wear = self.ctx.profile.tire_wear_pct
        if wear < 1:
            return "Tires: tread is in top shape"
        cost = round(wear * TIRE_SERVICE_COST_PER_PCT, 2)
        return f"Replace tires: {wear:.0f} percent wear for {cost:,.0f} dollars"

    def _wash_label(self) -> str:
        grime = self.ctx.profile.road_grime_pct
        if grime < 1:
            return "Wash: truck is clean"
        return f"Wash truck: {grime:.0f} percent road grime for {TRUCK_WASH_COST:,.0f} dollars"

    def _refuel(self) -> None:
        p = self.ctx.profile
        tank = self._tank_gal()
        need = tank - p.truck_fuel_gal
        if need < 1:
            self.ctx.say("The tank is already full.")
            return
        cost = self.ctx.economy.fuel_cost(self._region(), need)
        if p.money < cost:
            price = self.ctx.economy.fuel_price(self._region())
            gallons = p.money / price if price > 0 else 0.0
            if gallons < 1:
                self.ctx.audio.play("ui/error")
                self.ctx.say("Not enough money for even one gallon of fuel.")
                return
            cost = self.ctx.economy.fuel_cost(self._region(), gallons)
            p.money -= cost
            p.truck_fuel_gal = min(tank, p.truck_fuel_gal + gallons)
            p.game_hours += TERMINAL_FUEL_MIN / 60.0
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
            return
        p.money -= cost
        p.truck_fuel_gal = tank
        p.game_hours += TERMINAL_FUEL_MIN / 60.0
        p.hos.on_duty(TERMINAL_FUEL_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("vehicle/fuel_pump")
        self.ctx.say(f"Tank filled. {cost:,.0f} dollars. You have {p.money:,.0f} dollars left.")
        self.ctx.award_achievement("route_refuel")
        self.refresh()

    def _repair(self) -> None:
        p = self.ctx.profile
        if p.truck_damage_pct < 1:
            self.ctx.say("Nothing to repair.")
            return
        cost = self.ctx.economy.repair_cost(p.truck_damage_pct)
        if p.money < cost:
            repairable = p.money / REPAIR_COST_PER_PCT
            if repairable < 1:
                self.ctx.audio.play("ui/error")
                self.ctx.say("Not enough money for one percent of repairs.")
                return
            cost = self.ctx.economy.repair_cost(repairable)
            p.money -= cost
            p.truck_damage_pct = max(0.0, p.truck_damage_pct - repairable)
            p.game_hours += TERMINAL_REPAIR_MIN / 60.0
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
            return
        p.money -= cost
        p.truck_damage_pct = 0.0
        p.game_hours += TERMINAL_REPAIR_MIN / 60.0
        p.hos.on_duty(TERMINAL_REPAIR_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.say(f"Truck repaired. {cost:,.0f} dollars. You have {p.money:,.0f} dollars left.")
        self.ctx.award_achievement("garage_repair")
        self.refresh()

    def _service_tires(self) -> None:
        p = self.ctx.profile
        wear = p.tire_wear_pct
        if wear < 1:
            self.ctx.say("The tires are already in top shape.")
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
        if p.money < TRUCK_WASH_COST:
            self.ctx.audio.play("ui/error")
            self.ctx.say(f"A truck wash costs {TRUCK_WASH_COST:,.0f} dollars.")
            return
        p.money -= TRUCK_WASH_COST
        p.road_grime_pct = 0.0
        p.game_hours += TERMINAL_WASH_MIN / 60.0
        p.hos.on_duty(TERMINAL_WASH_MIN)
        self.ctx.save_profile()
        self.ctx.audio.play("ui/notify")
        self.ctx.say(
            f"Truck washed for {TRUCK_WASH_COST:,.0f} dollars. "
            f"You have {p.money:,.0f} dollars left."
        )
        self.refresh()

    def _upgrades(self) -> None:
        self.ctx.push_state(UpgradeShopState(self.ctx))

    def _trucks(self) -> None:
        self.ctx.push_state(TruckShopState(self.ctx))


class UpgradeShopState(MenuState):
    title = "Upgrades"
    intro_help = (
        "Each entry speaks the fleet upgrade, its price, and what you "
        "already own. Upgrades apply to every truck in your fleet. "
        "Enter buys the next tier. Press F1 on an upgrade to hear "
        "what it does. Escape returns to the garage."
    )

    def announce_entry(self) -> None:
        p = self.ctx.profile
        self.ctx.say(
            f"Fleet upgrades. They apply to every truck you own. "
            f"You have {p.money:,.0f} dollars. {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(lambda u=u: self._label(u), lambda u=u: self._buy(u), help=u.description)
            for u in UPGRADE_CATALOG.values()
        ]
        items.append(MenuItem("Back", self.go_back))
        return items

    def _label(self, upgrade: Upgrade) -> str:
        owned = self.ctx.profile.upgrades.get(upgrade.key, 0)
        if owned >= upgrade.max_tier:
            tiers = f", tier {owned} of {upgrade.max_tier}" if upgrade.max_tier > 1 else ""
            return f"{upgrade.label}: owned{tiers}"
        price = upgrade.prices[owned]
        if upgrade.max_tier > 1:
            owned_part = f", tier {owned} owned" if owned else ""
            return (
                f"{upgrade.label}, tier {owned + 1} of {upgrade.max_tier}: "
                f"{price:,.0f} dollars{owned_part}"
            )
        return f"{upgrade.label}: {price:,.0f} dollars"

    def _buy(self, upgrade: Upgrade) -> None:
        p = self.ctx.profile
        owned = p.upgrades.get(upgrade.key, 0)
        if owned >= upgrade.max_tier:
            self.ctx.say(f"{upgrade.label} is already fully installed.")
            return
        price = upgrade.prices[owned]
        if p.money < price:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                f"Not enough money. {upgrade.label} costs {price:,.0f} dollars "
                f"and you have {p.money:,.0f}."
            )
            return
        p.money -= price
        p.upgrades[upgrade.key] = owned + 1
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        tier_part = f" tier {owned + 1}" if upgrade.max_tier > 1 else ""
        self.ctx.say(
            f"{upgrade.label}{tier_part} installed across your fleet for "
            f"{price:,.0f} dollars. You have {p.money:,.0f} dollars left."
        )
        self.ctx.award_achievement("first_upgrade")
        self.refresh()


class TruckShopState(MenuState):
    title = "Trucks"
    intro_help = (
        "Each entry speaks the truck, its price, and whether you own it. "
        "Enter buys a truck you do not own, or switches to one you do. "
        "Your fleet upgrades apply to whichever truck you drive. "
        "Press F1 on a truck to hear its character. Escape returns "
        "to the garage."
    )

    def announce_entry(self) -> None:
        p = self.ctx.profile
        self.ctx.say(f"Trucks. You have {p.money:,.0f} dollars. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        items = [
            MenuItem(lambda m=m: self._label(m), lambda m=m: self._pick(m), help=m.description)
            for m in TRUCK_CATALOG.values()
        ]
        items.append(MenuItem("Back", self.go_back))
        return items

    def _label(self, model: TruckModel) -> str:
        p = self.ctx.profile
        name = model.label.capitalize()
        specs = model.specs
        traits = (
            f"{specs.max_torque_nm / 1000:.1f} thousand newton meters torque, "
            f"{specs.fuel_tank_gal:.0f} gallon tank"
        )
        if model.key == p.truck:
            return f"{name}: currently driving, {traits}"
        if model.key in p.owned_trucks:
            return f"{name}: owned, {traits}, switch to it"
        return f"{name}: {traits}, buy for {model.price:,.0f} dollars"

    def _pick(self, model: TruckModel) -> None:
        p = self.ctx.profile
        if model.key == p.truck:
            self.ctx.say(f"You are already driving the {model.label}.")
            return
        if model.key not in p.owned_trucks:
            if p.money < model.price:
                self.ctx.audio.play("ui/error")
                self.ctx.say(
                    f"Not enough money. The {model.label} costs "
                    f"{model.price:,.0f} dollars and you have {p.money:,.0f}."
                )
                return
            p.money -= model.price
            p.owned_trucks.append(model.key)
            self.ctx.audio.play("ui/cash")
            self._switch_to(model)
            self.ctx.say(
                f"You bought the {model.label} for {model.price:,.0f} dollars "
                f"and it is now your truck. You have {p.money:,.0f} dollars left."
            )
            if model.key == "heavy_hauler":
                self.ctx.award_achievement("heavy_hauler")
            return
        self.ctx.audio.play("vehicle/truck_door")
        self._switch_to(model)
        self.ctx.say(f"You are now driving the {model.label}.")

    def _switch_to(self, model: TruckModel) -> None:
        p = self.ctx.profile
        p.truck = model.key
        p.truck_fuel_gal = min(p.truck_fuel_gal, p.truck_specs().fuel_tank_gal)
        self.ctx.save_profile()
        self.refresh()
