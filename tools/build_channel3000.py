"""Pack Channel 3000's clips into ``channel3000.pak`` and stage its manifest.

Channel 3000 is the in-game radio station at 87.7: the owner's television
programming on a time-of-day schedule. Its audio is about five hours of
Ogg Opus, kept out of ``music.pak`` (which the game reads whole into memory)
in a pack of its own that the game opens only when someone tunes in. The
plan is ``docs/superpowers/plans/2026-10-06-channel-3000.md``.

The clips live on the orphan ``channel3000-clips`` branch, never merged::

    git fetch origin channel3000-clips
    git worktree add ../c3k-clips origin/channel3000-clips
    uv run python tools/build_channel3000.py ../c3k-clips

That folder holds ``clips/<key>.opus`` and ``clips.json``. This tool checks
the two against each other in both directions, then writes:

- ``assets/channel3000.pak``: the FFPK format of ``tools/assets_pack.py``,
  entries named ``c3k/<key>.opus`` and stored rather than deflated (Opus
  does not compress), byte for byte the same for the same clips on any
  machine. Gitignored; a release downloads it, SHA-pinned, like
  ``music.pak`` (``ensure_channel3000_pack`` in ``tools/build_release.py``).
- ``data/channel3000.json``: ``clips.json`` exactly as it is. Committed,
  and baked into ``world.ffdata``.

``--check`` validates without writing anything.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACK_OUTPUT = ROOT / "assets" / "channel3000.pak"
DEFAULT_MANIFEST_OUTPUT = ROOT / "data" / "channel3000.json"
PACK_PREFIX = "c3k/"
CLIP_SUFFIX = ".opus"
KINDS = frozenset({"programme", "ident", "continuity", "ad", "short"})
DAYPARTS = ("day", "prime", "late", "overnight")
_KEY_RE = re.compile(r"^[a-z0-9_]+$")
# Fixed zip metadata so the same clips make the same pack on every machine:
# zipfile stamps the host OS into each entry unless told otherwise.
_EPOCH = (1980, 1, 1, 0, 0, 0)
_UNIX = 3
_FILE_MODE = 0o100644 << 16


def _load_assets_pack():
    """Import the pack-format module beside this tool, by path."""
    spec = importlib.util.spec_from_file_location(
        "assets_pack", Path(__file__).resolve().parent / "assets_pack.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _stray_files(clips_dir: Path) -> list[str]:
    return sorted(
        path.name for path in clips_dir.iterdir() if path.is_file() and path.suffix != CLIP_SUFFIX
    )


def validate(manifest: dict, clips_dir: Path) -> list[str]:
    """Every problem with the manifest and the clips folder, in plain words.

    Empty means the station can be built. Counts are never pinned: a clip
    added to the branch is simply one more row and one more file.
    """
    errors: list[str] = []
    if manifest.get("schema") != 1:
        errors.append(f"schema is {manifest.get('schema')!r}, expected 1")
    hours = manifest.get("dayparts")
    if not isinstance(hours, dict) or set(hours) != set(DAYPARTS):
        errors.append(f"dayparts must be exactly {', '.join(DAYPARTS)}")
    else:
        for name, span in hours.items():
            if (
                not isinstance(span, list)
                or len(span) != 2
                or not all(isinstance(h, int) and 0 <= h < 24 for h in span)
                or span[0] == span[1]
            ):
                errors.append(f"daypart {name} has bad hours {span!r}")
    clips = manifest.get("clips")
    if not isinstance(clips, list) or not clips:
        return [*errors, "the manifest has no clips"]

    seen: set[str] = set()
    for clip in clips:
        key = clip.get("key", "")
        if not isinstance(key, str) or not _KEY_RE.match(key):
            errors.append(f"clip key {key!r} is not lowercase letters, digits and underscores")
            continue
        if key in seen:
            errors.append(f"clip {key} is listed twice")
        seen.add(key)
        if clip.get("kind") not in KINDS:
            errors.append(f"clip {key} has unknown kind {clip.get('kind')!r}")
        parts = clip.get("dayparts")
        if not isinstance(parts, list) or not parts:
            errors.append(f"clip {key} has no dayparts")
        else:
            unknown = [part for part in parts if part not in DAYPARTS]
            if unknown:
                errors.append(f"clip {key} has unknown dayparts {unknown}")
        duration = clip.get("duration_s")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
            errors.append(f"clip {key} has duration {duration!r}; it must be above zero")
        title = clip.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"clip {key} has no title")
        if not isinstance(clip.get("opener", False), bool):
            errors.append(f"clip {key} has a non-true/false opener")
        if clip.get("opener") and clip.get("kind") != "continuity":
            errors.append(f"clip {key} is an opener but not a continuity line")

    for part in DAYPARTS:
        in_part = [c for c in clips if part in (c.get("dayparts") or [])]
        if not any(c.get("kind") == "programme" for c in in_part):
            errors.append(f"daypart {part} has no programmes")
        if not any(c.get("kind") == "ident" for c in in_part):
            errors.append(f"daypart {part} has no idents")
        openers = [c.get("key") for c in in_part if c.get("opener")]
        if len(openers) != 1:
            errors.append(f"daypart {part} has {len(openers)} openers, expected exactly one")

    if not clips_dir.is_dir():
        return [*errors, f"no clips folder at {clips_dir}"]
    stray = _stray_files(clips_dir)
    if stray:
        errors.append(f"files in the clips folder that are not {CLIP_SUFFIX}: {', '.join(stray)}")
    on_disk = {
        path.stem for path in clips_dir.iterdir() if path.is_file() and path.suffix == CLIP_SUFFIX
    }
    for key in sorted(seen - on_disk):
        errors.append(f"clip {key} is in the manifest but has no {key}{CLIP_SUFFIX}")
    for key in sorted(on_disk - seen):
        errors.append(f"{key}{CLIP_SUFFIX} is in the clips folder but not in the manifest")
    return errors


def write_channel3000_pack(clips_dir: Path, output: Path) -> Path:
    """Pack every ``<key>.opus`` under ``clips_dir`` as ``c3k/<key>.opus``.

    Stored, sorted, fixed timestamps and fixed host stamps: the same clips
    make the same bytes on Windows, macOS and Linux, so the SHA the release
    pins is reproducible on the owner's machine.
    """
    paths = sorted(
        (path for path in clips_dir.iterdir() if path.is_file() and path.suffix == CLIP_SUFFIX),
        key=lambda path: path.name,
    )
    if not paths:
        raise ValueError(f"No {CLIP_SUFFIX} clips under {clips_dir}")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as z:
        for path in paths:
            info = zipfile.ZipInfo(PACK_PREFIX + path.name, date_time=_EPOCH)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = _UNIX
            info.external_attr = _FILE_MODE
            z.writestr(info, path.read_bytes())
    assets_pack = _load_assets_pack()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(assets_pack.PACK_MAGIC + assets_pack._mask(buffer.getvalue()))
    return output


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summary(manifest: dict) -> list[str]:
    """Clip counts and hours per daypart, for the builder's log."""
    clips = manifest["clips"]
    lines = []
    for part in DAYPARTS:
        in_part = [c for c in clips if part in c["dayparts"]]
        programmes = [c for c in in_part if c["kind"] == "programme"]
        hours = sum(c["duration_s"] for c in programmes) / 3600
        lines.append(
            f"{part}: {len(programmes)} programmes ({hours:.2f} h), "
            f"{len(in_part) - len(programmes)} glue clips"
        )
    total = sum(c["duration_s"] for c in clips) / 3600
    lines.append(f"{len(clips)} clips, {total:.2f} hours in all")
    return lines


def build(
    source: Path,
    pack_output: Path = DEFAULT_PACK_OUTPUT,
    manifest_output: Path = DEFAULT_MANIFEST_OUTPUT,
) -> tuple[Path, Path]:
    """Validate ``source`` (holding ``clips/`` and ``clips.json``), then write both outputs."""
    clips_dir = source / "clips"
    manifest_path = source / "clips.json"
    errors = validate(load_manifest(manifest_path), clips_dir)
    if errors:
        raise ValueError(
            "Channel 3000 clips do not match their manifest:\n  " + "\n  ".join(errors)
        )
    write_channel3000_pack(clips_dir, pack_output)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(manifest_path, manifest_output)
    return pack_output, manifest_output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", type=Path, help="folder holding clips/ and clips.json")
    parser.add_argument("--out", type=Path, default=DEFAULT_PACK_OUTPUT)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST_OUTPUT)
    parser.add_argument("--check", action="store_true", help="validate only; write nothing")
    args = parser.parse_args(argv)
    manifest = load_manifest(args.source / "clips.json")
    errors = validate(manifest, args.source / "clips")
    if errors:
        print("Channel 3000 clips do not match their manifest:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    for line in summary(manifest):
        print(line)
    if args.check:
        print("Clips and manifest agree.")
        return 0
    pack, manifest_out = build(args.source, args.out, args.manifest_out)
    size_mb = pack.stat().st_size / 1e6
    print(f"Wrote {pack} ({size_mb:.1f} MB, sha256 {file_sha256(pack)})")
    print(f"Wrote {manifest_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
