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
