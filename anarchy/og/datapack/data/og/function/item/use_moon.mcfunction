# Moon Juice: run as the player who used it, at them
advancement revoke @s only og:item/moon
tag @s add og.caster
execute at @s run function og:item/size_moon
tag @s remove og.caster
