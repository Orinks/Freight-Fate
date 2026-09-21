"""The watcher's closing re-audit must catch a sandbox that reached the account.

The sandbox itself is Rust (``crates/freight-fate/src/playtest/sandbox.rs``,
tested in ``tests/it/playtest_sandbox.rs``); the watcher mirrors its audit so
the end-of-session summary can say whether the drive stayed isolated.
"""

from __future__ import annotations

import json

import playtest_watch


def test_the_audit_names_an_identity_including_backup_spellings(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"cloud_saves": False}), encoding="utf-8")
    assert playtest_watch.audit(tmp_path) == []

    (tmp_path / "online.json.playtest1.bak").write_text("{}", encoding="utf-8")
    (tmp_path / "meaningful_play.json").write_text("{}", encoding="utf-8")
    problems = playtest_watch.audit(tmp_path)
    assert any("online.json.playtest1.bak" in p for p in problems)
    assert any("meaningful_play.json" in p for p in problems)


def test_the_audit_names_a_publishing_switch_turned_back_on(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"cloud_saves": True}), encoding="utf-8")
    assert playtest_watch.audit(tmp_path) == ["settings.json still has cloud_saves on"]
