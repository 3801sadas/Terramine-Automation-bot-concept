"""
Perception v2: exemplar NCC + edge-connectivity refinement.
Accumulates all ground-truth exemplars; handles LEP/POT on edges.
"""
import json, os, glob
import numpy as np
from PIL import Image

import tilegrid

ORDER=['N','E','S','W']
CALIB_PATH = r"C:\Users\Usernom\Documents\Terramine\calibration.json"
APK = r"C:\Users\Usernom\Downloads\TerraMine_+Real+World+Mining_1.1.45_APKPure"

def load_calib():
    with open(CALIB_PATH) as f: return json.load(f)
def S(s): return frozenset(s)

LABELS_JSON = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\labels\ground_truth.json"

def load_ground_truth():
    """Load labeled boards from the shared JSON label store."""
    if not os.path.exists(LABELS_JSON): return {}
    with open(LABELS_JSON, "r", encoding="utf-8") as f:
        doc = json.load(f)
    out = {}
    for board in doc.get("boards", []):
        img = board["image"]
        cells = {}
        for key, cell in board.get("cells", {}).items():
            r, c = [int(x) for x in key.split(",")]
            cells[(r, c)] = (cell.get("kind", "tile"), S(cell.get("sides", "")))
        out[img] = cells
    return out

def _prep(a):
    # keep near-edge road stubs visible (dead-ends/curves reach the cell border)
    h,w=a.shape[:2]; y0=int(h*0.05); y1=int(h*0.95); x0=int(w*0.05); x1=int(w*0.95)
    p=a[y0:y1,x0:x1]
    im=Image.fromarray(p.astype(np.uint8)).resize((48,48), Image.BILINEAR)
    v=np.array(im).astype(np.float32).flatten()
    sd=float(v.std())
    if sd < 4.0:
        # near-uniform patch -> identical grass texture everywhere; treat as grass template
        return np.zeros_like(v)
    v=(v-v.mean())/sd
    return v

_ex_cache = {}
def get_exemplars(exclude_path=None):
    key = exclude_path or "__all__"
    if key in _ex_cache: return _ex_cache[key]
    cal = load_calib(); L,T = cal["board"]["left"], cal["board"]["top"]; CW,CH = cal["board"]["cell_w"], cal["board"]["cell_h"]
    ex = {}
    for path, gt in load_ground_truth().items():
        if exclude_path and os.path.normcase(path)==os.path.normcase(exclude_path): continue
        if not os.path.exists(path): continue
        im = Image.open(path).convert("RGB"); arr=np.array(im).astype(np.float32)
        for (r,c),(kind,sides) in gt.items():
            if kind in ("LEP","POT"): continue
            x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
            sig = ''.join(sorted(sides)) if sides else '-'
            ex.setdefault(sig, []).append(_prep(arr[y0:y1,x0:x1]))
    _ex_cache[key] = ex
    return ex

def road_open(arr,r,c,L,T,CW,CH):
    # golden road mask; sample edge boundary + inner band
    R,G,B=arr[:,:,0],arr[:,:,1],arr[:,:,2]
    road = (R>195)&(G>145)&(B<90)
    x0=L+c*CW; y0=T+r*CH; x1=x0+CW; y1=y0+CH; cx=(x0+x1)/2; cy=(y0+y1)/2
    def f(a,b,c2,d):
        m=road[max(0,int(c2)):int(d),max(0,int(a)):int(b)]
        return float(m.mean()) if m.size else 0.0
    e = {
        'N':(f(cx-10,cx+10,y0+2,y0+11), f(cx-10,cx+10,y0+11,y0+28)),
        'E':(f(x1-11,x1-2,cy-10,cy+10), f(x1-28,x1-11,cy-10,cy+10)),
        'S':(f(cx-10,cx+10,y1-11,y1-2), f(cx-10,cx+10,y1-28,y1-11)),
        'W':(f(x0+2,x0+11,cy-10,cy+10), f(x0+11,x0+28,cy-10,cy+10)),
    }
    out=set()
    for d,(edge,inner) in e.items():
        # open if road reaches boundary and continues inward
        if edge>0.35 and inner>0.30: out.add(d)
        elif edge>0.55: out.add(d)
    return frozenset(out)

def classify_sides(arr, r,c, L,T,CW,CH, ex):
    x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
    v=_prep(arr[y0:y1,x0:x1])
    if not np.any(v):
        return frozenset(), 0.99  # uniform/grass cell
    scores=[]
    for sig,lst in ex.items():
        best=-1e9
        for pv in lst:
            s=float(np.dot(v,pv)/len(v))
            if s>best: best=s
        scores.append((best,sig))
    scores.sort(reverse=True)
    top_sig = scores[0][1] if scores else '-'
    top_sc = scores[0][0] if scores else -1
    ex_sides = frozenset() if top_sig=='-' else frozenset(top_sig)
    # edge refinement only for genuinely ambiguous, non-perfect matches
    if top_sc < 0.995 and scores and len(scores)>1 and (scores[0][0]-scores[1][0] < 0.015):
        ed = road_open(arr,r,c,L,T,CW,CH)
        for sc,sig in scores[:5]:
            cand = frozenset() if sig=='-' else frozenset(sig)
            if cand == ed: return cand, sc
    return ex_sides, top_sc

def detect_lep_pot(arr, geom):
    lep=None; pot=None
    L,T = geom["left"], geom["top"]; CW,CH = geom["cell_x"], geom["cell_y"]; n = int(geom["n"])
    # LEP: the leprechaun sprite has a large very-dark mass (hat/boots), unique on the board.
    # Search the left border columns; dark fraction is ~0.14 on the LEP cell, <0.01 elsewhere.
    for c in (0,1):
        for r in range(n):
            x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
            cell=arr[y0:y1,x0:x1]; R,G,B=cell[:,:,0],cell[:,:,1],cell[:,:,2]
            dark = float(((R<70)&(G<70)&(B<70)).mean())
            if dark > 0.05 and (lep is None or dark>lep[3]): lep=(r,c,"LEP",dark)
    if lep is None:  # fallback: green character
        for c in (0,1):
            for r in range(n):
                x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
                cell=arr[y0:y1,x0:x1]; R,G,B=cell[:,:,0],cell[:,:,1],cell[:,:,2]
                green = float(((G>R*1.08)&(G>B*1.05)&(G>70)&(R<150)).mean())
                if lep is None or green>lep[3]: lep=(r,c,"LEP",green)
    for r in range(n):
        for c in [n-1,n-2]:
            x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
            cell=arr[y0:y1,x0:x1]; R,G,B=cell[:,:,0],cell[:,:,1],cell[:,:,2]
            gold = float(((R>190)&(G>150)&(B<110)).mean())
            dark = float(((R<80)&(G<80)&(B<80)).mean())
            blackpot = float(((R<60)&(G<60)&(B<60)).mean())
            score = gold + dark*4 + blackpot*6 + (0.3 if c==n-1 else 0)
            if blackpot > 0.03 and (pot is None or score>pot[3]): pot=(r,c,"POT",score)
    if pot is None:
        for r in range(n):
            c=n-1
            x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
            cell=arr[y0:y1,x0:x1]; R,G,B=cell[:,:,0],cell[:,:,1],cell[:,:,2]
            gold = float(((R>190)&(G>150)&(B<110)).mean()); dark = float(((R<80)&(G<80)&(B<80)).mean())
            if pot is None or gold+dark*4>pot[3]: pot=(r,c,"POT",gold+dark*4)
    return lep, pot


def _inward_side(r, c, n):
    """Opening of a border LEP/POT tile: it always points into the board."""
    if c == 0: return "E"
    if c == n - 1: return "W"
    if r == 0: return "S"
    if r == n - 1: return "N"
    return "E" if c < n / 2 else "W"


def perceive(img_path, exclude_self=False, geom=None, n=None):
    """Perceive a board of any supported size (4x4, 5x5, 6x6, ...).

    The grid size comes from the drawn tile seams; the 6x6 exemplar classifier
    is used when available (it is the best-trained path) and the gold-road
    arm reader is used for every other size.
    """
    arr = np.array(Image.open(img_path).convert("RGB")).astype(np.float32)
    if geom is None:
        geom = tilegrid.detect_geometry(arr)
    if n is not None:
        geom = dict(geom, n=int(n))
    N = int(geom["n"])
    cal = load_calib()
    ex = get_exemplars(exclude_path=img_path if exclude_self else None) if N == 6 else {}
    # Keep the historical calibration rect for the 6x6 exemplar classifier:
    # the exemplars were harvested with it, so using the seam grid there would
    # shift every patch by ~10 px and regress a well-tested path.
    if N == 6 and ex:
        L, T = cal["board"]["left"], cal["board"]["top"]
        CW, CH = cal["board"]["cell_w"], cal["board"]["cell_h"]
        read_geom = {"n": 6, "left": L, "top": T, "cell_x": CW, "cell_y": CH}
    else:
        read_geom = geom
    lep, pot = detect_lep_pot(arr, read_geom)
    mask = tilegrid.road_mask(arr) if not ex else None
    grid = {}
    for r in range(N):
        for c in range(N):
            if ex:
                sides,conf = classify_sides(arr,r,c,read_geom["left"],read_geom["top"],
                                            read_geom["cell_x"],read_geom["cell_y"],ex)
            else:
                sides,conf,_vals = tilegrid.road_sides(mask,r,c,read_geom)
            if lep and (r,c)==(lep[0],lep[1]):
                grid[(r,c)] = ("LEP", frozenset(_inward_side(r,c,N)), conf)
            elif pot and (r,c)==(pot[0],pot[1]):
                grid[(r,c)] = ("POT", frozenset(_inward_side(r,c,N)), conf)
            else:
                kind = "grass" if not sides else "tile"
                grid[(r,c)] = (kind, sides, conf)
    return {"grid": grid, "lep": (lep[0],lep[1]) if lep else None,
            "pot": (pot[0],pot[1]) if pot else None,
            "n": N, "geom": geom, "cal": load_calib(), "arr": arr}

def format_grid(res):
    n = res.get("n", 6)
    lines=[f"LEP={res['lep']} POT={res['pot']} N={n}"]
    for r in range(n):
        row=[]
        for c in range(n):
            k,s,conf = res["grid"][(r,c)]
            sig=''.join(sorted(s)) if s else '-'
            row.append(f"{sig}")
        lines.append(f"r{r}: "+' | '.join(row))
    return '\n'.join(lines)

if __name__=="__main__":
    import sys
    p = sys.argv[1] if len(sys.argv)>1 else r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\fresh_01.png"
    excl = "--exclude" in sys.argv
    res = perceive(p, exclude_self=excl)
    print(format_grid(res))
