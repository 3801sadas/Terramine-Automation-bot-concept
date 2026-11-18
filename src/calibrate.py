import json, os
import numpy as np
from PIL import Image

CALIB = r"C:\Users\Usernom\Documents\Terramine\calibration.json"
with open(CALIB) as f: cal = json.load(f)
L,T = cal["board"]["left"], cal["board"]["top"]
cw,ch = cal["board"]["cell_w"], cal["board"]["cell_h"]

def S(s): return frozenset(s)
GT_RUN01 = {
(0,0):S(""),(0,1):S("NW"),(0,2):S("NE"),(0,3):S(""),(0,4):S("S"),(0,5):S(""),
(1,0):S("E"),(1,1):S("SW"),(1,2):S("NW"),(1,3):S("NS"),(1,4):S("NE"),(1,5):S(""),
(2,0):S(""),(2,1):S(""),(2,2):S("SW"),(2,3):S("NS"),(2,4):S("SW"),(2,5):S("W"),
(3,0):S(""),(3,1):S("EW"),(3,2):S("NW"),(3,3):S("E"),(3,4):S("NS"),(3,5):S(""),
(4,0):S(""),(4,1):S(""),(4,2):S(""),(4,3):S("W"),(4,4):S(""),(4,5):S(""),
(5,0):S(""),(5,1):S("EW"),(5,2):S(""),(5,3):S(""),(5,4):S("NW"),(5,5):S("N"),
}
GT_FRESH = {
(0,0):S(""),(0,1):S("E"),(0,2):S("SW"),(0,3):S("NS"),(0,4):S("NE"),(0,5):S(""),
(1,0):S(""),(1,1):S(""),(1,2):S("EW"),(1,3):S(""),(1,4):S("EW"),(1,5):S(""),
(2,0):S("E"),(2,1):S("NS"),(2,2):S("ES"),(2,3):S("NW"),(2,4):S("NE"),(2,5):S(""),
(3,0):S(""),(3,1):S("NS"),(3,2):S("EW"),(3,3):S("NW"),(3,4):S("ES"),(3,5):S(""),
(4,0):S(""),(4,1):S("NS"),(4,2):S("ES"),(4,3):S("NW"),(4,4):S("NE"),(4,5):S(""),
(5,0):S(""),(5,1):S("EW"),(5,2):S("EW"),(5,3):S("SW"),(5,4):S("NS"),(5,5):S("N"),
}

def frac(mask,x0,x1,y0,y1):
    a=mask[max(0,int(y0)):int(y1),max(0,int(x0)):int(x1)]
    return float(a.mean()) if a.size else 0.0

def edge_feats(mask,r,c):
    x0=L+c*cw; x1=x0+cw; y0=T+r*ch; y1=y0+ch
    cx=(x0+x1)/2; cy=(y0+y1)/2
    return {
        'N': (frac(mask,cx-12,cx+12,y0+1,y0+10), frac(mask,cx-12,cx+12,y0+10,y0+35)),
        'E': (frac(mask,x1-10,x1-1,cy-12,cy+12), frac(mask,x1-35,x1-10,cy-12,cy+12)),
        'S': (frac(mask,cx-12,cx+12,y1-10,y1-1), frac(mask,cx-12,cx+12,y1-35,y1-10)),
        'W': (frac(mask,x0+1,x0+10,cy-12,cy+12), frac(mask,x0+10,x0+35,cy-12,cy+12)),
    }

def score(img_path, gt, thr_edge=0.2, thr_in=0.1, use_and=True):
    im = np.array(Image.open(img_path).convert("RGB")).astype(np.float32)
    R,G,B = im[:,:,0],im[:,:,1],im[:,:,2]
    mask = (R>200)&(G>150)&(B<80)
    tp=fp=fn=0
    for r in range(6):
        for c in range(6):
            f = edge_feats(mask,r,c)
            pred=set()
            for d,(e,i) in f.items():
                ok = (e>thr_edge and i>thr_in) if use_and else (e>thr_edge or i>thr_in)
                if ok: pred.add(d)
            true = gt[(r,c)]
            tp += len(pred & true); fp += len(pred - true); fn += len(true - pred)
    prec = tp/(tp+fp+1e-9); rec = tp/(tp+fn+1e-9)
    return prec,rec,tp,fp,fn

for name,path,gt in [("run01",r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\run_01.png",GT_RUN01),
                     ("fresh",r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\fresh_01.png",GT_FRESH)]:
    for te in [0.15,0.2,0.25,0.3]:
        for ti in [0.05,0.1,0.15,0.2]:
            p,r,tp,fp,fn = score(path,gt,te,ti,True)
            f1=2*p*r/(p+r+1e-9)
            if f1>0.5: print(f"{name} te={te} ti={ti} F1={f1:.2f} P={p:.2f} R={r:.2f} fp={fp} fn={fn}")
