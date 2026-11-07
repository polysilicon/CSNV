import sys,json,math,os
from PIL import Image
P='/tmp/claude-0/-home-user-CSNV/c6f73eb8-1ab1-54f0-8c26-8516bedafa4b/scratchpad/'
src=open(P+'region_top.py').read().split('world=sys.argv[1]')[0]; exec(src)
CX,CZ,BPP=0,-15,4                      # map centre and blocks per pixel (128 px -> 512 blocks)
X0,Z0=CX-64*BPP,CZ-64*BPP
top={}
for rf in sorted(os.listdir(P+'oldworld/market')):
    for ch in chunks(P+'oldworld/market/'+rf):
        cx,cz=ch['xPos'],ch['zPos']
        if not (X0-16<=cx*16<X0+512 and Z0-16<=cz*16<Z0+512): continue
        for (x,z),(nm,y) in top_blocks(ch).items(): top[(cx*16+x,cz*16+z)]=(y,nm.replace('minecraft:',''))
print('columns',len(top))
import pickle; pickle.dump(top,open(P+'mapart/top.pkl','wb'))
