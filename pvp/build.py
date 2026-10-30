#!/usr/bin/env python3
"""Builds the crispy_pvp datapack (the Multiverse server, was "Crispy PvP"; Fabric 26.2, vanilla clients).

    python3 build.py [outdir]      -> <outdir>/crispy_pvp  (default: ./dist)

Kit/arena PvP plus "Outbreak", a CoD-zombies style wave mode, both using Anarchy's custom enchants
(crispy_enchants) and cyberware (crispy_cyberware built with --pvp, so implants don't drop).
Menus are chest screens opened with /pvpmenu (crispy-pvp-spawn mod) from storage pvp:menus.
"""
import json
import math
import abilities, arena_map, arena_maps, outbreak_maps, os, random, shutil, sys, tower
import micro

NS = "pvp"
PACK_FORMAT = [107, 0], [107, 1]

LOBBY_Y = 100                  # lobby floor; players stand at LOBBY_Y + 1, centred on 0,0
LOBBY_R = 11                   # lobby platform half-size
AY = -61                       # arena floors (superflat grass level); players stand at AY + 1
ACX, ACZ, AR = 0, 100, 40      # PvP arena centre and floor radius (a round colosseum: arena_map.py)
PCX, PCZ, PR = 0, 300, 32      # Outbreak (PvE) arena centre and half-size (outer walls at ±33)
KIT_NPC = (-3.5, LOBBY_Y + 1, -6.5)
PVE_NPC = (4.5, LOBBY_Y + 1, -6.5)
TOWER_NPC = (0.5, LOBBY_Y + 1, -7.5)   # between the two, under the board
SHOP_NPC = (PCX + 0.5, AY + 2, PCZ + 0.5)

def box(cx, cz, r, y0, dy): return f"x={cx - r - 1},y={y0},z={cz - r - 1},dx={2 * r + 2},dy={dy},dz={2 * r + 2}"
# admin room under the lobby: chests of every custom enchant (max-level books) and every cyberware item
ROOM_Y = LOBBY_Y - 10                # room floor; interior ROOM_Y+1..ROOM_Y+4
ROOM_BOX = f"x=-10,y={ROOM_Y},z=-5,dx=20,dy=6,dz=10"
ENCHANTS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "enchants.json")))   # from crispy_enchants
IMPLANT_KEYS = ["kiroshi", "subdermal", "titanium", "lungs", "gorilla", "mantis", "tendons", "lynx", "grip", "reflex", "biomon",
                "heart", "sandy", "berserk", "launcher", "cyberskeleton", "neuro"]   # cyber:item/<key> loot tables (cyberskeleton: PvP test-only)
VELOCITY_MAX, VELOCITY_CAP = 5, 20   # Velocity enchant: +20% arrow speed per level; levels above the cap (via /fe) count as the cap
LOBBY_BOX = box(0, 0, LOBBY_R, LOBBY_Y, 20)   # from the floor up: Micro Outbreak's arena is just below it
ARENA_BOX = box(ACX, ACZ, AR, AY - 1, 35)
STANDS_BOX = box(ACX, ACZ, arena_map.EXTENT - 1, AY - 1, 40)   # the colosseum stands, for spectators (tag pvp.spec)
# the arena rotation: the Colosseum (1) and the themed maps (arena_maps.py), each built at its own spot; every ROT_SECS
# the arena moves on to the next one and everyone fighting (or watching) goes with it
ROT_SECS = 600
ARENA_MAPS = [(1, "colosseum", "The Colosseum", "gold", "Ancient Rome")] + [m[:5] for m in arena_maps.MAPS]
MAP_AT = {1: (ACX, ACZ), **{m[0]: (-700, -400 + 100 * (m[0] - 2)) for m in arena_maps.MAPS}}
ARENA_BOXES = {1: ARENA_BOX, **{i: box(x, z, arena_maps.R + 1, AY - 1, 35) for i, (x, z) in MAP_AT.items() if i > 1}}
STANDS_BOXES = {1: STANDS_BOX, **{i: box(x, z, arena_maps.R + 4, AY - 1, 40) for i, (x, z) in MAP_AT.items() if i > 1}}
SPEC_PORTAL = (10, LOBBY_Y + 1, -1)   # lobby portal to the stands: east side, 3 wide (z -1..1), 3 high
# Outbreak maps: same size and layout (spawns, mob windows, Arsenal in the middle), 100 blocks apart along z.
# id, key, name, colour, menu icon, centre z, extra mobs (min wave, roll <=, type, extra NBT) tried before the normal pool
OUTBREAK_MAPS = [
    (1, "ruins", "Ruins", "green", "mossy_stone_bricks", 300, []),
    (2, "mine", "Toxic Mine", "yellow", "rail", 400,
     [(2, 14, "cave_spider", ""), (4, 20, "silverfish", "")]),
    (3, "neon", "Neon City", "light_purple", "magenta_stained_glass", 500,
     [(3, 14, "pillager", ',equipment:{mainhand:{id:"minecraft:crossbow",count:1}},drop_chances:{mainhand:0.0f}'),
      (5, 22, "vindicator", ',equipment:{mainhand:{id:"minecraft:iron_axe",count:1}},drop_chances:{mainhand:0.0f}')]),
    (4, "hellfort", "Hellfort", "red", "nether_bricks", 600,
     [(3, 12, "wither_skeleton", ',equipment:{mainhand:{id:"minecraft:stone_sword",count:1}},drop_chances:{mainhand:0.0f}'),
      (4, 20, "blaze", "")]),
    (5, "orbital", "Orbital Station", "aqua", "end_rod", 700,
     [(2, 12, "endermite", ""), (4, 20, "stray", ',equipment:{mainhand:{id:"minecraft:bow",count:1}},drop_chances:{mainhand:0.0f}')]),
    # Halloween only (the Haunted Night NPC; not in the map menu or Random): its own mob roster, rolls up to 100 so the
    # normal pool is never used
    (6, "haunted", "Haunted Night", "gold", "jack_o_lantern", 800,
     [(1, 28, "zombie", ',CustomName:{text:"Pumpkinhead",color:"gold"},equipment:{head:{id:"minecraft:carved_pumpkin",count:1}},drop_chances:{head:0.0f}'),
      (2, 42, "skeleton", ',CustomName:{text:"Restless Bones",color:"gray"},equipment:{mainhand:{id:"minecraft:bow",count:1},head:{id:"minecraft:jack_o_lantern",count:1}},drop_chances:{mainhand:0.0f,head:0.0f}'),
      (2, 52, "spider", ',CustomName:{text:"Graveyard Spider",color:"dark_red"}'),
      (3, 62, "witch", ',CustomName:{text:"Witch",color:"dark_purple"}'),
      (4, 72, "vex", ',CustomName:{text:"Ghost",color:"white"}'),
      (5, 80, "zombie_villager", ',CustomName:{text:"Ghoul",color:"dark_green"}'),
      (6, 88, "wither_skeleton", ',CustomName:{text:"Reaper",color:"dark_gray"},equipment:{mainhand:{id:"minecraft:stone_hoe",count:1}},drop_chances:{mainhand:0.0f}'),
      (7, 94, "creeper", ',CustomName:{text:"Jack-o-Creeper",color:"gold"}'),
      (1, 100, "zombie", ',CustomName:{text:"Pumpkinhead",color:"gold"},equipment:{head:{id:"minecraft:carved_pumpkin",count:1}},drop_chances:{head:0.0f}')]),
]
NORMAL_MAPS = OUTBREAK_MAPS[:5]   # the Outbreak NPC's maps (and Random)
PVE_BOXES = {m[0]: box(PCX, m[5], PR, AY - 1, 35) for m in OUTBREAK_MAPS}
PVE_BOX = PVE_BOXES[1]
BREAK_TICKS = 400        # break between waves
PVE_LOBBY_IDLE = 300     # s an Outbreak lobby may stay open without being started before it closes (downed players are back at its start, so they can re-buy)
MAP_LORE = {
    "ruins": ["Overgrown temple courtyard", "Broken colonnade, fallen columns", "Mobs: the classic horde"],
    "mine": ["Abandoned toxic mine", "Rock outcrops, mine-cart loop", "Sludge puddles slow you down", "Extra: cave spiders, silverfish"],
    "neon": ["Night-time crossroads", "Tower, noodle bar, car park, arcade", "Extra: pillagers, vindicators"],
    "hellfort": ["Nether keep with four gates", "Lava pools, basalt, a giant ribcage", "Extra: wither skeletons, blazes"],
    "haunted": ["A moonlit graveyard around a ruined chapel", "Tombstones, a crypt, a pumpkin patch", "10 waves, then it's over: survive them all",
                "Bosses: The Scarecrow (wave 5), the Headless Horseman (wave 10)"],
    "orbital": ["A roofed, wheel-shaped space station", "Round hub, four wide spokes, an outer ring", "Labs, cryo pods, server racks, hydroponics", "Mobs come in from the ring", "Extra: endermites, strays"],
}
POWERUP_CHANCE = 4       # % of kills that drop a power-up
POWERUP_SECS = 30        # Insta-Kill / Double Points length
POWERUPS = [  # key, item, name, colour
    ("ammo", "spectral_arrow", "MAX AMMO", "aqua"), ("insta", "wither_skeleton_skull", "INSTA-KILL", "red"),
    ("double", "experience_bottle", "DOUBLE POINTS", "yellow"), ("nuke", "tnt", "NUKE", "gold")]

# PvP spawn points: offset from the centre, yaw facing the centre
SPAWNS = arena_map.SPAWNS   # radius 32, facing the centre
# PvP cover: (x1, z1, x2, z2, height, stripe colour, hollow-with-doors) offsets from the arena centre
BUILDINGS = [
    (-3, -3, 3, 3, 10, "cyan", True),
    (-15, -15, -9, -9, 6, "magenta", True), (9, -15, 15, -9, 4, "yellow", True),
    (-15, 9, -9, 15, 4, "yellow", True), (9, 9, 15, 15, 6, "magenta", True),
    (-2, -18, 2, -17, 3, "light_blue", False), (-2, 17, 2, 18, 3, "light_blue", False),
    (-18, -2, -17, 2, 3, "light_blue", False), (17, -2, 18, 2, 3, "light_blue", False),
    (-8, -1, -7, 1, 2, "lime", False), (7, -1, 8, 1, 2, "lime", False),
    (-1, -8, 1, -7, 2, "lime", False), (-1, 7, 1, 8, 2, "lime", False),
]
ARENA_TRIM = {"cyan": "chiseled_sandstone", "magenta": "cut_red_sandstone", "yellow": "chiseled_red_sandstone",
              "light_blue": "cut_sandstone", "lime": "red_sandstone"}   # building colour -> colosseum trim block
# Outbreak: player spawns around the Arsenal, mob windows just inside the walls, ruins for cover
PVE_SPAWNS = [(4, 4, -45), (-4, 4, 45), (4, -4, -135), (-4, -4, 135)]
MOB_POINTS = [(30, 0), (-30, 0), (0, 30), (0, -30), (30, 16), (30, -16), (-30, 16), (-30, -16), (16, 30), (-16, 30), (16, -30), (-16, -30)]
# a map that isn't a square courtyard has its own mob points (the same number): the Orbital Station's are on its ring
MAP_POINTS = {"orbital": outbreak_maps.ORBITAL_POINTS}
def map_points(key): return MAP_POINTS.get(key, MOB_POINTS)
# where downed players float (spectating): high over open maps, inside the hub under the Orbital Station's roof
DOWNED_Y = {"orbital": outbreak_maps.ORBITAL_DOWNED_Y}
def downed_y(key): return DOWNED_Y.get(key, 12)
RUINS = [(-12, -12, -8, -11, 3, "mossy_stone_bricks"), (8, -14, 9, -8, 2, "cobblestone"), (-14, 6, -13, 12, 3, "stone_bricks"),
         (10, 10, 14, 11, 2, "mossy_cobblestone"), (-4, 14, 4, 15, 2, "cracked_stone_bricks"), (-4, -16, 4, -15, 2, "cracked_stone_bricks"),
         (15, -3, 16, 3, 3, "mossy_stone_bricks"), (-17, -3, -16, 3, 2, "cobblestone"), (5, 4, 6, 8, 2, "mossy_cobblestone"),
         (-8, -6, -5, -5, 2, "stone_bricks")]


def ench(d): return "{" + ",".join(f'"{k if ":" in k else "minecraft:" + k}":{v}' for k, v in d.items()) + "}"
def item(id_, name=None, color="white", enchants=None, extra="", durability=None):
    """Unbreakable unless durability is given (then it wears out and breaks after that many uses)."""
    comps = [f"minecraft:max_damage={durability}", "minecraft:damage=0"] if durability else ["minecraft:unbreakable={}"]
    if enchants: comps.append(f"minecraft:enchantments={ench(enchants)}")
    if name: comps.append(f'minecraft:custom_name={{"text":"{name}","color":"{color}","italic":false}}')
    if extra: comps.append(extra)
    return f"minecraft:{id_}[{','.join(comps)}]"
def armor(mat, prot, extra=None, dye=None):
    """extra: {"head"|"chest"|"legs"|"feet": {enchant: level}}; mat: material or {slot: material}"""
    out = []
    for slot, piece in (("head", "helmet"), ("chest", "chestplate"), ("legs", "leggings"), ("feet", "boots")):
        m = mat[slot] if isinstance(mat, dict) else mat
        e = {"protection": prot, **((extra or {}).get(slot) or {})}
        out.append(f"item replace entity @s armor.{slot} with {item(f'{m}_{piece}', enchants=e, extra=f'minecraft:dyed_color={dye}' if dye and m == 'leather' else '')}")
    return out
def potion(kind, p, n=1): return f'give @s minecraft:{kind}[minecraft:potion_contents={{potion:"minecraft:{p}"}}] {n}'

CE = "crispy_enchants:"
def passive(effect, level=0): return [f"effect give @s minecraft:{effect} infinite {level} true"]
def suit(mats, prot, dye=None, trim=None, extra=None):
    """Armor with per-slot material and leather colour (dicts or single values) and an optional armor trim."""
    out = []
    for slot, piece in (("head", "helmet"), ("chest", "chestplate"), ("legs", "leggings"), ("feet", "boots")):
        m = mats[slot] if isinstance(mats, dict) else mats
        d = dye.get(slot) if isinstance(dye, dict) else dye
        comps = [f"minecraft:dyed_color={d}"] if d is not None and m == "leather" else []
        if trim and m != "leather": comps.append(f'minecraft:trim={{material:"minecraft:{trim[0]}",pattern:"minecraft:{trim[1]}"}}')
        e = {"protection": prot, **((extra or {}).get(slot) or {})}
        out.append(f"item replace entity @s armor.{slot} with {item(f'{m}_{piece}', enchants=e, extra=','.join(comps))}")
    return out
def model(m): return f'minecraft:item_model="minecraft:{m}"'
HEADS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "heads.json")))   # kit key -> skin texture value
def head(key, name, color):
    """The character's head as the helmet: diamond-helmet armor and Protection IV, so it costs no defence."""
    comps = [f'minecraft:profile={{properties:[{{name:"textures",value:"{HEADS[key]}"}}]}}',
             f'minecraft:custom_name={{"text":"{name}","color":"{color}","italic":false}}',
             'minecraft:enchantments={"minecraft:protection":4}',
             'minecraft:attribute_modifiers=[{type:"minecraft:armor",amount:3,operation:"add_value",id:"pvp:head_armor",slot:"head"},'
             '{type:"minecraft:armor_toughness",amount:2,operation:"add_value",id:"pvp:head_tough",slot:"head"}]']
    return [f"item replace entity @s armor.head with minecraft:player_head[{','.join(comps)}]"]
SIZE_MODS = ("size_dmg", "size_hp", "size_kb", "size_spd")
def size_stats(scale):
    """What a size does besides the model: big characters hit harder, have more health and knockback resistance but
    are slower; small ones are faster but hit softer and have less health. d is the size change (1.3x -> 0.3)."""
    d = scale - 1
    return {"dmg": round(d * 0.5, 3),                        # attack damage, x total: 1.3x -> +15 %, 0.6x -> -20 %
            "hp": round(d * 20) if d > 0 else round(d * 10),   # max health: 1.3x -> +6 (3 hearts), 0.6x -> -4
            "kb": round(d, 3) if d > 0 else 0,                 # knockback resistance: 1.3x -> +0.3
            "spd": round(-d * 0.3, 3)}                         # movement speed, x base: 1.3x -> -9 %, 0.6x -> +12 %
def size(scale):
    st = size_stats(scale)
    out = [f"attribute @s minecraft:scale modifier add pvp:size {round(scale - 1, 3)} add_value",
           f"attribute @s minecraft:attack_damage modifier add pvp:size_dmg {st['dmg']} add_multiplied_total",
           f"attribute @s minecraft:movement_speed modifier add pvp:size_spd {st['spd']} add_multiplied_base"]
    if st["hp"]: out.append(f"attribute @s minecraft:max_health modifier add pvp:size_hp {st['hp']} add_value")
    if st["kb"]: out.append(f"attribute @s minecraft:knockback_resistance modifier add pvp:size_kb {st['kb']} add_value")
    if st["hp"] > 0: out.append("effect give @s minecraft:instant_health 1 1 true")   # fill the extra hearts
    return out
AB = abilities.give
def ab_line(*keys): return " · ".join(abilities.ABILITIES[k][0] for k in keys)

# Franchise kits: Star Wars, video games, Smash Bros. Two right-click ability items each (abilities.py); no cyberware.
FRANCHISE_KITS = [
    (11, "jedi", "Jedi Knight", "aqua", "breeze_rod", ["Lightsaber: Sharpness III, Double Strike II · robes: Dodge II", ab_line("force_push", "mind_trick")],
     [f"give @s {item('diamond_sword', 'Lightsaber', 'aqua', {'sharpness': 3, CE + 'doublestrike': 2}, model('breeze_rod'))}", AB("force_push"), AB("mind_trick")]
     + suit({"head": "leather", "chest": "leather", "legs": "leather", "feet": "iron"}, 4, dye=9137994,
            extra={"chest": {CE + "dodge": 2}, "feet": {"feather_falling": 4}})
     + head("jedi", "Jedi Knight", "aqua") + passive("jump_boost", 1), []),
    (12, "sith", "Sith Lord", "dark_red", "blaze_rod", ["Red lightsaber: Sharpness III, Demonic Lifesteal III, Paralyze II", ab_line("force_lightning", "force_choke")],
     [f"give @s {item('diamond_sword', 'Sith Lightsaber', 'red', {'sharpness': 3, 'fire_aspect': 1, CE + 'demoniclifesteal': 3, CE + 'paralyze': 2}, model('blaze_rod'))}",
      AB("force_lightning"), AB("force_choke")]
     + suit({"head": "netherite", "chest": "leather", "legs": "leather", "feet": "netherite"}, 4, dye=1908001) + head("sith", "Sith Lord", "dark_red"), []),
    (13, "link", "Hero of Hyrule", "green", "shield", ["Master Sword (Blessed III), Hylian Shield, bow (Eagle Eye III)", ab_line("spin_attack", "hookshot")],
     [f"give @s {item('diamond_sword', 'Master Sword', 'aqua', {'sharpness': 3, 'smite': 3, CE + 'blessed': 3})}", AB("spin_attack"), AB("hookshot"),
      f"give @s {item('bow', 'Hero Bow', 'green', {'power': 4, 'infinity': 1, CE + 'eagleeye': 3})}", "give @s minecraft:arrow 1",
      f"item replace entity @s weapon.offhand with {item('shield', 'Hylian Shield', 'blue')}"]
     + suit({"head": "leather", "chest": "leather", "legs": "leather", "feet": "iron"}, 3, dye=4237864, extra={"feet": {CE + "springs": 2}})
     + head("link", "Hero of Hyrule", "green"), []),
    (14, "spartan", "Spartan", "dark_green", "turtle_helmet", ["MA5 Assault Rifle + energy sword · MJOLNIR armor · tall", ab_line("ma5", "frag_grenade") + " · energy shield recharges"],
     [AB("ma5"), AB("frag_grenade"), f"give @s {item('diamond_sword', 'Energy Sword', 'aqua', {'sharpness': 3})}"]
     + suit({"head": "netherite", "chest": "netherite", "legs": "iron", "feet": "iron"}, 1, trim=("emerald", "sentry")) + head("spartan", "Master Chief", "dark_green") + size(1.1), []),
    (15, "doom", "Doom Slayer", "red", "netherite_axe", ["Super Shotgun + Crucible (Bleed IV, Rage III) · Praetor Suit", ab_line("super_shotgun", "chainsaw", "rip_tear") + " · kills heal"],
     [AB("super_shotgun"), AB("chainsaw"), AB("rip_tear"),
      f"give @s {item('diamond_sword', 'Crucible', 'dark_red', {'sharpness': 2, 'fire_aspect': 1, CE + 'bleed': 4, CE + 'rage': 3})}"]
     + suit({"head": "netherite", "chest": "netherite", "legs": "iron", "feet": "iron"}, 1, trim=("emerald", "ward")) + head("doom", "Doom Slayer", "red"), []),
    (16, "witcher", "Witcher", "gray", "iron_sword", ["Steel sword (Cleave III, Bleed III) + silver sword (Smite V), 2 Swallow potions", ab_line("igni", "quen")],
     [f"give @s {item('diamond_sword', 'Steel Sword', 'gray', {'sharpness': 3, CE + 'cleave': 3, CE + 'bleed': 3})}", AB("igni"), AB("quen"),
      f"give @s {item('golden_sword', 'Silver Sword', 'white', {'smite': 5, 'sharpness': 2})}", potion("potion", "strong_regeneration", 2)]
     + suit("chainmail", 2, extra={"chest": {CE + "dodge": 2}}) + head("witcher", "Geralt of Rivia", "gray"), []),
    (17, "mario", "Mario", "red", "red_mushroom", ["Hammer (Pummel II) · Springs III boots · Resistance I · short", ab_line("fireball", "super_jump")],
     [f"give @s {item('mace', 'Hammer', 'red', {'density': 2, 'breach': 1, CE + 'pummel': 2})}", AB("fireball"), AB("super_jump")]
     + suit("leather", 4, dye={"head": 13184550, "chest": 13184550, "legs": 3949738, "feet": 8606770}, extra={"feet": {CE + "springs": 3}})
     + head("mario", "Mario", "red") + passive("resistance") + size(0.85), []),
    (18, "pikachu", "Pikachu", "yellow", "yellow_dye", ["Iron Tail: Sharpness IV, Paralyze III (static) · Speed I · tiny", ab_line("thunder_jolt", "quick_attack")],
     [f"give @s {item('iron_sword', 'Iron Tail', 'yellow', {'sharpness': 4, 'knockback': 2, CE + 'paralyze': 3})}", AB("thunder_jolt"), AB("quick_attack")]
     + suit("leather", 4, dye=16701501) + head("pikachu", "Pikachu", "yellow") + passive("speed") + passive("resistance") + size(0.6), []),
    (19, "kirby", "Kirby", "light_purple", "pink_dye", ["Star Rod (Devour III) · Antigravity II boots · Jump Boost II · tiny", ab_line("inhale", "stone")],
     [f"give @s {item('diamond_sword', 'Star Rod', 'light_purple', {'sharpness': 4, CE + 'devour': 3})}", AB("inhale"), AB("stone")]
     + suit("leather", 4, dye=15961002, extra={"feet": {CE + "antigravity": 2}}) + head("kirby", "Kirby", "light_purple")
     + passive("jump_boost", 1) + passive("resistance") + size(0.6), []),
    (20, "samus", "Samus", "gold", "golden_helmet", ["Arm Cannon (Power Beam) · Varia Suit (Reinforced III)", ab_line("power_beam", "charge_shot", "screw_attack")],
     [AB("power_beam"), AB("charge_shot"), AB("screw_attack"), f"give @s {item('iron_sword', enchants={'sharpness': 2})}"]
     + suit("golden", 4, extra={"chest": {CE + "reinforced": 3}}) + head("samus", "Samus Aran", "gold") + size(1.08), []),
    (21, "randy", "Randy Marsh", "white", "fern", ["No weapon: fists hit for +7 (sword speed) · Sandevistan cyberware", ab_line("tegridy", "wassup_bruh") + " · Sandevistan (double-tap sneak)"],
     [AB("tegridy"), AB("wassup_bruh"), "attribute @s minecraft:attack_damage modifier add pvp:fists 7 add_value",
      "attribute @s minecraft:attack_speed modifier add pvp:fists -2.4 add_value"]
     + suit("leather", 4, dye={"head": 4007438, "chest": 9226476, "legs": 3949738, "feet": 6045219}) + head("randy", "Randy Marsh", "white"), ["sandy"]),
    (22, "courier", "Courier Six", "gold", "spyglass", ["Lucky (revolver) + machete (Bleed II) · Ranger armor", ab_line("lucky", "vats", "stimpak")],
     [AB("lucky"), AB("vats"), AB("stimpak"), f"give @s {item('iron_sword', 'Machete', 'gray', {'sharpness': 4, CE + 'bleed': 2})}"]
     + suit({"head": "iron", "chest": "leather", "legs": "iron", "feet": "iron"}, 2, dye=6045219) + head("courier", "Courier Six", "gold"), []),
    (24, "sonic", "Sonic", "blue", "lapis_lazuli", ["Chaos Emerald blade · Springs II + Gears II shoes · Speed II · small", ab_line("spin_dash", "homing_attack")],
     [f"give @s {item('iron_sword', 'Chaos Emerald', 'green', {'sharpness': 5}, model('emerald'))}", AB("spin_dash"), AB("homing_attack")]
     + suit("leather", 4, dye={"head": 2068440, "chest": 2068440, "legs": 2068440, "feet": 13184550},
            extra={"chest": {CE + "dodge": 2}, "feet": {CE + "springs": 2, CE + "gears": 2}})
     + head("sonic", "Sonic", "blue") + passive("speed", 1) + size(0.8), []),
    (25, "walter", "Walter White", "dark_gray", "quartz", ["Trunk M60 (machine gun) · 3 splash Poison II · hazmat suit (Explosive Immunity III)", ab_line("m60", "say_my_name", "fulminate")],
     [AB("m60"), AB("say_my_name"), AB("fulminate"), potion("splash_potion", "strong_poison", 3)]
     + suit("leather", 4, dye=15057152, extra={"chest": {CE + "explosiveimmunity": 3}}) + head("walter", "Heisenberg", "dark_gray"), []),
    (26, "herobrine", "Herobrine", "white", "end_rod", ["Diamond sword (Sharpness V, Fire Aspect) · Night Vision", ab_line("smite", "haunt")],
     [f"give @s {item('diamond_sword', 'Herobrine', 'white', {'sharpness': 5, 'fire_aspect': 1})}", AB("smite"), AB("haunt")]
     + suit("leather", 4, dye={"head": 43690, "chest": 43690, "legs": 3355562, "feet": 5592405}) + head("herobrine", "Herobrine", "white")
     + passive("night_vision"), []),
    (28, "dk", "Donkey Kong", "gold", "cocoa_beans", ["No weapon: fists hit for +9 (axe speed) · Tank II · big", ab_line("giant_punch", "ground_pound")],
     [AB("giant_punch"), AB("ground_pound"), "attribute @s minecraft:attack_damage modifier add pvp:fists 9 add_value",
      "attribute @s minecraft:attack_speed modifier add pvp:fists -2.8 add_value"]
     + suit("leather", 4, dye={"head": 6045219, "chest": 13184550, "legs": 6045219, "feet": 6045219}, extra={"legs": {CE + "tank": 2}})
     + head("dk", "Donkey Kong", "gold") + size(1.25), []),
    (29, "mando", "Mandalorian", "gray", "firework_rocket", ["Amban Rifle + Darksaber · Beskar armor", ab_line("amban", "jetpack", "flamethrower")],
     [AB("amban"), AB("jetpack"), AB("flamethrower"), f"give @s {item('netherite_sword', 'Darksaber', 'dark_gray', {'sharpness': 3})}"]
     + suit("iron", 3, trim=("quartz", "sentry"), extra={"feet": {"feather_falling": 4}})
     + head("mando", "Din Djarin", "gray"), []),
    (30, "red", "Red", "red", "red_dye", ["Slingshot bow (Power IV, Punch II) · beak: fists +8 (sword speed) · Jump Boost I · small", ab_line("fling", "battle_cry")],
     [f"give @s {item('bow', 'Slingshot', 'red', {'power': 4, 'punch': 2, 'infinity': 1})}", AB("fling"), AB("battle_cry"), "give @s minecraft:arrow 1",
      "attribute @s minecraft:attack_damage modifier add pvp:fists 8 add_value", "attribute @s minecraft:attack_speed modifier add pvp:fists -2.4 add_value"]
     + suit("leather", 4, dye={"head": 12986408, "chest": 12986408, "legs": 16247203, "feet": 12986408}, extra={"feet": {"feather_falling": 4}})
     + head("red", "Red", "red") + passive("jump_boost") + size(0.7), []),
    (31, "spiderman", "Spider-Man", "red", "cobweb", ["No weapon: fists +7 (sword speed) · Dodge III · Springs II · Jump Boost II", ab_line("web_shot", "web_swing")],
     [AB("web_shot"), AB("web_swing"), "attribute @s minecraft:attack_damage modifier add pvp:fists 7 add_value", "attribute @s minecraft:attack_speed modifier add pvp:fists -2.4 add_value"]
     + suit("leather", 4, dye={"head": 13184550, "chest": 13184550, "legs": 2068440, "feet": 13184550},
            extra={"chest": {CE + "dodge": 3}, "feet": {CE + "springs": 2, "feather_falling": 4}})
     + head("spiderman", "Spider-Man", "red") + passive("jump_boost", 1), []),
    (32, "shrek", "Shrek", "green", "slime_ball", ["No weapon: fists +8 (axe speed) · Tank II · Health Boost I · big", ab_line("swamp_roar", "onion_layers")],
     [AB("swamp_roar"), AB("onion_layers"), "attribute @s minecraft:attack_damage modifier add pvp:fists 8 add_value", "attribute @s minecraft:attack_speed modifier add pvp:fists -2.8 add_value"]
     + suit("leather", 3, dye={"head": 9349946, "chest": 6045219, "legs": 9127187, "feet": 3811599}, extra={"legs": {CE + "tank": 2}})
     + head("shrek", "Shrek", "green") + passive("health_boost") + ["effect give @s minecraft:instant_health 1 1 true"] + size(1.3), []),
    (33, "peter", "Peter Griffin", "green", "cooked_chicken", ["No weapon: fists +6 (sword speed) · 2 Pawtucket Patriot (Strength) · Health Boost I", ab_line("chicken_fight", "surfin_bird")],
     [AB("chicken_fight"), AB("surfin_bird"), "attribute @s minecraft:attack_damage modifier add pvp:fists 6 add_value", "attribute @s minecraft:attack_speed modifier add pvp:fists -2.4 add_value", potion("potion", "strength", 2)]
     + suit("leather", 3, dye={"head": 16777215, "chest": 16777215, "legs": 3828013, "feet": 3355443})
     + head("peter", "Peter Griffin", "green") + passive("health_boost") + ["effect give @s minecraft:instant_health 1 1 true"] + size(1.1), []),
    (34, "homer", "Homer Simpson", "yellow", "cookie", ["Plutonium Rod (Poison II) · Health Boost I · a bit big", ab_line("donut", "belly_bump")],
     [f"give @s {item('iron_sword', 'Plutonium Rod', 'green', {'sharpness': 4, CE + 'poison': 2}, model('end_rod'))}", AB("donut"), AB("belly_bump")]
     + suit("leather", 3, dye={"head": 16777215, "chest": 16777215, "legs": 2068440, "feet": 5592405})
     + head("homer", "Homer Simpson", "yellow") + passive("health_boost") + ["effect give @s minecraft:instant_health 1 1 true"] + size(1.1), []),
    (35, "maul", "Darth Maul", "dark_red", "redstone_torch", ["Double-bladed saber: Sharpness III, Double Strike II, Sweeping III · Speed I", ab_line("saber_throw", "saber_spin")],
     [f"give @s {item('diamond_sword', 'Double-Bladed Lightsaber', 'red', {'sharpness': 3, 'sweeping_edge': 3, CE + 'doublestrike': 2}, model('blaze_rod'))}",
      AB("saber_throw"), AB("saber_spin")]
     + suit("leather", 4, dye=1908001, extra={"chest": {CE + "dodge": 2}, "feet": {CE + "springs": 1}})
     + head("maul", "Darth Maul", "dark_red") + passive("speed"), []),
    (36, "krabs", "Mr. Krabs", "red", "turtle_scute", ["No weapon: claws hit for +6 (sword speed) · shell (Armored II) · small", ab_line("claw_pinch", "money_grab")],
     [AB("claw_pinch"), AB("money_grab"), "attribute @s minecraft:attack_damage modifier add pvp:fists 6 add_value",
      "attribute @s minecraft:attack_speed modifier add pvp:fists -2.4 add_value"]
     + suit("leather", 4, dye={"head": 13184550, "chest": 6134752, "legs": 9127187, "feet": 1908001}, extra={"chest": {CE + "armored": 2}})
     + head("krabs", "Mr. Krabs", "red") + size(0.9), []),
    (37, "saul", "Saul Goodman", "yellow", "paper", ["Gavel (mace: Density III) · loud suit (Dodge II), Springs II shoes · Speed I", ab_line("served", "loophole", "fingertips")],
     [f"give @s {item('mace', 'Gavel', 'gold', {'density': 3, 'breach': 1})}", AB("served"), AB("loophole"), AB("fingertips")]
     + suit("leather", 4, dye={"head": 14329120, "chest": 14329120, "legs": 14329120, "feet": 1908001}, extra={"chest": {CE + "dodge": 2}, "feet": {CE + "springs": 2}})
     + head("saul", "Saul Goodman", "yellow") + passive("speed"), []),
    (38, "hank", "Hank Hill", "aqua", "lantern", ["Grill spatula (Sharpness IV, Fire Aspect) · white tee, jeans · Fire Resistance", ab_line("propane", "kick_your_ass")],
     [f"give @s {item('iron_sword', 'Grill Spatula', 'aqua', {'sharpness': 4, 'fire_aspect': 1}, model('iron_shovel'))}", AB("propane"), AB("kick_your_ass")]
     + suit("leather", 4, dye={"head": 16777215, "chest": 16777215, "legs": 3949738, "feet": 6045219}, extra={"chest": {CE + "explosiveimmunity": 3}})
     + head("hank", "Hank Hill", "aqua") + passive("fire_resistance"), []),
    (39, "leela", "Leela", "light_purple", "rabbit_foot", ["No weapon: martial arts, fists +7 (sword speed) · Dodge II · Speed I", ab_line("leela_kick", "laser_pistol")],
     [AB("leela_kick"), AB("laser_pistol"), "attribute @s minecraft:attack_damage modifier add pvp:fists 7 add_value",
      "attribute @s minecraft:attack_speed modifier add pvp:fists -2.4 add_value"]
     + suit("leather", 4, dye={"head": 16777215, "chest": 16777215, "legs": 1908001, "feet": 1908001}, extra={"chest": {CE + "dodge": 2}, "feet": {CE + "springs": 1}})
     + head("leela", "Leela", "light_purple") + passive("speed"), []),
    (40, "elliot", "Elliot", "dark_gray", "command_block", ["Pocketknife (Sharpness III, Poison I) · black hoodie (Dodge II) · Night Vision", ab_line("blackout", "mr_robot")],
     [f"give @s {item('iron_sword', 'Pocketknife', 'gray', {'sharpness': 3, CE + 'poison': 1})}", AB("blackout"), AB("mr_robot")]
     + suit("leather", 4, dye={"head": 1908001, "chest": 1908001, "legs": 3355443, "feet": 5592405}, extra={"chest": {CE + "dodge": 2}})
     + head("elliot", "Elliot Alderson", "dark_gray") + passive("night_vision"), []),
    (41, "tony", "Tony Soprano", "dark_red", "flint", ["Baseball Bat (Sharpness IV, Knockback I) · bathrobe · a bit big", ab_line("gabagool", "whack")],
     [f"give @s {item('iron_sword', 'Baseball Bat', 'dark_red', {'sharpness': 4, 'knockback': 1}, model('stick'))}", AB("gabagool"), AB("whack")]
     + suit("leather", 4, dye={"head": 15790320, "chest": 15790320, "legs": 15790320, "feet": 6045219})
     + head("tony", "Tony Soprano", "dark_red") + size(1.1), []),
    (42, "spongebob", "SpongeBob", "yellow", "bread", ["Golden Spatula (Sharpness IV, Knockback II) · Springs II · Jump Boost I · small", ab_line("krabby_patty", "bubble_blower")],
     [f"give @s {item('iron_sword', 'Golden Spatula', 'gold', {'sharpness': 4, 'knockback': 2}, model('golden_shovel'))}", AB("krabby_patty"), AB("bubble_blower")]
     + suit("leather", 4, dye={"head": 16701501, "chest": 16777215, "legs": 9127187, "feet": 1908001}, extra={"chest": {CE + "dodge": 2}, "feet": {CE + "springs": 2}})
     + head("spongebob", "SpongeBob", "yellow") + passive("jump_boost") + size(0.8), []),
    (43, "bender", "Bender", "gray", "iron_ingot", ["Bent Girder (axe: Sharpness IV, Cleave II) · metal body (iron Prot III, Armored II) · Fire Resistance", ab_line("shiny_metal", "olde_fortran")],
     [f"give @s {item('iron_axe', 'Bent Girder', 'gray', {'sharpness': 4, CE + 'cleave': 2})}", AB("shiny_metal"), AB("olde_fortran")]
     + suit("iron", 3, extra={"chest": {CE + "armored": 2}}) + head("bender", "Bender", "gray") + passive("fire_resistance"), []),
]
FOOD = ["give @s minecraft:cooked_beef 16", "give @s minecraft:golden_apple 2"]
# id, key, name, colour, menu icon, blurb lines, item commands, implants (one per body slot)
KITS = [
    (1, "samurai", "David Martinez", "yellow", "netherite_sword", ["Cyber-arms: fists +6 (sword speed) · yellow EMT jacket (Dodge II)",
     "Cyberware: Sandevistan, Kiroshi, Reflex Tuner, Reinforced Tendons · " + ab_line("militech_handgun", "overclock")],
     [AB("militech_handgun"), AB("overclock"), "attribute @s minecraft:attack_damage modifier add pvp:fists 6 add_value",
      "attribute @s minecraft:attack_speed modifier add pvp:fists -2.4 add_value"]
     + suit({"head": "leather", "chest": "leather", "legs": "leather", "feet": "diamond"}, 4,
            dye={"head": 1908001, "chest": 15909166, "legs": 1908001}, extra={"chest": {CE + "dodge": 2}})
     + head("edgerunner", "David Martinez", "yellow"), ["sandy", "kiroshi", "reflex", "tendons"]),
    (3, "sniper", "Sniper", "dark_red", "bow", ["Sniper Rifle (bow: Power III, Lethal Sniper II) + Kukri · Night Vision", ab_line("jarate", "focus")],
     [f"give @s {item('bow', 'Sniper Rifle', 'dark_red', {'power': 3, 'infinity': 1, CE + 'lethalsniper': 2})}",
      AB("jarate"), AB("focus"), f"give @s {item('iron_sword', 'Kukri', 'gray', {'sharpness': 3, CE + 'bleed': 1})}", "give @s minecraft:arrow 1"]
     + suit({"head": "leather", "chest": "leather", "legs": "leather", "feet": "diamond"}, 3, dye={"head": 6045219, "chest": 11141120, "legs": 6045219})
     + head("sniper", "Sniper", "dark_red") + passive("night_vision"), []),
    (5, "assassin", "Lucy", "light_purple", "diamond_sword", ["Monowire: Sharpness IV, Assassin III, Poison II · Dodge II", "Cyberware: Lynx Paws, Reflex Tuner, Kiroshi · " + ab_line("short_circuit", "optical_camo")],
     [f"give @s {item('diamond_sword', 'Monowire', 'light_purple', {'sharpness': 4, CE + 'assassin': 3, CE + 'poison': 2})}", AB("short_circuit"), AB("optical_camo")]
     + suit({"head": "leather", "chest": "leather", "legs": "leather", "feet": "diamond"}, 3, dye=15790320, extra={"chest": {CE + "dodge": 2}})
     + head("lucy", "Lucy", "light_purple"), ["lynx", "reflex", "kiroshi"]),
    (23, "smasher", "Adam Smasher", "dark_red", "netherite_chestplate", ["Militech Heavy Cannon + Borg Slam + Arasaka axe (Cleave III) · full-borg frame · huge",
     "Cyberware: Projectile Launcher, Sandevistan"],
     [AB("heavy_cannon"), AB("borg_slam"), f"give @s {item('netherite_axe', 'Arasaka Breaker', 'red', {'sharpness': 1, CE + 'cleave': 3})}"]
     + suit({"head": "netherite", "chest": "netherite", "legs": "netherite", "feet": "iron"}, 1, trim=("redstone", "rib"), extra={"chest": {CE + "explosiveimmunity": 3}})
     + head("smasher", "Adam Smasher", "dark_red") + size(1.3), ["launcher", "sandy"]),
    (27, "rebecca", "Rebecca", "light_purple", "crossbow", ["Guts (shotgun) + Pistol · Dodge II · tiny",
     "Cyberware: Gorilla Arms, Reinforced Tendons, Reflex Tuner, Kiroshi"],
     [AB("guts"), AB("pistol")]
     + suit("leather", 4, dye={"head": 1908001, "chest": 1908001, "legs": 1908001, "feet": 15961002}, extra={"chest": {CE + "dodge": 2}})
     + head("rebecca", "Rebecca", "light_purple") + size(0.75), ["gorilla", "tendons", "reflex", "kiroshi"]),
] + FRANCHISE_KITS
# Halloween (Haunted Night only, outbreak map 6): horror icons. Never in the arena, duel, Tower or random-character pools.
HALLOWEEN_KITS = [
    (44, "myers", "Michael Myers", "dark_gray", "iron_sword", ["Kitchen Knife: Sharpness IV, Bleed II · coveralls · a bit big", ab_line("the_shape", "relentless")],
     [f"give @s {item('iron_sword', 'Kitchen Knife', 'gray', {'sharpness': 4, CE + 'bleed': 2})}", AB("the_shape"), AB("relentless")]
     + suit("leather", 3, dye=2834005, extra={"chest": {CE + "hardened": 2}}) + head("myers", "Michael Myers", "dark_gray") + size(1.08), []),
    (45, "jason", "Jason Voorhees", "dark_green", "iron_axe", ["Machete (axe): Sharpness III, Cleave II · big and tough", ab_line("machete_throw", "shift")],
     [f"give @s {item('iron_axe', 'Machete', 'dark_green', {'sharpness': 3, CE + 'cleave': 2})}", AB("machete_throw"), AB("shift")]
     + suit("leather", 3, dye={"head": 4873507, "chest": 4873507, "legs": 3684408, "feet": 2829099}) + head("jason", "Jason Voorhees", "dark_green") + size(1.15), []),
    (46, "slenderman", "Slender Man", "dark_gray", "iron_chain", ["Tendril (sword): Sharpness III, Blind II · black suit · very tall", ab_line("static", "tendrils")],
     [f"give @s {item('iron_sword', 'Tendril', 'dark_gray', {'sharpness': 3, CE + 'blind': 2}, model('iron_chain'))}", AB("static"), AB("tendrils")]
     + suit("leather", 3, dye=1710618, extra={"chest": {CE + "dodge": 1}}) + head("slenderman", "Slender Man", "dark_gray") + size(1.3), []),
    (47, "ghostface", "Ghostface", "white", "black_dye", ["Buck 120 Knife: Sharpness III, Assassin II · black robe (Dodge II)", ab_line("stalk", "ambush")],
     [f"give @s {item('iron_sword', 'Buck 120 Knife', 'white', {'sharpness': 3, CE + 'assassin': 2})}", AB("stalk"), AB("ambush")]
     + suit("leather", 3, dye=1907233, extra={"chest": {CE + "dodge": 2}}) + head("ghostface", "Ghostface", "white"), []),
    (48, "fazbear", "Freddy Fazbear", "gold", "jukebox", ["Microphone (mace): Density II, Stun II · animatronic suit · big", ab_line("jumpscare", "power_outage")],
     [f"give @s {item('mace', 'Microphone', 'gold', {'density': 2, CE + 'stun': 2})}", AB("jumpscare"), AB("power_outage")]
     + suit("leather", 3, dye=7948840, extra={"chest": {CE + "hardened": 2}}) + head("fazbear", "Freddy Fazbear", "gold") + size(1.2), []),
]
HW_IDS = [k[0] for k in HALLOWEEN_KITS]
ALL_KITS = KITS + HALLOWEEN_KITS
HW_MAP = 6           # Outbreak map id of Haunted Night
HW_WAVES = 10        # beat this many waves to complete it
HW_END = "2026-11-07"   # last day it's open (the mod sets #halloween pvp to 1 until then)
HW_NPC = (6.5, LOBBY_Y + 1, 5.5)
def alt(text, codes):
    """Text with the legacy codes cycling letter by letter (spaces skipped): works in every tag renderer."""
    out, i = "", 0
    for ch in text:
        if ch == " ": out += " "; continue
        out += codes[i % len(codes)] + ch; i += 1
    return out


# Haunted Night cosmetics: each completed run unlocks one the player doesn't have yet, at random. Score pvp.hw<n> = 1
# when unlocked; the lobby (CrispyLobby, config generated by halloween_cosmetics.py) reads them from the scoreboard.
# n, kind (tag / name / chat colour), lobby id, name, display (tags) or colour code
HW_COSMETICS = [
    (1, "tag", "hw_lostmyhead", "Lost My Head", "&8[&4☠ " + alt("Lost My Head", ["&c", "&4"]) + "&8]"),
    (2, "tag", "hw_pumpkinking", "Pumpkin King", "&8[&6☾ " + alt("Pumpkin", ["&6&l", "&e&l"]) + " &8&lKing&8]"),
    (3, "tag", "hw_spookyscary", "Spooky Scary", "&8[&7☠ " + alt("Spooky", ["&f", "&7"]) + " " + alt("Scary", ["&6", "&8"]) + "&8]"),
    (4, "tag", "hw_crispyhalloween", "Crispy Halloween '26", "&8[&6☾ " + alt("Crispy", ["&6&l", "&e&l"]) + " " + alt("Halloween", ["&6", "&5"]) + " &d'26&8]"),
    (5, "tag", "hw_trickortreat", "Trick or Treat", "&6[" + alt("Trick or Treat", ["&e", "&6", "&f"]) + "&6]"),
    (6, "tag", "hw_slasher", "Slasher", "&4[&c⚔ " + alt("Slasher", ["&4&l", "&c&l"]) + "&4]"),
    (7, "name", "hw_pumpkin", "Pumpkin", "&#ff7518>&#ffb347"),
    (8, "name", "hw_candycorn", "Candy Corn", "&#ffd23f/&#ff8c1a/&#ffffff"),
    (9, "name", "hw_witchbrew", "Witch's Brew", "&#7fff00>&#8a2be2"),
    (10, "name", "hw_bloodmoon", "Blood Moon", "&#8b0000>&#ff3b3b"),
    (11, "name", "hw_ghostly", "Ghostly", "&#ffffff>&#8a8f99"),
    (12, "chat", "hw_pumpkinspice", "Pumpkin Spice", "&#e8823a"),
    (13, "chat", "hw_candycorn", "Candy Corn", "&#ffd23f/&#ff8c1a/&#ffffff"),
    (14, "chat", "hw_witchbrew", "Witch's Brew", "&#7fff00>&#8a2be2"),
    (15, "chat", "hw_spectral", "Spectral", "&#7df9ff>&#ffffff"),
]
HW_KIND = {"tag": "tag", "name": "name colour", "chat": "chat colour"}
# Admin-only test kits: never in a menu. /function pvp:admin/test_david queues you for Outbreak with it.
TEST_KIT_ID = 60
TEST_KIT = [
    f"give @s {item('netherite_sword', 'Mantis Edge', 'red', {'sharpness': 5})}",
    f"item replace entity @s weapon.offhand with {item('netherite_axe', 'Off-hand Cleaver', 'dark_red', {'sharpness': 5})}",
    f"give @s {item('crossbow', 'Militech Launcher L', 'gold', {'quick_charge': 3, 'piercing': 2})}",
    f"give @s {item('crossbow', 'Militech Launcher R', 'gold', {'quick_charge': 3, 'piercing': 2})}",
    f"give @s {item('bow', 'Smart Bow', 'aqua', {'power': 5, 'infinity': 1})}",
    "give @s minecraft:arrow 64", "give @s minecraft:arrow 64",
    *armor("netherite", 4),
    "loot give @s loot cyber:item/neuro", "loot give @s loot cyber:item/neuro", "loot give @s loot cyber:item/neuro",
    "give @s minecraft:cooked_beef 32", "give @s minecraft:golden_apple 4",
    *[f"function cyber:implant/{k}/kit" for k in ("cyberskeleton", "sandy", "kiroshi", "reflex")],
    "tellraw @s [{\"text\":\"Kit: \",\"color\":\"gray\"},{\"text\":\"David (test)\",\"color\":\"dark_red\",\"bold\":true},"
    "{\"text\":\" · Cyberskeleton, Sandevistan, Kiroshi, Reflex Tuner. Swap the crossbows into both hands to dual-fire.\",\"color\":\"gray\"}]",
]
# kit menu order: four full rows of 9 (slots 9-44), grouped by franchise; the top and bottom rows stay empty
KIT_ORDER = [11, 12, 35, 29, 1, 5, 27, 23, 40,     # Jedi, Sith, Darth Maul, Mandalorian | David, Lucy, Rebecca, Adam Smasher, Elliot
             13, 14, 15, 16, 22, 3, 26, 30, 24,    # Link, Spartan, Doom Slayer, Witcher, Courier Six, Sniper, Herobrine, Red, Sonic
             17, 18, 19, 20, 28, 31, 32, 39, 43,   # Mario, Pikachu, Kirby, Samus, Donkey Kong | Spider-Man, Shrek | Leela, Bender
             21, 33, 34, 38, 42, 36, 25, 37, 41]   # Randy Marsh, Peter Griffin, Homer, Hank Hill, SpongeBob, Mr. Krabs | Walter White, Saul Goodman, Tony Soprano
KIT_SLOT = dict(zip(KIT_ORDER, range(9, 45)))# Upgrades (points per tier I / II / III). Pack-a-Punch works on the held weapon (the tier is stored on the item);
# armor upgrades are per player (pve.arm). Both are lost when you go down, since your kit is handed out again.
WEAPON_UP = [2000, 4000, 7500, 12000]   # tier IV: wonder-weapon territory for the late waves
ARMOR_UP = [1500, 3000, 6000]
UP_BOOST = {   # per tier, added to the existing enchants; kind -> (item tag/id, enchants, extra on tier III, extra on tier IV)
    "melee": ("#minecraft:swords", {"sharpness": 2}, {"fire_aspect": 2}, {CE + "lifesteal": 2}),
    "axe": ("#minecraft:axes", {"sharpness": 2}, {"fire_aspect": 2}, {"sharpness": 2}),
    "bow": ("minecraft:bow", {"power": 2}, {"flame": 1, "punch": 1}, {CE + "explosive": 1}),
    "crossbow": ("minecraft:crossbow", {"piercing": 1, "quick_charge": 1}, {"multishot": 1}, {CE + "explosive": 1}),
    "trident": ("minecraft:trident", {"impaling": 2}, {"channeling": 1}, {"impaling": 2}),
    "mace": ("minecraft:mace", {"density": 1, "breach": 1}, {"wind_burst": 1}, {"density": 2}),
}
# Wall-buys: Outbreak-only guns on the walls (outbreak_maps.wallbuy_spots finds the spots); right-click to buy.
# pve.wb on the interaction = the gun's number here. Every map has the M1911 and three of the others.
WALL_BUYS = [("m1911", 500), ("olympia", 750), ("mp40", 1000), ("kar98k", 1250), ("stakeout", 1500), ("stg44", 1750)]
WALL_MAPS = {"ruins": ["m1911", "olympia", "mp40", "kar98k"], "mine": ["m1911", "stakeout", "mp40", "stg44"],
             "neon": ["m1911", "olympia", "stg44", "kar98k"], "hellfort": ["m1911", "stakeout", "kar98k", "mp40"],
             "orbital": ["m1911", "olympia", "stg44", "stakeout"], "haunted": ["m1911", "olympia", "kar98k", "stakeout"]}
VETERAN_PER_WAVE, VETERAN_MAX = 25, 1000
# Kit mastery: XP per character (score pvp.mx<kit id>), +10 per PvP kill and +1 per Outbreak kill with that kit.
MASTERY = [50, 150, 400, 800, 1500]      # XP for levels I..V (V = Master)
MASTERY_PVP, MASTERY_PVE = 10, 1
# Duels: three private pits west of everything; ELO rating (K = 32) in pvp.elo, starting at 1000
DUEL_PITS = [(-300, 0), (-300, 60), (-300, 120)]
DUEL_K, DUEL_START = 32, 1000
RANDOM_KIT = 98   # pvp.kit / pve.join value of the "Random character" menu buttons
DUEL_ITEM = ('minecraft:flint[minecraft:item_model="minecraft:iron_sword",minecraft:max_stack_size=1,minecraft:enchantment_glint_override=true,'
             'minecraft:custom_name={"text":"⚔ Duel Challenge","color":"gold","bold":true,"italic":false},'
             'minecraft:lore=[{"text":"Look at a player and right-click","color":"gray","italic":false},'
             '{"text":"to challenge them to a 1v1 duel.","color":"gray","italic":false}],'
             'minecraft:consumable={consume_seconds:0.05f,animation:"none",has_consume_particles:false,sound:"minecraft:intentionally_empty"},'
             'minecraft:use_cooldown={seconds:2f,cooldown_group:"pvp:duel"}]')   # extra starting points per best wave reached
PERK_RESET = ["tag @s remove pvp.master", "attribute @s minecraft:scale modifier remove pvp:size", "attribute @s minecraft:attack_damage modifier remove pvp:size_dmg",
              "attribute @s minecraft:max_health modifier remove pvp:size_hp", "attribute @s minecraft:knockback_resistance modifier remove pvp:size_kb",
              "attribute @s minecraft:movement_speed modifier remove pvp:size_spd", "attribute @s minecraft:attack_damage modifier remove pvp:fists",
              "attribute @s minecraft:attack_speed modifier remove pvp:fists", "attribute @s minecraft:max_health modifier remove pvp:jug", "attribute @s minecraft:max_health modifier remove pvp:arm",
              "tag @s remove pve.jug", "tag @s remove pve.cola", "tag @s remove pve.dt", "tag @s remove pve.phd", "scoreboard players set @s pve.arm 0", "scoreboard players set @s pve.gun 0"]
PERK_RESET += tower.PERK_RESET   # the Tower's upgrade modifiers go with the other per-run perks
TOWER_BOX = box(tower.TCX, tower.TCZ, tower.R + 1, AY - 1, tower.WALL_H + 4)
CELLS_NEEDED = 3   # Power Cells (from boss waves) to assemble the Annihilator
CELL = ('minecraft:heart_of_the_sea[minecraft:custom_data={pvp_cell:1b},minecraft:custom_name={"text":"Power Cell","color":"light_purple","italic":false},'
        'minecraft:lore=[{"text":"Bring 3 to the Arsenal to assemble the Annihilator","color":"gray","italic":false}],minecraft:enchantment_glint_override=true]')
REVIVE_TICKS = 60  # crouching next to a downed teammate this long revives them   # steak for every survivor when a wave is cleared
# Outbreak shop: id, name, colour, icon, cost, lore, commands (run as the buyer), one-per-life tag (checked before paying)
SHOP = [
    (1, "Golden Apple", "gold", "golden_apple", 500, "One golden apple", ["give @s minecraft:golden_apple 1"], None),
    (2, "Med Kit", "light_purple", "splash_potion", 750, "2 Splash Healing II", [potion("splash_potion", "strong_healing", 2)], None),
    (3, "Ammo", "white", "arrow", 250, "32 arrows", ["give @s minecraft:arrow 32"], None),
    (4, "Strength", "red", "potion", 1000, "Potion of Strength (3:00)", [potion("potion", "strength")], None),
    (5, "Juggernog", "dark_red", "honey_bottle", 2500, "+3 hearts until you go down", [
        "attribute @s minecraft:max_health modifier add pvp:jug 6 add_value", "effect give @s minecraft:instant_health 1 1"], "pve.jug"),
    (6, "Speed Cola", "green", "lime_dye", 2000, "Speed I + Haste II until you go down", [
        "effect give @s minecraft:speed infinite 0 true", "effect give @s minecraft:haste infinite 1 true"], "pve.cola"),
    (7, "Mystery Box", "light_purple", "chest", 950, "A random wonder weapon or character ability", ["function pvp:pve/box"], None),
    (8, "Ray Bow", "aqua", "bow", 5000, "Power X, Flame, Infinity, Punch II", [
        f"give @s {item('bow', 'Ray Bow', 'aqua', {'power': 10, 'flame': 1, 'infinity': 1, 'punch': 2})}", "give @s minecraft:arrow 1"], None),
    (9, "Rations", "yellow", "cooked_beef", 100, "16 steak", ["give @s minecraft:cooked_beef 16"], None),
    # cost None: the function charges by tier itself
    (10, "Pack-a-Punch", "gold", "anvil", None, "Upgrade the weapon in your hand: " + " / ".join(f"{c:,}" for c in WEAPON_UP),
     ["function pvp:pve/up/weapon"], None),
    (11, "Armor Upgrade", "aqua", "netherite_chestplate", None, "Upgrade your armor: " + " / ".join(f"{c:,}" for c in ARMOR_UP),
     ["function pvp:pve/up/armor"], None),
    (12, "Double Tap", "dark_red", "blaze_powder", 3000, "Strength I until you go down",
     ["effect give @s minecraft:strength infinite 0 true"], "pve.dt"),
    (13, "PhD Flopper", "light_purple", "magma_cream", 1500, "Fire immunity + Jump Boost until you go down",
     ["effect give @s minecraft:fire_resistance infinite 0 true", "effect give @s minecraft:jump_boost infinite 0 true"], "pve.phd"),
    (14, "Assemble: Annihilator", "light_purple", "end_crystal", None, f"Needs {CELLS_NEEDED} Power Cells (one per survivor for each boss wave cleared)",
     ["function pvp:pve/assemble"], None),
]
SHOP_SLOTS = [10, 11, 12, 13, 14, 15, 16, 21, 23, 19, 20, 24, 25, 22]
WAVE_FOOD = 4
# Mystery Box rolls (equal odds): name, colour, commands. Wonder weapons, gear and abilities from the character
# kits, and the Teddy Bear (nothing, half the points back).
BOX = [
    # wonder weapons: far stronger than kit gear, but they wear out (durability = uses before they break)
    ("Excalibur", "gold", [f"give @s {item('netherite_sword', 'Excalibur', 'gold', {'sharpness': 10, 'sweeping_edge': 3, 'fire_aspect': 2, CE + 'lifesteal': 3}, durability=300)}"]),
    ("Thunderfang", "aqua", [f"give @s {item('trident', 'Thunderfang', 'aqua', {'sharpness': 8, 'impaling': 5, 'loyalty': 3, 'channeling': 1, CE + 'paralyze': 2}, durability=200)}"]),
    ("Wunderwaffe", "yellow", [f"give @s {item('crossbow', 'Wunderwaffe', 'yellow', {'quick_charge': 3, 'multishot': 1, 'piercing': 5, 'power': 6, 'flame': 1, CE + 'explosive': 2}, durability=250)}", "give @s minecraft:arrow 64"]),
    ("Thundergun", "blue", [f"give @s {item('mace', 'Thundergun', 'blue', {'density': 8, 'breach': 4, 'wind_burst': 3}, durability=150)}", "give @s minecraft:wind_charge 16"]),
    ("Lightsaber", "aqua", [f"give @s {item('netherite_sword', 'Lightsaber', 'aqua', {'sharpness': 6, CE + 'doublestrike': 2}, model('breeze_rod'))}"]),
    ("Darksaber", "dark_gray", [f"give @s {item('netherite_sword', 'Darksaber', 'dark_gray', {'sharpness': 7, 'fire_aspect': 1})}"]),
    ("Arasaka Breaker", "red", [f"give @s {item('netherite_axe', 'Arasaka Breaker', 'red', {'sharpness': 6, CE + 'cleave': 3})}"]),
    ("Propane Tank", "aqua", [abilities.give("propane")]),
    ("Jarate", "yellow", [abilities.give("jarate")]),
    ("Fingertip Lightning", "aqua", [abilities.give("fingertips")]),
    ("Charge Shot", "gold", [abilities.give("charge_shot")]),
    ("Krabby Patty", "yellow", [abilities.give("krabby_patty")]),
    ("MA5 Assault Rifle", "dark_green", [abilities.give("ma5")]),
    ("Super Shotgun", "red", [abilities.give("super_shotgun")]),
    ("Lucky", "gold", [abilities.give("lucky")]),
    ("Trunk M60", "dark_gray", [abilities.give("m60")]),
    ("Amban Rifle", "gray", [abilities.give("amban")]),
    ("Laser Pistol", "red", [abilities.give("laser_pistol")]),
    ("Teddy Bear", "gold", ["scoreboard players add @s pve.pts 475", "playsound minecraft:entity.panda.ambient player @s ~ ~ ~ 1 0.7",
                             "tellraw @s {\"text\":\"Bye bye! The box gave you a teddy bear (475 points back).\",\"color\":\"gray\",\"italic\":true}"]),
]

OUT = None
def w(path, text):
    p = os.path.join(OUT, path); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f: f.write(text if text.endswith("\n") else text + "\n")
def wj(path, obj): w(path, json.dumps(obj, indent=1, ensure_ascii=False))
def fn(name, lines): w(f"data/{NS}/function/{name}.mcfunction", "\n".join(l for l in lines if l is not None))
def tj(o): return json.dumps(o, ensure_ascii=False, separators=(",", ":"))
def say(sel, text, color="gray"): return f"tellraw {sel} {tj({'text': text, 'color': color})}"


def icon(id_, name, color, lore, glint=True):
    return {"id": f"minecraft:{id_}", "count": 1, "components": {
        "minecraft:custom_name": {"text": name, "color": color, "italic": False, "bold": True},
        # a lore line is plain text, or a list of text parts (selectors, scores... resolved when the menu opens, see PvpMenus)
        "minecraft:lore": [{"text": l, "color": "gray", "italic": False} if isinstance(l, str) else
                           {"text": "", "color": "gray", "italic": False, "extra": l if isinstance(l, list) else [l]} for l in lore],
        "minecraft:enchantment_glint_override": glint,
        "minecraft:tooltip_display": {"hidden_components": ["minecraft:attribute_modifiers", "minecraft:potion_contents", "minecraft:enchantments"]}}}
PANE = {"id": "minecraft:black_stained_glass_pane", "count": 1, "components": {"minecraft:tooltip_display": {"hide_tooltip": True}}}


def npc(tag, pos, name, color, prof, skin, yaw=0, mannequin=False):
    x, y, z = pos
    if mannequin:   # mobs ignore mannequins (they'd mob a villager)
        body = (f"summon minecraft:mannequin {x} {y} {z} {{Tags:[\"{tag}\"],Rotation:[{yaw}f,0f],Invulnerable:1b,Silent:1b,immovable:1b,"
                f"hide_description:1b,CustomNameVisible:1b,CustomName:{tj({'text': name, 'color': color, 'bold': True})},"
                "equipment:{chest:{id:\"minecraft:netherite_chestplate\",count:1},mainhand:{id:\"minecraft:crossbow\",count:1}}}")
    else:
        body = (f"summon minecraft:villager {x} {y} {z} {{Tags:[\"{tag}\"],Rotation:[{yaw}f,0f],NoAI:1b,Invulnerable:1b,Silent:1b,PersistenceRequired:1b,"
                f"CustomNameVisible:1b,CustomName:{tj({'text': name, 'color': color, 'bold': True})},"
                f"VillagerData:{{profession:\"minecraft:{prof}\",level:5,type:\"minecraft:{skin}\"}},Offers:{{Recipes:[]}}}}")
    return [f"kill @e[tag={tag}]", body, f"summon minecraft:interaction {x} {y} {z} {{Tags:[\"{tag}\"],width:1.2f,height:2.2f,response:1b}}"]


def npc_adv(key, tag, menu):
    wj(f"data/{NS}/advancement/{key}.json", {"criteria": {"c": {"trigger": "minecraft:player_interacted_with_entity", "conditions": {"entity": [{
        "condition": "minecraft:entity_properties", "entity": "this",
        "predicate": {"minecraft:entity_type": "minecraft:interaction", "minecraft:nbt": f"{{Tags:[\"{tag}\"]}}"}}]}}},
        "rewards": {"function": f"{NS}:open/{key}"}})
    fn(f"open/{key}", [f"advancement revoke @s only {NS}:{key}", menu if menu.startswith("function ") else f"pvpmenu {menu}",
                       f"execute as @e[type=minecraft:interaction,tag={tag},distance=..8] run data remove entity @s interaction"])


def build():
    shutil.rmtree(OUT, ignore_errors=True)
    wj("pack.mcmeta", {"pack": {"description": "Crispy Multiverse: kit arena + Outbreak waves, custom enchants + cyberware (26.2)",
                                "min_format": PACK_FORMAT[0], "max_format": PACK_FORMAT[1]}})
    wj("data/minecraft/tags/function/load.json", {"values": [f"{NS}:load"]})
    wj("data/minecraft/tags/function/tick.json", {"values": [f"{NS}:tick"]})

    MICRO = micro.build(sys.modules[__name__])   # Micro Outbreak (micro.py)

    # ------------------------------------------------------------------ menus (opened by /pvpmenu)
    kit_lore = lambda k: k[5] + ["", "Click to pick"]
    def kit_icon(k, lore):   # character kits show their head
        it = icon(k[4], k[2], k[3], lore)
        hk = {"samurai": "edgerunner", "assassin": "lucy"}.get(k[1], k[1])
        if hk in HEADS:
            it["id"] = "minecraft:player_head"
            it["components"]["minecraft:profile"] = {"properties": [{"name": "textures", "value": HEADS[hk]}]}
        return it
    def tower_menus():
        """The Tower NPC's menus, like the UNO tables in the lobby: one player opens a lobby and leads it, others join
        it from the menu (or the chat invite), and the leader starts the climb. tower/npc opens the one that fits."""
        T, MX = "tw", tower.MAX_PLAYERS
        lead = ["Leader: ", {"selector": "@a[tag=tw.lead]", "color": "white"}]
        party = ["Players (", {"score": {"name": "#tqn", "objective": T}, "color": "white"}, f"/{MX}): ", {"selector": "@a[tag=tw.q]", "color": "white"}]
        title = {"text": "🗼 The Tower", "color": "dark_purple"}
        about = {"slot": 4, "item": icon("end_rod", "The Tower", "light_purple", [
            f"A roguelite climb, solo or up to {MX} players", "Everyone starts as a random character",
            "Clear a floor, pick 1 of 3 upgrades, climb on"]), "cmd": ""}
        how = {"slot": 13, "item": icon("written_book", "How it works", "yellow", [
            "Mob floors: mobs get stronger every floor", "Every 3rd floor a challenge: Parkour, Glass Bridge,",
            "Maze or Crafting", "Every 5th floor a boss", f"Challenges: {tower.MAX_FALLS} strikes on a floor and you're out",
            "Upgrades: Common, Rare, Epic and Legendary,", "they stack for the whole climb",
            "Dying ends your climb (unless you have an Extra Life)"]), "cmd": ""}
        best = {"slot": 15, "item": icon("gold_block", "Best Tower Floor", "gold", [
            "The highest floors reached are on", "the leaderboard in the lobby",
            "Each floor also gives mastery XP", "for the character you're playing"]), "cmd": ""}
        status = {"slot": 4, "item": icon("end_rod", "Tower lobby", "light_purple", [lead, party, "", "The leader starts the climb"]), "cmd": ""}
        leave = {"slot": 15, "item": icon("barrier", "Leave the lobby", "red", ["Stop waiting for this climb"], False), "cmd": "trigger tw.join set 2"}
        m = lambda items: {"title": title, "rows": 3, "fill": PANE, "items": items}
        return {
            "tower": m([about, how, best, {"slot": 11, "item": icon("ladder", "Create a lobby", "light_purple", [
                "Open a lobby for the next climb: you lead it", f"Others join it from this menu (up to {MX})",
                "Start whenever you're ready, solo or as a team", "", "Click to create a lobby"]), "cmd": "trigger tw.join set 1"}]),
            "tower_join": m([status, how, best, {"slot": 11, "item": icon("ladder", "Join the lobby", "light_purple", [
                lead, party, "", "Click to join"]), "cmd": "trigger tw.join set 1"}]),
            "tower_member": m([status, how, leave, {"slot": 11, "item": icon("clock", "Waiting for the leader", "yellow", [
                lead, party, "", "The climb starts when the leader starts it"]), "cmd": ""}]),
            "tower_lead": m([status, how, {**leave, "item": icon("barrier", "Leave the lobby", "red", [
                "Stop waiting for this climb", "The next player becomes leader,", "or the lobby closes if you're alone"], False)},
                {"slot": 11, "item": icon("emerald_block", "▶ Start the climb", "green", [party, "", "Click to start"]), "cmd": "trigger tw.join set 3"}]),
            "tower_busy": m([how, best, {"slot": 11, "item": icon("clock", "A climb is in progress", "yellow", [
                ["Floor ", {"score": {"name": "#floor", "objective": T}, "color": "white"}, ", climbing: ", {"selector": "@a[tag=tw.in]", "color": "white"}],
                "", "Come back when it's over"]), "cmd": ""}]),
        }

    def pve_menus():
        """The Outbreak NPC's lobby menus (pve/open_menu picks which; pve_maps opens a new lobby)."""
        lead = ["Leader: ", {"selector": "@a[tag=pve.lead]", "color": "white"}]
        mapl = ["Map: ", {"nbt": "mapname", "storage": "pvp:pve", "interpret": True}]
        party = ["Players (", {"score": {"name": "#pqn", "objective": "pve"}, "color": "white"}, "): ", {"selector": "@a[tag=pve.q]", "color": "white"}]
        title = {"text": "☣ Outbreak", "color": "dark_green"}
        status = {"slot": 4, "item": icon("zombie_head", "Outbreak lobby", "green", [mapl, lead, party, "", "The leader starts the run"]), "cmd": ""}
        kit = {"slot": 13, "item": icon("iron_sword", "Change your kit", "aqua", ["Pick a different character for this run"]), "cmd": "trigger pve.join set 92"}
        leave = {"slot": 15, "item": icon("barrier", "Leave the lobby", "red", ["Stop waiting for this run"], False), "cmd": "trigger pve.join set 99"}
        m = lambda items: {"title": title, "rows": 3, "fill": PANE, "items": items}
        return {
            "pve_join": m([status, {"slot": 13, "item": icon("iron_sword", "Join the lobby", "green", [mapl, lead, party, "", "Click to pick your kit and join"]),
                                    "cmd": "trigger pve.join set 92"}]),
            "pve_member": m([status, kit, leave, {"slot": 11, "item": icon("clock", "Waiting for the leader", "yellow", [
                mapl, lead, party, "", "The run starts when the leader starts it"]), "cmd": ""}]),
            "pve_lead": m([status, kit, {**leave, "item": icon("barrier", "Leave the lobby", "red", [
                "Stop waiting for this run", "The next player becomes leader,", "or the lobby closes if you're alone"], False)},
                {"slot": 11, "item": icon("emerald_block", "▶ Start the Outbreak", "green", [mapl, party, "", "Click to start"]), "cmd": "trigger pve.join set 93"},
                {"slot": 22, "item": icon("filled_map", "Change the map", "yellow", [mapl, "", "Click to pick another map"], False), "cmd": "pvpmenu pve_maps"}]),
            "pve_running": m([{"slot": 13, "item": icon("iron_sword", "Drop in", "green", [
                ["Wave ", {"score": {"name": "#wave", "objective": "pve"}, "color": "white"}, " on ", {"nbt": "mapname", "storage": "pvp:pve", "interpret": True}],
                ["Fighting: ", {"selector": "@a[tag=pve.in]", "color": "white"}], "", "Pick a kit to join at the next wave break"]), "cmd": "trigger pve.join set 92"},
                {"slot": 15, "item": icon("barrier", "Leave the queue", "red", ["Stop waiting to drop in"], False), "cmd": "trigger pve.join set 99"}]),
        }

    menus = {
        "kits": {"title": {"text": "⚔ Pick a kit", "color": "dark_aqua"}, "rows": 6, "fill": PANE,
                 "items":
                 [{"slot": KIT_SLOT[k[0]], "item": kit_icon(k, kit_lore(k)), "cmd": f"trigger pvp.kit set {k[0]}"} for k in KITS]
                 + [{"slot": 49, "item": icon("ender_eye", "🎲 Random character", "light_purple", ["Let fate pick one of the " + str(len(KITS)) + " characters",
                     "", "Click to fight as a random character"]), "cmd": f"trigger pvp.kit set {RANDOM_KIT}"}]},
        "pve": {"title": {"text": "☣ Outbreak: pick your loadout", "color": "dark_green"}, "rows": 6, "fill": PANE,
                "items":
                [{"slot": KIT_SLOT[k[0]], "item": kit_icon(k, k[5] + ["", "Click to queue with this kit"]), "cmd": f"trigger pve.join set {k[0]}"} for k in KITS]
                + [{"slot": 51, "item": icon("ender_eye", "🎲 Random character", "light_purple", ["Let fate pick one of the " + str(len(KITS)) + " characters",
                     "", "Click to queue as a random character"]), "cmd": f"trigger pve.join set {RANDOM_KIT}"},
                   {"slot": 47, "item": icon("barrier", "Leave the lobby", "red", ["Stop waiting for the next Outbreak"], False), "cmd": "trigger pve.join set 99"},
                   {"slot": 45, "item": icon("filled_map", "Back to maps", "yellow", ["Pick a different map"], False), "cmd": "pvpmenu pve_maps"},
                   {"slot": 49, "item": icon("zombie_head", "How Outbreak works", "green", [
                       f"{len(NORMAL_MAPS)} maps, each with its own mobs", "Endless waves; every 5th wave brings a boss", "100 points per kill + a bonus each wave",
                       "Kills can drop power-ups: Max Ammo, Insta-Kill,", "Double Points, Nuke",
                       f"{BREAK_TICKS // 20} s break between waves to re-buy gear",
                       "Spend points at the Arsenal in the arena", "or buy guns off the walls (right-click)", "Pack-a-Punch weapons (4 tiers), upgrade armor, buy perks", "Your best wave adds starting points", "Go down and you're back next wave", "Game over when the whole team is down"]), "cmd": ""}]},
        "pve_maps": {"title": {"text": "☣ Outbreak: pick a map", "color": "dark_green"}, "rows": 3, "fill": PANE, "items":
                     [{"slot": s, "item": icon(m[4], m[2], m[3], MAP_LORE[m[1]] + ["", "Click to pick your kit"]), "cmd": f"trigger pve.join set {80 + m[0]}"}
                      for s, m in zip((11, 12, 13, 14, 15), NORMAL_MAPS)]
                     + [{"slot": 4, "item": icon("zombie_head", "Outbreak (PvE)", "green", [
                         "Fight endless waves of mobs, solo or as a team", "Pick a map, then your kit, to open a lobby:",
                         "you lead it, others join it from the Outbreak NPC,", "and you start the run when everyone's in"]), "cmd": ""},
                        {"slot": 22, "item": icon("ender_eye", "Random map", "light_purple", ["Let fate decide", "", "Click to pick your kit"]), "cmd": "trigger pve.join set 91"}]},
        **pve_menus(),
        "micro": MICRO["menu"],
        "pve_hw": {"title": {"text": "🎃 Haunted Night: pick your killer", "color": "gold"}, "rows": 3, "fill": PANE, "items":
                   [{"slot": sl, "item": kit_icon(k, k[5] + ["", "Click to queue with this character"]), "cmd": f"trigger pve.join set {k[0]}"}
                    for sl, k in zip((11, 12, 13, 14, 15), HALLOWEEN_KITS)]
                   + [{"slot": 4, "item": icon("jack_o_lantern", "Haunted Night", "gold", MAP_LORE["haunted"] + [
                       "", "Only these horror icons can play it", "Survive all 10 waves to unlock a random", "Halloween cosmetic (tag, name or chat colour)",
                       f"Open until {HW_END}"]), "cmd": ""},
                      {"slot": 22, "item": icon("ender_eye", "🎲 Random killer", "light_purple", ["Let fate pick one", "", "Click to queue as a random one"]),
                       "cmd": f"trigger pve.join set {RANDOM_KIT}"},
                      {"slot": 18, "item": icon("barrier", "Leave the lobby", "red", ["Stop waiting for this run"], False), "cmd": "trigger pve.join set 99"}]},
        **tower_menus(),
        "pve_shop": {"title": {"text": "☣ Arsenal (points)", "color": "dark_green"}, "rows": 3, "fill": PANE, "items":
                     [{"slot": s, "item": icon(i[3], f"{i[1]}" + (f" · {i[4]}" if i[4] else ""), i[2], [i[5]]), "cmd": f"trigger pve.buy set {i[0]}"} for s, i in zip(SHOP_SLOTS, SHOP)]},
    }

    rules = {"keep_inventory": "true", "immediate_respawn": "true", "spawn_mobs": "false", "advance_time": "false",
             "advance_weather": "false", "show_advancement_messages": "false", "respawn_radius": "0", "locator_bar": "false",
             "spawn_phantoms": "false", "mob_griefing": "false", "spawn_wandering_traders": "false", "raids": "false",
             "spawn_patrols": "false", "ender_pearls_vanish_on_death": "true", "command_block_output": "false"}
    ab_objectives = abilities.build(fn, wj, LOBBY_BOX)
    fn("load", [
        *[f"scoreboard objectives add {o}" for o in [
            *ab_objectives,
            "pvp dummy", "pvp.kit trigger", "pvp.spawn trigger", "pvp.kn playerKillCount", "pvp.dead deathCount",
            "pvp.left minecraft.custom:minecraft.leave_game", "pvp.streak dummy", "pvp.best dummy",
            "pvp.hurt minecraft.custom:minecraft.damage_taken", "pvp.ct dummy",
            "pvp.cur dummy", "pvp.mastery trigger", "pvp.mastered dummy", "pvp.kk dummy", "pvp.kd dummy",
            "pvp.elo dummy", "pvp.dwin dummy", "pvp.dloss dummy", "pvp.dfrom dummy", "pvp.dtm dummy", "pvp.dpit dummy",
            "pvp.duela trigger", "pvp.dueld trigger", "pvp.duelstats trigger", *[f"pvp.mx{k[0]} dummy" for k in ALL_KITS],
            *[f"pvp.hw{c[0]} dummy" for c in HW_COSMETICS], "pvp.hwwins dummy", *MICRO["objectives"],
            "pve dummy", "pve.join trigger", "pve.buy trigger", "pve.k totalKillCount", "pve.kit dummy", "pve.best dummy", "pve.arm dummy", "pve.gun dummy", "pve.map dummy", "pve.rv dummy", "pve.wb dummy"]],
        'scoreboard objectives add pvp.kills playerKillCount {"text":"⚔ Kills","color":"aqua","bold":true}',
        'scoreboard objectives add pve.pts dummy {"text":"☣ Points","color":"green","bold":true}',
        "scoreboard objectives setdisplay sidebar pvp.kills",
        "bossbar add pvp:map \"\"", "bossbar set pvp:map color purple", f"bossbar set pvp:map max {ROT_SECS}",
        "execute unless score #amap pvp matches 1.. run scoreboard players set #amap pvp 1",
        "execute unless score #anext pvp matches 1.. run scoreboard players set #anext pvp 2",
        f"execute unless score #arot pvp matches 1.. run scoreboard players set #arot pvp {ROT_SECS}",
        "team add pve", "team modify pve color green", "team modify pve friendlyFire false", "team modify pve seeFriendlyInvisibles true",
        # the Outbreak sidebar: only players in the current run (rebuilt every second by pve/side), points and kills
        'scoreboard objectives add pve.side dummy {"text":"☣ Outbreak","color":"green","bold":true}', "scoreboard objectives add pve.kc dummy",
        "scoreboard objectives setdisplay sidebar.team.green pve.side",
        'bossbar add pvp:boss {"text":"Abomination","color":"dark_red"}', "bossbar set pvp:boss color red", "bossbar set pvp:boss visible false",
        *[f"gamerule {k} {v}" for k, v in rules.items()],
        f"function {NS}:ability/migrate",
        "time set 18000", "weather clear", f"setworldspawn 0 {LOBBY_Y + 1} 0", "scoreboard players set #t pvp 0",
        "scoreboard players set #100 pve 100", "scoreboard players set #5 pve 5", "scoreboard players set #20 pve 20", "scoreboard players set #4c pve 4", "scoreboard players set #2c pve 2", "scoreboard players set #8c pve 8", "scoreboard players set #12c pve 12", f"scoreboard players set #vet pve {VETERAN_PER_WAVE}",
        "execute unless score #state pve matches 0.. run scoreboard players set #state pve 0",
        "execute unless score #record pve matches 0.. run scoreboard players set #record pve 0",
        *[f"data modify storage pvp:menus {k} set value {tj(v)}" for k, v in menus.items()],
        f"function {NS}:tower/load",
        *MICRO["load"],
    ])

    fn("tick", [
        "scoreboard players enable @a pvp.kit", "scoreboard players enable @a pvp.spawn",
        f"function {NS}:ability/tick",
        f"function {NS}:tower/tick",
        f"function {NS}:micro/tick",
        f"execute as @a[tag=!pvp.seen] run function {NS}:to_lobby",
        f"execute as @a[scores={{pvp.left=1..}}] run function {NS}:to_lobby",
        f"execute as @e[type=minecraft:player,scores={{pvp.dead=1..}}] run function {NS}:respawned",
        f"execute as @a[scores={{pvp.kn=1..}}] at @s run function {NS}:killed",
        f"execute as @a[scores={{pvp.kit=1..}}] at @s run function {NS}:kit/pick",
        f"execute as @a[scores={{pvp.spawn=1..}}] run function {NS}:trigger_lobby",
        "scoreboard players enable @a pvp.mastery", f"execute as @a[scores={{pvp.mastery=1..}}] run function {NS}:mastery/list",
        "scoreboard players enable @a pvp.duela", "scoreboard players enable @a pvp.dueld", "scoreboard players enable @a pvp.duelstats",
        f"execute as @a[scores={{pvp.duela=1..}}] run function {NS}:duel/accept", f"execute as @a[scores={{pvp.dueld=1..}}] run function {NS}:duel/decline",
        f"execute as @a[scores={{pvp.duelstats=1..}}] run function {NS}:duel/stats",
        "scoreboard players remove @a[scores={pvp.dtm=1..}] pvp.dtm 1",
        f"execute as @a[scores={{pvp.dtm=1}}] run function {NS}:duel/expire",
        f"execute as @a[x={SPEC_PORTAL[0]},y={SPEC_PORTAL[1]},z={SPEC_PORTAL[2]},dx=0,dy=2,dz=2,tag=!pvp.spec] run function {NS}:spectate",
        "scoreboard players set @a[scores={pvp.hurt=1..}] pvp.ct 200", "scoreboard players set @a[scores={pvp.hurt=1..}] pvp.hurt 0",
        "scoreboard players remove @a[scores={pvp.ct=1..}] pvp.ct 1",
        f"function {NS}:pve/tick",
        "scoreboard players add #t pvp 1", f"execute if score #t pvp matches 20.. run function {NS}:second",
    ])
    fn("second", [
        "scoreboard players set #t pvp 0",
        f"function {NS}:hw/gate",
        f"function {NS}:micro/second",
        f"effect give @a[{LOBBY_BOX}] minecraft:resistance 3 4 true",
        f"effect give @a[{LOBBY_BOX}] minecraft:weakness 3 255 true",
        f"effect give @a[{LOBBY_BOX}] minecraft:saturation 3 0 true",
        # spectators in the colosseum stands can't be hurt and can't hurt anyone
        "effect give @a[tag=pvp.spec] minecraft:resistance 3 4 true", "effect give @a[tag=pvp.spec] minecraft:weakness 3 255 true",
        "effect give @a[tag=pvp.spec] minecraft:saturation 3 0 true",
        f"function {NS}:arena/second",
        f"execute as @a[tag=pvp.spec,tag=!pvp.instands] run function {NS}:to_lobby",
        # anyone (in adventure) outside the lobby and both arenas goes back to the lobby
        f"execute as @a[gamemode=adventure] unless entity @s[{LOBBY_BOX}] unless entity @s[tag=pvp.inarena] {" ".join(f"unless entity @s[{b}]" for b in PVE_BOXES.values())} unless entity @s[tag=pvp.admin,{ROOM_BOX}] unless entity @s[tag=pvp.instands] unless entity @s[tag=pvp.duel] unless entity @s[{TOWER_BOX}] unless entity @s[tag=mo.in] run function {NS}:to_lobby",   # mo.in: Micro Outbreak (micro/second keeps them in its room)
        f"function {NS}:pve/second",
        f"function {NS}:ability/second",
        f"execute as @a[{LOBBY_BOX},tag=!pvp.spec] unless items entity @s container.* minecraft:flint unless items entity @s weapon.offhand minecraft:flint run item replace entity @s hotbar.8 with {DUEL_ITEM}",
        f"function {NS}:duel/check",
        f"function {NS}:tower/second", "advancement revoke @a only pvp:towernpc",
        # fire from fire abilities goes out within a second, before it can burn the maps' wooden blocks
        "execute at @a[gamemode=adventure,tag=!pvp.spec] run fill ~-12 ~-4 ~-12 ~12 ~8 ~12 minecraft:air replace #minecraft:fire",
        # no stashing gear on the floor to pick up as another character: items dropped in the arena or a duel pit vanish
        *[f"kill @e[type=minecraft:item,{b}]" for b in ARENA_BOXES.values()], *[f"kill @e[type=minecraft:item,{box(px, pz, arena_map.PIT_R + 3, AY - 1, 25)}]" for (px, pz) in DUEL_PITS],
        f"execute as @a[tag=pvp.master] at @s unless entity @s[{LOBBY_BOX}] run particle minecraft:wax_on ~ ~1 ~ 0.35 0.6 0.35 0 5",
        f"particle minecraft:reverse_portal {SPEC_PORTAL[0] + 0.5} {SPEC_PORTAL[1] + 1.5} 0.5 0.1 0.9 0.9 0.05 40",
        # NPC clicks are advancements; clear any left granted so an NPC can never get stuck for a player
        "advancement revoke @a only pvp:npc", "advancement revoke @a only pvp:pvenpc", "advancement revoke @a only pvp:shopnpc",
    ])
    fn("to_lobby", [
        f"execute if entity @s[tag=pvp.duel] run function {NS}:duel/forfeit",
        f"execute if entity @s[tag=tw.in] run function {NS}:tower/leave", "tag @s remove tw.q", "tag @s remove tw.lead", "tag @s remove pve.lead",
        "scoreboard players add @s pve.best 0",
        "execute if entity @s[tag=pve.in] if score #state pve matches 2..3 if score #wave pve > @s pve.best run scoreboard players operation @s pve.best = #wave pve",
        "clear @s", "effect clear @s", "function cyber:admin/reset", "gamemode adventure @s",
        *PERK_RESET, *MICRO["reset"],
        "tag @s remove pve.in", "tag @s remove pve.down", "tag @s remove pve.q", "team leave @s", "tag @s remove pvp.spec",
        f"tp @s 0.5 {LOBBY_Y + 1} 0.5 180 0",
        "scoreboard players set @s pvp.left 0", "scoreboard players set @s pvp.ct 0",
        "scoreboard players add @s pvp.streak 0", "scoreboard players add @s pvp.kills 0",
        "tag @s add pvp.seen",
        "title @s actionbar {\"text\":\"Multiverse  ·  PvP Arena: fight other players  ·  Outbreak: fight waves of mobs\",\"color\":\"aqua\"}",
    ])
    fn("trigger_lobby", [
        "scoreboard players set @s pvp.spawn 0",
        "execute if score @s pvp.ct matches 1.. run return run tellraw @s {\"text\":\"You can't leave combat yet (10 s after taking damage).\",\"color\":\"red\"}",
        f"function {NS}:to_lobby",
    ])
    fn("respawned", [
        "scoreboard players set @s pvp.dead 0",
        f"execute if entity @s[tag=mo.in] run return run function {NS}:micro/died",
        f"execute if entity @s[tag=pve.in] run return run function {NS}:pve/downed",
        f"execute if entity @s[tag=tw.in] run return run function {NS}:tower/died",
        *[f"execute if score @s pvp.cur matches {k[0]} run scoreboard players add #{k[1]} pvp.kd 1" for k in ALL_KITS],   # deaths per character
        f"execute if entity @s[tag=pvp.duel] run return run function {NS}:duel/lose",
        "execute if score @s pvp.streak matches 3.. run tellraw @a [{\"selector\":\"@s\",\"color\":\"yellow\"},{\"text\":\"'s \",\"color\":\"gray\"},"
        "{\"score\":{\"name\":\"@s\",\"objective\":\"pvp.streak\"},\"color\":\"gold\"},{\"text\":\" kill streak was ended.\",\"color\":\"gray\"}]",
        "scoreboard players set @s pvp.streak 0",
        f"function {NS}:to_lobby",
    ])
    fn("killed", [
        *[f"execute if score @s pvp.cur matches {k[0]} run scoreboard players add #{k[1]} pvp.kk 1" for k in ALL_KITS],   # kills per character
        f"scoreboard players set #g pvp {MASTERY_PVP}", f"function {NS}:mastery/gain",
        "scoreboard players add @s pvp.streak 1", "scoreboard players set @s pvp.kn 0", "scoreboard players add @s pvp.best 0",
        "execute if score @s pvp.streak > @s pvp.best run scoreboard players operation @s pvp.best = @s pvp.streak",
        "effect give @s minecraft:instant_health 1 0", "effect give @s minecraft:absorption 10 0",
        "give @s minecraft:golden_apple 1",
        "playsound minecraft:entity.experience_orb.pickup player @s ~ ~ ~ 1 1.2",
        "scoreboard players operation #m pvp = @s pvp.streak", "scoreboard players set #5 pvp 5", "scoreboard players operation #m pvp %= #5 pvp",
        "execute if score @s pvp.streak matches 3 unless entity @s[tag=pvp.master] run tellraw @a [{\"selector\":\"@s\",\"color\":\"yellow\"},{\"text\":\" is on a 3 kill streak!\",\"color\":\"gold\"}]",
        "execute if score @s pvp.streak matches 3 if entity @s[tag=pvp.master] run tellraw @a [{\"text\":\"★ \",\"color\":\"gold\"},{\"selector\":\"@s\",\"color\":\"yellow\"},{\"text\":\" is on a 3 kill streak!\",\"color\":\"gold\"}]",
        "execute if score @s pvp.streak matches 5.. if score #m pvp matches 0 if entity @s[tag=pvp.master] run tellraw @a {\"text\":\"★ Master\",\"color\":\"gold\",\"bold\":true}",
        "execute if score @s pvp.streak matches 5.. if score #m pvp matches 0 run tellraw @a [{\"selector\":\"@s\",\"color\":\"yellow\"},{\"text\":\" is on a \",\"color\":\"gold\"},"
        "{\"score\":{\"name\":\"@s\",\"objective\":\"pvp.streak\"},\"color\":\"red\",\"bold\":true},{\"text\":\" kill streak!\",\"color\":\"gold\"}]",
    ])

    # ------------------------------------------------------------------ kits
    pick = ["scoreboard players operation #k pvp = @s pvp.kit", "scoreboard players set @s pvp.kit 0",
            f"execute unless entity @s[{LOBBY_BOX}] run return run tellraw @s {{\"text\":\"Pick a kit in the lobby (/spawn).\",\"color\":\"red\"}}",
            f"execute if score #k pvp matches {RANDOM_KIT} run function {NS}:kit/roll",
            f"execute if score #k pvp matches {RANDOM_KIT} run scoreboard players operation #k pvp = #rk pvp",
            "tag @s remove pve.q", "clear @s", "effect clear @s", "function cyber:admin/reset", "scoreboard players set #ok pvp 0"]
    give = []
    for (kid, key, name, color, ic, blurb, items, implants) in ALL_KITS:
        if kid not in HW_IDS: pick.append(f"execute if score #k pvp matches {kid} run function {NS}:kit/{key}")
        give.append(f"execute if score @s pve.kit matches {kid} run function {NS}:kit/{key}")
        fn(f"kit/{key}", items + FOOD + [f"function cyber:implant/{i}/kit" for i in implants] + [
            f"tellraw @s [{{\"text\":\"Kit: \",\"color\":\"gray\"}},{{\"text\":\"{name}\",\"color\":\"{color}\",\"bold\":true}},"
            + ("{\"text\":\" (cyberware installed)\",\"color\":\"gray\"}]" if implants else
             "{\"text\":\" · right-click your ability items\",\"color\":\"gray\"}]" if any("loot pvp:ability/" in l for l in items) else "{\"text\":\"\"}]"),
            *(["tellraw @s {\"text\":\"Double-tap sneak to activate your Operating System implant.\",\"color\":\"dark_gray\"}"]
              if any(i in ("sandy", "berserk") for i in implants) else []),
            f"scoreboard players set @s pvp.cur {kid}", f"function {NS}:mastery/show/{key}"])
    pick += [*[f"execute if score #k pvp matches {k[0]} run scoreboard players set #ok pvp 1" for k in KITS],
             f"execute if score #k pvp matches 101.. run function {NS}:kit/custom",
             f"execute if score #ok pvp matches 1 run function {NS}:arena/enter",
             f"execute unless score #ok pvp matches 1 run {say('@s', 'That kit no longer exists.', 'red')}"]
    fn("kit/pick", pick)
    # a random character (as the player): #rk pvp = its kit id, and they're told which
    fn("kit/roll", [f"execute store result score #r pvp run random value 1..{len(KITS)}",
                    *[f"execute if score #r pvp matches {i} run scoreboard players set #rk pvp {k[0]}" for i, k in enumerate(KITS, 1)],
                    *[f"execute if score #rk pvp matches {k[0]} run tellraw @s " + tj([{"text": "🎲 Random character: ", "color": "light_purple"},
                                                                                       {"text": k[2], "color": k[3], "bold": True}]) for k in KITS]])
    build_mastery()
    build_duels()
    tower.build(sys.modules[__name__])
    fn("kit/valid_pve", [f"execute if score #jm pve matches {HW_MAP} if score #j pve matches {k[0]} run return 1" for k in HALLOWEEN_KITS]
       + [f"execute if score #jm pve matches {HW_MAP} run return 0"]
       + [f"execute if score #j pve matches {k[0]} run return 1" for k in KITS] + ["return 0"])   # #j pve is a real kit id, #jm pve the map
    fn("kit/roll_hw", [f"execute store result score #r pvp run random value 1..{len(HALLOWEEN_KITS)}",
                       *[f"execute if score #r pvp matches {i} run scoreboard players set #rk pvp {k[0]}" for i, k in enumerate(HALLOWEEN_KITS, 1)],
                       *[f"execute if score #rk pvp matches {k[0]} run tellraw @s " + tj([{"text": "🎲 Random character: ", "color": "gold"},
                                                                                          {"text": k[2], "color": k[3], "bold": True}]) for k in HALLOWEEN_KITS]])
    # admin-made kits are given by the mod ("pvpkit give <id>", ids 101+)
    fn("kit/custom", ["execute store result storage pvp:tmp k int 1 run scoreboard players get #k pvp", f"function {NS}:kit/custom_give with storage pvp:tmp"])
    fn("kit/custom_give", ["$execute store result score #ok pvp run pvpkit give $(k)"])
    give.append(f"execute if score @s pve.kit matches 101.. run function {NS}:kit/custom_pve")
    give.append(f"execute if score @s pve.kit matches {TEST_KIT_ID} run function {NS}:kit/test_david")
    fn("kit/test_david", TEST_KIT)
    fn("admin/test_david", [   # admin-only: queue for Outbreak with the David test kit (pick a map in the menu first)
        "tag @s add pvp.tester", f"scoreboard players set @s pve.join {TEST_KIT_ID}",
        say("@s", "Queuing you for Outbreak with the David test kit (your last-picked map).", "dark_red")])
    fn("kit/give_pve", give)
    fn("kit/custom_pve", ["execute store result storage pvp:tmp k int 1 run scoreboard players get @s pve.kit", f"function {NS}:kit/custom_give with storage pvp:tmp"])

    build_rotation()
    fn("arena/enter", [f"function {NS}:arena/spawn", "effect give @s minecraft:resistance 3 4 true", "scoreboard players set @s pvp.ct 0",
                       f"function {NS}:arena/subtitle", "title @s title {\"text\":\"FIGHT\",\"color\":\"red\",\"bold\":true}",
                       "playsound minecraft:block.beacon.power_select player @s ~ ~ ~ 1 1.4"])

    npc_adv("npc", "pvp.npc", "kits")
    npc_adv("pvenpc", "pvp.pvenpc", f"function {NS}:pve/open_menu")
    npc_adv("shopnpc", "pvp.shopnpc", "pve_shop")
    npc_adv("micronpc", "pvp.micronpc", f"function {NS}:micro/open")

    build_pve()
    build_halloween()

    # ------------------------------------------------------------------ admin: build the lobby + arenas (chunks must be loaded)
    holo = lambda y, z, text, scale=1: (f"summon minecraft:text_display 0.5 {y} {z} {{Tags:[\"pvp.holo\"],billboard:\"center\",background:0,"
                                        f"transformation:{{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[{scale}f,{scale}f,{scale}f]}},"
                                        f"text:{tj(text)}}}")
    # one big leaderboard on the south side of the lobby (top 3 of every category); the mod (Leaderboards.java) fills
    # in the text every 5 s
    lb = ["kill @e[tag=pvp.lb]",
          f"summon minecraft:text_display 0.5 {LOBBY_Y + 1.6} {LOBBY_R - 2.5} {{Tags:[\"pvp.lb\",\"pvp.lb.all\"],billboard:\"center\","
          "background:-2144728518,line_width:400,transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],"
          "translation:[0f,0f,0f],scale:[1.3f,1.3f,1.3f]},text:{\"text\":\"Loading leaderboards...\",\"color\":\"gray\"}}"]
    fn("admin/place_leaderboard", lb)
    fn("admin/place_npc", [
        f"function {NS}:admin/place_leaderboard",
        *npc("pvp.npc", KIT_NPC, "⚔ PvP Arena ⚔", "aqua", "weaponsmith", "snow"),
        *npc("pvp.pvenpc", PVE_NPC, "☣ Outbreak ☣", "green", "cleric", "swamp"),
        *npc("pvp.towernpc", TOWER_NPC, "🗼 The Tower 🗼", "light_purple", "librarian", "taiga"),
        *npc("pvp.micronpc", MICRO["npc"], "🔬 Micro Outbreak 🔬", "aqua", "cartographer", "plains", 230),
        f"function {NS}:admin/place_holo",
    ])
    fn("admin/place_holo", [   # the lobby board (on its own, so it can be redone without touching the NPCs)
        "kill @e[tag=pvp.holo]",
        holo(LOBBY_Y + 7.2, -LOBBY_R + 1.5, {"text": "MULTIVERSE", "color": "light_purple", "bold": True}, 3),   # above the 6-line board
        holo(LOBBY_Y + 4.6, -LOBBY_R + 1.5, [{"text": "PvP Arena: ", "color": "aqua"}, {"text": f"{len(ARENA_MAPS)} rotating maps from their worlds", "color": "gray"},
                                              {"text": "   Outbreak: ", "color": "green"}, {"text": "waves of mobs, solo or team", "color": "gray"},
                                              {"text": f"\n{len(KITS)} characters from your favourite shows and games", "color": "yellow"},
                                              {"text": "\nPvP · Duels · Outbreak · The Tower", "color": "white"},
                                              {"text": "\nThe Tower: ", "color": "light_purple"}, {"text": "climb floor by floor, solo or with friends", "color": "gray"},
                                              {"text": "\nEvery character has their own abilities · /spawn to return", "color": "dark_gray"}]),
    ])
    L, Y = LOBBY_R, LOBBY_Y
    # the Multiverse hub: a deepslate rift with purple accents (amethyst, purpur, crying obsidian), a purple beacon beam
    # rising from spawn, a pillar-and-glass rim, character heads on the west side and the spectate gate on the east
    lobby = [f"fill {-L} {Y} {-L} {L} {Y} {L} minecraft:deepslate_tiles",
             f"fill {-L + 1} {Y + 1} {-L + 1} {L - 1} {Y + 30} {L - 1} minecraft:air", "kill @e[tag=pvp.lobbydeco]"]
    for a in (-L, L):   # outer ring
        lobby += [f"fill {a} {Y} {-L} {a} {Y} {L} minecraft:polished_deepslate", f"fill {-L} {Y} {a} {L} {Y} {a} minecraft:polished_deepslate"]
    ring = sorted({(x, z) for x in range(-L, L + 1) for z in range(-L, L + 1) if abs(math.hypot(x, z) - 6.5) < 0.5})
    lobby += [f"setblock {x} {Y} {z} minecraft:amethyst_block" for x, z in ring]               # a ring at radius 6-7
    lobby += [f"fill {-L + 1} {Y} 0 {L - 1} {Y} 0 minecraft:purpur_block", f"fill 0 {Y} {-L + 1} 0 {Y} {L - 1} minecraft:purpur_block",
              f"fill -2 {Y} -2 2 {Y} 2 minecraft:polished_blackstone_bricks", f"fill -1 {Y} -1 1 {Y} 1 minecraft:crying_obsidian",
              f"setblock 0 {Y} 0 minecraft:purple_stained_glass",                                  # the beam comes up through spawn
              f"fill -1 {Y - 3} -1 1 {Y - 3} 1 minecraft:iron_block", f"setblock 0 {Y - 2} 0 minecraft:beacon", f"setblock 0 {Y - 1} 0 minecraft:air"]
    for a in (-L + 2, L - 2):
        for b in (-L + 2, L - 2):
            lobby.append(f"setblock {a} {Y} {b} minecraft:pearlescent_froglight")
    for (nx, nz) in ((KIT_NPC[0], KIT_NPC[2]), (PVE_NPC[0], PVE_NPC[2]), (TOWER_NPC[0], TOWER_NPC[2])):   # a podium under each NPC
        cx, cz = math.floor(nx), math.floor(nz)
        lobby += [f"fill {cx - 1} {Y} {cz - 1} {cx + 1} {Y} {cz + 1} minecraft:chiseled_deepslate", f"setblock {cx} {Y} {cz} minecraft:pearlescent_froglight"]
    # the rim: deepslate pillars (end rods on top) with purple glass between; the east middle is the spectate gate
    posts = (-L, -7, -3, 3, 7, L)
    for a in (-L, L):
        lobby += [f"fill {a} {Y + 1} {-L} {a} {Y + 2} {L} minecraft:purple_stained_glass_pane[north=true,south=true]",
                  f"fill {-L} {Y + 1} {a} {L} {Y + 2} {a} minecraft:purple_stained_glass_pane[east=true,west=true]"]
        for p_ in posts:
            for (x, z) in ((a, p_), (p_, a)):
                lobby += [f"fill {x} {Y + 1} {z} {x} {Y + 3} {z} minecraft:deepslate_bricks", f"setblock {x} {Y + 4} {z} minecraft:end_rod[facing=up]"]
    # Hall of Heroes: character heads on pedestals along the west side, facing whoever looks at them
    heroes = ("maul", "shrek", "pikachu", "spartan", "mario", "spiderman", "randy")
    for i, key in enumerate(heroes):
        z = -6 + 2 * i
        k = next(k for k in KITS if k[1] == key)
        lobby += [f"setblock {-L + 2} {Y + 1} {z} minecraft:deepslate_bricks", f"setblock {-L + 2} {Y + 2} {z} minecraft:amethyst_block",
                  f"summon minecraft:item_display {-L + 2.5} {Y + 3.85} {z + 0.5} {{Tags:[\"pvp.lobbydeco\"],billboard:\"vertical\","
                  f"transformation:{{left_rotation:[0f,1f,0f,0f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[1.3f,1.3f,1.3f]}},"
                  f"item:{{id:\"minecraft:player_head\",count:1,components:{{\"minecraft:profile\":{{properties:[{{name:\"textures\",value:\"{HEADS[key]}\"}}]}}}}}}}}",
                  f"summon minecraft:text_display {-L + 2.5} {Y + 4.65} {z + 0.5} {{Tags:[\"pvp.lobbydeco\"],billboard:\"center\",background:0,"
                  f"transformation:{{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[0.7f,0.7f,0.7f]}},"
                  f"text:{tj({'text': k[2], 'color': k[3], 'bold': True})}}}"]
    lobby.append(f"summon minecraft:text_display {-L + 2.5} {Y + 5.3} 0.5 {{Tags:[\"pvp.lobbydeco\"],billboard:\"center\",background:0,"
                 f"transformation:{{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[1.2f,1.2f,1.2f]}},"
                 f"text:{tj([{'text': 'HALL OF HEROES', 'color': 'light_purple', 'bold': True}, {'text': chr(10) + f'{len(KITS)} characters to play', 'color': 'gray', 'bold': False}])}}}")
    B = L + 1   # invisible walls so nobody falls off
    lobby += [f"fill {-B} {Y + 1} {-B} {B} {Y + 15} {-B} minecraft:barrier", f"fill {-B} {Y + 1} {B} {B} {Y + 15} {B} minecraft:barrier",
              f"fill {-B} {Y + 1} {-B} {-B} {Y + 15} {B} minecraft:barrier", f"fill {B} {Y + 1} {-B} {B} {Y + 15} {B} minecraft:barrier"]
    fn("admin/build_lobby", lobby + [f"function {NS}:admin/build_portal", f"function {NS}:admin/build_micro", f"function {NS}:admin/place_npc"])
    # the spectate gate on the east side, in the lobby's style: deepslate pillars and lintel, an amethyst keystone, a crying
    # obsidian back that glows like a portal, end rods; walking through it (tick: function spectate) takes you to the stands
    X, PY = SPEC_PORTAL[0], SPEC_PORTAL[1]
    fn("admin/build_portal", [
        f"fill {X - 1} {PY} -2 {X + 1} {PY + 5} 2 minecraft:air",
        f"fill {X + 1} {PY} -1 {X + 1} {PY + 2} 1 minecraft:crying_obsidian",
        *[f"fill {X} {PY} {z} {X + 1} {PY + 3} {z} minecraft:deepslate_bricks" for z in (-2, 2)],
        f"fill {X} {PY + 3} -2 {X + 1} {PY + 3} 2 minecraft:chiseled_deepslate", f"setblock {X} {PY + 3} 0 minecraft:amethyst_block",
        f"fill {X} {PY + 4} -2 {X + 1} {PY + 4} 2 minecraft:deepslate_brick_slab[type=bottom]",
        f"setblock {X} {PY + 4} 0 minecraft:amethyst_cluster[facing=up]",
        *[f"setblock {X} {PY + 4} {z} minecraft:end_rod[facing=up]" for z in (-2, 2)],
        *[f"setblock {X - 1} {PY + 2} {z} minecraft:amethyst_cluster[facing=west]" for z in (-2, 2)],
        f"fill {X - 1} {PY - 1} -1 {X} {PY - 1} 1 minecraft:crying_obsidian",
        "kill @e[tag=pvp.specholo]",
        f"summon minecraft:text_display {X - 0.5} {PY + 5.4} 0.5 {{Tags:[\"pvp.specholo\"],billboard:\"center\",background:0,"
        "text:[{\"text\":\"👁 Spectate the Arena\",\"color\":\"light_purple\",\"bold\":true},{\"text\":\"\\nWalk through to watch from the stands\",\"color\":\"gray\"}]}"])
    fn("spectate", [
        "clear @s", "effect clear @s", "gamemode adventure @s", "tag @s add pvp.spec", "tag @s add pvp.instands", f"function {NS}:arena/spec_tp",
        "effect give @s minecraft:resistance 3 4 true", "effect give @s minecraft:weakness 3 255 true",
        "playsound minecraft:block.portal.travel player @s ~ ~ ~ 0.4 1.4",
        "tellraw @s [{\"text\":\"👁 You're in the stands. \",\"color\":\"gold\"},{\"text\":\"Watch the fights, walk the rim, and type \",\"color\":\"gray\"},"
        "{\"text\":\"/spawn\",\"color\":\"yellow\"},{\"text\":\" to go back.\",\"color\":\"gray\"}]"])

    # the colosseum (arena_map.py): clear it and its stands, lay the floor, then draw it (wall, barrier and lid included)
    S = arena_map.EXTENT
    ar = [f"fill {ACX - S} {AY + 1 + k} {ACZ - S} {ACX + S} {AY + 2 + k} {ACZ + S} minecraft:air" for k in range(0, 32, 2)]
    ar.append(f"fill {ACX - AR} {AY} {ACZ - AR} {ACX + AR} {AY} {ACZ + AR} minecraft:smooth_sandstone")
    g = arena_map.colosseum(SPAWNS)
    arena_map.check(g, SPAWNS)
    ar += outbreak_maps.commands(g, ACX, AY, ACZ)
    fn("admin/build_arena", ar)
    for (i, key, *_), builder in zip(ARENA_MAPS[1:], (m[5] for m in arena_maps.MAPS)):
        g = builder()
        arena_maps.check(g, key)
        cx, cz = MAP_AT[i]
        E = arena_maps.E
        out = [f"fill {cx - E} {AY + 1 + k} {cz - E} {cx + E} {AY + 2 + k} {cz + E} minecraft:air" for k in range(0, arena_maps.TOP + 1, 2)]
        out += arena_maps.commands(g, cx, AY, cz)
        out.append(f"kill @e[tag=pvp.mapdeco_{key}]")
        for (lx, ly, lz, text, yaw, sc) in g.labels:
            out.append(f"summon minecraft:text_display {cx + lx:.2f} {AY + ly:.2f} {cz + lz:.2f} {{Tags:[\"pvp.mapdeco\",\"pvp.mapdeco_{key}\"],"
                       f"billboard:\"fixed\",Rotation:[{yaw}f,0f],background:0,shadow:1b,line_width:400,"
                       f"transformation:{{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[{sc}f,{sc}f,{sc}f]}},"
                       f"text:{tj(text)}}}")
        for (ent, lx, ly, lz, nbt) in g.summons:
            out.append(f"summon minecraft:{ent} {cx + lx:.2f} {AY + ly:.2f} {cz + lz:.2f} {{Tags:[\"pvp.mapdeco\",\"pvp.mapdeco_{key}\"],{nbt}}}")
        fn(f"admin/build_map_{key}", out)
    fn("admin/build", [f"function {NS}:admin/build_lobby", f"function {NS}:admin/build_arena", f"function {NS}:admin/build_pve", f"function {NS}:admin/build_room"])
    build_room()
    build_velocity()


def build_velocity():
    """pvp:velocity - bows and crossbows: arrows leave 20% faster per level (so they also drop less and hit harder).
    Runs on projectile_spawned; the level is read from the arrow's own copy of the weapon, so /fe levels work too."""
    wj(f"data/{NS}/enchantment/velocity.json", {
        "description": {"text": "Velocity", "color": "aqua"},
        "supported_items": ["minecraft:bow", "minecraft:crossbow"], "weight": 2, "max_level": VELOCITY_MAX,
        "min_cost": {"base": 10, "per_level_above_first": 9}, "max_cost": {"base": 40, "per_level_above_first": 9},
        "anvil_cost": 4, "slots": ["hand"],
        "effects": {"minecraft:projectile_spawned": [{"effect": {"type": "minecraft:run_function", "function": f"{NS}:ench/velocity"}}]}})
    fn("ench/velocity", [   # as the arrow: Motion *= (5 + level) / 5
        f'execute store result score #vl {NS} run data get entity @s weapon.components."minecraft:enchantments"."{NS}:velocity"',
        f"execute if score #vl {NS} matches {VELOCITY_CAP + 1}.. run scoreboard players set #vl {NS} {VELOCITY_CAP}",
        f"execute unless score #vl {NS} matches 1.. run return 0",
        f"scoreboard players add #vl {NS} 5",
        *[l for i in range(3) for l in (
            f"execute store result score #vm {NS} run data get entity @s Motion[{i}] 10000",
            f"scoreboard players operation #vm {NS} *= #vl {NS}",
            f"execute store result entity @s Motion[{i}] double 0.00002 run scoreboard players get #vm {NS}")],
    ])


def build_room():
    """Sealed admin room under the lobby. Ops: /function pvp:admin/room (in, creative), /function pvp:admin/leave."""
    Y = ROOM_Y
    chests = []   # (label, colour, list of item commands: ("book", id, lvl) or ("loot", key))
    for group, color in (("Melee", "red"), ("Ranged", "green"), ("Tools", "yellow"), ("Armor", "aqua")):
        books = [("book", e["id"], e["max"]) for e in ENCHANTS if e["group"] == group]
        if group == "Ranged": books.append(("book", f"{NS}:velocity", VELOCITY_MAX))
        parts = [books[i:i + 27] for i in range(0, len(books), 27)]
        for n, part in enumerate(parts, 1):
            chests.append((f"{group} enchants" + (f" {n}/{len(parts)}" if len(parts) > 1 else ""), color, part))
    chests.append(("Cyberware", "light_purple", [("loot", k) for k in IMPLANT_KEYS]))
    # north wall: melee, ranged, tools; south wall: armor, cyberware
    north = [c for c in chests if not c[0].startswith(("Armor", "Cyber"))]
    south = [c for c in chests if c[0].startswith(("Armor", "Cyber"))]
    spots = [(c, x, -3, "south") for c, x in zip(north, range(-(len(north) - 1), len(north), 2))] + \
            [(c, x, 3, "north") for c, x in zip(south, range(-(len(south) - 1), len(south), 2))]
    b = [f"fill -10 {Y} -5 10 {Y + 5} 5 minecraft:polished_deepslate hollow",
         f"fill -9 {Y} -4 9 {Y} 4 minecraft:deepslate_tiles", f"fill -9 {Y} 0 9 {Y} 0 minecraft:cyan_concrete",
         f"fill -9 {Y + 5} -4 9 {Y + 5} 4 minecraft:sea_lantern", "kill @e[tag=pvp.roomholo]",
         f"summon minecraft:text_display 0.5 {Y + 3.6} 0.5 {{Tags:[\"pvp.roomholo\"],billboard:\"center\",background:0,"
         f"text:[{{\"text\":\"ADMIN ROOM\",\"color\":\"gold\",\"bold\":true}},{{\"text\":\"\\nEvery custom enchant (max level) + all cyberware\\n/function pvp:admin/fill_room refills · /function pvp:admin/leave\",\"color\":\"gray\"}}]}}"]
    fill = []
    for (label, color, items), x, z, facing in spots:
        b.append(f"setblock {x} {Y + 1} {z} minecraft:chest[facing={facing}]{{CustomName:{tj({'text': label, 'color': color})}}} replace")
        b.append(f"summon minecraft:text_display {x + 0.5} {Y + 2.3} {z + 0.5} {{Tags:[\"pvp.roomholo\"],billboard:\"center\",background:0,"
                 f"text:{tj({'text': label, 'color': color, 'bold': True})}}}")
        fill.append(f"data modify block {x} {Y + 1} {z} Items set value []")
        for slot, it in enumerate(items):
            if it[0] == "book":
                fill.append(f"item replace block {x} {Y + 1} {z} container.{slot} with minecraft:enchanted_book"
                            f"[minecraft:stored_enchantments={{\"{it[1] if ':' in it[1] else 'crispy_enchants:' + it[1]}\":{it[2]}}}]")
            else:
                fill.append(f"loot replace block {x} {Y + 1} {z} container.{slot} loot cyber:item/{it[1]}")
    fn("admin/build_room", b + [f"function {NS}:admin/fill_room"])
    fn("admin/fill_room", fill + [say("@s", "Admin room chests refilled.", "gold")])
    fn("admin/room", ["tag @s add pvp.admin", "gamemode creative @s", f"tp @s 0.5 {Y + 1} 0.5 180 0",   # keeps your implants (for /pvpkit create)
                      say("@s", "Admin room: take what you need. /function pvp:admin/leave to go back.", "gold")])
    fn("admin/leave", ["tag @s remove pvp.admin", f"function {NS}:to_lobby"])
    # /function pvp:admin/unbreakable: every item with durability you carry (inventory, armor, offhand) becomes unbreakable;
    # food, potions etc. are left alone so they still stack
    wj(f"data/{NS}/item_modifier/unbreakable.json", {"function": "minecraft:set_components", "components": {"minecraft:unbreakable": {}}})
    fn("admin/unbreakable", [f"execute if items entity @s {sl} *[minecraft:max_damage] run item modify entity @s {sl} {NS}:unbreakable" for sl in
                             [f"container.{i}" for i in range(36)] + ["armor.head", "armor.chest", "armor.legs", "armor.feet", "weapon.offhand"]]
       + [say("@s", "All your gear with durability is now unbreakable.", "gold")])


def walls(cx, cz, r, block, stripe):
    """Visible walls (6 high, stripe at 4) plus barrier up to a barrier ceiling 31 above the floor."""
    W1, W2, Z1, Z2 = cx - r - 1, cx + r + 1, cz - r - 1, cz + r + 1
    out = []
    for (a1, b1, a2, b2) in ((W1, Z1, W2, Z1), (W1, Z2, W2, Z2), (W1, Z1, W1, Z2), (W2, Z1, W2, Z2)):
        out += [f"fill {a1} {AY} {b1} {a2} {AY + 5} {b2} minecraft:{block}",
                f"fill {a1} {AY + 4} {b1} {a2} {AY + 4} {b2} minecraft:{stripe}",
                f"fill {a1} {AY + 6} {b1} {a2} {AY + 30} {b2} minecraft:barrier"]
    out.append(f"fill {W1} {AY + 31} {Z1} {W2} {AY + 31} {Z2} minecraft:barrier")
    return out


def afford(name, cost):
    return (f"tellraw @s [{{\"text\":\"{name} costs {cost:,} points (you have \",\"color\":\"red\"}},"
            "{\"score\":{\"name\":\"@s\",\"objective\":\"pve.pts\"},\"color\":\"white\"},{\"text\":\").\",\"color\":\"red\"}]")


def build_duels():
    """1v1 duels: the Duel Challenge item (lobby), accept/decline, three pits, ELO, forfeits and walkovers."""
    D = f"{NS}:duel"
    say_ = lambda who, parts: f"tellraw {who} {tj(parts)}"
    elo_init = "execute unless score @s pvp.elo matches -99999.. run scoreboard players set @s pvp.elo %d" % DUEL_START
    wj(f"data/{NS}/advancement/duel_use.json", {"criteria": {"c": {"trigger": "minecraft:consume_item",
        "conditions": {"item": {"items": "minecraft:flint"}}}}, "rewards": {"function": f"{NS}:duel/use"}})
    fn("duel/use", [
        f"advancement revoke @s only {NS}:duel_use",
        f"execute unless entity @s[{LOBBY_BOX}] run return 0",
        "execute unless score @s pvp.id matches 1.. store result score @s pvp.id run scoreboard players add #nextid pvp 1",
        "tag @s add pvp.caster", "scoreboard players set #ray pvp 16", f"execute at @s run function {NS}:ability/ray_start",
        f"execute unless entity @a[tag=pvp.hit] run {say('@s', 'Look at a player in the lobby and right-click to challenge them.', 'gray')}",
        f"execute as @a[tag=pvp.hit,limit=1] run function {D}/challenged",
        "tag @s remove pvp.caster", "tag @e[tag=pvp.hit] remove pvp.hit"])
    fn("duel/challenged", [   # as the target; the challenger is the nearest player tagged... found by id
        "tag @a remove pvp.dsend", "execute as @a[tag=pvp.caster] run tag @s add pvp.dsend",
        f"execute if entity @s[tag=pvp.duel] run return run tellraw @a[tag=pvp.dsend] {tj({'text': 'They are already in a duel.', 'color': 'red'})}",
        f"execute unless entity @s[{LOBBY_BOX}] run return run tellraw @a[tag=pvp.dsend] {tj({'text': 'They need to be in the lobby.', 'color': 'red'})}",
        "execute unless score @s pvp.id matches 1.. store result score @s pvp.id run scoreboard players add #nextid pvp 1",
        "scoreboard players operation @s pvp.dfrom = @p[tag=pvp.dsend] pvp.id", "scoreboard players set @s pvp.dtm 600",
        "tellraw @a[tag=pvp.dsend] " + tj([{"text": "⚔ Duel challenge sent to ", "color": "gold"}, {"selector": "@s", "color": "yellow"},
                                         {"text": " (30 s to accept).", "color": "gray"}]),
        "tellraw @s " + tj([{"text": "⚔ ", "color": "gold"}, {"selector": "@a[tag=pvp.dsend]", "color": "yellow"},
                            {"text": " challenges you to a duel! ", "color": "gold"},
                            {"text": "[Accept]", "color": "green", "bold": True, "click_event": {"action": "run_command", "command": "/trigger pvp.duela"},
                             "hover_event": {"action": "show_text", "value": "Fight them 1v1 in a duel pit"}},
                            {"text": " "},
                            {"text": "[Decline]", "color": "red", "bold": True, "click_event": {"action": "run_command", "command": "/trigger pvp.dueld"}}]),
        "playsound minecraft:item.goat_horn.sound.0 player @s ~ ~ ~ 0.6 1.2", "tag @a remove pvp.dsend"])
    fn("duel/expire", ["scoreboard players set @s pvp.dfrom 0", "scoreboard players set @s pvp.dtm 0",
                       say("@s", "The duel challenge expired.", "gray")])
    fn("duel/decline", ["scoreboard players set @s pvp.dueld 0",
                        "execute unless score @s pvp.dfrom matches 1.. run return 0",
                        "scoreboard players operation #from pvp = @s pvp.dfrom", "tag @s add pvp.ddec",
                        "execute as @a if score @s pvp.id = #from pvp run tellraw @s " + tj([{"selector": "@a[tag=pvp.ddec]", "color": "yellow"}, {"text": " declined your duel.", "color": "gray"}]),
                        "tag @s remove pvp.ddec",
                        "scoreboard players set @s pvp.dfrom 0", "scoreboard players set @s pvp.dtm 0", say("@s", "Duel declined.", "gray")])
    acc = ["scoreboard players set @s pvp.duela 0",
           f"execute unless score @s pvp.dfrom matches 1.. run return run {say('@s', 'You have no duel challenge to accept.', 'gray')}",
           "scoreboard players operation #from pvp = @s pvp.dfrom", "scoreboard players set @s pvp.dfrom 0", "scoreboard players set @s pvp.dtm 0",
           "tag @a remove pvp.da", "tag @a remove pvp.db",
           "execute as @a if score @s pvp.id = #from pvp run tag @s add pvp.da", "tag @s add pvp.db",
           f"execute unless entity @a[tag=pvp.da,{LOBBY_BOX},tag=!pvp.duel] run return run {say('@s', 'They are no longer in the lobby.', 'red')}",
           f"execute unless entity @s[{LOBBY_BOX}] run return run {say('@s', 'You need to be in the lobby.', 'red')}",
           "scoreboard players set #pit pvp 0"]
    for n in range(len(DUEL_PITS), 0, -1):
        acc.append(f"execute unless score #duel{n} pvp matches 1 run scoreboard players set #pit pvp {n}")
    acc += [f"execute if score #pit pvp matches 0 run return run tellraw @a[tag=pvp.da] {tj({'text': 'All duel pits are busy, try again in a moment.', 'color': 'red'})}",
            f"execute if score #pit pvp matches 0 run return run {say('@s', 'All duel pits are busy, try again in a moment.', 'red')}",
            f"function {D}/start"]
    fn("duel/accept", acc)
    # start: both players into pit #pit, A (challenger) and B (accepter)
    st = [*[f"execute if score #pit pvp matches {n} run scoreboard players set #duel{n} pvp 1" for n in range(1, len(DUEL_PITS) + 1)],
          "scoreboard players operation @a[tag=pvp.da] pvp.dpit = #pit pvp", "scoreboard players operation @a[tag=pvp.db] pvp.dpit = #pit pvp",
          f"execute as @a[tag=pvp.da] run function {D}/prep", f"execute as @a[tag=pvp.db] run function {D}/prep"]
    for n, (px, pz) in enumerate(DUEL_PITS, 1):
        (ax, az, ay), (bx, bz, by) = arena_map.PIT_SPAWNS
        st += [f"execute if score #pit pvp matches {n} run tp @a[tag=pvp.da] {px + ax + 0.5} {AY + 1} {pz + az + 0.5} {ay} 0",
               f"execute if score #pit pvp matches {n} run tp @a[tag=pvp.db] {px + bx + 0.5} {AY + 1} {pz + bz + 0.5} {by} 0"]
    st += ["tellraw @a " + tj([{"text": "⚔ ", "color": "gold"}, {"selector": "@a[tag=pvp.da]", "color": "yellow"}, {"text": " and ", "color": "gray"},
                             {"selector": "@a[tag=pvp.db]", "color": "yellow"}, {"text": " are dueling!", "color": "gold"}]),
           "tag @a remove pvp.da", "tag @a remove pvp.db"]
    fn("duel/start", st)
    # prep: as each dueler, a random character (so nobody can bring their best one), 3 s of grace
    fn("duel/prep", [elo_init, "tag @s add pvp.duel", "tag @s remove pve.q", "clear @s", "effect clear @s", "function cyber:admin/reset", *PERK_RESET,
                     "gamemode adventure @s",
                     f"function {NS}:kit/roll", "scoreboard players operation @s pvp.cur = #rk pvp",
                     *[f"execute if score @s pvp.cur matches {k[0]} run function {NS}:kit/{k[1]}" for k in KITS],
                     "effect give @s minecraft:resistance 3 4 true", "effect give @s minecraft:weakness 3 255 true",
                     "scoreboard players set @s pvp.ct 0", "scoreboard players set @s pvp.streak 0",
                     "title @s title {\"text\":\"DUEL\",\"color\":\"gold\",\"bold\":true}",
                     *[f"execute if score @s pvp.cur matches {k[0]} run title @s subtitle " + tj([{"text": "You are ", "color": "gray"}, {"text": k[2], "color": k[3], "bold": True},
                                                                                              {"text": " · fight in 3 s", "color": "gray"}]) for k in KITS],
                     *[f"execute if score @s pvp.cur matches {k[0]} run tellraw @a " + tj([{"text": "⚔ ", "color": "gold"}, {"selector": "@s", "color": "yellow"},
                                                                                         {"text": " fights as ", "color": "gray"}, {"text": k[2], "color": k[3], "bold": True}]) for k in KITS]])
    # ELO: expected score from the rating gap (loser - winner), in 25-point steps
    delta = []
    for d in range(-400, 425, 25):
        e_w = 1 / (1 + 10 ** (d / 400))
        lo = "" if d == -400 else str(d - 12)
        hi = "" if d == 400 else str(d + 12)
        delta.append(f"execute if score #d pvp matches {lo}..{hi} run scoreboard players set #delta pvp {max(1, round(DUEL_K * (1 - e_w)))}")
    # lose: as the loser (died, forfeited); the winner is the other dueler in the same pit
    fn("duel/lose", ["scoreboard players set @s pvp.dead 0", "scoreboard players operation #pit pvp = @s pvp.dpit", "tag @s remove pvp.duel",
                     "tag @a remove pvp.dw", "execute as @a[tag=pvp.duel] if score @s pvp.dpit = #pit pvp run tag @s add pvp.dw",
                     f"execute if entity @a[tag=pvp.dw] run function {D}/result",
                     f"execute if entity @a[tag=pvp.dw] run function {D}/free",   # (a walkover already freed the pit)
                     "scoreboard players set @s pvp.dpit 0", f"function {NS}:to_lobby"])
    fn("duel/forfeit", [say("@s", "You left the duel: that counts as a loss.", "red"), f"function {D}/lose"])
    fn("duel/result", [   # as the loser; @a[tag=pvp.dw] is the winner
        elo_init, f"execute as @a[tag=pvp.dw] run {elo_init}",
        "scoreboard players operation #d pvp = @s pvp.elo", "scoreboard players operation #d pvp -= @p[tag=pvp.dw] pvp.elo", *delta,
        "scoreboard players operation @a[tag=pvp.dw] pvp.elo += #delta pvp", "scoreboard players operation @s pvp.elo -= #delta pvp",
        "scoreboard players add @a[tag=pvp.dw] pvp.dwin 1", "scoreboard players add @s pvp.dloss 1",
        "tellraw @a " + tj([{"text": "⚔ ", "color": "gold"}, {"selector": "@a[tag=pvp.dw]", "color": "green"}, {"text": " won a duel against ", "color": "gray"},
                            {"selector": "@s", "color": "red"}, {"text": " (+", "color": "gray"}, {"score": {"name": "#delta", "objective": "pvp"}, "color": "gold"},
                            {"text": " rating)", "color": "gray"}]),
        "execute as @a[tag=pvp.dw] run title @s title {\"text\":\"VICTORY\",\"color\":\"gold\",\"bold\":true}",
        "title @s title {\"text\":\"DEFEAT\",\"color\":\"red\",\"bold\":true}",
        "execute as @a[tag=pvp.dw] at @s run playsound minecraft:ui.toast.challenge_complete player @s ~ ~ ~ 1 1",
        f"execute as @a[tag=pvp.dw] run function {D}/send_home"])
    fn("duel/send_home", ["tag @s remove pvp.duel", "scoreboard players set @s pvp.dpit 0", "tag @s remove pvp.dw", f"function {NS}:to_lobby"])
    fn("duel/free", [f"execute if score #pit pvp matches {n} run scoreboard players set #duel{n} pvp 0" for n in range(1, len(DUEL_PITS) + 1)])
    # every second: a pit with one dueler left (the other logged out) is a walkover; an empty busy pit is freed
    chk = []
    for n in range(1, len(DUEL_PITS) + 1):
        chk += [f"execute store result score #c pvp if entity @a[tag=pvp.duel,scores={{pvp.dpit={n}}}]",
                f"execute if score #c pvp matches 1 as @a[tag=pvp.duel,scores={{pvp.dpit={n}}}] run function {D}/walkover",
                f"execute if score #c pvp matches 0 run scoreboard players set #duel{n} pvp 0"]
    fn("duel/check", chk)
    fn("duel/walkover", [say("@s", "Your opponent left the duel, so you win (no rating change).", "gold"),
                         "scoreboard players add @s pvp.dwin 1", "scoreboard players operation #pit pvp = @s pvp.dpit", f"function {D}/free",
                         f"function {D}/send_home"])
    fn("duel/stats", ["scoreboard players set @s pvp.duelstats 0", elo_init, "scoreboard players add @s pvp.dwin 0", "scoreboard players add @s pvp.dloss 0",
                      "tellraw @s " + tj([{"text": "⚔ Duel rating: ", "color": "gold"}, {"score": {"name": "@s", "objective": "pvp.elo"}, "color": "white", "bold": True},
                                          {"text": "  ·  ", "color": "dark_gray"}, {"score": {"name": "@s", "objective": "pvp.dwin"}, "color": "green"},
                                          {"text": " wins, ", "color": "gray"}, {"score": {"name": "@s", "objective": "pvp.dloss"}, "color": "red"},
                                          {"text": " losses", "color": "gray"}])])
    # building the pits (admin; force-load them first)
    g = arena_map.duel_pit()
    for n, (px, pz) in enumerate(DUEL_PITS, 1):
        E = arena_map.PIT_R + 3
        fn(f"admin/build_duel_{n}", [f"fill {px - E} {AY + 1} {pz - E} {px + E} {AY + 22} {pz + E} minecraft:air",
                                     f"fill {px - E} {AY - 1} {pz - E} {px + E} {AY} {pz + E} minecraft:sandstone"]
           + outbreak_maps.commands(g, px, AY, pz))
    fn("admin/build_duels", [f"function {NS}:admin/build_duel_{n}" for n in range(1, len(DUEL_PITS) + 1)])
    # lock (and empty) the containers of maps built before containers were locked, without rebuilding them
    lk = outbreak_maps.locks(arena_map.colosseum(SPAWNS), ACX, AY, ACZ, clear=True)
    for (px, pz) in DUEL_PITS: lk += outbreak_maps.locks(g, px, AY, pz, clear=True)
    for m in OUTBREAK_MAPS: lk += outbreak_maps.locks(outbreak_maps.MAPS[m[1]](map_points(m[1]), PVE_SPAWNS), PCX, AY, m[5], clear=True)
    for (i, key, *_), m in zip(ARENA_MAPS[1:], arena_maps.MAPS):
        lk += outbreak_maps.locks(m[5](), MAP_AT[i][0], AY, MAP_AT[i][1], clear=True)
    fn("admin/lock_containers", lk)


def build_rotation():
    """The arena map rotation: #amap pvp is the current map, #anext pvp the next, #arot pvp the seconds left on it."""
    N = len(ARENA_MAPS)
    name = lambda m: [{"text": m[2], "color": m[3], "bold": True}, {"text": f" ({m[4]})", "color": "gray"}]
    spawn, spec, sub = [], [], []
    for m in ARENA_MAPS:
        i, key = m[0], m[1]
        cx, cz = MAP_AT[i]
        pts = SPAWNS if i == 1 else next(b for b in arena_maps.MAPS if b[0] == i)[5]().spawns
        fn(f"arena/spawn_{key}", ["execute store result score #r pvp run random value 1..%d" % len(pts)] +
           [f"execute if score #r pvp matches {n} run tp @s {cx + dx + 0.5} {AY + 1} {cz + dz + 0.5} {yaw} 0" for n, (dx, dz, yaw) in enumerate(pts, 1)])
        if i == 1:
            spots = [(dx, dz, yaw, arena_map.WALL_H + (arena_map.row(dx, dz) - 1) + 1) for (dx, dz, yaw) in arena_map.SPECTATE]
        else:
            spots = [(dx, dz, yaw, arena_maps.WALL_H + 1) for (dx, dz, yaw) in arena_maps.SPECTATE]
        fn(f"arena/spec_{key}", ["execute store result score #r pvp run random value 1..%d" % len(spots)] +
           [f"execute if score #r pvp matches {n} run tp @s {cx + dx + 0.5} {AY + h} {cz + dz + 0.5} {yaw} 10" for n, (dx, dz, yaw, h) in enumerate(spots, 1)])
        spawn.append(f"execute if score #amap pvp matches {i} run return run function {NS}:arena/spawn_{key}")
        spec.append(f"execute if score #amap pvp matches {i} run return run function {NS}:arena/spec_{key}")
        sub.append(f"execute if score #amap pvp matches {i} run title @s subtitle " + tj([{"text": "🗺 "}] + name(m)))
    fn("arena/spawn", spawn)
    fn("arena/spec_tp", spec)
    fn("arena/subtitle", sub)
    fn("arena/moved", [f"function {NS}:arena/spawn", "effect give @s minecraft:resistance 3 4 true", f"function {NS}:arena/subtitle",
                       "title @s title {\"text\":\"NEW MAP\",\"color\":\"light_purple\",\"bold\":true}",
                       "playsound minecraft:entity.enderman.teleport player @s ~ ~ ~ 1 0.8"])
    fn("arena/rotate", [
        "scoreboard players operation #amap pvp = #anext pvp",
        "scoreboard players operation #anext pvp = #amap pvp", "scoreboard players add #anext pvp 1",
        f"execute if score #anext pvp matches {N + 1}.. run scoreboard players set #anext pvp 1",
        f"scoreboard players set #arot pvp {ROT_SECS}",
        f"execute as @a[tag=pvp.inarena,tag=!pvp.spec,gamemode=adventure] run function {NS}:arena/moved",
        f"execute as @a[tag=pvp.spec] run function {NS}:arena/spec_tp",
        *[f"execute if score #amap pvp matches {m[0]} run tellraw @a " + tj([{"text": "🗺 The arena is now ", "color": "light_purple"}] + name(m) +
                                                                           [{"text": "!", "color": "light_purple"}]) for m in ARENA_MAPS],
    ])
    warn = lambda secs: [f"execute if score #arot pvp matches {secs} if score #anext pvp matches {m[0]} run tellraw @a[tag=pvp.seemap] " +
                         tj([{"text": f"🗺 Next map in {secs}s: ", "color": "light_purple"}] + name(m)) for m in ARENA_MAPS]
    bar = []
    for m in ARENA_MAPS:
        for (cond, tail) in (("60..", [{"score": {"name": "#amin", "objective": "pvp"}, "color": "white"}, {"text": "m", "color": "white"}]),
                             ("..59", [{"score": {"name": "#arot", "objective": "pvp"}, "color": "white"}, {"text": "s", "color": "white"}])):
            bar.append(f"execute if score #amap pvp matches {m[0]} if score #arot pvp matches {cond} run bossbar set pvp:map name " +
                       tj([{"text": "🗺 ", "color": "white"}, {"text": m[2], "color": m[3], "bold": True}, {"text": "  ·  next map in ", "color": "gray"}] + tail))
    fn("arena/second", [
        "scoreboard players remove #arot pvp 1",
        *warn(60), *warn(10),
        f"execute if score #arot pvp matches ..0 run function {NS}:arena/rotate",
        "tag @a remove pvp.inarena", "tag @a remove pvp.instands", "tag @a remove pvp.seemap",
        *[f"tag @a[{b}] add pvp.inarena" for b in ARENA_BOXES.values()],
        *[f"tag @a[tag=pvp.spec,{b}] add pvp.instands" for b in STANDS_BOXES.values()],
        "tag @a[tag=pvp.inarena] add pvp.seemap", "tag @a[tag=pvp.instands] add pvp.seemap",
        "scoreboard players operation #amin pvp = #arot pvp", "scoreboard players add #amin pvp 59", "scoreboard players set #60 pvp 60",
        "scoreboard players operation #amin pvp /= #60 pvp",
        *bar,
        "execute store result bossbar pvp:map value run scoreboard players get #arot pvp",
        "bossbar set pvp:map players @a[tag=pvp.seemap]",
    ])
    fn("admin/next_map", ["scoreboard players set #arot pvp 1", say("@s", "The arena moves to the next map in a second.", "light_purple")])


def build_mastery():
    """Kit mastery: gain (#g pvp XP for the kit in pvp.cur), level-ups, the line shown on kit pick, and /trigger pvp.mastery."""
    roman = ["I", "II", "III", "IV", "V"]
    stars = lambda n: [{"text": "★" * n, "color": "gold"}, {"text": "☆" * (5 - n), "color": "dark_gray"}]
    fn("mastery/gain", ["execute unless score #g pvp matches 1.. run return 0"]
       + [f"execute if score @s pvp.cur matches {k[0]} run return run function {NS}:mastery/gain/{k[1]}" for k in ALL_KITS])
    shows, rows = [], []
    for (kid, key, name, color, *_rest) in ALL_KITS:
        o = f"pvp.mx{kid}"
        g = [f"scoreboard players add @s {o} 0", f"scoreboard players operation #x pvp = @s {o}",
             f"scoreboard players operation @s {o} += #g pvp", f"scoreboard players operation #y pvp = @s {o}"]
        for n, T in enumerate(MASTERY, 1):
            msg = [{"text": "MASTERY " + roman[n - 1], "color": "gold", "bold": True}]
            g += [f"execute if score #x pvp matches ..{T - 1} if score #y pvp matches {T}.. run title @s actionbar {tj(msg + [{'text': ' · ' + name, 'color': color}])}",
                  f"execute if score #x pvp matches ..{T - 1} if score #y pvp matches {T}.. run playsound minecraft:ui.toast.challenge_complete player @s ~ ~ ~ 0.8 1.2",
                  f"execute if score #x pvp matches ..{T - 1} if score #y pvp matches {T}.. run tellraw @s "
                  + tj([{"text": "Mastery up! ", "color": "gold"}, {"text": name, "color": color, "bold": True}, {"text": " is now ", "color": "gray"}]
                       + stars(n) + [{"text": f" {roman[n - 1]}" + (" (Master)" if n == 5 else ""), "color": "gold"}])]
        T = MASTERY[-1]
        g += [f"execute if score #x pvp matches ..{T - 1} if score #y pvp matches {T}.. run tag @s add pvp.master",
              f"execute if score #x pvp matches ..{T - 1} if score #y pvp matches {T}.. run scoreboard players add @s pvp.mastered 1",
              f"execute if score #x pvp matches ..{T - 1} if score #y pvp matches {T}.. run tellraw @a "
              + tj([{"text": "★ ", "color": "gold"}, {"selector": "@s", "color": "yellow"}, {"text": " has mastered ", "color": "gold"},
                    {"text": name, "color": color, "bold": True}, {"text": "!", "color": "gold"}])]
        fn(f"mastery/gain/{key}", g)
        # shown when the kit is given: level, stars and progress; masters get the aura tag
        sh = [f"scoreboard players add @s {o} 0", "tag @s remove pvp.master"]
        bounds = [0] + MASTERY
        for n in range(6):
            lo, hi = bounds[n], (MASTERY[n] - 1 if n < 5 else None)
            rng = f"{lo}..{hi}" if hi is not None else f"{lo}.."
            prog = ([{"score": {"name": "@s", "objective": o}, "color": "white"}, {"text": f"/{MASTERY[n]} XP", "color": "gray"}] if n < 5
                    else [{"text": "Master", "color": "gold", "bold": True}])
            sh.append(f"execute if score @s {o} matches {rng} run tellraw @s "
                      + tj([{"text": "Mastery: ", "color": "gray"}] + stars(n) + [{"text": f" {roman[n - 1] if n else '-'} · ", "color": "gray"}] + prog
                           + [{"text": "  [all]", "color": "aqua", "click_event": {"action": "run_command", "command": "/trigger pvp.mastery"},
                               "hover_event": {"action": "show_text", "value": "See your mastery for every character"}}]))
        sh.append(f"execute if score @s {o} matches {MASTERY[-1]}.. run tag @s add pvp.master")
        fn(f"mastery/show/{key}", sh)
        for n in range(6):
            lo, hi = bounds[n], (MASTERY[n] - 1 if n < 5 else None)
            rng = f"{max(lo, 1)}..{hi}" if hi is not None else f"{lo}.."
            rows.append(f"execute if score @s {o} matches {rng} run tellraw @s "
                        + tj([{"text": " " + name + " ", "color": color}] + stars(n)
                             + [{"text": " ", "color": "gray"}, {"score": {"name": "@s", "objective": o}, "color": "white"}, {"text": " XP", "color": "gray"}]))
    fn("mastery/list", ["scoreboard players set @s pvp.mastery 0",
                        f"tellraw @s {tj([{'text': '★ Kit mastery', 'color': 'gold', 'bold': True}, {'text': f' (+{MASTERY_PVP} XP per PvP kill, +{MASTERY_PVE} per Outbreak kill; Master at {MASTERY[-1]:,})', 'color': 'gray'}])}",
                        *rows,
                        f"execute unless score @s pvp.cur matches 1.. run tellraw @s {tj({'text': ' Play a character to start earning mastery.', 'color': 'gray'})}"])


def build_upgrades():
    """Pack-a-Punch (held weapon, tier on the item's custom_data) and Armor Upgrade (per player, pve.arm)."""
    P = f"{NS}:pve/up"
    roman = abilities.ROMAN
    N = len(WEAPON_UP)   # Pack-a-Punch tiers
    def em(enchants): return {"function": "minecraft:set_enchantments", "add": True,
                              "enchantments": {(k if ":" in k else "minecraft:" + k): v for k, v in enchants.items()}}
    # weapon: find the kind first (so nothing is charged for an item that can't be upgraded), then the tier
    # a gun ability in the hand upgrades the player's guns instead (see pve/up/gun)
    w = [*[f"execute if items entity @s weapon.mainhand {abilities.sel(k)} run return run function {P}/gun" for k in abilities.GUNS],
         "scoreboard players set #k pve 0"]
    for n, (kind, (match, *_)) in enumerate(UP_BOOST.items(), 1):
        w.append(f"execute if score #k pve matches 0 if items entity @s weapon.mainhand {match} run scoreboard players set #k pve {n}")
    w += [f"execute if score #k pve matches 0 run return run {say('@s', 'Hold a sword, axe, bow, crossbow, trident, mace or gun to Pack-a-Punch it.', 'red')}",
          "scoreboard players set #t pve 0",
          *[f"execute if items entity @s weapon.mainhand *[minecraft:custom_model_data={{strings:[\"pvp_tier{t}\"]}}] run scoreboard players set #t pve {t}" for t in range(1, N + 1)],
          f"execute if score #t pve matches {N}.. run return run {say('@s', f'That weapon is already fully upgraded (tier {roman[N - 1]}).', 'gold')}",
          *[f"execute if score #t pve matches {t} run return run function {P}/weapon_t{t + 1}" for t in range(N)]]
    fn("pve/up/weapon", w)
    for t in range(1, N + 1):
        cost = WEAPON_UP[t - 1]
        lines = [f"execute if score @s pve.pts matches ..{cost - 1} run return run {afford(f'Pack-a-Punch {roman[t - 1]}', cost)}",
                 f"scoreboard players remove @s pve.pts {cost}"]
        for n, (kind, (match, boost, extra3, extra4)) in enumerate(UP_BOOST.items(), 1):
            mods = [em(boost)] + ([em(extra3)] if t == 3 else []) + ([em(extra4)] if t == 4 else [])
            wj(f"data/{NS}/item_modifier/up/{kind}_t{t}.json", mods)
            lines.append(f"execute if score #k pve matches {n} run item modify entity @s weapon.mainhand {NS}:up/{kind}_t{t}")
        wj(f"data/{NS}/item_modifier/up/tier{t}.json", [
            # the tier marker: not custom_data, which crispy_enchants' migration wipes (that let tier I be bought again and again)
            {"function": "minecraft:set_components", "components": {"minecraft:custom_model_data": {"strings": [f"pvp_tier{t}"]}}},
            {"function": "minecraft:set_lore", "mode": "append",
             "lore": [{"text": f"{'★' * t} Pack-a-Punched: tier {roman[t - 1]}", "color": "gold", "italic": False}]}])
        lines += [f"item modify entity @s weapon.mainhand {NS}:up/tier{t}",
                  f"title @s actionbar {tj({'text': '★' * t + ' PACK-A-PUNCH ' + roman[t - 1], 'color': 'gold', 'bold': True})}",
                  "playsound minecraft:block.anvil.use player @s ~ ~ ~ 1 0.8", "playsound minecraft:block.beacon.power_select player @s ~ ~ ~ 1 1.4",
                  "particle minecraft:totem_of_undying ~ ~1 ~ 0.4 0.6 0.4 0.3 30",
                  say("@s", f"Weapon upgraded to tier {roman[t - 1]}." + (" Next: " + f"{WEAPON_UP[t]:,} points." if t < N else " Maxed out!"), "gold")]
        fn(f"pve/up/weapon_t{t}", lines)
    # guns: a gun item is swapped for a fresh one after every shot, so the tier is on the player (pve.gun) and covers
    # all their guns; it resets when they go down, like the armor upgrade
    pct = lambda t: f"+{round(abilities.GUN_TIER_BOOST[t] * 100)} % gun damage" + (", hits slow" if t >= 3 else "") + (", sets mobs on fire" if t >= 4 else "")
    fn("pve/up/gun", ["scoreboard players add @s pve.gun 0",
                      f"execute if score @s pve.gun matches {N}.. run return run {say('@s', f'Your guns are already fully upgraded (tier {roman[N - 1]}).', 'gold')}",
                      *[f"execute if score @s pve.gun matches {t - 1} run return run function {P}/gun_t{t}" for t in range(1, N + 1)]])
    # rewrite the lore of every gun the player carries, so it shows the new tier straight away
    fn("pve/up/gun_lore", [f"execute if items entity @s {sl} {abilities.sel(k)} run item modify entity @s {sl} {NS}:gunlore/{k}"
                           for sl in [f"container.{i}" for i in range(36)] + ["weapon.offhand"] for k in abilities.GUNS])
    for t in range(1, N + 1):
        cost = WEAPON_UP[t - 1]
        fn(f"pve/up/gun_t{t}", [
            f"execute if score @s pve.pts matches ..{cost - 1} run return run {afford(f'Pack-a-Punch {roman[t - 1]}', cost)}",
            f"scoreboard players remove @s pve.pts {cost}", f"scoreboard players set @s pve.gun {t}", f"function {P}/gun_lore",
            f"title @s actionbar {tj({'text': '★' * t + ' PACK-A-PUNCH ' + roman[t - 1] + ': ' + pct(t), 'color': 'gold', 'bold': True})}",
            "playsound minecraft:block.anvil.use player @s ~ ~ ~ 1 0.8", "playsound minecraft:block.beacon.power_select player @s ~ ~ ~ 1 1.4",
            "particle minecraft:totem_of_undying ~ ~1 ~ 0.4 0.6 0.4 0.3 30",
            say("@s", f"All your guns upgraded to tier {roman[t - 1]} ({pct(t)})." + (f" Next: {WEAPON_UP[t]:,} points." if t < N else " Maxed out!"), "gold")])
    # armor: I = +1 Protection on every worn piece, II = Resistance I, III = +2 hearts (all until you go down)
    wj(f"data/{NS}/item_modifier/up/armor.json", [em({"protection": 1}), em({"unbreaking": 1})])
    arm = {1: [*[f"item modify entity @s armor.{sl} {NS}:up/armor" for sl in ("head", "chest", "legs", "feet")]],
           2: ["effect give @s minecraft:resistance infinite 0 true"],
           3: ["attribute @s minecraft:max_health modifier add pvp:arm 4 add_value", "effect give @s minecraft:instant_health 1 0 true"]}
    desc = {1: "+1 Protection on all armor", 2: "Resistance I", 3: "+2 hearts"}
    a = ["scoreboard players add @s pve.arm 0",
         f"execute if score @s pve.arm matches 3.. run return run {say('@s', 'Your armor is fully upgraded (tier III).', 'aqua')}",
         *[f"execute if score @s pve.arm matches {t - 1} run return run function {P}/armor_t{t}" for t in (1, 2, 3)]]
    fn("pve/up/armor", a)
    for t in (1, 2, 3):
        cost = ARMOR_UP[t - 1]
        fn(f"pve/up/armor_t{t}", [
            f"execute if score @s pve.pts matches ..{cost - 1} run return run {afford(f'Armor Upgrade {roman[t - 1]}', cost)}",
            f"scoreboard players remove @s pve.pts {cost}", f"scoreboard players set @s pve.arm {t}", *arm[t],
            f"title @s actionbar {tj({'text': '◆ ARMOR ' + roman[t - 1] + ': ' + desc[t], 'color': 'aqua', 'bold': True})}",
            "playsound minecraft:item.armor.equip_netherite player @s ~ ~ ~ 1 1", "playsound minecraft:block.smithing_table.use player @s ~ ~ ~ 1 1",
            say("@s", f"Armor upgraded to tier {roman[t - 1]}: {desc[t]}." + (f" Next: {ARMOR_UP[t]:,} points ({desc[t + 1]})." if t < 3 else " Maxed out!"), "aqua")])


def smoke_puffs():
    """Smoke drifting across the outside of every window of the current map, while a run is on."""
    out = []
    for (i, key, _, _, _, cz, _) in OUTBREAK_MAPS:
        for (dx, dz) in map_points(key):
            if key in MAP_POINTS:
                a = math.atan2(dz, dx)
                out.append(f"execute if score #state pve matches 2..3 if score #map pve matches {i} run particle minecraft:large_smoke "
                           f"{PCX + 32.9 * math.cos(a) + 0.5:.1f} {AY + 2.5} {cz + 32.9 * math.sin(a) + 0.5:.1f} 0.4 0.6 0.4 0.01 12")
                continue
            if abs(dx) > abs(dz): x, z, d = PCX + (PR + 1) * (1 if dx > 0 else -1) + 0.5 + (0.8 if dx > 0 else -0.8), cz + dz + 0.5, "0.1 0.6 0.7"
            else: x, z, d = PCX + dx + 0.5, cz + (PR + 1) * (1 if dz > 0 else -1) + 0.5 + (0.8 if dz > 0 else -0.8), "0.7 0.6 0.1"
            out.append(f"execute if score #state pve matches 2..3 if score #map pve matches {i} run particle minecraft:large_smoke {x} {AY + 2.5} {z} {d} 0.01 12")
    return out


def build_pve():
    P = f"{NS}:pve"
    state_names = "0 idle, 1 lobby open (the leader starts), 2 wave running, 3 break between waves"
    fn("pve/tick", [
        f"# #state pve: {state_names}",
        "scoreboard players enable @a pve.join", "scoreboard players enable @a pve.buy",
        f"execute as @a[scores={{pve.join=1..}}] at @s run function {P}/join",
        f"execute as @a[scores={{pve.buy=1..}}] at @s run function {P}/buy",
        f"execute as @a[tag=pve.in,scores={{pve.k=1..}}] at @s run function {P}/points",
        *[f"execute as @a[tag=pve.in,tag=!pve.down] if items entity @s container.* *[minecraft:custom_data~{{pvp_pu:\"{k}\"}}] run function {P}/pu/{k}"
          for (k, _, _, _) in POWERUPS],
        f"execute if score #state pve matches 2 run function {P}/wave_tick",
        f"execute as @e[type=minecraft:armor_stand,tag=pve.body] at @s run function {P}/revive_tick",
        f"execute if score #state pve matches 3 run function {P}/break_tick",
    ])
    fn("pve/second", [
        f"execute if score #state pve matches 1 run function {P}/lobby_sec",
        "scoreboard players set @a[tag=!pve.in] pve.k 0",
        # sidebar: drop everyone (players who left or logged off included), then list who's in the run now
        "scoreboard players reset * pve.side", f"execute as @a[tag=pve.in] run function {P}/side",
        # downed markers whose player is gone (left, or already back) are removed
        "tag @e[type=minecraft:armor_stand,tag=pve.body] add pve.orphan", f"execute as @a[tag=pve.down] run function {P}/body_keep",
        "kill @e[type=minecraft:armor_stand,tag=pve.orphan]",
        f"execute if score #state pve matches 2..3 unless entity @a[tag=pve.in,tag=!pve.down] run function {P}/game_over",
        # downed spectators stay above the arena
        *[f"execute if score #map pve matches {i} as @a[tag=pve.down] unless entity @s[{b}] run tp @s {PCX + 0.5} {AY + downed_y(key)} {z + 0.5}"
          for (i, key, _, _, _, z, _), b in zip(OUTBREAK_MAPS, PVE_BOXES.values())],
        # items players throw stay (they despawn normally after 5 minutes); anything else (mob leftovers) is cleared
        *[f"execute as @e[type=minecraft:item,{b},tag=!pve.pu] unless data entity @s Thrower run kill @s" for b in PVE_BOXES.values()],
        *[f"kill @e[type=minecraft:experience_orb,{b}]" for b in PVE_BOXES.values()],
        # mobs that leave the map (Ghosts are vexes and fly through blocks, under the floor or into the next map) are
        # put back at a mob window, so a wave can't stall on a mob nobody can reach
        *[f"execute if score #map pve matches {i} as @e[tag=pve.mob] unless entity @s[{b}] run tp @s {PCX + map_points(key)[0][0] + 0.5} {AY + 1} {z + map_points(key)[0][1] + 0.5}"
          for (i, key, _, _, _, z, _), b in zip(OUTBREAK_MAPS, PVE_BOXES.values())],
        # spiders that climb the walls get pulled back down
        *[f"execute as @e[tag=pve.mob,x={PCX - PR - 1},y={AY + 8},z={z - PR - 1},dx={2 * PR + 2},dy=30,dz={2 * PR + 2}] at @s run tp @s {PCX + 0.5} {AY + 1} {z + 0.5}"
          for (_, _, _, _, _, z, _) in OUTBREAK_MAPS],
        *smoke_puffs(),
        # mobs only belong to a running wave; this also catches ones that come back when a chunk reloads
        "execute unless score #state pve matches 2 run kill @e[tag=pve.mob]",
        "execute if score #dp pve matches 1.. run scoreboard players remove #dp pve 1",
        "execute if score #dp pve matches 1 run tellraw @a[tag=pve.in] {\"text\":\"Double Points has worn off.\",\"color\":\"yellow\"}",
        "execute store result bossbar pvp:boss value run data get entity @n[tag=pve.boss] Health",
        f"execute if score #state pve matches 2 if score #map pve matches {HW_MAP} run function {NS}:hw/second",
        "execute unless entity @e[tag=pve.boss] run bossbar set pvp:boss visible false",
    ])

    # the lobby, like the UNO tables: the first player picks a map and a kit and leads the lobby, others join it from
    # the Outbreak NPC (or the chat invite) and pick a kit, and the leader starts the run. During a run, players can
    # still drop in (they join at the next wave break).
    # pve.join: kit id (or RANDOM_KIT / custom / test kit) = join with that kit, 81..85 / 91 = pick a map (91 random),
    # 92 = open the kit menu to join the lobby, 93 = start (leader), 99 = leave
    start_btn = {"text": "[▶ Start]", "color": "green", "bold": True, "click_event": {"action": "run_command", "command": "/trigger pve.join set 93"},
                 "hover_event": {"action": "show_text", "value": "Start the Outbreak now"}}
    join_btn = {"text": "[Click to join]", "color": "green", "bold": True, "click_event": {"action": "run_command", "command": "/trigger pve.join set 92"},
                "hover_event": {"action": "show_text", "value": "Join the Outbreak lobby and pick your kit"}}
    names = {m[0]: (m[2], m[3]) for m in OUTBREAK_MAPS}
    set_mapname = [f"execute if score #map pve matches {i} run data modify storage pvp:pve mapname set value {tj({'text': n, 'color': c, 'bold': True})}"
                   for i, (n, c) in names.items()]
    fn("pve/open_menu", [   # the Outbreak NPC: the menu that fits
        f"execute unless entity @s[{LOBBY_BOX}] run return 0",
        "execute store result score #pqn pve if entity @a[tag=pve.q]",
        "execute if score #state pve matches 2.. run return run pvpmenu pve_running",
        "execute if entity @s[tag=pve.lead] run return run pvpmenu pve_lead",
        "execute if entity @s[tag=pve.q] run return run pvpmenu pve_member",
        "execute if score #state pve matches 1 run return run pvpmenu pve_join",
        "pvpmenu pve_maps",
    ])
    fn("pve/join", [
        "scoreboard players operation #j pve = @s pve.join", "scoreboard players set @s pve.join 0",
        f"execute if score #j pve matches 81..{80 + len(OUTBREAK_MAPS)} run return run function {P}/pick_map",
        f"execute if score #j pve matches 91 run return run function {P}/pick_map",
        f"execute if score #j pve matches 92 unless entity @s[{LOBBY_BOX}] run return run {say('@s', 'Join the Outbreak from the lobby (/spawn).', 'red')}",
        f"execute if score #j pve matches 92 run return run function {P}/kit_menu",
        f"execute if score #j pve matches 93 run return run function {P}/start_lobby",
        f"execute if score #j pve matches 99 run return run function {P}/leave_lobby",
        # #jm pve: the map this kit is for (the open lobby's or run's, else the player's pick)
        "scoreboard players operation #jm pve = @s pve.map", "execute if score #state pve matches 1.. run scoreboard players operation #jm pve = #map pve",
        f"execute if score #j pve matches {RANDOM_KIT} if score #jm pve matches {HW_MAP} run function {NS}:kit/roll_hw",
        f"execute if score #j pve matches {RANDOM_KIT} unless score #jm pve matches {HW_MAP} run function {NS}:kit/roll",
        f"execute if score #j pve matches {RANDOM_KIT} run scoreboard players operation #j pve = #rk pvp",
        f"execute if entity @s[tag=pve.in] run return run {say('@s', 'You are already in the Outbreak.', 'red')}",
        f"execute unless entity @s[{LOBBY_BOX}] run return run {say('@s', 'Join the Outbreak from the lobby (/spawn).', 'red')}",
        f"execute if score #j pve matches {TEST_KIT_ID} unless entity @s[tag=pvp.tester] run return 0",
        f"execute if score #jm pve matches {HW_MAP} unless function {NS}:kit/valid_pve run return run {say('@s', 'Haunted Night is played as one of its horror characters.', 'gold')}",
        f"execute unless score #j pve matches 101..199 unless score #j pve matches {TEST_KIT_ID} unless function {NS}:kit/valid_pve run return 0",
        # already in the lobby: just a new kit
        f"execute if entity @s[tag=pve.q] if score #state pve matches 1 run scoreboard players operation @s pve.kit = #j pve",
        f"execute if entity @s[tag=pve.q] if score #state pve matches 1 run return run {say('@s', 'Kit changed.', 'green')}",
        "scoreboard players operation @s pve.kit = #j pve", "tag @s remove tw.q", "tag @s remove tw.lead", "tag @s add pve.q",
        f"execute unless score @s pve.map matches 1..{len(OUTBREAK_MAPS)} run scoreboard players operation @s pve.map = #map pve",
        f"execute unless score @s pve.map matches 1..{len(OUTBREAK_MAPS)} run scoreboard players set @s pve.map 1",
        f"execute if score @s pve.map matches {HW_MAP} unless function {NS}:hw/active run scoreboard players set @s pve.map 1",
        f"execute if score #state pve matches 0 run return run function {P}/create",
        f"execute if score #state pve matches 2..3 run return run {say('@s', 'Outbreak in progress: you will drop in at the next wave break.', 'green')}",
        # joining the open lobby
        "execute store result score #pqn pve if entity @a[tag=pve.q]",
        "tellraw @a[tag=pve.q] " + tj([{"text": "☣ ", "color": "green"}, {"selector": "@s", "color": "yellow"},
                                      {"text": " joined the Outbreak lobby (", "color": "green"}, {"score": {"name": "#pqn", "objective": "pve"}, "color": "white"},
                                      {"text": " players).", "color": "green"}]),
        "tellraw @s " + tj([{"text": "Map: ", "color": "gray"}, {"nbt": "mapname", "storage": "pvp:pve", "interpret": True},
                            {"text": ". The leader starts the run; you can change your kit from the Outbreak NPC.", "color": "gray"}]),
        "tellraw @a[tag=pve.lead] " + tj([{"text": "Start when everyone's in: ", "color": "gray"}, start_btn]),
        "playsound minecraft:block.note_block.pling player @a[tag=pve.q] ~ ~ ~ 1 0.8",
    ])
    fn("pve/create", [   # the first player opens the lobby with their map
        "tag @s add pve.lead", "scoreboard players set #state pve 1", "scoreboard players set #plob pve 0",
        "scoreboard players operation #map pve = @s pve.map", *set_mapname,
        f"tellraw @a[{LOBBY_BOX},tag=!pve.q] " + tj([
            {"text": "☣ ", "color": "green"}, {"selector": "@s", "color": "yellow"}, {"text": " opened an Outbreak lobby on ", "color": "green"},
            {"nbt": "mapname", "storage": "pvp:pve", "interpret": True}, {"text": "! ", "color": "green"}, join_btn,
            {"text": " (or use the Outbreak NPC)", "color": "gray"}]),
        "tellraw @s " + tj([{"text": "☣ You lead the Outbreak lobby. Others can join now. ", "color": "green"}, start_btn,
                            {"text": " (or start from the Outbreak NPC)", "color": "gray"}]),
        "playsound minecraft:block.note_block.pling player @s ~ ~ ~ 1 0.8",
    ])
    fn("pve/leave_lobby", [
        "execute unless entity @s[tag=pve.q] run return run " + say("@s", "You are not in the Outbreak lobby.", "gray"),
        "tag @s remove pve.q", say("@s", "You left the Outbreak lobby.", "yellow"),
        "execute if score #state pve matches 1 run tellraw @a[tag=pve.q] " + tj([{"selector": "@s", "color": "yellow"}, {"text": " left the Outbreak lobby.", "color": "gray"}]),
        f"execute if entity @s[tag=pve.lead] run function {P}/lose_leader",
    ])
    fn("pve/lose_leader", [
        "tag @a remove pve.lead",
        f"execute unless entity @a[tag=pve.q] run return run function {P}/close",
        "tag @a[tag=pve.q,limit=1,sort=arbitrary] add pve.lead",
        "tellraw @a[tag=pve.q] " + tj([{"selector": "@a[tag=pve.lead]", "color": "yellow"}, {"text": " now leads the Outbreak lobby.", "color": "green"}]),
        "tellraw @a[tag=pve.lead] " + tj([{"text": "You lead the lobby now. ", "color": "green"}, start_btn]),
    ])
    fn("pve/close", [
        "scoreboard players set #state pve 0", "tag @a remove pve.q", "tag @a remove pve.lead",
        f"tellraw @a[{LOBBY_BOX}] " + tj({"text": "☣ The Outbreak lobby closed.", "color": "gray"}),
    ])
    fn("pve/start_lobby", [
        f"execute unless entity @s[tag=pve.lead] run return run {say('@s', 'Only the lobby leader can start the Outbreak.', 'red')}",
        "execute unless score #state pve matches 1 run return 0",
        "tag @a remove pve.lead", f"function {P}/start",
    ])
    fn("pve/lobby_sec", [   # the open lobby: keep only players still in the lobby area, keep a leader, close it if left idle
        f"execute as @a[tag=pve.q] unless entity @s[{LOBBY_BOX}] run tag @s remove pve.lead",
        f"execute as @a[tag=pve.q] unless entity @s[{LOBBY_BOX}] run tag @s remove pve.q",
        f"execute unless entity @a[tag=pve.q] run return run function {P}/close",
        f"execute unless entity @a[tag=pve.lead,tag=pve.q] run function {P}/lose_leader",
        "scoreboard players add #plob pve 1",
        f"execute if score #plob pve matches {PVE_LOBBY_IDLE - 60} run tellraw @a[tag=pve.lead] " + tj([
            {"text": "☣ The Outbreak lobby closes in 1 minute unless you start. ", "color": "yellow"}, start_btn]),
        f"execute if score #plob pve matches {PVE_LOBBY_IDLE}.. run return run function {P}/close",
        "execute store result score #pqn pve if entity @a[tag=pve.q]",
        "title @a[tag=pve.q,tag=!pve.lead] actionbar " + tj([{"text": "☣ ", "color": "green"}, {"nbt": "mapname", "storage": "pvp:pve", "interpret": True},
            {"text": " lobby · ", "color": "green"}, {"score": {"name": "#pqn", "objective": "pve"}, "color": "white"},
            {"text": " players · waiting for ", "color": "green"}, {"selector": "@a[tag=pve.lead]", "color": "yellow"}, {"text": " to start", "color": "green"}]),
        "title @a[tag=pve.lead] actionbar " + tj([{"text": "☣ ", "color": "green"}, {"nbt": "mapname", "storage": "pvp:pve", "interpret": True},
            {"text": " lobby · ", "color": "green"}, {"score": {"name": "#pqn", "objective": "pve"}, "color": "white"},
            {"text": " players · start from the Outbreak NPC or the chat button", "color": "green"}]),
    ])
    fn("pve/pick_map", [   # as the clicking player: remember their map (the leader's sets the lobby's), then show the kit menu
        f"execute unless entity @s[{LOBBY_BOX}] run return run {say('@s', 'Join the Outbreak from the lobby (/spawn).', 'red')}",
        "execute if score #j pve matches 81.. run scoreboard players operation @s pve.map = #j pve",
        "execute if score #j pve matches 81.. run scoreboard players remove @s pve.map 80",
        f"execute if score #j pve matches 91 store result score @s pve.map run random value 1..{len(NORMAL_MAPS)}",
        f"execute if score #j pve matches {80 + HW_MAP} unless function {NS}:hw/active run return run {say('@s', 'Haunted Night is over for this year.', 'gold')}",
        f"execute if entity @s[tag=pve.lead] if score #state pve matches 1 run return run function {P}/lead_map",
        "execute if score #state pve matches 1 run tellraw @s " + tj([{"text": "This lobby is on ", "color": "gray"}, {"nbt": "mapname", "storage": "pvp:pve", "interpret": True},
                                                                     {"text": " (the leader picks the map). Pick your kit.", "color": "gray"}]),
        f"execute if score #state pve matches 1 run return run function {P}/kit_menu",
        *[f"execute if score @s pve.map matches {i} run tellraw @s [{{\"text\":\"Map: \",\"color\":\"gray\"}},{{\"text\":\"{n}\",\"color\":\"{c}\",\"bold\":true}},"
          f"{{\"text\":\". Now pick your kit.\",\"color\":\"gray\"}}]" for i, (n, c) in names.items()],
        "playsound minecraft:ui.button.click player @s ~ ~ ~ 1 1",
        f"function {P}/kit_menu",
    ])
    fn("pve/kit_menu", [   # as the player: Haunted Night has its own (horror) characters
        f"execute if score #state pve matches 1.. if score #map pve matches {HW_MAP} run return run pvpmenu pve_hw",
        f"execute unless score #state pve matches 1.. if score @s pve.map matches {HW_MAP} run return run pvpmenu pve_hw",
        "pvpmenu pve"])
    fn("pve/lead_map", [   # the leader changes the lobby's map
        "scoreboard players operation #map pve = @s pve.map", *set_mapname,
        "tellraw @a[tag=pve.q] " + tj([{"text": "☣ The lobby's map is now ", "color": "green"}, {"nbt": "mapname", "storage": "pvp:pve", "interpret": True},
                                      {"text": ".", "color": "green"}]),
        "playsound minecraft:ui.button.click player @s ~ ~ ~ 1 1",
    ])
    fn("pve/start", [
        "tag @a remove pve.lead",
        f"execute unless score #map pve matches 1..{len(OUTBREAK_MAPS)} run scoreboard players set #map pve 1",
        *[f"execute if score #map pve matches {i} run data modify storage pvp:pve map set value {{bz:{z + 18.5}d}}"
          for (i, _, _, _, _, z, _) in OUTBREAK_MAPS],
        "scoreboard players set #wave pve 0", "kill @e[tag=pve.mob]", "kill @e[type=minecraft:item,tag=pve.pu]",
        # keep the map loaded for the run, so mobs can always be cleared when it ends
        *[f"execute if score #map pve matches {i} run forceload add {PCX - PR - 1} {z - PR - 1} {PCX + PR + 1} {z + PR + 1}"
          for (i, _, _, _, _, z, _) in OUTBREAK_MAPS],
        "scoreboard players set #dp pve 0", "scoreboard players set #insta pve 0",
        "scoreboard players set #state pve 3", "scoreboard players set #timer pve 100",
        f"execute as @a[tag=pve.q] run function {P}/enter",
        "tellraw @a[tag=pve.in] {\"text\":\"☣ The Outbreak has begun. Survive as long as you can.\",\"color\":\"green\"}",
    ])
    pts_spawn = ["execute store result score #r pve run random value 1..%d" % len(PVE_SPAWNS)]
    for (i, _, _, _, _, mz, _) in OUTBREAK_MAPS:
        for n, (dx, dz, yaw) in enumerate(PVE_SPAWNS, 1):
            pts_spawn.append(f"execute if score #map pve matches {i} if score #r pve matches {n} run tp @s {PCX + dx + 0.5} {AY + 1} {mz + dz + 0.5} {yaw} 0")
    fn("pve/tp_spawn", pts_spawn)
    fn("pve/enter", [   # as a queued player: into the run with their kit and 500 points
        "tag @s remove pve.q", "tag @s add pve.in", "team join pve @s",
        "scoreboard players set @s pve.pts 500", "scoreboard players set @s pve.k 0", "scoreboard players set @s pve.kc 0", *PERK_RESET,
        # veteran bonus: +VETERAN_PER_WAVE starting points per best wave, up to VETERAN_MAX
        "scoreboard players add @s pve.best 0", "scoreboard players operation #vb pve = @s pve.best", "scoreboard players operation #vb pve *= #vet pve",
        f"execute if score #vb pve matches {VETERAN_MAX + 1}.. run scoreboard players set #vb pve {VETERAN_MAX}",
        "scoreboard players operation @s pve.pts += #vb pve",
        "execute if score #vb pve matches 1.. run tellraw @s [{\"text\":\"Veteran bonus: +\",\"color\":\"gold\"},{\"score\":{\"name\":\"#vb\",\"objective\":\"pve\"},\"color\":\"white\"},{\"text\":\" starting points (best wave \",\"color\":\"gold\"},{\"score\":{\"name\":\"@s\",\"objective\":\"pve.best\"},\"color\":\"white\"},{\"text\":\").\",\"color\":\"gold\"}]",
        "clear @s", "effect clear @s", "function cyber:admin/reset", "gamemode adventure @s",
        f"execute if score #map pve matches {HW_MAP} unless score @s pve.kit matches {min(HW_IDS)}..{max(HW_IDS)} run function {NS}:hw/fix_kit",
        f"execute unless score #map pve matches {HW_MAP} if score @s pve.kit matches {min(HW_IDS)}..{max(HW_IDS)} run function {NS}:hw/unfix_kit",
        f"function {NS}:kit/give_pve", f"function {P}/tp_spawn",
        f"execute if score #map pve matches {HW_MAP} run return run function {NS}:hw/enter_title",
        "title @s title {\"text\":\"☣ OUTBREAK\",\"color\":\"dark_green\",\"bold\":true}",
        "playsound minecraft:entity.zombie_villager.converted player @s ~ ~ ~ 1 0.7",
    ])
    fn("pve/break_tick", [
        "scoreboard players remove #timer pve 1",
        "scoreboard players operation #s pve = #timer pve", "scoreboard players operation #s pve /= #20 pve",
        "title @a[tag=pve.in] actionbar [{\"text\":\"Next wave in \",\"color\":\"gray\"},{\"score\":{\"name\":\"#s\",\"objective\":\"pve\"},\"color\":\"white\"},"
        "{\"text\":\"s · re-buy at the Arsenal\",\"color\":\"gray\"}]",
        f"execute if score #timer pve matches ..0 run function {P}/next_wave"])
    fn("pve/next_wave", [
        "scoreboard players add #wave pve 1",
        "execute store result score #np pve if entity @a[tag=pve.in]",
        # mobs this wave: 6 + 4(w-1), plus (3 + 2(w-1)) per extra player, capped at 150
        "scoreboard players operation #w1 pve = #wave pve", "scoreboard players remove #w1 pve 1",
        "scoreboard players operation #tospawn pve = #w1 pve", "scoreboard players operation #tospawn pve *= #4c pve",
        "scoreboard players add #tospawn pve 6",
        "scoreboard players operation #x pve = #w1 pve", "scoreboard players operation #x pve *= #2c pve", "scoreboard players add #x pve 3",
        "scoreboard players operation #np1 pve = #np pve", "scoreboard players remove #np1 pve 1",
        "scoreboard players operation #x pve *= #np1 pve", "scoreboard players operation #tospawn pve += #x pve",
        "execute if score #tospawn pve matches 151.. run scoreboard players set #tospawn pve 150",
        # health +15% and damage +8% per wave
        "execute store result storage pvp:pve s.hm double 0.15 run scoreboard players get #w1 pve",
        "execute store result storage pvp:pve s.dm double 0.08 run scoreboard players get #w1 pve",
        "scoreboard players set #state pve 2", "scoreboard players set #st pve 0", "scoreboard players set #wt pve 0",
        "title @a[tag=pve.in] title [{\"text\":\"Wave \",\"color\":\"red\"},{\"score\":{\"name\":\"#wave\",\"objective\":\"pve\"},\"color\":\"dark_red\",\"bold\":true}]",
        "execute as @a[tag=pve.in] at @s run playsound minecraft:event.raid.horn player @s ~ ~ ~ 0.6 1.2",
        "scoreboard players operation #m pve = #wave pve", "scoreboard players operation #m pve %= #5 pve",
        f"execute if score #m pve matches 0 run function {P}/boss",
    ])
    fn("pve/wave_tick", [
        "scoreboard players add #st pve 1", "scoreboard players add #wt pve 1",
        "execute if score #st pve matches 8.. store result score #alive pve if entity @e[tag=pve.mob]",
        f"execute if score #st pve matches 8.. if score #tospawn pve matches 1.. if score #alive pve matches ..29 run function {P}/spawn_mob",
        "execute if score #st pve matches 8.. run scoreboard players set #st pve 0",
        # last few (or a wave over 3 minutes) glow so they can be found
        "execute if score #tospawn pve matches 0 if score #alive pve matches ..4 run effect give @e[tag=pve.mob] minecraft:glowing 2 0 true",
        "execute if score #wt pve matches 3600.. run effect give @e[tag=pve.mob] minecraft:glowing 2 0 true",
        f"execute if score #tospawn pve matches 0 unless entity @e[tag=pve.mob] run function {P}/wave_end",
    ])
    fn("pve/wave_end", [
        "scoreboard players set #state pve 3", f"scoreboard players set #timer pve {BREAK_TICKS}",
        f"execute as @a[tag=pve.down] run function {P}/revive",   # back now, so they can re-buy during the break
        "kill @e[type=minecraft:armor_stand,tag=pve.body]",
        f"execute if score #map pve matches {HW_MAP} if score #wave pve matches {HW_WAVES}.. run return run function {NS}:hw/victory",
        "scoreboard players operation #m pve = #wave pve", "scoreboard players operation #m pve %= #5 pve",
        f"execute if score #m pve matches 0 run give @a[tag=pve.in,tag=!pve.down] {CELL}",
        "execute if score #m pve matches 0 run tellraw @a[tag=pve.in] [{\"text\":\"☣ Boss down! Everyone standing gets a \",\"color\":\"light_purple\"},"
        f"{{\"text\":\"Power Cell\",\"color\":\"light_purple\",\"bold\":true}},{{\"text\":\" ({CELLS_NEEDED} assemble the Annihilator at the Arsenal).\",\"color\":\"gray\"}}]",
        "scoreboard players operation #b pve = #wave pve", "scoreboard players operation #b pve *= #100 pve",
        "scoreboard players operation @a[tag=pve.in,tag=!pve.down] pve.pts += #b pve",
        "tellraw @a[tag=pve.in] [{\"text\":\"☣ Wave \",\"color\":\"green\"},{\"score\":{\"name\":\"#wave\",\"objective\":\"pve\"},\"color\":\"white\"},"
        "{\"text\":\" cleared! +\",\"color\":\"green\"},{\"score\":{\"name\":\"#b\",\"objective\":\"pve\"},\"color\":\"gold\"},{\"text\":\" points. Next wave in " + str(BREAK_TICKS // 20) + " s.\",\"color\":\"green\"}]",
        "execute as @a[tag=pve.in] at @s run playsound minecraft:ui.toast.challenge_complete player @s ~ ~ ~ 0.6 1",
        f"give @a[tag=pve.in,tag=!pve.down] minecraft:cooked_beef {WAVE_FOOD}",
        f"execute as @a[tag=pve.q] run function {P}/enter",
    ])

    # mob spawning: pick a type for this wave, a window, then summon + scale
    choose = ["execute store result score #r pve run random value 1..100", "scoreboard players set #p pve 0"]
    pool = [  # (min wave, roll <=, type, extra NBT)
        (7, 10, "wither_skeleton", ',equipment:{mainhand:{id:"minecraft:stone_sword",count:1}},drop_chances:{mainhand:0.0f}'),
        (6, 22, "vindicator", ',equipment:{mainhand:{id:"minecraft:iron_axe",count:1}},drop_chances:{mainhand:0.0f}'),
        (8, 30, "creeper", ""),
        (4, 45, "spider", ""),
        (3, 60, "skeleton", ',equipment:{mainhand:{id:"minecraft:bow",count:1}},drop_chances:{mainhand:0.0f}'),
        (2, 75, "husk", ""),
    ]
    for (i, _, _, _, _, _, extra_pool) in OUTBREAK_MAPS:   # this map's own mobs get the first roll
        if extra_pool:
            choose.append(f"execute if score #map pve matches {i} store result score #r2 pve run random value 1..100")
        for (mw, roll, typ, extra) in extra_pool:
            choose.append(f"execute if score #map pve matches {i} if score #p pve matches 0 if score #wave pve matches {mw}.. if score #r2 pve matches ..{roll} run "
                          f"function {P}/type {{type:\"{typ}\",extra:'{extra}'}}")
    for (mw, roll, typ, extra) in pool:
        choose.append(f"execute if score #p pve matches 0 if score #wave pve matches {mw}.. if score #r pve matches ..{roll} run "
                      f"function {P}/type {{type:\"{typ}\",extra:'{extra}'}}")
    choose.append(f"execute if score #p pve matches 0 run function {P}/type {{type:\"zombie\",extra:''}}")
    choose.append("execute store result score #r pve run random value 1..%d" % len(MOB_POINTS))
    for (i, key, _, _, _, mz, _) in OUTBREAK_MAPS:
        assert len(map_points(key)) == len(MOB_POINTS)
        for n, (dx, dz) in enumerate(map_points(key), 1):
            choose.append(f"execute if score #map pve matches {i} if score #r pve matches {n} run data modify storage pvp:pve m merge value {{x:{PCX + dx + 0.5},y:{AY + 1},z:{mz + dz + 0.5}}}")
    choose += [f"function {P}/summon with storage pvp:pve m", "scoreboard players remove #tospawn pve 1"]
    fn("pve/spawn_mob", choose)
    fn("pve/type", ["scoreboard players set #p pve 1", "$data modify storage pvp:pve m merge value {type:\"$(type)\",extra:'$(extra)'}"])
    fn("pve/summon", [
        "$summon minecraft:$(type) $(x) $(y) $(z) {Tags:[\"pve.mob\",\"pve.new\"],PersistenceRequired:1b,CanPickUpLoot:0b,"
        "DeathLootTable:\"minecraft:empty\",attributes:[{id:\"minecraft:follow_range\",base:64d}]$(extra)}",
        f"execute as @e[tag=pve.new] run function {P}/scale with storage pvp:pve s",
        "$particle minecraft:large_smoke $(x) $(y) $(z) 0.3 0.5 0.3 0.02 20",
    ])
    fn("pve/scale", [
        "tag @s remove pve.new",
        "$attribute @s minecraft:max_health modifier add pvp:wave $(hm) add_multiplied_base",
        "$attribute @s minecraft:attack_damage modifier add pvp:wave $(dm) add_multiplied_base",
        "execute store result entity @s Health float 1 run attribute @s minecraft:max_health get",
    ])
    fn("pve/boss", [
        f"execute if score #map pve matches {HW_MAP} run return run function {NS}:hw/boss",
        'bossbar set pvp:boss name {"text":"Abomination","color":"dark_red"}', "bossbar set pvp:boss color red",
        f"function {P}/boss_summon with storage pvp:pve map",
        f"execute as @e[tag=pve.new] run function {P}/scale with storage pvp:pve s",
        "execute store result bossbar pvp:boss max run data get entity @n[tag=pve.boss] Health",
        "bossbar set pvp:boss players @a[tag=pve.in]", "bossbar set pvp:boss visible true",
        "tellraw @a[tag=pve.in] {\"text\":\"☣ An Abomination has entered the arena!\",\"color\":\"dark_red\",\"bold\":true}",
        "execute as @a[tag=pve.in] at @s run playsound minecraft:entity.wither.spawn player @s ~ ~ ~ 0.5 0.8",
    ])
    fn("pve/boss_summon", [
        f"$summon minecraft:zombie {PCX + 0.5} {AY + 1} $(bz) {{Tags:[\"pve.mob\",\"pve.boss\",\"pve.new\"],PersistenceRequired:1b,CanPickUpLoot:0b,"
        "DeathLootTable:\"minecraft:empty\",IsBaby:0b,CustomName:{\"text\":\"Abomination\",\"color\":\"dark_red\",\"bold\":true},CustomNameVisible:1b,"
        "attributes:[{id:\"minecraft:follow_range\",base:64d},{id:\"minecraft:scale\",base:2.0d},{id:\"minecraft:max_health\",base:150d},"
        "{id:\"minecraft:attack_damage\",base:9d},{id:\"minecraft:knockback_resistance\",base:0.8d},{id:\"minecraft:movement_speed\",base:0.26d}]}",
    ])
    fn("pve/side", ["scoreboard players operation @s pve.side = @s pve.pts",
                    "execute store result storage pvp:side p int 1 run scoreboard players get @s pve.pts",
                    "scoreboard players add @s pve.kc 0", "execute store result storage pvp:side k int 1 run scoreboard players get @s pve.kc",
                    f"function {P}/side_fmt with storage pvp:side"])
    fn("pve/side_fmt", ['$scoreboard players display numberformat @s pve.side fixed [{"text":"$(p)","color":"gold"},{"text":" pts · ","color":"gray"},'
                        '{"text":"$(k)","color":"red"},{"text":" kills","color":"gray"}]'])
    fn("pve/points", ["scoreboard players operation #g pvp = @s pve.k", f"scoreboard players operation #g pvp *= #{MASTERY_PVE} pvp" if MASTERY_PVE != 1 else None,
                      f"function {NS}:mastery/gain",
                      "scoreboard players operation #k pve = @s pve.k", "scoreboard players operation #k pve *= #100 pve",
                      "execute if score #dp pve matches 1.. run scoreboard players operation #k pve *= #2c pve",
                      "scoreboard players operation @s pve.pts += #k pve", "scoreboard players operation @s pve.kc += @s pve.k", "scoreboard players set @s pve.k 0",
                      "execute store result score #r pve run random value 1..100",
                      f"execute if score #r pve matches ..{POWERUP_CHANCE} run function {P}/pu/drop"])
    # power-ups: dropped a few blocks in front of the killer, glowing, gone after 30 s; picked up by any survivor
    drop = ["execute store result score #r pve run random value 1..%d" % len(POWERUPS)]
    for n, (k, it, name, col) in enumerate(POWERUPS, 1):
        drop.append(f"execute if score #r pve matches {n} positioned ^ ^1 ^2 run summon minecraft:item ~ ~ ~ {{Tags:[\"pve.pu\"],Glowing:1b,Age:5400s,PickupDelay:10s,"
                    f"CustomNameVisible:1b,CustomName:{tj({'text': name, 'color': col, 'bold': True})},Item:{{id:\"minecraft:{it}\",count:1,"
                    f"components:{{\"minecraft:custom_data\":{{pvp_pu:\"{k}\"}},\"minecraft:custom_name\":{tj({'text': name, 'color': col, 'bold': True})}}}}}}}")
    fn("pve/pu/drop", drop + ["playsound minecraft:block.amethyst_block.chime player @a[tag=pve.in] ~ ~ ~ 1 1.5"])
    effects = {
        "ammo": ["give @a[tag=pve.in,tag=!pve.down] minecraft:arrow 64"],
        "insta": [f"effect give @a[tag=pve.in,tag=!pve.down] minecraft:strength {POWERUP_SECS} 19 true"],
        "double": [f"scoreboard players set #dp pve {POWERUP_SECS + 1}"],
        "nuke": ["kill @e[tag=pve.mob,tag=!pve.boss]", "scoreboard players add @a[tag=pve.in,tag=!pve.down] pve.pts 400",
                 "execute as @a[tag=pve.in] at @s run playsound minecraft:entity.generic.explode player @s ~ ~ ~ 1 0.6",
                 "execute as @a[tag=pve.in] at @s run particle minecraft:explosion_emitter ~ ~2 ~ 3 1 3 0 3"],
    }
    subs = {"ammo": "Arrows for everyone", "insta": f"{POWERUP_SECS} s of one-hit kills", "double": f"{POWERUP_SECS} s of double points",
            "nuke": "Every mob wiped out · +400 points"}
    for (k, it, name, col) in POWERUPS:
        fn(f"pve/pu/{k}", [f"clear @s *[minecraft:custom_data~{{pvp_pu:\"{k}\"}}]", *effects[k],
                           f"title @a[tag=pve.in] title {tj({'text': name, 'color': col, 'bold': True})}",
                           f"title @a[tag=pve.in] subtitle {tj({'text': subs[k], 'color': 'gray'})}",
                           "execute as @a[tag=pve.in] at @s run playsound minecraft:entity.player.levelup player @s ~ ~ ~ 1 0.7"])

    # going down / coming back
    fn("pve/downed", [
        "tag @s add pve.down", f"function {P}/body", "gamemode spectator @s", *PERK_RESET,
        *[f"execute if score #map pve matches {i} run tp @s {PCX + 0.5} {AY + downed_y(key)} {z + 0.5}" for (i, key, _, _, _, z, _) in OUTBREAK_MAPS],
        "title @s title {\"text\":\"DOWN\",\"color\":\"dark_red\",\"bold\":true}",
        "title @s subtitle {\"text\":\"A teammate can revive you, or you're back next wave\",\"color\":\"gray\"}",
        "tellraw @a[tag=pve.in] [{\"selector\":\"@s\",\"color\":\"red\"},{\"text\":\" went down!\",\"color\":\"gray\"}]",
    ])
    fn("pve/revive", [
        "tag @s remove pve.down", "gamemode adventure @s", "clear @s", "effect clear @s", "function cyber:admin/reset",
        f"function {NS}:kit/give_pve", f"function {P}/tp_spawn", say("@s", "You're back in the fight!", "green"),
    ])
    # co-op revive: a glowing marker where you went down; a teammate crouching next to it for 3 s brings you back there
    wj(f"data/{NS}/predicate/sneaking.json", {"condition": "minecraft:entity_properties", "entity": "this",
                                             "predicate": {"flags": {"is_sneaking": True}}})
    fn("pve/body", [
        "execute unless score @s pvp.id matches 1.. store result score @s pvp.id run scoreboard players add #nextid pvp 1",
        "data modify storage pvp:pve body set value {x:0,y:0,z:0}",
        "execute store result storage pvp:pve body.x int 1 run data get entity @s LastDeathLocation.pos[0]",
        "execute store result storage pvp:pve body.y int 1 run data get entity @s LastDeathLocation.pos[1]",
        "execute store result storage pvp:pve body.z int 1 run data get entity @s LastDeathLocation.pos[2]",
        f"function {P}/body_summon with storage pvp:pve body",
        "scoreboard players operation @n[type=minecraft:armor_stand,tag=pve.bnew] pvp.id = @s pvp.id",
        "scoreboard players set @n[type=minecraft:armor_stand,tag=pve.bnew] pve.rv 0",
        "tag @e[type=minecraft:armor_stand,tag=pve.bnew] remove pve.bnew"])
    fn("pve/body_summon", ["$summon minecraft:armor_stand $(x) $(y) $(z) {Tags:[\"pve.body\",\"pve.bnew\"],Invisible:1b,Invulnerable:1b,NoGravity:1b,"
                           "Marker:1b,Glowing:1b,CustomNameVisible:1b,CustomName:{\"text\":\"☠ Downed teammate · crouch here to revive\",\"color\":\"red\"}}"])
    fn("pve/revive_tick", [   # as a body, at it
        f"execute if entity @a[tag=pve.in,tag=!pve.down,distance=..2,predicate={NS}:sneaking] run scoreboard players add @s pve.rv 1",
        f"execute unless entity @a[tag=pve.in,tag=!pve.down,distance=..2,predicate={NS}:sneaking] run scoreboard players set @s pve.rv 0",
        "particle minecraft:dust{color:[1.0,0.1,0.1],scale:1.0} ~ ~0.3 ~ 0.3 0.1 0.3 0 2",
        f"execute if score @s pve.rv matches 1.. as @a[tag=pve.in,tag=!pve.down,distance=..2,predicate={NS}:sneaking] run title @s actionbar "
        "[{\"text\":\"Reviving... \",\"color\":\"green\"},{\"score\":{\"name\":\"@n[tag=pve.body]\",\"objective\":\"pve.rv\"},\"color\":\"white\"},"
        f"{{\"text\":\"/{REVIVE_TICKS}\",\"color\":\"gray\"}}]",
        f"execute if score @s pve.rv matches {REVIVE_TICKS}.. run function {P}/revive_done"])
    fn("pve/revive_done", [   # as the body
        "scoreboard players operation #id pvp = @s pvp.id",
        "execute as @a[tag=pve.in,tag=!pve.down,distance=..2,predicate=pvp:sneaking,limit=1] run tag @s add pve.saver",
        f"execute as @a[tag=pve.down] if score @s pvp.id = #id pvp run function {P}/revive",
        "execute as @a[tag=pve.in] if score @s pvp.id = #id pvp run tp @s @n[type=minecraft:armor_stand,tag=pve.body]",
        "execute as @a[tag=pve.in] if score @s pvp.id = #id pvp run tellraw @a[tag=pve.in] [{\"selector\":\"@a[tag=pve.saver]\",\"color\":\"green\"},"
        "{\"text\":\" revived \",\"color\":\"gray\"},{\"selector\":\"@s\",\"color\":\"green\"},{\"text\":\"! (+250 points)\",\"color\":\"gray\"}]",
        "scoreboard players add @a[tag=pve.saver] pve.pts 250", "tag @a remove pve.saver",
        "playsound minecraft:item.totem.use player @a[distance=..16] ~ ~ ~ 0.6 1.4", "particle minecraft:totem_of_undying ~ ~1 ~ 0.4 0.8 0.4 0.3 30",
        "kill @s"])
    fn("pve/body_keep", ["scoreboard players operation #id pvp = @s pvp.id",
                         "execute as @e[type=minecraft:armor_stand,tag=pve.body] if score @s pvp.id = #id pvp run tag @s remove pve.orphan"])
    # the quest: Power Cells from boss waves -> the Annihilator
    fn("pve/assemble", [
        "execute store result score #c pve run clear @s *[minecraft:custom_data~{pvp_cell:1b}] 0",
        f"execute if score #c pve matches ..{CELLS_NEEDED - 1} run return run tellraw @s [{{\"text\":\"You need {CELLS_NEEDED} Power Cells (you have \",\"color\":\"red\"}},"
        "{\"score\":{\"name\":\"#c\",\"objective\":\"pve\"},\"color\":\"white\"},{\"text\":\"). Every boss wave you clear gives one.\",\"color\":\"red\"}]",
        f"clear @s *[minecraft:custom_data~{{pvp_cell:1b}}] {CELLS_NEEDED}", abilities.give("annihilator"),
        "playsound minecraft:block.end_portal.spawn player @a[tag=pve.in] ~ ~ ~ 0.6 1.4", "particle minecraft:end_rod ~ ~1 ~ 0.5 1 0.5 0.1 60",
        "tellraw @a[tag=pve.in] [{\"text\":\"☣ \",\"color\":\"light_purple\"},{\"selector\":\"@s\",\"color\":\"white\"},"
        "{\"text\":\" assembled the \",\"color\":\"light_purple\"},{\"text\":\"ANNIHILATOR\",\"color\":\"light_purple\",\"bold\":true},{\"text\":\"!\",\"color\":\"light_purple\"}]"])
    fn("pve/game_over", [
        "scoreboard players set #state pve 0", "kill @e[type=minecraft:armor_stand,tag=pve.body]", "kill @e[tag=pve.mob]", "kill @e[type=minecraft:item,tag=pve.pu]", "scoreboard players set #dp pve 0",
        *[f"forceload remove {PCX - PR - 1} {z - PR - 1} {PCX + PR + 1} {z + PR + 1}" for (_, _, _, _, _, z, _) in OUTBREAK_MAPS],
        "bossbar set pvp:boss visible false",
        "execute unless score #hwwon pve matches 1 run tellraw @a[tag=pve.in] [{\"text\":\"☣ Outbreak over. You reached wave \",\"color\":\"red\"},{\"score\":{\"name\":\"#wave\",\"objective\":\"pve\"},\"color\":\"white\",\"bold\":true},{\"text\":\".\",\"color\":\"red\"}]",
        "scoreboard players add @a[tag=pve.in] pve.best 0",   # unset scores never compare, so a first run would never count
        "execute as @a[tag=pve.in] if score #wave pve > @s pve.best run scoreboard players operation @s pve.best = #wave pve",
        "execute if score #wave pve > #record pve run tellraw @a [{\"text\":\"☣ New Outbreak record: wave \",\"color\":\"gold\"},{\"score\":{\"name\":\"#wave\",\"objective\":\"pve\"},\"color\":\"white\",\"bold\":true},"
        "{\"text\":\" by \",\"color\":\"gold\"},{\"selector\":\"@a[tag=pve.in]\",\"color\":\"yellow\"}]",
        "execute if score #wave pve > #record pve run scoreboard players operation #record pve = #wave pve",
        f"execute as @a[tag=pve.in] run function {NS}:to_lobby",
        "team empty pve",   # players who logged off mid-run are still on the team (green name) until they rejoin
        "scoreboard players set #wave pve 0", "scoreboard players set #hwwon pve 0",
    ])

    # Arsenal shop
    buy = ["scoreboard players operation #n pve = @s pve.buy", "scoreboard players set @s pve.buy 0",
           f"execute unless entity @s[tag=pve.in,tag=!pve.down] run return run {say('@s', 'The Arsenal only serves Outbreak survivors.', 'red')}"]
    for (sid, name, color, ic, cost, lore, cmds, once) in SHOP:
        buy.append(f"execute if score #n pve matches {sid} run function {P}/shop/{sid}")
        fn(f"pve/shop/{sid}", [
            f"execute if entity @s[tag={once}] run return run {say('@s', f'You already have {name}.', 'red')}" if once else None,
            *([] if cost is None else [
                f"execute if score @s pve.pts matches ..{cost - 1} run return run {afford(name, cost)}",
                f"scoreboard players remove @s pve.pts {cost}"]),
            *cmds, f"tag @s add {once}" if once else None,
            *([] if cost is None else [f"tellraw @s [{{\"text\":\"Bought \",\"color\":\"green\"}},{{\"text\":\"{name}\",\"color\":\"{color}\"}}]",
                                       "playsound minecraft:entity.villager.yes neutral @s ~ ~ ~ 1 0.8"])])
    build_upgrades()
    fn("pve/buy", buy)
    # wall-buys: the clicked interaction carries the gun's number (pve.wb)
    wj(f"data/{NS}/advancement/wallbuy.json", {"criteria": {"c": {"trigger": "minecraft:player_interacted_with_entity", "conditions": {"entity": [{
        "condition": "minecraft:entity_properties", "entity": "this",
        "predicate": {"minecraft:entity_type": "minecraft:interaction", "minecraft:nbt": "{Tags:[\"pvp.wallbuy\"]}"}}]}}},
        "rewards": {"function": f"{P}/wallbuy"}})
    fn("pve/wallbuy", ["advancement revoke @s only pvp:wallbuy", "scoreboard players set #wb pve 0",
                       "execute as @e[type=minecraft:interaction,tag=pvp.wallbuy,distance=..6] if data entity @s interaction run scoreboard players operation #wb pve = @s pve.wb",
                       "execute as @e[type=minecraft:interaction,tag=pvp.wallbuy,distance=..6] run data remove entity @s interaction",
                       f"execute unless entity @s[tag=pve.in,tag=!pve.down] run return run {say('@s', 'Wall guns are for Outbreak survivors.', 'red')}",
                       *[f"execute if score #wb pve matches {n} run return run function {P}/wallbuy/{n}" for n in range(1, len(WALL_BUYS) + 1)]])
    for n, (k, cost) in enumerate(WALL_BUYS, 1):
        gname, gcolor = abilities.ABILITIES[k][0], abilities.ABILITIES[k][1]
        have = say("@s", f"You already have the {gname}. Pack-a-Punch it at the Arsenal.", "gold")
        fn(f"pve/wallbuy/{n}", [
            f"execute if items entity @s container.* {abilities.sel(k)} run return run {have}",
            f"execute if items entity @s weapon.offhand {abilities.sel(k)} run return run {have}",
            f"execute if score @s pve.pts matches ..{cost - 1} run return run {afford(gname, cost)}",
            f"scoreboard players remove @s pve.pts {cost}", abilities.give(k),
            f"tellraw @s [{{\"text\":\"Bought \",\"color\":\"green\"}},{{\"text\":\"{gname}\",\"color\":\"{gcolor}\"}},{{\"text\":\" off the wall\",\"color\":\"green\"}}]",
            "playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 0.8", "playsound minecraft:entity.villager.yes neutral @s ~ ~ ~ 0.6 0.8"])
    box = ["execute store result score #r pve run random value 1..%d" % len(BOX),
           "playsound minecraft:block.chest.open player @s ~ ~ ~ 1 0.8"]
    for n, (bname, bcolor, bcmds) in enumerate(BOX, 1):
        fn(f"pve/box/{n}", bcmds + [
            f"tellraw @a[tag=pve.in] [{{\"selector\":\"@s\",\"color\":\"white\"}},{{\"text\":\" got \",\"color\":\"gray\"}},"
            f"{{\"text\":\"{bname}\",\"color\":\"{bcolor}\",\"bold\":true}},{{\"text\":\" from the Mystery Box\",\"color\":\"gray\"}}]"])
        box.append(f"execute if score #r pve matches {n} run function {P}/box/{n}")
    fn("pve/box", box)

    # build the Outbreak arenas: same footprint, themed per map
    for m in OUTBREAK_MAPS:
        fn(f"admin/build_pve_{m[1]}", build_pve_map(m))
    fn("admin/build_pve", [f"function {NS}:admin/build_pve_{m[1]}" for m in OUTBREAK_MAPS])

def build_halloween():
    """Haunted Night (Halloween): Outbreak map 6 played with the horror characters, 10 waves, The Scarecrow at wave 5
    and the Headless Horseman at wave 10. Surviving wave 10 ends the run and unlocks a random Halloween cosmetic for
    everyone in it. Open while hw/active (the mod sets #halloween pvp until HW_END; #hwforce pvp 1 opens it for tests)."""
    H = f"{NS}:hw"
    fn("hw/active", ["execute if score #hwforce pvp matches 1 run return 1", "execute if score #halloween pvp matches 1 run return 1", "return 0"])
    # the lobby NPC (a mannequin dressed as Michael Myers) with pumpkins around it; it goes away when the event ends
    x, y, z = HW_NPC
    deco = [(5, 4), (8, 4), (5, 7), (8, 7)]
    fn("admin/place_hw", [
        "kill @e[tag=pvp.hwnpc]", "kill @e[tag=pvp.hwdeco]",
        f"summon minecraft:mannequin {x} {y} {z} {{Tags:[\"pvp.hwnpc\"],Rotation:[130f,0f],Invulnerable:1b,Silent:1b,immovable:1b,hide_description:1b,"
        f"profile:{{properties:[{{name:\"textures\",value:\"{HEADS['myers']}\"}}]}},CustomNameVisible:1b,"
        f"CustomName:{tj({'text': '🎃 Haunted Night 🎃', 'color': 'gold', 'bold': True})},equipment:{{mainhand:{{id:\"minecraft:iron_sword\",count:1}}}}}}",
        f"summon minecraft:interaction {x} {y} {z} {{Tags:[\"pvp.hwnpc\"],width:1.2f,height:2.2f,response:1b}}",
        f"summon minecraft:text_display {x} {y + 2.75} {z} {{Tags:[\"pvp.hwdeco\"],billboard:\"center\",background:0,"
        f"text:{tj([{'text': 'Halloween event', 'color': 'dark_purple'}, {'text': chr(10) + 'until ' + HW_END, 'color': 'gray'}])}}}",
        *[f"setblock {dx} {y} {dz} minecraft:jack_o_lantern[facing=north]" for dx, dz in deco],
    ])
    fn("admin/remove_hw", ["kill @e[tag=pvp.hwnpc]", "kill @e[tag=pvp.hwdeco]", *[f"setblock {dx} {y} {dz} minecraft:air" for dx, dz in deco]])
    npc_adv("hwnpc", "pvp.hwnpc", f"function {H}/npc")
    busy = say("@s", "An Outbreak is running right now. Haunted Night opens when it's over.", "gold")
    fn("hw/npc", [
        f"execute unless function {H}/active run return run {say('@s', 'Haunted Night is over for this year. Thanks for playing!', 'gold')}",
        f"execute if score #state pve matches 1.. unless score #map pve matches {HW_MAP} run return run {busy}",
        f"execute if score #state pve matches 1.. run return run function {NS}:pve/open_menu",
        f"scoreboard players set #j pve {80 + HW_MAP}", f"function {NS}:pve/pick_map"])
    # once a second (pvp second): the NPC disappears when the event is over
    fn("hw/gate", [f"execute unless function {H}/active if entity @e[tag=pvp.hwnpc] run function {NS}:admin/remove_hw"])
    fn("hw/fix_kit", [f"function {NS}:kit/roll_hw", "scoreboard players operation @s pve.kit = #rk pvp"])
    fn("hw/unfix_kit", [f"function {NS}:kit/roll", "scoreboard players operation @s pve.kit = #rk pvp"])
    fn("hw/enter_title", ["title @s title {\"text\":\"🎃 HAUNTED NIGHT\",\"color\":\"gold\",\"bold\":true}",
                          f"title @s subtitle {tj({'text': f'Survive {HW_WAVES} waves', 'color': 'gray'})}",
                          "playsound minecraft:entity.wither.ambient player @s ~ ~ ~ 0.6 0.6"])

    # bosses: The Scarecrow (wave 5) and the Headless Horseman on his skeleton horse (wave 10)
    mob = "Tags:[\"pve.mob\",\"pve.boss\",\"pve.new\"{t}],PersistenceRequired:1b,CanPickUpLoot:0b,DeathLootTable:\"minecraft:empty\",CustomNameVisible:1b"
    fn("hw/boss", [f"execute if score #wave pve matches {HW_WAVES}.. run return run function {H}/boss_horseman with storage pvp:pve map",
                   f"function {H}/boss_scarecrow with storage pvp:pve map"])
    def boss_done(name, color, bar):
        return [f"execute as @e[tag=pve.new] run function {NS}:pve/scale with storage pvp:pve s",
                f"bossbar set pvp:boss name {tj({'text': name, 'color': color, 'bold': True})}", f"bossbar set pvp:boss color {bar}",
                "execute store result bossbar pvp:boss max run data get entity @n[tag=pve.boss] Health",
                "bossbar set pvp:boss players @a[tag=pve.in]", "bossbar set pvp:boss visible true",
                f"tellraw @a[tag=pve.in] {tj([{'text': '🎃 ', 'color': color}, {'text': name, 'color': color, 'bold': True}, {'text': ' rises from the graves!', 'color': 'gray'}])}",
                "execute as @a[tag=pve.in] at @s run playsound minecraft:entity.wither.spawn player @s ~ ~ ~ 0.5 0.7"]
    fn("hw/boss_scarecrow", [
        f"$summon minecraft:zombie {PCX + 0.5} {AY + 1} $(bz) {{" + mob.format(t=',"pvp.scarecrow"') + ",IsBaby:0b,"
        "CustomName:{\"text\":\"The Scarecrow\",\"color\":\"gold\",\"bold\":true},"
        "equipment:{head:{id:\"minecraft:carved_pumpkin\",count:1},chest:{id:\"minecraft:leather_chestplate\",count:1,components:{\"minecraft:dyed_color\":9127187}},"
        "mainhand:{id:\"minecraft:iron_hoe\",count:1}},drop_chances:{head:0.0f,chest:0.0f,mainhand:0.0f},"
        "attributes:[{id:\"minecraft:follow_range\",base:64d},{id:\"minecraft:scale\",base:1.8d},{id:\"minecraft:max_health\",base:220d},"
        "{id:\"minecraft:attack_damage\",base:9d},{id:\"minecraft:knockback_resistance\",base:0.8d},{id:\"minecraft:movement_speed\",base:0.27d}]}"]
        + boss_done("The Scarecrow", "gold", "yellow"))
    fn("hw/boss_horseman", [
        f"$summon minecraft:skeleton_horse {PCX + 0.5} {AY + 1} $(bz) {{Tags:[\"pve.mob\",\"pve.new\",\"pvp.hwhorse\"],PersistenceRequired:1b,"
        "DeathLootTable:\"minecraft:empty\",Tame:0b,attributes:[{id:\"minecraft:max_health\",base:80d},{id:\"minecraft:movement_speed\",base:0.3d}],"
        "Passengers:[{id:\"minecraft:wither_skeleton\"," + mob.format(t=',"pvp.horseman"') + ","
        "CustomName:{\"text\":\"The Headless Horseman\",\"color\":\"dark_red\",\"bold\":true},"
        "equipment:{chest:{id:\"minecraft:leather_chestplate\",count:1,components:{\"minecraft:dyed_color\":1381653}},"
        "legs:{id:\"minecraft:leather_leggings\",count:1,components:{\"minecraft:dyed_color\":1381653}},"
        "mainhand:{id:\"minecraft:netherite_hoe\",count:1},offhand:{id:\"minecraft:jack_o_lantern\",count:1}},"
        "drop_chances:{chest:0.0f,legs:0.0f,mainhand:0.0f,offhand:0.0f},"
        "attributes:[{id:\"minecraft:follow_range\",base:64d},{id:\"minecraft:scale\",base:1.3d},{id:\"minecraft:max_health\",base:420d},"
        "{id:\"minecraft:attack_damage\",base:12d},{id:\"minecraft:knockback_resistance\",base:1.0d}]}]}"]
        + boss_done("The Headless Horseman", "dark_red", "red"))
    # boss abilities, once a second during a wave (#hwt counts seconds)
    fn("hw/second", ["scoreboard players add #hwt pve 1",
                     f"execute as @e[tag=pvp.scarecrow] at @s run function {H}/scarecrow",
                     f"execute as @e[tag=pvp.horseman] at @s run function {H}/horseman"])
    fn("hw/scarecrow", [   # every 8 s: a cloud of crows (slows and blinds nearby players) and two Pumpkinheads
        "scoreboard players operation #m pve = #hwt pve", "scoreboard players operation #m pve %= #8c pve",
        "execute unless score #m pve matches 0 run return 0",
        "effect give @a[tag=pve.in,tag=!pve.down,distance=..7] minecraft:slowness 3 1",
        "effect give @a[tag=pve.in,tag=!pve.down,distance=..7] minecraft:blindness 2 0",
        "particle minecraft:squid_ink ~ ~2 ~ 3 1 3 0.05 60", "playsound minecraft:entity.parrot.imitation.phantom hostile @a[distance=..32] ~ ~ ~ 1 0.6",
        *[f"summon minecraft:zombie ~{dx} ~ ~ {{Tags:[\"pve.mob\",\"pve.new\"],PersistenceRequired:1b,CanPickUpLoot:0b,DeathLootTable:\"minecraft:empty\","
          "CustomName:{text:\"Pumpkinhead\",color:\"gold\"},equipment:{head:{id:\"minecraft:carved_pumpkin\",count:1}},drop_chances:{head:0.0f},"
          "attributes:[{id:\"minecraft:follow_range\",base:64d}]}" for dx in (2, -2)],
        f"execute as @e[tag=pve.new] run function {NS}:pve/scale with storage pvp:pve s"])
    fn("hw/horseman", [   # every 4 s: graves burst under two players; every 12 s: two Ghosts; below half health: faster
        "scoreboard players operation #m pve = #hwt pve", "scoreboard players operation #m pve %= #4c pve",
        f"execute if score #m pve matches 0 as @a[tag=pve.in,tag=!pve.down,distance=..40,sort=random,limit=2] at @s run function {H}/grave_burst",
        "scoreboard players operation #m pve = #hwt pve", "scoreboard players operation #m pve %= #12c pve",
        "execute if score #m pve matches 0 run summon minecraft:vex ~ ~2 ~ {Tags:[\"pve.mob\",\"pve.new\"],PersistenceRequired:1b,DeathLootTable:\"minecraft:empty\",CustomName:{text:\"Ghost\",color:\"white\"}}",
        "execute if score #m pve matches 0 run summon minecraft:vex ~ ~2 ~ {Tags:[\"pve.mob\",\"pve.new\"],PersistenceRequired:1b,DeathLootTable:\"minecraft:empty\",CustomName:{text:\"Ghost\",color:\"white\"}}",
        "execute if score #m pve matches 0 run playsound minecraft:entity.vex.charge hostile @a[distance=..32] ~ ~ ~ 1 0.5",
        f"execute as @e[tag=pve.new] run function {NS}:pve/scale with storage pvp:pve s",
        "execute store result score #hp pve run data get entity @s Health", "execute store result score #hpm pve run attribute @s minecraft:max_health get",
        "scoreboard players operation #hpm pve /= #2c pve",
        "execute if score #hp pve <= #hpm pve on vehicle run effect give @s minecraft:speed 2 1 true",
        "execute if score #hp pve <= #hpm pve run particle minecraft:flame ~ ~2 ~ 0.3 0.4 0.3 0.02 6"])
    fn("hw/grave_burst", ["summon minecraft:evoker_fangs ~ ~ ~ {warmup:10}", "summon minecraft:evoker_fangs ~1 ~ ~ {warmup:12}",
                          "summon minecraft:evoker_fangs ~-1 ~ ~ {warmup:12}",
                          "particle minecraft:soul ~ ~0.2 ~ 0.6 0.1 0.6 0.02 15", "playsound minecraft:entity.evoker.prepare_attack hostile @a[distance=..16] ~ ~ ~ 1 0.6"])

    # winning: everyone in the run gets a random Halloween cosmetic they don't have yet
    fn("hw/victory", [
        "scoreboard players set #hwwon pve 1",
        f"tellraw @a {tj([{'text': '🎃 ', 'color': 'gold'}, {'selector': '@a[tag=pve.in]', 'color': 'yellow'}, {'text': ' survived ', 'color': 'gold'}, {'text': 'Haunted Night', 'color': 'gold', 'bold': True}, {'text': '!', 'color': 'gold'}])}",
        "title @a[tag=pve.in] title {\"text\":\"YOU SURVIVED\",\"color\":\"gold\",\"bold\":true}",
        "title @a[tag=pve.in] subtitle {\"text\":\"Haunted Night is over... for now\",\"color\":\"gray\"}",
        "execute as @a[tag=pve.in] at @s run playsound minecraft:ui.toast.challenge_complete player @s ~ ~ ~ 1 0.8",
        "execute as @a[tag=pve.in] at @s run particle minecraft:totem_of_undying ~ ~1 ~ 0.5 1 0.5 0.4 60",
        "scoreboard players add @a[tag=pve.in] pvp.hwwins 1",
        f"execute as @a[tag=pve.in] run function {H}/reward",
        f"function {NS}:pve/game_over"])
    n = len(HW_COSMETICS)
    fn("hw/reward", [   # as a winner: one cosmetic they don't own yet, picked at random
        "scoreboard players set #c pvp 0",
        *[f"execute unless score @s pvp.hw{c[0]} matches 1 run scoreboard players add #c pvp 1" for c in HW_COSMETICS],
        f"execute if score #c pvp matches 0 run return run tellraw @s {tj([{'text': '🎃 You already have every Haunted Night cosmetic (' + str(n) + '/' + str(n) + '). Respect.', 'color': 'gold'}])}",
        "execute store result score #r pvp run random value 0..999999", "scoreboard players operation #r pvp %= #c pvp",
        *[l for c in HW_COSMETICS for l in (
            f"execute unless score @s pvp.hw{c[0]} matches 1 if score #r pvp matches 0 run function {H}/grant/{c[0]}",
            f"execute unless score @s pvp.hw{c[0]} matches 1 run scoreboard players remove #r pvp 1")],
    ])
    for (i, kind, lid, name, code) in HW_COSMETICS:
        fn(f"hw/grant/{i}", [
            f"scoreboard players set @s pvp.hw{i} 1", "scoreboard players set #r pvp -1",
            f"tellraw @s {tj([{'text': '🎃 Unlocked the ', 'color': 'gold'}, {'text': name, 'color': 'yellow', 'bold': True}, {'text': ' ' + HW_KIND[kind] + '! ', 'color': 'gold'}, {'text': 'Wear it from /cosmetics > Halloween on any server (it shows up there within 5 minutes).', 'color': 'gray'}])}",
            "playsound minecraft:entity.player.levelup player @s ~ ~ ~ 1 1.2"])



PVE_THEMES = {"ruins": ("stone_bricks", "polished_andesite"), "mine": ("stone", "polished_tuff"),   # outer wall, Arsenal platform
              "neon": ("black_concrete", "light_blue_concrete"), "hellfort": ("nether_bricks", "polished_blackstone"),
              "orbital": ("black_concrete", "cyan_concrete"), "haunted": ("deepslate_bricks", "polished_blackstone")}   # the station sits in black "space"


def wallbuys(g, cz, key):
    """Wall-buy guns for one map: the gun on the wall (item display), its name and price above it, and an interaction
    in front to right-click. Spots are worked out from the layout (outbreak_maps.wallbuy_spots)."""
    out, ids = [], {k: i for i, (k, _) in enumerate(WALL_BUYS, 1)}
    guns = [(k, dict(WALL_BUYS)[k]) for k in WALL_MAPS[key]]
    for (x, z, ox, oz), (k, cost) in zip(outbreak_maps.wallbuy_spots(g, len(guns)), guns):
        n = ids[k]
        gname, gcolor, gmodel = abilities.ABILITIES[k][:3]
        cx, cz_ = PCX + x + 0.5, cz + z + 0.5
        yaw = round(math.degrees(math.atan2(ox, -oz)))   # facing away from the wall
        at = lambda d, y: f"{cx + ox * d:.2f} {AY + 1 + y:.2f} {cz_ + oz * d:.2f}"
        out += [
            f"summon minecraft:item_display {at(0.45, 1.35)} {{Tags:[\"pvp.wallbuy\"],Rotation:[{yaw}f,0f],item_display:\"fixed\","
            f"brightness:{{sky:15,block:15}},transformation:{{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[0.9f,0.9f,0.9f]}},"
            f"item:{{id:\"minecraft:clay_ball\",count:1,components:{{\"minecraft:item_model\":\"minecraft:{gmodel}\",\"minecraft:enchantment_glint_override\":true}}}}}}",
            f"summon minecraft:text_display {at(0.4, 2.05)} {{Tags:[\"pvp.wallbuy\"],Rotation:[{yaw}f,0f],billboard:\"fixed\",alignment:\"center\","
            f"background:1426063360,transformation:{{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[0.6f,0.6f,0.6f]}},"
            f"text:{tj([{'text': gname, 'color': gcolor, 'bold': True}, {'text': chr(10) + f'{cost:,} points · right-click', 'color': 'gray', 'bold': False}])}}}",
            f"summon minecraft:interaction {at(0.2, 0.7)} {{Tags:[\"pvp.wallbuy\",\"pvp.wbnew\"],width:0.6f,height:1.1f,response:1b}}",
            f"scoreboard players set @e[type=minecraft:interaction,tag=pvp.wbnew] pve.wb {n}",
            "tag @e[type=minecraft:interaction,tag=pvp.wbnew] remove pvp.wbnew"]
    return out


def build_pve_map(m):
    """Clear the map, put up the outer wall (with barrier above) and draw the layout from outbreak_maps.py."""
    i, key, name, color, _, cz, _ = m
    wall, plat = PVE_THEMES[key]
    g = outbreak_maps.MAPS[key](map_points(key), PVE_SPAWNS)
    outbreak_maps.check(g, name)
    x1, x2, z1, z2 = PCX - PR, PCX + PR, cz - PR, cz + PR
    a = [f"fill {x1} {AY + 1 + k} {z1} {x2} {AY + 5 + k} {z2} minecraft:air" for k in range(0, 30, 5)]
    a.append(f"fill {x1} {AY - 1} {z1} {x2} {AY} {z2} minecraft:{wall}")
    a += walls(PCX, cz, PR, wall, wall)
    a += outbreak_maps.commands(g, PCX, AY, cz)
    a += [f"fill {PCX - 1} {AY + 1} {cz - 1} {PCX + 1} {AY + 1} {cz + 1} minecraft:{plat}",   # Arsenal platform
          f"setblock {PCX} {AY + 1} {cz} minecraft:lodestone"]
    a += [f"kill @e[tag=pvp.wallbuy,{PVE_BOXES[i]}]"] + wallbuys(g, cz, key)
    sx, sy, _ = SHOP_NPC
    body = npc("pvp.shopnpc", (sx, sy, cz + 0.5), "☣ Arsenal ☣", "green", "", "", 180, mannequin=True)
    a += [f"kill @e[tag=pvp.shopnpc,x={sx},y={sy},z={cz + 0.5},distance=..4]"] + body[1:]   # only this map's Arsenal
    return a

if __name__ == "__main__":
    OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist"), "crispy_pvp")
    build()
    print(f"built {OUT} ({sum(len(f) for _, _, f in os.walk(OUT))} files)")
