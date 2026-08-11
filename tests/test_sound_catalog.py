"""The learn-sounds catalog: every entry plays something real and says what it means."""

from pathlib import Path

from freight_fate import sound_catalog


def test_catalog_has_categories_with_entries():
    assert sound_catalog.CATALOG, "the catalog is empty"
    for category in sound_catalog.CATALOG:
        assert category.name, "a category has no name"
        assert category.entries, f"{category.name} has no entries"


def test_every_entry_names_itself_plays_something_and_explains_itself():
    for entry in sound_catalog.catalog_entries():
        assert entry.name.strip(), "an entry has no name"
        assert entry.plays, f"{entry.name} plays nothing"
        assert entry.meaning.strip(), f"{entry.name} has no meaning text"


SOUNDS_ROOT = Path(__file__).parents[1] / "src" / "freight_fate" / "assets" / "sounds"


def _resolves(key: str) -> bool:
    """Whether ``key`` resolves the way the game resolves it: the builder's
    loose tree first, then the committed pack."""
    from asset_helpers import asset_exists

    return asset_exists(SOUNDS_ROOT, key)


def test_every_catalogued_key_resolves_to_a_real_asset():
    for entry in sound_catalog.catalog_entries():
        for cue in entry.plays:
            resolved = _resolves(cue.key) or (cue.fallback and _resolves(cue.fallback))
            assert resolved, f"{entry.name} plays {cue.key}, which resolves to nothing"


def test_lane_category_teaches_the_edge_ladder_in_order():
    lane = next(c for c in sound_catalog.CATALOG if c.name == "Lane and steering")
    names = [e.name for e in lane.entries]
    assert names.index("Rumble strip, clipped") < names.index("Rumble strip")
    assert names.index("Rumble strip") < names.index("Off the pavement")


def test_directional_entries_demo_both_sides():
    lane = next(c for c in sound_catalog.CATALOG if c.name == "Lane and steering")
    locator = next(e for e in lane.entries if e.name == "Lane locator")
    pans = sorted(cue.pan for cue in locator.plays)
    assert pans[0] < 0 < pans[-1], "a directional entry must demo left and right"


EXPECTED_CATEGORIES = (
    "Lane and steering",
    "Air and brakes",
    "Engine brake, speed and shifting",
    "Ramps and stop bars",
    "Hazards and the road",
    "Enforcement",
    "The load",
)


def test_all_seven_categories_are_present_in_order():
    assert [c.name for c in sound_catalog.CATALOG] == list(EXPECTED_CATEGORIES)


def test_no_entry_name_repeats_across_the_catalog():
    names = [e.name for e in sound_catalog.catalog_entries()]
    assert len(names) == len(set(names)), "two entries share a name"


def test_held_cues_declare_a_duration_and_one_shots_do_not_linger():
    for entry in sound_catalog.catalog_entries():
        for cue in entry.plays:
            assert cue.hold_s >= 0.0
            assert cue.hold_s <= 6.0, f"{entry.name} holds {cue.key} too long"


def test_the_emergency_brake_entry_declares_a_fallback():
    # vehicle/ebrake ships only in the licensed overlay; a clean clone must
    # still hear something rather than learning that the cue is silent.
    entry = next(e for e in sound_catalog.catalog_entries() if e.name == "Emergency brake")
    cue = entry.plays[0]
    assert cue.key == "vehicle/ebrake"
    assert cue.fallback == "vehicle/brake_air"
