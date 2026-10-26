"""The Tower: a roguelite climb for the Multiverse server (imported by build.py).

Solo or up to 4 players. Everyone starts as a random character. Each floor is a mob fight, a parkour run over magma
(every 4th floor, 3/7/11...) or a boss (every 5th). After each floor everyone picks 1 of 3 random upgrades (clickable
chat lines), which stack for the whole run. Dying is the end of your climb unless you have an Extra Life; the run is
over when nobody is left. Best floor per player in tw.best, the server record in #trecord tw.

One room, rebuilt for every floor: interior x/z -R..R around (TCX, TCZ), floor blocks at TY, players stand on TY + 1.
State (#tstate tw): 0 idle, 1 countdown (queue open), 2 floor in progress, 3 picking upgrades.
Floor type (#ttype tw): 1 mobs, 2 parkour, 3 boss.
"""
import random

NS = "pvp"
TCX, TCZ, R = 400, 0, 12           # room centre and interior half-size (walls at +-13)
WALL_H = 12                        # ceiling (barrier) at TY + WALL_H
MAX_PLAYERS = 4
COUNTDOWN = 10                     # s the queue stays open after the first click
PICK_SECS = 20                     # s to pick an upgrade (then it's picked for you)
LAYOUTS = 6                        # mob-room and parkour layouts generated per kind
FLOOR_XP = 5                       # mastery XP per floor cleared, for the character you're playing

# id, name, colour, description, attribute modifiers [(attribute, step per stack, operation)]
UPGRADES = [
    (1, "Vitality", "red", "+2 max hearts", [("max_health", 4, "add_value")]),
    (2, "Sharpened", "gold", "+15% melee damage", [("attack_damage", 0.15, "add_multiplied_total")]),
    (3, "Swift", "aqua", "+10% movement speed", [("movement_speed", 0.10, "add_multiplied_base")]),
    (4, "Plated", "gray", "+3 armor", [("armor", 3, "add_value")]),
    (5, "Frenzy", "yellow", "+15% attack speed", [("attack_speed", 0.15, "add_multiplied_total")]),
    (6, "Spring Step", "green", "Jump higher, take less fall damage", [("jump_strength", 0.06, "add_value"), ("safe_fall_distance", 2, "add_value")]),
    (7, "Juggernaut", "dark_gray", "+25% knockback resistance", [("knockback_resistance", 0.25, "add_value")]),
    (8, "Vampire", "dark_red", "Every kill gives you Regeneration", []),
    (9, "Second Wind", "light_purple", "Full heal now + 2 golden apples", []),
    (10, "Extra Life", "green", "Come back once when you die", []),
    (11, "Glass Cannon", "red", "+40% melee damage, but -2 max hearts", [("attack_damage", 0.40, "add_multiplied_total"), ("max_health", -4, "add_value")]),
]
# every modifier id the Tower ever adds (removed when you leave, with the other per-run perks)
MOD_IDS = [(f"{NS}:tw_u{u[0]}_{i}", a) for u in UPGRADES for i, (a, _, _) in enumerate(u[4])] + \
          [(f"{NS}:tw_mobhp", "max_health"), (f"{NS}:tw_mobdmg", "attack_damage")]
PERK_RESET = [f"attribute @s minecraft:{a} modifier remove {i}" for i, a in MOD_IDS]

# mob pools by tier (tier = floor / 5, capped); each entry: type, extra NBT
POOLS = [
    [("zombie", ""), ("skeleton", ""), ("spider", ""), ("zombie", "")],
    [("husk", ""), ("stray", ""), ("cave_spider", ""), ("zombie", ',equipment:{head:{id:"minecraft:iron_helmet",count:1}}')],
    [("vindicator", ',equipment:{mainhand:{id:"minecraft:iron_axe",count:1}}'), ("wither_skeleton", ',equipment:{mainhand:{id:"minecraft:stone_sword",count:1}}'),
     ("husk", ""), ("stray", "")],
    [("blaze", ""), ("wither_skeleton", ',equipment:{mainhand:{id:"minecraft:stone_sword",count:1}}'),
     ("piglin_brute", ',equipment:{mainhand:{id:"minecraft:golden_axe",count:1}}'), ("vindicator", ',equipment:{mainhand:{id:"minecraft:iron_axe",count:1}}')],
]
NODROP = ",drop_chances:{mainhand:0.0f,offhand:0.0f,head:0.0f,chest:0.0f,legs:0.0f,feet:0.0f}"
# bosses, every 5th floor in turn: type, name, colour, scale, extra NBT
BOSSES = [
    ("zombie", "The Brute", "dark_green", 2.0, ',equipment:{mainhand:{id:"minecraft:iron_axe",count:1}}'),
    ("skeleton", "Bone King", "white", 1.8, ',equipment:{mainhand:{id:"minecraft:bow",count:1},head:{id:"minecraft:golden_helmet",count:1}}'),
    ("vindicator", "The Warlord", "gray", 1.7, ',equipment:{mainhand:{id:"minecraft:diamond_axe",count:1}}'),
    ("ravager", "The Beast", "dark_red", 1.0, ""),
]
# where mobs come in: the north half, along the walls
SPAWN_PTS = [(x, -10) for x in (-10, -5, 0, 5, 10)] + [(-10, -4), (10, -4), (-10, 2), (10, 2)]
START = {1: (0.5, 1, 9.5), 2: (0.5, 3, 10.5), 3: (0.5, 1, 9.5)}   # player start per floor type (y relative to TY)


def build(b):
    """b: the build module (fn, wj, tj, say, npc, box, constants)."""
    fn, wj, tj, say = b.fn, b.wj, b.tj, b.say
    TY = b.AY
    T = f"{NS}:tower"
    BOX = b.box(TCX, TCZ, R + 1, TY - 1, WALL_H + 4)
    at = lambda x, y, z: f"{TCX + x} {TY + y} {TCZ + z}"
    start_tp = {k: f"tp @s {TCX + x} {TY + y} {TCZ + z} 180 0" for k, (x, y, z) in START.items()}
    inn = "@a[tag=tw.in]"

    # ------------------------------------------------------------------ load / tick / second
    fn("tower/load", [
        *[f"scoreboard objectives add {o}" for o in ["tw dummy", "tw.pick trigger", "tw.o1 dummy", "tw.o2 dummy", "tw.o3 dummy",
                                                     "tw.lives dummy", "tw.best dummy", "tw.kc totalKillCount",
                                                     *[f"tw.u{u[0]} dummy" for u in UPGRADES]]],
        "team add tower", "team modify tower color light_purple", "team modify tower friendlyFire false",
        "team modify tower seeFriendlyInvisibles true",
        'bossbar add pvp:tower {"text":"Boss"}', "bossbar set pvp:tower color purple", "bossbar set pvp:tower visible false",
        "execute unless score #tstate tw matches 0.. run scoreboard players set #tstate tw 0",
        "execute unless score #trecord tw matches 0.. run scoreboard players set #trecord tw 0",
        f"forceload add {TCX - R - 1} {TCZ - R - 1} {TCX + R + 1} {TCZ + R + 1}",
    ])
    fn("tower/tick", [
        f"scoreboard players enable {inn} tw.pick",
        f"execute as @a[tag=tw.in,scores={{tw.pick=1..}}] run function {T}/picked",
        f"execute if score #tstate tw matches 2 if score #ttype tw matches 2 as {inn} at @s if block ~ ~-0.2 ~ minecraft:magma_block run function {T}/fell",
        f"execute if score #tstate tw matches 2 if score #ttype tw matches 2 as {inn} at @s if block ~ ~-0.2 ~ minecraft:gold_block run function {T}/clear",
    ])
    fn("tower/second", [f"execute if score #tstate tw matches 1.. run function {T}/sec"])
    fn("tower/sec", [
        # the queue: keep only players still in the lobby
        f"execute if score #tstate tw matches 1 as @a[tag=tw.q] unless entity @s[{b.LOBBY_BOX}] run tag @s remove tw.q",
        "execute if score #tstate tw matches 1 unless entity @a[tag=tw.q] run return run scoreboard players set #tstate tw 0",
        "execute if score #tstate tw matches 1 run scoreboard players remove #tt tw 1",
        "execute if score #tstate tw matches 1 run title @a[tag=tw.q] actionbar " + tj([{"text": "🗼 The Tower starts in ", "color": "light_purple"},
                                                                                     {"score": {"name": "#tt", "objective": "tw"}, "color": "white", "bold": True},
                                                                                     {"text": " s", "color": "light_purple"}]),
        f"execute if score #tstate tw matches 1 if score #tt tw matches ..0 run return run function {T}/start",
        # a run with nobody left in it is over
        f"execute if score #tstate tw matches 2.. unless entity {inn} run return run function {T}/game_over",
        f"bossbar set pvp:tower players {inn}",
        f"kill @e[type=minecraft:item,{BOX}]", f"kill @e[type=minecraft:experience_orb,{BOX}]",
        # Vampire: Regeneration for kills since last second
        f"execute as @a[tag=tw.in,scores={{tw.kc=1..,tw.u8=1..}}] run effect give @s minecraft:regeneration 3 1",
        f"scoreboard players set {inn} tw.kc 0",
        f"execute if score #tstate tw matches 2 unless score #ttype tw matches 2 run function {T}/sec_fight",
        "execute if score #tstate tw matches 2 if score #ttype tw matches 2 run title @a[tag=tw.in] actionbar " + tj(
            [{"text": "🗼 Floor ", "color": "light_purple"}, {"score": {"name": "#floor", "objective": "tw"}, "color": "white", "bold": True},
             {"text": " · reach the gold block · don't touch the magma", "color": "gray"}]),
        f"execute if score #tstate tw matches 3 run function {T}/sec_pick",
    ])
    fn("tower/sec_fight", [
        f"execute store result score #m tw if entity @e[tag=tw.mob,{BOX}]",
        f"kill @e[tag=tw.mob,tag=!tw.boss,y={TY - 30},dy=29.5]",   # anything that fell out of the room
        f"execute if score #ttype tw matches 3 store result bossbar pvp:tower value run data get entity @n[tag=tw.boss] Health",
        f"execute if score #m tw matches 0 run return run function {T}/clear",
        "title @a[tag=tw.in] actionbar " + tj([{"text": "🗼 Floor ", "color": "light_purple"}, {"score": {"name": "#floor", "objective": "tw"}, "color": "white", "bold": True},
                                               {"text": " · ", "color": "gray"}, {"score": {"name": "#m", "objective": "tw"}, "color": "red", "bold": True},
                                               {"text": " left", "color": "gray"}]),
    ])
    fn("tower/sec_pick", [
        "scoreboard players remove #tt tw 1",
        f"execute if score #tt tw matches ..0 as @a[tag=tw.in,tag=!tw.picked] run function {T}/autopick",
        f"execute unless entity @a[tag=tw.in,tag=!tw.picked] run return run function {T}/next",
        "title @a[tag=tw.in,tag=!tw.picked] actionbar " + tj([{"text": "Pick an upgrade in chat · ", "color": "light_purple"},
                                                              {"score": {"name": "#tt", "objective": "tw"}, "color": "white", "bold": True},
                                                              {"text": " s", "color": "light_purple"}]),
        "title @a[tag=tw.in,tag=tw.picked] actionbar " + tj({"text": "Waiting for your team to pick...", "color": "gray"}),
    ])

    # ------------------------------------------------------------------ joining
    wj(f"data/{NS}/advancement/towernpc.json", {"criteria": {"c": {"trigger": "minecraft:player_interacted_with_entity", "conditions": {"entity": [{
        "condition": "minecraft:entity_properties", "entity": "this",
        "predicate": {"minecraft:entity_type": "minecraft:interaction", "minecraft:nbt": "{Tags:[\"pvp.towernpc\"]}"}}]}}},
        "rewards": {"function": f"{T}/npc"}})
    fn("tower/npc", [
        "advancement revoke @s only pvp:towernpc",
        "execute as @e[type=minecraft:interaction,tag=pvp.towernpc,distance=..8] run data remove entity @s interaction",
        f"execute unless entity @s[{b.LOBBY_BOX}] run return 0",
        "execute if score #tstate tw matches 2.. run return run tellraw @s " + tj([
            {"text": "🗼 A climb is in progress (floor ", "color": "light_purple"}, {"score": {"name": "#floor", "objective": "tw"}, "color": "white"},
            {"text": "). Try again when it's over.", "color": "light_purple"}]),
        f"execute if entity @s[tag=tw.q] run return run {say('@s', 'You are already in the queue for The Tower.', 'gray')}",
        f"execute if score #tstate tw matches 1 store result score #c tw if entity @a[tag=tw.q]",
        f"execute if score #tstate tw matches 1 if score #c tw matches {MAX_PLAYERS}.. run return run {say('@s', f'The Tower is full ({MAX_PLAYERS} players).', 'red')}",
        "tag @s remove pve.q", "tag @s add tw.q",
        f"execute if score #tstate tw matches 0 run scoreboard players set #tt tw {COUNTDOWN}",
        f"execute if score #tstate tw matches 0 run tellraw @a[{b.LOBBY_BOX}] " + tj([
            {"text": "🗼 ", "color": "light_purple"}, {"selector": "@s", "color": "yellow"}, {"text": " is climbing The Tower! ", "color": "light_purple"},
            {"text": f"Right-click the Tower NPC within {COUNTDOWN} s to join (up to {MAX_PLAYERS}).", "color": "gray"}]),
        "execute if score #tstate tw matches 1 run tellraw @a[tag=tw.q] " + tj([{"selector": "@s", "color": "yellow"}, {"text": " joined the climb!", "color": "light_purple"}]),
        "execute if score #tstate tw matches 0 run scoreboard players set #tstate tw 1",
        "playsound minecraft:block.beacon.activate player @s ~ ~ ~ 1 1.4",
    ])
    fn("tower/start", [
        "scoreboard players set #floor tw 0",
        f"execute as @a[tag=tw.q] run function {T}/enter",
        f"function {T}/next",
    ])
    fn("tower/enter", [   # as each player: a fresh random character, no upgrades
        "tag @s remove tw.q", "tag @s add tw.in", "tag @s remove tw.picked", "clear @s", "effect clear @s", "function cyber:admin/reset",
        *b.PERK_RESET, "gamemode adventure @s", "team join tower @s",
        *[f"scoreboard players set @s tw.u{u[0]} 0" for u in UPGRADES], "scoreboard players set @s tw.lives 0", "scoreboard players set @s tw.kc 0",
        f"function {NS}:kit/roll", "scoreboard players operation @s pvp.cur = #rk pvp",
        *[f"execute if score @s pvp.cur matches {k[0]} run function {NS}:kit/{k[1]}" for k in b.KITS],
    ])

    # ------------------------------------------------------------------ floors
    pick_layout = lambda kind: [f"execute store result score #r tw run random value 1..{LAYOUTS}",
                                *[f"execute if score #r tw matches {i} run function {T}/room/{kind}_{i}" for i in range(1, LAYOUTS + 1)]]
    floor_title = lambda sub, color: ("title @a[tag=tw.in] subtitle " + tj({"text": sub, "color": color}))
    fn("tower/next", [
        "scoreboard players add #floor tw 1", "scoreboard players set #tstate tw 2", "tag @a remove tw.picked",
        "scoreboard players operation #m5 tw = #floor tw", "scoreboard players set #k tw 5", "scoreboard players operation #m5 tw %= #k tw",
        "scoreboard players operation #m4 tw = #floor tw", "scoreboard players set #k tw 4", "scoreboard players operation #m4 tw %= #k tw",
        "scoreboard players set #ttype tw 1",
        "execute if score #m4 tw matches 3 run scoreboard players set #ttype tw 2",
        "execute if score #m5 tw matches 0 run scoreboard players set #ttype tw 3",
        f"execute store result score #pl tw if entity {inn}",
        f"function {T}/room/clear",
        f"execute if score #ttype tw matches 1 run function {T}/floor_mobs",
        f"execute if score #ttype tw matches 2 run function {T}/floor_parkour",
        f"execute if score #ttype tw matches 3 run function {T}/floor_boss",
        f"execute as {inn} run function {T}/tp_start",
        "title @a[tag=tw.in] times 5 40 10",
        "title @a[tag=tw.in] title " + tj([{"text": "FLOOR ", "color": "light_purple", "bold": True}, {"score": {"name": "#floor", "objective": "tw"}, "color": "white", "bold": True}]),
        f"execute as {inn} at @s run playsound minecraft:block.end_portal_frame.fill player @s ~ ~ ~ 1 0.8",
    ])
    fn("tower/tp_start", [*[f"execute if score #ttype tw matches {k} run {v}" for k, v in start_tp.items()],
                           "effect clear @s minecraft:weakness", "effect clear @s minecraft:resistance"])
    fn("tower/floor_mobs", [*pick_layout("mobs"), floor_title("Clear the room", "gray"),
                            # 3 + floor/2 mobs, 2 more per extra player, at most 16
                            "scoreboard players operation #n tw = #floor tw", "scoreboard players set #k tw 2", "scoreboard players operation #n tw /= #k tw",
                            "scoreboard players add #n tw 3", "scoreboard players operation #k tw = #pl tw", "scoreboard players remove #k tw 1",
                            "scoreboard players operation #n tw += #k tw", "scoreboard players operation #n tw += #k tw",
                            "execute if score #n tw matches 17.. run scoreboard players set #n tw 16",
                            f"function {T}/spawn_loop"])
    fn("tower/floor_parkour", [*pick_layout("parkour"), floor_title("Parkour: reach the gold block", "gold")])
    fn("tower/floor_boss", [f"function {T}/room/boss",
                            "scoreboard players operation #bt tw = #floor tw", "scoreboard players set #k tw 5", "scoreboard players operation #bt tw /= #k tw",
                            "scoreboard players remove #bt tw 1", "scoreboard players operation #bi tw = #bt tw", "scoreboard players set #k tw 4",
                            "scoreboard players operation #bi tw %= #k tw",
                            *[f"execute if score #bi tw matches {i} run function {T}/boss/{i}" for i in range(len(BOSSES))],
                            "scoreboard players set #n tw 2", f"function {T}/spawn_loop", "bossbar set pvp:tower visible true"])
    # mobs: one at a random spawn point, from the pool for this floor's tier
    fn("tower/spawn_loop", ["execute if score #n tw matches ..0 run return 0", f"function {T}/spawn_one",
                            "scoreboard players remove #n tw 1", f"function {T}/spawn_loop"])
    fn("tower/spawn_one", [
        f"execute store result score #r tw run random value 1..{len(SPAWN_PTS)}",
        "scoreboard players operation #tier tw = #floor tw", "scoreboard players set #k tw 5", "scoreboard players operation #tier tw /= #k tw",
        f"execute if score #tier tw matches {len(POOLS)}.. run scoreboard players set #tier tw {len(POOLS) - 1}",
        *[f"execute if score #r tw matches {i} positioned {at(x + 0.5, 1, z + 0.5)} run function {T}/mob" for i, (x, z) in enumerate(SPAWN_PTS, 1)],
        f"execute as @e[tag=tw.new] run function {T}/scale", "tag @e[tag=tw.new] remove tw.new",
    ])
    mob = []
    for t, pool in enumerate(POOLS):
        mob.append(f"execute if score #tier tw matches {t} store result score #r2 tw run random value 1..{len(pool)}")
        for i, (typ, extra) in enumerate(pool, 1):
            mob.append(f"execute if score #tier tw matches {t} if score #r2 tw matches {i} run summon minecraft:{typ} ~ ~ ~ "
                       f"{{Tags:[\"tw.mob\",\"tw.new\"],PersistenceRequired:1b{extra}{NODROP}}}")
    fn("tower/mob", mob)
    # stronger every floor: +12% health and +5% damage per floor
    fn("tower/scale", [
        "execute store result storage pvp:tw v double 0.12 run scoreboard players get #floor tw", f"function {T}/mod_mobhp with storage pvp:tw",
        "execute store result storage pvp:tw v double 0.05 run scoreboard players get #floor tw", f"function {T}/mod_mobdmg with storage pvp:tw",
        "data modify entity @s Health set value 2048f"])
    fn("tower/mod_mobhp", [f"$attribute @s minecraft:max_health modifier add {NS}:tw_mobhp $(v) add_multiplied_base"])
    fn("tower/mod_mobdmg", [f"$attribute @s minecraft:attack_damage modifier add {NS}:tw_mobdmg $(v) add_multiplied_base"])
    # bosses: health 80 + 40 per boss already beaten + 30 per extra player
    for i, (typ, name, color, scale, extra) in enumerate(BOSSES):
        fn(f"tower/boss/{i}", [
            f"summon minecraft:{typ} {at(0.5, 1, -6.5)} {{Tags:[\"tw.mob\",\"tw.boss\",\"tw.bnew\"],PersistenceRequired:1b,CustomNameVisible:1b,"
            f"CustomName:{tj({'text': name, 'color': color, 'bold': True})}{extra}{NODROP}}}",
            "scoreboard players set #hp tw 40", "scoreboard players operation #hp tw *= #bt tw", "scoreboard players add #hp tw 80",
            "scoreboard players operation #k tw = #pl tw", "scoreboard players remove #k tw 1", "scoreboard players set #k2 tw 30",
            "scoreboard players operation #k tw *= #k2 tw", "scoreboard players operation #hp tw += #k tw",
            "execute store result storage pvp:tw v double 1 run scoreboard players get #hp tw",
            f"execute as @e[tag=tw.bnew] run function {T}/boss_hp with storage pvp:tw",
            *([f"attribute @e[tag=tw.bnew,limit=1] minecraft:scale base set {scale}"] if scale != 1.0 else []),
            "attribute @e[tag=tw.bnew,limit=1] minecraft:attack_damage modifier add pvp:tw_mobdmg 0.5 add_multiplied_base",
            "tag @e[tag=tw.bnew] remove tw.bnew",
            f"bossbar set pvp:tower name {tj({'text': name, 'color': color, 'bold': True})}",
            "execute store result bossbar pvp:tower max run scoreboard players get #hp tw",
            "execute store result bossbar pvp:tower value run scoreboard players get #hp tw",
            floor_title(f"Boss: {name}", "red"),
            f"execute as {inn} at @s run playsound minecraft:entity.wither.spawn player @s ~ ~ ~ 0.6 1.2",
        ])
    fn("tower/boss_hp", ["$attribute @s minecraft:max_health base set $(v)", "data modify entity @s Health set value 4096f"])

    # ------------------------------------------------------------------ clearing a floor, upgrades
    roll = ["execute store result score @s tw.o1 run random value 1..%d" % len(UPGRADES),
            "execute store result score @s tw.o2 run random value 1..%d" % (len(UPGRADES) - 1),
            "execute if score @s tw.o2 >= @s tw.o1 run scoreboard players add @s tw.o2 1",
            "execute store result score @s tw.o3 run random value 1..%d" % (len(UPGRADES) - 2),
            # skip both earlier picks, lowest first
            "scoreboard players operation #lo tw = @s tw.o1", "scoreboard players operation #lo tw < @s tw.o2",
            "scoreboard players operation #hi tw = @s tw.o1", "scoreboard players operation #hi tw > @s tw.o2",
            "execute if score @s tw.o3 >= #lo tw run scoreboard players add @s tw.o3 1",
            "execute if score @s tw.o3 >= #hi tw run scoreboard players add @s tw.o3 1"]
    offer = ["tag @s remove tw.picked", "scoreboard players set @s tw.pick 0", "scoreboard players enable @s tw.pick", *roll,
             "tellraw @s " + tj([{"text": "\n🗼 Floor cleared! ", "color": "light_purple", "bold": True}, {"text": "Pick an upgrade (click one):", "color": "gray"}])]
    for slot in (1, 2, 3):
        for (uid, name, color, desc, _) in UPGRADES:
            offer.append(f"execute if score @s tw.o{slot} matches {uid} run tellraw @s " + tj([
                {"text": "  ▶ ", "color": "dark_gray"},
                {"text": f"[{name}]", "color": color, "bold": True, "click_event": {"action": "run_command", "command": f"/trigger tw.pick set {uid}"},
                 "hover_event": {"action": "show_text", "value": desc}},
                {"text": f" {desc}", "color": "gray"}]))
    offer += ["title @s title " + tj({"text": "FLOOR CLEARED", "color": "green", "bold": True}),
              "title @s subtitle " + tj({"text": "Pick an upgrade in chat", "color": "gray"})]
    fn("tower/offer", offer)
    fn("tower/clear", [
        "execute unless score #tstate tw matches 2 run return 0",
        "scoreboard players set #tstate tw 3", f"scoreboard players set #tt tw {PICK_SECS}",
        f"kill @e[tag=tw.mob,{BOX}]", "bossbar set pvp:tower visible false",
        f"function {T}/room/clear", f"execute as {inn} run tp @s {at(0.5, 1, 0.5)}",
        f"effect give {inn} minecraft:regeneration 8 1",
        f"execute as {inn} if score #floor tw > @s tw.best run scoreboard players operation @s tw.best = #floor tw",
        f"scoreboard players set #g pvp {FLOOR_XP}", f"execute as {inn} run function {NS}:mastery/gain",
        f"execute as {inn} at @s run playsound minecraft:ui.toast.challenge_complete player @s ~ ~ ~ 0.8 1.2",
        f"execute as {inn} run function {T}/offer",
    ])
    fn("tower/picked", [   # as a player who clicked an upgrade: only one of the three offered, once per floor
        "scoreboard players operation #p tw = @s tw.pick", "scoreboard players set @s tw.pick 0",
        "execute unless score #tstate tw matches 3 run return 0", "execute if entity @s[tag=tw.picked] run return 0",
        "execute unless score #p tw = @s tw.o1 unless score #p tw = @s tw.o2 unless score #p tw = @s tw.o3 run return 0",
        f"function {T}/take",
    ])
    fn("tower/autopick", ["scoreboard players operation #p tw = @s tw.o1", f"function {T}/take"])
    take = ["tag @s add tw.picked"]
    for (uid, name, color, desc, mods) in UPGRADES:
        take += [f"execute if score #p tw matches {uid} run scoreboard players add @s tw.u{uid} 1",
                 f"execute if score #p tw matches {uid} run tellraw @s " + tj([{"text": "✔ ", "color": "green"}, {"text": name, "color": color, "bold": True},
                                                                              {"text": f": {desc}", "color": "gray"}])]
    take += ["execute if score #p tw matches 9 run effect give @s minecraft:instant_health 1 4 true", "execute if score #p tw matches 9 run give @s minecraft:golden_apple 2",
             "execute if score #p tw matches 10 run scoreboard players add @s tw.lives 1",
             f"function {T}/apply", "execute if score #p tw matches 1 run effect give @s minecraft:instant_health 1 0 true",
             "playsound minecraft:block.enchantment_table.use player @s ~ ~ ~ 1 1.2"]
    fn("tower/take", take)
    # re-apply every stacking modifier from the counts (also after an Extra Life)
    apply = []
    for (uid, name, color, desc, mods) in UPGRADES:
        for i, (attr, step, op) in enumerate(mods):
            mid = f"{NS}:tw_u{uid}_{i}"
            apply += [f"attribute @s minecraft:{attr} modifier remove {mid}",
                      f"execute if score @s tw.u{uid} matches 1.. store result storage pvp:tw v double {step} run scoreboard players get @s tw.u{uid}",
                      f"execute if score @s tw.u{uid} matches 1.. run function {T}/mod/u{uid}_{i} with storage pvp:tw"]
            fn(f"tower/mod/u{uid}_{i}", [f"$attribute @s minecraft:{attr} modifier add {mid} $(v) {op}"])
    fn("tower/apply", apply)

    # ------------------------------------------------------------------ falling, dying, leaving, game over
    fn("tower/fell", [start_tp[2], "damage @s 2 minecraft:fall", "title @s actionbar " + tj({"text": "Back to the start!", "color": "red"}),
                      "playsound minecraft:entity.player.hurt_on_fire player @s ~ ~ ~ 1 1"])
    fn("tower/died", [   # respawned (in the lobby) while climbing
        f"execute unless score #tstate tw matches 2.. run return run function {NS}:to_lobby",
        f"execute unless score @s tw.lives matches 1.. run return run function {NS}:to_lobby",
        "scoreboard players remove @s tw.lives 1", f"execute if score #tstate tw matches 3 run tp @s {at(0.5, 1, 0.5)}",
        f"execute if score #tstate tw matches 2 run function {T}/tp_start", f"function {T}/apply",
        "effect give @s minecraft:instant_health 1 4 true",
        "tellraw @a[tag=tw.in] " + tj([{"selector": "@s", "color": "yellow"}, {"text": " used an Extra Life!", "color": "green"}]),
    ])
    fn("tower/leave", [   # from to_lobby: out of the climb (died, /spawn, logged out)
        "execute if score #floor tw > @s tw.best run scoreboard players operation @s tw.best = #floor tw",
        "tag @s remove tw.in", "tag @s remove tw.picked", "team leave @s",
        *PERK_RESET,
        "tellraw @s " + tj([{"text": "🗼 Your climb ended on floor ", "color": "light_purple"}, {"score": {"name": "#floor", "objective": "tw"}, "color": "white", "bold": True},
                            {"text": " (best: ", "color": "gray"}, {"score": {"name": "@s", "objective": "tw.best"}, "color": "white"}, {"text": ")", "color": "gray"}]),
        "tellraw @a[tag=tw.in] " + tj([{"selector": "@s", "color": "yellow"}, {"text": " is out of the climb.", "color": "gray"}]),
    ])
    fn("tower/game_over", [
        "scoreboard players set #tstate tw 0", f"kill @e[tag=tw.mob,{BOX}]", "bossbar set pvp:tower visible false",
        "tellraw @a " + tj([{"text": "🗼 A Tower climb ended on floor ", "color": "light_purple"}, {"score": {"name": "#floor", "objective": "tw"}, "color": "white", "bold": True}]),
        "execute if score #floor tw > #trecord tw run tellraw @a " + tj([{"text": "🗼 New Tower record: floor ", "color": "gold", "bold": True},
                                                                       {"score": {"name": "#floor", "objective": "tw"}, "color": "white", "bold": True}]),
        "execute if score #floor tw > #trecord tw run scoreboard players operation #trecord tw = #floor tw",
        f"function {T}/room/clear",
    ])

    # ------------------------------------------------------------------ the room
    x1, x2, z1, z2 = TCX - R, TCX + R, TCZ - R, TCZ + R
    fn("tower/room/clear", [
        f"fill {x1} {TY + 1} {z1} {x2} {TY + WALL_H - 1} {z2} minecraft:air",
        f"fill {x1} {TY} {z1} {x2} {TY} {z2} minecraft:polished_deepslate",
        f"fill {x1 + 1} {TY} {z1 + 1} {x2 - 1} {TY} {z2 - 1} minecraft:deepslate_tiles",
        f"fill {TCX - 1} {TY} {TCZ - 1} {TCX + 1} {TY} {TCZ + 1} minecraft:crying_obsidian",
    ])
    shell = [f"fill {x1 - 1} {TY - 1} {z1 - 1} {x2 + 1} {TY + WALL_H + 1} {z2 + 1} minecraft:deepslate_bricks hollow",
             f"fill {x1} {TY + WALL_H} {z1} {x2} {TY + WALL_H} {z2} minecraft:barrier",
             f"fill {x1 - 1} {TY + WALL_H + 1} {z1 - 1} {x2 + 1} {TY + WALL_H + 1} {z2 + 1} minecraft:tinted_glass"]
    for x in range(-R, R + 1, 6):   # lights in the walls, purple banners of glass
        for (wx, wz) in ((x, -R - 1), (x, R + 1), (-R - 1, x), (R + 1, x)):
            shell += [f"setblock {TCX + wx} {TY + 4} {TCZ + wz} minecraft:sea_lantern",
                      f"setblock {TCX + wx} {TY + 8} {TCZ + wz} minecraft:purple_stained_glass"]
    # the room stays force-loaded (4 chunks), so a floor can be rebuilt the moment a climb starts
    fn("admin/build_tower", [f"forceload add {x1 - 1} {z1 - 1} {x2 + 1} {z2 + 1}", *shell, f"function {T}/room/clear"])

    rnd = random.Random(7331)
    near_spawn = lambda x, z: any(abs(x - sx) <= 1 and abs(z - sz) <= 1 for sx, sz in SPAWN_PTS)
    for i in range(1, LAYOUTS + 1):   # mob rooms: cover pillars and low walls, south end kept open for the players
        cmds = []
        for _ in range(rnd.randint(5, 8)):
            x, z = rnd.randint(-9, 8), rnd.randint(-8, 4)
            if near_spawn(x, z) or abs(x) <= 1 and abs(z) <= 1: continue
            if rnd.random() < 0.55:
                h = rnd.randint(3, 6)
                cmds.append(f"fill {at(x, 1, z)} {at(x + 1, h, z + 1)} minecraft:{rnd.choice(['polished_deepslate', 'deepslate_bricks', 'chiseled_deepslate'])}")
                cmds.append(f"setblock {at(x, h + 1, z)} minecraft:soul_lantern")
            else:
                dx, dz = (3, 0) if rnd.random() < 0.5 else (0, 3)
                if any(near_spawn(x + k * (dx > 0), z + k * (dz > 0)) for k in range(4)): continue
                cmds.append(f"fill {at(x, 1, z)} {at(x + dx, 1, z + dz)} minecraft:cobbled_deepslate_wall")
        fn(f"tower/room/mobs_{i}", cmds)
    fn("tower/room/boss", [f"fill {at(px, 1, pz)} {at(px + 1, 8, pz + 1)} minecraft:polished_blackstone_bricks"
                           for px in (-8, 7) for pz in (-8, 4)] + [f"fill {TCX - 1} {TY} {TCZ - 8} {TCX + 1} {TY} {TCZ - 5} minecraft:crimson_nylium"])
    for i in range(1, LAYOUTS + 1):   # parkour: a snake of platforms over magma, harder (1x1) for layouts 4..6
        hard = i > LAYOUTS // 2
        size, block = (1, "cyan_concrete") if hard else (2, "purple_concrete")
        cmds = [f"fill {x1} {TY} {z1} {x2} {TY} {z2} minecraft:magma_block",
                f"fill {at(-1, 2, 9)} {at(1, 2, 11)} minecraft:polished_deepslate"]   # start platform, players stand on TY + 3
        way = [(0, 7), (-9, 7), (-9, 2), (9, 2), (9, -3), (-9, -3), (-9, -8), (0, -8)]
        cx, cz, h = 0, 9, 2
        def plat(x, z, y):
            cmds.append(f"fill {at(x, y, z)} {at(x + size - 1, y, z + size - 1)} minecraft:{block}")
        for (wx, wz) in way:
            while True:
                dx, dz = (wx > cx) - (wx < cx), (wz > cz) - (wz < cz)
                dist = abs(wx - cx) + abs(wz - cz)
                dy = rnd.choice([-1, 0, 0, 1])
                if h + dy < 2 or h + dy > 6: dy = 0
                gap = 1 if dy == 1 else rnd.randint(1, 2)
                step = size + gap
                if dist <= size + 2: break   # close enough to jump straight to the corner
                cx, cz, h = cx + dx * step, cz + dz * step, h + dy
                plat(cx, cz, h)
            cx, cz = wx, wz
            plat(cx, cz, h)
        cmds.append(f"fill {at(-1, h, -12)} {at(1, h, -10)} minecraft:gold_block")   # the exit, past the last platform
        cmds.append(f"setblock {at(0, h + 1, -12)} minecraft:end_rod")
        fn(f"tower/room/parkour_{i}", cmds)
    return BOX
