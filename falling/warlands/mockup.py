#!/usr/bin/env python3
"""Warlands mockup (concept, not built): a voxel model of the proposed PvP resource island for Crispy Skyblock,
rendered isometrically, plus a labelled top-down plan.   python3 mockup.py <out dir>"""
import math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
N, H = 150, 70                      # footprint and height of the model
R = 66                              # island radius
rng = random.Random(7)
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tiktok", "fonts", "LilitaOne-Regular.ttf")

# block palette: id -> (top colour, side colour)
B = {}
def blk(name, top, side=None): B[name] = (len(B) + 1, top, side or tuple(int(c * 0.8) for c in top)); return B[name][0]
BLACKSTONE = blk("blackstone", (52, 46, 54)); BASALT = blk("basalt", (78, 76, 82)); DEEPSLATE = blk("deepslate", (70, 70, 76))
STONE = blk("stone", (118, 116, 118)); DIRT = blk("dirt", (92, 66, 48)); COARSE = blk("coarse_dirt", (74, 62, 56)); ASH = blk("ash", (96, 92, 98))
MAGMA = blk("magma", (196, 82, 22)); LAVA = blk("lava", (240, 120, 20)); OBSIDIAN = blk("obsidian", (32, 22, 46))
DIAMOND = blk("diamond_ore", (90, 200, 210)); EMERALD = blk("emerald_ore", (40, 190, 90)); GOLD = blk("gold_ore", (230, 190, 50))
DEBRIS = blk("ancient_debris", (110, 74, 64)); AMETHYST = blk("amethyst", (154, 100, 210)); CRYSTAL = blk("crystal", (200, 160, 255))
BRICK = blk("deepslate_bricks", (84, 84, 92)); POLISHED = blk("polished_blackstone", (60, 54, 64)); BEACON = blk("beacon", (150, 240, 255))
GOLDBLOCK = blk("gold_block", (250, 210, 60)); RED = blk("red_banner", (180, 30, 30)); PLANK = blk("dark_oak_planks", (66, 44, 26))
CHAIN = blk("chain", (60, 66, 76)); SOUL = blk("soul_lantern", (120, 220, 240)); LANTERN = blk("lantern", (255, 200, 90))
COLOR = {i: (t, s) for _, (i, t, s) in B.items()}

V = np.zeros((N, H, N), dtype=np.uint8)   # x, y, z
cx = cz = N // 2

def noise2(x, z, scale, seed):
    r = random.Random(seed)
    g = {}
    def val(ix, iz):
        k = (ix, iz)
        if k not in g: g[k] = random.Random(hash((ix, iz, seed))).random()
        return g[k]
    fx, fz = x / scale, z / scale; ix, iz = math.floor(fx), math.floor(fz); tx, tz = fx - ix, fz - iz
    sm = lambda t: t * t * (3 - 2 * t)
    a = val(ix, iz) * (1 - sm(tx)) + val(ix + 1, iz) * sm(tx)
    b = val(ix, iz + 1) * (1 - sm(tx)) + val(ix + 1, iz + 1) * sm(tx)
    return a * (1 - sm(tz)) + b * sm(tz)

BASE = 34
top = np.full((N, N), -1)
for x in range(N):
    for z in range(N):
        dx, dz = x - cx, z - cz
        d = math.hypot(dx, dz); ang = math.atan2(dz, dx)
        edge = R + 7 * math.sin(ang * 5 + 1) + 4 * math.sin(ang * 11) + (noise2(x, z, 9, 3) - 0.5) * 10
        if d > edge: continue
        h = BASE + int((noise2(x, z, 18, 1) - 0.5) * 8 + (noise2(x, z, 7, 2) - 0.5) * 4)
        h += int(max(0, 6 - d / 6))            # the centre rises to the node
        depth = int((1 - d / edge) ** 0.7 * 26) + 3   # the floating underside: a rough cone
        for y in range(h - depth, h + 1):
            V[x, y, z] = DEEPSLATE if y < h - 6 else BASALT if y < h - 2 else BLACKSTONE
        n = noise2(x, z, 5, 9)
        V[x, h, z] = ASH if n > 0.72 else BASALT if n > 0.55 else COARSE if n < 0.12 else BLACKSTONE
        top[x, z] = h

def surf(x, z): return top[x, z]
def put(x, y, z, b):
    if 0 <= x < N and 0 <= z < N and 0 <= y < H: V[x, y, z] = b

# lava cracks and a lava river through the debris pit (west)
for t in range(260):
    a = t / 260 * math.tau * 1.0
    for base_ang, length in ((0.3, 50), (2.1, 46), (3.9, 44), (5.2, 40)):
        if t > length: continue
        x = int(cx + math.cos(base_ang + math.sin(t / 9) * 0.25) * (12 + t)); z = int(cz + math.sin(base_ang + math.sin(t / 9) * 0.25) * (12 + t))
        if 0 <= x < N and 0 <= z < N and surf(x, z) > 0: V[x, surf(x, z), z] = MAGMA if t % 3 else LAVA
for t in range(-40, 10):
    x = cx - 34 + int(math.sin(t / 6) * 3); z = cz + t
    for w in range(-2, 3):
        if surf(x + w, z) > 0: V[x + w, surf(x + w, z), z] = LAVA if abs(w) < 2 else MAGMA

# resource fields
def field(fx, fz, rad, ores, sink=0):
    for x in range(fx - rad, fx + rad + 1):
        for z in range(fz - rad, fz + rad + 1):
            if 0 <= x < N and 0 <= z < N and surf(x, z) > 0 and math.hypot(x - fx, z - fz) < rad:
                y = surf(x, z) - sink if math.hypot(x - fx, z - fz) < rad - 3 else surf(x, z)
                for yy in range(y + 1, surf(x, z) + 1): V[x, yy, z] = 0
                V[x, y, z] = STONE
                if rng.random() < 0.28: V[x, y, z] = rng.choice(ores)
                if rng.random() < 0.05: V[x, y + 1, z] = rng.choice(ores)
                top[x, z] = y
field(cx + 30, cz - 28, 15, [DIAMOND, EMERALD, DIAMOND], sink=4)          # NE quarry
field(cx - 32, cz - 6, 13, [DEBRIS, DEBRIS, MAGMA], sink=3)               # W debris pit
field(cx - 26, cz - 34, 13, [GOLD, AMETHYST, GOLD], sink=2)               # NW geode field
field(cx + 34, cz + 18, 12, [AMETHYST, CRYSTAL, AMETHYST], sink=0)        # E crystal ridge
for _ in range(14):                                                       # crystal spikes on the ridge
    x, z = cx + 34 + rng.randint(-9, 9), cz + 18 + rng.randint(-9, 9)
    if surf(x, z) > 0:
        for y in range(surf(x, z) + 1, surf(x, z) + rng.randint(3, 8)): put(x, y, z, CRYSTAL)

# the Treasure Node: a raised polished platform with an obelisk and beacon
ty = surf(cx, cz) + 1
for x in range(cx - 9, cx + 10):
    for z in range(cz - 9, cz + 10):
        if math.hypot(x - cx, z - cz) <= 9.5:
            for y in range(surf(x, z) + 1, ty + 1): V[x, y, z] = POLISHED
            top[x, z] = ty
for x, z in ((cx - 7, cz - 7), (cx + 7, cz - 7), (cx - 7, cz + 7), (cx + 7, cz + 7)):
    for y in range(ty + 1, ty + 7): put(x, y, z, BRICK)
    put(x, ty + 7, z, SOUL)
for y in range(ty + 1, ty + 9):
    for x in range(cx - 1, cx + 2):
        for z in range(cz - 1, cz + 2): put(x, y, z, OBSIDIAN if y < ty + 8 else GOLDBLOCK)
put(cx, ty + 9, cz, BEACON)
for y in range(ty + 10, H): put(cx, y, cz, BEACON) if y % 2 == 0 else None   # the beam

# ruined walls and broken pillars for cover
for _ in range(16):
    a = rng.random() * math.tau; d = rng.uniform(18, 52); x0, z0 = int(cx + math.cos(a) * d), int(cz + math.sin(a) * d)
    horiz = rng.random() < 0.5; ln = rng.randint(5, 11)
    for i in range(ln):
        x, z = (x0 + i, z0) if horiz else (x0, z0 + i)
        if 0 <= x < N and 0 <= z < N and surf(x, z) > 0:
            for y in range(surf(x, z) + 1, surf(x, z) + 1 + rng.choice([1, 2, 2, 3, 3, 4])): put(x, y, z, BRICK)
for _ in range(10):
    a = rng.random() * math.tau; d = rng.uniform(15, 55); x, z = int(cx + math.cos(a) * d), int(cz + math.sin(a) * d)
    if 0 <= x < N and 0 <= z < N and surf(x, z) > 0:
        for y in range(surf(x, z) + 1, surf(x, z) + rng.randint(4, 9)): put(x, y, z, POLISHED)

# watchtowers on the rim (NW, NE, SE, SW)
for a in (math.radians(225), math.radians(315), math.radians(45), math.radians(135)):
    x0, z0 = int(cx + math.cos(a) * 52), int(cz + math.sin(a) * 52)
    if surf(x0, z0) <= 0: continue
    b = surf(x0, z0)
    for x in range(x0 - 2, x0 + 3):
        for z in range(z0 - 2, z0 + 3):
            hollow = abs(x - x0) < 2 and abs(z - z0) < 2
            for y in range(b + 1, b + 13):
                if not hollow or y in (b + 1, b + 12): put(x, y, z, BRICK)
            if abs(x - x0) == 2 and abs(z - z0) == 2: put(x, b + 13, z, BRICK)
    put(x0, b + 13, z0, RED); put(x0, b + 14, z0, RED)

# arrival bastion (south): obsidian platform with the portal, a short wall and a gate into the warzone
bz = cz + R - 4; by = surf(cx, bz - 12) + 3 if surf(cx, bz - 12) > 0 else BASE + 3
for x in range(cx - 10, cx + 11):
    for z in range(bz - 6, bz + 7):
        for y in range(by - 6, by + 1): put(x, y, z, OBSIDIAN if y == by else BLACKSTONE)
        top[x, z] = by
for x in range(cx - 10, cx + 11):
    for y in range(by + 1, by + 3):
        if abs(x - cx) > 2: put(x, y, bz - 6, POLISHED)        # the gate wall, open in the middle
for x in range(cx - 2, cx + 3):
    for y in range(by + 1, by + 7):
        if abs(x - cx) == 2 or y == by + 6: put(x, y, bz + 4, OBSIDIAN)
        else: put(x, y, bz + 4, AMETHYST)                     # the portal surface
for x in (cx - 10, cx + 10):
    for z in (bz - 6, bz + 6): put(x, by + 1, z, LANTERN)
# bridge over the chasm between the bastion and the island
for z in range(bz - 18, bz - 5):
    for x in range(cx - 1, cx + 2):
        if surf(x, z) < by - 1 or surf(x, z) < 0:
            put(x, by, z, PLANK)
    if z % 4 == 0: put(cx - 2, by + 1, z, CHAIN); put(cx + 2, by + 1, z, CHAIN)

np.save(os.path.join(OUT, "warlands_voxels.npy"), V)

# ---------- isometric render
S = 5                                          # pixels per block edge
W_img, H_img = int(N * 2 * S * 0.9) + 80, int(N * S * 0.9 + H * S * 1.2) + 120
img = Image.new("RGB", (W_img, H_img), (12, 10, 20))
d = ImageDraw.Draw(img)
# void sky gradient
for yy in range(H_img):
    t = yy / H_img; d.line([(0, yy), (W_img, yy)], fill=(int(14 + 40 * t), int(10 + 14 * t), int(28 + 30 * t)))
ox, oy = W_img // 2, 60 + H * S
def proj(x, y, z): return (ox + (x - z) * S * 0.9, oy + (x + z) * S * 0.45 - y * S * 1.05)
lit = lambda c, f: tuple(min(255, int(v * f)) for v in c)
xs, ys, zs = np.nonzero(V)
order = np.lexsort((ys, zs + xs))              # back to front, bottom to top
for i in order:
    x, y, z = int(xs[i]), int(ys[i]), int(zs[i]); b = V[x, y, z]
    tc, sc = COLOR[b]
    glow = b in (LAVA, MAGMA, BEACON, SOUL, LANTERN, CRYSTAL)
    above = y + 1 >= H or V[x, y + 1, z] == 0
    right = x + 1 >= N or V[x + 1, y, z] == 0
    front = z + 1 >= N or V[x, y, z + 1] == 0
    if front:
        d.polygon([proj(x, y, z + 1), proj(x + 1, y, z + 1), proj(x + 1, y + 1, z + 1), proj(x, y + 1, z + 1)], fill=lit(sc, 1.0 if glow else 0.72))
    if right:
        d.polygon([proj(x + 1, y, z), proj(x + 1, y, z + 1), proj(x + 1, y + 1, z + 1), proj(x + 1, y + 1, z)], fill=lit(sc, 1.0 if glow else 0.86))
    if above:
        d.polygon([proj(x, y + 1, z), proj(x + 1, y + 1, z), proj(x + 1, y + 1, z + 1), proj(x, y + 1, z + 1)], fill=lit(tc, 1.15 if glow else 1.0))
pts = [proj(x, y, z) for x, y, z in ((0, 0, 0), (N, 0, 0), (0, 0, N), (N, 0, N), (0, H, 0), (N, H, N))]
xs_, ys_ = [int(p[0]) for p in pts], [int(p[1]) for p in pts]
mask = Image.new("L", img.size, 0)
bx = [int(proj(int(a), int(b), int(c))[0]) for a, b, c in zip(*np.nonzero(V))][::50]
by_ = [int(proj(int(a), int(b), int(c))[1]) for a, b, c in zip(*np.nonzero(V))][::50]
img = img.crop((max(0, min(bx) - 40), max(0, min(by_) - 60), min(img.width, max(bx) + 40), min(img.height, max(by_) + 40)))
img.save(os.path.join(OUT, "warlands_iso.png"))

# ---------- labelled top-down plan
P = 6
plan = Image.new("RGB", (N * P + 360, N * P + 40), (14, 12, 22)); pd = ImageDraw.Draw(plan)
for x in range(N):
    for z in range(N):
        col = None
        for y in range(H - 1, -1, -1):
            if V[x, y, z]: col = COLOR[V[x, y, z]][0]; shade = 0.65 + 0.35 * y / H; col = lit(col, shade); break
        if col: pd.rectangle([x * P, z * P, x * P + P - 1, z * P + P - 1], fill=col)
f1, f2 = ImageFont.truetype(FONT, 30), ImageFont.truetype(FONT, 21)
labels = [(cx, cz - 13, "TREASURE NODE", (255, 220, 90)), (cx + 30, cz - 46, "DIAMOND / EMERALD QUARRY", (110, 230, 230)),
          (cx - 34, cz + 12, "DEBRIS PIT", (230, 150, 110)), (cx - 26, cz - 51, "GOLD / AMETHYST GEODES", (240, 210, 90)),
          (cx + 34, cz + 34, "CRYSTAL RIDGE", (210, 170, 255)), (cx + 26, cz + R - 4, "ARRIVAL BASTION (safe)", (190, 160, 255))]
for x, z, text, col in labels:
    w = pd.textlength(text, font=f2); px, py = x * P - w / 2, z * P
    pd.rounded_rectangle([px - 8, py - 6, px + w + 8, py + 26], radius=8, fill=(10, 8, 16))
    pd.text((px, py - 2), text, font=f2, fill=col)
# legend
lx = N * P + 24
pd.text((lx, 24), "THE WARLANDS", font=f1, fill=(255, 90, 70))
legend = ["PvP ON past the bastion gate", "Combat tag: no /warp, /island,", "  /hub while tagged", "Die: drop everything you carry",
          "", "Richest ores in Skyblock,", "  regrow like the zones", "Mobs Lv 25-40", "", "Treasure Node: charges every",
          "  20 min, announced server-wide;", "  hold the platform 30 s to loot", "", "War Spoils: Warlands-only", "  currency for exclusive gear",
          "", "Entry: hub portal (new)", "Island radius ~66 blocks"]
for i, line in enumerate(legend): pd.text((lx, 76 + i * 30), line, font=f2, fill=(220, 214, 230))
plan.save(os.path.join(OUT, "warlands_plan.png"))
print("wrote", os.path.join(OUT, "warlands_iso.png"), os.path.join(OUT, "warlands_plan.png"))
