import os, sys, math
from PIL import Image, ImageDraw, ImageFont
CALIB = r"C:\Users\Usernom\Documents\Terramine\calibration.json"
import json
with open(CALIB) as f: cal=json.load(f)
L,T=cal["board"]["left"],cal["board"]["top"]; cw,ch=cal["board"]["cell_w"],cal["board"]["cell_h"]
CELL=int(round(cw))
IMG = sys.argv[1] if len(sys.argv)>1 else r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\fresh_01.png"
base=os.path.splitext(os.path.basename(IMG))[0]
OUT = sys.argv[2] if len(sys.argv)>2 else rf"C:\Users\Usernom\Documents\Terramine\Memory\derived\debug\{base}_label_sheet.png"
im = Image.open(IMG).convert("RGB")
pad=8; cols=6; rows=6
sheet = Image.new("RGB", (cols*(CELL+pad)+pad, rows*(CELL+pad)+pad+22), (30,30,30))
draw = ImageDraw.Draw(sheet)
try: font=ImageFont.truetype("arial.ttf", 14)
except: font=ImageFont.load_default()
for r in range(6):
    for c in range(6):
        x0=int(round(L+c*cw)); y0=int(round(T+r*ch))
        crop=im.crop((x0,y0,x0+CELL,y0+CELL))
        px=pad+c*(CELL+pad); py=pad+22+r*(CELL+pad)
        sheet.paste(crop,(px,py))
        draw.text((px,py-18),f"({r},{c})",(255,255,0),font=font)
os.makedirs(os.path.dirname(OUT),exist_ok=True)
sheet.save(OUT); print("saved",OUT)