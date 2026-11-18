import json
from heapq import heappush, heappop
from ground_truth import GT, LEP, POT

ORDER=['N','E','S','W']
OPP={'N':'S','E':'W','S':'N','W':'E'}
DIRS={'N':(-1,0),'E':(0,1),'S':(1,0),'W':(0,-1)}  # (dr,dc) in (row,col)
VALID = {
 'grass':[frozenset()],
 'str':[frozenset("NS"),frozenset("EW")],
 'curv':[frozenset("NE"),frozenset("ES"),frozenset("SW"),frozenset("WN")],
 'T':[frozenset("NES"),frozenset("ESW"),frozenset("SWN"),frozenset("WNE")],
 'cross':[frozenset("NESW")],
 'dead':[frozenset("N"),frozenset("E"),frozenset("S"),frozenset("W")],
 'LEP':[frozenset("N"),frozenset("E"),frozenset("S"),frozenset("W")],
 'POT':[frozenset("N"),frozenset("E"),frozenset("S"),frozenset("W")],
}

def cw(sides, n=1):
    for _ in range(n%4):
        sides=frozenset(ORDER[(ORDER.index(d)+1)%4] for d in sides)
    return sides

def taps_to_achieve(kind, cur_sides, needed):
    best=None
    for target in VALID[kind]:
        if needed.issubset(target):
            # find taps: try 0-3 from cur
            for t in range(4):
                if cw(cur_sides,t)==target:
                    if best is None or t<best[0]: best=(t,target)
                    break
    return best  # (taps, target_sides) or None

# Dijkstra: (cost,r,c,entry_dir_idx_or_-1)
INF=10**9
dist={}
pq=[]
heappush(pq,(0,LEP[0],LEP[1],-1))
dist[(LEP[0],LEP[1],-1)]=0
parent={}
goal=None
while pq:
    cost,r,c,ed = heappop(pq)
    if (r,c)==POT: goal=(r,c,ed); break
    if dist.get((r,c,ed),INF)<cost: continue
    kind,cur = GT[(r,c)]
    for di,d in enumerate(ORDER):
        dr,dc=DIRS[d]; nr,nc=r+dr,c+dc
        if not (0<=nr<6 and 0<=nc<6): continue
        needed={d}
        if ed!=-1: needed.add(OPP[ORDER[ed]])
        res=taps_to_achieve(kind,cur,needed)
        if not res: continue
        t_cost,_=res
        ncost=cost+t_cost
        key=(nr,nc,di)
        if ncost<dist.get(key,INF):
            dist[key]=ncost; parent[key]=(r,c,ed,t_cost,res[1]); heappush(pq,(ncost,nr,nc,di))

if not goal:
    print("NO SOLUTION")
else:
    print("COST", dist[goal])
    path=[]; cur=goal
    while cur!=(LEP[0],LEP[1],-1):
        pr,pc,ped,tc,ts = parent[cur]
        path.append((pr,pc,tc,ts))
        cur=(pr,pc,ped)
    path.reverse()
    print("PATH_TAPS (r,c,taps,target_sides):")
    for p in path: print(f"  ({p[0]},{p[1]}) taps={p[2]} -> {''.join(sorted(p[3]))}")
    print("TAP_LIST:")
    with open(CALIB:=r"C:\Users\Usernom\Documents\Terramine\calibration.json") as f: cal=json.load(f)
    L,T=cal["board"]["left"],cal["board"]["top"]; cw,ch=cal["board"]["cell_w"],cal["board"]["cell_h"]
    taps=[]
    for (r,c,tc,_) in path:
        for _ in range(tc): taps.append((r,c,int(round(L+c*cw+cw/2)),int(round(T+r*ch+ch/2))))
    print(json.dumps([{"r":r,"c":c,"x":x,"y":y} for r,c,x,y in taps]))
    print(f"TOTAL_TAPS={len(taps)}")
