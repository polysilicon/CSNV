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
CAMP_SPAWN = (0.5, 65, 0.5)
RAID_SECS = 25 * 60
EX_HOLD = 30            # seconds on an extraction point
EX_R = 4                # its radius
ZONE = (-1050, 30, 800, 800)          # x, z, dx, dz
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

CREDIT = item("minecraft:gold_nugget", "Credits", "gold", "credit", ["Currency of the Zone.", "Spend it at the Quartermaster."], bold=True)
AMMO = item("minecraft:iron_nugget", "Ammo", "yellow", "ammo", ["Every gun shot uses one round."])
heal = lambda amp, extra=(): {"minecraft:consumable": {"consume_seconds": 1.6, "animation": "bow", "sound": "minecraft:item.armor.equip_leather",
                                                        "has_consume_particles": False,
                                                        "on_consume_effects": [{"type": "minecraft:apply_effects", "effects": [
                                                            {"id": "minecraft:instant_health", "amplifier": amp, "duration": 1}, *extra]}]}}
BANDAGE = item("minecraft:paper", "Bandage", "white", "bandage", ["Hold right-click: heals 2 hearts."], heal(0))
MEDKIT = item("minecraft:red_dye", "Medkit", "red", "medkit", ["Hold right-click: heals 4 hearts", "and regenerates for 5 s."],
              heal(1, [{"id": "minecraft:regeneration", "amplifier": 1, "duration": 100}]))
# valuables: key, item, name, colour, sell price (credits)
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
VAL = {k: item(i, n, c, k, ["Valuable: sell it to the Fence", f"for {p} credits."]) | {"price": p} for k, i, n, c, p in VALUABLES}

# guns used here, with neutral names (the Multiverse names stay on Multiverse): key, display name, trader price
EZ_GUNS = [("pistol", "Pistol", 20), ("m1911", "M1911", 32), ("mp40", "MP40", 48), ("stakeout", "Pump Shotgun", 56),
           ("stg44", "STG-44", 72), ("olympia", "Double Barrel", 80), ("kar98k", "Kar98k", 96), ("m60", "M60", 112),
           ("amban", "Marksman Rifle", 128)]   # a villager trade asks for at most 64 + 64
for k, nm, _ in EZ_GUNS:
    v = abilities.ABILITIES[k]
    abilities.ABILITIES[k] = (nm, v[1], v[2], v[3], [l.replace("Pack-a-Punch", "upgrade") for l in v[4]], v[5])

def gun(k): return {"id": abilities.BASE, "components": abilities.item_components(k)}
AMMO_SEL = 'minecraft:iron_nugget[minecraft:custom_data~{ez:"ammo"}]'

# ------------------------------------------------------------------ output helpers
OUT = None
def w(path, text):
    p = os.path.join(OUT, path); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f: f.write(text if text.endswith("\n") else text + "\n")
def wj(path, obj): w(path, json.dumps(obj, indent=1, ensure_ascii=False))
def tj(o): return json.dumps(o, ensure_ascii=False, separators=(",", ":"))

def ammo_gate(name, lines):
    """Guns used here need Ammo: no round = no shot (the gun is still handed back); a shot uses one."""
    key = name.rsplit("/", 1)[1]
    if name.startswith("ability/use/") and key in {g[0] for g in EZ_GUNS}:
        i = lines.index("scoreboard players set @s pvp.rgt 3") + 1
        lines = lines[:i] + [f"execute unless items entity @s container.* {AMMO_SEL} run return run function {NS}:noammo",
                             f"clear @s {AMMO_SEL} 1"] + lines[i:]
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
RAIDERS = {   # summon NBT per type (tags added by the spawner)
    "infected": ("minecraft:zombie", {"CustomName": name("Infected", "dark_green"), "equipment": {"head": {"id": "minecraft:leather_helmet", "count": 1}},
                                      "drop_chances": {"head": 0.0}}),
    "bandit": ("minecraft:pillager", {"CustomName": name("Bandit", "red"), "equipment": {"mainhand": {"id": "minecraft:crossbow", "count": 1}},
                                      "drop_chances": {"mainhand": 0.0}}),
    "raider": ("minecraft:vindicator", {"CustomName": name("Raider", "dark_red"), "equipment": {
        "mainhand": {"id": "minecraft:iron_axe", "count": 1}, "chest": {"id": "minecraft:iron_chestplate", "count": 1}},
        "drop_chances": {"mainhand": 0.0, "chest": 0.0}}),
}

def loot_tables():
    for t, d in TIERS.items():
        wj(f"data/{NS}/loot_table/crate/t{t}.json", {"type": "minecraft:chest", "pools": [
            {"rolls": {"min": d["rolls"][0], "max": d["rolls"][1]}, "entries": d["entries"]}]})
    for k, drops in MOB_LOOT.items():
        wj(f"data/{NS}/loot_table/mob/{k}.json", {"type": "minecraft:entity", "pools": [
            {"rolls": 1, "entries": [e], "conditions": [{"condition": "minecraft:random_chance", "chance": c}]} for e, c in drops]})

# ------------------------------------------------------------------ traders
def trade(buy, sell, buy_b=None):
    r = {"buy": buy, "sell": sell, "maxUses": 2147483647, "rewardExp": False, "xp": 0}
    if buy_b: r["buyB"] = buy_b
    return r
def credits(n): return stack(CREDIT, n)
def villager(x, z, nm, color, prof, recipes, rot):
    nbt = {"Tags": ["ez.npc"], "NoAI": True, "Invulnerable": True, "PersistenceRequired": True, "Silent": True,
           "CustomName": name(nm, color, True), "CustomNameVisible": True, "Rotation": [float(rot), 0.0],
           "VillagerData": {"profession": f"minecraft:{prof}", "type": "minecraft:plains", "level": 5}, "Offers": {"Recipes": recipes}}
    return f"summon minecraft:villager {x} 64 {z} {snbt(nbt)}"

QUARTERMASTER = [trade(credits(4), stack(AMMO, 16)), trade(credits(3), stack(BANDAGE, 2)), trade(credits(8), stack(MEDKIT, 1)),
                 *[trade(credits(p) if p <= 64 else credits(64), {"id": abilities.BASE, "count": 1, "components": abilities.item_components(k)},
                         credits(p - 64) if p > 64 else None) for k, _, p in EZ_GUNS],
                 trade(credits(20), {"id": "minecraft:iron_chestplate", "count": 1}), trade(credits(12), {"id": "minecraft:iron_helmet", "count": 1}),
                 trade(credits(16), {"id": "minecraft:iron_leggings", "count": 1}), trade(credits(10), {"id": "minecraft:iron_boots", "count": 1})]
FENCE = [trade(stack(VAL[k], 1), credits(VAL[k]["price"])) for k, *_ in VALUABLES]

# ------------------------------------------------------------------ build
def build(out):
    global OUT
    OUT = os.path.join(out, "crispy_extraction")
    shutil.rmtree(OUT, ignore_errors=True)
    wj("pack.mcmeta", {"pack": {"description": "Crispy Extraction Zone (26.2)", "min_format": PACK_FORMAT[0], "max_format": PACK_FORMAT[1]}})
    wj("data/minecraft/tags/function/load.json", {"values": [f"{NS}:load"]})
    wj("data/minecraft/tags/function/tick.json", {"values": [f"{NS}:tick"]})
    # the camp: an empty dimension
    wj(f"data/{NS}/dimension/camp.json", {"type": "minecraft:overworld", "generator": {"type": "minecraft:flat", "settings": {
        "biome": "minecraft:the_void", "layers": [], "lakes": False, "features": False, "structure_overrides": []}}})

    ab_obj = abilities.build(pfn, pwj, "x=0,y=-2000,z=0,dx=1,dy=1,dz=1")
    loot_tables()

    rules = {"keep_inventory": "false", "immediate_respawn": "true", "spawn_phantoms": "false", "raids": "false",
             "spawn_patrols": "false", "spawn_wandering_traders": "false", "mob_griefing": "false", "show_advancement_messages": "false",
             "locator_bar": "false", "command_block_output": "false", "respawn_radius": "0"}
    objs = [*ab_obj, "pvp dummy", "pve.gun dummy", "ez dummy", "ez.time dummy", "ez.mm dummy", "ez.s1 dummy", "ez.s10 dummy",
            "ez.ex dummy", "ez.dead deathCount", "ez.id dummy", "ez.sq dummy", "ez.ti dummy", "ez.tit dummy", "ez.ct dummy",
            "truce trigger", "ez.extracts dummy", "ez.kills playerKillCount", "ez.raids dummy", "ez.new dummy", "ez.out dummy"]
    fn("load", [*[f"scoreboard objectives add {o}" for o in objs],
                *[f"gamerule {k} {v}" for k, v in rules.items()],
                "scoreboard players set #t ez 0", "scoreboard players set #60 ez 60", "scoreboard players set #10 ez 10",
                "execute unless score #nextid ez matches 1.. run scoreboard players set #nextid ez 1",
                "execute unless score #nextsq ez matches 1.. run scoreboard players set #nextsq ez 1",
                "difficulty normal", f"function {NS}:second"])

    fn("tick", ["function pvp:ability/tick"])
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
                     say("@s", "Welcome to the Extraction Zone! You got a starter kit: a pistol, ammo, bandages and some credits.", "gold"),
                     "loot give @s loot pvp:ability/pistol", give(AMMO, 24), give(BANDAGE, 2), give(CREDIT, 10)])
    fn("noammo", ['title @s actionbar {"text":"✖ Out of ammo","color":"red","bold":true}',
                  "playsound minecraft:block.dispenser.fail player @s ~ ~ ~ 0.8 1.6"])
    fn("to_camp", [f"execute in {CAMP} run tp @s {CAMP_SPAWN[0]} {CAMP_SPAWN[1]} {CAMP_SPAWN[2]} 180 0",
                   "tag @s remove ez.raid", "scoreboard players set @s ez.ex 0"])
    fn("camp/player", [   # safe in camp: no damage dealt or taken, fed; fell off: back on the deck
        "effect give @s minecraft:resistance 3 255 true", "effect give @s minecraft:weakness 3 255 true",
        "effect give @s minecraft:saturation 3 0 true", "effect give @s minecraft:regeneration 3 2 true",
        f"execute if entity @s[y=-64,dy=110] run tp @s {CAMP_SPAWN[0]} {CAMP_SPAWN[1]} {CAMP_SPAWN[2]}",
        f"execute unless entity @s[x=-24,y=60,z=-24,dx=48,dy=30,dz=48] run tp @s {CAMP_SPAWN[0]} {CAMP_SPAWN[1]} {CAMP_SPAWN[2]}",
        "scoreboard players set @s truce 0", "scoreboard players enable @s truce"])

    # ---------------------------------------------------------------- deploy / raid
    fn("deploy/click", [f"advancement revoke @s only {NS}:deploy",
                        "execute if entity @s[tag=ez.raid] run return 0",
                        "tag @s add ez.raid", f"scoreboard players set @s ez.time {RAID_SECS}", "scoreboard players set @s ez.ex 0",
                        "scoreboard players add @s ez.raids 1",
                        "effect clear @s", "effect give @s minecraft:resistance 8 4 true",
                        "tp @s @e[type=minecraft:marker,tag=ez.insert,sort=random,limit=1]",
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
                     f"function {NS}:squad/leave", f"function {NS}:to_camp",
                     *title("@s", "KILLED IN ACTION", "Your gear is lying where you fell.", "red")])

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
    fn("exfil/done", ["scoreboard players add @s ez.extracts 1", f"function {NS}:squad/leave", f"function {NS}:to_camp",
                      *title("@s", "EXTRACTED", "Your loot is safe. Stash it in an ender chest.", "green"),
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
    for k, (mob, nbt) in RAIDERS.items():
        n = dict(nbt, Tags=["ez.ai", "ez.newai"], DeathLootTable=f"{NS}:mob/{k}", PersistenceRequired=False)
        fn(f"spawner/{k}", [f"summon {mob} ~ ~ ~ {snbt(n)}"])
    fn("spawner/run", [   # as a spawner marker (ez score = cap, tag says the type): top up to the cap, scattered around it
        "execute store result score #n ez if entity @e[tag=ez.ai,distance=..48]",
        "execute if score #n ez >= @s ez run return 0",
        *[f"execute if entity @s[tag=ez.sp_{k}] run function {NS}:spawner/{k}" for k in RAIDERS],
        "spreadplayers ~ ~ 2 18 false @e[tag=ez.newai]",
        "tag @e[tag=ez.newai] remove ez.newai"])

    # ---------------------------------------------------------------- setup (run once by an op: /function ez:admin/setup)
    setup1 = ["say Extraction Zone setup: loading points...", "kill @e[type=minecraft:marker,tag=ez.pt]"]
    for k, nm, ex, ez_ in EXFILS:
        setup1.append(f"forceload add {ex} {ez_}")
    for ix, iz in INSERTS:
        setup1.append(f"forceload add {ix} {iz}")
    for k, nm, px, pz, r, tier, n, rtype, cap in POIS:
        setup1.append(f"forceload add {px - r} {pz - r} {px + r} {pz + r}")
    setup1.append(f"schedule function {NS}:admin/setup2 400t replace")   # time to generate the terrain
    # the console (and schedule) run where the world spawn is, which is the camp: say "the zone" explicitly
    fn("admin/setup", [f"execute in {CAMP} run forceload remove all", f"execute in {CAMP} run forceload add -16 -16 16 16",
                       f"execute in minecraft:overworld run function {NS}:admin/setup_ow"])
    fn("admin/setup_ow", setup1)
    fn("admin/setup2", [f"execute in minecraft:overworld run function {NS}:admin/setup2_ow"])
    s2 = []
    for k, nm, ex, ez_ in EXFILS:
        s2.append(f"execute positioned {ex} 0 {ez_} positioned over motion_blocking_no_leaves run summon minecraft:marker ~ ~ ~ "
                  + snbt({"Tags": ["ez.pt", "ez.exfil"], "CustomName": name(nm, "aqua")}))
    for ix, iz in INSERTS:
        s2.append(f"execute positioned {ix} 0 {iz} positioned over motion_blocking_no_leaves run summon minecraft:marker ~ ~ ~ " + snbt({"Tags": ["ez.pt", "ez.insert"]}))
    for k, nm, px, pz, r, tier, n, rtype, cap in POIS:
        s2.append(f"execute positioned {px} 0 {pz} positioned over motion_blocking_no_leaves run summon minecraft:marker ~ ~ ~ "
                  + snbt({"Tags": ["ez.pt", "ez.spawner", f"ez.sp_{rtype}"], "CustomName": name(nm, "red")}))
        for i in range(n):
            s2.append(f"summon minecraft:marker {px} 100 {pz} " + snbt({"Tags": ["ez.pt", "ez.crate", "ez.newcrate", f"ez.t{tier}"]}))
        s2.append(f"spreadplayers {px} {pz} 4 {r} false @e[type=minecraft:marker,tag=ez.newcrate]")
        s2.append("tag @e[tag=ez.newcrate] remove ez.newcrate")
    s2 += [*[f"scoreboard players set @e[type=minecraft:marker,tag=ez.t{t}] ez {t}" for t in TIERS],
           "scoreboard players set @e[type=minecraft:marker,tag=ez.crate] ez.ct 0",
           *[f"scoreboard players set @e[type=minecraft:marker,tag=ez.spawner,tag=ez.sp_{rt}] ez {cap}" for k, nm, px, pz, r, t, n, rt, cap in POIS],
           f"execute as @e[type=minecraft:marker,tag=ez.crate] at @s run function {NS}:crate/refill",
           # keep only the exfil and insertion chunks loaded
           *[f"forceload remove {px - r} {pz - r} {px + r} {pz + r}" for k, nm, px, pz, r, *_ in POIS],
           *[f"forceload add {ex} {ez_}" for k, nm, ex, ez_ in EXFILS], *[f"forceload add {ix} {iz}" for ix, iz in INSERTS],
           "execute store result score #c ez if entity @e[type=minecraft:marker,tag=ez.crate]",
           "tellraw @a[tag=ez.admin] " + tj([{"text": "Extraction Zone setup done: ", "color": "green"}, {"score": {"name": "#c", "objective": "ez"}}, {"text": " crates.", "color": "green"}])]
    fn("admin/setup2_ow", s2)

    # ---------------------------------------------------------------- the camp (built once: /function ez:admin/build_camp)
    camp = [f"execute in {CAMP} run forceload add -32 -32 32 32", f"schedule function {NS}:admin/build_camp2 40t replace"]
    fn("admin/build_camp", camp)
    c = lambda cmd: f"execute in {CAMP} run {cmd}"
    b2 = [c("kill @e[tag=ez.npc]"), c("kill @e[tag=ez.deco]"), c("kill @e[type=minecraft:interaction,tag=ez.deploy]"),
          c("fill -22 63 -22 22 63 22 minecraft:polished_deepslate"), c("fill -21 63 -21 21 63 21 minecraft:mud_bricks"),
          c("fill -22 64 -22 22 70 22 minecraft:air"),
          c("fill -22 64 -22 22 64 -22 minecraft:mud_brick_wall"), c("fill -22 64 22 22 64 22 minecraft:mud_brick_wall"),
          c("fill -22 64 -22 -22 64 22 minecraft:mud_brick_wall"), c("fill 22 64 -22 22 64 22 minecraft:mud_brick_wall"),
          c("fill -23 64 -23 23 72 -23 minecraft:barrier"), c("fill -23 64 23 23 72 23 minecraft:barrier"),
          c("fill -23 64 -23 -23 72 23 minecraft:barrier"), c("fill 23 64 -23 23 72 23 minecraft:barrier"),
          c("fill -3 63 -3 3 63 3 minecraft:polished_tuff"),
          # stash wall (north): a row of ender chests
          c("fill -8 63 -17 8 63 -13 minecraft:dark_oak_planks"), c("fill -7 64 -18 7 64 -18 minecraft:ender_chest[facing=south]"),
          c("fill -8 65 -19 8 68 -19 minecraft:dark_oak_planks"),
          # deploy pad (south)
          c("fill -3 63 13 3 63 19 minecraft:black_concrete"), c("fill -2 63 14 2 63 18 minecraft:yellow_concrete"),
          c("summon minecraft:interaction 0 64 16 " + snbt({"Tags": ["ez.deploy", "ez.deco"], "width": 5.0, "height": 2.5, "response": True})),
          # lights
          *[c(f"setblock {x} 64 {z} minecraft:lantern") for x in (-20, -10, 10, 20) for z in (-20, 0, 20)],
          *[c(f"setblock {x} 63 {z} minecraft:sea_lantern") for x in (-15, 0, 15) for z in (-8, 8)],
          # labels
          c("summon minecraft:text_display 0 67.5 -17 " + snbt({"Tags": ["ez.deco"], "billboard": "center", "text": [
              name("📦 YOUR STASH\n", "gold", True), {"text": "Ender chests are your private storage.\nOnly what's in here is safe.", "color": "gray"}]})),
          c("summon minecraft:text_display 0 67.5 16 " + snbt({"Tags": ["ez.deco"], "billboard": "center", "text": [
              name("▶ DEPLOY INTO THE ZONE\n", "red", True), {"text": "Right-click the pad. You bring what you carry.\nDie and you lose it all.", "color": "gray"}]})),
          c("summon minecraft:text_display 0 68 0 " + snbt({"Tags": ["ez.deco"], "billboard": "center", "text": [
              name("☢ EXTRACTION ZONE\n", "yellow", True),
              {"text": "1. Gear up from your stash.\n2. Deploy, loot crates and raiders.\n3. Hold an extraction point (flare column) for "
                       f"{EX_HOLD} s.\n4. Sell valuables to the Fence, buy gear from the Quartermaster.\n"
                       "Team up with /trigger truce. Trust no one.", "color": "white"}]})),
          c(villager(-16.5, -0.5, "Quartermaster", "gold", "weaponsmith", QUARTERMASTER, -90)),
          c(villager(16.5, -0.5, "The Fence", "dark_purple", "cartographer", FENCE, 90)),
          f"execute in {CAMP} run setworldspawn 0 65 0", f"execute in {CAMP} run forceload remove -32 -32 32 32",
          f"execute in {CAMP} run forceload add -16 -16 16 16",
          "tellraw @a[tag=ez.admin] " + tj({"text": "Camp built.", "color": "green"})]
    fn("admin/build_camp2", b2)
    return OUT


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")))
