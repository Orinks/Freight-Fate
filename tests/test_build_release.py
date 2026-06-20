import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD_RELEASE_PATH = ROOT / "tools" / "build_release.py"
spec = importlib.util.spec_from_file_location("build_release", BUILD_RELEASE_PATH)
assert spec is not None
assert spec.loader is not None
build_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_release)


def test_prism_target_native_dir_uses_macos_app_runtime_layout(tmp_path):
    build_dir = tmp_path / "FreightFate.app"

    assert build_release.prism_target_native_dir(build_dir) == (
        build_dir / "Contents" / "MacOS" / "prism" / "_native"
    )


def test_stage_prism_runtime_files_copies_native_library(tmp_path, monkeypatch):
    source_dir = tmp_path / "site-packages" / "prism" / "_native"
    source_dir.mkdir(parents=True)
    (source_dir / "libprism.dylib").write_bytes(b"prism")
    build_dir = tmp_path / "FreightFate.app"

    monkeypatch.setattr(build_release, "prism_native_dir", lambda: source_dir)

    build_release.stage_prism_runtime_files(build_dir)

    target = build_dir / "Contents" / "MacOS" / "prism" / "_native" / "libprism.dylib"
    assert target.read_bytes() == b"prism"


def test_stage_prism_runtime_files_rejects_missing_native_library(tmp_path, monkeypatch):
    source_dir = tmp_path / "site-packages" / "prism" / "_native"
    source_dir.mkdir(parents=True)
    (source_dir / "README.txt").write_text("not a native library", encoding="utf-8")
    build_dir = tmp_path / "FreightFate.app"

    monkeypatch.setattr(build_release, "prism_native_dir", lambda: source_dir)

    with pytest.raises(RuntimeError, match="No Prism native libraries"):
        build_release.stage_prism_runtime_files(build_dir)


def test_smoke_check_keeps_save_data_out_of_app_bundle(tmp_path, monkeypatch):
    build_dir = tmp_path / "FreightFate.app"
    exe = build_dir / "Contents" / "MacOS" / build_release.APP_NAME
    exe.parent.mkdir(parents=True)
    exe.write_text("fake executable", encoding="utf-8")
    observed = {}

    def fake_run(cmd, check, cwd, env, timeout):
        observed["cmd"] = cmd
        observed["check"] = check
        observed["cwd"] = cwd
        observed["env"] = env
        observed["timeout"] = timeout
        assert Path(env["FREIGHT_FATE_DATA_DIR"]).is_dir()

    monkeypatch.setattr(build_release.subprocess, "run", fake_run)

    build_release.smoke_check(build_dir)

    data_dir = Path(observed["env"]["FREIGHT_FATE_DATA_DIR"])
    assert observed["cmd"] == [str(exe), "--smoke"]
    assert observed["check"] is True
    assert observed["cwd"] == exe.parent
    assert observed["timeout"] == 120
    assert observed["env"]["FREIGHT_FATE_NO_SPEECH"] == "1"
    assert build_dir not in data_dir.parents
