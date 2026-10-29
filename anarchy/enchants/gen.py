"""Generate the crispy_enchants datapack: AdvancedEnchantments' custom enchantments rebuilt as native
data-driven enchantments for Minecraft 26.2, plus an XP Enchanter in the market and item migration."""
import json, os, re, shutil, sys, math, yaml

OUT = sys.argv[1]
NS = "crispy_enchants"
Y = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "enchantments.yml")))
Y = {k.lower(): v for k, v in Y.items()}
# telepathy was on items but missing from the config: rebuild it from AE's stock definition
Y.setdefault("telepathy", {"display": "%group-color%Telepathy", "description": "Automatically places\nblocks broken by tools\nin your inventory.",
                           "applies-to": "Tools", "type": "MINING", "group": "UNIQUE",
                           "applies": ["ALL_PICKAXE", "ALL_AXE", "ALL_SPADE"],
                           "levels": {1: {"chance": 100, "effects": ["TELEPATHY"]}}})

GROUPS = {  # color, enchanter price in XP points (None = not sold)
    "SIMPLE": ("gray", 400), "UNIQUE": ("green", 800), "ELITE": ("aqua", 2500), "ULTIMATE": ("yellow", 5000),
    "LEGENDARY": ("gold", 25000), "SOUL": ("red", 35000), "HEROIC": ("light_purple", 50000), "MASTERY": ("dark_red", 75000),
    "RARE": ("blue", 2500)}
TIER_ORDER = ["SIMPLE", "UNIQUE", "ELITE", "ULTIMATE", "LEGENDARY", "SOUL", "MASTERY"]
APPLIES = {"ALL_ARMOR": "#minecraft:enchantable/armor", "ALL_SWORD": "#minecraft:swords", "ALL_AXE": "#minecraft:axes",
           "BOW": "minecraft:bow", "CROSSBOW": "minecraft:crossbow", "ALL_BOOTS": "#minecraft:enchantable/foot_armor",
           "ALL_PICKAXE": "#minecraft:pickaxes", "ALL_HELMET": "#minecraft:enchantable/head_armor", "ALL_SPADE": "#minecraft:shovels",
           "ALL_CHESTPLATE": "#minecraft:enchantable/chest_armor", "ALL_LEGGINGS": "#minecraft:enchantable/leg_armor",
           "ALL": "#minecraft:enchantable/durability"}
ARMORISH = {"ALL_ARMOR", "ALL_BOOTS", "ALL_HELMET", "ALL_CHESTPLATE", "ALL_LEGGINGS"}
POTIONS = {"SLOW": "slowness", "FAST_DIGGING": "haste", "SLOW_DIGGING": "mining_fatigue", "INCREASE_DAMAGE": "strength",
           "HEAL": "instant_health", "HARM": "instant_damage", "JUMP": "jump_boost", "CONFUSION": "nausea",
           "DAMAGE_RESISTANCE": "resistance", "SPEED": "speed", "REGENERATION": "regeneration", "FIRE_RESISTANCE": "fire_resistance",
           "WATER_BREATHING": "water_breathing", "INVISIBILITY": "invisibility", "BLINDNESS": "blindness", "NIGHT_VISION": "night_vision",
           "HUNGER": "hunger", "WEAKNESS": "weakness", "POISON": "poison", "WITHER": "wither", "HEALTH_BOOST": "health_boost",
           "ABSORPTION": "absorption", "SATURATION": "saturation", "GLOWING": "glowing", "LEVITATION": "levitation", "LUCK": "luck",
           "UNLUCK": "unluck", "SLOW_FALLING": "slow_falling", "DOLPHINS_GRACE": "dolphins_grace", "BAD_OMEN": "bad_omen",
           "DARKNESS": "darkness", "CONDUIT_POWER": "conduit_power", "HERO_OF_THE_VILLAGE": "hero_of_the_village"}
MOBS = {"ZOMBIE_PIGMAN": "zombified_piglin", "PIG_ZOMBIE": "zombified_piglin", "ENDERDRAGON": "ender_dragon", "MUSHROOM_COW": "mooshroom",
        "SNOWMAN": "snow_golem"}
PARTICLES = {"BURN": "flame", "FLAME": "flame", "HEART": "heart", "SMOKE": "smoke", "LAVA": "lava", "PORTAL": "portal", "SPELL": "effect",
             "CLOUD": "cloud", "CRIT": "crit", "EXPLOSION": "explosion", "REDSTONE": "dust{color:[1.0,0.0,0.0],scale:1.0}"}

def roman(n): return ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"][n] if n <= 10 else str(n)
def plain(s): return re.sub(r"(%[a-z\-]+%|[§&][0-9a-fk-or])", "", str(s)).strip()
def legacy_to_json(s):
    """Convert a legacy §-coded string to a text component list (colors + bold)."""
    colors = {"0": "black", "1": "dark_blue", "2": "dark_green", "3": "dark_aqua", "4": "dark_red", "5": "dark_purple", "6": "gold",
              "7": "gray", "8": "dark_gray", "9": "blue", "a": "green", "b": "aqua", "c": "red", "d": "light_purple", "e": "yellow", "f": "white"}
    parts, cur = [], {"color": "white"}
    for tok in re.split(r"([§&][0-9a-fk-or])", str(s)):
        if re.fullmatch(r"[§&][0-9a-fk-or]", tok):
            c = tok[1]
            if c in colors: cur = {"color": colors[c]}
            elif c == "l": cur = dict(cur, bold=True)
            elif c == "o": cur = dict(cur, italic=True)
            elif c == "r": cur = {"color": "white"}
        elif tok:
            parts.append(dict(cur, text=tok))
    return parts or [{"text": ""}]

def num(x, default=0.0):
    s = str(x)
    m = re.search(r"<random number>\s*(-?[\d.]+)\s*-\s*(-?[\d.]+)\s*</random number>", s)
    if m: return (float(m.group(1)) + float(m.group(2))) / 2
    if "<math>" in s: return 2.0
    m = re.search(r"-?\d+(\.\d+)?", s)
    return float(m.group(0)) if m else default

if os.path.exists(OUT): shutil.rmtree(OUT)
def w(path, text):
    p = os.path.join(OUT, path); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(text if isinstance(text, str) else json.dumps(text, indent=1))
def _macro_fix(text):
    return "\n".join(l[1:] if l.startswith("$") and "$(" not in l else l for l in text.split("\n"))
def fn(name, text): w(f"data/{NS}/function/{name}.mcfunction", _macro_fix(text.strip("\n")) + "\n")

w("pack.mcmeta", {"pack": {"description": "Crispy custom enchantments (rebuilt from AdvancedEnchantments) + Enchanter",
                           "min_format": [107, 0], "max_format": [107, 1]}})

# ------------------------------------------------------------------ type helpers
def triggers(t): return [x.strip().upper() for x in str(t).split(";")]
OWNER_ATTACK = {"ATTACK", "ATTACK_MOB", "SHOOT", "SHOOT_MOB", "KILL_PLAYER", "KILL_MOB", "BOW", "BOW_MOB", "SWING"}
OWNER_DEFENSE = {"DEFENSE", "DEFENSE_MOB", "DEFENSE_PROJECTILE", "DEFENSE_BOW", "EXPLOSION", "FALL_DAMAGE", "FIRE"}

# --------------------------------------------------------- effect -> commands (inside fx body)
V, A = "@e[tag=ce.v,limit=1]", "@e[tag=ce.a,limit=1]"
def sel(base, extra): return base[:-1] + "," + extra + "]"
NOT_LIVING = ["item", "experience_orb", "arrow", "spectral_arrow", "trident", "armor_stand", "item_frame", "glow_item_frame", "marker",
              "text_display", "item_display", "block_display", "interaction", "falling_block", "tnt", "area_effect_cloud", "painting",
              "lightning_bolt", "ender_pearl", "snowball", "egg", "fireball", "small_fireball", "wind_charge", "breeze_wind_charge",
              "firework_rocket", "splash_potion", "lingering_potion", "experience_bottle", "eye_of_ender", "leash_knot", "end_crystal", "evoker_fangs", "llama_spit",
              "shulker_bullet", "dragon_fireball", "wither_skull", "fishing_bobber", "villager", "wandering_trader"]
w(f"data/{NS}/tags/entity_type/not_aoe.json", {"values": [f"minecraft:{x}" for x in NOT_LIVING] + ["#minecraft:boat"]})

def target_of(eff, owner, default):
    m = re.search(r"@(Victim|Attacker)\b", eff, re.I)
    aoe = re.search(r"<aoe>\s*radius=(\d+)\s*target=(\w+)\s*</aoe>", eff)
    if aoe:
        r, kind = aoe.group(1), aoe.group(2).lower()
        if kind == "undamageable": return owner
        return f"@e[type=!#{NS}:not_aoe,tag=!ce.owner,distance=..{r}]"   # evaluated `at` the owner
    if m: return V if m.group(1).lower() == "victim" else A
    return default

def effect_cmds(eff, ctx):
    """ctx: dict(owner=selector, other=selector, kind='hit'|'static'|'mine', name, level). Returns list of commands."""
    e = str(eff).strip(); up = e.upper()
    key = up.split(":")[0].split(" ")[0].split("<")[0]
    O, X = ctx["owner"], ctx["other"]
    T = target_of(e, O, O)
    at = f"execute at {O} as {T} at @s run " if "<aoe>" in e else f"execute as {T} at @s run "
    args = re.sub(r"<aoe>.*?</aoe>", "", e).split(" @")[0].split(":")
    if key == "POTION":
        eff_id = POTIONS.get(args[1].upper()) if len(args) > 1 else None
        if not eff_id: return [f"# unsupported potion {e}"]
        amp = int(num(args[2])) if len(args) > 2 else 0
        if ctx["kind"] == "static": return []           # handled by static effect refresh
        secs = max(1, round(num(args[3]) / 20)) if len(args) > 3 else 5
        return [at + f"effect give @s minecraft:{eff_id} {secs} {min(amp, 255)}"]
    if key == "MESSAGE":
        txt = re.sub(r"\s*@(Victim|Attacker)\b.*$", "", e.split(":", 1)[1] if ":" in e else "", flags=re.I)
        comps = []
        for i, part in enumerate(re.split(r"(%victim name%|%attacker name%)", txt)):
            if part == "%victim name%": comps.append({"selector": V})
            elif part == "%attacker name%": comps.append({"selector": A})
            else: comps += legacy_to_json(re.sub(r"%[a-z ]+%", "", part))
        tgt = T if re.search(r"@(Victim|Attacker)", e, re.I) else O
        return [f"execute as {tgt} run tellraw @s " + json.dumps(comps, ensure_ascii=False)]
    if key in ("DO_HARM", "EXTRA_DAMAGE"):
        n = max(0.5, num(args[1] if len(args) > 1 else 2)); T2 = T if re.search(r"@|<aoe>", e) else X
        at2 = f"execute at {O} as {T2} at @s run " if "<aoe>" in e else f"execute as {T2} at @s run "
        return [at2 + f"damage @s {n:g} minecraft:magic"]
    if key == "STEAL_HEALTH":
        n = max(1, num(args[1] if len(args) > 1 else 2))
        tgt = T if "<aoe>" in e else X
        pre = f"execute at {O} as {tgt} at @s run " if "<aoe>" in e else f"execute as {tgt} at @s run "
        return [pre + f"damage @s {n:g} minecraft:magic", f"effect give {O} minecraft:instant_health 1 0" if n >= 3 else f"effect give {O} minecraft:regeneration 2 2"]
    if key == "ADD_HEALTH":
        n = num(args[1] if len(args) > 1 else 4)
        if n >= 3:
            amp = min(5, max(0, int(math.log2(max(n, 4) / 4))))
            return [at + f"effect give @s minecraft:instant_health 1 {amp}"]
        return [at + "effect give @s minecraft:regeneration 2 3"]
    if key == "ADD_FOOD":
        return [at + f"effect give @s minecraft:saturation 1 {max(0, int(num(args[1] if len(args) > 1 else 1)) - 1)}"]
    if key in ("CURE", "CURE_PERMANENT"):
        eff_id = POTIONS.get(args[1].upper()) if len(args) > 1 else None
        return [at + f"effect clear @s minecraft:{eff_id}"] if eff_id else []
    if key == "LIGHTNING": return [at + "summon minecraft:lightning_bolt ~ ~ ~"]
    if key == "TNT": return [at + "summon minecraft:tnt ~ ~0.5 ~ {fuse:20s}"]
    if key == "BURN":
        secs = max(1, int(num(args[1] if len(args) > 1 else 3)))
        return [at + f"function {NS}:lib/burn"] if False else [at + f"damage @s 1 minecraft:on_fire", at + f"execute if block ~ ~ ~ #minecraft:air run setblock ~ ~ ~ minecraft:fire"]
    if key == "EXTINGUISH": return [at + "effect give @s minecraft:fire_resistance 2 0 true"]
    if key == "GUARD":
        mob = (args[1] if len(args) > 1 else "IRON_GOLEM").lower()
        mob = MOBS.get(mob.upper(), mob)
        return [f"execute at {O} run function {NS}:lib/guard {{mob:\"minecraft:{mob}\"}}"]
    if key == "TELEPORT_BEHIND":
        return [f"execute as {O} at {X} rotated as {X} positioned ^ ^ ^-1.5 run tp @s ~ ~ ~ facing entity {X} feet"]
    if key == "REMOVE_RANDOM_ARMOR": return [f"execute as {T} at @s run function {NS}:lib/disarmor"]
    if key == "DAMAGE_ARMOR":
        n = int(min(50, max(1, num(args[1] if len(args) > 1 else 2))))
        return [f"execute as {T} run function {NS}:lib/damage_armor {{n:{n}}}"]
    if key in ("ADD_DURABILITY", "ADD_DURABILITY_ITEM"):
        n = int(num(args[1] if len(args) > 1 else -1)); n = max(-50, min(50, n))
        who = O if key == "ADD_DURABILITY_ITEM" else T
        slot = "weapon.mainhand" if key == "ADD_DURABILITY_ITEM" else "armor"
        if n < 0: return [f"execute as {who} run function {NS}:lib/repair {{n:{-n},slot:\"{slot}\"}}"]
        return [f"execute as {who} run function {NS}:lib/damage_armor {{n:{n}}}"]
    if key == "REPAIR": return [f"execute as {O} run function {NS}:lib/repair {{n:100,slot:\"weapon.mainhand\"}}"]
    if key == "EXP": return [f"execute as {O} run xp add @s {max(1, int(num(args[1] if len(args) > 1 else 2)))} points"]
    if key == "STEAL_EXP":
        n = max(1, int(num(args[1] if len(args) > 1 else 5)))
        return [f"execute as {X} run xp add @s -{n} points", f"execute as {O} run xp add @s {n} points"]
    if key in ("PARTICLE",):
        p = PARTICLES.get(args[1].upper() if len(args) > 1 else "", "crit")
        return [at + f"particle minecraft:{p} ~ ~1 ~ 0.4 0.6 0.4 0.05 20"]
    if key == "BLOOD":
        return [at + "particle minecraft:block{block_state:\"minecraft:redstone_block\"} ~ ~1 ~ 0.3 0.5 0.3 0 40",
                f"execute as {T} run function {NS}:lib/bleed"]
    if key in ("PLAY_SOUND", "PLAY_SOUND_OUTLOUD"):
        snd = {"ANVIL_DROP": "block.anvil.land", "ITEM_BREAK": "entity.item.break", "BAT_TAKEOFF": "entity.bat.takeoff",
               "WITHER_SPAWN": "entity.wither.spawn", "ENDERDRAGON_GROWL": "entity.ender_dragon.growl"}.get(
               (args[1].upper() if len(args) > 1 else ""), "entity.experience_orb.pickup")
        return [at + f"playsound minecraft:{snd} master @a ~ ~ ~ 1 1"]
    if key == "SHUFFLE_HOTBAR": return [f"execute as {T} at @s run function {NS}:lib/shuffle"]
    if key == "DROP_HEAD": return [f"execute as {T} at @s run loot spawn ~ ~1 ~ loot {NS}:head"]
    if key == "KILL": return [at + "kill @s"]
    if key == "PUMPKIN": return [at + "effect give @s minecraft:darkness 4 0", at + "effect give @s minecraft:blindness 2 0"]
    if key == "CANCEL_USE":
        ticks = int(num(args[2] if len(args) > 2 else 100))
        return [f"execute as {T} run function {NS}:lib/teleblock {{t:{max(20, ticks)}}}"]
    if key == "TAKE_AWAY":
        n = int(num(args[2] if len(args) > 2 else 1))
        return [at + f"clear @s minecraft:ender_pearl {max(1, n)}"]
    if key == "SPAWN_ARROWS":
        return [at + "summon minecraft:arrow ~ ~4 ~ {Motion:[0.0,-1.0,0.0],damage:4.0d,pickup:0b}" for _ in range(3)]
    if key == "AIR": return [f"effect give {O} minecraft:water_breathing 5 0 true"]
    if key == "FLY": return [f"effect give {O} minecraft:slow_falling 5 0 true"]
    if key == "DISABLE_ACTIVATION":
        tname = args[1].lower() if len(args) > 1 else ""
        secs = int(num(args[2] if len(args) > 2 else 5))
        if tname in Y:
            tgt = T if re.search(r"@(Victim|Attacker)", e, re.I) else X
            return [f"execute as {tgt} run function {NS}:lib/disable {{e:\"{tname}\",t:{secs * 20}}}"]
        return []
    if key in ("KEEP_ON_DEATH", "BREAK_BLOCK", "BREAK_TREE", "SMELT", "TELEPATHY", "LAVA_WALKER", "WAIT", "CANCEL_EVENT",
               "INCREASE_DAMAGE", "DECREASE_DAMAGE", "DOUBLE_DAMAGE", "HALF_DAMAGE", "NEGATE_DAMAGE", "PULL_AWAY", "PULL_CLOSER", "BOOST",
               "REMOVE_SOULS", "STEAL_GUARD", "CONSOLE_COMMAND", "REMOVE_ENCHANT", "BREAK", ""):
        return []
    return [f"# unsupported: {e}"]

# --------------------------------------------------------------------- conditions
def cond_cmds(conds, owner):
    """Returns (pre-commands, chance_bonus_cmds). %stop%: abort if true. %allow%/%continue%: abort if false."""
    out = []
    if not conds: return out
    for c in (conds if isinstance(conds, list) else [conds]):
        c = str(c)
        if ":" not in c: continue
        expr, act = c.rsplit(":", 1); act = act.strip().lower()
        tests = []   # list of 'execute if ...' fragments OR'ed
        for part in re.split(r"\s+or\s+", expr.strip()):
            p = part.strip()
            m = re.match(r"%(victim|attacker) health%\s*([<>]=?|=)\s*(\d+)", p)
            if m:
                who = V if m.group(1) == "victim" else A
                n = int(m.group(3)); op = m.group(2)
                rng = {">": f"{n+1}..", ">=": f"{n}..", "<": f"..{n-1}", "<=": f"..{n}", "=": f"{n}"}[op]
                tests.append(("pre", f"execute store result score #hp ce run data get entity {who} Health", f"score #hp ce matches {rng}")); continue
            m = re.match(r"%(victim|attacker) is holding%\s*(contains|=)\s*(\w+)", p)
            if m:
                who = V if m.group(1) == "victim" else A
                it = {"SWORD": "#minecraft:swords", "AXE": "#minecraft:axes", "BOW": "minecraft:bow", "PICKAXE": "#minecraft:pickaxes",
                      "CROSSBOW": "minecraft:crossbow", "TRIDENT": "minecraft:trident"}.get(m.group(3).upper(), "minecraft:air")
                tests.append(("", "", f"items entity {who} weapon.mainhand {it}")); continue
            m = re.match(r"%(victim|attacker) is sneaking%\s*=\s*(\w+)", p)
            if m:
                who = V if m.group(1) == "victim" else A; want = m.group(2).lower() == "true"
                tests.append(("", "", f"entity " + sel(who, f"predicate={NS}:sneaking") if want else f"entity " + sel(who, f"predicate=!{NS}:sneaking"))); continue
            m = re.match(r"%(victim|attacker) is on fire%\s*=\s*(\w+)", p)
            if m:
                who = V if m.group(1) == "victim" else A
                tests.append(("", "", "entity " + sel(who, f"predicate={NS}:on_fire"))); continue
            m = re.match(r"%mob type%\s*=\s*(\w+)", p)
            if m:
                mob = MOBS.get(m.group(1).upper(), m.group(1).lower())
                tests.append(("", "", "entity " + sel(V, f"type=minecraft:{mob}"))); continue
            m = re.match(r"%victim has potion effect (\w+)%\s*(!=|=)\s*(\w+)", p, re.I)
            if m:
                eff = POTIONS.get(m.group(1).upper(), m.group(1).lower())
                has = (m.group(2) == "=") == (m.group(3).lower() == "true")
                tests.append(("", "", "entity " + sel(V, f"predicate={NS}:effect/{eff}") if has else "entity " + sel(V, f"predicate=!{NS}:effect/{eff}")))
                continue
            m = re.match(r"%is under water%\s*=\s*(\w+)", p, re.I)
            if m: tests.append(("", "", "entity " + sel(owner, f"predicate={NS}:in_water"))); continue
            m = re.match(r"%victim is bleeding%\s*=\s*(\w+)", p, re.I)
            if m:
                tests.append(("", "", "entity " + sel(V, "tag=ce.bleed") if m.group(1).lower() == "true" else "entity " + sel(V, "tag=!ce.bleed"))); continue
            m = re.match(r"%is headshot%\s*=\s*(\w+)", p, re.I)
            if m:
                tests.append(("pre", "execute store result score #hs ce run random value 1..4", "score #hs ce matches 1" if m.group(1).lower() == "true" else "score #hs ce matches 2..4"))
                continue
            tests = None; break      # unsupported part -> skip whole condition
        if not tests: continue
        for pre, cmd, _ in tests:
            if pre: out.append(cmd)
        # OR of tests -> set #ok
        out.append("scoreboard players set #ok ce 0")
        for _, _, t in tests: out.append(f"execute if {t} run scoreboard players set #ok ce 1")
        if act.startswith("%stop%"): out.append("execute if score #ok ce matches 1 run return 0")
        elif act.startswith("%allow%") or act.startswith("%continue%"): out.append("execute if score #ok ce matches 0 run return 0")
        elif act.startswith("%chance%"):
            out.append(f"execute if score #ok ce matches 1 run scoreboard players add #ch ce {int(num(act) * 100)}")
    return out

# ------------------------------------------------------------------ build enchantments
def lookup(vals): return {"type": "minecraft:lookup", "values": vals, "fallback": 0.0}
def level_gate(l, n): return {"condition": "minecraft:random_chance", "chance": {"type": "minecraft:enchantment_level", "amount": lookup([1.0 if i == l else 0.0 for i in range(1, n + 1)])}}
def chance_req(vals): return {"condition": "minecraft:random_chance", "chance": {"type": "minecraft:enchantment_level", "amount": lookup(vals)}}
def ent(entity, pred): return {"condition": "minecraft:entity_properties", "entity": entity, "predicate": pred}
def not_(c): return {"condition": "minecraft:inverted", "term": c}
PLAYER = {"minecraft:entity_type": "minecraft:player"}
ARROWS = {"minecraft:entity_type": "#minecraft:arrows"}

def trigger_reqs(trig):
    """requirements for a post_attack / damage entry for one AE trigger (context: this=victim)."""
    if trig in ("ATTACK", "KILL_PLAYER", "BOW", "SWING"): return [ent("this", PLAYER), not_(ent("direct_attacker", ARROWS))]
    if trig in ("ATTACK_MOB", "KILL_MOB"): return [not_(ent("this", PLAYER)), not_(ent("direct_attacker", ARROWS))]
    if trig == "SHOOT": return [ent("this", PLAYER), ent("direct_attacker", ARROWS)]
    if trig in ("SHOOT_MOB", "BOW_MOB"): return [not_(ent("this", PLAYER)), ent("direct_attacker", ARROWS)]
    if trig == "DEFENSE": return [ent("attacker", PLAYER)]
    if trig == "DEFENSE_MOB": return [ent("attacker", {}), not_(ent("attacker", PLAYER))]
    if trig in ("DEFENSE_PROJECTILE", "DEFENSE_BOW"): return [ent("direct_attacker", ARROWS)]
    return []

ENCH_LIST = []           # (name, group, max_level)
MINING = {}              # name -> {level: (chance, cooldown, effects)}
DEATH = {}               # soulbound
STATIC_EFFECTS = {}      # (name, level) -> [(effect id, amp)]
fx_count = 0
for name, e in sorted(Y.items()):
    if not isinstance(e, dict) or "levels" not in e: continue
    grp = str(e.get("group", "SIMPLE")).upper(); color = GROUPS.get(grp, ("gray", None))[0]
    levels = {int(k): (v or {}) for k, v in e["levels"].items()}
    n = max(levels)
    trigs = triggers(e.get("type", "ATTACK"))
    applies = [a for a in e.get("applies", ["ALL"]) if a in APPLIES] or ["ALL"]
    w(f"data/{NS}/tags/item/supports/{name}.json", {"values": [APPLIES[a] for a in applies]})
    slots = ["armor"] if set(applies) <= ARMORISH else (["mainhand"] if not (set(applies) & ARMORISH) else ["any"])
    display = plain(e.get("display", name)) or name.title()
    desc_lines = [plain(l) for l in str(e.get("description", "")).split("\n") if plain(l)]
    ENCH_LIST.append((name, grp, n, display, desc_lines, e.get("settings") or {}))
    effects = {}
    owner_is_attacker = any(t in OWNER_ATTACK for t in trigs)
    owner = A if owner_is_attacker else V
    other = V if owner_is_attacker else A

    kill_trigs = [t for t in trigs if t in ("KILL_PLAYER", "KILL_MOB")]
    hit_trigs = [t for t in trigs if (t in OWNER_ATTACK or t in ("DEFENSE", "DEFENSE_MOB", "DEFENSE_PROJECTILE", "DEFENSE_BOW")) and t not in kill_trigs] or kill_trigs
    # ---------- per-level fx functions for hit triggers
    if hit_trigs:
        entries = []
        for l, ld in levels.items():
            body = []
            chance = ld.get("chance", 100); chance = 100 if chance is None else float(chance)
            cd = int(num(ld.get("cooldown", 0) or 0))
            body += [f"execute store result score #now ce run time query gametime",
                     f"execute if score {owner} ce.{name[:40]} > #now ce run return 0"]
            body += cond_cmds(ld.get("condition"), owner)
            body += [f"scoreboard players set #ch ce {int(round(chance * 100))}",
                     "execute store result score #r ce run random value 1..10000",
                     "execute if score #r ce > #ch ce run return 0"]
            if cd > 0:
                body += [f"scoreboard players operation {owner} ce.{name[:40]} = #now ce", f"scoreboard players add {owner} ce.{name[:40]} {cd * 20}"]
            body.append(f"tag {owner} add ce.owner")
            ctx = dict(owner=owner, other=other, kind="hit", name=name, level=l)
            for ef in ld.get("effects", []) or []:
                body += effect_cmds(ef, ctx)
            body.append(f"tag {owner} remove ce.owner")
            fn(f"fx/{name}/{l}", f"""
tag @s add ce.v
execute on attacker run tag @s add ce.a
function {NS}:fx/{name}/{l}b
tag @s remove ce.v
tag @e[tag=ce.a] remove ce.a
""")
            fn(f"fx/{name}/{l}b", "\n".join(body)); fx_count += 1
        for t in kill_trigs:
            for l in levels:
                lp = {"enchantments": f"{NS}:{name}", "levels": l}
                victim_type = ent("this", PLAYER) if t == "KILL_PLAYER" else not_(ent("this", PLAYER))
                w(f"data/{NS}/advancement/kill/{name}_{l}.json", {"criteria": {"k": {"trigger": "minecraft:player_killed_entity", "conditions": {
                    "player": [ent("this", {"minecraft:equipment": {"mainhand": {"predicates": {"minecraft:enchantments": [lp]}}}})],
                    "entity": [victim_type]}}}, "rewards": {"function": f"{NS}:kill/{name}_{l}"}})
                vsel = "@a[distance=..12,nbt={Health:0.0f},limit=1,sort=nearest]" if t == "KILL_PLAYER" else "@e[type=!minecraft:player,distance=..12,nbt={Health:0.0f},limit=1,sort=nearest]"
                fn(f"kill/{name}_{l}", f"""advancement revoke @s only {NS}:kill/{name}_{l}
tag @s add ce.a
tag {vsel} add ce.v
function {NS}:fx/{name}/{l}b
tag @s remove ce.a
tag @e[tag=ce.v] remove ce.v""")
        for t in [x for x in hit_trigs if x not in kill_trigs]:
            enchanted = "attacker" if t in OWNER_ATTACK else "victim"
            for l in levels:
                entries.append({"enchanted": enchanted, "affected": "victim",
                                "effect": {"type": "minecraft:run_function", "function": f"{NS}:fx/{name}/{l}"},
                                "requirements": {"condition": "minecraft:all_of", "terms": [level_gate(l, n)] + trigger_reqs(t)}})
        if entries: effects["minecraft:post_attack"] = entries
        # ---------- pre-damage natives (damage multipliers, protection, dodge, knockback)
        dmg_mult, prot, immune, impulse = [], [], [], []
        for l in range(1, n + 1):
            ld = levels.get(l, {}); ch = (100 if ld.get("chance") is None else float(ld.get("chance"))) / 100
            effs = [str(x) for x in ld.get("effects", []) or []]
            mult, p, im, imp = 1.0, 0.0, False, 0.0
            for ef in effs:
                k = ef.upper().split(":")[0].split(" ")[0]
                if k == "INCREASE_DAMAGE" and owner_is_attacker: mult *= 1 + num(ef.split(":", 1)[1]) / 100
                if k == "DOUBLE_DAMAGE" and owner_is_attacker: mult *= 2
                if not owner_is_attacker:
                    if k == "HALF_DAMAGE": p += 12.5
                    if k == "DECREASE_DAMAGE": p += num(ef.split(":", 1)[1]) / 4
                    if k == "NEGATE_DAMAGE": p += min(20, num(ef.split(":", 1)[1]) / 2)
                    if k == "CANCEL_EVENT": im = True
                if k in ("PULL_AWAY", "PULL_CLOSER"): imp = num(ef.split(":", 1)[1]) * (1 if k == "PULL_AWAY" else -1)
            dmg_mult.append((mult, ch)); prot.append((min(p, 20), ch)); immune.append((im, ch)); impulse.append((imp, ch))
        for t in [x for x in hit_trigs if x not in kill_trigs]:
            reqs = trigger_reqs(t)
            if any(m != 1.0 for m, _ in dmg_mult) and t in OWNER_ATTACK:
                effects.setdefault("minecraft:damage", []).append({
                    "effect": {"type": "minecraft:multiply", "factor": lookup([m for m, _ in dmg_mult])},
                    "requirements": {"condition": "minecraft:all_of", "terms": [chance_req([c if m != 1.0 else 0.0 for m, c in dmg_mult])] + reqs}})
            if any(p > 0 for p, _ in prot) and t not in OWNER_ATTACK:
                effects.setdefault("minecraft:damage_protection", []).append({
                    "effect": {"type": "minecraft:add", "value": lookup([p for p, _ in prot])},
                    "requirements": {"condition": "minecraft:all_of", "terms": [chance_req([c if p > 0 else 0.0 for p, c in prot])] + reqs}})
            if any(i for i, _ in immune) and t not in OWNER_ATTACK:
                effects.setdefault("minecraft:damage_immunity", []).append({
                    "effect": {}, "requirements": {"condition": "minecraft:all_of", "terms": [chance_req([c if i else 0.0 for i, c in immune])] + reqs}})
            if any(abs(i) > 0 for i, _ in impulse):
                pa = effects.setdefault("minecraft:post_attack", [])
                pa.append({"enchanted": "attacker" if t in OWNER_ATTACK else "victim",
                           "affected": "victim" if owner_is_attacker else "attacker",
                           "effect": {"type": "minecraft:apply_impulse", "direction": [0.0, 0.25, -1.0], "coordinate_scale": [1.0, 1.0, 1.0],
                                      "magnitude": lookup([abs(i) for i, _ in impulse])},
                           "requirements": {"condition": "minecraft:all_of", "terms": [chance_req([c if i else 0.0 for i, c in impulse])] + reqs}})
        # BURN as native ignite (players can't be set on fire by commands)
        burn = []
        for l in range(1, n + 1):
            ld = levels.get(l, {}); ch = (100 if ld.get("chance") is None else float(ld.get("chance"))) / 100
            secs = 0.0
            for ef in ld.get("effects", []) or []:
                if str(ef).upper().startswith("BURN") and "<aoe>" not in str(ef): secs = max(secs, num(str(ef).split(":", 1)[1]) if ":" in str(ef) else 3)
            burn.append((secs, ch))
        if any(s > 0 for s, _ in burn):
            for t in [x for x in hit_trigs if x not in kill_trigs]:
                effects.setdefault("minecraft:post_attack", []).append({
                    "enchanted": "attacker" if t in OWNER_ATTACK else "victim", "affected": "victim" if owner_is_attacker else "attacker",
                    "effect": {"type": "minecraft:ignite", "duration": lookup([s for s, _ in burn])},
                    "requirements": {"condition": "minecraft:all_of", "terms": [chance_req([c if s else 0.0 for s, c in burn])] + trigger_reqs(t)}})

    # ---------- passive / held / repeating
    if any(t in ("EFFECT_STATIC", "HELD", "REPEATING") for t in trigs):
        attr = []
        for l, ld in levels.items():
            pots, body = [], []
            for ef in ld.get("effects", []) or []:
                s = str(ef); k = s.upper().split(":")[0]
                if k == "POTION":
                    a = s.split(":"); pid = POTIONS.get(a[1].upper()) if len(a) > 1 else None
                    amp = int(num(a[2])) if len(a) > 2 else 0
                    if pid == "health_boost": attr.append((l, "minecraft:max_health", 4.0 * (amp + 1)))
                    elif pid: body.append(f"effect give @s minecraft:{pid} 20 {amp} true")
                elif k == "CURE_PERMANENT" or k == "CURE":
                    a = s.split(":"); pid = POTIONS.get(a[1].upper().split(" ")[0]) if len(a) > 1 else None
                    if pid: body.append(f"effect clear @s minecraft:{pid}")
                elif k == "LAVA_WALKER":
                    pass
                else:
                    body += effect_cmds(s, dict(owner="@s", other="@s", kind="static", name=name, level=l))
            if body:
                fn(f"fx/{name}/{l}", "\n".join(body)); fx_count += 1
                period = int(e.get("time", 100) or 100) if "REPEATING" in trigs else 100
                effects.setdefault("minecraft:tick", []).append({
                    "effect": {"type": "minecraft:run_function", "function": f"{NS}:fx/{name}/{l}"},
                    "requirements": {"condition": "minecraft:all_of", "terms": [level_gate(l, n),
                                     {"condition": "minecraft:time_check", "clock": "minecraft:overworld", "period": period, "value": 0}]}})
        if attr:
            for l, aid, amt in attr:
                pass
            effects["minecraft:attributes"] = [{"id": f"{NS}:{name}", "attribute": attr[0][1], "operation": "add_value",
                                                "amount": lookup([next((a for ll, _, a in attr if ll == i), 0.0) for i in range(1, n + 1)])}]
        if any("LAVA_WALKER" in str(ef).upper() for ld in levels.values() for ef in (ld.get("effects") or [])):
            effects["minecraft:location_changed"] = [{
                "effect": {"type": "minecraft:replace_disk", "block_state": {"type": "minecraft:simple_state_provider", "state": {"Name": "minecraft:magma_block"}},
                           "height": 1.0, "offset": [0, -1, 0], "predicate": {"type": "minecraft:all_of", "predicates": [
                               {"type": "minecraft:matching_blocks", "blocks": "minecraft:lava"},
                               {"type": "minecraft:matching_fluids", "fluids": "minecraft:lava"},
                               {"type": "minecraft:matching_block_tag", "offset": [0, 1, 0], "tag": "minecraft:air"}]},
                           "radius": 2.0},
                "requirements": {"condition": "minecraft:entity_properties", "entity": "this", "predicate": {"minecraft:flags": {"is_on_ground": True}}}}]

    # ---------- fall / explosion protection
    for t, tag in (("FALL_DAMAGE", "minecraft:is_fall"), ("EXPLOSION", "minecraft:is_explosion"), ("FIRE", "minecraft:is_fire")):
        if t in trigs:
            vals = []
            for l in range(1, n + 1):
                ld = levels.get(l, {}); effs = " ".join(map(str, ld.get("effects", []) or [])).upper()
                ch = (100 if ld.get("chance") is None else float(ld.get("chance"))) / 100
                v = 20.0 if "CANCEL_EVENT" in effs else (12.5 if "HALF_DAMAGE" in effs else (num(effs.split("DECREASE_DAMAGE:")[1]) / 4 if "DECREASE_DAMAGE:" in effs else 5.0))
                vals.append((v, ch))
            effects.setdefault("minecraft:damage_protection", []).append({
                "effect": {"type": "minecraft:add", "value": lookup([v for v, _ in vals])},
                "requirements": {"condition": "minecraft:all_of", "terms": [chance_req([c for _, c in vals]),
                                 {"condition": "minecraft:damage_source_properties", "predicate": {"tags": [{"id": tag, "expected": True}]}}]}})

    if any(t == "MINING" for t in trigs):
        MINING[name] = {l: (100 if ld.get("chance") is None else float(ld["chance"]), int(num(ld.get("cooldown", 0) or 0)),
                            [str(x) for x in ld.get("effects", []) or []]) for l, ld in levels.items()}
    if any(t in ("DEATH", "PASSIVE_DEATH") for t in trigs):
        DEATH[name] = {l: (100 if ld.get("chance") is None else float(ld["chance"])) for l, ld in levels.items()}

    w(f"data/{NS}/enchantment/{name}.json", {
        "description": {"text": display, "color": color},
        "supported_items": f"#{NS}:supports/{name}", "primary_items": f"#{NS}:supports/{name}",
        "weight": 1, "max_level": n, "min_cost": {"base": 200, "per_level_above_first": 0}, "max_cost": {"base": 250, "per_level_above_first": 0},
        "anvil_cost": 1, "slots": slots, "effects": effects})

# ------------------------------------------------------------------ load / tick / scoreboards
objs = "\n".join(f"scoreboard objectives add ce.{n[:40]} dummy" for n, *_ in ENCH_LIST)
TOOLS = [f"{m}_{t}" for m in ("wooden", "stone", "iron", "golden", "diamond", "netherite", "copper") for t in ("pickaxe", "axe", "shovel")]
tool_objs = "\n".join(f"scoreboard objectives add ce.u.{t} minecraft.used:minecraft.{t}" for t in TOOLS)
fn("load", f"""
scoreboard objectives add ce dummy
scoreboard objectives add ce.buy trigger
scoreboard objectives add ce.death deathCount
scoreboard objectives add ce.life dummy
scoreboard objectives add ce.tb dummy
scoreboard objectives add ce.bl dummy
{objs}
{tool_objs}
scoreboard players set #100 ce 100
scoreboard players set #20 ce 20
""")
w("data/minecraft/tags/function/load.json", {"values": [f"{NS}:load"]})
w("data/minecraft/tags/function/tick.json", {"values": [f"{NS}:tick"]})
used_checks = "\n".join(f"execute as @a[scores={{ce.u.{t}=1..}}] at @s run function {NS}:mine/used" for t in TOOLS)
fn("tick", f"""
scoreboard players enable @a ce.buy
execute as @a[scores={{ce.buy=1..}}] at @s run function {NS}:enchanter/buy
{used_checks}
execute as @a[scores={{ce.death=1..}}] at @s run function {NS}:death/died
execute as @e[type=minecraft:player,tag=ce.sb] run function {NS}:death/respawned
execute as @e[type=minecraft:ender_pearl] on origin if entity @s[tag=ce.tblock] run tag @s add ce.pearlowner
execute as @e[type=minecraft:ender_pearl] if function {NS}:lib/pearl_blocked run kill @s
tag @a remove ce.pearlowner
scoreboard players add #t ce 1
execute if score #t ce matches 20.. run function {NS}:second
""")
fn("second", f"""
scoreboard players set #t ce 0
scoreboard players remove @e[scores={{ce.life=1..}}] ce.life 1
kill @e[tag=ce.guard,scores={{ce.life=..0}}]
scoreboard players remove @a[scores={{ce.tb=1..}}] ce.tb 1
tag @a[tag=ce.tblock,scores={{ce.tb=..0}}] remove ce.tblock
scoreboard players remove @e[scores={{ce.bl=1..}}] ce.bl 1
tag @e[tag=ce.bleed,scores={{ce.bl=..0}}] remove ce.bleed
scoreboard players add #mig ce 1
execute if score #mig ce matches 2.. run function {NS}:migrate/all
""")
fn("lib/pearl_blocked", "execute on origin if entity @s[tag=ce.tblock] run return 1\nreturn 0")

# ------------------------------------------------------------------ lib functions
fn("lib/guard", f"""
$summon $(mob) ~1 ~ ~1 {{Tags:["ce.guard","ce.new"],PersistenceRequired:0b,PlayerCreated:1b}}
execute as @e[tag=ce.new] run scoreboard players set @s ce.life 30
execute if entity {A} as @e[tag=ce.new] run data modify entity @s AngryAt set from entity {A} UUID
execute if entity {A} as @e[tag=ce.new] run data modify entity @s anger_end_time set value 600L
tag @e[tag=ce.new] remove ce.new
""")
fn("lib/disarmor", f"""
execute store result score #r ce run random value 0..3
execute if score #r ce matches 0 if items entity @s armor.head * run function {NS}:lib/disarmor_slot {{s:"head"}}
execute if score #r ce matches 1 if items entity @s armor.chest * run function {NS}:lib/disarmor_slot {{s:"chest"}}
execute if score #r ce matches 2 if items entity @s armor.legs * run function {NS}:lib/disarmor_slot {{s:"legs"}}
execute if score #r ce matches 3 if items entity @s armor.feet * run function {NS}:lib/disarmor_slot {{s:"feet"}}
""")
fn("lib/disarmor_slot", """
summon minecraft:item ~ ~1 ~ {Tags:["ce.drop"],Item:{id:"minecraft:stone",count:1},PickupDelay:20s}
$data modify entity @e[tag=ce.drop,limit=1] Item set from entity @s equipment.$(s)
$item replace entity @s armor.$(s) with minecraft:air
tag @e[tag=ce.drop] remove ce.drop
""")
for k in range(1, 51):
    w(f"data/{NS}/item_modifier/dmg/{k}.json", {"function": "minecraft:set_damage", "damage": -0.02 * k, "add": True})
    w(f"data/{NS}/item_modifier/rep/{k}.json", {"function": "minecraft:set_damage", "damage": 0.01 * k, "add": True})
w(f"data/{NS}/item_modifier/rep/100.json", {"function": "minecraft:set_damage", "damage": 1.0, "add": False})
fn("lib/damage_armor", "\n".join(f"$item modify entity @s armor.{s} {NS}:dmg/$(n)" for s in ("head", "chest", "legs", "feet")))
fn("lib/repair", "$function crispy_enchants:lib/repair_$(slot) {n:$(n)}")
fn("lib/repair_armor", "\n".join(f"$item modify entity @s armor.{s} {NS}:rep/$(n)" for s in ("head", "chest", "legs", "feet")))
fn("lib/repair_weapon.mainhand", f"$item modify entity @s weapon.mainhand {NS}:rep/$(n)")
fn("lib/bleed", "tag @s add ce.bleed\nscoreboard players set @s ce.bl 5")
fn("lib/teleblock", "tag @s add ce.tblock\n$scoreboard players set @s ce.tb $(t)\nscoreboard players operation @s ce.tb /= #20 ce")
fn("lib/disable", f"""
execute store result score #now ce run time query gametime
$scoreboard players operation #u ce = #now ce
$scoreboard players add #u ce $(t)
$execute unless score @s ce.$(e) >= #u ce run scoreboard players operation @s ce.$(e) = #u ce
""")
fn("lib/shuffle", f"""
summon minecraft:item_display ~ ~ ~ {{Tags:["ce.tmp"]}}
item replace entity @e[tag=ce.tmp,limit=1] contents from entity @s hotbar.0
item replace entity @s hotbar.0 from entity @s hotbar.4
item replace entity @s hotbar.4 from entity @s hotbar.8
item replace entity @s hotbar.8 from entity @s hotbar.2
item replace entity @s hotbar.2 from entity @e[tag=ce.tmp,limit=1] contents
kill @e[tag=ce.tmp]
""")
w(f"data/{NS}/loot_table/head.json", {"type": "minecraft:entity", "pools": [{"rolls": 1, "entries": [{"type": "minecraft:item", "name": "minecraft:player_head",
   "functions": [{"function": "minecraft:fill_player_head", "entity": "this"}]}], "conditions": [ent("this", PLAYER)]}]})
w(f"data/{NS}/predicate/sneaking.json", ent("this", {"minecraft:flags": {"is_sneaking": True}}))
w(f"data/{NS}/predicate/on_fire.json", ent("this", {"minecraft:flags": {"is_on_fire": True}}))
w(f"data/{NS}/predicate/in_water.json", ent("this", {"minecraft:location": {"fluid": {"fluids": "#minecraft:water"}}}))
for pid in set(POTIONS.values()):
    w(f"data/{NS}/predicate/effect/{pid}.json", ent("this", {"minecraft:effects": {f"minecraft:{pid}": {}}}))

# ------------------------------------------------------------------ mining (after a tool is used)
mine = [f"scoreboard players reset @s ce.u.{t}" for t in TOOLS]
PROTECTED = [(-18, 18, -17, 18), (160069, 160416, -6112, -5573), (-301, -165, 1218, 1354)]   # YAWP regions (x1,x2,z1,z2)
mine += ["execute if dimension crispy:market run return 0"] + [
    f"execute if dimension minecraft:overworld if entity @s[x={x1-8},y=-64,z={z1-8},dx={x2-x1+16},dy=400,dz={z2-z1+16}] run return 0"
    for x1, x2, z1, z2 in PROTECTED]
mine += [
         f"execute store result score #now ce run time query gametime",
         "tag @s add ce.miner",
         "execute at @s as @e[type=minecraft:item,distance=..7,nbt={Age:0s}] run tag @s add ce.fresh",
         "execute at @s as @e[type=minecraft:item,distance=..7,nbt={Age:1s}] run tag @s add ce.fresh",
         "execute unless entity @e[tag=ce.fresh] run return run tag @s remove ce.miner"]
for name, lv in MINING.items():
    for l, (ch, cd, effs) in sorted(lv.items()):
        cmds = []
        for ef in effs:
            k = ef.upper().split(":")[0].split(" ")[0]
            if k == "SMELT": cmds.append(f"execute as @e[tag=ce.fresh] run item modify entity @s contents {NS}:smelt")
            elif k == "TELEPATHY": cmds.append("execute as @e[tag=ce.fresh] run data modify entity @s PickupDelay set value 0s\ntp @e[tag=ce.fresh] @s")
            elif k == "BREAK_TREE": cmds.append(f"execute at @e[tag=ce.fresh,limit=1,sort=nearest] align xyz positioned ~0.5 ~0.5 ~0.5 run function {NS}:mine/tree_start")
            elif k == "BREAK_BLOCK":
                r = int(re.search(r"r=(\d+)", ef).group(1)) if re.search(r"r=(\d+)", ef) else 1
                cmds.append(f"execute at @e[tag=ce.fresh,limit=1,sort=nearest] align xyz positioned ~0.5 ~0.5 ~0.5 run function {NS}:mine/area_{min(r, 7)}")
            elif k == "EXP": cmds.append(f"xp add @s {max(1, int(num(ef.split(':', 1)[1])))} points")
            elif k == "AIR": cmds.append("effect give @s minecraft:water_breathing 5 0 true")
            elif k in ("ADD_DURABILITY_ITEM",): cmds.append(f"item modify entity @s weapon.mainhand {NS}:rep/{max(1, int(abs(num(ef.split(':', 1)[1]))))}")
            elif k == "REPAIR": cmds.append(f"item modify entity @s weapon.mainhand {NS}:rep/2")
        if not cmds: continue
        body = [f"execute if score @s ce.{name[:40]} > #now ce run return 0",
                "execute store result score #r ce run random value 1..10000", f"execute if score #r ce matches {int(ch * 100) + 1}.. run return 0"]
        if cd: body += [f"scoreboard players operation @s ce.{name[:40]} = #now ce", f"scoreboard players add @s ce.{name[:40]} {cd * 20}"]
        fn(f"mine/{name}_{l}", "\n".join(body + cmds))
        lp = '{enchantments:"%s:%s",levels:%d}' % (NS, name, l)
        mine.append(f"execute if items entity @s weapon.mainhand *[minecraft:enchantments~[{lp}]] run function {NS}:mine/{name}_{l}")
mine += ["tag @e[tag=ce.fresh] remove ce.fresh", "tag @s remove ce.miner"]
fn("mine/used", "\n".join(mine))
w(f"data/{NS}/item_modifier/smelt.json", {"function": "minecraft:furnace_smelt"})
# tree felling: flood-fill logs (max ~96 blocks)
fn("mine/tree_start", f"scoreboard players set #tree ce 96\nfunction {NS}:mine/tree")
fn("mine/tree", f"""
scoreboard players remove #tree ce 1
execute if score #tree ce matches ..0 run return 0
""" + "\n".join(f"execute positioned {d} if block ~ ~ ~ #minecraft:logs run function {NS}:mine/tree_break"
                for d in ("~ ~1 ~", "~1 ~ ~", "~-1 ~ ~", "~ ~ ~1", "~ ~ ~-1", "~1 ~1 ~", "~-1 ~1 ~", "~ ~1 ~1", "~ ~1 ~-1")))
fn("mine/tree_break", f"setblock ~ ~ ~ minecraft:air destroy\nfunction {NS}:mine/tree")
w(f"data/{NS}/tags/block/no_area_break.json", {"values": ["minecraft:bedrock", "minecraft:barrier", "minecraft:end_portal_frame", "minecraft:end_portal",
   "minecraft:nether_portal", "minecraft:end_gateway", "minecraft:command_block", "minecraft:chain_command_block", "minecraft:repeating_command_block",
   "minecraft:structure_block", "minecraft:jigsaw", "minecraft:spawner", "minecraft:reinforced_deepslate", "minecraft:light", "#minecraft:shulker_boxes",
   "minecraft:chest", "minecraft:trapped_chest", "minecraft:barrel", "minecraft:ender_chest", "minecraft:obsidian", "minecraft:crying_obsidian",
   "minecraft:respawn_anchor", "minecraft:beacon", "#minecraft:beds", "minecraft:air", "minecraft:water", "minecraft:lava"]})
# area mining: a flat r-radius panel facing the player (like a hammer), never a full cube
for r in range(1, 8):
    lines = ["tag @s add ce.area"]
    for a in range(-r, r + 1):
        for b in range(-r, r + 1):
            if a == 0 and b == 0: continue
            lines.append(f"execute positioned ^{a} ^{b} ^ unless block ~ ~ ~ #{NS}:no_area_break run setblock ~ ~ ~ minecraft:air destroy")
    fn(f"mine/area_{r}", "\n".join([
        f"execute if entity @a[tag=ce.miner,limit=1,x_rotation=45..90] rotated 0 90 run function {NS}:mine/area_{r}_p",
        f"execute if entity @a[tag=ce.miner,limit=1,x_rotation=-90..-45] rotated 0 -90 run function {NS}:mine/area_{r}_p",
        f"execute if entity @a[tag=ce.miner,limit=1,x_rotation=-45..45] rotated as @a[tag=ce.miner,limit=1] rotated ~ 0 run function {NS}:mine/area_{r}_p"]))
    fn(f"mine/area_{r}_p", "\n".join(lines[1:]))

# ------------------------------------------------------------------ soulbound (keep on death)
died = ["scoreboard players reset @s ce.death",
        f"execute store result storage {NS}:tmp key.a int 1 run data get entity @s UUID[0]",
        f"execute store result storage {NS}:tmp key.b int 1 run data get entity @s UUID[1]",
        f"execute store result storage {NS}:tmp key.c int 1 run data get entity @s UUID[2]",
        f"execute store result storage {NS}:tmp key.d int 1 run data get entity @s UUID[3]"]
for name, lv in DEATH.items():
    for l, ch in sorted(lv.items()):
        lp = '{enchantments:"%s:%s",levels:%d}' % (NS, name, l)
        for age in (0, 1, 2):
            died.append(f"execute as @e[type=minecraft:item,distance=..4,nbt={{Age:{age}s}},tag=!ce.keep] if items entity @s contents *[minecraft:enchantments~[{lp}]] "
                        f"if predicate {NS}:chance/{int(ch)} run tag @s add ce.keep")
died += [f"execute if entity @e[tag=ce.keep,distance=..5] run tag @s add ce.sb",
         f"execute as @e[tag=ce.keep,distance=..5] run function {NS}:death/store with storage {NS}:tmp key",
         'execute if entity @s[tag=ce.sb] run tellraw @s {"text":"Soulbound items will return when you respawn.","color":"light_purple"}']
fn("death/died", "\n".join(died))
fn("death/store", f"$data modify storage {NS}:sb u$(a)_$(b)_$(c)_$(d) append from entity @s Item\nkill @s")
fn("death/respawned", f"""
tag @s remove ce.sb
execute store result storage {NS}:tmp key.a int 1 run data get entity @s UUID[0]
execute store result storage {NS}:tmp key.b int 1 run data get entity @s UUID[1]
execute store result storage {NS}:tmp key.c int 1 run data get entity @s UUID[2]
execute store result storage {NS}:tmp key.d int 1 run data get entity @s UUID[3]
function {NS}:death/give with storage {NS}:tmp key
""")
fn("death/give", f"""
$execute unless data storage {NS}:sb u$(a)_$(b)_$(c)_$(d)[0] run return 0
summon minecraft:item ~ ~ ~ {{Tags:["ce.ret"],Item:{{id:"minecraft:stone",count:1}},PickupDelay:0s}}
$data modify entity @e[tag=ce.ret,limit=1] Item set from storage {NS}:sb u$(a)_$(b)_$(c)_$(d)[0]
tag @e[tag=ce.ret] remove ce.ret
$data remove storage {NS}:sb u$(a)_$(b)_$(c)_$(d)[0]
$function {NS}:death/give {{a:$(a),b:$(b),c:$(c),d:$(d)}}
""")
for c in range(0, 101):
    w(f"data/{NS}/predicate/chance/{c}.json", {"condition": "minecraft:random_chance", "chance": c / 100})

# ------------------------------------------------------------------ migration of AdvancedEnchantments items
MAXL = {n: lv for n, _, lv, *_ in ENCH_LIST}
fn("migrate/apply", "\n".join(
    f"$execute if data entity @s $(p).components.\"minecraft:custom_data\".\"ae_enchantment;{n}\" run function {NS}:migrate/add {{p:'$(p)',s:\"$(s)\",e:\"{n}\",m:{lv}}}"
    for n, lv in MAXL.items()))
fn("migrate/add", f"""
$execute store result score #lv ce run data get entity @s $(p).components."minecraft:custom_data"."ae_enchantment;$(e)"
$scoreboard players set #max ce $(m)
execute if score #lv ce > #max ce run scoreboard players operation #lv ce = #max ce
execute if score #lv ce matches ..0 run return 0
execute store result storage {NS}:tmp lv int 1 run scoreboard players get #lv ce
$data modify storage {NS}:tmp e set value "$(e)"
$data modify storage {NS}:tmp s set value "$(s)"
function {NS}:migrate/set with storage {NS}:tmp
""")
fn("migrate/set", '$item modify entity @s $(s) {function:"minecraft:set_enchantments",add:true,enchantments:{"%s:$(e)":$(lv)}}' % NS)
for k in range(1, 16):
    w(f"data/{NS}/item_modifier/strip/{k}.json", {"function": "minecraft:set_lore", "mode": "replace_section", "offset": 0, "size": k, "lore": []})
SLOTS = [(f"Inventory[{{Slot:{i}b}}]", f"container.{i}") for i in range(36)] + \
        [(f"equipment.{s}", f"armor.{s}") for s in ("head", "chest", "legs", "feet")] + [("equipment.offhand", "weapon.offhand")] + \
        [(f"EnderItems[{{Slot:{i}b}}]", f"enderchest.{i}") for i in range(27)]
fn("migrate/all", f"scoreboard players set #mig ce 0\nexecute as @a run function {NS}:migrate/player")
# "if items" checks the slot without copying the player's whole NBT ("if data entity" does, per check: with
# inventories full of shulker boxes that was ~70 x 300 KB every 2 s and a 0.5 s lag spike), so only slots that hold an
# item with custom_data get the NBT checks
fn("migrate/player", "\n".join(
    f"execute if items entity @s {s} *[minecraft:custom_data] run function {NS}:migrate/slot {{p:'{p}',s:\"{s}\"}}" for p, s in SLOTS))
fn("migrate/slot", f"""
$execute store result score #n ce run data get entity @s $(p).components."minecraft:custom_data"
$execute if data entity @s $(p).components."minecraft:custom_data".slots run scoreboard players remove #n ce 1
$execute if data entity @s $(p).components."minecraft:custom_data".PublicBukkitValues run scoreboard players remove #n ce 1
$execute if data entity @s $(p).components."minecraft:custom_data".ench run scoreboard players remove #n ce 1
$execute if data entity @s $(p).components."minecraft:custom_data".blocktrak run scoreboard players remove #n ce 1
$execute unless function {NS}:migrate/is_ae run return 0
$data modify storage {NS}:tmp p set value '$(p)'
execute store result score #ae ce run function {NS}:migrate/has_ae with storage {NS}:tmp
execute unless score #ae ce matches 1 run return 0
execute store result storage {NS}:tmp n int 1 run scoreboard players get #n ce
$data modify storage {NS}:tmp s set value "$(s)"
function {NS}:migrate/strip with storage {NS}:tmp
$function {NS}:migrate/apply {{p:'$(p)',s:"$(s)"}}
$item modify entity @s $(s) {{function:"minecraft:set_components",components:{{"minecraft:custom_data":{{}}}}}}
""")
fn("migrate/is_ae", "execute if score #n ce matches 1.. if score #n ce matches ..15 run return 1\nreturn 0")
# only real AdvancedEnchantments items (an "ae_enchantment;<name>" key) are migrated: other items with a little
# custom_data (cyberware, Pack-a-Punch tiers, other datapacks' items) used to have their lore and data wiped
fn("migrate/has_ae", "\n".join(
    f"$execute if data entity @s $(p).components.\"minecraft:custom_data\".\"ae_enchantment;{n}\" run return 1" for n in MAXL) + "\nreturn 0")
fn("migrate/strip", f"$item modify entity @s $(s) {NS}:strip/$(n)")

# ------------------------------------------------------------------ enchanter (dialog + XP purchase)
books = {g: [] for g in GROUPS}
heroic = []
for n, g, lv, disp, desc, st in ENCH_LIST:
    if g == "HEROIC" and st.get("required-enchants"):
        req = str(st["required-enchants"][0]).split(":"); heroic.append((n, lv, req[0].lower(), int(req[1]) if len(req) > 1 else 1, disp))
    elif g in books: books[g].append((n, lv, disp, desc))
def book_cmd(n, lv, disp, desc, g):
    color = GROUPS[g][0]
    lore = [{"text": d, "color": "gray", "italic": False} for d in desc] + [{"text": f"{GROUPS[g][0] and g.title()} enchantment", "color": color, "italic": False}]
    return (f"$give @s minecraft:enchanted_book[minecraft:stored_enchantments={{\"{NS}:{n}\":$(l)}},"
            f"minecraft:lore={json.dumps(lore, ensure_ascii=False)}] 1")
TIERS = [g for g in TIER_ORDER if books.get(g)]
for i, g in enumerate(TIERS, start=1):
    lst = books[g]
    lines = [f"execute store result score #pick ce run random value 0..{len(lst) - 1}"]
    for j, (n, lv, disp, desc) in enumerate(lst):
        fn(f"enchanter/give/{n}", book_cmd(n, lv, disp, desc, g))
        lines.append(f"execute if score #pick ce matches {j} store result storage {NS}:tmp l int 1 run random value 1..{lv}")
        lines.append(f"execute if score #pick ce matches {j} run return run function {NS}:enchanter/give/{n} with storage {NS}:tmp")
    fn(f"enchanter/roll/{g.lower()}", "\n".join(lines))
# XP total helpers (points from levels)
fn("enchanter/xp_total", """
execute store result score #L ce run xp query @s levels
execute store result score #P ce run xp query @s points
scoreboard players operation #T ce = #L ce
# levels 0-16: L^2 + 6L
execute if score #L ce matches ..16 run scoreboard players operation #T ce *= #L ce
execute if score #L ce matches ..16 run scoreboard players operation #x ce = #L ce
execute if score #L ce matches ..16 run scoreboard players set #6 ce 6
execute if score #L ce matches ..16 run scoreboard players operation #x ce *= #6 ce
execute if score #L ce matches ..16 run scoreboard players operation #T ce += #x ce
# 17-31: 2.5L^2 - 40.5L + 360  -> (5L^2 - 81L + 720)/2
execute if score #L ce matches 17..31 run function crispy_enchants:enchanter/xp_mid
# 32+: 4.5L^2 - 162.5L + 2220 -> (9L^2 - 325L + 4440)/2
execute if score #L ce matches 32.. run function crispy_enchants:enchanter/xp_high
scoreboard players operation #T ce += #P ce
""")
fn("enchanter/xp_mid", """
scoreboard players operation #T ce = #L ce
scoreboard players operation #T ce *= #L ce
scoreboard players set #k ce 5
scoreboard players operation #T ce *= #k ce
scoreboard players set #k ce 81
scoreboard players operation #x ce = #L ce
scoreboard players operation #x ce *= #k ce
scoreboard players operation #T ce -= #x ce
scoreboard players add #T ce 720
scoreboard players set #k ce 2
scoreboard players operation #T ce /= #k ce
""")
fn("enchanter/xp_high", """
scoreboard players operation #T ce = #L ce
scoreboard players operation #T ce *= #L ce
scoreboard players set #k ce 9
scoreboard players operation #T ce *= #k ce
scoreboard players set #k ce 325
scoreboard players operation #x ce = #L ce
scoreboard players operation #x ce *= #k ce
scoreboard players operation #T ce -= #x ce
scoreboard players add #T ce 4440
scoreboard players set #k ce 2
scoreboard players operation #T ce /= #k ce
""")
fn("enchanter/pay", f"""
# #price ce = cost in points; returns 1 when paid
function {NS}:enchanter/xp_total
execute if score #T ce < #price ce run return run tellraw @s [{{"text":"You need ","color":"red"}},{{"score":{{"name":"#price","objective":"ce"}},"color":"gold"}},{{"text":" XP (you have ","color":"red"}},{{"score":{{"name":"#T","objective":"ce"}},"color":"gold"}},{{"text":").","color":"red"}}]
scoreboard players operation #T ce -= #price ce
xp set @s 0 levels
xp set @s 0 points
execute store result storage {NS}:tmp xp int 1 run scoreboard players get #T ce
function {NS}:enchanter/xp_set with storage {NS}:tmp
return 1
""")
fn("enchanter/xp_set", "$xp add @s $(xp) points")
buy = [f"scoreboard players operation #b ce = @s ce.buy", "scoreboard players set @s ce.buy 0"]
for i, g in enumerate(TIERS, start=1):
    buy.append(f"execute if score #b ce matches {i} run scoreboard players set #price ce {GROUPS[g][1]}")
    buy.append(f"execute if score #b ce matches {i} if function {NS}:enchanter/pay run function {NS}:enchanter/got/{g.lower()}")
    fn(f"enchanter/got/{g.lower()}", f"""
function {NS}:enchanter/roll/{g.lower()}
playsound minecraft:block.enchantment_table.use master @s ~ ~ ~ 1 1
tellraw @s [{{"text":"✦ You bought a ","color":"gray"}},{{"text":"{g.title()}","color":"{GROUPS[g][0]}","bold":true}},{{"text":" enchantment book! Combine it with an item in an anvil.","color":"gray"}}]
""")
buy.append(f"execute if score #b ce matches 50 run function {NS}:enchanter/heroic")
fn("enchanter/buy", "\n".join(buy))
# heroic upgrade of the held item
h = ["scoreboard players set #did ce 0"]
for n, lv, base, need, disp in heroic:
    if base not in MAXL: continue
    bp = '{enchantments:"%s:%s",levels:{min:%d}}' % (NS, base, need)
    h.append(f"execute if score #did ce matches 0 if items entity @s weapon.mainhand *[minecraft:enchantments~[{bp}]] run function {NS}:enchanter/heroic_do/{n}")
    fn(f"enchanter/heroic_do/{n}", f"""
scoreboard players set #did ce 1
scoreboard players set #price ce {GROUPS['HEROIC'][1]}
execute unless function {NS}:enchanter/pay run return 0
item modify entity @s weapon.mainhand {{"function":"minecraft:set_enchantments","add":false,"enchantments":{{"{NS}:{base}":0}}}}
execute store result storage {NS}:tmp l int 1 run random value 1..{lv}
function {NS}:enchanter/heroic_set/{n} with storage {NS}:tmp
playsound minecraft:ui.toast.challenge_complete master @s ~ ~ ~ 1 1
tellraw @s [{{"text":"✦ Upgraded to ","color":"gray"}},{{"text":"{disp}","color":"light_purple","bold":true}},{{"text":"!","color":"gray"}}]
""")
    fn(f"enchanter/heroic_set/{n}", f"$item modify entity @s weapon.mainhand {{\"function\":\"minecraft:set_enchantments\",\"add\":false,\"enchantments\":{{\"{NS}:{n}\":$(l)}}}}")
h.append('execute if score #did ce matches 0 run tellraw @s {"text":"Hold an item with the base enchantment at the required level (e.g. Overload III → Godly Overload). Upgrades cost 50,000 XP.","color":"red"}')
fn("enchanter/heroic", "\n".join(h))

def btn(label, cmd, tip, width=230):
    return {"label": label, "tooltip": {"text": tip}, "width": width, "action": {"type": "minecraft:run_command", "command": cmd}}
acts = [btn({"text": f"{g.title()} book", "color": GROUPS[g][0], "bold": True}, f"trigger ce.buy set {i}",
            f"Random {g.title()} enchantment book — {GROUPS[g][1]:,} XP points ({len(books[g])} possible)") for i, g in enumerate(TIERS, start=1)]
acts.append(btn({"text": "Heroic upgrade (held item)", "color": "light_purple", "bold": True}, "trigger ce.buy set 50",
                "Upgrades a base enchantment on the item in your hand to its Heroic version — 50,000 XP points"))
w(f"data/{NS}/dialog/enchanter.json", {
    "type": "minecraft:multi_action", "title": {"text": "✦ Enchanter ✦", "color": "light_purple", "bold": True},
    "body": [{"type": "minecraft:plain_message", "width": 300, "contents": [
        {"text": "Buy random custom enchantment books with XP, then combine them with your gear in an anvil.\n", "color": "gray"},
        {"text": "Prices are in XP points.", "color": "dark_gray"}]}],
    "actions": acts, "columns": 1, "exit_action": {"label": {"text": "Close"}, "width": 150},
    "can_close_with_escape": True, "pause": False, "after_action": "close"})
# open the dialog when a player right-clicks the enchanter's interaction box
w(f"data/{NS}/advancement/enchanter.json", {"criteria": {"c": {"trigger": "minecraft:player_interacted_with_entity",
   "conditions": {"entity": [ent("this", {"minecraft:entity_type": "minecraft:interaction", "minecraft:nbt": "{Tags:[\"ce.enchanter\"]}"})]}}},
   "rewards": {"function": f"{NS}:enchanter/open"}})
fn("enchanter/open", f"advancement revoke @s only {NS}:enchanter\ndialog show @s {NS}:enchanter\nexecute as @e[type=minecraft:interaction,tag=ce.enchanter,distance=..8] run data remove entity @s interaction")
fn("enchanter/place", f"""
# run at the spot where the enchanter should stand (facing direction from the executor)
kill @e[tag=ce.enchanter]
summon minecraft:villager ~ ~ ~ {{Tags:["ce.enchanter","crispy_shop"],Rotation:[90f,0f],NoAI:1b,Invulnerable:1b,Silent:1b,PersistenceRequired:1b,CustomNameVisible:1b,CustomName:{{"text":"✦ Enchanter ✦","color":"light_purple","bold":true}},VillagerData:{{profession:"minecraft:librarian",level:5,type:"minecraft:swamp"}},Offers:{{Recipes:[]}}}}
summon minecraft:interaction ~ ~ ~ {{Tags:["ce.enchanter"],width:1.2f,height:2.2f,response:1b}}
""")

# ------------------------------------------------------------------ listing for admins
fn("admin/give", f"$give @s minecraft:enchanted_book[minecraft:stored_enchantments={{\"{NS}:$(e)\":$(l)}}] 1")
print(f"enchantments: {len(ENCH_LIST)}; fx functions: {fx_count}; mining: {len(MINING)}; soulbound: {len(DEATH)}; heroic: {len(heroic)}; tiers: {TIERS}")
