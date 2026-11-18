import sys
sys.path.insert(0, r"C:\Users\Usernom\Documents\Terramine\src")
import device

x, p = device.dump_ui()
print("path", p, "len", len(x))
nodes = device.parse_nodes(x)
print("nodes", len(nodes))
for n in nodes:
    t = (n["text"] or n["desc"]).strip()
    if t or (n["rect"] and n["clickable"]):
        print(n["cls"].split(".")[-1], repr(t[:70]), n["rect"], "click" if n["clickable"] else "")
