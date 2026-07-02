"""Business-status, truck, upgrade, and trailer program menus."""

from __future__ import annotations

from ..models.business import (
    AUTHORITY_ACTIVATION_COST,
    AUTHORITY_READY_RESERVE,
    INDEPENDENT_AUTHORITY,
    LEASED_OWNER_OPERATOR,
    OWNER_OPERATOR_BUY_IN,
    authority_activation_eligibility,
    authority_readiness_eligibility,
    business_path_label,
    business_status_summary,
    has_authority_readiness,
    is_owner_operator,
    next_business_unlock,
    owner_operator_eligibility,
    status_label,
)
from ..models.career import (
    ENDORSEMENT_COURSE_COSTS,
    ENDORSEMENT_LABELS_SPOKEN,
    ENDORSEMENT_LEVELS,
)
from ..models.trailers import (
    DEFAULT_TRAILER_PROGRAMS,
    TRAILER_CATALOG,
    TrailerType,
)
from ..models.trucks import TRUCK_CATALOG, UPGRADE_CATALOG, TruckModel, Upgrade
from .base import MenuItem, MenuState


class BusinessStatusState(MenuState):
    title = "Business status"
    intro_help = (
        "Use up and down arrows to review the business path. Enter repeats "
        "status, or buys into owner-operator status when qualified. Escape "
        "returns to the terminal."
    )

    def announce_entry(self) -> None:
        self.ctx.say(
            f"Business status. {business_status_summary(self.ctx.profile)} {self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        p = self.ctx.profile
        items = [
            MenuItem(
                self._summary_label,
                self._summary,
                help="Hear the current business status and tradeoffs.",
            ),
            MenuItem(
                self._rank_label,
                self._rank_status,
                help="Hear your starter carrier, rank, and career stage.",
            ),
            MenuItem(
                self._next_unlock_label,
                self._next_unlock,
                help="Hear the next career or business unlock.",
            ),
        ]
        if not is_owner_operator(p.business_status):
            ok, _reasons = owner_operator_eligibility(p)
            if ok:
                items.append(
                    MenuItem(
                        f"Buy into leased-on owner-operator: {OWNER_OPERATOR_BUY_IN:,.0f} dollars",
                        self._become_owner_operator,
                        help="Buy your first tractor position and start running as "
                        "a leased-on owner-operator. Higher revenue, but your "
                        "business pays operating costs.",
                    )
                )
            else:
                items.append(
                    MenuItem(
                        "Owner-operator path locked",
                        self._summary,
                        help="Hear the remaining requirements.",
                    )
                )
        else:
            if p.business_status == INDEPENDENT_AUTHORITY:
                items.append(
                    MenuItem(
                        "Own authority active",
                        self._summary,
                        help="Direct freight is available. Settlement includes "
                        "insurance, compliance, and factoring costs.",
                    )
                )
            elif has_authority_readiness(p):
                items.append(
                    MenuItem(
                        "Authority prep reserve: set",
                        self._summary,
                        help="This career has set aside the prep reserve for "
                        "own-authority startup.",
                    )
                )
                ok, _reasons = authority_activation_eligibility(p)
                if ok:
                    items.append(
                        MenuItem(
                            f"Activate own authority: {AUTHORITY_ACTIVATION_COST:,.0f} dollars",
                            self._activate_authority,
                            help="Start direct freight with higher gross revenue "
                            "and more business overhead.",
                        )
                    )
                else:
                    items.append(
                        MenuItem(
                            "Own authority locked",
                            self._next_unlock,
                            help="Hear the remaining own-authority requirements.",
                        )
                    )
            else:
                ok, _reasons = authority_readiness_eligibility(p)
                if ok:
                    items.append(
                        MenuItem(
                            f"Commit {AUTHORITY_READY_RESERVE:,.0f} dollars to authority prep",
                            self._set_authority_readiness,
                            help="Set aside money for the later own-authority activation gate.",
                        )
                    )
                else:
                    items.append(
                        MenuItem(
                            "Authority prep locked",
                            self._next_unlock,
                            help="Hear the remaining authority prep requirements.",
                        )
                    )
        items.append(MenuItem("Back", self.go_back))
        return items

    def _summary_label(self) -> str:
        p = self.ctx.profile
        return f"Current status: {status_label(p.business_status)}"

    def _summary(self) -> None:
        self.ctx.say(business_status_summary(self.ctx.profile))

    def _rank_label(self) -> str:
        return "Carrier and rank"

    def _rank_status(self) -> None:
        self.ctx.say(business_path_label(self.ctx.profile))

    def _next_unlock_label(self) -> str:
        return "Next business unlock"

    def _next_unlock(self) -> None:
        self.ctx.say(next_business_unlock(self.ctx.profile))

    def _become_owner_operator(self) -> None:
        p = self.ctx.profile
        ok, reasons = owner_operator_eligibility(p)
        if not ok:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Owner-operator path locked. " + " ".join(reasons))
            self.refresh()
            return
        p.money -= OWNER_OPERATOR_BUY_IN
        assigned = p.active_truck_key()
        p.business_status = LEASED_OWNER_OPERATOR
        if assigned not in p.owned_trucks:
            p.owned_trucks.append(assigned)
        if not p.trailer_programs:
            p.trailer_programs = list(DEFAULT_TRAILER_PROGRAMS)
        p.truck = assigned
        p.dispatch_board_cache = None
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        self.ctx.say(
            f"Leased-on owner-operator status unlocked. You paid "
            f"{OWNER_OPERATOR_BUY_IN:,.0f} dollars toward your first tractor "
            f"and kept {p.money:,.0f} dollars working capital. Future loads "
            "pay higher gross revenue, and your business pays fuel, repairs, "
            "maintenance reserve, insurance, trailer program, truck payment "
            "reserve, and settlement fees."
        )
        self.refresh()

    def _set_authority_readiness(self) -> None:
        p = self.ctx.profile
        ok, reasons = authority_readiness_eligibility(p)
        if not ok:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Authority prep locked. " + " ".join(reasons))
            self.refresh()
            return
        p.money -= AUTHORITY_READY_RESERVE
        p.authority_readiness = True
        p.dispatch_board_cache = None
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        self.ctx.say(
            f"Authority prep reserve set aside: "
            f"{AUTHORITY_READY_RESERVE:,.0f} dollars. You have "
            f"{p.money:,.0f} dollars left. Own authority can unlock after "
            "the final delivery, reputation, trailer program, and cash gates. "
            "For now you remain leased on."
        )
        self.refresh()

    def _activate_authority(self) -> None:
        p = self.ctx.profile
        ok, reasons = authority_activation_eligibility(p)
        if not ok:
            self.ctx.audio.play("ui/error")
            self.ctx.say("Own authority locked. " + " ".join(reasons))
            self.refresh()
            return
        p.money -= AUTHORITY_ACTIVATION_COST
        p.business_status = INDEPENDENT_AUTHORITY
        p.dispatch_board_cache = None
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        self.ctx.say(
            f"Own authority active. Startup cost "
            f"{AUTHORITY_ACTIVATION_COST:,.0f} dollars. You have "
            f"{p.money:,.0f} dollars left. Dispatch now lists direct freight. "
            "Settlement includes insurance, compliance, trailer, truck, and "
            "factoring costs."
        )
        self.refresh()


class UpgradeShopState(MenuState):
    title = "Upgrades"
    intro_help = (
        "Each entry speaks the fleet upgrade, its price, and what you "
        "already own. Upgrades apply to every tractor in your fleet. "
        "Enter buys the next tier. Press F1 on an upgrade to hear "
        "what it does. Escape returns to the garage."
    )

    def announce_entry(self) -> None:
        p = self.ctx.profile
        if is_owner_operator(p.business_status):
            self.ctx.say(
                f"Fleet upgrades. They apply to every tractor you own. "
                f"You have {p.money:,.0f} dollars. {self.current_text()}"
            )
        else:
            self.ctx.say(f"Upgrades. You have {p.money:,.0f} dollars. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        if not is_owner_operator(self.ctx.profile.business_status):
            return [
                MenuItem(
                    "Upgrades locked: carrier-assigned tractor",
                    self._locked,
                    help=(
                        "Company drivers use fleet-maintained equipment. "
                        "Performance upgrades unlock after the leased-on "
                        "owner-operator buy-in."
                    ),
                ),
                MenuItem("Back", self.go_back),
            ]
        items = [
            MenuItem(lambda u=u: self._label(u), lambda u=u: self._buy(u), help=u.description)
            for u in UPGRADE_CATALOG.values()
        ]
        items.append(MenuItem("Back", self.go_back))
        return items

    def _locked(self) -> None:
        self.ctx.audio.play("ui/error")
        self.ctx.say(
            "Upgrades are locked. Company drivers use carrier-assigned, "
            "fleet-maintained tractors. Ownership upgrades unlock after the "
            "leased-on owner-operator buy-in."
        )

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
        if not is_owner_operator(p.business_status):
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                "Upgrades unlock after the leased-on owner-operator buy-in. "
                "The company tractor stays carrier-maintained for now."
            )
            return
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
            f"{price:,.0f} dollars. "
            f"You have {p.money:,.0f} dollars left."
        )
        self.ctx.award_achievement("first_upgrade")
        self.refresh()


class TruckShopState(MenuState):
    title = "Trucks"
    intro_help = (
        "Owner-operators can buy tractors or switch among tractors "
        "they own. Your fleet upgrades apply to whichever tractor you "
        "drive. Company drivers use carrier-assigned equipment. "
        "Escape returns to the garage."
    )

    def announce_entry(self) -> None:
        p = self.ctx.profile
        self.ctx.say(f"Trucks. You have {p.money:,.0f} dollars. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        if not is_owner_operator(self.ctx.profile.business_status):
            return [
                MenuItem(
                    "Truck ownership locked: carrier-assigned tractor",
                    self._locked,
                    help=(
                        "Company drivers do not buy tractors here. The carrier "
                        "assigns and maintains the company tractor until the "
                        "leased-on owner-operator buy-in."
                    ),
                ),
                MenuItem("Back", self.go_back),
            ]
        items = [
            MenuItem(lambda m=m: self._label(m), lambda m=m: self._pick(m), help=m.description)
            for m in TRUCK_CATALOG.values()
        ]
        items.append(MenuItem("Back", self.go_back))
        return items

    def _locked(self) -> None:
        self.ctx.audio.play("ui/error")
        self.ctx.say(
            "Truck ownership is locked. Company drivers run a carrier-assigned "
            "tractor. Buying and switching owned tractors unlocks after the "
            "leased-on owner-operator buy-in."
        )

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
        if model.key in p.visible_owned_trucks():
            return f"{name}: owned, {traits}, switch to it"
        return f"{name}: {traits}, buy for {model.price:,.0f} dollars"

    def _pick(self, model: TruckModel) -> None:
        p = self.ctx.profile
        if model.key == p.truck:
            self.ctx.say(f"You are already driving the {model.label}.")
            return
        if not is_owner_operator(p.business_status):
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                "Truck purchases unlock after the leased-on owner-operator buy-in. "
                "For now, the carrier assigns your company tractor."
            )
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
                f"and it is now your owned tractor. "
                f"You have {p.money:,.0f} dollars left."
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


class TrailerProgramState(MenuState):
    title = "Trailers"
    intro_help = (
        "Company drivers use carrier-provided trailers. Owner-operators start "
        "with the dry van trailer program and can add specialty programs. "
        "Own-authority drivers can buy trailers outright. "
        "Escape returns to the garage."
    )

    def announce_entry(self) -> None:
        p = self.ctx.profile
        self.ctx.say(f"Trailers. You have {p.money:,.0f} dollars. {self.current_text()}")

    def build_items(self) -> list[MenuItem]:
        p = self.ctx.profile
        if not is_owner_operator(p.business_status):
            return [
                MenuItem(
                    "Trailer programs locked: carrier-provided trailers",
                    self._locked,
                    help=(
                        "Company drivers do not lease or buy trailers. The "
                        "carrier supplies the right trailer for approved loads."
                    ),
                ),
                MenuItem("Back", self.go_back),
            ]
        items = [
            MenuItem(lambda t=t: self._label(t), lambda t=t: self._select(t), help=t.description)
            for t in TRAILER_CATALOG.values()
        ]
        items.append(MenuItem("Back", self.go_back))
        return items

    def _locked(self) -> None:
        self.ctx.audio.play("ui/error")
        self.ctx.say(
            "Trailer programs are locked. Company drivers use carrier-provided "
            "trailers, so no trailer lease is needed."
        )

    def _label(self, trailer: TrailerType) -> str:
        p = self.ctx.profile
        owned = set(p.visible_owned_trailers())
        if p.business_status == INDEPENDENT_AUTHORITY:
            if trailer.key in owned:
                return f"{trailer.label}: owned trailer"
            return f"{trailer.label}: buy trailer for {trailer.purchase_price:,.0f} dollars"
        programs = set(p.active_trailer_programs())
        if trailer.key in programs:
            if trailer.key in DEFAULT_TRAILER_PROGRAMS:
                return f"{trailer.label}: included carrier trailer program"
            return f"{trailer.label}: leased program active"
        return f"{trailer.label}: lease program for {trailer.lease_deposit:,.0f} dollars"

    def _select(self, trailer: TrailerType) -> None:
        if self.ctx.profile.business_status == INDEPENDENT_AUTHORITY:
            self._buy_trailer(trailer)
            return
        self._lease(trailer)

    def _lease(self, trailer: TrailerType) -> None:
        p = self.ctx.profile
        if not is_owner_operator(p.business_status):
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                "Company drivers use carrier-provided trailers. Trailer "
                "programs unlock after the leased-on owner-operator buy-in."
            )
            return
        if trailer.key in p.active_trailer_programs():
            self.ctx.say(f"{trailer.label} trailer program is already active.")
            return
        if p.money < trailer.lease_deposit:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                f"Not enough money. {trailer.label} trailer program costs "
                f"{trailer.lease_deposit:,.0f} dollars and you have "
                f"{p.money:,.0f}."
            )
            return
        p.money -= trailer.lease_deposit
        p.trailer_programs = list(p.active_trailer_programs()) + [trailer.key]
        p.dispatch_board_cache = None
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        self.ctx.say(
            f"{trailer.label} trailer program active for "
            f"{trailer.lease_deposit:,.0f} dollars. You have "
            f"{p.money:,.0f} dollars left. Matching cargo can now appear as "
            "available on the dispatch board."
        )
        self.refresh()

    def _buy_trailer(self, trailer: TrailerType) -> None:
        p = self.ctx.profile
        if p.business_status != INDEPENDENT_AUTHORITY:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                "Trailer purchases unlock after own authority. Leased-on "
                "owner-operators can use trailer programs for now."
            )
            return
        if trailer.key in p.visible_owned_trailers():
            self.ctx.say(f"You already own a {trailer.label} trailer.")
            return
        if p.money < trailer.purchase_price:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                f"Not enough money. The {trailer.label} trailer costs "
                f"{trailer.purchase_price:,.0f} dollars and you have "
                f"{p.money:,.0f}."
            )
            return
        p.money -= trailer.purchase_price
        p.owned_trailers = list(p.visible_owned_trailers()) + [trailer.key]
        p.dispatch_board_cache = None
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        self.ctx.say(
            f"{trailer.label} trailer purchased for "
            f"{trailer.purchase_price:,.0f} dollars. You have "
            f"{p.money:,.0f} dollars left. Matching direct freight now uses "
            "an owned-trailer reserve at settlement."
        )
        self.refresh()


class EndorsementCourseState(MenuState):
    title = "Endorsement courses"
    intro_help = (
        "Each endorsement course unlocks its freight early, before the "
        "carrier would sponsor the training at the listed level. Enter books "
        "a course you can afford. Escape returns to the terminal."
    )

    def announce_entry(self) -> None:
        p = self.ctx.profile
        self.ctx.say(
            f"Endorsement courses. Pay for training yourself to unlock "
            f"specialty freight early; the carrier sponsors each course for "
            f"free at its listed level. You have {p.money:,.0f} dollars. "
            f"{self.current_text()}"
        )

    def build_items(self) -> list[MenuItem]:
        career = self.ctx.profile.career
        items: list[MenuItem] = []
        for key, level in ENDORSEMENT_LEVELS.items():
            label = ENDORSEMENT_LABELS_SPOKEN[key]
            if key in career.endorsements:
                how = (
                    "self-paid course"
                    if key in career.purchased_endorsements
                    else "carrier-sponsored"
                )
                items.append(
                    MenuItem(
                        f"{label.capitalize()} endorsement: earned, {how}",
                        lambda lab=label: self.ctx.say(f"You already hold the {lab} endorsement."),
                        help="This endorsement is already on your license.",
                    )
                )
                continue
            cost = ENDORSEMENT_COURSE_COSTS[key]
            items.append(
                MenuItem(
                    f"{label.capitalize()} course: {cost:,.0f} dollars "
                    f"(carrier-sponsored free at level {level})",
                    lambda k=key: self._buy(k),
                    help=f"Pay for the {label} training and testing now to "
                    f"unlock that freight before level {level}.",
                )
            )
        items.append(MenuItem("Back", self.go_back, help="Return to the terminal menu."))
        return items

    def _buy(self, key: str) -> None:
        p = self.ctx.profile
        label = ENDORSEMENT_LABELS_SPOKEN[key]
        cost = ENDORSEMENT_COURSE_COSTS[key]
        if key in p.career.endorsements:
            self.ctx.say(f"You already hold the {label} endorsement.")
            return
        if p.money < cost:
            self.ctx.audio.play("ui/error")
            self.ctx.say(
                f"The {label} course costs {cost:,.0f} dollars and you have {p.money:,.0f}."
            )
            return
        p.money -= cost
        p.career.purchased_endorsements.append(key)
        p.dispatch_board_cache = None
        self.ctx.save_profile()
        self.ctx.audio.play("ui/cash")
        self.ctx.say(
            f"Course complete: you paid {cost:,.0f} dollars and earned the "
            f"{label} endorsement. Matching freight is unlocked on the "
            f"dispatch board. You have {p.money:,.0f} dollars left."
        )
        self.refresh()
