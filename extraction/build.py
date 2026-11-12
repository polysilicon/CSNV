#!/usr/bin/env python3
"""Extraction Zone: builds the crispy_extraction datapack (Fabric 26.2, instance Extraction01).

    python3 build.py <out dir>        -> <out>/crispy_extraction  (zip it into world/datapacks)

Loop: base camp (its own void dimension ez:camp, safe) -> deploy to a random edge of the zone (the overworld around a
village and a pillager outpost) -> loot crates and raiders -> hold an extraction point for EX_HOLD s -> back to camp
with everything you carried. Die, or run out of time, and you lose what you carried (vanilla drops, keep_inventory off).
The stash is the vanilla ender chest (only in camp). Guns are Multiverse's hitscan gun abilities (pvp/abilities.py,
namespace pvp), and need Ammo in your inventory. /trigger truce near another player twice forms a squad; hitting a
squadmate is a betrayal (announced, squad left).
"""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvp"))
import abilities   # noqa: E402

NS = "ez"
PACK_FORMAT = [107, 0], [107, 1]
CAMP = "ez:camp"
RAID_SECS = 25 * 60
EX_HOLD = 30            # seconds on an extraction point
EX_R = 4                # its radius
ZONE_DIM = "lostcities:lostcity"   # The Lost Cities' city dimension (profile "extraction"); the mod turns its chests and spawners into ours
ZONE = (48, 48, 800, 800)          # x, z, dx, dz: centre 448 448 (the zone map's grid), see the mod's Zone.CX/CZ
SPAWN_EVERY = 20        # raider spawner check (s)
CRATE_EVERY = 600       # crate refill (s, counted while loaded)

# POIs: key, name, x, z, radius, crate tier, crates, raider type, raider cap
POIS = [
    ("town", "Old Town", -912, 624, 40, 2, 14, "bandit", 6),
    ("outpost", "Raider Outpost", -384, 240, 32, 3, 10, "raider", 8),
    ("ruins", "Portal Ruins", -576, 304, 24, 2, 6, "infected", 4),
    ("crash", "Crash Site", -760, 430, 24, 1, 6, "infected", 4),
    ("lumber", "Lumber Camp", -980, 300, 24, 1, 5, "infected", 3),
    ("radio", "Radio Hill", -560, 720, 24, 1, 5, "bandit", 3),
]
EXFILS = [("north", "North LZ", -650, 60), ("east", "East Docks", -280, 600), ("sw", "South-West Tunnel", -1010, 800)]
INSERTS = [(-1030, 100), (-1030, 430), (-1030, 700), (-800, 815), (-450, 815), (-270, 330), (-450, 45), (-870, 45)]

# ------------------------------------------------------------------ items
def name(text, color, bold=False): return {"text": text, "color": color, "italic": False, "bold": bold}
def lore(*lines): return [{"text": l, "color": "gray", "italic": False} for l in lines]

def item(id_, nm, color, tag, lines=(), extra=None, bold=False):
    c = {"minecraft:custom_name": name(nm, color, bold), "minecraft:lore": lore(*lines), "minecraft:custom_data": {"ez": tag}}
    c.update(extra or {})
    return {"id": id_, "components": c}

# money is Anarchy's Gold Coin (exactly the same item); the mod condenses 64 into a Coin Bag (mod Coins.java)
CREDIT = {"id": "minecraft:sunflower", "components": {"minecraft:custom_name": {"text": "Gold Coin", "italic": False, "color": "gold", "bold": True},
          "minecraft:lore": [{"text": " -Used for special shop items", "italic": False, "color": "dark_purple"}],
          "minecraft:enchantments": {"minecraft:unbreaking": 1}}}
AMMO = item("minecraft:iron_nugget", "Ammo", "yellow", "ammo", ["Every gun shot uses one round."])
heal = lambda amp, extra=(): {"minecraft:consumable": {"consume_seconds": 1.6, "animation": "bow", "sound": "minecraft:item.armor.equip_leather",
                                                        "has_consume_particles": False,
                                                        "on_consume_effects": [{"type": "minecraft:apply_effects", "effects": [
                                                            {"id": "minecraft:instant_health", "amplifier": amp, "duration": 1}, *extra]}]}}
BANDAGE = item("minecraft:paper", "Bandage", "white", "bandage", ["Hold right-click: heals 2 hearts."], heal(0))
STASH = item("minecraft:barrel", "Stash Crate", "gold", "stash", ["Storage for your plot (27 slots).", "Your bunker holds 4, 7 or 10 by size.",
                                                                 "Break it to move it: you get it back."], bold=True)
MEDKIT = item("minecraft:red_dye", "Medkit", "red", "medkit", ["Hold right-click: heals 4 hearts", "and regenerates for 5 s."],
              heal(1, [{"id": "minecraft:regeneration", "amplifier": 1, "duration": 100}]))
# valuables: key, item, name, colour, sell price (coins)
VALUABLES = [
    ("scrap", "minecraft:redstone", "Scrap Electronics", "gray", 2),
    ("wire", "minecraft:copper_ingot", "Copper Wire", "gold", 3),
    ("pills", "minecraft:sugar", "Painkillers", "white", 4),
    ("crystal", "minecraft:amethyst_shard", "Raw Crystal", "light_purple", 6),
    ("watch", "minecraft:clock", "Gold Watch", "yellow", 9),
    ("goldbar", "minecraft:gold_ingot", "Gold Bar", "gold", 14),
    ("gem", "minecraft:diamond", "Uncut Gem", "aqua", 20),
    ("drive", "minecraft:echo_shard", "Data Drive", "dark_aqua", 28),
    ("blackbox", "minecraft:recovery_compass", "Black Box", "red", 45),
]
VAL = {k: item(i, n, c, k, ["Valuable: sell it to the Broker", f"for {p} coins."]) | {"price": p} for k, i, n, c, p in VALUABLES}

# guns used here, with neutral names (the Multiverse names stay on Multiverse): key, display name, trader price
EZ_GUNS = [("pistol", "Pistol", 20), ("m1911", "M1911", 32), ("mp40", "MP40", 48), ("stakeout", "Pump Shotgun", 56),
           ("stg44", "STG-44", 72), ("olympia", "Double Barrel", 80), ("kar98k", "Kar98k", 96), ("m60", "M60", 112),
           ("amban", "Marksman Rifle", 128)]   # a villager trade asks for at most 64 + 64
for k, nm, _ in EZ_GUNS:
    v = abilities.ABILITIES[k]
    abilities.ABILITIES[k] = (nm, v[1], v[2], v[3], [l.replace("Pack-a-Punch", "upgrade") for l in v[4]], v[5])

def gun(k): return {"id": abilities.BASE, "components": abilities.item_components(k)}
# magazine size and reload time (ticks) per gun
MAGS = {"pistol": (12, 30), "m1911": (8, 30), "mp40": (32, 45), "stakeout": (6, 60), "stg44": (30, 50), "olympia": (2, 40),
        "kar98k": (5, 55), "m60": (75, 110), "amban": (10, 55)}
GUN_NAME = {k: n for k, n, _ in EZ_GUNS}
for k, (cap, rt) in MAGS.items():   # magazine size and reload in the lore
    v = abilities.ABILITIES[k]
    abilities.ABILITIES[k] = (v[0], v[1], v[2], v[3], v[4] + [f"Magazine {cap} · reload {rt / 20:g} s", "Sneak + right-click to reload"], v[5])
AMMO_SEL = 'minecraft:iron_nugget[minecraft:custom_data~{ez:"ammo"}]'

# ------------------------------------------------------------------ output helpers
OUT = None
def w(path, text):
    p = os.path.join(OUT, path); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f: f.write(text if text.endswith("\n") else text + "\n")
def wj(path, obj): w(path, json.dumps(obj, indent=1, ensure_ascii=False))
def tj(o): return json.dumps(o, ensure_ascii=False, separators=(",", ":"))

def ammo_gate(name, lines):
    """Guns here have magazines (ez.m_<gun>): a shot uses a round from the magazine; an empty magazine, or sneak +
    right-click, reloads from the Ammo in your inventory (ez.rl ticks, no shooting meanwhile). The gun item is still
    handed back after every use."""
    key = name.rsplit("/", 1)[1]
    if name.startswith("ability/use/") and key in MAGS:
        cap = MAGS[key][0]
        i = lines.index("scoreboard players set @s pvp.rgt 3") + 1
        lines = lines[:i] + [
            f"scoreboard players set @s ez.cap {cap}",   # Extended Magazine (workbench): +50%
            f"execute if items entity @s weapon.mainhand *[minecraft:custom_data~{{ezmod:{{mag:1b}}}}] run scoreboard players set @s ez.cap {cap + cap // 2}",
            'execute if score @s ez.rl matches 1.. run return run title @s actionbar {"text":"⟳ Reloading...","color":"yellow"}',
            f"execute if predicate {NS}:sneaking if score @s ez.m_{key} < @s ez.cap run return run function {NS}:gun/reload_{key}",
            f"execute unless score @s ez.m_{key} matches 1.. run return run function {NS}:gun/reload_{key}",
            f"scoreboard players remove @s ez.m_{key} 1"] + lines[i:] + [f"function {NS}:gun/hud_{key}"]
    return lines

def fn(name, lines, ns=None):
    ns = ns or NS
    if ns == "pvp": lines = ammo_gate(name, lines)
    w(f"data/{ns}/function/{name}.mcfunction", "\n".join(l for l in lines if l is not None))
def pfn(name, lines): fn(name, lines, "pvp")   # for abilities.build, which writes into pvp:
def pwj(path, obj): wj(path, obj)

def snbt(o):
    if isinstance(o, bool): return "true" if o else "false"
    if isinstance(o, (int, float)): return str(o)
    if isinstance(o, str): return json.dumps(o, ensure_ascii=False)
    if isinstance(o, list): return "[" + ",".join(snbt(x) for x in o) + "]"
    return "{" + ",".join(f"{json.dumps(k) if not k.replace('_', '').isalnum() else k}:{snbt(v)}" for k, v in o.items()) + "}"

def stack(it, n=1): return {"id": it["id"], "count": n, "components": it["components"]}
def give(it, n=1): return f"give @s {it['id']}[{','.join(f'{k}={snbt(v)}' for k, v in it['components'].items())}] {n}"
def say(sel, text, color="gray"): return f"tellraw {sel} {tj({'text': text, 'color': color})}"
def title(sel, t, sub, color="gold"): return [f"title {sel} title {tj(name(t, color, True))}", f"title {sel} subtitle {tj({'text': sub, 'color': 'gray'})}"]

# ------------------------------------------------------------------ loot
def entry(it, w_, lo=1, hi=1):
    fx = [{"function": "minecraft:set_components", "components": it["components"]}]
    if hi > 1: fx.append({"function": "minecraft:set_count", "count": {"min": lo, "max": hi}})
    return {"type": "minecraft:item", "name": it["id"], "weight": w_, "functions": fx}
def ventry(id_, w_, lo=1, hi=1, ench=None):
    fx = [{"function": "minecraft:set_count", "count": {"min": lo, "max": hi}}] if hi > 1 else []
    return {"type": "minecraft:item", "name": id_, "weight": w_, "functions": fx}
def gentry(k, w_): return {"type": "minecraft:loot_table", "value": f"pvp:ability/{k}", "weight": w_}

TIERS = {
    1: {"rolls": (3, 5), "entries": [entry(AMMO, 30, 4, 12), entry(BANDAGE, 14, 1, 2), entry(CREDIT, 16, 1, 6),
         entry(VAL["scrap"], 18, 1, 3), entry(VAL["wire"], 12, 1, 2), entry(VAL["pills"], 8), ventry("minecraft:bread", 10, 1, 3),
         ventry("minecraft:leather_chestplate", 4), ventry("minecraft:chainmail_helmet", 3), gentry("pistol", 3), gentry("m1911", 1)]},
    2: {"rolls": (4, 6), "entries": [entry(AMMO, 28, 8, 20), entry(BANDAGE, 10, 1, 3), entry(MEDKIT, 6), entry(CREDIT, 14, 3, 12),
         entry(VAL["wire"], 10, 1, 3), entry(VAL["pills"], 8, 1, 2), entry(VAL["crystal"], 8), entry(VAL["watch"], 6), entry(VAL["goldbar"], 3),
         ventry("minecraft:cooked_beef", 8, 1, 3), ventry("minecraft:iron_helmet", 3), ventry("minecraft:iron_chestplate", 2),
         ventry("minecraft:iron_leggings", 2), gentry("m1911", 4), gentry("mp40", 3), gentry("stakeout", 3), gentry("stg44", 1)]},
    3: {"rolls": (5, 7), "entries": [entry(AMMO, 24, 12, 32), entry(MEDKIT, 10, 1, 2), entry(CREDIT, 12, 8, 24),
         entry(VAL["watch"], 8), entry(VAL["goldbar"], 7), entry(VAL["gem"], 5), entry(VAL["drive"], 4), entry(VAL["blackbox"], 1),
         ventry("minecraft:iron_chestplate", 4), ventry("minecraft:diamond_helmet", 2), ventry("minecraft:diamond_chestplate", 1),
         gentry("stg44", 4), gentry("olympia", 3), gentry("kar98k", 3), gentry("m60", 2), gentry("amban", 1), ventry("minecraft:golden_apple", 3)]},
}
MOB_LOOT = {
    "infected": [(entry(AMMO, 1, 1, 4), 0.5), (entry(VAL["scrap"], 1), 0.3), (entry(CREDIT, 1, 1, 3), 0.3)],
    "bandit": [(entry(AMMO, 1, 3, 8), 0.8), (entry(CREDIT, 1, 2, 6), 0.5), (entry(VAL["watch"], 1), 0.08), (entry(BANDAGE, 1), 0.3)],
    "raider": [(entry(AMMO, 1, 4, 10), 0.9), (entry(CREDIT, 1, 3, 10), 0.6), (entry(VAL["goldbar"], 1), 0.08),
               (entry(VAL["drive"], 1), 0.03), (entry(MEDKIT, 1), 0.2)],
}
def held_gun(k): return {"id": abilities.BASE, "count": 1, "components": {"minecraft:item_model": f"minecraft:{abilities.ABILITIES[k][2]}"}}
# Soldiers: a modern-soldier player head (textures from minecraft-heads.com: "Desert Soldier", "Camouflaged Soldier",
# "Elite Soldier") and dyed leather with an armour trim for the pattern. Skeleton bodies, since illagers can't show
# armour; Silent, so they don't rattle like bones. Nothing they wear drops.
SOLDIER_HEADS = {
 "desert": "eyJ0ZXh0dXJlcyI6eyJTS0lOIjp7InVybCI6Imh0dHA6Ly90ZXh0dXJlcy5taW5lY3JhZnQubmV0L3RleHR1cmUvOWY2MGFjNWFmNmQzYjNkN2VhNGQ4MmRmZTY3NjRhZTg4OTkxMzUwMTMwYmUzYTYxYjhiY2E2YTFkZTJkZTczZSJ9fX0=",
 "camo": "eyJ0ZXh0dXJlcyI6eyJTS0lOIjp7InVybCI6Imh0dHA6Ly90ZXh0dXJlcy5taW5lY3JhZnQubmV0L3RleHR1cmUvZWI4NDE4YzQ2MWY2M2Q2YWFkMzkzMmE2MzlmY2UzZmVjMjI3YTM3NzRhNTliODUxZmZiZTY1NTg3NGViNzkxIn19fQ==",
 "elite": "eyJ0ZXh0dXJlcyI6eyJTS0lOIjp7InVybCI6Imh0dHA6Ly90ZXh0dXJlcy5taW5lY3JhZnQubmV0L3RleHR1cmUvMzMzNjk5ZGFiNGVkOWIyZGNlZDZiZGE3OTA5OTRhYzIzNDNlNTEyNjEyNjlkZGE0Mzk4YzUyOTdlMjI4NzEifX19"
}
def soldier(head, chest, legs, boots, trim_pattern, trim_mat, hand):
    def piece(i, color): return {"id": f"minecraft:leather_{i}", "count": 1, "components": {"minecraft:dyed_color": color,
                                 "minecraft:trim": {"material": f"minecraft:{trim_mat}", "pattern": f"minecraft:{trim_pattern}"}}}
    return {"equipment": {"mainhand": hand, "head": {"id": "minecraft:player_head", "count": 1, "components": {
                "minecraft:profile": {"properties": [{"name": "textures", "value": SOLDIER_HEADS[head]}]}}},
                "chest": piece("chestplate", chest), "legs": piece("leggings", legs), "feet": piece("boots", boots)},
            "drop_chances": {"mainhand": 0.0, "head": 0.0, "chest": 0.0, "legs": 0.0, "feet": 0.0}, "Silent": True}
RAIDERS = {   # type: (mob, summon NBT, extra tags, loot table). Gunners (ez.gunner) shoot hitscan, see ai/gunner
    "infected": ("minecraft:zombie", {"CustomName": name("Infected", "dark_green"), "equipment": {"head": {"id": "minecraft:leather_helmet", "count": 1}},
                                      "drop_chances": {"head": 0.0}}, [], "infected"),
    "bandit": ("minecraft:skeleton", {"CustomName": name("Bandit Gunner", "red"),
        **soldier("desert", 0xA68A5B, 0xBFA270, 0x6B5A3E, "dune", "copper", held_gun("mp40"))}, ["ez.gunner", "ez.g_bandit"], "bandit"),
    "raider": ("minecraft:skeleton", {"CustomName": name("Raider", "dark_red"),
        **soldier("camo", 0x4B5320, 0x556B2F, 0x3B2F1E, "wild", "emerald", {"id": "minecraft:iron_axe", "count": 1})}, [], "raider"),
    "rifleman": ("minecraft:skeleton", {"CustomName": name("Raider Rifleman", "dark_red"),
        **soldier("elite", 0x262626, 0x333333, 0x1A1A1A, "silence", "netherite", held_gun("stg44"))}, ["ez.gunner", "ez.g_rifle"], "raider"),
}
GUNNERS = {"bandit": (3, 30, 0.35), "rifle": (4, 38, 0.25), "boss": (5, 12, 0.2)}   # damage, ticks between shots, miss chance
AI_RANGE = 28

def loot_tables():
    for t, d in TIERS.items():
        wj(f"data/{NS}/loot_table/crate/t{t}.json", {"type": "minecraft:chest", "pools": [
            {"rolls": {"min": d["rolls"][0], "max": d["rolls"][1]}, "entries": d["entries"]}]})
    # 1.1.0: events and the boss (mod Events.java / Boss.java)
    pool = lambda rolls, entries: {"rolls": rolls, "entries": entries}
    wj(f"data/{NS}/loot_table/event/supply.json", {"type": "minecraft:chest", "pools": [
        pool({"min": 6, "max": 8}, TIERS[3]["entries"]), pool(1, [entry(MEDKIT, 1, 2, 3)]), pool(1, [entry(AMMO, 1, 32, 48)])]})
    wj(f"data/{NS}/loot_table/event/heli.json", {"type": "minecraft:chest", "pools": [
        pool({"min": 4, "max": 6}, TIERS[3]["entries"]),
        pool(1, [entry(VAL["blackbox"], 1), entry(VAL["drive"], 2, 1, 2), entry(VAL["gem"], 2, 1, 2)])]})
    wj(f"data/{NS}/loot_table/mob/boss.json", {"type": "minecraft:entity", "pools": [
        pool(1, [entry(CREDIT, 1, 40, 70)]), pool(1, [entry(VAL["blackbox"], 1, 1, 2)]), pool(1, [entry(VAL["gem"], 1, 2, 4)]),
        pool(1, [entry(VAL["drive"], 1, 1, 3)]), pool(1, [entry(VAL["goldbar"], 1, 2, 4)]), pool(1, [entry(MEDKIT, 1, 1, 2)]),
        {"rolls": 1, "entries": [gentry("m60", 1), gentry("amban", 1)], "conditions": [{"condition": "minecraft:random_chance", "chance": 0.45}]}]})
    for k, drops in MOB_LOOT.items():
        wj(f"data/{NS}/loot_table/mob/{k}.json", {"type": "minecraft:entity", "pools": [
            {"rolls": 1, "entries": [e], "conditions": [{"condition": "minecraft:random_chance", "chance": c}]} for e, c in drops]})

# ------------------------------------------------------------------ traders (chest menus in the mod; config/crispy_extraction/shops.json)
def sn(st): return snbt(st)
def buy(it, price, n=1): return {"item": sn(stack(it, n) if "components" in it else {"id": it["id"], "count": n}), "price": price}
def vbuy(id_, price, n=1): return {"item": sn({"id": id_, "count": n}), "price": price}
def gbuy(k, price): return {"item": sn({"id": abilities.BASE, "count": 1, "components": abilities.item_components(k)}), "price": price}
def sells(rate=1.0): return [{"key": k, "item": sn(stack(VAL[k])), "price": max(1, int(VAL[k]["price"] * rate))} for k, *_ in VALUABLES]
SHOPS = {
    "quartermaster": {"title": "Quartermaster", "buy": [buy(AMMO, 4, 16), buy(BANDAGE, 3, 2), buy(MEDKIT, 8), gbuy("pistol", 20), gbuy("m1911", 35),
                      gbuy("mp40", 60), gbuy("stakeout", 70), gbuy("stg44", 110), vbuy("minecraft:leather_helmet", 4), vbuy("minecraft:leather_chestplate", 6),
                      vbuy("minecraft:iron_helmet", 14), vbuy("minecraft:iron_chestplate", 24), vbuy("minecraft:iron_leggings", 20),
                      vbuy("minecraft:iron_boots", 12), vbuy("minecraft:cooked_beef", 2, 8), vbuy("minecraft:golden_apple", 25)], "sell": []},
    "fence": {"title": "The Broker", "buy": [], "sell": sells()},
    "builder": {"title": "Builder", "buy": [buy(STASH, 25), vbuy("minecraft:oak_planks", 6, 32),
                vbuy("minecraft:spruce_planks", 6, 32), vbuy("minecraft:stone_bricks", 6, 32), vbuy("minecraft:bricks", 8, 32),
                vbuy("minecraft:deepslate_tiles", 8, 32), vbuy("minecraft:smooth_quartz", 10, 32), vbuy("minecraft:glass", 6, 16),
                vbuy("minecraft:oak_log", 5, 16), vbuy("minecraft:oak_stairs", 5, 16), vbuy("minecraft:oak_slab", 4, 16),
                vbuy("minecraft:oak_door", 3), vbuy("minecraft:lantern", 5, 8), vbuy("minecraft:white_wool", 4, 16), vbuy("minecraft:red_carpet", 4, 16),
                vbuy("minecraft:white_bed", 8), vbuy("minecraft:crafting_table", 3), vbuy("minecraft:item_frame", 2, 4), vbuy("minecraft:armor_stand", 5),
                vbuy("minecraft:flower_pot", 2, 4), vbuy("minecraft:poppy", 1, 4), vbuy("minecraft:oak_sapling", 2, 2), vbuy("minecraft:bookshelf", 6, 4),
                vbuy("minecraft:painting", 3)], "sell": []},
    # inside the zone: worth carrying cash in
    "smuggler": {"title": "The Smuggler", "buy": [buy(AMMO, 7, 16), buy(BANDAGE, 5, 2), buy(MEDKIT, 12), gbuy("m1911", 50), gbuy("stakeout", 90),
                 vbuy("minecraft:golden_apple", 35)], "sell": sells(0.75)},
    "armsdealer": {"title": "Arms Dealer", "buy": [buy(AMMO, 6, 16), gbuy("olympia", 140), gbuy("kar98k", 170), gbuy("m60", 220), gbuy("amban", 250),
                   vbuy("minecraft:diamond_helmet", 60), vbuy("minecraft:diamond_chestplate", 90)], "sell": []},
}
NPC_SKINS = json.load(open(os.path.join(HERE, "npc_skins.json")))   # milsim skins (minecraft-heads.com textures), by shop id
def npc(x, z, nm, color, prof, shop, rot, y=64):
    """A trader: a mannequin (player model) in a milsim skin; right-click opens its shop (mod Shops)."""
    nbt = {"Tags": ["ez.npc", f"ez.shop.{shop}"], "Invulnerable": True, "immovable": True, "hide_description": True,
           "CustomName": name(nm, color, True), "CustomNameVisible": True, "Rotation": [float(rot), 0.0],
           "profile": {"properties": [{"name": "textures", "value": NPC_SKINS[shop]}]}}
    return f"summon minecraft:mannequin {x} {y} {z} {snbt(nbt)}"

# ------------------------------------------------------------------ the camp (dimension ez:camp, floor y 63): a compact forward base, -18..18
# posts: name, colour, shop, NPC x/z/yaw, label y
POSTS = [("Quartermaster", "gold", "quartermaster", -12.5, -6.5, -90), ("Builder", "green", "builder", -12.5, 6.5, -90),
         ("The Broker", "dark_purple", "fence", 13.5, -6.5, 90), ("Bunker Manager", "aqua", "plots", 13.5, 6.5, 90),
         ("The Fixer", "red", "contracts", 0.5, -12.5, 0)]
STALL_NPCS = [(x, z, nm, col, "none", shop, rot) for nm, col, shop, x, z, rot in POSTS]
HELI = (0, 12)        # helipad centre; the deploy click box sits on it
CAMP_SPAWN = (0.5, 64, 6.5)
CAMP_LABELS = [
    (0.5, 67.8, -3.5, [name("☢ EXTRACTION ZONE\n", "yellow", True), {"text": "Deploy at the helipad, loot, and get out alive.\n"
        "Die and you lose everything you carried.\nTake a job from the Fixer. Store gear in your bunker.", "color": "white"}]),
    (HELI[0] + 0.5, 66.4, HELI[1] + 0.5, [name("▶ DEPLOY\n", "red", True), {"text": "Right-click the helipad.\nYou bring what you carry.", "color": "gray"}]),
    *[(x, 67.3, z, [name(nm, col, True)]) for nm, col, shop, x, z, rot in POSTS],
]

def camp_commands():
    import random
    rnd = random.Random(11)
    B = {}   # (x, y, z) -> block
    R = 18
    pick = lambda *opts: rnd.choice(opts)
    # ground: three layers, bedrock under; worn dirt, gravel and mud
    for x in range(-R, R + 1):
        for z in range(-R, R + 1):
            B[(x, 59, z)] = "minecraft:bedrock"
            for y in (60, 61, 62): B[(x, y, z)] = "minecraft:dirt"
            B[(x, 63, z)] = rnd.choice(["minecraft:coarse_dirt"] * 4 + ["minecraft:gravel", "minecraft:packed_mud", "minecraft:dirt", "minecraft:rooted_dirt", "minecraft:mud"])
    def fill(x0, y0, z0, x1, y1, z1, blk):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1): B[(x, y, z)] = blk
    def disc(cx, cz, r, blk, y=63):
        for x in range(cx - r, cx + r + 1):
            for z in range(cz - r, cz + r + 1):
                if (x - cx) ** 2 + (z - cz) ** 2 <= r * r + r: B[(x, y, z)] = blk
    # roads: gravel cross with packed-mud edges
    for k in range(-R + 1, R):
        for w in (-1, 0, 1):
            B[(k, 63, w)] = "minecraft:gravel"; B[(w, 63, k)] = "minecraft:gravel"
        for w in (-2, 2):
            if abs(k) > 3: B[(k, 63, w)] = "minecraft:packed_mud"; B[(w, 63, k)] = "minecraft:packed_mud"
    # plaza: a square of stone bricks, a fire pit, the flag and the briefing board
    fill(-3, 63, -3, 3, 63, 3, "minecraft:stone_bricks")
    for x in range(-3, 4):
        for z in range(-3, 4):
            if rnd.random() < 0.3: B[(x, 63, z)] = pick("minecraft:cracked_stone_bricks", "minecraft:mossy_stone_bricks", "minecraft:andesite")
    B[(0, 63, 0)] = "minecraft:campfire[lit=true]"
    for dx, dz in [(-1, -1), (1, -1), (-1, 1), (1, 1)]: B[(dx, 64, dz)] = "minecraft:stone_brick_slab"
    for y in range(64, 72): B[(3, y, -3)] = "minecraft:iron_bars" if y > 64 else "minecraft:polished_andesite"
    fill(4, 69, -3, 6, 71, -3, "minecraft:green_wool"); fill(4, 70, -3, 6, 70, -3, "minecraft:white_wool")
    # perimeter: HESCO barriers, two deep: the outer row 4 high, the inner row 2 high as a step, chain-link and
    # razor wire on top, barriers above so nobody climbs out
    hesco = lambda: pick("minecraft:smooth_sandstone", "minecraft:smooth_sandstone", "minecraft:sandstone", "minecraft:cut_sandstone")
    for k in range(-R, R + 1):
        for (x, z) in [(k, -R), (k, R), (-R, k), (R, k)]:
            for y in (64, 65, 66, 67): B[(x, y, z)] = hesco()
            B[(x, 68, z)] = "minecraft:iron_bars"; B[(x, 69, z)] = "minecraft:chain[axis=x]" if z in (-R, R) else "minecraft:chain[axis=z]"
            for y in range(70, 74): B[(x, y, z)] = "minecraft:barrier"
    for k in range(-R + 1, R):
        for (x, z) in [(k, -R + 1), (k, R - 1), (-R + 1, k), (R - 1, k)]:
            B[(x, 64, z)] = hesco(); B[(x, 65, z)] = hesco()
            B[(x, 66, z)] = "minecraft:sandstone_slab[type=bottom]"
    # buttresses every 6 blocks on the inside
    for k in range(-R + 3, R - 2, 6):
        for (x, z) in [(k, -R + 2), (k, R - 2), (-R + 2, k), (R - 2, k)]: B[(x, 64, z)] = "minecraft:sandstone_stairs[facing=" + ("north" if z == -R + 2 else "south" if z == R - 2 else "west" if x == -R + 2 else "east") + "]"
    # a vehicle gate on the east side (closed: plots are reached with /plot): a steel frame with a barred gate
    for z in range(-2, 3):
        for x in (R, R - 1):
            for y in range(64, 68): B[(x, y, z)] = "minecraft:air"
        B[(R, 64, z)] = "minecraft:iron_bars"; B[(R, 65, z)] = "minecraft:iron_bars"; B[(R, 66, z)] = "minecraft:iron_bars"
        B[(R - 1, 63, z)] = "minecraft:gravel"
    for z in (-3, 3):
        for y in range(64, 70): B[(R, y, z)] = B[(R - 1, y, z)] = "minecraft:iron_block"
    for z in range(-3, 4): B[(R, 69, z)] = B[(R - 1, 69, z)] = "minecraft:iron_block"
    B[(R - 1, 68, 0)] = "minecraft:lantern[hanging=true]"
    # watchtowers: log posts, a plank back wall with a ladder, a sandbagged platform, a camo-net roof of leaves
    for tx in (-15, 15):
        for tz in (-15, 15):
            sx, sz = (1 if tx > 0 else -1), (1 if tz > 0 else -1)
            for x in (tx - 1, tx + 1):
                for z in (tz - 1, tz + 1):
                    for y in range(64, 75): B[(x, y, z)] = "minecraft:spruce_log"
            for y in range(64, 71): B[(tx, y, tz + sz)] = "minecraft:spruce_planks"            # back wall (outer side)
            for y in range(64, 72): B[(tx, y, tz)] = f"minecraft:ladder[facing={'north' if sz > 0 else 'south'}]"
            for x in range(tx - 1, tx + 2):
                for z in range(tz - 1, tz + 2):
                    if (x, z) != (tx, tz): B[(x, 71, z)] = "minecraft:spruce_planks"
            for x in range(tx - 2, tx + 3):
                for z in range(tz - 2, tz + 3):
                    if abs(x - tx) == 2 or abs(z - tz) == 2: B[(x, 71, z)] = "minecraft:spruce_slab[type=top]"; B[(x, 72, z)] = "minecraft:mud_brick_wall"
            for x in range(tx - 2, tx + 3):
                for z in range(tz - 2, tz + 3): B[(x, 75, z)] = "minecraft:dark_oak_leaves[persistent=true]"
            B[(tx, 74, tz)] = "minecraft:lantern[hanging=true]"
            B[(tx + sx, 73, tz + sz)] = "minecraft:sea_lantern"   # searchlight facing out
    # posts: a ribbed shipping container each for the Quartermaster and the Broker (awning over the open side),
    # A-frame tents with closed back gables and guy ropes for the Builder and the Plot Manager
    def container(x0, z0, x1, z1, open_x, col):
        d = 1 if open_x > x0 else -1   # the open side faces +x when it's x1
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                edge = x in (x0, x1) or z in (z0, z1)
                B[(x, 63, z)] = "minecraft:spruce_planks"
                for y in (64, 65, 66, 67):
                    if edge and x != open_x: B[(x, y, z)] = f"minecraft:{col}_concrete" if (x + z) % 2 == 0 else f"minecraft:{col}_terracotta"
                    elif not edge or x == open_x: B[(x, y, z)] = "minecraft:air"
                B[(x, 68, z)] = f"minecraft:{col}_concrete"
        for z in (z0, z1):
            for y in (64, 65, 66, 67): B[(open_x, y, z)] = "minecraft:iron_block"
        for z in range(z0, z1 + 1): B[(open_x + d, 68, z)] = "minecraft:dark_oak_slab[type=top]"   # awning
        B[(open_x + d, 67, z0)] = B[(open_x + d, 67, z1)] = "minecraft:dark_oak_fence"
        for z in range(z0 + 1, z1): B[(x0 if open_x == x1 else x1, 66, z)] = "minecraft:iron_bars"  # a vent slit in the back wall
    def tent(x0, z0, x1, z1, open_x, col):
        mid = (z0 + z1) / 2; half = (z1 - z0) / 2
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                B[(x, 63, z)] = "minecraft:spruce_planks"
                h = 64 + round(3 * (1 - abs(z - mid) / half)) + 1   # roof height over this row
                B[(x, h, z)] = f"minecraft:{col}_wool"
                if x == (x0 if open_x == x1 else x1):                # closed back gable
                    for y in range(64, h): B[(x, y, z)] = f"minecraft:{col}_wool"
                elif x == open_x and abs(z - mid) >= half - 0.5:
                    B[(x, 64, z)] = "minecraft:spruce_fence"
        for x in range(x0, x1 + 1): B[(x, 68, int(mid))] = "minecraft:spruce_log[axis=x]"   # ridge pole
        for (x, z) in [(x0 - 1, z0 - 1), (x0 - 1, z1 + 1), (x1 + 1, z0 - 1), (x1 + 1, z1 + 1)]: B[(x, 64, z)] = "minecraft:spruce_fence"  # guy-rope pegs
    container(-16, -9, -10, -4, -10, "green")
    container(10, -9, 16, -4, 10, "gray")
    tent(-16, 3, -10, 9, -10, "green")
    tent(10, 3, 16, 9, 10, "brown")
    # counters and props inside the posts
    for z in (-8, -5): B[(-14, 64, z)] = pick("minecraft:smithing_table", "minecraft:grindstone[face=floor,facing=east]")
    B[(-15, 64, -6)] = "minecraft:anvil[facing=east]"; B[(-15, 64, -7)] = "minecraft:barrel[facing=up]"; B[(-15, 65, -7)] = "minecraft:lantern"
    for x, z in [(-11, -8), (-11, -5)]: B[(x, 64, z)] = "minecraft:barrel[facing=east]"
    for z in (-8, -5): B[(14, 64, z)] = "minecraft:chiseled_bookshelf[facing=west]"
    B[(15, 64, -6)] = "minecraft:cartography_table"; B[(15, 64, -7)] = "minecraft:barrel[facing=up]"; B[(15, 65, -7)] = "minecraft:soul_lantern"
    for x, z in [(11, -8), (11, -5)]: B[(x, 64, z)] = "minecraft:barrel[facing=west]"
    B[(-15, 64, 4)] = "minecraft:stonecutter"; B[(-15, 64, 8)] = "minecraft:crafting_table"; B[(-14, 64, 8)] = "minecraft:scaffolding"; B[(-11, 64, 4)] = "minecraft:barrel[facing=up]"
    B[(15, 64, 5)] = "minecraft:lectern[facing=west]"; B[(15, 64, 7)] = "minecraft:crafting_table"; B[(15, 65, 7)] = "minecraft:lantern"; B[(11, 64, 8)] = "minecraft:barrel[facing=up]"
    # the Fixer's booth (north): dark oak frame, a plank back wall with a map board, a desk, a camo-net roof
    fill(-3, 63, -16, 3, 63, -11, "minecraft:dark_oak_planks")
    for x in (-3, 3):
        for z in (-16, -11):
            for y in range(64, 68): B[(x, y, z)] = "minecraft:dark_oak_log"
    fill(-3, 64, -16, 3, 67, -16, "minecraft:spruce_planks"); fill(-2, 65, -16, 2, 66, -16, "minecraft:cartography_table")
    fill(-3, 68, -16, 3, 68, -11, "minecraft:dark_oak_slab[type=bottom]"); fill(-2, 69, -15, 2, 69, -12, "minecraft:dark_oak_leaves[persistent=true]")
    for x in range(-2, 3):
        if x != 0: B[(x, 64, -14)] = "minecraft:spruce_slab[type=top]"
    B[(-2, 65, -14)] = "minecraft:lantern"; B[(2, 65, -14)] = "minecraft:candle[candles=3,lit=true]"; B[(2, 64, -15)] = "minecraft:barrel[facing=up]"
    # sleeping tents (north-west and north-east), smaller A-frames
    tent(-11, -16, -6, -12, -6, "green")
    tent(6, -16, 11, -12, 6, "green")
    for x0 in (-10, 7):
        B[(x0, 64, -14)] = "minecraft:green_bed[facing=east,part=foot]"; B[(x0 + 1, 64, -14)] = "minecraft:green_bed[facing=east,part=head]"
    # helipad (south): concrete pad, yellow ring, white H, edge lights, sandbags and a windsock
    hx, hz = HELI
    disc(hx, hz, 4, "minecraft:gray_concrete")
    for x in range(hx - 5, hx + 6):
        for z in range(hz - 5, hz + 6):
            d = ((x - hx) ** 2 + (z - hz) ** 2) ** 0.5
            if 4.2 <= d <= 4.9: B[(x, 63, z)] = "minecraft:yellow_concrete"
            if 5.6 <= d <= 6.3 and z > hz - 2: B[(x, 64, z)] = "minecraft:mud_brick_wall"
    for z in range(hz - 2, hz + 3): B[(hx - 1, 63, z)] = B[(hx + 1, 63, z)] = "minecraft:white_concrete"
    B[(hx, 63, hz)] = "minecraft:white_concrete"
    for dx, dz in [(-4, 0), (4, 0), (0, 4), (-3, 3), (3, 3)]: B[(hx + dx, 64, hz + dz)] = "minecraft:end_rod"
    for y in range(64, 69): B[(7, y, 16)] = "minecraft:iron_bars"
    B[(8, 68, 16)] = "minecraft:orange_wool"; B[(9, 68, 16)] = "minecraft:white_wool"; B[(10, 68, 16)] = "minecraft:orange_wool"
    # a jeep (south-west) and fuel drums
    fill(-14, 64, 12, -9, 64, 14, "minecraft:green_concrete"); fill(-12, 65, 12, -9, 65, 14, "minecraft:green_concrete")
    fill(-14, 65, 12, -13, 65, 14, "minecraft:air"); B[(-13, 65, 13)] = "minecraft:spruce_stairs[facing=west]"
    for x in (-14, -9):
        for z in (11, 15): B[(x, 64, z)] = "minecraft:black_concrete"
    B[(-9, 66, 12)] = B[(-9, 66, 14)] = "minecraft:tinted_glass"
    for x, z in [(-16, 12), (-16, 13), (-16, 15), (-15, 16)]: B[(x, 64, z)] = pick("minecraft:cauldron", "minecraft:blast_furnace[facing=east]", "minecraft:barrel[facing=up]")
    # supply pallets and crates along the walls
    for x, z in [(-6, -16), (-5, -16), (5, 16), (6, 16), (12, 15), (13, 15), (-6, 16), (4, -16)]:
        B[(x, 64, z)] = pick("minecraft:barrel[facing=up]", "minecraft:spruce_planks", "minecraft:hay_block", "minecraft:composter", "minecraft:scaffolding")
        if rnd.random() < 0.5: B[(x, 65, z)] = pick("minecraft:barrel[facing=up]", "minecraft:spruce_slab")
    # sandbag lines
    for x in range(-8, -3): B[(x, 64, 16)] = "minecraft:mud_brick_wall"
    for z in range(-10, -4): B[(-6, 64, z)] = "minecraft:mud_brick_wall" if z % 3 else "minecraft:air"
    for z in range(4, 10): B[(6, 64, z)] = "minecraft:mud_brick_wall" if z % 3 else "minecraft:air"
    # lamp posts
    for x, z in [(-5, -5), (5, -5), (-5, 5), (5, 5), (-9, 0), (9, 0), (0, -9)]:
        for y in (64, 65, 66): B[(x, y, z)] = "minecraft:dark_oak_fence"
        B[(x, 67, z)] = "minecraft:lantern"
    # radio mast (west of the plaza)
    for y in range(64, 74): B[(-7, y, 1)] = "minecraft:iron_bars" if y > 65 else "minecraft:polished_deepslate"
    B[(-7, 74, 1)] = "minecraft:lightning_rod"; B[(-7, 70, 1)] = "minecraft:copper_bulb[lit=true]"
    B[(-8, 64, 1)] = "minecraft:blast_furnace[facing=west]"; B[(-6, 64, 1)] = "minecraft:lever[face=floor,facing=east]"   # its generator
    # emit: clear the old camp (it was 61 x 61), then runs of the same block along x
    out = [f"execute in {CAMP} run fill -32 {y} -32 32 {y} 32 minecraft:air" for y in range(58, 76)]
    rows = {}
    for (x, y, z), blk in B.items(): rows.setdefault((y, z), {})[x] = blk
    for (y, z), cols in sorted(rows.items()):
        xs = sorted(cols)
        start = xs[0]; prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1 and cols[x] == cols[start]:
                prev = x; continue
            blk = cols[start]
            out.append(f"execute in {CAMP} run " + (f"setblock {start} {y} {z} {blk}" if start == prev else f"fill {start} {y} {z} {prev} {y} {z} {blk}"))
            if x is not None: start = prev = x
    camp_commands.blocks = B
    return out

# ------------------------------------------------------------------ build
def build(out):
    global OUT
    OUT = os.path.join(out, "crispy_extraction")
    shutil.rmtree(OUT, ignore_errors=True)
    wj("pack.mcmeta", {"pack": {"description": "Crispy Extraction Zone (26.2)", "min_format": PACK_FORMAT[0], "max_format": PACK_FORMAT[1]}})
    wj("data/minecraft/tags/function/load.json", {"values": [f"{NS}:load"]})
    wj("data/minecraft/tags/function/tick.json", {"values": [f"{NS}:tick"]})
    # the camp: an empty dimension
    # 1.2.0: the camp has its own dimension type, the overworld's plus a grey-green fog that closes in at ~60 blocks
    # and drifting ash, so the void around the base and the plots fades into haze instead of showing as empty sky
    wj(f"data/{NS}/dimension_type/camp.json", {
        "ambient_light": 0.0, "coordinate_scale": 1.0, "default_clock": "minecraft:overworld", "has_ceiling": False,
        "has_ender_dragon_fight": False, "has_skylight": True, "height": 384, "infiniburn": "#minecraft:infiniburn_overworld",
        "logical_height": 384, "min_y": -64, "monster_spawn_block_light_limit": 0,
        "monster_spawn_light_level": {"type": "minecraft:uniform", "max_inclusive": 7, "min_inclusive": 0}, "timelines": "#minecraft:in_overworld",
        "attributes": {"minecraft:visual/fog_color": "#a3ab9c", "minecraft:visual/sky_color": "#9aa49a", "minecraft:visual/cloud_color": "#ccc8d0c4",
                       "minecraft:visual/fog_start_distance": 14.0, "minecraft:visual/fog_end_distance": 62.0, "minecraft:visual/sky_fog_end_distance": 62.0,
                       "minecraft:visual/ambient_particles": [{"particle": {"type": "minecraft:white_ash"}, "probability": 0.004}],
                       "minecraft:visual/ambient_light_color": "#0a0a0a"}})
    wj(f"data/{NS}/dimension/camp.json", {"type": f"{NS}:camp", "generator": {"type": "minecraft:flat", "settings": {
        "biome": "minecraft:the_void", "layers": [], "lakes": False, "features": False, "structure_overrides": []}}})

    ab_obj = abilities.build(pfn, pwj, "x=0,y=-2000,z=0,dx=1,dy=1,dz=1")
    # the mod's shop file (config/crispy_extraction/shops.json on the server)
    with open(os.path.join(out, "shops.json"), "w") as f:
        json.dump({"credit": snbt(stack(CREDIT)), "shops": SHOPS, "skins": NPC_SKINS}, f, indent=1, ensure_ascii=False)
    loot_tables()

    rules = {"spawn_mobs": "false", "keep_inventory": "false", "immediate_respawn": "true", "spawn_phantoms": "false", "raids": "false",
             "spawn_patrols": "false", "spawn_wandering_traders": "false", "mob_griefing": "false", "show_advancement_messages": "false",
             "locator_bar": "false", "command_block_output": "false", "respawn_radius": "0"}
    objs = [*ab_obj, "pvp dummy", "pve.gun dummy", "ez dummy", "ez.time dummy", "ez.mm dummy", "ez.s1 dummy", "ez.s10 dummy",
            "ez.ex dummy", "ez.dead deathCount", "ez.id dummy", "ez.sq dummy", "ez.ti dummy", "ez.tit dummy", "ez.ct dummy",
            "truce trigger", "ez.extracts dummy", "ez.rl dummy", "ez.rlk dummy", "ez.cd dummy", *[f"ez.m_{k} dummy" for k in MAGS], "ez.kills playerKillCount", "ez.raids dummy", "ez.new dummy", "ez.out dummy", "ez.cap dummy"]
    fn("load", [*[f"scoreboard objectives add {o}" for o in objs],
                *[f"gamerule {k} {v}" for k, v in rules.items()],
                "scoreboard players set #t ez 0", "scoreboard players set #60 ez 60", "scoreboard players set #10 ez 10",
                "execute unless score #nextid ez matches 1.. run scoreboard players set #nextid ez 1",
                "execute unless score #nextsq ez matches 1.. run scoreboard players set #nextsq ez 1",
                "difficulty normal", f"function {NS}:second"])

    fn("tick", ["function pvp:ability/tick",
                f"execute as @a[scores={{ez.rl=1..}}] run function {NS}:gun/rl_tick",
                f"execute as @e[tag=ez.gunner] at @s run function {NS}:ai/gunner"])
    wj(f"data/{NS}/predicate/sneaking.json", {"condition": "minecraft:entity_properties", "entity": "this",
                                               "predicate": {"flags": {"is_sneaking": True}}})
    # ---- magazines
    fn("gun/rl_tick", ["scoreboard players remove @s ez.rl 1",
                       *[f"execute if score @s ez.rl matches 0 if score @s ez.rlk matches {i} run function {NS}:gun/fill_{k}" for i, k in enumerate(MAGS, 1)]])
    w(f"data/{NS}/function/gun/take.mcfunction", f"$clear @s {AMMO_SEL} $(n)")
    for i, (k, (cap, rt)) in enumerate(MAGS.items(), 1):
        fn(f"gun/reload_{k}", [
            f"execute unless items entity @s container.* {AMMO_SEL} run return run function {NS}:noammo",
            f"scoreboard players set @s ez.rl {rt}", f"scoreboard players set @s ez.rlk {i}",
            f"execute if items entity @s weapon.mainhand *[minecraft:custom_data~{{ezmod:{{rl:1b}}}}] run scoreboard players set @s ez.rl {round(rt * 0.65)}",
            "playsound minecraft:item.crossbow.loading_start player @a[distance=..16] ~ ~ ~ 0.8 1.2",
            'title @s actionbar {"text":"⟳ Reloading...","color":"yellow"}'])
        fn(f"gun/fill_{k}", [   # top the magazine up from the Ammo in the inventory
            f"execute store result score #have ez run clear @s {AMMO_SEL} 0",
            "scoreboard players operation #need ez = @s ez.cap", f"scoreboard players operation #need ez -= @s ez.m_{k}",
            "execute if score #have ez < #need ez run scoreboard players operation #need ez = #have ez",
            "execute store result storage ez:gun n int 1 run scoreboard players get #need ez",
            f"execute if score #need ez matches 1.. run function {NS}:gun/take with storage ez:gun",
            f"scoreboard players operation @s ez.m_{k} += #need ez",
            "playsound minecraft:item.crossbow.loading_end player @a[distance=..16] ~ ~ ~ 0.8 1.2",
            f"function {NS}:gun/hud_{k}"])
        fn(f"gun/hud_{k}", ["execute store result score #have ez run clear @s " + AMMO_SEL + " 0",
                            "title @s actionbar " + tj([{"text": f"🔫 {GUN_NAME[k]}  ", "color": "gold", "bold": True},
                                                        {"score": {"name": "@s", "objective": f"ez.m_{k}"}, "color": "white", "bold": True},
                                                        {"text": " / ", "color": "gray"}, {"score": {"name": "@s", "objective": "ez.cap"}, "color": "gray"},
                                                        {"text": "   ammo ", "color": "dark_gray"},
                                                        {"score": {"name": "#have", "objective": "ez"}, "color": "yellow"}])])
    fn("second", [
        f"schedule function {NS}:second 20t replace",
        "scoreboard players add #t ez 1",
        "function pvp:ability/second",
        # ids and the first-join kit
        f"execute as @a unless score @s ez.id matches 1.. run function {NS}:newplayer",
        # deaths: out of the raid (they lost what they carried), back to camp
        f"execute as @a[scores={{ez.dead=1..}}] run function {NS}:raid/died",
        # anyone not on a raid belongs in camp
        f"execute as @a[tag=!ez.raid] at @s unless dimension {CAMP} run function {NS}:to_camp",
        f"execute in {CAMP} as @a[distance=0..] run function {NS}:camp/player",
        f"execute in {CAMP} run kill @e[type=#{NS}:hostile,distance=0..]",
        # raids
        f"execute as @a[tag=ez.raid] at @s run function {NS}:raid/second",
        f"execute as @e[type=minecraft:marker,tag=ez.exfil] at @s run function {NS}:exfil/second",
        f"execute if score #t ez matches 1.. run function {NS}:periodic",
    ])
    wj(f"data/{NS}/tags/entity_type/hostile.json", {"values": ["minecraft:zombie", "minecraft:skeleton", "minecraft:spider", "minecraft:creeper",
        "minecraft:enderman", "minecraft:witch", "minecraft:slime", "minecraft:zombie_villager", "minecraft:husk", "minecraft:stray",
        "minecraft:drowned", "minecraft:phantom", "minecraft:cave_spider", "minecraft:bogged", "minecraft:pillager", "minecraft:vindicator"]})
    fn("periodic", [   # spawners every SPAWN_EVERY s, crate refills, raider cleanup
        "scoreboard players operation #m ez = #t ez", f"scoreboard players set #k ez {SPAWN_EVERY}", "scoreboard players operation #m ez %= #k ez",
        f"execute if score #m ez matches 0 as @e[type=minecraft:marker,tag=ez.spawner] at @s if entity @a[tag=ez.raid,distance=..80] run function {NS}:spawner/run",
        f"execute if score #m ez matches 0 as @e[tag=ez.ai] at @s unless entity @a[tag=ez.raid,distance=..110] run tp @s ~ -400 ~",
        f"execute as @e[type=minecraft:marker,tag=ez.crate] at @s run function {NS}:crate/second",
    ])
    fn("newplayer", ["scoreboard players operation @s ez.id = #nextid ez", "scoreboard players add #nextid ez 1",
                     say("@s", "Welcome to the Extraction Zone! You got a starter kit: a pistol, ammo, bandages and some Gold Coins.", "gold"),
                     "loot give @s loot pvp:ability/pistol", give(AMMO, 24), give(BANDAGE, 2), give(CREDIT, 10)])
    fn("noammo", ['title @s actionbar {"text":"✖ Out of ammo","color":"red","bold":true}',
                  "playsound minecraft:block.dispenser.fail player @s ~ ~ ~ 0.8 1.6"])
    fn("to_camp", [f"execute in {CAMP} run tp @s {CAMP_SPAWN[0]} {CAMP_SPAWN[1]} {CAMP_SPAWN[2]} 180 0",
                   "tag @s remove ez.raid", "scoreboard players set @s ez.ex 0"])
    fn("camp/player", [   # safe in camp: no damage dealt or taken, fed; fell off: back on the deck
        "effect give @s minecraft:resistance 3 255 true", "effect give @s minecraft:weakness 3 255 true",
        "effect give @s minecraft:saturation 3 0 true", "effect give @s minecraft:regeneration 3 2 true",
        f"execute if entity @s[y=-64,dy=70] run tp @s {CAMP_SPAWN[0]} {CAMP_SPAWN[1]} {CAMP_SPAWN[2]}",   # fell out (bunkers are at y 20)
        f"execute unless entity @s[x=-31,y=60,z=-31,dx=62,dy=40,dz=62] unless entity @s[x=40,y=10,z=-200,dx=320,dy=105,dz=420] run tp @s {CAMP_SPAWN[0]} {CAMP_SPAWN[1]} {CAMP_SPAWN[2]}",
        "scoreboard players set @s truce 0", "scoreboard players enable @s truce"])

    # ---------------------------------------------------------------- deploy / raid
    fn("deploy/click", [f"advancement revoke @s only {NS}:deploy",
                        "execute if entity @s[tag=ez.raid] run return 0",
                        "tag @s add ez.raid", f"scoreboard players set @s ez.time {RAID_SECS}", "scoreboard players set @s ez.ex 0",
                        "scoreboard players add @s ez.raids 1",
                        "effect clear @s", "effect give @s minecraft:resistance 8 4 true",
                        "tp @s @e[type=minecraft:marker,tag=ez.insert,sort=random,limit=1]",
                        "ezmapgive",   # a zone map if they don't carry one (mod)
                        "ezhook deploy",   # mod: raid stats, contract set-up
                        "scoreboard players set @s ez.dead 0",
                        *title("@s", "DEPLOYED", f"{RAID_SECS // 60}:00 to reach an extraction point"),
                        say("@s", "Loot what you can and reach an extraction point (the flare columns). Die and you lose everything you carry.", "yellow"),
                        "playsound minecraft:item.elytra.flying player @s ~ ~ ~ 0.6 1.2"])
    wj(f"data/{NS}/advancement/deploy.json", {"criteria": {"c": {"trigger": "minecraft:player_interacted_with_entity", "conditions": {
        "entity": [{"condition": "minecraft:entity_properties", "entity": "this", "predicate": {"nbt": "{Tags:[\"ez.deploy\"]}"}}]}}},
        "rewards": {"function": f"{NS}:deploy/click"}})
    x, z, dx, dz = ZONE
    fn("raid/second", [
        "scoreboard players remove @s ez.time 1",
        "scoreboard players operation @s ez.mm = @s ez.time", "scoreboard players operation @s ez.mm /= #60 ez",
        "scoreboard players operation @s ez.s1 = @s ez.time", "scoreboard players operation @s ez.s1 %= #60 ez",
        "scoreboard players operation @s ez.s10 = @s ez.s1", "scoreboard players operation @s ez.s10 /= #10 ez",
        "scoreboard players operation @s ez.s1 %= #10 ez",
        "title @s actionbar " + tj([{"text": "⏱ ", "color": "gold"}, {"score": {"name": "@s", "objective": "ez.mm"}, "color": "white", "bold": True},
                                    {"text": ":", "color": "white"}, {"score": {"name": "@s", "objective": "ez.s10"}, "color": "white", "bold": True},
                                    {"score": {"name": "@s", "objective": "ez.s1"}, "color": "white", "bold": True},
                                    {"text": "   ✈ nearest extract: ", "color": "gray"},
                                    {"selector": "@e[type=minecraft:marker,tag=ez.exfil,sort=nearest,limit=1]", "color": "aqua"}]),
        "execute if score @s ez.time matches 300 run " + say("@s", "5 minutes left. Get to an extraction point.", "red"),
        "execute if score @s ez.time matches 60 run " + say("@s", "60 seconds! Extract now or lose everything.", "red"),
        f"execute if score @s ez.time matches ..0 run return run function {NS}:raid/timeout",
        # outside the zone: radiation
        f"execute unless entity @s[x={x},y=-64,z={z},dx={dx},dy=400,dz={dz}] run function {NS}:raid/outside",
        # truce requests
        f"execute if score @s truce matches 1.. run function {NS}:squad/truce",
        "scoreboard players enable @s truce",
        "execute if score @s ez.tit matches 1.. run scoreboard players remove @s ez.tit 1",
    ])
    fn("raid/outside", ['title @s actionbar {"text":"☢ RADIATION: get back into the zone","color":"green","bold":true}',
                        "damage @s 3 minecraft:magic", "playsound minecraft:block.beacon.deactivate player @s ~ ~ ~ 0.5 2"])
    fn("raid/timeout", [*title("@s", "BLOWOUT", "You ran out of time. Everything you carried is lost.", "red"),
                        say("@a[tag=ez.raid]", "☢ A raider was caught by the blowout.", "dark_green"),
                        "kill @s"])
    fn("raid/died", ["scoreboard players set @s ez.dead 0", "tag @s remove ez.raid", "scoreboard players set @s ez.ex 0",
                     "scoreboard players set @s ez.rl 0", *[f"scoreboard players set @s ez.m_{k} 0" for k in MAGS],
                     f"function {NS}:squad/leave", f"function {NS}:to_camp",
                     *title("@s", "KILLED IN ACTION", "Your gear is lying where you fell.", "red"),
                     "ezhook died",   # mod: recap, contract failed
                     "ezkit"])   # lost everything (inventory and stash)? the mod hands out a relief kit
    fn("kit/give", ["loot give @s loot pvp:ability/pistol", give(AMMO, 24), give(BANDAGE, 3), "give @s minecraft:cooked_beef 8",
                    say("@s", "📦 Relief kit: you'd lost everything, so the Quartermaster sent a pistol, 24 rounds, 3 bandages and food. "
                        "(Once every 10 minutes; /kit in camp if you're ever broke.)", "gold"),
                    "playsound minecraft:item.armor.equip_leather player @s ~ ~ ~ 1 1"])

    # ---------------------------------------------------------------- extraction
    fn("exfil/second", [
        f"particle minecraft:end_rod ~ ~3 ~ 0.1 10 0.1 0 25 force",
        f"particle minecraft:flame ~ ~1 ~ {EX_R / 2} 0.1 {EX_R / 2} 0 8 force",
        f"execute as @a[tag=ez.raid,distance=..{EX_R}] run function {NS}:exfil/hold",
        f"execute as @a[tag=ez.raid,distance={EX_R}.01..,scores={{ez.ex=1..}}] at @s unless entity @e[type=minecraft:marker,tag=ez.exfil,distance=..{EX_R}] run function {NS}:exfil/left",
    ])
    fn("exfil/hold", [
        "scoreboard players add @s ez.ex 1",
        "execute if score @s ez.ex matches 1 run tellraw @a[tag=ez.raid] " + tj([{"text": "📡 Someone is extracting at ", "color": "yellow"},
                                                                                 {"selector": "@e[type=minecraft:marker,tag=ez.exfil,sort=nearest,limit=1]", "color": "aqua"},
                                                                                 {"text": "!", "color": "yellow"}]),
        "execute if score @s ez.ex matches 1 run playsound minecraft:entity.firework_rocket.launch player @a[tag=ez.raid] ~ ~ ~ 1 0.8",
        f"title @s actionbar " + tj([{"text": "✈ EXTRACTING ", "color": "green", "bold": True}, {"score": {"name": "@s", "objective": "ez.ex"}, "color": "white"},
                                     {"text": f" / {EX_HOLD} s: stay in the zone", "color": "gray"}]),
        f"execute if score @s ez.ex matches {EX_HOLD}.. run function {NS}:exfil/done",
    ])
    fn("exfil/left", ["scoreboard players set @s ez.ex 0", 'title @s actionbar {"text":"✖ Extraction cancelled: you left the zone","color":"red"}'])
    fn("exfil/done", ["ezhook extract",   # mod, while still at the extraction point: contract, hot-extract bonus, recap
                      "scoreboard players add @s ez.extracts 1", f"function {NS}:squad/leave", f"function {NS}:to_camp",
                      *title("@s", "EXTRACTED", "Your loot is safe. Stash it in your bunker (/bunker).", "green"),
                      "tellraw @a " + tj([{"text": "✈ ", "color": "green"}, {"selector": "@s", "color": "white"}, {"text": " extracted from the Zone.", "color": "green"}]),
                      "playsound minecraft:ui.toast.challenge_complete player @s ~ ~ ~ 1 1"])

    # ---------------------------------------------------------------- squads (truce / betrayal)
    fn("squad/truce", [   # /trigger truce near another raider: propose, or accept their proposal
        "scoreboard players set @s truce 0",
        "tag @s add ez.me",
        "execute as @a[tag=ez.raid,tag=!ez.me,distance=..6,sort=nearest,limit=1] run tag @s add ez.other",
        "execute unless entity @a[tag=ez.other] run tellraw @s " + tj({"text": "Stand next to the player you want a truce with (within 6 blocks), then /trigger truce.", "color": "gray"}),
        f"execute if entity @a[tag=ez.other] run function {NS}:squad/truce2",
        "tag @a remove ez.me", "tag @a remove ez.other"])
    fn("squad/truce2", [
        # they asked me first (their id in my ez.ti, still valid): join up
        "scoreboard players operation #oid ez = @a[tag=ez.other,limit=1] ez.id",
        f"execute if score @s ez.ti = #oid ez if score @s ez.tit matches 1.. run return run function {NS}:squad/join",
        # otherwise ask them
        "scoreboard players operation @a[tag=ez.other] ez.ti = @s ez.id", "scoreboard players set @a[tag=ez.other] ez.tit 30",
        "tellraw @a[tag=ez.other] " + tj([{"text": "🤝 ", "color": "green"}, {"selector": "@a[tag=ez.me]"},
                                          {"text": " offers a truce. Stand close and type ", "color": "green"}, {"text": "/trigger truce", "color": "white"},
                                          {"text": " within 30 s to squad up (betrayal is always possible...)", "color": "green"}]),
        "tellraw @s " + tj([{"text": "Truce offered to ", "color": "green"}, {"selector": "@a[tag=ez.other]"}, {"text": ".", "color": "green"}])])
    fn("squad/join", [   # me (accepting) + other (proposed): use their squad if they have one, else a new one
        "scoreboard players set @s ez.ti 0", "scoreboard players set @s ez.tit 0",
        "execute if score @a[tag=ez.other,limit=1] ez.sq matches 1.. run scoreboard players operation #sq ez = @a[tag=ez.other,limit=1] ez.sq",
        "execute unless score @a[tag=ez.other,limit=1] ez.sq matches 1.. run scoreboard players operation #sq ez = #nextsq ez",
        "execute unless score @a[tag=ez.other,limit=1] ez.sq matches 1.. run scoreboard players add #nextsq ez 1",
        "execute store result storage ez:sq id int 1 run scoreboard players get #sq ez",
        f"function {NS}:squad/team with storage ez:sq",
        "scoreboard players operation @s ez.sq = #sq ez", "scoreboard players operation @a[tag=ez.other] ez.sq = #sq ez",
        "tellraw @a[tag=ez.raid] " + tj([{"text": "🤝 ", "color": "green"}, {"selector": "@s"}, {"text": " and ", "color": "green"},
                                         {"selector": "@a[tag=ez.other]"}, {"text": " formed a truce.", "color": "green"}]),
        "playsound minecraft:entity.villager.yes player @s ~ ~ ~ 1 1"])
    w(f"data/{NS}/function/squad/team.mcfunction", "\n".join([
        "$team add ez_sq$(id)", "$team modify ez_sq$(id) color green", "$team modify ez_sq$(id) friendlyFire true",
        "$team modify ez_sq$(id) seeFriendlyInvisibles true", "$team join ez_sq$(id) @s", "$team join ez_sq$(id) @a[tag=ez.other]"]))
    fn("squad/leave", ["team leave @s", "scoreboard players set @s ez.sq 0", "scoreboard players set @s ez.ti 0"])
    wj(f"data/{NS}/advancement/hurt_by_player.json", {"criteria": {"c": {"trigger": "minecraft:entity_hurt_player"}}, "rewards": {"function": f"{NS}:squad/hurt"}})
    fn("squad/hurt", [f"advancement revoke @s only {NS}:hurt_by_player",
                      "execute unless score @s ez.sq matches 1.. run return 0",
                      "scoreboard players operation #vs ez = @s ez.sq",
                      f"execute on attacker if entity @s[type=minecraft:player] if score @s ez.sq = #vs ez run function {NS}:squad/betray"])
    fn("squad/betray", ["tellraw @a[tag=ez.raid] " + tj([{"text": "☠ ", "color": "dark_red"}, {"selector": "@s", "color": "red"},
                                                          {"text": " BETRAYED their squad!", "color": "dark_red", "bold": True}]),
                        "playsound minecraft:entity.wither.spawn player @a[tag=ez.raid,distance=..48] ~ ~ ~ 0.5 1.4",
                        f"function {NS}:squad/leave"])

    # ---------------------------------------------------------------- crates and spawners
    fn("crate/second", [   # a loaded crate counts down; refills when nobody is close
        "scoreboard players remove @s ez.ct 1",
        f"execute if score @s ez.ct matches ..0 unless entity @a[distance=..20] run function {NS}:crate/refill"])
    for t in TIERS:
        fn(f"crate/fill{t}", [f"setblock ~ ~ ~ minecraft:air", f"setblock ~ ~ ~ minecraft:barrel[facing=up]{{LootTable:\"{NS}:crate/t{t}\"}}"])
    fn("crate/refill", [f"scoreboard players set @s ez.ct {CRATE_EVERY}",
                        *[f"execute if score @s ez {f'matches {t}'} run function {NS}:crate/fill{t}" for t in TIERS]])
    for k, (mob, nbt, tags, loot) in RAIDERS.items():
        n = dict(nbt, Tags=["ez.ai", "ez.newai", f"ez.t_{k}", *tags], DeathLootTable=f"{NS}:mob/{loot}", PersistenceRequired=False)
        fn(f"spawner/{k}", [f"summon {mob} ~ ~ ~ {snbt(n)}"])
    # ---- 1.1.0 the Commander (mod Boss.java spawns it at the city centre, with three Riflemen around it)
    boss = {"CustomName": name("☠ The Commander", "dark_red", True), "CustomNameVisible": True, "PersistenceRequired": True,
            "Tags": ["ez.boss", "ez.gunner", "ez.g_boss", "ez.t_boss"], "DeathLootTable": f"{NS}:mob/boss", "Health": 260.0,
            "attributes": [{"id": "minecraft:max_health", "base": 260.0}, {"id": "minecraft:armor", "base": 10.0},
                           {"id": "minecraft:knockback_resistance", "base": 0.8}, {"id": "minecraft:movement_speed", "base": 0.22},
                           {"id": "minecraft:follow_range", "base": 40.0}],
            **soldier("elite", 0x7A1010, 0x2A2A2A, 0x1A1A1A, "rib", "redstone", held_gun("m60"))}
    fn("boss/spawn", [f"summon minecraft:skeleton ~ ~ ~ {snbt(boss)}",
                      *[f"execute positioned ~{dx} ~ ~{dz} run function {NS}:spawner/rifleman" for dx, dz in ((3, 0), (-3, 1), (0, -3))],
                      "tag @e[tag=ez.newai] remove ez.newai",
                      "playsound minecraft:entity.wither.spawn hostile @a[distance=..120] ~ ~ ~ 0.6 1.4"])
    # the Fixer: hands out contracts (mod Contracts.java), next to the helipad
    fn("admin/contracts_npc", [f"execute in {CAMP} run kill @e[tag=ez.shop.contracts]",
                               f"execute in {CAMP} run kill @e[type=minecraft:text_display,tag=ez.fixerlabel]",
                               *[f"execute in {CAMP} run {npc(x, z, nm, col, prof, shop, rot)}" for x, z, nm, col, prof, shop, rot in STALL_NPCS if shop == "contracts"]])
    wj(f"data/{NS}/predicate/half.json", {"condition": "minecraft:random_chance", "chance": 0.5})
    fn("spawner/raider_mix", [f"execute if predicate {NS}:half run return run function {NS}:spawner/rifleman", f"function {NS}:spawner/raider"])
    # ---- enemy gunners: cock (a click you can hear), fire 10 ticks later along a hitscan ray that walls stop
    for g, (dmg, rate, miss) in GUNNERS.items():
        wj(f"data/{NS}/predicate/miss_{g}.json", {"condition": "minecraft:random_chance", "chance": miss})
    T = f"@p[tag=ez.raid,distance=..{AI_RANGE},gamemode=!spectator]"
    fn("ai/gunner", [
        "scoreboard players remove @s ez.cd 1",
        f"execute if score @s ez.cd matches 10 if entity {T} run playsound minecraft:block.iron_trapdoor.close hostile @a[distance=..32] ~ ~ ~ 0.7 1.8",
        "execute if score @s ez.cd matches 1.. run return 0",
        f"execute unless entity {T} run return run scoreboard players set @s ez.cd 20",
        "tag @s add ez.shooter", "scoreboard players set #ar ez 60",
        *[f"execute if entity @s[tag=ez.g_{g}] if predicate {NS}:miss_{g} anchored eyes facing entity {T} eyes rotated ~6 ~-4 positioned ^ ^ ^0.8 run function {NS}:ai/ray" for g in GUNNERS],
        *[f"execute if entity @s[tag=ez.g_{g}] unless predicate {NS}:miss_{g} anchored eyes facing entity {T} eyes positioned ^ ^ ^0.8 run function {NS}:ai/ray" for g in GUNNERS],
        "playsound minecraft:entity.generic.explode hostile @a[distance=..48] ~ ~ ~ 0.35 2",
        "execute anchored eyes run particle minecraft:smoke ^ ^ ^0.8 0.03 0.03 0.03 0.01 3",
        *[f"execute if entity @s[tag=ez.g_{g}] run scoreboard players set @s ez.cd {rate}" for g in GUNNERS],
        "tag @s remove ez.shooter"])
    fn("ai/ray", [
        "particle minecraft:crit ~ ~ ~ 0 0 0 0 1",
        f"execute positioned ~-0.5 ~-0.5 ~-0.5 as @a[tag=ez.raid,dx=0,dy=0,dz=0,gamemode=!spectator,limit=1] run return run function {NS}:ai/hit",
        "scoreboard players remove #ar ez 1",
        f"execute if score #ar ez matches 1.. if block ~ ~ ~ #minecraft:replaceable positioned ^ ^ ^0.5 run function {NS}:ai/ray"])
    fn("ai/hit", [*[f"execute if entity @e[tag=ez.shooter,tag=ez.g_{g}] run damage @s {dmg} minecraft:arrow by @e[tag=ez.shooter,limit=1]" for g, (dmg, _, _) in GUNNERS.items()],
                  "particle minecraft:damage_indicator ~ ~1 ~ 0.2 0.3 0.2 0.1 3"])
    fn("spawner/run", [   # as a spawner marker (ez score = cap, tag says the type): top up to the cap, scattered around it
        "execute store result score #n ez if entity @e[tag=ez.ai,distance=..48]",
        "execute if score #n ez >= @s ez run return 0",
        *[f"execute if entity @s[tag=ez.sp_{k}] run function {NS}:spawner/{k}" for k in RAIDERS if k != "raider"],
        f"execute if entity @s[tag=ez.sp_raider] run function {NS}:spawner/raider_mix",
        "execute unless entity @s[tag=ez.nospread] run spreadplayers ~ ~ 2 18 false @e[tag=ez.newai]",
        "tag @e[tag=ez.newai] remove ez.newai"])

    # ---------------------------------------------------------------- setup: the mod places points on street level (/ezadmin setup)
    fn("admin/setup", ["ezadmin setup"])

    # ---------------------------------------------------------------- the camp (built once: /function ez:admin/build_camp)
    fn("admin/build_camp", [f"execute in {CAMP} run forceload add -40 -40 40 40", f"schedule function {NS}:admin/build_camp2 40t replace"])
    cmds = camp_commands()
    for n in range(0, len(cmds), 1500):   # in parts, a tick apart
        part = cmds[n:n + 1500]
        nxt = f"schedule function {NS}:admin/camp_part{n // 1500 + 1} 2t replace" if n + 1500 < len(cmds) else f"function {NS}:admin/camp_done"
        fn(f"admin/camp_part{n // 1500}", part + [nxt])
    fn("admin/build_camp2", [f"function {NS}:admin/camp_part0"])
    fn("admin/camp_done", [
        f"execute in {CAMP} run kill @e[tag=ez.npc]", f"execute in {CAMP} run kill @e[tag=ez.deco]",
        f"execute in {CAMP} run kill @e[type=minecraft:interaction,tag=ez.deploy]",
        f"execute in {CAMP} run summon minecraft:interaction {HELI[0] + 0.5} 64 {HELI[1] + 0.5} " + snbt({"Tags": ["ez.deploy", "ez.deco"], "width": 7.0, "height": 2.5, "response": True}),
        *[f"execute in {CAMP} run {npc(x, z, nm, col, prof, shop, rot)}" for x, z, nm, col, prof, shop, rot in STALL_NPCS],
        *[f"execute in {CAMP} run summon minecraft:text_display {x} {y} {z} " + snbt({"Tags": ["ez.deco"], "billboard": "center", "text": t})
          for x, y, z, t in CAMP_LABELS],
        f"execute in {CAMP} run setworldspawn 0 {CAMP_SPAWN[1]} 6", f"execute in {CAMP} run forceload remove -40 -40 40 40",
        f"execute in {CAMP} run forceload add -32 -32 32 32", "say Camp built."])
    return OUT


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")))
