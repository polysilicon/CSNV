# Chrono Clock: where each player stood the last 5 seconds (x100), oldest in slot 4. og_hn counts good samples
scoreboard players operation @s og_x4 = @s og_x3
scoreboard players operation @s og_y4 = @s og_y3
scoreboard players operation @s og_z4 = @s og_z3
scoreboard players operation @s og_x3 = @s og_x2
scoreboard players operation @s og_y3 = @s og_y2
scoreboard players operation @s og_z3 = @s og_z2
scoreboard players operation @s og_x2 = @s og_x1
scoreboard players operation @s og_y2 = @s og_y1
scoreboard players operation @s og_z2 = @s og_z1
scoreboard players operation @s og_x1 = @s og_x0
scoreboard players operation @s og_y1 = @s og_y0
scoreboard players operation @s og_z1 = @s og_z0
execute store result score @s og_x0 run data get entity @s Pos[0] 100
execute store result score @s og_y0 run data get entity @s Pos[1] 100
execute store result score @s og_z0 run data get entity @s Pos[2] 100
scoreboard players add @s og_hn 1
