"""Outbreak map layouts (imported by build.py).

Each map is drawn into a Grid of blocks relative to the map centre:
- dx and dz run from -33 to 33, with the outer walls at ±33;
- each map's designed centre fills about ±22; the ring outside it (to ±32) has more cover in the same theme;
- dy 0 is the floor layer, and players stand on dy 1.

commands() turns a grid into setblock/fill commands. It works out fence, wall and pane connections itself, since a
block placed by a command doesn't connect to the blocks around it. It places blocks that need support (plants,
lanterns, rails, dripstone) after the blocks they rest on.

check() makes sure every mob window can still walk to the Arsenal and that the player spawns stay clear.
"""
import math
import random
from collections import defaultdict, deque

R = 32          # interior half-size; the outer wall is at ±33
WALL_H = 6      # wall rows dy 0..5 (build.py's walls() puts barrier above)

# blocks you can walk through, and blocks that need another block to hold them up
PASSABLE = ("air", "carpet", "rail", "short_grass", "fern", "roots", "sprouts", "candle", "pressure_plate", "button",
            "glow_lichen", "poppy", "dandelion", "cornflower", "torch", "lantern", "fungus")
ATTACHED = ("lantern", "rail", "carpet", "candle", "torch", "end_rod", "short_grass", "fern", "roots", "sprouts",
            "pointed_dripstone", "glow_lichen", "pressure_plate", "poppy", "dandelion", "cornflower", "fungus", "fire")
NOT_FULL = ("slab", "stairs", "fence", "_wall", "pane", "bars", "chain", "lava", "water", "glass_pane", "campfire",
            "cauldron", "trapdoor", "door", "barrel_x") + PASSABLE + ATTACHED
DIRS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def nm(b): return b.split("[")[0]
def is_full(b): return b is not None and not any(s in nm(b) for s in NOT_FULL)
def is_fence(b): return b is not None and nm(b).endswith("fence")
def is_wall(b): return b is not None and nm(b).endswith("_wall") and "torch" not in nm(b)
def is_pane(b): return b is not None and (nm(b).endswith("pane") or nm(b) == "iron_bars")


class Noise:
    """Smooth 2D value noise in 0..1; `scale` is the feature size in blocks."""
    def __init__(self, seed, scale): self.seed, self.s = seed, scale
    def _v(self, i, j): return random.Random(self.seed * 1000003 + i * 7919 + j * 104729).random()
    def __call__(self, x, z):
        fx, fz = x / self.s, z / self.s
        i, j = math.floor(fx), math.floor(fz)
        u, v = fx - i, fz - j
        u, v = u * u * (3 - 2 * u), v * v * (3 - 2 * v)
        a = self._v(i, j) + (self._v(i + 1, j) - self._v(i, j)) * u
        b = self._v(i, j + 1) + (self._v(i + 1, j + 1) - self._v(i, j + 1)) * u
        return a + (b - a) * v


class Grid:
    def __init__(self, mob_points, spawns):
        self.b = {}
        self.mob_points, self.spawns = mob_points, spawns
        self.windows = []   # (x, z) wall cells holding iron bars

    def protected(self, x, z):
        """Cells kept clear above the floor: the Arsenal, the player spawns and the mob windows."""
        if max(abs(x), abs(z)) <= 2: return True
        if any(max(abs(x - sx), abs(z - sz)) <= 1 for (sx, sz, _) in self.spawns): return True
        return any(math.hypot(x - mx, z - mz) <= 2.5 for (mx, mz) in self.mob_points)

    def put(self, x, y, z, block, force=False):
        if abs(x) > R + 1 or abs(z) > R + 1: return
        if y >= 1 and not force and abs(x) <= R and abs(z) <= R and self.protected(x, z): return
        self.b[(x, y, z)] = block

    def fill(self, x1, y1, z1, x2, y2, z2, block, force=False):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    self.put(x, y, z, block, force)

    def get(self, x, y, z): return self.b.get((x, y, z))
    def empty(self, x, y, z): return (x, y, z) not in self.b
    def floor(self): return [(x, z) for x in range(-R, R + 1) for z in range(-R, R + 1)]


def base(mob_points, spawns, wallfn, fire="campfire"):
    """A grid with the outer wall skin (wallfn(x, y, z, t) per wall block; t = position along the wall) and barred
    mob windows. Behind each window, outside the wall, a lit campfire sends smoke up past the bars, and a solid
    backing hides the world (and the other maps) beyond."""
    g = Grid(mob_points, spawns)
    for t in range(-R - 1, R + 2):
        for (x, z) in ((t, -R - 1), (t, R + 1), (-R - 1, t), (R + 1, t)):
            for y in range(WALL_H):
                g.b[(x, y, z)] = wallfn(x, y, z, t)
    for (dx, dz) in mob_points:
        if abs(dx) > abs(dz): cells = [((R + 1) * (1 if dx > 0 else -1), dz + k) for k in (-1, 0, 1)]
        else: cells = [(dx + k, (R + 1) * (1 if dz > 0 else -1)) for k in (-1, 0, 1)]
        for (x, z) in cells:
            g.windows.append((x, z))
            for y in (1, 2, 3): g.b[(x, y, z)] = "iron_bars"
        if abs(dx) > abs(dz): s, along = (1 if dx > 0 else -1), "z"
        else: s, along = (1 if dz > 0 else -1), "x"
        b, c = R + 1, dz if along == "z" else dx
        for k in range(-2, 3):
            for y in range(WALL_H):
                for depth in (1, 2):
                    if depth == 1 and abs(k) <= 1 and y >= 1: continue   # the smoke chamber
                    pos = (s * (b + depth), c + k) if along == "z" else (c + k, s * (b + depth))
                    g.b[(pos[0], y, pos[1])] = wallfn(pos[0], y, pos[1], c + k)
        for k in (-1, 0, 1):
            pos = (s * (b + 1), c + k) if along == "z" else (c + k, s * (b + 1))
            g.b[(pos[0], 1, pos[1])] = f"{fire}[lit=true]"
    return g


def wall_sides():
    """(inner cell (x, z), outward direction, position along the wall) for the ring just inside the outer wall."""
    for t in range(-R, R + 1):
        yield (R, t), "east", t
        yield (-R, t), "west", t
        yield (t, R), "south", t
        yield (t, -R), "north", t


def near_window(t, gap=2): return any(abs(t - w) <= gap for w in (-16, 0, 16))


def line(x1, z1, x2, z2):
    n = max(abs(x2 - x1), abs(z2 - z1))
    return [(round(x1 + (x2 - x1) * k / n), round(z1 + (z2 - z1) * k / n)) for k in range(n + 1)]


# ---------------------------------------------------------------------------------------------- Ruins
def ruins(mob_points, spawns):
    """Overgrown temple courtyard: a broken colonnade around a raised dais, fallen columns, crumbling wall corners."""
    rnd = random.Random(11)
    g = base(mob_points, spawns, lambda x, y, z, t: rnd.choices(["stone_bricks", "mossy_stone_bricks", "cracked_stone_bricks"], [5, 3, 2])[0])
    wear, moss = Noise(1, 6), Noise(2, 5)
    for (x, z) in g.floor():
        m, w = moss(x, z), wear(x, z)
        if m > 0.70:
            g.put(x, 0, z, "moss_block")
            r = rnd.random()
            if r < 0.35: g.put(x, 1, z, "moss_carpet")
            elif r < 0.45: g.put(x, 1, z, "short_grass")
        elif m > 0.62:
            g.put(x, 0, z, "grass_block")
            r = rnd.random()
            if r < 0.4: g.put(x, 1, z, "short_grass")
            elif r < 0.5: g.put(x, 1, z, "fern")
            elif r < 0.54: g.put(x, 1, z, rnd.choice(["poppy", "dandelion", "cornflower"]))
        else:
            b = ("cracked_stone_bricks" if w < 0.3 else "stone_bricks" if w < 0.55 else "mossy_stone_bricks" if w < 0.7
                 else "cobblestone" if w < 0.82 else "mossy_cobblestone" if w < 0.92 else "gravel")
            if rnd.random() < 0.07: b = "cracked_stone_bricks"
            g.put(x, 0, z, b)
    # the dais around the Arsenal
    for x in range(-2, 3):
        for z in range(-2, 3):
            if max(abs(x), abs(z)) == 2: g.put(x, 1, z, "stone_brick_slab[type=bottom]", force=True)
            g.put(x, 0, z, "chiseled_stone_bricks" if (x + z) % 2 == 0 else "stone_bricks")
    # colonnade: 12 pillars, every third one broken; neighbouring intact pillars carry a lintel
    pillars = []
    for k in range(12):
        a = math.radians(k * 30 + 15)
        px, pz = round(13 * math.cos(a)), round(13 * math.sin(a))
        intact = k % 3 != 1
        pillars.append((px, pz, intact))
        g.put(px, 0, pz, "chiseled_stone_bricks")
        if intact:
            g.put(px, 1, pz, "chiseled_stone_bricks")
            for y in range(2, 6): g.put(px, y, pz, rnd.choice(["stone_bricks", "stone_bricks", "mossy_stone_bricks"]))
            g.put(px, 6, pz, "chiseled_stone_bricks")
            for d, (ox, oz) in DIRS.items():   # glowing lichen creeping up the shafts
                if rnd.random() < 0.4:
                    opp = {"north": "south", "south": "north", "east": "west", "west": "east"}[d]
                    for y in range(rnd.randint(2, 4), 6): g.put(px + ox, y, pz + oz, f"glow_lichen[{opp}=true]")
        else:
            h = rnd.randint(2, 4)
            for y in range(1, h): g.put(px, y, pz, rnd.choice(["stone_bricks", "mossy_stone_bricks"]))
            g.put(px, h, pz, "cracked_stone_bricks")
            g.put(px, h + 1, pz, "soul_lantern")
            for (ox, oz) in rnd.sample(list(DIRS.values()), 3):   # rubble at the foot
                g.put(px + ox, 1, pz + oz, rnd.choice(["stone_brick_slab[type=bottom]", "cobblestone_slab[type=bottom]",
                                                       f"mossy_stone_brick_stairs[facing={rnd.choice(list(DIRS))}]"]))
    for k in range(12):
        (x1, z1, i1), (x2, z2, i2) = pillars[k], pillars[(k + 1) % 12]
        if i1 and i2:
            cells = line(x1, z1, x2, z2)[1:-1]
            for (x, z) in cells: g.put(x, 6, z, rnd.choice(["stone_bricks", "mossy_stone_bricks"]))
            mx, mz = cells[len(cells) // 2]
            g.put(mx, 5, mz, "lantern[hanging=true]")
    # crumbling wall corners, jagged tops
    for sx in (-1, 1):
        for sz in (-1, 1):
            cells = [(sx * x, sz * 16) for x in range(13, 17)] + [(sx * 16, sz * z) for z in range(13, 16)]
            for (x, z) in cells:
                if rnd.random() < 0.15: continue
                h = rnd.choice([1, 2, 2, 3, 3])
                for y in range(1, h + 1): g.put(x, y, z, rnd.choice(["stone_bricks", "mossy_stone_bricks", "cracked_stone_bricks", "mossy_cobblestone"]))
                if rnd.random() < 0.4: g.put(x, h + 1, z, rnd.choice(["stone_brick_slab[type=bottom]", f"stone_brick_stairs[facing={rnd.choice(list(DIRS))}]"]))
            g.put(sx * 17, 1, sz * 17, "lantern")
    # fallen columns
    for cells in ([(x, -11) for x in range(7, 11)], [(-11, z) for z in range(7, 11)]):
        for n, (x, z) in enumerate(cells):
            g.put(x, 1, z, "chiseled_stone_bricks" if n == 0 else "stone_brick_slab[type=bottom]" if n == len(cells) - 1 else rnd.choice(["stone_bricks", "mossy_stone_bricks"]))
        x, z = cells[1]
        g.put(x, 2, z, "candle[candles=3,lit=true]")
    # outer ring: a second, more ruined colonnade and more fallen columns
    for k in range(16):
        a = math.radians(k * 22.5 + 11)
        px, pz = round(26 * math.cos(a)), round(26 * math.sin(a))
        g.put(px, 0, pz, "chiseled_stone_bricks")
        h = 6 if k % 4 == 0 else rnd.randint(2, 4)
        for y in range(1, h): g.put(px, y, pz, rnd.choice(["stone_bricks", "mossy_stone_bricks", "cracked_stone_bricks"]))
        g.put(px, h, pz, "chiseled_stone_bricks" if h == 6 else "cracked_stone_bricks")
        g.put(px, h + 1, pz, "soul_lantern" if h < 6 else "lantern")
        for (ox, oz) in rnd.sample(list(DIRS.values()), 2):
            g.put(px + ox, 1, pz + oz, rnd.choice(["stone_brick_slab[type=bottom]", "cobblestone_slab[type=bottom]", "mossy_cobblestone"]))
    for cells in ([(x, 20) for x in range(18, 23)], [(x, -20) for x in range(-22, -17)], [(20, z) for z in range(-23, -18)],
                  [(-20, z) for z in range(18, 23)]):
        for n, (x, z) in enumerate(cells):
            g.put(x, 1, z, "chiseled_stone_bricks" if n == 0 else "stone_brick_slab[type=bottom]" if n == len(cells) - 1 else rnd.choice(["stone_bricks", "mossy_stone_bricks"]))
    # buttresses along the outer wall
    for (x, z), d, t in wall_sides():
        if t in (-24, -8, 8, 24):
            for y in range(1, 6): g.put(x, y, z, "stone_bricks")
            g.put(x, 6, z, f"stone_brick_stairs[facing={d}]")
            ox, oz = DIRS[d]
            g.put(x - ox, 1, z - oz, f"stone_brick_stairs[facing={d}]")
        elif not near_window(t) and rnd.random() < 0.07:
            for y in range(rnd.randint(1, 3), 6): g.put(x, y, z, f"glow_lichen[{d}=true]")
    return g


# ---------------------------------------------------------------------------------------------- Toxic Mine
def mine(mob_points, spawns):
    """Cave with a mine-cart loop under timber frames, rock outcrops, stalagmites, an overhanging rock ceiling with
    stalactites, and puddles of toxic sludge (slime, so it slows you down) glowing green from below."""
    rnd = random.Random(12)
    rock = Noise(3, 4)
    rocks = lambda x, z: ["stone", "andesite", "tuff", "cobblestone", "stone", "tuff"][min(5, int(rock(x, z) * 6))]
    g = base(mob_points, spawns, lambda x, y, z, t: rocks(x + y * 3, z - y * 2))
    ground, sludge = Noise(4, 5), Noise(5, 4)
    on_rail = lambda x, z: max(abs(x), abs(z)) == 15
    near_rail = lambda x, z: abs(max(abs(x), abs(z)) - 15) <= 1
    for (x, z) in g.floor():
        n = ground(x, z)
        b = "gravel" if n < 0.22 else "andesite" if n < 0.42 else "stone" if n < 0.68 else "tuff" if n < 0.86 else "cobblestone"
        if rnd.random() < 0.05: b = "coarse_dirt"
        s = sludge(x, z)
        if not near_rail(x, z) and not g.protected(x, z):
            if s > 0.74:
                b = "slime_block"
                g.put(x, -1, z, "verdant_froglight")
            elif s > 0.69:
                b = "moss_block"
                if rnd.random() < 0.5: g.put(x, 1, z, "moss_carpet")
        g.put(x, 0, z, b)
    # mine-cart loop on gravel ballast
    corners = {(15, 15): "north_west", (-15, 15): "north_east", (15, -15): "south_west", (-15, -15): "south_east"}
    for t in range(-15, 16):
        for (x, z, shape) in ((15, t, "north_south"), (-15, t, "north_south"), (t, 15, "east_west"), (t, -15, "east_west")):
            g.put(x, 0, z, "gravel")
            g.put(x, 1, z, f"rail[shape={corners.get((x, z), shape)}]")
    # timber frames over the track
    for t in (-7, 7):
        for side in (-1, 1):
            for (along_x, c) in ((False, side * 15), (True, side * 15)):
                if along_x:   # frame across the east/west track: posts at x = c ± 2, z = t
                    posts, beam, axis = [(c - 2, t), (c + 2, t)], [(x, t) for x in range(c - 2, c + 3)], "x"
                    mid = (c, t)
                else:
                    posts, beam, axis = [(t, c - 2), (t, c + 2)], [(t, z) for z in range(c - 2, c + 3)], "z"
                    mid = (t, c)
                for (x, z) in posts:
                    for y in (1, 2, 3): g.put(x, y, z, "stripped_spruce_log[axis=y]")
                for (x, z) in beam: g.put(x, 4, z, f"stripped_spruce_log[axis={axis}]")
                g.put(mid[0], 3, mid[1], "lantern[hanging=true]")
    # rock outcrops: steep sides (rubble, then a 3-high step) so nobody can climb on top
    shape = Noise(6, 2)
    for (cx, cz, r) in ((-9, -9, 3.2), (9, 8, 2.6), (2, -10, 2.0), (-10, 3, 2.2), (10, -3, 2.0),
                        (19, -19, 2.8), (-19, 19, 2.8), (-19, -19, 2.2), (19, 19, 2.2),
                        (25, -6, 3.0), (-25, 7, 3.0), (7, 25, 2.6), (-6, -25, 2.6), (26, 24, 2.4), (-24, -26, 2.4),
                        (24, -26, 2.2), (-26, 24, 2.2), (22, 10, 1.8), (-22, -10, 1.8)):
        peak = None
        for x in range(math.floor(cx - r * 1.4), math.ceil(cx + r * 1.4) + 1):
            for z in range(math.floor(cz - r * 1.4), math.ceil(cz + r * 1.4) + 1):
                if abs(x) > R or abs(z) > R or near_rail(x, z) or g.protected(x, z): continue
                q = math.hypot(x - cx, z - cz) / (r * (0.8 + 0.5 * shape(x, z)))
                if q >= 1: continue
                h = rnd.randint(4, 6) if q < 0.45 else 3 if q < 0.75 else 1
                for y in range(1, h + 1): g.put(x, y, z, rocks(x + y, z))
                if h == 1 and rnd.random() < 0.5: g.put(x, 1, z, rnd.choice(["cobblestone_slab", "andesite_slab", "tuff_slab", "stone_slab"]) + "[type=bottom]")
                if q < 0.45 and (peak is None or h > peak[2]): peak = (x, z, h)
        if peak:
            x, z, h = peak
            g.put(x, h, z, "dripstone_block")
            g.put(x, h + 1, z, "pointed_dripstone[vertical_direction=up,thickness=frustum]")
            g.put(x, h + 2, z, "pointed_dripstone[vertical_direction=up,thickness=tip]")
    # stalagmite clusters on the open floor
    thick = {1: ["tip"], 2: ["frustum", "tip"], 3: ["base", "frustum", "tip"]}
    for _ in range(26):
        x, z = rnd.randint(-30, 30), rnd.randint(-30, 30)
        for (ox, oz) in rnd.sample([(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)], rnd.randint(1, 3)):
            X, Z = x + ox, z + oz
            if near_rail(X, Z) or g.protected(X, Z) or not g.empty(X, 1, Z): continue
            g.put(X, 0, Z, "dripstone_block")
            for y, th in enumerate(thick[rnd.choice([1, 2, 2, 3])], 1): g.put(X, y, Z, f"pointed_dripstone[vertical_direction=up,thickness={th}]")
    # toxic waste barrels with green candles
    for (x, z) in ((-6, -13), (12, -9), (-12, 10), (7, 12), (-20, -6), (20, 5), (5, 20), (-5, -20),
                   (27, 12), (-27, -13), (12, -27), (-13, 27), (20, 28), (-28, 20)):
        for (ox, oz) in [(0, 0)] + rnd.sample([(1, 0), (0, 1), (-1, 0), (0, -1)], 2):
            X, Z = x + ox, z + oz
            if near_rail(X, Z) or g.protected(X, Z) or not g.empty(X, 1, Z): continue
            g.put(X, 1, Z, "barrel[facing=up]")
            if (ox, oz) == (0, 0) and rnd.random() < 0.6:
                g.put(X, 2, Z, "barrel[facing=up]")
                g.put(X, 3, Z, f"lime_candle[candles={rnd.randint(1, 4)},lit=true]")
            else: g.put(X, 2, Z, f"lime_candle[candles={rnd.randint(1, 4)},lit=true]")
    # rock lining along the walls (3+ high, so it can't be climbed) and an overhang with stalactites
    depth, over = Noise(7, 3), Noise(8, 4)
    for (x, z), d, t in wall_sides():
        if near_window(t): continue
        ox, oz = DIRS[d]
        dn = depth(x, z)
        k = 1 if dn < 0.45 else 2 if dn < 0.8 else 3
        h = 3 + int(depth(z, x) * 4)
        for i in range(k):
            X, Z = x - ox * i, z - oz * i
            for y in range(1, max(3, h - i) + 1): g.put(X, y, Z, rocks(X + y, Z))
    for (x, z) in g.floor():
        c = max(abs(x), abs(z))
        if c < R - 3: continue
        if over(x, z) > {R: 0.15, R - 1: 0.35, R - 2: 0.55, R - 3: 0.75}[c]:
            g.put(x, 6, z, rocks(x, z + 6))
            if c >= R - 1: g.put(x, 7, z, rocks(x + 7, z))
    for (x, z) in g.floor():
        if g.get(x, 6, z) and not g.get(x, 5, z) and rnd.random() < 0.3:
            if rnd.random() < 0.5: g.put(x, 5, z, "pointed_dripstone[vertical_direction=down,thickness=tip]")
            else:
                g.put(x, 5, z, "pointed_dripstone[vertical_direction=down,thickness=frustum]")
                g.put(x, 4, z, "pointed_dripstone[vertical_direction=down,thickness=tip]")
    return g


# ---------------------------------------------------------------------------------------------- Neon City
def neon(mob_points, spawns):
    """A night-time crossroads: roads with lane markings and crosswalks, kerbs and street lamps, a tower with a
    glowing sign, a noodle bar, a car park and an arcade with a rooftop billboard."""
    rnd = random.Random(13)
    def wallfn(x, y, z, t):
        if abs(t) == 24 and 1 <= y <= 5: return "sea_lantern"
        return "magenta_concrete" if y == 4 else "black_concrete"
    g = base(mob_points, spawns, wallfn)
    for (x, z) in g.floor():
        ax, az, lo = abs(x), abs(z), min(abs(x), abs(z))
        if ax <= 4 or az <= 4:   # roads
            b = "blackstone" if rnd.random() < 0.06 else "black_concrete"
            if ax <= 4 and az <= 4: pass
            elif az <= 4 and ax in (5, 6) and z % 2 == 0: b = "white_concrete"
            elif ax <= 4 and az in (5, 6) and x % 2 == 0: b = "white_concrete"
            elif x == 0 and az >= 8 and z % 4 in (0, 1): b = "yellow_concrete"
            elif z == 0 and ax >= 8 and x % 4 in (0, 1): b = "yellow_concrete"
        elif lo <= 7: b = "smooth_stone" if rnd.random() < 0.15 else "light_gray_concrete"   # pavement
        else: b = "gray_concrete" if rnd.random() < 0.8 else "cyan_terracotta"
        g.put(x, 0, z, b)
        if lo == 5 and ax >= 5 and az >= 5: g.put(x, 1, z, "smooth_stone_slab[type=bottom]")   # kerb
    # lamps
    for (x, z) in [(sx * 6, sz * 6) for sx in (-1, 1) for sz in (-1, 1)] + [(sx * 6, sz * 16) for sx in (-1, 1) for sz in (-1, 1)] \
            + [(sx * 16, sz * 6) for sx in (-1, 1) for sz in (-1, 1)] + [(sx * 6, sz * 26) for sx in (-1, 1) for sz in (-1, 1)] \
            + [(sx * 26, sz * 6) for sx in (-1, 1) for sz in (-1, 1)]:
        for y in range(1, 5): g.put(x, y, z, "polished_blackstone_wall")
        g.put(x, 5, z, "sea_lantern")
        g.put(x, 6, z, "polished_blackstone_slab[type=bottom]")
    # tower (+x, -z)
    X1, X2, Z1, Z2 = 8, 15, -15, -8
    for x in range(X1, X2 + 1):
        for z in range(Z1, Z2 + 1):
            edge, corner = x in (X1, X2) or z in (Z1, Z2), x in (X1, X2) and z in (Z1, Z2)
            for y in range(1, 17):
                if y <= 3 and not edge: continue   # lobby
                b = "purple_concrete" if corner else "black_concrete"
                if edge and not corner and y in (5, 6, 9, 10, 13, 14): b = "cyan_stained_glass"
                if y == 4 and not edge and (x + z) % 3 == 0: b = "sea_lantern"
                g.put(x, y, z, b)
    for (x, z) in ((X1, Z1), (X1, Z2), (X2, Z1), (X2, Z2)): g.put(x, 17, z, "end_rod[facing=up]")
    for z in (-12, -11):
        for y in (1, 2): g.put(X1, y, z, "air")   # door to the north-south road
    for x in (11, 12):
        for y in (1, 2): g.put(x, y, Z2, "air")   # door to the east-west road
    for z in (-13, -12):   # vertical sign over the pavement
        for y in range(5, 12):
            g.put(X1, y, z, "pearlescent_froglight")
            g.put(X1 - 1, y, z, "magenta_stained_glass")
    g.put(13, 1, -13, "smooth_quartz_slab[type=top]")
    g.put(14, 1, -13, "smooth_quartz_slab[type=top]")
    g.put(14, 2, -13, "potted_azalea_bush")
    # noodle bar (+x, +z)
    X1, X2, Z1, Z2 = 9, 16, 10, 15
    for x in range(X1, X2 + 1):
        for z in range(Z1, Z2 + 1):
            edge = x in (X1, X2) or z in (Z1, Z2)
            for y in range(1, 6):
                if y < 5 and not edge: continue
                g.put(x, y, z, "red_concrete" if y == 4 else "light_gray_concrete")
    for x in range(11, 15):
        for y in (1, 2, 3): g.put(x, y, Z1, "air")
    for x in range(X1, X2 + 1):
        g.put(x, 4, Z1 - 1, "crimson_slab[type=top]" if x % 2 else "birch_slab[type=top]")   # striped awning
        if x in (10, 15): g.put(x, 3, Z1 - 1, "lantern[hanging=true]")
        if 10 <= x <= 15:
            for y in (6, 7):
                g.put(x, y, Z1, "red_stained_glass")
                g.put(x, y, Z1 + 1, "shroomlight")
    for x in (11, 14):
        g.put(x, 1, 12, "spruce_fence")
        g.put(x, 2, 12, "spruce_pressure_plate")
        g.put(x, 4, 12, "lantern[hanging=true]")
    for x in range(10, 16): g.put(x, 1, Z2 - 1, "polished_andesite_slab[type=top]")
    g.put(12, 2, Z2 - 1, "cauldron")
    # car park (-x, +z)
    for x in (-17, -14, -11):
        for z in range(9, 17): g.put(x, 0, z, "white_concrete")
    for (x0, z0, body) in ((-16, 9, "red"), (-13, 12, "yellow"), (-10, 9, "white"), (-16, 18, "lime")):
        for x in (x0, x0 + 1):
            for z in range(z0, z0 + 4):
                g.put(x, 1, z, f"{body}_concrete")
                if z0 < z < z0 + 3: g.put(x, 2, z, "gray_stained_glass")
    # arcade (-x, -z), L-shaped, with a rooftop billboard
    foot = {(x, z) for x in range(-16, -7) for z in range(-16, -11)} | {(x, z) for x in range(-16, -11) for z in range(-11, -7)}
    for (x, z) in foot:
        edge = any((x + ox, z + oz) not in foot for (ox, oz) in DIRS.values())
        for y in range(1, 8):
            if y <= 3 and not edge: continue
            b = "light_blue_concrete" if y == 6 else "black_concrete"
            if y == 4 and not edge and (x + z) % 3 == 0: b = "sea_lantern"
            g.put(x, y, z, b)
    for z in (-14, -13):
        for y in (1, 2): g.put(-8, y, z, "air")
    for x in (-15, -14):
        for y in (1, 2): g.put(x, y, -8, "air")
    for n, x in enumerate(range(-15, -8, 2)):   # arcade machines
        g.put(x, 1, -15, "black_concrete")
        g.put(x, 2, -15, ["magenta_stained_glass", "cyan_stained_glass", "lime_stained_glass", "orange_stained_glass"][n % 4])
        g.put(x, 2, -16, "sea_lantern")
    for x in range(-15, -8):
        for y in range(8, 12):
            frame = x in (-15, -9) or y in (8, 11)
            g.put(x, y, -16, "black_concrete" if frame else ["magenta_glazed_terracotta", "light_blue_glazed_terracotta", "purple_glazed_terracotta"][(x + y) % 3])
    # billboards on the outer walls, between the windows
    colours = ["magenta", "cyan", "lime", "orange", "purple", "light_blue", "pink", "yellow"]
    n = 0
    for (x, z), d, t in wall_sides():
        if 4 <= abs(t) <= 8:
            for y in (3, 4, 5): g.put(x, y, z, f"{colours[(n // 15) % 8]}_glazed_terracotta")
        elif abs(t) == 24:
            for y in range(1, 6): g.put(x, y, z, "light_blue_stained_glass")
        n += 1
    # kiosks in the outer corners: neon boxes with a door facing the middle
    for n, (sx, sz) in enumerate(((1, 1), (-1, -1), (1, -1), (-1, 1))):
        col = ["magenta", "cyan", "lime", "orange"][n]
        xs, zs = sorted((sx * 21, sx * 26)), sorted((sz * 21, sz * 26))
        for x in range(xs[0], xs[1] + 1):
            for z in range(zs[0], zs[1] + 1):
                edge = x in xs or z in zs
                for y in range(1, 6):
                    if y <= 3 and not edge: continue
                    g.put(x, y, z, f"{col}_stained_glass" if edge and y in (2, 3) and not (x in xs and z in zs) else
                          "sea_lantern" if y == 5 and (x + z) % 3 == 0 else "black_concrete")
        dx_, dz_ = sx * 21, sz * 23
        for y in (1, 2): g.put(dx_, y, dz_, "air"); g.put(dx_, y, dz_ + sz, "air")
    # parked cars along the outer roads
    for (x0, z0, body) in ((-3, 24, "blue"), (2, -28, "red"), (24, 2, "white"), (-28, -3, "yellow")):
        along_x = abs(x0) > abs(z0)
        for a in range(4):
            for b in range(2):
                x, z = (x0 + a, z0 + b) if along_x else (x0 + b, z0 + a)
                g.put(x, 1, z, f"{body}_concrete")
                if 0 < a < 3: g.put(x, 2, z, "gray_stained_glass")
    # alley clutter
    for (x, z) in ((30, 30), (-30, -30), (30, -30), (-30, 30), (18, 21), (-21, 18), (30, 10), (-30, -10)):
        g.put(x, 1, z, rnd.choice(["barrel[facing=up]", "composter", "cauldron"]))
    return g


# ---------------------------------------------------------------------------------------------- Hellfort
def hellfort(mob_points, spawns):
    """A nether keep: you start inside a walled courtyard with four arched gates and corner towers; outside are
    fenced lava pools, basalt columns, a giant ribcage and a ruined portal."""
    rnd = random.Random(14)
    g = base(mob_points, spawns, lambda x, y, z, t: rnd.choices(["nether_bricks", "red_nether_bricks", "cracked_nether_bricks"], [6, 2, 2])[0], "soul_campfire")
    ground, growth = Noise(9, 5), Noise(10, 4)
    for (x, z) in g.floor():
        c = max(abs(x), abs(z))
        if c < 9:   # courtyard
            b = "chiseled_polished_blackstone" if c in (3, 6) and (x + z) % 2 == 0 else \
                rnd.choices(["polished_blackstone_bricks", "cracked_polished_blackstone_bricks", "gilded_blackstone"], [8, 3, 0.3])[0]
        else:
            n = ground(x, z)
            b = "nether_bricks" if n < 0.35 else "netherrack" if n < 0.5 else "cracked_nether_bricks" if n < 0.62 else "soul_soil" if n < 0.78 else "blackstone"
            if growth(x, z) > 0.72:
                b = "crimson_nylium"
                r = rnd.random()
                if r < 0.3: g.put(x, 1, z, "crimson_roots")
                elif r < 0.4: g.put(x, 1, z, "nether_sprouts")
                elif r < 0.44: g.put(x, 1, z, "crimson_fungus")
            if rnd.random() < 0.02: b = "shroomlight"
        g.put(x, 0, z, b)
    # keep wall, crenellated, with arched gates
    for x in range(-10, 11):
        for z in range(-10, 11):
            if max(abs(x), abs(z)) != 9: continue
            t = z if abs(x) == 9 else x
            gate = abs(t) <= 2 and min(abs(x), abs(z)) <= 2
            for y in range(1, 6):
                if gate and y <= 4:
                    if abs(t) == 2 and y == 4:
                        if abs(x) == 9: f = "south" if t > 0 else "north"
                        else: f = "east" if t > 0 else "west"
                        g.put(x, y, z, f"nether_brick_stairs[facing={f},half=top]", force=True)
                    else: g.put(x, y, z, "air", force=True)
                    continue
                b = "red_nether_bricks" if gate else rnd.choices(["nether_bricks", "cracked_nether_bricks", "red_nether_bricks"], [7, 2, 1])[0]
                g.put(x, y, z, b, force=True)
            if t % 2 == 0: g.put(x, 6, z, "nether_bricks", force=True)
    for sx in (-1, 1):   # corner towers
        for sz in (-1, 1):
            for x in range(9 * sx - 1, 9 * sx + 2):
                for z in range(9 * sz - 1, 9 * sz + 2):
                    for y in range(1, 8): g.put(x, y, z, "red_nether_bricks")
                    if (x + z) % 2 == 0 and (x, z) != (9 * sx, 9 * sz): g.put(x, 8, z, "red_nether_bricks")
            g.put(9 * sx, 8, 9 * sz, "soul_campfire[lit=true]")
            g.put(6 * sx, 1, 6 * sz, "nether_brick_fence")   # braziers in the courtyard
            g.put(6 * sx, 2, 6 * sz, "soul_campfire[lit=true]")
    for (x, z, f) in ((8, 5, "west"), (8, -5, "west"), (-8, 5, "east"), (-8, -5, "east"), (5, 8, "north"), (-5, 8, "north"),
                      (5, -8, "south"), (-5, -8, "south")):
        g.put(x, 3, z, f"soul_wall_torch[facing={f}]")
        ox, oz = DIRS[f]
        g.put(x - 2 * ox, 3, z - 2 * oz, f"soul_wall_torch[facing={ {'west': 'east', 'east': 'west', 'north': 'south', 'south': 'north'}[f] }]")
    # fenced lava pools
    for (cx, cz) in ((17, -17), (-17, 17), (26, 9), (-26, -9), (9, -26), (-9, 26)):
        for x in range(cx - 2, cx + 3):
            for z in range(cz - 2, cz + 3):
                if max(abs(x - cx), abs(z - cz)) <= 1: g.put(x, 0, z, "lava")
                else:
                    g.put(x, 0, z, "nether_bricks")
                    g.put(x, 1, z, "nether_brick_fence")
        for (x, z) in ((cx - 2, cz - 2), (cx + 2, cz + 2)): g.put(x, 2, z, "soul_lantern")
    # basalt columns with blackstone skirts
    for n, (x, z) in enumerate(((14, 4), (14, -4), (-14, 4), (-14, -4), (4, 14), (-4, 14), (4, -14), (-4, -14),
                                (24, 24), (-24, -24), (24, -20), (-20, 24), (27, -2), (-27, 2), (2, 27), (-2, -27))):
        h = [3, 5, 4, 6, 5, 3, 6, 4, 7, 6, 5, 7, 4, 5, 6, 4][n]
        for y in range(1, h + 1): g.put(x, y, z, "polished_basalt[axis=y]")
        g.put(x, h + 1, z, "soul_lantern")
        for (ox, oz) in DIRS.values():
            if rnd.random() < 0.7: g.put(x + ox, 1, z + oz, "blackstone_slab[type=bottom]")
    # giant ribcage (north-west)
    for x in range(-19, -12): g.put(x, 1, -17, "bone_block[axis=x]")
    for x in (-18, -16, -14):
        for s in (-1, 1):
            for y in (1, 2, 3): g.put(x, y, -17 + 2 * s, "bone_block[axis=y]")
            g.put(x, 4, -17 + s, "bone_block[axis=z]")
    for z in (-18, -17, -16):
        for y in (1, 2): g.put(-20, y, z, "bone_block[axis=y]")
    g.put(-20, 3, -17, "bone_block[axis=x]")
    # ruined portal (south-east)
    frame = [(x, 1) for x in range(14, 18)] + [(x, 5) for x in (14, 15)] + [(x, y) for x in (14, 17) for y in (2, 3, 4)]
    for (x, y) in frame:
        if (x, y) == (17, 4): continue
        g.put(x, y, 16, "crying_obsidian" if rnd.random() < 0.3 else "obsidian")
    for (x, z) in ((13, 17), (18, 15), (16, 18)): g.put(x, 1, z, "gilded_blackstone")
    for (x, z) in ((15, 15), (18, 17)): g.put(x, 0, z, "netherrack"); g.put(x, 1, z, "fire")
    # buttresses with soul lanterns along the outer wall
    for (x, z), d, t in wall_sides():
        if t in (-24, -8, 8, 24):
            for y in range(1, 6): g.put(x, y, z, "red_nether_bricks")
            g.put(x, 6, z, "soul_lantern")
    return g


# ---------------------------------------------------------------------------------------------- Orbital Station
# Not a square courtyard: a wheel-shaped station. A round hub (the Arsenal and the spawns), four spoke corridors, and
# an outer ring corridor; everything else is space (a starfield you can see over the hull but never reach). Its mob
# windows sit in the outer hull, so it has its own mob points (ORBITAL_POINTS, on the ring).
HUB_R, RING_IN, RING_OUT, SPOKE_W = 11.5, 19.5, 30.5, 3   # walkable: d <= HUB_R, RING_IN <= d <= RING_OUT, |minor| <= SPOKE_W
ORBITAL_POINTS = [(round(28 * math.cos(math.radians(15 + 30 * k))), round(28 * math.sin(math.radians(15 + 30 * k)))) for k in range(12)]


def orbital_walk(x, z):
    d = math.hypot(x, z)
    if d <= HUB_R or RING_IN <= d <= RING_OUT: return True
    return d < RING_IN and min(abs(x), abs(z)) <= SPOKE_W


def orbital_hull(x, z):
    """A hull cell: not walkable, but next to a walkable one (8 neighbours)."""
    if orbital_walk(x, z): return False
    return any(orbital_walk(x + ox, z + oz) for ox in (-1, 0, 1) for oz in (-1, 0, 1))


def orbital(mob_points, spawns):
    rnd = random.Random(15)
    g = Grid(mob_points, spawns)
    stars = Noise(17, 2)
    E = R + 1
    hull = set()
    for x in range(-E, E + 1):
        for z in range(-E, E + 1):
            d = math.hypot(x, z)
            if orbital_walk(x, z):   # decks
                if d <= HUB_R:
                    b = "cyan_concrete" if int(d) in (3, 7, 11) else "smooth_quartz" if int(d) % 2 else "white_concrete"
                elif d >= RING_IN:
                    a = (math.degrees(math.atan2(z, x)) + 360) % 360
                    if abs(d - 25) < 0.5: b = "sea_lantern" if int(a) % 15 == 0 else "light_blue_concrete"   # a lit seam round the ring
                    else: b = "white_concrete" if int(a / 6) % 2 else "smooth_quartz"
                else:   # spokes: a lit strip down the middle
                    b = "sea_lantern" if min(abs(x), abs(z)) == 0 and int(d) % 4 == 0 else "light_blue_concrete" if min(abs(x), abs(z)) == 0 else "white_concrete"
                g.put(x, 0, z, b)
            elif orbital_hull(x, z):
                hull.add((x, z))
            else:   # space: black, with stars
                g.put(x, 0, z, "sea_lantern" if stars(x * 3, z * 3) > 0.93 else "black_concrete")
    # the hull: 6 high, viewports in the spoke walls and around the hub, barrier above so nobody jumps into space
    for (x, z) in hull:
        d = math.hypot(x, z)
        for y in range(1, 7):
            b = "white_concrete" if y <= 1 else "cyan_concrete" if y == 4 else "light_gray_concrete"
            if y in (2, 3) and RING_IN - 1 > d > HUB_R + 1 and (x + z) % 4 == 0: b = "light_blue_stained_glass"   # spoke viewports
            if y == 6 and (x * 7 + z * 3) % 9 == 0: b = "sea_lantern"
            g.b[(x, y, z)] = b
        for y in range(7, 31): g.b[(x, y, z)] = "barrier"
    # mob windows in the outer hull: bars where each mob point meets the hull, smoke behind them
    for (mx, mz) in mob_points:
        a = math.atan2(mz, mx)
        for k in (-1, 0, 1):
            tx, tz = -math.sin(a) * k, math.cos(a) * k
            wx, wz = round(31.3 * math.cos(a) + tx), round(31.3 * math.sin(a) + tz)
            if (wx, wz) not in hull: continue
            g.windows.append((wx, wz))
            for y in (1, 2, 3): g.b[(wx, y, wz)] = "iron_bars"
            bx, bz = round(32.4 * math.cos(a) + tx), round(32.4 * math.sin(a) + tz)
            if (bx, bz) not in hull and abs(bx) <= R + 1 and abs(bz) <= R + 1: g.b[(bx, 1, bz)] = "campfire[lit=true]"
    # the hub: a reactor (four columns on the diagonals) and consoles
    for (x, z) in ((6, 6), (-6, -6), (6, -6), (-6, 6)):
        for y in range(1, 4): g.put(x, y, z, "iron_block")
        g.put(x, 4, z, "sea_lantern"); g.put(x, 5, z, "end_rod[facing=up]")
    for (x, z, b) in ((8, 3, "observer[facing=up]"), (-8, -3, "crafter"), (3, -8, "observer[facing=up]"), (-3, 8, "crafter")):
        g.put(x, 1, z, b)
    # the ring: four glass lab pods on the diagonals, cargo crates, copper bulbs along the outer hull
    for k in range(4):
        a = math.radians(45 + 90 * k)
        cx, cz = round(25 * math.cos(a)), round(25 * math.sin(a))
        for x in range(cx - 2, cx + 3):
            for z in range(cz - 2, cz + 3):
                if not orbital_walk(x, z): continue
                edge = max(abs(x - cx), abs(z - cz)) == 2
                if edge:
                    door = abs(x - cx) <= 0 or abs(z - cz) <= 0
                    for y in range(1, 4):
                        if door and y <= 2: continue
                        g.put(x, y, z, "iron_block" if abs(x - cx) == 2 and abs(z - cz) == 2 else "light_blue_stained_glass_pane" if y in (2, 3) else "white_concrete")
                g.put(x, 4, z, "smooth_quartz_slab[type=bottom]")
        g.put(cx, 1, cz, "verdant_froglight"); g.put(cx + 1, 1, cz, "cauldron")
    for _ in range(26):
        a = rnd.uniform(0, 2 * math.pi); d = rnd.uniform(RING_IN + 1, RING_OUT - 1)
        x, z = round(d * math.cos(a)), round(d * math.sin(a))
        if not orbital_walk(x, z) or g.protected(x, z) or not g.empty(x, 1, z): continue
        if min(abs(x), abs(z)) <= 3: continue   # keep the spoke mouths open
        g.put(x, 1, z, f"{rnd.choice(['white', 'light_gray', 'orange', 'cyan'])}_shulker_box")
        if rnd.random() < 0.4: g.put(x, 2, z, f"{rnd.choice(['white', 'orange'])}_shulker_box")
    for (x, z) in hull:
        d = math.hypot(x, z)
        if d > RING_OUT and (x * 5 + z * 11) % 13 == 0:
            ix, iz = round(x * (d - 1) / d), round(z * (d - 1) / d)   # the deck cell just inside
            if orbital_walk(ix, iz) and not g.protected(ix, iz) and g.empty(ix, 4, iz): g.put(ix, 4, iz, "waxed_copper_bulb[lit=true]")
    return g


MAPS = {"ruins": ruins, "mine": mine, "neon": neon, "hellfort": hellfort, "orbital": orbital}


# ---------------------------------------------------------------------------------------------- output
def resolve(g, x, y, z, b):
    """Give fences, walls, panes and bars the connections the game would have given them."""
    if not (is_fence(b) or is_wall(b) or is_pane(b)) or "[" in b: return b
    def nb(d):
        ox, oz = DIRS[d]
        o = g.get(x + ox, y, z + oz)
        if o is None and (abs(x + ox) == R + 1 or abs(z + oz) == R + 1): return True   # barrier above the outer wall
        if is_full(o): return True
        if is_fence(b): return is_fence(o) and ("nether" in nm(o)) == ("nether" in nm(b))
        return is_wall(o) or is_pane(o)
    c = {d: nb(d) for d in DIRS}
    if is_wall(b):
        straight = (c["north"] and c["south"] and not c["east"] and not c["west"]) or (c["east"] and c["west"] and not c["north"] and not c["south"])
        up = not straight or g.get(x, y + 1, z) not in (None, "air")
        return f"{b}[up={str(up).lower()}," + ",".join(f"{d}={'low' if v else 'none'}" for d, v in c.items()) + "]"
    return f"{b}[" + ",".join(f"{d}={str(v).lower()}" for d, v in c.items()) + "]"


def commands(g, ox, oy, oz):
    """setblock/fill commands for the grid, shifted to the map's centre (ox, oy, oz). Solid blocks go first (bottom
    up), then blocks that rest on something (bottom up), then hanging ones (top down)."""
    groups = ([], [], [])
    for (x, y, z), b in g.b.items():
        b = resolve(g, x, y, z, b)
        hanging = "hanging=true" in b or "vertical_direction=down" in b
        groups[2 if hanging else 1 if any(s in nm(b) for s in ATTACHED) else 0].append((x, y, z, b))
    out = []
    for gi, items in enumerate(groups):
        rows = defaultdict(list)
        for (x, y, z, b) in items: rows[(y, z)].append((x, b))
        for (y, z) in sorted(rows, key=lambda k: (-k[0] if gi == 2 else k[0], k[1])):
            cells = sorted(rows[(y, z)])
            i = 0
            while i < len(cells):
                j = i
                while j + 1 < len(cells) and cells[j + 1][0] == cells[j][0] + 1 and cells[j + 1][1] == cells[i][1]: j += 1
                (x1, b), x2 = cells[i], cells[j][0]
                if x1 == x2: out.append(f"setblock {ox + x1} {oy + y} {oz + z} minecraft:{b}")
                else: out.append(f"fill {ox + x1} {oy + y} {oz + z} {ox + x2} {oy + y} {oz + z} minecraft:{b}")
                i = j + 1
    return out


def check(g, name):
    """Every mob window must have a walking route to the Arsenal, and the player spawns must be clear."""
    def passable(b): return b is None or any(s in nm(b) for s in PASSABLE)
    def blocked(x, z):
        b1, b2, b3 = g.get(x, 1, z), g.get(x, 2, z), g.get(x, 3, z)
        if b1 and (is_fence(b1) or is_wall(b1) or is_pane(b1) or any(s in nm(b1) for s in ("lava", "campfire", "pointed_dripstone", "fire"))): return True
        if g.get(x, 0, z) == "lava": return True
        if not passable(b2): return True
        return not passable(b1) and not passable(b3)
    for (sx, sz, _) in g.spawns:
        assert not blocked(sx, sz), f"{name}: spawn {sx},{sz} is blocked"
    seen, todo = {(0, 3)}, deque([(0, 3)])
    while todo:
        x, z = todo.popleft()
        for (ox, oz) in DIRS.values():
            n = (x + ox, z + oz)
            if abs(n[0]) <= R and abs(n[1]) <= R and n not in seen and not blocked(*n):
                seen.add(n); todo.append(n)
    for (mx, mz) in g.mob_points:
        assert (mx, mz) in seen, f"{name}: mob window {mx},{mz} can't reach the Arsenal"
    for (sx, sz, _) in g.spawns:
        assert (sx, sz) in seen, f"{name}: spawn {sx},{sz} is cut off"
    return len(seen)
