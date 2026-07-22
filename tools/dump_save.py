"""Dump a packed .ffsave profile as readable JSON, for debugging.

Save files are a magic header plus zlib-compressed JSON (see
``freight_fate.models.profile``). When a bug report arrives with a save
attached, this prints the JSON inside so the profile can actually be read:

    uv run python tools/dump_save.py "saves/profiles/Driver.ffsave"
    uv run python tools/dump_save.py Driver.ffsave -o driver.json

Legacy plain-JSON saves pass through unchanged. Deliberately dump-only:
there is no repack mode. To load an edited save for testing, run the game
from source with ``FREIGHT_FATE_SKIP_SAVE_SIGNING=1`` instead.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("save", type=Path, help="path to a .ffsave (or legacy .json) save file")
    parser.add_argument("-o", "--output", type=Path, help="write JSON here instead of stdout")
    args = parser.parse_args()

    from freight_fate.models.profile import ProfileIntegrityError, _decode_save_bytes

    try:
        data, packed = _decode_save_bytes(args.save.read_bytes())
    except OSError as e:
        print(f"error: cannot read {args.save}: {e}", file=sys.stderr)
        return 1
    except ProfileIntegrityError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    text = json.dumps(data, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
        kind = "packed container" if packed else "plain JSON"
        print(f"{args.save.name} ({kind}) -> {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
