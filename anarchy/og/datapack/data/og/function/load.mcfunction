scoreboard objectives add bm_sneak dummy
scoreboard objectives add bm dummy
execute unless score #spot bm matches 1..5 store result score #spot bm run random value 1..5
schedule function og:bm/loop 20t replace
