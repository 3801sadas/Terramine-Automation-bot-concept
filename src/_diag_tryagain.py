import re, sys
sys.path.insert(0, "src")
import device

xml = device.dump_ui()[0]
for m in re.finditer(r"<node[^>]*>", xml):
    t = m.group(0)
    a = dict(re.findall(r'([\w:-]+)="([^"]*)"', t))
    blob = a.get("text", "") + a.get("content-desc", "")
    if "Play Again" in blob or "Watch Ad" in blob:
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', t)
        if b:
            x1, y1, x2, y2 = (int(v) for v in b.groups())
            print(f"{blob[:20]:20s} center=({(x1+x2)//2},{(y1+y2)//2}) clickable={a.get('clickable')}")