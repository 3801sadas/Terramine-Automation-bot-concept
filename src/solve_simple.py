"""
Simple-path solver (no cell revisits) for Gold Rush.

Cost = taps, 1 tap = 90 deg clockwise. A plan is only valid if the final
orientation of every cell can be achieved with its (cumulative) taps and the
resulting grid contains a LEP->POT path.
"""
import json, sys
from collections import deque
from perception_v2 import perceive

ORDER=['N','E','S','W']
OPP={'N':'S','E':'W','S':'N','W':'E'}
DIRS={'N':(-1,0),'E':(0,1),'S':(1,0),'W':(0,-1)}
VALID_BY_CLASS = {
 'str':[frozenset("NS"),frozenset("EW")],
 'curv':[frozenset("NE"),frozenset("ES"),frozenset("SW"),frozenset("NW")],
 'T':[frozenset("NES"),frozenset("ESW"),frozenset("SWN"),frozenset("NEW")],
 'cross':[frozenset("NESW")],
 'dead':[frozenset("N"),frozenset("E"),frozenset("S"),frozenset("W")],
 'grass':[frozenset()],
}

def sides_class(sides):
    n=len(sides)
    if n==0: return 'grass'
    if n==4: return 'cross'
    if n==3: return 'T'
    if n==1: return 'dead'
    if sides in (frozenset("NS"),frozenset("EW")): return 'str'
    return 'curv'

def cw(sides,n=1):
    for _ in range(n%4): sides=frozenset(ORDER[(ORDER.index(d)+1)%4] for d in sides)
    return sides

def min_taps(cls, cur, needed):
    """Min taps to get an orientation that covers `needed`, or None."""
    if cls in ('LEP','POT'):
        return (0, frozenset(needed))
    targets=VALID_BY_CLASS.get(cls)
    if targets is None: return None
    best=None
    for target in targets:
        if needed.issubset(target):
            for t in range(4):
                if cw(cur,t)==target:
                    if best is None or t<best[0]: best=(t,target)
                    break
    return best

def solve_simple(grid, LEP, POT, max_cost=48):
    best={'cost':max_cost+1,'path':None}
    lep_sides=grid[LEP][1]
    # infer grid size from keys
    rows = {r for r,_ in grid.keys()}
    cols = {c for _,c in grid.keys()}
    N = max(max(rows) + 1, max(cols) + 1)
    def in_bounds(r, c): return 0 <= r < N and 0 <= c < N

    def dfs(r,c,entry_dir,visited,cost,plan):
        if cost>=best['cost']: return
        kind,cur,_=grid[(r,c)]
        cls = kind if kind in ('LEP','POT') else sides_class(cur)
        cand_dirs = [d for d in ORDER if d in cur] if (r,c)==LEP else ORDER
        for d in cand_dirs:
            dr,dc=DIRS[d]; nr,nc=r+dr,c+dc
            if not in_bounds(nr,nc): continue
            if (nr,nc) in visited: continue
            needed={d}
            if entry_dir is not None: needed.add(OPP[entry_dir])
            if (r,c)==LEP:
                if not needed.issubset(cur): continue
                res=(0,cur)
            else:
                res=min_taps(cls,cur,needed)
            if res is None: continue
            t,new_sides=res
            nkind,nsides,_=grid[(nr,nc)]
            if (nr,nc)==POT:
                if nsides and OPP[d] not in nsides: continue
                if cost+t>=best['cost']: continue
                best['cost']=cost+t
                best['path']=list(plan)+[(r,c,t,new_sides)]
                continue
            ncls = nkind if nkind in ('LEP','POT') else sides_class(nsides)
            if ncls in ('LEP','POT'): continue
            # neighbor must have some orientation that includes the incoming side
            nres=min_taps(ncls,nsides,{OPP[d]})
            if nres is None: continue
            dfs(nr,nc,d,visited|{(nr,nc)},cost+t,plan+[(r,c,t,new_sides)])
    dfs(LEP[0],LEP[1],None,{LEP},0,[])
    return best if best['path'] else None

def apply_plan(grid, plan):
    taps={}
    for (r,c,t,_) in plan: taps[(r,c)]=taps.get((r,c),0)+t
    out={}
    for k,(kind,sides,_) in grid.items():
        if kind in ('LEP','POT'): out[k]=(kind,sides); continue
        ns=sides
        for _ in range(taps.get(k,0)%4): ns=cw(ns)
        out[k]=(kind,ns)
    return out

def path_exists(g, LEP, POT):
    # infer grid size
    rows = {r for r,_ in g.keys()}
    cols = {c for _,c in g.keys()}
    N = max(max(rows) + 1, max(cols) + 1)
    def in_bounds(r, c): return 0 <= r < N and 0 <= c < N
    q=deque([LEP]); seen={LEP}
    while q:
        r,c=q.popleft()
        kind,sides=g[(r,c)]
        if kind=='grass': continue
        for d in sides:
            dr,dc=DIRS[d]; nr,nc=r+dr,c+dc
            if not in_bounds(nr,nc): continue
            if (nr,nc) in seen: continue
            nk,ns=g[(nr,nc)]
            if nk not in ('LEP','POT') and OPP[d] not in ns: continue
            if nk in ('LEP','POT') and ns and OPP[d] not in ns: continue
            seen.add((nr,nc)); q.append((nr,nc))
    return POT in seen

def solve_and_validate(res):
    grid, LEP, POT = res['grid'], res['lep'], res['pot']
    sol=solve_simple(grid,LEP,POT)
    if not sol: return None
    g=apply_plan(grid,sol['path'])
    if not path_exists(g,LEP,POT):
        return None
    return sol, g

if __name__=="__main__":
    img = sys.argv[1] if len(sys.argv)>1 else r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\fresh_04.png"
    res=perceive(img)
    out=solve_and_validate(res)
    if not out:
        print("NO VALID SIMPLE-PATH SOLUTION"); sys.exit(1)
    sol,g=out
    print("LEP",res['lep'],"POT",res['pot'],"cost",sol['cost'])
    for (r,c,t,ts) in sol['path']:
        print(f" ({r},{c}) taps={t} -> {''.join(x for x in 'NESW' if x in ts)}")
    # Use the geom from perception for tap centres (works for any grid size)
    geom = res.get('geom', res['cal']['board'])
    L,T = geom['left'], geom['top']
    CW,CH = geom['cell_x'], geom['cell_y']
    seq=[]
    for (r,c,t,ts) in sol['path']:
        for _ in range(t):
            seq.append({"r":r,"c":c,"x":int(round(L+c*CW+CW/2)),"y":int(round(T+r*CH+CH/2))})
    print("VALIDATED: True")
    print("TAPS_JSON="+json.dumps(seq))
    print("TOTAL_TAPS="+str(len(seq)))
