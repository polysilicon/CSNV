"""The rotating PvP arena maps (imported by build.py): iconic places from the characters' universes. The Colosseum
(arena_map.py) is map 1; these are the others, each built once at its own spot and swapped in by the rotation.

Coordinates are relative to a map's centre, y 0 = floor. Every map has the same frame: a square fighting floor
(-R..R), a themed outer wall (R + 1) with barrier above it up to a barrier lid at TOP + 1, and behind the wall a
rampart R + 2..R + 4 wide whose top (y WALL_H) is the spectators' walkway, closed in by an outer barrier ring at
R + 5. The eight player spawns are the same on every map unless a map says otherwise.
"""
import math
import random
from collections import defaultdict, deque
import outbreak_maps as om
from outbreak_maps import DIRS, Noise

R = 36           # floor half-size; the outer wall is at +-37
WALL_H = 7       # wall rows y 0..7; the walkway on the rampart is the top of y 7
TOP = 30         # barrier above the wall up to y TOP; the lid is at TOP + 1
E = R + 5        # half-size of everything (for clearing): the outer barrier ring
SPAWNS = [(28, 0, 90), (-28, 0, -90), (0, -28, 0), (0, 28, 180), (20, -20, 45), (-20, -20, -45), (20, 20, 135), (-20, 20, -135)]
# where spectators arrive (relative x, z, yaw), standing on the rampart at y WALL_H + 1
SPECTATE = [(R + 3, 0, 90), (-(R + 3), 0, -90), (0, R + 3, 180), (0, -(R + 3), 0)]
PASSABLE = om.PASSABLE + ("lily_pad", "dead_bush", "flower", "tulip", "mushroom", "sapling", "sugar_cane", "vine",
                          "snow", "seagrass", "moss_carpet", "large_fern", "tall_grass", "bush", "allium", "orchid")
ATTACHED = om.ATTACHED + ("lily_pad", "dead_bush", "sunflower", "tulip", "red_mushroom[", "brown_mushroom[", "sugar_cane",
                          "vine", "large_fern", "cactus", "moss_carpet", "lantern", "sea_pickle", "flower_pot", "allium", "orchid")
NOT_FULL = om.NOT_FULL + ("lily_pad", "dead_bush", "sunflower", "sugar_cane", "vine", "cactus", "leaves", "glass", "bars",
                          "lightning_rod", "brewing_stand", "flower_pot")


def nm(b): return b.split("[")[0].split("{")[0]
def is_full(b): return b is not None and not any(s in nm(b) for s in NOT_FULL)
def passable(b): return b is None or any(s in nm(b) for s in PASSABLE)


class MapGrid(om.Grid):
    """Grid out to the outer barrier ring; the player spawns are kept clear above the floor."""
    def __init__(self, spawns=SPAWNS):
        super().__init__([], spawns)
        self.labels = []   # (x, y, z, text component, yaw, scale): text_display signs
        self.raw = []      # extra relative fill commands: (x1, y1, z1, x2, y2, z2, block)

    def protected(self, x, z):
        return any(max(abs(x - sx), abs(z - sz)) <= 1 for (sx, sz, _) in self.spawns)

    def put(self, x, y, z, block, force=False):
        if abs(x) > E or abs(z) > E: return
        if y >= 1 and not force and max(abs(x), abs(z)) <= R and self.protected(x, z): return
        self.b[(x, y, z)] = block

    def label(self, x, y, z, text, yaw=0, scale=2.0): self.labels.append((x, y, z, text, yaw, scale))


# ---------------------------------------------------------------------------------------------- shared pieces
def frame(g, wall, deck, rail):
    """The outer wall (wall(x, y, z, t) per block, t = position along the wall), the rampart with its walkway (deck)
    and railing, and the barrier (as fills: above the wall, the lid and the outer ring)."""
    for x in range(-E, E + 1):
        for z in range(-E, E + 1):
            m = max(abs(x), abs(z))
            t = x if abs(z) >= abs(x) else z
            if m == R + 1:
                for y in range(WALL_H + 1): g.put(x, y, z, wall(x, y, z, t), force=True)
            elif R + 2 <= m <= R + 4:
                for y in range(WALL_H): g.put(x, y, z, wall(x, y, z, t), force=True)
                g.put(x, WALL_H, z, deck, force=True)
                if m == R + 4: g.put(x, WALL_H + 1, z, rail, force=True)
    a, b = R + 1, R + 5
    g.raw += [(-a, WALL_H + 1, -a, a, TOP, -a, "barrier"), (-a, WALL_H + 1, a, a, TOP, a, "barrier"),
              (-a, WALL_H + 1, -a, -a, TOP, a, "barrier"), (a, WALL_H + 1, -a, a, TOP, a, "barrier"),
              (-a, TOP + 1, -a, a, TOP + 1, a, "barrier"),
              (-b, 1, -b, b, WALL_H + 6, -b, "barrier"), (-b, 1, b, b, WALL_H + 6, b, "barrier"),
              (-b, 1, -b, -b, WALL_H + 6, b, "barrier"), (b, 1, -b, b, WALL_H + 6, b, "barrier")]


def floor(g, f):
    for x in range(-R, R + 1):
        for z in range(-R, R + 1): g.put(x, 0, z, f(x, z))


def building(g, x1, z1, x2, z2, h, wall, roof=None, inside=None, doors=(), pane=None, win_y=(2,), corner=None, trim=None):
    """A box building: walls on the edge y 1..h, door openings (side, along, width, height), windows every third block
    along each wall, an optional flat roof at y h + 1 and an optional floor inside."""
    gaps = set()
    for (side, at, w, dh) in doors:
        for k in range(-(w // 2), w - w // 2):
            for y in range(1, dh + 1):
                p = {"north": (at + k, z1), "south": (at + k, z2), "west": (x1, at + k), "east": (x2, at + k)}[side]
                gaps.add((p[0], y, p[1]))
    for x in range(x1, x2 + 1):
        for z in range(z1, z2 + 1):
            edge, cor = x in (x1, x2) or z in (z1, z2), x in (x1, x2) and z in (z1, z2)
            if inside and not edge: g.put(x, 0, z, inside)
            if roof: g.put(x, h + 1, z, roof)
            if not edge: continue
            along = x if z in (z1, z2) else z
            for y in range(1, h + 1):
                if (x, y, z) in gaps:
                    g.put(x, y, z, "air"); continue
                b = corner if (cor and corner) else trim if (trim and y == h) else wall
                if pane and not cor and y in win_y and along % 3 == 0: b = pane
                g.put(x, y, z, b)


def gable(g, x1, z1, x2, z2, y0, stair, ridge, end=None, axis="x", over=1):
    """A pitched roof over x1..x2 / z1..z2 starting at y0 (overhang `over`). axis = the direction the ridge runs.
    end: the block filling the triangular gable ends."""
    if axis == "x":
        lo, hi = z1 - over, z2 + over
        i = 0
        while lo + i <= hi - i:
            a, b = lo + i, hi - i
            for x in range(x1 - over, x2 + over + 1):
                if a == b: g.put(x, y0 + i, a, ridge)
                else:
                    g.put(x, y0 + i, a, f"{stair}[facing=south,half=bottom]"); g.put(x, y0 + i, b, f"{stair}[facing=north,half=bottom]")
            if end:
                for z in range(a + 1, b):
                    for x in (x1, x2): g.put(x, y0 + i, z, end)
            i += 1
    else:
        lo, hi = x1 - over, x2 + over
        i = 0
        while lo + i <= hi - i:
            a, b = lo + i, hi - i
            for z in range(z1 - over, z2 + over + 1):
                if a == b: g.put(a, y0 + i, z, ridge)
                else:
                    g.put(a, y0 + i, z, f"{stair}[facing=east,half=bottom]"); g.put(b, y0 + i, z, f"{stair}[facing=west,half=bottom]")
            if end:
                for x in range(a + 1, b):
                    for z in (z1, z2): g.put(x, y0 + i, z, end)
            i += 1


def cyl(g, cx, cz, r, y1, y2, block, hollow=False, top=None):
    for x in range(math.floor(cx - r) - 1, math.ceil(cx + r) + 2):
        for z in range(math.floor(cz - r) - 1, math.ceil(cz + r) + 2):
            d = math.hypot(x - cx, z - cz)
            if d > r + 0.3: continue
            for y in range(y1, y2 + 1):
                if hollow and d < r - 0.7 and y > y1 - 1 and (top is None or y < y2): continue
                g.put(x, y, z, block(x, y, z) if callable(block) else block)


def tree(g, x, z, h=5, log="oak_log", leaves="oak_leaves[persistent=true]", r=2, vines=False, rnd=None):
    for y in range(1, h + 1): g.put(x, y, z, log)
    for ox in range(-r, r + 1):
        for oz in range(-r, r + 1):
            for oy in (-1, 0, 1):
                if ox * ox + oz * oz + oy * oy * 2 > r * r + 1 or (ox == 0 and oz == 0 and oy < 1): continue
                g.put(x + ox, h + oy, z + oz, leaves)
    g.put(x, h + 1, z, leaves)
    if vines and rnd:
        for ox in range(-r, r + 1):
            for oz in range(-r, r + 1):
                if (ox or oz) and rnd.random() < 0.3 and (x + ox, h - 1, z + oz) in g.b and "leaves" in g.b[(x + ox, h - 1, z + oz)]:
                    if (x + ox, h - 2, z + oz) not in g.b: g.put(x + ox, h - 2, z + oz, "vine[up=true]")


def car(g, x, z, color, axis="x", length=5):
    """A little car: wheels at the corners, a glass cabin in the middle, a roof."""
    for k in range(length):
        for w in (0, 1):
            cx, cz = (x + k, z + w) if axis == "x" else (x + w, z + k)
            end = k in (0, length - 1)
            g.put(cx, 1, cz, "black_concrete" if k in (1, length - 2) else f"{color}_concrete")
            if not end: g.put(cx, 2, cz, "light_gray_stained_glass" if 0 < k < length - 1 and k != 1 else f"{color}_concrete")
            if 1 < k < length - 1: g.put(cx, 3, cz, f"{color}_concrete")


def checker(x, y, z, a="brown_terracotta", b="orange_terracotta", s=2):
    return a if (x // s + y // s + z // s) % 2 else b


def sign_post(g, x, z, text, yaw, h=2, post="oak_fence", scale=1.0):
    for y in range(1, h + 1): g.put(x, y, z, post)
    g.label(x + 0.5, h + 1.2, z + 0.5, text, yaw, scale)


# ---------------------------------------------------------------------------------------------- Mustafar (Star Wars)
def mustafar():
    g = MapGrid()
    rnd, n1, n2 = random.Random(201), Noise(211, 7), Noise(212, 3)
    ra = lambda x, z: abs(z - (-12 + 4 * math.sin(x / 6)))       # east-west lava river
    rb = lambda x, z: abs(x - (13 + 4 * math.sin(z / 7)))        # north-south lava river
    bridges_a, bridges_b = (-24, -4, 22), (-26, 6, 26)

    def on_bridge(x, z):
        return (ra(x, z) < 3 and any(abs(x - b) <= 2 for b in bridges_a)) or (rb(x, z) < 3 and any(abs(z - b) <= 2 for b in bridges_b))

    def fl(x, z):
        lava = ra(x, z) < 1.7 or rb(x, z) < 1.7
        if lava and not on_bridge(x, z): return "lava"
        if lava: return "polished_blackstone_bricks"
        if min(ra(x, z), rb(x, z)) < 2.7: return "gilded_blackstone" if rnd.random() < 0.08 else "blackstone"   # cooled banks
        n = n1(x, z) + 0.3 * n2(x, z)
        return "smooth_basalt" if n < 0.5 else "blackstone" if n < 0.78 else "basalt" if n < 0.95 else "polished_blackstone"
    floor(g, fl)
    # bridge railings over the lava
    for x in range(-R, R + 1):
        for z in range(-R, R + 1):
            if g.get(x, 0, z) == "polished_blackstone_bricks" and (any(abs(x - b) == 2 for b in bridges_a) and ra(x, z) < 1.7 or
                                                                   any(abs(z - b) == 2 for b in bridges_b) and rb(x, z) < 1.7):
                g.put(x, 1, z, "polished_blackstone_wall")
    # the mining facility in the middle: dark halls, wide doors, a control deck on the roof
    building(g, -6, -5, 6, 5, 6, "polished_blackstone_bricks", roof="polished_blackstone", inside="polished_deepslate",
             doors=[("north", 0, 3, 3), ("south", 0, 3, 3), ("west", 0, 3, 3), ("east", 0, 3, 3)],
             pane="orange_stained_glass_pane", win_y=(3, 4), trim="gray_concrete")
    for (x, z) in ((-4, -3), (4, 3), (-4, 3), (4, -3)):
        g.put(x, 1, z, "polished_blackstone_slab[type=top]"); g.put(x, 2, z, "observer[facing=up]")
    for (x, z) in ((0, -2), (0, 2)): g.put(x, 1, z, "lodestone")
    g.put(0, 8, 0, "shroomlight"); g.put(0, 9, 0, "lightning_rod")
    for x in range(-6, 7):
        for z in (-5, 5): g.put(x, 8, z, "polished_blackstone_wall")
    # collector towers along the rivers, their arms holding lava buckets out over the lava
    for (tx, tz, dx, dz) in ((18, -16, 0, 1), (-22, -5, 0, -1), (8, 20, 1, 0), (22, 12, -1, 0)):
        for y in range(1, 12):
            for (ox, oz) in ((0, 0), (1, 0), (0, 1), (1, 1)):
                g.put(tx + ox, y, tz + oz, "gray_concrete" if y % 4 == 0 else "polished_blackstone_bricks")
        for k in range(1, 6):
            g.put(tx + dx * k, 11, tz + dz * k, "polished_blackstone_slab[type=top]")
        ax, az = tx + dx * 5, tz + dz * 5
        for y in range(7, 11): g.put(ax, y, az, "iron_bars")
        g.put(ax, 6, az, "lava_cauldron")
        g.put(tx, 12, tz, "shroomlight"); g.put(tx + 1, 12, tz + 1, "lightning_rod")
    # basalt spires
    placed = 0
    while placed < 16:
        x, z = rnd.randint(-33, 33), rnd.randint(-33, 33)
        if max(abs(x), abs(z)) < 9 or min(ra(x, z), rb(x, z)) < 4 or g.protected(x, z) or any(abs(x - sx) + abs(z - sz) < 5 for (sx, sz, _) in g.spawns): continue
        h = rnd.randint(4, 11)
        for y in range(1, h + 1):
            r = 1 if y < h * 0.5 else 0
            for ox in range(-r, r + 1):
                for oz in range(-r, r + 1):
                    if r and abs(ox) + abs(oz) == 2: continue
                    g.put(x + ox, y, z + oz, "basalt" if (y + ox) % 3 else "blackstone")
        g.put(x, h + 1, z, "magma_block")
        placed += 1
    # a landing pad
    for x in range(-27, -13):
        for z in range(9, 23):
            d = math.hypot(x + 20, z - 16)
            if d <= 5.5: g.put(x, 0, z, "yellow_concrete" if 4.6 < d else "smooth_stone" if (x + z) % 2 else "light_gray_concrete")
    for k in range(8):
        a = math.radians(45 * k)
        g.put(round(-20 + 6 * math.cos(a)), 1, round(16 + 6 * math.sin(a)), "ochre_froglight")
    g.label(-19.5, 1.6, 16.5, {"text": "LANDING PAD", "color": "yellow", "bold": True}, 0, 1.2)

    def wall(x, y, z, t):
        if (t * 3 + y * 7) % 13 == 0: return "magma_block"
        if y == WALL_H: return "polished_blackstone_bricks"
        if y == 4 and t % 6 == 0: return "orange_stained_glass"
        return "blackstone" if (t + y) % 5 else "basalt"
    frame(g, wall, "polished_blackstone", "polished_blackstone_wall")
    return g


# ---------------------------------------------------------------------------------------------- Shrek's swamp
def swamp():
    g = MapGrid()
    rnd, n1, wet = random.Random(301), Noise(311, 6), Noise(312, 7)
    house = (-10, -15)

    def fl(x, z):
        if math.hypot(x - house[0], z - house[1]) < 7: return "coarse_dirt" if (x + z) % 3 else "mud"
        if wet(x, z) > 0.74 and not g.protected(x, z): return "water"
        n = n1(x, z)
        return "grass_block" if n < 0.45 else "podzol" if n < 0.6 else "mud" if n < 0.72 else "moss_block" if n < 0.86 else "rooted_dirt"
    floor(g, fl)
    for x in range(-R, R + 1):
        for z in range(-R, R + 1):
            b = g.get(x, 0, z)
            if b == "water":
                if rnd.random() < 0.3: g.put(x, 1, z, "lily_pad")
            else:
                near_water = any(g.get(x + ox, 0, z + oz) == "water" for (ox, oz) in DIRS.values())
                if near_water and b in ("grass_block", "mud", "podzol") and b != "mud" and rnd.random() < 0.25:
                    for y in range(1, rnd.randint(2, 3) + 1): g.put(x, y, z, "sugar_cane")
                elif b == "podzol" and rnd.random() < 0.05: g.put(x, 1, z, rnd.choice(["red_mushroom", "brown_mushroom"]))
                elif b in ("grass_block", "moss_block") and rnd.random() < 0.12: g.put(x, 1, z, rnd.choice(["short_grass", "fern", "short_grass"]))
    # a muddy path from Shrek's door out to the middle and on to the east
    for (a, b) in (((-10, -9), (0, 0)), ((0, 0), (30, 4)), ((0, 0), (-6, 30))):
        for (x, z) in om.line(a[0], a[1], b[0], b[1]):
            for ox in (-1, 0, 1):
                if g.get(x + ox, 0, z) != "water": g.put(x + ox, 0, z, "dirt_path" if ox == 0 or rnd.random() < 0.6 else "packed_mud")
    # Shrek's house: a giant hollow tree stump with a mossy roof, round windows and a smoking chimney
    hx, hz = house
    for x in range(hx - 6, hx + 7):
        for z in range(hz - 6, hz + 7):
            d = math.hypot(x - hx, z - hz)
            if d <= 5.4:
                g.put(x, 0, z, "spruce_planks")
                for y in range(1, 8):
                    if d > 4.4:
                        door = z > hz and abs(x - hx) <= 1 and y <= 3
                        window = y in (3, 4) and abs(z - hz) <= 0 and abs(x - hx) > 4
                        g.put(x, y, z, "air" if door else "glass_pane" if window else ("oak_log" if (x * 7 + z * 3) % 5 else "stripped_oak_log"))
                g.put(x, 8, z, "moss_block")
                if d <= 4.4 and rnd.random() < 0.4: g.put(x, 9, z, rnd.choice(["moss_carpet", "short_grass"]))
            elif d <= 6.2 and rnd.random() < 0.4 and not (z > hz and abs(x - hx) <= 2):
                g.put(x, 1, z, "moss_carpet")
    for y in range(8, 12): g.put(hx + 2, y, hz - 2, "cobblestone")
    g.put(hx + 2, 12, hz - 2, "campfire[lit=true]")
    for (x, z, b) in ((hx - 2, hz - 2, "crafting_table"), (hx + 2, hz + 1, "barrel[facing=up]"), (hx - 3, hz + 1, "cauldron"),
                      (hx, hz - 3, "red_bed[facing=north,part=head]")):
        g.put(x, 1, z, b)
    g.put(hx, 1, hz - 2, "red_bed[facing=north,part=foot]")
    g.put(hx, 6, hz, "lantern[hanging=true]")
    # the outhouse
    ox_, oz_ = 8, -24
    building(g, ox_ - 1, oz_ - 1, ox_ + 1, oz_ + 1, 3, "spruce_planks", roof="spruce_slab[type=bottom]", doors=[("west", oz_, 1, 2)], corner="spruce_log")
    g.label(ox_ - 1.1, 3.2, oz_ + 0.5, {"text": "OUTHOUSE", "color": "gold", "bold": True}, 90, 0.6)
    # "Beware Ogre" signs
    for (x, z, yaw) in ((22, 2, 90), (-4, 26, 180), (-24, -6, -90), (14, -12, 45)):
        sign_post(g, x, z, [{"text": "BEWARE\n", "color": "dark_red", "bold": True}, {"text": "OGRE!", "color": "red", "bold": True}], yaw, scale=0.9)
    # swamp trees with vines, fallen logs, a camp fire with log seats
    spots = [(-28, -28), (26, -30), (30, 22), (-30, 10), (-16, 28), (12, 30), (24, -6), (-26, -12), (16, 18), (-6, 12), (28, -18), (2, -16)]
    for (x, z) in spots:
        g.put(x, 0, z, "grass_block")
        tree(g, x, z, h=rnd.randint(5, 7), log="oak_log", r=3, vines=True, rnd=rnd)
    for (x, z, ax, n) in ((6, 10, "x", 5), (-20, 22, "z", 4), (18, -26, "x", 4)):
        for k in range(n): g.put(x + (k if ax == "x" else 0), 1, z + (k if ax == "z" else 0), f"oak_log[axis={ax}]")
        g.put(x, 2, z, "moss_carpet")
    g.put(10, 1, 4, "campfire[lit=true]")
    for (x, z, ax) in ((8, 4, "z"), (12, 4, "z"), (10, 2, "x"), (10, 6, "x")): g.put(x, 1, z, f"spruce_log[axis={ax}]")
    # a big red mushroom or two
    for (x, z) in ((-30, -20), (30, 30)):
        for y in range(1, 5): g.put(x, y, z, "mushroom_stem")
        for ox in range(-2, 3):
            for oz in range(-2, 3):
                if abs(ox) + abs(oz) < 4: g.put(x + ox, 5, z + oz, "red_mushroom_block")
        g.put(x, 6, z, "red_mushroom_block")

    def wall(x, y, z, t):   # a log palisade, leaves on top
        if y == WALL_H: return "oak_leaves[persistent=true]" if max(abs(x), abs(z)) == R + 1 else "spruce_planks"
        return "spruce_log" if t % 3 else "stripped_spruce_log"
    frame(g, wall, "spruce_planks", "spruce_fence")
    return g


# ---------------------------------------------------------------------------------------------- Tegridy Farms (South Park)
def tegridy():
    g = MapGrid()
    rnd, n1 = random.Random(401), Noise(411, 5)

    def fl(x, z):
        if abs(x) <= 2 and z > -16: return "dirt_path"                 # the farm road
        if z < -12: return "coarse_dirt" if n1(x, z) > 0.62 else "grass_block" if n1(x, z) > 0.3 else "gravel"   # the yard
        return "grass_block"
    floor(g, fl)
    # the fields: rows of "crops" (tall ferns) between dirt furrows, fenced, with gaps to walk through
    for (x1, x2, z1, z2) in ((-34, -6, 4, 34), (6, 34, 4, 34)):
        for x in range(x1, x2 + 1):
            for z in range(z1, z2 + 1):
                if z % 3 == 0: g.put(x, 0, z, "coarse_dirt"); continue
                if x in (x1, x2) or z in (z1, z2) or abs(x - (x1 + x2) // 2) <= 1: continue   # paths round and through
                g.put(x, 0, z, "grass_block")
                g.put(x, 1, z, "large_fern[half=lower]"); g.put(x, 2, z, "large_fern[half=upper]")
        for x in range(x1, x2 + 1):
            if abs(x - (x1 + x2) // 2) > 1: g.put(x, 1, z1 - 1, "oak_fence")
    # the farmhouse: white siding, a porch, a dark gabled roof
    building(g, -16, -30, -4, -20, 7, "white_concrete", inside="spruce_planks", doors=[("south", -10, 1, 2), ("east", -25, 1, 2)],
             pane="glass_pane", win_y=(2, 5), corner="stripped_spruce_log")
    for x in range(-15, -4):
        for z in range(-29, -20): g.put(x, 4, z, "spruce_planks")   # upstairs floor
    for k, y in enumerate(range(1, 4)): g.put(-6, y, -28 + k, f"spruce_stairs[facing=south]")
    for z in range(-28, -25):
        for y in range(4, 5): g.put(-6, y, z, "air")
    gable(g, -16, -30, -4, -20, 8, "dark_oak_stairs", "dark_oak_planks", end="white_concrete", axis="x")
    for x in range(-16, -3):   # porch
        for z in (-19, -18, -17):
            g.put(x, 0, z, "spruce_planks")
            g.put(x, 4, z, "spruce_slab[type=bottom]")
        if x % 3 == 2:
            for y in range(1, 4): g.put(x, y, -17, "spruce_fence")
    g.put(-13, 1, -19, "spruce_stairs[facing=north]"); g.put(-7, 1, -19, "spruce_stairs[facing=north]")
    # the red barn with white trim, hay inside, a big door
    building(g, 6, -32, 16, -18, 6, "red_terracotta", inside="spruce_planks", doors=[("south", 11, 3, 4), ("north", 11, 3, 4)],
             corner="white_concrete", trim="white_concrete")
    gable(g, 6, -32, 16, -18, 7, "spruce_stairs", "spruce_planks", end="red_terracotta", axis="z")
    for (x, z) in ((7, -31), (8, -31), (7, -30), (15, -31), (15, -30), (14, -31), (7, -20), (15, -19)):
        g.put(x, 1, z, "hay_block")
    g.put(7, 2, -31, "hay_block"); g.put(15, 2, -31, "hay_block")
    g.label(11.5, 9.5, -16.9, {"text": "TEGRIDY", "color": "dark_green", "bold": True}, 0, 1.6)
    # the silo
    cyl(g, 25, -9, 3.2, 1, 15, lambda x, y, z: "iron_block" if y % 5 == 0 else "light_gray_concrete", hollow=True)
    cyl(g, 25, -9, 2.4, 16, 16, "white_concrete"); g.put(25, 17, -9, "white_concrete")
    for y in (1, 2): g.put(25, y, -12, "air")
    # the farm gate: TEGRIDY FARMS over the road
    for x in (-4, 4):
        for y in range(1, 8): g.put(x, y, 2, "spruce_log")
    for x in range(-4, 5): g.put(x, 7, 2, "stripped_spruce_log[axis=x]")
    g.label(0.5, 8.1, 2.55, [{"text": "TEGRIDY ", "color": "green", "bold": True}, {"text": "FARMS", "color": "dark_green", "bold": True}], 0, 2.0)
    g.label(0.5, 8.1, 2.45, [{"text": "TEGRIDY ", "color": "green", "bold": True}, {"text": "FARMS", "color": "dark_green", "bold": True}], 180, 2.0)
    # the grow tent and a greenhouse
    building(g, -32, -12, -22, -4, 4, "white_wool", roof="white_wool", doors=[("east", -8, 1, 2)], inside="coarse_dirt")
    for x in range(-31, -22, 2):
        for z in range(-11, -4, 2):
            g.put(x, 1, z, "large_fern[half=lower]"); g.put(x, 2, z, "large_fern[half=upper]")
    for (x, z) in ((-29, -8), (-25, -8)): g.put(x, 4, z, "shroomlight")
    # Randy's tractor
    tx, tz = 22, -2
    for k in range(4):
        for w in (0, 1, 2):
            g.put(tx + k, 1, tz + w, "black_concrete" if k in (0, 3) and w != 1 else "green_concrete")
    for w in (0, 1, 2): g.put(tx + 3, 2, tz + w, "green_concrete")
    g.put(tx + 1, 2, tz + 1, "dark_oak_stairs[facing=west]"); g.put(tx, 2, tz + 1, "iron_bars"); g.put(tx, 3, tz + 1, "iron_bars")
    # hay bales, barrels, a scarecrow
    for (x, z) in ((-2, -10), (3, -11), (-3, -14), (20, 2)): g.put(x, 1, z, "hay_block")
    g.put(0, 1, 18, "oak_fence"); g.put(0, 2, 18, "hay_block"); g.put(0, 3, 18, "carved_pumpkin[facing=north]")

    def wall(x, y, z, t):
        if y == WALL_H: return "hay_block"
        return "stripped_spruce_log" if t % 4 == 0 else "spruce_planks"
    frame(g, wall, "spruce_planks", "oak_fence")
    return g


# ---------------------------------------------------------------------------------------------- Quahog (Family Guy)
def quahog():
    g = MapGrid()
    rnd = random.Random(501)

    def fl(x, z):
        ax, az = abs(x), abs(z)
        if az <= 4 or ax <= 4:   # Spooner Street (east-west) and the cross street
            if az <= 4 and ax <= 4:
                return "white_concrete" if (ax in (3, 4) or az in (3, 4)) and (x + z) % 2 == 0 else "gray_concrete"
            if az == 0 and ax > 6 and x % 4 < 2: return "yellow_concrete"
            if ax == 0 and az > 6 and z % 4 < 2: return "yellow_concrete"
            return "gray_concrete"
        if az <= 6 or ax <= 6: return "smooth_stone"   # sidewalks
        return "grass_block"
    floor(g, fl)
    # the Griffin house: blue-grey siding, white trim, red door, grey gabled roof
    building(g, -30, -18, -12, -10, 8, "light_blue_terracotta", inside="oak_planks", doors=[("south", -21, 1, 2), ("north", -21, 1, 2)],
             pane="glass_pane", win_y=(2, 6), corner="white_concrete")
    for x in range(-29, -12):
        for z in range(-17, -10): g.put(x, 4, z, "oak_planks")
    for k in range(4): g.put(-14, 1 + k, -16 + k, "oak_stairs[facing=south]")
    for z in (-16, -15, -14): g.put(-14, 4, z, "air")
    g.put(-22, 1, -10, "red_concrete"); g.put(-22, 2, -10, "red_concrete"); g.put(-20, 1, -10, "red_concrete"); g.put(-20, 2, -10, "red_concrete")
    g.put(-21, 3, -10, "red_concrete")
    gable(g, -30, -18, -12, -10, 9, "deepslate_tile_stairs", "deepslate_tiles", end="light_blue_terracotta", axis="x")
    for z in (-9, -8, -7): g.put(-21, 0, z, "smooth_stone")
    g.label(-20.5, 4.2, -8.9, {"text": "31 SPOONER ST", "color": "white", "bold": True}, 0, 0.8)
    # Quagmire's house next door
    building(g, 10, -18, 26, -10, 7, "birch_planks", inside="oak_planks", doors=[("south", 18, 1, 2)], pane="glass_pane", win_y=(2, 5), corner="stripped_birch_log")
    gable(g, 10, -18, 26, -10, 8, "dark_oak_stairs", "dark_oak_planks", end="birch_planks", axis="x")
    g.label(18.5, 3.5, -8.9, {"text": "Giggity!", "color": "gold", "italic": True}, 0, 0.8)
    # Joe's house over the road, with its ramp
    building(g, -30, 10, -12, 18, 7, "light_gray_terracotta", inside="oak_planks", doors=[("north", -21, 1, 2)], pane="glass_pane", win_y=(2, 5), corner="white_concrete")
    gable(g, -30, 10, -12, 18, 8, "stone_brick_stairs", "stone_bricks", end="light_gray_terracotta", axis="x")
    g.put(-21, 1, 9, "smooth_stone_slab[type=bottom]"); g.put(-22, 1, 9, "smooth_stone_slab[type=bottom]"); g.put(-20, 1, 9, "smooth_stone_slab[type=bottom]")
    # the Drunken Clam
    building(g, 10, 9, 30, 21, 6, "bricks", roof="dark_oak_planks", inside="spruce_planks", doors=[("north", 16, 2, 3), ("west", 15, 1, 2)],
             pane="glass_pane", win_y=(2, 3), trim="stripped_dark_oak_log")
    for x in range(10, 31): g.put(x, 4, 8, "green_wool") if x % 2 else g.put(x, 4, 8, "white_wool")
    for x in range(12, 28): g.put(x, 1, 18, "stripped_dark_oak_log[axis=x]")
    for x in range(12, 28, 3): g.put(x, 2, 18, "flower_pot")
    for (x, z) in ((13, 12), (19, 12), (25, 14), (22, 11)): g.put(x, 1, z, "oak_fence"); g.put(x, 2, z, "oak_pressure_plate")
    for x in (12, 14, 16): g.put(x, 1, 20, "barrel[facing=up]")
    g.label(20.5, 5.0, 7.9, [{"text": "THE DRUNKEN ", "color": "gold", "bold": True}, {"text": "CLAM", "color": "aqua", "bold": True}], 180, 1.6)
    # parked cars, lamp posts, a hydrant, trees and fences in the yards
    for (x, z, c) in ((-18, -4, "red"), (12, 3, "blue"), (-30, 3, "white"), (22, -4, "lime")):
        car(g, x, z, c)
    for x in (-32, -16, 10, 26):
        for z in (-6, 6):
            for y in range(1, 5): g.put(x, y, z, "dark_oak_fence")
            g.put(x, 5, z, "lantern")
    g.put(8, 1, -6, "red_nether_brick_wall"); g.put(-8, 1, 6, "red_nether_brick_wall")
    for (x, z) in ((-32, -30), (-8, -30), (14, -32), (32, -26), (-34, 30), (-8, 32), (14, 32), (34, 28)):
        tree(g, x, z, h=5, r=2)
    for x in range(-36, -6):
        if abs(x + 20) > 2: g.put(x, 1, -26, "oak_fence")
    for x in range(6, 37):
        if abs(x - 20) > 2: g.put(x, 1, 26, "oak_fence")
    sign_post(g, 5, -5, [{"text": "SPOONER ST", "color": "white", "bold": True}], 45, h=3, post="iron_bars", scale=0.7)

    def wall(x, y, z, t):   # tall hedges on a stone base
        if y <= 1 or max(abs(x), abs(z)) > R + 1: return "stone_bricks"
        return "oak_leaves[persistent=true]"
    frame(g, wall, "smooth_stone", "stone_brick_wall")
    return g


# ---------------------------------------------------------------------------------------------- Bikini Bottom (SpongeBob)
def bikini():
    g = MapGrid()
    rnd, n1 = random.Random(601), Noise(611, 6)

    def fl(x, z):
        n = n1(x, z)
        if abs(x) <= 2 and -10 < z < 10 or abs(z) <= 2 and abs(x) < 10: return "smooth_sandstone"
        return "sand" if n < 0.55 else "sandstone" if n < 0.7 else "smooth_sandstone" if n < 0.85 else "gravel"
    floor(g, fl)
    # SpongeBob's pineapple
    px, pz = -16, -16
    for y in range(1, 11):
        r = 4.2 * math.sin(math.pi * (y + 1) / 13) + 0.5
        for x in range(px - 5, px + 6):
            for z in range(pz - 5, pz + 6):
                d = math.hypot(x - px, z - pz)
                if d > r: continue
                if d < r - 1 and y < 10: continue
                door = z > pz and abs(x - px) <= 0 and y <= 2
                window = y in (5, 6) and abs(z - pz) <= 0
                b = "brown_terracotta" if (y + round(math.degrees(math.atan2(z - pz, x - px)) / 30)) % 3 == 0 else "orange_terracotta"
                g.put(x, y, z, "air" if door else "light_blue_stained_glass" if window else b)
    for k in range(10):   # the leafy crown
        a = math.radians(36 * k)
        for s in range(1, 4):
            g.put(round(px + s * 0.8 * math.cos(a)), 10 + s, round(pz + s * 0.8 * math.sin(a)), "lime_concrete" if s < 3 else "green_concrete")
    g.put(px, 11, pz, "green_concrete"); g.put(px, 12, pz, "lime_concrete")
    g.put(px, 1, pz - 1, "yellow_bed[facing=north,part=foot]"); g.put(px, 1, pz - 2, "yellow_bed[facing=north,part=head]")
    # Squidward's moai head
    sx, sz = 0, -16
    for x in range(sx - 3, sx + 4):
        for z in range(sz - 3, sz + 2):
            edge = x in (sx - 3, sx + 3) or z in (sz - 3, sz + 1)
            for y in range(1, 12):
                if edge: g.put(x, y, z, "cyan_terracotta" if y < 11 else "light_gray_terracotta")
            g.put(x, 12, z, "light_gray_terracotta")
    for y in range(4, 8): g.put(sx, y, sz + 2, "cyan_terracotta")     # the nose
    g.put(sx, 8, sz + 2, "cyan_terracotta")
    for x in range(sx - 3, sx + 4): g.put(x, 9, sz + 2, "cyan_terracotta")   # the brow
    for x in (sx - 2, sx + 2): g.put(x, 7, sz + 1, "light_blue_stained_glass")
    for y in (1, 2): g.put(sx, y, sz + 1, "air")
    g.put(sx, 3, sz + 1, "spruce_planks")
    # Patrick's rock
    rx, rz = 14, -15
    for x in range(rx - 5, rx + 6):
        for z in range(rz - 5, rz + 6):
            for y in range(1, 6):
                if math.hypot(x - rx, z - rz) ** 2 + (y * 1.1) ** 2 <= 24: g.put(x, y, z, "brown_terracotta" if (x + y + z) % 4 else "terracotta")
    g.put(rx, 6, rz, "lightning_rod"); g.put(rx + 1, 6, rz, "spruce_fence")
    # the Krusty Krab: a lobster trap of planks and logs, portholes, double doors facing the middle
    building(g, -12, 12, 12, 26, 7, "spruce_planks", roof="spruce_planks", inside="smooth_stone", doors=[("north", 0, 3, 3)],
             pane="light_blue_stained_glass", win_y=(3, 4), corner="spruce_log", trim="stripped_spruce_log")
    for x in (-12, -8, -4, 4, 8, 12):
        for y in range(1, 9): g.put(x, y, 12, "spruce_log")
    for z in range(12, 27, 4):
        g.put(-13, 8, z, "spruce_log[axis=x]"); g.put(13, 8, z, "spruce_log[axis=x]")
    for x in range(-8, 9): g.put(x, 1, 20, "stripped_spruce_log[axis=x]")
    for (x, z) in ((-8, 16), (-3, 16), (4, 16), (8, 16)): g.put(x, 1, z, "barrel[facing=up]")
    for x in (-6, -2, 2, 6): g.put(x, 1, 24, "smoker[facing=north]")
    for y in range(9, 14): g.put(0, y, 19, "spruce_fence")
    g.put(0, 14, 19, "red_banner[rotation=0]")
    g.label(0.5, 8.6, 11.9, [{"text": "THE ", "color": "red"}, {"text": "KRUSTY KRAB", "color": "red", "bold": True}], 180, 2.2)
    # the Chum Bucket across the way
    cyl(g, 27, 9, 4, 1, 6, lambda x, y, z: "black_concrete" if y in (5, 6) else "light_gray_concrete", hollow=True)
    for y in (1, 2): g.put(23, y, 9, "air")
    for (ox, oz) in ((0, 0), (1, 0), (-1, 0)): g.put(27 + ox, 7, 9 + oz, "iron_bars")
    g.label(22.4, 7.2, 9.5, {"text": "CHUM BUCKET", "color": "dark_green", "bold": True}, 90, 1.0)
    # coral "trees", tube sponges and floating jellyfish
    colours = ["magenta", "pink", "orange", "yellow", "lime", "purple", "red"]
    cor = [(-30, -30), (-30, 4), (-28, 30), (-6, 30), (30, -30), (32, -6), (30, 30), (-6, -32), (8, -30), (-20, 4), (20, 2), (6, 6)]
    for (x, z) in cor:
        c = rnd.choice(colours)
        h = rnd.randint(3, 6)
        for y in range(1, h + 1): g.put(x, y, z, f"{c}_concrete")
        for (ox, oz) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for y in range(h - 1, h + rnd.randint(1, 3)): g.put(x + ox * 2, y, z + oz * 2, f"{c}_concrete")
            g.put(x + ox, h - 1, z + oz, f"{c}_concrete")
    for k in range(14):
        x, z, y = rnd.randint(-32, 32), rnd.randint(-32, 32), rnd.randint(14, 24)
        for (ox, oz) in ((0, 0), (1, 0), (0, 1), (1, 1)): g.put(x + ox, y, z + oz, "pink_stained_glass", force=True)
        g.put(x, y - 1, z, "pink_stained_glass_pane", force=True); g.put(x + 1, y - 1, z + 1, "pink_stained_glass_pane", force=True)

    def wall(x, y, z, t):
        if y == 3 and t % 8 == 0: return "sea_lantern"
        if y == WALL_H: return "prismarine_bricks"
        return "prismarine" if (t + y) % 4 else "dark_prismarine"
    frame(g, wall, "prismarine_bricks", "prismarine_wall")
    return g


# ---------------------------------------------------------------------------------------------- the Mushroom Kingdom (Mario)
MUSHROOM_SPAWNS = [(28, 0, 90), (-28, 0, -90), (0, -14, 0), (0, 28, 180), (20, -20, 45), (-20, -20, -45), (20, 20, 135), (-20, 20, -135)]


def mushroom():
    g = MapGrid(MUSHROOM_SPAWNS)
    rnd = random.Random(701)
    floor(g, lambda x, z: "grass_block" if abs(x) > 2 or z < -22 else "smooth_stone")
    for x in range(-R, R + 1):
        for z in range(-R, R + 1):
            if g.get(x, 0, z) == "grass_block" and rnd.random() < 0.06: g.put(x, 1, z, rnd.choice(["dandelion", "poppy", "short_grass", "short_grass"]))
    # Peach's castle at the north end: cream walls, red cone roofs, a stained-glass window over the door
    for x in range(-10, 11):
        for z in range(-34, -23):
            edge = x in (-10, 10) or z in (-34, -24)
            g.put(x, 0, z, "red_wool" if abs(x) <= 1 and z > -32 else "smooth_quartz")
            if not edge: continue
            for y in range(1, 11):
                door = z == -24 and abs(x) <= 1 and y <= 4
                window = z == -24 and abs(x) <= 1 and 6 <= y <= 9
                g.put(x, y, z, "air" if door else ("pink_stained_glass" if (x + y) % 2 else "yellow_stained_glass") if window else "white_concrete")
            if (x + z) % 2 == 0: g.put(x, 11, z, "white_concrete")
    for (cx, cz, r, h) in ((-10, -24, 2.2, 14), (10, -24, 2.2, 14), (-10, -34, 2.2, 14), (10, -34, 2.2, 14), (0, -29, 3.2, 18)):
        cyl(g, cx, cz, r, 1, h, "white_concrete")
        for k in range(5):   # cone roof
            cyl(g, cx, cz, max(r + 0.8 - k * (r + 0.8) / 5, 0.4), h + 1 + k, h + 1 + k, "red_concrete")
        g.put(cx, h + 6, cz, "gold_block")
    for x in range(-2, 3): g.put(x, 5, -23, "dark_oak_planks")
    g.put(0, 8, -23, "red_concrete")
    # warp pipes
    for (x, z, h) in ((-14, -6, 3), (14, -6, 4), (-24, 10, 2), (24, 10, 5), (-6, 22, 3), (8, 18, 2), (-30, -14, 4), (30, -14, 3), (0, 6, 2)):
        for ox in (-1, 0, 1):
            for oz in (-1, 0, 1):
                for y in range(1, h + 1):
                    g.put(x + ox, y, z + oz, "black_concrete" if y == h and ox == 0 and oz == 0 else "lime_concrete" if y == h else
                          "green_concrete" if ox == 1 else "lime_concrete")
    # floating rows of brick and ? blocks
    for (x, z, ax, pattern) in ((-6, -8, "x", "B?B?B"), (4, 12, "x", "B?BB"), (-20, -2, "z", "?B?"), (18, 2, "z", "B?B?"), (-12, 26, "x", "B??B")):
        for k, c in enumerate(pattern):
            p = (x + k, z) if ax == "x" else (x, z + k)
            g.put(p[0], 4, p[1], "bricks" if c == "B" else "yellow_glazed_terracotta[facing=south]")
    # green hills you can climb
    for (hx, hz, r, h) in ((-26, 30, 6, 5), (28, 30, 5, 4)):
        for x in range(hx - r, hx + r + 1):
            for z in range(hz - r, hz + r + 1):
                d = math.hypot(x - hx, z - hz)
                top = round(h * (1 - (d / (r + 0.5)) ** 2))
                for y in range(1, top + 1): g.put(x, y, z, "grass_block" if y == top else "dirt")
    # the end-of-level flagpole and a little brick castle
    for y in range(1, 2): g.put(30, y, -28, "stone_bricks")
    for y in range(2, 14): g.put(30, y, -28, "iron_bars")
    g.put(30, 14, -28, "emerald_block")
    for y in (11, 12): g.put(29, y, -28, "white_wool"); g.put(28, y, -28, "white_wool")
    building(g, -34, -9, -28, -3, 5, "bricks", doors=[("east", -6, 1, 2)], roof="bricks")
    for x in range(-34, -27, 2): g.put(x, 7, -9, "bricks"); g.put(x, 7, -3, "bricks")
    # round bushes and clouds overhead
    for (x, z) in ((-32, -2), (32, 4), (-8, 32), (12, 30), (-16, 14), (16, -18)):
        for (ox, oz, oy) in ((0, 0, 1), (1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (0, 0, 2)): g.put(x + ox, oy, z + oz, "azalea_leaves[persistent=true]")
    for k in range(9):
        x, z, y = rnd.randint(-30, 30), rnd.randint(-30, 30), rnd.randint(20, 27)
        for ox in range(-2, 3):
            for oz in range(-1, 2): g.put(x + ox, y, z + oz, "white_wool", force=True)
        g.put(x - 1, y + 1, z, "white_wool", force=True); g.put(x, y + 1, z, "white_wool", force=True)

    def wall(x, y, z, t):   # "ground" blocks
        if y == WALL_H: return "yellow_glazed_terracotta[facing=south]" if t % 6 == 0 else "bricks"
        return "bricks" if y >= 3 else "orange_terracotta" if (t // 2 + y) % 2 else "brown_terracotta"
    frame(g, wall, "smooth_stone", "stone_brick_wall")
    return g


# ---------------------------------------------------------------------------------------------- Springfield (The Simpsons)
def springfield():
    g = MapGrid()
    rnd, n1 = random.Random(801), Noise(811, 5)

    def fl(x, z):
        if z < -14 and x > -2: return "gray_concrete" if (x % 6 != 0 or z % 2) else "white_concrete"   # the plant's car park
        if abs(z + 2) <= 2: return "gray_concrete" if not (z == -2 and x % 4 < 2) else "yellow_concrete"   # the road
        if abs(z + 2) <= 3: return "smooth_stone"
        return "grass_block" if n1(x, z) < 0.8 else "coarse_dirt"
    floor(g, fl)
    # the power plant's two cooling towers (hollow, walk in at the bottom)
    for (cx, cz) in ((-12, -24), (-28, -12)):
        for y in range(1, 19):
            r = 3.8 + 2.2 * ((y - 12) / 12) ** 2
            for x in range(cx - 7, cx + 8):
                for z in range(cz - 7, cz + 8):
                    d = math.hypot(x - cx, z - cz)
                    if r - 1 < d <= r:
                        door = y <= 3 and z > cz and abs(x - cx) <= 1
                        g.put(x, y, z, "air" if door else "light_gray_concrete" if y % 6 else "white_concrete")
        g.put(cx, 1, cz, "verdant_froglight")
    # the plant building, a smokestack and the waste barrels
    building(g, 6, -34, 30, -24, 8, "light_gray_concrete", roof="gray_concrete", inside="polished_andesite",
             doors=[("south", 18, 3, 3), ("west", -29, 1, 2)], pane="lime_stained_glass_pane", win_y=(4, 5, 6), trim="white_concrete")
    for (x, z) in ((10, -30), (14, -30), (22, -30), (26, -30)):
        g.put(x, 1, z, "polished_andesite"); g.put(x, 2, z, "lever[face=floor,facing=north]")
    g.put(18, 1, -32, "smooth_stone"); g.put(18, 2, -32, "red_concrete")   # the big red button
    for y in range(9, 20): g.put(28, y, -32, "bricks")
    g.label(18.5, 10.2, -22.9, [{"text": "SPRINGFIELD NUCLEAR ", "color": "yellow", "bold": True}, {"text": "POWER PLANT", "color": "white", "bold": True}], 0, 1.4)
    for (x, z) in ((3, -16), (4, -17), (3, -18), (-4, -8), (26, -18), (27, -18), (26, -17), (33, -10)):
        g.put(x, 1, z, "verdant_froglight")
        if (x + z) % 3 == 0: g.put(x, 2, z, "verdant_froglight")
    # Kwik-E-Mart
    building(g, 8, 8, 24, 17, 5, "smooth_sandstone", roof="smooth_stone", inside="white_concrete", doors=[("north", 14, 2, 3)],
             pane="glass_pane", win_y=(2, 3), trim="cyan_terracotta")
    for x in range(8, 25): g.put(x, 6, 8, "red_terracotta" if x % 2 else "cyan_terracotta")
    for x in range(10, 23, 3):
        for y in (1, 2): g.put(x, y, 13, "bookshelf")
    g.put(20, 1, 10, "red_concrete"); g.put(20, 2, 10, "blue_stained_glass")   # the Squishee machine
    g.put(11, 1, 10, "stripped_oak_log[axis=x]"); g.put(12, 1, 10, "stripped_oak_log[axis=x]")
    g.label(16.5, 7.0, 7.9, [{"text": "KWIK-E-MART", "color": "red", "bold": True}], 180, 1.8)
    # the Simpsons' house
    building(g, -30, 7, -12, 17, 7, "orange_terracotta", inside="oak_planks", doors=[("north", -21, 1, 2), ("east", 12, 1, 2)],
             pane="glass_pane", win_y=(2, 5), corner="white_concrete")
    gable(g, -30, 7, -12, 17, 8, "spruce_stairs", "spruce_planks", end="orange_terracotta", axis="x")
    building(g, -11, 10, -5, 16, 4, "orange_terracotta", roof="spruce_planks", doors=[("north", -8, 3, 3)])   # the garage
    for x in range(-11, -4): g.put(x, 0, 9, "smooth_stone")
    g.label(-20.5, 3.5, 6.9, {"text": "742 EVERGREEN TERRACE", "color": "white", "bold": True}, 180, 0.7)
    # the Lard Lad donut on a pole
    for y in range(1, 6): g.put(0, y, 22, "iron_bars")
    for x in range(-5, 6):
        for y in range(6, 18):
            d = math.hypot(x, y - 11.5)
            if 2.2 <= d <= 4.6:
                g.put(x, y, 22, "pink_concrete" if d > 3.2 or y > 11 else "orange_terracotta", force=True)
                if d > 3.2 and rnd.random() < 0.15: g.put(x, y, 22, rnd.choice(["yellow_concrete", "lime_concrete", "light_blue_concrete", "white_concrete"]), force=True)
    g.label(0.5, 4.5, 23.05, {"text": "LARD LAD DONUTS", "color": "light_purple", "bold": True}, 0, 1.0)
    g.label(0.5, 4.5, 21.95, {"text": "LARD LAD DONUTS", "color": "light_purple", "bold": True}, 180, 1.0)
    # trees, lamp posts and a couple of cars on the road
    for (x, z) in ((-32, -6), (-6, 30), (30, 30), (32, 4), (-30, 30), (6, 30)): tree(g, x, z, h=5, r=2)
    for x in (-24, -8, 8, 24):
        for y in range(1, 5): g.put(x, y, 2, "iron_bars")
        g.put(x, 5, 2, "lantern")
    car(g, -14, -3, "pink"); car(g, 12, -2, "red")

    def wall(x, y, z, t):   # a concrete fence with bars along the top
        if y <= 2 or max(abs(x), abs(z)) > R + 1: return "light_gray_concrete" if y != 2 else "yellow_concrete" if t % 8 < 4 else "black_concrete"
        return "iron_bars" if y < WALL_H else "light_gray_concrete"
    frame(g, wall, "gray_concrete", "iron_bars")
    return g


# ---------------------------------------------------------------------------------------------- Albuquerque (Breaking Bad)
def albuquerque():
    g = MapGrid()
    rnd, n1 = random.Random(901), Noise(911, 6)

    def fl(x, z):
        if abs(z) <= 3: return "yellow_concrete" if z == 0 and x % 5 < 3 else "black_concrete" if abs(z) == 3 else "gray_concrete"   # the highway
        n = n1(x, z)
        return "sand" if n < 0.4 else "red_sand" if n < 0.6 else "terracotta" if n < 0.72 else "smooth_sandstone" if n < 0.88 else "coarse_dirt"
    floor(g, fl)
    for x in range(-R, R + 1):
        for z in range(-R, R + 1):
            b = g.get(x, 0, z)
            if b in ("sand", "red_sand") and rnd.random() < 0.025: g.put(x, 1, z, "dead_bush")
    # the RV: white with a brown stripe, a door, black windows; a cook set-up inside
    vx, vz = -16, 10
    for x in range(vx, vx + 9):
        for z in range(vz, vz + 4):
            edge = x in (vx, vx + 8) or z in (vz, vz + 3)
            g.put(x, 1, z, "white_concrete" if edge else "white_concrete")
            for y in (2, 3, 4):
                if not edge: continue
                door = z == vz + 3 and x == vx + 5 and y <= 3
                window = y == 3 and (x in (vx, vx + 8) or x % 2 == 0)
                g.put(x, y, z, "air" if door else "black_stained_glass" if window else "brown_concrete" if y == 2 else "white_concrete")
            g.put(x, 5, z, "white_concrete")
    for (x, z) in ((vx + 1, vz), (vx + 7, vz), (vx + 1, vz + 3), (vx + 7, vz + 3)): g.put(x, 1, z, "black_concrete")
    g.put(vx + 2, 2, vz + 1, "brewing_stand"); g.put(vx + 3, 2, vz + 1, "cauldron"); g.put(vx + 6, 2, vz + 2, "barrel[facing=up]")
    for (x, z) in ((vx + 4, vz + 6), (vx + 7, vz + 7), (vx + 10, vz + 5)): g.put(x, 1, z, "light_blue_stained_glass")   # blue crystals
    # the pool with the pink teddy bear
    for x in range(-30, -21):
        for z in range(-14, -7):
            g.put(x, 0, z, "smooth_quartz" if x in (-30, -22) or z in (-14, -8) else "water")
    for (x, y, z) in ((-26, 1, -11), (-25, 1, -11), (-26, 1, -10), (-25, 1, -10), (-26, 2, -11)):
        g.put(x, y, z, "pink_wool")
    # Los Pollos Hermanos
    building(g, 8, -32, 28, -22, 5, "smooth_sandstone", roof="red_terracotta", inside="white_concrete", doors=[("south", 18, 2, 3)],
             pane="glass_pane", win_y=(2, 3), trim="yellow_terracotta")
    for x in range(8, 29): g.put(x, 6, -22, "yellow_concrete" if x % 2 else "red_concrete")
    for x in range(11, 26, 4): g.put(x, 1, -27, "oak_fence"); g.put(x, 2, -27, "oak_pressure_plate")
    for x in range(10, 27): g.put(x, 1, -30, "stripped_oak_log[axis=x]")
    g.label(18.5, 7.1, -20.9, [{"text": "LOS POLLOS ", "color": "yellow", "bold": True}, {"text": "HERMANOS", "color": "red", "bold": True}], 0, 1.8)
    # the A1A car wash: an open tunnel
    for x in range(-32, -15):
        for z in (-31, -23):
            for y in range(1, 6): g.put(x, y, z, "white_concrete" if x % 4 else "light_blue_concrete")
        for z in range(-31, -22): g.put(x, 6, z, "light_blue_concrete" if z % 2 else "white_concrete")
    for x in (-28, -22):
        for z in range(-30, -23): g.put(x, 5, z, "blue_wool")
    g.label(-23.5, 7.1, -21.9, [{"text": "A1A ", "color": "aqua", "bold": True}, {"text": "CAR WASH", "color": "white", "bold": True}], 0, 1.8)
    # Saul's strip-mall office
    building(g, 22, 8, 34, 16, 5, "white_terracotta", roof="smooth_stone", inside="spruce_planks", doors=[("west", 12, 1, 2)], pane="glass_pane", win_y=(2, 3))
    g.label(21.9, 6.2, 12.5, [{"text": "BETTER CALL ", "color": "white", "bold": True}, {"text": "SAUL!", "color": "red", "bold": True}], -90, 1.4)
    # mesas
    for (mx, mz, r) in ((-30, 30, 6), (30, 30, 5), (6, 22, 3)):
        for y, b in enumerate(("terracotta", "orange_terracotta", "white_terracotta", "red_terracotta", "yellow_terracotta", "orange_terracotta", "brown_terracotta"), 1):
            rr = r - (y - 1) * 0.6
            if rr < 1: break
            cyl(g, mx, mz, rr, y, y, b)
    # cacti and a broken-down car
    for (x, z) in ((-6, -18), (6, 26), (-34, 0), (34, -6), (-10, 32), (14, -12), (-2, -32)):
        if g.get(x, 0, z) not in ("sand", "red_sand"): g.put(x, 0, z, "sand")
        for y in range(1, rnd.randint(2, 4)): g.put(x, y, z, "cactus")
    car(g, 4, 5, "yellow", length=5)

    def wall(x, y, z, t):   # a layered canyon wall
        return ("brown_terracotta", "orange_terracotta", "terracotta", "yellow_terracotta", "white_terracotta", "orange_terracotta",
                "red_terracotta", "terracotta")[y]
    frame(g, wall, "smooth_red_sandstone", "red_sandstone_wall")
    return g


# ---------------------------------------------------------------------------------------------- Green Hill Zone (Sonic)
def greenhill():
    g = MapGrid()
    rnd = random.Random(1001)
    floor(g, lambda x, z: "grass_block")
    for x in range(-R, R + 1):
        for z in range(-R, R + 1):
            if rnd.random() < 0.05: g.put(x, 1, z, rnd.choice(["dandelion", "short_grass", "poppy"]))
    # checkered plateaus with grass tops (steps up the side)
    for (x1, z1, x2, z2, h) in ((-34, -34, -22, -26, 4), (22, -34, 34, -26, 3), (-16, 30, -6, 35, 3), (6, 30, 16, 35, 3), (-34, -8, -30, 8, 2), (30, -8, 34, 8, 2)):
        for x in range(x1, x2 + 1):
            for z in range(z1, z2 + 1):
                for y in range(1, h + 1): g.put(x, y, z, "grass_block" if y == h else checker(x, y, z))
        mid = (x1 + x2) // 2
        side = z2 + 1 if z1 < 0 else z1 - 1
        dz = 1 if z1 < 0 else -1
        for k in range(h):
            for x in range(mid - 1, mid + 2): g.put(x, h - k, side + dz * k, "grass_block")
            for x in range(mid - 1, mid + 2):
                for y in range(1, h - k): g.put(x, y, side + dz * k, checker(x, y, side + dz * k))
    # the loop-de-loop in the middle
    for x in range(-2, 3):
        for y in range(1, 17):
            for z in range(-9, 10):
                d = math.hypot(z, y - 8.5)
                if 6.6 <= d <= 7.8 and not (y <= 2):
                    g.put(x, y, z, "grass_block" if d < 7.2 else checker(x, y, z))
    # palm trees
    for (x, z) in ((-18, -10), (18, 12), (-26, 18), (26, -16), (10, -24), (-10, 20), (30, 26), (-30, -18)):
        lean = 1 if x < 0 else -1
        for y in range(1, 9): g.put(x + (lean if y > 6 else 0), y, z, "jungle_log")
        tx = x + lean
        for (ox, oz) in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2)]:
            g.put(tx + ox, 9, z + oz, "jungle_leaves[persistent=true]")
        for (ox, oz) in ((3, 0), (-3, 0), (0, 3), (0, -3)): g.put(tx + ox, 8, z + oz, "jungle_leaves[persistent=true]")
        g.put(tx, 10, z, "jungle_leaves[persistent=true]")
    # totem poles, sunflowers, springs
    for (x, z, f) in ((-8, -14, "south"), (8, 14, "north"), (-14, 6, "east"), (14, -6, "west")):
        for y, b in enumerate(("red_terracotta", "yellow_terracotta", "blue_terracotta", "black_terracotta", "orange_terracotta"), 1): g.put(x, y, z, b)
        g.put(x, 6, z, f"carved_pumpkin[facing={f}]")
    for k in range(18):
        x, z = rnd.randint(-33, 33), rnd.randint(-20, 20)
        if g.empty(x, 1, z) or g.get(x, 1, z) in ("dandelion", "short_grass", "poppy"):
            g.put(x, 1, z, "sunflower[half=lower]"); g.put(x, 2, z, "sunflower[half=upper]")
    for (x, z) in ((-6, 0), (6, 0), (0, -16), (0, 16), (-24, -20), (24, 20)):
        g.put(x, 0, z, "slime_block")
    # floating gold rings
    for (x, y, z, ax) in ((-14, 3, -22, "x"), (-10, 3, -22, "x"), (-6, 3, -22, "x"), (16, 4, 22, "x"), (20, 4, 22, "x"), (-20, 4, 8, "z"), (20, 3, -6, "z")):
        for (a, b) in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            if abs(a) + abs(b) == 2: continue
            p = (x + a, y + b, z) if ax == "x" else (x, y + b, z + a)
            g.put(*p, "gold_block")

    def wall(x, y, z, t):
        if y == WALL_H: return "grass_block"
        return checker(t, y, 0)
    frame(g, wall, "grass_block", "oak_fence")
    return g


# id (the Colosseum is 1), key, name, colour, universe, builder
MAPS = [
    (2, "mustafar", "Mustafar", "red", "Star Wars", mustafar),
    (3, "swamp", "Shrek's Swamp", "green", "Shrek", swamp),
    (4, "tegridy", "Tegridy Farms", "dark_green", "South Park", tegridy),
    (5, "quahog", "Quahog", "aqua", "Family Guy", quahog),
    (6, "bikini", "Bikini Bottom", "yellow", "SpongeBob SquarePants", bikini),
    (7, "mushroom", "Mushroom Kingdom", "red", "Super Mario", mushroom),
    (8, "springfield", "Springfield", "yellow", "The Simpsons", springfield),
    (9, "albuquerque", "Albuquerque", "gold", "Breaking Bad", albuquerque),
    (10, "greenhill", "Green Hill Zone", "green", "Sonic the Hedgehog", greenhill),
]


# ---------------------------------------------------------------------------------------------- checks and output
def check(g, name):
    """Every spawn must be clear and all of them must be able to reach each other on foot."""
    def blocked(x, z):
        b1, b2, b3 = g.get(x, 1, z), g.get(x, 2, z), g.get(x, 3, z)
        if g.get(x, 0, z) == "lava": return True
        if b1 and (om.is_fence(b1) or om.is_wall(b1) or om.is_pane(b1) or any(s in nm(b1) for s in ("campfire", "cactus", "lava"))): return True
        if not passable(b2): return True
        return not passable(b1) and not passable(b3)
    for (sx, sz, _) in g.spawns:
        assert not blocked(sx, sz), f"{name}: spawn {sx},{sz} is blocked"
        assert g.get(sx, 0, sz) not in ("lava", "water", None), f"{name}: spawn {sx},{sz} has no floor"
    s0 = g.spawns[0][:2]
    seen, todo = {s0}, deque([s0])
    while todo:
        x, z = todo.popleft()
        for (ox, oz) in DIRS.values():
            n = (x + ox, z + oz)
            if abs(n[0]) <= R and abs(n[1]) <= R and n not in seen and not blocked(*n):
                seen.add(n); todo.append(n)
    for (sx, sz, _) in g.spawns:
        assert (sx, sz) in seen, f"{name}: spawn {sx},{sz} is cut off"
    assert len(seen) > (2 * R + 1) ** 2 * 0.5, f"{name}: only {len(seen)} cells walkable"
    return len(seen)


def resolve(g, x, y, z, b):
    """Fences, walls, panes and bars get the connections the game would have given them."""
    if not (om.is_fence(b) or om.is_wall(b) or om.is_pane(b)) or "[" in b: return b
    def nb(d):
        ox, oz = DIRS[d]
        o = g.get(x + ox, y, z + oz)
        if is_full(o): return True
        if om.is_fence(b): return o is not None and om.is_fence(o) and ("nether" in nm(o)) == ("nether" in nm(b))
        return o is not None and (om.is_wall(o) or om.is_pane(o))
    c = {d: nb(d) for d in DIRS}
    if om.is_wall(b):
        straight = (c["north"] and c["south"] and not c["east"] and not c["west"]) or (c["east"] and c["west"] and not c["north"] and not c["south"])
        up = not straight or g.get(x, y + 1, z) not in (None, "air")
        return f"{b}[up={str(up).lower()}," + ",".join(f"{d}={'low' if v else 'none'}" for d, v in c.items()) + "]"
    return f"{b}[" + ",".join(f"{d}={str(v).lower()}" for d, v in c.items()) + "]"


def commands(g, ox, oy, oz):
    """setblock/fill commands for the grid shifted to (ox, oy, oz): solid blocks bottom up, then the ones resting on
    something, then hanging ones top down; then the raw fills (barrier) and the container locks."""
    groups = ([], [], [])
    for (x, y, z), b in g.b.items():
        b = resolve(g, x, y, z, b)
        hanging = "hanging=true" in b or "vine" in b
        groups[2 if hanging else 1 if any(s in nm(b) + "[" for s in ATTACHED) else 0].append((x, y, z, b))
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
    for (x1, y1, z1, x2, y2, z2, b) in g.raw:
        out.append(f"fill {ox + x1} {oy + y1} {oz + z1} {ox + x2} {oy + y2} {oz + z2} minecraft:{b}")
    return out + om.locks(g, ox, oy, oz)
