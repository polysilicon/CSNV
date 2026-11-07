# Moon Juice: replaces any brew you already had, for 180 s
function og:item/size_reset
attribute @s minecraft:gravity modifier add og:size -0.06 add_value
attribute @s minecraft:jump_strength modifier add og:size 0.15 add_value
attribute @s minecraft:safe_fall_distance modifier add og:size 256 add_value
scoreboard players set @s og_size 180
tag @s add og.sized
particle minecraft:effect ~ ~1 ~ 0.5 1 0.5 0.1 40
playsound minecraft:block.amethyst_block.resonate player @a[distance=..24] ~ ~ ~ 1 0.8
title @s actionbar {"text":"◆ MOON JUICE · 3 minutes","color":"white","bold":true}
