from PIL import Image
import numpy as np
from collections import deque

IMG = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\live_new_01.png"
im = np.array(Image.open(IMG).convert("RGB")).astype(np.float32) / 255.0
mx = im.max(2); mn = im.min(2); V = mx; S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
mask = (V > 0.86) & (S > 0.55)
L, T = 36.0, 503.0; cw = 1007 / 6.0

def frac(x0, x1, y0, y1):
    a = mask[int(y0):int(y1), int(x0):int(x1)]
    return float(a.mean()) if a.size else 0.0

def open_set(r, c):
    x0 = L + c * cw; x1 = x0 + cw; y0 = T + r * cw; y1 = y0 + cw
    cx = (x0 + x1) / 2; cy = (y0 + y1) / 2
    u = frac(cx - 18, cx + 18, y0 + 6, y0 + 26); rt = frac(x1 - 26, x1 - 6, cy - 18, cy + 18)
    d = frac(cx - 18, cx + 18, y1 - 26, y1 - 6); l = frac(x0 + 6, x0 + 26, cy - 18, cy + 18)
    sc = (u, rt, d, l)
    return {k for k, v in zip("NESW", sc) if v > 0.35}

cells = {(r, c): open_set(r, c) for r in range(6) for c in range(6)}
DIRS = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}

adj = {k: [] for k in cells}
for (r, c), sides in cells.items():
    for d, (dr, dc) in DIRS.items():
        if d in sides:
            nb = (r + dr, c + dc)
            if nb in cells and {"N": "S", "E": "W", "S": "N", "W": "E"}[d] in cells[nb]:
                adj[(r, c)].append(nb)

start = min(cells, key=lambda k: (k[1], k[0]))
goal = max(cells, key=lambda k: (k[1], k[0]))
prev = {start: None}
q = deque([start])
while q:
    cur = q.popleft()
    if cur == goal:
        break
    for nb in adj[cur]:
        if nb not in prev:
            prev[nb] = cur
            q.append(nb)
if goal not in prev:
    print("NO PATH")
else:
    path = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    print("PATH:", path)
    print("open cells along path:", [(p, sorted(cells[p])) for p in path])
