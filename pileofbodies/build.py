#!/usr/bin/env python3
"""Pile of Bodies (CrispyAnarchy remake of SethBling's 2013 map) for Minecraft 26.2.

    python3 build.py <skins dir> <out datapack dir>

Turns each skin in <skins dir> (PNG + index.json: name -> {slim}) into a giant statue of the player model, two blocks
per skin pixel, with the outer layers (hat, jacket, sleeves, trousers) as a one-block shell. Surface blocks are the
closest survival block to the pixel colour (logs, planks, stone, dirt, terracotta, wool, pumpkins, mushroom blocks,
ice for water, leaves for saplings...). The insides are stone with ore clusters and the odd lava pocket. The statues are
dropped one by one onto a growing heap in a void world (flat, one air layer, plains biome, so mobs spawn on the pile).
One torso hides an End portal room. Every head gets a name sign, and a starter chest sits by the spawn on top.

Output: a datapack with function pob:build (run it once in a fresh void world; see README.md).
"""
import json, math, os, random, sys
from PIL import Image

SKINS, OUT = sys.argv[1], sys.argv[2]
NS, S = "pob", 2                  # scale: blocks per skin pixel
FLOOR = 64                        # lowest block of the pile
SPREAD0, SPREAD_PER, SETTLE, CENTRE_PULL = 12, 3, 6, 0.45   # heap width growth per body, sink depth, pull to the middle
rnd = random.Random(2013)

# ------------------------------------------------------------------ palette: survival block -> average texture colour
PALETTE = {
    "oak_log": (109, 85, 50), "spruce_log": (58, 37, 16), "birch_log": (216, 215, 210), "jungle_log": (85, 67, 25),
    "acacia_log": (103, 96, 86), "dark_oak_log": (60, 46, 26), "cherry_log": (54, 33, 44), "mangrove_log": (84, 67, 41),
    "oak_planks": (162, 130, 78), "spruce_planks": (114, 84, 48), "birch_planks": (192, 175, 121), "jungle_planks": (160, 115, 80),
    "acacia_planks": (168, 90, 50), "dark_oak_planks": (66, 43, 20), "cherry_planks": (226, 178, 172),
    "stone": (125, 125, 125), "cobblestone": (127, 127, 127), "andesite": (136, 136, 136), "diorite": (188, 182, 183),
    "granite": (149, 103, 85), "gravel": (131, 127, 126), "dirt": (134, 96, 67), "coarse_dirt": (119, 85, 59),
    "sand": (219, 207, 163), "sandstone": (216, 203, 155), "red_sand": (190, 102, 33), "clay": (160, 166, 179),
    "snow_block": (249, 254, 254), "ice": (145, 183, 253), "moss_block": (89, 109, 45), "grass_block": (127, 178, 56),
    "oak_leaves[persistent=true]": (60, 95, 30), "pumpkin": (198, 118, 24), "melon": (111, 145, 30), "hay_block": (166, 136, 38),
    "red_mushroom_block": (200, 46, 45), "brown_mushroom_block": (149, 111, 81), "mushroom_stem": (203, 196, 185),
    "bone_block": (229, 225, 207), "blackstone": (42, 36, 41), "deepslate": (80, 80, 82),
    "terracotta": (152, 94, 67), "white_terracotta": (209, 178, 161), "orange_terracotta": (161, 83, 37),
    "magenta_terracotta": (149, 88, 108), "light_blue_terracotta": (113, 108, 137), "yellow_terracotta": (186, 133, 35),
    "lime_terracotta": (103, 117, 52), "pink_terracotta": (161, 78, 78), "gray_terracotta": (57, 42, 35),
    "light_gray_terracotta": (135, 107, 98), "cyan_terracotta": (86, 91, 91), "purple_terracotta": (118, 70, 86),
    "blue_terracotta": (74, 59, 91), "brown_terracotta": (77, 51, 35), "green_terracotta": (76, 83, 42),
    "red_terracotta": (143, 61, 46), "black_terracotta": (37, 22, 16),
}
WOOL = {"white_wool": (233, 236, 236), "light_gray_wool": (142, 142, 134), "gray_wool": (62, 68, 71), "black_wool": (20, 21, 25),
        "brown_wool": (114, 71, 40), "red_wool": (160, 39, 34), "orange_wool": (240, 118, 19), "yellow_wool": (248, 197, 39),
        "lime_wool": (112, 185, 25), "green_wool": (84, 109, 27), "cyan_wool": (21, 137, 145), "light_blue_wool": (58, 175, 217),
        "blue_wool": (53, 57, 157), "purple_wool": (121, 42, 172), "magenta_wool": (189, 68, 179), "pink_wool": (237, 141, 172)}
COLOURS = [(b, c, 1.0) for b, c in PALETTE.items()] + [(b, c, 1.3) for b, c in WOOL.items()]   # wool only for strong colours
_cache = {}
def block_for(rgb):
    if rgb in _cache: return _cache[rgb]
    r, g, b = rgb
    best = min(COLOURS, key=lambda e: e[2] * ((2 + (r + e[1][0]) / 512) * (r - e[1][0]) ** 2 + 4 * (g - e[1][1]) ** 2
                                               + (3 - (r + e[1][0]) / 512) * (b - e[1][2]) ** 2))[0]
    _cache[rgb] = best
    return best

# ------------------------------------------------------------------ player model (pixel units; x to the viewer's right, y up, front at +z)
def parts(slim):
    aw = 3 if slim else 4
    #       name, x0, y0, z0, w, h, d, base uv, overlay uv (64x64 only)
    return [("head", 0, 24, -2, 8, 8, 8, (0, 0), (32, 0)),
            ("body", 0, 12, 0, 8, 12, 4, (16, 16), (16, 32)),
            ("rarm", -aw, 12, 0, aw, 12, 4, (40, 16), (40, 32)),
            ("larm", 8, 12, 0, aw, 12, 4, (32, 48), (48, 48)),
            ("rleg", 0, 0, 0, 4, 12, 4, (0, 16), (0, 32)),
            ("lleg", 4, 0, 0, 4, 12, 4, (16, 48), (0, 48))]

def face_pixel(img, uv, w, h, d, face, i, j, k):
    """Texture pixel for box face `face` at in-box pixel coords (i along x, j along y from the top, k along z from the back)."""
    u, v = uv
    if face == "front":  return img.getpixel((u + d + i, v + d + j))
    if face == "back":   return img.getpixel((u + 2 * d + w + (w - 1 - i), v + d + j))
    if face == "right":  return img.getpixel((u + k, v + d + j))                      # the -x side
    if face == "left":   return img.getpixel((u + d + w + (d - 1 - k), v + d + j))    # the +x side
    if face == "top":    return img.getpixel((u + d + i, v + k))
    if face == "bottom": return img.getpixel((u + d + w + i, v + (d - 1 - k)))

def statue(name, slim):
    """Voxels {(x, y, z): block} in model space, blocks (scaled), for one skin."""
    img = Image.open(os.path.join(SKINS, name + ".png")).convert("RGBA")
    modern = img.size[1] == 64
    if not modern:   # old 64x32 skins: the left limbs mirror the right ones
        new = Image.new("RGBA", (64, 64)); new.paste(img, (0, 0))
        for (sx, sy), (dx, dy) in (((0, 16), (16, 48)), ((40, 16), (32, 48))):
            new.paste(img.crop((sx, sy, sx + 16, sy + 16)).transpose(Image.FLIP_LEFT_RIGHT), (dx, dy))
        img = new
    vox, shell = {}, {}
    for (pn, x0, y0, z0, w, h, d, uv, ouv) in parts(slim):
        X0, Y0, Z0, W, H, D = x0 * S, y0 * S, z0 * S, w * S, h * S, d * S
        for X in range(W):
            for Y in range(H):
                for Z in range(D):
                    i, j, k = X // S, (H - 1 - Y) // S, Z // S
                    faces = [("front", Z == D - 1), ("back", Z == 0), ("right", X == 0), ("left", X == W - 1),
                             ("top", Y == H - 1), ("bottom", Y == 0)]
                    on = [f for f, hit in faces if hit]
                    if on:
                        px = face_pixel(img, uv, w, h, d, on[0], i, j, k)
                        vox[(X0 + X, Y0 + Y, Z0 + Z)] = block_for(px[:3]) if px[3] > 0 else "stone"
                    else:
                        vox[(X0 + X, Y0 + Y, Z0 + Z)] = None   # interior, filled later
        if not modern and pn != "head": continue
        # outer layer: a one-block shell just outside each face, where the overlay pixel is opaque
        for face, axis in (("front", 2), ("back", 2), ("right", 0), ("left", 0), ("top", 1), ("bottom", 1)):
            for A in range(W if axis != 0 else D):
                for B in range(H if axis != 1 else D):
                    if axis == 2:   X, Y, Z = A, B, (D if face == "front" else -1)
                    elif axis == 0: X, Y, Z = (-1 if face == "right" else W), B, A
                    else:           X, Y, Z = A, (H if face == "top" else -1), B
                    i, j, k = min(max(X, 0), W - 1) // S, (H - 1 - min(max(Y, 0), H - 1)) // S, min(max(Z, 0), D - 1) // S
                    px = face_pixel(img, ouv, w, h, d, face, i, j, k)
                    if px[3] >= 128: shell[(X0 + X, Y0 + Y, Z0 + Z)] = block_for(px[:3])
    for p, b in shell.items(): vox.setdefault(p, b)
    return vox

# ------------------------------------------------------------------ insides: stone with ore clusters and lava pockets
ORES = [("coal_ore", 0.010), ("iron_ore", 0.007), ("copper_ore", 0.005), ("redstone_ore", 0.0025), ("lapis_ore", 0.0018),
        ("gold_ore", 0.0016), ("diamond_ore", 0.0005), ("emerald_ore", 0.0002)]
def fill_insides(vox):
    inside = [p for p, b in vox.items() if b is None]
    inside_set = set(inside)
    for p in inside: vox[p] = rnd.choices(["stone", "andesite", "tuff", "gravel"], [86, 6, 5, 3])[0]
    for ore, rate in ORES:
        for _ in range(max(1, round(len(inside) * rate))):
            p = rnd.choice(inside); size = rnd.randint(2, 6)
            for _ in range(size):
                if vox.get(p) in ("stone", "andesite", "tuff", "gravel"): vox[p] = ore
                q = (p[0] + rnd.choice((-1, 0, 1)), p[1] + rnd.choice((-1, 0, 1)), p[2] + rnd.choice((-1, 0, 1)))
                if q in inside_set: p = q
    if rnd.random() < 0.5:   # a small lava pocket deep inside
        p = rnd.choice(inside)
        for dx in range(2):
            for dz in range(2):
                q = (p[0] + dx, p[1], p[2] + dz)
                if vox.get(q) in ("stone", "andesite", "tuff"): vox[q] = "lava"

# ------------------------------------------------------------------ poses and the pile
def rotations():
    """Axis-aligned rotations that lay the body down (its height axis ends up horizontal)."""
    out = []
    import itertools
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            m = [[0] * 3 for _ in range(3)]
            for r in range(3): m[r][perm[r]] = signs[r]
            det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                   + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
            if det == 1 and m[1][1] == 0: out.append(m)
    return out
ROTS = rotations()

def rotate(vox, m):
    out = {}
    for (x, y, z), b in vox.items():
        out[(m[0][0] * x + m[0][1] * y + m[0][2] * z, m[1][0] * x + m[1][1] * y + m[1][2] * z, m[2][0] * x + m[2][1] * y + m[2][2] * z)] = b
    mn = [min(p[a] for p in out) for a in range(3)]
    return {(x - mn[0], y - mn[1], z - mn[2]): b for (x, y, z), b in out.items()}

world, top = {}, {}           # placed blocks; heightmap of the pile
def drop(vox, spread):
    """Drop a posed statue onto the heap at the best of a few random spots (lowest landing fills gaps)."""
    w = max(p[0] for p in vox) + 1; d = max(p[2] for p in vox) + 1
    low = {}
    for (x, y, z) in vox: low[(x, z)] = min(low.get((x, z), 999), y)
    best = None
    for _ in range(40):
        a, r = rnd.uniform(0, 2 * math.pi), rnd.uniform(0, spread)
        ox, oz = int(r * math.cos(a)) - w // 2, int(r * math.sin(a)) - d // 2
        Y = max(top.get((ox + x, oz + z), FLOOR - 1) - ly for (x, z), ly in low.items()) + 1
        Y = max(FLOOR, Y - SETTLE)     # settle into what is below, like a real heap
        score = Y + CENTRE_PULL * r          # low spots near the middle win, so it heaps into a mound
        if best is None or score < best[0]: best = (score, Y, ox, oz)
    _, Y, ox, oz = best
    placed = {}
    for (x, y, z), b in vox.items():
        p = (ox + x, Y + y, oz + z)
        if p not in world:
            world[p] = b; placed[p] = b
            top[(p[0], p[2])] = max(top.get((p[0], p[2]), FLOOR - 1), p[1])
    return placed, (ox, Y, oz)

# ------------------------------------------------------------------ build
index = json.load(open(os.path.join(SKINS, "index.json")))
names = list(index); rnd.shuffle(names)
heads, torsos = {}, {}
for n, name in enumerate(names):
    vox = statue(name, index[name]["slim"])
    fill_insides(vox)
    m = rnd.choice(ROTS)
    rot = lambda q: (m[0][0] * q[0] + m[0][1] * q[1] + m[0][2] * q[2], m[1][0] * q[0] + m[1][1] * q[1] + m[1][2] * q[2],
                     m[2][0] * q[0] + m[2][1] * q[1] + m[2][2] * q[2])
    raw = {rot(q): b for q, b in vox.items()}
    mn = [min(q[a] for q in raw) for a in range(3)]
    norm = lambda q: (q[0] - mn[0], q[1] - mn[1], q[2] - mn[2])
    posed = {norm(q): b for q, b in raw.items()}
    placed, (ox, oy, oz) = drop(posed, spread=SPREAD0 + SPREAD_PER * n)
    to_world = lambda q: (lambda r: (r[0] + ox, r[1] + oy, r[2] + oz))(norm(rot(q)))
    heads[name] = to_world((4 * S, 28 * S, 2 * S))      # centre of the head
    torsos[name] = to_world((4 * S, 18 * S, 2 * S))     # centre of the torso
    print(f"{name:16} {len(posed):6} voxels, {len(placed):6} placed at y {oy}")

# End portal room inside the torso of a famous body (the void world has no strongholds)
host = next((n for n in names if n == "SethBling"), names[0])
cx, cy, cz = torsos[host]
for x in range(cx - 3, cx + 4):
    for z in range(cz - 3, cz + 4):
        world[(x, cy - 1, z)] = "stone_bricks"
        for y in range(cy, cy + 3): world[(x, y, z)] = "air"
        world[(x, cy + 3, z)] = "stone_bricks"
for i in range(-1, 2):
    world[(cx + i, cy, cz - 2)] = "end_portal_frame[facing=south]"
    world[(cx + i, cy, cz + 2)] = "end_portal_frame[facing=north]"
    world[(cx - 2, cy, cz + i)] = "end_portal_frame[facing=east]"
    world[(cx + 2, cy, cz + i)] = "end_portal_frame[facing=west]"
world[(cx, cy + 2, cz)] = "glowstone"   # a lamp, so it isn't pitch black
print("End portal room inside", host, "at", (cx, cy, cz))

# ------------------------------------------------------------------ write the datapack
def w(path, text):
    full = os.path.join(OUT, path); os.makedirs(os.path.dirname(full), exist_ok=True); open(full, "w").write(text)
w("pack.mcmeta", json.dumps({"pack": {"description": "Pile of Bodies builder (CrispyAnarchy)", "pack_format": 94,
                                      "supported_formats": [48, 200], "min_format": [48, 0], "max_format": [200, 0]}}))
xs = [p[0] for p in world]; zs = [p[2] for p in world]; ys = [p[1] for p in world]
bounds = (min(xs), min(zs), max(xs), max(zs))
# one function per 16-block slab of x, each block run along z as one fill
by_slab = {}
for (x, y, z), b in world.items(): by_slab.setdefault(x // 16, {}).setdefault((x, y), []).append((z, b))
parts_ = []
for slab, cols in sorted(by_slab.items()):
    lines = []
    for (x, y), zl in sorted(cols.items()):
        zl.sort(); start, prev, cur = zl[0][0], zl[0][0], zl[0][1]
        for z, b in zl[1:] + [(None, None)]:
            if z is not None and z == prev + 1 and b == cur: prev = z; continue
            ns = "" if ":" in cur else "minecraft:"
            lines.append(f"setblock {x} {y} {start} {ns}{cur}" if start == prev else f"fill {x} {y} {start} {x} {y} {prev} {ns}{cur}")
            if z is not None: start, prev, cur = z, z, b
    name = f"slab_{slab - min(by_slab)}"
    w(f"data/{NS}/function/{name}.mcfunction", "\n".join(lines) + "\n"); parts_.append(name)
# spawn: the highest point of the pile, with a starter chest and a sign
sx, sz = max(top, key=lambda k: top[k]); sy = top[(sx, sz)] + 1
signs = []
for name, (hx, hy, hz) in heads.items():
    ty = top.get((hx, hz), hy) + 1
    signs.append(f'setblock {hx} {ty} {hz} minecraft:oak_sign[rotation={rnd.randint(0, 15)}]'
                 f'{{front_text:{{messages:["","{name}","",""]}},back_text:{{messages:["","{name}","",""]}}}}')
chest = ('setblock {x} {y} {z} minecraft:chest[facing=north]{{Items:['
         '{{Slot:0b,id:"minecraft:oak_sapling",count:2}},{{Slot:1b,id:"minecraft:wheat_seeds",count:4}},'
         '{{Slot:2b,id:"minecraft:sugar_cane",count:2}},{{Slot:3b,id:"minecraft:bone_meal",count:4}},'
         '{{Slot:4b,id:"minecraft:water_bucket",count:1}},{{Slot:5b,id:"minecraft:torch",count:8}},'
         '{{Slot:13b,id:"minecraft:written_book",count:1,components:{{"minecraft:written_book_content":{{title:"Pile of Bodies",author:"CrispyAnarchy",'
         'pages:["Welcome to Pile of Bodies!\\n\\nA remake of SethBling\'s 2013 survival map for 26.2.\\n\\nEverything you need is in the bodies: '
         'wood, stone, dirt, wool, food blocks, and ores inside.","Goals:\\n- Build a farm\\n- Find every ore\\n- Reach the Nether\\n- Find the hidden '
         'End portal (inside a famous torso)\\n- Beat the dragon\\n\\nPlay more at crispyanarchy.net"]}}}}}}]}}').format(x=sx + 1, y=sy, z=sz)
setup = [f"forceload add {bounds[0]} {bounds[1]} {bounds[2]} {bounds[3]}",
         *[f"function {NS}:{p}" for p in parts_], *signs, chest,
         f"setworldspawn {sx} {sy} {sz}", "gamerule respawn_radius 0", "difficulty normal",
         f"forceload remove {bounds[0]} {bounds[1]} {bounds[2]} {bounds[3]}",
         'tellraw @a {"text":"Pile of Bodies built.","color":"green"}']
w(f"data/{NS}/function/build.mcfunction", "\n".join(setup) + "\n")
json.dump({"bounds": bounds, "height": [min(ys), max(ys)], "spawn": [sx, sy, sz], "blocks": len(world), "end_portal": [cx, cy, cz],
           "bodies": names}, open(os.path.join(OUT, "info.json"), "w"), indent=1)
chunks = ((bounds[2] // 16) - (bounds[0] // 16) + 1) * ((bounds[3] // 16) - (bounds[1] // 16) + 1)
print(f"{len(world)} blocks, x {bounds[0]}..{bounds[2]}, z {bounds[1]}..{bounds[3]}, y {min(ys)}..{max(ys)}, {chunks} chunks, spawn {(sx, sy, sz)}")
