"""
Ad close helper: scan for close (X) buttons in high-probability regions.

Usage:
  python src/ad_close.py scan <screenshot.png> [--out debug.png] [--no-known]
  python src/ad_close.py sample <screenshot.png> <tap_x> <tap_y> [--note "..."]
  python src/ad_close.py add-point <x> <y> [--source "..."]
  python src/ad_close.py points

Live (agent-assisted): poll every ~10s with agentdroid.screenshot -> scan -> if confident tap -> wait/verify -> repeat.
This script provides detection & bookkeeping; device actions are done by the agent via execute/tools.agentdroid.*.
"""
import json, os, sys, time
from ad_detector import (
    find_close_candidates, annotate, save_sample, load_known_points,
    CONFIG_PATH, DEBUG_DIR, DEFAULT_REGIONS
)

def cmd_scan(args):
    if not args:
        print("usage: scan <image> [--out path] [--no-known]"); return 2
    img = args[0]
    no_known = "--no-known" in args
    out = None
    if "--out" in args:
        i = args.index("--out"); out = args[i+1] if i+1 < len(args) else None
    cands, (W,H) = find_close_candidates(img, include_known=not no_known)
    if not out:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        base = os.path.splitext(os.path.basename(img))[0]
        out = os.path.join(DEBUG_DIR, f"{base}_adscan.png")
    annotate(img, cands, out)
    print(f"IMAGE: {img} ({W}x{H})")
    print(f"ANNOTATED: {out}")
    print(f"CANDIDATES ({len(cands)}):")
    for i,c in enumerate(cands):
        print(f"  #{i} tap=({c.x},{c.y}) score={c.score:.3f} region={c.region} method={c.method} meta={c.meta}")
    if cands:
        best = cands[0]
        print(f"RECOMMENDED: ({best.x},{best.y}) score={best.score:.3f}")
        # safe action suggestion
        if best.score >= 0.7:
            print("CONFIDENCE: high (>=0.7) - candidate for tap, verify after")
        elif best.score >= 0.5:
            print("CONFIDENCE: medium (>=0.5) - tap with caution/verify; consider known-point fallback")
        else:
            print("CONFIDENCE: low - do not auto-tap; wait/poll or manual")
    else:
        print("RECOMMENDED: none (poll again / wait for close control)")
    # machine-readable
    print("JSON=" + json.dumps([{"x":c.x,"y":c.y,"score":c.score,"region":c.region,"method":c.method} for c in cands]))
    return 0

def cmd_sample(args):
    if len(args) < 3:
        print("usage: sample <image> <tap_x> <tap_y> [--note text]"); return 2
    img, x, y = args[0], int(args[1]), int(args[2])
    note = ""
    if "--note" in args:
        i = args.index("--note"); note = args[i+1] if i+1 < len(args) else ""
    rec = save_sample(img, x, y, label="close", note=note)
    print("SAVED SAMPLE:", json.dumps(rec, ensure_ascii=False))
    return 0

def cmd_add_point(args):
    if len(args) < 2:
        print("usage: add-point <x> <y> [--source text]"); return 2
    x,y = int(args[0]), int(args[1])
    source = ""
    if "--source" in args:
        i = args.index("--source"); source = args[i+1] if i+1 < len(args) else ""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f: d=json.load(f)
    else:
        d = {"points": [], "strategy": ""}
    pts = d.setdefault("points", [])
    pts.append({"x":x,"y":y,"source":source})
    # keep unique-ish
    uniq=[]
    for p in pts:
        if not any(abs(p["x"]-q["x"])+abs(p["y"]-q["y"])<20 for q in uniq):
            uniq.append(p)
    d["points"]=uniq
    with open(CONFIG_PATH, "w", encoding="utf-8") as f: json.dump(d,f,indent=2)
    print("UPDATED", CONFIG_PATH, "points=", len(uniq))
    return 0

def cmd_points(args):
    pts = load_known_points()
    print("CONFIG:", CONFIG_PATH, "exists=", os.path.exists(CONFIG_PATH))
    print("REGIONS:", json.dumps(DEFAULT_REGIONS))
    print("KNOWN_POINTS:", pts)
    return 0

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 0
    cmd = sys.argv[1]; args = sys.argv[2:]
    if cmd == "scan": return cmd_scan(args)
    if cmd == "sample": return cmd_sample(args)
    if cmd == "add-point": return cmd_add_point(args)
    if cmd == "points": return cmd_points(args)
    print(__doc__); return 1

if __name__ == "__main__":
    sys.exit(main())
