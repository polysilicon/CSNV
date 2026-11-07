# Growth Potion: run as the player who used it, at them
advancement revoke @s only og:item/grow
tag @s add og.caster
execute at @s run function og:item/size_grow
tag @s remove og.caster
