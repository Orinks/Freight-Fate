"""Generate release notes for the build workflow.

* ``stable``: extracts the matching version's section from CHANGELOG.md.
* ``nightly``: a short developer-snapshot header plus the commit subjects
  since the previous nightly tag (or the last 10 on a first run).

Usage:
    python tools/release_notes.py stable --version 1.5.0 --output notes.md
    python tools/release_notes.py nightly --previous-tag nightly-20260609 \
        --output notes.md
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def stable_notes(version: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    pattern = rf"^## {re.escape(version)}\b.*?$(.*?)(?=^## |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        return f"Freight Fate {version}. See CHANGELOG.md for details."
    return match.group(1).strip()


def nightly_notes(previous_tag: str) -> str:
    rev_range = f"{previous_tag}..HEAD" if previous_tag else "-10"
    log = subprocess.run(
        ["git", "log", "--no-merges", "--pretty=format:- %s", rev_range],
        capture_output=True, text=True, cwd=ROOT, check=False,
    ).stdout.strip()
    header = (
        "Automated developer snapshot of the main branch, for players who "
        "want the newest features before the next stable release. "
        "Expect rough edges; your save files stay compatible whenever "
        "possible, but back them up first.\n\n"
        "## Changes since the previous snapshot\n"
    )
    return header + (log or "- No commit details available.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["stable", "nightly"])
    parser.add_argument("--version", default="")
    parser.add_argument("--previous-tag", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.kind == "stable":
        if not args.version:
            parser.error("stable notes need --version")
        notes = stable_notes(args.version.lstrip("v"))
    else:
        notes = nightly_notes(args.previous_tag)
    Path(args.output).write_text(notes + "\n", encoding="utf-8")
    print(notes[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
