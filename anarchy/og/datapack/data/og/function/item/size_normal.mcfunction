# Restoring Draught: back to normal
function og:item/size_reset
particle minecraft:effect ~ ~1 ~ 0.5 1 0.5 0.1 40
playsound minecraft:block.beacon.deactivate player @a[distance=..24] ~ ~ ~ 1 1.2
title @s actionbar {"text":"◆ BACK TO NORMAL","color":"gray","bold":true}
