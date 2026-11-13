"""The Extraction camp, laid out as a designed space (1.6.0).

One geometry, two modes:
  grey   - big shapes and structure in plain blocks (no props): the grey-box the flow checks run against first
  detail - the same geometry in the measured palette (design/palette.json), plus the props layer

Every block carries (family, role, layer). family/role come from the palette (main / secondary / accent, aimed at
60 / 30 / 10); layer is shape (big shapes), structure (frames, openings, roofs, lights) or props. The plan the
self-test checks (paths, doorways, destinations) is written out as layout.json from the same numbers.

Plan (camp floor y 63, feet at y 64; interior -17..17):
  spawn (0.5, 6.5) on the spine, facing north: the plaza, the flag and the Fixer's booth closing the view
  spine      x -1..1,  z -10..8   Fixer booth  <->  helipad
  cross road z -1..1,  x -9..9
  streets    x -9..-7 and 7..9, z -8..8 (east: to z 11): every post's open side faces a street
  spur       z 9..11,  x 7..13   east street -> blockhouse (bunker entrance, 3 wide x 3 high)
  posts      Quartermaster / Builder west, Broker / Bunker Manager east, Fixer north; NPCs 3-4 blocks from a path
  landmarks  Fixer booth (end of the spine), flag (NE of the plaza), radio mast (SW), helipad (south),
             blockhouse with a green blast-door frame (SE)
"""
import json, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
PAL = json.load(open(os.path.join(HERE, "design", "palette.json")))
VALID = {"minecraft:" + l.strip() for l in open(os.path.join(HERE, "design", "blocks262.txt")) if l.strip()} | {
    "minecraft:air", "minecraft:barrier", "minecraft:bedrock", "minecraft:reinforced_deepslate"}

HELI = (0, 12)
R = 18
PATHS = [("spine", -1, -10, 1, 8), ("cross road", -9, -1, 9, 1), ("west street", -9, -8, -7, 8),
         ("east street", 7, -8, 9, 11), ("blockhouse spur", 7, 9, 13, 11), ("plaza", -3, -3, 3, 3)]
# name, feet cells across the opening, needed width, needed height (3 for main entries, 2 for doors)
DOORWAYS = [("blockhouse entrance (main)", [(x, 64, 12) for x in (11, 12, 13)], 3, 3),
            ("Quartermaster container", [(-10, 64, z) for z in range(-8, -4)], 3, 3),
            ("Broker container", [(10, 64, z) for z in range(-8, -4)], 3, 3),
            ("Builder tent", [(-10, 64, z) for z in (5, 6, 7)], 3, 3),
            ("Bunker Manager tent", [(10, 64, z) for z in (4, 5, 6)], 3, 3),
            ("Fixer booth", [(x, 64, -11) for x in range(-2, 3)], 3, 3),
            ("bunker door (bottom of the steps)", [(12, 62, 15)], 1, 2)]
LIGHTS_GREY = "minecraft:sea_lantern"
GREY = {"ground": "minecraft:gray_concrete", "path": "minecraft:white_concrete", "earthworks": "minecraft:light_gray_concrete",
        "timber": "minecraft:light_gray_concrete", "steel": "minecraft:light_gray_concrete", "canvas": "minecraft:light_gray_concrete",
        "concrete": "minecraft:light_gray_concrete", "light": LIGHTS_GREY}
SHAPED = ("_slab", "_stairs", "_wall", "_fence", "door", "trapdoor", "ladder", "iron_bars", "chain", "lantern", "lightning_rod", "campfire")


def on_path(x, z):
    return any(x0 <= x <= x1 and z0 <= z <= z1 for _, x0, z0, x1, z1 in PATHS)


class Camp:
    def __init__(self, mode):
        self.mode = mode
        self.B = {}   # (x, y, z) -> (block, family, role, layer)
        self.rnd = random.Random(11)

    def p(self, fam, role="main", k=0):
        opts = PAL[fam][role]
        return "minecraft:" + opts[k % len(opts)]

    def put(self, x, y, z, fam, role="main", layer="shape", blk=None, k=0):
        blk = blk or self.p(fam, role, k)
        if self.mode == "grey":
            if layer == "props": return
            base = blk.split("[")[0]
            if fam != "air" and not any(s in base for s in SHAPED) and base not in ("minecraft:barrier", "minecraft:bedrock", "minecraft:air"):
                blk = GREY.get(fam, "minecraft:light_gray_concrete")
        self.B[(x, y, z)] = (blk, fam, role, layer)

    def air(self, x, y, z, layer="structure"):
        self.B[(x, y, z)] = ("minecraft:air", "air", "-", layer)

    def fill(self, x0, y0, z0, x1, y1, z1, *a, **kw):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    if a and a[0] == "air": self.air(x, y, z, kw.get("layer", "structure"))
                    else: self.put(x, y, z, *a, **kw)

    # ------------------------------------------------------------ layer 1: big shapes
    def ground(self):
        r = self.rnd
        for x in range(-R, R + 1):
            for z in range(-R, R + 1):
                self.put(x, 59, z, "ground", blk="minecraft:bedrock")
                for y in (60, 61, 62): self.put(x, y, z, "ground", "secondary", blk="minecraft:dirt")
                if on_path(x, z):
                    edge = (x, z) not in [(xx, zz) for _, x0, z0, x1, z1 in PATHS for xx in range(x0 + 1, x1) for zz in range(z0 + 1, z1)]
                    if edge and r.random() < 0.3: self.put(x, 63, z, "path", "secondary", blk=self.p("ground", "secondary", 1))   # andesite kerb
                    else: self.put(x, 63, z, "path", "main", blk=self.p("ground", "main", 0))                                        # gravel
                else:
                    v = r.random()
                    if v < 0.62: self.put(x, 63, z, "ground", "main", k=1)          # coarse dirt
                    elif v < 0.85: self.put(x, 63, z, "ground", "secondary", k=0)   # packed mud
                    else: self.put(x, 63, z, "ground", "secondary", k=2)            # dirt

    def perimeter(self):
        r = self.rnd
        for k in range(-R, R + 1):   # outer HESCO, 4 high: one unit (column) is one block kind
            for (x, z) in [(k, -R), (k, R), (-R, k), (R, k)]:
                v = r.random(); role, kk = ("main", r.randrange(2)) if v < 0.8 else ("secondary", r.randrange(2))
                for y in (64, 65, 66, 67): self.put(x, y, z, "earthworks", role, k=kk)
                if (x + z) % 2 == 0: self.put(x, 68, z, "earthworks", "accent", "structure", blk="minecraft:iron_bars")
                if (x + z) % 3 == 0: self.put(x, 69, z, "earthworks", "accent", "structure", blk="minecraft:iron_chain[axis=x]" if z in (-R, R) else "minecraft:iron_chain[axis=z]")
                for y in range(70, 74): self.put(x, y, z, "air", blk="minecraft:barrier", layer="structure")
        for k in range(-R + 1, R):   # inner step row, 2 high with a sandbag cap
            for (x, z) in [(k, -R + 1), (k, R - 1), (-R + 1, k), (R - 1, k)]:
                v = r.random(); role, kk = ("main", r.randrange(2)) if v < 0.66 else ("secondary", r.randrange(2))
                self.put(x, 64, z, "earthworks", role, k=kk); self.put(x, 65, z, "earthworks", role, k=kk)
                self.put(x, 66, z, "earthworks", "secondary", "structure", blk="minecraft:mud_brick_slab[type=bottom]")
        # the closed vehicle gate (east): steel frame, barred
        for z in range(-2, 3):
            for x in (R, R - 1):
                for y in range(64, 69): self.air(x, y, z)
            for y in (64, 65, 66): self.put(R, y, z, "steel", "accent", "structure", blk="minecraft:iron_bars")
            self.put(R - 1, 63, z, "path", "main", blk=self.p("ground", "main", 0))
        for z in (-3, 3):
            for y in range(64, 70): self.put(R, y, z, "steel", "secondary", k=1); self.put(R - 1, y, z, "steel", "secondary", k=1)
        for z in range(-3, 4): self.put(R, 69, z, "steel", "secondary", k=1); self.put(R - 1, 69, z, "steel", "secondary", k=1)

    def container(self, x0, z0, x1, z1, open_x, band):
        d = 1 if open_x == x1 else -1
        back = x0 if open_x == x1 else x1
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                self.put(x, 63, z, "timber", "main", k=1)   # ply floor
                edge = x in (x0, x1) or z in (z0, z1)
                for y in (64, 65, 66, 67):
                    if edge and x != open_x: self.put(x, y, z, "steel", "main")
                    else: self.air(x, y, z, "shape")
                self.put(x, 68, z, "steel", "main", "structure")
        for z in (z0, z1):                                     # corner castings
            for y in range(64, 69): self.put(open_x, y, z, "steel", "secondary", "structure", k=1); self.put(back, y, z, "steel", "secondary", "structure", k=1)
        for x in range(x0, x1 + 1):                            # top rail
            self.put(x, 68, z0, "steel", "main", "structure"); self.put(x, 68, z1, "steel", "main", "structure")
        if band:                                               # stencil band
            for x in range(x0 + 1, x1):
                if x != open_x: self.put(x, 66, z0, "steel", "accent", "structure", k=1); self.put(x, 66, z1, "steel", "accent", "structure", k=1)
        for z in range(z0 + 1, z1): self.put(back, 66, z, "steel", "accent", "structure", blk="minecraft:iron_bars")   # vent slit
        for z in range(z0, z1 + 1): self.put(open_x + d, 68, z, "timber", "secondary", "structure", blk="minecraft:dark_oak_slab[type=top]")   # awning
        for z in (z0, z1): self.put(open_x + d, 67, z, "timber", "secondary", "structure", blk="minecraft:dark_oak_fence")

    def tent(self, x0, z0, x1, z1, open_x):
        mid = (z0 + z1) / 2; half = (z1 - z0) / 2
        back = x0 if open_x == x1 else x1
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                self.put(x, 63, z, "timber", "main", k=1)
                h = 64 + round(3 * (1 - abs(z - mid) / half)) + 1
                for y in range(64, h): self.air(x, y, z, "shape")
                self.put(x, h, z, "canvas", "main" if (x * 2 + z) % 3 else "secondary", k=x % 2)
                if x == back:
                    for y in range(64, h): self.put(x, y, z, "canvas", "main")
                elif x == open_x and abs(z - mid) >= half - 0.5:
                    self.put(x, 64, z, "canvas", "accent", "structure", blk="minecraft:spruce_fence")
        for x in range(x0, x1 + 1): self.put(x, 68, int(mid), "timber", "secondary", "structure", blk="minecraft:stripped_dark_oak_log[axis=x]")

    def posts(self):
        self.container(-16, -9, -10, -4, -10, band=False)   # Quartermaster
        self.container(10, -9, 16, -4, 10, band=True)       # The Broker
        self.tent(-16, 3, -10, 9, -10)                       # Builder
        self.tent(10, 3, 16, 7, 10)                          # Bunker Manager
        # the Fixer's booth: ply back wall, dark posts, a desk, a slab roof
        self.fill(-3, 63, -16, 3, 63, -11, "timber", "main", k=1)
        for x in range(-3, 4):
            for z in range(-16, -10):
                for y in range(64, 68): self.air(x, y, z, "shape")
        for x in (-3, 3):
            for z in (-16, -11):
                for y in range(64, 68): self.put(x, y, z, "timber", "secondary", "structure", k=0)
        self.fill(-2, 64, -16, 2, 67, -16, "timber", "main", k=1)
        self.fill(-3, 64, -15, -3, 67, -12, "timber", "main", k=1); self.fill(3, 64, -15, 3, 67, -12, "timber", "main", k=1)
        self.fill(-3, 68, -16, 3, 68, -11, "timber", "secondary", "structure", blk="minecraft:dark_oak_slab[type=bottom]")
        for x in range(-3, 4): self.put(x, 68, -10, "timber", "accent", "structure", blk="minecraft:spruce_trapdoor[half=top,facing=south]")   # shutter awning
        for x in (-3, 3):
            for z in range(-15, -11): self.put(x, 64, z, "timber", "accent", k=1)   # kick plates
        # sleeping tents
        self.tent(-11, -16, -6, -12, -6)
        self.tent(6, -16, 11, -12, 6)

    def helipad(self):
        hx, hz = HELI
        for x in range(hx - 5, hx + 6):
            for z in range(hz - 5, hz + 6):
                d = ((x - hx) ** 2 + (z - hz) ** 2) ** 0.5
                if d <= 4.2: self.put(x, 63, z, "ground", "accent", k=0)          # grey pad
                elif d <= 4.9: self.put(x, 63, z, "ground", "accent", k=2)        # yellow ring
        for z in range(hz - 2, hz + 3): self.put(hx - 1, 63, z, "ground", "accent", k=1); self.put(hx + 1, 63, z, "ground", "accent", k=1)
        self.put(hx, 63, hz, "ground", "accent", k=1)
        for dx, dz in [(-4, 0), (4, 0), (0, 4), (0, -4)]: self.put(hx + dx, 63, hz + dz, "light", "secondary", "structure", k=0)   # flush pad lights

    def blockhouse(self):
        # concrete blockhouse over the bunker steps: 3 wide x 3 high entrance (north), green blast-door frame
        for x in range(10, 15):
            for z in range(12, 17):
                self.put(x, 64, z, "concrete", "secondary", k=0)                 # grey plinth band
                for y in (65, 66, 67): self.put(x, y, z, "concrete", "main", k=1)
                self.put(x, 68, z, "concrete", "secondary", "structure", blk="minecraft:smooth_stone_slab[type=bottom]")
        for x in range(11, 14):
            for z in range(13, 16):
                for y in range(64, 68): self.air(x, y, z, "shape")
        for x in range(11, 14):
            for y in range(64, 67): self.air(x, y, 12, "shape")
        for y in range(64, 68): self.put(10, y, 12, "concrete", "accent", "structure", k=0); self.put(14, y, 12, "concrete", "accent", "structure", k=0)
        for x in range(11, 14): self.put(x, 67, 12, "concrete", "accent", "structure", k=0)
        # the steps down, the landing, the door
        for x in (10, 14):
            for z in (13, 14, 15): self.fill(x, 61, z, x, 63, z, "concrete", "main", k=1)
        self.fill(11, 60, 13, 13, 60, 16, "concrete", "main", k=1)
        self.fill(11, 61, 16, 13, 63, 16, "concrete", "main", k=1)
        self.fill(11, 62, 13, 13, 63, 15, "air")
        self.fill(11, 63, 13, 13, 63, 13, "concrete", "secondary", "structure", blk="minecraft:polished_tuff_stairs[facing=north]")
        self.fill(11, 62, 14, 13, 62, 14, "concrete", "secondary", "structure", blk="minecraft:polished_tuff_stairs[facing=north]")
        self.fill(11, 61, 15, 13, 61, 15, "concrete", "secondary", k=0)
        self.put(12, 62, 16, "steel", "secondary", "structure", blk="minecraft:iron_door[half=lower,facing=north]")
        self.put(12, 63, 16, "steel", "secondary", "structure", blk="minecraft:iron_door[half=upper,facing=north]")
        self.put(11, 63, 16, "concrete", "accent", "structure", k=1); self.put(13, 63, 16, "concrete", "accent", "structure", k=2)
        self.put(11, 62, 16, "concrete", "accent", "structure", k=2); self.put(13, 62, 16, "concrete", "accent", "structure", k=1)
        self.put(12, 64, 16, "light", "secondary", "structure", k=0)                      # warm light over the door
        self.put(12, 67, 14, "light", "main", "structure", blk="minecraft:lantern[hanging=true]")

    def towers(self):
        for tx, tz in [(-15, -15), (15, -15), (-15, 15)]:   # the south-east corner is the blockhouse
            sz = 1 if tz > 0 else -1
            for x in (tx - 1, tx + 1):
                for z in (tz - 1, tz + 1):
                    for y in range(64, 75): self.put(x, y, z, "timber", "main", "structure", k=0)
            for y in range(64, 71): self.put(tx, y, tz + sz, "timber", "main", k=1)
            for y in range(64, 72): self.put(tx, y, tz, "timber", "main", "structure", blk=f"minecraft:ladder[facing={'north' if sz > 0 else 'south'}]")
            for x in range(tx - 1, tx + 2):
                for z in range(tz - 1, tz + 2):
                    if (x, z) != (tx, tz): self.put(x, 71, z, "timber", "main", k=1)
            for x in range(tx - 2, tx + 3):
                for z in range(tz - 2, tz + 3):
                    if abs(x - tx) == 2 or abs(z - tz) == 2:
                        self.put(x, 71, z, "timber", "main", "structure", blk="minecraft:oak_slab[type=top]")
                        self.put(x, 72, z, "earthworks", "secondary", "structure", blk="minecraft:mud_brick_wall")
            for x in range(tx - 2, tx + 3):
                for z in range(tz - 2, tz + 3): self.put(x, 75, z, "timber", "secondary", "structure", blk="minecraft:dark_oak_slab[type=bottom]")
            self.put(tx, 74, tz, "light", "main", "structure", blk="minecraft:lantern[hanging=true]")

    # ------------------------------------------------------------ layer 2: landmarks, lights
    def landmarks(self):
        # flag, north-east of the plaza
        self.put(4, 64, -5, "steel", "secondary", "structure", k=0)
        for y in range(65, 73): self.put(4, y, -5, "steel", "accent", "structure", blk="minecraft:iron_bars")
        for x in (5, 6, 7):
            for y in (70, 71): self.put(x, y, -5, "canvas", "accent", "structure", blk="minecraft:white_wool" if y == 71 else "minecraft:green_wool")
        # radio mast, south-west of the plaza, with its generator
        self.put(-5, 64, 4, "steel", "secondary", "structure", k=0)
        for y in range(65, 76): self.put(-5, y, 4, "light", "accent", "structure", blk="minecraft:iron_bars")
        self.put(-5, 71, 4, "light", "secondary", "structure", k=0)
        self.put(-5, 76, 4, "light", "accent", "structure", blk="minecraft:lightning_rod")
        # lamp posts, all beside a path, never on one
        for x, z in [(-2, -7), (2, -7), (-2, 5), (2, 5), (-6, -2), (6, -2), (-6, 2), (6, 2), (-10, 0), (10, 0), (10, 8), (6, 10), (-6, 10), (-6, -9), (6, -9)]:
            assert not on_path(x, z), (x, z)
            for y in (64, 65, 66): self.put(x, y, z, "timber", "secondary", "structure", blk="minecraft:dark_oak_fence")
            self.put(x, 67, z, "light", "main", "structure", blk="minecraft:lantern")

    # ------------------------------------------------------------ layer 3: props
    def props(self):
        P = lambda x, y, z, b, fam="steel", role="accent": self.put(x, y, z, fam, role, "props", blk=b)
        # Quartermaster: racks and an armourer's bench, a lit counter
        P(-14, 64, -8, "minecraft:smithing_table"); P(-14, 64, -5, "minecraft:grindstone[face=floor,facing=east]")
        P(-15, 64, -6, "minecraft:anvil[facing=east]"); P(-15, 64, -7, "minecraft:barrel[facing=up]"); P(-15, 65, -7, "minecraft:lantern", "light", "main")
        P(-11, 64, -8, "minecraft:barrel[facing=east]"); P(-11, 64, -5, "minecraft:barrel[facing=east]"); P(-11, 65, -8, "minecraft:lantern", "light", "main")
        # Broker: shelves, maps, a lamp
        P(14, 64, -8, "minecraft:chiseled_bookshelf[facing=west]"); P(14, 64, -5, "minecraft:chiseled_bookshelf[facing=west]")
        P(15, 64, -6, "minecraft:cartography_table"); P(15, 64, -7, "minecraft:barrel[facing=up]"); P(15, 65, -7, "minecraft:lantern", "light", "main")
        P(11, 64, -8, "minecraft:barrel[facing=west]"); P(11, 64, -5, "minecraft:barrel[facing=west]"); P(11, 65, -8, "minecraft:lantern", "light", "main")
        # Builder: saw bench, materials; Bunker Manager: plans on a lectern, crates
        P(-15, 64, 4, "minecraft:stonecutter"); P(-15, 64, 8, "minecraft:crafting_table"); P(-14, 64, 8, "minecraft:scaffolding"); P(-11, 64, 4, "minecraft:barrel[facing=up]")
        P(-11, 65, 4, "minecraft:lantern", "light", "main")
        P(15, 64, 4, "minecraft:lectern[facing=west]"); P(15, 64, 6, "minecraft:crafting_table"); P(15, 65, 6, "minecraft:lantern", "light", "main"); P(11, 64, 4, "minecraft:barrel[facing=up]")
        # Fixer: map board on the back wall, a desk with a lamp
        for x in range(-2, 3): P(x, 65, -15, "minecraft:cartography_table")
        for x in (-2, -1, 1, 2): P(x, 64, -14, "minecraft:dark_oak_slab[type=top]", "timber", "secondary")
        P(-2, 65, -14, "minecraft:lantern", "light", "main"); P(2, 64, -15, "minecraft:barrel[facing=up]")
        # sleeping tents: cots
        for x0 in (-10, 7):
            P(x0, 64, -14, "minecraft:green_bed[facing=east,part=foot]", "canvas"); P(x0 + 1, 64, -14, "minecraft:green_bed[facing=east,part=head]", "canvas")
        # fire pit (north-west quarter), seats round it
        P(-4, 64, -7, "minecraft:campfire[lit=true]", "light", "accent")
        for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]: P(-4 + dx, 64, -7 + dz, "minecraft:mud_brick_slab[type=bottom]", "earthworks", "secondary")
        # generator and cable run to the mast; a conduit along the west wall's step to the posts
        P(-6, 64, 4, "minecraft:blast_furnace[facing=west]"); P(-6, 64, 5, "minecraft:cauldron", "light", "accent")
        for z in range(-9, 10): P(-17, 66, z, "minecraft:lightning_rod[facing=south]", "light", "accent")
        # sandbags: by the blockhouse door, round the helipad's back
        for x in (14, 15): P(x, 64, 11, "minecraft:mud_brick_wall", "earthworks", "secondary")
        hx, hz = HELI
        for x in range(hx - 7, hx + 8):
            for z in range(hz + 2, hz + 7):
                d = ((x - hx) ** 2 + (z - hz) ** 2) ** 0.5
                if 5.6 <= d <= 6.3 and not on_path(x, z): P(x, 64, z, "minecraft:mud_brick_wall", "earthworks", "secondary")
        # windsock
        for y in range(64, 69): P(7, y, 16, "minecraft:iron_bars")
        P(8, 68, 16, "minecraft:orange_wool", "canvas"); P(9, 68, 16, "minecraft:white_wool", "canvas"); P(10, 67, 16, "minecraft:orange_wool", "canvas")
        # the jeep (south-west) and fuel drums
        for x in range(-14, -8):
            for z in (12, 13, 14): P(x, 64, z, "minecraft:green_terracotta", "steel", "main")
        for x in range(-12, -8):
            for z in (12, 13, 14): P(x, 65, z, "minecraft:green_terracotta", "steel", "main")
        P(-13, 65, 13, "minecraft:dark_oak_stairs[facing=west]", "timber", "secondary")
        for x in (-14, -9):
            for z in (11, 15): P(x, 64, z, "minecraft:black_concrete")
        P(-9, 66, 12, "minecraft:tinted_glass"); P(-9, 66, 14, "minecraft:tinted_glass")
        for x, z in [(-16, 12), (-16, 13), (-16, 15), (-15, 16)]: P(x, 64, z, "minecraft:cauldron", "light", "accent")
        # supply stacks along the walls
        for x, z in [(-4, -16), (4, -16), (5, -16), (-6, 16), (-5, 16), (5, 16)]:
            P(x, 64, z, "minecraft:barrel[facing=up]")
            if (x + z) % 2: P(x, 65, z, "minecraft:spruce_trapdoor[half=bottom]", "timber", "accent")

    def build(self):
        self.ground(); self.perimeter(); self.posts(); self.helipad(); self.blockhouse(); self.towers()
        self.landmarks()
        if self.mode == "detail": self.props()
        return self

    # ------------------------------------------------------------ checks done at build time
    def check(self):
        bad = sorted({b.split("[")[0] for b, *_ in self.B.values() if b.split("[")[0] not in VALID})
        assert not bad, f"not 26.2 blocks: {bad}"
        blocked = [(x, y, z, b) for (x, y, z), (b, f, *_ ) in self.B.items() if y in (64, 65) and on_path(x, z) and f != "air" and b != "minecraft:air"]
        assert not blocked, f"something stands on a path: {blocked[:8]}"
        return True

    def shares(self):
        """Measured palette split per family: shape and structure blocks above the ground (props and paths left out)."""
        out = {}
        for (x, y, z), (b, fam, role, layer) in self.B.items():
            if layer == "props": continue   # props are props, not palette material
            if fam in ("air", "path") or role not in ("main", "secondary", "accent") or b in ("minecraft:bedrock", "minecraft:dirt") and y < 63: continue
            if fam == "ground" and y < 63: continue
            out.setdefault(fam, {"main": 0, "secondary": 0, "accent": 0})[role] += 1
        return {f: {r: round(n / max(1, sum(v.values())), 2) for r, n in v.items()} | {"blocks": sum(v.values())} for f, v in out.items()}

    def commands(self, dim):
        out = [f"execute in {dim} run fill -32 {y} -32 32 {y} 32 minecraft:air" for y in range(58, 78)]
        rows = {}
        for (x, y, z), (blk, *_) in self.B.items(): rows.setdefault((y, z), {})[x] = blk
        for (y, z), cols in sorted(rows.items()):
            xs = sorted(cols); start = prev = xs[0]
            for x in xs[1:] + [None]:
                if x is not None and x == prev + 1 and cols[x] == cols[start]:
                    prev = x; continue
                blk = cols[start]
                if blk != "minecraft:air":
                    out.append(f"execute in {dim} run " + (f"setblock {start} {y} {z} {blk}" if start == prev else f"fill {start} {y} {z} {prev} {y} {z} {blk}"))
                if x is not None: start = prev = x
        return out


def layout(posts, spawn, heli):
    """The plan the self-test checks, from the same numbers the builder used."""
    return {"version": "1.6.0", "spawn": list(spawn), "region": [-17, 58, -17, 17, 76, 17],
            "paths": [{"name": n, "box": [x0, z0, x1, z1]} for n, x0, z0, x1, z1 in PATHS],
            "doorways": [{"name": n, "cells": c, "width": w, "height": h} for n, c, w, h in DOORWAYS],
            "destinations": [{"name": nm, "kind": "npc", "pos": [x, 64, z]} for nm, col, shop, x, z, rot in posts]
                            + [{"name": "helipad (deploy)", "kind": "pad", "pos": [heli[0] + 0.5, 64, heli[1] + 0.5]},
                               {"name": "blockhouse door", "kind": "door", "pos": [12.5, 62, 15.5]},
                               {"name": "bunker exit point", "kind": "point", "pos": [12.5, 64, 10.5]}],
            "npc_path_max": 4.5, "path_width": 3, "path_headroom": 3}


if __name__ == "__main__":
    for m in ("grey", "detail"):
        c = Camp(m).build(); c.check()
        print(m, len(c.B), "blocks;", json.dumps(c.shares()))
