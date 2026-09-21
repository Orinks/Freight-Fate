"""Export catalogs consumed by the orinks.net cloud-save validator."""

from __future__ import annotations

import argparse
from pathlib import Path

from freight_fate.profile_integrity_invariants import rendered_invariants


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = rendered_invariants()
    if args.check:
        # newline="" so a CRLF copy is read as it was written rather than
        # translated on the way in, and the comparison is newline-blind: a
        # file exported on Windows still checks out against one exported on
        # Linux. What the validator reads is the JSON, not the line endings.
        with args.output.open("r", encoding="utf-8", newline="") as handle:
            on_disk = handle.read()
        return 0 if on_disk.replace("\r\n", "\n") == content else 1
    # newline="\n" so the same catalogs always produce the same bytes.
    # Without it Python translates on write, the export differs between a
    # Windows run and a Linux one, and two people's exports cannot be
    # compared for a reason that has nothing to do with the game.
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
