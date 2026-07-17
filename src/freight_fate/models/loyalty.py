"""Truck stop loyalty programs: points, rewards, and redemption.

Real-world truck stop loyalty programs like Pilot Pro Rewards and TA UltraONE
give drivers points per gallon fueled, with redemption options for showers,
parking, food, and other services. This system mimics that behavior for
gameplay depth and strategic fueling decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Point earning rates (points per gallon) by brand tier
POINTS_PER_GALLON = {
    "travel_center": 1.0,  # Major chains like Pilot, TA, Love's
    "landmark": 1.5,  # Premium stops like Big Buck's
    "generic": 0.5,  # Unbranded stops
}

# Points required for rewards
REWARD_COSTS = {
    "shower": 50,  # Points needed for a free shower
    "parking": 30,  # Points needed for parking discount
    "food": 25,  # Points needed for food discount
    "laundry": 40,  # Points needed for laundry discount
}

# Shower credits earned per fueling threshold (gallons)
SHOWER_CREDIT_GALLONS = 50


@dataclass
class LoyaltyAccount:
    """A driver's loyalty program account across all truck stop brands."""

    total_points: float = 0.0
    total_gallons_fueled: float = 0.0
    shower_credits: int = 0
    brand_points: dict[str, float] = field(default_factory=dict)  # Points per brand
    fueling_history: list[dict] = field(default_factory=list)  # Track fueling sessions

    def to_dict(self) -> dict:
        return {
            "total_points": self.total_points,
            "total_gallons_fueled": self.total_gallons_fueled,
            "shower_credits": self.shower_credits,
            "brand_points": self.brand_points,
            "fueling_history": self.fueling_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> LoyaltyAccount:
        if not isinstance(data, dict):
            return cls()
        return cls(
            total_points=float(data.get("total_points", 0.0)),
            total_gallons_fueled=float(data.get("total_gallons_fueled", 0.0)),
            shower_credits=int(data.get("shower_credits", 0)),
            brand_points=dict(data.get("brand_points", {})),
            fueling_history=list(data.get("fueling_history", [])),
        )

    def add_fueling(
        self,
        gallons: float,
        brand_key: str | None = None,
        stop_name: str = "",
        location: str = "",
    ) -> dict:
        """Record a fueling session and award loyalty points.

        Returns a summary of points earned and any rewards unlocked.
        """
        if gallons <= 0:
            return {"points_earned": 0, "rewards": []}

        # Determine point rate based on brand
        rate = POINTS_PER_GALLON.get("generic", 0.5)

        # Try to detect brand from stop name if brand_key not provided
        if not brand_key and stop_name:
            from freight_fate.data.amenities import classify_brand

            brand = classify_brand(stop_name)
            if brand:
                brand_key = brand.key
                rate = POINTS_PER_GALLON.get(brand.tier, POINTS_PER_GALLON["generic"])
        elif brand_key:
            # If brand_key is provided, look up the tier
            from freight_fate.data.amenities import BRANDS

            for brand in BRANDS:
                if brand.key == brand_key:
                    rate = POINTS_PER_GALLON.get(brand.tier, POINTS_PER_GALLON["generic"])
                    break

        points_earned = gallons * rate
        self.total_points += points_earned
        self.total_gallons_fueled += gallons

        # Track brand-specific points
        if brand_key:
            self.brand_points[brand_key] = self.brand_points.get(brand_key, 0.0) + points_earned

        # Check for shower credits
        rewards_unlocked = []
        if gallons >= SHOWER_CREDIT_GALLONS:
            self.shower_credits += 1
            rewards_unlocked.append("shower_credit")

        # Record fueling session
        self.fueling_history.append(
            {
                "gallons": gallons,
                "points_earned": points_earned,
                "brand_key": brand_key,
                "stop_name": stop_name,
                "location": location,
            }
        )

        return {
            "points_earned": points_earned,
            "total_points": self.total_points,
            "rewards": rewards_unlocked,
        }

    def can_redeem(self, reward_type: str) -> bool:
        """Check if the driver has enough points for a reward."""
        cost = REWARD_COSTS.get(reward_type, 0)
        return self.total_points >= cost

    def redeem_reward(self, reward_type: str) -> dict:
        """Redeem points for a reward.

        Returns success status and updated point balance.
        """
        cost = REWARD_COSTS.get(reward_type, 0)
        if not self.can_redeem(reward_type):
            return {
                "success": False,
                "points_remaining": self.total_points,
                "reason": "insufficient_points",
            }

        self.total_points -= cost
        return {
            "success": True,
            "points_remaining": self.total_points,
            "reward_type": reward_type,
            "points_spent": cost,
        }

    def use_shower_credit(self) -> bool:
        """Use a shower credit if available."""
        if self.shower_credits > 0:
            self.shower_credits -= 1
            return True
        return False

    def summary(self) -> str:
        """Generate a spoken summary of loyalty status."""
        return (
            f"Loyalty points: {self.total_points:.0f}. "
            f"Total gallons fueled: {self.total_gallons_fueled:.0f}. "
            f"Shower credits available: {self.shower_credits}."
        )


def loyalty_earnings_text(gallons: float, points_earned: float, rewards: list[str]) -> str:
    """Generate spoken text for loyalty earnings after fueling."""
    parts = [f"{gallons:.0f} gallons fueled"]
    if points_earned > 0:
        parts.append(f"{points_earned:.0f} loyalty points earned")
    if "shower_credit" in rewards:
        parts.append("shower credit earned")
    return ", ".join(parts) + "."


def reward_cost_text(reward_type: str) -> str:
    """Generate spoken text for reward cost."""
    cost = REWARD_COSTS.get(reward_type, 0)
    reward_labels = {
        "shower": "free shower",
        "parking": "parking discount",
        "food": "food discount",
        "laundry": "laundry discount",
    }
    label = reward_labels.get(reward_type, reward_type)
    return f"{label} costs {cost} loyalty points."


__all__ = [
    "POINTS_PER_GALLON",
    "REWARD_COSTS",
    "SHOWER_CREDIT_GALLONS",
    "LoyaltyAccount",
    "loyalty_earnings_text",
    "reward_cost_text",
]
