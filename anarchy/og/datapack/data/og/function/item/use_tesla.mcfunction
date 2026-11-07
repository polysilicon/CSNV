# Tesla Coil: run as the player who used it, at them
advancement revoke @s only og:item/tesla
tag @s add og.caster
execute at @s run execute as @e[distance=..5,type=!#og:not_target,tag=!og.caster] at @s run damage @s 6 minecraft:lightning_bolt by @p[tag=og.caster]
execute at @s run execute as @e[distance=..5,type=!#og:not_target,tag=!og.caster] at @s run effect give @s minecraft:slowness 3 1
execute at @s run execute as @e[distance=..5,type=!#og:not_target,tag=!og.caster] at @s run particle minecraft:electric_spark ~ ~1 ~ 0.3 0.6 0.3 0.3 30
execute at @s run particle minecraft:electric_spark ~ ~1 ~ 2.5 1 2.5 0.4 120
execute at @s run playsound minecraft:entity.lightning_bolt.thunder player @a[distance=..24] ~ ~ ~ 0.3 2
execute at @s run playsound minecraft:block.respawn_anchor.deplete player @a[distance=..24] ~ ~ ~ 0.8 1.6
execute at @s run title @s actionbar {"text":"◆ TESLA COIL","color":"yellow","bold":true}
tag @s remove og.caster
