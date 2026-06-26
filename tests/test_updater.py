"""Update discovery, channel resolution, notes flattening, apply scripts."""

import importlib.util
import json
import logging
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

from freight_fate import updater
from freight_fate.settings import Settings
from freight_fate.updater import (
    BuildInfo,
    build_info_from_dict,
    dev_update_from,
    flatten_markdown,
    parse_version,
    pick_asset,
    resolve_channel,
    stable_update_from,
    write_apply_script,
)


def release(tag, prerelease=False, body="", published="",
            assets=("-windows-portable.zip",
                    "-macos.zip",
                    "-linux-x64.tar.gz")):
    return {
        "tag_name": tag,
        "prerelease": prerelease,
        "body": body,
        "published_at": published,
        "assets": [
            {"name": f"FreightFate-{tag}{suffix}",
             "browser_download_url": f"https://example.test/{tag}/{suffix}",
             "size": 50_000_000}
            for suffix in assets
        ],
    }


def load_build_release_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_release.py"
    spec = importlib.util.spec_from_file_location("build_release", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_linux_prism_dependency_dir(build_release, build_dir: Path) -> None:
    dependency_dir = build_dir / build_release.PRISM_DEPENDENCY_DIR
    dependency_dir.mkdir(parents=True)
    (dependency_dir / "libglibmm-test.so.1.3.0").write_text("", encoding="utf-8")


# -- version parsing and channels --------------------------------------------


def test_parse_version_orders_semver():
    assert parse_version("v1.6.0") > parse_version("1.5.0")
    assert parse_version("1.10.0") > parse_version("1.9.3")
    assert parse_version("garbage") == (0,)


def test_resolve_channel_prefers_explicit_setting():
    nightly = BuildInfo(tag="nightly-20260610", channel="dev", built_at="2026-06-10")
    assert resolve_channel("stable", nightly) == "stable"
    assert resolve_channel("dev", None) == "dev"


def test_resolve_channel_follows_build_when_unset():
    nightly = BuildInfo(tag="nightly-20260610", channel="dev", built_at="2026-06-10")
    assert resolve_channel("", nightly) == "dev"
    assert resolve_channel("", None) == "stable"


# -- stable channel -----------------------------------------------------------


def test_stable_update_found_when_newer():
    info = stable_update_from(release("v9.9.9", body="- Big stuff"), "1.5.0")
    assert info is not None
    assert info.tag == "v9.9.9"
    assert "9.9.9" in info.title
    assert info.notes == ["Big stuff"]
    assert info.asset_url.startswith("https://example.test/")


def test_stable_no_update_when_current_or_older():
    assert stable_update_from(release("v1.5.0"), "1.5.0") is None
    assert stable_update_from(release("v1.4.0"), "1.5.0") is None


def test_stable_no_update_without_platform_asset():
    assert stable_update_from(release("v9.9.9", assets=()), "1.5.0") is None


# -- dev channel --------------------------------------------------------------


def test_dev_update_skips_non_nightlies_and_finds_newer():
    releases = [
        release("v1.5.0"),                                  # stable, ignored
        release("nightly-20260611", prerelease=True),
        release("nightly-20260610", prerelease=True),
    ]
    build = BuildInfo(tag="nightly-20260610", channel="dev", built_at="2026-06-10")
    info = dev_update_from(releases, build)
    assert info is not None
    assert info.tag == "nightly-20260611"
    assert "2026-06-11" in info.title


def test_dev_update_sorts_nightlies_before_comparing():
    releases = [
        release("nightly-20260610", prerelease=True),
        release("nightly-20260612", prerelease=True),
        release("nightly-20260611", prerelease=True),
    ]
    build = BuildInfo(tag="nightly-20260611", channel="dev", built_at="2026-06-11")
    info = dev_update_from(releases, build)
    assert info is not None
    assert info.tag == "nightly-20260612"


def test_dev_no_update_when_on_latest_nightly():
    releases = [release("nightly-20260611", prerelease=True)]
    build = BuildInfo(tag="nightly-20260611", channel="dev", built_at="2026-06-11")
    assert dev_update_from(releases, build) is None


def test_dev_update_uses_partial_nightly_build_info():
    build = build_info_from_dict({"tag": "nightly-20260611"}, "1.6.0")
    assert build.channel == "dev"
    assert build.tag == "nightly-20260611"

    releases = [
        release("nightly-20260611", prerelease=True),
        release("nightly-20260610", prerelease=True),
    ]
    assert dev_update_from(releases, build) is None


def test_build_info_malformed_falls_back_to_stable_version():
    assert build_info_from_dict([], "1.6.0") == BuildInfo(
        tag="v1.6.0", channel="stable", built_at="")


def test_build_info_stamp_marks_stable_and_nightly_channels(tmp_path):
    stamp_build_info = load_build_release_module().stamp_build_info

    stable_dir = tmp_path / "stable"
    stable_dir.mkdir()
    stamp_build_info(stable_dir, "1.6.0")
    stable = build_info_from_dict(json.loads(
        (stable_dir / "build_info.json").read_text(encoding="utf-8")), "1.6.0")
    assert stable.tag == "v1.6.0"
    assert stable.channel == "stable"
    assert stable.built_at

    nightly_dir = tmp_path / "nightly"
    nightly_dir.mkdir()
    stamp_build_info(nightly_dir, "nightly-20260615")
    nightly = build_info_from_dict(json.loads(
        (nightly_dir / "build_info.json").read_text(encoding="utf-8")), "1.6.0")
    assert nightly.tag == "nightly-20260615"
    assert nightly.channel == "dev"
    assert nightly.built_at


def test_release_docs_are_staged_with_build_payload(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    source_root = tmp_path / "repo"
    source_root.mkdir()
    (source_root / "docs").mkdir()
    (source_root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## Unreleased\n", encoding="utf-8")
    (source_root / "docs" / "user-manual.md").write_text(
        "# Freight Fate User Manual\n", encoding="utf-8")
    monkeypatch.setattr(build_release, "ROOT", source_root)

    build_dir = tmp_path / "FreightFate"
    build_dir.mkdir()
    build_release.stage_release_docs(build_dir)

    assert (build_dir / "CHANGELOG.md").read_text(
        encoding="utf-8").startswith("# Changelog")
    assert (build_dir / "USER_MANUAL.md").read_text(
        encoding="utf-8").startswith("# Freight Fate User Manual")


def test_packaged_payload_requires_release_docs(tmp_path):
    build_release = load_build_release_module()
    build_dir = tmp_path / "FreightFate"
    exe = build_dir / ("FreightFate.exe" if sys.platform == "win32" else "FreightFate")
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    if sys.platform != "win32":
        exe.chmod(0o755)
    (build_dir / "build_info.json").write_text("{}", encoding="utf-8")
    (build_dir / "freight_fate" / "assets" / "sounds").mkdir(parents=True)
    (build_dir / "freight_fate" / "data").mkdir(parents=True)
    (build_dir / "freight_fate" / "data" / "world.json").write_text(
        "{}", encoding="utf-8")
    (build_dir / "sound_lib" / "lib").mkdir(parents=True)
    sound_suffix = next(iter(build_release.platform_native_exts()))
    (build_dir / "sound_lib" / "lib" / f"bass{sound_suffix}").write_text(
        "", encoding="utf-8")
    (build_dir / "prism" / "_native").mkdir(parents=True)
    native_suffix = next(iter(build_release.platform_native_exts()))
    (build_dir / "prism" / "_native" / f"bridge{native_suffix}").write_text(
        "", encoding="utf-8")

    try:
        build_release.verify_packaged_payload(build_dir)
    except RuntimeError as exc:
        assert "CHANGELOG.md" in str(exc)
        assert "USER_MANUAL.md" in str(exc)
    else:
        raise AssertionError("verify_packaged_payload accepted missing docs")


def test_packaged_payload_requires_platform_prism_native(tmp_path):
    build_release = load_build_release_module()
    build_dir = tmp_path / "FreightFate"
    exe = build_dir / ("FreightFate.exe" if sys.platform == "win32" else "FreightFate")
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    if sys.platform != "win32":
        exe.chmod(0o755)
    (build_dir / "build_info.json").write_text("{}", encoding="utf-8")
    (build_dir / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (build_dir / "USER_MANUAL.md").write_text("# Manual\n", encoding="utf-8")
    (build_dir / "freight_fate" / "assets" / "sounds").mkdir(parents=True)
    (build_dir / "freight_fate" / "data").mkdir(parents=True)
    (build_dir / "freight_fate" / "data" / "world.json").write_text(
        "{}", encoding="utf-8")
    (build_dir / "sound_lib" / "lib").mkdir(parents=True)
    sound_suffix = next(iter(build_release.platform_native_exts()))
    (build_dir / "sound_lib" / "lib" / f"bass{sound_suffix}").write_text(
        "", encoding="utf-8")
    (build_dir / "prism" / "_native").mkdir(parents=True)
    wrong_suffix = ".dll" if ".dll" not in build_release.platform_native_exts() else ".so"
    (build_dir / "prism" / "_native" / f"bridge{wrong_suffix}").write_text(
        "", encoding="utf-8")
    if build_release.sys.platform.startswith("linux"):
        add_linux_prism_dependency_dir(build_release, build_dir)

    try:
        build_release.verify_packaged_payload(build_dir)
    except RuntimeError as exc:
        assert "Prism native speech libraries are missing" in str(exc)
    else:
        raise AssertionError("verify_packaged_payload accepted missing platform Prism")


def test_packaged_payload_requires_runnable_posix_executable(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    monkeypatch.setattr(build_release.sys, "platform", "linux")
    monkeypatch.setattr(build_release, "verify_prism_native_linkage", lambda *_args: None)
    build_dir = tmp_path / "FreightFate"
    exe = build_dir / "FreightFate"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    exe.chmod(0o644)
    (build_dir / "build_info.json").write_text("{}", encoding="utf-8")
    (build_dir / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (build_dir / "USER_MANUAL.md").write_text("# Manual\n", encoding="utf-8")
    (build_dir / "freight_fate" / "assets" / "sounds").mkdir(parents=True)
    (build_dir / "freight_fate" / "data").mkdir(parents=True)
    (build_dir / "freight_fate" / "data" / "world.json").write_text(
        "{}", encoding="utf-8")
    (build_dir / "sound_lib" / "lib").mkdir(parents=True)
    (build_dir / "sound_lib" / "lib" / "libbass.so").write_text("", encoding="utf-8")
    (build_dir / "prism" / "_native").mkdir(parents=True)
    (build_dir / "prism" / "_native" / "bridge.so").write_text("", encoding="utf-8")
    add_linux_prism_dependency_dir(build_release, build_dir)

    try:
        build_release.verify_packaged_payload(build_dir)
    except RuntimeError as exc:
        assert "updates cannot restart" in str(exc)
    else:
        raise AssertionError("verify_packaged_payload accepted non-runnable executable")


def test_release_dependency_check_requires_platform_native_files(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    monkeypatch.setattr(build_release.sys, "platform", "linux")
    sound_dir = tmp_path / "sound_lib" / "lib"
    prism_dir = tmp_path / "prism" / "_native"
    sound_dir.mkdir(parents=True)
    prism_dir.mkdir(parents=True)
    (sound_dir / "bass.dll").write_text("", encoding="utf-8")
    (prism_dir / "bridge.dll").write_text("", encoding="utf-8")
    monkeypatch.setattr(build_release, "sound_lib_lib_dir", lambda: sound_dir)
    monkeypatch.setattr(build_release, "prism_native_dir", lambda: prism_dir)
    monkeypatch.setattr(build_release.importlib, "import_module", lambda _name: object())

    try:
        build_release.verify_release_dependencies()
    except RuntimeError as exc:
        assert "sound_lib native audio libraries are missing" in str(exc)
    else:
        raise AssertionError("dependency check accepted missing Linux natives")


def test_stage_prism_runtime_files_copies_linux_dependency_bundle(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    prism_dir = tmp_path / "site-packages" / "prism" / "_native"
    dependency_dir = tmp_path / "site-packages" / build_release.PRISM_DEPENDENCY_DIR
    prism_dir.mkdir(parents=True)
    dependency_dir.mkdir()
    (prism_dir / "libprism.so").write_text("", encoding="utf-8")
    (dependency_dir / "libglibmm-test.so.1.3.0").write_text("", encoding="utf-8")
    monkeypatch.setattr(build_release, "prism_native_dir", lambda: prism_dir)
    monkeypatch.setattr(build_release, "prism_dependency_dir", lambda: dependency_dir)

    build_dir = tmp_path / "FreightFate"
    build_release.stage_prism_runtime_files(build_dir)

    assert (build_dir / "prism" / "_native" / "libprism.so").exists()
    assert (
        build_dir
        / build_release.PRISM_DEPENDENCY_DIR
        / "libglibmm-test.so.1.3.0"
    ).exists()


def test_linux_packaged_payload_requires_prism_dependency_bundle(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    monkeypatch.setattr(build_release.sys, "platform", "linux")
    build_dir = tmp_path / "FreightFate"
    exe = build_dir / "FreightFate"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    exe.chmod(0o755)
    (build_dir / "build_info.json").write_text("{}", encoding="utf-8")
    (build_dir / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (build_dir / "USER_MANUAL.md").write_text("# Manual\n", encoding="utf-8")
    (build_dir / "freight_fate" / "assets" / "sounds").mkdir(parents=True)
    (build_dir / "freight_fate" / "data").mkdir(parents=True)
    (build_dir / "freight_fate" / "data" / "world.json").write_text(
        "{}", encoding="utf-8")
    (build_dir / "sound_lib" / "lib").mkdir(parents=True)
    (build_dir / "sound_lib" / "lib" / "libbass.so").write_text("", encoding="utf-8")
    (build_dir / "prism" / "_native").mkdir(parents=True)
    (build_dir / "prism" / "_native" / "libprism.so").write_text("", encoding="utf-8")

    try:
        build_release.verify_packaged_payload(build_dir)
    except RuntimeError as exc:
        assert build_release.PRISM_DEPENDENCY_DIR in str(exc)
    else:
        raise AssertionError("verify_packaged_payload accepted missing Prism deps")


def test_nuitka_standalone_folder_counts_as_packaged_build(tmp_path, monkeypatch):
    exe = tmp_path / "FreightFate.exe"
    exe.write_text("", encoding="utf-8")
    (tmp_path / "freight_fate").mkdir()
    monkeypatch.setattr(updater.sys, "executable", str(exe))
    monkeypatch.delattr(updater, "__compiled__", raising=False)
    monkeypatch.setattr(updater.sys, "frozen", False, raising=False)

    assert updater.is_frozen()


def test_dev_stable_build_compares_by_build_date():
    releases = [release("nightly-20260611", prerelease=True)]
    older = BuildInfo(tag="v1.5.0", channel="stable", built_at="2026-06-01")
    newer = BuildInfo(tag="v1.6.0", channel="stable", built_at="2026-06-11")
    assert dev_update_from(releases, older) is not None
    assert dev_update_from(releases, newer) is None


def test_dev_steered_to_stable_when_it_postdates_newest_nightly():
    # Dev work was promoted to stable this afternoon; the nightly the user is
    # on predates it. They should be offered stable, not left on nightlies.
    stable = release("v1.7.0", published="2026-06-26T15:00:00Z")
    releases = [stable, release("nightly-20260625", prerelease=True)]
    build = BuildInfo(tag="nightly-20260625", channel="dev", built_at="2026-06-25")
    info = dev_update_from(releases, build, stable)
    assert info is not None
    assert info.tag == "v1.7.0"
    assert "1.7.0" in info.title


def test_dev_ties_favor_stable_over_equivalent_nightly():
    # Tonight's nightly is content-identical to the stable released earlier the
    # same day. A dev user on an older nightly should land on stable, not the
    # equivalent same-day nightly.
    stable = release("v1.7.0", published="2026-06-26T15:00:00Z")
    releases = [
        stable,
        release("nightly-20260626", prerelease=True),
        release("nightly-20260625", prerelease=True),
    ]
    build = BuildInfo(tag="nightly-20260625", channel="dev", built_at="2026-06-25")
    info = dev_update_from(releases, build, stable)
    assert info is not None
    assert info.tag == "v1.7.0"


def test_dev_on_promoted_stable_is_not_pulled_onto_equivalent_nightly():
    # A dev user who already took the stable update must not be churned onto
    # the content-identical nightly that builds the same evening.
    stable = release("v1.7.0", published="2026-06-26T15:00:00Z")
    releases = [stable, release("nightly-20260626", prerelease=True)]
    build = BuildInfo(tag="v1.7.0", channel="stable", built_at="2026-06-26")
    assert dev_update_from(releases, build, stable) is None


def test_dev_resumes_nightlies_once_they_outpace_stable():
    # Days later dev advances past stable again; nightlies resume.
    stable = release("v1.7.0", published="2026-06-26T15:00:00Z")
    releases = [stable, release("nightly-20260630", prerelease=True)]
    build = BuildInfo(tag="v1.7.0", channel="stable", built_at="2026-06-26")
    info = dev_update_from(releases, build, stable)
    assert info is not None
    assert info.tag == "nightly-20260630"


# -- assets and notes ---------------------------------------------------------


def test_pick_asset_matches_platform_suffix():
    rel = release("v1.6.0")
    name, url, size = pick_asset(rel, suffix="-windows-portable.zip")
    assert name.endswith("-windows-portable.zip")
    assert size == 50_000_000
    name, _, _ = pick_asset(rel, suffix="-linux-x64.tar.gz")
    assert name.endswith("-linux-x64.tar.gz")
    assert pick_asset(rel, suffix="-bsd.tar.xz") is None


def test_flatten_markdown_strips_formatting():
    body = ("## Changes\n\n- **Cruise control.** K sets cruise.\n"
            "* See [the manual](https://example.test) for `details`.\n"
            "---\n")
    assert flatten_markdown(body) == [
        "Changes",
        "Cruise control. K sets cruise.",
        "See the manual for details.",
    ]


def test_flatten_markdown_handles_empty_body():
    assert flatten_markdown("") == []
    assert flatten_markdown(None) == []


# -- apply script -------------------------------------------------------------


def test_write_apply_script_waits_for_pid_and_relaunches(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    new_root = staging / "FreightFate"
    install = tmp_path / "install"
    script = write_apply_script(new_root, install, staging, pid=4242)
    text = script.read_text(encoding="utf-8")
    assert "4242" in text
    assert str(install) in text
    assert str(new_root) in text
    assert "FreightFate" in text
    assert script.parent == tmp_path  # outside the staging dir it deletes
    # portable saves live inside the install folder; the swap must not
    # touch them (Windows excludes the dir, POSIX never purges the root)
    if sys.platform == "win32":
        assert "/XD _internal saves" in text
    else:
        assert f"rm -rf \"{new_root}/saves\"" in text
    assert "/PURGE" not in text
    assert f"rm -rf \"{install}\"" not in text


# -- settings -----------------------------------------------------------------


def test_settings_default_and_validation(tmp_path, monkeypatch):
    s = Settings()
    assert s.update_channel == ""
    assert s.skipped_update == ""

    monkeypatch.setattr("freight_fate.models.profile.data_dir",
                        lambda: tmp_path)
    monkeypatch.setattr(Settings, "path",
                        property(lambda self: tmp_path / "settings.json"))
    s.update_channel = "weird"
    s.save()
    loaded = Settings.load()
    assert loaded.update_channel == ""   # invalid value reset


def test_build_info_none_when_not_frozen():
    assert not updater.is_frozen()
    assert updater.load_build_info("1.6.0") is None


def test_is_frozen_detects_nuitka(monkeypatch):
    # Nuitka (the build backend) never sets sys.frozen; it marks compiled
    # modules with a __compiled__ global. Simulate that and confirm the
    # updater recognizes the packaged build.
    assert not updater.is_frozen()
    monkeypatch.setattr(updater, "__compiled__", object(), raising=False)
    assert updater.is_frozen()


def test_install_root_is_executable_dir():
    assert updater.install_root() == Path(updater.sys.executable).resolve().parent


# -- update states ------------------------------------------------------------


def test_manual_update_check_explains_source_builds(monkeypatch):
    from freight_fate.states.update import UpdateCheckState

    spoken = []
    monkeypatch.setattr(updater, "is_frozen", lambda: False)
    ctx = SimpleNamespace(say=lambda text: spoken.append(text))
    state = UpdateCheckState(ctx)

    state.enter()

    assert state.checker is None
    assert "This copy runs from source; update it with git." in state.message
    assert spoken == [state.message + " Press Escape to go back."]


def test_packaged_logging_writes_info_to_game_log(tmp_path, monkeypatch):
    from freight_fate import app

    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    for handler in old_handlers:
        root.removeHandler(handler)
    root.addHandler(logging.NullHandler())

    monkeypatch.delenv("FREIGHT_FATE_LOG", raising=False)
    monkeypatch.setattr("freight_fate.updater.is_frozen", lambda: True)
    monkeypatch.setattr("freight_fate.models.profile.game_root", lambda: tmp_path)

    try:
        app._configure_logging()
        logging.getLogger("freight_fate.speech").info("Speech backend: Speech Dispatcher")
        logging.shutdown()
        text = (tmp_path / "logs" / "game.log").read_text(encoding="utf-8")
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()
        for handler in old_handlers:
            root.addHandler(handler)
        root.setLevel(old_level)

    assert "Speech backend: Speech Dispatcher" in text


def test_startup_update_prompt_respects_skipped_version():
    from freight_fate.states.main_menu import MainMenuState

    done = threading.Event()
    done.set()
    info = updater.UpdateInfo(
        tag="v1.6.1",
        title="Freight Fate version 1.6.1",
        notes=[],
        asset_name="FreightFate-1.6.1-windows-portable.zip",
        asset_url="https://example.test/FreightFate.zip",
        asset_size=1,
    )
    checker = SimpleNamespace(done=done, result=info)
    pushed = []
    ctx = SimpleNamespace(
        settings=SimpleNamespace(skipped_update="v1.6.1"),
        push_state=lambda state: pushed.append(state),
    )

    try:
        MainMenuState._update_checker = checker
        MainMenuState._update_prompted = False
        MainMenuState(ctx).update(0.0)
    finally:
        MainMenuState._update_checker = None
        MainMenuState._update_prompted = False

    assert pushed == []
