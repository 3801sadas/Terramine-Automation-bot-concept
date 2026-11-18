from PIL import Image
import numpy as np
import glob, os

BOARD = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\board_01.png"
ASSET_DIR = r"C:\Users\Usernom\Downloads\TerraMine_+Real+World+Mining_1.1.45_APKPure\res\drawable-mdpi"
CELL = 168

types = {
    "grass": "assets_images_goldmine_tilegrass.png",
    "straight": "assets_images_goldmine_tilestraighth.png",
    "curve": "assets_images_goldmine_tilecurve.png",
    "t": "assets_images_goldmine_tiletjunction.png",
    "cross": "assets_images_goldmine_tilecross.png",
    "deadend": "assets_images_goldmine_tiledeadend.png",
}

def load_gray(path):
    return np.asarray(Image.open(path).convert("L").resize((CELL, CELL), Image.LANCZOS), dtype=np.float32)

templates = {}
for name, fn in types.items():
    base = load_gray(os.path.join(ASSET_DIR, fn))
    for rot in range(4):
        arr = np.asarray(Image.fromarray(base.astype(np.uint8)).rotate(-90 * rot, expand=False), dtype=np.float32)
        a = arr - arr.mean()
        a /= np.linalg.norm(a) + 1e-6
        templates[(name, rot)] = a

im = np.asarray(Image.open(BOARD).convert("L"), dtype=np.float32)
L, T = 36.0, 503.0
cw = 1007 / 6.0

for r in range(6):
    out = []
    for c in range(6):
        x0 = int(round(L + c * cw))
        y0 = int(round(T + r * cw))
        cell = im[y0:y0 + CELL, x0:x0 + CELL]
        if cell.shape != (CELL, CELL):
            out.append("??")
            continue
        v = cell - cell.mean()
        v /= np.linalg.norm(v) + 1e-6
        scored = sorted(((float((v * a).sum()), k) for k, a in templates.items()), reverse=True)
        top = scored[0]
        out.append(f"{top[1][0][:4]}{top[1][1]} {top[0]:.2f} | 2nd {scored[1][1][0][:4]}{scored[1][1][1]} {scored[1][0]:.2f}")
    print(f"r{r + 1}: " + " || ".join(out))
