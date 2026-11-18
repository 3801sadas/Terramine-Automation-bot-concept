from PIL import Image
import numpy as np

im = np.array(Image.open(r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\board_02.png").convert("RGB")).astype(float)
L, T, R, B = 36, 503, 1043, 1510
cw = (R - L) / 6.0
ch = (B - T) / 6.0
GRASS = np.array([100.0, 128.0, 70.0])
for r in range(6):
    line = []
    for c in range(6):
        x0, y0, x1, y1 = int(round(L + c * cw)), int(round(T + r * ch)), int(round(L + (c + 1) * cw)), int(round(T + (r + 1) * ch))
        reg = im[y0:y1, x0:x1]
        d = np.linalg.norm(reg - GRASS, axis=2)
        line.append(f"{d.mean():.0f}")
    print("r%d %s" % (r, " ".join(line)))
