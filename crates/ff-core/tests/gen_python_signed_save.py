"""Generate python_signed_save.json / .key: a real save, signed by Python.

Run from the repo root with the project venv, pointing at any genuine save
written by the Python game and the install key that signed it:

    .venv/Scripts/python.exe crates/ff-core/tests/gen_python_signed_save.py \
        path/to/Driver.ffsave path/to/saves/profile.key

The point of this fixture is that no Rust code produced it. A save the Rust
port writes and then reads back proves only that the port agrees with
itself; the 2026-08-23 defect (serde_json's default float parser landing one
ulp away from `float()` on a sixteen-digit duty-log hour, so every
Python-written career was greeted as "changed outside the game") survived
every such round trip and was only ever visible against bytes Python wrote.

So this reads a real career, replaces the driver's name -- the only personal
thing in a save -- and re-signs the result with the fixed test key below
using the shipped `_signature_for`. Every number is left exactly as the game
recorded it, because the long decimals are the whole test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from freight_fate.models import profile as profile_mod  # noqa: E402

# Not a secret: a fixed key so the fixture's signature is reproducible.
FIXTURE_KEY = "0" * 62 + "1f"

OUT_JSON = Path(__file__).with_name("python_signed_save.json")
OUT_KEY = Path(__file__).with_name("python_signed_save.key")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    save_path, key_path = Path(sys.argv[1]), Path(sys.argv[2])

    original_secret = profile_mod._profile_secret
    profile_mod._profile_secret = lambda: bytes.fromhex(key_path.read_text().strip())
    try:
        data, _packed = profile_mod._decode_save_bytes(save_path.read_bytes())
        if not profile_mod._is_signature_valid(data):
            raise SystemExit(f"{save_path} is not validly signed by {key_path}")
    finally:
        profile_mod._profile_secret = original_secret

    # The driver's name is the only thing in a save that belongs to a person.
    data["name"] = "Fixture Driver"

    profile_mod._profile_secret = lambda: bytes.fromhex(FIXTURE_KEY)
    try:
        data[profile_mod.SIGNATURE_FIELD] = profile_mod._signature_for(data)
        assert profile_mod._is_signature_valid(data)
    finally:
        profile_mod._profile_secret = original_secret

    OUT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8", newline="\n")
    OUT_KEY.write_text(FIXTURE_KEY + "\n", encoding="ascii", newline="\n")
    print(f"wrote {OUT_JSON} ({len(data)} keys) and {OUT_KEY}")


if __name__ == "__main__":
    main()
