"""Curated release-note generation for build snapshots."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml

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

    assert "Preview snapshot for players" in notes
    assert "## Changes since the previous snapshot" in notes
    assert "## Added" in notes
    assert "- **Dispatch.** New spoken board details." in notes
    assert "chore: seed changelog" not in notes


def test_first_career_snapshot_uses_accurate_release_notes_heading(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    repo = make_repo(
        tmp_path,
        changelog("### Added\n- **Career.** A new driver can begin a career.\n"),
    )
    monkeypatch.setattr(release_notes, "ROOT", repo)

    notes = release_notes.nightly_notes(first_snapshot=True)

    assert "## Changes in this snapshot" in notes
    assert "Changes since the previous snapshot" not in notes


def test_first_career_snapshot_notes_fit_github_without_cutting_entries(tmp_path, monkeypatch):
    release_notes = load_release_notes_module()
    added_entries = "\n".join(
        f"- **Career improvement {index}.** " + ("Player-facing detail. " * 90)
        for index in range(100)
    )
    fixed_entries = "\n".join(
        f"- **Career fix {index}.** " + ("Clear fix detail. " * 90) for index in range(100)
    )
    repo = make_repo(
        tmp_path,
        changelog(f"### Added\n{added_entries}\n\n### Fixed\n{fixed_entries}\n"),
    )
    monkeypatch.setattr(release_notes, "ROOT", repo)

    notes = release_notes.nightly_notes(first_snapshot=True)

    assert len(notes) <= release_notes.GITHUB_RELEASE_NOTES_SAFE_CHARACTERS
    assert "### Added" in notes
    assert "### Fixed" in notes
    assert "\n## Added\n" not in notes
    assert "\n## Fixed\n" not in notes
    assert "**Career improvement 0.**" in notes
    assert "**Career fix 0.**" in notes
    assert "## Complete change list" in notes
    assert "CHANGELOG.md" in notes
    emitted = {
        release_notes.format_entry(entry)
        for section in release_notes.parse_sections(notes, min_heading_level=3)
        for entry in section.entries
    }
    source = {
        release_notes.format_entry(entry)
        for entry in [*added_entries.splitlines(), *fixed_entries.splitlines()]
    }
    assert emitted
    assert emitted <= source


def test_release_notes_size_check_rejects_oversized_input(tmp_path, capsys):
    release_notes = load_release_notes_module()
    notes = tmp_path / "notes.md"
    notes.write_text("x" * 101, encoding="utf-8")

    result = release_notes.main(["check-size", "--input", str(notes), "--max-characters", "100"])

    captured = capsys.readouterr()
    assert result == 1
    assert "101 characters" in captured.err
    assert "100-character publication limit" in captured.err


def test_release_notes_size_check_counts_crlf_characters(tmp_path, capsys):
    release_notes = load_release_notes_module()
    notes = tmp_path / "notes.md"
    notes.write_bytes(b"x\r\n" * 40)

    result = release_notes.main(["check-size", "--input", str(notes), "--max-characters", "100"])

    assert result == 1
    assert "120 characters" in capsys.readouterr().err


def test_first_snapshot_budget_reserves_the_written_newline():
    release_notes = load_release_notes_module()

    assert release_notes.first_snapshot_fits("x" * 119_999)
    assert not release_notes.first_snapshot_fits("x" * 120_000)


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
        "Preview snapshot.\n\n"
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
        version_only_changelog("## 1.6.0 - 2026-06-15\n\n### Added\n- Old player-facing note.\n"),
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
    out = release_notes.format_sections(
        [
            section("Added", ("- Unreleased badge.",)),
            section("Added", ("- Staged feature.",)),
        ]
    )

    assert out.count("## Added") == 1
    assert "- Unreleased badge." in out
    assert "- Staged feature." in out


def test_should_build_nightly_ignores_internal_version_block_entries(tmp_path, monkeypatch, capsys):
    release_notes = load_release_notes_module()
    repo = make_repo(
        tmp_path,
        version_only_changelog(
            "## 1.6.0 - 2026-06-15\n\n### Internal\n- Old build script cleanup.\n"
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
    args = type(
        "Args",
        (),
        {
            "previous_tag": "nightly-20260615",
            "exclude_notes": "",
            "latest_stable_tag": "",
            "exclude_stable_notes": "",
            "head": "HEAD",
        },
    )()

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
    args = type(
        "Args",
        (),
        {
            "previous_tag": "nightly-20260615",
            "exclude_notes": "",
            "latest_stable_tag": "",
            "exclude_stable_notes": "",
            "head": "HEAD",
        },
    )()

    assert release_notes.should_build_nightly_command(args) == 0

    assert "should_build=true" in capsys.readouterr().out


def test_should_build_nightly_skips_without_entries_or_marker(tmp_path, monkeypatch, capsys):
    release_notes = load_release_notes_module()
    repo = make_repo(tmp_path, changelog("### Added\n- Old curated note.\n"))
    git(repo, "tag", "nightly-20260615")
    (repo / "README.md").write_text("Docs only\n", encoding="utf-8")
    commit(repo, "docs: update readme")
    monkeypatch.setattr(release_notes, "ROOT", repo)
    args = type(
        "Args",
        (),
        {
            "previous_tag": "nightly-20260615",
            "exclude_notes": "",
            "latest_stable_tag": "",
            "exclude_stable_notes": "",
            "head": "HEAD",
        },
    )()

    assert release_notes.should_build_nightly_command(args) == 0

    assert "should_build=false" in capsys.readouterr().out


def test_should_build_nightly_allows_explicit_marker(tmp_path, monkeypatch, capsys):
    release_notes = load_release_notes_module()
    repo = make_repo(tmp_path, changelog("### Added\n- Old curated note.\n"))
    git(repo, "tag", "nightly-20260615")
    (repo / "README.md").write_text("Nightly refresh\n", encoding="utf-8")
    commit(repo, "chore: refresh snapshot\n\nnightly: build")
    monkeypatch.setattr(release_notes, "ROOT", repo)
    args = type(
        "Args",
        (),
        {
            "previous_tag": "nightly-20260615",
            "exclude_notes": "",
            "latest_stable_tag": "",
            "exclude_stable_notes": "",
            "head": "HEAD",
        },
    )()

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


def test_check_accepts_single_push_release_sync(tmp_path, monkeypatch, capsys):
    """A release-sync push lands new bullets already under a tagged version
    heading (the v1.8.3 release did the merge and the heading in one push);
    the changelog gate must credit those bullets to the push, not dismiss
    the block as already released."""
    release_notes = load_release_notes_module()
    stable_history = "## 1.8.1 - 2026-07-13\n\n### Fixed\n- Old stable fix.\n"
    repo = make_repo(tmp_path, changelog("", stable_history))
    git(repo, "tag", "v1.8.1")
    base = git(repo, "rev-parse", "HEAD")

    (repo / "src").mkdir()
    (repo / "src" / "game.py").write_text("GAME = True\n", encoding="utf-8")
    (repo / "CHANGELOG.md").write_text(
        changelog(
            "",
            "## 1.8.3 - 2026-07-14\n\n### Fixed\n- Restoring a cloud backup works again.\n\n"
            + stable_history,
        ),
        encoding="utf-8",
    )
    commit(repo, "release: merge dev into main for 1.8.3")
    git(repo, "tag", "v1.8.3")
    monkeypatch.setattr(release_notes, "ROOT", repo)

    args = release_notes.argparse.Namespace(base=base, head="HEAD")
    assert release_notes.check_command(args) == 0

    # The same push without new bullets must still fail the gate.
    git(repo, "tag", "-d", "v1.8.3")
    (repo / "CHANGELOG.md").write_text(
        changelog("", "## 1.8.3 - 2026-07-14\n\n" + stable_history), encoding="utf-8"
    )
    commit(repo, "release: heading only")
    capsys.readouterr()
    assert release_notes.check_command(args) == 1


def test_build_workflow_uses_curated_nightly_decision_and_notes():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build.yml"
    ).read_text(encoding="utf-8")

    assert "tools/release_notes.py should-build-nightly" in workflow
    assert "--exclude-notes previous-notes.md" in workflow
    assert "--exclude-stable-notes latest-stable-notes.md" in workflow
    assert "tools/release_notes.py nightly" in workflow
    assert 'git diff --name-only "$LAST_TAG"..HEAD' not in workflow
    assert "macos-arm64.zip" not in workflow


def test_career_19_snapshot_workflow_contract():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build-career-1.9.yml"
    ).read_text(encoding="utf-8")

    assert 'CAREER_BRANCH: "feat/career-1.9"' in workflow
    assert "group: career-19-snapshot\n" in workflow
    assert "career-19-snapshot-${{ github.ref }}" not in workflow
    assert 'cron: "37 2 * * *"' in workflow
    assert "tag=1.9-tester-$(date -u +%Y%m%d)" in workflow
    assert "commit_sha: ${{ steps.check.outputs.commit_sha }}" in workflow
    assert 'echo "commit_sha=$(git rev-parse HEAD)"' in workflow
    # Windows, macOS, Linux build, the Linux distro smoke, and the release.
    assert workflow.count("ref: ${{ needs.prepare.outputs.commit_sha }}") == 5
    assert 'git tag --list "1.9-tester-*"' in workflow
    assert "tools/release_notes.py should-build-nightly" in workflow
    assert "tools/release_notes.py nightly" in workflow
    assert "tools/release_notes.py nightly --first-snapshot" in workflow
    assert "tools/release_notes.py check-size --input notes.md --max-characters 120000" in workflow
    assert "./build-release.ps1" in workflow
    assert "windows-portable.zip" in workflow
    assert "macos-arm64.zip" in workflow
    assert "--prerelease" in workflow
    assert "COMMIT_SHA: ${{ needs.prepare.outputs.commit_sha }}" in workflow
    assert '--target "$COMMIT_SHA"' in workflow
    assert '--target "$CAREER_BRANCH"' not in workflow
    assert "needs.build_windows.result == 'success'" in workflow
    assert "needs.build_macos.result == 'success'" in workflow
    assert "needs.build_linux.result == 'success'" in workflow
    assert "needs.smoke_linux.result == 'success'" in workflow


def test_career_19_snapshot_builds_and_boots_a_linux_release():
    """The Linux tarball and AppImage ship only after both boot untouched on
    the popular distributions, from a build whose glibc floor is 22.04's."""
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build-career-1.9.yml"
    ).read_text(encoding="utf-8")
    assert "tools/build_release.py --rust --smoke" in workflow
    assert "tools/build_appimage.py --rust" in workflow
    assert "bash /work/tools/linux_smoke.sh" in workflow
    # One build job, two native legs: the PC one on 22.04 and the ARM64 one
    # (the Blazie BT Speak and BT Braille, Raspberry Pi) on GitHub's
    # hosted ARM runner of the same release, so both carry the same glibc
    # floor. Each leg uploads its own pair of downloads.
    assert "            runner: ubuntu-22.04\n" in workflow
    assert "            runner: ubuntu-22.04-arm\n" in workflow
    assert "            tarball: linux-x64\n" in workflow
    assert "            tarball: linux-arm64\n" in workflow
    assert "name: Linux-${{ matrix.arch }}" in workflow
    assert "dist/FreightFate-*-${{ matrix.tarball }}.tar.gz" in workflow
    assert "dist/FreightFate-*-linux-${{ matrix.arch }}.AppImage" in workflow
    # The smoke matrix runs on both architectures, minus Arch on ARM64
    # (Docker Hub's archlinux image is amd64 only).
    assert "arch: [x86_64, aarch64]" in workflow
    assert (
        "runs-on: ${{ matrix.arch == 'aarch64' && 'ubuntu-24.04-arm' || 'ubuntu-latest' }}"
        in workflow
    )
    assert (
        "        exclude:\n          - arch: aarch64\n            image: archlinux:latest\n"
        in workflow
    )
    for image in (
        "ubuntu:22.04",
        "ubuntu:24.04",
        "debian:12",
        "debian:13",
        "fedora:latest",
        "archlinux:latest",
        "opensuse/tumbleweed:latest",
    ):
        assert f"- {image}\n" in workflow, image
    assert (
        "FreightFate-*-linux-x64.tar.gz FreightFate-*-linux-x86_64.AppImage "
        "FreightFate-*-linux-arm64.tar.gz FreightFate-*-linux-aarch64.AppImage > checksums.txt"
        in workflow
    )

    smoke = (Path(__file__).resolve().parents[1] / "tools" / "linux_smoke.sh").read_text(
        encoding="utf-8"
    )
    # Speech is not disabled in the container boot: libprism.so and its
    # bundled glib are really opened, which is where a loader would object.
    assert "FREIGHT_FATE_NO_SPEECH" not in smoke
    assert "prism: loaded from" in smoke
    assert "Speech backend: Speech Dispatcher" in smoke
    assert 'grep -q " ERROR "' in smoke
    assert "--appimage-extract-and-run --smoke" in smoke
    assert "xvfb-run" in smoke
    # The script boots whichever pair matches the container it runs in.
    assert 'case "$(uname -m)"' in smoke
    assert "x86_64) tarball_arch=x64; appimage_arch=x86_64 ;;" in smoke
    assert "aarch64) tarball_arch=arm64; appimage_arch=aarch64 ;;" in smoke
    assert '/work/dist/FreightFate-*-linux-"$tarball_arch".tar.gz' in smoke
    assert '/work/dist/FreightFate-*-linux-"$appimage_arch".AppImage' in smoke


def test_career_19_snapshot_builds_an_apple_silicon_macos_release():
    workflow_path = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build-career-1.9.yml"
    )
    workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    jobs = workflow["jobs"]
    mac = jobs["build_macos"]

    assert mac["runs-on"] == "macos-26"
    steps = mac["steps"]
    named_steps = {
        step["name"]: (index, step) for index, step in enumerate(steps) if "name" in step
    }
    assert any(step.get("uses") == "astral-sh/setup-uv@v8.2.0" for step in steps)
    assert named_steps["Install the pinned Rust toolchain"][1]["run"] == "rustup show"
    # No brewed SDL anywhere in the job: Homebrew's sdl2 is sdl2-compat,
    # which loads SDL3 at runtime and dies on player Macs. SDL2 is compiled
    # into the executable instead.
    assert all(
        "brew install" not in step.get("run", "") or "sdl" not in step.get("run", "")
        for step in steps
    )
    assert "uv run python tools/fetch_bass.py\n" in named_steps["Fetch BASS"][1]["run"]
    assert "uv run python tools/fetch_bass.py --check" in named_steps["Fetch BASS"][1]["run"]
    assert named_steps["Check Rust formatting"][1]["run"] == "cargo fmt --all --check"
    assert (
        named_steps["Lint Rust targets"][1]["run"]
        == "cargo clippy --all-targets --locked -- -D warnings"
    )
    assert named_steps["Test Rust workspace"][1]["run"] == "cargo test -p ff-core -p freight-fate"
    # The launch smoke is BACK on macOS: the hang that forced non-launch
    # verification was the boot probes, moved off the boot path 2026-08-30.
    # A packaged app that cannot boot must fail the build, not ship.
    assert (
        "uv run python tools/build_release.py --rust --smoke --tag"
        in named_steps["Build the macOS release"][1]["run"]
    )
    assert "--macos-non-launch-verify" not in named_steps["Build the macOS release"][1]["run"]
    assert "--skip-smoke" not in named_steps["Build the macOS release"][1]["run"]
    assert "Contents/MacOS/FreightFate" not in named_steps["Build the macOS release"][1]["run"]
    assert all("build-release.ps1" not in step.get("run", "") for step in steps)
    upload = next(step for step in steps if step.get("uses") == "actions/upload-artifact@v7")
    assert upload["with"]["path"] == "dist/FreightFate-*-macos-arm64.zip"


def test_career_19_release_requires_and_verifies_every_platform_archive():
    workflow_path = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build-career-1.9.yml"
    )
    workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    release = workflow["jobs"]["release"]

    assert release["needs"] == [
        "prepare",
        "build_windows",
        "build_macos",
        "build_linux",
        "smoke_linux",
    ]
    assert "needs.build_windows.result == 'success'" in release["if"]
    assert "needs.build_macos.result == 'success'" in release["if"]
    assert "needs.build_linux.result == 'success'" in release["if"]
    assert "needs.smoke_linux.result == 'success'" in release["if"]
    downloads = [
        step for step in release["steps"] if step.get("uses") == "actions/download-artifact@v7"
    ]
    assert {step["with"]["name"] for step in downloads} == {
        "Windows",
        "macOS-arm64",
        "Linux-x86_64",
        "Linux-aarch64",
    }
    assert all(step["with"]["path"] == "assets" for step in downloads)
    verify = next(
        step for step in release["steps"] if step.get("name") == "Verify release archives"
    )
    assert "assets/FreightFate-*-windows-portable.zip" in verify["run"]
    assert "assets/FreightFate-*-macos-arm64.zip" in verify["run"]
    assert "assets/FreightFate-*-linux-x64.tar.gz" in verify["run"]
    assert "assets/FreightFate-*-linux-x86_64.AppImage" in verify["run"]
    assert "assets/FreightFate-*-linux-arm64.tar.gz" in verify["run"]
    assert "assets/FreightFate-*-linux-aarch64.AppImage" in verify["run"]
    assert verify["run"].count('"${#') == 6
    checksum = next(
        step
        for step in release["steps"]
        if step.get("name") == "Prepare and verify release notes and checksums"
    )
    assert (
        "sha256sum FreightFate-*-windows-portable.zip FreightFate-*-macos-arm64.zip "
        "FreightFate-*-linux-x64.tar.gz FreightFate-*-linux-x86_64.AppImage "
        "FreightFate-*-linux-arm64.tar.gz FreightFate-*-linux-aarch64.AppImage" in checksum["run"]
    )


def test_player_manual_distinguishes_stable_and_career_19_mac_archives():
    manual = (Path(__file__).resolve().parents[1] / "docs" / "user-manual.md").read_text(
        encoding="utf-8"
    )

    assert "| macOS stable | `FreightFate-<version>-macos.zip` |" in manual
    assert (
        "| Career 1.9 macOS, Apple Silicon | `FreightFate-<version>-macos-arm64.zip` |"
    ) in manual
    assert "On an Intel Mac, the in-game updater will not offer" in manual


def test_player_manual_names_both_linux_architectures():
    manual = (Path(__file__).resolve().parents[1] / "docs" / "user-manual.md").read_text(
        encoding="utf-8"
    )
    assert "| Linux | `FreightFate-<version>-linux-x64.tar.gz` |" in manual
    assert "| Linux (AppImage) | `FreightFate-<version>-linux-x86_64.AppImage` |" in manual
    assert "| Linux ARM64 | `FreightFate-<version>-linux-arm64.tar.gz` |" in manual
    assert "| Linux ARM64 (AppImage) | `FreightFate-<version>-linux-aarch64.AppImage` |" in manual
    assert "BT Speak" in manual


def test_career_19_snapshot_prepares_bass_before_rust_validation():
    workflow_path = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build-career-1.9.yml"
    )
    workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    for job_name, build_step_name in (
        ("build_windows", "Build the portable release"),
        ("build_macos", "Build the macOS release"),
    ):
        steps = workflow["jobs"][job_name]["steps"]
        named_steps = {
            step["name"]: (index, step) for index, step in enumerate(steps) if "name" in step
        }

        bass_index, bass_step = named_steps["Fetch BASS"]
        assert "uv run python tools/fetch_bass.py\n" in bass_step["run"]
        assert "uv run python tools/fetch_bass.py --check" in bass_step["run"]
        assert bass_index < named_steps["Lint Rust targets"][0]
        assert bass_index < named_steps["Test Rust workspace"][0]
        assert named_steps["Test Rust workspace"][0] < named_steps[build_step_name][0]


def test_career_19_retry_is_bounded_to_one_delayed_attempt():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "retry-failed-nightly.yml"
    ).read_text(encoding="utf-8")

    assert "workflows: [Build, Career 1.9 snapshot]" in workflow
    assert "github.event.workflow_run.run_attempt == 1" in workflow
    assert 'if [ "$WORKFLOW_NAME" = "Career 1.9 snapshot" ]; then' in workflow
    assert 'TAG="1.9-tester-$(date -u +%Y%m%d)"' in workflow
    assert 'TARGET_BRANCH="feat/career-1.9"' in workflow
    assert 'TAG="nightly-$(date -u +%Y%m%d)"' in workflow
    assert 'TARGET_BRANCH="dev"' in workflow
    assert (
        'gh workflow run "Career 1.9 snapshot" --repo "$GITHUB_REPOSITORY" '
        '--ref "feat/career-1.9" -f dry_run=false'
    ) in workflow
    assert (
        'gh workflow run Build --repo "$GITHUB_REPOSITORY" --ref dev -f dry_run=false'
    ) in workflow
    assert '"$TAG already exists; the nightly recovered while waiting."' in workflow


def test_auto_base_follows_the_release_line_the_branch_was_cut_from(tmp_path, monkeypatch):
    """A hotfix is cut from main and never contains dev.

    Resolving its base to dev counted dev's bullets as already present and
    rejected the push over a changelog entry that was right there -- which is
    what the 1.8.6.2 hotfix hit. Ancestry cannot decide it either, since the
    two lines each carry commits the other does not.
    """
    release_notes = load_release_notes_module()
    repo = make_repo(tmp_path, changelog("- Seed entry."))
    monkeypatch.setattr(release_notes, "ROOT", repo)
    seed = git(repo, "rev-parse", "HEAD")  # git init's branch name varies
    # dev moves ahead of main, as it always is between releases...
    git(repo, "checkout", "-q", "-b", "dev")
    for n in range(4):
        (repo / f"dev{n}.txt").write_text("dev work\n", encoding="utf-8")
        commit(repo, f"feat: dev only {n}")
    git(repo, "update-ref", "refs/remotes/origin/dev", "HEAD")

    # ...and main carries release commits of its own that dev never sees, so
    # neither branch contains the other. That is the shape this has to read.
    git(repo, "checkout", "-q", "-b", "stable-line", seed)
    (repo / "release.txt").write_text("1.0\n", encoding="utf-8")
    commit(repo, "release: 1.0")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")

    git(repo, "checkout", "-q", "-b", "hotfix/1.0.1", "refs/remotes/origin/main")
    (repo / "fix.txt").write_text("hotfix\n", encoding="utf-8")
    commit(repo, "fix: stable only")
    assert release_notes.nearest_release_line() == "origin/main"
    assert release_notes.resolve_base("auto") == "origin/main"

    # An ordinary branch off dev still resolves to dev...
    git(repo, "checkout", "-q", "-b", "feat/thing", "refs/remotes/origin/dev")
    (repo / "feature.txt").write_text("feature\n", encoding="utf-8")
    commit(repo, "feat: a feature")
    assert release_notes.nearest_release_line() == "origin/dev"

    # ...and still does once dev has moved on without it.
    git(repo, "checkout", "-q", "dev")
    (repo / "more.txt").write_text("more dev work\n", encoding="utf-8")
    commit(repo, "feat: more dev")
    git(repo, "update-ref", "refs/remotes/origin/dev", "HEAD")
    git(repo, "checkout", "-q", "feat/thing")
    assert release_notes.nearest_release_line() == "origin/dev"

    # An explicit base is never second-guessed.
    assert release_notes.resolve_base("origin/main") == "origin/main"
