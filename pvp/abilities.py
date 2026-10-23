"""Kit abilities for crispy_pvp (imported by build.py).

An ability is an item in the hotbar: right-click to use it.
- It is a clay ball (not paper, which the cyberware implants use) with an item_model, a near-instant `consumable` and
  a `use_cooldown`, so the client shows the cooldown sweep and the server enforces it.
- Using any of them fires one consume_item advancement (pvp:ability/used, matched on the base item only). Its reward
  runs while the item is still in the hand: it works out which ability that is from the item model
  and runs pvp:ability/use/<key>, which remembers the ability and the selected hotbar slot. The last used item is
  kept in storage pvp:debug for troubleshooting.
- 3 ticks later pvp:ability/regive puts the item back in that slot (not sooner: if the slot is emptied and refilled
  before the server syncs the inventory, the client never hears about either change and keeps showing it empty), or the offhand if it came from there, otherwise the
  inventory. Never twice, and never in the lobby.

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
    """Projectiles from the caster's eyes along their look direction (yaw offsets in spread), owned by the caster.
    They have no acceleration, so air drag stops one that misses and it would hover forever: ability/tick removes
    them (tag pvp.proj) after PROJ_LIFE ticks."""
    out = []
    for yaw in spread:
        out += [f"execute anchored eyes positioned ^ ^ ^1 rotated ~{yaw} ~ run summon minecraft:{entity} ^ ^ ^0.2 {{Tags:[\"pvp.shot\",\"pvp.proj\"]{extra}}}",
                f"execute rotated ~{yaw} ~ positioned 0.0 0.0 0.0 run summon minecraft:marker ^ ^ ^{speed} {{Tags:[\"pvp.vec\"]}}",
                "data modify entity @n[tag=pvp.shot] Motion set from entity @n[type=minecraft:marker,tag=pvp.vec] Pos",
                "data modify entity @n[tag=pvp.shot] Owner set from entity @s UUID",
                "kill @e[type=minecraft:marker,tag=pvp.vec]", "tag @e[tag=pvp.shot] remove pvp.shot"]
    return out


PROJ_LIFE = 40


GUN_TIER_BOOST = [0, 0.4, 0.8, 1.2]   # Pack-a-Punch gun tiers (Outbreak): extra damage; tier III also slows on hit
GUNS = []                             # keys of the gun abilities (filled in below)
def tiered(dmg, cmd):
    """Damage lines for each Pack-a-Punch gun tier (score pve.gun on the caster; unset = tier 0). cmd(d) -> command."""
    out = [f"execute unless score @s pve.gun matches 1.. run {cmd(dmg)}"]
    for t in (1, 2, 3):
        out.append(f"execute if score @s pve.gun matches {t} run {cmd(round(dmg * (1 + GUN_TIER_BOOST[t]), 1))}")
    return out


def gun(name, color, model, cd, dmg, rng, what, sound, pitch=1.0, on_hit=()):
    """A hitscan gun: right-click fires a bullet (with a tracer) at the first enemy along your aim, up to rng blocks."""
    extra = [h[0] for h in on_hit if h[0]]
    return (name, color, model, cd, [what, f"{rng} blocks · {dmg} damage" + (f" · {', '.join(extra)}" if extra else "")], [
        "scoreboard players set #tr pvp 1", *ray(rng * 2), "scoreboard players set #tr pvp 0",
        *tiered(dmg, lambda d: hit(damage(d, "arrow"))), *[hit(h[1]) for h in on_hit],
        "execute if score @s pve.gun matches 3 run " + hit("effect give @s minecraft:slowness 1 1"),
        hit("particle minecraft:damage_indicator ~ ~1 ~ 0.2 0.3 0.2 0.1 3"),
        "execute anchored eyes run particle minecraft:smoke ^ ^-0.1 ^0.9 0.03 0.03 0.03 0.01 4",
        f"playsound minecraft:{sound} player @a[distance=..48] ~ ~ ~ 1 {pitch}"])


def shotgun(name, color, model, cd, dmg, rng, what, sound, pitch=1.0):
    """A shotgun: a blast hitting every enemy in a cone in front of you, with knockback."""
    return (name, color, model, cd, [what, f"{round(rng * 2)} blocks · {dmg} damage to everything in front · knockback"], [
        *tiered(dmg, lambda d: cone(rng, damage(d, "arrow"))), cone(rng, PUSH),
        "execute if score @s pve.gun matches 3 run " + cone(rng, "effect give @s minecraft:slowness 1 1"),
        f"execute anchored eyes run particle minecraft:crit ^ ^ ^{rng} 0.8 0.5 0.8 0.3 40",
        "execute anchored eyes run particle minecraft:large_smoke ^ ^-0.1 ^1 0.1 0.1 0.1 0.02 6",
        f"playsound minecraft:{sound} player @a[distance=..48] ~ ~ ~ 1 {pitch}"])


def snd(s, vol=1, pitch=1): return f"playsound minecraft:{s} player @a[distance=..24] ~ ~ ~ {vol} {pitch}"
def bar(text, color): return f'title @s actionbar {{"text":"◆ {text}","color":"{color}","bold":true}}'


# key: (name, colour, item model, cooldown s, lore, effect lines)
ABILITIES = {
    # ---------------------------------------------------------------- Star Wars
    "force_push": ("Force Push", "aqua", "wind_charge", 7, ["Blasts enemies in front of you back.", "7 blocks · 2 damage · knockback"], [
        cone(3.5, damage(2, "magic")), cone(3.5, PUSH),
        "execute anchored eyes run particle minecraft:gust ^ ^ ^2 0.6 0.4 0.6 0 4",
        snd("entity.breeze.shoot", 1, 0.6), bar("FORCE PUSH", "aqua")]),
    "mind_trick": ("Jedi Mind Trick", "aqua", "ender_eye", 15, ["Confuses enemies in front of you.", "8 blocks · Blindness, Slowness II, Nausea · 4 s"], [
        cone(4, "effect give @s minecraft:blindness 4 0"), cone(4, "effect give @s minecraft:slowness 4 1"),
        cone(4, "effect give @s minecraft:nausea 5 0"),
        "execute anchored eyes run particle minecraft:enchant ^ ^ ^2.5 1 0.6 1 0.5 60",
        snd("entity.illusioner.cast_spell", 1, 1.2), bar("THESE AREN'T THE DROIDS YOU'RE LOOKING FOR", "aqua")]),
    "force_lightning": ("Force Lightning", "dark_purple", "lightning_rod", 9, ["Electrocutes enemies in front of you.", "8 blocks · 6 damage · Slowness II 2 s"], [
        cone(4, damage(6, "lightning_bolt")), cone(4, "effect give @s minecraft:slowness 2 1"),
        cone(4, "particle minecraft:electric_spark ~ ~1 ~ 0.3 0.6 0.3 0.3 30"),
        "execute anchored eyes run particle minecraft:electric_spark ^ ^ ^1.5 0.2 0.2 0.2 0.4 40",
        snd("entity.lightning_bolt.thunder", 0.3, 2), snd("block.respawn_anchor.deplete", 0.8, 1.6), bar("UNLIMITED POWER", "dark_purple")]),
    "force_choke": ("Force Choke", "dark_red", "wither_rose", 14, ["Lifts and chokes the enemy you aim at.", "16 blocks · 4 damage · Wither II 3 s"], [
        *ray(32),
        hit(damage(4, "magic")), hit("effect give @s minecraft:levitation 2 0"), hit("effect give @s minecraft:wither 3 1"),
        hit("particle minecraft:dust{color:[0.5,0.0,0.0],scale:1.2} ~ ~1.6 ~ 0.2 0.1 0.2 0 20"),
        hit(snd("entity.player.hurt_drown", 1, 0.7)),
        "execute unless entity @e[tag=pvp.hit] run " + snd("block.fire.extinguish", 0.5, 1.5),
        bar("I FIND YOUR LACK OF FAITH DISTURBING", "dark_red")]),
    # ---------------------------------------------------------------- video games
    "spin_attack": ("Spin Attack", "green", "nautilus_shell", 6, ["Strikes everything around you.", "3.5 blocks · 7 damage · knockback"], [
        around(3.5, damage(7)), around(3.5, PUSH),
        "particle minecraft:sweep_attack ~1.5 ~1 ~ 0 0 0 0 1", "particle minecraft:sweep_attack ~-1.5 ~1 ~ 0 0 0 0 1",
        "particle minecraft:sweep_attack ~ ~1 ~1.5 0 0 0 0 1", "particle minecraft:sweep_attack ~ ~1 ~-1.5 0 0 0 0 1",
        snd("entity.player.attack.sweep", 1, 0.8), snd("item.trident.riptide_1", 0.6, 1.4), bar("SPIN ATTACK", "green")]),
    "hookshot": ("Hookshot", "green", "lead", 8, ["Pulls the enemy you aim at to you.", "18 blocks · Slowness III 1 s"], [
        *ray(36),
        "execute rotated ~ 0 positioned ^ ^ ^1.8 run tp @e[tag=pvp.hit,limit=1] ~ ~ ~",
        hit("effect give @s minecraft:slowness 1 2"), hit("particle minecraft:crit ~ ~1 ~ 0.3 0.5 0.3 0.2 15"),
        snd("item.crossbow.hit", 1, 0.7), snd("entity.fishing_bobber.retrieve", 1, 0.8), bar("HOOKSHOT", "green")]),
    "frag_grenade": ("Frag Grenade", "dark_green", "tnt", 10, ["Throws a grenade that explodes on landing.", "10 damage to everything within 4 blocks"], [
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
    "chainsaw": ("Chainsaw", "red", "shears", 12, ["Saws the enemy right in front of you.", "4 blocks · 14 damage · +4 absorption hearts on a hit"], [
        *ray(8),
        hit(damage(14)), hit("particle minecraft:block{block_state:\"minecraft:redstone_block\"} ~ ~1 ~ 0.3 0.5 0.3 0.2 40"),
        "execute if entity @e[tag=pvp.hit] run effect give @s minecraft:absorption 8 1",
        snd("entity.ravager.attack", 1, 1.4), snd("block.grindstone.use", 1, 0.6), bar("RIP AND TEAR", "red")]),
    "rip_tear": ("Berserk Rune", "dark_red", "redstone", 25, ["Goes berserk for 6 seconds.", "Strength II · Speed II · Resistance I"], [
        "effect give @s minecraft:strength 6 1", "effect give @s minecraft:speed 6 1", "effect give @s minecraft:resistance 6 0",
        "particle minecraft:angry_villager ~ ~1 ~ 0.5 0.6 0.5 0 12",
        snd("entity.ravager.roar", 1, 0.8), bar("BERSERK", "dark_red")]),
    "igni": ("Igni", "gold", "blaze_powder", 8, ["Casts a fan of 3 fireballs.", "Sets whatever they hit on fire"], [
        *shoot("small_fireball", 1.3, ",acceleration_power:0.0d", (-12, 0, 12)),
        snd("entity.blaze.shoot", 1, 0.8), bar("IGNI", "gold")]),
    "quen": ("Quen", "yellow", "amethyst_shard", 16, ["Raises a protective shield.", "4 absorption hearts (10 s) · Resistance I 6 s"], [
        "effect clear @s minecraft:absorption", "effect give @s minecraft:absorption 10 1", "effect give @s minecraft:resistance 6 0",
        "particle minecraft:totem_of_undying ~ ~1 ~ 0.5 0.8 0.5 0.1 30",
        snd("block.amethyst_block.chime", 1, 0.6), snd("block.beacon.power_select", 0.6, 1.6), bar("QUEN", "yellow")]),
    # ---------------------------------------------------------------- Smash Bros
    "fireball": ("Fireball", "red", "fire_charge", 3, ["Throws a fireball.", "Sets whatever it hits on fire"], [
        *shoot("small_fireball", 1.0, ",acceleration_power:0.0d"), snd("entity.blaze.shoot", 0.8, 1.6), bar("FIREBALL", "red")]),
    "super_jump": ("Super Jump Punch", "gold", "gold_nugget", 8, ["Leaps up with a rising uppercut.", "2.5 blocks · 6 damage · launches enemies up"], [
        LAUNCH, around(2.5, damage(6)), around(2.5, "effect give @s minecraft:levitation 1 3"),
        "particle minecraft:wax_on ~ ~1.5 ~ 0.4 0.6 0.4 0.1 20",
        snd("entity.experience_orb.pickup", 1, 1.8), snd("entity.player.attack.strong", 1, 1), bar("SUPER JUMP PUNCH", "gold")]),
    "thunder_jolt": ("Thunder Jolt", "yellow", "glowstone_dust", 4, ["Zaps the enemy you aim at.", "16 blocks · 6 damage · Slowness II 2 s"], [
        *ray(32),
        hit(damage(6, "lightning_bolt")), hit("effect give @s minecraft:slowness 2 1"), hit("effect give @s minecraft:glowing 2 0"),
        hit("particle minecraft:electric_spark ~ ~1 ~ 0.3 0.6 0.3 0.4 40"),
        "execute anchored eyes run particle minecraft:electric_spark ^ ^ ^1 0.1 0.1 0.1 0.3 15",
        snd("item.trident.thunder", 0.4, 1.8), bar("PIKA!", "yellow")]),
    "quick_attack": ("Quick Attack", "yellow", "feather", 6, ["Dashes forward at high speed.", "Speed II for 2 s"], [
        DASH, "effect give @s minecraft:speed 2 1", "particle minecraft:cloud ~ ~0.2 ~ 0.3 0.1 0.3 0.05 15",
        snd("entity.breeze.jump", 1, 1.6), bar("QUICK ATTACK", "yellow")]),
    "inhale": ("Inhale", "light_purple", "pink_petals", 10, ["Sucks in the enemy you aim at.", "10 blocks · 5 damage · +2 absorption hearts"], [
        *ray(20),
        "execute rotated ~ 0 positioned ^ ^ ^1.5 run tp @e[tag=pvp.hit,limit=1] ~ ~ ~",
        hit(damage(5)),
        "execute if entity @e[tag=pvp.hit] run effect give @s minecraft:absorption 10 0",
        "execute anchored eyes run particle minecraft:cloud ^ ^ ^2 0.6 0.4 0.6 0.05 25",
        snd("entity.player.breath", 1, 0.5), snd("entity.player.burp", 1, 1.2), bar("INHALE", "light_purple")]),
    "stone": ("Stone", "gray", "cobblestone", 12, ["Turns you to stone and slams down.", "Immune but rooted 3 s · 6 damage within 3 blocks"], [
        "effect give @s minecraft:resistance 3 4", "effect give @s minecraft:slowness 3 5",
        around(3, damage(6)), around(3, PUSH),
        "particle minecraft:block{block_state:\"minecraft:stone\"} ~ ~0.5 ~ 1 0.3 1 0.2 50",
        snd("entity.iron_golem.damage", 1, 0.6), snd("block.stone.place", 1, 0.5), bar("STONE", "gray")]),
    "charge_shot": ("Charge Shot", "gold", "magma_cream", 6, ["Fires an explosive plasma shot.", "Explodes where it hits"], [
        *shoot("fireball", 1.3, ",ExplosionPower:1b,acceleration_power:0.0d"), snd("entity.blaze.shoot", 1, 0.5),
        snd("block.beacon.deactivate", 0.6, 2), bar("CHARGE SHOT", "gold")]),
    "screw_attack": ("Screw Attack", "aqua", "prismarine_crystals", 8, ["Spins upward, hitting everything nearby.", "3 blocks · 6 damage · knockback"], [
        LAUNCH, around(3, damage(6)), around(3, PUSH),
        "particle minecraft:electric_spark ~ ~1 ~ 0.6 1 0.6 0.4 50",
        snd("entity.breeze.wind_burst", 1, 1.4), bar("SCREW ATTACK", "aqua")]),
    # ---------------------------------------------------------------- South Park / Fallout
    "tegridy": ("Tegridy", "green", "fern", 20, ["Samples some Tegridy Farms product.", "Regeneration II + Speed I for 6 s"], [
        "effect give @s minecraft:regeneration 6 1", "effect give @s minecraft:speed 6 0",
        "particle minecraft:campfire_cosy_smoke ~ ~1.8 ~ 0.2 0.2 0.2 0.01 12",
        snd("entity.player.breath", 1, 0.6), bar("TEGRIDY", "green")]),
    "wassup_bruh": ("Wassup Bruh", "aqua", "goat_horn", 22, ["Randy is feeling it.", "Strength II 8 s · your punches hit much harder"], [
        "effect give @s minecraft:strength 8 1",
        "particle minecraft:note ~ ~2.2 ~ 0.4 0.2 0.4 1 6", "particle minecraft:crit ~ ~1 ~ 0.4 0.6 0.4 0.2 20",
        snd("entity.villager.celebrate", 1, 0.7), snd("entity.player.levelup", 0.6, 1.4), bar("WASSUP BRUH", "aqua")]),
    "vats": ("V.A.T.S.", "green", "spyglass", 18, ["Slows time for every enemy near you.", "12 blocks · Slowness III + glowing 5 s · you: Strength I"], [
        around(12, "effect give @s minecraft:slowness 5 2"), around(12, "effect give @s minecraft:glowing 5 0"),
        "effect give @s minecraft:strength 5 0",
        "particle minecraft:happy_villager ~ ~1 ~ 4 1 4 0 40",
        snd("block.beacon.activate", 1, 1.6), snd("block.note_block.bit", 1, 0.8), bar("V.A.T.S. ENGAGED", "green")]),
    "stimpak": ("Stimpak", "red", "glistering_melon_slice", 15, ["Injects a Stimpak.", "Instant Health II + Regeneration II 4 s"], [
        "effect give @s minecraft:instant_health 1 1", "effect give @s minecraft:regeneration 4 1",
        "particle minecraft:heart ~ ~1.5 ~ 0.4 0.3 0.4 0 6",
        snd("entity.bee.sting", 1, 1.4), bar("STIMPAK", "red")]),
    # ---------------------------------------------------------------- Sonic / Breaking Bad / Minecraft / DK / Mandalorian
    "spin_dash": ("Spin Dash", "blue", "lapis_lazuli", 6, ["Revs up and rockets forward.", "Speed III 2 s · 5 damage + knockback up close"], [
        DASH, "effect give @s minecraft:speed 2 2", cone(2.5, damage(5)), cone(2.5, PUSH),
        "particle minecraft:dust{color:[0.1,0.3,1.0],scale:1.5} ~ ~0.5 ~ 0.4 0.3 0.4 0 30",
        snd("entity.breeze.charge", 1, 1.8), snd("entity.breeze.jump", 1, 1.4), bar("SPIN DASH", "blue")]),
    "homing_attack": ("Homing Attack", "gold", "gold_ingot", 8, ["Homes in on the enemy you aim at.", "12 blocks · 7 damage · you bounce off them"], [
        *ray(24),
        "execute at @e[tag=pvp.hit,limit=1] run tp @s ~ ~1.2 ~",
        hit(damage(7)), hit("particle minecraft:crit ~ ~1 ~ 0.3 0.5 0.3 0.3 25"),
        "execute if entity @e[tag=pvp.hit] at @s run " + LAUNCH,
        "execute unless entity @e[tag=pvp.hit] run " + snd("entity.item.pickup", 0.6, 0.6),
        snd("entity.experience_orb.pickup", 1, 1.4), bar("HOMING ATTACK", "gold")]),
    "say_my_name": ("Say My Name", "dark_gray", "name_tag", 22, ["Everyone near you knows who you are.", "10 blocks · Weakness II + Slowness I 6 s · you: Resistance I"], [
        around(10, "effect give @s minecraft:weakness 6 1"), around(10, "effect give @s minecraft:slowness 6 0"),
        around(10, "effect give @s minecraft:glowing 6 0"), "effect give @s minecraft:resistance 6 0",
        "particle minecraft:smoke ~ ~1 ~ 3 0.5 3 0.02 60",
        snd("entity.warden.heartbeat", 1, 0.6), snd("block.bell.resonate", 0.6, 0.5), bar("SAY MY NAME.", "dark_gray")]),
    "fulminate": ("Fulminated Mercury", "white", "quartz", 10, ["Throws a 'crystal' that blows up.", "Explodes where it hits"], [
        *shoot("fireball", 1.2, ",ExplosionPower:1b,acceleration_power:0.0d"),
        snd("entity.snowball.throw", 1, 0.5), snd("block.glass.break", 0.6, 1.6), bar("THIS IS NOT METH", "white")]),
    "smite": ("Smite", "white", "end_rod", 10, ["Strikes the enemy you aim at from the sky.", "24 blocks · 7 damage · Blindness 2 s"], [
        *ray(48),
        hit(damage(7, "lightning_bolt")), hit("effect give @s minecraft:blindness 2 0"),
        hit("particle minecraft:end_rod ~ ~4 ~ 0.05 3 0.05 0 60"), hit("particle minecraft:electric_spark ~ ~1 ~ 0.4 0.6 0.4 0.4 40"),
        hit(snd("entity.lightning_bolt.thunder", 0.5, 1.4)),
        "execute unless entity @e[tag=pvp.hit] run " + snd("block.fire.extinguish", 0.5, 1.5), bar("YOU WERE NEVER ALONE", "white")]),
    "haunt": ("Haunt", "dark_gray", "ender_pearl", 12, ["Vanishes and appears behind the nearest enemy.", "16 blocks · they're blinded 2 s · you: Invisibility 2 s"], [
        f"execute as @e[distance=..16,{TGT},sort=nearest,limit=1] run effect give @s minecraft:blindness 2 0",
        "particle minecraft:large_smoke ~ ~1 ~ 0.3 0.6 0.3 0.02 20",
        f"execute as @e[distance=..16,{TGT},sort=nearest,limit=1] at @s rotated ~ 0 positioned ^ ^ ^-1.5 run tp @p[tag=pvp.caster] ~ ~ ~ facing entity @s eyes",
        "effect give @s minecraft:invisibility 2 0 true",
        snd("entity.enderman.teleport", 1, 0.5), snd("ambient.cave", 0.8, 1), bar("HAUNT", "dark_gray")]),
    "giant_punch": ("Giant Punch", "gold", "cocoa_beans", 9, ["A huge wind-up punch.", "4 blocks · 12 damage · sends them flying"], [
        *ray(8),
        hit(damage(12)), hit(PUSH), hit("effect give @s minecraft:levitation 1 1"),
        hit("particle minecraft:explosion ~ ~1 ~ 0 0 0 0 1"),
        snd("entity.player.attack.knockback", 1, 0.5), snd("entity.iron_golem.attack", 1, 0.6), bar("GIANT PUNCH", "gold")]),
    "ground_pound": ("Ground Pound", "dark_red", "anvil", 10, ["Pounds the ground around you.", "5 blocks · 6 damage · Slowness III 2 s · pops them up"], [
        around(5, damage(6)), around(5, "effect give @s minecraft:slowness 2 2"), around(5, "effect give @s minecraft:levitation 1 0"),
        "particle minecraft:block{block_state:\"minecraft:dirt\"} ~ ~0.2 ~ 2 0.2 2 0.2 80",
        snd("entity.warden.attack_impact", 1, 0.6), snd("block.anvil.land", 0.6, 0.6), bar("GROUND POUND", "dark_red")]),
    "jetpack": ("Jetpack", "gray", "firework_rocket", 9, ["Blasts you into the air.", "Then Slow Falling for 6 s"], [
        LAUNCH, "effect give @s minecraft:levitation 1 2 true", "effect give @s minecraft:slow_falling 6 0 true",
        "particle minecraft:flame ~ ~0.2 ~ 0.2 0.1 0.2 0.05 30", "particle minecraft:campfire_cosy_smoke ~ ~0.2 ~ 0.3 0.1 0.3 0.02 8",
        snd("entity.firework_rocket.launch", 1, 0.6), snd("block.fire.ambient", 1, 0.5), bar("JETPACK", "gray")]),
    "flamethrower": ("Flamethrower", "gold", "flint_and_steel", 9, ["Sprays fire in front of you.", "4 blocks · 5 damage · sets them on fire"], [
        cone(4, damage(5, "in_fire")),
        *shoot("small_fireball", 1.0, ",acceleration_power:0.0d", (-8, 0, 8)),
        "execute anchored eyes run particle minecraft:flame ^ ^ ^2 0.6 0.4 0.6 0.05 60",
        snd("item.firecharge.use", 1, 0.6), snd("entity.blaze.burn", 1, 0.8), bar("THIS IS THE WAY", "gold")]),
    # ---------------------------------------------------------------- Angry Birds
    "fling": ("Fling", "red", "string", 8, ["Slingshots you forward like a bird.", "Crash into enemies or land: 7 damage within 3 blocks"], [
        "tag @s add pvp.sling", "scoreboard players set @s pvp.ft 0", DASH, LAUNCH, "effect give @s minecraft:resistance 2 1 true",
        "particle minecraft:cloud ~ ~0.3 ~ 0.3 0.1 0.3 0.05 12",
        snd("item.crossbow.shoot", 1, 0.6), snd("entity.parrot.ambient", 1, 0.6), bar("FLING", "red")]),
    "battle_cry": ("Battle Cry", "dark_red", "red_dye", 18, ["Lets out a furious squawk.", "6 blocks · 4 damage + knockback · you: Strength I + Speed I 6 s"], [
        around(6, damage(4)), around(6, PUSH), around(6, "effect give @s minecraft:slowness 2 0"),
        "effect give @s minecraft:strength 6 0", "effect give @s minecraft:speed 6 0",
        "particle minecraft:angry_villager ~ ~1.2 ~ 1.5 0.6 1.5 0 15",
        snd("entity.ravager.roar", 1, 1.8), snd("entity.parrot.hurt", 1, 0.5), bar("BATTLE CRY", "dark_red")]),
    # ---------------------------------------------------------------- Marvel / DreamWorks / Family Guy / Simpsons / Star Wars
    "web_shot": ("Web Shot", "white", "cobweb", 9, ["Webs up the enemy you aim at.", "20 blocks · stuck in place 2 s · 3 damage"], [
        *ray(40),
        hit(damage(3)), hit("effect give @s minecraft:slowness 2 6"), hit("effect give @s minecraft:mining_fatigue 2 2"),
        hit("particle minecraft:item{item:\"minecraft:cobweb\"} ~ ~1 ~ 0.4 0.6 0.4 0.05 30"),
        "execute anchored eyes run particle minecraft:item{item:\"minecraft:string\"} ^ ^ ^2 0.1 0.1 0.1 0.2 15",
        snd("entity.spider.step", 1, 1.6), snd("block.wool.place", 1, 0.6), bar("THWIP", "white")]),
    "web_swing": ("Web Swing", "red", "tripwire_hook", 7, ["Swings you forward on a web line.", "Then Slow Falling 3 s"], [
        DASH, LAUNCH, "effect give @s minecraft:slow_falling 3 0 true", "effect give @s minecraft:speed 3 1 true",
        "execute anchored eyes run particle minecraft:item{item:\"minecraft:string\"} ^ ^1 ^4 0.1 1 0.1 0.05 20",
        snd("entity.fishing_bobber.throw", 1, 0.6), snd("entity.breeze.jump", 0.6, 1.4), bar("WEB SWING", "red")]),
    "swamp_roar": ("Swamp Roar", "green", "slime_ball", 14, ["Roars at everyone around you.", "6 blocks · 4 damage + knockback · Nausea 4 s + Slowness I 3 s"], [
        around(6, damage(4)), around(6, PUSH), around(6, "effect give @s minecraft:nausea 4 0"), around(6, "effect give @s minecraft:slowness 3 0"),
        "particle minecraft:item_slime ~ ~1.5 ~ 1.5 0.5 1.5 0.1 40",
        snd("entity.ravager.roar", 1, 0.7), snd("entity.slime.squish", 1, 0.5), bar("WHAT ARE YOU DOING IN MY SWAMP?!", "green")]),
    "onion_layers": ("Onion Layers", "dark_green", "beetroot", 20, ["Ogres are like onions: they have layers.", "8 absorption hearts 12 s · Resistance I 6 s"], [
        "effect clear @s minecraft:absorption", "effect give @s minecraft:absorption 12 3", "effect give @s minecraft:resistance 6 0",
        "particle minecraft:composter ~ ~1 ~ 0.5 0.8 0.5 0 25",
        snd("block.composter.fill_success", 1, 0.6), bar("LAYERS", "dark_green")]),
    "chicken_fight": ("Chicken Fight", "yellow", "cooked_chicken", 30, ["Time to fight the giant chicken.", "Strength II + Resistance I + Speed I 10 s"], [
        "effect give @s minecraft:strength 10 1", "effect give @s minecraft:resistance 10 0", "effect give @s minecraft:speed 10 0",
        "particle minecraft:item{item:\"minecraft:feather\"} ~ ~1 ~ 0.8 0.8 0.8 0.1 30",
        snd("entity.chicken.hurt", 1, 0.5), snd("entity.player.attack.strong", 1, 0.8), bar("CHICKEN FIGHT", "yellow")]),
    "surfin_bird": ("Surfin' Bird", "aqua", "music_disc_cat", 20, ["Everyone near you hears the word.", "8 blocks · Nausea 6 s · Slowness II 4 s · Weakness I 4 s"], [
        around(8, "effect give @s minecraft:nausea 6 0"), around(8, "effect give @s minecraft:slowness 4 1"), around(8, "effect give @s minecraft:weakness 4 0"),
        "particle minecraft:note ~ ~2 ~ 3 1 3 1 30",
        snd("block.note_block.bass", 1, 0.5), snd("block.note_block.didgeridoo", 1, 0.8), bar("THE BIRD IS THE WORD", "aqua")]),
    "donut": ("Donut", "light_purple", "cookie", 14, ["Mmm... donuts.", "Instant Health I · Regeneration II 4 s · full hunger"], [
        "effect give @s minecraft:instant_health 1 0", "effect give @s minecraft:regeneration 4 1", "effect give @s minecraft:saturation 1 9 true",
        "particle minecraft:item{item:\"minecraft:cookie\"} ~ ~1.6 ~ 0.2 0.1 0.2 0.05 10",
        snd("entity.generic.eat", 1, 0.8), snd("entity.player.burp", 1, 0.7), bar("MMM... DONUTS", "light_purple")]),
    "belly_bump": ("Belly Bump", "yellow", "honeycomb", 8, ["Bumps everyone in front of you.", "6 blocks · 5 damage + big knockback"], [
        cone(3, damage(5)), cone(3, PUSH), cone(3, "effect give @s minecraft:levitation 1 0"),
        "execute anchored eyes run particle minecraft:poof ^ ^-0.6 ^1.5 0.6 0.3 0.6 0.05 15",
        snd("entity.slime.jump", 1, 0.5), snd("entity.player.attack.knockback", 1, 0.6), bar("D'OH!", "yellow")]),
    "saber_throw": ("Saber Throw", "red", "redstone_torch", 9, ["Hurls your saber at the enemy you aim at.", "16 blocks · 8 damage · Slowness I 2 s"], [
        *ray(32),
        hit(damage(8)), hit("effect give @s minecraft:slowness 2 0"),
        hit("particle minecraft:dust{color:[1.0,0.0,0.0],scale:1.5} ~ ~1 ~ 0.4 0.6 0.4 0 30"),
        "execute anchored eyes run particle minecraft:dust{color:[1.0,0.1,0.1],scale:1.2} ^ ^ ^3 0.1 0.1 2 0 30",
        snd("item.trident.throw", 1, 0.7), snd("block.beacon.ambient", 1, 2), bar("SABER THROW", "red")]),
    "saber_spin": ("Saber Spin", "dark_red", "nether_wart", 7, ["Spins your double-bladed saber.", "3.5 blocks · 7 damage · knockback"], [
        around(3.5, damage(7)), around(3.5, PUSH),
        "particle minecraft:dust{color:[1.0,0.0,0.0],scale:1.5} ~ ~1 ~ 1.5 0.2 1.5 0 50", "particle minecraft:sweep_attack ~ ~1 ~ 1 0 1 0 4",
        snd("entity.player.attack.sweep", 1, 0.6), snd("block.beacon.ambient", 1, 2), bar("SABER SPIN", "dark_red")]),
    # ---------------------------------------------------------------- SpongeBob / Better Call Saul
    "claw_pinch": ("Claw Pinch", "red", "turtle_scute", 7, ["Pinches the enemy right in front of you.", "4 blocks · 8 damage · Slowness II 2 s"], [
        *ray(8),
        hit(damage(8)), hit("effect give @s minecraft:slowness 2 1"),
        hit("particle minecraft:damage_indicator ~ ~1 ~ 0.3 0.4 0.3 0.1 8"),
        snd("entity.turtle.egg_crack", 1, 0.6), snd("entity.player.attack.crit", 1, 0.8), bar("PINCH", "red")]),
    "money_grab": ("Money Grab", "gold", "raw_gold", 14, ["Drags everyone near you closer. Money!", "6 blocks · pulled 2 blocks in · Weakness I 4 s · you: Strength I 5 s"], [
        f"execute as @e[distance=..6,{TGT}] at @s facing entity @p[tag=pvp.caster] feet run tp @s ^ ^ ^2",
        around(6, "effect give @s minecraft:weakness 4 0"), "effect give @s minecraft:strength 5 0",
        "particle minecraft:item{item:\"minecraft:gold_nugget\"} ~ ~1.5 ~ 2 0.6 2 0.1 40",
        snd("entity.experience_orb.pickup", 1, 0.6), snd("block.chain.place", 1, 0.8), bar("MONEY! MONEY! MONEY!", "gold")]),
    "served": ("You've Been Served", "yellow", "paper", 16, ["Serves papers to the enemy you aim at.", "16 blocks · 5 damage · Weakness II + glowing 5 s · you heal 4"], [
        *ray(32),
        hit(damage(5, "magic")), hit("effect give @s minecraft:weakness 5 1"), hit("effect give @s minecraft:glowing 5 0"),
        hit("particle minecraft:item{item:\"minecraft:paper\"} ~ ~1.2 ~ 0.3 0.4 0.3 0.1 20"),
        "execute if entity @e[tag=pvp.hit] run effect give @s minecraft:instant_health 1 0",
        "execute anchored eyes run particle minecraft:item{item:\"minecraft:paper\"} ^ ^ ^2 0.1 0.1 1 0.05 12",
        "execute unless entity @e[tag=pvp.hit] run " + snd("item.book.page_turn", 0.6, 0.6),
        snd("entity.villager.work_cartographer", 1, 1.2), snd("block.note_block.bell", 1, 1.2), bar("YOU'VE BEEN SERVED", "yellow")]),
    "loophole": ("Loophole", "gold", "book", 20, ["Finds a loophole: untouchable for 1.5 s.", "Clears Slowness, Weakness, Poison, Wither, Blindness · Speed II 3 s"], [
        *[f"effect clear @s minecraft:{e}" for e in ("slowness", "weakness", "poison", "wither", "blindness", "nausea", "levitation")],
        "effect give @s minecraft:resistance 2 4 true", "effect give @s minecraft:speed 3 1",
        "particle minecraft:enchant ~ ~1 ~ 0.4 0.8 0.4 0.6 40",
        snd("item.book.page_turn", 1, 0.8), snd("block.note_block.bell", 1, 1.6), bar("IT'S ALL ABOUT LOOPHOLES", "gold")]),
    "fingertips": ("Fingertip Lightning", "aqua", "glow_ink_sac", 10, ["Lightning bolts shoot from your fingertips.", "16 blocks · 6 damage · arcs to enemies within 3 blocks of it (3 damage)"], [
        *ray(32),
        "execute anchored eyes run particle minecraft:electric_spark ^ ^ ^2 0.1 0.1 1.5 0.3 40",
        "execute anchored eyes run particle minecraft:electric_spark ^ ^ ^5 0.1 0.1 2 0.3 40",
        f"execute at @e[tag=pvp.hit,limit=1] as @e[distance=..3,{TGT},tag=!pvp.hit] at @s run {damage(3, 'lightning_bolt')}",
        f"execute at @e[tag=pvp.hit,limit=1] as @e[distance=..3,{TGT},tag=!pvp.hit] at @s run particle minecraft:electric_spark ~ ~1 ~ 0.3 0.5 0.3 0.3 15",
        hit(damage(6, "lightning_bolt")), hit("effect give @s minecraft:slowness 1 1"),
        hit("particle minecraft:electric_spark ~ ~1 ~ 0.4 0.7 0.4 0.5 50"),
        snd("entity.lightning_bolt.thunder", 0.3, 2), snd("block.respawn_anchor.deplete", 0.8, 1.8),
        bar("LIGHTNING BOLTS SHOOT FROM MY FINGERTIPS", "aqua")]),
    # ---------------------------------------------------------------- Edgerunners (Lucy)
    "short_circuit": ("Short Circuit", "aqua", "repeater", 8, ["Quickhack: fries the enemy you aim at.", "20 blocks · 5 damage · Slowness II 2 s · revealed 3 s"], [
        *ray(40),
        hit(damage(5, "lightning_bolt")), hit("effect give @s minecraft:slowness 2 1"), hit("effect give @s minecraft:glowing 3 0"),
        hit("particle minecraft:electric_spark ~ ~1 ~ 0.3 0.6 0.3 0.4 40"),
        hit("particle minecraft:dust{color:[0.3,1.0,1.0],scale:1.0} ~ ~1.8 ~ 0.3 0.2 0.3 0 20"),
        snd("block.beacon.deactivate", 1, 2), snd("block.respawn_anchor.deplete", 0.6, 2), bar("QUICKHACK: SHORT CIRCUIT", "aqua")]),
    "optical_camo": ("Optical Camo", "light_purple", "glass_pane", 25, ["Bends light around you.", "Invisibility + Speed I 6 s"], [
        "effect give @s minecraft:invisibility 6 0 true", "effect give @s minecraft:speed 6 0 true",
        "particle minecraft:dust{color:[0.7,0.6,1.0],scale:1.0} ~ ~1 ~ 0.3 0.8 0.3 0 40",
        snd("block.beacon.power_select", 0.8, 2), snd("entity.illusioner.mirror_move", 1, 1.4), bar("OPTICAL CAMO", "light_purple")]),
    "overclock": ("Overclock", "aqua", "observer", 20, ["Push your chrome past the limit.", "Strength II + Speed II 6 s · costs some health"], [
        "damage @s 4 minecraft:magic", "effect give @s minecraft:strength 6 1", "effect give @s minecraft:speed 6 1",
        "effect give @s minecraft:nausea 2 0 true",
        "particle minecraft:dust{color:[0.2,1.0,0.9],scale:1.2} ~ ~1 ~ 0.4 0.8 0.4 0 40", "particle minecraft:electric_spark ~ ~1 ~ 0.4 0.8 0.4 0.3 25",
        snd("block.beacon.power_select", 1, 1.6), snd("entity.warden.heartbeat", 1, 1.4), bar("OVERCLOCK", "aqua")]),
    "borg_slam": ("Borg Slam", "dark_red", "heavy_core", 14, ["Leaps high, then crashes down.", "Landing: 10 damage within 5 blocks · knockback · Slowness II 2 s"], [
        "tag @s add pvp.slam", "scoreboard players set @s pvp.ft 0", LAUNCH, "effect give @s minecraft:levitation 1 3 true",
        "effect give @s minecraft:resistance 4 2 true",   # no fall damage from his own slam
        "particle minecraft:large_smoke ~ ~0.3 ~ 0.4 0.1 0.4 0.05 20",
        snd("entity.iron_golem.attack", 1, 0.5), snd("entity.wind_charge.wind_burst", 1, 0.6), bar("BORG SLAM", "dark_red")]),
    # ---------------------------------------------------------------- Team Fortress 2
    "jarate": ("Jarate", "yellow", "honey_bottle", 16, ["Throws a jar of... something.", "Splash: Weakness II + glowing 8 s, Slowness I 3 s"], [
        *shoot("splash_potion", 0.9, ',Item:{id:"minecraft:splash_potion",count:1,components:{"minecraft:potion_contents":{custom_color:15128576,'
               'custom_effects:[{id:"minecraft:weakness",amplifier:1b,duration:160},{id:"minecraft:glowing",duration:160},{id:"minecraft:slowness",duration:60}]}}}'),
        snd("entity.splash_potion.throw", 1, 0.7), bar("JARATE!", "yellow")]),
    "focus": ("Focus", "dark_green", "compass", 20, ["Spots every enemy in the area.", "40 blocks · they glow 6 s"], [
        around(40, "effect give @s minecraft:glowing 6 0"),
        "particle minecraft:end_rod ~ ~1.6 ~ 0.3 0.3 0.3 0.02 10",
        snd("block.note_block.hat", 1, 0.6), snd("item.spyglass.use", 1, 0.8), bar("PROFESSIONALS HAVE STANDARDS", "dark_green")]),
    # ---------------------------------------------------------------- guns (hitscan; no arrows)
    "ma5": gun("MA5 Assault Rifle", "dark_green", "netherite_hoe", 0.4, 4, 32, "UNSC standard issue.", "entity.firework_rocket.blast", 1.6),
    "super_shotgun": shotgun("Super Shotgun", "red", "crossbow", 1.2, 10, 3.5, "Both barrels.", "entity.generic.explode", 1.6),
    "lucky": gun("Lucky", "gold", "iron_hoe", 1.0, 8, 40, "A .357 revolver. Lucky.", "entity.firework_rocket.blast", 0.8),
    "heavy_cannon": gun("Militech Heavy Cannon", "dark_red", "diamond_hoe", 1.0, 8, 32, "Arm-mounted heavy cannon.", "entity.generic.explode", 1.2,
                        [("Slowness I 1 s", "effect give @s minecraft:slowness 1 0"), ("", "particle minecraft:explosion ~ ~1 ~ 0 0 0 0 1")]),
    "guts": shotgun("Guts", "light_purple", "golden_hoe", 1.0, 9, 3, "Rebecca's oversized shotgun.", "entity.generic.explode", 1.8),
    "pistol": gun("Pistol", "aqua", "stone_hoe", 0.35, 3, 28, "Quick sidearm.", "entity.firework_rocket.blast", 1.9),
    "m60": gun("Trunk M60", "dark_gray", "netherite_shovel", 0.25, 3, 32, "The machine gun from the trunk.", "entity.firework_rocket.blast", 1.8),
    "power_beam": gun("Arm Cannon", "gold", "orange_dye", 0.5, 5, 36, "Samus's Power Beam.", "block.beacon.deactivate", 2.0,
                      [("", "particle minecraft:electric_spark ~ ~1 ~ 0.2 0.4 0.2 0.3 12")]),
    "militech_handgun": gun("Militech Handgun", "yellow", "wooden_hoe", 0.6, 6, 30, "David's sidearm.", "entity.firework_rocket.blast", 1.3),
    # the Outbreak quest reward (3 Power Cells at the Arsenal); not in any kit
    "annihilator": gun("Annihilator", "light_purple", "end_crystal", 0.8, 24, 50, "The Outbreak's ultimate wonder weapon.", "entity.wither.shoot", 1.4,
                       [("8 damage to everything within 3 blocks of the hit", around(3, damage(8, "magic"))),
                        ("", "particle minecraft:explosion ~ ~1 ~ 0 0 0 0 1"), ("", "particle minecraft:end_rod ~ ~1 ~ 0.6 0.6 0.6 0.1 25")]),
    "amban": gun("Amban Rifle", "gray", "iron_shovel", 2.5, 12, 60, "Disintegration sniper rifle.", "block.beacon.deactivate", 1.8,
                 [("glowing 3 s", "effect give @s minecraft:glowing 3 0"), ("", "particle minecraft:electric_spark ~ ~1 ~ 0.3 0.5 0.3 0.3 20")]),
    # ---------------------------------------------------------------- King of the Hill / Futurama / Mr. Robot
    "propane": ("Propane Tank", "aqua", "lantern", 10, ["Lobs a propane tank that blows up.", "Explodes where it hits"], [
        *shoot("fireball", 1.0, ",ExplosionPower:1b,acceleration_power:0.0d"),
        snd("entity.snowball.throw", 1, 0.5), snd("block.fire.ambient", 1, 1.4), bar("PROPANE AND PROPANE ACCESSORIES", "aqua")]),
    "kick_your_ass": ("I'm Gonna Kick Your Ass", "red", "leather", 22, ["Hank has had it.", "Strength II + Speed I 6 s · knocks back enemies within 3 blocks"], [
        "effect give @s minecraft:strength 6 1", "effect give @s minecraft:speed 6 0", around(3, PUSH),
        "particle minecraft:angry_villager ~ ~2 ~ 0.4 0.3 0.4 0 6",
        snd("entity.villager.no", 1, 0.6), snd("entity.player.attack.strong", 1, 0.8), bar("I'M GONNA KICK YOUR ASS!", "red")]),
    "leela_kick": ("Martial Arts Kick", "light_purple", "rabbit_foot", 7, ["A flying kick forward.", "Dash · 7 damage + knockback up close"], [
        DASH, cone(3, damage(7)), cone(3, PUSH),
        "particle minecraft:sweep_attack ^ ^1 ^1.5 0 0 0 0 1", "particle minecraft:crit ~ ~1 ~ 0.4 0.4 0.4 0.3 15",
        snd("entity.player.attack.knockback", 1, 1.2), snd("entity.breeze.jump", 1, 1.4), bar("HI-YAH!", "light_purple")]),
    "laser_pistol": ("Laser Pistol", "red", "prismarine_shard", 5, ["Zaps the enemy you aim at.", "20 blocks · 5 damage · glowing 2 s"], [
        *ray(40),
        hit(damage(5, "magic")), hit("effect give @s minecraft:glowing 2 0"),
        hit("particle minecraft:dust{color:[1.0,0.1,0.1],scale:1.2} ~ ~1 ~ 0.3 0.5 0.3 0 25"),
        "execute anchored eyes run particle minecraft:dust{color:[1.0,0.2,0.2],scale:0.8} ^ ^ ^3 0.05 0.05 2 0 30",
        snd("block.beacon.deactivate", 1, 2), snd("entity.guardian.attack", 0.5, 2), bar("PEW", "red")]),
    "blackout": ("Blackout", "dark_gray", "command_block", 22, ["Hacks the grid around you.", "12 blocks · Darkness 6 s + Blindness 2 s + Slowness I 3 s"], [
        around(12, "effect give @s minecraft:darkness 6 0"), around(12, "effect give @s minecraft:blindness 2 0"),
        around(12, "effect give @s minecraft:slowness 3 0"),
        "particle minecraft:dust{color:[0.0,1.0,0.3],scale:0.8} ~ ~1.5 ~ 3 1 3 0 60",
        snd("block.beacon.deactivate", 1, 0.6), snd("block.note_block.bit", 1, 0.5), bar("FSOCIETY", "dark_gray")]),
    "mr_robot": ("Mr. Robot", "red", "black_dye", 25, ["Your other self takes over.", "Strength II + Resistance I 6 s · Speed I"], [
        "effect give @s minecraft:strength 6 1", "effect give @s minecraft:resistance 6 0", "effect give @s minecraft:speed 6 0",
        "particle minecraft:dust{color:[0.8,0.0,0.0],scale:1.0} ~ ~1 ~ 0.4 0.8 0.4 0 40",
        snd("entity.warden.heartbeat", 1, 1), snd("block.note_block.bit", 1, 1.6), bar("HELLO, FRIEND.", "red")]),
    # ---------------------------------------------------------------- The Sopranos / SpongeBob / Futurama
    "gabagool": ("Gabagool", "gold", "porkchop", 15, ["A little gabagool.", "Instant Health I · Regeneration II 4 s · full hunger"], [
        "effect give @s minecraft:instant_health 1 0", "effect give @s minecraft:regeneration 4 1", "effect give @s minecraft:saturation 1 9 true",
        "particle minecraft:item{item:\"minecraft:porkchop\"} ~ ~1.6 ~ 0.2 0.1 0.2 0.05 10",
        snd("entity.generic.eat", 1, 0.7), bar("GABAGOOL!", "gold")]),
    "whack": ("Whack", "dark_red", "flint", 14, ["Puts out a hit on the enemy you aim at.", "16 blocks · 6 damage · Wither I + Slowness II + glowing 4 s"], [
        *ray(32),
        hit(damage(6)), hit("effect give @s minecraft:wither 4 0"), hit("effect give @s minecraft:slowness 4 1"), hit("effect give @s minecraft:glowing 4 0"),
        hit("particle minecraft:smoke ~ ~1 ~ 0.3 0.5 0.3 0.02 25"),
        snd("entity.firework_rocket.blast", 1, 0.5), snd("entity.generic.explode", 0.3, 1.8), bar("IT'S JUST BUSINESS", "dark_red")]),
    "krabby_patty": ("Krabby Patty", "yellow", "bread", 15, ["Fresh off the grill.", "Instant Health I · Regeneration II 5 s · full hunger"], [
        "effect give @s minecraft:instant_health 1 0", "effect give @s minecraft:regeneration 5 1", "effect give @s minecraft:saturation 1 9 true",
        "particle minecraft:item{item:\"minecraft:bread\"} ~ ~1.6 ~ 0.2 0.1 0.2 0.05 10",
        snd("entity.generic.eat", 1, 1.2), snd("block.note_block.chime", 1, 1.6), bar("I'M READY!", "yellow")]),
    "bubble_blower": ("Bubble Blower", "aqua", "glass_bottle", 8, ["Blows three bubbles.", "Each pops with knockback"], [
        *shoot("wind_charge", 0.9, "", (-10, 0, 10)),
        "execute anchored eyes run particle minecraft:bubble_pop ^ ^ ^1.5 0.4 0.3 0.4 0.05 30",
        snd("block.bubble_column.upwards_inside", 1, 1.4), snd("entity.player.breath", 1, 1.6), bar("BUBBLES!", "aqua")]),
    "shiny_metal": ("Bite My Shiny Metal Ass", "gray", "iron_ingot", 18, ["Taunts everyone around you.", "8 blocks · Weakness I + glowing 6 s · you: Resistance I 6 s"], [
        around(8, "effect give @s minecraft:weakness 6 0"), around(8, "effect give @s minecraft:glowing 6 0"),
        "effect give @s minecraft:resistance 6 0",
        "particle minecraft:wax_off ~ ~1 ~ 0.6 0.8 0.6 0.5 30",
        snd("block.anvil.land", 0.6, 1.6), snd("entity.iron_golem.hurt", 1, 1.4), bar("BITE MY SHINY METAL ASS!", "gray")]),
    "olde_fortran": ("Olde Fortran", "gold", "experience_bottle", 20, ["Fuels up on malt liquor.", "Strength I + Speed I + Regeneration I 8 s"], [
        "effect give @s minecraft:strength 8 0", "effect give @s minecraft:speed 8 0", "effect give @s minecraft:regeneration 8 0",
        "particle minecraft:flame ~ ~0.3 ~ 0.2 0.1 0.2 0.03 15",
        snd("entity.generic.drink", 1, 0.8), snd("entity.player.burp", 1, 0.6), bar("OLDE FORTRAN", "gold")]),
}


GUNS += [k for k, v in ABILITIES.items() if any("pve.gun" in l for l in v[5])]   # gun() and shotgun() abilities


BASE = "minecraft:clay_ball"
def give(key): return f"loot give @s loot {NS}:ability/{key}"
# Ability items are told apart by their item model (each is unique). They carry no custom_data on purpose:
# crispy_enchants' migration (for old Advanced Enchantments items) strips lore lines and wipes custom_data from
# any item with a few custom_data keys, every 2 seconds.
def sel(key): return f'{BASE}[minecraft:item_model="minecraft:{ABILITIES[key][2]}"]'


def item_components(key):
    name, color, model, cd, lore, _ = ABILITIES[key]
    comps = {
        "minecraft:item_model": f"minecraft:{model}",
        "minecraft:custom_name": {"text": name, "color": color, "italic": False, "bold": True},
        "minecraft:lore": [{"text": l, "color": "gray", "italic": False} for l in lore]
                          + [{"text": f"Right-click · {cd} s cooldown", "color": "dark_gray", "italic": False}],
        "minecraft:max_stack_size": 1,
        "minecraft:enchantment_glint_override": True,
        "minecraft:consumable": {"consume_seconds": 0.05, "animation": "none", "has_consume_particles": False,
                                 "sound": "minecraft:intentionally_empty"},
        "minecraft:use_cooldown": {"seconds": cd, "cooldown_group": f"pvp:ab_{key}"},
    }
    return comps


def build(fn, wj, lobby_box):
    wj(f"data/{NS}/tags/entity_type/not_target.json", {"values": [f"minecraft:{t}" for t in NOT_TARGET]})
    for idx, (key, (name, color, model, cd, lore, body)) in enumerate(ABILITIES.items(), 1):
        wj(f"data/{NS}/loot_table/ability/{key}.json", {"pools": [{"rolls": 1, "entries": [{
            "type": "minecraft:item", "name": BASE,
            "functions": [{"function": "minecraft:set_components", "components": item_components(key)}]}]}]})
        fn(f"ability/use/{key}", [
            f"scoreboard players set @s pvp.abk {idx}",
            "execute store result score @s pvp.abs run data get entity @s SelectedItemSlot",
            "scoreboard players set @s pvp.rgt 3", "tag @s add pvp.caster",
            f"execute at @s run function {NS}:ability/fx/{key}",
            "tag @s remove pvp.caster", "tag @e[tag=pvp.hit] remove pvp.hit",
        ])
        fn(f"ability/fx/{key}", body)
    # one trigger for every ability item; the reward reads the item still in the hand
    wj(f"data/{NS}/advancement/ability/used.json", {"criteria": {"c": {"trigger": "minecraft:consume_item",
        "conditions": {"item": {"items": BASE}}}}, "rewards": {"function": f"{NS}:ability/used"}})
    fn("ability/used", [f"advancement revoke @s only {NS}:ability/used",
                        "data modify storage pvp:debug last set value {}",
                        "data modify storage pvp:debug last.main set from entity @s SelectedItem",
                        "data modify storage pvp:debug last.off set from entity @s equipment.offhand"]
       + [f"execute if items entity @s {h} {sel(k)} run return run function {NS}:ability/use/{k}"
          for h in ("weapon.mainhand", "weapon.offhand") for k in ABILITIES])
    # give the used item back (it was consumed): its hotbar slot, else the offhand, else anywhere
    fn("ability/regive", ["scoreboard players set @s pvp.rgt 0"] + [
        f"execute if score @s pvp.abk matches {i} run return run function {NS}:ability/regive/{k}" for i, k in enumerate(ABILITIES, 1)])
    for k in ABILITIES:
        mine = sel(k)
        fn(f"ability/regive/{k}", [
            f"execute if entity @s[{lobby_box}] run return 0",
            f"execute if items entity @s container.* {mine} run return 0",
            f"execute if items entity @s weapon.offhand {mine} run return 0",
            *[f"execute if score @s pvp.abs matches {n} unless items entity @s hotbar.{n} * run return run loot replace entity @s hotbar.{n} loot {NS}:ability/{k}"
              for n in range(9)],
            f"execute unless items entity @s weapon.offhand * run return run loot replace entity @s weapon.offhand loot {NS}:ability/{k}",
            f"loot give @s loot {NS}:ability/{k}",
        ])
    # 1.0 ability items were paper (and clashed with cyberware): swap any still in inventories for the clay-ball ones
    old = lambda k: f"minecraft:paper[minecraft:custom_data~{{pvp_ab:\"{k}\"}}]"
    fn("ability/migrate", [
        # Saul's old wolf "clients" (that ability was replaced): no owner first, so nobody gets a death message
        "execute as @e[type=minecraft:wolf,tag=pvp.client] run data remove entity @s Owner", "kill @e[type=minecraft:wolf,tag=pvp.client]"]
       + [l for k in ABILITIES for l in (
        f"execute as @a if items entity @s container.* {old(k)} run loot give @s loot {NS}:ability/{k}",
        f"execute as @a if items entity @s weapon.offhand {old(k)} run loot give @s loot {NS}:ability/{k}",
        f"clear @a {old(k)}")]
       # refresh held ability items (restores lore lines crispy_enchants' migration removed)
       + [l for k in ABILITIES for l in (
        f"execute as @a if items entity @s container.* {sel(k)} run tag @s add pvp.rf",
        f"execute as @a if items entity @s weapon.offhand {sel(k)} run tag @s add pvp.rf",
        f"clear @a[tag=pvp.rf] {sel(k)}",
        f"execute as @a[tag=pvp.rf] run loot give @s loot {NS}:ability/{k}",
        "tag @a remove pvp.rf")])
    # raycast: half-block steps from the eyes, stops at the first target or a solid block
    fn("ability/ray_start", [f"execute anchored eyes positioned ^ ^ ^0.5 run function {NS}:ability/ray"])
    fn("ability/ray", [
        "execute if score #tr pvp matches 1 run particle minecraft:crit ~ ~ ~ 0 0 0 0 1",   # gun tracer
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
    has = lambda k: f"if items entity @s container.* {sel(k)}"
    fn("ability/tick", [
        f"execute as @a[scores={{pvp.rgt=1}}] run function {NS}:ability/regive",
        "scoreboard players remove @a[scores={pvp.rgt=2..}] pvp.rgt 1",
        f"execute as @e[type=minecraft:armor_stand,tag=pvp.nade] at @s run function {NS}:ability/nade_tick",
        # Borg Slam: hits everything around when Adam Smasher lands
        f"execute as @a[tag=pvp.slam] at @s run function {NS}:ability/slam_tick",
        # Fling: the bird hits whatever it crashes into (or the ground)
        f"execute as @a[tag=pvp.sling] at @s run function {NS}:ability/sling_tick",
        # ability fireballs that missed: gone after PROJ_LIFE ticks
        "scoreboard players add @e[tag=pvp.proj] pvp.ft 1",
        f"kill @e[tag=pvp.proj,scores={{pvp.ft={PROJ_LIFE}..}}]",
        # Doom Slayer: every kill heals (glory kill)
        f"execute as @a[scores={{pvp.gk=1..}}] {has('chainsaw')} at @s run function {NS}:ability/glory",
        "scoreboard players set @a[scores={pvp.gk=1..}] pvp.gk 0",
    ])
    fn("ability/slam_tick", [
        "scoreboard players add @s pvp.ft 1",
        f"execute if score @s pvp.ft matches 10.. if entity @s[nbt={{OnGround:1b}}] run return run function {NS}:ability/slam_hit",
        f"execute if score @s pvp.ft matches 80.. run function {NS}:ability/slam_end"])
    fn("ability/slam_hit", ["tag @s add pvp.caster", around(5, damage(10)), around(5, PUSH), around(5, "effect give @s minecraft:slowness 2 1"),
                            "particle minecraft:explosion_emitter ~ ~0.5 ~ 0 0 0 0 1", "particle minecraft:block{block_state:\"minecraft:stone\"} ~ ~0.2 ~ 2 0.2 2 0.3 80",
                            snd("entity.generic.explode", 1, 0.6), snd("entity.iron_golem.damage", 1, 0.5),
                            "tag @s remove pvp.caster", f"function {NS}:ability/slam_end"])
    fn("ability/slam_end", ["tag @s remove pvp.slam", "effect clear @s minecraft:levitation", "scoreboard players set @s pvp.ft 0"])
    fn("ability/sling_tick", [
        "tag @s add pvp.caster", "scoreboard players add @s pvp.ft 1",
        f"execute if score @s pvp.ft matches 3.. if entity @e[distance=..2,{TGT}] run return run function {NS}:ability/sling_hit",
        f"execute if score @s pvp.ft matches 5.. if entity @s[nbt={{OnGround:1b}}] run return run function {NS}:ability/sling_hit",
        f"execute if score @s pvp.ft matches 60.. run return run function {NS}:ability/sling_end",
        "tag @s remove pvp.caster"])
    fn("ability/sling_hit", [around(3, damage(7)), around(3, PUSH),
                             "particle minecraft:poof ~ ~0.5 ~ 1 0.4 1 0.05 25", "particle minecraft:item{item:\"minecraft:feather\"} ~ ~1 ~ 0.6 0.5 0.6 0.1 15",
                             snd("entity.player.attack.knockback", 1, 0.6), snd("entity.parrot.hurt", 1, 0.8),
                             f"function {NS}:ability/sling_end"])
    fn("ability/sling_end", ["tag @s remove pvp.sling", "tag @s remove pvp.caster", "scoreboard players set @s pvp.ft 0"])
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
    return ["pvp.rgt dummy", "pvp.abk dummy", "pvp.abs dummy", "pvp.id dummy", "pvp.ft dummy", "pvp.gk totalKillCount", "pvp.dmg minecraft.custom:minecraft.damage_taken", "pvp.sh dummy"]
