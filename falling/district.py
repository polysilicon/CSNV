"""The Market District (imported by skyblock.py): a floating island south of the hub, joined to it by a bridge, with 16
plots players can buy for shops and houses. This file builds it (function district/build) and puts the plot layout
into storage crispy_skyblock:eco cfg.hubplots, which the mod (HubPlots.java) reads: buying, the /plots menu, who may
build where, and the plot labels.

Plots are 16x16 with a build height from 4 below the floor to 32 above. The owner, players they trust and their
island co-op can build there (the mod switches them to survival inside it); everywhere else in the district is
adventure mode like the hub.
"""

Y = 100
X0, X1, Z0, Z1 = -45, 45, 50, 146          # the island's top surface
PLOT = 16
COLS = [(-39, -24), (-20, -5), (5, 20), (24, 39)]
ROWS = [(62, 77), (82, 97), (102, 117), (122, 137)]
DOWN, UP = 4, 32                           # build height below / above the floor
PRICE, REFUND = 20_000, 50                 # coins; % back when abandoning
BOX = (-47, Y - 45, 47, 94, 90, 102)       # the district's selector box (x, y, z, dx, dy, dz), bridge included
PLAZA = (0.5, Y + 1, 55.5, 0)              # where /warp plots lands, facing south down the avenue


def plots():
    out = []
    for r, (z1, z2) in enumerate(ROWS):
        for c, (x1, x2) in enumerate(COLS):
            n = r * len(COLS) + c + 1
            sx, sz = (x1 + x2) // 2, z1 - 1     # the sign: in the street in front of the plot's north edge
            out.append({"n": n, "x1": x1, "z1": z1, "x2": x2, "z2": z2, "y1": Y - DOWN, "y2": Y + UP, "sx": sx, "sy": Y + 1, "sz": sz})
    return out


def sel(box=BOX):
    x, y, z, dx, dy, dz = box
    return f"x={x},y={y},z={z},dx={dx},dy={dy},dz={dz}"


def build(NS, fn, txt, snbt, label, hsign):
    ps = plots()
    c = [f"forceload add {X0 - 2} {Z0 - 4} {X1 + 2} {Z1 + 2}",
         f"kill @e[type=minecraft:text_display,tag=cs_district,{sel()}]"]
    # clear the space, then the island: grass on dirt, and a rocky underside that narrows as it goes down
    c += [f"fill {X0 - 1} {y} {Z0} {X1 + 1} {y} {Z1 + 1} minecraft:air" for y in range(Y - 30, Y + UP + 2)]
    c += [f"fill {X0} {Y} {Z0} {X1} {Y} {Z1} minecraft:grass_block",
          f"fill {X0} {Y - 3} {Z0} {X1} {Y - 1} {Z1} minecraft:dirt"]
    for d in range(4, 29):
        k = int((d - 3) * 1.55)
        if X0 + k >= X1 - k or Z0 + k >= Z1 - k: break
        block = ["stone", "stone", "andesite", "stone", "tuff", "stone", "cobblestone"][d % 7]
        c.append(f"fill {X0 + k} {Y - d} {Z0 + k} {X1 - k} {Y - d} {Z1 - k} minecraft:{block}")
    for cx, cz in ((X0, Z0), (X1, Z0), (X0, Z1), (X1, Z1)):        # round the corners off
        sx, sz = (1 if cx == X0 else -1), (1 if cz == Z0 else -1)
        for i in range(3):
            for j in range(3 - i):
                c.append(f"fill {cx + sx * i} {Y - 3} {cz + sz * j} {cx + sx * i} {Y} {cz + sz * j} minecraft:air")
    # streets: stone bricks everywhere but the plots, a polished avenue down the middle, a hedge round the edge
    c += [f"fill {X0 + 2} {Y} {Z0 + 2} {X1 - 2} {Y} {Z1 - 3} minecraft:stone_bricks",
          f"fill -4 {Y} {Z0} 4 {Y} {Z1 - 3} minecraft:polished_andesite",
          f"fill 0 {Y} {Z0} 0 {Y} {Z1 - 3} minecraft:smooth_stone"]
    c += [f"fill {X0} {Y + 1} {Z0 + 3} {X0} {Y + 1} {Z1 - 3} minecraft:oak_leaves[persistent=true]",
          f"fill {X1} {Y + 1} {Z0 + 3} {X1} {Y + 1} {Z1 - 3} minecraft:oak_leaves[persistent=true]",
          f"fill {X0 + 3} {Y + 1} {Z1} {X1 - 3} {Y + 1} {Z1} minecraft:oak_leaves[persistent=true]",
          f"fill {X0 + 3} {Y + 1} {Z0} -6 {Y + 1} {Z0} minecraft:oak_leaves[persistent=true]",
          f"fill 6 {Y + 1} {Z0} {X1 - 3} {Y + 1} {Z0} minecraft:oak_leaves[persistent=true]"]
    # lamp posts down both sides of the avenue, and planters in its middle
    for z in range(Z0 + 6, Z1 - 4, 10):
        for x in (-4, 4):
            c += [f"fill {x} {Y + 1} {z} {x} {Y + 3} {z} minecraft:stone_brick_wall", f"setblock {x} {Y + 4} {z} minecraft:lantern"]
        if z > Z0 + 10:
            c += [f"fill -1 {Y} {z + 4} 1 {Y} {z + 6} minecraft:moss_block", f"setblock 0 {Y + 1} {z + 5} minecraft:flowering_azalea",
                  f"setblock -1 {Y + 1} {z + 4} minecraft:cornflower", f"setblock 1 {Y + 1} {z + 6} minecraft:poppy"]
    # the plots: grass, a corner post with a lantern at each corner, and a sign with a label in front
    for p in ps:
        x1, z1, x2, z2 = p["x1"], p["z1"], p["x2"], p["z2"]
        c += [f"fill {x1} {Y} {z1} {x2} {Y} {z2} minecraft:grass_block",
              f"fill {x1} {Y - DOWN} {z1} {x2} {Y - 1} {z2} minecraft:dirt"]
        for cx, cz in ((x1 - 1, z1 - 1), (x2 + 1, z1 - 1), (x1 - 1, z2 + 1), (x2 + 1, z2 + 1)):
            c += [f"setblock {cx} {Y + 1} {cz} minecraft:spruce_fence", f"setblock {cx} {Y + 2} {cz} minecraft:lantern"]
        c.append(f"setblock {p['sx']} {Y + 1} {p['sz']} minecraft:oak_sign[rotation=8]"
                 + hsign(["", f"Plot {p['n']}", "Right-click", ""], "black"))
        c.append(label(p["sx"] + 0.5, Y + 2.6, p["sz"] + 0.5, snbt({"text": f"Plot {p['n']}", "color": "green", "bold": True,
                       "extra": [txt(f"\nFor sale · {PRICE:,} coins", "gray", bold=False)]}), 0.8, bill="center", tag=f"cs_hpl_{p['n']}")
                 .replace(f'"{NS}"', f'"{NS}","cs_district"', 1))
    # the district's name over the plaza (the bridge from the hub is built by the hub, skyblock.py hub_build)
    c.append(label(0.5, Y + 6, Z0 + 4.5, snbt({"text": "Market District", "color": "gold", "bold": True,
                   "extra": [txt(f"\nBuy a plot for your shop or house · {PRICE:,} coins · /plots", "yellow", bold=False)]}), 1.6, bill="center")
             .replace(f'"{NS}"', f'"{NS}","cs_district"', 1))
    c += ["scoreboard players set #districtv cs_cfg 2"]
    fn("district/build", "\n".join(c))
    fn("district/reset", "\n".join([
        f"$fill $(x1) {Y + 1} $(z1) $(x2) {Y + UP} $(z2) minecraft:air",
        f"$fill $(x1) {Y - DOWN} $(z1) $(x2) {Y - 1} $(z2) minecraft:dirt",
        f"$fill $(x1) {Y} $(z1) $(x2) {Y} $(z2) minecraft:grass_block",
        f"$kill @e[type=!minecraft:player,type=!minecraft:text_display,x=$(x1),y={Y - DOWN},z=$(z1),dx={PLOT - 1},dy={DOWN + UP},dz={PLOT - 1}]"]))
    fn("district/tp", f"$execute in minecraft:overworld run tp @s $(x) $(y) $(z) $(yaw) 0")
    npc = (f"summon minecraft:villager 0.5 {Y + 1} {Z0 + 7.5} " + snbt({
        "NoAI": True, "Invulnerable": True, "Silent": True, "PersistenceRequired": True, "Tags": [NS, "cs_npc", "cs_realtor"],
        "VillagerData": {"profession": "minecraft:cartographer", "level": 5, "type": "minecraft:plains"}, "Offers": {"Recipes": []}})[:-1]
        + ",Rotation:[180f,0f]}")
    npc_label = label(0.5, Y + 3.15, Z0 + 7.5, snbt({"text": "Realtor", "color": "gold", "bold": True,
                      "extra": [txt("\nbuy and manage plots · click", "gray", bold=False)]}), 0.7, bill="center", tag="cs_npcl")
    return [npc, npc_label]


def cfg():
    """Settings the mod reads (storage crispy_skyblock:eco cfg)."""
    return {"hubplots": plots(), "hubplot_price": PRICE, "hubplot_refund": REFUND,
            "district": [BOX[0], BOX[1], BOX[2], BOX[0] + BOX[3], BOX[1] + BOX[4], BOX[2] + BOX[5]], "district_warp": list(PLAZA)}
