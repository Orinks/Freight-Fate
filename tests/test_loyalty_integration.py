"""Loyalty system integration tests."""

from freight_fate.models.loyalty import LoyaltyAccount
from freight_fate.models.profile import Profile


def test_profile_has_loyalty_account():
    """Test that new profiles have a loyalty account."""
    profile = Profile()
    assert hasattr(profile, "loyalty")
    assert isinstance(profile.loyalty, LoyaltyAccount)
    assert profile.loyalty.total_points == 0.0
    assert profile.loyalty.shower_credits == 0


def test_profile_serialization_includes_loyalty():
    """Test that loyalty data is included in profile serialization."""
    profile = Profile()
    profile.loyalty.add_fueling(50.0, stop_name="Pilot Travel Center", location="Springfield, IL")

    data = profile.to_dict()
    assert "loyalty" in data
    assert data["loyalty"]["total_points"] == 50.0
    assert data["loyalty"]["shower_credits"] == 1


def test_profile_deserialization_restores_loyalty():
    """Test that loyalty data is restored from profile serialization."""
    profile = Profile()
    profile.loyalty.add_fueling(75.0, stop_name="Flying J Travel Center", location="Columbus, OH")

    data = profile.to_dict()
    restored = Profile.from_dict(data)

    assert restored.loyalty.total_points == 75.0
    assert restored.loyalty.shower_credits == 1
    assert restored.loyalty.total_gallons_fueled == 75.0


def test_profile_from_dict_without_loyalty():
    """Test that profiles without loyalty data get a fresh account."""
    data = {
        "name": "Test Driver",
        "money": 5000.0,
        "current_city": "chicago_il_us",
        "version": 11,
        "_signature": "test",
        "_signature_version": 2,
    }

    profile = Profile.from_dict(data)
    assert hasattr(profile, "loyalty")
    assert isinstance(profile.loyalty, LoyaltyAccount)
    assert profile.loyalty.total_points == 0.0


def test_loyalty_persists_across_saves():
    """Test that loyalty data persists through save/load cycles."""
    profile = Profile()
    profile.loyalty.add_fueling(100.0, stop_name="Love's Travel Stop", location="Atlanta, GA")

    # Serialize and deserialize
    data = profile.to_dict()
    restored = Profile.from_dict(data)

    assert restored.loyalty.total_points == 100.0
    assert restored.loyalty.shower_credits == 1  # 100 gallons = 1 shower credit (50+ threshold)
    assert len(restored.loyalty.fueling_history) == 1
