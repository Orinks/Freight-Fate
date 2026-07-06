"""City slug keys, the composed spoken layer, and legacy-save aliases.

The slug migration separated city identity (``jackson_ms_us``) from speech
("Jackson" / "Jackson, Mississippi"). These tests pin the three contracts it
introduced: keys are well-formed and unique, spoken names compose from the
geo lookup and never leak a slug, and everything a pre-slug save persisted
(bare city names, "City, State" names, facility ids) still resolves.
"""

from __future__ import annotations

import re

from freight_fate.data.legacy_aliases import LEGACY_CITY_SLUGS

SLUG_PATTERN = re.compile(r"^[a-z0-9_]+_[a-z]{2}_[a-z]{2}$")


def test_every_city_key_is_a_well_formed_slug(world):
    for key, city in world.cities.items():
        assert SLUG_PATTERN.match(key), f"malformed city key {key!r}"
        assert city.key == key
        assert key.endswith(f"_{city.state_code.lower()}_{city.country.lower()}")


def test_spoken_layer_composes_from_geo_codes(world):
    jackson = world.cities["jackson_ms_us"]
    assert jackson.name == "Jackson"
    assert jackson.state == "Mississippi"
    assert jackson.state_code == "MS"
    assert jackson.country == "US"
    assert jackson.country_name == "United States"
    assert jackson.spoken_qualified == "Jackson, Mississippi"


def test_spoken_city_never_speaks_a_slug(world):
    for key in world.cities:
        spoken = world.spoken_city(key)
        assert spoken != key
        assert "_" not in spoken


def test_ambiguous_spoken_names_auto_qualify(world):
    # Two Jacksons share a bare spoken name, so both qualify by default.
    assert world.spoken_city("jackson_ms_us") == "Jackson, Mississippi"
    assert world.spoken_city("jackson_mi_us") == "Jackson, Michigan"
    # A unique name stays bare unless qualification is asked for.
    assert world.spoken_city("chicago_il_us") == "Chicago"
    assert world.spoken_city("chicago_il_us", qualified=True) == "Chicago, Illinois"
    assert world.spoken_city("jackson_ms_us", qualified=False) == "Jackson"


def test_spoken_city_passes_legacy_and_unknown_text_through(world):
    # A legacy display name resolves to its city's spoken form.
    assert world.spoken_city("Chicago") == "Chicago"
    assert world.spoken_city("Jackson, Michigan") == "Jackson, Michigan"
    # Unknown text comes back unchanged -- it is already the best speakable form.
    assert world.spoken_city("Atlantis") == "Atlantis"


def test_every_legacy_name_resolves_to_a_live_city(world):
    for old_name, slug in LEGACY_CITY_SLUGS.items():
        assert slug in world.cities, f"{old_name!r} aliases missing city {slug!r}"
        assert world.resolve_city_key(old_name) == slug


def test_frozen_legacy_map_wins_name_collisions(world):
    # Bare "Jackson" belonged to Jackson MS before Jackson MI joined the map;
    # old saves that say "Jackson" must keep meaning Mississippi forever.
    assert world.resolve_city_key("Jackson") == "jackson_ms_us"


def test_qualified_city_state_forms_resolve(world):
    assert world.resolve_city_key("Jackson, Mississippi") == "jackson_ms_us"
    assert world.resolve_city_key("Jackson, MS") == "jackson_ms_us"
    assert world.resolve_city_key("Springfield, Illinois") == "springfield_il_us"


def test_legacy_facility_ids_still_resolve(world):
    # Pre-slug facility ids embedded a slug of the display name
    # ("chicago:cross_dock:..."). Every location must stay reachable through
    # its old id, including template facilities of comma-disambiguated cities
    # whose names embedded the old display name too.
    chicago = world.cities["chicago_il_us"]
    for location in chicago.locations:
        old_id = "chicago:" + location.id.split(":", 1)[1]
        assert world.facility_by_id(old_id).id == location.id
        assert world.facility_location("Chicago", old_id).id == location.id

    jackson_mi = world.cities["jackson_mi_us"]
    template = next(loc for loc in jackson_mi.locations if loc.template)
    old_name = template.name.replace("Jackson", "Jackson, Michigan")
    old_suffix = template.id.split(":", 2)
    old_id = f"jackson-michigan:{old_suffix[1]}:{_legacy_slug(old_name)}"
    assert world.facility_by_id(old_id).id == template.id
    assert world.facility_location("Jackson, Michigan", old_name).id == template.id


def test_legacy_market_names_fall_back_to_default_facility(world):
    # Old jobs that only named the whole-city market keep resolving, under
    # both the current spoken name and the pre-slug display name.
    default = world.default_facility("jackson_mi_us")
    assert world.facility_location("jackson_mi_us", "Jackson freight market").id == default.id
    assert (
        world.facility_location("Jackson, Michigan", "Jackson, Michigan freight market").id
        == default.id
    )


def test_geo_lookup_covers_every_state_code_in_use(world):
    for city in world.cities.values():
        assert city.state_code, f"{city.key} has no state code"
        assert city.state and city.state != city.state_code, (
            f"{city.key} state code {city.state_code!r} did not resolve to a spoken name"
        )


def _legacy_slug(text: str) -> str:
    """The pre-slug facility-id slug: lowercase, non-alphanumerics to dashes."""
    out: list[str] = []
    pending = False
    for char in text.lower():
        if char.isalnum():
            if pending and out:
                out.append("-")
            out.append(char)
            pending = False
        else:
            pending = True
    return "".join(out).strip("-")
