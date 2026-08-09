"""The 1.9 cutover gate: careers from the 1.8 line do not continue here.

1.9 rebalanced the whole career arc (owner ruling, 2026-08-08), so the load
path refuses pre-1.9 saves without ever touching the file -- it stays intact
on disk, still playable by the build that wrote it -- while the menus keep
the career visible with a spoken explanation instead of letting it vanish.
1.9 careers from before the ``created_line`` marker existed are recognized by
their save version (the 1.8 line never wrote past version 5) and stamped
with the marker so testers are never locked out.
"""

import json

import pygame
import pytest
from speech_capture import speech_stub

from freight_fate.models.profile import (
    LEGACY_SAVE_SUFFIX,
    SAVE_VERSION,
    LegacyCareerError,
    Profile,
    _decode_save_bytes,
    _signature_for,
    encode_save_bytes,
    is_pre_1_9_save,
    is_pre_1_9_save_file,
)


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="")


def write_1_8_save(name="Old Timer"):
    """A save exactly as a current 1.8-line build leaves it.

    dev and every stable release write packed, version-5, signature-v1 saves
    that already carry per-truck condition records (the mainline migrated by
    shape without bumping the save version) -- so the version field, not the
    record shape, is what tells the lines apart.
    """
    p = Profile(name=name)
    path = p.save()
    data = _decode_save_bytes(path.read_bytes())[0]
    data.pop("created_line", None)
    data.pop("_signature", None)
    data.pop("_signature_version", None)
    data["version"] = 5
    data["_signature_version"] = 1
    data["_signature"] = _signature_for(data)
    path.write_bytes(encode_save_bytes(data))
    return path


def write_ancient_json_save(name="Ancient"):
    """A plain-JSON save from long before the packed container (version 3)."""
    p = Profile(name=name)
    packed = p.save()
    data = _decode_save_bytes(packed.read_bytes())[0]
    packed.unlink()
    for field in ("created_line", "truck_conditions", "_signature", "_signature_version"):
        data.pop(field, None)
    data["version"] = 3
    path = packed.with_suffix(LEGACY_SAVE_SUFFIX)
    path.write_text(json.dumps(data))
    return path


def write_pre_marker_1_9_save(name="Tester"):
    """A current-version 1.9 save from before the created-on marker existed."""
    p = Profile(name=name)
    path = p.save()
    data = _decode_save_bytes(path.read_bytes())[0]
    del data["created_line"]
    data.pop("_signature", None)
    data["_signature"] = _signature_for(data)
    path.write_bytes(encode_save_bytes(data))
    return path


# -- the discriminator --------------------------------------------------------


def test_marker_decides_when_present():
    assert is_pre_1_9_save({"version": 5}) is True
    assert is_pre_1_9_save({"version": 4}) is True
    assert is_pre_1_9_save({}) is True  # no version at all: ancient
    assert is_pre_1_9_save({"version": 6}) is False
    assert is_pre_1_9_save({"version": SAVE_VERSION}) is False
    # The marker wins over the version threshold in both directions: a future
    # line may keep version numbers while changing lines.
    assert is_pre_1_9_save({"version": 5, "created_line": "1.9"}) is False


def test_new_saves_carry_the_created_on_marker():
    path = Profile(name="Fresh Start").save()
    data = _decode_save_bytes(path.read_bytes())[0]
    assert data["created_line"] == "1.9"
    # The marker is signed like every other field; a clean reload needs no
    # rewrite and keeps the marker.
    loaded = Profile.load(path)
    assert loaded.needs_migration_resave is False
    assert loaded.created_line == "1.9"


# -- the load gate ------------------------------------------------------------


def test_1_8_save_refuses_to_load_and_stays_byte_for_byte_intact():
    path = write_1_8_save()
    before = path.read_bytes()

    with pytest.raises(LegacyCareerError) as refusal:
        Profile.load(path)

    assert refusal.value.name == "Old Timer"
    assert path.read_bytes() == before
    # Refused, not quarantined, not converted: no side files appear.
    assert not path.with_suffix(path.suffix + ".invalid").exists()
    assert not path.with_suffix(".ffsave.bak").exists()
    assert is_pre_1_9_save_file(path)


def test_ancient_plain_json_save_is_also_refused_untouched():
    path = write_ancient_json_save()
    before = path.read_bytes()
    with pytest.raises(LegacyCareerError):
        Profile.load(path)
    assert path.exists() and path.read_bytes() == before
    # No conversion to the packed container happened either.
    assert not path.with_suffix(".ffsave").exists()


def test_pre_marker_1_9_save_loads_and_is_stamped():
    path = write_pre_marker_1_9_save()
    loaded = Profile.load(path)
    assert loaded.name == "Tester"
    assert loaded.created_line == "1.9"
    # The load stamped the marker into the rewritten save, so the version
    # threshold backfill is only ever consulted once per career.
    on_disk = _decode_save_bytes(path.read_bytes())[0]
    assert on_disk["created_line"] == "1.9"
    assert Profile.load(path).needs_migration_resave is False


# -- the career menus ---------------------------------------------------------


def test_legacy_career_stays_listed_and_opens_the_notice(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.main_menu import LoadDriverState, MainMenuState
    from freight_fate.states.save_notice import LegacyCareerNoticeState

    path = write_1_8_save(name="Old Timer")
    before = path.read_bytes()
    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

        menu = MainMenuState(app.ctx)
        app.push_state(menu)
        labels = [item.text for item in menu.items]
        # Nothing is loadable, so there is no Continue item -- but the career
        # has not vanished: Choose career is offered and the welcome says why.
        assert not any(str(label).startswith("Continue") for label in labels)
        assert "Choose career" in labels
        assert any("earlier version" in text for text in spoken)

        picker = LoadDriverState(app.ctx)
        app.push_state(picker)
        assert picker.items[0].text == "Old Timer: career from an earlier version of Freight Fate"

        spoken.clear()
        picker.handle_event(key_event(pygame.K_RETURN))
        notice = app.state
        assert isinstance(notice, LegacyCareerNoticeState)
        assert any("Nothing was lost" in text for text in spoken)
        assert any("still works in Freight Fate 1.8" in text for text in spoken)

        # The first choice starts a fresh career; Escape instead returns to
        # the career list without changing anything.
        assert notice.items[0].text == "Start a new career"
        notice.handle_event(key_event(pygame.K_ESCAPE))
        assert app.state is picker

        # Through all of it the old save was never touched.
        assert path.read_bytes() == before
        assert app.ctx.profile is None
    finally:
        app.shutdown()


def test_notice_start_new_career_opens_name_entry(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.main_menu import LoadDriverState, NameEntryState

    write_1_8_save(name="Old Timer")
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        picker = LoadDriverState(app.ctx)
        app.push_state(picker)
        picker.handle_event(key_event(pygame.K_RETURN))  # open the notice
        app.state.handle_event(key_event(pygame.K_RETURN))  # Start a new career
        assert isinstance(app.state, NameEntryState)
    finally:
        app.shutdown()


def test_new_career_will_not_overwrite_a_same_named_legacy_save(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import DEFAULT_CITY
    from freight_fate.models.start_options import DEFAULT_START_KEY
    from freight_fate.states.main_menu_career import HomeCityState

    path = write_1_8_save(name="Old Timer")
    before = path.read_bytes()
    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        region = app.ctx.world.cities[DEFAULT_CITY].region
        picker = HomeCityState(app.ctx, "Old Timer", DEFAULT_START_KEY, region, [DEFAULT_CITY])
        app.push_state(picker)

        picker.handle_event(key_event(pygame.K_RETURN))

        assert any("different driver name" in text for text in spoken)
        assert app.ctx.profile is None
        assert path.read_bytes() == before
        # The picker is still up; the career chain was not torn down.
        assert app.state is picker
    finally:
        app.shutdown()
