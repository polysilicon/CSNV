#!/usr/bin/env python3
"""Extraction new-player flow, from the server's own logs (run on the host; player data stays there).

    python3 extraction_flow.py /AMPStorage/.ampdata/instances/Extraction01/Minecraft/logs [--since YYYY-MM-DD] [--json]

Reads the "[ez-flow]" lines the mod writes (1.6.0+), in latest.log and the rotated *.log.gz files:
    join <name> first=<bool>
    milestone <name> <trader|helipad|bunker> first=<bool> since_first_join=<s> since_join=<s>
    miss <name> <what> at <x y z> eye-dist <d> nearest <target> <d>
and reports, for players whose first join is in the logs:
  - how long new players take from their first join to their first trader, the helipad (deploy) and their bunker
    (median, 75th percentile, slowest) and how many never got there;
  - the clicks in camp that did nothing, grouped by the nearest real target and by what was clicked, with how far
    from the eyes they were (a miss 3+ blocks out is reach; a close one is aim or a dead spot).
Player names are printed only in counts by default; --names lists them (for the operator, not for sharing).
"""
import gzip, json, os, re, statistics, sys
from collections import Counter, defaultdict

LINE = re.compile(r"\[ez-flow\] (join|milestone|miss) (\S+) ?(.*)$")
STAGES = ("trader", "helipad", "bunker")


def logs(folder, since):
    files = []
    for f in os.listdir(folder):
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(\d+)\.log\.gz$", f)
        if m and (not since or m.group(1) >= since): files.append((m.group(1), int(m.group(2)), f))
    files.sort()
    for _, _, f in files:
        with gzip.open(os.path.join(folder, f), "rt", encoding="utf-8", errors="replace") as h: yield from h
    latest = os.path.join(folder, "latest.log")
    if os.path.exists(latest):
        with open(latest, encoding="utf-8", errors="replace") as h: yield from h


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))] if v else None


def fmt(s):
    return "-" if s is None else (f"{s}s" if s < 120 else f"{s // 60}m{s % 60:02d}s")


def main():
    a = sys.argv[1:]
    folder = a[0] if a and not a[0].startswith("--") else "logs"
    since = a[a.index("--since") + 1] if "--since" in a else None
    new, reached, misses, miss_rows = set(), defaultdict(dict), Counter(), []
    for line in logs(folder, since):
        m = LINE.search(line)
        if not m: continue
        kind, who, rest = m.groups()
        if kind == "join" and "first=true" in rest: new.add(who)
        elif kind == "milestone":
            p = rest.split()
            stage = p[0]; kv = dict(x.split("=", 1) for x in p[1:] if "=" in x)
            if kv.get("first") == "true": reached[who][stage] = int(kv.get("since_first_join", 0))
        elif kind == "miss":
            mm = re.search(r"^(\S+?)(?:\[.*?\])? at (.+?) eye-dist ([\d.]+) nearest (.+) ([\d.]+)$", rest)
            if mm:
                what, at, eye, target, dist = mm.groups()
                misses[(target, what)] += 1
                miss_rows.append({"who": who, "what": what, "at": at, "eye": float(eye), "nearest": target, "dist": float(dist)})
    out = {"new_players": len(new), "stages": {}, "misses": []}
    for st in STAGES:
        t = [reached[w][st] for w in new if st in reached[w]]
        out["stages"][st] = {"reached": len(t), "never": len(new) - len(t), "median_s": pct(t, 0.5), "p75_s": pct(t, 0.75), "max_s": max(t) if t else None}
    by_target = defaultdict(list)
    for r in miss_rows: by_target[r["nearest"]].append(r)
    for target, rows in sorted(by_target.items(), key=lambda kv: -len(kv[1])):
        out["misses"].append({"nearest": target, "count": len(rows), "players": len({r["who"] for r in rows}),
                              "what": Counter(r["what"] for r in rows).most_common(4),
                              "far_from_eye_3plus": sum(r["eye"] >= 3.0 for r in rows), "median_target_dist": statistics.median(r["dist"] for r in rows)})
    if "--json" in a: print(json.dumps(out, indent=1)); return
    print(f"New players (first join in these logs): {out['new_players']}")
    print(f"{'stage':8s} {'reached':>8s} {'never':>6s} {'median':>8s} {'p75':>8s} {'slowest':>8s}")
    for st, v in out["stages"].items():
        print(f"{st:8s} {v['reached']:>8d} {v['never']:>6d} {fmt(v['median_s']):>8s} {fmt(v['p75_s']):>8s} {fmt(v['max_s']):>8s}")
    print(f"\nClicks in camp that did nothing: {len(miss_rows)}")
    for r in out["misses"]:
        print(f"  near {r['nearest']}: {r['count']} by {r['players']} player(s); clicked {r['what']}; {r['far_from_eye_3plus']} from 3+ blocks; median {r['median_target_dist']:.1f} from the target")
    if "--names" in a:
        for w in sorted(new): print(" ", w, {st: fmt(reached[w].get(st)) for st in STAGES})


if __name__ == "__main__":
    main()
