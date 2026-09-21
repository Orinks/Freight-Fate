"""list511 parser: the 511 sites' own list-page JSON plus map pins.

fl511.com and 511ny.org publish work zones on a standard WZDx feed but no
incidents; the incident data rides the endpoints their own site pages use,
verified keyless 2026-08-20:

  ``POST /List/GetData/<layer>``  — DataTables-style list rows with the full
      event text (``id``, ``roadwayName``, ``description``, ``severity``,
      ``isFullClosure``, ``laneDescription``, ``locationDescription``,
      ``county``, date strings).  Needs the paging fields and one column
      definition or ``data`` comes back empty; a page caps at 100 rows.
  ``GET /map/mapIcons/<layer>``   — the map pins: ``{"item2": [{"itemId":
      ..., "location": [lat, lon]}, ...]}``.  Joined on the event id to give
      the list rows coordinates.

Split out of ``real_traffic_parsers`` to keep that module at a reviewable
size.  The fetch side (paging, the pin join) lives in ``real_traffic``.
"""

from __future__ import annotations

import html
import logging
import re

from .real_traffic_parsers import TrafficEvent

log = logging.getLogger(__name__)


class List511Parsers:
    """Mixin with the list511 response parsers for RealTrafficProvider."""

    def _parse_list511_events(
        self,
        rows: list[dict],
        locations: dict[str, tuple[float, float]],
        state: str,
    ) -> list[TrafficEvent]:
        """Parse incidents from list511 list rows plus map-pin locations.

        ``rows`` are the ``data`` entries from ``POST /List/GetData/<layer>``
        (fetched 2026-08-20 from fl511.com and 511ny.org: ``id``,
        ``roadwayName``, ``description``, ``severity``, ``isFullClosure``,
        ``laneDescription``, ``locationDescription``, ``county``, date
        strings).  ``locations`` maps event id to ``(lat, lon)`` from the
        matching ``/map/mapIcons/<layer>`` fetch; rows without a pin keep
        ``None`` coordinates and fall out of the distance filters.
        """
        events: list[TrafficEvent] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                event_id = str(row.get("id") or row.get("DT_RowId") or "")
                if not event_id:
                    continue

                description = self._clean_list511_text(str(row.get("description") or ""))
                if not description:
                    continue

                # Site severities are Minor/Moderate/Major (NY) and
                # Minor/Intermediate/Major (FL); a flagged full closure
                # outranks whatever the row says.
                if row.get("isFullClosure") is True:
                    severity = "high"
                else:
                    severity = self._map_severity(str(row.get("severity") or ""))

                lat, lon = locations.get(event_id, (None, None))

                # NY separates location parts with "|" ("West 179th Street|")
                location_text = str(row.get("locationDescription") or "")
                location_text = ", ".join(
                    part.strip() for part in location_text.split("|") if part.strip()
                )

                lanes = str(row.get("laneDescription") or "").strip() or None

                events.append(
                    TrafficEvent(
                        id=event_id,
                        event_type="incident",
                        severity=severity,
                        description=description,
                        county=str(row.get("county") or ""),
                        latitude=lat,
                        longitude=lon,
                        start_time=str(row.get("startDate") or "") or None,
                        estimated_end=str(row.get("endDate") or "") or None,
                        lanes_affected=lanes,
                        road_name=str(row.get("roadwayName") or ""),
                        location_text=location_text,
                    )
                )
            except (TypeError, ValueError, KeyError) as e:
                log.debug(f"Failed to parse list511 row: {e}")
                continue
        return events

    def _parse_list511_icon_locations(self, data: object) -> dict[str, tuple[float, float]]:
        """Extract ``id -> (lat, lon)`` from a ``/map/mapIcons`` response.

        Shape (fetched 2026-08-20): ``{"item1": {...icon style...},
        "item2": [{"itemId": "815973", "location": [lat, lon], ...}, ...]}``.
        """
        locations: dict[str, tuple[float, float]] = {}
        if not isinstance(data, dict):
            return locations
        pins = data.get("item2")
        if not isinstance(pins, list):
            return locations
        for pin in pins:
            if not isinstance(pin, dict):
                continue
            loc = pin.get("location")
            item_id = str(pin.get("itemId") or "")
            if not item_id or not isinstance(loc, list) or len(loc) < 2:
                continue
            try:
                locations[item_id] = (float(loc[0]), float(loc[1]))
            except (TypeError, ValueError):
                continue
        return locations

    def _clean_list511_text(self, text: str) -> str:
        """Reduce a list511 description to clean spoken text.

        The sites embed HTML (a ``cellSpacer`` div duplicating the comment
        field), trailing source tags like ``[CARS CAD-262320295]``, and a
        site-clock "Last updated at ..." sentence that would clash with the
        game clock when read aloud.
        """
        text = re.sub(r"<div class='cellSpacer'>.*", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s*Last updated at [^.]+\.$", "", text)
        text = re.sub(r"\s*\[[^\][]*\]$", "", text)
        return text.strip()


__all__ = ["List511Parsers"]
