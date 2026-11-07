# Restoring Draught: run as the player who used it, at them
advancement revoke @s only og:item/normal
tag @s add og.caster
execute at @s run function og:item/size_normal
tag @s remove og.caster
