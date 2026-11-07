# Blood Siphon: run as the player who used it, at them
advancement revoke @s only og:item/siphon
tag @s add og.caster
execute at @s run execute store result score #n og_i if entity @e[distance=..5,type=!#og:not_target,tag=!og.caster]
execute at @s run execute as @e[distance=..5,type=!#og:not_target,tag=!og.caster] at @s run damage @s 4 minecraft:magic by @p[tag=og.caster]
execute at @s run execute as @e[distance=..5,type=!#og:not_target,tag=!og.caster] at @s run particle minecraft:damage_indicator ~ ~1 ~ 0.3 0.5 0.3 0.1 6
execute at @s run execute if score #n og_i matches 1.. run effect give @s minecraft:instant_health 1 0 true
execute at @s run execute if score #n og_i matches 3.. run effect give @s minecraft:regeneration 5 1 true
execute at @s run particle minecraft:dust{color:[0.6,0.0,0.0],scale:1.5} ~ ~1 ~ 2.5 0.8 2.5 0 120
execute at @s run playsound minecraft:entity.warden.heartbeat player @a[distance=..24] ~ ~ ~ 1 1.2
execute at @s run playsound minecraft:entity.vex.charge player @a[distance=..24] ~ ~ ~ 1 0.6
execute at @s run title @s actionbar {"text":"◆ BLOOD SIPHON","color":"dark_red","bold":true}
tag @s remove og.caster
