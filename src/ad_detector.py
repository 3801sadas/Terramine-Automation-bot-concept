"""
Heuristic ad close-button (X) detector for 1080x2340 screenshots.

Searches high-probability regions and returns candidate tap points.
Designed for polling every ~10s with post-tap verification (caller responsibility).
"""
from __future__ import annotations
import json, math, os
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple
import numpy as np
from PIL import Image

try:
    import cv2
except Exception:
    cv2 = None

CONFIG_PATH = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\ad_close_points.json"
SAMPLES_DIR = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\ad_close\samples"
DEBUG_DIR = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\ad_close\debug"

# Candidate search regions (x1,y1,x2,y2) for 1080x2340
DEFAULT_REGIONS = {
    "mid_right": (860, 480, 1065, 700),   # around learned ~(985,582)
    "top_right": (920, 20, 1075, 220),
    "top_left":  (5,   20,  180, 260),
    "top_center":(420, 20,  660, 200),
}

@dataclass
class Candidate:
    x: int
    y: int
    score: float
    region: str
    method: str
    meta: dict = None

def load_known_points():
    if not os.path.exists(CONFIG_PATH):
        return []
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        d = json.load(f)
    pts = d.get("points") or d.get("known_points") or []
    # normalize
    out = []
    for p in pts:
        if isinstance(p, dict) and "x" in p and "y" in p:
            out.append((int(p["x"]), int(p["y"])))
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            out.append((int(p[0]), int(p[1])))
    if not out:
        # fallback to learned defaults
        out = [(993, 581), (975, 584)]
    return out

def _imread(path_or_arr):
    if isinstance(path_or_arr, np.ndarray):
        arr = path_or_arr
        if arr.ndim == 2:
            return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
        if arr.shape[2] == 4:
            return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        return arr.copy()
    im = Image.open(path_or_arr).convert("RGB")
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)

def _x_score_hough(roi_gray):
    """Score likelihood of an X (two crossing diagonal lines) in ROI. Returns (score, cx, cy)."""
    if cv2 is None or roi_gray.size == 0:
        return 0.0, None, None
    h, w = roi_gray.shape[:2]
    if h < 20 or w < 20:
        return 0.0, None, None
    # enhance edges
    blur = cv2.GaussianBlur(roi_gray, (3,3), 0)
    # try multiple thresholds
    best = 0.0; best_pt = (w//2, h//2)
    for t1,t2 in [(50,150),(30,100),(80,200)]:
        edges = cv2.Canny(blur, t1, t2)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=max(10, min(h,w)//5),
                                minLineLength=max(8, min(h,w)//4), maxLineGap=6)
        if lines is None:
            continue
        # classify by angle
        diag1=[]; diag2=[]
        for l in lines:
            seg = l[0] if hasattr(l, '__len__') and len(l)==1 else l
            x1,y1,x2,y2 = [int(v) for v in seg]
            ang = math.degrees(math.atan2(y2-y1, x2-x1))
            # normalize to [-90,90]
            while ang > 90: ang -= 180
            while ang < -90: ang += 180
            if 25 < ang < 65:
                diag1.append((x1,y1,x2,y2,ang))
            elif -65 < ang < -25:
                diag2.append((x1,y1,x2,y2,ang))
        if not diag1 or not diag2:
            continue
        # find intersections near center-ish
        for a in diag1[:8]:
            for b in diag2[:8]:
                ix, iy = _intersect(a,b)
                if ix is None: continue
                if 0 <= ix < w and 0 <= iy < h:
                    # prefer central crossings
                    cxn = 1.0 - (abs(ix - w/2)/(w/2))*0.5
                    score = 0.6 + 0.4*cxn
                    if score > best:
                        best = score; best_pt = (ix, iy)
    # contrast/smallness bonus: X usually in a compact button
    if best > 0:
        std = float(np.std(roi_gray))
        best += min(0.2, std/200.0)
    return min(best, 1.0), int(best_pt[0]), int(best_pt[1])

def _intersect(a,b):
    x1,y1,x2,y2,_ = a; x3,y3,x4,y4,_ = b
    den = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(den) < 1e-6: return None, None
    px = ((x1*y2-y1*x2)*(x3-x4) - (x1-x2)*(x3*y4-y3*x4)) / den
    py = ((x1*y2-y1*x2)*(y3-y4) - (y1-y2)*(x3*y4-y3*x4)) / den
    return px, py

def _template_x_score(roi_gray):
    """Match simple synthetic X templates at multiple scales."""
    if cv2 is None: return 0.0, None, None
    h,w = roi_gray.shape[:2]
    best = 0.0; best_pt=(w//2,h//2)
    for size in [18,24,30,40,52]:
        if size >= min(h,w): continue
        tmpl = np.zeros((size,size), dtype=np.uint8)
        t = max(2, size//10)
        cv2.line(tmpl, (3,3), (size-4,size-4), 255, t)
        cv2.line(tmpl, (size-4,3), (3,size-4), 255, t)
        # also try on inverted/edges
        for src in [roi_gray, 255-roi_gray, cv2.Canny(roi_gray,50,150)]:
            if src.dtype != np.uint8:
                src = src.astype(np.uint8)
            if src.shape[0] < size or src.shape[1] < size: continue
            res = cv2.matchTemplate(src, tmpl, cv2.TM_CCOEFF_NORMED)
            _, mv, _, ml = cv2.minMaxLoc(res)
            if mv > best:
                best = float(mv); best_pt = (ml[0]+size//2, ml[1]+size//2)
    # normalize roughly
    score = max(0.0, min(1.0, (best - 0.2) / 0.6))
    return score, int(best_pt[0]), int(best_pt[1])

def detect_in_region(bgr, name, box):
    x1,y1,x2,y2 = [int(v) for v in box]
    H,W = bgr.shape[:2]
    x1=max(0,x1); y1=max(0,y1); x2=min(W,x2); y2=min(H,y2)
    roi = bgr[y1:y2, x1:x2]
    if roi.size == 0:
        return []
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    cands = []
    s1,cx,cy = _x_score_hough(gray)
    if s1 >= 0.45 and cx is not None:
        cands.append(Candidate(x1+cx, y1+cy, round(s1,3), name, "hough", {"raw":s1}))
    s2,cx,cy = _template_x_score(gray)
    if s2 >= 0.45 and cx is not None:
        cands.append(Candidate(x1+cx, y1+cy, round(s2,3), name, "template", {"raw":s2}))
    # merge close candidates in same region
    merged = []
    for c in sorted(cands, key=lambda z: -z.score):
        if any(abs(c.x-m.x)+abs(c.y-m.y) < 30 for m in merged):
            # boost existing
            for m in merged:
                if abs(c.x-m.x)+abs(c.y-m.y) < 30:
                    m.score = min(1.0, max(m.score, c.score) + 0.05)
            continue
        merged.append(c)
    return merged

def find_close_candidates(path_or_arr, regions=None, include_known=True):
    bgr = _imread(path_or_arr)
    H,W = bgr.shape[:2]
    regions = regions or DEFAULT_REGIONS
    out = []
    # known-point priors: if a known point falls inside (or near) a region, emit a prior candidate
    if include_known:
        for (kx,ky) in load_known_points():
            region_name = "known"
            for rn, box in regions.items():
                x1,y1,x2,y2 = box
                if x1-40 <= kx <= x2+40 and y1-40 <= ky <= y2+40:
                    region_name = rn; break
            out.append(Candidate(kx, ky, 0.55, region_name, "known_point", {"prior":True}))
    # visual detection
    for name, box in regions.items():
        out.extend(detect_in_region(bgr, name, box))
    # dedupe across regions
    final = []
    for c in sorted(out, key=lambda z: (-z.score, 0 if z.method=="known_point" else 1)):
        found = None
        for f in final:
            if abs(c.x-f.x)+abs(c.y-f.y) < 35:
                found = f; break
        if found:
            # combine: known prior + visual boost is strong
            if c.method != found.method:
                found.score = min(1.0, found.score + c.score*0.4)
                found.meta = {**(found.meta or {}), "corroborated_by": c.method}
            else:
                found.score = max(found.score, c.score)
        else:
            final.append(c)
    final.sort(key=lambda z: -z.score)
    return final, (W,H)

def annotate(path_or_arr, candidates, out_path):
    bgr = _imread(path_or_arr)
    for c in candidates:
        color = (0,255,0) if c.score >= 0.7 else (0,200,255) if c.score >= 0.5 else (0,0,255)
        cv2.circle(bgr, (c.x,c.y), 22, color, 2)
        cv2.drawMarker(bgr, (c.x,c.y), color, cv2.MARKER_CROSS, 18, 2)
        label = f"{c.score:.2f} {c.region}/{c.method}"
        cv2.putText(bgr, label, (max(5,c.x-80), max(20,c.y-28)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    # draw regions
    for name, (x1,y1,x2,y2) in DEFAULT_REGIONS.items():
        cv2.rectangle(bgr, (x1,y1), (x2,y2), (255,255,0), 1)
        cv2.putText(bgr, name, (x1+4,y1+16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,0), 1, cv2.LINE_AA)
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    cv2.imwrite(out_path, bgr)
    return out_path

def save_sample(img_path, tap_x, tap_y, label="close", note=""):
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    import time, shutil
    ts = time.strftime("%Y%m%d_%H%M%S")
    base = os.path.splitext(os.path.basename(img_path))[0]
    dst_img = os.path.join(SAMPLES_DIR, f"{ts}_{base}.png")
    shutil.copy2(img_path, dst_img)
    rec = {"image": dst_img, "tap": [tap_x, tap_y], "label": label, "note": note, "time": ts}
    jpath = os.path.join(SAMPLES_DIR, "samples.jsonl")
    with open(jpath, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
