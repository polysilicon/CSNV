"""Skyblock expansion (imported by skyblock.py): pets, resource zones and their warps. The mod does the rest
(Bazaar.java, Upgrades.java, Pets.java, Zones.java); this file builds the zones and puts the pet and zone settings
into storage crispy_skyblock:eco cfg (pets, zones), which the mod reads.

Resource zones are shared areas off the hub where blocks regenerate (the mod turns a mined block into bedrock and
puts it back after `secs`) and hostile mobs roam while anyone is there. Only the listed blocks can be mined; nothing
can be placed. /warp or the Warps NPC in the hub takes you there.
"""
import math
import random

# ------------------------------------------------------------------ pets
# key, name, skill (the XP it boosts), price (None = only from End bosses), head texture (/heads animals), stat line
# head textures (from the Head Index "animals" category) are in pet_heads.json
PETS = [
    ("pig", "Pig", "FARMING", 2500, "+speed while farming"),
    ("silverfish", "Silverfish", "MINING", 5000, "+mining speed"),
    ("fox", "Fox", "FORAGING", 5000, "+speed"),
    ("wolf", "Wolf", "COMBAT", 8000, "+damage"),
    ("squid", "Squid", "FISHING", 5000, "+luck"),
    ("phoenix", "Phoenix", "ALL", None, "+2 hearts · boosts every skill"),
]
PHOENIX_CHANCE = 3    # % per island member per End boss kill

# ------------------------------------------------------------------ zones
MINES = (-260, 90, -360)     # rim of the pit at y 90
WOODS = (260, 100, -360)
STONES = ["stone", "cobblestone", "andesite", "diorite", "granite", "tuff", "deepslate", "cobbled_deepslate"]
ORES = ["coal_ore", "iron_ore", "copper_ore", "gold_ore", "lapis_ore", "redstone_ore", "diamond_ore", "emerald_ore"]
LOGS = ["oak_log", "birch_log", "spruce_log", "dark_oak_log", "cherry_log"]
ZONES = [
    # key, name, centre, box half-size (x/z), y range, minable blocks, seconds to regrow, mobs, warp (x, y, z, yaw)
    ("mines", "The Deep Mines", MINES, 40, (MINES[1] - 34, MINES[1] + 12), STONES + ORES + [f"deepslate_{o}" for o in ORES if o != "emerald_ore"] + ["deepslate_emerald_ore"],
     45, ["zombie", "skeleton", "cave_spider", "silverfish", "husk"], (MINES[0] + 0.5, MINES[1] + 1, MINES[2] - 30.5, 0)),
    ("woods", "Whispering Woods", WOODS, 38, (WOODS[1] - 16, WOODS[1] + 20), LOGS,
     30, ["spider", "zombie", "witch", "skeleton"], (WOODS[0] + 0.5, WOODS[1] + 1, WOODS[2] - 27.5, 0)),
]
ZONE_CAP = 8          # mobs per zone at once (+2 per player there)


def build(NS, fn, js, txt, snbt, Build):
    """Build: skyblock.py's relative-coordinate builder."""
    import json, os
    heads = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pet_heads.json")))
    cfg = {
        "pets": [{"key": k, "name": n, "skill": s, "price": p or 0, "shop": p is not None, "stat": st, "tex": heads[k]["value"]}
                 for k, n, s, p, st in PETS],
        "zones": [{"key": k, "name": n, "x1": c[0] - h, "z1": c[2] - h, "x2": c[0] + h, "z2": c[2] + h, "y1": y[0], "y2": y[1],
                   "allow": [f"minecraft:{b}" for b in allow], "secs": secs, "warp": list(w)}
                  for k, n, c, h, y, allow, secs, mobs, w in ZONES],
    }
    box = lambda z: f"x={z[2][0] - z[3]},y={z[4][0]},z={z[2][2] - z[3]},dx={2 * z[3]},dy={z[4][1] - z[4][0]},dz={2 * z[3]}"

    # ---- the Deep Mines: a floating rock island with a terraced pit; ores get richer deeper down
    rnd = random.Random(77)
    cx, cy, cz = MINES
    R, DEPTH, PIT, FLOOR = 36, 32, 27, 22        # island radius and depth; pit rim radius; pit depth
    solid = {}
    for d in range(DEPTH + 1):
        rr = R * (1 - d / (DEPTH + 1.2)) ** 0.75
        for x in range(-R, R + 1):
            for z in range(-R, R + 1):
                dist = math.hypot(x, z)
                if dist > rr + rnd.random() * 0.8: continue
                pit = PIT - d if d <= FLOOR else -1        # a funnel: one block narrower per level = walkable terraces
                if dist <= pit: continue
                base = "deepslate" if d >= 14 else rnd.choices(["stone", "andesite", "tuff", "diorite", "granite"], [10, 2, 2, 1, 1])[0]
                solid[(x, -d, z)] = base
    def ore_for(d):
        if d < 6: return rnd.choices(["coal_ore", "iron_ore", "copper_ore"], [50, 30, 20])[0]
        if d < 14: return rnd.choices(["iron_ore", "coal_ore", "gold_ore", "lapis_ore", "redstone_ore"], [35, 20, 15, 15, 15])[0]
        return "deepslate_" + rnd.choices(["iron_ore", "gold_ore", "lapis_ore", "redstone_ore", "diamond_ore", "emerald_ore"], [25, 20, 15, 20, 15, 5])[0]
    for (x, y, z), b in list(solid.items()):
        exposed = any((x + dx, y + dy, z + dz) not in solid for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))
        if exposed and math.hypot(x, z) < PIT + 2 and rnd.random() < 0.13: solid[(x, y, z)] = ore_for(-y)
    cmds = [f"fill {cx - R - 1} {cy - DEPTH - 1} {cz - R - 1} {cx + R + 1} {cy + 12} {cz + R + 1} minecraft:air"]
    rows = {}
    for (x, y, z), b in solid.items(): rows.setdefault((y, z), []).append((x, b))
    for (y, z), xs in rows.items():   # run-length fills along x
        xs.sort()
        start, prev, blk = xs[0][0], xs[0][0], xs[0][1]
        for x, b in xs[1:] + [(None, None)]:
            if x is not None and x == prev + 1 and b == blk: prev = x; continue
            cmds.append(f"fill {cx + start} {cy + y} {cz + z} {cx + prev} {cy + y} {cz + z} minecraft:{blk}" if start != prev
                        else f"setblock {cx + start} {cy + y} {cz + z} minecraft:{blk}")
            if x is not None: start, prev, blk = x, x, b
    wx, wy, wz = cx, cy, cz - 30   # the arrival platform on the rim
    cmds += [f"fill {wx - 2} {wy} {wz - 2} {wx + 2} {wy} {wz + 2} minecraft:polished_andesite",
             f"summon minecraft:text_display {wx + 0.5} {wy + 3} {wz + 0.5} {{Tags:[\"{NS}\",\"cs_zonel\"],billboard:\"center\",text:"
             + snbt({"text": "The Deep Mines", "color": "gray", "bold": True, "extra": [txt("\nOres grow back · mobs lurk below · /warp hub", "dark_gray", bold=False)]}) + "}"]
    # the portal back to the hub, just behind the arrival platform
    cmds += [f"fill {wx - 3} {wy} {wz - 5} {wx + 3} {wy} {wz - 2} minecraft:polished_andesite",
             f"fill {wx - 3} {wy - 1} {wz - 5} {wx + 3} {wy - 1} {wz - 2} minecraft:cobbled_deepslate",
             f"fill {wx - 3} {wy + 1} {wz - 5} {wx + 3} {wy + 8} {wz - 2} minecraft:air",
             f"execute positioned {wx} {wy} {wz - 3} run function {NS}:portal/style_mines",
             f"summon minecraft:text_display {wx + 0.5} {wy + 7.2} {wz - 2.5} {{Tags:[\"{NS}\",\"cs_zonel\"],billboard:\"center\",text:"
             + snbt({"text": "Hub", "color": "gold", "bold": True, "extra": [txt("\nWalk through to go back", "gray", bold=False)]}) + "}"]
    mine_spawns = [(round((PIT - d - 1) * math.cos(a)), -d + 1, round((PIT - d - 1) * math.sin(a))) for d in (4, 9, 14, 19) for a in (0.4, 2.0, 3.6, 5.2)]
    fn("zones/build_mines", "\n".join(cmds))

    # ---- Whispering Woods: a grassy island thick with trees
    b = Build(91)
    b.blob(34, 12, "grass_block", "dirt", "stone")
    spots = []
    for _ in range(400):
        x, z = b.rnd.randint(-28, 28), b.rnd.randint(-28, 28)
        if math.hypot(x, z) > 29 or (abs(x) <= 4 and z < -20): continue
        if all(math.hypot(x - sx, z - sz) >= 5 for sx, sz in spots): spots.append((x, z))
    kinds = [("oak_log", "oak_leaves"), ("birch_log", "birch_leaves"), ("dark_oak_log", "dark_oak_leaves"), ("cherry_log", "cherry_leaves")]
    for i, (x, z) in enumerate(spots):
        if i % 5 == 4: b.spruce(x, z, 7 + i % 3)
        else:
            log, leaves = kinds[i % 4]
            b.oak(x, z, 5 + i % 3, log, leaves)
    b.fill(-2, 0, -29, 2, 0, -25, "moss_block")
    wood_cmds = [f"execute positioned {WOODS[0]} {WOODS[1]} {WOODS[2]} run function {NS}:zones/woods_island",
                 f"summon minecraft:text_display {WOODS[0] + 0.5} {WOODS[1] + 3} {WOODS[2] - 26.5} {{Tags:[\"{NS}\",\"cs_zonel\"],billboard:\"center\",text:"
                 + snbt({"text": "Whispering Woods", "color": "dark_green", "bold": True, "extra": [txt("\nLogs grow back · beware the spiders · /warp hub", "dark_gray", bold=False)]}) + "}"]
    wood_cmds += [f"fill {WOODS[0] - 3} {WOODS[1]} {WOODS[2] - 33} {WOODS[0] + 3} {WOODS[1]} {WOODS[2] - 29} minecraft:moss_block",
                  f"fill {WOODS[0] - 3} {WOODS[1] - 1} {WOODS[2] - 33} {WOODS[0] + 3} {WOODS[1] - 1} {WOODS[2] - 29} minecraft:dirt",
                  f"fill {WOODS[0] - 3} {WOODS[1] + 1} {WOODS[2] - 33} {WOODS[0] + 3} {WOODS[1] + 9} {WOODS[2] - 30} minecraft:air",
                  f"execute positioned {WOODS[0]} {WOODS[1]} {WOODS[2] - 31} run function {NS}:portal/style_woods",
                  f"summon minecraft:text_display {WOODS[0] + 0.5} {WOODS[1] + 8.4} {WOODS[2] - 30.5} {{Tags:[\"{NS}\",\"cs_zonel\"],billboard:\"center\",text:"
                  + snbt({"text": "Hub", "color": "gold", "bold": True, "extra": [txt("\nWalk through to go back", "gray", bold=False)]}) + "}"]
    fn("zones/woods_island", "\n".join(b.c))
    fn("zones/build_woods", "\n".join(wood_cmds))
    woods_spawns = [(x, 1, z + 2) for x, z in spots[::3]][:16]
    fn("zones/portals_v2", "\n".join(cmds[-5:] + wood_cmds[-5:]))
    fn("zones/build_all", "\n".join([
        "kill @e[type=minecraft:text_display,tag=cs_zonel]",
        *[f"forceload add {c[0] - h - 2} {c[2] - h - 2} {c[0] + h + 2} {c[2] + h + 2}" for k, n, c, h, *_ in ZONES],
        f"function {NS}:zones/build_mines", f"function {NS}:zones/build_woods",
        *[f"forceload remove {c[0] - h - 2} {c[2] - h - 2} {c[0] + h + 2} {c[2] + h + 2}" for k, n, c, h, *_ in ZONES],
        "scoreboard players set #zonesv cs_cfg 1"]))

    # ---- mobs: while someone is in a zone, keep up to ZONE_CAP (+2 per player) hostiles there; none when it's empty
    sec = []
    for z in ZONES:
        key, name, c, h, y, allow, secs, mobs, w = z
        spawns = mine_spawns if key == "mines" else woods_spawns
        rp = (c[0], c[1], c[2] - 33) if key == "mines" else (c[0], c[1], c[2] - 31)
        sec += [f"execute if entity @a[{box(z)}] positioned {rp[0]} {rp[1]} {rp[2]} run function {NS}:portal/fx_{key}"]
        sec += [f"execute unless entity @a[{box(z)}] run kill @e[tag=cs_zone_{key}]",
                f"execute if entity @a[{box(z)}] run function {NS}:zones/{key}/tick"]
        roll = [f"execute store result score #n cs_tmp if entity @e[tag=cs_zone_{key}]",
                f"execute store result score #pl cs_tmp if entity @a[{box(z)}]",
                f"scoreboard players operation #pl cs_tmp *= #2c cs_tmp", f"scoreboard players add #pl cs_tmp {ZONE_CAP}",
                "execute if score #n cs_tmp >= #pl cs_tmp run return 0",
                "execute store result score #r cs_tmp run random value 1..3", "execute unless score #r cs_tmp matches 1 run return 0",
                f"execute store result score #r cs_tmp run random value 1..{len(spawns)}"]
        for i, (sx, sy, sz) in enumerate(spawns, 1):
            roll.append(f"execute if score #r cs_tmp matches {i} positioned {c[0] + sx}.5 {c[1] + sy} {c[2] + sz}.5 run function {NS}:zones/{key}/mob")
        fn(f"zones/{key}/tick", "\n".join(roll))
        mob = [f"execute store result score #m cs_tmp run random value 1..{len(mobs)}"]
        for i, m in enumerate(mobs, 1):
            mob.append(f"execute if score #m cs_tmp matches {i} run summon minecraft:{m} ~ ~ ~ {{Tags:[\"cs_zone_mob\",\"cs_zone_{key}\"],PersistenceRequired:1b}}")
        mob.append("particle minecraft:large_smoke ~ ~0.5 ~ 0.3 0.5 0.3 0.01 10")
        fn(f"zones/{key}/mob", "\n".join(mob))
    fn("zones/second", "\n".join(sec))
    fn("zones/tp", "$execute in minecraft:overworld run tp @s $(x) $(y) $(z) $(yaw) 0")

    # ---- the Phoenix: a rare drop from End bosses (boss/killed2 runs boss/phoenix_<realm>)
    fn("boss/phoenix_e", f"$execute as @a[scores={{cs_plot=$(id)}}] run function {NS}:boss/phoenix_roll")
    fn("boss/phoenix_n", "return 0")
    fn("boss/phoenix_roll", f"execute store result score #r cs_tmp run random value 1..100\nexecute if score #r cs_tmp matches ..{PHOENIX_CHANCE} run pets grant @s phoenix")

    in_zone = " ".join(f"unless entity @s[{box(z)}]" for z in ZONES)
    return {"cfg": cfg, "in_zone": in_zone}
