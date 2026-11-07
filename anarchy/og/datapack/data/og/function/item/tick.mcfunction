# every tick (schedules itself; started by og:load): splash brews in flight
execute as @e[type=minecraft:splash_potion,tag=!og.sp] at @s run function og:item/sp_new
execute as @e[type=minecraft:marker,tag=og.spm] at @s run function og:item/sp_follow
schedule function og:item/tick 1t replace
