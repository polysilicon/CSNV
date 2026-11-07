# Swap Orb: like the Snare Dart's ray, with portal sparks
scoreboard players remove #b og_i 1
particle minecraft:portal ~ ~ ~ 0 0 0 0 1
execute positioned ~-0.5 ~-0.5 ~-0.5 as @e[type=!#og:not_target,tag=!og.caster,dx=0,dy=0,dz=0,limit=1] run tag @s add og.hit
execute if entity @e[tag=og.hit] run return 0
execute unless block ~ ~ ~ #og:passable run return 0
execute if score #b og_i matches 1.. positioned ^ ^ ^0.5 run function og:item/swap_ray
