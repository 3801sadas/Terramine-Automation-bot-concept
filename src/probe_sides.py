from PIL import Image
import numpy as np

IMG = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\board_01.png"

im = np.array(Image.open(IMG).convert("RGB")).astype(np.float32) / 255.0
mx = im.max(2)
mn = im.min(2)
V = mx
S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
mask = (V > 0.86) & (S > 0.55)

L, T = 36.0, 503.0
cw = 1007 / 6.0


def frac(x0, x1, y0, y1):
    a = mask[int(y0):int(y1), int(x0):int(x1)]
    return float(a.mean()) if a.size else 0.0


print("side scores (U,R,D,L) and open-side set:")
for r in range(6):
    cells = []
    for c in range(6):
        x0 = L + c * cw
        x1 = x0 + cw
        y0 = T + r * cw
        y1 = y0 + cw
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        u = frac(cx - 18, cx + 18, y0 + 6, y0 + 26)
        rt = frac(x1 - 26, x1 - 6, cy - 18, cy + 18)
        d = frac(cx - 18, cx + 18, y1 - 26, y1 - 6)
        l = frac(x0 + 6, x0 + 26, cy - 18, cy + 18)
        scores = (u, rt, d, l)
        sides = "".join(k for k, v in zip("NESW", scores) if v > 0.35)
        cells.append(f"{sides or '-':4s} {scores[0]:.2f}/{scores[1]:.2f}/{scores[2]:.2f}/{scores[3]:.2f}")
    print(f"row {r + 1}: " + " | ".join(cells))
