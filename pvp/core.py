"""Core Defense (imported by build.py): an Outbreak map (id CORE_ID) where the team guards a core instead of just surviving.

- A beacon (the core) sits in the middle of an open meadow with trees and rock outcrops (coal, iron and copper ore).
  Players play in survival: they can mine, chop, craft and build walls around it. Everyone starts with stone tools,
  planks, cobblestone, a crafting table, a furnace and torches on top of their kit; the Arsenal (just south of the core)
  works as on the other maps.
- Mobs head for the core: they're tagged pve.seek and the PvP mod (spawnmod CoreSeek) walks any of them that isn't
  after a player to the core (#corex/#corey/#corez pve). Their follow range is cut to SEEK_RANGE, so only players
  close by pull them away. Zombies, husks, zombie villagers and vindicators only (melee mobs that can dig).
- Mobs break through: a mob that stands still with a block between it and the core chews through it (head height
  first, then feet): 3 s for most blocks, 5 s for stone-type blocks, twice as fast for Breakers (axe in hand). The
  Abomination clears a 3-wide, 4-high hole at a time. Builders (cobblestone in hand) bridge gaps on the way to the core
  and pillar up under a player standing on something high nearby.
- Every mob within ~2.5 blocks of the core takes 1 core HP a second (the Abomination 5). The core has CORE_HP and gets
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
DIG = 6                 # checks (every 10 ticks) to break a block: 3 s
DIG_HARD = 10           # stone-type blocks (#minecraft:mineable/pickaxe): 5 s
CORE_REACH = 2.8        # mobs this close to the core's centre damage it
SEEK_RANGE = 20         # core mobs only go after players this close (follow range); otherwise they head for the core
B_EXTRA = ',CustomName:{text:"Builder",color:"gold"},equipment:{mainhand:{id:"minecraft:cobblestone",count:1}},drop_chances:{mainhand:0.0f}'
K_EXTRA = ',CustomName:{text:"Breaker",color:"red"},equipment:{mainhand:{id:"minecraft:iron_axe",count:1}},drop_chances:{mainhand:0.0f}'
# this map's whole roster (rolls up to 100, so the normal pool, which has mobs that ignore villagers, is never used)
POOL = [(1, 18, "zombie", B_EXTRA), (1, 50, "zombie", ""), (2, 64, "husk", ""), (3, 76, "zombie_villager", ""),
        (4, 86, "vindicator", K_EXTRA), (6, 93, "zombie", K_EXTRA), (1, 100, "zombie", "")]
START_ITEMS = ["stone_pickaxe", "stone_axe", "stone_shovel", "oak_planks 32", "cobblestone 32", "crafting_table", "furnace",
               "torch 8"]
LORE = ["Guard the core in the middle of a meadow", "Mine, chop, craft and build walls", "Mobs dig through walls and build up",
        "Respawn while the core stands", "Mobs: zombies, husks, Builders, Breakers"]


def map_cmds(b, cz):
    """(Re)build the Core Defense map: meadow, trees, ore rocks, the core, the Arsenal, unbreakable walls."""
    PCX, AY, PR = b.PCX, b.AY, b.PR
    x1, x2, z1, z2 = PCX - PR, PCX + PR, cz - PR, cz + PR
    W1, W2, Z1, Z2 = x1 - 1, x2 + 1, z1 - 1, z2 + 1
    box = b.box(PCX, cz, PR, AY - 4, 40)
    a = [f"kill @e[type=minecraft:item,{box}]", f"kill @e[tag=pve.anchor,{box}]"]   # (pve.anchor: an older version's villager)
    a += [f"fill {x1} {AY + 1 + k} {z1} {x2} {AY + min(k + 7, 30)} {z2} minecraft:air" for k in range(0, 30, 7)]
    a += [f"fill {x1} {AY - 3} {z1} {x2} {AY - 3} {z2} minecraft:bedrock",
          f"fill {x1} {AY - 2} {z1} {x2} {AY - 1} {z2} minecraft:dirt",
          f"fill {x1} {AY} {z1} {x2} {AY} {z2} minecraft:grass_block"]
    # the outer wall is bedrock all the way down (survival players can't dig out), barrier above as on the other maps
    for (a1, b1, a2, b2) in ((W1, Z1, W2, Z1), (W1, Z2, W2, Z2), (W1, Z1, W1, Z2), (W2, Z1, W2, Z2)):
        a += [f"fill {a1} {AY - 3} {b1} {a2} {AY + 5} {b2} minecraft:bedrock", f"fill {a1} {AY + 6} {b1} {a2} {AY + 30} {b2} minecraft:barrier"]
    a.append(f"fill {W1} {AY + 31} {Z1} {W2} {AY + 31} {Z2} minecraft:barrier")

    rng = random.Random(CORE_ID)
    taken = [(0, 0, 10)] + [(dx, dz, 4) for dx, dz in b.MOB_POINTS]   # (x, z, keep-clear radius): the middle and the mob windows
    def free(x, z, r):
        if abs(x) > PR - 3 - r or abs(z) > PR - 3 - r:
            return False
        return all((x - tx) ** 2 + (z - tz) ** 2 > (r + tr) ** 2 for tx, tz, tr in taken)
    def spot(r, tries=200):
        for _ in range(tries):
            x, z = rng.randint(-PR + 3, PR - 3), rng.randint(-PR + 3, PR - 3)
            if free(x, z, r):
                taken.append((x, z, r))
                return x, z
        return None
    # trees (persistent leaves, so they don't decay into saplings)
    for n in range(18):
        p = spot(3)
        if not p:
            continue
        x, z = PCX + p[0], cz + p[1]
        wood = rng.choice(["oak", "oak", "birch", "spruce"])
        h = rng.randint(4, 6)
        top = AY + h
        leaves = f"minecraft:{wood}_leaves[persistent=true]"
        a += [f"fill {x - 2} {top - 1} {z - 2} {x + 2} {top} {z + 2} {leaves}",
              f"fill {x - 1} {top + 1} {z - 1} {x + 1} {top + 1} {z + 1} {leaves}",
              f"setblock {x} {top + 2} {z} {leaves}",
              f"fill {x} {AY + 1} {z} {x} {top} {z} minecraft:{wood}_log"]
    # rock outcrops with ore
    for n in range(10):
        p = spot(2)
        if not p:
            continue
        x, z = PCX + p[0], cz + p[1]
        w, d, h = rng.randint(1, 2), rng.randint(1, 2), rng.randint(1, 3)
        a.append(f"fill {x - w} {AY + 1} {z - d} {x + w} {AY + h} {z + d} minecraft:{rng.choice(['stone', 'stone', 'andesite', 'cobblestone'])}")
        a.append(f"fill {x - w + 1} {AY + h + 1} {z - d + 1} {x + w - 1} {AY + h + 1} {z + d - 1} minecraft:stone")
        for _ in range(rng.randint(3, 6)):
            ore = rng.choice(["coal_ore", "coal_ore", "iron_ore", "iron_ore", "copper_ore"])
            a.append(f"setblock {x + rng.randint(-w, w)} {AY + rng.randint(1, h)} {z + rng.randint(-d, d)} minecraft:{ore}")
    # grass and flowers
    for n in range(70):
        x, z = rng.randint(-PR, PR), rng.randint(-PR, PR)
        if free(x, z, 0):
            a.append(f"setblock {PCX + x} {AY + 1} {cz + z} minecraft:{rng.choice(['short_grass'] * 4 + ['fern', 'dandelion', 'poppy', 'cornflower'])} keep")
    # mob windows: worn ground where they come in
    for dx, dz in b.MOB_POINTS:
        a.append(f"fill {PCX + dx - 1} {AY} {cz + dz - 1} {PCX + dx + 1} {AY} {cz + dz + 1} minecraft:coarse_dirt")
    # the core on a stone pad, bedrock under it (nothing digs out from below)
    a += [f"fill {PCX - 2} {AY} {cz - 2} {PCX + 2} {AY} {cz + 2} minecraft:polished_andesite",
          f"setblock {PCX} {AY} {cz} minecraft:bedrock", f"setblock {PCX} {AY + 1} {cz} minecraft:beacon"]
    # the Arsenal, south of the core, facing it
    sx, sz = PCX + 0.5, cz + 6.5
    body = b.npc("pvp.shopnpc", (sx, AY + 1, sz), "☣ Arsenal ☣", "green", "sniper", 180, hand="crossbow", chest="netherite_chestplate")
    a += [f"kill @e[tag=pvp.shopnpc,{box}]"] + body[1:]
    return a


def build(b):
    """Functions for the Core Defense map; returns the hooks build.py puts into the Outbreak functions."""
    fn, wj, tj, NS = b.fn, b.wj, b.tj, b.NS
    P = f"{NS}:pve"
    PCX, AY = b.PCX, b.AY
    cx, cy, cz = PCX + 0.5, AY + 1, CORE_Z + 0.5   # the core block's centre (floor level)
    core_at = f"{PCX} {AY + 1} {CORE_Z}"
    box = b.box(PCX, CORE_Z, b.PR, AY - 4, 40)
    on = f"if score #map pve matches {CORE_ID}"

    # blocks mobs walk through or must never break
    wj(f"data/{NS}/tags/block/core_pass.json", {"values": [
        "#minecraft:replaceable", "#minecraft:small_flowers", "#minecraft:saplings", "minecraft:bedrock", "minecraft:barrier",
        "minecraft:beacon", "minecraft:light", "minecraft:torch", "minecraft:wall_torch", "minecraft:structure_void"]})
    wj(f"data/{NS}/predicate/half.json", {"condition": "minecraft:random_chance", "chance": 0.5})

    fn("pve/core_reset", [f"function {NS}:admin/build_pve_core"])
    fn("pve/core_start", [
        f"scoreboard players set #core pve {CORE_HP}", "tag @a remove pve.cw",
        f"scoreboard players set #corex pve {PCX}", f"scoreboard players set #corey pve {AY + 1}", f"scoreboard players set #corez pve {CORE_Z}",
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
        # only a mob that's stuck digs (moved less than ~0.3 blocks since the last check)
        "scoreboard players operation #ox pve = @s pve.cx", "scoreboard players operation #oz pve = @s pve.cz",
        "execute store result score @s pve.cx run data get entity @s Pos[0] 10",
        "execute store result score @s pve.cz run data get entity @s Pos[2] 10",
        "scoreboard players operation #ox pve -= @s pve.cx", "scoreboard players operation #oz pve -= @s pve.cz",
        "scoreboard players operation #ox pve *= #ox pve", "scoreboard players operation #oz pve *= #oz pve",
        "scoreboard players operation #ox pve += #oz pve",
        "execute if score #ox pve matches 10.. run return run scoreboard players set @s pve.dig 0",
        f"execute if entity @s[tag=pve.boss] run return run function {P}/core_bossdig",
        f"execute facing {cx} ~ {cz} positioned ^ ^1 ^0.8 unless block ~ ~ ~ #{NS}:core_pass run return run function {P}/core_dig",
        f"execute facing {cx} ~ {cz} positioned ^ ^ ^0.8 unless block ~ ~ ~ #{NS}:core_pass run return run function {P}/core_dig",
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
        f"execute facing {cx} ~ {cz} positioned ^ ^1 ^1.2 run particle minecraft:crit ~ ~ ~ 0.8 0.8 0.8 0.1 8",
        f"execute if score @s pve.dig matches ..{DIG - 1} run return 0",
        *[f"execute facing {cx} ~ {cz} positioned ^{x} ^{y} ^1.2 unless block ~ ~ ~ #{NS}:core_pass run setblock ~ ~ ~ minecraft:air destroy"
          for x, y in boss_cells],
        "scoreboard players set @s pve.dig 0",
    ])
    fn("pve/core_build", [   # a Builder: bridge a drop (2+ deep) towards the core; pillar up under a player standing high nearby
        f"execute unless block ~ ~-0.5 ~ #minecraft:air facing {cx} ~ {cz} positioned ^ ^-1 ^0.8 if block ~ ~ ~ #minecraft:air if block ~ ~-1 ~ #minecraft:air "
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
        f"execute as @a[tag=pve.cw] unless entity @s[{box}] run tp @s {cx} {AY + 12} {cz}",
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
        f"tp @s {cx} {AY + 12} {cz} 0 90",
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
        "objectives": ["pve.dig dummy", "pve.cx dummy", "pve.cz dummy", "pve.rt dummy"],
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
