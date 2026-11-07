# as a splash marker: keep up with its potion, or burst where it was last seen
scoreboard players operation #id og_i = @s og_sid
execute as @e[type=minecraft:splash_potion,tag=og.sp] if score @s og_sid = #id og_i run tag @s add og.me
tag @s add og.f
execute as @e[type=minecraft:splash_potion,tag=og.me] at @s run tp @e[type=minecraft:marker,tag=og.f,limit=1] ~ ~ ~
tag @s remove og.f
execute unless entity @e[type=minecraft:splash_potion,tag=og.me] at @s run function og:item/sp_burst
tag @e[tag=og.me] remove og.me
