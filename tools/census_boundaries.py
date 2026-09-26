"""Is a point in town? Census boundaries, read without a GIS stack.

A state's in-town statutory speed limit governs only inside the territory
its code names: a business, residence or urban district (defined in the
code by how densely the road frontage is built up), or the corporate limits
of a city, town or village. Neither is drawn on any map the game has, so
the street bake uses the nearest official boundary:

* ``urban_area`` -- Census 2020 Urban Areas (TIGER/Line 2023, UAC20): the
  Bureau's own delineation of densely built-up territory, the published
  stand-in for a frontage-density district. DERIVED as that stand-in: the
  statute measures frontage, the Census measures housing and population
  density, and the two edges do not coincide street by street.
* ``municipal`` -- incorporated places (Census cartographic boundary 2023,
  1:500,000), every place whose LSAD is not a census designated place
  (57). READ: these ARE the corporate limits the code names, generalised to
  about 100 m.

The shapefiles are parsed directly (polygons, no Z/M) so the tooling needs
no GIS dependency. Download (official, U.S. Census Bureau):
  https://www2.census.gov/geo/tiger/TIGER2023/UAC/tl_2023_us_uac20.zip
  https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_place_500k.zip
into ``~/.cache/freight-fate-census/`` and unzip each into a folder of the
same name.
"""

from __future__ import annotations

import struct
from functools import cache, lru_cache
from pathlib import Path

import numpy as np

CENSUS_DIR = Path.home() / ".cache" / "freight-fate-census"
URBAN_AREAS = CENSUS_DIR / "tl_2023_us_uac20" / "tl_2023_us_uac20"
PLACES = CENSUS_DIR / "cb_2023_us_place_500k" / "cb_2023_us_place_500k"
CDP_LSAD = "57"
CELL_DEG = 0.1


def _dbf(path: Path) -> list[dict[str, str]]:
    raw = path.with_suffix(".dbf").read_bytes()
    count = struct.unpack("<I", raw[4:8])[0]
    header_len, record_len = struct.unpack("<HH", raw[8:12])
    fields = []
    i = 32
    while raw[i] != 0x0D:
        name = raw[i : i + 11].split(b"\0")[0].decode()
        fields.append((name, raw[i + 16]))
        i += 32
    rows = []
    for n in range(count):
        at = header_len + n * record_len + 1
        row = {}
        for name, width in fields:
            row[name] = raw[at : at + width].decode("latin-1").strip()
            at += width
        rows.append(row)
    return rows


def _polygons(path: Path) -> list[tuple[tuple[float, float, float, float], list[np.ndarray]]]:
    """Per record: (bbox lon/lat min-max, rings as (n, 2) lon/lat arrays)."""
    raw = path.with_suffix(".shp").read_bytes()
    out = []
    at = 100
    while at < len(raw):
        length = struct.unpack(">i", raw[at + 4 : at + 8])[0] * 2
        body = raw[at + 8 : at + 8 + length]
        at += 8 + length
        if struct.unpack("<i", body[:4])[0] != 5:
            out.append(((0.0, 0.0, 0.0, 0.0), []))
            continue
        bbox = struct.unpack("<4d", body[4:36])
        parts, points = struct.unpack("<2i", body[36:44])
        starts = list(struct.unpack(f"<{parts}i", body[44 : 44 + 4 * parts])) + [points]
        coords = np.frombuffer(body, dtype="<f8", count=2 * points, offset=44 + 4 * parts)
        coords = coords.reshape(points, 2)
        rings = [coords[starts[k] : starts[k + 1]] for k in range(parts)]
        out.append((bbox, rings))
    return out


def _contains(rings: list[np.ndarray], lon: float, lat: float) -> bool:
    """Even-odd ray cast over every ring, so holes count as outside."""
    inside = False
    for ring in rings:
        x, y = ring[:, 0], ring[:, 1]
        xn, yn = np.roll(x, -1), np.roll(y, -1)
        crosses = (y > lat) != (yn > lat)
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = x + (lat - y) * (xn - x) / (yn - y)
        inside ^= bool(np.count_nonzero(crosses & (lon < xint)) % 2)
    return inside


class _Layer:
    def __init__(self, path: Path, keep) -> None:
        rows = _dbf(path)
        shapes = _polygons(path)
        self.shapes = []
        self.grid: dict[tuple[int, int], list[int]] = {}
        for row, (bbox, rings) in zip(rows, shapes, strict=True):
            if not rings or not keep(row):
                continue
            idx = len(self.shapes)
            self.shapes.append((bbox, rings))
            for cx in range(
                int(np.floor(bbox[0] / CELL_DEG)), int(np.floor(bbox[2] / CELL_DEG)) + 1
            ):
                for cy in range(
                    int(np.floor(bbox[1] / CELL_DEG)), int(np.floor(bbox[3] / CELL_DEG)) + 1
                ):
                    self.grid.setdefault((cx, cy), []).append(idx)

    def contains(self, lat: float, lon: float) -> bool:
        cell = (int(np.floor(lon / CELL_DEG)), int(np.floor(lat / CELL_DEG)))
        for idx in self.grid.get(cell, ()):
            (x0, y0, x1, y1), rings = self.shapes[idx]
            if x0 <= lon <= x1 and y0 <= lat <= y1 and _contains(rings, lon, lat):
                return True
        return False


@cache
def _layer(kind: str) -> _Layer:
    if kind == "urban_area":
        return _Layer(URBAN_AREAS, lambda row: True)
    if kind == "municipal":
        return _Layer(PLACES, lambda row: row.get("LSAD") != CDP_LSAD)
    raise ValueError(kind)


@lru_cache(maxsize=2_000_000)
def in_town(kind: str, lat: float, lon: float) -> bool:
    """Whether a point lies inside the ``kind`` boundary (``urban_area`` or
    ``municipal``). Callers round coordinates so nearby queries share a
    cache entry."""
    return _layer(kind).contains(lat, lon)


def available() -> bool:
    return URBAN_AREAS.with_suffix(".shp").exists() and PLACES.with_suffix(".shp").exists()
