"""Black Market contraband: ability items and size potions, and the dealer's trade list (python3 gen_items.py).

Writes og:place (the dealer and his trades), the items' advancements and functions, og:give_all (ops: one of each)
and adds a few of them to the hidden dealer's loot table.

Ability items work like Multiverse's: right-click and it fires, with a cooldown the client shows. Here each use spends
one charge from the stack (they're sold in stacks), so they stay something you buy, not something you own forever.
- The item is a clay ball with an item_model, a near-instant `consumable` and a `use_cooldown`.
- Using one fires its consume_item advancement (og:item/<key>, matched on custom_data {bm:"<key>"}), whose reward
  revokes it and runs og:item/<key> as the user, tagged og.caster.
- Targets: every living thing near the user except the user and shopkeepers (entity tag og:not_target).

Size potions (drink): Growth (2x size, +4 hearts, +1.5 reach) and Shrink (0.35x size: through 1-block gaps, a much
smaller target) for 3 minutes. Both use the attribute modifier og:size; drinking one replaces the other. og:item/second
counts the time down and puts you back to normal when it's up or when you die.
"""
import json
import os

D = "datapack/data/"
F = D + "og/function/"
for p in ("og/function/item", "og/advancement/item", "og/tags/entity_type", "og/tags/block"):
    os.makedirs(D + p, exist_ok=True)

COIN = ('{id:"minecraft:sunflower",count:%d,components:{"minecraft:custom_name":{text:"Gold Coin",italic:false,color:"gold",bold:true},'
        '"minecraft:lore":[{text:" -Used for special shop items",italic:false,color:"dark_purple"}],"minecraft:enchantments":{"minecraft:unbreaking":1}}}')
TAG_LINE = '{text:"Crispy Anarchy · Black Market",italic:false,color:"dark_gray"}'
TGT = "type=!#og:not_target,tag=!og.caster"
BY = "by @p[tag=og.caster]"


def txt(s, color="gray", **kw):
    d = {"text": s, "italic": False, "color": color, **kw}
    return "{" + ",".join(f"{k}:{json.dumps(v) if isinstance(v, str) else str(v).lower()}" for k, v in d.items()) + "}"


def around(r, cmd): return f"execute as @e[distance=..{r},{TGT}] at @s run {cmd}"
def snd(s, vol=1, pitch=1): return f"playsound minecraft:{s} player @a[distance=..24] ~ ~ ~ {vol} {pitch}"
def bar(t, c): return f'title @s actionbar {{"text":"◆ {t}","color":"{c}","bold":true}}'


# key: (name, colour, item model, cooldown s, lore lines, effect commands, (stack, price))
ABILITIES = {
    "blink": ("Phase Shard", "light_purple", "amethyst_shard", 4,
              ["Right-click: blink up to 10 blocks where you look.", "Stops at walls, never through them."], [
                  "particle minecraft:reverse_portal ~ ~1 ~ 0.3 0.6 0.3 0.05 40",
                  "scoreboard players set #b og_i 20", "execute rotated as @s run function og:item/blink_ray",
                  "execute at @s run particle minecraft:reverse_portal ~ ~1 ~ 0.3 0.6 0.3 0.05 40",
                  "execute at @s run " + snd("entity.enderman.teleport", 0.8, 1.4)], (8, 6)),
    "jet": ("Jump Jet", "aqua", "breeze_rod", 6,
            ["Right-click: launches you high into the air.", "Slow Falling 5 s to land."], [
                "summon minecraft:wind_charge ~ ~0.1 ~ {Motion:[0.0d,-1.0d,0.0d]}",
                "effect give @s minecraft:slow_falling 5 0 true",
                "particle minecraft:cloud ~ ~0.2 ~ 0.4 0.1 0.4 0.05 20", snd("entity.breeze.jump", 1, 1.2)], (8, 4)),
    "smoke": ("Smoke Bomb", "dark_gray", "gunpowder", 20,
              ["Right-click: a cloud of smoke around you.", "Everyone within 6 blocks: Blindness + Slowness 4 s",
               "You: Invisibility + Speed II 6 s"], [
                  around(6, "effect give @s minecraft:blindness 4 0"), around(6, "effect give @s minecraft:slowness 4 0"),
                  "effect give @s minecraft:invisibility 6 0 true", "effect give @s minecraft:speed 6 1 true",
                  "particle minecraft:campfire_cosy_smoke ~ ~1 ~ 2.5 1.2 2.5 0.01 160",
                  "particle minecraft:large_smoke ~ ~1 ~ 2 1 2 0.02 80", snd("entity.generic.extinguish_fire", 1, 0.6),
                  bar("SMOKE BOMB", "gray")], (4, 6)),
    "tesla": ("Tesla Coil", "yellow", "lightning_rod", 15,
              ["Right-click: shocks everything around you.", "5 blocks · 6 damage · Slowness II 3 s"], [
                  around(5, f"damage @s 6 minecraft:lightning_bolt {BY}"),
                  around(5, "effect give @s minecraft:slowness 3 1"),
                  around(5, "particle minecraft:electric_spark ~ ~1 ~ 0.3 0.6 0.3 0.3 30"),
                  "particle minecraft:electric_spark ~ ~1 ~ 2.5 1 2.5 0.4 120",
                  snd("entity.lightning_bolt.thunder", 0.3, 2), snd("block.respawn_anchor.deplete", 0.8, 1.6),
                  bar("TESLA COIL", "yellow")], (4, 8)),
    "gravity": ("Gravity Bomb", "dark_purple", "heavy_core", 20,
                ["Right-click: everyone within 6 blocks floats", "helplessly into the air for 3 s, then drops."], [
                    around(6, "effect give @s minecraft:levitation 3 2"),
                    around(6, "particle minecraft:portal ~ ~0.5 ~ 0.3 0.3 0.3 0.5 20"),
                    "particle minecraft:reverse_portal ~ ~1 ~ 3 0.5 3 0.05 120",
                    snd("block.beacon.deactivate", 1, 0.5), snd("entity.shulker.shoot", 1, 0.6),
                    bar("GRAVITY BOMB", "dark_purple")], (4, 8)),
    "snare": ("Snare Dart", "green", "prismarine_shard", 8,
              ["Right-click: fires a dart at what you aim at.", "24 blocks · 3 damage · Slowness IV 3 s · Glowing 8 s"], [
                  "scoreboard players set #b og_i 48",
                  "execute anchored eyes positioned ^ ^ ^ rotated as @s run function og:item/snare_ray",
                  "execute as @e[tag=og.hit] at @s run function og:item/snare_hit",
                  "tag @e[tag=og.hit] remove og.hit", snd("entity.arrow.shoot", 1, 1.6)], (8, 6)),
    "stim": ("Stim Shot", "red", "ghast_tear", 30,
             ["Right-click: heals you right away.", "Instant Health II · Regeneration II 6 s · Absorption 30 s"], [
                 "effect give @s minecraft:instant_health 1 1 true", "effect give @s minecraft:regeneration 6 1 true",
                 "effect give @s minecraft:absorption 30 0 true",
                 "particle minecraft:heart ~ ~1.8 ~ 0.4 0.3 0.4 0 6", snd("item.honey_bottle.drink", 1, 1.4),
                 bar("STIM SHOT", "red")], (4, 6)),
    "swap": ("Swap Orb", "dark_aqua", "ender_eye", 12,
             ["Right-click: trade places with what you aim at.", "24 blocks · players and mobs"], [
                 "scoreboard players set #b og_i 48",
                 "execute anchored eyes positioned ^ ^ ^ rotated as @s run function og:item/swap_ray",
                 "execute unless entity @e[tag=og.hit] run return run function og:item/refund {k:\"swap\",what:\"Nothing to swap with\"}",
                 "execute as @e[tag=og.hit] at @s run summon minecraft:marker ~ ~ ~ {Tags:[\"og.swp\"]}",
                 "tp @e[tag=og.hit] ~ ~ ~", "execute at @n[type=minecraft:marker,tag=og.swp] run tp @s ~ ~ ~",
                 "kill @e[type=minecraft:marker,tag=og.swp]",
                 "execute at @e[tag=og.hit] run particle minecraft:reverse_portal ~ ~1 ~ 0.3 0.6 0.3 0.05 40",
                 "execute at @s run particle minecraft:reverse_portal ~ ~1 ~ 0.3 0.6 0.3 0.05 40",
                 "tag @e[tag=og.hit] remove og.hit", snd("entity.shulker.teleport", 1, 1.2), bar("SWAPPED", "dark_aqua")], (4, 8)),
    "chrono": ("Chrono Clock", "gold", "clock", 25,
               ["Right-click: rewind to where you stood 5 seconds ago.", "Same dimension only"], [
                   "execute unless score @s og_hn matches 5.. run return run function og:item/refund {k:\"chrono\",what:\"The clock needs 5 seconds in this dimension to wind\"}",
                   "particle minecraft:totem_of_undying ~ ~1 ~ 0.3 0.6 0.3 0.3 30",
                   "execute store result storage og:t x double 0.01 run scoreboard players get @s og_x4",
                   "execute store result storage og:t y double 0.01 run scoreboard players get @s og_y4",
                   "execute store result storage og:t z double 0.01 run scoreboard players get @s og_z4",
                   "function og:item/chrono_tp with storage og:t", "scoreboard players set @s og_hn 0",
                   "execute at @s run particle minecraft:totem_of_undying ~ ~1 ~ 0.3 0.6 0.3 0.3 30",
                   "execute at @s run " + snd("block.bell.resonate", 1, 1.6), bar("REWOUND", "gold")], (4, 8)),
    "frost": ("Frost Nova", "aqua", "blue_ice", 18,
              ["Right-click: a blast of cold freezes everyone around you.", "6 blocks · 3 damage · Slowness V + Mining Fatigue III 4 s"], [
                  around(6, f"damage @s 3 minecraft:freeze {BY}"), around(6, "effect give @s minecraft:slowness 4 4"),
                  around(6, "effect give @s minecraft:mining_fatigue 4 2"),
                  around(6, "particle minecraft:snowflake ~ ~1 ~ 0.3 0.6 0.3 0.05 30"),
                  "particle minecraft:snowflake ~ ~1 ~ 3 0.8 3 0.05 200", snd("block.glass.break", 1, 0.6),
                  snd("entity.player.hurt_freeze", 1, 0.8), bar("FROST NOVA", "aqua")], (4, 6)),
    "siphon": ("Blood Siphon", "dark_red", "fermented_spider_eye", 20,
               ["Right-click: drains everyone within 5 blocks.", "4 damage each · heals you 2 hearts, more with 3+ hit"], [
                   f"execute store result score #n og_i if entity @e[distance=..5,{TGT}]",
                   around(5, f"damage @s 4 minecraft:magic {BY}"),
                   around(5, "particle minecraft:damage_indicator ~ ~1 ~ 0.3 0.5 0.3 0.1 6"),
                   "execute if score #n og_i matches 1.. run effect give @s minecraft:instant_health 1 0 true",
                   "execute if score #n og_i matches 3.. run effect give @s minecraft:regeneration 5 1 true",
                   "particle minecraft:dust{color:[0.6,0.0,0.0],scale:1.5} ~ ~1 ~ 2.5 0.8 2.5 0 120",
                   snd("entity.warden.heartbeat", 1, 1.2), snd("entity.vex.charge", 1, 0.6), bar("BLOOD SIPHON", "dark_red")], (4, 8)),
}

POTIONS = {   # key: (name, colour, rgb, lore, attribute modifiers, sound, (count, price)); one brew at a time
    "grow": ("Growth Potion", "green", 0x3FD14A, ["Drink: grow to twice your size for 3 minutes.", "+4 hearts · +1.5 blocks reach"],
             [("scale", 1.0), ("max_health", 8), ("entity_interaction_range", 1.5), ("block_interaction_range", 1.5)],
             ("block.beacon.power_select", 0.6), (2, 6)),
    "shrink": ("Shrink Potion", "light_purple", 0xB45CFF, ["Drink: shrink to a third of your size for 3 minutes.",
                                                           "Fit through 1-block gaps · far harder to hit"],
               [("scale", -0.65)], ("entity.illusioner.mirror_move", 1.6), (2, 6)),
    "moon": ("Moon Juice", "white", 0xD8E0F0, ["Drink: low gravity for 3 minutes.", "Huge, floaty jumps · no fall damage"],
             [("gravity", -0.06), ("jump_strength", 0.15), ("safe_fall_distance", 256)], ("block.amethyst_block.resonate", 0.8), (2, 6)),
    "normal": ("Restoring Draught", "gray", 0x9AA3AD, ["Drink: back to your normal size and self.", "Ends any Black Market brew right away"],
               [], ("block.beacon.deactivate", 1.2), (2, 2)),
}
SIZE_SECONDS = 180
MODS = sorted({a for p in POTIONS.values() for a, _ in p[4]})


def ability_item(k, count):
    name, color, model, cd, lore, _, _ = ABILITIES[k]
    return (f'{{id:"minecraft:clay_ball",count:{count},components:{{"minecraft:item_model":"minecraft:{model}",'
            f'"minecraft:custom_data":{{bm:"{k}"}},"minecraft:item_name":{txt(name, color, bold=True)},'
            f'"minecraft:lore":[{",".join(txt(l) for l in lore)},{txt("Each use spends one charge · " + str(cd) + " s cooldown", "dark_gray")},{TAG_LINE}],'
            f'"minecraft:max_stack_size":16,"minecraft:enchantment_glint_override":true,'
            f'"minecraft:consumable":{{consume_seconds:0.05f,animation:"none",has_consume_particles:false,sound:"minecraft:intentionally_empty"}},'
            f'"minecraft:use_cooldown":{{seconds:{cd}f,cooldown_group:"og:{k}"}}}}}}')


def potion_item(k, count):
    name, color, rgb, lore, *_ = POTIONS[k]
    return (f'{{id:"minecraft:potion",count:{count},components:{{"minecraft:custom_data":{{bm:"{k}"}},'
            f'"minecraft:custom_name":{txt(name, color, bold=True)},"minecraft:potion_contents":{{custom_color:{rgb}}},'
            f'"minecraft:lore":[{",".join(txt(l) for l in lore)},{TAG_LINE}],"minecraft:max_stack_size":4}}}}')


def trade(price, sell):
    return (f'{{buy:{COIN % price},sell:{sell},maxUses:2147483647,uses:0,rewardExp:false,xp:0,'
            f'priceMultiplier:0.0f,demand:0,specialPrice:0}}')


# ------------------------------------------------------------------ the items' advancements and functions
w = lambda path, lines: open(path, "w").write("\n".join(lines) + "\n")
for k, (name, *_rest) in {**ABILITIES, **POTIONS}.items():
    base = "minecraft:clay_ball" if k in ABILITIES else "minecraft:potion"
    json.dump({"criteria": {"used": {"trigger": "minecraft:consume_item", "conditions": {
        "item": {"items": base, "predicates": {"minecraft:custom_data": f'{{bm:"{k}"}}'}}}}},
        "rewards": {"function": f"og:item/use_{k}"}}, open(f"{D}og/advancement/item/{k}.json", "w"), indent=1)
    body = ABILITIES[k][5] if k in ABILITIES else [f"function og:item/size_{k}"]
    w(f"{F}item/use_{k}.mcfunction", [f"# {name}: run as the player who used it, at them",
                                      f"advancement revoke @s only og:item/{k}", "tag @s add og.caster",
                                      *[f"execute at @s run {c}" for c in body], "tag @s remove og.caster"])

w(f"{F}item/blink_ray.mcfunction", [
    "# Phase Shard: half a block at a time along the look; stop where the feet or head would be inside a block",
    "scoreboard players remove #b og_i 1",
    "execute positioned ^ ^ ^0.5 unless block ~ ~ ~ #og:passable run return 0",
    "execute positioned ^ ^ ^0.5 unless block ~ ~1 ~ #og:passable run return 0",
    "execute positioned ^ ^ ^0.5 run tp @s ~ ~ ~",
    "execute if score #b og_i matches 1.. positioned ^ ^ ^0.5 run function og:item/blink_ray"])
w(f"{F}item/snare_ray.mcfunction", [
    "# Snare Dart: half a block at a time from the eyes; the first target within 0.8 gets og.hit, a wall stops it",
    "scoreboard players remove #b og_i 1",
    "particle minecraft:happy_villager ~ ~ ~ 0 0 0 0 1",
    f"execute positioned ~-0.5 ~-0.5 ~-0.5 as @e[{TGT},dx=0,dy=0,dz=0,limit=1] run tag @s add og.hit",
    "execute if entity @e[tag=og.hit] run return 0",
    "execute unless block ~ ~ ~ #og:passable run return 0",
    "execute if score #b og_i matches 1.. positioned ^ ^ ^0.5 run function og:item/snare_ray"])
w(f"{F}item/swap_ray.mcfunction", [
    "# Swap Orb: like the Snare Dart's ray, with portal sparks",
    "scoreboard players remove #b og_i 1",
    "particle minecraft:portal ~ ~ ~ 0 0 0 0 1",
    f"execute positioned ~-0.5 ~-0.5 ~-0.5 as @e[{TGT},dx=0,dy=0,dz=0,limit=1] run tag @s add og.hit",
    "execute if entity @e[tag=og.hit] run return 0",
    "execute unless block ~ ~ ~ #og:passable run return 0",
    "execute if score #b og_i matches 1.. positioned ^ ^ ^0.5 run function og:item/swap_ray"])
w(f"{F}item/refund.mcfunction", [
    "# an ability that had nothing to do gives its charge back (and returns early, so the caster tag goes here)",
    "$loot give @s loot og:item/$(k)", "$title @s actionbar {\"text\":\"$(what)\",\"color\":\"gray\"}",
    "playsound minecraft:block.dispenser.fail player @s ~ ~ ~ 1 1.2", "tag @s remove og.caster"])
w(f"{F}item/chrono_tp.mcfunction", ["$tp @s $(x) $(y) $(z)"])
w(f"{F}item/history.mcfunction", [
    "# Chrono Clock: where each player stood the last 5 seconds (x100), oldest in slot 4. og_hn counts good samples",
    *[f"scoreboard players operation @s og_{c}{i} = @s og_{c}{i - 1}" for i in range(4, 0, -1) for c in "xyz"],
    *[f"execute store result score @s og_{c}0 run data get entity @s Pos[{n}] 100" for n, c in enumerate("xyz")],
    "scoreboard players add @s og_hn 1"])
json.dump({"criteria": {"moved": {"trigger": "minecraft:changed_dimension"}}, "rewards": {"function": "og:item/dim"}},
          open(f"{D}og/advancement/item/dim.json", "w"), indent=1)
w(f"{F}item/dim.mcfunction", ["advancement revoke @s only og:item/dim", "scoreboard players set @s og_hn 0"])
w(f"{F}item/snare_hit.mcfunction", [
    f"damage @s 3 minecraft:arrow {BY}", "effect give @s minecraft:slowness 3 3", "effect give @s minecraft:glowing 8 0",
    "particle minecraft:item_slime ~ ~1 ~ 0.3 0.5 0.3 0.1 20", snd("entity.slime.squish", 1, 1.4)])

for k, (name, color, rgb, lore, mods, (sound, pitch), _) in POTIONS.items():
    if not mods:   # the Restoring Draught: just ends whatever brew you're on
        w(f"{F}item/size_{k}.mcfunction", [f"# {name}: back to normal", "function og:item/size_reset",
                                           "particle minecraft:effect ~ ~1 ~ 0.5 1 0.5 0.1 40", snd(sound, 1, pitch),
                                           f'title @s actionbar {{"text":"◆ BACK TO NORMAL","color":"{color}","bold":true}}'])
        continue
    w(f"{F}item/size_{k}.mcfunction", [
        f"# {name}: replaces any brew you already had, for {SIZE_SECONDS} s",
        "function og:item/size_reset",
        *[f"attribute @s minecraft:{a} modifier add og:size {v} add_value" for a, v in mods],
        f"scoreboard players set @s og_size {SIZE_SECONDS}", "tag @s add og.sized",
        "particle minecraft:effect ~ ~1 ~ 0.5 1 0.5 0.1 40", snd(sound, 1, pitch),
        f'title @s actionbar {{"text":"◆ {name.upper()} · 3 minutes","color":"{color}","bold":true}}'])
w(f"{F}item/size_reset.mcfunction", [f"attribute @s minecraft:{a} modifier remove og:size" for a in MODS]
  + ["scoreboard players reset @s og_size", "tag @s remove og.sized"])
w(f"{F}item/second.mcfunction", [
    "# once a second (og:bm/loop): brews run out, and dying ends them; the Chrono Clock's position history",
    "scoreboard players remove @a[tag=og.sized] og_size 1",
    'title @a[tag=og.sized,scores={og_size=10}] actionbar {"text":"◆ Your brew wears off in 10 s","color":"gray"}',
    "execute as @a[tag=og.sized,scores={og_died=1..}] run function og:item/size_reset",
    "execute as @a[tag=og.sized] unless score @s og_size matches 1.. run function og:item/size_reset",
    "execute as @a[scores={og_died=1..}] run scoreboard players set @s og_hn 0",
    "scoreboard players reset @a og_died",
    "execute as @a[gamemode=!spectator] run function og:item/history"])
gives = []
for k in ABILITIES:
    gives.append(f"loot give @s loot og:item/{k}")
for k in POTIONS:
    gives.append(f"loot give @s loot og:item/{k}")
w(f"{F}give_all.mcfunction", ["# ops: one of every Black Market contraband item, to test"] + gives)

json.dump({"values": ["#minecraft:air", "#minecraft:replaceable", "#minecraft:flowers", "#minecraft:saplings",
                      "#minecraft:wool_carpets", "#minecraft:buttons", "#minecraft:pressure_plates", "#minecraft:rails",
                      "#minecraft:all_signs", "#minecraft:banners", "minecraft:torch", "minecraft:wall_torch",
                      "minecraft:soul_torch", "minecraft:soul_wall_torch", "minecraft:redstone_torch",
                      "minecraft:redstone_wall_torch", "minecraft:lever", "minecraft:ladder", "minecraft:vine",
                      "minecraft:redstone_wire", "minecraft:tripwire", "minecraft:light"]},
          open(f"{D}og/tags/block/passable.json", "w"), indent=1)
json.dump({"values": [f"minecraft:{t}" for t in [
    "item", "marker", "interaction", "text_display", "block_display", "item_display", "armor_stand", "mannequin",
    "villager", "wandering_trader", "experience_orb", "arrow", "spectral_arrow", "trident", "wind_charge",
    "breeze_wind_charge", "fireball", "small_fireball", "snowball", "tnt", "falling_block", "lightning_bolt",
    "area_effect_cloud", "ender_pearl", "splash_potion", "lingering_potion", "firework_rocket", "end_crystal", "egg",
    "experience_bottle", "item_frame", "glow_item_frame", "painting", "leash_knot"]]},
    open(f"{D}og/tags/entity_type/not_target.json", "w"), indent=1)


# ------------------------------------------------------------------ loot tables (one item each, for give_all and the dealer's loot)
def loot_entry(k, count, weight=None):
    if k in ABILITIES:
        name, color, model, cd, lore, _, _ = ABILITIES[k]
        comps = {"minecraft:item_model": f"minecraft:{model}", "minecraft:custom_data": {"bm": k},
                 "minecraft:item_name": {"text": name, "color": color, "bold": True, "italic": False},
                 "minecraft:lore": [{"text": l, "color": "gray", "italic": False} for l in lore]
                 + [{"text": f"Each use spends one charge · {cd} s cooldown", "color": "dark_gray", "italic": False},
                    {"text": "Crispy Anarchy · Black Market", "color": "dark_gray", "italic": False}],
                 "minecraft:max_stack_size": 16, "minecraft:enchantment_glint_override": True,
                 "minecraft:consumable": {"consume_seconds": 0.05, "animation": "none", "has_consume_particles": False,
                                          "sound": "minecraft:intentionally_empty"},
                 "minecraft:use_cooldown": {"seconds": float(cd), "cooldown_group": f"og:{k}"}}
        base = "minecraft:clay_ball"
    else:
        name, color, rgb, lore, *_ = POTIONS[k]
        comps = {"minecraft:custom_data": {"bm": k},
                 "minecraft:custom_name": {"text": name, "color": color, "bold": True, "italic": False},
                 "minecraft:potion_contents": {"custom_color": rgb},
                 "minecraft:lore": [{"text": l, "color": "gray", "italic": False} for l in lore]
                 + [{"text": "Crispy Anarchy · Black Market", "color": "dark_gray", "italic": False}],
                 "minecraft:max_stack_size": 4}
        base = "minecraft:potion"
    e = {"type": "minecraft:item", "name": base, "functions": [
        {"function": "minecraft:set_components", "components": comps},
        {"function": "minecraft:set_count", "count": count}]}
    if weight: e["weight"] = weight
    return e


os.makedirs(f"{D}og/loot_table/item", exist_ok=True)
for k in {**ABILITIES, **POTIONS}:
    json.dump({"type": "minecraft:command", "pools": [{"rolls": 1, "entries": [loot_entry(k, 1)]}]},
              open(f"{D}og/loot_table/item/{k}.json", "w"), indent=1)

# the hidden dealer's once-per-player gift: one random stack of contraband
U = lambda lo, hi: {"type": "minecraft:uniform", "min": lo, "max": hi}
json.dump({"type": "minecraft:chest", "pools": [{"rolls": 1, "entries": [
    loot_entry("blink", U(4, 8), 10), loot_entry("jet", U(4, 8), 10), loot_entry("stim", U(2, 4), 10),
    loot_entry("smoke", U(2, 4), 8), loot_entry("snare", U(4, 8), 8), loot_entry("frost", U(2, 3), 8),
    loot_entry("tesla", 2, 6), loot_entry("gravity", 2, 6), loot_entry("siphon", 2, 6), loot_entry("swap", 2, 6),
    loot_entry("chrono", 2, 6), loot_entry("grow", 2, 6), loot_entry("shrink", 2, 6), loot_entry("moon", 2, 6),
    loot_entry("normal", 2, 6)]}]}, open(f"{D}og/loot_table/black_market.json", "w"), indent=1)

# ------------------------------------------------------------------ the dealer
TRADES = ([trade(price, ability_item(k, n)) for k, (*_, (n, price)) in ABILITIES.items()]
          + [trade(price, potion_item(k, n)) for k, (*_, (n, price)) in POTIONS.items()]
)
w(F + "place.mcfunction", [
    "# /function og:place (ops, on Anarchy): put the Black Market Dealer in the market, on the street outside the bank's door.",
    "# Written by gen_items.py. Tagged crispy_shop (or the market moves it out) and needtag.blackmarket (only players wearing",
    "# [Black Market] can trade). The market's own spawn_shops/reinstall kills crispy_shop villagers, so run this again after one.",
    "execute in crispy:market run forceload add -112 -80 -96 -60",
    "execute in crispy:market run forceload add -64 56 -40 80",
    "execute in crispy:market run kill @e[tag=crispy_ogshop]",
    "execute in crispy:market run forceload remove -64 56 -40 80",
    "execute in crispy:market run summon minecraft:villager -102.5 95 -68.5 {Tags:[\"crispy_shop\",\"crispy_ogshop\",\"needtag.blackmarket\"],"
    "NoAI:true,Invulnerable:true,PersistenceRequired:true,Silent:true,CanPickUpLoot:false,CustomNameVisible:true,Rotation:[180f,0f],Xp:250,"
    "CustomName:{text:\"Black Market Dealer\",color:\"dark_gray\",bold:true,italic:false},"
    "VillagerData:{profession:\"minecraft:weaponsmith\",type:\"minecraft:plains\",level:5},Offers:{Recipes:[" + ",".join(TRADES) + "]}}",
    "execute in crispy:market run summon minecraft:text_display -102.5 97.6 -68.5 {Tags:[\"crispy_ogshop\"],billboard:\"center\","
    "text:{text:\"Only for players wearing \",color:\"gray\",extra:[{text:\"[Black Market]\",color:\"dark_gray\",bold:true}]}}",
    "execute in crispy:market run forceload remove -112 -80 -96 -60"])
print(len(ABILITIES), "abilities,", len(POTIONS), "potions,", len(TRADES), "trades")
