# to a different random spot: add 1..7 and wrap round
execute store result score #r bm run random value 1..7
scoreboard players operation #spot bm += #r bm
execute if score #spot bm matches 9.. run scoreboard players remove #spot bm 8
