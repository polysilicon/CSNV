"""Crispy Games (imported by build.py): a last-player-standing elimination show, six rounds in a row.

Players queue at the 🦑 Crispy Games NPC in the lobby (30 s countdown; it also runs with one player as a practice run).
Everyone plays in the same green tracksuit with a random player number; no kits or abilities. Eliminated players watch
the rest as spectators. The rounds, each in its own arena in a strip at x 1000 on the superflat ground:

1. Red Light, Green Light (z 100): cross the field to the finish line in 90 s. When the Watcher (a giant iron golem)
   turns round it's red light: after a short grace, any walking, sprinting, sneaking or jumping eliminates you (the
   movement statistics are checked, so it's exact). Not over the line in time: eliminated.
2. Glass Bridge (z 240): 12 steps of two glass panes, one of each pair fake. Stand on a fake one and it shatters;
   fall and you're out. Not across in 2 minutes: eliminated.
3. Hide and Seek (z 400): a third of the players (at least one) seek with iron swords after a 30 s head start, in a
   house of rooms and furniture. Hiders who are killed are out; seekers without a kill after 3 minutes are out.
   Skipped with fewer than 3 players left. Hiders glow for the last 30 s.
4. Honeycomb (z 560): each player gets a booth with a 7x7 wall: a shape (circle, triangle, star or umbrella) in
   yellow concrete surrounded by orange terracotta. Mine all the terracotta with the needle in 90 s without
   breaking a single yellow block.
5. Marbles (z 650): players in pairs, 10 marbles (snowballs) each, thrown into their booth's pit. The higher score
   goes through (a tie is a coin flip); an odd one out goes through.
6. Final (z 800): everyone left fights it out with the same kit; after 2 minutes everyone withers (sudden death).

A round never knocks everyone out: if it would, nobody from that round is eliminated. The last player standing wins
(cg.wins, announced to the server). Build the arenas once with function pvp:admin/build_games.
"""

X = 1000                                    # the strip's centre line
R1_Z, R2_Z, R3_Z, R4_Z, R5_Z, R6_Z = 100, 240, 400, 560, 650, 800
COUNTDOWN = 600                             # ticks in the lobby before a match starts
INTRO, OUTRO = 100, 100                     # ticks before / after each round
RLGL_T, BRIDGE_T, HIDE_T, HIDE_HEAD, HONEY_T, MARBLE_T, FINAL_T, FINAL_SD = 1800, 2400, 3600, 600, 1800, 1200, 2400, 2400
STEPS = 12                                  # glass bridge steps
BOOTHS = 32                                 # honeycomb booths (2 rows of 16)
PAIRS = 16                                  # marble booths
ROUNDS = [(1, "rlgl", "Red Light, Green Light", "green", "Cross the field. Freeze when the Watcher turns."),
          (2, "bridge", "Glass Bridge", "aqua", "One pane of each pair is fake. Choose wisely."),
          (3, "hide", "Hide and Seek", "red", "Hiders survive. Seekers need a kill."),
          (4, "honey", "Honeycomb", "gold", "Carve out the shape. Don't break it."),
          (5, "marbles", "Marbles", "light_purple", "Beat your partner: get marbles in the pit."),
          (6, "final", "The Final", "dark_red", "Last player standing wins.")]
# 7x7 shapes for the honeycomb (X = shape, kept; . = terracotta to carve away), row 0 at the top
SHAPES = {"circle": ["..XXX..", ".XXXXX.", "XXXXXXX", "XXXXXXX", "XXXXXXX", ".XXXXX.", "..XXX.."],
          "triangle": ["...X...", "...X...", "..XXX..", "..XXX..", ".XXXXX.", ".XXXXX.", "XXXXXXX"],
          "star": ["...X...", "..XXX..", "XXXXXXX", ".XXXXX.", "..XXX..", ".XX.XX.", "XX...XX"],
          "umbrella": ["..XXX..", ".XXXXX.", "XXXXXXX", "...X...", "...X...", ".X.X...", "..X...."]}
SUIT = 2063450                               # tracksuit green
NPC_POS = (7.5, None, -1.5)


import math


def build(b):
    fn, tj, say, NS, AY = b.fn, b.tj, b.say, b.NS, b.AY
    G = f"{NS}:games"
    FY = AY                                  # arena floors (players stand at FY + 1)
    YB = AY + 20                             # glass bridge level
    ALL = "@a[tag=cg.all]"
    tag_lobby = f"@a[{b.LOBBY_BOX}]"

    def xz(zc, half_x, half_z): return (X - half_x, zc - half_z, X + half_x, zc + half_z)
    AREAS = {"rlgl": xz(R1_Z + 32, 17, 36), "bridge": xz(R2_Z + 25, 12, 30), "hide": xz(R3_Z, 22, 22),
             "honey": (X - 66, R4_Z - 10, X + 66, R4_Z + 24), "marbles": (X - 66, R5_Z - 6, X + 66, R5_Z + 16), "final": xz(R6_Z, 17, 17)}
    forceload_add = [f"forceload add {a[0]} {a[1]} {a[2]} {a[3]}" for a in AREAS.values()]
    forceload_rm = [f"forceload remove {a[0]} {a[1]} {a[2]} {a[3]}" for a in AREAS.values()]
    VIEW = {"rlgl": (X + 0.5, FY + 16, R1_Z - 4, 0, 30), "bridge": (X + 14, YB + 8, R2_Z + 25, 90, 25),
            "hide": (X + 0.5, FY + 22, R3_Z + 0.5, 0, 90), "honey": (X + 0.5, FY + 12, R4_Z - 8, 0, 25),
            "marbles": (X + 0.5, FY + 10, R5_Z - 4, 0, 30), "final": (X + 0.5, FY + 16, R6_Z - 16, 0, 35)}

    def place(key, pts):
        """games/<key>/place, as each player: the next of a fixed list of spots (round robin), so nobody lands in a wall."""
        lines = ["scoreboard players operation @s cg.p = #pi cg", f"scoreboard players set #pn cg {len(pts)}",
                 "scoreboard players operation @s cg.p %= #pn cg", "scoreboard players add #pi cg 1"]
        for n, (px, py, pz, yaw, pitch) in enumerate(pts):
            lines.append(f"execute if score @s cg.p matches {n} run tp @s {px} {py} {pz} {yaw} {pitch}")
        fn(f"games/{key}/place", lines)
        return [f"scoreboard players set #pi cg 0", f"execute as @a[tag=cg.in,sort=random] run function {G}/{key}/place"]

    def elim_msg(reason):
        return (f"tellraw {ALL} " + tj([{"text": "✖ Player ", "color": "red"}, {"score": {"name": "@s", "objective": "cg.num"}, "color": "white"},
                                       {"text": " (", "color": "dark_gray"}, {"selector": "@s", "color": "gray"}, {"text": ") eliminated", "color": "red"},
                                       {"text": f" · {reason}", "color": "dark_gray"}]))

    # ------------------------------------------------------------------ joining
    fn("games/open", [f"execute unless entity @s[{b.LOBBY_BOX}] run return 0", "pvpmenu games"])
    join_btn = {"text": "[Click to join]", "color": "green", "bold": True, "click_event": {"action": "run_command", "command": "/trigger cg.join set 1"}}
    fn("games/join", [
        "scoreboard players operation #j cg = @s cg.join", "scoreboard players set @s cg.join 0",
        f"execute if score #j cg matches 2 run return run function {G}/leave_queue",
        f"execute unless entity @s[{b.LOBBY_BOX}] run return run {say('@s', 'Join Crispy Games from the lobby (/spawn).', 'red')}",
        f"execute if score #state cg matches 2..3 run return run {say('@s', 'A Crispy Games match is running. Wait for the next one!', 'red')}",
        f"execute if entity @s[tag=mo.q] run return run {say('@s', 'Leave the Micro Outbreak queue first.', 'red')}",
        f"execute if entity @s[tag=pve.q] run return run {say('@s', 'Leave your Outbreak lobby first.', 'red')}",
        f"execute if entity @s[tag=tw.q] run return run {say('@s', 'Leave your Tower lobby first.', 'red')}",
        f"execute if entity @s[tag=cg.q] run return run {say('@s', 'You are already in the queue.', 'yellow')}",
        "tag @s add cg.q", "playsound minecraft:block.note_block.bell player @s ~ ~ ~ 1 1.2",
        f"execute if score #state cg matches 0 run return run function {G}/countdown_start",
        f"tellraw @a[tag=cg.q] {tj([{'selector': '@s', 'color': 'yellow'}, {'text': ' joined Crispy Games!', 'color': 'green'}])}"])
    fn("games/leave_queue", ["tag @s remove cg.q", say("@s", "You left the Crispy Games queue.", "yellow"),
                             f"execute if score #state cg matches 1 unless entity @a[tag=cg.q] run function {G}/countdown_cancel"])
    fn("games/countdown_start", [
        "scoreboard players set #state cg 1", f"scoreboard players set #timer cg {COUNTDOWN}",
        f"tellraw {tag_lobby} " + tj([{"text": "🦑 ", "color": "light_purple"}, {"selector": "@s", "color": "yellow"},
                                      {"text": f" is starting Crispy Games in {COUNTDOWN // 20} s! ", "color": "light_purple"}, join_btn])])
    fn("games/countdown_cancel", ["scoreboard players set #state cg 0", f"tellraw {tag_lobby} {tj({'text': '🦑 Crispy Games was called off.', 'color': 'gray'})}"])
    fn("games/countdown_tick", [
        f"execute as @a[tag=cg.q] unless entity @s[{b.LOBBY_BOX}] run tag @s remove cg.q",
        f"execute unless entity @a[tag=cg.q] run return run function {G}/countdown_cancel",
        "scoreboard players remove #timer cg 1", "scoreboard players operation #s cg = #timer cg", "scoreboard players operation #s cg /= #20 cg",
        "execute store result score #n cg if entity @a[tag=cg.q]",
        "title @a[tag=cg.q] actionbar " + tj([{"text": "🦑 Crispy Games starts in ", "color": "light_purple"}, {"score": {"name": "#s", "objective": "cg"}, "color": "white"},
                                             {"text": " s · ", "color": "light_purple"}, {"score": {"name": "#n", "objective": "cg"}, "color": "white"}, {"text": " players", "color": "light_purple"}]),
        f"execute if score #timer cg matches ..0 run function {G}/start"])

    # ------------------------------------------------------------------ the match
    outfit = [f"item replace entity @s armor.{sl} with minecraft:leather_{pc}[minecraft:dyed_color={SUIT},minecraft:unbreakable={{}}]"
              for sl, pc in (("chest", "chestplate"), ("legs", "leggings"), ("feet", "boots"))]
    fn("games/start", [
        *forceload_add, "scoreboard players set #state cg 2", "scoreboard players set #round cg 0",
        "execute store result score #started cg if entity @a[tag=cg.q]",
        f"execute as @a[tag=cg.q] run function {G}/enter",
        f"tellraw {tag_lobby} " + tj([{"text": "🦑 Crispy Games has begun with ", "color": "light_purple"}, {"score": {"name": "#started", "objective": "cg"}, "color": "white"},
                                      {"text": " players. Who will be the last one standing?", "color": "light_purple"}]),
        f"function {G}/next_round"])
    fn("games/enter", [
        "tag @s remove cg.q", "tag @s add cg.all", "tag @s add cg.in", "clear @s", "effect clear @s", "function cyber:admin/reset",
        *b.PERK_RESET, "gamemode adventure @s", "team join cg @s", *outfit,
        "effect give @s minecraft:saturation infinite 0 true",
        "execute store result score @s cg.num run random value 1..456",
        f"tellraw @s {tj([{'text': '🦑 Welcome to Crispy Games. You are player ', 'color': 'light_purple'}, {'score': {'name': '@s', 'objective': 'cg.num'}, 'color': 'white', 'bold': True}])}",
        "title @s title {\"text\":\"🦑 CRISPY GAMES\",\"color\":\"light_purple\",\"bold\":true}",
        "title @s subtitle [{\"text\":\"Player \",\"color\":\"gray\"},{\"score\":{\"name\":\"@s\",\"objective\":\"cg.num\"},\"color\":\"white\"}]"])

    fn("games/elim", [   # as a player: out of the match, watch the rest
        "tag @s remove cg.in", "tag @s remove cg.safe", "tag @s add cg.lost", "tag @s add cg.spec", "clear @s", "gamemode spectator @s",
        "execute at @s run particle minecraft:large_smoke ~ ~1 ~ 0.3 0.6 0.3 0.02 30 force",
        f"execute as {ALL} at @s run playsound minecraft:entity.firework_rocket.blast master @s ~ ~ ~ 0.7 0.6",
        "title @s title {\"text\":\"ELIMINATED\",\"color\":\"red\",\"bold\":true}", "title @s subtitle {\"text\":\"Watch the rest as a spectator\",\"color\":\"gray\"}"])
    for k, why in (("moved", "moved on red light"), ("time", "ran out of time"), ("fell", "fell"), ("found", "was found"), ("nokill", "no kill"),
                   ("cracked", "cracked the shape"), ("marbles", "lost at marbles"), ("final", "fell in the final"), ("died", "died")):
        fn(f"games/out/{k}", [elim_msg(why), f"function {G}/elim"])
    fn("games/died", [   # respawned after dying during a match (Hide and Seek, the Final...)
        f"execute if entity @s[tag=cg.in] run function {G}/out/died",
        f"function {G}/to_view"])
    to_view = []
    for i, key, *_ in ROUNDS:
        vx, vy, vz, yaw, pitch = VIEW[key]
        to_view.append(f"execute if score #round cg matches {i} run tp @s {vx} {vy} {vz} {yaw} {pitch}")
    fn("games/to_view", ["gamemode spectator @s", *to_view])

    # rounds: setup (intro), begin (play), tick, end
    nr = ["scoreboard players add #round cg 1", "execute store result score #alive cg if entity @a[tag=cg.in]",
          f"execute if score #started cg matches 2.. if score #alive cg matches ..1 run return run function {G}/finish",
          f"execute if score #round cg matches 3 if score #alive cg matches ..2 run scoreboard players add #round cg 1",
          f"execute if score #round cg matches 5..6 if score #alive cg matches ..1 run return run function {G}/finish",
          f"execute if score #round cg matches 7.. run return run function {G}/finish",
          "scoreboard players set #phase cg 0", f"scoreboard players set #timer cg {INTRO}",
          "tag @a remove cg.lost", "tag @a remove cg.safe", "kill @e[type=minecraft:item,tag=!keep,x=900,y=-80,z=0,dx=200,dy=200,dz=900]"]
    for i, key, name, color, rule in ROUNDS:
        nr += [f"execute if score #round cg matches {i} run function {G}/{key}/setup",
               f"execute if score #round cg matches {i} run title {ALL} title {tj({'text': name, 'color': color, 'bold': True})}",
               f"execute if score #round cg matches {i} run title {ALL} subtitle {tj({'text': rule, 'color': 'gray'})}",
               f"execute if score #round cg matches {i} run bossbar set pvp:cg name {tj({'text': f'🦑 Round {i}: {name}', 'color': color})}"]
    nr += [f"execute as @a[tag=cg.spec] run function {G}/to_view", f"execute as {ALL} at @s run playsound minecraft:block.note_block.chime master @s ~ ~ ~ 1 0.8"]
    fn("games/next_round", nr)
    begin = ["scoreboard players set #phase cg 1"]
    for i, key, *_ in ROUNDS: begin.append(f"execute if score #round cg matches {i} run function {G}/{key}/begin")
    begin.append(f"execute as {ALL} at @s run playsound minecraft:block.note_block.pling master @s ~ ~ ~ 1 1.5")
    fn("games/begin", begin)
    tick = []
    for i, key, *_ in ROUNDS: tick.append(f"execute if score #round cg matches {i} run function {G}/{key}/tick")
    fn("games/round_tick", tick)
    fn("games/round_end", [   # a round is over: nobody knocked out if it would have been everyone
        "scoreboard players set #phase cg 2", f"scoreboard players set #timer cg {OUTRO}",
        "execute store result score #alive cg if entity @a[tag=cg.in]",
        f"execute if score #alive cg matches 0 run tellraw {ALL} {tj({'text': '🦑 Nobody survived that round, so nobody is out. Everyone from it plays on!', 'color': 'yellow'})}",
        f"execute if score #alive cg matches 0 as @a[tag=cg.lost] run function {G}/revive",
        "execute store result score #alive cg if entity @a[tag=cg.in]",
        f"tellraw {ALL} " + tj([{"text": "🦑 Round over. ", "color": "light_purple"}, {"score": {"name": "#alive", "objective": "cg"}, "color": "white", "bold": True},
                                {"text": " players remain.", "color": "light_purple"}]),
        "effect give @a[tag=cg.in] minecraft:instant_health 1 4 true", "effect clear @a[tag=cg.in] minecraft:glowing",
        f"execute as @a[tag=cg.in] run attribute @s minecraft:block_interaction_range modifier remove {NS}:cg_reach",
        "effect clear @a[tag=cg.in] minecraft:wither", "clear @a[tag=cg.in]", "team join cg @a[tag=cg.in]",
        *[f"execute as @a[tag=cg.in] run {c}" for c in outfit]])
    fn("games/revive", ["tag @s remove cg.lost", "tag @s remove cg.spec", "tag @s add cg.in", "gamemode adventure @s"])
    fn("games/finish", [
        "scoreboard players set #state cg 3", "scoreboard players set #timer cg 160", "bossbar set pvp:cg visible false",
        "execute store result score #alive cg if entity @a[tag=cg.in]",
        f"execute if score #started cg matches 2.. if score #alive cg matches 1 as @a[tag=cg.in] run function {G}/winner",
        f"execute if score #started cg matches ..1 run tellraw {ALL} {tj({'text': '🦑 Practice run over! Play with others to win for real.', 'color': 'light_purple'})}",
        f"execute if score #started cg matches 2.. unless score #alive cg matches 1 run tellraw {ALL} {tj({'text': '🦑 No single winner this time.', 'color': 'gray'})}"])
    fn("games/winner", [
        "scoreboard players add @s cg.wins 1",
        "tellraw @a " + tj([{"text": "🦑 ", "color": "light_purple"}, {"selector": "@s", "color": "gold", "bold": True},
                            {"text": " (player ", "color": "gray"}, {"score": {"name": "@s", "objective": "cg.num"}, "color": "white"}, {"text": ") won Crispy Games!", "color": "light_purple"}]),
        "title @s title {\"text\":\"WINNER\",\"color\":\"gold\",\"bold\":true}", "title @s subtitle {\"text\":\"Last player standing\",\"color\":\"yellow\"}",
        "execute at @s run summon minecraft:firework_rocket ~ ~1 ~ {LifeTime:20,FireworksItem:{id:\"minecraft:firework_rocket\",count:1,components:{\"minecraft:fireworks\":{explosions:[{shape:\"star\",colors:[I;16766720,12801229],has_trail:1b}]}}}}",
        f"execute as {ALL} at @s run playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1"])
    fn("games/close", [   # after the finish: everyone back to the lobby
        f"execute as {ALL} run function {NS}:to_lobby", *forceload_rm,
        "scoreboard players set #state cg 0", "scoreboard players set #round cg 0", "kill @e[tag=cg.ent]"])

    # ================================================================== 1. Red Light, Green Light
    START_Z, FINISH_Z, WATCH_Z = R1_Z + 4, R1_Z + 52, R1_Z + 57
    fn("games/rlgl/setup", [
        "kill @e[tag=cg.watcher]",
        f"summon minecraft:iron_golem {X + 0.5} {FY + 1} {WATCH_Z + 0.5} {{Tags:[\"cg.ent\",\"cg.watcher\"],NoAI:1b,Invulnerable:1b,Silent:1b,PersistenceRequired:1b,"
        f"Rotation:[0f,0f],CustomName:{{\"text\":\"The Watcher\",\"color\":\"red\",\"bold\":true}},CustomNameVisible:1b,attributes:[{{id:\"minecraft:scale\",base:3.5d}}]}}",
        *place("rlgl", [(X + dx + 0.5, FY + 1, R1_Z + 2.5, 0, 0) for dx in range(-13, 14)]),
        f"fill {X - 14} {FY + 1} {START_Z} {X + 14} {FY + 1} {START_Z} minecraft:white_carpet",
        "scoreboard players set #light cg 0"])
    fn("games/rlgl/begin", [f"fill {X - 14} {FY + 1} {START_Z} {X + 14} {FY + 1} {START_Z} minecraft:air", f"scoreboard players set #timer cg {RLGL_T}",
                            f"function {G}/rlgl/green"])
    fn("games/rlgl/green", [
        "scoreboard players set #light cg 1", "execute store result score #lt cg run random value 40..110",
        f"rotate @e[tag=cg.watcher,limit=1] 0 0",
        f"fill {X - 14} {FY + 2} {WATCH_Z + 4} {X + 14} {FY + 3} {WATCH_Z + 4} minecraft:lime_concrete",
        f"title @a[tag=cg.in] actionbar {tj({'text': '🟢 GREEN LIGHT · GO!', 'color': 'green', 'bold': True})}",
        f"execute as {ALL} at @s run playsound minecraft:block.note_block.bell master @s ~ ~ ~ 1 1.4"])
    fn("games/rlgl/red", [
        "scoreboard players set #light cg 2", "execute store result score #lt cg run random value 50..80", "scoreboard players set #grace cg 10",
        f"rotate @e[tag=cg.watcher,limit=1] 180 0",
        f"fill {X - 14} {FY + 2} {WATCH_Z + 4} {X + 14} {FY + 3} {WATCH_Z + 4} minecraft:red_concrete",
        f"title @a[tag=cg.in] actionbar {tj({'text': '🔴 RED LIGHT · FREEZE!', 'color': 'red', 'bold': True})}",
        f"execute as {ALL} at @s run playsound minecraft:block.note_block.bass master @s ~ ~ ~ 1 0.5"])
    mv = ["cg.wk", "cg.sp", "cg.cr", "cg.jp"]
    fn("games/rlgl/tick", [
        "scoreboard players remove #timer cg 1", "scoreboard players remove #lt cg 1",
        f"execute as @a[tag=cg.in,tag=!cg.safe] at @s if entity @s[z={FINISH_Z}.0,dz=40] run function {G}/rlgl/safe",
        f"execute if score #light cg matches 1 if score #lt cg matches ..0 run return run function {G}/rlgl/red",
        f"execute if score #light cg matches 2 if score #lt cg matches ..0 run return run function {G}/rlgl/green",
        "execute if score #light cg matches 2 if score #grace cg matches 1.. run scoreboard players remove #grace cg 1",
        *[f"execute if score #light cg matches 2 if score #grace cg matches 1.. run scoreboard players set @a[tag=cg.in] {o} 0" for o in mv],
        *[f"execute if score #light cg matches 2 if score #grace cg matches 0 as @a[tag=cg.in,tag=!cg.safe,scores={{{o}=1..}}] run function {G}/out/moved" for o in mv],
        f"execute if score #timer cg matches ..0 as @a[tag=cg.in,tag=!cg.safe] run function {G}/out/time",
        f"execute if score #timer cg matches ..0 run return run function {G}/round_end",
        f"execute unless entity @a[tag=cg.in,tag=!cg.safe] run return run function {G}/round_end"])
    fn("games/rlgl/safe", ["tag @s add cg.safe", f"tellraw @s {tj({'text': '🦑 You crossed the line. Safe!', 'color': 'green'})}",
                           "playsound minecraft:entity.player.levelup master @s ~ ~ ~ 1 1.2"])

    # ================================================================== 2. Glass Bridge
    BZ0 = R2_Z + 6                           # first step
    LANES = (X - 4, X + 3)                   # left and right panes' west edge (each 2 wide)
    END_Z = BZ0 + 3 * STEPS
    setup = [f"fill {X - 6} {YB} {BZ0} {X + 6} {YB} {END_Z - 1} minecraft:air", "kill @e[tag=cg.fake]"]
    for k in range(STEPS):
        z = BZ0 + 3 * k
        for lx in LANES:
            setup.append(f"fill {lx} {YB} {z} {lx + 1} {YB} {z + 1} minecraft:glass")
        setup += [f"execute store result score #r cg run random value 0..1",
                  f"execute if score #r cg matches 0 run summon minecraft:marker {LANES[0]} {YB} {z} {{Tags:[\"cg.ent\",\"cg.fake\"]}}",
                  f"execute if score #r cg matches 1 run summon minecraft:marker {LANES[1]} {YB} {z} {{Tags:[\"cg.ent\",\"cg.fake\"]}}"]
    setup += [*place("bridge", [(X + dx + 0.5, YB + 1, R2_Z + 1.5 + dz, 0, 10) for dz in (0, 2) for dx in range(-5, 6)]),
              f"fill {X - 6} {YB + 1} {BZ0 - 1} {X + 6} {YB + 1} {BZ0 - 1} minecraft:white_stained_glass"]
    fn("games/bridge/setup", setup)
    fn("games/bridge/begin", [f"fill {X - 6} {YB + 1} {BZ0 - 1} {X + 6} {YB + 1} {BZ0 - 1} minecraft:air", f"scoreboard players set #timer cg {BRIDGE_T}"])
    fn("games/bridge/break", ["execute at @s run fill ~ ~ ~ ~1 ~ ~1 minecraft:air",
                              "execute at @s run particle minecraft:block{block_state:\"minecraft:glass\"} ~1 ~ ~1 0.6 0.1 0.6 0 40 force",
                              f"execute at @s as {ALL} run playsound minecraft:block.glass.break master @s ~ ~ ~ 1 0.8", "kill @s"])
    fn("games/bridge/tick", [
        "scoreboard players remove #timer cg 1",
        f"execute as @e[type=minecraft:marker,tag=cg.fake] at @s if entity @a[tag=cg.in,dx=1,dy=2,dz=1] run function {G}/bridge/break",
        f"execute as @a[tag=cg.in] at @s if entity @s[y=-100,dy={YB - 3 + 100}] run function {G}/out/fell",
        f"execute as @a[tag=cg.in,tag=!cg.safe] at @s if entity @s[z={END_Z},dz=20,y={YB},dy=6] run function {G}/rlgl/safe",
        f"execute if score #timer cg matches ..0 as @a[tag=cg.in,tag=!cg.safe] run function {G}/out/time",
        f"execute if score #timer cg matches ..0 run return run function {G}/round_end",
        f"execute unless entity @a[tag=cg.in,tag=!cg.safe] run return run function {G}/round_end"])

    # ================================================================== 3. Hide and Seek
    DOOR_X = X + 5                           # the front door, in the middle of a room (inner walls are at X-10, X, X+10)
    CAGE = (DOOR_X - 1, FY + 1, R3_Z - 25)   # seekers wait just outside the front door, in a glass cage
    fn("games/hide/setup", [
        "tag @a remove cg.seek", "team join cg.hide @a[tag=cg.in]",
        "execute store result score #n cg if entity @a[tag=cg.in]", "scoreboard players operation #n cg /= #3 cg",
        "execute if score #n cg matches ..0 run scoreboard players set #n cg 1",
        f"function {G}/hide/pick",
        f"fill {CAGE[0] - 1} {CAGE[1]} {CAGE[2] - 1} {CAGE[0] + 3} {CAGE[1] + 3} {CAGE[2] + 3} minecraft:glass hollow",
        f"execute as @a[tag=cg.seek] run tp @s {CAGE[0] + 1.5} {CAGE[1]} {CAGE[2] + 1.5} 0 0",
        "team join cg.seek @a[tag=cg.seek]",
        "scoreboard players set #pi cg 0", f"execute as @a[tag=cg.in,tag=!cg.seek,sort=random] run function {G}/hide/place",
        "scoreboard players set @a[tag=cg.in] cg.kl 0"])
    place("hide", [(DOOR_X + dx + 0.5, FY + 1, R3_Z - 20 + 2 + dz + 0.5, 0, 0) for dz in range(0, 4) for dx in range(-3, 4)])
    fn("games/hide/pick", ["execute store result storage pvp:games n int 1 run scoreboard players get #n cg", f"function {G}/hide/pick2 with storage pvp:games"])
    fn("games/hide/pick2", ["$tag @a[tag=cg.in,sort=random,limit=$(n)] add cg.seek"])
    fn("games/hide/begin", [
        f"scoreboard players set #timer cg {HIDE_T + HIDE_HEAD}", "scoreboard players set #released cg 0",
        "effect give @a[tag=cg.seek] minecraft:blindness 30 0 true",
        f"tellraw @a[tag=cg.seek] {tj({'text': '🦑 You are a SEEKER. You are released in 30 s. Find a hider and get a kill, or you are out.', 'color': 'red'})}",
        f"tellraw @a[tag=cg.in,tag=!cg.seek] {tj({'text': '🦑 You are a HIDER. Hide in the house! Seekers are released in 30 s.', 'color': 'aqua'})}"])
    fn("games/hide/release", [
        "scoreboard players set #released cg 1",
        f"fill {CAGE[0] - 1} {CAGE[1]} {CAGE[2] - 1} {CAGE[0] + 3} {CAGE[1] + 3} {CAGE[2] + 3} minecraft:air",
        "effect clear @a[tag=cg.seek] minecraft:blindness",
        f"give @a[tag=cg.seek] {b.item('iron_sword', 'Seeker blade', 'red')}",
        f"tellraw {ALL} {tj({'text': '🦑 The seekers are released!', 'color': 'red', 'bold': True})}",
        f"execute as {ALL} at @s run playsound minecraft:entity.wither.spawn master @s ~ ~ ~ 0.4 1.6"])
    fn("games/hide/tick", [
        "scoreboard players remove #timer cg 1",
        f"execute if score #released cg matches 0 if score #timer cg matches ..{HIDE_T} run function {G}/hide/release",
        f"execute if score #timer cg matches 600 run effect give @a[tag=cg.in,tag=!cg.seek] minecraft:glowing 30 0 true",
        f"execute if score #timer cg matches 600 run tellraw {ALL} {tj({'text': '🦑 30 seconds left: the hiders glow!', 'color': 'yellow'})}",
        f"execute if score #released cg matches 1 unless entity @a[tag=cg.in,tag=!cg.seek] run return run function {G}/hide/end",
        f"execute if score #timer cg matches ..0 run return run function {G}/hide/end"])
    fn("games/hide/end", [f"execute as @a[tag=cg.in,tag=cg.seek,scores={{cg.kl=0}}] run function {G}/out/nokill",
                          "tag @a remove cg.seek", f"function {G}/round_end"])

    # ================================================================== 4. Honeycomb
    def booth(i):
        r, c = divmod(i, 16)
        return X - 64 + 8 * c, R4_Z + 20 * r     # wall's west x, wall z
    for name, rows in SHAPES.items():
        cmds = ["fill ~ ~ ~ ~6 ~6 ~ minecraft:orange_terracotta"]
        for ry, row in enumerate(rows):
            for rx, ch in enumerate(row):
                if ch == "X": cmds.append(f"setblock ~{rx} ~{6 - ry} ~ minecraft:yellow_concrete")
        fn(f"games/honey/shape_{name}", cmds)
    pick = ["execute store result score #shape cg run random value 1..4"]
    for n, name in enumerate(SHAPES, 1):
        orange = sum(row.count(".") for row in SHAPES[name])
        pick += [f"execute if score #shape cg matches {n} run scoreboard players set #target cg {orange}",
                 *[f"execute if score #shape cg matches {n} positioned {booth(i)[0]} {FY + 2} {booth(i)[1]} run function {G}/honey/shape_{name}" for i in range(BOOTHS)],
                 f"execute if score #shape cg matches {n} run tellraw {ALL} {tj([{'text': '🦑 Today\'s shape: ', 'color': 'gold'}, {'text': name.upper(), 'color': 'yellow', 'bold': True}])}"]
    assign = ["scoreboard players operation @s cg.b = #i cg", "scoreboard players add #i cg 1"]
    for i in range(BOOTHS):
        bx, bz = booth(i)
        assign.append(f"execute if score @s cg.b matches {i} run tp @s {bx + 3.5} {FY + 1} {bz - 2.5} 0 -20")
    fn("games/honey/assign", assign)
    needle = ('minecraft:iron_pickaxe[minecraft:custom_name={"text":"Needle","color":"gold","italic":false},minecraft:unbreakable={},'
              'minecraft:can_break=[{blocks:["minecraft:orange_terracotta","minecraft:yellow_concrete"]}]]')
    fn("games/honey/setup", [*pick, "scoreboard players set #i cg 0", f"execute as @a[tag=cg.in,sort=random] run function {G}/honey/assign"])
    fn("games/honey/begin", [f"scoreboard players set #timer cg {HONEY_T}", "scoreboard players set @a[tag=cg.in] cg.ho 0", "scoreboard players set @a[tag=cg.in] cg.hy 0",
                             f"give @a[tag=cg.in] {needle}",
                             f"execute as @a[tag=cg.in] run attribute @s minecraft:block_interaction_range modifier add {NS}:cg_reach 3 add_value",
                             f"tellraw @a[tag=cg.in] {tj({'text': '🦑 Mine away all the ORANGE blocks. Break one YELLOW block and you are out!', 'color': 'gold'})}"])
    fn("games/honey/tick", [
        "scoreboard players remove #timer cg 1",
        f"execute as @a[tag=cg.in,scores={{cg.hy=1..}}] run function {G}/out/cracked",
        f"execute as @a[tag=cg.in,tag=!cg.safe] if score @s cg.ho >= #target cg run function {G}/honey/done",
        f"execute if score #timer cg matches ..0 as @a[tag=cg.in,tag=!cg.safe] run function {G}/out/time",
        f"execute if score #timer cg matches ..0 run return run function {G}/round_end",
        f"execute unless entity @a[tag=cg.in,tag=!cg.safe] run return run function {G}/round_end"])
    fn("games/honey/done", ["tag @s add cg.safe", "clear @s minecraft:iron_pickaxe", f"tellraw @s {tj({'text': '🦑 Perfect cut. Safe!', 'color': 'green'})}",
                            "playsound minecraft:entity.player.levelup master @s ~ ~ ~ 1 1.2"])

    # ================================================================== 5. Marbles
    def pair(j): return X - 64 + 8 * j       # booth west x
    PIT_DZ = 10
    ma = ["scoreboard players operation @s cg.b = #i cg", "scoreboard players operation @s cg.b /= #2 cg",
          "scoreboard players operation @s cg.s = #i cg", "scoreboard players operation @s cg.s %= #2 cg", "scoreboard players add #i cg 1"]
    for j in range(PAIRS):
        bx = pair(j)
        ma += [f"execute if score @s cg.b matches {j} if score @s cg.s matches 0 run tp @s {bx + 2.5} {FY + 1} {R5_Z + 0.5} 0 15",
               f"execute if score @s cg.b matches {j} if score @s cg.s matches 1 run tp @s {bx + 5.5} {FY + 1} {R5_Z + 0.5} 0 15"]
    fn("games/marbles/assign", ma)
    marble = 'minecraft:snowball[minecraft:custom_name={"text":"Marble","color":"aqua","italic":false}]'
    fn("games/marbles/setup", ["scoreboard players set #i cg 0", f"execute as @a[tag=cg.in,sort=random] run function {G}/marbles/assign",
                               "scoreboard players set @a[tag=cg.in] cg.mb 0"])
    fn("games/marbles/begin", [f"scoreboard players set #timer cg {MARBLE_T}", f"give @a[tag=cg.in] {marble} 10",
                               f"tellraw @a[tag=cg.in] {tj({'text': '🦑 Throw your 10 marbles into the pit. Beat your partner!', 'color': 'light_purple'})}"])
    score = []
    for j in range(PAIRS):
        bx = pair(j)
        sel = f"type=minecraft:snowball,x={bx + 3},y={FY - 0.2},z={R5_Z + PIT_DZ},dx=1.99,dy=1.4,dz=1.99"
        score += [f"execute as @e[{sel}] on origin run scoreboard players add @s cg.mb 1",
                  f"execute as @e[{sel}] at @s run particle minecraft:happy_villager ~ ~ ~ 0.3 0.3 0.3 0 8",
                  f"kill @e[{sel}]"]
    fn("games/marbles/tick", [
        "scoreboard players remove #timer cg 1", *score,
        "execute as @a[tag=cg.in] run title @s actionbar [{\"text\":\"Marbles in: \",\"color\":\"aqua\"},{\"score\":{\"name\":\"@s\",\"objective\":\"cg.mb\"},\"color\":\"white\"}]",
        f"execute if score #timer cg matches ..1100 unless entity @e[type=minecraft:snowball,x={X - 66},y={FY - 2},z={R5_Z - 3},dx=132,dy=12,dz=18] "
        f"unless items entity @a[tag=cg.in] container.* minecraft:snowball unless items entity @a[tag=cg.in] weapon.offhand minecraft:snowball run return run function {G}/marbles/resolve",
        f"execute if score #timer cg matches ..0 run function {G}/marbles/resolve"])
    res = []
    for j in range(PAIRS):
        res.append(f"function {G}/marbles/pair {{j:{j}}}")
    fn("games/marbles/resolve", [f"kill @e[type=minecraft:snowball,x={X - 66},y={FY - 2},z={R5_Z - 3},dx=132,dy=12,dz=18]", "clear @a[tag=cg.in] minecraft:snowball", *res, f"function {G}/round_end"])
    fn("games/marbles/pair", [
        "scoreboard players set #a cg -1", "scoreboard players set #b cg -1",
        "$execute as @a[tag=cg.in,scores={cg.b=$(j),cg.s=0}] run scoreboard players operation #a cg = @s cg.mb",
        "$execute as @a[tag=cg.in,scores={cg.b=$(j),cg.s=1}] run scoreboard players operation #b cg = @s cg.mb",
        "execute if score #a cg matches -1 run return 0", "execute if score #b cg matches -1 run return 0",
        "scoreboard players set #tie cg 0", "execute if score #a cg = #b cg run scoreboard players set #tie cg 1",
        "execute if score #tie cg matches 1 store result score #a cg run random value 0..1",      # a tie: a coin flip (b = 1 - a)
        "execute if score #tie cg matches 1 run scoreboard players set #b cg 1",
        "execute if score #tie cg matches 1 run scoreboard players operation #b cg -= #a cg",
        "$execute if score #a cg > #b cg as @a[tag=cg.in,scores={cg.b=$(j),cg.s=1}] run function " + G + "/out/marbles",
        "$execute if score #b cg > #a cg as @a[tag=cg.in,scores={cg.b=$(j),cg.s=0}] run function " + G + "/out/marbles"])

    # ================================================================== 6. The Final
    final_kit = [f"give @s {b.item('iron_sword', 'Final blade', 'dark_red')}", "give @s minecraft:bow", "give @s minecraft:arrow 16",
                 "give @s minecraft:golden_apple 1", "item replace entity @s armor.chest with minecraft:chainmail_chestplate[minecraft:unbreakable={}]",
                 "item replace entity @s armor.head with minecraft:chainmail_helmet[minecraft:unbreakable={}]"]
    fn("games/final/kit", final_kit)
    ring = []
    for n in range(16):
        ang = 2 * math.pi * n / 16
        px, pz = X + 0.5 + round(12 * math.cos(ang)), R6_Z + 0.5 + round(12 * math.sin(ang))
        yaw = round(math.degrees(math.atan2(-(X + 0.5 - px), R6_Z + 0.5 - pz)), 1)
        ring.append((px, FY + 1, pz, yaw, 0))
    fn("games/final/setup", [*place("final", ring),
                             "effect give @a[tag=cg.in] minecraft:slowness 5 10 true"])
    fn("games/final/begin", [f"scoreboard players set #timer cg {FINAL_T + FINAL_SD}", "team leave @a[tag=cg.in]",
                             f"execute as @a[tag=cg.in] run function {G}/final/kit",
                             f"tellraw @a[tag=cg.in] {tj({'text': '🦑 FIGHT! Last player standing wins.', 'color': 'dark_red', 'bold': True})}"])
    fn("games/final/tick", [
        "scoreboard players remove #timer cg 1",
        f"execute if score #timer cg matches {FINAL_SD} run tellraw {ALL} {tj({'text': '🦑 SUDDEN DEATH: everyone withers!', 'color': 'dark_red', 'bold': True})}",
        f"execute if score #timer cg matches ..{FINAL_SD} run effect give @a[tag=cg.in] minecraft:wither 3 1 true",
        f"execute as @a[tag=cg.in] at @s unless entity @s[x={X - 16},y={FY - 2},z={R6_Z - 16},dx=32,dy=20,dz=32] run tp @s {X + 0.5} {FY + 1} {R6_Z + 0.5}",
        "execute store result score #alive cg if entity @a[tag=cg.in]",
        f"execute if score #alive cg matches ..1 run return run function {G}/round_end"])

    # ------------------------------------------------------------------ ticking
    fn("games/tick", [
        "scoreboard players enable @a cg.join", f"execute as @a[scores={{cg.join=1..}}] at @s run function {G}/join",
        f"execute if score #state cg matches 1 run function {G}/countdown_tick",
        f"execute if score #state cg matches 2 run function {G}/match_tick",
        "execute if score #state cg matches 3 run scoreboard players remove #timer cg 1",
        f"execute if score #state cg matches 3 if score #timer cg matches ..0 run function {G}/close"])
    fn("games/match_tick", [
        f"execute if score #phase cg matches 0 run scoreboard players remove #timer cg 1",
        f"execute if score #phase cg matches 0 if score #timer cg matches ..0 run return run function {G}/begin",
        f"execute if score #phase cg matches 1 run function {G}/round_tick",
        f"execute if score #phase cg matches 2 run scoreboard players remove #timer cg 1",
        f"execute if score #phase cg matches 2 if score #timer cg matches ..0 run function {G}/next_round"])
    fn("games/second", [
        # nobody online in the match any more: end it
        f"execute if score #state cg matches 2 unless entity {ALL} run function {G}/close",
        # back in after a match ended (left mid-game): to the lobby
        f"execute unless score #state cg matches 2..3 as {ALL} run function {NS}:to_lobby",
        "execute if score #state cg matches 2 run bossbar set pvp:cg players @a[tag=cg.all]",
        "execute if score #state cg matches 2 run bossbar set pvp:cg visible true",
        "execute if score #state cg matches 2 if score #phase cg matches 1 store result bossbar pvp:cg value run scoreboard players get #timer cg",
        f"execute if score #state cg matches 2 if score #phase cg matches 1 run function {G}/maxbar"])
    mx = []
    for i, key, *_ in ROUNDS:
        t = {"rlgl": RLGL_T, "bridge": BRIDGE_T, "hide": HIDE_T + HIDE_HEAD, "honey": HONEY_T, "marbles": MARBLE_T, "final": FINAL_T + FINAL_SD}[key]
        mx.append(f"execute if score #round cg matches {i} run bossbar set pvp:cg max {t}")
    fn("games/maxbar", mx)

    # ------------------------------------------------------------------ the arenas (function pvp:admin/build_games)
    a = list(forceload_add)
    # 1. a sandy field inside painted sky walls, a big tree behind the Watcher, the finish line
    x1, z1, x2, z2 = X - 16, R1_Z - 2, X + 16, R1_Z + 66
    a += [f"fill {x1} {FY + 1} {z1} {x2} {FY + 12} {z2} minecraft:air",
          f"fill {x1} {FY} {z1} {x2} {FY} {z2} minecraft:sand",
          f"fill {x1} {FY + 1} {z1} {x1} {FY + 10} {z2} minecraft:light_blue_concrete", f"fill {x2} {FY + 1} {z1} {x2} {FY + 10} {z2} minecraft:light_blue_concrete",
          f"fill {x1} {FY + 1} {z1} {x2} {FY + 10} {z1} minecraft:light_blue_concrete", f"fill {x1} {FY + 1} {z2} {x2} {FY + 10} {z2} minecraft:light_blue_concrete",
          f"fill {x1} {FY + 1} {z1} {x2} {FY + 2} {z1} minecraft:sandstone", f"fill {x1} {FY + 1} {z2} {x2} {FY + 2} {z2} minecraft:sandstone",
          f"fill {x1} {FY + 1} {z1} {x1} {FY + 2} {z2} minecraft:sandstone", f"fill {x2} {FY + 1} {z1} {x2} {FY + 2} {z2} minecraft:sandstone",
          f"fill {X - 14} {FY} {FINISH_Z} {X + 14} {FY} {FINISH_Z} minecraft:red_concrete",
          f"fill {X - 14} {FY} {START_Z} {X + 14} {FY} {START_Z} minecraft:white_concrete"]
    import random as _r
    rnd = _r.Random(11)
    for _ in range(26):                      # clouds on the walls
        side = rnd.choice(("w", "e", "n", "s")); h = rnd.randint(5, 8)
        if side in "we":
            wx = x1 if side == "w" else x2; zc = rnd.randint(z1 + 3, z2 - 6)
            a.append(f"fill {wx} {FY + h} {zc} {wx} {FY + h + 1} {zc + rnd.randint(2, 4)} minecraft:white_concrete")
        else:
            wz = z1 if side == "n" else z2; xc = rnd.randint(x1 + 2, x2 - 5)
            a.append(f"fill {xc} {FY + h} {wz} {xc + rnd.randint(2, 4)} {FY + h + 1} {wz} minecraft:white_concrete")
    tz = WATCH_Z + 4                         # the tree behind the Watcher (and the light strip on the wall)
    a += [f"fill {X + 7} {FY + 1} {tz} {X + 7} {FY + 7} {tz} minecraft:oak_log",
          f"fill {X + 4} {FY + 6} {tz - 3} {X + 10} {FY + 9} {tz} minecraft:oak_leaves[persistent=true]"]
    # 2. the bridge: start and end platforms high over a dark pit
    bx1, bz1, bx2, bz2 = X - 7, R2_Z - 2, X + 7, END_Z + 6
    a += [f"fill {bx1} {FY + 1} {bz1} {bx2} {YB + 8} {bz2} minecraft:air",
          f"fill {bx1} {FY} {bz1} {bx2} {FY} {bz2} minecraft:black_concrete",
          f"fill {X - 6} {YB} {R2_Z - 1} {X + 6} {YB} {BZ0 - 1} minecraft:smooth_quartz",
          f"fill {X - 6} {YB} {END_Z} {X + 6} {YB} {END_Z + 5} minecraft:smooth_quartz",
          *[f"fill {xx} {YB + 1} {R2_Z - 1} {xx} {YB + 3} {R2_Z - 1} minecraft:white_concrete" for xx in (X - 6, X + 6)],
          f"fill {X - 6} {YB + 1} {END_Z + 5} {X + 6} {YB + 2} {END_Z + 5} minecraft:white_concrete",
          f"setblock {X} {YB + 3} {END_Z + 5} minecraft:sea_lantern", f"setblock {X} {YB + 3} {R2_Z - 1} minecraft:sea_lantern"]
    # 3. the house: a 41x41 block of rooms with doorways and furniture, a roof with skylights
    hx1, hz1 = X - 20, R3_Z - 20
    a += [f"fill {hx1 - 1} {FY + 1} {hz1 - 1} {hx1 + 41} {FY + 6} {hz1 + 41} minecraft:air",
          f"fill {hx1} {FY} {hz1} {hx1 + 40} {FY} {hz1 + 40} minecraft:oak_planks",
          f"fill {hx1} {FY + 1} {hz1} {hx1 + 40} {FY + 4} {hz1 + 40} minecraft:stripped_spruce_wood hollow",
          f"fill {hx1} {FY + 5} {hz1} {hx1 + 40} {FY + 5} {hz1 + 40} minecraft:spruce_planks"]
    for gx in range(1, 4):                   # inner walls every 10 blocks, doorways in each
        wx = hx1 + 10 * gx
        a.append(f"fill {wx} {FY + 1} {hz1 + 1} {wx} {FY + 4} {hz1 + 39} minecraft:white_terracotta")
        wz = hz1 + 10 * gx
        a.append(f"fill {hx1 + 1} {FY + 1} {wz} {hx1 + 39} {FY + 4} {wz} minecraft:white_terracotta")
    for gx in range(4):
        for gz in range(4):
            cx, cz = hx1 + 10 * gx + 5, hz1 + 10 * gz + 5
            if gx < 3: a.append(f"fill {hx1 + 10 * (gx + 1)} {FY + 1} {cz - 1 + rnd.randint(-2, 2)} {hx1 + 10 * (gx + 1)} {FY + 2} {cz + rnd.randint(-2, 2) + 1} minecraft:air")
            if gz < 3: a.append(f"fill {cx - 1 + rnd.randint(-2, 2)} {FY + 1} {hz1 + 10 * (gz + 1)} {cx + rnd.randint(-2, 2) + 1} {FY + 2} {hz1 + 10 * (gz + 1)} minecraft:air")
            a.append(f"setblock {cx} {FY + 5} {cz} minecraft:glowstone")
            for _ in range(5):            # furniture to hide behind
                fx, fz = cx + rnd.randint(-3, 3), cz + rnd.randint(-3, 3)
                blk = rnd.choice(["bookshelf", "bookshelf", "barrel", "crafting_table", "chiseled_bookshelf", "hay_block", "oak_planks"])
                hh = rnd.randint(1, 3) if blk in ("bookshelf", "oak_planks", "hay_block") else 1
                a.append(f"fill {fx} {FY + 1} {fz} {fx} {FY + hh} {fz} minecraft:{blk}")
    a += [f"fill {DOOR_X - 1} {FY + 1} {hz1} {DOOR_X + 1} {FY + 3} {hz1} minecraft:air",                  # the front door
          f"fill {DOOR_X - 3} {FY} {CAGE[2] - 2} {DOOR_X + 3} {FY} {hz1 - 1} minecraft:stone_bricks",
          f"fill {DOOR_X - 4} {FY + 1} {hz1 + 1} {DOOR_X + 4} {FY + 3} {hz1 + 6} minecraft:air"]            # keep the entry room clear
    # 4. the honeycomb booths: a glass cell per player facing their wall
    a += [f"fill {X - 66} {FY + 1} {R4_Z - 8} {X} {FY + 11} {R4_Z + 22} minecraft:air",          # in two halves: a fill tops out at 32768 blocks
          f"fill {X + 1} {FY + 1} {R4_Z - 8} {X + 66} {FY + 11} {R4_Z + 22} minecraft:air"]
    a.append(f"fill {X - 66} {FY} {R4_Z - 8} {X + 66} {FY} {R4_Z + 22} minecraft:smooth_stone")
    for i in range(BOOTHS):
        bx, bz = booth(i)
        a += [f"fill {bx - 1} {FY + 1} {bz - 6} {bx + 7} {FY + 10} {bz + 1} minecraft:glass hollow",
              f"fill {bx} {FY + 1} {bz - 5} {bx + 6} {FY + 9} {bz - 1} minecraft:air",
              f"fill {bx} {FY + 1} {bz + 1} {bx + 6} {FY + 9} {bz + 1} minecraft:white_concrete",
              f"fill {bx} {FY + 2} {bz} {bx + 6} {FY + 8} {bz} minecraft:orange_terracotta",
              f"setblock {bx + 3} {FY + 10} {bz - 3} minecraft:sea_lantern"]
    # 5. marble booths: a sand lane to a 2x2 pit, each pair in its own glass alley
    a.append(f"fill {X - 66} {FY + 1} {R5_Z - 3} {X + 66} {FY + 8} {R5_Z + 14} minecraft:air")
    for j in range(PAIRS):
        bx = pair(j)
        a += [f"fill {bx - 1} {FY} {R5_Z - 2} {bx + 8} {FY + 7} {R5_Z + 13} minecraft:glass hollow",
              f"fill {bx} {FY + 1} {R5_Z - 1} {bx + 7} {FY + 6} {R5_Z + 12} minecraft:air",
              f"fill {bx} {FY} {R5_Z - 1} {bx + 7} {FY} {R5_Z + 12} minecraft:sand",
              f"fill {bx} {FY} {R5_Z - 1} {bx + 7} {FY} {R5_Z + 1} minecraft:smooth_stone",
              f"fill {bx + 3} {FY} {R5_Z + PIT_DZ} {bx + 4} {FY} {R5_Z + PIT_DZ + 1} minecraft:air",
              f"fill {bx + 3} {FY - 1} {R5_Z + PIT_DZ} {bx + 4} {FY - 1} {R5_Z + PIT_DZ + 1} minecraft:gold_block",
              f"setblock {bx + 3} {FY + 7} {R5_Z + 5} minecraft:sea_lantern"]
    # 6. the final: a walled stone arena with pillars
    fx1, fz1 = X - 16, R6_Z - 16
    a += [f"fill {fx1} {FY + 1} {fz1} {fx1 + 32} {FY + 14} {fz1 + 32} minecraft:air",
          f"fill {fx1} {FY} {fz1} {fx1 + 32} {FY} {fz1 + 32} minecraft:polished_andesite",
          f"fill {fx1} {FY + 1} {fz1} {fx1 + 32} {FY + 6} {fz1 + 32} minecraft:stone_bricks hollow",
          f"fill {fx1 + 1} {FY + 6} {fz1 + 1} {fx1 + 31} {FY + 6} {fz1 + 31} minecraft:air"]
    for px, pz in ((-8, -8), (8, -8), (-8, 8), (8, 8), (0, 0)):
        a += [f"fill {X + px} {FY + 1} {R6_Z + pz} {X + px + 1} {FY + 4} {R6_Z + pz + 1} minecraft:chiseled_stone_bricks",
              f"setblock {X + px} {FY + 5} {R6_Z + pz} minecraft:sea_lantern"]
    a += forceload_rm
    fn("admin/build_games", a)

    x, _, z = NPC_POS
    lore = ["Last player standing wins", "", *[f"{i}. {name}" for i, _, name, _, _ in ROUNDS], "",
            "Same tracksuit for everyone · no kits", "Eliminated players watch the rest"]
    return {
        "objectives": ["cg dummy", "cg.join trigger", "cg.num dummy", "cg.p dummy", "cg.wins dummy", "cg.b dummy", "cg.s dummy", "cg.mb dummy",
                       "cg.kl playerKillCount", "cg.wk minecraft.custom:minecraft.walk_one_cm", "cg.sp minecraft.custom:minecraft.sprint_one_cm",
                       "cg.cr minecraft.custom:minecraft.crouch_one_cm", "cg.jp minecraft.custom:minecraft.jump",
                       "cg.ho minecraft.mined:minecraft.orange_terracotta", "cg.hy minecraft.mined:minecraft.yellow_concrete"],
        "load": ["scoreboard players set #2 cg 2", "scoreboard players set #3 cg 3", "scoreboard players set #20 cg 20",
                 "execute unless score #state cg matches 0.. run scoreboard players set #state cg 0",
                 "team add cg", "team modify cg color green", "team modify cg friendlyFire false", "team modify cg collisionRule never",
                 "team add cg.seek", "team modify cg.seek color red", "team modify cg.seek friendlyFire false",
                 "team add cg.hide", "team modify cg.hide color aqua", "team modify cg.hide friendlyFire false",
                 'bossbar add pvp:cg {"text":"Crispy Games","color":"light_purple"}', "bossbar set pvp:cg color pink", "bossbar set pvp:cg visible false"],
        "reset": ["tag @s remove cg.q", "tag @s remove cg.all", "tag @s remove cg.in", "tag @s remove cg.spec", "tag @s remove cg.lost",
                  "tag @s remove cg.safe", "tag @s remove cg.seek", f"attribute @s minecraft:block_interaction_range modifier remove {NS}:cg_reach"],
        "died": f"execute if entity @s[tag=cg.all] run return run function {G}/died",
        "keep": "unless entity @s[tag=cg.all]",
        "npc": (x, b.LOBBY_Y + 1, z),
        "menu": {"title": {"text": "🦑 Crispy Games", "color": "dark_purple"}, "rows": 3, "fill": b.PANE, "items": [
            {"slot": 4, "item": b.icon("nautilus_shell", "Crispy Games", "light_purple", lore), "cmd": ""},
            {"slot": 13, "item": b.icon("lime_dye", "Join the next match", "green", ["Six rounds, one winner", "Starts 30 s after the first player joins", "", "Click to join"]), "cmd": "trigger cg.join set 1"},
            {"slot": 22, "item": b.icon("barrier", "Leave the queue", "red", ["Stop waiting for Crispy Games"], False), "cmd": "trigger cg.join set 2"}]},
    }
