#!/bin/bash
# Writes the Lost Cities profile "extraction" (the zone's city) on the AMP host, from the stock "onlycities" profile.
# Run as root on the host. Only affects chunks generated after it: wipe world/dimensions/lostcities to regenerate.
M=/AMPStorage/.ampdata/instances/Extraction01/Minecraft
set -e
python3 -I - "$M" <<'PY'
import json, sys
M = sys.argv[1]; P = M + "/config/lostcities/profiles/"
d = json.load(open(P + "onlycities.json"))
def strip(o):
    if isinstance(o, dict): return {k: strip(v) for k, v in o.items() if k != "__readonly__"}
    return o
d = strip(d)
d["description"] = "Crispy Extraction Zone: a war-torn but walkable city, open doorways, no railways"
lc = d["lostcity"]
lc.update({
    "buildingChance": 0.35,            # fewer buildings: more streets and gaps between blocks of buildings
    "buildingDoorwayChance": 1.0,      # every building gets doorways onto the street
    "rubbleLayer": False,              # no rubble piles in streets and doorways
    "ruinChance": 0.08, "ruinMinlevelPercent": 0.8,
    "corridorChance": 0.0,             # no sealed underground corridors
    "parkChance": 0.3,
    "buildingMaxFloors": 6, "buildingMaxFloorsChance": 4, "buildingMaxCellars": 1,
    "railwaysEnabled": False, "railwayStationsEnabled": False, "railwaySurfaceStationsEnabled": False,
    "chestWithoutLootChance": 0.0, "vineChance": 0.02, "randomLeafBlockChance": 0.2})
d["explosions"].update({"explosionChance": 0.001, "miniExplosionChance": 0.02})   # a few blast sites, not debris everywhere
json.dump(d, open(P + "extraction.json", "w"), indent=1)
print("profile written:", {k: lc[k] for k in ("buildingChance", "buildingDoorwayChance", "rubbleLayer", "ruinChance", "corridorChance")})
PY
sed -i 's#dimensionsWithProfiles = \[.*\]#dimensionsWithProfiles = ["lostcities:lostcity=extraction"]#' $M/config/lostcities/common.toml
chown -R amp:amp $M/config/lostcities
