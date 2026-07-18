"""Frozen builds carry the loose runtime data files baked into a module.

The 1.9 canary crash (2026-07-18): the packaged build shipped without
buffs.json because loose data files under freight_fate/data were never
included -- source runs read the files directly and hid the gap. Now
every registered file bakes into _baked_data (tools/bake_data.py) and
read_data_text serves both worlds.
"""

import importlib.util
import sys
from pathlib import Path

from freight_fate.data.data_resources import BAKED_DATA_FILES, read_data_text

DATA_DIR = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "data"


def test_every_registered_file_exists_and_reads():
    for name in BAKED_DATA_FILES:
        assert (DATA_DIR / Path(name)).exists(), name
        text = read_data_text(name)
        assert text, f"read_data_text returned nothing for {name}"


def test_bake_round_trips(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    try:
        import bake_data
    finally:
        sys.path.pop(0)

    out = bake_data.bake(output=tmp_path / "_baked_data.py")
    spec = importlib.util.spec_from_file_location("baked_under_test", out)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = module.load()

    assert set(payload) == set(BAKED_DATA_FILES)
    for name in BAKED_DATA_FILES:
        assert payload[name] == (DATA_DIR / Path(name)).read_text(encoding="utf-8"), name


def test_missing_file_is_none_not_crash():
    assert read_data_text("no_such_file.json") is None


def test_no_direct_package_json_reads():
    """Source tripwire: game code must read packaged data files through
    read_data_text, never straight off disk -- a direct read works in a
    source checkout and breaks (loudly or silently) in a frozen build.

    Files that legitimately read json elsewhere: data_resources itself,
    the world loader chain (covered by _baked_world), and modules that
    read the player's own save data. Individual sanctioned lines carry a
    "runtime-data-ok" marker."""
    import re

    src = Path(__file__).resolve().parents[1] / "src" / "freight_fate"
    allowed_files = {
        "data_resources.py",  # the sanctioned reader
        "world.py",  # prefers _baked_world, file read is the source fallback
        "world_loader.py",  # only ever called on the source world_data tree
    }
    pattern = re.compile(r"\.jsonl?[\"']")
    read_pattern = re.compile(r"read_text|\.open\(")
    offenders = []
    for path in src.rglob("*.py"):
        if path.name in allowed_files:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if (
                pattern.search(line)
                and read_pattern.search(line)
                and "runtime-data-ok" not in line
            ):
                offenders.append(f"{path.relative_to(src)}:{i}: {line.strip()}")
    assert offenders == [], "direct package json reads: " + "; ".join(offenders[:5])
