"""The Warlands island (Crispy Skyblock's PvPvE zone): block layout, relative to the island centre (surface ~y 0).

gen() -> (blocks, spawns, drops, resources)
  blocks     {(x, y, z): "block id"} relative to the centre
  spawns     mob spawn points [(x, y, z)] (standing positions on open ground)
  drops      player drop-in points [(x, y, z)] (ground positions; players are dropped in from above)
  resources  the minable block ids (they regrow like the other zones' resources)

Same layout as mockup.py (the concept render): a scorched floating island ~66 blocks across the radius, four sunken
resource fields, a raised Treasure Node platform with an obsidian obelisk and a beacon in the middle, ruined walls,
broken pillars and four rim watchtowers. Differences for the real build: no arrival bastion (players drop in at
random), the cracks are magma (glow, hurt, can't flow), and real lava only sits in a sunken channel whose every
source is checked to be enclosed (anything that could spill becomes magma).
"""
import math, random

R = 66
NODE_R = 9            # the Treasure Node platform radius
RESOURCES = ["diamond_ore", "deepslate_diamond_ore", "emerald_ore", "deepslate_emerald_ore", "gold_ore", "deepslate_gold_ore",
             "ancient_debris", "amethyst_block", "amethyst_cluster", "nether_gold_ore"]


def _noise(seed):
    cache = {}
    def val(ix, iz):
        k = (ix, iz)
        if k not in cache: cache[k] = random.Random(hash((ix, iz, seed)) & 0xffffffff).random()
        return cache[k]
    def n(x, z, scale):
        fx, fz = x / scale, z / scale; ix, iz = math.floor(fx), math.floor(fz); tx, tz = fx - ix, fz - iz
        sm = lambda t: t * t * (3 - 2 * t)
        a = val(ix, iz) * (1 - sm(tx)) + val(ix + 1, iz) * sm(tx)
        b = val(ix, iz + 1) * (1 - sm(tx)) + val(ix + 1, iz + 1) * sm(tx)
        return a * (1 - sm(tz)) + b * sm(tz)
    return n


def gen(seed=7):
    rng = random.Random(seed)
    n1, n2, n3, n4 = _noise(1), _noise(2), _noise(3), _noise(9)
    G = {}
    top = {}
    def put(x, y, z, b): G[(x, y, z)] = b
    edge_of = {}
    # ---- the island body: rolling top (y -4..+5 around 0), rising a little to the centre, a rough cone underneath
    for x in range(-R - 12, R + 13):
        for z in range(-R - 12, R + 13):
            d = math.hypot(x, z); ang = math.atan2(z, x)
            edge = R + 7 * math.sin(ang * 5 + 1) + 4 * math.sin(ang * 11) + (n3(x, z, 9) - 0.5) * 10
            if d > edge: continue
            edge_of[(x, z)] = edge
            h = int((n1(x, z, 18) - 0.5) * 8 + (n2(x, z, 7) - 0.5) * 4) + int(max(0, 6 - d / 6))
            depth = int((1 - d / edge) ** 0.7 * 26) + 3
            for y in range(h - depth, h):
                put(x, y, z, "deepslate" if y < h - 6 else "basalt" if y < h - 2 else "blackstone")
            v = n4(x, z, 5)
            put(x, h, z, "smooth_basalt" if v > 0.72 else "basalt" if v > 0.55 else "coarse_dirt" if v < 0.12 else "blackstone")
            top[(x, z)] = h
    surf = lambda x, z: top.get((x, z))
    def inner(x, z, margin):   # well inside the rim
        e = edge_of.get((x, z)); return e is not None and math.hypot(x, z) < e - margin

    # ---- magma cracks radiating from the centre
    for base_ang, length in ((0.3, 50), (2.1, 46), (3.9, 44), (5.2, 40)):
        for t in range(length):
            a = base_ang + math.sin(t / 9) * 0.25
            x, z = int(math.cos(a) * (12 + t)), int(math.sin(a) * (12 + t))
            if surf(x, z) is not None and inner(x, z, 5): put(x, surf(x, z), z, "magma_block")

    # ---- resource fields (sunken pits; the rim of each is plain stone)
    fields = [((30, -28), 15, ["diamond_ore", "deepslate_diamond_ore", "emerald_ore", "deepslate_emerald_ore"], 4),   # NE quarry
              ((-32, -6), 13, ["ancient_debris", "nether_gold_ore", "ancient_debris"], 3),                             # W debris pit
              ((-26, -34), 13, ["gold_ore", "deepslate_gold_ore", "amethyst_block"], 2),                               # NW geodes
              ((34, 18), 12, ["amethyst_block", "amethyst_block", "emerald_ore"], 0)]                                 # E crystal ridge
    for (fx, fz), rad, ores, sink in fields:
        for x in range(fx - rad, fx + rad + 1):
            for z in range(fz - rad, fz + rad + 1):
                if surf(x, z) is None or math.hypot(x - fx, z - fz) >= rad: continue
                deep = math.hypot(x - fx, z - fz) < rad - 3
                y = surf(x, z) - (sink if deep else 0)
                for yy in range(y + 1, surf(x, z) + 1): G.pop((x, yy, z), None)
                put(x, y, z, "stone" if not deep else "tuff")
                if rng.random() < 0.30: put(x, y, z, rng.choice(ores))
                if deep and rng.random() < 0.12: put(x, y - 1, z, rng.choice(ores))   # a second layer to dig into
                top[(x, z)] = y
    for _ in range(16):                       # amethyst spikes on the crystal ridge, clusters on top
        x, z = 34 + rng.randint(-9, 9), 18 + rng.randint(-9, 9)
        if surf(x, z) is None: continue
        hgt = rng.randint(2, 6)
        for y in range(surf(x, z) + 1, surf(x, z) + 1 + hgt): put(x, y, z, "amethyst_block")
        put(x, surf(x, z) + 1 + hgt, z, "amethyst_cluster[facing=up]")

    # ---- the lava channel beside the debris pit: sunk 2, sources only where fully enclosed
    chan = set()
    for t in range(-30, 8):
        x0 = -48 + int(math.sin(t / 6) * 3)
        for w in range(-1, 2): chan.add((x0 + w, t))
    for (x, z) in chan:
        if surf(x, z) is None or not inner(x, z, 6): continue
        y = surf(x, z) - 2
        for yy in range(y, surf(x, z) + 1): G.pop((x, yy, z), None)
        put(x, y, z, "lava"); put(x, y - 1, z, "blackstone")
    for (x, y, z), b in list(G.items()):      # any lava source that could spill becomes magma
        if b != "lava": continue
        ok = (x, y - 1, z) in G and all(G.get((x + dx, y, z + dz)) is not None for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if not ok: G[(x, y, z)] = "magma_block"

    # ---- the Treasure Node: a raised round platform, an obsidian obelisk with a 3x3 gold cap and a beacon on top
    ty = (surf(0, 0) or 0) + 1
    for x in range(-NODE_R, NODE_R + 1):
        for z in range(-NODE_R, NODE_R + 1):
            if math.hypot(x, z) > NODE_R + 0.5 or surf(x, z) is None: continue
            for y in range(surf(x, z) + 1, ty + 1): put(x, y, z, "polished_blackstone")
            if math.hypot(x, z) > NODE_R - 0.8: put(x, ty, z, "polished_blackstone_bricks")
            top[(x, z)] = ty
    for px, pz in ((-7, -7), (7, -7), (-7, 7), (7, 7)):
        for y in range(ty + 1, ty + 7): put(px, y, pz, "deepslate_bricks")
        put(px, ty + 7, pz, "soul_lantern")
    for y in range(ty + 1, ty + 8):
        for x in (-1, 0, 1):
            for z in (-1, 0, 1): put(x, y, z, "obsidian" if y < ty + 7 else "gold_block")
    put(0, ty + 8, 0, "beacon")
    node = (0, ty, 0)

    # ---- cover: ruined walls and broken pillars (never on the node platform or in a field)
    def clear_spot(x, z): return surf(x, z) is not None and math.hypot(x, z) > NODE_R + 3 and inner(x, z, 3) \
        and all(math.hypot(x - fx, z - fz) > rad for (fx, fz), rad, _, _ in fields)
    for _ in range(18):
        a = rng.random() * math.tau; d = rng.uniform(16, 54); x0, z0 = int(math.cos(a) * d), int(math.sin(a) * d)
        horiz = rng.random() < 0.5; ln = rng.randint(5, 11)
        for i in range(ln):
            x, z = (x0 + i, z0) if horiz else (x0, z0 + i)
            if clear_spot(x, z):
                for y in range(surf(x, z) + 1, surf(x, z) + 1 + rng.choice([1, 2, 2, 3, 3, 4])):
                    put(x, y, z, rng.choice(["deepslate_bricks", "deepslate_bricks", "cracked_deepslate_bricks"]))
    for _ in range(12):
        a = rng.random() * math.tau; d = rng.uniform(14, 56); x, z = int(math.cos(a) * d), int(math.sin(a) * d)
        if clear_spot(x, z):
            for y in range(surf(x, z) + 1, surf(x, z) + rng.randint(4, 9)): put(x, y, z, "polished_blackstone")

    # ---- four watchtowers on the rim: hollow, a ladder up the inside, a lookout with crenellations and a banner
    for a in (225, 315, 45, 135):
        x0, z0 = int(math.cos(math.radians(a)) * 50), int(math.sin(math.radians(a)) * 50)
        if surf(x0, z0) is None: continue
        b = surf(x0, z0)
        for x in range(x0 - 2, x0 + 3):
            for z in range(z0 - 2, z0 + 3):
                hollow = abs(x - x0) < 2 and abs(z - z0) < 2
                for y in range(b + 1, b + 13):
                    if not hollow or y == b + 12: put(x, y, z, "deepslate_bricks")
                    else: G.pop((x, y, z), None)
                if abs(x - x0) == 2 and abs(z - z0) == 2: put(x, b + 13, z, "deepslate_brick_wall")
        for y in range(b + 1, b + 12): put(x0, y, z0 + 1, "ladder[facing=north]")
        put(x0, b + 12, z0 + 1, "air")                                  # a hatch through the lookout floor
        for y in range(b + 1, b + 3): G.pop((x0, y, z0 - 2), None)       # a doorway
        put(x0, b + 13, z0, "red_banner")

    # ---- spawn and drop-in points: open ground away from the node, the fields and the towers
    spawns, drops = [], []
    tries = 0
    while (len(spawns) < 40 or len(drops) < 30) and tries < 20000:
        tries += 1
        x, z = rng.randint(-R, R), rng.randint(-R, R)
        if not clear_spot(x, z) or not inner(x, z, 6): continue
        y = surf(x, z)
        if G.get((x, y, z)) in ("magma_block", "lava"): continue
        if any(G.get((x, y + k, z)) for k in (1, 2, 3)): continue
        if len(spawns) < 40 and all(math.dist((x, z), (s[0], s[2])) > 6 for s in spawns): spawns.append((x, y + 1, z))
        elif len(drops) < 30 and all(math.dist((x, z), (s[0], s[2])) > 10 for s in drops) and math.hypot(x, z) > 20: drops.append((x, y + 1, z))
    return G, spawns, drops, RESOURCES, node


def fill_runs(G):
    """(x0, y, z, x1, block) runs along x of the same block, for compact fill commands."""
    rows = {}
    for (x, y, z), b in G.items(): rows.setdefault((y, z), []).append((x, b))
    out = []
    for (y, z) in sorted(rows):
        run = sorted(rows[(y, z)]); i = 0
        while i < len(run):
            j = i
            while j + 1 < len(run) and run[j + 1][0] == run[j][0] + 1 and run[j + 1][1] == run[i][1]: j += 1
            out.append((run[i][0], y, z, run[j][0], run[i][1])); i = j + 1
    return out


if __name__ == "__main__":
    G, s, d, res, node = gen()
    print(len(G), "blocks,", len(fill_runs(G)), "fill runs,", len(s), "spawns,", len(d), "drops, node", node)
    print("lava sources:", sum(1 for b in G.values() if b == "lava"))
