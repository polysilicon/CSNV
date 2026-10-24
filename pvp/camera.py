"""Cinematic camera rig for recording trailers/TikToks on the PvP server: builds the crispy_cam datapack.

A shot puts the viewer (tag cam.viewer) in spectator mode, locks their view to an invisible marker armor stand and
moves that stand along a path every tick. The client interpolates entity movement, so the camera glides at any
recording frame rate. Each shot holds still for 1 s first, so recording can start cleanly.

  python3 camera.py <out dir>      -> <out>/crispy_cam
  tag <player> add cam.viewer, then: function cam:start/<shot>   (function cam:stop to end early)
"""
import json, math, os, sys

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


# "I have to fight him, Sharon": Randy dives upside down at a giant Adam Smasher, then gets swatted away.
SMASH = (0.5, AY + 1, 94.5)                 # Smasher's feet, centre of the colosseum floor, facing south
SMASH_HEAD = (0.5, AY + 1 + 3.3, 94.5)
R_START, R_HIT = (0.5, AY + 22, 116.5), (0.5, AY + 4.6, 96.0)
R_END = (-3.5, AY + 1, 128.5)
DIVE = (0.15, 0.55)                         # share of the scene: hang in the air, dive, then the swat


def randy_pos(t):
    if t < DIVE[0]:                         # hanging at the top, drifting slightly
        return (R_START[0], R_START[1] + 0.6 * t / DIVE[0], R_START[2])
    if t < DIVE[1]:                         # accelerating dive onto Smasher's head
        u = (t - DIVE[0]) / (DIVE[1] - DIVE[0]); u = u * u
        return tuple(lerp(R_START[i] + (0.6 if i == 1 else 0), R_HIT[i], u) for i in range(3))
    u = (t - DIVE[1]) / (1 - DIVE[1])       # swatted: a high arc back across the arena
    v = min(1, u * 1.6)
    return (lerp(R_HIT[0], R_END[0], v), lerp(R_HIT[1], R_END[1], v) + 9 * math.sin(math.pi * v), lerp(R_HIT[2], R_END[2], v))


def sharon_cam(t):
    """Low behind Smasher's right shoulder, looking up at the dive; a slow push in, then it follows Randy out."""
    p = (lerp(4.2, 3.4, ease(min(t / DIVE[1], 1))), AY + 2.4, lerp(88.0, 89.2, ease(min(t / DIVE[1], 1))))
    r = randy_pos(t)
    at = tuple(lerp(SMASH_HEAD[i], r[i], 0.62 if t < DIVE[1] else 0.75) for i in range(3))
    return p, look(p, at)


def sharon_frame(k, n):
    t = k / (n - 1)
    x, y, z = randy_pos(t)
    spin = 0 if t < DIVE[1] else 1080 * min(1, (t - DIVE[1]) / (1 - DIVE[1]) * 1.6)   # tumbling once he's hit
    out = [f"tp @e[type=minecraft:mannequin,tag=cam.randy,limit=1] {x:.3f} {y:.3f} {z:.3f} {(180 + spin) % 360 - 180:.1f} 0",
           f"execute as @e[type=minecraft:mannequin,tag=cam.smasher,limit=1] at @s facing {x:.2f} {y + 1:.2f} {z:.2f} run tp @s ~ ~ ~ ~ ~"]
    hit = round(DIVE[1] * (n - 1))
    if k == hit:
        hx, hy, hz = SMASH_HEAD
        out += [f"particle minecraft:explosion_emitter {hx} {hy} {hz} 0 0 0 0 1 force",
                f"particle minecraft:crit {hx} {hy} {hz} 1 1 1 0.6 80 force",
                f"playsound minecraft:entity.generic.explode master @a {hx} {hy} {hz} 1.2 0.8",
                f"playsound minecraft:block.anvil.land master @a {hx} {hy} {hz} 1 0.6"]
    if k == round(DIVE[0] * (n - 1)):
        out.append(f"playsound minecraft:entity.phantom.swoop master @a {R_START[0]} {R_START[1]} {R_START[2]} 2 0.8")
    if k == n - 1:
        out.append(f"playsound minecraft:entity.player.big_fall master @a {R_END[0]} {R_END[1]} {R_END[2]} 1 1")
    return out


SHARON_SETUP = [
    mannequin("cam.smasher", SMASH, 0, -40, "smasher", scale=1.8,
              gear=',equipment:{head:{id:"minecraft:netherite_helmet",count:1},chest:{id:"minecraft:netherite_chestplate",count:1},'
                   'legs:{id:"minecraft:netherite_leggings",count:1},feet:{id:"minecraft:netherite_boots",count:1},mainhand:{id:"minecraft:netherite_axe",count:1}}'),
    mannequin("cam.randy", R_START, 180, 0, "randy", name="Dinnerbone"),
]

# name: (path, seconds, forceload area x1 z1 x2 z2[, setup commands, per-frame commands fn(k, n)])
SHOTS = {
    "colosseum_orbit": (colosseum_orbit, 14, (-56, 44, 56, 156)),
    "colosseum_rise": (colosseum_rise, 10, (-56, 44, 56, 156)),
    "orbital_ring": (orbital_ring, 18, (-40, 660, 40, 740)),
    "orbital_spoke": (orbital_spoke, 9, (-40, 660, 40, 740)),
    "lobby_orbit": (lobby_orbit, 12, (-24, -24, 24, 24)),
    "randy_vs_smasher": (sharon_cam, 7, (-56, 44, 56, 156), SHARON_SETUP, sharon_frame),
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
    fn("load", ["scoreboard objectives add cam dummy", "scoreboard players set #shot cam 0"])
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
            "scoreboard players set #actors cam 0", "kill @e[type=minecraft:mannequin,tag=cam.actor]",
            *setup,
        ])
        lines = ["scoreboard players add #f cam 1",
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
    tick += ["execute if score #actors cam matches 1.. run scoreboard players remove #actors cam 1",
             "execute if score #actors cam matches 1 run kill @e[type=minecraft:mannequin,tag=cam.actor]"]
    fn("tick", tick)
    stop = ["execute as @a[tag=cam.viewer] run spectate", f"kill @e[type=minecraft:armor_stand,tag=cam.rig]", "scoreboard players set #shot cam 0"]
    # actors stay up for 5 s after a scene (for a second take of the ending), then go
    stop += ["scoreboard players set #actors cam 100"]
    for i, (name, spec) in enumerate(SHOTS.items(), 1):
        area = spec[2]
        stop.append(f"execute if score #area cam matches {i} run forceload remove {area[0]} {area[1]} {area[2]} {area[3]}")
    stop.append("scoreboard players set #area cam 0")
    fn("stop", stop)
    print("built", d, "shots:", ", ".join(f"{k} ({v[1]} s)" for k, v in SHOTS.items()))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else ".")
