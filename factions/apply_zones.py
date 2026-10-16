"""Run ONLY while Factions01 is stopped: writes safezone/warzone chunks into SaberFactions board.json and
blocks creeper/fireball damage in the warzone. Safezone = chunks -3..2 (x/z -48..47), warzone = chunks -12..11 minus safezone."""
import json, shutil, time, os
F = "/AMPStorage/.ampdata/instances/Factions01/Minecraft/plugins/Factions/"
ts = time.strftime("%Y%m%d%H%M%S")
b = json.load(open(F + "board.json")); shutil.copy(F + "board.json", F + f"board.json.bak-{ts}")
w = b.setdefault("world", {})
for cx in range(-12, 12):
    for cz in range(-12, 12):
        k = f"{cx},{cz}"
        if w.get(k, "0") not in ("0", "-1", "-2"): continue   # never touch a player faction's land
        w[k] = "-1" if -3 <= cx <= 2 and -3 <= cz <= 2 else "-2"
json.dump(b, open(F + "board.json", "w"))
c = json.load(open(F + "conf.json")); shutil.copy(F + "conf.json", F + f"conf.json.bak-{ts}")
c["warZoneBlockCreepers"] = True; c["warZoneBlockFireballs"] = True
json.dump(c, open(F + "conf.json", "w"), indent=2)
os.system(f"chown amp:amp {F}board.json {F}conf.json")
print("safezone", sum(v == "-1" for v in w.values()), "warzone", sum(v == "-2" for v in w.values()))
