#!/usr/bin/env python3
"""Builds the crispy_pvp datapack (Crispy PvP, Fabric 26.2, vanilla clients).

    python3 build.py [outdir]      -> <outdir>/crispy_pvp  (default: ./dist)

Kit/arena PvP that reuses Anarchy's custom enchants (crispy_enchants) and cyberware (crispy_cyberware, built with
--pvp so implants don't drop). Players spawn in a safe lobby, pick a kit from the Kit Dealer, get dropped at a
random arena spawn, and return to the lobby when they die.
"""
import json, os, shutil, sys

NS = "pvp"
PACK_FORMAT = [107, 0], [107, 1]

LOBBY_Y = 100                  # lobby floor; players stand at LOBBY_Y + 1, centred on 0,0
LOBBY_R = 11                   # lobby platform half-size
AY = -61                       # arena floor (superflat grass level); players stand at AY + 1
ACX, ACZ, AR = 0, 100, 30      # arena centre and half-size
NPC = (0.5, LOBBY_Y + 1, -6.5)

LOBBY_BOX = f"x={-LOBBY_R - 1},y={LOBBY_Y - 1},z={-LOBBY_R - 1},dx={2 * LOBBY_R + 2},dy=20,dz={2 * LOBBY_R + 2}"
ARENA_BOX = f"x={ACX - AR - 1},y={AY - 1},z={ACZ - AR - 1},dx={2 * AR + 2},dy=35,dz={2 * AR + 2}"

# arena spawn points: offset from the centre, and yaw facing the centre
SPAWNS = [(24, 0, 90), (-24, 0, -90), (0, -24, 0), (0, 24, 180), (20, -20, 45), (-20, -20, -45), (20, 20, 135), (-20, 20, -135)]

# cover: (x1, z1, x2, z2, height, stripe colour, hollow-with-doors) offsets from the arena centre
BUILDINGS = [
    (-3, -3, 3, 3, 10, "cyan", True),
    (-15, -15, -9, -9, 6, "magenta", True), (9, -15, 15, -9, 4, "yellow", True),
    (-15, 9, -9, 15, 4, "yellow", True), (9, 9, 15, 15, 6, "magenta", True),
    (-2, -18, 2, -17, 3, "light_blue", False), (-2, 17, 2, 18, 3, "light_blue", False),
    (-18, -2, -17, 2, 3, "light_blue", False), (17, -2, 18, 2, 3, "light_blue", False),
    (-8, -1, -7, 1, 2, "lime", False), (7, -1, 8, 1, 2, "lime", False),
    (-1, -8, 1, -7, 2, "lime", False), (-1, 7, 1, 8, 2, "lime", False),
]


def ench(d): return "{" + ",".join(f'"{k if ":" in k else "minecraft:" + k}":{v}' for k, v in d.items()) + "}"
def item(id_, name=None, color="white", enchants=None, extra=""):
    comps = ["minecraft:unbreakable={}"]
    if enchants: comps.append(f"minecraft:enchantments={ench(enchants)}")
    if name: comps.append(f'minecraft:custom_name={{"text":"{name}","color":"{color}","italic":false}}')
    if extra: comps.append(extra)
    return f"minecraft:{id_}[{','.join(comps)}]"
def armor(mat, prot, extra_chest=None, extra_legs=None, dye=None):
    d = f"minecraft:dyed_color={dye}" if dye else ""
    out = []
    for slot, piece, ex in (("head", "helmet", None), ("chest", "chestplate", extra_chest), ("legs", "leggings", extra_legs), ("feet", "boots", None)):
        m = mat[slot] if isinstance(mat, dict) else mat
        e = {"protection": prot, **(ex or {})}
        out.append(f"item replace entity @s armor.{slot} with {item(f'{m}_{piece}', enchants=e, extra=d if m == 'leather' else '')}")
    return out

CE = "crispy_enchants:"
FOOD = ["give @s minecraft:cooked_beef 16", "give @s minecraft:golden_apple 2"]
# id, key, name, colour, blurb, item commands, implants
KITS = [
    (1, "samurai", "Edgerunner", "aqua", "Katana with Lifesteal + Double Strike · Sandevistan, Mantis Blades, Reflex Tuner, Kiroshi",
     [f"give @s {item('netherite_sword', 'Edgerunner Katana', 'aqua', {'sharpness': 5, CE + 'lifesteal': 3, CE + 'doublestrike': 2})}"]
     + armor("diamond", 3), ["sandy", "mantis", "reflex", "kiroshi"]),
    (2, "tank", "Juggernaut", "gray", "Netherite + Armored/Tank, shield · Subdermal Armor, Titanium Bones, Second Heart, Lynx Paws",
     [f"give @s {item('netherite_sword', 'Breaker', 'gray', {'sharpness': 3})}",
      f"item replace entity @s weapon.offhand with {item('shield')}"]
     + armor("netherite", 4, extra_chest={CE + "armored": 3}, extra_legs={CE + "tank": 2}),
     ["subdermal", "titanium", "heart", "lynx"]),
    (3, "sniper", "Sniper", "green", "Bow with Lethal Sniper + Lightning Arrows · Kiroshi, Reinforced Tendons, Biomonitor, Reflex Tuner",
     [f"give @s {item('bow', 'Overwatch', 'green', {'power': 5, 'infinity': 1, CE + 'lethalsniper': 3, CE + 'lightningarrows': 2})}",
      f"give @s {item('iron_sword', enchants={'sharpness': 2})}", "give @s minecraft:arrow 1"]
     + armor("diamond", 2), ["kiroshi", "tendons", "biomon", "reflex"]),
    (4, "berserker", "Berserker", "red", "Axe with Cleave, Bleed + Rage · Gorilla Arms, Berserk, Titanium Bones",
     [f"give @s {item('netherite_axe', 'Ripper', 'red', {'sharpness': 5, CE + 'cleave': 3, CE + 'bleed': 3, CE + 'rage': 2})}"]
     + armor("diamond", 3), ["gorilla", "berserk", "titanium"]),
    (5, "assassin", "Netrunner", "dark_purple", "Assassin + Poison blade, invisibility · Sandevistan, Lynx Paws, Reflex Tuner, Reinforced Tendons",
     [f"give @s {item('diamond_sword', 'Monowire', 'dark_purple', {'sharpness': 4, CE + 'assassin': 3, CE + 'poison': 2})}",
      'give @s minecraft:splash_potion[minecraft:potion_contents={potion:"minecraft:invisibility"}] 1']
     + armor({"head": "diamond", "chest": "leather", "legs": "leather", "feet": "diamond"}, 2, dye=1908001),
     ["sandy", "lynx", "reflex", "tendons"]),
]

OUT = None
def w(path, text):
    p = os.path.join(OUT, path); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f: f.write(text if text.endswith("\n") else text + "\n")
def wj(path, obj): w(path, json.dumps(obj, indent=1, ensure_ascii=False))
def fn(name, lines): w(f"data/{NS}/function/{name}.mcfunction", "\n".join(l for l in lines if l is not None))


def build():
    shutil.rmtree(OUT, ignore_errors=True)
    wj("pack.mcmeta", {"pack": {"description": "Crispy PvP: kit arena with custom enchants + cyberware (26.2)",
                                "min_format": PACK_FORMAT[0], "max_format": PACK_FORMAT[1]}})
    wj("data/minecraft/tags/function/load.json", {"values": [f"{NS}:load"]})
    wj("data/minecraft/tags/function/tick.json", {"values": [f"{NS}:tick"]})

    rules = {"keep_inventory": "true", "immediate_respawn": "true", "spawn_mobs": "false", "advance_time": "false",
             "advance_weather": "false", "show_advancement_messages": "false", "respawn_radius": "0", "locator_bar": "false",
             "spawn_phantoms": "false", "mob_griefing": "false", "spawn_wandering_traders": "false", "raids": "false",
             "spawn_patrols": "false", "ender_pearls_vanish_on_death": "true", "command_block_output": "false"}
    fn("load", [
        *[f"scoreboard objectives add {o}" for o in [
            "pvp dummy", "pvp.kit trigger", "pvp.spawn trigger", "pvp.kn playerKillCount", "pvp.dead deathCount",
            "pvp.left minecraft.custom:minecraft.leave_game", "pvp.streak dummy", "pvp.best dummy",
            "pvp.hurt minecraft.custom:minecraft.damage_taken", "pvp.ct dummy"]],
        'scoreboard objectives add pvp.kills playerKillCount {"text":"⚔ Kills","color":"aqua","bold":true}',
        "scoreboard objectives setdisplay sidebar pvp.kills",
        *[f"gamerule {k} {v}" for k, v in rules.items()],
        "time set 18000", "weather clear", f"setworldspawn 0 {LOBBY_Y + 1} 0", "scoreboard players set #t pvp 0",
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
        "scoreboard players add #t pvp 1", f"execute if score #t pvp matches 20.. run function {NS}:second",
    ])
    fn("second", [
        "scoreboard players set #t pvp 0",
        f"effect give @a[{LOBBY_BOX}] minecraft:resistance 3 4 true",
        f"effect give @a[{LOBBY_BOX}] minecraft:weakness 3 255 true",
        f"effect give @a[{LOBBY_BOX}] minecraft:saturation 3 0 true",
        # anyone (in adventure) outside both the lobby and the arena goes back to the lobby
        f"execute as @a[gamemode=adventure] unless entity @s[{LOBBY_BOX}] unless entity @s[{ARENA_BOX}] run function {NS}:to_lobby",
    ])
    fn("to_lobby", [
        "clear @s", "effect clear @s", "function cyber:admin/reset", "gamemode adventure @s",
        f"tp @s 0.5 {LOBBY_Y + 1} 0.5 180 0",
        "scoreboard players set @s pvp.left 0", "scoreboard players set @s pvp.ct 0",
        "scoreboard players add @s pvp.streak 0", "scoreboard players add @s pvp.kills 0",
        "tag @s add pvp.seen",
        "title @s actionbar {\"text\":\"Right-click the Kit Dealer to fight\",\"color\":\"aqua\"}",
    ])
    fn("trigger_lobby", [
        "scoreboard players set @s pvp.spawn 0",
        "execute if score @s pvp.ct matches 1.. run return run tellraw @s {\"text\":\"You can't leave combat yet (10 s after taking damage).\",\"color\":\"red\"}",
        f"function {NS}:to_lobby",
    ])
    fn("respawned", [
        "scoreboard players set @s pvp.dead 0",
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

    # kits
    pick = ["scoreboard players operation #k pvp = @s pvp.kit", "scoreboard players set @s pvp.kit 0",
            f"execute unless entity @s[{LOBBY_BOX}] run return run tellraw @s {{\"text\":\"Pick a kit in the lobby (/trigger pvp.spawn).\",\"color\":\"red\"}}",
            "clear @s", "effect clear @s", "function cyber:admin/reset"]
    for (kid, key, name, color, blurb, items, implants) in KITS:
        pick.append(f"execute if score #k pvp matches {kid} run function {NS}:kit/{key}")
        fn(f"kit/{key}", items + FOOD + [f"function cyber:implant/{i}/kit" for i in implants] + [
            f"tellraw @s [{{\"text\":\"Kit: \",\"color\":\"gray\"}},{{\"text\":\"{name}\",\"color\":\"{color}\",\"bold\":true}},"
            f"{{\"text\":\" (cyberware installed)\",\"color\":\"gray\"}}]",
            *(["tellraw @s {\"text\":\"Double-tap sneak to activate your Operating System implant.\",\"color\":\"dark_gray\"}"]
              if any(i in ("sandy", "berserk") for i in implants) else [])])
    pick.append(f"execute if score #k pvp matches 1..{len(KITS)} run function {NS}:arena/enter")
    fn("kit/pick", pick)

    enter = ["execute store result score #r pvp run random value 1..%d" % len(SPAWNS)]
    for n, (dx, dz, yaw) in enumerate(SPAWNS, 1):
        enter.append(f"execute if score #r pvp matches {n} run tp @s {ACX + dx + 0.5} {AY + 1} {ACZ + dz + 0.5} {yaw} 0")
    enter += ["effect give @s minecraft:resistance 3 4 true", "scoreboard players set @s pvp.ct 0",
              "title @s title {\"text\":\"FIGHT\",\"color\":\"red\",\"bold\":true}",
              "playsound minecraft:block.beacon.power_select player @s ~ ~ ~ 1 1.4"]
    fn("arena/enter", enter)

    # Kit Dealer NPC + dialog
    def btn(label, color, tip, cmd):
        return {"label": {"text": label, "color": color, "bold": True}, "tooltip": {"text": tip}, "width": 260,
                "action": {"type": "minecraft:run_command", "command": cmd}}
    wj(f"data/{NS}/dialog/kits.json", {
        "type": "minecraft:multi_action", "columns": 1, "can_close_with_escape": True, "pause": False, "after_action": "close",
        "exit_action": {"label": {"text": "Close"}, "width": 150},
        "title": {"text": "⚔ Kit Dealer ⚔", "color": "aqua", "bold": True},
        "body": [{"type": "minecraft:plain_message", "width": 310, "contents": [
            {"text": "Pick a kit and drop into the arena. Every kit comes with custom enchants and installed cyberware.\n", "color": "gray"},
            {"text": "Kills heal you and give a golden apple. Die and you're back here.\n", "color": "gray"},
            {"text": "/trigger pvp.spawn returns to the lobby (not within 10 s of taking damage).", "color": "dark_gray"}]}],
        "actions": [btn(name, color, blurb, f"trigger pvp.kit set {kid}") for (kid, key, name, color, blurb, *_r) in KITS]})
    wj(f"data/{NS}/advancement/npc.json", {"criteria": {"c": {"trigger": "minecraft:player_interacted_with_entity", "conditions": {"entity": [{
        "condition": "minecraft:entity_properties", "entity": "this",
        "predicate": {"minecraft:entity_type": "minecraft:interaction", "minecraft:nbt": "{Tags:[\"pvp.npc\"]}"}}]}}},
        "rewards": {"function": f"{NS}:npc_open"}})
    fn("npc_open", [f"advancement revoke @s only {NS}:npc", f"dialog show @s {NS}:kits",
                    "execute as @e[type=minecraft:interaction,tag=pvp.npc,distance=..8] run data remove entity @s interaction"])

    # ------------------------------------------------------------------ admin: build the lobby + arena (chunks must be loaded)
    x, y, z = NPC
    fn("admin/place_npc", [
        "kill @e[tag=pvp.npc]", "kill @e[tag=pvp.holo]",
        f"summon minecraft:villager {x} {y} {z} {{Tags:[\"pvp.npc\"],Rotation:[0f,0f],NoAI:1b,Invulnerable:1b,Silent:1b,PersistenceRequired:1b,"
        "CustomNameVisible:1b,CustomName:{\"text\":\"⚔ Kit Dealer ⚔\",\"color\":\"aqua\",\"bold\":true},"
        "VillagerData:{profession:\"minecraft:weaponsmith\",level:5,type:\"minecraft:snow\"},Offers:{Recipes:[]}}",
        f"summon minecraft:interaction {x} {y} {z} {{Tags:[\"pvp.npc\"],width:1.2f,height:2.2f,response:1b}}",
        f"summon minecraft:text_display 0.5 {LOBBY_Y + 6} {-LOBBY_R + 1.5} {{Tags:[\"pvp.holo\"],billboard:\"center\",background:0,"
        "transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[3f,3f,3f]},"
        "text:{\"text\":\"CRISPY PVP\",\"color\":\"aqua\",\"bold\":true}}",
        f"summon minecraft:text_display 0.5 {LOBBY_Y + 4.6} {-LOBBY_R + 1.5} {{Tags:[\"pvp.holo\"],billboard:\"center\",background:0,"
        "text:[{\"text\":\"Custom enchants \",\"color\":\"light_purple\"},{\"text\":\"+ \",\"color\":\"gray\"},{\"text\":\"cyberware\",\"color\":\"aqua\"},"
        "{\"text\":\"\\nRight-click the Kit Dealer to fight\",\"color\":\"gray\"}]}",
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
    # clear the arena in 5-high slices (fill is capped at 32768 blocks)
    ar = [f"fill {x1} {AY + 1 + k} {z1} {x2} {AY + 5 + k} {z2} minecraft:air" for k in range(0, 30, 5)]
    ar.append(f"fill {x1} {AY} {z1} {x2} {AY} {z2} minecraft:black_concrete")
    for k in range(-AR, AR + 1, 6):
        ar += [f"fill {ACX + k} {AY} {z1} {ACX + k} {AY} {z2} minecraft:gray_concrete", f"fill {x1} {AY} {ACZ + k} {x2} {AY} {ACZ + k} minecraft:gray_concrete"]
    for i in range(-AR, AR + 1, 6):
        for j in range(-AR, AR + 1, 6):
            ar.append(f"setblock {ACX + i} {AY} {ACZ + j} minecraft:sea_lantern")
    W1, W2, Z1, Z2 = x1 - 1, x2 + 1, z1 - 1, z2 + 1
    for (a1, b1, a2, b2) in ((W1, Z1, W2, Z1), (W1, Z2, W2, Z2), (W1, Z1, W1, Z2), (W2, Z1, W2, Z2)):
        ar += [f"fill {a1} {AY} {b1} {a2} {AY + 5} {b2} minecraft:black_concrete",
               f"fill {a1} {AY + 4} {b1} {a2} {AY + 4} {b2} minecraft:cyan_concrete",
               f"fill {a1} {AY + 6} {b1} {a2} {AY + 30} {b2} minecraft:barrier"]
    ar.append(f"fill {W1} {AY + 31} {Z1} {W2} {AY + 31} {Z2} minecraft:barrier")
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
    fn("admin/build", [f"function {NS}:admin/build_lobby", f"function {NS}:admin/build_arena"])


if __name__ == "__main__":
    OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist"), "crispy_pvp")
    build()
    print(f"built {OUT} ({sum(len(f) for _, _, f in os.walk(OUT))} files)")
