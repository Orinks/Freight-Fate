"""The learn-sounds catalog: every entry plays something real and says what it means."""

import ast
import re
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


SRC = Path(__file__).parents[1] / "src" / "freight_fate"

# What a sound key looks like: one folder, one name, lowercase.
KEY_SHAPE = re.compile(r"^[a-z][a-z0-9_]*/[a-z0-9_]+$")


def _referenced_keys() -> set[str]:
    """Every string literal in src/ that names a real sound asset.

    Deliberately not "every argument to audio.play". Most event cues are
    returned as strings from a helper and played through a variable further
    down (``driving_core`` alone returns a dozen), so scanning call arguments
    would quietly miss the majority of them -- and a completeness gate with a
    hole in it is worse than none, because it reads as coverage.

    Any literal shaped like a key AND resolving to a real asset is a sound the
    game can make. Keys assembled at runtime (the jake ring's f-string) cannot
    be read statically; those cues are catalogued by hand.
    """
    keys: set[str] = set()
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            value = node.value
            if KEY_SHAPE.match(value) and _resolves(value):
                keys.add(value)
    return keys


def test_every_playable_cue_is_taught_or_explicitly_excluded():
    missing = sorted(
        key
        for key in _referenced_keys()
        if key not in sound_catalog.catalog_keys() and not sound_catalog.is_excluded(key)
    )
    assert not missing, (
        "these cues are played in the game but neither catalogued nor excluded: "
        + ", ".join(missing)
        + ". Add a SoundEntry, or add the key to SELF_EXPLANATORY with a reason."
    )


def test_every_exclusion_carries_a_reason():
    for key, reason in sound_catalog.SELF_EXPLANATORY.items():
        assert reason.strip(), f"{key} is excluded with no reason given"


def test_nothing_is_both_taught_and_excluded():
    both = sorted(k for k in sound_catalog.catalog_keys() if sound_catalog.is_excluded(k))
    assert not both, f"catalogued and excluded at once: {both}"


def test_the_jake_ring_is_catalogued_by_hand():
    # Built by f-string at the call site, so the scanner above cannot see it.
    # Catalogued explicitly, which is why this asserts rather than trusts.
    assert any(k.startswith("engine/jake_") for k in sound_catalog.catalog_keys())


def test_every_entry_name_is_an_ontology_noun():
    ontology = (Path(__file__).parents[1] / "docs" / "ontology.md").read_text(encoding="utf-8")
    missing = [e.name for e in sound_catalog.catalog_entries() if e.name not in ontology]
    assert not missing, (
        "these entry names are not in docs/ontology.md: "
        + ", ".join(missing)
        + ". Add a row for each, in this change."
    )


def test_descriptions_stay_player_facing():
    banned = ("src/", ".py", "CH_", "audio.play", "TODO", "FIXME", "changelog", "pytest")
    for entry in sound_catalog.catalog_entries():
        text = f"{entry.meaning} {entry.when}"
        for word in banned:
            assert word not in text, f"{entry.name} says {word!r} to the player"
