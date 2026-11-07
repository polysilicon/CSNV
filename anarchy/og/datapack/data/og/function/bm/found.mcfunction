# the dealer appears for this one moment, pays out, and is gone again
scoreboard players reset @s bm_sneak
summon minecraft:wandering_trader -106.5 99 -75.5 {Tags:["bm_npc"],NoAI:1b,Invulnerable:1b,Silent:1b,PersistenceRequired:1b,DespawnDelay:200,Rotation:[180f,0f],CustomNameVisible:1b,CustomName:{text:"???",color:"dark_gray",italic:true},Offers:{Recipes:[]}}
particle minecraft:large_smoke -106.5 100 -75.5 0.4 0.8 0.4 0.01 40
playsound minecraft:entity.wandering_trader.reappeared neutral @s ~ ~ ~ 1 0.7
tellraw @s [{"text":"??? ","color":"dark_gray","italic":true},{"text":"whispers: ","color":"gray","italic":true},{"text":"You didn't find me. Take this, and tell no one.","color":"white","italic":true}]
loot give @s loot og:black_market
advancement grant @s only anarchy:black_market
tellraw @s [{"text":"You unlocked the ","color":"gray"},{"text":"[Black Market]","color":"dark_gray","bold":true},{"text":" tag: wear it in /cosmetics to trade with the Black Market Dealer outside the bank.","color":"gray"}]
schedule function og:bm/vanish 5s replace
