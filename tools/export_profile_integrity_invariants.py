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
        return 0 if args.output.read_text(encoding="utf-8") == content else 1
    args.output.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
