"""Update discovery, channel resolution, notes flattening, apply scripts."""

import importlib.util
import json
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


def release(tag, prerelease=False, body="", assets=("-windows-portable.zip",
                                                    "-macos.zip",
                                                    "-linux-x64.tar.gz")):
    return {
        "tag_name": tag,
        "prerelease": prerelease,
        "body": body,
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
    (source_root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## Unreleased\n", encoding="utf-8")
    monkeypatch.setattr(build_release, "ROOT", source_root)

    build_dir = tmp_path / "FreightFate"
    build_dir.mkdir()
    build_release.stage_release_docs(build_dir)

    assert (build_dir / "CHANGELOG.md").read_text(
        encoding="utf-8").startswith("# Changelog")


def test_packaged_payload_requires_changelog(tmp_path):
    build_release = load_build_release_module()
    build_dir = tmp_path / "FreightFate"
    (build_dir / "freight_fate" / "assets" / "sounds").mkdir(parents=True)
    (build_dir / "freight_fate" / "data").mkdir(parents=True)
    (build_dir / "freight_fate" / "data" / "world.json").write_text(
        "{}", encoding="utf-8")
    (build_dir / "sound_lib" / "lib").mkdir(parents=True)
    (build_dir / "prism" / "_native").mkdir(parents=True)
    native_suffix = next(iter(build_release.PRISM_NATIVE_EXTS))
    (build_dir / "prism" / "_native" / f"bridge{native_suffix}").write_text(
        "", encoding="utf-8")

    try:
        build_release.verify_packaged_payload(build_dir)
    except RuntimeError as exc:
        assert "CHANGELOG.md" in str(exc)
    else:
        raise AssertionError("verify_packaged_payload accepted a missing changelog")


def test_dev_stable_build_compares_by_build_date():
    releases = [release("nightly-20260611", prerelease=True)]
    older = BuildInfo(tag="v1.5.0", channel="stable", built_at="2026-06-01")
    newer = BuildInfo(tag="v1.6.0", channel="stable", built_at="2026-06-11")
    assert dev_update_from(releases, older) is not None
    assert dev_update_from(releases, newer) is None


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
