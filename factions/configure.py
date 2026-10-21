"""Apply the Working Man's 2013 Factions configuration to Factions01 (run while the server is stopped)."""
import json, os, re, secrets, shutil, yaml

M = "/AMPStorage/.ampdata/instances/Factions01/Minecraft"
P = M + "/plugins"
def ry(p): return yaml.safe_load(open(p))
def wy(p, d): open(p, "w").write(yaml.safe_dump(d, sort_keys=False, allow_unicode=True, width=1000))
def backup(p):
    # EconomyShopGUI loads every file in shops/ and sections/, so its backups go to shop-backups/ instead
    dst = p + ".orig"
    if "/EconomyShopGUI/shops/" in p or "/EconomyShopGUI/sections/" in p:
        d = os.path.join(P, "EconomyShopGUI", "shop-backups"); os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, os.path.basename(os.path.dirname(p)) + "-" + os.path.basename(p) + ".orig")
    if os.path.exists(p) and not os.path.exists(dst): shutil.copy2(p, dst)

# ---- server.properties (behind Velocity; RCON on localhost for admin scripts) ----
sp = M + "/server.properties"; backup(sp)
props = dict(l.rstrip("\n").split("=", 1) for l in open(sp) if "=" in l and not l.startswith("#"))
pw_file = "/root/factions_rcon_password.txt"
if not os.path.exists(pw_file):
    open(pw_file, "w").write(secrets.token_urlsafe(24)); os.chmod(pw_file, 0o600)
props.update({"online-mode": "false", "motd": "§c§lCrispy Factions §7- Working Man's 2013 Factions", "pvp": "true", "difficulty": "normal",
              "allow-flight": "false", "spawn-protection": "0", "view-distance": "8", "simulation-distance": "6", "enable-command-block": "false",
              "enable-rcon": "true", "rcon.port": "25581", "rcon.password": open(pw_file).read().strip(), "broadcast-rcon-to-ops": "false"})
open(sp, "w").write("".join(f"{k}={v}\n" for k, v in props.items()))

# ---- Paper / Spigot: Velocity forwarding + cannon-friendly physics ----
pg = M + "/config/paper-global.yml"; backup(pg); d = ry(pg)
d["proxies"]["velocity"].update({"enabled": True, "online-mode": True, "secret": open("/AMPStorage/.ampdata/instances/test01/Minecraft/forwarding.secret").read().strip()})
wy(pg, d)
pw = M + "/config/paper-world-defaults.yml"; backup(pw); d = ry(pw)
env = d["environment"]; env["optimize-explosions"] = True
fx = d["fixes"]; fx["falling-block-height-nerf"] = "disabled"; fx["tnt-entity-height-nerf"] = "disabled"; fx["prevent-tnt-from-moving-in-water"] = False
wy(pw, d)
sy = M + "/spigot.yml"; backup(sy); d = ry(sy)
d["world-settings"]["default"]["max-tnt-per-tick"] = 500
wy(sy, d)

# ---- SaberFactions ----
cj = P + "/Factions/conf.json"; backup(cj); d = json.load(open(cj))
d.update({"factionMemberLimit": 15, "factionAltMemberLimit": 0, "powerPlayerMax": 10.0, "powerPlayerMin": -10.0, "powerPlayerStarting": 0.0,
          "powerPerDeath": 2.0, "powerPerMinute": 0.2, "powerRegenOffline": False,
          "territoryBlockTNT": False, "territoryBlockTNTWhenOffline": False, "territoryBlockCreepers": False, "territoryBlockCreepersWhenOffline": False,
          "wildernessBlockTNT": False, "wildernessBlockCreepers": False, "warZoneBlockTNT": True, "safeZoneBlockTNT": True,
          "handleExploitTNTWaterlog": False, "defaultMaxVaults": 0})
json.dump(d, open(cj, "w"), indent=2)
fc = P + "/Factions/config.yml"; backup(fc); t = open(fc).read()
def ytoggle(text, section, key, val):
    pat = re.compile(r"(^" + re.escape(section) + r":\n(?:[ \t].*\n|\n)*?[ \t]+" + re.escape(key) + r":)[ \t]*\S+", re.M)
    new, n = pat.subn(lambda m: m.group(1) + " " + val, text, count=1)
    if not n: print("WARN not found:", section, key)
    return new
t = re.sub(r"^enable-faction-flight:\s*\S+", "enable-faction-flight: false", t, flags=re.M)
for sec, key in (("ftnt", "Enabled"), ("Tntfill", "enabled"), ("fchest", "Enabled"), ("fvault", "Enabled"), ("f-alts", "Enabled"), ("f-grace", "Enabled")):
    t = ytoggle(t, sec, key, "false")
open(fc, "w").write(t)
for f, pat, rep in ((P + "/Factions/configuration/upgrades.yml", r"(fupgrades:\n\s+Enabled:)\s*true", r"\1 false"),
                    (P + "/Factions/configuration/missions.yml", r"^Missions-Enabled:\s*true", "Missions-Enabled: false")):
    backup(f); s = open(f).read(); s2 = re.sub(pat, rep, s, count=1, flags=re.M); open(f, "w").write(s2); print(os.path.basename(f), "changed" if s2 != s else "UNCHANGED")

# ---- OldCombatMechanics: everyone on 1.8 mode, no offhand, no shields/mace/crystals crafting ----
oc = P + "/OldCombatMechanics/config.yml"; backup(oc); s = open(oc).read()
d = ry(oc)
always = d["always_enabled_modules"]; disabled = d["disabled_modules"]
if "disable-offhand" in disabled: disabled.remove("disable-offhand")
if "disable-offhand" not in always: always.append("disable-offhand")
s = re.sub(r"^always_enabled_modules:\n(?:\s+-.*\n)+", "always_enabled_modules:\n" + "".join(f"  - {m}\n" for m in always), s, flags=re.M)
s = re.sub(r"^disabled_modules:\n(?:\s+-.*\n)+", "disabled_modules:\n" + "".join(f"  - {m}\n" for m in disabled), s, flags=re.M)
s = re.sub(r"(^worlds:\n\s+__default__:)\s*\n?(?:\s+-.*\n)+", r"\1\n    - old\n", s, flags=re.M)
s = re.sub(r"(^disable-crafting:\n(?:.*\n)*?\s+denied:)\s*\n?(?:\s+-.*\n)+", r"\1\n    - shield\n    - mace\n    - end_crystal\n", s, count=1, flags=re.M)
open(oc, "w").write(s)
d = ry(oc); print("OCM worlds", d["worlds"], "| offhand always:", "disable-offhand" in d["always_enabled_modules"], "| denied", d["disable-crafting"]["denied"])

# ---- Essentials: classic economy + kits ----
ec = P + "/Essentials/config.yml"; backup(ec); s = open(ec).read()
for k, v in (("starting-balance", "500"), ("min-money", "0"), ("teleport-delay", "3"), ("auto-afk-timeout", "-1"), ("update-check", "false"), ("spawn-on-join", "false")):
    s = re.sub(rf"^{k}:.*$", f"{k}: {v}", s, count=1, flags=re.M)
open(ec, "w").write(s)
kits = {"kits": {
    "starter": {"delay": 86400, "items": ["stone_sword 1", "stone_pickaxe 1", "stone_axe 1", "stone_shovel 1", "bread 16", "torch 32", "oak_log 16"]},
    "vip": {"delay": 86400, "items": ["sand 64", "sand 64", "glass 64", "redstone 64", "piston 16", "sticky_piston 8", "hopper 8", "repeater 16",
                                     "diamond_helmet 1 protection:2", "diamond_chestplate 1 protection:2", "diamond_leggings 1 protection:2", "diamond_boots 1 protection:2", "diamond_sword 1 sharpness:2"]},
    "venom": {"delay": 86400, "items": ["sand 64", "sand 64", "sand 64", "glass 64", "glass 64", "redstone 64", "piston 32", "sticky_piston 16", "hopper 16", "repeater 32", "dispenser 16",
                                       "diamond_helmet 1 protection:2 unbreaking:1", "diamond_chestplate 1 protection:2 unbreaking:1", "diamond_leggings 1 protection:2 unbreaking:1",
                                       "diamond_boots 1 protection:2 unbreaking:1", "diamond_sword 1 sharpness:2 unbreaking:1"]},
    "immortal": {"delay": 86400, "items": ["sand 64", "sand 64", "sand 64", "sand 64", "glass 64", "glass 64", "redstone 64", "redstone 64", "piston 64", "sticky_piston 32", "hopper 32",
                                          "repeater 64", "dispenser 32", "observer 16",
                                          "diamond_helmet 1 protection:2 unbreaking:2", "diamond_chestplate 1 protection:2 unbreaking:2", "diamond_leggings 1 protection:2 unbreaking:2",
                                          "diamond_boots 1 protection:2 unbreaking:2", "diamond_sword 1 sharpness:2 unbreaking:2", "bow 1 power:2"]}}}
kp = P + "/Essentials/kits.yml"; backup(kp); wy(kp, kits)

# ---- EconomyShopGUI: classic phased economy ----
E = P + "/EconomyShopGUI"
KEEP = {"Blocks", "Decoration", "Dyes", "Redstone", "Workstations", "Food"}
OURS = {"OBSIDIAN", "TNT", "CACTUS", "SUGAR_CANE", "BLAZE_ROD", "GUNPOWDER", "IRON_INGOT", "SPAWNER", "CREEPER_SPAWN_EGG", "HOPPER", "NETHER_STAR"}
slots = {"Blocks": 29, "Decoration": 30, "Dyes": 31, "Redstone": 32, "Workstations": 33, "Food": 40}
for f in os.listdir(E + "/sections"):
    name = f[:-4]; sp_ = f"{E}/sections/{f}"; backup(sp_); sec = ry(sp_)
    if name in KEEP:
        sec["enable"] = True; sec["slot"] = slots[name]
        sh = f"{E}/shops/{f}"; backup(sh); shop = ry(sh)
        for page in shop.get("pages", {}).values():
            items = page.get("items", {})
            for k in list(items):
                it = items[k]
                if str(it.get("material", "")).upper() in OURS: del items[k]; continue
                it.pop("sell", None)            # in this economy only the farm tables pay out
        wy(sh, shop)
    elif name not in ("Raiding", "Farming", "Spawners", "Potions", "Specials", "Phase2"):
        sec["enable"] = False
    wy(sp_, sec)
def section(name, slot, icon, title, items, enable=True, rows=None):
    sec = {"enable": enable, "slot": slot, "title": title, "hidden": False, "sub-section": False, "display-item": False,
           "fill-item": {"material": "AIR"}, "nav-bar": {"mode": "INHERIT"}, "item": {"material": icon, "displayname": title, "name": title}}
    page = {"items": {str(i + 1): it for i, it in enumerate(items)}}
    if rows: page["gui-rows"] = rows
    wy(f"{E}/sections/{name}.yml", sec); wy(f"{E}/shops/{name}.yml", {"pages": {"page1": page}})
section("Specials", 4, "NETHER_STAR", "&b&lSpecials", [
    {"material": "NETHER_STAR", "name": "&b&l✦ Aegis Vacation Star &7(25 Raid-Hours) ✦",
     "lore": ["&7Right-click inside your claim as &fLeader&7/&fCo-Leader", "&7during peacetime to bank &b25 raid-window hours", "&7of explosion protection. &8Ticks only during raid windows."],
     "enchantments": ["UNBREAKING:1"], "buy": 2500000},
    {"material": "HOPPER", "name": "&a&lCactus Collector", "lore": ["&7Collects every cactus that drops in its chunk.", "&8One per chunk."], "buy": 50000}])
# Sell prices are checked against every buy price above (and blocks that craft, smelt, scrape or break back into
# the item) so nothing can be bought and resold at a profit. Copper (waxed/oxidised blocks scrape back to 9 ingots)
# and emeralds (villagers pay them for cheap shop stone/sticks) are left out on purpose; iron stays Phase 2.
# Mass-farmable drops (kelp, gold, pearls, guardians) are kept low so cactus/cane and spawners stay the main income.
section("Farming", 20, "CACTUS", "&a&lFarm Sell", [
    {"material": "CACTUS", "sell": 10, "buy": 100}, {"material": "SUGAR_CANE", "sell": 15, "buy": 150},
    {"material": "WHEAT", "sell": 4}, {"material": "CARROT", "sell": 2}, {"material": "POTATO", "sell": 2},
    {"material": "BEETROOT", "sell": 3}, {"material": "PUMPKIN", "sell": 6}, {"material": "MELON_SLICE", "sell": 1},
    {"material": "NETHER_WART", "sell": 3}, {"material": "COCOA_BEANS", "sell": 3}, {"material": "SWEET_BERRIES", "sell": 1},
    {"material": "KELP", "sell": 1},
    # added 2026-10-21
    {"material": "MELON", "sell": 4}, {"material": "BAMBOO", "sell": 0.5}, {"material": "RED_MUSHROOM", "sell": 2}, {"material": "BROWN_MUSHROOM", "sell": 2}, {"material": "CHORUS_FRUIT", "sell": 2}, {"material": "EGG", "sell": 1}, {"material": "HONEYCOMB", "sell": 3}, {"material": "APPLE", "sell": 2}, {"material": "BEEF", "sell": 2}, {"material": "PORKCHOP", "sell": 2}, {"material": "CHICKEN", "sell": 2}, {"material": "MUTTON", "sell": 2}, {"material": "RABBIT", "sell": 2}, {"material": "COD", "sell": 2}, {"material": "SALMON", "sell": 2}, {"material": "COOKED_BEEF", "sell": 3}, {"material": "COOKED_PORKCHOP", "sell": 3}, {"material": "COOKED_CHICKEN", "sell": 3}, {"material": "COOKED_MUTTON", "sell": 3}, {"material": "COOKED_COD", "sell": 3}, {"material": "COOKED_SALMON", "sell": 3}, {"material": "WHITE_WOOL", "sell": 2}])
section("Ores", 19, "DIAMOND", "&b&lOre Sell", [
    {"material": "COAL", "sell": 3}, {"material": "REDSTONE", "sell": 1}, {"material": "LAPIS_LAZULI", "sell": 2},
    {"material": "QUARTZ", "sell": 3}, {"material": "GOLD_INGOT", "sell": 8}, {"material": "DIAMOND", "sell": 100},
    {"material": "NETHERITE_SCRAP", "sell": 400},
    # added 2026-10-21
    {"material": "RAW_GOLD", "sell": 7}, {"material": "AMETHYST_SHARD", "sell": 2}, {"material": "GLOWSTONE_DUST", "sell": 1}, {"material": "FLINT", "sell": 1}, {"material": "ECHO_SHARD", "sell": 25}, {"material": "ANCIENT_DEBRIS", "sell": 400}, {"material": "NETHERITE_INGOT", "sell": 1600}, {"material": "COAL_BLOCK", "sell": 27}, {"material": "REDSTONE_BLOCK", "sell": 9}, {"material": "LAPIS_BLOCK", "sell": 18}, {"material": "QUARTZ_BLOCK", "sell": 12}, {"material": "GOLD_BLOCK", "sell": 72}, {"material": "DIAMOND_BLOCK", "sell": 900}])
section("Mobs", 25, "BONE", "&c&lMob Drop Sell", [
    {"material": "BLAZE_ROD", "sell": 35}, {"material": "GUNPOWDER", "sell": 20}, {"material": "ROTTEN_FLESH", "sell": 2},
    {"material": "BONE", "sell": 3}, {"material": "STRING", "sell": 3}, {"material": "SPIDER_EYE", "sell": 3},
    {"material": "ENDER_PEARL", "sell": 3}, {"material": "SLIME_BALL", "sell": 4}, {"material": "MAGMA_CREAM", "sell": 3},
    {"material": "GHAST_TEAR", "sell": 25}, {"material": "LEATHER", "sell": 3}, {"material": "RABBIT_HIDE", "sell": 2},
    {"material": "FEATHER", "sell": 1}, {"material": "INK_SAC", "sell": 2}, {"material": "GLOW_INK_SAC", "sell": 3},
    {"material": "PRISMARINE_SHARD", "sell": 1}, {"material": "PRISMARINE_CRYSTALS", "sell": 2},
    {"material": "SHULKER_SHELL", "sell": 30}, {"material": "WITHER_SKELETON_SKULL", "sell": 500},
    # added 2026-10-21
    {"material": "PHANTOM_MEMBRANE", "sell": 8}, {"material": "RABBIT_FOOT", "sell": 8}, {"material": "ARMADILLO_SCUTE", "sell": 4}, {"material": "TURTLE_SCUTE", "sell": 10}, {"material": "BREEZE_ROD", "sell": 15}, {"material": "NAUTILUS_SHELL", "sell": 20}, {"material": "TRIDENT", "sell": 75}, {"material": "TOTEM_OF_UNDYING", "sell": 150}])
section("Raiding", 21, "TNT", "&c&lRaiding", [
    {"material": "OBSIDIAN", "buy": 200}, {"material": "TNT", "buy": 150}, {"material": "CREEPER_SPAWN_EGG", "buy": 15000},
    {"material": "SAND", "buy": 5}, {"material": "RED_SAND", "buy": 5}, {"material": "GRAVEL", "buy": 5}, {"material": "WATER_BUCKET", "buy": 50}])
section("Spawners", 22, "SPAWNER", "&8&lSpawners", [
    {"material": "SPAWNER", "spawnertype": "BLAZE", "buy": 200000}, {"material": "SPAWNER", "spawnertype": "SKELETON", "buy": 75000},
    {"material": "SPAWNER", "spawnertype": "ZOMBIE", "buy": 75000}])
section("Potions", 23, "SPLASH_POTION", "&d&lPotions", [
    {"material": "SPLASH_POTION", "potiontypes": ["strong_healing"], "buy": 150},
    {"material": "POTION", "potiontypes": ["strong_swiftness"], "buy": 250},
    {"material": "POTION", "potiontypes": ["fire_resistance"], "buy": 250}])
section("Phase2", 24, "IRON_BLOCK", "&6&lPhase 2 &7(Iron)", [
    {"material": "SPAWNER", "spawnertype": "IRON_GOLEM", "buy": 650000}, {"material": "IRON_INGOT", "sell": 40}], enable=False)
print("shop sections:", sorted(f[:-4] for f in os.listdir(E + "/sections") if ry(f"{E}/sections/{f}").get("enable")))
os.system(f"chown -R amp:amp {M}")
print("done")
