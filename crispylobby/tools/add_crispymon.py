"""Add Crispymon to a CrispyLobby config.yml (idempotent): its vote reward server, its advancements as an earned
source, and Crispymon-only cosmetics (earned with Cobblemon-modpack advancements; CrispyLobby 1.25.0+ shows them on
the Crispymon page). Usage: python3 add_crispymon.py <config.yml>"""
import sys
p = sys.argv[1]; s = open(p).read()
if "crispymon:" in s.split("cosmetics:")[0] and "c_trainer" in s: print("already there"); sys.exit()

SERVER = '''    crispymon:
      label: "&c&lCrispymon"
      icon: TURTLE_EGG
      instance: Crispymon01
      reward: ["&e300 PokeDollars", "&b3 Ultra Balls", "&a1 Exp. Candy M"]   # 7 sites a day = 2,100 PokeDollars
      commands: ["balance %player% add 300", "give %player% cobblemon:ultra_ball 3", "give %player% cobblemon:exp_candy_m 1"]
'''
TAGS = '''    # ---- Crispymon: earned only by playing Crispymon (its Cobblemon-modpack advancements; the Crispymon page)
    c_trainer:   {display: "&c[Trainer]", icon: RED_WOOL, advancement: "cobblemon:catching/first_catch", note: "Catch your first Cobblemon"}
    c_rider:     {display: "&6[Rider]", icon: SADDLE, advancement: "cobblemon:catching/ride_pokemon", note: "Ride one of your Cobblemon"}
    c_fullteam:  {display: "&a[Full Team]", icon: TOTEM_OF_UNDYING, advancement: "cobblemon:catching/full_party", note: "Fill your party (six Cobblemon)"}
    c_evolver:   {display: "&d[Evolver]", icon: EXPERIENCE_BOTTLE, advancement: "cobblemon:catching/first_evolution", note: "Evolve a Cobblemon"}
    c_trader:    {display: "&e[Trader]", icon: EMERALD, advancement: "cobblemon:catching/trade_pokemon", note: "Trade a Cobblemon with another player"}
    c_fossil:    {display: "&7[Fossil Hunter]", icon: BONE_BLOCK, advancement: "cobblemon:geological/resurrect_pokemon", note: "Revive a fossil"}
    c_mega:      {display: "&5&l[Mega]", icon: AMETHYST_CLUSTER, advancement: "mega_showdown:mega_showdown/mega/mega_evolve", note: "Mega Evolve in battle"}
    c_cards:     {display: "&#FF3B3B&l[&#FF8A00&lD&#FFE600&le&#3BFF6A&lg&#00D1FF&le&#7A5CFF&ln&#FF4FD8&l]", icon: PAPER, advancement: "cobbletcg:open_100", note: "Open 100 card packs"}
    c_berries:   {display: "&2[Berry Master]", icon: SWEET_BERRIES, advancement: "cobblemon:agriculture/obtain_all_berries", note: "Collect every kind of berry"}
    c_alpha:     {display: "&#FF4D4D&l[Alpha]", icon: NETHERITE_SWORD, advancement: "cobblemon:catching/first_alpha_catch", note: "Catch an alpha", rare: true}
    c_shiny:     {display: "&#FFF1A8&l[&#FFE45C&lS&#FFD700&lh&#FFC800&li&#FFB800&ln&#FFA800&ly&#FF9900&l]", icon: GLOWSTONE_DUST, advancement: "cobblemon:catching/first_shiny_catch", note: "Catch a shiny", rare: true}
'''
NAMES = '''    # ---- Crispymon: earned only by playing Crispymon
    c_apricorn:  {name: Apricorn, code: "&#FF3B3B>&#FFFFFF", icon: RED_DYE, advancement: "cobblemon:catching/craft_apricorn_balls", note: "Craft an Apricorn ball"}
    c_shinygold: {name: Shiny Gold, code: "&#FFE45C>&#FF9900", icon: GOLD_INGOT, advancement: "cobblemon:catching/first_shiny_catch", note: "Catch a shiny", rare: true}
'''
CHATS = '''    # ---- Crispymon: earned only by playing Crispymon
    c_berry:     {name: Berry, code: "&#E05AE0", icon: SWEET_BERRIES, advancement: "cobblemon:agriculture/obtain_berry", note: "Pick a berry"}
    c_megaglow:  {name: Mega Glow, code: "&#FF7AE0>&#7A5CFF", icon: AMETHYST_SHARD, advancement: "mega_showdown:mega_showdown/mega/mega_evolve", note: "Mega Evolve in battle"}
'''
# vote server: after the pvp entry's commands line
i = s.index("\n    pvp:\n"); j = s.index("commands:", i); j = s.index("\n", j) + 1
s = s[:j] + SERVER + s[j:]
# earned source
s = s.replace("CrispyLobby01/Minecraft/world/players/advancements]", "CrispyLobby01/Minecraft/world/players/advancements,\n                   Crispymon01/Minecraft/world/advancements]", 1)
# cosmetics: after each section's "# ---- end of rare" (tags, name colours, chat colours), in that order
marks = [k for k in range(len(s)) if s.startswith("    # ---- end of rare\n", k)]
assert len(marks) == 3, f"expected 3 end-of-rare markers, found {len(marks)}"
for k, block in sorted(zip(marks, [TAGS, NAMES, CHATS]), reverse=True):
    e = k + len("    # ---- end of rare\n"); s = s[:e] + block + s[e:]
open(p, "w").write(s); print("added Crispymon to", p)
