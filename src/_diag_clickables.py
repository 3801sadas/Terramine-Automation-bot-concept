"""List every clickable node in the AD_STORE polls of run 013."""
import os, re

base = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\ad_close\runs\20261116_194433"
for n in [4, 6, 9, 13]:
    p = os.path.join(base, "poll_%02d.xml" % n)
    if not os.path.exists(p):
        continue
    s = open(p, encoding="utf-8", errors="ignore").read()
    print("=====", n, "nodes:", len(re.findall(r"<node", s)))
    for m in re.finditer(r"<node[^>]*>", s):
        t = m.group(0)
        a = dict(re.findall(r'([\w:-]+)="([^"]*)"', t))
        if a.get("clickable") != "true":
            continue
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', t)
        if not b:
            continue
        x1, y1, x2, y2 = (int(v) for v in b.groups())
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        desc = a.get("content-desc", "")
        text = a.get("text", "")
        cls = a.get("class", "")
        # only interesting ones: near edges, or with a label
        if (cx < 200 or cx > 880 or cy < 300) or desc or text:
            print(f"  ({cx:4d},{cy:4d}) cls={cls[:34]:34s} desc={desc[:24]:24s} text={text[:24]!r}")