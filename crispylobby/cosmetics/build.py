#!/usr/bin/env python3
"""crispy_cosmetics datapack: draws the vote-cosmetic walking trails on a backend server.

    python3 crispylobby/cosmetics/build.py [out.zip]

Reads the trails from crispylobby/res/config.yml (cosmetics.trails). CrispyLobby sets each player's crispy.trail
score over RCON; every 2 ticks anyone with a trail who walked or sprinted (and isn't a spectator or invisible) gets
the particle at their feet. Commands run from a scheduled function, so nothing is echoed to ops or the log.
Install as world/datapacks/crispy_cosmetics.zip on each backend (Paper and Fabric); it loads on the next restart.
"""
import json, os, sys, zipfile
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "crispy_cosmetics.zip")
trails = yaml.safe_load(open(os.path.join(HERE, "..", "res", "config.yml")))["cosmetics"]["trails"]
NS = "crispy_cos"
INVIS = '{condition:"minecraft:entity_properties",entity:"this",predicate:{effects:{"minecraft:invisibility":{}}}}'

files = {
    "pack.mcmeta": json.dumps({"pack": {"pack_format": 94, "supported_formats": [48, 200], "min_format": [48, 0], "max_format": [200, 0],
                                        "description": "CrispyAnarchy vote cosmetics: walking trails"}}),
    f"data/minecraft/tags/function/load.json": json.dumps({"values": [f"{NS}:load"]}),
    f"data/{NS}/function/load.mcfunction": "\n".join([
        "scoreboard objectives add crispy.trail dummy",
        "scoreboard objectives add crispy.walk minecraft.custom:minecraft.walk_one_cm",
        "scoreboard objectives add crispy.sprint minecraft.custom:minecraft.sprint_one_cm",
        f"schedule function {NS}:tick 2t replace"]) + "\n",
    f"data/{NS}/function/tick.mcfunction": "\n".join([
        "execute as @a run scoreboard players operation @s crispy.walk += @s crispy.sprint",
        f"execute as @a[scores={{crispy.trail=1..,crispy.walk=1..}},gamemode=!spectator] at @s unless predicate {INVIS} run function {NS}:trail",
        "scoreboard players reset @a crispy.walk",
        "scoreboard players reset @a crispy.sprint",
        f"schedule function {NS}:tick 2t replace"]) + "\n",
    f"data/{NS}/function/trail.mcfunction": "".join(
        f"execute if score @s crispy.trail matches {t['score']} run particle minecraft:{t['particle']} ~ ~0.2 ~ {t.get('args', '0.2 0.1 0.2 0 1')}\n"
        for t in trails.values()),
}
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for name, body in files.items(): z.writestr(name, body)
print(f"wrote {OUT}: {len(trails)} trails")
