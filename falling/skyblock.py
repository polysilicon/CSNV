"""Generate the crispy_skyblock datapack: Skyblock on Falling01 (Fabric 26.2). Players pick one of several themed
starter islands, and the sky still drops the odd supply crate, meteor, animal or dungeon onto it. Challenges trade
items for rewards; the crispy_skyblock mod (mod/) adds the chest menus, island levels and /island top.

Hub at 0,100,0. Islands sit on a 1024-block grid starting at z=2048, each in a 128x128 plot (8x8 chunks) with the
island centred at y=100. Every island also has its own small Nether plot under island/8.

usage: skyblock.py <outdir>   (install as <world>/datapacks/crispy_skyblock; the dimension files make the overworld and
Nether void, which only takes effect when the world is created)"""
import json, os, random, shutil, sys

OUT = sys.argv[1]
NS = "crispy_skyblock"
HUB_Y = 100
SIZE = 128                 # plot is SIZE x SIZE, chunk aligned
GRID = 1024                # spacing between plots
COLS = 64
ISLAND_Y = 100             # top surface of a starter island at its centre
SKY_Y = 300                # where things fall from
NFLOOR_Y = 64              # Nether starter island surface
NSPAWN_Y = 120
R = 6                      # sky events land within R blocks of the island centre

SUPPLY_EVERY = 1500        # seconds of island play time: supply crate every 25 min
METEOR_EVERY = 2700        # meteor every 45 min
ANIMAL_EVERY = 900         # an animal every 15 min
DUNGEON_AGES = [1800, 5400, 10800]   # 30, 90, 180 min
PORTAL_AGE = 9000                    # End portal at 150 min
HOSTILE_CAP = 10
FORTRESS_AGES = [(120, "blaze"), (1200, "blaze"), (3600, "wither_skeleton")]   # seconds spent in the island's Nether
BASTION_AGES = [600, 2400]
NHOSTILE_CAP = 10
NHOSTILES = ["zombified_piglin", "ghast", "magma_cube", "hoglin", "enderman", "skeleton", "strider"]
HOSTILES = ["zombie", "husk", "drowned", "zombie_villager", "skeleton", "stray", "bogged", "spider", "cave_spider", "creeper",
            "enderman", "witch", "slime", "silverfish", "phantom"]
ANIMALS = [(20, "cow"), (20, "pig"), (20, "sheep"), (20, "chicken"), (8, "rabbit"), (4, "horse"), (6, "wolf"), (6, "cat"),
           (4, "goat"), (3, "fox"), (2, "mooshroom"), (3, "turtle")]
METEOR = [(30, "magma_block"), (20, "obsidian"), (25, "coal_ore"), (20, "iron_ore"), (15, "copper_ore"), (8, "gold_ore"),
          (6, "redstone_ore"), (6, "lapis_ore"), (3, "diamond_ore"), (2, "emerald_ore"), (10, "gravel"), (8, "clay")]

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

def snbt(v):
    """Python value -> SNBT (bools as bytes, dict keys quoted only when needed)."""
    if isinstance(v, bool): return "1b" if v else "0b"
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, str): return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list): return "[" + ",".join(snbt(x) for x in v) + "]"
    return "{" + ",".join((k if k.replace("_", "").isalnum() else json.dumps(k)) + ":" + snbt(x) for k, x in v.items()) + "}"
def txt(text, color="white", **kw):
    d = {"text": text, "color": color, "italic": False}
    d.update(kw); return d
def item(id_, name=None, lore=(), glint=None, count=1):
    comp = {}
    if name is not None: comp["minecraft:custom_name"] = name
    if lore: comp["minecraft:lore"] = list(lore)
    if glint is not None: comp["minecraft:enchantment_glint_override"] = glint
    comp["minecraft:tooltip_display"] = {"hidden_components": ["minecraft:attribute_modifiers", "minecraft:enchantments"]}
    return {"id": f"minecraft:{id_}", "count": count, "components": comp}

w("pack.mcmeta", json.dumps({"pack": {"description": "Crispy Skyblock: pick a starter island, the sky still drops gifts",
                                       "min_format": [107, 0], "max_format": [107, 1]}}, indent=2))
js("data/minecraft/tags/function/load.json", {"values": [f"{NS}:load"]})
js("data/minecraft/tags/function/tick.json", {"values": [f"{NS}:tick"]})
js(f"data/{NS}/tags/entity_type/hostile.json", {"values": [f"minecraft:{m}" for m in HOSTILES]})
js(f"data/{NS}/tags/entity_type/nhostile.json", {"values": [f"minecraft:{m}" for m in NHOSTILES]})
js("data/minecraft/tags/dialog/pause_screen_additions.json", {"values": [f"{NS}:menu"]})
js("data/minecraft/tags/dialog/quick_actions.json", {"values": [f"{NS}:menu"]})
# void overworld and Nether (only read when the world is created)
def void_dim(kind, biome):
    return {"type": f"minecraft:{kind}", "generator": {"type": "minecraft:flat", "settings": {
        "biome": f"minecraft:{biome}", "layers": [{"block": "minecraft:air", "height": 1}], "lakes": False, "features": False,
        "structure_overrides": []}}}
js("data/minecraft/dimension/overworld.json", void_dim("overworld", "plains"))
js("data/minecraft/dimension/the_nether.json", void_dim("the_nether", "nether_wastes"))

# ======================================================================= starter islands
class Build:
    """Commands relative to the island centre: (0, 0, 0) is the top surface block at the centre, where players spawn
    on top of. Run as `execute positioned <cx> ISLAND_Y <cz> run function ...`."""
    def __init__(self, seed): self.c = []; self.rnd = random.Random(seed)
    def set(self, x, y, z, block): self.c.append(f"setblock ~{x} ~{y} ~{z} minecraft:{block}")
    def fill(self, x, y, z, x1, y1, z1, block): self.c.append(f"fill ~{x} ~{y} ~{z} ~{x1} ~{y1} ~{z1} minecraft:{block}")
    def disk(self, y, r, block, ox=0, oz=0, jitter=0):
        for dz in range(-int(r), int(r) + 1):
            half = int((r * r - dz * dz) ** 0.5 + 0.35)
            j0 = self.rnd.randint(-jitter, 0) if jitter else 0
            j1 = self.rnd.randint(0, jitter) if jitter else 0
            if half + j0 < 0: continue
            self.fill(ox - half - j0, y, oz + dz, ox + half + j1, y, oz + dz, block)
    def blob(self, r, depth, top, mid, low, ox=0, oz=0):
        """A floating island: surface radius r, tapering down `depth` layers (top / 2 mid layers / low below)."""
        for d in range(depth + 1):
            rr = r * (1 - d / (depth + 1.2)) ** 0.75
            block = top if d == 0 else mid if d <= 2 else low
            self.disk(-d, max(rr, 0.6), block, ox, oz, jitter=1 if 0 < d < depth else 0)
    def oak(self, x, z, h=5, log="oak_log", leaves="oak_leaves", vines=False):
        L = f"{leaves}[persistent=true]"
        for dy in (h - 2, h - 1):
            self.fill(x - 2, dy, z - 2, x + 2, dy, z + 2, L)
            for cx, cz in ((-2, -2), (-2, 2), (2, -2), (2, 2)): self.set(x + cx, dy, z + cz, "air")
        self.fill(x - 1, h, z - 1, x + 1, h, z + 1, L)
        self.set(x, h + 1, z, L)
        self.fill(x, 1, z, x, h - 1, z, log)
        if vines:
            for vx, vz, f in ((x - 3, z, "east"), (x + 3, z, "west"), (x, z - 3, "south"), (x, z + 3, "north")):
                self.fill(vx, h - 4, vz, vx, h - 2, vz, f"vine[{f}=true]")
    def spruce(self, x, z, h=7):
        L = "spruce_leaves[persistent=true]"
        for dy, r in ((h - 4, 2), (h - 3, 1), (h - 2, 2), (h - 1, 1), (h, 1)):
            self.fill(x - r, dy, z - r, x + r, dy, z + r, L)
            if r == 2:
                for cx, cz in ((-2, -2), (-2, 2), (2, -2), (2, 2)): self.set(x + cx, dy, z + cz, "air")
        self.set(x, h + 1, z, L)
        self.fill(x, 1, z, x, h, z, "spruce_log")
    def chest(self, x, y, z, facing, items):
        slots = ",".join("{Slot:%db,id:\"minecraft:%s\",count:%d}" % (i, it, n) for i, (it, n) in enumerate(items))
        self.c.append(f"setblock ~{x} ~{y} ~{z} minecraft:chest[facing={facing}]{{Items:[{slots}]}}")
    def sign(self, x, y, z, facing, lines, wood="oak", color="black"):
        msgs = ",".join(json.dumps(l) for l in (lines + ["", "", "", ""])[:4])
        self.c.append(f"setblock ~{x} ~{y} ~{z} minecraft:{wood}_sign[rotation={facing}]" +
                      "{front_text:{messages:[%s],color:\"%s\",has_glowing_text:1b},is_waxed:1b}" % (msgs, color))
    def summon(self, e, x, y, z, nbt="{PersistenceRequired:1b}"):
        self.c.append(f"summon minecraft:{e} ~{x}.5 ~{y} ~{z}.5 {nbt}")

def classic():
    b = Build(1)
    for y, blk in ((0, "grass_block"), (-1, "dirt"), (-2, "dirt")):
        b.fill(-1, y, -1, 4, y, 1, blk)        # the L: a 6x3 arm ...
        b.fill(-1, y, 2, 1, y, 4, blk)         # ... and a 3x3 arm
    b.fill(-1, -3, -1, 1, -3, 1, "stone")
    b.oak(3, 0)
    b.chest(-1, 1, 3, "east", [("lava_bucket", 1), ("ice", 2), ("melon_slice", 1), ("pumpkin_seeds", 1), ("sugar_cane", 1),
                                ("cactus", 1), ("sand", 2), ("red_mushroom", 1), ("brown_mushroom", 1), ("bone_meal", 3)])
    return b

def desert():
    b = Build(2)
    b.blob(5, 5, "sand", "sandstone", "sandstone")
    b.fill(-1, 0, 3, 0, 0, 3, "water")                     # oasis: two sources = infinite water
    b.fill(-2, 0, 3, -2, 0, 3, "sand")
    b.fill(1, 1, 3, 1, 2, 3, "sugar_cane")
    b.fill(1, 0, 3, 1, 0, 3, "sand")
    b.fill(3, 1, -2, 3, 3, -2, "cactus")
    b.set(-3, 1, -1, "dead_bush")
    b.set(2, 1, 1, "dead_bush")
    b.fill(-2, -1, -3, -1, -1, -2, "dirt")                 # a few dirt blocks to dig for
    b.chest(-3, 1, 1, "east", [("lava_bucket", 1), ("ice", 1), ("dirt", 4), ("oak_sapling", 2), ("wheat_seeds", 2), ("bone_meal", 4)])
    return b

def jungle():
    b = Build(3)
    b.blob(5, 5, "grass_block", "dirt", "stone")
    x, z, h = 2, -2, 8
    b.oak(x, z, h, "jungle_log", "jungle_leaves")
    for dy, (cx, cz, f) in ((3, (x + 1, z, "west")), (4, (x, z + 1, "north")), (2, (x - 1, z, "east"))):
        b.set(cx, dy, cz, f"cocoa[facing={f},age=2]")
    b.fill(-3, 1, 2, -3, 4, 2, "bamboo")
    b.fill(-2, 1, 3, -2, 3, 3, "bamboo")
    b.set(3, 1, 2, "melon")
    b.chest(-2, 1, -2, "south", [("lava_bucket", 1), ("ice", 2), ("wheat_seeds", 2), ("bone_meal", 3), ("melon_seeds", 1)])
    return b

def snowy():
    b = Build(4)
    b.blob(5, 5, "grass_block[snowy=true]", "dirt", "stone")
    b.disk(1, 4.6, "snow")
    b.spruce(2, -2, 7)
    b.fill(-2, 0, 2, -1, 0, 2, "ice")                         # frozen pond
    b.fill(-2, 1, 2, -1, 1, 2, "air")
    b.set(-3, 1, -1, "sweet_berry_bush[age=3]")
    b.set(0, 1, 0, "air")
    b.chest(-3, 1, 1, "east", [("lava_bucket", 1), ("ice", 1), ("sweet_berries", 2), ("wheat_seeds", 1), ("bone_meal", 2),
                               ("snowball", 4)])
    return b

def mushroom():
    b = Build(5)
    b.blob(4, 4, "mycelium", "dirt", "stone")
    x, z = 2, -1
    b.fill(x, 1, z, x, 4, z, "mushroom_stem")
    b.fill(x - 2, 5, z - 2, x + 2, 5, z + 2, "red_mushroom_block")
    b.fill(x - 1, 6, z - 1, x + 1, 6, z + 1, "red_mushroom_block")
    b.fill(x - 2, 4, z - 2, x - 2, 4, z + 2, "red_mushroom_block")
    b.fill(x + 2, 4, z - 2, x + 2, 4, z + 2, "red_mushroom_block")
    b.fill(x - 1, 4, z - 2, x + 1, 4, z - 2, "red_mushroom_block")
    b.fill(x - 1, 4, z + 2, x + 1, 4, z + 2, "red_mushroom_block")
    b.set(-1, 1, 2, "brown_mushroom")
    b.set(-2, 1, -2, "red_mushroom")
    # a little pen for the mooshroom
    b.fill(-3, 1, 0, -1, 1, 2, "oak_fence")
    b.fill(-2, 1, 1, -2, 1, 1, "air")
    b.summon("mooshroom", -2, 1, 1)
    b.chest(1, 1, 2, "north", [("lava_bucket", 1), ("ice", 2), ("dirt", 4), ("oak_sapling", 2), ("wheat_seeds", 1),
                               ("bowl", 1), ("bone_meal", 3)])
    return b

def swamp():
    b = Build(6)
    b.blob(5, 4, "grass_block", "mud", "dirt")
    b.fill(-3, 0, 1, -2, 0, 2, "water")                       # pond, lily pads on top
    b.set(-3, 1, 1, "lily_pad")
    b.set(-2, 1, 2, "lily_pad")
    b.fill(-1, 0, 3, 0, 0, 3, "mud")
    b.oak(2, -2, 5, vines=True)
    # Shrek's outhouse
    b.fill(2, 1, 1, 3, 3, 3, "spruce_planks")
    b.fill(2, 4, 1, 3, 4, 3, "spruce_slab")
    b.fill(2, 1, 2, 2, 2, 2, "air")
    b.set(2, 1, 1, "spruce_door[facing=north,half=lower]")
    b.set(2, 2, 1, "spruce_door[facing=north,half=upper]")
    b.sign(-1, 1, -3, 8, ["SHREK'S", "SWAMP", "", "KEEP OUT!"], "spruce", "green")
    b.chest(-3, 1, -1, "east", [("lava_bucket", 1), ("ice", 1), ("wheat_seeds", 2), ("carrot", 1), ("oak_sapling", 1), ("bone_meal", 2)])
    return b

def tegridy():
    b = Build(7)
    b.blob(6, 5, "grass_block", "dirt", "stone")
    for zz in (-4, -3, -1, 0):                               # crop rows either side of a water channel
        b.fill(-4, 0, zz, -1, 0, zz, "farmland[moisture=7]")
        b.fill(-4, 1, zz, -1, 1, zz, "wheat[age=7]" if zz < -2 else "carrots[age=7]" if zz == -1 else "potatoes[age=7]")
    b.fill(-4, 0, -2, -1, 0, -2, "water")
    # barn
    b.fill(2, 1, 1, 5, 3, 4, "red_terracotta")
    b.fill(3, 1, 2, 4, 2, 3, "air")
    b.fill(2, 4, 1, 5, 4, 4, "dark_oak_slab")
    b.fill(3, 1, 1, 3, 2, 1, "air")
    b.set(4, 1, 3, "hay_block")
    b.set(4, 2, 3, "hay_block")
    b.oak(3, -3, 4)
    # scarecrow
    b.set(-2, 1, 2, "oak_fence")
    b.set(-2, 2, 2, "hay_block")
    b.set(-2, 3, 2, "carved_pumpkin[facing=south]")
    b.sign(0, 1, 4, 0, ["TEGRIDY", "FARMS", "", "est. by you"], "oak", "green")
    b.chest(1, 1, -1, "west", [("lava_bucket", 1), ("ice", 1), ("wheat_seeds", 4), ("carrot", 2), ("potato", 2), ("bone_meal", 4), ("oak_sapling", 1)])
    return b

# key, builder, biome, menu icon, name, colour, lore lines
ISLANDS = [
    ("classic", classic, "plains", "grass_block", "Classic", "green",
     ["The original: an L of dirt, one tree", "and a chest. No frills, all skill."], "Normal"),
    ("desert", desert, "desert", "sand", "Desert Oasis", "yellow",
     ["Sand, cactus and a tiny oasis.", "It never rains here. Bring your own dirt."], "Hard"),
    ("jungle", jungle, "jungle", "jungle_log", "Jungle", "dark_green",
     ["A tall jungle tree with cocoa,", "bamboo and a melon. Wood for days."], "Easy"),
    ("snowy", snowy, "snowy_taiga", "snow_block", "Frozen Peak", "aqua",
     ["Spruce, snow and a frozen pond.", "Water is easy; food is not."], "Normal"),
    ("mushroom", mushroom, "mushroom_fields", "red_mushroom_block", "Mushroom Isle", "light_purple",
     ["Mycelium, a giant mushroom and a", "mooshroom. No monsters spawn here."], "Easy"),
    ("swamp", swamp, "swamp", "lily_pad", "Shrek's Swamp", "dark_green",
     ["Mud, lily pads and an outhouse.", "Slimes come out at night. Get out of my swamp!"], "Normal"),
    ("tegridy", tegridy, "plains", "hay_block", "Tegridy Farms", "gold",
     ["Ready-to-harvest crops, a barn and", "a scarecrow. Farming with tegridy."], "Easy"),
]
for key, builder, *_ in ISLANDS:
    fn(f"island/{key}", "\n".join(builder().c))
# biome for the whole plot, one layer per call (128x128 = the most one fillbiome may change)
fn("island/biome", "\n".join(f"$fillbiome $(x) {y} $(z) $(x1) {y} $(z1) minecraft:$(b)" for y in range(ISLAND_Y - 48, ISLAND_Y + 80)))

# ======================================================================= challenges
# key, name, icon, needs [(item, n)] or ("level", n), rewards [(item, n)], xp levels, tier
CH = [
    ("cobble", "Cobble Collector", "cobblestone", [("cobblestone", 64)], [("dirt", 8)], 2, "Easy"),
    ("logs", "Lumberjack", "oak_log", [("oak_log", 32)], [("birch_sapling", 1), ("spruce_sapling", 1), ("acacia_sapling", 1), ("cherry_sapling", 1)], 2, "Easy"),
    ("wheat", "Green Thumb", "wheat", [("wheat", 16)], [("carrot", 2), ("potato", 2)], 2, "Easy"),
    ("cane", "Paper Trail", "sugar_cane", [("sugar_cane", 32)], [("clay_ball", 8), ("sand", 8)], 2, "Easy"),
    ("cactus", "Prickly", "cactus", [("cactus", 16)], [("sand", 16)], 2, "Easy"),
    ("stone", "Stone Age", "stone", [("stone", 64)], [("iron_ingot", 4)], 3, "Easy"),
    ("charcoal", "Charcoal Burner", "charcoal", [("charcoal", 16)], [("gravel", 16)], 3, "Easy"),
    ("bread", "Baker", "bread", [("bread", 16)], [("cow_spawn_egg", 2)], 4, "Easy"),
    ("melon", "Melon Lord", "melon_slice", [("melon_slice", 32)], [("pig_spawn_egg", 2)], 4, "Easy"),
    ("bones", "Bone Collector", "bone", [("bone", 32)], [("sheep_spawn_egg", 2)], 4, "Medium"),
    ("flesh", "Rotten Deal", "rotten_flesh", [("rotten_flesh", 48)], [("chicken_spawn_egg", 2), ("leather", 4)], 4, "Medium"),
    ("string", "Spider Silk", "string", [("string", 32)], [("wolf_spawn_egg", 1), ("cat_spawn_egg", 1)], 4, "Medium"),
    ("wool", "Wool Gatherer", "white_wool", [("white_wool", 32)], [("lapis_lazuli", 16), ("redstone", 16)], 5, "Medium"),
    ("glass", "Glassblower", "glass", [("glass", 64)], [("dirt", 16), ("grass_block", 4)], 5, "Medium"),
    ("iron", "Ironworker", "iron_ingot", [("iron_ingot", 32)], [("diamond", 1), ("gold_ingot", 8)], 6, "Medium"),
    ("powder", "Boom Boom", "gunpowder", [("gunpowder", 32)], [("lava_bucket", 1), ("obsidian", 4)], 6, "Medium"),
    ("market", "Farmers Market", "carrot", [("carrot", 64), ("potato", 64)], [("villager_spawn_egg", 2)], 8, "Medium"),
    ("bricks", "Brickworks", "bricks", [("brick", 64)], [("red_sand", 16), ("emerald", 4)], 6, "Medium"),
    ("nether", "Into the Fire", "netherrack", [("netherrack", 64)], [("quartz", 16), ("soul_sand", 8)], 6, "Hard"),
    ("wart", "Wart Farmer", "nether_wart", [("nether_wart", 32)], [("blaze_rod", 2), ("ghast_tear", 1)], 8, "Hard"),
    ("pearls", "Pearl Diver", "ender_pearl", [("ender_pearl", 16)], [("ender_eye", 4)], 8, "Hard"),
    ("gold", "Gold Rush", "gold_block", [("gold_block", 16)], [("ancient_debris", 2)], 10, "Hard"),
    ("diamonds", "Diamond Hands", "diamond", [("diamond", 16)], [("netherite_upgrade_smithing_template", 1), ("ancient_debris", 2)], 15, "Hard"),
    ("lvl10", "Growing Island", "oak_sapling", ("level", 10), [("diamond", 3)], 5, "Level"),
    ("lvl50", "Sky Town", "bell", ("level", 50), [("totem_of_undying", 1), ("diamond", 5)], 10, "Level"),
    ("lvl150", "Floating Empire", "elytra", ("level", 150), [("elytra", 1)], 20, "Level"),
]
TIER_COL = {"Easy": "green", "Medium": "yellow", "Hard": "red", "Level": "light_purple"}
def nice(it): return it.replace("_spawn_egg", " spawn egg").replace("_", " ")
for i, (key, name, icon, needs, rewards, xp, tier) in enumerate(CH):
    obj = f"cs_c{i}"
    lines = [f"execute if score @s {obj} matches 1.. run return run tellraw @s {{text:\"You already finished {name}.\",color:\"yellow\"}}"]
    if needs[0] == "level":
        lines.append(f"execute unless score @s cs_lvl matches {needs[1]}.. run return run tellraw @s [{{text:\"{name} needs island level {needs[1]}. \",color:\"red\"}},{{text:\"Check yours with /island level.\",color:\"gray\"}}]")
    else:
        for it, n in needs:
            lines.append(f"execute store result score #h cs_tmp run clear @s minecraft:{it} 0")
            lines.append(f"execute if score #h cs_tmp matches ..{n - 1} run return run tellraw @s [{{text:\"{name} needs {n} {nice(it)} \",color:\"red\"}},{{text:\"(you have \",color:\"gray\"}},{{score:{{name:\"#h\",objective:\"cs_tmp\"}},color:\"gray\"}},{{text:\").\",color:\"gray\"}}]")
        lines += [f"clear @s minecraft:{it} {n}" for it, n in needs]
    lines += [f"give @s minecraft:{it} {n}" for it, n in rewards]
    lines += [f"xp add @s {xp} levels", f"scoreboard players set @s {obj} 1",
              f"tellraw @a [{{selector:\"@s\",color:\"gold\"}},{{text:\" completed the challenge \",color:\"gray\"}},{{text:\"{name}\",color:\"{TIER_COL[tier]}\"}}]",
              "playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 0.8 1",
              f"function {NS}:ch/reopen"]
    fn(f"ch/{key}", "\n".join(lines))
fn("ch/reopen", "execute as @s run island challenges")

# ======================================================================= economy and minions (read by the crispy_skyblock mod)
# Shop: per category, (item, buy price, sell price) in coins; 0 = can't buy / can't sell at the merchant.
SHOP = [
    ("farming", "Farming", "golden_hoe", "Farm Merchant", [
        ("wheat", 0, 2), ("wheat_seeds", 5, 0), ("carrot", 8, 1), ("potato", 8, 1), ("beetroot", 0, 1), ("beetroot_seeds", 6, 0),
        ("sugar_cane", 10, 2), ("cactus", 10, 1), ("melon_slice", 0, 1), ("melon_seeds", 20, 0), ("pumpkin", 0, 4),
        ("pumpkin_seeds", 20, 0), ("cocoa_beans", 10, 1), ("sweet_berries", 10, 1), ("nether_wart", 30, 2), ("egg", 0, 1),
        ("bone_meal", 6, 0), ("brown_mushroom", 15, 1), ("red_mushroom", 15, 1), ("hay_block", 0, 18)]),
    ("mining", "Mining", "iron_pickaxe", "Mine Merchant", [
        ("cobblestone", 3, 1), ("stone", 0, 2), ("coal", 0, 2), ("raw_iron", 0, 3), ("iron_ingot", 12, 3), ("raw_gold", 0, 4),
        ("gold_ingot", 16, 4), ("diamond", 0, 8), ("lapis_lazuli", 0, 1), ("redstone", 0, 1), ("emerald", 0, 6),
        ("raw_copper", 0, 1), ("copper_ingot", 0, 2), ("quartz", 0, 2), ("obsidian", 0, 5), ("netherrack", 0, 1),
        ("glowstone_dust", 0, 2), ("amethyst_shard", 0, 3)]),
    ("foraging", "Foraging", "iron_axe", "Lumber Merchant", [
        ("oak_log", 0, 2), ("birch_log", 0, 2), ("spruce_log", 0, 2), ("jungle_log", 0, 2), ("acacia_log", 0, 2),
        ("dark_oak_log", 0, 2), ("cherry_log", 0, 2), ("mangrove_log", 0, 2), ("oak_sapling", 15, 0), ("birch_sapling", 15, 0),
        ("spruce_sapling", 15, 0), ("jungle_sapling", 15, 0), ("acacia_sapling", 15, 0), ("dark_oak_sapling", 15, 0),
        ("cherry_sapling", 25, 0), ("mangrove_propagule", 25, 0), ("apple", 0, 2), ("stick", 0, 0)]),
    ("combat", "Combat", "iron_sword", "Monster Hunter", [
        ("rotten_flesh", 0, 1), ("bone", 0, 1), ("arrow", 2, 1), ("string", 0, 1), ("spider_eye", 0, 2), ("gunpowder", 0, 3),
        ("ender_pearl", 0, 7), ("slime_ball", 0, 3), ("blaze_rod", 0, 9), ("ghast_tear", 0, 15), ("magma_cream", 0, 4),
        ("phantom_membrane", 0, 5), ("chicken", 0, 2), ("feather", 0, 1), ("beef", 0, 2), ("leather", 0, 2), ("mutton", 0, 2),
        ("white_wool", 6, 2), ("porkchop", 0, 2), ("rabbit_hide", 0, 2)]),
    ("supplies", "Builder & Supplies", "bricks", "Builder", [
        ("dirt", 10, 0), ("grass_block", 20, 0), ("sand", 8, 2), ("red_sand", 10, 2), ("gravel", 8, 2), ("clay_ball", 6, 2),
        ("glass", 6, 0), ("ice", 20, 0), ("lava_bucket", 200, 0), ("water_bucket", 60, 0), ("torch", 2, 0), ("oak_planks", 2, 0),
        ("stone_bricks", 4, 0), ("bricks", 6, 0), ("lantern", 20, 0), ("chest", 15, 0), ("hopper", 120, 0),
        ("cow_spawn_egg", 500, 0), ("pig_spawn_egg", 500, 0), ("sheep_spawn_egg", 500, 0), ("chicken_spawn_egg", 300, 0)]),
]
# Minions: key, name, head (block/item on its head), tool, leather colour, drops per action [(item, n)], recipe item
MINIONS = [
    ("cobblestone", "Cobblestone", "cobblestone", "wooden_pickaxe", 0x8A8A8A, [("cobblestone", 1)], "cobblestone"),
    ("coal", "Coal", "coal_ore", "stone_pickaxe", 0x303030, [("coal", 1)], "coal"),
    ("iron", "Iron", "iron_ore", "stone_pickaxe", 0xD8AF93, [("raw_iron", 1)], "iron_ingot"),
    ("gold", "Gold", "gold_ore", "iron_pickaxe", 0xF5CC27, [("raw_gold", 1)], "gold_ingot"),
    ("diamond", "Diamond", "diamond_ore", "iron_pickaxe", 0x4AEDD9, [("diamond", 1)], "diamond"),
    ("lapis", "Lapis", "lapis_ore", "stone_pickaxe", 0x1E3FAD, [("lapis_lazuli", 2)], "lapis_lazuli"),
    ("redstone", "Redstone", "redstone_ore", "iron_pickaxe", 0xB01010, [("redstone", 2)], "redstone"),
    ("sand", "Sand", "sand", "wooden_shovel", 0xDBCFA3, [("sand", 1)], "sand"),
    ("clay", "Clay", "clay", "wooden_shovel", 0xA0A6B4, [("clay_ball", 2)], "clay_ball"),
    ("wheat", "Wheat", "hay_block", "wooden_hoe", 0xDCBB5A, [("wheat", 1), ("wheat_seeds", 1)], "wheat"),
    ("carrot", "Carrot", "carrot", "wooden_hoe", 0xF08A1E, [("carrot", 2)], "carrot"),
    ("potato", "Potato", "potato", "wooden_hoe", 0xC8A44E, [("potato", 2)], "potato"),
    ("cane", "Sugar Cane", "sugar_cane", "wooden_hoe", 0x8DBA54, [("sugar_cane", 1)], "sugar_cane"),
    ("melon", "Melon", "melon", "wooden_hoe", 0x6E9A2A, [("melon_slice", 3)], "melon_slice"),
    ("pumpkin", "Pumpkin", "pumpkin", "wooden_hoe", 0xE38A1D, [("pumpkin", 1)], "pumpkin"),
    ("oak", "Oak", "oak_log", "wooden_axe", 0x6B5434, [("oak_log", 1)], "oak_log"),
    ("birch", "Birch", "birch_log", "wooden_axe", 0xD7CB8D, [("birch_log", 1)], "birch_log"),
    ("chicken", "Chicken", "white_wool", "wooden_sword", 0xF0F0F0, [("chicken", 1), ("feather", 1)], "chicken"),
    ("cow", "Cow", "brown_mushroom_block", "wooden_sword", 0x443626, [("beef", 1), ("leather", 1)], "beef"),
    ("sheep", "Sheep", "white_wool", "shears", 0xE9ECEC, [("white_wool", 1), ("mutton", 1)], "white_wool"),
    ("zombie", "Zombie", "zombie_head", "wooden_sword", 0x426E35, [("rotten_flesh", 1)], "rotten_flesh"),
    ("skeleton", "Skeleton", "skeleton_skull", "bow", 0xBCBCBC, [("bone", 1), ("arrow", 1)], "bone"),
    ("spider", "Spider", "cobweb", "wooden_sword", 0x332A23, [("string", 1), ("spider_eye", 1)], "string"),
]
ROMAN = ["", "I", "II", "III", "IV", "V"]
# seconds per action, storage (items), upgrade cost from the tier below (coins, items of the minion's recipe item)
TIERS = [(30, 64, 0, 0), (25, 128, 500, 64), (20, 192, 2000, 160), (15, 256, 8000, 320), (10, 384, 25000, 640)]
MINION_BASE_LIMIT, MINION_MAX_LIMIT, LEVELS_PER_MINION = 5, 15, 20
ECO = {
    "shop": [{"key": k, "name": n, "icon": f"minecraft:{ic}", "npc": npc,
              "items": [{"id": f"minecraft:{i}", "buy": b, "sell": sv} for i, b, sv in items]} for k, n, ic, npc, items in SHOP],
    "minions": [{"key": k, "name": n, "head": f"minecraft:{h}", "tool": f"minecraft:{t}", "color": c, "recipe": f"minecraft:{r}",
                 "drops": [{"id": f"minecraft:{i}", "n": q} for i, q in d]} for k, n, h, t, c, d, r in MINIONS],
    "tiers": [{"secs": a, "cap": b, "coins": c, "items": d} for a, b, c, d in TIERS],
    "limit": {"base": MINION_BASE_LIMIT, "max": MINION_MAX_LIMIT, "per_levels": LEVELS_PER_MINION},
}
def minion_item(key, name, head, tier=1):
    return {"id": "minecraft:armor_stand", "count": 1, "components": {
        "minecraft:custom_name": txt(f"{name} Minion {ROMAN[tier]}", "aqua", bold=True),
        "minecraft:lore": [txt("Place it on your island. It gathers", "gray"), txt(f"{name.lower()} on its own, even while", "gray"),
                           txt("you're offline, until its storage is full.", "gray"), txt(""),
                           txt(f"Tier {ROMAN[tier]}: one action every {TIERS[tier - 1][0]}s, holds {TIERS[tier - 1][1]}", "dark_aqua"),
                           txt("Right-click it to collect or upgrade.", "yellow")],
        "minecraft:item_model": f"minecraft:{head}",
        "minecraft:enchantment_glint_override": True,
        "minecraft:max_stack_size": 1,
        "minecraft:custom_data": {"cs_minion": {"type": key, "tier": tier}}}}
for k, n, h, t, c, d, r in MINIONS:
    tool_ing = "minecraft:wooden_pickaxe"
    js(f"data/{NS}/recipe/minion_{k}.json", {"type": "minecraft:crafting_shaped", "category": "misc", "group": "crispy_minion",
        "pattern": ["###", "#P#", "###"], "key": {"#": f"minecraft:{r}", "P": tool_ing}, "result": minion_item(k, n, h)})

# ======================================================================= menus (read by the crispy_skyblock mod)
GRID_SLOTS = [10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 37, 38, 39, 40, 41, 42, 43]
DIFF_COL = {"Easy": "green", "Normal": "yellow", "Hard": "red"}
isl_items = []
for n, (key, _, biome, icon, name, col, lore, diff) in enumerate(ISLANDS):
    slot = [10, 12, 14, 16, 29, 31, 33][n]
    isl_items.append({"slot": slot, "cmd": f"trigger cs_act set {101 + n}", "item": item(icon, txt(name, col, bold=True),
        [txt(l, "gray") for l in lore] + [txt(""), txt("Difficulty: ", "gray", extra=[txt(diff, DIFF_COL[diff])]),
                                         txt("Biome: " + biome.replace("_", " ").title(), "dark_gray"), txt(""), txt("Click to start here", "yellow")])})
ch_items = []
for i, (key, name, icon, needs, rewards, xp, tier) in enumerate(CH):
    need_l = ([txt(f"Island level {needs[1]}", "white")] if needs[0] == "level" else
              [txt(f"{n} {nice(it)}", "white") for it, n in needs])
    body = ([txt(tier, TIER_COL[tier]), txt(""), txt("Needs:", "gray")] + [txt("• ", "dark_gray", extra=[l]) for l in need_l] +
            [txt("Reward:", "gray")] + [txt("• ", "dark_gray", extra=[txt(f"{n} {nice(it)}", "aqua")]) for it, n in rewards] +
            [txt("• ", "dark_gray", extra=[txt(f"{xp} XP levels", "aqua")]), txt("")])
    ch_items.append({"slot": GRID_SLOTS[i], "cmd": f"trigger cs_act set {200 + i}", "done": f"cs_c{i}",
                     "item": item(icon, txt(name, TIER_COL[tier], bold=True), body + [txt("Click to hand in", "yellow")]),
                     "item_done": item(icon, txt(name + " ✔", "dark_gray", bold=True, strikethrough=True), body + [txt("Completed", "green")], True)})
MENUS = {
    "islands": {"title": txt("Pick your starter island", "dark_gray"), "rows": 5, "fill": item("black_stained_glass_pane", txt("")),
                "items": isl_items},
    "challenges": {"title": txt("Challenges", "dark_gray"), "rows": 6, "fill": item("black_stained_glass_pane", txt("")),
                   "items": ch_items + [{"slot": 49, "cmd": "trigger cs_act set 7", "item": item("arrow", txt("Island Menu", "gray"))}]},
}

# ======================================================================= load / setup
CH_OBJS = "\n".join(f"scoreboard objectives add cs_c{i} dummy" for i in range(len(CH)))
fn("load", f"""
scoreboard objectives add cs_plot dummy
scoreboard objectives add cs_act trigger
scoreboard objectives add cs_inv dummy
scoreboard objectives add cs_on dummy
scoreboard objectives add cs_was dummy
scoreboard objectives add cs_age dummy
scoreboard objectives add cs_tmp dummy
scoreboard objectives add cs_cd dummy
scoreboard objectives add cs_seen dummy
scoreboard objectives add cs_die deathCount
scoreboard objectives add cs_cfg dummy
scoreboard objectives add cs_non dummy
scoreboard objectives add cs_nwas dummy
scoreboard objectives add cs_nage dummy
scoreboard objectives add cs_npend dummy
scoreboard objectives add cs_lvl dummy
scoreboard objectives add cs_coins dummy
{CH_OBJS}
function {NS}:boss/objectives
scoreboard players set #8 cs_tmp 8
scoreboard players set #64 cs_tmp {COLS}
scoreboard players set #grid cs_tmp {GRID}
scoreboard players set #60 cs_tmp 60
data modify storage {NS}:menus islands set value {snbt(MENUS["islands"])}
data modify storage {NS}:menus challenges set value {snbt(MENUS["challenges"])}
data modify storage {NS}:eco cfg set value {snbt(ECO)}
execute unless score #hubv cs_cfg matches 2.. run function {NS}:hub
execute if score #hubv cs_cfg matches 2 run function {NS}:hub_v3
# respawn the merchants once the hub's entities are loaded (at startup they load after this runs)
schedule function {NS}:npcs 100t replace
execute unless data storage {NS}:d plots run function {NS}:setup
gamerule minecraft:respawn_radius 0
gamerule minecraft:keep_inventory false
""")
fn("setup", f"""
# first load in a new world only
data modify storage {NS}:d plots set value [{{id:0}}]
scoreboard players set #next cs_tmp 0
function {NS}:hub
""")

# ======================================================================= hub
def hsign(lines, color="black"):
    return "{front_text:{messages:[%s],color:\"%s\",has_glowing_text:1b},is_waxed:1b}" % (",".join(json.dumps(l) for l in lines), color)
def label(x, y, z, text, scale=1.5, yaw=0, bill="fixed", tag=None):
    tags = [NS] + ([tag] if tag else [])
    return (f"summon minecraft:text_display {x} {y} {z} " +
            "{Tags:%s,billboard:\"%s\",Rotation:[%sf,0f],text:%s,background:1073741824,shadow:1b,line_width:400,"
            "transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[%sf,%sf,%sf]}}"
            % (json.dumps(tags), bill, yaw, text, scale, scale, scale))
Y = HUB_Y
HUB_R = 50                       # the hub area (adventure mode, no island bounds) is |x|,|z| <= HUB_R
HUB_SPAWN = (0.5, Y + 1, 5.5)    # facing north, towards the island portal
PORTAL_DZ = -14                  # every island's hub portal: 14 blocks north of the island centre, over the void
HUB_PORTAL_Z = -18               # the hub's portal home, north of the plaza

def _hash(ix, iz, seed):
    h = (ix * 374761393 + iz * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0
def noise(x, z, seed):
    """Smooth value noise in [0, 1]."""
    ix, iz = int(x // 1), int(z // 1)
    fx, fz = x - ix, z - iz
    sx, sz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    a, b = _hash(ix, iz, seed), _hash(ix + 1, iz, seed)
    c, d = _hash(ix, iz + 1, seed), _hash(ix + 1, iz + 1, seed)
    return (a + (b - a) * sx) + ((c + (d - c) * sx) - (a + (b - a) * sx)) * sz

def hub_build():
    """A big natural floating island: grassy hills around a flat plaza with a fountain, market stalls for the merchants,
    the portal to your island to the north, a pond, trees, flowers and a rocky underside."""
    import math
    rnd = random.Random(42)
    c = ["forceload add -64 -64 63 63", f"kill @e[type=minecraft:text_display,tag={NS},x=-64,y=0,z=-64,dx=128,dy=320,dz=128]"]
    c += [f"fill -{HUB_R} {y} -{HUB_R} {HUB_R} {y} {HUB_R} minecraft:air" for y in range(Y - 40, Y + 21)]
    top, edge = {}, {}
    pond = (-24, 16, 5.2)
    for x in range(-HUB_R + 2, HUB_R - 1):
        for z in range(-HUB_R + 2, HUB_R - 1):
            r = math.hypot(x, z)
            lim = 37 + 9 * noise(x * 0.05 + 7, z * 0.05 + 3, 1)
            if r > lim: continue
            inner = max(0.0, min(1.0, (r - 16) / 7)) * max(0.0, min(1.0, (lim - r) / 5))
            h = int(round(5 * noise(x * 0.07, z * 0.07, 2) * inner))
            if math.hypot(x - pond[0], z - pond[1]) < pond[2] + 2: h = 0
            depth = int(3 + 27 * (1 - r / lim) ** 0.9 + 5 * noise(x * 0.15, z * 0.15, 3))
            t = Y + h
            top[(x, z)] = t
            c.append(f"fill {x} {t - depth} {z} {x} {t - 4} {z} minecraft:stone")
            c.append(f"fill {x} {t - 3} {z} {x} {t - 1} {z} minecraft:dirt")
            c.append(f"setblock {x} {t} {z} minecraft:grass_block")
            under = rnd.choice(["stone", "stone", "andesite", "cobblestone", "tuff", "mossy_cobblestone", "coal_ore", "iron_ore", "copper_ore"])
            c.append(f"setblock {x} {t - depth} {z} minecraft:{under}")
    def surf(x, z, block):
        if (x, z) in top: c.append(f"setblock {x} {top[(x, z)]} {z} minecraft:{block}")
    used = set()
    # pond with a sandy shore
    for (x, z), t in top.items():
        d = math.hypot(x - pond[0], z - pond[1])
        if d <= pond[2]:
            c += [f"setblock {x} {t} {z} minecraft:water", f"setblock {x} {t - 1} {z} minecraft:water", f"setblock {x} {t - 2} {z} minecraft:sand"]
            used.add((x, z))
        elif d <= pond[2] + 1.3:
            surf(x, z, "sand"); used.add((x, z))
    for _ in range(5):
        a = rnd.random() * 6.28; rr = rnd.random() * (pond[2] - 1)
        px, pz = int(pond[0] + rr * math.cos(a)), int(pond[1] + rr * math.sin(a))
        if (px, pz) in top: c.append(f"setblock {px} {top[(px, pz)] + 1} {pz} minecraft:lily_pad")
    # plaza: polished andesite with a stone brick ring
    for (x, z) in top:
        r = math.hypot(x, z)
        if r <= 8.5: surf(x, z, "polished_andesite"); used.add((x, z))
        elif r <= 9.6: surf(x, z, "stone_bricks"); used.add((x, z))
    # paths: north to the portal, east and west to the stalls, south past spawn, and four out into the hills
    def path(points, width=1, block="dirt_path"):
        for (ax, az), (bx, bz) in zip(points, points[1:]):
            n = max(abs(bx - ax), abs(bz - az))
            for i in range(n + 1):
                x, z = round(ax + (bx - ax) * i / n), round(az + (bz - az) * i / n)
                for dx in range(-width, width + 1):
                    for dz in range(-width, width + 1):
                        if (x + dx, z + dz) in top and (x + dx, z + dz) not in used:
                            surf(x + dx, z + dz, block); used.add((x + dx, z + dz))
    path([(0, -9), (0, HUB_PORTAL_Z + 1)], 1, "stone_bricks")
    path([(0, 9), (0, 17)], 1, "stone_bricks")
    for ang in (35, 145, 215, 325):
        a = math.radians(ang)
        path([(round(10 * math.cos(a)), round(10 * math.sin(a))), (round(31 * math.cos(a)), round(31 * math.sin(a)))], 1)
        for k in (16, 23, 30):
            lx, lz = round(k * math.cos(a)) + 2, round(k * math.sin(a))
            if (lx, lz) in top and (lx, lz) not in used:
                t = top[(lx, lz)]
                c += [f"setblock {lx} {t + 1} {lz} minecraft:oak_fence", f"setblock {lx} {t + 2} {lz} minecraft:lantern[hanging=false]"]
                used.add((lx, lz))
    # fountain
    for (x, z) in list(top):
        r = math.hypot(x, z)
        if r <= 2.6: c += [f"setblock {x} {Y} {z} minecraft:water", f"setblock {x} {Y - 1} {z} minecraft:stone_bricks"]
        elif r <= 3.6: c += [f"setblock {x} {Y} {z} minecraft:stone_bricks", f"setblock {x} {Y + 1} {z} minecraft:stone_brick_wall"]
    c += [f"fill 0 {Y} 0 0 {Y + 2} 0 minecraft:chiseled_stone_bricks", f"setblock 0 {Y + 3} 0 minecraft:water"]
    # trees around the hills
    trees = []
    keys = sorted(top)
    rnd.shuffle(keys)
    for (x, z) in keys:
        r = math.hypot(x, z)
        if not (17 < r < 34) or (x, z) in used: continue
        if any(math.hypot(x - a, z - b) < 7 for a, b in trees): continue
        if len(trees) >= 26: break
        trees.append((x, z))
    for i, (x, z) in enumerate(trees):
        t = top[(x, z)]
        log, leaves = [("oak_log", "oak_leaves"), ("birch_log", "birch_leaves"), ("oak_log", "oak_leaves"), ("cherry_log", "cherry_leaves")][i % 4]
        h = 4 + rnd.randint(0, 2)
        L = f"minecraft:{leaves}[persistent=true]"
        for dy in (h - 2, h - 1):
            c.append(f"fill {x - 2} {t + dy} {z - 2} {x + 2} {t + dy} {z + 2} {L} replace minecraft:air")
        c.append(f"fill {x - 1} {t + h} {z - 1} {x + 1} {t + h} {z + 1} {L} replace minecraft:air")
        c.append(f"setblock {x} {t + h + 1} {z} {L}")
        c.append(f"fill {x} {t + 1} {z} {x} {t + h - 1} {z} minecraft:{log}")
        for dx in range(-2, 3):
            for dz in range(-2, 3): used.add((x + dx, z + dz))
    # flowers and grass
    flowers = ["short_grass"] * 6 + ["poppy", "dandelion", "oxeye_daisy", "cornflower", "allium", "azure_bluet", "fern"]
    for (x, z), t in top.items():
        if (x, z) in used or math.hypot(x, z) < 11: continue
        if rnd.random() < 0.16: c.append(f"setblock {x} {t + 1} {z} minecraft:{rnd.choice(flowers)}")
    # no monsters: light blocks every 10 blocks (invisible, you walk through them)
    for x in range(-40, 41, 10):
        for z in range(-40, 41, 10):
            if (x, z) in top: c.append(f"setblock {x} {top[(x, z)] + 3} {z} minecraft:light[level=15]")
    # market stalls with the merchants
    for key, sx, sz, wool, prof in STALLS:
        yaw = math.degrees(math.atan2(-sx, sz))   # face the plaza centre
        c += [f"fill {sx - 1} {Y} {sz - 1} {sx + 1} {Y} {sz + 1} minecraft:spruce_planks"]
        for cx_, cz_ in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            c.append(f"fill {sx + cx_} {Y + 1} {sz + cz_} {sx + cx_} {Y + 3} {sz + cz_} minecraft:spruce_fence")
        c += [f"fill {sx - 1} {Y + 4} {sz - 1} {sx + 1} {Y + 4} {sz + 1} minecraft:{wool}_wool",
              f"setblock {sx} {Y + 5} {sz} minecraft:{wool}_carpet", f"setblock {sx} {Y + 3} {sz} minecraft:light[level=13]"]
    # the portal to your island
    c += portal_blocks(0, Y, HUB_PORTAL_Z, platform=False)
    c.append(label(0.5, Y + 5.6, HUB_PORTAL_Z + 0.5, snbt({"text": "Your Island", "color": "light_purple", "bold": True,
                   "extra": [txt("\nWalk through", "gray", bold=False)]}), 1.0, bill="center"))
    c += [label(0.5, Y + 7.2, -24.5, '{text:"Crispy Skyblock",color:"gold",bold:1b}', 3.0, bill="center"),
          label(HUB_SPAWN[0], Y + 2.6, HUB_SPAWN[2] + 2, '{text:"Press Esc → Island Menu anytime",color:"yellow"}', 0.9, bill="vertical"),
          # top islands board, rewritten by the mod whenever an island level is worked out
          label(-6.5, Y + 3.4, -14.5, '{text:"Top Islands\\n",color:"gold",bold:1b,extra:[{text:"Use /island level to get on the board",color:"gray",bold:0b}]}',
                0.9, yaw=0, tag="cs_top"),
          label(7.5, Y + 3.4, -14.5, snbt({"text": "Minions\n", "color": "aqua", "bold": True, "extra": [
              txt("Craft one: 8 of a resource around a wooden pickaxe.\nPlace it on your island; it gathers while you're offline.\nRight-click it to collect, upgrade (I to V) or pick it up.", "gray", bold=False)]}),
                0.8, yaw=0)]
    c += [f"setworldspawn 0 {Y + 1} 5", "scoreboard players set #hubv cs_cfg 3"]
    return c

def portal_blocks(x, y, z, platform=True):
    """A portal frame across x at (x, y, z) (y = the floor under it): crying obsidian posts and lintel around a 3x3
    opening. Islands get a 5x5 platform of reinforced deepslate and obsidian under it, out over the void. Everything
    is blast-proof and can't be pushed; the mod also stops players breaking it."""
    c = []
    if platform:
        c += [f"fill {x - 2} {y} {z - 2} {x + 2} {y} {z + 2} minecraft:reinforced_deepslate",
              f"fill {x - 1} {y} {z - 1} {x + 1} {y} {z + 1} minecraft:obsidian",
              f"fill {x - 1} {y - 1} {z - 1} {x + 1} {y - 1} {z + 1} minecraft:reinforced_deepslate"]
    c += [f"fill {x - 2} {y + 1} {z} {x - 2} {y + 4} {z} minecraft:crying_obsidian",
          f"fill {x + 2} {y + 1} {z} {x + 2} {y + 4} {z} minecraft:crying_obsidian",
          f"fill {x - 1} {y + 4} {z} {x + 1} {y + 4} {z} minecraft:crying_obsidian",
          f"fill {x - 1} {y + 1} {z} {x + 1} {y + 3} {z} minecraft:air",
          f"setblock {x} {y + 5} {z} minecraft:amethyst_cluster[facing=up]",
          f"setblock {x - 2} {y + 5} {z} minecraft:end_rod[facing=up]", f"setblock {x + 2} {y + 5} {z} minecraft:end_rod[facing=up]"]
    return c

# merchants stand in market stalls around the plaza; the mod opens the shop category named in their cs_shop_<key> tag
STALLS = [("farming", 12, -5, "lime", "farmer"), ("mining", 12, 5, "light_gray", "toolsmith"), ("foraging", -12, -5, "brown", "fletcher"),
          ("combat", -12, 5, "red", "weaponsmith"), ("supplies", 0, 14, "orange", "mason")]
fn("hub", "\n".join(hub_build()))
# hub v3: the stall lanterns sat where the merchants' labels go
fn("hub_v3", "\n".join(f"setblock {sx} {Y + 3} {sz} minecraft:light[level=13]" for _k, sx, sz, _w, _p in STALLS) + "\nscoreboard players set #hubv cs_cfg 3")
import math as _m
npc_lines = [f"kill @e[type=minecraft:villager,tag=cs_npc]", f"kill @e[type=minecraft:text_display,tag=cs_npcl]"]
shop_names = {k: (n, npc) for k, n, ic, npc, items in SHOP}
for key, sx, sz, wool, prof in STALLS:
    cat, who = shop_names[key]
    yaw = round(_m.degrees(_m.atan2(sx, -sz)), 1)   # look at the plaza centre
    npc_lines.append(f"summon minecraft:villager {sx + 0.5} {Y+1} {sz + 0.5} " + snbt({
        "NoAI": True, "Invulnerable": True, "Silent": True, "PersistenceRequired": True,
        "Tags": [NS, "cs_npc", f"cs_shop_{key}"],
        "VillagerData": {"profession": f"minecraft:{prof}", "level": 5, "type": "minecraft:plains"}, "Offers": {"Recipes": []}})[:-1]
        + f",Rotation:[{yaw}f,0f]}}")
    # one two-line label instead of the villager's own name tag
    npc_lines.append(label(sx + 0.5, Y + 3.15, sz + 0.5, snbt({"text": who, "color": "gold", "bold": True,
                     "extra": [txt(f"\n{cat} · click to trade", "gray", bold=False)]}), 0.7, bill="center", tag="cs_npcl"))
fn("npcs", "\n".join(npc_lines))


# ======================================================================= tick
fn("tick", f"""
scoreboard players enable @a cs_act
execute as @a[scores={{cs_act=1..}}] at @s run function {NS}:act/dispatch
execute as @a unless score @s cs_seen matches 1 run function {NS}:first_join
execute as @e[type=minecraft:player,scores={{cs_die=1..}}] run function {NS}:p/respawned
# hub = adventure, everywhere else = survival
execute as @a[gamemode=survival] at @s if dimension minecraft:overworld if entity @s[x=-{HUB_R},y={Y-45},z=-{HUB_R},dx={2*HUB_R},dy=90,dz={2*HUB_R}] run gamemode adventure @s
execute as @a[gamemode=adventure] at @s unless entity @s[x=-{HUB_R},y={Y-45},z=-{HUB_R},dx={2*HUB_R},dy=90,dz={2*HUB_R}] run gamemode survival @s
execute as @a[gamemode=adventure] at @s unless dimension minecraft:overworld run gamemode survival @s
execute as @e[type=minecraft:player,x=-{HUB_R},y={Y-110},z=-{HUB_R},dx={2*HUB_R},dy=64,dz={2*HUB_R}] run function {NS}:act/hub
scoreboard players add #t cs_tmp 1
execute if score #t cs_tmp matches 10 run function {NS}:p/bounds_all
execute if score #t cs_tmp matches 10 run function {NS}:p/nbounds_all
execute if score #t cs_tmp matches 20.. run function {NS}:second
""")
fn("second", f"""
scoreboard players set #t cs_tmp 0
particle minecraft:portal 0.5 {Y+2.5} {HUB_PORTAL_Z+0.5} 0.9 0.9 0.05 0.3 30 force
kill @e[type=#{NS}:hostile,x=-{HUB_R},y={Y-45},z=-{HUB_R},dx={2*HUB_R},dy=90,dz={2*HUB_R}]
execute as @e[tag=cs_boss] at @s run function {NS}:boss/tick
scoreboard players remove @a[scores={{cs_cd=1..}}] cs_cd 1
scoreboard players reset * cs_on
scoreboard players reset * cs_non
execute as @a[scores={{cs_plot=1..}}] run function {NS}:p/count
scoreboard players set #i cs_tmp 1
execute if score #next cs_tmp matches 1.. run function {NS}:loop/step
""")
fn("p/count", f"""
execute store result storage {NS}:d q.i int 1 run scoreboard players get @s cs_plot
function {NS}:p/count2 with storage {NS}:d q
execute at @s if dimension minecraft:the_nether run function {NS}:p/ncount2 with storage {NS}:d q
""")
fn("p/count2", "$scoreboard players add #p$(i) cs_on 1")
fn("p/ncount2", "$scoreboard players add #p$(i) cs_non 1")
fn("loop/step", f"""
execute store result storage {NS}:d q.i int 1 run scoreboard players get #i cs_tmp
function {NS}:loop/one with storage {NS}:d q
scoreboard players add #i cs_tmp 1
execute if score #i cs_tmp <= #next cs_tmp run function {NS}:loop/step
""")
fn("loop/one", f"""
$execute if score #p$(i) cs_npend matches 1 run function {NS}:plot/npend_i {{i:$(i)}}
$execute unless score #p$(i) cs_on matches 1.. unless score #p$(i) cs_was matches 1.. run return 0
$data modify storage {NS}:d cur set from storage {NS}:d plots[$(i)]
function {NS}:plot/tick with storage {NS}:d cur
""")

# ======================================================================= per-island second
def every(n, f):
    return (f"$scoreboard players operation #m cs_tmp = #p$(id) cs_age\nscoreboard players set #k cs_tmp {n}\n"
            f"scoreboard players operation #m cs_tmp %= #k cs_tmp\nexecute if score #m cs_tmp matches 0 run function {NS}:{f} with storage {NS}:d cur")
dng = "\n".join(f"$execute if score #p$(id) cs_age matches {a} run function {NS}:ev/dungeon with storage {NS}:d cur" for a in DUNGEON_AGES)
fn("plot/tick", f"""
# just emptied: stop loading it (and its Nether)
$execute unless score #p$(id) cs_on matches 1.. run forceload remove $(x) $(z) $(x1) $(z1)
$execute unless score #p$(id) cs_on matches 1.. if score #p$(id) cs_nwas matches 1.. in minecraft:the_nether run forceload remove $(nwx) $(nwz) $(nwx1) $(nwz1)
$execute unless score #p$(id) cs_on matches 1.. run scoreboard players set #p$(id) cs_nwas 0
$execute unless score #p$(id) cs_on matches 1.. run return run scoreboard players set #p$(id) cs_was 0
$execute unless score #p$(id) cs_was matches 1.. run forceload add $(x) $(z) $(x1) $(z1)
$scoreboard players set #p$(id) cs_was 1
$scoreboard players add #p$(id) cs_age 1
{every(ANIMAL_EVERY, "ev/animal")}
{every(SUPPLY_EVERY, "ev/supply")}
{every(METEOR_EVERY, "ev/meteor")}
{dng}
$execute if score #p$(id) cs_age matches {PORTAL_AGE} run function {NS}:ev/portal with storage {NS}:d cur
function {NS}:plot/ntick with storage {NS}:d cur
$execute unless data storage {NS}:d plots[$(id)].portal run function {NS}:portal/retro with storage {NS}:d cur
$execute if score #p$(id) cs_bce matches 1.. run scoreboard players remove #p$(id) cs_bce 1
$execute if score #p$(id) cs_bcn matches 1.. run scoreboard players remove #p$(id) cs_bcn 1
$execute positioned $(cx) {ISLAND_Y} $(cz) run particle minecraft:portal ~0.5 ~2.5 ~{PORTAL_DZ + 0.5} 0.9 0.9 0.05 0.3 25
# hostile cap: mobs already here stay; brand-new spawns over the cap are sent into the void
$execute store result score #h cs_tmp if entity @e[type=#{NS}:hostile,x=$(x),y=-64,z=$(z),dx={SIZE-1},dy=400,dz={SIZE-1}]
$execute if score #h cs_tmp matches {HOSTILE_CAP+1}.. as @e[type=#{NS}:hostile,tag=!cs_old,x=$(x),y=-64,z=$(z),dx={SIZE-1},dy=400,dz={SIZE-1}] run function {NS}:mob_cull
$tag @e[type=#{NS}:hostile,tag=!cs_old,x=$(x),y=-64,z=$(z),dx={SIZE-1},dy=400,dz={SIZE-1}] add cs_old
""")
fn("mob_cull", f"""
execute if score #h cs_tmp matches ..{HOSTILE_CAP} run return 0
execute at @s run tp @s ~ -200 ~
scoreboard players remove #h cs_tmp 1
""")

# ======================================================================= sky events (all land near the island centre)
def spot():
    return (f"$execute store result storage {NS}:d ev.x int 1 run random value $(ix)..$(ix1)\n"
            f"$execute store result storage {NS}:d ev.z int 1 run random value $(iz)..$(iz1)\n"
            f"$data modify storage {NS}:d ev.id set value $(id)")
fn("ev/animal", spot() + f"""
execute store result score #r cs_tmp run random value 1..{cumulative(ANIMALS)[1]}
""" + "\n".join(f"execute if score #r cs_tmp matches {a}..{b} run data modify storage {NS}:d ev.e set value \"minecraft:{e}\""
                for a, b, (_, e) in cumulative(ANIMALS)[0]) + f"""
function {NS}:ev/animal_at with storage {NS}:d ev
""")
fn("ev/animal_at", f"""
$execute positioned $(x).5 {SKY_Y} $(z).5 positioned over motion_blocking run summon $(e) ~ ~ ~ {{Tags:["cs_animal"],PersistenceRequired:1b}}
$execute positioned $(x).5 {SKY_Y} $(z).5 positioned over motion_blocking run particle minecraft:happy_villager ~ ~1 ~ 0.5 0.5 0.5 0 15 force
$tellraw @a[scores={{cs_plot=$(id)}}] [{{text:"🐾 ",color:"green"}},{{text:"An animal floated down onto your island. Fence it in!",color:"green"}}]
""")
fn("ev/supply", spot() + f"\nfunction {NS}:ev/supply_at with storage {NS}:d ev")
fn("ev/supply_at", f"""
$summon minecraft:falling_block $(x).5 {SKY_Y} $(z).5 {{BlockState:{{Name:"minecraft:barrel",Properties:{{facing:"up"}}}},TileEntityData:{{LootTable:"{NS}:chests/supply"}},Time:1,DropItem:0b,HurtEntities:1b,FallHurtAmount:0.2f,FallHurtMax:4}}
$tellraw @a[scores={{cs_plot=$(id)}}] [{{text:"📦 ",color:"aqua"}},{{text:"A supply crate is falling onto your island! Look up.",color:"aqua"}}]
$execute as @a[scores={{cs_plot=$(id)}}] at @s run playsound minecraft:entity.firework_rocket.launch master @s ~ ~ ~ 1 0.6
""")
mt, mtotal = cumulative(METEOR)
fn("ev/meteor", spot() + f"\nfunction {NS}:ev/meteor_at with storage {NS}:d ev")
fn("ev/meteor_at", f"""
$tellraw @a[scores={{cs_plot=$(id)}}] [{{text:"☄ ",color:"red"}},{{text:"A meteor is coming down on your island! Stand clear, then mine it.",color:"red"}}]
$execute as @a[scores={{cs_plot=$(id)}}] at @s run playsound minecraft:entity.generic.explode master @s ~ ~ ~ 1 0.5
$execute positioned $(x) {SKY_Y} $(z) run function {NS}:ev/meteor_rocks
""")
rock = "\n".join(f"execute if score #r cs_tmp matches {a}..{b} run data modify storage {NS}:d rock.b set value \"minecraft:{blk}\""
                 for a, b, (_, blk) in mt)
fn("ev/meteor_rocks", "\n".join(
    f"execute store result score #r cs_tmp run random value 1..{mtotal}\n{rock}\n"
    f"execute positioned ~{dx} ~{dy} ~{dz} run function {NS}:ev/meteor_rock with storage {NS}:d rock"
    for dx, dy, dz in [(0, 0, 0), (1, 1, 0), (0, 2, 1), (-1, 1, 0), (0, 3, -1), (1, 4, 1), (-1, 5, -1), (0, 6, 0)]) +
    "\nparticle minecraft:flame ~ ~ ~ 1 2 1 0.05 120 force")
fn("ev/meteor_rock", "$summon minecraft:falling_block ~0.5 ~ ~0.5 {BlockState:{Name:\"$(b)\"},Time:1,DropItem:1b,HurtEntities:1b,FallHurtAmount:0.5f,FallHurtMax:6}")
fn("ev/dungeon", spot() + f"\nfunction {NS}:ev/dungeon_at with storage {NS}:d ev")
fn("ev/dungeon_at", f"""
$execute positioned $(x) {SKY_Y} $(z) positioned over motion_blocking_no_leaves run function {NS}:ev/dungeon_build
$tellraw @a[scores={{cs_plot=$(id)}}] [{{text:"☄ ",color:"red"}},{{text:"A dungeon crashed into your island! Monsters guard its loot (and it's free land).",color:"red"}}]
$execute as @a[scores={{cs_plot=$(id)}}] at @s run playsound minecraft:entity.generic.explode master @s ~ ~ ~ 1 0.6
""")
fn("ev/dungeon_build", f"""
# shell only fills air, so it never overwrites anything players built
fill ~-3 ~ ~-3 ~3 ~ ~3 minecraft:mossy_cobblestone replace minecraft:air
fill ~-3 ~1 ~-3 ~3 ~4 ~3 minecraft:cobblestone replace minecraft:air
fill ~-2 ~1 ~-2 ~2 ~3 ~2 minecraft:air replace minecraft:cobblestone
fill ~-3 ~1 ~ ~-3 ~2 ~ minecraft:air replace minecraft:cobblestone
fill ~-2 ~4 ~-2 ~2 ~4 ~2 minecraft:mossy_cobblestone replace minecraft:cobblestone
execute store result score #r cs_tmp run random value 1..3
execute if score #r cs_tmp matches 1 run setblock ~ ~1 ~ minecraft:spawner{{SpawnData:{{entity:{{id:"minecraft:zombie"}}}}}}
execute if score #r cs_tmp matches 2 run setblock ~ ~1 ~ minecraft:spawner{{SpawnData:{{entity:{{id:"minecraft:skeleton"}}}}}}
execute if score #r cs_tmp matches 3 run setblock ~ ~1 ~ minecraft:spawner{{SpawnData:{{entity:{{id:"minecraft:spider"}}}}}}
setblock ~2 ~1 ~2 minecraft:chest[facing=north]{{LootTable:"{NS}:chests/dungeon"}}
setblock ~-2 ~1 ~-2 minecraft:chest[facing=south]{{LootTable:"{NS}:chests/dungeon"}}
summon minecraft:zombie ~1 ~1 ~-1
summon minecraft:skeleton ~-1 ~1 ~1
particle minecraft:explosion_emitter ~ ~2 ~ 0 0 0 0 1 force
""")
END_DX = 14                # the island's End portal: on its own platform 14 blocks east of the island centre
fn("ev/portal", f"""
# the End portal: on its own platform east of the island, out over the void, so it never lands on anything built
$execute positioned $(cx) {ISLAND_Y} $(cz) positioned ~{END_DX} ~ ~ run function {NS}:ev/portal_build
$data modify storage {NS}:d plots[$(id)].endp set value 1b
$tellraw @a[scores={{cs_plot=$(id)}}] [{{text:"✦ ",color:"light_purple"}},{{text:"An End portal appeared east of your island, over the void. Bridge to it and fill it with 12 Eyes of Ender to reach your island's own End.",color:"light_purple"}}]
$execute as @a[scores={{cs_plot=$(id)}}] at @s run playsound minecraft:block.end_portal_frame.fill master @s ~ ~ ~ 1 0.5
""")
epb = Build(0)
epb.fill(-3, 0, -3, 3, 0, 3, "reinforced_deepslate")
epb.fill(-2, 0, -2, 2, 0, 2, "end_stone_bricks")
epb.fill(-2, -1, -2, 2, -1, 2, "reinforced_deepslate")
epb.fill(-1, 0, -1, 1, 0, 1, "obsidian")
epb.fill(-1, 1, -2, 1, 1, -2, "end_portal_frame[facing=south]")
epb.fill(-1, 1, 2, 1, 1, 2, "end_portal_frame[facing=north]")
epb.fill(-2, 1, -1, -2, 1, 1, "end_portal_frame[facing=east]")
epb.fill(2, 1, -1, 2, 1, 1, "end_portal_frame[facing=west]")
for cx_, cz_ in ((-3, -3), (-3, 3), (3, -3), (3, 3)): epb.set(cx_, 1, cz_, "end_rod[facing=up]")
fn("ev/portal_build", "\n".join(epb.c) + "\nparticle minecraft:portal ~ ~2 ~ 1.5 1 1.5 0.5 200 force\n" + "summon minecraft:text_display ~0.5 ~3.2 ~0.5 " + snbt({
    "Tags": [NS], "billboard": "center", "background": 1073741824,
    "text": {"text": "End Portal", "color": "dark_purple", "bold": True, "extra": [txt("\n12 Eyes of Ender: your own End and its boss", "gray", bold=False)]}}))

# ======================================================================= each island's own End: a void dimension, one sky island per island
END_Y = 64
etype = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "the_end_type.json")))
etype["has_ender_dragon_fight"] = False
js(f"data/{NS}/dimension_type/sky_end.json", etype)
js(f"data/{NS}/dimension/end.json", {"type": f"{NS}:sky_end", "generator": {"type": "minecraft:flat", "settings": {
    "biome": "minecraft:the_end", "layers": [{"block": "minecraft:air", "height": 1}], "lakes": False, "features": False, "structure_overrides": []}}})
eb = Build(11)
eb.blob(10, 7, "end_stone", "end_stone", "end_stone")
eb.disk(0, 5.5, "purpur_block")
eb.disk(0, 4.5, "end_stone_bricks")
eb.fill(-1, 0, -1, 1, 0, 1, "crying_obsidian")
eb.set(0, 1, 0, "lodestone")
for cx_, cz_ in ((-1, -1), (-1, 1), (1, -1), (1, 1)): eb.set(cx_, 1, cz_, "end_rod[facing=up]")
for px, pz, h in ((7, -3, 4), (-7, 2, 5), (4, 7, 3), (-5, -6, 3)):
    eb.fill(px, 1, pz, px, h, pz, "obsidian"); eb.set(px, h + 1, pz, "end_rod[facing=up]")
for fx, fz in ((-7, -2), (7, 3), (-3, 8), (2, -7)): eb.set(fx, 1, fz, "chorus_flower[age=0]")
# the way home: a purpur gateway on the north edge
eb.fill(-2, 0, -10, 2, 0, -8, "end_stone_bricks")
eb.fill(-2, 1, -9, -2, 4, -9, "purpur_pillar")
eb.fill(2, 1, -9, 2, 4, -9, "purpur_pillar")
eb.fill(-1, 4, -9, 1, 4, -9, "purpur_block")
eb.fill(-1, 1, -9, 1, 3, -9, "air")
eb.set(0, 5, -9, "end_rod[facing=up]")
def tdisp(dx, dy, dz, text):
    return f"summon minecraft:text_display ~{dx} ~{dy} ~{dz} " + snbt({"Tags": [NS, "cs_realml"], "billboard": "center", "background": 1073741824, "text": text})
fn("end/island", "\n".join(eb.c) + "\n" + "\n".join([
    tdisp(0.5, 2.2, 0.5, {"text": "Summoning Altar", "color": "light_purple", "bold": True, "extra": [txt("\nRight-click the lodestone to call your boss", "gray", bold=False)]}),
    tdisp(0.5, 5.8, -8.5, {"text": "Back to your island", "color": "aqua", "bold": True, "extra": [txt("\nWalk through", "gray", bold=False)]})]))

# ======================================================================= the Nether boss arena, a short bridge south of the island's Nether island
ARENA_DZ = 16
ab = Build(12)
ab.blob(8, 6, "blackstone", "basalt", "blackstone")
ab.disk(0, 6.5, "polished_blackstone_bricks")
ab.disk(0, 5.5, "blackstone")
ab.fill(-1, 0, -1, 1, 0, 1, "crying_obsidian")
ab.set(0, 1, 0, "lodestone")
for cx_, cz_ in ((-5, -5), (-5, 5), (5, -5), (5, 5)):
    ab.set(cx_, 1, cz_, "polished_blackstone_wall"); ab.set(cx_, 2, cz_, "soul_lantern")
fn("nether/arena", "\n".join(ab.c) + "\n" + tdisp(0.5, 2.2, 0.5, {"text": "Summoning Altar", "color": "red", "bold": True,
   "extra": [txt("\nRight-click the lodestone to call your boss", "gray", bold=False)]}))
fn("nether/arena_retro", f"""
$execute in minecraft:the_nether positioned $(ncx) {NFLOOR_Y} $(ncz) positioned ~ ~ ~{ARENA_DZ} run function {NS}:nether/arena
$data modify storage {NS}:d plots[$(id)].narena set value 1b
$tellraw @a[scores={{cs_plot=$(id)}}] [{{text:"🔥 ",color:"gold"}},{{text:"A boss arena rose out of the lava south of your Nether island. Bridge to it and right-click the altar!",color:"gold"}}]
""")

# ======================================================================= bosses: four per realm, each island works up its own ladder
# key, name, entity, bossbar colour, health, attributes, extra NBT, ability every N seconds, coins
BOSSES = {
    "e": [("colossus", "Ender Colossus", "enderman", "purple", 400, {"scale": 3.0, "attack_damage": 14.0, "movement_speed": 0.32, "knockback_resistance": 1.0, "follow_range": 48.0}, {}, 6),
          ("ravager", "Void Ravager", "ravager", "purple", 500, {"scale": 1.6, "attack_damage": 16.0, "knockback_resistance": 1.0, "follow_range": 48.0}, {}, 10),
          ("matriarch", "Shulker Matriarch", "shulker", "pink", 450, {"scale": 3.0, "armor": 10.0}, {"Color": 10}, 9),
          ("archmage", "The Archmage", "evoker", "purple", 350, {"scale": 1.8, "follow_range": 48.0}, {}, 7)],
    "n": [("blaze", "Blaze King", "blaze", "yellow", 400, {"scale": 2.5, "attack_damage": 10.0, "follow_range": 48.0}, {}, 9),
          ("magma", "Magma Titan", "magma_cube", "red", 500, {"attack_damage": 10.0, "follow_range": 48.0, "knockback_resistance": 1.0}, {"Size": 5}, 8),
          ("warlord", "Brute Warlord", "piglin_brute", "red", 450, {"scale": 2.0, "attack_damage": 16.0, "knockback_resistance": 1.0, "follow_range": 48.0},
           {"IsImmuneToZombification": True, "equipment": {"mainhand": {"id": "minecraft:netherite_axe"}, "head": {"id": "minecraft:golden_helmet"}}}, 12),
          ("knight", "Wither Knight", "wither_skeleton", "white", 500, {"scale": 2.5, "attack_damage": 14.0, "follow_range": 48.0, "knockback_resistance": 1.0},
           {"equipment": {"mainhand": {"id": "minecraft:netherite_sword"}, "head": {"id": "minecraft:netherite_helmet"}, "chest": {"id": "minecraft:netherite_chestplate"}}}, 6)],
}
REALM_COINS = {"e": 3000, "n": 1500}

REALM_NAME = {"e": "End", "n": "Nether"}
BOSS_COOLDOWN = 1200          # seconds of island play time between boss fights
BOSS_OBJS = "\n".join(f"scoreboard objectives add {o}{r} dummy" for r in "en" for o in ("cs_ba", "cs_bc", "cs_bi", "cs_bk")) + \
    "\nscoreboard objectives add cs_bplot dummy\nscoreboard objectives add cs_btm dummy\nscoreboard objectives add cs_bidle dummy\nscoreboard players set #4 cs_tmp 4"
fn("boss/objectives", BOSS_OBJS)
ABILITY = {
    "colossus": ["playsound minecraft:entity.enderman.scream hostile @a[distance=..32] ~ ~ ~ 2 0.5",
                 "particle minecraft:reverse_portal ~ ~1 ~ 3 1 3 0.1 150 force",
                 "damage @a[distance=..5,gamemode=!creative,gamemode=!spectator] 8 minecraft:mob_attack by @s",
                 "effect give @a[distance=..5,gamemode=!creative,gamemode=!spectator] minecraft:levitation 1 3"],
    "ravager": ["playsound minecraft:entity.ravager.roar hostile @a[distance=..32] ~ ~ ~ 2 0.7",
                "summon minecraft:endermite ~2 ~1 ~ {Tags:[\"cs_bminion\",\"cs_bmnew\",\"cs_old\"]}",
                "summon minecraft:endermite ~-2 ~1 ~ {Tags:[\"cs_bminion\",\"cs_bmnew\",\"cs_old\"]}",
                "summon minecraft:endermite ~ ~1 ~2 {Tags:[\"cs_bminion\",\"cs_bmnew\",\"cs_old\"]}"],
    "matriarch": ["playsound minecraft:entity.shulker.shoot hostile @a[distance=..32] ~ ~ ~ 2 0.5",
                  "summon minecraft:phantom ~2 ~6 ~ {Tags:[\"cs_bminion\",\"cs_bmnew\",\"cs_old\"]}",
                  "summon minecraft:phantom ~-2 ~6 ~ {Tags:[\"cs_bminion\",\"cs_bmnew\",\"cs_old\"]}",
                  "effect give @a[distance=..10,gamemode=!creative,gamemode=!spectator] minecraft:levitation 2 1"],
    "archmage": ["particle minecraft:witch ~ ~1.5 ~ 1 1 1 0.1 60 force",
                 "spreadplayers ~ ~ 1 6 false @s",
                 "effect give @a[distance=..12,gamemode=!creative,gamemode=!spectator] minecraft:blindness 2 0"],
    "blaze": ["playsound minecraft:entity.blaze.ambient hostile @a[distance=..32] ~ ~ ~ 2 0.5",
              "summon minecraft:blaze ~2 ~1 ~ {Tags:[\"cs_bminion\",\"cs_bmnew\",\"cs_old\"]}",
              "summon minecraft:blaze ~-2 ~1 ~ {Tags:[\"cs_bminion\",\"cs_bmnew\",\"cs_old\"]}"],
    "magma": ["playsound minecraft:entity.magma_cube.squish hostile @a[distance=..32] ~ ~ ~ 2 0.4",
              "particle minecraft:lava ~ ~0.5 ~ 2 0.2 2 0 60 force",
              "damage @a[distance=..4,gamemode=!creative,gamemode=!spectator] 6 minecraft:mob_attack by @s",
              "effect give @a[distance=..7,gamemode=!creative,gamemode=!spectator] minecraft:slowness 3 1"],
    "warlord": ["playsound minecraft:entity.piglin_brute.angry hostile @a[distance=..32] ~ ~ ~ 2 0.6",
                "summon minecraft:piglin_brute ~2 ~1 ~ {IsImmuneToZombification:1b,Tags:[\"cs_bminion\",\"cs_bmnew\",\"cs_old\"]}",
                "summon minecraft:piglin_brute ~-2 ~1 ~ {IsImmuneToZombification:1b,Tags:[\"cs_bminion\",\"cs_bmnew\",\"cs_old\"]}"],
    "knight": ["playsound minecraft:entity.wither_skeleton.ambient hostile @a[distance=..32] ~ ~ ~ 2 0.5",
               "particle minecraft:smoke ~ ~1 ~ 2 1 2 0.02 80 force",
               "effect give @a[distance=..6,gamemode=!creative,gamemode=!spectator] minecraft:wither 4 1"],
}
for realm, bosses in BOSSES.items():
    for i, (key, name, ent, color, hp, attrs, extra, every) in enumerate(bosses):
        data = {"Tags": [NS, "cs_boss", "cs_bnew", "cs_old", f"cs_boss_{realm}", f"cs_bt_{key}"],
                "CustomName": txt(name, "light_purple" if realm == "e" else "red", bold=True), "CustomNameVisible": True,
                "PersistenceRequired": True, "Health": f"{hp}.0f", "DeathLootTable": f"{NS}:entities/boss_{key}",
                "attributes": [{"id": "minecraft:max_health", "base": float(hp)}] + [{"id": f"minecraft:{a}", "base": v} for a, v in attrs.items()],
                "drop_chances": {"mainhand": 0.0, "head": 0.0, "chest": 0.0}}
        data.update(extra)
        nbt = snbt(data).replace(f'"{hp}.0f"', f"{hp}.0f")
        fn(f"boss/{realm}/{i}", f"""
summon minecraft:{ent} ~ ~ ~ {nbt}
$scoreboard players set @e[tag=cs_bnew,limit=1,sort=nearest] cs_bplot $(id)
tag @e[tag=cs_bnew] remove cs_bnew
$bossbar add {NS}:{realm}$(id) {snbt(txt(name, color if color != "white" else "gray", bold=True))}
$bossbar set {NS}:{realm}$(id) color {color}
$bossbar set {NS}:{realm}$(id) max {hp}
$bossbar set {NS}:{realm}$(id) value {hp}
$bossbar set {NS}:{realm}$(id) players @a[distance=..48]
$tellraw @a[scores={{cs_plot=$(id)}}] [{{text:"☠ ",color:"dark_red"}},{{text:"{name}",color:"{'light_purple' if realm == 'e' else 'red'}",bold:1b}},{{text:" has been summoned!",color:"gray",bold:0b}}]
playsound minecraft:entity.wither.spawn hostile @a[distance=..48] ~ ~ ~ 1 {'0.7' if realm == 'e' else '1.1'}
particle minecraft:explosion_emitter ~ ~1 ~ 0 0 0 0 1 force
""")
        fn(f"boss/ab/{key}", "\n".join(ABILITY[key] + ["scoreboard players set @s cs_btm 0"]))
    # loot: each boss
fn("boss/summon", f"""
# right-clicking a summoning altar (the mod runs this as the player): {{r:"e"|"n", id, x, y, z}} = realm, island, where the boss appears
$execute unless score @s cs_plot matches $(id) run return run tellraw @s {{text:"This isn't your island's altar.",color:"red"}}
# a boss that's gone without being killed (fell into the void...) doesn't block the next one
$execute if score #p$(id) cs_ba$(r) matches 1 positioned $(x) $(y) $(z) unless entity @e[tag=cs_boss_$(r),distance=..96] run scoreboard players reset #p$(id) cs_ba$(r)
$execute if score #p$(id) cs_ba$(r) matches 1 run return run tellraw @s {{text:"Your boss is already out there!",color:"red"}}
$execute if score #p$(id) cs_bc$(r) matches 1.. run scoreboard players operation #m cs_tmp = #p$(id) cs_bc$(r)
$execute if score #p$(id) cs_bc$(r) matches 1.. run scoreboard players operation #m cs_tmp /= #60 cs_tmp
$execute if score #p$(id) cs_bc$(r) matches 1.. run return run tellraw @s [{{text:"The altar is still recharging: about ",color:"red"}},{{score:{{name:"#m",objective:"cs_tmp"}},color:"white"}},{{text:" more minutes of island play.",color:"red"}}]
# each island starts on a different boss of the realm's four
$execute unless score #p$(id) cs_bi$(r) matches 0.. run scoreboard players set #p$(id) cs_bi$(r) $(id)
$scoreboard players operation #p$(id) cs_bi$(r) %= #4 cs_tmp
$execute if score #p$(id) cs_bi$(r) matches 0 positioned $(x) $(y) $(z) run function {NS}:boss/$(r)/0 {{id:$(id)}}
$execute if score #p$(id) cs_bi$(r) matches 1 positioned $(x) $(y) $(z) run function {NS}:boss/$(r)/1 {{id:$(id)}}
$execute if score #p$(id) cs_bi$(r) matches 2 positioned $(x) $(y) $(z) run function {NS}:boss/$(r)/2 {{id:$(id)}}
$execute if score #p$(id) cs_bi$(r) matches 3 positioned $(x) $(y) $(z) run function {NS}:boss/$(r)/3 {{id:$(id)}}
$scoreboard players set #p$(id) cs_ba$(r) 1
""")
fn("boss/tick", f"""
# every second, as each boss: bossbar, abilities, and leaving if nobody's near for 2 minutes
execute store result storage {NS}:d b.id int 1 run scoreboard players get @s cs_bplot
data modify storage {NS}:d b.r set value "e"
execute if entity @s[tag=cs_boss_n] run data modify storage {NS}:d b.r set value "n"
function {NS}:boss/tick2 with storage {NS}:d b
""")
abil = "\n".join(f"execute if entity @s[tag=cs_bt_{k}] if score @s cs_btm matches {every}.. run function {NS}:boss/ab/{k}"
                 for bosses in BOSSES.values() for (k, _n, _e, _c, _h, _a, _x, every) in bosses)
fn("boss/tick2", f"""
$execute store result bossbar {NS}:$(r)$(id) value run data get entity @s Health
$bossbar set {NS}:$(r)$(id) players @a[distance=..48]
scoreboard players add @s cs_btm 1
{abil}
$tag @e[tag=cs_bmnew] add cs_bm_$(r)$(id)
tag @e[tag=cs_bmnew] remove cs_bmnew
execute if entity @a[distance=..64] run scoreboard players set @s cs_bidle 0
execute unless entity @a[distance=..64] run scoreboard players add @s cs_bidle 1
$execute if score @s cs_bidle matches 120.. run function {NS}:boss/despawn {{r:"$(r)",id:$(id)}}
""")
fn("boss/despawn", f"""
$kill @e[tag=cs_bm_$(r)$(id)]
$bossbar remove {NS}:$(r)$(id)
$scoreboard players reset #p$(id) cs_ba$(r)
$tellraw @a[scores={{cs_plot=$(id)}}] {{text:"Your boss got bored and left (nobody was near it). Summon it again any time.",color:"gray"}}
data modify entity @s DeathLootTable set value "minecraft:empty"
tp @s ~ -500 ~
kill @s
""")
# kill credit: an advancement fires for whoever lands the killing blow
js(f"data/{NS}/advancement/boss_kill.json", {"criteria": {"k": {"trigger": "minecraft:player_killed_entity", "conditions": {"entity": [
    {"condition": "minecraft:entity_properties", "entity": "this", "predicate": {"nbt": "{Tags:[\"cs_boss\"]}"}}]}}},
    "rewards": {"function": f"{NS}:boss/killed"}})
fn("boss/killed", f"""
advancement revoke @s only {NS}:boss_kill
execute store result storage {NS}:d b.id int 1 run scoreboard players get @s cs_plot
data modify storage {NS}:d b.r set value "e"
execute if dimension minecraft:the_nether run data modify storage {NS}:d b.r set value "n"
execute if dimension minecraft:the_nether run data modify storage {NS}:d b.c set value {REALM_COINS["n"]}
execute unless dimension minecraft:the_nether run data modify storage {NS}:d b.c set value {REALM_COINS["e"]}
function {NS}:boss/killed2 with storage {NS}:d b
""")
names = "\n".join(f"$execute if score #p$(id) cs_bi{r} matches {i} if data storage {NS}:d b{{r:\"{r}\"}} run tellraw @a [{{selector:\"@s\",color:\"gold\"}},{{text:\"'s island defeated \",color:\"gray\"}},{{text:\"{n}\",color:\"{'light_purple' if r == 'e' else 'red'}\",bold:1b}},{{text:\"!\",color:\"gray\"}}]"
                  for r, bosses in BOSSES.items() for i, (_k, n, *_x) in enumerate(bosses))
fn("boss/killed2", f"""
$execute unless score #p$(id) cs_ba$(r) matches 1 run return 0
$scoreboard players reset #p$(id) cs_ba$(r)
$kill @e[tag=cs_bm_$(r)$(id)]
$bossbar remove {NS}:$(r)$(id)
{names}
$scoreboard players add @a[scores={{cs_plot=$(id)}}] cs_coins $(c)
$tellraw @a[scores={{cs_plot=$(id)}}] [{{text:"+$(c) coins ",color:"gold",bold:1b}},{{text:"for everyone on the island. The next boss waits at the altar after a {BOSS_COOLDOWN // 60}-minute recharge.",color:"gray",bold:0b}}]
$scoreboard players add #p$(id) cs_bk$(r) 1
$scoreboard players add #p$(id) cs_bi$(r) 1
$scoreboard players operation #p$(id) cs_bi$(r) %= #4 cs_tmp
$scoreboard players set #p$(id) cs_bc$(r) {BOSS_COOLDOWN}
$execute as @a[scores={{cs_plot=$(id)}}] at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 0.8
""")
def L(it, w_, lo=1, hi=1):
    d = {"type": "minecraft:item", "name": f"minecraft:{it}", "weight": w_}
    if hi > 1: d["functions"] = [{"function": "minecraft:set_count", "count": {"type": "minecraft:uniform", "min": lo, "max": hi}}]
    return d
def chance(it, p, lo=1, hi=1):
    e = L(it, 1, lo, hi); e.pop("weight")
    return {"rolls": 1, "conditions": [{"condition": "minecraft:random_chance", "chance": p}], "entries": [e]}
END_COMMON = [L("ender_pearl", 10, 4, 8), L("shulker_shell", 6, 1, 3), L("chorus_fruit", 8, 4, 10), L("dragon_breath", 4, 2, 4),
              L("end_crystal", 2), L("diamond", 5, 2, 4), L("experience_bottle", 8, 8, 16), L("popped_chorus_fruit", 4, 4, 8)]
NETHER_COMMON = [L("blaze_rod", 10, 4, 8), L("ghast_tear", 5, 1, 3), L("magma_cream", 8, 4, 8), L("gold_block", 5, 1, 3),
                 L("quartz", 8, 8, 16), L("ancient_debris", 3, 1, 2), L("experience_bottle", 8, 8, 16), L("nether_wart", 6, 4, 8)]
SPECIAL = {"colossus": [chance("elytra", 0.25), chance("ender_eye", 1.0, 4, 8)], "ravager": [chance("elytra", 0.25), chance("saddle", 0.5)],
           "matriarch": [chance("shulker_shell", 1.0, 4, 6), chance("elytra", 0.2)], "archmage": [chance("totem_of_undying", 1.0), chance("elytra", 0.2)],
           "blaze": [chance("netherite_scrap", 0.5, 1, 2), chance("blaze_rod", 1.0, 6, 10)], "magma": [chance("netherite_scrap", 0.5, 1, 2), chance("magma_block", 1.0, 8, 16)],
           "warlord": [chance("netherite_scrap", 1.0, 1, 2), chance("netherite_upgrade_smithing_template", 0.3)],
           "knight": [chance("wither_skeleton_skull", 0.35), chance("netherite_scrap", 0.6, 1, 2)]}
for realm, bosses in BOSSES.items():
    for (key, *_r) in bosses:
        js(f"data/{NS}/loot_table/entities/boss_{key}.json", {"type": "minecraft:entity", "pools": [
            {"rolls": {"type": "minecraft:uniform", "min": 4, "max": 6}, "entries": END_COMMON if realm == "e" else NETHER_COMMON}] + SPECIAL[key]})

# ======================================================================= the island's Nether
fn("plot/nfields", f"""
# Nether plot = 64x64 centred on (cx/8, cz/8); writes the n* fields into storage nf
$scoreboard players set #a cs_tmp $(cx)
$scoreboard players set #b cs_tmp $(cz)
scoreboard players operation #a cs_tmp /= #8 cs_tmp
scoreboard players operation #b cs_tmp /= #8 cs_tmp
data modify storage {NS}:d nf set value {{}}
""" + "\n".join(
    f"scoreboard players operation #o cs_tmp = #{s} cs_tmp\nscoreboard players {'add' if d >= 0 else 'remove'} #o cs_tmp {abs(d)}\n"
    f"execute store result storage {NS}:d nf.{k} int 1 run scoreboard players get #o cs_tmp"
    for k, s, d in [("ncx", "a", 0), ("ncz", "b", 0), ("nx", "a", -32), ("nz", "b", -32), ("nx1", "a", 31), ("nz1", "b", 31),
                    ("nwx", "a", -32), ("nwz", "b", -32), ("nwx1", "a", 31), ("nwz1", "b", 31),
                    ("nix", "a", -3), ("niz", "b", -3), ("nix1", "a", 3), ("niz1", "b", 3)]))
fn("plot/nbuild", f"""
# load the Nether plot; the starter island waits until the chunks are in (plot/npend, checked every second)
$execute in minecraft:the_nether run forceload add $(nwx) $(nwz) $(nwx1) $(nwz1)
$scoreboard players set #p$(id) cs_npend 1
""")
fn("plot/npend_i", f"""
$data modify storage {NS}:d cur set from storage {NS}:d plots[$(i)]
function {NS}:plot/npend with storage {NS}:d cur
""")
nb = Build(9)
nb.blob(4, 4, "netherrack", "netherrack", "blackstone")
nb.fill(-2, 0, 1, -1, 0, 2, "soul_sand")
nb.set(-2, 1, 1, "nether_wart[age=3]")
nb.set(-1, 1, 2, "nether_wart[age=3]")
nb.set(2, 0, -2, "magma_block")
nb.set(1, -1, 2, "glowstone")
nb.set(2, 1, 2, "crimson_fungus")
nb.set(2, 0, 2, "crimson_nylium")
fn("plot/nisland", "\n".join(nb.c))
fn("plot/npend", f"""
$execute in minecraft:the_nether unless loaded $(nwx) {NFLOOR_Y} $(nwz) run return run execute in minecraft:the_nether run forceload add $(nwx) $(nwz) $(nwx1) $(nwz1)
$execute in minecraft:the_nether unless loaded $(nwx1) {NFLOOR_Y} $(nwz1) run return 0
$execute in minecraft:the_nether positioned $(ncx) {NFLOOR_Y} $(ncz) run function {NS}:plot/nisland
$execute in minecraft:the_nether positioned $(ncx) {NFLOOR_Y} $(ncz) positioned ~ ~ ~16 run function {NS}:nether/arena
$data modify storage {NS}:d plots[$(id)].narena set value 1b
$fillbiome $(nx) {NFLOOR_Y} $(nz) $(nx1) {NFLOOR_Y} $(nz1) minecraft:nether_wastes
$scoreboard players reset #p$(id) cs_npend
$execute unless score #p$(id) cs_nwas matches 1.. in minecraft:the_nether run forceload remove $(nwx) $(nwz) $(nwx1) $(nwz1)
""")
fort = "\n".join(f"$execute if score #p$(id) cs_nage matches {a} run data modify storage {NS}:d ev.sp set value \"minecraft:{m}\"\n"
                 f"$execute if score #p$(id) cs_nage matches {a} in minecraft:the_nether run function {NS}:nev/fortress with storage {NS}:d cur"
                 for a, m in FORTRESS_AGES)
bast = "\n".join(f"$execute if score #p$(id) cs_nage matches {a} in minecraft:the_nether run function {NS}:nev/bastion with storage {NS}:d cur" for a in BASTION_AGES)
fn("plot/ntick", f"""
# runs every second for an island with someone online; the Nether part only while a member is in it
$execute unless score #p$(id) cs_non matches 1.. if score #p$(id) cs_nwas matches 1.. in minecraft:the_nether run forceload remove $(nwx) $(nwz) $(nwx1) $(nwz1)
$execute unless score #p$(id) cs_non matches 1.. run return run scoreboard players set #p$(id) cs_nwas 0
$execute unless score #p$(id) cs_nwas matches 1.. in minecraft:the_nether run forceload add $(nwx) $(nwz) $(nwx1) $(nwz1)
$scoreboard players set #p$(id) cs_nwas 1
$scoreboard players add #p$(id) cs_nage 1
$execute unless data storage {NS}:d plots[$(id)].narena run function {NS}:nether/arena_retro with storage {NS}:d cur
$execute if score #p$(id) cs_nage matches 1 run tellraw @a[scores={{cs_plot=$(id)}}] [{{text:"🔥 ",color:"gold"}},{{text:"Welcome to your island's Nether. A fortress wreck with a blaze spawner crashes in after 2 minutes here; a bastion after 10.",color:"gold"}}]
{fort}
{bast}
$execute in minecraft:the_nether store result score #h cs_tmp if entity @e[type=#{NS}:nhostile,x=$(nx),y=0,z=$(nz),dx=63,dy=256,dz=63]
$execute in minecraft:the_nether if score #h cs_tmp matches {NHOSTILE_CAP+1}.. as @e[type=#{NS}:nhostile,tag=!cs_old,x=$(nx),y=0,z=$(nz),dx=63,dy=256,dz=63] run function {NS}:nmob_cull
$execute in minecraft:the_nether run tag @e[type=#{NS}:nhostile,tag=!cs_old,x=$(nx),y=0,z=$(nz),dx=63,dy=256,dz=63] add cs_old
""")
fn("nmob_cull", f"""
execute if score #h cs_tmp matches ..{NHOSTILE_CAP} run return 0
execute at @s run tp @s ~ -100 ~
scoreboard players remove #h cs_tmp 1
""")
def nspot():
    return (f"$execute store result storage {NS}:d ev.x int 1 run random value $(nix)..$(nix1)\n"
            f"$execute store result storage {NS}:d ev.z int 1 run random value $(niz)..$(niz1)\n"
            f"$data modify storage {NS}:d ev.id set value $(id)")
fn("nev/fortress", nspot() + f"\nfunction {NS}:nev/fortress_at with storage {NS}:d ev")
fn("nev/fortress_at", f"""
$execute positioned $(x) {NSPAWN_Y} $(z) positioned over motion_blocking_no_leaves run function {NS}:nev/fortress_build {{sp:"$(sp)"}}
$tellraw @a[scores={{cs_plot=$(id)}}] [{{text:"☄ ",color:"dark_red"}},{{text:"A Nether fortress wreck crashed into your island's Nether!",color:"red"}}]
$execute as @a[scores={{cs_plot=$(id)}}] at @s run playsound minecraft:entity.generic.explode master @s ~ ~ ~ 1 0.5
""")
fn("nev/fortress_build", """
fill ~-3 ~ ~-3 ~3 ~ ~3 minecraft:nether_bricks replace minecraft:air
fill ~-3 ~1 ~-3 ~3 ~4 ~3 minecraft:nether_bricks replace minecraft:air
fill ~-2 ~1 ~-2 ~2 ~3 ~2 minecraft:air replace minecraft:nether_bricks
fill ~-3 ~1 ~ ~-3 ~2 ~ minecraft:air replace minecraft:nether_bricks
fill ~3 ~1 ~ ~3 ~2 ~ minecraft:air replace minecraft:nether_bricks
fill ~-3 ~4 ~-3 ~3 ~4 ~3 minecraft:nether_brick_fence replace minecraft:nether_bricks
fill ~-2 ~4 ~-2 ~2 ~4 ~2 minecraft:nether_bricks replace minecraft:nether_brick_fence
$setblock ~ ~1 ~ minecraft:spawner{SpawnData:{entity:{id:"$(sp)"}}}
setblock ~2 ~1 ~2 minecraft:chest[facing=north]{LootTable:"minecraft:chests/nether_bridge"}
setblock ~-2 ~1 ~-2 minecraft:nether_wart
setblock ~-2 ~ ~-2 minecraft:soul_sand
setblock ~-1 ~1 ~-2 minecraft:nether_wart
setblock ~-1 ~ ~-2 minecraft:soul_sand
particle minecraft:explosion_emitter ~ ~2 ~ 0 0 0 0 1 force
""")
fn("nev/bastion", nspot() + f"\nfunction {NS}:nev/bastion_at with storage {NS}:d ev")
fn("nev/bastion_at", f"""
$execute positioned $(x) {NSPAWN_Y} $(z) positioned over motion_blocking_no_leaves run function {NS}:nev/bastion_build
$tellraw @a[scores={{cs_plot=$(id)}}] [{{text:"☄ ",color:"gold"}},{{text:"A bastion chunk crashed into your Nether, piglins and all. They trade for gold!",color:"gold"}}]
$execute as @a[scores={{cs_plot=$(id)}}] at @s run playsound minecraft:entity.piglin.celebrate master @s ~ ~ ~ 1 1
""")
fn("nev/bastion_build", """
fill ~-3 ~ ~-3 ~3 ~ ~3 minecraft:polished_blackstone_bricks replace minecraft:air
fill ~-3 ~1 ~-3 ~3 ~3 ~3 minecraft:blackstone replace minecraft:air
fill ~-2 ~1 ~-2 ~2 ~3 ~2 minecraft:air replace minecraft:blackstone
fill ~-3 ~1 ~-1 ~-3 ~2 ~1 minecraft:air replace minecraft:blackstone
fill ~3 ~1 ~-1 ~3 ~2 ~1 minecraft:air replace minecraft:blackstone
setblock ~2 ~ ~-2 minecraft:gold_block
setblock ~-2 ~ ~2 minecraft:gilded_blackstone
setblock ~2 ~1 ~2 minecraft:chest[facing=north]{LootTable:"minecraft:chests/bastion_other"}
summon minecraft:piglin ~ ~1 ~ {IsImmuneToZombification:1b,PersistenceRequired:1b}
summon minecraft:piglin ~1 ~1 ~-1 {IsImmuneToZombification:1b,PersistenceRequired:1b}
particle minecraft:explosion_emitter ~ ~2 ~ 0 0 0 0 1 force
""")
fn("p/nbounds_all", f"execute as @a[gamemode=survival,tag=!cs_staff] at @s if dimension minecraft:the_nether run function {NS}:p/nbounds")
fn("p/nbounds", f"""
execute unless score @s cs_plot matches 1.. run return run function {NS}:act/hub
function {NS}:p/ctx
function {NS}:p/nbounds2 with storage {NS}:d cur
""")
fn("p/nbounds2", f"""
$execute if entity @s[x=$(nx),y=-64,z=$(nz),dx=63,dy=400,dz=63] run return 0
$execute in minecraft:the_nether positioned $(ncx) {NSPAWN_Y} $(ncz) positioned over motion_blocking run tp @s ~0.5 ~ ~0.5
tellraw @s {{text:"You can't leave your island's Nether.",color:"red"}}
""")

# ======================================================================= creating islands
pick_lines = "\n".join(f"execute if score @s cs_act matches {101 + n} run data modify storage {NS}:d new.theme set value \"{k}\"\n"
                       f"execute if score @s cs_act matches {101 + n} run data modify storage {NS}:d new.b set value \"{biome}\""
                       for n, (k, _, biome, *_r) in enumerate(ISLANDS))
fn("act/pick", f"""
# a starter island was picked in the menu (cs_act 101..): first island, or a fresh start after "Start a new island"
execute if score @s cs_plot matches 1.. unless entity @s[tag=cs_new] run return run function {NS}:p/home
execute if entity @s[tag=cs_new] run function {NS}:p/wipe
tag @s remove cs_new
data modify storage {NS}:d new set value {{}}
{pick_lines}
function {NS}:plot/create
""")
fn("p/wipe", """
clear @s
""" + "\n".join(f"item replace entity @s enderchest.{i} with minecraft:air" for i in range(27)) + """
xp set @s 0 levels
xp set @s 0 points
effect clear @s
""")
fn("plot/create", f"""
scoreboard players add #next cs_tmp 1
scoreboard players operation @s cs_plot = #next cs_tmp
scoreboard players operation #c cs_tmp = #next cs_tmp
scoreboard players operation #c cs_tmp %= #64 cs_tmp
scoreboard players operation #c cs_tmp *= #grid cs_tmp
scoreboard players operation #r cs_tmp = #next cs_tmp
scoreboard players operation #r cs_tmp /= #64 cs_tmp
scoreboard players operation #r cs_tmp *= #grid cs_tmp
scoreboard players add #r cs_tmp {2 * GRID}
execute store result storage {NS}:d new.id int 1 run scoreboard players get #next cs_tmp
execute store result storage {NS}:d new.x int 1 run scoreboard players get #c cs_tmp
execute store result storage {NS}:d new.z int 1 run scoreboard players get #r cs_tmp
""" + "\n".join(
    f"scoreboard players operation #o cs_tmp = #{s} cs_tmp\nscoreboard players {'add' if d >= 0 else 'remove'} #o cs_tmp {abs(d)}\n"
    f"execute store result storage {NS}:d new.{k} int 1 run scoreboard players get #o cs_tmp"
    for k, s, d in [("x1", "c", SIZE - 1), ("z1", "r", SIZE - 1), ("cx", "c", SIZE // 2), ("cz", "r", SIZE // 2),
                    ("ix", "c", SIZE // 2 - R), ("iz", "r", SIZE // 2 - R), ("ix1", "c", SIZE // 2 + R), ("iz1", "r", SIZE // 2 + R)]) + f"""
function {NS}:plot/nfields with storage {NS}:d new
data modify storage {NS}:d new merge from storage {NS}:d nf
data modify storage {NS}:d new.portal set value 1b
data modify storage {NS}:d plots append from storage {NS}:d new
function {NS}:plot/build with storage {NS}:d new
function {NS}:plot/nbuild with storage {NS}:d new
function {NS}:p/home
island refreshboard
tellraw @s [{{text:"Welcome to your island! ",color:"gold",bold:1b}},{{text:"Check the chest, then get a cobblestone generator going.",color:"yellow",bold:0b}}]
tellraw @s {{text:"Esc → Island Menu for challenges, your island level and invites. The sky drops the odd gift while you're online.",color:"gray"}}
""")
fn("plot/build", f"""
$forceload add $(x) $(z) $(x1) $(z1)
$execute positioned $(cx) {ISLAND_Y} $(cz) run function {NS}:island/$(theme)
$execute positioned $(cx) {ISLAND_Y} $(cz) positioned ~ ~ ~{PORTAL_DZ} run function {NS}:portal/build
function {NS}:island/biome with storage {NS}:d new
""")
# the island's hub portal, out over the void: players bridge to it. Run positioned at the platform centre.
pb = Build(0)
pb.fill(-2, 0, -2, 2, 0, 2, "reinforced_deepslate")
pb.fill(-1, 0, -1, 1, 0, 1, "obsidian")
pb.fill(-1, -1, -1, 1, -1, 1, "reinforced_deepslate")
pb.fill(-2, 1, 0, -2, 4, 0, "crying_obsidian")
pb.fill(2, 1, 0, 2, 4, 0, "crying_obsidian")
pb.fill(-1, 4, 0, 1, 4, 0, "crying_obsidian")
pb.fill(-1, 1, 0, 1, 3, 0, "air")
pb.set(0, 5, 0, "amethyst_cluster[facing=up]")
pb.set(-2, 5, 0, "end_rod[facing=up]")
pb.set(2, 5, 0, "end_rod[facing=up]")
fn("portal/build", "\n".join(pb.c) + "\n" + "summon minecraft:text_display ~0.5 ~6 ~0.5 " + snbt({
    "Tags": [NS, "cs_portall"], "billboard": "center", "background": 1073741824, "shadow": True,
    "text": {"text": "Hub Portal", "color": "light_purple", "bold": True, "extra": [txt("\nBuild a bridge, then walk through", "gray", bold=False)]},
    "transformation": {"left_rotation": [0.0, 0.0, 0.0, 1.0], "right_rotation": [0.0, 0.0, 0.0, 1.0], "translation": [0.0, 0.0, 0.0], "scale": [0.9, 0.9, 0.9]}}).replace("0.0,", "0.0f,").replace("1.0]", "1.0f]").replace("0.9,", "0.9f,").replace("0.9]", "0.9f]").replace("0.0]", "0.0f]"))
fn("portal/retro", f"""
# islands made before portals existed get theirs the next time a member is there
$execute positioned $(cx) {ISLAND_Y} $(cz) positioned ~ ~ ~{PORTAL_DZ} run function {NS}:portal/build
$data modify storage {NS}:d plots[$(id)].portal set value 1b
$tellraw @a[scores={{cs_plot=$(id)}}] [{{text:"✦ ",color:"light_purple"}},{{text:"A Hub Portal appeared just north of your island. Build a bridge to it!",color:"light_purple"}}]
""")

# ======================================================================= per-player helpers
fn("p/ctx", f"""
execute store result storage {NS}:d q.i int 1 run scoreboard players get @s cs_plot
function {NS}:p/ctx2 with storage {NS}:d q
""")
fn("p/ctx2", f"$data modify storage {NS}:d cur set from storage {NS}:d plots[$(i)]")
fn("p/home", f"""
function {NS}:p/ctx
function {NS}:p/home2 with storage {NS}:d cur
""")
fn("p/home2", f"""
$forceload add $(x) $(z) $(x1) $(z1)
# the spawn spot on top of the starter island; if something was built there, the highest block instead
$execute in minecraft:overworld positioned $(cx) {ISLAND_Y + 1} $(cz) if block ~ ~ ~ minecraft:air if block ~ ~1 ~ minecraft:air unless block ~ ~-1 ~ minecraft:air run return run function {NS}:p/home3
$execute in minecraft:overworld positioned $(cx) 318 $(cz) positioned over motion_blocking run tp @s ~0.5 ~ ~0.5
gamemode survival @s
""")
fn("p/home3", "tp @s ~0.5 ~ ~0.5\ngamemode survival @s")
fn("p/respawned", f"""
scoreboard players reset @s cs_die
execute unless score @s cs_plot matches 1.. run return 0
function {NS}:p/ctx
function {NS}:p/respawned2 with storage {NS}:d cur
""")
fn("p/respawned2", f"$execute unless entity @s[x=$(x),y=-64,z=$(z),dx={SIZE-1},dy=400,dz={SIZE-1}] run function {NS}:p/home")
fn("p/bounds_all", f"execute as @a[gamemode=survival,tag=!cs_staff] at @s if dimension minecraft:overworld unless entity @s[x=-{HUB_R},y={Y-45},z=-{HUB_R},dx={2*HUB_R},dy=90,dz={2*HUB_R}] run function {NS}:p/bounds")
fn("p/bounds", f"""
execute unless score @s cs_plot matches 1.. run return run function {NS}:act/hub
function {NS}:p/ctx
function {NS}:p/bounds2 with storage {NS}:d cur
""")
fn("p/bounds2", f"""
$execute if entity @s[x=$(x),y=-128,z=$(z),dx={SIZE-1},dy=500,dz={SIZE-1}] run return 0
function {NS}:p/home
tellraw @s {{text:"That's the edge of your island's space.",color:"red"}}
""")
fn("first_join", f"""
scoreboard players set @s cs_seen 1
function {NS}:act/hub
tellraw @s [{{text:"Welcome to Crispy Skyblock! ",color:"gold",bold:1b}},{{text:"Click ",color:"yellow",bold:0b}},{{text:"[Pick my island]",color:"green",bold:1b,click_event:{{action:"run_command",command:"trigger cs_act set 1"}},hover_event:{{action:"show_text",value:"Choose a starter island and go there"}}}}]
""")

# ======================================================================= menu actions
ACTS = {1: "act/home", 3: "act/accept", 4: "act/new", 5: "act/hub", 6: "act/info", 7: "act/menu", 8: "act/hub_help"}
fn("act/dispatch", "\n".join(f"execute if score @s cs_act matches {n} run function {NS}:{f}" for n, f in ACTS.items()) +
   f"\nexecute if score @s cs_act matches 101..{100 + len(ISLANDS)} run function {NS}:act/pick\n" +
   "\n".join(f"execute if score @s cs_act matches {200 + i} run function {NS}:ch/{k}" for i, (k, *_r) in enumerate(CH)) +
   "\nscoreboard players set @s cs_act 0")
fn("act/menu", f"dialog show @s {NS}:menu")
fn("act/home", f"""
execute unless score @s cs_plot matches 1.. run return run function {NS}:act/choose
function {NS}:p/home
""")
fn("act/choose", "execute as @s run island choose")
fn("act/hub", f"execute in minecraft:overworld run tp @s {HUB_SPAWN[0]} {HUB_SPAWN[1]} {HUB_SPAWN[2]} 180 0")
fn("act/invite_player", f"""
execute unless score @s cs_plot matches 1.. run return run tellraw @s {{text:"Pick an island first.",color:"red"}}
tag @s add cs_me
$execute as @a[name="$(name)",tag=!cs_me,limit=1] run function {NS}:act/invite_to
tag @s remove cs_me
""")
fn("act/invite_to", f"""
execute if score @s cs_plot = @a[tag=cs_me,limit=1] cs_plot run return run tellraw @a[tag=cs_me] {{text:"They're already on your island.",color:"yellow"}}
scoreboard players operation @s cs_inv = @a[tag=cs_me,limit=1] cs_plot
tellraw @a[tag=cs_me] [{{text:"Invite sent to ",color:"green"}},{{selector:"@s",color:"gold"}}]
tellraw @s [{{selector:"@a[tag=cs_me]",color:"gold"}},{{text:" invited you to their island. ",color:"green"}},{{text:"[Accept]",color:"aqua",bold:1b,click_event:{{action:"run_command",command:"trigger cs_act set 3"}},hover_event:{{action:"show_text",value:"Join their island (you will leave yours)"}}}}]
""")
fn("act/accept", f"""
execute unless score @s cs_inv matches 1.. run return run tellraw @s {{text:"You have no pending invite.",color:"red"}}
scoreboard players operation @s cs_plot = @s cs_inv
scoreboard players reset @s cs_inv
function {NS}:p/ctx
function {NS}:act/accept2 with storage {NS}:d cur
function {NS}:p/home
""")
fn("act/accept2", f"$tellraw @a[scores={{cs_plot=$(id)}}] [{{selector:\"@s\",color:\"gold\"}},{{text:\" joined the island!\",color:\"green\"}}]")
fn("act/new", f"""
execute if score @s cs_cd matches 1.. run return run tellraw @s [{{text:"You can start a new island again in ",color:"red"}},{{score:{{name:"@s",objective:"cs_cd"}}}},{{text:"s.",color:"red"}}]
scoreboard players set @s cs_cd 600
tag @s add cs_new
tellraw @s {{text:"Pick your new starter island. Your inventory, ender chest and XP are wiped when you pick.",color:"yellow"}}
function {NS}:act/choose
""")
fn("act/info", f"""
execute unless score @s cs_plot matches 1.. run return run tellraw @s {{text:"You don't have an island yet.",color:"red"}}
function {NS}:p/ctx
function {NS}:act/info2 with storage {NS}:d cur
""")
fn("act/info2", f"""
$scoreboard players operation #m cs_tmp = #p$(id) cs_age
scoreboard players operation #m cs_tmp /= #60 cs_tmp
$tellraw @s [{{text:"Island #$(id)",color:"gold",bold:1b}},{{text:"  play time: ",color:"gray",bold:0b}},{{score:{{name:"#m",objective:"cs_tmp"}},color:"white"}},{{text:" min",color:"gray"}}]
$tellraw @s [{{text:"Island level: ",color:"gray"}},{{score:{{name:"#p$(id)",objective:"cs_lvl"}},color:"white"}},{{text:" (update with /island level)",color:"dark_gray"}}]
$tellraw @s [{{text:"Online members: ",color:"gray"}},{{selector:"@a[scores={{cs_plot=$(id)}}]",color:"green"}}]
tellraw @s {{text:"Supply crates every 25 min of play, meteors every 45, an animal every 15. Dungeons crash in at 30, 90 and 180 min; the End portal at 150.",color:"dark_gray"}}
""")
fn("act/hub_help", f"""
tellraw @s {{text:"— How to play Crispy Skyblock —",color:"gold",bold:1b}}
tellraw @s {{text:"• Pick a starter island (each has its own biome and chest). Don't fall off: the void is forever.",color:"yellow"}}
tellraw @s {{text:"• Use the lava and ice from your chest to build a cobblestone generator, then grow your island.",color:"yellow"}}
tellraw @s {{text:"• The sky still drops gifts while you're online: supply crates, meteors full of ore, animals, dungeons and later an End portal.",color:"yellow"}}
tellraw @s {{text:"• Build a Nether portal to reach your island's own Nether: fortress wrecks bring blaze spawners.",color:"yellow"}}
tellraw @s {{text:"• /island challenges: hand in items for rewards. /island level: score your island. /island top: the best islands.",color:"yellow"}}
tellraw @s {{text:"• Coins: sell what you gather to the merchants in the hub (right-click them). /coins shows your purse, /pay sends coins.",color:"yellow"}}
tellraw @s {{text:"• Minions: craft one with 8 of a resource around a wooden pickaxe, place it on your island and it gathers for you, even offline. Right-click it to collect or upgrade.",color:"yellow"}}
tellraw @s {{text:"• Esc → Island Menu: go home, invite a player (or /invite <name>), accept invites, start over.",color:"yellow"}}
""")

# ======================================================================= dialogs
def btn(label_, cmd=None, tip=None, dialog=None, width=200):
    a = {"type": "minecraft:show_dialog", "dialog": dialog} if dialog else {"type": "minecraft:run_command", "command": cmd}
    b = {"label": label_, "action": a, "width": width}
    if tip: b["tooltip"] = {"text": tip}
    return b
js(f"data/{NS}/dialog/menu.json", {
    "type": "minecraft:multi_action", "title": {"text": "Island Menu", "color": "gold", "bold": True},
    "external_title": {"text": "Island Menu"},
    "body": [{"type": "minecraft:plain_message", "contents": {"text": "Grow your island, finish challenges and climb the top islands board."}}],
    "actions": [
        btn({"text": "Go to my island", "color": "green"}, "trigger cs_act set 1", "Pick your starter island the first time"),
        btn({"text": "Challenges", "color": "gold"}, "island challenges", "Hand in items for rewards"),
        btn({"text": "Island level"}, "island level", "Score the blocks on your island"),
        btn({"text": "Top islands"}, "island top"),
        btn({"text": "Invite a player…"}, dialog=f"{NS}:invite", tip="Type their username (or use /invite <name>)"),
        btn({"text": "Accept invite"}, "trigger cs_act set 3"),
        btn({"text": "Island info"}, "trigger cs_act set 6"),
        btn({"text": "Go to hub"}, "trigger cs_act set 5"),
        btn({"text": "How to play"}, "trigger cs_act set 8"),
        btn({"text": "Start a new island…", "color": "red"}, dialog=f"{NS}:confirm_new"),
    ],
    "columns": 2, "exit_action": {"label": {"text": "Close"}, "width": 200},
    "can_close_with_escape": True, "pause": False, "after_action": "close"})
js(f"data/{NS}/dialog/invite.json", {
    "type": "minecraft:notice", "title": {"text": "Invite a player", "color": "gold", "bold": True},
    "body": [{"type": "minecraft:plain_message", "contents": {"text": "They must be online on Skyblock. They get an [Accept] button in chat. You can also type /invite <name>."}}],
    "inputs": [{"type": "minecraft:text", "key": "player", "label": {"text": "Username"}, "width": 200, "max_length": 32}],
    "action": {"label": {"text": "Send invite", "color": "green"}, "width": 200,
               "action": {"type": "minecraft:dynamic/run_command", "template": "invite $(player)"}},
    "can_close_with_escape": True, "pause": False, "after_action": "close"})
js(f"data/{NS}/dialog/confirm_new.json", {
    "type": "minecraft:confirmation", "title": {"text": "Start a new island?", "color": "red", "bold": True},
    "body": [{"type": "minecraft:plain_message", "contents": {"text": "You pick a new starter island and leave your current one (teammates keep it). Your inventory, ender chest and XP are wiped. You can do this once every 10 minutes."}}],
    "yes": {"label": {"text": "Yes, start over", "color": "red"}, "action": {"type": "minecraft:run_command", "command": "trigger cs_act set 4"}},
    "no": {"label": {"text": "Cancel"}},
    "can_close_with_escape": True, "pause": False, "after_action": "close"})

# ======================================================================= loot
def e(it, w_, lo=1, hi=1):
    d = {"type": "minecraft:item", "name": f"minecraft:{it}", "weight": w_}
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
js(f"data/{NS}/loot_table/chests/supply.json", {"type": "minecraft:chest", "pools": [
    {"rolls": {"type": "minecraft:uniform", "min": 4, "max": 7}, "entries": [
        e("dirt", 10, 4, 12), e("sand", 8, 4, 12), e("gravel", 6, 4, 8), e("clay_ball", 6, 4, 12), e("bone_meal", 8, 4, 10),
        e("oak_sapling", 5, 1, 3), e("birch_sapling", 4, 1, 2), e("spruce_sapling", 4, 1, 2), e("jungle_sapling", 3, 1, 2),
        e("acacia_sapling", 3, 1, 2), e("cherry_sapling", 2), e("wheat_seeds", 6, 2, 6), e("melon_seeds", 3), e("pumpkin_seeds", 3),
        e("carrot", 4, 1, 3), e("potato", 4, 1, 3), e("sugar_cane", 4, 1, 3), e("cactus", 3), e("cocoa_beans", 2, 1, 3),
        e("iron_ingot", 6, 1, 4), e("string", 4, 2, 6), e("leather", 3, 1, 4), e("ice", 4, 1, 2), e("lava_bucket", 2),
        e("redstone", 3, 2, 8), e("emerald", 2, 1, 3), e("name_tag", 1), e("lead", 2), e("glow_berries", 2, 1, 3),
        e("kelp", 2, 1, 3), e("lily_pad", 2), e("vine", 2, 1, 3), e("moss_block", 2, 1, 3)]},
    {"rolls": 1, "entries": [
        e("cow_spawn_egg", 4), e("sheep_spawn_egg", 4), e("chicken_spawn_egg", 4), e("pig_spawn_egg", 3), e("bee_spawn_egg", 2),
        e("villager_spawn_egg", 1), {"type": "minecraft:empty", "weight": 22}]}]})

# ======================================================================= advancements tab
def has(it): return {"c": {"trigger": "minecraft:inventory_changed", "conditions": {"items": [{"items": it}]}}}
ADV = [  # key, parent, icon, title, description, criteria, frame
    ("root", None, "grass_block", "Crispy Skyblock", "An island, a chest and the void", {"t": {"trigger": "minecraft:tick"}}, "task"),
    ("wood", "root", "oak_log", "Getting Wood", "Chop your first log", has("#minecraft:logs"), "task"),
    ("stone", "wood", "cobblestone", "Generator", "Get cobblestone from a generator", has("minecraft:cobblestone"), "task"),
    ("water", "stone", "water_bucket", "Ice to Meet You", "Fill a bucket with water", has("minecraft:water_bucket"), "task"),
    ("bread", "water", "bread", "Bread Winner", "Bake bread from your own wheat", has("minecraft:bread"), "task"),
    ("iron", "stone", "iron_ingot", "Heavy Metal", "Smelt an iron ingot", has("minecraft:iron_ingot"), "task"),
    ("diamond", "iron", "diamond", "Sky High Diamonds", "Get a diamond", has("minecraft:diamond"), "goal"),
    ("supply", "root", "barrel", "Special Delivery", "Open a supply crate from the sky",
     {"c": {"trigger": "minecraft:player_generates_container_loot", "conditions": {"loot_table": f"{NS}:chests/supply"}}}, "task"),
    ("dungeon", "stone", "mossy_cobblestone", "Crash Site", "Loot a fallen dungeon",
     {"c": {"trigger": "minecraft:player_generates_container_loot", "conditions": {"loot_table": f"{NS}:chests/dungeon"}}}, "task"),
    ("bed", "wood", "red_bed", "Safe Landing", "Sleep in a bed on your island", {"c": {"trigger": "minecraft:slept_in_bed"}}, "task"),
    ("breed", "wood", "wheat", "Animal Farm", "Breed two animals", {"c": {"trigger": "minecraft:bred_animals"}}, "task"),
    ("trade", "dungeon", "emerald", "Village People", "Trade with a villager", {"c": {"trigger": "minecraft:villager_trade"}}, "task"),
    ("nether", "iron", "obsidian", "Into the Fire", "Enter your island's Nether",
     {"c": {"trigger": "minecraft:changed_dimension", "conditions": {"to": "minecraft:the_nether"}}}, "task"),
    ("blaze", "nether", "blaze_rod", "Hot Stuff", "Get a blaze rod", has("minecraft:blaze_rod"), "task"),
    ("eye", "blaze", "ender_eye", "Eyes on the Sky", "Craft an Eye of Ender", has("minecraft:ender_eye"), "task"),
    ("end", "eye", "end_stone", "The End?", "Enter the End through your island's portal",
     {"c": {"trigger": "minecraft:changed_dimension", "conditions": {"to": "minecraft:the_end"}}}, "goal"),
    ("dragon", "end", "dragon_head", "Sky Fall", "Defeat the Ender Dragon",
     {"c": {"trigger": "minecraft:player_killed_entity", "conditions": {"entity": [{"condition": "minecraft:entity_properties", "entity": "this", "predicate": {"minecraft:entity_type": "minecraft:ender_dragon"}}]}}}, "challenge"),
    ("elytra", "end", "elytra", "Falling With Style", "Find an Elytra", has("minecraft:elytra"), "goal"),
    ("beacon", "blaze", "beacon", "Lighthouse", "Build a beacon", {"c": {"trigger": "minecraft:construct_beacon"}}, "challenge"),
]
for key, parent, icon, title, desc, crit, frame in ADV:
    d = {"display": {"icon": {"id": f"minecraft:{icon}"}, "title": {"text": title}, "description": {"text": desc}, "frame": frame,
                     "show_toast": key != "root", "announce_to_chat": key != "root", "hidden": False},
         "criteria": crit}
    if parent: d["parent"] = f"{NS}:{parent}"
    else: d["display"]["background"] = "minecraft:gui/advancements/backgrounds/stone"
    js(f"data/{NS}/advancement/{key}.json", d)

print(f"islands: {len(ISLANDS)}; challenges: {len(CH)}; advancements: {len(ADV)}")
