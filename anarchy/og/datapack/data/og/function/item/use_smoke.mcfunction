# Smoke Bomb: run as the player who used it, at them
advancement revoke @s only og:item/smoke
tag @s add og.caster
execute at @s run execute as @e[distance=..6,type=!#og:not_target,tag=!og.caster] at @s run effect give @s minecraft:blindness 4 0
execute at @s run execute as @e[distance=..6,type=!#og:not_target,tag=!og.caster] at @s run effect give @s minecraft:slowness 4 0
execute at @s run effect give @s minecraft:invisibility 6 0 true
execute at @s run effect give @s minecraft:speed 6 1 true
execute at @s run particle minecraft:campfire_cosy_smoke ~ ~1 ~ 2.5 1.2 2.5 0.01 160
execute at @s run particle minecraft:large_smoke ~ ~1 ~ 2 1 2 0.02 80
execute at @s run playsound minecraft:entity.generic.extinguish_fire player @a[distance=..24] ~ ~ ~ 1 0.6
execute at @s run title @s actionbar {"text":"◆ SMOKE BOMB","color":"gray","bold":true}
tag @s remove og.caster
