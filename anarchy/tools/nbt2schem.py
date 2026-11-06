"""Structure-block .nbt -> Sponge v2 .schem (WorldEdit), keeping block states and block entities."""
import gzip, struct, sys
# typed NBT: every value is (tagtype, payload)
def r(b, i, t):
    if t == 1: return (1, struct.unpack('>b', b[i:i+1])[0]), i+1
    if t == 2: return (2, struct.unpack('>h', b[i:i+2])[0]), i+2
    if t == 3: return (3, struct.unpack('>i', b[i:i+4])[0]), i+4
    if t == 4: return (4, struct.unpack('>q', b[i:i+8])[0]), i+8
    if t == 5: return (5, struct.unpack('>f', b[i:i+4])[0]), i+4
    if t == 6: return (6, struct.unpack('>d', b[i:i+8])[0]), i+8
    if t == 7: n = struct.unpack('>i', b[i:i+4])[0]; return (7, b[i+4:i+4+n]), i+4+n
    if t == 8: n = struct.unpack('>H', b[i:i+2])[0]; return (8, b[i+2:i+2+n].decode('utf8')), i+2+n
    if t == 9:
        et = b[i]; n = struct.unpack('>i', b[i+1:i+5])[0]; i += 5; out = []
        for _ in range(n): v, i = r(b, i, et); out.append(v)
        return (9, (et, out)), i
    if t == 10:
        d = {}
        while True:
            et = b[i]; i += 1
            if et == 0: return (10, d), i
            n = struct.unpack('>H', b[i:i+2])[0]; k = b[i+2:i+2+n].decode(); i += 2+n
            d[k], i = r(b, i, et)
    if t == 11: n = struct.unpack('>i', b[i:i+4])[0]; return (11, list(struct.unpack('>%di' % n, b[i+4:i+4+4*n]))), i+4+4*n
    if t == 12: n = struct.unpack('>i', b[i:i+4])[0]; return (12, list(struct.unpack('>%dq' % n, b[i+4:i+4+8*n]))), i+4+8*n
def s(x): e = x.encode(); return struct.pack('>H', len(e)) + e
def w(v):
    t, p = v
    if t == 1: return struct.pack('>b', p)
    if t == 2: return struct.pack('>h', p)
    if t == 3: return struct.pack('>i', p)
    if t == 4: return struct.pack('>q', p)
    if t == 5: return struct.pack('>f', p)
    if t == 6: return struct.pack('>d', p)
    if t == 7: return struct.pack('>i', len(p)) + p
    if t == 8: return s(p)
    if t == 9:
        et, items = p
        if not items: et = 0
        return bytes([et]) + struct.pack('>i', len(items)) + b''.join(w(x) for x in items)
    if t == 10: return b''.join(bytes([v[0]]) + s(k) + w(v) for k, v in p.items()) + b'\x00'
    if t == 11: return struct.pack('>i', len(p)) + struct.pack('>%di' % len(p), *p)
    if t == 12: return struct.pack('>i', len(p)) + struct.pack('>%dq' % len(p), *p)

src, dst = sys.argv[1], sys.argv[2]
b = gzip.open(src).read()
(_, root), _ = r(b, 3 + struct.unpack('>H', b[1:3])[0], 10)
W, H, L = [x[1] for x in root['size'][1][1]]
dv = root['DataVersion'][1]
def state(p):
    name = p[1]['Name'][1]
    props = p[1].get('Properties')
    if props: name += '[' + ','.join(f'{k}={v[1]}' for k, v in sorted(props[1].items())) + ']'
    return name
spal = [state(p) for p in root['palette'][1][1]]
grid = {}; bents = []
for blk in root['blocks'][1][1]:
    d = blk[1]; x, y, z = [q[1] for q in d['pos'][1][1]]
    st = spal[d['state'][1]]
    grid[(x, y, z)] = st
    if 'nbt' in d:
        nb = dict(d['nbt'][1]); bid = nb.pop('id', (8, st.split('[')[0]))[1]
        for k in ('x', 'y', 'z'): nb.pop(k, None)
        nb['Pos'] = (11, [x, y, z]); nb['Id'] = (8, bid)
        bents.append((10, nb))
palette = {'minecraft:air': 0}
data = bytearray()
for y in range(H):
    for z in range(L):
        for x in range(W):
            st = grid.get((x, y, z), 'minecraft:air')
            if st == 'minecraft:structure_void': st = 'minecraft:air'
            i = palette.setdefault(st, len(palette))
            while True:
                byte = i & 0x7F; i >>= 7
                data.append(byte | (0x80 if i else 0))
                if not i: break
sch = {'Version': (3, 2), 'DataVersion': (3, dv), 'Width': (2, W), 'Height': (2, H), 'Length': (2, L),
       'Offset': (11, [0, 0, 0]), 'PaletteMax': (3, len(palette)),
       'Palette': (10, {k: (3, v) for k, v in palette.items()}),
       'Metadata': (10, {'WEOffsetX': (3, 0), 'WEOffsetY': (3, 0), 'WEOffsetZ': (3, 0)}),
       'BlockData': (7, bytes(data)), 'BlockEntities': (9, (10, bents))}
with gzip.open(dst, 'wb') as f: f.write(bytes([10]) + s('Schematic') + w((10, sch)))
print(f'{dst.split("/")[-1]}: {W}x{H}x{L}, {len(palette)} states, {len(bents)} block entities, DataVersion {dv}')
