# Stim Shot: run as the player who used it, at them
advancement revoke @s only og:item/stim
tag @s add og.caster
execute at @s run effect give @s minecraft:instant_health 1 1 true
execute at @s run effect give @s minecraft:regeneration 6 1 true
execute at @s run effect give @s minecraft:absorption 30 0 true
execute at @s run particle minecraft:heart ~ ~1.8 ~ 0.4 0.3 0.4 0 6
execute at @s run playsound minecraft:item.honey_bottle.drink player @a[distance=..24] ~ ~ ~ 1 1.4
execute at @s run title @s actionbar {"text":"◆ STIM SHOT","color":"red","bold":true}
tag @s remove og.caster
