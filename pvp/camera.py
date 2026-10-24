"""Cinematic camera rig for recording trailers/TikToks on the PvP server: builds the crispy_cam datapack.

A shot puts the viewer (tag cam.viewer) in spectator mode, locks their view to an invisible marker armor stand and
moves that stand along a path every tick. The client interpolates entity movement, so the camera glides at any
recording frame rate. Each shot holds still for 1 s first, so recording can start cleanly.

  python3 camera.py <out dir>      -> <out>/crispy_cam
  tag <player> add cam.viewer, then: function cam:start/<shot>   (function cam:stop to end early)
"""
import json, math, os, re, sys

AY = -61                      # arena floor level (build.py)
TPS = 20
HOLD = 20                     # still frames before a shot moves


def ease(t): return t * t * (3 - 2 * t)          # smoothstep: soft start and stop
def lerp(a, b, t): return a + (b - a) * t
def look(frm, at):
    dx, dy, dz = at[0] - frm[0], at[1] - frm[1], at[2] - frm[2]
    return math.degrees(math.atan2(-dx, dz)), -math.degrees(math.atan2(dy, math.hypot(dx, dz)))


def colosseum_orbit(t):
    """A 270° sweep around the colosseum from above the stands, always on the arena floor's centre."""
    c = (0.5, AY + 3, 100.5)
    a = math.radians(lerp(200, -70, ease(t)))
    r = lerp(34, 28, t)
    p = (c[0] + r * math.cos(a), lerp(AY + 12, AY + 8, ease(t)), c[2] + r * math.sin(a))
    return p, look(p, c)


def colosseum_rise(t):
    """Low through the south gate towards the emperor's box, then a crane up to look down on the floor."""
    box = (0.5, AY + 9, 58.5)
    if t < 0.55:
        u = ease(t / 0.55)
        p = (0.5, AY + 2.2, lerp(132, 112, u))
        return p, look(p, box)
    u = ease((t - 0.55) / 0.45)
    p = (0.5, lerp(AY + 2.2, AY + 24, u), lerp(112, 104, u))
    yaw, pitch = look(p, box)
    return p, (yaw, lerp(pitch, 78, u))


def orbital_ring(t):
    """Eye level around the Orbital Station's outer ring (r 27 is clear of pods, racks and benches)."""
    c = (0.5, 700.5)
    a = math.radians(lerp(0, 360, t) + 45)
    p = (c[0] + 27 * math.cos(a), AY + 2.6, c[1] + 27 * math.sin(a))
    ahead = math.radians(lerp(0, 360, t) + 45 + 25)
    q = (c[0] + 24 * math.cos(ahead), AY + 2.4, c[1] + 24 * math.sin(ahead))
    return p, look(p, q)


def orbital_spoke(t):
    """From the outer ring down the east spoke into the hub, ending on the reactor."""
    p = (lerp(29.5, 7.5, ease(t)), AY + lerp(2.6, 3.4, ease(t)), 700.5)
    return p, look(p, (0.5, AY + lerp(2.4, 4.5, t), 700.5))


def lobby_orbit(t):
    """A slow circle over the PvP lobby."""
    c = (0.5, 101.5, 0.5)
    a = math.radians(lerp(-30, 150, ease(t)))
    p = (c[0] + 15 * math.cos(a), lerp(108, 104, ease(t)), c[2] + 15 * math.sin(a))
    return p, look(p, c)


# ---------------------------------------------------------------- staged scenes: mannequin actors (tag cam.actor)
HEADS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "heads.json")))


def mannequin(tag, pos, yaw, pitch, skin, name=None, scale=1.0, gear=""):
    """A skinned mannequin. name "Dinnerbone" turns it upside down (hidden name)."""
    x, y, z = pos
    nm = f',CustomName:"{name}",CustomNameVisible:0b' if name else ""
    return (f"summon minecraft:mannequin {x:.2f} {y:.2f} {z:.2f} {{Tags:[\"cam.actor\",\"{tag}\"],Rotation:[{yaw:.1f}f,{pitch:.1f}f],"
            f"Invulnerable:1b,Silent:1b,NoGravity:1b,immovable:1b,hide_description:1b{nm},"
            f"profile:{{properties:[{{name:\"textures\",value:\"{HEADS[skin]}\"}}]}},"
            f"attributes:[{{id:\"minecraft:scale\",base:{scale}d}}]{gear}}}")


# "I have to fight him, Sharon": Randy and a giant Adam Smasher both pop their Sandevistans. Randy dives upside
# down, Smasher leaps to meet him, they clash mid-air, Randy is swatted away and Smasher slams down. Filmed side-on
# so the clash reads top to bottom in a 9:16 frame and both stay in shot the whole time.
SC = (0.5, AY + 1, 100.5)                   # stage centre (floor level)
SECS = 8
T_ON, T_HIT, T_OFF, T_LAND = 1.0, 3.4, 5.8, 4.4   # Sandevistans on, the clash, trails off, Smasher lands
R0, RM, R_END = (-3.2, 11.5), (-0.5, 6.9), (-4.4, 0.0)   # Randy (x, y) relative to SC: start, clash, end
S0, SM, S_END = (2.6, 0.0), (1.0, 3.6), (1.4, 0.0)       # Smasher: start, clash (mid-leap), landing
GHOST_EVERY, GHOST_LIFE = 2, 16             # after-image spacing and lifetime (ticks); cyber:ghost/age fades and removes them


def _arc(a, b, u, h=0.0): return (lerp(a[0], b[0], u), lerp(a[1], b[1], u) + h * math.sin(math.pi * u))


def randy_at(s):
    if s < T_ON: return R0
    if s < T_HIT: return _arc(R0, RM, ((s - T_ON) / (T_HIT - T_ON)) ** 1.6)
    u = min(1, (s - T_HIT) / 2.4)
    return _arc(RM, R_END, 1 - (1 - u) ** 2, h=3.0)


def smasher_at(s):
    if s < 1.8: return (lerp(S0[0], S0[0] - 0.3, max(0, s - T_ON) / 0.8), 0.0)   # a short wind-up step
    if s < T_HIT:
        u = (s - 1.8) / (T_HIT - 1.8)
        return (lerp(S0[0] - 0.3, SM[0], u), SM[1] * (1 - (1 - u) ** 2))             # leap, slowing at the top
    u = min(1, (s - T_HIT) / (T_LAND - T_HIT))
    return (lerp(SM[0], S_END[0], u), SM[1] * (1 - u * u))                          # drop into the slam


def w(rel, dy=0.0): return (SC[0] + rel[0], SC[1] + rel[1] + dy, SC[2])


def sharon_cam(t):
    s = t * SECS
    push = ease(min(1, s / T_HIT))
    shake = 0.12 * math.sin(s * 90) if T_HIT <= s < T_HIT + 0.3 or T_LAND <= s < T_LAND + 0.25 else 0.0
    p = (SC[0] + shake, SC[1] + 5.2 + shake, SC[2] + lerp(15.0, 12.5, push))
    return p, look(p, (SC[0], SC[1] + 5.2, SC[2]))


def ghost(tag, pos, yaw, skin, scale, flip):
    x, y, z = pos
    nm = ',CustomName:"Dinnerbone"' if flip else ""
    return [f"summon minecraft:mannequin {x:.2f} {y:.2f} {z:.2f} {{Tags:[\"cy.ghost\",\"cam.gnew\"],Rotation:[{yaw:.1f}f,0f],NoGravity:1b,"
            f"Invulnerable:1b,Silent:1b,immovable:1b,hide_description:1b,Glowing:1b{nm},"
            f"active_effects:[{{id:\"minecraft:invisibility\",duration:-1,amplifier:0b,show_particles:0b}}],"
            f"profile:{{properties:[{{name:\"textures\",value:\"{HEADS[skin]}\"}}]}},attributes:[{{id:\"minecraft:scale\",base:{scale}d}}]}}",
            "team join cy.g1 @e[type=minecraft:mannequin,tag=cam.gnew]",
            f"scoreboard players set @e[type=minecraft:mannequin,tag=cam.gnew] cy.gl {GHOST_LIFE}",
            "tag @e[type=minecraft:mannequin,tag=cam.gnew] remove cam.gnew"]


def sharon_frame(k, n):
    s = k / TPS
    r, sm = w(randy_at(s)), w(smasher_at(s))
    spin = 0 if s < T_HIT else 900 * min(1, (s - T_HIT) / 2.4)
    ryaw = (-90 + spin) % 360 - 180
    out = [f"tp @e[type=minecraft:mannequin,tag=cam.randy,limit=1] {r[0]:.3f} {r[1]:.3f} {r[2]:.3f} {ryaw:.1f} 0",
           f"execute as @e[type=minecraft:mannequin,tag=cam.smasher,limit=1] at @s positioned {sm[0]:.3f} {sm[1]:.3f} {sm[2]:.3f} "
           f"facing {r[0]:.2f} {r[1] + 0.5:.2f} {r[2]:.2f} run tp @s ~ ~ ~ ~ ~"]
    f = lambda tt: round(tt * TPS)
    if T_ON <= s < T_OFF and k % GHOST_EVERY == 0:
        out += ghost("randy", r, ryaw, "randy", 1.0, True)
        out += ghost("smasher", sm, 90, "smasher", 1.8, False)
    if k == f(T_ON):   # both Sandevistans kick in
        for (x, y, z), h in ((r, 1), (sm, 2)):
            out += [f"particle minecraft:electric_spark {x:.2f} {y + h:.2f} {z:.2f} 1 1 1 0.5 120 force",
                    f"particle minecraft:dust{{color:[0.2,1.0,0.85],scale:1.2}} {x:.2f} {y + h:.2f} {z:.2f} 0.6 1 0.6 0 40 force"]
        out += [f"playsound minecraft:block.beacon.power_select master @a {SC[0]} {SC[1] + 5} {SC[2]} 2 2",
                f"playsound minecraft:block.beacon.activate master @a {SC[0]} {SC[1] + 5} {SC[2]} 2 1.6"]
    if k == f(T_HIT):  # the clash
        x, y, z = w(RM)
        out += [f"particle minecraft:explosion_emitter {x:.2f} {y:.2f} {z:.2f} 0 0 0 0 1 force",
                f"particle minecraft:electric_spark {x:.2f} {y:.2f} {z:.2f} 1.5 1.5 1.5 1 200 force",
                f"particle minecraft:crit {x:.2f} {y:.2f} {z:.2f} 1 1 1 0.8 120 force",
                f"playsound minecraft:entity.generic.explode master @a {x:.2f} {y:.2f} {z:.2f} 2 0.7",
                f"playsound minecraft:block.anvil.land master @a {x:.2f} {y:.2f} {z:.2f} 1.5 0.6"]
    if k == f(T_LAND):  # Borg Slam landing
        x, y, z = sm
        out += [f"particle minecraft:explosion {x:.2f} {y + 0.2:.2f} {z:.2f} 1.5 0.1 1.5 0 12 force",
                f"particle minecraft:block{{block_state:\"minecraft:sand\"}} {x:.2f} {y + 0.2:.2f} {z:.2f} 2.5 0.2 2.5 0.3 160 force",
                f"playsound minecraft:entity.iron_golem.damage master @a {x:.2f} {y:.2f} {z:.2f} 2 0.5",
                f"playsound minecraft:entity.generic.explode master @a {x:.2f} {y:.2f} {z:.2f} 1.5 1.2"]
    if k == f(T_HIT + 2.4):
        x, y, z = w(R_END)
        out.append(f"playsound minecraft:entity.player.big_fall master @a {x:.2f} {y:.2f} {z:.2f} 1.5 1")
    return out


SHARON_SETUP = [
    mannequin("cam.smasher", w(S0), 90, -30, "smasher", scale=1.8,
              gear=',equipment:{head:{id:"minecraft:netherite_helmet",count:1},chest:{id:"minecraft:netherite_chestplate",count:1},'
                   'legs:{id:"minecraft:netherite_leggings",count:1},feet:{id:"minecraft:netherite_boots",count:1},mainhand:{id:"minecraft:netherite_axe",count:1}}'),
    mannequin("cam.randy", w(R0), -90, 0, "randy", name="Dinnerbone"),
    "team join cam.actors @e[type=minecraft:mannequin,tag=cam.actor]",
]

# Close-up of the meme's frame: both faces to camera in slow motion. Randy upside down at the top, Smasher's face in
# the bottom-right looking up at him; both drift in so their Sandevistan after-images stack up behind them.
CU_SECS = 7
CU_FLOOR = (0.5, AY + 1, 100.5)
CU_C = (CU_FLOOR[0], CU_FLOOR[1] + 5.25, CU_FLOOR[2])           # frame centre
CU_R0, CU_R1 = (1.7, 2.3, 0.0), (0.0, 1.15, 0.0)                 # Randy's feet-origin (x, y above centre, z) start/end
CU_S0, CU_S1 = (2.5, -5.25, 1.0), (1.15, -5.25, 0.8)             # Smasher's feet: start/end (face ends bottom-right)
CU_MOVE = (0.6, 5.6)                                              # slow drift window (s); the clash at its end
CU_LIFE = 30                                                      # longer trails than the wide shot


def cu_at(a, b, s):
    u = ease(min(1, max(0, (s - CU_MOVE[0]) / (CU_MOVE[1] - CU_MOVE[0]))))
    return tuple(CU_C[i] + lerp(a[i], b[i], u) for i in range(3))


def closeup_cam(t):
    s = t * CU_SECS
    d = lerp(5.6, 4.7, ease(min(1, s / CU_MOVE[1])))
    shake = 0.08 * math.sin(s * 95) if CU_MOVE[1] <= s < CU_MOVE[1] + 0.35 else 0.0
    p = (CU_C[0] + shake, CU_C[1] + 0.1 * math.sin(s * 0.8) + shake, CU_C[2] + d)
    return p, (180.0, 0.0)


def closeup_frame(k, n):
    s = k / TPS
    r, sm = cu_at(CU_R0, CU_R1, s), cu_at(CU_S0, CU_S1, s)
    out = [f"tp @e[type=minecraft:mannequin,tag=cam.randy,limit=1] {r[0]:.3f} {r[1]:.3f} {r[2]:.3f} 0 0",
           f"tp @e[type=minecraft:mannequin,tag=cam.smasher,limit=1] {sm[0]:.3f} {sm[1]:.3f} {sm[2]:.3f} 28 -28"]
    if CU_MOVE[0] - 0.4 <= s < CU_MOVE[1] and k % GHOST_EVERY == 0:
        for g in ghost("randy", r, 0, "randy", 1.0, True) + ghost("smasher", sm, 28, "smasher", 1.8, False):
            out.append(g.replace(f"cy.gl {GHOST_LIFE}", f"cy.gl {CU_LIFE}"))
    if k == round((CU_MOVE[0] - 0.4) * TPS):
        for (x, y, z) in ((r[0], r[1] + 0.4, r[2]), (sm[0], sm[1] + 3.0, sm[2])):
            out += [f"particle minecraft:electric_spark {x:.2f} {y:.2f} {z:.2f} 0.6 0.6 0.6 0.4 80 force",
                    f"particle minecraft:dust{{color:[0.2,1.0,0.85],scale:1.0}} {x:.2f} {y:.2f} {z:.2f} 0.5 0.5 0.5 0 30 force"]
        out += [f"playsound minecraft:block.beacon.power_select master @a {CU_C[0]} {CU_C[1]} {CU_C[2]} 2 2",
                f"playsound minecraft:block.beacon.activate master @a {CU_C[0]} {CU_C[1]} {CU_C[2]} 2 1.6"]
    if k == round(CU_MOVE[1] * TPS):
        x, y, z = CU_C[0] + 0.6, CU_C[1] - 0.6, CU_C[2] + 0.4
        out += [f"particle minecraft:explosion_emitter {x:.2f} {y:.2f} {z:.2f} 0 0 0 0 1 force",
                f"particle minecraft:electric_spark {x:.2f} {y:.2f} {z:.2f} 1 1 1 0.8 160 force",
                f"playsound minecraft:entity.generic.explode master @a {x:.2f} {y:.2f} {z:.2f} 2 0.7",
                f"playsound minecraft:block.anvil.land master @a {x:.2f} {y:.2f} {z:.2f} 1.5 0.6"]
    return out


CLOSEUP_SETUP = [
    mannequin("cam.smasher", tuple(CU_C[i] + CU_S0[i] for i in range(3)), 28, -28, "smasher", scale=1.8,
              gear=',equipment:{chest:{id:"minecraft:netherite_chestplate",count:1},legs:{id:"minecraft:netherite_leggings",count:1},'
                   'feet:{id:"minecraft:netherite_boots",count:1},mainhand:{id:"minecraft:netherite_axe",count:1}}'),
    mannequin("cam.randy", tuple(CU_C[i] + CU_R0[i] for i in range(3)), 0, 0, "randy", name="Dinnerbone"),
    "team join cam.actors @e[type=minecraft:mannequin,tag=cam.actor]",
]

# ---------------------------------------------------------------- the brawl: a full arena of characters fighting
# Mannequins can't fight, so fighters are zombies dressed as the PvP characters (their real head, the kit's armour
# colours and main weapon, kit size, name above the head). Zombies only fight back when hit, so every 2 s a few
# random fighters are "hit" by their nearest neighbour and the brawl keeps itself going. Fallen fighters are
# replaced, keeping BRAWL_N on the floor. cam:brawl/start, cam:brawl/stop; film it with cam:start/brawl_orbit.
BRAWL_N = 16
BRAWL_C = (0.5, AY + 1, 100.5)
SKIP_GIVE = ("clay_ball", "potion", "splash_potion", "lingering_potion", "cooked_beef", "golden_apple", "arrow",
             "spectral_arrow", "tipped_arrow", "firework_rocket", "bread", "cookie", "ender_pearl", "totem_of_undying")


def fighters():
    sys.argv = sys.argv[:1]
    import build
    out = []
    for k in build.KITS:
        key, name, color, cmds = k[1], k[2], k[3], k[6]
        joined = "\n".join(c for c in cmds if isinstance(c, str))
        eq = {}
        for slot, piece in (("chest", "chestplate"), ("legs", "leggings"), ("feet", "boots")):
            m = re.findall(rf"armor\.{slot} with minecraft:([a-z_]+_{piece})(\[[^\n]*)?", joined)
            if m:
                iid, comps = m[-1]
                dye = re.search(r"dyed_color=(\d+)", comps or "")
                eq[slot] = f'{{id:"minecraft:{iid}",count:1' + (f',components:{{"minecraft:dyed_color":{dye.group(1)}}}' if dye else "") + "}"
        for m in re.finditer(r"(?m)^give @s minecraft:([a-z_]+)(\[[^\n]*)?", joined):
            if m.group(1) in SKIP_GIVE: continue
            model = re.search(r'item_model="(minecraft:[a-z_]+)"', m.group(2) or "")
            eq["mainhand"] = f'{{id:"minecraft:{m.group(1)}",count:1' + (f',components:{{"minecraft:item_model":"{model.group(1)}"}}' if model else "") + "}"
            break
        hk = {"samurai": "edgerunner", "assassin": "lucy"}.get(key, key)
        eq["head"] = f'{{id:"minecraft:player_head",count:1,components:{{"minecraft:profile":{{properties:[{{name:"textures",value:"{HEADS[hk]}"}}]}}}}}}'
        size = re.search(r"pvp:size (-?[0-9.]+)", joined)
        out.append((key, name, color, eq, round(1 + float(size.group(1)), 2) if size else 1.0))
    return out


def brawl_spawn(key, name, color, eq, scale):
    gear = ",".join(f"{k}:{v}" for k, v in eq.items())
    nm = json.dumps({"text": name, "color": color, "bold": True}, separators=(",", ":"))
    return (f"summon minecraft:zombie ~ ~ ~ {{Tags:[\"cam.brawl\"],IsBaby:0b,CanBreakDoors:0b,PersistenceRequired:1b,CanPickUpLoot:0b,"
            f"DeathLootTable:\"minecraft:empty\",CustomName:{nm},CustomNameVisible:1b,equipment:{{{gear}}},"
            "drop_chances:{head:0f,chest:0f,legs:0f,feet:0f,mainhand:0f},Health:60f,"
            f"attributes:[{{id:\"minecraft:max_health\",base:60d}},{{id:\"minecraft:scale\",base:{scale}d}},"
            "{id:\"minecraft:spawn_reinforcements\",base:0d},{id:\"minecraft:follow_range\",base:48d},"
            "{id:\"minecraft:movement_speed\",base:0.3d}]}")


def build_brawl(fn):
    fs = fighters()
    for f in fs: fn(f"brawl/spawn/{f[0]}", [brawl_spawn(*f)])
    pts = [(BRAWL_C[0] + 13 * math.cos(math.radians(a)), BRAWL_C[1], BRAWL_C[2] + 13 * math.sin(math.radians(a))) for a in range(0, 360, 30)]
    one = ["execute store result score #r cam run random value 1..%d" % len(fs), "execute store result score #p cam run random value 1..%d" % len(pts)]
    for j, (x, y, z) in enumerate(pts, 1):
        one.append(f"execute if score #p cam matches {j} run data modify storage cam:b p set value {{x:{x:.2f},y:{y:.2f},z:{z:.2f}}}")
    one.append("function cam:brawl/at with storage cam:b p")
    fn("brawl/one", one)
    fn("brawl/at", ["$execute positioned $(x) $(y) $(z) run function cam:brawl/pick",
                    "$particle minecraft:large_smoke $(x) $(y) $(z) 0.4 0.8 0.4 0.02 25 force",
                    "$playsound minecraft:entity.evoker.prepare_summon master @a $(x) $(y) $(z) 0.6 1.4"])
    fn("brawl/pick", [f"execute if score #r cam matches {i} run function cam:brawl/spawn/{f[0]}" for i, f in enumerate(fs, 1)])
    fn("brawl/start", ["function cam:brawl/stop", f"forceload add -56 44 56 156", "scoreboard players set #brawl cam 1",
                       "scoreboard players set #bt cam 0"]
       + ["function cam:brawl/one"] * BRAWL_N)
    fn("brawl/tick", [
        "scoreboard players add #bt cam 1",
        # keep the floor full (one replacement every half second)
        "execute store result score #n cam if entity @e[type=minecraft:zombie,tag=cam.brawl]",
        f"execute if score #n cam matches ..{BRAWL_N - 1} if score #bt cam matches 1 run function cam:brawl/one",
        f"execute if score #n cam matches ..{BRAWL_N - 1} if score #bt cam matches 21 run function cam:brawl/one",
        # provoke: a few random fighters get "hit" by their nearest neighbour, who they then go after
        "execute if score #bt cam matches 1 as @e[type=minecraft:zombie,tag=cam.brawl,sort=random,limit=4] at @s run "
        "damage @s 1.5 minecraft:mob_attack by @e[type=minecraft:zombie,tag=cam.brawl,distance=0.5..,sort=nearest,limit=1]",
        # nobody wanders off the floor or goes after a spectator
        f"execute as @e[type=minecraft:zombie,tag=cam.brawl] at @s unless entity @s[x={BRAWL_C[0] - 30},y={BRAWL_C[1] - 3},z={BRAWL_C[2] - 30},dx=60,dy=20,dz=60] run tp @s {BRAWL_C[0]} {BRAWL_C[1]} {BRAWL_C[2]}",
        "execute if score #bt cam matches 40.. run scoreboard players set #bt cam 0",
    ])
    fn("brawl/stop", ["scoreboard players set #brawl cam 0",
                      "execute as @e[type=minecraft:zombie,tag=cam.brawl] at @s run tp @s ~ -1000 ~", "kill @e[type=minecraft:zombie,tag=cam.brawl]",
                      "forceload remove -56 44 56 156"])
    return ["execute if score #brawl cam matches 1 run function cam:brawl/tick"]


def brawl_orbit(t):
    """Low and close around the brawl: a full slow circle at head height, then rising for the wide view."""
    c = (BRAWL_C[0], AY + 2, BRAWL_C[2])
    a = math.radians(lerp(90, 450, t))
    r = lerp(17, 22, ease(t))
    p = (c[0] + r * math.cos(a), AY + lerp(3.5, 12, ease(max(0, t - 0.55) / 0.45)), c[2] + r * math.sin(a))
    return p, look(p, c)


# ---------------------------------------------------------------- Outbreak "wave 20" (staged)
# A real run needs a living player in it (it ends the moment none is left) and records best waves, so this is staged
# with the same ingredients instead: Hellfort's wave-20 mob mix and stats (+15% health and +8% damage per wave past
# the first: x3.85 health, x2.52 damage), 30 alive at once like the real cap, the wave-20 boss, and a squad of
# character survivors making a last stand in the middle. Mobs and survivors are provoked into each other every second.
# cam:horde/start, cam:horde/stop; film with cam:start/horde_orbit and cam:start/horde_dolly.
H_C = (0.5, AY + 1, 600.5)                  # Hellfort centre
H_WAVE = 20
H_HM, H_DM = round(0.15 * (H_WAVE - 1), 2), round(0.08 * (H_WAVE - 1), 2)
H_ALIVE = 30
H_POINTS = [(30, 0), (-30, 0), (0, 30), (0, -30), (30, 16), (30, -16), (-30, 16), (-30, -16), (16, 30), (-16, 30), (16, -30), (-16, -30)]
BOW = ',equipment:{mainhand:{id:"minecraft:bow",count:1}},drop_chances:{mainhand:0.0f}'
H_POOL = [  # (roll <=, type, extra) - Hellfort's own mobs get the first roll, then the normal pool, as in build.py
    ("map", 12, "wither_skeleton", ',equipment:{mainhand:{id:"minecraft:stone_sword",count:1}},drop_chances:{mainhand:0.0f}'),
    ("map", 20, "blaze", ""),
    ("pool", 10, "wither_skeleton", ',equipment:{mainhand:{id:"minecraft:stone_sword",count:1}},drop_chances:{mainhand:0.0f}'),
    ("pool", 22, "vindicator", ',equipment:{mainhand:{id:"minecraft:iron_axe",count:1}},drop_chances:{mainhand:0.0f}'),
    ("pool", 30, "creeper", ""), ("pool", 45, "spider", ""), ("pool", 60, "skeleton", BOW), ("pool", 75, "husk", ""),
    ("pool", 100, "zombie", ""),
]
SURVIVORS = [("doom", 0, -3), ("spartan", 3, 1), ("mando", -3, 1), ("smasher", 0, 3), ("witcher", 2, -2)]


def build_horde(fn):
    one = ["execute store result score #r2 cam run random value 1..100", "execute store result score #r cam run random value 1..100",
           "scoreboard players set #pk cam 0", "execute store result score #p cam run random value 1..%d" % len(H_POINTS)]
    for j, (dx, dz) in enumerate(H_POINTS, 1):
        one.append(f"execute if score #p cam matches {j} run data modify storage cam:h p set value {{x:{H_C[0] + dx:.1f},y:{H_C[1]},z:{H_C[2] + dz:.1f}}}")
    for (which, roll, typ, extra) in H_POOL:
        sc = "#r2" if which == "map" else "#r"
        one.append(f"execute if score #pk cam matches 0 if score {sc} cam matches ..{roll} run data modify storage cam:h p merge value {{type:\"{typ}\",extra:'{extra}'}}")
        one.append(f"execute if score #pk cam matches 0 if score {sc} cam matches ..{roll} run scoreboard players set #pk cam 1")
    one.append("function cam:horde/summon with storage cam:h p")
    fn("horde/one", one)
    fn("horde/summon", [
        "$summon minecraft:$(type) $(x) $(y) $(z) {Tags:[\"cam.horde\",\"cam.hnew\"],PersistenceRequired:1b,CanPickUpLoot:0b,"
        "DeathLootTable:\"minecraft:empty\",attributes:[{id:\"minecraft:follow_range\",base:64d},{id:\"minecraft:spawn_reinforcements\",base:0d}]$(extra)}",
        "$particle minecraft:large_smoke $(x) $(y) $(z) 0.3 0.5 0.3 0.02 20 force",
        "execute as @e[tag=cam.hnew] run function cam:horde/scale"])
    fn("horde/scale", ["tag @s remove cam.hnew",
                       f"attribute @s minecraft:max_health modifier add cam:wave {H_HM} add_multiplied_base",
                       f"attribute @s minecraft:attack_damage modifier add cam:wave {H_DM} add_multiplied_base",
                       "execute store result entity @s Health float 1 run attribute @s minecraft:max_health get"])
    boss = (f"summon minecraft:zombie {H_C[0]} {H_C[1]} {H_C[2] + 18} {{Tags:[\"cam.horde\",\"cam.hnew\",\"cam.boss\"],PersistenceRequired:1b,CanPickUpLoot:0b,"
            "DeathLootTable:\"minecraft:empty\",IsBaby:0b,CustomName:{\"text\":\"Abomination\",\"color\":\"dark_red\",\"bold\":true},CustomNameVisible:1b,"
            "attributes:[{id:\"minecraft:follow_range\",base:64d},{id:\"minecraft:scale\",base:2.0d},{id:\"minecraft:max_health\",base:150d},"
            "{id:\"minecraft:attack_damage\",base:9d},{id:\"minecraft:knockback_resistance\",base:0.8d},{id:\"minecraft:movement_speed\",base:0.26d},"
            "{id:\"minecraft:spawn_reinforcements\",base:0d}]}")
    surv = []
    for (key, dx, dz) in SURVIVORS:
        surv += [f"execute positioned {H_C[0] + dx} {H_C[1]} {H_C[2] + dz} run function cam:brawl/spawn/{key}",
                 "tag @e[type=minecraft:zombie,tag=cam.brawl,tag=!cam.surv,tag=!cam.horde] add cam.surv"]
    surv += ["execute as @e[tag=cam.surv] run attribute @s minecraft:max_health base set 400",
             "execute as @e[tag=cam.surv] store result entity @s Health float 1 run attribute @s minecraft:max_health get"]
    fn("horde/survivors", surv)
    fn("horde/start", ["function cam:horde/stop", "function cam:brawl/stop",
                       f"forceload add {H_C[0] - 36:.0f} {H_C[2] - 36:.0f} {H_C[0] + 36:.0f} {H_C[2] + 36:.0f}",
                       "scoreboard players set #horde cam 1", "scoreboard players set #ht cam 0",
                       "function cam:horde/survivors", boss, "execute as @e[tag=cam.hnew] run function cam:horde/scale",
                       f"playsound minecraft:event.raid.horn master @a {H_C[0]} {H_C[1] + 5} {H_C[2]} 4 1.2"]
       + ["function cam:horde/one"] * 12)
    near_s = "@e[type=minecraft:zombie,tag=cam.surv,sort=nearest,limit=1]"
    fn("horde/tick", [
        "scoreboard players add #ht cam 1",
        "execute store result score #n cam if entity @e[tag=cam.horde]",
        f"execute if score #n cam matches ..{H_ALIVE - 1} if score #ht cam matches 1 run function cam:horde/one",
        f"execute if score #n cam matches ..{H_ALIVE - 1} if score #ht cam matches 6 run function cam:horde/one",
        f"execute if score #n cam matches ..{H_ALIVE - 1} if score #ht cam matches 11 run function cam:horde/one",
        f"execute if score #n cam matches ..{H_ALIVE - 1} if score #ht cam matches 16 run function cam:horde/one",
        # mobs charge the survivors; survivors fight back
        f"execute if score #ht cam matches 1 as @e[tag=cam.horde,sort=random,limit=10] at @s run damage @s 1 minecraft:mob_attack by {near_s}",
        "execute if score #ht cam matches 11 as @e[type=minecraft:zombie,tag=cam.surv] at @s run damage @s 1 minecraft:mob_attack by @e[tag=cam.horde,sort=nearest,limit=1]",
        # the squad holds the middle; a fallen survivor is "revived"
        f"execute as @e[tag=cam.surv] at @s unless entity @s[x={H_C[0] - 12},y={H_C[1] - 3},z={H_C[2] - 12},dx=24,dy=12,dz=24] run tp @s {H_C[0]} {H_C[1]} {H_C[2]}",
        f"execute store result score #sv cam if entity @e[tag=cam.surv]",
        f"execute if score #ht cam matches 20 if score #sv cam matches ..{len(SURVIVORS) - 1} run function cam:horde/revive",
        f"execute as @e[tag=cam.horde] at @s unless entity @s[x={H_C[0] - 34},y={H_C[1] - 3},z={H_C[2] - 34},dx=68,dy=25,dz=68] run tp @s {H_C[0]} {H_C[1]} {H_C[2] + 20}",
        "execute if score #ht cam matches 20.. run scoreboard players set #ht cam 0",
    ])
    rv = ["execute store result score #r cam run random value 1..%d" % len(SURVIVORS)]
    for i, (key, dx, dz) in enumerate(SURVIVORS, 1):
        rv.append(f"execute if score #r cam matches {i} positioned {H_C[0] + dx} {H_C[1]} {H_C[2] + dz} run function cam:brawl/spawn/{key}")
    rv += ["tag @e[type=minecraft:zombie,tag=cam.brawl,tag=!cam.surv,tag=!cam.horde] add cam.surv",
           "execute as @e[tag=cam.surv] if entity @s[nbt={Health:60f}] run attribute @s minecraft:max_health base set 400",
           "execute as @e[tag=cam.surv] if entity @s[nbt={Health:60f}] store result entity @s Health float 1 run attribute @s minecraft:max_health get",
           f"particle minecraft:totem_of_undying {H_C[0]} {H_C[1] + 1} {H_C[2]} 1 1 1 0.4 60 force"]
    fn("horde/revive", rv)
    fn("horde/stop", ["scoreboard players set #horde cam 0",
                      "execute as @e[tag=cam.horde] at @s run tp @s ~ -1000 ~", "kill @e[tag=cam.horde]",
                      "execute as @e[tag=cam.surv] at @s run tp @s ~ -1000 ~", "kill @e[tag=cam.surv]",
                      f"forceload remove {H_C[0] - 36:.0f} {H_C[2] - 36:.0f} {H_C[0] + 36:.0f} {H_C[2] + 36:.0f}"])
    return ["execute if score #horde cam matches 1 run function cam:horde/tick"]


def horde_orbit(t):
    """High over Hellfort, circling the last stand as the horde pours in from the windows."""
    a = math.radians(lerp(30, 300, t))
    r = lerp(26, 17, ease(t))
    p = (H_C[0] + r * math.cos(a), AY + lerp(16, 9, ease(t)), H_C[2] + r * math.sin(a))
    return p, look(p, (H_C[0], AY + 1.5, H_C[2]))


def horde_dolly(t):
    """In through a mob window at mob height, through the horde to the squad, then a crane up over the fight."""
    if t < 0.6:
        u = ease(t / 0.6)
        p = (H_C[0] + lerp(31, 7, u), AY + 2.2, H_C[2] + 1.5)
        return p, look(p, (H_C[0], AY + 2, H_C[2]))
    u = ease((t - 0.6) / 0.4)
    p = (H_C[0] + lerp(7, 5, u), AY + lerp(2.2, 13, u), H_C[2] + lerp(1.5, 6, u))
    return p, look(p, (H_C[0], AY + 1, H_C[2]))


# ---------------------------------------------------------------- the horse in the doorway (Family Guy)
# A sitcom dining room on empty superflat at 3000, 3000: the family eats while a horse appears in the doorway behind
# Peter and just stands there. Nobody reacts, until Peter slowly turns to look at it. Mannequins sit by riding
# invisible armor stands; rotate (not tp) turns a seated head without dismounting it.
HD = (3000, AY, 3000)                       # floor block level; the room is x -5..5, z -6..2 around it, open to the south
HD_SECS = 10
T_HORSE, T_TURN = 1.6, 7.6


def seat(tag, x, z, yaw, skin):
    X, Y, Z = HD[0] + x, HD[1] + 1.5, HD[2] + z
    return (f"summon minecraft:armor_stand {X} {Y} {Z} {{Tags:[\"cam.actor\"],Invisible:1b,Marker:1b,NoGravity:1b,Invulnerable:1b,"
            f"Rotation:[{yaw}f,0f],Passengers:[{{id:\"minecraft:mannequin\",Tags:[\"cam.actor\",\"{tag}\"],Rotation:[{yaw}f,0f],"
            f"Invulnerable:1b,Silent:1b,immovable:1b,hide_description:1b,"
            f"profile:{{properties:[{{name:\"textures\",value:\"{HEADS[skin]}\"}}]}}}}]}}")


def horse_set():
    X, Y, Z = HD
    r = lambda x1, y1, z1, x2, y2, z2, b: f"fill {X + x1} {Y + y1} {Z + z1} {X + x2} {Y + y2} {Z + z2} {b}"
    return [
        r(-8, 1, -10, 8, 8, 6, "air"),   # (only when the set isn't standing yet: see horse_built)
        r(-6, 0, -7, 6, 0, 3, "cyan_terracotta"), r(-5, 1, -6, 5, 1, 2, "cyan_carpet"),          # floor
        r(-6, 1, -7, 6, 5, -7, "lime_terracotta"), r(-6, 1, -7, -6, 5, 3, "lime_terracotta"),    # back and side walls
        r(6, 1, -7, 6, 5, 3, "lime_terracotta"), r(-6, 6, -7, 6, 6, 3, "white_concrete"),       # wall, ceiling
        r(-6, 1, -7, 6, 1, -7, "stripped_oak_wood"), r(-6, 1, -7, -6, 1, 3, "stripped_oak_wood"),  # skirting
        r(6, 1, -7, 6, 1, 3, "stripped_oak_wood"),
        r(-4, 1, -7, -3, 3, -7, "air"), r(-5, 1, -7, -5, 4, -7, "stripped_oak_wood"),            # the doorway (back left)
        r(-2, 1, -7, -2, 4, -7, "stripped_oak_wood"), r(-4, 4, -7, -3, 4, -7, "stripped_oak_wood"),
        r(-5, 0, -10, -2, 0, -8, "dark_oak_planks"), r(-5, 1, -10, -5, 4, -8, "black_concrete"),  # dark hall behind it
        r(-2, 1, -10, -2, 4, -8, "black_concrete"), r(-5, 5, -10, -2, 5, -8, "black_concrete"), r(-5, 1, -10, -2, 4, -10, "black_concrete"),
        r(-2, 1, -2, 2, 1, -2, "oak_planks"), r(-2, 2, -2, 2, 2, -2, "white_carpet"),            # table + tablecloth
        f"setblock {X - 3} {Y + 1} {Z - 2} oak_stairs[facing=west]", f"setblock {X + 3} {Y + 1} {Z - 2} oak_stairs[facing=east]",
        f"setblock {X - 1} {Y + 1} {Z - 3} oak_stairs[facing=north]", f"setblock {X + 1} {Y + 1} {Z - 3} oak_stairs[facing=north]",
        f"fill {X - 4} {Y + 5} {Z - 5} {X + 4} {Y + 5} {Z + 1} light[level=15]",
        f"setblock {X} {Y + 5} {Z - 2} lantern[hanging=true]",
    ]


def horse_built():
    """The set once (the lantern, placed last, marks it as built), its painting, and no stray items."""
    X, Y, Z = HD
    done = f"execute unless block {X} {Y + 5} {Z - 2} minecraft:lantern run "
    return ([done + c for c in horse_set()] + [
        f"execute positioned {X + 1} {Y + 3} {Z - 6} unless entity @e[type=minecraft:painting,distance=..2] run "
        f"summon minecraft:painting {X + 1} {Y + 3} {Z - 6} {{facing:0,variant:\"minecraft:sunset\"}}",
        f"kill @e[type=minecraft:item,x={X - 12},y={Y - 2},z={Z - 14},dx=24,dy=14,dz=24]"])


def horse_cam(t):
    s = t * HD_SECS
    p = (HD[0] + 0.5, HD[1] + 3.3, HD[2] + lerp(8.5, 7.3, ease(t)))
    return p, look(p, (HD[0] + 0.0, HD[1] + 2.4, HD[2] - 3))


def horse_frame(k, n):
    s = k / TPS; X, Y, Z = HD; out = []
    if k == round(T_HORSE * TPS):   # it's just there
        out.append(f"summon minecraft:horse {X - 2.9} {Y + 1} {Z - 6.7} {{Tags:[\"cam.actor\"],NoAI:1b,Silent:1b,Invulnerable:1b,"
                   "Variant:3,Rotation:[0f,0f],PersistenceRequired:1b,DeathLootTable:\"minecraft:empty\"}")
    if T_TURN <= s <= T_TURN + 1.2:  # Peter slowly turns to look
        u = ease((s - T_TURN) / 1.2)
        out.append(f"rotate @e[type=minecraft:mannequin,tag=cam.peter,limit=1] {lerp(-90, -185, u):.1f} {lerp(0, -6, u):.1f}")
    return out


HORSE_SETUP = horse_built() + [
    seat("cam.peter", -2.5, -1.5, -90, "peter"),     # left end, facing along the table
    seat("cam.homer", -0.5, -2.6, 0, "homer"),       # behind the table, facing the camera
    seat("cam.leela", 1.5, -2.6, 0, "leela"),
    seat("cam.hank", 3.5, -1.5, 90, "hank"),         # right end
]

# ---------------------------------------------------------------- King of the Hill intro, cartoon dads edition
# The alley behind the fence, built once at 3100, 3000: Randy, Hank, Homer and Peter stand in a row with a drink,
# saying nothing, while the alley goes on behind them. Wide shot, Hank's "yep" nod, a push in on Hank, back to the
# wide while Sonic, SpongeBob and Bender pass. The world is frozen at midnight (build.py: time 18000), so the scene
# sets midday and puts midnight back at the end.
KH = (3100, AY, 3000)
KH_SECS = 20
KH_DADS = [("cam.randy", "randy", -3), ("cam.hank", "hank", -1), ("cam.homer", "homer", 1), ("cam.peter", "peter", 3)]
KH_WIDE = (0.5, 2.3, 12.0)                  # camera, relative
BEER = ',equipment:{mainhand:{id:"minecraft:honey_bottle",count:1}}'


def koth_built():
    X, Y, Z = KH
    r = lambda x1, y1, z1, x2, y2, z2, b: f"fill {X + x1} {Y + y1} {Z + z1} {X + x2} {Y + y2} {Z + z2} {b}"
    done = f"execute unless block {X + 13} {Y + 1} {Z - 3} minecraft:cauldron run "
    cmds = [
        r(-18, 1, -14, 18, 12, 14, "air"), r(-18, 0, -14, 18, 0, 14, "grass_block"),
        r(-18, 0, -3, 18, 0, -1, "dirt_path"),                                                    # the alley
        r(-18, 1, -4, 18, 3, -4, "spruce_planks"), r(-18, 4, -4, 18, 4, -4, "spruce_slab"),       # the fence
        *[f"setblock {X + x} {Y + h} {Z - 4} stripped_dark_oak_log" for x in range(-18, 19, 3) for h in (1, 2, 3)],
        r(4, 0, -11, 11, 0, -6, "stone"), r(4, 1, -11, 11, 4, -6, "white_terracotta"),           # garage behind the fence
        r(4, 5, -11, 11, 5, -6, "gray_concrete"), r(6, 1, -6, 9, 3, -6, "light_gray_concrete"),
        f"place feature minecraft:oak {X - 9} {Y + 1} {Z - 7}", f"place feature minecraft:fancy_oak {X - 14} {Y + 1} {Z - 8}",
        f"place feature minecraft:oak {X + 15} {Y + 1} {Z - 8}",
        f"setblock {X + 12} {Y + 1} {Z - 3} cauldron", f"setblock {X + 13} {Y + 1} {Z - 3} cauldron",   # trash cans (last: marks it built)
    ]
    return [done + c for c in cmds] + [f"kill @e[type=minecraft:item,x={X - 20},y={Y - 2},z={Z - 16},dx=40,dy=16,dz=32]"]


def koth_cam(t):
    s = t * KH_SECS
    X, Y, Z = KH
    wide = (X + KH_WIDE[0], Y + KH_WIDE[1], Z + KH_WIDE[2])
    if 5.0 <= s < 8.5:                                       # push in on Hank
        u = ease(min(1, (s - 5.0) / 2.6))
        hx = X - 1 + 0.5
        p = (lerp(wide[0], hx, u), lerp(wide[1], Y + 2.55, u), lerp(wide[2], Z + 3.0, u))
        return p, look(p, (hx, Y + 2.45, Z + 1))
    return wide, look(wide, (X + 0.5, Y + 2.0, Z))


def passer(tag, skin, x0, x1, t0, t1, s, z=-2.0):
    """Walk (or run) a mannequin along the alley from x0 to x1 between t0 and t1."""
    if not (t0 <= s <= t1): return []
    u = (s - t0) / (t1 - t0)
    X, Y, Z = KH
    yaw = -90 if x1 > x0 else 90
    return [f"tp @e[type=minecraft:mannequin,tag={tag},limit=1] {X + lerp(x0, x1, u) + 0.5:.3f} {Y + 1} {Z + z + 0.5:.3f} {yaw} 0"]


def koth_frame(k, n):
    s = k / TPS; out = []
    if k == 0:
        out += ["time set 6000", "weather clear"]
    if 3.4 <= s <= 4.4:                                      # Hank: "yep"
        u = (s - 3.4) / 1.0
        out.append(f"rotate @e[type=minecraft:mannequin,tag=cam.hank,limit=1] 0 {16 * math.sin(math.pi * u):.1f}")
    out += passer("cam.sonic", "sonic", -20, 20, 9.2, 10.4, s)              # Sonic, gone in a second
    out += passer("cam.sponge", "spongebob", 20, -20, 11.0, 16.5, s)        # SpongeBob strolling the other way
    out += passer("cam.bender", "bender", -20, 20, 14.5, 19.0, s, z=-2.8)   # Bender, last
    if k == n - 1:
        out.append("time set 18000")
    return out


KOTH_SETUP = koth_built() + [mannequin(tag, (KH[0] + x + 0.5, KH[1] + 1, KH[2] + 1.5), 0, 0, skin, gear=BEER)
                             for tag, skin, x in KH_DADS] + [
    mannequin("cam.sonic", (KH[0] - 30, KH[1] + 1, KH[2] - 1.5), -90, 0, "sonic"),
    mannequin("cam.sponge", (KH[0] + 30, KH[1] + 1, KH[2] - 1.5), 90, 0, "spongebob"),
    mannequin("cam.bender", (KH[0] - 30, KH[1] + 1, KH[2] - 2.3), -90, 0, "bender"),
]

# name: (path, seconds, forceload area x1 z1 x2 z2[, setup commands, per-frame commands fn(k, n)])
SHOTS = {
    "colosseum_orbit": (colosseum_orbit, 14, (-56, 44, 56, 156)),
    "colosseum_rise": (colosseum_rise, 10, (-56, 44, 56, 156)),
    "orbital_ring": (orbital_ring, 18, (-40, 660, 40, 740)),
    "orbital_spoke": (orbital_spoke, 9, (-40, 660, 40, 740)),
    "lobby_orbit": (lobby_orbit, 12, (-24, -24, 24, 24)),
    "randy_vs_smasher": (sharon_cam, SECS, (-56, 44, 56, 156), SHARON_SETUP, sharon_frame),
    "sharon_closeup": (closeup_cam, CU_SECS, (-56, 44, 56, 156), CLOSEUP_SETUP, closeup_frame),
    "brawl_orbit": (brawl_orbit, 24, (-56, 44, 56, 156)),
    "horde_orbit": (horde_orbit, 22, (-36, 564, 36, 636)),
    "horde_dolly": (horde_dolly, 12, (-36, 564, 36, 636)),
    "horse_dinner": (horse_cam, HD_SECS, (2984, 2984, 3016, 3016), HORSE_SETUP, horse_frame),
    "koth": (koth_cam, KH_SECS, (3064, 2968, 3136, 3032), KOTH_SETUP, koth_frame),
}
RIG = "@e[type=minecraft:armor_stand,tag=cam.rig,limit=1]"


def build(out):
    d = os.path.join(out, "crispy_cam")
    def fn(path, lines):
        p = os.path.join(d, "data", "cam", "function", path + ".mcfunction")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write("\n".join(lines) + "\n")
    os.makedirs(d, exist_ok=True)
    json.dump({"pack": {"description": "Crispy camera rig (camera.py)", "min_format": [107, 0], "max_format": [107, 1]}},
              open(os.path.join(d, "pack.mcmeta"), "w"))
    os.makedirs(os.path.join(d, "data", "minecraft", "tags", "function"), exist_ok=True)
    json.dump({"values": ["cam:tick"]}, open(os.path.join(d, "data", "minecraft", "tags", "function", "tick.json"), "w"))
    json.dump({"values": ["cam:load"]}, open(os.path.join(d, "data", "minecraft", "tags", "function", "load.json"), "w"))
    fn("load", ["scoreboard objectives add cam dummy", "scoreboard players set #shot cam 0",
                "team add cam.actors", "team modify cam.actors nametagVisibility never", "team modify cam.actors collisionRule never"])
    tick = []
    for i, (name, spec) in enumerate(SHOTS.items(), 1):
        path, secs, area = spec[:3]
        setup, per_frame = (spec[3], spec[4]) if len(spec) > 3 else ([], None)
        n = secs * TPS
        frames = [path(k / (n - 1)) for k in range(n)]
        (x, y, z), (yaw, pitch) = frames[0]
        fn(f"start/{name}", [
            "function cam:stop",
            f"forceload add {area[0]} {area[1]} {area[2]} {area[3]}",
            f"tp @a[tag=cam.viewer] {x:.2f} {y:.2f} {z:.2f} {yaw:.1f} {pitch:.1f}",
            "gamemode spectator @a[tag=cam.viewer]",
            f"summon minecraft:armor_stand {x:.2f} {y:.2f} {z:.2f} {{Tags:[\"cam.rig\"],Invisible:1b,Marker:1b,NoGravity:1b,Invulnerable:1b,Rotation:[{yaw:.1f}f,{pitch:.1f}f]}}",
            f"scoreboard players set #f cam {-HOLD}", f"scoreboard players set #shot cam {i}",
            f"scoreboard players set #area cam {i}",
            "scoreboard players set #actors cam 0", "execute as @e[type=!minecraft:player,tag=cam.actor] at @s run tp @s ~ -1000 ~", "kill @e[type=!minecraft:player,tag=cam.actor]",
            # a moment later, once forceload has loaded (or generated) the chunks
            *(["scoreboard players set #wait cam 1", f"schedule function cam:setup/{name} 5t"] if setup else ["scoreboard players set #wait cam 0"]),
        ])
        if setup:
            # build only once every corner of the area is loaded; until then try again, with the shot held still
            corners = [(area[0], area[1]), (area[2], area[1]), (area[0], area[3]), (area[2], area[3]), ((area[0] + area[2]) // 2, (area[1] + area[3]) // 2)]
            guard = "".join(f" if loaded {cx} 0 {cz}" for cx, cz in corners)
            fn(f"setup/{name}", [f"execute unless score #shot cam matches {i} run return 0",
                                 f"execute{guard} run return run function cam:setup/{name}_build",
                                 f"schedule function cam:setup/{name} 5t"])
            fn(f"setup/{name}_build", setup + [
                f"execute unless entity {RIG} run summon minecraft:armor_stand {x:.2f} {y:.2f} {z:.2f} {{Tags:[\"cam.rig\"],Invisible:1b,Marker:1b,NoGravity:1b,Invulnerable:1b,Rotation:[{yaw:.1f}f,{pitch:.1f}f]}}",
                f"tp @a[tag=cam.viewer] {x:.2f} {y:.2f} {z:.2f} {yaw:.1f} {pitch:.1f}",
                "scoreboard players set #wait cam 0"])
        lines = [f"execute if score #wait cam matches 1 as @a[tag=cam.viewer] run spectate {RIG} @s",
                 "execute if score #wait cam matches 1 run return 0",   # staged scene still being built: hold
                 "scoreboard players add #f cam 1",
                 # keep the view locked (a viewer who presses shift would drop out)
                 f"execute as @a[tag=cam.viewer] unless entity @s[gamemode=spectator] run gamemode spectator @s",
                 f"execute if score #f cam matches ..0 as @a[tag=cam.viewer] run spectate {RIG} @s"]
        for k, ((x, y, z), (yaw, pitch)) in enumerate(frames):
            lines.append(f"execute if score #f cam matches {k} run tp {RIG} {x:.3f} {y:.3f} {z:.3f} {yaw:.2f} {pitch:.2f}")
            if per_frame:
                lines += [f"execute if score #f cam matches {k} run {c}" for c in per_frame(k, n)]
        lines.append(f"execute if score #f cam matches {n + 10}.. run function cam:stop")
        fn(f"shot/{name}", lines)
        tick.append(f"execute if score #shot cam matches {i} run function cam:shot/{name}")
    tick += build_brawl(fn)
    tick += build_horde(fn)
    tick += ["execute if score #actors cam matches 1.. run scoreboard players remove #actors cam 1",
             "execute if score #actors cam matches 1 as @e[type=!minecraft:player,tag=cam.actor] at @s run tp @s ~ -1000 ~",
             "execute if score #actors cam matches 1 run kill @e[type=!minecraft:player,tag=cam.actor]"]
    fn("tick", tick)
    stop = ["execute as @a[tag=cam.viewer] run spectate", f"kill @e[type=minecraft:armor_stand,tag=cam.rig]", "scoreboard players set #shot cam 0"]
    # actors stay up for 5 s after a scene (for a second take of the ending), then go
    stop += ["scoreboard players set #actors cam 100"]
    stop += ["execute if score #area cam matches %d run time set 18000" % (list(SHOTS).index("koth") + 1)]
    for i, (name, spec) in enumerate(SHOTS.items(), 1):
        area = spec[2]
        stop.append(f"execute if score #area cam matches {i} run forceload remove {area[0]} {area[1]} {area[2]} {area[3]}")
    stop.append("scoreboard players set #area cam 0")
    fn("stop", stop)
    print("built", d, "shots:", ", ".join(f"{k} ({v[1]} s)" for k, v in SHOTS.items()))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else ".")
