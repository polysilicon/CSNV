# Snare Dart: half a block at a time from the eyes; the first target within 0.8 gets og.hit, a wall stops it
scoreboard players remove #b og_i 1
particle minecraft:happy_villager ~ ~ ~ 0 0 0 0 1
execute positioned ~-0.5 ~-0.5 ~-0.5 as @e[type=!#og:not_target,tag=!og.caster,dx=0,dy=0,dz=0,limit=1] run tag @s add og.hit
execute if entity @e[tag=og.hit] run return 0
execute unless block ~ ~ ~ #og:passable run return 0
execute if score #b og_i matches 1.. positioned ^ ^ ^0.5 run function og:item/snare_ray
