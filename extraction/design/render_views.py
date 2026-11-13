#!/usr/bin/env python3
"""Chunky renders of the Extraction camp and a bunker from the live server save, at fixed viewpoints.

Run on the host (after `save-all flush` on Extraction01):  python3 render_views.py <label> [spp]
It copies the camp dimension out of the live save, writes one Chunky scene per viewpoint and renders them, leaving
/root/chunky/out/<label>/<view>.png. The same viewpoints are used before and after a rebuild, so the pairs line up.

Camera conventions (checked with test renders, Chunky 2.4.6): yaw is atan2(dz, -dx) of the view direction (yaw 0 faces -x); pitch is
-pi/2 for a level view, 0 straight down, -pi straight up. Eye height is feet + 1.62.
"""
import json, math, os, shutil, subprocess, sys, time

LIVE = "/AMPStorage/.ampdata/instances/Extraction01/Minecraft/world"
WORLD = "/root/chunky/worlds/camp"
EYE = 1.62
CAMP = [(x, z) for x in range(-3, 3) for z in range(-3, 3)]
BUNKER = [(x, z) for x in range(4, 7) for z in range(-12, -10)]   # bunker 0 (x 80-95, z -185..-161)

# name: (camera position, look-at point, chunks, fov)
VIEWS = {
    "aerial":         ((-26, 100, 38), (0.5, 62, -1), CAMP, 55),
    "topdown":        ((0.5, 112, 0.5), None, CAMP, 42),
    "spawn":          ((0.5, 64 + EYE, 6.5), (0.5, 65, -6), CAMP, 75),
    "quartermaster":  ((-9.0, 64 + EYE, -6.5), (-12.5, 65.2, -6.5), CAMP, 75),
    "builder":        ((-9.0, 64 + EYE, 6.5), (-12.5, 65.2, 6.5), CAMP, 75),
    "broker":         ((10.0, 64 + EYE, -6.5), (13.5, 65.2, -6.5), CAMP, 75),
    "bunker_manager": ((10.0, 64 + EYE, 5.5), (13.5, 65.2, 5.5), CAMP, 75),
    "fixer":          ((0.5, 64 + EYE, -9.0), (0.5, 65.2, -12.5), CAMP, 75),
    "helipad":        ((0.5, 64 + EYE, 2.0), (0.0, 63.5, 12.0), CAMP, 75),
    "blockhouse":     ((12.5, 64 + EYE, 8.0), (12.0, 64.0, 16.0), CAMP, 75),
    "bunker_arrival": ((88.5, 21 + EYE, -162.5), (88.5, 22.0, -176.0), BUNKER, 80),
    "stairwell":      ((88.5, 21 + EYE, -177.5), (88.5, 28.5, -184.0), BUNKER, 80),
}


def orient(pos, at):
    if at is None: return 0.0, -math.pi / 2   # straight down, north at the top
    dx, dy, dz = at[0] - pos[0], at[1] - pos[1], at[2] - pos[2]
    yaw = math.atan2(dz, -dx)
    elev = math.atan2(dy, math.hypot(dx, dz))
    return -math.pi / 2 - elev, yaw


def scene(name, pos, at, chunks, fov, spp, w=1280, h=720):
    pitch, yaw = orient(pos, at)
    d = os.path.expanduser(f"~/.chunky/scenes/{name}")
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    sc = {"sdfVersion": 9, "name": name, "width": w, "height": h, "exposure": 1.0, "postprocess": "GAMMA", "sppTarget": spp, "rayDepth": 5,
          "world": {"path": WORLD, "dimension": 0},
          "camera": {"name": "camera 1", "position": {"x": pos[0], "y": pos[1], "z": pos[2]},
                     "orientation": {"roll": 0.0, "pitch": pitch, "yaw": yaw},
                     "projectionMode": "PINHOLE", "fov": fov, "dof": "Infinity", "focalOffset": 2.0},
          "sun": {"altitude": math.radians(50), "azimuth": math.radians(220), "intensity": 1.25,
                  "color": {"red": 1, "green": 1, "blue": 1}, "drawTexture": True},
          "emittersEnabled": True, "emitterIntensity": 13.0,
          "chunkList": [[x, z] for x, z in chunks]}
    with open(f"{d}/{name}.json", "w") as f: json.dump(sc, f)


def main():
    label = sys.argv[1]
    spp = int(sys.argv[2]) if len(sys.argv) > 2 else 64
    only = sys.argv[3].split(",") if len(sys.argv) > 3 else list(VIEWS)
    shutil.rmtree(WORLD, ignore_errors=True); os.makedirs(WORLD)
    shutil.copy2(f"{LIVE}/level.dat", WORLD)
    shutil.copytree(f"{LIVE}/dimensions/ez/camp/region", f"{WORLD}/region")
    out = f"/root/chunky/out/{label}"; os.makedirs(out, exist_ok=True)
    for name in only:
        pos, at, chunks, fov = VIEWS[name]
        sname = f"{label}_{name}"
        scene(sname, pos, at, chunks, fov, spp)
        t = time.time()
        subprocess.run(["java", "-Xmx2G", "-jar", "/root/chunky/ChunkyLauncher.jar", "-render", sname, "-reload-chunks", "-threads", "3", "-f"],
                       cwd="/root/chunky", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800)
        png = os.path.expanduser(f"~/.chunky/scenes/{sname}/snapshots/{sname}-{spp}.png")
        if os.path.exists(png): shutil.copy2(png, f"{out}/{name}.png")
        print(f"{name}: {'ok' if os.path.exists(png) else 'MISSING'} {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
