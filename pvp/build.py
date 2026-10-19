#!/usr/bin/env python3
"""Builds the crispy_pvp datapack (Crispy PvP, Fabric 26.2, vanilla clients).

    python3 build.py [outdir]      -> <outdir>/crispy_pvp  (default: ./dist)

Kit/arena PvP plus "Outbreak", a CoD-zombies style wave mode, both using Anarchy's custom enchants
(crispy_enchants) and cyberware (crispy_cyberware built with --pvp, so implants don't drop).
Menus are chest screens opened with /pvpmenu (crispy-pvp-spawn mod) from storage pvp:menus.
"""
import json, os, random, shutil, sys

NS = "pvp"
PACK_FORMAT = [107, 0], [107, 1]

LOBBY_Y = 100                  # lobby floor; players stand at LOBBY_Y + 1, centred on 0,0
LOBBY_R = 11                   # lobby platform half-size
AY = -61                       # arena floors (superflat grass level); players stand at AY + 1
ACX, ACZ, AR = 0, 100, 30      # PvP arena centre and half-size
PCX, PCZ, PR = 0, 300, 22      # Outbreak (PvE) arena centre and half-size
KIT_NPC = (-3.5, LOBBY_Y + 1, -6.5)
PVE_NPC = (4.5, LOBBY_Y + 1, -6.5)
SHOP_NPC = (PCX + 0.5, AY + 2, PCZ + 0.5)

def box(cx, cz, r, y0, dy): return f"x={cx - r - 1},y={y0},z={cz - r - 1},dx={2 * r + 2},dy={dy},dz={2 * r + 2}"
# admin room under the lobby: chests of every custom enchant (max-level books) and every cyberware item
ROOM_Y = LOBBY_Y - 10                # room floor; interior ROOM_Y+1..ROOM_Y+4
ROOM_BOX = f"x=-10,y={ROOM_Y},z=-5,dx=20,dy=6,dz=10"
ENCHANTS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "enchants.json")))   # from crispy_enchants
IMPLANT_KEYS = ["kiroshi", "subdermal", "titanium", "lungs", "gorilla", "mantis", "tendons", "lynx", "grip", "reflex", "biomon",
                "heart", "sandy", "berserk", "neuro"]   # cyber:item/<key> loot tables
LOBBY_BOX = box(0, 0, LOBBY_R, LOBBY_Y - 1, 20)
ARENA_BOX = box(ACX, ACZ, AR, AY - 1, 35)
PVE_BOX = box(PCX, PCZ, PR, AY - 1, 35)

# PvP spawn points: offset from the centre, yaw facing the centre
SPAWNS = [(24, 0, 90), (-24, 0, -90), (0, -24, 0), (0, 24, 180), (20, -20, 45), (-20, -20, -45), (20, 20, 135), (-20, 20, -135)]
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
# Outbreak: player spawns around the Arsenal, mob windows just inside the walls, ruins for cover
PVE_SPAWNS = [(4, 4, -45), (-4, 4, 45), (4, -4, -135), (-4, -4, 135)]
MOB_POINTS = [(20, 0), (-20, 0), (0, 20), (0, -20), (20, 12), (20, -12), (-20, 12), (-20, -12), (12, 20), (-12, 20), (12, -20), (-12, -20)]
RUINS = [(-12, -12, -8, -11, 3, "mossy_stone_bricks"), (8, -14, 9, -8, 2, "cobblestone"), (-14, 6, -13, 12, 3, "stone_bricks"),
         (10, 10, 14, 11, 2, "mossy_cobblestone"), (-4, 14, 4, 15, 2, "cracked_stone_bricks"), (-4, -16, 4, -15, 2, "cracked_stone_bricks"),
         (15, -3, 16, 3, 3, "mossy_stone_bricks"), (-17, -3, -16, 3, 2, "cobblestone"), (5, 4, 6, 8, 2, "mossy_cobblestone"),
         (-8, -6, -5, -5, 2, "stone_bricks")]


def ench(d): return "{" + ",".join(f'"{k if ":" in k else "minecraft:" + k}":{v}' for k, v in d.items()) + "}"
def item(id_, name=None, color="white", enchants=None, extra=""):
    comps = ["minecraft:unbreakable={}"]
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
FOOD = ["give @s minecraft:cooked_beef 16", "give @s minecraft:golden_apple 2"]
# id, key, name, colour, menu icon, blurb lines, item commands, implants (one per body slot)
KITS = [
    (1, "samurai", "Edgerunner", "aqua", "netherite_sword", ["Katana: Sharpness V, Lifesteal III, Double Strike II", "Sandevistan, Mantis Blades, Reflex Tuner, Kiroshi"],
     [f"give @s {item('netherite_sword', 'Edgerunner Katana', 'aqua', {'sharpness': 5, CE + 'lifesteal': 3, CE + 'doublestrike': 2})}"]
     + armor("diamond", 3), ["sandy", "mantis", "reflex", "kiroshi"]),
    (2, "tank", "Juggernaut", "gray", "netherite_chestplate", ["Netherite Prot IV, Armored III, Tank II, shield", "Subdermal Armor, Titanium Bones, Second Heart, Lynx Paws"],
     [f"give @s {item('netherite_sword', 'Breaker', 'gray', {'sharpness': 3})}", f"item replace entity @s weapon.offhand with {item('shield')}"]
     + armor("netherite", 4, {"chest": {CE + "armored": 3}, "legs": {CE + "tank": 2}}), ["subdermal", "titanium", "heart", "lynx"]),
    (3, "sniper", "Sniper", "green", "bow", ["Bow: Power V, Lethal Sniper III, Lightning Arrows II", "Kiroshi, Reinforced Tendons, Biomonitor, Reflex Tuner"],
     [f"give @s {item('bow', 'Overwatch', 'green', {'power': 5, 'infinity': 1, CE + 'lethalsniper': 3, CE + 'lightningarrows': 2})}",
      f"give @s {item('iron_sword', enchants={'sharpness': 2})}", "give @s minecraft:arrow 1"]
     + armor("diamond", 2), ["kiroshi", "tendons", "biomon", "reflex"]),
    (4, "berserker", "Berserker", "red", "netherite_axe", ["Axe: Sharpness V, Cleave III, Bleed III, Rage II", "Gorilla Arms, Berserk, Titanium Bones"],
     [f"give @s {item('netherite_axe', 'Ripper', 'red', {'sharpness': 5, CE + 'cleave': 3, CE + 'bleed': 3, CE + 'rage': 2})}"]
     + armor("diamond", 3), ["gorilla", "berserk", "titanium"]),
    (5, "assassin", "Netrunner", "dark_purple", "diamond_sword", ["Blade: Sharpness IV, Assassin III, Poison II + Invisibility", "Sandevistan, Lynx Paws, Reflex Tuner, Kiroshi"],
     [f"give @s {item('diamond_sword', 'Monowire', 'dark_purple', {'sharpness': 4, CE + 'assassin': 3, CE + 'poison': 2})}", potion("splash_potion", "invisibility")]
     + armor({"head": "diamond", "chest": "leather", "legs": "leather", "feet": "diamond"}, 2, dye=1908001), ["sandy", "lynx", "reflex", "kiroshi"]),
    (6, "medic", "Medic", "light_purple", "glistering_melon_slice", ["Lifesteal sword, Angelic III chest, 4 healing + 2 regen", "Biomonitor, Bionic Lungs, Kiroshi, Reflex Tuner"],
     [f"give @s {item('netherite_sword', 'Scalpel', 'light_purple', {'sharpness': 3, CE + 'lifesteal': 2})}",
      potion("splash_potion", "strong_healing", 4), potion("potion", "regeneration", 2)]
     + armor("diamond", 3, {"chest": {CE + "angelic": 3}}), ["biomon", "lungs", "kiroshi", "reflex"]),
    (7, "pyro", "Pyro", "gold", "blaze_powder", ["Fire Aspect II + Execute sword, Flame bow, Fire Prot IV", "Gorilla Arms, Berserk, Biomonitor, Lynx Paws"],
     [f"give @s {item('netherite_sword', 'Incinerator', 'gold', {'sharpness': 4, 'fire_aspect': 2, CE + 'execute': 3})}",
      f"give @s {item('bow', enchants={'power': 3, 'flame': 1, 'infinity': 1})}", "give @s minecraft:arrow 1"]
     + armor("diamond", 2, {s: {"fire_protection": 4} for s in ("head", "chest", "legs", "feet")}), ["gorilla", "berserk", "biomon", "lynx"]),
    (8, "ranger", "Ranger", "dark_green", "crossbow", ["Crossbow: Quick Charge III, Multishot, Longbow II, Venom II", "Kiroshi, Reinforced Tendons, Reflex Tuner, Subdermal Armor"],
     [f"give @s {item('crossbow', 'Deadeye', 'dark_green', {'quick_charge': 3, 'multishot': 1, CE + 'longbow': 2, CE + 'venom': 2})}",
      f"give @s {item('iron_axe', enchants={'sharpness': 3})}", "give @s minecraft:arrow 64"]
     + armor("diamond", 2, {"feet": {CE + "springs": 2}}), ["kiroshi", "tendons", "reflex", "subdermal"]),
    (9, "shinobi", "Shinobi", "dark_gray", "ender_pearl", ["Shadow Assassin blade, 8 ender pearls, Dodge + Trickster", "Sandevistan, Lynx Paws, Kiroshi, Subdermal Armor"],
     [f"give @s {item('diamond_sword', 'Kage', 'dark_gray', {'sharpness': 4, CE + 'shadowassassin': 3, CE + 'featherweight': 2})}", "give @s minecraft:ender_pearl 8"]
     + armor({"head": "diamond", "chest": "leather", "legs": "leather", "feet": "diamond"}, 2,
             {"chest": {CE + "dodge": 3, CE + "trickster": 3}, "feet": {CE + "springs": 3, CE + "gears": 2}}, dye=3355443),
     ["sandy", "lynx", "kiroshi", "subdermal"]),
    (10, "skyhammer", "Skyhammer", "blue", "mace", ["Mace: Density IV, Wind Burst II, 16 wind charges", "Reinforced Tendons, Titanium Bones, Second Heart, Subdermal"],
     [f"give @s {item('mace', 'Skyhammer', 'blue', {'density': 4, 'wind_burst': 2})}", "give @s minecraft:wind_charge 16"]
     + armor("netherite", 3, {"feet": {"feather_falling": 4}}), ["tendons", "titanium", "heart", "subdermal"]),
]
KIT_SLOTS = [11, 12, 13, 14, 15, 20, 21, 22, 23, 24]
CUSTOM_SLOTS = [29, 30, 31, 32, 33, 38, 39, 40, 41, 42]   # admin-made kits (/pvpkit create), ids 101+

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
    (7, "Mystery Box", "light_purple", "chest", 950, "A random wonder weapon", ["function pvp:pve/box"], None),
    (8, "Ray Bow", "aqua", "bow", 5000, "Power X, Flame, Infinity, Punch II", [
        f"give @s {item('bow', 'Ray Bow', 'aqua', {'power': 10, 'flame': 1, 'infinity': 1, 'punch': 2})}", "give @s minecraft:arrow 1"], None),
    (9, "Rations", "yellow", "cooked_beef", 100, "16 steak", ["give @s minecraft:cooked_beef 16"], None),
]
SHOP_SLOTS = [10, 11, 12, 13, 14, 15, 16, 21, 23]
WAVE_FOOD = 4   # steak for every survivor when a wave is cleared
BOX = [   # Mystery Box rolls
    f"give @s {item('netherite_sword', 'Excalibur', 'gold', {'sharpness': 7, 'sweeping_edge': 3})}",
    f"give @s {item('trident', 'Thunderfang', 'aqua', {'impaling': 5, 'loyalty': 3})}",
    f"give @s {item('crossbow', 'Wunderwaffe', 'yellow', {'quick_charge': 3, 'multishot': 1, 'piercing': 4})}\ngive @s minecraft:arrow 64",
    f"give @s {item('mace', 'Thundergun', 'blue', {'density': 5, 'wind_burst': 3})}\ngive @s minecraft:wind_charge 16",
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
        "minecraft:lore": [{"text": l, "color": "gray", "italic": False} for l in lore],
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
    fn(f"open/{key}", [f"advancement revoke @s only {NS}:{key}", f"pvpmenu {menu}",
                       f"execute as @e[type=minecraft:interaction,tag={tag},distance=..8] run data remove entity @s interaction"])


def build():
    shutil.rmtree(OUT, ignore_errors=True)
    wj("pack.mcmeta", {"pack": {"description": "Crispy PvP: kit arena + Outbreak waves, custom enchants + cyberware (26.2)",
                                "min_format": PACK_FORMAT[0], "max_format": PACK_FORMAT[1]}})
    wj("data/minecraft/tags/function/load.json", {"values": [f"{NS}:load"]})
    wj("data/minecraft/tags/function/tick.json", {"values": [f"{NS}:tick"]})

    # ------------------------------------------------------------------ menus (opened by /pvpmenu)
    kit_lore = lambda k: k[5] + ["", "Click to pick"]
    menus = {
        "kits": {"title": {"text": "⚔ Pick a kit", "color": "dark_aqua"}, "rows": 6, "fill": PANE,
                 "custom_kits": {"slots": CUSTOM_SLOTS, "cmd": "trigger pvp.kit set %d"}, "items":
                 [{"slot": s, "item": icon(k[4], k[2], k[3], kit_lore(k)), "cmd": f"trigger pvp.kit set {k[0]}"} for s, k in zip(KIT_SLOTS, KITS)]
                 + [{"slot": 49, "item": icon("zombie_head", "☣ Outbreak (PvE)", "green", ["Fight waves of mobs solo or with a team", "Click to pick your loadout"]), "cmd": "pvpmenu pve"}]},
        "pve": {"title": {"text": "☣ Outbreak: pick your loadout", "color": "dark_green"}, "rows": 6, "fill": PANE,
                "custom_kits": {"slots": CUSTOM_SLOTS, "cmd": "trigger pve.join set %d"}, "items":
                [{"slot": s, "item": icon(k[4], k[2], k[3], k[5] + ["", "Click to queue with this kit"]), "cmd": f"trigger pve.join set {k[0]}"} for s, k in zip(KIT_SLOTS, KITS)]
                + [{"slot": 47, "item": icon("barrier", "Leave the queue", "red", ["Stop waiting for the next Outbreak"], False), "cmd": "trigger pve.join set 99"},
                   {"slot": 49, "item": icon("zombie_head", "How Outbreak works", "green", [
                       "Endless waves; every 5th wave brings a boss", "100 points per kill + a bonus each wave",
                       "Spend points at the Arsenal in the arena", "Go down and you're back next wave", "Game over when the whole team is down"]), "cmd": ""},
                   {"slot": 51, "item": icon("netherite_sword", "Back to PvP kits", "aqua", ["Fight other players instead"], False), "cmd": "pvpmenu kits"}]},
        "pve_shop": {"title": {"text": "☣ Arsenal (points)", "color": "dark_green"}, "rows": 3, "fill": PANE, "items":
                     [{"slot": s, "item": icon(i[3], f"{i[1]} · {i[4]}", i[2], [i[5]]), "cmd": f"trigger pve.buy set {i[0]}"} for s, i in zip(SHOP_SLOTS, SHOP)]},
    }

    rules = {"keep_inventory": "true", "immediate_respawn": "true", "spawn_mobs": "false", "advance_time": "false",
             "advance_weather": "false", "show_advancement_messages": "false", "respawn_radius": "0", "locator_bar": "false",
             "spawn_phantoms": "false", "mob_griefing": "false", "spawn_wandering_traders": "false", "raids": "false",
             "spawn_patrols": "false", "ender_pearls_vanish_on_death": "true", "command_block_output": "false"}
    fn("load", [
        *[f"scoreboard objectives add {o}" for o in [
            "pvp dummy", "pvp.kit trigger", "pvp.spawn trigger", "pvp.kn playerKillCount", "pvp.dead deathCount",
            "pvp.left minecraft.custom:minecraft.leave_game", "pvp.streak dummy", "pvp.best dummy",
            "pvp.hurt minecraft.custom:minecraft.damage_taken", "pvp.ct dummy",
            "pve dummy", "pve.join trigger", "pve.buy trigger", "pve.k totalKillCount", "pve.kit dummy", "pve.best dummy"]],
        'scoreboard objectives add pvp.kills playerKillCount {"text":"⚔ Kills","color":"aqua","bold":true}',
        'scoreboard objectives add pve.pts dummy {"text":"☣ Points","color":"green","bold":true}',
        "scoreboard objectives setdisplay sidebar pvp.kills",
        "team add pve", "team modify pve color green", "team modify pve friendlyFire false", "team modify pve seeFriendlyInvisibles true",
        "scoreboard objectives setdisplay sidebar.team.green pve.pts",
        'bossbar add pvp:boss {"text":"Abomination","color":"dark_red"}', "bossbar set pvp:boss color red", "bossbar set pvp:boss visible false",
        *[f"gamerule {k} {v}" for k, v in rules.items()],
        "time set 18000", "weather clear", f"setworldspawn 0 {LOBBY_Y + 1} 0", "scoreboard players set #t pvp 0",
        "scoreboard players set #100 pve 100", "scoreboard players set #5 pve 5", "scoreboard players set #20 pve 20", "scoreboard players set #4c pve 4", "scoreboard players set #2c pve 2",
        "execute unless score #state pve matches 0.. run scoreboard players set #state pve 0",
        "execute unless score #record pve matches 0.. run scoreboard players set #record pve 0",
        *[f"data modify storage pvp:menus {k} set value {tj(v)}" for k, v in menus.items()],
    ])

    fn("tick", [
        "scoreboard players enable @a pvp.kit", "scoreboard players enable @a pvp.spawn",
        f"execute as @a[tag=!pvp.seen] run function {NS}:to_lobby",
        f"execute as @a[scores={{pvp.left=1..}}] run function {NS}:to_lobby",
        f"execute as @e[type=minecraft:player,scores={{pvp.dead=1..}}] run function {NS}:respawned",
        f"execute as @a[scores={{pvp.kn=1..}}] at @s run function {NS}:killed",
        f"execute as @a[scores={{pvp.kit=1..}}] at @s run function {NS}:kit/pick",
        f"execute as @a[scores={{pvp.spawn=1..}}] run function {NS}:trigger_lobby",
        "scoreboard players set @a[scores={pvp.hurt=1..}] pvp.ct 200", "scoreboard players set @a[scores={pvp.hurt=1..}] pvp.hurt 0",
        "scoreboard players remove @a[scores={pvp.ct=1..}] pvp.ct 1",
        f"function {NS}:pve/tick",
        "scoreboard players add #t pvp 1", f"execute if score #t pvp matches 20.. run function {NS}:second",
    ])
    fn("second", [
        "scoreboard players set #t pvp 0",
        f"effect give @a[{LOBBY_BOX}] minecraft:resistance 3 4 true",
        f"effect give @a[{LOBBY_BOX}] minecraft:weakness 3 255 true",
        f"effect give @a[{LOBBY_BOX}] minecraft:saturation 3 0 true",
        # anyone (in adventure) outside the lobby and both arenas goes back to the lobby
        f"execute as @a[gamemode=adventure] unless entity @s[{LOBBY_BOX}] unless entity @s[{ARENA_BOX}] unless entity @s[{PVE_BOX}] unless entity @s[tag=pvp.admin,{ROOM_BOX}] run function {NS}:to_lobby",
        f"function {NS}:pve/second",
        # NPC clicks are advancements; clear any left granted so an NPC can never get stuck for a player
        "advancement revoke @a only pvp:npc", "advancement revoke @a only pvp:pvenpc", "advancement revoke @a only pvp:shopnpc",
    ])
    fn("to_lobby", [
        "clear @s", "effect clear @s", "function cyber:admin/reset", "gamemode adventure @s",
        "attribute @s minecraft:max_health modifier remove pvp:jug",
        "tag @s remove pve.in", "tag @s remove pve.down", "tag @s remove pve.q", "tag @s remove pve.jug", "tag @s remove pve.cola", "team leave @s",
        f"tp @s 0.5 {LOBBY_Y + 1} 0.5 180 0",
        "scoreboard players set @s pvp.left 0", "scoreboard players set @s pvp.ct 0",
        "scoreboard players add @s pvp.streak 0", "scoreboard players add @s pvp.kills 0",
        "tag @s add pvp.seen",
        "title @s actionbar {\"text\":\"Kit Dealer: PvP  ·  Outbreak: fight waves of mobs\",\"color\":\"aqua\"}",
    ])
    fn("trigger_lobby", [
        "scoreboard players set @s pvp.spawn 0",
        "execute if score @s pvp.ct matches 1.. run return run tellraw @s {\"text\":\"You can't leave combat yet (10 s after taking damage).\",\"color\":\"red\"}",
        f"function {NS}:to_lobby",
    ])
    fn("respawned", [
        "scoreboard players set @s pvp.dead 0",
        f"execute if entity @s[tag=pve.in] run return run function {NS}:pve/downed",
        "execute if score @s pvp.streak matches 3.. run tellraw @a [{\"selector\":\"@s\",\"color\":\"yellow\"},{\"text\":\"'s \",\"color\":\"gray\"},"
        "{\"score\":{\"name\":\"@s\",\"objective\":\"pvp.streak\"},\"color\":\"gold\"},{\"text\":\" kill streak was ended.\",\"color\":\"gray\"}]",
        "scoreboard players set @s pvp.streak 0",
        f"function {NS}:to_lobby",
    ])
    fn("killed", [
        "scoreboard players add @s pvp.streak 1", "scoreboard players set @s pvp.kn 0",
        "execute if score @s pvp.streak > @s pvp.best run scoreboard players operation @s pvp.best = @s pvp.streak",
        "effect give @s minecraft:instant_health 1 0", "effect give @s minecraft:absorption 10 0",
        "give @s minecraft:golden_apple 1",
        "playsound minecraft:entity.experience_orb.pickup player @s ~ ~ ~ 1 1.2",
        "scoreboard players operation #m pvp = @s pvp.streak", "scoreboard players set #5 pvp 5", "scoreboard players operation #m pvp %= #5 pvp",
        "execute if score @s pvp.streak matches 3 run tellraw @a [{\"selector\":\"@s\",\"color\":\"yellow\"},{\"text\":\" is on a 3 kill streak!\",\"color\":\"gold\"}]",
        "execute if score @s pvp.streak matches 5.. if score #m pvp matches 0 run tellraw @a [{\"selector\":\"@s\",\"color\":\"yellow\"},{\"text\":\" is on a \",\"color\":\"gold\"},"
        "{\"score\":{\"name\":\"@s\",\"objective\":\"pvp.streak\"},\"color\":\"red\",\"bold\":true},{\"text\":\" kill streak!\",\"color\":\"gold\"}]",
    ])

    # ------------------------------------------------------------------ kits
    pick = ["scoreboard players operation #k pvp = @s pvp.kit", "scoreboard players set @s pvp.kit 0",
            f"execute unless entity @s[{LOBBY_BOX}] run return run tellraw @s {{\"text\":\"Pick a kit in the lobby (/spawn).\",\"color\":\"red\"}}",
            "tag @s remove pve.q", "clear @s", "effect clear @s", "function cyber:admin/reset", "scoreboard players set #ok pvp 0"]
    give = []
    for (kid, key, name, color, ic, blurb, items, implants) in KITS:
        pick.append(f"execute if score #k pvp matches {kid} run function {NS}:kit/{key}")
        give.append(f"execute if score @s pve.kit matches {kid} run function {NS}:kit/{key}")
        fn(f"kit/{key}", items + FOOD + [f"function cyber:implant/{i}/kit" for i in implants] + [
            f"tellraw @s [{{\"text\":\"Kit: \",\"color\":\"gray\"}},{{\"text\":\"{name}\",\"color\":\"{color}\",\"bold\":true}},"
            f"{{\"text\":\" (cyberware installed)\",\"color\":\"gray\"}}]",
            *(["tellraw @s {\"text\":\"Double-tap sneak to activate your Operating System implant.\",\"color\":\"dark_gray\"}"]
              if any(i in ("sandy", "berserk") for i in implants) else [])])
    pick += [f"execute if score #k pvp matches 1..{len(KITS)} run scoreboard players set #ok pvp 1",
             f"execute if score #k pvp matches 101.. run function {NS}:kit/custom",
             f"execute if score #ok pvp matches 1 run function {NS}:arena/enter",
             f"execute unless score #ok pvp matches 1 run {say('@s', 'That kit no longer exists.', 'red')}"]
    fn("kit/pick", pick)
    # admin-made kits are given by the mod ("pvpkit give <id>", ids 101+)
    fn("kit/custom", ["execute store result storage pvp:tmp k int 1 run scoreboard players get #k pvp", f"function {NS}:kit/custom_give with storage pvp:tmp"])
    fn("kit/custom_give", ["$execute store result score #ok pvp run pvpkit give $(k)"])
    give.append(f"execute if score @s pve.kit matches 101.. run function {NS}:kit/custom_pve")
    fn("kit/give_pve", give)
    fn("kit/custom_pve", ["execute store result storage pvp:tmp k int 1 run scoreboard players get @s pve.kit", f"function {NS}:kit/custom_give with storage pvp:tmp"])

    enter = ["execute store result score #r pvp run random value 1..%d" % len(SPAWNS)]
    for n, (dx, dz, yaw) in enumerate(SPAWNS, 1):
        enter.append(f"execute if score #r pvp matches {n} run tp @s {ACX + dx + 0.5} {AY + 1} {ACZ + dz + 0.5} {yaw} 0")
    enter += ["effect give @s minecraft:resistance 3 4 true", "scoreboard players set @s pvp.ct 0",
              "title @s title {\"text\":\"FIGHT\",\"color\":\"red\",\"bold\":true}",
              "playsound minecraft:block.beacon.power_select player @s ~ ~ ~ 1 1.4"]
    fn("arena/enter", enter)

    npc_adv("npc", "pvp.npc", "kits")
    npc_adv("pvenpc", "pvp.pvenpc", "pve")
    npc_adv("shopnpc", "pvp.shopnpc", "pve_shop")

    build_pve()

    # ------------------------------------------------------------------ admin: build the lobby + arenas (chunks must be loaded)
    holo = lambda y, z, text, scale=1: (f"summon minecraft:text_display 0.5 {y} {z} {{Tags:[\"pvp.holo\"],billboard:\"center\",background:0,"
                                        f"transformation:{{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[{scale}f,{scale}f,{scale}f]}},"
                                        f"text:{tj(text)}}}")
    fn("admin/place_npc", [
        *npc("pvp.npc", KIT_NPC, "⚔ Kit Dealer ⚔", "aqua", "weaponsmith", "snow"),
        *npc("pvp.pvenpc", PVE_NPC, "☣ Outbreak ☣", "green", "cleric", "swamp"),
        "kill @e[tag=pvp.holo]",
        holo(LOBBY_Y + 6, -LOBBY_R + 1.5, {"text": "CRISPY PVP", "color": "aqua", "bold": True}, 3),
        holo(LOBBY_Y + 4.6, -LOBBY_R + 1.5, [{"text": "Kit Dealer: ", "color": "aqua"}, {"text": "PvP arena", "color": "gray"},
                                              {"text": "   Outbreak: ", "color": "green"}, {"text": "waves of mobs, solo or team", "color": "gray"},
                                              {"text": "\nCustom enchants + cyberware in every kit · /spawn to return", "color": "dark_gray"}]),
    ])
    L, Y = LOBBY_R, LOBBY_Y
    lobby = [f"fill {-L} {Y} {-L} {L} {Y} {L} minecraft:black_concrete",
             f"fill {-L} {Y} 0 {L} {Y} 0 minecraft:cyan_concrete", f"fill 0 {Y} {-L} 0 {Y} {L} minecraft:magenta_concrete",
             f"fill {-L} {Y + 1} {-L} {L} {Y + 1} {L} minecraft:polished_blackstone_wall outline",
             f"fill {-L + 1} {Y + 1} {-L + 1} {L - 1} {Y + 30} {L - 1} minecraft:air"]
    for a in (-L, L):
        lobby += [f"fill {a} {Y} {-L} {a} {Y} {L} minecraft:light_blue_concrete", f"fill {-L} {Y} {a} {L} {Y} {a} minecraft:light_blue_concrete"]
    for a in (-L + 1, 0, L - 1):
        for b in (-L + 1, 0, L - 1):
            lobby.append(f"setblock {a} {Y} {b} minecraft:sea_lantern")
    B = L + 1   # invisible walls so nobody falls off
    lobby += [f"fill {-B} {Y + 1} {-B} {B} {Y + 15} {-B} minecraft:barrier", f"fill {-B} {Y + 1} {B} {B} {Y + 15} {B} minecraft:barrier",
              f"fill {-B} {Y + 1} {-B} {-B} {Y + 15} {B} minecraft:barrier", f"fill {B} {Y + 1} {-B} {B} {Y + 15} {B} minecraft:barrier"]
    fn("admin/build_lobby", lobby + [f"function {NS}:admin/place_npc"])

    x1, x2, z1, z2 = ACX - AR, ACX + AR, ACZ - AR, ACZ + AR
    ar = [f"fill {x1} {AY + 1 + k} {z1} {x2} {AY + 5 + k} {z2} minecraft:air" for k in range(0, 30, 5)]   # fill is capped at 32768 blocks
    ar.append(f"fill {x1} {AY} {z1} {x2} {AY} {z2} minecraft:black_concrete")
    for k in range(-AR, AR + 1, 6):
        ar += [f"fill {ACX + k} {AY} {z1} {ACX + k} {AY} {z2} minecraft:gray_concrete", f"fill {x1} {AY} {ACZ + k} {x2} {AY} {ACZ + k} minecraft:gray_concrete"]
    for i in range(-AR, AR + 1, 6):
        for j in range(-AR, AR + 1, 6):
            ar.append(f"setblock {ACX + i} {AY} {ACZ + j} minecraft:sea_lantern")
    ar += walls(ACX, ACZ, AR, "black_concrete", "cyan_concrete")
    for (bx1, bz1, bx2, bz2, h, stripe, hollow) in BUILDINGS:
        X1, X2, Q1, Q2 = ACX + bx1, ACX + bx2, ACZ + bz1, ACZ + bz2
        ar.append(f"fill {X1} {AY + 1} {Q1} {X2} {AY + h} {Q2} minecraft:black_concrete" + (" hollow" if hollow else ""))
        ar.append(f"fill {X1} {AY + h} {Q1} {X2} {AY + h} {Q2} minecraft:{stripe}_concrete outline")
        if hollow:   # 3-wide, 2-high doorway in the middle of every wall, a light inside
            mx, mz = (X1 + X2) // 2, (Q1 + Q2) // 2
            ar += [f"fill {mx - 1} {AY + 1} {Q1} {mx + 1} {AY + 2} {Q1} minecraft:air", f"fill {mx - 1} {AY + 1} {Q2} {mx + 1} {AY + 2} {Q2} minecraft:air",
                   f"fill {X1} {AY + 1} {mz - 1} {X1} {AY + 2} {mz + 1} minecraft:air", f"fill {X2} {AY + 1} {mz - 1} {X2} {AY + 2} {mz + 1} minecraft:air",
                   f"setblock {mx} {AY} {mz} minecraft:sea_lantern"]
    fn("admin/build_arena", ar)
    fn("admin/build", [f"function {NS}:admin/build_lobby", f"function {NS}:admin/build_arena", f"function {NS}:admin/build_pve", f"function {NS}:admin/build_room"])
    build_room()


def build_room():
    """Sealed admin room under the lobby. Ops: /function pvp:admin/room (in, creative), /function pvp:admin/leave."""
    Y = ROOM_Y
    chests = []   # (label, colour, list of item commands: ("book", id, lvl) or ("loot", key))
    for group, color in (("Melee", "red"), ("Ranged", "green"), ("Tools", "yellow"), ("Armor", "aqua")):
        books = [("book", e["id"], e["max"]) for e in ENCHANTS if e["group"] == group]
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
                            f"[minecraft:stored_enchantments={{\"crispy_enchants:{it[1]}\":{it[2]}}}]")
            else:
                fill.append(f"loot replace block {x} {Y + 1} {z} container.{slot} loot cyber:item/{it[1]}")
    fn("admin/build_room", b + [f"function {NS}:admin/fill_room"])
    fn("admin/fill_room", fill + [say("@s", "Admin room chests refilled.", "gold")])
    fn("admin/room", ["tag @s add pvp.admin", "gamemode creative @s", "function cyber:admin/reset", f"tp @s 0.5 {Y + 1} 0.5 180 0",
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


def build_pve():
    P = f"{NS}:pve"
    state_names = "0 idle, 1 countdown, 2 wave running, 3 break between waves"
    fn("pve/tick", [
        f"# #state pve: {state_names}",
        "scoreboard players enable @a pve.join", "scoreboard players enable @a pve.buy",
        f"execute as @a[scores={{pve.join=1..}}] at @s run function {P}/join",
        f"execute as @a[scores={{pve.buy=1..}}] at @s run function {P}/buy",
        f"execute as @a[tag=pve.in,scores={{pve.k=1..}}] run function {P}/points",
        f"execute if score #state pve matches 0 if entity @a[tag=pve.q] run function {P}/countdown_start",
        f"execute if score #state pve matches 1 run function {P}/countdown_tick",
        f"execute if score #state pve matches 2 run function {P}/wave_tick",
        f"execute if score #state pve matches 3 run function {P}/break_tick",
    ])
    fn("pve/second", [
        "scoreboard players set @a[tag=!pve.in] pve.k 0",
        f"execute if score #state pve matches 2..3 unless entity @a[tag=pve.in,tag=!pve.down] run function {P}/game_over",
        # downed spectators stay above the arena
        f"execute as @a[tag=pve.down] unless entity @s[{PVE_BOX}] run tp @s {PCX + 0.5} {AY + 12} {PCZ + 0.5}",
        f"kill @e[type=minecraft:item,{PVE_BOX}]", f"kill @e[type=minecraft:experience_orb,{PVE_BOX}]",
        # spiders that climb the walls get pulled back down
        f"execute as @e[tag=pve.mob,x={PCX - PR - 1},y={AY + 8},z={PCZ - PR - 1},dx={2 * PR + 2},dy=30,dz={2 * PR + 2}] at @s run tp @s {PCX + 0.5} {AY + 1} {PCZ + 0.5}",
        "execute store result bossbar pvp:boss value run data get entity @n[tag=pve.boss] Health",
        "execute unless entity @e[tag=pve.boss] run bossbar set pvp:boss visible false",
    ])

    # joining: pve.join = kit id (99 = leave the queue)
    fn("pve/join", [
        "scoreboard players operation #j pve = @s pve.join", "scoreboard players set @s pve.join 0",
        "execute if score #j pve matches 99 run tag @s remove pve.q",
        f"execute if score #j pve matches 99 run return run {say('@s', 'You left the Outbreak queue.', 'yellow')}",
        f"execute if entity @s[tag=pve.in] run return run {say('@s', 'You are already in the Outbreak.', 'red')}",
        f"execute unless entity @s[{LOBBY_BOX}] run return run {say('@s', 'Join the Outbreak from the lobby (/spawn).', 'red')}",
        f"execute unless score #j pve matches 1..{len(KITS)} unless score #j pve matches 101..199 run return 0",
        "scoreboard players operation @s pve.kit = #j pve", "tag @s add pve.q",
        f"execute if score #state pve matches 2..3 run return run {say('@s', 'Outbreak in progress: you will drop in at the next wave break.', 'green')}",
        say("@s", "Queued for the Outbreak. More players can join during the countdown.", "green"),
    ])
    fn("pve/countdown_start", ["scoreboard players set #state pve 1", "scoreboard players set #timer pve 200",
                               "playsound minecraft:block.note_block.pling player @a[tag=pve.q] ~ ~ ~ 1 0.8"])
    fn("pve/countdown_tick", [
        "execute unless entity @a[tag=pve.q] run return run scoreboard players set #state pve 0",
        "scoreboard players remove #timer pve 1",
        "scoreboard players operation #s pve = #timer pve", "scoreboard players operation #s pve /= #20 pve",
        "title @a[tag=pve.q] actionbar [{\"text\":\"☣ Outbreak starts in \",\"color\":\"green\"},{\"score\":{\"name\":\"#s\",\"objective\":\"pve\"},\"color\":\"white\"},{\"text\":\"s\",\"color\":\"green\"}]",
        f"execute if score #timer pve matches ..0 run function {P}/start",
    ])
    fn("pve/start", [
        "scoreboard players set #wave pve 0", "kill @e[tag=pve.mob]",
        "scoreboard players set #state pve 3", "scoreboard players set #timer pve 100",
        f"execute as @a[tag=pve.q] run function {P}/enter",
        "tellraw @a[tag=pve.in] {\"text\":\"☣ The Outbreak has begun. Survive as long as you can.\",\"color\":\"green\"}",
    ])
    pts_spawn = ["execute store result score #r pve run random value 1..%d" % len(PVE_SPAWNS)]
    for n, (dx, dz, yaw) in enumerate(PVE_SPAWNS, 1):
        pts_spawn.append(f"execute if score #r pve matches {n} run tp @s {PCX + dx + 0.5} {AY + 1} {PCZ + dz + 0.5} {yaw} 0")
    fn("pve/tp_spawn", pts_spawn)
    fn("pve/enter", [   # as a queued player: into the run with their kit and 500 points
        "tag @s remove pve.q", "tag @s add pve.in", "team join pve @s",
        "scoreboard players set @s pve.pts 500", "scoreboard players set @s pve.k 0",
        "clear @s", "effect clear @s", "function cyber:admin/reset", "gamemode adventure @s",
        f"function {NS}:kit/give_pve", f"function {P}/tp_spawn",
        "title @s title {\"text\":\"☣ OUTBREAK\",\"color\":\"dark_green\",\"bold\":true}",
        "playsound minecraft:entity.zombie_villager.converted player @s ~ ~ ~ 1 0.7",
    ])
    fn("pve/break_tick", ["scoreboard players remove #timer pve 1", f"execute if score #timer pve matches ..0 run function {P}/next_wave"])
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
        f"execute as @a[tag=pve.down] run function {P}/revive",
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
        "scoreboard players set #state pve 3", "scoreboard players set #timer pve 200",
        "scoreboard players operation #b pve = #wave pve", "scoreboard players operation #b pve *= #100 pve",
        "scoreboard players operation @a[tag=pve.in,tag=!pve.down] pve.pts += #b pve",
        "tellraw @a[tag=pve.in] [{\"text\":\"☣ Wave \",\"color\":\"green\"},{\"score\":{\"name\":\"#wave\",\"objective\":\"pve\"},\"color\":\"white\"},"
        "{\"text\":\" cleared! +\",\"color\":\"green\"},{\"score\":{\"name\":\"#b\",\"objective\":\"pve\"},\"color\":\"gold\"},{\"text\":\" points. Next wave in 10 s.\",\"color\":\"green\"}]",
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
    for (mw, roll, typ, extra) in pool:
        choose.append(f"execute if score #p pve matches 0 if score #wave pve matches {mw}.. if score #r pve matches ..{roll} run "
                      f"function {P}/type {{type:\"{typ}\",extra:'{extra}'}}")
    choose.append(f"execute if score #p pve matches 0 run function {P}/type {{type:\"zombie\",extra:''}}")
    choose.append("execute store result score #r pve run random value 1..%d" % len(MOB_POINTS))
    for n, (dx, dz) in enumerate(MOB_POINTS, 1):
        choose.append(f"execute if score #r pve matches {n} run data modify storage pvp:pve m merge value {{x:{PCX + dx + 0.5},y:{AY + 1},z:{PCZ + dz + 0.5}}}")
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
        f"summon minecraft:zombie {PCX + 0.5} {AY + 1} {PCZ + 18.5} {{Tags:[\"pve.mob\",\"pve.boss\",\"pve.new\"],PersistenceRequired:1b,CanPickUpLoot:0b,"
        "DeathLootTable:\"minecraft:empty\",IsBaby:0b,CustomName:{\"text\":\"Abomination\",\"color\":\"dark_red\",\"bold\":true},CustomNameVisible:1b,"
        "attributes:[{id:\"minecraft:follow_range\",base:64d},{id:\"minecraft:scale\",base:2.0d},{id:\"minecraft:max_health\",base:150d},"
        "{id:\"minecraft:attack_damage\",base:9d},{id:\"minecraft:knockback_resistance\",base:0.8d},{id:\"minecraft:movement_speed\",base:0.26d}]}",
        f"execute as @e[tag=pve.new] run function {P}/scale with storage pvp:pve s",
        "execute store result bossbar pvp:boss max run data get entity @n[tag=pve.boss] Health",
        "bossbar set pvp:boss players @a[tag=pve.in]", "bossbar set pvp:boss visible true",
        "tellraw @a[tag=pve.in] {\"text\":\"☣ An Abomination has entered the arena!\",\"color\":\"dark_red\",\"bold\":true}",
        "execute as @a[tag=pve.in] at @s run playsound minecraft:entity.wither.spawn player @s ~ ~ ~ 0.5 0.8",
    ])
    fn("pve/points", ["scoreboard players operation #k pve = @s pve.k", "scoreboard players operation #k pve *= #100 pve",
                      "scoreboard players operation @s pve.pts += #k pve", "scoreboard players set @s pve.k 0"])

    # going down / coming back
    fn("pve/downed", [
        "tag @s add pve.down", "gamemode spectator @s", "attribute @s minecraft:max_health modifier remove pvp:jug", "tag @s remove pve.jug", "tag @s remove pve.cola",
        f"tp @s {PCX + 0.5} {AY + 12} {PCZ + 0.5}",
        "title @s title {\"text\":\"DOWN\",\"color\":\"dark_red\",\"bold\":true}",
        "title @s subtitle {\"text\":\"You're back at the start of the next wave\",\"color\":\"gray\"}",
        "tellraw @a[tag=pve.in] [{\"selector\":\"@s\",\"color\":\"red\"},{\"text\":\" went down!\",\"color\":\"gray\"}]",
    ])
    fn("pve/revive", [
        "tag @s remove pve.down", "gamemode adventure @s", "clear @s", "effect clear @s", "function cyber:admin/reset",
        f"function {NS}:kit/give_pve", f"function {P}/tp_spawn", say("@s", "You're back in the fight!", "green"),
    ])
    fn("pve/game_over", [
        "scoreboard players set #state pve 0", "kill @e[tag=pve.mob]", "bossbar set pvp:boss visible false",
        "tellraw @a[tag=pve.in] [{\"text\":\"☣ Outbreak over. You reached wave \",\"color\":\"red\"},{\"score\":{\"name\":\"#wave\",\"objective\":\"pve\"},\"color\":\"white\",\"bold\":true},{\"text\":\".\",\"color\":\"red\"}]",
        "execute as @a[tag=pve.in] if score #wave pve > @s pve.best run scoreboard players operation @s pve.best = #wave pve",
        "execute if score #wave pve > #record pve run tellraw @a [{\"text\":\"☣ New Outbreak record: wave \",\"color\":\"gold\"},{\"score\":{\"name\":\"#wave\",\"objective\":\"pve\"},\"color\":\"white\",\"bold\":true},"
        "{\"text\":\" by \",\"color\":\"gold\"},{\"selector\":\"@a[tag=pve.in]\",\"color\":\"yellow\"}]",
        "execute if score #wave pve > #record pve run scoreboard players operation #record pve = #wave pve",
        f"execute as @a[tag=pve.in] run function {NS}:to_lobby",
        "scoreboard players set #wave pve 0",
    ])

    # Arsenal shop
    buy = ["scoreboard players operation #n pve = @s pve.buy", "scoreboard players set @s pve.buy 0",
           f"execute unless entity @s[tag=pve.in,tag=!pve.down] run return run {say('@s', 'The Arsenal only serves Outbreak survivors.', 'red')}"]
    for (sid, name, color, ic, cost, lore, cmds, once) in SHOP:
        buy.append(f"execute if score #n pve matches {sid} run function {P}/shop/{sid}")
        fn(f"pve/shop/{sid}", [
            f"execute if entity @s[tag={once}] run return run {say('@s', f'You already have {name}.', 'red')}" if once else None,
            f"execute if score @s pve.pts matches ..{cost - 1} run return run tellraw @s [{{\"text\":\"{name} costs {cost} points (you have \",\"color\":\"red\"}},"
            "{\"score\":{\"name\":\"@s\",\"objective\":\"pve.pts\"},\"color\":\"white\"},{\"text\":\").\",\"color\":\"red\"}]",
            f"scoreboard players remove @s pve.pts {cost}", *cmds, f"tag @s add {once}" if once else None,
            f"tellraw @s [{{\"text\":\"Bought \",\"color\":\"green\"}},{{\"text\":\"{name}\",\"color\":\"{color}\"}}]",
            "playsound minecraft:entity.villager.yes neutral @s ~ ~ ~ 1 0.8"])
    fn("pve/buy", buy)
    box = ["execute store result score #r pve run random value 1..%d" % len(BOX),
           "playsound minecraft:block.chest.open player @s ~ ~ ~ 1 0.8"]
    for n, b in enumerate(BOX, 1):
        fn(f"pve/box/{n}", b.split("\n"))
        box.append(f"execute if score #r pve matches {n} run function {P}/box/{n}")
    fn("pve/box", box)

    # build the Outbreak arena
    rnd = random.Random(7)
    x1, x2, z1, z2 = PCX - PR, PCX + PR, PCZ - PR, PCZ + PR
    a = [f"fill {x1} {AY + 1 + k} {z1} {x2} {AY + 5 + k} {z2} minecraft:air" for k in range(0, 30, 5)]
    a.append(f"fill {x1} {AY} {z1} {x2} {AY} {z2} minecraft:deepslate_tiles")
    for cx in range(x1, x2 + 1, 5):
        for cz in range(z1, z2 + 1, 5):
            b = rnd.choice(["cracked_deepslate_tiles", "cobbled_deepslate", "mossy_cobblestone", "deepslate_tiles", "tuff_bricks", "coarse_dirt"])
            a.append(f"fill {cx} {AY} {cz} {min(cx + 4, x2)} {AY} {min(cz + 4, z2)} minecraft:{b}")
    for i in range(-PR + 2, PR - 1, 9):
        for j in range(-PR + 2, PR - 1, 9):
            a.append(f"setblock {PCX + i} {AY} {PCZ + j} minecraft:{rnd.choice(['ochre_froglight', 'verdant_froglight'])}")
    a += walls(PCX, PCZ, PR, "polished_blackstone_bricks", "cracked_polished_blackstone_bricks")
    for (dx, dz) in MOB_POINTS:   # barred windows behind every mob spawn
        wx, wz = PCX + dx, PCZ + dz
        if abs(dx) == 20: wx = PCX + (PR + 1) * (1 if dx > 0 else -1); a.append(f"fill {wx} {AY + 1} {wz - 1} {wx} {AY + 3} {wz + 1} minecraft:iron_bars")
        else: wz = PCZ + (PR + 1) * (1 if dz > 0 else -1); a.append(f"fill {wx - 1} {AY + 1} {wz} {wx + 1} {AY + 3} {wz} minecraft:iron_bars")
    for (rx1, rz1, rx2, rz2, h, blk) in RUINS:
        a.append(f"fill {PCX + rx1} {AY + 1} {PCZ + rz1} {PCX + rx2} {AY + h} {PCZ + rz2} minecraft:{blk}")
        a.append(f"setblock {PCX + rx1} {AY + h + 1} {PCZ + rz1} minecraft:soul_lantern")
        a.append(f"fill {PCX + rx2} {AY + h} {PCZ + rz2} {PCX + rx2} {AY + h} {PCZ + rz2} minecraft:air")   # broken corner
    a += [f"fill {PCX - 1} {AY + 1} {PCZ - 1} {PCX + 1} {AY + 1} {PCZ + 1} minecraft:polished_andesite",   # Arsenal platform
          f"setblock {PCX} {AY + 1} {PCZ} minecraft:lodestone"]
    sx, sy, sz = SHOP_NPC
    a += npc("pvp.shopnpc", (sx, sy, sz), "☣ Arsenal ☣", "green", "", "", 180, mannequin=True)
    fn("admin/build_pve", a)


if __name__ == "__main__":
    OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist"), "crispy_pvp")
    build()
    print(f"built {OUT} ({sum(len(f) for _, _, f in os.walk(OUT))} files)")
