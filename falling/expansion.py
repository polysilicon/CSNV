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
RIFT = (0, 120, -640)        # the Sky Lord's Rift: only players wearing [Sky Lord] (lobby tag r_skylord) get in
RIFT_GATE = "r_skylord"
RIFT_RES = ["amethyst_block", "amethyst_cluster", "crying_obsidian", "gilded_blackstone", "nether_gold_ore", "nether_quartz_ore", "ancient_debris", "obsidian"]
RIFT_BIOME = "soul_sand_valley"   # no rain (it put out the blazes), soul particles and a blue haze
STONES = ["stone", "cobblestone", "andesite", "diorite", "granite", "tuff", "deepslate", "cobbled_deepslate"]
ORES = ["coal_ore", "iron_ore", "copper_ore", "gold_ore", "lapis_ore", "redstone_ore", "diamond_ore", "emerald_ore"]
LOGS = ["oak_log", "birch_log", "spruce_log", "dark_oak_log", "cherry_log"]
ZONES = [
    # key, name, centre, box half-size (x/z), y range, minable blocks, seconds to regrow, mobs, warp (x, y, z, yaw)
    ("mines", "The Deep Mines", MINES, 40, (MINES[1] - 34, MINES[1] + 12), STONES + ORES + [f"deepslate_{o}" for o in ORES if o != "emerald_ore"] + ["deepslate_emerald_ore"],
     45, ["zombie", "skeleton", "silverfish", "husk"], (MINES[0] + 0.5, MINES[1] + 1, MINES[2] - 30.5, 0)),
    ("woods", "Whispering Woods", WOODS, 38, (WOODS[1] - 16, WOODS[1] + 20), LOGS,
     30, ["spider", "zombie", "witch", "skeleton"], (WOODS[0] + 0.5, WOODS[1] + 1, WOODS[2] - 27.5, 0)),
    ("rift", "Sky Lord's Rift", RIFT, 34, (RIFT[1] - 28, RIFT[1] + 22), RIFT_RES,
     # no piglins in the Rift: brutes fight wither skeletons and zombify in the overworld
     90, ["wither_skeleton", "pillager", "vindicator", "blaze", "wither_skeleton"], (RIFT[0] + 0.5, RIFT[1] + 1, RIFT[2] - 27.5, 0)),
]
ZONE_CAP = 8          # mobs per zone at once (+2 per player there)
SPAWN_EVERY = {"mines": 8, "woods": 3, "rift": 4}   # a new mob about every N seconds per zone (a 1-in-N roll each second) until the cap


def build(NS, fn, js, txt, snbt, Build):
    """Build: skyblock.py's relative-coordinate builder."""
    import json, os
    heads = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pet_heads.json")))
    cfg = {
        "pets": [{"key": k, "name": n, "skill": s, "price": p or 0, "shop": p is not None, "stat": st, "tex": heads[k]["value"]}
                 for k, n, s, p, st in PETS],
        "zones": [{"key": k, "name": n, "x1": c[0] - h, "z1": c[2] - h, "x2": c[0] + h, "z2": c[2] + h, "y1": y[0], "y2": y[1],
                   "allow": [f"minecraft:{b}" for b in allow], "secs": secs, "warp": list(w), "gate": RIFT_GATE if k == "rift" else ""}
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
        for rx, rz in ((-1, 0), (2, 1), (0, 2), (1, -1)):                 # root flares, on their own column's ground
            if wr.random() < 0.5 and (x + rx, z + rz) in top: b.set(x + rx, top[(x + rx, z + rz)] + 1, z + rz, "dark_oak_log")
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
        if kind in (0, 5):   # 2x2 trunk: stand it on the lowest of its four columns so no corner hangs in the air
            dark_oak(x, z, min(top[(x + a_, z + c_)] for a_ in (0, 1) for c_ in (0, 1))); mark(x, z, 1); mark(x + 1, z + 1, 1)
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
        for a_ in (0, 1):
            for c_ in (0, 1): b.fill(x + a_, top[(x + a_, z + c_)] + 1, z + c_, x + a_, t_ + 1, z + c_, "mossy_cobblestone")
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

    # ---- the Sky Lord's Rift: a dark floating island torn open by an amethyst geode. Rolling blackstone ground with soul
    # soil, crimson and amethyst areas; a ring of basalt pillars hung with chains and soul lanterns; a ruined temple, a
    # ruined portal and a fossil; small islets hovering overhead; vines and dripstone hanging under it. Outcrops of the
    # rare minable blocks grow back (RIFT_RES).
    rnd = random.Random(1717)
    RR = 32
    G = {}                                   # (x, y, z) -> block, relative to the island centre (surface y 0)
    def put(x, y, z, blk): G[(x, y, z)] = blk
    def hgt(x, z):                           # rolling ground, 0..3, flattened near the edge
        r = math.hypot(x, z)
        v = 1.3 * math.sin(x * 0.21) + 1.1 * math.cos(z * 0.17) + 0.8 * math.sin((x + z) * 0.11) + 1.2
        return max(0, min(3, int(round(v * min(1, (RR - r) / 6)))))
    H = {}
    for x in range(-RR - 1, RR + 2):
        for z in range(-RR - 1, RR + 2):
            r = math.hypot(x, z) + 0.6 * math.sin(math.atan2(z, x) * 5) + rnd.uniform(-0.4, 0.4)
            if r > RR: continue
            h = 0 if r < 11 or (abs(x) <= 3 and z < -24) else hgt(x, z)
            H[(x, z)] = h
            depth = int(17 * (1 - (r / RR) ** 1.7)) + rnd.randint(0, 2)
            for y in range(-depth, h + 1):
                if y == h:
                    a_ = math.degrees(math.atan2(z, x)) % 360
                    if 30 < a_ < 100 and r > 14: top = rnd.choice(["soul_soil", "soul_soil", "soul_sand", "blackstone"])          # soul valley
                    elif 170 < a_ < 240 and r > 14: top = rnd.choice(["crimson_nylium", "crimson_nylium", "blackstone", "netherrack"])  # crimson
                    elif r < 15: top = rnd.choice(["smooth_basalt", "calcite", "blackstone", "tuff"])
                    else: top = rnd.choice(["blackstone"] * 5 + ["polished_blackstone", "basalt[axis=y]", "gilded_blackstone", "tuff", "magma_block"])
                    put(x, y, z, top)
                elif y >= h - 2: put(x, y, z, "blackstone")
                else: put(x, y, z, rnd.choice(["blackstone", "basalt[axis=y]", "obsidian", "smooth_basalt", "blackstone", "crying_obsidian" if rnd.random() < 0.08 else "obsidian"]))
            if depth > 3 and rnd.random() < 0.07:   # hanging from the underside
                if rnd.random() < 0.5:
                    n = rnd.randint(2, 6)
                    for k in range(1, n): put(x, -depth - k, z, "weeping_vines_plant")
                    put(x, -depth - n, z, "weeping_vines")
                else:
                    put(x, -depth - 1, z, "pointed_dripstone[thickness=frustum,vertical_direction=down]")
                    put(x, -depth - 2, z, "pointed_dripstone[thickness=tip,vertical_direction=down]")
    def ground(x, z): return H.get((x, z), 0)
    # surface plants
    for (x, z), h in list(H.items()):
        t = G.get((x, h, z), "")
        if t == "crimson_nylium" and rnd.random() < 0.3: put(x, h + 1, z, rnd.choice(["crimson_roots", "crimson_roots", "crimson_fungus"]))
        elif t.startswith("soul_s") and rnd.random() < 0.05: put(x, h + 1, z, "soul_fire")
        elif t == "blackstone" and rnd.random() < 0.04: put(x, h + 1, z, "amethyst_cluster[facing=up]" if math.hypot(x, z) < 20 else "dead_bush")
    # the geode crater with a floating crystal spire
    for x in range(-11, 12):
        for z in range(-11, 12):
            r = math.hypot(x, z)
            if r > 10.5: continue
            floor = -4 + int(r / 3.5)
            for y in range(floor + 1, 4): G.pop((x, y, z), None)
            if r > 9.5: put(x, floor, z, "smooth_basalt"); put(x, floor + 1, z, "smooth_basalt")
            elif r > 8.5: put(x, floor, z, "calcite")
            else:
                put(x, floor, z, "budding_amethyst" if rnd.random() < 0.3 else "amethyst_block")
                if rnd.random() < 0.25: put(x, floor + 1, z, rnd.choice(["amethyst_cluster[facing=up]", "large_amethyst_bud[facing=up]", "medium_amethyst_bud[facing=up]"]))
    for y in range(4, 15):
        w = max(0, int((15 - y) / 4))
        for dx in range(-w, w + 1):
            for dz in range(-w, w + 1):
                if abs(dx) + abs(dz) <= w: put(dx, y, dz, "amethyst_block" if (y + dx + dz) % 5 else "purpur_block")
    put(0, 15, 0, "end_rod[facing=up]"); put(0, 3, 0, "end_rod[facing=up]")
    for i in range(6):   # shards orbiting the spire
        a_ = i * math.pi / 3; put(int(6 * math.cos(a_)), 8 + (i % 3), int(6 * math.sin(a_)), "amethyst_block")
    # basalt pillar ring with chains and soul lanterns
    for i in range(10):
        a_ = i * 2 * math.pi / 10 + 0.3; x, z = int(math.cos(a_) * 19), int(math.sin(a_) * 19)
        g = ground(x, z); h = rnd.randint(6, 11)
        for y in range(g + 1, g + h + 1): put(x, y, z, "polished_basalt[axis=y]")
        put(x, g + h + 1, z, "soul_soil"); put(x, g + h + 2, z, "soul_fire")
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            put(x + dx, g + h - 1, z + dz, "polished_blackstone_wall")
            if rnd.random() < 0.6:
                n = rnd.randint(2, 4)
                for k in range(n): put(x + dx, g + h - 2 - k, z + dz, "iron_chain[axis=y]")
                put(x + dx, g + h - 2 - n, z + dz, "soul_lantern[hanging=true]")
    # paths: from the arrival platform to the crater, and a ring road at the pillars
    for z in range(-26, -10):
        for x in range(-1, 2): put(x, ground(x, z), z, rnd.choice(["polished_blackstone_bricks", "polished_blackstone_bricks", "cracked_polished_blackstone_bricks"]))
        if z % 5 == 0:
            for x in (-2, 2): put(x, ground(x, z) + 1, z, "polished_blackstone_wall"); put(x, ground(x, z) + 2, z, "soul_lantern")
    for i in range(160):
        a_ = i * 2 * math.pi / 160; x, z = int(round(math.cos(a_) * 15.5)), int(round(math.sin(a_) * 15.5))
        put(x, ground(x, z), z, rnd.choice(["polished_blackstone_bricks", "cracked_polished_blackstone_bricks", "blackstone"]))
    # a ruined temple in the south-east
    tx, tz = 17, 13; g = max(ground(tx + dx, tz + dz) for dx in range(-5, 6) for dz in range(-5, 6))
    for dx in range(-5, 6):
        for dz in range(-5, 6):
            for y in range(ground(tx + dx, tz + dz), g + 1): put(tx + dx, y, tz + dz, "polished_blackstone_bricks" if (dx + dz) % 3 else "cracked_polished_blackstone_bricks")
            for y in range(g + 1, g + 8): G.pop((tx + dx, y, tz + dz), None)
            edge = abs(dx) == 5 or abs(dz) == 5
            if edge:
                hh = rnd.choice([0, 1, 2, 3, 4, 5, 5]) if not (dz == -5 and abs(dx) <= 1) else 0
                for y in range(g + 1, g + 1 + hh): put(tx + dx, y, tz + dz, rnd.choice(["polished_blackstone_bricks", "cracked_polished_blackstone_bricks", "chiseled_polished_blackstone" if y == g + 3 else "polished_blackstone_bricks"]))
    for dx, dz in ((-3, -3), (3, -3), (-3, 3), (3, 3)):
        for y in range(g + 1, g + 7): put(tx + dx, y, tz + dz, "polished_blackstone")
        put(tx + dx, g + 7, tz + dz, "gilded_blackstone")
    put(tx, g + 1, tz, "crying_obsidian"); put(tx, g + 2, tz, "respawn_anchor"); put(tx - 1, g + 1, tz, "polished_blackstone_stairs[facing=east]"); put(tx + 1, g + 1, tz, "polished_blackstone_stairs[facing=west]")
    put(tx, g + 3, tz, "soul_lantern")
    for dx in (-1, 0, 1): put(tx + dx, g, tz - 6, "polished_blackstone_brick_stairs[facing=south]")
    # a ruined portal in the north-west
    px, pz = -17, -12; g = ground(px, pz)
    frame = [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (3, 1), (0, 2), (3, 2), (0, 3), (3, 3), (0, 4), (1, 4)]
    for fx, fy in frame: put(px + fx, g + 1 + fy, pz, rnd.choice(["obsidian", "crying_obsidian", "obsidian"]))
    for dx in range(-2, 6):
        for dz in range(-2, 3):
            if rnd.random() < 0.45: put(px + dx, ground(px + dx, pz + dz), pz + dz, rnd.choice(["netherrack", "magma_block", "netherrack", "gold_block" if rnd.random() < 0.08 else "netherrack"]))
    # a fossil in the soul valley (north-east)
    fx_, fz_ = 12, 22; g = ground(fx_, fz_)
    for i in range(7):
        x = fx_ + i - 3
        for y in range(g + 1, g + 1 + (4 if i % 2 == 0 else 1)): put(x, y, fz_, "bone_block[axis=y]")
        if i % 2 == 0: put(x, g + 4, fz_, "bone_block[axis=x]")
    for x in range(fx_ - 4, fx_ + 5): put(x, g + 1, fz_ + 1, "bone_block[axis=x]")
    # outcrops of the minable rarities (they grow back)
    for i in range(24):
        a_ = rnd.uniform(0, 2 * math.pi); d = rnd.uniform(11, RR - 4)
        x, z = int(math.cos(a_) * d), int(math.sin(a_) * d)
        if (z < -21 and abs(x) < 6) or math.hypot(x - tx, z - tz) < 8 or math.hypot(x - px, z - pz) < 5: continue
        blk = rnd.choice(["amethyst_block", "crying_obsidian", "gilded_blackstone", "nether_gold_ore", "nether_quartz_ore", "obsidian", "nether_quartz_ore", "gilded_blackstone"])
        r = rnd.randint(1, 2); g = ground(x, z)
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if abs(dx) + abs(dz) > r + 1 or (x + dx, z + dz) not in H or math.hypot(x + dx, z + dz) < 11.5: continue   # not over the crater
                gg = ground(x + dx, z + dz)   # each column sits on its own ground, so nothing hangs over a slope
                tall = rnd.randint(1, 3) if (dx, dz) != (0, 0) else 3
                for dy in range(1, tall + 1): put(x + dx, gg + dy, z + dz, blk)
        if i % 4 == 0: put(x, g + 1, z, "ancient_debris")
    # islets hovering overhead
    for i in range(5):
        a_ = i * 2 * math.pi / 5 + 0.7; cx_, cz_ = int(math.cos(a_) * 25), int(math.sin(a_) * 25); cy = rnd.randint(10, 15); rr = rnd.randint(2, 3)
        for dx in range(-rr, rr + 1):
            for dz in range(-rr, rr + 1):
                if dx * dx + dz * dz > rr * rr + 1: continue
                dep = rr - int(math.hypot(dx, dz)) + 1
                for y in range(cy - dep, cy + 1): put(cx_ + dx, y, cz_ + dz, "blackstone" if y < cy else rnd.choice(["amethyst_block", "blackstone", "crying_obsidian"]))
        put(cx_, cy + 1, cz_, "amethyst_cluster[facing=up]")
        for k in range(1, 4): put(cx_, cy - rr - k, cz_, "weeping_vines_plant" if k < 3 else "weeping_vines")
    # spawn points: open ground on two rings, away from the temple and the portal
    rift_spawns = []
    for i in range(16):
        a_ = i * 2 * math.pi / 16 + 0.15; d = 13 if i % 2 else 24
        x, z = int(math.cos(a_) * d), int(math.sin(a_) * d)
        if math.hypot(x - tx, z - tz) < 8: x, z = int(x * 0.7), int(z * 0.7)
        rift_spawns.append((x, ground(x, z) + 1, z))
    # arrival platform with the portal back to the hub
    for x in range(-3, 4):
        for z in range(-33, -26): put(x, 0, z, "polished_blackstone_bricks")
        for z in range(-33, -29):
            for y in range(1, 10): G.pop((x, y, z), None)
    # emit: runs along x of the same block become one fill
    b = Build(1717)
    rows = {}
    for (x, y, z), blk in G.items(): rows.setdefault((y, z), []).append((x, blk))
    for (y, z) in sorted(rows):
        run = sorted(rows[(y, z)])
        i = 0
        while i < len(run):
            j = i
            while j + 1 < len(run) and run[j + 1][0] == run[j][0] + 1 and run[j + 1][1] == run[i][1]: j += 1
            if j == i: b.set(run[i][0], y, z, run[i][1])
            else: b.fill(run[i][0], y, z, run[j][0], y, z, run[i][1])
            i = j + 1
    fn("zones/rift_island", "\n".join(b.c))
    rift_cmds = [f"kill @e[type=minecraft:text_display,tag=cs_zonel,x={RIFT[0] - 40},y={RIFT[1] - 20},z={RIFT[2] - 42},dx=80,dy=45,dz=84]"]
    rift_cmds += [f"fill {RIFT[0] - RR - 3} {y} {RIFT[2] - RR - 3} {RIFT[0] + RR + 3} {y} {RIFT[2] + RR + 3} minecraft:air" for y in range(RIFT[1] - 28, RIFT[1] + 22)]
    biome = [f"fillbiome {RIFT[0] - RR - 3} {y} {RIFT[2] - RR - 3} {RIFT[0] + RR + 3} {y + 3} {RIFT[2] + RR + 3} minecraft:{RIFT_BIOME}"
             for y in range(RIFT[1] - 32, RIFT[1] + 28, 4)]   # in 4-high slabs: fillbiome takes at most 32768 blocks a go
    fn("zones/rift_biome", "\n".join([f"forceload add {RIFT[0] - 36} {RIFT[2] - 36} {RIFT[0] + 36} {RIFT[2] + 36}"] + biome
                                     + [f"forceload remove {RIFT[0] - 36} {RIFT[2] - 36} {RIFT[0] + 36} {RIFT[2] + 36}"]))
    rift_cmds += biome
    rift_cmds += [f"execute positioned {RIFT[0]} {RIFT[1]} {RIFT[2]} run function {NS}:zones/rift_island",
                  f"execute positioned {RIFT[0]} {RIFT[1]} {RIFT[2] - 31} run function {NS}:portal/style_rift",
                  f"summon minecraft:text_display {RIFT[0] + 0.5} {RIFT[1] + 3} {RIFT[2] - 26.5} {{Tags:[\"{NS}\",\"cs_zonel\"],billboard:\"center\",text:"
                  + snbt({"text": "Sky Lord's Rift", "color": "light_purple", "bold": True, "extra": [txt("\nRare blocks grow back · Lv 15-30 mobs · /warp hub", "dark_gray", bold=False)]}) + "}",
                  f"summon minecraft:text_display {RIFT[0] + 0.5} {RIFT[1] + 8.4} {RIFT[2] - 30.5} {{Tags:[\"{NS}\",\"cs_zonel\"],billboard:\"center\",text:"
                  + snbt({"text": "Hub", "color": "gold", "bold": True, "extra": [txt("\nWalk through to go back", "gray", bold=False)]}) + "}"]
    fn("zones/build_rift", "\n".join([f"forceload add {RIFT[0] - 36} {RIFT[2] - 36} {RIFT[0] + 36} {RIFT[2] + 36}"] + rift_cmds
                                     + [f"forceload remove {RIFT[0] - 36} {RIFT[2] - 36} {RIFT[0] + 36} {RIFT[2] + 36}"]))
    # its portal in the hub: south-east of the plaza, mirroring the Woods portal (Portals.FIXED {13, 101, 15, rift})
    fn("zones/hub_rift_portal", "\n".join([
        "kill @e[type=minecraft:text_display,tag=cs_riftl]",
        "fill 10 100 12 16 100 18 minecraft:stone", "fill 10 101 12 16 101 18 minecraft:polished_blackstone_bricks",
        "fill 11 101 13 15 101 17 minecraft:cracked_polished_blackstone_bricks replace minecraft:polished_blackstone_bricks",
        "fill 10 102 12 16 110 18 minecraft:air",
        "fill 12 101 11 14 101 11 minecraft:polished_blackstone_brick_stairs[facing=south]",
        f"execute positioned 13 101 15 run function {NS}:portal/style_rift",
        "summon minecraft:text_display 13.5 108.4 15.5 {Tags:[\"" + NS + "\",\"cs_riftl\"],billboard:\"center\",text:"
        + snbt({"text": "Sky Lord's Rift", "color": "light_purple", "bold": True,
                "extra": [txt("\nOnly for those wearing ", "gray", bold=False), txt("[Sky Lord]", "aqua", bold=True), txt(" · Lv 15-30 mobs", "gray", bold=False)]}) + "}"]))

    # ---- mobs: while someone is in a zone, keep up to ZONE_CAP (+2 per player) hostiles there; none when it's empty
    sec = []
    for z in ZONES:
        key, name, c, h, y, allow, secs, mobs, w = z
        spawns = {"mines": mine_spawns, "woods": woods_spawns, "rift": rift_spawns}[key]
        rp = (c[0], c[1], c[2] - 33) if key == "mines" else (c[0], c[1], c[2] - 31)
        sec += [f"execute if entity @a[{box(z)}] positioned {rp[0]} {rp[1]} {rp[2]} run function {NS}:portal/fx_{key}"]
        sec += [f"execute unless entity @a[{box(z)}] run kill @e[tag=cs_zone_{key}]",
                f"execute if entity @a[{box(z)}] run function {NS}:zones/{key}/tick"]
        roll = [f"execute store result score #n cs_tmp if entity @e[tag=cs_zone_{key}]",
                f"execute store result score #pl cs_tmp if entity @a[{box(z)}]",
                f"scoreboard players operation #pl cs_tmp *= #2c cs_tmp", f"scoreboard players add #pl cs_tmp {ZONE_CAP}",
                "execute if score #n cs_tmp >= #pl cs_tmp run return 0",
                f"execute store result score #r cs_tmp run random value 1..{SPAWN_EVERY.get(key, 3)}", "execute unless score #r cs_tmp matches 1 run return 0",
                f"execute store result score #r cs_tmp run random value 1..{len(spawns)}"]
        for i, (sx, sy, sz) in enumerate(spawns, 1):
            roll.append(f"execute if score #r cs_tmp matches {i} positioned {c[0] + sx + 0.5} {c[1] + sy} {c[2] + sz + 0.5} run function {NS}:zones/{key}/mob")
        fn(f"zones/{key}/tick", "\n".join(roll))
        mob = [f"execute store result score #m cs_tmp run random value 1..{len(mobs)}"]
        for i, m in enumerate(mobs, 1):
            extra = ",IsImmuneToZombification:1b" if m.startswith("piglin") else ""   # brutes would zombify in the overworld
            mob.append(f"execute if score #m cs_tmp matches {i} run summon minecraft:{m} ~ ~ ~ {{Tags:[\"cs_zone_mob\",\"cs_zone_{key}\"],PersistenceRequired:1b{extra}}}")
        mob.append("particle minecraft:large_smoke ~ ~0.5 ~ 0.3 0.5 0.3 0.01 10")
        fn(f"zones/{key}/mob", "\n".join(mob))
    # ---- the Rift Warden: a giant armoured wither skeleton that sometimes rises in the Rift (while someone's there).
    # About once every WARDEN_ODDS seconds of play there, never within WARDEN_COOLDOWN seconds of the last one. It
    # calls up wither skeleton guards, sends out a withering shockwave, and drops rich loot; everyone in the Rift when
    # it falls gets WARDEN_COINS. It sinks back into the rift when the last player leaves (tag cs_zone_rift).
    WARDEN_ODDS, WARDEN_COOLDOWN, WARDEN_COINS, WARDEN_HP = 600, 900, 1500, 450
    rbox = box(next(z for z in ZONES if z[0] == "rift"))
    trim = '"minecraft:trim":{material:"minecraft:amethyst",pattern:"minecraft:%s"}'
    def piece(it, pat): return '{id:"minecraft:%s",count:1,components:{%s,"minecraft:enchantment_glint_override":true}}' % (it, trim % pat)
    warden = ("{Tags:[\"cs_zone_boss\",\"cs_rift_boss\",\"cs_zone_rift\"],PersistenceRequired:1b,CustomNameVisible:1b,"
              "CustomName:{text:\"☠ The Rift Warden\",color:\"dark_purple\",bold:true},DeathLootTable:\"%s:entities/rift_warden\","
              "equipment:{head:%s,chest:%s,legs:%s,feet:%s,mainhand:{id:\"minecraft:netherite_sword\",count:1,components:{\"minecraft:enchantment_glint_override\":true,\"minecraft:attribute_modifiers\":[]}}},"
              "drop_chances:{head:0f,chest:0f,legs:0f,feet:0f,mainhand:0f},"
              "attributes:[{id:\"minecraft:scale\",base:2.6},{id:\"minecraft:max_health\",base:%d},{id:\"minecraft:attack_damage\",base:9},"
              "{id:\"minecraft:armor\",base:8},{id:\"minecraft:armor_toughness\",base:2},{id:\"minecraft:knockback_resistance\",base:1},"
              "{id:\"minecraft:movement_speed\",base:0.28},{id:\"minecraft:follow_range\",base:48},{id:\"minecraft:step_height\",base:2}],Health:%d}"
              % (NS, piece("netherite_helmet", "silence"), piece("netherite_chestplate", "eye"), piece("netherite_leggings", "ward"),
                 piece("netherite_boots", "rib"), WARDEN_HP, WARDEN_HP))
    fn("zones/rift/boss_roll", "\n".join([
        f"execute if entity @e[tag=cs_rift_boss] run return run function {NS}:zones/rift/boss_tick",
        f"execute if score #rboss cs_tmp matches 1 run function {NS}:zones/rift/boss_gone",
        "execute if score #rcd cs_tmp matches 1.. run return run scoreboard players remove #rcd cs_tmp 1",
        f"execute store result score #r cs_tmp run random value 1..{WARDEN_ODDS}",
        f"execute if score #r cs_tmp matches 1 run function {NS}:zones/rift/boss_spawn"]))
    fn("zones/rift/boss_spawn", "\n".join([
        f"execute positioned {RIFT[0] + 0.5} {RIFT[1] + 12} {RIFT[2] - 14.5} positioned over motion_blocking_no_leaves run summon minecraft:wither_skeleton ~ ~ ~ " + warden,
        f"execute positioned {RIFT[0]} {RIFT[1] + 1} {RIFT[2] - 14} run particle minecraft:soul_fire_flame ~ ~2 ~ 2 3 2 0.05 300 force",
        f"execute positioned {RIFT[0]} {RIFT[1] + 1} {RIFT[2] - 14} run playsound minecraft:entity.wither.spawn hostile @a ~ ~ ~ 4 0.8",
        "scoreboard players set #rboss cs_tmp 1", "scoreboard players set #rtick cs_tmp 0",
        f"bossbar add {NS}:rift_warden {{text:\"☠ The Rift Warden\",color:\"dark_purple\",bold:true}}",
        f"bossbar set {NS}:rift_warden color purple", f"bossbar set {NS}:rift_warden style notched_10", f"bossbar set {NS}:rift_warden max {WARDEN_HP}",
        f"bossbar set {NS}:rift_warden value {WARDEN_HP}",
        f"tellraw @a [{{text:\"☠ \",color:\"dark_purple\"}},{{text:\"The Rift Warden has risen in the Sky Lord's Rift!\",color:\"light_purple\",bold:true}}]"]))
    fn("zones/rift/boss_tick", "\n".join([
        f"bossbar set {NS}:rift_warden players @a[{rbox}]",
        f"execute store result bossbar {NS}:rift_warden value run data get entity @e[tag=cs_rift_boss,limit=1] Health",
        "scoreboard players add #rtick cs_tmp 1",
        # every 15 s: two wither skeleton guards rise beside it
        "scoreboard players operation #m cs_tmp = #rtick cs_tmp", "scoreboard players set #k cs_tmp 20", "scoreboard players operation #m cs_tmp %= #k cs_tmp",
        f"execute if score #m cs_tmp matches 0 as @e[tag=cs_rift_boss] at @s run function {NS}:zones/rift/boss_guards",
        # every 9 s: a withering shockwave hits everyone within 7 blocks
        "scoreboard players operation #m cs_tmp = #rtick cs_tmp", "scoreboard players set #k cs_tmp 12", "scoreboard players operation #m cs_tmp %= #k cs_tmp",
        f"execute if score #m cs_tmp matches 4 as @e[tag=cs_rift_boss] at @s run function {NS}:zones/rift/boss_wave",
        # it never strays far from the island
        f"execute as @e[tag=cs_rift_boss] at @s unless entity @s[{rbox}] positioned {RIFT[0] + 0.5} {RIFT[1] + 12} {RIFT[2] - 14.5} positioned over motion_blocking_no_leaves run tp @s ~ ~ ~"]))
    fn("zones/rift/boss_guards", "\n".join([
        "execute store result score #g cs_tmp if entity @e[type=minecraft:wither_skeleton,tag=cs_zone_rift,distance=..24]",
        "execute if score #g cs_tmp matches 3.. run return 0",
        "particle minecraft:soul ~ ~1 ~ 2 1 2 0.05 60 force", "playsound minecraft:entity.wither_skeleton.ambient hostile @a ~ ~ ~ 3 0.6",
        "summon minecraft:wither_skeleton ~2 ~ ~ {Tags:[\"cs_zone_mob\",\"cs_zone_rift\"],PersistenceRequired:1b}"]))
    fn("zones/rift/boss_wave", "\n".join([
        "particle minecraft:sculk_soul ~ ~0.5 ~ 4 0.2 4 0.02 120 force", "particle minecraft:explosion ~ ~0.5 ~ 2 0.1 2 0 6 force",
        "playsound minecraft:entity.warden.sonic_boom hostile @a ~ ~ ~ 3 0.7",
        "execute as @a[distance=..6,gamemode=!creative,gamemode=!spectator] run damage @s 5 minecraft:sonic_boom",   # damage takes one target
        "effect give @a[distance=..6,gamemode=!creative,gamemode=!spectator] minecraft:wither 3 0"]))
    fn("zones/rift/boss_gone", "\n".join([
        "scoreboard players set #rboss cs_tmp 0", f"scoreboard players set #rcd cs_tmp {WARDEN_COOLDOWN}", f"bossbar remove {NS}:rift_warden",
        # killed (someone's still in the Rift) or just faded away when everyone left (then no reward)
        f"execute if entity @a[{rbox}] run function {NS}:zones/rift/boss_won"]))
    fn("zones/rift/boss_won", "\n".join([
        f"scoreboard players add @a[{rbox}] cs_coins {WARDEN_COINS}",
        f"tellraw @a [{{text:\"☠ \",color:\"dark_purple\"}},{{text:\"The Rift Warden has fallen! \",color:\"light_purple\",bold:true}},{{text:\"Everyone in the Rift gets {WARDEN_COINS:,} coins.\",color:\"gold\",bold:false}}]",
        f"execute positioned {RIFT[0]} {RIFT[1] + 1} {RIFT[2]} run playsound minecraft:ui.toast.challenge_complete master @a[{rbox}] ~ ~ ~ 1 1",
        f"kill @e[type=minecraft:wither_skeleton,tag=cs_zone_rift]"]))
    def lt(it, lo, hi=None, chance=1.0):
        e = {"type": "minecraft:item", "name": f"minecraft:{it}"}
        if hi: e["functions"] = [{"function": "minecraft:set_count", "count": {"type": "minecraft:uniform", "min": lo, "max": hi}}]
        p = {"rolls": 1, "entries": [e]}
        if chance < 1: p["conditions"] = [{"condition": "minecraft:random_chance", "chance": chance}]
        return p
    js(f"data/{NS}/loot_table/entities/rift_warden.json", {"type": "minecraft:entity", "pools": [
        lt("netherite_scrap", 2, 4), lt("ancient_debris", 1, 3), lt("amethyst_shard", 12, 24), lt("crying_obsidian", 4, 8),
        lt("enchanted_golden_apple", 1, None, 0.5), lt("wither_skeleton_skull", 1, None, 0.5), lt("netherite_upgrade_smithing_template", 1, None, 0.35),
        lt("nether_star", 1, None, 0.12), lt("silence_armor_trim_smithing_template", 1, None, 0.08)]})
    sec.append(f"execute if entity @a[{rbox}] run function {NS}:zones/rift/boss_roll")
    sec.append(f"execute unless entity @a[{rbox}] if score #rboss cs_tmp matches 1 unless entity @e[tag=cs_rift_boss] run function {NS}:zones/rift/boss_gone")

    fn("zones/second", "\n".join(sec))
    fn("zones/tp", "$execute in minecraft:overworld run tp @s $(x) $(y) $(z) $(yaw) 0")

    # ---- the Phoenix: a rare drop from End bosses (boss/killed2 runs boss/phoenix_<realm>)
    fn("boss/phoenix_e", f"$execute as @a[scores={{cs_plot=$(id)}}] run function {NS}:boss/phoenix_roll")
    fn("boss/phoenix_n", "return 0")
    fn("boss/phoenix_roll", f"execute store result score #r cs_tmp run random value 1..100\nexecute if score #r cs_tmp matches ..{PHOENIX_CHANCE} run pets grant @s phoenix")

    in_zone = " ".join(f"unless entity @s[{box(z)}]" for z in ZONES)
    return {"cfg": cfg, "in_zone": in_zone}
