"""Screen-state classifier driven entirely by the Android UI tree.

No pixels, no models: every decision comes from text / content-desc / bounds.
"""
from __future__ import annotations

import re
import unicodedata

from device import center, parse_nodes

STATES = [
    "BOARD", "RESULT_FREE", "RESULT_AD", "LEVEL_UP", "AD_LOADING",
    "AD_WEBVIEW", "AD_STORE", "AD_NOT_READY", "OUT_OF_MOVES", "TIME_UP",
    "MENU", "UNKNOWN",
]

EMOJI_RE = re.compile(
    "[" "\U0001F000-\U0001FAFF" "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF" "\U0000FE00-\U0000FE0F" "\U00002000-\U0000206F" "]"
)


def clean(s):
    """Strip emoji/symbols so substring tests survive encoding differences."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = EMOJI_RE.sub("", s)
    return " ".join(s.split())


def ui_package(xml_text):
    """Package of the topmost window in a uiautomator dump."""
    m = re.search(r'package="([^"]+)"', xml_text or "")
    return m.group(1) if m else None


def _texts(nodes):
    return [clean(n["text"]) for n in nodes]


def _descs(nodes):
    return [clean(n["desc"]) for n in nodes]


def _find(nodes, *, desc_contains=None, desc_equals=None, text_contains=None,
          rid=None, clickable_only=True):
    """First node (clickable by default) matching the given predicates."""
    for n in nodes:
        if clickable_only and not n["clickable"]:
            continue
        if rid and n["rid"] != rid:
            continue
        if desc_contains and desc_contains not in clean(n["desc"]):
            continue
        if desc_equals is not None and clean(n["desc"]) != desc_equals:
            continue
        if text_contains and text_contains not in clean(n["text"]):
            continue
        if n["rect"] is None:
            continue
        return n
    return None


def _element(nodes, name, **kw):
    n = _find(nodes, **kw)
    if not n:
        return None
    cx, cy = center(n["rect"])
    return {"name": name, "cx": cx, "cy": cy, "rect": n["rect"],
            "desc": clean(n["desc"]), "text": clean(n["text"])}


def elements(nodes):
    """Runtime-resolved tap targets. Coordinates always come from bounds."""
    out = {}
    for name, kw in (
        ("play_again", {"desc_contains": "Play Again"}),
        ("watch_ad", {"desc_contains": "Watch Ad"}),
        ("exit", {"desc_contains": "Exit"}),
        ("quit", {"desc_contains": "Quit"}),
        ("back", {"desc_contains": "Back"}),
        ("close_btn", {"desc_equals": "Close", "clickable_only": False}),
        ("ok", {"rid": "android:id/button1", "clickable_only": False}),
    ):
        el = _element(nodes, name, **kw)
        if el:
            out[name] = el
    # board cells: the 6x6 clickable grid
    cells = [n for n in nodes if n["clickable"] and n["rect"] and
             n["rect"][2] - n["rect"][0] < 200 and
             n["rect"][3] - n["rect"][1] < 200 and
             200 <= n["rect"][1] <= 1500 and n["cls"] == "android.view.ViewGroup"]
    if len(cells) >= 36:
        out["board_cells"] = len(cells)
    return out


def classify(nodes_or_xml):
    pkg = None
    if isinstance(nodes_or_xml, str):
        pkg = ui_package(nodes_or_xml)
        nodes = parse_nodes(nodes_or_xml)
    else:
        nodes = nodes_or_xml
    texts = _texts(nodes)
    descs = _descs(nodes)
    joined_text = " | ".join(t for t in texts if t)
    joined_desc = " | ".join(d for d in descs if d)

    els = elements(nodes)

    # 0. Time-up is checked first: the board is still visible behind the panel,
    #    so every later rule would otherwise misfire. Rule: do nothing on time-up.
    if "Time's Up" in joined_text or "couldn't find the way" in joined_text:
        return "TIME_UP", els

    # 0b. Another app is in the foreground: an ad opened the Play Store (or a
    #     browser). Nothing here belongs to TerraMine, so close it, never tap
    #     the creative.
    if pkg and pkg != "com.terramine.app":
        return "AD_STORE", els

    # 0c. Out of moves is checked before the board rules: the dead board is still
    #     visible behind the "Out of moves!" overlay, so rules 6/7 would call it a
    #     live BOARD and the loop would tap a plan on it (P013). The overlay must
    #     never be treated as a fresh board.
    if "out of moves" in joined_text.lower():
        return "OUT_OF_MOVES", els

    # 1. Full-screen WebView -> ad creative
    for n in nodes:
        if n["cls"] == "android.webkit.WebView" and n["rect"]:
            x1, y1, x2, y2 = n["rect"]
            area = max(0, x2 - x1) * max(0, y2 - y1)
            if area >= 0.8 * 1080 * 2340:
                return "AD_WEBVIEW", els

    # 2. "Ad Not Ready" dialog
    if "Ad Not Ready" in joined_text or (
            "Ad Not Ready" in joined_text + joined_desc and "button1" in
            " ".join(n["rid"] for n in nodes)):
        return "AD_NOT_READY", els
    if "Ad Not Ready" in joined_text:
        return "AD_NOT_READY", els

    # 3. Loading ad
    if "Loading ad" in joined_text:
        return "AD_LOADING", els

    # 4. Level-up offer
    if "Watch Ad" in joined_desc and "Play Level" in joined_desc:
        return "LEVEL_UP", els
    if "LEVEL UP!" in joined_text and "Watch Ad" in joined_desc:
        return "LEVEL_UP", els

    # 5. Result panels
    if "Pot of Gold Found!" in joined_text:
        if "Watch Ad" in joined_desc:
            return "RESULT_AD", els
        if "Play Again" in joined_desc:
            return "RESULT_FREE", els
        return "RESULT_AD" if "watch_ad" in els else "UNKNOWN", els

    # 6. Board
    if "Tap road tiles to rotate" in joined_text or "board_cells" in els:
        return "BOARD", els
    if "left" in joined_text and "Level" in joined_text and "XP" in joined_text:
        return "BOARD", els

    # 7. Menu (bottom nav visible, no board)
    if "Map" in joined_desc and "Settings" in joined_desc and "Profile" in joined_desc:
        return "MENU", els

    return "UNKNOWN", els


def classify_ui(xml_text):
    return classify(xml_text)


if __name__ == "__main__":
    import sys
    from device import dump_ui
    if len(sys.argv) > 1:
        xml = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
    else:
        xml, _ = dump_ui()
    state, els = classify(xml)
    print("STATE:", state)
    for k, v in els.items():
        print(" ", k, v)
