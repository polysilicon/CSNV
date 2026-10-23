"""The PvP arena (imported by build.py): a round Roman colosseum, drawn with the Outbreak map engine (outbreak_maps.Grid).

Coordinates are relative to the arena centre, y 0 = floor. The fighting floor is a circle of radius R (40); the
round wall is the band just outside it, with barrier above it up to a barrier dome lid at y 31. Outside the wall are
STANDS rows of stepped seating that spectators walk on (they arrive through the lobby portal), closed in by an outer
barrier ring. Gladiator gates (barred) sit at the four compass points; the emperor's box is above the north gate.
"""
import math
import random
from collections import deque
import outbreak_maps as om
from outbreak_maps import DIRS, Noise

R = 40           # floor radius
WALL = 41.6      # the wall band is R + 0.5 < d <= WALL
WALL_H = 6       # wall rows y 1..6
STANDS = 9       # rows of seating outside the wall
TOP = 30         # barrier above the wall up to y TOP; the lid is at TOP + 1
EXTENT = R + 2 + STANDS + 2   # half-size of everything (for clearing)
OPP = {"north": "south", "south": "north", "east": "west", "west": "east"}
# where spectators arrive (relative x, z, yaw): on the 5th row, east / south / west (north is the emperor's box)
SPECTATE = [(R + 6, 0, 90), (0, R + 6, 180), (-(R + 6), 0, -90)]
# PvP spawns: radius 32, facing the centre
SPAWNS = [(32, 0, 90), (-32, 0, -90), (0, -32, 0), (0, 32, 180), (23, -23, 45), (-23, -23, -45), (23, 23, 135), (-23, 23, -135)]


def dist(x, z): return math.hypot(x, z)
def row(x, z):
    """0 = floor, 1 = wall, 2.. = stands row (row - 1), None = outside."""
    d = dist(x, z)
    if d <= R + 0.5: return 0
    if d <= WALL: return 1
    k = math.ceil(d - WALL)
    return k + 1 if k <= STANDS else None


def facing_in(x, z):
    """Cardinal direction pointing toward the centre from (x, z)."""
    if abs(x) >= abs(z): return "west" if x > 0 else "east"
    return "north" if z > 0 else "south"


def angle(x, z): return (math.degrees(math.atan2(z, x)) + 360) % 360


class ArenaGrid(om.Grid):
    """Grid reaching out to the stands; only the spawns and the arrival spots are kept clear."""
    def put(self, x, y, z, block, force=False):
        if abs(x) > EXTENT or abs(z) > EXTENT: return
        if y >= 1 and not force and self.protected(x, z): return
        self.b[(x, y, z)] = block

    def protected(self, x, z):
        return any(max(abs(x - sx), abs(z - sz)) <= 1 for (sx, sz, _) in self.spawns)


def gate_at(x, z):
    """Which gate (if any) a wall/stand cell belongs to: within 2 of a compass axis."""
    if abs(z) <= 2 and abs(x) > R: return "east" if x > 0 else "west"
    if abs(x) <= 2 and abs(z) > R: return "south" if z > 0 else "north"
    return None


def clean_seat(x, z, k):
    """A stair only where it makes a straight run: both side neighbours are the same row facing the same way, and
    the step in front of it is the row below (otherwise the game bends stairs into corner shapes)."""
    f = facing_in(x, z)
    fx, fz = DIRS[f]
    if row(x + fx, z + fz) != k - 1: return False
    for (sx, sz) in ((fz, fx), (-fz, -fx)):   # the two sideways neighbours
        n = (x + sx, z + sz)
        if row(*n) != k or facing_in(*n) != f: return False
    return True


def colosseum(spawns=SPAWNS):
    rnd = random.Random(21)
    g = ArenaGrid([], spawns)
    sand, dust = Noise(31, 6), Noise(32, 3)
    E = EXTENT

    # ---------------------------------------------------------------- floor
    for x in range(-E, E + 1):
        for z in range(-E, E + 1):
            k = row(x, z)
            if k is None: continue
            d, a = dist(x, z), angle(x, z)
            if k == 0:
                if d <= 9.5:   # mosaic: rings and sixteen spokes
                    ring = int(d)
                    b = ("chiseled_red_sandstone" if ring == 0 else "cut_red_sandstone" if ring in (2, 6) else
                         "smooth_red_sandstone" if ring == 9 else "gold_block" if ring == 4 and int(a) % 45 < 3 else "smooth_sandstone")
                    if ring >= 2 and (a % 22.5 < 2.5 or a % 22.5 > 20): b = "orange_terracotta" if ring % 2 else "red_terracotta"
                elif d > 34.5:   # raked sand track along the wall
                    b = "sand" if int(a / 4) % 2 else "smooth_sandstone"
                    if rnd.random() < 0.03: g.put(x, 1, z, "dead_bush")
                elif min(a % 45, 45 - a % 45) * math.pi / 180 * d < 1.1:   # eight spoke paths
                    b = "cut_sandstone"
                elif abs(d - 22) < 0.6:   # a ring path between the spokes
                    b = "cut_red_sandstone"
                else:
                    n = sand(x, z)
                    b = "smooth_sandstone" if n < 0.45 else "sandstone" if n < 0.62 else "sand" if n < 0.8 else "red_sand"
                    if dust(x, z) > 0.8 and b in ("smooth_sandstone", "sandstone"): b = "sand"
                    if b in ("sand", "red_sand") and rnd.random() < 0.03: g.put(x, 1, z, "dead_bush")
                g.put(x, 0, z, b)
            else:
                g.put(x, 0, z, "cut_sandstone")

    # ---------------------------------------------------------------- the wall: pilasters, torches, banners; barrier above
    for x in range(-E, E + 1):
        for z in range(-E, E + 1):
            if row(x, z) != 1: continue
            a = angle(x, z)
            gate = gate_at(x, z)
            for y in range(1, WALL_H + 1):
                b = "cut_sandstone" if y == 1 else "chiseled_red_sandstone" if y == WALL_H else "smooth_sandstone"
                if y == 4: b = "cut_red_sandstone"   # a stripe
                if gate and (min(abs(x), abs(z)) <= 1 and y <= 4 or y <= 3): b = "iron_bars"
                g.put(x, y, z, b, force=True)
            for y in range(WALL_H + 1, TOP + 1): g.put(x, y, z, "barrier", force=True)

    def on_ring(rad, deg):
        """The cell at radius rad and angle deg."""
        return round(rad * math.cos(math.radians(deg))), round(rad * math.sin(math.radians(deg)))
    # pilasters every 10 degrees against the inside of the wall, red banners halfway between
    for k in range(72):
        deg = k * 5
        x, z = on_ring(R, deg)
        if row(x, z) != 0 or gate_at(*on_ring(R + 1, deg)): continue
        f = facing_in(x, z)
        ox, oz = DIRS[f]
        if row(x - ox, z - oz) != 1: continue   # must stand against the wall
        if k % 2 == 0:
            for y in range(1, WALL_H): g.put(x, y, z, "chiseled_sandstone" if y in (1, WALL_H - 1) else "smooth_sandstone")
            g.put(x, WALL_H, z, f"sandstone_stairs[facing={OPP[f]}]")
            g.put(x + ox, 4, z + oz, f"wall_torch[facing={f}]")
        else:
            g.put(x, 5, z, f"red_wall_banner[facing={f}]")

    # gates: a dark tunnel behind the bars, a banner over each
    for f, (sx, sz) in (("east", (1, 0)), ("west", (-1, 0)), ("south", (0, 1)), ("north", (0, -1))):
        for k in range(-2, 3):
            for depth in range(1, 5):
                cx, cz = (sx * (R + 1 + depth), k) if sx else (k, sz * (R + 1 + depth))
                for y in range(1, 5): g.put(cx, y, cz, "black_concrete" if depth == 4 else "air", force=True)
                g.put(cx, 5, cz, "chiseled_sandstone", force=True)
        bx, bz = (sx * R, 0) if sx else (0, sz * R)
        g.put(bx, 6, bz, f"red_wall_banner[facing={OPP[f]}]", force=True)

    # ---------------------------------------------------------------- the stands
    for x in range(-E, E + 1):
        for z in range(-E, E + 1):
            k = row(x, z)
            if k is None or k < 2: continue
            n = k - 1                 # seating row 1..STANDS
            h = WALL_H + n            # its seat height
            over_gate = gate_at(x, z) and n <= 3   # the gate tunnels run under the first rows: seats go on their roof
            a = angle(x, z)
            for y in range(6 if over_gate else 1, h): g.put(x, y, z, "sandstone" if y % 4 else "cut_sandstone")
            aisle = min(a % 30, 30 - a % 30) * math.pi / 180 * dist(x, z) < 0.8
            if aisle:
                g.put(x, h, z, "chiseled_sandstone")
            elif clean_seat(x, z, k):
                g.put(x, h, z, f"sandstone_stairs[facing={OPP[facing_in(x, z)]},shape=straight]")
            else:   # where the circle's steps don't line up, a flat terrace block instead of a twisted stair
                g.put(x, h, z, "cut_sandstone")
            if n == STANDS: g.put(x, h + 1, z, "sandstone_wall")   # the rim parapet
    # flag poles and braziers along the rim
    for k in range(48):
        deg = k * 7.5
        x, z = on_ring(WALL + STANDS - 0.5, deg)
        if row(x, z) != STANDS + 1: continue
        h = WALL_H + STANDS
        if k % 4 == 2:
            for y in range(h + 1, h + 6): g.put(x, y, z, "sandstone_wall")
            g.put(x, h + 6, z, rnd.choice(["red_banner", "yellow_banner", "orange_banner"]))
        elif k % 4 == 0:
            g.put(x, h + 1, z, "chiseled_sandstone")
            g.put(x, h + 2, z, "campfire[lit=true]")
    # the outer barrier ring, just outside the last row
    for x in range(-E, E + 1):
        for z in range(-E, E + 1):
            d = dist(x, z)
            if WALL + STANDS < d <= WALL + STANDS + 1.2:
                for y in range(1, WALL_H + STANDS + 6): g.put(x, y, z, "barrier", force=True)
            if d <= WALL:   # the lid over the fighting floor
                g.put(x, TOP + 1, z, "barrier", force=True)

    # the emperor's box over the north gate: a raised dais, quartz columns, a red canopy and a throne
    zb = -(R + 6)
    for x in range(-4, 5):
        for z in range(zb - 2, zb + 3):
            for y in range(1, 12): g.put(x, y, z, "smooth_sandstone" if y < 11 else "smooth_quartz", force=True)
            g.put(x, 12, z, "air", force=True)
            for y in range(13, 17): g.put(x, y, z, "air", force=True)
            g.put(x, 17, z, "red_wool" if (x + z) % 2 else "yellow_wool", force=True)
    for (x, z) in ((-4, zb - 2), (4, zb - 2), (-4, zb + 2), (4, zb + 2)):
        for y in range(12, 17): g.put(x, y, z, "quartz_pillar")
    for x in range(-3, 4): g.put(x, 12, zb + 2, "quartz_slab[type=bottom]")
    g.put(0, 12, zb - 1, "gold_block"); g.put(0, 13, zb - 1, "quartz_stairs[facing=north]")
    g.put(-1, 12, zb - 1, "red_carpet"); g.put(1, 12, zb - 1, "red_carpet")
    g.put(0, 16, zb, "lantern[hanging=true]")

    # ---------------------------------------------------------------- centre: the emperor's pavilion (9x9)
    for x in range(-4, 5):
        for z in range(-4, 5):
            edge, corner = max(abs(x), abs(z)) == 4, abs(x) == 4 and abs(z) == 4
            g.put(x, 0, z, "chiseled_sandstone" if (x + z) % 2 == 0 else "cut_sandstone")
            if corner:
                for y in range(1, 11): g.put(x, y, z, "chiseled_sandstone" if y in (1, 10) else "quartz_pillar")
            elif edge and min(abs(x), abs(z)) >= 2:   # L-shaped low walls at the corners for cover
                for y in (1, 2): g.put(x, y, z, "smooth_sandstone")
                g.put(x, 3, z, "sandstone_slab[type=bottom]")
            g.put(x, 11, z, "cut_sandstone" if edge else "smooth_sandstone_slab[type=top]")
    for t in range(-5, 6):
        for (x, z, f) in ((t, -5, "south"), (t, 5, "north"), (-5, t, "east"), (5, t, "west")):
            g.put(x, 11, z, "chiseled_sandstone" if abs(t) == 5 else f"sandstone_stairs[facing={f},half=top]")
    for y, b in ((12, "gold_block"), (13, "campfire[lit=true]")): g.put(0, y, 0, b)
    for (x, z) in ((0, 0), (2, 2), (-2, -2), (2, -2), (-2, 2)): g.put(x, 10, z, "lantern[hanging=true]")
    g.put(0, 1, 0, "chiseled_red_sandstone"); g.put(0, 2, 0, "sandstone_wall"); g.put(0, 3, 0, "lantern")

    # ---------------------------------------------------------------- four gladiator barracks (9x9)
    for (mx, mz, h, awning) in ((-16, -16, 7, "red"), (16, -16, 5, "yellow"), (-16, 16, 5, "yellow"), (16, 16, 7, "red")):
        bx1, bx2, bz1, bz2 = mx - 4, mx + 4, mz - 4, mz + 4
        for x in range(bx1, bx2 + 1):
            for z in range(bz1, bz2 + 1):
                edge = x in (bx1, bx2) or z in (bz1, bz2)
                corner = x in (bx1, bx2) and z in (bz1, bz2)
                g.put(x, 0, z, "cut_sandstone" if edge else "smooth_sandstone")
                if not edge: continue
                top = h + (0 if corner else rnd.choice([0, 0, -1, 1]))
                door = (abs(x - mx) <= 1 or abs(z - mz) <= 1) and not corner
                for y in range(1, top + 1):
                    if door and y <= 2: continue
                    window = y == 3 and not corner and (abs(x - mx) == 3 or abs(z - mz) == 3)
                    b = "chiseled_sandstone" if corner else "cut_red_sandstone" if y == top else "smooth_sandstone"
                    g.put(x, y, z, "iron_bars" if window else b)
        for (ox, oz) in DIRS.values():   # awnings over the doors facing the centre
            ax, az = mx + ox * 5, mz + oz * 5
            if abs(ax) < abs(mx) or abs(az) < abs(mz):
                for k in (-1, 0, 1):
                    px, pz = (ax, az + k) if ox else (ax + k, az)
                    g.put(px, 4, pz, f"{awning}_wool")
                    g.put(px, 3, pz, "air") if k else g.put(px, 3, pz, "lantern[hanging=true]")
        for (sx, sz, b) in ((-3, -3, "barrel[facing=up]"), (3, 3, "hay_block"), (3, -3, "hay_block"), (-3, 3, "smithing_table"),
                            (-3, -2, "barrel[facing=up]"), (2, 3, "grindstone[face=floor,facing=north]")):
            g.put(mx + sx, 1, mz + sz, b)
        g.put(mx, 1, mz, "lantern")
        for (sx, sz) in ((2, -3), (-3, 2)):   # practice targets
            g.put(mx + sx, 1, mz + sz, "hay_block"); g.put(mx + sx, 2, mz + sz, "target")

    # ---------------------------------------------------------------- spina walls on the compass axes
    for (sx, sz) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for k in range(-3, 4):
            for depth in (24, 25):
                x, z = (sx * depth, k) if sx else (k, sz * depth)
                end = abs(k) == 3
                for y in (1, 2): g.put(x, y, z, "chiseled_sandstone" if end else "cut_sandstone")
                g.put(x, 3, z, "chiseled_sandstone" if end else "sandstone_slab[type=bottom]")
                if end:
                    for y in (4, 5): g.put(x, y, z, "sandstone_wall")
                    g.put(x, 6, z, "lantern")

    # fallen columns and crates closer in
    for n, (sx, sz) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
        cells = [((sx * d, k) if sx else (k, sz * d)) for d in (10, 11) for k in (-1, 0, 1)]
        if n % 2 == 0:
            for (x, z) in cells: g.put(x, 1, z, "smooth_quartz" if (x + z) % 2 else "chiseled_sandstone")
            for (x, z) in cells[:2]: g.put(x, 2, z, "quartz_slab[type=bottom]")
        else:
            for (x, z) in cells: g.put(x, 1, z, rnd.choice(["barrel[facing=up]", "hay_block", "spruce_planks"]))
            x, z = cells[0]; g.put(x, 2, z, "barrel[facing=up]")

    # ---------------------------------------------------------------- obelisks, palms, lamp posts, lion cages
    for k in range(8):
        a = math.radians(22.5 + 45 * k)
        x, z = round(30 * math.cos(a)), round(30 * math.sin(a))
        for ox in (-1, 0, 1):
            for oz in (-1, 0, 1):
                g.put(x + ox, 1, z + oz, "smooth_sandstone_slab[type=bottom]" if ox and oz else "smooth_sandstone")
        for y in range(2, 10): g.put(x, y, z, "chiseled_sandstone" if y in (2, 9) else "smooth_sandstone")
        g.put(x, 10, z, "gold_block"); g.put(x, 11, z, "lightning_rod")
    for k in range(4):   # date palms
        a = math.radians(67.5 + 90 * k)
        x, z = round(36 * math.cos(a)), round(36 * math.sin(a))
        lean = (1 if x < 0 else -1, 0)   # lean toward the middle
        for y in range(1, 8): g.put(x + (lean[0] if y > 5 else 0), y, z, "jungle_log")
        tx, ty = x + lean[0], 8
        for (ox, oz) in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2)]:
            g.put(tx + ox, ty, z + oz, "jungle_leaves[persistent=true]")
        for (ox, oz) in ((3, 0), (-3, 0), (0, 3), (0, -3)):
            g.put(tx + ox, ty - 1, z + oz, "jungle_leaves[persistent=true]")
        g.put(tx, ty + 1, z, "jungle_leaves[persistent=true]")
    for k in range(8):   # lamp posts
        a = math.radians(22.5 + 45 * k)
        x, z = round(18 * math.cos(a)), round(18 * math.sin(a))
        for y in (1, 2, 3): g.put(x, y, z, "sandstone_wall")
        g.put(x, 4, z, "chiseled_sandstone"); g.put(x, 5, z, "lantern")
    for k in range(4):   # lion cages by the wall
        a = math.radians(22.5 + 90 * k)
        cx, cz = round(37 * math.cos(a)), round(37 * math.sin(a))
        for x in range(cx - 1, cx + 2):
            for z in range(cz - 1, cz + 2):
                g.put(x, 0, z, "polished_andesite")
                edge = (x, z) != (cx, cz)
                for y in (1, 2): g.put(x, y, z, "iron_bars" if edge else "air")
                g.put(x, 3, z, "smooth_stone_slab[type=bottom]")
        g.put(cx, 1, cz, "hay_block")
    return g


def check(g, spawns=SPAWNS):
    """Every spawn must be clear and able to walk to the centre."""
    def blocked(x, z):
        b1, b2 = g.get(x, 1, z), g.get(x, 2, z)
        pas = lambda b: b is None or any(s in om.nm(b) for s in om.PASSABLE + ("dead_bush", "air"))
        if b1 and (om.is_fence(b1) or om.is_wall(b1) or om.is_pane(b1) or "campfire" in b1): return True
        return not pas(b2) or (not pas(b1) and not pas(g.get(x, 3, z)))
    start = (0, 6)
    seen, todo = {start}, deque([start])
    while todo:
        x, z = todo.popleft()
        for (ox, oz) in DIRS.values():
            n = (x + ox, z + oz)
            if row(*n) == 0 and n not in seen and not blocked(*n):
                seen.add(n); todo.append(n)
    for (sx, sz, _) in spawns:
        assert row(sx, sz) == 0 and not blocked(sx, sz), f"arena spawn {sx},{sz} is blocked"
        assert (sx, sz) in seen, f"arena spawn {sx},{sz} can't reach the centre"
    for (sx, sz, _) in SPECTATE:
        assert row(sx, sz) and row(sx, sz) >= 2, f"spectator spot {sx},{sz} isn't on the stands"
    return len(seen)


# ---------------------------------------------------------------------------------------------- duel pits
PIT_R = 14            # floor radius of a duel pit
PIT_SPAWNS = [(-10, 0, -90), (10, 0, 90)]   # challenger, opponent (facing each other)


class PitGrid(om.Grid):
    def put(self, x, y, z, block, force=False):
        if abs(x) > PIT_R + 3 or abs(z) > PIT_R + 3: return
        if y >= 1 and not force and any(max(abs(x - sx), abs(z - sz)) <= 1 for (sx, sz, _) in PIT_SPAWNS): return
        self.b[(x, y, z)] = block


def duel_pit():
    """A small round sandstone pit for 1v1 duels: mosaic floor, a wall with torches and banners, barrier above and a
    lid, and four columns for cover."""
    g = PitGrid([], PIT_SPAWNS)
    E = PIT_R + 2
    for x in range(-E, E + 1):
        for z in range(-E, E + 1):
            d = dist(x, z)
            if d <= PIT_R + 0.5:
                ring = int(d)
                b = ("chiseled_red_sandstone" if ring == 0 else "cut_red_sandstone" if ring in (3, 9) else
                     "smooth_red_sandstone" if ring == PIT_R else "smooth_sandstone" if ring < 3 else "sandstone" if (x + z) % 2 else "smooth_sandstone")
                if 4 <= ring <= 8 and (angle(x, z) % 45 < 4 or angle(x, z) % 45 > 41): b = "orange_terracotta"
                g.put(x, 0, z, b)
                g.put(x, 21, z, "barrier", force=True)   # lid
            elif d <= PIT_R + 1.6:   # the wall
                g.put(x, 0, z, "cut_sandstone")
                for y in range(1, 6): g.put(x, y, z, "cut_red_sandstone" if y == 3 else "chiseled_sandstone" if y == 5 else "smooth_sandstone", force=True)
                for y in range(6, 21): g.put(x, y, z, "barrier", force=True)
                g.put(x, 21, z, "barrier", force=True)
    for k in range(16):   # torches and banners on the inside of the wall
        deg = k * 22.5
        x, z = round(PIT_R * math.cos(math.radians(deg))), round(PIT_R * math.sin(math.radians(deg)))
        f = facing_in(x, z)
        if k % 2 == 0: g.put(x, 4, z, f"wall_torch[facing={f}]")
        else: g.put(x, 4, z, f"red_wall_banner[facing={f}]")
    for (x, z) in ((0, 6), (0, -6), (5, 0), (-5, 0)):   # cover: columns
        for y in range(1, 5): g.put(x, y, z, "chiseled_sandstone" if y in (1, 4) else "smooth_quartz")
        g.put(x, 5, z, "lantern")
    return g
