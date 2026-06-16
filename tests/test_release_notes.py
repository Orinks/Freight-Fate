"""Curated release-note generation for build snapshots."""

import importlib.util
import subprocess
import sys
from pathlib import Path

from freight_fate.updater import flatten_markdown


def load_release_notes_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "release_notes.py"
    spec = importlib.util.spec_from_file_location("release_notes", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=repo,
        text=True,
        encoding="utf-8",
    ).strip()


def commit(repo: Path, message: str) -> None:
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)


def make_repo(tmp_path: Path, changelog: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "tests@example.test")
    git(repo, "config", "user.name", "Tests")
    (repo / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    commit(repo, "chore: seed changelog")
    return repo


def changelog(unreleased: str, stable: str = "") -> str:
    return f"# Changelog\n\n## Unreleased\n\n{unreleased}\n\n{stable}".rstrip() + "\n"


def test_nightly_notes_use_curated_unreleased_entries(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    repo = make_repo(
        tmp_path,
        changelog("### Added\n- **Dispatch.** New spoken board details.\n"),
    )
    monkeypatch.setattr(release_notes, "ROOT", repo)

    notes = release_notes.nightly_notes()

    assert "Automated developer snapshot" in notes
    assert "## Added" in notes
    assert "- **Dispatch.** New spoken board details." in notes
    assert "chore: seed changelog" not in notes


def test_stable_notes_extract_matching_version_block(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    repo = make_repo(
        tmp_path,
        changelog(
            "### Added\n- Next thing.\n",
            "## 1.6.0 - 2026-06-15\n\n### Fixed\n- Stable fix.\n",
        ),
    )
    monkeypatch.setattr(release_notes, "ROOT", repo)

    assert release_notes.stable_notes("v1.6.0") == "## Fixed\n- Stable fix."


def test_stable_notes_fall_back_to_unreleased_when_version_missing(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    repo = make_repo(tmp_path, changelog("### Changed\n- Upcoming change.\n"))
    monkeypatch.setattr(release_notes, "ROOT", repo)

    assert release_notes.stable_notes("9.9.9") == "## Changed\n- Upcoming change."


def test_nightly_notes_exclude_entries_from_previous_nightly(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    repo = make_repo(tmp_path, changelog("### Added\n- Old curated note.\n"))
    git(repo, "tag", "nightly-20260615")
    (repo / "CHANGELOG.md").write_text(
        changelog("### Added\n- Old curated note.\n- New curated note.\n"),
        encoding="utf-8",
    )
    commit(repo, "feat: add new work")
    monkeypatch.setattr(release_notes, "ROOT", repo)

    notes = release_notes.nightly_notes(previous_tag="nightly-20260615")

    assert "- New curated note." in notes
    assert "- Old curated note." not in notes


def test_nightly_notes_no_entry_behavior_is_explicit(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    repo = make_repo(tmp_path, changelog(""))
    git(repo, "tag", "nightly-20260615")
    (repo / "README.md").write_text("Docs only\n", encoding="utf-8")
    commit(repo, "docs: update readme")
    monkeypatch.setattr(release_notes, "ROOT", repo)

    notes = release_notes.nightly_notes(previous_tag="nightly-20260615")

    assert notes.endswith("- No user-facing changes")


def test_should_build_nightly_uses_curated_entries(tmp_path, monkeypatch, capsys):
    release_notes = load_release_notes_module()
    repo = make_repo(tmp_path, changelog("### Added\n- Old curated note.\n"))
    git(repo, "tag", "nightly-20260615")
    (repo / "CHANGELOG.md").write_text(
        changelog("### Added\n- Old curated note.\n- New curated note.\n"),
        encoding="utf-8",
    )
    commit(repo, "feat: add new work")
    monkeypatch.setattr(release_notes, "ROOT", repo)
    args = type("Args", (), {
        "previous_tag": "nightly-20260615",
        "exclude_notes": "",
        "latest_stable_tag": "",
        "exclude_stable_notes": "",
        "head": "HEAD",
    })()

    assert release_notes.should_build_nightly_command(args) == 0

    assert "should_build=true" in capsys.readouterr().out


def test_should_build_nightly_skips_without_entries_or_marker(
    tmp_path, monkeypatch, capsys
):
    release_notes = load_release_notes_module()
    repo = make_repo(tmp_path, changelog("### Added\n- Old curated note.\n"))
    git(repo, "tag", "nightly-20260615")
    (repo / "README.md").write_text("Docs only\n", encoding="utf-8")
    commit(repo, "docs: update readme")
    monkeypatch.setattr(release_notes, "ROOT", repo)
    args = type("Args", (), {
        "previous_tag": "nightly-20260615",
        "exclude_notes": "",
        "latest_stable_tag": "",
        "exclude_stable_notes": "",
        "head": "HEAD",
    })()

    assert release_notes.should_build_nightly_command(args) == 0

    assert "should_build=false" in capsys.readouterr().out


def test_should_build_nightly_allows_explicit_marker(tmp_path, monkeypatch, capsys):
    release_notes = load_release_notes_module()
    repo = make_repo(tmp_path, changelog("### Added\n- Old curated note.\n"))
    git(repo, "tag", "nightly-20260615")
    (repo / "README.md").write_text("Nightly refresh\n", encoding="utf-8")
    commit(repo, "chore: refresh snapshot\n\nnightly: build")
    monkeypatch.setattr(release_notes, "ROOT", repo)
    args = type("Args", (), {
        "previous_tag": "nightly-20260615",
        "exclude_notes": "",
        "latest_stable_tag": "",
        "exclude_stable_notes": "",
        "head": "HEAD",
    })()

    assert release_notes.should_build_nightly_command(args) == 0

    assert "should_build=true" in capsys.readouterr().out


def test_generated_notes_flatten_to_speakable_lines(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    repo = make_repo(
        tmp_path,
        changelog("### Added\n- **Cruise control.** See [manual](https://example.test).\n"),
    )
    monkeypatch.setattr(release_notes, "ROOT", repo)

    spoken = flatten_markdown(release_notes.nightly_notes())

    assert "Added" in spoken
    assert "Cruise control. See manual." in spoken
    assert all("**" not in line and "https://" not in line for line in spoken)
