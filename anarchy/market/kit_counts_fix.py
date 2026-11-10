# Restores stack sizes in the market kit shulkers (spawn_shops.mcfunction) from the original chests in the old
# market world (crispy:themarket). The 26.2 conversion had set every item inside every kit shulker to count 1.
# Inputs: spawn_shops.mcfunction and kits.json (slot,id,count per original shulker); writes spawn_shops.fixed.mcfunction.
# The letter heads also got their names and skins back (separate step, same source). Live since 2026-11-10.
import re, json, sys
s = open('spawn_shops.mcfunction').read()
kits = json.load(open('kits.json'))
FULL = {"Crying Obsidian Shulker", "Quartz Shard Shulker"}   # no original in the old market: full stacks
out, pos, report = [], 0, []
pat = re.compile(r'sell:\{id:"(minecraft:[a-z_]*shulker_box)",count:1,components:\{"minecraft:custom_name":\{text:"([^"]*)"')
for m in pat.finditer(s):
    sid, name = m.groups()
    start = s.index('"minecraft:container":[', m.end())
    end = s.index(']}},maxUses', start)
    cont = s[start:end]
    cur = re.findall(r'\{slot:(\d+),item:\{id:"([^"]+)",count:(\d+)', cont)
    cands = kits.get(f"{name}|{sid}", [])
    best = None
    for c in cands:   # pick the original whose slot ids match best
        ids = {e[0]: e[1] for e in c}
        score = sum(ids.get(int(sl)) == i for sl, i, _ in cur)
        if best is None or score > best[0]: best = (score, c)
    if best:
        ids = {e[0]: e[1] for e in best[1]}; cnt = {e[0]: e[2] for e in best[1]}
        pool = {}
        for e in best[1]:
            if ids.get(e[0]) is not None: pool.setdefault(e[1], []).append(e[2])
        want, mism = {}, []
        for sl, i, _ in cur:   # same slot + same item: take its count; otherwise any original count for that item
            sl = int(sl)
            if ids.get(sl) == i: want[sl] = cnt[sl]
        for sl, i, _ in cur:
            sl = int(sl)
            if sl in want: continue
            used = [want[int(x)] for x, j, _ in cur if j == i and int(x) in want]
            left = list(pool.get(i, []))
            for u in used:
                if u in left: left.remove(u)
            want[sl] = left[0] if left else (pool.get(i) or [1])[0]
            mism.append((sl, i, want[sl]))
    elif name in FULL:
        want = {int(sl): 64 for sl, _, _ in cur}; mism = []
    else:
        report.append(f"{name}: NO SOURCE, left alone"); continue
    def sub(mm):
        sl = int(mm.group(1)); return '{slot:%d,item:{id:"%s",count:%d' % (sl, mm.group(2), want.get(sl, 1))
    new = re.sub(r'\{slot:(\d+),item:\{id:"([^"]+)",count:\d+', sub, cont)
    out.append(s[pos:start]); out.append(new); pos = end
    tot = sum(want.get(int(sl), 1) for sl, _, _ in cur)
    report.append(f"{name:36} items {len(cur):2}  total {tot:5}  {'from old market' if best else 'full stacks'}  id mismatches: {mism or 'none'}")
out.append(s[pos:])
open('spawn_shops.fixed.mcfunction', 'w').write(''.join(out))
print('\n'.join(report))
