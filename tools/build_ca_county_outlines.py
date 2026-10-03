"""Write the California county outlines the Caltrans district lookup reads.

Caltrans publishes lane closures one district at a time, and a district is a
set of whole counties. The game has only a route's coordinates, so it needs
the counties' shapes to know which district feeds a route crosses. This tool
reads them from the U.S. Census Bureau's cartographic boundary file (public
domain) and writes ``crates/ff-core/src/sim/real_traffic/ca_county_outlines.txt``.

The 1:20,000,000 file is used because it is small (about 1,900 vertices for
all 58 counties). Its generalisation moves a boundary by at most a few miles;
``--measure`` reports that bound against the detailed 1:500,000 file, and the
Rust lookup widens every county by it.

Usage::

    uv run python tools/build_ca_county_outlines.py
    uv run python tools/build_ca_county_outlines.py --measure
"""

from __future__ import annotations

import argparse
import math
import os
import struct
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "crates" / "ff-core" / "src" / "sim" / "real_traffic" / "ca_county_outlines.txt"
CACHE_DIR = Path(os.environ.get("FF_CENSUS_CACHE", Path.home() / ".cache" / "freight-fate-census"))
URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_{scale}.zip"
CALIFORNIA_FIPS = "06"
MILES_PER_DEGREE = 69.17


def fetch(scale: str) -> Path:
    path = CACHE_DIR / f"cb_2023_us_county_{scale}.zip"
    if not path.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL.format(scale=scale), path)
    return path


def read_dbf(data: bytes) -> list[dict[str, str]]:
    count, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields = []
    offset = 32
    while data[offset] != 0x0D:
        fields.append((data[offset : offset + 11].split(b"\0")[0].decode(), data[offset + 16]))
        offset += 32
    rows = []
    for index in range(count):
        record = data[header_len + index * record_len : header_len + (index + 1) * record_len]
        pos = 1
        row = {}
        for name, width in fields:
            row[name] = record[pos : pos + width].decode("latin-1").strip()
            pos += width
        rows.append(row)
    return rows


def read_polygons(data: bytes) -> list[list[list[tuple[float, float]]]]:
    shapes = []
    offset = 100
    while offset < len(data):
        _, words = struct.unpack(">II", data[offset : offset + 8])
        body = data[offset + 8 : offset + 8 + words * 2]
        offset += 8 + words * 2
        if struct.unpack("<i", body[:4])[0] != 5:
            shapes.append([])
            continue
        parts_n, points_n = struct.unpack("<ii", body[36:44])
        parts = list(struct.unpack(f"<{parts_n}i", body[44 : 44 + 4 * parts_n]))
        base = 44 + 4 * parts_n
        points = [
            struct.unpack("<dd", body[base + 16 * k : base + 16 * k + 16]) for k in range(points_n)
        ]
        bounds = parts[1:] + [points_n]
        shapes.append([points[start:end] for start, end in zip(parts, bounds, strict=True)])
    return shapes


def california(zip_path: Path) -> dict[str, list[list[tuple[float, float]]]]:
    archive = zipfile.ZipFile(zip_path)
    names = archive.namelist()
    rows = read_dbf(archive.read(next(n for n in names if n.endswith(".dbf"))))
    shapes = read_polygons(archive.read(next(n for n in names if n.endswith(".shp"))))
    return {
        row["NAME"]: rings
        for row, rings in zip(rows, shapes, strict=True)
        if row["STATEFP"] == CALIFORNIA_FIPS
    }


def segment_miles(p, q, r) -> float:
    """Distance in miles from p to segment q-r, flat-earth about p."""
    kx = math.cos(math.radians(p[1])) * MILES_PER_DEGREE
    qx, qy = (q[0] - p[0]) * kx, (q[1] - p[1]) * MILES_PER_DEGREE
    rx, ry = (r[0] - p[0]) * kx, (r[1] - p[1]) * MILES_PER_DEGREE
    dx, dy = rx - qx, ry - qy
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, -(qx * dx + qy * dy) / length))
    return math.hypot(qx + t * dx, qy + t * dy)


def measure(coarse: dict, fine: dict) -> None:
    """Report the farthest a detailed boundary vertex sits from the coarse outline."""
    worst = (0.0, "", None)
    for name, rings in coarse.items():
        segments = [(ring[i], ring[i + 1]) for ring in rings for i in range(len(ring) - 1)]
        for ring in fine[name]:
            # Offshore islands the coarse file drops carry no road.
            if len(ring) < 300:
                continue
            for point in ring:
                miles = min(segment_miles(point, q, r) for q, r in segments)
                if miles > worst[0]:
                    worst = (miles, name, point)
    print(f"max deviation {worst[0]:.2f} mi ({worst[1]} at {worst[2]})")


def write(counties: dict) -> None:
    lines = [
        "# California county outlines for the Caltrans district lookup.",
        "# Read: U.S. Census Bureau 2023 cartographic boundary file, counties,",
        "# 1:20,000,000 (cb_2023_us_county_20m.zip), public domain. Coordinates",
        "# rounded to 4 decimals. Regenerate: uv run python tools/build_ca_county_outlines.py",
        "# One ring per line: county name, a tab, then lon,lat pairs separated by spaces.",
    ]
    for name in sorted(counties):
        for ring in counties[name]:
            pairs = " ".join(f"{lon:.4f},{lat:.4f}" for lon, lat in ring)
            lines.append(f"{name}\t{pairs}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(counties)} counties, {len(lines) - 5} rings)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--measure", action="store_true", help="report the outline error against the 1:500,000 file"
    )
    args = parser.parse_args()
    coarse = california(fetch("20m"))
    if len(coarse) != 58:
        print(f"expected 58 California counties, read {len(coarse)}", file=sys.stderr)
        return 1
    if args.measure:
        measure(coarse, california(fetch("500k")))
        return 0
    write(coarse)
    return 0


if __name__ == "__main__":
    sys.exit(main())
