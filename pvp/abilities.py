"""Kit abilities for crispy_pvp (imported by build.py).

An ability is an item in the hotbar: right-click to use it.
- It is paper with an item_model, a near-instant `consumable` and a `use_cooldown`, so the client shows the cooldown
  sweep and the server enforces it.
- Using it fires a consume_item advancement, whose reward runs pvp:ability/use/<key>.
- `use_remainder` leaves a copy without the remainder in the same hand. Next tick pvp:ability/regive swaps that copy
  for the full item, which marks the right hand without nesting remainders forever.

Effects run as the caster, at the caster, tagged pvp.caster. Targets:
- skip non-living entities (entity tag pvp:not_target), the caster, and Outbreak teammates (team pve);
- in Outbreak, mobs are on no team, so they are always targets.
"""
import json

NS = "pvp"
TGT = "type=!#pvp:not_target,tag=!pvp.caster,team=!pve"
BY = "by @p[tag=pvp.caster]"
NOT_TARGET = ["item", "marker", "interaction", "text_display", "block_display", "item_display", "armor_stand", "mannequin",
              "villager", "experience_orb", "arrow", "spectral_arrow", "trident", "wind_charge", "breeze_wind_charge", "fireball",
              "small_fireball", "snowball", "tnt", "falling_block", "lightning_bolt", "area_effect_cloud", "ender_pearl",
              "splash_potion", "lingering_potion", "firework_rocket", "end_crystal", "egg", "experience_bottle"]


def damage(n, kind="player_attack"): return f"damage @s {n} minecraft:{kind} {BY}"
def cone(r, cmd): return f"execute anchored eyes positioned ^ ^ ^{r} as @e[distance=..{r + 0.1},{TGT}] at @s run {cmd}"
def around(r, cmd): return f"execute as @e[distance=..{r},{TGT}] at @s run {cmd}"
def ray(n): return [f"scoreboard players set #ray pvp {n}", f"function {NS}:ability/ray_start"]   # n half-blocks; hit gets pvp.hit
def hit(cmd): return f"execute as @e[tag=pvp.hit] at @s run {cmd}"
PUSH = f"function {NS}:ability/push"          # as a target, at it: knocked away from the caster (and up)
LAUNCH = "summon minecraft:wind_charge ~ ~0.1 ~ {Motion:[0.0d,-1.0d,0.0d]}"            # launches the caster up
DASH = "execute rotated ~ 0 positioned ^ ^ ^-0.7 run summon minecraft:wind_charge ~ ~0.15 ~ {Motion:[0.0d,-1.0d,0.0d]}"


def shoot(entity, speed, extra="", spread=(0,)):
    """Projectiles from the caster's eyes along their look direction (yaw offsets in spread), owned by the caster."""
    out = []
    for yaw in spread:
        out += [f"execute anchored eyes positioned ^ ^ ^1 rotated ~{yaw} ~ run summon minecraft:{entity} ^ ^ ^0.2 {{Tags:[\"pvp.shot\"]{extra}}}",
                f"execute rotated ~{yaw} ~ positioned 0.0 0.0 0.0 run summon minecraft:marker ^ ^ ^{speed} {{Tags:[\"pvp.vec\"]}}",
                "data modify entity @n[tag=pvp.shot] Motion set from entity @n[type=minecraft:marker,tag=pvp.vec] Pos",
                "data modify entity @n[tag=pvp.shot] Owner set from entity @s UUID",
                "kill @e[type=minecraft:marker,tag=pvp.vec]", "tag @e[tag=pvp.shot] remove pvp.shot"]
    return out


def snd(s, vol=1, pitch=1): return f"playsound minecraft:{s} player @a[distance=..24] ~ ~ ~ {vol} {pitch}"
def bar(text, color): return f'title @s actionbar {{"text":"◆ {text}","color":"{color}","bold":true}}'


# key: (name, colour, item model, cooldown s, lore, effect lines)
ABILITIES = {
    # ---------------------------------------------------------------- Star Wars
    "force_push": ("Force Push", "aqua", "wind_charge", 7, ["Throws everything in front of you back."], [
        cone(3.5, damage(2, "magic")), cone(3.5, PUSH),
        "execute anchored eyes run particle minecraft:gust ^ ^ ^2 0.6 0.4 0.6 0 4",
        snd("entity.breeze.shoot", 1, 0.6), bar("FORCE PUSH", "aqua")]),
    "mind_trick": ("Jedi Mind Trick", "aqua", "ender_eye", 15, ["Blinds and slows everyone in front", "of you for 4 seconds."], [
        cone(4, "effect give @s minecraft:blindness 4 0"), cone(4, "effect give @s minecraft:slowness 4 1"),
        cone(4, "effect give @s minecraft:nausea 5 0"),
        "execute anchored eyes run particle minecraft:enchant ^ ^ ^2.5 1 0.6 1 0.5 60",
        snd("entity.illusioner.cast_spell", 1, 1.2), bar("THESE AREN'T THE DROIDS YOU'RE LOOKING FOR", "aqua")]),
    "force_lightning": ("Force Lightning", "dark_purple", "lightning_rod", 9, ["Lightning arcs into everyone", "in front of you: 6 damage + slow."], [
        cone(4, damage(6, "lightning_bolt")), cone(4, "effect give @s minecraft:slowness 2 1"),
        cone(4, "particle minecraft:electric_spark ~ ~1 ~ 0.3 0.6 0.3 0.3 30"),
        "execute anchored eyes run particle minecraft:electric_spark ^ ^ ^1.5 0.2 0.2 0.2 0.4 40",
        snd("entity.lightning_bolt.thunder", 0.3, 2), snd("block.respawn_anchor.deplete", 0.8, 1.6), bar("UNLIMITED POWER", "dark_purple")]),
    "force_choke": ("Force Choke", "dark_red", "wither_rose", 14, ["Lifts the target you look at (16 blocks)", "and crushes it: 4 damage + Wither."], [
        *ray(32),
        hit(damage(4, "magic")), hit("effect give @s minecraft:levitation 2 0"), hit("effect give @s minecraft:wither 3 1"),
        hit("particle minecraft:dust{color:[0.5,0.0,0.0],scale:1.2} ~ ~1.6 ~ 0.2 0.1 0.2 0 20"),
        hit(snd("entity.player.hurt_drown", 1, 0.7)),
        "execute unless entity @e[tag=pvp.hit] run " + snd("block.fire.extinguish", 0.5, 1.5),
        bar("I FIND YOUR LACK OF FAITH DISTURBING", "dark_red")]),
    # ---------------------------------------------------------------- video games
    "spin_attack": ("Spin Attack", "green", "nautilus_shell", 6, ["Hits everything around you", "for 7 damage and knocks it back."], [
        around(3.5, damage(7)), around(3.5, PUSH),
        "particle minecraft:sweep_attack ~1.5 ~1 ~ 0 0 0 0 1", "particle minecraft:sweep_attack ~-1.5 ~1 ~ 0 0 0 0 1",
        "particle minecraft:sweep_attack ~ ~1 ~1.5 0 0 0 0 1", "particle minecraft:sweep_attack ~ ~1 ~-1.5 0 0 0 0 1",
        snd("entity.player.attack.sweep", 1, 0.8), snd("item.trident.riptide_1", 0.6, 1.4), bar("SPIN ATTACK", "green")]),
    "hookshot": ("Hookshot", "green", "lead", 8, ["Grabs the target you look at", "(18 blocks) and reels it in."], [
        *ray(36),
        "execute rotated ~ 0 positioned ^ ^ ^1.8 run tp @e[tag=pvp.hit,limit=1] ~ ~ ~",
        hit("effect give @s minecraft:slowness 1 2"), hit("particle minecraft:crit ~ ~1 ~ 0.3 0.5 0.3 0.2 15"),
        snd("item.crossbow.hit", 1, 0.7), snd("entity.fishing_bobber.retrieve", 1, 0.8), bar("HOOKSHOT", "green")]),
    "frag_grenade": ("Frag Grenade", "dark_green", "tnt", 10, ["Throw a grenade: 10 damage to everything", "within 4 blocks where it lands."], [
        "execute unless score @s pvp.id matches 1.. store result score @s pvp.id run scoreboard players add #nextid pvp 1",
        "execute anchored eyes positioned ^ ^ ^0.8 run summon minecraft:armor_stand ~ ~-0.6 ~ {Tags:[\"pvp.nade\",\"pvp.nnew\"],Small:1b,Invisible:1b,"
        "Invulnerable:1b,DisabledSlots:4144959,equipment:{head:{id:\"minecraft:tnt\",count:1}}}",
        "execute rotated ~ ~-12 positioned 0.0 0.0 0.0 run summon minecraft:marker ^ ^ ^1.1 {Tags:[\"pvp.vec\"]}",
        "data modify entity @n[type=minecraft:armor_stand,tag=pvp.nnew] Motion set from entity @n[type=minecraft:marker,tag=pvp.vec] Pos",
        "kill @e[type=minecraft:marker,tag=pvp.vec]",
        "scoreboard players operation @n[type=minecraft:armor_stand,tag=pvp.nnew] pvp.id = @s pvp.id",
        "execute if entity @s[team=pve] run tag @n[type=minecraft:armor_stand,tag=pvp.nnew] add pvp.npve",
        "tag @e[type=minecraft:armor_stand,tag=pvp.nnew] remove pvp.nnew",
        snd("entity.snowball.throw", 1, 0.6), bar("FRAG OUT", "dark_green")]),
    "chainsaw": ("Chainsaw", "red", "shears", 12, ["Saw the target right in front of you", "(4 blocks) for 14 damage."], [
        *ray(8),
        hit(damage(14)), hit("particle minecraft:block{block_state:\"minecraft:redstone_block\"} ~ ~1 ~ 0.3 0.5 0.3 0.2 40"),
        "execute if entity @e[tag=pvp.hit] run effect give @s minecraft:absorption 8 1",
        snd("entity.ravager.attack", 1, 1.4), snd("block.grindstone.use", 1, 0.6), bar("RIP AND TEAR", "red")]),
    "rip_tear": ("Berserk Rune", "dark_red", "redstone", 25, ["Strength II, Speed II and", "Resistance I for 6 seconds."], [
        "effect give @s minecraft:strength 6 1", "effect give @s minecraft:speed 6 1", "effect give @s minecraft:resistance 6 0",
        "particle minecraft:angry_villager ~ ~1 ~ 0.5 0.6 0.5 0 12",
        snd("entity.ravager.roar", 1, 0.8), bar("BERSERK", "dark_red")]),
    "igni": ("Igni", "gold", "blaze_powder", 8, ["A fan of 3 fireballs that", "set targets alight."], [
        *shoot("small_fireball", 1.3, ",acceleration_power:0.0d", (-12, 0, 12)),
        snd("entity.blaze.shoot", 1, 0.8), bar("IGNI", "gold")]),
    "quen": ("Quen", "yellow", "amethyst_shard", 16, ["A shield: 4 absorption hearts", "and Resistance I for 6 seconds."], [
        "effect clear @s minecraft:absorption", "effect give @s minecraft:absorption 10 1", "effect give @s minecraft:resistance 6 0",
        "particle minecraft:totem_of_undying ~ ~1 ~ 0.5 0.8 0.5 0.1 30",
        snd("block.amethyst_block.chime", 1, 0.6), snd("block.beacon.power_select", 0.6, 1.6), bar("QUEN", "yellow")]),
    # ---------------------------------------------------------------- Smash Bros
    "fireball": ("Fireball", "red", "fire_charge", 3, ["Throw a fireball."], [
        *shoot("small_fireball", 1.0, ",acceleration_power:0.0d"), snd("entity.blaze.shoot", 0.8, 1.6), bar("FIREBALL", "red")]),
    "super_jump": ("Super Jump Punch", "gold", "gold_nugget", 8, ["Leap up, uppercutting everything", "around you: 6 damage."], [
        LAUNCH, around(2.5, damage(6)), around(2.5, "effect give @s minecraft:levitation 1 3"),
        "particle minecraft:wax_on ~ ~1.5 ~ 0.4 0.6 0.4 0.1 20",
        snd("entity.experience_orb.pickup", 1, 1.8), snd("entity.player.attack.strong", 1, 1), bar("SUPER JUMP PUNCH", "gold")]),
    "thunder_jolt": ("Thunder Jolt", "yellow", "glowstone_dust", 4, ["Zap the target you look at", "(16 blocks): 6 damage + slow."], [
        *ray(32),
        hit(damage(6, "lightning_bolt")), hit("effect give @s minecraft:slowness 2 1"), hit("effect give @s minecraft:glowing 2 0"),
        hit("particle minecraft:electric_spark ~ ~1 ~ 0.3 0.6 0.3 0.4 40"),
        "execute anchored eyes run particle minecraft:electric_spark ^ ^ ^1 0.1 0.1 0.1 0.3 15",
        snd("item.trident.thunder", 0.4, 1.8), bar("PIKA!", "yellow")]),
    "quick_attack": ("Quick Attack", "yellow", "feather", 6, ["Dash forward and gain Speed II", "for 2 seconds."], [
        DASH, "effect give @s minecraft:speed 2 1", "particle minecraft:cloud ~ ~0.2 ~ 0.3 0.1 0.3 0.05 15",
        snd("entity.breeze.jump", 1, 1.6), bar("QUICK ATTACK", "yellow")]),
    "inhale": ("Inhale", "light_purple", "pink_petals", 10, ["Suck in the target you look at", "(10 blocks): 5 damage, +2 hearts for you."], [
        *ray(20),
        "execute rotated ~ 0 positioned ^ ^ ^1.5 run tp @e[tag=pvp.hit,limit=1] ~ ~ ~",
        hit(damage(5)),
        "execute if entity @e[tag=pvp.hit] run effect give @s minecraft:absorption 10 0",
        "execute anchored eyes run particle minecraft:cloud ^ ^ ^2 0.6 0.4 0.6 0.05 25",
        snd("entity.player.breath", 1, 0.5), snd("entity.player.burp", 1, 1.2), bar("INHALE", "light_purple")]),
    "stone": ("Stone", "gray", "cobblestone", 12, ["Turn to stone: immune for 3 seconds,", "and slam everything around you."], [
        "effect give @s minecraft:resistance 3 4", "effect give @s minecraft:slowness 3 5",
        around(3, damage(6)), around(3, PUSH),
        "particle minecraft:block{block_state:\"minecraft:stone\"} ~ ~0.5 ~ 1 0.3 1 0.2 50",
        snd("entity.iron_golem.damage", 1, 0.6), snd("block.stone.place", 1, 0.5), bar("STONE", "gray")]),
    "charge_shot": ("Charge Shot", "gold", "magma_cream", 6, ["Fire an explosive plasma ball."], [
        *shoot("fireball", 1.3, ",ExplosionPower:1b,acceleration_power:0.0d"), snd("entity.blaze.shoot", 1, 0.5),
        snd("block.beacon.deactivate", 0.6, 2), bar("CHARGE SHOT", "gold")]),
    "screw_attack": ("Screw Attack", "aqua", "prismarine_crystals", 8, ["Spin upward, shredding everything", "around you: 6 damage."], [
        LAUNCH, around(3, damage(6)), around(3, PUSH),
        "particle minecraft:electric_spark ~ ~1 ~ 0.6 1 0.6 0.4 50",
        snd("entity.breeze.wind_burst", 1, 1.4), bar("SCREW ATTACK", "aqua")]),
}


def give(key): return f"loot give @s loot {NS}:ability/{key}"


def item_components(key, with_remainder=True):
    name, color, model, cd, lore, _ = ABILITIES[key]
    comps = {
        "minecraft:item_model": f"minecraft:{model}",
        "minecraft:custom_name": {"text": name, "color": color, "italic": False, "bold": True},
        "minecraft:lore": [{"text": l, "color": "gray", "italic": False} for l in lore]
                          + [{"text": f"Right-click · {cd} s cooldown", "color": "dark_gray", "italic": False}],
        "minecraft:custom_data": {"pvp_ab": key},
        "minecraft:max_stack_size": 1,
        "minecraft:enchantment_glint_override": True,
        "minecraft:consumable": {"consume_seconds": 0.05, "animation": "none", "has_consume_particles": False,
                                 "sound": "minecraft:intentionally_empty"},
        "minecraft:use_cooldown": {"seconds": cd, "cooldown_group": f"pvp:ab_{key}"},
    }
    if with_remainder:
        comps["minecraft:use_remainder"] = {"id": "minecraft:paper", "count": 1, "components": item_components(key, False)}
    return comps


def build(fn, wj):
    wj(f"data/{NS}/tags/entity_type/not_target.json", {"values": [f"minecraft:{t}" for t in NOT_TARGET]})
    for key, (name, color, model, cd, lore, body) in ABILITIES.items():
        wj(f"data/{NS}/loot_table/ability/{key}.json", {"pools": [{"rolls": 1, "entries": [{
            "type": "minecraft:item", "name": "minecraft:paper",
            "functions": [{"function": "minecraft:set_components", "components": item_components(key)}]}]}]})
        wj(f"data/{NS}/advancement/ability/{key}.json", {"criteria": {"c": {"trigger": "minecraft:consume_item", "conditions": {
            "item": {"items": "minecraft:paper", "components": {"minecraft:custom_data": {"pvp_ab": key}}}}}},
            "rewards": {"function": f"{NS}:ability/use/{key}"}})
        fn(f"ability/use/{key}", [
            f"advancement revoke @s only {NS}:ability/{key}",
            "tag @s add pvp.regive", "tag @s add pvp.caster",
            f"execute at @s run function {NS}:ability/fx/{key}",
            "tag @s remove pvp.caster", "tag @e[tag=pvp.hit] remove pvp.hit",
        ])
        fn(f"ability/fx/{key}", body)
    # the used item is now its remainder copy: swap it for the full item (keeps its slot)
    fn("ability/regive", ["tag @s remove pvp.regive"] + [
        f"execute if items entity @s {slot} minecraft:paper[minecraft:custom_data~{{pvp_ab:\"{k}\"}}] unless items entity @s {slot} "
        f"*[minecraft:use_remainder] run loot replace entity @s {slot} loot {NS}:ability/{k}"
        for k in ABILITIES for slot in ("weapon.mainhand", "weapon.offhand")])
    # raycast: half-block steps from the eyes, stops at the first target or a solid block
    fn("ability/ray_start", [f"execute anchored eyes positioned ^ ^ ^0.5 run function {NS}:ability/ray"])
    fn("ability/ray", [
        f"execute positioned ~-0.5 ~-0.5 ~-0.5 as @e[dx=0,dy=0,dz=0,{TGT},limit=1,sort=nearest] run return run tag @s add pvp.hit",
        "scoreboard players remove #ray pvp 1",
        f"execute if score #ray pvp matches 1.. if block ~ ~ ~ #minecraft:replaceable positioned ^ ^ ^0.5 run function {NS}:ability/ray",
    ])
    # knockback: a wind charge bursts between the caster and the target
    fn("ability/push", ["execute facing entity @p[tag=pvp.caster] feet positioned ^ ^ ^0.7 run summon minecraft:wind_charge ~ ~0.4 ~ {Motion:[0.0d,-1.0d,0.0d]}"])
    # grenades: fly until they land (or 2 s), then blow up for the thrower
    fn("ability/nade_tick", [
        "scoreboard players add @s pvp.ft 1",
        f"execute if entity @s[nbt={{OnGround:1b}}] run return run function {NS}:ability/nade_boom",
        f"execute if score @s pvp.ft matches 40.. run function {NS}:ability/nade_boom",
    ])
    fn("ability/nade_boom", [
        "scoreboard players operation #nid pvp = @s pvp.id",
        "execute as @a if score @s pvp.id = #nid pvp run tag @s add pvp.owner",
        "execute if entity @s[tag=pvp.npve] as @e[distance=..4,type=!#pvp:not_target,type=!minecraft:player] run damage @s 10 minecraft:explosion by @p[tag=pvp.owner]",
        "execute unless entity @s[tag=pvp.npve] as @e[distance=..4,type=!#pvp:not_target] run damage @s 10 minecraft:explosion by @p[tag=pvp.owner]",
        "summon minecraft:wind_charge ~ ~0.3 ~ {Motion:[0.0d,-1.0d,0.0d]}",
        "particle minecraft:explosion_emitter ~ ~0.5 ~ 0 0 0 0 1",
        "playsound minecraft:entity.generic.explode player @a[distance=..32] ~ ~ ~ 1 1",
        "tag @a remove pvp.owner", "kill @s",
    ])
    # passives, keyed off carrying the kit's ability items (so they end with the kit)
    has = lambda k: f"if items entity @s container.* minecraft:paper[minecraft:custom_data~{{pvp_ab:\"{k}\"}}]"
    fn("ability/tick", [
        f"execute as @a[tag=pvp.regive] run function {NS}:ability/regive",
        f"execute as @e[type=minecraft:armor_stand,tag=pvp.nade] at @s run function {NS}:ability/nade_tick",
        # Doom Slayer: every kill heals (glory kill)
        f"execute as @a[scores={{pvp.gk=1..}}] {has('chainsaw')} at @s run function {NS}:ability/glory",
        "scoreboard players set @a[scores={pvp.gk=1..}] pvp.gk 0",
    ])
    fn("ability/glory", ["effect give @s minecraft:instant_health 1 0 true", "effect give @s minecraft:speed 3 1 true",
                         "particle minecraft:heart ~ ~1.5 ~ 0.4 0.3 0.4 0 6", "playsound minecraft:entity.player.levelup player @s ~ ~ ~ 0.6 1.8",
                         "title @s actionbar {\"text\":\"◆ GLORY KILL\",\"color\":\"red\",\"bold\":true}"])
    fn("ability/second", [
        # Spartan energy shield: 4 absorption hearts that come back after 4 s without taking damage
        f"execute as @a {has('frag_grenade')} at @s run function {NS}:ability/shield",
    ])
    fn("ability/shield", [
        "execute if score @s pvp.dmg matches 1.. run scoreboard players set @s pvp.sh 0",
        "scoreboard players set @s pvp.dmg 0",
        "scoreboard players add @s pvp.sh 1",
        "execute store result score #ab pvp run data get entity @s AbsorptionAmount",
        f"execute if score @s pvp.sh matches 4.. if score #ab pvp matches ..7 run function {NS}:ability/shield_up",
    ])
    fn("ability/shield_up", ["effect clear @s minecraft:absorption", "effect give @s minecraft:absorption infinite 1 true",
                             "playsound minecraft:block.beacon.power_select player @s ~ ~ ~ 0.6 1.8",
                             "title @s actionbar {\"text\":\"◆ Shields recharged\",\"color\":\"dark_green\"}"])
    return ["pvp.id dummy", "pvp.ft dummy", "pvp.gk totalKillCount", "pvp.dmg minecraft.custom:minecraft.damage_taken", "pvp.sh dummy"]
