"""Reusable career-stage presets for transcript-backed playtests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from freight_fate.models.business import (
    COMPANY_DRIVER,
    INDEPENDENT_AUTHORITY,
    LEASED_OWNER_OPERATOR,
)
from freight_fate.models.career import LEVEL_XP


@dataclass(frozen=True)
class CareerStagePreset:
    key: str
    level: int
    deliveries: int
    reputation: float
    business_status: str = COMPANY_DRIVER
    authority_readiness: bool = False
    owned_trucks: tuple[str, ...] = ()
    owned_trailers: tuple[str, ...] = ()

    def configure(self, profile) -> None:
        profile.achievements.append("first_dispatch")
        profile.career.xp = LEVEL_XP[self.level - 1]
        profile.career.deliveries = self.deliveries
        profile.career.reputation = self.reputation
        profile.business_status = self.business_status
        profile.authority_readiness = self.authority_readiness
        profile.owned_trucks = list(self.owned_trucks)
        profile.owned_trailers = list(self.owned_trailers)
        if self.business_status != COMPANY_DRIVER:
            profile.trailer_programs = ["dry_van", "reefer", "flatbed", "bulk"]


CAREER_STAGES = {
    preset.key: preset
    for preset in (
        CareerStagePreset("new_hire", 1, 0, 50),
        # Company fleet bands: dispatch assigns better tractors with seniority.
        CareerStagePreset("regional_fleet_driver", 6, 12, 70),
        CareerStagePreset("trusted_company_driver", 10, 20, 86),
        CareerStagePreset("premium_fleet_driver", 13, 30, 90),
        CareerStagePreset("first_pick_driver", 17, 45, 95),
        CareerStagePreset(
            "owner_operator", 18, 35, 80, LEASED_OWNER_OPERATOR, owned_trucks=("rig",)
        ),
        CareerStagePreset(
            "own_authority", 27, 80, 92, INDEPENDENT_AUTHORITY, True, ("rig",), ("reefer",)
        ),
        CareerStagePreset(
            "trailer_fleet",
            30,
            150,
            98,
            INDEPENDENT_AUTHORITY,
            True,
            ("rig", "heavy_hauler"),
            ("dry_van", "reefer", "flatbed", "bulk"),
        ),
    )
}


def career_stage(key: str) -> Callable:
    return CAREER_STAGES[key].configure
