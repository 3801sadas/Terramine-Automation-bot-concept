import json
from heapq import heappush, heappop

ORDER=['N','E','S','W']
OPP={'N':'S','E':'W','S':'N','W':'E'}
DIRS={'N':(-1,0),'E':(0,1),'S':(1,0),'W':(0,-1)}
VALID = {
 'grass':[frozenset()],
 'str':[frozenset("NS"),frozenset("EW")],
 'curv':[frozenset("NE"),frozenset("ES"),frozenset("SW"),frozenset("NW")],
 'T':[frozenset("NES"),frozenset("ESW"),frozenset("SWN"),frozenset("WNE")],
 'cross':[frozenset("NESW")],
 'dead':[frozenset("N"),frozenset("E"),frozenset("S"),frozenset("W")],
 'LEP':[frozenset("N"),frozenset("E"),frozenset("S"),frozenset("W")],
 'POT':[frozenset("N"),frozenset("E"),frozenset("S"),frozenset("W")],
}
def cw(sides,n=1):
    for _ in range(n%4): sides=frozenset(ORDER[(ORDER.index(d)+1)%4] for d in sides)
    return sides
def taps_to_achieve(kind,cur,needed):
    best=None
    for target in VALID[kind]:
        if needed.issubset(target):
            for t in range(4):
                if cw(cur,t)==target:
                    if best is None or t<best[0]: best=(t,target); break
    return best

def S(s): return frozenset(s)
GT = {
(0,0):("grass",S("")),(0,1):("dead",S("E")),(0,2):("curv",S("SW")),(0,3):("str",S("NS")),(0,4):("curv",S("NE")),(0,5):("grass",S("")),
(1,0):("grass",S("")),(1,1):("grass",S("")),(1,2):("str",S("EW")),(1,3):("grass",S("")),(1,4):("str",S("EW")),(1,5):("grass",S("")),
(2,0):("LEP",S("E")),(2,1):("str",S("NS")),(2,2):("curv",S("ES")),(2,3):("curv",S("NW")),(2,4):("curv",S("NE")),(2,5):("grass",S("")),
(3,0):("grass",S("")),(3,1):("str",S("NS")),(3,2):("str",S("EW")),(3,3):("curv",S("NW")),(3,4):("curv",S("ES")),(3,5):("grass",S("")),
(4,0):("grass",S("")),(4,1):("str",S("NS")),(4,2):("curv",S("ES")),(4,3):("curv",S("NW")),(4,4):("curv",S("NE")),(4,5):("grass",S("")),
(5,0):("grass",S("")),(5,1):("str",S("EW")),(5,2):("str",S("EW")),(5,3):("curv",S("SW")),(5,4):("str",S("NS")),(5,5):("POT",S("N")),
}
LEP=(2,0); POT=(5,5)
INF=10**9; dist={}; pq=[]; heappush(pq,(0,LEP[0],LEP[1],-1)); dist[(LEP[0],LEP[1],-1)]=0; parent={}; goal=None
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
        t_cost,_=res; ncost=cost+t_cost; key=(nr,nc,di)
        if ncost<dist.get(key,INF): dist[key]=ncost; parent[key]=(r,c,ed,t_cost,res[1]); heappush(pq,(ncost,nr,nc,di))
if not goal: print("NO SOLUTION")
else:
    print("COST", dist[goal])
    path=[]; cur=goal
    while cur!=(LEP[0],LEP[1],-1):
        pr,pc,ped,tc,ts=parent[cur]; path.append((pr,pc,tc,ts)); cur=(pr,pc,ped)
    path.reverse()
    print("PATH:")
    for p in path: print(f"  ({p[0]},{p[1]}) taps={p[2]} -> {''.join(sorted(p[3]))}")
    with open(r"C:\Users\Usernom\Documents\Terramine\calibration.json") as f: cal=json.load(f)
    L,T=cal["board"]["left"],cal["board"]["top"]; cw,ch=cal["board"]["cell_w"],cal["board"]["cell_h"]
    taps=[]
    for (r,c,tc,_) in path:
        for _ in range(tc): taps.append((r,c,int(round(L+c*cw+cw/2)),int(round(T+r*ch+ch/2))))
    print("TAPS_JSON="+json.dumps([{"r":r,"c":c,"x":x,"y":y} for r,c,x,y in taps]))
    print("TOTAL_TAPS="+str(len(taps)))
