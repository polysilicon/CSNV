# the potion broke here: its brew hits everything living nearby (the thrower too, like any splash)
execute if score @s og_sk matches 1 as @e[distance=..4,type=!#og:not_target] at @s run function og:item/size_grow
execute if score @s og_sk matches 2 as @e[distance=..4,type=!#og:not_target] at @s run function og:item/size_shrink
execute if score @s og_sk matches 3 as @e[distance=..4,type=!#og:not_target] at @s run function og:item/size_moon
execute if score @s og_sk matches 4 as @e[distance=..4,type=!#og:not_target] at @s run function og:item/size_normal
kill @s
