scoreboard objectives add bm_sneak dummy
scoreboard objectives add bm dummy
scoreboard objectives add og_i dummy
scoreboard objectives add og_size dummy
scoreboard objectives add og_died deathCount
execute unless score #spot bm matches 1..8 store result score #spot bm run random value 1..8
schedule function og:bm/loop 20t replace
