"""Secondary search: nearest-neighbor connectivity gaps.

For each city, look at its K geographically-nearest neighbors. If there's no leg
to a near neighbor AND the two aren't already joined by a short 1-hop through a
third city, it's a gap. This surfaces the DENSE-region short legs the corridor
'no node between' filter drops (New England, Piedmont, SoCal, etc.).
"""
import json
import math
from collections import defaultdict

WORLD = "C:/dev/Freight-Fate-map/src/freight_fate/data/world.json"
OUT = "C:/Users/nrome/AppData/Local/Temp/claude/C--dev-Freight-Fate/6219228c-df3e-49e7-bc40-8ed9033a1a18/scratchpad/nn_gap.txt"
K = 3            # check this many nearest neighbors
MAX_MI = 120     # only care about genuinely-near neighbors
R = 3958.8

def rad(d): return d*math.pi/180
def hav(a, b):
    la1, lo1, la2, lo2 = rad(a[0]), rad(a[1]), rad(b[0]), rad(b[1])
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))

d = json.load(open(WORLD, encoding="utf-8"))
cities = d["cities"]
coord = {s: (c["lat"], c["lon"]) for s, c in cities.items()}
names = {s: c.get("spoken_city", s) for s, c in cities.items()}
region = {s: c.get("region", "?") for s, c in cities.items()}
adj = defaultdict(set)
leg = set()
for l in d["legs"]:
    adj[l["from"]].add(l["to"]); adj[l["to"]].add(l["from"])
    leg.add((l["from"], l["to"])); leg.add((l["to"], l["from"]))

slugs = list(coord)
gaps = set()
for a in slugs:
    dists = sorted(((hav(coord[a], coord[b]), b) for b in slugs if b != a))
    for dm, b in dists[:K]:
        if dm > MAX_MI: break
        if (a, b) in leg: continue
        # already joined by a 1-hop through a common neighbor that's BETWEEN them?
        onehop = adj[a] & adj[b]
        # only count as bridged if the shared neighbor is closer to the a-b line
        bridged = False
        for x in onehop:
            if hav(coord[a], coord[x]) < dm and hav(coord[b], coord[x]) < dm:
                bridged = True; break
        if not bridged:
            gaps.add((round(dm), *sorted((a, b))))

gaps = sorted(gaps)
byreg = defaultdict(int)
for dm, a, b in gaps:
    byreg[region[a]] += 1; byreg[region[b]] += 1
lines = [f"# {len(gaps)} nearest-neighbor connectivity gaps (K={K}, <{MAX_MI}mi, not 1-hop bridged)"]
lines.append("\n## by region (endpoints)")
for r, n in sorted(byreg.items(), key=lambda kv: -kv[1]):
    lines.append(f"  {n:>3}  {r}")
lines.append("\n## full list")
for dm, a, b in gaps:
    lines.append(f"  {dm:>3}mi  {names[a]},{cities[a]['state']} <-> {names[b]},{cities[b]['state']}  [{a} :: {b}]  ({region[a]})")
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines[:30]))
print(f"\n... wrote {len(gaps)} nearest-neighbor gaps to nn_gap.txt")
