from PIL import Image
import numpy as np
from solver import Cell, open_sides, solve, neighbours

IMG = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\live_now.png"
im = np.array(Image.open(IMG).convert("RGB")).astype(np.float32) / 255.0
mx = im.max(2); mn = im.min(2); V = mx; S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
mask = (V > 0.86) & (S > 0.55)
L, T = 36.0, 503.0; cw = 1007 / 6.0

def frac(x0, x1, y0, y1):
    a = mask[int(y0):int(y1), int(x0):int(x1)]
    return float(a.mean()) if a.size else 0.0

board = {}
start = goal = None
open_by_cell = {}
for r in range(6):
    for c in range(6):
        x0 = L + c * cw; x1 = x0 + cw; y0 = T + r * cw; y1 = y0 + cw
        cx = (x0 + x1) / 2; cy = (y0 + y1) / 2
        u = frac(cx - 18, cx + 18, y0 + 6, y0 + 26); rt = frac(x1 - 26, x1 - 6, cy - 18, cy + 18)
        d = frac(cx - 18, cx + 18, y1 - 26, y1 - 6); l = frac(cx - 18, cx + 18, y1 - 26, y1 - 6)
        scores = (u, rt, d, l)
        sides = "".join(k for k, v in zip("NESW", scores) if v > 0.35)
        open_by_cell[(r, c)] = sides
        board[(r, c)] = Cell(r, c, tile="straight" if len(sides) > 1 else "grass", rot=0)

# leprechaun / pot: find via gold-ish mask? simple: assume start leftmost open, goal rightmost open
flat = [(r, c) for (r, c) in sorted(board) if open_by_cell[(r, c)] not in ("", "-")]
print("open-ish cells:", flat)
start = min(flat, key=lambda k: (k[0], k[1]))
goal = max(flat, key=lambda k: (k[0], k[1]))
print("start", start, "goal", goal)
path = solve(board, start, goal)
print("path:", path)
