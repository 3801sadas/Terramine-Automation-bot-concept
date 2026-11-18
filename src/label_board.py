"""
Label a fresh Gold Rush board: screenshot -> perception -> overlay + correction template.

Usage:
  python src/label_board.py <screenshot.png> [--exclude]
  python src/label_board.py <screenshot.png> --save <corrected.json>

Workflow:
  1. Capture a screenshot of a fresh board.
  2. Run this: it writes an overlay PNG with predicted open sides per cell.
  3. Correct cells (only the wrong ones) in the JSON it prints.
  4. Re-run with --save to append the board to Memory/derived/labels/ground_truth.json,
     which immediately becomes an exemplar for future boards.
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from perception_v2 import perceive, load_calib

LABELS_JSON = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\labels\ground_truth.json"
OUT_DIR = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\debug"

def render(img_path, res, out_path):
    cal = res["cal"]; L,T = cal["board"]["left"], cal["board"]["top"]; CW,CH = cal["board"]["cell_w"], cal["board"]["cell_h"]
    im = Image.open(img_path).convert("RGB")
    d = ImageDraw.Draw(im)
    try:
        f1 = ImageFont.truetype("arial.ttf", 16); f2 = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        f1 = f2 = ImageFont.load_default()
    lep, pot = res["lep"], res["pot"]
    for r in range(6):
        for c in range(6):
            x0=int(round(L+c*CW)); y0=int(round(T+r*CH)); x1=x0+int(round(CW)); y1=y0+int(round(CH))
            kind, sides, conf = res["grid"][(r,c)]
            sig = ''.join(x for x in "NESW" if x in sides) or '-'
            color = (0,255,255) if sig != '-' else (150,150,150)
            if lep and (r,c)==lep: color=(255,0,255)
            if pot and (r,c)==pot: color=(255,165,0)
            d.rectangle([x0,y0,x1,y1], outline=color, width=2)
            d.text((x0+3,y0+3), f"{r},{c}", fill=(255,255,0), font=f2)
            tag = ("LEP " if lep and (r,c)==lep else "POT " if pot and (r,c)==pot else "")
            d.text((x0+3,y0+20), f"{tag}{sig}", fill=(255,255,255), font=f1)
            d.text((x0+3,y0+42), f"{conf:.2f}", fill=(200,200,200), font=f2)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    im.save(out_path)
    return out_path

def correction_template(res, img_path):
    cells = {}
    lep, pot = res["lep"], res["pot"]
    for r in range(6):
        for c in range(6):
            kind, sides, _ = res["grid"][(r,c)]
            sig = ''.join(x for x in "NESW" if x in sides)
            if lep and (r,c)==lep: kind = "LEP"
            elif pot and (r,c)==pot: kind = "POT"
            elif not sig: kind = "grass"
            else: kind = "tile"
            cells[f"{r},{c}"] = {"kind": kind, "sides": sig}
    return {"image": img_path, "lep": list(lep) if lep else None, "pot": list(pot) if pot else None, "cells": cells}

def append_board(board):
    if os.path.exists(LABELS_JSON):
        with open(LABELS_JSON, "r", encoding="utf-8") as f: doc=json.load(f)
    else:
        doc={"boards":[]}
    doc["boards"] = [b for b in doc.get("boards",[]) if os.path.normcase(b["image"])!=os.path.normcase(board["image"])]
    doc["boards"].append(board)
    with open(LABELS_JSON, "w", encoding="utf-8") as f: json.dump(doc, f, indent=2)
    return LABELS_JSON

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return
    img = args[0]
    exclude = "--exclude" in args
    save_idx = args.index("--save") if "--save" in args else -1
    res = perceive(img, exclude_self=exclude)
    os.makedirs(OUT_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(img))[0]
    out = os.path.join(OUT_DIR, f"{base}_label.png")
    render(img, res, out)
    print("OVERLAY:", out)
    print("LEP:", res["lep"], "POT:", res["pot"])
    print("\nPREDICTED (open sides):")
    for r in range(6):
        row=[]
        for c in range(6):
            kind,sides,_ = res["grid"][(r,c)]
            row.append(''.join(x for x in "NESW" if x in sides) or '-')
        print(f"r{r}: " + " | ".join(row))
    tpl = correction_template(res, img)
    print("\nCORRECTION_TEMPLATE (fix wrong cells, then save):")
    print(json.dumps(tpl, ensure_ascii=False))
    if save_idx >= 0 and save_idx+1 < len(args):
        with open(args[save_idx+1], "r", encoding="utf-8") as f: board=json.load(f)
        board["image"] = img
        path = append_board(board)
        print("\nSAVED to", path)

if __name__ == "__main__":
    main()
