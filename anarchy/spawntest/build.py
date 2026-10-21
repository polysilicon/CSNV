#!/usr/bin/env python3
"""crispy_rstest: tests Anarchy's random_spawn placement without a real new player.

    python3 anarchy/spawntest/build.py [out.zip]     then on the server:
    datapack enable "file/crispy_rstest.zip" ; function crispy_rstest:run ; data get storage crispy:rst r

Each trial spreads a marker exactly like random_spawn:place (spreadplayers 0 0 0 1000 in the overworld) and checks the
landing spot in the same tick (the chunk is loaded then): position, block underfoot, headroom, lava/fire close by.
It also removes test armour stands tagged "rst" whenever their chunk loads (left over from an earlier test).
"""
import json, os, sys, zipfile
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "crispy_rstest.zip")
NS, TRIALS = "crispy_rstest", 12
BELOW = [("lava", "minecraft:lava"), ("water", "minecraft:water"), ("fire", "#minecraft:fire"), ("magma", "minecraft:magma_block"),
         ("cactus", "minecraft:cactus"), ("powder_snow", "minecraft:powder_snow"), ("leaves", "#minecraft:leaves"),
         ("air", "minecraft:air"), ("bedrock", "minecraft:bedrock")]
probe = ['data modify storage crispy:rst r append value {below:"solid",head:"clear",hazard:"none"}',
         *[f"execute store result storage crispy:rst r[-1].{a} int 1 run data get entity @s Pos[{i}]" for i, a in enumerate("xyz")]]
probe += [f'execute if block ~ ~-1 ~ {b} run data modify storage crispy:rst r[-1].below set value "{n}"' for n, b in BELOW]
probe += ['execute unless block ~ ~ ~ #minecraft:air run data modify storage crispy:rst r[-1].head set value "blocked"',
          'execute unless block ~ ~1 ~ #minecraft:air run data modify storage crispy:rst r[-1].head set value "blocked"']
for dx in (-2, -1, 0, 1, 2):
    for dz in (-2, -1, 0, 1, 2):
        for dy in (-1, 0):
            probe.append(f'execute if block ~{dx} ~{dy} ~{dz} #crispy_rstest:hot run data modify storage crispy:rst r[-1].hazard set value "lava/fire within 2"')
files = {
    "pack.mcmeta": json.dumps({"pack": {"pack_format": 94, "supported_formats": [48, 200], "min_format": [48, 0], "max_format": [200, 0], "description": "random_spawn test"}}),
    f"data/{NS}/tags/block/hot.json": json.dumps({"values": ["minecraft:lava", "minecraft:fire", "minecraft:soul_fire", "minecraft:magma_block"]}),
    "data/minecraft/tags/function/load.json": json.dumps({"values": [f"{NS}:load"]}),
    f"data/{NS}/function/load.mcfunction": f"schedule function {NS}:cleanup 100t replace\n",
    f"data/{NS}/function/cleanup.mcfunction": f"kill @e[type=minecraft:armor_stand,tag=rst]\nkill @e[type=minecraft:marker,tag=rst_m]\nschedule function {NS}:cleanup 100t replace\n",
    f"data/{NS}/function/run.mcfunction": "data modify storage crispy:rst r set value []\n" + f"function {NS}:one\n" * TRIALS,
    f"data/{NS}/function/one.mcfunction": "execute in minecraft:overworld run summon minecraft:marker 287 70 -207 {Tags:[\"rst_m\"]}\n"
                                          f"execute as @e[type=minecraft:marker,tag=rst_m,limit=1] run function {NS}:spread\n",
    f"data/{NS}/function/spread.mcfunction": "execute in minecraft:overworld run spreadplayers 0 0 0 1000 false @s\n"
                                             f"execute at @s run function {NS}:probe\nkill @s\n",
    f"data/{NS}/function/probe.mcfunction": "\n".join(probe) + "\n",
}
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for k, v in files.items(): z.writestr(k, v)
print("wrote", OUT)
