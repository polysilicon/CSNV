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
- Waves of tiny zombies, husks, piglin brutes, drowned, zombie villagers and vindicators; every 5th wave a Giant (a zombie
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
KB_RESIST = 0.75                      # mobs: knockback resistance (a sword hit is a fixed distance, huge at this size)
X1, X2, Z1, Z2 = -8, 8, 6, 10        # interior
FLOOR = 97                            # floor blocks; players stand at FLOOR + 1
SPAWN = (0.5, FLOOR + 1, 8.5)
MOB_SPAWNS = [(-7.5, 6.5), (7.5, 6.5), (-7.5, 9.5), (7.5, 9.5)]
NPC_POS = (-6.5, None, 5.5)           # y filled in from the lobby
SHOP_POS = (0.5, FLOOR + 1, 9.5)      # the Toy Shop: right-click it for upgrades (like Outbreak's Arsenal), next to the spawn
BOX = f"x={X1 - 1},y={FLOOR - 1},z={Z1 - 1},dx={X2 - X1 + 2},dy=4,dz={Z2 - Z1 + 2}"
COUNTDOWN, BREAK, ALIVE_MAX = 200, 200, 15
# cover: (x, z, height, block) - full cubes only; never on the spawns or the mob corners
COVER = [(-5, 7, 1, "red_concrete"), (-5, 8, 1, "red_concrete"), (-4, 7, 1, "red_concrete"),
         (4, 9, 1, "blue_concrete"), (4, 8, 1, "blue_concrete"), (5, 9, 1, "blue_concrete"),
         (-1, 6, 1, "yellow_concrete"), (2, 10, 1, "lime_concrete"), (-2, 10, 1, "orange_concrete"),
         (-2, 8, 2, "bookshelf"), (2, 7, 2, "bookshelf"),             # floor-to-ceiling: you go round these
         (6, 7, 1, "hay_block"), (-6, 9, 1, "hay_block"), (0, 6, 1, "magenta_concrete"), (1, 10, 1, "light_blue_concrete")]
# The concrete soldiers: everyone has the same loadout, the colour is just the look (heads: /heads "Concrete (colour)",
# in heads.json as concrete_<key>). id, key, name, text colour, leather dye
SOLDIERS = [(1, "red", "Red Soldier", "red", 11546150), (2, "blue", "Blue Soldier", "blue", 3949738),
            (3, "lime", "Lime Soldier", "green", 8439583), (4, "yellow", "Yellow Soldier", "yellow", 16701501),
            (5, "orange", "Orange Soldier", "gold", 16351261), (6, "purple", "Purple Soldier", "dark_purple", 8991416),
            (7, "cyan", "Cyan Soldier", "dark_aqua", 1481884), (8, "pink", "Pink Soldier", "light_purple", 15961002)]
RANDOM, MENU, LEAVE, SHOP = 20, 21, 22, 23   # mo.join values besides a soldier's id; upgrades are 31+
KILL_PTS, WAVE_PTS = 10, 20                   # points per kill, and per wave number when a wave is cleared
# Upgrades, bought with points during a run (lost when you die): code, key, name, icon, cost of each tier in order
# (None = can be bought again and again, at ONE_OFF's price), lore
UPGRADES = [(31, "sword", "Bayonet upgrade", "iron_sword", [50, 120, 250], "Stone > iron > diamond > netherite"),
            (32, "armor", "Armor upgrade", "iron_chestplate", [40, 100, 220], "Leather > chainmail > iron > diamond"),
            (33, "rifle", "Rifle upgrade", "bow", [30, 70, 150], "Power I > II > III"),
            (34, "health", "Extra hearts", "golden_apple", [60, 120, 200], "+2 hearts per tier"),
            (35, "speed", "Running shoes", "leather_boots", [80], "Move faster"),
            (36, "arrows", "Arrows", "arrow", None, "+16 arrows"),
            (37, "medkit", "Medkit", "glistering_melon_slice", None, "Heal 4 hearts now")]
ONE_OFF = {"arrows": 15, "medkit": 25}
TIER_OBJ = {"sword": "mo.sw", "armor": "mo.ar", "rifle": "mo.bw", "health": "mo.hp", "speed": "mo.sp"}
MICRO_ATTRS = ("scale", "movement_speed", "jump_strength", "entity_interaction_range", "block_interaction_range")
# min wave, roll <=, type, extra NBT
# no spiders: they climb the walls straight up to the glass ceiling and stay there
POOL = [(6, 12, "vindicator", ',equipment:{mainhand:{id:"minecraft:iron_axe",count:1}},drop_chances:{mainhand:0.0f}'),
        (5, 24, "zombie_villager", ",IsBaby:0b"), (4, 38, "drowned", ",IsBaby:0b"), (3, 55, "piglin_brute", ",IsImmuneToZombification:1b"), (2, 72, "husk", ",IsBaby:0b")]


def build(b):
    fn, tj, say, NS = b.fn, b.tj, b.say, b.NS
    M = f"{NS}:micro"
    item, armor = b.item, b.armor
    micro_attrs = [f"attribute @s minecraft:scale modifier add {NS}:micro {SCALE - 1} add_value",
                   f"attribute @s minecraft:movement_speed modifier add {NS}:micro {SLOW} add_multiplied_base",
                   f"attribute @s minecraft:jump_strength modifier add {NS}:micro {JUMP} add_multiplied_base",
                   f"attribute @s minecraft:entity_interaction_range modifier add {NS}:micro -0.67 add_multiplied_base",
                   f"attribute @s minecraft:block_interaction_range modifier add {NS}:micro -1 add_multiplied_base"]
    def leather(dye):
        return [f"item replace entity @s armor.{sl} with minecraft:leather_{pc}[minecraft:dyed_color={dye},minecraft:unbreakable={{}}]"
                for sl, pc in (("chest", "chestplate"), ("legs", "leggings"), ("feet", "boots"))]
    for (sid, key, name, color, dye) in SOLDIERS:
        head = (f'item replace entity @s armor.head with minecraft:player_head[minecraft:profile={{properties:[{{name:"textures",'
                f'value:"{b.HEADS["concrete_" + key]}"}}]}},minecraft:custom_name={{"text":"{name}","color":"{color}","italic":false}}]')
        fn(f"micro/kit/{key}", [f"give @s {item('stone_sword', 'Bayonet', 'gray')}", f"give @s {item('bow', 'Toy Rifle', color)}",
                                "give @s minecraft:arrow 16", "give @s minecraft:cooked_beef 8", head, *leather(dye),
                                f"tellraw @s {tj([{'text': '🔬 You are the ', 'color': 'gray'}, {'text': name, 'color': color, 'bold': True}])}"])
    def head_icon(k):
        it = b.icon("player_head", k[2], k[3], ["Bayonet · Toy Rifle + 16 arrows", "Leather armor in your colour", "", "Click to join"])
        it["components"]["minecraft:profile"] = {"properties": [{"name": "textures", "value": b.HEADS["concrete_" + k[1]]}]}
        return it
    fn("micro/give_kit", [f"execute if score @s mo.kit matches {k[0]} run function {M}/kit/{k[1]}" for k in SOLDIERS])

    # ------------------------------------------------------------------ points and upgrades
    shop_btn = {"text": "right-click the 🛒 Toy Shop by the spawn for upgrades", "color": "gold"}
    fn("micro/points", ["scoreboard players operation @s mo.kc += @s mo.k",
                        f"scoreboard players operation #k mo = @s mo.k", f"scoreboard players operation #k mo *= #{KILL_PTS} mo",
                        "scoreboard players operation @s mo.pts += #k mo", "scoreboard players set @s mo.k 0"])
    def tier_apply(key, n):
        mats = {1: "iron", 2: "diamond", 3: "netherite"}
        if key == "sword": return ["clear @s #minecraft:swords", f"give @s {item(mats[n] + '_sword', 'Bayonet', 'gray')}"]
        if key == "armor":
            m = {1: "chainmail", 2: "iron", 3: "diamond"}[n]
            return [f"item replace entity @s armor.{sl} with minecraft:{m}_{pc}[minecraft:unbreakable={{}}]"
                    for sl, pc in (("chest", "chestplate"), ("legs", "leggings"), ("feet", "boots"))]
        if key == "rifle": return ["clear @s minecraft:bow", f"give @s {item('bow', 'Toy Rifle', 'gold', {'power': n})}"]
        if key == "health": return [f"attribute @s minecraft:max_health modifier remove {NS}:micro_hp",
                                    f"attribute @s minecraft:max_health modifier add {NS}:micro_hp {4 * n} add_value", "effect give @s minecraft:instant_health 1 1 true"]
        if key == "speed": return [f"attribute @s minecraft:movement_speed modifier add {NS}:micro_spd 0.2 add_multiplied_base"]
    buy = [f"execute unless entity @s[tag=mo.in] run return run {say('@s', 'Upgrades are for players in a Micro Outbreak run.', 'red')}"]
    for (code, key, name, ic, costs, lore) in UPGRADES:
        buy.append(f"execute if score #j mo matches {code} run return run function {M}/up/{key}")
        if costs is None:
            c = ONE_OFF[key]
            fn(f"micro/up/{key}", [f"execute if score @s mo.pts matches ..{c - 1} run return run {say('@s', f'{name} costs {c} points.', 'red')}",
                                   f"scoreboard players remove @s mo.pts {c}",
                                   "give @s minecraft:arrow 16" if key == "arrows" else "effect give @s minecraft:instant_health 1 1 true",
                                   f"tellraw @s {tj([{'text': 'Bought ', 'color': 'green'}, {'text': name, 'color': 'gold'}, {'text': ' · ', 'color': 'dark_gray'}, {'score': {'name': '@s', 'objective': 'mo.pts'}, 'color': 'white'}, {'text': ' points left', 'color': 'gray'}])}",
                                   "playsound minecraft:entity.villager.yes neutral @s ~ ~ ~ 0.6 1.4"])
            continue
        o = TIER_OBJ[key]
        lines = [f"scoreboard players add @s {o} 0",
                 f"execute if score @s {o} matches {len(costs)}.. run return run {say('@s', f'{name} is maxed out.', 'gold')}"]
        for t, c in enumerate(costs):
            lines.append(f"execute if score @s {o} matches {t} if score @s mo.pts matches ..{c - 1} run return run {say('@s', f'{name} (tier {t + 1}) costs {c} points.', 'red')}")
        for t, c in enumerate(costs):
            lines.append(f"execute if score @s {o} matches {t} run return run function {M}/up/{key}/{t + 1}")
            fn(f"micro/up/{key}/{t + 1}", [f"scoreboard players remove @s mo.pts {c}", f"scoreboard players set @s {o} {t + 1}", *tier_apply(key, t + 1),
                                           f"tellraw @s {tj([{'text': 'Upgraded: ', 'color': 'green'}, {'text': f'{name} {t + 1}/{len(costs)}', 'color': 'gold'}, {'text': ' · ', 'color': 'dark_gray'}, {'score': {'name': '@s', 'objective': 'mo.pts'}, 'color': 'white'}, {'text': ' points left', 'color': 'gray'}])}",
                                           "playsound minecraft:block.anvil.use neutral @s ~ ~ ~ 0.5 1.6"])
        fn(f"micro/up/{key}", lines)
    fn("micro/buy", buy)
    fn("micro/shop_open", [f"execute unless entity @s[tag=mo.in] run return run {say('@s', 'The Toy Shop only serves soldiers in a Micro Outbreak run.', 'red')}",
                           "pvpmenu micro_shop", "playsound minecraft:block.chest.open player @s ~ ~ ~ 0.6 1.6"])
    b.npc_adv("microshop", "pvp.microshop", f"function {M}/shop_open")
    # the sidebar on the right (team micro only, like Outbreak's): each soldier's points and kills this run
    fn("micro/side", ["scoreboard players operation @s mo.side = @s mo.pts",
                      "execute store result storage pvp:micro side.p int 1 run scoreboard players get @s mo.pts",
                      "scoreboard players add @s mo.kc 0", "execute store result storage pvp:micro side.k int 1 run scoreboard players get @s mo.kc",
                      f"function {M}/side_fmt with storage pvp:micro side"])
    fn("micro/side_fmt", ['$scoreboard players display numberformat @s mo.side fixed [{"text":"$(p)","color":"gold"},{"text":" pts · ","color":"gray"},'
                          '{"text":"$(k)","color":"red"},{"text":" kills","color":"gray"}]'])

    # ------------------------------------------------------------------ joining (from the NPC's menu: /trigger mo.join)
    join_btn = {"text": "[Click to join]", "color": "green", "bold": True, "click_event": {"action": "run_command", "command": f"/trigger mo.join set {MENU}"},
                "hover_event": {"action": "show_text", "value": "Pick a kit and join Micro Outbreak"}}
    fn("micro/open", [f"execute unless entity @s[{b.LOBBY_BOX}] run return 0", "pvpmenu micro"])
    fn("micro/join", [
        "scoreboard players operation #j mo = @s mo.join", "scoreboard players set @s mo.join 0",
        f"execute if score #j mo matches {MENU} run return run pvpmenu micro",
        f"execute if score #j mo matches {LEAVE} run return run function {M}/leave_queue",
        f"execute if score #j mo matches {SHOP} if entity @s[tag=mo.in] run return run pvpmenu micro_shop",
        f"execute if score #j mo matches 31.. run return run function {M}/buy",
        f"execute unless entity @s[{b.LOBBY_BOX}] run return run {say('@s', 'Join Micro Outbreak from the lobby (/spawn).', 'red')}",
        f"execute if entity @s[tag=mo.in] run return run {say('@s', 'You are already in Micro Outbreak.', 'red')}",
        f"execute if entity @s[tag=pve.q] run return run {say('@s', 'Leave your Outbreak lobby first.', 'red')}",
        f"execute if entity @s[tag=tw.q] run return run {say('@s', 'Leave your Tower lobby first.', 'red')}",
        f"execute if score #j mo matches {RANDOM} store result score #j mo run random value 1..{len(SOLDIERS)}",
        f"execute unless score #j mo matches 1..{len(SOLDIERS)} run return 0",
        "scoreboard players operation @s mo.kit = #j mo",
        *[f"execute if score #j mo matches {k[0]} run tellraw @s {tj([{'text': '🔬 You picked ', 'color': 'gray'}, {'text': k[2], 'color': k[3], 'bold': True}])}"
          for k in SOLDIERS],
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
        f"attribute @s minecraft:max_health modifier remove {NS}:micro_hp", f"attribute @s minecraft:movement_speed modifier remove {NS}:micro_spd",
        *micro_attrs, f"function {M}/give_kit", "effect give @s minecraft:instant_health 1 4 true",
        "scoreboard players set @s mo.pts 0", "scoreboard players set @s mo.k 0", "scoreboard players set @s mo.kc 0", "team join micro @s", *[f"scoreboard players set @s {o} 0" for o in TIER_OBJ.values()],
        f"tellraw @s {tj([{'text': f'🔬 {KILL_PTS} points per kill and a bonus every wave: ', 'color': 'gray'}, shop_btn])}",
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
        "title @a[tag=mo.in] actionbar " + tj([{"text": "Next wave in ", "color": "gray"}, {"score": {"name": "#s", "objective": "mo"}, "color": "white"}, {"text": " s · ", "color": "gray"},
                                              {"score": {"name": "@s", "objective": "mo.pts"}, "color": "gold"}, {"text": " pts · 🛒 Toy Shop by the spawn", "color": "gray"}]),
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
                                              {"text": " · ", "color": "dark_gray"}, {"score": {"name": "#left", "objective": "mo"}, "color": "white"}, {"text": " left · ", "color": "aqua"},
                                              {"score": {"name": "@s", "objective": "mo.pts"}, "color": "gold"}, {"text": " pts", "color": "gray"}]),
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
                       # knockback is a fixed distance in blocks, so at this size a sword hit sent them across the room
                       f"attribute @s minecraft:knockback_resistance modifier add {NS}:micro {KB_RESIST} add_value",
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
        "effect give @a[tag=mo.in] minecraft:instant_health 1 4 true", "give @a[tag=mo.in] minecraft:arrow 4",
        "scoreboard players operation #b mo = #wave mo", f"scoreboard players operation #b mo *= #{WAVE_PTS} mo",
        "scoreboard players operation @a[tag=mo.in] mo.pts += #b mo",
        "give @a[tag=mo.in] minecraft:cooked_beef 2",
        f"tellraw @a[tag=mo.in] {tj([{'text': '🔬 Wave ', 'color': 'aqua'}, {'score': {'name': '#wave', 'objective': 'mo'}, 'color': 'white'},
                                     {'text': ' cleared! +', 'color': 'aqua'}, {'score': {'name': '#b', 'objective': 'mo'}, 'color': 'gold'},
                                     {'text': f' points, healed up. Next wave in {BREAK // 20} s. ', 'color': 'aqua'}, shop_btn])}",
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
        f"execute as @a[tag=mo.in,scores={{mo.k=1..}}] run function {M}/points",
        f"execute if score #state mo matches 1 run function {M}/countdown_tick",
        f"execute if score #state mo matches 2 run function {M}/wave_tick",
        f"execute if score #state mo matches 3 run function {M}/break_tick"])
    fn("micro/second", [
        "scoreboard players reset * mo.side", f"execute as @a[tag=mo.in] run function {M}/side",
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
    sx, sy, sz = SHOP_POS
    a += ["kill @e[tag=pvp.microshop]",
          f"summon minecraft:mannequin {sx} {sy} {sz} {{Tags:[\"pvp.microshop\"],Rotation:[0f,0f],Invulnerable:1b,Silent:1b,immovable:1b,"
          "hide_description:1b,CustomNameVisible:1b,CustomName:{\"text\":\"🛒 Toy Shop\",\"color\":\"gold\",\"bold\":true},"
          "attributes:[{id:\"minecraft:scale\",base:0.15d}],equipment:{chest:{id:\"minecraft:leather_chestplate\",count:1,components:{\"minecraft:dyed_color\":16351261}}}}",
          f"summon minecraft:interaction {sx} {sy} {sz} {{Tags:[\"pvp.microshop\"],width:0.3f,height:0.4f,response:1b}}"]
    fn("admin/build_micro", a)
    x, _, z = NPC_POS
    return {
        "objectives": ["mo dummy", "mo.join trigger", "mo.kit dummy", "mo.best dummy", "mo.pts dummy", "mo.k totalKillCount", "mo.kc dummy", *[f"{o} dummy" for o in TIER_OBJ.values()]],
        "load": ["scoreboard players set #3 mo 3", "scoreboard players set #5 mo 5", "scoreboard players set #20 mo 20", f"scoreboard players set #{KILL_PTS} mo {KILL_PTS}", f"scoreboard players set #{WAVE_PTS} mo {WAVE_PTS}",
                 "execute unless score #state mo matches 0.. run scoreboard players set #state mo 0",
                 "execute unless score #record mo matches 0.. run scoreboard players set #record mo 0",
                 'scoreboard objectives add mo.side dummy {"text":"🔬 Micro Outbreak","color":"aqua","bold":true}',
                 "team add micro", "team modify micro color aqua", "team modify micro friendlyFire false", "team modify micro seeFriendlyInvisibles true",
                 "scoreboard objectives setdisplay sidebar.team.aqua mo.side",
                 'bossbar add pvp:mboss {"text":"Giant","color":"dark_red"}', "bossbar set pvp:mboss color red", "bossbar set pvp:mboss visible false"],
        "reset": ["tag @s remove mo.in", "tag @s remove mo.q",
                  *[f"attribute @s minecraft:{a_} modifier remove {NS}:micro" for a_ in MICRO_ATTRS],
                  f"attribute @s minecraft:max_health modifier remove {NS}:micro_hp", f"attribute @s minecraft:movement_speed modifier remove {NS}:micro_spd"],
        "npc": (x, b.LOBBY_Y + 1, z),
        "menu": {"title": {"text": "🔬 Micro Outbreak: pick your soldier", "color": "dark_aqua"}, "rows": 4, "fill": b.PANE, "items":
                 [{"slot": sl, "item": head_icon(k), "cmd": f"trigger mo.join set {k[0]}"} for sl, k in zip(range(10, 18), SOLDIERS)]
                 + [{"slot": 4, "item": b.icon("spyglass", "Micro Outbreak", "aqua", [
                     "Toy soldiers vs tiny mobs, in a room", "under the lobby floor (everyone watches through the glass)",
                     "Every soldier has the same loadout:", "Bayonet, Toy Rifle + 16 arrows, leather armor", "",
                     f"{KILL_PTS} points per kill + a bonus every wave", "Spend them on upgrades during the run",
                     "A Giant every 5th wave · die and you watch from the lobby"]), "cmd": ""},
                    {"slot": 31, "item": b.icon("ender_eye", "🎲 Random colour", "light_purple", ["Let fate pick", "", "Click to join"]), "cmd": f"trigger mo.join set {RANDOM}"},
                    {"slot": 27, "item": b.icon("barrier", "Leave the queue", "red", ["Stop waiting for Micro Outbreak"], False), "cmd": f"trigger mo.join set {LEAVE}"}]},
        "shop": {"title": {"text": "🛒 Micro Outbreak upgrades", "color": "gold"}, "rows": 3, "fill": b.PANE, "items":
                 [{"slot": sl, "item": b.icon(ic, name, "gold", [lore, ""] + ([f"Tier {t + 1}: {c} points" for t, c in enumerate(costs)] if costs else [f"{ONE_OFF[key]} points each"])
                                              + ["", "Lost when you die", "Click to buy"]), "cmd": f"trigger mo.join set {code}"}
                  for sl, (code, key, name, ic, costs, lore) in zip((10, 11, 12, 13, 14, 15, 16), UPGRADES)]},
    }
