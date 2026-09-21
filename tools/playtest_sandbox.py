"""A data directory a manual playtest can be reckless in.

A playtest career is a throwaway: it exists to reach one weigh station or one
hairpin, it gets abandoned mid-load, and it is deleted the moment the thing it
was made for has been heard. None of that belongs on the owner's account --
but a source checkout saves into ``saves/`` next to the game, which IS the
real account: the driver identity in ``online.json``, the cloud ledger in
``cloud_saves.json``, and twenty-odd careers that have been backing themselves
up to the site all along.

This puts a playtest somewhere else. It builds a sandbox data directory, seeds
it with the owner's real *settings* -- so the drive still reproduces what a
player would actually get -- and deliberately leaves the identity behind. With
no ``online.json`` the game has no driver: ``OnlineIdentity.load()`` returns
None, and every cloud backup, presence heartbeat, and profile update is a
branch that is never taken. The publishing settings are turned off in the
copy as well, so the sandbox stays silent even if somebody later signs it in
on purpose to test the online screens.

Careers are copied in by default, because most of what is worth playtesting
needs a driver who has already got somewhere: the weigh-station transponder
arrives at level four, the experience check reads out a level. They are
copies. Wreck them.

Prepare one and launch the real game inside it::

    uv run python tools/playtest_sandbox.py --launch

Start over, clean sandbox, no careers at all::

    uv run python tools/playtest_sandbox.py --reset --no-careers --launch

Print the environment for a session driven some other way::

    uv run python tools/playtest_sandbox.py --print

``tools/playtest_road.py --sandbox`` uses this, so the "drop me at a
downgrade" flow is isolated the same way.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SANDBOX = ROOT / "saves-playtest"
REAL_SAVES = ROOT / "saves"
SESSION_FILE = ROOT / "logs" / "playtest-session.json"

# Anything carrying the driver identity, or the cloud bookkeeping that hangs
# off it. Copying one of these into a sandbox is exactly how a throwaway
# career would reach the real account, so the seeding step names them rather
# than hoping a glob never matches.
IDENTITY_NAMES = frozenset(
    {
        "online.json",
        "online.token",
        "cloud_saves.json",
        "online-outbox.json",
        "online-mastodon-outbox.json",
    }
)

# The settings that publish. A sandbox with no identity cannot reach the site
# at all, so this is a second lock on the same door -- cheap, and it is the
# one that still holds if a session deliberately signs the sandbox in.
OFFLINE_SETTINGS = {
    "cloud_saves": False,
    "online_presence": False,
    "online_services": False,
    "mastodon_sharing": False,
}

# ``.ffsave`` is the signed current format. The ``.json.bak`` and
# ``.json.invalid`` leftovers beside them are not careers the game will load,
# so a sandbox does not want them cluttering its career list.
CAREER_SUFFIX = ".ffsave"


def _is_identity(path: Path) -> bool:
    """True for a file that would carry the real account into a sandbox.

    Matches the backup spellings too (``online.json.pre-clerk.bak``): a stale
    identity is still an identity, and the loader reads a driver id out of
    whichever file it is pointed at.
    """
    name = path.name
    if name in IDENTITY_NAMES:
        return True
    return name.startswith("online.json") or name.startswith("online.token")


def seed_settings(sandbox: Path, source: Path = REAL_SAVES) -> bool:
    """Copy the real settings in, with everything that publishes turned off.

    False when there is no real settings file to copy, which is not an error:
    a machine that has never run the game gets the game's own defaults, and
    that is a legitimate thing to playtest.
    """
    src = source / "settings.json"
    if not src.is_file():
        return False
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    data.update(OFFLINE_SETTINGS)
    (sandbox / "settings.json").write_text(
        json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
    )
    return True


def seed_careers(sandbox: Path, source: Path = REAL_SAVES) -> int:
    """Copy the real careers in as throwaways. Returns how many landed."""
    src = source / "profiles"
    if not src.is_dir():
        return 0
    dest = sandbox / "profiles"
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in sorted(src.glob(f"*{CAREER_SUFFIX}")):
        shutil.copy2(path, dest / path.name)
        copied += 1
    return copied


def prepare(
    sandbox: Path = DEFAULT_SANDBOX,
    *,
    reset: bool = False,
    careers: bool = True,
    source: Path = REAL_SAVES,
) -> Path:
    """Build the sandbox and point this process's game at it.

    Sets ``FREIGHT_FATE_DATA_DIR``, which has to happen before the game reads
    a save path -- the override is consulted on every ``data_dir()`` call, but
    a caller that has already resolved and cached a path keeps the old one.
    """
    if reset and sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True, exist_ok=True)
    if not (sandbox / "settings.json").exists():
        seed_settings(sandbox, source)
    if careers and not (sandbox / "profiles").exists():
        seed_careers(sandbox, source)
    os.environ["FREIGHT_FATE_DATA_DIR"] = str(sandbox)
    return sandbox


def audit(sandbox: Path = DEFAULT_SANDBOX) -> list[str]:
    """Every reason this sandbox could still reach the real account.

    An empty list is the whole guarantee this tool offers, so it is computed
    from what is on disk rather than from what the seeding step believes it
    did.
    """
    problems: list[str] = []
    for path in sorted(sandbox.rglob("*")):
        if path.is_file() and _is_identity(path):
            problems.append(f"identity file in the sandbox: {path.relative_to(sandbox)}")
    settings = sandbox / "settings.json"
    if settings.is_file():
        data: dict = {}
        try:
            loaded = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            problems.append("settings.json is unreadable; cannot confirm publishing is off")
        else:
            data = loaded if isinstance(loaded, dict) else {}
        for key, value in OFFLINE_SETTINGS.items():
            if data.get(key, value) != value:
                problems.append(f"settings.json still has {key} on")
    return problems


def describe(sandbox: Path) -> str:
    """What a prepared sandbox holds, in one block, for the session log."""
    profiles = sandbox / "profiles"
    careers = (
        sorted(p.stem for p in profiles.glob(f"*{CAREER_SUFFIX}")) if profiles.is_dir() else []
    )
    shown = ", ".join(careers[:6]) + ("..." if len(careers) > 6 else "")
    lines = [
        f"Playtest sandbox: {sandbox}",
        f"  careers: {len(careers)}" + (f" ({shown})" if careers else ""),
        f"  settings: {'copied from saves/' if (sandbox / 'settings.json').is_file() else 'game defaults'}",
    ]
    problems = audit(sandbox)
    if problems:
        lines.append("  NOT ISOLATED:")
        lines.extend(f"    - {p}" for p in problems)
    else:
        lines.append("  no driver identity: cloud backup, presence and profile updates are off")
    return "\n".join(lines)


def open_session(sandbox: Path, log_path: Path) -> Path:
    """Announce a live playtest so tools/playtest_watch.py can follow it.

    Both launchers write this -- the sandbox one and playtest_road's
    ``--sandbox`` -- because the watcher's job is the same either way, and
    the one thing it cannot work out for itself is when the player has quit
    rather than simply parked the truck and gone quiet.
    """
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "sandbox": str(sandbox),
                "log": str(log_path),
                "started": time.time(),
                "running": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return SESSION_FILE


def close_session() -> None:
    """Mark the session over. Best effort: a hard crash never reaches here,
    which is why the watcher also checks whether the pid is still alive."""
    with contextlib.suppress(OSError, ValueError):
        state = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        state["running"] = False
        state["ended"] = time.time()
        SESSION_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    """This tool's own options, and whatever is left for the game itself.

    Anything unrecognised is handed straight to ``freight_fate.app.main`` --
    ``--smoke`` above all, which is how a sandbox launch gets tested without a
    person having to sit through a window opening.
    """
    p = argparse.ArgumentParser(
        description="Run a manual playtest in a data directory that cannot reach the account.",
    )
    p.add_argument("--dir", type=Path, default=DEFAULT_SANDBOX, help="sandbox directory")
    p.add_argument("--reset", action="store_true", help="delete the sandbox and rebuild it")
    p.add_argument("--no-careers", action="store_true", help="start with no careers at all")
    p.add_argument("--launch", action="store_true", help="run the game inside the sandbox")
    p.add_argument("--log", help="session log path (default logs/playtest-manual.log)")
    p.add_argument("--print", dest="print_only", action="store_true", help="print the env and exit")
    return p.parse_known_args(argv)


def main(argv: list[str] | None = None) -> int:
    args, passthrough = parse_args(argv)
    sandbox = prepare(args.dir, reset=args.reset, careers=not args.no_careers)
    problems = audit(sandbox)
    print(describe(sandbox))
    if problems:
        # Refusing is the point. A sandbox that is only mostly isolated is
        # worse than no sandbox at all, because the operator stops watching.
        print("\nRefusing to launch: fix the above, or pass --reset.", file=sys.stderr)
        return 1
    if args.print_only:
        print(f"\nFREIGHT_FATE_DATA_DIR={sandbox}")
        return 0
    if not args.launch:
        return 0

    log_path = Path(args.log) if args.log else ROOT / "logs" / "playtest-manual.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["FREIGHT_FATE_LOG_FILE"] = str(log_path)
    os.environ.setdefault("FREIGHT_FATE_LOG", "INFO")
    print(f"\nSession log: {log_path}")

    session = open_session(sandbox, log_path)
    print(f"Session file: {session}")

    from freight_fate.app import main as game_main

    sys.argv = [sys.argv[0], *passthrough]
    try:
        return game_main()
    finally:
        close_session()


if __name__ == "__main__":
    raise SystemExit(main())
