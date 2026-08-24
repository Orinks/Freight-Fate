"""Generate pyfmt_fixtures.json: what CPython prints, for ff_core::pyfmt to match.

Run from the repo root with the project venv:

    .venv/Scripts/python.exe crates/ff-core/tests/gen_pyfmt_fixtures.py

Every float is written as its repr so the Rust side can parse it back
exactly (repr round-trips; "inf"/"nan" parse too). The Rust tests in
crates/ff-core/src/pyfmt.rs read the JSON next to this file.
"""

from __future__ import annotations

import json
import math
import random
import struct
from pathlib import Path

OUT = Path(__file__).with_name("pyfmt_fixtures.json")

rng = random.Random(20260822)

# Hand-picked values: ties, classic "2.675" binary surprises, magnitudes
# either side of the repr exponent switch, zeros of both signs, non-finite.
HAND = [
    0.0,
    -0.0,
    0.5,
    -0.5,
    1.5,
    2.5,
    3.5,
    -1.5,
    -2.5,
    0.25,
    0.75,
    0.125,
    0.375,
    1.005,
    2.675,
    1.045,
    0.045,
    12.345,
    12.355,
    99.995,
    0.4,
    -0.4,
    -0.04,
    1e15,
    1e16,
    1e17,
    9999999999999998.0,
    1e22,
    1e23,
    1.5e16,
    123456789012345678.0,
    0.001,
    0.0001,
    0.00001,
    0.000123,
    1.2e-5,
    1e-7,
    5e-324,
    1.7976931348623157e308,
    1.0,
    -1.0,
    10.0,
    100.0,
    1234.5,
    1234567.891,
    -1234567.891,
    999.5,
    1000.5,
    25.0,
    35.0,
    45.0,
    250.0,
    350.0,
    1250.0,
    15.0,
    0.3,
    2.0 / 3.0,
    1.0 / 3.0,
    123.456,
    0.1 + 0.2,
    4.35,
    4.45,
    4.55,
    1e100,
    1e-100,
    123456.7,
    65.0,
    104.60736,
    1.609344,
    38.0 * 1.609344,
    0.62 * 1.609344,
    55.0 * 1.609344,
    math.inf,
    -math.inf,
    math.nan,
]

RANDOM: list[float] = []
for _ in range(400):
    mag = rng.choice([-6, -3, -1, 0, 1, 2, 3, 6, 9, 15, 16, 17, 20])
    x = rng.uniform(-1.0, 1.0) * 10.0**mag
    RANDOM.append(x)
for _ in range(200):
    # Integer-and-a-half style ties at a few scales.
    scale = rng.choice([1.0, 10.0, 100.0, 1000.0])
    RANDOM.append((rng.randint(-5000, 5000) + 0.5) / scale)
for _ in range(100):
    # Quarter steps: exact binary fractions that tie at one decimal.
    RANDOM.append(rng.randint(-400, 400) / 4.0)

VALUES = HAND + RANDOM

# Extra values for str(float) only: random bit patterns, and quarter steps
# around 1e14-1e15 where the shortest 16-digit rendering can be an exact tie
# (...710.25 -> "...710.2", half-even; a shortest-digits algorithm that does
# not break ties to even says "...710.3").

REPR_EXTRA: list[float] = []
while len(REPR_EXTRA) < 3000:
    (x,) = struct.unpack("<d", rng.getrandbits(64).to_bytes(8, "little"))
    if math.isfinite(x):
        REPR_EXTRA.append(x)
for _ in range(2000):
    base = rng.randint(10**13, 10**15)
    REPR_EXTRA.append(base + rng.choice([0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875]))
for _ in range(1000):
    base = rng.randint(10**15, 10**16)
    REPR_EXTRA.append(float(base) + rng.choice([0.5, 1.0, 1.5, 2.0]))


def r(x: float) -> str:
    return repr(x)


def gen_round_py():
    # Python's round() with no ndigits returns an int: no sign on zero, and
    # exact for huge values. Recorded as the int's repr.
    out = []
    for x in VALUES:
        if math.isfinite(x):
            out.append([r(x), str(round(x))])
    return out


def gen_round_py_n():
    out = []
    for x in VALUES:
        for n in (-3, -2, -1, 0, 1, 2, 3, 4):
            out.append([r(x), n, r(round(x, n))])
    # ndigits beyond the decimal range.
    for x in (1.5, -1.5, 0.0, -0.0, 123.456, math.inf, math.nan):
        for n in (-400, -309, -308, 323, 324, 400):
            out.append([r(x), n, r(round(x, n))])
    return out


def gen_fmt_f():
    out = []
    for x in VALUES:
        for p in (0, 1, 2, 3):
            out.append([r(x), p, f"{x:.{p}f}"])
    return out


def gen_fmt_grouped():
    out = []
    for x in VALUES:
        for p in (0, 1, 2):
            out.append([r(x), p, f"{x:,.{p}f}"])
    return out


def gen_fmt_int_grouped():
    ints = [
        0,
        1,
        -1,
        9,
        10,
        99,
        100,
        999,
        1000,
        -1000,
        12345,
        123456,
        1234567,
        -1234567,
        10**9,
        -(10**9),
        2**63 - 1,
        -(2**63),
    ]
    ints += [rng.randint(-(10**12), 10**12) for _ in range(100)]
    return [[i, f"{i:,d}"] for i in ints]


def gen_py_int():
    out = []
    for x in VALUES:
        if math.isfinite(x) and abs(x) < 2**62:
            out.append([r(x), int(x)])
    return out


def gen_py_str_float():
    return [[r(x), str(x)] for x in VALUES + REPR_EXTRA]


def gen_pct02():
    return [[i, f"{i:02d}"] for i in list(range(-12, 125)) + [1000, -1000]]


fixtures = {
    "round_py": gen_round_py(),
    "round_py_n": gen_round_py_n(),
    "fmt_f": gen_fmt_f(),
    "fmt_grouped": gen_fmt_grouped(),
    "fmt_int_grouped": gen_fmt_int_grouped(),
    "py_int": gen_py_int(),
    "py_str_float": gen_py_str_float(),
    "pct02": gen_pct02(),
}
OUT.write_text(json.dumps(fixtures, indent=0) + "\n", encoding="utf-8")
print(OUT, {k: len(v) for k, v in fixtures.items()})
