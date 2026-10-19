#!/usr/bin/env python3
"""crispy_newspawn datapack for Vanilla01: brand-new players get a random, safe spawn.

    python3 vanilla/newspawn/build.py [out.zip]

The world spawn (16 64 -48) has a player-built cobblestone block floating at y 217 inside the spawn radius, so
new players were landing ~120 blocks up. Now, on a player's first appearance, anyone who has played before
(UUIDs in known_players.txt, taken from world/players/stats when this was built) is just tagged; a new player
standing near world spawn is moved with spreadplayers (never onto water, lava or fire), gets a few seconds of
resistance + slow falling, and gets that spot as their respawn point. Install as world/datapacks/crispy_newspawn.zip.
"""
import json, os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "crispy_newspawn.zip")
KNOWN = [l.strip() for l in open(os.path.join(HERE, "known_players.txt")) if l.strip()]
NS = "crispy_ns"
SPAWN_X, SPAWN_Z, NEAR = 16, -48, 48       # world spawn and how close a new player must be to count as "at spawn"
RANGE, UNDER = 1500, 200                   # spreadplayers max range around spawn, highest floor it may pick

files = {
    "pack.mcmeta": json.dumps({"pack": {"pack_format": 94, "supported_formats": [48, 200], "min_format": [48, 0], "max_format": [200, 0],
                                        "description": "CrispyAnarchy Vanilla: random safe spawn for new players"}}),
    "data/minecraft/tags/function/load.json": json.dumps({"values": [f"{NS}:load"]}),
    f"data/{NS}/function/load.mcfunction": f"schedule function {NS}:tick 10t replace\n",
    f"data/{NS}/function/tick.mcfunction":
        f"execute if entity @a[tag=!ns.seen] run function {NS}:check\n"
        f"schedule function {NS}:tick 10t replace\n",
    # tag everyone who has played before (a UUID only matches if that player is online)
    f"data/{NS}/function/check.mcfunction":
        "".join(f"tag {u} add ns.seen\n" for u in KNOWN)
        + f"execute as @a[tag=!ns.seen,x={SPAWN_X - NEAR},y=-64,z={SPAWN_Z - NEAR},dx={2 * NEAR},dy=400,dz={2 * NEAR}] run function {NS}:new\n"
        + "tag @a[tag=!ns.seen] add ns.seen\n",
    f"data/{NS}/function/new.mcfunction": "\n".join([
        "tag @s add ns.seen",
        "effect give @s minecraft:slow_falling 10 0 true",
        "effect give @s minecraft:resistance 10 4 true",
        f"execute store success score @s ns.ok run spreadplayers {SPAWN_X} {SPAWN_Z} 0 {RANGE} under {UNDER} false @s",
        f"execute if score @s ns.ok matches 1 at @s run spawnpoint @s ~ ~ ~",
        'execute if score @s ns.ok matches 1 run tellraw @s [{"text":"Welcome to CrispyAnarchy Vanilla! ","color":"green","bold":true},'
        '{"text":"You\'ve been dropped somewhere safe in the wild - this is your respawn point until you sleep in a bed.","color":"gray","bold":false}]',
    ]) + "\n",
}
files[f"data/{NS}/function/load.mcfunction"] = "scoreboard objectives add ns.ok dummy\n" + files[f"data/{NS}/function/load.mcfunction"]
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for name, body in files.items(): z.writestr(name, body)
print(f"wrote {OUT}: {len(KNOWN)} known players")
