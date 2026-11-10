"""Top-down extract of Anarchy region files: per column the top block (name id), its height and water depth.
Read-only. Usage: extract.py <region dir> <out dir> <rx0> <rx1> <rz0> <rz1>"""
import os, sys, zlib, struct, io, json, array
R, OUT = sys.argv[1], sys.argv[2]
rx0, rx1, rz0, rz1 = map(int, sys.argv[3:7])
os.makedirs(OUT, exist_ok=True)
names = {}
def nid(n):
    if n not in names: names[n] = len(names)
    return names[n]
AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:light", "minecraft:barrier", "minecraft:structure_void"}
WATERY = {"minecraft:water", "minecraft:bubble_column", "minecraft:kelp", "minecraft:kelp_plant", "minecraft:seagrass", "minecraft:tall_seagrass"}

def nbt(f):
    t = f.read(1)[0]
    if t == 0: return None
    f.read(struct.unpack('>H', f.read(2))[0]); return pl(f, t)
def pl(f, t):
    r = f.read
    if t == 1: return r(1)[0]
    if t == 2: return struct.unpack('>h', r(2))[0]
    if t == 3: return struct.unpack('>i', r(4))[0]
    if t == 4: return struct.unpack('>q', r(8))[0]
    if t == 5: r(4); return 0
    if t == 6: r(8); return 0
    if t == 7: n = struct.unpack('>i', r(4))[0]; r(n); return None
    if t == 8: n = struct.unpack('>H', r(2))[0]; return r(n).decode('utf-8', 'replace')
    if t == 9:
        et = r(1)[0]; n = struct.unpack('>i', r(4))[0]; return [pl(f, et) for _ in range(n)]
    if t == 10:
        d = {}
        while True:
            et = r(1)[0]
            if et == 0: return d
            k = r(struct.unpack('>H', r(2))[0]).decode('utf-8', 'replace'); d[k] = pl(f, et)
    if t == 11: n = struct.unpack('>i', r(4))[0]; return array.array('i', r(4 * n))
    if t == 12:
        n = struct.unpack('>i', r(4))[0]; a = array.array('q', r(8 * n)); a.byteswap(); return a

def unpack(longs, bits, count):
    out = [0] * count; per = 64 // bits; mask = (1 << bits) - 1; i = 0
    for v in longs:
        v &= 0xFFFFFFFFFFFFFFFF
        for _ in range(per):
            if i >= count: return out
            out[i] = v & mask; v >>= bits; i += 1
    return out

def chunk(data):
    root = nbt(io.BytesIO(data))
    if not root or str(root.get('Status', '')).split(':')[-1] not in ('full', 'spawn', 'heightmaps', 'light', 'initialize_light', 'features'):
        return None
    ymin = root.get('yPos', -4) * 16
    secs = {}
    for s in root.get('sections') or []:
        bs = s.get('block_states')
        if not bs: continue
        pal = [p.get('Name', 'minecraft:air') for p in bs.get('palette', [])]
        if len(pal) == 1: secs[s['Y']] = (pal, None); continue
        bits = max(4, (len(pal) - 1).bit_length())
        secs[s['Y']] = (pal, unpack(bs['data'], bits, 4096))
    hm = (root.get('Heightmaps') or {}).get('WORLD_SURFACE')
    if hm is None: return None
    heights = unpack(hm, 9, 256)
    def block(x, y, z):
        s = secs.get(y >> 4)
        if not s: return 'minecraft:air'
        pal, idx = s
        return pal[0] if idx is None else pal[idx[((y & 15) << 8) | (z << 4) | x]]
    res = []
    for z in range(16):
        for x in range(16):
            y = heights[z * 16 + x] + ymin - 1
            b = block(x, y, z); n = 0
            while b in AIR and y > ymin: y -= 1; b = block(x, y, z)
            depth = 0
            if b in WATERY:
                yy = y
                while yy > ymin and depth < 30:
                    yy -= 1; bb = block(x, yy, z)
                    if bb not in WATERY: break
                    depth += 1
            res.append((nid(b), y, depth))
    return res

for rx in range(rx0, rx1 + 1):
    for rz in range(rz0, rz1 + 1):
        fn = os.path.join(R, f"r.{rx}.{rz}.mca")
        outf = os.path.join(OUT, f"r.{rx}.{rz}.bin")
        if not os.path.exists(fn) or os.path.exists(outf): continue
        data = open(fn, 'rb').read()
        ids = array.array('H', [0xFFFF] * 512 * 512); hs = array.array('h', [-32768] * 512 * 512); ds = array.array('B', [0] * 512 * 512)
        for i in range(1024):
            off = int.from_bytes(data[i * 4:i * 4 + 3], 'big')
            if not off: continue
            p = off * 4096
            if p + 5 > len(data): continue
            ln = struct.unpack('>I', data[p:p + 4])[0]; ct = data[p + 4]
            try:
                raw = zlib.decompress(data[p + 5:p + 4 + ln]) if ct == 2 else None
                res = chunk(raw) if raw else None
            except Exception: res = None
            if not res: continue
            cx, cz = i % 32, i // 32
            for k, (b, y, d) in enumerate(res):
                x, z = cx * 16 + k % 16, cz * 16 + k // 16
                ids[z * 512 + x] = b; hs[z * 512 + x] = y; ds[z * 512 + x] = d
        with open(outf + '.tmp', 'wb') as f:
            f.write(zlib.compress(ids.tobytes() + hs.tobytes() + ds.tobytes(), 6))
        os.replace(outf + '.tmp', outf)
        json.dump({v: k for k, v in names.items()}, open(os.path.join(OUT, 'names.json'), 'w'))
        print("done", rx, rz, flush=True)
print("ALL DONE", flush=True)
