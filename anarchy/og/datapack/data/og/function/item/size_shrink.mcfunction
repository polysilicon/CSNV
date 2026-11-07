# Shrink Potion: replaces any brew you already had, for 180 s
function og:item/size_reset
attribute @s minecraft:scale modifier add og:size -0.65 add_value
scoreboard players set @s og_size 180
tag @s add og.sized
particle minecraft:effect ~ ~1 ~ 0.5 1 0.5 0.1 40
playsound minecraft:entity.illusioner.mirror_move player @a[distance=..24] ~ ~ ~ 1 1.6
title @s actionbar {"text":"◆ SHRINK POTION · 3 minutes","color":"light_purple","bold":true}
