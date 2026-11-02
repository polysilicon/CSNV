"""Core Defense (imported by build.py): an Outbreak map (id CORE_ID) where the team guards a core instead of just surviving.

- A beacon (the core) sits on a small clearing in real terrain: a 65 x 65 slice of a normally generated world (the
  pvp:wild dimension) cloned in on every reset, with BELOW blocks of real underground under the core for trenches.
  The border is black concrete up to WALL_TOP (about 32 above the core) with barrier above it to the build limit and a
  barrier shell behind it; Mining Fatigue V right by it and patching during a run keep it whole. Players play in survival: they can mine, chop, craft, dig trenches and build walls around it. Everyone starts with stone tools,
  planks, cobblestone, a crafting table, a furnace and torches on top of their kit; the Arsenal (out in the south-east corner)
  works as on the other maps.
- Mobs head for the core: they're tagged pve.seek and the PvP mod (spawnmod CoreSeek) walks any of them that isn't
  after a player to the core (#corex/#corey/#corez pve). Their follow range is cut to SEEK_RANGE, so only players
  close by pull them away. Zombies, husks, zombie villagers and vindicators only (melee mobs that can dig).
- Mobs break through: a mob that stands still with a block between it and the core chews through it (head height
  first, then feet): 3 s for most blocks, 5 s for stone-type blocks, twice as fast for Breakers (axe in hand). The
  Warlord (this map's boss) digs about four times as fast. A mob stuck below the core (in a trench) digs a staircase up. Builders (cobblestone in hand) bridge gaps on the way to the core
  and pillar up under a player standing on something high nearby.
- Every mob within ~2.5 blocks of the core takes 1 core HP a second (the Warlord 5). The core has CORE_HP and gets
  CORE_HEAL back after every wave (boss bar "Core"). A player who breaks it gets it put straight back.
- Dying isn't "down" here: while the core stands you're back at a spawn after RESPAWN_S seconds, with your inventory
  (keep_inventory is on). When the core is destroyed the run is over.
- The map is rebuilt (pve/core_reset) when a run starts and when it ends, so every run starts on a fresh meadow.
"""
import random

CORE_ID = 7
CORE_Z = 900
CORE_HP = 100
CORE_HEAL = 20          # core HP back after each wave
RESPAWN_S = 5
FIRST_BREAK_S = 90      # before wave 1: time to build defences
BREAK_S = 30            # between waves
DIG = 6                 # checks (every 10 ticks) to break a block: 3 s
DIG_HARD = 10           # stone-type blocks (#minecraft:mineable/pickaxe): 5 s
DIG_TOUGH = 24          # obsidian, iron blocks (#pvp:core_tough): 12 s
CORE_REACH = 2.8        # mobs this close to the core's centre damage it
BOTTOM = -64            # the world's floor: bedrock (unbreakable)
# The terrain is real: a slice of a normally generated world (dimension pvp:wild, the world's seed) centred on
# (SRC_X, SRC_Z) is cloned in on every reset. The slice is SLICE_H high and starts BELOW blocks under the ground at its
# centre, so the core's ground lands on SURF and there are BELOW blocks of real underground (stone, caves, ore) to dig.
WILD = "pvp:wild"
SRC_X, SRC_Z = -216, 72   # a forest: hills 62-71, no water or lava (picked with admin/wildprobe)
SLICE_H = 46
BELOW = 19
SURF = BOTTOM + 1 + BELOW   # -44: the ground under the core
WALL_TOP = BOTTOM + SLICE_H + 6   # black concrete up to here (-12, about 32 above the core); barrier above, to the build limit
ARSENAL = (22, 22)      # the Arsenal NPC, from the core (between the mob windows at (30, 16) and (16, 30))
BOX_Y0 = BOTTOM - 1     # the map's selector box (build.PVE_BOXES uses it too)
BOX_DY = WALL_TOP + 20 - BOX_Y0
SEEK_RANGE = 20         # core mobs only go after players this close (follow range); otherwise they head for the core
B_EXTRA = ',CustomName:{text:"Builder",color:"gold"},equipment:{mainhand:{id:"minecraft:cobblestone",count:1}},drop_chances:{mainhand:0.0f}'
K_EXTRA = ',CustomName:{text:"Breaker",color:"red"},equipment:{mainhand:{id:"minecraft:iron_axe",count:1}},drop_chances:{mainhand:0.0f}'
# this map's whole roster (rolls up to 100, so the normal pool, which has mobs that ignore villagers, is never used)
POOL = [(1, 18, "zombie", B_EXTRA), (1, 50, "zombie", ""), (2, 64, "husk", ""), (3, 76, "zombie_villager", ""),
        (4, 86, "vindicator", K_EXTRA), (6, 93, "zombie", K_EXTRA), (1, 100, "zombie", "")]
# the Arsenal's Base Defense page (pve.buy 41..): id, name, colour, icon, cost, lore, commands
CORE_SHOP = [
    (41, "Oak Planks", "gold", "oak_planks", 150, "64 planks: quick walls", ["give @s minecraft:oak_planks 64"]),
    (42, "Cobblestone", "gray", "cobblestone", 250, "64 cobblestone: slower to dig through", ["give @s minecraft:cobblestone 64"]),
    (43, "Stone Bricks", "gray", "stone_bricks", 400, "64 stone bricks", ["give @s minecraft:stone_bricks 64"]),
    (44, "Obsidian", "dark_purple", "obsidian", 1500, "16 obsidian: mobs need 12 s per block", ["give @s minecraft:obsidian 16"]),
    (45, "Iron Bars", "white", "iron_bars", 500, "32 iron bars: see (and shoot) through", ["give @s minecraft:iron_bars 32"]),
    (46, "Fences", "gold", "oak_fence", 350, "32 fences + 4 gates: too high to jump", ["give @s minecraft:oak_fence 32", "give @s minecraft:oak_fence_gate 4"]),
    (47, "Water Bucket", "aqua", "water_bucket", 300, "Push mobs back, put out fires", ["give @s minecraft:water_bucket"]),
    (48, "Lava Bucket", "red", "lava_bucket", 800, "A moat that burns (Builders cover it)", ["give @s minecraft:lava_bucket"]),
    (49, "Cobwebs", "white", "cobweb", 600, "8 cobwebs: slow mobs to a crawl", ["give @s minecraft:cobweb 8"]),
    (50, "Magma Blocks", "gold", "magma_block", 450, "16 magma blocks: burn anything standing on them", ["give @s minecraft:magma_block 16"]),
    (51, "Scaffolding", "yellow", "scaffolding", 250, "32 scaffolding: build up fast", ["give @s minecraft:scaffolding 32"]),
    (52, "Ladders & Torches", "yellow", "ladder", 150, "16 ladders + 32 torches", ["give @s minecraft:ladder 16", "give @s minecraft:torch 32"]),
    (53, "Repair Core", "aqua", "beacon", 1000, "+25 core HP", ["function pvp:pve/core_repair"]),
]
SHOP_SLOTS = [10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 23, 24, 25]
# the Warlord: this map's boss (every 5th wave) instead of the Abomination, which got stuck in the trees.
# 2026-11-02: nerfed (was 160 health, full netherite, no knockback): 100 health, netherite helmet + chainmail, 60% knockback resistance
WARLORD = ('{Tags:["pve.mob","pve.boss","pve.new"],PersistenceRequired:1b,CanPickUpLoot:0b,DeathLootTable:"minecraft:empty",IsBaby:0b,'
           'CustomName:{text:"Warlord",color:"dark_red",bold:true},CustomNameVisible:1b,'
           'equipment:{mainhand:{id:"minecraft:netherite_axe",count:1},head:{id:"minecraft:netherite_helmet",count:1},'
           'chest:{id:"minecraft:chainmail_chestplate",count:1},legs:{id:"minecraft:chainmail_leggings",count:1},feet:{id:"minecraft:chainmail_boots",count:1}},'
           'drop_chances:{mainhand:0.0f,head:0.0f,chest:0.0f,legs:0.0f,feet:0.0f},'
           'attributes:[{id:"minecraft:max_health",base:100d},{id:"minecraft:attack_damage",base:8d},{id:"minecraft:knockback_resistance",base:0.6d},'
           '{id:"minecraft:movement_speed",base:0.25d},{id:"minecraft:follow_range",base:20d}]}')
RALLY_S = 15            # the Warlord calls in two Builders this often
START_ITEMS = ["stone_pickaxe", "stone_axe", "stone_shovel", "oak_planks 32", "cobblestone 32", "crafting_table", "furnace",
               "torch 8"]
LORE = ["Guard the core in a patch of wild world", "Mine, chop, craft, dig trenches, build walls", "Mobs dig through walls and build up",
        "Respawn while the core stands", "Mobs: zombies, husks, Builders, Breakers"]


def map_cmds(b, cz):
    """admin/build_pve_core: (re)build the map. The work is in pve/core_reset (it has to wait for chunks to load)."""
    return [f"function {b.NS}:pve/core_reset"]


def post_cmds(b, cz):
    """After the terrain is cloned in: the bedrock floor, the walls, a clearing with the core on its pad, the Arsenal."""
    PCX, PR = b.PCX, b.PR
    x1, x2, z1, z2 = PCX - PR, PCX + PR, cz - PR, cz + PR
    W1, W2, Z1, Z2 = x1 - 1, x2 + 1, z1 - 1, z2 + 1
    box = b.box(PCX, cz, PR, BOX_Y0, BOX_DY)
    S, top = SURF, BOTTOM + SLICE_H
    a = [f"kill @e[type=minecraft:item,{box}]", f"kill @e[tag=pve.anchor,{box}]",
         f"fill {x1} {BOTTOM} {z1} {x2} {BOTTOM} {z2} minecraft:bedrock"]
    a += [f"fill {x1} {k} {z1} {x2} {min(k + 6, WALL_TOP + 8)} {z2} minecraft:air" for k in range(top, WALL_TOP + 9, 7)]   # above the slice
    # walls: black concrete from bedrock to WALL_TOP, barrier above it to the build limit, and a barrier shell all round
    # (so even a broken wall block leads nowhere); Mining Fatigue near the wall and patching during a run (core_sec)
    for (a1, b1, a2, b2) in ((W1, Z1, W2, Z1), (W1, Z2, W2, Z2), (W1, Z1, W1, Z2), (W2, Z1, W2, Z2)):
        a += [f"fill {a1} {BOTTOM} {b1} {a2} {WALL_TOP} {b2} minecraft:black_concrete",
              f"fill {a1} {WALL_TOP + 1} {b1} {a2} 319 {b2} minecraft:barrier"]
    for (a1, b1, a2, b2) in ((W1 - 1, Z1 - 1, W2 + 1, Z1 - 1), (W1 - 1, Z2 + 1, W2 + 1, Z2 + 1), (W1 - 1, Z1 - 1, W1 - 1, Z2 + 1), (W2 + 1, Z1 - 1, W2 + 1, Z2 + 1)):
        a.append(f"fill {a1} {BOTTOM} {b1} {a2} 319 {b2} minecraft:barrier")
    # a clearing round the core (no trees where players spawn), from well below the core's ground, since the land
    # around it can be lower; then the core on an old mossy stone pad
    for t in ("#minecraft:logs", "#minecraft:leaves"):
        a.append(f"fill {PCX - 8} {S - 12} {cz - 8} {PCX + 8} {WALL_TOP} {cz + 8} minecraft:air replace {t}")
    a += [f"fill {PCX - 1} {S + 1} {cz - 1} {PCX + 1} {S + 3} {cz + 1} minecraft:air",
          f"fill {PCX - 1} {S} {cz - 1} {PCX + 1} {S} {cz + 1} minecraft:mossy_stone_bricks",
          f"setblock {PCX} {S} {cz} minecraft:chiseled_stone_bricks", f"setblock {PCX} {S + 1} {cz} minecraft:beacon"]
    a += [f"setblock {PCX + ox} {S} {cz + oz} minecraft:cracked_stone_bricks" for ox, oz in ((1, 1), (-1, -1))]
    # no trees on the mob windows (mobs and the Warlord come in there, on the ground)
    for dx, dz in b.MOB_POINTS:
        for t in ("#minecraft:logs", "#minecraft:leaves"):
            a.append(f"fill {PCX + dx - 2} {S - 10} {cz + dz - 2} {PCX + dx + 2} {WALL_TOP} {cz + dz + 2} minecraft:air replace {t}")
    # the Arsenal: out in the south-east, well away from the core (and players' defences), facing it; trees cleared there
    ax, az = PCX + ARSENAL[0], cz + ARSENAL[1]
    for t in ("#minecraft:logs", "#minecraft:leaves"):
        a.append(f"fill {ax - 2} {BOTTOM + 1} {az - 2} {ax + 2} {WALL_TOP} {az + 2} minecraft:air replace {t}")
    body = b.npc("pvp.shopnpc", ("~", "~", "~"), "☣ Arsenal ☣", "green", "sniper", 135, hand="crossbow", chest="netherite_chestplate")
    a += [f"kill @e[tag=pvp.shopnpc,{box}]"] + [f"execute positioned {ax + 0.5} 0 {az + 0.5} positioned over motion_blocking_no_leaves run {c}" for c in body[1:]]
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
    wj(f"data/{NS}/tags/block/core_tough.json", {"values": ["minecraft:obsidian", "minecraft:crying_obsidian", "minecraft:iron_block"]})
    wj(f"data/{NS}/tags/block/core_liquid.json", {"values": ["minecraft:water", "minecraft:lava"]})
    wj(f"data/{NS}/predicate/half.json", {"condition": "minecraft:random_chance", "chance": 0.5})

    wj(f"data/{NS}/dimension/wild.json", {"type": "minecraft:overworld", "generator": {
        "type": "minecraft:noise", "settings": "minecraft:overworld",
        "biome_source": {"type": "minecraft:multi_noise", "preset": "minecraft:overworld"}}})
    src = f"{SRC_X - PR} {{}} {SRC_Z - PR} {SRC_X + PR} {{}} {SRC_Z + PR}"
    fn("pve/core_reset", [   # load the source and the map, then clone once they're in
        f"execute in {WILD} run forceload add {SRC_X - PR - 1} {SRC_Z - PR - 1} {SRC_X + PR + 1} {SRC_Z + PR + 1}",
        f"forceload add {W1 - 1} {Z1 - 1} {W2 + 1} {Z2 + 1}",
        f"schedule function {P}/core_paste 20t replace",
    ])
    paste = [   # the ground at the source's centre (#sy, the first air above it) sets the slice
        "scoreboard players set #sy pve -999",
        f"execute in {WILD} positioned {SRC_X} 0 {SRC_Z} positioned over motion_blocking_no_leaves run summon minecraft:marker ~ ~ ~ {{Tags:[\"pve.probe\"]}}",
        f"execute in {WILD} store result score #sy pve run data get entity @e[type=minecraft:marker,tag=pve.probe,limit=1] Pos[1]",
        f"execute in {WILD} run kill @e[type=minecraft:marker,tag=pve.probe]",
        f"execute unless score #sy pve matches -60..300 run tellraw @a[tag=pvp.tester] " + tj({"text": f"Core Defense: couldn't read the terrain in {WILD}.", "color": "red"}),
        f"execute unless score #sy pve matches -60..300 run return run function {P}/core_unload",
        f"scoreboard players remove #sy pve {BELOW + 1}",
    ]
    for k in range(0, SLICE_H, 7):
        n = min(6, SLICE_H - 1 - k)
        paste += [f"execute store result storage pvp:core c.a{k} int 1 run scoreboard players get #sy pve", f"scoreboard players add #sy pve {n}",
                  f"execute store result storage pvp:core c.b{k} int 1 run scoreboard players get #sy pve", "scoreboard players add #sy pve 1"]
    paste += [f"function {P}/core_clone with storage pvp:core c", *post_cmds(b, CORE_Z),
              f"execute if score #state pve matches 2..3 as @a[tag=pve.in,tag=!pve.cw] run function {P}/tp_spawn",
              f"function {P}/core_unload"]
    fn("pve/core_paste", paste)
    fn("pve/core_unload", [f"execute in {WILD} run forceload remove {SRC_X - PR - 1} {SRC_Z - PR - 1} {SRC_X + PR + 1} {SRC_Z + PR + 1}",
                           f"execute if score #state pve matches 0 run forceload remove {W1 - 1} {Z1 - 1} {W2 + 1} {Z2 + 1}"])
    fn("pve/core_clone", [f"$clone from {WILD} " + src.format(f"$(a{k})", f"$(b{k})") + f" to minecraft:overworld {PCX - PR} {BOTTOM + 1 + k} {CORE_Z - PR}"
                          for k in range(0, SLICE_H, 7)])
    # picking a source spot (admin): "execute in pvp:wild run forceload add" the area, wait for it to generate, then
    # "function pvp:admin/wildprobe {x:.., z:..}" and "data get storage pvp:probe h": ground height (first air) on a
    # 7 x 7 grid 10 apart, +1000 where the surface is water, +2000 on a tree (logs), +5000 on lava
    probe = ["data remove storage pvp:probe h"]
    for i, dx in enumerate(range(-30, 31, 10)):
        for j, dz in enumerate(range(-30, 31, 10)):
            at = f"$execute in {WILD} positioned $(x) 0 $(z) positioned ~{dx} 0 ~{dz} positioned over"
            k = f"r{j}c{i}"
            probe += [f"{at} motion_blocking_no_leaves run summon minecraft:marker ~ ~ ~ {{Tags:[\"pr\"]}}",
                      f"execute in {WILD} store result score #p pve run data get entity @e[type=minecraft:marker,tag=pr,limit=1] Pos[1]",
                      f"execute in {WILD} run kill @e[type=minecraft:marker,tag=pr]",
                      f"{at} world_surface if block ~ ~-1 ~ water run scoreboard players add #p pve 1000",
                      f"{at} world_surface if block ~ ~-1 ~ #minecraft:logs run scoreboard players add #p pve 2000",
                      f"{at} world_surface if block ~ ~-1 ~ lava run scoreboard players add #p pve 5000",
                      f"execute store result storage pvp:probe h.{k} int 1 run scoreboard players get #p pve"]
    fn("admin/wildprobe", probe)
    # the Arsenal's Base Defense page
    buy = []
    for (sid, name, color, ic, cost, lore, cmds) in CORE_SHOP:
        buy.append(f"execute if score #n pve matches {sid} run return run function {P}/core_shop/{sid}")
        fn(f"pve/core_shop/{sid}", [f"execute if score @s pve.pts matches ..{cost - 1} run return run {b.afford(name, cost)}",
                                    f"scoreboard players remove @s pve.pts {cost}", *cmds,
                                    "tellraw @s " + tj([{"text": "Bought ", "color": "green"}, {"text": name, "color": color}]),
                                    "playsound minecraft:entity.villager.yes neutral @s ~ ~ ~ 1 0.8"])
    fn("pve/core_buy", [f"execute unless score #map pve matches {CORE_ID} run return run " + b.say("@s", "That's only sold in Core Defense.", "red"), *buy])
    fn("pve/core_repair", [f"scoreboard players add #core pve 25",
                           f"execute if score #core pve matches {CORE_HP + 1}.. run scoreboard players set #core pve {CORE_HP}",
                           "execute store result bossbar pvp:core value run scoreboard players get #core pve",
                           f"particle minecraft:happy_villager {cx} {cy + 0.5} {cz} 0.6 0.6 0.6 0 20",
                           "tellraw @a[tag=pve.in] " + tj([{"selector": "@s", "color": "yellow"}, {"text": " repaired the core (", "color": "aqua"},
                                                           {"score": {"name": "#core", "objective": "pve"}, "color": "white"}, {"text": f"/{CORE_HP}).", "color": "aqua"}])])
    shop_menu = {"title": {"text": "⚡ Arsenal: Base Defense (points)", "color": "dark_aqua"}, "rows": 4, "fill": b.PANE, "items":
                 [{"slot": sl, "item": b.icon(i[3], f"{i[1]} · {i[4]}", i[2], [i[5]], False), "cmd": f"trigger pve.buy set {i[0]}"}
                  for sl, i in zip(SHOP_SLOTS, CORE_SHOP)]
                 + [{"slot": 4, "item": b.icon("beacon", "Base Defense", "aqua", ["Blocks and supplies to hold the core", "Paid with Outbreak points"]), "cmd": ""},
                    {"slot": 31, "item": b.icon("iron_sword", "Weapons, perks & armor →", "green", ["The usual Arsenal"], False), "cmd": "pvpmenu pve_shop"}]}
    fn("pve/shop_open", [f"execute if score #map pve matches {CORE_ID} run return run pvpmenu core_shop", "pvpmenu pve_shop"])
    # the Warlord: at a random mob window (cleared of trees), on the ground
    fn("pve/core_boss", [
        'bossbar set pvp:boss name {"text":"Warlord","color":"dark_red"}', "bossbar set pvp:boss color red",
        "execute store result score #r pve run random value 1..4",
        *[f"execute if score #r pve matches {n} run data modify storage pvp:pve m merge value {{x:{PCX + dx + 0.5},z:{CORE_Z + dz + 0.5}}}"
          for n, (dx, dz) in enumerate([(30, 0), (-30, 0), (0, 30), (0, -30)], 1)],
        f"function {P}/core_spawny with storage pvp:pve m",
        f"function {P}/core_boss_summon with storage pvp:pve m",
        f"execute as @e[tag=pve.new] run function {P}/scale with storage pvp:pve s",
        "execute store result bossbar pvp:boss max run data get entity @e[tag=pve.boss,limit=1] Health",
        "bossbar set pvp:boss players @a[tag=pve.in]", "bossbar set pvp:boss visible true", "scoreboard players set #wr pve 0",
        "tellraw @a[tag=pve.in] " + tj({"text": "⚡ The Warlord has come for the core! He hacks through walls and calls in Builders.", "color": "dark_red", "bold": True}),
        "execute as @a[tag=pve.in] at @s run playsound minecraft:event.raid.horn player @s ~ ~ ~ 1 0.6",
    ])
    fn("pve/core_boss_summon", ["$summon minecraft:zombie $(x) $(y) $(z) " + WARLORD,
                                "$particle minecraft:large_smoke $(x) $(y) $(z) 0.5 1 0.5 0.02 40"])
    fn("pve/core_rally", [   # as the Warlord, at him
        *[f"summon minecraft:zombie ~{ox} ~ ~{oz} " + '{Tags:["pve.mob","pve.new"],PersistenceRequired:1b,CanPickUpLoot:0b,DeathLootTable:"minecraft:empty",IsBaby:0b' + B_EXTRA + "}"
          for ox, oz in ((1, 0), (-1, 0))],
        f"execute as @e[tag=pve.new] run function {P}/scale with storage pvp:pve s",
        "particle minecraft:large_smoke ~ ~1 ~ 0.8 0.5 0.8 0.02 20",
        "tellraw @a[tag=pve.in] " + tj({"text": "⚡ The Warlord calls in Builders!", "color": "red"}),
    ])
    # mobs and the boss come in on the ground at their spot (the terrain isn't flat)
    fn("pve/core_spawny", ["$execute positioned $(x) 0 $(z) positioned over motion_blocking_no_leaves run summon minecraft:marker ~ ~ ~ {Tags:[\"pve.probe\"]}",
                           "execute store result storage pvp:pve m.y int 1 run data get entity @e[type=minecraft:marker,tag=pve.probe,limit=1] Pos[1]",
                           "kill @e[type=minecraft:marker,tag=pve.probe]"])
    fn("pve/core_bossy", [f"execute positioned {PCX + 0.5} 0 {CORE_Z + 18.5} positioned over motion_blocking_no_leaves run summon minecraft:marker ~ ~ ~ {{Tags:[\"pve.probe\"]}}",
                          "execute store result storage pvp:pve map.by int 1 run data get entity @e[type=minecraft:marker,tag=pve.probe,limit=1] Pos[1]",
                          "kill @e[type=minecraft:marker,tag=pve.probe]"])
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
                            {"text": f"keep the beacon in the middle alive. You have {FIRST_BREAK_S} s before the first wave and {BREAK_S} s between waves. Mine, chop, craft and build walls; the mobs dig through "
                                     "and build up, and you respawn as long as the core stands. The Arsenal is out in the south-east corner.",
                             "color": "gray", "bold": False}]),
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
        "execute if entity @s[tag=pve.boss] run scoreboard players add @s pve.dig 2",
        "particle minecraft:crit ~ ~0.5 ~ 0.3 0.3 0.3 0.1 4",
        "playsound minecraft:entity.zombie.attack_wooden_door hostile @a[distance=..20] ~ ~ ~ 0.4 1.3",
        f"execute if block ~ ~ ~ #{NS}:core_tough if score @s pve.dig matches ..{DIG_TOUGH - 1} run return 0",
        f"execute if block ~ ~ ~ #minecraft:mineable/pickaxe if score @s pve.dig matches ..{DIG_HARD - 1} run return 0",
        f"execute if score @s pve.dig matches ..{DIG - 1} run return 0",
        "setblock ~ ~ ~ minecraft:air destroy", "scoreboard players set @s pve.dig 0",
    ])
    fn("pve/core_build", [   # a Builder: bridge a drop (2+ deep) towards the core; pillar up under a player standing high nearby
        f"execute unless block ~ ~-0.5 ~ #minecraft:air facing {cx} ~ {cz} positioned ^ ^-1 ^1.0 if block ~ ~ ~ #minecraft:air if block ~ ~-1 ~ #minecraft:air "
        "run setblock ~ ~ ~ minecraft:cobblestone",
        f"execute facing {cx} ~ {cz} positioned ^ ^-1 ^1.0 if block ~ ~ ~ #{NS}:core_liquid run setblock ~ ~ ~ minecraft:cobblestone",
        f"execute facing {cx} ~ {cz} positioned ^ ^ ^1.0 if block ~ ~ ~ #{NS}:core_liquid run setblock ~ ~ ~ minecraft:cobblestone",
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
        *[f"fill {a1} {BOTTOM} {b1} {a2} {WALL_TOP} {b2} minecraft:black_concrete replace #{NS}:core_wallgap"
          for (a1, b1, a2, b2) in ((W1, Z1, W2, Z1), (W1, Z2, W2, Z2), (W1, Z1, W1, Z2), (W2, Z1, W2, Z2))],
        "execute if entity @e[tag=pve.boss] run scoreboard players add #wr pve 1",
        f"execute if score #wr pve matches {RALLY_S}.. as @e[tag=pve.boss] at @s run function {P}/core_rally",
        f"execute if score #wr pve matches {RALLY_S}.. run scoreboard players set #wr pve 0",
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
        "boss": f"execute {on} run return run function {P}/core_boss",
        "buy": f"execute if score #n pve matches 41..60 run return run function {P}/core_buy",
        "shop_menu": shop_menu,
        "first_break": f"execute {on} run scoreboard players set #timer pve {FIRST_BREAK_S * 20}",
        "break": f"execute {on} run scoreboard players set #timer pve {BREAK_S * 20}",
        "spawn_y": f"execute {on} run function {P}/core_spawny with storage pvp:pve m",
        "boss_y": f"execute {on} run function {P}/core_bossy",
        "tp_spawn": lambda x, z, yaw: f"execute positioned {x} 0 {z} positioned over motion_blocking_no_leaves run tp @s ~ ~ ~ {yaw} 0",
        "game_over": [f"execute {on} run function {P}/core_reset", "bossbar set pvp:core visible false", "tag @a remove pve.cw"],
        "reset": ["tag @s remove pve.cw"],
        "box": box,
    }
