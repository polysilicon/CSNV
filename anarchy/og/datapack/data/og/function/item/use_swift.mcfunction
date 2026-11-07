# Swiftfoot Tonic: run as the player who used it, at them
advancement revoke @s only og:item/swift
tag @s add og.caster
execute at @s run function og:item/size_swift
tag @s remove og.caster
