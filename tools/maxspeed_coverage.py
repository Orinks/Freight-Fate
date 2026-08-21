"""How much maxspeed does OSM really carry on the local road classes a
facility approach is built from?"""

import collections
import sys

import osmium

CLASSES = {
    "residential",
    "service",
    "unclassified",
    "tertiary",
    "secondary",
    "primary",
    "living_street",
    "road",
}


class Counter(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.total = collections.Counter()
        self.tagged = collections.Counter()
        self.values = collections.Counter()
        self.named = collections.Counter()
        self.named_tagged = collections.Counter()

    def way(self, w):
        hw = w.tags.get("highway")
        if hw not in CLASSES:
            return
        self.total[hw] += 1
        ms = w.tags.get("maxspeed")
        named = bool(w.tags.get("name"))
        if named:
            self.named[hw] += 1
        if ms:
            self.tagged[hw] += 1
            self.values[ms] += 1
            if named:
                self.named_tagged[hw] += 1


for path in sys.argv[1:]:
    h = Counter()
    h.apply_file(path)
    state = path.split("/")[-1].split("-latest")[0]
    tot = sum(h.total.values())
    tag = sum(h.tagged.values())
    print(
        f"\n=== {state}: {tot:,} local ways, {tag:,} with maxspeed ({100 * tag / max(tot, 1):.1f}%)"
    )
    for hw in sorted(h.total, key=lambda k: -h.total[k]):
        t, g = h.total[hw], h.tagged[hw]
        n, ng = h.named[hw], h.named_tagged[hw]
        print(
            f"   {hw:14s} {t:8,}  maxspeed {g:7,} ({100 * g / max(t, 1):5.1f}%)   "
            f"named {n:8,} of which tagged {ng:7,} ({100 * ng / max(n, 1):5.1f}%)"
        )
    print("   most common values:", h.values.most_common(8))
