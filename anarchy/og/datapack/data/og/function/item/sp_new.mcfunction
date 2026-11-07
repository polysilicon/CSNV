tag @s add og.sp
scoreboard players set #k og_i 0
execute if entity @s[nbt={Item:{components:{"minecraft:custom_data":{bm:"grow"}}}}] run scoreboard players set #k og_i 1
execute if entity @s[nbt={Item:{components:{"minecraft:custom_data":{bm:"shrink"}}}}] run scoreboard players set #k og_i 2
execute if entity @s[nbt={Item:{components:{"minecraft:custom_data":{bm:"moon"}}}}] run scoreboard players set #k og_i 3
execute if entity @s[nbt={Item:{components:{"minecraft:custom_data":{bm:"normal"}}}}] run scoreboard players set #k og_i 4
execute if score #k og_i matches 0 run return 0
scoreboard players add #sid og_i 1
scoreboard players operation @s og_sid = #sid og_i
summon minecraft:marker ~ ~ ~ {Tags:["og.spm","og.new"]}
scoreboard players operation @n[type=minecraft:marker,tag=og.new] og_sid = #sid og_i
scoreboard players operation @n[type=minecraft:marker,tag=og.new] og_sk = #k og_i
tag @e[type=minecraft:marker,tag=og.new] remove og.new
