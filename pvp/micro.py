"""Micro Outbreak (imported by build.py): Outbreak at 1/16 scale.

Players and mobs are shrunk to scale 0.0625 (the smallest there is) and fight in a sealed toy-room arena right under
the south half of the lobby. Its ceiling is the lobby floor, made of glass there, so everyone in the lobby can watch
from above (mobs can't see through glass, so they don't fixate on the people watching).

- Interior x -8..8, z 6..10, floor at y 97 (players stand on y 98), two blocks of headroom, the glass at y 100.
  To a micro player that's a 270 x 80 block room with a 32-block ceiling.
- No clipping: everything in and around the arena is a full cube (planks, concrete "toy blocks", bookshelves, hay,
  sea lanterns, the stone walls and the glass ceiling), so there are no gaps, edges or thin shapes a 1/16-size
  hitbox could slip through. Players can't touch blocks at all (block reach 0) and their attack reach is cut to
  about a block to match their size. Anything that ends up outside the arena is put back (micro/second).
- Four basic kits of its own (MICRO_KITS), picked from the 🔬 Micro Outbreak NPC in the lobby. Others join during a
  10 s countdown or drop in at the next wave break. Dying sends you back to the lobby (normal size) to watch.
- Waves of tiny zombies, husks, spiders, drowned, zombie villagers and vindicators; every 5th wave a Giant (a zombie
  at scale 0.25, four times everyone's size). Mobs get +12% health and +6% damage per wave. Between waves (10 s)
  everyone is healed and archers get arrows. Best wave per player in mo.best, server record in #record mo.
"""

SCALE = 0.0625                        # players: the smallest scale there is
MOB_SCALE = 0.085                     # mobs a bit bigger than the players (zombie height vs player height)
GIANT_SCALE = 0.25
SLOW = -0.5                           # player movement speed x0.5 (full speed felt frantic at this size)
MOB_SLOW = -0.2                       # mobs x0.8 (x0.5 made them too slow to catch anyone)
JUMP = -0.45                          # player jump strength: about a third of the height (1-block toy blocks are obstacles)
# Mob melee reach is a fixed 0.83 blocks unless the held item has an attack_range component (26.2), so micro mobs
# hold one with a short reach. Not quite 0.83 x scale: at this size the shove between entities that bump each other
# doesn't shrink with them, so a strictly scaled reach never lands a hit
REACH, GIANT_REACH = 0.2, 0.45
X1, X2, Z1, Z2 = -8, 8, 6, 10        # interior
FLOOR = 97                            # floor blocks; players stand at FLOOR + 1
SPAWN = (0.5, FLOOR + 1, 8.5)
MOB_SPAWNS = [(-7.5, 6.5), (7.5, 6.5), (-7.5, 9.5), (7.5, 9.5)]
NPC_POS = (-6.5, None, 5.5)           # y filled in from the lobby
BOX = f"x={X1 - 1},y={FLOOR - 1},z={Z1 - 1},dx={X2 - X1 + 2},dy=4,dz={Z2 - Z1 + 2}"
COUNTDOWN, BREAK, ALIVE_MAX = 200, 200, 15
# cover: (x, z, height, block) - full cubes only; never on the spawns or the mob corners
COVER = [(-5, 7, 1, "red_concrete"), (-5, 8, 1, "red_concrete"), (-4, 7, 1, "red_concrete"),
         (4, 9, 1, "blue_concrete"), (4, 8, 1, "blue_concrete"), (5, 9, 1, "blue_concrete"),
         (-1, 6, 1, "yellow_concrete"), (2, 10, 1, "lime_concrete"), (-2, 10, 1, "orange_concrete"),
         (-2, 8, 2, "bookshelf"), (2, 7, 2, "bookshelf"),             # floor-to-ceiling: you go round these
         (6, 7, 1, "hay_block"), (-6, 9, 1, "hay_block"), (0, 6, 1, "magenta_concrete"), (1, 10, 1, "light_blue_concrete")]
# id, key, name, colour, icon, lore, item commands (built with build.py's item()/armor() in build())
MICRO_KITS = [
    (1, "needle", "Needle Knight", "gray", "iron_sword", ["Sewing Needle (Sharpness I) · iron armor", "A steady all-rounder"]),
    (2, "peashooter", "Pea Shooter", "green", "bow", ["Rubber Band Bow (Power II, Infinity) + Splinter", "Picks them off from range"]),
    (3, "bottlecap", "Bottlecap Tank", "aqua", "shield", ["Staple Axe + Bottle Cap shield · heavy armor", "Holds the line"]),
    (4, "crumb", "Crumb Medic", "light_purple", "splash_potion", ["Toothpick + 3 healing splashes · Regeneration", "Keeps everyone standing"]),
]
RANDOM = 5
MICRO_ATTRS = ("scale", "movement_speed", "jump_strength", "entity_interaction_range", "block_interaction_range")
# min wave, roll <=, type, extra NBT
POOL = [(6, 12, "vindicator", ',equipment:{mainhand:{id:"minecraft:iron_axe",count:1}},drop_chances:{mainhand:0.0f}'),
        (5, 24, "zombie_villager", ",IsBaby:0b"), (4, 38, "drowned", ",IsBaby:0b"), (3, 55, "spider", ""), (2, 72, "husk", ",IsBaby:0b")]


def build(b):
    fn, tj, say, NS = b.fn, b.tj, b.say, b.NS
    M = f"{NS}:micro"
    item, armor = b.item, b.armor
    kit_items = {
        "needle": [f"give @s {item('iron_sword', 'Sewing Needle', 'gray', {'sharpness': 1})}"] + armor("iron", 1),
        "peashooter": [f"give @s {item('bow', 'Rubber Band Bow', 'green', {'power': 2, 'infinity': 1})}", "give @s minecraft:arrow 1",
                       f"give @s {item('stone_sword', 'Splinter', 'gold')}"] + armor("leather", 2, dye=5013401),
        "bottlecap": [f"give @s {item('iron_axe', 'Staple Axe', 'aqua', {'sharpness': 1})}",
                      f"item replace entity @s weapon.offhand with {item('shield', 'Bottle Cap', 'red')}"]
                     + armor({"head": "iron", "chest": "diamond", "legs": "iron", "feet": "iron"}, 2),
        "crumb": [f"give @s {item('stone_sword', 'Toothpick', 'yellow')}", b.potion("splash_potion", "strong_healing", 3),
                  "effect give @s minecraft:regeneration infinite 0 true"] + armor("chainmail", 1),
    }
    micro_attrs = [f"attribute @s minecraft:scale modifier add {NS}:micro {SCALE - 1} add_value",
                   f"attribute @s minecraft:movement_speed modifier add {NS}:micro {SLOW} add_multiplied_base",
                   f"attribute @s minecraft:jump_strength modifier add {NS}:micro {JUMP} add_multiplied_base",
                   f"attribute @s minecraft:entity_interaction_range modifier add {NS}:micro -0.67 add_multiplied_base",
                   f"attribute @s minecraft:block_interaction_range modifier add {NS}:micro -1 add_multiplied_base"]
    for (kid, key, name, color, ic, lore) in MICRO_KITS:
        fn(f"micro/kit/{key}", kit_items[key] + ["give @s minecraft:cooked_beef 8",
            f"tellraw @s {tj([{'text': '🔬 Kit: ', 'color': 'gray'}, {'text': name, 'color': color, 'bold': True}])}"])
    fn("micro/give_kit", [f"execute if score @s mo.kit matches {k[0]} run function {M}/kit/{k[1]}" for k in MICRO_KITS])

    # ------------------------------------------------------------------ joining (from the NPC's menu: /trigger mo.join)
    join_btn = {"text": "[Click to join]", "color": "green", "bold": True, "click_event": {"action": "run_command", "command": "/trigger mo.join set 6"},
                "hover_event": {"action": "show_text", "value": "Pick a kit and join Micro Outbreak"}}
    fn("micro/open", [f"execute unless entity @s[{b.LOBBY_BOX}] run return 0", "pvpmenu micro"])
    fn("micro/join", [
        "scoreboard players operation #j mo = @s mo.join", "scoreboard players set @s mo.join 0",
        "execute if score #j mo matches 6 run return run pvpmenu micro",
        f"execute if score #j mo matches 9 run return run function {M}/leave_queue",
        f"execute unless entity @s[{b.LOBBY_BOX}] run return run {say('@s', 'Join Micro Outbreak from the lobby (/spawn).', 'red')}",
        f"execute if entity @s[tag=mo.in] run return run {say('@s', 'You are already in Micro Outbreak.', 'red')}",
        f"execute if entity @s[tag=pve.q] run return run {say('@s', 'Leave your Outbreak lobby first.', 'red')}",
        f"execute if entity @s[tag=tw.q] run return run {say('@s', 'Leave your Tower lobby first.', 'red')}",
        f"execute if score #j mo matches {RANDOM} store result score #j mo run random value 1..{len(MICRO_KITS)}",
        f"execute unless score #j mo matches 1..{len(MICRO_KITS)} run return 0",
        "scoreboard players operation @s mo.kit = #j mo",
        *[f"execute if score #j mo matches {k[0]} run tellraw @s {tj([{'text': '🔬 You picked ', 'color': 'gray'}, {'text': k[2], 'color': k[3], 'bold': True}])}"
          for k in MICRO_KITS],
        "execute if entity @s[tag=mo.q] run return 0", "tag @s add mo.q",
        "playsound minecraft:block.note_block.pling player @s ~ ~ ~ 1 1.4",
        f"execute if score #state mo matches 0 run return run function {M}/countdown_start",
        f"execute if score #state mo matches 1 run return run tellraw @a[tag=mo.q] {tj([{'selector': '@s', 'color': 'yellow'}, {'text': ' joined Micro Outbreak!', 'color': 'green'}])}",
        say("@s", "Micro Outbreak is running: you'll drop in at the next wave break.", "green"),
    ])
    fn("micro/leave_queue", ["tag @s remove mo.q", say("@s", "You left the Micro Outbreak queue.", "yellow"),
                              f"execute if score #state mo matches 1 unless entity @a[tag=mo.q] run function {M}/countdown_cancel"])
    fn("micro/countdown_start", [
        "scoreboard players set #state mo 1", f"scoreboard players set #timer mo {COUNTDOWN}",
        f"tellraw @a[{b.LOBBY_BOX}] " + tj([{"text": "🔬 ", "color": "aqua"}, {"selector": "@s", "color": "yellow"},
            {"text": f" is starting Micro Outbreak in {COUNTDOWN // 20} s! ", "color": "aqua"}, join_btn,
            {"text": " (watch it through the glass floor)", "color": "gray"}])])
    fn("micro/countdown_cancel", ["scoreboard players set #state mo 0", f"tellraw @a[{b.LOBBY_BOX}] {tj({'text': '🔬 Micro Outbreak was called off.', 'color': 'gray'})}"])
    fn("micro/countdown_tick", [
        f"execute as @a[tag=mo.q] unless entity @s[{b.LOBBY_BOX}] run tag @s remove mo.q",
        f"execute unless entity @a[tag=mo.q] run return run function {M}/countdown_cancel",
        "scoreboard players remove #timer mo 1", "scoreboard players operation #s mo = #timer mo", "scoreboard players operation #s mo /= #20 mo",
        "title @a[tag=mo.q] actionbar " + tj([{"text": "🔬 Micro Outbreak starts in ", "color": "aqua"}, {"score": {"name": "#s", "objective": "mo"}, "color": "white"},
                                             {"text": " s", "color": "aqua"}]),
        f"execute if score #timer mo matches ..0 run function {M}/start"])
    fn("micro/start", ["scoreboard players set #wave mo 0", "kill @e[tag=mo.mob]", "scoreboard players set #state mo 3", "scoreboard players set #timer mo 60",
                       f"execute as @a[tag=mo.q] run function {M}/enter",
                       f"tellraw @a[tag=mo.in] {tj({'text': '🔬 You shrink to the size of a crumb... Survive!', 'color': 'aqua'})}"])
    fn("micro/enter", [   # as a queued player: shrink, kit up, into the arena
        "tag @s remove mo.q", "tag @s add mo.in", "clear @s", "effect clear @s", "function cyber:admin/reset", "gamemode adventure @s",
        *b.PERK_RESET, *[f"attribute @s minecraft:{a_} modifier remove {NS}:micro" for a_ in MICRO_ATTRS],
        *micro_attrs, f"function {M}/give_kit", "effect give @s minecraft:instant_health 1 4 true",
        f"tp @s {SPAWN[0]} {SPAWN[1]} {SPAWN[2]} 90 0",
        "title @s title {\"text\":\"🔬 MICRO\",\"color\":\"aqua\",\"bold\":true}", "title @s subtitle {\"text\":\"Everything is huge now\",\"color\":\"gray\"}",
        "playsound minecraft:entity.puffer_fish.blow_out player @s ~ ~ ~ 1 1.6"])
    fn("micro/died", [   # as a player who died in the arena: back to the lobby, normal size, to watch
        "scoreboard players add @s mo.best 0", "execute if score #wave mo > @s mo.best run scoreboard players operation @s mo.best = #wave mo",
        f"function {NS}:to_lobby",
        f"tellraw @s {tj([{'text': '🔬 You were squished on wave ', 'color': 'red'}, {'score': {'name': '#wave', 'objective': 'mo'}, 'color': 'white'},
                          {'text': '. Watch the rest through the glass floor!', 'color': 'gray'}])}",
        f"tellraw @a[tag=mo.in] {tj([{'selector': '@s', 'color': 'red'}, {'text': ' got squished!', 'color': 'gray'}])}"])

    # ------------------------------------------------------------------ waves
    fn("micro/break_tick", [
        "scoreboard players remove #timer mo 1", "scoreboard players operation #s mo = #timer mo", "scoreboard players operation #s mo /= #20 mo",
        "title @a[tag=mo.in] actionbar " + tj([{"text": "Next wave in ", "color": "gray"}, {"score": {"name": "#s", "objective": "mo"}, "color": "white"}, {"text": " s", "color": "gray"}]),
        f"execute if score #timer mo matches ..0 run function {M}/next_wave"])
    fn("micro/next_wave", [
        "scoreboard players add #wave mo 1", "execute store result score #np mo if entity @a[tag=mo.in]",
        # 5 + 3(w-1) mobs, + 3 per extra player, capped at 60
        "scoreboard players operation #tospawn mo = #wave mo", "scoreboard players remove #tospawn mo 1", "scoreboard players operation #tospawn mo *= #3 mo",
        "scoreboard players add #tospawn mo 5", "scoreboard players operation #x mo = #np mo", "scoreboard players remove #x mo 1",
        "scoreboard players operation #x mo *= #3 mo", "scoreboard players operation #tospawn mo += #x mo",
        "execute if score #tospawn mo matches 61.. run scoreboard players set #tospawn mo 60",
        "scoreboard players operation #w1 mo = #wave mo", "scoreboard players remove #w1 mo 1",
        "execute store result storage pvp:micro s.hm double 0.12 run scoreboard players get #w1 mo",
        "execute store result storage pvp:micro s.dm double 0.06 run scoreboard players get #w1 mo",
        "scoreboard players set #state mo 2", "scoreboard players set #st mo 0",
        "title @a[tag=mo.in] title [{\"text\":\"Wave \",\"color\":\"aqua\"},{\"score\":{\"name\":\"#wave\",\"objective\":\"mo\"},\"color\":\"dark_aqua\",\"bold\":true}]",
        "execute as @a[tag=mo.in] at @s run playsound minecraft:event.raid.horn player @s ~ ~ ~ 0.4 2",
        "scoreboard players operation #m mo = #wave mo", "scoreboard players operation #m mo %= #5 mo",
        f"execute if score #m mo matches 0 run function {M}/giant"])
    fn("micro/wave_tick", [
        "scoreboard players add #st mo 1",
        "execute if score #st mo matches 10.. store result score #alive mo if entity @e[tag=mo.mob]",
        f"execute if score #st mo matches 10.. if score #tospawn mo matches 1.. if score #alive mo matches ..{ALIVE_MAX - 1} run function {M}/spawn",
        "execute if score #st mo matches 10.. run scoreboard players set #st mo 0",
        "execute store result score #left mo if entity @e[tag=mo.mob]", "scoreboard players operation #left mo += #tospawn mo",
        "title @a[tag=mo.in] actionbar " + tj([{"text": "Wave ", "color": "aqua"}, {"score": {"name": "#wave", "objective": "mo"}, "color": "white"},
                                              {"text": " · ", "color": "dark_gray"}, {"score": {"name": "#left", "objective": "mo"}, "color": "white"}, {"text": " left", "color": "aqua"}]),
        "execute if score #tospawn mo matches 0 if score #alive mo matches ..3 run effect give @e[tag=mo.mob] minecraft:glowing 2 0 true",
        f"execute if score #tospawn mo matches 0 unless entity @e[tag=mo.mob] run function {M}/wave_end"])
    choose = ["execute store result score #r mo run random value 1..100", "scoreboard players set #p mo 0"]
    for (mw, roll, typ, extra) in POOL:
        choose.append(f"execute if score #p mo matches 0 if score #wave mo matches {mw}.. if score #r mo matches ..{roll} run function {M}/type {{type:\"{typ}\",extra:'{extra}'}}")
    choose.append(f"execute if score #p mo matches 0 run function {M}/type {{type:\"zombie\",extra:',IsBaby:0b'}}")
    choose.append(f"execute store result score #r mo run random value 1..{len(MOB_SPAWNS)}")
    for n, (x, z) in enumerate(MOB_SPAWNS, 1):
        choose.append(f"execute if score #r mo matches {n} run data modify storage pvp:micro m merge value {{x:{x},z:{z}}}")
    choose += [f"function {M}/summon with storage pvp:micro m", "scoreboard players remove #tospawn mo 1"]
    fn("micro/spawn", choose)
    fn("micro/type", ["scoreboard players set #p mo 1", "$data modify storage pvp:micro m merge value {type:\"$(type)\",extra:'$(extra)'}"])
    mob_attrs = f"{{id:\"minecraft:scale\",base:{MOB_SCALE}d}},{{id:\"minecraft:follow_range\",base:32d}}"
    fn("micro/summon", [
        f"$summon minecraft:$(type) $(x) {FLOOR + 1} $(z) {{Tags:[\"mo.mob\",\"mo.new\"],PersistenceRequired:1b,CanPickUpLoot:0b,"
        f"DeathLootTable:\"minecraft:empty\",attributes:[{mob_attrs}]$(extra)}}",
        f"execute as @e[tag=mo.new] run function {M}/scale with storage pvp:micro s",
        f"$particle minecraft:poof $(x) {FLOOR + 1.1} $(z) 0.1 0.05 0.1 0.01 8"])
    reach = lambda r_: ('item modify entity @s weapon.mainhand {function:"minecraft:set_components",components:{"minecraft:attack_range":'
                        f'{{max_reach:{r_}f,min_reach:0.0f}}}}}}')
    fn("micro/scale", ["tag @s remove mo.new",
                       f"attribute @s minecraft:movement_speed modifier add {NS}:micro {MOB_SLOW} add_multiplied_base",
                       # reach to scale: a stick if the hand is empty, then the attack_range on whatever is held
                       "execute unless items entity @s weapon.mainhand * run item replace entity @s weapon.mainhand with minecraft:stick",
                       "data modify entity @s drop_chances.mainhand set value 0.0f",
                       "execute if entity @s[tag=mo.giant] run " + reach(GIANT_REACH),
                       "execute unless entity @s[tag=mo.giant] run " + reach(REACH),
                       "$attribute @s minecraft:max_health modifier add pvp:micro_wave $(hm) add_multiplied_base",
                       "$attribute @s minecraft:attack_damage modifier add pvp:micro_wave $(dm) add_multiplied_base",
                       "execute store result entity @s Health float 1 run attribute @s minecraft:max_health get"])
    gx, gz = MOB_SPAWNS[1]
    fn("micro/giant", [   # every 5th wave: a Giant, four times everyone's size
        f"summon minecraft:zombie {gx} {FLOOR + 1} {gz} {{Tags:[\"mo.mob\",\"mo.new\",\"mo.giant\"],PersistenceRequired:1b,CanPickUpLoot:0b,IsBaby:0b,"
        "DeathLootTable:\"minecraft:empty\",CustomName:{\"text\":\"Giant\",\"color\":\"dark_red\",\"bold\":true},CustomNameVisible:1b,"
        f"attributes:[{{id:\"minecraft:scale\",base:{GIANT_SCALE}d}}," "{id:\"minecraft:follow_range\",base:32d},{id:\"minecraft:max_health\",base:60d},"
        "{id:\"minecraft:attack_damage\",base:7d},{id:\"minecraft:knockback_resistance\",base:0.8d}]}",
        f"execute as @e[tag=mo.new] run function {M}/scale with storage pvp:micro s",
        "execute store result bossbar pvp:mboss max run data get entity @n[tag=mo.giant] Health",
        "bossbar set pvp:mboss players @a[tag=mo.in]", "bossbar set pvp:mboss visible true",
        f"tellraw @a[tag=mo.in] {tj({'text': '🔬 A GIANT has entered the room!', 'color': 'dark_red', 'bold': True})}",
        "execute as @a[tag=mo.in] at @s run playsound minecraft:entity.ravager.roar player @s ~ ~ ~ 0.6 0.6"])
    fn("micro/wave_end", [
        "scoreboard players set #state mo 3", f"scoreboard players set #timer mo {BREAK}",
        "effect give @a[tag=mo.in] minecraft:instant_health 1 4 true", f"give @a[tag=mo.in,scores={{mo.kit=2}}] minecraft:arrow 1",
        "give @a[tag=mo.in] minecraft:cooked_beef 2",
        f"tellraw @a[tag=mo.in] {tj([{'text': '🔬 Wave ', 'color': 'aqua'}, {'score': {'name': '#wave', 'objective': 'mo'}, 'color': 'white'},
                                     {'text': f' cleared! Healed up. Next wave in {BREAK // 20} s.', 'color': 'aqua'}])}",
        "execute as @a[tag=mo.in] at @s run playsound minecraft:ui.toast.challenge_complete player @s ~ ~ ~ 0.5 1.4",
        f"execute as @a[tag=mo.q] run function {M}/enter"])
    fn("micro/game_over", [
        "scoreboard players set #state mo 0", "kill @e[tag=mo.mob]", "bossbar set pvp:mboss visible false",
        f"tellraw @a[{b.LOBBY_BOX}] {tj([{'text': '🔬 Micro Outbreak is over: they reached wave ', 'color': 'aqua'}, {'score': {'name': '#wave', 'objective': 'mo'}, 'color': 'white', 'bold': True}, {'text': '.', 'color': 'aqua'}])}",
        "execute if score #wave mo > #record mo run tellraw @a [{\"text\":\"🔬 New Micro Outbreak record: wave \",\"color\":\"gold\"},{\"score\":{\"name\":\"#wave\",\"objective\":\"mo\"},\"color\":\"white\",\"bold\":true}]",
        "execute if score #wave mo > #record mo run scoreboard players operation #record mo = #wave mo",
        "scoreboard players set #wave mo 0"])

    # ------------------------------------------------------------------ ticking (called from pvp tick / second)
    fn("micro/tick", [
        "scoreboard players enable @a mo.join", f"execute as @a[scores={{mo.join=1..}}] at @s run function {M}/join",
        f"execute if score #state mo matches 1 run function {M}/countdown_tick",
        f"execute if score #state mo matches 2 run function {M}/wave_tick",
        f"execute if score #state mo matches 3 run function {M}/break_tick"])
    fn("micro/second", [
        f"execute if score #state mo matches 2..3 unless entity @a[tag=mo.in] run function {M}/game_over",
        "execute unless score #state mo matches 2 run kill @e[tag=mo.mob]",
        # nothing stays outside the arena: mobs go back to a corner, players back to the spawn
        f"execute as @e[tag=mo.mob] unless entity @s[{BOX}] run tp @s {MOB_SPAWNS[0][0]} {FLOOR + 1} {MOB_SPAWNS[0][1]}",
        f"execute as @a[tag=mo.in] unless entity @s[{BOX}] run tp @s {SPAWN[0]} {SPAWN[1]} {SPAWN[2]}",
        "execute store result bossbar pvp:mboss value run data get entity @n[tag=mo.giant] Health",
        "execute unless entity @e[tag=mo.giant] run bossbar set pvp:mboss visible false"])

    # ------------------------------------------------------------------ the arena (and the lobby's glass floor above it)
    Y = FLOOR
    a = [f"fill {X1 - 1} {Y} {Z1 - 1} {X2 + 1} {Y + 2} {Z2 + 1} minecraft:smooth_stone",          # shell: floor + walls
         f"fill {X1} {Y + 1} {Z1} {X2} {Y + 2} {Z2} minecraft:air",
         f"fill {X1} {Y} {Z1} {X2} {Y} {Z2} minecraft:oak_planks",
         *[f"setblock {x} {Y} 8 minecraft:sea_lantern" for x in range(X1, X2 + 1, 4)],
         *[f"setblock {x} {Y + 1} {z} minecraft:sea_lantern" for x in (X1 - 1, X2 + 1) for z in (7, 9)],   # lights set in the end walls
         f"fill {X1} {b.LOBBY_Y} {Z1} {X2} {b.LOBBY_Y} {Z2} minecraft:glass"]                     # the lobby floor above
    for (x, z, h, blk) in COVER:
        a.append(f"fill {x} {Y + 1} {z} {x} {Y + h} {z} minecraft:{blk}")
    fn("admin/build_micro", a)
    x, _, z = NPC_POS
    return {
        "objectives": ["mo dummy", "mo.join trigger", "mo.kit dummy", "mo.best dummy"],
        "load": ["scoreboard players set #3 mo 3", "scoreboard players set #5 mo 5", "scoreboard players set #20 mo 20",
                 "execute unless score #state mo matches 0.. run scoreboard players set #state mo 0",
                 "execute unless score #record mo matches 0.. run scoreboard players set #record mo 0",
                 'bossbar add pvp:mboss {"text":"Giant","color":"dark_red"}', "bossbar set pvp:mboss color red", "bossbar set pvp:mboss visible false"],
        "reset": ["tag @s remove mo.in", "tag @s remove mo.q",
                  *[f"attribute @s minecraft:{a_} modifier remove {NS}:micro" for a_ in MICRO_ATTRS]],
        "npc": (x, b.LOBBY_Y + 1, z),
        "menu": {"title": {"text": "🔬 Micro Outbreak: pick a kit", "color": "dark_aqua"}, "rows": 3, "fill": b.PANE, "items":
                 [{"slot": s, "item": b.icon(k[4], k[2], k[3], k[5] + ["", "Click to join"]), "cmd": f"trigger mo.join set {k[0]}"}
                  for s, k in zip((10, 11, 15, 16), MICRO_KITS)]
                 + [{"slot": 13, "item": b.icon("spyglass", "Micro Outbreak", "aqua", [
                     "Outbreak at 1/16 scale: you and the mobs", "are tiny, in a room under the lobby floor",
                     "Everyone in the lobby watches through the glass", "", "Waves of tiny mobs, a Giant every 5th wave",
                     "Healed between waves · die and you watch", "from the lobby"]), "cmd": ""},
                    {"slot": 22, "item": b.icon("ender_eye", "🎲 Random kit", "light_purple", ["Let fate pick", "", "Click to join"]), "cmd": f"trigger mo.join set {RANDOM}"},
                    {"slot": 18, "item": b.icon("barrier", "Leave the queue", "red", ["Stop waiting for Micro Outbreak"], False), "cmd": "trigger mo.join set 9"}]},
    }
