"""Writes the Black Market's rotating-spot functions (python3 gen_bm.py). The current spot is #spot in objective bm;
after each find it moves to a different random one, so finders can't pass the location on."""
SPOTS = [  # (x, y, z) block a player crouches in: a covered corner inside or right beside a shop building, in an
           # area that opens to the outside (find_spots2: walkable from the shop and connected to open sky), each
           # checked in the live world (feet and head clear, solid ground)
    (-26, 93, -100),   # Basic Tools And Equipment
    (-58, 93, -71),    # Concrete Mixer
    (-57, 105, -35),   # Redstone Parts Dealer
    (203, 74, -202),   # Building Blocks
    (109, 175, -146),  # Cartography
    (164, 155, 235),   # Cookies And Milk
    (148, 86, -206),   # fireworks tags and leads
    (-138, 95, -52),   # Golden Food Supplies
]
N = len(SPOTS)
F = "datapack/data/og/function/bm/"
open("datapack/data/og/function/load.mcfunction", "w").write("\n".join([
    "scoreboard objectives add bm_sneak dummy", "scoreboard objectives add bm dummy",
    f"execute unless score #spot bm matches 1..{N} store result score #spot bm run random value 1..{N}",
    "schedule function og:bm/loop 20t replace", ""]))
sneak = 'if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}}'
open(F + "second.mcfunction", "w").write("\n".join(
    ["# The Black Market: crouch 4 seconds on today's spot (#spot bm, one of the nooks in gen_bm.py). Nothing marks it",
     "# (no block, sign, chest or entity) and it moves after every find, so x-ray, entity finders and word of mouth don't help."]
    + [f"execute if score #spot bm matches {i} in crispy:market as @a[x={x},y={y},z={z},dx=0,dy=0,dz=0,gamemode=!spectator] {sneak} run tag @s add bm_here"
       for i, (x, y, z) in enumerate(SPOTS, 1)]
    + ["scoreboard players add @a[tag=bm_here] bm_sneak 1", "scoreboard players reset @a[tag=!bm_here] bm_sneak",
       "execute as @a[tag=bm_here,scores={bm_sneak=4..}] at @s unless entity @s[advancements={anarchy:black_market=true}] run function og:bm/found",
       "tag @a remove bm_here", ""]))
open(F + "move.mcfunction", "w").write("\n".join([
    f"# to a different random spot: add 1..{N - 1} and wrap round",
    f"execute store result score #r bm run random value 1..{N - 1}",
    "scoreboard players operation #spot bm += #r bm",
    f"execute if score #spot bm matches {N + 1}.. run scoreboard players remove #spot bm {N}", ""]))
open(F + "found.mcfunction", "w").write("\n".join([
    "# the dealer appears beside the finder for a moment, pays out, and is gone; then the market moves",
    "scoreboard players reset @s bm_sneak",
    "execute at @s run summon minecraft:wandering_trader ^ ^ ^1 {Tags:[\"bm_npc\"],NoAI:1b,Invulnerable:1b,Silent:1b,PersistenceRequired:1b,DespawnDelay:200,"
    "CustomNameVisible:1b,CustomName:{text:\"???\",color:\"dark_gray\",italic:true},Offers:{Recipes:[]}}",
    "execute at @s run particle minecraft:large_smoke ^ ^1 ^1 0.4 0.8 0.4 0.01 40",
    "playsound minecraft:entity.wandering_trader.reappeared neutral @s ~ ~ ~ 1 0.7",
    "tellraw @s [{\"text\":\"??? \",\"color\":\"dark_gray\",\"italic\":true},{\"text\":\"whispers: \",\"color\":\"gray\",\"italic\":true},{\"text\":\"You didn't find me. Take this, and tell no one. I won't be here tomorrow.\",\"color\":\"white\",\"italic\":true}]",
    "loot give @s loot og:black_market",
    "advancement grant @s only anarchy:black_market",
    "# unlock and wear [Black Market] at once (chat-tags mod -> lobby), not when the advancement file next saves",
    "crispytag award blackmarket",
    "function og:bm/move",
    "schedule function og:bm/vanish 5s replace", ""]))
print(N, "spots")
