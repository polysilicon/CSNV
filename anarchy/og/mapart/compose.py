import json,pickle,math
from PIL import Image
P='/tmp/claude-0/-home-user-CSNV/c6f73eb8-1ab1-54f0-8c26-8516bedafa4b/scratchpad/'
src=open(P+'schem_render.py').read(); exec(src[src.index('def col(name):'):src.index('img=Image.new')])
EXTRA=[('water',(64,64,255)),('leaves',(0,124,0)),('grass_block',(127,178,56)),('sand',(247,233,163)),('snow',(255,255,255)),('stone',(112,112,112))]
def col2(n):
    for k,c in EXTRA:
        if k==n or (k in n and k in ('water','leaves')): return c
    return col(n)
top=pickle.load(open(P+'mapart/top.pkl','rb'))
CX,CZ,BPP=0,-15,4; X0,Z0=CX-64*BPP,CZ-64*BPP
SPOTS=[(-26,93,-100),(-58,93,-71),(-57,105,-35),(203,74,-202),(109,175,-146),(164,155,235),(148,86,-206),(-138,95,-52)]
H={}; img=Image.new('RGB',(128,128),(0,0,0)); mask=[[False]*128 for _ in range(128)]
for px in range(128):
    for pz in range(128):
        best=None
        for dx in range(BPP):
            for dz in range(BPP):
                t=top.get((X0+px*BPP+dx,Z0+pz*BPP+dz))
                if t and (best is None or t[0]>best[0]): best=t
        if best: H[(px,pz)]=best
for (px,pz),(y,nm) in H.items():
    c=col2(nm)
    n=H.get((px,pz-1)); sh=1.0
    if n: sh=1.12 if y>n[0] else 0.86 if y<n[0] else 1.0
    img.putpixel((px,pz),tuple(max(0,min(255,int(k*sh))) for k in c)); mask[pz][px]=True
# palette: map colour ids * 4 shades
pal=json.load(open(P+'mapart/palette.json')); MUL=[180,220,255,135]
choices=[]
for i,rgb in pal.items():
    i=int(i)
    if i==0: continue
    r,g,b=(rgb>>16)&255,(rgb>>8)&255,rgb&255
    for s,m in enumerate(MUL): choices.append((i*4+s,(r*m//255,g*m//255,b*m//255)))
def near(c): return min(choices,key=lambda e:(e[1][0]-c[0])**2*3+(e[1][1]-c[1])**2*4+(e[1][2]-c[2])**2*2)
cache={}
data=bytearray(128*128); out=Image.new('RGB',(128,128),(0,0,0))
for pz in range(128):
    for px in range(128):
        if not mask[pz][px]: idx,rgb=0,(0,0,0)   # 0 = transparent (map paper shows through)
        else:
            c=img.getpixel((px,pz)); key=(c[0]//4,c[1]//4,c[2]//4)
            if key not in cache: cache[key]=near(c)
            idx,rgb=cache[key]
        data[pz*128+px]=idx; out.putpixel((px,pz),rgb if idx else (214,196,150))
# dots: a red mark with a dark ring at each spot
RED=near((230,20,20)); DARK=near((30,10,10)); 
for (x,y,z) in SPOTS:
    px,pz=(x-X0)//BPP,(z-Z0)//BPP
    for dx in range(-2,3):
        for dz in range(-2,3):
            if not (0<=px+dx<128 and 0<=pz+dz<128): continue
            ring=max(abs(dx),abs(dz))==2
            if ring and abs(dx)==2 and abs(dz)==2: continue
            e=DARK if ring else RED
            data[(pz+dz)*128+px+dx]=e[0]; out.putpixel((px+dx,pz+dz),e[1])
open(P+'mapart/overview.colors','wb').write(bytes(data))
out.resize((512,512),Image.NEAREST).save(P+'mapart/overview.png'); print('ok', len(cache))
