import json, os
import numpy as np
from PIL import Image, ImageDraw

CALIB = r"C:\Users\Usernom\Documents\Terramine\calibration.json"
with open(CALIB) as f: cal = json.load(f)
L,T = cal["board"]["left"], cal["board"]["top"]
CW,CH = cal["board"]["cell_w"], cal["board"]["cell_h"]

def S(s): return frozenset(s)
GT_RUN01 = {
(0,0):("grass",S("")),(0,1):("curv",S("NW")),(0,2):("curv",S("NE")),(0,3):("grass",S("")),(0,4):("dead",S("S")),(0,5):("grass",S("")),
(1,0):("LEP",S("E")),(1,1):("curv",S("SW")),(1,2):("curv",S("NW")),(1,3):("str",S("NS")),(1,4):("curv",S("NE")),(1,5):("grass",S("")),
(2,0):("grass",S("")),(2,1):("grass",S("")),(2,2):("curv",S("SW")),(2,3):("str",S("NS")),(2,4):("curv",S("SW")),(2,5):("POT",S("W")),
(3,0):("grass",S("")),(3,1):("str",S("EW")),(3,2):("curv",S("NW")),(3,3):("dead",S("E")),(3,4):("str",S("NS")),(3,5):("grass",S("")),
(4,0):("grass",S("")),(4,1):("grass",S("")),(4,2):("grass",S("")),(4,3):("dead",S("W")),(4,4):("grass",S("")),(4,5):("grass",S("")),
(5,0):("grass",S("")),(5,1):("str",S("EW")),(5,2):("grass",S("")),(5,3):("grass",S("")),(5,4):("curv",S("NW")),(5,5):("dead",S("N")),
}
GT_FRESH = {
(0,0):("grass",S("")),(0,1):("dead",S("E")),(0,2):("curv",S("SW")),(0,3):("str",S("NS")),(0,4):("curv",S("NE")),(0,5):("grass",S("")),
(1,0):("grass",S("")),(1,1):("grass",S("")),(1,2):("str",S("EW")),(1,3):("grass",S("")),(1,4):("str",S("EW")),(1,5):("grass",S("")),
(2,0):("LEP",S("E")),(2,1):("str",S("NS")),(2,2):("curv",S("ES")),(2,3):("curv",S("NW")),(2,4):("curv",S("NE")),(2,5):("grass",S("")),
(3,0):("grass",S("")),(3,1):("str",S("NS")),(3,2):("str",S("EW")),(3,3):("curv",S("NW")),(3,4):("curv",S("ES")),(3,5):("grass",S("")),
(4,0):("grass",S("")),(4,1):("str",S("NS")),(4,2):("curv",S("ES")),(4,3):("curv",S("NW")),(4,4):("curv",S("NE")),(4,5):("grass",S("")),
(5,0):("grass",S("")),(5,1):("str",S("EW")),(5,2):("str",S("EW")),(5,3):("curv",S("SW")),(5,4):("str",S("NS")),(5,5):("POT",S("N")),
}

# game-accurate base types (from Hermes)
BASE = {
  "straight": S("NS"),
  "curve": S("ES"),       # S,E
  "t-junction": S("NEW"), # N,E,W
  "cross": S("NESW"),
  "dead-end": S("S"),
  "grass": S(""),
}
ORDER=['N','E','S','W']
def cw(sides,n=1):
    for _ in range(n%4): sides=frozenset(ORDER[(ORDER.index(d)+1)%4] for d in sides)
    return sides
# map kind+open sides to (base_type, rotation_taps_cw_from_base)
def sides_to_type(sides):
    if not sides: return ("grass",0)
    for t,b in BASE.items():
        if t=="grass": continue
        for r in range(4):
            if cw(b,r)==sides: return (t,r)
    return ("unknown",0)

# build exemplars from ground truth: key by open-sides signature (ignore LEP/POT overlay? still useful)
exemplars = {}  # sig -> list of (img_array, source)
def add_exemplars(img_path, gt):
    im = Image.open(img_path).convert("RGB")
    arr = np.array(im).astype(np.float32)
    for (r,c),(kind,sides) in gt.items():
        # skip LEP/POT for clean exemplars? keep but note
        x0=int(round(L+c*CW)); y0=int(round(T+r*CH))
        x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
        crop = arr[y0:y1,x0:x1]
        sig = ''.join(sorted(sides)) if sides else '-'
        exemplars.setdefault(sig, []).append((crop, kind, r,c,img_path))

add_exemplars(r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\run_01.png", GT_RUN01)
add_exemplars(r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\fresh_01.png", GT_FRESH)
print("exemplar sigs:", sorted(exemplars.keys()))
for k,v in sorted(exemplars.items()):
    print(f"  {k}: {len(v)}")

# test: classify each cell by nearest exemplar (center-weighted NCC on downscaled interior)
def prep(a):
    # interior 60%
    h,w=a.shape[:2]; y0=int(h*0.2); y1=int(h*0.8); x0=int(w*0.2); x1=int(w*0.8)
    p=a[y0:y1,x0:x1]
    # downscale
    im=Image.fromarray(p.astype(np.uint8)).resize((48,48), Image.BILINEAR)
    v=np.array(im).astype(np.float32).flatten()
    v=(v-v.mean())/(v.std()+1e-6)
    return v

ex_prep = {k:[(prep(x[0]),x[1]) for x in v] for k,v in exemplars.items()}

def classify(img_path, gt, name):
    im = Image.open(img_path).convert("RGB")
    arr = np.array(im).astype(np.float32)
    correct=0; total=0; errs=[]
    for r in range(6):
        for c in range(6):
            x0=int(round(L+c*CW)); y0=int(round(T+r*CH))
            x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
            v=prep(arr[y0:y1,x0:x1])
            best=( -1e9, None )
            for sig, lst in ex_prep.items():
                for pv,_ in lst:
                    s=float(np.dot(v,pv)/len(v))
                    if s>best[0]: best=(s,sig)
            true = ''.join(sorted(gt[(r,c)][1])) if gt[(r,c)][1] else '-'
            total+=1
            if best[1]==true: correct+=1
            else: errs.append((r,c,true,best[1],round(best[0],3)))
    print(f"{name}: {correct}/{total} sides-correct. errors={errs[:12]} (total {len(errs)})")

classify(r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\run_01.png", GT_RUN01, "run01(self)")
classify(r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\fresh_01.png", GT_FRESH, "fresh(self)")

# cross-test: exemplars from run01 -> test fresh, and vice versa
ex_run = {}; ex_fresh = {}
add_exemplars # no
for path,gt,store in [
 (r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\run_01.png", GT_RUN01, ex_run),
 (r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\fresh_01.png", GT_FRESH, ex_fresh)]:
    im = Image.open(path).convert("RGB"); arr=np.array(im).astype(np.float32)
    for (r,c),(kind,sides) in gt.items():
        x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
        sig = ''.join(sorted(sides)) if sides else '-'
        store.setdefault(sig, []).append(prep(arr[y0:y1,x0:x1]))

def cross(test_path, gt, store, name):
    im = Image.open(test_path).convert("RGB"); arr=np.array(im).astype(np.float32)
    correct=0; total=0; errs=[]
    for r in range(6):
        for c in range(6):
            x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=int(round(L+(c+1)*CW)); y1=int(round(T+(r+1)*CH))
            v=prep(arr[y0:y1,x0:x1])
            best=(-1e9,None)
            for sig,lst in store.items():
                for pv in lst:
                    s=float(np.dot(v,pv)/len(v))
                    if s>best[0]: best=(s,sig)
            true = ''.join(sorted(gt[(r,c)][1])) if gt[(r,c)][1] else '-'
            total+=1
            if best[1]==true: correct+=1
            else: errs.append((r,c,true,best[1],round(best[0],3)))
    print(f"{name}: {correct}/{total}. errs={errs[:15]} ({len(errs)})")

cross(r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\fresh_01.png", GT_FRESH, ex_run, "train=run01 -> fresh")
cross(r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\run_01.png", GT_RUN01, ex_fresh, "train=fresh -> run01")
