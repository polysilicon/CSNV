"""Generate the crispy_falling datapack: skyblock-style private 50x50 islands where blocks rain from the sky
while a member of the island is online. Hub at 0,100,0; islands on a 1024-block grid starting at z=2048."""
import json, os, shutil, sys

OUT = sys.argv[1]
NS = "crispy_falling"
HUB_Y = 100
SIZE = 50                 # playable island is SIZE x SIZE
GRID = 1024               # spacing between islands
COLS = 64
SPAWN_Y = 310             # where falling blocks appear
FLOOR_Y = 0               # bedrock floor

# ---------------------------------------------------------------- what falls (weight, block, damage tier)
# tier: (FallHurtAmount per block fallen, FallHurtMax)
TIER = {"l": ("0.05", 1), "m": ("0.2", 3), "h": ("0.5", 6)}
BLOCKS = [
    (150, "dirt", "l"), (90, "grass_block", "l"), (110, "stone", "h"), (50, "cobblestone", "h"),
    (25, "andesite", "h"), (20, "diorite", "h"), (20, "granite", "h"), (20, "deepslate", "h"), (10, "tuff", "h"),
    (50, "sand", "l"), (10, "red_sand", "l"), (45, "gravel", "l"), (15, "clay", "m"), (5, "mud", "l"),
    (25, "oak_log", "m"), (15, "birch_log", "m"), (15, "spruce_log", "m"), (5, "jungle_log", "m"),
    (5, "acacia_log", "m"), (5, "dark_oak_log", "m"), (3, "cherry_log", "m"),
    (20, "oak_leaves", "l"), (10, "birch_leaves", "l"), (6, "spruce_leaves", "l"),
    (6, "oak_sapling", "l"), (3, "birch_sapling", "l"), (3, "spruce_sapling", "l"), (2, "jungle_sapling", "l"),
    (35, "coal_ore", "h"), (25, "iron_ore", "h"), (25, "copper_ore", "h"), (8, "gold_ore", "h"),
    (10, "redstone_ore", "h"), (8, "lapis_ore", "h"), (3, "diamond_ore", "h"), (2, "emerald_ore", "h"),
    (5, "deepslate_iron_ore", "h"), (15, "ice", "m"), (5, "snow_block", "l"),
    (6, "pumpkin", "m"), (6, "melon", "m"), (4, "hay_block", "l"), (10, "moss_block", "l"),
    (5, "podzol", "l"), (3, "mycelium", "l"), (3, "brown_mushroom_block", "l"), (3, "red_mushroom_block", "l"),
    (4, "cactus", "m"), (5, "sugar_cane", "l"), (4, "obsidian", "h"), (3, "cobweb", "l"), (2, "tnt", "m"),
    (3, "bone_block", "m"), (2, "bookshelf", "m"), (1, "amethyst_block", "h"), (1, "sculk", "l"),
]
ITEMS = [  # (weight, item, count) — dropped as loose items
    (20, "wheat_seeds", 3), (8, "carrot", 2), (8, "potato", 2), (6, "beetroot_seeds", 3), (6, "melon_seeds", 2),
    (6, "pumpkin_seeds", 2), (10, "bone", 2), (8, "string", 2), (6, "feather", 2), (5, "egg", 1),
    (6, "flint", 2), (4, "sweet_berries", 3), (3, "cocoa_beans", 2), (3, "bamboo", 2), (2, "bucket", 1),
    (3, "kelp", 2), (2, "lily_pad", 1), (2, "glow_berries", 2),
]
ITEM_CHANCE = 6           # % of drops that are loose items
ANIMALS = [(20, "cow"), (20, "pig"), (20, "sheep"), (20, "chicken"), (10, "rabbit"), (6, "horse"), (4, "donkey"),
           (4, "llama"), (6, "wolf"), (6, "cat"), (4, "parrot"), (5, "goat"), (2, "mooshroom"), (3, "fox"), (3, "turtle")]
DUNGEON_AGES = [900, 2400, 4500, 7200, 10800]   # seconds of island play time: 15, 40, 75, 120, 180 min
PORTAL_AGE = 9000                               # 150 min
ANIMAL_EVERY = 150                              # seconds
HOSTILE_CAP = 10                                # natural hostiles allowed per island (the whole mob cap otherwise lands on 2500 blocks)
# Nether: every island gets its own void Nether plot (50x50 bedrock floor at y32) centred under island/8.
NFLOOR_Y = 32
NSPAWN_Y = 120
NBLOCKS = [
    (220, "netherrack", "m"), (40, "soul_sand", "l"), (25, "soul_soil", "l"), (25, "gravel", "l"), (25, "magma_block", "m"),
    (20, "glowstone", "l"), (30, "nether_quartz_ore", "h"), (25, "nether_gold_ore", "h"), (25, "basalt", "h"), (30, "blackstone", "h"),
    (15, "crimson_nylium", "m"), (15, "warped_nylium", "m"), (15, "crimson_stem", "m"), (15, "warped_stem", "m"),
    (12, "nether_wart_block", "l"), (8, "warped_wart_block", "l"), (6, "shroomlight", "l"), (8, "bone_block", "m"),
    (10, "nether_bricks", "h"), (5, "smooth_basalt", "h"), (6, "obsidian", "h"), (3, "crying_obsidian", "h"),
    (3, "gilded_blackstone", "h"), (1, "ancient_debris", "h"),
]
NITEMS = [
    (15, "nether_wart", 2), (8, "crimson_fungus", 1), (8, "warped_fungus", 1), (10, "quartz", 3), (12, "gold_nugget", 4),
    (8, "glowstone_dust", 3), (3, "magma_cream", 1), (3, "twisting_vines", 2), (3, "weeping_vines", 2), (2, "blaze_powder", 1),
    (1, "ghast_tear", 1),
]
FORTRESS_AGES = [(120, "blaze"), (1200, "blaze"), (3600, "wither_skeleton")]   # seconds spent in the island's Nether
BASTION_AGES = [600, 2400]
NHOSTILE_CAP = 10       # natural Nether spawns only; spawner blazes / wither skeletons are not culled
NHOSTILES = ["zombified_piglin", "ghast", "magma_cube", "hoglin", "enderman", "skeleton", "strider"]
HOSTILES = ["zombie", "husk", "drowned", "zombie_villager", "skeleton", "stray", "bogged", "spider", "cave_spider", "creeper",
            "enderman", "witch", "slime", "silverfish", "phantom"]

if os.path.exists(OUT): shutil.rmtree(OUT)
def w(path, text):
    p = os.path.join(OUT, path); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(text.strip("\n") + "\n")
def fn(name, text): w(f"data/{NS}/function/{name}.mcfunction", text)
def js(path, obj): w(path, json.dumps(obj, indent=1))

def cumulative(table):
    out, acc = [], 0
    for row in table:
        out.append((acc + 1, acc + row[0], row)); acc += row[0]
    return out, acc

w("pack.mcmeta", json.dumps({"pack": {"description": "Crispy Falling: private islands where blocks rain from the sky",
                                       "min_format": [107, 0], "max_format": [107, 1]}}, indent=2))
js("data/minecraft/tags/function/load.json", {"values": [f"{NS}:load"]})
js(f"data/{NS}/tags/entity_type/hostile.json", {"values": [f"minecraft:{m}" for m in HOSTILES]})
js(f"data/{NS}/tags/entity_type/nhostile.json", {"values": [f"minecraft:{m}" for m in NHOSTILES]})
js("data/minecraft/tags/function/tick.json", {"values": [f"{NS}:tick"]})
js("data/minecraft/tags/dialog/pause_screen_additions.json", {"values": [f"{NS}:menu"]})
js("data/minecraft/tags/dialog/quick_actions.json", {"values": [f"{NS}:menu"]})

# ---------------------------------------------------------------- load / setup
fn("load", f"""
scoreboard objectives add cf_plot dummy
scoreboard objectives add cf_act trigger
scoreboard objectives add cf_inv dummy
scoreboard objectives add cf_on dummy
scoreboard objectives add cf_was dummy
scoreboard objectives add cf_age dummy
scoreboard objectives add cf_dng dummy
scoreboard objectives add cf_tmp dummy
scoreboard objectives add cf_cd dummy
scoreboard objectives add cf_seen dummy
scoreboard objectives add cf_die deathCount
scoreboard objectives add cf_cfg dummy
scoreboard objectives add cf_non dummy
scoreboard objectives add cf_nwas dummy
scoreboard objectives add cf_nage dummy
scoreboard objectives add cf_npend dummy
scoreboard players set #8 cf_tmp 8
scoreboard players set #64 cf_tmp {COLS}
scoreboard players set #grid cf_tmp {GRID}
scoreboard players set #60 cf_tmp 60
execute unless score #rate cf_cfg matches 1.. run scoreboard players set #rate cf_cfg 2
execute unless data storage {NS}:d plots run function {NS}:setup
# one-time: give islands made before the void Nether existed their Nether plot
execute unless score #nmig cf_cfg matches 1 if score #next cf_tmp matches 1.. run function {NS}:migrate/start
scoreboard players set #nmig cf_cfg 1
gamerule minecraft:respawn_radius 0
gamerule minecraft:keep_inventory false
""")
fn("migrate/start", f"""
scoreboard players set #i cf_tmp 1
function {NS}:migrate/step
""")
fn("migrate/step", f"""
execute store result storage {NS}:d q.i int 1 run scoreboard players get #i cf_tmp
function {NS}:migrate/one with storage {NS}:d q
scoreboard players add #i cf_tmp 1
execute if score #i cf_tmp <= #next cf_tmp run function {NS}:migrate/step
""")
fn("migrate/one", f"""
$data modify storage {NS}:d cur set from storage {NS}:d plots[$(i)]
function {NS}:plot/nfields with storage {NS}:d cur
$data modify storage {NS}:d plots[$(i)] merge from storage {NS}:d nf
$data modify storage {NS}:d cur set from storage {NS}:d plots[$(i)]
function {NS}:plot/nbuild with storage {NS}:d cur
""")
fn("setup", f"""
# first install only
data modify storage {NS}:d plots set value [{{id:0}}]
scoreboard players set #next cf_tmp 0
function {NS}:hub
setworldspawn 0 {HUB_Y+1} 0
""")

# ---------------------------------------------------------------- hub
def sign(lines, color="black"):
    return "{front_text:{messages:[%s],color:\"%s\",has_glowing_text:1b},is_waxed:1b}" % (",".join(json.dumps(l) for l in lines), color)
def label(x, y, z, text, scale=1.5, yaw=0, bill="fixed"):
    return (f"summon minecraft:text_display {x} {y} {z} " +
            "{Tags:[\"%s\"],billboard:\"%s\",Rotation:[%sf,0f],text:%s,background:0,shadow:1b,"
            "transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[%sf,%sf,%sf]}}"
            % (NS, bill, yaw, text, scale, scale, scale))
Y = HUB_Y
hub = [
    "forceload add -16 -16 15 15",
    f"fill -14 {Y-1} -14 14 {Y+8} 14 minecraft:air",
    f"fill -13 {Y} -13 13 {Y} 13 minecraft:polished_deepslate",
    f"fill -12 {Y} -12 12 {Y} 12 minecraft:smooth_quartz",
    f"fill -6 {Y} -6 6 {Y} 6 minecraft:moss_block",
    f"fill -2 {Y} -2 2 {Y} 2 minecraft:chiseled_quartz_block",
    f"fill -13 {Y+1} -13 13 {Y+1} 13 minecraft:polished_deepslate_wall",
    f"fill -12 {Y+1} -12 12 {Y+1} 12 minecraft:air",
] + [f"setblock {x} {Y+2} {z} minecraft:lantern" for x in (-13, 13) for z in (-13, 13)] + [f"setblock {x} {Y+3} {z} minecraft:light[level=15]" for x in (-9, 0, 9) for z in (-9, 0, 9)] + [
    # button wall to the north
    f"fill -4 {Y+1} -8 4 {Y+5} -8 minecraft:quartz_bricks",
    f"fill -4 {Y+6} -8 4 {Y+6} -8 minecraft:quartz_slab",
]
BTNS = [(-2, "act/home", ["", "MY", "ISLAND", ""], "lime"), (0, None, ["", "ISLAND", "MENU", ""], "yellow"),
        (2, "act/hub_help", ["", "HOW TO", "PLAY", ""], "light_blue")]
for x, f, lines, col in BTNS:
    cmd = f"execute as @p[distance=..6] run function {NS}:{f}" if f else f"dialog show @p[distance=..6] {NS}:menu"
    hub += [f"setblock {x} {Y+2} -9 minecraft:command_block[facing=up]" + "{Command:%s,TrackOutput:0b}" % json.dumps(cmd),
            f"setblock {x} {Y+2} -7 minecraft:stone_button[face=wall,facing=south]",
            f"setblock {x} {Y+3} -7 minecraft:dark_oak_wall_sign[facing=south]" + sign(lines, col)]
hub += [
    f"kill @e[type=minecraft:text_display,tag={NS}]",
    label(0.5, Y + 5.3, -6.9, '{text:"Crispy Falling",color:"gold",bold:1b}', 2.5),
    label(0.5, Y + 4.6, -6.9, '{text:"Survive on your own island while the sky falls",color:"gray"}', 0.8),
    label(0.5, Y + 3.5, 0.5, '{text:"Press Esc → Island Menu anytime",color:"yellow"}', 1.0, bill="vertical"),
]
fn("hub", "\n".join(hub))

# ---------------------------------------------------------------- tick
fn("tick", f"""
scoreboard players enable @a cf_act
execute as @a[scores={{cf_act=1..}}] at @s run function {NS}:act/dispatch
execute as @a unless score @s cf_seen matches 1 run function {NS}:first_join
# respawned players (alive again) go back to their island unless they slept in a bed there
execute as @e[type=minecraft:player,scores={{cf_die=1..}}] run function {NS}:p/respawned
# hub = adventure, everywhere else = survival
execute as @a[gamemode=survival] at @s if dimension minecraft:overworld if entity @s[x=-14,y={Y-20},z=-14,dx=28,dy=60,dz=28] run gamemode adventure @s
execute as @a[gamemode=adventure] at @s unless entity @s[x=-14,y={Y-20},z=-14,dx=28,dy=60,dz=28] run gamemode survival @s
execute as @a[gamemode=adventure] at @s unless dimension minecraft:overworld run gamemode survival @s
execute as @e[type=minecraft:player,x=-14,y={Y-60},z=-14,dx=28,dy=50,dz=28] run tp @s 0.5 {Y+1} 0.5
scoreboard players add #t cf_tmp 1
execute if score #t cf_tmp matches 10 run function {NS}:p/bounds_all
execute if score #t cf_tmp matches 10 run function {NS}:p/nbounds_all
execute if score #t cf_tmp matches 20.. run function {NS}:second
""")
fn("second", f"""
scoreboard players set #t cf_tmp 0
scoreboard players remove @a[scores={{cf_cd=1..}}] cf_cd 1
# count online members per island, then run every island that has (or just lost) someone online
scoreboard players reset * cf_on
scoreboard players reset * cf_non
execute as @a[scores={{cf_plot=1..}}] run function {NS}:p/count
scoreboard players set #i cf_tmp 1
execute if score #next cf_tmp matches 1.. run function {NS}:loop/step
""")
fn("p/count", f"""
execute store result storage {NS}:d q.i int 1 run scoreboard players get @s cf_plot
function {NS}:p/count2 with storage {NS}:d q
execute at @s if dimension minecraft:the_nether run function {NS}:p/ncount2 with storage {NS}:d q
""")
fn("p/count2", "$scoreboard players add #p$(i) cf_on 1")
fn("p/ncount2", "$scoreboard players add #p$(i) cf_non 1")
fn("loop/step", f"""
execute store result storage {NS}:d q.i int 1 run scoreboard players get #i cf_tmp
function {NS}:loop/one with storage {NS}:d q
scoreboard players add #i cf_tmp 1
execute if score #i cf_tmp <= #next cf_tmp run function {NS}:loop/step
""")
fn("loop/one", f"""
$execute if score #p$(i) cf_npend matches 1 run function {NS}:plot/npend_i {{i:$(i)}}
$execute unless score #p$(i) cf_on matches 1.. unless score #p$(i) cf_was matches 1.. run return 0
$data modify storage {NS}:d cur set from storage {NS}:d plots[$(i)]
function {NS}:plot/tick with storage {NS}:d cur
""")

# ---------------------------------------------------------------- per-island second
drop_calls = "\n".join(f"execute if score #rate cf_cfg matches {n}.. run function {NS}:drop/one with storage {NS}:d cur" for n in range(1, 7))
ev_lines = "\n".join(f"$execute if score #p$(id) cf_age matches {a} run function {NS}:ev/dungeon with storage {NS}:d cur" for a in DUNGEON_AGES)
fn("plot/tick", f"""
# just emptied: stop loading it (and its Nether)
$execute unless score #p$(id) cf_on matches 1.. run forceload remove $(x) $(z) $(x1) $(z1)
$execute unless score #p$(id) cf_on matches 1.. if score #p$(id) cf_nwas matches 1.. in minecraft:the_nether run forceload remove $(nwx) $(nwz) $(nwx1) $(nwz1)
$execute unless score #p$(id) cf_on matches 1.. run scoreboard players set #p$(id) cf_nwas 0
$execute unless score #p$(id) cf_on matches 1.. run return run scoreboard players set #p$(id) cf_was 0
$execute unless score #p$(id) cf_was matches 1.. run forceload add $(x) $(z) $(x1) $(z1)
$scoreboard players set #p$(id) cf_was 1
$scoreboard players add #p$(id) cf_age 1
{drop_calls}
# events by island play time
$scoreboard players operation #m cf_tmp = #p$(id) cf_age
scoreboard players set #k cf_tmp {ANIMAL_EVERY}
scoreboard players operation #m cf_tmp %= #k cf_tmp
execute if score #m cf_tmp matches 0 run function {NS}:ev/animal with storage {NS}:d cur
{ev_lines}
$execute if score #p$(id) cf_age matches {PORTAL_AGE} run function {NS}:ev/portal with storage {NS}:d cur
# hunger: food gets harder to keep up as the island ages
$scoreboard players operation #m cf_tmp = #p$(id) cf_age
scoreboard players set #k cf_tmp 120
scoreboard players operation #m cf_tmp %= #k cf_tmp
$execute if score #p$(id) cf_age matches 3600..10799 if score #m cf_tmp matches 0 run effect give @a[x=$(x),y=-64,z=$(z),dx={SIZE-1},dy=400,dz={SIZE-1}] minecraft:hunger 20 0 true
$execute if score #p$(id) cf_age matches 10800.. if score #m cf_tmp matches 0 run effect give @a[x=$(x),y=-64,z=$(z),dx={SIZE-1},dy=400,dz={SIZE-1}] minecraft:hunger 30 1 true
function {NS}:plot/ntick with storage {NS}:d cur
# hostile cap: mobs already here stay; brand-new spawns over the cap are sent into the void
$execute store result score #h cf_tmp if entity @e[type=#{NS}:hostile,x=$(x),y=-64,z=$(z),dx={SIZE-1},dy=400,dz={SIZE-1}]
$execute if score #h cf_tmp matches {HOSTILE_CAP+1}.. as @e[type=#{NS}:hostile,tag=!cf_old,x=$(x),y=-64,z=$(z),dx={SIZE-1},dy=400,dz={SIZE-1}] run function {NS}:mob_cull
$tag @e[type=#{NS}:hostile,tag=!cf_old,x=$(x),y=-64,z=$(z),dx={SIZE-1},dy=400,dz={SIZE-1}] add cf_old
""")

fn("mob_cull", f"""
execute if score #h cf_tmp matches ..{HOSTILE_CAP} run return 0
execute at @s run tp @s ~ -200 ~
scoreboard players remove #h cf_tmp 1
""")

# ---------------------------------------------------------------- drops
bl, btotal = cumulative(BLOCKS)
it, itotal = cumulative(ITEMS)
pick_b = "\n".join(
    f"execute if score #r cf_tmp matches {a}..{b} run data modify storage {NS}:d drop merge value "
    f"{{b:\"minecraft:{blk}\",a:\"{TIER[t][0]}\",m:{TIER[t][1]}}}" for a, b, (_, blk, t) in bl)
pick_i = "\n".join(
    f"execute if score #r cf_tmp matches {a}..{b} run data modify storage {NS}:d drop merge value "
    f"{{i:\"minecraft:{item}\",n:{n}}}" for a, b, (_, item, n) in it)
fn("drop/one", f"""
$execute store result storage {NS}:d drop.x int 1 run random value $(x)..$(x1)
$execute store result storage {NS}:d drop.z int 1 run random value $(z)..$(z1)
execute store result score #c cf_tmp run random value 1..100
execute if score #c cf_tmp matches ..{ITEM_CHANCE} run return run function {NS}:drop/item
execute store result score #r cf_tmp run random value 1..{btotal}
{pick_b}
function {NS}:drop/summon_block with storage {NS}:d drop
""")
fn("drop/item", f"""
execute store result score #r cf_tmp run random value 1..{itotal}
{pick_i}
function {NS}:drop/summon_item with storage {NS}:d drop
""")
fn("drop/summon_block", f"$summon minecraft:falling_block $(x).5 {SPAWN_Y} $(z).5 {{BlockState:{{Name:\"$(b)\"}},Time:1,DropItem:1b,HurtEntities:1b,FallHurtAmount:$(a)f,FallHurtMax:$(m)}}")
fn("drop/summon_item", f"$summon minecraft:item $(x).5 {SPAWN_Y} $(z).5 {{Item:{{id:\"$(i)\",count:$(n)}},PickupDelay:10s}}")

# ---------------------------------------------------------------- events
# events pick a spot at least 4 blocks in from the edge (ranges pre-shrunk in the plot record as ix/ix1/iz/iz1)
fn("ev/animal", f"""
$execute store result storage {NS}:d ev.x int 1 run random value $(ix)..$(ix1)
$execute store result storage {NS}:d ev.z int 1 run random value $(iz)..$(iz1)
$data modify storage {NS}:d ev.id set value $(id)
execute store result score #r cf_tmp run random value 1..{cumulative(ANIMALS)[1]}
""" + "\n".join(f"execute if score #r cf_tmp matches {a}..{b} run data modify storage {NS}:d ev.e set value \"minecraft:{e}\""
                for a, b, (_, e) in cumulative(ANIMALS)[0]) + f"""
function {NS}:ev/animal_at with storage {NS}:d ev
""")
fn("ev/animal_at", f"""
$execute positioned $(x).5 {SPAWN_Y-4} $(z).5 positioned over motion_blocking run summon $(e) ~ ~ ~ {{Tags:["cf_animal"]}}
$execute positioned $(x).5 {SPAWN_Y-4} $(z).5 positioned over motion_blocking run particle minecraft:happy_villager ~ ~1 ~ 0.5 0.5 0.5 0 15 force
$tellraw @a[scores={{cf_plot=$(id)}}] [{{text:"🐾 ",color:"green"}},{{text:"An animal was dropped onto your island. Save it before the sky buries it!",color:"green"}}]
""")
fn("ev/dungeon", f"""
$execute store result storage {NS}:d ev.x int 1 run random value $(ix)..$(ix1)
$execute store result storage {NS}:d ev.z int 1 run random value $(iz)..$(iz1)
$data modify storage {NS}:d ev.id set value $(id)
function {NS}:ev/dungeon_at with storage {NS}:d ev
""")
fn("ev/dungeon_at", f"""
$execute positioned $(x) {SPAWN_Y-12} $(z) positioned over motion_blocking_no_leaves run function {NS}:ev/dungeon_build
$tellraw @a[scores={{cf_plot=$(id)}}] [{{text:"☄ ",color:"red"}},{{text:"A dungeon crashed into your island! Monsters guard its loot.",color:"red"}}]
$execute as @a[scores={{cf_plot=$(id)}}] at @s run playsound minecraft:entity.generic.explode master @s ~ ~ ~ 1 0.6
""")
fn("ev/dungeon_build", f"""
# shell only fills air, so it never overwrites anything players built
fill ~-3 ~ ~-3 ~3 ~ ~3 minecraft:mossy_cobblestone replace minecraft:air
fill ~-3 ~1 ~-3 ~3 ~4 ~3 minecraft:cobblestone replace minecraft:air
fill ~-2 ~1 ~-2 ~2 ~3 ~2 minecraft:air replace minecraft:cobblestone
fill ~-3 ~1 ~ ~-3 ~2 ~ minecraft:air replace minecraft:cobblestone
fill ~-2 ~4 ~-2 ~2 ~4 ~2 minecraft:mossy_cobblestone replace minecraft:cobblestone
execute store result score #r cf_tmp run random value 1..3
execute if score #r cf_tmp matches 1 run setblock ~ ~1 ~ minecraft:spawner{{SpawnData:{{entity:{{id:"minecraft:zombie"}}}}}}
execute if score #r cf_tmp matches 2 run setblock ~ ~1 ~ minecraft:spawner{{SpawnData:{{entity:{{id:"minecraft:skeleton"}}}}}}
execute if score #r cf_tmp matches 3 run setblock ~ ~1 ~ minecraft:spawner{{SpawnData:{{entity:{{id:"minecraft:spider"}}}}}}
setblock ~2 ~1 ~2 minecraft:chest[facing=north]{{LootTable:"{NS}:chests/dungeon"}}
setblock ~-2 ~1 ~-2 minecraft:chest[facing=south]{{LootTable:"{NS}:chests/dungeon"}}
summon minecraft:zombie ~1 ~1 ~-1
summon minecraft:skeleton ~-1 ~1 ~1
particle minecraft:explosion_emitter ~ ~2 ~ 0 0 0 0 1 force
""")
fn("ev/portal", f"""
$execute store result storage {NS}:d ev.x int 1 run random value $(ix)..$(ix1)
$execute store result storage {NS}:d ev.z int 1 run random value $(iz)..$(iz1)
$data modify storage {NS}:d ev.id set value $(id)
function {NS}:ev/portal_at with storage {NS}:d ev
""")
fn("ev/portal_at", f"""
$execute positioned $(x) {SPAWN_Y-12} $(z) positioned over motion_blocking_no_leaves run function {NS}:ev/portal_build
$tellraw @a[scores={{cf_plot=$(id)}}] [{{text:"✦ ",color:"light_purple"}},{{text:"An End portal crashed into your island! Fill it with 12 Eyes of Ender to reach the End.",color:"light_purple"}}]
$execute as @a[scores={{cf_plot=$(id)}}] at @s run playsound minecraft:block.end_portal_frame.fill master @s ~ ~ ~ 1 0.5
""")
fn("ev/portal_build", """
fill ~-3 ~ ~-3 ~3 ~ ~3 minecraft:stone_bricks replace minecraft:air
fill ~-2 ~1 ~-2 ~2 ~3 ~2 minecraft:air
fill ~-1 ~1 ~-2 ~1 ~1 ~-2 minecraft:end_portal_frame[facing=south]
fill ~-1 ~1 ~2 ~1 ~1 ~2 minecraft:end_portal_frame[facing=north]
fill ~-2 ~1 ~-1 ~-2 ~1 ~1 minecraft:end_portal_frame[facing=east]
fill ~2 ~1 ~-1 ~2 ~1 ~1 minecraft:end_portal_frame[facing=west]
particle minecraft:portal ~ ~2 ~ 1.5 1 1.5 0.5 200 force
""")


# ---------------------------------------------------------------- void Nether
nbl, nbtotal = cumulative(NBLOCKS)
nit, nitotal = cumulative(NITEMS)
fn("plot/nfields", f"""
# Nether plot = 50x50 centred on (cx/8, cz/8); writes the n* fields into storage nf
$scoreboard players set #a cf_tmp $(cx)
$scoreboard players set #b cf_tmp $(cz)
scoreboard players operation #a cf_tmp /= #8 cf_tmp
scoreboard players operation #b cf_tmp /= #8 cf_tmp
data modify storage {NS}:d nf set value {{}}
""" + "\n".join(
    f"scoreboard players operation #o cf_tmp = #{s} cf_tmp\nscoreboard players {'add' if d >= 0 else 'remove'} #o cf_tmp {abs(d)}\n"
    f"execute store result storage {NS}:d nf.{k} int 1 run scoreboard players get #o cf_tmp"
    for k, s, d in [("ncx", "a", 0), ("ncz", "b", 0), ("nx", "a", -25), ("nz", "b", -25), ("nx1", "a", 24), ("nz1", "b", 24),
                    ("nwx", "a", -26), ("nwz", "b", -26), ("nwx1", "a", 25), ("nwz1", "b", 25),
                    ("nix", "a", -21), ("niz", "b", -21), ("nix1", "a", 20), ("niz1", "b", 20)]))
fn("plot/nbuild", f"""
# load the Nether plot; the build itself waits until the chunks are in (plot/npend, checked every second)
$execute in minecraft:the_nether run forceload add $(nwx) $(nwz) $(nwx1) $(nwz1)
$scoreboard players set #p$(id) cf_npend 1
""")
fn("plot/npend_i", f"""
$data modify storage {NS}:d cur set from storage {NS}:d plots[$(i)]
function {NS}:plot/npend with storage {NS}:d cur
""")
fn("plot/npend", f"""
$execute in minecraft:the_nether unless loaded $(nwx) {NFLOOR_Y} $(nwz) run return run execute in minecraft:the_nether run forceload add $(nwx) $(nwz) $(nwx1) $(nwz1)
$execute in minecraft:the_nether unless loaded $(nwx1) {NFLOOR_Y} $(nwz1) run return 0
$execute in minecraft:the_nether run fill $(nx) {NFLOOR_Y} $(nz) $(nx1) {NFLOOR_Y} $(nz1) minecraft:bedrock
$execute in minecraft:the_nether run fill $(nwx) {NFLOOR_Y-1} $(nwz) $(nwx1) {NFLOOR_Y-1} $(nwz1) minecraft:barrier
$execute in minecraft:the_nether run fill $(nwx) 0 $(nwz) $(nwx1) 255 $(nwz) minecraft:barrier
$execute in minecraft:the_nether run fill $(nwx) 0 $(nwz1) $(nwx1) 255 $(nwz1) minecraft:barrier
$execute in minecraft:the_nether run fill $(nwx) 0 $(nwz) $(nwx) 255 $(nwz1) minecraft:barrier
$execute in minecraft:the_nether run fill $(nwx1) 0 $(nwz) $(nwx1) 255 $(nwz1) minecraft:barrier
$execute in minecraft:the_nether run setblock $(ncx) {NFLOOR_Y+1} $(ncz) minecraft:netherrack
$scoreboard players reset #p$(id) cf_npend
$execute unless score #p$(id) cf_nwas matches 1.. in minecraft:the_nether run forceload remove $(nwx) $(nwz) $(nwx1) $(nwz1)
""")
ndrop_calls = "\n".join(f"execute if score #rate cf_cfg matches {n}.. in minecraft:the_nether run function {NS}:ndrop/one with storage {NS}:d cur" for n in range(1, 7))
fort_lines = "\n".join(f"$execute if score #p$(id) cf_nage matches {a} run data modify storage {NS}:d ev.sp set value \"minecraft:{m}\"\n"
                       f"$execute if score #p$(id) cf_nage matches {a} in minecraft:the_nether run function {NS}:nev/fortress with storage {NS}:d cur"
                       for a, m in FORTRESS_AGES)
bast_lines = "\n".join(f"$execute if score #p$(id) cf_nage matches {a} in minecraft:the_nether run function {NS}:nev/bastion with storage {NS}:d cur" for a in BASTION_AGES)
fn("plot/ntick", f"""
# runs every second for an island with someone online; the Nether part only while a member is in it
$execute unless score #p$(id) cf_non matches 1.. if score #p$(id) cf_nwas matches 1.. in minecraft:the_nether run forceload remove $(nwx) $(nwz) $(nwx1) $(nwz1)
$execute unless score #p$(id) cf_non matches 1.. run return run scoreboard players set #p$(id) cf_nwas 0
$execute unless score #p$(id) cf_nwas matches 1.. in minecraft:the_nether run forceload add $(nwx) $(nwz) $(nwx1) $(nwz1)
$scoreboard players set #p$(id) cf_nwas 1
$scoreboard players add #p$(id) cf_nage 1
$execute if score #p$(id) cf_nage matches 1 run tellraw @a[scores={{cf_plot=$(id)}}] [{{text:"🔥 ",color:"gold"}},{{text:"Welcome to your island's Nether. Nether blocks fall here while a teammate is in it. A fortress wreck with a blaze spawner crashes in after 2 minutes here; a bastion after 10.",color:"gold"}}]
{ndrop_calls}
{fort_lines}
{bast_lines}
$execute in minecraft:the_nether store result score #h cf_tmp if entity @e[type=#{NS}:nhostile,x=$(nx),y=0,z=$(nz),dx={SIZE-1},dy=256,dz={SIZE-1}]
$execute in minecraft:the_nether if score #h cf_tmp matches {NHOSTILE_CAP+1}.. as @e[type=#{NS}:nhostile,tag=!cf_old,x=$(nx),y=0,z=$(nz),dx={SIZE-1},dy=256,dz={SIZE-1}] run function {NS}:nmob_cull
$execute in minecraft:the_nether run tag @e[type=#{NS}:nhostile,tag=!cf_old,x=$(nx),y=0,z=$(nz),dx={SIZE-1},dy=256,dz={SIZE-1}] add cf_old
""")
fn("nmob_cull", f"""
execute if score #h cf_tmp matches ..{NHOSTILE_CAP} run return 0
execute at @s run tp @s ~ -100 ~
scoreboard players remove #h cf_tmp 1
""")
pick_nb = "\n".join(
    f"execute if score #r cf_tmp matches {a}..{b} run data modify storage {NS}:d drop merge value "
    f"{{b:\"minecraft:{blk}\",a:\"{TIER[t][0]}\",m:{TIER[t][1]}}}" for a, b, (_, blk, t) in nbl)
pick_ni = "\n".join(
    f"execute if score #r cf_tmp matches {a}..{b} run data modify storage {NS}:d drop merge value "
    f"{{i:\"minecraft:{item}\",n:{n}}}" for a, b, (_, item, n) in nit)
fn("ndrop/one", f"""
$execute store result storage {NS}:d drop.x int 1 run random value $(nx)..$(nx1)
$execute store result storage {NS}:d drop.z int 1 run random value $(nz)..$(nz1)
execute store result score #c cf_tmp run random value 1..100
execute if score #c cf_tmp matches ..{ITEM_CHANCE} run return run function {NS}:ndrop/item
execute store result score #r cf_tmp run random value 1..{nbtotal}
{pick_nb}
function {NS}:ndrop/summon_block with storage {NS}:d drop
""")
fn("ndrop/item", f"""
execute store result score #r cf_tmp run random value 1..{nitotal}
{pick_ni}
function {NS}:ndrop/summon_item with storage {NS}:d drop
""")
fn("ndrop/summon_block", f"$summon minecraft:falling_block $(x).5 {NSPAWN_Y} $(z).5 {{BlockState:{{Name:\"$(b)\"}},Time:1,DropItem:1b,HurtEntities:1b,FallHurtAmount:$(a)f,FallHurtMax:$(m)}}")
fn("ndrop/summon_item", f"$summon minecraft:item $(x).5 {NSPAWN_Y} $(z).5 {{Item:{{id:\"$(i)\",count:$(n)}},PickupDelay:10s}}")
fn("nev/fortress", f"""
$execute store result storage {NS}:d ev.x int 1 run random value $(nix)..$(nix1)
$execute store result storage {NS}:d ev.z int 1 run random value $(niz)..$(niz1)
$data modify storage {NS}:d ev.id set value $(id)
function {NS}:nev/fortress_at with storage {NS}:d ev
""")
fn("nev/fortress_at", f"""
$execute positioned $(x) {NSPAWN_Y-12} $(z) positioned over motion_blocking_no_leaves run function {NS}:nev/fortress_build {{sp:"$(sp)"}}
$tellraw @a[scores={{cf_plot=$(id)}}] [{{text:"☄ ",color:"dark_red"}},{{text:"A Nether fortress wreck crashed into your island's Nether!",color:"red"}}]
$execute as @a[scores={{cf_plot=$(id)}}] at @s run playsound minecraft:entity.generic.explode master @s ~ ~ ~ 1 0.5
""")
fn("nev/fortress_build", f"""
# shell only fills air, so it never overwrites anything players built
fill ~-3 ~ ~-3 ~3 ~ ~3 minecraft:nether_bricks replace minecraft:air
fill ~-3 ~1 ~-3 ~3 ~4 ~3 minecraft:nether_bricks replace minecraft:air
fill ~-2 ~1 ~-2 ~2 ~3 ~2 minecraft:air replace minecraft:nether_bricks
fill ~-3 ~1 ~ ~-3 ~2 ~ minecraft:air replace minecraft:nether_bricks
fill ~3 ~1 ~ ~3 ~2 ~ minecraft:air replace minecraft:nether_bricks
fill ~-3 ~4 ~-3 ~3 ~4 ~3 minecraft:nether_brick_fence replace minecraft:nether_bricks
fill ~-2 ~4 ~-2 ~2 ~4 ~2 minecraft:nether_bricks replace minecraft:nether_brick_fence
$setblock ~ ~1 ~ minecraft:spawner{{SpawnData:{{entity:{{id:"$(sp)"}}}}}}
setblock ~2 ~1 ~2 minecraft:chest[facing=north]{{LootTable:"minecraft:chests/nether_bridge"}}
setblock ~-2 ~1 ~-2 minecraft:nether_wart
setblock ~-2 ~ ~-2 minecraft:soul_sand
setblock ~-1 ~1 ~-2 minecraft:nether_wart
setblock ~-1 ~ ~-2 minecraft:soul_sand
particle minecraft:explosion_emitter ~ ~2 ~ 0 0 0 0 1 force
""")
fn("nev/bastion", f"""
$execute store result storage {NS}:d ev.x int 1 run random value $(nix)..$(nix1)
$execute store result storage {NS}:d ev.z int 1 run random value $(niz)..$(niz1)
$data modify storage {NS}:d ev.id set value $(id)
function {NS}:nev/bastion_at with storage {NS}:d ev
""")
fn("nev/bastion_at", f"""
$execute positioned $(x) {NSPAWN_Y-12} $(z) positioned over motion_blocking_no_leaves run function {NS}:nev/bastion_build
$tellraw @a[scores={{cf_plot=$(id)}}] [{{text:"☄ ",color:"gold"}},{{text:"A bastion chunk crashed into your Nether, piglins and all. They trade for gold!",color:"gold"}}]
$execute as @a[scores={{cf_plot=$(id)}}] at @s run playsound minecraft:entity.piglin.celebrate master @s ~ ~ ~ 1 1
""")
fn("nev/bastion_build", f"""
fill ~-3 ~ ~-3 ~3 ~ ~3 minecraft:polished_blackstone_bricks replace minecraft:air
fill ~-3 ~1 ~-3 ~3 ~3 ~3 minecraft:blackstone replace minecraft:air
fill ~-2 ~1 ~-2 ~2 ~3 ~2 minecraft:air replace minecraft:blackstone
fill ~-3 ~1 ~-1 ~-3 ~2 ~1 minecraft:air replace minecraft:blackstone
fill ~3 ~1 ~-1 ~3 ~2 ~1 minecraft:air replace minecraft:blackstone
setblock ~2 ~ ~-2 minecraft:gold_block
setblock ~-2 ~ ~2 minecraft:gilded_blackstone
setblock ~2 ~1 ~2 minecraft:chest[facing=north]{{LootTable:"minecraft:chests/bastion_other"}}
summon minecraft:piglin ~ ~1 ~ {{IsImmuneToZombification:1b,PersistenceRequired:1b}}
summon minecraft:piglin ~1 ~1 ~-1 {{IsImmuneToZombification:1b,PersistenceRequired:1b}}
particle minecraft:explosion_emitter ~ ~2 ~ 0 0 0 0 1 force
""")
fn("p/nbounds_all", f"""
# keep players inside their own Nether plot (staff, creative and spectators are free to roam)
execute as @a[gamemode=survival,tag=!cf_staff] at @s if dimension minecraft:the_nether run function {NS}:p/nbounds
""")
fn("p/nbounds", f"""
execute unless score @s cf_plot matches 1.. run return run execute in minecraft:overworld run tp @s 0.5 {Y+1} 0.5
function {NS}:p/ctx
function {NS}:p/nbounds2 with storage {NS}:d cur
""")
fn("p/nbounds2", f"""
$execute if entity @s[x=$(nx),y=0,z=$(nz),dx={SIZE-1},dy=256,dz={SIZE-1}] run return 0
$execute in minecraft:the_nether positioned $(ncx) {NSPAWN_Y} $(ncz) positioned over motion_blocking run tp @s ~0.5 ~ ~0.5
tellraw @s {{text:"You can't leave your island's Nether.",color:"red"}}
""")

# ---------------------------------------------------------------- islands
fn("plot/create", f"""
# new island for @s
scoreboard players add #next cf_tmp 1
scoreboard players operation @s cf_plot = #next cf_tmp
scoreboard players operation #c cf_tmp = #next cf_tmp
scoreboard players operation #c cf_tmp %= #64 cf_tmp
scoreboard players operation #c cf_tmp *= #grid cf_tmp
scoreboard players add #c cf_tmp 1
scoreboard players operation #r cf_tmp = #next cf_tmp
scoreboard players operation #r cf_tmp /= #64 cf_tmp
scoreboard players operation #r cf_tmp *= #grid cf_tmp
scoreboard players add #r cf_tmp {2 * GRID + 1}
data modify storage {NS}:d new set value {{}}
execute store result storage {NS}:d new.id int 1 run scoreboard players get #next cf_tmp
execute store result storage {NS}:d new.x int 1 run scoreboard players get #c cf_tmp
execute store result storage {NS}:d new.z int 1 run scoreboard players get #r cf_tmp
""" + "\n".join(
    f"scoreboard players operation #o cf_tmp = #{s} cf_tmp\nscoreboard players {'add' if d >= 0 else 'remove'} #o cf_tmp {abs(d)}\n"
    f"execute store result storage {NS}:d new.{k} int 1 run scoreboard players get #o cf_tmp"
    for k, s, d in [("x1", "c", SIZE - 1), ("z1", "r", SIZE - 1), ("wx", "c", -1), ("wz", "r", -1), ("wx1", "c", SIZE), ("wz1", "r", SIZE),
                    ("cx", "c", SIZE // 2), ("cz", "r", SIZE // 2), ("ix", "c", 4), ("iz", "r", 4), ("ix1", "c", SIZE - 5), ("iz1", "r", SIZE - 5)]) + f"""
function {NS}:plot/nfields with storage {NS}:d new
data modify storage {NS}:d new merge from storage {NS}:d nf
data modify storage {NS}:d plots append from storage {NS}:d new
scoreboard players operation #pid cf_tmp = #next cf_tmp
function {NS}:plot/build with storage {NS}:d new
function {NS}:plot/nbuild with storage {NS}:d new
function {NS}:p/home
tellraw @s [{{text:"Welcome to your island! ",color:"gold",bold:1b}},{{text:"Blocks fall from the sky while you or a teammate are online. Watch your head!",color:"yellow",bold:0b}}]
tellraw @s {{text:"Invite friends from the Island Menu (Esc → Island Menu).",color:"gray"}}
""")
fn("plot/build", f"""
$forceload add $(wx) $(wz) $(wx1) $(wz1)
$fill $(x) {FLOOR_Y} $(z) $(x1) {FLOOR_Y} $(z1) minecraft:bedrock
$fill $(wx) -64 $(wz) $(wx1) 319 $(wz) minecraft:barrier
$fill $(wx) -64 $(wz1) $(wx1) 319 $(wz1) minecraft:barrier
$fill $(wx) -64 $(wz) $(wx) 319 $(wz1) minecraft:barrier
$fill $(wx1) -64 $(wz) $(wx1) 319 $(wz1) minecraft:barrier
$fill $(wx) {FLOOR_Y-1} $(wz) $(wx1) {FLOOR_Y-1} $(wz1) minecraft:barrier
$fill $(cx) {FLOOR_Y+1} $(cz) $(cx) {FLOOR_Y+1} $(cz) minecraft:grass_block
""")

# ---------------------------------------------------------------- per-player helpers
fn("p/ctx", f"""
# load @s's island record into storage cur
execute store result storage {NS}:d q.i int 1 run scoreboard players get @s cf_plot
function {NS}:p/ctx2 with storage {NS}:d q
""")
fn("p/ctx2", f"$data modify storage {NS}:d cur set from storage {NS}:d plots[$(i)]")
fn("p/home", f"""
function {NS}:p/ctx
function {NS}:p/home2 with storage {NS}:d cur
""")
fn("p/home2", f"""
$forceload add $(x) $(z) $(x1) $(z1)
$execute in minecraft:overworld positioned $(cx) 318 $(cz) positioned over motion_blocking run tp @s ~0.5 ~ ~0.5
gamemode survival @s
""")
fn("p/respawned", f"""
scoreboard players reset @s cf_die
execute unless score @s cf_plot matches 1.. run return 0
function {NS}:p/ctx
function {NS}:p/respawned2 with storage {NS}:d cur
""")
fn("p/respawned2", f"$execute unless entity @s[x=$(x),y=-64,z=$(z),dx={SIZE-1},dy=400,dz={SIZE-1}] run function {NS}:p/home")
fn("p/bounds_all", f"""
# keep players on their own island (staff, creative and spectators are free to roam)
execute as @a[gamemode=survival,tag=!cf_staff] at @s if dimension minecraft:overworld unless entity @s[x=-14,y={Y-20},z=-14,dx=28,dy=60,dz=28] run function {NS}:p/bounds
""")
fn("p/bounds", f"""
execute unless score @s cf_plot matches 1.. run return run tp @s 0.5 {Y+1} 0.5
function {NS}:p/ctx
function {NS}:p/bounds2 with storage {NS}:d cur
""")
fn("p/bounds2", f"""
$execute if entity @s[x=$(x),y=-64,z=$(z),dx={SIZE-1},dy=400,dz={SIZE-1}] run return 0
function {NS}:p/home
tellraw @s {{text:"You can't leave your island.",color:"red"}}
""")
fn("first_join", f"""
scoreboard players set @s cf_seen 1
tp @s 0.5 {Y+1} 0.5
tellraw @s [{{text:"Welcome to Crispy Falling! ",color:"gold",bold:1b}},{{text:"Click ",color:"yellow",bold:0b}},{{text:"[Start my island]",color:"green",bold:1b,click_event:{{action:"run_command",command:"trigger cf_act set 1"}},hover_event:{{action:"show_text",value:"Create your island and go there"}}}}]
dialog show @s {NS}:menu
""")

# ---------------------------------------------------------------- menu actions
ACTS = {1: "act/home", 2: "act/invite", 3: "act/accept", 4: "act/new", 5: "act/hub", 6: "act/info", 7: "act/menu", 8: "act/hub_help"}
fn("act/dispatch", "\n".join(f"execute if score @s cf_act matches {n} run function {NS}:{f}" for n, f in ACTS.items()) +
   "\nscoreboard players set @s cf_act 0")
fn("act/menu", f"dialog show @s {NS}:menu")
fn("act/home", f"""
execute unless score @s cf_plot matches 1.. run return run function {NS}:plot/create
function {NS}:p/home
""")
fn("act/hub", f"tp @s 0.5 {Y+1} 0.5")
fn("act/invite", f"dialog show @s {NS}:invite")
# run by the crispy_falling mod's /invite <player> as the inviter (the mod checks the player is online)
fn("act/invite_player", f"""
execute unless score @s cf_plot matches 1.. run return run tellraw @s {{text:"Start an island first.",color:"red"}}
tag @s add cf_me
$execute as @a[name="$(name)",tag=!cf_me,limit=1] run function {NS}:act/invite_to
tag @s remove cf_me
""")
fn("act/invite_to", f"""
execute if score @s cf_plot = @a[tag=cf_me,limit=1] cf_plot run return run tellraw @a[tag=cf_me] {{text:"They're already on your island.",color:"yellow"}}
scoreboard players operation @s cf_inv = @a[tag=cf_me,limit=1] cf_plot
tellraw @a[tag=cf_me] [{{text:"Invite sent to ",color:"green"}},{{selector:"@s",color:"gold"}}]
tellraw @s [{{selector:"@a[tag=cf_me]",color:"gold"}},{{text:" invited you to their island. ",color:"green"}},{{text:"[Accept]",color:"aqua",bold:1b,click_event:{{action:"run_command",command:"trigger cf_act set 3"}},hover_event:{{action:"show_text",value:"Join their island (you will leave yours)"}}}}]
""")
fn("act/accept", f"""
execute unless score @s cf_inv matches 1.. run return run tellraw @s {{text:"You have no pending invite.",color:"red"}}
scoreboard players operation @s cf_plot = @s cf_inv
scoreboard players reset @s cf_inv
function {NS}:p/ctx
function {NS}:act/accept2 with storage {NS}:d cur
function {NS}:p/home
""")
fn("act/accept2", f"$tellraw @a[scores={{cf_plot=$(id)}}] [{{selector:\"@s\",color:\"gold\"}},{{text:\" joined the island!\",color:\"green\"}}]")
fn("act/new", f"""
execute if score @s cf_cd matches 1.. run return run tellraw @s [{{text:"You can start a new island again in ",color:"red"}},{{score:{{name:"@s",objective:"cf_cd"}}}},{{text:"s.",color:"red"}}]
clear @s
""" + "\n".join(f"item replace entity @s enderchest.{i} with minecraft:air" for i in range(27)) + f"""
xp set @s 0 levels
xp set @s 0 points
effect clear @s
advancement revoke @s everything
scoreboard players set @s cf_cd 600
function {NS}:plot/create
""")
fn("act/info", f"""
execute unless score @s cf_plot matches 1.. run return run tellraw @s {{text:"You don't have an island yet.",color:"red"}}
function {NS}:p/ctx
function {NS}:act/info2 with storage {NS}:d cur
""")
fn("act/info2", f"""
$scoreboard players operation #m cf_tmp = #p$(id) cf_age
scoreboard players operation #m cf_tmp /= #60 cf_tmp
$tellraw @s [{{text:"Island #$(id)",color:"gold",bold:1b}},{{text:"  play time: ",color:"gray",bold:0b}},{{score:{{name:"#m",objective:"cf_tmp"}},color:"white"}},{{text:" min",color:"gray"}}]
$scoreboard players operation #n cf_tmp = #p$(id) cf_nage
scoreboard players operation #n cf_tmp /= #60 cf_tmp
tellraw @s [{{text:"Time in your Nether: ",color:"gray"}},{{score:{{name:"#n",objective:"cf_tmp"}},color:"white"}},{{text:" min",color:"gray"}}]
$tellraw @s [{{text:"Online members: ",color:"gray"}},{{selector:"@a[scores={{cf_plot=$(id)}}]",color:"green"}}]
tellraw @s {{text:"Dungeons land at 15, 40, 75, 120 and 180 min of play time; the End portal at 150 min.",color:"dark_gray"}}
""")
fn("act/hub_help", f"""
tellraw @s {{text:"— How to play Crispy Falling —",color:"gold",bold:1b}}
tellraw @s {{text:"• Your island is a 50×50 bedrock floor. Blocks fall from the sky while you or a teammate are online.",color:"yellow"}}
tellraw @s {{text:"• Rarer blocks fall less often. Heavy blocks (stone, ores) hurt more than dirt or sand — wear a helmet!",color:"yellow"}}
tellraw @s {{text:"• Animals drop in every few minutes. Dungeons crash in with monsters and loot. An End portal arrives later.",color:"yellow"}}
tellraw @s {{text:"• Build a Nether portal on your island to reach your own void Nether: Nether blocks fall there, fortress wrecks bring blaze spawners.",color:"yellow"}}
tellraw @s {{text:"• Food gets harder to keep up as your island ages. Check the Falling advancements tab for goals.",color:"yellow"}}
tellraw @s {{text:"• Esc → Island Menu: go home, invite a player by name (or /invite <name>), accept invites, start over.",color:"yellow"}}
""")

# ---------------------------------------------------------------- dialogs
def btn(label, cmd=None, tip=None, dialog=None, width=200):
    a = {"type": "minecraft:show_dialog", "dialog": dialog} if dialog else {"type": "minecraft:run_command", "command": cmd}
    b = {"label": label, "action": a, "width": width}
    if tip: b["tooltip"] = {"text": tip}
    return b
js(f"data/{NS}/dialog/menu.json", {
    "type": "minecraft:multi_action", "title": {"text": "Island Menu", "color": "gold", "bold": True},
    "external_title": {"text": "Island Menu"},
    "body": [{"type": "minecraft:plain_message", "contents": {"text": "Blocks fall on your island while you or a teammate are online."}}],
    "actions": [
        btn({"text": "Go to my island", "color": "green"}, "trigger cf_act set 1", "Creates your island the first time"),
        btn({"text": "Invite a player…"}, dialog=f"{NS}:invite", tip="Type their username (or use /invite <name>)"),
        btn({"text": "Accept invite"}, "trigger cf_act set 3"),
        btn({"text": "Island info"}, "trigger cf_act set 6"),
        btn({"text": "Go to hub"}, "trigger cf_act set 5"),
        btn({"text": "How to play"}, "trigger cf_act set 8"),
        btn({"text": "Start a new island…", "color": "red"}, dialog=f"{NS}:confirm_new"),
    ],
    "columns": 2, "exit_action": {"label": {"text": "Close"}, "width": 200},
    "can_close_with_escape": True, "pause": False, "after_action": "close"})
js(f"data/{NS}/dialog/invite.json", {
    "type": "minecraft:notice", "title": {"text": "Invite a player", "color": "gold", "bold": True},
    "body": [{"type": "minecraft:plain_message", "contents": {"text": "They must be online on Crispy Falling. They get an [Accept] button in chat. You can also type /invite <name>."}}],
    "inputs": [{"type": "minecraft:text", "key": "player", "label": {"text": "Username"}, "width": 200, "max_length": 32}],
    "action": {"label": {"text": "Send invite", "color": "green"}, "width": 200,
               "action": {"type": "minecraft:dynamic/run_command", "template": "invite $(player)"}},
    "can_close_with_escape": True, "pause": False, "after_action": "close"})
js(f"data/{NS}/dialog/confirm_new.json", {
    "type": "minecraft:confirmation", "title": {"text": "Start a new island?", "color": "red", "bold": True},
    "body": [{"type": "minecraft:plain_message", "contents": {"text": "You leave your current island (teammates keep it) and your inventory, ender chest, XP and advancements are wiped. You can do this once every 10 minutes."}}],
    "yes": {"label": {"text": "Yes, start over", "color": "red"}, "action": {"type": "minecraft:run_command", "command": "trigger cf_act set 4"}},
    "no": {"label": {"text": "Cancel"}},
    "can_close_with_escape": True, "pause": False, "after_action": "close"})

# ---------------------------------------------------------------- dungeon loot
def e(item, w_, lo=1, hi=1):
    d = {"type": "minecraft:item", "name": f"minecraft:{item}", "weight": w_}
    if hi > 1: d["functions"] = [{"function": "minecraft:set_count", "count": {"type": "minecraft:uniform", "min": lo, "max": hi}}]
    return d
js(f"data/{NS}/loot_table/chests/dungeon.json", {"type": "minecraft:chest", "pools": [
    {"rolls": {"type": "minecraft:uniform", "min": 3, "max": 6}, "entries": [
        e("bread", 10, 1, 4), e("wheat_seeds", 8, 2, 6), e("oak_sapling", 6, 1, 3), e("birch_sapling", 4, 1, 2),
        e("water_bucket", 6), e("lava_bucket", 4), e("bucket", 5), e("iron_ingot", 8, 1, 5), e("gold_ingot", 5, 1, 4),
        e("string", 6, 2, 6), e("bone", 6, 2, 6), e("gunpowder", 5, 1, 4), e("obsidian", 4, 1, 4), e("ender_pearl", 3, 1, 2),
        e("redstone", 5, 2, 8), e("coal", 6, 2, 8), e("name_tag", 2), e("saddle", 2), e("lead", 3), e("nether_wart", 2, 1, 3),
        e("golden_apple", 2), e("diamond", 1, 1, 2), e("sugar_cane", 4, 1, 3), e("cactus", 2), e("cocoa_beans", 2, 1, 3)]},
    {"rolls": 1, "entries": [
        e("cow_spawn_egg", 6), e("pig_spawn_egg", 5), e("sheep_spawn_egg", 6), e("chicken_spawn_egg", 6), e("wolf_spawn_egg", 3),
        e("cat_spawn_egg", 3), e("horse_spawn_egg", 2), e("villager_spawn_egg", 2), e("zombie_villager_spawn_egg", 1),
        e("bee_spawn_egg", 2), {"type": "minecraft:empty", "weight": 10}]}]})

# ---------------------------------------------------------------- advancements tab
ADV = [  # key, parent, icon, title, description, criteria, frame
    ("root", None, "grass_block", "Crispy Falling", "Survive while the sky falls", {"t": {"trigger": "minecraft:tick"}}, "task"),
    ("wood", "root", "oak_log", "Timber!", "Get a log from the sky", {"c": {"trigger": "minecraft:inventory_changed", "conditions": {"items": [{"items": "#minecraft:logs"}]}}}, "task"),
    ("stone", "wood", "cobblestone", "Stone Age", "Collect cobblestone", {"c": {"trigger": "minecraft:inventory_changed", "conditions": {"items": [{"items": "minecraft:cobblestone"}]}}}, "task"),
    ("water", "stone", "water_bucket", "Ice to Meet You", "Fill a bucket with water", {"c": {"trigger": "minecraft:inventory_changed", "conditions": {"items": [{"items": "minecraft:water_bucket"}]}}}, "task"),
    ("bread", "water", "bread", "Bread Winner", "Bake bread from your own wheat", {"c": {"trigger": "minecraft:inventory_changed", "conditions": {"items": [{"items": "minecraft:bread"}]}}}, "task"),
    ("iron", "stone", "iron_ingot", "Iron Rain", "Smelt an iron ingot", {"c": {"trigger": "minecraft:inventory_changed", "conditions": {"items": [{"items": "minecraft:iron_ingot"}]}}}, "task"),
    ("helmet", "iron", "iron_helmet", "Hard Hat", "Make an iron helmet. You'll want it", {"c": {"trigger": "minecraft:inventory_changed", "conditions": {"items": [{"items": "minecraft:iron_helmet"}]}}}, "task"),
    ("diamond", "iron", "diamond", "Lucky Strike", "Find a diamond", {"c": {"trigger": "minecraft:inventory_changed", "conditions": {"items": [{"items": "minecraft:diamond"}]}}}, "goal"),
    ("bed", "wood", "red_bed", "Safe Landing", "Sleep in a bed on your island", {"c": {"trigger": "minecraft:slept_in_bed"}}, "task"),
    ("dungeon", "stone", "mossy_cobblestone", "Crash Site", "Loot a fallen dungeon", {"c": {"trigger": "minecraft:player_generates_container_loot", "conditions": {"loot_table": f"{NS}:chests/dungeon"}}}, "task"),
    ("breed", "wood", "wheat", "Animal Rescue", "Breed two animals", {"c": {"trigger": "minecraft:bred_animals"}}, "task"),
    ("tame", "breed", "bone", "Best Friends", "Tame an animal", {"c": {"trigger": "minecraft:tame_animal"}}, "task"),
    ("trade", "dungeon", "emerald", "Village People", "Trade with a villager", {"c": {"trigger": "minecraft:villager_trade"}}, "task"),
    ("cure", "trade", "golden_apple", "Island Doctor", "Cure a zombie villager", {"c": {"trigger": "minecraft:cured_zombie_villager"}}, "goal"),
    ("nether", "iron", "obsidian", "Into the Fire", "Enter the Nether", {"c": {"trigger": "minecraft:changed_dimension", "conditions": {"to": "minecraft:the_nether"}}}, "task"),
    ("blaze", "nether", "blaze_rod", "Hot Stuff", "Get a blaze rod", {"c": {"trigger": "minecraft:inventory_changed", "conditions": {"items": [{"items": "minecraft:blaze_rod"}]}}}, "task"),
    ("eye", "blaze", "ender_eye", "Eyes on the Sky", "Craft an Eye of Ender", {"c": {"trigger": "minecraft:inventory_changed", "conditions": {"items": [{"items": "minecraft:ender_eye"}]}}}, "task"),
    ("end", "eye", "end_stone", "The End?", "Enter the End through your island's portal", {"c": {"trigger": "minecraft:changed_dimension", "conditions": {"to": "minecraft:the_end"}}}, "goal"),
    ("dragon", "end", "dragon_head", "Sky Fall", "Defeat the Ender Dragon", {"c": {"trigger": "minecraft:player_killed_entity", "conditions": {"entity": [{"condition": "minecraft:entity_properties", "entity": "this", "predicate": {"minecraft:entity_type": "minecraft:ender_dragon"}}]}}}, "challenge"),
    ("elytra", "end", "elytra", "Falling With Style", "Find an Elytra", {"c": {"trigger": "minecraft:inventory_changed", "conditions": {"items": [{"items": "minecraft:elytra"}]}}}, "goal"),
    ("wither", "blaze", "nether_star", "Withered Sky", "Defeat the Wither", {"c": {"trigger": "minecraft:player_killed_entity", "conditions": {"entity": [{"condition": "minecraft:entity_properties", "entity": "this", "predicate": {"minecraft:entity_type": "minecraft:wither"}}]}}}, "challenge"),
    ("beacon", "wither", "beacon", "Lighthouse", "Build a beacon", {"c": {"trigger": "minecraft:construct_beacon"}}, "challenge"),
]
for key, parent, icon, title, desc, crit, frame in ADV:
    d = {"display": {"icon": {"id": f"minecraft:{icon}"}, "title": {"text": title}, "description": {"text": desc}, "frame": frame,
                     "show_toast": key != "root", "announce_to_chat": key != "root", "hidden": False},
         "criteria": crit}
    if parent: d["parent"] = f"{NS}:{parent}"
    else: d["display"]["background"] = "minecraft:gui/advancements/backgrounds/stone"
    js(f"data/{NS}/advancement/{key}.json", d)

print(f"blocks: {len(BLOCKS)} (total weight {btotal}); items: {len(ITEMS)}; animals: {len(ANIMALS)}; advancements: {len(ADV)}")
