# once a second (og:bm/loop): brews run out, and dying ends them; the Chrono Clock's position history
scoreboard players remove @e[tag=og.sized] og_size 1
title @a[tag=og.sized,scores={og_size=10}] actionbar {"text":"◆ Your brew wears off in 10 s","color":"gray"}
execute as @a[tag=og.sized,scores={og_died=1..}] run function og:item/size_reset
execute as @e[tag=og.sized] unless score @s og_size matches 1.. run function og:item/size_reset
execute as @a[scores={og_died=1..}] run scoreboard players set @s og_hn 0
scoreboard players reset @a og_died
execute as @a[gamemode=!spectator] run function og:item/history
