"""The Tower: a roguelite climb for the Multiverse server (imported by build.py).

Solo or up to 4 players. Everyone starts as a random character. Each floor is a mob fight, a parkour run over magma
(every 4th floor, 3/7/11...) or a boss (every 5th). After each floor everyone picks 1 of 3 random upgrades (clickable
chat lines), which stack for the whole run. Dying is the end of your climb unless you have an Extra Life; the run is
over when nobody is left. Best floor per player in tw.best, the server record in #trecord tw.

One room, rebuilt for every floor: interior x/z -R..R around (TCX, TCZ), floor blocks at TY, players stand on TY + 1.
State (#tstate tw): 0 idle, 1 countdown (queue open), 2 floor in progress, 3 picking upgrades.
Floor type (#ttype tw): 1 mobs, 3 boss; challenge floors (every 3rd, picked at random, never the same twice in a row):
2 parkour, 4 glass bridge, 5 maze, 6 crafting.
"""
import random

NS = "pvp"
TCX, TCZ, R = 400, 0, 12           # room centre and interior half-size (walls at +-13)
WALL_H = 12                        # ceiling (barrier) at TY + WALL_H
MAX_PLAYERS = 4
COUNTDOWN = 10                     # s the queue stays open after the first click
PICK_SECS = 20                     # s to pick an upgrade (then it's picked for you)
LAYOUTS = 10                       # layouts generated per kind (mob rooms, parkour, mazes)
CHALLENGES = [2, 4, 5, 6]          # parkour, glass bridge, maze, crafting
MAGMA, GOAL = (2, 4), (2, 4, 5)    # floor types with magma to fall in / a gold block to reach
MAZE_SECS, CRAFT_SECS = 60, 90     # time limits (+1 s per floor, max 2 min); when they run out everyone takes a strike
# crafting challenge: target item, name, ingredient stacks hidden in the barrels (split so you have to search), hint
RECIPES = [
    ("iron_pickaxe", "Iron Pickaxe", [("iron_ingot", 1), ("iron_ingot", 1), ("iron_ingot", 1), ("oak_planks", 2)], "3 iron ingots + 2 sticks"),
    ("compass", "Compass", [("iron_ingot", 2), ("iron_ingot", 2), ("redstone", 1)], "4 iron ingots around 1 redstone"),
    ("clock", "Clock", [("gold_ingot", 2), ("gold_ingot", 2), ("redstone", 1)], "4 gold ingots around 1 redstone"),
    ("lantern", "Lantern", [("iron_nugget", 4), ("iron_nugget", 4), ("coal", 1), ("oak_planks", 1)], "8 iron nuggets around a torch"),
    ("fishing_rod", "Fishing Rod", [("string", 1), ("string", 1), ("oak_planks", 2)], "3 sticks + 2 string"),
    ("jukebox", "Jukebox", [("oak_planks", 4), ("oak_planks", 4), ("diamond", 1)], "8 planks around a diamond"),
]
CRAFT_ITEMS = sorted({r[0] for r in RECIPES} | {i for r in RECIPES for i, _ in r[2]} | {"stick", "torch"})   # taken back after the floor
JUNK = ["rotten_flesh", "bone", "dirt", "cobblestone", "wheat_seeds", "feather", "flint", "clay_ball"]
BARRELS = [(-12, -8), (-12, -2), (-12, 4), (12, -8), (12, -2), (12, 4), (-8, -12), (-3, -12), (3, -12), (8, -12), (-6, 6), (6, 6)]
FLOOR_XP = 5                       # mastery XP per floor cleared, for the character you're playing
MAX_FALLS = 3                      # parkour: the 3rd fall into the magma on a floor kills you
SIDE = [1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]   # sidebar (Second Wind, Extra Life are one-offs)
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV"]
LOG = ('minecraft:book[minecraft:custom_name={"text":"🗼 Climb Log","color":"light_purple","bold":true,"italic":false},'
       'minecraft:lore=[{"text":"Right-click: your upgrades and stats","color":"gray","italic":false}],minecraft:max_stack_size=1,'
       'minecraft:enchantment_glint_override=true,minecraft:use_cooldown={seconds:1f,cooldown_group:"pvp:twlog"},'
       'minecraft:consumable={consume_seconds:0.05f,animation:"none",has_consume_particles:false,sound:"minecraft:intentionally_empty"}]')


def stat(uid, lv):
    """What lv stacks of an upgrade add up to, for the sidebar and the Climb Log."""
    return {1: f"+{2 * lv} ❤", 2: f"+{15 * lv}% damage", 3: f"+{10 * lv}% speed", 4: f"+{3 * lv} armor", 5: f"+{15 * lv}% attack speed",
            6: f"+{14 * lv}% jump", 7: f"+{min(100, 25 * lv)}% knockback res.", 8: f"Regen {ROMAN[min(lv, 3) - 1]} on kills",
            9: f"used {lv}x", 10: f"{lv} picked", 11: f"+{40 * lv}% dmg, -{2 * lv} ❤",
            12: f"{min(75, 15 * lv)}% crits", 13: f"burn {1 + 2 * min(lv, 3)} s", 14: f"Slowness {ROMAN[min(lv, 3) - 1]}" + (" + Weakness" if lv >= 3 else ""),
            15: f"Wither {ROMAN[min(lv, 3) - 1]}", 16: f"{min(75, 15 * lv)}%, {6 + 2 * min(lv, 6)} dmg", 17: f"{min(75, 15 * lv)}% blasts",
            18: f"{2 * min(lv, 6)} dmg back", 19: f"+{2 * min(lv, 5)} ❤ per floor", 20: f"Strength {ROMAN[min(lv, 2) - 1]} on kills",
            21: f"{3 * min(lv, 4)} dmg / 2 s", 22: f"{4 * min(lv, 5)} dmg / 8 s", 23: f"Lucky {ROMAN[lv - 1]}"}[uid]

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
    # inspired by Crab Champions. The on-hit ones (12-17) work with melee, guns and ability damage alike.
    (12, "Crit Chance", "yellow", "15% chance per hit for +5 bonus damage", []),
    (13, "Firestarter", "gold", "Your hits set mobs on fire", []),
    (14, "Frostbite", "aqua", "Your hits slow mobs down", []),
    (15, "Toxic", "dark_green", "Your hits wither mobs (works on undead too)", []),
    (16, "Lightning", "yellow", "15% chance per hit to call lightning (8 dmg)", []),
    (17, "Explosive", "red", "15% chance per hit to blast nearby mobs (5 dmg)", []),
    (18, "Thorns", "dark_green", "Getting hit deals 2 damage to mobs around you", []),
    (19, "Shield", "aqua", "+2 absorption hearts at the start of every floor", []),
    (20, "Bloodlust", "dark_red", "Kills give you Strength for 4 s", []),
    (21, "Attack Drone", "gold", "A drone zaps the nearest mob every 2 s (3 dmg)", []),
    (22, "Black Hole", "dark_purple", "Every 8 s: pull nearby mobs in, 4 damage", []),
    (23, "Lucky", "green", "Better odds of Epic and Legendary upgrades", []),
]
# rarity (Crab Champions style): offers roll a rarity first, then an upgrade of that rarity
RARITY = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 9: 0, 13: 0, 15: 0, 18: 0,
          8: 1, 12: 1, 14: 1, 19: 1, 20: 1, 23: 1, 10: 2, 11: 2, 16: 2, 17: 2, 21: 3, 22: 3}
TIERS = [("Common", "gray"), ("Rare", "aqua"), ("Epic", "light_purple"), ("Legendary", "gold")]
ODDS = (60, 28, 10)            # % common / rare / epic (the rest legendary); each Lucky: -10 common (min 20), +4 rare, +4 epic
# every modifier id the Tower ever adds (removed when you leave, with the other per-run perks)
MOD_IDS = [(f"{NS}:tw_u{u[0]}_{i}", a) for u in UPGRADES for i, (a, _, _) in enumerate(u[4])] + \
          [(f"{NS}:tw_mobhp", "max_health"), (f"{NS}:tw_mobdmg", "attack_damage")]
PERK_RESET = [f"attribute @s minecraft:{a} modifier remove {i}" for i, a in MOD_IDS]

# mob pools by tier (tier = floor / 5, capped); each entry: type, extra NBT
POOLS = [
    # no spiders: they climb the walls to the ceiling, where melee characters can't reach them
    [("zombie", ""), ("skeleton", ""), ("creeper", ""), ("zombie", "")],
    [("husk", ""), ("stray", ""), ("zombie_villager", ""), ("zombie", ',equipment:{head:{id:"minecraft:iron_helmet",count:1}}')],
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
START = {1: (0.5, 1, 9.5), 2: (0.5, 3, 10.5), 3: (0.5, 1, 9.5), 4: (0.5, 3, 10.5), 5: (-10.5, 1, 11.5), 6: (0.5, 1, 9.5)}   # per floor type (y from TY)


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
        *[f"scoreboard objectives add {o}" for o in ["tw dummy", "tw.pick trigger", "tw.join trigger", "tw.o1 dummy", "tw.o2 dummy", "tw.o3 dummy",
                                                     "tw.lives dummy", "tw.best dummy", "tw.kc totalKillCount", "tw.falls dummy",
                                                     *[f"tw.u{u[0]} dummy" for u in UPGRADES]]],
        'scoreboard objectives add tw.side dummy {"text":"🗼 THE TOWER","color":"light_purple","bold":true}',
        "scoreboard objectives setdisplay sidebar.team.light_purple tw.side",   # team tower is light purple
        "team add tower", "team modify tower color light_purple", "team modify tower friendlyFire false",
        "team modify tower seeFriendlyInvisibles true",
        'bossbar add pvp:tower {"text":"Boss"}', "bossbar set pvp:tower color purple", "bossbar set pvp:tower visible false",
        "execute unless score #tstate tw matches 0.. run scoreboard players set #tstate tw 0",
        "execute unless score #trecord tw matches 0.. run scoreboard players set #trecord tw 0",
        "execute unless score #lasti tw matches 0.. run scoreboard players set #lasti tw 0",
        f"forceload add {TCX - R - 1} {TCZ - R - 1} {TCX + R + 1} {TCZ + R + 1}",
    ])
    fn("tower/tick", [
        f"scoreboard players enable {inn} tw.pick",
        # the Tower menu (the NPC opens it): 1 = join the queue, 2 = leave it
        f"scoreboard players enable @a[{b.LOBBY_BOX}] tw.join",
        f"execute as @a[scores={{tw.join=1}}] run function {T}/join",
        f"execute as @a[scores={{tw.join=2}}] run function {T}/leave_queue",
        "scoreboard players set @a[scores={tw.join=1..}] tw.join 0",
        f"execute as @a[tag=tw.in,scores={{tw.pick=1..}}] run function {T}/picked",
        # anyone climbing who ends up outside the room (through the ceiling, a wall...) goes back in
        f"execute if score #tstate tw matches 2.. as {inn} unless entity @s[x={TCX - R},y={TY},z={TCZ - R},dx={2 * R},dy={WALL_H - 2},dz={2 * R}] run function {T}/escaped",
        f"execute if score #tstate tw matches 2 if score #mag tw matches 1 as {inn} at @s if block ~ ~-0.2 ~ minecraft:magma_block run function {T}/fell",
        f"execute if score #tstate tw matches 2 if score #goal tw matches 1 as {inn} at @s if block ~ ~-0.2 ~ minecraft:gold_block run function {T}/clear",
        f"execute if score #tstate tw matches 2 if score #ttype tw matches 4 run function {T}/glass_tick",
        f"execute if score #tstate tw matches 2 if score #ttype tw matches 6 as {inn} run function {T}/craft_check",
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
        *[f"execute as @a[tag=tw.in,scores={{tw.kc=1..,tw.u8={lv}}}] run effect give @s minecraft:regeneration 3 {amp}" for lv, amp in (("1", 0), ("2", 1), ("3..", 2))],
        *[f"execute as @a[tag=tw.in,scores={{tw.kc=1..,tw.u20={lv}}}] run effect give @s minecraft:strength 4 {amp}" for lv, amp in (("1", 0), ("2..", 1))],
        f"scoreboard players set {inn} tw.kc 0",
        "scoreboard players add #t8 tw 1", "scoreboard players operation #t2 tw = #t8 tw", "scoreboard players set #k tw 2", "scoreboard players operation #t2 tw %= #k tw",
        "scoreboard players set #k tw 8", "scoreboard players operation #t8 tw %= #k tw",
        f"execute if score #tstate tw matches 2 if score #t2 tw matches 0 as @a[tag=tw.in,scores={{tw.u21=1..}}] at @s run function {T}/drone",
        f"execute if score #tstate tw matches 2 if score #t8 tw matches 0 as @a[tag=tw.in,scores={{tw.u22=1..}}] at @s run function {T}/blackhole",
        f"execute if score #tstate tw matches 2 if score #chal tw matches 0 run function {T}/sec_fight",
        f"execute if score #tstate tw matches 2 if score #chal tw matches 1 run function {T}/sec_chal",
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
    fn("tower/npc", [   # the NPC opens the Tower menu (build.py "tower"), like the PvP Arena and Outbreak NPCs
        "advancement revoke @s only pvp:towernpc",
        "execute as @e[type=minecraft:interaction,tag=pvp.towernpc,distance=..8] run data remove entity @s interaction",
        f"execute if entity @s[{b.LOBBY_BOX}] run pvpmenu tower",
    ])
    fn("tower/leave_queue", [
        f"execute unless entity @s[tag=tw.q] run return run {say('@s', 'You are not in the queue for The Tower.', 'gray')}",
        "tag @s remove tw.q", say("@s", "You left the queue for The Tower.", "gray"),   # an empty queue cancels itself (tower/sec)
    ])
    fn("tower/join", [   # menu: join (or open) the queue
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
            {"text": f"Click the Tower NPC and pick Climb within {COUNTDOWN} s to join (up to {MAX_PLAYERS}).", "color": "gray"}]),
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
        f"function {NS}:kit/roll", "scoreboard players operation @s pvp.cur = #rk pvp", "scoreboard players set @s tw.falls 0", f"give @s {LOG}",
        *[f"execute if score @s pvp.cur matches {k[0]} run function {NS}:kit/{k[1]}" for k in b.KITS],
    ])

    # ------------------------------------------------------------------ floors
    pick_layout = lambda kind: [f"execute store result score #r tw run random value 1..{LAYOUTS}",
                                *[f"execute if score #r tw matches {i} run function {T}/room/{kind}_{i}" for i in range(1, LAYOUTS + 1)]]
    floor_title = lambda sub, color: ("title @a[tag=tw.in] subtitle " + tj({"text": sub, "color": color}))
    fn("tower/next", [
        "scoreboard players add #floor tw 1", "scoreboard players set #tstate tw 2", "tag @a remove tw.picked", f"scoreboard players set {inn} tw.falls 0",
        "scoreboard players operation #m5 tw = #floor tw", "scoreboard players set #k tw 5", "scoreboard players operation #m5 tw %= #k tw",
        "scoreboard players operation #m3 tw = #floor tw", "scoreboard players set #k tw 3", "scoreboard players operation #m3 tw %= #k tw",
        "scoreboard players set #ttype tw 1",
        f"execute if score #m3 tw matches 0 unless score #m5 tw matches 0 run function {T}/pick_challenge",
        "execute if score #m5 tw matches 0 run scoreboard players set #ttype tw 3",
        "scoreboard players set #mag tw 0", "scoreboard players set #goal tw 0", "scoreboard players set #chal tw 0",
        *[f"execute if score #ttype tw matches {t} run scoreboard players set #mag tw 1" for t in MAGMA],
        *[f"execute if score #ttype tw matches {t} run scoreboard players set #goal tw 1" for t in GOAL],
        *[f"execute if score #ttype tw matches {t} run scoreboard players set #chal tw 1" for t in CHALLENGES],
        f"execute store result score #pl tw if entity {inn}",
        f"function {T}/room/clear",
        f"execute if score #ttype tw matches 1 run function {T}/floor_mobs",
        f"execute if score #ttype tw matches 2 run function {T}/floor_parkour",
        f"execute if score #ttype tw matches 3 run function {T}/floor_boss",
        f"execute if score #ttype tw matches 4 run function {T}/floor_glass",
        f"execute if score #ttype tw matches 5 run function {T}/floor_maze",
        f"execute if score #ttype tw matches 6 run function {T}/floor_craft",
        f"execute as {inn} run function {T}/tp_start",
        f"effect clear {inn} minecraft:absorption",
        *[f"execute as @a[tag=tw.in,scores={{tw.u19={lv}}}] run effect give @s minecraft:absorption infinite {amp} true" for lv, amp in (("1", 0), ("2", 1), ("3", 2), ("4", 3), ("5..", 4))],
        "title @a[tag=tw.in] times 5 40 10",
        "title @a[tag=tw.in] title " + tj([{"text": "FLOOR ", "color": "light_purple", "bold": True}, {"score": {"name": "#floor", "objective": "tw"}, "color": "white", "bold": True}]),
        f"execute as {inn} at @s run playsound minecraft:block.end_portal_frame.fill player @s ~ ~ ~ 1 0.8",
        f"function {T}/side",
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
    # one upgrade (#u tw) for @s: a rarity from ODDS shifted by Lucky, then one of that rarity
    by_tier = [[u for u, t in sorted(RARITY.items()) if t == k] for k in range(len(TIERS))]
    one = ["execute store result score #r tw run random value 1..100", "scoreboard players operation #L tw = @s tw.u23",
           f"scoreboard players set #c tw {ODDS[0]}", "scoreboard players operation #k tw = #L tw", "scoreboard players set #k2 tw 10",
           "scoreboard players operation #k tw *= #k2 tw", "scoreboard players operation #c tw -= #k tw",
           "execute if score #c tw matches ..19 run scoreboard players set #c tw 20",
           "scoreboard players operation #k tw = #L tw", "scoreboard players set #k2 tw 4", "scoreboard players operation #k tw *= #k2 tw",
           "scoreboard players operation #rr tw = #c tw", f"scoreboard players add #rr tw {ODDS[1]}", "scoreboard players operation #rr tw += #k tw",
           "scoreboard players operation #ee tw = #rr tw", f"scoreboard players add #ee tw {ODDS[2]}", "scoreboard players operation #ee tw += #k tw",
           "scoreboard players set #tier tw 3", "execute if score #r tw <= #ee tw run scoreboard players set #tier tw 2",
           "execute if score #r tw <= #rr tw run scoreboard players set #tier tw 1", "execute if score #r tw <= #c tw run scoreboard players set #tier tw 0"]
    for k, ids in enumerate(by_tier):
        one.append(f"execute if score #tier tw matches {k} store result score #r2 tw run random value 1..{len(ids)}")
        one += [f"execute if score #tier tw matches {k} if score #r2 tw matches {i} run scoreboard players set #u tw {u}" for i, u in enumerate(ids, 1)]
    fn("tower/roll_one", one)
    # re-roll (up to 20 times) until it differs from the slots already filled
    fn("tower/roll2", [f"function {T}/roll_one", "execute unless score #u tw = @s tw.o1 run return 0",
                       "scoreboard players add #try tw 1", f"execute if score #try tw matches ..20 run function {T}/roll2"])
    fn("tower/roll3", [f"function {T}/roll_one", "execute unless score #u tw = @s tw.o1 unless score #u tw = @s tw.o2 run return 0",
                       "scoreboard players add #try tw 1", f"execute if score #try tw matches ..20 run function {T}/roll3"])
    roll = [f"function {T}/roll_one", "scoreboard players operation @s tw.o1 = #u tw",
            "scoreboard players set #try tw 0", f"function {T}/roll2", "scoreboard players operation @s tw.o2 = #u tw",
            "scoreboard players set #try tw 0", f"function {T}/roll3", "scoreboard players operation @s tw.o3 = #u tw"]
    offer = ["tag @s remove tw.picked", "scoreboard players set @s tw.pick 0", "scoreboard players enable @s tw.pick", *roll,
             "tellraw @s " + tj([{"text": "\n🗼 Floor cleared! ", "color": "light_purple", "bold": True}, {"text": "Pick an upgrade (click one):", "color": "gray"}])]
    for slot in (1, 2, 3):
        for (uid, name, color, desc, _) in UPGRADES:
            rname, rcolor = TIERS[RARITY[uid]]
            offer.append(f"execute if score @s tw.o{slot} matches {uid} run tellraw @s " + tj([
                {"text": "  ▶ ", "color": "dark_gray"}, {"text": f"{rname.upper()} ", "color": rcolor, "bold": True},
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
        *[f"clear {inn} minecraft:{i}" for i in CRAFT_ITEMS],
        f"function {T}/room/clear", f"execute as {inn} run tp @s {at(0.5, 1, 0.5)}",
        f"effect give {inn} minecraft:regeneration 8 1",
        f"scoreboard players add {inn} tw.best 0",   # a missing score never compares, so give everyone one first
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
             f"function {T}/summary", f"function {T}/side",
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
    fn("tower/escaped", [f"execute if score #tstate tw matches 3 run tp @s {at(0.5, 1, 0.5)}",
                         f"execute if score #tstate tw matches 2 run function {T}/tp_start",
                         "title @s actionbar " + tj({"text": "Back into the room!", "color": "yellow"})])
    fn("tower/fell", [
        "scoreboard players add @s tw.falls 1",
        f"execute if score @s tw.falls matches {MAX_FALLS}.. run tellraw @a[tag=tw.in] " + tj([{"selector": "@s", "color": "yellow"},
                                                                                               {"text": f" fell into the magma {MAX_FALLS} times!", "color": "red"}]),
        f"execute if score @s tw.falls matches {MAX_FALLS}.. run return run kill @s",
        f"function {T}/tp_start", "damage @s 2 minecraft:fall",
        "title @s actionbar " + tj([{"text": "Back to the start! Strikes: ", "color": "red"}, {"score": {"name": "@s", "objective": "tw.falls"}, "color": "red", "bold": True},
                                    {"text": f"/{MAX_FALLS}", "color": "red"}]),
        "playsound minecraft:entity.player.hurt_on_fire player @s ~ ~ ~ 1 1", f"function {T}/side"])
    fn("tower/died", [   # respawned (in the lobby) while climbing
        f"execute unless score #tstate tw matches 2.. run return run function {NS}:to_lobby",
        f"execute unless score @s tw.lives matches 1.. run return run function {NS}:to_lobby",
        "scoreboard players remove @s tw.lives 1", "scoreboard players set @s tw.falls 0", f"execute if score #tstate tw matches 3 run tp @s {at(0.5, 1, 0.5)}",
        f"execute if score #tstate tw matches 2 run function {T}/tp_start", f"function {T}/apply",
        "effect give @s minecraft:instant_health 1 4 true",
        "tellraw @a[tag=tw.in] " + tj([{"selector": "@s", "color": "yellow"}, {"text": " used an Extra Life!", "color": "green"}]),
        f"function {T}/side",
    ])
    fn("tower/leave", [   # from to_lobby: out of the climb (died, /spawn, logged out)
        "scoreboard players add @s tw.best 0",
        "execute if score #floor tw > @s tw.best run scoreboard players operation @s tw.best = #floor tw",
        "tag @s remove tw.in", "tag @s remove tw.picked", "team leave @s",
        *PERK_RESET,
        "tellraw @s " + tj([{"text": "🗼 Your climb ended on floor ", "color": "light_purple"}, {"score": {"name": "#floor", "objective": "tw"}, "color": "white", "bold": True},
                            {"text": " (best: ", "color": "gray"}, {"score": {"name": "@s", "objective": "tw.best"}, "color": "white"}, {"text": ")", "color": "gray"}]),
        "tellraw @a[tag=tw.in] " + tj([{"selector": "@s", "color": "yellow"}, {"text": " is out of the climb.", "color": "gray"}]),
        f"function {T}/side",
    ])
    fn("tower/game_over", [
        "scoreboard players set #tstate tw 0", f"kill @e[tag=tw.mob,{BOX}]", "bossbar set pvp:tower visible false", "scoreboard players reset * tw.side",
        "tellraw @a " + tj([{"text": "🗼 A Tower climb ended on floor ", "color": "light_purple"}, {"score": {"name": "#floor", "objective": "tw"}, "color": "white", "bold": True}]),
        "execute if score #floor tw > #trecord tw run tellraw @a " + tj([{"text": "🗼 New Tower record: floor ", "color": "gold", "bold": True},
                                                                       {"score": {"name": "#floor", "objective": "tw"}, "color": "white", "bold": True}]),
        "execute if score #floor tw > #trecord tw run scoreboard players operation #trecord tw = #floor tw",
        f"function {T}/room/clear",
    ])

    # ------------------------------------------------------------------ your build: chat summary, sidebar, Climb Log
    summ = ["tellraw @s " + tj([{"text": "🗼 Your build", "color": "light_purple", "bold": True}, {"text": " · floor ", "color": "gray"},
                                {"score": {"name": "#floor", "objective": "tw"}, "color": "white"}])]
    summ += [f"execute if score @s pvp.cur matches {k[0]} run tellraw @s " + tj([{"text": "  Character: ", "color": "gray"}, {"text": k[2], "color": k[3], "bold": True}])
             for k in b.KITS]
    for (uid, name, color, desc, _) in UPGRADES:
        for lv in range(1, len(ROMAN) + 1):
            rng = f"{lv}.." if lv == len(ROMAN) else str(lv)
            summ.append(f"execute if score @s tw.u{uid} matches {rng} run tellraw @s " + tj([
                {"text": "  ▪ ", "color": "dark_gray"}, {"text": f"{name} {ROMAN[lv - 1]}", "color": color, "bold": True},
                {"text": f"  {stat(uid, lv)}", "color": "gray"}]))
    summ += ["execute if score @s tw.lives matches 1.. run tellraw @s " + tj([{"text": "  ❤ Extra Lives left: ", "color": "green"},
                                                                            {"score": {"name": "@s", "objective": "tw.lives"}, "color": "white", "bold": True}]),
             "execute unless score @s tw.u1 matches 1.. unless score @s tw.u2 matches 1.. unless score @s tw.u3 matches 1.. unless score @s tw.u4 matches 1.. "
             "unless score @s tw.u5 matches 1.. unless score @s tw.u6 matches 1.. unless score @s tw.u7 matches 1.. unless score @s tw.u8 matches 1.. "
             "unless score @s tw.u11 matches 1.. run tellraw @s " + tj({"text": "  No upgrades yet: clear a floor to pick one.", "color": "gray"})]
    fn("tower/summary", summ)
    # sidebar (shown to team tower): floor and climbers for everyone; in a solo climb also your lives, falls and upgrades.
    # Positive scores are shown as numbers; upgrades get negative scores (so they sort below) and a fixed text instead.
    side = ["scoreboard players reset * tw.side", f"execute store result score #pl tw if entity {inn}",
            "execute unless score #tstate tw matches 2.. run return 0",
            "scoreboard players operation #f tw.side = #floor tw", "scoreboard players display name #f tw.side " + tj({"text": "Floor", "color": "white", "bold": True}),
            "execute if score #pl tw matches 2.. run scoreboard players operation #c tw.side = #pl tw",
            "execute if score #pl tw matches 2.. run scoreboard players display name #c tw.side " + tj({"text": "Climbers", "color": "gray"}),
            f"execute if score #pl tw matches 1 as {inn} run function {T}/side_solo"]
    fn("tower/side", side)
    solo = ["execute if score @s tw.lives matches 1.. run scoreboard players operation #lv tw.side = @s tw.lives",
            "execute if score @s tw.lives matches 1.. run scoreboard players display name #lv tw.side " + tj({"text": "Extra Lives", "color": "green"}),
            f"execute if score #chal tw matches 1 run scoreboard players set #fa tw.side {MAX_FALLS}",
            "execute if score #chal tw matches 1 run scoreboard players operation #fa tw.side -= @s tw.falls",
            "execute if score #chal tw matches 1 run scoreboard players display name #fa tw.side " + tj({"text": "Strikes left", "color": "gold"})]
    for uid in SIDE:
        _, name, color, _, _ = UPGRADES[uid - 1]
        solo.append(f"execute if score @s tw.u{uid} matches 1.. run scoreboard players set #u{uid} tw.side -{uid}")
        for lv in range(1, len(ROMAN) + 1):
            rng = f"{lv}.." if lv == len(ROMAN) else str(lv)
            solo += [f"execute if score @s tw.u{uid} matches {rng} run scoreboard players display name #u{uid} tw.side " + tj({"text": f"{name} {ROMAN[lv - 1]}", "color": color}),
                     f"execute if score @s tw.u{uid} matches {rng} run scoreboard players display numberformat #u{uid} tw.side fixed " + tj({"text": stat(uid, lv), "color": "gray"})]
    fn("tower/side_solo", solo)
    # the Climb Log: right-click to see your build in chat (it's consumed, so it's handed straight back)
    wj(f"data/{NS}/advancement/towerlog.json", {"criteria": {"c": {"trigger": "minecraft:consume_item", "conditions": {"item": {"items": "minecraft:book"}}}},
                                                 "rewards": {"function": f"{T}/log"}})
    fn("tower/log", ["advancement revoke @s only pvp:towerlog", "execute unless entity @s[tag=tw.in] run return 0",
                     f"function {T}/summary", f"give @s {LOG}"])

    # ------------------------------------------------------------------ on-hit upgrades (Crab Champions style)
    # Any damage you deal (melee, gun, ability, drone) fires player_hurt_entity; the mobs hurt this tick have HurtTime 10.
    # tw.inhit stops the bonus damage below from triggering it again.
    wj(f"data/{NS}/advancement/towerhit.json", {"criteria": {"c": {"trigger": "minecraft:player_hurt_entity"}}, "rewards": {"function": f"{T}/onhit"}})
    wj(f"data/{NS}/advancement/towerhurt.json", {"criteria": {"c": {"trigger": "minecraft:entity_hurt_player"}}, "rewards": {"function": f"{T}/thorns"}})
    me = "@p[tag=tw.inhit]"
    chance = lambda uid: [f"execute store result score #r tw run random value 1..100", f"scoreboard players operation #ch tw = @s tw.u{uid}",
                          "scoreboard players set #k tw 15", "scoreboard players operation #ch tw *= #k tw", "execute if score #ch tw matches 76.. run scoreboard players set #ch tw 75"]
    oh = [f"advancement revoke @s only {NS}:towerhit", "execute unless entity @s[tag=tw.in] run return 0", "execute if entity @s[tag=tw.inhit] run return 0",
          "tag @s add tw.inhit", "execute as @e[tag=tw.mob,distance=..64,nbt={HurtTime:10s}] run tag @s add tw.hit"]
    oh += [f"execute if score @s tw.u13 matches {lv} as @e[tag=tw.hit] run data merge entity @s {{Fire:{20 * (1 + 2 * min(int(lv[0]), 3))}s}}" for lv in ("1", "2", "3..")]
    oh += [f"execute if score @s tw.u14 matches {lv} as @e[tag=tw.hit] run effect give @s minecraft:slowness 2 {amp}" for lv, amp in (("1", 0), ("2", 1), ("3..", 2))]
    oh += ["execute if score @s tw.u14 matches 3.. as @e[tag=tw.hit] run effect give @s minecraft:weakness 2 0"]
    oh += [f"execute if score @s tw.u15 matches {lv} as @e[tag=tw.hit] run effect give @s minecraft:wither 3 {amp}" for lv, amp in (("1", 0), ("2", 1), ("3..", 2))]
    oh += ["execute if score @s tw.u12 matches 1.. run function " + f"{T}/oh_crit", "execute if score @s tw.u16 matches 1.. run function " + f"{T}/oh_lightning",
           "execute if score @s tw.u17 matches 1.. run function " + f"{T}/oh_explosive",
           "tag @e[tag=tw.hit] remove tw.hit", "tag @s remove tw.inhit"]
    fn("tower/onhit", oh)
    fn("tower/oh_crit", [*chance(12), "execute if score #r tw > #ch tw run return 0",
                         f"execute as @e[tag=tw.hit] run damage @s 5 minecraft:player_attack by {me}",
                         "execute at @e[tag=tw.hit] run particle minecraft:crit ~ ~1 ~ 0.3 0.5 0.3 0.4 25",
                         "playsound minecraft:entity.player.attack.crit player @s ~ ~ ~ 1 1"])
    fn("tower/oh_lightning", [*chance(16), "execute if score #r tw > #ch tw run return 0",
                              *[f"execute if score @s tw.u16 matches {lv} as @e[tag=tw.hit] run damage @s {6 + 2 * min(int(lv[0]), 6)} minecraft:lightning_bolt by {me}"
                                for lv in ("1", "2", "3", "4", "5", "6..")],
                              "execute at @e[tag=tw.hit] run particle minecraft:electric_spark ~ ~1 ~ 0.3 1.2 0.3 0.4 60",
                              "execute at @e[tag=tw.hit] run particle minecraft:flash{color:[1.0,1.0,1.0,1.0]} ~ ~1 ~ 0 0 0 0 1",
                              "playsound minecraft:entity.lightning_bolt.thunder player @s ~ ~ ~ 0.4 1.6"])
    fn("tower/oh_explosive", [*chance(17), "execute if score #r tw > #ch tw run return 0",
                              f"execute at @e[tag=tw.hit] as @e[tag=tw.mob,distance=..3] run damage @s 5 minecraft:explosion by {me}",
                              "execute at @e[tag=tw.hit] run particle minecraft:explosion ~ ~1 ~ 0.5 0.5 0.5 0 3",
                              "execute at @e[tag=tw.hit] run playsound minecraft:entity.generic.explode player @a ~ ~ ~ 0.7 1.3"])
    fn("tower/thorns", [f"advancement revoke @s only {NS}:towerhurt", "execute unless entity @s[tag=tw.in] run return 0",
                        "execute unless score @s tw.u18 matches 1.. run return 0",
                        *[f"execute if score @s tw.u18 matches {lv} as @e[tag=tw.mob,distance=..3] run damage @s {2 * min(int(lv[0]), 6)} minecraft:thorns by @p[tag=tw.in,distance=..0.1]"
                          for lv in ("1", "2", "3", "4", "5", "6..")],
                        "particle minecraft:enchanted_hit ~ ~1 ~ 0.6 0.6 0.6 0.2 15"])
    fn("tower/drone", [   # as and at a player with the drone: zap the nearest mob in 16 blocks
        "particle minecraft:end_rod ~ ~2.6 ~ 0.15 0.1 0.15 0 4",
        "execute unless entity @e[tag=tw.mob,distance=..16] run return 0",
        *[f"execute if score @s tw.u21 matches {lv} run damage @n[tag=tw.mob,distance=..16] {3 * min(int(lv[0]), 4)} minecraft:magic by @s" for lv in ("1", "2", "3", "4..")],
        "execute at @n[tag=tw.mob,distance=..16] run particle minecraft:electric_spark ~ ~1 ~ 0.2 0.4 0.2 0.3 20",
        "playsound minecraft:block.beacon.power_select player @s ~ ~ ~ 0.3 2"])
    fn("tower/blackhole", [   # as and at a player with it: pull mobs within 9 blocks in, then hurt everything close
        "tag @s add tw.bh",
        "execute as @e[tag=tw.mob,distance=2..9] at @s facing entity @p[tag=tw.bh] feet run tp @s ^ ^ ^2.5",
        *[f"execute if score @s tw.u22 matches {lv} as @e[tag=tw.mob,distance=..4] run damage @s {4 * min(int(lv[0]), 5)} minecraft:magic by @p[tag=tw.bh]" for lv in ("1", "2", "3", "4", "5..")],
        "particle minecraft:reverse_portal ~ ~1 ~ 3 1 3 0.5 150", "particle minecraft:portal ~ ~1 ~ 0.5 0.5 0.5 1 60",
        "playsound minecraft:entity.enderman.teleport player @a[distance=..16] ~ ~ ~ 1 0.5", "tag @s remove tw.bh"])

    # ------------------------------------------------------------------ challenge floors
    x1, x2, z1, z2 = TCX - R, TCX + R, TCZ - R, TCZ + R
    names = {2: "Parkour", 4: "Glass Bridge", 5: "Maze", 6: "Crafting"}
    fn("tower/pick_challenge", [   # a different challenge from last time: index (last + 1..n-1) mod n
        f"execute store result score #r tw run random value 1..{len(CHALLENGES) - 1}", "scoreboard players operation #ci tw = #lasti tw",
        "scoreboard players operation #ci tw += #r tw", f"scoreboard players set #k tw {len(CHALLENGES)}", "scoreboard players operation #ci tw %= #k tw",
        "scoreboard players operation #lasti tw = #ci tw",
        *[f"execute if score #ci tw matches {i} run scoreboard players set #ttype tw {t}" for i, t in enumerate(CHALLENGES)]])
    strikes = [{"text": " · strikes ", "color": "gray"}, {"score": {"name": "@s", "objective": "tw.falls"}, "color": "red", "bold": True},
               {"text": f"/{MAX_FALLS}", "color": "red"}]
    timer = [{"text": " · ", "color": "gray"}, {"score": {"name": "#ctime", "objective": "tw"}, "color": "white", "bold": True}, {"text": " s", "color": "gray"}]
    head = lambda n: [{"text": f"🗼 {n}", "color": "light_purple", "bold": True}]
    fn("tower/sec_chal", [
        # maze and crafting run against the clock; when it runs out everyone takes a strike and gets 30 s more
        "execute if score #ttype tw matches 5..6 run scoreboard players remove #ctime tw 1",
        "execute if score #ttype tw matches 5..6 if score #ctime tw matches ..0 run tellraw @a[tag=tw.in] " + tj({"text": "⏰ Time's up! Everyone takes a strike.", "color": "red"}),
        f"execute if score #ttype tw matches 5..6 if score #ctime tw matches ..0 as {inn} run function {T}/strike",
        "execute if score #ttype tw matches 5..6 if score #ctime tw matches ..0 run scoreboard players set #ctime tw 30",
        # crafting: a mob every 15 s keeps you moving
        "execute if score #ttype tw matches 6 run scoreboard players add #cm tw 1",
        f"execute if score #ttype tw matches 6 if score #cm tw matches 15.. run function {T}/spawn_one",
        "execute if score #cm tw matches 15.. run scoreboard players set #cm tw 0",
        "execute if score #ttype tw matches 2 as @a[tag=tw.in] run title @s actionbar " + tj(head("Parkour") + [{"text": " · reach the gold block", "color": "gray"}] + strikes),
        "execute if score #ttype tw matches 4 as @a[tag=tw.in] run title @s actionbar " + tj(head("Glass Bridge") + [{"text": " · one pane in every row is fake", "color": "gray"}] + strikes),
        "execute if score #ttype tw matches 5 as @a[tag=tw.in] run title @s actionbar " + tj(head("Maze") + [{"text": " · find the gold block", "color": "gray"}] + timer + strikes),
        *[f"execute if score #ttype tw matches 6 if score #rec tw matches {i} as @a[tag=tw.in] run title @s actionbar " + tj(
            head("Craft") + [{"text": f": {r[1]}", "color": "yellow", "bold": True}] + timer + strikes) for i, r in enumerate(RECIPES, 1)],
    ])
    fn("tower/strike", [   # as a player: a strike (wrong move, time up); the last one kills you
        "scoreboard players add @s tw.falls 1",
        f"execute if score @s tw.falls matches {MAX_FALLS}.. run tellraw @a[tag=tw.in] " + tj([{"selector": "@s", "color": "yellow"}, {"text": " ran out of strikes!", "color": "red"}]),
        f"execute if score @s tw.falls matches {MAX_FALLS}.. run return run kill @s",
        "title @s actionbar " + tj([{"text": "Strike! ", "color": "red", "bold": True}, {"score": {"name": "@s", "objective": "tw.falls"}, "color": "red", "bold": True},
                                    {"text": f"/{MAX_FALLS}", "color": "red"}]),
        "playsound minecraft:block.note_block.didgeridoo player @s ~ ~ ~ 1 0.6", f"function {T}/side"])

    # glass bridge: 6 rows of two 2x2 panes over magma; in every row one is fake (rolled each time) and shatters
    rows = [(6 - 3 * k, k) for k in range(6)]   # (z of the row's first block, row number)
    panes = lambda k, side: ((-3 if side == 0 else 2), 6 - 3 * k)   # top-left corner of that pane
    gb = [f"fill {x1} {TY} {z1} {x2} {TY} {z2} minecraft:magma_block", f"fill {at(-2, 2, 9)} {at(2, 2, 11)} minecraft:polished_deepslate",
          f"fill {at(-1, 2, -12)} {at(1, 2, -10)} minecraft:gold_block", f"setblock {at(0, 3, -12)} minecraft:end_rod"]
    for _, k in rows:
        for side in (0, 1):
            px, pz = panes(k, side)
            gb.append(f"fill {at(px, 2, pz)} {at(px + 1, 2, pz + 1)} minecraft:glass")
    fn("tower/room/glass", gb)
    fn("tower/floor_glass", [f"function {T}/room/glass", *[f"execute store result score #g{k} tw run random value 0..1" for _, k in rows],
                             floor_title("Glass Bridge: one pane in every row is fake!", "aqua")])
    gt = []
    for _, k in rows:
        for side in (0, 1):
            px, pz = panes(k, side)
            gt.append(f"execute if score #g{k} tw matches {side} if block {at(px, 2, pz)} minecraft:glass "
                      f"if entity @a[tag=tw.in,x={TCX + px},y={TY + 3},z={TCZ + pz},dx=1,dy=0,dz=1] run function {T}/glass/{k}_{side}")
            fn(f"tower/glass/{k}_{side}", [f"fill {at(px, 2, pz)} {at(px + 1, 2, pz + 1)} minecraft:air",
                                           f"particle minecraft:block{{block_state:\"minecraft:glass\"}} {at(px + 1, 2.5, pz + 1)} 0.6 0.2 0.6 0.1 40",
                                           f"playsound minecraft:block.glass.break player @a {at(px + 1, 2, pz + 1)} 1.5 0.8"])
    fn("tower/glass_tick", gt)

    # maze: 10 hedge mazes (random each build), a roof so nobody jumps over, gold block at the far end
    fn("tower/floor_maze", [*pick_layout("maze"), floor_title("Maze: find the gold block", "green"),
                            "scoreboard players operation #ctime tw = #floor tw", f"scoreboard players add #ctime tw {MAZE_SECS}",
                            "execute if score #ctime tw matches 121.. run scoreboard players set #ctime tw 120"])
    mrnd = random.Random(4242)
    N = 12   # cells per side; cell (i, j) is the block at x = -11 + 2i, z = -11 + 2j
    for m in range(1, LAYOUTS + 1):
        seen, stack, edges = {(0, N - 1)}, [(0, N - 1)], []
        while stack:
            ci, cj = stack[-1]
            nb = [(ci + a, cj + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= ci + a < N and 0 <= cj + b < N and (ci + a, cj + b) not in seen]
            if not nb: stack.pop(); continue
            nxt = mrnd.choice(nb); seen.add(nxt); edges.append(((ci, cj), nxt)); stack.append(nxt)
        adj = {}
        for a, c in edges: adj.setdefault(a, []).append(c); adj.setdefault(c, []).append(a)
        dist, todo = {(0, N - 1): 0}, [(0, N - 1)]
        while todo:
            c = todo.pop(0)
            for d in adj.get(c, []):
                if d not in dist: dist[d] = dist[c] + 1; todo.append(d)
        gi, gj = max(dist, key=dist.get)   # the cell furthest from the start
        bx = lambda i: -11 + 2 * i
        cmds = [f"fill {at(-12, 1, -12)} {at(12, 3, 12)} minecraft:azalea_leaves[persistent=true]", f"fill {at(-12, 4, -12)} {at(12, 4, 12)} minecraft:barrier"]
        for i in range(N):
            for j in range(N):
                cmds.append(f"fill {at(bx(i), 1, bx(j))} {at(bx(i), 3, bx(j))} minecraft:air")
                if (i + j) % 3 == 0: cmds.append(f"setblock {at(bx(i), 3, bx(j))} minecraft:light[level=12]")
        for (ai, aj), (ci2, cj2) in edges:
            cmds.append(f"fill {at((bx(ai) + bx(ci2)) // 2, 1, (bx(aj) + bx(cj2)) // 2)} {at((bx(ai) + bx(ci2)) // 2, 3, (bx(aj) + bx(cj2)) // 2)} minecraft:air")
        cmds += [f"setblock {at(bx(gi), 0, bx(gj))} minecraft:gold_block", f"setblock {at(bx(gi), 3, bx(gj))} minecraft:end_rod"]
        fn(f"tower/room/maze_{m}", cmds)

    # crafting: the materials for a random item, split over 12 barrels (random each time) with junk; craft it to clear
    cr = ["kill @e[tag=tw.deco]", f"setblock {at(0, 1, -1)} minecraft:crafting_table"]
    for (bx2, bz2) in BARRELS:
        cr.append(f"setblock {at(bx2, 1, bz2)} minecraft:barrel[facing=up]")
    for (dx, dz, b) in ((-12, -5, "bookshelf"), (12, -5, "bookshelf"), (-12, 1, "hay_block"), (12, 1, "hay_block"), (-6, -12, "bookshelf"), (6, -12, "bookshelf"),
                        (-6, 7, "hay_block"), (6, 7, "hay_block")):
        cr.append(f"setblock {at(dx, 1, dz)} minecraft:{b}")
    fn("tower/room/craft", cr)
    fc = [f"function {T}/room/craft", f"execute store result score #rec tw run random value 1..{len(RECIPES)}",
          "scoreboard players operation #ctime tw = #floor tw", f"scoreboard players add #ctime tw {CRAFT_SECS}",
          "execute if score #ctime tw matches 121.. run scoreboard players set #ctime tw 120", "scoreboard players set #cm tw 0"]
    for (bx2, bz2) in BARRELS:   # junk in every barrel, two random pieces
        for slot in (13, 22):
            fc.append(f"execute store result score #r tw run random value 1..{len(JUNK)}")
            fc += [f"execute if score #r tw matches {i} run item replace block {at(bx2, 1, bz2)} container.{slot} with minecraft:{j} {1 + (i % 3)}"
                   for i, j in enumerate(JUNK, 1)]
    for ri, (item, name, stacks, hint) in enumerate(RECIPES, 1):
        for si, (ing, cnt) in enumerate(stacks):   # each stack in a random barrel, in its own slot so none overwrite
            fc.append(f"execute if score #rec tw matches {ri} store result score #b tw run random value 1..{len(BARRELS)}")
            fc += [f"execute if score #rec tw matches {ri} if score #b tw matches {bi} run item replace block {at(bx2, 1, bz2)} container.{2 * si + 1} with minecraft:{ing} {cnt}"
                   for bi, (bx2, bz2) in enumerate(BARRELS, 1)]
        fc += [f"execute if score #rec tw matches {ri} run title @a[tag=tw.in] subtitle " + tj([{"text": "Craft: ", "color": "gray"}, {"text": name, "color": "yellow", "bold": True}]),
               f"execute if score #rec tw matches {ri} run tellraw @a[tag=tw.in] " + tj([{"text": "🔨 Crafting challenge: ", "color": "light_purple", "bold": True},
                                                                                       {"text": f"craft a {name}", "color": "yellow", "bold": True},
                                                                                       {"text": f" ({hint}). The materials are hidden in the barrels; use the crafting table.", "color": "gray"}]),
               f"execute if score #rec tw matches {ri} run summon minecraft:text_display {at(0.5, 2.6, -0.5)} {{Tags:[\"tw.deco\"],billboard:\"center\","
               f"text:{tj([{'text': 'Craft: ', 'color': 'gray'}, {'text': name, 'color': 'yellow', 'bold': True}])}}}"]
    fn("tower/floor_craft", fc)
    fn("tower/craft_check", [f"execute if score #rec tw matches {ri} if items entity @s container.* minecraft:{r[0]} run return run function {T}/craft_done"
                             for ri, r in enumerate(RECIPES, 1)])
    fn("tower/craft_done", ["tellraw @a[tag=tw.in] " + tj([{"selector": "@s", "color": "yellow"}, {"text": " crafted it!", "color": "green"}]), f"function {T}/clear"])

    # ------------------------------------------------------------------ the room
    x1, x2, z1, z2 = TCX - R, TCX + R, TCZ - R, TCZ + R
    fn("tower/room/clear", ["kill @e[tag=tw.deco]",
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
