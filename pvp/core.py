"""Core Defense (imported by build.py): an Outbreak map (id CORE_ID) where the team guards a core instead of just surviving.

- A beacon (the core) sits on a clearing in a natural patch of world: grass hills, a pond, oak, birch and spruce trees,
  and dirt, stone and deepslate with ore veins down to bedrock (about 14 blocks deep, for trenches). The border is
  black concrete with a barrier shell behind it and barrier above; Mining Fatigue V right by it and patching during a
  run keep it whole. Players play in survival: they can mine, chop, craft, dig trenches and build walls around it. Everyone starts with stone tools,
  planks, cobblestone, a crafting table, a furnace and torches on top of their kit; the Arsenal (just south of the core)
  works as on the other maps.
- Mobs head for the core: they're tagged pve.seek and the PvP mod (spawnmod CoreSeek) walks any of them that isn't
  after a player to the core (#corex/#corey/#corez pve). Their follow range is cut to SEEK_RANGE, so only players
  close by pull them away. Zombies, husks, zombie villagers and vindicators only (melee mobs that can dig).
- Mobs break through: a mob that stands still with a block between it and the core chews through it (head height
  first, then feet): 3 s for most blocks, 5 s for stone-type blocks, twice as fast for Breakers (axe in hand). The
  Abomination clears a 3-wide, 4-high hole at a time. A mob stuck below the core (in a trench) digs a staircase up. Builders (cobblestone in hand) bridge gaps on the way to the core
  and pillar up under a player standing on something high nearby.
- Every mob within ~2.5 blocks of the core takes 1 core HP a second (the Abomination 5). The core has CORE_HP and gets
  CORE_HEAL back after every wave (boss bar "Core"). A player who breaks it gets it put straight back.
- Dying isn't "down" here: while the core stands you're back at a spawn after RESPAWN_S seconds, with your inventory
  (keep_inventory is on). When the core is destroyed the run is over.
- The map is rebuilt (pve/core_reset) when a run starts and when it ends, so every run starts on a fresh meadow.
"""
import math
import random

CORE_ID = 7
CORE_Z = 900
CORE_HP = 100
CORE_HEAL = 20          # core HP back after each wave
RESPAWN_S = 5
DIG = 6                 # checks (every 10 ticks) to break a block: 3 s
DIG_HARD = 10           # stone-type blocks (#minecraft:mineable/pickaxe): 5 s
CORE_REACH = 2.8        # mobs this close to the core's centre damage it
BOTTOM = -64            # the world's floor: bedrock (unbreakable), so trenches go down to BOTTOM + 1
DEEP_TOP = -59          # deepslate up to here, stone above
SURF = -49              # the ground (build.AY + 12): about 14 blocks of dirt and stone to dig trenches in
WALL_H = 6              # black concrete wall height above the ground
BOX_Y0 = BOTTOM - 1     # the map's selector box (build.PVE_BOXES uses it too)
BOX_DY = SURF + 32 - BOX_Y0
POND, POND_R = (-17, 13), 4.5
# the mob windows (build.MOB_POINTS), kept flat
MOB_POINTS = [(30, 0), (-30, 0), (0, 30), (0, -30), (30, 16), (30, -16), (-30, 16), (-30, -16), (16, 30), (-16, 30), (16, -30), (-16, -30)]
# ore, veins, y range (deepslate_ variants in deepslate)
ORES = [("coal_ore", 70, -58, -52), ("iron_ore", 45, -64, -53), ("copper_ore", 28, -58, -53), ("gold_ore", 10, -64, -57),
        ("redstone_ore", 12, -64, -58), ("lapis_ore", 8, -64, -55), ("diamond_ore", 4, -64, -60), ("emerald_ore", 2, -60, -53)]
SEEK_RANGE = 20         # core mobs only go after players this close (follow range); otherwise they head for the core
B_EXTRA = ',CustomName:{text:"Builder",color:"gold"},equipment:{mainhand:{id:"minecraft:cobblestone",count:1}},drop_chances:{mainhand:0.0f}'
K_EXTRA = ',CustomName:{text:"Breaker",color:"red"},equipment:{mainhand:{id:"minecraft:iron_axe",count:1}},drop_chances:{mainhand:0.0f}'
# this map's whole roster (rolls up to 100, so the normal pool, which has mobs that ignore villagers, is never used)
POOL = [(1, 18, "zombie", B_EXTRA), (1, 50, "zombie", ""), (2, 64, "husk", ""), (3, 76, "zombie_villager", ""),
        (4, 86, "vindicator", K_EXTRA), (6, 93, "zombie", K_EXTRA), (1, 100, "zombie", "")]
START_ITEMS = ["stone_pickaxe", "stone_axe", "stone_shovel", "oak_planks 32", "cobblestone 32", "crafting_table", "furnace",
               "torch 8"]
LORE = ["Guard the core in a patch of wild world", "Mine, chop, craft, dig trenches, build walls", "Mobs dig through walls and build up",
        "Respawn while the core stands", "Mobs: zombies, husks, Builders, Breakers"]


def terrain(PR):
    """Ground height offsets from SURF for x, z in -PR..PR: gentle hills, flat at the core and the mob windows, a pond.
    Returns (heights, sand, water): {(x, z): dh}, {(x, z)} with a sand top, {(x, z): water surface y offset}."""
    rng = random.Random(CORE_ID * 31)
    waves = [(rng.uniform(-0.22, 0.22), rng.uniform(-0.22, 0.22), rng.uniform(0, 6.3), a) for a in (1.6, 1.2, 0.8, 0.5)]
    def smooth(d, r0, r1):   # 0 inside r0, 1 outside r1
        t = min(1.0, max(0.0, (d - r0) / (r1 - r0)))
        return t * t * (3 - 2 * t)
    flat = [(0, 0, 8, 15)] + [(dx, dz, 3, 7) for dx, dz in MOB_POINTS] + [(POND[0], POND[1], 6, 9)]
    h, sand, water = {}, set(), {}
    for x in range(-PR, PR + 1):
        for z in range(-PR, PR + 1):
            v = 1.2 + sum(a * math.sin(fx * x + fz * z + ph) for fx, fz, ph, a in waves)
            w = min(smooth(math.hypot(x - fx, z - fz), r0, r1) for fx, fz, r0, r1 in flat)
            dh = round(max(-2.0, min(5.0, v)) * w)
            d = math.hypot(x - POND[0], z - POND[1])   # the pond: a bowl 1-3 deep, water one below the grass
            if d < POND_R:
                dh = -3 if d < POND_R - 2 else -2
                water[(x, z)] = -1
            if d < POND_R + 1.5:
                sand.add((x, z))
            h[(x, z)] = dh
    return h, sand, water


def map_cmds(b, cz):
    """(Re)build the Core Defense map: a natural patch of world (hills, a pond, trees, stone and ore down to bedrock)
    inside unbreakable black concrete walls, the core on a flat clearing in the middle, the Arsenal by it."""
    PCX, PR = b.PCX, b.PR
    x1, x2, z1, z2 = PCX - PR, PCX + PR, cz - PR, cz + PR
    W1, W2, Z1, Z2 = x1 - 1, x2 + 1, z1 - 1, z2 + 1
    box = b.box(PCX, cz, PR, BOX_Y0, BOX_DY)
    S = SURF
    a = [f"kill @e[type=minecraft:item,{box}]", f"kill @e[tag=pve.anchor,{box}]"]   # (pve.anchor: an older version's villager)
    # layers: bedrock, deepslate, stone, dirt, grass; air above (fills stay under 32768 blocks)
    a.append(f"fill {x1} {BOTTOM} {z1} {x2} {BOTTOM} {z2} minecraft:bedrock")
    layers = [(BOTTOM + 1, DEEP_TOP, "deepslate"), (DEEP_TOP + 1, S - 4, "stone"), (S - 3, S - 1, "dirt"), (S, S, "grass_block"),
              (S + 1, S + 30, "air")]
    for y0, y1, blk in layers:
        for k in range(y0, y1 + 1, 7):
            a.append(f"fill {x1} {k} {z1} {x2} {min(k + 6, y1)} {z2} minecraft:{blk}")
    # walls: black concrete from bedrock up to 6 above the ground, barrier above it and a barrier shell all round
    # (so even a broken wall block leads nowhere), barrier ceiling; Mining Fatigue near the wall (core_sec) and the
    # wall is patched during a run
    for (a1, b1, a2, b2) in ((W1, Z1, W2, Z1), (W1, Z2, W2, Z2), (W1, Z1, W1, Z2), (W2, Z1, W2, Z2)):
        a += [f"fill {a1} {BOTTOM} {b1} {a2} {S + WALL_H} {b2} minecraft:black_concrete",
              f"fill {a1} {S + WALL_H + 1} {b1} {a2} {S + 30} {b2} minecraft:barrier"]
    for (a1, b1, a2, b2) in ((W1 - 1, Z1 - 1, W2 + 1, Z1 - 1), (W1 - 1, Z2 + 1, W2 + 1, Z2 + 1), (W1 - 1, Z1 - 1, W1 - 1, Z2 + 1), (W2 + 1, Z1 - 1, W2 + 1, Z2 + 1)):
        a.append(f"fill {a1} {BOTTOM} {b1} {a2} {S + 31} {b2} minecraft:barrier")
    a.append(f"fill {W1 - 1} {S + 31} {Z1 - 1} {W2 + 1} {S + 31} {Z2 + 1} minecraft:barrier")

    rng = random.Random(CORE_ID)
    # underground: patches of granite, diorite, andesite, tuff, gravel and dirt, then ore veins
    for _ in range(55):
        x, z, y = rng.randint(x1 + 1, x2 - 1), rng.randint(z1 + 1, z2 - 1), rng.randint(BOTTOM + 1, S - 5)
        r = rng.randint(1, 2)
        blk = rng.choice(["granite", "diorite", "andesite", "tuff", "gravel", "dirt"])
        host = "deepslate" if y <= DEEP_TOP else "stone"
        a.append(f"fill {max(x - r, x1)} {max(y - r + 1, BOTTOM + 1)} {max(z - r, z1)} {min(x + r, x2)} {y} {min(z + r, z2)} minecraft:{blk} replace minecraft:{host}")
    for ore, n, ylo, yhi in ORES:
        for _ in range(n):
            x, z, y = rng.randint(x1, x2), rng.randint(z1, z2), rng.randint(max(ylo, BOTTOM + 1), min(yhi, S - 4))
            dx, dz, dy = rng.randint(0, 1), rng.randint(0, 1), rng.randint(0, 1)
            for host, name in (("stone", ore), ("deepslate", "deepslate_" + ore)):
                a.append(f"fill {x} {y} {z} {min(x + dx, x2)} {y + dy} {min(z + dz, z2)} minecraft:{name} replace minecraft:{host}")

    # the surface: runs of equal height along x, one or two fills each
    h, sand, water = terrain(PR)
    for z in range(-PR, PR + 1):
        x = -PR
        while x <= PR:
            dh, top = h[(x, z)], ("sand" if (x, z) in sand else "grass_block")
            e = x
            while e + 1 <= PR and h[(e + 1, z)] == dh and (("sand" if (e + 1, z) in sand else "grass_block") == top):
                e += 1
            X1, X2, Z = PCX + x, PCX + e, cz + z
            if dh > 0:
                a.append(f"fill {X1} {S} {Z} {X2} {S + dh - 1} {Z} minecraft:dirt")
            elif dh < 0:
                a.append(f"fill {X1} {S + dh + 1} {Z} {X2} {S} {Z} minecraft:air")
            if dh != 0 or top != "grass_block":
                a.append(f"fill {X1} {S + dh} {Z} {X2} {S + dh} {Z} minecraft:{top}")
            x = e + 1
    for (x, z), wy in water.items():
        a.append(f"fill {PCX + x} {S + h[(x, z)] + 1} {cz + z} {PCX + x} {S + wy} {cz + z} minecraft:water")
    top = lambda x, z: S + h[(x, z)]   # the ground block's y

    taken = [(0, 0, 9), (POND[0], POND[1], POND_R + 2)] + [(dx, dz, 4) for dx, dz in MOB_POINTS]
    def free(x, z, r):
        if abs(x) > PR - 2 - r or abs(z) > PR - 2 - r:
            return False
        return all((x - tx) ** 2 + (z - tz) ** 2 > (r + tr) ** 2 for tx, tz, tr in taken)
    def spot(r, tries=300):
        for _ in range(tries):
            x, z = rng.randint(-PR + 2, PR - 2), rng.randint(-PR + 2, PR - 2)
            if free(x, z, r):
                taken.append((x, z, r))
                return x, z
        return None
    # trees: oak and birch (a round crown, corners trimmed at random), spruce (a cone)
    for n in range(26):
        p = spot(2)
        if not p:
            continue
        x, z, g = PCX + p[0], cz + p[1], top(*p)
        wood = rng.choice(["oak", "oak", "oak", "birch", "birch", "spruce"])
        leaves = f"minecraft:{wood}_leaves[persistent=true]"
        if wood == "spruce":
            th = rng.randint(6, 8)
            for k, r in enumerate([2, 1, 2, 1, 1, 0]):
                y = g + th - 5 + k
                a.append(f"fill {x - r} {y} {z - r} {x + r} {y} {z + r} {leaves}")
                if r == 2:
                    a += [f"setblock {x + sx * 2} {y} {z + sz * 2} minecraft:air" for sx in (-1, 1) for sz in (-1, 1)]
            a.append(f"setblock {x} {g + th + 1} {z} {leaves}")
        else:
            th = rng.randint(4, 6) + (1 if wood == "birch" else 0)
            yt = g + th
            a += [f"fill {x - 2} {yt - 2} {z - 2} {x + 2} {yt - 1} {z + 2} {leaves}",
                  f"fill {x - 1} {yt} {z - 1} {x + 1} {yt + 1} {z + 1} {leaves}"]
            a += [f"setblock {x + sx * 2} {yt - 1} {z + sz * 2} minecraft:air" for sx in (-1, 1) for sz in (-1, 1) if rng.random() < 0.7]
            a += [f"setblock {x + sx} {yt + 1} {z + sz} minecraft:air" for sx in (-1, 1) for sz in (-1, 1)]
        a.append(f"fill {x} {g + 1} {z} {x} {g + th} {z} minecraft:{wood}_log")
    # bushes and mossy boulders
    for n in range(10):
        p = spot(1)
        if p:
            x, z, g = PCX + p[0], cz + p[1], top(*p)
            a += [f"setblock {x} {g + 1} {z} minecraft:oak_leaves[persistent=true]", f"setblock {x + rng.choice((-1, 1))} {g + 1} {z} minecraft:oak_leaves[persistent=true] keep"]
    for n in range(6):
        p = spot(2)
        if p:
            x, z, g = PCX + p[0], cz + p[1], top(*p)
            r = rng.randint(1, 2)
            a += [f"fill {x - r} {g + 1} {z - r + 1} {x + r} {g + 1} {z + r - 1} minecraft:{rng.choice(['mossy_cobblestone', 'cobblestone', 'andesite'])}",
                  f"fill {x - r + 1} {g + 2} {z - r + 1} {x + r - 1} {g + 2} {z + r - 1} minecraft:mossy_cobblestone",
                  f"setblock {x} {g + 1} {z} minecraft:{rng.choice(['coal_ore', 'iron_ore', 'copper_ore'])}"]
    # sugar cane at the pond's edge, pumpkins, then grass, ferns and flowers
    for (x, z) in sorted(sand):
        if (x, z) not in water and any((x + ox, z + oz) in water for ox, oz in ((1, 0), (-1, 0), (0, 1), (0, -1))) and rng.random() < 0.3:
            a.append(f"fill {PCX + x} {top(x, z) + 1} {cz + z} {PCX + x} {top(x, z) + rng.randint(1, 3)} {cz + z} minecraft:sugar_cane")
    for n in range(4):
        p = spot(0)
        if p:
            a.append(f"setblock {PCX + p[0]} {top(*p) + 1} {cz + p[1]} minecraft:pumpkin keep")
    plants = ["short_grass"] * 8 + ["fern"] * 2 + ["dandelion", "poppy", "cornflower", "oxeye_daisy", "azure_bluet"]
    for n in range(420):
        x, z = rng.randint(-PR, PR), rng.randint(-PR, PR)
        if (x, z) not in sand and x * x + z * z > 9:
            a.append(f"setblock {PCX + x} {top(x, z) + 1} {cz + z} minecraft:{rng.choice(plants)} keep")
    # mob windows: worn ground where they come in
    for dx, dz in MOB_POINTS:
        a.append(f"fill {PCX + dx - 1} {S} {cz + dz - 1} {PCX + dx + 1} {S} {cz + dz + 1} minecraft:coarse_dirt")
    # the core on an old mossy stone pad
    a += [f"fill {PCX - 1} {S} {cz - 1} {PCX + 1} {S} {cz + 1} minecraft:mossy_stone_bricks",
          f"setblock {PCX} {S} {cz} minecraft:chiseled_stone_bricks", f"setblock {PCX} {S + 1} {cz} minecraft:beacon"]
    a += [f"setblock {PCX + ox} {S} {cz + oz} minecraft:cracked_stone_bricks" for ox, oz in ((1, 1), (-1, -1))]
    # the Arsenal, south of the core, facing it
    body = b.npc("pvp.shopnpc", (PCX + 0.5, S + 1, cz + 6.5), "☣ Arsenal ☣", "green", "sniper", 180, hand="crossbow", chest="netherite_chestplate")
    a += [f"kill @e[tag=pvp.shopnpc,{box}]"] + body[1:]
    return a


def build(b):
    """Functions for the Core Defense map; returns the hooks build.py puts into the Outbreak functions."""
    fn, wj, tj, NS = b.fn, b.wj, b.tj, b.NS
    P = f"{NS}:pve"
    PCX, AY = b.PCX, b.AY
    cx, cy, cz = PCX + 0.5, SURF + 1, CORE_Z + 0.5   # the core block's centre (bottom)
    core_at = f"{PCX} {SURF + 1} {CORE_Z}"
    box = b.box(PCX, CORE_Z, b.PR, BOX_Y0, BOX_DY)
    PR = b.PR
    W1, W2, Z1, Z2 = PCX - PR - 1, PCX + PR + 1, CORE_Z - PR - 1, CORE_Z + PR + 1
    on = f"if score #map pve matches {CORE_ID}"

    # blocks mobs walk through or must never break
    wj(f"data/{NS}/tags/block/core_pass.json", {"values": [
        "#minecraft:replaceable", "#minecraft:small_flowers", "#minecraft:saplings", "minecraft:bedrock", "minecraft:barrier",
        "minecraft:beacon", "minecraft:light", "minecraft:torch", "minecraft:wall_torch", "minecraft:structure_void"]})
    wj(f"data/{NS}/tags/block/core_wallgap.json", {"values": ["#minecraft:air", "minecraft:water"]})
    wj(f"data/{NS}/predicate/half.json", {"condition": "minecraft:random_chance", "chance": 0.5})

    fn("pve/core_reset", [f"function {NS}:admin/build_pve_core"])
    fn("pve/core_start", [
        f"scoreboard players set #core pve {CORE_HP}", "tag @a remove pve.cw",
        f"scoreboard players set #corex pve {PCX}", f"scoreboard players set #corey pve {SURF + 1}", f"scoreboard players set #corez pve {CORE_Z}",
        f"bossbar set pvp:core max {CORE_HP}", f"bossbar set pvp:core value {CORE_HP}", "bossbar set pvp:core color blue",
        "bossbar set pvp:core visible true",
        # the map is loaded by the run's forceload a few ticks later; rebuild it then
        f"schedule function {P}/core_reset 5t replace",
    ])
    fn("pve/core_enter", [   # as a player entering the run: survival, plus building gear
        "gamemode survival @s", *[f"give @s minecraft:{it}" for it in START_ITEMS],
        "tellraw @s " + tj([{"text": "⚡ Core Defense: ", "color": "aqua", "bold": True},
                            {"text": "keep the beacon in the middle alive. Mine, chop, craft and build walls; the mobs dig through "
                                     "and build up, and you respawn as long as the core stands.", "color": "gray", "bold": False}]),
    ])
    fn("pve/core_tick", [   # every tick in a wave: mobs act every 10 ticks
        "scoreboard players add #ctk pve 1",
        "execute if score #ctk pve matches 10.. as @e[tag=pve.mob] at @s run function " + f"{P}/core_mob",
        "execute if score #ctk pve matches 10.. run scoreboard players set #ctk pve 0",
    ])
    fn("pve/core_mob", [   # as a mob, at it
        f"execute unless entity @s[tag=pve.seek] run function {P}/core_seek",
        f"execute positioned {cx} {cy} {cz} if entity @s[distance=..{CORE_REACH}] run return 0",
        f"execute if items entity @s weapon.mainhand minecraft:cobblestone if predicate {NS}:half run function {P}/core_build",
        # only a mob that's stuck digs: one that hasn't beaten its closest approach to the core (pve.cd, squared distance
        # in tenths of a block) by more than 1/20 (about 0.1 blocks at 4 away, 0.6 at 25). Jittering or sliding along a
        # wall it can't pass doesn't count as progress.
        f"execute store result score #dx pve run data get entity @s Pos[0] 10", f"scoreboard players remove #dx pve {round(cx * 10)}",
        f"execute store result score #dz pve run data get entity @s Pos[2] 10", f"scoreboard players remove #dz pve {round(cz * 10)}",
        "scoreboard players operation #dx pve *= #dx pve", "scoreboard players operation #dz pve *= #dz pve",
        "scoreboard players operation #dx pve += #dz pve",
        "scoreboard players add @s pve.cd 0",
        "execute if score @s pve.cd matches 0 run scoreboard players operation @s pve.cd = #dx pve",
        "scoreboard players operation #t pve = @s pve.cd", "scoreboard players operation #t2 pve = @s pve.cd",
        "scoreboard players operation #t2 pve /= #20 pve", "scoreboard players operation #t pve -= #t2 pve",
        "execute if score #dx pve < #t pve run scoreboard players operation @s pve.cd = #dx pve",
        "execute if score #dx pve < #t pve run return run scoreboard players set @s pve.dig 0",
        f"execute if entity @s[tag=pve.boss] run return run function {P}/core_bossdig",
        # below the core (in a trench): dig a staircase up towards it instead of a tunnel under it
        "execute store result score #my pve run data get entity @s Pos[1] 10",
        f"execute if score #my pve matches ..{round((cy - 0.5) * 10)} run return run function {P}/core_up",
        f"execute facing {cx} ~ {cz} positioned ^ ^1 ^1.0 unless block ~ ~ ~ #{NS}:core_pass run return run function {P}/core_dig",
        f"execute facing {cx} ~ {cz} positioned ^ ^ ^1.0 unless block ~ ~ ~ #{NS}:core_pass run return run function {P}/core_dig",
        "scoreboard players set @s pve.dig 0",
    ])
    fn("pve/core_up", [   # as a stuck mob below the core: clear head height and the block above it ahead (the block at
        # its feet ahead stays as a step), then the block over its own head if that's what stops the jump
        f"execute facing {cx} ~ {cz} positioned ^ ^1 ^1.0 unless block ~ ~ ~ #{NS}:core_pass run return run function {P}/core_dig",
        f"execute facing {cx} ~ {cz} positioned ^ ^2 ^1.0 unless block ~ ~ ~ #{NS}:core_pass run return run function {P}/core_dig",
        f"execute positioned ~ ~2 ~ unless block ~ ~ ~ #{NS}:core_pass run return run function {P}/core_dig",
        "scoreboard players set @s pve.dig 0",
    ])
    fn("pve/core_seek", ["tag @s add pve.seek", f"attribute @s minecraft:follow_range base set {SEEK_RANGE}"])
    fn("pve/core_dig", [   # as the mob, positioned in the block it's breaking
        "scoreboard players add @s pve.dig 1",
        "execute if items entity @s weapon.mainhand #minecraft:axes run scoreboard players add @s pve.dig 1",
        "particle minecraft:crit ~ ~0.5 ~ 0.3 0.3 0.3 0.1 4",
        "playsound minecraft:entity.zombie.attack_wooden_door hostile @a[distance=..20] ~ ~ ~ 0.4 1.3",
        f"execute if block ~ ~ ~ #minecraft:mineable/pickaxe if score @s pve.dig matches ..{DIG_HARD - 1} run return 0",
        f"execute if score @s pve.dig matches ..{DIG - 1} run return 0",
        "setblock ~ ~ ~ minecraft:air destroy", "scoreboard players set @s pve.dig 0",
    ])
    boss_cells = [(x, y) for y in range(4) for x in (-1, 0, 1)]
    fn("pve/core_bossdig", [   # the Abomination (scale 2) needs a 3-wide, 4-high hole
        "scoreboard players add @s pve.dig 1",
        f"execute facing {cx} ~ {cz} positioned ^ ^1 ^1.6 run particle minecraft:crit ~ ~ ~ 0.8 0.8 0.8 0.1 8",
        f"execute if score @s pve.dig matches ..{DIG - 1} run return 0",
        *[f"execute facing {cx} ~ {cz} positioned ^{x} ^{y} ^1.6 unless block ~ ~ ~ #{NS}:core_pass run setblock ~ ~ ~ minecraft:air destroy"
          for x, y in boss_cells],
        "scoreboard players set @s pve.dig 0",
    ])
    fn("pve/core_build", [   # a Builder: bridge a drop (2+ deep) towards the core; pillar up under a player standing high nearby
        f"execute unless block ~ ~-0.5 ~ #minecraft:air facing {cx} ~ {cz} positioned ^ ^-1 ^1.0 if block ~ ~ ~ #minecraft:air if block ~ ~-1 ~ #minecraft:air "
        "run setblock ~ ~ ~ minecraft:cobblestone",
        f"execute unless block ~ ~-0.5 ~ #minecraft:air if block ~ ~2 ~ #minecraft:air positioned ~-3 ~3 ~-3 "
        f"if entity @a[tag=pve.in,gamemode=survival,dx=6,dy=16,dz=6] positioned ~3 ~-3 ~3 run function {P}/core_pillar",
    ])
    fn("pve/core_pillar", ["tp @s ~ ~1.05 ~", "setblock ~ ~ ~ minecraft:cobblestone keep",
                           "playsound minecraft:block.stone.place hostile @a[distance=..16] ~ ~ ~ 0.6 1"])
    fn("pve/core_sec", [   # every second of a run on this map
        # mobs at the core wear it down
        f"execute positioned {cx} {cy} {cz} as @e[tag=pve.mob,distance=..{CORE_REACH}] run function {P}/core_hit",
        "execute store result bossbar pvp:core value run scoreboard players get #core pve",
        "bossbar set pvp:core players @a[tag=pve.in]",
        "execute if score #core pve matches ..30 run bossbar set pvp:core color red",
        "execute if score #core pve matches 31.. run bossbar set pvp:core color blue",
        "execute if score #calert pve matches 1.. run scoreboard players remove #calert pve 1",
        # a player who breaks the core gets it put back (and the dropped beacon removed)
        f"execute if score #core pve matches 1.. unless block {core_at} minecraft:beacon run setblock {core_at} minecraft:beacon",
        f"execute as @e[type=minecraft:item,{box}] if items entity @s contents minecraft:beacon run kill @s",
        # respawn timers; dead players watch from above the core
        f"execute as @a[tag=pve.cw] run function {P}/core_wait",
        f"execute as @a[tag=pve.cw] unless entity @s[{box}] run tp @s {cx} {SURF + 12} {cz}",
        # the wall: Mining Fatigue V right next to it (the concrete can't really be broken), and any gap is patched
        *[f"effect give @a[tag=pve.in,{sel}] minecraft:mining_fatigue 2 4 true" for sel in (
            f"x={W1},y={BOX_Y0},z={Z1},dx=2,dy={BOX_DY},dz={Z2 - Z1}", f"x={W2 - 2},y={BOX_Y0},z={Z1},dx=2,dy={BOX_DY},dz={Z2 - Z1}",
            f"x={W1},y={BOX_Y0},z={Z1},dx={W2 - W1},dy={BOX_DY},dz=2", f"x={W1},y={BOX_Y0},z={Z2 - 2},dx={W2 - W1},dy={BOX_DY},dz=2")],
        *[f"fill {a1} {BOTTOM} {b1} {a2} {SURF + WALL_H} {b2} minecraft:black_concrete replace #{NS}:core_wallgap"
          for (a1, b1, a2, b2) in ((W1, Z1, W2, Z1), (W1, Z2, W2, Z2), (W1, Z1, W1, Z2), (W2, Z1, W2, Z2))],
        f"execute if score #core pve matches ..0 run function {P}/core_lost",
    ])
    fn("pve/core_hit", [   # as a mob at the core
        "scoreboard players remove #core pve 1", "execute if entity @s[tag=pve.boss] run scoreboard players remove #core pve 4",
        f"particle minecraft:electric_spark {cx} {cy + 0.5} {cz} 0.4 0.4 0.4 0.2 10",
        f"playsound minecraft:block.beacon.deactivate block @a[tag=pve.in] {cx} {cy} {cz} 0.5 1.6",
        "execute unless score #calert pve matches 1.. run tellraw @a[tag=pve.in] " + tj([
            {"text": "⚡ The core is under attack! (", "color": "red"}, {"score": {"name": "#core", "objective": "pve"}, "color": "white"},
            {"text": f"/{CORE_HP})", "color": "red"}]),
        "execute unless score #calert pve matches 1.. run scoreboard players set #calert pve 8",
    ])
    fn("pve/core_heal", [   # after a wave
        f"scoreboard players add #core pve {CORE_HEAL}",
        f"execute if score #core pve matches {CORE_HP + 1}.. run scoreboard players set #core pve {CORE_HP}",
        "execute store result bossbar pvp:core value run scoreboard players get #core pve",
        "tellraw @a[tag=pve.in] " + tj([{"text": f"⚡ The core recovers +{CORE_HEAL} (", "color": "aqua"},
                                       {"score": {"name": "#core", "objective": "pve"}, "color": "white"}, {"text": f"/{CORE_HP}).", "color": "aqua"}]),
    ])
    fn("pve/core_died", [   # as a player who just respawned: back after RESPAWN_S while the core stands
        "execute if score #core pve matches ..0 run return 0",
        "tag @s add pve.cw", f"scoreboard players set @s pve.rt {RESPAWN_S}", "gamemode spectator @s", *b.PERK_RESET,
        f"tp @s {cx} {SURF + 12} {cz} 0 90",
        "title @s title {\"text\":\"YOU DIED\",\"color\":\"dark_red\",\"bold\":true}",
        "title @s subtitle " + tj({"text": f"Back in {RESPAWN_S} s while the core stands", "color": "gray"}),
        "tellraw @a[tag=pve.in] " + tj([{"selector": "@s", "color": "red"}, {"text": f" died (back in {RESPAWN_S} s).", "color": "gray"}]),
    ])
    fn("pve/core_wait", [
        "scoreboard players remove @s pve.rt 1",
        "title @s actionbar " + tj([{"text": "Respawning in ", "color": "gray"}, {"score": {"name": "@s", "objective": "pve.rt"}, "color": "white"},
                                    {"text": " s", "color": "gray"}]),
        f"execute if score @s pve.rt matches ..0 run function {P}/core_back",
    ])
    fn("pve/core_back", ["tag @s remove pve.cw", "gamemode survival @s", f"function {P}/tp_spawn",
                         "effect give @s minecraft:resistance 3 4 true", b.say("@s", "You're back. Defend the core!", "green")])
    fn("pve/core_lost", [
        f"setblock {core_at} minecraft:air destroy",
        f"particle minecraft:explosion_emitter {cx} {cy} {cz} 1 1 1 0 3",
        f"execute as @a[tag=pve.in] at @s run playsound minecraft:entity.generic.explode player @s ~ ~ ~ 1 0.6",
        "title @a[tag=pve.in] title {\"text\":\"CORE DESTROYED\",\"color\":\"dark_red\",\"bold\":true}",
        "tellraw @a[tag=pve.in] " + tj([{"text": "⚡ The core was destroyed on wave ", "color": "red"},
                                       {"score": {"name": "#wave", "objective": "pve"}, "color": "white", "bold": True}, {"text": ".", "color": "red"}]),
        f"function {P}/game_over",
    ])

    return {
        "objectives": ["pve.dig dummy", "pve.cd dummy", "pve.rt dummy"],
        "load": ['bossbar add pvp:core {"text":"⚡ Core","color":"aqua"}', "bossbar set pvp:core visible false"],
        "tick": f"execute {on} if score #state pve matches 2 run function {P}/core_tick",
        "second": f"execute {on} if score #state pve matches 2..3 run function {P}/core_sec",
        "start": f"execute {on} run function {P}/core_start",
        "enter": f"execute {on} run function {P}/core_enter",
        "died": f"execute {on} run return run function {P}/core_died",
        "wave_end": f"execute {on} run function {P}/core_heal",
        "game_over": [f"execute {on} run function {P}/core_reset", "bossbar set pvp:core visible false", "tag @a remove pve.cw"],
        "reset": ["tag @s remove pve.cw"],
        "box": box,
    }
