# Growth Potion: replaces any brew you already had, for 180 s
function og:item/size_reset
attribute @s minecraft:scale modifier add og:size 1.0 add_value
attribute @s minecraft:max_health modifier add og:size 8 add_value
attribute @s minecraft:entity_interaction_range modifier add og:size 1.5 add_value
attribute @s minecraft:block_interaction_range modifier add og:size 1.5 add_value
scoreboard players set @s og_size 180
tag @s add og.sized
particle minecraft:effect ~ ~1 ~ 0.5 1 0.5 0.1 40
playsound minecraft:block.beacon.power_select player @a[distance=..24] ~ ~ ~ 1 0.6
title @s actionbar {"text":"◆ GROWTH POTION · 3 minutes","color":"green","bold":true}
