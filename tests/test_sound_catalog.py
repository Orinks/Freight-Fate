"""The learn-sounds catalog: every entry plays something real and says what it means."""

import ast
import re
from functools import cache
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


@cache
def _generated_keys() -> frozenset[str]:
    """Sound keys the game synthesizes at runtime instead of shipping a file.

    They resolve to nothing on disk and to nothing in the pack, so a scan
    that only looks at files cannot see them at all -- which is exactly how
    the enforcement signature reached players uncatalogued. Registering is
    idempotent, so asking here costs one synthesis for the whole session.
    """
    from freight_fate.audio import generated_sound_keys
    from freight_fate.states.driving_siren import register_enforcement_sounds

    register_enforcement_sounds()
    return frozenset(generated_sound_keys())


def _resolves(key: str) -> bool:
    """Whether ``key`` resolves the way the game resolves it: synthesized
    cues, then the builder's loose tree, then the committed pack."""
    from asset_helpers import asset_exists

    return key in _generated_keys() or asset_exists(SOUNDS_ROOT, key)


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


# Entries where the side is a property of the truck's position, not of the
# event: whichever side of the lane you are on, or whichever side a police
# vehicle went by on, both are ordinary. Demoing one of them teaches half the
# cue. Turn left, turn right and the siren are deliberately NOT here -- their
# side IS the information.
BOTH_SIDES_ENTRIES = (
    "The road lean",
    "Rumble strip, clipped",
    "Rumble strip",
    "Off the pavement",
    "Lane line crossed",
    "Lane locator",
    "Curve chime",
    "Signal tone",
    "Police car going by",
)


def test_directional_entries_demo_both_sides():
    by_name = {e.name: e for e in sound_catalog.catalog_entries()}
    for name in BOTH_SIDES_ENTRIES:
        pans = sorted(cue.pan for cue in by_name[name].plays)
        assert pans[0] < 0 < pans[-1], f"{name} must demo left and right"


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


def test_the_scan_sees_a_cue_the_game_synthesizes_rather_than_ships():
    """The completeness gate has to cover generated cues too.

    ``enforcement/signature`` is built at runtime and published under an
    ordinary key. It has no file anywhere, so a scan that kept only literals
    resolving to a file dropped it silently -- the gate reported coverage it
    did not have, which is worse than no gate.
    """
    from asset_helpers import asset_exists

    from freight_fate.states.driving_siren import SIGNATURE_KEY

    assert not asset_exists(SOUNDS_ROOT, SIGNATURE_KEY), (
        "this cue now ships as a file, so it no longer pins the generated-cue case"
    )
    assert _resolves(SIGNATURE_KEY), "a synthesized cue must count as resolving"
    assert SIGNATURE_KEY in _referenced_keys(), "the scan must see synthesized cues"
    assert SIGNATURE_KEY in sound_catalog.catalog_keys()


# Entries whose cue a setting can silence, delay or change the meaning of.
# Nothing in the data says so -- the gating lives at the call site -- so this
# list is kept by hand: catalogue a cue that a setting governs, and add its
# name here in the same change.
SETTINGS_GATED_ENTRIES = (
    "The road lean",
    "Rumble strip, clipped",
    "Rumble strip",
    "Off the pavement",
    "Back in the lane",
    "Lane locator",
    "Curve chime",
    "Overspeed chime",
    "Gear grind",
    "Police car going by",
)


def test_every_settings_gated_entry_says_when_it_sounds():
    by_name = {e.name: e for e in sound_catalog.catalog_entries()}
    for name in SETTINGS_GATED_ENTRIES:
        entry = by_name.get(name)
        assert entry is not None, f"{name} is no longer in the catalog; fix this list"
        assert entry.when.strip(), (
            f"{name} only sounds under some settings, so it must say which. "
            "A player told a cue means one thing, whose settings mean it means "
            "another, has been taught something false."
        )


def test_the_enforcement_entries_match_what_the_road_plays():
    """The warning and the pass are different cues and must stay so.

    The catalog once taught the pass as the thing "heard before it can see
    you". It is not: it fires a twentieth of a mile PAST the post. The cue
    that arrives first is the marker, and these two entries are only worth
    having if each keeps the recipe of the thing it names.
    """
    from freight_fate.states.driving_enforcement import PASS_BASE_VOLUME, PASS_PAN
    from freight_fate.states.driving_siren import PASS_MARKER_LEAD_S, SIGNATURE_KEY

    enforcement = next(c for c in sound_catalog.CATALOG if c.name == "Enforcement")
    by_name = {e.name: e for e in enforcement.entries}

    marker = by_name["Enforcement marker"]
    assert [cue.key for cue in marker.plays] == [SIGNATURE_KEY]
    assert marker.plays[0].volume == 0.75, "the marker's own level in _play_enforcement_marker"
    assert marker.plays[0].pan == 0.0, "the pre-post marker is centered"

    passing = by_name["Police car going by"]
    assert len(passing.plays) % 2 == 0, "the pass is marker-then-vehicle pairs"
    for lead, behind in zip(passing.plays[::2], passing.plays[1::2], strict=True):
        assert lead.key == SIGNATURE_KEY, "the marker leads the whoosh, never the other way"
        assert behind.key == "traffic/trooper_pass"
        assert round(behind.delay_s - lead.delay_s, 3) == PASS_MARKER_LEAD_S
        assert lead.pan == behind.pan, "both halves of one pass come from one side"
        assert abs(lead.pan) == PASS_PAN
        assert lead.volume == behind.volume == PASS_BASE_VOLUME


def test_the_jake_ring_is_catalogued_by_hand():
    # Built by f-string at the call site, so the scanner above cannot see it.
    # Catalogued explicitly, which is why this asserts rather than trusts.
    assert any(k.startswith("engine/jake_") for k in sound_catalog.catalog_keys())


def test_every_entry_name_is_an_ontology_noun():
    ontology = (Path(__file__).parents[1] / "docs" / "ontology.md").read_text(encoding="utf-8")
    # Only the Spoken vocabulary table counts as a real row: a name that only
    # turns up as a substring of a class name, a file path, or a sentence
    # elsewhere in the file is a coincidence, not a documented noun.
    start = ontology.index("## Spoken vocabulary")
    end = ontology.find("\n## ", start)
    vocabulary = ontology[start:] if end == -1 else ontology[start:end]
    missing = [e.name for e in sound_catalog.catalog_entries() if e.name not in vocabulary]
    assert not missing, (
        "these entry names have no row in the Spoken vocabulary table of "
        "docs/ontology.md: " + ", ".join(missing) + ". Add a row for each, in this change."
    )


def test_descriptions_stay_player_facing():
    banned = ("src/", ".py", "CH_", "audio.play", "TODO", "FIXME", "changelog", "pytest")
    for entry in sound_catalog.catalog_entries():
        text = f"{entry.meaning} {entry.when}"
        for word in banned:
            assert word not in text, f"{entry.name} says {word!r} to the player"


def test_the_help_reader_points_at_the_screen():
    from freight_fate.states.main_menu_help import HELP_PAGES

    joined = " ".join(line for _title, lines in HELP_PAGES for line in lines)
    assert "Learn game sounds" in joined


def test_the_changelog_records_the_feature():
    text = (Path(__file__).parents[1] / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = text.split("## Unreleased", 1)[1].split("\n## ", 1)[0]
    assert "Learn game sounds" in unreleased


def _entry(name: str):
    return next(e for e in sound_catalog.catalog_entries() if e.name == name)


def test_the_road_lean_is_taught_as_a_cue_you_steer_toward():
    """The lane guide is a pursuit instrument and the rumble strip is not.

    Its target is ``curve_steer - offset`` (sim/lane_guidance), so drifting
    right leans the bed left and following the lean is what recovers the
    lane -- the opposite of the rumble strip, which sounds from the side
    being drifted toward and is steered away from. Prose is the only place
    that difference can live, and getting it backwards would teach a blind
    driver to steer off the road, so it is pinned here rather than trusted.
    """
    lean = _entry("The road lean")
    assert "Steer toward the lean" in lean.meaning
    for rung in ("Rumble strip, clipped", "Rumble strip"):
        assert "away" in _entry(rung).meaning.lower(), (
            f"{rung} must keep telling the player to steer away from it, "
            "or the two opposite conventions blur together"
        )
