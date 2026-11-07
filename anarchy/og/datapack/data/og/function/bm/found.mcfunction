# the dealer appears beside the finder for a moment, pays out, and is gone; then the market moves
scoreboard players reset @s bm_sneak
execute at @s run summon minecraft:wandering_trader ^ ^ ^1 {Tags:["bm_npc"],NoAI:1b,Invulnerable:1b,Silent:1b,PersistenceRequired:1b,DespawnDelay:200,CustomNameVisible:1b,CustomName:{text:"???",color:"dark_gray",italic:true},Offers:{Recipes:[]}}
execute at @s run particle minecraft:large_smoke ^ ^1 ^1 0.4 0.8 0.4 0.01 40
playsound minecraft:entity.wandering_trader.reappeared neutral @s ~ ~ ~ 1 0.7
tellraw @s [{"text":"??? ","color":"dark_gray","italic":true},{"text":"whispers: ","color":"gray","italic":true},{"text":"You didn't find me. Take this, and tell no one. I won't be here tomorrow.","color":"white","italic":true}]
loot give @s loot og:black_market
advancement grant @s only anarchy:black_market
# unlock and wear [Black Market] at once (chat-tags mod -> lobby), not when the advancement file next saves
crispytag award blackmarket
function og:bm/move
schedule function og:bm/vanish 5s replace
