# once a second (og:bm/loop): size potions run out, and dying ends them
scoreboard players remove @a[tag=og.sized] og_size 1
title @a[tag=og.sized,scores={og_size=10}] actionbar {"text":"◆ Your potion wears off in 10 s","color":"gray"}
execute as @a[tag=og.sized,scores={og_died=1..}] run function og:item/size_reset
execute as @a[tag=og.sized] unless score @s og_size matches 1.. run function og:item/size_reset
scoreboard players reset @a og_died
