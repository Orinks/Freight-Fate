"""Prove a compiled build can still reach the platform secret store.

The online driver token lives in Windows Credential Manager, the macOS
Keychain, or Secret Service on Linux. ``keyring`` finds those backends through
entry points rather than imports, so a build that lost either the backend
modules or the distribution metadata naming them keeps every player's token in
the fallback file instead, on every platform, without a word.

Nuitka 4.1 was measured to carry both across on its own, and the release build
asks for them explicitly anyway. Neither fact is worth trusting untested: the
failure is invisible from a source checkout, where the entry points are always
present, and it would only ever show up as tokens quietly sitting in a file.
So CI compiles this probe with the release packaging flags on all three
platforms and runs it. That costs a one-file build rather than a full game
build on every pull request; the shipped binary asserts the same thing through
``freight_fate.app --smoke``.

    uv run python tools/check_keyring_packaging.py
"""

from __future__ import annotations

import sys


def main() -> int:
    from freight_fate.online_presence import secret_store_report
    from freight_fate.updater import is_frozen

    ok, detail = secret_store_report()
    # Nuitka does not set sys.frozen, so this is the project's own check --
    # the CI log has to make clear which of the two runs it is looking at.
    print(f"[{sys.platform}, {'compiled' if is_frozen() else 'source'}] {detail}")
    if not ok:
        print("FAIL: the platform secret store is not reachable from this build.")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
