# Gravity Bomb: run as the player who used it, at them
advancement revoke @s only og:item/gravity
tag @s add og.caster
execute at @s run execute as @e[distance=..6,type=!#og:not_target,tag=!og.caster] at @s run effect give @s minecraft:levitation 3 2
execute at @s run execute as @e[distance=..6,type=!#og:not_target,tag=!og.caster] at @s run particle minecraft:portal ~ ~0.5 ~ 0.3 0.3 0.3 0.5 20
execute at @s run particle minecraft:reverse_portal ~ ~1 ~ 3 0.5 3 0.05 120
execute at @s run playsound minecraft:block.beacon.deactivate player @a[distance=..24] ~ ~ ~ 1 0.5
execute at @s run playsound minecraft:entity.shulker.shoot player @a[distance=..24] ~ ~ ~ 1 0.6
execute at @s run title @s actionbar {"text":"◆ GRAVITY BOMB","color":"dark_purple","bold":true}
tag @s remove og.caster
