"""Baked speed-limit profiles stay free of wrong-road anchor pollution.

`tools/repair_interstate_anchor_limits.py` encodes the judgment that no US
interstate mainline opens below 45 mph and that a lone city-street anchor
must not rule a whole highway leg. The 2026-07-14 repair fixed 680 polluted
legs; this test makes that judgment permanent: any future data sweep that
reintroduces the pollution fails CI instead of waiting for someone to
remember the linter. The tool's dry run must always report zero.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_repair_tool():
    """Import tools/repair_interstate_anchor_limits.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "repair_interstate_anchor_limits",
        ROOT / "tools" / "repair_interstate_anchor_limits.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["repair_interstate_anchor_limits"] = module
    spec.loader.exec_module(module)
    return module


def test_no_anchor_polluted_speed_profiles() -> None:
    tool = _load_repair_tool()
    data = json.loads(tool.WORLD_PATH.read_text(encoding="utf-8"))
    repaired = tool.repair(data)
    details = "; ".join(f"{entry['leg']} ({entry['highway']})" for entry in repaired[:5])
    assert repaired == [], (
        f"{len(repaired)} legs carry wrong-road anchor speed limits again "
        f"(first few: {details}). A data sweep reintroduced the pollution -- "
        "fix the bake, do not hand-edit; see tools/repair_interstate_anchor_limits.py."
    )
