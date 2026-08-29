"""The ``--rust`` mode of tools/build_release.py: layout planning without cargo.

Everything here runs against a fake Cargo profile directory and a fake
package tree, so it proves what the staged ``FreightFate/`` folder would hold
(and what it would refuse) without building or copying the real game.
"""

from __future__ import annotations

import importlib.util
import subprocess
import urllib.error
from pathlib import Path

import pytest


def load_build_release_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_release.py"
    spec = importlib.util.spec_from_file_location("build_release", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_package_tree(package_dir: Path, build_release) -> None:
    """A package tree carrying every shipped data file plus source-only noise."""
    data = package_dir / "data"
    for relative in build_release.RUST_DATA_FILES + build_release.RUST_BAKED_SOURCE_FILES:
        path = data / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    legs = data / "world_data" / "us" / "legs"
    legs.mkdir(parents=True, exist_ok=True)
    (legs / "TX.json").write_text("{}\n", encoding="utf-8")
    (legs / "CA.json").write_text("{}\n", encoding="utf-8")
    # Source-only material that must never reach a player.
    (data / "world_source" / "legs").mkdir(parents=True)
    (data / "world_source" / "legs" / "TX.json").write_text("{}\n", encoding="utf-8")
    (data / "__pycache__").mkdir()
    (data / "__pycache__" / "world.cpython-312.pyc").write_bytes(b"")
    (data / "world.py").write_text("", encoding="utf-8")
    (data / "world_data" / "us" / "geometry").mkdir()
    (data / "world_data" / "us" / "geometry" / "tx.jsonl").write_text("", encoding="utf-8")
    (data / "world_data" / "us" / "gameplay" / "ramps.jsonl").write_text("", encoding="utf-8")
    sounds = package_dir / "assets" / "sounds"
    (sounds / "engine_classic").mkdir(parents=True)
    (sounds / "CREDITS.md").write_text("# Credits\n", encoding="utf-8")
    (sounds / "engine_classic" / "idle.ogg").write_bytes(b"ogg")
    licensed = package_dir / "assets" / "sounds-licensed" / "engine"
    licensed.mkdir(parents=True)
    (licensed / "idle.ogg").write_bytes(b"never ships loose")


def make_container(path: Path, build_release, size: int = 2_000_000) -> Path:
    """A stand-in for what ``ff-bake`` writes: right magic, plausible size."""
    path.parent.mkdir(parents=True, exist_ok=True)
    magic = build_release.BAKED_MAGIC
    path.write_bytes(magic + bytes(size - len(magic)))
    return path


def make_profile_dir(profile_dir: Path, exe_name: str) -> None:
    """What ``cargo build --release`` leaves behind on Windows."""
    profile_dir.mkdir(parents=True)
    (profile_dir / exe_name).write_bytes(b"MZ")
    for name in ("SDL2.dll", "bass.dll", "bassopus.dll", "basshls.dll", "prism.dll"):
        (profile_dir / name).write_bytes(b"dll")
    (profile_dir / "freightfate.pdb").write_bytes(b"pdb")
    (profile_dir / "libfreight_fate.rlib").write_bytes(b"rlib")
    deps = profile_dir / "deps"
    deps.mkdir()
    (deps / "serde_derive-abc123.dll").write_bytes(b"proc macro")


def track_everything(root: Path) -> None:
    """Make `root` a repository whose whole tree is tracked.

    The staging plan asks git which loose sounds are committed, so a fake
    package tree only means anything once git knows about it. Staging the
    index is enough -- `git ls-files` reads the index, so nothing has to be
    committed and no author identity is needed.
    """
    for args in (("init", "-q"), ("add", "-A")):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def planned(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    package_dir = tmp_path / "src" / "freight_fate"
    make_package_tree(package_dir, build_release)
    track_everything(tmp_path)
    # Left on the disk after git was told what the project ships: the 254 MB
    # of source audio that got into one release is exactly this, and it must
    # not reach the plan.
    (package_dir / "assets" / "sounds" / "idle_take3_source.wav").write_bytes(b"local accident")
    addon = tmp_path / "addon_lib"
    addon.mkdir()
    (addon / "basshls.dll").write_bytes(b"hls")
    (addon / "basshls.txt").write_text("licence", encoding="utf-8")
    monkeypatch.setattr(build_release, "ADDON_LIB_DIR", addon)
    profile_dir = tmp_path / "target" / "release"
    make_profile_dir(profile_dir, "freightfate.exe")
    baked = make_container(tmp_path / "build" / build_release.RUST_BAKED_FILE, build_release)
    plan = build_release.plan_rust_layout(
        profile_dir,
        package_dir=package_dir,
        platform_name="win32",
        native_exts={".dll"},
        baked_data=baked,
    )
    return build_release, plan, profile_dir, package_dir


def destinations(plan) -> set[str]:
    return {relative.as_posix() for _, relative in plan}


def test_plan_renames_the_cargo_binary_to_the_updater_name(planned):
    _, plan, profile_dir, _ = planned
    exe_sources = [(src, rel) for src, rel in plan if rel.as_posix() == "FreightFate.exe"]
    assert exe_sources == [(profile_dir / "freightfate.exe", Path("FreightFate.exe"))]
    assert "freightfate.exe" not in destinations(plan)


def test_exe_name_follows_the_platform():
    build_release = load_build_release_module()
    assert build_release.rust_exe_name("win32") == "FreightFate.exe"
    assert build_release.rust_exe_name("linux") == "FreightFate"
    assert build_release.rust_exe_name("darwin") == "FreightFate"
    assert build_release.cargo_exe_name("win32") == "freightfate.exe"
    assert build_release.cargo_exe_name("linux") == "freightfate"


def test_plan_ships_the_baked_container_instead_of_the_json_tree(planned):
    build_release, plan, _, _ = planned
    dests = destinations(plan)
    assert f"freight_fate/data/{build_release.RUST_BAKED_FILE}" in dests
    # Everything the container holds stays home: 142 MB of JSON is exactly
    # what shipping the container was for.
    for relative in build_release.RUST_BAKED_SOURCE_FILES:
        assert f"freight_fate/data/{relative}" not in dests
    assert not any("/world_data/" in dest for dest in dests)
    assert "freight_fate/data/world_data/us/legs/TX.json" not in dests
    for relative in build_release.RUST_DATA_FILES:
        assert f"freight_fate/data/{relative}" in dests
    assert not any("world_source" in dest for dest in dests)
    assert not any("__pycache__" in dest for dest in dests)
    assert not any(dest.endswith(".py") for dest in dests)
    assert not any("/geometry/" in dest for dest in dests)


def test_plan_refuses_to_stage_without_a_baked_container(planned, tmp_path):
    build_release, _, profile_dir, package_dir = planned
    with pytest.raises(RuntimeError, match="baked data container is missing"):
        build_release.plan_rust_layout(
            profile_dir, package_dir=package_dir, platform_name="win32", native_exts={".dll"}
        )
    with pytest.raises(RuntimeError, match="baked data container is missing"):
        build_release.plan_rust_layout(
            profile_dir,
            package_dir=package_dir,
            platform_name="win32",
            native_exts={".dll"},
            baked_data=tmp_path / "nowhere" / "world.ffdata",
        )


def test_bake_command_names_the_data_tree_and_the_container(tmp_path):
    build_release = load_build_release_module()
    out = tmp_path / "world.ffdata"
    cmd = build_release.bake_command(out)
    assert cmd[:7] == ["cargo", "run", "--release", "-p", "ff-core", "--bin", "ff-bake"]
    assert cmd[cmd.index("--out") + 1] == str(out)
    assert cmd[cmd.index("--data-dir") + 1] == str(build_release.PACKAGE_DIR / "data")
    assert "--check" not in cmd
    target = tmp_path / "t18"
    checked = build_release.bake_command(out, target, check=True)
    assert checked[checked.index("--target-dir") + 1] == str(target)
    assert checked[-1] == "--check"


def test_plan_ships_committed_sounds_but_never_the_licensed_overlay(planned):
    _, plan, _, _ = planned
    dests = destinations(plan)
    assert "freight_fate/assets/sounds/CREDITS.md" in dests
    assert "freight_fate/assets/sounds/engine_classic/idle.ogg" in dests
    assert not any("sounds-licensed" in dest for dest in dests)


def test_plan_leaves_uncommitted_sounds_on_the_builders_disk(planned):
    """The 548 MB release: loose audio nobody had committed went out in it.

    Committed means asked of git, so a file sitting in the tree that git has
    never heard of is a local accident and stays home.
    """
    _, plan, _, _ = planned
    assert "freight_fate/assets/sounds/idle_take3_source.wav" not in destinations(plan)


def test_plan_stages_only_top_level_runtime_libraries(planned):
    _, plan, _, _ = planned
    dests = destinations(plan)
    for name in ("SDL2.dll", "bass.dll", "bassopus.dll", "basshls.dll", "prism.dll"):
        assert name in dests
    assert "freightfate.pdb" not in dests
    assert "libfreight_fate.rlib" not in dests
    assert not any("serde_derive" in dest for dest in dests)
    # The game's own fallback plugin folder gets the add-on, not its licence note.
    assert "freight_fate/lib/basshls.dll" in dests
    assert "freight_fate/lib/basshls.txt" not in dests


def test_plan_refuses_a_profile_dir_without_the_binary(tmp_path):
    build_release = load_build_release_module()
    package_dir = tmp_path / "src" / "freight_fate"
    make_package_tree(package_dir, build_release)
    profile_dir = tmp_path / "target" / "release"
    profile_dir.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="no executable"):
        build_release.plan_rust_layout(profile_dir, package_dir=package_dir, platform_name="win32")


def test_plan_refuses_a_checkout_missing_a_loose_runtime_data_file(tmp_path, monkeypatch):
    """A file registered as shipping loose has to be there.

    ``RUST_DATA_FILES`` is empty today -- the container covers everything the
    game loads -- so the rule is exercised through a file added to it, which
    is what registering a new runtime data file looks like.
    """
    build_release = load_build_release_module()
    package_dir = tmp_path / "src" / "freight_fate"
    make_package_tree(package_dir, build_release)
    monkeypatch.setattr(build_release, "RUST_DATA_FILES", ("late_addition.json",))
    profile_dir = tmp_path / "target" / "release"
    make_profile_dir(profile_dir, "freightfate")
    baked = make_container(tmp_path / "build" / build_release.RUST_BAKED_FILE, build_release)
    with pytest.raises(RuntimeError, match="late_addition.json"):
        build_release.plan_rust_layout(
            profile_dir, package_dir=package_dir, platform_name="linux", baked_data=baked
        )


def test_bake_refuses_a_checkout_without_a_data_tree(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    monkeypatch.setattr(build_release, "PACKAGE_DIR", tmp_path / "src" / "freight_fate")
    with pytest.raises(RuntimeError, match="Runtime data tree is missing"):
        build_release.bake_world_data(out=tmp_path / "world.ffdata")


def test_lfs_pointer_is_refused_with_a_pull_hint(tmp_path):
    build_release = load_build_release_module()
    pointer = tmp_path / "sounds.pak"
    pointer.write_bytes(
        b"version https://git-lfs.github.com/spec/v1\noid sha256:0123456789abcdef\nsize 7781859\n"
    )
    assert build_release.is_lfs_pointer(pointer)
    with pytest.raises(RuntimeError, match="git lfs pull"):
        build_release.require_real_pack(pointer)

    real = tmp_path / "music.pak"
    real.write_bytes(b"FFPK1\x00" + b"\x00" * 64)
    assert not build_release.is_lfs_pointer(real)
    build_release.require_real_pack(real)

    with pytest.raises(RuntimeError, match="not found"):
        build_release.require_real_pack(tmp_path / "absent.pak")


def test_music_download_config_uses_public_defaults(monkeypatch):
    build_release = load_build_release_module()
    monkeypatch.delenv("FREIGHT_FATE_MUSIC_URL", raising=False)
    monkeypatch.delenv("FREIGHT_FATE_MUSIC_SHA256", raising=False)
    assert build_release.music_download_config() == (
        "https://dev.orinks.net/downloads/music.pak",
        "50f5440eb478f1e0e630e65081d83e6c308f48a6aa3ea5fe67c7dd1a7f50a8bb",
    )


def test_music_download_config_allows_independent_overrides():
    build_release = load_build_release_module()
    assert build_release.music_download_config(
        {
            "FREIGHT_FATE_MUSIC_URL": "https://example.test/music.pak",
            "FREIGHT_FATE_MUSIC_SHA256": "A" * 64,
        }
    ) == ("https://example.test/music.pak", "a" * 64)


def test_ensure_music_pack_keeps_a_verified_existing_pack(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    pack = tmp_path / "music.pak"
    pack.write_bytes(b"approved pack")
    digest = build_release.hashlib.sha256(pack.read_bytes()).hexdigest()
    monkeypatch.setenv("FREIGHT_FATE_MUSIC_SHA256", digest)
    monkeypatch.setattr(
        build_release.urllib.request,
        "urlretrieve",
        lambda *_: pytest.fail("downloaded"),
    )
    build_release.ensure_music_pack(pack)


def test_music_download_config_rejects_a_non_hex_digest(monkeypatch):
    build_release = load_build_release_module()
    monkeypatch.setenv("FREIGHT_FATE_MUSIC_SHA256", "not-a-digest")
    with pytest.raises(
        RuntimeError,
        match="FREIGHT_FATE_MUSIC_SHA256 must be a 64-character hexadecimal digest",
    ):
        build_release.music_download_config()


def test_ensure_music_pack_atomically_installs_a_verified_download(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    pack = tmp_path / "music.pak"
    payload = b"replacement pack"
    digest = build_release.hashlib.sha256(payload).hexdigest()
    monkeypatch.setenv("FREIGHT_FATE_MUSIC_URL", "https://example.test/music.pak")
    monkeypatch.setenv("FREIGHT_FATE_MUSIC_SHA256", digest)

    def download(url, destination):
        assert url == "https://example.test/music.pak"
        Path(destination).write_bytes(payload)

    monkeypatch.setattr(build_release.urllib.request, "urlretrieve", download)
    build_release.ensure_music_pack(pack)

    assert pack.read_bytes() == payload
    assert list(tmp_path.glob("*.download")) == []


def test_ensure_music_pack_rejects_a_mismatched_download(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    pack = tmp_path / "music.pak"
    monkeypatch.setenv("FREIGHT_FATE_MUSIC_SHA256", "a" * 64)
    monkeypatch.setattr(
        build_release.urllib.request,
        "urlretrieve",
        lambda _url, destination: Path(destination).write_bytes(b"unapproved pack"),
    )

    with pytest.raises(RuntimeError, match="failed SHA-256 verification"):
        build_release.ensure_music_pack(pack)

    assert not pack.exists()
    assert list(tmp_path.glob("*.download")) == []


def test_ensure_music_pack_replaces_a_mismatched_existing_pack_after_verification(
    tmp_path, monkeypatch
):
    build_release = load_build_release_module()
    pack = tmp_path / "music.pak"
    pack.write_bytes(b"old pack")
    payload = b"new approved pack"
    digest = build_release.hashlib.sha256(payload).hexdigest()
    monkeypatch.setenv("FREIGHT_FATE_MUSIC_SHA256", digest)
    monkeypatch.setattr(
        build_release.urllib.request,
        "urlretrieve",
        lambda _url, destination: Path(destination).write_bytes(payload),
    )

    build_release.ensure_music_pack(pack)

    assert pack.read_bytes() == payload
    assert list(tmp_path.glob("*.download")) == []


def test_ensure_music_pack_preserves_existing_pack_when_download_fails(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    pack = tmp_path / "music.pak"
    old_payload = b"old pack"
    pack.write_bytes(old_payload)
    monkeypatch.setenv(
        "FREIGHT_FATE_MUSIC_SHA256",
        build_release.hashlib.sha256(b"new approved pack").hexdigest(),
    )

    def fail_download(_url, _destination):
        raise urllib.error.URLError("download unavailable")

    monkeypatch.setattr(build_release.urllib.request, "urlretrieve", fail_download)
    with pytest.raises(
        RuntimeError,
        match=(
            "Music-pack download failed: download unavailable. "
            "Check your connection and retry the build."
        ),
    ) as exc:
        build_release.ensure_music_pack(pack)

    assert isinstance(exc.value.__cause__, urllib.error.URLError)
    assert pack.read_bytes() == old_payload
    assert list(tmp_path.glob("*.download")) == []


def test_ensure_music_pack_reports_http_status_and_preserves_the_cause(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    pack = tmp_path / "music.pak"
    monkeypatch.setenv("FREIGHT_FATE_MUSIC_SHA256", "a" * 64)

    def fail_download(url, _destination):
        raise urllib.error.HTTPError(url, 503, "Service Unavailable", None, None)

    monkeypatch.setattr(build_release.urllib.request, "urlretrieve", fail_download)
    with pytest.raises(
        RuntimeError,
        match=(
            "Music-pack download failed with HTTP status 503. "
            "Check your connection and retry the build."
        ),
    ) as exc:
        build_release.ensure_music_pack(pack)

    assert isinstance(exc.value.__cause__, urllib.error.HTTPError)
    assert exc.value.__cause__.code == 503
    assert not pack.exists()
    assert list(tmp_path.glob("*.download")) == []


def test_ensure_music_pack_does_not_mislabel_local_io_failures(tmp_path, monkeypatch):
    build_release = load_build_release_module()
    pack = tmp_path / "music.pak"
    monkeypatch.setenv("FREIGHT_FATE_MUSIC_SHA256", "a" * 64)

    def fail_download(_url, _destination):
        raise PermissionError("destination is read-only")

    monkeypatch.setattr(build_release.urllib.request, "urlretrieve", fail_download)
    with pytest.raises(PermissionError, match="destination is read-only"):
        build_release.ensure_music_pack(pack)

    assert not pack.exists()
    assert list(tmp_path.glob("*.download")) == []


def test_cargo_command_honours_the_target_dir(tmp_path):
    build_release = load_build_release_module()
    assert build_release.cargo_build_command() == [
        "cargo",
        "build",
        "--release",
        "-p",
        "freight-fate",
    ]
    target = tmp_path / "t53"
    assert build_release.cargo_build_command(target)[-2:] == ["--target-dir", str(target)]
    assert build_release.cargo_profile_dir(target) == target / "release"
    assert build_release.cargo_profile_dir() == build_release.ROOT / "target" / "release"


def test_prepare_rust_release_dependencies_fetches_bass_then_music(monkeypatch):
    """Release builds restore native audio before fetching the music pack."""
    build_release = load_build_release_module()
    calls = []
    monkeypatch.setattr(
        build_release.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )
    monkeypatch.setattr(build_release, "ensure_music_pack", lambda: calls.append(("music", {})))

    build_release.prepare_rust_release_dependencies()

    assert calls[0][0] == [build_release.sys.executable, str(build_release.TOOLS / "fetch_bass.py")]
    assert calls[0][1] == {"cwd": build_release.ROOT, "check": True}
    assert calls[1][0] == "music"


def test_windows_release_wrapper_is_the_complete_beginner_command():
    root = Path(__file__).resolve().parents[1]
    script = (root / "build-release.ps1").read_text(encoding="utf-8")
    readme_heading = "## Build a standalone copy"
    assert readme_heading in (root / "README.md").read_text(encoding="utf-8")
    assert readme_heading.removeprefix("## ") in script
    assert "Get-Command rustc" in script
    assert "Get-Command uv" in script
    assert "uv sync --group dev --group build" in script
    assert "uv run python tools/build_release.py --rust --smoke" in script
    assert "Start-Process" not in script


def test_main_accepts_the_rust_flags(capsys):
    build_release = load_build_release_module()
    with pytest.raises(SystemExit) as exc:
        import sys

        old = sys.argv
        sys.argv = ["build_release.py", "--help"]
        try:
            build_release.main()
        finally:
            sys.argv = old
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--rust" in out
    assert "--cargo-target-dir" in out
    assert "--smoke" in out
