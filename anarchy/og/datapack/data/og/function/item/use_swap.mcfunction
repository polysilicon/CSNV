# Swap Orb: run as the player who used it, at them
advancement revoke @s only og:item/swap
tag @s add og.caster
execute at @s run scoreboard players set #b og_i 48
execute at @s run execute anchored eyes positioned ^ ^ ^ rotated as @s run function og:item/swap_ray
execute at @s run execute unless entity @e[tag=og.hit] run return run function og:item/refund {k:"swap",what:"Nothing to swap with"}
execute at @s run execute as @e[tag=og.hit] at @s run summon minecraft:marker ~ ~ ~ {Tags:["og.swp"]}
execute at @s run tp @e[tag=og.hit] ~ ~ ~
execute at @s run execute at @n[type=minecraft:marker,tag=og.swp] run tp @s ~ ~ ~
execute at @s run kill @e[type=minecraft:marker,tag=og.swp]
execute at @s run execute at @e[tag=og.hit] run particle minecraft:reverse_portal ~ ~1 ~ 0.3 0.6 0.3 0.05 40
execute at @s run execute at @s run particle minecraft:reverse_portal ~ ~1 ~ 0.3 0.6 0.3 0.05 40
execute at @s run tag @e[tag=og.hit] remove og.hit
execute at @s run playsound minecraft:entity.shulker.teleport player @a[distance=..24] ~ ~ ~ 1 1.2
execute at @s run title @s actionbar {"text":"◆ SWAPPED","color":"dark_aqua","bold":true}
tag @s remove og.caster
