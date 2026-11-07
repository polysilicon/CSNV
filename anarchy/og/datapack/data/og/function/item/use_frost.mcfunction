# Frost Nova: run as the player who used it, at them
advancement revoke @s only og:item/frost
tag @s add og.caster
execute at @s run execute as @e[distance=..6,type=!#og:not_target,tag=!og.caster] at @s run damage @s 3 minecraft:freeze by @p[tag=og.caster]
execute at @s run execute as @e[distance=..6,type=!#og:not_target,tag=!og.caster] at @s run effect give @s minecraft:slowness 4 4
execute at @s run execute as @e[distance=..6,type=!#og:not_target,tag=!og.caster] at @s run effect give @s minecraft:mining_fatigue 4 2
execute at @s run execute as @e[distance=..6,type=!#og:not_target,tag=!og.caster] at @s run particle minecraft:snowflake ~ ~1 ~ 0.3 0.6 0.3 0.05 30
execute at @s run particle minecraft:snowflake ~ ~1 ~ 3 0.8 3 0.05 200
execute at @s run playsound minecraft:block.glass.break player @a[distance=..24] ~ ~ ~ 1 0.6
execute at @s run playsound minecraft:entity.player.hurt_freeze player @a[distance=..24] ~ ~ ~ 1 0.8
execute at @s run title @s actionbar {"text":"◆ FROST NOVA","color":"aqua","bold":true}
tag @s remove og.caster
