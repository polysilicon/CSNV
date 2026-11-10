"""Colour the extracted columns like an in-game map. render.py <extract dir> <out png> [rx0 rx1 rz0 rz1]"""
import sys, json, zlib, array, os, re
from PIL import Image
D, OUT = sys.argv[1], sys.argv[2]
names = {int(k): v for k, v in json.load(open(os.path.join(D, 'names.json'))).items()}
C = {  # base colours (roughly Minecraft's map colours, a bit brighter)
 'grass_block': (110, 160, 60), 'short_grass': (100, 150, 55), 'tall_grass': (100, 150, 55), 'fern': (90, 140, 55), 'moss_block': (90, 130, 50),
 'dirt': (134, 96, 67), 'coarse_dirt': (120, 86, 60), 'rooted_dirt': (130, 95, 70), 'podzol': (100, 70, 40), 'mycelium': (110, 95, 105), 'farmland': (110, 75, 45), 'dirt_path': (150, 125, 75), 'mud': (60, 55, 60),
 'stone': (125, 125, 125), 'cobblestone': (115, 115, 115), 'mossy_cobblestone': (100, 115, 95), 'andesite': (135, 135, 135), 'diorite': (190, 190, 190), 'granite': (150, 105, 85), 'tuff': (110, 110, 100), 'deepslate': (80, 80, 85), 'cobbled_deepslate': (75, 75, 80), 'calcite': (220, 220, 215), 'bedrock': (60, 60, 60), 'gravel': (135, 130, 128), 'clay': (160, 165, 180),
 'sand': (220, 210, 160), 'sandstone': (215, 200, 150), 'red_sand': (190, 100, 40), 'red_sandstone': (180, 95, 40),
 'snow': (245, 250, 250), 'snow_block': (240, 245, 245), 'powder_snow': (240, 245, 245), 'ice': (160, 190, 245), 'packed_ice': (150, 180, 240), 'blue_ice': (120, 160, 240),
 'water': (50, 90, 200), 'lava': (230, 90, 20), 'obsidian': (25, 15, 40), 'crying_obsidian': (45, 20, 80), 'netherrack': (110, 40, 40), 'soul_sand': (85, 65, 50), 'soul_soil': (75, 58, 45), 'glowstone': (250, 210, 120), 'magma_block': (140, 60, 20), 'end_stone': (220, 220, 160),
 'oak_leaves': (60, 120, 40), 'birch_leaves': (95, 140, 60), 'spruce_leaves': (50, 90, 55), 'jungle_leaves': (50, 135, 30), 'acacia_leaves': (80, 130, 35), 'dark_oak_leaves': (45, 100, 30), 'mangrove_leaves': (60, 120, 35), 'cherry_leaves': (240, 170, 200), 'azalea_leaves': (90, 130, 50), 'flowering_azalea_leaves': (120, 130, 80),
 'cactus': (85, 130, 45), 'pumpkin': (210, 125, 30), 'melon': (120, 160, 40), 'hay_block': (205, 175, 40), 'bone_block': (225, 220, 200), 'tnt': (200, 50, 40), 'glass': (200, 225, 230), 'bricks': (150, 80, 65), 'nether_bricks': (60, 30, 35), 'quartz_block': (235, 230, 225), 'iron_block': (220, 220, 220), 'gold_block': (245, 210, 60), 'diamond_block': (100, 230, 225), 'emerald_block': (60, 210, 100), 'redstone_block': (180, 20, 10), 'lapis_block': (35, 70, 160), 'netherite_block': (65, 60, 65), 'purpur_block': (170, 120, 170), 'prismarine': (95, 160, 150), 'sea_lantern': (210, 230, 225), 'slime_block': (120, 200, 90), 'honey_block': (240, 170, 40), 'sponge': (200, 195, 80),
}
WOOL = {'white': (235, 235, 235), 'orange': (235, 120, 30), 'magenta': (190, 70, 180), 'light_blue': (60, 175, 220), 'yellow': (245, 205, 45), 'lime': (115, 185, 30), 'pink': (235, 140, 170), 'gray': (65, 70, 75), 'light_gray': (145, 145, 140), 'cyan': (20, 140, 145), 'purple': (120, 40, 170), 'blue': (50, 55, 160), 'brown': (115, 75, 45), 'green': (85, 110, 30), 'red': (160, 40, 35), 'black': (25, 25, 30)}
WOOD = {'oak': (165, 135, 85), 'spruce': (115, 85, 50), 'birch': (195, 180, 125), 'jungle': (160, 115, 80), 'acacia': (170, 90, 50), 'dark_oak': (70, 45, 25), 'mangrove': (120, 50, 45), 'cherry': (225, 180, 170), 'bamboo': (200, 180, 80), 'crimson': (110, 50, 75), 'warped': (45, 105, 100), 'pale_oak': (230, 220, 215)}
def colour(n):
    b = n.split(':')[-1]
    if b in C: return C[b]
    for col, rgb in WOOL.items():
        if b.startswith(col + '_'): return rgb
    for w, rgb in WOOD.items():
        if b.startswith(w + '_') or b.startswith('stripped_' + w): return rgb
    for k in ('deepslate', 'blackstone', 'basalt', 'stone_brick', 'cobblestone', 'andesite', 'diorite', 'granite', 'tuff', 'sandstone', 'quartz', 'prismarine', 'purpur', 'nether_brick', 'brick', 'mud_brick', 'copper', 'iron', 'gold', 'amethyst', 'terracotta', 'concrete', 'glass', 'ice', 'snow', 'stone', 'leaves', 'sand', 'end_stone', 'obsidian'):
        if k in b:
            return {'deepslate': (80, 80, 85), 'blackstone': (45, 40, 45), 'basalt': (80, 80, 85), 'stone_brick': (120, 120, 120), 'cobblestone': (115, 115, 115), 'andesite': (135, 135, 135), 'diorite': (190, 190, 190), 'granite': (150, 105, 85), 'tuff': (110, 110, 100), 'sandstone': (215, 200, 150), 'quartz': (235, 230, 225), 'prismarine': (95, 160, 150), 'purpur': (170, 120, 170), 'nether_brick': (60, 30, 35), 'brick': (150, 80, 65), 'mud_brick': (140, 105, 80), 'copper': (190, 110, 80), 'iron': (200, 200, 200), 'gold': (240, 200, 60), 'amethyst': (140, 100, 200), 'terracotta': (155, 95, 70), 'concrete': (150, 150, 150), 'glass': (200, 225, 230), 'ice': (160, 190, 245), 'snow': (240, 245, 245), 'stone': (125, 125, 125), 'leaves': (60, 120, 40), 'sand': (220, 210, 160), 'end_stone': (220, 220, 160), 'obsidian': (25, 15, 40)}[k]
    if 'ore' in b: return (125, 125, 125)
    if any(k in b for k in ('torch', 'lantern', 'campfire')): return (240, 200, 90)
    if any(k in b for k in ('flower', 'tulip', 'poppy', 'dandelion', 'orchid', 'allium', 'daisy', 'rose', 'lilac', 'peony', 'cornflower')): return (110, 150, 60)
    if any(k in b for k in ('kelp', 'seagrass', 'bubble_column')): return C['water']
    if any(k in b for k in ('vine', 'sapling', 'bush', 'crop', 'wheat', 'carrots', 'potatoes', 'beetroots', 'sugar_cane', 'bamboo', 'lily_pad')): return (90, 140, 50)
    if 'sign' in b or 'chest' in b or 'barrel' in b or 'crafting' in b: return (150, 115, 70)
    if 'shulker_box' in b: return (140, 100, 140)
    if 'rail' in b: return (150, 130, 110)
    return (140, 140, 140)
cache = {}
def regions():
    for f in os.listdir(D):
        m = re.match(r'r\.(-?\d+)\.(-?\d+)\.bin$', f)
        if m: yield int(m.group(1)), int(m.group(2))
rs = list(regions())
if len(sys.argv) > 3: rx0, rx1, rz0, rz1 = map(int, sys.argv[3:7])
else: rx0, rx1, rz0, rz1 = min(r[0] for r in rs), max(r[0] for r in rs), min(r[1] for r in rs), max(r[1] for r in rs)
W, H = (rx1 - rx0 + 1) * 512, (rz1 - rz0 + 1) * 512
ids = array.array('H', [0xFFFF] * (W * H)); hs = array.array('h', [-32768] * (W * H)); ds = array.array('B', [0] * (W * H))
for rx, rz in rs:
    if not (rx0 <= rx <= rx1 and rz0 <= rz <= rz1): continue
    raw = zlib.decompress(open(os.path.join(D, f'r.{rx}.{rz}.bin'), 'rb').read())
    a = array.array('H', raw[:512 * 512 * 2]); h = array.array('h', raw[512 * 512 * 2:512 * 512 * 4]); d = raw[512 * 512 * 4:]
    ox, oz = (rx - rx0) * 512, (rz - rz0) * 512
    for z in range(512):
        row = (oz + z) * W + ox
        ids[row:row + 512] = a[z * 512:(z + 1) * 512]; hs[row:row + 512] = h[z * 512:(z + 1) * 512]; ds[row:row + 512] = array.array('B', d[z * 512:(z + 1) * 512])
img = Image.new('RGB', (W, H), (20, 22, 30)); px = img.load()
for z in range(H):
    for x in range(W):
        i = z * W + x; b = ids[i]
        if b == 0xFFFF: continue
        n = names[b]
        if n not in cache: cache[n] = colour(n)
        r, g, bl = cache[n]
        y = hs[i]
        if n.endswith(':water') or ds[i]:
            k = max(0.45, 1 - ds[i] * 0.04); r, g, bl = int(r * k), int(g * k), int(bl * k)
        else:
            yn = hs[i - W] if z > 0 and hs[i - W] != -32768 else y
            f = 1.12 if y > yn else 0.82 if y < yn else 1.0
            r, g, bl = min(255, int(r * f)), min(255, int(g * f)), min(255, int(bl * f))
        px[x, z] = (r, g, bl)
img.save(OUT)
print("rendered", W, "x", H, "origin block", rx0 * 512, rz0 * 512)
