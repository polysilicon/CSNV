"""Crispy Anarchy 2020 spawn, recreated from the one screenshot we have (no world or schematic of it survived).

python3 build.py <out.schem> [preview.png]
Writes a Sponge v2 schematic (WorldEdit: //schem load spawn2020, //paste). Local axes: x = west->east (left->right
in the screenshot), z = south->north (near->far), y up; the clipboard origin is the middle of the south wall at
ground level, so stand where the spawn gate should be and //paste.

Everything is guesswork past what one high-angle night shot shows: proportions are read off the picture, backs and
interiors are invented, and the lettering on the walls says CRISPY ANARCHY because the original text can't be read.
"""
import gzip, io, math, random, struct, sys

W, L, H = 128, 160, 72          # size: x, z, y
G = 4                            # ground surface level (y of the top ground block)
random.seed(2020)
blocks = {}                      # (x, y, z) -> block state


def put(x, y, z, b):
    if 0 <= x < W and 0 <= y < H and 0 <= z < L:
        blocks[(x, y, z)] = b


def fill(x1, y1, z1, x2, y2, z2, b):
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            for z in range(min(z1, z2), max(z1, z2) + 1):
                put(x, y, z, b)


def box(x1, y1, z1, x2, y2, z2, wall, floor=None):
    """Hollow box: walls, optional floor, open top."""
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            put(x, y, z1, wall); put(x, y, z2, wall)
        for z in range(z1, z2 + 1):
            put(x1, y, z, wall); put(x2, y, z, wall)
    if floor: fill(x1, y1 - 1, z1, x2, y1 - 1, z2, floor)


def get(x, y, z): return blocks.get((x, y, z))


# ------------------------------------------------------------------ ground
fill(0, 0, 0, W - 1, G - 1, L - 1, "minecraft:stone")
for x in range(W):
    for z in range(L):
        # snowy white plaza across the middle and far side, grass at the near end and in the field
        if z < 52: g = "minecraft:grass_block"
        else: g = random.choice(["minecraft:snow_block"] * 5 + ["minecraft:white_concrete_powder"] * 3 + ["minecraft:smooth_quartz"] * 2)
        put(x, G, z, g)

# ------------------------------------------------------------------ walls with glowing lettering on top
WALL_H = 14
for x in range(W):
    for z in range(L):
        if x < 4 or x >= W - 4 or z < 4 or z >= L - 4:
            fill(x, G + 1, z, x, G + WALL_H, z, "minecraft:stone_bricks")
            put(x, G + WALL_H, z, "minecraft:polished_andesite")
# inner face texture
for i in range(0, max(W, L), 3):
    for y in range(G + 2, G + WALL_H, 4):
        for (x, z) in ((i, 4), (4, i), (W - 5, i), (i, L - 5)):
            if get(x, y, z) == "minecraft:stone_bricks": put(x, y, z, "minecraft:cracked_stone_bricks")

FONT = {  # 3x5 letters, rows top->bottom
    "C": ["111", "100", "100", "100", "111"], "R": ["110", "101", "110", "101", "101"], "I": ["111", "010", "010", "010", "111"],
    "S": ["111", "100", "111", "001", "111"], "P": ["110", "101", "110", "100", "100"], "Y": ["101", "101", "010", "010", "010"],
    "A": ["010", "101", "111", "101", "101"], "N": ["101", "111", "111", "111", "101"], "H": ["101", "101", "111", "101", "101"], " ": ["000"] * 5}


# left and right walls (run along z), far wall (along x): letters 3 wide, rows across the 4-wide top
def wall_text(text, axis, fixed_lo, start, step):
    pos = start
    for ch in text:
        for r, row in enumerate(FONT[ch]):
            for c, bit in enumerate(row):
                if bit != "1": continue
                across = fixed_lo + min(3, r * 4 // 5)
                along = pos + c * step
                if axis == "z": put(across, G + WALL_H, along, "minecraft:sea_lantern")
                else: put(along, G + WALL_H, across, "minecraft:sea_lantern")
        pos += 4 * step


for start in (20, 90):
    wall_text("CRISPY ANARCHY", "z", 0, start, 1)
    wall_text("CRISPY ANARCHY", "z", W - 4, start, 1)
wall_text("CRISPY ANARCHY", "x", L - 4, 8, 1)
wall_text("CRISPY ANARCHY", "x", L - 4, 66, 1)
# gate in the south wall
fill(W // 2 - 3, G + 1, 0, W // 2 + 3, G + 7, 3, "minecraft:air")
for x in (W // 2 - 4, W // 2 + 4):
    fill(x, G + 1, 0, x, G + 9, 3, "minecraft:polished_deepslate")
fill(W // 2 - 4, G + 8, 0, W // 2 + 4, G + 9, 3, "minecraft:polished_deepslate")


# ------------------------------------------------------------------ helpers for organic shapes
def disc(cx, cz, rx, rz, y, b, only_if=None):
    for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
        for z in range(int(cz - rz) - 1, int(cz + rz) + 2):
            if ((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2 <= 1:
                if only_if is None or get(x, y, z) in only_if: put(x, y, z, b)


def sphere(cx, cy, cz, r, b, ry=None, hollow=False, top_only=False):
    ry = ry or r
    for x in range(int(cx - r) - 1, int(cx + r) + 2):
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            if top_only and y < cy: continue
            for z in range(int(cz - r) - 1, int(cz + r) + 2):
                d = ((x - cx) / r) ** 2 + ((y - cy) / ry) ** 2 + ((z - cz) / r) ** 2
                if d <= 1 and (not hollow or d >= (1 - 2.2 / r) ** 2): put(x, y, z, b)


def spruce(x, z, h):
    fill(x, G + 1, z, x, G + h, z, "minecraft:spruce_log")
    for y in range(G + 3, G + h + 2):
        r = max(0, int((G + h + 2 - y) / 2.6))
        if (y - G) % 2 == 0: r = max(0, r - 1)
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if abs(dx) + abs(dz) <= r + 1 and get(x + dx, y, z + dz) is None:
                    put(x + dx, y, z + dz, "minecraft:spruce_leaves[persistent=true]")
    put(x, G + h + 2, z, "minecraft:spruce_leaves[persistent=true]")


def pink_tree(x, z, h=6, r=4):
    fill(x, G + 1, z, x, G + h, z, "minecraft:dark_oak_log")
    for dx, dz in ((1, 0), (-1, 1)):
        put(x + dx, G + h - 1, z + dz, "minecraft:dark_oak_log")
    sphere(x, G + h + 1, z, r, "minecraft:pink_wool", ry=r * 0.6)
    for _ in range(14):  # a few hanging bits
        a = random.uniform(0, 6.28); d = random.uniform(1, r)
        put(int(x + math.cos(a) * d), G + h - 1, int(z + math.sin(a) * d), "minecraft:pink_wool")


def dead_tree(x, z):
    h = random.randint(4, 7)
    fill(x, G + 1, z, x, G + h, z, "minecraft:stripped_dark_oak_log")
    for _ in range(3):
        dx, dz = random.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
        y = G + random.randint(3, h)
        put(x + dx, y, z + dz, "minecraft:dark_oak_fence"); put(x + 2 * dx, y + 1, z + 2 * dz, "minecraft:dark_oak_fence")


def gable_roof(x1, z1, x2, z2, y, mat_stairs, ridge_axis="x", overhang=1, slab=None):
    """Simple gable roof of stairs over a rectangle (ridge along ridge_axis)."""
    x1 -= overhang; x2 += overhang; z1 -= overhang; z2 += overhang
    if ridge_axis == "x":
        half = (z2 - z1 + 1) // 2
        for i in range(half + 1):
            for x in range(x1, x2 + 1):
                put(x, y + i, z1 + i, f"{mat_stairs}[facing=south]")
                put(x, y + i, z2 - i, f"{mat_stairs}[facing=north]")
            if z1 + i >= z2 - i: break
    else:
        half = (x2 - x1 + 1) // 2
        for i in range(half + 1):
            for z in range(z1, z2 + 1):
                put(x1 + i, y + i, z, f"{mat_stairs}[facing=east]")
                put(x2 - i, y + i, z, f"{mat_stairs}[facing=west]")
            if x1 + i >= x2 - i: break


def windows(x1, y, z1, x2, z2, every=3, glass="minecraft:glass_pane"):
    for x in range(x1 + 2, x2 - 1, every):
        for z in (z1, z2):
            put(x, y, z, glass); put(x, y + 1, z, glass)
    for z in range(z1 + 2, z2 - 1, every):
        for x in (x1, x2):
            put(x, y, z, glass); put(x, y + 1, z, glass)


# ------------------------------------------------------------------ near left: big wooden hall with a flat roof
hx1, hz1, hx2, hz2, hh = 6, 6, 44, 38, 9
box(hx1, G + 1, hz1, hx2, G + hh, hz2, "minecraft:stone_bricks", floor="minecraft:spruce_planks")
for x in range(hx1, hx2 + 1, 6):
    fill(x, G + 1, hz1, x, G + hh, hz1, "minecraft:dark_oak_log"); fill(x, G + 1, hz2, x, G + hh, hz2, "minecraft:dark_oak_log")
windows(hx1, G + 4, hz1, hx2, hz2, 4)
fill(hx1 - 1, G + hh + 1, hz1 - 1, hx2 + 1, G + hh + 1, hz2 + 1, "minecraft:dark_oak_planks")
for x in range(hx1 - 1, hx2 + 2):
    put(x, G + hh + 2, hz1 - 1, "minecraft:spruce_fence"); put(x, G + hh + 2, hz2 + 1, "minecraft:spruce_fence")
for z in range(hz1 - 1, hz2 + 2):
    put(hx1 - 1, G + hh + 2, z, "minecraft:spruce_fence"); put(hx2 + 1, G + hh + 2, z, "minecraft:spruce_fence")
fill(24, G + 1, hz1, 26, G + 4, hz1, "minecraft:air")   # door

# pixel art billboard standing behind the hall: an original fox face (orange, cream, black), 24 x 24
FOX = [
    "....KK..............KK..",
    "...KOOK............KOOK.",
    "..KOOOOK..........KOOOOK",
    "..KOCCOOK........KOOCCOK",
    "..KOCCCOOKKKKKKKKOOCCCOK",
    "..KOCCCOOOOOOOOOOOOCCCOK",
    "..KOOCOOOOOOOOOOOOOOCOOK",
    "..KOOOOOOOOOOOOOOOOOOOOK",
    ".KOOOOOOOOOOOOOOOOOOOOOK",
    ".KOOOKKOOOOOOOOOOKKOOOOK",
    ".KOOKKKKOOOOOOOOKKKKOOOK",
    ".KOOKWKKOOOOOOOOKWKKOOOK",
    ".KOOOKKOOOOOOOOOOKKOOOOK",
    ".KCCOOOOOOOOOOOOOOOOCCK.",
    ".KCCCCOOOOOOOOOOOOCCCCK.",
    "..KCCCCCCOOOOOOCCCCCCK..",
    "..KCCCCCCCKKKKCCCCCCCK..",
    "...KCCCCCCKKKKCCCCCCK...",
    "....KCCCCCCKKCCCCCCK....",
    ".....KCCCCCCCCCCCCK.....",
    "......KKCCCCCCCCKK......",
    "........KKCCCCKK........",
    "..........KKKK..........",
    "........................"]
PIX = {"K": "minecraft:black_concrete", "O": "minecraft:orange_concrete", "C": "minecraft:white_terracotta", "W": "minecraft:white_concrete"}
bx, bz, by = 12, hz2 + 2, G + hh + 2
for r, row in enumerate(FOX):
    for c, ch in enumerate(row):
        if ch in PIX: put(bx + c, by + (len(FOX) - 1 - r), bz, PIX[ch])
fill(bx + 4, G + 1, bz + 1, bx + 4, by + 2, bz + 1, "minecraft:spruce_log"); fill(bx + 19, G + 1, bz + 1, bx + 19, by + 2, bz + 1, "minecraft:spruce_log")

# ------------------------------------------------------------------ near right: white mansion with a grey roof
mx1, mz1, mx2, mz2, mh = 84, 8, 122, 46, 10
box(mx1, G + 1, mz1, mx2, G + mh, mz2, "minecraft:white_concrete", floor="minecraft:oak_planks")
for (x, z) in ((mx1, mz1), (mx2, mz1), (mx1, mz2), (mx2, mz2)):
    fill(x, G + 1, z, x, G + mh, z, "minecraft:quartz_pillar")
windows(mx1, G + 3, mz1, mx2, mz2, 4, "minecraft:light_gray_stained_glass_pane")
windows(mx1, G + 7, mz1, mx2, mz2, 4, "minecraft:light_gray_stained_glass_pane")
fill(mx1, G + 6, mz1, mx2, G + 6, mz2, "minecraft:white_concrete")
gable_roof(mx1, mz1, mx2, mz2, G + mh + 1, "minecraft:deepslate_tile_stairs", "z", 1)
# second wing toward the field
wx1, wz1, wx2, wz2 = 90, 46, 112, 56
box(wx1, G + 1, wz1, wx2, G + 7, wz2, "minecraft:white_concrete", floor="minecraft:oak_planks")
windows(wx1, G + 3, wz1, wx2, wz2, 4, "minecraft:light_gray_stained_glass_pane")
gable_roof(wx1, wz1, wx2, wz2, G + 8, "minecraft:deepslate_tile_stairs", "x", 1)
# red flower beds and steps along the mansion front
for z in range(mz1 + 2, mz2 - 1):
    put(mx1 - 2, G + 1, z, random.choice(["minecraft:poppy", "minecraft:red_tulip"]))
fill(mx1 - 1, G + 1, 20, mx1 - 1, G + 1, 26, "minecraft:quartz_stairs[facing=east]")

# ------------------------------------------------------------------ near middle: grass slope with flowers and lights
for x in range(46, 82):
    for z in range(4, 52):
        if get(x, G + 1, z) is None and random.random() < 0.18:
            put(x, G + 1, z, random.choice(["minecraft:poppy", "minecraft:dandelion", "minecraft:oxeye_daisy", "minecraft:azure_bluet", "minecraft:short_grass"]))
        if random.random() < 0.012: put(x, G, z, "minecraft:glowstone")
for z in range(4, 52):   # path from the gate
    for x in range(W // 2 - 2, W // 2 + 3):
        put(x, G, z, "minecraft:dirt_path")
        if get(x, G + 1, z) not in (None, "minecraft:air") and z > 3: blocks.pop((x, G + 1, z), None)

# ------------------------------------------------------------------ pond with a dock, glass dome and pumpkin
pcx, pcz = 40, 72
for x in range(10, 72):
    for z in range(50, 96):
        d = ((x - pcx) / 26) ** 2 + ((z - pcz) / 17) ** 2 + 0.15 * math.sin(x * 0.5) * math.cos(z * 0.4)
        if d <= 1:
            depth = 1 + int(3 * (1 - d))
            for y in range(G - depth + 1, G + 1): put(x, y, z, "minecraft:water")
            put(x, G - depth, z, "minecraft:sand" if d > 0.6 else "minecraft:gravel")
            for y in range(G + 1, G + 4): blocks.pop((x, y, z), None)
        elif d <= 1.18:
            put(x, G, z, "minecraft:sand" if random.random() < 0.7 else "minecraft:white_concrete_powder")
for x in range(22, 36):   # dock
    put(x, G, 64, "minecraft:spruce_planks"); put(x, G, 65, "minecraft:spruce_planks")
    if x % 4 == 0: put(x, G + 1, 63, "minecraft:spruce_fence"); put(x, G + 2, 63, "minecraft:lantern")
fill(18, G, 60, 23, G, 68, "minecraft:spruce_planks")
# glass dome at the pond's east edge, a little garden inside
sphere(58, G, 74, 9, "minecraft:light_blue_stained_glass", hollow=True, top_only=True)
disc(58, 74, 8, 8, G, "minecraft:moss_block")
for _ in range(10): put(58 + random.randint(-5, 5), G + 1, 74 + random.randint(-5, 5), "minecraft:azalea")
put(58, G + 1, 74, "minecraft:sea_lantern")
# pumpkin: a squashed orange sphere with ribs and a stem
pcx2, pcz2, pr = 66, 60, 7
for x in range(pcx2 - pr - 1, pcx2 + pr + 2):
    for y in range(G + 1, G + 12):
        for z in range(pcz2 - pr - 1, pcz2 + pr + 2):
            d = ((x - pcx2) / pr) ** 2 + ((y - (G + 5)) / 5.2) ** 2 + ((z - pcz2) / pr) ** 2
            if d <= 1:
                rib = (math.atan2(z - pcz2, x - pcx2) * 8 / math.pi) % 2 < 0.35
                put(x, y, z, "minecraft:orange_terracotta" if rib else "minecraft:orange_concrete")
fill(pcx2, G + 10, pcz2, pcx2, G + 12, pcz2, "minecraft:green_concrete"); put(pcx2 + 1, G + 12, pcz2, "minecraft:green_concrete")

# ------------------------------------------------------------------ wooden hut next to the pumpkin
box(70, G + 1, 66, 82, G + 7, 80, "minecraft:spruce_planks", floor="minecraft:spruce_planks")
for (x, z) in ((70, 66), (82, 66), (70, 80), (82, 80)): fill(x, G + 1, z, x, G + 7, z, "minecraft:spruce_log")
windows(70, G + 3, 66, 82, 80, 4)
gable_roof(70, 66, 82, 80, G + 8, "minecraft:spruce_stairs", "z", 1)
fill(76, G + 1, 66, 76, G + 3, 66, "minecraft:air")

# ------------------------------------------------------------------ right: fenced red flower field with dead trees
fx1, fz1, fx2, fz2 = 84, 58, 120, 104
for x in range(fx1, fx2 + 1):
    for z in range(fz1, fz2 + 1):
        put(x, G, z, "minecraft:grass_block")
        if random.random() < 0.55: put(x, G + 1, z, random.choice(["minecraft:poppy"] * 4 + ["minecraft:red_tulip", "minecraft:short_grass"]))
for x in range(fx1, fx2 + 1): put(x, G + 1, fz1, "minecraft:spruce_fence"); put(x, G + 1, fz2, "minecraft:spruce_fence")
for z in range(fz1, fz2 + 1): put(fx1, G + 1, z, "minecraft:spruce_fence"); put(fx2, G + 1, z, "minecraft:spruce_fence")
fill(fx1, G + 1, 80, fx1, G + 2, 82, "minecraft:air")   # field gate
for (x, z) in ((92, 66), (100, 72), (108, 64), (96, 86), (112, 92), (104, 98), (116, 76)): dead_tree(x, z)
# a crooked dirt track through the field and on to the saucer tower
x = 86
for z in range(fz1, 124):
    x += random.choice((-1, 0, 0, 1)); x = max(fx1 + 2, min(fx2 - 2, x))
    for dx in (0, 1): put(x + dx, G, z, "minecraft:coarse_dirt" if z <= fz2 else "minecraft:black_concrete"); blocks.pop((x + dx, G + 1, z), None)

# ------------------------------------------------------------------ middle: small shops and black roads
for z in range(84, 150):   # main road north
    for x in range(62, 65): put(x, G, z, "minecraft:black_concrete")
for x in range(44, 84):   # cross road
    for z in range(108, 111): put(x, G, z, "minecraft:black_concrete")
SHOPS = [(46, 86, 54, 94, "minecraft:oak_planks", "minecraft:oak_stairs"), (46, 98, 56, 106, "minecraft:birch_planks", "minecraft:spruce_stairs"),
         (68, 112, 76, 120, "minecraft:spruce_planks", "minecraft:dark_oak_stairs"), (50, 112, 58, 120, "minecraft:stripped_oak_log", "minecraft:spruce_stairs")]
for x1, z1, x2, z2, wall, roof in SHOPS:
    box(x1, G + 1, z1, x2, G + 5, z2, wall, floor="minecraft:spruce_planks")
    windows(x1, G + 2, z1, x2, z2, 3)
    gable_roof(x1, z1, x2, z2, G + 6, roof, "x", 1)
    fill((x1 + x2) // 2, G + 1, z1, (x1 + x2) // 2, G + 3, z1, "minecraft:air")
# market stall awnings along the road
for i, z in enumerate(range(86, 104, 6)):
    c = ("red", "white", "red")[i % 3]
    fill(66, G + 4, z, 68, G + 4, z + 3, f"minecraft:{c}_wool")
    for (x, zz) in ((66, z), (68, z), (66, z + 3), (68, z + 3)): fill(x, G + 1, zz, x, G + 3, zz, "minecraft:spruce_fence")

# ------------------------------------------------------------------ the red nether-brick spire
nx1, nz1, nx2, nz2 = 70, 90, 82, 102
box(nx1, G + 1, nz1, nx2, G + 14, nz2, "minecraft:red_nether_bricks", floor="minecraft:nether_bricks")
for (x, z) in ((nx1, nz1), (nx2, nz1), (nx1, nz2), (nx2, nz2), (76, nz1), (76, nz2), (nx1, 96), (nx2, 96)):
    fill(x, G + 1, z, x, G + 17 + random.randint(0, 4), z, "minecraft:nether_bricks")
for i in range(7):   # stepped spiky roof
    fill(nx1 + i, G + 15 + i, nz1 + i, nx2 - i, G + 15 + i, nz2 - i, "minecraft:red_nether_bricks")
for _ in range(26):
    x = random.randint(nx1, nx2); z = random.randint(nz1, nz2)
    top = max(y for (xx, y, zz) in blocks if xx == x and zz == z)
    fill(x, top + 1, z, x, top + random.randint(1, 4), z, "minecraft:red_nether_brick_wall")
fill(76, G + 1, nz1, 76, G + 4, nz1, "minecraft:air")
for z in range(nz1 + 2, nz2 - 1, 3): put(nx1, G + 6, z, "minecraft:red_stained_glass_pane"); put(nx2, G + 6, z, "minecraft:red_stained_glass_pane")
put(76, G + 3, nz1 - 1, "minecraft:shroomlight")

# ------------------------------------------------------------------ the white tower with the red ring and beacon
tcx, tcz, th = 66, 132, 42
for y in range(G + 1, G + th + 1):
    r = 5 if y < G + 30 else 4
    for x in range(tcx - r, tcx + r + 1):
        for z in range(tcz - r, tcz + r + 1):
            edge = x in (tcx - r, tcx + r) or z in (tcz - r, tcz + r)
            if not edge: continue
            corner = x in (tcx - r, tcx + r) and z in (tcz - r, tcz + r)
            if corner: put(x, y, z, "minecraft:smooth_sandstone")
            elif (y - G) % 6 in (0, 1): put(x, y, z, "minecraft:cut_sandstone")
            else: put(x, y, z, "minecraft:white_stained_glass" if (x + z) % 2 else "minecraft:sandstone_wall")
    if (y - G) % 6 == 0: fill(tcx - r + 1, y, tcz - r + 1, tcx + r - 1, y, tcz + r - 1, "minecraft:smooth_sandstone")
fill(tcx - 6, G + 1, tcz - 6, tcx + 6, G + 3, tcz + 6, "minecraft:smooth_sandstone")   # plinth
box(tcx - 6, G + 4, tcz - 6, tcx + 6, G + 4, tcz + 6, "minecraft:sandstone_wall")
for y in range(G + 5, G + 16):   # vines on the plinth face, like the screenshot's green streaks
    for x in range(tcx - 5, tcx + 6, 2):
        if random.random() < 0.4: put(x, y, tcz - 6, "minecraft:vine[south=true]")
top = G + th
fill(tcx - 5, top + 1, tcz - 5, tcx + 5, top + 1, tcz + 5, "minecraft:smooth_quartz")
box(tcx - 5, top + 2, tcz - 5, tcx + 5, top + 2, tcz + 5, "minecraft:quartz_slab")
# beacon with a red beam
fill(tcx - 1, top + 1, tcz - 1, tcx + 1, top + 1, tcz + 1, "minecraft:iron_block")
put(tcx, top + 2, tcz, "minecraft:beacon"); put(tcx, top + 3, tcz, "minecraft:red_stained_glass")
# the red ring floating above it
ry, R = top + 9, 12
for a in range(0, 360, 2):
    x = tcx + R * math.cos(math.radians(a)); z = tcz + R * math.sin(math.radians(a))
    for w in (-0.6, 0, 0.6):
        put(round(x + w * math.cos(math.radians(a))), ry, round(z + w * math.sin(math.radians(a))), "minecraft:red_concrete")
for a in range(0, 360, 45):   # spokes
    for d in range(3, R):
        put(round(tcx + d * math.cos(math.radians(a))), ry, round(tcz + d * math.sin(math.radians(a))), "minecraft:red_nether_bricks")
put(tcx, ry, tcz, "minecraft:redstone_block")

# ------------------------------------------------------------------ the dark tower with a saucer on top
scx, scz, sh = 102, 128, 36
for y in range(G + 1, G + sh + 1):
    for x in range(scx - 5, scx + 6):
        for z in range(scz - 5, scz + 6):
            d = math.hypot(x - scx, z - scz)
            if 3.6 <= d <= 4.6: put(x, y, z, "minecraft:gray_concrete" if (y + int(math.degrees(math.atan2(z - scz, x - scx)) // 30)) % 5 else "minecraft:light_gray_stained_glass")
sy = G + sh + 1
disc(scx, scz, 12, 12, sy, "minecraft:smooth_stone_slab[type=top]")
disc(scx, scz, 10, 10, sy + 1, "minecraft:white_concrete")
disc(scx, scz, 8, 8, sy + 2, "minecraft:light_gray_stained_glass")
disc(scx, scz, 6, 6, sy + 3, "minecraft:black_concrete")
disc(scx, scz, 4, 4, sy + 4, "minecraft:gray_concrete")
for a in range(0, 360, 15):
    put(round(scx + 12 * math.cos(math.radians(a))), sy + 1, round(scz + 12 * math.sin(math.radians(a))), "minecraft:sea_lantern")
fill(scx, sy + 5, scz, scx, sy + 8, scz, "minecraft:lightning_rod")
fill(scx - 1, G + 1, scz - 5, scx + 1, G + 3, scz - 5, "minecraft:air")

# ------------------------------------------------------------------ far left: Japanese houses, pink trees, spruces
def japanese_house(x1, z1, x2, z2, h=5):
    box(x1, G + 1, z1, x2, G + h, z2, "minecraft:white_terracotta", floor="minecraft:spruce_planks")
    for x in range(x1, x2 + 1, 3):
        fill(x, G + 1, z1, x, G + h, z1, "minecraft:dark_oak_log"); fill(x, G + 1, z2, x, G + h, z2, "minecraft:dark_oak_log")
    for z in range(z1, z2 + 1, 3):
        fill(x1, G + 1, z, x1, G + h, z, "minecraft:dark_oak_log"); fill(x2, G + 1, z, x2, G + h, z, "minecraft:dark_oak_log")
    fill(x1, G + h, z1, x2, G + h, z2, "minecraft:dark_oak_planks")
    gable_roof(x1, z1, x2, z2, G + h + 1, "minecraft:deepslate_brick_stairs", "x", 2)
    for x in (x1 - 2, x2 + 2):   # upturned eaves
        put(x, G + h + 2, z1 - 2, "minecraft:deepslate_brick_wall"); put(x, G + h + 2, z2 + 2, "minecraft:deepslate_brick_wall")
    windows(x1, G + 2, z1, x2, z2, 3, "minecraft:white_stained_glass_pane")
    fill((x1 + x2) // 2, G + 1, z1, (x1 + x2) // 2, G + 3, z1, "minecraft:air")


japanese_house(10, 104, 26, 116)
japanese_house(30, 118, 44, 130, 6)
japanese_house(12, 128, 24, 140)
japanese_house(28, 136, 42, 150, 7)
for (x, z) in ((8, 120), (27, 124), (46, 142), (20, 146), (8, 96), (44, 116)): pink_tree(x, z, random.randint(5, 7), random.randint(3, 5))
for (x, z) in ((22, 44), (28, 48), (34, 44), (16, 52), (40, 50), (6, 48), (12, 90), (46, 98)): spruce(x, z, random.randint(13, 19))
# teal-roofed pavilion on the left, by the pond
box(6, G + 1, 56, 20, G + 5, 74, "minecraft:dark_prismarine", floor="minecraft:prismarine_bricks")
windows(6, G + 2, 56, 20, 74, 3, "minecraft:cyan_stained_glass_pane")
gable_roof(6, 56, 20, 74, G + 6, "minecraft:prismarine_brick_stairs", "z", 1)
# farm plots
for x in range(28, 46):
    for z in range(84, 100):
        if x % 5 == 0: put(x, G, z, "minecraft:water")
        else: put(x, G, z, "minecraft:farmland[moisture=7]"); put(x, G + 1, z, "minecraft:wheat[age=7]")
for x in range(27, 47): put(x, G + 1, 83, "minecraft:oak_fence"); put(x, G + 1, 100, "minecraft:oak_fence")
# lanterns along the roads
for z in range(86, 150, 8):
    for x in (60, 66): fill(x, G + 1, z, x, G + 3, z, "minecraft:spruce_fence"); put(x, G + 4, z, "minecraft:lantern")


# ------------------------------------------------------------------ write the schematic (Sponge v2)
def nbt_str(s): b = s.encode(); return struct.pack(">H", len(b)) + b
def tag(t, name, payload): return bytes([t]) + nbt_str(name) + payload


palette = {"minecraft:air": 0}
data = bytearray()
for y in range(H):
    for z in range(L):
        for x in range(W):
            b = blocks.get((x, y, z), "minecraft:air")
            i = palette.setdefault(b, len(palette))
            while True:
                byte = i & 0x7F; i >>= 7
                data.append(byte | (0x80 if i else 0))
                if not i: break
pal = b"".join(tag(3, k, struct.pack(">i", v)) for k, v in palette.items()) + b"\x00"
meta = tag(3, "WEOffsetX", struct.pack(">i", -(W // 2))) + tag(3, "WEOffsetY", struct.pack(">i", -(G + 1))) + tag(3, "WEOffsetZ", struct.pack(">i", 0)) + b"\x00"
root = (tag(3, "Version", struct.pack(">i", 2)) + tag(3, "DataVersion", struct.pack(">i", 3953))
        + tag(2, "Width", struct.pack(">h", W)) + tag(2, "Height", struct.pack(">h", H)) + tag(2, "Length", struct.pack(">h", L))
        + tag(11, "Offset", struct.pack(">i3i", 3, 0, 0, 0)) + tag(3, "PaletteMax", struct.pack(">i", len(palette)))
        + tag(10, "Palette", pal) + tag(10, "Metadata", meta) + tag(7, "BlockData", struct.pack(">i", len(data)) + bytes(data)) + b"\x00")
out = sys.argv[1] if len(sys.argv) > 1 else "spawn2020.schem"
with gzip.open(out, "wb") as f: f.write(bytes([10]) + nbt_str("Schematic") + root)
print(f"wrote {out}: {W}x{H}x{L}, {len([1 for b in blocks.values() if b != 'minecraft:air'])} blocks, {len(palette)} block types")
