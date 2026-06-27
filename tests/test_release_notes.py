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


def version_only_changelog(version_block: str, stable: str = "") -> str:
    return f"# Changelog\n\n{version_block}\n\n{stable}".rstrip() + "\n"


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


def test_nightly_notes_exclude_previous_release_body_sections(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    repo = make_repo(tmp_path, changelog("### Fixed\n- **Updater.** Packaged updates work.\n"))
    git(repo, "tag", "nightly-20260615")
    (repo / "CHANGELOG.md").write_text(
        changelog(
            "### Fixed\n"
            "- **Updater.** Packaged updates work.\n"
            "- **Help.** Upgrade help explains what to buy.\n"
        ),
        encoding="utf-8",
    )
    commit(repo, "docs: improve help")
    previous_notes = repo / "previous-notes.md"
    previous_notes.write_text(
        "Automated developer snapshot.\n\n"
        "## Changes since the previous snapshot\n\n"
        "## Fixed\n"
        "- **Updater.** Packaged updates work.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(release_notes, "ROOT", repo)

    notes = release_notes.nightly_notes(
        previous_tag="nightly-20260615",
        exclude_notes=str(previous_notes),
    )

    assert "- **Help.** Upgrade help explains what to buy." in notes
    assert "- **Updater.** Packaged updates work." not in notes


def test_nightly_notes_exclude_stable_release_body_sections(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    repo = make_repo(tmp_path, changelog("### Fixed\n- **Updater.** Packaged updates work.\n"))
    git(repo, "tag", "nightly-20260615")
    (repo / "CHANGELOG.md").write_text(
        changelog(
            "### Added\n"
            "- **Radio.** New radio chatter.\n"
            "### Fixed\n"
            "- **Updater.** Packaged updates work.\n"
            "- **Help.** Upgrade help explains what to buy.\n"
        ),
        encoding="utf-8",
    )
    commit(repo, "docs: improve help")
    stable_notes = repo / "stable-notes.md"
    stable_notes.write_text(
        "## Added\n"
        "- **Radio.** New radio chatter.\n\n"
        "## Fixed\n"
        "- **Updater.** Packaged updates work.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(release_notes, "ROOT", repo)

    notes = release_notes.nightly_notes(
        previous_tag="nightly-20260615",
        exclude_stable_notes=str(stable_notes),
    )

    assert "- **Help.** Upgrade help explains what to buy." in notes
    assert "- **Radio.** New radio chatter." not in notes
    assert "- **Updater.** Packaged updates work." not in notes


def test_nightly_notes_use_new_version_block_entries(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    repo = make_repo(
        tmp_path,
        version_only_changelog(
            "## 1.6.0 - 2026-06-15\n\n"
            "### Added\n- Old player-facing note.\n"
        ),
    )
    git(repo, "tag", "nightly-20260615")
    (repo / "CHANGELOG.md").write_text(
        version_only_changelog(
            "## 1.6.0 - 2026-06-15\n\n"
            "### Added\n"
            "- Old player-facing note.\n"
            "- New player-facing note.\n"
        ),
        encoding="utf-8",
    )
    commit(repo, "feat: add player-facing work")
    monkeypatch.setattr(release_notes, "ROOT", repo)

    notes = release_notes.nightly_notes(previous_tag="nightly-20260615")

    assert "- New player-facing note." in notes
    assert "- Old player-facing note." not in notes


def test_nightly_notes_skip_already_released_version_block(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    base = changelog(
        "### Added\n- Pre-release staged note.\n",
        "## 1.6.0 - 2026-06-15\n\n### Added\n- Shipped feature.\n",
    )
    repo = make_repo(tmp_path, base)
    git(repo, "tag", "nightly-20260615")
    git(repo, "tag", "v1.6.0")
    (repo / "CHANGELOG.md").write_text(
        changelog(
            "### Added\n- Pre-release staged note.\n- **Achievements.** New badges.\n",
            "## 1.6.0 - 2026-06-15\n\n### Added\n- Shipped feature.\n",
        ),
        encoding="utf-8",
    )
    commit(repo, "feat: achievements")
    monkeypatch.setattr(release_notes, "ROOT", repo)

    notes = release_notes.nightly_notes(previous_tag="nightly-20260615")

    # New Unreleased work surfaces even though a released version block shares
    # the same "Added" subsection title.
    assert "- **Achievements.** New badges." in notes
    # The shipped 1.6.0 block has a stable tag, so it is not re-advertised.
    assert "- Shipped feature." not in notes
    # Already carried in the previous snapshot.
    assert "- Pre-release staged note." not in notes


def test_format_sections_merges_duplicate_titles(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    section = release_notes.ChangelogSection
    out = release_notes.format_sections([
        section("Added", ("- Unreleased badge.",)),
        section("Added", ("- Staged feature.",)),
    ])

    assert out.count("## Added") == 1
    assert "- Unreleased badge." in out
    assert "- Staged feature." in out


def test_should_build_nightly_ignores_internal_version_block_entries(
    tmp_path, monkeypatch, capsys
):
    release_notes = load_release_notes_module()
    repo = make_repo(
        tmp_path,
        version_only_changelog(
            "## 1.6.0 - 2026-06-15\n\n"
            "### Internal\n- Old build script cleanup.\n"
        ),
    )
    git(repo, "tag", "nightly-20260615")
    (repo / "CHANGELOG.md").write_text(
        version_only_changelog(
            "## 1.6.0 - 2026-06-15\n\n"
            "### Internal\n"
            "- Old build script cleanup.\n"
            "- New test-only helper.\n"
        ),
        encoding="utf-8",
    )
    commit(repo, "test: add helper")
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
        changelog(
            "### Added\n"
            "- **Cruise control.** See [manual](https://example.test)\n"
            "  before setting speed.\n"
        ),
    )
    monkeypatch.setattr(release_notes, "ROOT", repo)

    spoken = flatten_markdown(release_notes.nightly_notes())

    assert "Added" in spoken
    assert "Cruise control. See manual before setting speed." in spoken
    assert all("**" not in line and "https://" not in line for line in spoken)


def test_build_workflow_uses_curated_nightly_decision_and_notes():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build.yml"
    ).read_text(encoding="utf-8")

    assert "tools/release_notes.py should-build-nightly" in workflow
    assert "--exclude-notes previous-notes.md" in workflow
    assert "--exclude-stable-notes latest-stable-notes.md" in workflow
    assert "tools/release_notes.py nightly" in workflow
    assert "git diff --name-only \"$LAST_TAG\"..HEAD" not in workflow
