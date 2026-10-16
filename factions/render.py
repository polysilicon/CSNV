import sys, zlib, struct, importlib; sys.path.insert(0,"/opt/factions/survey"); import scan
COL={"stone_bricks":(122,122,122),"mossy_stone_bricks":(110,125,100),"cracked_stone_bricks":(115,115,115),"smooth_stone":(160,160,160),"polished_andesite":(135,138,135),
"quartz_bricks":(235,230,225),"quartz_pillar":(235,230,225),"water":(50,90,220),"beacon":(120,240,240),"sea_lantern":(200,240,230),"grass_block":(90,160,60),
"oak_leaves":(60,120,40),"spruce_leaves":(40,80,50),"smooth_sandstone":(220,205,150),"sandstone":(215,200,140),"sand":(225,215,160),"chiseled_sandstone":(210,190,130),
"cut_red_sandstone":(185,100,40),"polished_blackstone_bricks":(45,40,50),"gold_block":(250,210,50),"stone_brick_slab":(140,140,140),"andesite":(130,130,130),
"cobblestone":(110,110,110),"snow":(250,250,255),"snow_block":(250,250,255),"dark_oak_wall_sign":(70,50,30),"stone_brick_wall":(122,122,122),"lantern":(255,200,80),
"stone_brick_stairs":(130,130,130),"spruce_log":(80,60,40),"oak_log":(100,80,50),"dirt":(130,95,65),"stone":(115,115,115),"chiseled_stone_bricks":(130,130,130),"ice":(150,180,250),"gravel":(130,125,120)}
X0,Z0,X1,Z1=-80,-176,80,80; rows=[]
for z in range(Z0,Z1):
    r=bytearray([0])
    for x in range(X0,X1):
        c=(255,0,255)
        for y in range(110,40,-1):
            n=scan.get(x,y,z)[0].split(":")[1]
            if n in("air","short_grass","tall_grass","fern","large_fern","sweet_berry_bush"): continue
            c=COL.get(n,(255,0,255) if "sign" not in n else (70,50,30)); s=0.75+0.25*(y-55)/30; c=tuple(max(0,min(255,int(v*s))) for v in c); break
        r+=bytes(c)
    rows.append(bytes(r))
w,h=X1-X0,Z1-Z0
def ch(t,d): return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d))
open("/opt/factions/survey/map.png","wb").write(b"\x89PNG\r\n\x1a\n"+ch(b"IHDR",struct.pack(">IIBBBBB",w,h,8,2,0,0,0))+ch(b"IDAT",zlib.compress(b"".join(rows)))+ch(b"IEND",b""))
