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
import camp
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
SPAWN_EVERY = 15        # raider spawner check (s)
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

# ------------------------------------------------------------------ armour (1.7.0): milsim sets, no vanilla armour
# Helmets are player heads (textures from minecraft-heads.com, armor_heads.json); chest, legs and boots are dyed leather
# with an armour trim. Every piece sets its own protection (attribute modifiers replace leather's), durability and
# custom_data {ezarmor:<set>, ezslot:<slot>}; the mod reads that for the full-set bonuses and swaps any vanilla armour.
ARMOR_HEADS = json.load(open(os.path.join(HERE, "armor_heads.json")))
SLOTS = (("head", "Helmet"), ("chest", "Jacket"), ("legs", "Trousers"), ("feet", "Boots"))
LEATHER = {"chest": "minecraft:leather_chestplate", "legs": "minecraft:leather_leggings", "feet": "minecraft:leather_boots"}
# set: name, colour, tier, armour per slot (head, chest, legs, feet), toughness per piece, durability, dyes (chest, legs, feet),
#      trim (pattern, material), extra modifiers per piece, piece names, set bonus line(s)
ARMOR = {
    "scav":       ("Scav", "gray", 0, (1, 2, 1, 1), 0.0, 80, (0x5A4E3C, 0x4B4636, 0x2E2A24), ("coast", "iron"), [],
                   ("Balaclava", "Rag Jacket", "Work Trousers", "Old Boots"), []),
    "ghillie":    ("Ghillie", "dark_green", 1, (1, 3, 2, 1), 0.0, 140, (0x3B4A22, 0x4A5A2A, 0x2F3A1C), ("wild", "emerald"), [],
                   ("Ghillie Hood", "Ghillie Jacket", "Ghillie Trousers", "Ghillie Boots"),
                   ["Full set: crouch and raiders more than", "8 blocks away lose sight of you."]),
    "hazmat":     ("Hazmat", "yellow", 1, (1, 3, 2, 1), 0.0, 140, (0xE3C21A, 0xD8B417, 0x2A2A2A), ("bolt", "netherite"), [],
                   ("Hazmat Hood", "Hazmat Suit", "Hazmat Trousers", "Hazmat Boots"),
                   ["Blocks 25% of the radiation at a crash", "site per piece; a full suit, all of it."]),
    "patrol":     ("Woodland Patrol", "green", 2, (2, 5, 4, 2), 0.0, 220, (0x4B5320, 0x556B2F, 0x3B2F1E), ("sentry", "copper"), [],
                   ("Combat Helmet", "Patrol Jacket", "Patrol Trousers", "Patrol Boots"), []),
    "tactical":   ("Tactical Ops", "dark_aqua", 3, (3, 6, 5, 2), 0.5, 320, (0x262626, 0x2E2E2E, 0x1A1A1A), ("silence", "netherite"), [],
                   ("NVG Helmet", "Plate Carrier", "Tactical Trousers", "Tactical Boots"),
                   ["Helmet: night vision while worn."]),
    "juggernaut": ("Juggernaut", "dark_red", 4, (3, 8, 6, 3), 0.75, 500, (0x3A3F44, 0x2F3438, 0x202326), ("rib", "iron"),
                   [("minecraft:knockback_resistance", 0.1, "add_value"), ("minecraft:movement_speed", -0.05, "add_multiplied_base")],
                   ("Bomb-Suit Helmet", "Blast Plate", "Blast Trousers", "Blast Boots"),
                   ["Heavy: +10% knockback resistance", "and -5% speed per piece."]),
}
TIER_NAME = ["Light", "Light", "Medium", "Heavy", "Assault"]
def armor_piece(key, slot):
    nm, col, tier, arm, tough, dur, dyes, (pat, mat), extra, names, bonus = ARMOR[key]
    i = [s for s, _ in SLOTS].index(slot)
    mods = [{"type": "minecraft:armor", "amount": float(arm[i]), "id": f"ez:armor_{slot}", "operation": "add_value", "slot": slot}]
    if tough: mods.append({"type": "minecraft:armor_toughness", "amount": tough, "id": f"ez:tough_{slot}", "operation": "add_value", "slot": slot})
    for t, a, op in extra: mods.append({"type": t, "amount": a, "id": f"ez:{t.split(':')[1]}_{slot}", "operation": op, "slot": slot})
    comps = {"minecraft:custom_name": {"text": names[i], "italic": False, "color": col},
             "minecraft:lore": [{"text": f"{nm} set · {TIER_NAME[tier]} (tier {tier})", "color": "gray", "italic": False},
                                *[{"text": l, "color": "aqua", "italic": False} for l in bonus]],
             "minecraft:attribute_modifiers": mods, "minecraft:max_damage": dur, "minecraft:custom_data": {"ezarmor": key, "ezslot": slot},
             "minecraft:tooltip_display": {"hidden_components": ["minecraft:trim", "minecraft:dyed_color"]}}
    if slot == "head":
        comps["minecraft:profile"] = {"properties": [{"name": "textures", "value": ARMOR_HEADS[key]["value"]}]}
        return {"id": "minecraft:player_head", "components": comps}
    comps["minecraft:dyed_color"] = dyes[i - 1]
    comps["minecraft:trim"] = {"material": f"minecraft:{mat}", "pattern": f"minecraft:{pat}"}
    return {"id": LEATHER[slot], "components": comps}
ARMOR_ITEMS = {(k, sl): armor_piece(k, sl) for k in ARMOR for sl, _ in SLOTS}
def aentries(key, w_):   # one loot entry per piece; the chest piece rarer
    return [entry(ARMOR_ITEMS[(key, sl)], max(1, w_ // (2 if sl == "chest" else 1))) for sl, _ in SLOTS]
def abuy(key, prices): return [buy(ARMOR_ITEMS[(key, sl)], pr) for (sl, _), pr in zip(SLOTS, prices)]


def gentry(k, w_): return {"type": "minecraft:loot_table", "value": f"pvp:ability/{k}", "weight": w_}

# ------------------------------------------------------------------ crafting (1.8.0): bunker stations, farming, tools
# Stations are vanilla blocks with no vanilla use left (recipes are filtered out); in your own bunker the mod opens a
# station menu instead (mod Stations.java). Inputs are matched exactly: "ez:<key>" is one of our items, anything else
# a vanilla item id (farm produce and the Builder's basics). Timed recipes (Kiln, Still) run while you're away.
CLOTH = item("minecraft:rabbit_hide", "Cloth", "white", "cloth", ["Woven from wheat at a Sewing Table.", "For bandages, ladders, parachutes,", "Ghillie and Patrol armour, smoke",
                                                                 "grenades, repair kits and hooks."])
SALTPETER = item("minecraft:white_dye", "Saltpeter", "white", "saltpeter", ["Made in a Kiln from wheat and potatoes.", "Reloading Bench: with 2 Charcoal it",
                                                                           "makes Propellant (ammo, smoke)."])
PROPELLANT = item("minecraft:gunpowder", "Propellant", "dark_gray", "propellant", ["Made at the Reloading Bench.", "With Copper Wire: 24 rounds of ammo.",
                                                                               "With Cloth and Scrap: smoke grenades."])
HERB = item("minecraft:green_dye", "Herbal Extract", "green", "herb", ["Pressed from sweet berries at a Med Bench.", "Med Bench: with 2 Bandages and",
                                                                     "Painkillers it makes a Medkit."])
MOONSHINE = item("minecraft:potion", "Moonshine", "gold", "moonshine", ["The Broker pays 8 each (24 a week,", "then 2). Or drink it: a little", "healing, a lot of wobble."],
                 {"minecraft:max_stack_size": 16, "minecraft:potion_contents": {"custom_color": 0xE0C070, "custom_effects": [
                     {"id": "minecraft:regeneration", "amplifier": 0, "duration": 100}, {"id": "minecraft:nausea", "amplifier": 0, "duration": 200}]},
                  "minecraft:tooltip_display": {"hidden_components": ["minecraft:potion_contents"]}})
RATION = item("minecraft:bread", "Mushroom Ration", "gold", "ration", ["Smoked mushrooms: a filling meal."],
              {"minecraft:food": {"nutrition": 8, "saturation": 10.0}})
REPAIRKIT = item("minecraft:flint", "Repair Kit", "aqua", "repairkit", ["Hold right-click: mends the armour you wear", "by half its durability."])
GRAPPLE = item("minecraft:tripwire_hook", "Grappling Hook", "gold", "grapple", ["Right-click a wall or roof edge up to", "28 blocks away: it pulls you there.", "2 s between shots · 40 uses"],
               {"minecraft:max_stack_size": 1, "minecraft:max_damage": 40, "minecraft:damage": 0}, bold=True)
PARACHUTE = item("minecraft:phantom_membrane", "Parachute", "white", "parachute", ["Hold right-click: slow falling for 20 s.", "Step off any roof."],
                 {"minecraft:max_stack_size": 4, "minecraft:consumable": {"consume_seconds": 0.4, "animation": "none", "sound": "minecraft:item.armor.equip_elytra",
                  "has_consume_particles": False, "on_consume_effects": [{"type": "minecraft:apply_effects", "effects": [
                      {"id": "minecraft:slow_falling", "amplifier": 0, "duration": 400}]}]}})
SMOKE = item("minecraft:snowball", "Smoke Grenade", "gray", "smoke", ["Throw it: a smoke screen for 15 s.", "Raiders can't shoot through smoke."], {"minecraft:max_stack_size": 8})
HAMMER = item("minecraft:iron_pickaxe", "Breaching Hammer", "gold", "hammer", ["Breaks through walls, doors and floors", "above street level, fast."],
              {"minecraft:max_damage": 300, "minecraft:tool": {"default_mining_speed": 1.0, "damage_per_block": 1, "rules": [
                  {"blocks": f"#minecraft:mineable/{t}", "speed": 9.0, "correct_for_drops": True} for t in ("pickaxe", "axe", "shovel")]}})
LADDER = {"id": "minecraft:ladder", "components": {"minecraft:custom_name": name("Rope Ladder", "gold")}}
HOE = item("minecraft:wooden_hoe", "Garden Hoe", "gold", "hoe", ["Turns dirt into farmland."])
def ez(k): return f"ez:{k}"
def mc(k): return f"minecraft:{k}"
def rcp(key, out, n, ins, sec=0, **kw):
    label = out["components"].get("minecraft:custom_name", {}).get("text") or out["id"].split(":")[1].replace("_", " ").title()
    return {"key": key, "label": label, "out": snbt(stack(out, n)), "n": n, "in": [[m, c] for m, c in ins if c > 0], "seconds": sec, **kw}
AR = lambda k, sl: ARMOR_ITEMS[(k, sl)]
STATIONS = {
    "sewing": {"block": mc("loom"), "title": "Sewing Table", "price": 30, "recipes": [
        rcp("cloth", CLOTH, 1, [(mc("wheat"), 3)]),
        rcp("bandage", BANDAGE, 2, [(ez("cloth"), 2)]),
        rcp("ladder", LADDER, 8, [(ez("cloth"), 2), (mc("oak_planks"), 2)]),
        rcp("parachute", PARACHUTE, 1, [(ez("cloth"), 4), (ez("wire"), 1)]),
        *[rcp(f"ghillie_{sl}", AR("ghillie", sl), 1, [(ez("cloth"), c), (mc("wheat"), w)]) for sl, c, w in (("head", 3, 6), ("chest", 6, 12), ("legs", 5, 10), ("feet", 2, 4))],
        *[rcp(f"patrol_{sl}", AR("patrol", sl), 1, [(ez("cloth"), c), (ez("scrap"), sc), (ez("wire"), w)])
          for sl, c, sc, w in (("head", 2, 3, 1), ("chest", 5, 4, 2), ("legs", 4, 3, 1), ("feet", 2, 2, 0))]]},
    "med": {"block": mc("brewing_stand"), "title": "Med Bench", "price": 40, "recipes": [
        rcp("herb", HERB, 1, [(mc("sweet_berries"), 4)]),
        rcp("medkit", MEDKIT, 1, [(ez("bandage"), 2), (ez("pills"), 1), (ez("herb"), 1)], perk_double="med")]},
    "kiln": {"block": mc("blast_furnace"), "title": "Kiln", "price": 40, "recipes": [
        rcp("charcoal", {"id": mc("charcoal"), "components": {"minecraft:lore": lore("Made in a Kiln from oak logs.", "Reloading Bench: 2 with a Saltpeter",
                                                                                     "make Propellant (ammo, smoke).")}}, 4, [(mc("oak_log"), 2)], 60),
        rcp("saltpeter", SALTPETER, 2, [(mc("wheat"), 2), (mc("potato"), 2)], 120),
        rcp("ration", RATION, 2, [(mc("brown_mushroom"), 2), (mc("red_mushroom"), 1)], 60)]},
    "reload": {"block": mc("fletching_table"), "title": "Reloading Bench", "price": 50, "recipes": [
        rcp("propellant", PROPELLANT, 2, [(ez("saltpeter"), 1), (mc("charcoal"), 2)]),
        rcp("ammo", AMMO, 24, [(ez("wire"), 1), (ez("propellant"), 1)]),
        rcp("smoke", SMOKE, 2, [(ez("propellant"), 1), (ez("cloth"), 1), (ez("scrap"), 1)])]},
    "still": {"block": mc("smoker"), "title": "Still", "price": 60, "recipes": [
        rcp("moonshine", MOONSHINE, 2, [(mc("potato"), 4), (mc("sugar_cane"), 2)], 300)]},
    "tools": {"block": mc("stonecutter"), "title": "Tool Bench", "price": 50, "recipes": [
        rcp("grapple", GRAPPLE, 1, [(ez("wire"), 3), (ez("scrap"), 2), (ez("cloth"), 2)]),
        rcp("hammer", HAMMER, 1, [(ez("scrap"), 4), (mc("oak_log"), 2), (ez("wire"), 1)]),
        rcp("repairkit", REPAIRKIT, 1, [(ez("cloth"), 1), (ez("scrap"), 1), (ez("wire"), 1)]),
        rcp("stash", STASH, 1, [(mc("oak_planks"), 8), (ez("scrap"), 2)])]},
}
def station_item(k):
    st = STATIONS[k]
    labels = list(dict.fromkeys(r["label"].split(" (")[0] for r in st["recipes"]))
    return item(st["block"], st["title"], "aqua", "station_" + k, ["Place it in your bunker and right-click it.", "Makes: " + ", ".join(labels[:5]) + (", ..." if len(labels) > 5 else "")], bold=True)

TIERS = {
    1: {"rolls": (3, 5), "entries": [entry(AMMO, 30, 4, 12), entry(BANDAGE, 14, 1, 2), entry(CREDIT, 16, 1, 6),
         entry(VAL["scrap"], 18, 1, 3), entry(VAL["wire"], 12, 1, 2), entry(VAL["pills"], 8), ventry("minecraft:bread", 10, 1, 3),
         *aentries("scav", 4), *aentries("ghillie", 1), *aentries("hazmat", 1), gentry("pistol", 3), gentry("m1911", 1)]},
    2: {"rolls": (4, 6), "entries": [entry(AMMO, 28, 8, 20), entry(BANDAGE, 10, 1, 3), entry(MEDKIT, 6), entry(CREDIT, 14, 3, 12),
         entry(VAL["wire"], 10, 1, 3), entry(VAL["pills"], 8, 1, 2), entry(VAL["crystal"], 8), entry(VAL["watch"], 6), entry(VAL["goldbar"], 3),
         ventry("minecraft:cooked_beef", 8, 1, 3), *aentries("patrol", 3), *aentries("ghillie", 2), *aentries("hazmat", 2),
         gentry("m1911", 4), gentry("mp40", 3), gentry("stakeout", 3), gentry("stg44", 1)]},
    3: {"rolls": (5, 7), "entries": [entry(AMMO, 24, 12, 32), entry(MEDKIT, 10, 1, 2), entry(CREDIT, 12, 8, 24),
         entry(VAL["watch"], 8), entry(VAL["goldbar"], 7), entry(VAL["gem"], 5), entry(VAL["drive"], 4), entry(VAL["blackbox"], 1),
         *aentries("tactical", 3), *aentries("patrol", 2), *aentries("juggernaut", 1),
         gentry("stg44", 4), gentry("olympia", 3), gentry("kar98k", 3), gentry("m60", 2), gentry("amban", 1), ventry("minecraft:golden_apple", 3)]},
    # 1.8.0 the Core (under 80 blocks from the centre): the best regular loot in the zone
    4: {"rolls": (6, 8), "entries": [entry(AMMO, 20, 16, 40), entry(MEDKIT, 12, 1, 2), entry(CREDIT, 12, 12, 32),
         entry(VAL["watch"], 6), entry(VAL["goldbar"], 8), entry(VAL["gem"], 8), entry(VAL["drive"], 6), entry(VAL["blackbox"], 3),
         *aentries("tactical", 5), *aentries("juggernaut", 3), entry(SMOKE, 4, 1, 2), entry(PARACHUTE, 3),
         gentry("m60", 4), gentry("amban", 3), gentry("kar98k", 3), gentry("olympia", 2), ventry("minecraft:golden_apple", 4)]},
}
MOB_LOOT = {
    "infected": [(entry(AMMO, 1, 1, 4), 0.5), (entry(VAL["scrap"], 1), 0.3), (entry(CREDIT, 1, 1, 3), 0.3)],
    "bandit": [(entry(AMMO, 1, 3, 8), 0.8), (entry(CREDIT, 1, 2, 6), 0.5), (entry(VAL["watch"], 1), 0.08), (entry(BANDAGE, 1), 0.3)],
    "raider": [(entry(AMMO, 1, 4, 10), 0.9), (entry(CREDIT, 1, 3, 10), 0.6), (entry(VAL["goldbar"], 1), 0.08),
               (entry(VAL["drive"], 1), 0.03), (entry(MEDKIT, 1), 0.2)],
    "scav": [(entry(AMMO, 1, 1, 3), 0.5), (entry(VAL["scrap"], 1), 0.4), (entry(CLOTH, 1), 0.2), (entry(CREDIT, 1, 1, 2), 0.3)],
    "sniper": [(entry(AMMO, 1, 4, 10), 0.8), (entry(CREDIT, 1, 4, 10), 0.6), (entry(VAL["drive"], 1), 0.06), (entry(SMOKE, 1), 0.15),
               (entry(ARMOR_ITEMS[("ghillie", "head")], 1), 0.05)],
    "heavy": [(entry(AMMO, 1, 10, 20), 1.0), (entry(CREDIT, 1, 8, 16), 0.8), (entry(VAL["goldbar"], 1), 0.15), (entry(MEDKIT, 1), 0.3),
              (entry(ARMOR_ITEMS[("juggernaut", "chest")], 1), 0.06), (entry(ARMOR_ITEMS[("juggernaut", "head")], 1), 0.06)],
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
SOLDIER_HEADS["ghillie"] = json.load(open(os.path.join(HERE, "armor_heads.json")))["ghillie"]["value"]
SOLDIER_HEADS["jugg"] = json.load(open(os.path.join(HERE, "armor_heads.json")))["juggernaut"]["value"]
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
    # 1.8.0 outer-ring scavengers (melee), inner-ring snipers (long range, slow), Core heavies (tough, a machine gun)
    "scav": ("minecraft:vindicator", {"CustomName": name("Scav Looter", "gray"), "equipment": {"mainhand": {"id": "minecraft:wooden_sword", "count": 1}},
             "drop_chances": {"mainhand": 0.0}, "attributes": [{"id": "minecraft:attack_damage", "base": 2.0}, {"id": "minecraft:max_health", "base": 18.0}],
             "Health": 18.0, "Silent": True}, [], "scav"),
    "sniper": ("minecraft:skeleton", {"CustomName": name("Raider Sniper", "dark_green"),
        "attributes": [{"id": "minecraft:movement_speed", "base": 0.18}, {"id": "minecraft:follow_range", "base": 48.0}],
        **soldier("ghillie", 0x3B4A22, 0x4A5A2A, 0x2F3A1C, "wild", "emerald", held_gun("kar98k"))}, ["ez.gunner", "ez.g_sniper"], "sniper"),
    "heavy": ("minecraft:skeleton", {"CustomName": name("Raider Heavy", "dark_red", True), "Health": 60.0,
        "attributes": [{"id": "minecraft:max_health", "base": 60.0}, {"id": "minecraft:armor", "base": 12.0}, {"id": "minecraft:knockback_resistance", "base": 0.6},
                       {"id": "minecraft:movement_speed", "base": 0.18}],
        **soldier("jugg", 0x3A3F44, 0x2F3438, 0x202326, "rib", "iron", held_gun("m60"))}, ["ez.gunner", "ez.g_heavy"], "heavy"),
}
# what each ring spawns (weights) and how many raiders a spawn point keeps around it
RINGS = {1: ([("infected", 45), ("scav", 35), ("bandit", 20)], 2), 2: ([("bandit", 45), ("raider", 30), ("infected", 15), ("scav", 10)], 3),
         3: ([("rifleman", 40), ("raider", 30), ("sniper", 30)], 4), 4: ([("rifleman", 35), ("heavy", 40), ("sniper", 25)], 5)}
GUNNERS = {"bandit": (3, 30, 0.35), "rifle": (4, 38, 0.25), "boss": (5, 12, 0.2), "sniper": (8, 60, 0.2), "heavy": (3, 8, 0.5)}   # damage, ticks between shots, miss chance
SNIPER_RANGE = 48
AI_RANGE = 28

def building_recipes():
    """1.8.0: vanilla recipes are filtered out; these give back the shapes you build with, from what the Builder sells
    (and what you break in the city). In the ez namespace, so the filter leaves them alone."""
    R = {}
    def shaped(name, pattern, key, out, n, cat="building"):
        R[name] = {"type": "minecraft:crafting_shaped", "category": cat, "pattern": pattern, "key": key, "result": {"id": out, "count": n}}
    def shapeless(name, ins, out, n, cat="building"):
        R[name] = {"type": "minecraft:crafting_shapeless", "category": cat, "ingredients": ins, "result": {"id": out, "count": n}}
    for w in ("oak", "spruce"):
        P = f"minecraft:{w}_planks"
        shapeless(f"{w}_planks", [f"minecraft:{w}_log"], P, 4)
        shaped(f"{w}_stairs", ["#  ", "## ", "###"], {"#": P}, f"minecraft:{w}_stairs", 4)
        shaped(f"{w}_slab", ["###"], {"#": P}, f"minecraft:{w}_slab", 6)
        shaped(f"{w}_fence", ["#|#", "#|#"], {"#": P, "|": "minecraft:stick"}, f"minecraft:{w}_fence", 3)
        shaped(f"{w}_fence_gate", ["|#|", "|#|"], {"#": P, "|": "minecraft:stick"}, f"minecraft:{w}_fence_gate", 1)
        shaped(f"{w}_door", ["##", "##", "##"], {"#": P}, f"minecraft:{w}_door", 3)
        shaped(f"{w}_trapdoor", ["###", "###"], {"#": P}, f"minecraft:{w}_trapdoor", 2)
        shaped(f"{w}_sticks", ["#", "#"], {"#": P}, "minecraft:stick", 4, "misc")
    shaped("crafting_table", ["##", "##"], {"#": "minecraft:oak_planks"}, "minecraft:crafting_table", 1, "misc")
    shaped("ladder", ["| |", "|||", "| |"], {"|": "minecraft:stick"}, "minecraft:ladder", 3)
    for base, stairs, slab, wall in (("stone_bricks", "stone_brick_stairs", "stone_brick_slab", "stone_brick_wall"), ("bricks", "brick_stairs", "brick_slab", "brick_wall"),
                                     ("deepslate_tiles", "deepslate_tile_stairs", "deepslate_tile_slab", "deepslate_tile_wall"), ("smooth_quartz", "smooth_quartz_stairs", "smooth_quartz_slab", None)):
        B = f"minecraft:{base}"
        shaped(stairs, ["#  ", "## ", "###"], {"#": B}, f"minecraft:{stairs}", 4)
        shaped(slab, ["###"], {"#": B}, f"minecraft:{slab}", 6)
        if wall: shaped(wall, ["###", "###"], {"#": B}, f"minecraft:{wall}", 6)
    shaped("glass_pane", ["###", "###"], {"#": "minecraft:glass"}, "minecraft:glass_pane", 16)
    shaped("white_carpet", ["##"], {"#": "minecraft:white_wool"}, "minecraft:white_carpet", 3)
    shaped("red_carpet", ["##"], {"#": "minecraft:red_wool"}, "minecraft:red_carpet", 3)
    shaped("item_frame", ["|||", "|#|", "|||"], {"|": "minecraft:stick", "#": "minecraft:rabbit_hide"}, "minecraft:item_frame", 2, "misc")
    for k, v in R.items(): wj(f"data/{NS}/recipe/{k}.json", v)
    return len(R)

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
        pool(1, [entry(VAL["blackbox"], 1), entry(VAL["drive"], 2, 1, 2), entry(VAL["gem"], 2, 1, 2)]),
        pool(1, [*aentries("juggernaut", 2), *aentries("tactical", 4)])]})
    wj(f"data/{NS}/loot_table/mob/boss.json", {"type": "minecraft:entity", "pools": [
        pool(1, [entry(CREDIT, 1, 40, 70)]), pool(1, [entry(VAL["blackbox"], 1, 1, 2)]), pool(1, [entry(VAL["gem"], 1, 2, 4)]),
        pool(1, [entry(VAL["drive"], 1, 1, 3)]), pool(1, [entry(VAL["goldbar"], 1, 2, 4)]), pool(1, [entry(MEDKIT, 1, 1, 2)]), pool(1, aentries("juggernaut", 1)),
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
                      gbuy("mp40", 60), gbuy("stakeout", 70), gbuy("stg44", 110), *abuy("scav", (3, 5, 4, 2)), *abuy("patrol", (14, 24, 20, 12)),
                      *abuy("ghillie", (16, 26, 22, 12)), *abuy("hazmat", (16, 26, 22, 12)), vbuy("minecraft:cooked_beef", 2, 8), vbuy("minecraft:golden_apple", 25)], "sell": []},
    "fence": {"title": "The Broker", "buy": [], "sell": sells() + [{"key": "moonshine", "item": sn(stack(MOONSHINE)), "price": 8, "cap": 24, "after": 2}]},
    "builder": {"title": "Builder", "buy": [buy(STASH, 25), vbuy("minecraft:oak_planks", 6, 32),
                vbuy("minecraft:spruce_planks", 6, 32), vbuy("minecraft:stone_bricks", 6, 32), vbuy("minecraft:bricks", 8, 32),
                vbuy("minecraft:deepslate_tiles", 8, 32), vbuy("minecraft:smooth_quartz", 10, 32), vbuy("minecraft:glass", 6, 16),
                vbuy("minecraft:oak_log", 5, 16), vbuy("minecraft:oak_stairs", 5, 16), vbuy("minecraft:oak_slab", 4, 16),
                vbuy("minecraft:oak_door", 3), vbuy("minecraft:lantern", 5, 8), vbuy("minecraft:white_wool", 4, 16), vbuy("minecraft:red_carpet", 4, 16),
                vbuy("minecraft:white_bed", 8), vbuy("minecraft:crafting_table", 3), vbuy("minecraft:item_frame", 2, 4), vbuy("minecraft:armor_stand", 5),
                vbuy("minecraft:flower_pot", 2, 4), vbuy("minecraft:poppy", 1, 4), vbuy("minecraft:oak_sapling", 2, 2), vbuy("minecraft:bookshelf", 6, 4),
                vbuy("minecraft:painting", 3),
                # 1.8.0 crafting stations and farm supplies
                *[buy(station_item(k), STATIONS[k]["price"]) for k in STATIONS],
                vbuy("minecraft:dirt", 4, 16), buy(HOE, 5), vbuy("minecraft:water_bucket", 6), vbuy("minecraft:wheat_seeds", 3, 8),
                vbuy("minecraft:potato", 3, 4), vbuy("minecraft:sugar_cane", 3, 4), vbuy("minecraft:sweet_berries", 4, 4),
                vbuy("minecraft:brown_mushroom", 3, 4), vbuy("minecraft:red_mushroom", 3, 4)], "sell": []},
    # inside the zone: worth carrying cash in
    "smuggler": {"title": "The Smuggler", "buy": [buy(AMMO, 7, 16), buy(BANDAGE, 5, 2), buy(MEDKIT, 12), gbuy("m1911", 50), gbuy("stakeout", 90),
                 vbuy("minecraft:golden_apple", 35)], "sell": sells(0.75)},
    "armsdealer": {"title": "Arms Dealer", "buy": [buy(AMMO, 6, 16), gbuy("olympia", 140), gbuy("kar98k", 170), gbuy("m60", 220), gbuy("amban", 250),
                   *abuy("tactical", (45, 75, 60, 35))], "sell": []},
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
         ("The Broker", "dark_purple", "fence", 13.5, -6.5, 90), ("Bunker Manager", "aqua", "plots", 13.5, 5.5, 90),
         ("The Fixer", "red", "contracts", 0.5, -12.5, 0)]
STALL_NPCS = [(x, z, nm, col, "none", shop, rot) for nm, col, shop, x, z, rot in POSTS]
HELI = (0, 12)        # helipad centre; the deploy click box sits on it
CAMP_SPAWN = (0.5, 64, 6.5)
CAMP_LABELS = [
    (0.5, 67.8, -3.5, [name("☢ EXTRACTION ZONE\n", "yellow", True), {"text": "Deploy at the helipad, loot, and get out alive.\n"
        "Die and you lose everything you carried.\nTake a job from the Fixer. Store gear in your bunker.", "color": "white"}]),
    (HELI[0] + 0.5, 66.4, HELI[1] + 0.5, [name("▶ DEPLOY\n", "red", True), {"text": "Right-click the helipad.\nYou bring what you carry.", "color": "gray"}]),
    (12.5, 68.4, 12.0, [name("▼ BUNKERS\n", "aqua", True), {"text": "Your bunker is down the steps.\nRight-click the door at the bottom.", "color": "gray"}]),
]   # 1.4.0: no labels over the NPCs: mannequins show their own name

def camp_commands(mode="detail"):
    """The camp's blocks (camp.py: grey-box or detail), checked at build time (26.2 block IDs, nothing on a path)."""
    c = camp.Camp(mode).build()
    c.check()
    camp_commands.blocks = {k: v[0] for k, v in c.B.items()}
    camp_commands.shares = c.shares()
    return c.commands(CAMP)

# ------------------------------------------------------------------ build
def build(out):
    global OUT
    OUT = os.path.join(out, "crispy_extraction")
    shutil.rmtree(OUT, ignore_errors=True)
    wj("pack.mcmeta", {"pack": {"description": "Crispy Extraction Zone (26.2)", "min_format": PACK_FORMAT[0], "max_format": PACK_FORMAT[1]},
                       # 1.7.0: no vanilla recipes (crafting, smelting, stonecutting, smithing) or their recipe-book unlocks
                       "filter": {"block": [{"namespace": "minecraft", "path": "recipe/.*"}, {"namespace": "minecraft", "path": "advancement/recipes/.*"}]}})
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
        json.dump({"credit": snbt(stack(CREDIT)), "shops": SHOPS, "skins": NPC_SKINS,
                   "armor": {k: {sl: snbt(stack(ARMOR_ITEMS[(k, sl)])) for sl, _ in SLOTS} for k in ARMOR},
                   "stations": STATIONS}, f, indent=1, ensure_ascii=False)
    loot_tables()
    building_recipes()

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
        "execute store result score #now ez run time query gametime",
        f"execute as @e[type=minecraft:marker,tag=ez.crate] at @s run function {NS}:crate/second",
    ])
    fn("newplayer", ["scoreboard players operation @s ez.id = #nextid ez", "scoreboard players add #nextid ez 1",
                     say("@s", "Welcome to the Extraction Zone! You got a starter kit: a pistol, ammo, bandages, a Scav outfit and some Gold Coins.", "gold"),
                     "loot give @s loot pvp:ability/pistol", give(AMMO, 24), give(BANDAGE, 2), give(CREDIT, 10),
                     *[give(ARMOR_ITEMS[("scav", sl)]) for sl, _ in SLOTS]])
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
    fn("crate/second", [   # 1.8.0: refills CRATE_EVERY s of game time after its last fill (ez.ct = when), when nobody is close
        "scoreboard players operation #d ez = #now ez", "scoreboard players operation #d ez -= @s ez.ct",
        f"execute if score #d ez matches {CRATE_EVERY * 20}.. unless entity @a[distance=..20] run function {NS}:crate/refill"])
    for t in TIERS:
        fn(f"crate/fill{t}", [f"setblock ~ ~ ~ minecraft:air", f"setblock ~ ~ ~ minecraft:barrel[facing=up]{{LootTable:\"{NS}:crate/t{t}\"}}"])
    fn("crate/refill", ["scoreboard players operation @s ez.ct = #now ez",
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
    for gname, rng in (("gunner", AI_RANGE), ("gunner_long", SNIPER_RANGE)):
     T = f"@p[tag=ez.raid,tag=!ez.hidden,distance=..{rng},gamemode=!spectator]"   # ez.hidden: a crouching ghillie (mod Armor)
     fn(f"ai/{gname}", [
        *([f"execute if entity @s[tag=ez.g_sniper] run return run function {NS}:ai/gunner_long"] if gname == "gunner" else []),
        "scoreboard players remove @s ez.cd 1",
        f"execute if score @s ez.cd matches 10 if entity {T} run playsound minecraft:block.iron_trapdoor.close hostile @a[distance=..32] ~ ~ ~ 0.7 1.8",
        "execute if score @s ez.cd matches 1.. run return 0",
        f"execute unless entity {T} run return run scoreboard players set @s ez.cd 20",
        "tag @s add ez.shooter", f"scoreboard players set #ar ez {rng * 2 + 4}",
        *[f"execute if entity @s[tag=ez.g_{g}] if predicate {NS}:miss_{g} anchored eyes facing entity {T} eyes rotated ~6 ~-4 positioned ^ ^ ^0.8 run function {NS}:ai/ray" for g in GUNNERS],
        *[f"execute if entity @s[tag=ez.g_{g}] unless predicate {NS}:miss_{g} anchored eyes facing entity {T} eyes positioned ^ ^ ^0.8 run function {NS}:ai/ray" for g in GUNNERS],
        "playsound minecraft:entity.generic.explode hostile @a[distance=..48] ~ ~ ~ 0.35 2",
        "execute anchored eyes run particle minecraft:smoke ^ ^ ^0.8 0.03 0.03 0.03 0.01 3",
        *[f"execute if entity @s[tag=ez.g_{g}] run scoreboard players set @s ez.cd {rate}" for g in GUNNERS],
        "tag @s remove ez.shooter"])
    fn("ai/ray", [
        "particle minecraft:crit ~ ~ ~ 0 0 0 0 1",
        "execute if entity @e[type=minecraft:marker,tag=ez.smoke,distance=..3.5] run return 0",   # 1.8.0 smoke stops the shot
        f"execute positioned ~-0.5 ~-0.5 ~-0.5 as @a[tag=ez.raid,dx=0,dy=0,dz=0,gamemode=!spectator,limit=1] run return run function {NS}:ai/hit",
        "scoreboard players remove #ar ez 1",
        f"execute if score #ar ez matches 1.. if block ~ ~ ~ #minecraft:replaceable positioned ^ ^ ^0.5 run function {NS}:ai/ray"])
    fn("ai/hit", [*[f"execute if entity @e[tag=ez.shooter,tag=ez.g_{g}] run damage @s {dmg} minecraft:arrow by @e[tag=ez.shooter,limit=1]" for g, (dmg, _, _) in GUNNERS.items()],
                  "particle minecraft:damage_indicator ~ ~1 ~ 0.2 0.3 0.2 0.1 3"])
    for r, (mix, cap) in RINGS.items():   # 1.8.0: a ring picks its raider type each time (weighted)
        lines, left = [], 100
        for k, wt in mix[:-1]:
            wj(f"data/{NS}/predicate/ring{r}_{k}.json", {"condition": "minecraft:random_chance", "chance": round(wt / left, 4)})
            lines.append(f"execute if predicate {NS}:ring{r}_{k} run return run function {NS}:spawner/{k}"); left -= wt
        lines.append(f"function {NS}:spawner/{mix[-1][0]}")
        fn(f"spawner/ring{r}", lines)
    fn("spawner/run", [   # as a spawner marker (ez score = cap; ez.ring<n> or, before 1.8.0, ez.sp_<type>): top up to the cap
        "execute store result score #n ez if entity @e[tag=ez.ai,distance=..48]",
        "execute if score #n ez >= @s ez run return 0",
        *[f"execute if entity @s[tag=ez.ring{r}] run return run function {NS}:spawner/ring_then {{r:{r}}}" for r in RINGS],
        *[f"execute if entity @s[tag=ez.sp_{k}] run function {NS}:spawner/{k}" for k in RAIDERS if k != "raider"],
        f"execute if entity @s[tag=ez.sp_raider] run function {NS}:spawner/raider_mix",
        "execute unless entity @s[tag=ez.nospread] run spreadplayers ~ ~ 2 18 false @e[tag=ez.newai]",
        "tag @e[tag=ez.newai] remove ez.newai"])

    fn("spawner/ring_then", [f"$function {NS}:spawner/ring$(r)", "execute unless entity @s[tag=ez.nospread] run spreadplayers ~ ~ 2 18 false @e[tag=ez.newai]",
                             "tag @e[tag=ez.newai] remove ez.newai"])

    # ---------------------------------------------------------------- setup: the mod places points on street level (/ezadmin setup)
    fn("admin/setup", ["ezadmin setup"])

    # ---------------------------------------------------------------- the camp (built once: /function ez:admin/build_camp)
    ids, fns = set(), []
    for mode, pre in (("detail", "camp"), ("grey", "grey")):
        fn(f"admin/build_{pre}", [f"execute in {CAMP} run forceload add -40 -40 40 40", f"schedule function {NS}:admin/build_{pre}2 40t replace"])
        cmds = camp_commands(mode)
        for n in range(0, len(cmds), 1500):   # in parts, a tick apart
            part = cmds[n:n + 1500]
            nxt = f"schedule function {NS}:admin/{pre}_part{n // 1500 + 1} 2t replace" if n + 1500 < len(cmds) else f"function {NS}:admin/camp_done"
            fn(f"admin/{pre}_part{n // 1500}", part + [nxt])
            fns.append(f"{NS}:admin/{pre}_part{n // 1500}")
        fn(f"admin/build_{pre}2", [f"function {NS}:admin/{pre}_part0"])
        fns += [f"{NS}:admin/build_{pre}", f"{NS}:admin/build_{pre}2"]
        ids |= {b.split("[")[0] for b in camp_commands.blocks.values()}
    camp_commands("detail")
    with open(os.path.join(out, "layout.json"), "w") as f:   # the plan the self-test checks (config/crispy_extraction/layout.json)
        ids |= {"minecraft:" + b for fam, d in camp.PAL.items() if not fam.startswith("_") for r in ("main", "secondary", "accent") for b in d[r]}
        json.dump(camp.layout(POSTS, CAMP_SPAWN, HELI) | {"palette_shares": camp_commands.shares, "block_ids": sorted(ids),
                                                         "functions": fns + [f"{NS}:admin/camp_done", f"{NS}:admin/selftest"]}, f, indent=1)
    fn("admin/camp_done", [
        f"execute in {CAMP} run kill @e[tag=ez.npc]", f"execute in {CAMP} run kill @e[tag=ez.deco]",
        f"execute in {CAMP} run kill @e[type=minecraft:interaction,tag=ez.deploy]",
        f"execute in {CAMP} run summon minecraft:interaction {HELI[0] + 0.5} 64 {HELI[1] + 0.5} " + snbt({"Tags": ["ez.deploy", "ez.deco"], "width": 7.0, "height": 2.5, "response": True}),
        f"execute in {CAMP} run kill @e[type=minecraft:interaction,tag=ez.bunkerdoor]",
        f"execute in {CAMP} run summon minecraft:interaction 12.5 62 15.5 " + snbt({"Tags": ["ez.bunkerdoor", "ez.deco"], "width": 3.0, "height": 2.2, "response": True}),
        *[f"execute in {CAMP} run {npc(x, z, nm, col, prof, shop, rot)}" for x, z, nm, col, prof, shop, rot in STALL_NPCS],
        *[f"execute in {CAMP} run summon minecraft:text_display {x} {y} {z} " + snbt({"Tags": ["ez.deco"], "billboard": "center", "text": t})
          for x, y, z, t in CAMP_LABELS],
        f"execute in {CAMP} run setworldspawn 0 {CAMP_SPAWN[1]} 6", f"execute in {CAMP} run forceload remove -40 -40 40 40",
        f"execute in {CAMP} run forceload add -32 -32 32 32", "say Camp built.", f"schedule function {NS}:admin/selftest 100t replace"])   # 1.6.0: the checks run after every rebuild
    fn("admin/selftest", ["ezadmin selftest"])
    return OUT


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")))
