"""Inspect the Play-Store (AD_STORE) frames from run 013 for close affordances."""
import os, re, glob
from PIL import Image, ImageDraw

base = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\ad_close\runs\20261116_194433"
out = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\ad_close\debug"

# polls that were AD_STORE: 4, 6, 9, 13
for n in [4, 6, 9, 13]:
    p = os.path.join(base, "poll_%02d.jpg" % n)
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert("RGB")
    # upscale top portion (where close affordances live) 2x
    top = im.crop((0, 0, 1080, 400)).resize((1080 * 2, 400 * 2))
    top.save(os.path.join(out, "store_%02d.png" % n))
    print(n, "saved", top.size)

# side by side
ims = []
for n in [4, 6, 9, 13]:
    p = os.path.join(out, "store_%02d.png" % n)
    if os.path.exists(p):
        ims.append((n, Image.open(p)))
if ims:
    w, h = ims[0][1].size
    sheet = Image.new("RGB", (w, h * len(ims)), "black")
    d = ImageDraw.Draw(sheet)
    for i, (n, im) in enumerate(ims):
        sheet.paste(im, (0, i * h))
        d.rectangle([0, i * h, 80, i * h + 16], fill="black")
        d.text((2, i * h + 2), "poll %02d" % n, fill="yellow")
    sheet.save(os.path.join(out, "stores_all.png"))
    print("sheet", sheet.size)