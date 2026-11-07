# Shrink Potion: run as the player who used it, at them
advancement revoke @s only og:item/shrink
tag @s add og.caster
execute at @s run function og:item/size_shrink
tag @s remove og.caster
