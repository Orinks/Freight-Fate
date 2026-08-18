"""Build a distributable map+radio data pack (the map-pack channel).

The producer half of in-game map updates: collects the indexed world data
tree and the radio catalog, hashes every file, and emits a pack directory
holding a manifest plus a zip of payload files. With ``--previous`` (the
last published manifest) the zip carries only files whose hashes changed —
the monthly diff pack a player downloads in seconds. Without it, the zip
is a full continental pack — the "install North America" download.

The client (2.0 feature) consumes the same manifest: check version,
verify min_game_version, download the zip, verify each file's sha256,
swap atomically at the main menu.

Deterministic by design: file order is sorted, zip entry timestamps are
fixed, and the same inputs always produce byte-identical output — so a
re-run of the same bake publishes the same pack. Pass --created to stamp
the manifest reproducibly (defaults to today, the one impure input).

Usage:
    # Full continental pack:
    uv run python tools/build_map_pack.py --pack north-america \\
        --version 2026.07 --out dist/map-packs

    # Monthly diff against the last published manifest:
    uv run python tools/build_map_pack.py --pack north-america \\
        --version 2026.08 --previous dist/map-packs/manifest.json \\
        --out dist/map-packs-aug

    # Verify a data tree against a manifest (the client's check, runnable
    # by the producer as a sanity pass):
    uv run python tools/build_map_pack.py --verify dist/map-packs/manifest.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "src" / "freight_fate" / "data"

# What ships in a pack, relative to the data dir. world_data is the indexed
# tree the game loads; the radio catalog rides along because stream URLs rot
# faster than any map layer.
PACK_CONTENTS = ("world_data", "radio_catalog.json")

# Oldest game data-schema this pack loads on. Bump when the world_data
# format changes shape; the client refuses politely instead of crashing.
MIN_GAME_VERSION = "2.0.0"

MANIFEST_NAME = "manifest.json"
# Fixed zip entry timestamp: determinism beats archaeology.
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files(data_dir: Path) -> dict[str, Path]:
    """Payload files as {pack-relative posix path: absolute path}, sorted."""
    found: dict[str, Path] = {}
    for name in PACK_CONTENTS:
        target = data_dir / name
        if target.is_file():
            found[name] = target
        elif target.is_dir():
            for path in sorted(target.rglob("*")):
                if path.is_file():
                    found[path.relative_to(data_dir).as_posix()] = path
        else:
            raise SystemExit(f"missing pack content: {target}")
    return dict(sorted(found.items()))


def build_manifest(files: dict[str, Path], *, pack: str, version: str, created: str) -> dict:
    entries = {
        rel: {"sha256": _sha256(path), "bytes": path.stat().st_size} for rel, path in files.items()
    }
    return {
        "pack": pack,
        "version": version,
        "created": created,
        "min_game_version": MIN_GAME_VERSION,
        "file_count": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries.values()),
        "files": entries,
    }


def diff_against(manifest: dict, previous: dict) -> tuple[list[str], list[str]]:
    """(changed-or-new paths, removed paths) versus the previous manifest."""
    old = previous.get("files", {})
    new = manifest["files"]
    changed = [
        rel for rel, entry in new.items() if old.get(rel, {}).get("sha256") != entry["sha256"]
    ]
    removed = [rel for rel in old if rel not in new]
    return changed, removed


def write_pack(
    out_dir: Path,
    files: dict[str, Path],
    manifest: dict,
    payload_paths: list[str],
    removed: list[str],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"{manifest['pack']}-{manifest['version']}.zip"
    zip_path = out_dir / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in sorted(payload_paths):
            info = zipfile.ZipInfo(rel, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, files[rel].read_bytes())
    manifest = dict(manifest)
    manifest["payload"] = {
        "zip": zip_name,
        "zip_sha256": _sha256(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "carries": len(payload_paths),
        "removed": sorted(removed),
    }
    manifest_path = out_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return zip_path


def verify(manifest_path: Path, data_dir: Path) -> int:
    manifest = json.loads(manifest_path.read_text())
    bad = missing = 0
    for rel, entry in manifest["files"].items():
        path = data_dir / rel
        if not path.is_file():
            print(f"MISSING  {rel}")
            missing += 1
        elif _sha256(path) != entry["sha256"]:
            print(f"CHANGED  {rel}")
            bad += 1
    ok = manifest["file_count"] - bad - missing
    print(f"{ok} verified, {bad} changed, {missing} missing of {manifest['file_count']}")
    return 0 if bad == missing == 0 else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pack", default="north-america", help="pack name (continent)")
    p.add_argument("--version", help="pack version, e.g. 2026.07")
    p.add_argument("--out", help="output directory for manifest + zip")
    p.add_argument("--previous", help="last published manifest.json to diff against")
    p.add_argument("--data-dir", default=str(DATA_DIR), help="game data directory")
    p.add_argument("--created", help="manifest date stamp (YYYY-MM-DD); default today")
    p.add_argument("--verify", help="verify a data tree against this manifest and exit")
    args = p.parse_args(argv)

    data_dir = Path(args.data_dir)
    if args.verify:
        return verify(Path(args.verify), data_dir)
    if not args.version or not args.out:
        p.error("--version and --out are required to build (or use --verify)")

    created = args.created or _dt.date.today().isoformat()
    files = collect_files(data_dir)
    manifest = build_manifest(files, pack=args.pack, version=args.version, created=created)

    if args.previous:
        previous = json.loads(Path(args.previous).read_text())
        payload, removed = diff_against(manifest, previous)
        kind = f"diff vs {previous.get('version', '?')}"
    else:
        payload, removed = list(files), []
        kind = "full"

    zip_path = write_pack(Path(args.out), files, manifest, payload, removed)
    size_mb = zip_path.stat().st_size / (1 << 20)
    print(
        f"{manifest['pack']} {manifest['version']} ({kind}): "
        f"{len(payload)} file(s) in {zip_path.name}, {size_mb:.1f} MB"
        + (f", {len(removed)} removed" if removed else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
