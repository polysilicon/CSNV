"""Hub plots (imported by skyblock.py): 16 plots players can buy for shops and houses, spread in a ring through the
outer hills of the hub island. skyblock.py's hub_build levels a pad for each (flat() below), joins them with a ring
path, and places what features() returns; the plot layout goes into storage crispy_skyblock:eco cfg.hubplots, which
the mod (HubPlots.java) reads: buying, the /plots menu, who may build where, and the plot labels.

Plots are 16x16 with a build height from 4 below the floor to 32 above. The owner, players they trust and their
island co-op can build there (the mod switches them to survival inside it); the rest of the hub is adventure mode.
"""
import math

Y = 100
HUB_R = 104                 # the hub's area (adventure mode, no island bounds): |x|, |z| <= HUB_R
ISLAND = 92                 # the island's edge is about this far out (+ up to 8 of noise)
RING = 74                   # plot centres sit on this circle
ROAD = 56                   # the ring path that links them
N, PLOT = 16, 16
DOWN, UP = 4, 32            # build height below / above the floor
PRICE, REFUND = 20_000, 50  # coins; % back when abandoning
REALTOR = (-6, 9)           # the Realtor NPC, just south-west of the plaza
WARP = (-5.5, Y + 1, 7.5, 0)


def plots():
    out = []
    for i in range(N):
        a = 2 * math.pi * (i + 0.5) / N - math.pi / 2          # plot 1 just east of north, then clockwise
        cx, cz = round(RING * math.cos(a)), round(RING * math.sin(a))
        x1, z1 = cx - PLOT // 2, cz - PLOT // 2
        x2, z2 = x1 + PLOT - 1, z1 + PLOT - 1
        mx, mz = (x1 + x2) // 2, (z1 + z2) // 2
        # the front faces the plaza: the sign stands just outside it, you arrive 2 blocks further out facing the plot
        if abs(cx) > abs(cz):
            if cx > 0: sx, sz, rot, tx, tz, yaw = x1 - 1, mz, 4, x1 - 2.5, mz + 0.5, -90
            else:      sx, sz, rot, tx, tz, yaw = x2 + 1, mz, 12, x2 + 3.5, mz + 0.5, 90
        else:
            if cz > 0: sx, sz, rot, tx, tz, yaw = mx, z1 - 1, 8, mx + 0.5, z1 - 2.5, 0
            else:      sx, sz, rot, tx, tz, yaw = mx, z2 + 1, 0, mx + 0.5, z2 + 3.5, 180
        out.append({"n": i + 1, "x1": x1, "z1": z1, "x2": x2, "z2": z2, "y1": Y - DOWN, "y2": Y + UP,
                    "sx": sx, "sy": Y + 1, "sz": sz, "rot": rot, "tx": tx, "ty": Y + 1, "tz": tz, "tyaw": yaw})
    for p in out:      # no two plots closer than 6 blocks
        for q in out:
            if p is not q:
                gap = max(q["x1"] - p["x2"], p["x1"] - q["x2"], q["z1"] - p["z2"], p["z1"] - q["z2"])
                assert gap >= 6, (p["n"], q["n"], gap)
    return out


PLOTS = plots()


def flat(x, z):
    """How much of the hills to keep at (x, z): 0 on and next to a plot (a level pad), easing back up over 6 blocks."""
    d = min(max(p["x1"] - x, x - p["x2"], p["z1"] - z, z - p["z2"]) for p in PLOTS)
    return max(0.0, min(1.0, (d - 2) / 6))


def in_plot(x, z, margin=0):
    return any(p["x1"] - margin <= x <= p["x2"] + margin and p["z1"] - margin <= z <= p["z2"] + margin for p in PLOTS)


def features(txt, snbt, label, hsign):
    """Each plot: grass on dirt, a lantern post at each corner, a sign facing the plaza with a label over it."""
    c = []
    for p in PLOTS:
        x1, z1, x2, z2 = p["x1"], p["z1"], p["x2"], p["z2"]
        c += [f"fill {x1} {Y - DOWN} {z1} {x2} {Y - 1} {z2} minecraft:dirt",
              f"fill {x1} {Y} {z1} {x2} {Y} {z2} minecraft:grass_block",
              f"fill {x1} {Y + 1} {z1} {x2} {Y + 12} {z2} minecraft:air"]
        for cx, cz in ((x1 - 1, z1 - 1), (x2 + 1, z1 - 1), (x1 - 1, z2 + 1), (x2 + 1, z2 + 1)):
            c += [f"setblock {cx} {Y} {cz} minecraft:stone_bricks", f"setblock {cx} {Y + 1} {cz} minecraft:spruce_fence",
                  f"setblock {cx} {Y + 2} {cz} minecraft:lantern"]
        c += [f"setblock {p['sx']} {Y} {p['sz']} minecraft:stone_bricks",
              f"setblock {p['sx']} {Y + 1} {p['sz']} minecraft:oak_sign[rotation={p['rot']}]" + hsign(["", f"Plot {p['n']}", "Right-click", ""], "black"),
              label(p["sx"] + 0.5, Y + 2.6, p["sz"] + 0.5, snbt({"text": f"Plot {p['n']}", "color": "green", "bold": True,
                    "extra": [txt(f"\nFor sale · {PRICE:,} coins", "gray", bold=False)]}), 0.8, bill="center", tag=f"cs_hpl_{p['n']}")]
    return c


def build(NS, fn, txt, snbt, label):
    """The reset and teleport functions, and the Realtor NPC (its lines go into the npcs function)."""
    fn("district/reset", "\n".join([
        f"$fill $(x1) {Y + 1} $(z1) $(x2) {Y + UP} $(z2) minecraft:air",
        f"$fill $(x1) {Y - DOWN} $(z1) $(x2) {Y - 1} $(z2) minecraft:dirt",
        f"$fill $(x1) {Y} $(z1) $(x2) {Y} $(z2) minecraft:grass_block",
        f"$kill @e[type=!minecraft:player,type=!minecraft:text_display,x=$(x1),y={Y - DOWN},z=$(z1),dx={PLOT - 1},dy={DOWN + UP},dz={PLOT - 1}]"]))
    fn("district/tp", "$execute in minecraft:overworld run tp @s $(x) $(y) $(z) $(yaw) 0")
    rx, rz = REALTOR
    npc = (f"summon minecraft:villager {rx + 0.5} {Y + 1} {rz + 0.5} " + snbt({
        "NoAI": True, "Invulnerable": True, "Silent": True, "PersistenceRequired": True, "Tags": [NS, "cs_npc", "cs_realtor"],
        "VillagerData": {"profession": "minecraft:cartographer", "level": 5, "type": "minecraft:plains"}, "Offers": {"Recipes": []}})[:-1]
        + ",Rotation:[180f,0f]}")
    npc_label = label(rx + 0.5, Y + 3.15, rz + 0.5, snbt({"text": "Realtor", "color": "gold", "bold": True,
                      "extra": [txt("\nplots for shops and houses · click", "gray", bold=False)]}), 0.7, bill="center", tag="cs_npcl")
    return [npc, npc_label]


def cfg():
    """Settings the mod reads (storage crispy_skyblock:eco cfg)."""
    return {"hubplots": PLOTS, "hubplot_price": PRICE, "hubplot_refund": REFUND,
            "district": [-HUB_R, Y - 45, -HUB_R, HUB_R, Y + 45, HUB_R], "district_warp": list(WARP)}
