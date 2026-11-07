# Chrono Clock: run as the player who used it, at them
advancement revoke @s only og:item/chrono
tag @s add og.caster
execute at @s run execute unless score @s og_hn matches 5.. run return run function og:item/refund {k:"chrono",what:"The clock needs 5 seconds in this dimension to wind"}
execute at @s run particle minecraft:totem_of_undying ~ ~1 ~ 0.3 0.6 0.3 0.3 30
execute at @s run execute store result storage og:t x double 0.01 run scoreboard players get @s og_x4
execute at @s run execute store result storage og:t y double 0.01 run scoreboard players get @s og_y4
execute at @s run execute store result storage og:t z double 0.01 run scoreboard players get @s og_z4
execute at @s run function og:item/chrono_tp with storage og:t
execute at @s run scoreboard players set @s og_hn 0
execute at @s run execute at @s run particle minecraft:totem_of_undying ~ ~1 ~ 0.3 0.6 0.3 0.3 30
execute at @s run execute at @s run playsound minecraft:block.bell.resonate player @a[distance=..24] ~ ~ ~ 1 1.6
execute at @s run title @s actionbar {"text":"◆ REWOUND","color":"gold","bold":true}
tag @s remove og.caster
