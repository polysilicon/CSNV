# The Black Market: crouch 4 seconds on today's spot (#spot bm, one of the nooks in gen_bm.py). Nothing marks it
# (no block, sign, chest or entity) and it moves after every find, so x-ray, entity finders and word of mouth don't help.
execute if score #spot bm matches 1 in crispy:market as @a[x=-107,y=99,z=-77,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
execute if score #spot bm matches 2 in crispy:market as @a[x=-57,y=105,z=-39,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
execute if score #spot bm matches 3 in crispy:market as @a[x=-26,y=93,z=-100,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
execute if score #spot bm matches 4 in crispy:market as @a[x=-52,y=106,z=-90,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
execute if score #spot bm matches 5 in crispy:market as @a[x=191,y=73,z=-207,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
scoreboard players add @a[tag=bm_here] bm_sneak 1
scoreboard players reset @a[tag=!bm_here] bm_sneak
execute as @a[tag=bm_here,scores={bm_sneak=4..}] at @s unless entity @s[advancements={anarchy:black_market=true}] run function og:bm/found
tag @a remove bm_here
