# an ability that had nothing to do gives its charge back (and returns early, so the caster tag goes here)
$loot give @s loot og:item/$(k)
$title @s actionbar {"text":"$(what)","color":"gray"}
playsound minecraft:block.dispenser.fail player @s ~ ~ ~ 1 1.2
tag @s remove og.caster
