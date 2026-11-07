# Phase Shard: half a block at a time along the look; stop where the feet or head would be inside a block
scoreboard players remove #b og_i 1
execute positioned ^ ^ ^0.5 unless block ~ ~ ~ #og:passable run return 0
execute positioned ^ ^ ^0.5 unless block ~ ~1 ~ #og:passable run return 0
execute positioned ^ ^ ^0.5 run tp @s ~ ~ ~
execute if score #b og_i matches 1.. positioned ^ ^ ^0.5 run function og:item/blink_ray
