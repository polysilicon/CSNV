# The Black Market: crouch 4 seconds on one ordinary block in the market. Nothing marks the spot (no block, sign,
# chest or entity), so x-ray and entity finders have nothing to see; only this server-side check knows where it is.
execute in crispy:market as @a[x=-107,y=99,z=-77,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
scoreboard players add @a[tag=bm_here] bm_sneak 1
scoreboard players reset @a[tag=!bm_here] bm_sneak
execute as @a[tag=bm_here,scores={bm_sneak=4..}] at @s unless entity @s[advancements={anarchy:black_market=true}] run function og:bm/found
tag @a remove bm_here
