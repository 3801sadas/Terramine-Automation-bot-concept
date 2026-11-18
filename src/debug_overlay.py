import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import sys
IMG = sys.argv[1] if len(sys.argv)>1 else r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\run_01.png"
CALIB = r"C:\Users\Usernom\Documents\Terramine\calibration.json"
base = os.path.splitext(os.path.basename(IMG))[0]
OUT = sys.argv[2] if len(sys.argv)>2 else rf"C:\Users\Usernom\Documents\Terramine\Memory\derived\debug\{base}_overlay.png"

with open(CALIB) as f: cal = json.load(f)
L,T = cal["board"]["left"], cal["board"]["top"]
cw,ch = cal["board"]["cell_w"], cal["board"]["cell_h"]

im = Image.open(IMG).convert("RGB")
arr = np.array(im).astype(np.float32)
R,G,B = arr[:,:,0], arr[:,:,1], arr[:,:,2]
mask = (R > 200) & (G > 150) & (B < 80)

def frac(x0,x1,y0,y1):
    a=mask[max(0,int(y0)):int(y1),max(0,int(x0)):int(x1)]
    return float(a.mean()) if a.size else 0.0

def detect_sides(r,c):
    x0=L+c*cw; x1=x0+cw; y0=T+r*ch; y1=y0+ch
    cx=(x0+x1)/2; cy=(y0+y1)/2
    def edge(frac_fn, frac_in_fn):
        return frac_fn() > 0.25 and frac_in_fn() > 0.15
    u = 1.0 if edge(lambda: frac(cx-10,cx+10,y0+1,y0+8), lambda: frac(cx-10,cx+10,y0+8,y0+30)) else 0.0
    rt = 1.0 if edge(lambda: frac(x1-8,x1-1,cy-10,cy+10), lambda: frac(x1-30,x1-8,cy-10,cy+10)) else 0.0
    d = 1.0 if edge(lambda: frac(cx-10,cx+10,y1-8,y1-1), lambda: frac(cx-10,cx+10,y1-30,y1-8)) else 0.0
    l = 1.0 if edge(lambda: frac(x0+1,x0+8,cy-10,cy+10), lambda: frac(x0+8,x0+30,cy-10,cy+10)) else 0.0
    return {k for k,v in {'N':u,'E':rt,'S':d,'W':l}.items() if v>0.5}

ORDER=['N','E','S','W']
def classify(sides):
    n=len(sides)
    if n==0: return 'gras', 0
    if n==4: return 'cross', 0
    if n==3:
        for i,d in enumerate(ORDER):
            if d not in sides: return 'T', i
        return 'T',0
    if n==2:
        if sides=={'N','S'}: return 'str', 0
        if sides=={'E','W'}: return 'str', 1
        pairs=[({'N','E'},0),({'E','S'},1),({'S','W'},2),({'W','N'},3)]
        for p,rot in pairs:
            if sides==p: return 'curv', rot
    if n==1: return 'dead', ORDER.index(list(sides)[0])
    return '?',0

# lep/pot guess (same heuristic as fast_solve)
imc=np.array(Image.open(IMG).convert('RGB')).astype(np.float32)
lep=pot=None; best_lep=best_pot=-1
CELL=int(round(cw))
for r in range(6):
    for c in range(6):
        x0=int(round(L+c*cw)); y0=int(round(T+r*ch))
        reg=imc[y0:y0+CELL,x0:x0+CELL]
        if reg.size==0: continue
        gold=((reg[:,:,0]>200)&(reg[:,:,1]>150)&(reg[:,:,2]<80)).sum()
        non_bg=((np.abs(reg[:,:,0]-reg[:,:,1])>20)).sum()
        if c>=4 and gold>best_pot: best_pot=gold; pot=(r,c)
        if c<=1 and non_bg>best_lep and (r,c)!=pot: best_lep=non_bg; lep=(r,c)

draw = ImageDraw.Draw(im)
try:
    font = ImageFont.truetype("arial.ttf", 14)
    font2 = ImageFont.truetype("arial.ttf", 12)
except:
    font = font2 = ImageFont.load_default()

for r in range(6):
    for c in range(6):
        x0=int(round(L+c*cw)); y0=int(round(T+r*ch)); x1=x0+CELL; y1=y0+CELL
        sides = detect_sides(r,c)
        t,rot = classify(sides)
        sstr = ''.join(sorted(sides)) or '-'
        color = (0,255,255) if t!='gras' else (180,180,180)
        draw.rectangle([x0,y0,x1,y1], outline=color, width=2)
        draw.text((x0+3,y0+3), f"{r},{c}", fill=(255,255,0), font=font2)
        draw.text((x0+3,y0+18), f"{t}{rot}", fill=(255,255,255), font=font)
        draw.text((x0+3,y0+36), sstr, fill=(0,255,0), font=font)
        if (r,c)==lep:
            draw.rectangle([x0+2,y0+2,x1-2,y1-2], outline=(255,0,255), width=3)
            draw.text((x0+3,y0+54), "LEP", fill=(255,0,255), font=font)
        if (r,c)==pot:
            draw.rectangle([x0+2,y0+2,x1-2,y1-2], outline=(255,165,0), width=3)
            draw.text((x0+3,y0+54), "POT", fill=(255,165,0), font=font)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
im.save(OUT)
print("saved", OUT)
print("lep", lep, "pot", pot)
for r in range(6):
    row=[]
    for c in range(6):
        s=detect_sides(r,c); t,rot=classify(s)
        row.append(f"{t}{rot}:{(''.join(sorted(s)) or '-')}")
    print(f"r{r}:", " | ".join(row))
