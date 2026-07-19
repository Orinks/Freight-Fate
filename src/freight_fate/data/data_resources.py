"""Runtime data files that ship baked into frozen builds.

Source checkouts read the JSON files that live next to this module.
Release builds compile them into ``_baked_data`` (tools/bake_data.py) so
packaged builds ship no editable data files next to the executable --
the same policy as the world (``_baked_world``) and the sound pack.

Every runtime loader of a loose data file under ``freight_fate/data``
must go through :func:`read_data_text`; reading ``Path(__file__)``
siblings directly works in a source checkout and silently (or loudly)
breaks in a frozen build.
"""

from __future__ import annotations

from pathlib import Path

_DATA_DIR = Path(__file__).parent

# Every file bake_data.py compiles into frozen builds. Keeping the list
# here, next to the reader, means a new runtime data file only needs one
# registration to reach both source and packaged players.
BAKED_DATA_FILES = (
    "buffs.json",
    "city_services.json",
    "facility_approaches.json",
    "facility_endpoints.json",
    "local_approaches.json",
    "local_geometry.json",
    "radio_catalog.json",
    "world_data/us/gameplay/curves.jsonl",
)


def read_data_text(relative: str) -> str | None:
    """The text of a runtime data file, baked or from the source tree.

    Returns None when the file does not exist in either place; callers
    that cannot degrade gracefully raise on None themselves.
    """
    try:
        from . import _baked_data
    except ImportError:
        path = _DATA_DIR / Path(relative)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")
    return _baked_data.load().get(relative)
