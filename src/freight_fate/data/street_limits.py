"""Statutory street speed limits, per state, with the law behind each one.

A city street is very rarely tagged in OpenStreetMap: measured across the
cached extracts, `service` ways carry a `maxspeed` on 0.2 to 1.3 percent of
their length and `residential` on 2 to 14 percent (`tools/maxspeed_coverage.py`).
So the last mile into a facility cannot be READ, and for a long time the game
filled the gap with a flat 25 that nothing stood behind.

What does stand behind it is the law. Every state's vehicle code sets a
default speed limit for business and residence districts that governs
precisely when no sign is posted -- which is the situation the map leaves us
in. That number is a reading from a published legal source, not a guess, so
this layer is `read` in the provenance sense even though no surveyor measured
the street.

The curated table with its citations lives in `tools/statutory_limits.py`;
this module loads what that tool bakes and answers questions about it. A
state the table does not cover falls back to `FALLBACK_MPH`, which is
`assumed` and says so through `is_assumed`.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

STREET_LIMITS_PATH = Path(__file__).parent / "street_limits.json"

# Where the table is silent. Not a number anyone legislated: it is the old
# blanket access-road speed, kept only so an uncovered state still drives.
FALLBACK_MPH = 25.0

# Nothing in any state's code puts an ordinary street outside this band, so a
# row beyond it is a transcription error rather than an unusual jurisdiction.
MIN_PLAUSIBLE_MPH = 10.0
MAX_PLAUSIBLE_MPH = 45.0


@dataclass(frozen=True)
class StatutoryLimit:
    """One state's default limits for unposted streets, and its citation."""

    state: str
    business_mph: float | None
    residence_mph: float | None
    urban_mph: float | None
    citation: str
    title: str
    url: str
    rule_type: str  # "absolute" or "prima facie"
    signs_required: bool
    truck_note: str
    verified: bool
    notes: str
    # True where the state's code genuinely writes no district default --
    # a researched finding, not a missing row. Connecticut is the case: a
    # limit there exists only where a traffic authority has established and
    # SIGNED a zone, so the legally correct figure for an unposted street is
    # the 55 ceiling, which is not a number to drive a yard approach at. The
    # runtime falls back for these exactly as it does for an unknown state.
    no_district_default: bool = False

    @property
    def facility_street_mph(self) -> float | None:
        """The number to post on the way in to a freight facility.

        A warehouse, terminal, or cross-dock stands in a business or
        industrial district, so the business-district figure is the one that
        governs. States that write a single urban-district limit instead
        answer with that, and the residence figure is the last resort -- some
        codes give only that one, and a residential street is still nearer to
        a yard approach than any highway default.

        None where the state's own figures do not reach an UNPOSTED street,
        which is the only situation this table exists for. Pennsylvania is the
        case that forced the check: 75 Pa.C.S. 3362(b)(1) makes its 35 mph
        urban and 25 mph residence limits ineffective unless signs stand at
        both ends of the zone and every half mile between, so on a street with
        no sign the enforceable maximum is the 55 ceiling instead. Reading
        Pennsylvania's 35 off the page and posting it would have been the
        exact failure this layer was built to stop -- a number that is real in
        the statute and false on the road.
        """
        if self.signs_required:
            return None
        for value in (self.business_mph, self.urban_mph, self.residence_mph):
            if value is not None:
                return value
        return None


class StreetLimits:
    """The loaded table. Lookup is by the spoken state name the world uses."""

    def __init__(self, rows: dict[str, StatutoryLimit], meta: dict) -> None:
        self._rows = rows
        self.meta = meta

    def get(self, state: str) -> StatutoryLimit | None:
        return self._rows.get(state.strip())

    def statutory_mph(self, state: str) -> float | None:
        """The number the law really gives for an unposted street here, or None.

        THE one rule, so that every view of this table agrees. It said
        different things in two places for an afternoon: this accessor handed
        back an unverified state's figure while `is_assumed` called the same
        state assumed, and only the trip's own separate `verified` check kept
        an unconfirmed number off the road. Three views, one rule, no third
        place to forget.

        None when the state is unknown, when its code writes no district
        default, when its figures only bind once signs are posted, or when
        nobody could confirm the reading.
        """
        row = self.get(state)
        if row is None or not row.verified:
            return None
        return row.facility_street_mph

    def facility_street_mph(self, state: str) -> float:
        """The number to drive by: the law where there is one, else the
        fallback. Never raises, never returns None."""
        value = self.statutory_mph(state)
        return FALLBACK_MPH if value is None else value

    def is_assumed(self, state: str) -> bool:
        """True when the answer for ``state`` is the fallback rather than law."""
        return self.statutory_mph(state) is None

    def __len__(self) -> int:
        return len(self._rows)

    def __contains__(self, state: str) -> bool:
        return state.strip() in self._rows


def _limit(value, path: Path, state: str, field: str) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not MIN_PLAUSIBLE_MPH <= number <= MAX_PLAUSIBLE_MPH:
        raise ValueError(
            f"{path} {state} {field} is {number}, outside the plausible street "
            f"band {MIN_PLAUSIBLE_MPH}-{MAX_PLAUSIBLE_MPH}"
        )
    return number


def parse_street_limits(raw: dict, path: Path = STREET_LIMITS_PATH) -> StreetLimits:
    records = raw.get("limits", {})
    if not isinstance(records, dict):
        raise ValueError(f"{path} must contain a limits object")
    rows: dict[str, StatutoryLimit] = {}
    for state, entry in records.items():
        citation = str(entry.get("citation", "")).strip()
        url = str(entry.get("url", "")).strip()
        verified = bool(entry.get("verified", False))
        # A verified row is a claim about the law, so it has to carry the
        # section that says so. Unverified rows are allowed to be thin --
        # that is what unverified MEANS -- but they may never be silent
        # about it, which is why `notes` is required there instead.
        if verified and not citation:
            raise ValueError(f"{path} {state} is verified with no citation")
        if not verified and not str(entry.get("notes", "")).strip():
            raise ValueError(f"{path} {state} is unverified without saying why")
        business = _limit(entry.get("business_mph"), path, state, "business_mph")
        residence = _limit(entry.get("residence_mph"), path, state, "residence_mph")
        urban = _limit(entry.get("urban_mph"), path, state, "urban_mph")
        if (
            business is None
            and residence is None
            and urban is None
            and not bool(entry.get("no_district_default", False))
        ):
            raise ValueError(
                f"{path} {state} carries no district figure and does not declare "
                "no_district_default -- an empty row must say whether that is a "
                "finding or an omission"
            )
        rule_type = str(entry.get("rule_type", "")).strip()
        if rule_type not in ("absolute", "prima facie", ""):
            raise ValueError(f"{path} {state} has unknown rule_type {rule_type!r}")
        rows[str(state).strip()] = StatutoryLimit(
            state=str(state).strip(),
            business_mph=business,
            residence_mph=residence,
            urban_mph=urban,
            citation=citation,
            title=str(entry.get("title", "")).strip(),
            url=url,
            rule_type=rule_type,
            signs_required=bool(entry.get("signs_required", False)),
            truck_note=str(entry.get("truck_note", "")).strip(),
            verified=verified,
            notes=str(entry.get("notes", "")).strip(),
            no_district_default=bool(entry.get("no_district_default", False)),
        )
    return StreetLimits(rows, dict(raw.get("meta", {})))


_cache: StreetLimits | None = None
_cache_lock = threading.Lock()


def load_street_limits(path: Path = STREET_LIMITS_PATH) -> StreetLimits:
    """The table, read once per process. Missing file reads as empty, so the
    game still drives on the fallback rather than refusing to start."""
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                if not path.exists():
                    _cache = StreetLimits({}, {})
                else:
                    _cache = parse_street_limits(json.loads(path.read_text(encoding="utf-8")), path)
    return _cache


def facility_street_mph(state: str) -> float:
    """Module-level convenience for the one caller that matters."""
    return load_street_limits().facility_street_mph(state)
