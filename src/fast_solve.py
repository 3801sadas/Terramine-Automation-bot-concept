import json
from collections import deque
from heapq import heappush, heappop
from PIL import Image
import numpy as np

IMG = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\run_01.png"
CALIB = r"C:\Users\Usernom\Documents\Terramine\calibration.json"
with open(CALIB) as f: cal = json.load(f)
L,T = cal["board"]["left"], cal["board"]["top"]
cw,ch = cal["board"]["cell_w"], cal["board"]["cell_h"]

im = np.array(Image.open(IMG).convert("RGB")).astype(np.float32)
R,G,B = im[:,:,0], im[:,:,1], im[:,:,2]
# Bright road interior (light golden path) vs tile frame
mask = (R > 200) & (G > 150) & (B < 80)

def frac(x0,x1,y0,y1):
    a=mask[max(0,int(y0)):int(y1),max(0,int(x0)):int(x1)]
    return float(a.mean()) if a.size else 0.0

def detect_sides(r,c):
    x0=L+c*cw; x1=x0+cw; y0=T+r*ch; y1=y0+ch
    cx=(x0+x1)/2; cy=(y0+y1)/2
    # Check edge connectivity: road must be present at boundary AND extend inward
    def edge(frac_fn, frac_in_fn):
        return frac_fn() > 0.25 and frac_in_fn() > 0.15
    u = 1.0 if edge(lambda: frac(cx-10,cx+10,y0+1,y0+8), lambda: frac(cx-10,cx+10,y0+8,y0+30)) else 0.0
    rt = 1.0 if edge(lambda: frac(x1-8,x1-1,cy-10,cy+10), lambda: frac(x1-30,x1-8,cy-10,cy+10)) else 0.0
    d = 1.0 if edge(lambda: frac(cx-10,cx+10,y1-8,y1-1), lambda: frac(cx-10,cx+10,y1-30,y1-8)) else 0.0
    l = 1.0 if edge(lambda: frac(x0+1,x0+8,cy-10,cy+10), lambda: frac(x0+8,x0+30,cy-10,cy+10)) else 0.0
    return {k for k,v in {'N':u,'E':rt,'S':d,'W':l}.items() if v>0.5}

ORDER=['N','E','S','W']
OPP={'N':'S','E':'W','S':'N','W':'E'}
DIRS={'N':(-1,0),'E':(0,1),'S':(1,0),'W':(0,-1)}

# classify tile type from open sides
def classify(sides):
    n=len(sides)
    if n==0: return 'grass', 0
    if n==4: return 'cross', 0
    if n==3: 
        # T-junction: missing one side
        for i,d in enumerate(ORDER):
            if d not in sides: return 't', i  # rotation = which side is closed, relative to base
        return 't',0
    if n==2:
        s=sorted(sides, key=lambda d:ORDER.index(d))
        # straight if opposite
        if sides=={'N','S'} or sides=={'E','W'}:
            return 'straight', 0 if sides=={'N','S'} else 1
        # curve: adjacent
        pairs=[({'N','E'},0),({'E','S'},1),({'S','W'},2),({'W','N'},3)]
        for p,rot in pairs:
            if sides==p: return 'curve', rot
        return 'curve', 0
    if n==1:
        d=list(sides)[0]
        return 'deadend', ORDER.index(d)
    return 'grass', 0

def rot_sides(tile, rot):
    base={'grass':set(),'straight':{'N','S'},'curve':{'N','E'},'t':{'N','E','S'},'cross':{'N','E','S','W'},'deadend':{'N'}}
    b=base.get(tile,set())
    out=set()
    for d in b: out.add(ORDER[(ORDER.index(d)+rot)%4])
    return out

board={}
for r in range(6):
    for c in range(6):
        s=detect_sides(r,c)
        t,rot=classify(s)
        board[(r,c)]={'sides':s,'tile':t,'rot':rot}

# find start/goal: lep on left col area, pot on right col area
# use image heuristics + position
imc=np.array(Image.open(IMG).convert('RGB')).astype(np.float32)
lep=pot=None
best_lep=best_pot=-1
for r in range(6):
    for c in range(6):
        x0=int(round(L+c*cw)); y0=int(round(T+r*ch))
        reg=imc[y0:y0+168,x0:x0+168]
        if reg.size==0: continue
        gold=((reg[:,:,0]>200)&(reg[:,:,1]>150)&(reg[:,:,2]<80)).sum()
        # pot is bright golden and usually on right
        if c>=4 and gold>best_pot: best_pot=gold; pot=(r,c)
        # lep: has green/dark elements, on left
        non_bg=((reg[:,:,0]-reg[:,:,1]).__abs__()>20).sum()
        if c<=1 and non_bg>best_lep and (r,c)!=pot: best_lep=non_bg; lep=(r,c)
if lep is None: lep=(0,0)
if pot is None: pot=(5,5)
# adjust if lep/pot landed on cells that look like empty due to overlay
print(f"lep={lep} pot={pot}")
for (r,c),v in sorted(board.items()):
    print(f"  ({r},{c}) {v['tile']} rot={v['rot']} sides={sorted(v['sides'])}")

# Find path allowing rotations: Dijkstra on (r,c, entry_dir_concept simplified)
# State: (r,c). Cost = taps to orient current tile to connect from prev and to next.
# We need to know: to traverse edge (r,c)--d-->(nr,nc), (r,c) must have d open, (nr,nc) must have OPP[d] open.
# Cost for (r,c) = min over orientations that include required sides: (rot_needed - cur_rot)%4
# This is path-dependent. Use Dijkstra with state = (r,c, came_from_dir) - still complex.
# Simplified: try to find any path where we can rotate tiles (cost = sum of rotations needed).
# For each tile, precompute cost to have any given set of sides? Easier: try all 4 rotations.

def taps_to_have(tile, cur_rot, needed_sides):
    """min taps (CW) to make tile open include all needed_sides"""
    if not needed_sides: return 0, cur_rot
    best=(99,cur_rot)
    for add in range(4):
        nr=(cur_rot+add)%4
        if needed_sides.issubset(rot_sides(tile,nr)):
            if add<best[0]: best=(add,nr)
    return best

# Dijkstra: (cost, r,c, prev_dir_or_None)
# We track min cost to reach (r,c) having entered from some direction
INF=10**9
dist={}
pq=[]
# start: can exit in any direction the start tile can open (with rotations)
start_sides_ok=set()
for rot in range(4):
    pass
# try starting by treating start as passable
for start_rot in range(4):
    t=board[lep]['tile']; cost=(start_rot-board[lep]['rot'])%4
    if (cost,lep,start_rot) < (dist.get((lep,), (INF,))[0] if False else (INF,)):
        pass
heappush(pq,(0,lep[0],lep[1],-1))  # -1 = start
dist[(lep[0],lep[1],-1)]=0
parent={}
goal_state=None
while pq:
    cost,r,c,pd = heappop(pq)
    if (r,c)==pot: goal_state=(r,c,pd); break
    if dist.get((r,c,pd),INF)<cost: continue
    tile=board[(r,c)]['tile']; cur_rot=board[(r,c)]['rot']
    # try each exit direction
    for di,d in enumerate(ORDER):
        dr,dc=DIRS[d]; nr,nc=r+dr,c+dc
        if not (0<=nr<6 and 0<=nc<6): continue
        # need this tile to open d, and if came from pd, also open OPP[pd]
        needed={d}
        if pd!=-1: needed.add(OPP[ORDER[pd]])
        t_cost, new_rot = taps_to_have(tile, cur_rot, needed)
        ncost=cost+t_cost
        nd=di
        key=(nr,nc,nd)
        if ncost < dist.get(key,INF):
            dist[key]=ncost
            parent[key]=(r,c,pd,new_rot,t_cost)
            heappush(pq,(ncost,nr,nc,nd))

taps=[]
if goal_state:
    # reconstruct
    path=[]
    cur=goal_state
    while cur in parent or (cur[0],cur[1])==lep:
        if cur in parent:
            pr,pc,ppd,nrot,tc = parent[cur]
            path.append((pr,pc,tc))
            cur=(pr,pc,ppd)
        else:
            break
    path.reverse()
    print("SOLUTION cost", dist[goal_state], "path_taps:", path)
    for (r,c,tc) in path:
        for _ in range(tc):
            taps.append((r,c))
else:
    print("NO SOLUTION FOUND by Dijkstra")
    # fallback: try rotating likely-blocking tiles
    for r in range(6):
        for c in range(2,5):  # middle columns
            if board[(r,c)]['tile']!='grass': taps.append((r,c))

print("TAPS:", json.dumps([{"r":r,"c":c,"x":int(round(L+c*cw+cw/2)),"y":int(round(T+r*ch+ch/2))} for r,c in taps[:48]]))
