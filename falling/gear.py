"""Crafted armor sets and weapons for crispy_skyblock (imported by skyblock.py), Hypixel style but vanilla.

- Everything is crafted at a crafting table from things players farm: compacted blocks (hay bales, lapis, kelp, magma,
  purpur...) and, for the top tiers, boss loot (shulker shells, dragon's breath, netherite). The recipes are unlocked in
  every player's recipe book, and /gear (or Island Menu > Armor & Weapons) lists them all with their recipes.
- Items carry vanilla enchantments, enchantments from the crispy_enchants datapack (installed on Skyblock too), stats as
  attribute modifiers, and custom_data: {cs_set:"<set>"} on armor, {cs_ability:"<key>", cs_cd:<ticks>} on weapons.
- Full set bonuses: once a second each player wearing all four pieces of a set gets its effects (gear/bonus).
- Abilities: right-clicking an item with cs_ability makes the mod (Gear.java) run gear/ab/<key> as and at the player
  and start the item's cooldown. Abilities only hit mobs in #crispy_skyblock:gear_targets (never players, villagers or
  pets), and none of them set fire to or break blocks.
"""

RARITY = {"UNCOMMON": "green", "RARE": "blue", "EPIC": "dark_purple", "LEGENDARY": "gold"}
PIECES = [  # slot, vanilla piece suffix, armor slot name, recipe pattern (# = main block, C = core item)
    ("head", "helmet", "Helmet", ["#C#", "# #"]),
    ("chest", "chestplate", "Chestplate", ["# #", "#C#", "###"]),
    ("legs", "leggings", "Leggings", ["#C#", "# #", "# #"]),
    ("feet", "boots", "Boots", ["# #", "C C"]),
]
SLOT_ARMOR = {"head": "helmet", "chest": "chestplate", "legs": "leggings", "feet": "boots"}

# key, name, rarity, base material (leather/iron/netherite...), dye colour or trim, main block, core item,
# armor per piece [h, c, l, b], toughness per piece, extra attributes on every piece, enchants per slot,
# bonus name, bonus text lines, bonus commands (run as the player once a second)
SETS = [
    ("farm", "Farm Suit", "UNCOMMON", "leather", 0xE6C13E, "hay_block", "wheat",
     [2, 4, 3, 2], 0, {"movement_speed": ("add_multiplied_base", 0.03)},
     {"chest": {"crispy_enchants:sustain": 2}, "feet": {"crispy_enchants:gears": 1}},
     "Bountiful Harvest", ["Speed I and Haste I."],
     ["effect give @s minecraft:speed 3 0 true", "effect give @s minecraft:haste 3 0 true"]),
    ("mushroom", "Mushroom Armor", "UNCOMMON", "leather", 0xB02E26, "red_mushroom_block", "brown_mushroom",
     [2, 4, 3, 2], 0, {"max_health": ("add_value", 1.0)},
     {"head": {"crispy_enchants:glowing": 1}},
     "Night Stalker", ["At night: Strength I and", "Regeneration I."],
     ["execute store result score #tod cs_tmp run time query minecraft:day",
      "execute if score #tod cs_tmp matches 13000..23000 run effect give @s minecraft:strength 3 0 true",
      "execute if score #tod cs_tmp matches 13000..23000 run effect give @s minecraft:regeneration 3 0 true"]),
    ("cactus", "Cactus Armor", "UNCOMMON", "leather", 0x3E7A1E, "cactus", "green_dye",
     [2, 4, 3, 2], 0, {},
     {"head": {"crispy_enchants:cactus": 1}, "chest": {"crispy_enchants:cactus": 2}, "legs": {"crispy_enchants:cactus": 1},
      "feet": {"crispy_enchants:cactus": 1}},
     "Desert Bloom", ["Regeneration I while standing", "on sand. Attackers get pricked."],
     ["execute if block ~ ~-0.5 ~ #minecraft:sand run effect give @s minecraft:regeneration 3 0 true"]),
    ("pumpkin", "Pumpkin Armor", "UNCOMMON", "leather", 0xE38A1D, "pumpkin", "jack_o_lantern",
     [2, 5, 4, 2], 0, {"max_health": ("add_value", 1.0)},
     {"chest": {"crispy_enchants:hardened": 1}},
     "Squash Buckler", ["Resistance I: you take", "20% less damage."],
     ["effect give @s minecraft:resistance 3 0 true"]),
    ("angler", "Angler Armor", "UNCOMMON", "leather", 0x2B8C8C, "dried_kelp_block", "cod",
     [2, 4, 3, 2], 0, {"oxygen_bonus": ("add_value", 1.0)},
     {"head": {"crispy_enchants:aquatic": 1, "minecraft:respiration": 3}, "feet": {"minecraft:depth_strider": 3}},
     "Deep Sea Diver", ["Water Breathing, Dolphin's Grace", "and Luck II (better fishing loot)."],
     ["effect give @s minecraft:water_breathing 3 0 true", "effect give @s minecraft:dolphins_grace 3 0 true",
      "effect give @s minecraft:luck 3 1 true"]),
    ("lapis", "Lapis Armor", "RARE", "leather", 0x1E3FAD, "lapis_block", "diamond",
     [3, 6, 5, 2], 0, {"max_health": ("add_value", 2.0)},
     {"head": {"crispy_enchants:implants": 1}, "chest": {"minecraft:protection": 2}},
     "Deep Core", ["+4 hearts and Luck II.", "Each piece gives +1 heart too."],
     ["effect give @s minecraft:health_boost 3 1 true", "effect give @s minecraft:luck 3 1 true"]),
    ("miner", "Miner's Outfit", "RARE", "leather", 0x5A5A5A, "coal_block", "iron_pickaxe",
     [3, 6, 5, 2], 0, {"mining_efficiency": ("add_value", 4.0)},
     {"head": {"crispy_enchants:glowing": 1}, "chest": {"crispy_enchants:explosiveimmunity": 1},
      "feet": {"crispy_enchants:balancedlanding": 1}},
     "Pickaxe Prodigy", ["Haste II. Each piece mines", "a bit faster."],
     ["effect give @s minecraft:haste 3 1 true"]),
    ("golem", "Golem Armor", "RARE", "iron", ("iron", "sentry"), "iron_block", "carved_pumpkin",
     [3, 7, 6, 3], 1.0, {"knockback_resistance": ("add_value", 0.1)},
     {"chest": {"crispy_enchants:guardians": 2, "minecraft:protection": 3}, "legs": {"minecraft:protection": 2}},
     "Iron Skin", ["Resistance I. Every 30s you", "get Absorption II."],
     ["effect give @s minecraft:resistance 3 0 true",
      "execute if score #gear30 cs_tmp matches 0 run effect give @s minecraft:absorption 30 1 true"]),
    ("blaze", "Blaze Armor", "EPIC", "leather", 0xF5A623, "magma_block", "blaze_rod",
     [3, 7, 6, 3], 1.0, {"attack_damage": ("add_value", 0.5)},
     {"head": {"crispy_enchants:molten": 2}, "chest": {"crispy_enchants:molten": 2, "minecraft:fire_protection": 4},
      "legs": {"crispy_enchants:molten": 2}, "feet": {"crispy_enchants:molten": 2}},
     "Hellfire", ["Fire Resistance. In the Nether:", "Strength I and Speed I too."],
     ["effect give @s minecraft:fire_resistance 3 0 true",
      "execute if dimension minecraft:the_nether run effect give @s minecraft:strength 3 0 true",
      "execute if dimension minecraft:the_nether run effect give @s minecraft:speed 3 0 true"]),
    ("ender", "Ender Armor", "EPIC", "leather", 0x3B1E5C, "purpur_block", "ender_eye",
     [3, 7, 6, 3], 1.0, {"max_health": ("add_value", 2.0)},
     {"head": {"crispy_enchants:endershift": 2}, "chest": {"crispy_enchants:trickster": 2},
      "feet": {"crispy_enchants:endershift": 2, "minecraft:feather_falling": 4}},
     "End Born", ["Speed I. In your island's End:", "Strength II and Regeneration I."],
     ["effect give @s minecraft:speed 3 0 true",
      "execute if dimension crispy_skyblock:end run effect give @s minecraft:strength 3 1 true",
      "execute if dimension crispy_skyblock:end run effect give @s minecraft:regeneration 3 0 true"]),
    ("void", "Voidwalker Armor", "LEGENDARY", "netherite", ("amethyst", "silence"), "shulker_shell", "netherite_ingot",
     [3, 8, 6, 3], 3.0, {"max_health": ("add_value", 2.0), "movement_speed": ("add_multiplied_base", 0.02)},
     {"head": {"crispy_enchants:deathgod": 1, "minecraft:protection": 4}, "chest": {"crispy_enchants:angelic": 2, "minecraft:protection": 4},
      "legs": {"crispy_enchants:overload": 1, "minecraft:protection": 4}, "feet": {"crispy_enchants:jellylegs": 3, "minecraft:protection": 4}},
     "Void Touched", ["Strength I, Speed I, Resistance I", "and +4 hearts. Fall into the void", "and you drift down slowly."],
     ["effect give @s minecraft:strength 3 0 true", "effect give @s minecraft:speed 3 0 true",
      "effect give @s minecraft:resistance 3 0 true", "effect give @s minecraft:health_boost 3 1 true",
      "execute if entity @s[y=-200,dy=240] run effect give @s minecraft:slow_falling 3 0 true"]),
]

# key, name, rarity, base item, damage (total), attack speed (vanilla shown value), enchants, ability (key, name, text lines,
# cooldown seconds) or None, extra lore lines, recipe pattern, recipe key
WEAPONS = [
    ("undead_sword", "Undead Sword", "UNCOMMON", "iron_sword", 7, 1.6,
     {"minecraft:smite": 5, "crispy_enchants:thunderingblow": 1}, None,
     ["Deals extra damage to zombies,", "skeletons and other undead."],
     [" B ", " B ", " S "], {"B": "bone_block", "S": "stick"}),
    ("rogue_sword", "Rogue Sword", "UNCOMMON", "golden_sword", 6, 1.6,
     {"minecraft:unbreaking": 3, "crispy_enchants:featherweight": 2}, ("rogue", "Speed Boost", ["Gain Speed III for 6 seconds."], 15),
     [], [" G ", " U ", " S "], {"G": "gold_block", "U": "sugar", "S": "stick"}),
    ("zombie_sword", "Zombie Sword", "RARE", "iron_sword", 8, 1.6,
     {"minecraft:smite": 3, "crispy_enchants:vampire": 2}, ("heal", "Instant Heal", ["Heal yourself and players within", "7 blocks for 4 hearts."], 20),
     [], ["FIF", "FIF", " S "], {"F": "rotten_flesh", "I": "iron_block", "S": "stick"}),
    ("golem_sword", "Golem Sword", "RARE", "iron_sword", 9, 1.4,
     {"minecraft:knockback": 2, "crispy_enchants:obliterate": 1}, ("iron_punch", "Iron Punch", ["Slam the ground: 10 damage to", "every enemy within 5 blocks", "and knocks them into the air."], 8),
     [], [" I ", " I ", "PSP"], {"I": "iron_block", "P": "carved_pumpkin", "S": "stick"}),
    ("leaping_sword", "Leaping Sword", "RARE", "iron_sword", 8, 1.6,
     {"minecraft:sharpness": 2, "crispy_enchants:shackle": 1}, ("leap", "Leap", ["Launch yourself forward and", "fall slowly for a moment."], 4),
     [], ["F F", " L ", " S "], {"F": "feather", "L": "slime_block", "S": "stick"}),
    ("aote", "Aspect of the End", "RARE", "diamond_sword", 9, 1.6,
     {"minecraft:sharpness": 3, "crispy_enchants:enderslayer": 3}, ("aote", "Instant Transmission", ["Teleport 8 blocks ahead of you", "and gain Speed II for 3 seconds."], 2),
     [], [" E ", " E ", " D "], {"E": "ender_eye", "D": "diamond_sword"}),
    ("ember_rod", "Ember Rod", "EPIC", "blaze_rod", 5, 1.6,
     {"crispy_enchants:scorch": 2}, ("ember", "Fire Blast", ["Shoot a blast of flame at the", "first enemy in your sight", "(12 damage, up to 16 blocks)."], 3),
     [], [" M ", " B ", " B "], {"M": "magma_block", "B": "blaze_rod"}),
    ("pigman_sword", "Pigman Sword", "EPIC", "golden_sword", 10, 1.6,
     {"minecraft:fire_aspect": 2, "minecraft:unbreaking": 5, "crispy_enchants:netherslayer": 3},
     ("burning_souls", "Burning Souls", ["8 damage to enemies within 6", "blocks, then Absorption II", "for 15 seconds."], 20),
     [], ["PGP", " G ", " R "], {"P": "cooked_porkchop", "G": "gold_block", "R": "blaze_rod"}),
    ("voidedge", "Voidedge", "LEGENDARY", "netherite_sword", 13, 1.6,
     {"minecraft:sharpness": 5, "crispy_enchants:lifesteal": 2, "crispy_enchants:execute": 3},
     ("shadow_step", "Shadow Step", ["Teleport behind the nearest", "enemy within 12 blocks and", "strike it for 16 damage."], 8),
     [], ["DHD", "DHD", " N "], {"D": "dragon_breath", "H": "shulker_shell", "N": "netherite_sword"}),
    ("runaan", "Runaan's Crossbow", "RARE", "crossbow", 0, 0,
     {"minecraft:multishot": 1, "minecraft:quick_charge": 3, "minecraft:unbreaking": 3, "crispy_enchants:snare": 2}, None,
     ["Fires three arrows at once and", "reloads in a flash."],
     ["BBB", "SCS", " B "], {"B": "bone_block", "S": "string", "C": "crossbow"}),
    ("stonk", "Stonk", "RARE", "golden_pickaxe", 0, 0,
     {"minecraft:efficiency": 6, "crispy_enchants:telepathy": 1, "crispy_enchants:autosmelt": 1, "crispy_enchants:experience": 3}, None,
     ["Mines faster than any vanilla", "pickaxe, smelts ores and puts", "the drops straight in your bag."],
     ["GGG", " S ", " S "], {"G": "gold_block", "S": "stick"}),
    ("treecapitator", "Treecapitator", "EPIC", "golden_axe", 0, 0,
     {"minecraft:efficiency": 5, "crispy_enchants:timber": 3, "crispy_enchants:telepathy": 1}, None,
     ["A good chance to fell a whole", "tree with one swing."],
     ["OO", "OS", " S"], {"O": "obsidian", "S": "stick"}),
    ("angler_rod", "Angler's Rod", "UNCOMMON", "fishing_rod", 0, 0,
     {"minecraft:luck_of_the_sea": 4, "minecraft:lure": 4, "minecraft:unbreaking": 3}, None,
     ["Better catches, and they bite", "much sooner."],
     ["  K", " KS", "K S"], {"K": "dried_kelp_block", "S": "string"}),
]

GEAR_TARGETS = ["zombie", "husk", "drowned", "zombie_villager", "skeleton", "stray", "bogged", "spider", "cave_spider", "creeper",
                "enderman", "endermite", "witch", "slime", "silverfish", "phantom", "blaze", "magma_cube", "ghast", "wither_skeleton",
                "piglin", "piglin_brute", "zombified_piglin", "hoglin", "zoglin", "ravager", "evoker", "vindicator", "pillager",
                "vex", "shulker", "guardian", "elder_guardian", "breeze", "bogged", "warden"]
PASSABLE = ["#minecraft:air", "minecraft:water", "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern",
            "minecraft:large_fern", "minecraft:snow", "minecraft:light", "#minecraft:small_flowers", "minecraft:vine",
            "minecraft:dead_bush", "minecraft:torch", "minecraft:wall_torch"]
TGT = "type=#crispy_skyblock:gear_targets"
CASTER = "@a[tag=cs_caster,limit=1]"


def build(NS, fn, js, txt):
    def mods(attrs, slot):
        return [{"type": f"minecraft:{a}", "id": f"{NS}:gear_{a}_{slot}", "amount": v, "operation": op, "slot": slot}
                for a, (op, v) in attrs.items()]

    items, menu_items, recipes = {}, [], []

    for (key, name, rar, mat, look, block, core, armor, tough, extra, enchs, bname, btext, _cmds) in SETS:
        for i, (slot, suffix, pname, pattern) in enumerate(PIECES):
            base = f"minecraft:{mat}_{suffix}"
            comp = {
                "minecraft:custom_name": txt(f"{name.removesuffix(' Armor')} {pname}", RARITY[rar]),
                "minecraft:attribute_modifiers": (
                    [{"type": "minecraft:armor", "id": f"minecraft:armor.{SLOT_ARMOR[slot]}", "amount": float(armor[i]), "operation": "add_value", "slot": slot}] +
                    ([{"type": "minecraft:armor_toughness", "id": f"minecraft:armor.{SLOT_ARMOR[slot]}", "amount": float(tough), "operation": "add_value", "slot": slot}] if tough else []) +
                    mods(extra, slot)),
                "minecraft:custom_data": {"cs_set": key},
                "minecraft:unbreakable": {},
                "minecraft:lore": [txt(f"Full Set Bonus: {bname}", "gold")] + [txt(l, "gray") for l in btext] +
                                  [txt(""), txt(f"{rar} ARMOR", RARITY[rar], bold=True)],
            }
            if enchs.get(slot): comp["minecraft:enchantments"] = enchs[slot]
            if isinstance(look, int): comp["minecraft:dyed_color"] = look
            else: comp["minecraft:trim"] = {"material": f"minecraft:{look[0]}", "pattern": f"minecraft:{look[1]}"}
            comp["minecraft:tooltip_display"] = {"hidden_components": ["minecraft:dyed_color", "minecraft:unbreakable", "minecraft:trim"]}
            it = {"id": base, "count": 1, "components": comp}
            rkey = f"{key}_{suffix}"
            items[rkey] = it
            js(f"data/{NS}/recipe/gear/{rkey}.json", {"type": "minecraft:crafting_shaped", "category": "equipment", "group": f"crispy_gear_{key}",
                "pattern": pattern, "key": {"#": f"minecraft:{block}", "C": f"minecraft:{core}"}, "result": it})
            recipes.append(rkey)
    for (key, name, rar, base, dmg, speed, enchs, ab, lore, pattern, rkey_map) in WEAPONS:
        comp = {"minecraft:custom_name": txt(name, RARITY[rar]), "minecraft:enchantments": enchs, "minecraft:unbreakable": {}}
        if dmg:
            comp["minecraft:attribute_modifiers"] = [
                {"type": "minecraft:attack_damage", "id": "minecraft:base_attack_damage", "amount": float(dmg - 1), "operation": "add_value", "slot": "mainhand"},
                {"type": "minecraft:attack_speed", "id": "minecraft:base_attack_speed", "amount": round(speed - 4.0, 2), "operation": "add_value", "slot": "mainhand"}]
        body = [txt(l, "gray") for l in lore]
        kind = "BOW" if base in ("crossbow", "bow") else "TOOL" if base.endswith(("pickaxe", "axe", "rod")) and base != "blaze_rod" else "SWORD"
        if ab:
            akey, aname, atext, cd = ab
            comp["minecraft:custom_data"] = {"cs_ability": akey, "cs_cd": cd * 20}
            comp["minecraft:use_cooldown"] = {"seconds": float(cd), "cooldown_group": f"{NS}:{akey}"}
            body += ([txt("")] if body else []) + [txt(f"Ability: {aname} ", "gold", extra=[txt("RIGHT CLICK", "yellow", bold=True)])] + \
                    [txt(l, "gray") for l in atext] + [txt(f"Cooldown: {cd}s", "dark_gray")]
        comp["minecraft:lore"] = body + [txt(""), txt(f"{rar} {kind}", RARITY[rar], bold=True)]
        comp["minecraft:tooltip_display"] = {"hidden_components": ["minecraft:unbreakable"]}
        it = {"id": f"minecraft:{base}", "count": 1, "components": comp}
        items[key] = it
        js(f"data/{NS}/recipe/gear/{key}.json", {"type": "minecraft:crafting_shaped", "category": "equipment", "group": f"crispy_gear_{key}",
            "pattern": pattern, "key": {k: f"minecraft:{v}" for k, v in rkey_map.items()}, "result": it})
        recipes.append(key)

    # ---------------------------------------------------------------- set bonuses
    js(f"data/{NS}/tags/entity_type/gear_targets.json", {"values": [f"minecraft:{m}" for m in dict.fromkeys(GEAR_TARGETS)]})
    js(f"data/{NS}/tags/block/passable.json", {"values": PASSABLE})
    has = lambda key: " ".join(f"if items entity @s armor.{s} *[minecraft:custom_data~{{cs_set:\"{key}\"}}]" for s, *_ in PIECES)
    fn("gear/bonus", "\n".join(f"execute {has(key)} run return run function {NS}:gear/set/{key}" for key, *_ in SETS))
    for (key, *_r, cmds) in SETS:
        fn(f"gear/set/{key}", "\n".join(cmds))
    fn("gear/second", f"""
scoreboard players add #gear30 cs_tmp 1
execute if score #gear30 cs_tmp matches 30.. run scoreboard players set #gear30 cs_tmp 0
execute as @a[gamemode=!spectator] at @s run function {NS}:gear/bonus
execute as @a unless score @s cs_gearv matches {len(recipes)} run function {NS}:gear/unlock
""")
    fn("gear/unlock", "\n".join(f"recipe give @s {NS}:gear/{r}" for r in recipes) + f"\nscoreboard players set @s cs_gearv {len(recipes)}")

    # ---------------------------------------------------------------- abilities (as and at the player)
    def ability(key, body):
        fn(f"gear/ab/{key}", f"tag @s add cs_caster\n{body.strip()}\ntag @s remove cs_caster")
    ability("rogue", """
effect give @s minecraft:speed 6 2
playsound minecraft:entity.player.attack.sweep player @a[distance=..16] ~ ~ ~ 1 1.6
particle minecraft:cloud ~ ~0.2 ~ 0.3 0.1 0.3 0.05 15
""")
    ability("heal", """
effect give @a[distance=..7,gamemode=!spectator] minecraft:instant_health 1 1
effect give @a[distance=..7,gamemode=!spectator] minecraft:regeneration 4 0
playsound minecraft:entity.zombie_villager.cure player @a[distance=..16] ~ ~ ~ 0.6 1.6
particle minecraft:heart ~ ~1.2 ~ 2 0.5 2 0 20
""")
    ability("iron_punch", f"""
execute as @e[{TGT},distance=..5] run damage @s 10 minecraft:player_attack by {CASTER}
effect give @e[{TGT},distance=..5] minecraft:levitation 1 4 true
playsound minecraft:entity.iron_golem.attack player @a[distance=..16] ~ ~ ~ 1 0.6
playsound minecraft:block.anvil.land player @a[distance=..16] ~ ~ ~ 0.5 0.8
particle minecraft:explosion ~ ~0.3 ~ 2 0.2 2 0 6
""")
    ability("leap", """
execute rotated ~ 0 positioned ^ ^ ^-0.7 run summon minecraft:wind_charge ~ ~0.15 ~ {Motion:[0.0d,-1.0d,0.0d]}
effect give @s minecraft:slow_falling 3 0 true
playsound minecraft:entity.breeze.jump player @a[distance=..16] ~ ~ ~ 1 1.2
""")
    ability("aote", f"""
scoreboard players set #n cs_tmp 0
execute rotated as @s positioned as @s run function {NS}:gear/aote_ray
effect give @s minecraft:speed 3 1
execute at @s run playsound minecraft:entity.enderman.teleport player @a[distance=..16] ~ ~ ~ 1 1.2
execute at @s run particle minecraft:portal ~ ~1 ~ 0.4 0.6 0.4 0.3 40
""")
    # 16 steps of half a block: stop before anything solid at the feet or head
    fn("gear/aote_ray", f"""
execute if score #n cs_tmp matches 16.. run return run tp @s ~ ~ ~
execute positioned ^ ^ ^0.5 unless block ~ ~ ~ #{NS}:passable run return run tp @s ~ ~ ~
execute positioned ^ ^ ^0.5 unless block ~ ~1 ~ #{NS}:passable run return run tp @s ~ ~ ~
scoreboard players add #n cs_tmp 1
execute positioned ^ ^ ^0.5 run function {NS}:gear/aote_ray
""")
    ability("ember", f"""
scoreboard players set #n cs_tmp 0
execute anchored eyes positioned ^ ^ ^ run function {NS}:gear/ember_ray
playsound minecraft:entity.blaze.shoot player @a[distance=..16] ~ ~ ~ 1 1
""")
    fn("gear/ember_ray", f"""
particle minecraft:flame ~ ~ ~ 0.05 0.05 0.05 0.01 2
execute as @e[{TGT},distance=..1.5,limit=1,sort=nearest] at @s run return run function {NS}:gear/ember_hit
execute unless block ~ ~ ~ #{NS}:passable run return 0
scoreboard players add #n cs_tmp 1
execute if score #n cs_tmp matches ..32 positioned ^ ^ ^0.5 run function {NS}:gear/ember_ray
""")
    fn("gear/ember_hit", f"""
damage @s 12 minecraft:in_fire by {CASTER}
data merge entity @s {{Fire:80s}}
particle minecraft:lava ~ ~1 ~ 0.3 0.5 0.3 0 8
playsound minecraft:entity.blaze.hurt player @a[distance=..16] ~ ~ ~ 1 1
""")
    ability("burning_souls", f"""
execute as @e[{TGT},distance=..6] run damage @s 8 minecraft:in_fire by {CASTER}
execute as @e[{TGT},distance=..6] run data merge entity @s {{Fire:100s}}
effect give @s minecraft:absorption 15 1
particle minecraft:soul_fire_flame ~ ~1 ~ 3 0.8 3 0.02 60
playsound minecraft:entity.piglin_brute.angry player @a[distance=..16] ~ ~ ~ 1 1
""")
    ability("shadow_step", f"""
execute unless entity @e[{TGT},distance=..12] run return run title @s actionbar {{text:"No enemy close enough.",color:"red"}}
execute as @e[{TGT},distance=..12,sort=nearest,limit=1] at @s run function {NS}:gear/shadow_hit
""")
    fn("gear/shadow_hit", f"""
execute rotated as @s rotated ~ 0 positioned ^ ^ ^-1.5 if block ~ ~ ~ #{NS}:passable if block ~ ~1 ~ #{NS}:passable run tp {CASTER} ~ ~ ~ facing entity @s feet
execute unless entity @a[tag=cs_caster,distance=..2.5] run tp {CASTER} ~ ~ ~ facing entity @s feet
damage @s 16 minecraft:player_attack by {CASTER}
particle minecraft:reverse_portal ~ ~1 ~ 0.4 0.8 0.4 0.05 40
playsound minecraft:entity.enderman.teleport player @a[distance=..16] ~ ~ ~ 1 0.6
""")

    # ---------------------------------------------------------------- the Armor & Weapons menu
    def preview(it, ingredients):
        comp = dict(it["components"])
        comp["minecraft:lore"] = list(comp["minecraft:lore"]) + [txt(""), txt("Recipe (crafting table):", "yellow")] + \
                                 [txt("• ", "dark_gray", extra=[txt(l, "white")]) for l in ingredients]
        comp["minecraft:tooltip_display"] = {"hidden_components": ["minecraft:dyed_color", "minecraft:unbreakable", "minecraft:trim", "minecraft:attribute_modifiers"]}
        return {"id": it["id"], "count": 1, "components": comp}
    nice = lambda s: s.replace("_", " ").title()
    pages = []
    for (key, name, rar, mat, look, block, core, *_r) in SETS:
        chest = items[f"{key}_chestplate"]
        cnt = lambda pat, ch: sum(row.count(ch) for row in pat)
        pages.append(preview(chest, [f"{nice(block)} + {nice(core)} in the piece's shape:"] +
                             [f"{pn}: {cnt(pat, '#')} {nice(block)}, {cnt(pat, 'C')} {nice(core)}" for _s, _x, pn, pat in PIECES] +
                             ["Shown: the chestplate. All four", "pieces give the set bonus."]))
    for (key, name, rar, base, dmg, speed, enchs, ab, lore, pattern, rkey_map) in WEAPONS:
        n = {}
        for row in pattern:
            for ch in row:
                if ch != " ": n[ch] = n.get(ch, 0) + 1
        pages.append(preview(items[key], [f"{c} {nice(rkey_map[ch])}" for ch, c in n.items()] + [" / ".join(r.replace(" ", "·") for r in pattern)]))
    slots = [10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 37, 38, 39, 40, 41, 42, 43]
    menu = {"title": txt("Armor & Weapons", "dark_gray"), "rows": 6,
            "fill": {"id": "minecraft:black_stained_glass_pane", "count": 1, "components": {"minecraft:custom_name": txt("")}},
            "items": [{"slot": slots[i], "cmd": "", "item": p} for i, p in enumerate(pages)] +
                     [{"slot": 49, "cmd": "trigger cs_act set 7", "item": {"id": "minecraft:arrow", "count": 1,
                       "components": {"minecraft:custom_name": txt("Island Menu", "gray")}}}]}
    assert len(pages) <= len(slots)
    return {"menu": menu, "count": len(recipes), "sets": len(SETS), "weapons": len(WEAPONS)}
