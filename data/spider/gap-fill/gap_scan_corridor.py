"""Definitive adjacency-gap finder using ACTUAL ORS road geometry.

For each node pair (a,b) with no existing leg and geodesic < GEO_MAX:
  - fetch the ORS driving-hgv route polyline
  - a TRUE gap = no OTHER node lies within NEAR_MI of the route's MIDDLE (i.e.
    the road doesn't already pass through/by another city), and the road isn't a
    huge detour (driving/geo < RATIO_MAX)
This fixes the straight-line false positives (bending highways through a node).

Output: true gaps grouped by region-pair + full list, written to gap_true.txt.
"""
import json
import math
import urllib.request

GEO_MAX = 150.0
NEAR_MI = 13.0     # a node this close to the route mid = the road already serves it
END_BUF = 12.0     # ignore nodes near either endpoint
RATIO_MAX = 1.55
WORLD = "C:/dev/Freight-Fate-map/src/freight_fate/data/world.json"
OUT = "C:/Users/nrome/AppData/Local/Temp/claude/C--dev-Freight-Fate/6219228c-df3e-49e7-bc40-8ed9033a1a18/scratchpad/gap_true.txt"
R = 3958.8

def rad(d): return d * math.pi / 180.0

def hav(a, b):
    la1, lo1, la2, lo2 = rad(a[0]), rad(a[1]), rad(b[0]), rad(b[1])
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))

def route(coord, a, b):
    body = json.dumps({"coordinates": [[coord[a][1], coord[a][0]], [coord[b][1], coord[b][0]]]}).encode()
    req = urllib.request.Request(
        "http://localhost:8080/ors/v2/directions/driving-hgv/geojson",
        data=body, headers={"Content-Type": "application/json", "Authorization": "selfhosted"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=30))
        feat = r["features"][0]
        dm = feat["properties"]["summary"]["distance"] / 1609.344
        pts = [(lat, lon) for lon, lat in feat["geometry"]["coordinates"]]
        return dm, pts
    except Exception:
        return None, None

def main():
    d = json.load(open(WORLD, encoding="utf-8"))
    cities = d["cities"]
    coord = {s: (c["lat"], c["lon"]) for s, c in cities.items()}
    names = {s: c.get("spoken_city", s) for s, c in cities.items()}
    region = {s: c.get("region", "?") for s, c in cities.items()}
    legs = set()
    for l in d["legs"]:
        legs.add((l["from"], l["to"])); legs.add((l["to"], l["from"]))
    slugs = list(coord)
    # geodesic candidates
    cand = []
    for i in range(len(slugs)):
        for j in range(i+1, len(slugs)):
            a, b = slugs[i], slugs[j]
            if (a, b) in legs: continue
            gm = hav(coord[a], coord[b])
            if 10 <= gm <= GEO_MAX:
                cand.append((gm, a, b))
    true_gaps = []
    for gm, a, b in cand:
        dm, pts = route(coord, a, b)
        if dm is None or dm < 10 or dm/gm > RATIO_MAX:
            continue
        # sample every Nth polyline point for speed
        poly = pts[::max(1, len(pts)//120)]
        bridged = False
        for x in slugs:
            if x == a or x == b: continue
            cx = coord[x]
            # quick bbox reject
            if abs(cx[0]-coord[a][0]) > 3 and abs(cx[0]-coord[b][0]) > 3: continue
            mind = min(hav(cx, p) for p in poly)
            if mind < NEAR_MI:
                # ignore if it's basically at an endpoint
                if hav(cx, coord[a]) > END_BUF and hav(cx, coord[b]) > END_BUF:
                    bridged = True; break
        if not bridged:
            true_gaps.append((round(dm), a, b))
    true_gaps.sort()
    # group by region-pair
    from collections import Counter
    rc = Counter()
    for dm, a, b in true_gaps:
        key = tuple(sorted((region[a], region[b])))
        rc[key] += 1
    lines = [f"# {len(true_gaps)} TRUE adjacency gaps (route-verified: no node near the actual road)"]
    lines.append("\n## by region-pair (thinnest connectivity first)")
    for (r1, r2), n in rc.most_common():
        lines.append(f"  {n:>3}  {r1} <-> {r2}")
    # by single region (which regions appear most)
    solo = Counter()
    for dm, a, b in true_gaps:
        solo[region[a]] += 1; solo[region[b]] += 1
    lines.append("\n## by region (total gap endpoints)")
    for r1, n in solo.most_common():
        lines.append(f"  {n:>3}  {r1}")
    lines.append("\n## full list (driving mi)")
    for dm, a, b in true_gaps:
        lines.append(f"  {dm:>3}mi  {names[a]},{cities[a]['state']} <-> {names[b]},{cities[b]['state']}  [{a} :: {b}]  ({region[a]}/{region[b]})")
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines[:40]))
    print(f"\n... wrote {len(true_gaps)} true gaps to gap_true.txt")

if __name__ == "__main__":
    main()
