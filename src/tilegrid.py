"""Grid-size agnostic board geometry + tile-edge perception for Gold Rush.

The playfield frame (gold border) is the same for every grid size
(calibration.json -> board.left/top/right/bottom).  Inside it the game draws
an N x N grid of ~250 px sprite tiles whose seams are dark lines, so N can be
recovered from the screenshot alone (no uiautomator dump needed):

    n = 4  ->  cell ~252 px      n = 6  ->  cell ~168 px

`detect_geometry()` returns where the drawn tiles actually are; `road_sides()`
reads the four edge openings of one tile with a gold-road mask (thresholds are
scaled by the cell size so 4x4 and 6x6 behave the same).

Tile types only matter through their opening set, so 4 edge bits are enough:
    0 -> grass, 1 -> dead end, 2 adjacent -> curve, 2 opposite -> straight,
    3 -> T, 4 -> cross
"""
from __future__ import annotations

import os

import numpy as np

CALIB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "calibration.json")

ORDER = ["N", "E", "S", "W"]
VALID_N = (3, 4, 5, 6, 7, 8)
ARM_THRESHOLD = 0.40


def load_frame():
    """(left, top, right, bottom) of the gold playfield border."""
    import json
    with open(CALIB_PATH) as f:
        cal = json.load(f)
    b = cal["board"]
    return float(b["left"]), float(b["top"]), float(b["right"]), float(b["bottom"])


# ---------------------------------------------------------------- N detection

def _dip_centres(prof, lo, hi, gap=4, drop=10.0):
    """Centres of the dark seam lines in a luminance profile."""
    lo = max(0, int(lo)); hi = min(len(prof), int(hi))
    seg = prof[lo:hi]
    if seg.size < 8:
        return []
    thr = float(seg.min()) + drop
    idx = np.nonzero(seg < thr)[0] + lo
    groups = []
    for i in idx:
        if groups and i - groups[-1][-1] <= gap:
            groups[-1].append(i)
        else:
            groups.append([i])
    return [float(g[0] + g[-1]) / 2.0 for g in groups if len(g) >= 2]


def _fit_grid(seams, lo, hi):
    """Fit an evenly spaced N-cell grid to a list of seam positions.

    Spurious dips (sprites, road shadows, the frame itself) are tolerated: the
    cell size is the gap length that best explains *all* gaps as near-integer
    multiples, and the origin is the seam that best sits on that lattice.
    Returns (n, origin, cell) or None.
    """
    if len(seams) < 2:
        return None
    gaps = [b - a for a, b in zip(seams, seams[1:])]
    cands = sorted({round(g, 1) for g in gaps if g >= 60})
    best = None
    for s in cands:
        if not (120.0 <= s <= 320.0):
            continue
        n = int(round((hi - lo) / s))
        if n not in VALID_N or abs((hi - lo) / s - n) > 0.06 * n:
            continue
        if (seams[-1] - seams[0]) < (n - 2.2) * s:
            continue
        score, err = 0, 0.0
        for g in gaps:
            k = max(1, int(round(g / s)))
            d = abs(g - k * s)
            err += d
            if d <= 0.10 * s:
                score += 1
        cand = (score, -err, s, n)
        if best is None or cand[:2] > best[:2]:
            best = cand
    if not best or best[0] < 1:
        return None
    # One clean gap is enough when there are at least 3 candidate seams (a 4x4
    # board only has 3 internal seam lines and a single road shadow can split
    # one gap). The lattice phase + least-squares refine below reject the
    # spurious lines.
    if best[0] == 1 and len(seams) < 3:
        return None
    _, _, s, n = best
    # lattice phase: the seam that most other seams agree with
    origin = min(seams, key=lambda x: sum(
        abs(((y - x) / s) - round((y - x) / s)) for y in seams))
    # move to the lattice point nearest the frame -> row/col 0 of the grid
    phase = origin % s
    left = phase + int(round((lo - phase) / s)) * s
    # least-squares refine spacing/origin with every seam that sits on it
    idx, vals = [], []
    for x in seams:
        j = int(round((x - left) / s))
        if 0 <= j <= n and abs(x - (left + j * s)) <= 0.12 * s:
            idx.append(j); vals.append(x)
    if len(set(idx)) >= 2:
        a, b = np.polyfit(np.asarray(idx, float), np.asarray(vals, float), 1)
        if 110.0 <= a <= 330.0:
            s, left = float(a), float(b)
    # the playfield frame never moves, so the grid origin cannot drift far
    left = min(max(left, lo), lo + 0.15 * s)
    return n, left, s


def detect_geometry(arr):
    """Find the drawn tile grid inside the playfield frame.

    Returns dict(n, left, top, cell_x, cell_y, source).  Falls back to the 6x6
    calibrated rect only when the seams cannot be read at all.
    """
    fl, ft, fr, fb = load_frame()
    lum = arr.mean(axis=2)
    # 20th percentile over the perpendicular axis keeps sprites/roads from
    # hiding a seam without being fooled by a single dark column.
    colprof = np.percentile(lum[int(ft) + 6:int(fb) - 6, :], 20, axis=0)
    rowprof = np.percentile(lum[:, int(fl) + 6:int(fr) - 6], 20, axis=1)
    xs = _dip_centres(colprof, fl + 3, fr - 3)
    ys = _dip_centres(rowprof, ft + 3, fb - 3)

    gx = _fit_grid(xs, fl, fr)
    gy = _fit_grid(ys, ft, fb)

    def _ok(a, b):
        return a and b and a[0] == b[0] and \
            abs(a[2] - b[2]) <= 0.06 * max(a[2], b[2])

    if _ok(gx, gy):
        n, lx, cx = gx
        _, ty, cy = gy
        return {"n": n, "left": lx, "top": ty,
                "cell_x": cx, "cell_y": cy, "source": "seams"}

    # One axis often fails on grass-heavy boards: the horizontal gold road
    # segments and the "Time's Up" panel leak into the row profile and hide the
    # real seams. The playfield is square and the cells are square, so mirror
    # the axis that did fit instead of silently falling back to 6x6 (P005).
    if gx:
        n, lx, cx = gx
        inset = lx - fl
        return {"n": n, "left": lx, "top": ft + inset,
                "cell_x": cx, "cell_y": cx, "source": "seams_x"}
    if gy:
        n, ty, cy = gy
        inset = ty - ft
        return {"n": n, "left": fl + inset, "top": ty,
                "cell_x": cy, "cell_y": cy, "source": "seams_y"}

    # fallback: the historical 6x6 calibration
    cell = (fr - fl) / 6.0
    return {"n": 6, "left": fl, "top": ft,
            "cell_x": cell, "cell_y": (fb - ft) / 6.0, "source": "default"}


def cell_rect(geom, r, c):
    x0 = geom["left"] + c * geom["cell_x"]
    y0 = geom["top"] + r * geom["cell_y"]
    return x0, y0, x0 + geom["cell_x"], y0 + geom["cell_y"]


def tap_centre(geom, r, c):
    """Tap point for cell (r, c).

    Uses the drawn-cell centre, which sits inside the (larger, slightly
    higher) uiautomator clickable cell for every grid size we have seen.
    """
    x0, y0, x1, y1 = cell_rect(geom, r, c)
    return int(round((x0 + x1) / 2.0)), int(round((y0 + y1) / 2.0))


# ------------------------------------------------------------- tile openings

def road_mask(arr):
    a = np.asarray(arr).astype(np.int32)
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    # gold road: bright, saturated, and clearly yellow (R-B huge).
    # grass is far darker in R and has B ~ 0 too, so R>190 is the discriminator.
    return (R > 190) & (G > 120) & ((R - B) > 140)


def road_sides(mask, r, c, geom):
    """Read a tile's four openings from the gold-road mask.

    Returns (frozenset of sides, confidence, per-side fractions).
    """
    m = np.asarray(mask)
    x0, y0, x1, y1 = cell_rect(geom, r, c)
    cw = x1 - x0
    ch = y1 - y0
    band = max(6.0, 0.104 * cw)   # 26 px at 252 px cells, 17 px at 168 px
    hw = max(5.0, 0.080 * cw)     # half-width of the strip across the road
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    h, w = m.shape

    def f(ax, ay, bx, by):
        ax, ay = max(0, int(ax)), max(0, int(ay))
        bx, by = min(w, int(bx)), min(h, int(by))
        if bx <= ax or by <= ay:
            return 0.0
        return float(m[ay:by, ax:bx].mean())

    vals = {
        "N": f(cx - hw, y0, cx + hw, y0 + band),
        "E": f(x1 - band, cy - hw, x1, cy + hw),
        "S": f(cx - hw, y1 - band, cx + hw, y1),
        "W": f(x0, cy - hw, x0 + band, cy + hw),
    }
    sides = frozenset(d for d in ORDER if vals[d] > ARM_THRESHOLD)
    conf = min(vals.values()) if not sides else min(vals[d] for d in sides)
    return sides, float(conf), vals


def looks_like_grass(sides):
    return not sides
