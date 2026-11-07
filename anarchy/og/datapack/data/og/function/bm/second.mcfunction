# The Black Market: crouch 4 seconds on today's spot (#spot bm, one of the nooks in gen_bm.py). Nothing marks it
# (no block, sign, chest or entity) and it moves after every find, so x-ray, entity finders and word of mouth don't help.
execute if score #spot bm matches 1 in crispy:market as @a[x=-26,y=93,z=-100,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
execute if score #spot bm matches 2 in crispy:market as @a[x=-137,y=172,z=-72,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
execute if score #spot bm matches 3 in crispy:market as @a[x=-58,y=93,z=-71,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
execute if score #spot bm matches 4 in crispy:market as @a[x=-57,y=105,z=-35,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
execute if score #spot bm matches 5 in crispy:market as @a[x=203,y=74,z=-202,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
execute if score #spot bm matches 6 in crispy:market as @a[x=109,y=175,z=-146,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
execute if score #spot bm matches 7 in crispy:market as @a[x=164,y=155,z=235,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
execute if score #spot bm matches 8 in crispy:market as @a[x=148,y=86,z=-206,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
execute if score #spot bm matches 9 in crispy:market as @a[x=-138,y=95,z=-52,dx=0,dy=0,dz=0,gamemode=!spectator] if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:flags":{is_sneaking:true}}} run tag @s add bm_here
scoreboard players add @a[tag=bm_here] bm_sneak 1
scoreboard players reset @a[tag=!bm_here] bm_sneak
execute as @a[tag=bm_here,scores={bm_sneak=4..}] at @s unless entity @s[advancements={anarchy:black_market=true}] run function og:bm/found
tag @a remove bm_here
