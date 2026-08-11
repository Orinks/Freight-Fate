# Learn Game Sounds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Learn game sounds screen, reachable from the main menu and the driving pause menu, where a player can play any meaningful road cue on demand and hear what it means.

**Architecture:** A pure data catalog module (`sound_catalog.py`) lists categories of entries; each entry names a cue and carries the recipe for playing it faithfully. A small sequencer (`sound_demo.py`) walks an entry's cues on a timer and guarantees held loops are released. Two `MenuState` subclasses in `states/learn_sounds.py` present category and entry lists; both entry points push the same state.

**Tech Stack:** Python 3.12, pygame, `uv`, pytest. No new dependencies.

Spec: `docs/superpowers/specs/2026-08-10-learn-game-sounds-design.md`.

## Global Constraints

- **Branch:** `feat/career-1.9`. All work lands there, not on `dev`.
- **Commands:** setup `uv sync --group dev`; tests `uv run pytest`; lint `uv run ruff check src tests tools`; byte-compile `uv run python -m compileall src tests tools`.
- **Every spoken string is player-facing.** No maintainer jargon, no CI words, no file keys or channel names in anything the player hears.
- **Canonical nouns only.** Every entry name must be the word `docs/ontology.md` already uses for that concept. A concept with no row gets one in the same change.
- **`sound_catalog.py` imports nothing from pygame, the audio engine, or `states/`.** It is data.
- **Keep practical files at or below 1000 lines.**
- **Changelog gate:** the final task adds a `## Unreleased` entry. Every other commit in this plan carries `[skip changelog]` in its message.
- **Roadmap:** the final task adds the shipped feature to the 1.9 section of `ROADMAP.md`.
- **Headless runs:** `FREIGHT_FATE_NO_SPEECH=1`; `tests/conftest.py` already forces the dummy SDL drivers.

## File Structure

| File | Responsibility |
| --- | --- |
| `src/freight_fate/sound_catalog.py` (create) | `Cue`, `SoundEntry`, `SoundCategory`, the `CATALOG` tuple, `SELF_EXPLANATORY`, and two lookup helpers. Pure data. |
| `src/freight_fate/sound_demo.py` (create) | `SoundDemo`: sequences one entry's cues against an audio engine, releases held loops. No pygame, no state. |
| `src/freight_fate/states/learn_sounds.py` (create) | `LearnSoundsState` (categories) and `LearnSoundCategoryState` (entries + demo driving). |
| `src/freight_fate/states/main_menu.py` (modify) | One `MenuItem` and one handler. |
| `src/freight_fate/states/driving_pause_states.py` (modify) | One `MenuItem` and one handler. |
| `docs/ontology.md` (modify) | Rows for cue concepts that lack one, and for the screen. |
| `tests/test_sound_catalog.py` (create) | Catalog integrity: keys resolve, coverage is complete, names are ontology nouns, copy rules hold. |
| `tests/test_learn_sounds_state.py` (create) | Screen behaviour: arrow, Enter, F1, held-loop release, both entry points. |

---

### Task 1: Catalog types and the Lane and steering category

**Files:**
- Create: `src/freight_fate/sound_catalog.py`
- Test: `tests/test_sound_catalog.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Cue(key, volume, pan, delay_s, hold_s, fallback)`, `SoundEntry(name, plays, meaning, when)`, `SoundCategory(name, entries)`, `CATALOG: tuple[SoundCategory, ...]`, `catalog_entries() -> tuple[SoundEntry, ...]`, `catalog_keys() -> set[str]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_sound_catalog.py`:

```python
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
```

`tests/asset_helpers.py::asset_exists(root, key)` already does the loose-tree-
then-pack lookup. Test helpers are imported bare (`from asset_helpers import
...`), not as `tests.asset_helpers` -- there is no `tests/__init__.py` and
pytest puts `tests/` itself on `sys.path`. Same for `speech_capture` later.
That lookup, which is why the test above wraps it rather than reaching
for the filesystem. No change to that file is needed.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_sound_catalog.py -v
```

Expected: collection error, `ModuleNotFoundError: No module named 'freight_fate.sound_catalog'`.

- [ ] **Step 3: Write the module with its types and the first category**

Create `src/freight_fate/sound_catalog.py`:

```python
"""What every road cue means, as data.

Freight Fate teaches its cues at seventy miles an hour: the first time a
player hears one, something is already happening. That is fine for the engine
and useless for the edge ladder, the stop bar and the jake stages, where the
sound IS the information. This catalog is what the Learn game sounds screen
reads -- one entry per cue that carries a decision, with the recipe for
playing it exactly the way the road plays it.

Rules this file lives by:

* **Pure data.** No pygame, no audio engine, no states. It is imported by the
  screen and by tests, and it must stay cheap and headless.
* **Canonical nouns.** Every ``name`` is the word ``docs/ontology.md`` already
  uses. A catalog that invents a second name for the rumble strip is worse
  than no catalog.
* **Faithful recipes.** Volumes and pans are copied from the call site that
  plays the cue in the drive, so what a player learns here is what they hear
  out there. Panned cues demo both sides, because the side is the point.
* **Every exclusion is on the record.** A cue left out goes in
  ``SELF_EXPLANATORY`` with its reason, and the completeness test in
  ``tests/test_sound_catalog.py`` fails on anything in neither list.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Cue:
    """One sounding inside a demo: what to play, how, and when.

    ``hold_s`` above zero makes this a held loop rather than a one-shot: the
    demo re-asserts it for that many seconds and then releases it. ``delay_s``
    is measured from the start of the whole demo, not from the previous cue.
    """

    key: str
    volume: float = 1.0
    pan: float = 0.0
    delay_s: float = 0.0
    hold_s: float = 0.0
    fallback: str = ""


@dataclass(frozen=True)
class SoundEntry:
    name: str  # the canonical spoken noun, from docs/ontology.md
    plays: tuple[Cue, ...]
    meaning: str  # what it tells you, and what to do about it
    when: str = ""  # the setting or situation that gates it, if any


@dataclass(frozen=True)
class SoundCategory:
    name: str
    entries: tuple[SoundEntry, ...]


# Lane and steering -----------------------------------------------------------
#
# The edge ladder is three structural textures, not one beep getting louder
# (sim/lane_guidance.edge_rung): clipping the strip is intermittent, fully on
# it is periodic, off the pavement is aperiodic gravel. They are catalogued in
# that order so the escalation is learnable as an escalation.

_LANE = SoundCategory(
    "Lane and steering",
    (
        SoundEntry(
            "The road lean",
            (
                Cue("vehicle/road", volume=0.6, pan=-0.8, hold_s=2.0),
                Cue("vehicle/road", volume=0.6, pan=0.8, delay_s=2.4, hold_s=2.0),
            ),
            "Road noise leans toward the side of the lane you are on, and "
            "toward a bend before you reach it. It is the quietest thing in "
            "the cab that tells you where you are; steer back toward the "
            "middle and it settles.",
            when="Lane keeping partial or off. On full, the truck holds the "
            "lane and the road stays centered.",
        ),
        SoundEntry(
            "Rumble strip, clipped",
            (
                Cue("vehicle/edge_clip", volume=0.5, pan=-0.7, hold_s=1.8),
                Cue("vehicle/edge_clip", volume=0.5, pan=0.7, delay_s=2.2, hold_s=1.8),
            ),
            "A tire is just catching the edge line on that side. You are "
            "still in the lane. Steer gently away from it.",
            when="Lane keeping partial or off.",
        ),
        SoundEntry(
            "Rumble strip",
            (
                Cue("vehicle/edge_strip", volume=0.7, pan=-0.7, hold_s=1.8),
                Cue("vehicle/edge_strip", volume=0.7, pan=0.7, delay_s=2.2, hold_s=1.8),
            ),
            "The whole tire is on the rumble strip on that side. Steer away "
            "now: the next rung of this ladder is off the pavement.",
            when="Lane keeping partial or off.",
        ),
        SoundEntry(
            "Off the pavement",
            (Cue("vehicle/edge_shoulder", volume=0.88, pan=-0.7, hold_s=2.0),),
            "Gravel. The truck has left the road surface on that side. Ease "
            "back on: do not yank the wheel, and do not brake hard while a "
            "trailer wheel is still in the dirt.",
            when="Lane keeping partial or off. Past an undivided centerline "
            "there is no gravel, so the rumble strip stays the outermost "
            "sound and the spoken warning carries the danger.",
        ),
        SoundEntry(
            "Back in the lane",
            (Cue("vehicle/lane_centered", volume=0.5),),
            "The soft chime that says you are centered again. It is the "
            "all-clear after a drift, and it also marks a bend taken cleanly "
            "when speech is set to terse.",
        ),
        SoundEntry(
            "Lane line crossed",
            (
                Cue("vehicle/lane_line_cross", volume=0.7, pan=-0.6),
                Cue("vehicle/lane_line_cross", volume=0.7, pan=0.6, delay_s=1.2),
            ),
            "The tires rolling over the raised markers of a painted line. "
            "You have changed lanes, whether you meant to or not. A quieter "
            "version of it means you have crossed the same line again "
            "straight away.",
        ),
        SoundEntry(
            "Lane locator",
            (
                Cue("vehicle/lane_locator", volume=0.5, pan=-0.9),
                Cue("vehicle/lane_locator", volume=0.5, pan=-0.3, delay_s=1.0),
                Cue("vehicle/lane_locator", volume=0.5, pan=0.3, delay_s=2.0),
                Cue("vehicle/lane_locator", volume=0.5, pan=0.9, delay_s=3.0),
            ),
            "A soft tock, once a beat, panned to where the truck sits inside "
            "its lane. You turn it on and off yourself and it keeps ticking "
            "until you stop it. The demo walks it from the left of the lane "
            "to the right.",
            when="Lane keeping partial or off, and above walking pace.",
        ),
        SoundEntry(
            "Rumble strip, single hit",
            (Cue("vehicle/rumble_strip", volume=0.9),),
            "A single hit of rumble strip with nothing held after it. A tired "
            "driver wandering, or the truck catching the edge for a moment. "
            "If you did not steer, it is fatigue, and it is telling you to "
            "find somewhere to stop.",
        ),
        SoundEntry(
            "Transverse strips",
            (Cue("vehicle/transverse_strips", volume=0.8),),
            "Grouped bars cut across the whole lane, not along its edge. Real "
            "road agencies only cut these ahead of a curve that has killed "
            "people. Brake as soon as you hear them; they are placed far "
            "enough back that braking still makes the corner.",
        ),
        SoundEntry(
            "Curve chime",
            (
                Cue("vehicle/curve_bink", volume=0.6, pan=-0.85),
                Cue("vehicle/curve_bink", volume=0.6, pan=0.85, delay_s=1.2),
            ),
            "A demanding bend is coming, and the chime comes from the side it "
            "turns toward. Be under the advised speed before you reach it, "
            "not while you are in it.",
            when="Curve callouts on.",
        ),
        SoundEntry(
            "Exit signal tone",
            (
                Cue("vehicle/signal_tone", volume=0.8, pan=-0.6),
                Cue("vehicle/signal_tone", volume=0.8, pan=0.6, delay_s=1.2),
            ),
            "Your signal, from the side you signalled. It marks a deliberate "
            "move: an exit you asked for, or a lane change you meant.",
        ),
    ),
)


CATALOG: tuple[SoundCategory, ...] = (_LANE,)


def catalog_entries() -> tuple[SoundEntry, ...]:
    """Every entry, in catalog order."""
    return tuple(entry for category in CATALOG for entry in category.entries)


def catalog_keys() -> set[str]:
    """Every sound key the catalog plays, fallbacks included."""
    keys: set[str] = set()
    for entry in catalog_entries():
        for cue in entry.plays:
            keys.add(cue.key)
            if cue.fallback:
                keys.add(cue.fallback)
    return keys
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_sound_catalog.py -v
```

Expected: PASS. If `test_every_catalogued_key_resolves_to_a_real_asset` fails on a key, the key is wrong — fix the catalog, not the test.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src tests tools
git add src/freight_fate/sound_catalog.py tests/test_sound_catalog.py
git commit -m "feat(sounds): catalog the lane and steering cues [skip changelog]"
```

---

### Task 2: The remaining six categories

**Files:**
- Modify: `src/freight_fate/sound_catalog.py`
- Test: `tests/test_sound_catalog.py`

**Interfaces:**
- Consumes: `Cue`, `SoundEntry`, `SoundCategory`, `CATALOG` from Task 1.
- Produces: `CATALOG` grown to seven categories, roughly 45 entries.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sound_catalog.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_sound_catalog.py -v
```

Expected: `test_all_seven_categories_are_present_in_order` FAILS (only `Lane and steering` exists), and `test_the_emergency_brake_entry_declares_a_fallback` FAILS with `StopIteration`.

- [ ] **Step 3: Add the six categories**

Insert these before the `CATALOG` assignment in `src/freight_fate/sound_catalog.py`, then extend `CATALOG` to `(_LANE, _AIR, _ENGINE_BRAKE, _RAMPS, _HAZARDS, _ENFORCEMENT, _LOAD)`.

```python
_AIR = SoundCategory(
    "Air and brakes",
    (
        SoundEntry(
            "Air building",
            (Cue("vehicle/air_pressurize", volume=0.55, hold_s=3.0),),
            "The compressor filling the tanks. The truck cannot move until "
            "there is enough air in them, so start the engine, leave the "
            "parking brake set, and wait for it to reach a hundred psi.",
        ),
        SoundEntry(
            "Air dryer purge",
            (Cue("vehicle/air_dryer_purge", volume=0.65),),
            "A short sharp pop from under the truck when the tanks reach "
            "full and the compressor cuts out. Nothing is wrong; it is the "
            "sound of the air system being healthy.",
        ),
        SoundEntry(
            "Low air buzzer",
            (Cue("vehicle/low_air_buzzer", volume=0.9, hold_s=3.0),),
            "Air pressure has fallen too low to brake safely. Stop using the "
            "brakes, let the compressor catch up, and keep the parking brake "
            "set until it does. Hard repeated braking is what empties the "
            "tanks fastest.",
        ),
        SoundEntry(
            "Parking brake set",
            (Cue("vehicle/brake_set", volume=0.9),),
            "The parking brake going on: a hard mechanical clunk of air "
            "dumping. The truck will not move until you release it.",
        ),
        SoundEntry(
            "Parking brake released",
            (Cue("vehicle/brake_release", volume=0.65),),
            "The parking brake coming off. You are free to roll, which also "
            "means the truck can roll on a grade before you are ready.",
        ),
        SoundEntry(
            "Brake air",
            (Cue("vehicle/brake_air", volume=1.0),),
            "The hiss of the service brakes releasing after a stop. Routine "
            "on every pull-away, and worth knowing so it is not mistaken for "
            "the low air buzzer or the dryer purge.",
        ),
        SoundEntry(
            "Emergency brake",
            (Cue("vehicle/ebrake", volume=0.9, fallback="vehicle/brake_air"),),
            "The hardest stop the truck has. It is for a hazard you cannot "
            "otherwise miss, or a stop you would otherwise overshoot, and it "
            "is rough on the load.",
        ),
        SoundEntry(
            "Tire screech",
            (Cue("vehicle/tire_screech", volume=0.9),),
            "The tires have lost their grip on the road. Ease off whatever "
            "you were doing -- brake, throttle or steering -- rather than "
            "adding more of it. On a wet or icy road this arrives at speeds "
            "that would be fine on dry pavement.",
        ),
    ),
)


# The jake growl is one synthesized loop per rpm band; the retard stage sets
# its level (JAKE_STAGE_GAIN in states/driving_updates.py). The three entries
# below demo the same 1600 rpm band at each stage's gain, so what a player
# learns is the step between stages rather than a change of pitch.
_ENGINE_BRAKE = SoundCategory(
    "Engine brake, speed and shifting",
    (
        SoundEntry(
            "Engine brake, stage one",
            (Cue("engine/jake_1600", volume=0.19, hold_s=2.5),),
            "Two cylinders of retard: the lightest setting. Enough to hold "
            "speed on a gentle grade without touching the brakes.",
        ),
        SoundEntry(
            "Engine brake, stage two",
            (Cue("engine/jake_1600", volume=0.49, hold_s=2.5),),
            "Four cylinders of retard. The usual working setting on a long "
            "descent.",
        ),
        SoundEntry(
            "Engine brake, stage three",
            (Cue("engine/jake_1600", volume=0.76, hold_s=2.5),),
            "Six cylinders: everything the engine brake has. Loud enough "
            "that towns ban it, which is what a no engine brake zone is "
            "about.",
        ),
        SoundEntry(
            "Overspeed chime",
            (Cue("vehicle/overspeed_chime", volume=0.65),),
            "You are over the posted limit here. It is not a ticket and "
            "nobody has necessarily seen you, but an officer who has will "
            "act on it.",
        ),
        SoundEntry(
            "Gear grind",
            (Cue("vehicle/gear_grind", volume=1.0),),
            "The shift did not take. Clutch in properly and try the gear "
            "again; grinding wears the box and leaves you without drive on a "
            "grade.",
            when="Manual transmission only.",
        ),
    ),
)


_RAMPS = SoundCategory(
    "Ramps and stop bars",
    (
        SoundEntry(
            "Stop bar tone",
            (Cue("vehicle/bar_solid", volume=0.85, hold_s=3.0),),
            "A continuous tone that means the stop bar is close enough that "
            "you must already be stopping. It runs until you have stopped or "
            "passed it. Treat it as the last warning, not the first.",
        ),
        SoundEntry(
            "Green light",
            (Cue("events/ramp_light_green", volume=0.8),),
            "The signal at the bottom of the ramp is green. You may go "
            "through without stopping if you are already rolling.",
        ),
        SoundEntry(
            "Red light",
            (Cue("events/ramp_light_red", volume=0.7),),
            "The signal has gone red. Stop at the bar and wait for green. "
            "Rolling through draws horns; going through at speed means cross "
            "traffic hits the trailer.",
        ),
    ),
)


_HAZARDS = SoundCategory(
    "Hazards and the road",
    (
        SoundEntry(
            "Hazard warning",
            (Cue("events/hazard_warning", volume=1.0),),
            "Something in your path needs a real reaction now: brake below "
            "twenty five miles per hour quickly, or move to a clear lane if "
            "the warning says the object is in your lane.",
        ),
        SoundEntry(
            "Hazard clear",
            (Cue("events/hazard_clear", volume=0.75),),
            "The hazard is behind you. You can go back to normal speed.",
        ),
        SoundEntry(
            "Construction zone",
            (Cue("events/construction_zone", volume=0.9),),
            "Roadwork ahead. The posted limit drops, a lane may close, and "
            "the taper callout names which side. Move over when told or you "
            "will go through the barrels.",
        ),
        SoundEntry(
            "Traffic slowing",
            (Cue("events/traffic_slowing", volume=0.9),),
            "The traffic in front of you is coming down in speed. Back off "
            "the throttle before you need the brakes.",
        ),
        SoundEntry(
            "Turn ahead",
            (Cue("events/turn_ahead", volume=0.9),),
            "A street maneuver is coming on a local drive. The spoken "
            "guidance that follows names the street and the direction.",
        ),
        SoundEntry(
            "Turn left",
            (Cue("events/turn_left", volume=0.9),),
            "The next maneuver is a left. Be under the advised speed before "
            "the corner: a loaded trailer off-tracks through a city turn.",
        ),
        SoundEntry(
            "Turn right",
            (Cue("events/turn_right", volume=0.9),),
            "The next maneuver is a right. Same rule as a left, and a right "
            "in a truck needs more room than it looks like it should.",
        ),
        SoundEntry(
            "State line",
            (Cue("events/state_crossing", volume=0.9),),
            "You have crossed into another state. Speed limits and rules can "
            "change with it, and the spoken callout names the new state.",
        ),
        SoundEntry(
            "Toll charged",
            (Cue("events/toll_charged", volume=0.9),),
            "A toll gantry or plaza has billed the truck. Tolls are settled "
            "at delivery, listed separately from anything you were fined.",
        ),
        SoundEntry(
            "Yawn",
            (Cue("driver/yawn", volume=0.9),),
            "You are the one making this sound. Fatigue is building, faster "
            "at night, and a tired driver drifts and reacts late. Plan a "
            "stop rather than pushing through it.",
        ),
    ),
)


_ENFORCEMENT = SoundCategory(
    "Enforcement",
    (
        SoundEntry(
            "Enforcement post",
            (
                Cue("traffic/trooper_pass", volume=0.8, pan=-0.6),
                Cue("traffic/trooper_pass", volume=0.8, pan=0.6, delay_s=1.6),
            ),
            "A patrol car sitting off the road on that side, heard before it "
            "can see you. Most posts are empty and cost you nothing; this "
            "sound means this one is not, so be at the limit before you "
            "reach it.",
        ),
        SoundEntry(
            "Siren",
            (Cue("events/police_siren", volume=0.8, pan=-0.5, hold_s=3.0),),
            "A trooper is pulling you over. Signal, brake, and stop on the "
            "shoulder. Ignoring it is logged as evasion and costs far more "
            "than the ticket would have.",
        ),
        SoundEntry(
            "Inspection warning",
            (Cue("events/inspection_warning", volume=0.7),),
            "You are being looked at for something other than speed: visible "
            "damage, no chains inside a chain control, or following far too "
            "close.",
        ),
        SoundEntry(
            "Weigh station",
            (Cue("poi/weigh_station_lane", volume=0.6, hold_s=3.0),),
            "The bed that swells as you come up on an open scale. An open "
            "scale must be pulled into; blowing past one is its own stop.",
        ),
        SoundEntry(
            "Spike strip",
            (Cue("events/spike_strip", volume=1.0),),
            "The end of a pursuit. If you are hearing this, running from the "
            "lights has already gone as badly as it can go.",
        ),
        SoundEntry(
            "CB chatter",
            (Cue("events/cb_radio_chatter", volume=0.8),),
            "Other drivers passing on what they have seen: enforcement, "
            "wrecks, work zones. It says how sure it is, it is sometimes out "
            "of date, and it never claims the road is clear.",
        ),
    ),
)


_LOAD = SoundCategory(
    "The load",
    (
        SoundEntry(
            "Surge",
            (Cue("vehicle/liquid_wash", volume=0.7, hold_s=3.0),),
            "Liquid running back and forth inside a tank trailer. It builds "
            "while you brake or accelerate and it pushes the truck after you "
            "have stopped doing whatever started it.",
            when="Liquid bulk freight in a tank trailer only.",
        ),
        SoundEntry(
            "Surge strike",
            (Cue("vehicle/liquid_hit", volume=0.8),),
            "The load hitting the front or back of the tank. It shoves the "
            "truck along its length, which is why a smooth bore tank is "
            "braked early and gently rather than late and hard.",
            when="Liquid bulk freight in a tank trailer only.",
        ),
        SoundEntry(
            "Surge strike, sideways",
            (
                Cue("vehicle/liquid_hit_lateral", volume=0.8, pan=-0.6),
                Cue("vehicle/liquid_hit_lateral", volume=0.8, pan=0.6, delay_s=1.4),
            ),
            "The load hitting the side of the tank, from the side it hit. "
            "This is the one that rolls trucks: it arrives after you have "
            "already turned or changed lanes.",
            when="Liquid bulk freight in a tank trailer only.",
        ),
    ),
)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_sound_catalog.py -v
```

Expected: PASS, all tests. `test_every_catalogued_key_resolves_to_a_real_asset` is the one to watch — it proves every key above is real.

- [ ] **Step 5: Lint, check the file size, and commit**

```bash
uv run ruff check src tests tools
uv run python -c "print(sum(1 for _ in open('src/freight_fate/sound_catalog.py', encoding='utf-8')))"
```

Expected: under 1000 lines. If it is over, split the category definitions into `sound_catalog_entries.py` and keep the types and lookups in `sound_catalog.py`.

```bash
git add src/freight_fate/sound_catalog.py tests/test_sound_catalog.py
git commit -m "feat(sounds): catalog air, brakes, hazards, enforcement and the load [skip changelog]"
```

---

### Task 3: Exclusions, the completeness gate, and ontology rows

**Files:**
- Modify: `src/freight_fate/sound_catalog.py`, `docs/ontology.md`
- Test: `tests/test_sound_catalog.py`

**Interfaces:**
- Consumes: `CATALOG`, `catalog_keys()` from Tasks 1-2.
- Produces: `SELF_EXPLANATORY: dict[str, str]` mapping key (or `prefix/*` glob) to the reason it is left out; `is_excluded(key) -> bool`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sound_catalog.py`:

Ruff runs `E` and `I`, so `import ast` and `import re` go at the **top** of
`tests/test_sound_catalog.py` alongside `from pathlib import Path`, not here.
Everything below is appended to the end of the file.

```python
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
```

Note `test_nothing_is_both_taught_and_excluded` and `vehicle/road`: the road bed is catalogued as the road lean, so it must NOT appear in `SELF_EXPLANATORY`.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_sound_catalog.py -v
```

Expected: `AttributeError: module 'freight_fate.sound_catalog' has no attribute 'is_excluded'`, and once that exists, `test_every_playable_cue_is_taught_or_explicitly_excluded` FAILS listing the uncatalogued keys.

- [ ] **Step 3: Add the exclusion list and the lookup**

Append to `src/freight_fate/sound_catalog.py`:

```python
# What is deliberately not taught, and why. An exclusion is a decision on the
# record, not a gap: the completeness test fails on any played cue that is
# neither catalogued above nor listed here. A trailing "/*" excludes a whole
# folder.
#
# vehicle/road is in NEITHER list as a plain bed -- it is catalogued once, as
# the road lean, because what teaches a player something is its pan.
SELF_EXPLANATORY: dict[str, str] = {
    # Listed one by one rather than as "engine/*": the jake ring lives in the
    # same folder and IS taught, and a folder glob here would mark it excluded
    # and taught at once.
    "engine/idle": "It is an engine and it sounds like one.",
    "engine/low": "As the idle loop: an engine at an engine speed.",
    "engine/mid": "As the idle loop.",
    "engine/midhigh": "As the idle loop.",
    "engine/high": "As the idle loop.",
    "engine/start": "An engine starting, immediately after you started it.",
    "engine/shutdown": "An engine stopping, immediately after you stopped it.",
    "weather/*": "Rain, wind, snow and thunder name themselves.",
    "ambient/*": "Scene, not a cue: no decision attached.",
    "music/*": "Songs.",
    "ui/*": "Menu feedback, learned in the first ten seconds of the main menu.",
    "radio/fm_hiss_loop": (
        "Static means weak signal to anyone who has owned a radio, and the "
        "station dropping is spoken aloud when it happens."
    ),
    "radio/picket": "The fringe flutter, same reason as the hiss bed.",
    "radio/static_burst": "Plays under a spoken line that already explains it.",
    "vehicle/road_joint": "Pavement seams: texture, not a decision.",
    "vehicle/truck_door": "A door.",
    "vehicle/fuel_pump": "A fuel pump, at a fuel pump.",
    "vehicle/reverse": "A backup beeper while backing up.",
    "vehicle/horn": "The player is holding the horn key.",
    "vehicle/brake_squeal": "It means you braked hard, which you know.",
    "vehicle/collision": "A collision announces itself by having happened.",
    "vehicle/gear_shift": "A gear change in a truck that is changing gear.",
    "vehicle/shift_manual": "Banked gear changes, same reason.",
    "vehicle/shift_auto": "Banked gear changes, same reason.",
    "traffic/car_pass": "A vehicle going past sounds like a vehicle going past.",
    "traffic/box_truck_pass": "As the car pass.",
    "traffic/semi_pass": "As the car pass.",
    "poi/facility_gate": "Ambient bed for a place the game has already named.",
    "poi/rest_stop_night": "Ambient bed for a place the game has already named.",
    "facility/dock_gate": "Menu feedback at a facility, not a road cue.",
    "poi/dock_and_deliver": "Menu feedback at a facility, not a road cue.",
}


def is_excluded(key: str) -> bool:
    """Whether ``key`` is deliberately left out of the catalog."""
    if key in SELF_EXPLANATORY:
        return True
    folder = key.split("/", 1)[0]
    return f"{folder}/*" in SELF_EXPLANATORY
```

`radio/picket` is the bank base; `play_bank` is called with the base, so the
literal key the scanner sees is `radio/picket`. If the completeness test
reports a key this list does not cover, add it here with a real reason or
catalog it — never widen a glob to silence the test.

- [ ] **Step 4: Add the missing ontology rows**

`test_every_entry_name_is_an_ontology_noun` names exactly which entries lack a
row. For each, add a row to the Spoken vocabulary table in `docs/ontology.md`
using its existing four columns (`Concept | Say | Avoid | Internal name`).
Examples of the shape expected:

```markdown
| The three edge textures, in order out of the lane | rumble strip, clipped; rumble strip; off the pavement | edge ladder (that is the code word), drift beep, lane departure warning | `sim/lane_guidance.edge_rung` |
| The bars cut across a lane ahead of a killer curve | transverse strips | rumble bars, wake-up strips | `sim/lane_guidance.TRANSVERSE_KEY` |
| The screen that plays a cue and says what it means | Learn game sounds | sound test, sound gallery, sound tutorial | `states/learn_sounds.py` |
```

Reuse the existing noun wherever the table already has one — "surge", "engine
brake", "enforcement post", "weigh station", "CB chatter" and "facility gate"
are all already there, so those entries should already pass.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
uv run pytest tests/test_sound_catalog.py -v
```

Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check src tests tools
git add src/freight_fate/sound_catalog.py tests/test_sound_catalog.py docs/ontology.md
git commit -m "feat(sounds): gate catalog completeness and name the cues [skip changelog]"
```

---

### Task 4: The demo sequencer

**Files:**
- Create: `src/freight_fate/sound_demo.py`
- Test: `tests/test_learn_sounds_state.py`

**Interfaces:**
- Consumes: `SoundEntry`, `Cue` from Task 1.
- Produces: `SoundDemo(audio)` with `start(entry)`, `update(dt)`, `stop()`, and a `running` property. Held cues are asserted through `audio.hold_alert(key, volume=...)` plus `audio.set_loop_pan(CH_ALERT, pan)`; one-shots through `audio.play(key, volume=..., pan=...)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_learn_sounds_state.py`:

```python
"""Learn game sounds: the demo sequencer and the screen that drives it."""

from freight_fate.sound_catalog import Cue, SoundEntry


class FakeAudio:
    """Records what a demo asked for, in order."""

    def __init__(self) -> None:
        self.played: list[tuple[str, float, float]] = []
        self.holds: list[tuple[str, float]] = []
        self.pans: list[tuple[int, float]] = []
        self.released = 0

    def play(self, key, volume=1.0, pan=0.0):
        self.played.append((key, volume, pan))

    def hold_alert(self, key, volume=1.0, fade_ms=60):
        self.holds.append((key, volume))

    def set_loop_pan(self, channel, pan):
        self.pans.append((channel, pan))

    def release_alert(self, fade_ms=120):
        self.released += 1

    def has_asset(self, key):
        return not key.startswith("missing/")


def test_a_one_shot_entry_plays_once_with_its_volume_and_pan():
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("X", (Cue("a/one", volume=0.5, pan=-0.6),), "why"))
    assert audio.played == [("a/one", 0.5, -0.6)]
    demo.update(0.1)
    assert audio.played == [("a/one", 0.5, -0.6)], "a one-shot must not repeat"


def test_a_delayed_cue_waits_for_its_moment():
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(
        SoundEntry(
            "X",
            (Cue("a/left", pan=-0.8), Cue("a/right", pan=0.8, delay_s=1.0)),
            "why",
        )
    )
    assert [k for k, _v, _p in audio.played] == ["a/left"]
    demo.update(0.5)
    assert [k for k, _v, _p in audio.played] == ["a/left"]
    demo.update(0.6)
    assert [k for k, _v, _p in audio.played] == ["a/left", "a/right"]


def test_a_held_cue_is_reasserted_every_frame_then_released():
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("X", (Cue("a/loop", volume=0.7, pan=0.3, hold_s=1.0),), "why"))
    assert audio.holds == [("a/loop", 0.7)]
    assert audio.pans and audio.pans[-1][1] == 0.3
    demo.update(0.5)
    assert len(audio.holds) > 1, "a held cue must be re-asserted while it runs"
    assert audio.released == 0
    demo.update(0.6)
    assert audio.released == 1
    assert not demo.running


def test_starting_a_new_demo_cancels_the_running_one():
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("X", (Cue("a/loop", hold_s=5.0),), "why"))
    demo.start(SoundEntry("Y", (Cue("b/one"),), "why"))
    assert audio.released == 1
    demo.update(0.1)
    assert audio.released == 1, "the second demo has nothing to release"


def test_stop_releases_a_held_cue_and_ends_the_demo():
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("X", (Cue("a/loop", hold_s=5.0),), "why"))
    demo.stop()
    assert audio.released == 1
    assert not demo.running


def test_a_cue_falls_back_when_its_key_is_missing():
    from freight_fate.sound_demo import SoundDemo

    audio = FakeAudio()
    demo = SoundDemo(audio)
    demo.start(SoundEntry("X", (Cue("missing/thing", fallback="a/real"),), "why"))
    assert [k for k, _v, _p in audio.played] == ["a/real"]
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_learn_sounds_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'freight_fate.sound_demo'`.

- [ ] **Step 3: Write the sequencer**

Create `src/freight_fate/sound_demo.py`:

```python
"""Playing one catalog entry, faithfully and without leaving anything ringing.

A demo is a short script: fire each cue at its moment, hold the ones that are
loops for as long as they declare, and release everything the moment the demo
ends -- whether it ended on its own, was replaced by another, or the screen
was closed underneath it.

Held cues go through ``hold_alert``, which is a dead man's switch: it stops on
its own a fraction of a second after the re-assertions stop. A continuous tone
in a blind player's headphones must never be able to outlive the thing that
started it, and routing every held demo cue through that one mechanism is what
makes that true here without a second watchdog to get wrong.
"""

from __future__ import annotations

from .audio import CH_ALERT
from .sound_catalog import Cue, SoundEntry


class SoundDemo:
    """Sequences one :class:`SoundEntry`'s cues against an audio engine."""

    def __init__(self, audio) -> None:
        self._audio = audio
        self._entry: SoundEntry | None = None
        self._pending: list[Cue] = []
        self._elapsed = 0.0
        self._hold_key = ""
        self._hold_volume = 1.0
        self._hold_left = 0.0

    @property
    def running(self) -> bool:
        return self._entry is not None

    def start(self, entry: SoundEntry) -> None:
        """Play ``entry`` from the top, cancelling whatever was running."""
        self.stop()
        self._entry = entry
        self._pending = sorted(entry.plays, key=lambda cue: cue.delay_s)
        self._elapsed = 0.0
        self._fire_due()

    def update(self, dt: float) -> None:
        if self._entry is None:
            return
        self._elapsed += dt
        self._fire_due()
        if self._hold_key:
            self._hold_left -= dt
            if self._hold_left <= 0.0:
                self._release()
            else:
                # Re-assert every frame: the engine's own watchdog drops the
                # tone if this ever stops, which is the behaviour we want.
                self._audio.hold_alert(self._hold_key, volume=self._hold_volume)
        if not self._pending and not self._hold_key:
            self._entry = None

    def stop(self) -> None:
        """End the demo now and release anything it was holding."""
        self._release()
        self._entry = None
        self._pending = []
        self._elapsed = 0.0

    # -- internals -------------------------------------------------------------

    def _fire_due(self) -> None:
        while self._pending and self._pending[0].delay_s <= self._elapsed:
            self._play(self._pending.pop(0))

    def _play(self, cue: Cue) -> None:
        key = self._resolve(cue)
        if not key:
            return
        if cue.hold_s > 0.0:
            self._release()  # one held cue at a time: the alert channel is one channel
            self._audio.hold_alert(key, volume=cue.volume)
            self._audio.set_loop_pan(CH_ALERT, cue.pan)
            self._hold_key = key
            self._hold_volume = cue.volume
            self._hold_left = cue.hold_s
            return
        self._audio.play(key, volume=cue.volume, pan=cue.pan)

    def _resolve(self, cue: Cue) -> str:
        """``cue.key`` where it exists, else its fallback, else nothing.

        The licensed overlay carries cues a clean clone does not have. A demo
        that silently played nothing would teach a player that a real cue is
        silent, which is the worst thing this screen could do.
        """
        has_asset = getattr(self._audio, "has_asset", None)
        if has_asset is None or has_asset(cue.key):
            return cue.key
        if cue.fallback and has_asset(cue.fallback):
            return cue.fallback
        return ""

    def _release(self) -> None:
        if not self._hold_key:
            return
        self._hold_key = ""
        self._hold_left = 0.0
        self._audio.release_alert()
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_learn_sounds_state.py -v
```

Expected: PASS, six tests.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src tests tools
git add src/freight_fate/sound_demo.py tests/test_learn_sounds_state.py
git commit -m "feat(sounds): sequence a catalog entry without leaving a loop ringing [skip changelog]"
```

---

### Task 5: The two menu states

**Files:**
- Create: `src/freight_fate/states/learn_sounds.py`
- Test: `tests/test_learn_sounds_state.py`

**Interfaces:**
- Consumes: `CATALOG`, `SoundCategory` from Tasks 1-2; `SoundDemo` from Task 4; `MenuState`, `MenuItem` from `states/base.py`.
- Produces: `LearnSoundsState(ctx)` and `LearnSoundCategoryState(ctx, category)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_learn_sounds_state.py`:

```python
def _app():
    from freight_fate.app import App

    return App()


def test_the_category_screen_lists_every_catalog_category():
    from freight_fate.sound_catalog import CATALOG
    from freight_fate.states.learn_sounds import LearnSoundsState

    app = _app()
    try:
        state = LearnSoundsState(app.ctx)
        labels = [item.text for item in state.build_items()]
        assert labels == [c.name for c in CATALOG]
    finally:
        app.shutdown()


def test_arrowing_speaks_the_name_and_plays_no_cue(monkeypatch):
    from freight_fate.sound_catalog import CATALOG
    from freight_fate.states.learn_sounds import LearnSoundCategoryState
    from speech_capture import speech_stub

    app = _app()
    try:
        spoken: list[str] = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        played: list[str] = []
        monkeypatch.setattr(app.ctx.audio, "play", lambda key, **_kw: played.append(key))

        state = LearnSoundCategoryState(app.ctx, CATALOG[0])
        state.enter()
        played.clear()
        spoken.clear()
        state.move(1)

        assert any(state.items[state.index].text in line for line in spoken)
        # Only the menu's own movement click, never a catalogued cue.
        assert played == ["ui/menu_move"]
    finally:
        app.shutdown()


def test_enter_plays_the_entrys_cue_with_its_volume_and_pan(monkeypatch):
    from freight_fate.sound_catalog import CATALOG
    from freight_fate.states.learn_sounds import LearnSoundCategoryState
    from speech_capture import speech_stub

    app = _app()
    try:
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        calls: list[tuple[str, float, float]] = []
        monkeypatch.setattr(
            app.ctx.audio,
            "play",
            lambda key, volume=1.0, pan=0.0: calls.append((key, volume, pan)),
        )
        monkeypatch.setattr(app.ctx.audio, "hold_alert", lambda key, **_kw: None)
        monkeypatch.setattr(app.ctx.audio, "set_loop_pan", lambda *_a, **_k: None)

        category = CATALOG[0]
        state = LearnSoundCategoryState(app.ctx, category)
        state.enter()
        # Land on an entry whose first cue is a one-shot so the assert is direct.
        index = next(i for i, e in enumerate(category.entries) if e.plays[0].hold_s == 0.0)
        state.index = index
        calls.clear()
        state.activate()

        cue = category.entries[index].plays[0]
        assert (cue.key, cue.volume, cue.pan) in calls
    finally:
        app.shutdown()


def test_f1_speaks_the_meaning_and_the_when_note():
    from freight_fate.sound_catalog import CATALOG
    from freight_fate.states.learn_sounds import LearnSoundCategoryState

    app = _app()
    try:
        category = next(c for c in CATALOG if any(e.when for e in c.entries))
        entry_index = next(i for i, e in enumerate(category.entries) if e.when)
        state = LearnSoundCategoryState(app.ctx, category)
        state.items = state.build_items()
        state.index = entry_index

        help_text = state.current_help()
        entry = category.entries[entry_index]
        assert entry.meaning in help_text
        assert entry.when in help_text
    finally:
        app.shutdown()


def test_leaving_the_screen_releases_a_held_cue(monkeypatch):
    from freight_fate.sound_catalog import Cue, SoundCategory, SoundEntry
    from freight_fate.states.learn_sounds import LearnSoundCategoryState
    from speech_capture import speech_stub

    app = _app()
    try:
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx.audio, "play", lambda *_a, **_k: None)
        monkeypatch.setattr(app.ctx.audio, "hold_alert", lambda *_a, **_k: None)
        monkeypatch.setattr(app.ctx.audio, "set_loop_pan", lambda *_a, **_k: None)
        releases: list[int] = []
        monkeypatch.setattr(
            app.ctx.audio, "release_alert", lambda **_kw: releases.append(1)
        )

        held = SoundCategory(
            "Held", (SoundEntry("Held cue", (Cue("vehicle/bar_solid", hold_s=5.0),), "why"),)
        )
        state = LearnSoundCategoryState(app.ctx, held)
        state.enter()
        state.activate()
        state.exit()

        assert releases, "a held cue must not survive the screen closing"
    finally:
        app.shutdown()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_learn_sounds_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'freight_fate.states.learn_sounds'`.

- [ ] **Step 3: Write the states**

Create `src/freight_fate/states/learn_sounds.py`:

```python
"""Learn game sounds: hear a cue and what it means, before it matters.

Two screens. The first lists the catalog's categories; the second lists the
cues inside one and plays them on request.

Arrowing speaks the name and nothing else, the way every other menu in the
game behaves. Enter plays the cue, and Enter again replays it. A cue that
fired while its own name was being spoken would teach the player the
collision rather than the cue, and holding Down would machine-gun the audio,
so nothing here plays on movement.
"""

from __future__ import annotations

from ..sound_catalog import CATALOG, SoundCategory
from ..sound_demo import SoundDemo
from .base import MenuItem, MenuState


class LearnSoundsState(MenuState):
    """The category list."""

    title = "Learn game sounds"
    intro_help = (
        "Choose a group of sounds. Inside a group, Enter plays the sound and "
        "F1 says what it means. Up and down arrows move, Escape goes back."
    )

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                category.name,
                lambda c=category: self.ctx.push_state(LearnSoundCategoryState(self.ctx, c)),
                help=f"{len(category.entries)} sounds. {self._summary(category)}",
            )
            for category in CATALOG
        ]

    @staticmethod
    def _summary(category: SoundCategory) -> str:
        names = ", ".join(entry.name for entry in category.entries[:3])
        return f"Starting with {names}." if names else ""


class LearnSoundCategoryState(MenuState):
    """The cues inside one category, and the demo that plays them."""

    intro_help = (
        "Enter plays the sound, and Enter again plays it a second time. "
        "F1 says what it means and when you hear it. Up and down arrows "
        "move, Escape stops the sound and goes back."
    )

    def __init__(self, ctx, category: SoundCategory) -> None:
        super().__init__(ctx)
        self.category = category
        self.title = category.name
        self.demo = SoundDemo(ctx.audio)

    def build_items(self) -> list[MenuItem]:
        return [
            MenuItem(
                entry.name,
                lambda e=entry: self.demo.start(e),
                help=f"{entry.meaning} {entry.when}".strip(),
                # The demo IS the confirmation; a menu click over the top of a
                # cue the player is trying to learn defeats the screen.
                select_sound=None,
            )
            for entry in self.category.entries
        ]

    def update(self, dt: float) -> None:
        super().update(dt)
        self.demo.update(dt)

    def move(self, delta: int) -> None:
        # Arrowing away from a running demo stops it: the next name should
        # arrive over silence, not over the last cue.
        self.demo.stop()
        super().move(delta)

    def go_back(self) -> None:
        self.demo.stop()
        super().go_back()

    def exit(self) -> None:
        self.demo.stop()
        super().exit()
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_learn_sounds_state.py -v
```

Expected: PASS, all eleven tests.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src tests tools
git add src/freight_fate/states/learn_sounds.py tests/test_learn_sounds_state.py
git commit -m "feat(sounds): add the learn game sounds screens [skip changelog]"
```

---

### Task 6: Both entry points

**Files:**
- Modify: `src/freight_fate/states/main_menu.py` (the `build_items` list, after the `How to play` item at ~line 321, and a handler beside `_help` at ~line 379)
- Modify: `src/freight_fate/states/driving_pause_states.py` (the `build_items` list, after `Controls and help`)
- Test: `tests/test_learn_sounds_state.py`

**Interfaces:**
- Consumes: `LearnSoundsState` from Task 5.
- Produces: a `Learn game sounds` item on both menus.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_learn_sounds_state.py`:

```python
def test_the_main_menu_offers_learn_game_sounds():
    from freight_fate.states.main_menu import MainMenuState

    app = _app()
    try:
        labels = [item.text for item in MainMenuState(app.ctx).build_items()]
        assert "Learn game sounds" in labels
        # It sits with the other learning material, after How to play.
        assert labels.index("Learn game sounds") == labels.index("How to play") + 1
    finally:
        app.shutdown()


def test_the_pause_menu_offers_learn_game_sounds():
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState, PauseMenuState

    app = _app()
    try:
        app.ctx.profile = Profile(name="Sounds", current_city="Buffalo")
        route = app.ctx.world.supported_route("Buffalo", "Rochester")
        job = Job(
            CARGO_CATALOG["general"],
            12.0,
            "Buffalo",
            "company yard",
            "Rochester",
            route.miles,
            1000.0,
            12.0,
            destination_location="Rochester freight market",
        )
        driving = DrivingState(app.ctx, job, route, phase="delivery")
        labels = [item.text for item in PauseMenuState(app.ctx, driving).build_items()]
        assert "Learn game sounds" in labels
        assert labels.index("Learn game sounds") == labels.index("Controls and help") + 1
    finally:
        app.shutdown()


def test_both_entry_points_push_the_same_screen(monkeypatch):
    from freight_fate.states.learn_sounds import LearnSoundsState
    from freight_fate.states.main_menu import MainMenuState

    app = _app()
    try:
        pushed: list[object] = []
        monkeypatch.setattr(app.ctx, "push_state", lambda state, **_kw: pushed.append(state))
        menu = MainMenuState(app.ctx)
        item = next(i for i in menu.build_items() if i.text == "Learn game sounds")
        item.action()
        assert isinstance(pushed[0], LearnSoundsState)
    finally:
        app.shutdown()
```

The class is `MainMenuState` in `src/freight_fate/states/main_menu.py:201`.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_learn_sounds_state.py -k learn_game_sounds -v
```

Expected: three FAILs on `assert "Learn game sounds" in labels`.

- [ ] **Step 3: Add the main menu item**

In `src/freight_fate/states/main_menu.py`, directly after the `How to play`
item in `build_items`:

```python
        items.append(
            MenuItem(
                "Learn game sounds",
                self._learn_sounds,
                help="Play any sound the road uses and hear what it means, "
                "before you meet it at speed.",
            )
        )
```

And beside `_help`:

```python
    def _learn_sounds(self) -> None:
        from .learn_sounds import LearnSoundsState

        self.ctx.push_state(LearnSoundsState(self.ctx))
```

- [ ] **Step 4: Add the pause menu item**

In `src/freight_fate/states/driving_pause_states.py`, in `PauseMenuState.build_items`,
directly after the `Controls and help` item:

```python
            MenuItem(
                "Learn game sounds",
                self._learn_sounds,
                help="Play any sound the road uses and hear what it means. "
                "The drive is paused while you listen.",
            ),
```

And a handler beside `_controls`:

```python
    def _learn_sounds(self) -> None:
        from .learn_sounds import LearnSoundsState

        self.ctx.push_state(LearnSoundsState(self.ctx))
```

No audio cleanup is needed here: `PauseMenuState.enter` already calls
`stop_world()`, so the engine, road, weather and any held alert are down
before the catalog is reachable, and demos play against silence.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
uv run pytest tests/test_learn_sounds_state.py -v
```

Expected: PASS, all fourteen tests.

- [ ] **Step 6: Run the neighbouring suites**

```bash
uv run pytest tests/test_controls_reference.py tests/test_menu_readout.py tests/test_menu_stop_speech.py tests/test_sound_catalog.py -v
```

Any test that pins the main menu's or pause menu's exact item list needs the
new item added to it. Fix the pin; do not move the item to avoid the failure.

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff check src tests tools
git add src/freight_fate/states/main_menu.py src/freight_fate/states/driving_pause_states.py tests/test_learn_sounds_state.py
git commit -m "feat(sounds): reach learn game sounds from the menu and the cab [skip changelog]"
```

---

### Task 7: Help text, manual, roadmap, changelog

**Files:**
- Modify: `src/freight_fate/states/main_menu_help.py` (the `Menus` page and the `Driving basics` page)
- Modify: `docs/user-manual-1.9-draft.md`
- Modify: `ROADMAP.md`
- Modify: `CHANGELOG.md`
- Test: `tests/test_sound_catalog.py`

**Interfaces:**
- Consumes: everything above.
- Produces: the player-facing paperwork. This is the only commit in the plan without `[skip changelog]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sound_catalog.py`:

```python
def test_the_help_reader_points_at_the_screen():
    from freight_fate.states.main_menu_help import HELP_PAGES

    joined = " ".join(line for _title, lines in HELP_PAGES for line in lines)
    assert "Learn game sounds" in joined


def test_the_changelog_records_the_feature():
    text = (Path(__file__).parents[1] / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = text.split("## Unreleased", 1)[1].split("\n## ", 1)[0]
    assert "Learn game sounds" in unreleased
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_sound_catalog.py -k "help_reader or changelog" -v
```

Expected: two FAILs.

- [ ] **Step 3: Add the help lines**

In `src/freight_fate/states/main_menu_help.py`, add to the `Menus` page's list:

```python
            "Learn game sounds on the main menu plays any sound the road uses "
            "and says what it means. It is also on the pause menu while you drive.",
```

And to the `Driving basics` page's list:

```python
            "If a sound on the road is unfamiliar, pause and open Learn game "
            "sounds: it plays every cue on demand with what it is asking for.",
```

- [ ] **Step 4: Add the manual pointer**

Add one line to `docs/user-manual-1.9-draft.md` in whichever section covers
the main menu, matching the surrounding prose style:

> **Learn game sounds** plays any cue the road uses, with what it means and
> what to do about it. It is on the main menu and on the pause menu while you
> drive. Arrow to a sound, press Enter to hear it, and press F1 for what it
> is telling you.

- [ ] **Step 5: Add the roadmap bullet**

In `ROADMAP.md`, under `## 1.9 in flight`, in the `World and narration`
section:

```markdown
- [x] **Learn game sounds.** A catalog screen on the main menu and the pause
      menu: seven categories of road cue, each entry played on demand with
      the canonical name, what it means, and the setting that gates it.
      Ambience, music and self-explanatory sounds are excluded on the record,
      and a completeness test fails any new cue that ships uncatalogued.
```

- [ ] **Step 6: Add the changelog entry**

In `CHANGELOG.md`, under `## Unreleased`, in the `Added` section (create the
section if `## Unreleased` has none):

```markdown
- **Learn what every sound means before you meet it at speed.** A new Learn
  game sounds screen on the main menu, and on the pause menu while you drive,
  plays any cue the road uses on demand. Arrow to a sound, press Enter to hear
  it exactly as the drive plays it -- panned to the side it comes from, held
  for as long as it would really run -- and press F1 for what it is telling
  you and what to do about it. Sounds that explain themselves, like the engine
  and the weather, are left out so the list stays worth reading.
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
uv run pytest tests/test_sound_catalog.py tests/test_learn_sounds_state.py -v
```

Expected: PASS.

- [ ] **Step 8: Run the full suite and the byte-compile check**

```bash
uv run pytest
```

```bash
uv run python -m compileall src tests tools
```

Expected: the suite passes. If a pinned help-page or menu-list assertion
elsewhere fails, it is pinning a list this change adds to — update the pin.

- [ ] **Step 9: Commit**

```bash
uv run ruff check src tests tools
git add src/freight_fate/states/main_menu_help.py docs/user-manual-1.9-draft.md ROADMAP.md CHANGELOG.md tests/test_sound_catalog.py
git commit -m "feat(sounds): let players learn the road's cues before they meet them"
```

---

## Verification

Before calling this done, from the repo root on `feat/career-1.9`:

```bash
uv run pytest tests/test_sound_catalog.py tests/test_learn_sounds_state.py -v
```

```bash
uv run pytest
```

```bash
uv run ruff check src tests tools
```

Then read the screen out loud, which is the part no test covers. The
transcript harness drives spoken output headlessly:

```bash
FREIGHT_FATE_LOG_FILE=learn-sounds.log uv run python -m freight_fate
```

Open Learn game sounds, walk one category end to end, and check the log's
`freight_fate.transcript` lines: every entry name should read as a noun a
driver would use, and every F1 line should say what to do, not just what the
sound is. Report in the PR which category you listened to and what it said.
