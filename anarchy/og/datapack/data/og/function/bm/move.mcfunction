# to a different random spot: add 1..8 and wrap round
execute store result score #r bm run random value 1..8
scoreboard players operation #spot bm += #r bm
execute if score #spot bm matches 10.. run scoreboard players remove #spot bm 9
