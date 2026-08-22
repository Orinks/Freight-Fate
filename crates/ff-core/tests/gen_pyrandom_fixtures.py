"""Generate pyrandom_fixtures.json from CPython's own random.Random.

Run with the repo venv interpreter (CPython 3.12) from the repo root:

    .venv/Scripts/python.exe crates/ff-core/tests/gen_pyrandom_fixtures.py

Every block below builds a FRESH Random(seed) per method so each Rust
assertion stands on its own. Floats are recorded as their IEEE-754 bit
pattern (u64) so the Rust side compares bit-exactly; the repr is kept next
to it for humans reading the file. Integers that may exceed 64 bits are
written as decimal strings.
"""

from __future__ import annotations

import hashlib
import json
import random
import struct
import sys
from pathlib import Path

OUT = Path(__file__).with_name("pyrandom_fixtures.json")


def bits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def floats(xs: list[float]) -> dict:
    return {"bits": [bits(x) for x in xs], "repr": [repr(x) for x in xs]}


INT_SEEDS = [
    0,
    1,
    2,
    42,
    12345,
    2**31 - 1,
    2**32,
    2**40 + 7,
    -5,
    0x5EED ^ 99,
    2**64 - 1,
    2**64,
    2**70 + 12345,
    -(2**63),
    (1234567 << 16) ^ 777,
    (1234567 << 8) ^ int(12.34 * 50),
    987654321 * 1_000_003 + 17,
]
STR_SEEDS = [
    "parking:0:12",
    "post:7:stop:2",
    "scale:12:inspect",
    "a",
    "",
    "héllo wörld",
    "shoulder-damage:42:1234",
]

WEIGHTS = [0.1, 0.4, 0.2, 0.25, 0.05]


def block(seed) -> dict:
    def fresh():
        return random.Random(seed)

    r = fresh()
    out = {"random": floats([r.random() for _ in range(20)])}
    r = fresh()
    out["getrandbits32"] = [r.getrandbits(32) for _ in range(5)]
    r = fresh()
    out["getrandbits_mixed"] = {
        "k": [0, 1, 7, 31, 32, 33, 63, 64, 65, 100, 128],
        "values": [str(r.getrandbits(k)) for k in [0, 1, 7, 31, 32, 33, 63, 64, 65, 100, 128]],
    }
    r = fresh()
    out["randrange100"] = [r.randrange(100) for _ in range(10)]
    r = fresh()
    out["randint16"] = [r.randint(1, 6) for _ in range(10)]
    r = fresh()
    out["randrange_step"] = [r.randrange(-50, 50, 7) for _ in range(10)]
    r = fresh()
    out["randrange_negstep"] = [r.randrange(50, -50, -3) for _ in range(10)]
    r = fresh()
    out["randrange_big"] = [str(r.randrange(2**40 + 3)) for _ in range(6)]
    r = fresh()
    out["randbelow_huge"] = [str(r._randbelow(2**70 + 5)) for _ in range(4)]
    r = fresh()
    out["uniform"] = floats([r.uniform(-3.5, 10.25) for _ in range(10)])
    r = fresh()
    out["choice7"] = [r.choice(list(range(7))) for _ in range(10)]
    r = fresh()
    out["choices_weighted"] = r.choices(range(5), weights=WEIGHTS, k=10)
    r = fresh()
    out["choices_unweighted"] = r.choices(range(5), k=10)
    r = fresh()
    out["choices_cum"] = r.choices(range(4), cum_weights=[1, 3, 3, 10], k=10)
    r = fresh()
    out["choices_intweights"] = r.choices(["a", "b", "c"], [5, 1, 4], k=10)
    r = fresh()
    out["sample_pool"] = r.sample(range(50), 8)
    r = fresh()
    out["sample_set"] = r.sample(range(500), 3)
    r = fresh()
    out["sample_pool_k6"] = r.sample(range(60), 6)
    r = fresh()
    out["sample_set_k6"] = r.sample(range(100), 6)
    r = fresh()
    out["expovariate"] = floats([r.expovariate(1 / 45) for _ in range(5)])
    r = fresh()
    out["gauss"] = floats([r.gauss(0.0, 1.0) for _ in range(6)])
    r = fresh()
    out["normalvariate"] = floats([r.normalvariate(2.0, 3.0) for _ in range(6)])
    r = fresh()
    out["triangular"] = floats([r.triangular(1.0, 9.0, 3.0) for _ in range(4)])
    r = fresh()
    lst = list(range(12))
    r.shuffle(lst)
    out["shuffle12"] = lst
    r = fresh()
    first3 = [r.random() for _ in range(3)]
    state = r.getstate()
    after5 = [r.random() for _ in range(5)]
    r.setstate(state)
    restored5 = [r.random() for _ in range(5)]
    assert after5 == restored5
    version, internal, gauss_next = state
    out["state_roundtrip"] = {
        "first3": floats(first3),
        "after5": floats(after5),
        "index": internal[-1],
        "mt_head": list(internal[:4]),
        "mt_tail": list(internal[620:624]),
    }
    # gauss_next survives getstate/setstate
    r = fresh()
    g1 = r.gauss(0.0, 1.0)
    st = r.getstate()
    g2 = r.gauss(0.0, 1.0)
    r.setstate(st)
    assert r.gauss(0.0, 1.0) == g2
    out["gauss_state"] = {
        "g1": bits(g1),
        "g2": bits(g2),
        "gauss_next_bits": bits(st[2]) if st[2] is not None else None,
    }
    # the very first 624-word state after seeding, as a digest-friendly head
    r = fresh()
    internal = r.getstate()[1]
    out["initial_state"] = {"index": internal[-1], "mt": list(internal[:624])}
    return out


def main() -> None:
    assert sys.version_info[:2] == (3, 12), sys.version
    fixtures: dict = {"python": sys.version, "seeds": []}
    for s in INT_SEEDS:
        fixtures["seeds"].append({"kind": "int", "seed": str(s), **block(s)})
    for s in STR_SEEDS:
        fixtures["seeds"].append({"kind": "str", "seed": s, **block(s)})
    # str -> int words (the init_by_array key), to pin the sha512 path itself
    fixtures["str_seed_words"] = []
    for s in STR_SEEDS:
        b = s.encode()
        n = int.from_bytes(b + hashlib.sha512(b).digest(), "big")
        nbits = n.bit_length()
        keyused = 1 if nbits == 0 else (nbits - 1) // 32 + 1
        words = [(n >> (32 * i)) & 0xFFFFFFFF for i in range(keyused)]
        fixtures["str_seed_words"].append({"s": s, "words": words})
    # sha256 prefix-16 seeding, exactly as sim/traffic_manager.py
    fixtures["sha256_prefix16"] = []
    for key in ["traffic-manager:42:I-80", "traffic-manager:7:US-50:cell:13", "", "x"]:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        seed = int(digest[:16], 16)
        r = random.Random(seed)
        fixtures["sha256_prefix16"].append(
            {"key": key, "seed": str(seed), "random": floats([r.random() for _ in range(5)])}
        )
    OUT.write_text(json.dumps(fixtures, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
