"""Tile perception for Gold Rush: classify each cell's tile type and rotation."""
import json, os
import numpy as np
from PIL import Image

ASSET_DIR = r"C:\Users\Usernom\Downloads\TerraMine_+Real+World+Mining_1.1.45_APKPure\res\drawable-mdpi"
CALIB = r"C:\Users\Usernom\Documents\Terramine\calibration.json"
TYPES = {
    "grass": "assets_images_goldmine_tilegrass.png",
    "straight": "assets_images_goldmine_tilestraighth.png",
    "curve": "assets_images_goldmine_tilecurve.png",
    "t": "assets_images_goldmine_tiletjunction.png",
    "cross": "assets_images_goldmine_tilecross.png",
    "deadend": "assets_images_goldmine_tiledeadend.png",
}
ORDER = ["N","E","S","W"]

def rot_sides(tile, rot):
    base = {"grass":set(),"straight":{"N","S"},"curve":{"N","E"},"t":{"N","E","S"},"cross":{"N","E","S","W"},"deadend":{"N"}}
    return {ORDER[(ORDER.index(d)+rot)%4] for d in base.get(tile,set())}

def load_calib():
    with open(CALIB) as f: return json.load(f)

def build_templates(cell_size):
    templates = []
    for name, fn in TYPES.items():
        path = os.path.join(ASSET_DIR, fn)
        img = Image.open(path).convert("RGB").resize((cell_size, cell_size), Image.LANCZOS)
        base = np.asarray(img, dtype=np.float32)
        for rot in range(4):
            arr = np.asarray(Image.fromarray(base.astype(np.uint8)).rotate(-90*rot, expand=False), dtype=np.float32)
            # normalize for NCC
            a = arr.reshape(-1); a = a - a.mean()
            n = np.linalg.norm(a)
            templates.append((name, rot, a / (n + 1e-8), arr.shape))
    return templates

def classify_board(img_path, debug=False):
    cal = load_calib()
    L,T = cal["board"]["left"], cal["board"]["top"]
    cw,ch = cal["board"]["cell_w"], cal["board"]["cell_h"]
    CELL = int(round(cw))
    templates = build_templates(CELL)
    im = Image.open(img_path).convert("RGB")
    arr = np.asarray(im, dtype=np.float32)
    board = {}
    for r in range(6):
        for c in range(6):
            x0 = int(round(L + c*cw)); y0 = int(round(T + r*ch))
            cell = arr[y0:y0+CELL, x0:x0+CELL]
            if cell.shape[0] != CELL or cell.shape[1] != CELL:
                pad = np.zeros((CELL,CELL,3), dtype=np.float32)
                pad[:cell.shape[0],:cell.shape[1]] = cell
                cell = pad
            v = cell.reshape(-1); v = v - v.mean()
            n = np.linalg.norm(v)
            v = v / (n + 1e-8)
            best = None
            for name, rot, t, _ in templates:
                score = float(np.dot(v, t))
                if best is None or score > best[0]: best = (score, name, rot)
            board[(r,c)] = {"tile": best[1], "rot": best[2], "score": best[0], "sides": sorted(rot_sides(best[1], best[2]))}
    return board, cal

if __name__ == "__main__":
    import sys
    img = sys.argv[1] if len(sys.argv)>1 else r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\run_01.png"
    b, cal = classify_board(img)
    for r in range(6):
        row = []
        for c in range(6):
            v=b[(r,c)]; row.append(f"{v['tile'][:3]}{v['rot']}({v['score']:.2f})")
        print(f"r{r}: " + " ".join(row))
