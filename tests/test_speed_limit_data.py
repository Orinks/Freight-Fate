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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_repair_tool():
    """Import tools/repair_interstate_anchor_limits.py by path (tools is not a package).

    The tool imports its sibling world_source helper; pytest's ``pythonpath``
    setting puts tools/ on the path so that resolves here as it does in a script.
    """
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
    data = tool.load_world()
    repaired = tool.repair(data)
    details = "; ".join(f"{entry['leg']} ({entry['highway']})" for entry in repaired[:5])
    assert repaired == [], (
        f"{len(repaired)} legs carry wrong-road anchor speed limits again "
        f"(first few: {details}). A data sweep reintroduced the pollution -- "
        "fix the bake, do not hand-edit; see tools/repair_interstate_anchor_limits.py."
    )


def test_no_interstate_sample_below_45_at_any_position() -> None:
    """The 2026-07-16 class: a mid-leg city-street sample enforced on the
    interstate mainline (player-found live on I-55 toward Memphis). The
    repair tool now drops these; this direct assertion holds even if the
    tool's own rules ever drift."""
    tool = _load_repair_tool()
    data = tool.load_world()
    offenders = []
    for leg in data["legs"]:
        if not tool.is_interstate(leg.get("highway", "")):
            continue
        for row in (leg.get("corridor") or {}).get("speed_limits") or []:
            # Coverage-gap markers (mph null) are "tagging ends here", not
            # postings -- the runtime reverts to the heuristic there.
            if row["mph"] is not None and row["mph"] < tool.INTERSTATE_MIN_PLAUSIBLE_MPH:
                offenders.append(
                    f"{leg['from']}-{leg['to']} ({leg['highway']}) "
                    f"{row['mph']:.0f} mph at mile {row['at_mi']}"
                )
    assert offenders == [], (
        f"{len(offenders)} sub-45 samples on interstate legs (first few: "
        f"{'; '.join(offenders[:5])}). No US interstate mainline posts below "
        "45; these are wrong-road matches -- fix the bake, do not hand-edit."
    )
