"""The hub island's detail (imported by skyblock.py's hub_build): cliffs and a hanging underside, a patterned plaza
with benches, planters and lamp posts, a tiered fountain, proper market stalls, worn paths, varied trees and bushes,
flower meadows, boulders and fallen logs, a lookout tower, a gazebo and a waterfall off the island's edge.

Everything works on hub_build's own data: top[(x, z)] = the surface block's y, bottom[(x, z)] = the column's lowest
block, used = cells something already stands on (plots, paths, pond...), and appends commands to c."""
import math

N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
FACE = {(1, 0): "west", (-1, 0): "east", (0, 1): "north", (0, -1): "south"}   # a vine east of a block hangs on its west side


# ------------------------------------------------------------------ cliffs and underside
def cliffs(c, top, bottom, rnd, noise, Y):
    """Edge columns: banded rock instead of plain stone, a grass lip with vines and roots hanging over the side.
    Underneath: dripstone stalactites, hanging roots and glow lichen."""
    edge = {k for k in top if any((k[0] + a, k[1] + b) not in top for a, b in N4)}
    bands = ["stone", "andesite", "stone", "tuff", "stone", "calcite", "andesite", "stone", "deepslate", "stone"]
    for (x, z) in edge:
        t, b = top[(x, z)], bottom[(x, z)]
        for y in range(b + 1, t - 3):
            band = bands[int((y + 3 * noise(x * 0.05, z * 0.05, 21)) // 3) % len(bands)]
            if band != "stone": c.append(f"setblock {x} {y} {z} minecraft:{band}")
        for a, b2 in N4:
            n = (x + a, z + b2)
            if n in top: continue
            r_ = rnd.random()
            if r_ < 0.32:
                ln = rnd.randint(1, 6)
                c.append(f"fill {n[0]} {t - ln} {n[1]} {n[0]} {t} {n[1]} minecraft:vine[{FACE[(a, b2)]}=true] replace minecraft:air")
            elif r_ < 0.38:
                c.append(f"setblock {n[0]} {t - 1} {n[1]} minecraft:glow_lichen[{FACE[(a, b2)]}=true]")
    # the underside: hanging things under the lowest block of a column (only where nothing is directly below)
    for (x, z), b in bottom.items():
        r_ = rnd.random()
        if r_ < 0.035:
            ln = rnd.choice([1, 2, 2, 3, 3, 4])
            parts = (["base"] + ["middle"] * max(0, ln - 3) + ["frustum"] + ["tip"])[-ln:] if ln > 1 else ["tip"]
            if ln == 2: parts = ["frustum", "tip"]
            for i, th in enumerate(parts):
                c.append(f"setblock {x} {b - 1 - i} {z} minecraft:pointed_dripstone[vertical_direction=down,thickness={th}]")
            c.append(f"setblock {x} {b} {z} minecraft:dripstone_block")
        elif r_ < 0.06:
            c.append(f"setblock {x} {b - 1} {z} minecraft:hanging_roots")
            c.append(f"setblock {x} {b} {z} minecraft:rooted_dirt")
        elif r_ < 0.085:
            c.append(f"setblock {x} {b - 1} {z} minecraft:glow_lichen[up=true]")
    return edge


# ------------------------------------------------------------------ ground cover
def ground(c, top, used, rnd, noise, surf):
    """Patches of coarse dirt, podzol, moss and rooted dirt in the hills, so the grass isn't one flat green."""
    for (x, z), t in top.items():
        if (x, z) in used or math.hypot(x, z) < 17: continue
        n = noise(x * 0.09 + 40, z * 0.09 + 40, 31)
        m = noise(x * 0.3, z * 0.3, 32)
        if n > 0.78 and m > 0.4: surf(x, z, "coarse_dirt")
        elif n < 0.16 and m > 0.45: surf(x, z, "moss_block")
        elif 0.5 < n < 0.53 and m > 0.6: surf(x, z, "rooted_dirt")


def path_block(kind, rnd):
    if kind == "stone":
        return rnd.choices(["stone_bricks", "mossy_stone_bricks", "cracked_stone_bricks", "andesite", "polished_andesite"], [60, 14, 12, 7, 7])[0]
    if kind == "dirt":
        return rnd.choices(["dirt_path", "coarse_dirt", "gravel", "packed_mud", "rooted_dirt"], [72, 12, 7, 5, 4])[0]
    return kind


# ------------------------------------------------------------------ plaza
def plaza(c, top, used, rnd, surf, Y, keep_clear):
    """A compass-rose floor, a mossy-edged border, benches, planters and lamp posts round the edge."""
    for (x, z) in top:
        r = math.hypot(x, z)
        if r > 10.6: continue
        a = (math.degrees(math.atan2(z, x)) + 360) % 360
        spoke = min(abs(((a + 22.5) % 45) - 22.5), 45) * math.pi / 180 * r < 0.75   # 8 spokes
        if r <= 3.6: continue                                   # the fountain
        if r <= 4.6: b = "chiseled_stone_bricks" if (round(a) // 30) % 2 else "polished_andesite"
        elif spoke and r <= 8.5: b = "stone_bricks" if r > 5.5 else "chiseled_stone_bricks"
        elif r <= 8.5: b = rnd.choices(["polished_andesite", "andesite", "smooth_stone"], [6, 3, 1])[0] if (int(r * 1.0) % 2) else "polished_andesite"
        elif r <= 9.6: b = rnd.choices(["stone_bricks", "mossy_stone_bricks", "cracked_stone_bricks"], [7, 2, 1])[0]
        else: b = rnd.choices(["mossy_stone_bricks", "stone_bricks", "moss_block", "coarse_dirt"], [3, 4, 2, 1])[0]
        surf(x, z, b); used.add((x, z))
    # around the edge, between the paths: planters (hedge + flowers) and benches facing the fountain, lamp posts
    for ang in (22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5):
        a = math.radians(ang)
        lx, lz = round(9.3 * math.cos(a)), round(9.3 * math.sin(a))
        if (lx, lz) in keep_clear: continue
        c += [f"setblock {lx} {Y + 1} {lz} minecraft:stone_brick_wall", f"setblock {lx} {Y + 2} {lz} minecraft:stone_brick_wall",
              f"setblock {lx} {Y + 3} {lz} minecraft:lantern"]
    for ang in (45, 135, 225, 315):
        a = math.radians(ang)
        # a planter: a 3-wide hedge of azalea on mossy bricks, with flowers in front
        px, pz = round(11.5 * math.cos(a)), round(11.5 * math.sin(a))
        tx, tz = -math.sin(a), math.cos(a)
        for k in (-1, 0, 1):
            x, z = round(px + tx * k), round(pz + tz * k)
            if (x, z) in keep_clear: continue
            c += [f"setblock {x} {Y} {z} minecraft:mossy_stone_bricks", f"setblock {x} {Y + 1} {z} minecraft:{'flowering_azalea' if k == 0 else 'azalea'}"]
            used.add((x, z))
        # a bench just inside, facing the fountain: two stairs with trapdoor arms
        bx, bz = 7 * math.cos(a), 7 * math.sin(a)
        facing = {45: "north", 135: "north", 225: "south", 315: "south"}[ang]   # benches on the diagonals face along z
        for k in (-0.5, 0.5):
            x, z = round(bx + k), round(bz)
            c.append(f"setblock {x} {Y + 1} {z} minecraft:spruce_stairs[facing={facing}]")
    return c


def fountain(c, top, Y):
    """A tiered fountain: a glowing basin with a rim, a central column with an upper bowl spilling water."""
    for (x, z) in list(top):
        r = math.hypot(x, z)
        if r <= 2.6:
            c += [f"setblock {x} {Y} {z} minecraft:water", f"setblock {x} {Y - 1} {z} minecraft:{'sea_lantern' if (x + z) % 3 == 0 else 'stone_bricks'}"]
        elif r <= 3.6:
            c += [f"setblock {x} {Y} {z} minecraft:stone_bricks", f"setblock {x} {Y + 1} {z} minecraft:stone_brick_slab[type=bottom]"]
    c += [f"fill 0 {Y} 0 0 {Y + 2} 0 minecraft:chiseled_stone_bricks", f"setblock 0 {Y + 3} 0 minecraft:water",
          f"setblock 1 {Y + 1} 1 minecraft:lily_pad", f"setblock -2 {Y + 1} 0 minecraft:lily_pad"]
    for dx, dz in N4:   # four spouts on the column
        c.append(f"setblock {dx} {Y + 1} {dz} minecraft:stone_brick_stairs[facing={ {(1, 0): 'west', (-1, 0): 'east', (0, 1): 'north', (0, -1): 'south'}[(dx, dz)] },half=top,waterlogged=true]")


# ------------------------------------------------------------------ market stalls
STALL_DECO = {
    "farming": ["hay_block", "pumpkin", "melon", "hay_block"],
    "mining": ["coal_block", "raw_iron_block", "raw_copper_block", "iron_block"],
    "foraging": ["oak_log", "birch_log", "spruce_log", "cherry_log"],
    "combat": ["target", "bone_block", "polished_blackstone_bricks", "target"],
    "supplies": ["bricks", "stone_bricks", "terracotta", "mud_bricks"],
}


def stalls(c, used, Y, STALLS):
    """5x5 stalls: plank floor with a log border, corner posts, a striped awning with a ridge, a counter either side of
    the open front (where the merchant stands), goods stacked at the back and hanging lanterns."""
    for key, sx, sz, wool, prof in STALLS:
        # front = the side towards the plaza centre
        if abs(sx) >= abs(sz): fx, fz = (-1 if sx > 0 else 1), 0
        else: fx, fz = 0, (-1 if sz > 0 else 1)
        sx_, sz_ = -fz, fx                                  # sideways
        stair_out = {(1, 0): "west", (-1, 0): "east", (0, 1): "north", (0, -1): "south"}[(fx, fz)]
        L = lambda f, s: (sx + fx * f + sx_ * s, sz + fz * f + sz_ * s)   # local (forward, side) to world
        for f in range(-2, 3):
            for s in range(-2, 3):
                x, z = L(f, s)
                edge = abs(f) == 2 or abs(s) == 2
                c.append(f"setblock {x} {Y} {z} minecraft:{'stripped_spruce_log' if edge else 'spruce_planks'}")
                c.append(f"fill {x} {Y + 1} {z} {x} {Y + 6} {z} minecraft:air")
                used.add((x, z))
        for f in (-2, 2):
            for s in (-2, 2):
                x, z = L(f, s)
                c.append(f"fill {x} {Y + 1} {z} {x} {Y + 3} {z} minecraft:stripped_spruce_log")
        # awning: stripes across, the front edge as stairs dipping out
        for f in range(-2, 3):
            for s in range(-2, 3):
                x, z = L(f, s)
                c.append(f"setblock {x} {Y + 4} {z} minecraft:{wool if s % 2 == 0 else 'white'}_wool")
        for s in range(-2, 3):
            x, z = L(3, s)
            c.append(f"setblock {x} {Y + 4} {z} minecraft:spruce_stairs[facing={stair_out},half=top]")
        for f in range(-1, 2):
            for s in range(-1, 2):
                x, z = L(f, s)
                c.append(f"setblock {x} {Y + 5} {z} minecraft:{wool}_carpet" if (f, s) != (0, 0) else f"setblock {x} {Y + 5} {z} minecraft:{wool}_wool")
        # counter: either side of the open middle at the front
        for s in (-1, 1):
            x, z = L(1, s)
            c.append(f"setblock {x} {Y + 1} {z} minecraft:stripped_spruce_wood")
        # goods at the back
        deco = STALL_DECO.get(key, ["barrel"] * 4)
        for i, s in enumerate((-1, 0, 1)):
            x, z = L(-1, s)
            c.append(f"setblock {x} {Y + 1} {z} minecraft:{deco[i]}")
        x, z = L(-1, -1)
        c.append(f"setblock {x} {Y + 2} {z} minecraft:{deco[3]}")
        for s in (-1, 1):   # lanterns hanging from the awning at the front
            x, z = L(1, s * 2)
            c.append(f"setblock {x} {Y + 3} {z} minecraft:lantern[hanging=true]")
        c.append(f"setblock {sx} {Y + 3} {sz} minecraft:light[level=13]")


# ------------------------------------------------------------------ trees and plants
def tree(c, rnd, x, t, z, kind):
    """One of several tree shapes; returns the footprint radius."""
    def L(b): return f"minecraft:{b}[persistent=true]"
    if kind == "spruce":
        h = rnd.randint(8, 11)
        layers = [0, 0, 1, 1, 2, 1, 2, 3, 2, 3, 3]          # leaf radius from the top down, like a real spruce
        top_y = t + h + 1
        for i, r in enumerate(layers[:h - 1]):
            y = top_y - i
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    d = dx * dx + dz * dz
                    if d > r * r + r * 0.6 or (d and d >= r * r and rnd.random() < 0.25): continue
                    c.append(f"setblock {x + dx} {y} {z + dz} {L('spruce_leaves')}")
        c.append(f"fill {x} {t + 1} {z} {x} {t + h} {z} minecraft:spruce_log")
        return 3
    if kind == "big_oak":
        h = rnd.randint(7, 9)
        c.append(f"fill {x} {t + 1} {z} {x} {t + h} {z} minecraft:oak_log")
        for dx, dz in rnd.sample([(1, 0), (-1, 0), (0, 1), (0, -1)], 3):   # branches
            by = t + rnd.randint(h - 3, h - 1)
            ax = "x" if dx else "z"
            c += [f"setblock {x + dx} {by} {z + dz} minecraft:oak_log[axis={ax}]", f"setblock {x + 2 * dx} {by} {z + 2 * dz} minecraft:oak_log[axis={ax}]"]
            cx, cz = x + 2 * dx, z + 2 * dz
            c.append(f"fill {cx - 2} {by + 1} {cz - 2} {cx + 2} {by + 2} {cz + 2} {L('oak_leaves')} replace minecraft:air")
            c.append(f"fill {cx - 1} {by + 3} {cz - 1} {cx + 1} {by + 3} {cz + 1} {L('oak_leaves')} replace minecraft:air")
        c.append(f"fill {x - 2} {t + h - 1} {z - 2} {x + 2} {t + h + 1} {z + 2} {L('oak_leaves')} replace minecraft:air")
        c.append(f"fill {x - 1} {t + h + 2} {z - 1} {x + 1} {t + h + 2} {z + 1} {L('oak_leaves')} replace minecraft:air")
        c.append(f"fill {x} {t + 1} {z} {x} {t + h} {z} minecraft:oak_log")
        if rnd.random() < 0.4: c.append(f"setblock {x} {t + h - 3} {z + 1} minecraft:bee_nest[facing=south]")
        return 4
    log, leaves = {"oak": ("oak_log", "oak_leaves"), "birch": ("birch_log", "birch_leaves"), "cherry": ("cherry_log", "cherry_leaves"),
                   "azalea": ("oak_log", "azalea_leaves")}[kind]
    h = rnd.randint(5, 7) if kind == "birch" else rnd.randint(4, 6)
    for dy in (h - 2, h - 1):
        c.append(f"fill {x - 2} {t + dy} {z - 2} {x + 2} {t + dy} {z + 2} {L(leaves)} replace minecraft:air")
        for cx, cz in ((-2, -2), (-2, 2), (2, -2), (2, 2)):
            if rnd.random() < 0.7: c.append(f"setblock {x + cx} {t + dy} {z + cz} minecraft:air")
    c.append(f"fill {x - 1} {t + h} {z - 1} {x + 1} {t + h} {z + 1} {L(leaves)} replace minecraft:air")
    c.append(f"setblock {x} {t + h + 1} {z} {L(leaves)}")
    if kind == "azalea":
        for _ in range(4):
            c.append(f"setblock {x + rnd.randint(-2, 2)} {t + h - rnd.randint(1, 2)} {z + rnd.randint(-2, 2)} {L('flowering_azalea_leaves')}")
    c.append(f"fill {x} {t + 1} {z} {x} {t + h - 1} {z} minecraft:{log}")
    if kind == "birch" and rnd.random() < 0.25: c.append(f"setblock {x} {t + h - 3} {z - 1} minecraft:bee_nest[facing=north]")
    return 2


def plants(c, top, used, rnd, noise, Y, district, avoid):
    """Trees in groves (spruce up north, cherries by the pond, oaks and birches elsewhere), bushes, flower meadows,
    pink petals under the cherries, boulders and fallen logs."""
    trees = []
    keys = sorted(top)
    rnd.shuffle(keys)
    for (x, z) in keys:
        r = math.hypot(x, z)
        if not (18 < r < district.ISLAND - 4) or (x, z) in used or district.in_plot(x, z, 4) or (x, z) in avoid: continue
        if any(math.hypot(x - a, z - b) < 6.5 for a, b, _k in trees): continue
        if len(trees) >= 110: break
        g = noise(x * 0.025 + 11, z * 0.025 + 11, 41)
        if z < -40 and g < 0.6: kind = "spruce"
        elif math.hypot(x + 36, z) < 26: kind = "cherry"
        elif g > 0.7: kind = "big_oak"
        elif g > 0.5: kind = "birch"
        elif g < 0.25: kind = "azalea"
        else: kind = "oak"
        trees.append((x, z, kind))
    for x, z, kind in trees:
        t = top[(x, z)]
        rr = tree(c, rnd, x, t, z, kind)
        for dx in range(-rr, rr + 1):
            for dz in range(-rr, rr + 1): used.add((x + dx, z + dz))
        if kind == "cherry":   # petals round the trunk
            for dx in range(-3, 4):
                for dz in range(-3, 4):
                    k = (x + dx, z + dz)
                    if k in top and k not in used and rnd.random() < 0.45:
                        c.append(f"setblock {k[0]} {top[k] + 1} {k[1]} minecraft:pink_petals[flower_amount={rnd.randint(1, 4)}]")
                        used.add(k)
    # bushes
    n_b = 0
    for (x, z) in keys:
        if n_b >= 140: break
        r = math.hypot(x, z)
        if not (14 < r < district.ISLAND - 2) or (x, z) in used or district.in_plot(x, z, 2) or (x, z) in avoid: continue
        if rnd.random() > 0.05: continue
        t = top[(x, z)]
        leaves = rnd.choice(["oak_leaves", "azalea_leaves", "flowering_azalea_leaves", "birch_leaves"])
        c.append(f"setblock {x} {t + 1} {z} minecraft:{leaves}[persistent=true]")
        if rnd.random() < 0.5:
            dx, dz = rnd.choice(N4)
            if (x + dx, z + dz) in top and (x + dx, z + dz) not in used:
                c.append(f"setblock {x + dx} {t + 1} {z + dz} minecraft:{leaves}[persistent=true]")
                used.add((x + dx, z + dz))
        used.add((x, z)); n_b += 1
    # boulders
    n_r = 0
    for (x, z) in keys:
        if n_r >= 30: break
        r = math.hypot(x, z)
        if not (20 < r < district.ISLAND - 3) or district.in_plot(x, z, 3) or (x, z) in avoid: continue
        if any((x + a, z + b) in used for a in (-1, 0, 1, 2) for b in (-1, 0, 1, 2)): continue
        if rnd.random() > 0.02: continue
        t = top[(x, z)]
        stone = rnd.choice(["mossy_cobblestone", "cobblestone", "andesite", "stone", "tuff"])
        drop = rnd.choice([None, (1, 0), (0, 1)])
        for a in (0, 1):
            for b in (0, 1):
                if (a, b) != drop: c.append(f"setblock {x + a} {t + 1} {z + b} minecraft:{stone}")
        if rnd.random() < 0.6: c.append(f"setblock {x} {t + 2} {z} minecraft:{stone}")
        c.append(f"setblock {x + 1} {t + 2} {z + 1} minecraft:moss_carpet")
        for a in (-1, 0, 1, 2):
            for b in (-1, 0, 1, 2): used.add((x + a, z + b))
        n_r += 1
    # fallen logs with moss and mushrooms on top
    n_l = 0
    for (x, z) in keys:
        if n_l >= 12: break
        r = math.hypot(x, z)
        if not (20 < r < district.ISLAND - 6) or district.in_plot(x, z, 3) or (x, z) in avoid: continue
        dx, dz = rnd.choice(((1, 0), (0, 1)))
        cells = [(x + dx * i, z + dz * i) for i in range(4)]
        if any(k not in top or k in used or top[k] != top[(x, z)] for k in cells): continue
        if rnd.random() > 0.05: continue
        log = rnd.choice(["oak_log", "birch_log", "spruce_log"])
        for i, (a, b) in enumerate(cells):
            c.append(f"setblock {a} {top[(a, b)] + 1} {b} minecraft:{log}[axis={'x' if dx else 'z'}]")
            if i in (1, 2): c.append(f"setblock {a} {top[(a, b)] + 2} {b} minecraft:{rnd.choice(['moss_carpet', 'brown_mushroom', 'red_mushroom', 'moss_carpet'])}")
            used.add((a, b))
        n_l += 1
    # flowers in meadows: one or two kinds per patch, sparse grass between
    kinds = [["poppy", "dandelion"], ["oxeye_daisy", "azure_bluet"], ["cornflower", "allium"], ["dandelion", "oxeye_daisy"],
             ["red_tulip", "orange_tulip"], ["pink_tulip", "white_tulip"], ["lily_of_the_valley", "azure_bluet"], ["cornflower", "poppy"]]
    for (x, z), t in top.items():
        if (x, z) in used or math.hypot(x, z) < 12: continue
        m = noise(x * 0.06 + 70, z * 0.06 + 70, 51)
        k = kinds[int(noise(x * 0.02 + 5, z * 0.02 + 5, 52) * 7.99)]
        r_ = rnd.random()
        if m > 0.68 and r_ < 0.18: c.append(f"setblock {x} {t + 1} {z} minecraft:{rnd.choice(k)}")
        elif r_ < 0.10:
            g = rnd.choice(["short_grass"] * 5 + ["fern", "tall_grass"])
            if g == "tall_grass": c += [f"setblock {x} {t + 1} {z} minecraft:tall_grass[half=lower]", f"setblock {x} {t + 2} {z} minecraft:tall_grass[half=upper]"]
            else: c.append(f"setblock {x} {t + 1} {z} minecraft:{g}")


# ------------------------------------------------------------------ landmarks
def lookout(c, top, used, Y, ox, oz):
    """A stone lookout tower with a ladder up the inside to a railed platform and a pointed roof."""
    t = max(top.get((ox + a, oz + b), Y) for a in range(-2, 3) for b in range(-2, 3))
    lo = min(top.get((ox + a, oz + b), Y) for a in range(-3, 4) for b in range(-3, 4))
    H = 14
    c.append(f"fill {ox - 2} {lo - 1} {oz - 2} {ox + 2} {t} {oz + 2} minecraft:stone_bricks")
    c.append(f"fill {ox - 2} {t + 1} {oz - 2} {ox + 2} {t + H} {oz + 2} minecraft:stone_bricks")
    c.append(f"fill {ox - 1} {t + 1} {oz - 1} {ox + 1} {t + H} {oz + 1} minecraft:air")
    for y in range(t + 1, t + H, 4):   # mossy bands and windows
        c.append(f"fill {ox - 2} {y} {oz - 2} {ox + 2} {y} {oz + 2} minecraft:mossy_stone_bricks replace minecraft:stone_bricks")
    for y in (t + 5, t + 9):
        for a, b in ((0, -2), (2, 0), (-2, 0)):
            c.append(f"setblock {ox + a} {y} {oz + b} minecraft:glass_pane")
    for a, b in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
        c.append(f"fill {ox + a} {t + 1} {oz + b} {ox + a} {t + H} {oz + b} minecraft:polished_andesite")
    P = t + H + 1      # the platform
    c += [f"fill {ox} {t + 1} {oz + 2} {ox} {t + 2} {oz + 2} minecraft:air",                      # door on the south side
          f"setblock {ox} {t + 3} {oz + 2} minecraft:stone_brick_stairs[facing=north,half=top]",
          f"fill {ox} {t + 1} {oz - 1} {ox} {P} {oz - 1} minecraft:ladder[facing=south]",
          f"fill {ox - 3} {P} {oz - 3} {ox + 3} {P} {oz + 3} minecraft:spruce_planks",
          f"fill {ox - 3} {P - 1} {oz - 3} {ox + 3} {P - 1} {oz + 3} minecraft:spruce_slab[type=top] replace minecraft:air",
          f"setblock {ox} {P} {oz - 1} minecraft:ladder[facing=south]",
          f"fill {ox - 3} {P + 1} {oz - 3} {ox + 3} {P + 1} {oz + 3} minecraft:spruce_fence",
          f"fill {ox - 2} {P + 1} {oz - 2} {ox + 2} {P + 1} {oz + 2} minecraft:air"]
    for a, b in ((-3, -3), (3, -3), (-3, 3), (3, 3)):
        c.append(f"fill {ox + a} {P + 1} {oz + b} {ox + a} {P + 3} {oz + b} minecraft:spruce_log")
    R = P + 4          # the roof, resting on the corner posts
    c += [f"fill {ox - 3} {R} {oz - 3} {ox + 3} {R} {oz + 3} minecraft:dark_oak_planks",
          f"fill {ox - 4} {R} {oz - 4} {ox + 4} {R} {oz + 4} minecraft:dark_oak_slab[type=bottom] replace minecraft:air",
          f"fill {ox - 2} {R + 1} {oz - 2} {ox + 2} {R + 1} {oz + 2} minecraft:dark_oak_planks",
          f"fill {ox - 1} {R + 2} {oz - 1} {ox + 1} {R + 2} {oz + 1} minecraft:dark_oak_planks",
          f"setblock {ox} {R + 3} {oz} minecraft:dark_oak_slab[type=bottom]", f"setblock {ox} {R + 4} {oz} minecraft:lightning_rod"]
    for a, b in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
        c.append(f"setblock {ox + a} {R - 1} {oz + b} minecraft:lantern[hanging=true]")
    c.append(f"setblock {ox} {t + 4} {oz} minecraft:light[level=12]")
    c.append(f"setblock {ox} {t + 10} {oz} minecraft:light[level=12]")
    for a in range(-4, 5):
        for b in range(-4, 5): used.add((ox + a, oz + b))
    return t


def gazebo(c, top, used, Y, ox, oz):
    """An open octagonal gazebo with a bench ring and a hanging lantern."""
    t = top.get((ox, oz), Y)
    lo = min(top.get((ox + a, oz + b), t) for a in range(-4, 5) for b in range(-4, 5))
    cells = [(a, b) for a in range(-3, 4) for b in range(-3, 4) if math.hypot(a, b) <= 3.4]
    for a, b in cells:
        c += [f"setblock {ox + a} {t} {oz + b} minecraft:{'polished_granite' if math.hypot(a, b) < 2 else 'spruce_planks'}",
              f"fill {ox + a} {min(lo, t) - 1} {oz + b} {ox + a} {t - 1} {oz + b} minecraft:dirt",
              f"fill {ox + a} {t + 1} {oz + b} {ox + a} {t + 7} {oz + b} minecraft:air"]
        used.add((ox + a, oz + b))
    posts = [(3, 0), (-3, 0), (0, 3), (0, -3), (2, 2), (2, -2), (-2, 2), (-2, -2)]
    for a, b in posts:
        c.append(f"fill {ox + a} {t + 1} {oz + b} {ox + a} {t + 3} {oz + b} minecraft:stripped_dark_oak_log")
    for a, b in cells:
        c.append(f"setblock {ox + a} {t + 4} {oz + b} minecraft:dark_oak_planks")
    for a, b in [(a, b) for a in range(-2, 3) for b in range(-2, 3) if math.hypot(a, b) <= 2.3]:
        c.append(f"setblock {ox + a} {t + 5} {oz + b} minecraft:dark_oak_slab[type=bottom]")
    c += [f"setblock {ox} {t + 5} {oz} minecraft:dark_oak_planks", f"setblock {ox} {t + 6} {oz} minecraft:dark_oak_slab[type=bottom]",
          f"setblock {ox} {t + 3} {oz} minecraft:lantern[hanging=true]"]
    for a, b, f in ((2, 1, "west"), (2, -1, "west"), (-2, 1, "east"), (-2, -1, "east"), (1, -2, "south"), (-1, -2, "south")):
        c.append(f"setblock {ox + a} {t + 1} {oz + b} minecraft:spruce_stairs[facing={f}]")
    for a, b in ((4, 0), (-4, 0), (0, -4)):
        k = (ox + a, oz + b)
        if k in top: c.append(f"setblock {k[0]} {top[k] + 1} {k[1]} minecraft:flowering_azalea")


def waterfall(c, top, used, rnd, Y, ang):
    """A spring in a mossy rock pool near the edge, its stream running out over the side of the island."""
    a = math.radians(ang)
    dx, dz = math.cos(a), math.sin(a)
    r_edge = max(r for r in range(60, 110) if (round(r * dx), round(r * dz)) in top)
    pool = (round((r_edge - 9) * dx), round((r_edge - 9) * dz))
    t0 = top.get(pool, Y)
    # the pool: water 2 deep, mossy rock rim, a little rock spring with water spilling from it
    for i in range(-2, 3):
        for j in range(-2, 3):
            k = (pool[0] + i, pool[1] + j)
            if k not in top: continue
            if abs(i) <= 1 and abs(j) <= 1:
                c += [f"fill {k[0]} {t0 - 1} {k[1]} {k[0]} {t0} {k[1]} minecraft:water", f"setblock {k[0]} {t0 - 2} {k[1]} minecraft:mossy_cobblestone"]
                c.append(f"fill {k[0]} {t0 + 1} {k[1]} {k[0]} {t0 + 4} {k[1]} minecraft:air")
            else:
                c += [f"fill {k[0]} {min(top[k], t0)} {k[1]} {k[0]} {t0} {k[1]} minecraft:{rnd.choice(['mossy_cobblestone', 'mossy_stone_bricks', 'moss_block', 'cobblestone'])}",
                      f"fill {k[0]} {t0 + 1} {k[1]} {k[0]} {t0 + 4} {k[1]} minecraft:air"]
            used.add(k)
    back = (pool[0] - round(2 * dx) - (1 if abs(dz) > abs(dx) else 0) * 0, pool[1] - round(2 * dz))
    c += [f"fill {back[0]} {t0 + 1} {back[1]} {back[0]} {t0 + 3} {back[1]} minecraft:mossy_cobblestone",
          f"setblock {back[0]} {t0 + 4} {back[1]} minecraft:moss_carpet"]
    # the stream: a 1-wide channel at each cell's own ground (stepping down where the ground does), walled with moss
    last = t0
    for r in range(r_edge - 7, r_edge + 1):
        x, z = round(r * dx), round(r * dz)
        if (x, z) not in top: break
        y = min(top[(x, z)], last)
        c += [f"setblock {x} {y} {z} minecraft:water", f"fill {x} {y - 2} {z} {x} {y - 1} {z} minecraft:mossy_cobblestone",
              f"fill {x} {y + 1} {z} {x} {y + 3} {z} minecraft:air"]
        for sx, sz in ((-dz, dx), (dz, -dx)):
            k = (round(x + sx), round(z + sz))
            if k in top and k != (x, z):
                c += [f"fill {k[0]} {min(top[k], y)} {k[1]} {k[0]} {y} {k[1]} minecraft:{rnd.choice(['mossy_cobblestone', 'moss_block', 'stone'])}",
                      f"fill {k[0]} {y + 1} {k[1]} {k[0]} {y + 3} {k[1]} minecraft:air"]
                used.add(k)
        used.add((x, z)); last = y
    t0e = last
    # over the edge: the last cell's water flows out and down to the void
    x, z = round((r_edge + 1) * dx), round((r_edge + 1) * dz)
    c.append(f"setblock {x} {t0e} {z} minecraft:water")
    return pool, t0


def signpost(c, top, x, z, Y, lines, hsign, rot):
    t = top.get((x, z), Y)
    c += [f"setblock {x} {t + 1} {z} minecraft:spruce_fence", f"setblock {x} {t + 2} {z} minecraft:spruce_sign[rotation={rot}]" + hsign(lines, "black")]
