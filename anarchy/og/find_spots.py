import sys,math,re,os,random
from collections import deque
P='/tmp/claude-0/-home-user-CSNV/c6f73eb8-1ab1-54f0-8c26-8516bedafa4b/scratchpad/'
exec(open(P+'find_nooks.py').read().split('cands=[]')[0])   # loads B (blocks near shops), shops, soft/solid helpers
names=re.findall(r'summon minecraft:villager \S+ \S+ \S+ \{.*?CustomName:\{text:"([^"]*)"',open(P+'mkt/spawn_shops.mcfunction').read())
def passable(b): return soft(b) or (b is not None and any(k in b for k in ('door','fence_gate')) and 'trapdoor' not in b)
def floor_ok(b): return b is not None and not soft(b) and not any(k in b for k in ('water','lava'))
def stand(x,y,z): return floor_ok(B.get((x,y-1,z))) and passable(B.get((x,y,z))) and passable(B.get((x,y+1,z)))
def sky(x,y,z): return all(B.get((x,y+k,z)) is None for k in range(2,16))
def roofed(x,y,z): return any(solid(B.get((x,y+k,z))) for k in (2,3,4))
out=[]
for (sx,sy,sz),name in zip(shops,names+['arrival']):
    if name=='arrival': continue
    vx,vy,vz=int(math.floor(sx)),int(sy),int(math.floor(sz))
    # walkable cells within 14 blocks of the shop villager, 1-block steps, small drops
    seen=set(); comp={}
    starts=[(vx+dx,vy+dy,vz+dz) for dx in range(-3,4) for dz in range(-3,4) for dy in (-1,0,1) if stand(vx+dx,vy+dy,vz+dz)]
    cid=0
    for st in starts:
        if st in seen: continue
        cid+=1; q=deque([st]); seen.add(st); cells=[st]
        while q:
            x,y,z=q.popleft()
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                for dy in (0,1,-1,-2,-3):
                    n=(x+dx,y+dy,z+dz)
                    if n in seen or abs(n[0]-vx)>14 or abs(n[2]-vz)>14 or abs(n[1]-vy)>6: continue
                    if dy==1 and not passable(B.get((x,y+2,z))): continue
                    if stand(*n): seen.add(n); q.append(n); cells.append(n); break
        if any(sky(*c) for c in cells): comp[cid]=cells   # this area opens to the outside: players can walk in
    cells=[c for cs in comp.values() for c in cs]
    best=None
    for (x,y,z) in cells:
        walls=sum(1 for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)) if solid(B.get((x+dx,y,z+dz))) and solid(B.get((x+dx,y+1,z+dz))))
        d=math.dist((x,y,z),(vx,vy,vz))
        if walls>=2 and roofed(x,y,z) and 3<=d<=10:
            score=walls*10-d
            if best is None or score>best[0]: best=(score,(x,y,z),walls,round(d,1))
    if best: out.append((name,best[1],best[2],best[3]))
pick=[]
for o in out:
    if all(math.dist(o[1],p[1])>=20 for p in pick): pick.append(o)
for p in pick: print(p)
print(len(out),'shops with a spot;',len(pick),'spread out')
