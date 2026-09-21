"""The manual-playtest sandbox must never carry the real account into a drive.

``tools/playtest_sandbox.py`` exists for one guarantee: a throwaway career
driven in the sandbox cannot back itself up, cannot heartbeat onto the drivers
board, and cannot touch the public profile. That guarantee is not a property of
the tool's intentions -- it is the fact that ``OnlineIdentity.load()`` finds no
``online.json`` there. These pin both halves: the seeding never copies an
identity in, and the audit refuses a sandbox that has one anyway.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_tool():
    path = Path(__file__).resolve().parents[1] / "tools" / "playtest_sandbox.py"
    spec = importlib.util.spec_from_file_location("playtest_sandbox", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fake_real_saves(root: Path) -> Path:
    """A stand-in for the owner's ``saves/``: settings, careers, identity."""
    source = root / "saves"
    (source / "profiles").mkdir(parents=True)
    (source / "settings.json").write_text(
        json.dumps({"cloud_saves": True, "online_presence": True, "master_volume": 0.5}),
        encoding="utf-8",
    )
    (source / "online.json").write_text(
        json.dumps({"driver_id": "d" * 16, "driver_token": "t" * 40}), encoding="utf-8"
    )
    (source / "online.json.pre-clerk.bak").write_text("{}", encoding="utf-8")
    (source / "online.token").write_text("t" * 40, encoding="utf-8")
    (source / "cloud_saves.json").write_text(json.dumps({"slots": {}}), encoding="utf-8")
    (source / "profiles" / "Playtest.ffsave").write_text("career", encoding="utf-8")
    (source / "profiles" / "Old.json.bak").write_text("not a career", encoding="utf-8")
    return source


def test_seeding_carries_careers_but_never_the_identity(tmp_path):
    tool = _load_tool()
    source = _fake_real_saves(tmp_path)
    sandbox = tmp_path / "sandbox"

    tool.prepare(sandbox, source=source)

    assert (sandbox / "profiles" / "Playtest.ffsave").is_file()
    # The stale ``.json.bak`` leftovers are not careers the game loads, so a
    # sandbox does not want them cluttering its career list either.
    assert not (sandbox / "profiles" / "Old.json.bak").exists()
    assert not (sandbox / "online.json").exists()
    assert not (sandbox / "online.token").exists()
    assert not (sandbox / "cloud_saves.json").exists()
    assert tool.audit(sandbox) == []


def test_the_seeded_settings_have_every_publishing_switch_off(tmp_path):
    tool = _load_tool()
    source = _fake_real_saves(tmp_path)
    sandbox = tmp_path / "sandbox"

    tool.prepare(sandbox, source=source)

    settings = json.loads((sandbox / "settings.json").read_text(encoding="utf-8"))
    for key, value in tool.OFFLINE_SETTINGS.items():
        assert settings[key] == value, key
    # Everything else is copied through, because the point of seeding real
    # settings is that the drive reproduces what a player would get.
    assert settings["master_volume"] == 0.5


def test_no_careers_leaves_the_sandbox_empty(tmp_path):
    tool = _load_tool()
    source = _fake_real_saves(tmp_path)
    sandbox = tmp_path / "sandbox"

    tool.prepare(sandbox, careers=False, source=source)

    assert not (sandbox / "profiles").exists()


def test_the_audit_names_an_identity_that_got_in_somehow(tmp_path):
    """The audit is the guard, so it has to fail on a sandbox somebody
    signed in by hand -- including the backup spellings of the file."""
    tool = _load_tool()
    source = _fake_real_saves(tmp_path)
    sandbox = tmp_path / "sandbox"
    tool.prepare(sandbox, source=source)

    (sandbox / "online.json.playtest1.bak").write_text("{}", encoding="utf-8")

    problems = tool.audit(sandbox)
    assert any("online.json.playtest1.bak" in p for p in problems)


def test_the_audit_names_a_publishing_switch_turned_back_on(tmp_path):
    tool = _load_tool()
    source = _fake_real_saves(tmp_path)
    sandbox = tmp_path / "sandbox"
    tool.prepare(sandbox, source=source)

    settings = json.loads((sandbox / "settings.json").read_text(encoding="utf-8"))
    settings["cloud_saves"] = True
    (sandbox / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    assert any("cloud_saves" in p for p in tool.audit(sandbox))


def test_a_sandbox_data_dir_has_no_driver_at_all(tmp_path, monkeypatch):
    """The guarantee itself, through the game's own loader.

    Every cloud backup, presence heartbeat and profile update in the game
    hangs off ``OnlineIdentity.load()`` returning something. In a sandbox it
    returns None, so those are branches the drive never takes.
    """
    from freight_fate.online_presence import OnlineIdentity

    tool = _load_tool()
    source = _fake_real_saves(tmp_path)
    sandbox = tmp_path / "sandbox"
    tool.prepare(sandbox, source=source)
    monkeypatch.setenv("FREIGHT_FATE_DATA_DIR", str(sandbox))
    # The token cache is a class attribute that outlives one identity, and a
    # cached token would mask exactly the failure this test is here to catch.
    monkeypatch.setattr(OnlineIdentity, "_token_cache", {})

    assert OnlineIdentity.path() == sandbox / "online.json"
    assert OnlineIdentity.load() is None


def test_the_real_saves_are_only_ever_read(tmp_path):
    """Seeding copies out of ``saves/``; it must never write back into it."""
    tool = _load_tool()
    source = _fake_real_saves(tmp_path)
    before = {p: p.stat().st_mtime_ns for p in sorted(source.rglob("*")) if p.is_file()}

    tool.prepare(tmp_path / "sandbox", source=source)

    after = {p: p.stat().st_mtime_ns for p in sorted(source.rglob("*")) if p.is_file()}
    assert after == before
