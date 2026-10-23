"""The PvP arena (imported by build.py): a Roman colosseum, drawn with the Outbreak map engine (outbreak_maps.Grid).

Coordinates are relative to the arena centre: the playable floor runs from -30 to 30 and build.py's walls() puts the
outer wall (with barrier above) at ±31. The cover keeps the footprints of the old plain blocks (centre, four corner
buildings, low walls), so fights play the same; the stands outside the walls are scenery behind the barrier.
"""
import math
import random
from collections import deque
import outbreak_maps as om
from outbreak_maps import DIRS, Noise

AR = 30          # floor half-size; wall at ±31
STANDS = 8       # rows of seating outside the wall (±32 .. ±39)
OPP = {"north": "south", "south": "north", "east": "west", "west": "east"}


class ArenaGrid(om.Grid):
    """Grid that reaches past the wall (for the stands) and only keeps the spawns and the centre clear."""
    def put(self, x, y, z, block, force=False):
        if abs(x) > AR + 1 + STANDS + 1 or abs(z) > AR + 1 + STANDS + 1: return
        if y >= 1 and not force and abs(x) <= AR and abs(z) <= AR and self.protected(x, z): return
        self.b[(x, y, z)] = block

    def protected(self, x, z):
        return any(max(abs(x - sx), abs(z - sz)) <= 1 for (sx, sz, _) in self.spawns)


def facing_in(x, z):
    """Direction pointing back into the arena from a wall/stand cell."""
    if abs(x) >= abs(z): return "west" if x > 0 else "east"
    return "north" if z > 0 else "south"


def colosseum(spawns):
    rnd = random.Random(21)
    g = ArenaGrid([], spawns)
    sand, dust = Noise(31, 6), Noise(32, 3)

    # ---------------------------------------------------------------- floor: sand-swept stone with a central mosaic
    for x in range(-AR, AR + 1):
        for z in range(-AR, AR + 1):
            r = math.hypot(x, z)
            if r <= 7.5:   # mosaic: rings and eight spokes
                ring = int(r)
                b = ("chiseled_red_sandstone" if ring == 0 else "cut_red_sandstone" if ring in (2, 5) else
                     "smooth_red_sandstone" if ring == 7 else "smooth_sandstone")
                ang = (math.degrees(math.atan2(z, x)) + 360) % 45
                if ring >= 2 and (ang < 5 or ang > 40): b = "orange_terracotta" if ring % 2 else "red_terracotta"
            elif x == 0 or z == 0 or abs(x) == abs(z):   # paths from the centre
                b = "cut_sandstone"
            else:
                n = sand(x, z)
                b = "smooth_sandstone" if n < 0.45 else "sandstone" if n < 0.62 else "sand" if n < 0.8 else "red_sand"
                if dust(x, z) > 0.8 and b in ("smooth_sandstone", "sandstone"): b = "sand"
            g.put(x, 0, z, b)
            if g.get(x, 0, z) in ("sand", "red_sand") and rnd.random() < 0.04:
                g.put(x, 1, z, "dead_bush")

    # ---------------------------------------------------------------- inner wall face: pilasters, torches, banners
    W = AR + 1
    for t in range(-W, W + 1):
        for (x, z) in ((t, -W), (t, W), (-W, t), (W, t)):
            if abs(t) == W: continue
            if t % 6 == 0:   # pilaster, one block proud of the wall
                f = facing_in(x, z)
                ox, oz = DIRS[f]
                for y in range(1, 6): g.put(x + ox, y, z + oz, "chiseled_sandstone" if y in (1, 5) else "smooth_sandstone")
                g.put(x + ox, 6, z + oz, f"sandstone_stairs[facing={OPP[f]}]")
                g.put(x + ox * 2, 4, z + oz * 2, f"wall_torch[facing={f}]")
            elif t % 6 == 3 and abs(t) > 3:   # banner between pilasters
                f = facing_in(x, z)
                ox, oz = DIRS[f]
                g.put(x + ox, 4, z + oz, f"red_wall_banner[facing={f}]")

    # four gladiator gates: barred arches at the middle of each wall, a dark tunnel behind
    for (sx, sz) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for k in range(-2, 3):
            for y in range(1, 5):
                x, z = (sx * W, k) if sx else (k, sz * W)
                arch = abs(k) <= 1 or y <= 3
                if not arch: continue
                g.put(x, y, z, "iron_bars", force=True)
                for d in (1, 2):
                    tx, tz = (sx * (W + d), k) if sx else (k, sz * (W + d))
                    g.put(tx, y, tz, "air", force=True)
                bx, bz = (sx * (W + 3), k) if sx else (k, sz * (W + 3))
                g.put(bx, y, bz, "black_concrete", force=True)
            x, z = (sx * W, k) if sx else (k, sz * W)
            g.put(x, 5, z, "chiseled_red_sandstone", force=True)
        x, z = (sx * W, 0) if sx else (0, sz * W)
        ox, oz = (-sx, -sz)
        g.put(x + ox, 5, z + oz, "red_wall_banner[facing=%s]" % ({(1, 0): "west", (-1, 0): "east", (0, 1): "north", (0, -1): "south"}[(sx, sz)]))

    # ---------------------------------------------------------------- the stands: stepped seating outside the wall
    for d in range(1, STANDS + 1):
        h = 5 + d   # each row one higher
        R = W + d
        for t in range(-R, R + 1):
            for (x, z) in ((t, -R), (t, R), (-R, t), (R, t)):
                gate = max(abs(x), abs(z)) == R and min(abs(x), abs(z)) <= 2 and d <= 3
                if gate: continue
                for y in range(1, h): g.put(x, y, z, "sandstone" if y % 4 else "cut_sandstone")
                corner = abs(x) == abs(z)
                g.put(x, h, z, "smooth_sandstone" if corner else f"sandstone_stairs[facing={OPP[facing_in(x, z)]}]")
                if d == STANDS and not corner:   # the rim: a parapet with banners and braziers
                    g.put(x, h + 1, z, "sandstone_wall")
                    if t % 8 == 0:
                        for y in (h + 1, h + 2, h + 3): g.put(x, y, z, "sandstone_wall")
                        g.put(x, h + 4, z, "campfire[lit=true]")
                    elif t % 8 == 4:
                        g.put(x, h + 1, z, "chiseled_sandstone")
                        g.put(x, h + 2, z, rnd.choice(["red_banner", "yellow_banner", "orange_banner"]))
                elif not corner and d % 3 == 0 and rnd.random() < 0.06:   # a few seat cushions
                    g.put(x, h + 1, z, rnd.choice(["red_carpet", "yellow_carpet", "white_carpet"]))

    # ---------------------------------------------------------------- centre: the emperor's pavilion (old 7x7, 10 high)
    for x in range(-3, 4):
        for z in range(-3, 4):
            edge, corner = max(abs(x), abs(z)) == 3, abs(x) == 3 and abs(z) == 3
            g.put(x, 0, z, "chiseled_sandstone" if (x + z) % 2 == 0 else "cut_sandstone")
            if corner:   # columns
                for y in range(1, 10): g.put(x, y, z, "chiseled_sandstone" if y in (1, 9) else "smooth_quartz")
            elif edge:
                if min(abs(x), abs(z)) >= 2:   # L-shaped low walls at the corners for cover
                    for y in (1, 2): g.put(x, y, z, "smooth_sandstone")
                    g.put(x, 3, z, f"sandstone_slab[type=bottom]")
            g.put(x, 10, z, "cut_sandstone" if edge else "smooth_sandstone_slab[type=top]")
    for t in range(-4, 5):   # roof cornice
        for (x, z, f) in ((t, -4, "south"), (t, 4, "north"), (-4, t, "east"), (4, t, "west")):
            if abs(t) == 4: g.put(x, 10, z, "chiseled_sandstone")
            else: g.put(x, 10, z, f"sandstone_stairs[facing={f},half=top]")
    g.put(0, 11, 0, "gold_block")
    g.put(0, 12, 0, "campfire[lit=true]")
    g.put(0, 9, 0, "lantern[hanging=true]")
    for (x, z) in ((2, 2), (-2, -2), (2, -2), (-2, 2)):
        g.put(x, 9, z, "lantern[hanging=true]")

    # ---------------------------------------------------------------- four gladiator barracks (the old corner blocks)
    for (bx1, bz1, bx2, bz2, h, awning) in ((-15, -15, -9, -9, 6, "red"), (9, -15, 15, -9, 4, "yellow"),
                                            (-15, 9, -9, 15, 4, "yellow"), (9, 9, 15, 15, 6, "red")):
        mx, mz = (bx1 + bx2) // 2, (bz1 + bz2) // 2
        for x in range(bx1, bx2 + 1):
            for z in range(bz1, bz2 + 1):
                edge = x in (bx1, bx2) or z in (bz1, bz2)
                corner = x in (bx1, bx2) and z in (bz1, bz2)
                g.put(x, 0, z, "cut_sandstone" if edge else "smooth_sandstone")
                if not edge: continue
                top = h + (0 if corner else rnd.choice([0, 0, -1, 1]))   # jagged, weathered tops
                for y in range(1, top + 1):
                    door = (abs(x - mx) <= 1 or abs(z - mz) <= 1) and not corner and y <= 2
                    if door: continue
                    window = y == 3 and not corner and (abs(x - mx) == 2 or abs(z - mz) == 2) and h >= 4
                    b = "chiseled_sandstone" if corner else "cut_red_sandstone" if y == top else "smooth_sandstone"
                    g.put(x, y, z, "iron_bars" if window else b)
                if (abs(x - mx) <= 1 or abs(z - mz) <= 1) and not corner:   # arch over the doors
                    g.put(x, 3, z, "smooth_sandstone")
        # awnings over the doors facing the centre, supplies inside
        for (ox, oz) in DIRS.values():
            ax, az = mx + ox * 4, mz + oz * 4
            if abs(ax) < abs(mx) or abs(az) < abs(mz):
                for k in (-1, 0, 1):
                    px, pz = (ax, az + k) if ox else (ax + k, az)
                    g.put(px, 4, pz, f"{awning}_wool")
        for (sx, sz) in ((-2, -2), (2, 2)):
            g.put(mx + sx, 1, mz + sz, rnd.choice(["barrel[facing=up]", "hay_block", "barrel[facing=up]"]))
        g.put(mx + 2, 1, mz - 2, "hay_block")
        g.put(mx - 2, 1, mz + 2, "smithing_table")
        g.put(mx, 1, mz, "lantern")

    # ---------------------------------------------------------------- spina walls (the old 5x2 blocks): wall + stair caps + a column
    for (x1, z1, x2, z2) in ((-2, -18, 2, -17), (-2, 17, 2, 18), (-18, -2, -17, 2), (17, -2, 18, 2)):
        for x in range(x1, x2 + 1):
            for z in range(z1, z2 + 1):
                end = (x in (x1, x2)) if x2 - x1 > z2 - z1 else (z in (z1, z2))
                for y in (1, 2): g.put(x, y, z, "chiseled_sandstone" if end else "cut_sandstone")
                g.put(x, 3, z, "chiseled_sandstone" if end else "sandstone_slab[type=bottom]")
                if end:
                    for y in (4, 5): g.put(x, y, z, "sandstone_wall")
                    g.put(x, 6, z, "lantern")

    # fallen columns and crates (the old 2x3 low blocks)
    for n, (x1, z1, x2, z2) in enumerate(((-8, -1, -7, 1), (7, -1, 8, 1), (-1, -8, 1, -7), (-1, 7, 1, 8))):
        cells = [(x, z) for x in range(x1, x2 + 1) for z in range(z1, z2 + 1)]
        if n % 2 == 0:
            for (x, z) in cells: g.put(x, 1, z, "smooth_quartz" if (x + z) % 2 else "chiseled_sandstone")
            for (x, z) in cells[:2]: g.put(x, 2, z, "quartz_slab[type=bottom]")
        else:
            for (x, z) in cells: g.put(x, 1, z, rnd.choice(["barrel[facing=up]", "hay_block", "spruce_planks"]))
            x, z = cells[0]; g.put(x, 2, z, "barrel[facing=up]")

    # ---------------------------------------------------------------- obelisks, palms and lamp posts
    for (x, z) in ((24, 12), (-24, -12), (12, -24), (-12, 24), (24, -12), (-24, 12), (12, 24), (-12, -24)):
        for ox in (-1, 0, 1):
            for oz in (-1, 0, 1):
                g.put(x + ox, 1, z + oz, "smooth_sandstone_slab[type=bottom]" if ox and oz else "smooth_sandstone")
        for y in range(2, 9): g.put(x, y, z, "chiseled_sandstone" if y in (2, 8) else "smooth_sandstone")
        g.put(x, 9, z, "gold_block")
        g.put(x, 10, z, "lightning_rod")
    for (x, z) in ((25, 25), (-26, -25), (25, -25), (-26, 25)):   # date palms in the corners (fronds stay inside ±30)
        for y in range(1, 8): g.put(x + (1 if y > 5 else 0), y, z, "jungle_log")
        tx, ty = x + 1, 8
        for (ox, oz) in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2)]:
            g.put(tx + ox, ty, z + oz, "jungle_leaves[persistent=true]")
        for (ox, oz) in ((3, 0), (-3, 0), (0, 3), (0, -3)):
            g.put(tx + ox, ty - 1, z + oz, "jungle_leaves[persistent=true]")
        g.put(tx, ty + 1, z, "jungle_leaves[persistent=true]")
    for (x, z) in ((6, 20), (-6, -20), (20, -6), (-20, 6), (-6, 20), (6, -20), (20, 6), (-20, -6)):
        for y in (1, 2, 3): g.put(x, y, z, "sandstone_wall")
        g.put(x, 4, z, "chiseled_sandstone")
        g.put(x, 5, z, "lantern")
    return g


def check(g, spawns):
    """Every spawn must be clear and able to walk to the centre."""
    def blocked(x, z):
        b1, b2 = g.get(x, 1, z), g.get(x, 2, z)
        pas = lambda b: b is None or any(s in om.nm(b) for s in om.PASSABLE + ("dead_bush", "air"))
        if b1 and (om.is_fence(b1) or om.is_wall(b1) or om.is_pane(b1) or "campfire" in b1): return True
        return not pas(b2) or (not pas(b1) and not pas(g.get(x, 3, z)))
    start = (0, 4)
    seen, todo = {start}, deque([start])
    while todo:
        x, z = todo.popleft()
        for (ox, oz) in DIRS.values():
            n = (x + ox, z + oz)
            if abs(n[0]) <= AR and abs(n[1]) <= AR and n not in seen and not blocked(*n):
                seen.add(n); todo.append(n)
    for (sx, sz, _) in spawns:
        assert not blocked(sx, sz), f"arena spawn {sx},{sz} is blocked"
        assert (sx, sz) in seen, f"arena spawn {sx},{sz} can't reach the centre"
    return len(seen)
