"""Factions01 spawn hub (safezone) + PvP colosseum and roads (warzone). Writes the cspawn datapack functions.
Spawn: walled stone-brick plaza, floor y72, centre 0,0, walls at +-40, four gates with stairs down to y65.
Arena: colosseum centre (0,-112), sand floor y64, linked to the north gate by a flat road at y64."""
import sys, math, random, os, json
sys.path.insert(0, "/opt/factions/survey"); from scan import get
random.seed(2013)
W = "/AMPStorage/.ampdata/instances/Factions01/Minecraft/world/datapacks/crispyspawn"
OUT = W + "/data/cspawn/function/"
SKIP = ("air", "leaves", "log", "wood", "snow", "grass", "fern", "bush", "flower", "poppy", "dandelion", "vine", "sapling",
        "mushroom", "berry", "lichen", "tulip", "allium", "bluet", "daisy", "cornflower", "lily", "root", "kelp", "seagrass", "cactus", "cane")
def ground(x, z):
    for y in range(140, -60, -1):
        n = get(x, y, z)[0].split(":")[1]
        if not any(k in n for k in SKIP): return y
    return 62

fns = {}; cur = None
def fn(name):
    global cur; cur = name; fns[name] = []
def C(s): fns[cur].append(s)
def fill(x0, y0, z0, x1, y1, z1, b, mode=""):
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    dx, dy, dz = x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1
    if dx * dy * dz > 32768:
        if dx >= dy and dx >= dz: m = x0 + dx // 2 - 1; fill(x0, y0, z0, m, y1, z1, b, mode); fill(m + 1, y0, z0, x1, y1, z1, b, mode)
        elif dz >= dy: m = z0 + dz // 2 - 1; fill(x0, y0, z0, x1, y1, m, b, mode); fill(x0, y0, m + 1, x1, y1, z1, b, mode)
        else: m = y0 + dy // 2 - 1; fill(x0, y0, z0, x1, m, z1, b, mode); fill(x0, m + 1, z0, x1, y1, z1, b, mode)
        return
    C(f"fill {x0} {y0} {z0} {x1} {y1} {z1} minecraft:{b}" + (" " + mode if mode else ""))
def sb(x, y, z, b): C(f"setblock {x} {y} {z} minecraft:{b}")
def runs(xs):
    xs = sorted(xs); out = []
    for x in xs:
        if out and out[-1][1] == x - 1: out[-1][1] = x
        else: out.append([x, x])
    return out
def rowfill(cells, y0, y1, b, mode=""):
    """cells: set of (x,z) -> fills per z row."""
    byz = {}
    for x, z in cells: byz.setdefault(z, []).append(x)
    for z, xs in sorted(byz.items()):
        for a, c in runs(xs): fill(a, y0, z, c, y1, z, b, mode)
def weather(b): return random.choice(["mossy_stone_bricks", "cracked_stone_bricks"]) if random.random() < 0.16 else b

# ---------------------------------------------------------------- spawn
R, F = 40, 72
fn("biome")
for x0 in range(-80, 80, 16):
    for z0 in range(-176, 80, 16):
        C(f"fillbiome {x0} 48 {z0} {x0 + 15} 127 {z0 + 15} minecraft:plains")

fn("spawn1")
fill(-R, 73, -R, R, 130, R, "air")
fill(-R, 45, -R, R, F - 1, R, "stone_bricks")
for t in range(-R, R + 1):
    for y in range(56, F):
        for x, z in ((t, -R), (t, R), (-R, t), (R, t)):
            b = weather("stone_bricks")
            if b != "stone_bricks": sb(x, y, z, b)

fn("spawn2")
fill(-R, F, -R, R, F, R, "smooth_stone")
fill(-3, F, -38, 3, F, 38, "polished_andesite"); fill(-38, F, -3, 38, F, 3, "polished_andesite")
for s in (-4, 4):
    fill(s, F, -38, s, F, 38, "stone_bricks"); fill(-38, F, s, 38, F, s, "stone_bricks")
fill(-38, F, -38, 38, F, -37, "stone_bricks"); fill(-38, F, 37, 38, F, 38, "stone_bricks")
fill(-38, F, -38, -37, F, 38, "stone_bricks"); fill(37, F, -38, 38, F, 38, "stone_bricks")
plaza = {(x, z) for x in range(-10, 11) for z in range(-10, 11) if math.hypot(x, z) <= 9.5}
rowfill(plaza, F, F, "polished_andesite")
rowfill({c for c in plaza if math.hypot(*c) > 8.5}, F, F, "quartz_bricks")
pool = {c for c in plaza if math.hypot(*c) <= 4.5}
rim = {c for c in plaza if 4.5 < math.hypot(*c) <= 5.5}
rowfill(pool, F, F, "dark_prismarine"); rowfill(rim, F + 1, F + 1, "quartz_bricks")
rowfill(pool, F + 1, F + 1, "water")
fill(-1, F, -1, 1, F + 3, 1, "quartz_pillar"); fill(-1, F + 4, -1, 1, F + 4, 1, "iron_block"); sb(0, F + 5, 0, "beacon")
for x in range(-36, 37, 8):
    for z in range(-36, 37, 8):
        if abs(x) > 5 and abs(z) > 5 and (x, z) not in plaza and max(abs(x), abs(z)) < 32: sb(x, F, z, "sea_lantern")
# planters with bushes in each quadrant
for sx in (-1, 1):
    for sz in (-1, 1):
        cx, cz = 20 * sx, 20 * sz
        fill(cx - 3, F, cz - 3, cx + 3, F, cz + 3, "grass_block")
        fill(cx - 4, F + 1, cz - 4, cx + 4, F + 1, cz + 4, "stone_brick_wall")
        fill(cx - 3, F + 1, cz - 3, cx + 3, F + 1, cz + 3, "air")
        for g in ((cx - 4, cz), (cx + 4, cz), (cx, cz - 4), (cx, cz + 4)): sb(g[0], F + 1, g[1], "air")
        fill(cx, F + 1, cz, cx, F + 4, cz, "oak_log")
        fill(cx - 2, F + 4, cz - 2, cx + 2, F + 5, cz + 2, "oak_leaves[persistent=true]", "keep")
        fill(cx - 1, F + 6, cz - 1, cx + 1, F + 6, cz + 1, "oak_leaves[persistent=true]", "keep")
        for b in ((cx - 2, cz - 2), (cx + 2, cz + 2), (cx - 2, cz + 2), (cx + 2, cz - 2)):
            sb(b[0], F + 1, b[1], random.choice(["flowering_azalea", "azalea", "rose_bush[half=lower]"]))
            if "rose" in fns[cur][-1]: sb(b[0], F + 2, b[1], "rose_bush[half=upper]")
        # benches facing the planter
        for i in (-1, 0, 1):
            sb(cx + i, F + 1, cz - 6 * sz, "spruce_stairs[facing=" + ("north" if sz > 0 else "south") + "]")

fn("spawn3")
for a, b in ((-R, -R + 1), (R - 1, R)):
    fill(-R, F + 1, a, R, F + 5, b, "stone_bricks"); fill(a, F + 1, -R, b, F + 5, R, "stone_bricks")
for t in range(-R, R + 1, 2):
    for x, z in ((t, -R), (t, R), (-R, t), (R, t)): sb(x, F + 6, z, "stone_bricks")
for t in range(-R, R + 1):
    for y in range(F + 1, F + 6):
        for x, z in ((t, -R), (t, R), (-R, t), (R, t)):
            b = weather("stone_bricks")
            if b != "stone_bricks": sb(x, y, z, b)
for t in range(-36, 37, 8):
    if abs(t) > 5:
        for x, z in ((t, -R + 1), (t, R - 1), (-R + 1, t), (R - 1, t)): sb(x, F + 3, z, "sea_lantern")
for sx in (-1, 1):  # corner towers
    for sz in (-1, 1):
        fill(32 * sx, F + 1, 32 * sz, 40 * sx, F + 12, 40 * sz, "stone_bricks")
        for i in range(0, 9, 2):
            for x, z in ((32 * sx + i * sx, 32 * sz), (32 * sx + i * sx, 40 * sz), (32 * sx, 32 * sz + i * sz), (40 * sx, 32 * sz + i * sz)):
                sb(x, F + 13, z, "stone_bricks")
        sb(36 * sx, F + 13, 36 * sz, "sea_lantern")
        for y in range(F + 1, F + 13):
            for i in range(9):
                for x, z in ((32 * sx + i * sx, 40 * sz), (40 * sx, 32 * sz + i * sz)):
                    b = weather("stone_bricks")
                    if b != "stone_bricks": sb(x, y, z, b)
        for x, z in ((36 * sx, 40 * sz + sz), (40 * sx + sx, 36 * sz)):
            sb(x - (sx if abs(x) > 40 else 0), F + 9, z - (sz if abs(z) > 40 else 0), "sea_lantern")
# gates
for d in ("N", "S", "E", "W"):
    if d in "NS":
        z0 = -R if d == "N" else R - 1; fill(-3, F + 1, z0, 3, F + 4, z0 + 1, "air"); fill(-4, F + 5, z0, 4, F + 5, z0 + 1, "chiseled_stone_bricks")
    else:
        x0 = -R if d == "W" else R - 1; fill(x0, F + 1, -3, x0 + 1, F + 4, 3, "air"); fill(x0, F + 5, -4, x0 + 1, F + 5, 4, "chiseled_stone_bricks")

# ---------------------------------------------------------------- stairs + roads
DIRS = {"N": (0, -1, "south"), "S": (0, 1, "north"), "E": (1, 0, "west"), "W": (-1, 0, "east")}
def P(d, p, t):
    ax, az, _ = DIRS[d]
    return (ax * p + (t if ax == 0 else 0), az * p + (t if az == 0 else 0))

fn("stairs")
for d, (ax, az, face) in DIRS.items():
    a, b = P(d, 41, -4), P(d, 48, 4); fill(a[0], 65, a[1], b[0], 90, b[1], "air")
    for k in range(1, 9):
        p, y = 40 + k, F + 1 - k
        a, b = P(d, p, -4), P(d, p, 4); fill(a[0], 45, a[1], b[0], y - 1, b[1], "stone_bricks")
        a, b = P(d, p, -3), P(d, p, 3); fill(a[0], y, a[1], b[0], y, b[1], f"stone_brick_stairs[facing={face}]")
        for t in (-4, 4):
            x, z = P(d, p, t); sb(x, y, z, "stone_bricks"); sb(x, y + 1, z, "stone_brick_wall")
    for t in (-4, 4):
        x, z = P(d, 48, t); sb(x, 67, z, "lantern")

def road(d, p0, n, ox=0, oz=0, flat=None, posts=True, mats=("polished_andesite", "polished_andesite", "stone_bricks", "andesite", "cobblestone")):
    """Road of width 5 from p=p0 for n blocks in direction d, offset (ox,oz). Starts at y64; ramps at most 1 per block."""
    y = 64; ax, az, _ = DIRS[d]
    for i in range(n):
        p = p0 + i
        cx, cz = P(d, p, 0); cx += ox; cz += oz
        if flat is None and i > 0: y = max(y - 1, min(y + 1, ground(cx, cz)))
        a, b = P(d, p, -3), P(d, p, 3)
        fill(a[0] + ox, y + 1, a[1] + oz, b[0] + ox, y + 24, b[1] + oz, "air")
        fill(a[0] + ox, 45, a[1] + oz, b[0] + ox, y - 1, b[1] + oz, "stone_bricks", "keep")
        for t in range(-2, 3):
            x, z = P(d, p, t); sb(x + ox, y, z + oz, random.choice(mats))
        for t in (-3, 3):
            x, z = P(d, p, t); x += ox; z += oz
            if flat is not None:
                sb(x, y, z, "stone_bricks"); sb(x, y + 1, z, "stone_brick_wall")
                if posts and i % 8 == 4: sb(x, y + 2, z, "lantern")
            elif ground(x, z) < y - 1: sb(x, y, z, "stone_bricks")
            elif posts and i % 8 == 4: sb(x, y, z, "stone_bricks"); sb(x, y + 1, z, "stone_brick_wall"); sb(x, y + 2, z, "lantern")

fn("roads")
road("N", 49, 27, flat=64)            # spawn north gate -> arena south entrance (z -49 .. -75)
for d in ("S", "E", "W"): road(d, 49, 24)

# ---------------------------------------------------------------- arena
AX, AZ, AY = 0, -112, 64
cells = {(x, z): math.hypot(x - AX, z - AZ) for x in range(AX - 37, AX + 38) for z in range(AZ - 37, AZ + 38)}
def ring(lo, hi): return {c for c, r in cells.items() if lo < r <= hi}
fn("arena1")
rowfill(ring(-1, 36.5), AY + 1, 110, "air")
rowfill(ring(-1, 36.5), 45, AY - 1, "stone_bricks")
rowfill(ring(-1, 25.5), AY, AY, "smooth_sandstone")
for (x, z), r in cells.items():
    if r <= 25.5 and random.random() < 0.22: sb(x, AY, z, random.choice(["sandstone", "sand", "sandstone", "chiseled_sandstone"] if r > 3 else ["sandstone"]))
rowfill(ring(11.5, 12.5), AY, AY, "cut_red_sandstone")
rowfill(ring(25.5, 36.5), AY, AY, "stone_bricks")

fn("arena2")
rowfill(ring(25.5, 27.5), AY + 1, AY + 5, "stone_bricks")
for i in range(1, 9):
    rowfill(ring(27.5 + i - 1, 27.5 + i), AY + 1, AY + 5 + i, "stone_bricks")
    rowfill(ring(27.5 + i - 1, 27.5 + i), AY + 5 + i, AY + 5 + i, "polished_andesite" if i % 2 else "smooth_stone")
rowfill(ring(35.5, 36.5), AY + 1, AY + 16, "stone_bricks")
for (x, z), r in cells.items():
    if 35.5 < r <= 36.5:
        if round(math.degrees(math.atan2(z - AZ, x - AX)) / 4) % 2 == 0: sb(x, AY + 17, z, "stone_bricks")
        for y in range(56, AY + 17):
            b = weather("stone_bricks")
            if b != "stone_bricks": sb(x, y, z, b)
    if 25.5 < r <= 26.5 and round(math.degrees(math.atan2(z - AZ, x - AX))) % 30 == 15: sb(x, AY + 3, z, "sea_lantern")
    if 35.5 < r <= 36.5 and round(math.degrees(math.atan2(z - AZ, x - AX))) % 30 == 15: sb(x, AY + 16, z, "sea_lantern")
# pillars and the king-of-the-hill dais
for k in range(8):
    a = math.radians(22.5 + 45 * k); px, pz = AX + round(15 * math.cos(a)), AZ + round(15 * math.sin(a))
    fill(px, AY + 1, pz, px + 1, AY + 4, pz + 1, "stone_bricks"); fill(px, AY + 5, pz, px + 1, AY + 5, pz + 1, "sea_lantern")
    fill(px, AY + 6, pz, px + 1, AY + 6, pz + 1, "stone_brick_slab")
fill(AX - 3, AY + 1, AZ - 3, AX + 3, AY + 1, AZ + 3, "polished_blackstone_bricks")
fill(AX - 2, AY + 2, AZ - 2, AX + 2, AY + 2, AZ + 2, "polished_blackstone_bricks")
sb(AX, AY + 2, AZ, "gold_block")
for x, z in ((AX - 3, AZ - 3), (AX + 3, AZ + 3), (AX - 3, AZ + 3), (AX + 3, AZ - 3)): sb(x, AY + 2, z, "sea_lantern")
# entrance tunnels
for d in ("N", "S", "E", "W"):
    ax, az, _ = DIRS[d]
    for p in range(25, 38):
        a, b = P(d, p, -2), P(d, p, 2)
        fill(a[0] + AX, AY + 1, a[1] + AZ, b[0] + AX, AY + 4, b[1] + AZ, "air")
        fill(a[0] + AX, AY, a[1] + AZ, b[0] + AX, AY, b[1] + AZ, "polished_andesite")
    for p in (27, 31, 35):
        x, z = P(d, p, 0); sb(x + AX, AY + 5, z + AZ, "sea_lantern")
    x, z = P(d, 25, 0)
    fill(*(lambda a, b: (a[0] + AX, AY + 5, a[1] + AZ, b[0] + AX, AY + 5, b[1] + AZ))(P(d, 26, -3), P(d, 26, 3)), "chiseled_stone_bricks")
fn("arena3")
for d in ("N", "E", "W"): road(d, 37, 12, ox=AX, oz=AZ)

# ---------------------------------------------------------------- signs
def sign(x, y, z, face, lines):
    msgs = ",".join(("{text:%s}" % json.dumps(l)) if isinstance(l, str) and l else ('""' if not l else "{" + ",".join(f"{k}:{json.dumps(v) if not isinstance(v, bool) else ('1b' if v else '0b')}" for k, v in l.items()) + "}") for l in lines)
    sb(x, y, z, f"dark_oak_wall_sign[facing={face}]{{front_text:{{messages:[{msgs}]}},is_waxed:1b}}")
fn("signs")
fill(-3, F + 1, 10, 3, F + 1, 10, "polished_andesite"); sb(-3, F + 2, 10, "lantern"); sb(3, F + 2, 10, "lantern")
H = lambda t, c="gold": {"text": t, "color": c, "bold": True}
sign(-2, F + 1, 11, "south", ["", H("Welcome to"), H("Crispy Factions"), {"text": "2013 classic", "color": "gray"}])
sign(-1, F + 1, 11, "south", [H("Getting Started", "dark_green"), "/f create <name>", "/kit starter", "/shop"])
sign(0, F + 1, 11, "south", [H("Combat", "red"), "1.8 PvP", "No shields/elytra", "No netherite"])
sign(1, F + 1, 11, "south", [H("Raiding", "dark_red"), "Obsidian: 5 TNT", "or 3 creepers", "Watered = immune"])
sign(2, F + 1, 11, "south", [H("PvP Arena", "dark_purple"), "North gate", "Warzone: PvP on", "Border: 2500"])
# gate signs (outside face, above the stairs)
sign(5, F + 3, -R - 1, "north", ["", H("PvP Arena", "dark_purple"), {"text": "straight ahead", "color": "gray"}, ""])
sign(-5, F + 3, -R - 1, "north", ["", H("WARZONE", "dark_red"), {"text": "PvP is on", "color": "gray"}, ""])
for d, face, x, z in (("S", "south", 5, R + 1), ("E", "east", R + 1, 5), ("W", "west", -R - 1, 5)):
    sign(x, F + 3, z, face, ["", H("WARZONE", "dark_red"), {"text": "PvP is on", "color": "gray"}, {"text": "wilds past 192", "color": "gray"}])

# ---------------------------------------------------------------- write
os.makedirs(OUT, exist_ok=True)
json.dump({"pack": {"pack_format": 94, "supported_formats": [48, 200], "min_format": [48, 0], "max_format": [200, 0], "description": "Crispy Factions spawn build"}}, open(W + "/pack.mcmeta", "w"))
for name, lines in fns.items():
    open(OUT + name + ".mcfunction", "w").write("\n".join(lines) + "\n")
    print(name, len(lines))
os.system(f"chown -R amp:amp {W}")
