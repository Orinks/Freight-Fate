"""Hard profile invariants and their defense-in-depth hook in cloud restore."""

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from freight_fate.cloud_save_integrity import (
    CloudSaveIntegrityError,
    canonical_profile,
    verify_cloud_revision,
)
from freight_fate.models.profile import Profile
from freight_fate.profile_invariants import (
    check_profile_invariants,
    spoken_rejection,
)


def codes(profile: Profile) -> set[str]:
    return {v.code for v in check_profile_invariants(profile)}


def test_fresh_profile_passes_clean():
    assert check_profile_invariants(Profile(name="Honest Norm")) == []


def test_played_profile_passes_clean():
    p = Profile(name="Veteran")
    p.money = 84_000.0
    p.fatigue = 62.0
    p.career.xp = 32_000.0
    p.career.deliveries = 41
    p.career.on_time_deliveries = 39
    p.career.on_time_streak = 12
    p.career.total_miles = 21_500.0
    p.career.total_earnings = 96_000.0
    p.career.purchased_endorsements = ["heavy_haul"]
    p.truck_conditions["rig"] = {
        "tire_wear_pct": 34.0,
        "brake_wear_pct": 12.5,
        "engine_wear_pct": 8.0,
        "damage_pct": 3.0,
        "fuel_gal": 180.0,
        "tire_type": "winter",
        "chains_owned": True,
        "chain_wear_pct": 22.0,
    }
    p.upgrades["engine_tune"] = 1
    assert check_profile_invariants(p) == []


def test_range_edits_are_caught():
    p = Profile(name="Edited")
    p.money = float("nan")
    p.fatigue = -5.0
    p.career.xp = -1.0
    p.career.reputation = 1000.0
    found = codes(p)
    assert {"money", "fatigue", "xp", "reputation"} <= found


def test_counter_relations_are_caught():
    p = Profile(name="Edited")
    p.career.deliveries = 3
    p.career.on_time_deliveries = 9
    p.career.on_time_streak = 40
    assert "on_time_exceeds" in codes(p)
    p2 = Profile(name="Edited")
    p2.career.deliveries = 9
    p2.career.on_time_deliveries = 3
    p2.career.on_time_streak = 7
    assert "streak_exceeds" in codes(p2)


def test_condition_record_edits_are_caught():
    p = Profile(name="Edited")
    p.truck_conditions["rig"] = {
        "tire_wear_pct": -20.0,  # fresher than new
        "fuel_gal": 9_000.0,  # tanker, not a tank
        "tire_type": "slicks",
        "chain_wear_pct": 250.0,
    }
    found = codes(p)
    assert {"condition_range", "fuel_range", "tire_type"} <= found


def test_closed_sets_and_upgrade_tiers_are_caught():
    p = Profile(name="Edited")
    p.business_status = "fleet_emperor"
    p.career.purchased_endorsements = ["rocket_fuel"]
    p.upgrades["engine_tune"] = 99
    p.achievements = ["first_delivery", "first_delivery"]
    found = codes(p)
    assert {"business_status", "endorsement", "upgrade_tier", "achievement_dupes"} <= found


def test_unknown_keys_from_newer_builds_pass():
    # Version tolerance: a newer build's truck, buff, upgrade, or
    # achievement key is not an edit -- values are judged, keys are not.
    p = Profile(name="From The Future")
    p.owned_trucks = ["cabover_classic_2027"]
    p.truck_conditions["cabover_classic_2027"] = {
        "tire_wear_pct": 10.0,
        "fuel_gal": 100.0,
    }
    p.upgrades["chrome_stacks"] = 2
    p.achievements = ["antler_polisher"]
    p.active_buffs = [{"key": "mystery_meat", "label": "Mystery meat", "expires_h": 4.0}]
    assert check_profile_invariants(p) == []


def test_spoken_rejection_is_plain_language():
    p = Profile(name="Edited")
    p.career.reputation = 555.0
    text = spoken_rejection(check_profile_invariants(p))
    assert text.startswith("This profile fails the game's integrity checks")
    assert "Reputation" in text
    assert "0 to" not in text.split("First problem:")[0]  # no jargon before the reason


# -- the defense-in-depth hook in verify_cloud_revision ------------------------

KEY_ID = "invariant-test"
PRIVATE_KEY = Ed25519PrivateKey.generate()
PUBLIC_KEYS = {
    KEY_ID: PRIVATE_KEY.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
}


def signed_envelope(payload: dict) -> dict:
    signature = PRIVATE_KEY.sign(canonical_profile(payload))
    return {
        "keyId": KEY_ID,
        "validatorVersion": 1,
        "sig": base64.b64encode(signature).decode("ascii"),
        "signedAt": "2026-07-13T00:00:00Z",
    }


def test_signed_honest_payload_restores():
    payload = Profile(name="Honest Norm").to_dict()
    profile = verify_cloud_revision(payload, signed_envelope(payload), public_keys=PUBLIC_KEYS)
    assert profile.name == "Honest Norm"


def test_signed_but_impossible_payload_is_refused():
    # A valid signature is not a pardon: a payload blessed by an older or
    # compromised validator still has to obey the invariants.
    p = Profile(name="Signed Cheater")
    p.money = 500_000_000_000.0
    payload = p.to_dict()
    with pytest.raises(CloudSaveIntegrityError) as caught:
        verify_cloud_revision(payload, signed_envelope(payload), public_keys=PUBLIC_KEYS)
    assert caught.value.code == "invalid_profile"
    assert "integrity checks" in str(caught.value)
