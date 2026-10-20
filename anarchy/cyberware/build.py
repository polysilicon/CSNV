#!/usr/bin/env python3
"""Builds the crispy_cyberware datapack (Crispy Anarchy, Fabric 26.2, vanilla clients).

    python3 build.py [outdir]      -> <outdir>/crispy_cyberware  (default: ./dist)

Implants are consumable items sold by the Ripperdoc in the market. Using one installs it into its body
slot (one implant per slot). Each implant costs capacity; going over CAP_LIMIT is allowed but causes
cyberpsychosis episodes. Every death drops all installed implants.
"""
import json, os, shutil, sys

NS = "cyber"
DROP_ON_DEATH = True   # build.py --pvp: implants are just removed on death (kit servers)
CAP_LIMIT = 20
LAUNCH_CD, LAUNCH_SPEED, LAUNCH_POWER = 160, 1.5, 1   # Projectile Launch System: reload ticks, blocks/tick, explosion power
PACK_FORMAT = [107, 0], [107, 1]

SLOTS = {1: "Ocular", 2: "Integumentary", 3: "Skeleton", 4: "Arms", 5: "Hands", 6: "Legs",
         7: "Nervous System", 8: "Circulatory", 9: "Operating System"}

# id, key, name, color, slot, capacity, (price item, count), icon, lore, attribute modifiers
IMPLANTS = [
    (1, "kiroshi", "Kiroshi Optics", "aqua", 1, 2, ("diamond", 8), "ender_eye",
     ["Permanent night vision."], []),
    (2, "subdermal", "Subdermal Armor", "gray", 2, 4, ("diamond", 24), "netherite_scrap",
     ["+4 armor, +1 armor toughness."],
     [("armor", 4, "add_value"), ("armor_toughness", 1, "add_value")]),
    (3, "titanium", "Titanium Bones", "white", 3, 4, ("diamond", 24), "bone",
     ["+2 hearts, +10% knockback resistance."],
     [("max_health", 4, "add_value"), ("knockback_resistance", 0.1, "add_value")]),
    (4, "lungs", "Bionic Lungs", "dark_aqua", 3, 2, ("diamond", 8), "prismarine_crystals",
     ["Hold your breath much longer,", "swim 30% faster."],
     [("oxygen_bonus", 4, "add_value"), ("water_movement_efficiency", 0.3, "add_value")]),
    (5, "gorilla", "Gorilla Arms", "gold", 4, 5, ("diamond", 32), "heavy_core",
     ["+2 attack damage, extra knockback."],
     [("attack_damage", 2, "add_value"), ("attack_knockback", 0.5, "add_value")]),
    (6, "mantis", "Mantis Blades", "red", 4, 6, ("diamond", 32), "iron_sword",
     ["+1.5 attack damage, 25% faster swings,", "+0.5 block reach."],
     [("attack_damage", 1.5, "add_value"), ("attack_speed", 0.4, "add_value"),
      ("entity_interaction_range", 0.5, "add_value")]),
    (7, "tendons", "Reinforced Tendons", "green", 6, 4, ("diamond", 16), "lead",
     ["Jump higher, take 40% less fall damage."],
     [("jump_strength", 0.12, "add_value"), ("safe_fall_distance", 3, "add_value"),
      ("fall_damage_multiplier", -0.4, "add_value")]),
    (8, "lynx", "Lynx Paws", "yellow", 6, 2, ("diamond", 8), "rabbit_foot",
     ["Fast sneaking, step up full blocks."],
     [("sneaking_speed", 0.25, "add_value"), ("step_height", 0.4, "add_value")]),
    (9, "grip", "Power Grip", "blue", 5, 2, ("diamond", 12), "iron_pickaxe",
     ["Mine 30% faster (and underwater)."],
     [("block_break_speed", 0.3, "add_multiplied_base"), ("submerged_mining_speed", 0.5, "add_value")]),
    (10, "reflex", "Reflex Tuner", "light_purple", 7, 4, ("diamond", 24), "comparator",
     ["+10% movement speed."],
     [("movement_speed", 0.1, "add_multiplied_base")]),
    (11, "biomon", "Biomonitor", "green", 8, 3, ("diamond", 16), "clock",
     ["Under 4 hearts: Regeneration II + Absorption.", "90 second cooldown."], []),
    (12, "heart", "Second Heart", "dark_red", 8, 8, ("netherite_ingot", 2), "heart_of_the_sea",
     ["Under 2 hearts: instant big heal,", "Absorption II, Fire Resistance.", "10 minute cooldown."], []),
    (13, "sandy", "Sandevistan", "aqua", 9, 8, ("netherite_ingot", 3), "echo_shard",
     ["Double-tap sneak: Speed IV + Haste for 6s", "and Slowness III on everyone within 12 blocks.",
      "60 second cooldown."], []),
    (14, "berserk", "Berserk", "dark_red", 9, 7, ("netherite_ingot", 2), "blaze_powder",
     ["Double-tap sneak: Strength II + Resistance", "for 8s (you glow while it runs).", "75 second cooldown."], []),
    (16, "launcher", "Projectile Launch System", "gold", 4, 6, ("netherite_ingot", 2), "fire_charge",
     ["Sneak + jump: fire an explosive round", "where you're looking.", f"{LAUNCH_CD // 20} second reload."], []),
]
NEURO = ("neuro", "Neuroblocker", ("diamond", 2), "honey_bottle", 1200)   # seconds of psychosis immunity
OS_CD = {13: 1200, 14: 1500}   # ticks
GHOST_TICKS, GHOST_LIFE = 120, 8     # Sandevistan after-images: how long they spawn, and how long each lasts (ticks)
GHOST_COLORS = ["aqua", "green", "light_purple", "yellow"]
BY_ID = {i[0]: i for i in IMPLANTS}


def price_text(p):
    item, n = p
    return f"{n} {'Diamonds' if item == 'diamond' else 'Netherite Ingots'}"


# ------------------------------------------------------------------------------------------ writers
OUT = None
def w(path, text):
    p = os.path.join(OUT, path); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f: f.write(text if text.endswith("\n") else text + "\n")
def wj(path, obj): w(path, json.dumps(obj, indent=1, ensure_ascii=False))
def fn(name, lines): w(f"data/{NS}/function/{name}.mcfunction", "\n".join(lines))
def tj(obj): return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def item_components(key, name, color, lore, icon, rarity, anim, secs, sound):
    return {
        "minecraft:item_model": f"minecraft:{icon}",
        "minecraft:custom_name": {"text": name, "color": color, "italic": False, "bold": True},
        "minecraft:lore": [{"text": l, "color": "gray", "italic": False} for l in lore],
        "minecraft:custom_data": {NS: key},
        "minecraft:max_stack_size": 1,
        "minecraft:enchantment_glint_override": True,
        "minecraft:rarity": rarity,
        "minecraft:consumable": {"consume_seconds": secs, "animation": anim, "sound": sound,
                                 "has_consume_particles": False},
    }


def loot(key, comps):
    wj(f"data/{NS}/loot_table/item/{key}.json", {"pools": [{"rolls": 1, "entries": [{
        "type": "minecraft:item", "name": "minecraft:paper",
        "functions": [{"function": "minecraft:set_components", "components": comps}]}]}]})


def consume_adv(key, icon):
    # Matched on the icon, not custom_data: creative-mode clients can strip custom_data when they move an item.
    # Every implant has its own icon, and only Ripperdoc items are consumable paper.
    wj(f"data/{NS}/advancement/use/{key}.json", {
        "criteria": {"c": {"trigger": "minecraft:consume_item", "conditions": {"item": {
            "items": "minecraft:paper", "components": {"minecraft:item_model": f"minecraft:{icon}"}}}}},
        "rewards": {"function": f"{NS}:implant/{key}/use"}})


def build():
    shutil.rmtree(OUT, ignore_errors=True)
    wj("pack.mcmeta", {"pack": {"description": "Crispy Cyberware: Ripperdoc implants, capacity and cyberpsychosis (26.2)",
                                "min_format": PACK_FORMAT[0], "max_format": PACK_FORMAT[1]}})
    wj("data/minecraft/tags/function/load.json", {"values": [f"{NS}:load"]})
    wj("data/minecraft/tags/function/tick.json", {"values": [f"{NS}:tick"]})
    wj(f"data/{NS}/predicate/sneaking.json", {"condition": "minecraft:entity_properties", "entity": "this",
                                               "predicate": {"minecraft:flags": {"is_sneaking": True}}})

    # ------------------------------------------------------------------ load / tick / second
    objs = ["cy dummy", "cy.buy trigger", "cy.rm trigger", "cyber trigger", "cy.cap dummy", "cy.cd dummy",
            "cy.cdh dummy", "cy.hp health", "cy.death deathCount", "cy.snk dummy", "cy.tap dummy",
            "cy.nb dummy", "cy.pcd dummy", "cy.sv dummy", "cy.gl dummy",
            "cy.jump minecraft.custom:minecraft.jump", "cy.lcd dummy"] + [f"cy.s{s} dummy" for s in SLOTS]
    fn("load", [f"scoreboard objectives add {o}" for o in objs] + [
        f"scoreboard players set #limit cy {CAP_LIMIT}", "scoreboard players set #t cy 0", "scoreboard players set #2 cy 2",
        # Sandevistan after-image glow colours
        *[l for n, c in enumerate(GHOST_COLORS, 1) for l in (
            f"team add cy.g{n}", f"team modify cy.g{n} color {c}", f"team modify cy.g{n} collisionRule never",
            f"team modify cy.g{n} nametagVisibility never")],
        "kill @e[tag=cy.ghost]", "kill @e[tag=cy.ganchor]"])

    fn("tick", [
        "scoreboard players enable @a cy.buy", "scoreboard players enable @a cy.rm", "scoreboard players enable @a cyber",
        f"execute as @a[scores={{cy.buy=1..}}] at @s run function {NS}:doc/buy",
        f"execute as @a[scores={{cy.rm=1..}}] at @s run function {NS}:doc/remove",
        f"execute as @a[scores={{cyber=1..}}] run function {NS}:status",
        f"execute as @a[scores={{cy.death=1..}}] at @s run function {NS}:death/died",
        f"execute as @e[type=minecraft:player,tag=cy.dead] run function {NS}:death/respawned",
        # active Operating System implants: double-tap sneak
        f"execute as @a[scores={{cy.s9=13..}}] at @s run function {NS}:os/tick",
        "scoreboard players remove @a[scores={cy.cd=1..}] cy.cd 1",
        "execute as @a[scores={cy.cd=1,cy.s9=13}] run title @s actionbar {\"text\":\"◆ Sandevistan ready\",\"color\":\"aqua\"}",
        "execute as @a[scores={cy.cd=1,cy.s9=14}] run title @s actionbar {\"text\":\"◆ Berserk ready\",\"color\":\"red\"}",
        # Projectile Launch System (arms): sneak + jump
        f"execute as @a[scores={{cy.s4=16}}] at @s run function {NS}:arms/tick",
        "scoreboard players remove @a[scores={cy.lcd=1..}] cy.lcd 1",
        "execute as @a[scores={cy.lcd=1,cy.s4=16}] run title @s actionbar {\"text\":\"◆ Launcher loaded\",\"color\":\"gold\"}",
        # circulatory implants
        "scoreboard players remove @a[scores={cy.cdh=1..}] cy.cdh 1",
        f"execute as @a[scores={{cy.s8=11,cy.hp=1..8,cy.cdh=0}}] at @s run function {NS}:fx/biomon",
        f"execute as @a[scores={{cy.s8=12,cy.hp=1..4,cy.cdh=0}}] at @s run function {NS}:fx/heart",
        "scoreboard players add #t cy 1",
        # Sandevistan after-images
        f"execute as @a[scores={{cy.sv=1..}}] at @s run function {NS}:ghost/player",
        f"execute as @e[tag=cy.ghost] run function {NS}:ghost/age",
        f"execute as @e[type=minecraft:item_display,tag=cy.ganchor] run function {NS}:ghost/age",
        f"execute if score #t cy matches 20.. run function {NS}:second",
    ])
    fn("second", [
        "scoreboard players set #t cy 0",
        # make sure every score used in a selector exists
        *[f"scoreboard players add @a {o} 0" for o in ["cy.cap", "cy.cd", "cy.cdh", "cy.nb", "cy.pcd", "cy.lcd"] + [f"cy.s{s}" for s in SLOTS]],
        "effect give @a[scores={cy.s1=1}] minecraft:night_vision 30 0 true",
        "scoreboard players remove @a[scores={cy.nb=1..}] cy.nb 1",
        "execute as @a[scores={cy.nb=1}] run tellraw @s {\"text\":\"Your Neuroblocker wore off.\",\"color\":\"dark_purple\"}",
        "scoreboard players remove @a[scores={cy.pcd=1..}] cy.pcd 1",
        f"execute as @a[scores={{cy.nb=0,cy.pcd=0}}] if score @s cy.cap > #limit cy at @s run function {NS}:psycho/roll",
    ])

    # ------------------------------------------------------------------ items, install, remove
    for (iid, key, name, color, slot, cap, price, icon, lore, mods) in IMPLANTS:
        full_lore = [f"Slot: {SLOTS[slot]}", f"Capacity: {cap}"] + lore + ["Use (hold right-click) to install."]
        loot(key, item_components(key, name, color, full_lore, icon, "epic" if price[0] != "diamond" else "rare",
                                  "bow", 2.5, "minecraft:block.anvil.use"))
        consume_adv(key, icon)
        d = f"implant/{key}"
        fn(f"{d}/apply", [f"attribute @s minecraft:{a} modifier add {NS}:{key}_{n} {v} {op}" for n, (a, v, op) in enumerate(mods)])
        fn(f"{d}/unapply", [f"attribute @s minecraft:{a} modifier remove {NS}:{key}_{n}" for n, (a, v, op) in enumerate(mods)])
        nm = {"text": name, "color": color}
        fn(f"{d}/use", [
            f"advancement revoke @s only {NS}:use/{key}",
            f"execute unless score @s cy.s{slot} matches 0 run return run function {NS}:implant/{key}/occupied",
            f"scoreboard players set @s cy.s{slot} {iid}",
            f"scoreboard players add @s cy.cap {cap}",
            f"function {NS}:{d}/apply",
            "scoreboard players set @s cy.cdh 0" if slot == 8 else "scoreboard players set @s cy.cd 0" if slot == 9 else "",
            "playsound minecraft:block.beacon.activate player @s ~ ~ ~ 1 1.6",
            "particle minecraft:electric_spark ~ ~1 ~ 0.4 0.6 0.4 0.2 40",
            f"tellraw @s [{{\"text\":\"Installed \",\"color\":\"green\"}},{tj(nm)},{{\"text\":\" ({SLOTS[slot]}).\",\"color\":\"green\"}}]",
            *(["tellraw @s {\"text\":\"Double-tap sneak to activate.\",\"color\":\"gray\"}"] if slot == 9 else []),
            *(["tellraw @s {\"text\":\"Sneak + jump to fire.\",\"color\":\"gray\"}", "scoreboard players set @s cy.lcd 0"] if key == "launcher" else []),
            f"function {NS}:capacity_msg",
        ])
        fn(f"{d}/occupied", [
            f"loot give @s loot {NS}:item/{key}",
            f"tellraw @s [{{\"text\":\"Your {SLOTS[slot]} slot already has an implant. \",\"color\":\"red\"}},"
            f"{{\"text\":\"Remove it at the Ripperdoc first.\",\"color\":\"gray\"}}]",
        ])
        fn(f"{d}/remove", [   # at the Ripperdoc: implant goes back to your inventory
            f"loot give @s loot {NS}:item/{key}",
            f"function {NS}:{d}/unapply",
            f"scoreboard players remove @s cy.cap {cap}",
            f"scoreboard players set @s cy.s{slot} 0",
            f"tellraw @s [{{\"text\":\"Removed \",\"color\":\"yellow\"}},{tj(nm)},{{\"text\":\".\",\"color\":\"yellow\"}}]",
        ])
        fn(f"{d}/drop", ([f"loot spawn ~ ~ ~ loot {NS}:item/{key}"] if DROP_ON_DEATH else []) + [f"function {NS}:{d}/unapply"])
        fn(f"{d}/kit", [   # install without an item and without chat output (kits; run admin/reset first)
            f"scoreboard players set @s cy.s{slot} {iid}", f"scoreboard players add @s cy.cap {cap}", f"function {NS}:{d}/apply",
            "scoreboard players set @s cy.cdh 0" if slot == 8 else "scoreboard players set @s cy.cd 0" if slot == 9 else ""])

    nkey, nname, nprice, nicon, nsecs = NEURO
    loot(nkey, item_components(nkey, nname, "dark_purple",
                               ["Suppresses cyberpsychosis for 20 minutes.", "Drink to use."], nicon, "uncommon",
                               "drink", 1.6, "minecraft:entity.generic.drink"))
    consume_adv(nkey, nicon)
    fn(f"implant/{nkey}/use", [
        f"advancement revoke @s only {NS}:use/{nkey}",
        f"scoreboard players set @s cy.nb {nsecs}",
        "tellraw @s {\"text\":\"Neuroblocker active: no cyberpsychosis for 20 minutes.\",\"color\":\"dark_purple\"}",
    ])

    fn("capacity_msg", [
        f"tellraw @s [{{\"text\":\"Capacity: \",\"color\":\"gray\"}},{{\"score\":{{\"name\":\"@s\",\"objective\":\"cy.cap\"}},\"color\":\"white\"}},"
        f"{{\"text\":\"/{CAP_LIMIT}\",\"color\":\"gray\"}}]",
        f"execute if score @s cy.cap > #limit cy run tellraw @s {{\"text\":\"⚠ Over capacity: you are at risk of cyberpsychosis. "
        f"Neuroblockers from the Ripperdoc suppress it.\",\"color\":\"red\"}}",
    ])

    # ------------------------------------------------------------------ status (/trigger cyber)
    st = ["scoreboard players set @s cyber 0", "tellraw @s {\"text\":\"--- Your cyberware ---\",\"color\":\"aqua\",\"bold\":true}"]
    for slot, sname in SLOTS.items():
        st.append(f"execute if score @s cy.s{slot} matches 0 run tellraw @s [{{\"text\":\"{sname}: \",\"color\":\"gray\"}},{{\"text\":\"empty\",\"color\":\"dark_gray\"}}]")
        for i in IMPLANTS:
            if i[4] == slot:
                st.append(f"execute if score @s cy.s{slot} matches {i[0]} run tellraw @s [{{\"text\":\"{sname}: \",\"color\":\"gray\"}},{tj({'text': i[2], 'color': i[3]})}]")
    st += [f"function {NS}:capacity_msg",
           "execute if score @s cy.nb matches 1.. run tellraw @s [{\"text\":\"Neuroblocker: \",\"color\":\"dark_purple\"},{\"score\":{\"name\":\"@s\",\"objective\":\"cy.nb\"}},{\"text\":\"s left\",\"color\":\"dark_purple\"}]",
           "execute if score @s cy.cd matches 1.. run tellraw @s {\"text\":\"Operating System is cooling down.\",\"color\":\"gray\"}"]
    fn("status", st)

    # ------------------------------------------------------------------ Ripperdoc: buy / remove
    near = f"execute unless entity @e[type=minecraft:villager,tag=cy.doc,distance=..8] run return run tellraw @s {{\"text\":\"Visit the Ripperdoc in the market (/trigger market).\",\"color\":\"red\"}}"
    buy = ["scoreboard players operation #b cy = @s cy.buy", "scoreboard players set @s cy.buy 0", near]
    for (iid, key, name, color, slot, cap, price, *_ ) in IMPLANTS + [(15, nkey, nname, "dark_purple", 0, 0, nprice)]:
        buy.append(f"execute if score #b cy matches {iid} if function {NS}:pay/{key} run function {NS}:doc/got/{key}")
        item, n = price
        fn(f"pay/{key}", [
            f"execute store result score #have cy run clear @s minecraft:{item} 0",
            f"execute if score #have cy matches ..{n - 1} run return run tellraw @s [{{\"text\":\"You need {price_text(price)} \",\"color\":\"red\"}},"
            f"{{\"text\":\"(you have \",\"color\":\"gray\"}},{{\"score\":{{\"name\":\"#have\",\"objective\":\"cy\"}},\"color\":\"gray\"}},{{\"text\":\").\",\"color\":\"gray\"}}]",
            f"clear @s minecraft:{item} {n}",
            "return 1",
        ])
        fn(f"doc/got/{key}", [
            f"loot give @s loot {NS}:item/{key}",
            "playsound minecraft:entity.villager.yes neutral @s ~ ~ ~ 1 0.8",
            f"tellraw @s [{{\"text\":\"Bought \",\"color\":\"green\"}},{tj({'text': name, 'color': color})},{{\"text\":\". \",\"color\":\"green\"}},"
            + ("{\"text\":\"Hold right-click with it to install.\",\"color\":\"gray\"}]" if slot else "{\"text\":\"Drink it when you need it.\",\"color\":\"gray\"}]"),
        ])
    buy.append(f"execute if score #b cy matches 99 run dialog show @s {NS}:remove")
    fn("doc/buy", buy)

    rm = ["scoreboard players operation #s cy = @s cy.rm", "scoreboard players set @s cy.rm 0", near]
    for slot in SLOTS:
        rm.append(f"execute if score #s cy matches {slot} if score @s cy.s{slot} matches 0 run return run tellraw @s {{\"text\":\"Nothing installed in {SLOTS[slot]}.\",\"color\":\"red\"}}")
        for i in IMPLANTS:
            if i[4] == slot:
                rm.append(f"execute if score #s cy matches {slot} if score @s cy.s{slot} matches {i[0]} run return run function {NS}:implant/{i[1]}/remove")
    fn("doc/remove", rm)

    fn("doc/open", [
        f"advancement revoke @s only {NS}:doc",
        f"dialog show @s {NS}:ripperdoc",
        "execute as @e[type=minecraft:interaction,tag=cy.doc,distance=..8] run data remove entity @s interaction",
    ])
    wj(f"data/{NS}/advancement/doc.json", {"criteria": {"c": {"trigger": "minecraft:player_interacted_with_entity", "conditions": {"entity": [{
        "condition": "minecraft:entity_properties", "entity": "this",
        "predicate": {"minecraft:entity_type": "minecraft:interaction", "minecraft:nbt": "{Tags:[\"cy.doc\"]}"}}]}}},
        "rewards": {"function": f"{NS}:doc/open"}})
    fn("admin/place_doc", [
        "# run at the spot where the Ripperdoc should stand, e.g.",
        "# execute in crispy:market positioned -46.5 172 65.5 run function cyber:admin/place_doc",
        "# crispy_shop: the market moves every other villager out of the world (crispy:second)",
        "kill @e[tag=cy.doc]",
        "summon minecraft:villager ~ ~ ~ {Tags:[\"cy.doc\",\"crispy_shop\"],Rotation:[90f,0f],NoAI:1b,Invulnerable:1b,Silent:1b,PersistenceRequired:1b,"
        "CustomNameVisible:1b,CustomName:{\"text\":\"⚕ Ripperdoc ⚕\",\"color\":\"aqua\",\"bold\":true},"
        "VillagerData:{profession:\"minecraft:cleric\",level:5,type:\"minecraft:swamp\"},Offers:{Recipes:[]}}",
        "summon minecraft:interaction ~ ~ ~ {Tags:[\"cy.doc\"],width:1.2f,height:2.2f,response:1b}",
    ])
    fn("admin/reset", [f"function {NS}:implant/{i[1]}/unapply" for i in IMPLANTS if i[9]]
       + [f"scoreboard players set @s cy.s{s} 0" for s in SLOTS] + ["scoreboard players set @s cy.cap 0", "scoreboard players set @s cy.sv 0"])
    fn("admin/give", [f"loot give @s loot {NS}:item/{i[1]}" for i in IMPLANTS] + [f"loot give @s loot {NS}:item/{nkey}"])

    # dialogs
    def btn(label, color, tip, cmd, width=150):
        return {"label": {"text": label, "color": color, "bold": True}, "tooltip": {"text": tip}, "width": width,
                "action": {"type": "minecraft:run_command", "command": cmd}}
    acts = []
    for (iid, key, name, color, slot, cap, price, icon, lore, mods) in IMPLANTS:
        acts.append(btn(name, color, f"{SLOTS[slot]} · capacity {cap} · {price_text(price)}\n" + " ".join(lore), f"trigger cy.buy set {iid}"))
    acts.append(btn(nname, "dark_purple", f"No cyberpsychosis for 20 minutes · {price_text(nprice)}", "trigger cy.buy set 15"))
    acts.append(btn("Remove an implant…", "yellow", "Take an installed implant out and get the item back (free).", "trigger cy.buy set 99"))
    common = {"type": "minecraft:multi_action", "columns": 2, "can_close_with_escape": True, "pause": False, "after_action": "close",
              "exit_action": {"label": {"text": "Close"}, "width": 150}}
    wj(f"data/{NS}/dialog/ripperdoc.json", {**common,
        "title": {"text": "⚕ Ripperdoc ⚕", "color": "aqua", "bold": True},
        "body": [{"type": "minecraft:plain_message", "width": 310, "contents": [
            {"text": "Chrome for sale. One implant per body slot; use the item to install it.\n", "color": "gray"},
            {"text": f"Every implant uses capacity. Over {CAP_LIMIT} capacity you risk cyberpsychosis.\n", "color": "red"},
            {"text": "All installed implants drop when you die.\n", "color": "gold"},
            {"text": "Operating System implants: double-tap sneak. Check yours with /trigger cyber.", "color": "dark_gray"}]}],
        "actions": acts})
    wj(f"data/{NS}/dialog/remove.json", {**common,
        "title": {"text": "Remove an implant", "color": "yellow", "bold": True},
        "body": [{"type": "minecraft:plain_message", "width": 310, "contents": [
            {"text": "The implant goes back into your inventory.", "color": "gray"}]}],
        "actions": [btn(sname, "yellow", f"Remove your {sname} implant", f"trigger cy.rm set {slot}") for slot, sname in SLOTS.items()]})

    # ------------------------------------------------------------------ death: chrome drops
    died = ["scoreboard players reset @s cy.death"]
    for i in IMPLANTS:
        died.append(f"execute if score @s cy.s{i[4]} matches {i[0]} run function {NS}:implant/{i[1]}/drop")
    if DROP_ON_DEATH: died += [f"execute if score @s cy.cap matches 1.. run tellraw @s {{\"text\":\"Your chrome was left where you died.\",\"color\":\"red\"}}"]
    died += [f"scoreboard players set @s cy.s{s} 0" for s in SLOTS]
    died += ["scoreboard players set @s cy.cap 0", "scoreboard players set @s cy.cd 0", "scoreboard players set @s cy.cdh 0",
             "scoreboard players set @s cy.sv 0", "tag @s add cy.dead"]
    fn("death/died", died)
    fn("death/respawned", ["tag @s remove cy.dead"] + [f"function {NS}:implant/{i[1]}/unapply" for i in IMPLANTS if i[9]])

    # ------------------------------------------------------------------ active / reactive effects
    fn("os/tick", [
        "scoreboard players add @s cy.tap 1",
        f"execute if predicate {NS}:sneaking if score @s cy.snk matches 0 run function {NS}:os/press",
        f"execute store success score @s cy.snk if predicate {NS}:sneaking",
    ])
    fn("os/press", [
        f"execute if score @s cy.tap matches ..7 run return run function {NS}:os/activate",
        "scoreboard players set @s cy.tap 0",
    ])
    fn("os/activate", [
        "scoreboard players set @s cy.tap 100",
        "execute if score @s cy.cd matches 1.. run return run title @s actionbar {\"text\":\"Operating System cooling down\",\"color\":\"gray\"}",
        f"execute if score @s cy.s9 matches 13 run function {NS}:fx/sandy",
        f"execute if score @s cy.s9 matches 14 run function {NS}:fx/berserk",
    ])
    fn("fx/sandy", [
        f"scoreboard players set @s cy.cd {OS_CD[13]}",
        "effect give @s minecraft:speed 6 3", "effect give @s minecraft:haste 6 1", "effect give @s minecraft:jump_boost 6 0",
        "effect give @e[distance=0.01..12,type=!minecraft:armor_stand,tag=!cy.ghost] minecraft:slowness 6 2",
        f"scoreboard players set @s cy.sv {GHOST_TICKS}",
        # an item_display holding the player's head carries their skin for the after-images; it follows the player
        "summon minecraft:item_display ~ ~ ~ {Tags:[\"cy.ganchor\",\"cy.anew\"]}",
        f"loot replace entity @n[type=minecraft:item_display,tag=cy.anew] contents loot {NS}:head",
        f"scoreboard players set @n[type=minecraft:item_display,tag=cy.anew] cy.gl {GHOST_TICKS + 5}",
        "tag @e[type=minecraft:item_display,tag=cy.anew] remove cy.anew",
        "playsound minecraft:block.beacon.power_select player @a[distance=..16] ~ ~ ~ 1 2",
        "particle minecraft:electric_spark ~ ~1 ~ 2 1 2 0.5 200",
        "title @s actionbar {\"text\":\"◆ SANDEVISTAN\",\"color\":\"aqua\",\"bold\":true}",
    ])
    # ------------------------------------------------------------------ Sandevistan after-images (Edgerunners)
    # Every 2 ticks while active, a mannequin copy of the player (skin, facing, armor, held items, crouch) is left
    # behind with a random neon glow; each lives GHOST_LIFE ticks, so a short trail follows the player.
    wj(f"data/{NS}/loot_table/head.json", {"pools": [{"rolls": 1, "entries": [{"type": "minecraft:item", "name": "minecraft:player_head",
        "functions": [{"function": "minecraft:fill_player_head", "entity": "this"}]}]}]})
    fn("ghost/player", [
        "scoreboard players remove @s cy.sv 1",
        "tp @n[type=minecraft:item_display,tag=cy.ganchor,distance=..8] @s",
        "scoreboard players operation #m cy = @s cy.sv", "scoreboard players operation #m cy %= #2 cy",
        f"execute if score #m cy matches 0 run function {NS}:ghost/spawn",
    ])
    fn("ghost/spawn", [
        "summon minecraft:mannequin ~ ~ ~ {Tags:[\"cy.ghost\",\"cy.gnew\"],NoGravity:1b,Invulnerable:1b,Silent:1b,immovable:1b,hide_description:1b,Glowing:1b}",
        "execute rotated as @s run tp @n[type=minecraft:mannequin,tag=cy.gnew] ~ ~ ~ ~ ~",
        "data modify entity @n[type=minecraft:mannequin,tag=cy.gnew] profile set from entity @n[type=minecraft:item_display,tag=cy.ganchor,distance=..1] item.components.\"minecraft:profile\"",
        *[f"item replace entity @n[type=minecraft:mannequin,tag=cy.gnew] {sl} from entity @s {sl}"
          for sl in ("armor.head", "armor.chest", "armor.legs", "armor.feet", "weapon.mainhand", "weapon.offhand")],
        f"execute if predicate {NS}:sneaking run data modify entity @n[type=minecraft:mannequin,tag=cy.gnew] pose set value \"crouching\"",
        f"scoreboard players set @n[type=minecraft:mannequin,tag=cy.gnew] cy.gl {GHOST_LIFE}",
        f"execute store result score #c cy run random value 1..{len(GHOST_COLORS)}",
        *[f"execute if score #c cy matches {n} run team join cy.g{n} @n[type=minecraft:mannequin,tag=cy.gnew]" for n in range(1, len(GHOST_COLORS) + 1)],
        "tag @e[type=minecraft:mannequin,tag=cy.gnew] remove cy.gnew",
    ])
    fn("ghost/age", [
        "scoreboard players remove @s cy.gl 1",
        f"execute unless score @s cy.gl matches 1.. run function {NS}:ghost/remove",
    ])
    fn("ghost/remove", [   # empty the copied gear first so nothing drops, then vanish below the world (no death animation)
        "data modify entity @s[type=minecraft:mannequin] equipment set value {}",
        "execute at @s run tp @s ~ -1000 ~",
        "kill @s",
    ])

    # ------------------------------------------------------------------ Projectile Launch System
    fn("arms/tick", [
        f"execute if score @s cy.jump matches 1.. if predicate {NS}:sneaking run function {NS}:arms/fire",
        "scoreboard players set @s cy.jump 0",
    ])
    fn("arms/fire", [
        "execute if score @s cy.lcd matches 1.. run return run title @s actionbar {\"text\":\"Launcher reloading\",\"color\":\"gray\"}",
        f"scoreboard players set @s cy.lcd {LAUNCH_CD}",
        # a ghast-style fireball from the eyes, aimed by the gap between two points along the look direction
        f"execute anchored eyes positioned ^ ^ ^1.2 run summon minecraft:fireball ~ ~ ~ {{Tags:[\"cy.round\",\"cy.rnew\"],ExplosionPower:{LAUNCH_POWER}b}}",
        "execute anchored eyes positioned ^ ^ ^2.2 run summon minecraft:marker ~ ~ ~ {Tags:[\"cy.aim\"]}",
        *[l for i in range(3) for l in (
            f"execute store result score #a cy run data get entity @n[type=minecraft:marker,tag=cy.aim] Pos[{i}] 1000",
            f"execute store result score #b cy run data get entity @n[type=minecraft:fireball,tag=cy.rnew] Pos[{i}] 1000",
            "scoreboard players operation #a cy -= #b cy",
            f"execute store result entity @n[type=minecraft:fireball,tag=cy.rnew] Motion[{i}] double {LAUNCH_SPEED / 1000} run scoreboard players get #a cy")],
        "data modify entity @n[type=minecraft:fireball,tag=cy.rnew] Owner set from entity @s UUID",
        "kill @e[type=minecraft:marker,tag=cy.aim]",
        "tag @e[type=minecraft:fireball,tag=cy.rnew] remove cy.rnew",
        "playsound minecraft:entity.blaze.shoot player @a[distance=..24] ~ ~ ~ 1 0.7",
        "playsound minecraft:item.crossbow.shoot player @a[distance=..24] ~ ~ ~ 1 0.6",
        "particle minecraft:smoke ^-0.4 ^1.2 ^0.6 0.1 0.1 0.1 0.02 8",
        "title @s actionbar {\"text\":\"◆ PROJECTILE LAUNCHED\",\"color\":\"gold\",\"bold\":true}",
    ])

    fn("fx/berserk", [
        f"scoreboard players set @s cy.cd {OS_CD[14]}",
        "effect give @s minecraft:strength 8 1", "effect give @s minecraft:resistance 8 0", "effect give @s minecraft:glowing 8 0",
        "playsound minecraft:entity.ravager.roar player @a[distance=..16] ~ ~ ~ 1 1.2",
        "particle minecraft:angry_villager ~ ~1 ~ 0.5 0.6 0.5 0 20",
        "title @s actionbar {\"text\":\"◆ BERSERK\",\"color\":\"red\",\"bold\":true}",
    ])
    fn("fx/biomon", [
        "scoreboard players set @s cy.cdh 1800",
        "effect give @s minecraft:regeneration 6 1", "effect give @s minecraft:absorption 30 0",
        "playsound minecraft:block.note_block.chime player @s ~ ~ ~ 1 1.5",
        "title @s actionbar {\"text\":\"Biomonitor: emergency regen\",\"color\":\"green\"}",
    ])
    fn("fx/heart", [
        "scoreboard players set @s cy.cdh 12000",
        "effect give @s minecraft:instant_health 1 2", "effect give @s minecraft:absorption 60 1",
        "effect give @s minecraft:fire_resistance 10 0",
        "playsound minecraft:item.totem.use player @a[distance=..16] ~ ~ ~ 0.8 1.4",
        "particle minecraft:heart ~ ~1 ~ 0.5 0.6 0.5 0 15",
        "title @s actionbar {\"text\":\"♥ SECOND HEART\",\"color\":\"dark_red\",\"bold\":true}",
    ])

    # ------------------------------------------------------------------ cyberpsychosis
    # Each second over the limit: chance = excess / 600 (10 over -> about one episode a minute), 30 s minimum gap.
    fn("psycho/roll", [
        "scoreboard players operation #ex cy = @s cy.cap", "scoreboard players operation #ex cy -= #limit cy",
        "execute store result score #r cy run random value 1..600",
        f"execute if score #r cy <= #ex cy run function {NS}:psycho/episode",
    ])
    fn("psycho/episode", [
        "scoreboard players set @s cy.pcd 30",
        "execute store result score #e cy run random value 1..5",
        "title @s title {\"text\":\"CYBERPSYCHOSIS\",\"color\":\"dark_red\",\"bold\":true}",
        "playsound minecraft:entity.warden.heartbeat player @s ~ ~ ~ 1 0.6",
        "tellraw @a[distance=0.01..32] [{\"selector\":\"@s\",\"color\":\"red\"},{\"text\":\" is showing signs of cyberpsychosis!\",\"color\":\"red\"}]",
        "execute if score #e cy matches 1 run effect give @s minecraft:nausea 12 0",
        "execute if score #e cy matches 1 run effect give @s minecraft:darkness 6 0",
        "execute if score #e cy matches 2 run effect give @s minecraft:strength 15 0",
        "execute if score #e cy matches 2 run effect give @s minecraft:glowing 15 0",
        "execute if score #e cy matches 2 run title @s subtitle {\"text\":\"You see red...\",\"color\":\"red\"}",
        "execute if score #e cy matches 3 run effect give @s minecraft:blindness 5 0",
        "execute if score #e cy matches 3 run title @s subtitle {\"text\":\"Optics glitching\",\"color\":\"gray\"}",
        "execute if score #e cy matches 4 run damage @s 4 minecraft:magic",
        "execute if score #e cy matches 4 run title @s subtitle {\"text\":\"Chrome rejection\",\"color\":\"gray\"}",
        "execute if score #e cy matches 5 run effect give @s minecraft:hunger 15 2",
        "execute if score #e cy matches 5 run effect give @s minecraft:weakness 15 0",
    ])


if __name__ == "__main__":
    if "--pvp" in sys.argv: sys.argv.remove("--pvp"); DROP_ON_DEATH = False
    OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist"), "crispy_cyberware")
    build()
    n = sum(len(f) for _, _, f in os.walk(OUT))
    print(f"built {OUT} ({n} files)")
