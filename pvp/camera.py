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


# name: (path, seconds, forceload area x1 z1 x2 z2)
SHOTS = {
    "colosseum_orbit": (colosseum_orbit, 14, (-56, 44, 56, 156)),
    "colosseum_rise": (colosseum_rise, 10, (-56, 44, 56, 156)),
    "orbital_ring": (orbital_ring, 18, (-40, 660, 40, 740)),
    "orbital_spoke": (orbital_spoke, 9, (-40, 660, 40, 740)),
    "lobby_orbit": (lobby_orbit, 12, (-24, -24, 24, 24)),
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
    for i, (name, (path, secs, area)) in enumerate(SHOTS.items(), 1):
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
        ])
        lines = ["scoreboard players add #f cam 1",
                 # keep the view locked (a viewer who presses shift would drop out)
                 f"execute as @a[tag=cam.viewer] unless entity @s[gamemode=spectator] run gamemode spectator @s",
                 f"execute if score #f cam matches ..0 as @a[tag=cam.viewer] run spectate {RIG} @s"]
        for k, ((x, y, z), (yaw, pitch)) in enumerate(frames):
            lines.append(f"execute if score #f cam matches {k} run tp {RIG} {x:.3f} {y:.3f} {z:.3f} {yaw:.2f} {pitch:.2f}")
        lines.append(f"execute if score #f cam matches {n + 10}.. run function cam:stop")
        fn(f"shot/{name}", lines)
        tick.append(f"execute if score #shot cam matches {i} run function cam:shot/{name}")
    fn("tick", tick)
    stop = ["execute as @a[tag=cam.viewer] run spectate", f"kill @e[type=minecraft:armor_stand,tag=cam.rig]", "scoreboard players set #shot cam 0"]
    for i, (name, (_, _, area)) in enumerate(SHOTS.items(), 1):
        stop.append(f"execute if score #area cam matches {i} run forceload remove {area[0]} {area[1]} {area[2]} {area[3]}")
    stop.append("scoreboard players set #area cam 0")
    fn("stop", stop)
    print("built", d, "shots:", ", ".join(f"{k} ({v[1]} s)" for k, v in SHOTS.items()))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else ".")
