# Swiftfoot Tonic: replaces any brew you already had, for 180 s
function og:item/size_reset
attribute @s minecraft:movement_speed modifier add og:size 0.04 add_value
attribute @s minecraft:step_height modifier add og:size 0.9 add_value
scoreboard players set @s og_size 180
tag @s add og.sized
particle minecraft:effect ~ ~1 ~ 0.5 1 0.5 0.1 40
playsound minecraft:entity.horse.gallop player @a[distance=..24] ~ ~ ~ 1 1.4
title @s actionbar {"text":"◆ SWIFTFOOT TONIC · 3 minutes","color":"yellow","bold":true}
