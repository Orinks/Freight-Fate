"""Portable Windows CRT packaging, using synthetic PE files (no Windows required)."""

import os
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import build_release
import windows_runtime


def pe_file(path, imports=(), delayed=(), machine=0x8664):
    """One PE32+ section, with independently laid-out import descriptors."""
    data = bytearray(4096)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HH", data, 0x84, machine, 1)
    struct.pack_into("<H", data, 0x94, 240)
    struct.pack_into("<H", data, 0x98, 0x20B)
    struct.pack_into("<Q", data, 0xB0, 0x140000000)
    struct.pack_into("<I", data, 0x104, 16)
    struct.pack_into("<IIII", data, 0x190, 0xE00, 0x1000, 0xE00, 0x200)
    name_offset = 0x800
    for index, names, offset, size, name_field in (
        (1, imports, 0x200, 20, 12),
        (13, delayed, 0x400, 32, 4),
    ):
        if not names:
            continue
        struct.pack_into("<II", data, 0x108 + index * 8, offset + 0xE00, (len(names) + 1) * size)
        for i, name in enumerate(names):
            descriptor = offset + i * size
            if index == 13:
                struct.pack_into("<I", data, descriptor, 1)
            struct.pack_into("<I", data, descriptor + name_field, name_offset + 0xE00)
            value = name.encode("ascii") + b"\0"
            data[name_offset : name_offset + len(value)] = value
            name_offset += len(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class WindowsRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def make_redist(self, version="14.44.0", machine=0x8664):
        redist = self.root / "VC" / "Redist" / "MSVC" / version
        crt = redist / "x64" / "Microsoft.VC143.CRT"
        for name in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"):
            pe_file(crt / name, machine=machine)
        return redist, crt

    def make_payload(self):
        payload = self.root / "payload"
        pe_file(payload / "FreightFate.exe", ["VCRUNTIME140.dll", "KERNEL32.dll"])
        for name in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"):
            pe_file(payload / name)
        return payload

    def test_collects_whole_crt_family_and_replaces_stale_cargo_copy(self):
        redist, crt = self.make_redist()
        pe_file(crt / "msvcp140_atomic_wait.dll")
        payload = self.make_payload()
        (payload / "vcruntime140.dll").write_bytes(b"old CRT")
        with patch.dict(os.environ, {"VCToolsRedistDir": str(redist)}, clear=True):
            windows_runtime.stage_windows_runtime(payload)
        self.assertEqual(
            (payload / "msvcp140_atomic_wait.dll").read_bytes(),
            (crt / "msvcp140_atomic_wait.dll").read_bytes(),
        )
        self.assertEqual(
            (payload / "vcruntime140.dll").read_bytes(), (crt / "vcruntime140.dll").read_bytes()
        )

    def test_missing_or_incomplete_configured_redist_fails_closed(self):
        redist, crt = self.make_redist()
        (crt / "vcruntime140_1.dll").unlink()
        with (
            patch.dict(os.environ, {"VCToolsRedistDir": str(redist)}, clear=True),
            self.assertRaisesRegex(RuntimeError, "complete Visual Studio x64"),
        ):
            windows_runtime.stage_windows_runtime(self.make_payload())

    def test_vs_install_discovery_uses_numeric_version_order(self):
        self.make_redist("14.9.0")
        _, newest = self.make_redist("14.44.0")
        with patch.dict(os.environ, {"VCINSTALLDIR": str(self.root / "VC")}, clear=True):
            self.assertEqual(windows_runtime.find_crt_directory(), newest)

    def test_vswhere_discovery_without_developer_prompt(self):
        _, crt = self.make_redist()
        vswhere = self.root / "Microsoft Visual Studio/Installer/vswhere.exe"
        vswhere.parent.mkdir(parents=True)
        vswhere.touch()

        def run(command, **kwargs):
            self.assertEqual(command[0], str(vswhere))
            self.assertIn("installationPath", command)
            return type("Result", (), {"stdout": str(self.root) + "\n"})()

        with (
            patch.dict(os.environ, {"ProgramFiles(x86)": str(self.root)}, clear=True),
            patch.object(windows_runtime.subprocess, "run", side_effect=run),
        ):
            self.assertEqual(windows_runtime.find_crt_directory(), crt)

    def test_rejects_wrong_architecture_in_redist(self):
        redist, _ = self.make_redist(machine=0x14C)
        with (
            patch.dict(os.environ, {"VCToolsRedistDir": str(redist)}, clear=True),
            self.assertRaisesRegex(RuntimeError, "expected x64"),
        ):
            windows_runtime.stage_windows_runtime(self.make_payload())

    def test_normal_and_delay_imports_are_case_insensitive(self):
        path = pe_file(
            self.root / "test.dll",
            ["KERNEL32.dll", "VCRUNTIME140.dll"],
            ["MSVCP140_ATOMIC_WAIT.dll"],
        )
        self.assertEqual(
            windows_runtime.pe_imports(path),
            {"kernel32.dll", "vcruntime140.dll", "msvcp140_atomic_wait.dll"},
        )

    def test_missing_nested_plugin_delay_dependency_stops_release(self):
        payload = self.make_payload()
        pe_file(payload / "freight_fate/lib/plugin.dll", delayed=["MSVCP140_2.dll"])
        with self.assertRaisesRegex(RuntimeError, "plugin.dll.*msvcp140_2.dll"):
            windows_runtime.verify_windows_runtime(payload)
        pe_file(payload / "msvcp140_2.dll")
        windows_runtime.verify_windows_runtime(payload)

    def test_missing_required_runtime_stops_release(self):
        payload = self.make_payload()
        (payload / "vcruntime140_1.dll").unlink()
        with self.assertRaisesRegex(RuntimeError, "missing VC.*vcruntime140_1.dll"):
            windows_runtime.verify_windows_runtime(payload)

    def test_finished_rust_zip_requires_nonempty_root_crt(self):
        archive = self.root / "FreightFate-test-windows-portable.zip"
        names = [
            "FreightFate.exe",
            "build_info.json",
            "LICENSE.txt",
            "USER_MANUAL.md",
            "freight_fate/sounds.pak",
            "freight_fate/music.pak",
            "freight_fate/data/world.ffdata",
        ]
        for missing in (True, False):
            with zipfile.ZipFile(archive, "w") as output:
                for name in names:
                    output.writestr("FreightFate/" + name, b"payload")
                if not missing:
                    for name in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"):
                        output.writestr("FreightFate/" + name, b"runtime")
            if missing:
                with self.assertRaisesRegex(RuntimeError, "vcruntime140.dll"):
                    build_release.verify_archive(archive)
            else:
                build_release.verify_archive(archive)

    def test_unbundled_debug_runtime_stops_release(self):
        payload = self.make_payload()
        pe_file(payload / "prism.dll", ["VCRUNTIME140D.dll"])
        with self.assertRaisesRegex(RuntimeError, "vcruntime140d.dll"):
            windows_runtime.verify_windows_runtime(payload)

    def test_truncated_or_unmapped_imports_fail_closed(self):
        path = pe_file(self.root / "bad.dll", ["vcruntime140.dll"])
        data = bytearray(path.read_bytes())
        struct.pack_into("<I", data, 0x20C, 0xF00000)
        path.write_bytes(data)
        with self.assertRaisesRegex(RuntimeError, "unmapped RVA"):
            windows_runtime.pe_imports(path)
        path.write_bytes(data[:100])
        with self.assertRaisesRegex(RuntimeError, "Cannot audit"):
            windows_runtime.pe_imports(path)

    def test_legacy_delay_import_uses_image_base(self):
        path = pe_file(self.root / "legacy.dll", delayed=["vcruntime140.dll"])
        data = bytearray(path.read_bytes())
        struct.pack_into("<Q", data, 0xB0, 0x10000000)
        struct.pack_into("<II", data, 0x400, 0, 0x10001600)
        path.write_bytes(data)
        self.assertEqual(windows_runtime.pe_imports(path), {"vcruntime140.dll"})

    def test_windows_staging_copies_crt_beside_executable(self):
        # Removing the Windows staging hook must regress this test.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile, stage = root / "release", root / "stage"
            exe = pe_file(profile / "freightfate.exe", ["VCRUNTIME140.dll"])
            redist = root / "Redist" / "14.44.0" / "x64" / "Microsoft.VC143.CRT"
            for name in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"):
                pe_file(redist / name)
            with (
                patch.dict(os.environ, {"VCToolsRedistDir": str(redist.parents[1])}),
                patch.object(build_release, "require_real_pack"),
                patch.object(build_release, "stage_sound_pack"),
                patch.object(
                    build_release, "plan_rust_layout", return_value=[(exe, Path("FreightFate.exe"))]
                ),
            ):
                build_release.stage_rust_build(profile, stage, platform_name="win32")
            self.assertEqual(
                (stage / "vcruntime140.dll").read_bytes(),
                (redist / "vcruntime140.dll").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
