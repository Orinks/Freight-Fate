from freight_fate.models.business import INDEPENDENT_AUTHORITY, LEASED_OWNER_OPERATOR
from freight_fate.models.career import LEVEL_XP
from freight_fate.models.career_level_guidance import career_level_guidance
from freight_fate.models.profile import Profile


def _profile(level: int, *, status: str = "company_driver") -> Profile:
    profile = Profile(name="Level Guide", current_city="Chicago")
    profile.career.xp = LEVEL_XP[level - 1]
    profile.career.deliveries = 12
    profile.career.reputation = 82
    profile.business_status = status
    if status != "company_driver":
        profile.owned_trucks = ["rig"]
        profile.money = 80_000.0
    return profile


def test_company_level_guidance_moves_from_regional_to_senior_to_business_prep():
    regional = career_level_guidance(_profile(4))
    assert regional.title == "Build a regional service record"
    assert "broader company lanes" in regional.terminal_text
    assert regional.recommendation == "reputation-building lane"

    senior = career_level_guidance(_profile(10))
    assert senior.title == "Run like a senior company driver"
    assert "premium" in senior.dispatch_text
    assert senior.recommendation == "senior company lane"

    prep = career_level_guidance(_profile(14))
    assert prep.title == "Prepare for owner-operator risk"
    assert "cash cushion" in prep.terminal_text
    assert prep.recommendation == "business-prep load"


def test_owner_operator_guidance_tracks_margin_authority_and_independence():
    leased = career_level_guidance(_profile(18, status=LEASED_OWNER_OPERATOR))
    assert leased.title == "Protect owner-operator margin"
    assert "reserve" in leased.dispatch_text
    assert leased.recommendation == "reserve-safe owner-operator freight"

    authority_prep = career_level_guidance(_profile(22, status=LEASED_OWNER_OPERATOR))
    assert authority_prep.title == "Build authority readiness"
    assert "trailer strategy" in authority_prep.terminal_text
    assert authority_prep.recommendation == "authority-readiness lane"

    independent = career_level_guidance(_profile(27, status=INDEPENDENT_AUTHORITY))
    assert independent.title == "Grow a freight business"
    assert "direct freight" in independent.dispatch_text
    assert independent.recommendation == "direct freight with margin"


def test_high_level_company_bands_do_not_overstate_business_status():
    owner_ready = career_level_guidance(_profile(18))
    assert owner_ready.title == "Protect owner-operator readiness"
    assert "practice" in owner_ready.terminal_text
    assert owner_ready.recommendation == "reserve-building freight"

    authority_ready = career_level_guidance(_profile(22))
    assert authority_ready.title == "Build authority readiness"
    assert "before authority is real" in authority_ready.terminal_text
    assert authority_ready.recommendation == "authority-readiness lane"

    high_level_company = career_level_guidance(_profile(25))
    assert high_level_company.title == "Plan the next business step"
    assert "direct freight" not in high_level_company.dispatch_text
    assert high_level_company.recommendation == "business-decision lane"

    leased_without_authority = career_level_guidance(_profile(27, status=LEASED_OWNER_OPERATOR))
    assert leased_without_authority.title == "Build authority readiness"
    assert "Use authority" not in leased_without_authority.terminal_text
    assert leased_without_authority.recommendation == "authority-readiness lane"

    early_independent = career_level_guidance(_profile(22, status=INDEPENDENT_AUTHORITY))
    assert early_independent.title == "Prove independent authority"
    assert early_independent.recommendation == "authority-building freight"


def test_level_30_guidance_is_distinct_per_business_path():
    company = career_level_guidance(_profile(30))
    leased = career_level_guidance(_profile(30, status=LEASED_OWNER_OPERATOR))
    authority = career_level_guidance(_profile(30, status=INDEPENDENT_AUTHORITY))

    titles = {company.title, leased.title, authority.title}
    assert len(titles) == 3
    assert company.title != career_level_guidance(_profile(25)).title
    assert (
        authority.title != career_level_guidance(_profile(25, status=INDEPENDENT_AUTHORITY)).title
    )
