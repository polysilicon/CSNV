# Snare Dart: run as the player who used it, at them
advancement revoke @s only og:item/snare
tag @s add og.caster
execute at @s run scoreboard players set #b og_i 48
execute at @s run execute anchored eyes positioned ^ ^ ^ rotated as @s run function og:item/snare_ray
execute at @s run execute as @e[tag=og.hit] at @s run function og:item/snare_hit
execute at @s run tag @e[tag=og.hit] remove og.hit
execute at @s run playsound minecraft:entity.arrow.shoot player @a[distance=..24] ~ ~ ~ 1 1.6
tag @s remove og.caster
