"""Update discovery, channel resolution, notes flattening, apply scripts."""

import sys
from pathlib import Path

from freight_fate import updater
from freight_fate.settings import Settings
from freight_fate.updater import (
    BuildInfo,
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


def test_dev_no_update_when_on_latest_nightly():
    releases = [release("nightly-20260611", prerelease=True)]
    build = BuildInfo(tag="nightly-20260611", channel="dev", built_at="2026-06-11")
    assert dev_update_from(releases, build) is None


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
    assert updater.load_build_info("1.5.0") is None


def test_install_root_is_executable_dir():
    assert updater.install_root() == Path(updater.sys.executable).resolve().parent
