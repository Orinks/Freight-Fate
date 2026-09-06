"""Application-local MSVC runtime staging for the Windows x64 portable build.

Only Visual Studio's redistributable CRT directory is a source. Never copy
from System32, a Python environment, or an arbitrary DLL download site.
See https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files
and https://learn.microsoft.com/en-us/windows/win32/debug/pe-format .
"""

from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
from pathlib import Path

REQUIRED_CRT = ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll")
VC_DLL = re.compile(r"(?:vcruntime|msvcp|msvcr|concrt|vcomp)\d[^/\\]*\.dll$", re.I)


def _version(path: Path) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", path.name))


def find_crt_directory() -> Path:
    """Prefer the active toolchain, otherwise discover the latest installed VS."""
    roots: list[Path] = []
    configured = os.environ.get("VCToolsRedistDir")  # noqa: SIM112 - Microsoft's spelling
    if configured:
        roots.append(Path(configured))
    else:
        vc = os.environ.get("VCINSTALLDIR")
        vs = os.environ.get("VSINSTALLDIR")
        if vc or vs:
            base = Path(vc) if vc else Path(vs) / "VC"
            roots.extend(sorted((base / "Redist" / "MSVC").glob("*"), key=_version, reverse=True))
        if not roots:
            program_files = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")  # noqa: SIM112
            vswhere = Path(program_files) / ("Microsoft Visual Studio/Installer/vswhere.exe")
            if vswhere.is_file():
                result = subprocess.run(
                    [
                        str(vswhere),
                        "-latest",
                        "-products",
                        "*",
                        "-requires",
                        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                        "-property",
                        "installationPath",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                installation = result.stdout.strip()
                if installation:
                    roots.extend(
                        sorted(
                            (Path(installation) / "VC/Redist/MSVC").glob("*"),
                            key=_version,
                            reverse=True,
                        )
                    )
    for root in roots:
        for directory in sorted(
            (root / "x64").glob("Microsoft.VC*.CRT"), key=_version, reverse=True
        ):
            files = {p.name.lower() for p in directory.iterdir() if p.is_file()}
            if set(REQUIRED_CRT) <= files:
                return directory
    raise RuntimeError(
        "Cannot find a complete Visual Studio x64 redistributable CRT. Install the "
        "Visual Studio C++ build tools, or set VCToolsRedistDir to the toolchain's "
        "VC/Redist/MSVC/<version> directory. The portable build cannot ship without it."
    )


def pe_imports(path: Path) -> set[str]:
    """Read normal and delay imports from an x64 PE; reject malformed inputs.

    This is a static VC-runtime audit, not a general Windows loader emulator.
    All reads must map to bytes in the file, never a section's zero-filled tail.
    """
    data = path.read_bytes()

    def unpack(fmt: str, offset: int):
        if offset < 0 or offset + struct.calcsize(fmt) > len(data):
            raise ValueError("truncated PE structure")
        return struct.unpack_from(fmt, data, offset)

    try:
        if data[:2] != b"MZ":
            raise ValueError("missing DOS signature")
        pe = unpack("<I", 0x3C)[0]
        if data[pe : pe + 4] != b"PE\0\0":
            raise ValueError("missing PE signature")
        machine, section_count = unpack("<HH", pe + 4)
        if machine != 0x8664:
            raise ValueError(f"expected x64 machine, got 0x{machine:04x}")
        optional_size = unpack("<H", pe + 20)[0]
        optional = pe + 24
        if optional_size < 112 or unpack("<H", optional)[0] != 0x20B:
            raise ValueError("expected PE32+ optional header")
        image_base = unpack("<Q", optional + 24)[0]
        directory_count = unpack("<I", optional + 108)[0]
        if directory_count > (optional_size - 112) // 8:
            raise ValueError("data directories exceed optional header")
        sections = []
        for index in range(section_count):
            offset = optional + optional_size + index * 40
            _, address, raw_size, raw_offset = unpack("<IIII", offset + 8)
            sections.append((address, raw_size, raw_offset))

        def rva_offset(rva: int, size: int) -> int:
            for address, raw_size, raw_offset in sections:
                delta = rva - address
                if delta >= 0 and delta + size <= raw_size:
                    offset = raw_offset + delta
                    if offset + size <= len(data):
                        return offset
            raise ValueError(f"unmapped RVA 0x{rva:x}")

        def dll_name(rva: int) -> str:
            value = bytearray()
            for index in range(260):
                byte = data[rva_offset(rva + index, 1)]
                if byte == 0:
                    name = value.decode("ascii").lower()
                    if not name or "/" in name or "\\" in name:
                        raise ValueError("invalid imported DLL name")
                    return name
                value.append(byte)
            raise ValueError("unterminated DLL name")

        imports = set()
        for index, size, name_field in ((1, 20, 12), (13, 32, 4)):
            if directory_count <= index:
                continue
            rva, length = unpack("<II", optional + 112 + index * 8)
            if not rva and not length:
                continue
            if not rva or length < size:
                raise ValueError("invalid import directory")
            terminated = False
            for delta in range(0, length - size + 1, size):
                offset = rva_offset(rva + delta, size)
                if not any(data[offset : offset + size]):
                    terminated = True
                    break
                name_rva = unpack("<I", offset + name_field)[0]
                if index == 13:
                    attributes = unpack("<I", offset)[0]
                    if attributes & ~1:
                        raise ValueError("unknown delay-import attributes")
                    if not attributes & 1:
                        name_rva -= image_base
                imports.add(dll_name(name_rva))
            if not terminated:
                raise ValueError("unterminated import directory")
        return imports
    except (ValueError, struct.error) as error:
        raise RuntimeError(f"Cannot audit Windows binary {path}: {error}") from error


def verify_windows_runtime(root: Path) -> None:
    """Prove every VC import has an application-local DLL, including plugins."""
    available = {p.name.lower() for p in root.iterdir() if p.is_file()}
    missing = set(REQUIRED_CRT) - available
    if missing:
        raise RuntimeError("Windows payload is missing VC++ runtime: " + ", ".join(sorted(missing)))
    for path in sorted(root.rglob("*")):
        if not path.is_file() or (path.suffix.lower() != ".dll" and path.name != "FreightFate.exe"):
            continue
        for name in pe_imports(path):
            if VC_DLL.fullmatch(name) and name not in available:
                raise RuntimeError(
                    f"{path.relative_to(root)} requires unbundled VC++ runtime {name}"
                )


def stage_windows_runtime(root: Path) -> None:
    """Copy one complete official CRT family and audit before archiving."""
    source = find_crt_directory()
    files = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() == ".dll")
    for path in files:
        pe_imports(path)  # A wrong-architecture/corrupt redist must not be copied.
    # Replace any CRT left in the Cargo directory; never mix runtime versions.
    for path in root.iterdir():
        if path.is_file() and VC_DLL.fullmatch(path.name):
            path.unlink()
    for path in files:
        shutil.copy2(path, root / path.name)
    print(f"Staged Visual C++ runtime from {source}: " + ", ".join(p.name for p in files))
    verify_windows_runtime(root)
