"""Truck stop loyalty programs: points, rewards, and redemption."""

from freight_fate.models.loyalty import (
    LoyaltyAccount,
    loyalty_earnings_text,
    reward_cost_text,
)


def test_new_account_starts_empty():
    """Test that a new loyalty account starts with zero points and credits."""
    account = LoyaltyAccount()
    assert account.total_points == 0.0
    assert account.total_gallons_fueled == 0.0
    assert account.shower_credits == 0
    assert account.brand_points == {}
    assert account.fueling_history == []


def test_fueling_awards_points():
    """Test that fueling awards loyalty points at the correct rate."""
    account = LoyaltyAccount()
    result = account.add_fueling(50.0, stop_name="Pilot Travel Center")

    assert result["points_earned"] == 50.0  # 1 point per gallon for travel centers
    assert account.total_points == 50.0
    assert account.total_gallons_fueled == 50.0


def test_landmark_brand_awards_bonus_points():
    """Test that landmark brands award 1.5 points per gallon."""
    account = LoyaltyAccount()
    result = account.add_fueling(50.0, stop_name="Big Buck's Travel Center")

    assert result["points_earned"] == 75.0  # 1.5 points per gallon for landmarks
    assert account.total_points == 75.0


def test_generic_stop_awards_half_points():
    """Test that unbranded stops award 0.5 points per gallon."""
    account = LoyaltyAccount()
    result = account.add_fueling(50.0, stop_name="Downtown Fuel Mart")

    assert result["points_earned"] == 25.0  # 0.5 points per gallon for generic
    assert account.total_points == 25.0


def test_shower_credit_at_threshold():
    """Test that fueling 50+ gallons awards a shower credit."""
    account = LoyaltyAccount()
    result = account.add_fueling(50.0, stop_name="Pilot Travel Center")

    assert "shower_credit" in result["rewards"]
    assert account.shower_credits == 1


def test_no_shower_credit_below_threshold():
    """Test that fueling below 50 gallons does not award a shower credit."""
    account = LoyaltyAccount()
    result = account.add_fueling(49.0, stop_name="Pilot Travel Center")

    assert "shower_credit" not in result["rewards"]
    assert account.shower_credits == 0


def test_multiple_shower_credits():
    """Test that multiple fueling sessions accumulate shower credits."""
    account = LoyaltyAccount()
    account.add_fueling(50.0, stop_name="Pilot Travel Center")
    account.add_fueling(60.0, stop_name="Flying J Travel Center")

    assert account.shower_credits == 2


def test_brand_specific_points_tracking():
    """Test that points are tracked per brand."""
    account = LoyaltyAccount()
    account.add_fueling(50.0, stop_name="Pilot Travel Center")
    account.add_fueling(30.0, stop_name="Love's Travel Stop")

    assert account.brand_points["pilot"] == 50.0
    assert account.brand_points["loves"] == 30.0


def test_fueling_history_recorded():
    """Test that fueling sessions are recorded in history."""
    account = LoyaltyAccount()
    account.add_fueling(50.0, stop_name="Pilot Travel Center", location="Springfield, IL")

    assert len(account.fueling_history) == 1
    entry = account.fueling_history[0]
    assert entry["gallons"] == 50.0
    assert entry["brand_key"] == "pilot"  # Should be detected from stop name
    assert entry["stop_name"] == "Pilot Travel Center"
    assert entry["location"] == "Springfield, IL"


def test_can_redeem_checks_point_balance():
    """Test that redemption checks point balance correctly."""
    account = LoyaltyAccount()
    account.add_fueling(50.0, stop_name="Pilot Travel Center")

    assert account.can_redeem("shower")  # 50 points needed, have 50
    assert account.can_redeem("parking")  # 30 points needed, have 50
    assert account.can_redeem("food")  # 25 points needed, have 50


def test_redeem_reward_deducts_points():
    """Test that redeeming a reward deducts points correctly."""
    account = LoyaltyAccount()
    account.add_fueling(50.0, stop_name="Pilot Travel Center")

    result = account.redeem_reward("shower")
    assert result["success"]
    assert result["points_spent"] == 50
    assert account.total_points == 0.0


def test_redeem_insufficient_points_fails():
    """Test that redeeming without enough points fails."""
    account = LoyaltyAccount()
    account.add_fueling(20.0, stop_name="Independent Truck Stop")  # Generic stop = 0.5 rate

    result = account.redeem_reward("shower")
    assert not result["success"]
    assert result["reason"] == "insufficient_points"
    assert account.total_points == 10.0  # Points unchanged (20 * 0.5)


def test_use_shower_credit():
    """Test that using a shower credit reduces the count."""
    account = LoyaltyAccount()
    account.add_fueling(50.0, stop_name="Pilot Travel Center")

    assert account.use_shower_credit()
    assert account.shower_credits == 0

    # Second use fails
    assert not account.use_shower_credit()


def test_loyalty_summary_text():
    """Test that loyalty summary generates readable text."""
    account = LoyaltyAccount()
    account.add_fueling(50.0, stop_name="Pilot Travel Center")

    summary = account.summary()
    # Check the actual structure
    assert "Loyalty points:" in summary
    assert "Total gallons fueled:" in summary
    assert "Shower credits available:" in summary
    # Check values are present
    assert "50" in summary  # Points and gallons
    assert "1" in summary  # Shower credits


def test_loyalty_earnings_text():
    """Test that earnings text is readable and informative."""
    text = loyalty_earnings_text(50.0, 50.0, ["shower_credit"])
    assert "50 gallons fueled" in text
    assert "50 loyalty points earned" in text
    assert "shower credit earned" in text


def test_loyalty_earnings_text_no_rewards():
    """Test earnings text when no rewards are earned."""
    text = loyalty_earnings_text(30.0, 30.0, [])
    assert "30 gallons fueled" in text
    assert "30 loyalty points earned" in text
    assert "shower credit" not in text


def test_reward_cost_text():
    """Test that reward cost text is readable."""
    text = reward_cost_text("shower")
    assert "free shower" in text
    assert "50 loyalty points" in text


def test_zero_gallons_no_points():
    """Test that fueling zero gallons awards no points."""
    account = LoyaltyAccount()
    result = account.add_fueling(0.0, stop_name="Pilot Travel Center")

    assert result["points_earned"] == 0
    assert account.total_points == 0.0


def test_negative_gallons_no_points():
    """Test that negative gallons (error case) awards no points."""
    account = LoyaltyAccount()
    result = account.add_fueling(-10.0, stop_name="Pilot Travel Center")

    assert result["points_earned"] == 0
    assert account.total_points == 0.0


def test_realistic_fueling_scenario():
    """Test a realistic scenario: multiple stops, strategic fueling."""
    account = LoyaltyAccount()

    # Fuel at Pilot (travel center) - good rate
    result1 = account.add_fueling(75.0, stop_name="Pilot Travel Center")
    assert result1["points_earned"] == 75.0
    assert account.shower_credits == 1

    # Fuel at generic stop - lower rate but necessary
    result2 = account.add_fueling(40.0, stop_name="Independent Truck Stop")
    assert result2["points_earned"] == 20.0  # 0.5 rate
    assert account.shower_credits == 1  # No change (below threshold)

    # Fuel at Big Buck's (landmark) - bonus rate
    result3 = account.add_fueling(60.0, stop_name="Big Buck's")
    assert result3["points_earned"] == 90.0  # 1.5 rate
    assert account.shower_credits == 2

    # Total points and strategic redemption
    assert account.total_points == 185.0
    assert account.can_redeem("shower")
    assert account.can_redeem("parking")
    assert account.can_redeem("food")

    # Redeem shower
    shower_result = account.redeem_reward("shower")
    assert shower_result["success"]
    assert account.total_points == 135.0  # 185 - 50
