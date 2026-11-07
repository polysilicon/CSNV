# Phase Shard: run as the player who used it, at them
advancement revoke @s only og:item/blink
tag @s add og.caster
execute at @s run particle minecraft:reverse_portal ~ ~1 ~ 0.3 0.6 0.3 0.05 40
execute at @s run scoreboard players set #b og_i 20
execute at @s run execute rotated as @s run function og:item/blink_ray
execute at @s run execute at @s run particle minecraft:reverse_portal ~ ~1 ~ 0.3 0.6 0.3 0.05 40
execute at @s run execute at @s run playsound minecraft:entity.enderman.teleport player @a[distance=..24] ~ ~ ~ 0.8 1.4
tag @s remove og.caster
