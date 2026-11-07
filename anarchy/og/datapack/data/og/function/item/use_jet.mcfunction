# Jump Jet: run as the player who used it, at them
advancement revoke @s only og:item/jet
tag @s add og.caster
execute at @s run summon minecraft:wind_charge ~ ~0.1 ~ {Motion:[0.0d,-1.0d,0.0d]}
execute at @s run effect give @s minecraft:slow_falling 5 0 true
execute at @s run particle minecraft:cloud ~ ~0.2 ~ 0.4 0.1 0.4 0.05 20
execute at @s run playsound minecraft:entity.breeze.jump player @a[distance=..24] ~ ~ ~ 1 1.2
tag @s remove og.caster
