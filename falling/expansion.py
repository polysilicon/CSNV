"""Skyblock expansion (imported by skyblock.py): pets, resource zones and their warps. The mod does the rest
(Bazaar.java, Upgrades.java, Pets.java, Zones.java); this file builds the zones and puts the pet and zone settings
into storage crispy_skyblock:eco cfg (pets, zones), which the mod reads.

Resource zones are shared areas off the hub where blocks regenerate (the mod turns a mined block into bedrock and
puts it back after `secs`) and hostile mobs roam while anyone is there. Only the listed blocks can be mined; nothing
can be placed. /warp or the Warps NPC in the hub takes you there.
"""
import math
import random

# ------------------------------------------------------------------ pets
# key, name, skill (the XP it boosts), price (None = only from End bosses), head texture (/heads animals), stat line
# head textures (from the Head Index "animals" category) are in pet_heads.json
PETS = [
    ("pig", "Pig", "FARMING", 2500, "+speed while farming"),
    ("silverfish", "Silverfish", "MINING", 5000, "+mining speed"),
    ("fox", "Fox", "FORAGING", 5000, "+speed"),
    ("wolf", "Wolf", "COMBAT", 8000, "+damage"),
    ("squid", "Squid", "FISHING", 5000, "+luck"),
    ("phoenix", "Phoenix", "ALL", None, "+2 hearts · boosts every skill"),
]
PHOENIX_CHANCE = 3    # % per island member per End boss kill

# ------------------------------------------------------------------ zones
MINES = (-260, 90, -360)     # rim of the pit at y 90
WOODS = (260, 100, -360)
STONES = ["stone", "cobblestone", "andesite", "diorite", "granite", "tuff", "deepslate", "cobbled_deepslate"]
ORES = ["coal_ore", "iron_ore", "copper_ore", "gold_ore", "lapis_ore", "redstone_ore", "diamond_ore", "emerald_ore"]
LOGS = ["oak_log", "birch_log", "spruce_log", "dark_oak_log", "cherry_log"]
ZONES = [
    # key, name, centre, box half-size (x/z), y range, minable blocks, seconds to regrow, mobs, warp (x, y, z, yaw)
    ("mines", "The Deep Mines", MINES, 40, (MINES[1] - 34, MINES[1] + 12), STONES + ORES + [f"deepslate_{o}" for o in ORES if o != "emerald_ore"] + ["deepslate_emerald_ore"],
     45, ["zombie", "skeleton", "cave_spider", "silverfish", "husk"], (MINES[0] + 0.5, MINES[1] + 1, MINES[2] - 30.5, 0)),
    ("woods", "Whispering Woods", WOODS, 38, (WOODS[1] - 16, WOODS[1] + 20), LOGS,
     30, ["spider", "zombie", "witch", "skeleton"], (WOODS[0] + 0.5, WOODS[1] + 1, WOODS[2] - 27.5, 0)),
]
ZONE_CAP = 8          # mobs per zone at once (+2 per player there)


def build(NS, fn, js, txt, snbt, Build):
    """Build: skyblock.py's relative-coordinate builder."""
    import json, os
    heads = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pet_heads.json")))
    cfg = {
        "pets": [{"key": k, "name": n, "skill": s, "price": p or 0, "shop": p is not None, "stat": st, "tex": heads[k]["value"]}
                 for k, n, s, p, st in PETS],
        "zones": [{"key": k, "name": n, "x1": c[0] - h, "z1": c[2] - h, "x2": c[0] + h, "z2": c[2] + h, "y1": y[0], "y2": y[1],
                   "allow": [f"minecraft:{b}" for b in allow], "secs": secs, "warp": list(w)}
                  for k, n, c, h, y, allow, secs, mobs, w in ZONES],
    }
    box = lambda z: f"x={z[2][0] - z[3]},y={z[4][0]},z={z[2][2] - z[3]},dx={2 * z[3]},dy={z[4][1] - z[4][0]},dz={2 * z[3]}"

    # ---- the Deep Mines: a solid floating rock island riddled with caves. A cave mouth by the arrival platform leads down
    # winding tunnels through four chambers to the deepest one ~26 blocks down; side tunnels branch off, two sinkholes
    # let daylight in, and ores line the cave walls, richer the deeper you go.
    rnd = random.Random(77)
    cx, cy, cz = MINES
    R, DEPTH = 36, 32                              # island radius; how far its underside hangs below the top (y 90)
    def h3(x, y, z, seed):                          # a smooth 3D value noise in [0, 1)
        def hv(i, j, k): return (math.sin(i * 127.1 + j * 311.7 + k * 74.7 + seed * 19.3) * 43758.5453) % 1.0
        ix, iy, iz = math.floor(x), math.floor(y), math.floor(z)
        fx, fy, fz = x - ix, y - iy, z - iz
        fx, fy, fz = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), fz * fz * (3 - 2 * fz)
        def lerp(a_, b_, t_): return a_ + (b_ - a_) * t_
        c00 = lerp(hv(ix, iy, iz), hv(ix + 1, iy, iz), fx); c10 = lerp(hv(ix, iy + 1, iz), hv(ix + 1, iy + 1, iz), fx)
        c01 = lerp(hv(ix, iy, iz + 1), hv(ix + 1, iy, iz + 1), fx); c11 = lerp(hv(ix, iy + 1, iz + 1), hv(ix + 1, iy + 1, iz + 1), fx)
        return lerp(lerp(c00, c10, fy), lerp(c01, c11, fy), fz)
    # the island: a rough rocky top with a few mounds (kept flat round the arrival platform), a rounded underside
    solid = {}
    for x in range(-R - 2, R + 3):
        for z in range(-R - 2, R + 3):
            dist = math.hypot(x, z)
            edge = R + 3 * (h3(x * 0.08, 0, z * 0.08, 1) - 0.5)
            if dist > edge: continue
            k = dist / edge
            bottom = max(-DEPTH - 1, -round(DEPTH * (1 - k ** 2) ** 0.55 + 3 * h3(x * 0.15, 5, z * 0.15, 2)))   # stays inside the zone (y 56+)
            mound = 0 if math.hypot(x, z + 30) < 9 or k > 0.85 else round(4 * max(0.0, h3(x * 0.09, 9, z * 0.09, 3) - 0.45) / 0.55)
            for y in range(bottom, mound + 1):
                solid[(x, y, z)] = True
    # the caves: tunnels from waypoint to waypoint, wiggling, carved as squashed spheres; chambers are big spheres
    air = set()
    def carve(px, py, pz, r, ry=None):
        ry = ry or r * 0.8
        for x in range(math.floor(px - r), math.ceil(px + r) + 1):
            for y in range(math.floor(py - ry), math.ceil(py + ry) + 1):
                for z in range(math.floor(pz - r), math.ceil(pz + r) + 1):
                    if ((x - px) / r) ** 2 + ((y - py) / ry) ** 2 + ((z - pz) / r) ** 2 <= 1 and (x, y, z) in solid: air.add((x, y, z))
    def tunnel(a_, b_, r0=2.2, wiggle=6):
        n = max(1, int(math.dist(a_, b_)))
        ox, oz = rnd.uniform(-wiggle, wiggle), rnd.uniform(-wiggle, wiggle)
        for i in range(n + 1):
            t_ = i / n
            bend = math.sin(t_ * math.pi)
            px = a_[0] + (b_[0] - a_[0]) * t_ + ox * bend
            py = a_[1] + (b_[1] - a_[1]) * t_
            pz = a_[2] + (b_[2] - a_[2]) * t_ + oz * bend
            carve(px, py, pz, r0 + 0.8 * h3(px * 0.2, py * 0.2, pz * 0.2, 4))
    mouth = (0, -1, -24)
    chambers = [(-8, -7, -10, 6.5), (12, -13, 2, 7), (-6, -19, 14, 6.5), (6, -25, -4, 7.5)]   # x, y, z, radius
    tunnel((0, 1, -27), mouth, 2.4, 0)                                   # the cave mouth, open to the sky
    prev = mouth
    for (hx, hy, hz, hr) in chambers:
        tunnel(prev, (hx, hy + 1, hz), 2.4)
        carve(hx, hy + hr * 0.45, hz, hr, hr * 0.6)
        prev = (hx, hy + 1, hz)
    for (hx, hy, hz, hr) in chambers:                                   # side tunnels that wander off and end
        for _ in range(2):
            a_ = rnd.uniform(0, 2 * math.pi)
            end = (hx + 16 * math.cos(a_), hy + rnd.uniform(-4, 3), hz + 16 * math.sin(a_))
            if math.hypot(end[0], end[2]) < R - 8 and end[1] > -DEPTH + 7: tunnel((hx, hy + 1, hz), end, 1.8, 4)
    tunnel((-8, -6, -10), (12, -12, 2), 1.9, 5)                         # loops between chambers
    tunnel((-6, -18, 14), (6, -24, -4), 1.9, 5)
    for sx_, sz_, deep in ((14, -6, -12), (-14, 10, -18)):              # sinkholes from the surface
        for y in range(4, deep - 1, -1): carve(sx_ + 1.5 * math.sin(y * 0.4), y, sz_, 2.3)
    for v in air: solid.pop(v, None)
    # rock: stone with patches of andesite, tuff, diorite and granite near the top, deepslate lower down; ores on
    # the cave walls (and a few hidden in the rock), richer deeper; gravel on some cave floors
    def ore_for(d):
        if d < 8: return rnd.choices(["coal_ore", "iron_ore", "copper_ore"], [50, 30, 20])[0]
        if d < 16: return rnd.choices(["iron_ore", "coal_ore", "gold_ore", "lapis_ore", "redstone_ore"], [35, 20, 15, 15, 15])[0]
        return "deepslate_" + rnd.choices(["iron_ore", "gold_ore", "lapis_ore", "redstone_ore", "diamond_ore", "emerald_ore"], [25, 20, 15, 20, 15, 5])[0]
    NB = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
    block = {}
    for (x, y, z) in solid:
        d = -y
        if d >= 16 + round(3 * h3(x * 0.1, 0, z * 0.1, 6)): base = "deepslate"
        else:
            n = h3(x * 0.12, y * 0.12, z * 0.12, 5)
            base = "andesite" if n < 0.22 else "tuff" if n > 0.8 else "diorite" if 0.48 < n < 0.52 else "granite" if 0.6 < n < 0.64 else "stone"
        cave_wall = any((x + a_, y + b_, z + c_) in air for a_, b_, c_ in NB)
        if y >= 0 and (x, y + 1, z) not in solid and (x, y + 1, z) not in air:
            base = "gravel" if h3(x * 0.2, 0, z * 0.2, 7) > 0.75 else "cobblestone" if h3(x * 0.2, 1, z * 0.2, 8) > 0.7 else "stone"
        elif cave_wall and rnd.random() < 0.16: base = ore_for(d)
        elif cave_wall and (x, y + 1, z) in air and rnd.random() < 0.06 and d > 2: base = "gravel"
        elif rnd.random() < 0.025: base = ore_for(d)
        block[(x, y, z)] = base
    # lanterns on some cave floors (they can't be mined), and the mob spawn spots: cave floors, spread out by depth
    floors = sorted(v for v in air if (v[0], v[1] - 1, v[2]) in block and (v[0], v[1] + 1, v[2]) in air and v[1] < -2)
    lanterns, spawns = [], []
    for v in rnd.sample(floors, len(floors)):
        if all(math.dist(v, l_) > 9 for l_ in lanterns) and len(lanterns) < 40: lanterns.append(v)
    for band in ((-8, -2), (-14, -8), (-20, -14), (-30, -20)):
        cand = [v for v in floors if band[0] <= v[1] < band[1] and v not in lanterns]
        for v in rnd.sample(cand, len(cand)):
            if all(math.dist(v, s_) > 6 for s_ in spawns) and sum(1 for s_ in spawns if band[0] <= s_[1] < band[1]) < 4: spawns.append(v)
    cmds = [f"kill @e[type=minecraft:text_display,tag=cs_zonel,x={cx - R - 6},y={cy - DEPTH - 6},z={cz - R - 6},dx={2 * R + 12},dy={DEPTH + 30},dz={2 * R + 12}]"]
    cmds += [f"fill {cx - R - 4} {y} {cz - R - 4} {cx + R + 4} {y} {cz + R + 4} minecraft:air" for y in range(cy - DEPTH - 6, cy + 14)]
    rows = {}
    for (x, y, z), b_ in block.items(): rows.setdefault((y, z), []).append((x, b_))
    for (y, z), xs in rows.items():   # run-length fills along x
        xs.sort()
        start, prev, blk = xs[0][0], xs[0][0], xs[0][1]
        for x, b_ in xs[1:] + [(None, None)]:
            if x is not None and x == prev + 1 and b_ == blk: prev = x; continue
            cmds.append(f"fill {cx + start} {cy + y} {cz + z} {cx + prev} {cy + y} {cz + z} minecraft:{blk}" if start != prev
                        else f"setblock {cx + start} {cy + y} {cz + z} minecraft:{blk}")
            if x is not None: start, prev, blk = x, x, b_
    cmds += [f"setblock {cx + x} {cy + y} {cz + z} minecraft:lantern" for x, y, z in lanterns]
    mine_spawns = [(x, y, z) for x, y, z in spawns]
    wx, wy, wz = cx, cy, cz - 30   # the arrival platform on the rim
    cmds += [f"fill {wx - 2} {wy} {wz - 2} {wx + 2} {wy} {wz + 2} minecraft:polished_andesite",
             f"summon minecraft:text_display {wx + 0.5} {wy + 3} {wz + 0.5} {{Tags:[\"{NS}\",\"cs_zonel\"],billboard:\"center\",text:"
             + snbt({"text": "The Deep Mines", "color": "gray", "bold": True, "extra": [txt("\nOres grow back · mobs lurk below · /warp hub", "dark_gray", bold=False)]}) + "}"]
    # the portal back to the hub, just behind the arrival platform
    cmds += [f"fill {wx - 3} {wy} {wz - 5} {wx + 3} {wy} {wz - 2} minecraft:polished_andesite",
             f"fill {wx - 3} {wy - 1} {wz - 5} {wx + 3} {wy - 1} {wz - 2} minecraft:cobbled_deepslate",
             f"fill {wx - 3} {wy + 1} {wz - 5} {wx + 3} {wy + 8} {wz - 2} minecraft:air",
             f"execute positioned {wx} {wy} {wz - 3} run function {NS}:portal/style_mines",
             f"summon minecraft:text_display {wx + 0.5} {wy + 7.2} {wz - 2.5} {{Tags:[\"{NS}\",\"cs_zonel\"],billboard:\"center\",text:"
             + snbt({"text": "Hub", "color": "gold", "bold": True, "extra": [txt("\nWalk through to go back", "gray", bold=False)]}) + "}"]
    fn("zones/build_mines", "\n".join(cmds))

    # ---- Whispering Woods: a dense forest on gently rolling ground. Big dark oaks, tall spruces, birches and vine-hung
    # oaks packed close, an undergrowth of ferns, bushes, mushrooms and flowers, mossy fallen logs and boulders, and a
    # lantern-lit path from the arrival spot to a clearing with a stone circle round a campfire.
    b = Build(91)
    wr = b.rnd
    WR = 34
    def n2(x, z, seed, f=0.09):
        return (math.sin(x * f * 12.9898 + z * f * 78.233 + seed) * 0.5 + math.sin(x * f * 3.1 - z * f * 4.7 + seed * 2) * 0.5 + 1) / 2
    path = [(0, -27), (1, -21), (-2, -15), (1, -9), (0, -4)]
    def near_path(x, z, d):
        for (ax, az), (bx, bz) in zip(path, path[1:]):
            for i in range(11):
                px, pz = ax + (bx - ax) * i / 10, az + (bz - az) * i / 10
                if math.hypot(x - px, z - pz) <= d: return True
        return False
    top = {}
    for x in range(-WR - 1, WR + 2):
        for z in range(-WR - 1, WR + 2):
            dist = math.hypot(x, z)
            edge = WR + 2.5 * (n2(x, z, 1, 0.12) - 0.5)
            if dist > edge: continue
            k = dist / edge
            calm = math.hypot(x, z) < 7 or near_path(x, z, 2) or (abs(x) <= 4 and z < -22)
            hgt = 0 if calm or k > 0.9 else round(3 * n2(x, z, 2) * min(1, (0.9 - k) * 5))
            depth = round(4 + 14 * (1 - k ** 2) ** 0.6)
            top[(x, z)] = hgt
            b.fill(x, -depth, z, x, hgt - 3, z, "stone")
            b.fill(x, hgt - 2, z, x, hgt - 1, z, "dirt")
            g = n2(x, z, 3, 0.15)
            surf = "podzol" if g > 0.82 else "moss_block" if g < 0.14 else "coarse_dirt" if 0.5 < g < 0.53 else "rooted_dirt" if 0.62 < g < 0.64 else "grass_block"
            if near_path(x, z, 1.2) and not (abs(x) <= 2 and -29 <= z <= -25): surf = "dirt_path" if wr.random() < 0.7 else "coarse_dirt"
            b.set(x, hgt, z, surf)
    taken = set()                                   # columns with something on them
    def free(x, z, r=0):
        return all((x + a_, z + c_) in top and (x + a_, z + c_) not in taken for a_ in range(-r, r + 1) for c_ in range(-r, r + 1))
    def mark(x, z, r=0):
        for a_ in range(-r, r + 1):
            for c_ in range(-r, r + 1): taken.add((x + a_, z + c_))
    # the clearing: a ring of mossy standing stones round a campfire, mossy cobble paving
    for (x, z) in list(top):
        if math.hypot(x, z) <= 2.5: b.set(x, top[(x, z)], z, "mossy_cobblestone" if wr.random() < 0.5 else "cobblestone")
    b.set(0, 1, 0, "campfire[lit=true]")
    for i in range(7):
        a_ = i / 7 * 2 * math.pi
        x, z = round(5.5 * math.cos(a_)), round(5.5 * math.sin(a_))
        if (x, z) in top:
            hh = 2 + (i % 2)
            b.fill(x, top[(x, z)] + 1, z, x, top[(x, z)] + hh, z, "mossy_stone_bricks" if i % 3 else "mossy_cobblestone")
            b.set(x, top[(x, z)] + hh + 1, z, "moss_carpet")
    for (x, z) in list(top):
        if math.hypot(x, z) < 7: taken.add((x, z))
    for (x, z) in list(top):
        if near_path(x, z, 2) or (abs(x) <= 6 and z <= -22): taken.add((x, z))
    # lanterns on posts along the path
    for i, (px, pz) in enumerate(path[:-1]):
        lx, lz = px + (2 if i % 2 else -2), pz
        if (lx, lz) in top:
            b.fill(lx, top[(lx, lz)] + 1, lz, lx, top[(lx, lz)] + 2, lz, "spruce_fence")
            b.set(lx, top[(lx, lz)] + 3, lz, "lantern")
    # trees
    def leaf(x, y, z, L, chance=1.0):
        if wr.random() < chance: b.c.append(f"fill ~{x} ~{y} ~{z} ~{x} ~{y} ~{z} minecraft:{L} replace minecraft:air")
    def blob_leaves(x, y, z, r, L, holes=0.12):
        for a_ in range(-r, r + 1):
            for c_ in range(-r, r + 1):
                if a_ * a_ + c_ * c_ <= r * r + 1 and wr.random() > holes: leaf(x + a_, y, z + c_, L)
    def oak(x, z, base, log="oak_log", leaves="oak_leaves", vines=False):
        h = wr.randint(5, 7)
        L = f"{leaves}[persistent=true]"
        for dy, r in ((h - 3, 2), (h - 2, 2), (h - 1, 1), (h, 1)): blob_leaves(x, base + dy, z, r, L, 0.15 if r == 2 else 0.05)
        b.fill(x, base + 1, z, x, base + h - 1, z, log)
        if vines:
            for vx, vz, f in ((x - 3, z, "east"), (x + 3, z, "west"), (x, z - 3, "south"), (x, z + 3, "north")):
                if wr.random() < 0.7: b.c.append(f"fill ~{vx} ~{base + h - 5} ~{vz} ~{vx} ~{base + h - 3} ~{vz} minecraft:vine[{f}=true] replace minecraft:air")
    def birch(x, z, base):
        h = wr.randint(7, 9)
        L = "birch_leaves[persistent=true]"
        for dy, r in ((h - 3, 1), (h - 2, 2), (h - 1, 1), (h, 1), (h + 1, 0)): blob_leaves(x, base + dy, z, r, L, 0.1)
        b.fill(x, base + 1, z, x, base + h - 1, z, "birch_log")
    def spruce(x, z, base):
        h = wr.randint(10, 13)
        L = "spruce_leaves[persistent=true]"
        for dy in range(4, h + 1):
            r = 2 if (h - dy) % 3 == 2 and dy < h - 1 else 1
            if dy >= h - 1: r = 0 if dy == h else 1
            blob_leaves(x, base + dy, z, r, L, 0.05)
        leaf(x, base + h + 1, z, L)
        b.fill(x, base + 1, z, x, base + h, z, "spruce_log")
    def dark_oak(x, z, base):
        h = wr.randint(6, 8)
        L = "dark_oak_leaves[persistent=true]"
        for dy, r in ((h - 2, 3), (h - 1, 3), (h, 2), (h + 1, 1)): blob_leaves(x, base + dy, z, r, L, 0.1)
        for dy, r in ((h - 2, 3), (h - 1, 3), (h, 2), (h + 1, 1)): blob_leaves(x + 1, base + dy, z + 1, r, L, 0.25)
        b.fill(x, base + 1, z, x + 1, base + h, z + 1, "dark_oak_log")
        for rx, rz in ((-1, 0), (2, 1), (0, 2), (1, -1)):                 # root flares
            if wr.random() < 0.5: b.set(x + rx, base + 1, z + rz, "dark_oak_log")
        for _ in range(2):                                                # mushrooms in its shade
            mx, mz = x + wr.choice((-2, 3)), z + wr.randint(-1, 2)
            if (mx, mz) in top and (mx, mz) not in taken:
                b.set(mx, top[(mx, mz)] + 1, mz, wr.choice(["red_mushroom", "brown_mushroom"])); taken.add((mx, mz))
    cells = sorted(c_ for c_ in top if c_ not in taken and math.hypot(*c_) < WR - 3)
    wr.shuffle(cells)
    trees = []
    for (x, z) in cells:
        if any(math.hypot(x - tx, z - tz) < 3.6 for tx, tz in trees): continue
        if not free(x, z) or not free(x + 1, z + 1): continue
        trees.append((x, z))
    spots = []
    for i, (x, z) in enumerate(trees):
        base = top[(x, z)]
        kind = i % 10
        if kind in (0, 5): dark_oak(x, z, base); mark(x, z, 1); mark(x + 1, z + 1, 1)
        elif kind in (1, 6, 8): spruce(x, z, base); mark(x, z, 1)
        elif kind in (2, 7): birch(x, z, base); mark(x, z)
        elif kind == 9: oak(x, z, base, "cherry_log", "cherry_leaves"); mark(x, z)
        else: oak(x, z, base, vines=True); mark(x, z)
        spots.append((x, z))
    # fallen mossy logs and boulders
    placed = 0
    for (x, z) in cells:
        if placed >= 7: break
        axis = wr.choice("xz"); ln = wr.randint(4, 6)
        run = [(x + i, z) if axis == "x" else (x, z + i) for i in range(ln)]
        if not all(c_ in top and c_ not in taken and top[c_] == top[(x, z)] for c_ in run): continue
        log = wr.choice(["oak_log", "spruce_log", "birch_log", "dark_oak_log"])
        for (ax, az) in run:
            b.set(ax, top[(ax, az)] + 1, az, f"{log}[axis={axis}]"); taken.add((ax, az))
            if wr.random() < 0.6: b.set(ax, top[(ax, az)] + 2, az, "moss_carpet")
        placed += 1
    placed = 0
    for (x, z) in cells[::-1]:
        if placed >= 9: break
        if not free(x, z, 1): continue
        t_ = top[(x, z)]
        b.fill(x, t_ + 1, z, x + 1, t_ + 1, z + 1, "mossy_cobblestone")
        b.set(x + wr.randint(0, 1), t_ + 2, z + wr.randint(0, 1), wr.choice(["mossy_cobblestone", "cobblestone"]))
        mark(x, z, 1); placed += 1
    # undergrowth
    plants = (["short_grass"] * 8 + ["fern"] * 6 + ["tall_grass", "large_fern"] * 3 + ["lily_of_the_valley", "red_mushroom", "brown_mushroom",
              "oxeye_daisy", "cornflower", "bush"] + ["leaf_bush"] * 4)
    for (x, z), t_ in top.items():
        if (x, z) in taken or wr.random() > 0.42: continue
        p_ = wr.choice(plants)
        if p_ in ("tall_grass", "large_fern"):
            b.set(x, t_ + 1, z, f"{p_}[half=lower]"); b.set(x, t_ + 2, z, f"{p_}[half=upper]")
        elif p_ == "leaf_bush":
            b.set(x, t_ + 1, z, wr.choice(["oak_leaves[persistent=true]", "azalea_leaves[persistent=true]", "flowering_azalea_leaves[persistent=true]"]))
        elif p_ == "bush":
            b.set(x, t_ + 1, z, "azalea")
        else:
            b.set(x, t_ + 1, z, p_)
        if wr.random() < 0.15 and t_ >= 0: b.set(x, t_ + 1, z, "moss_carpet") if p_ == "short_grass" else None
    # the arrival spot
    b.fill(-2, 0, -29, 2, 0, -25, "moss_block")
    wood_cmds = [f"kill @e[type=minecraft:text_display,tag=cs_zonel,x={WOODS[0] - 40},y={WOODS[1] - 20},z={WOODS[2] - 42},dx=80,dy=45,dz=84]"]
    wood_cmds += [f"fill {WOODS[0] - WR - 3} {y} {WOODS[2] - WR - 3} {WOODS[0] + WR + 3} {y} {WOODS[2] + WR + 3} minecraft:air" for y in range(WOODS[1] - 20, WOODS[1] + 20)]
    wood_cmds += [f"execute positioned {WOODS[0]} {WOODS[1]} {WOODS[2]} run function {NS}:zones/woods_island",
                 f"summon minecraft:text_display {WOODS[0] + 0.5} {WOODS[1] + 3} {WOODS[2] - 26.5} {{Tags:[\"{NS}\",\"cs_zonel\"],billboard:\"center\",text:"
                 + snbt({"text": "Whispering Woods", "color": "dark_green", "bold": True, "extra": [txt("\nLogs grow back · beware the spiders · /warp hub", "dark_gray", bold=False)]}) + "}"]
    wood_cmds += [f"fill {WOODS[0] - 3} {WOODS[1]} {WOODS[2] - 33} {WOODS[0] + 3} {WOODS[1]} {WOODS[2] - 29} minecraft:moss_block",
                  f"fill {WOODS[0] - 3} {WOODS[1] - 1} {WOODS[2] - 33} {WOODS[0] + 3} {WOODS[1] - 1} {WOODS[2] - 29} minecraft:dirt",
                  f"fill {WOODS[0] - 3} {WOODS[1] + 1} {WOODS[2] - 33} {WOODS[0] + 3} {WOODS[1] + 9} {WOODS[2] - 30} minecraft:air",
                  f"execute positioned {WOODS[0]} {WOODS[1]} {WOODS[2] - 31} run function {NS}:portal/style_woods",
                  f"summon minecraft:text_display {WOODS[0] + 0.5} {WOODS[1] + 8.4} {WOODS[2] - 30.5} {{Tags:[\"{NS}\",\"cs_zonel\"],billboard:\"center\",text:"
                  + snbt({"text": "Hub", "color": "gold", "bold": True, "extra": [txt("\nWalk through to go back", "gray", bold=False)]}) + "}"]
    fn("zones/woods_island", "\n".join(b.c))
    fn("zones/build_woods", "\n".join(wood_cmds))
    gspots = [c_ for c_ in cells if c_ not in taken and math.hypot(*c_) > 8]
    woods_spawns = [(x, top[(x, z)] + 1, z) for x, z in gspots[:: max(1, len(gspots) // 16)]][:16]
    fn("zones/portals_v2", "\n".join(cmds[-5:] + wood_cmds[-5:]))
    fn("zones/build_all", "\n".join([
        "kill @e[type=minecraft:text_display,tag=cs_zonel]",
        *[f"forceload add {c[0] - h - 2} {c[2] - h - 2} {c[0] + h + 2} {c[2] + h + 2}" for k, n, c, h, *_ in ZONES],
        f"function {NS}:zones/build_mines", f"function {NS}:zones/build_woods",
        *[f"forceload remove {c[0] - h - 2} {c[2] - h - 2} {c[0] + h + 2} {c[2] + h + 2}" for k, n, c, h, *_ in ZONES],
        "scoreboard players set #zonesv cs_cfg 1"]))

    # ---- mobs: while someone is in a zone, keep up to ZONE_CAP (+2 per player) hostiles there; none when it's empty
    sec = []
    for z in ZONES:
        key, name, c, h, y, allow, secs, mobs, w = z
        spawns = mine_spawns if key == "mines" else woods_spawns
        rp = (c[0], c[1], c[2] - 33) if key == "mines" else (c[0], c[1], c[2] - 31)
        sec += [f"execute if entity @a[{box(z)}] positioned {rp[0]} {rp[1]} {rp[2]} run function {NS}:portal/fx_{key}"]
        sec += [f"execute unless entity @a[{box(z)}] run kill @e[tag=cs_zone_{key}]",
                f"execute if entity @a[{box(z)}] run function {NS}:zones/{key}/tick"]
        roll = [f"execute store result score #n cs_tmp if entity @e[tag=cs_zone_{key}]",
                f"execute store result score #pl cs_tmp if entity @a[{box(z)}]",
                f"scoreboard players operation #pl cs_tmp *= #2c cs_tmp", f"scoreboard players add #pl cs_tmp {ZONE_CAP}",
                "execute if score #n cs_tmp >= #pl cs_tmp run return 0",
                "execute store result score #r cs_tmp run random value 1..3", "execute unless score #r cs_tmp matches 1 run return 0",
                f"execute store result score #r cs_tmp run random value 1..{len(spawns)}"]
        for i, (sx, sy, sz) in enumerate(spawns, 1):
            roll.append(f"execute if score #r cs_tmp matches {i} positioned {c[0] + sx + 0.5} {c[1] + sy} {c[2] + sz + 0.5} run function {NS}:zones/{key}/mob")
        fn(f"zones/{key}/tick", "\n".join(roll))
        mob = [f"execute store result score #m cs_tmp run random value 1..{len(mobs)}"]
        for i, m in enumerate(mobs, 1):
            mob.append(f"execute if score #m cs_tmp matches {i} run summon minecraft:{m} ~ ~ ~ {{Tags:[\"cs_zone_mob\",\"cs_zone_{key}\"],PersistenceRequired:1b}}")
        mob.append("particle minecraft:large_smoke ~ ~0.5 ~ 0.3 0.5 0.3 0.01 10")
        fn(f"zones/{key}/mob", "\n".join(mob))
    fn("zones/second", "\n".join(sec))
    fn("zones/tp", "$execute in minecraft:overworld run tp @s $(x) $(y) $(z) $(yaw) 0")

    # ---- the Phoenix: a rare drop from End bosses (boss/killed2 runs boss/phoenix_<realm>)
    fn("boss/phoenix_e", f"$execute as @a[scores={{cs_plot=$(id)}}] run function {NS}:boss/phoenix_roll")
    fn("boss/phoenix_n", "return 0")
    fn("boss/phoenix_roll", f"execute store result score #r cs_tmp run random value 1..100\nexecute if score #r cs_tmp matches ..{PHOENIX_CHANCE} run pets grant @s phoenix")

    in_zone = " ".join(f"unless entity @s[{box(z)}]" for z in ZONES)
    return {"cfg": cfg, "in_zone": in_zone}
