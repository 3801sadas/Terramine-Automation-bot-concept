"""
Perception for Gold Rush: classify each 6x6 cell's open sides from a screenshot.
Uses screenshot exemplars from ground-truth boards + LEP/POT sprite detection.
Game-accurate base types confirmed from Hermes bundle (HBC v96, TerraMine 1.1.45).
"""
import json, os
import numpy as np
from PIL import Image

ORDER=['N','E','S','W']
OPP={'N':'S','E':'W','S':'N','W':'E'}
DIRS={'N':(-1,0),'E':(0,1),'S':(1,0),'W':(0,-1)}
BASE = { # from bundle
  "straight": frozenset("NS"),
  "curve": frozenset("ES"),
  "t-junction": frozenset("NEW"),
  "cross": frozenset("NESW"),
  "dead-end": frozenset("S"),
  "grass": frozenset(""),
}
def cw(sides,n=1):
    for _ in range(n%4): sides=frozenset(ORDER[(ORDER.index(d)+1)%4] for d in sides)
    return sides

CALIB_PATH = r"C:\Users\Usernom\Documents\Terramine\calibration.json"
def load_calib():
    with open(CALIB_PATH) as f: return json.load(f)

# --- ground truth exemplars ---
def S(s): return frozenset(s)
GT = {
 r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\run_01.png": {
  (0,0):("grass",S("")),(0,1):("curv",S("NW")),(0,2):("curv",S("NE")),(0,3):("grass",S("")),(0,4):("dead",S("S")),(0,5):("grass",S("")),
  (1,0):("LEP",S("E")),(1,1):("curv",S("SW")),(1,2):("curv",S("NW")),(1,3):("str",S("NS")),(1,4):("curv",S("NE")),(1,5):("grass",S("")),
  (2,0):("grass",S("")),(2,1):("grass",S("")),(2,2):("curv",S("SW")),(2,3):("str",S("NS")),(2,4):("curv",S("SW")),(2,5):("POT",S("W")),
  (3,0):("grass",S("")),(3,1):("str",S("EW")),(3,2):("curv",S("NW")),(3,3):("dead",S("E")),(3,4):("str",S("NS")),(3,5):("grass",S("")),
  (4,0):("grass",S("")),(4,1):("grass",S("")),(4,2):("grass",S("")),(4,3):("dead",S("W")),(4,4):("grass",S("")),(4,5):("grass",S("")),
  (5,0):("grass",S("")),(5,1):("str",S("EW")),(5,2):("grass",S("")),(5,3):("grass",S("")),(5,4):("curv",S("NW")),(5,5):("dead",S("N")),
 },
 r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\fresh_01.png": {
  (0,0):("grass",S("")),(0,1):("dead",S("E")),(0,2):("curv",S("SW")),(0,3):("str",S("NS")),(0,4):("curv",S("NE")),(0,5):("grass",S("")),
  (1,0):("grass",S("")),(1,1):("grass",S("")),(1,2):("str",S("EW")),(1,3):("grass",S("")),(1,4):("str",S("EW")),(1,5):("grass",S("")),
  (2,0):("LEP",S("E")),(2,1):("str",S("NS")),(2,2):("curv",S("ES")),(2,3):("curv",S("NW")),(2,4):("curv",S("NE")),(2,5):("grass",S("")),
  (3,0):("grass",S("")),(3,1):("str",S("NS")),(3,2):("str",S("EW")),(3,3):("curv",S("NW")),(3,4):("curv",S("ES")),(3,5):("grass",S("")),
  (4,0):("grass",S("")),(4,1):("str",S("NS")),(4,2):("curv",S("ES")),(4,3):("curv",S("NW")),(4,4):("curv",S("NE")),(4,5):("grass",S("")),
  (5,0):("grass",S("")),(5,1):("str",S("EW")),(5,2):("str",S("EW")),(5,3):("curv",S("SW")),(5,4):("str",S("NS")),(5,5):("POT",S("")), # open side TBD; detect
 },
}

def _prep(a):
    h,w=a.shape[:2]; y0=int(h*0.18); y1=int(h*0.82); x0=int(w*0.18); x1=int(w*0.82)
    p=a[y0:y1,x0:x1]
    im=Image.fromarray(p.astype(np.uint8)).resize((48,48), Image.BILINEAR)
    v=np.array(im).astype(np.float32).flatten()
    v=(v-v.mean())/(v.std()+1e-6)
    return v

_ex_cache = {}
def get_exemplars(exclude_path=None):
    key = exclude_path or "__all__"
    if key in _ex_cache: return _ex_cache[key]
    cal = load_calib(); L,T = cal["board"]["left"], cal["board"]["top"]; CW,CH = cal["board"]["cell_w"], cal["board"]["cell_h"]
    ex = {}
    for path, gt in GT.items():
        if exclude_path and os.path.normcase(path)==os.path.normcase(exclude_path): continue
        if not os.path.exists(path): continue
        im = Image.open(path).convert("RGB"); arr=np.array(im).astype(np.float32)
        for (r,c),(kind,sides) in gt.items():
            if kind in ("LEP","POT"): continue # handle separately
            x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
            sig = ''.join(sorted(sides)) if sides else '-'
            ex.setdefault(sig, []).append(_prep(arr[y0:y1,x0:x1]))
    _ex_cache[key] = ex
    return ex

def classify_sides(arr, r,c, L,T,CW,CH, ex):
    x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
    v=_prep(arr[y0:y1,x0:x1])
    best=(-1e9,None)
    for sig,lst in ex.items():
        for pv in lst:
            s=float(np.dot(v,pv)/len(v))
            if s>best[0]: best=(s,sig)
    sig = best[1] or '-'
    return frozenset() if sig=='-' else frozenset(sig), best[0]

APK = r"C:\Users\Usernom\Downloads\TerraMine_+Real+World+Mining_1.1.45_APKPure"
_sprite_cache = {}
def _sprite_template(name):
    if name in _sprite_cache: return _sprite_cache[name]
    paths = {
        "LEP": os.path.join(APK, "res","drawable-mdpi","assets_images_goldmine_leprechaunidle.png"),
        "POT": os.path.join(APK, "res","drawable-mdpi","assets_images_goldmine_potofgold.png"),
    }
    p = paths[name]
    im = Image.open(p).convert("RGBA")
    # scale to roughly cell size
    sz = 140
    im = im.resize((sz,sz), Image.LANCZOS)
    a = np.array(im).astype(np.float32)
    rgb = a[:,:,:3]; alpha = a[:,:,3]/255.0
    # premultiply-like: use alpha to mask; create grayscale-ish feature emphasizing subject
    gray = (0.299*rgb[:,:,0]+0.587*rgb[:,:,1]+0.114*rgb[:,:,2])
    mask = alpha > 0.2
    _sprite_cache[name] = (gray, mask, sz)
    return _sprite_cache[name]

def _ncc_masked(search_gray, tpl_gray, tpl_mask):
    # NCC over masked pixels
    tg = tpl_gray[tpl_mask]; sg = search_gray[tpl_mask]
    tg = tg - tg.mean(); sg = sg - sg.mean()
    denom = (np.sqrt((tg*tg).sum()) * np.sqrt((sg*sg).sum()) + 1e-6)
    return float((tg*sg).sum()/denom)

def detect_lep_pot(arr, L,T,CW,CH):
    # Edge-based: LEP is on left edge (col 0 primarily), POT on right edge (col 5 primarily).
    # Leprechaun: green character sprite. Pot of gold: dark cauldron + bright gold.
    lep=None; pot=None
    for r in range(6):
        c=0
        x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
        cell=arr[y0:y1,x0:x1]; R,G,B=cell[:,:,0],cell[:,:,1],cell[:,:,2]
        green = float(((G>R*1.08)&(G>B*1.05)&(G>70)&(R<150)).mean())
        # skin/brown tones also present, but green hat is distinctive
        score = green
        if lep is None or score>lep[3]: lep=(r,c,"LEP",score)
    # also check col 1 just in case
    for r in range(6):
        c=1
        x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
        cell=arr[y0:y1,x0:x1]; R,G,B=cell[:,:,0],cell[:,:,1],cell[:,:,2]
        green = float(((G>R*1.08)&(G>B*1.05)&(G>70)&(R<150)).mean())
        if green > (lep[3] if lep else 0) + 0.03: lep=(r,c,"LEP",green)
    # POT: dark cauldron + gold is distinctive; road tiles have gold but almost no very-dark mass
    for r in range(6):
        for c in [5,4]:
            x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
            cell=arr[y0:y1,x0:x1]; R,G,B=cell[:,:,0],cell[:,:,1],cell[:,:,2]
            gold = float(((R>190)&(G>150)&(B<110)).mean())
            dark = float(((R<80)&(G<80)&(B<80)).mean())
            blackpot = float(((R<60)&(G<60)&(B<60)).mean())
            score = gold + dark*4 + blackpot*6 + (0.3 if c==5 else 0)
            if blackpot > 0.03 and (pot is None or score>pot[3]): pot=(r,c,"POT",score)
    if pot is None: # fallback
        for r in range(6):
            c=5
            x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
            cell=arr[y0:y1,x0:x1]; R,G,B=cell[:,:,0],cell[:,:,1],cell[:,:,2]
            gold = float(((R>190)&(G>150)&(B<110)).mean()); dark = float(((R<80)&(G<80)&(B<80)).mean())
            score = gold + dark*4
            if pot is None or score>pot[3]: pot=(r,c,"POT",score)
    return lep, pot

def perceive(img_path, exclude_self=False):
    cal = load_calib(); L,T = cal["board"]["left"], cal["board"]["top"]; CW,CH = cal["board"]["cell_w"], cal["board"]["cell_h"]
    arr = np.array(Image.open(img_path).convert("RGB")).astype(np.float32)
    ex = get_exemplars(exclude_path=img_path if exclude_self else None)
    lep, pot = detect_lep_pot(arr,L,T,CW,CH)
    grid = {}
    for r in range(6):
        for c in range(6):
            sides,conf = classify_sides(arr,r,c,L,T,CW,CH,ex)
            if lep and (r,c)==(lep[0],lep[1]):
                # LEP is rotatable single-exit; keep detected if plausible else flexible marker
                grid[(r,c)] = ("LEP", sides if len(sides)==1 else (frozenset("E") if c==0 else frozenset("W") if c==5 else frozenset("E")), conf)
            elif pot and (r,c)==(pot[0],pot[1]):
                grid[(r,c)] = ("POT", sides if len(sides)==1 else (frozenset("W") if c==5 else frozenset("E") if c==0 else frozenset("W")), conf)
            else:
                kind = "grass" if not sides else "tile"
                grid[(r,c)] = (kind, sides, conf)
    return {"grid": grid, "lep": (lep[0],lep[1]) if lep else None, "pot": (pot[0],pot[1]) if pot else None, "cal": cal}

if __name__=="__main__":
    import sys
    p = sys.argv[1] if len(sys.argv)>1 else r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\fresh_01.png"
    excl = "--exclude" in sys.argv
    res = perceive(p, exclude_self=excl)
    print("LEP", res["lep"], "POT", res["pot"])
    for r in range(6):
        row=[]
        for c in range(6):
            k,s,conf = res["grid"][(r,c)]
            sig=''.join(sorted(s)) if s else '-'
            row.append(f"{k[:3]}:{sig}")
        print(f"r{r}:"," | ".join(row))


if __name__=="__main__":
    import sys
    p = sys.argv[1] if len(sys.argv)>1 else r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\fresh_01.png"
    res = perceive(p)
    print("LEP", res["lep"], "POT", res["pot"])
    for r in range(6):
        row=[]
        for c in range(6):
            k,s,conf = res["grid"][(r,c)]
            sig=''.join(sorted(s)) if s else '-'
            row.append(f"{k[:3]}:{sig}")
        print(f"r{r}:"," | ".join(row))
