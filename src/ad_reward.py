"""Screenshot-only detection of the rewarded-ad 'Reward granted' state.

Why this exists (P007)
----------------------
The reward is granted when the *creative* ends, and the game deals the next
board at that moment - its 60 s clock starts running *behind* the ad end card.
`close_ad()` used to wait a fixed 75 s before looking for the X, so a board
could be 57 s old by the time we got to it.

AdMob's rewarded overlay shows a small badge in the top-right corner that reads
`Reward in N second(s)` while the video plays and switches to
`Reward granted` the instant the reward is paid. That string is rendered by the
SDK, so its glyph shapes are identical across ads; only the colours differ
(white-on-grey for a dark creative, black-on-white for a light one). Matching an
*edge map* is therefore both colour- and polarity-invariant, and it needs no
OCR and no `uiautomator dump` (~2.4 s per call), so it can run on every frame.

Templates live in Memory/derived/ad_close/templates/ and were cut from real
frames: 20261111_211046 (light text on grey pill) and 20261111_210930 (dark
text on white).
"""
from __future__ import annotations

import os

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

TEMPLATE_DIR = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\ad_close\templates"

# Fixed badge text box (x0, y0, x1, y1) in the 1080x2340 screenshot. The badge
# is right-anchored just left of the close X, so this box holds the whole
# "Reward granted" string and nothing else.
BADGE_RECT = (700, 130, 962, 182)

# Tolerance of the small positional jitter between ads (measured 4 px vertical).
SEARCH = 8

_TEMPLATES = None


def _edge(gray):
    gy, gx = np.gradient(gray.astype(np.float32))
    return np.hypot(gx, gy)


def _norm(a):
    a = a - a.mean()
    return a / (a.std() + 1e-6)


def _load_templates():
    global _TEMPLATES
    if _TEMPLATES is not None:
        return _TEMPLATES
    tpls = []
    if os.path.isdir(TEMPLATE_DIR):
        for name in sorted(os.listdir(TEMPLATE_DIR)):
            if not name.lower().endswith(".png"):
                continue
            from PIL import Image
            im = Image.open(os.path.join(TEMPLATE_DIR, name)).convert("L")
            e = _edge(np.asarray(im))
            if e.shape == (BADGE_RECT[3] - BADGE_RECT[1], BADGE_RECT[2] - BADGE_RECT[0]):
                tpls.append(_norm(e))
    _TEMPLATES = tpls
    return tpls


def _gray_of(img):
    """Accept a path or an RGB uint8 array; return an L array."""
    from PIL import Image
    if isinstance(img, np.ndarray):
        return np.asarray(Image.fromarray(img.astype(np.uint8)).convert("L"))
    return np.asarray(Image.open(img).convert("L"))


def reward_state(img):
    """Return {'granted': bool, 'score': float, 'available': bool}.

    `available` is False when no template could be loaded, in which case the
    caller must fall back to the old timing heuristic.
    """
    tpls = _load_templates()
    if not tpls:
        return {"granted": False, "score": 0.0, "available": False}
    try:
        g = _gray_of(img)
        x0, y0, x1, y1 = BADGE_RECT
        band = g[max(0, y0 - SEARCH):y1 + SEARCH, x0:x1]
        e = _edge(band)
        h = y1 - y0
        best = -1.0
        for dy in range(e.shape[0] - h + 1):
            a = _norm(e[dy:dy + h, :])
            for t in tpls:
                if a.shape != t.shape:
                    continue
                s = float((a * t).mean())
                if s > best:
                    best = s
    except Exception:
        return {"granted": False, "score": 0.0, "available": False}
    return {"granted": best >= 0.55, "score": round(best, 3), "available": True}
